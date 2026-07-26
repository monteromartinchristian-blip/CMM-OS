"""Registry for external LLM provider configurations."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from kernel.llm.exceptions import ProviderError

APIStyle = Literal["chat_completions", "responses"]


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """Declarative configuration for an external LLM provider."""

    name: str
    api_style: APIStyle
    default_model: str
    api_key_env: str
    base_url: str | None = None
    base_url_env: str | None = None

    def resolve_api_key(self) -> str | None:
        """Resolve the provider API key from its environment variable."""

        return os.getenv(self.api_key_env)

    def resolve_base_url(self) -> str | None:
        """Resolve an overridden or default API base URL."""

        if self.base_url_env:
            overridden = os.getenv(self.base_url_env)
            if overridden:
                return overridden

        return self.base_url

    def resolve_model(self, requested_model: str | None = None) -> str:
        """Resolve an explicitly requested or default model."""

        return requested_model or self.default_model


_PROVIDER_REGISTRY: dict[str, ProviderSpec] = {}


def register_provider(
    spec: ProviderSpec,
    *,
    replace: bool = False,
) -> None:
    """Register an external provider configuration."""

    normalized_name = spec.name.strip().lower()

    if not normalized_name:
        raise ProviderError("Provider name cannot be empty")

    if normalized_name in _PROVIDER_REGISTRY and not replace:
        raise ProviderError(f"Provider is already registered: {normalized_name}")

    if normalized_name != spec.name:
        spec = ProviderSpec(
            name=normalized_name,
            api_style=spec.api_style,
            default_model=spec.default_model,
            api_key_env=spec.api_key_env,
            base_url=spec.base_url,
            base_url_env=spec.base_url_env,
        )

    _PROVIDER_REGISTRY[normalized_name] = spec


def get_provider_spec(name: str) -> ProviderSpec:
    """Return a registered provider configuration."""

    normalized_name = name.strip().lower()

    try:
        return _PROVIDER_REGISTRY[normalized_name]
    except KeyError as error:
        raise ProviderError(f"Unknown registered provider: {name}") from error


def has_provider(name: str) -> bool:
    """Return whether a provider is registered."""

    return name.strip().lower() in _PROVIDER_REGISTRY


def list_provider_specs() -> tuple[ProviderSpec, ...]:
    """Return registered provider configurations sorted by name."""

    return tuple(_PROVIDER_REGISTRY[name] for name in sorted(_PROVIDER_REGISTRY))


register_provider(
    ProviderSpec(
        name="nvidia",
        api_style="chat_completions",
        default_model="z-ai/glm-5.2",
        api_key_env="NVIDIA_API_KEY",
        base_url="https://integrate.api.nvidia.com/v1",
        base_url_env="NVIDIA_BASE_URL",
    )
)
