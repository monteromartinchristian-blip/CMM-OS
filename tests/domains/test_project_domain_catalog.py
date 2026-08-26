"""Phase 10.30 — Project Domain Catalog & Definition Tests."""

from __future__ import annotations

from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind
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
    PROJECT_MANIFEST_ID,
    PROJECT_PROFILE_NAME,
)
from cmm.domains.project.definition import build_project_domain_definition

EXPECTED_ENTITY_TYPES = (
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

EXPECTED_RESOURCE_KINDS = (
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

EXPECTED_RULE_IDS = (
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

EXPECTED_OPERATION_IDS = (
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

EXPECTED_WORKFLOW_IDS = (
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


def test_canonical_catalog_identity_and_counts() -> None:
    assert PROJECT_DOMAIN_ID == "domain:project"
    assert PROJECT_DOMAIN_VERSION == "1.0.0"
    assert PROJECT_MANIFEST_ID == "manifest:project:1.0.0"
    assert PROJECT_PROFILE_NAME == "ProjectProfile"

    assert len(CANONICAL_PROJECT_ENTITY_TYPES) == 27
    assert len(CANONICAL_PROJECT_RESOURCE_KINDS) == 22
    assert len(CANONICAL_PROJECT_RULE_IDS) == 18
    assert len(CANONICAL_PROJECT_OPERATION_IDS) == 20
    assert len(CANONICAL_PROJECT_WORKFLOW_IDS) == 12

    assert CANONICAL_PROJECT_ENTITY_TYPES == EXPECTED_ENTITY_TYPES
    assert CANONICAL_PROJECT_ENTITY_IDS == tuple(
        f"project.entity.{t}" for t in EXPECTED_ENTITY_TYPES
    )

    assert CANONICAL_PROJECT_RESOURCE_KINDS == EXPECTED_RESOURCE_KINDS
    assert CANONICAL_PROJECT_RESOURCE_IDS == tuple(
        f"project.resource.{k}" for k in EXPECTED_RESOURCE_KINDS
    )

    assert CANONICAL_PROJECT_RULE_IDS == EXPECTED_RULE_IDS
    assert CANONICAL_PROJECT_OPERATION_IDS == EXPECTED_OPERATION_IDS
    assert CANONICAL_PROJECT_WORKFLOW_IDS == EXPECTED_WORKFLOW_IDS

    # Disallow legacy operation in canonical inventory
    assert "project.review_change" in CANONICAL_PROJECT_OPERATION_IDS
    assert "project.prepare_change_review" not in CANONICAL_PROJECT_OPERATION_IDS


def test_build_project_domain_definition() -> None:
    defn = build_project_domain_definition()
    assert isinstance(defn, DomainDefinition)
    assert defn.id == "domain:project"
    assert defn.name == "project"
    assert defn.display_name == "Project"
    assert defn.version == "1.0.0"
    assert defn.kind == DomainKind.PROJECT
    assert defn.manifest_id == "manifest:project:1.0.0"
    assert defn.reasoning_profile == "ProjectProfile"
    assert defn.resources == CANONICAL_PROJECT_RESOURCE_IDS
    assert defn.rules == CANONICAL_PROJECT_RULE_IDS
    assert defn.operations == CANONICAL_PROJECT_OPERATION_IDS
    assert defn.workflows == CANONICAL_PROJECT_WORKFLOW_IDS
    assert defn.permissions == ("domain-permission:project:1.0.0",)
    assert defn.enabled is True
    assert len(defn.capabilities) > 0
