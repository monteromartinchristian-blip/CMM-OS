"""Tests for Phase 10.21 Relationships Domain structural definition."""

from __future__ import annotations

from cmm.domains import relationships
from cmm.domains.enums import DomainKind
from cmm.domains.relationships.catalog import (
    CANONICAL_RELATIONSHIPS_ENTITY_TYPES,
    CANONICAL_RELATIONSHIPS_OPERATION_IDS,
    CANONICAL_RELATIONSHIPS_RESOURCE_IDS,
    CANONICAL_RELATIONSHIPS_RULE_IDS,
    CANONICAL_RELATIONSHIPS_WORKFLOW_IDS,
)


def test_definition_identity():
    definition = relationships.build_relationships_domain_definition()
    assert str(definition.id) == "domain:relationships"
    assert definition.version == "1.0.0"
    assert definition.kind is DomainKind.PERSONAL
    assert definition.reasoning_profile == "RelationshipsProfile"
    assert definition.name == "relationships"


def test_manifest():
    definition = relationships.build_relationships_domain_definition()
    assert definition.manifest_id == "manifest:relationships:1.0.0"


def test_exact_structural_counts():
    assert len(CANONICAL_RELATIONSHIPS_ENTITY_TYPES) == 13
    assert len(CANONICAL_RELATIONSHIPS_RESOURCE_IDS) == 8
    assert len(CANONICAL_RELATIONSHIPS_RULE_IDS) == 8
    assert len(CANONICAL_RELATIONSHIPS_OPERATION_IDS) == 10
    assert len(CANONICAL_RELATIONSHIPS_WORKFLOW_IDS) == 6


def test_built_definitions_match_catalog_counts():
    assert len(relationships.build_relationships_resource_definitions()) == 8
    assert len(relationships.build_relationships_rules()) == 8
    assert len(relationships.build_relationships_operation_definitions()) == 10
    assert len(relationships.build_relationships_workflow_definitions()) == 6


def test_catalog_ids_sorted():
    for ids in (
        CANONICAL_RELATIONSHIPS_ENTITY_TYPES,
        CANONICAL_RELATIONSHIPS_OPERATION_IDS,
        CANONICAL_RELATIONSHIPS_RESOURCE_IDS,
        CANONICAL_RELATIONSHIPS_RULE_IDS,
        CANONICAL_RELATIONSHIPS_WORKFLOW_IDS,
    ):
        assert tuple(sorted(ids)) == ids


def test_definition_lists_reconcile_with_catalog():
    definition = relationships.build_relationships_domain_definition()
    assert tuple(definition.resources) == CANONICAL_RELATIONSHIPS_RESOURCE_IDS
    assert tuple(definition.rules) == CANONICAL_RELATIONSHIPS_RULE_IDS
    assert tuple(definition.operations) == CANONICAL_RELATIONSHIPS_OPERATION_IDS
    assert tuple(definition.workflows) == CANONICAL_RELATIONSHIPS_WORKFLOW_IDS


def test_capabilities_present():
    definition = relationships.build_relationships_domain_definition()
    capability_names = {cap.name for cap in definition.capabilities}
    assert {
        "relationships_timeline",
        "relationships_analysis",
        "relationships_boundary",
        "relationships_preparation",
        "relationships_decision_support",
    } <= capability_names
