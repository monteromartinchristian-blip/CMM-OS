from decimal import Decimal

import pytest

from kernel.llm.model_catalog import ModelSpec, register_model
from kernel.llm.model_selection import (
    ModelRequirements,
    find_matching_models,
    model_matches_requirements,
)
from kernel.llm.provider_capabilities import ProviderCapabilities


def _register_selection_models() -> None:
    register_model(
        ModelSpec(
            id="selection-fast",
            provider="groq",
            context_window=32_768,
            capabilities=ProviderCapabilities(
                streaming=True,
                tool_calling=True,
            ),
            input_cost_per_million=Decimal("0.20"),
            output_cost_per_million=Decimal("0.40"),
        ),
        replace=True,
    )

    register_model(
        ModelSpec(
            id="selection-reasoning",
            provider="together",
            context_window=131_072,
            capabilities=ProviderCapabilities(
                streaming=True,
                tool_calling=True,
                reasoning=True,
                vision=True,
            ),
            input_cost_per_million=Decimal("0.50"),
            output_cost_per_million=Decimal("1.00"),
        ),
        replace=True,
    )

    register_model(
        ModelSpec(
            id="selection-unknown-cost",
            provider="openrouter",
            context_window=200_000,
            capabilities=ProviderCapabilities(
                streaming=True,
                reasoning=True,
                vision=True,
            ),
        ),
        replace=True,
    )


def test_matches_required_capabilities_and_context() -> None:
    _register_selection_models()

    requirements = ModelRequirements(
        minimum_context_window=100_000,
        reasoning=True,
        vision=True,
    )

    matches = find_matching_models(requirements)
    qualified_ids = {
        model.qualified_id for model in matches if model.id.startswith("selection-")
    }

    assert qualified_ids == {
        "together:selection-reasoning",
        "openrouter:selection-unknown-cost",
    }


def test_filters_allowed_and_excluded_providers() -> None:
    _register_selection_models()

    requirements = ModelRequirements(
        allowed_providers=(" GROQ ", "together"),
        excluded_providers=("TOGETHER",),
    )

    matches = find_matching_models(requirements)
    selection_matches = [
        model for model in matches if model.id.startswith("selection-")
    ]

    assert [model.qualified_id for model in selection_matches] == [
        "groq:selection-fast"
    ]


def test_rejects_unknown_cost_when_maximum_is_required() -> None:
    _register_selection_models()

    requirements = ModelRequirements(
        reasoning=True,
        maximum_input_cost_per_million=Decimal("0.75"),
        maximum_output_cost_per_million=Decimal("1.50"),
    )

    matches = find_matching_models(requirements)
    selection_matches = [
        model.qualified_id for model in matches if model.id.startswith("selection-")
    ]

    assert selection_matches == ["together:selection-reasoning"]


def test_sorts_known_cost_models_before_unknown_cost_models() -> None:
    _register_selection_models()

    requirements = ModelRequirements(streaming=True)

    matches = [
        model
        for model in find_matching_models(requirements)
        if model.id.startswith("selection-")
    ]

    assert [model.qualified_id for model in matches] == [
        "groq:selection-fast",
        "together:selection-reasoning",
        "openrouter:selection-unknown-cost",
    ]


def test_local_only_rejects_remote_model() -> None:
    _register_selection_models()

    model = next(
        model
        for model in find_matching_models(ModelRequirements())
        if model.id == "selection-fast"
    )

    assert not model_matches_requirements(
        model,
        ModelRequirements(local_only=True),
    )


@pytest.mark.parametrize(
    "minimum_context_window",
    [0, -1],
)
def test_rejects_invalid_minimum_context(
    minimum_context_window: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="minimum_context_window",
    ):
        ModelRequirements(minimum_context_window=minimum_context_window)


def test_rejects_negative_maximum_cost() -> None:
    with pytest.raises(
        ValueError,
        match="cost cannot be negative",
    ):
        ModelRequirements(maximum_input_cost_per_million=Decimal("-0.01"))
