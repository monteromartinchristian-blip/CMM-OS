"""Phase 10.30 — Project Domain Cross-Domain & Life Plan Projection Tests."""

from __future__ import annotations

import pytest

from cmm.domains.project.catalog import PROJECT_DOMAIN_ID
from cmm.domains.project.rules import (
    ALLOWED_LIFE_PLAN_PROJECTION_FIELDS,
    PROHIBITED_LIFE_PLAN_PROJECTION_FIELDS,
    build_project_life_plan_projection,
)


def test_life_plan_projection_allows_purpose_minimized_fields() -> None:
    raw_payload = {
        "project_status_impact": "milestone_achieved",
        "timeline_impact": "2_weeks_ahead",
        "resource_impact": "none",
        "source_reference": "project:proj-001",
        "provenance": "project_domain_v1",
        "effective_from": "2026-09-01T00:00:00Z",
        "effective_until": "2026-10-01T00:00:00Z",
    }
    projection = build_project_life_plan_projection(raw_payload)
    assert projection["source_domain"] == PROJECT_DOMAIN_ID
    assert projection["project_status_impact"] == "milestone_achieved"
    assert projection["timeline_impact"] == "2_weeks_ahead"
    assert projection["source_reference"] == "project:proj-001"

    # All returned keys must be in ALLOWED_LIFE_PLAN_PROJECTION_FIELDS
    for k in projection:
        assert k in ALLOWED_LIFE_PLAN_PROJECTION_FIELDS


def test_life_plan_projection_fails_closed_on_prohibited_internals() -> None:
    for prohibited in PROHIBITED_LIFE_PLAN_PROJECTION_FIELDS:
        payload = {
            "project_status_impact": "on_track",
            prohibited: "internal_data_leak",
        }
        with pytest.raises(
            ValueError, match=f"Prohibited internal field '{prohibited}'"
        ):
            build_project_life_plan_projection(payload)


def test_formation_overlay_not_absorbed_in_project_domain() -> None:
    from cmm.domains.project.catalog import CANONICAL_PROJECT_ENTITY_IDS

    # Formation is a General domain overlay, not a Project domain entity
    assert "project.entity.formation" not in CANONICAL_PROJECT_ENTITY_IDS
    assert "project.formation" not in CANONICAL_PROJECT_ENTITY_IDS
