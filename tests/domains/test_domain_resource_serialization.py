"""Tests for Phase 10.10 – Domain Resource strict serialization (Tasks 2-5)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.errors import DomainResourceSerializationError
from cmm.domains.identifiers import DomainId
from cmm.domains.resource_contracts import (
    DomainResourceBinding,
    DomainResourceChecksum,
    DomainResourceContext,
    DomainResourceDecision,
    DomainResourceDefinition,
    DomainResourceDerivation,
    DomainResourceRejection,
    DomainResourceResolution,
    DomainResourceTemporalPolicy,
    DomainResourceValidationResult,
    DomainResourceValidationRule,
)


def test_checksum_round_trip():
    checksum = DomainResourceChecksum(algorithm="sha256", value="a" * 64)
    assert DomainResourceChecksum.from_dict(checksum.to_dict()) == checksum


def test_checksum_rejects_unknown_field():
    with pytest.raises(DomainResourceSerializationError):
        DomainResourceChecksum.from_dict(
            {"algorithm": "sha256", "value": "a" * 64, "bogus": 1}
        )


def test_temporal_policy_round_trip():
    policy = DomainResourceTemporalPolicy(
        validity_window_seconds=3600,
        staleness_policy="strict",
        effective_date_required=True,
        expiration_required=True,
        historical_allowed=False,
    )
    assert DomainResourceTemporalPolicy.from_dict(policy.to_dict()) == policy


def test_temporal_policy_rejects_unknown_field():
    with pytest.raises(DomainResourceSerializationError):
        DomainResourceTemporalPolicy.from_dict({"bogus": 1})


def test_validation_rule_round_trip():
    rule = DomainResourceValidationRule(
        id="rule-1",
        field="sensitivity",
        operator="equals",
        expected="internal",
        severity="warning",
        message="check sensitivity",
    )
    assert DomainResourceValidationRule.from_dict(rule.to_dict()) == rule


def test_validation_rule_rejects_unknown_field():
    with pytest.raises(DomainResourceSerializationError):
        DomainResourceValidationRule.from_dict(
            {
                "id": "rule-1",
                "field": "sensitivity",
                "operator": "equals",
                "expected": "internal",
                "severity": "warning",
                "message": "check",
                "bogus": 1,
            }
        )


def test_validation_result_round_trip():
    result = DomainResourceValidationResult(
        rule_id="rule-1",
        passed=False,
        severity="error",
        message="mismatch",
        field="sensitivity",
        observed="restricted",
    )
    assert DomainResourceValidationResult.from_dict(result.to_dict()) == result


def test_definition_round_trip():
    definition = DomainResourceDefinition(
        id="def-1",
        kind="calendar-event",
        domain_id=DomainId("health"),
        adapter="health.calendar",
        entity_types=("event",),
        default_permissions=("read",),
        source_priority=5,
        default_reliability=0.9,
    )
    restored = DomainResourceDefinition.from_dict(definition.to_dict())
    assert restored == definition


def test_definition_rejects_unknown_field():
    with pytest.raises(DomainResourceSerializationError):
        DomainResourceDefinition.from_dict(
            {
                "id": "def-1",
                "kind": "calendar-event",
                "domain_id": "domain:health",
                "adapter": "health.calendar",
                "bogus": 1,
            }
        )


def test_context_round_trip():
    context = DomainResourceContext(
        resource_id="res-1",
        kind="calendar-event",
        provenance=("src-a",),
        applicable_domains=(DomainId("health"),),
        permissions=("read",),
    )
    restored = DomainResourceContext.from_dict(context.to_dict())
    assert restored == context


def test_context_rejects_unknown_field():
    with pytest.raises(DomainResourceSerializationError):
        DomainResourceContext.from_dict(
            {
                "resource_id": "res-1",
                "kind": "calendar-event",
                "provenance": ["src-a"],
                "bogus": 1,
            }
        )


def test_binding_round_trip():
    binding = DomainResourceBinding(
        id="bind-1",
        resource_id="res-1",
        definition_id="def-1",
        domain_id=DomainId("health"),
        adapter="health.calendar",
        provenance=("src-a",),
    )
    restored = DomainResourceBinding.from_dict(binding.to_dict())
    assert restored == binding


def test_binding_rejects_unknown_field():
    with pytest.raises(DomainResourceSerializationError):
        DomainResourceBinding.from_dict(
            {
                "id": "bind-1",
                "resource_id": "res-1",
                "definition_id": "def-1",
                "domain_id": "domain:health",
                "adapter": "health.calendar",
                "provenance": ["src-a"],
                "bogus": 1,
            }
        )


def test_rejection_round_trip():
    rejection = DomainResourceRejection(
        definition_id="def-1",
        domain_id=DomainId("health"),
        code="validation_failed",
        reason="rule failed",
        blocking=True,
    )
    restored = DomainResourceRejection.from_dict(rejection.to_dict())
    assert restored == rejection


def test_decision_round_trip():
    decision = DomainResourceDecision(
        code="resource_shared",
        resource_id="res-1",
        reason="shared",
        blocking=False,
    )
    restored = DomainResourceDecision.from_dict(decision.to_dict())
    assert restored == decision


def test_resolution_round_trip():
    binding = DomainResourceBinding(
        id="bind-1",
        resource_id="res-1",
        definition_id="def-1",
        domain_id=DomainId("health"),
        adapter="health.calendar",
        provenance=("src-a",),
    )
    resolution = DomainResourceResolution(
        id="res-res-1",
        resource_id="res-1",
        status="resolved",
        trace_id="trace-1",
        resolved_at=datetime.now(timezone.utc),
        bindings=(binding,),
    )
    restored = DomainResourceResolution.from_dict(resolution.to_dict())
    assert restored == resolution


def test_resolution_rejects_unknown_field():
    with pytest.raises(DomainResourceSerializationError):
        DomainResourceResolution.from_dict(
            {
                "id": "res-res-1",
                "resource_id": "res-1",
                "status": "rejected",
                "trace_id": "trace-1",
                "resolved_at": datetime.now(timezone.utc).isoformat(),
                "bogus": 1,
            }
        )


def test_derivation_round_trip():
    derivation = DomainResourceDerivation(
        id="der-1",
        source_resource_id="res-1",
        derived_resource_id="res-2",
        definition_id="def-1",
        transformation="normalize",
        actor="system",
        created_at=datetime.now(timezone.utc),
        version="1",
        checksum=DomainResourceChecksum(algorithm="sha256", value="a" * 64),
        provenance=("res-1",),
    )
    restored = DomainResourceDerivation.from_dict(derivation.to_dict())
    assert restored == derivation


def test_derivation_rejects_unknown_field():
    with pytest.raises(DomainResourceSerializationError):
        DomainResourceDerivation.from_dict(
            {
                "id": "der-1",
                "source_resource_id": "res-1",
                "derived_resource_id": "res-2",
                "definition_id": "def-1",
                "transformation": "normalize",
                "actor": "system",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "version": "1",
                "bogus": 1,
            }
        )
