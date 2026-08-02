from decimal import Decimal

import pytest

from cmm.agent_runtime.action_budget_contracts import BudgetAllocation
from cmm.agent_runtime.action_budget_service import ActionBudgetService
from cmm.agent_runtime.economic_budget_adapters import EconomicBudgetActionBudgetAdapter
from cmm.agent_runtime.economic_budget_calculator import ModelCostCalculator
from cmm.agent_runtime.economic_budget_contracts import (
    EconomicBudget,
    EconomicBudgetAction,
    EconomicBudgetDecision,
    EconomicBudgetSource,
    EconomicBudgetStatus,
    ModelCostEstimate,
    ResolvedEconomicBudget,
)
from cmm.agent_runtime.economic_budget_errors import InvalidEconomicBudgetContractError
from cmm.agent_runtime.economic_budget_resolver import EconomicBudgetResolver
from cmm.agent_runtime.enums import (
    BudgetResourceType,
    GoalKind,
    GoalStatus,
    WorkflowPlanRisk,
    WorkflowPlanStatus,
)
from cmm.agent_runtime.goal_contracts import Goal, GoalPriority
from cmm.agent_runtime.workflow_planner_contracts import (
    AgentWorkflowOperation,
    AgentWorkflowPlan,
)
from kernel.llm.model_catalog import ModelSpec


def test_economic_budget_round_trip_is_json_safe_and_immutable():
    budget = EconomicBudget(
        id="goal-budget-1",
        source=EconomicBudgetSource.GOAL,
        currency="eur",
        maximum_cost=Decimal("1.00"),
        metadata={"owner": "user"},
    )

    restored = EconomicBudget.from_dict(budget.to_dict())

    assert restored == budget
    assert budget.currency == "EUR"
    with pytest.raises(TypeError):
        budget.metadata["new"] = "value"


@pytest.mark.parametrize(
    "value", [True, Decimal("NaN"), Decimal("Infinity"), Decimal(-1)]
)
def test_economic_budget_rejects_unsafe_money(value):
    with pytest.raises(InvalidEconomicBudgetContractError):
        EconomicBudget(id="b1", maximum_cost=value)


def test_resolver_applies_restrictive_hierarchy_and_preserves_provenance():
    resolved = EconomicBudgetResolver().resolve(
        goal=EconomicBudget(
            id="g",
            source=EconomicBudgetSource.GOAL,
            maximum_cost=Decimal(10),
            maximum_input_tokens=1000,
            premium_allowed=True,
        ),
        workflow=EconomicBudget(
            id="w",
            source=EconomicBudgetSource.WORKFLOW,
            maximum_cost=Decimal(5),
            maximum_input_tokens=800,
            premium_allowed=False,
        ),
        operation=EconomicBudget(
            id="o",
            source=EconomicBudgetSource.OPERATION,
            maximum_cost=Decimal(2),
            maximum_input_tokens=900,
        ),
    )

    assert resolved.maximum_cost == Decimal(2)
    assert resolved.maximum_input_tokens == 800
    assert resolved.premium_allowed is False
    assert resolved.provenance == ("goal:g", "workflow:w", "operation:o")


def test_resolver_rejects_mixed_currencies():
    with pytest.raises(InvalidEconomicBudgetContractError):
        EconomicBudgetResolver().resolve(
            goal=EconomicBudget(id="g", currency="EUR"),
            workflow=EconomicBudget(id="w", currency="USD"),
        )


def test_model_cost_calculator_uses_decimal_catalog_prices():
    model = ModelSpec(
        id="model-a",
        provider_id="provider-a",
        input_cost_per_million=Decimal("2.00"),
        cached_input_cost_per_million=Decimal("0.50"),
        output_cost_per_million=Decimal("4.00"),
    )

    estimate = ModelCostCalculator().estimate(
        model,
        input_tokens=1_000_000,
        cached_input_tokens=100_000,
        output_tokens=500_000,
    )

    assert estimate == ModelCostEstimate(
        input_cost=Decimal("2.00"),
        cached_input_cost=Decimal("0.05"),
        output_cost=Decimal("2.00"),
        total_cost=Decimal("4.05"),
        currency="USD",
        complete=True,
        input_tokens=1_000_000,
        output_tokens=500_000,
        cached_input_tokens=100_000,
        total_tokens=1_600_000,
    )


def test_adapter_reserves_confirms_and_releases_canonical_cost_resource():
    service = ActionBudgetService()
    budget = service.create_budget(
        "run-1", {BudgetResourceType.COST: Decimal("5.00")}, budget_id="ab-1"
    )
    adapter = EconomicBudgetActionBudgetAdapter(service)
    estimate = ModelCostEstimate(
        input_cost=Decimal(1),
        cached_input_cost=Decimal(0),
        output_cost=Decimal(1),
        total_cost=Decimal(2),
        currency="EUR",
        complete=True,
    )

    reservation = adapter.reserve(
        budget,
        estimate,
        goal_id="goal-1",
        workflow_id="workflow-1",
        operation_id="operation-1",
        run_id="run-1",
        model_id="model-a",
        provider_id="provider-a",
    )
    adapter.confirm(reservation.id, Decimal("1.50"))

    assert service.get_budget("ab-1").used_for(BudgetResourceType.COST) == Decimal(
        "1.50"
    )


def test_adapter_uses_service_public_lookup_and_enforces_currency_on_reuse():
    service = ActionBudgetService()
    service.create_budget(
        "run-existing",
        {BudgetResourceType.COST: Decimal(5)},
        currency="USD",
        budget_id="ab-existing",
    )
    adapter = EconomicBudgetActionBudgetAdapter(service)

    with pytest.raises(Exception, match="currency"):
        adapter.ensure_action_budget(
            "economic-1",
            agent_run_id="run-existing",
            maximum_cost=Decimal(5),
            currency="EUR",
        )

    assert not hasattr(adapter, "repository")


def test_adapter_rejects_currency_mismatch_on_reserve_and_confirm():
    service = ActionBudgetService()
    budget = service.create_budget(
        "run-2", {BudgetResourceType.COST: Decimal(5)}, currency="EUR", budget_id="ab-2"
    )
    adapter = EconomicBudgetActionBudgetAdapter(service)
    estimate = ModelCostEstimate(
        Decimal(1), Decimal(0), Decimal(1), Decimal(2), currency="USD"
    )
    with pytest.raises(Exception, match="currency"):
        adapter.reserve(
            budget,
            estimate,
            goal_id="g",
            workflow_id="w",
            operation_id="o",
            run_id="r",
            model_id="m",
            provider_id="p",
        )

    reservation = adapter.reserve(
        budget,
        ModelCostEstimate(
            Decimal(1), Decimal(0), Decimal(1), Decimal(2), currency="EUR"
        ),
        goal_id="g",
        workflow_id="w",
        operation_id="o",
        run_id="r",
        model_id="m",
        provider_id="p",
    )
    with pytest.raises(Exception, match="currency"):
        adapter.confirm(reservation.id, Decimal(1), currency="USD")


def test_incomplete_estimate_is_explicit_and_cannot_be_reserved():
    model = ModelSpec(
        id="partial", provider_id="provider", output_cost_per_million=Decimal(2)
    )
    estimate = ModelCostCalculator().estimate(
        model, input_tokens=10, output_tokens=10, allow_partial=True
    )
    assert estimate.complete is False
    assert estimate.missing_prices == ("input",)
    assert estimate.known_cost == Decimal("0.00002")

    service = ActionBudgetService()
    budget = service.create_budget(
        "run-3", {BudgetResourceType.COST: Decimal(5)}, budget_id="ab-3"
    )
    with pytest.raises(Exception, match="incomplete"):
        EconomicBudgetActionBudgetAdapter(service).reserve(
            budget,
            estimate,
            goal_id="g",
            workflow_id="w",
            operation_id="o",
            run_id="r",
            model_id="m",
            provider_id="p",
        )


def test_incomplete_estimate_with_limit_fails_closed_in_resolver():
    model = ModelSpec(
        id="partial-limit", provider_id="provider", output_cost_per_million=Decimal(2)
    )
    estimate = ModelCostCalculator().estimate(
        model, input_tokens=10, output_tokens=10, allow_partial=True
    )
    resolved = EconomicBudgetResolver().resolve(
        goal=EconomicBudget(
            id="g-limit", maximum_cost=Decimal(1), allow_overrun_with_approval=False
        )
    )
    decision = EconomicBudgetResolver.decide(estimate, resolved)
    assert decision.decision is EconomicBudgetAction.PAUSE
    assert decision.resolved.status is EconomicBudgetStatus.PAUSED
    assert decision.to_snapshot()["available"] is False


def test_typed_budget_contracts_round_trip_state_and_actions():
    budget = EconomicBudget(
        id="typed",
        on_warning=EconomicBudgetAction.REQUEST_APPROVAL,
        on_exhaustion=EconomicBudgetAction.DENY,
        status=EconomicBudgetStatus.WARNING,
    )
    restored = EconomicBudget.from_dict(budget.to_dict())
    assert restored == budget
    resolved = ResolvedEconomicBudget.from_dict(
        ResolvedEconomicBudget(status=EconomicBudgetStatus.EXHAUSTED).to_dict()
    )
    assert resolved.status is EconomicBudgetStatus.EXHAUSTED


def test_economic_states_actions_and_snapshot_are_typed_and_explicit():
    decision = EconomicBudgetDecision(
        decision=EconomicBudgetAction.REQUEST_APPROVAL,
        resolved=ResolvedEconomicBudget(
            status=EconomicBudgetStatus.NEAR_EXHAUSTION,
            warning=True,
            near_exhaustion=True,
            approval_required=True,
            estimated_cost_excessive=True,
            estimated_cost=Decimal(2),
            actual_cost=Decimal(1),
            maximum_cost=Decimal(3),
        ),
    )
    snapshot = decision.to_snapshot()
    assert snapshot["status"] == "near_exhaustion"
    assert snapshot["warning"] is True
    assert snapshot["near_exhaustion"] is True
    assert snapshot["approval_required"] is True
    assert snapshot["estimated_cost_excessive"] is True
    assert snapshot["actual_cost_excessive"] is False
    assert EconomicBudgetStatus.from_value("paused") is EconomicBudgetStatus.PAUSED
    assert EconomicBudgetAction.from_value("deny") is EconomicBudgetAction.DENY


def test_decision_snapshot_is_consumable_by_fallback_budget_mapping():
    decision = EconomicBudgetDecision(
        decision="allow_with_reservation",
        reason_codes=("budget.available",),
        resolved=ResolvedEconomicBudget(maximum_cost=Decimal(3), currency="USD"),
    )

    snapshot = decision.to_snapshot()

    assert snapshot["available"] is True
    assert snapshot["currency"] == "USD"
    assert snapshot["maximum_cost"] == "3"
    assert snapshot["reason_codes"] == ["budget.available"]


def test_goal_and_workflow_contracts_preserve_optional_economic_budget():
    economic = EconomicBudget(id="goal-budget", maximum_cost=Decimal(4))
    goal = Goal(
        id="goal-1",
        title="Goal",
        description="Description",
        kind=GoalKind.PROJECT_IMPROVEMENT,
        status=GoalStatus.PROPOSED,
        priority=GoalPriority(),
        economic_budget=economic,
    )
    operation = AgentWorkflowOperation(
        id="op-1",
        task_id="task-1",
        operation_name="model_call",
        risk=WorkflowPlanRisk.NONE,
        economic_budget=EconomicBudget(
            id="op-budget", source="operation", maximum_cost=Decimal(1)
        ),
    )
    plan = AgentWorkflowPlan(
        id="plan-1",
        goal_id="goal-1",
        agent_run_id="run-1",
        workflow_id="workflow-1",
        status=WorkflowPlanStatus.DRAFT,
        operations=[operation],
        economic_budget=EconomicBudget(
            id="workflow-budget", source="workflow", maximum_cost=Decimal(2)
        ),
    )

    assert Goal.from_dict(goal.to_dict()).economic_budget == economic
    restored_plan = AgentWorkflowPlan.from_dict(plan.to_dict())
    assert restored_plan.economic_budget.maximum_cost == Decimal(2)
    assert restored_plan.operations[0].economic_budget.maximum_cost == Decimal(1)


def test_estimate_decision_applies_token_and_operation_limits():
    model = ModelSpec(
        id="limited",
        provider_id="provider",
        input_cost_per_million=Decimal(1),
        output_cost_per_million=Decimal(1),
        cached_input_cost_per_million=Decimal(1),
    )
    estimate = ModelCostCalculator().estimate(
        model, input_tokens=11, output_tokens=20, cached_input_tokens=3
    )
    resolved = EconomicBudgetResolver().resolve(
        goal=EconomicBudget(
            id="limits",
            maximum_cost=Decimal(10),
            maximum_estimated_cost_per_operation=Decimal("0.00001"),
            maximum_input_tokens=10,
            maximum_output_tokens=10,
            maximum_total_tokens=30,
        )
    )
    decision = EconomicBudgetResolver.decide(estimate, resolved)
    assert decision.decision is EconomicBudgetAction.DENY
    assert "budget.input_tokens_exceeded" in decision.reason_codes


def test_estimate_decision_allows_valid_operation_and_marks_warning():
    estimate = ModelCostEstimate(
        Decimal(1),
        Decimal(0),
        Decimal("0.7"),
        Decimal("1.7"),
        currency="EUR",
        input_tokens=1,
        output_tokens=1,
        cached_input_tokens=0,
        total_tokens=2,
    )
    resolved = EconomicBudgetResolver().resolve(
        goal=EconomicBudget(
            id="warning", maximum_cost=Decimal(2), warning_threshold_percent=80
        )
    )
    decision = EconomicBudgetResolver.decide(estimate, resolved, used_cost=Decimal(0))
    assert decision.decision is EconomicBudgetAction.WARN
    assert decision.resolved.warning is True
    assert decision.resolved.status is EconomicBudgetStatus.WARNING


def test_actual_decision_handles_tolerance_and_approval():
    resolved = EconomicBudgetResolver().resolve(
        goal=EconomicBudget(
            id="actual",
            maximum_cost=Decimal(10),
            maximum_actual_cost_per_operation=Decimal(5),
            overrun_tolerance=Decimal("0.50"),
            allow_overrun_with_approval=True,
        )
    )
    decision = EconomicBudgetResolver.decide_actual(
        actual_cost=Decimal("5.75"),
        estimated_cost=Decimal(4),
        reserved_cost=Decimal(5),
        resolved=resolved,
    )
    assert decision.resolved.actual_cost_excessive is True
    assert decision.resolved.approval_required is True
    assert decision.decision is EconomicBudgetAction.REQUEST_APPROVAL


def test_ensure_action_budget_reconciles_more_permissive_existing_limit():
    service = ActionBudgetService()
    service.create_budget(
        "run-reconcile",
        {BudgetResourceType.COST: Decimal(10)},
        budget_id="ab-reconcile",
    )
    adapter = EconomicBudgetActionBudgetAdapter(service)
    budget = adapter.ensure_action_budget(
        "economic-reconcile",
        agent_run_id="run-reconcile",
        maximum_cost=Decimal(5),
        currency="EUR",
    )
    assert budget.limit_for(BudgetResourceType.COST) == Decimal(5)


def test_ensure_action_budget_preserves_existing_commitment_when_reduction_is_unsafe():
    service = ActionBudgetService()
    budget = service.create_budget(
        "run-committed",
        {BudgetResourceType.COST: Decimal(10)},
        budget_id="ab-committed",
    )
    reservation = service.reserve(
        budget.id, [BudgetAllocation(BudgetResourceType.COST, Decimal(6))]
    )
    with pytest.raises(Exception, match="committed|below"):
        EconomicBudgetActionBudgetAdapter(service).ensure_action_budget(
            "economic-committed",
            agent_run_id="run-committed",
            maximum_cost=Decimal(5),
            currency="EUR",
        )
    assert service.get_reservation(reservation.id).status.value == "reserved"
