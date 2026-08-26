"""Phase 10.30 — Project Domain Profile.

A structured ``DomainProfileDefinition`` for Project:
- Generic project management core (scope, milestones, dependencies, status,
  resources, decisions, temporal validity, progress evidence).
- Conditional software capability (architecture, code/doc consistency,
  validation, technical debt, dead code, public API, backward compatibility,
  dependencies, test coverage, semantic transformations).
- Fail-closed permissions and no automatic external actions.
"""

from __future__ import annotations

from typing import Any

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
from cmm.domains.project.catalog import (
    CANONICAL_PROJECT_RESOURCE_KINDS,
    CANONICAL_PROJECT_RULE_IDS,
    PROJECT_DOMAIN_ID,
    PROJECT_PROFILE_NAME,
)

PROJECT_PROFILE_ID = "project.profile"

GENERIC_PROJECT_RULE_IDS: tuple[str, ...] = CANONICAL_PROJECT_RULE_IDS[:8]
SOFTWARE_PROJECT_RULE_IDS: tuple[str, ...] = CANONICAL_PROJECT_RULE_IDS[8:]

SOFTWARE_WORKFLOW_IDS: frozenset[str] = frozenset(
    {
        "project.architecture_review",
        "project.feature_implementation",
        "project.bug_resolution",
        "project.technical_debt_review",
        "project.documentation_synchronisation",
        "project.refactor",
        "project.release_preparation",
        "project.self_development",
    }
)

SOFTWARE_OPERATION_IDS: frozenset[str] = frozenset(
    {
        "project.analyse_architecture",
        "project.detect_technical_debt",
        "project.compare_code_documentation",
        "project.detect_dead_code",
        "project.detect_duplication",
        "project.generate_adr",
        "project.create_implementation_plan",
        "project.modify_code",
        "project.run_validation",
        "project.prepare_commit",
        "project.review_change",
        "project.update_documentation",
        "project.generate_release_notes",
    }
)

SOFTWARE_RESOURCE_KINDS: frozenset[str] = frozenset(
    {
        "source_code",
        "project_file",
        "documentation",
        "test_result",
        "validation_result",
        "git_history",
        "issue",
        "roadmap",
        "architecture_document",
        "commit",
        "pull_request",
    }
)

SOFTWARE_CAPABILITY_NAMES: frozenset[str] = frozenset(
    {
        "project_software_analysis",
        "project_software_development",
        "project_self_development",
    }
)

PROJECT_PROHIBITED_ACTIONS: tuple[str, ...] = (
    "direct_memory_write",
    "silent_memory_persistence",
    "direct_git_commit",
    "unauthorized_file_modification",
    "unauthorized_cross_domain_access",
    "external_communication",
    "payment",
    "financial_action",
    "permission_modification",
    "shell_execution",
)


CANONICAL_SOFTWARE_RESOURCE_IDS: frozenset[str] = frozenset(
    f"project.resource.{kind}" for kind in SOFTWARE_RESOURCE_KINDS
)


def project_software_capability_active(
    *,
    workflow_id: str | None = None,
    operation_id: str | None = None,
    resource_ids: tuple[str, ...] | list[str] = (),
    capabilities: tuple[str, ...] | list[str] = (),
    repository_context: Any = None,
    repository_backed: bool = False,
) -> bool:
    """Determine whether the conditional software capability is active fail-closed.

    Software capability activation requires grounded canonical evidence:
    - exact registered software workflow ID
    - exact registered software operation ID
    - resolved canonical Project software resource ID or kind
    - resolved canonical capability name
    - verified repository context object

    Prefix matches, suffix collisions, arbitrary booleans, or ungrounded caller
    strings are rejected fail-closed.
    """
    if workflow_id is not None and workflow_id in SOFTWARE_WORKFLOW_IDS:
        return True

    if operation_id is not None and operation_id in SOFTWARE_OPERATION_IDS:
        return True

    for cap in capabilities:
        if cap in SOFTWARE_CAPABILITY_NAMES:
            return True

    for r_id in resource_ids:
        base = r_id.split(":", 1)[0]
        if base in CANONICAL_SOFTWARE_RESOURCE_IDS or base in SOFTWARE_RESOURCE_KINDS:
            return True

    if repository_context is not None:
        if (
            hasattr(repository_context, "repo_path")
            or hasattr(repository_context, "root")
            or hasattr(repository_context, "repository_id")
        ):
            return True
        if isinstance(repository_context, dict) and (
            "repo_path" in repository_context or "repository_id" in repository_context
        ):
            return True

    return False


def build_project_profile() -> DomainProfileDefinition:
    """Build the ``ProjectProfile`` deterministically."""
    return DomainProfileDefinition(
        id=PROJECT_PROFILE_ID,
        domain_id=PROJECT_DOMAIN_ID,
        profile_name=PROJECT_PROFILE_NAME,
        required_rules=GENERIC_PROJECT_RULE_IDS,
        optional_rules=SOFTWARE_PROJECT_RULE_IDS,
        prohibited_rules=(),
        allowed_resource_kinds=CANONICAL_PROJECT_RESOURCE_KINDS,
        priority_resource_kinds=(
            "project_brief",
            "project_plan",
            "status_report",
            "milestone_record",
        ),
        prohibited_resource_kinds=(),
        minimum_confidence=0.7,
        reasoning_depth=DomainReasoningDepth.STANDARD,
        allowed_inferences=(
            "scope_consistency_analysis",
            "milestone_consistency_analysis",
            "dependency_consistency_analysis",
            "status_transition_evaluation",
            "resource_constraint_evaluation",
            "decision_state_tracking",
            "temporal_validity_evaluation",
            "progress_evidence_evaluation",
            "software_architecture_analysis",
            "code_documentation_consistency",
            "validation_requirement_evaluation",
            "technical_debt_detection",
            "dead_code_detection",
            "public_api_change_analysis",
            "backward_compatibility_analysis",
            "dependency_boundary_analysis",
            "test_coverage_impact_analysis",
            "semantic_transformation_requirement",
        ),
        prohibited_inferences=(
            "silent_memory_persistence",
            "unconfirmed_decision_promotion",
            "unconfirmed_status_promotion",
            "plan_to_completion_promotion",
            "ready_to_committed_promotion",
            "invented_capacity_inference",
            "fake_commit_inference",
        ),
        maximum_questions=5,
        escalation_rules=(
            "project.resource_constraint",
            "project.status_transition",
            "project.dependency_consistency",
        ),
        prohibited_actions=PROJECT_PROHIBITED_ACTIONS,
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
            require_disclaimers=False,
            required_sections=(
                "objective",
                "project_status",
                "milestones_and_deliverables",
                "dependencies_and_blockers",
                "resources_and_constraints",
                "decisions_and_risks",
                "progress_and_next_steps",
            ),
            optional_sections=(
                "architecture_contracts",
                "validation_results",
                "technical_debt",
                "change_review",
            ),
            suppressible_sections=(),
            preferred_section_order=(
                "objective",
                "project_status",
                "milestones_and_deliverables",
                "dependencies_and_blockers",
                "resources_and_constraints",
                "decisions_and_risks",
                "progress_and_next_steps",
            ),
            protected_terms=(
                "objective",
                "milestone",
                "deliverable",
                "dependency",
                "status",
                "blocker",
                "decision",
                "commit_readiness",
            ),
            term_glosses={
                "milestone": "significant scheduled checkpoint in the project lifecycle",
                "dependency": "prerequisite relationship between tasks, deliverables, or milestones",
                "status": "grounded state of progress, distinct from inferred or desired progress",
                "decision": "confirmed choice distinct from options, proposals, or plans",
                "commit_readiness": "state of change validation and approval prior to external commit",
            },
            preferred_components=(
                "objective",
                "project_status",
                "milestones_and_deliverables",
                "dependencies_and_blockers",
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
            sensitivity_limit=SensitivityLevel.INTERNAL,
        ),
        temporal_policy=DomainTemporalPolicy(
            require_current_information=True,
            allow_historical_information=True,
            require_temporal_provenance=True,
            allow_future_projection=True,
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
    "GENERIC_PROJECT_RULE_IDS",
    "PROJECT_PROFILE_ID",
    "PROJECT_PROFILE_NAME",
    "PROJECT_PROHIBITED_ACTIONS",
    "SOFTWARE_CAPABILITY_NAMES",
    "SOFTWARE_OPERATION_IDS",
    "SOFTWARE_PROJECT_RULE_IDS",
    "SOFTWARE_RESOURCE_KINDS",
    "SOFTWARE_WORKFLOW_IDS",
    "build_project_profile",
    "project_software_capability_active",
]
