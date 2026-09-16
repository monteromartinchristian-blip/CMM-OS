"""Phase 11.2 — the orchestration decision repository.

Phase 11.2 introduces exactly one new persistence owner:
``OrchestrationDecisionRepository``.  It records the orchestration layer's own
decisions and nothing else — it is not a session, goal, workflow, memory,
knowledge or event repository, and it adds no file, SQLite or database
persistence.

The official in-memory implementation is durable only for the lifetime of the
process.  It is intentionally narrow and safe:

* it stores immutable decision records and never copies canonical subsystem
  state;
* an identical replay of the same decision identity is idempotent and returns
  the already-stored record;
* a contradictory reuse of a decision identity or a request identity fails
  closed rather than silently creating conflicting history.
"""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

from cmm.orchestration.contracts import OrchestrationDecisionRecord
from cmm.orchestration.errors import DecisionPersistenceError

__all__ = [
    "InMemoryOrchestrationDecisionRepository",
    "OrchestrationDecisionRepository",
]


def _identifier(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


@runtime_checkable
class OrchestrationDecisionRepository(Protocol):
    """Narrow persistence boundary for orchestration decision records."""

    def save(
        self, record: OrchestrationDecisionRecord
    ) -> OrchestrationDecisionRecord: ...

    def get(self, decision_id: str) -> OrchestrationDecisionRecord | None: ...

    def get_by_request_id(
        self, request_id: str
    ) -> OrchestrationDecisionRecord | None: ...

    def list_for_session(
        self, session_id: str
    ) -> tuple[OrchestrationDecisionRecord, ...]: ...


class InMemoryOrchestrationDecisionRepository:
    """Thread-safe in-memory orchestration decision repository.

    The repository owns no canonical state and performs no I/O.  Every returned
    record is the immutable decision value itself, so a caller can never mutate
    stored history through the repository.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._decisions: dict[str, OrchestrationDecisionRecord] = {}
        self._by_request: dict[str, str] = {}

    # ── Writes ───────────────────────────────────────────────────────────────

    def save(self, record: OrchestrationDecisionRecord) -> OrchestrationDecisionRecord:
        """Store *record*, or fail closed on a contradictory duplicate."""

        if not isinstance(record, OrchestrationDecisionRecord):
            raise TypeError("record must be an OrchestrationDecisionRecord")

        with self._lock:
            existing = self._decisions.get(record.decision_id)
            if existing is not None:
                if existing.identity_payload() == record.identity_payload():
                    return existing
                raise DecisionPersistenceError(
                    "Orchestration decision identity was reused with "
                    "contradictory content",
                    details={"decision_id": record.decision_id},
                )

            request_owner = self._by_request.get(record.request_id)
            if request_owner is not None:
                raise DecisionPersistenceError(
                    "Orchestration request identity already has a decision",
                    details={
                        "request_id": record.request_id,
                        "decision_id": request_owner,
                    },
                )

            self._decisions[record.decision_id] = record
            self._by_request[record.request_id] = record.decision_id
            return record

    # ── Reads ────────────────────────────────────────────────────────────────

    def get(self, decision_id: str) -> OrchestrationDecisionRecord | None:
        """Return the decision stored under *decision_id*, or ``None``."""

        key = _identifier(decision_id, "decision_id")
        with self._lock:
            return self._decisions.get(key)

    def get_by_request_id(self, request_id: str) -> OrchestrationDecisionRecord | None:
        """Return the decision recorded for *request_id*, or ``None``."""

        key = _identifier(request_id, "request_id")
        with self._lock:
            decision_id = self._by_request.get(key)
            if decision_id is None:
                return None
            return self._decisions.get(decision_id)

    def list_for_session(
        self, session_id: str
    ) -> tuple[OrchestrationDecisionRecord, ...]:
        """Return a session's decisions in deterministic recording order.

        Ordering is by recording timestamp and then by decision ID, so the
        result depends only on stored facts and never on insertion order.
        """

        key = _identifier(session_id, "session_id")
        with self._lock:
            records = [
                record
                for record in self._decisions.values()
                if record.session_id == key
            ]
        return tuple(
            sorted(records, key=lambda item: (item.occurred_at, item.decision_id))
        )
