from __future__ import annotations

from decimal import Decimal

from kernel.llm.model_catalog import ModelSpec
from kernel.llm.model_ranking import ModelRankingPolicy


def make_model(
    model_id: str,
    provider_id: str,
    *,
    context_window: int = 8_192,
    input_cost: str | None = None,
    output_cost: str | None = None,
) -> ModelSpec:
    return ModelSpec(
        id=model_id,
        provider_id=provider_id,
        context_window=context_window,
        input_cost_per_million=(
            Decimal(input_cost) if input_cost is not None else None
        ),
        output_cost_per_million=(
            Decimal(output_cost) if output_cost is not None else None
        ),
    )


def test_lowest_cost_places_unknown_prices_last() -> None:
    models = (
        make_model("unknown", "alpha"),
        make_model("cheap", "alpha", input_cost="0.10", output_cost="0.20"),
        make_model("expensive", "alpha", input_cost="1.00", output_cost="2.00"),
    )

    ranked = ModelRankingPolicy(strategy="lowest_cost").rank(models)

    assert [model.id for model in ranked] == [
        "cheap",
        "expensive",
        "unknown",
    ]


def test_largest_context_is_deterministic() -> None:
    models = (
        make_model("small", "alpha", context_window=8_192),
        make_model("large-b", "alpha", context_window=128_000),
        make_model("large-a", "alpha", context_window=128_000),
    )

    ranked = ModelRankingPolicy(strategy="largest_context").rank(models)

    assert [model.id for model in ranked] == [
        "large-a",
        "large-b",
        "small",
    ]


def test_provider_preference_normalizes_and_deduplicates() -> None:
    models = (
        make_model("one", "secondary", input_cost="0.01"),
        make_model("two", "preferred", input_cost="1.00"),
    )

    policy = ModelRankingPolicy(
        strategy="provider_preference",
        preferred_providers=(" Preferred ", "preferred"),
    )

    ranked = policy.rank(models)

    assert policy.preferred_providers == ("preferred",)
    assert [model.provider_id for model in ranked] == [
        "preferred",
        "secondary",
    ]
