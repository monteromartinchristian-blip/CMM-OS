"""Tests for canonical catalog reconciliation of University Domain."""

from __future__ import annotations

from cmm.domains.university import (
    UNIVERSITY_OPERATION_IDS,
    UNIVERSITY_RESOURCE_IDS,
    UNIVERSITY_RULE_IDS,
    UNIVERSITY_WORKFLOW_IDS,
    build_standard_university_domain_bootstrap,
)
from cmm.domains.university.catalog import (
    CANONICAL_UNIVERSITY_ENTITY_TYPES,
    CANONICAL_UNIVERSITY_OPERATION_IDS,
    CANONICAL_UNIVERSITY_RESOURCE_IDS,
    CANONICAL_UNIVERSITY_RULE_IDS,
    CANONICAL_UNIVERSITY_WORKFLOW_IDS,
)


def test_canonical_entities_exact():
    """The canonical entity set contains exactly the 14 final entities."""
    assert len(CANONICAL_UNIVERSITY_ENTITY_TYPES) == 14
    assert len(set(CANONICAL_UNIVERSITY_ENTITY_TYPES)) == 14


def test_canonical_operations_exact():
    """The canonical operation set contains exactly the 11 final operations."""
    assert len(CANONICAL_UNIVERSITY_OPERATION_IDS) == 11
    assert set(CANONICAL_UNIVERSITY_OPERATION_IDS) == set(UNIVERSITY_OPERATION_IDS)


def test_canonical_rules_exact():
    """The canonical rule set contains exactly the 10 final rules."""
    assert len(CANONICAL_UNIVERSITY_RULE_IDS) == 10
    assert set(CANONICAL_UNIVERSITY_RULE_IDS) == set(UNIVERSITY_RULE_IDS)


def test_canonical_resources_exact():
    """The canonical resource set contains exactly the 12 final resources."""
    assert len(CANONICAL_UNIVERSITY_RESOURCE_IDS) == 12
    assert set(CANONICAL_UNIVERSITY_RESOURCE_IDS) == set(UNIVERSITY_RESOURCE_IDS)


def test_canonical_workflows_exact():
    """The canonical workflow set contains exactly the 7 final workflows."""
    assert len(CANONICAL_UNIVERSITY_WORKFLOW_IDS) == 7
    assert set(CANONICAL_UNIVERSITY_WORKFLOW_IDS) == set(UNIVERSITY_WORKFLOW_IDS)


def test_no_duplicate_ids():
    """No duplicate IDs within any canonical set."""
    assert len(CANONICAL_UNIVERSITY_OPERATION_IDS) == len(
        set(CANONICAL_UNIVERSITY_OPERATION_IDS)
    )
    assert len(CANONICAL_UNIVERSITY_RULE_IDS) == len(set(CANONICAL_UNIVERSITY_RULE_IDS))
    assert len(CANONICAL_UNIVERSITY_RESOURCE_IDS) == len(
        set(CANONICAL_UNIVERSITY_RESOURCE_IDS)
    )
    assert len(CANONICAL_UNIVERSITY_WORKFLOW_IDS) == len(
        set(CANONICAL_UNIVERSITY_WORKFLOW_IDS)
    )


def test_bootstrap_exposes_same_sets():
    """Bootstrap and canonical catalog expose the same sets."""
    bootstrap = build_standard_university_domain_bootstrap()

    bootstrap_ops = {
        d.operation_id
        for d in bootstrap.operation_registry.list_definitions()
        if d.domain_id == "domain:university"
    }
    assert bootstrap_ops == set(CANONICAL_UNIVERSITY_OPERATION_IDS)

    bootstrap_rules = {
        r.definition.id
        for r in bootstrap.rule_registry.list_all()
        if r.definition.domain_id == "domain:university"
    }
    assert bootstrap_rules == set(CANONICAL_UNIVERSITY_RULE_IDS)

    bootstrap_resources = {
        r.id
        for r in bootstrap.resource_registry.list_all()
        if r.domain_id == "domain:university"
    }
    assert bootstrap_resources == set(CANONICAL_UNIVERSITY_RESOURCE_IDS)

    bootstrap_wf = {
        w.workflow_id
        for w in bootstrap.workflow_registry.list_for_domain("domain:university")
    }
    assert bootstrap_wf == set(CANONICAL_UNIVERSITY_WORKFLOW_IDS)


def test_canonical_order_deterministic():
    """Canonical sets are in deterministic sorted order."""
    assert CANONICAL_UNIVERSITY_OPERATION_IDS == tuple(
        sorted(CANONICAL_UNIVERSITY_OPERATION_IDS)
    )
    assert CANONICAL_UNIVERSITY_RULE_IDS == tuple(sorted(CANONICAL_UNIVERSITY_RULE_IDS))
    assert CANONICAL_UNIVERSITY_RESOURCE_IDS == tuple(
        sorted(CANONICAL_UNIVERSITY_RESOURCE_IDS)
    )
    assert CANONICAL_UNIVERSITY_WORKFLOW_IDS == tuple(
        sorted(CANONICAL_UNIVERSITY_WORKFLOW_IDS)
    )


def test_university_profile_is_canonical():
    """UniversityProfile is the canonical profile of the domain."""
    from cmm.domains.university import build_university_profile

    profile = build_university_profile()
    assert profile.profile_name == "UniversityProfile"
    assert profile.domain_id == "domain:university"


def test_import_no_side_effects():
    """Importing the package does not register anything."""
    import cmm.domains.university

    assert not hasattr(cmm.domains.university, "_GLOBAL_REGISTRIES")
