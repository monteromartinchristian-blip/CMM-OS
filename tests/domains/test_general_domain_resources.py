"""Tests for General Domain resources."""

from __future__ import annotations

import pytest

from cmm.cognitive.enums import SensitivityLevel
from cmm.domains.errors import (
    DomainResourceContractError,
    DomainResourceSerializationError,
)
from cmm.domains.general import (
    GENERAL_RESOURCE_KINDS,
    build_general_resource_definitions,
)
from cmm.domains.resource_contracts import DomainResourceDefinition


def test_complete_catalog():
    resources = build_general_resource_definitions()
    assert len(resources) == 9


def test_exact_ids():
    resources = build_general_resource_definitions()
    ids = tuple(r.id for r in resources)
    assert ids == (
        "general.calendar_event",
        "general.conversation",
        "general.document",
        "general.external_source",
        "general.generic_goal",
        "general.generic_task",
        "general.memory_entry",
        "general.note",
        "general.user_message",
    )


def test_no_duplicates():
    resources = build_general_resource_definitions()
    ids = [r.id for r in resources]
    assert len(set(ids)) == len(ids)


def test_all_kinds_match():
    resources = build_general_resource_definitions()
    kinds = tuple(r.kind for r in resources)
    assert kinds == GENERAL_RESOURCE_KINDS


def test_all_domain_ids():
    resources = build_general_resource_definitions()
    for r in resources:
        assert r.domain_id.slug == "general"


def test_external_source_is_restricted():
    resources = build_general_resource_definitions()
    external = next(r for r in resources if r.kind == "external_source")
    assert external.default_sensitivity is SensitivityLevel.RESTRICTED
    assert external.default_reliability < 0.5


def test_user_message_is_unverified():
    resources = build_general_resource_definitions()
    message = next(r for r in resources if r.kind == "user_message")
    assert message.default_reliability < 0.6
    assert message.metadata.get("unverified") is True


def test_memory_entry_uses_memory_integration():
    resources = build_general_resource_definitions()
    memory = next(r for r in resources if r.kind == "memory_entry")
    assert memory.metadata.get("memory_integration") is True


def test_serialization_round_trip():
    resources = build_general_resource_definitions()
    for r in resources:
        restored = DomainResourceDefinition.from_dict(r.to_dict())
        assert restored == r


def test_deterministic_ordering():
    a = build_general_resource_definitions()
    b = build_general_resource_definitions()
    assert [r.id for r in a] == [r.id for r in b]


def test_unknown_fields_rejected():
    resources = build_general_resource_definitions()
    data = resources[0].to_dict()
    data["unknown_field"] = "x"
    with pytest.raises(DomainResourceSerializationError):
        DomainResourceDefinition.from_dict(data)


def test_wrong_types_rejected():
    resources = build_general_resource_definitions()
    data = resources[0].to_dict()
    data["default_reliability"] = "not-a-number"
    with pytest.raises(DomainResourceContractError):
        DomainResourceDefinition.from_dict(data)


def test_unknown_adapter_rejected():
    with pytest.raises(DomainResourceContractError):
        DomainResourceDefinition(
            id="general.test",
            kind="test",
            domain_id="domain:general",
            adapter="",
        )


def test_external_source_fail_closed():
    resources = build_general_resource_definitions()
    external = next(r for r in resources if r.kind == "external_source")
    assert external.default_reliability == 0.3
    assert external.default_sensitivity is SensitivityLevel.RESTRICTED
    assert external.temporal_policy.effective_date_required is True
    assert external.temporal_policy.expiration_required is True