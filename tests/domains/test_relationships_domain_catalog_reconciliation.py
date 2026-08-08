"""Tests for canonical catalog reconciliation of Relationships Domain."""

from __future__ import annotations

from cmm.domains.relationships import (
    RELATIONSHIPS_OPERATION_IDS,
    RELATIONSHIPS_RESOURCE_IDS,
    RELATIONSHIPS_RULE_IDS,
    RELATIONSHIPS_WORKFLOW_IDS,
    build_standard_relationships_domain_bootstrap,
)
from cmm.domains.relationships.catalog import (
    CANONICAL_RELATIONSHIPS_OPERATION_IDS,
    CANONICAL_RELATIONSHIPS_RESOURCE_IDS,
    CANONICAL_RELATIONSHIPS_RULE_IDS,
    CANONICAL_RELATIONSHIPS_WORKFLOW_IDS,
)


def test_canonical_operations_exact():
    """The canonical operation set contains exactly the 10 final operations."""
    assert len(CANONICAL_RELATIONSHIPS_OPERATION_IDS) == 10
    assert set(CANONICAL_RELATIONSHIPS_OPERATION_IDS) == set(
        RELATIONSHIPS_OPERATION_IDS
    )


def test_canonical_rules_exact():
    """The canonical rule set contains exactly the 8 final rules."""
    assert len(CANONICAL_RELATIONSHIPS_RULE_IDS) == 8
    assert set(CANONICAL_RELATIONSHIPS_RULE_IDS) == set(RELATIONSHIPS_RULE_IDS)


def test_canonical_resources_exact():
    """The canonical resource set contains exactly the 8 final resources."""
    assert len(CANONICAL_RELATIONSHIPS_RESOURCE_IDS) == 8
    assert set(CANONICAL_RELATIONSHIPS_RESOURCE_IDS) == set(RELATIONSHIPS_RESOURCE_IDS)


def test_canonical_workflows_exact():
    """The canonical workflow set contains exactly the 6 final workflows."""
    assert len(CANONICAL_RELATIONSHIPS_WORKFLOW_IDS) == 6
    assert set(CANONICAL_RELATIONSHIPS_WORKFLOW_IDS) == set(RELATIONSHIPS_WORKFLOW_IDS)


def test_no_duplicate_ids():
    """No duplicate IDs within any canonical set."""
    assert len(CANONICAL_RELATIONSHIPS_OPERATION_IDS) == len(
        set(CANONICAL_RELATIONSHIPS_OPERATION_IDS)
    )
    assert len(CANONICAL_RELATIONSHIPS_RULE_IDS) == len(
        set(CANONICAL_RELATIONSHIPS_RULE_IDS)
    )
    assert len(CANONICAL_RELATIONSHIPS_RESOURCE_IDS) == len(
        set(CANONICAL_RELATIONSHIPS_RESOURCE_IDS)
    )
    assert len(CANONICAL_RELATIONSHIPS_WORKFLOW_IDS) == len(
        set(CANONICAL_RELATIONSHIPS_WORKFLOW_IDS)
    )


def test_bootstrap_exposes_same_sets():
    """Bootstrap and canonical catalog expose the same sets."""
    bootstrap = build_standard_relationships_domain_bootstrap()

    bootstrap_ops = {
        d.operation_id
        for d in bootstrap.operation_registry.list_definitions()
        if d.domain_id == "domain:relationships"
    }
    assert bootstrap_ops == set(CANONICAL_RELATIONSHIPS_OPERATION_IDS)

    bootstrap_rules = {
        r.definition.id
        for r in bootstrap.rule_registry.list_all()
        if r.definition.domain_id == "domain:relationships"
    }
    assert bootstrap_rules == set(CANONICAL_RELATIONSHIPS_RULE_IDS)

    bootstrap_resources = {
        r.id
        for r in bootstrap.resource_registry.list_all()
        if r.domain_id == "domain:relationships"
    }
    assert bootstrap_resources == set(CANONICAL_RELATIONSHIPS_RESOURCE_IDS)

    bootstrap_wf = {
        w.workflow_id
        for w in bootstrap.workflow_registry.list_for_domain("domain:relationships")
    }
    assert bootstrap_wf == set(CANONICAL_RELATIONSHIPS_WORKFLOW_IDS)


def test_canonical_order_deterministic():
    """Canonical sets are in deterministic sorted order."""
    assert CANONICAL_RELATIONSHIPS_OPERATION_IDS == tuple(
        sorted(CANONICAL_RELATIONSHIPS_OPERATION_IDS)
    )
    assert CANONICAL_RELATIONSHIPS_RULE_IDS == tuple(
        sorted(CANONICAL_RELATIONSHIPS_RULE_IDS)
    )
    assert CANONICAL_RELATIONSHIPS_RESOURCE_IDS == tuple(
        sorted(CANONICAL_RELATIONSHIPS_RESOURCE_IDS)
    )
    assert CANONICAL_RELATIONSHIPS_WORKFLOW_IDS == tuple(
        sorted(CANONICAL_RELATIONSHIPS_WORKFLOW_IDS)
    )


def test_relationships_profile_is_canonical():
    """RelationshipsProfile is the canonical profile of the domain."""
    from cmm.domains.relationships import build_relationships_profile

    profile = build_relationships_profile()
    assert profile.profile_name == "RelationshipsProfile"
    assert profile.domain_id == "domain:relationships"


def test_import_no_side_effects():
    """Importing the package does not register anything."""
    import cmm.domains.relationships

    assert not hasattr(cmm.domains.relationships, "_GLOBAL_REGISTRIES")
