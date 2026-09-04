"""Phase 10.42 — immutable planner/workflow integration contract tests.

DP-042 — Domain-specialized Planner and Workflow Engine integration.

Locks the frozen Phase 10.42 public surface before any production code
exists:

- DomainPlanningCapabilityView
- DomainPlannerWorkflowIntegrationRequest
- DomainPlannerWorkflowIntegrationResult
- DomainPlannerWorkflowIntegrator (protocol)
- DefaultDomainPlannerWorkflowIntegrator (existence/export only)

Contracts are value objects only: no registries, services, stores,
executors, planners, or state machines.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cmm.agent_runtime.workflow_planner_contracts import (
    AgentPlanningRequest,
    AgentWorkflowPlan,
)
from cmm.domains import (
    DefaultDomainPlannerWorkflowIntegrator,
    DomainPlannerWorkflowIntegrationRequest,
    DomainPlannerWorkflowIntegrationResult,
    DomainPlannerWorkflowIntegrator,
    DomainPlanningCapabilityView,
)
from cmm.domains.composition_contracts import DomainComposition
from cmm.domains.enums import DomainCompositionStatus, DomainResolutionStatus
from cmm.domains.errors import DomainContractValidationError
from cmm.domains.identifiers import DomainId
from cmm.domains.resolution_contracts import DomainResolutionContext
from cmm.domains.resolver_contracts import DomainResolutionResult

# ── Canonical fixtures ────────────────────────────────────────────────────


def _resolution_context() -> DomainResolutionContext:
    return DomainResolutionContext(
        id="ctx-042-1",
        objective="Inspect the project domain",
        available_domains=(DomainId(slug="project"),),
    )


def _planning_request() -> AgentPlanningRequest:
    return AgentPlanningRequest(
        id="req-042-1",
        goal_id="goal-042-1",
        agent_run_id="run-042-1",
        objective="Inspect the project domain",
    )


def _resolution() -> DomainResolutionResult:
    return DomainResolutionResult(
        id="res-042-1",
        context_id="ctx-042-1",
        status=DomainResolutionStatus.RESOLVED,
        primary_domain=DomainId(slug="project"),
    )


def _composition() -> DomainComposition:
    return DomainComposition(
        id="comp-042-1",
        resolution_id="res-042-1",
        status=DomainCompositionStatus.COMPOSED,
        primary_domain=DomainId(slug="project"),
    )


def _capability_view(**overrides) -> DomainPlanningCapabilityView:
    kwargs: dict = {"primary_domain_id": "domain:project"}
    kwargs.update(overrides)
    return DomainPlanningCapabilityView(**kwargs)


def _plan() -> AgentWorkflowPlan:
    return AgentWorkflowPlan(
        id="plan-042-1",
        goal_id="goal-042-1",
        agent_run_id="run-042-1",
        workflow_id="workflow-042-1",
    )


# ── DomainPlanningCapabilityView ──────────────────────────────────────────


def test_capability_view_valid_minimal_construction() -> None:
    view = _capability_view()
    assert view.primary_domain_id == "domain:project"
    assert view.supporting_domain_ids == ()
    assert view.available_operation_ids == ()
    assert view.prohibited_operation_ids == ()
    assert view.available_workflow_ids == ()
    assert view.operation_dependency_ids == ()
    assert view.workflow_dependency_ids == ()
    assert view.required_permission_ids == ()
    assert view.required_approval_ids == ()
    assert view.required_validation_ids == ()
    assert view.cross_domain_constraint_ids == ()
    assert view.authority_reference_ids == ()
    assert dict(view.metadata) == {}


def test_capability_view_is_frozen() -> None:
    view = _capability_view()
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        view.primary_domain_id = "domain:other"  # type: ignore[misc]


def test_capability_view_defensively_copies_metadata() -> None:
    source = {"origin": "test"}
    view = _capability_view(metadata=source)
    source["origin"] = "mutated"
    assert dict(view.metadata) == {"origin": "test"}


def test_capability_view_normalizes_identifiers_deterministically() -> None:
    view = _capability_view(
        available_operation_ids=("project.write", "project.inspect"),
        supporting_domain_ids=("domain:support-b", "domain:support-a"),
    )
    assert view.available_operation_ids == ("project.inspect", "project.write")
    assert view.supporting_domain_ids == ("domain:support-a", "domain:support-b")


@pytest.mark.parametrize(
    "field",
    [
        "supporting_domain_ids",
        "available_operation_ids",
        "prohibited_operation_ids",
        "available_workflow_ids",
        "required_permission_ids",
        "required_approval_ids",
        "required_validation_ids",
        "cross_domain_constraint_ids",
        "authority_reference_ids",
    ],
)
def test_capability_view_rejects_duplicate_identifiers(field: str) -> None:
    with pytest.raises(DomainContractValidationError):
        _capability_view(**{field: ("project.inspect", "project.inspect")})


@pytest.mark.parametrize(
    "field",
    [
        "supporting_domain_ids",
        "available_operation_ids",
        "prohibited_operation_ids",
        "available_workflow_ids",
        "required_permission_ids",
        "required_approval_ids",
        "required_validation_ids",
        "cross_domain_constraint_ids",
        "authority_reference_ids",
    ],
)
def test_capability_view_rejects_blank_identifiers(field: str) -> None:
    with pytest.raises(DomainContractValidationError):
        _capability_view(**{field: ("   ",)})


def test_capability_view_rejects_blank_primary_domain() -> None:
    with pytest.raises(DomainContractValidationError):
        _capability_view(primary_domain_id="   ")


def test_capability_view_rejects_non_mapping_metadata() -> None:
    with pytest.raises(DomainContractValidationError):
        _capability_view(metadata=["not", "a", "mapping"])  # type: ignore[arg-type]


def test_capability_view_rejects_non_json_safe_metadata() -> None:
    with pytest.raises(DomainContractValidationError):
        _capability_view(metadata={"handle": object()})


def test_capability_view_dependency_rows_are_deterministic() -> None:
    view = _capability_view(
        operation_dependency_ids=(
            ("project.write", ("project.lock", "project.inspect")),
            ("project.inspect", ()),
        ),
    )
    assert view.operation_dependency_ids == (
        ("project.inspect", ()),
        ("project.write", ("project.inspect", "project.lock")),
    )


def test_capability_view_rejects_blank_dependency_owner() -> None:
    with pytest.raises(DomainContractValidationError):
        _capability_view(operation_dependency_ids=(("  ", ("project.inspect",)),))


def test_capability_view_rejects_blank_dependency_id() -> None:
    with pytest.raises(DomainContractValidationError):
        _capability_view(operation_dependency_ids=(("project.write", ("  ",)),))


# ── DomainPlannerWorkflowIntegrationRequest ───────────────────────────────


def test_integration_request_valid_construction() -> None:
    request = DomainPlannerWorkflowIntegrationRequest(
        request_id="int-req-042-1",
        resolution_context=_resolution_context(),
        planning_request=_planning_request(),
    )
    assert request.request_id == "int-req-042-1"
    assert request.current_plan is None
    assert dict(request.metadata) == {}


def test_integration_request_is_frozen() -> None:
    request = DomainPlannerWorkflowIntegrationRequest(
        request_id="int-req-042-1",
        resolution_context=_resolution_context(),
        planning_request=_planning_request(),
    )
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        request.request_id = "other"  # type: ignore[misc]


def test_integration_request_rejects_blank_request_id() -> None:
    with pytest.raises(DomainContractValidationError):
        DomainPlannerWorkflowIntegrationRequest(
            request_id="  ",
            resolution_context=_resolution_context(),
            planning_request=_planning_request(),
        )


def test_integration_request_rejects_wrong_resolution_context_type() -> None:
    with pytest.raises(DomainContractValidationError):
        DomainPlannerWorkflowIntegrationRequest(
            request_id="int-req-042-1",
            resolution_context={"id": "ctx-1"},  # type: ignore[arg-type]
            planning_request=_planning_request(),
        )


def test_integration_request_rejects_wrong_planning_request_type() -> None:
    with pytest.raises(DomainContractValidationError):
        DomainPlannerWorkflowIntegrationRequest(
            request_id="int-req-042-1",
            resolution_context=_resolution_context(),
            planning_request={"id": "req-1"},  # type: ignore[arg-type]
        )


def test_integration_request_rejects_wrong_current_plan_type() -> None:
    with pytest.raises(DomainContractValidationError):
        DomainPlannerWorkflowIntegrationRequest(
            request_id="int-req-042-1",
            resolution_context=_resolution_context(),
            planning_request=_planning_request(),
            current_plan={"id": "plan-1"},  # type: ignore[arg-type]
        )


def test_integration_request_accepts_canonical_current_plan() -> None:
    request = DomainPlannerWorkflowIntegrationRequest(
        request_id="int-req-042-1",
        resolution_context=_resolution_context(),
        planning_request=_planning_request(),
        current_plan=_plan(),
    )
    assert request.current_plan is not None
    assert request.current_plan.id == "plan-042-1"


def test_integration_request_metadata_is_defensive() -> None:
    source = {"requested_workflow_ids": ["workflow:a"]}
    request = DomainPlannerWorkflowIntegrationRequest(
        request_id="int-req-042-1",
        resolution_context=_resolution_context(),
        planning_request=_planning_request(),
        metadata=source,
    )
    source["requested_workflow_ids"] = ["workflow:mutated"]
    assert list(request.metadata["requested_workflow_ids"]) == ["workflow:a"]


# ── DomainPlannerWorkflowIntegrationResult ────────────────────────────────


def _result(**overrides) -> DomainPlannerWorkflowIntegrationResult:
    kwargs: dict = {
        "request_id": "int-req-042-1",
        "resolution": _resolution(),
        "composition": _composition(),
        "capability_view": _capability_view(),
        "prepared_planning_request": _planning_request(),
        "plan": _plan(),
    }
    kwargs.update(overrides)
    return DomainPlannerWorkflowIntegrationResult(**kwargs)


def test_integration_result_valid_construction() -> None:
    result = _result()
    assert result.request_id == "int-req-042-1"
    assert result.selected_domain_workflow_ids == ()
    assert result.blocked is False
    assert result.reason_codes == ()


def test_integration_result_is_frozen() -> None:
    result = _result()
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        result.blocked = True  # type: ignore[misc]


def test_integration_result_blocked_requires_reason_code() -> None:
    with pytest.raises(DomainContractValidationError):
        _result(blocked=True, plan=None, reason_codes=())


def test_integration_result_blocked_with_reason_code() -> None:
    result = _result(
        blocked=True,
        plan=None,
        reason_codes=("domain_operation_not_composable",),
    )
    assert result.blocked is True
    assert result.plan is None


def test_integration_result_rejects_wrong_plan_type() -> None:
    with pytest.raises(DomainContractValidationError):
        _result(plan={"id": "plan-1"})  # type: ignore[arg-type]


def test_integration_result_rejects_composition_resolution_mismatch() -> None:
    composition = DomainComposition(
        id="comp-042-9",
        resolution_id="res-other",
        status=DomainCompositionStatus.COMPOSED,
        primary_domain=DomainId(slug="project"),
    )
    with pytest.raises(DomainContractValidationError):
        _result(composition=composition)


# ── Protocol ──────────────────────────────────────────────────────────────


def test_integrator_protocol_runtime_check() -> None:
    class _Dummy:
        def integrate(self, request):  # type: ignore[no-untyped-def]
            raise NotImplementedError

        def execute_workflow_reference(self, *, workflow_id, context, inputs):  # type: ignore[no-untyped-def]
            raise NotImplementedError

        def replan(self, request, *, reason, reason_details):  # type: ignore[no-untyped-def]
            raise NotImplementedError

    assert isinstance(_Dummy(), DomainPlannerWorkflowIntegrator)
    assert not isinstance(object(), DomainPlannerWorkflowIntegrator)


def test_default_integrator_is_exported() -> None:
    assert DefaultDomainPlannerWorkflowIntegrator is not None


def test_public_surface_exact_exports() -> None:
    import cmm.domains as domains_pkg

    for name in (
        "DomainPlanningCapabilityView",
        "DomainPlannerWorkflowIntegrationRequest",
        "DomainPlannerWorkflowIntegrationResult",
        "DomainPlannerWorkflowIntegrator",
        "DefaultDomainPlannerWorkflowIntegrator",
    ):
        assert name in domains_pkg.__all__, name
        assert getattr(domains_pkg, name) is not None
