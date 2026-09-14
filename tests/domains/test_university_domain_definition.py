"""Tests for Phase 10.22 University Domain structural definition."""

from __future__ import annotations

from cmm.domains import university
from cmm.domains.enums import DomainKind
from cmm.domains.university.catalog import (
    CANONICAL_UNIVERSITY_ENTITY_TYPES,
    CANONICAL_UNIVERSITY_OPERATION_IDS,
    CANONICAL_UNIVERSITY_RESOURCE_IDS,
    CANONICAL_UNIVERSITY_RULE_IDS,
    CANONICAL_UNIVERSITY_WORKFLOW_IDS,
)


def test_definition_identity():
    definition = university.build_university_domain_definition()
    assert str(definition.id) == "domain:university"
    assert definition.version == "1.0.0"
    assert definition.kind is DomainKind.PERSONAL
    assert definition.reasoning_profile == "UniversityProfile"
    assert definition.name == "university"


def test_manifest():
    definition = university.build_university_domain_definition()
    assert definition.manifest_id == "manifest:university:1.0.0"


def test_exact_structural_counts():
    assert len(CANONICAL_UNIVERSITY_ENTITY_TYPES) == 14
    assert len(CANONICAL_UNIVERSITY_RESOURCE_IDS) == 12
    assert len(CANONICAL_UNIVERSITY_RULE_IDS) == 10
    assert len(CANONICAL_UNIVERSITY_OPERATION_IDS) == 11
    assert len(CANONICAL_UNIVERSITY_WORKFLOW_IDS) == 7


def test_built_definitions_match_catalog_counts():
    assert len(university.build_university_resource_definitions()) == 12
    assert len(university.build_university_rules()) == 10
    assert len(university.build_university_operation_definitions()) == 11
    assert len(university.build_university_workflow_definitions()) == 7


def test_catalog_ids_sorted():
    for ids in (
        CANONICAL_UNIVERSITY_ENTITY_TYPES,
        CANONICAL_UNIVERSITY_OPERATION_IDS,
        CANONICAL_UNIVERSITY_RESOURCE_IDS,
        CANONICAL_UNIVERSITY_RULE_IDS,
        CANONICAL_UNIVERSITY_WORKFLOW_IDS,
    ):
        assert tuple(sorted(ids)) == ids


def test_definition_lists_reconcile_with_catalog():
    definition = university.build_university_domain_definition()
    assert tuple(definition.resources) == CANONICAL_UNIVERSITY_RESOURCE_IDS
    assert tuple(definition.rules) == CANONICAL_UNIVERSITY_RULE_IDS
    assert tuple(definition.operations) == CANONICAL_UNIVERSITY_OPERATION_IDS
    assert tuple(definition.workflows) == CANONICAL_UNIVERSITY_WORKFLOW_IDS


def test_capabilities_present():
    definition = university.build_university_domain_definition()
    capability_names = {cap.name for cap in definition.capabilities}
    assert {
        "university_academic_record",
        "university_planning",
        "university_preparation",
        "university_deadline_tracking",
        "university_decision_support",
    } <= capability_names
