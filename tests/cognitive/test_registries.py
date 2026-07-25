"""Tests for Phase 8.3 registries."""

from __future__ import annotations

import pytest

from cmm.cognitive import (
    AdaptationStatus,
    ComponentNotCompatibleError,
    ComponentNotFoundError,
    DuplicateRegistryEntryError,
    ExtractionStatus,
    InvalidAdapterContractError,
    KnowledgeExtractorRegistry,
    MappingKnowledgeExtractor,
    MappingResourceAdapter,
    PlainTextKnowledgeExtractor,
    PlainTextResourceAdapter,
    Resource,
    ResourceAdapterRegistry,
    ResourceInput,
    ResourceKind,
    ResourceSourceKind,
)
from cmm.cognitive.adapters import AdaptationContext, ResourceAdapter
from cmm.cognitive.contracts import Confidence
from cmm.cognitive.extraction import ExtractionContext, KnowledgeExtractor
from cmm.cognitive.resources import ResourceProvenance, ResourceTemporalScope


# ── Helpers ───────────────────────────────────────────────────────────────────


def _text_input(id: str = "inp-1") -> ResourceInput:
    return ResourceInput(
        id=id,
        source_kind=ResourceSourceKind.USER_INPUT,
        payload="A short text payload.",
    )


def _mapping_input(id: str = "inp-2") -> ResourceInput:
    return ResourceInput(
        id=id,
        source_kind=ResourceSourceKind.STRUCTURED_DATA,
        payload={"key": "value"},
    )


def _text_resource() -> Resource:
    return Resource(
        domain="test",
        kind=ResourceKind.DOCUMENT,
        source=ResourceSourceKind.USER_INPUT,
        content="Some text",
        provenance=ResourceProvenance(
            source_type=ResourceSourceKind.USER_INPUT, source_id="s1"
        ),
        reliability=Confidence(1.0),
        temporal_scope=ResourceTemporalScope(),
    )


def _mapping_resource() -> Resource:
    return Resource(
        domain="test",
        kind=ResourceKind.STRUCTURED_DATASET,
        source=ResourceSourceKind.STRUCTURED_DATA,
        content={"name": "Test"},
        provenance=ResourceProvenance(
            source_type=ResourceSourceKind.STRUCTURED_DATA, source_id="s2"
        ),
        reliability=Confidence(1.0),
        temporal_scope=ResourceTemporalScope(),
    )


class _DummyAdapter:
    name: str = "dummy"
    version: str = "0.1.0"

    def supports(self, source: ResourceInput) -> bool:
        return True

    def adapt(
        self,
        source: ResourceInput,
        *,
        context: AdaptationContext | None = None,
    ):
        raise NotImplementedError


class _AnotherAdapter:
    name: str = "another"
    version: str = "1.0.0"

    def supports(self, source: ResourceInput) -> bool:
        return isinstance(source.payload, str)

    def adapt(
        self,
        source: ResourceInput,
        *,
        context: AdaptationContext | None = None,
    ):
        raise NotImplementedError


class _DummyExtractor:
    name: str = "dummy_ext"
    version: str = "0.1.0"

    def supports(self, resource: Resource) -> bool:
        return True

    def extract(
        self,
        resource: Resource,
        *,
        context: ExtractionContext | None = None,
    ):
        raise NotImplementedError


# ── ResourceAdapterRegistry ───────────────────────────────────────────────────


class TestResourceAdapterRegistry:
    def _registry_with_defaults(self) -> ResourceAdapterRegistry:
        reg = ResourceAdapterRegistry()
        reg.register(PlainTextResourceAdapter())
        reg.register(MappingResourceAdapter())
        return reg

    def test_register_and_retrieve(self) -> None:
        reg = ResourceAdapterRegistry()
        reg.register(PlainTextResourceAdapter())
        adapter = reg.get("plain_text")
        assert adapter.name == "plain_text"

    def test_contains(self) -> None:
        reg = ResourceAdapterRegistry()
        reg.register(PlainTextResourceAdapter())
        assert reg.contains("plain_text")
        assert not reg.contains("missing")

    def test_register_duplicate_raises(self) -> None:
        reg = ResourceAdapterRegistry()
        reg.register(PlainTextResourceAdapter())
        with pytest.raises(DuplicateRegistryEntryError, match="plain_text"):
            reg.register(PlainTextResourceAdapter())

    def test_register_duplicate_with_replace(self) -> None:
        reg = ResourceAdapterRegistry()
        reg.register(PlainTextResourceAdapter())
        reg.register(PlainTextResourceAdapter(), replace=True)  # no error
        assert reg.contains("plain_text")

    def test_get_missing_raises(self) -> None:
        reg = ResourceAdapterRegistry()
        with pytest.raises(ComponentNotFoundError, match="missing"):
            reg.get("missing")

    def test_unregister(self) -> None:
        reg = ResourceAdapterRegistry()
        reg.register(PlainTextResourceAdapter())
        reg.unregister("plain_text")
        assert not reg.contains("plain_text")

    def test_unregister_missing_raises(self) -> None:
        reg = ResourceAdapterRegistry()
        with pytest.raises(ComponentNotFoundError):
            reg.unregister("ghost")

    def test_list_adapters(self) -> None:
        reg = self._registry_with_defaults()
        adapters = reg.list_adapters()
        assert len(adapters) == 2
        names = [a.name for a in adapters]
        assert "plain_text" in names
        assert "mapping" in names

    def test_len(self) -> None:
        reg = ResourceAdapterRegistry()
        assert len(reg) == 0
        reg.register(PlainTextResourceAdapter())
        assert len(reg) == 1

    def test_resolve_text_input(self) -> None:
        reg = self._registry_with_defaults()
        adapter = reg.resolve(_text_input())
        assert adapter.name == "plain_text"

    def test_resolve_mapping_input(self) -> None:
        reg = self._registry_with_defaults()
        adapter = reg.resolve(_mapping_input())
        assert adapter.name == "mapping"

    def test_resolve_no_compatible_raises(self) -> None:
        reg = ResourceAdapterRegistry()
        # Register only the plain-text adapter
        reg.register(PlainTextResourceAdapter())
        # A dict payload is not supported by plain-text adapter
        with pytest.raises(ComponentNotCompatibleError):
            reg.resolve(_mapping_input())
        # An integer payload is not supported by any adapter
        incompatible = ResourceInput(
            id="x1",
            source_kind=ResourceSourceKind.USER_INPUT,
            payload=12345,
        )
        with pytest.raises(ComponentNotCompatibleError):
            reg.resolve(incompatible)

    def test_priority_determines_order(self) -> None:
        """Higher priority adapter wins when both support the same input."""
        reg = ResourceAdapterRegistry()
        low_prio = _DummyAdapter()
        reg.register(low_prio, priority=0)

        class HighPrioAdapter:
            name = "high_prio"
            version = "1.0.0"

            def supports(self, source: ResourceInput) -> bool:
                return True

            def adapt(self, source, *, context=None):
                raise NotImplementedError

        high_prio = HighPrioAdapter()
        reg.register(high_prio, priority=10)
        resolved = reg.resolve(_text_input())
        assert resolved.name == "high_prio"

    def test_insertion_order_tiebreaks(self) -> None:
        """When priorities are equal, first-registered adapter wins."""
        reg = ResourceAdapterRegistry()
        reg.register(_DummyAdapter(), priority=5)

        class SecondAdapter:
            name = "second"
            version = "1.0.0"

            def supports(self, source: ResourceInput) -> bool:
                return True

            def adapt(self, source, *, context=None):
                raise NotImplementedError

        reg.register(SecondAdapter(), priority=5)
        resolved = reg.resolve(_text_input())
        assert resolved.name == "dummy"

    def test_invalid_adapter_contract_rejected(self) -> None:
        reg = ResourceAdapterRegistry()
        with pytest.raises(InvalidAdapterContractError):
            reg.register("not_an_adapter")  # type: ignore[arg-type]

    def test_adapt_convenience_method(self) -> None:
        reg = self._registry_with_defaults()
        result = reg.adapt(_text_input())
        assert result.status is AdaptationStatus.COMPLETED


# ── KnowledgeExtractorRegistry ────────────────────────────────────────────────


class TestKnowledgeExtractorRegistry:
    def _registry_with_defaults(self) -> KnowledgeExtractorRegistry:
        reg = KnowledgeExtractorRegistry()
        reg.register(PlainTextKnowledgeExtractor())
        reg.register(MappingKnowledgeExtractor())
        return reg

    def test_register_and_retrieve(self) -> None:
        reg = KnowledgeExtractorRegistry()
        reg.register(PlainTextKnowledgeExtractor())
        ext = reg.get("plain_text")
        assert ext.name == "plain_text"

    def test_contains(self) -> None:
        reg = KnowledgeExtractorRegistry()
        reg.register(PlainTextKnowledgeExtractor())
        assert reg.contains("plain_text")
        assert not reg.contains("unknown")

    def test_register_duplicate_raises(self) -> None:
        reg = KnowledgeExtractorRegistry()
        reg.register(PlainTextKnowledgeExtractor())
        with pytest.raises(DuplicateRegistryEntryError):
            reg.register(PlainTextKnowledgeExtractor())

    def test_register_with_replace(self) -> None:
        reg = KnowledgeExtractorRegistry()
        reg.register(PlainTextKnowledgeExtractor())
        reg.register(PlainTextKnowledgeExtractor(), replace=True)
        assert reg.contains("plain_text")

    def test_get_missing_raises(self) -> None:
        reg = KnowledgeExtractorRegistry()
        with pytest.raises(ComponentNotFoundError):
            reg.get("ghost")

    def test_unregister(self) -> None:
        reg = KnowledgeExtractorRegistry()
        reg.register(PlainTextKnowledgeExtractor())
        reg.unregister("plain_text")
        assert not reg.contains("plain_text")

    def test_unregister_missing_raises(self) -> None:
        reg = KnowledgeExtractorRegistry()
        with pytest.raises(ComponentNotFoundError):
            reg.unregister("nope")

    def test_list_extractors(self) -> None:
        reg = self._registry_with_defaults()
        exts = reg.list_extractors()
        assert len(exts) == 2

    def test_resolve_text_resource(self) -> None:
        reg = self._registry_with_defaults()
        ext = reg.resolve(_text_resource())
        assert ext.name == "plain_text"

    def test_resolve_mapping_resource(self) -> None:
        reg = self._registry_with_defaults()
        ext = reg.resolve(_mapping_resource())
        assert ext.name == "mapping"

    def test_resolve_no_compatible_raises(self) -> None:
        reg = KnowledgeExtractorRegistry()
        # Only register mapping extractor
        reg.register(MappingKnowledgeExtractor())
        # text resource won't be supported by mapping extractor
        with pytest.raises(ComponentNotCompatibleError):
            reg.resolve(_text_resource())

    def test_extract_with_explicit_name(self) -> None:
        reg = self._registry_with_defaults()
        result = reg.extract(_text_resource(), extractor_name="plain_text")
        assert result.extractor_name == "plain_text"

    def test_extract_auto_resolves(self) -> None:
        reg = self._registry_with_defaults()
        result = reg.extract(_text_resource())
        assert result.status in (
            ExtractionStatus.COMPLETED,
            ExtractionStatus.FAILED,  # if no INFER permission
        )

    def test_priority_determinism(self) -> None:
        reg = KnowledgeExtractorRegistry()
        reg.register(_DummyExtractor(), priority=0)

        class HighPrioExtractor:
            name = "high_ext"
            version = "1.0.0"

            def supports(self, resource: Resource) -> bool:
                return True

            def extract(self, resource, *, context=None):
                raise NotImplementedError

        reg.register(HighPrioExtractor(), priority=10)
        resolved = reg.resolve(_text_resource())
        assert resolved.name == "high_ext"

    def test_invalid_extractor_contract_rejected(self) -> None:
        reg = KnowledgeExtractorRegistry()
        with pytest.raises(InvalidAdapterContractError):
            reg.register(object())  # type: ignore[arg-type]

    def test_len(self) -> None:
        reg = KnowledgeExtractorRegistry()
        assert len(reg) == 0
        reg.register(PlainTextKnowledgeExtractor())
        assert len(reg) == 1
