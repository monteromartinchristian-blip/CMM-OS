"""Deterministic Decimal cost calculations using ModelSpec catalog prices."""

from __future__ import annotations

from decimal import Decimal

from kernel.llm.model_catalog import ModelSpec

from .economic_budget_contracts import ModelCostEstimate
from .economic_budget_errors import EconomicBudgetCostError


class ModelCostCalculator:
    """Calculate token costs without inventing or silently rounding prices."""

    _MILLION = Decimal(1_000_000)

    def estimate(
        self,
        model: ModelSpec,
        *,
        input_tokens: int,
        output_tokens: int,
        cached_input_tokens: int = 0,
        allow_partial: bool = False,
        currency: str = "USD",
    ) -> ModelCostEstimate:
        if not isinstance(model, ModelSpec):
            raise EconomicBudgetCostError("model must be a ModelSpec")
        tokens = {"input_tokens": input_tokens, "output_tokens": output_tokens, "cached_input_tokens": cached_input_tokens}
        for name, value in tokens.items():
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise EconomicBudgetCostError(f"{name} must be a non-negative integer")

        missing: list[str] = []
        input_cost = self._cost(input_tokens, model.input_cost_per_million, "input", missing)
        cached_cost = self._cost(cached_input_tokens, model.cached_input_cost_per_million, "cached_input", missing)
        output_cost = self._cost(output_tokens, model.output_cost_per_million, "output", missing)
        if missing and not allow_partial:
            raise EconomicBudgetCostError(f"unknown model prices: {', '.join(missing)}")
        total = input_cost + cached_cost + output_cost
        return ModelCostEstimate(
            input_cost, cached_cost, output_cost, total, currency, not missing,
            tuple(missing), total, input_tokens, output_tokens, cached_input_tokens,
            input_tokens + output_tokens + cached_input_tokens,
        )

    @staticmethod
    def _cost(tokens: int, price: Decimal | None, label: str, missing: list[str]) -> Decimal:
        if tokens == 0:
            return Decimal(0)
        if price is None:
            missing.append(label)
            return Decimal(0)
        return Decimal(tokens) * price / ModelCostCalculator._MILLION
