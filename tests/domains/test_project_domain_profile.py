"""Phase 10.30 — Project Domain Profile & Activation Matrix Tests."""

from __future__ import annotations

from cmm.domains.project.catalog import CANONICAL_PROJECT_RULE_IDS
from cmm.domains.project.profile import (
    GENERIC_PROJECT_RULE_IDS,
    PROJECT_PROFILE_ID,
    SOFTWARE_PROJECT_RULE_IDS,
    build_project_profile,
    project_software_capability_active,
)


def test_project_profile_identity_and_rules() -> None:
    profile = build_project_profile()
    assert profile.profile_name == "ProjectProfile"
    assert profile.id == PROJECT_PROFILE_ID
    assert str(profile.domain_id) == "domain:project"

    assert len(GENERIC_PROJECT_RULE_IDS) == 8
    assert len(SOFTWARE_PROJECT_RULE_IDS) == 10
    assert GENERIC_PROJECT_RULE_IDS == CANONICAL_PROJECT_RULE_IDS[:8]
    assert SOFTWARE_PROJECT_RULE_IDS == CANONICAL_PROJECT_RULE_IDS[8:]

    assert profile.required_rules == GENERIC_PROJECT_RULE_IDS
    assert profile.optional_rules == SOFTWARE_PROJECT_RULE_IDS
    assert profile.prohibited_rules == ()


def test_fake_software_workflow_prefix_does_not_activate() -> None:
    assert (
        project_software_capability_active(workflow_id="project.software_forged")
        is False
    )


def test_resource_suffix_collision_does_not_activate() -> None:
    assert (
        project_software_capability_active(resource_ids=("attacker.source_code",))
        is False
    )


def test_raw_repository_boolean_is_not_authority() -> None:
    assert project_software_capability_active(repository_backed=True) is False


def test_project_software_capability_activation_matrix() -> None:
    # False conditions:
    assert not project_software_capability_active()
    assert not project_software_capability_active(workflow_id="project.project_setup")
    assert not project_software_capability_active(workflow_id="project.status_review")
    assert not project_software_capability_active(workflow_id="project.software_forged")
    assert not project_software_capability_active(operation_id="project.review_status")
    assert not project_software_capability_active(
        resource_ids=("project.resource.project_brief",)
    )
    assert not project_software_capability_active(
        resource_ids=("attacker.source_code",)
    )
    assert not project_software_capability_active(capabilities=("project_management",))
    assert not project_software_capability_active(repository_backed=True)

    # True conditions:
    assert project_software_capability_active(workflow_id="project.self_development")
    assert project_software_capability_active(
        workflow_id="project.feature_implementation"
    )
    assert project_software_capability_active(operation_id="project.modify_code")
    assert project_software_capability_active(
        operation_id="project.analyse_architecture"
    )
    assert project_software_capability_active(
        resource_ids=("project.resource.source_code",)
    )
    assert project_software_capability_active(
        resource_ids=("project.resource.source_code:file.py",)
    )
    assert project_software_capability_active(resource_ids=("source_code",))
    assert project_software_capability_active(
        capabilities=("project_software_development",)
    )
    assert project_software_capability_active(
        repository_context={"repo_path": "/tmp/repo"}
    )
