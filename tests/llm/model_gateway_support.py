"""Shared, deterministic fixtures for the Phase 11.21 Model Gateway tests.

Everything here is deterministic: the image and document payloads are fixed
byte sequences, and the canonical graph builders always register the same
providers and models in the same order.  No fixture performs network or
filesystem I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from kernel.llm.capabilities import ModelCapabilities, ReasoningEffort
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_gateway import ModelGateway
from kernel.llm.model_gateway_contracts import InMemoryModelExecutionEvidenceSink
from kernel.llm.model_provider_adapter import (
    InMemoryModelProviderAdapter,
    ModelProviderAdapterRegistry,
)
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

#: Smallest deterministic 1x1 PNG payload (real PNG signature, IHDR and IEND).
PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)

#: Minimal deterministic JPEG payload (real SOI/APP0/SOF0/EOI markers).
JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
    b"\xff\xd9"
)

#: Minimal deterministic PDF payload.
PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    b"2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n"
    b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"
)

#: Deterministic markdown and plain-text document payloads.
MARKDOWN_BYTES = b"# Phase 11.21\n\nReal document content.\n"
TEXT_DOCUMENT_BYTES = b"real plain text document content\n"


@dataclass(frozen=True, slots=True)
class CanonicalGraph:
    """The canonical Phase 11.34 authorities used by gateway tests."""

    providers: ProviderRegistry
    models: ModelCatalog

    def register_local_model(
        self,
        model_id: str,
        *,
        capabilities: ModelCapabilities | None = None,
        provider_id: str = "local",
        context_window: int | None = 32768,
        availability: str = "available",
        aliases: tuple[str, ...] = (),
    ) -> ModelSpec:
        """Register one local model and return its canonical spec."""

        return self.models.register(
            ModelSpec(
                id=model_id,
                provider_id=provider_id,
                context_window=context_window,
                capabilities=capabilities or ModelCapabilities(),
                availability=availability,  # type: ignore[arg-type]
                aliases=aliases,
            )
        )


def build_canonical_graph(
    *,
    local_provider_id: str = "local",
    remote_provider_id: str = "remote-a",
) -> CanonicalGraph:
    """Build the canonical registry/catalog pair used by most gateway tests."""

    providers = ProviderRegistry()
    providers.register(
        ProviderSpec(
            id=local_provider_id,
            provider_type="local",
            api_style="chat_completions",
            availability="available",
        )
    )
    providers.register(
        ProviderSpec(
            id=remote_provider_id,
            provider_type="remote",
            api_style="chat_completions",
            base_url="https://remote-a.example/v1",
            availability="available",
        )
    )
    return CanonicalGraph(providers=providers, models=ModelCatalog(providers))


#: Capabilities of a typical text model that also supports tools and schemas.
TEXT_CAPABLE = ModelCapabilities(
    structured_output=True,
    tool_calling=True,
    json_schema=True,
)

#: Capabilities of a fully multimodal local model.
MULTIMODAL = ModelCapabilities(
    structured_output=True,
    tool_calling=True,
    json_schema=True,
    vision=True,
    streaming=True,
    reasoning=True,
    reasoning_efforts=(
        ReasoningEffort.LOW,
        ReasoningEffort.MEDIUM,
        ReasoningEffort.HIGH,
        ReasoningEffort.EXTRA_HIGH,
    ),
    document_media_types=("application/pdf", "text/plain", "text/markdown"),
)


@dataclass
class GatewayRuntime:
    """A composed gateway plus the canonical components observing it."""

    graph: CanonicalGraph
    sink: InMemoryModelExecutionEvidenceSink
    gateway: ModelGateway
    adapters: dict[str, InMemoryModelProviderAdapter]

    def adapter(self, provider_id: str = "local") -> InMemoryModelProviderAdapter:
        """Return the in-memory adapter registered for ``provider_id``."""

        return self.adapters[provider_id]


def build_runtime(
    *,
    model_id: str = "model-1",
    provider_id: str = "local",
    capabilities: ModelCapabilities | None = None,
    context_window: int | None = 32768,
    graph: CanonicalGraph | None = None,
    register_model: bool = True,
    sink: InMemoryModelExecutionEvidenceSink | None = None,
    adapters: tuple[InMemoryModelProviderAdapter, ...] = (),
    derive_content_from_input: bool = False,
    **gateway_kwargs: object,
) -> GatewayRuntime:
    """Compose a canonical gateway over the canonical registry and catalog.

    ``graph`` may be supplied to pre-register extra providers/models; the model
    named by ``model_id`` is then registered on top of it.  Passing
    ``register_model=False`` reuses a model already registered on the graph.
    """

    resolved_graph = graph or build_canonical_graph()
    if register_model:
        resolved_graph.models.register(
            ModelSpec(
                id=model_id,
                provider_id=provider_id,
                context_window=context_window,
                capabilities=capabilities or ModelCapabilities(),
                availability="available",
            )
        )
    adapter_map = {adapter.provider_id: adapter for adapter in adapters}
    if provider_id not in adapter_map:
        adapter_map[provider_id] = InMemoryModelProviderAdapter(
            provider_id,
            derive_content_from_input=derive_content_from_input,
        )
    evidence = sink or InMemoryModelExecutionEvidenceSink()
    gateway = ModelGateway(
        provider_registry=resolved_graph.providers,
        model_catalog=resolved_graph.models,
        adapters=ModelProviderAdapterRegistry(adapter_map.values()),
        evidence_sink=evidence,
        **gateway_kwargs,  # type: ignore[arg-type]
    )
    return GatewayRuntime(
        graph=resolved_graph,
        sink=evidence,
        gateway=gateway,
        adapters=adapter_map,
    )
