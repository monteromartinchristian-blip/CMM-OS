"""Phase 10.43 — Policy-family bindings (Task 1).

Proves the six conceptual policy families resolve to canonical Phase 7
``ValidationPolicy`` instances with deterministic, monotonic composition.
"""

from __future__ import annotations

import pytest

from cmm.domains.validation_policy_bindings import (
    CROSS_DOMAIN_EXECUTION_POLICY_NAME,
    DOMAIN_OPERATION_POLICY_NAME,
    DOMAIN_PACK_BASE_VALIDATION_IDS,
    DOMAIN_PACK_INSTALLATION_POLICY_NAME,
    DOMAIN_PACK_UPDATE_POLICY_NAME,
    DOMAIN_WORKFLOW_POLICY_NAME,
    PROJECT_DOMAIN_CHANGE_POLICY_NAME,
    build_cross_domain_execution_policy,
    build_domain_operation_policy,
    build_domain_pack_installation_policy,
    build_domain_pack_update_policy,
    build_domain_workflow_policy,
    build_project_domain_change_policy,
    compose_required_validation_ids,
)
from cmm.validation import ValidationPolicy


@pytest.mark.parametrize(
    "impact",
    (
        "unknown",
        "critical-structural",
        "unexpected-new-impact",
    ),
)
def test_unknown_project_impact_fails_closed(impact: str) -> None:
    with pytest.raises(ValueError):
        build_project_domain_change_policy(impact=impact)


def test_public_impact_maps_to_canonical_public_api_change() -> None:
    policy = build_project_domain_change_policy(impact="public")
    assert policy.metadata["canonical_phase7_policy"] == "public_api_change"
    assert policy.require_full_suite is True


def test_phase_1043_exposes_all_six_policy_family_identities() -> None:
    assert {
        DOMAIN_PACK_INSTALLATION_POLICY_NAME,
        DOMAIN_PACK_UPDATE_POLICY_NAME,
        DOMAIN_OPERATION_POLICY_NAME,
        DOMAIN_WORKFLOW_POLICY_NAME,
        CROSS_DOMAIN_EXECUTION_POLICY_NAME,
        PROJECT_DOMAIN_CHANGE_POLICY_NAME,
    } == {
        "DomainPackInstallationPolicy",
        "DomainPackUpdatePolicy",
        "DomainOperationPolicy",
        "DomainWorkflowPolicy",
        "CrossDomainExecutionPolicy",
        "ProjectDomainChangePolicy",
    }


def test_pack_policy_reuses_canonical_validation_policy() -> None:
    policy = build_domain_pack_installation_policy()
    assert isinstance(policy, ValidationPolicy)


def test_all_builders_return_canonical_validation_policy() -> None:
    assert isinstance(build_domain_pack_update_policy(), ValidationPolicy)
    assert isinstance(
        build_domain_operation_policy(required_validation_ids=("domain.contracts",)),
        ValidationPolicy,
    )
    assert isinstance(
        build_domain_workflow_policy(required_validation_ids=("domain.contracts",)),
        ValidationPolicy,
    )
    assert isinstance(
        build_cross_domain_execution_policy(
            primary_required=("domain.contracts",),
            supporting_required=("domain.permissions",),
        ),
        ValidationPolicy,
    )
    assert isinstance(build_project_domain_change_policy(), ValidationPolicy)


def test_pack_base_ids_preserve_existing_eight_domain_checks() -> None:
    assert DOMAIN_PACK_BASE_VALIDATION_IDS == (
        "domain.compatibility",
        "domain.contracts",
        "domain.dependencies",
        "domain.fragmentation",
        "domain.manifest",
        "domain.permissions",
        "domain.security",
        "domain.tests",
    )


def test_installation_policy_requires_base_domain_checks() -> None:
    policy = build_domain_pack_installation_policy()
    assert set(policy.required_steps) >= set(DOMAIN_PACK_BASE_VALIDATION_IDS)


def test_update_policy_requires_base_domain_checks() -> None:
    policy = build_domain_pack_update_policy()
    assert set(policy.required_steps) >= set(DOMAIN_PACK_BASE_VALIDATION_IDS)


def test_policy_family_identity_preserved_in_metadata() -> None:
    assert (
        build_domain_pack_installation_policy().metadata["domain_policy_family"]
        == DOMAIN_PACK_INSTALLATION_POLICY_NAME
    )
    assert (
        build_domain_pack_update_policy().metadata["domain_policy_family"]
        == DOMAIN_PACK_UPDATE_POLICY_NAME
    )
    assert (
        build_domain_operation_policy().metadata["domain_policy_family"]
        == DOMAIN_OPERATION_POLICY_NAME
    )
    assert (
        build_domain_workflow_policy().metadata["domain_policy_family"]
        == DOMAIN_WORKFLOW_POLICY_NAME
    )
    assert (
        build_cross_domain_execution_policy().metadata["domain_policy_family"]
        == CROSS_DOMAIN_EXECUTION_POLICY_NAME
    )
    assert (
        build_project_domain_change_policy().metadata["domain_policy_family"]
        == PROJECT_DOMAIN_CHANGE_POLICY_NAME
    )


def test_compose_required_validation_ids_is_deterministic_and_monotonic() -> None:
    actual = compose_required_validation_ids(
        ("domain.permissions", "domain.contracts"),
        ("domain.contracts", "project.validation"),
    )
    assert actual == (
        "domain.contracts",
        "domain.permissions",
        "project.validation",
    )


def test_compose_collapses_duplicates_without_dropping_distinct() -> None:
    actual = compose_required_validation_ids(
        ("domain.contracts", "domain.permissions"),
        ("domain.permissions", "domain.contracts", "domain.security"),
        ("domain.security",),
    )
    assert actual == (
        "domain.contracts",
        "domain.permissions",
        "domain.security",
    )
    # Monotonic: adding a group never removes an obligation.
    smaller = compose_required_validation_ids(("domain.contracts",))
    larger = compose_required_validation_ids(
        ("domain.contracts",), ("domain.permissions",)
    )
    assert set(smaller) <= set(larger)


def test_compose_empty_groups_yields_empty() -> None:
    assert compose_required_validation_ids() == ()
    assert compose_required_validation_ids((), ()) == ()


def test_compose_rejects_empty_and_non_string_ids() -> None:
    with pytest.raises(ValueError):
        compose_required_validation_ids(("",))
    with pytest.raises(ValueError):
        compose_required_validation_ids((None,))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        compose_required_validation_ids((123,))  # type: ignore[arg-type]


def test_cross_domain_policy_composes_monotonic_union() -> None:
    policy = build_cross_domain_execution_policy(
        global_required=("domain.manifest",),
        primary_required=("domain.contracts", "domain.permissions"),
        supporting_required=("domain.permissions", "domain.security"),
        operation_required=("operation.output.validation",),
        workflow_required=("workflow.result.validation",),
    )
    assert tuple(policy.required_steps) == (
        "domain.contracts",
        "domain.manifest",
        "domain.permissions",
        "domain.security",
        "operation.output.validation",
        "workflow.result.validation",
    )


def test_project_policy_is_stricter_than_empty_operation_policy() -> None:
    operation_policy = build_domain_operation_policy(required_validation_ids=())
    project_policy = build_project_domain_change_policy()
    # Project code-change policy must carry real obligations even when an
    # ordinary operation declares none.
    assert len(project_policy.required_steps) > len(operation_policy.required_steps)
    assert project_policy.stop_on_blocking_failure is True
