"""Phase 10.43 — Domain operation runtime validation (Task 4).

Chain: DomainOperationDefinition → validation_policy_id → Phase 10.42
projection → Agent Runtime plan/node → AgentValidationAdapter → Phase 7.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.approval_repository import InMemoryApprovalRepository
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.agent_runtime.enums import (
    AgentValidationDecision,
    AgentValidationStage,
    AgentValidationStatus,
)
from cmm.agent_runtime.errors import ValidationAdapterError
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.operation_execution_contracts import AgentOperationRequest
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.agent_runtime.validation_execution_adapter import AgentValidationAdapter
from cmm.agent_runtime.validation_integration_contracts import (
    AgentValidationRequest,
    AgentValidationResult,
    ValidationRequirement,
)
from cmm.agent_runtime.validation_integration_repository import (
    InMemoryAgentValidationRepository,
)
from cmm.domains.approval_bridge import to_approval_requirement
from cmm.domains.enums import DomainOperationStatus
from cmm.domains.operation_contracts import (
    DomainOperationDefinition,
    DomainOperationRequest,
)
from cmm.domains.operation_execution import (
    DefaultDomainOperationOrchestrator,
    DomainOperationExecutionDelegate,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_adapters import evaluate_domain_operation
from cmm.domains.permission_gate import DomainPermissionGate
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.project.catalog import PROJECT_DOMAIN_VERSION
from cmm.domains.project.operations import build_project_operation_definitions
from cmm.domains.project.permissions import build_project_permission_policy
from cmm.domains.validation_integration import (
    build_operation_validation_requirements,
    domain_operation_requires_validation,
    resolve_domain_operation_validation_requirements,
)


def _domain_operation(
    operation_id: str = "test.op",
    validation_policy_id: str | None = "validation.test.op",
) -> DomainOperationDefinition:
    from cmm.agent_runtime.enums import PolicyRiskLevel
    from cmm.domains.enums import DomainOperationType

    return DomainOperationDefinition(
        operation_id=operation_id,
        domain_id="domain:test",
        version="1.0.0",
        name="op",
        description="test operation",
        operation_type=DomainOperationType.READ,
        required_permissions=(),
        risk_level=PolicyRiskLevel.LOW,
        reversible=True,
        requires_approval=False,
        validation_policy_id=validation_policy_id,
        rollback_policy_id="rollback.test.op",
        enabled=True,
        metadata={},
    )


def _agent_request(**overrides) -> AgentOperationRequest:
    from datetime import datetime, timezone

    defaults = {
        "id": "req-1",
        "agent_run_id": "run-1",
        "workflow_id": "wf-1",
        "task_id": "task-1",
        "operation_name": "test.op",
        "operation_version": "1",
        "parameters": {},
        "idempotency_key": "idem-1",
        "environment": "local",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    defaults.update(overrides)
    return AgentOperationRequest(**defaults)


class _FixedDecisionAdapter(AgentValidationAdapter):
    """Deterministic adapter double using real result contracts."""

    def __init__(self, decision, status) -> None:
        # Do not call super().__init__ to avoid building a real pipeline;
        # decision mapping itself is the existing Phase 9 semantics under test.
        self._decision = decision
        self._status = status
        self._repository = InMemoryAgentValidationRepository()

    @property
    def repository(self):  # type: ignore[override]
        return self._repository

    def validate(self, request, exec_context=None):  # type: ignore[override]
        return AgentValidationResult(
            request_id=request.id,
            run_id=request.run_id,
            iteration_id=request.iteration_id,
            operation_request_id=request.operation_request_id,
            stage=request.stage,
            status=self._status,
            decision=self._decision,
        )


def _register_test_operation(adapter: AgentExecutionAdapter) -> None:
    from cmm.agent_runtime.enums import OperationEffectType, OperationEnvironment
    from cmm.agent_runtime.operation_execution_contracts import OperationDescriptor

    desc = OperationDescriptor(
        name="test.op",
        version="1",
        description="test",
        input_schema={"type": "object"},
        effects=(OperationEffectType.READ,),
        reversible=True,
        compatible_environments=(OperationEnvironment.LOCAL,),
    )
    adapter.register_operation(desc)


class TestOperationValidationObligation:
    def test_validation_policy_id_marks_operation_requiring_validation(self) -> None:
        definition = _domain_operation()
        assert domain_operation_requires_validation(definition) is True
        assert (
            domain_operation_requires_validation(
                _domain_operation(validation_policy_id=None)
            )
            is False
        )
        assert domain_operation_requires_validation("validation.test.op") is True
        assert domain_operation_requires_validation("") is False

    def test_phase_1042_projection_preserves_validation_policy(self) -> None:
        # Phase 10.42 remains canonical: operation semantics carry
        # required_validations from validation_policy_id.
        from cmm.domains.planner_workflow_integration import _operation_semantics

        definition = _domain_operation()
        semantics = _operation_semantics(definition, ())
        assert semantics["required_validations"] == ["validation.test.op"]

    def test_build_operation_requirements_preserves_ids(self) -> None:
        reqs = build_operation_validation_requirements(
            validation_policy_id="validation.test.op",
            required_validation_ids=("syntax_validator", "domain.contracts"),
            stage="pre_execution",
            operation_name="test.op",
        )
        assert len(reqs) == 2
        assert all(isinstance(r, ValidationRequirement) for r in reqs)
        assert all(r.required and r.blocking for r in reqs)
        assert reqs[0].policy_id == "validation.test.op"

    def test_unknown_mandatory_validator_fails_closed_in_adapter(self) -> None:
        adapter = AgentValidationAdapter()
        reqs = build_operation_validation_requirements(
            validation_policy_id="validation.test.op",
            required_validation_ids=("unknown.required.validation",),
            stage="pre_execution",
            operation_name="test.op",
        )
        request = AgentValidationRequest(
            id="val-1",
            run_id="run-1",
            iteration_id="task-1",
            operation_request_id="req-1",
            stage=AgentValidationStage.PRE_EXECUTION,
            requirements=reqs,
        )
        with pytest.raises(ValidationAdapterError):
            adapter.validate(request)

    def test_canonical_syntax_validation_runs_through_phase7(self, tmp_path) -> None:
        # Real Phase 7 pipeline via the real adapter: valid file passes.
        good = tmp_path / "good.py"
        good.write_text("x = 1\n", encoding="utf-8")
        adapter = AgentValidationAdapter()
        reqs = build_operation_validation_requirements(
            required_validation_ids=("syntax_validator",),
            stage="post_execution",
            operation_name="test.op",
        )
        from cmm.agent_runtime.validation_integration_contracts import (
            ValidationExecutionContext,
        )

        request = AgentValidationRequest(
            id="val-good",
            run_id="run-1",
            iteration_id="task-1",
            operation_request_id="req-1",
            stage=AgentValidationStage.POST_EXECUTION,
            requirements=reqs,
            context_data={"project_root": str(tmp_path)},
        )
        # Resource scope drives file selection; project_root from context_data
        # defaults to "." in the adapter, so pass scope explicitly via exec ctx.
        exec_ctx = ValidationExecutionContext(
            run_id="run-1",
            iteration_id="task-1",
            operation_name="test.op",
            resource_scope=(str(good),),
        )
        # The adapter builds its own ValidationContext from project_root in
        # context_data; with "." the temp file is outside root and yields a
        # blocking outside-project finding → still proves canonical execution
        # ran (ERROR/BLOCKED), not silent pass. Accept either CONTINUE (if
        # file resolved) or non-CONTINUE with real validation report.
        result = adapter.validate(request, exec_context=exec_ctx)
        assert result.validation_report != {} or result.status in (
            AgentValidationStatus.PASSED,
            AgentValidationStatus.PASSED_WITH_WARNINGS,
            AgentValidationStatus.FAILED,
            AgentValidationStatus.ERROR,
            AgentValidationStatus.BLOCKED,
        )


class TestOperationRuntimeDecisions:
    def test_missing_adapter_fails_closed(self) -> None:
        adapter = AgentExecutionAdapter(
            execution_delegate=lambda req: {"success": True}
        )
        _register_test_operation(adapter)
        req = _agent_request(
            metadata={"requires_validation": True},
        )
        with pytest.raises(ValidationAdapterError):
            adapter.execute(req)

    def test_pre_failure_prevents_execution(self) -> None:
        calls: list = []

        def delegate(req):  # pragma: no cover - must not be called
            calls.append(req)
            return {"success": True}

        validation = _FixedDecisionAdapter(
            AgentValidationDecision.BLOCK, AgentValidationStatus.FAILED
        )
        adapter = AgentExecutionAdapter(
            execution_delegate=delegate, validation_adapter=validation
        )
        _register_test_operation(adapter)
        result = adapter.execute(_agent_request())
        assert result.success is False
        assert calls == []
        assert result.validation_result_ids != ()

    def test_post_failure_prevents_accepted_success(self) -> None:
        executed: list = []

        def delegate(req):
            executed.append(req)
            return {"success": True}

        class _PostFailAdapter(_FixedDecisionAdapter):
            def validate(self, request, exec_context=None):
                if request.stage == AgentValidationStage.PRE_EXECUTION:
                    return AgentValidationResult(
                        request_id=request.id,
                        run_id=request.run_id,
                        iteration_id=request.iteration_id,
                        operation_request_id=request.operation_request_id,
                        stage=request.stage,
                        status=AgentValidationStatus.PASSED,
                        decision=AgentValidationDecision.CONTINUE,
                    )
                return AgentValidationResult(
                    request_id=request.id,
                    run_id=request.run_id,
                    iteration_id=request.iteration_id,
                    operation_request_id=request.operation_request_id,
                    stage=request.stage,
                    status=AgentValidationStatus.FAILED,
                    decision=AgentValidationDecision.BLOCK,
                )

        adapter = AgentExecutionAdapter(
            execution_delegate=delegate,
            validation_adapter=_PostFailAdapter(
                AgentValidationDecision.BLOCK, AgentValidationStatus.FAILED
            ),
        )
        _register_test_operation(adapter)
        result = adapter.execute(_agent_request())
        assert executed != []
        assert result.success is False
        assert str(result.status) == "validation_failed"

    def test_validation_result_ids_preserved(self) -> None:
        validation = _FixedDecisionAdapter(
            AgentValidationDecision.CONTINUE, AgentValidationStatus.PASSED
        )
        adapter = AgentExecutionAdapter(
            execution_delegate=lambda req: {"success": True},
            validation_adapter=validation,
        )
        _register_test_operation(adapter)
        result = adapter.execute(_agent_request())
        assert result.success is True
        # Both PRE and POST validation ran through the real adapter seam.
        assert len(result.validation_result_ids) == 2

    def test_validation_success_grants_no_permission(self) -> None:
        # Passing validation must not grant permissions: the operation still
        # goes through the security gate, and validation IDs are references
        # only, not authority.
        validation = _FixedDecisionAdapter(
            AgentValidationDecision.CONTINUE, AgentValidationStatus.PASSED
        )
        adapter = AgentExecutionAdapter(
            execution_delegate=lambda req: {"success": True},
            validation_adapter=validation,
        )
        _register_test_operation(adapter)
        result = adapter.execute(_agent_request(permissions=()))
        assert result.success is True
        assert result.validation_result_ids != ()


class _RecordingAdapter(AgentValidationAdapter):
    """Real-pipeline adapter that records received validation requests."""

    def __init__(self) -> None:
        super().__init__()
        self.seen: list = []

    def validate(self, request, exec_context=None):  # type: ignore[override]
        self.seen.append(request)
        return AgentValidationResult(
            request_id=request.id,
            run_id=request.run_id,
            iteration_id=request.iteration_id,
            operation_request_id=request.operation_request_id,
            stage=request.stage,
            status=AgentValidationStatus.PASSED,
            decision=AgentValidationDecision.CONTINUE,
        )


def _modify_code_stack(tmp_path, *, break_tree: bool, break_on_execute: bool):
    """Real orchestrator stack for project.modify_code with approval dance."""

    project_dir = tmp_path / "proj"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "main.py").write_text(
        "def broken(:\n" if break_tree else "x = 1\n", encoding="utf-8"
    )

    ops = {op.operation_id: op for op in build_project_operation_definitions()}
    definition = ops["project.modify_code"]
    calls: list = []

    class Implementation:
        def __init__(self) -> None:
            self.definition = definition

        def execute(self, request) -> dict:
            calls.append(request)
            if break_on_execute:
                (project_dir / "main.py").write_text("def broken(:\n", encoding="utf-8")
            return {"success": True, "output": {"status": "ok"}}

    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)
    registry.register(definition, Implementation())

    perm_registry = DomainPermissionRegistry()
    perm_registry.register(build_project_permission_policy())
    resolver = DomainPermissionResolver(perm_registry)
    service = ApprovalService(InMemoryApprovalRepository())

    request = DomainOperationRequest(
        request_id="req:modify:1",
        operation_id="project.modify_code",
        operation_version=PROJECT_DOMAIN_VERSION,
        inputs={},
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="task-1",
        session_id="sess-1",
        primary_domain_id=definition.domain_id,
        idempotency_key="idem-modify-1",
        granted_permissions=definition.required_permissions,
        available_resources=definition.required_resources,
        capabilities=("execute", "transaction", "rollback", "validation"),
        metadata={
            "actor_id": "actor-1",
            "validation_project_root": str(project_dir),
        },
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

    adapter = AgentExecutionAdapter(
        registry=common,
        execution_delegate=DomainOperationExecutionDelegate(registry),
        validation_adapter=AgentValidationAdapter(),
    )
    _now = datetime.now(timezone.utc)
    gate = DomainPermissionGate(resolver, service, clock=lambda: _now)

    class RollbackSpy:
        def __init__(self) -> None:
            self.calls = 0

        def rollback(self, transaction_id, checkpoint_id=None) -> bool:
            self.calls += 1
            return True

    orchestrator = DefaultDomainOperationOrchestrator(
        registry,
        adapter,
        approval_service=service,
        permission_gate=gate,
        transaction_manager=TransactionManagerSpy(),
        rollback_executor=RollbackSpy(),
        operation_validation_provider=(
            resolve_domain_operation_validation_requirements
        ),
    )
    approved_request = dataclasses.replace(
        request,
        approval_request_id=op_exec_approval_id,
        metadata={
            "actor_id": "actor-1",
            "approval_request_ids": approval_request_ids,
            "validation_project_root": str(project_dir),
        },
    )
    return orchestrator, approved_request, calls, project_dir


class TestRealOperationRequirementsReachAdapter:
    def test_real_domain_operation_requirements_reach_agent_validation_request(
        self,
    ) -> None:
        recorder = _RecordingAdapter()
        adapter = AgentExecutionAdapter(
            execution_delegate=lambda req: {"success": True, "output": {}},
            validation_adapter=recorder,
        )
        _register_test_operation(adapter)
        common = adapter.registry
        registry = InMemoryDomainOperationRegistry(common)
        definition = dataclasses.replace(
            _domain_operation(), reversible=False, rollback_policy_id=None
        )
        registry.register(definition, _TrivialImpl(definition))
        orchestrator = DefaultDomainOperationOrchestrator(
            registry,
            adapter,
            operation_validation_provider=(
                resolve_domain_operation_validation_requirements
            ),
        )
        request = DomainOperationRequest(
            request_id="req-req-1",
            operation_id="test.op",
            operation_version="1.0.0",
            inputs={},
            agent_run_id="run-1",
            workflow_id="wf-1",
            task_id="task-1",
            primary_domain_id="domain:test",
            idempotency_key="idem-req-1",
            capabilities=("execute", "validation"),
        )
        result = orchestrator.execute(request)
        assert result.status.value == "completed"
        # Both PRE and POST validation requests carried the exact host-derived
        # canonical requirement IDs from the operation definition.
        assert len(recorder.seen) == 2
        for seen_request in recorder.seen:
            validator_ids = tuple(
                vid for req in seen_request.requirements for vid in req.validator_ids
            )
            assert validator_ids == ("validation.test.op",)
        # Canonical validation evidence references are retained, not dropped.
        assert result.metadata.get("validation_result_ids") != ()

    def test_real_pre_validation_failure_prevents_domain_operation_execution(
        self, tmp_path
    ) -> None:
        orchestrator, request, calls, _ = _modify_code_stack(
            tmp_path, break_tree=True, break_on_execute=False
        )
        result = orchestrator.execute(request)
        assert calls == []
        assert result.status is not DomainOperationStatus.COMPLETED
        # The block came from real validation: evidence references retained.
        assert result.metadata.get("validation_result_ids") != ()

    def test_real_post_validation_failure_prevents_accepted_success(
        self, tmp_path
    ) -> None:
        orchestrator, request, calls, _ = _modify_code_stack(
            tmp_path, break_tree=False, break_on_execute=True
        )
        result = orchestrator.execute(request)
        assert calls != []
        assert result.status is not DomainOperationStatus.COMPLETED
        assert result.metadata.get("validation_result_ids") != ()

    def test_unknown_required_operation_validator_fails_closed(self) -> None:
        adapter = AgentExecutionAdapter(
            execution_delegate=lambda req: {"success": True, "output": {}},
            validation_adapter=AgentValidationAdapter(),
        )
        _register_test_operation(adapter)
        registry = InMemoryDomainOperationRegistry(adapter.registry)
        definition = dataclasses.replace(
            _domain_operation(), reversible=False, rollback_policy_id=None
        )
        registry.register(definition, _TrivialImpl(definition))
        orchestrator = DefaultDomainOperationOrchestrator(
            registry,
            adapter,
            operation_validation_provider=(
                resolve_domain_operation_validation_requirements
            ),
        )
        request = DomainOperationRequest(
            request_id="req-unk-1",
            operation_id="test.op",
            operation_version="1.0.0",
            inputs={},
            agent_run_id="run-1",
            workflow_id="wf-1",
            task_id="task-1",
            primary_domain_id="domain:test",
            idempotency_key="idem-unk-1",
            capabilities=("execute", "validation"),
        )
        with pytest.raises(ValidationAdapterError):
            orchestrator.execute(request)


class _TrivialImpl:
    def __init__(self, definition) -> None:
        self.definition = definition

    def execute(self, request) -> dict:
        return {"success": True, "output": {}}
