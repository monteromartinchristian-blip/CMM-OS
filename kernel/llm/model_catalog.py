"""Instance-based catalog for provider-independent model metadata."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Literal

from kernel.llm.capabilities import ModelCapabilities
from kernel.llm.exceptions import ProviderError
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

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
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)
    aliases: tuple[str, ...] = ()
    input_cost_per_million: Decimal | None = None
    output_cost_per_million: Decimal | None = None
    cached_input_cost_per_million: Decimal | None = None
    availability: ModelAvailability = "unknown"
    version: str | None = None
    #: The vendor that actually serves this model, as the serving authority
    #: declares it (an OpenAI-compatible listing's ``owned_by``), never derived
    #: from the model id's spelling.  ``None`` means the authority declared
    #: nothing, which a selector must present as unknown rather than guess.
    vendor: str | None = None
    #: The human label the serving authority published for this model.  It is
    #: carried unchanged so a selector shows what the upstream actually calls
    #: it, instead of a name reconstructed from the id -- which is how a
    #: rolling alias such as "sonnet" ends up presented as if it named a
    #: specific variant.  ``None`` means the authority published no name.
    display_name: str | None = None
    #: Where this model's context actually goes: ``local`` only when the
    #: serving authority stated that the weights are on this machine.
    #:
    #: This is deliberately per-model rather than per-provider.  A single
    #: runtime can serve both on-device weights and models it forwards to a
    #: hosted upstream, so a lane-level answer would mislabel one of them.  A
    #: loopback endpoint is not evidence either way: it says where the process
    #: runs, not where the data goes.  ``None`` means the authority declared
    #: nothing, and the lane default applies.
    locality: Literal["local", "cloud"] | None = None

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
            raise ProviderError("Model context window must be greater than zero")

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

        if self.vendor is not None:
            vendor = self.vendor.strip()
            if not vendor:
                raise ProviderError("Model vendor cannot be blank")
            object.__setattr__(self, "vendor", vendor)

    @property
    def qualified_id(self) -> str:
        """Return the provider-qualified model identifier."""

        return f"{self.provider_id}:{self.id}"


@dataclass(frozen=True, slots=True)
class _ModelBinding:
    """One model together with the canonical provider instance it was bound to.

    Private storage detail (MAJOR-V4-01): identity is the exact ``ProviderSpec``
    object resolved at registration, never the provider id alone, so a removed
    or same-id replaced provider leaves the model visibly stale instead of
    silently current.
    """

    provider: ProviderSpec
    model: ModelSpec


class ModelCatalog:
    """Model catalog bound to an explicit provider registry."""

    def __init__(self, provider_registry: ProviderRegistry) -> None:
        self._provider_registry = provider_registry
        self._models: dict[str, _ModelBinding] = {}
        self._aliases: dict[str, str] = {}

    @property
    def provider_registry(self) -> ProviderRegistry:
        """Return the canonical provider authority this catalog is bound to.

        Read-only binding accessor (MAJOR-V3-01): it exposes the existing
        reference so a composition boundary can prove exact object identity.
        There is deliberately no setter and no rebinding method — a catalog is
        bound to one authority for its whole lifetime.
        """
        return self._provider_registry

    def register(
        self,
        spec: ModelSpec,
        *,
        replace_existing: bool = False,
    ) -> ModelSpec:
        """Register one model after validating its provider.

        The exact ``ProviderSpec`` resolved here is retained privately as this
        model's authority binding (MAJOR-V4-01): a later removal of that
        provider — or its same-id replacement by a different object — leaves the
        model bound to a non-current authority, which capture refuses to
        persist.
        """

        provider = self._provider_registry.get(spec.provider_id)
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
            raise ProviderError(f"Model is already registered: {qualified_id}")

        alias_keys = self._alias_keys(normalized)
        for alias in alias_keys:
            owner = self._aliases.get(alias)
            if owner is not None and owner != qualified_id:
                raise ProviderError(f"Model alias is already registered: {alias}")

        if replace_existing and qualified_id in self._models:
            self._drop_aliases(self._models[qualified_id].model)

        self._models[qualified_id] = _ModelBinding(provider=provider, model=normalized)
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
            return self._models[qualified_id].model
        except KeyError as error:
            raise ProviderError(f"Unknown registered model: {model_id}") from error

    def is_bound_to_current_provider(self, model: ModelSpec) -> bool:
        """Return whether ``model`` still belongs to the current provider authority.

        Authority coherence check (MAJOR-V4-01), read-only: it reports whether
        the model stored under ``model``'s canonical key is that same model and
        is bound to the exact ``ProviderSpec`` the canonical registry currently
        resolves for its provider id. It never mutates, rebinds or repairs — a
        stale entry stays visible and answers ``False``.
        """
        stored = self._models.get(model.qualified_id)
        if stored is None:
            return False
        if stored.model is not model and stored.model != model:
            return False
        try:
            current_provider = self._provider_registry.get(model.provider_id)
        except ProviderError:
            return False
        return current_provider is stored.provider

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

        models = tuple(
            self._models[qualified_id].model for qualified_id in sorted(self._models)
        )
        if provider_id is None:
            return models
        normalized_provider = _normalize_identifier(provider_id, label="Provider id")
        return tuple(
            model for model in models if model.provider_id == normalized_provider
        )

    def remove(self, model_id: str, *, provider_id: str) -> ModelSpec:
        """Remove and return one model definition."""

        spec = self.get(model_id, provider_id=provider_id)
        self._drop_aliases(spec)
        return self._models.pop(spec.qualified_id).model

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
