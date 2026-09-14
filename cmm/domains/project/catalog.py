"""Phase 10.30 — Canonical Project Domain Catalog.

Single source of truth for the structural IDs of the Project Domain.

Counts:
27 entities, 22 resources, 18 rules, 20 operations, 12 workflows.
"""

from __future__ import annotations

PROJECT_DOMAIN_ID: str = "domain:project"
PROJECT_DOMAIN_VERSION: str = "1.0.0"
PROJECT_MANIFEST_ID: str = "manifest:project:1.0.0"
PROJECT_PROFILE_NAME: str = "ProjectProfile"

CANONICAL_PROJECT_ENTITY_TYPES: tuple[str, ...] = (
    "project",
    "objective",
    "milestone",
    "work_item",
    "deliverable",
    "project_resource",
    "constraint",
    "risk",
    "decision",
    "status_change",
    "project_event",
    "repository",
    "module",
    "package",
    "file",
    "class",
    "method",
    "function",
    "contract",
    "dependency",
    "test",
    "validation_result",
    "issue",
    "technical_debt",
    "architecture_decision",
    "workflow",
    "release",
)

CANONICAL_PROJECT_ENTITY_IDS: tuple[str, ...] = tuple(
    f"project.entity.{name}" for name in CANONICAL_PROJECT_ENTITY_TYPES
)

PROJECT_ENTITY_IDS: tuple[str, ...] = CANONICAL_PROJECT_ENTITY_IDS

CANONICAL_PROJECT_RESOURCE_KINDS: tuple[str, ...] = (
    "project_brief",
    "project_plan",
    "milestone_record",
    "work_item_record",
    "dependency_record",
    "resource_record",
    "status_report",
    "decision_record",
    "risk_record",
    "project_timeline",
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
    "memory_entry",
)

CANONICAL_PROJECT_RESOURCE_IDS: tuple[str, ...] = tuple(
    f"project.resource.{kind}" for kind in CANONICAL_PROJECT_RESOURCE_KINDS
)

PROJECT_RESOURCE_IDS: tuple[str, ...] = CANONICAL_PROJECT_RESOURCE_IDS

CANONICAL_PROJECT_RULE_IDS: tuple[str, ...] = (
    "project.scope_consistency",
    "project.milestone_consistency",
    "project.dependency_consistency",
    "project.status_transition",
    "project.resource_constraint",
    "project.decision_state",
    "project.temporal_validity",
    "project.progress_evidence",
    "project.architecture_contract",
    "project.code_documentation_consistency",
    "project.validation_required",
    "project.technical_debt",
    "project.dead_code",
    "project.public_api_change",
    "project.backward_compatibility",
    "project.dependency_boundary",
    "project.test_coverage_impact",
    "project.semantic_transformation",
)

PROJECT_RULE_IDS: tuple[str, ...] = CANONICAL_PROJECT_RULE_IDS

CANONICAL_PROJECT_OPERATION_IDS: tuple[str, ...] = (
    "project.create_project_overview",
    "project.review_status",
    "project.plan_milestones",
    "project.review_dependencies",
    "project.review_resources",
    "project.review_risks",
    "project.generate_progress_summary",
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
)

PROJECT_OPERATION_IDS: tuple[str, ...] = CANONICAL_PROJECT_OPERATION_IDS

CANONICAL_PROJECT_WORKFLOW_IDS: tuple[str, ...] = (
    "project.project_setup",
    "project.status_review",
    "project.milestone_dependency_review",
    "project.periodic_project_review",
    "project.architecture_review",
    "project.feature_implementation",
    "project.bug_resolution",
    "project.technical_debt_review",
    "project.documentation_synchronisation",
    "project.refactor",
    "project.release_preparation",
    "project.self_development",
)

PROJECT_WORKFLOW_IDS: tuple[str, ...] = CANONICAL_PROJECT_WORKFLOW_IDS

__all__ = [
    "CANONICAL_PROJECT_ENTITY_IDS",
    "CANONICAL_PROJECT_ENTITY_TYPES",
    "CANONICAL_PROJECT_OPERATION_IDS",
    "CANONICAL_PROJECT_RESOURCE_IDS",
    "CANONICAL_PROJECT_RESOURCE_KINDS",
    "CANONICAL_PROJECT_RULE_IDS",
    "CANONICAL_PROJECT_WORKFLOW_IDS",
    "PROJECT_DOMAIN_ID",
    "PROJECT_DOMAIN_VERSION",
    "PROJECT_ENTITY_IDS",
    "PROJECT_MANIFEST_ID",
    "PROJECT_OPERATION_IDS",
    "PROJECT_PROFILE_NAME",
    "PROJECT_RESOURCE_IDS",
    "PROJECT_RULE_IDS",
    "PROJECT_WORKFLOW_IDS",
]
