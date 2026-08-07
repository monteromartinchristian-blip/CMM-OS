"""Tests for General Domain public API."""

from __future__ import annotations

from cmm.domains import general


def test_expected_exports():
    expected = {
        "CANONICAL_GENERAL_OPERATION_IDS",
        "CANONICAL_GENERAL_RESOURCE_IDS",
        "CANONICAL_GENERAL_RULE_IDS",
        "CANONICAL_GENERAL_WORKFLOW_IDS",
        "GENERAL_DOMAIN_ID",
        "GENERAL_DOMAIN_VERSION",
        "GENERAL_MANIFEST_ID",
        "GENERAL_OPERATION_IDS",
        "GENERAL_PERMISSION_IDS",
        "GENERAL_PERMISSION_POLICY_ID",
        "GENERAL_PROFILE_ID",
        "GENERAL_PROFILE_NAME",
        "GENERAL_PROHIBITED_ACTIONS",
        "GENERAL_RESOURCE_IDS",
        "GENERAL_RESOURCE_KINDS",
        "GENERAL_RULE_IDS",
        "GENERAL_WORKFLOW_IDS",
        "HISTORICAL_GENERAL_OPERATION_IDS",
        "GeneralAmbiguityRule",
        "GeneralDomainBootstrap",
        "GeneralDomainIntegrationResult",
        "GeneralDuplicationRule",
        "GeneralGoalClarificationRule",
        "GeneralPermissionRule",
        "GeneralSourceReliabilityRule",
        "GeneralTemporalValidityRule",
        "assemble_general_trace",
        "build_general_domain_definition",
        "build_general_goal_binding",
        "build_general_goal_proposal",
        "build_general_memory_view",
        "build_general_memory_view_request",
        "build_general_operation_definitions",
        "build_general_permission_policy",
        "build_general_presentation_policy",
        "build_general_profile",
        "build_general_resource_definitions",
        "build_general_rules",
        "build_general_task_binding",
        "build_general_task_proposal",
        "build_general_trace_contribution",
        "build_general_trace_reference",
        "build_general_workflow_definitions",
        "build_standard_general_domain_bootstrap",
        "register_general_domain",
        "validate_general_memory_binding",
        "validate_general_trace",
    }
    assert set(general.__all__) == expected


def test_no_private_exports():
    for name in general.__all__:
        assert not name.startswith("_")


def test_clean_import():
    import importlib

    module = importlib.import_module("cmm.domains.general")
    assert module is not None


def test_import_no_side_effects():
    import sys

    import cmm.domains.general  # noqa: F401

    after = set(sys.modules)
    # Importing should not register anything globally
    assert "cmm.domains.general" in after


def test_no_cycles():
    import cmm.domains
    import cmm.domains.general  # noqa: F401

    # Both should import without circular dependency errors
    assert True


def test_name_stability():
    assert general.GENERAL_DOMAIN_ID == "domain:general"
    assert general.GENERAL_PROFILE_NAME == "GeneralProfile"
    assert len(general.GENERAL_RESOURCE_IDS) == 9
    assert len(general.GENERAL_RULE_IDS) == 6
    assert len(general.GENERAL_OPERATION_IDS) == 8
    assert len(general.GENERAL_WORKFLOW_IDS) == 4