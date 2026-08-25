"""Tests for Phase 10.28 Sport Domain Resources."""

from __future__ import annotations

from cmm.domains.sport.catalog import (
    CANONICAL_SPORT_RESOURCE_IDS,
    SPORT_RESOURCE_KINDS,
)
from cmm.domains.sport.resources import (
    build_sport_resource_definitions,
)


def test_sport_resource_definitions_count_and_order() -> None:
    resources = build_sport_resource_definitions()
    assert len(resources) == 9
    assert tuple(r.id for r in resources) == CANONICAL_SPORT_RESOURCE_IDS
    assert all(r.domain_id == "domain:sport" for r in resources)


def test_health_resource_restriction() -> None:
    resources = {r.id: r for r in build_sport_resource_definitions()}
    health_res = resources["sport.resource.health_resource"]
    assert health_res.kind == "resource.health_resource"
    assert health_res.metadata.get("health_projection_only") is True
    assert health_res.metadata.get("unrestricted_health_access") is not True
