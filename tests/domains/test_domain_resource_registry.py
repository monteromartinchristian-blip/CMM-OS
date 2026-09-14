"""Tests for Phase 10.10 – Domain Resource Registry (Task 6)."""

from __future__ import annotations

from typing import runtime_checkable

import pytest

from cmm.domains.errors import DomainResourceRegistryError
from cmm.domains.identifiers import DomainId
from cmm.domains.resource_contracts import DomainResourceDefinition
from cmm.domains.resource_registry import (
    DomainResourceRegistry,
    InMemoryDomainResourceRegistry,
)


def _make_definition(**overrides) -> DomainResourceDefinition:
    defaults = {
        "id": "def-1",
        "kind": "calendar-event",
        "domain_id": DomainId("health"),
        "adapter": "health.calendar",
    }
    defaults.update(overrides)
    return DomainResourceDefinition(**defaults)


def test_domain_resource_registry_is_runtime_checkable_protocol():
    assert runtime_checkable(DomainResourceRegistry) is DomainResourceRegistry
    registry = InMemoryDomainResourceRegistry()
    assert isinstance(registry, DomainResourceRegistry)


def test_register_rejects_duplicate_ids():
    registry = InMemoryDomainResourceRegistry()
    registry.register(_make_definition())
    with pytest.raises(DomainResourceRegistryError):
        registry.register(_make_definition())


def test_register_allows_same_kind_across_domains():
    registry = InMemoryDomainResourceRegistry()
    registry.register(_make_definition(id="def-health", domain_id=DomainId("health")))
    registry.register(
        _make_definition(id="def-university", domain_id=DomainId("university"))
    )
    matches = registry.find_by_kind("calendar-event")
    assert {d.id for d in matches} == {"def-health", "def-university"}


def test_get_returns_none_for_unknown_id():
    registry = InMemoryDomainResourceRegistry()
    assert registry.get("missing") is None


def test_get_returns_registered_definition():
    registry = InMemoryDomainResourceRegistry()
    definition = registry.register(_make_definition())
    assert registry.get("def-1") is definition


def test_find_by_kind_orders_by_priority_domain_and_id():
    registry = InMemoryDomainResourceRegistry()
    registry.register(
        _make_definition(
            id="def-b", domain_id=DomainId("university"), source_priority=5
        )
    )
    registry.register(
        _make_definition(id="def-a", domain_id=DomainId("health"), source_priority=5)
    )
    registry.register(
        _make_definition(id="def-c", domain_id=DomainId("health"), source_priority=10)
    )
    matches = registry.find_by_kind("calendar-event")
    assert [d.id for d in matches] == ["def-c", "def-a", "def-b"]


def test_find_by_domain_orders_by_kind_priority_and_id():
    registry = InMemoryDomainResourceRegistry()
    registry.register(_make_definition(id="def-b", kind="note", source_priority=1))
    registry.register(
        _make_definition(id="def-a", kind="calendar-event", source_priority=1)
    )
    registry.register(
        _make_definition(id="def-c", kind="calendar-event", source_priority=5)
    )
    matches = registry.find_by_domain(DomainId("health"))
    assert [d.id for d in matches] == ["def-c", "def-a", "def-b"]


def test_list_all_orders_by_domain_slug_kind_and_id():
    registry = InMemoryDomainResourceRegistry()
    registry.register(
        _make_definition(id="def-b", domain_id=DomainId("university"), kind="note")
    )
    registry.register(
        _make_definition(id="def-a", domain_id=DomainId("health"), kind="note")
    )
    matches = registry.list_all()
    assert [d.id for d in matches] == ["def-a", "def-b"]


def test_returned_tuples_are_immutable_and_isolated():
    registry = InMemoryDomainResourceRegistry()
    registry.register(_make_definition())
    result = registry.list_all()
    assert isinstance(result, tuple)
    with pytest.raises(TypeError):
        result[0] = None


def test_register_rejects_non_definition_input():
    registry = InMemoryDomainResourceRegistry()
    with pytest.raises(DomainResourceRegistryError):
        registry.register("not-a-definition")
