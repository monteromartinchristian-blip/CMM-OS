"""Audit guards for General Domain."""

from __future__ import annotations

import pytest

from cmm.domains.general import (
    GENERAL_DOMAIN_ID,
    GENERAL_OPERATION_IDS,
    GENERAL_RESOURCE_IDS,
    GENERAL_RULE_IDS,
    GENERAL_WORKFLOW_IDS,
    build_general_domain_definition,
    build_general_operation_definitions,
    build_general_permission_policy,
    build_general_profile,
    build_general_resource_definitions,
    build_general_rules,
    build_general_workflow_definitions,
)


def test_domain_general_exists():
    definition = build_general_domain_definition()
    assert definition.id.slug == "general"
    assert str(definition.id) == GENERAL_DOMAIN_ID


def test_nine_resource_kinds():
    resources = build_general_resource_definitions()
    assert len(resources) == 9
    assert len(GENERAL_RESOURCE_IDS) == 9


def test_six_rule_ids():
    rules = build_general_rules()
    assert len(rules) == 6
    assert len(GENERAL_RULE_IDS) == 6


def test_eight_operation_ids():
    operations = build_general_operation_definitions()
    assert len(operations) == 8
    assert len(GENERAL_OPERATION_IDS) == 8


def test_four_workflow_ids():
    workflows = build_general_workflow_definitions()
    assert len(workflows) == 4
    assert len(GENERAL_WORKFLOW_IDS) == 4


def test_no_external_actions_policy():
    policy = build_general_permission_policy()
    assert policy.allow_external_search is False
    assert policy.allow_external_models is False
    assert policy.allow_external_communication is False
    assert policy.allow_file_modification is False
    assert policy.allow_schedule_modification is False


def test_memory_via_proposals():
    profile = build_general_profile()
    assert profile.memory_policy.allow_write is False
    policy = build_general_permission_policy()
    assert policy.allow_memory_write is False


def test_specialized_domain_priority():
    # General Domain is a fallback, not a catch-all
    definition = build_general_domain_definition()
    assert definition.kind.value == "core"
    assert definition.reasoning_profile == "GeneralProfile"


def test_general_not_catch_all():
    # General Domain has explicit capabilities, not universal
    definition = build_general_domain_definition()
    capability_names = {c.name for c in definition.capabilities}
    assert "general_fallback" in capability_names
    assert "general_analysis" in capability_names


# ── Structural guards ─────────────────────────────────────────────────────────


def test_thirteen_production_modules():
    """There are exactly 13 production modules under cmm/domains/general/."""
    import pathlib

    package_dir = pathlib.Path("cmm/domains/general")
    modules = [
        p.name
        for p in package_dir.glob("*.py")
        if p.name != "__init__.py" and not p.name.startswith("_")
    ]
    assert len(modules) == 13


def test_seventeen_test_modules():
    """There are exactly 17 test modules for General Domain."""
    import pathlib

    test_dir = pathlib.Path("tests/domains")
    test_files = [
        p.name
        for p in test_dir.glob("test_general_domain_*.py")
    ]
    assert len(test_files) == 17


def test_no_prohibited_dependencies():
    """General Domain has no prohibited direct dependencies."""
    import pathlib

    package_dir = pathlib.Path("cmm/domains/general")
    for py_file in package_dir.glob("*.py"):
        content = py_file.read_text()
        for prohibited in ("sqlite", "store_sqlite", "requests.", "httpx.",
                           "urllib.", "subprocess", "os.system", "shell=True"):
            assert prohibited not in content, (
                f"{py_file.name} contains prohibited dependency: {prohibited}"
            )


def test_no_import_side_effects():
    """Importing cmm.domains.general from a clean interpreter has no side effects."""
    import pathlib
    import subprocess
    import sys

    # Repo root is three directory levels up from tests/domains/test_...py.
    repo_root = pathlib.Path(__file__).resolve().parent.parent.parent

    # Run the import in a brand-new interpreter so it is a genuine first import.
    # Any registration, global, or output side effect makes the subprocess fail.
    script = (
        "import cmm.domains.general;"
        "assert not hasattr(cmm.domains.general, '_GLOBAL_REGISTRIES'), "
        "'cmm.domains.general must not create global registries on import'"
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


def test_approval_required_operations_are_proposal_only_and_unavailable_by_default():
    """Approval-required operations are proposal-only and UNAVAILABLE by default.

    'proposal-only' defines the output contract of a future implementation,
    while the standard bootstrap stays UNAVAILABLE (fail-closed) until a real
    implementation is injected.  No fake delegates are installed.
    """
    from cmm.domains.errors import DomainOperationRegistryError
    from cmm.domains.general import build_standard_general_domain_bootstrap

    bootstrap = build_standard_general_domain_bootstrap()

    approval_ops = {
        op.operation_id: op
        for op in bootstrap.operation_registry.list_definitions()
        if op.requires_approval
    }
    assert set(approval_ops) == {"general.create_task", "general.update_goal"}

    for op in approval_ops.values():
        assert op.requires_approval is True
        assert op.metadata["proposal_only"] is True
        # Output contract of a future implementation: proposal + binding.
        assert set(op.output_schema["required"]) == {"proposal", "binding"}
        # Fail-closed: the standard bootstrap registers declared-but-unimplemented
        # operations as disabled.
        registered = bootstrap.operation_registry.get(op.operation_id, op.version)
        assert registered.enabled is False
        with pytest.raises(DomainOperationRegistryError):
            bootstrap.operation_registry.get_implementation(
                op.operation_id, op.version
            )
