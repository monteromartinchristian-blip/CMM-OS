"""Phase 10.42 — Domain planning capability projection tests.

DP-042 — Domain-specialized Planner and Workflow Engine integration.

Covers the read-only capability view built from canonical sources only:

- DomainRegistry listings (operations/workflows per effective domain);
- InMemoryDomainWorkflowRegistry active resolution authority;
- injected operation-availability answers;
- injected effective/prohibited/approval/validation/authority providers;
- canonical DomainDependency declarations;
- canonical workflow node topology.
"""

from __future__ import annotations

import pytest

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.agent_runtime.workflow_planner_adapter import AgentPlanningService
from cmm.agent_runtime.workflow_planner_contracts import (
    AgentPlanningRequest,
    AgentWorkflowPlan,
)
from cmm.domains.composition_contracts import (
    DomainComposition,
    DomainCompositionConflict,
)
from cmm.domains.contracts import DomainDefinition, DomainDependency, DomainManifestId
from cmm.domains.enums import (
    DomainCompositionStatus,
    DomainKind,
    DomainOperationType,
    DomainResolutionStatus,
)
from cmm.domains.errors import DomainContractValidationError
from cmm.domains.identifiers import DomainId
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.planner_workflow_integration import (
    DefaultDomainPlannerWorkflowIntegrator,
    _build_capability_view,
    _prepare_planning_request,
)
from cmm.domains.planner_workflow_integration_contracts import (
    DomainPlannerWorkflowIntegrationRequest,
    DomainPlannerWorkflowIntegrator,
    DomainPlanningCapabilityView,
)
from cmm.domains.registry import DomainRegistry
from cmm.domains.resolver_contracts import DomainResolutionResult
from cmm.domains.workflow_contracts import DomainWorkflowDefinition
from cmm.domains.workflow_registry import InMemoryDomainWorkflowRegistry
from cmm.workflows.contracts import WorkflowNode


def _definition(slug, **kwargs):
    defaults = {
        "id": DomainId.from_str(f"domain:{slug}"),
        "name": slug,
        "display_name": slug.title(),
        "version": "1.0.0",
        "kind": DomainKind.CORE,
        "description": f"Test domain {slug}",
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
        "description": f"Test operation {operation_id}",
        "operation_type": DomainOperationType.READ,
    }
    values.update(kwargs)
    return DomainOperationDefinition(**values)


class _Implementation:
    def __init__(self, definition):
        self.definition = definition

    def execute(self, request):
        return {"ok": True}


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
                operation_id="project.inspect",
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


def _resolution(primary="project", supporting=()):
    return DomainResolutionResult(
        id="res-042-1",
        context_id="ctx-042-1",
        status=DomainResolutionStatus.RESOLVED,
        primary_domain=DomainId.from_str(f"domain:{primary}"),
        supporting_domains=tuple(DomainId.from_str(f"domain:{s}") for s in supporting),
    )


def _composition(resolution, supporting=(), conflicts=(), status=None):
    if status is None:
        status = (
            DomainCompositionStatus.BLOCKED
            if conflicts
            else DomainCompositionStatus.COMPOSED
        )
    return DomainComposition(
        id="comp-042-1",
        resolution_id=resolution.id,
        status=status,
        primary_domain=resolution.primary_domain,
        supporting_domains=tuple(DomainId.from_str(f"domain:{s}") for s in supporting),
        conflicts=tuple(conflicts),
    )


def _blocking_conflict():
    return DomainCompositionConflict(
        code="capability.conflict",
        category="operations",
        domains=(
            DomainId.from_str("domain:project"),
            DomainId.from_str("domain:support"),
        ),
        severity="high",
        message="Blocking capability conflict",
        blocking=True,
        resolved=False,
    )


def _graph():
    domain_registry = DomainRegistry()
    domain_registry.register(
        _definition(
            "project",
            operations=("project.inspect", "project.write", "project.delete"),
            workflows=("project.review", "project.missing"),
            dependencies=(DomainDependency(domain_id="domain:support"),),
        )
    )
    domain_registry.register(
        _definition(
            "support",
            operations=("support.read", "project.inspect"),
            workflows=(),
        )
    )
    operation_registry = InMemoryDomainOperationRegistry(
        InMemoryAgentOperationRegistry()
    )
    for operation_id in ("project.inspect", "project.write", "support.read"):
        domain_id = f"domain:{operation_id.split('.')[0]}"
        definition = _operation(operation_id, domain_id)
        operation_registry.register(definition, _Implementation(definition))
    # Registered without an implementation: canonically UNAVAILABLE.
    operation_registry.register(_operation("project.delete", "domain:project"))
    workflow_registry = InMemoryDomainWorkflowRegistry()
    workflow_registry.register(
        _workflow(
            "project.review",
            "domain:project",
            required_permissions=("project.read",),
            approval_gates=("review-board",),
        )
    )
    return domain_registry, operation_registry, workflow_registry


def _view(**overrides):
    domain_registry, operation_registry, workflow_registry = _graph()
    resolution = _resolution()
    composition = _composition(resolution)
    kwargs = {
        "resolution": resolution,
        "composition": composition,
        "domain_registry": domain_registry,
        "workflow_registry": workflow_registry,
        "operation_availability": lambda op_id, domain_id: (
            operation_registry.resolve_active(op_id, required=False) is not None
        ),
        "effective_permission_ids": ("project.read",),
        "prohibited_operation_ids": (),
        "required_approval_ids": (),
        "required_validation_ids": (),
        "authority_reference_ids": ("authority:v1",),
    }
    kwargs.update(overrides)
    return _build_capability_view(**kwargs)


# ── Discovery ─────────────────────────────────────────────────────────────


def test_capability_view_preserves_primary_and_supporting_ids():
    resolution = _resolution(supporting=("support",))
    view = _view(
        resolution=resolution,
        composition=_composition(resolution, supporting=("support",)),
    )
    assert view.primary_domain_id == "domain:project"
    assert view.supporting_domain_ids == ("domain:support",)


def test_capability_view_lists_only_registry_operations():
    resolution = _resolution(supporting=("support",))
    view = _view(
        resolution=resolution,
        composition=_composition(resolution, supporting=("support",)),
    )
    # project.delete has no implementation → unavailable, excluded.
    assert view.available_operation_ids == (
        "project.inspect",
        "project.write",
        "support.read",
    )


def test_capability_view_excludes_operations_missing_from_domain_definition():
    domain_registry, operation_registry, workflow_registry = _graph()
    stray = _operation("project.stray", "domain:project")
    operation_registry.register(stray, _Implementation(stray))
    resolution = _resolution()
    view = _build_capability_view(
        resolution=resolution,
        composition=_composition(resolution),
        domain_registry=domain_registry,
        workflow_registry=workflow_registry,
        operation_availability=lambda op_id, domain_id: (
            operation_registry.resolve_active(op_id, required=False) is not None
        ),
        effective_permission_ids=(),
        prohibited_operation_ids=(),
        required_approval_ids=(),
        required_validation_ids=(),
        authority_reference_ids=(),
    )
    assert "project.stray" not in view.available_operation_ids


def test_capability_view_excludes_unavailable_operations():
    view = _view(operation_availability=lambda op_id, domain_id: False)
    assert view.available_operation_ids == ()


def test_capability_view_marks_prohibited_operations():
    view = _view(prohibited_operation_ids=("project.write",))
    assert "project.write" not in view.available_operation_ids
    assert view.prohibited_operation_ids == ("project.write",)


def test_capability_view_exposes_only_resolvable_workflows():
    view = _view()
    # project.missing is declared by the domain but absent from the registry.
    assert view.available_workflow_ids == ("project.review",)


def test_capability_view_excludes_permission_denied_workflows():
    view = _view(effective_permission_ids=())
    # project.review requires project.read, which is no longer effective.
    assert view.available_workflow_ids == ()


def test_capability_view_unions_workflow_approval_gates():
    view = _view(required_approval_ids=("change-advisory",))
    assert view.required_approval_ids == ("change-advisory", "review-board")


def test_capability_view_copies_dependency_ids_deterministically():
    first = _view()
    second = _view()
    assert first.operation_dependency_ids == (("domain:project", ("domain:support",)),)
    assert first.workflow_dependency_ids == (("project.review", ("start",)),)
    assert first.operation_dependency_ids == second.operation_dependency_ids
    assert first.workflow_dependency_ids == second.workflow_dependency_ids


def test_capability_view_reports_blocking_conflicts():
    resolution = _resolution(supporting=("support",))
    composition = _composition(
        resolution, supporting=("support",), conflicts=(_blocking_conflict(),)
    )
    view = _view(resolution=resolution, composition=composition)
    assert view.cross_domain_constraint_ids == ("capability.conflict",)


def test_capability_view_deduplicates_shared_operation_ids():
    view = _view()
    assert view.available_operation_ids.count("project.inspect") == 1


def test_capability_view_does_not_mutate_registries():
    domain_registry, _, workflow_registry = _graph()
    before_domains = domain_registry.snapshot()
    before_workflows = workflow_registry.snapshot_state()
    resolution = _resolution()
    _build_capability_view(
        resolution=resolution,
        composition=_composition(resolution),
        domain_registry=domain_registry,
        workflow_registry=workflow_registry,
        operation_availability=lambda op_id, domain_id: True,
        effective_permission_ids=(),
        prohibited_operation_ids=(),
        required_approval_ids=(),
        required_validation_ids=(),
        authority_reference_ids=(),
    )
    assert domain_registry.snapshot().records == before_domains.records
    assert workflow_registry.snapshot_state() == before_workflows


def test_capability_view_nonexistent_operation_is_not_exposed():
    view = _view(
        operation_availability=lambda op_id, domain_id: op_id == "project.nope"
    )
    assert "project.nope" not in view.available_operation_ids
    assert view.available_operation_ids == ()


# ── Most-restrictive AgentPlanningRequest composition ─────────────────────


def _incoming_request(**overrides):
    values = {
        "id": "req-042-1",
        "goal_id": "goal-042-1",
        "agent_run_id": "run-042-1",
        "objective": "Inspect the project domain",
    }
    values.update(overrides)
    return AgentPlanningRequest(**values)


def _capability(
    available=("project.inspect", "project.write"),
    prohibited=(),
    approvals=(),
    validations=(),
    permissions=("project.read",),
    workflows=("project.review",),
):
    return DomainPlanningCapabilityView(
        primary_domain_id="domain:project",
        available_operation_ids=available,
        prohibited_operation_ids=prohibited,
        available_workflow_ids=workflows,
        required_permission_ids=permissions,
        required_approval_ids=approvals,
        required_validation_ids=validations,
    )


def test_prepare_request_intersects_allowed_operations_and_unions_prohibitions():
    incoming = _incoming_request(
        allowed_operations=["project.inspect", "project.write"],
        prohibited_operations=["project.delete"],
    )
    view = _capability(
        available=("project.inspect",),
        prohibited=("project.write",),
    )
    prepared = _prepare_planning_request(incoming=incoming, capability_view=view)
    assert prepared.allowed_operations == ["project.inspect"]
    assert prepared.prohibited_operations == ["project.delete", "project.write"]


def test_prepare_request_defaults_allowed_to_domain_available():
    incoming = _incoming_request()
    view = _capability(available=("project.inspect", "project.write"))
    prepared = _prepare_planning_request(incoming=incoming, capability_view=view)
    assert prepared.allowed_operations == ["project.inspect", "project.write"]


def test_prepare_request_empty_intersection_does_not_fall_back():
    incoming = _incoming_request(allowed_operations=["project.write"])
    view = _capability(available=("project.inspect",))
    prepared = _prepare_planning_request(incoming=incoming, capability_view=view)
    assert prepared.allowed_operations == []


def test_prepare_request_required_approvals_are_additive():
    incoming = _incoming_request(required_approvals=["team-lead"])
    view = _capability(approvals=("review-board",))
    prepared = _prepare_planning_request(incoming=incoming, capability_view=view)
    assert prepared.required_approvals == ["team-lead", "review-board"]


def test_prepare_request_required_validations_are_additive():
    incoming = _incoming_request(required_validations=["schema-v1"])
    view = _capability(validations=("policy-check",))
    prepared = _prepare_planning_request(incoming=incoming, capability_view=view)
    assert prepared.required_validations == ["schema-v1", "policy-check"]


def test_prepare_request_permissions_never_expand():
    incoming = _incoming_request(permissions=["project.read", "project.admin"])
    view = _capability(permissions=("project.read",))
    prepared = _prepare_planning_request(incoming=incoming, capability_view=view)
    assert prepared.permissions == ["project.read"]


def test_prepare_request_empty_incoming_permissions_stay_empty():
    incoming = _incoming_request()
    view = _capability(permissions=("project.read",))
    prepared = _prepare_planning_request(incoming=incoming, capability_view=view)
    assert prepared.permissions == []


def test_prepare_request_budget_and_autonomy_never_increase():
    incoming = _incoming_request(
        budget={"max_tokens": 100, "max_cost": 5.0},
        autonomy_level=2,
    )
    view = _capability()
    prepared = _prepare_planning_request(incoming=incoming, capability_view=view)
    assert prepared.budget == {"max_tokens": 100, "max_cost": 5.0}
    assert prepared.autonomy_level == 2


def test_prepare_request_stamps_selected_workflow_references_only():
    incoming = _incoming_request(metadata={"caller": "test"})
    view = _capability(workflows=("project.review", "project.audit"))
    prepared = _prepare_planning_request(
        incoming=incoming,
        capability_view=view,
        selected_workflow_ids=("project.review",),
    )
    assert prepared.metadata["caller"] == "test"
    assert prepared.metadata["workflow_references"] == ("project.review",)


def test_prepare_request_omits_workflow_references_when_nothing_selected():
    incoming = _incoming_request()
    prepared = _prepare_planning_request(
        incoming=incoming, capability_view=_capability()
    )
    assert "workflow_references" not in prepared.metadata


def test_prepare_request_rejects_selected_workflow_outside_available():
    incoming = _incoming_request()
    with pytest.raises(DomainContractValidationError):
        _prepare_planning_request(
            incoming=incoming,
            capability_view=_capability(workflows=("project.review",)),
            selected_workflow_ids=("project.missing",),
        )


def test_prepare_request_does_not_mutate_incoming():
    incoming = _incoming_request(
        allowed_operations=["project.inspect", "project.write"],
        metadata={"caller": "test"},
    )
    before = incoming.to_dict()
    _prepare_planning_request(
        incoming=incoming,
        capability_view=_capability(available=("project.inspect",)),
    )
    assert incoming.to_dict() == before


def test_prepare_request_rejects_wrong_types():
    with pytest.raises(DomainContractValidationError):
        _prepare_planning_request(
            incoming={"id": "req-1"}, capability_view=_capability()
        )
    with pytest.raises(DomainContractValidationError):
        _prepare_planning_request(
            incoming=_incoming_request(), capability_view={"primary": "x"}
        )


# ── DefaultDomainPlannerWorkflowIntegrator.integrate ──────────────────────


class _StubReasoner:
    def locate_feature(self, query):
        return []

    def impact_analysis(self, feature_name):
        return None

    def explain_dependencies(self, feature_name):
        return None


class _CountingPlanningService(AgentPlanningService):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plan_calls = 0

    def plan(self, request):
        self.plan_calls += 1
        return super().plan(request)


class _CannedPlanningService:
    def __init__(self, plan):
        self.plan_calls = 0
        self._plan = plan

    def plan(self, request):
        self.plan_calls += 1
        return self._plan


def _planner_graph():

    domain_registry = DomainRegistry()
    domain_registry.register(
        _definition(
            "python",
            operations=(
                "python.find_symbol",
                "python.list_imports",
                "python.describe_module",
            ),
            workflows=("python.review", "python.simple", "python.guarded"),
        )
    )
    domain_registry.register(
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
    domain_registry.enable("domain:python")
    domain_registry.enable("domain:filesystem")
    operation_registry = InMemoryDomainOperationRegistry(
        InMemoryAgentOperationRegistry()
    )
    for operation_id in (
        "python.find_symbol",
        "python.list_imports",
        "python.describe_module",
        "filesystem.read_file",
        "filesystem.exists",
    ):
        domain_id = f"domain:{operation_id.split('.')[0]}"
        definition = _operation(operation_id, domain_id)
        operation_registry.register(definition, _Implementation(definition))
    # No implementation: canonically unavailable, and prohibited below.
    operation_registry.register(
        _operation("filesystem.delete_file", "domain:filesystem")
    )
    workflow_registry = InMemoryDomainWorkflowRegistry()
    workflow_registry.register(
        _workflow(
            "python.review",
            "domain:python",
            required_permissions=("python.use",),
            approval_gates=("review-board",),
        )
    )
    workflow_registry.register(
        _workflow(
            "python.guarded",
            "domain:python",
            required_permissions=("python.use",),
        )
    )
    workflow_registry.register(
        _workflow(
            "python.simple",
            "domain:python",
            nodes=(
                WorkflowNode(
                    "start",
                    "execute_operation",
                    "Start",
                    operation_id="python.find_symbol",
                    operation_version="1.0.0",
                ),
                WorkflowNode("finish", "complete", "Finish", dependencies=("start",)),
            ),
        )
    )
    workflow_registry.register(
        _workflow("other.flow", "domain:other"),
    )
    return domain_registry, operation_registry, workflow_registry


def _planning_stack(planning_service_factory=AgentPlanningService):
    from cmm.agent_runtime.workflow_planner_adapter import (
        DefaultWorkflowPlannerAdapter,
    )
    from cmm.agent_runtime.workflow_planner_store import InMemoryWorkflowPlanStore
    from cmm.planner.task_planner import TaskPlanner

    store = InMemoryWorkflowPlanStore()
    adapter = DefaultWorkflowPlannerAdapter(
        planner=TaskPlanner(reasoner=_StubReasoner()),
        plan_store=store,
    )
    service = planning_service_factory(adapter)
    return store, adapter, service


def _resolution_context_5(**overrides):
    from cmm.domains.resolution_contracts import (
        DomainResolutionContext,
        DomainResolutionResource,
    )

    values = {
        "id": "ctx-042-5",
        "user_input": "Python inspection with filesystem reading",
        "goal_id": "goal-042-5",
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


def _integrator_5(
    domain_registry,
    operation_registry,
    workflow_registry,
    service,
    executor=None,
    prohibited=("filesystem.delete_file",),
    approvals=(),
):
    from cmm.domains.composer import DefaultDomainComposer
    from cmm.domains.resolver import DefaultDomainResolver
    from cmm.domains.resolver_contracts import DomainScoringPolicy
    from cmm.domains.workflow_execution import DomainWorkflowExecutor

    return DefaultDomainPlannerWorkflowIntegrator(
        resolver=DefaultDomainResolver(
            scoring_policy=DomainScoringPolicy(
                max_supporting_domains=1, supporting_margin=100.0
            )
        ),
        composer=DefaultDomainComposer(),
        domain_registry=domain_registry,
        workflow_registry=workflow_registry,
        planning_service=service,
        workflow_executor=executor
        if executor is not None
        else DomainWorkflowExecutor(id_factory=lambda: "wf-id-1"),
        operation_availability=lambda op_id, domain_id: (
            operation_registry.resolve_active(op_id, required=False) is not None
        ),
        permission_ids_provider=lambda composition: ("filesystem.use", "python.use"),
        prohibited_operation_ids_provider=lambda composition: prohibited,
        approval_ids_provider=lambda composition: approvals,
        validation_ids_provider=lambda composition: ("python.schema",),
        authority_reference_ids_provider=lambda composition: ("authority:v1",),
    )


def _integration_request_5(**overrides):
    values = {
        "request_id": "int-req-042-5",
        "resolution_context": _resolution_context_5(),
        "planning_request": _incoming_request(
            id="req-042-5",
            goal_id="goal-042-5",
            agent_run_id="run-042-5",
            actor_id="actor-042",
            objective="Inspect python symbols and read filesystem files",
            allowed_operations=[
                "python.find_symbol",
                "python.list_imports",
                "python.describe_module",
                "filesystem.read_file",
                "filesystem.exists",
            ],
        ),
        "metadata": {"requested_workflow_ids": ["python.review"]},
    }
    values.update(overrides)
    return DomainPlannerWorkflowIntegrationRequest(**values)


def test_integrate_produces_canonical_plan_through_planning_service():
    from cmm.agent_runtime.enums import WorkflowPlanStatus
    from cmm.agent_runtime.workflow_planner_contracts import AgentWorkflowPlan

    domain_registry, operation_registry, workflow_registry = _planner_graph()
    store, _, service = _planning_stack()
    integrator = _integrator_5(
        domain_registry, operation_registry, workflow_registry, service
    )

    result = integrator.integrate(_integration_request_5())

    assert result.blocked is False
    assert result.reason_codes == ()
    assert type(result.plan) is AgentWorkflowPlan
    assert result.plan.status == WorkflowPlanStatus.VALID
    assert store.get(result.plan.id) is result.plan
    assert result.prepared_planning_request.allowed_operations == [
        "python.find_symbol",
        "python.list_imports",
        "python.describe_module",
        "filesystem.read_file",
        "filesystem.exists",
    ]
    assert result.prepared_planning_request.prohibited_operations == [
        "filesystem.delete_file"
    ]
    assert result.prepared_planning_request.required_validations == ["python.schema"]
    assert result.plan.metadata["workflow_references"] == ["python.review"]
    assert result.selected_domain_workflow_ids == ("python.review",)
    assert isinstance(integrator, DomainPlannerWorkflowIntegrator)
    assert not any("store" in attr for attr in vars(integrator))


def test_integrate_blocks_nonexistent_workflow_without_calling_planner():
    domain_registry, operation_registry, workflow_registry = _planner_graph()
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _integrator_5(
        domain_registry, operation_registry, workflow_registry, service
    )
    request = _integration_request_5(
        metadata={"requested_workflow_ids": ["python.nope"]}
    )

    result = integrator.integrate(request)

    assert result.blocked is True
    assert result.plan is None
    assert "domain_workflow_unavailable" in result.reason_codes
    assert service.plan_calls == 0


def test_integrate_blocks_workflow_outside_composition():
    domain_registry, operation_registry, workflow_registry = _planner_graph()
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _integrator_5(
        domain_registry, operation_registry, workflow_registry, service
    )
    # other.flow is registered but belongs to no effective domain.
    request = _integration_request_5(
        metadata={"requested_workflow_ids": ["other.flow"]}
    )

    result = integrator.integrate(request)

    assert result.blocked is True
    assert result.plan is None
    assert service.plan_calls == 0


def test_integrate_blocks_zero_permitted_operations():
    domain_registry, operation_registry, workflow_registry = _planner_graph()
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _integrator_5(
        domain_registry, operation_registry, workflow_registry, service
    )
    planning_request = _incoming_request(
        id="req-042-5",
        goal_id="goal-042-5",
        agent_run_id="run-042-5",
        actor_id="actor-042",
        objective="Inspect python symbols",
        allowed_operations=["python.nonexistent"],
    )
    request = _integration_request_5(planning_request=planning_request, metadata={})

    result = integrator.integrate(request)

    assert result.blocked is True
    assert result.plan is None
    assert "domain_no_permitted_operations" in result.reason_codes
    assert service.plan_calls == 0


def test_integrate_blocks_identity_conflict():
    domain_registry, operation_registry, workflow_registry = _planner_graph()
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _integrator_5(
        domain_registry, operation_registry, workflow_registry, service
    )
    planning_request = _incoming_request(
        id="req-042-5",
        goal_id="goal-other",
        agent_run_id="run-042-5",
        actor_id="actor-042",
        objective="Inspect python symbols",
    )
    request = _integration_request_5(planning_request=planning_request, metadata={})

    result = integrator.integrate(request)

    assert result.blocked is True
    assert result.plan is None
    assert "identity_conflict" in result.reason_codes
    assert service.plan_calls == 0


def test_integrate_blocks_prohibited_operation_emitted_by_planner():
    from cmm.agent_runtime.workflow_planner_contracts import (
        AgentWorkflowOperation,
        AgentWorkflowTask,
    )

    domain_registry, operation_registry, workflow_registry = _planner_graph()
    canned = AgentWorkflowPlan(
        id="plan-canned",
        goal_id="goal-042-5",
        agent_run_id="run-042-5",
        workflow_id="workflow-canned",
        tasks=[
            AgentWorkflowTask(
                id="t-1", workflow_id="workflow-canned", name="T", description="d"
            )
        ],
        operations=[
            AgentWorkflowOperation(
                id="op-1", task_id="t-1", operation_name="filesystem.delete_file"
            )
        ],
    )
    service = _CannedPlanningService(canned)
    integrator = _integrator_5(
        domain_registry, operation_registry, workflow_registry, service
    )

    result = integrator.integrate(_integration_request_5(metadata={}))

    assert service.plan_calls == 1
    assert result.blocked is True
    assert "domain_prohibited_operation_planned" in result.reason_codes


# ── Planned Domain workflow delegation ──────────────────────────────────


def _executing_integrator(workflow_registry, executor):
    domain_registry, operation_registry, _ = _planner_graph()
    _, _, service = _planning_stack()
    return _integrator_5(
        domain_registry, operation_registry, workflow_registry, service, executor
    )


def _workflow_context_5(**overrides):
    from cmm.domains.workflow_contracts import DomainWorkflowContext

    values = {
        "primary_domain_id": "domain:python",
        "available_operations": frozenset(
            {
                "python.find_symbol",
                "python.list_imports",
                "python.describe_module",
                "filesystem.read_file",
                "filesystem.exists",
            }
        ),
    }
    values.update(overrides)
    return DomainWorkflowContext(**values)


def test_execute_workflow_reference_delegates_to_canonical_executor():
    from cmm.domains.workflow_contracts import DomainWorkflowResult
    from cmm.domains.workflow_execution import DomainWorkflowExecutor
    from cmm.workflows.engine import NodeExecution
    from cmm.workflows.enums import WorkflowRunStatus

    _, _, workflow_registry = _planner_graph()
    calls: list[str] = []

    def adapter(node, run):
        calls.append(node.node_id)
        return NodeExecution.complete({"node": node.node_id})

    executor = DomainWorkflowExecutor(
        id_factory=lambda: f"wf-exec-{len(calls)}",
        operation_adapter=adapter,
    )
    integrator = _executing_integrator(workflow_registry, executor)

    result = integrator.execute_workflow_reference(
        workflow_id="python.simple",
        context=_workflow_context_5(),
        inputs={},
    )

    assert type(result) is DomainWorkflowResult
    assert result.status == WorkflowRunStatus.COMPLETED
    assert calls, "shared WorkflowEngine path must execute nodes"
    assert not any("store" in attr or "engine" in attr for attr in vars(integrator))


def test_execute_workflow_reference_unavailable_workflow_never_starts():
    from cmm.domains.workflow_execution import DomainWorkflowExecutor
    from cmm.workflows.engine import NodeExecution
    from cmm.workflows.errors import WorkflowRegistryError

    _, _, workflow_registry = _planner_graph()
    calls: list[str] = []

    def adapter(node, run):
        calls.append(node.node_id)
        return NodeExecution.complete({})

    executor = DomainWorkflowExecutor(
        id_factory=lambda: "wf-exec-1", operation_adapter=adapter
    )
    integrator = _executing_integrator(workflow_registry, executor)

    with pytest.raises(WorkflowRegistryError):
        integrator.execute_workflow_reference(
            workflow_id="python.missing",
            context=_workflow_context_5(),
            inputs={},
        )
    assert calls == []


def test_execute_workflow_reference_permission_downgrade_blocks_execution():
    from cmm.domains.workflow_execution import DomainWorkflowExecutor
    from cmm.workflows.engine import NodeExecution

    _, _, workflow_registry = _planner_graph()
    calls: list[str] = []

    def adapter(node, run):
        calls.append(node.node_id)
        return NodeExecution.complete({})

    executor = DomainWorkflowExecutor(
        id_factory=lambda: "wf-exec-1", operation_adapter=adapter
    )
    integrator = _executing_integrator(workflow_registry, executor)

    # python.guarded requires python.use; the downgraded context grants nothing,
    # so the canonical resolution boundary inside the executor blocks it.
    with pytest.raises(ValueError, match="unavailable"):
        integrator.execute_workflow_reference(
            workflow_id="python.guarded",
            context=_workflow_context_5(available_permissions=frozenset()),
            inputs={},
        )
    assert calls == []


def test_execute_workflow_reference_reuses_subworkflow_through_shared_engine():
    from cmm.domains.workflow_contracts import DomainWorkflowDefinition
    from cmm.domains.workflow_execution import DomainWorkflowExecutor
    from cmm.workflows.contracts import WorkflowNode as CommonWorkflowNode
    from cmm.workflows.engine import NodeExecution
    from cmm.workflows.enums import WorkflowRunStatus

    workflow_registry = InMemoryDomainWorkflowRegistry()
    child = DomainWorkflowDefinition(
        "python.child",
        "domain:python",
        "1.0.0",
        "Child",
        nodes=(CommonWorkflowNode("done", "complete", "Done"),),
    )
    parent = DomainWorkflowDefinition(
        "python.parent",
        "domain:python",
        "1.0.0",
        "Parent",
        nodes=(
            CommonWorkflowNode(
                "child",
                "invoke_subworkflow",
                "Child",
                subworkflow_id="python.child",
                subworkflow_version="1.0.0",
            ),
            CommonWorkflowNode("finish", "complete", "Finish", dependencies=("child",)),
        ),
    )
    workflow_registry.register(child)
    workflow_registry.register(parent)
    calls: list[str] = []

    def adapter(node, run):
        calls.append(node.node_id)
        return NodeExecution.complete({"node": node.node_id})

    executor = DomainWorkflowExecutor(
        id_factory=lambda: f"wf-sub-{len(calls)}",
        operation_adapter=adapter,
        workflow_definitions={("python.child", "1.0.0"): child},
    )
    integrator = _executing_integrator(workflow_registry, executor)

    result = integrator.execute_workflow_reference(
        workflow_id="python.parent",
        context=_workflow_context_5(available_permissions=frozenset()),
        inputs={},
    )

    assert result.status == WorkflowRunStatus.COMPLETED
    assert calls, "subworkflow must execute through the shared WorkflowEngine"


# ── Canonical replanning, stale authority, cross-domain conflicts ────────


def test_replan_supersedes_previous_through_canonical_service():
    from dataclasses import replace

    from cmm.agent_runtime.enums import WorkflowPlanChangeReason, WorkflowPlanStatus

    domain_registry, operation_registry, workflow_registry = _planner_graph()
    store, _, service = _planning_stack()
    integrator = _integrator_5(
        domain_registry, operation_registry, workflow_registry, service
    )
    first = integrator.integrate(_integration_request_5())
    assert first.blocked is False
    assert first.prepared_planning_request.required_approvals == ["review-board"]
    assert len(first.plan.approval_nodes) > 0

    # Material authority change: the domain now requires change-board approval.
    integrator2 = _integrator_5(
        domain_registry,
        operation_registry,
        workflow_registry,
        service,
        approvals=("change-board",),
    )
    replan_request = replace(_integration_request_5(), current_plan=first.plan)
    result = integrator2.replan(
        replan_request,
        reason=WorkflowPlanChangeReason.PERMISSION_CHANGED,
        reason_details="domain now requires change-board approval",
    )

    assert result.blocked is False
    assert result.plan.version == 2
    assert result.plan.previous_version_id == first.plan.id
    assert store.get(first.plan.id).status == WorkflowPlanStatus.SUPERSEDED
    assert result.prepared_planning_request.required_approvals == [
        "change-board",
        "review-board",
    ]
    assert len(result.plan.approval_nodes) > 0
    assert not any("store" in attr or "history" in attr for attr in vars(integrator2))


def test_replan_requires_current_plan():
    from cmm.agent_runtime.enums import WorkflowPlanChangeReason

    domain_registry, operation_registry, workflow_registry = _planner_graph()
    _, _, service = _planning_stack()
    integrator = _integrator_5(
        domain_registry, operation_registry, workflow_registry, service
    )

    with pytest.raises(DomainContractValidationError):
        integrator.replan(
            _integration_request_5(),
            reason=WorkflowPlanChangeReason.PERMISSION_CHANGED,
            reason_details="no current plan bound",
        )


def test_stale_operation_authority_cannot_execute_through_dispatch():
    from datetime import datetime, timezone

    from cmm.agent_runtime.errors import ControlledOperationExecutionError
    from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
    from cmm.agent_runtime.operation_execution_contracts import AgentOperationRequest
    from cmm.domains.agent_runtime_integration import DomainOperationDispatchAdapter
    from cmm.domains.errors import DomainError
    from cmm.domains.operation_execution import (
        DefaultDomainOperationOrchestrator,
        DomainOperationExecutionDelegate,
    )

    definition = _operation("python.find_symbol", "domain:python")
    calls: list[str] = []

    class _CountingImpl:
        def __init__(self):
            self.definition = definition

        def execute(self, request):
            calls.append(request.operation_name)
            return {"ok": True}

    common = InMemoryAgentOperationRegistry()
    domain_operations = InMemoryDomainOperationRegistry(common)
    domain_operations.register(definition, _CountingImpl())
    execution_adapter = AgentExecutionAdapter(
        registry=common,
        execution_delegate=DomainOperationExecutionDelegate(domain_operations),
    )
    orchestrator = DefaultDomainOperationOrchestrator(
        domain_operations, execution_adapter
    )
    dispatch = DomainOperationDispatchAdapter(orchestrator)

    def _dispatch_request():
        return AgentOperationRequest(
            id="op-req-stale",
            agent_run_id="run-042-5",
            workflow_id="workflow-042-5",
            task_id="task-042-5",
            operation_name="python.find_symbol",
            operation_version="1.0.0",
            idempotency_key="idem-stale-1",
            parameters={},
            permissions=(),
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata={
                "domain_intelligence": {
                    "primary_domain_id": "domain:python",
                    "supporting_domain_ids": (),
                    "actor_id": "actor-042",
                    "goal_id": "goal-042-5",
                    "available_resources": (),
                    "denied_permissions": (),
                    "capabilities": ("execute",),
                }
            },
        )

    first = dispatch(_dispatch_request())
    assert first["success"] is True
    assert calls == ["python.find_symbol"]

    # The operation becomes unavailable after planning: stale authority dies.
    domain_operations.set_enabled("python.find_symbol", "1.0.0", False)
    try:
        second = dispatch(_dispatch_request())
    except (DomainError, ControlledOperationExecutionError):
        second = None
    assert calls == ["python.find_symbol"]
    if second is not None:
        assert second["success"] is False

    # Phase 10.42 adds no Domain operation executor of its own.
    _, _, service = _planning_stack()
    domain_registry, operation_registry, workflow_registry = _planner_graph()
    integrator = _integrator_5(
        domain_registry, operation_registry, workflow_registry, service
    )
    for forbidden in (
        "_operation_executor",
        "_operation_orchestrator",
        "_operation_dispatcher",
        "_domain_operation_executor",
    ):
        assert not hasattr(integrator, forbidden)


def test_cross_domain_conflict_blocks_without_silent_selection():
    from cmm.domains.contracts import DomainDependency

    domain_registry = DomainRegistry()
    domain_registry.register(
        _definition(
            "python",
            operations=(),
            workflows=(),
            dependencies=(DomainDependency(domain_id="domain:ghost"),),
        )
    )
    # Ghost satisfies registry validation but never enters the resolution,
    # so the canonical composer reports a blocking missing-dependency conflict.
    domain_registry.register(_definition("ghost", operations=(), workflows=()))
    domain_registry.register(_definition("filesystem", operations=(), workflows=()))
    domain_registry.enable("domain:ghost")
    domain_registry.enable("domain:filesystem")
    domain_registry.enable("domain:python")
    _, operation_registry, workflow_registry = _planner_graph()
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _integrator_5(
        domain_registry, operation_registry, workflow_registry, service
    )

    result = integrator.integrate(_integration_request_5(metadata={}))

    assert result.blocked is True
    assert result.plan is None
    assert result.selected_domain_workflow_ids == ()
    assert result.capability_view.available_operation_ids == ()
    assert result.capability_view.cross_domain_constraint_ids == (
        "DOMAIN_COMPOSITION_REQUIRED_DEPENDENCY_MISSING",
    )
    assert service.plan_calls == 0


# ── BLOCKER-01 remediation (V1): fail closed on unavailable/invalid plans ──


def _canned_plan_with_operation(operation_name: str, **overrides):
    from cmm.agent_runtime.workflow_planner_contracts import (
        AgentWorkflowOperation,
        AgentWorkflowTask,
    )

    values = {
        "id": "plan-canned-blocker01",
        "goal_id": "goal-042-5",
        "agent_run_id": "run-042-5",
        "workflow_id": "workflow-canned-blocker01",
        "tasks": [
            AgentWorkflowTask(
                id="t-1",
                workflow_id="workflow-canned-blocker01",
                name="T",
                description="d",
            )
        ],
        "operations": [
            AgentWorkflowOperation(
                id="op-1", task_id="t-1", operation_name=operation_name
            )
        ],
    }
    values.update(overrides)
    return AgentWorkflowPlan(**values)


def test_blocker01_unavailable_operation_outside_allowlist_is_blocked():
    """RED 1: declared-but-unavailable op outside the allowlist must block.

    ``filesystem.delete_file`` is registered without an implementation, so it
    is canonically UNAVAILABLE and excluded from the prepared allowlist. It is
    deliberately not prohibited here so only the allowlist rule can catch it.
    """
    domain_registry, operation_registry, workflow_registry = _planner_graph()
    canned = _canned_plan_with_operation("filesystem.delete_file")
    service = _CannedPlanningService(canned)
    integrator = _integrator_5(
        domain_registry,
        operation_registry,
        workflow_registry,
        service,
        prohibited=(),
    )

    result = integrator.integrate(_integration_request_5(metadata={}))

    assert (
        "filesystem.delete_file"
        not in result.prepared_planning_request.allowed_operations
    )
    assert service.plan_calls == 1
    assert result.blocked is True
    assert "domain_operation_not_permitted" in result.reason_codes


def test_blocker01_invalid_canonical_plan_never_returns_unblocked():
    """RED 2: an INVALID canonical plan must fail closed at the boundary."""
    from cmm.agent_runtime.enums import (
        WorkflowPlanStatus,
        WorkflowPlanValidationStatus,
    )
    from cmm.agent_runtime.workflow_planner_contracts import (
        AgentWorkflowPlanValidation,
    )

    domain_registry, operation_registry, workflow_registry = _planner_graph()
    canned = _canned_plan_with_operation(
        "python.find_symbol",
        status=WorkflowPlanStatus.INVALID,
        validation=AgentWorkflowPlanValidation(
            status=WorkflowPlanValidationStatus.FAILED,
            is_valid=False,
            blocking_errors=[
                "Operation 'python.find_symbol' is not in allowed_operations."
            ],
        ),
    )
    service = _CannedPlanningService(canned)
    integrator = _integrator_5(
        domain_registry, operation_registry, workflow_registry, service
    )

    result = integrator.integrate(_integration_request_5(metadata={}))

    assert service.plan_calls == 1
    assert result.blocked is True
    assert "invalid_canonical_plan" in result.reason_codes


# ── MAJOR-01 remediation (V1): project capability semantics ────────────────


def _rich_planner_graph():
    """Planner graph with one semantically rich Domain operation definition."""
    from cmm.agent_runtime.enums import PolicyRiskLevel

    domain_registry = DomainRegistry()
    domain_registry.register(
        _definition(
            "python",
            operations=(
                "python.find_symbol",
                "python.list_imports",
                "python.describe_module",
            ),
            workflows=("python.review", "python.simple", "python.guarded"),
        )
    )
    domain_registry.register(
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
    domain_registry.enable("domain:python")
    domain_registry.enable("domain:filesystem")
    operation_registry = InMemoryDomainOperationRegistry(
        InMemoryAgentOperationRegistry()
    )
    rich = _operation(
        "python.find_symbol",
        "domain:python",
        required_permissions=("perm.a",),
        validation_policy_id="validation.a",
        requires_approval=True,
        reversible=False,
        risk_level=PolicyRiskLevel.HIGH,
        metadata={"timeout_seconds": 42.0},
    )
    operation_registry.register(rich, _Implementation(rich))
    for operation_id in (
        "python.list_imports",
        "python.describe_module",
        "filesystem.read_file",
        "filesystem.exists",
    ):
        domain_id = f"domain:{operation_id.split('.')[0]}"
        definition = _operation(operation_id, domain_id)
        operation_registry.register(definition, _Implementation(definition))
    operation_registry.register(
        _operation("filesystem.delete_file", "domain:filesystem")
    )
    workflow_registry = InMemoryDomainWorkflowRegistry()
    workflow_registry.register(
        _workflow(
            "python.review",
            "domain:python",
            required_permissions=("python.use",),
            approval_gates=("review-board",),
        )
    )
    workflow_registry.register(
        _workflow(
            "python.guarded",
            "domain:python",
            required_permissions=("python.use",),
        )
    )
    workflow_registry.register(_workflow("python.simple", "domain:python"))
    return domain_registry, operation_registry, workflow_registry


def _rich_integrator(
    domain_registry,
    operation_registry,
    workflow_registry,
    service,
    dependencies=None,
):
    from cmm.domains.composer import DefaultDomainComposer
    from cmm.domains.resolver import DefaultDomainResolver
    from cmm.domains.resolver_contracts import DomainScoringPolicy
    from cmm.domains.workflow_execution import DomainWorkflowExecutor

    return DefaultDomainPlannerWorkflowIntegrator(
        resolver=DefaultDomainResolver(
            scoring_policy=DomainScoringPolicy(
                max_supporting_domains=1, supporting_margin=100.0
            )
        ),
        composer=DefaultDomainComposer(),
        domain_registry=domain_registry,
        workflow_registry=workflow_registry,
        planning_service=service,
        workflow_executor=DomainWorkflowExecutor(id_factory=lambda: "wf-id-1"),
        operation_availability=lambda op_id, domain_id: (
            operation_registry.resolve_active(op_id, required=False) is not None
        ),
        permission_ids_provider=lambda composition: ("filesystem.use", "python.use"),
        prohibited_operation_ids_provider=lambda composition: (
            "filesystem.delete_file",
        ),
        approval_ids_provider=lambda composition: ("approval.review-board",),
        validation_ids_provider=lambda composition: ("validation.python-schema",),
        authority_reference_ids_provider=lambda composition: ("authority:v1",),
        operation_definition_provider=lambda operation_id: (
            operation_registry.resolve_active(operation_id, required=False)
        ),
        operation_dependency_provider=lambda operation_id: (
            dependencies.get(operation_id, ()) if dependencies is not None else ()
        ),
    )


def test_major01_operation_semantics_projected_into_canonical_plan():
    """RED: exact Domain operation semantics must reach the canonical plan."""
    from cmm.agent_runtime.enums import WorkflowPlanRisk

    domain_registry, operation_registry, workflow_registry = _rich_planner_graph()
    _, _, service = _planning_stack()
    integrator = _rich_integrator(
        domain_registry, operation_registry, workflow_registry, service
    )

    result = integrator.integrate(_integration_request_5(metadata={}))

    assert result.blocked is False
    target = next(
        op for op in result.plan.operations if op.operation_name == "python.find_symbol"
    )
    assert target.required_permissions == ["perm.a"]
    assert target.required_validations == ["validation.a"]
    assert target.requires_approval is True
    assert target.reversible is False
    assert target.rollback_operation is None
    assert target.risk is WorkflowPlanRisk.HIGH
    assert target.timeout_seconds == 42.0
    assert target.metadata["domain_id"] == "domain:python"
    assert any(
        "approval.review-board" in node.required_approvers
        for node in result.plan.approval_nodes
    )
    assert any(
        "validation.a" in node.metadata.get("validation_requirement_ids", [])
        for node in result.plan.validation_nodes
    )
    assert any(
        "validation.python-schema"
        in node.metadata.get("validation_requirement_ids", [])
        for node in result.plan.validation_nodes
    )


def test_major01_operation_and_workflow_dependencies_consumed():
    """RED: dependency rows must become edges/references, not inert data.

    The required pair is forward under the documented deterministic
    candidate selection order (eligible candidates consumed round-robin in
    step order): ``filesystem.read_file`` is planned before
    ``python.find_symbol``, so the edge cannot cycle with the sequential
    task chain. A backward pair would genuinely cycle and fail closed.
    """
    domain_registry, operation_registry, workflow_registry = _rich_planner_graph()
    _, _, service = _planning_stack()
    integrator = _rich_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        service,
        dependencies={"python.find_symbol": ("filesystem.read_file",)},
    )

    result = integrator.integrate(_integration_request_5(metadata={}))

    assert result.blocked is False
    references = result.prepared_planning_request.metadata["dependency_references"]
    assert references["operation_dependencies"] == [
        ["filesystem.read_file", "python.find_symbol"]
    ]
    assert references["workflow_dependencies"]["python.review"] == ["start"]
    tasks_by_op = {}
    for task, operation in zip(result.plan.tasks, result.plan.operations):
        tasks_by_op.setdefault(operation.operation_name, task.id)
    source = tasks_by_op["filesystem.read_file"]
    target = tasks_by_op["python.find_symbol"]
    assert any(
        dep.source_task_id == source and dep.target_task_id == target
        for dep in result.plan.dependencies
    )
    assert result.plan.metadata["dependency_references"]["operation_dependencies"] == [
        ["filesystem.read_file", "python.find_symbol"]
    ]


# ── V3 remediation (V2 MAJOR-03): real production Domain Pack selection ─────


def _project_graph(available_override=None):
    """Real production ``domain:project`` graph with all 20 operations live."""
    from cmm.domains.project.definition import build_project_domain_definition
    from cmm.domains.project.operations import build_project_operation_definitions

    domain_registry = DomainRegistry()
    domain_registry.register(build_project_domain_definition())
    domain_registry.enable("domain:project")
    definitions = {
        definition.operation_id: definition
        for definition in build_project_operation_definitions()
    }
    operation_registry = InMemoryDomainOperationRegistry(
        InMemoryAgentOperationRegistry()
    )
    for definition in definitions.values():
        operation_registry.register(definition, _Implementation(definition))
    workflow_registry = InMemoryDomainWorkflowRegistry()
    if available_override is not None:
        availability = available_override
    else:

        def availability(operation_id, domain_id):
            return (
                operation_registry.resolve_active(operation_id, required=False)
                is not None
            )

    return (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    )


def _project_integrator(
    domain_registry,
    operation_registry,
    workflow_registry,
    definitions,
    availability,
    service,
    dependencies=None,
):
    from cmm.domains.composer import DefaultDomainComposer
    from cmm.domains.resolver import DefaultDomainResolver
    from cmm.domains.resolver_contracts import DomainScoringPolicy
    from cmm.domains.workflow_execution import DomainWorkflowExecutor

    return DefaultDomainPlannerWorkflowIntegrator(
        resolver=DefaultDomainResolver(
            scoring_policy=DomainScoringPolicy(
                max_supporting_domains=0, supporting_margin=100.0
            )
        ),
        composer=DefaultDomainComposer(),
        domain_registry=domain_registry,
        workflow_registry=workflow_registry,
        planning_service=service,
        workflow_executor=DomainWorkflowExecutor(id_factory=lambda: "wf-id-project"),
        operation_availability=availability,
        permission_ids_provider=lambda composition: (),
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


def _project_request(**overrides):
    from cmm.domains.resolution_contracts import (
        DomainResolutionContext,
        DomainResolutionResource,
    )

    values = {
        "request_id": "int-req-042-project",
        "resolution_context": DomainResolutionContext(
            id="ctx-042-project",
            user_input="Review project status and plan milestones",
            goal_id="goal-042-project",
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
        "planning_request": _incoming_request(
            id="req-042-project",
            goal_id="goal-042-project",
            agent_run_id="run-042-project",
            actor_id="actor-042",
            objective="Review project status and plan milestones",
        ),
        "metadata": {},
    }
    values.update(overrides)
    return DomainPlannerWorkflowIntegrationRequest(**values)


def test_v3_real_project_pack_plan_uses_registered_capability():
    """RED (V2 MAJOR-03): real ``domain:project`` ops must enter the plan."""
    from cmm.agent_runtime.enums import WorkflowPlanStatus

    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_graph()
    _, _, service = _planning_stack()
    integrator = _project_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
    )

    result = integrator.integrate(_project_request())

    assert result.blocked is False
    assert result.reason_codes == ()
    planned = [operation.operation_name for operation in result.plan.operations]
    assert planned, "canonical plan must contain operations"
    assert set(planned) & set(definitions), (
        "REAL_DOMAIN_REGISTERED_OPERATIONS ∩ RETURNED_PLAN_OPERATION_NAMES != empty"
    )
    assert result.plan.status == WorkflowPlanStatus.VALID
    assert result.plan.validation.is_valid


def test_v3_no_heuristic_operation_escapes_eligible_candidates():
    """RED (V2 MAJOR-03): only eligible ``project.*`` candidates may be planned."""
    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_graph()
    _, _, service = _planning_stack()
    integrator = _project_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
    )

    result = integrator.integrate(_project_request())

    assert result.blocked is False
    eligible = set(result.prepared_planning_request.metadata["operation_candidates"])
    assert eligible == set(definitions)
    planned = [operation.operation_name for operation in result.plan.operations]
    assert all(operation in eligible for operation in planned)
    assert not any(operation.startswith("python.") for operation in planned)
    assert not any(operation.startswith("filesystem.") for operation in planned)


def test_v3_real_project_pack_selection_is_deterministic():
    """RED (V2 MAJOR-03): real-pack selection must be deterministic."""
    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_graph()
    _, _, service = _planning_stack()
    integrator = _project_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
    )

    first = integrator.integrate(_project_request())
    second = integrator.integrate(_project_request())

    assert [op.operation_name for op in first.plan.operations] == [
        op.operation_name for op in second.plan.operations
    ]


