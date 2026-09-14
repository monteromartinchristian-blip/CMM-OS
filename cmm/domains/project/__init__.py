"""Phase 10.30 — Project Domain.

Canonical implementation of the Project Domain for CMM OS.
Provides:
- 27 entities, 22 resources, 18 reasoning rules, 20 operations, 12 workflows
- Strict generic / software capability partitioning
- Approval-gated file modification
- Fail-closed memory proposal and trace bindings
- Atomic registration and bootstrap
"""

from __future__ import annotations

from cmm.domains.project.bootstrap import (
    PROJECT_BOOTSTRAP_NAME,
    ProjectDomainBootstrap,
    build_standard_project_domain_bootstrap,
)
from cmm.domains.project.catalog import (
    CANONICAL_PROJECT_ENTITY_IDS,
    CANONICAL_PROJECT_ENTITY_TYPES,
    CANONICAL_PROJECT_OPERATION_IDS,
    CANONICAL_PROJECT_RESOURCE_IDS,
    CANONICAL_PROJECT_RESOURCE_KINDS,
    CANONICAL_PROJECT_RULE_IDS,
    CANONICAL_PROJECT_WORKFLOW_IDS,
    PROJECT_DOMAIN_ID,
    PROJECT_DOMAIN_VERSION,
    PROJECT_ENTITY_IDS,
    PROJECT_MANIFEST_ID,
    PROJECT_OPERATION_IDS,
    PROJECT_PROFILE_NAME,
    PROJECT_RESOURCE_IDS,
    PROJECT_RULE_IDS,
    PROJECT_WORKFLOW_IDS,
)
from cmm.domains.project.definition import build_project_domain_definition
from cmm.domains.project.integration import (
    ProjectDomainIntegrationResult,
    register_project_domain,
)
from cmm.domains.project.memory import (
    CANDIDATE_PROJECT_LONGITUDINAL_KINDS,
    build_project_memory_binding,
    build_project_memory_proposal,
    build_project_memory_view,
    build_project_memory_view_request,
    validate_project_memory_binding,
    validate_project_memory_proposal_content,
)
from cmm.domains.project.operations import (
    build_prepare_commit_readiness_result,
    build_project_operation_definitions,
    create_project_overview_result,
    generate_project_progress_summary_result,
    plan_project_milestones_result,
    review_project_dependencies_result,
    review_project_resources_result,
    review_project_risks_result,
    review_project_status_result,
)
from cmm.domains.project.permissions import (
    PROJECT_PERMISSION_POLICY_ID,
    PROJECT_PROHIBITED_CAPABILITIES,
    build_project_permission_policy,
    permission_authorization_allows,
)
from cmm.domains.project.presentation import (
    build_project_presentation_policy,
    present_project_result,
)
from cmm.domains.project.profile import (
    GENERIC_PROJECT_RULE_IDS,
    SOFTWARE_PROJECT_RULE_IDS,
    build_project_profile,
    project_software_capability_active,
)
from cmm.domains.project.resources import (
    GENERIC_PROJECT_RESOURCE_KINDS,
    PROJECT_DECISION_STATE_VALUES,
    PROJECT_STATUS_VALUES,
    SOFTWARE_PROJECT_RESOURCE_KINDS,
    build_project_resource_definitions,
    validate_project_decision_state,
    validate_project_status,
)
from cmm.domains.project.rules import (
    ALLOWED_LIFE_PLAN_PROJECTION_FIELDS,
    PROHIBITED_LIFE_PLAN_PROJECTION_FIELDS,
    authorize_project_life_plan_contribution,
    build_project_life_plan_projection,
    build_project_rules,
    evaluate_dependency_consistency,
    evaluate_milestone_consistency,
    evaluate_project_decision_state,
    evaluate_project_progress_evidence,
    evaluate_project_resource_constraints,
    evaluate_project_scope_consistency,
    evaluate_project_status_transition,
    evaluate_project_temporal_validity,
)
from cmm.domains.project.trace import (
    assemble_project_trace,
    build_project_trace_contribution,
    build_project_trace_reference,
    build_supporting_trace_contribution,
    validate_project_trace,
)
from cmm.domains.project.workflows import (
    GENERIC_PROJECT_WORKFLOW_IDS,
    PROJECT_WORKFLOW_NAMES_BY_ID,
    SOFTWARE_PROJECT_WORKFLOW_IDS,
    build_project_workflow_definitions,
)

__all__ = [
    "ALLOWED_LIFE_PLAN_PROJECTION_FIELDS",
    "CANDIDATE_PROJECT_LONGITUDINAL_KINDS",
    "CANONICAL_PROJECT_ENTITY_IDS",
    "CANONICAL_PROJECT_ENTITY_TYPES",
    "CANONICAL_PROJECT_OPERATION_IDS",
    "CANONICAL_PROJECT_RESOURCE_IDS",
    "CANONICAL_PROJECT_RESOURCE_KINDS",
    "CANONICAL_PROJECT_RULE_IDS",
    "CANONICAL_PROJECT_WORKFLOW_IDS",
    "GENERIC_PROJECT_RESOURCE_KINDS",
    "GENERIC_PROJECT_RULE_IDS",
    "GENERIC_PROJECT_WORKFLOW_IDS",
    "PROHIBITED_LIFE_PLAN_PROJECTION_FIELDS",
    "PROJECT_BOOTSTRAP_NAME",
    "PROJECT_DECISION_STATE_VALUES",
    "PROJECT_DOMAIN_ID",
    "PROJECT_DOMAIN_VERSION",
    "PROJECT_ENTITY_IDS",
    "PROJECT_MANIFEST_ID",
    "PROJECT_OPERATION_IDS",
    "PROJECT_PERMISSION_POLICY_ID",
    "PROJECT_PROFILE_NAME",
    "PROJECT_PROHIBITED_CAPABILITIES",
    "PROJECT_RESOURCE_IDS",
    "PROJECT_RULE_IDS",
    "PROJECT_STATUS_VALUES",
    "PROJECT_WORKFLOW_IDS",
    "PROJECT_WORKFLOW_NAMES_BY_ID",
    "SOFTWARE_PROJECT_RESOURCE_KINDS",
    "SOFTWARE_PROJECT_RULE_IDS",
    "SOFTWARE_PROJECT_WORKFLOW_IDS",
    "ProjectDomainBootstrap",
    "ProjectDomainIntegrationResult",
    "assemble_project_trace",
    "authorize_project_life_plan_contribution",
    "build_prepare_commit_readiness_result",
    "build_project_domain_definition",
    "build_project_life_plan_projection",
    "build_project_memory_binding",
    "build_project_memory_proposal",
    "build_project_memory_view",
    "build_project_memory_view_request",
    "build_project_operation_definitions",
    "build_project_permission_policy",
    "build_project_presentation_policy",
    "build_project_profile",
    "build_project_resource_definitions",
    "build_project_rules",
    "build_project_trace_contribution",
    "build_project_trace_reference",
    "build_project_workflow_definitions",
    "build_standard_project_domain_bootstrap",
    "build_supporting_trace_contribution",
    "create_project_overview_result",
    "evaluate_dependency_consistency",
    "evaluate_milestone_consistency",
    "evaluate_project_decision_state",
    "evaluate_project_progress_evidence",
    "evaluate_project_resource_constraints",
    "evaluate_project_scope_consistency",
    "evaluate_project_status_transition",
    "evaluate_project_temporal_validity",
    "generate_project_progress_summary_result",
    "permission_authorization_allows",
    "plan_project_milestones_result",
    "present_project_result",
    "project_software_capability_active",
    "register_project_domain",
    "review_project_dependencies_result",
    "review_project_resources_result",
    "review_project_risks_result",
    "review_project_status_result",
    "validate_project_decision_state",
    "validate_project_memory_binding",
    "validate_project_memory_proposal_content",
    "validate_project_status",
    "validate_project_trace",
]
