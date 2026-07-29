"""Phase 9.15 – Transaction Manager and Boundary Resolver.

Coordinates transaction boundaries (ATOMIC, COMPENSABLE, CHECKPOINT_SEQUENCE, INDEPENDENT,
IRREVERSIBLE_WITH_APPROVAL), operational recovery requirements, and commit/rollback state transitions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from threading import RLock

from cmm.agent_runtime.checkpoint_contracts import (
    CheckpointCreationRequest,
    CompensationAction,
    TransactionBoundary,
    TransactionExecutionState,
    TransactionOperation,
)
from cmm.agent_runtime.checkpoint_manager import CheckpointManager
from cmm.agent_runtime.enums import (
    OperationRecoveryKind,
    TransactionBoundaryKind,
    TransactionStatus,
)
from cmm.agent_runtime.errors import (
    IrreversibleOperationError,
    TransactionBoundaryError,
    TransactionCommitError,
    TransactionStateError,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TransactionBoundaryResolver:
    """Resolves and validates transaction boundary configurations against operations."""

    @staticmethod
    def resolve_boundary(
        agent_run_id: str,
        kind: TransactionBoundaryKind | str,
        name: str,
        has_approval: bool = False,
        operations: tuple[TransactionOperation, ...] = (),
    ) -> TransactionBoundary:
        """Resolve a TransactionBoundary contract and enforce capability/approval rules."""
        kind_str = (
            kind.value if isinstance(kind, TransactionBoundaryKind) else str(kind)
        )

        boundary_id = f"txb-{uuid.uuid4().hex[:12]}"

        # Validate operations against boundary kind
        for op in operations:
            rk_str = (
                op.recovery_kind.value
                if isinstance(op.recovery_kind, OperationRecoveryKind)
                else str(op.recovery_kind)
            )

            if kind_str == TransactionBoundaryKind.ATOMIC.value:
                if rk_str == OperationRecoveryKind.IRREVERSIBLE.value:
                    raise TransactionBoundaryError(
                        f"Operation '{op.operation_name}' is IRREVERSIBLE, which is forbidden in ATOMIC transaction boundary."
                    )
            elif kind_str == TransactionBoundaryKind.COMPENSABLE.value:
                if (
                    rk_str == OperationRecoveryKind.IRREVERSIBLE.value
                    and not op.compensation_action
                ):
                    raise TransactionBoundaryError(
                        f"Operation '{op.operation_name}' in COMPENSABLE transaction lacks a CompensationAction."
                    )
            elif (
                kind_str == TransactionBoundaryKind.IRREVERSIBLE_WITH_APPROVAL.value
                and rk_str == OperationRecoveryKind.IRREVERSIBLE.value
                and not has_approval
            ):
                raise IrreversibleOperationError(
                    f"Irreversible operation '{op.operation_name}' requires active approval before execution."
                )

        return TransactionBoundary(
            id=boundary_id,
            agent_run_id=agent_run_id,
            kind=kind_str,
            name=name,
            status=TransactionStatus.PENDING,
            created_at=_now_iso(),
        )


class TransactionManager:
    """Coordinates lifecycle, boundaries, checkpoint associations, commits, and rollbacks for transactions."""

    def __init__(self, checkpoint_manager: CheckpointManager) -> None:
        self._checkpoint_manager = checkpoint_manager
        self._boundaries: dict[str, TransactionBoundary] = {}
        self._states: dict[str, TransactionExecutionState] = {}
        self._rlock = RLock()

    @property
    def checkpoint_manager(self) -> CheckpointManager:
        return self._checkpoint_manager

    def start_transaction(
        self,
        agent_run_id: str,
        goal_id: str,
        workflow_id: str,
        iteration_id: str,
        kind: TransactionBoundaryKind | str,
        name: str,
        resource_keys: tuple[str, ...] = (),
        has_approval: bool = False,
        requires_checkpoint: bool = True,
        now: str | None = None,
    ) -> tuple[TransactionBoundary, str | None]:
        """Start a transaction, resolving its boundary and creating an associated checkpoint if required."""
        timestamp = now or _now_iso()
        with self._rlock:
            boundary = TransactionBoundaryResolver.resolve_boundary(
                agent_run_id=agent_run_id,
                kind=kind,
                name=name,
                has_approval=has_approval,
            )

            checkpoint_id: str | None = None
            if requires_checkpoint or boundary.kind in (
                TransactionBoundaryKind.ATOMIC.value,
                TransactionBoundaryKind.CHECKPOINT_SEQUENCE.value,
            ):
                req = CheckpointCreationRequest(
                    agent_run_id=agent_run_id,
                    goal_id=goal_id,
                    workflow_id=workflow_id,
                    iteration_id=iteration_id,
                    name=f"tx-checkpoint-{boundary.id}",
                    transaction_boundary_id=boundary.id,
                    resource_keys=resource_keys,
                )
                cp_res = self._checkpoint_manager.create_checkpoint(req, now=timestamp)
                checkpoint_id = cp_res.checkpoint_id

            active_boundary = TransactionBoundary(
                id=boundary.id,
                agent_run_id=boundary.agent_run_id,
                kind=boundary.kind,
                name=boundary.name,
                checkpoint_id=checkpoint_id,
                status=TransactionStatus.ACTIVE,
                created_at=timestamp,
            )

            state = TransactionExecutionState(
                transaction_boundary_id=boundary.id,
                status=TransactionStatus.ACTIVE,
                active_checkpoint_id=checkpoint_id,
                started_at=timestamp,
                updated_at=timestamp,
            )

            self._boundaries[boundary.id] = active_boundary
            self._states[boundary.id] = state

            return active_boundary, checkpoint_id

    def register_operation(
        self,
        transaction_boundary_id: str,
        operation_name: str,
        recovery_kind: OperationRecoveryKind | str,
        compensation_action: CompensationAction | None = None,
        effects: tuple[str, ...] = (),
    ) -> TransactionOperation:
        """Register an operation execution against an active transaction boundary."""
        with self._rlock:
            if transaction_boundary_id not in self._boundaries:
                raise TransactionStateError(
                    f"Transaction boundary '{transaction_boundary_id}' not found."
                )

            bnd = self._boundaries[transaction_boundary_id]
            if bnd.status != TransactionStatus.ACTIVE.value:
                raise TransactionStateError(
                    f"Cannot register operation in transaction '{transaction_boundary_id}' with status '{bnd.status}'."
                )

            op_id = f"txop-{uuid.uuid4().hex[:8]}"
            op = TransactionOperation(
                operation_id=op_id,
                transaction_boundary_id=transaction_boundary_id,
                operation_name=operation_name,
                recovery_kind=recovery_kind,
                compensation_action=compensation_action,
                executed_at=_now_iso(),
                is_executed=True,
                effects=effects,
            )

            st = self._states[transaction_boundary_id]
            new_ops = st.executed_operations + (op,)
            self._states[transaction_boundary_id] = TransactionExecutionState(
                transaction_boundary_id=st.transaction_boundary_id,
                status=st.status,
                executed_operations=new_ops,
                active_checkpoint_id=st.active_checkpoint_id,
                started_at=st.started_at,
                updated_at=_now_iso(),
            )
            return op

    def commit(
        self, transaction_boundary_id: str, now: str | None = None
    ) -> TransactionBoundary:
        """Commit an active transaction boundary after successful execution and post-validation."""
        timestamp = now or _now_iso()
        with self._rlock:
            if transaction_boundary_id not in self._boundaries:
                raise TransactionCommitError(
                    f"Transaction boundary '{transaction_boundary_id}' not found."
                )

            bnd = self._boundaries[transaction_boundary_id]
            if bnd.status not in (
                TransactionStatus.ACTIVE.value,
                TransactionStatus.COMMITTING.value,
            ):
                raise TransactionStateError(
                    f"Cannot commit transaction '{transaction_boundary_id}' in state '{bnd.status}'."
                )

            committed_bnd = TransactionBoundary(
                id=bnd.id,
                agent_run_id=bnd.agent_run_id,
                kind=bnd.kind,
                name=bnd.name,
                checkpoint_id=bnd.checkpoint_id,
                status=TransactionStatus.COMMITTED,
                created_at=bnd.created_at,
                committed_at=timestamp,
            )

            st = self._states[transaction_boundary_id]
            self._states[transaction_boundary_id] = TransactionExecutionState(
                transaction_boundary_id=st.transaction_boundary_id,
                status=TransactionStatus.COMMITTED,
                executed_operations=st.executed_operations,
                active_checkpoint_id=st.active_checkpoint_id,
                started_at=st.started_at,
                updated_at=timestamp,
            )

            self._boundaries[transaction_boundary_id] = committed_bnd
            return committed_bnd

    def mark_rollback_started(
        self, transaction_boundary_id: str
    ) -> TransactionBoundary:
        """Transition transaction status to ROLLING_BACK or COMPENSATING."""
        with self._rlock:
            bnd = self._boundaries[transaction_boundary_id]
            st = self._states[transaction_boundary_id]

            target_status = (
                TransactionStatus.COMPENSATING
                if bnd.kind == TransactionBoundaryKind.COMPENSABLE.value
                else TransactionStatus.ROLLING_BACK
            )

            updated_bnd = TransactionBoundary(
                id=bnd.id,
                agent_run_id=bnd.agent_run_id,
                kind=bnd.kind,
                name=bnd.name,
                checkpoint_id=bnd.checkpoint_id,
                status=target_status,
                created_at=bnd.created_at,
            )

            self._states[transaction_boundary_id] = TransactionExecutionState(
                transaction_boundary_id=st.transaction_boundary_id,
                status=target_status,
                executed_operations=st.executed_operations,
                active_checkpoint_id=st.active_checkpoint_id,
                started_at=st.started_at,
                updated_at=_now_iso(),
            )

            self._boundaries[transaction_boundary_id] = updated_bnd
            return updated_bnd

    def mark_rolled_back(
        self,
        transaction_boundary_id: str,
        partially: bool = False,
        now: str | None = None,
    ) -> TransactionBoundary:
        """Mark transaction as ROLLED_BACK, COMPENSATED, or PARTIALLY_RESTORED."""
        timestamp = now or _now_iso()
        with self._rlock:
            bnd = self._boundaries[transaction_boundary_id]
            st = self._states[transaction_boundary_id]

            if partially:
                final_status = TransactionStatus.PARTIALLY_RESTORED
            elif bnd.kind == TransactionBoundaryKind.COMPENSABLE.value:
                final_status = TransactionStatus.COMPENSATED
            else:
                final_status = TransactionStatus.ROLLED_BACK

            updated_bnd = TransactionBoundary(
                id=bnd.id,
                agent_run_id=bnd.agent_run_id,
                kind=bnd.kind,
                name=bnd.name,
                checkpoint_id=bnd.checkpoint_id,
                status=final_status,
                created_at=bnd.created_at,
                rolled_back_at=timestamp,
            )

            self._states[transaction_boundary_id] = TransactionExecutionState(
                transaction_boundary_id=st.transaction_boundary_id,
                status=final_status,
                executed_operations=st.executed_operations,
                active_checkpoint_id=st.active_checkpoint_id,
                started_at=st.started_at,
                updated_at=timestamp,
            )

            self._boundaries[transaction_boundary_id] = updated_bnd
            return updated_bnd

    def get_boundary(self, transaction_boundary_id: str) -> TransactionBoundary:
        with self._rlock:
            if transaction_boundary_id not in self._boundaries:
                raise TransactionStateError(
                    f"Transaction boundary '{transaction_boundary_id}' not found."
                )
            return self._boundaries[transaction_boundary_id]

    def get_state(self, transaction_boundary_id: str) -> TransactionExecutionState:
        with self._rlock:
            if transaction_boundary_id not in self._states:
                raise TransactionStateError(
                    f"Transaction state '{transaction_boundary_id}' not found."
                )
            return self._states[transaction_boundary_id]
