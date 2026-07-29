from __future__ import annotations

from decimal import Decimal

import pytest

from kernel.llm.capabilities import ModelCapabilities
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_ranking import ModelRankingPolicy
from kernel.llm.model_selection import (
    ModelRequirements,
    find_matching_models,
    select_model,
)
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec


@pytest.fixture
def provider_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(
        ProviderSpec(
            id="local",
            provider_type="local",
            api_style="custom",
            availability="available",
        )
    )
    registry.register(
        ProviderSpec(
            id="remote",
            provider_type="remote",
            api_style="chat_completions",
            base_url="https://example.test/v1",
            availability="available",
        )
    )
    registry.register(
        ProviderSpec(
            id="disabled",
            provider_type="remote",
            api_style="chat_completions",
            base_url="https://disabled.test/v1",
            enabled=False,
        )
    )
    return registry


@pytest.fixture
def catalog(provider_registry: ProviderRegistry) -> ModelCatalog:
    model_catalog = ModelCatalog(provider_registry)
    model_catalog.register(
        ModelSpec(
            id="local-reasoner",
            provider_id="local",
            context_window=32_768,
            capabilities=ModelCapabilities(
                reasoning=True,
                structured_output=True,
            ),
        )
    )
    model_catalog.register(
        ModelSpec(
            id="remote-cheap",
            provider_id="remote",
            context_window=128_000,
            capabilities=ModelCapabilities(
                reasoning=True,
                tool_calling=True,
                structured_output=True,
                json_schema=True,
            ),
            input_cost_per_million=Decimal("0.20"),
            output_cost_per_million=Decimal("0.50"),
        )
    )
    model_catalog.register(
        ModelSpec(
            id="remote-expensive",
            provider_id="remote",
            context_window=256_000,
            capabilities=ModelCapabilities(
                reasoning=True,
                tool_calling=True,
                structured_output=True,
                json_schema=True,
                vision=True,
            ),
            input_cost_per_million=Decimal("2.00"),
            output_cost_per_million=Decimal("5.00"),
        )
    )
    model_catalog.register(
        ModelSpec(
            id="disabled-model",
            provider_id="disabled",
            context_window=32_768,
        )
    )
    return model_catalog


def test_requirements_reject_invalid_values() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        ModelRequirements(minimum_context_window=0)

    with pytest.raises(ValueError, match="cannot be negative"):
        ModelRequirements(
            maximum_input_cost_per_million=Decimal("-0.01")
        )

    with pytest.raises(ValueError, match="both allowed and excluded"):
        ModelRequirements(
            allowed_providers=("remote",),
            excluded_providers=("REMOTE",),
        )


def test_local_only_filters_remote_models(
    catalog: ModelCatalog,
    provider_registry: ProviderRegistry,
) -> None:
    matches = find_matching_models(
        catalog,
        provider_registry,
        ModelRequirements(
            reasoning=True,
            structured_output=True,
            privacy="LOCAL_ONLY",
        ),
    )

    assert [model.id for model in matches] == ["local-reasoner"]


def test_sensitive_policy_is_conservative(
    catalog: ModelCatalog,
    provider_registry: ProviderRegistry,
) -> None:
    selected = select_model(
        catalog,
        provider_registry,
        ModelRequirements(
            reasoning=True,
            privacy="SENSITIVE",
        ),
    )

    assert selected is not None
    assert selected.provider_id == "local"


def test_capabilities_and_context_are_hard_constraints(
    catalog: ModelCatalog,
    provider_registry: ProviderRegistry,
) -> None:
    matches = find_matching_models(
        catalog,
        provider_registry,
        ModelRequirements(
            minimum_context_window=100_000,
            tool_calling=True,
            json_schema=True,
        ),
    )

    assert [model.id for model in matches] == [
        "remote-cheap",
        "remote-expensive",
    ]


def test_cost_limits_exclude_unknown_or_expensive_models(
    catalog: ModelCatalog,
    provider_registry: ProviderRegistry,
) -> None:
    matches = find_matching_models(
        catalog,
        provider_registry,
        ModelRequirements(
            maximum_input_cost_per_million=Decimal("0.50"),
            maximum_output_cost_per_million=Decimal("1.00"),
        ),
    )

    assert [model.id for model in matches] == ["remote-cheap"]


def test_allowed_and_excluded_providers_are_normalized(
    catalog: ModelCatalog,
    provider_registry: ProviderRegistry,
) -> None:
    matches = find_matching_models(
        catalog,
        provider_registry,
        ModelRequirements(
            allowed_providers=(" REMOTE ",),
            excluded_providers=(),
        ),
    )

    assert {model.provider_id for model in matches} == {"remote"}


def test_disabled_provider_is_never_selected(
    catalog: ModelCatalog,
    provider_registry: ProviderRegistry,
) -> None:
    matches = find_matching_models(
        catalog,
        provider_registry,
        ModelRequirements(),
    )

    assert all(model.provider_id != "disabled" for model in matches)


def test_ranking_policy_controls_deterministic_selection(
    catalog: ModelCatalog,
    provider_registry: ProviderRegistry,
) -> None:
    selected = select_model(
        catalog,
        provider_registry,
        ModelRequirements(reasoning=True),
        ranking_policy=ModelRankingPolicy(
            strategy="largest_context"
        ),
    )

    assert selected is not None
    assert selected.id == "remote-expensive"


def test_no_match_returns_none(
    catalog: ModelCatalog,
    provider_registry: ProviderRegistry,
) -> None:
    selected = select_model(
        catalog,
        provider_registry,
        ModelRequirements(
            audio_output=True,
        ),
    )

    assert selected is None
