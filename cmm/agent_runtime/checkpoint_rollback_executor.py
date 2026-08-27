"""Adapter connecting CheckpointRestorationManager to Domain Operation rollback protocol."""

from __future__ import annotations

from cmm.agent_runtime.checkpoint_contracts import CheckpointRestorationRequest
from cmm.agent_runtime.checkpoint_restoration import CheckpointRestorationManager
from cmm.agent_runtime.errors import AgentRuntimeError
from cmm.agent_runtime.transaction_manager import TransactionManager


class CheckpointRestorationRollbackExecutor:
    """Adapts CheckpointRestorationManager to execute rollback for transaction boundaries."""

    def __init__(
        self,
        *,
        transaction_manager: TransactionManager,
        restoration_manager: CheckpointRestorationManager,
    ) -> None:
        self._transaction_manager = transaction_manager
        self._restoration_manager = restoration_manager

    def rollback(self, transaction_id: str, checkpoint_id: str | None) -> bool:
        if checkpoint_id is None:
            return False

        try:
            boundary = self._transaction_manager.get_boundary(transaction_id)
            result = self._restoration_manager.restore_checkpoint(
                CheckpointRestorationRequest(
                    checkpoint_id=checkpoint_id,
                    agent_run_id=boundary.agent_run_id,
                    requested_by="domain-operation-orchestrator",
                    reason=f"rollback:{transaction_id}",
                    metadata={"transaction_id": transaction_id},
                )
            )
            return bool(result.success)
        except AgentRuntimeError:
            return False
