"""Tests for Phase 10.11 – Domain Profile Registry (Task 5)."""

from __future__ import annotations

from typing import runtime_checkable

import pytest

from cmm.domains.errors import DomainProfileRegistryError
from cmm.domains.identifiers import DomainId
from cmm.domains.profile_contracts import DomainProfileDefinition
from cmm.domains.profile_registry import (
    INITIAL_DOMAIN_PROFILE_NAMES,
    DomainProfileRegistry,
    InMemoryDomainProfileRegistry,
)


def _make_definition(**overrides) -> DomainProfileDefinition:
    defaults = {
        "id": "def-1",
        "domain_id": DomainId("health"),
        "profile_name": "HealthProfile",
    }
    defaults.update(overrides)
    return DomainProfileDefinition(**defaults)


def test_domain_profile_registry_is_runtime_checkable_protocol():
    assert runtime_checkable(DomainProfileRegistry) is DomainProfileRegistry
    registry = InMemoryDomainProfileRegistry()
    assert isinstance(registry, DomainProfileRegistry)


def test_initial_domain_profile_names_are_expected_set():
    assert INITIAL_DOMAIN_PROFILE_NAMES == (
        "GeneralProfile",
        "HealthProfile",
        "RelationshipProfile",
        "UniversityProfile",
        "OppositionProfile",
        "ReflectionProfile",
        "ConcernProfile",
        "LanguageProfile",
        "NilProfile",
        "SportProfile",
        "LifePlanProfile",
        "ProjectProfile",
    )


def test_register_rejects_duplicate_ids():
    registry = InMemoryDomainProfileRegistry()
    registry.register(_make_definition(domain_id=DomainId("health")))
    with pytest.raises(DomainProfileRegistryError):
        registry.register(_make_definition(domain_id=DomainId("university")))


def test_register_rejects_second_active_base_profile_for_same_domain():
    registry = InMemoryDomainProfileRegistry()
    registry.register(_make_definition(id="def-1", domain_id=DomainId("health")))
    with pytest.raises(DomainProfileRegistryError):
        registry.register(_make_definition(id="def-2", domain_id=DomainId("health")))


def test_register_allows_distinct_domains():
    registry = InMemoryDomainProfileRegistry()
    registry.register(_make_definition(id="def-1", domain_id=DomainId("health")))
    registry.register(_make_definition(id="def-2", domain_id=DomainId("university")))
    assert {d.id for d in registry.list_all()} == {"def-1", "def-2"}


def test_register_rejects_non_definition_input():
    registry = InMemoryDomainProfileRegistry()
    with pytest.raises(DomainProfileRegistryError):
        registry.register("not-a-definition")


def test_get_returns_none_for_unknown_id():
    registry = InMemoryDomainProfileRegistry()
    assert registry.get("missing") is None


def test_get_returns_registered_definition():
    registry = InMemoryDomainProfileRegistry()
    definition = registry.register(_make_definition())
    assert registry.get("def-1") is definition


def test_get_by_domain_returns_none_for_unknown_domain():
    registry = InMemoryDomainProfileRegistry()
    assert registry.get_by_domain(DomainId("health")) is None


def test_get_by_domain_returns_registered_definition():
    registry = InMemoryDomainProfileRegistry()
    definition = registry.register(_make_definition(domain_id=DomainId("health")))
    assert registry.get_by_domain(DomainId("health")) is definition


def test_list_all_orders_by_domain_slug_and_id():
    registry = InMemoryDomainProfileRegistry()
    registry.register(_make_definition(id="def-b", domain_id=DomainId("university")))
    registry.register(_make_definition(id="def-a", domain_id=DomainId("health")))
    matches = registry.list_all()
    assert [d.id for d in matches] == ["def-a", "def-b"]


def test_returned_tuples_are_immutable_and_isolated():
    registry = InMemoryDomainProfileRegistry()
    registry.register(_make_definition())
    result = registry.list_all()
    assert isinstance(result, tuple)
    with pytest.raises(TypeError):
        result[0] = None


def test_no_persistence_across_registry_instances():
    registry_one = InMemoryDomainProfileRegistry()
    registry_one.register(_make_definition())
    registry_two = InMemoryDomainProfileRegistry()
    assert registry_two.list_all() == ()
