"""Tests for Phase 10.29 Life Plan Domain Resources."""

from __future__ import annotations

from cmm.domains.life_plan.catalog import (
    CANONICAL_LIFE_PLAN_RESOURCE_IDS,
)
from cmm.domains.life_plan.resources import (
    build_life_plan_resource_definitions,
)


def test_life_plan_resource_definitions_count_and_order() -> None:
    resources = build_life_plan_resource_definitions()
    assert len(resources) == 12
    assert tuple(r.id for r in resources) == CANONICAL_LIFE_PLAN_RESOURCE_IDS
    assert all(r.domain_id == "domain:life-plan" for r in resources)


def test_life_plan_cross_domain_resources_purpose_minimized() -> None:
    resources = {r.id: r for r in build_life_plan_resource_definitions()}

    health_res = resources["life_plan.resource.health_constraints"]
    assert health_res.kind == "resource.health_constraints"
    assert health_res.metadata.get("health_projection_only") is True
    assert health_res.metadata.get("unrestricted_health_access") is not True

    acad_res = resources["life_plan.resource.academic_plan"]
    assert acad_res.kind == "resource.academic_plan"
    assert acad_res.metadata.get("minimized_projection_only") is True

    opp_res = resources["life_plan.resource.opposition_plan"]
    assert opp_res.kind == "resource.opposition_plan"
    assert opp_res.metadata.get("minimized_projection_only") is True

    fam_res = resources["life_plan.resource.family_plan"]
    assert fam_res.kind == "resource.family_plan"
    assert fam_res.metadata.get("minimized_projection_only") is True
