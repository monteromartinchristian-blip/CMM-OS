from __future__ import annotations

import hashlib
from pathlib import Path

from cmm.agent_runtime.checkpoint_manager import CheckpointManager
from cmm.agent_runtime.checkpoint_repository import InMemoryCheckpointRepository
from cmm.agent_runtime.checkpoint_restoration import CheckpointRestorationManager
from cmm.agent_runtime.checkpoint_rollback_executor import (
    CheckpointRestorationRollbackExecutor,
)
from cmm.agent_runtime.transaction_manager import TransactionManager


class TempFileResourceVersionProvider:
    """Resource version provider that captures file content snapshots and restores them."""

    def __init__(self, file_path: Path) -> None:
        self._file_path = file_path
        self._snapshots: dict[str, bytes] = {}

    def capture_version(self, resource_key: str) -> str:
        data = self._file_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        self._snapshots[digest] = data
        return digest

    def verify_version(self, resource_key: str, expected_version: str) -> bool:
        data = self._file_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        return digest == expected_version

    def restore_version(self, resource_key: str, target_version: str) -> bool:
        if target_version not in self._snapshots:
            return False
        self._file_path.write_bytes(self._snapshots[target_version])
        return True


def test_checkpoint_rollback_executor_restores_file_bytes(tmp_path: Path) -> None:
    test_file = tmp_path / "code.py"
    initial_bytes = b"# initial code\nval = 1\n"
    test_file.write_bytes(initial_bytes)

    res_provider = TempFileResourceVersionProvider(test_file)
    repo = InMemoryCheckpointRepository()
    cp_manager = CheckpointManager(
        repository=repo,
        resource_provider=res_provider,
    )
    tx_manager = TransactionManager(cp_manager)
    rest_manager = CheckpointRestorationManager(
        repository=repo,
        resource_provider=res_provider,
    )
    rollback_executor = CheckpointRestorationRollbackExecutor(
        transaction_manager=tx_manager,
        restoration_manager=rest_manager,
    )

    boundary, checkpoint_id = tx_manager.start_transaction(
        agent_run_id="run:test:1",
        goal_id="goal:test",
        workflow_id="workflow:test",
        iteration_id="task:test",
        kind="compensable",
        name="domain-operation:test",
        resource_keys=("res:test_file",),
        requires_checkpoint=True,
    )
    assert checkpoint_id is not None

    # Mutate the file
    mutated_bytes = b"# mutated code\nval = 2\n"
    test_file.write_bytes(mutated_bytes)
    assert test_file.read_bytes() == mutated_bytes

    # Execute rollback through CheckpointRestorationRollbackExecutor
    tx_manager.mark_rollback_started(boundary.id)
    success = rollback_executor.rollback(boundary.id, checkpoint_id)
    assert success is True
    tx_manager.mark_rolled_back(boundary.id)

    # Verify file was restored purely through restoration manager / rollback executor
    assert test_file.read_bytes() == initial_bytes


def test_checkpoint_rollback_executor_returns_false_for_none_checkpoint(
    tmp_path: Path,
) -> None:
    repo = InMemoryCheckpointRepository()
    cp_manager = CheckpointManager(repository=repo)
    tx_manager = TransactionManager(cp_manager)
    rest_manager = CheckpointRestorationManager(repository=repo)
    rollback_executor = CheckpointRestorationRollbackExecutor(
        transaction_manager=tx_manager,
        restoration_manager=rest_manager,
    )
    boundary, _ = tx_manager.start_transaction(
        agent_run_id="run:test:2",
        goal_id="goal:test",
        workflow_id="workflow:test",
        iteration_id="task:test",
        kind="compensable",
        name="domain-operation:test",
        requires_checkpoint=False,
    )
    assert rollback_executor.rollback(boundary.id, None) is False
