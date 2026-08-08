"""Phase 10.20 — Health Domain Profile.

A deliberately conservative ``DomainProfileDefinition``: provenance and
temporal validity are weighted strongly, documentary evidence precedes
inference, uncertainty and contradictions are explicit, and there is low
tolerance for unsupported clinical conclusions.  The profile never promotes
a model hypothesis to a clinical fact.
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.enums import DomainReasoningDepth
from cmm.domains.health.catalog import CANONICAL_HEALTH_RULE_IDS
from cmm.domains.health.resources import HEALTH_RESOURCE_KINDS
from cmm.domains.profile_contracts import (
    DomainMemoryPolicy,
    DomainPresentationPolicy,
    DomainProductionPolicy,
    DomainProfileDefinition,
    DomainQuestionPolicy,
    DomainTemporalPolicy,
)

HEALTH_PROFILE_ID = "health.profile"
HEALTH_PROFILE_NAME = "HealthProfile"

# Encodes the forbidden actions of the Health safety model (spec §5, §13).
HEALTH_PROHIBITED_ACTIONS: tuple[str, ...] = (
    "definitive_diagnosis",
    "diagnostic_certainty_claim",
    "medication_start",
    "medication_stop",
    "medication_dose_change",
    "medication_substitution",
    "clinician_override",
    "automatic_treatment_decision",
    "automatic_external_communication",
    "automatic_medical_action",
    "sensitive_inference_persist",
    "sensitive_cross_domain_transfer",
    "unconfirmed_sensitive_memory_persistence",
    "export",
    "shell_execution",
)


def build_health_profile() -> DomainProfileDefinition:
    """Build the ``HealthProfile`` deterministically."""
    return DomainProfileDefinition(
        id=HEALTH_PROFILE_ID,
        domain_id="domain:health",
        profile_name=HEALTH_PROFILE_NAME,
        required_rules=CANONICAL_HEALTH_RULE_IDS,
        optional_rules=(),
        prohibited_rules=(),
        allowed_resource_kinds=HEALTH_RESOURCE_KINDS,
        priority_resource_kinds=(
            "medical_report",
            "laboratory_result",
            "prescription",
            "symptom_log",
        ),
        prohibited_resource_kinds=(),
        minimum_confidence=0.75,
        reasoning_depth=DomainReasoningDepth.STANDARD,
        allowed_inferences=(
            "documented_information",
            "clinical_observation",
            "reported_symptom",
            "documented_diagnosis",
            "provisional_diagnosis",
            "system_hypothesis",
            "user_possibility",
            "contradiction",
            "missing_information",
            "red_flag",
            "escalation",
        ),
        prohibited_inferences=(
            "definitive_diagnosis",
            "causal_claim",
            "sensitive_inference",
            "sensitive_inference_persist",
        ),
        maximum_questions=10,
        escalation_rules=(
            "health.professional_escalation",
            "health.medical_red_flag",
        ),
        prohibited_actions=HEALTH_PROHIBITED_ACTIONS,
        question_policy=DomainQuestionPolicy(
            maximum_questions=10,
            allow_follow_up=True,
            require_deduplication=True,
            allow_clarification=True,
            stop_on_blocking_gap=True,
        ),
        presentation_policy=DomainPresentationPolicy(
            detail_level="detailed",
            include_uncertainty=True,
            include_provenance=True,
            include_alternatives=True,
            allow_speculation=False,
            require_disclaimers=True,
            required_sections=(
                "documented_information",
                "reported_symptoms",
                "temporal_changes",
                "hypotheses_and_possibilities",
                "contradictions",
                "missing_information",
                "red_flags",
                "questions_for_professional",
                "authorized_next_steps",
            ),
            optional_sections=("timeline", "comparison"),
            suppressible_sections=(),
            preferred_section_order=(
                "documented_information",
                "reported_symptoms",
                "temporal_changes",
                "hypotheses_and_possibilities",
                "contradictions",
                "missing_information",
                "red_flags",
                "questions_for_professional",
                "authorized_next_steps",
            ),
            protected_terms=(
                "hypothesis",
                "possibility",
                "temporal_association",
                "uncertainty",
                "provenance",
                "contradiction",
                "missing_information",
                "red_flag",
                "escalation",
                "documented",
                "reported",
                "provisional",
                "definitive",
            ),
            term_glosses={
                "hypothesis": "unverified system proposition",
                "possibility": "proposition proposed by the user",
                "temporal_association": "temporal relationship, not causation",
                "uncertainty": "unknown confidence",
                "provenance": "source origin",
                "contradiction": "conflicting information",
                "missing_information": "information absent",
                "red_flag": "signal requiring professional review",
                "escalation": "referral to professional review",
                "documented": "recorded in a source",
                "reported": "stated by the user",
                "provisional": "guidance, not confirmed",
                "definitive": "confirmed clinical truth",
            },
            preferred_components=(
                "documented_information",
                "reported_symptoms",
                "contradictions",
                "red_flags",
            ),
            preferred_views=("structured",),
            warning_position="before_content",
            allowed_output_types=("HUMAN_READABLE", "STRUCTURED"),
            preferred_output_types=("STRUCTURED",),
        ),
        memory_policy=DomainMemoryPolicy(
            allow_read=True,
            allow_write=False,
            allow_long_term=False,
            allow_cross_domain=False,
            retention_scope="session",
            sensitivity_limit=SensitivityLevel.HIGHLY_SENSITIVE,
        ),
        temporal_policy=DomainTemporalPolicy(
            require_current_information=True,
            allow_historical_information=True,
            require_temporal_provenance=True,
            allow_future_projection=False,
        ),
        production_policy=DomainProductionPolicy(
            allow_draft=True,
            allow_final=False,
            allow_external_action=False,
            require_review=True,
            require_validation=True,
            maximum_output_items=64,
        ),
        permissions=(
            "resource.read",
            "memory.read",
            "operation.execute",
        ),
        metadata={"phase": "10.20"},
    )


__all__ = [
    "HEALTH_PROFILE_ID",
    "HEALTH_PROFILE_NAME",
    "HEALTH_PROHIBITED_ACTIONS",
    "build_health_profile",
]