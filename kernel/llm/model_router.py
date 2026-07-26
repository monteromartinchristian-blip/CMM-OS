"""Executable routing for catalog-backed LLM models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cmm.development.providers import create_planning_provider
from kernel.llm.model_catalog import ModelSpec
from kernel.llm.model_selection import (
    ModelRequirements,
    find_matching_models,
    select_model,
)
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

    def route_candidates(
        self,
        requirements: ModelRequirements,
        *,
        limit: int | None = None,
    ) -> tuple[ModelRoute, ...]:
        """Return ranked executable routes for fallback execution."""

        if limit is not None and limit <= 0:
            raise ValueError("limit must be greater than zero")

        models = find_matching_models(requirements)

        if limit is not None:
            models = models[:limit]

        return tuple(self._build_route(model) for model in models)

    def route(
        self,
        requirements: ModelRequirements,
    ) -> ModelRoute:
        """Select a model and construct its provider client."""

        model = select_model(requirements)
        return self._build_route(model)

    @staticmethod
    def _build_route(model: ModelSpec) -> ModelRoute:
        """Construct an executable route for a selected model."""

        provider = get_provider_spec(model.provider)
        client = create_planning_provider(model.qualified_id)

        return ModelRoute(
            model=model,
            provider=provider,
            client=client,
        )
