"""Phase 10.23 — Opposition Domain Profile.

A deliberately conservative ``DomainProfileDefinition`` for opposition
reasoning: provenance-heavy, attribute-specific and scope-aware source
authority, explicit temporal validity for changing official facts, explicit
uncertainty, Official Opposition State vs CMM Opposition Strategy State vs
Personal Memory separation, versioned strategy, and decision support that
never adopts an opposition strategy.  The profile never registers, submits,
pays, signs, modifies official public-body records, abandons or switches the
target, or infers capacity/guranteed exam success from mock performance.

This binds/configure the shared ``OppositionProfile`` semantics (Phase 8)
through the shared profile contracts; it does not create a cognitive engine.
"""

from __future__ import annotations

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.enums import DomainReasoningDepth
from cmm.domains.oppositions.catalog import CANONICAL_OPPOSITION_RULE_IDS
from cmm.domains.oppositions.resources import OPPOSITIONS_RESOURCE_KINDS
from cmm.domains.profile_contracts import (
    DomainMemoryPolicy,
    DomainPresentationPolicy,
    DomainProductionPolicy,
    DomainProfileDefinition,
    DomainQuestionPolicy,
    DomainTemporalPolicy,
)

OPPOSITIONS_PROFILE_ID = "oppositions.profile"
OPPOSITIONS_PROFILE_NAME = "OppositionProfile"

# Forbidden autonomous actions of the Opposition safety model (spec §9, §22).
OPPOSITIONS_PROHIBITED_ACTIONS: tuple[str, ...] = (
    "opposition_registration",
    "application_submission",
    "application_sign",
    "fee_payment",
    "service_purchase",
    "formal_document_upload",
    "user_impersonation",
    "application_withdrawal",
    "target_abandonment",
    "primary_route_switch",
    "final_user_decision",
    "official_records_modification",
    "official_records_write",
    "calendar_event_creation",
    "task_creation",
    "schedule_modification",
    "memory_persistence",
    "strategy_adoption",
    "capacity_inference_from_mock",
    "exam_success_inference",
    "intelligence_inference",
    "sensitive_inference_persist",
    "clinical_detail_transfer",
    "university_state_merge",
    "unconfirmed_sensitive_memory_persistence",
    "export",
    "shell_execution",
)


def build_oppositions_profile() -> DomainProfileDefinition:
    """Build the ``OppositionProfile`` deterministically."""
    return DomainProfileDefinition(
        id=OPPOSITIONS_PROFILE_ID,
        domain_id="domain:oppositions",
        profile_name=OPPOSITIONS_PROFILE_NAME,
        required_rules=CANONICAL_OPPOSITION_RULE_IDS,
        optional_rules=(),
        prohibited_rules=(),
        allowed_resource_kinds=OPPOSITIONS_RESOURCE_KINDS,
        priority_resource_kinds=(
            "official_call",
            "regulation",
            "syllabus",
            "external_official_source",
        ),
        prohibited_resource_kinds=(),
        minimum_confidence=0.75,
        reasoning_depth=DomainReasoningDepth.STANDARD,
        allowed_inferences=(
            "observed_opposition_fact",
            "official_source_fact",
            "user_stated_fact",
            "system_hypothesis",
            "source_authority_by_attribute",
            "contradiction",
            "missing_information",
            "open_question",
            "possible_action",
            "planning_proposal",
            "preparation_proposal",
            "temporal_state",
            "call_monitoring_need",
            "trade_off",
            "risk",
            "strategy_proposal",
        ),
        prohibited_inferences=(
            "capacity_inference",
            "intelligence_inference",
            "exam_success_guarantee",
            "target_abandonment",
            "strategy_adoption",
            "clinical_inference",
            "university_state_inference",
            "sensitive_inference",
            "sensitive_inference_persist",
        ),
        maximum_questions=10,
        escalation_rules=(
            "oppositions.official_call_priority",
            "oppositions.temporal_validity",
            "oppositions.study_feasibility",
            "oppositions.alternative_route",
        ),
        prohibited_actions=OPPOSITIONS_PROHIBITED_ACTIONS,
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
                "source_authority",
                "temporal_state",
                "interpretations",
                "hypotheses",
                "contradictions",
                "gaps",
                "open_questions",
                "planning_proposals",
                "possible_actions",
            ),
            optional_sections=("timeline", "comparison", "workload", "risks"),
            suppressible_sections=(),
            preferred_section_order=(
                "facts",
                "source_authority",
                "temporal_state",
                "interpretations",
                "hypotheses",
                "contradictions",
                "gaps",
                "open_questions",
                "planning_proposals",
                "possible_actions",
            ),
            protected_terms=(
                "observed_opposition_fact",
                "source_authority",
                "provenance",
                "interpretation",
                "hypothesis",
                "uncertainty",
                "contradiction",
                "official_state",
                "strategy_state",
                "personal_memory",
                "performance_not_capacity",
                "one_mock_not_trend",
                "planning_proposal",
                "preparation_proposal",
                "strategy_proposal",
                "call_monitoring_need",
                "possible_action",
                "open_question",
            ),
            term_glosses={
                "observed_opposition_fact": "directly evidenced opposition fact",
                "source_authority": "authority preserved by attribute and source",
                "provenance": "source origin",
                "interpretation": "user's interpretation, not a fact",
                "hypothesis": "unverified system proposition",
                "uncertainty": "unknown confidence",
                "contradiction": "conflicting information",
                "official_state": "grounded external opposition facts",
                "strategy_state": "internal CMM planning/decision state, not an official fact",
                "personal_memory": "personal memory, never Official Opposition State",
                "performance_not_capacity": "one mock or score never implies capacity",
                "one_mock_not_trend": "a single mock observation is not a performance trend",
                "planning_proposal": "a candidate plan, not an adopted decision",
                "preparation_proposal": "preparation material, not an action",
                "strategy_proposal": "a candidate strategy, not an adopted user decision",
                "call_monitoring_need": "structured verification requirement, not a scheduler",
                "possible_action": "a candidate, not an adopted decision",
                "open_question": "unresolved question or missing information",
            },
            preferred_components=(
                "facts",
                "source_authority",
                "temporal_state",
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
        metadata={"phase": "10.23"},
    )


__all__ = [
    "OPPOSITIONS_PROFILE_ID",
    "OPPOSITIONS_PROFILE_NAME",
    "OPPOSITIONS_PROHIBITED_ACTIONS",
    "build_oppositions_profile",
]