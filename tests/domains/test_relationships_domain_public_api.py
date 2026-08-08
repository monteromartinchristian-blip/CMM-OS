"""Tests for Phase 10.21 Relationships Domain public API (side-effect-free
import)."""

from __future__ import annotations

from cmm.domains import relationships


def test_expected_exports():
    expected = {
        "AmbivalencePreservationRule",
        "BoundaryConsistencyRule",
        "CANONICAL_RELATIONSHIPS_ENTITY_TYPES",
        "CANONICAL_RELATIONSHIPS_OPERATION_IDS",
        "CANONICAL_RELATIONSHIPS_RESOURCE_IDS",
        "CANONICAL_RELATIONSHIPS_RULE_IDS",
        "CANONICAL_RELATIONSHIPS_WORKFLOW_IDS",
        "DoNotInferIntentRule",
        "EmotionNeedDistinctionRule",
        "PatternWithoutCertaintyRule",
        "RELATIONSHIPS_DOMAIN_ID",
        "RELATIONSHIPS_DOMAIN_VERSION",
        "RELATIONSHIPS_MANIFEST_ID",
        "RELATIONSHIPS_OPERATION_IDS",
        "RELATIONSHIPS_PERMISSION_IDS",
        "RELATIONSHIPS_PERMISSION_POLICY_ID",
        "RELATIONSHIPS_PROFILE_ID",
        "RELATIONSHIPS_PROFILE_NAME",
        "RELATIONSHIPS_PROHIBITED_ACTIONS",
        "RELATIONSHIPS_RESOURCE_IDS",
        "RELATIONSHIPS_RESOURCE_KINDS",
        "RELATIONSHIPS_RULE_IDS",
        "RELATIONSHIPS_WORKFLOW_IDS",
        "RelationshipTimelineRule",
        "RelationshipsDomainBootstrap",
        "RelationshipsDomainIntegrationResult",
        "SelfOtherPerspectiveRule",
        "SeparateRelationshipFactInterpretationRule",
        "assemble_relationships_trace",
        "build_relationships_domain_definition",
        "build_relationships_memory_binding",
        "build_relationships_memory_proposal",
        "build_relationships_memory_view",
        "build_relationships_memory_view_request",
        "build_relationships_operation_definitions",
        "build_relationships_permission_policy",
        "build_relationships_presentation_policy",
        "build_relationships_profile",
        "build_relationships_resource_definitions",
        "build_relationships_rules",
        "build_relationships_trace_contribution",
        "build_relationships_trace_reference",
        "build_relationships_workflow_definitions",
        "build_standard_relationships_domain_bootstrap",
        "register_relationships_domain",
        "validate_relationships_memory_binding",
        "validate_relationships_trace",
    }
    assert set(relationships.__all__) == expected


def test_no_private_exports():
    for name in relationships.__all__:
        assert not name.startswith("_")


def test_import_no_side_effects():
    import importlib

    module = importlib.import_module("cmm.domains.relationships")
    assert module is not None


def test_clean_import_in_fresh_interpreter():
    """Importing cmm.domains.relationships from a clean interpreter has no side
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
        "import cmm.domains.relationships;"
        "assert not hasattr(cmm.domains.relationships, '_GLOBAL_REGISTRIES'), "
        "'cmm.domains.relationships must not create global registries on import'"
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
    import cmm.domains.relationships  # noqa: F401

    assert True


def test_name_stability():
    assert relationships.RELATIONSHIPS_DOMAIN_ID == "domain:relationships"
    assert relationships.RELATIONSHIPS_PROFILE_NAME == "RelationshipsProfile"
    assert relationships.RELATIONSHIPS_PROFILE_ID == "relationships.profile"
    assert len(relationships.RELATIONSHIPS_RESOURCE_IDS) == 8
    assert len(relationships.RELATIONSHIPS_RULE_IDS) == 8
    assert len(relationships.RELATIONSHIPS_OPERATION_IDS) == 10
    assert len(relationships.RELATIONSHIPS_WORKFLOW_IDS) == 6
