"""Tests for Phase 8.3 ResourceExtractionService."""

from __future__ import annotations

from datetime import datetime

import pytest

from cmm.cognitive import (
    AdaptAndExtractResult,
    AdaptationContext,
    AdaptationStatus,
    ExtractionContext,
    ExtractionStatus,
    KnowledgeExtractorRegistry,
    MappingKnowledgeExtractor,
    MappingResourceAdapter,
    PlainTextKnowledgeExtractor,
    PlainTextResourceAdapter,
    Resource,
    ResourceAdapterRegistry,
    ResourceExtractionService,
    ResourceInput,
    ResourceKind,
    ResourcePermission,
    ResourcePermissionOperation,
    ResourceSourceKind,
)
from cmm.cognitive.contracts import Confidence
from cmm.cognitive.resources import ResourceProvenance, ResourceTemporalScope

# ── Helpers ───────────────────────────────────────────────────────────────────


def _infer_permission() -> ResourcePermission:
    return ResourcePermission(
        allowed_operations=(
            ResourcePermissionOperation.READ,
            ResourcePermissionOperation.INFER,
        )
    )


def _build_service() -> ResourceExtractionService:
    adapter_reg = ResourceAdapterRegistry()
    adapter_reg.register(PlainTextResourceAdapter())
    adapter_reg.register(MappingResourceAdapter())

    extractor_reg = KnowledgeExtractorRegistry()
    extractor_reg.register(PlainTextKnowledgeExtractor())
    extractor_reg.register(MappingKnowledgeExtractor())

    return ResourceExtractionService(adapter_reg, extractor_reg)


def _text_input(id: str = "inp-txt") -> ResourceInput:
    return ResourceInput(
        id=id,
        source_kind=ResourceSourceKind.USER_INPUT,
        payload="The patient visited the clinic. Is this the first visit?",
    )


def _mapping_input(id: str = "inp-map") -> ResourceInput:
    return ResourceInput(
        id=id,
        source_kind=ResourceSourceKind.STRUCTURED_DATA,
        payload={"name": "Alice", "age": 30},
    )


def _empty_text_input() -> ResourceInput:
    return ResourceInput(
        id="empty-inp",
        source_kind=ResourceSourceKind.USER_INPUT,
        payload="   ",
    )


def _unsupported_input() -> ResourceInput:
    """A payload that no registered adapter handles."""
    return ResourceInput(
        id="unsupported-inp",
        source_kind=ResourceSourceKind.USER_INPUT,
        payload=99999,  # integer — not supported
    )


# ── AdaptAndExtractResult contract ────────────────────────────────────────────


class TestAdaptAndExtractResultContract:
    def _result(
        self, adaptation_status=AdaptationStatus.COMPLETED, with_extraction=True
    ):
        from cmm.cognitive.adapters import ResourceAdaptationResult
        from cmm.cognitive.extraction import KnowledgeExtractionResult

        adaptation = ResourceAdaptationResult(
            adapter_name="plain_text",
            adapter_version="1.0.0",
            input_id="i1",
            status=adaptation_status,
        )
        extraction = None
        if with_extraction:
            extraction = KnowledgeExtractionResult(
                resource_id="r1",
                extractor_name="plain_text",
                extractor_version="1.0.0",
                status=ExtractionStatus.COMPLETED,
            )
        return AdaptAndExtractResult(adaptation=adaptation, extraction=extraction)

    def test_successful_when_both_succeed(self) -> None:
        result = self._result()
        assert result.successful is True

    def test_not_successful_when_adaptation_fails(self) -> None:
        result = self._result(
            adaptation_status=AdaptationStatus.FAILED, with_extraction=False
        )
        assert result.successful is False

    def test_not_successful_when_extraction_none(self) -> None:
        result = self._result(with_extraction=False)
        assert result.successful is False

    def test_is_frozen(self) -> None:
        result = self._result()
        with pytest.raises(Exception):  # noqa: B017
            result.extraction = None  # type: ignore[misc]

    def test_requires_tz_aware_created_at(self) -> None:
        from cmm.cognitive import InvalidExtractionError
        from cmm.cognitive.adapters import ResourceAdaptationResult

        adaptation = ResourceAdaptationResult(
            adapter_name="x",
            adapter_version="1",
            input_id="i1",
            status=AdaptationStatus.FAILED,
        )
        with pytest.raises(InvalidExtractionError, match="timezone-aware"):
            AdaptAndExtractResult(
                adaptation=adaptation,
                extraction=None,
                created_at=datetime(2026, 1, 1),  # naive  # noqa: DTZ001
            )

    def test_to_dict_has_expected_keys(self) -> None:
        result = self._result()
        d = result.to_dict()
        assert "id" in d
        assert "adaptation" in d
        assert "extraction" in d
        assert "successful" in d
        assert "created_at" in d

    def test_to_dict_extraction_is_none_when_absent(self) -> None:
        result = self._result(with_extraction=False)
        d = result.to_dict()
        assert d["extraction"] is None


# ── ResourceExtractionService ─────────────────────────────────────────────────


class TestResourceExtractionService:
    def test_adapt_text_succeeds(self) -> None:
        svc = _build_service()
        result = svc.adapt(_text_input())
        assert result.status is AdaptationStatus.COMPLETED
        assert result.resource is not None

    def test_adapt_mapping_succeeds(self) -> None:
        svc = _build_service()
        result = svc.adapt(_mapping_input())
        assert result.status is AdaptationStatus.COMPLETED

    def test_adapt_empty_text_fails(self) -> None:
        svc = _build_service()
        result = svc.adapt(_empty_text_input())
        assert result.status is AdaptationStatus.FAILED

    def test_adapt_and_extract_full_pipeline(self) -> None:
        svc = _build_service()
        # We need INFER permission on the adapted resource — we can't inject
        # a permission into what the adapter creates, so we test with a resource
        # that already has infer. The text extractor will fail without INFER
        # (default resource has no explicit permissions, only READ by default).
        # This is correct behaviour per spec.
        result = svc.adapt_and_extract(_text_input())
        assert isinstance(result, AdaptAndExtractResult)
        assert result.adaptation.status is AdaptationStatus.COMPLETED
        # The extraction will be FAILED because the adapted resource has no INFER perm
        assert result.extraction is not None
        assert result.extraction.status is ExtractionStatus.FAILED

    def test_adapt_and_extract_with_infer_permission_succeeds(self) -> None:
        """Use ExistingResourceAdapter to pass a resource with INFER permission."""
        from cmm.cognitive import ExistingResourceAdapter

        # Build a resource that explicitly allows INFER
        resource = Resource(
            domain="test",
            kind=ResourceKind.DOCUMENT,
            source=ResourceSourceKind.USER_INPUT,
            content="The patient recovered quickly. Is full recovery expected?",
            provenance=ResourceProvenance(
                source_type=ResourceSourceKind.USER_INPUT, source_id="s1"
            ),
            reliability=Confidence(1.0),
            temporal_scope=ResourceTemporalScope(),
            permissions=(_infer_permission(),),
        )

        adapter_reg = ResourceAdapterRegistry()
        adapter_reg.register(ExistingResourceAdapter())

        extractor_reg = KnowledgeExtractorRegistry()
        extractor_reg.register(PlainTextKnowledgeExtractor())

        svc = ResourceExtractionService(adapter_reg, extractor_reg)

        inp = ResourceInput(
            id="inp-existing",
            source_kind=ResourceSourceKind.MEMORY,
            payload=resource,
        )
        result = svc.adapt_and_extract(inp)
        assert result.adaptation.successful
        assert result.extraction is not None
        assert result.extraction.successful
        assert result.extraction.candidate_count > 0

    def test_adapt_failure_skips_extraction(self) -> None:
        svc = _build_service()
        result = svc.adapt_and_extract(_empty_text_input())
        assert result.adaptation.status is AdaptationStatus.FAILED
        assert result.extraction is None

    def test_no_compatible_adapter_skips_extraction(self) -> None:
        from cmm.cognitive import ComponentNotCompatibleError

        svc = _build_service()
        # Unsupported payload → ComponentNotCompatibleError from resolve
        with pytest.raises(ComponentNotCompatibleError):
            svc.adapt_and_extract(_unsupported_input())

    def test_context_propagation_trace_id(self) -> None:
        svc = _build_service()
        ctx = AdaptationContext(trace_id="trace-xyz", actor_id="user-1")
        result = svc.adapt_and_extract(_text_input(), adaptation_context=ctx)
        assert result.metadata.get("trace_id") == "trace-xyz"
        assert result.metadata.get("actor_id") == "user-1"

    def test_context_propagation_domain(self) -> None:
        svc = _build_service()
        ctx = AdaptationContext(target_domain="health", trace_id="t1")
        result = svc.adapt_and_extract(_text_input(), adaptation_context=ctx)
        assert result.metadata.get("domain") == "health"

    def test_explicit_extraction_context_overrides_propagation(self) -> None:
        from cmm.cognitive import ExistingResourceAdapter

        resource = Resource(
            domain="test",
            kind=ResourceKind.DOCUMENT,
            source=ResourceSourceKind.USER_INPUT,
            content="Hello world sentence.",
            provenance=ResourceProvenance(
                source_type=ResourceSourceKind.USER_INPUT, source_id="s1"
            ),
            reliability=Confidence(1.0),
            temporal_scope=ResourceTemporalScope(),
            permissions=(_infer_permission(),),
        )

        adapter_reg = ResourceAdapterRegistry()
        adapter_reg.register(ExistingResourceAdapter())

        extractor_reg = KnowledgeExtractorRegistry()
        extractor_reg.register(PlainTextKnowledgeExtractor())

        svc = ResourceExtractionService(adapter_reg, extractor_reg)

        inp = ResourceInput(
            id="inp-ctx",
            source_kind=ResourceSourceKind.MEMORY,
            payload=resource,
        )
        explicit_ctx = ExtractionContext(max_candidates=2, actor_id="explicit-actor")
        result = svc.adapt_and_extract(inp, extraction_context=explicit_ctx)
        assert result.extraction is not None
        assert result.extraction.candidate_count <= 2

    def test_extract_directly(self) -> None:

        resource = Resource(
            domain="test",
            kind=ResourceKind.DOCUMENT,
            source=ResourceSourceKind.USER_INPUT,
            content="Direct extraction test sentence.",
            provenance=ResourceProvenance(
                source_type=ResourceSourceKind.USER_INPUT, source_id="s1"
            ),
            reliability=Confidence(1.0),
            temporal_scope=ResourceTemporalScope(),
            permissions=(_infer_permission(),),
        )

        _, extractor_reg = ResourceAdapterRegistry(), KnowledgeExtractorRegistry()
        extractor_reg.register(PlainTextKnowledgeExtractor())
        svc = ResourceExtractionService(ResourceAdapterRegistry(), extractor_reg)
        result = svc.extract(resource)
        assert result.successful

    def test_full_pipeline_to_dict_is_serialisable(self) -> None:
        from cmm.cognitive import ExistingResourceAdapter

        resource = Resource(
            domain="test",
            kind=ResourceKind.DOCUMENT,
            source=ResourceSourceKind.USER_INPUT,
            content="Serialise everything.",
            provenance=ResourceProvenance(
                source_type=ResourceSourceKind.USER_INPUT, source_id="s1"
            ),
            reliability=Confidence(1.0),
            temporal_scope=ResourceTemporalScope(),
            permissions=(_infer_permission(),),
        )

        adapter_reg = ResourceAdapterRegistry()
        adapter_reg.register(ExistingResourceAdapter())

        extractor_reg = KnowledgeExtractorRegistry()
        extractor_reg.register(PlainTextKnowledgeExtractor())

        svc = ResourceExtractionService(adapter_reg, extractor_reg)

        inp = ResourceInput(
            id="inp-serial",
            source_kind=ResourceSourceKind.MEMORY,
            payload=resource,
        )
        result = svc.adapt_and_extract(inp)
        d = result.to_dict()
        import json

        # Must be JSON-serialisable (resource content is a str, so it should work)
        raw = json.dumps(d, default=str)
        assert isinstance(raw, str)
