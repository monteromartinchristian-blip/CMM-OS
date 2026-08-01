from __future__ import annotations

from dataclasses import replace

import pytest

from cmm.agent_runtime.enums import ApprovalRequestStatus, PolicyRiskLevel
from cmm.domains import (
    DomainOperationAvailabilityContext,
    DomainOperationAvailabilityResolver,
    DomainOperationDefinition,
    DomainOperationSerializationError,
    DomainOperationStatus,
    DomainOperationType,
)


def _definition(**overrides: object) -> DomainOperationDefinition:
    values = {
        "operation_id": "health.prepare_medical_appointment",
        "domain_id": "domain:health",
        "version": "1.0.0",
        "name": "Prepare appointment",
        "description": "Prepare structured material",
        "operation_type": DomainOperationType.PREPARATION,
        "required_resources": ("health.notes",),
        "required_permissions": ("health.read",),
        "risk_level": PolicyRiskLevel.HIGH,
        "reversible": True,
        "rollback_policy_id": "rollback.safe",
    }
    values.update(overrides)
    return DomainOperationDefinition(**values)  # type: ignore[arg-type]


def _context(**overrides: object) -> DomainOperationAvailabilityContext:
    values = {
        "primary_domain_id": "domain:health",
        "supporting_domain_ids": ("domain:general",),
        "granted_permissions": ("health.read",),
        "denied_permissions": (),
        "available_resources": ("health.notes",),
        "capabilities": ("execute", "rollback", "transaction"),
        "available_validation_policy_ids": (),
        "available_rollback_policy_ids": ("rollback.safe",),
        "approval_status": None,
        "approval_fingerprint": None,
        "request_fingerprint": "fingerprint",
    }
    values.update(overrides)
    return DomainOperationAvailabilityContext(**values)  # type: ignore[arg-type]


def test_available_decision_contains_effective_audit_data() -> None:
    decision = DomainOperationAvailabilityResolver().resolve(_definition(), _context())
    assert decision.status is DomainOperationStatus.AVAILABLE
    assert decision.required_permissions == ("health.read",)
    assert decision.granted_permissions == ("health.read",)
    assert decision.missing_resources == ()
    assert decision.trace_entries[-1].reason_code == "availability.available"


def test_availability_contracts_round_trip_and_reject_unknown_fields() -> None:
    context = _context(metadata={"nested": {"items": [1, True]}})
    assert DomainOperationAvailabilityContext.from_dict(context.to_dict()) == context

    decision = DomainOperationAvailabilityResolver().resolve(_definition(), context)
    restored = type(decision).from_dict(decision.to_dict())
    assert restored == decision
    with pytest.raises(DomainOperationSerializationError, match="unknown fields"):
        type(decision).from_dict({**decision.to_dict(), "unknown": True})


def test_disabled_missing_resource_permission_and_deny_precedence() -> None:
    resolver = DomainOperationAvailabilityResolver()
    assert (
        resolver.resolve(replace(_definition(), enabled=False), _context()).status
        is DomainOperationStatus.UNAVAILABLE
    )
    assert (
        resolver.resolve(_definition(), _context(available_resources=())).status
        is DomainOperationStatus.UNAVAILABLE
    )
    assert (
        resolver.resolve(_definition(), _context(granted_permissions=())).status
        is DomainOperationStatus.BLOCKED
    )
    denied = resolver.resolve(
        _definition(), _context(denied_permissions=("health.read",))
    )
    assert denied.status is DomainOperationStatus.BLOCKED
    assert denied.denied_permissions == ("health.read",)


def test_domain_external_validation_transaction_and_rollback_capabilities() -> None:
    resolver = DomainOperationAvailabilityResolver()
    assert (
        resolver.resolve(
            _definition(),
            _context(primary_domain_id="domain:project", supporting_domain_ids=()),
        ).status
        is DomainOperationStatus.BLOCKED
    )
    external = _definition(
        operation_type="external", rollback_policy_id=None, reversible=False
    )
    assert (
        resolver.resolve(external, _context(capabilities=())).status
        is DomainOperationStatus.UNAVAILABLE
    )
    validated = _definition(validation_policy_id="validation:health")
    assert (
        resolver.resolve(validated, _context()).status
        is DomainOperationStatus.UNAVAILABLE
    )
    assert (
        resolver.resolve(
            _definition(), _context(available_rollback_policy_ids=())
        ).status
        is DomainOperationStatus.BLOCKED
    )


def test_approval_is_pending_until_matching_approved_fingerprint() -> None:
    resolver = DomainOperationAvailabilityResolver()
    definition = _definition(requires_approval=True)
    assert (
        resolver.resolve(definition, _context()).status
        is DomainOperationStatus.WAITING_FOR_APPROVAL
    )
    assert (
        resolver.resolve(
            definition, _context(approval_status=ApprovalRequestStatus.PENDING)
        ).status
        is DomainOperationStatus.WAITING_FOR_APPROVAL
    )
    assert (
        resolver.resolve(
            definition, _context(approval_status=ApprovalRequestStatus.REJECTED)
        ).status
        is DomainOperationStatus.BLOCKED
    )
    assert (
        resolver.resolve(
            definition,
            _context(
                approval_status=ApprovalRequestStatus.APPROVED,
                approval_fingerprint="other",
            ),
        ).status
        is DomainOperationStatus.BLOCKED
    )
    assert (
        resolver.resolve(
            definition,
            _context(
                approval_status=ApprovalRequestStatus.APPROVED,
                approval_fingerprint="fingerprint",
            ),
        ).status
        is DomainOperationStatus.AVAILABLE
    )


def test_destructive_always_requires_approval() -> None:
    destructive = _definition(
        operation_type="destructive",
        requires_approval=True,
        reversible=False,
        rollback_policy_id=None,
    )
    decision = DomainOperationAvailabilityResolver().resolve(destructive, _context())
    assert decision.status is DomainOperationStatus.WAITING_FOR_APPROVAL
