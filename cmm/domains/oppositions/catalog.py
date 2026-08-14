"""Phase 10.23 — Canonical Opposition Domain Catalog.

Single source of truth for the structural IDs of the Opposition Domain.

All other modules (definition, resources, profile, rules, operations,
workflows, bootstrap) must import from this module rather than re-declaring
the same tuples.  This prevents catalog divergence.

The canonical entity types are semantic vocabulary surfaced through shared
Entity / KnowledgeItem bindings and the ``entity_types`` field of Opposition
resource definitions.  They are not new persistent classes.
"""

from __future__ import annotations

# ── Canonical opposition entity semantics ─────────────────────────────────────

CANONICAL_OPPOSITION_ENTITY_TYPES: tuple[str, ...] = (
    "alternative_route",
    "block",
    "call",
    "deadline",
    "exam",
    "merit",
    "mock_exam",
    "opposition",
    "public_body",
    "requirement",
    "score",
    "study_session",
    "syllabus",
    "topic",
)

# ── Canonical resource IDs ────────────────────────────────────────────────────

CANONICAL_OPPOSITION_RESOURCE_IDS: tuple[str, ...] = (
    "oppositions.calendar_event",
    "oppositions.external_official_source",
    "oppositions.memory_entry",
    "oppositions.mock_exam",
    "oppositions.note",
    "oppositions.official_call",
    "oppositions.regulation",
    "oppositions.score_record",
    "oppositions.study_plan",
    "oppositions.syllabus",
    "oppositions.user_message",
)

# ── Canonical rule IDs ────────────────────────────────────────────────────────

CANONICAL_OPPOSITION_RULE_IDS: tuple[str, ...] = (
    "oppositions.alternative_route",
    "oppositions.mock_exam_interpretation",
    "oppositions.official_call_priority",
    "oppositions.study_feasibility",
    "oppositions.syllabus_coverage",
    "oppositions.temporal_validity",
)

# ── Canonical operation IDs ───────────────────────────────────────────────────
# The frozen spec's operation-prefix notation is ``opposition.`` (singular).
# ``domain:oppositions`` yields slug ``oppositions`` and the shared
# ``DomainOperationDefinition`` contract (operation_contracts.py) requires the
# operation prefix to equal that slug, so the canonical registered form uses the
# plural domain convention ``oppositions.`` exactly like the other ID families.
# This is spec §7's sanctioned "mechanically different canonical form".

CANONICAL_OPPOSITION_OPERATION_IDS: tuple[str, ...] = (
    "oppositions.compare_bodies",
    "oppositions.create_study_plan",
    "oppositions.divide_syllabus",
    "oppositions.generate_revision_plan",
    "oppositions.generate_weekly_review",
    "oppositions.identify_risks",
    "oppositions.review_call",
    "oppositions.review_mock_exam",
    "oppositions.track_progress",
    "oppositions.update_progress",
)

# ── Canonical workflow IDs ────────────────────────────────────────────────────

CANONICAL_OPPOSITION_WORKFLOW_IDS: tuple[str, ...] = (
    "oppositions.alternative_route_comparison",
    "oppositions.call_analysis",
    "oppositions.exam_readiness",
    "oppositions.mock_exam_review",
    "oppositions.setup",
    "oppositions.syllabus_revision",
    "oppositions.weekly_review",
)

__all__ = [
    "CANONICAL_OPPOSITION_ENTITY_TYPES",
    "CANONICAL_OPPOSITION_OPERATION_IDS",
    "CANONICAL_OPPOSITION_RESOURCE_IDS",
    "CANONICAL_OPPOSITION_RULE_IDS",
    "CANONICAL_OPPOSITION_WORKFLOW_IDS",
]