"""Protocol-backed store for Agent Runtime integration execution records."""

from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from cmm.agent_runtime.agent_runtime_integration_contracts import (
    IntegratedAgentExecutionResult,
    IntegrationCompensation,
    IntegrationExecutionRecord,
)
from cmm.agent_runtime.agent_runtime_integration_enums import (
    TERMINAL_INTEGRATION_STATES,
    IntegrationCompensationStatus,
    IntegrationExecutionState,
    can_transition_integration_state,
)
from cmm.agent_runtime.agent_runtime_integration_errors import (
    IntegrationDuplicateError,
    IntegrationIdempotencyConflictError,
    IntegrationNotFoundError,
    IntegrationStateError,
    IntegrationStoreConsistencyError,
    IntegrationVersionConflictError,
)


@runtime_checkable
class AgentRuntimeIntegrationStore(Protocol):
    """Storage boundary for durable Agent Runtime integration state."""

    def create(
        self, record: IntegrationExecutionRecord
    ) -> IntegrationExecutionRecord: ...

    def get(self, execution_id: str) -> IntegrationExecutionRecord | None: ...

    def update(
        self,
        record: IntegrationExecutionRecord,
        *,
        expected_version: int | None = None,
    ) -> IntegrationExecutionRecord: ...

    def get_by_request_id(
        self, request_id: str
    ) -> IntegrationExecutionRecord | None: ...

    def get_by_run_id(self, run_id: str) -> IntegrationExecutionRecord | None: ...

    def get_by_pending_approval_id(
        self, approval_id: str
    ) -> IntegrationExecutionRecord | None: ...

    def list_by_state(
        self, state: IntegrationExecutionState | str
    ) -> tuple[IntegrationExecutionRecord, ...]: ...

    def list_by_goal_id(
        self, goal_id: str
    ) -> tuple[IntegrationExecutionRecord, ...]: ...

    def list_by_agent_id(
        self, agent_id: str
    ) -> tuple[IntegrationExecutionRecord, ...]: ...

    def bind_run(
        self,
        execution_id: str,
        run_id: str,
        *,
        expected_version: int | None = None,
    ) -> IntegrationExecutionRecord: ...

    def set_pending_approval(
        self,
        execution_id: str,
        approval_id: str,
        *,
        expected_version: int | None = None,
    ) -> IntegrationExecutionRecord: ...

    def resolve_pending_approval(
        self, approval_id: str, *, expected_version: int | None = None
    ) -> IntegrationExecutionRecord: ...

    def append_compensation(
        self,
        execution_id: str,
        compensation: IntegrationCompensation,
        *,
        expected_version: int | None = None,
    ) -> IntegrationExecutionRecord: ...

    def list_pending_compensations(
        self, execution_id: str
    ) -> tuple[IntegrationCompensation, ...]: ...

    def mark_compensation_completed(
        self,
        execution_id: str,
        compensation_id: str,
        *,
        expected_version: int | None = None,
    ) -> IntegrationExecutionRecord: ...

    def transition(
        self,
        execution_id: str,
        state: IntegrationExecutionState | str,
        *,
        expected_version: int | None = None,
    ) -> IntegrationExecutionRecord: ...

    def resume(
        self,
        execution_id: str,
        state: IntegrationExecutionState | str,
        *,
        expected_version: int | None = None,
    ) -> IntegrationExecutionRecord: ...

    def cancel(
        self, execution_id: str, *, reason: str | None = None
    ) -> IntegrationExecutionRecord: ...

    def save_terminal_result(
        self,
        execution_id: str,
        result: IntegratedAgentExecutionResult,
        *,
        expected_version: int | None = None,
    ) -> IntegrationExecutionRecord: ...

    def delete(self, execution_id: str) -> bool: ...

    def clear(self) -> None: ...


class InMemoryAgentRuntimeIntegrationStore:
    """Thread-safe in-memory implementation of AgentRuntimeIntegrationStore."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: dict[str, dict] = {}
        self._request_index: dict[str, str] = {}
        self._run_index: dict[str, str] = {}
        self._approval_index: dict[str, str] = {}
        self._state_index: dict[IntegrationExecutionState, set[str]] = {}
        self._goal_index: dict[str, set[str]] = {}
        self._agent_index: dict[str, set[str]] = {}

    def create(self, record: IntegrationExecutionRecord) -> IntegrationExecutionRecord:
        with self._lock:
            normalized = self._copy(record)
            existing = self._record(normalized.execution_id)
            if existing is not None:
                if existing == normalized:
                    return self._copy(existing)
                raise IntegrationDuplicateError(
                    f"execution_id {normalized.execution_id!r} already exists"
                )
            request_owner = self._request_index.get(normalized.request_id)
            if request_owner is not None:
                current = self._record(request_owner)
                if current == normalized:
                    return self._copy(current)
                raise IntegrationIdempotencyConflictError(
                    f"request_id {normalized.request_id!r} already exists"
                )
            self._ensure_unique_run(normalized.agent_run_id, normalized.execution_id)
            self._ensure_unique_approvals(
                normalized.pending_approval_ids, normalized.execution_id
            )
            self._records[normalized.execution_id] = normalized.to_dict()
            self._add_indexes(normalized)
            return self._copy(normalized)

    def get(self, execution_id: str) -> IntegrationExecutionRecord | None:
        with self._lock:
            return self._copy_or_none(self._record(execution_id))

    def update(
        self,
        record: IntegrationExecutionRecord,
        *,
        expected_version: int | None = None,
    ) -> IntegrationExecutionRecord:
        with self._lock:
            normalized = self._copy(record)
            current = self._require_mutable(normalized.execution_id, expected_version)
            if current == normalized:
                return self._copy(current)
            if (
                normalized.request_id != current.request_id
                or normalized.goal_id != current.goal_id
            ):
                raise IntegrationIdempotencyConflictError(
                    "request_id and goal_id cannot change during update"
                )
            if current.state is not normalized.state and not (
                can_transition_integration_state(current.state, normalized.state)
            ):
                raise IntegrationStateError(
                    f"cannot transition from {current.state.value} "
                    f"to {normalized.state.value}"
                )
            updated = replace(
                normalized,
                version=current.version + 1,
                updated_at=self._now(),
            )
            return self._persist_replace(current, updated)

    def get_by_request_id(self, request_id: str) -> IntegrationExecutionRecord | None:
        with self._lock:
            execution_id = self._request_index.get(request_id)
            return self._copy_or_none(self._record(execution_id))

    def get_by_run_id(self, run_id: str) -> IntegrationExecutionRecord | None:
        with self._lock:
            execution_id = self._run_index.get(run_id)
            return self._copy_or_none(self._record(execution_id))

    def get_by_pending_approval_id(
        self, approval_id: str
    ) -> IntegrationExecutionRecord | None:
        with self._lock:
            execution_id = self._approval_index.get(approval_id)
            return self._copy_or_none(self._record(execution_id))

    def list_by_state(
        self, state: IntegrationExecutionState | str
    ) -> tuple[IntegrationExecutionRecord, ...]:
        normalized = self._state(state)
        with self._lock:
            return self._records_for_ids(self._state_index.get(normalized, set()))

    def list_by_goal_id(self, goal_id: str) -> tuple[IntegrationExecutionRecord, ...]:
        with self._lock:
            return self._records_for_ids(self._goal_index.get(goal_id, set()))

    def list_by_agent_id(self, agent_id: str) -> tuple[IntegrationExecutionRecord, ...]:
        with self._lock:
            return self._records_for_ids(self._agent_index.get(agent_id, set()))

    def bind_run(
        self,
        execution_id: str,
        run_id: str,
        *,
        expected_version: int | None = None,
    ) -> IntegrationExecutionRecord:
        with self._lock:
            current = self._require_mutable(execution_id, expected_version)
            if current.agent_run_id == run_id:
                return self._copy(current)
            if current.agent_run_id is not None:
                raise IntegrationStateError("record already has an agent_run_id")
            self._ensure_unique_run(run_id, execution_id)
            updated = self._replace(current, agent_run_id=run_id)
            return self._persist_replace(current, updated)

    def set_pending_approval(
        self,
        execution_id: str,
        approval_id: str,
        *,
        expected_version: int | None = None,
    ) -> IntegrationExecutionRecord:
        with self._lock:
            current = self._require_mutable(execution_id, expected_version)
            if approval_id in current.pending_approval_ids:
                return self._copy(current)
            self._ensure_unique_approvals((approval_id,), execution_id)
            updated = self._replace(
                current,
                pending_approval_ids=(*current.pending_approval_ids, approval_id),
            )
            return self._persist_replace(current, updated)

    def resolve_pending_approval(
        self, approval_id: str, *, expected_version: int | None = None
    ) -> IntegrationExecutionRecord:
        with self._lock:
            execution_id = self._approval_index.get(approval_id)
            if execution_id is None:
                raise IntegrationNotFoundError(
                    f"pending approval {approval_id!r} not found"
                )
            current = self._require_mutable(execution_id, expected_version)
            pending = tuple(
                item for item in current.pending_approval_ids if item != approval_id
            )
            approvals = current.approval_ids
            if approval_id not in approvals:
                approvals = (*approvals, approval_id)
            updated = self._replace(
                current, pending_approval_ids=pending, approval_ids=approvals
            )
            return self._persist_replace(current, updated)

    def append_compensation(
        self,
        execution_id: str,
        compensation: IntegrationCompensation,
        *,
        expected_version: int | None = None,
    ) -> IntegrationExecutionRecord:
        with self._lock:
            current = self._require_mutable(execution_id, expected_version)
            if compensation.execution_id != execution_id:
                raise ValueError("compensation execution_id must match record")
            for existing in current.compensations:
                if existing.compensation_id == compensation.compensation_id:
                    if existing == compensation:
                        return self._copy(current)
                    raise IntegrationIdempotencyConflictError(
                        "compensation_id already exists with different payload"
                    )
            updated = self._replace(
                current, compensations=(*current.compensations, compensation)
            )
            return self._persist_replace(current, updated)

    def list_pending_compensations(
        self, execution_id: str
    ) -> tuple[IntegrationCompensation, ...]:
        with self._lock:
            current = self._require(execution_id)
            return tuple(
                item
                for item in reversed(current.compensations)
                if item.status is IntegrationCompensationStatus.PENDING
            )

    def mark_compensation_completed(
        self,
        execution_id: str,
        compensation_id: str,
        *,
        expected_version: int | None = None,
    ) -> IntegrationExecutionRecord:
        with self._lock:
            current = self._require_mutable(execution_id, expected_version)
            found = False
            already_completed = False
            compensations: list[IntegrationCompensation] = []
            for item in current.compensations:
                if item.compensation_id != compensation_id:
                    compensations.append(item)
                    continue
                found = True
                if item.status is IntegrationCompensationStatus.COMPLETED:
                    already_completed = True
                    compensations.append(item)
                else:
                    compensations.append(
                        replace(
                            item,
                            status=IntegrationCompensationStatus.COMPLETED,
                            completed_at=self._now(),
                        )
                    )
            if not found:
                raise IntegrationNotFoundError(
                    f"compensation {compensation_id!r} not found"
                )
            if already_completed:
                return self._copy(current)
            updated = self._replace(current, compensations=tuple(compensations))
            return self._persist_replace(current, updated)

    def transition(
        self,
        execution_id: str,
        state: IntegrationExecutionState | str,
        *,
        expected_version: int | None = None,
    ) -> IntegrationExecutionRecord:
        target = self._state(state)
        with self._lock:
            current = self._require_mutable(execution_id, expected_version)
            if current.state is target:
                return self._copy(current)
            if not can_transition_integration_state(current.state, target):
                raise IntegrationStateError(
                    f"cannot transition from {current.state.value} to {target.value}"
                )
            updated = self._replace(
                current,
                state=target,
                result=None
                if current.result is not None and not current.result.is_terminal
                else current.result,
            )
            return self._persist_replace(current, updated)

    def resume(
        self,
        execution_id: str,
        state: IntegrationExecutionState | str,
        *,
        expected_version: int | None = None,
    ) -> IntegrationExecutionRecord:
        return self.transition(execution_id, state, expected_version=expected_version)

    def cancel(
        self, execution_id: str, *, reason: str | None = None
    ) -> IntegrationExecutionRecord:
        with self._lock:
            current = self._require(execution_id)
            if current.state is IntegrationExecutionState.CANCELLED:
                return self._copy(current)
            if current.state in TERMINAL_INTEGRATION_STATES:
                raise IntegrationStateError("terminal records cannot be cancelled")
            updated = self._replace(
                current,
                state=IntegrationExecutionState.CANCELLED,
                result=None
                if current.result is not None and not current.result.is_terminal
                else current.result,
                completed_at=self._now(),
                last_error=reason or current.last_error,
            )
            return self._persist_replace(current, updated, allow_terminal=True)

    def save_terminal_result(
        self,
        execution_id: str,
        result: IntegratedAgentExecutionResult,
        *,
        expected_version: int | None = None,
    ) -> IntegrationExecutionRecord:
        with self._lock:
            current = self._require(execution_id)
            if expected_version is not None and current.version != expected_version:
                raise IntegrationVersionConflictError(
                    f"expected version {expected_version}, found {current.version}"
                )
            if result.final_state not in TERMINAL_INTEGRATION_STATES:
                raise IntegrationStateError("result must be terminal")
            if current.result is not None:
                if current.result == result:
                    return self._copy(current)
                raise IntegrationIdempotencyConflictError(
                    "terminal result already exists with different payload"
                )
            if current.state is not result.final_state and not (
                can_transition_integration_state(current.state, result.final_state)
            ):
                raise IntegrationStateError(
                    "terminal result final_state is not reachable from current state"
                )
            updated = self._replace(
                current,
                state=result.final_state,
                result=result,
                completed_at=result.completed_at or self._now(),
            )
            return self._persist_replace(current, updated, allow_terminal=True)

    def delete(self, execution_id: str) -> bool:
        with self._lock:
            current = self._record(execution_id)
            if current is None:
                return False
            self._remove_indexes(current)
            self._records.pop(execution_id, None)
            return True

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self._request_index.clear()
            self._run_index.clear()
            self._approval_index.clear()
            self._state_index.clear()
            self._goal_index.clear()
            self._agent_index.clear()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _state(state: IntegrationExecutionState | str) -> IntegrationExecutionState:
        return (
            state
            if isinstance(state, IntegrationExecutionState)
            else IntegrationExecutionState(state)
        )

    @staticmethod
    def _copy(record: IntegrationExecutionRecord) -> IntegrationExecutionRecord:
        return IntegrationExecutionRecord.from_dict(record.to_dict())

    def _copy_or_none(
        self, record: IntegrationExecutionRecord | None
    ) -> IntegrationExecutionRecord | None:
        return self._copy(record) if record is not None else None

    def _record(self, execution_id: str | None) -> IntegrationExecutionRecord | None:
        if execution_id is None:
            return None
        data = self._records.get(execution_id)
        return IntegrationExecutionRecord.from_dict(data) if data is not None else None

    def _require(self, execution_id: str) -> IntegrationExecutionRecord:
        current = self._record(execution_id)
        if current is None:
            raise IntegrationNotFoundError(f"execution {execution_id!r} not found")
        self._validate_indexes(current)
        return current

    def _require_mutable(
        self, execution_id: str, expected_version: int | None = None
    ) -> IntegrationExecutionRecord:
        current = self._require(execution_id)
        if expected_version is not None and current.version != expected_version:
            raise IntegrationVersionConflictError(
                f"expected version {expected_version}, found {current.version}"
            )
        if current.state in TERMINAL_INTEGRATION_STATES or (
            current.result is not None and current.result.is_terminal
        ):
            raise IntegrationStateError("terminal records are immutable")
        return current

    def _replace(
        self, current: IntegrationExecutionRecord, **changes: object
    ) -> IntegrationExecutionRecord:
        # ``changes`` is restricted to this store's typed internal call sites.
        # mypy cannot validate a dynamic kwargs mapping against dataclass fields.
        return replace(
            current,
            **changes,  # type: ignore[arg-type]
            version=current.version + 1,
            updated_at=self._now(),
        )

    def _persist_replace(
        self,
        current: IntegrationExecutionRecord,
        updated: IntegrationExecutionRecord,
        *,
        allow_terminal: bool = False,
    ) -> IntegrationExecutionRecord:
        if current.state in TERMINAL_INTEGRATION_STATES and not allow_terminal:
            raise IntegrationStateError("terminal records are immutable")
        self._validate_indexes(current)
        self._ensure_unique_run(updated.agent_run_id, updated.execution_id)
        self._ensure_unique_approvals(
            updated.pending_approval_ids, updated.execution_id
        )
        self._remove_indexes(current)
        self._records[updated.execution_id] = updated.to_dict()
        self._add_indexes(updated)
        return self._copy(updated)

    def _records_for_ids(
        self, execution_ids: Iterable[str]
    ) -> tuple[IntegrationExecutionRecord, ...]:
        records = [self._record(execution_id) for execution_id in execution_ids]
        present = [record for record in records if record is not None]
        present.sort(key=lambda record: (record.created_at, record.execution_id))
        return tuple(self._copy(record) for record in present)

    def _add_to_index(
        self, index: dict[str, set[str]], key: str, execution_id: str
    ) -> None:
        index.setdefault(key, set()).add(execution_id)

    def _remove_from_index(
        self, index: dict[str, set[str]], key: str, execution_id: str
    ) -> None:
        ids = index.get(key)
        if ids is None:
            return
        ids.discard(execution_id)
        if not ids:
            index.pop(key, None)

    def _add_indexes(self, record: IntegrationExecutionRecord) -> None:
        self._request_index[record.request_id] = record.execution_id
        if record.agent_run_id is not None:
            self._run_index[record.agent_run_id] = record.execution_id
        for approval_id in record.pending_approval_ids:
            self._approval_index[approval_id] = record.execution_id
        self._state_index.setdefault(record.state, set()).add(record.execution_id)
        self._add_to_index(self._goal_index, record.goal_id, record.execution_id)
        if record.agent_id is not None:
            self._add_to_index(self._agent_index, record.agent_id, record.execution_id)

    def _remove_indexes(self, record: IntegrationExecutionRecord) -> None:
        if self._request_index.get(record.request_id) == record.execution_id:
            self._request_index.pop(record.request_id, None)
        if (
            record.agent_run_id is not None
            and self._run_index.get(record.agent_run_id) == record.execution_id
        ):
            self._run_index.pop(record.agent_run_id, None)
        for approval_id in record.pending_approval_ids:
            if self._approval_index.get(approval_id) == record.execution_id:
                self._approval_index.pop(approval_id, None)
        ids = self._state_index.get(record.state)
        if ids is not None:
            ids.discard(record.execution_id)
            if not ids:
                self._state_index.pop(record.state, None)
        self._remove_from_index(self._goal_index, record.goal_id, record.execution_id)
        if record.agent_id is not None:
            self._remove_from_index(
                self._agent_index, record.agent_id, record.execution_id
            )

    def _ensure_unique_run(self, run_id: str | None, execution_id: str) -> None:
        if run_id is None:
            return
        owner = self._run_index.get(run_id)
        if owner is not None and owner != execution_id:
            raise IntegrationDuplicateError(f"run_id {run_id!r} already exists")

    def _ensure_unique_approvals(
        self, approval_ids: Iterable[str], execution_id: str
    ) -> None:
        for approval_id in approval_ids:
            owner = self._approval_index.get(approval_id)
            if owner is not None and owner != execution_id:
                raise IntegrationDuplicateError(
                    f"approval_id {approval_id!r} already exists"
                )

    def _validate_indexes(self, record: IntegrationExecutionRecord) -> None:
        if self._records.get(record.execution_id) is None:
            raise IntegrationStoreConsistencyError("record missing from primary index")
        if self._request_index.get(record.request_id) != record.execution_id:
            raise IntegrationStoreConsistencyError("request index is stale")
        if (
            record.agent_run_id is not None
            and self._run_index.get(record.agent_run_id) != record.execution_id
        ):
            raise IntegrationStoreConsistencyError("run index is stale")
        for approval_id in record.pending_approval_ids:
            if self._approval_index.get(approval_id) != record.execution_id:
                raise IntegrationStoreConsistencyError("approval index is stale")
        if record.execution_id not in self._state_index.get(record.state, set()):
            raise IntegrationStoreConsistencyError("state index is stale")
        if record.execution_id not in self._goal_index.get(record.goal_id, set()):
            raise IntegrationStoreConsistencyError("goal index is stale")
        if record.agent_id is not None and record.execution_id not in (
            self._agent_index.get(record.agent_id, set())
        ):
            raise IntegrationStoreConsistencyError("agent index is stale")
