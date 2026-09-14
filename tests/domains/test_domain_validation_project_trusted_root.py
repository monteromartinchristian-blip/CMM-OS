"""Phase 10.43 V5 — trusted Project root and fail-closed derivation (BLOCKER-V4-02).

The validation root for ``project.modify_code`` is host authority: the
host-registered operation implementation declares its execution root via
``host_project_root``. Caller metadata ``validation_project_root`` is at
most a transport hint that must match host truth. Missing/undeclared/
invalid roots, snapshot failures, and change-derivation failures all fail
closed before acceptance — never a silent ``small`` downgrade.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
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


def _trusted_stack(
    tmp_path: Path,
    *,
    hint: str | None = "match",
    declare_host_root: bool = True,
    host_root_override: str | None = None,
):
    """Orchestrator stack where the host implementation declares its root.

    ``hint="match"`` sends metadata root equal to the host tree (legacy
    compatible). ``hint="omit"`` sends no metadata root. Any other string
    is sent verbatim as the caller hint (e.g. a decoy tree).
    """
    ops = {op.operation_id: op for op in build_project_operation_definitions()}
    definition = ops["project.modify_code"]

    project_dir = tmp_path / "hostproj"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "main.py").write_text("x = 1\n", encoding="utf-8")

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
            return {"success": True, "output": {"status": "ok"}}

    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)
    registry.register(definition, Implementation())

    perm_registry = DomainPermissionRegistry()
    perm_registry.register(build_project_permission_policy())
    resolver = DomainPermissionResolver(perm_registry)
    service = ApprovalService(InMemoryApprovalRepository())

    metadata: dict = {"actor_id": "actor-1"}
    if hint == "match":
        metadata["validation_project_root"] = str(project_dir)
    elif hint == "omit":
        pass
    elif hint is not None:
        metadata["validation_project_root"] = hint

    request = DomainOperationRequest(
        request_id="req:trust:1",
        operation_id="project.modify_code",
        operation_version=definition.version,
        inputs={},
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="task-1",
        session_id="sess-1",
        primary_domain_id=definition.domain_id,
        idempotency_key="idem-trust-1",
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

    class Boundary:
        id = "transaction:1"

    class TransactionManagerSpy:
        def start_transaction(self, **kwargs):
            return Boundary(), "checkpoint:1"

        def register_operation(self, **kwargs) -> None:
            return None

        def commit(self, transaction_id: str) -> None:
            return None

        def mark_rollback_started(self, transaction_id: str) -> None:
            return None

        def mark_rolled_back(self, transaction_id: str) -> None:
            return None

        def mark_failed(self, transaction_id: str) -> None:
            return None

    class RollbackSpy:
        def __init__(self) -> None:
            self.calls = 0

        def rollback(self, transaction_id, checkpoint_id=None) -> bool:
            self.calls += 1
            return True

    rollback_spy = RollbackSpy()
    adapter = AgentExecutionAdapter(
        registry=common,
        execution_delegate=DomainOperationExecutionDelegate(registry),
        validation_adapter=AgentValidationAdapter(),
    )
    _now = datetime.now(timezone.utc)
    gate = DomainPermissionGate(resolver, service, clock=lambda: _now)
    orchestrator = DefaultDomainOperationOrchestrator(
        registry,
        adapter,
        approval_service=service,
        permission_gate=gate,
        transaction_manager=TransactionManagerSpy(),
        rollback_executor=rollback_spy,
        operation_validation_provider=(
            resolve_domain_operation_validation_requirements
        ),
    )
    approved_request = dataclasses.replace(
        request,
        approval_request_id=op_exec_approval_id,
        metadata={**metadata, "approval_request_ids": approval_request_ids},
    )
    return orchestrator, approved_request, calls, project_dir, rollback_spy


class TestTrustedProjectRoot:
    def test_caller_decoy_root_is_rejected(self, tmp_path) -> None:
        decoy = tmp_path / "decoy"
        decoy.mkdir(parents=True, exist_ok=True)
        (decoy / "main.py").write_text("x = 1\n", encoding="utf-8")
        orchestrator, request, calls, _, _ = _trusted_stack(
            tmp_path / "case",
            hint=str(decoy),
        )
        with pytest.raises(DomainValidationIntegrationError):
            orchestrator.execute(request)
        assert calls == []

    def test_omitted_hint_uses_host_root(self, tmp_path) -> None:
        orchestrator, request, _, _, _ = _trusted_stack(tmp_path, hint="omit")
        result = orchestrator.execute(request)
        assert result.status is DomainOperationStatus.COMPLETED

    def test_matching_hint_is_accepted(self, tmp_path) -> None:
        orchestrator, request, _, _, _ = _trusted_stack(tmp_path, hint="match")
        result = orchestrator.execute(request)
        assert result.status is DomainOperationStatus.COMPLETED

    def test_missing_implementation_root_fails_closed(self, tmp_path) -> None:
        orchestrator, request, calls, _, _ = _trusted_stack(
            tmp_path, hint="match", declare_host_root=False
        )
        with pytest.raises(DomainValidationIntegrationError):
            orchestrator.execute(request)
        assert calls == []

    def test_nonexistent_implementation_root_fails_closed(self, tmp_path) -> None:
        orchestrator, request, calls, _, _ = _trusted_stack(
            tmp_path,
            hint="omit",
            host_root_override=str(tmp_path / "does-not-exist"),
        )
        with pytest.raises(DomainValidationIntegrationError):
            orchestrator.execute(request)
        assert calls == []

    def test_before_snapshot_failure_fails_closed(self, tmp_path, monkeypatch) -> None:
        import cmm.domains.operation_execution as execution_mod

        real_scan = execution_mod.scan_project_snapshot

        def _boom(root, *, source):
            if source == "before":
                raise RuntimeError("snapshot capture unavailable")
            return real_scan(root, source=source)

        monkeypatch.setattr(execution_mod, "scan_project_snapshot", _boom)
        orchestrator, request, calls, _, _ = _trusted_stack(tmp_path, hint="omit")
        with pytest.raises(DomainValidationIntegrationError):
            orchestrator.execute(request)
        assert calls == []

    def test_changeset_builder_failure_fails_closed(
        self, tmp_path, monkeypatch
    ) -> None:
        import cmm.domains.validation_integration as integration_mod

        class _BoomBuilder:
            def build_from_snapshots(self, **kwargs):
                raise RuntimeError("changeset unavailable")

        monkeypatch.setattr(integration_mod, "ChangeSetBuilder", lambda: _BoomBuilder())
        orchestrator, request, calls, _, _ = _trusted_stack(tmp_path, hint="omit")
        result = orchestrator.execute(request)
        assert calls != []
        assert result.status is not DomainOperationStatus.COMPLETED

    def test_impact_analyzer_failure_fails_closed(self, tmp_path, monkeypatch) -> None:
        import cmm.domains.validation_integration as integration_mod

        class _BoomAnalyzer:
            def analyze(self, change_set):
                raise RuntimeError("analyzer unavailable")

        monkeypatch.setattr(
            integration_mod, "ChangeImpactAnalyzer", lambda: _BoomAnalyzer()
        )
        orchestrator, request, calls, _, _ = _trusted_stack(tmp_path, hint="omit")
        result = orchestrator.execute(request)
        assert calls != []
        assert result.status is not DomainOperationStatus.COMPLETED
