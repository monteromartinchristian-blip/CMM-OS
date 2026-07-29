"""Thin adapter from economic decisions to the canonical ActionBudget service."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

from .action_budget_contracts import ActionBudget, BudgetAllocation, BudgetReservation
from .action_budget_service import ActionBudgetService
from .economic_budget_contracts import ModelCostEstimate
from .economic_budget_errors import EconomicBudgetError
from .economic_budget_resolver import EconomicBudgetResolver
from .enums import BudgetResourceType


class EconomicBudgetActionBudgetAdapter:
    def __init__(self, service: ActionBudgetService) -> None:
        self.service = service

    def ensure_action_budget(
        self,
        economic_budget_id: str,
        *,
        agent_run_id: str,
        maximum_cost: Decimal,
        currency: str,
        warning_threshold_percent: int = 80,
    ) -> ActionBudget:
        existing = self.service.find_budget_by_agent_run(agent_run_id)
        if existing is not None:
            if existing.currency.upper() != currency.upper():
                raise EconomicBudgetError("ActionBudget and economic budget currency differs")
            current_limit = existing.limit_for(BudgetResourceType.COST)
            if current_limit is None or current_limit > maximum_cost:
                try:
                    existing, _ = self.service.decrease_budget(
                        existing.id,
                        BudgetResourceType.COST,
                        new_limit=maximum_cost,
                        reason_codes=("budget.economic_limit_reconciled",),
                    )
                except Exception as exc:
                    raise EconomicBudgetError(
                        "cannot safely reduce existing ActionBudget cost limit below committed usage"
                    ) from exc
            return existing
        return self.service.create_budget(
            agent_run_id,
            {BudgetResourceType.COST: maximum_cost},
            currency=currency.upper(),
            warning_threshold=Decimal(warning_threshold_percent) / Decimal(100),
            budget_id=economic_budget_id,
            metadata={"economic_budget_id": economic_budget_id},
        )

    def reserve(
        self,
        budget: ActionBudget,
        estimate: ModelCostEstimate,
        *,
        goal_id: str,
        workflow_id: str,
        operation_id: str,
        run_id: str,
        model_id: str,
        provider_id: str,
        routing_decision: str | None = None,
        estimate_version: str = "1",
    ) -> BudgetReservation:
        if not estimate.complete:
            raise EconomicBudgetError("cannot reserve an incomplete economic cost estimate")
        if budget.currency.upper() != estimate.currency.upper():
            raise EconomicBudgetError("ActionBudget and model cost currency differs")
        key_payload = {
            "goal_id": goal_id, "workflow_id": workflow_id, "operation_id": operation_id,
            "run_id": run_id, "budget_id": budget.id, "model_id": model_id,
            "provider_id": provider_id, "routing_decision": routing_decision,
            "cost": str(estimate.total_cost), "currency": estimate.currency,
            "estimate_version": estimate_version,
        }
        key = "economic:" + hashlib.sha256(json.dumps(key_payload, sort_keys=True).encode()).hexdigest()
        return self.service.reserve(
            budget.id,
            [BudgetAllocation(BudgetResourceType.COST, estimate.total_cost)],
            operation_id=operation_id,
            workflow_id=workflow_id,
            idempotency_key=key,
        )

    @staticmethod
    def evaluate_estimate(*args, **kwargs):
        return EconomicBudgetResolver.decide(*args, **kwargs)

    @staticmethod
    def evaluate_actual(*args, **kwargs):
        return EconomicBudgetResolver.decide_actual(*args, **kwargs)

    def confirm(
        self,
        reservation_id: str,
        actual_cost: Decimal | ModelCostEstimate,
        *,
        currency: str | None = None,
    ):
        reservation = self.service.get_reservation(reservation_id)
        budget = self.service.get_budget(reservation.budget_id)
        if isinstance(actual_cost, ModelCostEstimate):
            actual_amount = actual_cost.total_cost
            actual_currency = actual_cost.currency
        else:
            actual_amount = actual_cost
            actual_currency = currency or budget.currency
        if actual_currency.upper() != budget.currency.upper():
            raise EconomicBudgetError("ActionBudget and actual cost currency differs")
        return self.service.confirm(
            reservation_id,
            [BudgetAllocation(BudgetResourceType.COST, actual_amount)],
        )

    def release(self, reservation_id: str, reason: str = "not_executed") -> BudgetReservation:
        return self.service.release(reservation_id, reason=reason)

    def fail(
        self,
        reservation_id: str,
        partial_cost: Decimal = Decimal(0),
        *,
        currency: str | None = None,
    ):
        reservation = self.service.get_reservation(reservation_id)
        budget = self.service.get_budget(reservation.budget_id)
        if (currency or budget.currency).upper() != budget.currency.upper():
            raise EconomicBudgetError("ActionBudget and partial cost currency differs")
        allocations = [BudgetAllocation(BudgetResourceType.COST, partial_cost)] if partial_cost else []
        return self.service.fail(reservation_id, consumed_allocations=allocations)
