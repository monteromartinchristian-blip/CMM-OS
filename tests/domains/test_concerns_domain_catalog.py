"""Phase 10.25 — Concerns Domain canonical catalog tests.

The catalog module is the single source of truth for the frozen canonical
members (frozen design §13, §14, §15, §33, §47).  These tests pin the exact
17/10/14/13/8 surface, duplicate-freedom, the ``concerns.*`` operation prefix,
and the derived resource kinds / workflow names (never redeclared).
"""

from __future__ import annotations

from cmm.domains.concerns.catalog import (
    CANONICAL_CONCERNS_ENTITY_TYPES,
    CANONICAL_CONCERNS_OPERATION_IDS,
    CANONICAL_CONCERNS_RESOURCE_IDS,
    CANONICAL_CONCERNS_RULE_IDS,
    CANONICAL_CONCERNS_RULE_NAMES,
    CANONICAL_CONCERNS_WORKFLOW_IDS,
    CANONICAL_CONCERNS_WORKFLOW_NAMES,
    CONCERNS_RESOURCE_KINDS,
    CONCERNS_WORKFLOW_NAMES_BY_ID,
)


def test_entities_exactly_17():
    assert CANONICAL_CONCERNS_ENTITY_TYPES == (
        "concern",
        "situation",
        "trigger",
        "emotion",
        "fear",
        "need",
        "support_need",
        "fact",
        "interpretation",
        "hypothesis",
        "scenario",
        "evidence",
        "uncertainty",
        "risk",
        "desired_outcome",
        "option",
        "action",
    )
    assert len(CANONICAL_CONCERNS_ENTITY_TYPES) == 17


def test_resources_exactly_10():
    assert CONCERNS_RESOURCE_KINDS == (
        "user_message",
        "conversation",
        "note",
        "journal_entry",
        "memory_entry",
        "event",
        "goal",
        "decision",
        "domain_result",
        "external_source",
    )
    assert len(CONCERNS_RESOURCE_KINDS) == 10
    assert CANONICAL_CONCERNS_RESOURCE_IDS == tuple(
        f"concerns.{kind}" for kind in CONCERNS_RESOURCE_KINDS
    )


def test_rules_exactly_14():
    assert CANONICAL_CONCERNS_RULE_NAMES == (
        "UnderstandBeforeInterveneRule",
        "EmotionalValidationRule",
        "ExperienceRealitySeparationRule",
        "SupportNeedCalibrationRule",
        "ContextualQuestionRule",
        "UncertaintyPreservationRule",
        "EvidenceCalibratedReassuranceRule",
        "ProportionalRiskRule",
        "NoCatastrophicEscalationRule",
        "NoFalseReassuranceRule",
        "RepetitionWithoutPathologizingRule",
        "AgencyWithoutPressureRule",
        "DirectnessWithoutHarshnessRule",
        "ImmediateRiskEscalationRule",
    )
    assert len(CANONICAL_CONCERNS_RULE_NAMES) == 14
    assert CANONICAL_CONCERNS_RULE_IDS == (
        "concerns.understand_before_intervene",
        "concerns.emotional_validation",
        "concerns.experience_reality_separation",
        "concerns.support_need_calibration",
        "concerns.contextual_question",
        "concerns.uncertainty_preservation",
        "concerns.evidence_calibrated_reassurance",
        "concerns.proportional_risk",
        "concerns.no_catastrophic_escalation",
        "concerns.no_false_reassurance",
        "concerns.repetition_without_pathologizing",
        "concerns.agency_without_pressure",
        "concerns.directness_without_harshness",
        "concerns.immediate_risk_escalation",
    )


def test_operations_exactly_13():
    assert CANONICAL_CONCERNS_OPERATION_IDS == (
        "concerns.understand_concern",
        "concerns.infer_support_need",
        "concerns.map_lived_experience",
        "concerns.separate_reality_interpretation",
        "concerns.explore_hypotheses",
        "concerns.calibrate_uncertainty",
        "concerns.evaluate_reassurance",
        "concerns.evaluate_risk",
        "concerns.identify_open_questions",
        "concerns.explore_options",
        "concerns.prepare_next_step",
        "concerns.review_recurring_concern",
        "concerns.prepare_professional_discussion",
    )
    assert len(CANONICAL_CONCERNS_OPERATION_IDS) == 13


def test_workflow_names_exactly_8():
    assert CANONICAL_CONCERNS_WORKFLOW_NAMES == (
        "Open Concern Conversation",
        "Talk It Through",
        "Reality Check",
        "Reassurance Review",
        "Practical Problem Solving",
        "Decision Under Uncertainty",
        "Recurring Concern Review",
        "Professional Discussion Preparation",
    )
    assert len(CANONICAL_CONCERNS_WORKFLOW_NAMES) == 8
    assert CANONICAL_CONCERNS_WORKFLOW_IDS == (
        "concerns.open_concern_conversation",
        "concerns.talk_it_through",
        "concerns.reality_check",
        "concerns.reassurance_review",
        "concerns.practical_problem_solving",
        "concerns.decision_under_uncertainty",
        "concerns.recurring_concern_review",
        "concerns.professional_discussion_preparation",
    )
    # Names are derived from catalog data, never redeclared.
    assert CANONICAL_CONCERNS_WORKFLOW_NAMES == tuple(
        CONCERNS_WORKFLOW_NAMES_BY_ID[workflow_id]
        for workflow_id in CANONICAL_CONCERNS_WORKFLOW_IDS
    )


def test_no_duplicates():
    for values in (
        CANONICAL_CONCERNS_ENTITY_TYPES,
        CANONICAL_CONCERNS_RESOURCE_IDS,
        CANONICAL_CONCERNS_RULE_IDS,
        CANONICAL_CONCERNS_RULE_NAMES,
        CANONICAL_CONCERNS_OPERATION_IDS,
        CANONICAL_CONCERNS_WORKFLOW_IDS,
        CANONICAL_CONCERNS_WORKFLOW_NAMES,
    ):
        assert len(values) == len(set(values))


def test_operation_prefix_is_concerns():
    for operation_id in CANONICAL_CONCERNS_OPERATION_IDS:
        assert operation_id.startswith("concerns.")
        assert operation_id.count(".") == 1


def test_resource_prefix_is_concerns():
    for resource_id in CANONICAL_CONCERNS_RESOURCE_IDS:
        assert resource_id.startswith("concerns.")
        assert resource_id.count(".") == 1


def test_rule_ids_align_with_rule_names():
    """Every rule ID is the snake_case projection of its canonical class name."""
    import re

    for rule_id, rule_name in zip(CANONICAL_CONCERNS_RULE_IDS, CANONICAL_CONCERNS_RULE_NAMES):
        suffix = rule_id.split(".", 1)[1]
        projected = re.sub(r"(?<!^)(?=[A-Z])", "_", rule_name.replace("Rule", "")).lower()
        assert suffix == projected, f"{rule_id} does not project {rule_name}"
