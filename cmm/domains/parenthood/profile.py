"""Phase 10.27 — Parenthood Domain Profile.

A structured ``DomainProfileDefinition`` for parenthood:
high epistemic discipline, strict separation between proposals, candidate
pathways, parent preferences and adopted parental decisions; normal
developmental variations as non-pathological; isolated child parenting
workspaces; selective and authorized journey-to-child context transfer;
fail-closed protection for sensitive minor and family information; no direct
memory mutation; and no autonomous medical, legal, financial, enrollment,
contracting, payment, or external communication actions.
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.enums import DomainReasoningDepth
from cmm.domains.parenthood.catalog import (
    CANONICAL_PARENTHOOD_RULE_IDS,
    PARENTHOOD_RESOURCE_KINDS,
)
from cmm.domains.profile_contracts import (
    DomainMemoryPolicy,
    DomainPresentationPolicy,
    DomainProductionPolicy,
    DomainProfileDefinition,
    DomainQuestionPolicy,
    DomainTemporalPolicy,
)

PARENTHOOD_PROFILE_ID = "parenthood.profile"
PARENTHOOD_PROFILE_NAME = "ParenthoodProfile"
PARENTHOOD_FUNCTIONAL_SCOPES: tuple[str, ...] = (
    "parenthood.journey",
    "parenthood.child",
)

PARENTHOOD_PROHIBITED_ACTIONS: tuple[str, ...] = (
    "direct_memory_write",
    "silent_memory_persistence",
    "unconfirmed_sensitive_memory_persistence",
    "external_communication",
    "child_enrollment",
    "contracting",
    "payment",
    "consent",
    "legal_commitment",
    "medical_decision",
    "legal_decision",
    "financial_decision",
    "high_impact_parental_decision",
    "export",
    "publication",
    "permission_modification",
    "shell_execution",
)


def build_parenthood_profile() -> DomainProfileDefinition:
    """Build the ``ParenthoodProfile`` deterministically."""
    return DomainProfileDefinition(
        id=PARENTHOOD_PROFILE_ID,
        domain_id="domain:parenthood",
        profile_name=PARENTHOOD_PROFILE_NAME,
        required_rules=CANONICAL_PARENTHOOD_RULE_IDS,
        optional_rules=(),
        prohibited_rules=(),
        allowed_resource_kinds=PARENTHOOD_RESOURCE_KINDS,
        priority_resource_kinds=(
            "resource.life_plan",
            "resource.parenting_note",
            "resource.child_development_resource",
        ),
        prohibited_resource_kinds=(),
        minimum_confidence=0.7,
        reasoning_depth=DomainReasoningDepth.STANDARD,
        allowed_inferences=(
            "journey_dependency",
            "pathway_comparison",
            "requirement_gap",
            "cost_uncertainty",
            "developmental_context",
            "age_appropriate_need",
            "child_wellbeing_signal",
            "parent_child_preference_separation",
            "parenting_option",
            "parental_uncertainty",
            "sibling_specific_context",
            "transfer_candidate",
        ),
        prohibited_inferences=(
            "inferred_parental_decision_as_adopted",
            "child_trait_as_stable_identity_without_evidence",
            "cross_sibling_identity_merge",
            "medical_diagnosis_from_parenting_context",
            "legal_conclusion_without_current_verification",
            "financial_commitment_as_decided",
            "journey_history_auto_transfer",
            "silent_memory_persistence",
        ),
        maximum_questions=5,
        escalation_rules=(
            "parenthood.rule.minor_privacy",
            "parenthood.rule.health_boundary",
            "parenthood.rule.sibling_identity_isolation",
        ),
        prohibited_actions=PARENTHOOD_PROHIBITED_ACTIONS,
        question_policy=DomainQuestionPolicy(
            maximum_questions=5,
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
                "objective",
                "scope_context",
                "evidence_and_observations",
                "options_and_hypotheses",
                "uncertainties_and_boundaries",
                "recommended_next_steps",
            ),
            optional_sections=(
                "developmental_notes",
                "legal_administrative_context",
                "medical_context",
                "financial_context",
                "sibling_isolation_confirmation",
                "transfer_candidates",
                "questions_for_professionals",
            ),
            suppressible_sections=(),
            preferred_section_order=(
                "objective",
                "scope_context",
                "evidence_and_observations",
                "options_and_hypotheses",
                "uncertainties_and_boundaries",
                "recommended_next_steps",
            ),
            protected_terms=(
                "proposed_decision",
                "adopted_decision",
                "normal_developmental_variation",
                "child_need",
                "parent_preference",
                "journey_transfer_candidate",
                "authorized_transfer",
            ),
            term_glosses={
                "proposed_decision": "an exploratory option requiring explicit user adoption",
                "adopted_decision": "an explicit parental choice confirmed by the user",
                "normal_developmental_variation": "typical developmental variation, not a diagnosis",
                "child_need": "individual safety, wellbeing, or developmental requirement of the child",
                "parent_preference": "parental aspiration or personal preference",
                "journey_transfer_candidate": "pre-parenthood context proposed for child workspace",
                "authorized_transfer": "context explicitly reviewed and approved for transfer",
            },
            preferred_components=(
                "objective",
                "scope_context",
                "options_and_hypotheses",
                "uncertainties_and_boundaries",
            ),
            preferred_views=("structured",),
            warning_position="before_content",
            allowed_output_types=("HUMAN_READABLE", "STRUCTURED"),
            preferred_output_types=("STRUCTURED",),
        ),
        memory_policy=DomainMemoryPolicy(
            allow_read=True,
            allow_write=None,
            allow_long_term=True,
            allow_cross_domain=False,
            retention_scope="long_term",
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
    )


__all__ = [
    "PARENTHOOD_FUNCTIONAL_SCOPES",
    "PARENTHOOD_PROFILE_ID",
    "PARENTHOOD_PROFILE_NAME",
    "PARENTHOOD_PROHIBITED_ACTIONS",
    "build_parenthood_profile",
]
