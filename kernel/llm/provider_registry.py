"""Instance-based registry for LLM provider definitions."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from typing import Literal

from kernel.llm.capabilities import ProviderCapabilities
from kernel.llm.exceptions import ProviderError

APIStyle = Literal["chat_completions", "responses", "custom"]
ProviderType = Literal["local", "remote"]
ProviderAvailability = Literal[
    "unknown",
    "available",
    "degraded",
    "unavailable",
    "disabled",
]


def _normalize_identifier(value: str, *, label: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ProviderError(f"{label} cannot be empty")
    return normalized


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """Declarative provider metadata without model-specific assumptions."""

    id: str
    provider_type: ProviderType
    api_style: APIStyle
    api_key_env: str | None = None
    base_url: str | None = None
    base_url_env: str | None = None
    enabled: bool = True
    region: str | None = None
    data_policy: str | None = None
    availability: ProviderAvailability = "unknown"
    capabilities: ProviderCapabilities = field(
        default_factory=ProviderCapabilities
    )

    def __post_init__(self) -> None:
        normalized_id = _normalize_identifier(self.id, label="Provider id")
        object.__setattr__(self, "id", normalized_id)

        if self.provider_type == "remote" and not self.base_url:
            raise ProviderError("Remote provider base_url cannot be empty")

        if self.api_key_env is not None and not self.api_key_env.strip():
            raise ProviderError("api_key_env cannot be blank")

        if self.base_url_env is not None and not self.base_url_env.strip():
            raise ProviderError("base_url_env cannot be blank")

    def resolve_api_key(self) -> str | None:
        """Resolve the configured credential without storing the secret."""

        if self.api_key_env is None:
            return None
        return os.getenv(self.api_key_env)

    def resolve_base_url(self) -> str | None:
        """Resolve an environment override or the configured base URL."""

        if self.base_url_env:
            override = os.getenv(self.base_url_env)
            if override:
                return override
        return self.base_url


class ProviderRegistry:
    """Mutable registry owned explicitly by an application container."""

    def __init__(self) -> None:
        self._providers: dict[str, ProviderSpec] = {}

    def register(
        self,
        spec: ProviderSpec,
        *,
        replace_existing: bool = False,
    ) -> ProviderSpec:
        """Register one provider and return its normalized definition."""

        normalized = replace(
            spec,
            id=_normalize_identifier(spec.id, label="Provider id"),
        )

        if normalized.id in self._providers and not replace_existing:
            raise ProviderError(
                f"Provider is already registered: {normalized.id}"
            )

        self._providers[normalized.id] = normalized
        return normalized

    def get(self, provider_id: str) -> ProviderSpec:
        """Return a provider definition by normalized identifier."""

        normalized_id = _normalize_identifier(
            provider_id,
            label="Provider id",
        )
        try:
            return self._providers[normalized_id]
        except KeyError as error:
            raise ProviderError(
                f"Unknown registered provider: {provider_id}"
            ) from error

    def has(self, provider_id: str) -> bool:
        """Return whether the registry contains the provider."""

        normalized_id = _normalize_identifier(
            provider_id,
            label="Provider id",
        )
        return normalized_id in self._providers

    def list(self) -> tuple[ProviderSpec, ...]:
        """Return provider definitions sorted by identifier."""

        return tuple(
            self._providers[provider_id]
            for provider_id in sorted(self._providers)
        )

    def remove(self, provider_id: str) -> ProviderSpec:
        """Remove and return a provider definition."""

        normalized_id = _normalize_identifier(
            provider_id,
            label="Provider id",
        )
        try:
            return self._providers.pop(normalized_id)
        except KeyError as error:
            raise ProviderError(
                f"Unknown registered provider: {provider_id}"
            ) from error
