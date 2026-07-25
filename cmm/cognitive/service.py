"""Phase 8.3 – ResourceExtractionService.

Orchestrates the full pipeline::

    ResourceInput
        ↓
    ResourceAdapterRegistry
        ↓
    ResourceAdaptationResult
        ↓
    Resource
        ↓
    KnowledgeExtractorRegistry
        ↓
    KnowledgeExtractionResult

Public surface
--------------
AdaptAndExtractResult
ResourceExtractionService
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from cmm.cognitive.adapters import (
    AdaptationContext,
    ResourceAdaptationResult,
    ResourceInput,
)
from cmm.cognitive.errors import InvalidExtractionError
from cmm.cognitive.extraction import (
    ExtractionContext,
    KnowledgeExtractionResult,
)
from cmm.cognitive.identifiers import generate_cognitive_id
from cmm.cognitive.registries import (
    KnowledgeExtractorRegistry,
    ResourceAdapterRegistry,
)
from cmm.cognitive.resources import Resource


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ── AdaptAndExtractResult ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AdaptAndExtractResult:
    """Composite outcome that preserves both adaptation and extraction results."""

    adaptation: ResourceAdaptationResult
    extraction: KnowledgeExtractionResult | None
    id: str = field(
        default_factory=lambda: generate_cognitive_id("adapt-extract-result", "general")
    )
    created_at: datetime = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            raise InvalidExtractionError(
                "AdaptAndExtractResult created_at must be timezone-aware"
            )
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def successful(self) -> bool:
        return (
            self.adaptation.successful
            and self.extraction is not None
            and self.extraction.successful
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "adaptation": self.adaptation.to_dict(),
            "extraction": (
                self.extraction.to_dict() if self.extraction is not None else None
            ),
            "successful": self.successful,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }


# ── ResourceExtractionService ─────────────────────────────────────────────────


class ResourceExtractionService:
    """Lightweight orchestrator for adaptation and extraction pipelines.

    Parameters
    ----------
    adapter_registry:
        Registry of :class:`~cmm.cognitive.adapters.ResourceAdapter` instances.
    extractor_registry:
        Registry of :class:`~cmm.cognitive.extraction.KnowledgeExtractor`
        instances.
    """

    def __init__(
        self,
        adapter_registry: ResourceAdapterRegistry,
        extractor_registry: KnowledgeExtractorRegistry,
    ) -> None:
        self._adapters = adapter_registry
        self._extractors = extractor_registry

    # ── Public API ────────────────────────────────────────────────────────────

    def adapt(
        self,
        source: ResourceInput,
        *,
        context: AdaptationContext | None = None,
    ) -> ResourceAdaptationResult:
        """Adapt *source* using the best available adapter."""
        return self._adapters.adapt(source, context=context)

    def extract(
        self,
        resource: Resource,
        *,
        context: ExtractionContext | None = None,
        extractor_name: str | None = None,
    ) -> KnowledgeExtractionResult:
        """Extract knowledge from *resource* using the best available extractor."""
        return self._extractors.extract(
            resource, context=context, extractor_name=extractor_name
        )

    def adapt_and_extract(
        self,
        source: ResourceInput,
        *,
        adaptation_context: AdaptationContext | None = None,
        extraction_context: ExtractionContext | None = None,
        extractor_name: str | None = None,
    ) -> AdaptAndExtractResult:
        """Run the full pipeline: adapt *source*, then extract knowledge.

        If adaptation fails (status != completed or partial, or no resource
        returned), extraction is skipped and the result reflects only the
        adaptation outcome.

        Context propagation
        -------------------
        actor_id, trace_id, session_id, and domain are forwarded from the
        adaptation context to the extraction context when the latter is not
        provided.
        """
        adaptation_result = self._adapters.adapt(source, context=adaptation_context)

        if not adaptation_result.successful or adaptation_result.resource is None:
            return AdaptAndExtractResult(
                adaptation=adaptation_result,
                extraction=None,
                metadata=self._propagation_metadata(adaptation_context),
            )

        # Propagate context fields to extraction when not explicitly supplied
        resolved_extraction_context = self._resolve_extraction_context(
            adaptation_context=adaptation_context,
            extraction_context=extraction_context,
        )

        resource = adaptation_result.resource
        extraction_result = self._extractors.extract(
            resource,
            context=resolved_extraction_context,
            extractor_name=extractor_name,
        )

        return AdaptAndExtractResult(
            adaptation=adaptation_result,
            extraction=extraction_result,
            metadata=self._propagation_metadata(adaptation_context),
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _resolve_extraction_context(
        self,
        *,
        adaptation_context: AdaptationContext | None,
        extraction_context: ExtractionContext | None,
    ) -> ExtractionContext | None:
        """Build an extraction context, propagating fields from adaptation."""
        if extraction_context is not None:
            return extraction_context
        if adaptation_context is None:
            return None
        # Propagate relevant fields
        return ExtractionContext(
            actor_id=adaptation_context.actor_id,
            domain=adaptation_context.target_domain,
            trace_id=adaptation_context.trace_id,
            session_id=adaptation_context.session_id,
        )

    def _propagation_metadata(
        self, context: AdaptationContext | None
    ) -> dict[str, Any]:
        if context is None:
            return {}
        return {
            k: v
            for k, v in {
                "trace_id": context.trace_id,
                "session_id": context.session_id,
                "actor_id": context.actor_id,
                "domain": context.target_domain,
            }.items()
            if v is not None
        }
