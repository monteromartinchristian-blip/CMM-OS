"""Phase 10.43 V6 — Project preflight transaction lifecycle (MAJOR-V5-01).

RED/GREEN regression: pre-mutation fail-closed preflight (decoy root,
missing host root, missing validation provider, before-snapshot failure)
must leave zero ACTIVE transaction/checkpoint state. Uses the real
TransactionManager / CheckpointManager and the host-registered
project.modify_code implementation (same connected stack as AT-DP-043).
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.checkpoint_manager import CheckpointManager
from cmm.agent_runtime.checkpoint_repository import InMemoryCheckpointRepository
from cmm.agent_runtime.checkpoint_restoration import CheckpointRestorationManager
from cmm.agent_runtime.checkpoint_rollback_executor import (
    CheckpointRestorationRollbackExecutor,
)
from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.agent_runtime.enums import TransactionStatus
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.agent_runtime.transaction_manager import TransactionManager
from cmm.agent_runtime.validation_execution_adapter import AgentValidationAdapter
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.enums import DomainOperationStatus
from cmm.domains.operation_contracts import DomainOperationRequest
from cmm.domains.operation_execution import (
    DefaultDomainOperationOrchestrator,
    DomainOperationExecutionDelegate,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_adapters import evaluate_domain_operation
from cmm.domains.permission_gate import DomainPermissionGate
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.project.operations import build_project_operation_definitions
from cmm.domains.project.permissions import build_project_permission_policy
from cmm.domains.validation_integration import (
    DomainValidationIntegrationError,
    resolve_domain_operation_validation_requirements,
)


class _TreeResourceVersionProvider:
    """Whole-tree resource provider for canonical checkpoint restoration."""

    def __init__(self, repo_path) -> None:
        import hashlib
        from pathlib import Path as _Path

        self._hashlib = hashlib
        self.repo_path = _Path(repo_path)
        self._snapshots: dict[str, dict] = {}

    def _current_state(self) -> dict:
        files_state = {}
        for path in self.repo_path.rglob("*"):
            if path.is_file() and ".git" not in path.parts:
                files_state[path] = path.read_bytes()
        return files_state

    def capture_version(self, resource_key: str) -> str:
        files_state = self._current_state()
        digest_content = "".join(
            f"{path.relative_to(self.repo_path)}:"
            f"{self._hashlib.sha256(data).hexdigest()};"
            for path, data in sorted(files_state.items(), key=lambda item: str(item[0]))
        )
        digest = self._hashlib.sha256(digest_content.encode("utf-8")).hexdigest()
        self._snapshots[digest] = files_state
        return digest

    def verify_version(self, resource_key: str, expected_version: str) -> bool:
        return self.capture_version(resource_key) == expected_version

    def restore_version(self, resource_key: str, target_version: str) -> bool:
        if target_version not in self._snapshots:
            return False
        snapshot = self._snapshots[target_version]
        current_files = {
            path
            for path in self.repo_path.rglob("*")
            if path.is_file() and ".git" not in path.parts
        }
        for path in current_files - set(snapshot.keys()):
            path.unlink()
        for path, data in snapshot.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return True


def _active_transaction_ids(transaction_manager: TransactionManager) -> list[str]:
    """Canonical ACTIVE transaction enumeration via manager state."""
    active: list[str] = []
    boundaries = getattr(transaction_manager, "_boundaries", {})
    for boundary_id, boundary in list(boundaries.items()):
        status = getattr(boundary, "status", None)
        if status == TransactionStatus.ACTIVE.value:
            active.append(boundary_id)
            continue
        state = None
        try:
            state = transaction_manager.get_state(boundary_id)
        except Exception:  # noqa: BLE001 -- missing state means not active
            state = None
        if state is not None and getattr(state, "status", None) == (
            TransactionStatus.ACTIVE.value
        ):
            active.append(boundary_id)
    return active


def _project_preflight_stack(
    tmp_path: Path,
    *,
    mutation=None,
    suffix: str = "v6",
    hint: str | None = "omit",
    declare_host_root: bool = True,
    host_root_override: str | None = None,
    operation_validation_provider=None,
    use_canonical_provider: bool = True,
):
    """Connected Project stack with real Transaction/Checkpoint managers."""
    ops = {op.operation_id: op for op in build_project_operation_definitions()}
    definition = ops["project.modify_code"]

    project_dir = tmp_path / f"preflight-{suffix}"
    pkg_dir = project_dir / "src" / "pkg"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "src" / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "module.py").write_text(
        "def add(a, b):\n    return a + b\n", encoding="utf-8"
    )
    tests_dir = project_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "__init__.py").write_text("", encoding="utf-8")
    (tests_dir / "test_module.py").write_text(
        "from src.pkg.module import add\n"
        "\n"
        "\n"
        "def test_add():\n"
        "    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )

    host_root = (
        host_root_override if host_root_override is not None else str(project_dir)
    )
    calls: list = []

    class Implementation:
        def __init__(self) -> None:
            self.definition = definition
            if declare_host_root:
                self.host_project_root = host_root

        def execute(self, request) -> dict:
            calls.append(request)
            if mutation is not None:
                mutation(project_dir)
            return {"success": True, "output": {"status": "ok"}}

    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)
    registry.register(definition, Implementation())

    perm_registry = DomainPermissionRegistry()
    perm_registry.register(build_project_permission_policy())
    resolver = DomainPermissionResolver(perm_registry)
    service = ApprovalService(InMemoryApprovalRepository())

    metadata: dict = {"actor_id": "actor-1"}
    if hint is not None and hint != "omit":
        metadata["validation_project_root"] = hint

    request = DomainOperationRequest(
        request_id=f"req:preflight:{suffix}",
        operation_id="project.modify_code",
        operation_version=definition.version,
        inputs={},
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="task-1",
        session_id="sess-1",
        primary_domain_id=definition.domain_id,
        idempotency_key=f"idem-preflight-{suffix}",
        granted_permissions=definition.required_permissions,
        available_resources=definition.required_resources,
        capabilities=("execute", "transaction", "rollback", "validation"),
        metadata=metadata,
    )
    decision = evaluate_domain_operation(
        definition,
        resolver,
        request_id=request.request_id,
        actor_id="actor-1",
        session_id="sess-1",
    )
    approval_request_ids: dict = {}
    op_exec_approval_id = None
    for req in decision.approval_requirements:
        bridged = to_approval_requirement(req, agent_run_id="run-1")
        app_req = service.create_request_from_requirement(
            bridged,
            requested_by="agent:dev",
            metadata_override={
                "domain_request_fingerprint": request.calculate_fingerprint(),
            },
        )
        service.approve(app_req.id, actor_id="lead")
        approval_request_ids[req.requirement_id] = app_req.id
        if req.action is PermissionCapability.OPERATION_EXECUTE:
            op_exec_approval_id = app_req.id

    resource_provider = _TreeResourceVersionProvider(project_dir)
    checkpoint_repo = InMemoryCheckpointRepository()
    checkpoint_manager = CheckpointManager(
        repository=checkpoint_repo, resource_provider=resource_provider
    )
    transaction_manager = TransactionManager(checkpoint_manager)
    restoration_manager = CheckpointRestorationManager(
        repository=checkpoint_repo, resource_provider=resource_provider
    )
    rollback_executor = CheckpointRestorationRollbackExecutor(
        transaction_manager=transaction_manager,
        restoration_manager=restoration_manager,
    )

    validation_adapter = AgentValidationAdapter()
    adapter = AgentExecutionAdapter(
        registry=common,
        execution_delegate=DomainOperationExecutionDelegate(registry),
        validation_adapter=validation_adapter,
    )
    _now = datetime.now(timezone.utc)
    gate = DomainPermissionGate(resolver, service, clock=lambda: _now)
    if use_canonical_provider and operation_validation_provider is None:
        provider = resolve_domain_operation_validation_requirements
    else:
        provider = operation_validation_provider
    orchestrator = DefaultDomainOperationOrchestrator(
        registry,
        adapter,
        approval_service=service,
        permission_gate=gate,
        transaction_manager=transaction_manager,
        rollback_executor=rollback_executor,
        operation_validation_provider=provider,
    )
    approved_request = dataclasses.replace(
        request,
        approval_request_id=op_exec_approval_id,
        metadata={**metadata, "approval_request_ids": approval_request_ids},
    )
    return (
        orchestrator,
        approved_request,
        calls,
        project_dir,
        transaction_manager,
        checkpoint_repo,
        adapter,
    )


class TestProjectPreflightTransactionHygiene:
    def test_project_decoy_root_preflight_does_not_leave_active_transaction(
        self, tmp_path
    ) -> None:
        decoy = tmp_path / "decoy"
        decoy.mkdir(parents=True, exist_ok=True)
        (decoy / "main.py").write_text("x = 1\n", encoding="utf-8")
        (
            orchestrator,
            request,
            calls,
            _,
            tx_mgr,
            checkpoint_repo,
            _adapter,
        ) = _project_preflight_stack(tmp_path, suffix="decoy", hint=str(decoy))
        with pytest.raises(DomainValidationIntegrationError):
            orchestrator.execute(request)
        assert calls == []
        assert _active_transaction_ids(tx_mgr) == []
        assert len(getattr(tx_mgr, "_boundaries", {})) == 0
        assert checkpoint_repo.find_active() == ()
        assert len(getattr(checkpoint_repo, "_checkpoints", {})) == 0

    def test_project_missing_host_root_preflight_does_not_leave_active_transaction(
        self, tmp_path
    ) -> None:
        (
            orchestrator,
            request,
            calls,
            _,
            tx_mgr,
            checkpoint_repo,
            _adapter,
        ) = _project_preflight_stack(
            tmp_path, suffix="nohost", hint="omit", declare_host_root=False
        )
        with pytest.raises(DomainValidationIntegrationError):
            orchestrator.execute(request)
        assert calls == []
        assert _active_transaction_ids(tx_mgr) == []
        assert len(getattr(tx_mgr, "_boundaries", {})) == 0
        assert checkpoint_repo.find_active() == ()
        assert len(getattr(checkpoint_repo, "_checkpoints", {})) == 0

    def test_project_missing_provider_preflight_does_not_leave_active_transaction(
        self, tmp_path
    ) -> None:
        (
            orchestrator,
            request,
            calls,
            _,
            tx_mgr,
            checkpoint_repo,
            _adapter,
        ) = _project_preflight_stack(
            tmp_path,
            suffix="noprovider",
            hint="omit",
            operation_validation_provider=None,
            use_canonical_provider=False,
        )
        # Missing provider configuration: orchestrator must fail closed
        # without creating transaction state.
        assert getattr(orchestrator, "_operation_validation_provider", None) is None
        with pytest.raises(DomainValidationIntegrationError):
            orchestrator.execute(request)
        assert calls == []
        assert _active_transaction_ids(tx_mgr) == []
        assert len(getattr(tx_mgr, "_boundaries", {})) == 0
        assert checkpoint_repo.find_active() == ()
        assert len(getattr(checkpoint_repo, "_checkpoints", {})) == 0

    def test_project_before_snapshot_failure_does_not_leave_active_transaction(
        self, tmp_path, monkeypatch
    ) -> None:
        import cmm.domains.operation_execution as execution_mod

        real_scan = execution_mod.scan_project_snapshot

        def _boom(root, *, source):
            if source == "before":
                raise RuntimeError("snapshot capture unavailable")
            return real_scan(root, source=source)

        monkeypatch.setattr(execution_mod, "scan_project_snapshot", _boom)
        (
            orchestrator,
            request,
            calls,
            _,
            tx_mgr,
            checkpoint_repo,
            _adapter,
        ) = _project_preflight_stack(tmp_path, suffix="snapshot", hint="omit")
        with pytest.raises(DomainValidationIntegrationError):
            orchestrator.execute(request)
        assert calls == []
        assert _active_transaction_ids(tx_mgr) == []
        assert len(getattr(tx_mgr, "_boundaries", {})) == 0
        assert checkpoint_repo.find_active() == ()
        assert len(getattr(checkpoint_repo, "_checkpoints", {})) == 0


class TestValidProjectTransactionLifecycle:
    def test_valid_project_mutation_commits_transaction(self, tmp_path) -> None:
        (
            orchestrator,
            request,
            calls,
            _project_dir,
            tx_mgr,
            _checkpoint_repo,
            _adapter,
        ) = _project_preflight_stack(tmp_path, suffix="valid", hint="omit")
        result = orchestrator.execute(request)
        assert result.status is DomainOperationStatus.COMPLETED
        assert calls != []
        assert result.transaction_id is not None
        boundary = tx_mgr.get_boundary(result.transaction_id)
        assert boundary.status == TransactionStatus.COMMITTED.value
        state = tx_mgr.get_state(result.transaction_id)
        assert state.status == TransactionStatus.COMMITTED.value
        assert _active_transaction_ids(tx_mgr) == []

    def test_post_validation_rejection_rolls_back_and_restores(self, tmp_path) -> None:
        def break_mutation(project_dir) -> None:
            (project_dir / "src" / "pkg" / "module.py").write_text(
                "def add(a, b):\n    return a - b\n", encoding="utf-8"
            )

        (
            orchestrator,
            request,
            calls,
            project_dir,
            tx_mgr,
            _checkpoint_repo,
            _adapter,
        ) = _project_preflight_stack(
            tmp_path, mutation=break_mutation, suffix="rollback", hint="omit"
        )
        original = (project_dir / "src" / "pkg" / "module.py").read_text(
            encoding="utf-8"
        )
        result = orchestrator.execute(request)
        assert calls != []
        assert result.status is DomainOperationStatus.ROLLED_BACK
        assert (project_dir / "src" / "pkg" / "module.py").read_text(
            encoding="utf-8"
        ) == original
        assert result.transaction_id is not None
        state = tx_mgr.get_state(result.transaction_id)
        assert state.status in (
            TransactionStatus.ROLLED_BACK.value,
            TransactionStatus.COMPENSATED.value,
        )
        assert _active_transaction_ids(tx_mgr) == []
