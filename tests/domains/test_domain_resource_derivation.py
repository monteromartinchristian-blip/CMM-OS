"""Tests for Phase 10.10 – Domain Resource Derivation Service (Task 10)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive.enums import SensitivityLevel as Sensitivity
from cmm.domains.errors import (
    DomainResourceContractError,
    DomainResourceDerivationError,
)
from cmm.domains.resource_contracts import DomainResourceDerivation
from cmm.domains.resource_derivation import DomainResourceDerivationService


def _make_derivation(**overrides) -> DomainResourceDerivation:
    defaults = {
        "id": "der-1",
        "source_resource_id": "res-1",
        "derived_resource_id": "res-2",
        "definition_id": "def-1",
        "transformation": "normalize",
        "actor": "system",
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "version": "1",
        "provenance": ("res-1",),
    }
    defaults.update(overrides)
    return DomainResourceDerivation(**defaults)


def test_record_rejects_permission_widening():
    service = DomainResourceDerivationService()
    derivation = _make_derivation(permissions=("read", "write"))
    with pytest.raises(DomainResourceDerivationError):
        service.record(
            derivation=derivation,
            source_permissions=("read",),
            source_sensitivity=Sensitivity.INTERNAL,
        )


def test_record_allows_permission_narrowing():
    service = DomainResourceDerivationService()
    derivation = _make_derivation(permissions=("read",))
    result = service.record(
        derivation=derivation,
        source_permissions=("read", "write"),
        source_sensitivity=Sensitivity.INTERNAL,
    )
    assert result is derivation


def test_record_rejects_sensitivity_decrease():
    service = DomainResourceDerivationService()
    derivation = _make_derivation(sensitivity=Sensitivity.PUBLIC)
    with pytest.raises(DomainResourceDerivationError):
        service.record(
            derivation=derivation,
            source_permissions=(),
            source_sensitivity=Sensitivity.SENSITIVE,
        )


def test_record_allows_sensitivity_increase():
    service = DomainResourceDerivationService()
    derivation = _make_derivation(sensitivity=Sensitivity.SENSITIVE)
    result = service.record(
        derivation=derivation,
        source_permissions=(),
        source_sensitivity=Sensitivity.INTERNAL,
    )
    assert result.sensitivity == Sensitivity.SENSITIVE


def test_record_requires_complete_lineage_provenance():
    with pytest.raises(DomainResourceContractError):
        _make_derivation(provenance=())


def test_record_preserves_checksum():
    from cmm.domains.resource_contracts import DomainResourceChecksum

    checksum = DomainResourceChecksum(algorithm="sha256", value="a" * 64)
    service = DomainResourceDerivationService()
    derivation = _make_derivation(checksum=checksum)
    result = service.record(
        derivation=derivation,
        source_permissions=(),
        source_sensitivity=Sensitivity.INTERNAL,
    )
    assert result.checksum == checksum


def test_record_rejects_non_derivation_input():
    service = DomainResourceDerivationService()
    with pytest.raises(DomainResourceDerivationError):
        service.record(
            derivation="not-a-derivation",
            source_permissions=(),
            source_sensitivity=Sensitivity.INTERNAL,
        )


def test_record_carries_no_payload_attribute():
    service = DomainResourceDerivationService()
    derivation = _make_derivation()
    result = service.record(
        derivation=derivation,
        source_permissions=(),
        source_sensitivity=Sensitivity.INTERNAL,
    )
    assert not hasattr(result, "content")
    assert not hasattr(result, "payload")


def test_source_deny_cannot_be_lifted_by_derivation():
    service = DomainResourceDerivationService()
    derivation = _make_derivation(permissions=("read",))
    with pytest.raises(DomainResourceDerivationError):
        service.record(
            derivation=derivation,
            source_permissions=("read", "deny:read"),
            source_sensitivity=Sensitivity.INTERNAL,
        )


def test_derived_deny_can_narrow_source_permission():
    service = DomainResourceDerivationService()
    derivation = _make_derivation(permissions=("read", "write", "deny:write"))
    result = service.record(
        derivation=derivation,
        source_permissions=("read", "write"),
        source_sensitivity=Sensitivity.INTERNAL,
    )
    assert result is derivation


def test_derived_permission_not_effective_in_source_is_rejected():
    service = DomainResourceDerivationService()
    derivation = _make_derivation(permissions=("write",))
    with pytest.raises(DomainResourceDerivationError):
        service.record(
            derivation=derivation,
            source_permissions=("read",),
            source_sensitivity=Sensitivity.INTERNAL,
        )


def test_literal_permission_subset_does_not_bypass_source_deny():
    service = DomainResourceDerivationService()
    derivation = _make_derivation(permissions=("write",))
    with pytest.raises(DomainResourceDerivationError):
        service.record(
            derivation=derivation,
            source_permissions=("read", "write", "deny:write"),
            source_sensitivity=Sensitivity.INTERNAL,
        )


def test_derivation_contract_requires_provenance():
    with pytest.raises(DomainResourceContractError):
        _make_derivation(provenance=())


def test_derivation_round_trip_preserves_provenance():
    derivation = _make_derivation(provenance=("res-1", "res-0"))
    restored = DomainResourceDerivation.from_dict(derivation.to_dict())
    assert restored.provenance == derivation.provenance
