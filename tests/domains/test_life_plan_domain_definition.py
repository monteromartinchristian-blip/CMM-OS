"""Tests for Phase 10.29 Life Plan Domain Definition."""

from __future__ import annotations

from cmm.domains.enums import DomainKind
from cmm.domains.life_plan.definition import (
    LIFE_PLAN_DOMAIN_ID,
    LIFE_PLAN_DOMAIN_VERSION,
    LIFE_PLAN_MANIFEST_ID,
    LIFE_PLAN_PERMISSION_IDS,
    LIFE_PLAN_PROFILE_NAME,
    build_life_plan_domain_definition,
)


def test_life_plan_domain_definition_properties() -> None:
    definition = build_life_plan_domain_definition()
    assert str(definition.id) == LIFE_PLAN_DOMAIN_ID
    assert definition.name == "life-plan"
    assert definition.display_name == "Life Plan"
    assert definition.version == LIFE_PLAN_DOMAIN_VERSION
    assert definition.kind == DomainKind.PERSONAL
    assert definition.manifest_id == LIFE_PLAN_MANIFEST_ID
    assert definition.reasoning_profile == LIFE_PLAN_PROFILE_NAME
    assert definition.permissions == LIFE_PLAN_PERMISSION_IDS
    assert len(definition.capabilities) == 10
    assert definition.enabled is True
    assert definition.metadata.metadata["phase"] == "10.29"
