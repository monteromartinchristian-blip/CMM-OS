"""Deterministic ranking policies for model candidates."""

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


def _cost_key(value: Decimal | None) -> Decimal:
    """Sort unknown prices after known prices."""

    return value if value is not None else Decimal("Infinity")


@dataclass(frozen=True, slots=True)
class ModelRankingPolicy:
    """Deterministic ordering applied after requirement filtering."""

    strategy: RankingStrategy = "lowest_cost"
    preferred_providers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        normalized = tuple(
            dict.fromkeys(
                provider.strip().lower()
                for provider in self.preferred_providers
                if provider.strip()
            )
        )
        object.__setattr__(self, "preferred_providers", normalized)

    def rank(
        self,
        models: tuple[ModelSpec, ...],
    ) -> tuple[ModelSpec, ...]:
        """Return candidates in a stable and reproducible order."""

        if self.strategy == "largest_context":
            return tuple(
                sorted(
                    models,
                    key=lambda model: (
                        -(
                            model.context_window
                            if model.context_window is not None
                            else -1
                        ),
                        model.qualified_id,
                    ),
                )
            )

        if self.strategy == "provider_preference":
            provider_positions = {
                provider: index
                for index, provider in enumerate(self.preferred_providers)
            }
            fallback_position = len(provider_positions)

            return tuple(
                sorted(
                    models,
                    key=lambda model: (
                        provider_positions.get(
                            model.provider_id,
                            fallback_position,
                        ),
                        _cost_key(model.input_cost_per_million),
                        _cost_key(model.output_cost_per_million),
                        model.qualified_id,
                    ),
                )
            )

        return tuple(
            sorted(
                models,
                key=lambda model: (
                    _cost_key(model.input_cost_per_million),
                    _cost_key(model.output_cost_per_million),
                    model.qualified_id,
                ),
            )
        )
