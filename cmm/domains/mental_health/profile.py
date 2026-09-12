"""Phase 10.52 — Mental Health Domain Profile.

A deliberately conservative ``DomainProfileDefinition`` for emotional and
therapeutic specialization: non-pathologizing ordinary mode, epistemic
separation, high uncertainty preservation, speaker/source provenance,
proposal-first sensitive memory, purpose-minimized cross-domain context,
Health clinical-authority preservation, and current permission/privacy
revalidation.  The profile never promotes an interpretation to a fact and
never becomes a Phase 11 Communication Profile or renderer.
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.enums import DomainReasoningDepth
from cmm.domains.mental_health.catalog import (
    MENTAL_HEALTH_PROFILE_NAME,
    MENTAL_HEALTH_RULE_IDS,
)
from cmm.domains.mental_health.resources import MENTAL_HEALTH_RESOURCE_KINDS
from cmm.domains.profile_contracts import (
    DomainMemoryPolicy,
    DomainPresentationPolicy,
    DomainProductionPolicy,
    DomainProfileDefinition,
    DomainQuestionPolicy,
    DomainTemporalPolicy,
)

MENTAL_HEALTH_PROFILE_ID = "mental-health.profile"

# Encodes the forbidden actions of the Mental Health safety model (frozen
# design §29.3, §39, §40).  Mental Health specializes; it never executes.
MENTAL_HEALTH_PROHIBITED_ACTIONS: tuple[str, ...] = (
    "diagnosis_presentation",
    "psychological_diagnosis",
    "psychiatric_label_inference",
    "disorder_attribution",
    "severity_score_invention",
    "medication_start",
    "medication_stop",
    "medication_dose_change",
    "medication_substitution",
    "treatment_plan_change",
    "clinician_override",
    "clinical_authority_claim",
    "fabricated_therapist_statement",
    "model_interpretation_as_clinician_statement",
    "semantic_memory_write",
    "memory_persistence",
    "unconfirmed_memory_persistence",
    "sensitive_inference_persist",
    "sensitive_cross_domain_transfer",
    "external_communication",
    "message_send",
    "crisis_dispatch",
    "hidden_emergency_contact",
    "automatic_external_action",
    "export",
    "shell_execution",
)


def build_mental_health_profile() -> DomainProfileDefinition:
    """Build the ``MentalHealthProfile`` deterministically."""
    return DomainProfileDefinition(
        id=MENTAL_HEALTH_PROFILE_ID,
        domain_id="domain:mental-health",
        profile_name=MENTAL_HEALTH_PROFILE_NAME,
        required_rules=MENTAL_HEALTH_RULE_IDS,
        optional_rules=(),
        prohibited_rules=(),
        allowed_resource_kinds=MENTAL_HEALTH_RESOURCE_KINDS,
        priority_resource_kinds=(
            "conversation",
            "therapy_session_note",
            "therapy_transcript",
            "user_reflection",
        ),
        prohibited_resource_kinds=(),
        minimum_confidence=0.6,
        reasoning_depth=DomainReasoningDepth.STANDARD,
        allowed_inferences=(
            "observation",
            "user_stated_experience",
            "emotion_candidate",
            "fear_as_fear",
            "intuition_as_intuition",
            "preference_as_preference",
            "interpretation",
            "hypothesis",
            "scenario_as_scenario",
            "uncertainty",
            "open_question",
            "material_question",
            "missing_information",
            "emotional_pattern_hypothesis",
            "loop_hypothesis",
            "session_theme_candidate",
            "session_question_candidate",
            "prepared_content",
            "proposal",
            "proportionate_risk",
            "specialized_risk_preservation",
            "no_forced_action",
            "no_forced_closure",
        ),
        prohibited_inferences=(
            "definitive_diagnosis",
            "psychological_diagnosis",
            "psychiatric_label",
            "disorder_attribution",
            "causal_claim",
            "sensitive_inference_persist",
            "fabricated_therapist_statement",
            "interpretation_as_fact",
            "fear_as_prediction",
            "repetition_as_disorder",
        ),
        maximum_questions=10,
        escalation_rules=(
            "mental_health.proportionate_safety_escalation",
            "mental_health.health_authority",
        ),
        prohibited_actions=MENTAL_HEALTH_PROHIBITED_ACTIONS,
        question_policy=DomainQuestionPolicy(
            maximum_questions=10,
            allow_follow_up=True,
            require_deduplication=True,
            allow_clarification=True,
            stop_on_blocking_gap=True,
        ),
        # Non-clinical, human, uncertainty-visible ordinary presentation.
        # Mental Health may order/label sections but never alter the epistemic
        # result, never hide uncertainty, and never remove approval gates.
        presentation_policy=DomainPresentationPolicy(
            detail_level="standard",
            include_uncertainty=True,
            include_provenance=True,
            include_alternatives=True,
            allow_speculation=False,
            require_disclaimers=True,
            required_sections=(
                "understanding",
                "facts_and_observations",
                "interpretations",
                "uncertainty",
                "open_questions",
            ),
            optional_sections=(
                "therapy_structure",
                "longitudinal_context",
                "decision_trade_offs",
                "sensitive_action_confirmations",
            ),
            suppressible_sections=(),
            preferred_section_order=(
                "understanding",
                "facts_and_observations",
                "interpretations",
                "uncertainty",
                "open_questions",
            ),
            protected_terms=(
                "fact",
                "observation",
                "interpretation",
                "hypothesis",
                "fear",
                "intuition",
                "uncertainty",
                "provenance",
                "proposal",
                "therapist_statement",
                "user_statement",
                "model_interpretation",
            ),
            term_glosses={
                "fact": "documented or directly verifiable",
                "observation": "noticed without asserting more",
                "interpretation": "a possible reading, not a fact",
                "hypothesis": "unverified system proposition",
                "fear": "an emotion, not a prediction",
                "intuition": "a felt sense, not evidence",
                "uncertainty": "unknown confidence",
                "provenance": "source origin",
                "proposal": "requires explicit approval before persistence",
                "therapist_statement": "attributed to the therapist",
                "user_statement": "attributed to the user",
                "model_interpretation": "system reading, not a source statement",
            },
            preferred_components=(
                "understanding",
                "facts_and_observations",
                "uncertainty",
            ),
            preferred_views=("conversational", "structured"),
            warning_position="after_content",
            allowed_output_types=("HUMAN_READABLE", "STRUCTURED"),
            preferred_output_types=("HUMAN_READABLE",),
        ),
        # Proposal-first sensitive memory: reading never authorizes writing.
        memory_policy=DomainMemoryPolicy(
            allow_read=True,
            allow_write=False,
            allow_long_term=False,
            allow_cross_domain=False,
            retention_scope="session",
            sensitivity_limit=SensitivityLevel.SENSITIVE,
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
        metadata={"phase": "10.52"},
    )
