"""Ranking policies for suitable LLM model candidates."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from kernel.llm.model_catalog import ModelSpec

RankingStrategy = Literal[
    "lowest_cost",
    "largest_context",
    "provider_preference",
]


@dataclass(frozen=True, slots=True)
class ModelRankingPolicy:
    """Rules used to order models that already satisfy requirements."""

    strategy: RankingStrategy = "lowest_cost"
    preferred_providers: tuple[str, ...] = ()

    def rank(
        self,
        models: tuple[ModelSpec, ...],
    ) -> tuple[ModelSpec, ...]:
        """Return models ordered according to this policy."""

        if self.strategy == "largest_context":
            return tuple(
                sorted(
                    models,
                    key=lambda model: (
                        -model.context_window,
                        model.qualified_id.lower(),
                    ),
                )
            )

        if self.strategy == "provider_preference":
            priorities = {
                provider.strip().lower(): index
                for index, provider in enumerate(self.preferred_providers)
                if provider.strip()
            }

            return tuple(
                sorted(
                    models,
                    key=lambda model: (
                        priorities.get(model.provider.lower(), len(priorities)),
                        *_lowest_cost_key(model),
                    ),
                )
            )

        return tuple(sorted(models, key=_lowest_cost_key))


def _lowest_cost_key(
    model: ModelSpec,
) -> tuple[bool, Decimal, str]:
    input_cost = model.input_cost_per_million
    output_cost = model.output_cost_per_million

    has_unknown_cost = input_cost is None or output_cost is None
    total_cost = (input_cost or Decimal(0)) + (output_cost or Decimal(0))

    return (
        has_unknown_cost,
        total_cost,
        model.qualified_id.lower(),
    )
