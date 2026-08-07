"""Tests for canonical catalog reconciliation of General Domain."""

from __future__ import annotations

from cmm.domains.general import (
    GENERAL_OPERATION_IDS,
    GENERAL_RESOURCE_IDS,
    GENERAL_RULE_IDS,
    GENERAL_WORKFLOW_IDS,
    build_standard_general_domain_bootstrap,
)
from cmm.domains.general.catalog import (
    CANONICAL_GENERAL_OPERATION_IDS,
    CANONICAL_GENERAL_RESOURCE_IDS,
    CANONICAL_GENERAL_RULE_IDS,
    CANONICAL_GENERAL_WORKFLOW_IDS,
)
from cmm.domains.operation_catalog import INITIAL_DOMAIN_OPERATION_IDS
from cmm.domains.rule_catalog import INITIAL_DOMAIN_REASONING_RULE_IDS


def test_canonical_operations_exact():
    """The canonical operation set contains exactly the 8 final operations."""
    assert len(CANONICAL_GENERAL_OPERATION_IDS) == 8
    assert set(CANONICAL_GENERAL_OPERATION_IDS) == set(GENERAL_OPERATION_IDS)


def test_canonical_rules_exact():
    """The canonical rule set contains exactly the 6 final rules."""
    assert len(CANONICAL_GENERAL_RULE_IDS) == 6
    assert set(CANONICAL_GENERAL_RULE_IDS) == set(GENERAL_RULE_IDS)


def test_canonical_resources_exact():
    """The canonical resource set contains exactly the 9 final resources."""
    assert len(CANONICAL_GENERAL_RESOURCE_IDS) == 9
    assert set(CANONICAL_GENERAL_RESOURCE_IDS) == set(GENERAL_RESOURCE_IDS)


def test_canonical_workflows_exact():
    """The canonical workflow set contains exactly the 4 final workflows."""
    assert len(CANONICAL_GENERAL_WORKFLOW_IDS) == 4
    assert set(CANONICAL_GENERAL_WORKFLOW_IDS) == set(GENERAL_WORKFLOW_IDS)


def test_no_duplicate_ids():
    """No duplicate IDs within any canonical set."""
    assert len(CANONICAL_GENERAL_OPERATION_IDS) == len(set(CANONICAL_GENERAL_OPERATION_IDS))
    assert len(CANONICAL_GENERAL_RULE_IDS) == len(set(CANONICAL_GENERAL_RULE_IDS))
    assert len(CANONICAL_GENERAL_RESOURCE_IDS) == len(set(CANONICAL_GENERAL_RESOURCE_IDS))
    assert len(CANONICAL_GENERAL_WORKFLOW_IDS) == len(set(CANONICAL_GENERAL_WORKFLOW_IDS))


def test_initial_operation_catalog_imports_canonical():
    """The initial operation catalog imports general.* IDs from the canonical source."""
    # The 4 historical general.* IDs in INITIAL_DOMAIN_OPERATION_IDS are placeholders
    # from Phase 10.13 with different semantics. They must not collide with the
    # 8 canonical Phase 10.19 operations.
    historical = {op for op in INITIAL_DOMAIN_OPERATION_IDS if op.startswith("general.")}
    canonical = set(CANONICAL_GENERAL_OPERATION_IDS)
    assert historical.isdisjoint(canonical), (
        f"Historical general.* IDs collide with canonical: {historical & canonical}"
    )


def test_initial_rule_catalog_has_no_general_rules():
    """The initial rule catalog has no general.* rules (no collision)."""
    historical = {r for r in INITIAL_DOMAIN_REASONING_RULE_IDS if r.startswith("general.")}
    assert historical == set(), f"Unexpected general.* rules in initial catalog: {historical}"


def test_bootstrap_exposes_same_sets():
    """Bootstrap and canonical catalog expose the same sets."""
    bootstrap = build_standard_general_domain_bootstrap()

    bootstrap_ops = {
        d.operation_id for d in bootstrap.operation_registry.list_definitions()
    }
    assert bootstrap_ops == set(CANONICAL_GENERAL_OPERATION_IDS)

    bootstrap_rules = {
        r.definition.id for r in bootstrap.rule_registry.list_all()
    }
    assert bootstrap_rules == set(CANONICAL_GENERAL_RULE_IDS)

    bootstrap_resources = {
        r.id for r in bootstrap.resource_registry.list_all()
    }
    assert bootstrap_resources == set(CANONICAL_GENERAL_RESOURCE_IDS)

    bootstrap_wf = {
        w.workflow_id
        for w in bootstrap.workflow_registry.list_for_domain("domain:general")
    }
    assert bootstrap_wf == set(CANONICAL_GENERAL_WORKFLOW_IDS)


def test_canonical_order_deterministic():
    """Canonical sets are in deterministic sorted order."""
    assert CANONICAL_GENERAL_OPERATION_IDS == tuple(sorted(CANONICAL_GENERAL_OPERATION_IDS))
    assert CANONICAL_GENERAL_RULE_IDS == tuple(sorted(CANONICAL_GENERAL_RULE_IDS))
    assert CANONICAL_GENERAL_RESOURCE_IDS == tuple(sorted(CANONICAL_GENERAL_RESOURCE_IDS))
    assert CANONICAL_GENERAL_WORKFLOW_IDS == tuple(sorted(CANONICAL_GENERAL_WORKFLOW_IDS))


def test_general_profile_is_canonical():
    """GeneralProfile is the canonical profile of the domain."""
    from cmm.domains.general import build_general_profile

    profile = build_general_profile()
    assert profile.profile_name == "GeneralProfile"
    assert profile.domain_id == "domain:general"


def test_import_no_side_effects():
    """Importing the package does not register anything."""
    import cmm.domains.general

    assert not hasattr(cmm.domains.general, "_GLOBAL_REGISTRIES")