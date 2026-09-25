"""Canonical provider-independent Model Gateway (Phase 11.21).

The Model Gateway is the single model-call execution boundary of CMM OS.  It
owns normalization and execution only:

* canonical model/provider lookup through the exact canonical
  :class:`~kernel.llm.provider_registry.ProviderRegistry` and
  :class:`~kernel.llm.model_catalog.ModelCatalog` instances it was constructed
  with (never a copy, snapshot or second authority);
* preflight capability, reasoning-effort and modality validation before any
  provider I/O;
* canonical privacy enforcement before any remote egress;
* provider request translation through an injected provider adapter;
* normalized responses, streams, cancellation, timeout, bounded transport
  retry, authorized fallback mechanics and usage/latency/cost facts.

It owns none of: provider identity, model inventory, routing policy, user
preferences, conversation state, persistence, memory, domain logic, agent
planning, tool execution, permissions, approval, validation or events.  A
provider tool call grants the gateway no authority, and a provider being
available never implies permission to transmit.
"""

from __future__ import annotations

from kernel.llm.exceptions import ProviderError
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_gateway_contracts import ModelCapabilityProjection
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

__all__ = ["ModelGateway"]

_UNAVAILABLE_AVAILABILITY = frozenset({"unavailable", "disabled"})


class ModelGateway:
    """The canonical model-call execution boundary.

    Construction requires the exact canonical provider registry and the
    canonical model catalog bound to that registry.  The gateway stores those
    references and exposes them read-only so a composition boundary can prove
    exact object identity.
    """

    __slots__ = ("_model_catalog", "_provider_registry")

    def __init__(
        self,
        *,
        provider_registry: ProviderRegistry,
        model_catalog: ModelCatalog,
    ) -> None:
        if not isinstance(provider_registry, ProviderRegistry):
            raise TypeError("provider_registry must be a ProviderRegistry")
        if not isinstance(model_catalog, ModelCatalog):
            raise TypeError("model_catalog must be a ModelCatalog")
        if model_catalog.provider_registry is not provider_registry:
            raise ValueError(
                "model_catalog must be bound to the supplied provider_registry"
            )
        self._provider_registry = provider_registry
        self._model_catalog = model_catalog

    @property
    def provider_registry(self) -> ProviderRegistry:
        """Return the exact canonical provider authority (read-only)."""

        return self._provider_registry

    @property
    def model_catalog(self) -> ModelCatalog:
        """Return the exact canonical model catalog (read-only)."""

        return self._model_catalog

    # ── Read-only capability projection ──────────────────────────────────────

    def model_capabilities(
        self,
        model_id: str,
        *,
        provider_id: str | None = None,
    ) -> ModelCapabilityProjection:
        """Return the canonical capability projection for one model.

        The projection is derived only from canonical registry/catalog state, so
        an unknown model fails closed with ``MODEL_NOT_FOUND`` and an unknown
        capability stays unknown rather than being guessed.
        """

        try:
            model = self._model_catalog.get(model_id, provider_id=provider_id)
        except ProviderError as error:
            raise ModelGatewayError(
                ModelGatewayErrorCode.MODEL_NOT_FOUND,
                "requested model is not registered",
                details={"model_id": str(model_id)},
            ) from error
        return self._project(model, self._resolve_provider(model))

    def list_model_capabilities(
        self,
        *,
        provider_id: str | None = None,
    ) -> tuple[ModelCapabilityProjection, ...]:
        """Return the capability projection for every canonical model, sorted."""

        return tuple(
            self._project(model, self._resolve_provider(model))
            for model in self._model_catalog.list(provider_id=provider_id)
        )

    def _resolve_provider(self, model: ModelSpec) -> ProviderSpec | None:
        """Resolve a model's canonical provider, or ``None`` when it is gone."""

        try:
            return self._provider_registry.get(model.provider_id)
        except ProviderError:
            return None

    def _project(
        self,
        model: ModelSpec,
        provider: ProviderSpec | None,
    ) -> ModelCapabilityProjection:
        """Build one truthful, read-only capability projection."""

        authority_current = self._model_catalog.is_bound_to_current_provider(model)
        capabilities = model.capabilities

        if provider is None:
            provider_type = "unknown"
            provider_available = False
        else:
            provider_type = provider.provider_type
            provider_available = (
                authority_current
                and provider.enabled
                and provider.availability not in _UNAVAILABLE_AVAILABILITY
            )

        return ModelCapabilityProjection(
            model_id=model.id,
            provider_id=model.provider_id,
            qualified_id=model.qualified_id,
            provider_type=provider_type,
            is_local=provider_type == "local",
            provider_available=provider_available,
            model_available=model.availability not in _UNAVAILABLE_AVAILABILITY,
            authority_current=authority_current,
            context_window=model.context_window,
            reasoning=capabilities.reasoning,
            reasoning_efforts=capabilities.reasoning_efforts,
            tool_calling=capabilities.tool_calling,
            structured_output=capabilities.structured_output,
            json_mode=capabilities.json_mode,
            json_schema=capabilities.json_schema,
            vision=capabilities.vision,
            document_media_types=capabilities.document_media_types,
            streaming=capabilities.streaming,
            audio_input=capabilities.audio_input,
            audio_output=capabilities.audio_output,
            embeddings=capabilities.embeddings,
            aliases=model.aliases,
            version=model.version,
            input_cost_per_million=model.input_cost_per_million,
            output_cost_per_million=model.output_cost_per_million,
            cached_input_cost_per_million=model.cached_input_cost_per_million,
        )
