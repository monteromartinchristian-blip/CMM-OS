"""Restrictive hierarchical economic budget resolution."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from decimal import Decimal
from typing import Any

from .action_budget_contracts import ActionBudget
from .economic_budget_contracts import (
    EconomicBudget,
    EconomicBudgetAction,
    EconomicBudgetDecision,
    EconomicBudgetStatus,
    ModelCostEstimate,
    ResolvedEconomicBudget,
)
from .economic_budget_errors import EconomicBudgetResolutionError
from .enums import ActionBudgetStatus, BudgetResourceType


class EconomicBudgetResolver:
    def resolve(
        self,
        *,
        goal: EconomicBudget | None = None,
        workflow: EconomicBudget | None = None,
        operation: EconomicBudget | None = None,
        policy: EconomicBudget | None = None,
        approval: EconomicBudget | None = None,
    ) -> ResolvedEconomicBudget:
        sources = tuple(
            x for x in (goal, workflow, operation, policy, approval) if x is not None
        )
        if not sources:
            raise EconomicBudgetResolutionError(
                "at least one economic budget source is required"
            )
        currencies = {source.currency for source in sources}
        if len(currencies) != 1:
            raise EconomicBudgetResolutionError(
                "economic budget sources must use the same currency"
            )

        def minimum(name: str):
            values = [
                getattr(source, name)
                for source in sources
                if getattr(source, name) is not None
            ]
            return min(values) if values else None

        reasons = [f"budget.source.{source.source.value}" for source in sources]
        metadata: dict[str, object] = {}
        for source in sources:
            for key, value in source.metadata.items():
                if key in metadata and metadata[key] != value:
                    reasons.append(f"budget.metadata_conflict.{key}")
                metadata[key] = value
        if any(
            source.source.value == "policy"
            and source.status is EconomicBudgetStatus.DENIED
            for source in sources
        ):
            reasons.append("budget.policy_denied")
        return ResolvedEconomicBudget(
            maximum_cost=minimum("maximum_cost"),
            maximum_estimated_cost_per_operation=minimum(
                "maximum_estimated_cost_per_operation"
            ),
            maximum_actual_cost_per_operation=minimum(
                "maximum_actual_cost_per_operation"
            ),
            maximum_input_tokens=minimum("maximum_input_tokens"),
            maximum_output_tokens=minimum("maximum_output_tokens"),
            maximum_total_tokens=minimum("maximum_total_tokens"),
            currency=next(iter(currencies)),
            premium_allowed=all(source.premium_allowed for source in sources),
            overrun_tolerance=min(source.overrun_tolerance for source in sources),
            warning_threshold_percent=min(
                source.warning_threshold_percent for source in sources
            ),
            critical_threshold_percent=min(
                source.critical_threshold_percent for source in sources
            ),
            on_warning=self._most_restrictive_action(
                source.on_warning for source in sources
            ),
            on_exhaustion=self._most_restrictive_action(
                source.on_exhaustion for source in sources
            ),
            allow_overrun_with_approval=all(
                source.allow_overrun_with_approval for source in sources
            ),
            savings_mode=any(source.savings_mode for source in sources),
            provenance=tuple(
                f"{source.source.value}:{source.id}" for source in sources
            ),
            reason_codes=tuple(reasons),
            metadata=metadata,
            policy_denied=any(
                source.source.value == "policy"
                and source.status is EconomicBudgetStatus.DENIED
                for source in sources
            ),
        )

    @staticmethod
    def decide(
        estimate: ModelCostEstimate,
        resolved: ResolvedEconomicBudget,
        *,
        action_budget: ActionBudget | None = None,
        used_cost: Decimal = Decimal(0),
        reserved_cost: Decimal = Decimal(0),
        available_cost: Decimal | None = None,
        policy_denied: bool = False,
    ) -> EconomicBudgetDecision:
        """Evaluate an estimate in the conservative order used by Phase 9.31."""
        if action_budget is not None:
            used_cost = Decimal(action_budget.used_for(BudgetResourceType.COST))
            reserved_cost = Decimal(action_budget.reserved_for(BudgetResourceType.COST))
            available_cost = action_budget.available_for(BudgetResourceType.COST)
            if action_budget.currency.upper() != estimate.currency.upper():
                return EconomicBudgetDecision(
                    EconomicBudgetAction.DENY,
                    ("budget.currency_conflict",),
                    replace(resolved, status=EconomicBudgetStatus.DENIED),
                )
            resolved = replace(
                resolved,
                warning_threshold_percent=int(action_budget.warning_threshold * 100),
                critical_threshold_percent=int(action_budget.critical_threshold * 100),
            )
            if action_budget.status in (
                ActionBudgetStatus.PAUSED,
                ActionBudgetStatus.CANCELLED,
            ):
                return EconomicBudgetDecision(
                    EconomicBudgetAction.PAUSE,
                    (f"budget.action_budget_{action_budget.status.value}",),
                    replace(resolved, status=EconomicBudgetStatus.PAUSED),
                )
            if action_budget.status in (
                ActionBudgetStatus.EXHAUSTED,
                ActionBudgetStatus.COMPLETED,
            ):
                return EconomicBudgetDecision(
                    EconomicBudgetAction.DENY,
                    (
                        f"budget.action_budget_{action_budget.status.value}",
                        "budget.exhausted",
                    ),
                    replace(
                        resolved, status=EconomicBudgetStatus.EXHAUSTED, exhausted=True
                    ),
                )

        if policy_denied or resolved.policy_denied:
            return EconomicBudgetDecision(
                EconomicBudgetAction.DENY,
                (*resolved.reason_codes, "budget.policy_denied"),
                replace(
                    resolved, status=EconomicBudgetStatus.DENIED, policy_denied=True
                ),
            )

        cost_limit_exists = any(
            value is not None
            for value in (
                resolved.maximum_cost,
                resolved.maximum_estimated_cost_per_operation,
            )
        )
        token_limit_requires_count = any(
            limit is not None
            for limit in (
                resolved.maximum_input_tokens,
                resolved.maximum_output_tokens,
                resolved.maximum_total_tokens,
            )
        )
        if not estimate.complete and cost_limit_exists:
            return EconomicBudgetResolver._blocked(
                resolved, "budget.incomplete_estimate", "budget.price_unknown"
            )
        if token_limit_requires_count and any(
            count is None
            for count in (
                estimate.input_tokens,
                estimate.output_tokens,
                estimate.total_tokens,
            )
        ):
            return EconomicBudgetResolver._blocked(
                resolved, "budget.incomplete_token_counts"
            )

        violations: list[str] = []
        if (
            resolved.maximum_input_tokens is not None
            and estimate.input_tokens > resolved.maximum_input_tokens
        ):
            violations.append("budget.input_tokens_exceeded")
        if (
            resolved.maximum_output_tokens is not None
            and estimate.output_tokens > resolved.maximum_output_tokens
        ):
            violations.append("budget.output_tokens_exceeded")
        if (
            resolved.maximum_total_tokens is not None
            and estimate.total_tokens > resolved.maximum_total_tokens
        ):
            violations.append("budget.total_tokens_exceeded")
        if (
            resolved.maximum_estimated_cost_per_operation is not None
            and estimate.total_cost > resolved.maximum_estimated_cost_per_operation
        ):
            violations.append("budget.estimated_cost_per_operation_exceeded")
        if violations:
            return EconomicBudgetDecision(
                EconomicBudgetAction.DENY,
                tuple(violations),
                replace(
                    resolved,
                    status=EconomicBudgetStatus.DENIED,
                    estimated_cost_excessive=True,
                    estimated_cost=estimate.total_cost,
                ),
            )

        if resolved.maximum_cost is not None:
            if available_cost is None:
                available_cost = resolved.maximum_cost - used_cost - reserved_cost
            if estimate.total_cost > available_cost:
                return EconomicBudgetResolver._blocked(
                    resolved,
                    "budget.total_cost_unavailable",
                    "budget.exhausted",
                    estimated_cost_excessive=True,
                    exhausted=True,
                )

        projected = used_cost + reserved_cost + estimate.total_cost
        utilization = (
            projected / resolved.maximum_cost
            if resolved.maximum_cost is not None and resolved.maximum_cost > 0
            else Decimal(0)
        )
        status = EconomicBudgetStatus.AVAILABLE
        action = EconomicBudgetAction.ALLOW_WITH_RESERVATION
        reasons = ["budget.allow_with_reservation"]
        warning = False
        near = False
        if utilization * 100 >= resolved.critical_threshold_percent:
            status, warning, near = EconomicBudgetStatus.NEAR_EXHAUSTION, True, True
            reasons.append("budget.near_exhaustion")
            action = EconomicBudgetAction.from_value(resolved.on_warning)
        elif utilization * 100 >= resolved.warning_threshold_percent:
            status, warning = EconomicBudgetStatus.WARNING, True
            reasons.append("budget.warning_threshold_reached")
            action = EconomicBudgetAction.from_value(resolved.on_warning)
        return EconomicBudgetDecision(
            action,
            tuple(reasons),
            replace(
                resolved,
                status=status,
                warning=warning,
                near_exhaustion=near,
                estimated_cost=estimate.total_cost,
            ),
        )

    @staticmethod
    def decide_actual(
        *,
        actual_cost: Decimal,
        resolved: ResolvedEconomicBudget,
        estimated_cost: Decimal = Decimal(0),
        reserved_cost: Decimal = Decimal(0),
        used_cost: Decimal = Decimal(0),
        available_cost: Decimal | None = None,
        action_budget: ActionBudget | None = None,
        currency: str | None = None,
    ) -> EconomicBudgetDecision:
        """Evaluate actual spend before delegating confirmation to ActionBudgetService."""
        actual_cost = Decimal(actual_cost)
        if currency is not None and currency.upper() != resolved.currency.upper():
            return EconomicBudgetDecision(
                EconomicBudgetAction.DENY,
                ("budget.currency_conflict",),
                replace(
                    resolved,
                    status=EconomicBudgetStatus.DENIED,
                    actual_cost=actual_cost,
                    estimated_cost=estimated_cost,
                ),
            )
        if action_budget is not None:
            used_cost = Decimal(action_budget.used_for(BudgetResourceType.COST))
            reserved_cost = Decimal(action_budget.reserved_for(BudgetResourceType.COST))
            available_cost = action_budget.available_for(BudgetResourceType.COST)
            if (
                currency is not None
                and action_budget.currency.upper() != currency.upper()
            ):
                return EconomicBudgetDecision(
                    EconomicBudgetAction.DENY,
                    ("budget.currency_conflict",),
                    replace(
                        resolved,
                        status=EconomicBudgetStatus.DENIED,
                        actual_cost=actual_cost,
                        estimated_cost=estimated_cost,
                    ),
                )
            if action_budget.status in (
                ActionBudgetStatus.PAUSED,
                ActionBudgetStatus.CANCELLED,
            ):
                return EconomicBudgetDecision(
                    EconomicBudgetAction.PAUSE,
                    ("budget.action_budget_paused",),
                    replace(
                        resolved,
                        status=EconomicBudgetStatus.PAUSED,
                        estimated_cost=estimated_cost,
                        actual_cost=actual_cost,
                    ),
                )
            if action_budget.status in (
                ActionBudgetStatus.EXHAUSTED,
                ActionBudgetStatus.COMPLETED,
            ):
                return EconomicBudgetDecision(
                    EconomicBudgetAction.DENY,
                    ("budget.exhausted",),
                    replace(
                        resolved,
                        status=EconomicBudgetStatus.EXHAUSTED,
                        exhausted=True,
                        estimated_cost=estimated_cost,
                        actual_cost=actual_cost,
                    ),
                )

        violations: list[str] = []
        if (
            resolved.maximum_actual_cost_per_operation is not None
            and actual_cost > resolved.maximum_actual_cost_per_operation
        ):
            violations.append("budget.actual_cost_per_operation_exceeded")
        if actual_cost > reserved_cost + resolved.overrun_tolerance:
            violations.append("budget.actual_cost_overrun_exceeded")
        if resolved.maximum_cost is not None:
            capacity = (
                available_cost + reserved_cost
                if available_cost is not None
                else resolved.maximum_cost - used_cost
            )
            if actual_cost > capacity:
                violations.append("budget.actual_cost_unavailable")
        excessive = bool(violations)
        if excessive:
            action = (
                EconomicBudgetAction.REQUEST_APPROVAL
                if resolved.allow_overrun_with_approval
                else EconomicBudgetAction.PAUSE
            )
            status = (
                EconomicBudgetStatus.APPROVAL_REQUIRED
                if action is EconomicBudgetAction.REQUEST_APPROVAL
                else EconomicBudgetStatus.EXHAUSTED
            )
            return EconomicBudgetDecision(
                action,
                tuple(violations),
                replace(
                    resolved,
                    status=status,
                    actual_cost_excessive=True,
                    approval_required=action is EconomicBudgetAction.REQUEST_APPROVAL,
                    exhausted=status is EconomicBudgetStatus.EXHAUSTED,
                    estimated_cost=estimated_cost,
                    actual_cost=actual_cost,
                ),
            )
        return EconomicBudgetDecision(
            EconomicBudgetAction.ALLOW,
            ("budget.actual_cost_allowed",),
            replace(
                resolved,
                status=EconomicBudgetStatus.AVAILABLE,
                estimated_cost=estimated_cost,
                actual_cost=actual_cost,
            ),
        )

    @staticmethod
    def _blocked(
        resolved: ResolvedEconomicBudget, *codes: str, **flags: Any
    ) -> EconomicBudgetDecision:
        action = (
            EconomicBudgetAction.REQUEST_APPROVAL
            if resolved.allow_overrun_with_approval
            else EconomicBudgetAction.PAUSE
        )
        status = (
            EconomicBudgetStatus.APPROVAL_REQUIRED
            if action is EconomicBudgetAction.REQUEST_APPROVAL
            else EconomicBudgetStatus.EXHAUSTED
            if flags.get("exhausted")
            else EconomicBudgetStatus.PAUSED
        )
        return EconomicBudgetDecision(
            action,
            tuple(codes),
            replace(
                resolved,
                status=status,
                approval_required=action is EconomicBudgetAction.REQUEST_APPROVAL,
                **flags,
            ),
        )

    @staticmethod
    def _most_restrictive_action(actions: Iterable[str]) -> str:
        rank = {
            "warn": 0,
            "reduce_scope": 1,
            "request_approval": 2,
            "pause": 3,
            "deny": 4,
        }
        values = tuple(actions)
        return max(values, key=lambda value: rank.get(value, 4))
