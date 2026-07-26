"""Declarative catalog of models available through LLM providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from kernel.llm.exceptions import ProviderError
from kernel.llm.provider_capabilities import ProviderCapabilities
from kernel.llm.provider_registry import has_provider


@dataclass(frozen=True, slots=True)
class ModelSpec:
    """Declarative metadata for a model exposed by a provider."""

    id: str
    provider: str
    context_window: int
    capabilities: ProviderCapabilities = field(default_factory=ProviderCapabilities)
    aliases: tuple[str, ...] = ()
    input_cost_per_million: Decimal | None = None
    output_cost_per_million: Decimal | None = None

    @property
    def qualified_id(self) -> str:
        """Return the provider-qualified model identifier."""

        return f"{self.provider}:{self.id}"


_MODEL_CATALOG: dict[str, ModelSpec] = {}
_MODEL_ALIASES: dict[str, str] = {}


def register_model(
    spec: ModelSpec,
    *,
    replace: bool = False,
) -> None:
    """Register a model and its aliases in the catalog."""

    model_id = spec.id.strip()
    provider = spec.provider.strip().lower()

    if not model_id:
        raise ProviderError("Model id cannot be empty")

    if not provider:
        raise ProviderError("Model provider cannot be empty")

    if not has_provider(provider):
        raise ProviderError(f"Unknown registered provider: {provider}")

    if spec.context_window <= 0:
        raise ProviderError("Model context window must be greater than zero")

    for cost in (
        spec.input_cost_per_million,
        spec.output_cost_per_million,
    ):
        if cost is not None and cost < 0:
            raise ProviderError("Model cost cannot be negative")

    normalized_aliases = tuple(
        alias.strip().lower() for alias in spec.aliases if alias.strip()
    )

    normalized_spec = ModelSpec(
        id=model_id,
        provider=provider,
        context_window=spec.context_window,
        capabilities=spec.capabilities,
        aliases=normalized_aliases,
        input_cost_per_million=spec.input_cost_per_million,
        output_cost_per_million=spec.output_cost_per_million,
    )

    qualified_id = normalized_spec.qualified_id.lower()

    if qualified_id in _MODEL_CATALOG and not replace:
        raise ProviderError(f"Model is already registered: {qualified_id}")

    conflicting_aliases = [
        alias
        for alias in normalized_aliases
        if alias in _MODEL_ALIASES and _MODEL_ALIASES[alias] != qualified_id
    ]

    if conflicting_aliases and not replace:
        aliases = ", ".join(sorted(conflicting_aliases))
        raise ProviderError(f"Model aliases are already registered: {aliases}")

    if replace and qualified_id in _MODEL_CATALOG:
        previous = _MODEL_CATALOG[qualified_id]
        for alias in previous.aliases:
            if _MODEL_ALIASES.get(alias) == qualified_id:
                del _MODEL_ALIASES[alias]

    _MODEL_CATALOG[qualified_id] = normalized_spec

    for alias in normalized_aliases:
        _MODEL_ALIASES[alias] = qualified_id


def get_model_spec(
    model: str,
    *,
    provider: str | None = None,
) -> ModelSpec:
    """Resolve a model by qualified identifier or alias."""

    normalized_model = model.strip().lower()

    if not normalized_model:
        raise ProviderError("Model id cannot be empty")

    if provider is not None:
        qualified_id = f"{provider.strip().lower()}:{normalized_model}"
    elif ":" in normalized_model:
        qualified_id = normalized_model
    else:
        try:
            qualified_id = _MODEL_ALIASES[normalized_model]
        except KeyError as error:
            raise ProviderError(
                f"Unknown registered model or alias: {model}"
            ) from error

    try:
        return _MODEL_CATALOG[qualified_id]
    except KeyError as error:
        raise ProviderError(f"Unknown registered model: {qualified_id}") from error


def has_model(
    model: str,
    *,
    provider: str | None = None,
) -> bool:
    """Return whether a model or alias is registered."""

    try:
        get_model_spec(model, provider=provider)
    except ProviderError:
        return False

    return True


def list_model_specs(
    *,
    provider: str | None = None,
) -> tuple[ModelSpec, ...]:
    """Return registered models, optionally filtered by provider."""

    specs = _MODEL_CATALOG.values()

    if provider is not None:
        normalized_provider = provider.strip().lower()
        specs = (spec for spec in specs if spec.provider == normalized_provider)

    return tuple(sorted(specs, key=lambda spec: spec.qualified_id))


def clear_model_catalog() -> None:
    """Remove all registered models and aliases from the catalog."""

    _MODEL_CATALOG.clear()
    _MODEL_ALIASES.clear()
