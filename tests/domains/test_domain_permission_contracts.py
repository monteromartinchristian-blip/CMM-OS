from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.agent_security_enums import SensitivityLevel
from cmm.agent_runtime.domain_permission_contracts import (
    PermissionCapability,
    PermissionOutcome,
)
from cmm.domains.permission_contracts import (
    CrossDomainPermissionDecision,
    CrossDomainPermissionRequest,
    DomainAutonomyLimits,
    DomainPermissionPolicy,
    DomainPermissionRequest,
)


def test_policy_is_immutable_semver_and_round_trips():
    policy = DomainPermissionPolicy(
        policy_id="domain-permission:health:default",
        domain_id="domain:health",
        version="1.10.0",
        allowed_operations=("operation:health.read",),
        allow_memory_read=True,
        metadata={"owner": "product"},
    )
    assert policy.from_dict(policy.to_dict()) == policy
    with pytest.raises(TypeError):
        policy.metadata["owner"] = "other"
    with pytest.raises(ValueError):
        DomainPermissionPolicy("p", "domain:health", "1.9", metadata={})


def test_policy_rejects_unknown_fields_and_non_json_metadata():
    with pytest.raises(ValueError):
        DomainPermissionPolicy.from_dict({"policy_id": "p", "domain_id": "domain:x", "version": "1.0.0", "unknown": 1})
    with pytest.raises(ValueError):
        DomainPermissionPolicy("p", "domain:x", "1.0.0", metadata={"bad": object()})


def test_request_requires_context_for_action_and_round_trips():
    request = DomainPermissionRequest(
        request_id="request-1",
        action=PermissionCapability.OPERATION_EXECUTE,
        domain_id="domain:health",
        actor_id="actor-1",
        session_id="session-1",
        operation_id="operation:health.read",
        sensitivity_level=SensitivityLevel.INTERNAL,
        context={"purpose": "test"},
    )
    assert DomainPermissionRequest.from_dict(request.to_dict()) == request
    with pytest.raises(ValueError):
        DomainPermissionRequest("r", PermissionCapability.OPERATION_EXECUTE, "domain:x", "a", "s")
    with pytest.raises(ValueError):
        DomainPermissionRequest("r", "domain.cross_access", "domain:x", "a", "s")


def test_cross_domain_requires_distinct_domains_and_immutable_scope():
    request = CrossDomainPermissionRequest(
        request_id="cross-1",
        source_domain="domain:life-plan",
        target_domain="domain:health",
        resource_ids=("resource:health:1",),
        requested_operations=("operation:health.read",),
        duration="session",
        reason="evaluate constraints",
        actor_id="actor-1",
        session_id="session-1",
        expires_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
    )
    assert CrossDomainPermissionRequest.from_dict(request.to_dict()) == request
    with pytest.raises(ValueError):
        CrossDomainPermissionRequest("x", "domain:a", "domain:a", reason="x", actor_id="a", session_id="s")


def test_cross_domain_capability_and_constraints_are_strictly_typed():
    with pytest.raises(ValueError, match="requested_operations"):
        CrossDomainPermissionRequest(
            "x", "domain:a", "domain:b",
            capability=PermissionCapability.OPERATION_EXECUTE,
            reason="x", actor_id="a", session_id="s",
        )
    with pytest.raises(ValueError, match="allowed_operations"):
        CrossDomainPermissionRequest(
            "x", "domain:a", "domain:b", reason="x", actor_id="a", session_id="s",
            constraints={"allowed_operations": "operation:read"},
        )
    with pytest.raises(ValueError, match="maximum_operations"):
        CrossDomainPermissionRequest(
            "x", "domain:a", "domain:b", reason="x", actor_id="a", session_id="s",
            constraints={"maximum_operations": True},
        )


def test_decision_invariants():
    with pytest.raises(ValueError):
        CrossDomainPermissionDecision("x", PermissionOutcome.APPROVAL_REQUIRED)
    decision = CrossDomainPermissionDecision("x", PermissionOutcome.DENY, reasons=("target_denied",))
    assert decision.to_dict()["decision"] == "deny"


def test_autonomy_limits_reject_bool_and_non_finite_numbers():
    with pytest.raises(ValueError):
        DomainAutonomyLimits(maximum_operations=True)
    with pytest.raises(ValueError):
        DomainAutonomyLimits(maximum_cost=float("inf"))
