"""Phase 10.21 — Canonical Relationships Domain Catalog.

Single source of truth for the structural IDs of Relationships Domain.

All other modules (definition, operations, rules, resources, workflows,
bootstrap) must import from this module rather than re-declaring the same
tuples.  This prevents catalog divergence.
"""

from __future__ import annotations

# ── Canonical relationships entity semantics ─────────────────────────────────
# These are semantic types, not new persistent classes.  They are surfaced
# through canonical Entity / KnowledgeItem bindings and the ``entity_types``
# field of Relationships resource definitions.

CANONICAL_RELATIONSHIPS_ENTITY_TYPES: tuple[str, ...] = (
    "boundary",
    "commitment",
    "conflict",
    "conversation",
    "emotion",
    "expectation",
    "interaction",
    "need",
    "person",
    "reconciliation",
    "relationship",
    "rupture",
    "support_event",
)

# ── Canonical operation IDs ───────────────────────────────────────────────────

CANONICAL_RELATIONSHIPS_OPERATION_IDS: tuple[str, ...] = (
    "relationships.build_timeline",
    "relationships.compare_periods",
    "relationships.detect_patterns",
    "relationships.extract_events",
    "relationships.generate_relationship_summary",
    "relationships.identify_needs",
    "relationships.prepare_conversation",
    "relationships.review_boundaries",
    "relationships.separate_facts_interpretations",
    "relationships.track_open_questions",
)

# ── Canonical rule IDs ────────────────────────────────────────────────────────

CANONICAL_RELATIONSHIPS_RULE_IDS: tuple[str, ...] = (
    "relationships.ambivalence_preservation",
    "relationships.boundary_consistency",
    "relationships.do_not_infer_intent",
    "relationships.emotion_need_distinction",
    "relationships.pattern_without_certainty",
    "relationships.relationship_timeline",
    "relationships.self_other_perspective",
    "relationships.separate_facts_interpretations",
)

# ── Canonical resource IDs ────────────────────────────────────────────────────

CANONICAL_RELATIONSHIPS_RESOURCE_IDS: tuple[str, ...] = (
    "relationships.communication",
    "relationships.conversation",
    "relationships.memory_entry",
    "relationships.note",
    "relationships.personal_reflection",
    "relationships.relationship_event",
    "relationships.timeline",
    "relationships.user_message",
)

# ── Canonical workflow IDs ────────────────────────────────────────────────────

CANONICAL_RELATIONSHIPS_WORKFLOW_IDS: tuple[str, ...] = (
    "relationships.boundary_review",
    "relationships.conflict_review",
    "relationships.conversation_preparation",
    "relationships.decision_support",
    "relationships.pattern_evolution_review",
    "relationships.timeline_analysis",
)

__all__ = [
    "CANONICAL_RELATIONSHIPS_ENTITY_TYPES",
    "CANONICAL_RELATIONSHIPS_OPERATION_IDS",
    "CANONICAL_RELATIONSHIPS_RESOURCE_IDS",
    "CANONICAL_RELATIONSHIPS_RULE_IDS",
    "CANONICAL_RELATIONSHIPS_WORKFLOW_IDS",
]
