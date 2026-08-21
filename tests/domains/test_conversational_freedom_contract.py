"""Cross-cutting conversational-freedom contract.

These tests intentionally separate:
- qualified conversational inference;
- promotion to fact / authoritative claim;
- sensitive persistence or action.

Production changes must remain minimal and must not touch Reflection.
"""

from dataclasses import replace
from datetime import datetime, timezone

from cmm.agent_runtime.domain_permission_contracts import PermissionCapability
from cmm.cognitive.enums import ReasoningRuleResultStatus
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext
from cmm.domains.composition_contracts import PresentationComposition
from cmm.domains.health.permissions import build_health_permission_policy
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
from cmm.domains.relationships.permissions import (
    build_relationships_permission_policy,
)
from cmm.domains.relationships.profile import build_relationships_profile
from cmm.domains.relationships.rules import build_relationships_rules

NOW = datetime(2026, 8, 21, tzinfo=timezone.utc)


def _context(domain_id: str, **metadata: object) -> ReasoningRuleContext:
    return ReasoningRuleContext(
        reasoning_id="conversational-freedom-red-1",
        timestamp=NOW,
        active_domains=(domain_id,),
        primary_domain=domain_id,
        metadata=metadata,
    )


def _relationship_rules():
    return {
        rule.definition.id: rule
        for rule in build_relationships_rules()
    }


def test_relationships_allows_sensitive_analysis_but_not_persistence() -> None:
    policy = build_relationships_permission_policy()

    assert PermissionCapability.SENSITIVE_INFERENCE in policy.allowed_capabilities
    assert (
        PermissionCapability.SENSITIVE_INFERENCE
        not in policy.prohibited_capabilities
    )
    assert policy.allow_sensitive_inference is True

    assert (
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST
        in policy.prohibited_capabilities
    )
    assert policy.allow_memory_write is False


def test_relationships_profile_allows_labelled_hypothesis_not_intent_as_fact() -> None:
    profile = build_relationships_profile()

    assert "system_hypothesis" in profile.allowed_inferences
    assert "possible_function" in profile.allowed_inferences
    assert "possible_origin" in profile.allowed_inferences

    assert "sensitive_inference" not in profile.prohibited_inferences
    assert "intent_as_fact" in profile.prohibited_inferences
    assert "sensitive_inference_persist" in profile.prohibited_inferences


def test_unsupported_intent_remains_hypothesis_instead_of_blocking() -> None:
    rule = _relationship_rules()["relationships.do_not_infer_intent"]

    result = rule.evaluate(
        _context(
            "domain:relationships",
            intent_claim={"intent": "wanted to keep me close"},
        )
    )

    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        finding.code == "INTENT_NOT_ESTABLISHED"
        for finding in result.findings
    )
    assert result.escalation is None


def test_health_allows_sensitive_analysis_but_not_persistence() -> None:
    policy = build_health_permission_policy()

    assert PermissionCapability.SENSITIVE_INFERENCE in policy.allowed_capabilities
    assert (
        PermissionCapability.SENSITIVE_INFERENCE
        not in policy.prohibited_capabilities
    )
    assert policy.allow_sensitive_inference is True

    assert (
        PermissionCapability.SENSITIVE_INFERENCE_PERSIST
        in policy.prohibited_capabilities
    )
    assert policy.allow_memory_write is False


def test_claimed_direct_evidence_without_reference_remains_blocked() -> None:
    rule = _relationship_rules()["relationships.do_not_infer_intent"]

    result = rule.evaluate(
        _context(
            "domain:relationships",
            intent_claim={
                "intent": "wanted to leave me",
                "direct_evidence": True,
            },
        )
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert any(
        finding.code == "INTENT_NOT_ESTABLISHED"
        for finding in result.findings
    )
    assert result.escalation is not None
    assert result.escalation.code == "INTENT_BLOCKED"


def test_claimed_sourced_statement_without_reference_remains_blocked() -> None:
    rule = _relationship_rules()["relationships.do_not_infer_intent"]

    result = rule.evaluate(
        _context(
            "domain:relationships",
            intent_claim={
                "intent": "wanted to leave me",
                "sourced_statement": True,
            },
        )
    )

    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert any(
        finding.code == "INTENT_NOT_ESTABLISHED"
        for finding in result.findings
    )
    assert result.escalation is not None
    assert result.escalation.code == "INTENT_BLOCKED"



# PRESENTATION CONVERSATIONAL-FREEDOM CONTRACT


def _presentation_request(
    *,
    output_type: DomainOutputIntentType = DomainOutputIntentType.HUMAN_READABLE,
    items: tuple[DomainPresentationItemRef, ...] | None = None,
    allow_speculation: bool | None = None,
) -> DomainPresentationRequest:
    return DomainPresentationRequest(
        request_id="conversational-freedom-presentation",
        upstream_result_id="conversational-result",
        composition_id="conversational-composition",
        policy_id="conversational-policy",
        presentation=PresentationComposition(values={}, provenance={}),
        policy=DomainPresentationPolicy(
            require_disclaimers=True,
            allow_speculation=allow_speculation,
        ),
        output_intent=DomainOutputIntent(output_type),
        items=items
        or (
            DomainPresentationItemRef(
                "finding-1",
                "FINDING",
                0,
                epistemic_kind="fact",
            ),
        ),
        primary_domain_id="domain:relationships",
    )


def test_human_readable_does_not_manufacture_empty_disclaimer_section() -> None:
    request = _presentation_request()

    plan = DefaultDomainPresentationPlanner().plan(request)

    assert "disclaimers" not in {
        section.section_id
        for section in plan.sections
    }


def test_human_readable_validator_accepts_absent_empty_disclaimer_section() -> None:
    request = _presentation_request()
    plan = DefaultDomainPresentationPlanner().plan(request)

    plan_without_empty_disclaimer = replace(
        plan,
        sections=tuple(
            section
            for section in plan.sections
            if section.section_id != "disclaimers"
        ),
    )

    result = DefaultDomainPresentationPreservationValidator().validate(
        request,
        plan_without_empty_disclaimer,
    )

    assert result.valid is True
    assert "DISCLAIMERS_MISSING" not in result.codes


def test_structured_output_keeps_required_disclaimer_structure() -> None:
    request = _presentation_request(
        output_type=DomainOutputIntentType.STRUCTURED,
    )

    plan = DefaultDomainPresentationPlanner().plan(request)
    result = DefaultDomainPresentationPreservationValidator().validate(
        request,
        plan,
    )

    disclaimer = next(
        section
        for section in plan.sections
        if section.section_id == "disclaimers"
    )

    assert disclaimer.required is True
    assert disclaimer.visible is True
    assert result.valid is True


def test_human_readable_keeps_real_warning_visible() -> None:
    request = _presentation_request(
        items=(
            DomainPresentationItemRef(
                "warning-1",
                "WARNING",
                0,
                warning_priority=0,
            ),
            DomainPresentationItemRef(
                "finding-1",
                "FINDING",
                1,
            ),
        ),
    )

    plan = DefaultDomainPresentationPlanner().plan(request)

    warning_section = next(
        section
        for section in plan.sections
        if section.section_id == "warnings"
    )

    assert warning_section.visible is True
    assert warning_section.item_refs == ("warning-1",)
    assert plan.warning_refs == ("warning-1",)


def test_human_readable_keeps_hypothesis_epistemically_qualified() -> None:
    request = _presentation_request(
        allow_speculation=False,
        items=(
            DomainPresentationItemRef(
                "hypothesis-1",
                "FINDING",
                0,
                epistemic_kind="hypothesis",
            ),
        ),
    )

    plan = DefaultDomainPresentationPlanner().plan(request)
    result = DefaultDomainPresentationPreservationValidator().validate(
        request,
        plan,
    )

    assert plan.qualified_hypothesis_refs == ("hypothesis-1",)
    assert result.valid is True
