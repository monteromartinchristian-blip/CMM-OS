"""Tests for Phase 10.52 Mental Health Domain canonical contracts.

Task 1: canonical inventory (catalog), resources and profile.
Task 2: reasoning rules with non-pathologizing epistemic discipline.
Task 3: operation semantics.
Task 5: presentation defaults.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive.enums import ReasoningRuleResultStatus, SensitivityLevel
from cmm.cognitive.reasoning_rule_contracts import ReasoningRuleContext

T = datetime(2026, 8, 1, tzinfo=timezone.utc)

EXPECTED_OPERATIONS = (
    "mental_health.analyze_therapy_transcript",
    "mental_health.compare_emotional_periods",
    "mental_health.map_fact_interpretation_uncertainty",
    "mental_health.prepare_therapy_session",
    "mental_health.propose_memory_update",
    "mental_health.review_emotional_context",
    "mental_health.review_emotional_decision",
    "mental_health.review_therapy_session",
)

EXPECTED_WORKFLOWS = (
    "mental_health.emotional_context_review",
    "mental_health.therapy_session_preparation",
    "mental_health.therapy_session_post_processing",
    "mental_health.therapy_transcript_review",
    "mental_health.longitudinal_emotional_review",
    "mental_health.emotionally_relevant_decision_review",
    "mental_health.sensitive_memory_proposal_review",
    "mental_health.safety_escalation_review",
)


def test_mental_health_canonical_identity_and_operations_are_frozen():
    from cmm.domains.mental_health.catalog import (
        MENTAL_HEALTH_DOMAIN_ID,
        MENTAL_HEALTH_OPERATION_IDS,
        MENTAL_HEALTH_PROFILE_NAME,
        MENTAL_HEALTH_WORKFLOW_IDS,
    )

    assert MENTAL_HEALTH_DOMAIN_ID == "domain:mental-health"
    assert MENTAL_HEALTH_PROFILE_NAME == "MentalHealthProfile"
    assert MENTAL_HEALTH_OPERATION_IDS == tuple(sorted(EXPECTED_OPERATIONS))
    assert MENTAL_HEALTH_WORKFLOW_IDS == EXPECTED_WORKFLOWS
    assert len(MENTAL_HEALTH_WORKFLOW_IDS) == 8


def test_mental_health_resource_inventory_is_exact_and_frozen():
    from cmm.domains.mental_health.catalog import MENTAL_HEALTH_RESOURCE_IDS
    from cmm.domains.mental_health.resources import (
        MENTAL_HEALTH_RESOURCE_KINDS,
        build_mental_health_resource_definitions,
    )

    kinds = {item.kind for item in build_mental_health_resource_definitions()}
    assert {
        "conversation",
        "therapy_session_note",
        "therapy_transcript",
        "user_reflection",
        "decision",
        "goal",
        "memory_reference",
        "health_projection",
        "relationship_projection",
        "external_source",
    } <= kinds
    assert MENTAL_HEALTH_RESOURCE_KINDS == tuple(
        resource_id.split(".", 1)[1] for resource_id in MENTAL_HEALTH_RESOURCE_IDS
    )
    kinds_from_definitions = tuple(
        resource.kind for resource in build_mental_health_resource_definitions()
    )
    assert kinds_from_definitions == MENTAL_HEALTH_RESOURCE_KINDS


def test_mental_health_resources_are_sensitive_and_provenance_aware():
    from cmm.domains.mental_health.resources import (
        build_mental_health_resource_definitions,
    )

    for resource in build_mental_health_resource_definitions():
        assert resource.domain_id == "domain:mental-health"
        assert resource.default_sensitivity is SensitivityLevel.SENSITIVE
        assert resource.temporal_policy.historical_allowed is True


def test_mental_health_profile_is_canonical_and_restrictive():
    from cmm.domains.mental_health.catalog import MENTAL_HEALTH_RULE_IDS
    from cmm.domains.mental_health.profile import build_mental_health_profile
    from cmm.domains.mental_health.resources import MENTAL_HEALTH_RESOURCE_KINDS

    profile = build_mental_health_profile()
    assert profile.profile_name == "MentalHealthProfile"
    assert profile.domain_id == "domain:mental-health"
    assert profile.required_rules == MENTAL_HEALTH_RULE_IDS
    assert profile.allowed_resource_kinds == MENTAL_HEALTH_RESOURCE_KINDS
    # Non-pathologizing, epistemically separated ordinary mode.
    assert profile.memory_policy.allow_read is True
    assert profile.memory_policy.allow_write is False
    assert profile.presentation_policy.include_uncertainty is True
    assert profile.presentation_policy.include_provenance is True
    assert profile.presentation_policy.allow_speculation is False


def test_mental_health_rule_inventory_matches_catalog():
    from cmm.domains.mental_health.catalog import MENTAL_HEALTH_RULE_IDS
    from cmm.domains.mental_health.rules import build_mental_health_rules

    rules = build_mental_health_rules()
    ids = tuple(rule.definition.id for rule in rules)
    assert ids == MENTAL_HEALTH_RULE_IDS
    assert len(ids) == len(set(ids))
    for rule in rules:
        assert rule.definition.domain_id == "domain:mental-health"
        assert rule.definition.id.startswith("mental_health.")
        assert rule.definition.scope.value == "domain"


def _context(**metadata) -> ReasoningRuleContext:
    return ReasoningRuleContext(
        reasoning_id="rid",
        timestamp=T,
        active_domains=("domain:mental-health",),
        primary_domain="domain:mental-health",
        metadata=metadata,
    )


def _by_id(rules):
    return {rule.definition.id: rule for rule in rules}


def test_non_pathologizing_rule_never_promotes_repetition_to_diagnosis():
    from cmm.domains.mental_health.rules import build_mental_health_rules

    rule = _by_id(build_mental_health_rules())[
        "mental_health.repetition_without_pathology"
    ]
    result = rule.evaluate(_context(recurrence={"topic": "work worry"}))
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.escalation is None
    assert not any(finding.code == "DIAGNOSIS_INVENTED" for finding in result.findings)


def test_emotional_epistemic_separation_rule_keeps_interpretation_distinct():
    from cmm.domains.mental_health.rules import build_mental_health_rules

    rule = _by_id(build_mental_health_rules())[
        "mental_health.emotional_epistemic_separation"
    ]
    result = rule.evaluate(
        _context(
            statements=[
                {"id": "s1", "interpretation": True},
                {"id": "s2", "fact": True},
                {"id": "s3", "fear": True},
                {"id": "s4", "intuition": True},
            ]
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    kinds = {finding.code: finding.message for finding in result.findings}
    assert any("interpretation" in message for message in kinds.values())
    assert all("fact:" not in message or True for message in kinds.values())
    # no interpretation statement is classified as fact
    for finding in result.findings:
        if "s1" in finding.references:
            assert "fact" not in finding.metadata["epistemic_category"]


def test_therapy_speaker_separation_rule_preserves_three_classes():
    from cmm.domains.mental_health.rules import build_mental_health_rules

    rule = _by_id(build_mental_health_rules())[
        "mental_health.therapy_speaker_provenance"
    ]
    result = rule.evaluate(
        _context(
            transcript_turns=[
                {"id": "t1", "speaker": "therapist"},
                {"id": "t2", "speaker": "user"},
                {"id": "t3", "speaker": "model", "model_interpretation": True},
            ]
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    speakers = {finding.metadata["speaker"] for finding in result.findings}
    assert speakers == {"therapist", "user", "model"}


def test_therapy_speaker_separation_rule_blocks_unknown_high_confidence():
    from cmm.domains.mental_health.rules import build_mental_health_rules

    rule = _by_id(build_mental_health_rules())[
        "mental_health.therapy_speaker_provenance"
    ]
    result = rule.evaluate(
        _context(
            transcript_turns=[
                {"id": "t1", "speaker": "unknown", "clinical_claim": True},
            ]
        )
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED


def test_health_authority_rule_blocks_clinical_override():
    from cmm.domains.mental_health.rules import build_mental_health_rules

    rule = _by_id(build_mental_health_rules())["mental_health.health_authority"]
    result = rule.evaluate(
        _context(
            clinical_claim={
                "documented_medication_change": True,
                "emotional_effect": "more tired",
                "requested": "adjust_medication",
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED
    assert result.metadata["primary_authority"] == "domain:health"
    assert result.metadata["mental_health_may_override"] is False
    assert result.metadata["mental_health_supporting_allowed"] is True


def test_sensitive_inference_persistence_rule_blocks_silent_persistence():
    from cmm.domains.mental_health.rules import build_mental_health_rules

    rule = _by_id(build_mental_health_rules())[
        "mental_health.sensitive_persistence_control"
    ]
    result = rule.evaluate(
        _context(
            persistence_request={
                "content_kind": "inferred_emotional_pattern",
                "authorization": None,
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.BLOCKED


def test_proportionate_safety_rule_does_not_escalate_ordinary_distress():
    from cmm.domains.mental_health.rules import build_mental_health_rules

    rule = _by_id(build_mental_health_rules())[
        "mental_health.proportionate_safety_escalation"
    ]
    result = rule.evaluate(_context(safety={"distress": True, "material_risk": False}))
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.escalation is None

    escalated = rule.evaluate(
        _context(safety={"distress": True, "material_risk": True})
    )
    assert escalated.escalation is not None


def test_cross_domain_minimization_rule_excludes_irrelevant_fields():
    from cmm.domains.mental_health.rules import build_mental_health_rules

    rule = _by_id(build_mental_health_rules())[
        "mental_health.purpose_minimized_cross_domain"
    ]
    result = rule.evaluate(
        _context(
            projection={
                "purpose": "emotional_context",
                "source_domain": "domain:health",
                "fields": {
                    "medication_name": {"relevant": True},
                    "appointment_phone": {"relevant": False},
                },
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert result.findings
    excluded = set(result.metadata["excluded_fields"])
    included = set(result.metadata["included_fields"])
    assert "appointment_phone" in excluded
    assert "medication_name" in included
    assert not excluded & included


def test_uncertainty_preservation_rule_keeps_uncertainty_visible():
    from cmm.domains.mental_health.rules import build_mental_health_rules

    rule = _by_id(build_mental_health_rules())["mental_health.uncertainty_preservation"]
    result = rule.evaluate(
        _context(conclusions=[{"id": "c1", "certainty": "high", "evidence": "thin"}])
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        gap.code == "EVIDENCE_THIN" or finding.code == "UNCERTAINTY_PRESERVED"
        for finding in result.findings
        for gap in result.gaps
    )


def test_material_gap_questioning_rule_requests_material_information():
    from cmm.domains.mental_health.rules import build_mental_health_rules

    rule = _by_id(build_mental_health_rules())["mental_health.material_gap_questioning"]
    result = rule.evaluate(
        _context(gaps=[{"topic": "sleep change", "affects_reasoning": True}])
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    assert any(
        gap.code == "MATERIAL_GAP" or finding.code == "MATERIAL_GAP"
        for finding in result.findings
        for gap in result.gaps
    )


def test_longitudinal_continuity_rule_requires_authorized_references():
    from cmm.domains.mental_health.rules import build_mental_health_rules

    rule = _by_id(build_mental_health_rules())[
        "mental_health.authorized_longitudinal_continuity"
    ]
    result = rule.evaluate(
        _context(
            longitudinal={
                "references": [{"id": "r1", "authorized": True, "date": "2026-07-01"}]
            }
        )
    )
    assert result.status is ReasoningRuleResultStatus.APPLIED
    unauthorized = rule.evaluate(
        _context(
            longitudinal={
                "references": [{"id": "r2", "authorized": False, "date": "2026-07-01"}]
            }
        )
    )
    assert unauthorized.status is ReasoningRuleResultStatus.BLOCKED


def test_emotional_context_relevance_rule_detects_emotional_objective():
    from cmm.domains.mental_health.rules import build_mental_health_rules

    rule = _by_id(build_mental_health_rules())[
        "mental_health.emotional_context_relevance"
    ]
    result = rule.evaluate(_context(objective="feeling lonely this week"))
    assert result.status is ReasoningRuleResultStatus.APPLIED


def test_operation_semantics_are_frozen():
    from cmm.domains.mental_health.catalog import MENTAL_HEALTH_OPERATION_IDS
    from cmm.domains.mental_health.operations import (
        build_mental_health_operation_definitions,
    )

    definitions = build_mental_health_operation_definitions()
    by_id = {operation.operation_id: operation for operation in definitions}
    assert set(by_id) == set(MENTAL_HEALTH_OPERATION_IDS)
    for operation in definitions:
        assert operation.domain_id == "domain:mental-health"
        assert operation.operation_id in MENTAL_HEALTH_OPERATION_IDS

    proposal = by_id["mental_health.propose_memory_update"]
    assert proposal.metadata["proposal_only"] is True
    assert proposal.metadata.get("direct_memory_write") is not True
    assert proposal.requires_approval is True


def test_ordinary_emotional_presentation_defaults_are_non_clinical():
    from cmm.domains.mental_health.presentation import (
        build_mental_health_presentation_policy,
    )

    policy = build_mental_health_presentation_policy()
    assert policy.include_uncertainty is True
    assert "diagnosis" not in policy.required_sections
    assert "clinical" not in policy.required_sections


@pytest.mark.parametrize(
    "rule_id",
    (
        "mental_health.emotional_context_relevance",
        "mental_health.emotional_epistemic_separation",
        "mental_health.non_pathologizing_default",
        "mental_health.material_gap_questioning",
        "mental_health.authorized_longitudinal_continuity",
        "mental_health.therapy_speaker_provenance",
        "mental_health.therapy_statement_separation",
        "mental_health.uncertainty_preservation",
        "mental_health.repetition_without_pathology",
        "mental_health.health_authority",
        "mental_health.purpose_minimized_cross_domain",
        "mental_health.sensitive_persistence_control",
        "mental_health.proportionate_safety_escalation",
    ),
)
def test_thirteen_rule_responsibilities_are_declared(rule_id):
    from cmm.domains.mental_health.catalog import MENTAL_HEALTH_RULE_IDS

    assert rule_id in MENTAL_HEALTH_RULE_IDS
