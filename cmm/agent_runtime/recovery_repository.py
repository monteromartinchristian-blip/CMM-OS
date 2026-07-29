"""Phase 9.16 – Recovery Repository.

Defines the repository interface and thread-safe in-memory implementation for persisting
RecoveryContexts, RecoveryDecisions, RecoveryAttempts, and RecoveryExecutionResults.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Sequence

from cmm.agent_runtime.errors import (
    RecoveryIdempotencyError,
    RecoveryRepositoryError,
)
from cmm.agent_runtime.recovery_contracts import (
    RecoveryAttempt,
    RecoveryContext,
    RecoveryDecision,
    RecoveryExecutionResult,
)


class RecoveryRepository(ABC):
    """Abstract interface for storing and retrieving recovery data."""

    @abstractmethod
    def save_context(self, context: RecoveryContext) -> RecoveryContext:
        """Persist a RecoveryContext."""

    @abstractmethod
    def get_context(self, recovery_context_id: str) -> RecoveryContext | None:
        """Retrieve a RecoveryContext by ID."""

    @abstractmethod
    def get_contexts_by_run(self, agent_run_id: str) -> Sequence[RecoveryContext]:
        """Retrieve all RecoveryContexts for an agent run ID."""

    @abstractmethod
    def get_contexts_by_workflow(self, workflow_id: str) -> Sequence[RecoveryContext]:
        """Retrieve all RecoveryContexts for a workflow ID."""

    @abstractmethod
    def get_history_by_operation(self, operation_id: str) -> Sequence[RecoveryContext]:
        """Retrieve all RecoveryContexts for a failed operation ID."""

    @abstractmethod
    def save_decision(self, decision: RecoveryDecision) -> RecoveryDecision:
        """Persist a RecoveryDecision with idempotency and fingerprint verification."""

    @abstractmethod
    def get_decision(self, recovery_decision_id: str) -> RecoveryDecision | None:
        """Retrieve a RecoveryDecision by decision ID."""

    @abstractmethod
    def get_decision_by_context(
        self, recovery_context_id: str
    ) -> RecoveryDecision | None:
        """Retrieve the latest RecoveryDecision for a context ID."""

    @abstractmethod
    def get_pending_decisions(self) -> Sequence[RecoveryDecision]:
        """Retrieve all pending recovery decisions."""

    @abstractmethod
    def save_attempt(
        self, recovery_context_id: str, attempt: RecoveryAttempt
    ) -> RecoveryAttempt:
        """Add a RecoveryAttempt to the context history without removing prior attempts."""

    @abstractmethod
    def save_execution_result(
        self, result: RecoveryExecutionResult
    ) -> RecoveryExecutionResult:
        """Persist a final RecoveryExecutionResult."""

    @abstractmethod
    def get_execution_result(
        self, recovery_execution_id: str
    ) -> RecoveryExecutionResult | None:
        """Retrieve a RecoveryExecutionResult by execution ID."""


class InMemoryRecoveryRepository(RecoveryRepository):
    """Thread-safe, in-memory implementation of RecoveryRepository."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._contexts: dict[str, RecoveryContext] = {}
        self._decisions: dict[str, RecoveryDecision] = {}
        self._idempotency_index: dict[str, RecoveryDecision] = {}
        self._attempts: dict[str, list[RecoveryAttempt]] = {}
        self._execution_results: dict[str, RecoveryExecutionResult] = {}

    def save_context(self, context: RecoveryContext) -> RecoveryContext:
        with self._lock:
            existing = self._contexts.get(context.recovery_context_id)
            if existing:
                if existing.fingerprint != context.fingerprint:
                    raise RecoveryIdempotencyError(
                        f"RecoveryContext ID '{context.recovery_context_id}' exists with a different fingerprint."
                    )
                return existing
            self._contexts[context.recovery_context_id] = context
            if context.recovery_context_id not in self._attempts:
                self._attempts[context.recovery_context_id] = list(
                    context.retry_history
                )
            return context

    def get_context(self, recovery_context_id: str) -> RecoveryContext | None:
        with self._lock:
            return self._contexts.get(recovery_context_id)

    def get_contexts_by_run(self, agent_run_id: str) -> list[RecoveryContext]:
        with self._lock:
            return [
                c for c in self._contexts.values() if c.agent_run_id == agent_run_id
            ]

    def get_contexts_by_workflow(self, workflow_id: str) -> list[RecoveryContext]:
        with self._lock:
            return [c for c in self._contexts.values() if c.workflow_id == workflow_id]

    def get_history_by_operation(self, operation_id: str) -> list[RecoveryContext]:
        with self._lock:
            return [
                c
                for c in self._contexts.values()
                if c.failed_operation_id == operation_id
            ]

    def save_decision(self, decision: RecoveryDecision) -> RecoveryDecision:
        with self._lock:
            # Check idempotency key conflict
            existing_by_key = self._idempotency_index.get(decision.idempotency_key)
            if existing_by_key:
                if existing_by_key.fingerprint == decision.fingerprint:
                    return existing_by_key
                raise RecoveryIdempotencyError(
                    f"Idempotency key '{decision.idempotency_key}' already used with different fingerprint."
                )

            # Check decision ID conflict
            existing_by_id = self._decisions.get(decision.recovery_decision_id)
            if existing_by_id:
                if existing_by_id.fingerprint == decision.fingerprint:
                    return existing_by_id
                raise RecoveryRepositoryError(
                    f"Decision ID '{decision.recovery_decision_id}' already exists with different fingerprint."
                )

            self._decisions[decision.recovery_decision_id] = decision
            self._idempotency_index[decision.idempotency_key] = decision
            return decision

    def get_decision(self, recovery_decision_id: str) -> RecoveryDecision | None:
        with self._lock:
            return self._decisions.get(recovery_decision_id)

    def get_decision_by_context(
        self, recovery_context_id: str
    ) -> RecoveryDecision | None:
        with self._lock:
            matching = [
                d
                for d in self._decisions.values()
                if d.recovery_context_id == recovery_context_id
            ]
            if not matching:
                return None
            # Return most recently decided
            return max(matching, key=lambda d: d.decided_at)

    def get_pending_decisions(self) -> list[RecoveryDecision]:
        with self._lock:
            # Return decisions whose context status or execution is not finalized
            executed_dec_ids = {
                res.recovery_decision_id for res in self._execution_results.values()
            }
            return [
                d
                for d in self._decisions.values()
                if d.recovery_decision_id not in executed_dec_ids
            ]

    def save_attempt(
        self, recovery_context_id: str, attempt: RecoveryAttempt
    ) -> RecoveryAttempt:
        with self._lock:
            ctx = self._contexts.get(recovery_context_id)
            if not ctx:
                raise RecoveryRepositoryError(
                    f"Cannot save attempt for non-existent RecoveryContext ID '{recovery_context_id}'."
                )
            if recovery_context_id not in self._attempts:
                self._attempts[recovery_context_id] = []

            # Append attempt
            self._attempts[recovery_context_id].append(attempt)

            # Update context retry_history immutably
            updated_history = tuple(self._attempts[recovery_context_id])
            updated_ctx = RecoveryContext(
                recovery_context_id=ctx.recovery_context_id,
                agent_run_id=ctx.agent_run_id,
                goal_id=ctx.goal_id,
                workflow_id=ctx.workflow_id,
                iteration_id=ctx.iteration_id,
                failed_task_id=ctx.failed_task_id,
                failed_operation_id=ctx.failed_operation_id,
                error=ctx.error,
                validation_result_ids=ctx.validation_result_ids,
                retry_history=updated_history,
                checkpoint_ids=ctx.checkpoint_ids,
                transaction_boundary_id=ctx.transaction_boundary_id,
                remaining_budget=ctx.remaining_budget,
                executed_operations=ctx.executed_operations,
                side_effects=ctx.side_effects,
                partial_changes=ctx.partial_changes,
                current_state=ctx.current_state,
                constraints=ctx.constraints,
                approvals=ctx.approvals,
                risks=ctx.risks,
                knowledge_version=ctx.knowledge_version,
                memory_version=ctx.memory_version,
                created_at=ctx.created_at,
                metadata=ctx.metadata,
                fingerprint=ctx.fingerprint,
            )
            self._contexts[recovery_context_id] = updated_ctx
            return attempt

    def save_execution_result(
        self, result: RecoveryExecutionResult
    ) -> RecoveryExecutionResult:
        with self._lock:
            existing = self._execution_results.get(result.recovery_execution_id)
            if existing:
                if existing.fingerprint == result.fingerprint:
                    return existing
                raise RecoveryRepositoryError(
                    f"Execution result '{result.recovery_execution_id}' already finalized and immutable."
                )
            self._execution_results[result.recovery_execution_id] = result
            return result

    def get_execution_result(
        self, recovery_execution_id: str
    ) -> RecoveryExecutionResult | None:
        with self._lock:
            return self._execution_results.get(recovery_execution_id)
