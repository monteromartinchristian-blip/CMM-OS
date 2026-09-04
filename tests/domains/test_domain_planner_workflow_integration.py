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

from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
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
from cmm.domains.identifiers import DomainId
from cmm.domains.operation_contracts import DomainOperationDefinition
from cmm.domains.operation_registry import InMemoryDomainOperationRegistry
from cmm.domains.planner_workflow_integration import _build_capability_view
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
