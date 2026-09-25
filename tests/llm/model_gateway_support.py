"""Shared, deterministic fixtures for the Phase 11.21 Model Gateway tests.

Everything here is deterministic: the image and document payloads are fixed
byte sequences, and the canonical graph builders always register the same
providers and models in the same order.  No fixture performs network or
filesystem I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

from kernel.llm.capabilities import ModelCapabilities
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
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
