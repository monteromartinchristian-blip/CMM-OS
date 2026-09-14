"""Phase 10.53 — Neurodivergence Domain Profile.

An **exploration-friendly** ``DomainProfileDefinition`` for neurodevelopmental
specialization.  The profile deliberately permits working hypotheses, pattern
association, differential and overlap reasoning, functional-impact
candidates and longitudinal comparison, while prohibiting diagnostic
promotion: a model inference may never become a confirmed clinical diagnosis,
a screening score may never become a diagnosis, self-report may never become a
diagnosis, and an isolated trait may never become a stable diagnostic identity.

The profile keeps sensitive persistence proposal-first, keeps Health clinical
authority and sibling source-domain authority intact, and never becomes a
Phase 11 Communication Profile or renderer.

Semantics (frozen design §6, §7, §10):

    exploratory inference is allowed
    diagnostic promotion is not
    understanding > premature closure
    evidence organization > categorical labeling
    useful hypothesis generation > defensive refusal
    certainty preservation > diagnostic promotion
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.enums import DomainReasoningDepth
from cmm.domains.neurodivergence.catalog import (
    NEURODIVERGENCE_PROFILE_NAME,
    NEURODIVERGENCE_RULE_IDS,
)
from cmm.domains.neurodivergence.resources import NEURODIVERGENCE_RESOURCE_KINDS
from cmm.domains.profile_contracts import (
    DomainMemoryPolicy,
    DomainPresentationPolicy,
    DomainProductionPolicy,
    DomainProfileDefinition,
    DomainQuestionPolicy,
    DomainTemporalPolicy,
)

NEURODIVERGENCE_PROFILE_ID = "neurodivergence.profile"

# Encodes the forbidden actions of the Neurodivergence safety model (frozen
# design §7, §28, §39).  Neurodivergence specializes; it never executes, never
# promotes a hypothesis to a diagnosis and never touches clinical authority.
NEURODIVERGENCE_PROHIBITED_ACTIONS: tuple[str, ...] = (
    "definitive_diagnosis",
    "diagnosis_confirmation",
    "diagnosis_removal",
    "diagnostic_label_assertion",
    "psychological_diagnosis",
    "psychiatric_label_inference",
    "screening_as_diagnosis",
    "self_report_as_diagnosis",
    "isolated_trait_as_diagnostic_identity",
    "model_inference_as_clinical_fact",
    "severity_score_invention",
    "medication_start",
    "medication_stop",
    "medication_dose_change",
    "medication_substitution",
    "treatment_plan_change",
    "medical_contraindication_override",
    "clinician_override",
    "clinical_authority_claim",
    "source_authority_rewrite",
    "semantic_memory_write",
    "memory_persistence",
    "unconfirmed_memory_persistence",
    "sensitive_inference_persist",
    "sensitive_cross_domain_transfer",
    "external_communication",
    "message_send",
    "automatic_external_action",
    "export",
    "shell_execution",
)

# Exploratory vocabulary surfaced for reasoning/organization.  A working
# hypothesis is a first-class, expected output — never a refusal trigger.
NEURODIVERGENCE_ALLOWED_INFERENCES: tuple[str, ...] = (
    "observation",
    "user_stated_experience",
    "self_report",
    "third_party_report",
    "working_hypothesis",
    "pattern_association",
    "differential_hypothesis",
    "overlap_hypothesis",
    "functional_impact_candidate",
    "developmental_pattern_candidate",
    "screening_evidence",
    "psychometric_evidence",
    "uncertainty",
    "competing_explanation",
    "alternative_explanation",
    "negative_evidence",
    "assessment_question",
    "evidence_needed",
    "structured_summary",
    "timeline_candidate",
    "proposal",
)

# The promotion boundary.  None of these may be produced by Neurodivergence
# reasoning alone (spec §6.2, §28.1).
NEURODIVERGENCE_PROHIBITED_INFERENCES: tuple[str, ...] = (
    "definitive_diagnosis",
    "confirmed_clinical_status",
    "diagnosis_removal",
    "model_inference_as_clinical_fact",
    "screening_as_diagnosis",
    "self_report_as_diagnosis",
    "isolated_trait_as_diagnostic_identity",
    "conversation_pattern_as_diagnosis",
    "academic_difficulty_as_diagnosis",
    "sensory_difficulty_as_diagnosis",
    "social_difficulty_as_diagnosis",
    "executive_difficulty_as_diagnosis",
    "medication_change",
    "treatment_change",
    "source_authority_rewrite",
    "global_neurodivergence_attribution",
)


def build_neurodivergence_profile() -> DomainProfileDefinition:
    """Build the ``NeurodivergenceProfile`` deterministically."""
    return DomainProfileDefinition(
        id=NEURODIVERGENCE_PROFILE_ID,
        domain_id="domain:neurodivergence",
        profile_name=NEURODIVERGENCE_PROFILE_NAME,
        required_rules=NEURODIVERGENCE_RULE_IDS,
        optional_rules=(),
        prohibited_rules=(),
        allowed_resource_kinds=NEURODIVERGENCE_RESOURCE_KINDS,
        priority_resource_kinds=(
            "developmental_history",
            "assessment_records",
            "psychometric_results",
            "longitudinal_evidence",
        ),
        prohibited_resource_kinds=(),
        # Exploratory organization must not be gated on high confidence: a
        # working hypothesis is useful precisely while evidence is incomplete.
        minimum_confidence=0.5,
        reasoning_depth=DomainReasoningDepth.STANDARD,
        allowed_inferences=NEURODIVERGENCE_ALLOWED_INFERENCES,
        prohibited_inferences=NEURODIVERGENCE_PROHIBITED_INFERENCES,
        maximum_questions=10,
        escalation_rules=(
            "neurodivergence.clinical_status_authority",
            "neurodivergence.source_authority",
        ),
        prohibited_actions=NEURODIVERGENCE_PROHIBITED_ACTIONS,
        question_policy=DomainQuestionPolicy(
            maximum_questions=10,
            allow_follow_up=True,
            require_deduplication=True,
            allow_clarification=True,
            stop_on_blocking_gap=True,
        ),
        # Calm, exploratory, epistemically explicit presentation.  Certainty,
        # provenance and alternatives stay visible; a clinical tone is not
        # required and a disclaimer block is not mandatory.
        presentation_policy=DomainPresentationPolicy(
            detail_level="standard",
            include_uncertainty=True,
            include_provenance=True,
            include_alternatives=True,
            allow_speculation=True,
            require_disclaimers=False,
            required_sections=(),
            optional_sections=(
                "what_may_fit",
                "why_it_may_fit",
                "what_remains_unclear",
                "what_may_not_fit",
                "alternative_or_overlapping_explanations",
                "evidence_that_would_clarify",
                "current_certainty",
                "functional_observations",
                "developmental_timeline",
                "assessment_preparation",
            ),
            suppressible_sections=(),
            # Exploratory organization is available, not mandatory: the order
            # below is a preferred shape, never a mechanically enforced
            # for/against template.
            preferred_section_order=(
                "what_may_fit",
                "why_it_may_fit",
                "what_remains_unclear",
                "what_may_not_fit",
                "alternative_or_overlapping_explanations",
                "evidence_that_would_clarify",
                "current_certainty",
            ),
            protected_terms=(
                "confirmed",
                "in_evaluation",
                "hypothesis",
                "not_confirmed",
                "ruled_out",
                "insufficiently_supported",
                "screening",
                "self_report",
                "third_party_report",
                "observation",
                "model_interpretation",
                "provenance",
                "working_hypothesis",
                "functional_observation",
            ),
            term_glosses={
                "confirmed": "authoritative documented status",
                "in_evaluation": "an assessment process is documented as underway",
                "hypothesis": "unverified possibility, not a clinical fact",
                "not_confirmed": "no confirming evidence yet",
                "ruled_out": "assessed and excluded by the owning authority",
                "insufficiently_supported": "evidence exists but does not suffice",
                "screening": "a screening result, not a diagnosis",
                "self_report": "attributed to the user",
                "third_party_report": "attributed to another person",
                "observation": "noticed without asserting more",
                "model_interpretation": "system reading, not a source statement",
                "provenance": "source origin",
                "working_hypothesis": "useful while exploring; never promoted",
                "functional_observation": "everyday-function context, not a label",
            },
            preferred_components=(
                "what_may_fit",
                "why_it_may_fit",
                "current_certainty",
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
        metadata={
            "phase": "10.53",
            "reasoning_orientation": "exploratory_and_hypothesis_friendly",
            "differential_reasoning": "balanced_not_adversarial",
            "disclaimer_spam": "prohibited",
        },
    )


__all__ = [
    "NEURODIVERGENCE_ALLOWED_INFERENCES",
    "NEURODIVERGENCE_PROFILE_ID",
    "NEURODIVERGENCE_PROHIBITED_ACTIONS",
    "NEURODIVERGENCE_PROHIBITED_INFERENCES",
    "build_neurodivergence_profile",
]
