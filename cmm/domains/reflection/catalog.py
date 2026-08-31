"""Phase 10.24 — Canonical Reflection Domain Catalog.

Single source of truth for the structural IDs of the Reflection Domain.

All other modules (definition, resources, profile, rules, operations,
workflows, bootstrap, integration) must import from this module rather than
re-declaring the same tuples.  This prevents catalog divergence.

The canonical entity types are semantic vocabulary surfaced through shared
Entity / KnowledgeItem bindings and the ``entity_types`` field of Reflection
resource definitions.  They are not new persistent classes.
"""

from __future__ import annotations

# ── Canonical reflection entity semantics ────────────────────────────────────

CANONICAL_REFLECTION_ENTITY_TYPES: tuple[str, ...] = (
    "reflection",
    "belief",
    "value",
    "question",
    "hypothesis",
    "emotion",
    "need",
    "conflict",
    "identity_narrative",
    "decision",
    "uncertainty",
)

# ── Canonical resource IDs ────────────────────────────────────────────────────
# ``domain:reflection`` yields slug ``reflection``; the shared resource and
# operation contracts require the domain prefix on the canonical IDs.

CANONICAL_REFLECTION_RESOURCE_IDS: tuple[str, ...] = (
    "reflection.user_message",
    "reflection.conversation",
    "reflection.note",
    "reflection.journal_entry",
    "reflection.memory_entry",
    "reflection.relationship_event",
    "reflection.life_event",
    "reflection.goal",
    "reflection.decision",
)

REFLECTION_RESOURCE_KINDS: tuple[str, ...] = tuple(
    resource_id.split(".", 1)[1] for resource_id in CANONICAL_REFLECTION_RESOURCE_IDS
)

# ── Canonical rule IDs ────────────────────────────────────────────────────────

CANONICAL_REFLECTION_RULE_IDS: tuple[str, ...] = (
    "reflection.multiple_hypotheses",
    "reflection.preserve_ambivalence",
    "reflection.belief_evidence",
    "reflection.open_question",
    "reflection.temporal_evolution",
    "reflection.no_forced_conclusion",
)

# Canonical rule class names (frozen design §5.3).  The classes are declared
# in ``rules.py`` under exactly these names.
CANONICAL_REFLECTION_RULE_NAMES: tuple[str, ...] = (
    "MultipleHypothesesRule",
    "PreserveAmbivalenceRule",
    "BeliefEvidenceRule",
    "OpenQuestionRule",
    "ReflectionTemporalEvolutionRule",
    "NoForcedConclusionRule",
)

# ── Canonical operation IDs ───────────────────────────────────────────────────
# The frozen spec's operation-prefix notation is ``reflection.*``; the shared
# ``DomainOperationDefinition`` contract requires the operation prefix to
# equal the domain slug ``reflection``.

CANONICAL_REFLECTION_OPERATION_IDS: tuple[str, ...] = (
    "reflection.structure_reflection",
    "reflection.extract_beliefs",
    "reflection.compare_versions",
    "reflection.identify_open_questions",
    "reflection.generate_hypotheses",
    "reflection.build_personal_timeline",
    "reflection.prepare_notion_entry",
    "reflection.generate_summary",
    "reflection.review_decision",
)

# ── Canonical workflow IDs ────────────────────────────────────────────────────

CANONICAL_REFLECTION_WORKFLOW_IDS: tuple[str, ...] = (
    "reflection.structured_reflection",
    "reflection.belief_review",
    "reflection.personal_question_exploration",
    "reflection.decision_reflection",
    "reflection.identity_narrative_review",
    "reflection.longitudinal_review",
)

# Canonical workflow display names (frozen design §5.5), keyed by workflow ID.
REFLECTION_WORKFLOW_NAMES_BY_ID: dict[str, str] = {
    "reflection.structured_reflection": "Structured Reflection",
    "reflection.belief_review": "Belief Review",
    "reflection.personal_question_exploration": "Personal Question Exploration",
    "reflection.decision_reflection": "Decision Reflection",
    "reflection.identity_narrative_review": "Identity Narrative Review",
    "reflection.longitudinal_review": "Longitudinal Reflection Review",
}

CANONICAL_REFLECTION_WORKFLOW_NAMES: tuple[str, ...] = tuple(
    REFLECTION_WORKFLOW_NAMES_BY_ID[workflow_id]
    for workflow_id in CANONICAL_REFLECTION_WORKFLOW_IDS
)

__all__ = [
    "CANONICAL_REFLECTION_ENTITY_TYPES",
    "CANONICAL_REFLECTION_OPERATION_IDS",
    "CANONICAL_REFLECTION_RESOURCE_IDS",
    "CANONICAL_REFLECTION_RULE_IDS",
    "CANONICAL_REFLECTION_RULE_NAMES",
    "CANONICAL_REFLECTION_WORKFLOW_IDS",
    "CANONICAL_REFLECTION_WORKFLOW_NAMES",
    "REFLECTION_RESOURCE_KINDS",
    "REFLECTION_WORKFLOW_NAMES_BY_ID",
]
