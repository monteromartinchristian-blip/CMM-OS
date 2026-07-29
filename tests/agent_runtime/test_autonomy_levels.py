from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.autonomy_adapters import (
    create_autonomy_request_from_policy_result,
)
from cmm.agent_runtime.autonomy_contracts import (
    AutonomyEvaluationRequest,
    coerce_autonomy_level,
)
from cmm.agent_runtime.autonomy_evaluator import DefaultAutonomyEvaluator
from cmm.agent_runtime.autonomy_manager import (
    apply_autonomy_transition,
    build_transition_record,
    build_transition_request,
    derive_new_agent_run,
)
from cmm.agent_runtime.autonomy_profiles import get_autonomy_profile
from cmm.agent_runtime.contracts import AgentDefinition, AgentRun
from cmm.agent_runtime.enums import (
    AgentAutonomyLevel,
    AgentRuntimeStatus,
    AutonomyCapability,
    AutonomyDecision,
    AutonomyTransitionReason,
    PolicyDecision,
    PolicyEvaluationStatus,
)
from cmm.agent_runtime.errors import (
    AutonomyEscalationNotAuthorizedError,
    AutonomyLevelError,
    AutonomyPolicyIntegrationError,
    AutonomyTransitionError,
)
from cmm.agent_runtime.policy_contracts import PolicyEvaluationResult


def test_autonomy_levels_are_integer_compatible() -> None:
    assert AgentAutonomyLevel.ANALYZE_ONLY == 0
    assert AgentAutonomyLevel.PROPOSE_ACTIONS == 1
    assert AgentAutonomyLevel.REVERSIBLE_EXECUTION == 2
    assert AgentAutonomyLevel.SUPERVISED_AUTONOMY == 3
    assert AgentAutonomyLevel.POLICY_BOUNDED_AUTONOMY == 4


@pytest.mark.parametrize("level", range(5))
def test_coerce_autonomy_level_accepts_supported_integers(level: int) -> None:
    result = coerce_autonomy_level(level)

    assert isinstance(result, AgentAutonomyLevel)
    assert int(result) == level


@pytest.mark.parametrize("value", (-1, 5, True, "high", None))
def test_coerce_autonomy_level_rejects_invalid_values(value: object) -> None:
    with pytest.raises(AutonomyLevelError):
        coerce_autonomy_level(value)


def test_agent_definition_serializes_autonomy_level_as_integer() -> None:
    definition = AgentDefinition(
        id="agent-1",
        name="Agent",
        version="1",
        description="Autonomy test agent",
        reasoning_profile="default",
        runtime_policy="default",
        observation_profile="default",
        autonomy_level=AgentAutonomyLevel.REVERSIBLE_EXECUTION,
    )

    assert definition.autonomy_level == AgentAutonomyLevel.REVERSIBLE_EXECUTION
    assert definition.to_dict()["autonomy_level"] == 2
    assert AgentDefinition.from_dict(definition.to_dict()) == definition


def test_agent_run_serializes_autonomy_level_as_integer() -> None:
    now = datetime.now(timezone.utc)
    run = AgentRun(
        id="run-1",
        agent_id="agent-1",
        goal_id="goal-1",
        status=AgentRuntimeStatus.REASONING,
        autonomy_level=3,
        current_iteration=0,
        started_at=now,
        updated_at=now,
    )

    assert run.autonomy_level == AgentAutonomyLevel.SUPERVISED_AUTONOMY
    assert run.to_dict()["autonomy_level"] == 3
    assert AgentRun.from_dict(run.to_dict()) == run


def test_level_zero_profile_never_executes() -> None:
    profile = get_autonomy_profile(AgentAutonomyLevel.ANALYZE_ONLY)

    assert profile.allow_execution is False
    assert profile.allows(AutonomyCapability.REASON)
    assert not profile.allows(AutonomyCapability.EXECUTE_READ_ONLY)


def test_level_one_proposes_but_does_not_execute() -> None:
    profile = get_autonomy_profile(AgentAutonomyLevel.PROPOSE_ACTIONS)

    assert profile.allows(AutonomyCapability.PROPOSE_OPERATION)
    assert profile.prohibits(AutonomyCapability.EXECUTE_READ_ONLY)


def test_level_two_allows_reversible_execution() -> None:
    profile = get_autonomy_profile(AgentAutonomyLevel.REVERSIBLE_EXECUTION)

    assert profile.allow_execution is True
    assert profile.allows(AutonomyCapability.EXECUTE_READ_ONLY)
    assert profile.allows(AutonomyCapability.EXECUTE_REVERSIBLE)
    assert profile.requires_rollback_for_mutation is True
    assert profile.prohibits(AutonomyCapability.EXECUTE_IRREVERSIBLE)


def test_level_three_requires_approval_for_publication() -> None:
    profile = get_autonomy_profile(AgentAutonomyLevel.SUPERVISED_AUTONOMY)

    assert profile.allows(AutonomyCapability.EXECUTE_WORKFLOW)
    assert profile.requires_approval_for(AutonomyCapability.PUBLISH)


def test_level_four_is_still_policy_bounded() -> None:
    request = AutonomyEvaluationRequest(
        id="req-level-4",
        agent_run_id="run-1",
        autonomy_level=AgentAutonomyLevel.POLICY_BOUNDED_AUTONOMY,
        capability=AutonomyCapability.PUBLISH,
        is_external=True,
    )

    result = DefaultAutonomyEvaluator().evaluate(request)

    assert result.decision == AutonomyDecision.DENY
    assert result.allowed is False
    assert result.denied is True


def test_level_zero_allows_reasoning() -> None:
    request = AutonomyEvaluationRequest(
        id="req-reason",
        agent_run_id="run-1",
        autonomy_level=AgentAutonomyLevel.ANALYZE_ONLY,
        capability=AutonomyCapability.REASON,
    )

    result = DefaultAutonomyEvaluator().evaluate(request)

    assert result.decision == AutonomyDecision.ALLOW
    assert result.allowed is True


def test_level_zero_denies_execution() -> None:
    request = AutonomyEvaluationRequest(
        id="req-exec",
        agent_run_id="run-1",
        autonomy_level=AgentAutonomyLevel.ANALYZE_ONLY,
        capability=AutonomyCapability.EXECUTE_READ_ONLY,
    )

    result = DefaultAutonomyEvaluator().evaluate(request)

    assert result.decision == AutonomyDecision.DENY
    assert result.denied is True


def test_level_one_allows_proposal() -> None:
    request = AutonomyEvaluationRequest(
        id="req-propose",
        agent_run_id="run-1",
        autonomy_level=AgentAutonomyLevel.PROPOSE_ACTIONS,
        capability=AutonomyCapability.PROPOSE_OPERATION,
    )

    result = DefaultAutonomyEvaluator().evaluate(request)

    assert result.decision == AutonomyDecision.ALLOW
    assert result.allowed is True


def test_level_two_allows_read_only_execution() -> None:
    request = AutonomyEvaluationRequest(
        id="req-read",
        agent_run_id="run-1",
        autonomy_level=AgentAutonomyLevel.REVERSIBLE_EXECUTION,
        capability=AutonomyCapability.EXECUTE_READ_ONLY,
    )

    result = DefaultAutonomyEvaluator().evaluate(request)

    assert result.decision == AutonomyDecision.ALLOW
    assert result.allowed is True


def test_level_two_requires_rollback_for_reversible_mutation() -> None:
    request = AutonomyEvaluationRequest(
        id="req-mutation",
        agent_run_id="run-1",
        autonomy_level=AgentAutonomyLevel.REVERSIBLE_EXECUTION,
        capability=AutonomyCapability.EXECUTE_REVERSIBLE,
        is_mutation=True,
        is_reversible=True,
        validation_passed=True,
        rollback_available=False,
    )

    result = DefaultAutonomyEvaluator().evaluate(request)

    assert result.decision == AutonomyDecision.REQUIRE_ROLLBACK
    assert result.requires_rollback is True
    assert result.allowed is False


def test_level_two_denies_irreversible_execution() -> None:
    request = AutonomyEvaluationRequest(
        id="req-irreversible",
        agent_run_id="run-1",
        autonomy_level=AgentAutonomyLevel.REVERSIBLE_EXECUTION,
        capability=AutonomyCapability.EXECUTE_IRREVERSIBLE,
        is_mutation=True,
        is_reversible=False,
    )

    result = DefaultAutonomyEvaluator().evaluate(request)

    assert result.decision == AutonomyDecision.DENY
    assert result.denied is True


@pytest.mark.parametrize(
    ("capability", "flags"),
    (
        (AutonomyCapability.PUBLISH, {"is_external": True}),
        (AutonomyCapability.SPEND_BUDGET, {"requires_spend": True}),
        (
            AutonomyCapability.MODIFY_PERMISSIONS,
            {"changes_permissions": True},
        ),
        (AutonomyCapability.MODIFY_POLICY, {"changes_policy": True}),
    ),
)
def test_level_three_requires_approval_for_high_impact_capabilities(
    capability: AutonomyCapability,
    flags: dict[str, bool],
) -> None:
    request = AutonomyEvaluationRequest(
        id=f"req-{capability.value}",
        agent_run_id="run-1",
        autonomy_level=AgentAutonomyLevel.SUPERVISED_AUTONOMY,
        capability=capability,
        **flags,
    )

    result = DefaultAutonomyEvaluator().evaluate(request)

    assert result.decision == AutonomyDecision.REQUIRE_APPROVAL
    assert result.requires_approval is True
    assert result.allowed is False


def test_level_four_respects_policy_deny() -> None:
    request = AutonomyEvaluationRequest(
        id="req-policy-deny",
        agent_run_id="run-1",
        autonomy_level=AgentAutonomyLevel.POLICY_BOUNDED_AUTONOMY,
        capability=AutonomyCapability.EXECUTE_WORKFLOW,
        policy_decision="deny",
    )

    result = DefaultAutonomyEvaluator().evaluate(request)

    assert result.decision == AutonomyDecision.DENY
    assert result.denied is True


def test_level_four_respects_policy_require_approval() -> None:
    request = AutonomyEvaluationRequest(
        id="req-policy-approval",
        agent_run_id="run-1",
        autonomy_level=AgentAutonomyLevel.POLICY_BOUNDED_AUTONOMY,
        capability=AutonomyCapability.EXECUTE_WORKFLOW,
        policy_decision="require_approval",
    )

    result = DefaultAutonomyEvaluator().evaluate(request)

    assert result.decision == AutonomyDecision.REQUIRE_APPROVAL
    assert result.requires_approval is True


def test_level_four_allows_when_all_constraints_are_satisfied() -> None:
    request = AutonomyEvaluationRequest(
        id="req-policy-allow",
        agent_run_id="run-1",
        autonomy_level=AgentAutonomyLevel.POLICY_BOUNDED_AUTONOMY,
        capability=AutonomyCapability.EXECUTE_WORKFLOW,
        policy_decision="allow",
        approval_present=True,
        validation_passed=True,
        rollback_available=True,
    )

    result = DefaultAutonomyEvaluator().evaluate(request)

    assert result.decision == AutonomyDecision.ALLOW
    assert result.allowed is True


def _make_agent_run(
    autonomy_level: AgentAutonomyLevel | int = AgentAutonomyLevel.SUPERVISED_AUTONOMY,
) -> AgentRun:
    now = datetime.now(timezone.utc)
    return AgentRun(
        id="run-transition",
        agent_id="agent-1",
        goal_id="goal-1",
        status=AgentRuntimeStatus.EXECUTING,
        autonomy_level=autonomy_level,
        current_iteration=1,
        started_at=now,
        updated_at=now,
    )


def test_autonomy_transition_can_keep_same_level() -> None:
    run = _make_agent_run(2)
    request = build_transition_request(
        agent_run=run,
        target_level=2,
        agent_definition_max_level=4,
    )

    result = apply_autonomy_transition(run, request)

    assert result.success is True
    assert result.previous_level == AgentAutonomyLevel.REVERSIBLE_EXECUTION
    assert result.new_level == AgentAutonomyLevel.REVERSIBLE_EXECUTION
    assert "autonomy.transition_noop" in result.reason_codes


def test_autonomy_transition_can_reduce_without_authorization() -> None:
    run = _make_agent_run(3)
    request = build_transition_request(
        agent_run=run,
        target_level=1,
        agent_definition_max_level=4,
        authorized=False,
        reason=AutonomyTransitionReason.FAILSAFE,
    )

    result = apply_autonomy_transition(run, request)

    assert result.success is True
    assert result.previous_level == AgentAutonomyLevel.SUPERVISED_AUTONOMY
    assert result.new_level == AgentAutonomyLevel.PROPOSE_ACTIONS
    assert result.authorized is True


def test_autonomy_transition_denies_unauthorized_escalation() -> None:
    run = _make_agent_run(1)
    request = build_transition_request(
        agent_run=run,
        target_level=2,
        agent_definition_max_level=4,
        authorized=False,
    )

    with pytest.raises(AutonomyEscalationNotAuthorizedError):
        apply_autonomy_transition(run, request)


def test_autonomy_transition_allows_authorized_escalation() -> None:
    run = _make_agent_run(1)
    request = build_transition_request(
        agent_run=run,
        target_level=3,
        agent_definition_max_level=4,
        authorized=True,
        actor_id="user-1",
    )

    result = apply_autonomy_transition(run, request)

    assert result.success is True
    assert result.previous_level == AgentAutonomyLevel.PROPOSE_ACTIONS
    assert result.new_level == AgentAutonomyLevel.SUPERVISED_AUTONOMY
    assert result.authorized is True


def test_autonomy_transition_cannot_exceed_agent_definition_maximum() -> None:
    run = _make_agent_run(2)
    request = build_transition_request(
        agent_run=run,
        target_level=4,
        agent_definition_max_level=3,
        authorized=True,
    )

    with pytest.raises(
        AutonomyTransitionError,
        match="exceeds the AgentDefinition maximum",
    ):
        apply_autonomy_transition(run, request)


def test_autonomy_transition_rejects_mismatched_run() -> None:
    run = _make_agent_run(2)
    request = build_transition_request(
        agent_run=run,
        target_level=1,
        agent_definition_max_level=4,
    )

    invalid_request = request.__class__.from_dict(
        {
            **request.to_dict(),
            "agent_run_id": "different-run",
        }
    )

    with pytest.raises(AutonomyTransitionError, match="does not match"):
        apply_autonomy_transition(run, invalid_request)


def test_transition_record_preserves_audit_information() -> None:
    run = _make_agent_run(3)
    request = build_transition_request(
        agent_run=run,
        target_level=2,
        agent_definition_max_level=4,
        actor_id="system-safety",
        reason=AutonomyTransitionReason.FAILSAFE,
        message="Risk increased during execution",
    )

    result = apply_autonomy_transition(run, request)
    record = build_transition_record(
        result,
        actor_id="system-safety",
        reason=AutonomyTransitionReason.FAILSAFE,
    )

    assert record.agent_run_id == run.id
    assert record.previous_level == AgentAutonomyLevel.SUPERVISED_AUTONOMY
    assert record.new_level == AgentAutonomyLevel.REVERSIBLE_EXECUTION
    assert record.actor_id == "system-safety"
    assert record.reason == AutonomyTransitionReason.FAILSAFE


def test_derive_new_agent_run_does_not_mutate_original() -> None:
    run = _make_agent_run(3)

    updated = derive_new_agent_run(run, 1)

    assert run.autonomy_level == AgentAutonomyLevel.SUPERVISED_AUTONOMY
    assert updated is not run
    assert updated.autonomy_level == AgentAutonomyLevel.PROPOSE_ACTIONS
    assert updated.id == run.id
    assert updated.agent_id == run.agent_id
    assert updated.goal_id == run.goal_id


def _make_policy_result(
    decision: PolicyDecision,
    *,
    allowed: bool = False,
    denied: bool = False,
    requires_approval: bool = False,
    requires_validation: bool = False,
    paused: bool = False,
) -> PolicyEvaluationResult:
    return PolicyEvaluationResult(
        id=f"policy-result-{decision.value}",
        request_id="policy-request-1",
        decision=decision,
        status=PolicyEvaluationStatus.COMPLETED,
        allowed=allowed,
        denied=denied,
        requires_approval=requires_approval,
        requires_validation=requires_validation,
        requires_information=False,
        paused=paused,
    )


def test_policy_adapter_preserves_explicit_operation_flags() -> None:
    run = _make_agent_run(3)
    policy_result = _make_policy_result(
        PolicyDecision.REQUIRE_APPROVAL,
        requires_approval=True,
    )

    request = create_autonomy_request_from_policy_result(
        agent_run=run,
        capability=AutonomyCapability.PUBLISH,
        policy_result=policy_result,
        operation_name="release",
        is_mutation=True,
        is_reversible=False,
        is_external=True,
        is_sensitive=True,
        approval_present=False,
    )

    assert request.autonomy_level == AgentAutonomyLevel.SUPERVISED_AUTONOMY
    assert request.policy_decision == "require_approval"
    assert request.operation_name == "release"
    assert request.is_mutation is True
    assert request.is_reversible is False
    assert request.is_external is True
    assert request.is_sensitive is True


def test_policy_adapter_does_not_infer_flags_from_operation_name() -> None:
    run = _make_agent_run(4)
    policy_result = _make_policy_result(PolicyDecision.ALLOW, allowed=True)

    request = create_autonomy_request_from_policy_result(
        agent_run=run,
        capability=AutonomyCapability.EXECUTE_READ_ONLY,
        policy_result=policy_result,
        operation_name="delete_publish_pay_modify_permissions",
    )

    assert request.policy_decision == "allow"
    assert request.is_mutation is False
    assert request.is_reversible is True
    assert request.is_destructive is False
    assert request.is_external is False
    assert request.requires_spend is False
    assert request.changes_permissions is False
    assert request.changes_policy is False


@pytest.mark.parametrize(
    ("decision", "kwargs", "expected"),
    (
        (PolicyDecision.DENY, {"denied": True}, "deny"),
        (
            PolicyDecision.REQUIRE_APPROVAL,
            {"requires_approval": True},
            "require_approval",
        ),
        (
            PolicyDecision.REQUIRE_VALIDATION,
            {"requires_validation": True},
            "require_validation",
        ),
        (PolicyDecision.PAUSE, {"paused": True}, "pause"),
        (PolicyDecision.ALLOW, {"allowed": True}, "allow"),
    ),
)
def test_policy_adapter_normalizes_policy_decisions(
    decision: PolicyDecision,
    kwargs: dict[str, bool],
    expected: str,
) -> None:
    request = create_autonomy_request_from_policy_result(
        agent_run=_make_agent_run(4),
        capability=AutonomyCapability.EXECUTE_WORKFLOW,
        policy_result=_make_policy_result(decision, **kwargs),
    )

    assert request.policy_decision == expected


def test_policy_adapter_rejects_invalid_inputs() -> None:
    policy_result = _make_policy_result(PolicyDecision.ALLOW, allowed=True)

    with pytest.raises(AutonomyPolicyIntegrationError):
        create_autonomy_request_from_policy_result(
            agent_run=object(),
            capability=AutonomyCapability.REASON,
            policy_result=policy_result,
        )

    with pytest.raises(AutonomyPolicyIntegrationError):
        create_autonomy_request_from_policy_result(
            agent_run=_make_agent_run(),
            capability=AutonomyCapability.REASON,
            policy_result=object(),
        )
