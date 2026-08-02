"""Phase 10.16 multi-domain presentation composition is deterministic and safe."""

from __future__ import annotations

from cmm.domains.composition_contracts import PresentationComposition
from cmm.domains.presentation_contracts import (
    DomainOutputIntent,
    DomainOutputIntentType,
    DomainPresentationItemRef,
    DomainPresentationRequest,
)
from cmm.domains.presentation_planner import DefaultDomainPresentationPlanner
from cmm.domains.presentation_validation import (
    DefaultDomainPresentationPreservationValidator,
)
from cmm.domains.profile_contracts import DomainPresentationPolicy


def _request(values: dict[str, object]) -> DomainPresentationRequest:
    return DomainPresentationRequest(
        request_id="request-1", upstream_result_id="result-1", composition_id="composition-1", policy_id="profile-1",
        presentation=PresentationComposition(values=values, provenance={}),
        policy=DomainPresentationPolicy(
            required_sections=("warnings",), protected_terms=("risk",), term_glosses={"risk": "policy gloss"},
            preferred_components=("warning-banner",),
        ),
        output_intent=DomainOutputIntent(DomainOutputIntentType.HUMAN_READABLE),
        items=(DomainPresentationItemRef("warning-1", "WARNING", 0, warning_priority=0),),
        primary_domain_id="domain:general", supporting_domain_ids=("domain:health",),
    )


def test_multidomain_mapping_order_does_not_change_plan_and_safety_stays_visible():
    first = _request({"required_sections": ["contradictions"], "components": ["source-panel"]})
    second = _request({"components": ["source-panel"], "required_sections": ["contradictions"]})
    planner = DefaultDomainPresentationPlanner()

    first_plan = planner.plan(first)
    second_plan = planner.plan(second)

    assert first_plan.plan_id == second_plan.plan_id
    assert [section.section_id for section in first_plan.sections][:2] == ["warnings", "contradictions"]
    assert {component.component_id for component in first_plan.components} == {"warning-banner", "source-panel"}


def test_incompatible_multi_domain_gloss_is_typed_conflict_and_blocks_validation():
    request = _request({"term_glosses": {"risk": "different gloss"}})
    plan = DefaultDomainPresentationPlanner().plan(request)

    result = DefaultDomainPresentationPreservationValidator().validate(request, plan)

    assert plan.conflicts[0].code.value == "TERMINOLOGY_INCOMPATIBLE"
    assert result.valid is False
    assert "UNRESOLVED_MULTIDOMAIN_CONFLICT" in result.codes
