"""Tests for Phase 10.22 University Domain public API (side-effect-free
import)."""

from __future__ import annotations

from cmm.domains import university


def test_expected_exports():
    expected = {
        "AcademicContradictionRule",
        "AcademicDeadlineRule",
        "AcademicDecisionPreservationRule",
        "AcademicDependencyRule",
        "AcademicIntegrityRule",
        "AcademicSourceAuthorityRule",
        "AcademicWorkloadRule",
        "CANONICAL_UNIVERSITY_ENTITY_TYPES",
        "CANONICAL_UNIVERSITY_OPERATION_IDS",
        "CANONICAL_UNIVERSITY_RESOURCE_IDS",
        "CANONICAL_UNIVERSITY_RULE_IDS",
        "CANONICAL_UNIVERSITY_WORKFLOW_IDS",
        "EctsConsistencyRule",
        "ExamAttemptRule",
        "ObservedPerformanceCapacityRule",
        "UNIVERSITY_DOMAIN_ID",
        "UNIVERSITY_DOMAIN_VERSION",
        "UNIVERSITY_MANIFEST_ID",
        "UNIVERSITY_OPERATION_IDS",
        "UNIVERSITY_PERMISSION_IDS",
        "UNIVERSITY_PERMISSION_POLICY_ID",
        "UNIVERSITY_PROFILE_ID",
        "UNIVERSITY_PROFILE_NAME",
        "UNIVERSITY_PROHIBITED_ACTIONS",
        "UNIVERSITY_RESOURCE_IDS",
        "UNIVERSITY_RESOURCE_KINDS",
        "UNIVERSITY_RULE_IDS",
        "UNIVERSITY_WORKFLOW_IDS",
        "UniversityDomainBootstrap",
        "UniversityDomainIntegrationResult",
        "assemble_university_trace",
        "build_standard_university_domain_bootstrap",
        "build_university_domain_definition",
        "build_university_memory_binding",
        "build_university_memory_proposal",
        "build_university_memory_view",
        "build_university_memory_view_request",
        "build_university_operation_definitions",
        "build_university_permission_policy",
        "build_university_presentation_policy",
        "build_university_profile",
        "build_university_resource_definitions",
        "build_university_rules",
        "build_university_trace_contribution",
        "build_university_trace_reference",
        "build_university_workflow_definitions",
        "register_university_domain",
        "validate_university_memory_binding",
        "validate_university_trace",
    }
    assert set(university.__all__) == expected


def test_no_private_exports():
    for name in university.__all__:
        assert not name.startswith("_")


def test_import_no_side_effects():
    import importlib

    module = importlib.import_module("cmm.domains.university")
    assert module is not None


def test_clean_import_in_fresh_interpreter():
    """Importing cmm.domains.university from a clean interpreter has no side
    effects.

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
        "import cmm.domains.university;"
        "assert not hasattr(cmm.domains.university, '_GLOBAL_REGISTRIES'), "
        "'cmm.domains.university must not create global registries on import'"
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
    import cmm.domains.university  # noqa: F401

    assert True


def test_name_stability():
    assert university.UNIVERSITY_DOMAIN_ID == "domain:university"
    assert university.UNIVERSITY_PROFILE_NAME == "UniversityProfile"
    assert university.UNIVERSITY_PROFILE_ID == "university.profile"
    assert len(university.UNIVERSITY_RESOURCE_IDS) == 12
    assert len(university.UNIVERSITY_RULE_IDS) == 10
    assert len(university.UNIVERSITY_OPERATION_IDS) == 11
    assert len(university.UNIVERSITY_WORKFLOW_IDS) == 7
    assert len(university.CANONICAL_UNIVERSITY_ENTITY_TYPES) == 14