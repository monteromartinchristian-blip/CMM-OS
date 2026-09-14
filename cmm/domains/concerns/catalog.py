"""Phase 10.25 — Canonical Concerns Domain Catalog.

Single source of truth for the structural IDs of the Concerns Domain.

All other modules (definition, resources, profile, rules, operations,
workflows, bootstrap, integration) must import from this module rather than
re-declaring the same tuples.  This prevents catalog divergence.

The canonical entity types are semantic vocabulary surfaced through shared
Entity / KnowledgeItem bindings and the ``entity_types`` field of Concerns
resource definitions.  They are not new persistent classes.

Canonical identity (frozen design §5):

    domain:concerns / namespace ``concerns.*`` / version ``1.0.0``

Counts are frozen acceptance criteria (frozen design §91):
17 entities, 10 resources, 14 rules, 13 operations, 8 workflows.
"""

from __future__ import annotations

# ── Canonical concerns entity semantics ──────────────────────────────────────

CANONICAL_CONCERNS_ENTITY_TYPES: tuple[str, ...] = (
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

# ── Canonical resource IDs ────────────────────────────────────────────────────
# ``domain:concerns`` yields slug ``concerns``; the shared resource and
# operation contracts require the domain prefix on the canonical IDs.
# ``domain_result`` is the authorized cross-domain projection boundary; a
# ``memory_entry`` is provenance, not current truth; ``external_source``
# is NOT external-search authorization.

CANONICAL_CONCERNS_RESOURCE_IDS: tuple[str, ...] = (
    "concerns.user_message",
    "concerns.conversation",
    "concerns.note",
    "concerns.journal_entry",
    "concerns.memory_entry",
    "concerns.event",
    "concerns.goal",
    "concerns.decision",
    "concerns.domain_result",
    "concerns.external_source",
)

CONCERNS_RESOURCE_KINDS: tuple[str, ...] = tuple(
    resource_id.split(".", 1)[1] for resource_id in CANONICAL_CONCERNS_RESOURCE_IDS
)

# ── Canonical rule IDs ────────────────────────────────────────────────────────

CANONICAL_CONCERNS_RULE_IDS: tuple[str, ...] = (
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

# Canonical rule class names (frozen design §15).  The classes are declared in
# ``rules.py`` under exactly these names.
CANONICAL_CONCERNS_RULE_NAMES: tuple[str, ...] = (
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

# ── Canonical operation IDs ───────────────────────────────────────────────────
# All thirteen operations are analysis/preparation operations.

CANONICAL_CONCERNS_OPERATION_IDS: tuple[str, ...] = (
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

# ── Canonical workflow IDs ────────────────────────────────────────────────────

CANONICAL_CONCERNS_WORKFLOW_IDS: tuple[str, ...] = (
    "concerns.open_concern_conversation",
    "concerns.talk_it_through",
    "concerns.reality_check",
    "concerns.reassurance_review",
    "concerns.practical_problem_solving",
    "concerns.decision_under_uncertainty",
    "concerns.recurring_concern_review",
    "concerns.professional_discussion_preparation",
)

# Canonical workflow display names (implementation plan Task 1), keyed by
# workflow ID.  Names are derived from this mapping, never redeclared.
CONCERNS_WORKFLOW_NAMES_BY_ID: dict[str, str] = {
    "concerns.open_concern_conversation": "Open Concern Conversation",
    "concerns.talk_it_through": "Talk It Through",
    "concerns.reality_check": "Reality Check",
    "concerns.reassurance_review": "Reassurance Review",
    "concerns.practical_problem_solving": "Practical Problem Solving",
    "concerns.decision_under_uncertainty": "Decision Under Uncertainty",
    "concerns.recurring_concern_review": "Recurring Concern Review",
    "concerns.professional_discussion_preparation": (
        "Professional Discussion Preparation"
    ),
}

CANONICAL_CONCERNS_WORKFLOW_NAMES: tuple[str, ...] = tuple(
    CONCERNS_WORKFLOW_NAMES_BY_ID[workflow_id]
    for workflow_id in CANONICAL_CONCERNS_WORKFLOW_IDS
)

__all__ = [
    "CANONICAL_CONCERNS_ENTITY_TYPES",
    "CANONICAL_CONCERNS_OPERATION_IDS",
    "CANONICAL_CONCERNS_RESOURCE_IDS",
    "CANONICAL_CONCERNS_RULE_IDS",
    "CANONICAL_CONCERNS_RULE_NAMES",
    "CANONICAL_CONCERNS_WORKFLOW_IDS",
    "CANONICAL_CONCERNS_WORKFLOW_NAMES",
    "CONCERNS_RESOURCE_KINDS",
    "CONCERNS_WORKFLOW_NAMES_BY_ID",
]
