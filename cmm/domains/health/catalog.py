"""Phase 10.20 — Canonical Health Domain Catalog.

Single source of truth for the structural IDs of Health Domain.

All other modules (definition, operations, rules, resources, workflows,
bootstrap) must import from this module rather than re-declaring the same
tuples.  This prevents catalog divergence.
"""

from __future__ import annotations

# ── Canonical health entity semantics ─────────────────────────────────────────
# These are semantic types, not new persistent classes.  They are surfaced
# through canonical Entity / KnowledgeItem bindings and the ``entity_types``
# field of Health resource definitions.

CANONICAL_HEALTH_ENTITY_TYPES: tuple[str, ...] = (
    "adverse_effect",
    "allergy",
    "appointment",
    "diagnosis",
    "healthcare_provider",
    "medical_condition",
    "medical_report",
    "medical_test",
    "medication",
    "procedure",
    "specialist",
    "surgery",
    "symptom",
    "treatment",
    "vital_sign",
)

# ── Canonical operation IDs ───────────────────────────────────────────────────

CANONICAL_HEALTH_OPERATION_IDS: tuple[str, ...] = (
    "health.build_medical_timeline",
    "health.build_symptom_timeline",
    "health.compare_reports",
    "health.compare_test_results",
    "health.detect_open_medical_questions",
    "health.export_medical_context",
    "health.generate_medical_summary",
    "health.prepare_medical_appointment",
    "health.prepare_questions",
    "health.register_symptom_update",
    "health.review_follow_up",
    "health.review_medication_changes",
)

# ── Canonical rule IDs ────────────────────────────────────────────────────────

CANONICAL_HEALTH_RULE_IDS: tuple[str, ...] = (
    "health.clinical_source_priority",
    "health.medical_red_flag",
    "health.medical_temporal_validity",
    "health.medication_consistency",
    "health.medication_temporal_relationship",
    "health.no_definitive_diagnosis",
    "health.professional_escalation",
    "health.symptom_diagnosis_hypothesis",
)

# ── Canonical resource IDs ────────────────────────────────────────────────────

CANONICAL_HEALTH_RESOURCE_IDS: tuple[str, ...] = (
    "health.appointment",
    "health.discharge_report",
    "health.external_medical_source",
    "health.health_memory",
    "health.imaging_report",
    "health.laboratory_result",
    "health.medical_report",
    "health.medication_list",
    "health.prescription",
    "health.symptom_log",
    "health.treatment_plan",
    "health.user_message",
)

# ── Canonical workflow IDs ────────────────────────────────────────────────────

CANONICAL_HEALTH_WORKFLOW_IDS: tuple[str, ...] = (
    "health.chronic_condition_timeline",
    "health.diagnostic_process_review",
    "health.medical_follow_up",
    "health.medical_report_comparison",
    "health.medication_change_review",
    "health.postoperative_follow_up",
    "health.specialist_appointment_preparation",
    "health.symptom_review",
)

__all__ = [
    "CANONICAL_HEALTH_ENTITY_TYPES",
    "CANONICAL_HEALTH_OPERATION_IDS",
    "CANONICAL_HEALTH_RESOURCE_IDS",
    "CANONICAL_HEALTH_RULE_IDS",
    "CANONICAL_HEALTH_WORKFLOW_IDS",
]
