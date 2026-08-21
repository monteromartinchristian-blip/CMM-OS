"""Phase 10.21 — Relationships Domain Profile.

A deliberately conservative ``DomainProfileDefinition``: provenance-heavy,
explicitly uncertain, with strict fact/interpretation separation.  The profile
has low tolerance for unsupported third-party inference, permits sensitive
inference only as a visibly labelled hypothesis where policy permits, never
diagnoses a third party, never adopts a relational decision autonomously,
preserves ambivalence, controls memory, and never communicates automatically.
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.enums import DomainReasoningDepth
from cmm.domains.profile_contracts import (
    DomainMemoryPolicy,
    DomainPresentationPolicy,
    DomainProductionPolicy,
    DomainProfileDefinition,
    DomainQuestionPolicy,
    DomainTemporalPolicy,
)
from cmm.domains.relationships.catalog import CANONICAL_RELATIONSHIPS_RULE_IDS
from cmm.domains.relationships.resources import RELATIONSHIPS_RESOURCE_KINDS

RELATIONSHIPS_PROFILE_ID = "relationships.profile"
RELATIONSHIPS_PROFILE_NAME = "RelationshipsProfile"

# Encodes the forbidden actions of the Relationships safety model (spec §1, §8).
RELATIONSHIPS_PROHIBITED_ACTIONS: tuple[str, ...] = (
    "third_party_diagnosis",
    "third_party_psychiatric_diagnosis",
    "personality_disorder_attribution",
    "intent_attribution_as_fact",
    "mind_reading_as_fact",
    "relational_decision_adoption",
    "relational_decision_execution",
    "boundary_modification",
    "boundary_enforcement",
    "boundary_communication",
    "automatic_external_communication",
    "contact_initiation",
    "message_sending",
    "relationship_end",
    "relationship_resume",
    "relationship_distance",
    "reconciliation_initiation",
    "sensitive_inference_persist",
    "sensitive_cross_domain_transfer",
    "unconfirmed_sensitive_memory_persistence",
    "ambivalence_resolution",
    "export",
    "shell_execution",
)


def build_relationships_profile() -> DomainProfileDefinition:
    """Build the ``RelationshipsProfile`` deterministically."""
    return DomainProfileDefinition(
        id=RELATIONSHIPS_PROFILE_ID,
        domain_id="domain:relationships",
        profile_name=RELATIONSHIPS_PROFILE_NAME,
        required_rules=CANONICAL_RELATIONSHIPS_RULE_IDS,
        optional_rules=(),
        prohibited_rules=(),
        allowed_resource_kinds=RELATIONSHIPS_RESOURCE_KINDS,
        priority_resource_kinds=(
            "user_message",
            "relationship_event",
            "conversation",
        ),
        prohibited_resource_kinds=(),
        minimum_confidence=0.75,
        reasoning_depth=DomainReasoningDepth.STANDARD,
        allowed_inferences=(
            "observed_fact",
            "direct_statement",
            "user_interpretation",
            "system_hypothesis",
            "possible_function",
            "possible_origin",
            "unknown",
            "pattern_hypothesis",
            "contradiction",
            "missing_information",
            "open_question",
            "possible_action",
        ),
        prohibited_inferences=(
            "third_party_diagnosis",
            "intent_as_fact",
            "psychological_cause",
            "sensitive_inference_persist",
        ),
        maximum_questions=10,
        escalation_rules=(
            "relationships.self_other_perspective",
            "relationships.do_not_infer_intent",
        ),
        prohibited_actions=RELATIONSHIPS_PROHIBITED_ACTIONS,
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
                "facts",
                "statements",
                "emotions",
                "needs",
                "interpretations",
                "hypotheses",
                "patterns",
                "contradictions",
                "open_questions",
                "possible_actions",
            ),
            optional_sections=("timeline", "comparison"),
            suppressible_sections=(),
            preferred_section_order=(
                "facts",
                "statements",
                "emotions",
                "needs",
                "interpretations",
                "hypotheses",
                "patterns",
                "contradictions",
                "open_questions",
                "possible_actions",
            ),
            protected_terms=(
                "observed_fact",
                "direct_statement",
                "interpretation",
                "hypothesis",
                "possible_function",
                "possible_origin",
                "unknown",
                "uncertainty",
                "provenance",
                "contradiction",
                "ambivalence",
                "pattern_hypothesis",
                "possible_action",
                "open_question",
            ),
            term_glosses={
                "observed_fact": "directly evidenced behavior or event",
                "direct_statement": "explicitly said or written by a person",
                "interpretation": "user's interpretation, not a fact",
                "hypothesis": "unverified system proposition",
                "possible_function": "hypothesis about a behavior's possible function",
                "possible_origin": "hypothesis about why a pattern may exist",
                "unknown": "not established by available evidence",
                "uncertainty": "unknown confidence",
                "provenance": "source origin",
                "contradiction": "conflicting information",
                "ambivalence": "simultaneous contradictory feelings",
                "pattern_hypothesis": "repeated structure, not a cause",
                "possible_action": "a candidate, not an adopted decision",
                "open_question": "unresolved question or missing information",
            },
            preferred_components=(
                "facts",
                "statements",
                "interpretations",
                "open_questions",
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
        metadata={"phase": "10.21"},
    )


__all__ = [
    "RELATIONSHIPS_PROFILE_ID",
    "RELATIONSHIPS_PROFILE_NAME",
    "RELATIONSHIPS_PROHIBITED_ACTIONS",
    "build_relationships_profile",
]
