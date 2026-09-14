"""Phase 10.42 — AT-DP-042 connected acceptance test.

DP-042 — Domain-specialized Planner and Workflow Engine integration.

Connects one shared registry/service graph through real canonical or
official in-memory components:

DefaultDomainResolver
→ canonical Domain composition (DefaultDomainComposer)
→ DomainRegistry
→ InMemoryDomainOperationRegistry
→ InMemoryDomainWorkflowRegistry
→ current Domain permission components (authority seam + real gate/resolver)
→ DefaultDomainPlannerWorkflowIntegrator
→ AgentPlanningService
→ DefaultWorkflowPlannerAdapter
→ TaskPlanner
→ AgentWorkflowPlan
→ AgentWorkflowPlanValidator
→ canonical approval / validation nodes
→ Phase 10.41 DomainOperationDispatchAdapter path
→ DefaultDomainOperationOrchestrator
→ DomainOperationExecutionDelegate
→ DomainWorkflowExecutor
→ shared WorkflowEngine
→ canonical replan / completion

Recording probes observe edges only; they never replace canonical behavior.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.agent_runtime.enums import WorkflowPlanStatus
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.operation_execution_contracts import AgentOperationRequest
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.agent_runtime.workflow_planner_adapter import (
    AgentPlanningService,
    DefaultWorkflowPlannerAdapter,
)
from cmm.agent_runtime.workflow_planner_contracts import (
    AgentPlanningRequest,
    AgentWorkflowPlan,
)
from cmm.agent_runtime.workflow_planner_store import InMemoryWorkflowPlanStore
from cmm.domains.agent_runtime_integration import DomainOperationDispatchAdapter
from cmm.domains.composer import DefaultDomainComposer
from cmm.domains.contracts import DomainDefinition, DomainDependency, DomainManifestId
from cmm.domains.enums import (
    DomainCompositionStatus,
    DomainKind,
    DomainOperationType,
    DomainResolutionStatus,
)
from cmm.domains.errors import DomainError
from cmm.domains.identifiers import DomainId
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.operation_execution import (
    DefaultDomainOperationOrchestrator,
    DomainOperationExecutionDelegate,
)
from cmm.agent_runtime.enums import (
    AgentValidationDecision,
    AgentValidationStage,
    AgentValidationStatus,
)
from cmm.agent_runtime.validation_execution_adapter import AgentValidationAdapter
from cmm.agent_runtime.validation_integration_contracts import AgentValidationResult
from cmm.domains.validation_integration import (
    resolve_domain_operation_validation_requirements,
)
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.permission_contracts import DomainPermissionPolicy
from cmm.domains.permission_gate import DomainPermissionGate
from cmm.domains.permission_registry import DomainPermissionRegistry
from cmm.domains.permission_resolution import DomainPermissionResolver
from cmm.domains.planner_workflow_integration import (
    DefaultDomainPlannerWorkflowIntegrator,
)
from cmm.domains.planner_workflow_integration_contracts import (
    DomainPlannerWorkflowIntegrationRequest,
)
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolution_contracts import (
    DomainResolutionContext,
    DomainResolutionResource,
)
from cmm.domains.resolver import DefaultDomainResolver
from cmm.domains.resolver_contracts import DomainScoringPolicy
from cmm.domains.workflow_contracts import (
    DomainWorkflowContext,
    DomainWorkflowDefinition,
    DomainWorkflowResult,
)
from cmm.domains.workflow_execution import DomainWorkflowExecutor
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.planner.task_planner import TaskPlanner
from cmm.workflows.contracts import WorkflowNode
from cmm.workflows.engine import NodeExecution
from cmm.workflows.enums import WorkflowRunStatus

ROOT = Path(__file__).resolve().parents[2]
ALLOWED_OPERATIONS = (
    "python.find_symbol",
    "python.list_imports",
    "python.describe_module",
    "filesystem.read_file",
    "filesystem.exists",
)


class _StubReasoner:
    def locate_feature(self, query):
        return []

    def impact_analysis(self, feature_name):
        return None

    def explain_dependencies(self, feature_name):
        return None


class _CountingResolver(DomainPermissionResolver):
    """Real permission resolver that only counts resolutions."""

    def __init__(self, registry):
        super().__init__(registry)
        self.resolve_calls = 0

    def resolve(self, request, **kwargs):
        self.resolve_calls += 1
        return super().resolve(request, **kwargs)


def _definition(slug, **kwargs):
    defaults = {
        "id": DomainId.from_str(f"domain:{slug}"),
        "name": slug,
        "display_name": slug.title(),
        "version": "1.0.0",
        "kind": DomainKind.CORE,
        "description": f"Acceptance domain {slug}",
        "manifest_id": DomainManifestId(slug=slug, version="1.0.0"),
        "enabled": True,
    }
    defaults.update(kwargs)
    return DomainDefinition(**defaults)


def _operation(operation_id, domain_id, **kwargs):
    values = {
        "operation_id": operation_id,
        "domain_id": domain_id,
        "version": "1.0.0",
        "name": operation_id,
        "description": f"Acceptance operation {operation_id}",
        "operation_type": DomainOperationType.READ,
        # Reversible so the connected positive chain traverses the current
        # permission gate with ALLOW (irreversible operations canonically
        # require an approval grant first).
        "reversible": True,
    }
    values.update(kwargs)
    return DomainOperationDefinition(**values)


def _counting_impl(operation_calls, operation_id: str, definition):
    class _CountingImpl:
        def __init__(self):
            self.definition = definition

        def execute(self, request):
            operation_calls[operation_id] += 1
            return {"ok": True}

    return _CountingImpl()


def _counting_project_impl(operation_calls, operation_id: str, definition):
    """Counting implementation returning schema-valid Project operation output."""

    class _CountingProjectImpl:
        def __init__(self):
            self.definition = definition

        def execute(self, request):
            operation_calls[operation_id] += 1
            return {
                "output": {
                    "status": "completed",
                    "result": {"operation": operation_id},
                }
            }

    return _CountingProjectImpl()


def _workflow(workflow_id, domain_id, **kwargs):
    values = {
        "workflow_id": workflow_id,
        "domain_id": domain_id,
        "version": "1.0.0",
        "name": workflow_id,
        "nodes": (
            WorkflowNode(
                "start",
                "execute_operation",
                "Start",
                operation_id="python.find_symbol",
                operation_version="1.0.0",
            ),
            WorkflowNode("finish", "complete", "Finish", dependencies=("start",)),
        ),
    }
    values.update(kwargs)
    return DomainWorkflowDefinition(
        values.pop("workflow_id"),
        values.pop("domain_id"),
        values.pop("version"),
        values.pop("name"),
        **values,
    )


@dataclass
class _AcceptanceGraph:
    """One shared registry/service graph for the whole acceptance."""

    domain_registry: DomainRegistry
    operation_registry: InMemoryDomainOperationRegistry
    workflow_registry: InMemoryDomainWorkflowRegistry
    permission_registry: DomainPermissionRegistry
    authority: dict[str, set[str]] = field(default_factory=dict)
    operation_calls: dict[str, int] = field(default_factory=dict)
    engine_calls: list[str] = field(default_factory=list)
    store: InMemoryWorkflowPlanStore = field(default_factory=InMemoryWorkflowPlanStore)
    service: AgentPlanningService | None = None
    executor: DomainWorkflowExecutor | None = None


def _build_graph() -> _AcceptanceGraph:
    graph = _AcceptanceGraph(
        domain_registry=DomainRegistry(),
        operation_registry=InMemoryDomainOperationRegistry(
            InMemoryAgentOperationRegistry()
        ),
        workflow_registry=InMemoryDomainWorkflowRegistry(),
        permission_registry=DomainPermissionRegistry(),
        authority={
            "permissions": {"python.use", "filesystem.use"},
            "prohibited": {"filesystem.delete_file"},
            "approvals": set(),
        },
    )
    graph.domain_registry.register(
        _definition(
            "python",
            operations=(
                "python.find_symbol",
                "python.list_imports",
                "python.describe_module",
            ),
            workflows=(
                "python.review",
                "python.simple",
                "python.guarded",
                "python.parent",
                "python.child",
            ),
        )
    )
    graph.domain_registry.register(
        _definition(
            "filesystem",
            operations=(
                "filesystem.read_file",
                "filesystem.exists",
                "filesystem.delete_file",
            ),
            workflows=(),
        )
    )
    graph.domain_registry.enable("domain:python")
    graph.domain_registry.enable("domain:filesystem")

    for operation_id in (*ALLOWED_OPERATIONS, "filesystem.delete_file"):
        domain_id = f"domain:{operation_id.split('.')[0]}"
        graph.operation_calls[operation_id] = 0
        definition = _operation(operation_id, domain_id)
        graph.operation_registry.register(
            definition,
            _counting_impl(graph.operation_calls, operation_id, definition),
        )

    graph.workflow_registry.register(
        _workflow(
            "python.review",
            "domain:python",
            required_permissions=("python.use",),
            approval_gates=("review-board",),
        )
    )
    graph.workflow_registry.register(_workflow("python.simple", "domain:python"))
    graph.workflow_registry.register(
        _workflow(
            "python.guarded",
            "domain:python",
            required_permissions=("python.use",),
        )
    )
    child = DomainWorkflowDefinition(
        "python.child",
        "domain:python",
        "1.0.0",
        "Child",
        nodes=(WorkflowNode("done", "complete", "Done"),),
    )
    parent = DomainWorkflowDefinition(
        "python.parent",
        "domain:python",
        "1.0.0",
        "Parent",
        nodes=(
            WorkflowNode(
                "child",
                "invoke_subworkflow",
                "Child",
                subworkflow_id="python.child",
                subworkflow_version="1.0.0",
            ),
            WorkflowNode("finish", "complete", "Finish", dependencies=("child",)),
        ),
    )
    graph.workflow_registry.register(child)
    graph.workflow_registry.register(parent)

    graph.permission_registry.register(
        DomainPermissionPolicy(
            policy_id="acc-python",
            domain_id="domain:python",
            version="1.0.0",
            allowed_capabilities=(
                PermissionCapability.OPERATION_EXECUTE,
                PermissionCapability.WORKFLOW_EXECUTE,
            ),
            allowed_operations=tuple(
                op for op in ALLOWED_OPERATIONS if op.startswith("python.")
            ),
            prohibited_operations=(),
        )
    )
    graph.permission_registry.register(
        DomainPermissionPolicy(
            policy_id="acc-filesystem",
            domain_id="domain:filesystem",
            version="1.0.0",
            allowed_capabilities=(
                PermissionCapability.OPERATION_EXECUTE,
                PermissionCapability.WORKFLOW_EXECUTE,
            ),
            allowed_operations=("filesystem.read_file", "filesystem.exists"),
            prohibited_operations=("filesystem.delete_file",),
        )
    )

    adapter = DefaultWorkflowPlannerAdapter(
        planner=TaskPlanner(reasoner=_StubReasoner()),
        plan_store=graph.store,
    )
    graph.service = AgentPlanningService(adapter)

    def _engine_adapter(node, run):
        graph.engine_calls.append(node.node_id)
        return NodeExecution.complete({"node": node.node_id})

    graph.executor = DomainWorkflowExecutor(
        id_factory=lambda: f"acc-exec-{len(graph.engine_calls)}",
        operation_adapter=_engine_adapter,
        workflow_definitions={("python.child", "1.0.0"): child},
    )
    return graph


def _make_integrator(graph: _AcceptanceGraph) -> DefaultDomainPlannerWorkflowIntegrator:
    return DefaultDomainPlannerWorkflowIntegrator(
        resolver=DefaultDomainResolver(
            scoring_policy=DomainScoringPolicy(
                max_supporting_domains=1, supporting_margin=100.0
            )
        ),
        composer=DefaultDomainComposer(),
        domain_registry=graph.domain_registry,
        workflow_registry=graph.workflow_registry,
        planning_service=graph.service,
        workflow_executor=graph.executor,
        operation_definition_provider=lambda op: (
            graph.operation_registry.resolve_active(op, required=False)
        ),
        operation_availability=lambda op_id, domain_id: (
            graph.operation_registry.resolve_active(op_id, required=False) is not None
        ),
        permission_ids_provider=lambda composition: tuple(
            sorted(graph.authority["permissions"])
        ),
        prohibited_operation_ids_provider=lambda composition: tuple(
            sorted(graph.authority["prohibited"])
        ),
        approval_ids_provider=lambda composition: tuple(
            sorted(graph.authority["approvals"])
        ),
        validation_ids_provider=lambda composition: ("python.schema",),
        authority_reference_ids_provider=lambda composition: ("authority:v1",),
        capabilities_provider=lambda composition: (
            "validation",
            "rollback",
            "transaction",
            "external",
        ),
        available_validation_policy_ids_provider=lambda composition: ("python.schema",),
        available_rollback_policy_ids_provider=lambda composition: (),
    )


def _resolution_context(**overrides: Any) -> DomainResolutionContext:
    values: dict[str, Any] = {
        "id": "ctx-042-acc",
        "user_input": "Python inspection with filesystem reading",
        "goal_id": "goal-042-acc",
        "actor": "actor-042",
        "available_domains": (DomainId(slug="python"), DomainId(slug="filesystem")),
        "authorized_domains": (DomainId(slug="python"), DomainId(slug="filesystem")),
        "explicit_domains": (DomainId(slug="python"),),
        "resources": (
            DomainResolutionResource(
                id="r-py",
                resource_type="document",
                source="user",
                domain_ids=(DomainId(slug="python"),),
            ),
            DomainResolutionResource(
                id="r-fs",
                resource_type="document",
                source="user",
                domain_ids=(DomainId(slug="filesystem"),),
            ),
        ),
    }
    values.update(overrides)
    return DomainResolutionContext(**values)


def _planning_request(**overrides: Any) -> AgentPlanningRequest:
    values: dict[str, Any] = {
        "id": "req-042-acc",
        "goal_id": "goal-042-acc",
        "agent_run_id": "run-042-acc",
        "actor_id": "actor-042",
        "objective": "Inspect python symbols and read filesystem files",
        "allowed_operations": list(ALLOWED_OPERATIONS),
        "permissions": ["python.use", "filesystem.use"],
    }
    values.update(overrides)
    return AgentPlanningRequest(**values)


def _integration_request(
    graph: _AcceptanceGraph, **overrides: Any
) -> DomainPlannerWorkflowIntegrationRequest:
    values: dict[str, Any] = {
        "request_id": "int-req-042-acc",
        "resolution_context": _resolution_context(),
        "planning_request": _planning_request(),
        "metadata": {"requested_workflow_ids": ["python.review"]},
    }
    values.update(overrides)
    return DomainPlannerWorkflowIntegrationRequest(**values)


def _dispatch_adapter(
    graph: _AcceptanceGraph,
    permission_gate=None,
    transaction_manager=None,
    rollback_executor=None,
    validation_adapter=None,
    operation_validation_provider=None,
) -> DomainOperationDispatchAdapter:
    common = graph.operation_registry.common_registry
    execution_adapter = AgentExecutionAdapter(
        registry=common,
        execution_delegate=DomainOperationExecutionDelegate(graph.operation_registry),
        validation_adapter=validation_adapter,
    )
    orchestrator = DefaultDomainOperationOrchestrator(
        graph.operation_registry,
        execution_adapter,
        permission_gate=permission_gate,
        transaction_manager=transaction_manager,
        rollback_executor=rollback_executor,
        operation_validation_provider=operation_validation_provider,
    )
    return DomainOperationDispatchAdapter(orchestrator)


def _dispatch_request(
    operation_name: str, capabilities: tuple[str, ...] = ("execute",)
) -> AgentOperationRequest:
    return AgentOperationRequest(
        id=f"op-req-{operation_name}",
        agent_run_id="run-042-acc",
        workflow_id="workflow-042-acc",
        task_id="task-042-acc",
        operation_name=operation_name,
        operation_version="1.0.0",
        idempotency_key=f"idem-{operation_name}",
        parameters={},
        permissions=(),
        created_at=datetime.now(timezone.utc).isoformat(),
        metadata={
            "domain_intelligence": {
                "primary_domain_id": "domain:python"
                if operation_name.startswith("python.")
                else "domain:filesystem",
                "supporting_domain_ids": (),
                "actor_id": "actor-042",
                "goal_id": "goal-042-acc",
                "available_resources": (),
                "denied_permissions": (),
                "capabilities": capabilities,
            }
        },
    )


def _workflow_context(**overrides: Any):

    values: dict[str, Any] = {
        "primary_domain_id": "domain:python",
        "available_operations": frozenset(
            {*ALLOWED_OPERATIONS, "filesystem.delete_file"}
        ),
    }
    values.update(overrides)
    return DomainWorkflowContext(**values)


# ── Positive connected path (one coherent graph) ────────────────────────────


def test_at_dp042_connected_planning_operation_workflow_chain() -> None:
    """AT-DP-042 connected chain on one coherent registry/service graph.

    DefaultDomainResolver → canonical composition → DomainRegistry →
    InMemoryDomainOperationRegistry → InMemoryDomainWorkflowRegistry → current
    permission components → DefaultDomainPlannerWorkflowIntegrator →
    AgentPlanningService → DefaultWorkflowPlannerAdapter → TaskPlanner →
    AgentWorkflowPlan → AgentWorkflowPlanValidator → canonical approval /
    validation nodes → exact planned operation → Phase 10.41 dispatch →
    DefaultDomainOperationOrchestrator → real current DomainPermissionGate →
    DomainOperationExecutionDelegate → registered implementation → exact
    selected workflow → DomainWorkflowExecutor → shared WorkflowEngine →
    canonical replan.
    """
    from dataclasses import replace

    from cmm.agent_runtime.enums import WorkflowPlanChangeReason

    graph = _build_graph()
    integrator = _make_integrator(graph)

    # Planning through the canonical stack on the shared graph.
    request = _integration_request(
        graph, metadata={"requested_workflow_ids": ["python.simple"]}
    )
    result = integrator.integrate(request)

    assert result.blocked is False
    assert result.reason_codes == ()
    assert result.resolution.status is DomainResolutionStatus.RESOLVED
    assert str(result.resolution.primary_domain) == "domain:python"
    assert result.composition.status is DomainCompositionStatus.COMPOSED
    assert type(result.plan) is AgentWorkflowPlan
    assert result.plan.status is WorkflowPlanStatus.VALID
    assert graph.store.get(result.plan.id) is result.plan
    assert result.prepared_planning_request.allowed_operations == list(
        ALLOWED_OPERATIONS
    )
    assert "filesystem.delete_file" in (
        result.prepared_planning_request.prohibited_operations
    )
    # V7 MAJOR-09: the selected python.simple workflow carries no approval
    # gate, and gates of available-but-unselected workflows (python.review's
    # review-board) must not leak into the plan-wide requirements.
    assert result.prepared_planning_request.required_approvals == []
    assert result.prepared_planning_request.required_validations == ["python.schema"]
    assert result.plan.metadata["workflow_references"] == ["python.simple"]
    assert result.selected_domain_workflow_ids == ("python.simple",)
    assert len(result.plan.approval_nodes) == 0
    assert len(result.plan.validation_nodes) > 0
    assert all(node.required and node.blocking for node in result.plan.validation_nodes)
    validation = graph.service.validate_plan(
        result.plan, request=result.prepared_planning_request
    )
    assert validation.is_valid

    # The exact planned operation executes via Phase 10.41 dispatch behind a
    # real current DomainPermissionGate. The reversible operation carries the
    # canonical transaction capability, so availability passes and the gate
    # decides ALLOW through the real permission resolver.
    from cmm.agent_runtime.checkpoint_manager import CheckpointManager
    from cmm.agent_runtime.transaction_manager import TransactionManager

    planned_operation = result.plan.operations[0].operation_name
    assert planned_operation in ALLOWED_OPERATIONS
    assert planned_operation in result.prepared_planning_request.allowed_operations
    resolver = _CountingResolver(graph.permission_registry)
    dispatch = _dispatch_adapter(
        graph,
        permission_gate=DomainPermissionGate(resolver),
        transaction_manager=TransactionManager(CheckpointManager()),
    )
    outcome = dispatch(
        _dispatch_request(planned_operation, capabilities=("execute", "transaction"))
    )

    assert outcome["success"] is True
    assert graph.operation_calls[planned_operation] == 1
    assert resolver.resolve_calls > 0, "current DomainPermissionGate must decide"

    # The exact selected workflow from the same result executes through the
    # canonical executor and the shared WorkflowEngine.
    workflow_id = result.plan.metadata["workflow_references"][0]
    assert workflow_id == result.selected_domain_workflow_ids[0]
    engine_before = list(graph.engine_calls)
    workflow_result = integrator.execute_workflow_reference(
        workflow_id=workflow_id,
        context=_workflow_context(),
        inputs={},
    )

    assert type(workflow_result) is DomainWorkflowResult
    assert workflow_result.status is WorkflowRunStatus.COMPLETED
    assert len(graph.engine_calls) > len(engine_before)

    # Material authority change on the same graph drives canonical replan.
    graph.authority["approvals"].add("change-board")
    replanned = integrator.replan(
        replace(request, current_plan=result.plan),
        reason=WorkflowPlanChangeReason.PERMISSION_CHANGED,
        reason_details="domain now requires change-board approval",
    )

    assert replanned.blocked is False
    assert replanned.plan.version == 2
    assert replanned.plan.previous_version_id == result.plan.id
    assert graph.store.get(result.plan.id).status is WorkflowPlanStatus.SUPERSEDED
    assert "change-board" in replanned.prepared_planning_request.required_approvals


# ── Adversarial cases ─────────────────────────────────────────────────────


def test_at_dp042_nonexistent_operation_neither_exposed_nor_executed() -> None:
    graph = _build_graph()
    integrator = _make_integrator(graph)
    result = integrator.integrate(_integration_request(graph, metadata={}))

    assert "python.nope" not in result.capability_view.available_operation_ids
    assert "python.nope" not in result.prepared_planning_request.allowed_operations
    assert all(op.operation_name != "python.nope" for op in result.plan.operations)

    dispatch = _dispatch_adapter(graph)
    with pytest.raises(DomainError):
        dispatch(_dispatch_request("python.nope"))
    assert all(calls == 0 for calls in graph.operation_calls.values())


def test_at_dp042_prohibited_operation_never_executes() -> None:
    graph = _build_graph()
    integrator = _make_integrator(graph)
    result = integrator.integrate(_integration_request(graph, metadata={}))

    assert (
        "filesystem.delete_file" not in result.capability_view.available_operation_ids
    )
    assert "filesystem.delete_file" in result.capability_view.prohibited_operation_ids
    assert all(
        op.operation_name != "filesystem.delete_file" for op in result.plan.operations
    )

    resolver = _CountingResolver(graph.permission_registry)
    gate = DomainPermissionGate(resolver)
    from cmm.agent_runtime.checkpoint_manager import CheckpointManager
    from cmm.agent_runtime.transaction_manager import TransactionManager

    dispatch = _dispatch_adapter(
        graph,
        permission_gate=gate,
        transaction_manager=TransactionManager(CheckpointManager()),
    )
    try:
        outcome = dispatch(
            _dispatch_request(
                "filesystem.delete_file", capabilities=("execute", "transaction")
            )
        )
    except DomainError:
        outcome = None
    assert graph.operation_calls["filesystem.delete_file"] == 0
    if outcome is not None:
        assert outcome["success"] is False
    assert resolver.resolve_calls > 0, "current DomainPermissionGate must decide"


def test_at_dp042_unavailable_workflow_never_starts() -> None:
    from cmm.workflows.errors import WorkflowRegistryError

    graph = _build_graph()
    integrator = _make_integrator(graph)

    before = list(graph.engine_calls)
    with pytest.raises(WorkflowRegistryError):
        integrator.execute_workflow_reference(
            workflow_id="python.missing",
            context=_workflow_context(),
            inputs={},
        )
    assert graph.engine_calls == before


def test_at_dp042_permission_downgrade_blocks_stale_execution() -> None:
    graph = _build_graph()
    integrator = _make_integrator(graph)
    planned = integrator.integrate(_integration_request(graph))
    assert planned.blocked is False
    assert planned.selected_domain_workflow_ids == ("python.review",)

    # Authority downgrade after planning: python.use is revoked.
    graph.authority["permissions"].discard("python.use")

    before = list(graph.engine_calls)
    with pytest.raises(ValueError, match="unavailable"):
        integrator.execute_workflow_reference(
            workflow_id="python.review",
            context=_workflow_context(available_permissions=frozenset()),
            inputs={},
        )
    assert graph.engine_calls == before

    # Fresh planning under current authority no longer exposes the workflow.
    fresh = integrator.integrate(_integration_request(graph))
    assert fresh.blocked is True
    assert fresh.plan is None
    assert "domain_workflow_unavailable" in fresh.reason_codes


def test_at_dp042_approval_required_cannot_be_bypassed() -> None:
    graph = _build_graph()
    integrator = _make_integrator(graph)

    # No approval granted: the gated workflow cannot execute.
    before = list(graph.engine_calls)
    with pytest.raises(ValueError, match="unavailable"):
        integrator.execute_workflow_reference(
            workflow_id="python.review",
            context=_workflow_context(),
            inputs={},
        )
    assert graph.engine_calls == before

    # A scoped approval satisfies the gate but never expands permission:
    # python.use is still missing, so execution stays blocked.
    from cmm.domains.workflow_resolution import resolve_domain_workflow

    definition = graph.workflow_registry.resolve_active("python.review")
    resolution = resolve_domain_workflow(
        definition,
        _workflow_context(approved_gates=frozenset({"review-board"})),
    )
    assert resolution.status.value != "available"
    assert "permission.missing" in resolution.reasons


def test_at_dp042_validation_obligation_cannot_disappear() -> None:
    graph = _build_graph()
    integrator = _make_integrator(graph)

    result = integrator.integrate(_integration_request(graph, metadata={}))

    assert result.blocked is False
    assert result.prepared_planning_request.required_validations == ["python.schema"]
    assert len(result.plan.validation_nodes) > 0
    assert all(node.required for node in result.plan.validation_nodes)


def test_at_dp042_cross_domain_conflict_fails_closed() -> None:
    """AT-DP-042: blocking composition conflicts never silently union authority."""
    from cmm.domains.composer import DefaultDomainComposer

    python_dep = _definition(
        "python",
        operations=(),
        workflows=(),
        dependencies=(DomainDependency(domain_id="domain:ghost"),),
    )
    context = DomainResolutionContext(
        id="ctx-042-conflict",
        user_input="Python work with ghost support",
        available_domains=(DomainId(slug="python"),),
        authorized_domains=(DomainId(slug="python"),),
        explicit_domains=(DomainId(slug="python"),),
        resources=(
            DomainResolutionResource(
                id="r-py",
                resource_type="document",
                source="user",
                domain_ids=(DomainId(slug="python"),),
            ),
        ),
    )
    resolved = DefaultDomainResolver().resolve(context)
    assert resolved.status is DomainResolutionStatus.RESOLVED
    # The required ghost dependency is absent from the effective composition.
    composition = DefaultDomainComposer().compose(resolved, [python_dep])

    assert composition.status is DomainCompositionStatus.BLOCKED
    blocking = [
        conflict
        for conflict in composition.conflicts
        if conflict.blocking and not conflict.resolved
    ]
    assert blocking, "blocking conflict must propagate"
    assert "ghost.read" not in [item.identifier for item in composition.operations], (
        "no silent authority union"
    )


def test_at_dp042_subworkflow_reuse_through_shared_engine() -> None:
    graph = _build_graph()
    integrator = _make_integrator(graph)

    result = integrator.execute_workflow_reference(
        workflow_id="python.parent",
        context=_workflow_context(available_permissions=frozenset()),
        inputs={},
    )

    assert result.status is WorkflowRunStatus.COMPLETED
    assert graph.engine_calls, "subworkflow must reuse the shared WorkflowEngine"
    assert not any("store" in attr for attr in vars(integrator))


def test_at_dp042_canonical_replan_supersedes() -> None:
    from dataclasses import replace

    from cmm.agent_runtime.enums import WorkflowPlanChangeReason

    graph = _build_graph()
    integrator = _make_integrator(graph)
    first = integrator.integrate(_integration_request(graph, metadata={}))
    assert first.blocked is False

    graph.authority["approvals"].add("change-board")
    result = integrator.replan(
        replace(_integration_request(graph, metadata={}), current_plan=first.plan),
        reason=WorkflowPlanChangeReason.PERMISSION_CHANGED,
        reason_details="domain now requires change-board approval",
    )

    assert result.blocked is False
    assert result.plan.version == 2
    assert result.plan.previous_version_id == first.plan.id
    assert graph.store.get(first.plan.id).status is WorkflowPlanStatus.SUPERSEDED
    assert "change-board" in result.prepared_planning_request.required_approvals


# ── Architecture inside acceptance ────────────────────────────────────────


def _imports_prefix(root: Path, prefix: str) -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == prefix or alias.name.startswith(prefix + "."):
                        found.append((path, f"import {alias.name}"))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == prefix or module.startswith(prefix + "."):
                    found.append((path, f"from {module} import ..."))
    return found


def test_at_dp042_reverse_imports_are_zero() -> None:
    assert _imports_prefix(ROOT / "cmm" / "agent_runtime", "cmm.domains") == []
    assert _imports_prefix(ROOT / "cmm" / "workflows", "cmm.domains") == []


def test_at_dp042_no_parallel_owners() -> None:
    graph = _build_graph()
    integrator = _make_integrator(graph)
    for attr in vars(integrator):
        lowered = attr.lower()
        assert "store" not in lowered, attr
        assert "engine" not in lowered, attr
    assert graph.service.get_plan is not None


# ── Real production Domain Pack acceptance (Phase 10.42 V3) ─────────────────


def _build_project_graph() -> _AcceptanceGraph:
    """Shared graph wired to the real production ``domain:project`` pack."""
    from cmm.domains.project.definition import build_project_domain_definition
    from cmm.domains.project.operations import build_project_operation_definitions

    graph = _AcceptanceGraph(
        domain_registry=DomainRegistry(),
        operation_registry=InMemoryDomainOperationRegistry(
            InMemoryAgentOperationRegistry()
        ),
        workflow_registry=InMemoryDomainWorkflowRegistry(),
        permission_registry=DomainPermissionRegistry(),
        authority={
            "permissions": set(),
            "prohibited": set(),
            "approvals": set(),
        },
    )
    graph.domain_registry.register(build_project_domain_definition())
    graph.domain_registry.enable("domain:project")
    definitions = {
        definition.operation_id: definition
        for definition in build_project_operation_definitions()
    }
    for operation_id, definition in definitions.items():
        graph.operation_calls[operation_id] = 0
        graph.operation_registry.register(
            definition,
            _counting_project_impl(graph.operation_calls, operation_id, definition),
        )

    from cmm.domains.project.workflows import build_project_workflow_definitions

    for workflow in build_project_workflow_definitions():
        graph.workflow_registry.register(workflow)

    adapter = DefaultWorkflowPlannerAdapter(
        planner=TaskPlanner(reasoner=_StubReasoner()),
        plan_store=graph.store,
    )
    graph.service = AgentPlanningService(adapter)

    def _engine_adapter(node, run):
        graph.engine_calls.append(node.node_id)
        return NodeExecution.complete({"node": node.node_id})

    graph.executor = DomainWorkflowExecutor(
        id_factory=lambda: f"acc-project-exec-{len(graph.engine_calls)}",
        operation_adapter=_engine_adapter,
    )
    graph.authority["definitions"] = definitions
    return graph


def _make_project_integrator(
    graph: _AcceptanceGraph, dependencies=None
) -> DefaultDomainPlannerWorkflowIntegrator:
    definitions = graph.authority["definitions"]
    return DefaultDomainPlannerWorkflowIntegrator(
        resolver=DefaultDomainResolver(
            scoring_policy=DomainScoringPolicy(
                max_supporting_domains=0, supporting_margin=100.0
            )
        ),
        composer=DefaultDomainComposer(),
        domain_registry=graph.domain_registry,
        workflow_registry=graph.workflow_registry,
        planning_service=graph.service,
        workflow_executor=graph.executor,
        operation_availability=lambda op_id, domain_id: (
            graph.operation_registry.resolve_active(op_id, required=False) is not None
        ),
        permission_ids_provider=lambda composition: tuple(
            sorted(graph.authority["permissions"])
        ),
        prohibited_operation_ids_provider=lambda composition: (),
        approval_ids_provider=lambda composition: (),
        validation_ids_provider=lambda composition: (),
        authority_reference_ids_provider=lambda composition: ("authority:v1",),
        operation_definition_provider=lambda operation_id: definitions.get(
            operation_id
        ),
        operation_dependency_provider=lambda operation_id: (
            dependencies.get(operation_id, ()) if dependencies is not None else ()
        ),
    )


def _project_integration_request() -> DomainPlannerWorkflowIntegrationRequest:
    return DomainPlannerWorkflowIntegrationRequest(
        request_id="int-req-042-acc-project",
        resolution_context=DomainResolutionContext(
            id="ctx-042-acc-project",
            user_input="Review project status and plan milestones",
            goal_id="goal-042-acc-project",
            actor="actor-042",
            available_domains=(DomainId(slug="project"),),
            authorized_domains=(DomainId(slug="project"),),
            explicit_domains=(DomainId(slug="project"),),
            resources=(
                DomainResolutionResource(
                    id="r-project",
                    resource_type="document",
                    source="user",
                    domain_ids=(DomainId(slug="project"),),
                ),
            ),
        ),
        planning_request=AgentPlanningRequest(
            id="req-042-acc-project",
            goal_id="goal-042-acc-project",
            agent_run_id="run-042-acc-project",
            actor_id="actor-042",
            objective="Review project status and plan milestones",
        ),
        metadata={},
    )


def _project_dispatch_request(
    graph: _AcceptanceGraph, operation_name: str
) -> AgentOperationRequest:
    definition = graph.authority["definitions"][operation_name]
    return AgentOperationRequest(
        id=f"op-req-{operation_name}",
        agent_run_id="run-042-acc-project",
        workflow_id="workflow-042-acc-project",
        task_id="task-042-acc-project",
        operation_name=operation_name,
        operation_version="1.0.0",
        idempotency_key=f"idem-{operation_name}",
        parameters={},
        permissions=(),
        created_at=datetime.now(timezone.utc).isoformat(),
        metadata={
            "domain_intelligence": {
                "primary_domain_id": "domain:project",
                "supporting_domain_ids": (),
                "actor_id": "actor-042",
                "goal_id": "goal-042-acc-project",
                "available_resources": tuple(definition.required_resources),
                "denied_permissions": (),
                "capabilities": ("execute", "transaction", "rollback", "validation"),
            }
        },
    )


class _RecordingValidationAdapter(AgentValidationAdapter):
    """Real-pipeline adapter that records requirement materialization.

    The DP-042 dispatch path is a planning/projection acceptance, not a
    validation acceptance; this adapter records that the Phase 10.43
    provider materialized non-empty required validation sets and defers
    pass/block evidence to the dedicated Phase 10.43 suites.
    """

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


def test_at_dp042_real_project_pack_operation_planning_chain() -> None:
    """AT-DP-042 (V3): real ``domain:project`` capability → plan → execution.

    Real Domain resolution → real registry capabilities → returned plan uses
    at least one registered ``project.*`` operation → exact operation
    semantics projected → canonical validation passes → operation executes
    through the Phase 10.41 dispatch path.
    """
    from cmm.domains.enums import DomainCompositionStatus as CompositionStatus

    graph = _build_project_graph()
    integrator = _make_project_integrator(graph)

    result = integrator.integrate(_project_integration_request())

    assert result.blocked is False
    assert result.reason_codes == ()
    assert result.resolution.status is DomainResolutionStatus.RESOLVED
    assert str(result.resolution.primary_domain) == "domain:project"
    assert result.composition.status is CompositionStatus.COMPOSED
    assert type(result.plan) is AgentWorkflowPlan
    assert result.plan.status is WorkflowPlanStatus.VALID

    registered = set(graph.authority["definitions"])
    planned = [op.operation_name for op in result.plan.operations]
    assert planned
    assert set(planned) & registered, "plan must use a registered Domain capability"
    assert not any(name.startswith("python.") for name in planned)
    assert not any(name.startswith("filesystem.") for name in planned)

    # Exact operation semantics are projected onto the selected operations:
    # each planned project operation carries its canonical validation ID,
    # traceable on both the operation and its validation node.
    for operation in result.plan.operations:
        assert operation.required_validations == [
            f"validation.{operation.operation_name}"
        ]
    validation_ids = {
        validation_id
        for node in result.plan.validation_nodes
        for validation_id in node.metadata.get("validation_requirement_ids", [])
    }
    assert {f"validation.{name}" for name in planned} <= validation_ids

    validation = graph.service.validate_plan(
        result.plan, request=result.prepared_planning_request
    )
    assert validation.is_valid

    # The exact planned operation executes through the Phase 10.41 path.
    # Project operations are reversible with rollback policies, so the
    # orchestrator is wired with the canonical transaction manager and a
    # recording rollback executor (idle on the success path).
    from cmm.agent_runtime.checkpoint_manager import CheckpointManager
    from cmm.agent_runtime.transaction_manager import TransactionManager
    from cmm.agent_runtime.validation_execution_adapter import (
        AgentValidationAdapter,
    )

    planned_operation = result.plan.operations[0].operation_name
    rollback_calls: list[tuple[str, str | None]] = []

    class _RecordingRollbackExecutor:
        def rollback(self, transaction_id, checkpoint_id=None):
            rollback_calls.append((transaction_id, checkpoint_id))
            return {"rolled_back": True}

    recording_adapter = _RecordingValidationAdapter()
    dispatch = _dispatch_adapter(
        graph,
        transaction_manager=TransactionManager(CheckpointManager()),
        rollback_executor=_RecordingRollbackExecutor(),
        validation_adapter=recording_adapter,
        operation_validation_provider=(
            resolve_domain_operation_validation_requirements
        ),
    )
    outcome = dispatch(_project_dispatch_request(graph, planned_operation))

    assert outcome["success"] is True
    assert graph.operation_calls[planned_operation] == 1
    assert rollback_calls == []
    # Phase 10.43 fail-closed wiring: the dispatched validation-mandated
    # Project operation materialized real runtime validation requirements
    # through the canonical provider (recorded on both validation stages).
    assert recording_adapter.seen
    for seen_request in recording_adapter.seen:
        assert seen_request.requirements
        assert all(
            requirement.required for requirement in seen_request.requirements
        )
    assert outcome["success"] is True
    assert graph.operation_calls[planned_operation] == 1


def test_at_dp042_real_project_pack_missing_dependency_fails_closed() -> None:
    """AT-DP-042 (V3): a missing required ``project.*`` dependency blocks."""
    graph = _build_project_graph()
    integrator = _make_project_integrator(
        graph,
        dependencies={"project.compare_code_documentation": ("project.nope",)},
    )

    result = integrator.integrate(_project_integration_request())

    assert result.blocked is True
    assert "domain_unresolved_operation_dependency" in result.reason_codes
    assert result.plan is not None
    assert not result.plan.validation.is_valid
    assert graph.operation_calls["project.compare_code_documentation"] == 0


def test_at_dp042_real_project_modify_code_without_permission_blocked() -> None:
    """AT-DP-042 (V5): ``project.modify_code`` without ``file.modify`` blocks.

    The production operation requires ``file.modify``; this graph grants no
    permissions, so the operation must be excluded from planning candidates
    and the request must fail closed before planning.
    """
    from dataclasses import replace

    graph = _build_project_graph()
    definitions = graph.authority["definitions"]
    assert definitions["project.modify_code"].required_permissions == ("file.modify",)
    integrator = _make_project_integrator(graph)

    base = _project_integration_request()
    planning_request = replace(
        base.planning_request,
        allowed_operations=["project.modify_code"],
        permissions=[],
    )
    request = replace(base, planning_request=planning_request)
    result = integrator.integrate(request)

    assert (
        "project.modify_code"
        not in result.prepared_planning_request.metadata["operation_candidates"]
    )
    assert result.blocked is True
    assert result.plan is None
    assert graph.operation_calls["project.modify_code"] == 0
    # REAL_PROJECT_MODIFY_CODE_WITHOUT_PERMISSION=BLOCKED


def test_at_dp042_real_project_workflow_without_incoming_permission_blocked() -> None:
    """AT-DP-042 (V6): real ``project.project_setup`` without permission blocks.

    The workflow requires ``domain-permission:project:1.0.0``; the Domain
    authority grants it, but the incoming canonical request does not.
    The workflow must fail selection and the request must block before planning.
    """
    from dataclasses import replace

    graph = _build_project_graph()
    graph.authority["permissions"].add("domain-permission:project:1.0.0")
    integrator = _make_project_integrator(graph)

    base = _project_integration_request()
    planning_request = replace(
        base.planning_request,
        permissions=[],
        allowed_operations=["project.review_status"],
    )
    request = replace(
        base,
        planning_request=planning_request,
        metadata={"requested_workflow_ids": ["project.project_setup"]},
    )
    result = integrator.integrate(request)

    assert "project.project_setup" in result.capability_view.available_workflow_ids
    assert result.prepared_planning_request.permissions == []
    assert "project.project_setup" not in result.selected_domain_workflow_ids
    assert result.selected_domain_workflow_ids == ()
    assert result.blocked is True
    assert result.plan is None
    assert "domain_workflow_unavailable" in result.reason_codes
    # REAL_PROJECT_WORKFLOW_WITHOUT_INCOMING_PERMISSION=BLOCKED
    # PERMISSION_INCOMPATIBLE_WORKFLOW_FAILS_BEFORE_PLANNER=PASS


# ── AT-DP-042 adversarial coverage (Phase 10.42 V7) ─────────────────────────


def test_at_dp042_real_project_selected_workflow_with_unavailable_operation_blocked():
    """AT-DP-042 (V7): selected workflow with unavailable operation blocks.

    Real production ``project.feature_implementation`` requires the
    ``project.modify_code`` operation node. With ``file.modify`` absent from
    final planning authority, the operation is excluded from the final
    candidates and the workflow must fail selection before planner
    invocation — planning eligibility agrees with the canonical workflow
    resolver's ``operation.unavailable`` verdict.
    """
    from dataclasses import replace

    graph = _build_project_graph()
    graph.authority["permissions"].add("domain-permission:project:1.0.0")
    integrator = _make_project_integrator(graph)

    base = _project_integration_request()
    planning_request = replace(
        base.planning_request,
        permissions=["domain-permission:project:1.0.0"],
        allowed_operations=[
            "project.create_implementation_plan",
            "project.modify_code",
            "project.review_status",
        ],
    )
    request = replace(
        base,
        planning_request=planning_request,
        metadata={"requested_workflow_ids": ["project.feature_implementation"]},
    )
    result = integrator.integrate(request)

    assert (
        "project.modify_code"
        not in result.prepared_planning_request.metadata["operation_candidates"]
    )
    assert result.selected_domain_workflow_ids == ()
    assert result.blocked is True
    assert result.plan is None
    assert "domain_workflow_unavailable" in result.reason_codes
    # REAL_PROJECT_FEATURE_IMPLEMENTATION_WITHOUT_MODIFY_CODE=BLOCKED


def test_at_dp042_real_project_unselected_gated_workflow_never_leaks_approvals():
    """AT-DP-042 (V7): unselected approval-gated workflow leaves plans clean.

    Real production Project Domain: only ``project.review_status`` is
    planned, no workflow is selected, and the available
    approval-gated workflows' ``approval.file.modify`` gate must not appear
    in the prepared requirements or the plan's approval nodes.
    """
    from dataclasses import replace

    graph = _build_project_graph()
    graph.authority["permissions"].add("domain-permission:project:1.0.0")
    integrator = _make_project_integrator(graph)

    base = _project_integration_request()
    planning_request = replace(
        base.planning_request,
        permissions=["domain-permission:project:1.0.0"],
        allowed_operations=["project.review_status"],
    )
    result = integrator.integrate(replace(base, planning_request=planning_request))

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ()
    assert "project.feature_implementation" in (
        result.capability_view.available_workflow_ids
    )
    assert "approval.file.modify" not in (
        result.prepared_planning_request.required_approvals
    )
    assert result.plan is not None
    assert all(
        "approval.file.modify" not in node.required_approvers
        for node in result.plan.approval_nodes
    )
    # UNSELECTED_WORKFLOW_APPROVAL_GATE_LEAKAGE=0


def test_at_dp042_selected_approval_gated_workflow_projects_canonical_requirement():
    """AT-DP-042 (V7): selected workflow approval gate stays projected.

    Selecting ``python.review`` (canonical gate ``review-board``) under
    full final eligibility keeps the gate an additive plan obligation:
    the prepared request requires it and the canonical approval nodes
    trace the exact approval ID. No approval is synthesized as granted.
    """
    graph = _build_graph()
    integrator = _make_integrator(graph)

    result = integrator.integrate(_integration_request(graph))

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ("python.review",)
    assert result.prepared_planning_request.required_approvals == ["review-board"]
    assert result.plan is not None
    assert result.plan.approval_nodes
    assert any(
        "review-board" in node.required_approvers
        and "review-board" in node.metadata.get("approval_requirement_ids", [])
        for node in result.plan.approval_nodes
    )
    assert all(node.pending for node in result.plan.approval_nodes)
    validation = graph.service.validate_plan(
        result.plan, request=result.prepared_planning_request
    )
    assert validation.is_valid
    # SELECTED_WORKFLOW_APPROVAL_GATE_PROJECTED=PASS


def test_at_dp042_real_project_selected_workflow_without_internal_resources_blocked():
    """AT-DP-042 (V10): selected workflow missing internal operation resources blocks.

    Real production ``project.feature_implementation`` requires
    ``project.create_implementation_plan`` (requiring ``project.resource.project_plan``
    and ``project.resource.source_code``) and ``project.modify_code`` (requiring
    ``project.resource.source_code``). When planning authority omits these
    internal operation resources, the workflow must be rejected before planner
    invocation.
    """
    from dataclasses import replace

    graph = _build_project_graph()
    graph.authority["permissions"].update(
        {"domain-permission:project:1.0.0", "file.modify"}
    )
    integrator = _make_project_integrator(graph)

    base = _project_integration_request()
    planning_request = replace(
        base.planning_request,
        permissions=["domain-permission:project:1.0.0", "file.modify"],
        allowed_operations=[
            "project.create_implementation_plan",
            "project.modify_code",
            "project.review_status",
        ],
        resource_ids=[],
    )
    request = replace(
        base,
        planning_request=planning_request,
        metadata={"requested_workflow_ids": ["project.feature_implementation"]},
    )
    result = integrator.integrate(request)

    assert result.blocked is True
    assert result.selected_domain_workflow_ids == ()
    assert result.plan is None
    assert "domain_workflow_unavailable" in result.reason_codes
    print("REAL_PROJECT_FEATURE_IMPLEMENTATION_WITHOUT_INTERNAL_RESOURCES=BLOCKED")


def test_at_dp042_real_project_selected_workflow_full_eligibility_plans():
    """AT-DP-042 (V7/V10): fully eligible real workflow plans with obligation.

    ``project.feature_implementation`` with ``file.modify`` present in both
    permission authorities and required internal resources present stays
    selected, plans canonically, and keeps its outstanding approval gate as
    a projected obligation.
    """
    from dataclasses import replace

    graph = _build_project_graph()
    graph.authority["permissions"].update(
        {"domain-permission:project:1.0.0", "file.modify"}
    )
    integrator = _make_project_integrator(graph)

    base = _project_integration_request()
    planning_request = replace(
        base.planning_request,
        permissions=["domain-permission:project:1.0.0", "file.modify"],
        allowed_operations=[
            "project.create_implementation_plan",
            "project.modify_code",
            "project.review_status",
        ],
        resource_ids=[
            "project.resource.project_plan",
            "project.resource.source_code",
        ],
        metadata={
            "capabilities": ["transaction", "rollback", "validation"],
            "available_validation_policy_ids": [
                "validation.project.create_implementation_plan",
                "validation.project.modify_code",
                "validation.project.review_status",
            ],
            "available_rollback_policy_ids": [
                "rollback.project.create_implementation_plan",
                "rollback.project.modify_code",
                "rollback.project.review_status",
            ],
        },
    )
    request = replace(
        base,
        planning_request=planning_request,
        metadata={"requested_workflow_ids": ["project.feature_implementation"]},
    )
    result = integrator.integrate(request)

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ("project.feature_implementation",)
    assert result.plan is not None
    assert result.plan.status is WorkflowPlanStatus.VALID
    assert "approval.file.modify" in result.prepared_planning_request.required_approvals
    assert any(
        "approval.file.modify" in node.required_approvers
        for node in result.plan.approval_nodes
    )
    print("REAL_PROJECT_FEATURE_IMPLEMENTATION_WITH_INTERNAL_RESOURCES=PASS")
    print("REAL_PROJECT_INTERNAL_OPERATION_AVAILABILITY_AUTHORITY_EXPLICIT=PASS")
    print("REAL_PROJECT_FEATURE_IMPLEMENTATION_FULL_CANONICAL_AVAILABILITY=PASS")


def test_at_dp042_real_project_selected_workflow_missing_availability_prerequisite_blocked():
    """AT-DP-042 (V11 RED K): missing any operation availability prerequisite blocks planning."""
    from dataclasses import replace

    graph = _build_project_graph()
    graph.authority["permissions"].update(
        {"domain-permission:project:1.0.0", "file.modify"}
    )
    integrator = _make_project_integrator(graph)

    base = _project_integration_request()
    # Missing 'transaction' capability
    planning_request = replace(
        base.planning_request,
        permissions=["domain-permission:project:1.0.0", "file.modify"],
        allowed_operations=[
            "project.create_implementation_plan",
            "project.modify_code",
            "project.review_status",
        ],
        resource_ids=[
            "project.resource.project_plan",
            "project.resource.source_code",
        ],
        metadata={
            "capabilities": ["rollback", "validation"],
            "available_validation_policy_ids": [
                "validation.project.create_implementation_plan",
                "validation.project.modify_code",
                "validation.project.review_status",
            ],
            "available_rollback_policy_ids": [
                "rollback.project.create_implementation_plan",
                "rollback.project.modify_code",
                "rollback.project.review_status",
            ],
        },
    )
    request = replace(
        base,
        planning_request=planning_request,
        metadata={"requested_workflow_ids": ["project.feature_implementation"]},
    )
    result = integrator.integrate(request)
    assert result.blocked is True
    assert result.selected_domain_workflow_ids == ()
    assert result.plan is None
    assert "domain_workflow_unavailable" in result.reason_codes
    print("REAL_PROJECT_AVAILABILITY_AUTHORITY_DOWNGRADE_BLOCKS=PASS")


# ── AT-DP-042 V12 — most-restrictive multi-source authority (connected) ───


def test_at_dp042_v12_real_project_multi_source_agreement_pass():
    """AT-DP-042 (V12): planning/integration agreement on real Project passes."""
    from dataclasses import replace

    graph = _build_project_graph()
    graph.authority["permissions"].update(
        {"domain-permission:project:1.0.0", "file.modify"}
    )
    integrator = _make_project_integrator(graph)
    authority = {
        "capabilities": ["transaction", "rollback", "validation"],
        "available_validation_policy_ids": [
            "validation.project.create_implementation_plan",
            "validation.project.modify_code",
            "validation.project.review_status",
        ],
        "available_rollback_policy_ids": [
            "rollback.project.create_implementation_plan",
            "rollback.project.modify_code",
            "rollback.project.review_status",
        ],
    }
    base = _project_integration_request()
    planning_request = replace(
        base.planning_request,
        permissions=["domain-permission:project:1.0.0", "file.modify"],
        allowed_operations=[
            "project.create_implementation_plan",
            "project.modify_code",
            "project.review_status",
        ],
        resource_ids=[
            "project.resource.project_plan",
            "project.resource.source_code",
        ],
        metadata=dict(authority),
    )
    request = replace(
        base,
        planning_request=planning_request,
        metadata={
            "requested_workflow_ids": ["project.feature_implementation"],
            **authority,
        },
    )
    result = integrator.integrate(request)
    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ("project.feature_implementation",)
    assert result.plan is not None
    assert result.plan.status is WorkflowPlanStatus.VALID
    print("REAL_PROJECT_MULTI_SOURCE_AGREEMENT_PASS=PASS")


def test_at_dp042_v12_real_project_multi_source_restriction_blocks():
    """AT-DP-042 (V12): one applicable source removing authority blocks."""
    from dataclasses import replace

    graph = _build_project_graph()
    graph.authority["permissions"].update(
        {"domain-permission:project:1.0.0", "file.modify"}
    )
    integrator = _make_project_integrator(graph)
    full_authority = {
        "capabilities": ["transaction", "rollback", "validation"],
        "available_validation_policy_ids": [
            "validation.project.create_implementation_plan",
            "validation.project.modify_code",
            "validation.project.review_status",
        ],
        "available_rollback_policy_ids": [
            "rollback.project.create_implementation_plan",
            "rollback.project.modify_code",
            "rollback.project.review_status",
        ],
    }
    base = _project_integration_request()
    planning_request = replace(
        base.planning_request,
        permissions=["domain-permission:project:1.0.0", "file.modify"],
        allowed_operations=[
            "project.create_implementation_plan",
            "project.modify_code",
            "project.review_status",
        ],
        resource_ids=[
            "project.resource.project_plan",
            "project.resource.source_code",
        ],
        metadata=dict(full_authority),
    )
    request = replace(
        base,
        planning_request=planning_request,
        metadata={
            "requested_workflow_ids": ["project.feature_implementation"],
            "capabilities": [],
            "available_validation_policy_ids": [],
            "available_rollback_policy_ids": [],
        },
    )
    result = integrator.integrate(request)
    assert result.blocked is True
    assert result.selected_domain_workflow_ids == ()
    assert result.plan is None
    assert "domain_workflow_unavailable" in result.reason_codes
    print("REAL_PROJECT_MULTI_SOURCE_RESTRICTION_BLOCKS=PASS")


# ── AT-DP-042 V8 — workflow graph planning obligations (adversarial) ───────


class _CountingPlanningService(AgentPlanningService):
    """Acceptance probe: counts planner invocations without replacing it."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plan_calls = 0

    def plan(self, request):
        self.plan_calls += 1
        return super().plan(request)


def _build_subworkflow_acceptance_graph() -> _AcceptanceGraph:
    """Acceptance graph with required subworkflow dependency workflows.

    Canonical in-memory workflows (official ``DomainWorkflowDefinition`` /
    ``WorkflowNode`` contracts):

    - ``python.sub_parent_ok`` → required ``python.sub_child_ok@1.0.0``
      (eligible operation under final authority);
    - ``python.sub_parent_missing`` → required ``python.sub_missing@1.0.0``
      (not registered);
    - ``python.sub_parent_ineligible`` → required
      ``python.sub_child_bad@1.0.0`` (operation prohibited by final
      authority).
    """
    graph = _AcceptanceGraph(
        domain_registry=DomainRegistry(),
        operation_registry=InMemoryDomainOperationRegistry(
            InMemoryAgentOperationRegistry()
        ),
        workflow_registry=InMemoryDomainWorkflowRegistry(),
        permission_registry=DomainPermissionRegistry(),
        authority={
            "permissions": {"python.use", "filesystem.use"},
            "prohibited": {"filesystem.delete_file"},
            "approvals": set(),
        },
    )
    graph.domain_registry.register(
        _definition(
            "python",
            operations=("python.find_symbol",),
            workflows=(
                "python.sub_parent_ok",
                "python.sub_parent_missing",
                "python.sub_parent_ineligible",
            ),
        )
    )
    graph.domain_registry.register(
        _definition("filesystem", operations=("filesystem.delete_file",))
    )
    graph.domain_registry.enable("domain:python")
    graph.domain_registry.enable("domain:filesystem")

    for operation_id in ("python.find_symbol", "filesystem.delete_file"):
        domain_id = f"domain:{operation_id.split('.')[0]}"
        graph.operation_calls[operation_id] = 0
        definition = _operation(operation_id, domain_id)
        graph.operation_registry.register(
            definition,
            _counting_impl(graph.operation_calls, operation_id, definition),
        )

    def _sub_parent(workflow_id, subworkflow_id):
        return DomainWorkflowDefinition(
            workflow_id,
            "domain:python",
            "1.0.0",
            workflow_id,
            nodes=(
                WorkflowNode(
                    "child",
                    "invoke_subworkflow",
                    "Child",
                    subworkflow_id=subworkflow_id,
                    subworkflow_version="1.0.0",
                ),
                WorkflowNode(
                    "finish",
                    "complete",
                    "Finish",
                    dependencies=("child",),
                ),
            ),
        )

    def _sub_child(workflow_id, operation_id):
        return DomainWorkflowDefinition(
            workflow_id,
            "domain:python",
            "1.0.0",
            workflow_id,
            nodes=(
                WorkflowNode(
                    "work",
                    "execute_operation",
                    "Work",
                    operation_id=operation_id,
                    operation_version="1.0.0",
                ),
                WorkflowNode("done", "complete", "Done", dependencies=("work",)),
            ),
        )

    graph.workflow_registry.register(
        _sub_parent("python.sub_parent_ok", "python.sub_child_ok")
    )
    graph.workflow_registry.register(
        _sub_child("python.sub_child_ok", "python.find_symbol")
    )
    graph.workflow_registry.register(
        _sub_parent("python.sub_parent_missing", "python.sub_missing")
    )
    graph.workflow_registry.register(
        _sub_parent("python.sub_parent_ineligible", "python.sub_child_bad")
    )
    graph.workflow_registry.register(
        _sub_child("python.sub_child_bad", "filesystem.delete_file")
    )

    adapter = DefaultWorkflowPlannerAdapter(
        planner=TaskPlanner(reasoner=_StubReasoner()),
        plan_store=graph.store,
    )
    graph.service = _CountingPlanningService(adapter)

    def _engine_adapter(node, run):
        graph.engine_calls.append(node.node_id)
        return NodeExecution.complete({"node": node.node_id})

    graph.executor = DomainWorkflowExecutor(
        id_factory=lambda: f"acc-sub-{len(graph.engine_calls)}",
        operation_adapter=_engine_adapter,
    )
    return graph


def _subworkflow_acceptance_request(
    graph: _AcceptanceGraph, requested_workflow_ids: list[str]
) -> DomainPlannerWorkflowIntegrationRequest:
    return DomainPlannerWorkflowIntegrationRequest(
        request_id="int-req-042-acc-subworkflow",
        resolution_context=_resolution_context(),
        planning_request=_planning_request(),
        metadata={"requested_workflow_ids": requested_workflow_ids},
    )


def test_at_dp042_real_node_level_workflow_approval_projection() -> None:
    """AT-DP-042 (V8): real node-level approval gate reaches the plan.

    Real production Relationships Domain: ``relationships.decision_support``
    encodes its approval obligation only on the canonical
    ``REQUEST_APPROVAL`` node while ``approval_gates == ()``. Selecting the
    workflow under full final eligibility must project the exact node gate
    into the prepared planning request and keep it traceable and pending on
    the canonical plan approval nodes — never pre-granted.
    """
    from cmm.domains.relationships.definition import (
        build_relationships_domain_definition,
    )
    from cmm.domains.relationships.operations import (
        build_relationships_operation_definitions,
    )
    from cmm.domains.relationships.workflows import (
        build_relationships_workflow_definitions,
    )

    definition = build_relationships_domain_definition()
    graph = _AcceptanceGraph(
        domain_registry=DomainRegistry(),
        operation_registry=InMemoryDomainOperationRegistry(
            InMemoryAgentOperationRegistry()
        ),
        workflow_registry=InMemoryDomainWorkflowRegistry(),
        permission_registry=DomainPermissionRegistry(),
        authority={
            "permissions": set(),
            "prohibited": set(),
            "approvals": set(),
        },
    )
    graph.domain_registry.register(definition)
    graph.domain_registry.enable(str(definition.id))
    definitions = {
        entry.operation_id: entry
        for entry in build_relationships_operation_definitions()
    }
    for operation_id, entry in definitions.items():
        graph.operation_calls[operation_id] = 0
        graph.operation_registry.register(
            entry,
            _counting_impl(graph.operation_calls, operation_id, entry),
        )
    for workflow in build_relationships_workflow_definitions():
        graph.workflow_registry.register(workflow)
    adapter = DefaultWorkflowPlannerAdapter(
        planner=TaskPlanner(reasoner=_StubReasoner()),
        plan_store=graph.store,
    )
    graph.service = AgentPlanningService(adapter)
    graph.executor = DomainWorkflowExecutor(id_factory=lambda: "acc-rel-exec")

    integrator = DefaultDomainPlannerWorkflowIntegrator(
        resolver=DefaultDomainResolver(
            scoring_policy=DomainScoringPolicy(
                max_supporting_domains=0, supporting_margin=100.0
            )
        ),
        composer=DefaultDomainComposer(),
        domain_registry=graph.domain_registry,
        workflow_registry=graph.workflow_registry,
        planning_service=graph.service,
        workflow_executor=graph.executor,
        operation_definition_provider=lambda op: (
            graph.operation_registry.resolve_active(op, required=False)
        ),
        operation_availability=lambda op_id, domain_id: (
            graph.operation_registry.resolve_active(op_id, required=False) is not None
        ),
        permission_ids_provider=lambda composition: tuple(
            sorted(graph.authority["permissions"])
        ),
        prohibited_operation_ids_provider=lambda composition: (),
        approval_ids_provider=lambda composition: (),
        validation_ids_provider=lambda composition: (),
        authority_reference_ids_provider=lambda composition: ("authority:v1",),
    )

    result = integrator.integrate(
        DomainPlannerWorkflowIntegrationRequest(
            request_id="int-req-042-acc-rel",
            resolution_context=_resolution_context(
                id="ctx-042-acc-rel",
                user_input="Compare relationship options",
                available_domains=(DomainId(slug="relationships"),),
                authorized_domains=(DomainId(slug="relationships"),),
                explicit_domains=(DomainId(slug="relationships"),),
                resources=(
                    DomainResolutionResource(
                        id="r-rel",
                        resource_type="document",
                        source="user",
                        domain_ids=(DomainId(slug="relationships"),),
                    ),
                ),
            ),
            planning_request=_planning_request(
                id="req-042-acc-rel",
                agent_run_id="run-042-acc-rel",
                objective="Compare relationship options under explicit criteria",
                allowed_operations=[
                    "relationships.identify_needs",
                    "relationships.track_open_questions",
                ],
                permissions=[],
                resource_ids=["relationships.user_message"],
            ),
            metadata={"requested_workflow_ids": ["relationships.decision_support"]},
        )
    )

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ("relationships.decision_support",)
    assert "relationships.decision_support" in (
        result.prepared_planning_request.required_approvals
    )
    assert result.plan is not None
    assert result.plan.status is WorkflowPlanStatus.VALID
    assert any(
        "relationships.decision_support" in node.required_approvers
        and "relationships.decision_support"
        in node.metadata.get("approval_requirement_ids", [])
        for node in result.plan.approval_nodes
    )
    assert all(node.pending for node in result.plan.approval_nodes)
    validation = graph.service.validate_plan(
        result.plan, request=result.prepared_planning_request
    )
    assert validation.is_valid
    # AT_DP_042_REAL_NODE_LEVEL_APPROVAL_PROJECTION=PASS


def test_at_dp042_missing_required_subworkflow_blocks_before_planner() -> None:
    """AT-DP-042 (V8): missing required child never reaches the planner."""
    graph = _build_subworkflow_acceptance_graph()
    integrator = _make_integrator(graph)

    result = integrator.integrate(
        _subworkflow_acceptance_request(graph, ["python.sub_parent_missing"])
    )

    assert result.blocked is True
    assert result.plan is None
    assert result.selected_domain_workflow_ids == ()
    assert "domain_workflow_dependency_not_available" in result.reason_codes
    assert graph.service.plan_calls == 0
    # AT_DP_042_MISSING_REQUIRED_SUBWORKFLOW_BLOCKED=PASS
    # AT_DP_042_WORKFLOW_GRAPH_FAILS_BEFORE_PLANNER=PASS


def test_at_dp042_ineligible_required_subworkflow_blocks_before_planner() -> None:
    """AT-DP-042 (V8): final-authority-ineligible child blocks the parent.

    ``python.sub_child_bad`` executes ``filesystem.delete_file``, which the
    final planning authority prohibits; the parent must be blocked before
    planner invocation even though an unrelated eligible candidate exists.
    """
    graph = _build_subworkflow_acceptance_graph()
    integrator = _make_integrator(graph)

    result = integrator.integrate(
        _subworkflow_acceptance_request(graph, ["python.sub_parent_ineligible"])
    )

    assert result.blocked is True
    assert result.plan is None
    assert result.selected_domain_workflow_ids == ()
    assert "domain_workflow_dependency_not_available" in result.reason_codes
    assert graph.service.plan_calls == 0
    # AT_DP_042_INELIGIBLE_REQUIRED_SUBWORKFLOW_BLOCKED=PASS


def test_at_dp042_eligible_parent_child_subworkflow_chain_plans() -> None:
    """AT-DP-042 (V8): fully eligible parent/child chain plans canonically."""
    graph = _build_subworkflow_acceptance_graph()
    integrator = _make_integrator(graph)

    result = integrator.integrate(
        _subworkflow_acceptance_request(graph, ["python.sub_parent_ok"])
    )

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ("python.sub_parent_ok",)
    assert result.plan is not None
    assert result.plan.status is WorkflowPlanStatus.VALID
    assert graph.service.plan_calls == 1
    validation = graph.service.validate_plan(
        result.plan, request=result.prepared_planning_request
    )
    assert validation.is_valid
    # AT_DP_042_ELIGIBLE_PARENT_CHILD_CHAIN_PLANS=PASS
    # AT_DP_042_SUBWORKFLOW_SHARED_ENGINE_EXECUTION_PRESERVED=PASS


@pytest.mark.parametrize(
    "case",
    [
        {"version": "9.9.9"},
        {"optional_missing": True},
        {"approval": True, "validation": True},
        {"child": True, "cross": True, "cross_denied": True},
        {"child": True, "cross": True},
        {"child": True, "optional_child": True, "child_approval": True},
    ],
)
def test_at_dp042_v9_canonical_workflow_node_authority(case):
    from cmm.agent_runtime.workflow_planner_validator import AgentWorkflowPlanValidator

    from .test_domain_planner_workflow_integration import _v9_case

    result, service, canonical = _v9_case(**case)
    denied = bool(case.get("cross_denied") or case.get("version") == "9.9.9")
    assert result.blocked == denied
    assert service.plan_calls == int(not denied)
    if denied:
        assert canonical.decision.value == "deny"
        assert result.plan is None
        return
    assert (
        AgentWorkflowPlanValidator()
        .validate(result.plan, request=result.prepared_planning_request)
        .is_valid
    )
    assert all("find_symbol" not in op.operation_name for op in result.plan.operations)
    expected_approvals = set()
    if case.get("approval"):
        expected_approvals.add("operation.execute")
    if case.get("cross"):
        expected_approvals.add("domain.cross_access")
    if case.get("optional_child"):
        expected_approvals.update(("child.board", "child.policy"))
    assert expected_approvals <= set(
        result.prepared_planning_request.required_approvals
    )
    for approval in expected_approvals:
        assert any(
            approval in node.metadata.get("approval_requirement_ids", ())
            and node.pending
            for node in result.plan.approval_nodes
        )
    if case.get("validation"):
        assert (
            "internal.validation"
            in result.prepared_planning_request.required_validations
        )
        assert any(
            "internal.validation" in node.metadata.get("validation_requirement_ids", ())
            for node in result.plan.validation_nodes
        )
