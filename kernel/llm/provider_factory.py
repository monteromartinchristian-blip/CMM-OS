"""Explicit factories that turn routing decisions into LLM providers."""

from __future__ import annotations

from typing import Any

from kernel.llm.clients.openai_compatible_client import (
    OpenAICompatibleClient,
)
from kernel.llm.exceptions import ProviderError
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_router import RoutingDecision
from kernel.llm.openai_compatible_provider import (
    OpenAICompatibleProvider,
)
from kernel.llm.provider import LLMProvider
from kernel.llm.provider_registry import (
    ProviderRegistry,
    ProviderSpec,
)


class ProviderFactory:
    """Build executable providers without coupling the router to clients."""

    def create(
        self,
        *,
        provider: ProviderSpec,
        model: ModelSpec,
        client: Any | None = None,
    ) -> LLMProvider:
        """Create an executable provider for one provider/model pair."""

        if model.provider_id != provider.id:
            raise ProviderError(
                "Model provider does not match provider definition"
            )

        if not provider.enabled:
            raise ProviderError(
                f"Provider is disabled: {provider.id}"
            )

        if provider.availability in {"unavailable", "disabled"}:
            raise ProviderError(
                f"Provider is not available: {provider.id}"
            )

        if model.availability in {"unavailable", "disabled"}:
            raise ProviderError(
                f"Model is not available: {model.qualified_id}"
            )

        if provider.api_style != "chat_completions":
            raise ProviderError(
                "Unsupported provider API style for this factory: "
                f"{provider.api_style}"
            )

        compatible_client = client or OpenAICompatibleClient(
            api_key=provider.resolve_api_key(),
            base_url=provider.resolve_base_url(),
        )

        return OpenAICompatibleProvider(
            provider_id=provider.id,
            client=compatible_client,
            model=model.id,
        )

    def create_from_decision(
        self,
        decision: RoutingDecision,
        *,
        provider_registry: ProviderRegistry,
        model_catalog: ModelCatalog,
        client: Any | None = None,
    ) -> LLMProvider:
        """Create a provider from an accepted routing decision."""

        if decision.status != "selected":
            raise ProviderError(
                "Cannot create a provider from a no-match decision"
            )

        if (
            decision.selected_provider_id is None
            or decision.selected_model_id is None
        ):
            raise ProviderError(
                "Routing decision does not contain a selected model"
            )

        provider = provider_registry.get(
            decision.selected_provider_id
        )
        model = model_catalog.get(
            decision.selected_model_id,
            provider_id=decision.selected_provider_id,
        )

        return self.create(
            provider=provider,
            model=model,
            client=client,
        )
