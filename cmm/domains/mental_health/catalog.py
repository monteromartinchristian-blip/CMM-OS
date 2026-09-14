"""Phase 10.52 — Canonical Mental Health Domain Catalog.

Single source of truth for the structural IDs of the Mental Health Domain.

All other modules (definition, resources, profile, rules, operations,
workflows, bootstrap, integration) must import from this module rather than
re-declaring the same tuples.  This prevents catalog divergence.

Canonical identity (frozen design §6):

    domain:mental-health / namespace ``mental_health.*`` / version ``1.0.0``

Counts are frozen acceptance criteria (plan Task 1 / spec §19–§20):
13 rules, 10 resource families, 8 operations, 8 workflows.
"""

from __future__ import annotations

# ── Canonical mental-health entity semantics ─────────────────────────────────
# Semantic vocabulary surfaced through shared Entity / KnowledgeItem bindings
# and the ``entity_types`` field of Mental Health resource definitions.  They
# are not new persistent classes and never become a second epistemic taxonomy:
# the canonical Cognitive Layer kinds remain authoritative (frozen design §10).

CANONICAL_MENTAL_HEALTH_ENTITY_TYPES: tuple[str, ...] = (
    "emotion",
    "emotional_objective",
    "therapy_session",
    "therapy_topic",
    "coping_pattern",
    "emotional_loop",
    "trigger",
    "fact",
    "observation",
    "interpretation",
    "hypothesis",
    "fear",
    "intuition",
    "preference",
    "decision",
    "uncertainty",
)

# ── Canonical resource IDs ────────────────────────────────────────────────────
# ``domain:mental-health`` yields slug ``mental-health``; the shared resource
# and operation contracts require the domain prefix on the canonical IDs.
# ``health_projection`` is an authorized Health-owned projection: it is never
# rewritten by Mental Health.  ``external_source`` is NOT external-search
# authorization.

CANONICAL_MENTAL_HEALTH_RESOURCE_IDS: tuple[str, ...] = (
    "mental_health.conversation",
    "mental_health.therapy_session_note",
    "mental_health.therapy_transcript",
    "mental_health.user_reflection",
    "mental_health.decision",
    "mental_health.goal",
    "mental_health.memory_reference",
    "mental_health.health_projection",
    "mental_health.relationship_projection",
    "mental_health.external_source",
)

MENTAL_HEALTH_RESOURCE_KINDS: tuple[str, ...] = tuple(
    resource_id.split(".", 1)[1] for resource_id in CANONICAL_MENTAL_HEALTH_RESOURCE_IDS
)

# ── Canonical rule IDs ────────────────────────────────────────────────────────
# Exactly the thirteen required semantic responsibilities (plan Task 2).

CANONICAL_MENTAL_HEALTH_RULE_IDS: tuple[str, ...] = (
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
)

# ── Canonical operation IDs ──────────────────────────────────────────────────

CANONICAL_MENTAL_HEALTH_OPERATION_IDS: tuple[str, ...] = (
    "mental_health.analyze_therapy_transcript",
    "mental_health.compare_emotional_periods",
    "mental_health.map_fact_interpretation_uncertainty",
    "mental_health.prepare_therapy_session",
    "mental_health.propose_memory_update",
    "mental_health.review_emotional_context",
    "mental_health.review_emotional_decision",
    "mental_health.review_therapy_session",
)

# ── Canonical workflow IDs ───────────────────────────────────────────────────
# Stable IDs under the ``mental_health.`` namespace; display titles are never
# used as identifiers (plan Task 1).

CANONICAL_MENTAL_HEALTH_WORKFLOW_IDS: tuple[str, ...] = (
    "mental_health.emotional_context_review",
    "mental_health.therapy_session_preparation",
    "mental_health.therapy_session_post_processing",
    "mental_health.therapy_transcript_review",
    "mental_health.longitudinal_emotional_review",
    "mental_health.emotionally_relevant_decision_review",
    "mental_health.sensitive_memory_proposal_review",
    "mental_health.safety_escalation_review",
)

# Canonical workflow display names keyed by workflow ID.
MENTAL_HEALTH_WORKFLOW_NAMES_BY_ID: dict[str, str] = {
    "mental_health.emotional_context_review": (
        "Mental Health — Emotional Context Review"
    ),
    "mental_health.therapy_session_preparation": (
        "Mental Health — Therapy Session Preparation"
    ),
    "mental_health.therapy_session_post_processing": (
        "Mental Health — Therapy Session Post-Processing"
    ),
    "mental_health.therapy_transcript_review": (
        "Mental Health — Therapy Transcript Review"
    ),
    "mental_health.longitudinal_emotional_review": (
        "Mental Health — Longitudinal Emotional Review"
    ),
    "mental_health.emotionally_relevant_decision_review": (
        "Mental Health — Emotionally Relevant Decision Review"
    ),
    "mental_health.sensitive_memory_proposal_review": (
        "Mental Health — Sensitive Memory Proposal Review"
    ),
    "mental_health.safety_escalation_review": (
        "Mental Health — Safety Escalation Review"
    ),
}

CANONICAL_MENTAL_HEALTH_WORKFLOW_NAMES: tuple[str, ...] = tuple(
    MENTAL_HEALTH_WORKFLOW_NAMES_BY_ID[workflow_id]
    for workflow_id in CANONICAL_MENTAL_HEALTH_WORKFLOW_IDS
)

MENTAL_HEALTH_DOMAIN_ID = "domain:mental-health"
MENTAL_HEALTH_PROFILE_NAME = "MentalHealthProfile"

# Convenience aliases (single source of truth stays the CANONICAL_* tuples).
MENTAL_HEALTH_RESOURCE_IDS: tuple[str, ...] = CANONICAL_MENTAL_HEALTH_RESOURCE_IDS
MENTAL_HEALTH_RULE_IDS: tuple[str, ...] = CANONICAL_MENTAL_HEALTH_RULE_IDS
MENTAL_HEALTH_OPERATION_IDS: tuple[str, ...] = CANONICAL_MENTAL_HEALTH_OPERATION_IDS
MENTAL_HEALTH_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_MENTAL_HEALTH_WORKFLOW_IDS

__all__ = [
    "CANONICAL_MENTAL_HEALTH_ENTITY_TYPES",
    "CANONICAL_MENTAL_HEALTH_OPERATION_IDS",
    "CANONICAL_MENTAL_HEALTH_RESOURCE_IDS",
    "CANONICAL_MENTAL_HEALTH_RULE_IDS",
    "CANONICAL_MENTAL_HEALTH_WORKFLOW_IDS",
    "CANONICAL_MENTAL_HEALTH_WORKFLOW_NAMES",
    "MENTAL_HEALTH_DOMAIN_ID",
    "MENTAL_HEALTH_OPERATION_IDS",
    "MENTAL_HEALTH_PROFILE_NAME",
    "MENTAL_HEALTH_RESOURCE_IDS",
    "MENTAL_HEALTH_RESOURCE_KINDS",
    "MENTAL_HEALTH_RULE_IDS",
    "MENTAL_HEALTH_WORKFLOW_IDS",
    "MENTAL_HEALTH_WORKFLOW_NAMES_BY_ID",
]
