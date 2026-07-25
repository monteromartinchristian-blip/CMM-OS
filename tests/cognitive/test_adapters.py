"""Tests for Phase 8.3 adapters."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.cognitive import (
    AdaptationStatus,
    AdaptationContext,
    ExistingResourceAdapter,
    MappingResourceAdapter,
    PlainTextResourceAdapter,
    Resource,
    ResourceAdaptationResult,
    ResourceInput,
    ResourceKind,
    ResourcePermission,
    ResourcePermissionOperation,
    ResourceSourceKind,
    SensitivityLevel,
    InvalidResourceInputError,
)
from cmm.cognitive.contracts import Confidence
from cmm.cognitive.resources import ResourceProvenance, ResourceTemporalScope


# ── Fixtures ──────────────────────────────────────────────────────────────────


def _simple_text_input(**kwargs) -> ResourceInput:
    return ResourceInput(
        id="input-001",
        source_kind=ResourceSourceKind.USER_INPUT,
        payload="Hello, world! This is a test.",
        **kwargs,
    )


def _minimal_resource(
    content: object = "some text",
    kind: ResourceKind = ResourceKind.DOCUMENT,
    permissions: tuple = (),
) -> Resource:
    return Resource(
        domain="test",
        kind=kind,
        source=ResourceSourceKind.USER_INPUT,
        content=content,
        provenance=ResourceProvenance(
            source_type=ResourceSourceKind.USER_INPUT,
            source_id="src-1",
        ),
        reliability=Confidence(1.0),
        temporal_scope=ResourceTemporalScope(),
        permissions=permissions,
    )


# ── ResourceInput contract tests ──────────────────────────────────────────────


def test_resource_input_valid_construction() -> None:
    inp = ResourceInput(
        id="inp-1",
        source_kind=ResourceSourceKind.LOCAL_FILE,
        payload="content",
        name="test.txt",
        mime_type="text/plain",
        language="en",
        author="Alice",
        location="/tmp/test.txt",
        sensitivity=SensitivityLevel.PUBLIC,
        metadata={"key": "value"},
    )
    assert inp.id == "inp-1"
    assert inp.sensitivity is SensitivityLevel.PUBLIC
    assert inp.metadata == {"key": "value"}


def test_resource_input_rejects_empty_id() -> None:
    with pytest.raises(InvalidResourceInputError, match="id must not be empty"):
        ResourceInput(id="  ", source_kind=ResourceSourceKind.USER_INPUT, payload="x")


def test_resource_input_rejects_blank_mime_type() -> None:
    with pytest.raises(InvalidResourceInputError, match="mime_type"):
        ResourceInput(
            id="i1",
            source_kind=ResourceSourceKind.USER_INPUT,
            payload="x",
            mime_type="   ",
        )


def test_resource_input_rejects_naive_content_created_at() -> None:
    with pytest.raises(InvalidResourceInputError, match="content_created_at"):
        ResourceInput(
            id="i1",
            source_kind=ResourceSourceKind.USER_INPUT,
            payload="x",
            content_created_at=datetime(2026, 1, 1),  # naive
        )


def test_resource_input_accepts_aware_datetime() -> None:
    aware = datetime(2026, 1, 1, tzinfo=timezone.utc)
    inp = ResourceInput(
        id="i1",
        source_kind=ResourceSourceKind.USER_INPUT,
        payload="x",
        content_created_at=aware,
    )
    assert inp.content_created_at == aware


def test_resource_input_metadata_is_defensive_copy() -> None:
    original = {"a": 1}
    inp = ResourceInput(
        id="i1",
        source_kind=ResourceSourceKind.USER_INPUT,
        payload="x",
        metadata=original,
    )
    original["b"] = 2
    assert "b" not in inp.metadata


def test_resource_input_to_dict_is_structured() -> None:
    inp = _simple_text_input(
        mime_type="text/plain",
        language="en",
        sensitivity=SensitivityLevel.INTERNAL,
    )
    d = inp.to_dict()
    assert d["id"] == "input-001"
    assert d["mime_type"] == "text/plain"
    assert d["language"] == "en"


# ── AdaptationContext tests ───────────────────────────────────────────────────


def test_adaptation_context_defaults_are_aware() -> None:
    ctx = AdaptationContext()
    assert ctx.timestamp.tzinfo is not None


def test_adaptation_context_rejects_naive_timestamp() -> None:
    from cmm.cognitive import InvalidAdaptationError

    with pytest.raises(InvalidAdaptationError, match="timezone-aware"):
        AdaptationContext(timestamp=datetime(2026, 1, 1))


def test_adaptation_context_to_dict() -> None:
    ctx = AdaptationContext(
        actor_id="user-1",
        target_domain="health",
        trace_id="trace-abc",
    )
    d = ctx.to_dict()
    assert d["actor_id"] == "user-1"
    assert d["target_domain"] == "health"
    assert d["trace_id"] == "trace-abc"


# ── PlainTextResourceAdapter ──────────────────────────────────────────────────


class TestPlainTextResourceAdapter:
    adapter = PlainTextResourceAdapter()

    def test_supports_str_payload(self) -> None:
        assert self.adapter.supports(_simple_text_input())

    def test_supports_utf8_bytes(self) -> None:
        inp = ResourceInput(
            id="b1",
            source_kind=ResourceSourceKind.USER_INPUT,
            payload=b"hello bytes",
        )
        assert self.adapter.supports(inp)

    def test_supports_text_mime(self) -> None:
        inp = ResourceInput(
            id="m1",
            source_kind=ResourceSourceKind.LOCAL_FILE,
            payload="hello",
            mime_type="text/plain",
        )
        assert self.adapter.supports(inp)

    def test_does_not_support_dict(self) -> None:
        inp = ResourceInput(
            id="d1",
            source_kind=ResourceSourceKind.USER_INPUT,
            payload={"key": "val"},
        )
        assert not self.adapter.supports(inp)

    def test_adapt_str_returns_completed(self) -> None:
        result = self.adapter.adapt(_simple_text_input())
        assert result.status is AdaptationStatus.COMPLETED
        assert result.resource is not None
        assert isinstance(result.resource.content, str)

    def test_adapt_bytes_decodes_and_succeeds(self) -> None:
        inp = ResourceInput(
            id="b2",
            source_kind=ResourceSourceKind.USER_INPUT,
            payload="Encoded content".encode("utf-8"),
        )
        result = self.adapter.adapt(inp)
        assert result.status is AdaptationStatus.COMPLETED
        assert result.resource is not None
        assert result.resource.content == "Encoded content"

    def test_adapt_non_utf8_bytes_fails(self) -> None:
        inp = ResourceInput(
            id="b3",
            source_kind=ResourceSourceKind.USER_INPUT,
            payload=b"\xff\xfe invalid bytes",
        )
        result = self.adapter.adapt(inp)
        assert result.status is AdaptationStatus.FAILED
        assert result.has_errors

    def test_adapt_empty_text_fails(self) -> None:
        inp = ResourceInput(
            id="e1",
            source_kind=ResourceSourceKind.USER_INPUT,
            payload="   ",
        )
        result = self.adapter.adapt(inp)
        assert result.status is AdaptationStatus.FAILED
        assert result.has_errors

    def test_adapt_records_provenance_transformation(self) -> None:
        result = self.adapter.adapt(_simple_text_input())
        assert result.resource is not None
        history = result.resource.provenance.transformation_history
        assert len(history) == 1
        assert history[0].operation == "plain_text_adaptation"

    def test_adapt_preserves_sensitivity(self) -> None:
        inp = _simple_text_input(sensitivity=SensitivityLevel.RESTRICTED)
        result = self.adapter.adapt(inp)
        assert result.resource is not None
        assert result.resource.sensitivity is SensitivityLevel.RESTRICTED

    def test_adapt_preserves_language(self) -> None:
        inp = _simple_text_input(language="es")
        result = self.adapter.adapt(inp)
        assert result.resource is not None
        assert result.resource.language == "es"

    def test_adapt_preserves_temporal_fields(self) -> None:
        aware_dt = datetime(2025, 6, 1, tzinfo=timezone.utc)
        inp = _simple_text_input(content_created_at=aware_dt)
        result = self.adapter.adapt(inp)
        assert result.resource is not None
        assert result.resource.temporal_scope.content_created_at == aware_dt

    def test_adapt_sets_checksum_in_provenance(self) -> None:
        result = self.adapter.adapt(_simple_text_input())
        assert result.resource is not None
        assert result.resource.provenance.checksum is not None

    def test_adapt_with_context_sets_domain(self) -> None:
        ctx = AdaptationContext(target_domain="education")
        result = self.adapter.adapt(_simple_text_input(), context=ctx)
        assert result.resource is not None
        assert result.resource.domain == "education"

    def test_result_is_immutable(self) -> None:
        result = self.adapter.adapt(_simple_text_input())
        with pytest.raises(Exception):
            result.status = AdaptationStatus.FAILED  # type: ignore[misc]

    def test_result_successful_property(self) -> None:
        result = self.adapter.adapt(_simple_text_input())
        assert result.successful is True

    def test_result_to_dict_serialisable(self) -> None:
        result = self.adapter.adapt(_simple_text_input())
        d = result.to_dict()
        assert d["status"] == "completed"
        assert d["successful"] is True
        assert "resource" in d

    def test_adapter_name_and_version(self) -> None:
        assert self.adapter.name == "plain_text"
        assert isinstance(self.adapter.version, str)

    def test_duration_ms_is_non_negative(self) -> None:
        result = self.adapter.adapt(_simple_text_input())
        assert result.duration_ms is not None
        assert result.duration_ms >= 0


# ── MappingResourceAdapter ────────────────────────────────────────────────────


class TestMappingResourceAdapter:
    adapter = MappingResourceAdapter()

    def test_supports_dict_payload(self) -> None:
        inp = ResourceInput(
            id="m1",
            source_kind=ResourceSourceKind.STRUCTURED_DATA,
            payload={"name": "Alice", "age": 30},
        )
        assert self.adapter.supports(inp)

    def test_does_not_support_str(self) -> None:
        assert not self.adapter.supports(_simple_text_input())

    def test_adapt_dict_returns_completed(self) -> None:
        inp = ResourceInput(
            id="m2",
            source_kind=ResourceSourceKind.STRUCTURED_DATA,
            payload={"key": "value"},
        )
        result = self.adapter.adapt(inp)
        assert result.status is AdaptationStatus.COMPLETED
        assert result.resource is not None

    def test_adapt_preserves_dict_structure(self) -> None:
        data = {"patient": {"name": "Bob", "age": 40}}
        inp = ResourceInput(
            id="m3",
            source_kind=ResourceSourceKind.STRUCTURED_DATA,
            payload=data,
        )
        result = self.adapter.adapt(inp)
        assert result.resource is not None
        assert result.resource.content["patient"]["name"] == "Bob"

    def test_adapt_content_is_defensive_copy(self) -> None:
        original = {"x": 1}
        inp = ResourceInput(
            id="m4",
            source_kind=ResourceSourceKind.STRUCTURED_DATA,
            payload=original,
        )
        result = self.adapter.adapt(inp)
        original["y"] = 2
        assert result.resource is not None
        assert "y" not in result.resource.content

    def test_adapt_unsupported_payload_fails(self) -> None:
        inp = ResourceInput(
            id="m5",
            source_kind=ResourceSourceKind.STRUCTURED_DATA,
            payload=12345,  # integer is not a mapping
        )
        result = self.adapter.adapt(inp)
        assert result.status is AdaptationStatus.UNSUPPORTED

    def test_adapt_records_mapping_transformation(self) -> None:
        inp = ResourceInput(
            id="m6",
            source_kind=ResourceSourceKind.STRUCTURED_DATA,
            payload={"k": "v"},
        )
        result = self.adapter.adapt(inp)
        assert result.resource is not None
        history = result.resource.provenance.transformation_history
        assert history[0].operation == "mapping_adaptation"

    def test_metadata_from_input_propagates(self) -> None:
        inp = ResourceInput(
            id="m7",
            source_kind=ResourceSourceKind.STRUCTURED_DATA,
            payload={"k": "v"},
            metadata={"source_system": "ehr"},
        )
        result = self.adapter.adapt(inp)
        assert result.resource is not None
        # source input metadata should appear in provenance metadata
        assert result.resource.provenance.metadata.get("source_system") == "ehr"


# ── ExistingResourceAdapter ───────────────────────────────────────────────────


class TestExistingResourceAdapter:
    adapter = ExistingResourceAdapter()

    def _resource_input_with(self, resource: Resource) -> ResourceInput:
        return ResourceInput(
            id="pass-1",
            source_kind=ResourceSourceKind.MEMORY,
            payload=resource,
        )

    def test_supports_resource_payload(self) -> None:
        r = _minimal_resource()
        inp = self._resource_input_with(r)
        assert self.adapter.supports(inp)

    def test_does_not_support_str_payload(self) -> None:
        assert not self.adapter.supports(_simple_text_input())

    def test_adapt_returns_same_resource_object(self) -> None:
        r = _minimal_resource()
        inp = self._resource_input_with(r)
        result = self.adapter.adapt(inp)
        assert result.status is AdaptationStatus.COMPLETED
        assert result.resource is r  # identical object, not a copy

    def test_adapt_does_not_modify_resource(self) -> None:
        r = _minimal_resource(content="original")
        inp = self._resource_input_with(r)
        self.adapter.adapt(inp)
        assert r.content == "original"

    def test_adapt_records_already_normalised_in_metadata(self) -> None:
        r = _minimal_resource()
        inp = self._resource_input_with(r)
        result = self.adapter.adapt(inp)
        assert result.metadata.get("already_normalised") is True

    def test_adapt_fails_when_read_not_permitted(self) -> None:
        # Create a resource with only INFER allowed (no READ)
        perm = ResourcePermission(
            allowed_operations=(ResourcePermissionOperation.INFER,)
        )
        r = _minimal_resource(permissions=(perm,))
        inp = self._resource_input_with(r)
        result = self.adapter.adapt(inp)
        assert result.status is AdaptationStatus.FAILED
        assert result.has_errors

    def test_adapt_unsupported_payload_returns_unsupported(self) -> None:
        inp = ResourceInput(
            id="x1",
            source_kind=ResourceSourceKind.MEMORY,
            payload="not a resource",
        )
        result = self.adapter.adapt(inp)
        assert result.status is AdaptationStatus.UNSUPPORTED


# ── ResourceAdaptationResult contract ─────────────────────────────────────────


class TestResourceAdaptationResultContract:
    def test_result_is_frozen(self) -> None:
        result = PlainTextResourceAdapter().adapt(_simple_text_input())
        with pytest.raises(Exception):
            result.status = AdaptationStatus.FAILED  # type: ignore[misc]

    def test_result_requires_tz_aware_created_at(self) -> None:
        from cmm.cognitive import InvalidAdaptationError

        with pytest.raises(InvalidAdaptationError, match="timezone-aware"):
            ResourceAdaptationResult(
                adapter_name="x",
                adapter_version="1",
                input_id="i1",
                status=AdaptationStatus.COMPLETED,
                created_at=datetime(2026, 1, 1),  # naive
            )

    def test_result_rejects_negative_duration(self) -> None:
        from cmm.cognitive import InvalidAdaptationError

        with pytest.raises(InvalidAdaptationError, match="duration_ms"):
            ResourceAdaptationResult(
                adapter_name="x",
                adapter_version="1",
                input_id="i1",
                status=AdaptationStatus.FAILED,
                duration_ms=-1.0,
            )

    def test_has_warnings_and_has_errors(self) -> None:
        result = ResourceAdaptationResult(
            adapter_name="x",
            adapter_version="1",
            input_id="i1",
            status=AdaptationStatus.FAILED,
            warnings=("watch out",),
            errors=("something broke",),
        )
        assert result.has_warnings is True
        assert result.has_errors is True

    def test_partial_is_successful(self) -> None:
        result = ResourceAdaptationResult(
            adapter_name="x",
            adapter_version="1",
            input_id="i1",
            status=AdaptationStatus.PARTIAL,
        )
        assert result.successful is True

    def test_unsupported_is_not_successful(self) -> None:
        result = ResourceAdaptationResult(
            adapter_name="x",
            adapter_version="1",
            input_id="i1",
            status=AdaptationStatus.UNSUPPORTED,
        )
        assert result.successful is False

    def test_to_dict_contains_all_keys(self) -> None:
        result = ResourceAdaptationResult(
            adapter_name="plain_text",
            adapter_version="1.0.0",
            input_id="i1",
            status=AdaptationStatus.COMPLETED,
        )
        d = result.to_dict()
        for key in (
            "id",
            "adapter_name",
            "adapter_version",
            "input_id",
            "status",
            "resource",
            "warnings",
            "errors",
            "created_at",
            "successful",
        ):
            assert key in d
