"""Phase 9.28 – Integration with the Existing System.

Verifies that ``AgentRuntimeIntegrationService`` wires the Cognitive Layer
adapter (9.5), Workflow Planner adapter (9.7), and Validation Integration
adapter (9.14) through their existing public APIs, without reimplementing
reasoning, planning, or validation, and without creating a second runtime,
planner, cognitive engine, or store.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cmm.agent_runtime.action_budget_service import ActionBudgetService
from cmm.agent_runtime.agent_factory import AgentFactoryRegistry
from cmm.agent_runtime.agent_registry import AgentRegistry
from cmm.agent_runtime.agent_registry_contracts import (
    AgentCapability,
    AgentDescriptor,
    AgentFactoryContext,
    AgentInstance,
    AgentVersion,
)
from cmm.agent_runtime.agent_registry_enums import (
    AgentCapabilityKind,
    AgentFactoryScope,
    AgentKind,
    AgentLifecycle,
)
from cmm.agent_runtime.agent_registry_service import AgentRegistryService
from cmm.agent_runtime.agent_runtime_integration_contracts import (
    IntegratedAgentExecutionRequest,
    IntegrationExecutionPolicy,
)
from cmm.agent_runtime.agent_runtime_integration_enums import IntegrationExecutionState
from cmm.agent_runtime.agent_runtime_integration_errors import (
    AgentRuntimeIntegrationError,
)
from cmm.agent_runtime.agent_runtime_integration_service import (
    AgentRuntimeIntegrationService,
)
from cmm.agent_runtime.agent_runtime_integration_store import (
    InMemoryAgentRuntimeIntegrationStore,
)
from cmm.agent_runtime.agent_security_contracts import AgentPermissionContext
from cmm.agent_runtime.agent_security_enums import SensitivityLevel
from cmm.agent_runtime.agent_security_service import AgentSecurityService
from cmm.agent_runtime.approval_service import ApprovalService
from cmm.agent_runtime.cognitive_adapter import AgentCognitiveService
from cmm.agent_runtime.enums import (
    AgentPlanningDecision,
    AgentPlanningStatus,
    AgentValidationStage,
    GoalKind,
    GoalStatus,
    ValidationRequirementKind,
    WorkflowPlanValidationStatus,
)
from cmm.agent_runtime.errors import CognitiveAdapterExecutionError
from cmm.agent_runtime.goal_contracts import Goal, GoalPriority
from cmm.agent_runtime.goal_manager import GoalManager
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.operation_execution_contracts import (
    AgentOperationRequest,
    OperationDescriptor,
)
from cmm.agent_runtime.runtime_event_bus import AgentRuntimeEventBus
from cmm.agent_runtime.runtime_loop import AgentRuntimeLoop
from cmm.agent_runtime.validation_execution_adapter import AgentValidationAdapter
from cmm.agent_runtime.validation_integration_contracts import (
    ValidationPolicySelection,
    ValidationRequirement,
)
from cmm.agent_runtime.validation_policy_adapter import AgentValidationPolicyAdapter
from cmm.agent_runtime.workflow_planner_contracts import (
    AgentReplanningResult,
    AgentWorkflowOperation,
    AgentWorkflowPlan,
    AgentWorkflowPlanValidation,
    AgentWorkflowTask,
)
from cmm.cognitive.contracts import CognitiveResult, CognitiveStatus, Confidence

UTC_NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)

SCRATCH_DIR = Path(
    "/private/tmp/claude-501/-Users-chris-CMM-OS/9f1e84e4-c208-4141-9918-f1e4570d75d2"
    "/scratchpad/phase-9-28"
)
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)


def _write_fixture(name: str, content: str) -> Path:
    path = SCRATCH_DIR / name
    path.write_text(content)
    return path


GOOD_PY = _write_fixture("good_9_28.py", "def ok():\n    return 1\n")
BAD_PY = _write_fixture("bad_9_28.py", "def broken(:\n    pass\n")

# The composition root threads ``validation_project_root`` straight into the
# real Phase 7 ``ValidationContext.project_root`` — required so the syntax/ast
# steps resolve the scratch fixtures below as in-scope instead of falling
# back to a whole-repo scan (see AgentRuntimeIntegrationService._run_validation_stage).
_VALIDATION_ROOT_METADATA = {"validation_project_root": str(SCRATCH_DIR)}


# ── Shared value-object builders ──────────────────────────────────────────


def _permission_context(**overrides: object) -> AgentPermissionContext:
    values: dict[str, object] = {
        "id": "perm-ctx-928",
        "agent_id": "agent-1",
        "agent_run_id": "run-1",
        "goal_id": "goal-1",
        "actor_id": "actor-1",
        "owner_actor_id": "actor-1",
        "allowed_domains": ("documents", "code"),
        "allowed_resources": ("doc-1", str(GOOD_PY), str(BAD_PY)),
        "allowed_operations": ("documents.read", "code.write", "flaky.op"),
        "allowed_sensitivity_levels": (SensitivityLevel.INTERNAL,),
        "maximum_autonomy_level": 2,
        "created_at": UTC_NOW,
    }
    values.update(overrides)
    return AgentPermissionContext(**values)


def _operation_request(**overrides: object) -> AgentOperationRequest:
    values: dict[str, object] = {
        "id": "op-1",
        "agent_run_id": "run-1",
        "workflow_id": "workflow-1",
        "task_id": "task-1",
        "operation_name": "documents.read",
        "idempotency_key": "idem-1",
        "parameters": {},
        "created_at": UTC_NOW.isoformat(),
    }
    values.update(overrides)
    return AgentOperationRequest(**values)


def _policy(**overrides: object) -> IntegrationExecutionPolicy:
    values: dict[str, object] = {"max_operations": 10, "max_retries": 2}
    values.update(overrides)
    return IntegrationExecutionPolicy(**values)


def _request(**overrides: object) -> IntegratedAgentExecutionRequest:
    values: dict[str, object] = {
        "execution_id": "exec-1",
        "request_id": "req-1",
        "goal_id": "goal-1",
        "actor_id": "actor-1",
        "owner_actor_id": "actor-1",
        "requested_agent_id": "agent-1",
        "permission_context": _permission_context(),
        "operations": (_operation_request(),),
        "sensitivity": SensitivityLevel.INTERNAL,
        "max_autonomy_level": 2,
        "deadline": UTC_NOW + timedelta(hours=1),
        "correlation_id": "corr-1",
        "causation_id": "cause-1",
        "policy": _policy(),
        "created_at": UTC_NOW,
    }
    values.update(overrides)
    return IntegratedAgentExecutionRequest(**values)


# ── Test doubles for canonical registry/factory/observability plumbing ───


class _StubAgentFactory:
    def __init__(self, factory_id: str = "factory-agent-928") -> None:
        self.factory_id = factory_id
        self.scope = AgentFactoryScope.TRANSIENT
        self.thread_safe = True
        self.created: list[AgentFactoryContext] = []

    def supports(self, descriptor: AgentDescriptor) -> bool:
        return descriptor.factory_id == self.factory_id

    def create(
        self, descriptor: AgentDescriptor, context: AgentFactoryContext
    ) -> AgentInstance:
        self.created.append(context)
        return AgentInstance(
            instance_id=f"instance-{context.request_id}",
            descriptor=descriptor,
            runtime_object={"agent_id": descriptor.agent_id},
            scope=self.scope,
        )


class _FakeMemoryService:
    def __init__(self) -> None:
        self.updates: list[dict[str, object]] = []

    def record_execution_result(self, **payload: object) -> str:
        self.updates.append(dict(payload))
        return f"memory-{len(self.updates)}"


# ── Test doubles for Cognitive Layer scripting ────────────────────────────


class _ScriptedCognitiveLayer:
    """A minimal, deterministic stand-in for the Cognitive Layer engine.

    Real ``CognitiveResult``/``Confidence`` contracts are returned — only the
    reasoning *content* is scripted (by ``correlation_id``), matching how a
    caller of ``CognitiveRuntimeAdapter.analyze`` would inject any cognitive
    engine.
    """

    def __init__(self) -> None:
        self.calls: list[object] = []
        self.scripts: dict[str, CognitiveResult] = {}
        self.raise_for: dict[str, Exception] = {}

    def analyze(self, ctx: object) -> CognitiveResult:
        self.calls.append(ctx)
        key = ctx.metadata.get("correlation_id")
        if key in self.raise_for:
            raise self.raise_for[key]
        if key in self.scripts:
            return self.scripts[key]
        return CognitiveResult(
            objective="objective",
            status=CognitiveStatus.COMPLETED,
            confidence=Confidence(value=1.0, source="scripted"),
        )


# ── Test doubles for Planner scripting ────────────────────────────────────


class _FakePlanningService:
    """Real canonical plan/validation dataclasses, scripted plan content.

    Exercises the integration service's planner wiring (request shape,
    validation gate, operation conversion, replan bookkeeping) without
    depending on ``TaskPlanner``'s specific reasoning output — that is
    covered by Phase 9.7's own test suite.
    """

    def __init__(self) -> None:
        self.plan_calls: list[object] = []
        self.replan_calls: list[object] = []
        self.validate_calls: list[AgentWorkflowPlan] = []
        self._plans: dict[str, AgentWorkflowPlan] = {}
        self.plan_operation_name = "documents.read"
        self.replan_operation_name = "documents.read"
        self.invalid = False
        self.plan_error: Exception | None = None

    def _build_plan(
        self,
        *,
        plan_id: str,
        goal_id: str,
        agent_run_id: str,
        workflow_id: str,
        version: int,
        operation_name: str,
        previous_version_id: str | None,
    ) -> AgentWorkflowPlan:
        task_id = f"task-{plan_id}"
        op_id = f"op-{plan_id}"
        operation = AgentWorkflowOperation(
            id=op_id, task_id=task_id, operation_name=operation_name, parameters={}
        )
        task = AgentWorkflowTask(
            id=task_id,
            workflow_id=workflow_id,
            name="do the work",
            description="do the work",
            operation_ids=[op_id],
        )
        return AgentWorkflowPlan(
            id=plan_id,
            goal_id=goal_id,
            agent_run_id=agent_run_id,
            workflow_id=workflow_id,
            version=version,
            previous_version_id=previous_version_id,
            tasks=[task],
            operations=[operation],
        )

    def plan(self, request: object) -> AgentWorkflowPlan:
        self.plan_calls.append(request)
        if self.plan_error is not None:
            raise self.plan_error
        plan_id = f"plan-{request.id}-{len(self._plans) + 1}"
        wf_id = f"workflow-{request.id}"
        built = self._build_plan(
            plan_id=plan_id,
            goal_id=request.goal_id,
            agent_run_id=request.agent_run_id,
            workflow_id=wf_id,
            version=1,
            operation_name=self.plan_operation_name,
            previous_version_id=None,
        )
        self._plans[plan_id] = built
        return built

    def validate_plan(
        self, plan: AgentWorkflowPlan, request: object = None
    ) -> AgentWorkflowPlanValidation:
        self.validate_calls.append(plan)
        if self.invalid:
            return AgentWorkflowPlanValidation(
                status=WorkflowPlanValidationStatus.FAILED,
                is_valid=False,
                blocking_errors=["operation is not registered"],
            )
        return AgentWorkflowPlanValidation(
            status=WorkflowPlanValidationStatus.PASSED, is_valid=True
        )

    def replan(self, request: object) -> AgentReplanningResult:
        self.replan_calls.append(request)
        prev = self._plans[request.plan_id]
        new_id = f"{prev.id}-replan-{len(self.replan_calls)}"
        new_plan = self._build_plan(
            plan_id=new_id,
            goal_id=prev.goal_id,
            agent_run_id=prev.agent_run_id,
            workflow_id=prev.workflow_id,
            version=prev.version + 1,
            operation_name=self.replan_operation_name,
            previous_version_id=prev.id,
        )
        self._plans[new_id] = new_plan
        return AgentReplanningResult(
            id=f"replan-res-{request.id}",
            request_id=request.id,
            status=AgentPlanningStatus.COMPLETED,
            decision=AgentPlanningDecision.REPLAN,
            previous_plan_id=prev.id,
            new_plan=new_plan,
            version=new_plan.version,
            change_reason=request.reason,
        )

    def get_plan(self, plan_id: str) -> AgentWorkflowPlan | None:
        return self._plans.get(plan_id)


class _RaisingPlanningService:
    """Planning service whose ``plan()`` always raises — proves visibility."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def plan(self, request: object) -> AgentWorkflowPlan:
        raise self._error

    def replan(self, request: object) -> AgentReplanningResult:
        raise self._error

    def validate_plan(self, plan: object, request: object = None) -> object:
        raise self._error


# ── Test doubles for Validation scripting ─────────────────────────────────


class _PreExecutionOverridePolicyService:
    """Wraps the real ``AgentValidationPolicyAdapter`` for every stage except
    ``PRE_EXECUTION``, where it substitutes a scripted requirement.

    The real resolver's ``PRE_EXECUTION`` requirements are intentionally
    abstract (preventative/security, no ``validator_ids``) and never block —
    see docs/architecture/phase-9-28-existing-system-integration.md. This
    double lets tests exercise a genuinely blocking pre-execution requirement
    while still executing it through the real ``AgentValidationAdapter`` /
    Phase 7 pipeline.
    """

    def __init__(self, pre_execution_requirement: ValidationRequirement) -> None:
        self._real = AgentValidationPolicyAdapter()
        self._requirement = pre_execution_requirement
        self.calls: list[str] = []

    def select_policy(self, **kwargs: object) -> ValidationPolicySelection:
        stage = kwargs.get("stage")
        self.calls.append(str(stage))
        if stage == AgentValidationStage.PRE_EXECUTION:
            return ValidationPolicySelection(
                policy_id="scripted-pre-execution",
                requirements=(self._requirement,),
                rationale=("scripted for test",),
            )
        return self._real.select_policy(**kwargs)


class _RaisingValidationService:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def validate(self, request: object, exec_context: object = None) -> object:
        raise self._error


# ── Harness ────────────────────────────────────────────────────────────────


class _Harness:
    def __init__(
        self,
        *,
        cognitive_service: object = None,
        planning_service: object = None,
        validation_service: object = None,
        validation_policy_service: object = None,
        failing_operations: frozenset[str] = frozenset(),
    ) -> None:
        self.store = InMemoryAgentRuntimeIntegrationStore()
        self.goal_manager = GoalManager()
        self.registry_service = AgentRegistryService(
            registry=AgentRegistry(), factory_registry=AgentFactoryRegistry()
        )
        self.factory = _StubAgentFactory()
        self.registry_service.register_factory(self.factory)
        self.runtime_loop = AgentRuntimeLoop(
            goal_repository=self.goal_manager.repository
        )
        self.security_service = AgentSecurityService()
        self.approval_service = ApprovalService()
        self.budget_service = ActionBudgetService()
        self._failing_operations = failing_operations
        self.execution_adapter = AgentExecutionAdapter(
            execution_delegate=self._execution_delegate
        )
        self.event_bus = AgentRuntimeEventBus()
        self.memory_service = _FakeMemoryService()
        self.cognitive_service = cognitive_service
        self.planning_service = planning_service
        self.validation_service = validation_service
        self.validation_policy_service = validation_policy_service
        self.service = AgentRuntimeIntegrationService(
            store=self.store,
            goal_manager=self.goal_manager,
            registry_service=self.registry_service,
            runtime_loop=self.runtime_loop,
            security_service=self.security_service,
            budget_service=self.budget_service,
            approval_service=self.approval_service,
            execution_adapter=self.execution_adapter,
            event_bus=self.event_bus,
            observability_service=None,
            memory_service=self.memory_service,
            cognitive_service=cognitive_service,
            planning_service=planning_service,
            validation_service=validation_service,
            validation_policy_service=validation_policy_service,
        )
        self.register_goal()
        self.register_agent()
        self.register_operation("documents.read")
        self.register_operation("flaky.op")
        self.register_operation(
            "code.write",
            effects=("update",),
            tags=("python", "src"),
            reversible=True,
        )

    def _execution_delegate(
        self, operation: AgentOperationRequest
    ) -> dict[str, object]:
        if operation.operation_name in self._failing_operations:
            return {"success": False}
        return {"success": True, "operation": operation.operation_name}

    def register_goal(
        self, *, goal_id: str = "goal-1", status: GoalStatus = GoalStatus.ACTIVE
    ) -> Goal:
        goal = Goal(
            id=goal_id,
            title="Do work",
            description="Do the requested work",
            kind=GoalKind.INFORMATION,
            status=status,
            priority=GoalPriority(score=50),
            owner_actor_id="actor-1",
            assigned_agent_id="agent-1",
            autonomy_level=2,
            created_at=UTC_NOW,
            updated_at=UTC_NOW,
        )
        return self.goal_manager.register_goal(goal, actor_id="actor-1")

    def register_agent(
        self,
        *,
        agent_id: str = "agent-1",
        capabilities: tuple[str, ...] = ("documents.read", "flaky.op", "code.write"),
    ) -> AgentDescriptor:
        descriptor = AgentDescriptor(
            agent_id=agent_id,
            name="Worker Agent",
            version=AgentVersion(1, 0, 0),
            kind=AgentKind.GENERAL,
            lifecycle=AgentLifecycle.ACTIVE,
            description="Executes registered operations",
            capabilities=tuple(
                AgentCapability(
                    name=capability,
                    kind=AgentCapabilityKind.OPERATION,
                    description=f"Capability {capability}",
                    operations=(capability,),
                )
                for capability in capabilities
            ),
            supported_operations=capabilities,
            factory_id=self.factory.factory_id,
            created_at=UTC_NOW,
        )
        self.registry_service.register_agent(descriptor)
        return descriptor

    def register_operation(
        self,
        name: str,
        *,
        effects: tuple[str, ...] = ("read",),
        tags: tuple[str, ...] = (),
        reversible: bool = True,
    ) -> None:
        self.execution_adapter.register_operation(
            OperationDescriptor(
                name=name,
                description=f"Operation {name}",
                effects=effects,
                reversible=reversible,
                metadata={"tags": tags} if tags else {},
            )
        )


def _service_request(**overrides: object) -> IntegratedAgentExecutionRequest:
    values: dict[str, object] = {
        "deadline": datetime.now(timezone.utc) + timedelta(hours=1)
    }
    values.update(overrides)
    return _request(**values)


# ── 1. Direct execution without Cognitive/Planner ─────────────────────────


def test_direct_execution_without_cognitive_or_planner() -> None:
    layer = _ScriptedCognitiveLayer()
    planning = _FakePlanningService()
    harness = _Harness(
        cognitive_service=AgentCognitiveService(cognitive_layer=layer),
        planning_service=planning,
    )

    result = harness.service.execute(_service_request())

    assert result.final_state is IntegrationExecutionState.COMPLETED
    assert layer.calls == []
    assert planning.plan_calls == []


# ── 2. Cognitive analyze() real ────────────────────────────────────────────


def test_cognitive_analyze_real_result_persisted() -> None:
    layer = _ScriptedCognitiveLayer()
    planning = _FakePlanningService()
    harness = _Harness(
        cognitive_service=AgentCognitiveService(cognitive_layer=layer),
        planning_service=planning,
    )
    request = _service_request(
        operations=(), correlation_id="corr-cognitive-real", causation_id="cause-real"
    )

    result = harness.service.execute(request)

    assert result.final_state is IntegrationExecutionState.COMPLETED
    assert len(layer.calls) == 1
    assert layer.calls[0].actor_id == "actor-1"
    assert result.metadata["cognitive_result_id"].startswith("ag-cog-res-")
    assert result.metadata["cognitive_status"] == "completed"
    assert result.metadata["cognitive_decision"] == "plan"
    assert 0.0 <= result.metadata["cognitive_confidence"] <= 1.0
    assert (
        planning.plan_calls[0].cognitive_result_id
        == result.metadata["cognitive_result_id"]
    )


# ── 3. Cognitive blocking gap / question ───────────────────────────────────


def test_cognitive_blocking_gap_fails_closed() -> None:
    layer = _ScriptedCognitiveLayer()
    layer.scripts["corr-gap"] = CognitiveResult(
        objective="objective",
        status=CognitiveStatus.COMPLETED,
        confidence=Confidence(value=0.4, source="scripted"),
        metadata={
            "information_gaps": ["missing target file"],
            "blocking_resource_gap": True,
        },
    )
    planning = _FakePlanningService()
    harness = _Harness(
        cognitive_service=AgentCognitiveService(cognitive_layer=layer),
        planning_service=planning,
    )
    request = _service_request(operations=(), correlation_id="corr-gap")

    result = harness.service.execute(request)

    assert result.final_state is IntegrationExecutionState.FAILED
    assert result.errors
    assert planning.plan_calls == []


def test_cognitive_blocking_question_fails_closed() -> None:
    layer = _ScriptedCognitiveLayer()
    layer.scripts["corr-question"] = CognitiveResult(
        objective="objective",
        status=CognitiveStatus.COMPLETED,
        confidence=Confidence(value=0.4, source="scripted"),
        metadata={"questions": ["what target?"], "blocking_question": True},
    )
    harness = _Harness(
        cognitive_service=AgentCognitiveService(cognitive_layer=layer),
        planning_service=_FakePlanningService(),
    )
    request = _service_request(operations=(), correlation_id="corr-question")

    result = harness.service.execute(request)

    assert result.final_state is IntegrationExecutionState.FAILED


# ── 4. Cognitive non-blocking warning continues ────────────────────────────


def test_cognitive_non_blocking_warning_continues() -> None:
    layer = _ScriptedCognitiveLayer()
    layer.scripts["corr-nonblocking"] = CognitiveResult(
        objective="objective",
        status=CognitiveStatus.COMPLETED,
        confidence=Confidence(value=0.9, source="scripted"),
        metadata={"questions": ["clarify later"], "blocking_question": False},
    )
    harness = _Harness(
        cognitive_service=AgentCognitiveService(cognitive_layer=layer),
        planning_service=_FakePlanningService(),
    )
    request = _service_request(operations=(), correlation_id="corr-nonblocking")

    result = harness.service.execute(request)

    assert result.final_state is IntegrationExecutionState.COMPLETED
    assert result.metadata["cognitive_question_count"] == 1


def test_cognitive_required_by_policy_fails_closed_when_absent() -> None:
    harness = _Harness(cognitive_service=None, planning_service=None)
    request = _service_request(policy=_policy(metadata={"require_cognitive": True}))

    with pytest.raises(AgentRuntimeIntegrationError, match="cognitive"):
        harness.service.execute(request)

    assert harness.store.get("exec-1") is None


# ── 5. Planning real when operations missing ───────────────────────────────


def test_planning_real_when_operations_missing() -> None:
    planning = _FakePlanningService()
    planning.plan_operation_name = "documents.read"
    harness = _Harness(planning_service=planning)
    request = _service_request(operations=())

    result = harness.service.execute(request)

    assert result.final_state is IntegrationExecutionState.COMPLETED
    assert len(planning.plan_calls) == 1
    assert len(planning.validate_calls) == 1
    assert len(result.operation_results) == 1
    assert result.operation_results[0].operation_name == "documents.read"


def test_workflow_version_preserved() -> None:
    planning = _FakePlanningService()
    harness = _Harness(planning_service=planning)
    request = _service_request(operations=())

    result = harness.service.execute(request)

    assert result.metadata["plan_version"] == 1
    stored_plan_id = result.metadata["plan_id"]
    assert planning.get_plan(stored_plan_id) is not None
    assert (
        result.metadata["plan_workflow_id"]
        == planning.get_plan(stored_plan_id).workflow_id
    )


# ── 6. Invalid workflow plan fails closed ──────────────────────────────────


def test_invalid_plan_fails_closed() -> None:
    planning = _FakePlanningService()
    planning.invalid = True
    harness = _Harness(planning_service=planning)
    request = _service_request(operations=())

    result = harness.service.execute(request)

    assert result.final_state is IntegrationExecutionState.FAILED
    assert any("invalid" in error for error in result.errors)
    assert harness.execution_adapter.repository.list_results("run-exec-1") == []


# ── 8. Replan during recovery, bounded ──────────────────────────────────────


def test_replan_during_recovery() -> None:
    planning = _FakePlanningService()
    planning.plan_operation_name = "flaky.op"
    planning.replan_operation_name = "documents.read"
    harness = _Harness(
        planning_service=planning, failing_operations=frozenset({"flaky.op"})
    )
    request = _service_request(
        operations=(),
        policy=_policy(allow_recovery=True, require_terminal_validation=False),
    )

    result = harness.service.execute(request)

    original_plan_id = next(iter(planning._plans))

    assert result.final_state is IntegrationExecutionState.COMPLETED
    assert len(planning.replan_calls) == 1
    assert result.metadata["plan_version"] == 2
    assert result.metadata["previous_plan_id"] == original_plan_id
    assert result.metadata["replan_count"] == 1
    assert len(result.operation_results) == 2
    assert result.operation_results[0].success is False
    assert result.operation_results[1].success is True


def test_replan_is_bounded_to_one_attempt() -> None:
    planning = _FakePlanningService()
    planning.plan_operation_name = "flaky.op"
    planning.replan_operation_name = "flaky.op"
    harness = _Harness(
        planning_service=planning, failing_operations=frozenset({"flaky.op"})
    )
    request = _service_request(
        operations=(),
        policy=_policy(allow_recovery=True, require_terminal_validation=False),
    )

    result = harness.service.execute(request)

    assert result.final_state is IntegrationExecutionState.FAILED
    assert len(planning.replan_calls) == 1
    assert result.metadata["replan_count"] == 1


# ── 9/10. Pre-execution validation approved / rejected ─────────────────────


def test_pre_validation_approved() -> None:
    harness = _Harness(
        validation_service=AgentValidationAdapter(),
        validation_policy_service=AgentValidationPolicyAdapter(),
    )

    result = harness.service.execute(_service_request())

    assert result.final_state is IntegrationExecutionState.COMPLETED
    assert result.validation_results
    assert result.validation_results[0]["stage"] == "pre_execution"
    assert result.validation_results[0]["decision"] == "continue"


def test_pre_validation_rejected_blocks_execution() -> None:
    scripted_requirement = ValidationRequirement(
        requirement_id="req-scripted-pre-syntax",
        validation_kind=ValidationRequirementKind.SYNTAX,
        stage=AgentValidationStage.PRE_EXECUTION,
        required=True,
        blocking=True,
        validator_ids=("syntax_validator",),
    )
    policy_service = _PreExecutionOverridePolicyService(scripted_requirement)
    harness = _Harness(
        validation_service=AgentValidationAdapter(),
        validation_policy_service=policy_service,
    )
    request = _service_request(
        resources={"changed_files": (str(BAD_PY),)}, metadata=_VALIDATION_ROOT_METADATA
    )

    result = harness.service.execute(request)

    assert result.final_state is IntegrationExecutionState.FAILED
    assert result.validation_results[0]["decision"] == "block"
    assert result.validation_results[0]["findings"]
    assert harness.execution_adapter.repository.list_results("run-exec-1") == []


# ── 11/12. Post-execution validation approved / rejected ───────────────────


def test_post_validation_approved_writes_memory() -> None:
    harness = _Harness(
        validation_service=AgentValidationAdapter(),
        validation_policy_service=AgentValidationPolicyAdapter(),
    )
    request = _service_request(
        operations=(_operation_request(operation_name="code.write"),),
        resources={"changed_files": (str(GOOD_PY),)},
        policy=_policy(require_terminal_validation=False),
        metadata=_VALIDATION_ROOT_METADATA,
    )

    result = harness.service.execute(request)

    assert result.final_state is IntegrationExecutionState.COMPLETED
    post_results = [
        v for v in result.validation_results if v["stage"] == "post_execution"
    ]
    assert post_results and post_results[0]["decision"] == "continue"
    assert harness.memory_service.updates


def test_post_validation_rejected_no_memory_write() -> None:
    harness = _Harness(
        validation_service=AgentValidationAdapter(),
        validation_policy_service=AgentValidationPolicyAdapter(),
    )
    request = _service_request(
        operations=(_operation_request(operation_name="code.write"),),
        resources={"changed_files": (str(BAD_PY),)},
        policy=_policy(require_terminal_validation=False),
        metadata=_VALIDATION_ROOT_METADATA,
    )

    result = harness.service.execute(request)

    assert result.final_state is IntegrationExecutionState.FAILED
    post_results = [
        v for v in result.validation_results if v["stage"] == "post_execution"
    ]
    assert post_results and post_results[0]["decision"] != "continue"
    assert harness.memory_service.updates == []


# ── 13. Commit gate denial blocks completion ────────────────────────────────


def test_commit_gate_denied_blocks_completion() -> None:
    harness = _Harness(
        validation_service=AgentValidationAdapter(),
        validation_policy_service=AgentValidationPolicyAdapter(),
    )
    request = _service_request(
        operations=(_operation_request(operation_name="code.write"),),
        resources={"changed_files": (str(GOOD_PY),)},
        metadata=_VALIDATION_ROOT_METADATA,
    )

    result = harness.service.execute(request)

    assert result.final_state is IntegrationExecutionState.FAILED
    commit_results = [
        v for v in result.validation_results if v["stage"] == "pre_commit"
    ]
    assert commit_results and commit_results[0]["decision"] != "continue"
    assert harness.memory_service.updates == []


def test_commit_gate_approved_completes() -> None:
    harness = _Harness(
        validation_service=AgentValidationAdapter(),
        validation_policy_service=AgentValidationPolicyAdapter(),
    )
    request = _service_request(
        operations=(_operation_request(operation_name="code.write"),),
        resources={"changed_files": (str(GOOD_PY),)},
        metadata={
            "validation_policy_name": "documentation_only",
            **_VALIDATION_ROOT_METADATA,
        },
    )

    result = harness.service.execute(request)

    assert result.final_state is IntegrationExecutionState.COMPLETED
    commit_results = [
        v for v in result.validation_results if v["stage"] == "pre_commit"
    ]
    assert commit_results and commit_results[0]["decision"] == "continue"


# ── 14. Findings persisted ──────────────────────────────────────────────────


def test_validation_findings_persisted() -> None:
    harness = _Harness(
        validation_service=AgentValidationAdapter(),
        validation_policy_service=AgentValidationPolicyAdapter(),
    )
    request = _service_request(
        operations=(_operation_request(operation_name="code.write"),),
        resources={"changed_files": (str(BAD_PY),)},
        policy=_policy(require_terminal_validation=False),
        metadata=_VALIDATION_ROOT_METADATA,
    )

    result = harness.service.execute(request)

    findings = [f for v in result.validation_results for f in v["findings"]]
    assert findings
    assert all("finding_id" in f for f in findings)


# ── 15. Cancellation propagates through new stages ──────────────────────────


def test_cancellation_propagates_with_cognitive_and_planning() -> None:
    layer = _ScriptedCognitiveLayer()
    planning = _FakePlanningService()
    harness = _Harness(
        cognitive_service=AgentCognitiveService(cognitive_layer=layer),
        planning_service=planning,
    )
    request = _service_request(operations=(), metadata={"requires_approval": True})

    paused = harness.service.execute(request)
    assert paused.final_state is IntegrationExecutionState.WAITING_APPROVAL

    cancelled = harness.service.cancel("exec-1", reason="user requested")

    assert cancelled.final_state is IntegrationExecutionState.CANCELLED
    assert layer.calls == []
    assert planning.plan_calls == []


# ── 16. Correlation/causation preserved ─────────────────────────────────────


def test_correlation_causation_preserved_across_services() -> None:
    layer = _ScriptedCognitiveLayer()
    planning = _FakePlanningService()
    harness = _Harness(
        cognitive_service=AgentCognitiveService(cognitive_layer=layer),
        planning_service=planning,
    )
    request = _service_request(
        operations=(), correlation_id="corr-xyz", causation_id="cause-xyz"
    )

    harness.service.execute(request)

    cognitive_call = layer.calls[0]
    assert cognitive_call.metadata["correlation_id"] == "corr-xyz"
    assert cognitive_call.metadata["causation_id"] == "cause-xyz"
    planning_call = planning.plan_calls[0]
    assert planning_call.metadata["correlation_id"] == "corr-xyz"
    assert planning_call.metadata["causation_id"] == "cause-xyz"


# ── 17. Idempotency with Cognitive/Planner/Validation ───────────────────────


def test_idempotent_execute_does_not_reinvoke_services() -> None:
    layer = _ScriptedCognitiveLayer()
    planning = _FakePlanningService()
    harness = _Harness(
        cognitive_service=AgentCognitiveService(cognitive_layer=layer),
        planning_service=planning,
        validation_service=AgentValidationAdapter(),
        validation_policy_service=AgentValidationPolicyAdapter(),
    )
    request = _service_request(operations=())

    first = harness.service.execute(request)
    second = harness.service.execute(request)

    assert first == second
    assert len(layer.calls) == 1
    assert len(planning.plan_calls) == 1


# ── 18. Concurrent execute does not duplicate side effects ─────────────────


def test_concurrent_execute_does_not_duplicate_side_effects() -> None:
    layer = _ScriptedCognitiveLayer()
    planning = _FakePlanningService()
    harness = _Harness(
        cognitive_service=AgentCognitiveService(cognitive_layer=layer),
        planning_service=planning,
    )
    request = _service_request(operations=())
    barrier = threading.Barrier(4)

    def _run() -> object:
        barrier.wait(timeout=5)
        return harness.service.execute(request)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: _run(), range(4)))

    assert all(r.final_state is IntegrationExecutionState.COMPLETED for r in results)
    assert len(layer.calls) == 1
    assert len(planning.plan_calls) == 1


# ── 19/20/21. Failures are visible, not swallowed ───────────────────────────


def test_cognitive_failure_is_visible() -> None:
    layer = _ScriptedCognitiveLayer()
    layer.raise_for["corr-cog-fail"] = CognitiveAdapterExecutionError("boom")
    harness = _Harness(cognitive_service=AgentCognitiveService(cognitive_layer=layer))
    request = _service_request(
        correlation_id="corr-cog-fail",
        policy=_policy(metadata={"require_cognitive": True}),
    )

    with pytest.raises(CognitiveAdapterExecutionError):
        harness.service.execute(request)


def test_planner_failure_is_visible() -> None:
    harness = _Harness(
        planning_service=_RaisingPlanningService(RuntimeError("planner exploded"))
    )
    request = _service_request(operations=())

    with pytest.raises(RuntimeError, match="planner exploded"):
        harness.service.execute(request)


def test_validation_failure_is_visible() -> None:
    harness = _Harness(
        validation_service=_RaisingValidationService(
            RuntimeError("validator exploded")
        ),
        validation_policy_service=AgentValidationPolicyAdapter(),
    )

    with pytest.raises(RuntimeError, match="validator exploded"):
        harness.service.execute(_service_request())


# ── 22. No duplicate runtime/planner/cognitive subsystem ───────────────────


def test_no_duplicate_subsystems_created() -> None:
    harness = _Harness(
        cognitive_service=AgentCognitiveService(
            cognitive_layer=_ScriptedCognitiveLayer()
        ),
        planning_service=_FakePlanningService(),
        validation_service=AgentValidationAdapter(),
        validation_policy_service=AgentValidationPolicyAdapter(),
    )

    # Exactly one canonical runtime loop, one store, one registry service —
    # the composition root holds references, it does not construct parallel
    # instances of any of them.
    assert harness.service._runtime_loop is harness.runtime_loop
    assert harness.service._store is harness.store
    assert harness.service._registry_service is harness.registry_service
    assert harness.service._cognitive_service is harness.cognitive_service
    assert harness.service._planning_service is harness.planning_service
    assert harness.service._validation_service is harness.validation_service
    assert not hasattr(harness.service, "_kernel")
    assert not hasattr(harness.service, "_workflow_engine")
