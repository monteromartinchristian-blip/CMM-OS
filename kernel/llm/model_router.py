"""Executable routing for catalog-backed LLM models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cmm.development.providers import create_planning_provider
from kernel.llm.model_catalog import ModelSpec
from kernel.llm.model_selection import ModelRequirements, select_model
from kernel.llm.provider_registry import ProviderSpec, get_provider_spec


@dataclass(frozen=True, slots=True)
class ModelRoute:
    """Resolved model route ready for execution."""

    model: ModelSpec
    provider: ProviderSpec
    client: Any

    @property
    def qualified_model(self) -> str:
        """Return the provider-qualified model identifier."""

        return self.model.qualified_id


class ModelRouter:
    """Resolve model requirements into executable provider clients."""

    def route(
        self,
        requirements: ModelRequirements,
    ) -> ModelRoute:
        """Select a model and construct its provider client."""

        model = select_model(requirements)
        provider = get_provider_spec(model.provider)
        client = create_planning_provider(model.qualified_id)

        return ModelRoute(
            model=model,
            provider=provider,
            client=client,
        )
