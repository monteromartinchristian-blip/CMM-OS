"""Phase 10.19 — Canonical General Domain Catalog.

Single source of truth for the structural IDs of General Domain.

All other modules (definition, operations, rules, resources, workflows,
bootstrap) must import from this module rather than re-declaring the same
tuples.  This prevents catalog divergence.
"""

from __future__ import annotations

# ── Canonical operation IDs ───────────────────────────────────────────────────

CANONICAL_GENERAL_OPERATION_IDS: tuple[str, ...] = (
    "general.build_timeline",
    "general.compare_items",
    "general.create_summary",
    "general.create_task",
    "general.generate_report",
    "general.prepare_questions",
    "general.search_knowledge",
    "general.update_goal",
)

# ── Canonical rule IDs ────────────────────────────────────────────────────────

CANONICAL_GENERAL_RULE_IDS: tuple[str, ...] = (
    "general.ambiguity",
    "general.duplication",
    "general.goal_clarification",
    "general.permission",
    "general.source_reliability",
    "general.temporal_validity",
)

# ── Canonical resource IDs ────────────────────────────────────────────────────

CANONICAL_GENERAL_RESOURCE_IDS: tuple[str, ...] = (
    "general.calendar_event",
    "general.conversation",
    "general.document",
    "general.external_source",
    "general.generic_goal",
    "general.generic_task",
    "general.memory_entry",
    "general.note",
    "general.user_message",
)

# ── Canonical workflow IDs ────────────────────────────────────────────────────

CANONICAL_GENERAL_WORKFLOW_IDS: tuple[str, ...] = (
    "general.decision_support",
    "general.goal_clarification",
    "general.information_review",
    "general.periodic_review",
)

# ── Historical placeholders (Phase 10.13) ────────────────────────────────────
# These IDs exist in INITIAL_DOMAIN_OPERATION_IDS from Phase 10.13.  They have
# different semantics from the Phase 10.19 operations and are NOT part of the
# canonical General Domain API.  They are preserved for backward compatibility
# with the Phase 10.13 catalog.

HISTORICAL_GENERAL_OPERATION_IDS: tuple[str, ...] = (
    "general.read_resources",
    "general.prepare_structured_summary",
    "general.create_plan",
    "general.propose_memory_update",
)

__all__ = [
    "CANONICAL_GENERAL_OPERATION_IDS",
    "CANONICAL_GENERAL_RESOURCE_IDS",
    "CANONICAL_GENERAL_RULE_IDS",
    "CANONICAL_GENERAL_WORKFLOW_IDS",
    "HISTORICAL_GENERAL_OPERATION_IDS",
]