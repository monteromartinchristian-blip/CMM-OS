"""Phase 8.13 – Resolution Memory Contracts & Enums.

Defines immutable, typed contracts for storing cognitive decision history and querying resolution memory.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from cmm.cognitive.contracts import utc_now
from cmm.cognitive.errors import InvalidResolutionMemoryEntryError
from cmm.cognitive.resolution_contracts import ResolutionDecision
from cmm.cognitive.resolution_executor_contracts import ExecutionStatus
from cmm.cognitive.resolution_policy_contracts import PolicyDecision


def _require_aware(value: datetime | None, field_name: str) -> None:
    if value is not None:
        if not isinstance(value, datetime):
            raise InvalidResolutionMemoryEntryError(
                f"{field_name} must be a datetime instance"
            )
        if value.tzinfo is None:
            raise InvalidResolutionMemoryEntryError(
                f"{field_name} must be timezone-aware when provided"
            )


def generate_resolution_memory_id(
    contradiction_id: str,
    proposal_id: str | None,
    decision: ResolutionDecision | str,
    execution_status: ExecutionStatus | str,
    created_at: datetime | str | None = None,
) -> str:
    """Generate a deterministic cognitive identifier for a resolution memory entry."""
    if not isinstance(contradiction_id, str) or not contradiction_id.strip():
        raise InvalidResolutionMemoryEntryError(
            "contradiction_id must be a non-empty string"
        )

    dec_val = (
        decision.value
        if isinstance(decision, ResolutionDecision)
        else str(decision).strip()
    )
    if not dec_val:
        raise InvalidResolutionMemoryEntryError(
            "decision must be a valid non-empty value"
        )

    exec_val = (
        execution_status.value
        if isinstance(execution_status, ExecutionStatus)
        else str(execution_status).strip()
    )
    if not exec_val:
        raise InvalidResolutionMemoryEntryError(
            "execution_status must be a valid non-empty value"
        )

    prop_val = (
        proposal_id.strip()
        if proposal_id and isinstance(proposal_id, str) and proposal_id.strip()
        else ""
    )

    ts_val = ""
    if created_at is not None:
        if isinstance(created_at, datetime):
            ts_val = created_at.isoformat()
        else:
            ts_val = str(created_at).strip()

    seed = f"{contradiction_id.strip()}:{prop_val}:{dec_val}:{exec_val}:{ts_val}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"resolution-memory:{digest}"


@dataclass(frozen=True, slots=True)
class ResolutionMemoryEntry:
    """Immutable record of a historical cognitive decision and execution trace."""

    id: str
    contradiction_id: str
    item_a_id: str
    item_b_id: str
    proposal_id: str | None
    decision: ResolutionDecision
    policy_decision: PolicyDecision
    execution_status: ExecutionStatus
    confidence: float
    actor_id: str | None
    created_at: datetime
    updated_at: datetime
    rationale: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise InvalidResolutionMemoryEntryError("id must be a non-empty string")
        object.__setattr__(self, "id", self.id.strip())

        if (
            not isinstance(self.contradiction_id, str)
            or not self.contradiction_id.strip()
        ):
            raise InvalidResolutionMemoryEntryError(
                "contradiction_id must be a non-empty string"
            )
        object.__setattr__(self, "contradiction_id", self.contradiction_id.strip())

        if not isinstance(self.item_a_id, str) or not self.item_a_id.strip():
            raise InvalidResolutionMemoryEntryError(
                "item_a_id must be a non-empty string"
            )
        object.__setattr__(self, "item_a_id", self.item_a_id.strip())

        if not isinstance(self.item_b_id, str) or not self.item_b_id.strip():
            raise InvalidResolutionMemoryEntryError(
                "item_b_id must be a non-empty string"
            )
        object.__setattr__(self, "item_b_id", self.item_b_id.strip())

        if self.proposal_id is not None:
            if not isinstance(self.proposal_id, str):
                raise InvalidResolutionMemoryEntryError(
                    "proposal_id must be a string or None"
                )
            prop_str = self.proposal_id.strip()
            object.__setattr__(self, "proposal_id", prop_str if prop_str else None)

        dec_val = self.decision
        if isinstance(dec_val, str):
            try:
                dec_val = ResolutionDecision(dec_val.lower())
            except ValueError as exc:
                raise InvalidResolutionMemoryEntryError(
                    f"Unknown ResolutionDecision: {dec_val}"
                ) from exc
        elif not isinstance(dec_val, ResolutionDecision):
            raise InvalidResolutionMemoryEntryError(f"Invalid decision: {dec_val}")
        object.__setattr__(self, "decision", dec_val)

        pol_val = self.policy_decision
        if isinstance(pol_val, str):
            try:
                pol_val = PolicyDecision(pol_val.lower())
            except ValueError:
                try:
                    pol_val = PolicyDecision[pol_val.upper()]
                except KeyError as exc:
                    raise InvalidResolutionMemoryEntryError(
                        f"Unknown PolicyDecision: {pol_val}"
                    ) from exc
        elif not isinstance(pol_val, PolicyDecision):
            raise InvalidResolutionMemoryEntryError(
                f"Invalid policy_decision: {pol_val}"
            )
        object.__setattr__(self, "policy_decision", pol_val)

        exec_val = self.execution_status
        if isinstance(exec_val, str):
            try:
                exec_val = ExecutionStatus(exec_val.lower())
            except ValueError:
                try:
                    exec_val = ExecutionStatus[exec_val.upper()]
                except KeyError as exc:
                    raise InvalidResolutionMemoryEntryError(
                        f"Unknown ExecutionStatus: {exec_val}"
                    ) from exc
        elif not isinstance(exec_val, ExecutionStatus):
            raise InvalidResolutionMemoryEntryError(
                f"Invalid execution_status: {exec_val}"
            )
        object.__setattr__(self, "execution_status", exec_val)

        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not (0.0 <= float(self.confidence) <= 1.0)
        ):
            raise InvalidResolutionMemoryEntryError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
        object.__setattr__(self, "confidence", float(self.confidence))

        if self.actor_id is not None:
            if not isinstance(self.actor_id, str):
                raise InvalidResolutionMemoryEntryError(
                    "actor_id must be a string or None"
                )
            actor_str = self.actor_id.strip()
            object.__setattr__(self, "actor_id", actor_str if actor_str else None)

        if not isinstance(self.created_at, datetime):
            raise InvalidResolutionMemoryEntryError("created_at must be a datetime")
        _require_aware(self.created_at, "created_at")

        if not isinstance(self.updated_at, datetime):
            raise InvalidResolutionMemoryEntryError("updated_at must be a datetime")
        _require_aware(self.updated_at, "updated_at")

        object.__setattr__(
            self, "rationale", tuple(str(r) for r in self.rationale or ())
        )
        object.__setattr__(
            self, "evidence_ids", tuple(str(e) for e in self.evidence_ids or ())
        )
        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization."""
        return {
            "id": self.id,
            "contradiction_id": self.contradiction_id,
            "item_a_id": self.item_a_id,
            "item_b_id": self.item_b_id,
            "proposal_id": self.proposal_id,
            "decision": self.decision.value,
            "policy_decision": self.policy_decision.value,
            "execution_status": self.execution_status.value,
            "confidence": self.confidence,
            "actor_id": self.actor_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "rationale": list(self.rationale),
            "evidence_ids": list(self.evidence_ids),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ResolutionMemoryEntry:
        """Canonical deserialization from mapping."""
        if not isinstance(payload, Mapping):
            raise InvalidResolutionMemoryEntryError("payload must be a mapping")

        entry_id = payload.get("id")
        if not isinstance(entry_id, str):
            raise InvalidResolutionMemoryEntryError("id must be a string")

        contradiction_id = payload.get("contradiction_id")
        if not isinstance(contradiction_id, str):
            raise InvalidResolutionMemoryEntryError("contradiction_id must be a string")

        item_a_id = payload.get("item_a_id")
        if not isinstance(item_a_id, str):
            raise InvalidResolutionMemoryEntryError("item_a_id must be a string")

        item_b_id = payload.get("item_b_id")
        if not isinstance(item_b_id, str):
            raise InvalidResolutionMemoryEntryError("item_b_id must be a string")

        dec_raw = payload.get("decision")
        if dec_raw is None:
            raise InvalidResolutionMemoryEntryError("decision is required")

        pol_raw = payload.get("policy_decision")
        if pol_raw is None:
            raise InvalidResolutionMemoryEntryError("policy_decision is required")

        exec_raw = payload.get("execution_status")
        if exec_raw is None:
            raise InvalidResolutionMemoryEntryError("execution_status is required")

        conf_raw = payload.get("confidence")
        if conf_raw is None:
            raise InvalidResolutionMemoryEntryError("confidence is required")

        created_at_raw = payload.get("created_at")
        if isinstance(created_at_raw, datetime):
            created_at = created_at_raw
        elif isinstance(created_at_raw, str):
            try:
                created_at = datetime.fromisoformat(created_at_raw)
            except ValueError as exc:
                raise InvalidResolutionMemoryEntryError(
                    f"Invalid ISO format for created_at: {created_at_raw}"
                ) from exc
        else:
            raise InvalidResolutionMemoryEntryError("created_at is required")

        updated_at_raw = payload.get("updated_at")
        if isinstance(updated_at_raw, datetime):
            updated_at = updated_at_raw
        elif isinstance(updated_at_raw, str):
            try:
                updated_at = datetime.fromisoformat(updated_at_raw)
            except ValueError as exc:
                raise InvalidResolutionMemoryEntryError(
                    f"Invalid ISO format for updated_at: {updated_at_raw}"
                ) from exc
        else:
            updated_at = created_at

        return cls(
            id=entry_id,
            contradiction_id=contradiction_id,
            item_a_id=item_a_id,
            item_b_id=item_b_id,
            proposal_id=payload.get("proposal_id"),
            decision=dec_raw,
            policy_decision=pol_raw,
            execution_status=exec_raw,
            confidence=conf_raw,
            actor_id=payload.get("actor_id"),
            created_at=created_at,
            updated_at=updated_at,
            rationale=tuple(payload.get("rationale") or ()),
            evidence_ids=tuple(payload.get("evidence_ids") or ()),
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResolutionMemoryEntry:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(data)


@dataclass(frozen=True, slots=True)
class ResolutionMemoryQuery:
    """Query parameter container for searching resolution memory history."""

    contradiction_id: str | None = None
    item_id: str | None = None
    decision: ResolutionDecision | str | None = None
    policy_decision: PolicyDecision | str | None = None
    execution_status: ExecutionStatus | str | None = None
    actor_id: str | None = None
    minimum_confidence: float | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    limit: int | None = None
    offset: int = 0

    def __post_init__(self) -> None:
        if self.minimum_confidence is not None:
            if (
                isinstance(self.minimum_confidence, bool)
                or not isinstance(self.minimum_confidence, (int, float))
                or not (0.0 <= float(self.minimum_confidence) <= 1.0)
            ):
                raise InvalidResolutionMemoryEntryError(
                    f"minimum_confidence must be between 0.0 and 1.0, got {self.minimum_confidence}"
                )
            object.__setattr__(
                self, "minimum_confidence", float(self.minimum_confidence)
            )

        if self.created_after is not None:
            _require_aware(self.created_after, "created_after")
        if self.created_before is not None:
            _require_aware(self.created_before, "created_before")

        if (
            self.created_after is not None
            and self.created_before is not None
            and self.created_after > self.created_before
        ):
            raise InvalidResolutionMemoryEntryError(
                "created_after cannot be after created_before"
            )

        if self.decision is not None:
            dec_val = self.decision
            if isinstance(dec_val, str):
                try:
                    dec_val = ResolutionDecision(dec_val.lower())
                except ValueError as exc:
                    raise InvalidResolutionMemoryEntryError(
                        f"Unknown ResolutionDecision: {dec_val}"
                    ) from exc
            elif not isinstance(dec_val, ResolutionDecision):
                raise InvalidResolutionMemoryEntryError(f"Invalid decision: {dec_val}")
            object.__setattr__(self, "decision", dec_val)

        if self.policy_decision is not None:
            pol_val = self.policy_decision
            if isinstance(pol_val, str):
                try:
                    pol_val = PolicyDecision(pol_val.lower())
                except ValueError:
                    try:
                        pol_val = PolicyDecision[pol_val.upper()]
                    except KeyError as exc:
                        raise InvalidResolutionMemoryEntryError(
                            f"Unknown PolicyDecision: {pol_val}"
                        ) from exc
            elif not isinstance(pol_val, PolicyDecision):
                raise InvalidResolutionMemoryEntryError(
                    f"Invalid policy_decision: {pol_val}"
                )
            object.__setattr__(self, "policy_decision", pol_val)

        if self.execution_status is not None:
            exec_val = self.execution_status
            if isinstance(exec_val, str):
                try:
                    exec_val = ExecutionStatus(exec_val.lower())
                except ValueError:
                    try:
                        exec_val = ExecutionStatus[exec_val.upper()]
                    except KeyError as exc:
                        raise InvalidResolutionMemoryEntryError(
                            f"Unknown ExecutionStatus: {exec_val}"
                        ) from exc
            elif not isinstance(exec_val, ExecutionStatus):
                raise InvalidResolutionMemoryEntryError(
                    f"Invalid execution_status: {exec_val}"
                )
            object.__setattr__(self, "execution_status", exec_val)

        if self.limit is not None and (
            isinstance(self.limit, bool)
            or not isinstance(self.limit, int)
            or self.limit < 0
        ):
            raise InvalidResolutionMemoryEntryError(
                "limit must be a non-negative integer"
            )

        if (
            isinstance(self.offset, bool)
            or not isinstance(self.offset, int)
            or self.offset < 0
        ):
            raise InvalidResolutionMemoryEntryError(
                "offset must be a non-negative integer"
            )


@dataclass(frozen=True, slots=True)
class ResolutionMemoryResult:
    """Immutable result wrapper for queries over resolution memory."""

    entries: tuple[ResolutionMemoryEntry, ...]
    total_count: int
    query: ResolutionMemoryQuery | None = None
    created_at: datetime = field(default_factory=utc_now)
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", tuple(self.entries or ()))
        for entry in self.entries:
            if not isinstance(entry, ResolutionMemoryEntry):
                raise InvalidResolutionMemoryEntryError(
                    f"entries must contain ResolutionMemoryEntry instances, got {type(entry).__name__}"
                )

        if (
            isinstance(self.total_count, bool)
            or not isinstance(self.total_count, int)
            or self.total_count < 0
        ):
            raise InvalidResolutionMemoryEntryError(
                "total_count must be a non-negative integer"
            )

        if not isinstance(self.created_at, datetime):
            raise InvalidResolutionMemoryEntryError("created_at must be a datetime")
        _require_aware(self.created_at, "created_at")

        object.__setattr__(self, "warnings", tuple(str(w) for w in self.warnings or ()))
