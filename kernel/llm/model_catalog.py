"""Instance-based catalog for provider-independent model metadata."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Literal

from kernel.llm.capabilities import ModelCapabilities
from kernel.llm.exceptions import ProviderError
from kernel.llm.provider_registry import ProviderRegistry

ModelAvailability = Literal[
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


def _validate_cost(value: Decimal | None, *, label: str) -> None:
    if value is not None and value < 0:
        raise ProviderError(f"{label} cannot be negative")


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Declarative metadata for a model exposed by one provider."""

    id: str
    provider_id: str
    context_window: int | None = None
    capabilities: ModelCapabilities = field(
        default_factory=ModelCapabilities
    )
    aliases: tuple[str, ...] = ()
    input_cost_per_million: Decimal | None = None
    output_cost_per_million: Decimal | None = None
    cached_input_cost_per_million: Decimal | None = None
    availability: ModelAvailability = "unknown"
    version: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "id",
            _normalize_identifier(self.id, label="Model id"),
        )
        object.__setattr__(
            self,
            "provider_id",
            _normalize_identifier(
                self.provider_id,
                label="Provider id",
            ),
        )

        if self.context_window is not None and self.context_window <= 0:
            raise ProviderError(
                "Model context window must be greater than zero"
            )

        _validate_cost(
            self.input_cost_per_million,
            label="Input cost",
        )
        _validate_cost(
            self.output_cost_per_million,
            label="Output cost",
        )
        _validate_cost(
            self.cached_input_cost_per_million,
            label="Cached input cost",
        )

        normalized_aliases = tuple(
            dict.fromkeys(
                _normalize_identifier(alias, label="Model alias")
                for alias in self.aliases
            )
        )
        object.__setattr__(self, "aliases", normalized_aliases)

    @property
    def qualified_id(self) -> str:
        """Return the provider-qualified model identifier."""

        return f"{self.provider_id}:{self.id}"


class ModelCatalog:
    """Model catalog bound to an explicit provider registry."""

    def __init__(self, provider_registry: ProviderRegistry) -> None:
        self._provider_registry = provider_registry
        self._models: dict[str, ModelSpec] = {}
        self._aliases: dict[str, str] = {}

    def register(
        self,
        spec: ModelSpec,
        *,
        replace_existing: bool = False,
    ) -> ModelSpec:
        """Register one model after validating its provider."""

        self._provider_registry.get(spec.provider_id)
        normalized = replace(
            spec,
            id=_normalize_identifier(spec.id, label="Model id"),
            provider_id=_normalize_identifier(
                spec.provider_id,
                label="Provider id",
            ),
        )
        qualified_id = normalized.qualified_id

        if qualified_id in self._models and not replace_existing:
            raise ProviderError(
                f"Model is already registered: {qualified_id}"
            )

        alias_keys = self._alias_keys(normalized)
        for alias in alias_keys:
            owner = self._aliases.get(alias)
            if owner is not None and owner != qualified_id:
                raise ProviderError(
                    f"Model alias is already registered: {alias}"
                )

        if replace_existing and qualified_id in self._models:
            self._drop_aliases(self._models[qualified_id])

        self._models[qualified_id] = normalized
        for alias in alias_keys:
            self._aliases[alias] = qualified_id

        return normalized

    def get(
        self,
        model_id: str,
        *,
        provider_id: str | None = None,
    ) -> ModelSpec:
        """Resolve a model by qualified id, provider/id pair, or alias."""

        lookup = _normalize_identifier(model_id, label="Model id")

        if provider_id is not None:
            provider = _normalize_identifier(
                provider_id,
                label="Provider id",
            )
            lookup = f"{provider}:{lookup}"

        qualified_id = self._aliases.get(lookup, lookup)
        try:
            return self._models[qualified_id]
        except KeyError as error:
            raise ProviderError(
                f"Unknown registered model: {model_id}"
            ) from error

    def has(
        self,
        model_id: str,
        *,
        provider_id: str | None = None,
    ) -> bool:
        """Return whether the catalog can resolve the model."""

        try:
            self.get(model_id, provider_id=provider_id)
        except ProviderError:
            return False
        return True

    def list(
        self,
        *,
        provider_id: str | None = None,
    ) -> tuple[ModelSpec, ...]:
        """Return models sorted by qualified identifier."""

        normalized_provider = (
            _normalize_identifier(provider_id, label="Provider id")
            if provider_id is not None
            else None
        )

        return tuple(
            self._models[qualified_id]
            for qualified_id in sorted(self._models)
            if normalized_provider is None
            or self._models[qualified_id].provider_id
            == normalized_provider
        )

    def remove(self, model_id: str, *, provider_id: str) -> ModelSpec:
        """Remove and return one model definition."""

        spec = self.get(model_id, provider_id=provider_id)
        self._drop_aliases(spec)
        return self._models.pop(spec.qualified_id)

    @staticmethod
    def _alias_keys(spec: ModelSpec) -> tuple[str, ...]:
        return (
            spec.qualified_id,
            *(f"{spec.provider_id}:{alias}" for alias in spec.aliases),
            *spec.aliases,
        )

    def _drop_aliases(self, spec: ModelSpec) -> None:
        for alias in self._alias_keys(spec):
            if self._aliases.get(alias) == spec.qualified_id:
                self._aliases.pop(alias)
