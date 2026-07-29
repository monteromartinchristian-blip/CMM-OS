from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from kernel.llm.capabilities import ModelCapabilities
from kernel.llm.exceptions import ProviderError
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_router import ModelRouter
from kernel.llm.model_selection import ModelRequirements
from kernel.llm.models import LLMRequest
from kernel.llm.provider_factory import ProviderFactory
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec


class DummyClient:
    def generate(
        self,
        *,
        model: str,
        system: str | None,
        prompt: str,
        temperature: float,
        max_tokens: int | None,
    ) -> tuple[str, int, int, str]:
        return "ok", 1, 1, "stop"


def build_components() -> tuple[
    ProviderRegistry,
    ModelCatalog,
    ModelRouter,
]:
    providers = ProviderRegistry()
    providers.register(
        ProviderSpec(
            id="compatible",
            provider_type="remote",
            api_style="chat_completions",
            base_url="https://example.test/v1",
            availability="available",
        )
    )

    catalog = ModelCatalog(providers)
    catalog.register(
        ModelSpec(
            id="model-a",
            provider_id="compatible",
            context_window=32_768,
            capabilities=ModelCapabilities(reasoning=True),
            input_cost_per_million=Decimal("0.10"),
            output_cost_per_million=Decimal("0.20"),
        )
    )

    return providers, catalog, ModelRouter(
        provider_registry=providers,
        model_catalog=catalog,
    )


def test_factory_creates_provider_from_routing_decision() -> None:
    providers, catalog, router = build_components()
    decision = router.decide(
        ModelRequirements(reasoning=True)
    )

    provider = ProviderFactory().create_from_decision(
        decision,
        provider_registry=providers,
        model_catalog=catalog,
        client=DummyClient(),
    )

    response = provider.generate(LLMRequest(prompt="hello"))

    assert response.content == "ok"
    assert response.model == "model-a"
    assert response.metadata["provider_id"] == "compatible"


def test_factory_rejects_no_match_decision() -> None:
    providers, catalog, router = build_components()
    decision = router.decide(
        ModelRequirements(audio_output=True)
    )

    with pytest.raises(
        ProviderError,
        match="no-match decision",
    ):
        ProviderFactory().create_from_decision(
            decision,
            provider_registry=providers,
            model_catalog=catalog,
            client=DummyClient(),
        )


def test_factory_rejects_provider_model_mismatch() -> None:
    provider = ProviderSpec(
        id="one",
        provider_type="remote",
        api_style="chat_completions",
        base_url="https://one.test/v1",
    )
    model = ModelSpec(
        id="model-a",
        provider_id="two",
    )

    with pytest.raises(
        ProviderError,
        match="does not match",
    ):
        ProviderFactory().create(
            provider=provider,
            model=model,
            client=DummyClient(),
        )


def test_factory_rejects_unsupported_api_style() -> None:
    provider = ProviderSpec(
        id="responses-provider",
        provider_type="remote",
        api_style="responses",
        base_url="https://example.test/v1",
    )
    model = ModelSpec(
        id="model-a",
        provider_id="responses-provider",
    )

    with pytest.raises(
        ProviderError,
        match="Unsupported provider API style",
    ):
        ProviderFactory().create(
            provider=provider,
            model=model,
            client=DummyClient(),
        )
