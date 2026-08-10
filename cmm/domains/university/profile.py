"""Phase 10.22 — University Domain Profile.

A deliberately conservative ``DomainProfileDefinition`` for academic reasoning:
provenance-heavy, attribute-specific source authority, explicit uncertainty,
Academic State vs Personal Memory separation, Academic Integrity Mode C
(permissive-by-default), and decision support that never adopts an academic
decision.  The profile preserves source authority by attribute, never infers
intellectual capacity from observed performance, never sends email, never
submits formal procedures, and never modifies the official university record.
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
from cmm.domains.university.catalog import CANONICAL_UNIVERSITY_RULE_IDS
from cmm.domains.university.resources import UNIVERSITY_RESOURCE_KINDS

UNIVERSITY_PROFILE_ID = "university.profile"
UNIVERSITY_PROFILE_NAME = "UniversityProfile"

# Encodes the forbidden actions of the University safety model (spec §1, §8).
# University never adopts an academic decision, never sends email, never
# submits formal procedures, never modifies the official record, never sets a
# calendar/task event autonomously, and never infers intellectual capacity.
UNIVERSITY_PROHIBITED_ACTIONS: tuple[str, ...] = (
    "academic_decision_adoption",
    "academic_decision_execution",
    "email_sending",
    "email_authorization",
    "formal_procedure_submission",
    "enrollment_registration",
    "official_record_modification",
    "official_record_write",
    "calendar_event_creation",
    "task_creation",
    "schedule_modification",
    "capacity_inference_from_performance",
    "intellectual_capacity_inference",
    "performance_as_capacity",
    "academic_integrity_mode_a",
    "academic_integrity_mode_b",
    "sensitive_inference_persist",
    "sensitive_cross_domain_transfer",
    "unconfirmed_sensitive_memory_persistence",
    "export",
    "shell_execution",
)


def build_university_profile() -> DomainProfileDefinition:
    """Build the ``UniversityProfile`` deterministically."""
    return DomainProfileDefinition(
        id=UNIVERSITY_PROFILE_ID,
        domain_id="domain:university",
        profile_name=UNIVERSITY_PROFILE_NAME,
        required_rules=CANONICAL_UNIVERSITY_RULE_IDS,
        optional_rules=(),
        prohibited_rules=(),
        allowed_resource_kinds=UNIVERSITY_RESOURCE_KINDS,
        priority_resource_kinds=(
            "academic_record",
            "grade",
            "regulation",
            "subject_guide",
        ),
        prohibited_resource_kinds=(),
        minimum_confidence=0.75,
        reasoning_depth=DomainReasoningDepth.STANDARD,
        allowed_inferences=(
            "observed_academic_fact",
            "official_record_fact",
            "user_stated_fact",
            "system_hypothesis",
            "source_authority_by_attribute",
            "contradiction",
            "missing_information",
            "open_question",
            "possible_action",
            "planning_proposal",
            "preparation_proposal",
        ),
        prohibited_inferences=(
            "capacity_inference",
            "intellectual_capacity",
            "psychometric_inference",
            "academic_decision_adoption",
            "sensitive_inference",
            "sensitive_inference_persist",
        ),
        maximum_questions=10,
        escalation_rules=(
            "university.academic_source_authority",
            "university.academic_contradiction",
            "university.observed_performance_capacity",
            "university.academic_integrity",
        ),
        prohibited_actions=UNIVERSITY_PROHIBITED_ACTIONS,
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
                "interpretations",
                "hypotheses",
                "contradictions",
                "open_questions",
                "planning_proposals",
                "possible_actions",
            ),
            optional_sections=("timeline", "comparison", "workload"),
            suppressible_sections=(),
            preferred_section_order=(
                "facts",
                "source_authority",
                "interpretations",
                "hypotheses",
                "contradictions",
                "open_questions",
                "planning_proposals",
                "possible_actions",
            ),
            protected_terms=(
                "observed_academic_fact",
                "source_authority",
                "provenance",
                "interpretation",
                "hypothesis",
                "uncertainty",
                "contradiction",
                "academic_state",
                "personal_memory",
                "performance_not_capacity",
                "planning_proposal",
                "preparation_proposal",
                "possible_action",
                "open_question",
            ),
            term_glosses={
                "observed_academic_fact": "directly evidenced academic fact",
                "source_authority": "authority preserved by attribute and source",
                "provenance": "source origin",
                "interpretation": "user's interpretation, not a fact",
                "hypothesis": "unverified system proposition",
                "uncertainty": "unknown confidence",
                "contradiction": "conflicting information",
                "academic_state": "internal CMM structured academic state, never the official university record",
                "personal_memory": "personal memory, never Academic State",
                "performance_not_capacity": "observed performance never implies capacity",
                "planning_proposal": "a candidate plan, not an adopted decision",
                "preparation_proposal": "preparation material, not an action",
                "possible_action": "a candidate, not an adopted decision",
                "open_question": "unresolved question or missing information",
            },
            preferred_components=(
                "facts",
                "source_authority",
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
        metadata={"phase": "10.22"},
    )


__all__ = [
    "UNIVERSITY_PROFILE_ID",
    "UNIVERSITY_PROFILE_NAME",
    "UNIVERSITY_PROHIBITED_ACTIONS",
    "build_university_profile",
]