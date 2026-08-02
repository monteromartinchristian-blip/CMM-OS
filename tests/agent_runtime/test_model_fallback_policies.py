import json
from decimal import Decimal

import pytest

from cmm.agent_runtime.enums import RecoveryReasonCode, RecoveryStrategy
from cmm.agent_runtime.model_fallback_contracts import (
    ModelAttemptHistory,
    ModelAttemptResult,
    ModelFallbackAction,
    ModelFallbackContext,
    ModelFallbackDecision,
    ModelFallbackPolicy,
    ModelFallbackTrigger,
)
from cmm.agent_runtime.model_fallback_decision_engine import (
    ModelFallbackDecisionEngine,
)
from cmm.agent_runtime.model_fallback_errors import InvalidModelFallbackContractError
from cmm.agent_runtime.model_fallback_recovery_adapter import (
    ModelFallbackRecoveryAdapter,
)
from cmm.agent_runtime.workflow_planner_contracts import AgentWorkflowOperation
from kernel.llm.model_ranking import ModelRankingPolicy
from kernel.llm.model_router import (
    RoutingCandidate,
    RoutingDecision,
)
from kernel.llm.model_selection import ModelRequirements


def _routing() -> RoutingDecision:
    requirements = ModelRequirements(reasoning=True)
    candidates = (
        RoutingCandidate(1, "p1/m1", "p1", "m1", Decimal(1), Decimal(1), 100),
        RoutingCandidate(2, "p1/m2", "p1", "m2", Decimal(1), Decimal(1), 100),
        RoutingCandidate(3, "p2/m3", "p2", "m3", Decimal(1), Decimal(1), 100),
    )
    return RoutingDecision(
        id="routing-1",
        status="selected",
        selected_model_id="m1",
        selected_provider_id="p1",
        candidates=candidates,
        rejected_models=(),
        requirements=requirements,
        ranking_policy=ModelRankingPolicy(),
    )


def _context(**kwargs: object) -> ModelFallbackContext:
    policy = kwargs.pop("policy", ModelFallbackPolicy())
    result = ModelAttemptResult(
        operation_id="op-1",
        attempt_index=1,
        model_id="m1",
        provider_id="p1",
        trigger=ModelFallbackTrigger.TIMEOUT,
        estimated_cost=Decimal("0.01"),
        actual_cost=Decimal("0.01"),
        **kwargs,
    )
    return ModelFallbackContext(
        operation_id="op-1",
        workflow_id="wf-1",
        routing_decision=_routing(),
        effective_requirements=ModelRequirements(reasoning=True),
        latest_result=result,
        history=ModelAttemptHistory((result,)),
        policy=policy,
        approval={"approved": False},
        budget={"available": True},
    )


def test_timeout_selects_next_routing_candidate_and_is_serializable() -> None:
    decision = ModelFallbackDecisionEngine().decide(_context())

    assert decision.action is ModelFallbackAction.NEXT_ROUTING_CANDIDATE
    assert decision.selected_model_id == "m2"
    assert decision.selected_provider_id == "p1"
    assert decision.to_dict()["action"] == "next_routing_candidate"


def test_exhausted_attempts_fail_closed() -> None:
    policy = ModelFallbackPolicy(maximum_attempts=1)
    decision = ModelFallbackDecisionEngine().decide(_context(policy=policy))

    assert decision.action is ModelFallbackAction.FAIL_TERMINAL
    assert "maximum_attempts_exhausted" in decision.reason_codes


def test_premium_requires_approval_and_requirements_are_preserved() -> None:
    policy = ModelFallbackPolicy(
        actions=(ModelFallbackAction.SELECT_HIGHER_QUALITY_MODEL,),
        allow_premium_with_approval=True,
    )
    context = _context(policy=policy)
    decision = ModelFallbackDecisionEngine().decide(context)

    assert decision.action is ModelFallbackAction.SELECT_HIGHER_QUALITY_MODEL
    assert decision.selected_model_id == "m2"
    assert decision.effective_requirements == context.effective_requirements


def test_history_excludes_used_model_and_provider() -> None:
    policy = ModelFallbackPolicy(exclude_failed_provider=True)
    result = ModelAttemptResult(
        operation_id="op-1",
        attempt_index=2,
        model_id="m2",
        provider_id="p1",
        trigger=ModelFallbackTrigger.MODEL_UNAVAILABLE,
    )
    context = _context(policy=policy)
    context = ModelFallbackContext(
        operation_id=context.operation_id,
        workflow_id=context.workflow_id,
        routing_decision=context.routing_decision,
        effective_requirements=context.effective_requirements,
        latest_result=result,
        history=ModelAttemptHistory((context.latest_result, result)),
        policy=context.policy,
        approval=context.approval,
        budget=context.budget,
    )

    decision = ModelFallbackDecisionEngine().decide(context)

    assert decision.action is ModelFallbackAction.NEXT_ROUTING_CANDIDATE
    assert decision.selected_model_id == "m3"
    assert "provider_excluded:p1" in decision.reason_codes


def test_operation_fallback_policy_round_trip_and_recovery_adapter() -> None:
    operation = AgentWorkflowOperation(
        id="op-1",
        task_id="task-1",
        operation_name="llm.complete",
        model_fallback_policy=ModelFallbackPolicy(),
    )
    restored = AgentWorkflowOperation.from_dict(operation.to_dict())
    assert restored.model_fallback_policy == operation.model_fallback_policy

    decision = ModelFallbackDecisionEngine().decide(_context())
    recovery = ModelFallbackRecoveryAdapter().to_recovery_decision(
        decision, recovery_context_id="recovery-1"
    )
    assert recovery.strategy is RecoveryStrategy.RETRY
    assert recovery.idempotency_key == decision.idempotency_key


def test_context_and_all_decision_contracts_are_json_round_trippable() -> None:
    context = _context()
    assert json.dumps(context.to_dict())
    assert json.dumps(context.history.to_dict())
    restored = ModelFallbackContext.from_dict(context.to_dict())
    assert restored.to_dict() == context.to_dict()
    decision = ModelFallbackDecisionEngine().decide(context)
    assert ModelFallbackDecision.from_dict(decision.to_dict()) == decision


def test_policy_from_dict_preserves_defaults_and_explicit_empty_actions() -> None:
    default = ModelFallbackPolicy()
    assert ModelFallbackPolicy.from_dict({}) == default
    assert ModelFallbackPolicy.from_dict({"actions": []}).actions == ()


def test_context_without_policy_uses_the_default_policy() -> None:
    payload = _context().to_dict()
    payload.pop("policy")
    restored = ModelFallbackContext.from_dict(payload)
    assert restored.policy == ModelFallbackPolicy()


def test_context_rejects_invalid_history_and_policy_types() -> None:
    context = _context()
    kwargs = {
        "operation_id": context.operation_id,
        "workflow_id": context.workflow_id,
        "routing_decision": context.routing_decision,
        "effective_requirements": context.effective_requirements,
        "latest_result": context.latest_result,
        "history": {},
        "policy": context.policy,
    }
    with pytest.raises(InvalidModelFallbackContractError):
        ModelFallbackContext(**kwargs)

    kwargs["history"] = context.history
    kwargs["policy"] = {}
    with pytest.raises(InvalidModelFallbackContractError):
        ModelFallbackContext(**kwargs)


@pytest.mark.parametrize(
    "field", ("approval", "budget", "privacy", "policy_context", "metadata")
)
@pytest.mark.parametrize("value", ([], "invalid", True))
def test_context_rejects_non_mapping_snapshots(field: str, value: object) -> None:
    context = _context()
    kwargs = {
        "operation_id": context.operation_id,
        "workflow_id": context.workflow_id,
        "routing_decision": context.routing_decision,
        "effective_requirements": context.effective_requirements,
        "latest_result": context.latest_result,
        "history": context.history,
        "policy": context.policy,
        "approval": context.approval,
        "budget": context.budget,
        "privacy": context.privacy,
        "policy_context": context.policy_context,
        "metadata": context.metadata,
    }
    kwargs[field] = value
    with pytest.raises(InvalidModelFallbackContractError):
        ModelFallbackContext(**kwargs)


def test_history_rejects_inconsistent_indices_and_operations() -> None:
    first = ModelAttemptResult(
        operation_id="op-1",
        attempt_index=2,
        model_id="m1",
        provider_id="p1",
        trigger=ModelFallbackTrigger.TIMEOUT,
    )
    with pytest.raises(InvalidModelFallbackContractError):
        ModelAttemptHistory((first, first))
    with pytest.raises(InvalidModelFallbackContractError):
        ModelAttemptHistory(
            (
                first,
                ModelAttemptResult(
                    operation_id="op-2",
                    attempt_index=3,
                    model_id="m2",
                    provider_id="p1",
                    trigger=ModelFallbackTrigger.TIMEOUT,
                ),
            )
        )


def test_fallback_candidates_are_requested_through_injected_router() -> None:
    calls: list[str] = []

    def fallback_provider(decision: RoutingDecision) -> tuple[RoutingCandidate, ...]:
        calls.append(decision.id)
        return decision.candidates[1:]

    decision = ModelFallbackDecisionEngine(fallback_provider=fallback_provider).decide(
        _context()
    )
    assert decision.selected_model_id == "m2"
    assert calls == ["routing-1"]


def test_invalid_candidate_is_skipped_and_reason_is_recorded() -> None:
    context = _context()
    routing = RoutingDecision(
        id=context.routing_decision.id,
        status=context.routing_decision.status,
        selected_model_id=context.routing_decision.selected_model_id,
        selected_provider_id=context.routing_decision.selected_provider_id,
        candidates=(
            RoutingCandidate(1, "p1/m1", "p1", "m1", Decimal(1), Decimal(1), 100),
            RoutingCandidate(2, "p1/m2", "p1", "m2", Decimal(2), Decimal(2), 100),
        ),
        rejected_models=context.routing_decision.rejected_models,
        requirements=context.routing_decision.requirements,
        ranking_policy=context.routing_decision.ranking_policy,
    )
    context = ModelFallbackContext(
        operation_id=context.operation_id,
        workflow_id=context.workflow_id,
        routing_decision=routing,
        effective_requirements=ModelRequirements(
            reasoning=True, maximum_input_cost_per_million=Decimal(1)
        ),
        latest_result=context.latest_result,
        history=context.history,
        policy=context.policy,
        budget=context.budget,
    )
    decision = ModelFallbackDecisionEngine().decide(context)
    assert decision.action is ModelFallbackAction.REROUTE
    assert "candidate_cost_exceeded:p1/m2" in decision.reason_codes


def test_premium_approval_is_only_requested_when_explicitly_required() -> None:
    policy = ModelFallbackPolicy(
        actions=(
            ModelFallbackAction.SELECT_HIGHER_QUALITY_MODEL,
            ModelFallbackAction.NEXT_ROUTING_CANDIDATE,
        ),
        allow_premium_with_approval=True,
    )
    context = _context(policy=policy)
    decision = ModelFallbackDecisionEngine().decide(context)
    assert decision.action is ModelFallbackAction.NEXT_ROUTING_CANDIDATE

    context = ModelFallbackContext(
        operation_id=context.operation_id,
        workflow_id=context.workflow_id,
        routing_decision=context.routing_decision,
        effective_requirements=context.effective_requirements,
        latest_result=context.latest_result,
        history=context.history,
        policy=policy,
        approval=context.approval,
        budget=context.budget,
        policy_context={"premium_required": True},
    )
    decision = ModelFallbackDecisionEngine().decide(context)
    assert decision.action is ModelFallbackAction.REQUEST_APPROVAL


def test_recovery_adapter_preserves_structured_reason_codes() -> None:
    context = _context()
    context = ModelFallbackContext(
        operation_id=context.operation_id,
        workflow_id=context.workflow_id,
        routing_decision=context.routing_decision,
        effective_requirements=context.effective_requirements,
        latest_result=ModelAttemptResult(
            operation_id="op-1",
            attempt_index=1,
            model_id="m1",
            provider_id="p1",
            trigger=ModelFallbackTrigger.BUDGET_EXHAUSTED,
        ),
        history=ModelAttemptHistory(
            (
                ModelAttemptResult(
                    operation_id="op-1",
                    attempt_index=1,
                    model_id="m1",
                    provider_id="p1",
                    trigger=ModelFallbackTrigger.BUDGET_EXHAUSTED,
                ),
            )
        ),
        policy=context.policy,
        budget={"available": False},
    )
    decision = ModelFallbackDecisionEngine().decide(context)
    recovery = ModelFallbackRecoveryAdapter().to_recovery_decision(
        decision, recovery_context_id="recovery-1"
    )
    assert RecoveryReasonCode.BUDGET_EXHAUSTED in recovery.reason_codes


@pytest.mark.parametrize(
    ("requested_action", "expected"),
    [
        (ModelFallbackAction.REOBSERVE, ModelFallbackAction.REOBSERVE),
        (ModelFallbackAction.REPLAN, ModelFallbackAction.REPLAN),
        (ModelFallbackAction.PAUSE, ModelFallbackAction.PAUSE),
    ],
)
def test_requested_recovery_actions_are_reachable(
    requested_action: ModelFallbackAction,
    expected: ModelFallbackAction,
) -> None:
    context = _context()
    policy = ModelFallbackPolicy(actions=(requested_action,))
    context = ModelFallbackContext(
        operation_id=context.operation_id,
        workflow_id=context.workflow_id,
        routing_decision=context.routing_decision,
        effective_requirements=context.effective_requirements,
        latest_result=context.latest_result,
        history=context.history,
        policy=policy,
        budget=context.budget,
        policy_context={"requested_action": requested_action.value},
    )
    assert ModelFallbackDecisionEngine().decide(context).action is expected


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("privacy", {"compatible": False}, "privacy_conflict"),
        ("policy_context", {"allowed": False}, "policy_denied"),
        ("budget", {"available": False}, "budget_exhausted"),
    ],
)
def test_restricted_precedence_escalates_only_when_enabled(
    field: str,
    value: object,
    reason: str,
) -> None:
    context = _context()
    policy = ModelFallbackPolicy(actions=(ModelFallbackAction.ESCALATE,))
    kwargs = {
        "operation_id": context.operation_id,
        "workflow_id": context.workflow_id,
        "routing_decision": context.routing_decision,
        "effective_requirements": context.effective_requirements,
        "latest_result": context.latest_result,
        "history": context.history,
        "policy": policy,
        "approval": context.approval,
        "budget": context.budget,
        "privacy": context.privacy,
        "policy_context": context.policy_context,
    }
    kwargs[field] = value
    decision = ModelFallbackDecisionEngine().decide(ModelFallbackContext(**kwargs))
    assert decision.action is ModelFallbackAction.ESCALATE
    assert reason in decision.reason_codes


def test_idempotency_changes_for_policy_or_routing_inputs() -> None:
    first = ModelFallbackDecisionEngine().decide(_context())
    base = _context()
    changed = ModelFallbackDecisionEngine().decide(
        ModelFallbackContext(
            operation_id="op-1",
            workflow_id="wf-1",
            routing_decision=_routing(),
            effective_requirements=ModelRequirements(reasoning=False),
            latest_result=base.latest_result,
            history=base.history,
            policy=ModelFallbackPolicy(version="2"),
            budget={"available": True},
        )
    )
    assert first.idempotency_key != changed.idempotency_key
