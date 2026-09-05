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
        # V7 MAJOR-08: fixture node operations must be resolvable under the
        # graph's final planning authority — a selected workflow whose
        # EXECUTE_OPERATION node references an unavailable operation is
        # canonically ineligible for planning.
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


def test_capability_view_keeps_workflow_approval_gates_out_of_global_approvals():
    """V7 MAJOR-09: workflow gates are selection-scoped, never plan-wide.

    The capability view carries only injected global/composition approval
    requirements. Gates of available workflows stay on their canonical
    definitions: ``project.review`` requires ``review-board``, but that
    gate must not appear in the plan-wide projection merely because the
    workflow is available (V6 MAJOR-09 root cause).
    """
    view = _view(required_approval_ids=("change-advisory",))
    assert view.required_approval_ids == ("change-advisory",)
    assert "review-board" not in view.required_approval_ids


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
            permissions=["python.use", "filesystem.use"],
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
        permission_ids_provider=lambda composition: (
            "filesystem.use",
            "python.use",
            "perm.a",
        ),
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


def _rich_request_5(**overrides):
    """Default ``_integration_request_5`` planning graph plus ``perm.a`` grant.

    V5 MAJOR-06: the rich ``python.find_symbol`` definition requires
    ``perm.a``, so the incoming request must carry it (with the Domain
    effective authority above) for the operation to stay a
    permission-compatible candidate.
    """
    planning_request = _incoming_request(
        id="req-042-5",
        goal_id="goal-042-5",
        agent_run_id="run-042-5",
        actor_id="actor-042",
        objective="Inspect python symbols and read filesystem files",
        permissions=["perm.a"],
        allowed_operations=[
            "python.find_symbol",
            "python.list_imports",
            "python.describe_module",
            "filesystem.read_file",
            "filesystem.exists",
        ],
    )
    values = {"planning_request": planning_request, "metadata": {}}
    values.update(overrides)
    return _integration_request_5(**values)


def test_major01_operation_semantics_projected_into_canonical_plan():
    """RED: exact Domain operation semantics must reach the canonical plan."""
    from cmm.agent_runtime.enums import WorkflowPlanRisk

    domain_registry, operation_registry, workflow_registry = _rich_planner_graph()
    _, _, service = _planning_stack()
    integrator = _rich_integrator(
        domain_registry, operation_registry, workflow_registry, service
    )

    result = integrator.integrate(_rich_request_5())

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

    result = integrator.integrate(_rich_request_5())

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
    # V5 MAJOR-06: project.modify_code requires file.modify, which this
    # fixture's empty permission authority does not grant, so it is
    # correctly excluded while every other registered pack operation
    # remains eligible.
    assert eligible == set(definitions) - {"project.modify_code"}
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


# ── V3 remediation (V2 MAJOR-04): missing dependencies fail closed ──────────


def test_v3_nonexistent_required_upstream_fails_closed():
    """RED (V2 MAJOR-04): dependency on a nonexistent operation must block."""
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
        dependencies={"project.compare_code_documentation": ("project.nope",)},
    )

    result = integrator.integrate(_project_request())

    assert result.blocked is True
    assert "domain_unresolved_operation_dependency" in result.reason_codes
    assert result.plan is not None
    assert not result.plan.validation.is_valid
    assert result.plan.metadata["unresolved_operation_dependencies"] == [
        ["project.nope", "project.compare_code_documentation"]
    ]


def test_v3_unavailable_required_upstream_fails_closed():
    """RED (V2 MAJOR-04): dependency on an unavailable operation must block."""
    domain_registry, operation_registry, workflow_registry, definitions, _ = (
        _project_graph()
    )

    def availability(operation_id, domain_id):
        if operation_id == "project.review_status":
            return False
        return (
            operation_registry.resolve_active(operation_id, required=False) is not None
        )

    _, _, service = _planning_stack()
    integrator = _project_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
        dependencies={"project.compare_code_documentation": ("project.review_status",)},
    )

    result = integrator.integrate(_project_request())

    assert "project.review_status" not in result.capability_view.available_operation_ids
    assert result.blocked is True
    assert "domain_unresolved_operation_dependency" in result.reason_codes
    assert not result.plan.validation.is_valid


def test_v3_valid_required_dependency_materializes_canonical_edge():
    """RED (V2 MAJOR-04): planned endpoints keep one canonical edge."""
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
        dependencies={
            "project.create_implementation_plan": ("project.analyse_architecture",)
        },
    )

    result = integrator.integrate(_project_request())

    assert result.blocked is False
    tasks_by_op = {}
    for task, operation in zip(result.plan.tasks, result.plan.operations):
        tasks_by_op.setdefault(operation.operation_name, task.id)
    source = tasks_by_op["project.analyse_architecture"]
    target = tasks_by_op["project.create_implementation_plan"]
    assert source != target
    assert any(
        dep.source_task_id == source and dep.target_task_id == target
        for dep in result.plan.dependencies
    )
    assert "unresolved_operation_dependencies" not in result.plan.metadata


def test_v3_no_silent_required_dependency_drop():
    """RED (V2 MAJOR-04): every declared required pair is either an edge or a block."""
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
        dependencies={"project.compare_code_documentation": ("project.nope",)},
    )

    result = integrator.integrate(_project_request())

    declared = result.prepared_planning_request.metadata["dependency_references"][
        "operation_dependencies"
    ]
    assert declared == [["project.nope", "project.compare_code_documentation"]]
    materialized = {
        (
            next(
                task.id
                for task, operation in zip(result.plan.tasks, result.plan.operations)
                if operation.operation_name == pair[0]
            ),
            next(
                task.id
                for task, operation in zip(result.plan.tasks, result.plan.operations)
                if operation.operation_name == pair[1]
            ),
        )
        for pair in declared
        if all(
            any(
                operation.operation_name == endpoint
                for operation in result.plan.operations
            )
            for endpoint in pair
        )
    }
    assert materialized == set()
    assert result.blocked is True
    assert "domain_unresolved_operation_dependency" in result.reason_codes


# ── V4 remediation (V3 MAJOR-05): effective operation candidates ──────────


def test_v4_real_project_narrow_allowlist_plan():
    """V4 MAJOR-05 RED A: narrow allowlist constrains candidates and plan."""
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
    incoming = _incoming_request(
        id="req-042-v4-narrow",
        goal_id="goal-042-project",
        agent_run_id="run-042-v4-narrow",
        actor_id="actor-042",
        objective="Review project status",
        allowed_operations=["project.review_status"],
    )
    result = integrator.integrate(_project_request(planning_request=incoming))

    assert tuple(result.prepared_planning_request.allowed_operations) == (
        "project.review_status",
    )
    assert tuple(result.prepared_planning_request.metadata["operation_candidates"]) == (
        "project.review_status",
    )
    planned = [operation.operation_name for operation in result.plan.operations]
    assert planned, "canonical plan must contain operations"
    assert all(operation == "project.review_status" for operation in planned)
    assert result.plan.status == WorkflowPlanStatus.VALID
    assert result.plan.validation.is_valid
    assert result.blocked is False
    # REAL_DOMAIN_NARROW_ALLOWLIST_PLAN=PASS


def test_v4_real_project_partial_prohibition_plan():
    """V4 MAJOR-05 RED B: prohibited capability never enters candidates/plan."""
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
    incoming = _incoming_request(
        id="req-042-v4-prohibit",
        goal_id="goal-042-project",
        agent_run_id="run-042-v4-prohibit",
        actor_id="actor-042",
        objective="Review project status and plan milestones",
        prohibited_operations=["project.analyse_architecture"],
    )
    result = integrator.integrate(_project_request(planning_request=incoming))

    candidates = result.prepared_planning_request.metadata["operation_candidates"]
    assert "project.analyse_architecture" not in candidates
    assert "project.analyse_architecture" in tuple(
        result.prepared_planning_request.prohibited_operations
    )
    planned = [operation.operation_name for operation in result.plan.operations]
    assert planned, "canonical plan must contain operations"
    assert "project.analyse_architecture" not in planned
    assert any(operation in set(definitions) for operation in planned)
    assert result.blocked is False
    # REAL_DOMAIN_PARTIAL_PROHIBITION_PLAN=PASS


def test_v4_zero_effective_candidates_fails_before_planner():
    """V4 MAJOR-05 RED C: empty effective set fails closed without planning."""
    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_graph()
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _project_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
    )
    incoming = _incoming_request(
        id="req-042-v4-empty",
        goal_id="goal-042-project",
        agent_run_id="run-042-v4-empty",
        actor_id="actor-042",
        objective="Review project status",
        allowed_operations=["project.review_status"],
        prohibited_operations=["project.review_status"],
    )
    result = integrator.integrate(_project_request(planning_request=incoming))

    assert (
        tuple(result.prepared_planning_request.metadata["operation_candidates"]) == ()
    )
    assert service.plan_calls == 0
    assert result.blocked is True
    assert "domain_no_permitted_operations" in result.reason_codes
    # ZERO_EFFECTIVE_CANDIDATES_FAILS_BEFORE_PLANNER=PASS


def test_v4_effective_candidates_subset_of_prepared_allowed():
    """V4 MAJOR-05 RED D1: candidates ⊆ prepared allowed."""
    incoming = _incoming_request(allowed_operations=["project.review_status"])
    view = _capability(
        available=("project.inspect", "project.write", "project.review_status"),
        prohibited=(),
    )
    prepared = _prepare_planning_request(incoming=incoming, capability_view=view)
    assert set(prepared.metadata["operation_candidates"]) <= set(
        prepared.allowed_operations
    )
    # EFFECTIVE_CANDIDATES_SUBSET_OF_PREPARED_ALLOWED=PASS


def test_v4_effective_candidates_exclude_prepared_prohibited():
    """V4 MAJOR-05 RED D2: candidates ∩ prepared prohibited = ∅."""
    incoming = _incoming_request(
        allowed_operations=["project.inspect", "project.analyse_architecture"],
        prohibited_operations=["project.analyse_architecture"],
    )
    view = _capability(
        available=("project.inspect", "project.analyse_architecture"),
        prohibited=("project.write",),
    )
    prepared = _prepare_planning_request(incoming=incoming, capability_view=view)
    assert (
        set(prepared.metadata["operation_candidates"])
        & set(prepared.prohibited_operations)
        == set()
    )
    assert (
        "project.analyse_architecture" not in prepared.metadata["operation_candidates"]
    )
    assert "project.write" not in prepared.metadata["operation_candidates"]
    # EFFECTIVE_CANDIDATES_EXCLUDE_PREPARED_PROHIBITED=PASS


# ── V5 remediation (V4 MAJOR-06): operation permission compatibility ───────


def _project_permission_integrator(
    domain_registry,
    operation_registry,
    workflow_registry,
    definitions,
    availability,
    service,
    *,
    effective_permissions=(),
    prohibited=(),
    dependencies=None,
):
    """Real ``domain:project`` integrator with explicit permission authority."""
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
        permission_ids_provider=lambda composition: tuple(effective_permissions),
        prohibited_operation_ids_provider=lambda composition: tuple(prohibited),
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


def test_v5_real_project_modify_code_without_permission_blocked():
    """V5 MAJOR-06 RED A: modify_code without file.modify never reaches planning."""
    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_graph()
    assert definitions["project.modify_code"].required_permissions == ("file.modify",)
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _project_permission_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
        effective_permissions=(),
    )
    incoming = _incoming_request(
        id="req-042-v5-noperm",
        goal_id="goal-042-project",
        agent_run_id="run-042-v5-noperm",
        actor_id="actor-042",
        objective="Modify project code",
        permissions=[],
        allowed_operations=["project.modify_code"],
    )
    result = integrator.integrate(_project_request(planning_request=incoming))

    assert "project.modify_code" not in tuple(
        result.prepared_planning_request.metadata["operation_candidates"]
    )
    assert service.plan_calls == 0
    assert result.blocked is True
    assert result.plan is None
    # REAL_PROJECT_MODIFY_CODE_WITHOUT_PERMISSION=BLOCKED


def test_v5_real_project_modify_code_with_permission_plans():
    """V5 MAJOR-06 RED B: modify_code with file.modify remains plannable."""
    from cmm.agent_runtime.enums import WorkflowPlanStatus

    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_graph()
    assert definitions["project.modify_code"].required_permissions == ("file.modify",)
    _, _, service = _planning_stack()
    integrator = _project_permission_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
        effective_permissions=("file.modify",),
    )
    incoming = _incoming_request(
        id="req-042-v5-perm",
        goal_id="goal-042-project",
        agent_run_id="run-042-v5-perm",
        actor_id="actor-042",
        objective="Modify project code",
        permissions=["file.modify"],
        allowed_operations=["project.modify_code"],
    )
    result = integrator.integrate(_project_request(planning_request=incoming))

    assert "project.modify_code" in tuple(
        result.prepared_planning_request.metadata["operation_candidates"]
    )
    assert result.blocked is False
    assert result.plan.status == WorkflowPlanStatus.VALID
    assert result.plan.validation.is_valid
    planned = [operation.operation_name for operation in result.plan.operations]
    assert planned and all(operation == "project.modify_code" for operation in planned)
    # REAL_PROJECT_MODIFY_CODE_WITH_PERMISSION=PASS


def test_v5_mixed_permission_candidates_filtered():
    """V5 MAJOR-06 RED C: only the permission-incompatible op is excluded."""
    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_graph()
    assert definitions["project.modify_code"].required_permissions == ("file.modify",)
    assert definitions["project.review_status"].required_permissions == ()
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _project_permission_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
        effective_permissions=(),
    )
    incoming = _incoming_request(
        id="req-042-v5-mixed",
        goal_id="goal-042-project",
        agent_run_id="run-042-v5-mixed",
        actor_id="actor-042",
        objective="Review status and modify code",
        permissions=[],
        allowed_operations=["project.review_status", "project.modify_code"],
    )
    result = integrator.integrate(_project_request(planning_request=incoming))

    candidates = tuple(
        result.prepared_planning_request.metadata["operation_candidates"]
    )
    assert "project.review_status" in candidates
    assert "project.modify_code" not in candidates
    assert service.plan_calls == 1
    assert result.blocked is False
    assert result.plan.validation.is_valid
    planned = [operation.operation_name for operation in result.plan.operations]
    assert planned
    assert "project.modify_code" not in planned
    assert all(operation == "project.review_status" for operation in planned)
    # MIXED_PERMISSION_CANDIDATES_FILTERED=PASS


def test_v5_permission_compatible_candidates_satisfy_all_authority():
    """V5 MAJOR-06 RED D: allow/prohibit/permission invariants hold together."""
    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_graph()
    _, _, service = _planning_stack()
    integrator = _project_permission_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
        effective_permissions=(),
        prohibited=("project.analyse_architecture",),
    )
    incoming = _incoming_request(
        id="req-042-v5-composed",
        goal_id="goal-042-project",
        agent_run_id="run-042-v5-composed",
        actor_id="actor-042",
        objective="Review, analyse, and modify",
        permissions=[],
        allowed_operations=[
            "project.review_status",
            "project.modify_code",
            "project.analyse_architecture",
        ],
        prohibited_operations=["project.analyse_architecture"],
    )
    result = integrator.integrate(_project_request(planning_request=incoming))

    prepared = result.prepared_planning_request
    candidates = list(prepared.metadata["operation_candidates"])
    assert candidates, "at least one permission-compatible candidate must remain"
    assert set(candidates) <= set(prepared.allowed_operations)
    assert not (set(candidates) & set(prepared.prohibited_operations))
    prepared_permissions = set(prepared.permissions)
    incompatible = 0
    for candidate in candidates:
        definition = definitions.get(candidate)
        assert definition is not None
        required = set(definition.required_permissions)
        if not required <= prepared_permissions:
            incompatible += 1
    assert incompatible == 0
    assert "project.modify_code" not in candidates
    assert "project.analyse_architecture" not in candidates
    assert "project.review_status" in candidates
    # PERMISSION_INCOMPATIBLE_OPERATION_CANDIDATE=0
    # EFFECTIVE_CANDIDATES_SUBSET_OF_PREPARED_ALLOWED=PASS
    # EFFECTIVE_CANDIDATES_EXCLUDE_PREPARED_PROHIBITED=PASS


def test_v5_zero_permission_compatible_candidates_fails_before_planner():
    """V5 MAJOR-06 RED: all candidates permission-incompatible blocks early."""
    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_graph()
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _project_permission_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
        effective_permissions=(),
    )
    incoming = _incoming_request(
        id="req-042-v5-zero",
        goal_id="goal-042-project",
        agent_run_id="run-042-v5-zero",
        actor_id="actor-042",
        objective="Modify project code",
        permissions=[],
        allowed_operations=["project.modify_code"],
    )
    result = integrator.integrate(_project_request(planning_request=incoming))

    assert (
        tuple(result.prepared_planning_request.metadata["operation_candidates"]) == ()
    )
    assert service.plan_calls == 0
    assert result.blocked is True
    assert result.plan is None
    assert "domain_no_permitted_operations" in result.reason_codes
    # ZERO_PERMISSION_COMPATIBLE_CANDIDATES_FAILS_BEFORE_PLANNER=PASS


def test_v5_unknown_operation_definition_preserves_registration_authority():
    """V5 MAJOR-06 RED E: unknown definitions keep registration/availability rule."""
    incoming = _incoming_request(allowed_operations=["project.inspect"])
    view = _capability(
        available=("project.inspect",),
        prohibited=(),
    )
    prepared = _prepare_planning_request(
        incoming=incoming,
        capability_view=view,
        operation_definition_provider=lambda operation_id: None,
    )
    assert tuple(prepared.metadata["operation_candidates"]) == ("project.inspect",)


# ── V6 remediation (V5 MAJOR-07): workflow permission compatibility ───────


def _project_workflow_graph(available_override=None):
    """Real production ``domain:project`` graph with operations and workflows live."""
    from cmm.domains.project.workflows import build_project_workflow_definitions

    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_graph(available_override=available_override)
    for workflow in build_project_workflow_definitions():
        workflow_registry.register(workflow)
    return (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    )


def test_v6_real_project_workflow_without_incoming_permission_blocked():
    """V6 MAJOR-07 RED A: real project workflow without incoming permission fails before planner."""
    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_workflow_graph()
    setup_wf = workflow_registry.resolve_active("project.project_setup")
    assert setup_wf.required_permissions == ("domain-permission:project:1.0.0",)
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _project_permission_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
        effective_permissions=("domain-permission:project:1.0.0",),
    )
    incoming = _incoming_request(
        id="req-042-v6-noperm",
        goal_id="goal-042-project",
        agent_run_id="run-042-v6-noperm",
        actor_id="actor-042",
        objective="Setup project",
        permissions=[],
        allowed_operations=["project.review_status"],
    )
    request = _project_request(
        planning_request=incoming,
        metadata={"requested_workflow_ids": ["project.project_setup"]},
    )
    result = integrator.integrate(request)

    assert "project.project_setup" in result.capability_view.available_workflow_ids
    assert result.prepared_planning_request.permissions == []
    assert "project.project_setup" not in result.selected_domain_workflow_ids
    assert result.selected_domain_workflow_ids == ()
    assert service.plan_calls == 0
    assert result.blocked is True
    assert result.plan is None
    assert "domain_workflow_unavailable" in result.reason_codes
    # REAL_PROJECT_WORKFLOW_WITHOUT_INCOMING_PERMISSION=BLOCKED
    # PERMISSION_INCOMPATIBLE_WORKFLOW_FAILS_BEFORE_PLANNER=PASS


def test_v6_real_project_workflow_with_permission_plans():
    """V6 MAJOR-07 RED B: real workflow with permission in both authorities plans successfully."""
    from cmm.agent_runtime.enums import WorkflowPlanStatus

    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_workflow_graph()
    setup_wf = workflow_registry.resolve_active("project.project_setup")
    assert setup_wf.required_permissions == ("domain-permission:project:1.0.0",)
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _project_permission_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
        effective_permissions=("domain-permission:project:1.0.0",),
    )
    incoming = _incoming_request(
        id="req-042-v6-perm",
        goal_id="goal-042-project",
        agent_run_id="run-042-v6-perm",
        actor_id="actor-042",
        objective="Setup project",
        permissions=["domain-permission:project:1.0.0"],
        # V7 MAJOR-08: the requested workflow's EXECUTE_OPERATION node
        # requires project.create_project_overview, which must be eligible
        # under the final candidates for the workflow to stay selected.
        allowed_operations=["project.create_project_overview"],
    )
    request = _project_request(
        planning_request=incoming,
        metadata={"requested_workflow_ids": ["project.project_setup"]},
    )
    result = integrator.integrate(request)

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ("project.project_setup",)
    assert result.prepared_planning_request.permissions == [
        "domain-permission:project:1.0.0"
    ]
    assert service.plan_calls == 1
    assert result.plan.status == WorkflowPlanStatus.VALID
    assert result.plan.validation.is_valid
    # REAL_PROJECT_WORKFLOW_WITH_PERMISSION=PASS


def test_v6_workflow_required_permissions_subset_of_prepared():
    """V6 MAJOR-07 RED C: every selected workflow must satisfy final permission invariant."""
    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_workflow_graph()
    _, _, service = _planning_stack()
    integrator = _project_permission_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
        effective_permissions=("domain-permission:project:1.0.0",),
    )
    incoming = _incoming_request(
        id="req-042-v6-subset",
        goal_id="goal-042-project",
        agent_run_id="run-042-v6-subset",
        actor_id="actor-042",
        objective="Setup project",
        permissions=["domain-permission:project:1.0.0"],
        # V7 MAJOR-08: workflow node operations must be final-authority
        # eligible for selection (see test_v6_real_project_workflow_with_
        # permission_plans).
        allowed_operations=["project.create_project_overview"],
    )
    request = _project_request(
        planning_request=incoming,
        metadata={"requested_workflow_ids": ["project.project_setup"]},
    )
    result = integrator.integrate(request)

    assert result.blocked is False
    selected = result.selected_domain_workflow_ids
    prepared_permissions = set(result.prepared_planning_request.permissions)
    incompatible = 0
    for wf_id in selected:
        wf = workflow_registry.resolve_active(wf_id)
        if not (set(wf.required_permissions) <= prepared_permissions):
            incompatible += 1
    assert incompatible == 0
    assert "project.project_setup" in selected
    # WORKFLOW_REQUIRED_PERMISSIONS_SUBSET_OF_PREPARED=PASS
    # PERMISSION_INCOMPATIBLE_SELECTED_WORKFLOW=0


def test_v6_mixed_workflow_permission_authority():
    """V6 MAJOR-07 RED D: atomic fail-closed when requested set contains incompatible workflow."""
    from cmm.domains.composer import DefaultDomainComposer
    from cmm.domains.contracts import DomainDefinition, DomainManifestId
    from cmm.domains.enums import DomainKind, DomainOperationType
    from cmm.domains.identifiers import DomainId
    from cmm.domains.operation_contracts import DomainOperationDefinition
    from cmm.domains.resolution_contracts import (
        DomainResolutionContext,
        DomainResolutionResource,
    )
    from cmm.domains.resolver import DefaultDomainResolver
    from cmm.domains.resolver_contracts import DomainScoringPolicy
    from cmm.domains.workflow_contracts import DomainWorkflowDefinition
    from cmm.domains.workflow_execution import DomainWorkflowExecutor
    from cmm.workflows.contracts import WorkflowNode

    domain_registry = DomainRegistry()
    domain_registry.register(
        DomainDefinition(
            id=DomainId.from_str("domain:mixed"),
            name="mixed",
            display_name="Mixed",
            version="1.0.0",
            kind=DomainKind.CORE,
            description="Mixed domain",
            manifest_id=DomainManifestId(slug="mixed", version="1.0.0"),
            enabled=True,
            operations=("mixed.op",),
            workflows=("mixed.compatible", "mixed.incompatible"),
        )
    )
    domain_registry.enable("domain:mixed")

    wf_compatible = DomainWorkflowDefinition(
        workflow_id="mixed.compatible",
        domain_id="domain:mixed",
        version="1.0.0",
        name="Compatible Workflow",
        nodes=(WorkflowNode("step1", "complete", "Step1"),),
        required_permissions=("perm.base",),
    )
    wf_incompatible = DomainWorkflowDefinition(
        workflow_id="mixed.incompatible",
        domain_id="domain:mixed",
        version="1.0.0",
        name="Incompatible Workflow",
        nodes=(WorkflowNode("step1", "complete", "Step1"),),
        required_permissions=("perm.base", "perm.restricted"),
    )
    workflow_registry = InMemoryDomainWorkflowRegistry()
    workflow_registry.register(wf_compatible)
    workflow_registry.register(wf_incompatible)

    op_def = DomainOperationDefinition(
        operation_id="mixed.op",
        domain_id="domain:mixed",
        version="1.0.0",
        name="Mixed Operation",
        description="Mixed Operation",
        operation_type=DomainOperationType.READ,
        reversible=True,
    )
    operation_registry = InMemoryDomainOperationRegistry(
        InMemoryAgentOperationRegistry()
    )
    operation_registry.register(op_def, _Implementation(op_def))

    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = DefaultDomainPlannerWorkflowIntegrator(
        resolver=DefaultDomainResolver(
            scoring_policy=DomainScoringPolicy(
                max_supporting_domains=0, supporting_margin=100.0
            )
        ),
        composer=DefaultDomainComposer(),
        domain_registry=domain_registry,
        workflow_registry=workflow_registry,
        planning_service=service,
        workflow_executor=DomainWorkflowExecutor(id_factory=lambda: "wf-id-mixed"),
        operation_availability=lambda op_id, domain_id: True,
        permission_ids_provider=lambda composition: ("perm.base", "perm.restricted"),
        prohibited_operation_ids_provider=lambda composition: (),
        approval_ids_provider=lambda composition: (),
        validation_ids_provider=lambda composition: (),
        authority_reference_ids_provider=lambda composition: ("authority:v1",),
        operation_definition_provider=lambda op_id: (
            op_def if op_id == "mixed.op" else None
        ),
    )

    context = DomainResolutionContext(
        id="ctx-mixed",
        user_input="Mixed work",
        goal_id="goal-mixed",
        actor="actor-mixed",
        available_domains=(DomainId(slug="mixed"),),
        authorized_domains=(DomainId(slug="mixed"),),
        explicit_domains=(DomainId(slug="mixed"),),
        resources=(
            DomainResolutionResource(
                id="r-mixed",
                resource_type="document",
                source="user",
                domain_ids=(DomainId(slug="mixed"),),
            ),
        ),
    )
    incoming = _incoming_request(
        id="req-mixed",
        goal_id="goal-mixed",
        agent_run_id="run-mixed",
        actor_id="actor-mixed",
        objective="Mixed work",
        permissions=["perm.base"],
        allowed_operations=["mixed.op"],
    )

    # Both workflows are in capability_view because Domain authority granted both
    # Sub-case 1: Requesting only the compatible workflow succeeds
    req_compatible = DomainPlannerWorkflowIntegrationRequest(
        request_id="int-req-compatible",
        resolution_context=context,
        planning_request=incoming,
        metadata={"requested_workflow_ids": ["mixed.compatible"]},
    )
    res_compatible = integrator.integrate(req_compatible)
    assert res_compatible.blocked is False
    assert res_compatible.selected_domain_workflow_ids == ("mixed.compatible",)
    assert service.plan_calls == 1

    # Sub-case 2: Requesting both (mixed set containing incompatible workflow) fails closed atomically
    req_mixed = DomainPlannerWorkflowIntegrationRequest(
        request_id="int-req-mixed",
        resolution_context=context,
        planning_request=incoming,
        metadata={"requested_workflow_ids": ["mixed.compatible", "mixed.incompatible"]},
    )
    res_mixed = integrator.integrate(req_mixed)
    assert "mixed.incompatible" in res_mixed.capability_view.available_workflow_ids
    assert "perm.restricted" not in res_mixed.prepared_planning_request.permissions
    assert res_mixed.blocked is True
    assert res_mixed.selected_domain_workflow_ids == ()
    assert res_mixed.plan is None
    assert "domain_workflow_unavailable" in res_mixed.reason_codes
    assert service.plan_calls == 1  # No additional planner call
    # MIXED_WORKFLOW_PERMISSION_AUTHORITY=PASS


# ── V7 remediation (V6 MAJOR-08/09): final workflow eligibility + approvals ─


def _project_request_with_workflow(workflow_id, incoming):
    return _project_request(
        planning_request=incoming,
        metadata={"requested_workflow_ids": [workflow_id]},
    )


def test_v7_real_project_feature_implementation_without_modify_code_blocked():
    """V7 MAJOR-08 RED A: ``feature_implementation`` without modify_code blocks.

    Real production ``project.feature_implementation`` requires the
    ``project.modify_code`` operation node. When ``file.modify`` is absent
    from final planning authority, ``project.modify_code`` is correctly
    excluded from the final operation candidates — and the workflow that
    requires it must then fail selection before planner invocation instead
    of being selected and planned unblocked.
    """
    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_workflow_graph()
    feature = workflow_registry.resolve_active("project.feature_implementation")
    assert feature.approval_gates == ("approval.file.modify",)
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _project_permission_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
        effective_permissions=("domain-permission:project:1.0.0",),
    )
    incoming = _incoming_request(
        id="req-042-v7-nomodify",
        goal_id="goal-042-project",
        agent_run_id="run-042-v7-nomodify",
        actor_id="actor-042",
        objective="Implement feature without code modification authority",
        permissions=["domain-permission:project:1.0.0"],
        allowed_operations=[
            "project.create_implementation_plan",
            "project.modify_code",
            "project.review_status",
        ],
    )
    result = integrator.integrate(
        _project_request_with_workflow("project.feature_implementation", incoming)
    )

    candidates = tuple(
        result.prepared_planning_request.metadata["operation_candidates"]
    )
    assert "project.modify_code" not in candidates
    assert "project.create_implementation_plan" in candidates
    assert result.selected_domain_workflow_ids == ()
    assert service.plan_calls == 0
    assert result.blocked is True
    assert result.plan is None
    assert "domain_workflow_unavailable" in result.reason_codes
    # REAL_PROJECT_FEATURE_IMPLEMENTATION_WITHOUT_MODIFY_CODE=BLOCKED


def test_v7_real_project_feature_implementation_with_modify_code_plans():
    """V7 MAJOR-08 RED B: fully eligible ``feature_implementation`` plans.

    With ``file.modify`` present in both the Domain and incoming permission
    authority, every workflow operation node is eligible under the final
    candidates, so the workflow stays selected and canonical planning
    succeeds.
    """
    from cmm.agent_runtime.enums import WorkflowPlanStatus

    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_workflow_graph()
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _project_permission_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
        effective_permissions=("domain-permission:project:1.0.0", "file.modify"),
    )
    incoming = _incoming_request(
        id="req-042-v7-modify",
        goal_id="goal-042-project",
        agent_run_id="run-042-v7-modify",
        actor_id="actor-042",
        objective="Implement feature with full authority",
        permissions=["domain-permission:project:1.0.0", "file.modify"],
        allowed_operations=[
            "project.create_implementation_plan",
            "project.modify_code",
            "project.review_status",
        ],
    )
    result = integrator.integrate(
        _project_request_with_workflow("project.feature_implementation", incoming)
    )

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ("project.feature_implementation",)
    assert service.plan_calls == 1
    assert result.plan.status == WorkflowPlanStatus.VALID
    assert result.plan.validation.is_valid
    candidates = tuple(
        result.prepared_planning_request.metadata["operation_candidates"]
    )
    assert {"project.create_implementation_plan", "project.modify_code"} <= set(
        candidates
    )
    # REAL_PROJECT_FEATURE_IMPLEMENTATION_WITH_MODIFY_CODE=PASS


def test_v7_workflow_required_operations_subset_of_effective_operations():
    """V7 MAJOR-08 RED C: workflow operation nodes ⊆ final effective operations.

    The invariant uses canonical ``WorkflowNodeType.EXECUTE_OPERATION``
    extraction over the selected workflow definition — never a hardcoded
    operation ID — and must hold for every selected workflow. When the
    invariant would be violated, the workflow is not selected at all.
    """
    from cmm.workflows.enums import WorkflowNodeType

    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_workflow_graph()
    _, _, service = _planning_stack()
    integrator = _project_permission_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
        effective_permissions=("domain-permission:project:1.0.0", "file.modify"),
    )
    incoming = _incoming_request(
        id="req-042-v7-subset",
        goal_id="goal-042-project",
        agent_run_id="run-042-v7-subset",
        actor_id="actor-042",
        objective="Implement feature with full authority",
        permissions=["domain-permission:project:1.0.0", "file.modify"],
        allowed_operations=[
            "project.create_implementation_plan",
            "project.modify_code",
            "project.review_status",
        ],
    )
    result = integrator.integrate(
        _project_request_with_workflow("project.feature_implementation", incoming)
    )

    assert result.blocked is False
    selected = result.selected_domain_workflow_ids
    candidates = set(result.prepared_planning_request.metadata["operation_candidates"])
    for workflow_id in selected:
        workflow = workflow_registry.resolve_active(workflow_id)
        required_operations = {
            node.operation_id
            for node in workflow.nodes
            if node.node_type is WorkflowNodeType.EXECUTE_OPERATION
            and node.operation_id
        }
        assert required_operations <= candidates
    # WORKFLOW_REQUIRED_OPERATIONS_SUBSET_OF_EFFECTIVE_OPERATIONS=PASS


def _resourced_workflow_integrator(service, *, enabled=True):
    """Focused canonical workflow graph declaring a workflow-level resource."""
    from cmm.domains.composer import DefaultDomainComposer
    from cmm.domains.contracts import DomainDefinition, DomainManifestId
    from cmm.domains.enums import DomainKind, DomainOperationType
    from cmm.domains.identifiers import DomainId
    from cmm.domains.operation_contracts import DomainOperationDefinition
    from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
    from cmm.domains.resolution_contracts import (
        DomainResolutionContext,
        DomainResolutionResource,
    )
    from cmm.domains.resolver import DefaultDomainResolver
    from cmm.domains.resolver_contracts import DomainScoringPolicy
    from cmm.domains.workflow_contracts import DomainWorkflowDefinition
    from cmm.domains.workflow_execution import DomainWorkflowExecutor
    from cmm.workflows.contracts import WorkflowNode

    domain_registry = DomainRegistry()
    domain_registry.register(
        DomainDefinition(
            id=DomainId.from_str("domain:resourced"),
            name="resourced",
            display_name="Resourced",
            version="1.0.0",
            kind=DomainKind.CORE,
            description="Resourced domain",
            manifest_id=DomainManifestId(slug="resourced", version="1.0.0"),
            enabled=True,
            operations=("resourced.op",),
            workflows=("resourced.flow",),
        )
    )
    domain_registry.enable("domain:resourced")

    op_def = DomainOperationDefinition(
        operation_id="resourced.op",
        domain_id="domain:resourced",
        version="1.0.0",
        name="Resourced Operation",
        description="Resourced Operation",
        operation_type=DomainOperationType.READ,
        reversible=True,
    )
    operation_registry = InMemoryDomainOperationRegistry(
        InMemoryAgentOperationRegistry()
    )
    operation_registry.register(op_def, _Implementation(op_def))

    workflow_registry = InMemoryDomainWorkflowRegistry()
    workflow_registry.register(
        DomainWorkflowDefinition(
            workflow_id="resourced.flow",
            domain_id="domain:resourced",
            version="1.0.0",
            name="Resourced Workflow",
            nodes=(
                WorkflowNode(
                    "start",
                    "execute_operation",
                    "Start",
                    operation_id="resourced.op",
                    operation_version="1.0.0",
                ),
                WorkflowNode("finish", "complete", "Finish", dependencies=("start",)),
            ),
            required_resources=("res-alpha",),
            enabled=enabled,
        )
    )

    context = DomainResolutionContext(
        id="ctx-resourced",
        user_input="Resourced work",
        goal_id="goal-resourced",
        actor="actor-resourced",
        available_domains=(DomainId(slug="resourced"),),
        authorized_domains=(DomainId(slug="resourced"),),
        explicit_domains=(DomainId(slug="resourced"),),
        resources=(
            DomainResolutionResource(
                id="r-resourced",
                resource_type="document",
                source="user",
                domain_ids=(DomainId(slug="resourced"),),
            ),
        ),
    )
    incoming = _incoming_request(
        id="req-resourced",
        goal_id="goal-resourced",
        agent_run_id="run-resourced",
        actor_id="actor-resourced",
        objective="Resourced work",
        allowed_operations=["resourced.op"],
    )
    integrator = DefaultDomainPlannerWorkflowIntegrator(
        resolver=DefaultDomainResolver(
            scoring_policy=DomainScoringPolicy(
                max_supporting_domains=0, supporting_margin=100.0
            )
        ),
        composer=DefaultDomainComposer(),
        domain_registry=domain_registry,
        workflow_registry=workflow_registry,
        planning_service=service,
        workflow_executor=DomainWorkflowExecutor(id_factory=lambda: "wf-id-resourced"),
        operation_availability=lambda op_id, domain_id: (
            operation_registry.resolve_active(op_id, required=False) is not None
        ),
        permission_ids_provider=lambda composition: (),
        prohibited_operation_ids_provider=lambda composition: (),
        approval_ids_provider=lambda composition: (),
        validation_ids_provider=lambda composition: (),
        authority_reference_ids_provider=lambda composition: ("authority:v1",),
        operation_definition_provider=lambda operation_id: (
            op_def if operation_id == "resourced.op" else None
        ),
    )
    request = DomainPlannerWorkflowIntegrationRequest(
        request_id="int-req-resourced",
        resolution_context=context,
        planning_request=incoming,
        metadata={"requested_workflow_ids": ["resourced.flow"]},
    )
    return integrator, request


def test_v7_workflow_final_resource_compatibility():
    """V7 MAJOR-08 RED D: workflow resources must hold under final authority.

    No production workflow currently declares a workflow-level
    ``required_resources`` entry, so per the remediation contract this
    focused test uses the official in-memory canonical
    ``DomainWorkflowDefinition`` contract (production coverage explicitly
    absent). The final planning resource authority is the canonical
    planning request's own ``resource_ids``; a workflow whose required
    resources exceed it is not plannable. Providing the required resource
    makes the same workflow plannable.
    """
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator, request = _resourced_workflow_integrator(service)

    # The request declares no resources: the workflow requirement is unmet.
    blocked = integrator.integrate(request)
    assert "resourced.flow" in blocked.capability_view.available_workflow_ids
    assert blocked.blocked is True
    assert blocked.plan is None
    assert blocked.selected_domain_workflow_ids == ()
    assert service.plan_calls == 0
    assert "domain_workflow_unavailable" in blocked.reason_codes

    # The same workflow with the resource present in the canonical request.
    from dataclasses import replace

    from cmm.agent_runtime.enums import WorkflowPlanStatus

    _, _, service2 = _planning_stack()
    integrator2, request2 = _resourced_workflow_integrator(service2)
    granted = integrator2.integrate(
        replace(
            request2,
            request_id="int-req-resourced-granted",
            planning_request=replace(
                request2.planning_request, resource_ids=["res-alpha"]
            ),
        )
    )
    assert granted.blocked is False
    assert granted.selected_domain_workflow_ids == ("resourced.flow",)
    assert granted.plan.status == WorkflowPlanStatus.VALID
    # WORKFLOW_FINAL_RESOURCE_COMPATIBILITY=PASS


def _supporting_workflow_integrator(service, *, with_helper: bool):
    """Focused canonical workflow graph declaring a supporting Domain.

    ``main.flow`` canonically requires supporting domain ``domain:helper``.
    When ``with_helper`` is true, the resolution context carries helper
    evidence so the composition includes it; otherwise the effective
    composition is ``domain:main`` only.
    """
    from cmm.domains.composer import DefaultDomainComposer
    from cmm.domains.contracts import DomainDefinition, DomainManifestId
    from cmm.domains.enums import DomainKind, DomainOperationType
    from cmm.domains.identifiers import DomainId
    from cmm.domains.operation_contracts import DomainOperationDefinition
    from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
    from cmm.domains.resolution_contracts import (
        DomainResolutionContext,
        DomainResolutionResource,
    )
    from cmm.domains.resolver import DefaultDomainResolver
    from cmm.domains.resolver_contracts import DomainScoringPolicy
    from cmm.domains.workflow_contracts import DomainWorkflowDefinition
    from cmm.domains.workflow_execution import DomainWorkflowExecutor
    from cmm.workflows.contracts import WorkflowNode

    domain_registry = DomainRegistry()
    domain_registry.register(
        DomainDefinition(
            id=DomainId.from_str("domain:main"),
            name="main",
            display_name="Main",
            version="1.0.0",
            kind=DomainKind.CORE,
            description="Main domain",
            manifest_id=DomainManifestId(slug="main", version="1.0.0"),
            enabled=True,
            operations=("main.op",),
            workflows=("main.flow",),
        )
    )
    domain_registry.register(
        DomainDefinition(
            id=DomainId.from_str("domain:helper"),
            name="helper",
            display_name="Helper",
            version="1.0.0",
            kind=DomainKind.CORE,
            description="Helper domain",
            manifest_id=DomainManifestId(slug="helper", version="1.0.0"),
            enabled=True,
            operations=("helper.op",),
        )
    )
    domain_registry.enable("domain:main")
    domain_registry.enable("domain:helper")

    op_def = DomainOperationDefinition(
        operation_id="main.op",
        domain_id="domain:main",
        version="1.0.0",
        name="Main Operation",
        description="Main Operation",
        operation_type=DomainOperationType.READ,
        reversible=True,
    )
    operation_registry = InMemoryDomainOperationRegistry(
        InMemoryAgentOperationRegistry()
    )
    operation_registry.register(op_def, _Implementation(op_def))

    workflow_registry = InMemoryDomainWorkflowRegistry()
    workflow_registry.register(
        DomainWorkflowDefinition(
            workflow_id="main.flow",
            domain_id="domain:main",
            version="1.0.0",
            name="Main Workflow",
            nodes=(
                WorkflowNode(
                    "start",
                    "execute_operation",
                    "Start",
                    operation_id="main.op",
                    operation_version="1.0.0",
                ),
                WorkflowNode("finish", "complete", "Finish", dependencies=("start",)),
            ),
            supporting_domain_ids=("domain:helper",),
        )
    )

    resources: tuple = ()
    if with_helper:
        resources = (
            DomainResolutionResource(
                id="r-helper",
                resource_type="document",
                source="user",
                domain_ids=(DomainId(slug="helper"),),
            ),
        )
    context = DomainResolutionContext(
        id="ctx-supporting",
        user_input="Main work with helper support",
        goal_id="goal-supporting",
        actor="actor-supporting",
        available_domains=(DomainId(slug="main"), DomainId(slug="helper")),
        authorized_domains=(DomainId(slug="main"), DomainId(slug="helper")),
        explicit_domains=(DomainId(slug="main"),),
        resources=resources,
    )
    incoming = _incoming_request(
        id="req-supporting",
        goal_id="goal-supporting",
        agent_run_id="run-supporting",
        actor_id="actor-supporting",
        objective="Main work with helper support",
        allowed_operations=["main.op"],
    )
    integrator = DefaultDomainPlannerWorkflowIntegrator(
        resolver=DefaultDomainResolver(
            scoring_policy=DomainScoringPolicy(
                max_supporting_domains=1, supporting_margin=100.0
            )
        ),
        composer=DefaultDomainComposer(),
        domain_registry=domain_registry,
        workflow_registry=workflow_registry,
        planning_service=service,
        workflow_executor=DomainWorkflowExecutor(id_factory=lambda: "wf-id-supporting"),
        operation_availability=lambda op_id, domain_id: (
            operation_registry.resolve_active(op_id, required=False) is not None
        ),
        permission_ids_provider=lambda composition: (),
        prohibited_operation_ids_provider=lambda composition: (),
        approval_ids_provider=lambda composition: (),
        validation_ids_provider=lambda composition: (),
        authority_reference_ids_provider=lambda composition: ("authority:v1",),
        operation_definition_provider=lambda operation_id: (
            op_def if operation_id == "main.op" else None
        ),
    )
    request = DomainPlannerWorkflowIntegrationRequest(
        request_id="int-req-supporting",
        resolution_context=context,
        planning_request=incoming,
        metadata={"requested_workflow_ids": ["main.flow"]},
    )
    return integrator, request


def test_v7_workflow_final_composition_compatibility():
    """V7 MAJOR-08 RED E: workflow Domains must exist in current composition.

    A workflow whose canonical supporting Domain is absent from the current
    effective composition is not plannable (no parallel composition
    resolver: the canonical composer owns composition truth). When the
    composition includes the supporting Domain, the same workflow plans.
    """
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator, request = _supporting_workflow_integrator(service, with_helper=False)

    blocked = integrator.integrate(request)
    assert "main.flow" in blocked.capability_view.available_workflow_ids
    assert blocked.blocked is True
    assert blocked.plan is None
    assert blocked.selected_domain_workflow_ids == ()
    assert service.plan_calls == 0
    assert "domain_workflow_unavailable" in blocked.reason_codes

    from cmm.agent_runtime.enums import WorkflowPlanStatus

    _, _, service2 = _planning_stack()
    integrator2, request2 = _supporting_workflow_integrator(service2, with_helper=True)
    granted = integrator2.integrate(request2)

    assert granted.blocked is False
    assert granted.selected_domain_workflow_ids == ("main.flow",)
    assert "domain:helper" in granted.composition.supporting_domains
    assert granted.plan.status == WorkflowPlanStatus.VALID
    # WORKFLOW_FINAL_COMPOSITION_COMPATIBILITY=PASS


def test_v7_workflow_approval_obligation_representable():
    """V7 RED F: outstanding approval never blocks a representable workflow.

    ``project.feature_implementation`` with every availability constraint
    satisfied stays selected and plannable while its canonical approval
    gate is outstanding: the obligation is projected into the plan instead
    of being treated as granted or as unavailability.
    """
    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_workflow_graph()
    _, _, service = _planning_stack()
    integrator = _project_permission_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
        effective_permissions=("domain-permission:project:1.0.0", "file.modify"),
    )
    incoming = _incoming_request(
        id="req-042-v7-approval-repr",
        goal_id="goal-042-project",
        agent_run_id="run-042-v7-approval-repr",
        actor_id="actor-042",
        objective="Implement feature with outstanding approval",
        permissions=["domain-permission:project:1.0.0", "file.modify"],
        allowed_operations=[
            "project.create_implementation_plan",
            "project.modify_code",
            "project.review_status",
        ],
    )
    result = integrator.integrate(
        _project_request_with_workflow("project.feature_implementation", incoming)
    )

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ("project.feature_implementation",)
    assert "approval.file.modify" in result.prepared_planning_request.required_approvals
    assert result.plan is not None
    assert any(
        "approval.file.modify" in node.required_approvers
        for node in result.plan.approval_nodes
    )
    # No approval is synthesized as granted: the gate stays a pending
    # canonical obligation on the plan.
    assert all(node.pending for node in result.plan.approval_nodes)
    # WORKFLOW_APPROVAL_OBLIGATION_REPRESENTABLE=PASS


def test_v7_unselected_workflow_approval_gate_leakage_zero():
    """V7 MAJOR-09 RED G: unselected workflow gates never leak plan-wide.

    Real production Project Domain: only ``project.review_status`` is
    planned and no workflow is selected, while approval-gated workflows
    (``project.feature_implementation`` and friends) remain available. The
    ``approval.file.modify`` gate belongs only to those unselected
    workflows and must not appear anywhere in the prepared plan.
    """
    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_workflow_graph()
    _, _, service = _planning_stack()
    integrator = _project_permission_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
        effective_permissions=("domain-permission:project:1.0.0",),
    )
    incoming = _incoming_request(
        id="req-042-v7-leak",
        goal_id="goal-042-project",
        agent_run_id="run-042-v7-leak",
        actor_id="actor-042",
        objective="Review project status",
        permissions=["domain-permission:project:1.0.0"],
        allowed_operations=["project.review_status"],
    )
    result = integrator.integrate(_project_request(planning_request=incoming))

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ()
    assert "project.feature_implementation" in (
        result.capability_view.available_workflow_ids
    )
    assert "approval.file.modify" not in (
        result.prepared_planning_request.required_approvals
    )
    assert result.plan is not None
    leaking = [
        node
        for node in result.plan.approval_nodes
        if "approval.file.modify" in node.required_approvers
    ]
    assert leaking == []
    # UNSELECTED_WORKFLOW_APPROVAL_GATE_LEAKAGE=0


def test_v7_selected_workflow_approval_gate_projected():
    """V7 MAJOR-09 RED H: selected workflow gates stay projected.

    When ``project.feature_implementation`` is selected with all final
    availability constraints satisfied, its ``approval.file.modify`` gate
    remains an additive plan obligation and the canonical approval nodes
    trace the exact approval ID.
    """
    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_workflow_graph()
    _, _, service = _planning_stack()
    integrator = _project_permission_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
        effective_permissions=("domain-permission:project:1.0.0", "file.modify"),
    )
    incoming = _incoming_request(
        id="req-042-v7-projected",
        goal_id="goal-042-project",
        agent_run_id="run-042-v7-projected",
        actor_id="actor-042",
        objective="Implement feature with full authority",
        permissions=["domain-permission:project:1.0.0", "file.modify"],
        allowed_operations=[
            "project.create_implementation_plan",
            "project.modify_code",
            "project.review_status",
        ],
    )
    result = integrator.integrate(
        _project_request_with_workflow("project.feature_implementation", incoming)
    )

    assert result.blocked is False
    assert "project.feature_implementation" in result.selected_domain_workflow_ids
    assert "approval.file.modify" in result.prepared_planning_request.required_approvals
    assert result.plan is not None
    assert any(
        "approval.file.modify" in node.required_approvers
        and "approval.file.modify" in node.metadata.get("approval_requirement_ids", [])
        for node in result.plan.approval_nodes
    )
    # SELECTED_WORKFLOW_APPROVAL_GATE_PROJECTED=PASS


def test_v7_incoming_global_approval_requirements_preserved():
    """V7 RED I: incoming canonical approval requirements stay additive.

    An unrelated incoming approval obligation survives unchanged while no
    workflow is selected, and no workflow-only gate is added on top.
    """
    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_workflow_graph()
    _, _, service = _planning_stack()
    integrator = _project_permission_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
        effective_permissions=("domain-permission:project:1.0.0",),
    )
    incoming = _incoming_request(
        id="req-042-v7-incoming",
        goal_id="goal-042-project",
        agent_run_id="run-042-v7-incoming",
        actor_id="actor-042",
        objective="Review project status under a global approval",
        permissions=["domain-permission:project:1.0.0"],
        allowed_operations=["project.review_status"],
        required_approvals=["approval.global.example"],
    )
    result = integrator.integrate(_project_request(planning_request=incoming))

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ()
    approvals = result.prepared_planning_request.required_approvals
    assert "approval.global.example" in approvals
    assert "approval.file.modify" not in approvals
    assert any(
        "approval.global.example" in node.required_approvers
        for node in result.plan.approval_nodes
    )
    # INCOMING_GLOBAL_APPROVAL_REQUIREMENTS_PRESERVED=PASS


def test_v7_operation_specific_approval_requirements_preserved():
    """V7 RED J: operation-specific approvals stay traceable.

    The production ``project.modify_code`` operation canonically requires
    approval through the existing V1 semantics. With no workflow selected,
    the planned operation still carries ``requires_approval`` and the
    canonical approval node traces the injected composition approval ID —
    the leakage fix must not strip operation-level obligations.
    """
    (
        domain_registry,
        _operation_registry_unused,
        workflow_registry,
        definitions,
        availability,
    ) = _project_workflow_graph()
    assert definitions["project.modify_code"].requires_approval is True
    _, _, service = _planning_stack()
    incoming = _incoming_request(
        id="req-042-v7-opspecific",
        goal_id="goal-042-project",
        agent_run_id="run-042-v7-opspecific",
        actor_id="actor-042",
        objective="Modify project code under operation approval",
        permissions=["file.modify"],
        allowed_operations=["project.modify_code"],
    )
    from cmm.domains.composer import DefaultDomainComposer
    from cmm.domains.resolver import DefaultDomainResolver
    from cmm.domains.resolver_contracts import DomainScoringPolicy
    from cmm.domains.workflow_execution import DomainWorkflowExecutor

    integrator = DefaultDomainPlannerWorkflowIntegrator(
        resolver=DefaultDomainResolver(
            scoring_policy=DomainScoringPolicy(
                max_supporting_domains=0, supporting_margin=100.0
            )
        ),
        composer=DefaultDomainComposer(),
        domain_registry=domain_registry,
        workflow_registry=workflow_registry,
        planning_service=service,
        workflow_executor=DomainWorkflowExecutor(id_factory=lambda: "wf-id-opspecific"),
        operation_availability=availability,
        permission_ids_provider=lambda composition: (
            "file.modify",
            "approval.review-board",
        ),
        prohibited_operation_ids_provider=lambda composition: (),
        approval_ids_provider=lambda composition: ("approval.review-board",),
        validation_ids_provider=lambda composition: (),
        authority_reference_ids_provider=lambda composition: ("authority:v1",),
        operation_definition_provider=lambda operation_id: definitions.get(
            operation_id
        ),
    )
    result = integrator.integrate(_project_request(planning_request=incoming))

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ()
    planned = [operation for operation in result.plan.operations]
    assert planned and all(
        operation.operation_name == "project.modify_code" for operation in planned
    )
    assert all(operation.requires_approval for operation in planned)
    assert any(
        "approval.review-board" in node.required_approvers
        for node in result.plan.approval_nodes
    )
    # OPERATION_SPECIFIC_APPROVAL_REQUIREMENTS_PRESERVED=PASS


def test_v7_workflow_planning_eligibility_matrix():
    """V7: encode the complete workflow planning eligibility table.

    | Condition                                | Workflow planning result      |
    |------------------------------------------|-------------------------------|
    | inactive / unregistered                  | BLOCK                         |
    | required planning permission missing     | BLOCK                         |
    | required operation unavailable           | BLOCK                         |
    | required resource unavailable            | BLOCK                         |
    | required/supporting Domain incompatible  | BLOCK                         |
    | approval outstanding but representable   | ALLOW + approval obligation   |
    | all constraints satisfied                | ALLOW                         |
    | available-but-unselected workflow gate   | DO NOT PROJECT                |
    """
    # Row 1: unregistered workflow → BLOCK.
    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
    ) = _project_workflow_graph()
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _project_permission_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service,
        effective_permissions=("domain-permission:project:1.0.0",),
    )
    incoming = _incoming_request(
        id="req-042-v7-matrix-1",
        goal_id="goal-042-project",
        agent_run_id="run-042-v7-matrix-1",
        actor_id="actor-042",
        objective="Request unregistered workflow",
        permissions=["domain-permission:project:1.0.0"],
        allowed_operations=["project.review_status"],
    )
    result = integrator.integrate(
        _project_request(
            planning_request=incoming,
            metadata={"requested_workflow_ids": ["project.does_not_exist"]},
        )
    )
    assert result.blocked is True
    assert result.plan is None
    assert service.plan_calls == 0
    # Matrix row 1: inactive/unregistered → BLOCK

    # Row 1b: disabled workflow → BLOCK (registry truth: not resolvable active).
    _, _, service_disabled = _planning_stack(_CountingPlanningService)
    disabled_integrator, disabled_request = _resourced_workflow_integrator(
        service_disabled, enabled=False
    )
    disabled_result = disabled_integrator.integrate(disabled_request)
    assert disabled_result.blocked is True
    assert disabled_result.plan is None
    assert disabled_result.selected_domain_workflow_ids == ()
    assert service_disabled.plan_calls == 0
    # Matrix row 1: inactive → BLOCK

    # Row 2: required planning permission missing → BLOCK.
    _, _, service2 = _planning_stack(_CountingPlanningService)
    integrator2 = _project_permission_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service2,
        effective_permissions=("domain-permission:project:1.0.0",),
    )
    incoming2 = _incoming_request(
        id="req-042-v7-matrix-2",
        goal_id="goal-042-project",
        agent_run_id="run-042-v7-matrix-2",
        actor_id="actor-042",
        objective="Setup project without permission",
        permissions=[],
        allowed_operations=["project.create_project_overview"],
    )
    result2 = integrator2.integrate(
        _project_request_with_workflow("project.project_setup", incoming2)
    )
    assert result2.blocked is True
    assert result2.plan is None
    assert service2.plan_calls == 0
    # Matrix row 2: required planning permission missing → BLOCK

    # Row 3: required operation unavailable under final authority → BLOCK.
    incoming3 = _incoming_request(
        id="req-042-v7-matrix-3",
        goal_id="goal-042-project",
        agent_run_id="run-042-v7-matrix-3",
        actor_id="actor-042",
        objective="Implement feature without modify authority",
        permissions=["domain-permission:project:1.0.0"],
        allowed_operations=[
            "project.create_implementation_plan",
            "project.modify_code",
            "project.review_status",
        ],
    )
    result3 = integrator2.integrate(
        _project_request_with_workflow("project.feature_implementation", incoming3)
    )
    assert result3.blocked is True
    assert result3.plan is None
    assert service2.plan_calls == 0
    # Matrix row 3: required operation unavailable → BLOCK

    # Row 4: required resource unavailable → BLOCK.
    _, _, service4 = _planning_stack(_CountingPlanningService)
    resource_integrator, resource_request = _resourced_workflow_integrator(service4)
    result4 = resource_integrator.integrate(resource_request)
    assert result4.blocked is True
    assert result4.plan is None
    assert service4.plan_calls == 0
    # Matrix row 4: required resource unavailable → BLOCK

    # Row 5: required supporting Domain incompatible → BLOCK.
    _, _, service5 = _planning_stack(_CountingPlanningService)
    composition_integrator, composition_request = _supporting_workflow_integrator(
        service5, with_helper=False
    )
    result5 = composition_integrator.integrate(composition_request)
    assert result5.blocked is True
    assert result5.plan is None
    assert service5.plan_calls == 0
    # Matrix row 5: required/supporting Domain incompatible → BLOCK

    # Row 6: approval outstanding but representable → ALLOW + obligation.
    _, _, service6 = _planning_stack()
    integrator6 = _project_permission_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        availability,
        service6,
        effective_permissions=("domain-permission:project:1.0.0", "file.modify"),
    )
    incoming6 = _incoming_request(
        id="req-042-v7-matrix-6",
        goal_id="goal-042-project",
        agent_run_id="run-042-v7-matrix-6",
        actor_id="actor-042",
        objective="Implement feature with outstanding approval",
        permissions=["domain-permission:project:1.0.0", "file.modify"],
        allowed_operations=[
            "project.create_implementation_plan",
            "project.modify_code",
            "project.review_status",
        ],
    )
    result6 = integrator6.integrate(
        _project_request_with_workflow("project.feature_implementation", incoming6)
    )
    assert result6.blocked is False
    assert result6.selected_domain_workflow_ids == ("project.feature_implementation",)
    assert (
        "approval.file.modify" in result6.prepared_planning_request.required_approvals
    )
    # Matrix row 6: approval outstanding but representable → ALLOW + obligation

    # Row 7: all constraints satisfied → ALLOW.
    assert result6.plan is not None
    assert result6.plan.validation.is_valid
    # Matrix row 7: all constraints satisfied → ALLOW

    # Row 8: available-but-unselected workflow approval gate → DO NOT PROJECT.
    incoming8 = _incoming_request(
        id="req-042-v7-matrix-8",
        goal_id="goal-042-project",
        agent_run_id="run-042-v7-matrix-8",
        actor_id="actor-042",
        objective="Review project status",
        permissions=["domain-permission:project:1.0.0"],
        allowed_operations=["project.review_status"],
    )
    result8 = integrator6.integrate(_project_request(planning_request=incoming8))
    assert result8.blocked is False
    assert result8.selected_domain_workflow_ids == ()
    assert "approval.file.modify" not in (
        result8.prepared_planning_request.required_approvals
    )
    # Matrix row 8: available-but-unselected workflow gate → DO NOT PROJECT

    # WORKFLOW_PLANNING_ELIGIBILITY_MATRIX=PASS


# ── Phase 10.42 V8 — workflow graph planning obligations ──────────────────
#
# V7 MAJOR-10: node-level REQUEST_APPROVAL / approval_gate obligations of
# selected workflows must be projected into the canonical planning approval
# representation.
# V7 MAJOR-11: required INVOKE_SUBWORKFLOW dependencies must be resolved and
# final-authority eligible before a parent workflow can be planned.


def _production_pack_graph(slug):
    """Real production Domain Pack graph: domain, operations, workflows live."""
    import importlib

    definition_builder = getattr(
        importlib.import_module(f"cmm.domains.{slug}.definition"),
        f"build_{slug}_domain_definition",
    )
    operations_builder = getattr(
        importlib.import_module(f"cmm.domains.{slug}.operations"),
        f"build_{slug}_operation_definitions",
    )
    workflows_builder = getattr(
        importlib.import_module(f"cmm.domains.{slug}.workflows"),
        f"build_{slug}_workflow_definitions",
    )
    domain_registry = DomainRegistry()
    definition = definition_builder()
    domain_registry.register(definition)
    domain_registry.enable(str(definition.id))
    definitions = {
        definition.operation_id: definition
        for definition in operations_builder()
    }
    operation_registry = InMemoryDomainOperationRegistry(
        InMemoryAgentOperationRegistry()
    )
    for definition in definitions.values():
        operation_registry.register(definition, _Implementation(definition))
    workflow_registry = InMemoryDomainWorkflowRegistry()
    for workflow in workflows_builder():
        workflow_registry.register(workflow)
    return domain_registry, operation_registry, workflow_registry, definitions


def _pack_request(slug, **overrides):
    from cmm.domains.resolution_contracts import (
        DomainResolutionContext,
        DomainResolutionResource,
    )

    values = {
        "request_id": f"int-req-042-{slug}",
        "resolution_context": DomainResolutionContext(
            id=f"ctx-042-{slug}",
            user_input=f"Plan a {slug} workflow",
            goal_id=f"goal-042-{slug}",
            actor="actor-042",
            available_domains=(DomainId(slug=slug),),
            authorized_domains=(DomainId(slug=slug),),
            explicit_domains=(DomainId(slug=slug),),
            resources=(
                DomainResolutionResource(
                    id=f"r-{slug}",
                    resource_type="document",
                    source="user",
                    domain_ids=(DomainId(slug=slug),),
                ),
            ),
        ),
        "planning_request": _incoming_request(
            id=f"req-042-{slug}",
            goal_id=f"goal-042-{slug}",
            agent_run_id=f"run-042-{slug}",
            actor_id="actor-042",
            objective=f"Plan a {slug} workflow",
        ),
        "metadata": {},
    }
    values.update(overrides)
    return DomainPlannerWorkflowIntegrationRequest(**values)


def _pack_integrator(
    domain_registry,
    operation_registry,
    workflow_registry,
    definitions,
    service,
    *,
    effective_permissions=(),
    prohibited=(),
):
    """Real-pack integrator with explicit permission authority."""
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
        workflow_executor=DomainWorkflowExecutor(id_factory=lambda: "wf-id-pack"),
        operation_availability=lambda operation_id, domain_id: (
            operation_registry.resolve_active(operation_id, required=False)
            is not None
        ),
        permission_ids_provider=lambda composition: tuple(effective_permissions),
        prohibited_operation_ids_provider=lambda composition: tuple(prohibited),
        approval_ids_provider=lambda composition: (),
        validation_ids_provider=lambda composition: (),
        authority_reference_ids_provider=lambda composition: ("authority:v1",),
        operation_definition_provider=lambda operation_id: definitions.get(
            operation_id
        ),
    )


def _subworkflow_fixtures():
    """Canonical in-memory python pack for subworkflow eligibility tests."""
    domain_registry = DomainRegistry()
    domain_registry.register(
        _definition(
            "python",
            operations=("python.find_symbol", "python.list_imports"),
            workflows=(
                "python.sub_parent",
                "python.opt_parent",
                "python.cycle_a",
                "python.cycle_b",
                "python.matrix",
            ),
        )
    )
    domain_registry.enable("domain:python")
    domain_registry.register(
        _definition(
            "filesystem",
            operations=("filesystem.read_file", "filesystem.exists"),
            workflows=(),
        )
    )
    domain_registry.enable("domain:filesystem")
    operation_registry = InMemoryDomainOperationRegistry(
        InMemoryAgentOperationRegistry()
    )
    for operation_id in ("python.find_symbol", "python.list_imports"):
        definition = _operation(operation_id, "domain:python")
        operation_registry.register(definition, _Implementation(definition))
    for operation_id in ("filesystem.read_file", "filesystem.exists"):
        definition = _operation(operation_id, "domain:filesystem")
        operation_registry.register(definition, _Implementation(definition))
    workflow_registry = InMemoryDomainWorkflowRegistry()
    return domain_registry, operation_registry, workflow_registry


def _sub_parent_workflow(
    subworkflow_id="python.sub_child",
    subworkflow_version="1.0.0",
    *,
    required=True,
    workflow_id="python.sub_parent",
):
    return DomainWorkflowDefinition(
        workflow_id,
        "domain:python",
        "1.0.0",
        "SubParent",
        nodes=(
            WorkflowNode(
                "child",
                "invoke_subworkflow",
                "Child",
                subworkflow_id=subworkflow_id,
                subworkflow_version=subworkflow_version,
                required=required,
            ),
            WorkflowNode("finish", "complete", "Finish", dependencies=("child",)),
        ),
    )


def _sub_child_workflow(
    operation_id="python.find_symbol",
    *,
    version="1.0.0",
    workflow_id="python.sub_child",
    permissions=(),
    gates=(),
):
    return DomainWorkflowDefinition(
        workflow_id,
        "domain:python",
        version,
        "SubChild",
        required_permissions=tuple(permissions),
        approval_gates=tuple(gates),
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


def _subworkflow_request(metadata_overrides):
    metadata = {"requested_workflow_ids": ["python.sub_parent"]}
    metadata.update(metadata_overrides)
    return _integration_request_5(metadata=metadata)


def test_v8_red_a_real_relationships_node_approval_projection():
    """V8 MAJOR-10 RED A: real node-level approval gate must be projected.

    ``relationships.decision_support`` carries its approval obligation only
    on the canonical ``REQUEST_APPROVAL`` node
    (``approval_gate="relationships.decision_support"``) while
    ``DomainWorkflowDefinition.approval_gates == ()``. Selecting the
    workflow must project that exact node gate into the prepared planning
    request and the canonical plan approval nodes.
    """
    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
    ) = _production_pack_graph("relationships")
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _pack_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        service,
    )
    incoming = _incoming_request(
        id="req-042-v8-rel",
        goal_id="goal-042-relationships",
        agent_run_id="run-042-v8-rel",
        actor_id="actor-042",
        objective="Compare relationship options under explicit criteria",
        permissions=[],
        allowed_operations=[
            "relationships.identify_needs",
            "relationships.track_open_questions",
        ],
    )
    result = integrator.integrate(
        _pack_request(
            "relationships",
            planning_request=incoming,
            metadata={
                "requested_workflow_ids": ["relationships.decision_support"],
            },
        )
    )

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ("relationships.decision_support",)
    assert "relationships.decision_support" in (
        result.prepared_planning_request.required_approvals
    )
    assert result.plan is not None
    assert any(
        "relationships.decision_support" in node.required_approvers
        and "relationships.decision_support"
        in node.metadata.get("approval_requirement_ids", [])
        for node in result.plan.approval_nodes
    )
    # REAL_RELATIONSHIPS_DECISION_SUPPORT_NODE_APPROVAL=PROJECTED


def test_v8_red_b_real_health_node_approval_projection():
    """V8 MAJOR-10 RED B: real Health node gate projected exactly once.

    ``health.medication_change_review`` declares the node gate
    ``health.medication_review`` only. The projected obligation must appear
    exactly once, deterministically, and remain traceable on the plan.
    """
    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
    ) = _production_pack_graph("health")
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _pack_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        service,
    )
    incoming = _incoming_request(
        id="req-042-v8-health",
        goal_id="goal-042-health",
        agent_run_id="run-042-v8-health",
        actor_id="actor-042",
        objective="Review medication changes",
        permissions=[],
        allowed_operations=[
            "health.review_medication_changes",
            "health.prepare_questions",
        ],
    )
    result = integrator.integrate(
        _pack_request(
            "health",
            planning_request=incoming,
            metadata={
                "requested_workflow_ids": ["health.medication_change_review"],
            },
        )
    )

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == (
        "health.medication_change_review",
    )
    approvals = result.prepared_planning_request.required_approvals
    assert approvals.count("health.medication_review") == 1
    assert result.plan is not None
    assert any(
        "health.medication_review" in node.required_approvers
        and "health.medication_review"
        in node.metadata.get("approval_requirement_ids", [])
        for node in result.plan.approval_nodes
    )
    # REAL_HEALTH_MEDICATION_REVIEW_NODE_APPROVAL=PROJECTED


def test_v8_unselected_node_approval_gate_leakage_zero():
    """V8 MAJOR-10: unselected node-level gates never leak into a plan.

    Real production Relationships Domain plans an unrelated permitted
    operation while all node-approval workflows remain available but
    unselected: no ``relationships.*`` node gate may appear in the prepared
    requirements or the plan's approval nodes.
    """
    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
    ) = _production_pack_graph("relationships")
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _pack_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        service,
    )
    incoming = _incoming_request(
        id="req-042-v8-rel-leak",
        goal_id="goal-042-relationships",
        agent_run_id="run-042-v8-rel-leak",
        actor_id="actor-042",
        objective="Review relationship boundaries without selecting a workflow",
        permissions=[],
        allowed_operations=["relationships.review_boundaries"],
    )
    result = integrator.integrate(
        _pack_request("relationships", planning_request=incoming)
    )

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ()
    leaking = [
        approval
        for approval in result.prepared_planning_request.required_approvals
        if approval.startswith("relationships.")
    ]
    assert leaking == []
    assert result.plan is not None
    assert all(
        not any(
            approval.startswith("relationships.")
            for approval in node.required_approvers
        )
        for node in result.plan.approval_nodes
    )
    # UNSELECTED_NODE_APPROVAL_GATE_LEAKAGE=0


def test_v8_workflow_approval_deduplication():
    """V8 MAJOR-10 RED D: duplicate approval sources stay one obligation.

    ``project.feature_implementation`` carries ``approval.file.modify`` both
    at workflow level and on an approval node. The projected canonical
    approval set must contain the ID exactly once with stable ordering.
    """
    (
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
    ) = _production_pack_graph("project")
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _pack_integrator(
        domain_registry,
        operation_registry,
        workflow_registry,
        definitions,
        service,
        effective_permissions=("domain-permission:project:1.0.0", "file.modify"),
    )
    incoming = _incoming_request(
        id="req-042-v8-dedup",
        goal_id="goal-042-project",
        agent_run_id="run-042-v8-dedup",
        actor_id="actor-042",
        objective="Implement feature with deduplicated approval authority",
        permissions=["domain-permission:project:1.0.0", "file.modify"],
        allowed_operations=[
            "project.create_implementation_plan",
            "project.modify_code",
            "project.review_status",
        ],
    )
    result = integrator.integrate(
        _pack_request(
            "project",
            planning_request=incoming,
            metadata={
                "requested_workflow_ids": ["project.feature_implementation"],
            },
        )
    )

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ("project.feature_implementation",)
    approvals = result.prepared_planning_request.required_approvals
    assert approvals.count("approval.file.modify") == 1
    assert approvals == sorted(set(approvals))
    # WORKFLOW_APPROVAL_DEDUPLICATION=PASS


def test_v8_red_e_missing_required_subworkflow_blocks_before_planner():
    """V8 MAJOR-11 RED E: missing required child blocks before the planner.

    Canonical in-memory parent ``python.sub_parent`` requires
    ``python.sub_child@1.0.0`` which is not registered. The parent must be
    blocked deterministically before planner invocation and never returned
    as a valid selected workflow.
    """
    domain_registry, operation_registry, workflow_registry = _subworkflow_fixtures()
    workflow_registry.register(_sub_parent_workflow())
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _integrator_5(
        domain_registry, operation_registry, workflow_registry, service
    )
    result = integrator.integrate(_subworkflow_request({}))

    assert result.blocked is True
    assert result.plan is None
    assert result.selected_domain_workflow_ids == ()
    assert service.plan_calls == 0
    assert "domain_workflow_dependency_not_available" in result.reason_codes
    # MISSING_REQUIRED_SUBWORKFLOW_BLOCKS_BEFORE_PLANNER=PASS
    # INVALID_WORKFLOW_GRAPH_FAILS_BEFORE_PLANNER=PASS


def test_v8_red_f_ineligible_required_subworkflow_blocks_before_planner():
    """V8 MAJOR-11 RED F: ineligible required child blocks before planner.

    ``python.sub_child`` executes ``python.list_imports``, which the final
    planning authority excludes from the eligible candidate set. The parent
    must be blocked before the planner even though an unrelated safe
    operation candidate remains.
    """
    domain_registry, operation_registry, workflow_registry = _subworkflow_fixtures()
    workflow_registry.register(_sub_parent_workflow())
    workflow_registry.register(_sub_child_workflow(operation_id="python.list_imports"))
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _integrator_5(
        domain_registry,
        operation_registry,
        workflow_registry,
        service,
        prohibited=("python.list_imports",),
    )
    result = integrator.integrate(_subworkflow_request({}))

    assert result.blocked is True
    assert result.plan is None
    assert result.selected_domain_workflow_ids == ()
    assert service.plan_calls == 0
    assert "domain_workflow_dependency_not_available" in result.reason_codes
    # INELIGIBLE_REQUIRED_SUBWORKFLOW_BLOCKS_BEFORE_PLANNER=PASS
    # INVALID_WORKFLOW_GRAPH_FAILS_BEFORE_PLANNER=PASS


def test_v8_eligible_subworkflow_chain_plans():
    """V8 RED G: an eligible parent → child chain plans canonically.

    All required workflows resolve, the child's operation is final-authority
    eligible, and planning succeeds through the existing canonical path with
    the shared WorkflowEngine still owning execution.
    """
    domain_registry, operation_registry, workflow_registry = _subworkflow_fixtures()
    workflow_registry.register(_sub_parent_workflow())
    workflow_registry.register(_sub_child_workflow())
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _integrator_5(
        domain_registry, operation_registry, workflow_registry, service
    )
    from cmm.agent_runtime.enums import WorkflowPlanStatus

    result = integrator.integrate(_subworkflow_request({}))

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ("python.sub_parent",)
    assert result.plan is not None
    assert result.plan.status is WorkflowPlanStatus.VALID
    assert service.plan_calls == 1
    # ELIGIBLE_SUBWORKFLOW_CHAIN_PLANS=PASS
    # SUBWORKFLOW_REUSES_SHARED_WORKFLOW_ENGINE=PASS


def _nested_subworkflow_graph(grandchild_operation_id):
    """parent → child → grandchild chain with the given grandchild operation."""
    domain_registry, operation_registry, workflow_registry = _subworkflow_fixtures()
    workflow_registry.register(_sub_parent_workflow("python.mid_child"))
    workflow_registry.register(
        _sub_parent_workflow(
            "python.leaf_child",
            workflow_id="python.mid_child",
        )
    )
    workflow_registry.register(
        _sub_child_workflow(
            grandchild_operation_id,
            workflow_id="python.leaf_child",
        )
    )
    return domain_registry, operation_registry, workflow_registry


def test_v8_nested_subworkflow_eligibility():
    """V8 RED H: nested chain failures propagate; eligible chains plan.

    With an ineligible grandchild the parent is blocked before the planner;
    with all three levels eligible the parent plans canonically.
    """
    domain_registry, operation_registry, workflow_registry = _nested_subworkflow_graph(
        "python.list_imports"
    )
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _integrator_5(
        domain_registry,
        operation_registry,
        workflow_registry,
        service,
        prohibited=("python.list_imports",),
    )
    result = integrator.integrate(_subworkflow_request({}))

    assert result.blocked is True
    assert result.plan is None
    assert result.selected_domain_workflow_ids == ()
    assert service.plan_calls == 0
    assert "domain_workflow_dependency_not_available" in result.reason_codes
    # Nested dependency failure identified deterministically before planner.

    domain_registry, operation_registry, workflow_registry = _nested_subworkflow_graph(
        "python.find_symbol"
    )
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _integrator_5(
        domain_registry, operation_registry, workflow_registry, service
    )
    from cmm.agent_runtime.enums import WorkflowPlanStatus

    result = integrator.integrate(_subworkflow_request({}))

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ("python.sub_parent",)
    assert result.plan is not None
    assert result.plan.status is WorkflowPlanStatus.VALID
    # NESTED_SUBWORKFLOW_ELIGIBILITY=PASS


def test_v8_subworkflow_version_resolution_is_exact():
    """V8: referenced subworkflow version resolves exactly, never latest.

    With both child versions registered, an eligible ``1.0.0`` and an
    ineligible ``2.0.0``, the parent referencing ``1.0.0`` must plan — a
    silent latest-version fallback would evaluate ``2.0.0`` and block.
    Referencing a version that is not registered fails closed.
    """
    domain_registry, operation_registry, workflow_registry = _subworkflow_fixtures()
    workflow_registry.register(_sub_parent_workflow())
    workflow_registry.register(_sub_child_workflow(version="1.0.0"))
    workflow_registry.register(
        _sub_child_workflow(
            operation_id="python.list_imports",
            version="2.0.0",
        )
    )
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _integrator_5(
        domain_registry,
        operation_registry,
        workflow_registry,
        service,
        prohibited=("python.list_imports",),
    )
    from cmm.agent_runtime.enums import WorkflowPlanStatus

    result = integrator.integrate(_subworkflow_request({}))

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ("python.sub_parent",)
    assert result.plan is not None
    assert result.plan.status is WorkflowPlanStatus.VALID
    # Exact referenced version evaluated: 1.0.0 eligible, 2.0.0 never used.

    domain_registry, operation_registry, workflow_registry = _subworkflow_fixtures()
    workflow_registry.register(_sub_parent_workflow())
    workflow_registry.register(
        _sub_child_workflow(
            operation_id="python.list_imports",
            version="2.0.0",
        )
    )
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _integrator_5(
        domain_registry,
        operation_registry,
        workflow_registry,
        service,
        prohibited=("python.list_imports",),
    )
    result = integrator.integrate(_subworkflow_request({}))

    assert result.blocked is True
    assert result.plan is None
    assert service.plan_calls == 0
    assert "domain_workflow_dependency_not_available" in result.reason_codes
    # SUBWORKFLOW_VERSION_RESOLUTION=PASS


def test_v8_subworkflow_cycle_fails_closed():
    """V8: versioned subworkflow cycles fail closed deterministically.

    ``python.cycle_a → python.cycle_b → python.cycle_a`` with required
    references must block before planner invocation instead of recursing.
    """
    domain_registry, operation_registry, workflow_registry = _subworkflow_fixtures()
    workflow_registry.register(
        _sub_parent_workflow("python.cycle_b", workflow_id="python.cycle_a")
    )
    workflow_registry.register(
        _sub_parent_workflow("python.cycle_a", workflow_id="python.cycle_b")
    )
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _integrator_5(
        domain_registry, operation_registry, workflow_registry, service
    )
    result = integrator.integrate(
        _subworkflow_request({"requested_workflow_ids": ["python.cycle_a"]})
    )

    assert result.blocked is True
    assert result.plan is None
    assert result.selected_domain_workflow_ids == ()
    assert service.plan_calls == 0
    assert "domain_workflow_dependency_not_available" in result.reason_codes
    # SUBWORKFLOW_CYCLE_FAILS_CLOSED=PASS


def test_v8_subworkflow_final_authority_propagates():
    """V8: the child is evaluated under the same final planning authority.

    The child workflow requires ``python.secret``, which the prepared
    planning permissions never grant. The child is therefore final-authority
    ineligible and the parent is blocked before the planner; the parent is
    never granted the child's missing permission.
    """
    domain_registry, operation_registry, workflow_registry = _subworkflow_fixtures()
    workflow_registry.register(_sub_parent_workflow())
    workflow_registry.register(
        _sub_child_workflow(permissions=("python.secret",))
    )
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _integrator_5(
        domain_registry, operation_registry, workflow_registry, service
    )
    result = integrator.integrate(_subworkflow_request({}))

    assert result.blocked is True
    assert result.plan is None
    assert result.selected_domain_workflow_ids == ()
    assert service.plan_calls == 0
    assert "domain_workflow_dependency_not_available" in result.reason_codes
    assert "python.secret" not in set(
        result.prepared_planning_request.permissions
    )
    # SUBWORKFLOW_FINAL_AUTHORITY_PROPAGATES=PASS


def test_v8_subworkflow_approval_obligations_preserved():
    """V8: eligible child approval obligations stay representable.

    The required child is final-authority eligible except for its canonical
    approval obligations (workflow-level gate plus a node-level gate). The
    parent remains plan-eligible, the child obligations are flattened into
    the canonical ``required_approvals`` representation, and the plan's
    approval nodes trace them as pending — never pre-granted.
    """
    domain_registry, operation_registry, workflow_registry = _subworkflow_fixtures()
    workflow_registry.register(_sub_parent_workflow())
    workflow_registry.register(
        DomainWorkflowDefinition(
            "python.sub_child",
            "domain:python",
            "1.0.0",
            "SubChild",
            approval_gates=("child-approval",),
            nodes=(
                WorkflowNode(
                    "work",
                    "execute_operation",
                    "Work",
                    operation_id="python.find_symbol",
                    operation_version="1.0.0",
                ),
                WorkflowNode(
                    "gate",
                    "request_approval",
                    "Gate",
                    dependencies=("work",),
                    approval_gate="child-node-gate",
                ),
                WorkflowNode("done", "complete", "Done", dependencies=("gate",)),
            ),
        )
    )
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _integrator_5(
        domain_registry, operation_registry, workflow_registry, service
    )
    result = integrator.integrate(_subworkflow_request({}))

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ("python.sub_parent",)
    approvals = result.prepared_planning_request.required_approvals
    assert "child-approval" in approvals
    assert "child-node-gate" in approvals
    assert result.plan is not None
    for obligation in ("child-approval", "child-node-gate"):
        assert any(
            obligation in node.required_approvers
            and obligation in node.metadata.get("approval_requirement_ids", [])
            for node in result.plan.approval_nodes
        ), obligation
    assert all(node.pending for node in result.plan.approval_nodes)
    # SUBWORKFLOW_APPROVAL_OBLIGATIONS_PRESERVED=PASS


def test_v8_optional_subworkflow_semantics_preserved():
    """V8: optional subworkflow nodes follow canonical skip semantics.

    The canonical permission/execution path never blocks on an unavailable
    optional node (only ``required`` node denials block). Planning preserves
    that contract: an optional reference to an unregistered child leaves the
    parent selectable and plannable.
    """
    domain_registry, operation_registry, workflow_registry = _subworkflow_fixtures()
    workflow_registry.register(
        _sub_parent_workflow(
            "python.does_not_exist",
            required=False,
            workflow_id="python.opt_parent",
        )
    )
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _integrator_5(
        domain_registry, operation_registry, workflow_registry, service
    )
    from cmm.agent_runtime.enums import WorkflowPlanStatus

    result = integrator.integrate(
        _subworkflow_request({"requested_workflow_ids": ["python.opt_parent"]})
    )

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ("python.opt_parent",)
    assert result.plan is not None
    assert result.plan.status is WorkflowPlanStatus.VALID
    assert service.plan_calls == 1
    # OPTIONAL_SUBWORKFLOW_SEMANTICS=PRESERVED


def _all_production_pack_names():
    return (
        "concerns",
        "general",
        "health",
        "languages",
        "life_plan",
        "oppositions",
        "parenthood",
        "project",
        "reflection",
        "relationships",
        "sport",
        "university",
    )


def _canonical_node_approval_sources(workflow):
    """Audit-side enumeration of one workflow's canonical approval sources.

    Mirrors the canonical permission/execution semantics directly:
    workflow-level gates plus node-level ``approval_gate`` /
    ``REQUEST_APPROVAL`` sources (``node.approval_gate or node.node_id``).
    """
    from cmm.workflows.enums import WorkflowNodeType

    sources = set(workflow.approval_gates)
    for node in workflow.nodes:
        if (
            node.approval_gate is not None
            or node.node_type is WorkflowNodeType.REQUEST_APPROVAL
        ):
            source = node.approval_gate or node.node_id
            if source:
                sources.add(source)
    return sources


def test_v8_production_workflow_approval_inventory_gate():
    """V8 MAJOR-10: production-wide selected-approval representation gate.

    Every production Domain Pack workflow is selected under a compatible
    per-pack authority context. The canonical approval sources of each
    selected workflow graph (workflow-level and node-level) must all be
    representable in the prepared planning request and traceable on the
    canonical plan approval nodes.
    """
    import importlib

    domain_registry = DomainRegistry()
    pack_permissions: dict[str, set[str]] = {}
    pack_resources: dict[str, set[str]] = {}
    pack_workflows: dict[str, list] = {}
    pack_slugs: dict[str, str] = {}
    for module_slug in _all_production_pack_names():
        definition_builder = getattr(
            importlib.import_module(f"cmm.domains.{module_slug}.definition"),
            f"build_{module_slug}_domain_definition",
        )
        operations_builder = getattr(
            importlib.import_module(f"cmm.domains.{module_slug}.operations"),
            f"build_{module_slug}_operation_definitions",
        )
        workflows_builder = getattr(
            importlib.import_module(f"cmm.domains.{module_slug}.workflows"),
            f"build_{module_slug}_workflow_definitions",
        )
        definition = definition_builder()
        domain_id = str(definition.id)
        slug = definition.id.slug
        domain_registry.register(definition)
        domain_registry.enable(domain_id)
        permissions: set[str] = set()
        resources: set[str] = set()
        workflows = list(workflows_builder())
        for workflow in workflows:
            permissions.update(workflow.required_permissions)
            resources.update(workflow.required_resources)
        for operation_definition in operations_builder():
            permissions.update(operation_definition.required_permissions)
        pack_permissions[domain_id] = permissions
        pack_resources[domain_id] = resources
        pack_workflows[slug] = workflows
        pack_slugs[slug] = module_slug

    operation_registry = InMemoryDomainOperationRegistry(
        InMemoryAgentOperationRegistry()
    )
    for module_slug in _all_production_pack_names():
        operations_builder = getattr(
            importlib.import_module(f"cmm.domains.{module_slug}.operations"),
            f"build_{module_slug}_operation_definitions",
        )
        for operation_definition in operations_builder():
            operation_registry.register(
                operation_definition, _Implementation(operation_definition)
            )
    workflow_registry = InMemoryDomainWorkflowRegistry()
    for slug in pack_workflows:
        for workflow in pack_workflows[slug]:
            workflow_registry.register(workflow)

    _, _, service = _planning_stack()
    from cmm.domains.composer import DefaultDomainComposer
    from cmm.domains.resolver import DefaultDomainResolver
    from cmm.domains.resolver_contracts import DomainScoringPolicy
    from cmm.domains.workflow_execution import DomainWorkflowExecutor

    integrator = DefaultDomainPlannerWorkflowIntegrator(
        resolver=DefaultDomainResolver(
            scoring_policy=DomainScoringPolicy(
                max_supporting_domains=0, supporting_margin=100.0
            )
        ),
        composer=DefaultDomainComposer(),
        domain_registry=domain_registry,
        workflow_registry=workflow_registry,
        planning_service=service,
        workflow_executor=DomainWorkflowExecutor(id_factory=lambda: "wf-id-inv"),
        operation_availability=lambda operation_id, domain_id: (
            operation_registry.resolve_active(operation_id, required=False)
            is not None
        ),
        permission_ids_provider=lambda composition: tuple(
            sorted(pack_permissions.get(str(composition.primary_domain), ()))
        ),
        prohibited_operation_ids_provider=lambda composition: (),
        approval_ids_provider=lambda composition: (),
        validation_ids_provider=lambda composition: (),
        authority_reference_ids_provider=lambda composition: ("authority:v1",),
    )

    inspected = 0
    unrepresented: list[str] = []
    for slug in pack_workflows:
        domain_id = f"domain:{slug}"
        for workflow in pack_workflows[slug]:
            inspected += 1
            expected_gates = _canonical_node_approval_sources(workflow)
            node_operations = sorted(
                {node.operation_id for node in workflow.nodes if node.operation_id}
            )
            incoming = _incoming_request(
                id=f"req-042-v8-inv-{workflow.workflow_id}",
                goal_id=f"goal-042-{slug}",
                agent_run_id=f"run-042-{workflow.workflow_id}",
                actor_id="actor-042",
                objective=f"Select {workflow.workflow_id} under full authority",
                permissions=sorted(pack_permissions[domain_id]),
                allowed_operations=node_operations,
                resource_ids=sorted(pack_resources[domain_id]),
            )
            result = integrator.integrate(
                _pack_request(
                    slug,
                    request_id=f"int-req-042-{slug}-inv",
                    planning_request=incoming,
                    metadata={
                        "requested_workflow_ids": [workflow.workflow_id],
                    },
                )
            )
            assert result.blocked is False, (
                workflow.workflow_id,
                result.reason_codes,
            )
            assert result.selected_domain_workflow_ids == (workflow.workflow_id,)
            assert result.plan is not None
            projected = set(result.prepared_planning_request.required_approvals)
            missing = expected_gates - projected
            if missing:
                unrepresented.append(f"{workflow.workflow_id}:{sorted(missing)}")
                continue
            for gate in expected_gates:
                assert any(
                    gate in node.required_approvers
                    and gate in node.metadata.get("approval_requirement_ids", [])
                    for node in result.plan.approval_nodes
                ), (workflow.workflow_id, gate)
    assert inspected == 95
    assert unrepresented == []
    # UNREPRESENTED_SELECTED_WORKFLOW_APPROVAL_GATE=0


def test_v8_production_subworkflow_inventory():
    """V8 MAJOR-11: production subworkflow reference inventory.

    Enumerates every production ``INVOKE_SUBWORKFLOW`` node and verifies
    each required reference resolves exactly (id, version) against the
    canonical registry. Production currently declares none; the check is
    dynamic so any future reference is verified or fails the gate.
    """
    import importlib

    from cmm.workflows.enums import WorkflowNodeType

    workflow_registry = InMemoryDomainWorkflowRegistry()
    node_count = 0
    parents: set[str] = set()
    required_references: list[tuple[str, str, str]] = []
    for slug in _all_production_pack_names():
        workflows_builder = getattr(
            importlib.import_module(f"cmm.domains.{slug}.workflows"),
            f"build_{slug}_workflow_definitions",
        )
        for workflow in workflows_builder():
            workflow_registry.register(workflow)
            for node in workflow.nodes:
                if node.node_type is not WorkflowNodeType.INVOKE_SUBWORKFLOW:
                    continue
                node_count += 1
                parents.add(workflow.workflow_id)
                if node.required:
                    required_references.append(
                        (
                            workflow.workflow_id,
                            node.subworkflow_id or "",
                            node.subworkflow_version or "",
                        )
                    )
    unresolved = [
        (parent, child_id, child_version)
        for parent, child_id, child_version in required_references
        if not child_id
        or not child_version
        or _resolves_exact(workflow_registry, child_id, child_version) is None
    ]
    assert unresolved == []
    # PRODUCTION_SUBWORKFLOW_NODE_COUNT=0
    # PRODUCTION_SUBWORKFLOW_PARENT_COUNT=0
    # PRODUCTION_REQUIRED_SUBWORKFLOW_REFERENCES=VERIFIED


def _resolves_exact(workflow_registry, workflow_id, version):
    try:
        return workflow_registry.get(workflow_id, version)
    except KeyError:
        return None


# ── Phase 10.42 V8 — canonical WorkflowNodeType classification matrix ─────
#
# Every canonical WorkflowNodeType member must carry an explicit Phase 10.42
# planning classification. Classification categories:
#
# - operation_eligibility: node introduces a planning-time operation
#   dependency; enforced by the canonical ``resolve_domain_workflow``
#   EXECUTE_OPERATION candidate check (V6 MAJOR-08 semantics).
# - workflow_approval_extraction: node introduces a planning-time approval
#   obligation; projected by ``_workflow_approval_ids`` (V8 MAJOR-10).
# - subworkflow_eligibility: node introduces a required child workflow
#   dependency; enforced by ``_required_subworkflow_closure_for_planning``
#   (V8 MAJOR-11).
# - deferred_runtime_<aspect>: the node's semantics are owned at execution
#   time by the canonical executor / shared WorkflowEngine / Phase 9/10
#   owners; it introduces no additional Phase 10.42 pre-planning constraint
#   and no separate planning authority.
#
# Evidence per classification (canonical sources, not assumptions):
# - EXECUTE_OPERATION: ``cmm.workflows.graph`` requires operation_id/version;
#   ``cmm.domains.workflow_resolution`` checks node operation availability.
# - REQUEST_APPROVAL: ``cmm.workflows.graph`` requires approval_gate;
#   ``cmm.domains.permission_adapters._node_decision`` returns
#   APPROVAL_REQUIRED with source ``node.approval_gate or node.node_id``;
#   the executor waits on the gate. Planning projects the exact gate ID.
# - INVOKE_SUBWORKFLOW: ``cmm.workflows.graph`` requires id+version; the
#   permission adapter resolves the child recursively and denies a missing
#   required child; the executor runs it through the shared WorkflowEngine.
#   Planning checks exact-version final-authority eligibility.
# - WAIT_FOR_RESOURCE / LOAD_RESOURCE: ``WorkflowNode`` declares no
#   canonical resource identity field; workflow resource obligations are
#   declared solely through ``DomainWorkflowDefinition.required_resources``
#   (workflow-level final resource eligibility, V6 MAJOR-08). The node
#   itself is a runtime wait/load whose resource identity is supplied
#   dynamically at execution time.
# - VALIDATE: ``cmm.workflows.engine`` evaluates the node wait_condition
#   fail-closed at runtime; planning-time validation obligations travel
#   only through the canonical ``required_validations`` request/view seam.
# - ASK_QUESTION / PAUSE / ESCALATE: runtime control flow owned by the
#   WorkflowEngine and Phase 9 runtime/recovery; they carry no canonical
#   planning-time capability/approval field (ESCALATE is not an approval
#   source; approval nodes are REQUEST_APPROVAL).
# - PROPOSE_MEMORY / UPDATE_SESSION: memory/session mutation stays owned by
#   the existing Phase 9/10 runtime safeguards; planning creates no
#   mutation authority for them.
# - SEARCH_KNOWLEDGE / RESOLVE_ENTITY / APPLY_PROFILE / REASON /
#   DETECT_GAPS / EVALUATE_OUTCOME: runtime-internal cognitive nodes; no
#   canonical planning authority fields, no separate Phase 10.42 constraint.
# - COMPLETE: terminal marker only (``cmm.workflows.graph`` forbids
#   successors); introduces no capability authority.
_V8_WORKFLOW_NODE_TYPE_CLASSIFICATION = {
    "COMPLETE": "no_additional_phase_10_42_constraint",
    "EXECUTE_OPERATION": "operation_eligibility",
    "REQUEST_APPROVAL": "workflow_approval_extraction",
    "WAIT_FOR_RESOURCE": "deferred_runtime_resource_wait",
    "ASK_QUESTION": "deferred_runtime_control_flow",
    "INVOKE_SUBWORKFLOW": "subworkflow_eligibility",
    "PAUSE": "deferred_runtime_control_flow",
    "VALIDATE": "deferred_runtime_validation",
    "PROPOSE_MEMORY": "deferred_runtime_state_mutation",
    "UPDATE_SESSION": "deferred_runtime_state_mutation",
    "LOAD_RESOURCE": "deferred_runtime_resource_load",
    "SEARCH_KNOWLEDGE": "deferred_runtime_cognitive",
    "RESOLVE_ENTITY": "deferred_runtime_cognitive",
    "APPLY_PROFILE": "deferred_runtime_cognitive",
    "REASON": "deferred_runtime_cognitive",
    "DETECT_GAPS": "deferred_runtime_cognitive",
    "EVALUATE_OUTCOME": "deferred_runtime_cognitive",
    "ESCALATE": "deferred_runtime_control_flow",
}


def test_v8_all_canonical_workflow_node_types_classified():
    """V8: every canonical WorkflowNodeType is explicitly classified.

    The matrix must cover the enum dynamically: adding a new
    ``WorkflowNodeType`` member without a Phase 10.42 classification fails
    this gate.
    """
    from cmm.workflows.enums import WorkflowNodeType

    enum_names = {node_type.name for node_type in WorkflowNodeType}
    classified_names = set(_V8_WORKFLOW_NODE_TYPE_CLASSIFICATION)
    unclassified = sorted(enum_names - classified_names)
    stale = sorted(classified_names - enum_names)
    assert unclassified == [], unclassified
    assert stale == [], stale
    allowed_categories = {
        "operation_eligibility",
        "workflow_approval_extraction",
        "subworkflow_eligibility",
        "no_additional_phase_10_42_constraint",
        "deferred_runtime_resource_wait",
        "deferred_runtime_resource_load",
        "deferred_runtime_validation",
        "deferred_runtime_control_flow",
        "deferred_runtime_state_mutation",
        "deferred_runtime_cognitive",
    }
    assert set(_V8_WORKFLOW_NODE_TYPE_CLASSIFICATION.values()) <= allowed_categories
    # Planning-binding categories must name exactly the node forms the
    # canonical execution/permission semantics treat as capability sources.
    assert _V8_WORKFLOW_NODE_TYPE_CLASSIFICATION["EXECUTE_OPERATION"] == (
        "operation_eligibility"
    )
    assert _V8_WORKFLOW_NODE_TYPE_CLASSIFICATION["REQUEST_APPROVAL"] == (
        "workflow_approval_extraction"
    )
    assert _V8_WORKFLOW_NODE_TYPE_CLASSIFICATION["INVOKE_SUBWORKFLOW"] == (
        "subworkflow_eligibility"
    )
    # ALL_CANONICAL_WORKFLOW_NODE_TYPES_CLASSIFIED=PASS
    # UNCLASSIFIED_WORKFLOW_NODE_TYPES=0
    # WORKFLOW_NODE_TYPE_COUNT=18


def _matrix_workflow():
    """One canonical workflow exercising every non-binding node type."""
    return DomainWorkflowDefinition(
        "python.matrix",
        "domain:python",
        "1.0.0",
        "Matrix",
        nodes=(
            WorkflowNode(
                "start",
                "execute_operation",
                "Start",
                operation_id="python.find_symbol",
                operation_version="1.0.0",
            ),
            WorkflowNode(
                "validate",
                "validate",
                "Validate",
                dependencies=("start",),
                wait_condition={},
            ),
            WorkflowNode(
                "wait_resource",
                "wait_for_resource",
                "WaitForResource",
                dependencies=("validate",),
                wait_condition={},
            ),
            WorkflowNode("load", "load_resource", "Load", dependencies=("wait_resource",)),
            WorkflowNode(
                "ask",
                "ask_question",
                "Ask",
                dependencies=("load",),
                wait_condition={},
            ),
            WorkflowNode("pause", "pause", "Pause", dependencies=("ask",)),
            WorkflowNode("propose", "propose_memory", "Propose", dependencies=("pause",)),
            WorkflowNode("session", "update_session", "Session", dependencies=("propose",)),
            WorkflowNode("search", "search_knowledge", "Search", dependencies=("session",)),
            WorkflowNode("resolve", "resolve_entity", "Resolve", dependencies=("search",)),
            WorkflowNode("profile", "apply_profile", "Profile", dependencies=("resolve",)),
            WorkflowNode("reason", "reason", "Reason", dependencies=("profile",)),
            WorkflowNode("gaps", "detect_gaps", "Gaps", dependencies=("reason",)),
            WorkflowNode("outcome", "evaluate_outcome", "Outcome", dependencies=("gaps",)),
            WorkflowNode("escalate", "escalate", "Escalate", dependencies=("outcome",)),
            WorkflowNode("finish", "complete", "Finish", dependencies=("escalate",)),
        ),
    )


def test_v8_non_binding_node_types_add_no_planning_constraints():
    """V8: runtime-deferred node types introduce no pre-planning obligation.

    A selected workflow containing VALIDATE, WAIT_FOR_RESOURCE,
    LOAD_RESOURCE, ASK_QUESTION, PAUSE, PROPOSE_MEMORY, UPDATE_SESSION,
    SEARCH_KNOWLEDGE, RESOLVE_ENTITY, APPLY_PROFILE, REASON, DETECT_GAPS,
    EVALUATE_OUTCOME, ESCALATE, and COMPLETE nodes stays selectable and
    plannable with no inferred approvals, no inferred validations, and no
    node-level resource requirements: those obligations remain owned by the
    canonical request/view seams and runtime owners.
    """
    domain_registry, operation_registry, workflow_registry = _subworkflow_fixtures()
    workflow_registry.register(_matrix_workflow())
    _, _, service = _planning_stack(_CountingPlanningService)
    integrator = _integrator_5(
        domain_registry, operation_registry, workflow_registry, service
    )
    result = integrator.integrate(
        _subworkflow_request({"requested_workflow_ids": ["python.matrix"]})
    )

    from cmm.agent_runtime.enums import WorkflowPlanStatus

    assert result.blocked is False
    assert result.selected_domain_workflow_ids == ("python.matrix",)
    assert result.plan is not None
    assert result.plan.status is WorkflowPlanStatus.VALID
    # No approval obligation may be inferred from ESCALATE or any other
    # non-approval node form.
    assert result.prepared_planning_request.required_approvals == []
    # VALIDATE nodes do not mint planning-time validation requirements: the
    # only validation obligation is the one injected by the composition.
    assert result.prepared_planning_request.required_validations == ["python.schema"]
    # WAIT_FOR_RESOURCE / LOAD_RESOURCE nodes declare no canonical node-level
    # resource identity: the planning request carried no resource ids.
    assert result.prepared_planning_request.resource_ids == []
    assert service.plan_calls == 1
    # WORKFLOW_NODE_RESOURCE_SEMANTICS=VERIFIED
    # WORKFLOW_NODE_VALIDATION_SEMANTICS=VERIFIED
    # WORKFLOW_CONTROL_NODE_SEMANTICS=VERIFIED
    # WORKFLOW_COGNITIVE_NODE_SEMANTICS=VERIFIED
    # WORKFLOW_STATE_MUTATION_NODE_SEMANTICS=VERIFIED
    # WORKFLOW_COMPLETE_NODE_SEMANTICS=VERIFIED


def test_v8_production_node_types_are_classified():
    """V8: every node type used by production packs is in the matrix."""
    import importlib

    from cmm.workflows.enums import WorkflowNodeType

    used: set[str] = set()
    for slug in _all_production_pack_names():
        workflows_builder = getattr(
            importlib.import_module(f"cmm.domains.{slug}.workflows"),
            f"build_{slug}_workflow_definitions",
        )
        for workflow in workflows_builder():
            for node in workflow.nodes:
                used.add(node.node_type.name)
    assert used <= set(_V8_WORKFLOW_NODE_TYPE_CLASSIFICATION)
    assert used <= {node_type.name for node_type in WorkflowNodeType}
