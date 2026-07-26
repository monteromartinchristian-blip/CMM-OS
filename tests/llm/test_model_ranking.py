from decimal import Decimal

from kernel.llm.model_catalog import ModelSpec
from kernel.llm.model_ranking import ModelRankingPolicy


def _models() -> tuple[ModelSpec, ...]:
    return (
        ModelSpec(
            id="cheap",
            provider="groq",
            context_window=32_768,
            input_cost_per_million=Decimal("0.10"),
            output_cost_per_million=Decimal("0.20"),
        ),
        ModelSpec(
            id="large",
            provider="openrouter",
            context_window=200_000,
            input_cost_per_million=Decimal("0.50"),
            output_cost_per_million=Decimal("1.00"),
        ),
        ModelSpec(
            id="unknown",
            provider="together",
            context_window=131_072,
        ),
    )


def test_ranks_by_lowest_known_cost_by_default() -> None:
    ranked = ModelRankingPolicy().rank(_models())

    assert [model.id for model in ranked] == [
        "cheap",
        "large",
        "unknown",
    ]


def test_ranks_by_largest_context() -> None:
    ranked = ModelRankingPolicy(strategy="largest_context").rank(_models())

    assert [model.id for model in ranked] == [
        "large",
        "unknown",
        "cheap",
    ]


def test_ranks_by_provider_preference_then_cost() -> None:
    ranked = ModelRankingPolicy(
        strategy="provider_preference",
        preferred_providers=("together", "groq"),
    ).rank(_models())

    assert [model.id for model in ranked] == [
        "unknown",
        "cheap",
        "large",
    ]
