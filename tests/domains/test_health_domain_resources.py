"""Tests for Phase 10.20 Health Domain resources."""

from __future__ import annotations

from cmm.domains import health
from cmm.domains.health.catalog import CANONICAL_HEALTH_RESOURCE_IDS


def test_twelve_resources_and_sorted_ids():
    resources = health.build_health_resource_definitions()
    assert len(resources) == 12
    assert [r.id for r in resources] == list(CANONICAL_HEALTH_RESOURCE_IDS)


def test_all_high_sensitivity():
    from cmm.cognitive.enums import SensitivityLevel

    for resource in health.build_health_resource_definitions():
        assert resource.default_sensitivity is SensitivityLevel.HIGHLY_SENSITIVE


def test_domain_and_kind():
    for resource in health.build_health_resource_definitions():
        assert resource.domain_id == "domain:health"
        assert resource.kind == resource.id.split(".", 1)[1]


def test_entity_types_subset_of_catalog():
    from cmm.domains.health.catalog import CANONICAL_HEALTH_ENTITY_TYPES

    allowed = set(CANONICAL_HEALTH_ENTITY_TYPES)
    for resource in health.build_health_resource_definitions():
        assert set(resource.entity_types) <= allowed
