"""Tests for Phase 10.28 Sport Domain Definition."""

from __future__ import annotations

from cmm.domains.enums import DomainKind
from cmm.domains.sport.definition import (
    SPORT_DOMAIN_ID,
    SPORT_DOMAIN_VERSION,
    SPORT_MANIFEST_ID,
    SPORT_PERMISSION_IDS,
    SPORT_PROFILE_NAME,
    build_sport_domain_definition,
)


def test_sport_domain_definition_properties() -> None:
    definition = build_sport_domain_definition()
    assert str(definition.id) == SPORT_DOMAIN_ID
    assert definition.name == "sport"
    assert definition.display_name == "Sport"
    assert definition.version == SPORT_DOMAIN_VERSION
    assert definition.kind == DomainKind.PERSONAL
    assert definition.manifest_id == SPORT_MANIFEST_ID
    assert definition.reasoning_profile == SPORT_PROFILE_NAME
    assert definition.permissions == SPORT_PERMISSION_IDS
    assert len(definition.capabilities) >= 5
    assert definition.enabled is True
