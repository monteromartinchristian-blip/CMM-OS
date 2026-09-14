import math

import pytest

from cmm.agent_runtime.domain_permission_contracts import (
    EffectivePermissionResult,
    PermissionApprovalRequirement,
    PermissionCapability,
    PermissionLayer,
    PermissionLayerEvaluation,
    PermissionOutcome,
    intersect_permission_layers,
)


def test_capabilities_are_closed_and_strict():
    assert PermissionCapability.MEMORY_READ.value == "memory.read"
    with pytest.raises(ValueError):
        PermissionCapability("made.up")


def test_layer_evaluation_is_deeply_immutable_and_serializable():
    evaluation = PermissionLayerEvaluation(
        source=PermissionLayer.DOMAIN,
        effect=PermissionOutcome.ALLOW,
        matched_rules=("policy:health:1.0.0",),
        reasons=("granted",),
        constraints={"maximum_operations": 2},
        metadata={"evidence": {"resource": "r1"}},
    )
    assert evaluation.to_dict()["constraints"] == {"maximum_operations": 2}
    with pytest.raises(TypeError):
        evaluation.constraints["maximum_operations"] = 3
    assert PermissionLayerEvaluation.from_dict(evaluation.to_dict()) == evaluation


def test_deny_wins_independent_of_layer_order():
    allow = PermissionLayerEvaluation(PermissionLayer.DOMAIN, PermissionOutcome.ALLOW)
    deny = PermissionLayerEvaluation(
        PermissionLayer.GLOBAL, PermissionOutcome.DENY, reasons=("global_deny",)
    )
    first = intersect_permission_layers((allow, deny), request_id="req-1", action="memory.read")
    second = intersect_permission_layers((deny, allow), request_id="req-1", action="memory.read")
    assert first.decision is PermissionOutcome.DENY
    assert first == second
    assert first.denied_by == (PermissionLayer.GLOBAL,)


def test_approval_requires_requirements_and_does_not_override_deny():
    requirement = PermissionApprovalRequirement(
        requirement_id="approval-1", action=PermissionCapability.FILE_MODIFY,
        actor_id="actor", session_id="session", domain_id="domain:project",
        fingerprint="request:file:actor:session:project",
    )
    approval = PermissionLayerEvaluation(
        PermissionLayer.OPERATION,
        PermissionOutcome.APPROVAL_REQUIRED,
        approval_requirements=(requirement,),
    )
    result = intersect_permission_layers((approval,), request_id="r", action="file.modify")
    assert result.decision is PermissionOutcome.APPROVAL_REQUIRED
    assert result.approval_requirements == (requirement,)
    with pytest.raises(ValueError):
        PermissionLayerEvaluation(PermissionLayer.DOMAIN, PermissionOutcome.APPROVAL_REQUIRED)


def test_node_scoped_approval_requirement_round_trip_is_deterministic():
    requirement = PermissionApprovalRequirement(
        requirement_id="approval-node",
        action=PermissionCapability.WORKFLOW_EXECUTE,
        actor_id="actor",
        session_id="session",
        domain_id="domain:project",
        workflow_id="project.review",
        node_id="publish",
        fingerprint="workflow:node:publish",
        scope="node",
    )

    assert PermissionApprovalRequirement.from_dict(requirement.to_dict()) == requirement


def test_abstain_blocks_approval_when_a_required_layer_did_not_grant():
    requirement = PermissionApprovalRequirement(
        requirement_id="approval-1",
        action=PermissionCapability.FILE_MODIFY,
        actor_id="actor",
        session_id="session",
        domain_id="domain:project",
        fingerprint="request:file:actor:session:project",
    )
    approval = PermissionLayerEvaluation(
        PermissionLayer.OPERATION,
        PermissionOutcome.APPROVAL_REQUIRED,
        approval_requirements=(requirement,),
    )
    abstain = PermissionLayerEvaluation(
        PermissionLayer.DOMAIN,
        PermissionOutcome.ABSTAIN,
        reasons=("domain_did_not_grant",),
    )

    result = intersect_permission_layers(
        (approval, abstain), request_id="r", action="file.modify"
    )

    assert result.decision is PermissionOutcome.DENY
    assert result.unresolved_by == (PermissionLayer.DOMAIN,)
    assert "no_sufficient_allow" in result.reasons


def test_approval_requires_every_supplied_layer_to_allow_or_require_approval():
    requirement = PermissionApprovalRequirement(
        requirement_id="approval-1",
        action=PermissionCapability.FILE_MODIFY,
        actor_id="actor",
        session_id="session",
        domain_id="domain:project",
        fingerprint="request:file:actor:session:project",
    )
    approval = PermissionLayerEvaluation(
        PermissionLayer.OPERATION,
        PermissionOutcome.APPROVAL_REQUIRED,
        approval_requirements=(requirement,),
    )
    allow = PermissionLayerEvaluation(
        PermissionLayer.DOMAIN,
        PermissionOutcome.ALLOW,
    )

    result = intersect_permission_layers(
        (approval, allow), request_id="r", action="file.modify"
    )

    assert result.decision is PermissionOutcome.APPROVAL_REQUIRED


def test_constraints_take_restrictive_intersection_and_reject_bool_numeric():
    left = PermissionLayerEvaluation(
        PermissionLayer.GLOBAL, PermissionOutcome.ALLOW,
        constraints={"maximum_operations": 10, "minimum_autonomy_level": 1},
    )
    right = PermissionLayerEvaluation(
        PermissionLayer.DOMAIN, PermissionOutcome.ALLOW,
        constraints={"maximum_operations": 3, "minimum_autonomy_level": 2},
    )
    result = intersect_permission_layers((left, right), request_id="r", action="operation.execute")
    assert result.effective_constraints == {"maximum_operations": 3, "minimum_autonomy_level": 2}
    with pytest.raises(ValueError):
        PermissionLayerEvaluation(PermissionLayer.DOMAIN, PermissionOutcome.ALLOW, constraints={"maximum_operations": True})
    with pytest.raises(ValueError):
        PermissionLayerEvaluation(PermissionLayer.DOMAIN, PermissionOutcome.ALLOW, constraints={"maximum_cost": math.inf})


def test_abstain_everywhere_is_denied_not_allowed():
    result = intersect_permission_layers(
        tuple(PermissionLayerEvaluation(layer, PermissionOutcome.ABSTAIN) for layer in PermissionLayer),
        request_id="r",
        action="resource.read",
    )
    assert result.decision is PermissionOutcome.DENY


def test_constraints_are_restrictive_for_boolean_sets_scopes_and_expiry():
    left = PermissionLayerEvaluation(
        PermissionLayer.GLOBAL,
        PermissionOutcome.ALLOW,
        source_id="global:default",
        constraints={
            "allow_external_access": True,
            "prohibit_export": False,
            "allowed_resources": ("a", "b"),
            "prohibited_resources": ("x",),
            "scopes": ("request", "session"),
            "expires_at": "2026-08-05T00:00:00+00:00",
        },
    )
    right = PermissionLayerEvaluation(
        PermissionLayer.DOMAIN,
        PermissionOutcome.ALLOW,
        source_id="domain:health",
        policy_id="domain-permission:health:default",
        policy_version="1.0.0",
        constraints={
            "allow_external_access": False,
            "prohibit_export": True,
            "allowed_resources": ("b", "c"),
            "prohibited_resources": ("y",),
            "scopes": ("session",),
            "expires_at": "2026-08-03T00:00:00+00:00",
        },
    )
    result = intersect_permission_layers((right, left), request_id="r", action="memory.read")
    assert result.effective_constraints == {
        "allow_external_access": False,
        "prohibit_export": True,
        "allowed_resources": ("b",),
        "prohibited_resources": ("x", "y"),
        "scopes": ("session",),
        "expires_at": "2026-08-03T00:00:00+00:00",
    }


def test_constraints_reject_unknown_keys_and_are_commutative_idempotent():
    with pytest.raises(ValueError, match="unknown constraint"):
        PermissionLayerEvaluation(
            PermissionLayer.DOMAIN,
            PermissionOutcome.ALLOW,
            constraints={"unbounded": True},
        )
    item = PermissionLayerEvaluation(
        PermissionLayer.DOMAIN,
        PermissionOutcome.ALLOW,
        source_id="domain:health",
        constraints={"allowed_resources": ("a", "b")},
    )
    same = intersect_permission_layers((item, item), request_id="r", action="memory.read")
    assert same.effective_constraints == {"allowed_resources": ("a", "b")}


def test_effective_result_round_trips_with_policy_identity_and_rejects_unknown_fields():
    evaluation = PermissionLayerEvaluation(
        PermissionLayer.DOMAIN,
        PermissionOutcome.ALLOW,
        source_id="domain:health:primary",
        policy_id="policy:health",
        policy_version="1.0.0",
    )
    result = intersect_permission_layers((evaluation,), request_id="r", action="memory.read")
    assert EffectivePermissionResult.from_dict(result.to_dict()) == result
    assert result.allowed_by == ("domain:health:primary",)
    with pytest.raises(ValueError, match="unknown fields"):
        EffectivePermissionResult.from_dict({**result.to_dict(), "extra": True})


def test_expiry_constraint_uses_chronological_not_lexical_order():
    later_lexically_first = PermissionLayerEvaluation(
        PermissionLayer.GLOBAL,
        PermissionOutcome.ALLOW,
        constraints={"expires_at": "2026-08-02T01:00:00+02:00"},
    )
    earlier_lexically_later = PermissionLayerEvaluation(
        PermissionLayer.DOMAIN,
        PermissionOutcome.ALLOW,
        source_id="domain:health",
        constraints={"expires_at": "2026-08-01T23:30:00+00:00"},
    )
    result = intersect_permission_layers(
        (later_lexically_first, earlier_lexically_later),
        request_id="r",
        action="memory.read",
    )
    assert result.effective_constraints["expires_at"] == "2026-08-02T01:00:00+02:00"
