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

from kernel.llm.model_catalog import ModelCatalog
from kernel.llm.provider_registry import ProviderRegistry

__all__ = ["ModelGateway"]


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
