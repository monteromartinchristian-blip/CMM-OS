"""Tests for Phase 10.20 Health Domain structural definition."""

from __future__ import annotations

from cmm.domains import health
from cmm.domains.enums import DomainKind
from cmm.domains.health.catalog import (
    CANONICAL_HEALTH_ENTITY_TYPES,
    CANONICAL_HEALTH_OPERATION_IDS,
    CANONICAL_HEALTH_RESOURCE_IDS,
    CANONICAL_HEALTH_RULE_IDS,
    CANONICAL_HEALTH_WORKFLOW_IDS,
)


def test_definition_identity():
    definition = health.build_health_domain_definition()
    assert str(definition.id) == "domain:health"
    assert definition.version == "1.0.0"
    assert definition.kind is DomainKind.PERSONAL
    assert definition.reasoning_profile == "HealthProfile"
    assert definition.name == "health"


def test_manifest():
    definition = health.build_health_domain_definition()
    assert definition.manifest_id == "manifest:health:1.0.0"


def test_exact_structural_counts():
    assert len(CANONICAL_HEALTH_ENTITY_TYPES) == 15
    assert len(CANONICAL_HEALTH_RESOURCE_IDS) == 12
    assert len(CANONICAL_HEALTH_RULE_IDS) == 8
    assert len(CANONICAL_HEALTH_OPERATION_IDS) == 12
    assert len(CANONICAL_HEALTH_WORKFLOW_IDS) == 8


def test_built_definitions_match_catalog_counts():
    assert len(health.build_health_resource_definitions()) == 12
    assert len(health.build_health_rules()) == 8
    assert len(health.build_health_operation_definitions()) == 12
    assert len(health.build_health_workflow_definitions()) == 8


def test_catalog_ids_sorted():
    for ids in (
        CANONICAL_HEALTH_ENTITY_TYPES,
        CANONICAL_HEALTH_OPERATION_IDS,
        CANONICAL_HEALTH_RESOURCE_IDS,
        CANONICAL_HEALTH_RULE_IDS,
        CANONICAL_HEALTH_WORKFLOW_IDS,
    ):
        assert tuple(sorted(ids)) == ids


def test_definition_lists_reconcile_with_catalog():
    definition = health.build_health_domain_definition()
    assert tuple(definition.resources) == CANONICAL_HEALTH_RESOURCE_IDS
    assert tuple(definition.rules) == CANONICAL_HEALTH_RULE_IDS
    assert tuple(definition.operations) == CANONICAL_HEALTH_OPERATION_IDS
    assert tuple(definition.workflows) == CANONICAL_HEALTH_WORKFLOW_IDS


def test_capabilities_present():
    definition = health.build_health_domain_definition()
    capability_names = {cap.name for cap in definition.capabilities}
    assert {
        "health_timeline",
        "health_comparison",
        "health_summary",
        "health_questions",
        "health_escalation",
    } <= capability_names
