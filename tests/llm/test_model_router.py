from decimal import Decimal

import pytest

from cmm.development.providers import OpenAICompatiblePlanningProvider
from kernel.llm.exceptions import ModelSelectionError
from kernel.llm.model_catalog import ModelSpec, register_model
from kernel.llm.model_router import ModelRouter
from kernel.llm.model_selection import ModelRequirements
from kernel.llm.provider_capabilities import ProviderCapabilities


def _register_router_models() -> None:
    register_model(
        ModelSpec(
            id="router-fast",
            provider="groq",
            context_window=32_768,
            capabilities=ProviderCapabilities(
                streaming=True,
                tool_calling=True,
            ),
            input_cost_per_million=Decimal("0.10"),
            output_cost_per_million=Decimal("0.20"),
        ),
        replace=True,
    )

    register_model(
        ModelSpec(
            id="router-reasoning",
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


def test_routes_requirements_to_executable_provider() -> None:
    _register_router_models()

    route = ModelRouter().route(
        ModelRequirements(
            streaming=True,
            tool_calling=True,
        )
    )

    assert route.qualified_model == "groq:router-fast"
    assert route.model.id == "router-fast"
    assert route.provider.name == "groq"
    assert isinstance(
        route.client,
        OpenAICompatiblePlanningProvider,
    )
    assert route.client.model == "router-fast"
    assert route.client.provider.source == "groq"


def test_routes_capability_specific_request() -> None:
    _register_router_models()

    route = ModelRouter().route(
        ModelRequirements(
            minimum_context_window=100_000,
            reasoning=True,
            vision=True,
        )
    )

    assert route.qualified_model == "together:router-reasoning"
    assert route.provider.name == "together"
    assert route.client.model == "router-reasoning"
    assert route.client.provider.source == "together"


def test_router_propagates_selection_failure() -> None:
    _register_router_models()

    with pytest.raises(
        ModelSelectionError,
        match="No registered model satisfies",
    ):
        ModelRouter().route(
            ModelRequirements(
                local_only=True,
                audio_input=True,
            )
        )
