"""Phase 10.22 — Canonical University Domain Catalog.

Single source of truth for the structural IDs of University Domain.

All other modules (definition, operations, rules, resources, workflows,
bootstrap) must import from this module rather than re-declaring the same
tuples.  This prevents catalog divergence.
"""

from __future__ import annotations

# ── Canonical university entity semantics ──────────────────────────────────────
# These are semantic types, not new persistent classes.  They are surfaced
# through canonical Entity / KnowledgeItem bindings and the ``entity_types``
# field of University resource definitions.

CANONICAL_UNIVERSITY_ENTITY_TYPES: tuple[str, ...] = (
    "academic_requirement",
    "academic_year",
    "adaptation",
    "assignment",
    "credit",
    "deadline",
    "degree",
    "exam_attempt",
    "examination",
    "grade",
    "professor",
    "semester",
    "subject",
    "university",
)

# ── Canonical resource IDs ─────────────────────────────────────────────────────

CANONICAL_UNIVERSITY_RESOURCE_IDS: tuple[str, ...] = (
    "university.academic_record",
    "university.assignment",
    "university.email",
    "university.examination_schedule",
    "university.grade",
    "university.memory_entry",
    "university.note",
    "university.regulation",
    "university.study_session",
    "university.subject_guide",
    "university.university_calendar",
    "university.user_message",
)

# ── Canonical rule IDs ─────────────────────────────────────────────────────────

CANONICAL_UNIVERSITY_RULE_IDS: tuple[str, ...] = (
    "university.academic_contradiction",
    "university.academic_deadline",
    "university.academic_decision_preservation",
    "university.academic_dependency",
    "university.academic_integrity",
    "university.academic_source_authority",
    "university.academic_workload",
    "university.ects_consistency",
    "university.exam_attempt",
    "university.observed_performance_capacity",
)

# ── Canonical operation IDs ────────────────────────────────────────────────────

CANONICAL_UNIVERSITY_OPERATION_IDS: tuple[str, ...] = (
    "university.analyse_performance",
    "university.compare_semesters",
    "university.create_study_plan",
    "university.generate_academic_summary",
    "university.plan_semester",
    "university.prepare_assignment",
    "university.prepare_exam",
    "university.review_academic_record",
    "university.review_degree_completion",
    "university.track_deadlines",
    "university.update_subject_status",
)

# ── Canonical workflow IDs ─────────────────────────────────────────────────────

CANONICAL_UNIVERSITY_WORKFLOW_IDS: tuple[str, ...] = (
    "university.academic_review",
    "university.assignment_preparation",
    "university.degree_completion_review",
    "university.exam_preparation",
    "university.reassessment_planning",
    "university.semester_planning",
    "university.tfg_planning",
)

__all__ = [
    "CANONICAL_UNIVERSITY_ENTITY_TYPES",
    "CANONICAL_UNIVERSITY_OPERATION_IDS",
    "CANONICAL_UNIVERSITY_RESOURCE_IDS",
    "CANONICAL_UNIVERSITY_RULE_IDS",
    "CANONICAL_UNIVERSITY_WORKFLOW_IDS",
]
