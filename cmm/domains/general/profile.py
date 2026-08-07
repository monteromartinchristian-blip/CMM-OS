"""Phase 10.19 — General Domain Profile."""

from __future__ import annotations

from cmm.domains.enums import DomainReasoningDepth
from cmm.domains.profile_contracts import (
    DomainMemoryPolicy,
    DomainPresentationPolicy,
    DomainProductionPolicy,
    DomainProfileDefinition,
    DomainQuestionPolicy,
    DomainTemporalPolicy,
)

GENERAL_PROFILE_ID = "general.profile"
GENERAL_PROFILE_NAME = "GeneralProfile"

GENERAL_PROHIBITED_ACTIONS: tuple[str, ...] = (
    "external_communication",
    "file_modification",
    "schedule_modification",
    "task_creation_persistent",
    "goal_update_persistent",
    "sensitive_inference",
    "medical_decision",
    "legal_decision",
    "financial_decision",
    "export",
    "shell_execution",
)


def build_general_profile() -> DomainProfileDefinition:
    """Build the ``GeneralProfile`` deterministically."""
    return DomainProfileDefinition(
        id=GENERAL_PROFILE_ID,
        domain_id="domain:general",
        profile_name=GENERAL_PROFILE_NAME,
        required_rules=(
            "general.temporal_validity",
            "general.source_reliability",
            "general.ambiguity",
            "general.permission",
            "general.goal_clarification",
            "general.duplication",
        ),
        optional_rules=(),
        prohibited_rules=(),
        allowed_resource_kinds=(
            "user_message",
            "conversation",
            "calendar_event",
            "note",
            "document",
            "memory_entry",
            "generic_task",
            "generic_goal",
            "external_source",
        ),
        priority_resource_kinds=("user_message", "note", "document"),
        prohibited_resource_kinds=(),
        minimum_confidence=0.55,
        reasoning_depth=DomainReasoningDepth.STANDARD,
        allowed_inferences=("fact", "inference", "hypothesis"),
        prohibited_inferences=("sensitive_inference",),
        maximum_questions=8,
        escalation_rules=("general.permission",),
        prohibited_actions=GENERAL_PROHIBITED_ACTIONS,
        question_policy=DomainQuestionPolicy(
            maximum_questions=8,
            allow_follow_up=True,
            require_deduplication=True,
            allow_clarification=True,
            stop_on_blocking_gap=True,
        ),
        presentation_policy=DomainPresentationPolicy(
            detail_level="standard",
            include_uncertainty=True,
            include_provenance=True,
            include_alternatives=True,
            allow_speculation=False,
            require_disclaimers=True,
            required_sections=(
                "summary",
                "facts",
                "inferences",
                "hypotheses",
                "sources",
                "confidence",
                "contradictions",
                "gaps",
                "questions",
            ),
            optional_sections=("timeline", "options", "recommendations"),
            suppressible_sections=(),
            preferred_section_order=(
                "summary",
                "facts",
                "inferences",
                "hypotheses",
                "sources",
                "confidence",
                "contradictions",
                "gaps",
                "questions",
            ),
            protected_terms=(
                "fact",
                "inference",
                "hypothesis",
                "uncertainty",
                "provenance",
                "contradiction",
                "gap",
                "warning",
            ),
            term_glosses={
                "fact": "verified information",
                "inference": "derived conclusion",
                "hypothesis": "unverified proposition",
                "uncertainty": "unknown confidence",
                "provenance": "source origin",
                "contradiction": "conflicting information",
                "gap": "missing information",
                "warning": "caution required",
            },
            preferred_components=("summary", "facts", "sources"),
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
            sensitivity_limit="internal",
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
        metadata={"phase": "10.19"},
    )


__all__ = [
    "GENERAL_PROFILE_ID",
    "GENERAL_PROFILE_NAME",
    "GENERAL_PROHIBITED_ACTIONS",
    "build_general_profile",
]