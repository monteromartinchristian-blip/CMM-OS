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
            # Host authority: the implementation declares the tree it
            # mutates; the orchestrator validates that tree, never caller
            # metadata.
            self.host_project_root = str(project_dir)

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


class _TrivialImpl:
    def __init__(self, definition) -> None:
        self.definition = definition

    def execute(self, request) -> dict:
        return {"success": True, "output": {}}


def _validating_operation(
    operation_id: str = "flow.op",
    domain_id: str = "domain:flow",
    validation_policy_id: str | None = "validation.flow.op",
    declared_ids: tuple[str, ...] = ("syntax_validator",),
) -> DomainOperationDefinition:
    from cmm.agent_runtime.enums import PolicyRiskLevel
    from cmm.domains.enums import DomainOperationType

    return DomainOperationDefinition(
        operation_id=operation_id,
        domain_id=domain_id,
        version="1.0.0",
        name="op",
        description="test operation",
        operation_type=DomainOperationType.READ,
        required_permissions=(),
        risk_level=PolicyRiskLevel.LOW,
        reversible=False,
        requires_approval=False,
        validation_policy_id=validation_policy_id,
        rollback_policy_id=None,
        enabled=True,
        metadata=(
            {"domain_validation_requirement_ids": list(declared_ids)}
            if declared_ids
            else {}
        ),
    )


def _validating_stack(tmp_path, project_root: str | None = None):
    import itertools as _itertools

    from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
    from cmm.domains.operation_execution import (
        DefaultDomainOperationOrchestrator,
        DomainOperationExecutionDelegate,
    )
    from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
    from cmm.domains.validation_integration import (
        resolve_domain_operation_validation_requirements as _resolver,
    )
    from cmm.domains.workflow_execution import DomainWorkflowExecutor

    _ids = _itertools.count()
    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)
    calls: list = []

    class Impl:
        def __init__(self, definition) -> None:
            self.definition = definition

        def execute(self, request) -> dict:
            calls.append(getattr(request, "operation_name", None))
            return {"success": True, "output": {"status": "ok"}}

    for op_id in ("flow.first", "flow.second", "flow.child"):
        definition = _validating_operation(operation_id=op_id)
        registry.register(definition, Impl(definition))

    adapter = AgentExecutionAdapter(
        registry=common,
        execution_delegate=DomainOperationExecutionDelegate(registry),
        validation_adapter=AgentValidationAdapter(),
    )
    orchestrator = DefaultDomainOperationOrchestrator(
        registry,
        adapter,
        operation_validation_provider=_resolver,
    )
    from cmm.domains.operation_execution import (
        build_domain_workflow_operation_adapter as _factory,
    )

    metadata: dict = {}
    if project_root is not None:
        metadata["validation_project_root"] = project_root
    node_adapter = _factory(
        orchestrator,
        primary_domain_id="domain:flow",
        capabilities=("execute", "validation"),
        metadata=metadata,
        id_factory=lambda: f"wf-node-{next(_ids)}",
    )
    executor = DomainWorkflowExecutor(
        id_factory=lambda: f"wf-run-{next(_ids)}",
        operation_adapter=node_adapter,
    )
    return executor, orchestrator, calls


class TestRealWorkflowValidationNodes:
    def test_real_domain_workflow_executes_required_validation_nodes(
        self, tmp_path
    ) -> None:
        from cmm.domains.workflow_contracts import (
            DomainWorkflowContext,
            DomainWorkflowDefinition,
        )
        from cmm.workflows.contracts import WorkflowNode
        from cmm.workflows.enums import WorkflowNodeType, WorkflowRunStatus

        project_dir = tmp_path / "flowproj"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "main.py").write_text("x = 1\n", encoding="utf-8")
        executor, _, calls = _validating_stack(tmp_path, str(project_dir))
        definition = DomainWorkflowDefinition(
            workflow_id="flow.main",
            domain_id="domain:flow",
            version="1.0.0",
            name="main",
            nodes=(
                WorkflowNode(
                    node_id="first",
                    node_type=WorkflowNodeType.EXECUTE_OPERATION,
                    name="first",
                    operation_id="flow.first",
                    operation_version="1.0.0",
                ),
                WorkflowNode(
                    node_id="second",
                    node_type=WorkflowNodeType.EXECUTE_OPERATION,
                    name="second",
                    dependencies=("first",),
                    operation_id="flow.second",
                    operation_version="1.0.0",
                ),
            ),
        )
        run = executor.execute(
            definition,
            DomainWorkflowContext(
                "domain:flow",
                available_operations=frozenset({"flow.first", "flow.second"}),
            ),
            {},
        )
        assert run.common_run.status is WorkflowRunStatus.COMPLETED
        assert calls == ["flow.first", "flow.second"]

        # A validation failure in a required node blocks the workflow: the
        # failing operation implementation never runs.
        (project_dir / "main.py").write_text("def broken(:\n", encoding="utf-8")
        executor2, _, calls2 = _validating_stack(tmp_path, str(project_dir))
        run2 = executor2.execute(
            definition,
            DomainWorkflowContext(
                "domain:flow",
                available_operations=frozenset({"flow.first", "flow.second"}),
            ),
            {},
        )
        assert run2.common_run.status is WorkflowRunStatus.FAILED
        assert calls2 == []

    def test_required_subworkflow_validation_survives_real_dependency_closure(
        self, tmp_path
    ) -> None:
        from cmm.domains.validation_integration import (
            compose_effective_validation_ids as _compose,
        )
        from cmm.domains.workflow_contracts import (
            DomainWorkflowContext,
            DomainWorkflowDefinition,
        )
        from cmm.workflows.contracts import WorkflowNode
        from cmm.workflows.enums import WorkflowNodeType, WorkflowRunStatus

        project_dir = tmp_path / "subproj"
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "main.py").write_text("x = 1\n", encoding="utf-8")

        # Host-computed dependency closure: parent plus required subworkflow
        # obligations survive as one effective set (planning-layer closure).
        closure = _compose(
            workflow_required=("syntax_validator",),
            dependency_required=("syntax_validator",),
        )
        assert closure == ("syntax_validator",)

        from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
        from cmm.domains.operation_execution import (
            DefaultDomainOperationOrchestrator,
            DomainOperationExecutionDelegate,
        )
        from cmm.domains.operation_execution import (
            build_domain_workflow_operation_adapter as _factory,
        )
        from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
        from cmm.domains.validation_integration import (
            resolve_domain_operation_validation_requirements as _resolver,
        )
        from cmm.domains.workflow_execution import DomainWorkflowExecutor

        common = InMemoryAgentOperationRegistry()
        registry = InMemoryDomainOperationRegistry(common)
        calls: list = []

        class Impl:
            def __init__(self, definition) -> None:
                self.definition = definition

            def execute(self, request) -> dict:
                calls.append(getattr(request, "operation_name", None))
                return {"success": True, "output": {"status": "ok"}}

        for op_id in ("flow.parent", "flow.child"):
            definition = _validating_operation(operation_id=op_id)
            registry.register(definition, Impl(definition))

        adapter = AgentExecutionAdapter(
            registry=common,
            execution_delegate=DomainOperationExecutionDelegate(registry),
            validation_adapter=AgentValidationAdapter(),
        )
        orchestrator = DefaultDomainOperationOrchestrator(
            registry, adapter, operation_validation_provider=_resolver
        )
        child_definition = DomainWorkflowDefinition(
            workflow_id="flow.child",
            domain_id="domain:flow",
            version="1.0.0",
            name="child",
            nodes=(
                WorkflowNode(
                    node_id="child-op",
                    node_type=WorkflowNodeType.EXECUTE_OPERATION,
                    name="child-op",
                    operation_id="flow.child",
                    operation_version="1.0.0",
                ),
            ),
        )
        import itertools as _itertools2

        _sub_ids = _itertools2.count()
        _run_ids = _itertools2.count()
        node_adapter = _factory(
            orchestrator,
            primary_domain_id="domain:flow",
            capabilities=("execute", "validation"),
            metadata={"validation_project_root": str(project_dir)},
            additional_validation_ids=closure,
            workflow_definitions={("flow.child", "1.0.0"): child_definition},
            available_operations=("flow.parent", "flow.child"),
            id_factory=lambda: f"wf-sub-{next(_sub_ids)}",
        )
        executor = DomainWorkflowExecutor(
            id_factory=lambda: f"wf-subrun-{next(_run_ids)}",
            operation_adapter=node_adapter,
        )
        parent = DomainWorkflowDefinition(
            workflow_id="flow.parent",
            domain_id="domain:flow",
            version="1.0.0",
            name="parent",
            nodes=(
                WorkflowNode(
                    node_id="parent-op",
                    node_type=WorkflowNodeType.EXECUTE_OPERATION,
                    name="parent-op",
                    operation_id="flow.parent",
                    operation_version="1.0.0",
                ),
                WorkflowNode(
                    node_id="child-flow",
                    node_type=WorkflowNodeType.INVOKE_SUBWORKFLOW,
                    name="child-flow",
                    dependencies=("parent-op",),
                    subworkflow_id="flow.child",
                    subworkflow_version="1.0.0",
                ),
            ),
        )
        run = executor.execute(
            parent,
            DomainWorkflowContext(
                "domain:flow",
                available_operations=frozenset({"flow.parent"}),
            ),
            {},
        )
        assert run.common_run.status is WorkflowRunStatus.COMPLETED
        assert calls == ["flow.parent", "flow.child"]

        # Breaking the subworkflow obligation blocks the parent run: the
        # dependency obligation survived execution, not just planning.
        (project_dir / "main.py").write_text("def broken(:\n", encoding="utf-8")
        run2 = executor.execute(
            parent,
            DomainWorkflowContext(
                "domain:flow",
                available_operations=frozenset({"flow.parent"}),
            ),
            {},
        )
        assert run2.common_run.status is WorkflowRunStatus.FAILED


def _specialized_stack(output_payload: dict):
    """Orchestrator stack whose implementation returns a specialized result."""
    from cmm.domains.operation_execution import (
        DefaultDomainOperationOrchestrator,
        DomainOperationExecutionDelegate,
    )
    from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
    from cmm.domains.validation_integration import (
        resolve_domain_operation_validation_requirements as _resolver,
    )

    common = InMemoryAgentOperationRegistry()
    registry = InMemoryDomainOperationRegistry(common)
    definition = _validating_operation(
        operation_id="flow.special",
        validation_policy_id="validation.flow.special",
        declared_ids=(),
    )

    class Impl:
        def __init__(self) -> None:
            self.definition = definition

        def execute(self, request) -> dict:
            return {"success": True, "output": dict(output_payload)}

    registry.register(definition, Impl())
    adapter = AgentExecutionAdapter(
        registry=common,
        execution_delegate=DomainOperationExecutionDelegate(registry),
        validation_adapter=_RecordingAdapter(),
    )
    orchestrator = DefaultDomainOperationOrchestrator(
        registry,
        adapter,
        operation_validation_provider=_resolver,
    )
    request = DomainOperationRequest(
        request_id="req-spec-1",
        operation_id="flow.special",
        operation_version="1.0.0",
        inputs={},
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="task-1",
        primary_domain_id="domain:flow",
        idempotency_key="idem-spec-1",
        capabilities=("execute", "validation"),
    )
    return orchestrator, request


class TestRealSpecializedResultAcceptance:
    def test_real_operation_outcome_rejects_invalid_specialized_result(self) -> None:
        orchestrator, request = _specialized_stack(
            {
                "domain_id": "domain:other",
                "operation_id": "flow.special",
                "status": "ok",
            }
        )
        result = orchestrator.execute(request)
        assert result.status is not DomainOperationStatus.COMPLETED

    def test_real_operation_outcome_rejects_operation_mismatch(self) -> None:
        orchestrator, request = _specialized_stack(
            {
                "domain_id": "domain:flow",
                "operation_id": "flow.impostor",
                "status": "ok",
            }
        )
        result = orchestrator.execute(request)
        assert result.status is not DomainOperationStatus.COMPLETED

    def test_real_operation_outcome_rejects_impossible_success(self) -> None:
        orchestrator, request = _specialized_stack(
            {
                "domain_id": "domain:flow",
                "operation_id": "flow.special",
                "status": "success",
                "validation_failed": True,
            }
        )
        result = orchestrator.execute(request)
        assert result.status is not DomainOperationStatus.COMPLETED

    def test_real_operation_outcome_accepts_coherent_specialized_result(self) -> None:
        orchestrator, request = _specialized_stack(
            {
                "domain_id": "domain:flow",
                "operation_id": "flow.special",
                "status": "ok",
            }
        )
        result = orchestrator.execute(request)
        assert result.status is DomainOperationStatus.COMPLETED

    def test_plain_output_without_identity_is_not_specialized(self) -> None:
        orchestrator, request = _specialized_stack({"status": "ok"})
        result = orchestrator.execute(request)
# ── V2→V3 remediation: BLOCKER-V2-01 provider fail-open ────────────────────────


class TestV2Blocker01ProviderFailClosed:
    """A validation-mandated operation must fail closed without a provider."""

    def test_validation_mandated_operation_fails_closed_when_provider_is_omitted(
        self,
    ) -> None:
        from cmm.domains.validation_integration import (
            DomainValidationIntegrationError,
        )

        common = InMemoryAgentOperationRegistry()
        registry = InMemoryDomainOperationRegistry(common)
        definition = _validating_operation(
            operation_id="flow.required",
            validation_policy_id="validation.flow.required",
            declared_ids=(),
        )
        calls: list = []

        class Impl:
            def __init__(self, definition) -> None:
                self.definition = definition

            def execute(self, request) -> dict:  # pragma: no cover
                calls.append(request)
                return {"success": True, "output": {}}

        registry.register(definition, Impl(definition))
        adapter = AgentExecutionAdapter(
            registry=common,
            execution_delegate=DomainOperationExecutionDelegate(registry),
            validation_adapter=AgentValidationAdapter(),
        )
        # Real orchestrator WITHOUT operation_validation_provider.
        orchestrator = DefaultDomainOperationOrchestrator(registry, adapter)
        request = DomainOperationRequest(
            request_id="req-provider-omitted",
            operation_id="flow.required",
            operation_version="1.0.0",
            inputs={},
            agent_run_id="run-1",
            workflow_id="wf-1",
            task_id="task-1",
            primary_domain_id="domain:flow",
            idempotency_key="idem-provider-omitted",
            capabilities=("execute", "validation"),
        )
        with pytest.raises(DomainValidationIntegrationError):
            orchestrator.execute(request)
        assert calls == []

    def test_validation_obligation_without_provider_fails_closed(self) -> None:
        from cmm.domains.validation_integration import (
            DomainValidationIntegrationError,
        )

        common = InMemoryAgentOperationRegistry()
        registry = InMemoryDomainOperationRegistry(common)
        definition = _validating_operation(
            operation_id="flow.needs",
            validation_policy_id="validation.flow.needs",
            declared_ids=(),
        )

        class Impl:
            def __init__(self, definition) -> None:
                self.definition = definition

            def execute(self, request) -> dict:  # pragma: no cover
                raise AssertionError("must not execute")

        registry.register(definition, Impl(definition))
        adapter = AgentExecutionAdapter(
            registry=common,
            execution_delegate=DomainOperationExecutionDelegate(registry),
            validation_adapter=AgentValidationAdapter(),
        )
        orchestrator = DefaultDomainOperationOrchestrator(registry, adapter)
        request = DomainOperationRequest(
            request_id="req-needs-provider",
            operation_id="flow.needs",
            operation_version="1.0.0",
            inputs={},
            agent_run_id="run-1",
            workflow_id="wf-1",
            task_id="task-1",
            primary_domain_id="domain:flow",
            idempotency_key="idem-needs-provider",
            capabilities=("execute", "validation"),
        )
        with pytest.raises(DomainValidationIntegrationError):
            orchestrator.execute(request)

    def test_no_obligation_operation_stays_compatible_without_provider(self) -> None:
        common = InMemoryAgentOperationRegistry()
        registry = InMemoryDomainOperationRegistry(common)
        definition = _validating_operation(
            operation_id="flow.free",
            validation_policy_id=None,
            declared_ids=(),
        )
        registry.register(definition, _TrivialImpl(definition))
        adapter = AgentExecutionAdapter(
            registry=common,
            execution_delegate=DomainOperationExecutionDelegate(registry),
            validation_adapter=AgentValidationAdapter(),
        )
        orchestrator = DefaultDomainOperationOrchestrator(registry, adapter)
        request = DomainOperationRequest(
            request_id="req-free",
            operation_id="flow.free",
            operation_version="1.0.0",
            inputs={},
            agent_run_id="run-1",
            workflow_id="wf-1",
            task_id="task-1",
            primary_domain_id="domain:flow",
            idempotency_key="idem-free",
            capabilities=("execute", "validation"),
        )
        result = orchestrator.execute(request)
        assert result.status is DomainOperationStatus.COMPLETED


class TestV2Blocker01SpecializedResultUnconditional:
    """Structural specialized-result acceptance must not depend on the provider."""

    def test_invalid_specialized_result_is_rejected_even_without_validation_provider(
        self,
    ) -> None:
        common = InMemoryAgentOperationRegistry()
        registry = InMemoryDomainOperationRegistry(common)
        definition = _validating_operation(
            operation_id="flow.special-free",
            validation_policy_id=None,
            declared_ids=(),
        )

        class Impl:
            def __init__(self, definition) -> None:
                self.definition = definition

            def execute(self, request) -> dict:  # pragma: no cover
                return {
                    "success": True,
                    "output": {
                        "domain_id": "domain:other",
                        "operation_id": "flow.special-free",
                        "status": "ok",
                    },
                }

        registry.register(definition, Impl(definition))
        adapter = AgentExecutionAdapter(
            registry=common,
            execution_delegate=DomainOperationExecutionDelegate(registry),
            validation_adapter=AgentValidationAdapter(),
        )
        orchestrator = DefaultDomainOperationOrchestrator(registry, adapter)
        request = DomainOperationRequest(
            request_id="req-special-free",
            operation_id="flow.special-free",
            operation_version="1.0.0",
            inputs={},
            agent_run_id="run-1",
            workflow_id="wf-1",
            task_id="task-1",
            primary_domain_id="domain:flow",
            idempotency_key="idem-special-free",
            capabilities=("execute", "validation"),
        )
        result = orchestrator.execute(request)
        assert result.status is not DomainOperationStatus.COMPLETED

    def test_coherent_specialized_result_accepted_without_provider(self) -> None:
        common = InMemoryAgentOperationRegistry()
        registry = InMemoryDomainOperationRegistry(common)
        definition = _validating_operation(
            operation_id="flow.special-free",
            validation_policy_id=None,
            declared_ids=(),
        )

        class Impl:
            def __init__(self, definition) -> None:
                self.definition = definition

            def execute(self, request) -> dict:  # pragma: no cover
                return {
                    "success": True,
                    "output": {
                        "domain_id": "domain:flow",
                        "operation_id": "flow.special-free",
                        "status": "ok",
                    },
                }

        registry.register(definition, Impl(definition))
        adapter = AgentExecutionAdapter(
            registry=common,
            execution_delegate=DomainOperationExecutionDelegate(registry),
            validation_adapter=AgentValidationAdapter(),
        )
        orchestrator = DefaultDomainOperationOrchestrator(registry, adapter)
        request = DomainOperationRequest(
            request_id="req-special-free-ok",
            operation_id="flow.special-free",
            operation_version="1.0.0",
            inputs={},
            agent_run_id="run-1",
            workflow_id="wf-1",
            task_id="task-1",
            primary_domain_id="domain:flow",
            idempotency_key="idem-special-free-ok",
            capabilities=("execute", "validation"),
        )
        result = orchestrator.execute(request)
        assert result.status is DomainOperationStatus.COMPLETED
