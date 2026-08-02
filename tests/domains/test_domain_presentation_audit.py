"""Regression tests for confirmed Phase 10.16 audit defects."""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from cmm import domains
from cmm.domains.composition_contracts import PresentationComposition
from cmm.domains.errors import DomainPresentationContractError
from cmm.domains.presentation_contracts import (
    DomainOutputIntent,
    DomainOutputIntentType,
    DomainPresentationComponentDescriptor,
    DomainPresentationItemRef,
    DomainPresentationRequest,
)
from cmm.domains.presentation_planner import DefaultDomainPresentationPlanner
from cmm.domains.presentation_validation import (
    DefaultDomainPresentationPreservationValidator,
)
from cmm.domains.profile_contracts import DomainPresentationPolicy


def test_visibility_validation_codes_are_typed_and_public():
    assert domains.DomainPresentationValidationCode.REQUIRED_REFERENCE_HIDDEN.value == (
        "REQUIRED_REFERENCE_HIDDEN"
    )


def _request(
    *,
    policy: DomainPresentationPolicy | None = None,
    composition: dict[str, object] | None = None,
    items: tuple[DomainPresentationItemRef, ...] | None = None,
    output_intent: DomainOutputIntent | None | object = ...,
) -> DomainPresentationRequest:
    if output_intent is ...:
        output_intent = DomainOutputIntent(DomainOutputIntentType.HUMAN_READABLE)
    return DomainPresentationRequest(
        request_id="request-audit",
        upstream_result_id="result-audit",
        composition_id="composition-audit",
        policy_id="policy-audit",
        presentation=PresentationComposition(values=composition or {}, provenance={}),
        policy=policy or DomainPresentationPolicy(),
        output_intent=output_intent,
        items=items
        or (
            DomainPresentationItemRef("finding-1", "FINDING", 0),
            DomainPresentationItemRef("warning-1", "WARNING", 1, warning_priority=0),
        ),
        primary_domain_id="domain:general",
    )


def _validate(request: DomainPresentationRequest):
    plan = DefaultDomainPresentationPlanner().plan(request)
    return plan, DefaultDomainPresentationPreservationValidator().validate(request, plan)


@pytest.mark.parametrize("item_type", ("WARNING", "CONTRADICTION", "ESCALATION"))
def test_always_visible_reference_hidden_is_blocked(item_type: str):
    request = _request(items=(DomainPresentationItemRef("item-1", item_type, 0, visible=False),))

    _, result = _validate(request)

    assert result.valid is False
    assert "REQUIRED_REFERENCE_HIDDEN" in result.codes


def test_pending_approval_hidden_is_blocked():
    request = _request(
        items=(
            DomainPresentationItemRef(
                "approval-1", "APPROVAL", 0, pending=True, visible=False
            ),
        )
    )

    _, result = _validate(request)

    assert "REQUIRED_REFERENCE_HIDDEN" in result.codes


def test_question_requiring_approval_is_a_visibility_obligation():
    request = _request(
        items=(
            DomainPresentationItemRef(
                "question-1", "QUESTION", 0, requires_approval=True, visible=False
            ),
        )
    )

    _, result = _validate(request)

    assert "REQUIRED_REFERENCE_HIDDEN" in result.codes


def test_required_reference_without_section_is_blocked():
    request = _request(items=(DomainPresentationItemRef("warning-1", "WARNING", 0),))
    plan = DefaultDomainPresentationPlanner().plan(request)
    plan = replace(plan, sections=())

    result = DefaultDomainPresentationPreservationValidator().validate(request, plan)

    assert "REQUIRED_REFERENCE_WITHOUT_SECTION" in result.codes


def test_required_reference_duplicated_in_sections_is_blocked():
    request = _request(items=(DomainPresentationItemRef("warning-1", "WARNING", 0),))
    plan = DefaultDomainPresentationPlanner().plan(request)
    duplicate_section = replace(plan.sections[0], section_id="duplicate", item_refs=("warning-1",))
    plan = replace(plan, sections=plan.sections + (duplicate_section,))

    result = DefaultDomainPresentationPreservationValidator().validate(request, plan)

    assert "DUPLICATE_REFERENCE" in result.codes


def test_completed_workflow_and_discarded_memory_proposal_are_not_forced_visible():
    request = _request(
        items=(
            DomainPresentationItemRef("workflow-1", "WORKFLOW", 0, pending=False, visible=False),
            DomainPresentationItemRef(
                "memory-1", "MEMORY_PROPOSAL", 1, pending=False, visible=False
            ),
        )
    )

    plan, result = _validate(request)

    assert result.valid is True
    assert plan.visibility_obligations == ()


def test_effective_required_section_from_supporting_composition_cannot_be_hidden():
    request = _request(composition={"required_sections": ["contradictions"]})
    plan = DefaultDomainPresentationPlanner().plan(request)
    sections = tuple(
        replace(section, visible=False)
        if section.section_id == "contradictions"
        else section
        for section in plan.sections
    )

    result = DefaultDomainPresentationPreservationValidator().validate(
        request, replace(plan, sections=sections)
    )

    assert "EFFECTIVE_REQUIRED_SECTION_HIDDEN" in result.codes


def test_effective_required_section_cannot_be_removed_or_marked_optional():
    request = _request(composition={"required_sections": ["contradictions"]})
    plan = DefaultDomainPresentationPlanner().plan(request)
    optional_sections = tuple(
        replace(section, required=False)
        if section.section_id == "contradictions"
        else section
        for section in plan.sections
    )

    result = DefaultDomainPresentationPreservationValidator().validate(
        request, replace(plan, sections=optional_sections)
    )

    assert "EFFECTIVE_REQUIRED_SECTION_NOT_REQUIRED" in result.codes


def test_effective_required_section_cannot_be_removed():
    request = _request(composition={"required_sections": ["contradictions"]})
    plan = DefaultDomainPresentationPlanner().plan(request)

    result = DefaultDomainPresentationPreservationValidator().validate(
        request,
        replace(
            plan,
            sections=tuple(
                section
                for section in plan.sections
                if section.section_id != "contradictions"
            ),
        ),
    )

    assert "EFFECTIVE_REQUIRED_SECTION_MISSING" in result.codes


def test_escalation_in_hidden_section_is_blocked():
    request = _request(items=(DomainPresentationItemRef("escalation-1", "ESCALATION", 0),))
    plan = DefaultDomainPresentationPlanner().plan(request)
    hidden_sections = tuple(
        replace(section, visible=False)
        if section.section_id == "escalations"
        else section
        for section in plan.sections
    )

    result = DefaultDomainPresentationPreservationValidator().validate(
        request, replace(plan, sections=hidden_sections)
    )

    assert "REQUIRED_SECTION_HIDDEN" in result.codes


def test_mapping_order_does_not_change_effective_required_sections():
    policy = DomainPresentationPolicy(required_sections=("warnings",))
    first = _request(policy=policy, composition={"required_sections": ["contradictions"], "views": ["summary"]})
    second = _request(policy=policy, composition={"views": ["summary"], "required_sections": ["contradictions"]})

    assert DefaultDomainPresentationPlanner().plan(first).sections == DefaultDomainPresentationPlanner().plan(second).sections


def test_inherited_uncertainty_and_provenance_require_visible_qualified_refs():
    policy = DomainPresentationPolicy(include_uncertainty=True, include_provenance=True)
    request = _request(
        policy=policy,
        items=(
            DomainPresentationItemRef(
                "hypothesis-1", "FINDING", 0, epistemic_kind="hypothesis", visible=False
            ),
            DomainPresentationItemRef(
                "evidence-1", "FINDING", 1, requires_provenance=True, visible=False
            ),
        ),
    )

    plan, result = _validate(request)

    assert {"hypothesis-1", "evidence-1"}.issubset(plan.visibility_obligations)
    assert "REQUIRED_REFERENCE_HIDDEN" in result.codes


def test_disclaimers_warning_position_and_detail_level_are_structural():
    policy = DomainPresentationPolicy(
        require_disclaimers=True,
        warning_position="after_content",
        detail_level="detailed",
    )
    request = _request(
        policy=policy,
        items=(
            DomainPresentationItemRef("warning-1", "WARNING", 0),
            DomainPresentationItemRef("finding-1", "FINDING", 1),
        ),
    )

    plan, result = _validate(request)

    assert "disclaimers" in {section.section_id for section in plan.sections}
    assert plan.sections[-1].section_id == "warnings"
    assert plan.detail_level == "detailed"
    assert result.valid is True


def test_preferred_output_is_used_only_when_request_has_no_resolved_intent():
    policy = DomainPresentationPolicy(preferred_output_types=("STRUCTURED",))

    inherited_plan, _ = _validate(_request(policy=policy, output_intent=None))
    explicit_plan, _ = _validate(
        _request(
            policy=policy,
            output_intent=DomainOutputIntent(DomainOutputIntentType.HUMAN_READABLE),
        )
    )

    assert inherited_plan.output_intent.output_type is DomainOutputIntentType.STRUCTURED
    assert explicit_plan.output_intent.output_type is DomainOutputIntentType.HUMAN_READABLE
    assert explicit_plan.preferred_output_type is DomainOutputIntentType.STRUCTURED


def test_no_speculation_keeps_hypothesis_qualified_without_presenting_it_as_fact():
    request = _request(
        policy=DomainPresentationPolicy(allow_speculation=False),
        items=(
            DomainPresentationItemRef(
                "hypothesis-1", "FINDING", 0, epistemic_kind="hypothesis"
            ),
        ),
    )

    plan, result = _validate(request)

    assert plan.qualified_hypothesis_refs == ("hypothesis-1",)
    assert result.valid is True


@pytest.mark.parametrize("non_finite", (math.nan, math.inf, -math.inf))
def test_safe_metadata_rejects_non_finite_floats(non_finite: float):
    with pytest.raises(DomainPresentationContractError):
        replace(_request(), safe_metadata={"score": non_finite})


def test_safe_metadata_accepts_finite_float_and_digest_is_canonical():
    request = replace(_request(), safe_metadata={"score": 0.5, "enabled": True})

    assert request.calculate_digest() == request.calculate_digest()
    assert request.safe_metadata["score"] == 0.5


def test_typed_groups_components_and_visibility_obligations_are_validated():
    request = _request(
        items=(
            DomainPresentationItemRef("finding-1", "FINDING", 0),
            DomainPresentationItemRef("warning-1", "WARNING", 1),
            DomainPresentationItemRef("question-1", "QUESTION", 2),
            DomainPresentationItemRef("approval-1", "APPROVAL", 3),
            DomainPresentationItemRef("escalation-1", "ESCALATION", 4),
            DomainPresentationItemRef("workflow-1", "WORKFLOW", 5),
            DomainPresentationItemRef("memory-1", "MEMORY_PROPOSAL", 6),
        )
    )
    plan = DefaultDomainPresentationPlanner().plan(request)
    invalid = replace(
        plan,
        warning_refs=("finding-1",),
        question_refs=(),
        approval_refs=("finding-1",),
        escalation_refs=("finding-1",),
        workflow_refs=("finding-1",),
        memory_proposal_refs=("finding-1",),
        visibility_obligations=plan.visibility_obligations + ("unknown-1",),
        components=(
            DomainPresentationComponentDescriptor("panel", "summary", "missing-section"),
        ),
    )

    result = DefaultDomainPresentationPreservationValidator().validate(request, invalid)

    assert "WARNING_GROUP_TYPE_MISMATCH" in result.codes
    assert "QUESTION_GROUP_MISSING_REF" in result.codes
    assert "APPROVAL_GROUP_TYPE_MISMATCH" in result.codes
    assert "ESCALATION_GROUP_TYPE_MISMATCH" in result.codes
    assert "WORKFLOW_GROUP_TYPE_MISMATCH" in result.codes
    assert "MEMORY_PROPOSAL_GROUP_TYPE_MISMATCH" in result.codes
    assert "UNKNOWN_VISIBILITY_REFERENCE" in result.codes
    assert "COMPONENT_UNKNOWN_SECTION" in result.codes
