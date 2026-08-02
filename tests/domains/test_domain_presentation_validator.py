"""Phase 10.16 preservation validation is a blocking semantic boundary."""

from __future__ import annotations

from dataclasses import replace

from cmm.domains.composition_contracts import PresentationComposition
from cmm.domains.presentation_contracts import (
    DomainOutputIntent,
    DomainOutputIntentType,
    DomainPresentationEpistemicKind,
    DomainPresentationItemRef,
    DomainPresentationItemType,
    DomainPresentationRequest,
)
from cmm.domains.presentation_planner import DefaultDomainPresentationPlanner
from cmm.domains.presentation_validation import (
    DefaultDomainPresentationPreservationValidator,
)
from cmm.domains.profile_contracts import DomainPresentationPolicy


def _request() -> DomainPresentationRequest:
    return DomainPresentationRequest(
        request_id="request-1", upstream_result_id="result-1", composition_id="composition-1", policy_id="profile-1",
        presentation=PresentationComposition(values={}, provenance={}),
        policy=DomainPresentationPolicy(required_sections=("warnings",), protected_terms=("risk",), term_glosses={"risk": "risk_gloss"}),
        output_intent=DomainOutputIntent(DomainOutputIntentType.HUMAN_READABLE),
        items=(
            DomainPresentationItemRef("warning-1", "WARNING", 0, warning_priority=0),
            DomainPresentationItemRef("finding-1", "FINDING", 1, epistemic_kind="hypothesis", confidence=0.3, requires_provenance=True),
            DomainPresentationItemRef("recommendation-1", "RECOMMENDATION", 2, epistemic_kind="recommendation"),
        ),
        primary_domain_id="domain:general",
    )


def test_validator_accepts_exact_reference_only_plan():
    request = _request()
    plan = DefaultDomainPresentationPlanner().plan(request)

    result = DefaultDomainPresentationPreservationValidator().validate(request, plan)

    assert result.valid is True
    assert result.state.value == "VALID"
    assert result.upstream_digest == request.calculate_digest()
    assert result.plan_digest == plan.calculate_digest()


def test_validator_blocks_lost_or_introduced_references_and_required_section_suppression():
    request = _request()
    plan = DefaultDomainPresentationPlanner().plan(request)
    lost = replace(plan, item_refs=plan.item_refs[:-1])

    result = DefaultDomainPresentationPreservationValidator().validate(request, lost)

    assert result.valid is False
    assert "MISSING_REF" in result.codes


def test_validator_blocks_confidence_epistemic_and_recommendation_mutations():
    request = _request()
    plan = DefaultDomainPresentationPlanner().plan(request)
    changed_finding = replace(
        plan.item_refs[1], confidence=0.9, epistemic_kind=DomainPresentationEpistemicKind.DIAGNOSIS
    )
    changed_recommendation = replace(plan.item_refs[2], item_type=DomainPresentationItemType.DECISION)
    mutated = replace(plan, item_refs=(plan.item_refs[0], changed_finding, changed_recommendation))

    result = DefaultDomainPresentationPreservationValidator().validate(request, mutated)

    assert result.valid is False
    assert "CONFIDENCE_CHANGED" in result.codes
    assert "EPISTEMIC_KIND_CHANGED" in result.codes
    assert "ITEM_TYPE_CHANGED" in result.codes


def test_validator_blocks_reordered_warnings_and_mandatory_section_suppression():
    request = _request()
    plan = DefaultDomainPresentationPlanner().plan(request)
    sections = tuple(
        replace(section, visible=False) if section.section_id == "warnings" else section
        for section in plan.sections
    )
    invalid = replace(plan, sections=sections, warning_refs=())

    result = DefaultDomainPresentationPreservationValidator().validate(request, invalid)

    assert result.valid is False
    assert "MANDATORY_SECTION_SUPPRESSED" in result.codes
    assert "INVALID_WARNING_PRIORITY" in result.codes
