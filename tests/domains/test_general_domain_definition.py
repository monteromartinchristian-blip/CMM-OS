"""Tests for General Domain definition, manifest, and pack."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind
from cmm.domains.general import (
    GENERAL_DOMAIN_ID,
    GENERAL_MANIFEST_ID,
    GENERAL_OPERATION_IDS,
    GENERAL_RESOURCE_IDS,
    GENERAL_RULE_IDS,
    GENERAL_WORKFLOW_IDS,
    build_general_domain_definition,
)
from cmm.domains.identifiers import DomainId


def test_domain_id_is_valid():
    domain_id = DomainId.from_str(GENERAL_DOMAIN_ID)
    assert domain_id.slug == "general"


def test_definition_is_frozen():
    definition = build_general_domain_definition()
    with pytest.raises(FrozenInstanceError):
        definition.name = "changed"  # type: ignore[misc]


def test_version_is_valid_semver():
    definition = build_general_domain_definition()
    assert definition.version == "1.0.0"


def test_kind_uses_real_enum():
    definition = build_general_domain_definition()
    assert definition.kind is DomainKind.CORE


def test_no_duplicate_ids():
    definition = build_general_domain_definition()
    assert len(set(definition.resources)) == len(definition.resources)
    assert len(set(definition.rules)) == len(definition.rules)
    assert len(set(definition.operations)) == len(definition.operations)
    assert len(set(definition.workflows)) == len(definition.workflows)


def test_construction_is_deterministic():
    a = build_general_domain_definition()
    b = build_general_domain_definition()
    assert a == b
    assert a.to_dict() == b.to_dict()


def test_manifest_id_matches():
    definition = build_general_domain_definition()
    assert str(definition.manifest_id) == GENERAL_MANIFEST_ID
    assert definition.manifest_id.slug == "general"
    assert definition.manifest_id.version == "1.0.0"


def test_definition_round_trip():
    definition = build_general_domain_definition()
    restored = DomainDefinition.from_dict(definition.to_dict())
    assert restored == definition


def test_definition_has_expected_ids():
    definition = build_general_domain_definition()
    assert definition.id.slug == "general"
    assert definition.name == "general"
    assert definition.reasoning_profile == "GeneralProfile"
    assert definition.resources == GENERAL_RESOURCE_IDS
    assert definition.rules == GENERAL_RULE_IDS
    assert definition.operations == GENERAL_OPERATION_IDS
    assert definition.workflows == GENERAL_WORKFLOW_IDS


def test_definition_can_be_registered():
    from cmm.domains.registry import DomainRegistry

    registry = DomainRegistry()
    definition = build_general_domain_definition()
    registered = registry.register(definition)
    assert registered.id == definition.id
    assert registered.version == definition.version
    assert registry.get("domain:general") is not None


def test_repeated_registration_is_idempotent():
    from cmm.domains.registry import DomainRegistry

    registry = DomainRegistry()
    definition = build_general_domain_definition()
    registry.register(definition)
    result = registry.register(definition)
    assert result.id == definition.id
    assert result.version == definition.version


def test_no_side_effects_on_import():
    import sys

    import cmm.domains.general  # noqa: F401

    after = set(sys.modules)
    # Importing the package should not register anything globally
    assert "cmm.domains.general" in after
