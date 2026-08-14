"""Tests for canonical catalog reconciliation of the Opposition Domain."""

from __future__ import annotations

from cmm.domains.oppositions import (
    OPPOSITIONS_OPERATION_IDS,
    OPPOSITIONS_RESOURCE_IDS,
    OPPOSITIONS_RULE_IDS,
    OPPOSITIONS_WORKFLOW_IDS,
    build_standard_oppositions_domain_bootstrap,
)
from cmm.domains.oppositions.catalog import (
    CANONICAL_OPPOSITION_ENTITY_TYPES,
    CANONICAL_OPPOSITION_OPERATION_IDS,
    CANONICAL_OPPOSITION_RESOURCE_IDS,
    CANONICAL_OPPOSITION_RULE_IDS,
    CANONICAL_OPPOSITION_WORKFLOW_IDS,
)


def test_canonical_entities_exact():
    """The canonical entity set contains exactly the 14 final entities."""
    assert len(CANONICAL_OPPOSITION_ENTITY_TYPES) == 14
    assert len(set(CANONICAL_OPPOSITION_ENTITY_TYPES)) == 14


def test_canonical_operations_exact():
    """The canonical operation set contains exactly the 10 final operations."""
    assert len(CANONICAL_OPPOSITION_OPERATION_IDS) == 10
    assert set(CANONICAL_OPPOSITION_OPERATION_IDS) == set(OPPOSITIONS_OPERATION_IDS)


def test_canonical_rules_exact():
    """The canonical rule set contains exactly the 6 final rules."""
    assert len(CANONICAL_OPPOSITION_RULE_IDS) == 6
    assert set(CANONICAL_OPPOSITION_RULE_IDS) == set(OPPOSITIONS_RULE_IDS)


def test_canonical_resources_exact():
    """The canonical resource set contains exactly the 11 final resources."""
    assert len(CANONICAL_OPPOSITION_RESOURCE_IDS) == 11
    assert set(CANONICAL_OPPOSITION_RESOURCE_IDS) == set(OPPOSITIONS_RESOURCE_IDS)


def test_canonical_workflows_exact():
    """The canonical workflow set contains exactly the 7 final workflows."""
    assert len(CANONICAL_OPPOSITION_WORKFLOW_IDS) == 7
    assert set(CANONICAL_OPPOSITION_WORKFLOW_IDS) == set(OPPOSITIONS_WORKFLOW_IDS)


def test_no_duplicate_ids():
    """No duplicate IDs within any canonical set."""
    assert len(CANONICAL_OPPOSITION_OPERATION_IDS) == len(
        set(CANONICAL_OPPOSITION_OPERATION_IDS)
    )
    assert len(CANONICAL_OPPOSITION_RULE_IDS) == len(
        set(CANONICAL_OPPOSITION_RULE_IDS)
    )
    assert len(CANONICAL_OPPOSITION_RESOURCE_IDS) == len(
        set(CANONICAL_OPPOSITION_RESOURCE_IDS)
    )
    assert len(CANONICAL_OPPOSITION_WORKFLOW_IDS) == len(
        set(CANONICAL_OPPOSITION_WORKFLOW_IDS)
    )


def test_bootstrap_exposes_same_sets():
    """Bootstrap and canonical catalog expose the same sets."""
    bootstrap = build_standard_oppositions_domain_bootstrap()

    bootstrap_ops = {
        d.operation_id
        for d in bootstrap.operation_registry.list_definitions()
        if d.domain_id == "domain:oppositions"
    }
    assert bootstrap_ops == set(CANONICAL_OPPOSITION_OPERATION_IDS)

    bootstrap_rules = {
        r.definition.id
        for r in bootstrap.rule_registry.list_all()
        if r.definition.domain_id == "domain:oppositions"
    }
    assert bootstrap_rules == set(CANONICAL_OPPOSITION_RULE_IDS)

    bootstrap_resources = {
        r.id
        for r in bootstrap.resource_registry.list_all()
        if r.domain_id == "domain:oppositions"
    }
    assert bootstrap_resources == set(CANONICAL_OPPOSITION_RESOURCE_IDS)

    bootstrap_wf = {
        w.workflow_id
        for w in bootstrap.workflow_registry.list_for_domain("domain:oppositions")
    }
    assert bootstrap_wf == set(CANONICAL_OPPOSITION_WORKFLOW_IDS)


def test_canonical_order_deterministic():
    """Canonical sets are in deterministic sorted order."""
    assert CANONICAL_OPPOSITION_OPERATION_IDS == tuple(
        sorted(CANONICAL_OPPOSITION_OPERATION_IDS)
    )
    assert CANONICAL_OPPOSITION_RULE_IDS == tuple(
        sorted(CANONICAL_OPPOSITION_RULE_IDS)
    )
    assert CANONICAL_OPPOSITION_RESOURCE_IDS == tuple(
        sorted(CANONICAL_OPPOSITION_RESOURCE_IDS)
    )
    assert CANONICAL_OPPOSITION_WORKFLOW_IDS == tuple(
        sorted(CANONICAL_OPPOSITION_WORKFLOW_IDS)
    )


def test_oppositions_profile_is_canonical():
    """OppositionProfile is the canonical profile of the domain."""
    from cmm.domains.oppositions import build_oppositions_profile

    profile = build_oppositions_profile()
    assert profile.profile_name == "OppositionProfile"
    assert profile.domain_id == "domain:oppositions"


def test_operation_ids_exact_names():
    """The 10 canonical operations are exactly the frozen set."""
    assert set(CANONICAL_OPPOSITION_OPERATION_IDS) == {
        "oppositions.create_study_plan",
        "oppositions.divide_syllabus",
        "oppositions.track_progress",
        "oppositions.review_mock_exam",
        "oppositions.compare_bodies",
        "oppositions.review_call",
        "oppositions.generate_weekly_review",
        "oppositions.identify_risks",
        "oppositions.generate_revision_plan",
        "oppositions.update_progress",
    }


def test_workflow_ids_exact_names():
    """The 7 canonical workflows are exactly the frozen conceptual set."""
    assert set(CANONICAL_OPPOSITION_WORKFLOW_IDS) == {
        "oppositions.setup",
        "oppositions.weekly_review",
        "oppositions.mock_exam_review",
        "oppositions.call_analysis",
        "oppositions.syllabus_revision",
        "oppositions.alternative_route_comparison",
        "oppositions.exam_readiness",
    }


def test_rule_ids_exact_names():
    """The 6 canonical rules are exactly the frozen set."""
    assert set(CANONICAL_OPPOSITION_RULE_IDS) == {
        "oppositions.official_call_priority",
        "oppositions.temporal_validity",
        "oppositions.syllabus_coverage",
        "oppositions.study_feasibility",
        "oppositions.mock_exam_interpretation",
        "oppositions.alternative_route",
    }


def test_resource_ids_exact_names():
    """The 11 canonical resources are exactly the frozen set."""
    assert set(CANONICAL_OPPOSITION_RESOURCE_IDS) == {
        "oppositions.official_call",
        "oppositions.syllabus",
        "oppositions.regulation",
        "oppositions.study_plan",
        "oppositions.mock_exam",
        "oppositions.score_record",
        "oppositions.calendar_event",
        "oppositions.note",
        "oppositions.user_message",
        "oppositions.external_official_source",
        "oppositions.memory_entry",
    }