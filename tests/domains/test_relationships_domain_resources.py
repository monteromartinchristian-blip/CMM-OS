"""Tests for Phase 10.21 Relationships Domain resources."""

from __future__ import annotations

from cmm.domains import relationships
from cmm.domains.relationships.catalog import CANONICAL_RELATIONSHIPS_RESOURCE_IDS


def test_eight_resources_and_sorted_ids():
    resources = relationships.build_relationships_resource_definitions()
    assert len(resources) == 8
    assert [r.id for r in resources] == list(CANONICAL_RELATIONSHIPS_RESOURCE_IDS)


def test_all_high_sensitivity():
    from cmm.cognitive.enums import SensitivityLevel

    for resource in relationships.build_relationships_resource_definitions():
        assert resource.default_sensitivity is SensitivityLevel.HIGHLY_SENSITIVE


def test_domain_and_kind():
    for resource in relationships.build_relationships_resource_definitions():
        assert resource.domain_id == "domain:relationships"
        assert resource.kind == resource.id.split(".", 1)[1]


def test_entity_types_subset_of_catalog():
    from cmm.domains.relationships.catalog import CANONICAL_RELATIONSHIPS_ENTITY_TYPES

    allowed = set(CANONICAL_RELATIONSHIPS_ENTITY_TYPES)
    for resource in relationships.build_relationships_resource_definitions():
        assert set(resource.entity_types) <= allowed


def test_communication_resource_no_authorization_send():
    """relationships.communication represents an existing communication context;
    it must never authorize sending."""
    resources = {
        r.id: r for r in relationships.build_relationships_resource_definitions()
    }
    communication = resources["relationships.communication"]
    assert communication.metadata.get("no_authorization_send") is True
    assert communication.metadata.get("communication_context") is True
