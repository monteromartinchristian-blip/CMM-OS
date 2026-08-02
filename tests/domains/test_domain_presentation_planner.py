"""Phase 10.16 planner plans structure without semantic mutation or rendering."""

from __future__ import annotations

import pytest

from cmm.domains.composition_contracts import PresentationComposition
from cmm.domains.errors import DomainPresentationOutputIntentError
from cmm.domains.presentation_contracts import (
    DomainOutputIntent,
    DomainOutputIntentType,
    DomainPresentationItemRef,
    DomainPresentationRequest,
)
from cmm.domains.presentation_planner import DefaultDomainPresentationPlanner
from cmm.domains.profile_contracts import DomainPresentationPolicy


def _request(*, output: DomainOutputIntent | None = None) -> DomainPresentationRequest:
    return DomainPresentationRequest(
        request_id="request-1",
        upstream_result_id="result-1",
        composition_id="composition-1",
        policy_id="profile-1",
        presentation=PresentationComposition(
            values={"required_sections": ["warnings"]}, provenance={}
        ),
        policy=DomainPresentationPolicy(
            required_sections=("findings",),
            protected_terms=("contraindication",),
            term_glosses={"contraindication": "brief_gloss"},
            preferred_components=("warning-banner",),
            preferred_views=("summary",),
            allowed_output_types=("HUMAN_READABLE", "ARTIFACT_REQUEST"),
        ),
        output_intent=output or DomainOutputIntent(DomainOutputIntentType.HUMAN_READABLE),
        items=(
            DomainPresentationItemRef("finding-1", "FINDING", 2, epistemic_kind="fact", confidence=0.8, requires_provenance=True),
            DomainPresentationItemRef("warning-2", "WARNING", 1, warning_priority=1),
            DomainPresentationItemRef("warning-1", "WARNING", 0, warning_priority=0),
            DomainPresentationItemRef("question-1", "QUESTION", 3),
            DomainPresentationItemRef("approval-1", "APPROVAL", 4),
            DomainPresentationItemRef("escalation-1", "ESCALATION", 5),
            DomainPresentationItemRef("workflow-1", "WORKFLOW", 6),
            DomainPresentationItemRef("memory-proposal-1", "MEMORY_PROPOSAL", 7),
        ),
        primary_domain_id="domain:general",
    )


def test_planner_orders_sections_and_warnings_without_copying_or_changing_items():
    request = _request()
    plan = DefaultDomainPresentationPlanner().plan(request)

    assert [section.section_id for section in plan.sections][:2] == ["findings", "warnings"]
    assert next(section for section in plan.sections if section.section_id == "warnings").item_refs == (
        "warning-1", "warning-2"
    )
    assert plan.protected_terms == ("contraindication",)
    assert dict(plan.term_glosses) == {"contraindication": "brief_gloss"}
    assert plan.question_refs == ("question-1",)
    assert plan.approval_refs == ("approval-1",)
    assert plan.escalation_refs == ("escalation-1",)
    assert plan.workflow_refs == ("workflow-1",)
    assert plan.memory_proposal_refs == ("memory-proposal-1",)
    assert plan.output_intent.output_type is DomainOutputIntentType.HUMAN_READABLE
    assert "finding-1" not in plan.to_dict().__repr__() or "content" not in plan.to_dict()


def test_planner_is_deterministic_and_artifact_intent_does_not_render_a_file():
    request = _request(
        output=DomainOutputIntent(DomainOutputIntentType.ARTIFACT_REQUEST, "PDF")
    )
    planner = DefaultDomainPresentationPlanner()

    first = planner.plan(request)
    second = planner.plan(request)

    assert first == second
    assert first.plan_id == second.plan_id
    assert first.output_intent.artifact_format == "PDF"
    assert "file" not in first.to_dict()


def test_planner_rejects_logical_output_not_allowed_by_effective_policy():
    with pytest.raises(DomainPresentationOutputIntentError):
        DefaultDomainPresentationPlanner().plan(
            _request(output=DomainOutputIntent(DomainOutputIntentType.STRUCTURED))
        )


def test_warnings_without_resolved_priority_keep_upstream_source_order():
    request = _request()
    request = DomainPresentationRequest(
        **{
            **request.to_dict(),
            "presentation": request.presentation,
            "policy": request.policy,
            "output_intent": request.output_intent,
            "items": (
                DomainPresentationItemRef("warning-2", "WARNING", 2),
                DomainPresentationItemRef("warning-1", "WARNING", 1),
            ),
        }
    )

    plan = DefaultDomainPresentationPlanner().plan(request)

    assert plan.warning_refs == ("warning-1", "warning-2")
