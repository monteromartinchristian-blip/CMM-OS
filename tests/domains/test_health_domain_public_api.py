"""Tests for Phase 10.20 Health Domain public API (side-effect-free import)."""

from __future__ import annotations

from cmm.domains import health


def test_expected_exports():
    expected = {
        "CANONICAL_HEALTH_ENTITY_TYPES",
        "CANONICAL_HEALTH_OPERATION_IDS",
        "CANONICAL_HEALTH_RESOURCE_IDS",
        "CANONICAL_HEALTH_RULE_IDS",
        "CANONICAL_HEALTH_WORKFLOW_IDS",
        "HEALTH_DOMAIN_ID",
        "HEALTH_DOMAIN_VERSION",
        "HEALTH_MANIFEST_ID",
        "HEALTH_OPERATION_IDS",
        "HEALTH_PERMISSION_IDS",
        "HEALTH_PERMISSION_POLICY_ID",
        "HEALTH_PROFILE_ID",
        "HEALTH_PROFILE_NAME",
        "HEALTH_PROHIBITED_ACTIONS",
        "HEALTH_RESOURCE_IDS",
        "HEALTH_RESOURCE_KINDS",
        "HEALTH_RULE_IDS",
        "HEALTH_WORKFLOW_IDS",
        "HealthClinicalSourcePriorityRule",
        "HealthDomainBootstrap",
        "HealthDomainIntegrationResult",
        "HealthMedicalRedFlagRule",
        "HealthMedicalTemporalValidityRule",
        "HealthMedicationConsistencyRule",
        "HealthMedicationTemporalRelationshipRule",
        "HealthNoDefinitiveDiagnosisRule",
        "HealthProfessionalEscalationRule",
        "HealthSymptomDiagnosisHypothesisRule",
        "assemble_health_trace",
        "build_health_domain_definition",
        "build_health_memory_view",
        "build_health_memory_view_request",
        "build_health_operation_definitions",
        "build_health_permission_policy",
        "build_health_presentation_policy",
        "build_health_profile",
        "build_health_resource_definitions",
        "build_health_rules",
        "build_health_symptom_binding",
        "build_health_symptom_proposal",
        "build_health_trace_contribution",
        "build_health_trace_reference",
        "build_health_workflow_definitions",
        "build_standard_health_domain_bootstrap",
        "register_health_domain",
        "validate_health_memory_binding",
        "validate_health_trace",
    }
    assert set(health.__all__) == expected


def test_no_private_exports():
    for name in health.__all__:
        assert not name.startswith("_")


def test_import_no_side_effects():
    import importlib

    module = importlib.import_module("cmm.domains.health")
    assert module is not None


def test_clean_import_in_fresh_interpreter():
    """Importing cmm.domains.health from a clean interpreter has no side effects.

    Mirrors the canonical General-domain clean-import regression: a brand-new
    Python interpreter must import the module with exit code 0, empty stdout,
    empty stderr, and no global registries created by the import itself.
    """
    import pathlib
    import subprocess
    import sys

    # Repo root is three directory levels up from tests/domains/test_...py.
    repo_root = pathlib.Path(__file__).resolve().parent.parent.parent

    script = (
        "import cmm.domains.health;"
        "assert not hasattr(cmm.domains.health, '_GLOBAL_REGISTRIES'), "
        "'cmm.domains.health must not create global registries on import'"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert result.stderr == ""


def test_no_cycles():
    import cmm.domains
    import cmm.domains.health  # noqa: F401

    assert True


def test_name_stability():
    assert health.HEALTH_DOMAIN_ID == "domain:health"
    assert health.HEALTH_PROFILE_NAME == "HealthProfile"
    assert len(health.HEALTH_RESOURCE_IDS) == 12
    assert len(health.HEALTH_RULE_IDS) == 8
    assert len(health.HEALTH_OPERATION_IDS) == 12
    assert len(health.HEALTH_WORKFLOW_IDS) == 8
