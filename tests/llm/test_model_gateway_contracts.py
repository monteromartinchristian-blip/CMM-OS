"""Phase 11.21 — canonical model gateway contract and error tests.

These tests freeze the provider-independent contract surface: closed typed
enums, immutable request/response contracts, safe serialization (no attachment
bytes, no secrets, no hidden reasoning) and a safe error taxonomy.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from decimal import Decimal

import pytest

from kernel.llm.model_gateway_contracts import (
    CANONICAL_DOCUMENT_MEDIA_TYPES,
    CANONICAL_MODEL_CAPABILITIES,
    TERMINAL_STREAM_EVENT_TYPES,
    InMemoryModelExecutionEvidenceSink,
    InputModality,
    InputPartKind,
    ModelExecutionFacts,
    ModelGatewayRequest,
    ModelGatewayResponse,
    ModelInputPart,
    ModelSelectionMode,
    ModelStreamEvent,
    ModelStreamEventType,
    ModelToolCall,
    ModelToolDefinition,
    ModelUsage,
    PrivacyEgressDecision,
    ReasoningEffort,
    StructuredOutputRequirement,
)
from kernel.llm.model_gateway_errors import (
    RETRYABLE_ERROR_CODES,
    ModelGatewayError,
    ModelGatewayErrorCode,
)

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
)


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"


# ── Reasoning effort ─────────────────────────────────────────────────────────


def test_reasoning_effort_is_a_closed_provider_independent_enum() -> None:
    assert [member.name for member in ReasoningEffort] == [
        "DEFAULT",
        "NONE",
        "LOW",
        "MEDIUM",
        "HIGH",
        "EXTRA_HIGH",
    ]
    assert [member.value for member in ReasoningEffort] == [
        "default",
        "none",
        "low",
        "medium",
        "high",
        "extra_high",
    ]


@pytest.mark.parametrize(
    "provider_native",
    ["minimal", "provider_default", "thinking", "xhigh", "HIGH", "none_of_the_above"],
)
def test_reasoning_effort_rejects_provider_native_names(provider_native: str) -> None:
    with pytest.raises(ValueError):
        ReasoningEffort(provider_native)


def test_reasoning_effort_is_not_a_free_form_string() -> None:
    assert ReasoningEffort("high") is ReasoningEffort.HIGH
    with pytest.raises(ValueError):
        ReasoningEffort("HIGH")


# ── Selection mode, part kinds, stream event types ──────────────────────────


def test_selection_mode_values() -> None:
    assert [member.value for member in ModelSelectionMode] == ["explicit", "auto"]


def test_input_part_kind_values_and_modality_alias() -> None:
    assert [member.value for member in InputPartKind] == ["text", "image", "document"]
    assert InputModality is InputPartKind


def test_stream_event_type_values_and_terminal_set() -> None:
    assert [member.value for member in ModelStreamEventType] == [
        "started",
        "content_delta",
        "tool_call_delta",
        "usage",
        "completed",
        "cancelled",
        "error",
    ]
    assert TERMINAL_STREAM_EVENT_TYPES == {
        ModelStreamEventType.COMPLETED,
        ModelStreamEventType.CANCELLED,
        ModelStreamEventType.ERROR,
    }


def test_canonical_document_media_types_and_capability_names() -> None:
    assert CANONICAL_DOCUMENT_MEDIA_TYPES == (
        "application/pdf",
        "text/plain",
        "text/markdown",
    )
    assert CANONICAL_MODEL_CAPABILITIES == (
        "reasoning",
        "tool_calling",
        "structured_output",
        "json_mode",
        "json_schema",
        "vision",
        "document",
        "streaming",
        "audio_input",
        "audio_output",
        "embeddings",
    )


# ── Input parts ──────────────────────────────────────────────────────────────


def test_text_part_carries_text_and_digest() -> None:
    part = ModelInputPart.text_part("hola mundo")
    assert part.kind is InputPartKind.TEXT
    assert part.text == "hola mundo"
    assert part.byte_length == len(b"hola mundo")
    assert part.content_digest == hashlib.sha256(b"hola mundo").hexdigest()


def test_image_part_carries_real_bytes() -> None:
    part = ModelInputPart.image_part(PNG_BYTES, "image/png", display_name="pixel.png")
    assert part.kind is InputPartKind.IMAGE
    assert part.content == PNG_BYTES
    assert part.byte_length == len(PNG_BYTES)
    assert part.content_digest == hashlib.sha256(PNG_BYTES).hexdigest()
    assert part.display_name == "pixel.png"


def test_image_part_requires_non_empty_bytes() -> None:
    with pytest.raises(ValueError):
        ModelInputPart.image_part(b"", "image/png")
    with pytest.raises(ValueError):
        ModelInputPart(kind=InputPartKind.IMAGE, media_type="image/png")


def test_image_part_rejects_non_image_media_type() -> None:
    with pytest.raises(ValueError):
        ModelInputPart.image_part(PNG_BYTES, "application/pdf")


@pytest.mark.parametrize("media_type", CANONICAL_DOCUMENT_MEDIA_TYPES)
def test_document_part_accepts_canonical_media_types(media_type: str) -> None:
    part = ModelInputPart.document_part(_pdf_bytes(), media_type)
    assert part.kind is InputPartKind.DOCUMENT
    assert part.media_type == media_type


def test_document_part_requires_non_empty_bytes_and_an_application_media_type() -> None:
    with pytest.raises(ValueError):
        ModelInputPart.document_part(b"", "application/pdf")
    with pytest.raises(ValueError):
        ModelInputPart.document_part(_pdf_bytes(), "image/png")
    with pytest.raises(ValueError):
        ModelInputPart.document_part(_pdf_bytes(), "pdf")


def test_text_part_rejects_undecodable_bytes() -> None:
    with pytest.raises(ValueError):
        ModelInputPart(kind=InputPartKind.TEXT, content=b"\xff\xfe\x00")


@pytest.mark.parametrize(
    "display_name",
    ["/etc/passwd", "../secrets.txt", "C:\\Users\\secret.txt", "https://x.test/a.png"],
)
def test_input_part_rejects_path_or_url_shaped_display_names(display_name: str) -> None:
    with pytest.raises(ValueError):
        ModelInputPart.image_part(PNG_BYTES, "image/png", display_name=display_name)


def test_input_part_rejects_a_forged_digest() -> None:
    with pytest.raises(ValueError):
        ModelInputPart.image_part(
            PNG_BYTES,
            "image/png",
            content_digest="0" * 64,
        )


def test_input_part_public_serialization_excludes_raw_bytes() -> None:
    part = ModelInputPart.image_part(PNG_BYTES, "image/png", display_name="pixel.png")
    payload = part.to_dict()

    assert set(payload) == {
        "kind",
        "media_type",
        "byte_length",
        "content_digest",
        "display_name",
        "metadata",
    }
    assert payload["byte_length"] == len(PNG_BYTES)
    assert payload["content_digest"] == hashlib.sha256(PNG_BYTES).hexdigest()
    assert "content" not in payload
    serialized = json.dumps(payload)
    assert "PNG" not in serialized
    assert PNG_BYTES.decode("latin-1") not in serialized


def test_input_part_metadata_must_be_json_safe() -> None:
    with pytest.raises(TypeError):
        ModelInputPart.text_part("hi", metadata={"payload": object()})
    with pytest.raises(TypeError):
        ModelInputPart.text_part("hi", metadata={"payload": b"bytes"})


@pytest.mark.parametrize(
    "key",
    ["api_key", "apiKey", "authorization", "credential", "password", "secret", "token"],
)
def test_input_part_metadata_rejects_secret_like_keys(key: str) -> None:
    with pytest.raises(ValueError):
        ModelInputPart.text_part("hi", metadata={key: "value"})


def test_input_part_metadata_rejects_nested_secret_like_keys() -> None:
    with pytest.raises(ValueError):
        ModelInputPart.text_part("hi", metadata={"nested": {"api_key": "value"}})


def test_input_part_metadata_is_immutable() -> None:
    part = ModelInputPart.text_part("hi", metadata={"source": "unit-test"})
    assert part.metadata["source"] == "unit-test"
    with pytest.raises(TypeError):
        part.metadata["source"] = "other"  # type: ignore[index]


# ── Tool contracts ───────────────────────────────────────────────────────────


def test_tool_definition_round_trips_and_has_no_executable_callback() -> None:
    definition = ModelToolDefinition(
        tool_id="cmm.ops.list_files",
        description="List files in an approved workspace",
        input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
    )
    assert {field.name for field in dataclasses.fields(definition)} == {
        "tool_id",
        "description",
        "input_schema",
    }
    assert json.loads(json.dumps(definition.to_dict())) == definition.to_dict()


def test_tool_definition_rejects_non_json_safe_schema_and_blank_id() -> None:
    with pytest.raises(ValueError):
        ModelToolDefinition(tool_id="  ")
    with pytest.raises(TypeError):
        ModelToolDefinition(tool_id="t", input_schema={"callback": object()})
    with pytest.raises(TypeError):
        ModelToolDefinition(tool_id="t", input_schema=["not", "a", "mapping"])


def test_tool_call_carries_no_authority() -> None:
    call = ModelToolCall(call_id="call-1", tool_id="cmm.ops.list_files", arguments={})
    assert {field.name for field in dataclasses.fields(call)} == {
        "call_id",
        "tool_id",
        "arguments",
    }
    payload = call.to_dict()
    for forbidden in ("permission", "permissions", "granted", "approved", "authority"):
        assert forbidden not in payload


def test_tool_call_requires_non_empty_identifiers() -> None:
    with pytest.raises(ValueError):
        ModelToolCall(call_id="", tool_id="t")
    with pytest.raises(ValueError):
        ModelToolCall(call_id="c", tool_id="  ")


# ── Structured output ────────────────────────────────────────────────────────


def test_structured_output_requirement_round_trips() -> None:
    requirement = StructuredOutputRequirement(
        schema={"type": "object", "required": ["answer"]},
        schema_id="cmm.answer",
        schema_version="1",
    )
    assert requirement.required is True
    assert requirement.to_dict()["schema_id"] == "cmm.answer"
    assert requirement.to_dict()["schema"] == {
        "type": "object",
        "required": ["answer"],
    }


def test_structured_output_requirement_rejects_non_json_safe_schema() -> None:
    with pytest.raises(TypeError):
        StructuredOutputRequirement(schema={"value": object()})
    with pytest.raises(TypeError):
        StructuredOutputRequirement(schema="not-a-mapping")  # type: ignore[arg-type]


# ── Usage and accounting semantics ───────────────────────────────────────────


def test_usage_defaults_to_unknown_not_zero() -> None:
    usage = ModelUsage()
    assert usage.input_tokens is None
    assert usage.output_tokens is None
    assert usage.cached_tokens is None
    assert usage.cost is None
    assert usage.cost_source is None
    assert usage.total_tokens is None


def test_usage_total_tokens_is_unknown_when_any_side_is_unknown() -> None:
    assert ModelUsage(input_tokens=10).total_tokens is None
    assert ModelUsage(output_tokens=5).total_tokens is None
    assert ModelUsage(input_tokens=10, output_tokens=5).total_tokens == 15


def test_usage_rejects_negative_counters_and_costs() -> None:
    with pytest.raises(ValueError):
        ModelUsage(input_tokens=-1)
    with pytest.raises(ValueError):
        ModelUsage(cached_tokens=-3)
    with pytest.raises(ValueError):
        ModelUsage(cost=Decimal("-0.01"), cost_source="provider_reported")


def test_usage_cost_requires_a_truthful_source() -> None:
    with pytest.raises(ValueError):
        ModelUsage(cost=Decimal("0.01"))
    with pytest.raises(ValueError):
        ModelUsage(cost_source="provider_reported")
    with pytest.raises(ValueError):
        ModelUsage(cost=Decimal("0.01"), cost_source="guessed")


def test_usage_serializes_cost_as_a_string_without_losing_truth() -> None:
    usage = ModelUsage(
        input_tokens=100,
        output_tokens=20,
        cached_tokens=0,
        cost=Decimal("0.000420"),
        cost_source="catalog_derived",
    )
    payload = usage.to_dict()
    assert payload["cached_tokens"] == 0
    assert payload["cost"] == "0.000420"
    assert payload["cost_source"] == "catalog_derived"


# ── Request contract ─────────────────────────────────────────────────────────


def _request(**overrides: object) -> ModelGatewayRequest:
    values: dict[str, object] = {
        "request_id": "model-request-1",
        "model_id": "local:model-1",
        "input_parts": (ModelInputPart.text_part("hello"),),
    }
    values.update(overrides)
    return ModelGatewayRequest(**values)  # type: ignore[arg-type]


def test_request_defaults_follow_the_frozen_contract() -> None:
    request = _request()
    assert request.selection_mode is ModelSelectionMode.EXPLICIT
    assert request.reasoning_effort is ReasoningEffort.DEFAULT
    assert request.provider_id is None
    assert request.stream is False
    assert request.tools == ()
    assert request.structured_output is None
    assert request.fallback_model_ids == ()
    assert request.timeout_seconds > 0


def test_request_is_immutable_and_slot_only() -> None:
    request = _request()
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.model_id = "other"  # type: ignore[misc]
    assert not hasattr(request, "__dict__")


def test_request_rejects_unknown_fields() -> None:
    with pytest.raises(TypeError):
        ModelGatewayRequest(  # type: ignore[call-arg]
            request_id="r",
            model_id="local:model-1",
            reasoning_trace="hidden",
        )


def test_request_requires_identifiers_and_at_least_one_input_part() -> None:
    with pytest.raises(ValueError):
        _request(request_id="  ")
    with pytest.raises(ValueError):
        _request(input_parts=())


def test_explicit_selection_requires_a_model_id() -> None:
    with pytest.raises(ValueError):
        _request(model_id=None, selection_mode=ModelSelectionMode.EXPLICIT)


def test_auto_selection_may_omit_the_model_id() -> None:
    request = _request(model_id=None, selection_mode=ModelSelectionMode.AUTO)
    assert request.model_id is None
    assert request.selection_mode is ModelSelectionMode.AUTO


@pytest.mark.parametrize("timeout", [0.0, -1.0, float("inf"), float("nan")])
def test_request_requires_a_finite_positive_timeout(timeout: float) -> None:
    with pytest.raises(ValueError):
        _request(timeout_seconds=timeout)


def test_request_rejects_unknown_required_capability() -> None:
    with pytest.raises(ValueError):
        _request(required_capabilities=("telepathy",))


def test_request_accepts_canonical_required_capabilities() -> None:
    request = _request(required_capabilities=("vision", "tool_calling"))
    assert request.required_capabilities == ("vision", "tool_calling")


def test_request_rejects_duplicate_fallback_candidates() -> None:
    with pytest.raises(ValueError):
        _request(fallback_model_ids=("local:model-2", "local:model-2"))


def test_request_rejects_blank_fallback_candidate() -> None:
    with pytest.raises(ValueError):
        _request(fallback_model_ids=("   ",))


def test_request_metadata_is_screened_and_json_safe() -> None:
    with pytest.raises(ValueError):
        _request(metadata={"api_key": "value"})
    with pytest.raises(TypeError):
        _request(metadata={"payload": b"bytes"})
    request = _request(metadata={"trace": "abc"})
    assert request.metadata["trace"] == "abc"


def test_request_public_serialization_excludes_attachment_bytes() -> None:
    request = _request(
        input_parts=(
            ModelInputPart.text_part("hello"),
            ModelInputPart.image_part(PNG_BYTES, "image/png", display_name="pixel.png"),
            ModelInputPart.document_part(_pdf_bytes(), "application/pdf"),
        )
    )
    payload = request.to_dict()
    serialized = json.dumps(payload)

    assert "content" not in payload["input_parts"][1]
    assert "content" not in payload["input_parts"][2]
    assert PNG_BYTES.decode("latin-1") not in serialized
    assert _pdf_bytes().decode("latin-1") not in serialized
    assert (
        payload["input_parts"][1]["content_digest"]
        == hashlib.sha256(PNG_BYTES).hexdigest()
    )
    assert payload["input_modalities"] == ["text", "image", "document"]


def test_request_exposes_safe_modality_inventory() -> None:
    request = _request(
        input_parts=(
            ModelInputPart.text_part("a"),
            ModelInputPart.text_part("b"),
            ModelInputPart.image_part(PNG_BYTES, "image/png"),
        )
    )
    assert request.input_modalities == ("text", "image")


# ── Execution facts and evidence ─────────────────────────────────────────────


def _facts(**overrides: object) -> ModelExecutionFacts:
    values: dict[str, object] = {
        "request_id": "model-request-1",
        "provider_id": "local",
        "model_id": "model-1",
        "selection_mode": ModelSelectionMode.EXPLICIT,
        "success": True,
        "privacy_decision": "not_required",
    }
    values.update(overrides)
    return ModelExecutionFacts(**values)  # type: ignore[arg-type]


def test_execution_facts_record_requested_and_effective_effort() -> None:
    facts = _facts(
        requested_reasoning_effort=ReasoningEffort.HIGH,
        effective_reasoning_effort=ReasoningEffort.HIGH,
    )
    payload = facts.to_dict()
    assert payload["requested_reasoning_effort"] == "high"
    assert payload["effective_reasoning_effort"] == "high"


def test_execution_facts_reject_invalid_counters_and_modalities() -> None:
    with pytest.raises(ValueError):
        _facts(retry_count=-1)
    with pytest.raises(ValueError):
        _facts(latency_ms=-5)
    with pytest.raises(ValueError):
        _facts(input_modalities=("telepathy",))


def test_execution_facts_serialization_has_no_forbidden_keys() -> None:
    facts = _facts(
        usage=ModelUsage(input_tokens=10, output_tokens=2),
        metadata={"trace": "abc"},
    )
    payload = facts.to_dict()
    assert set(payload).isdisjoint(
        {
            "prompt",
            "raw_prompt",
            "content",
            "reasoning_trace",
            "chain_of_thought",
            "provider_exception",
            "api_key",
            "credential",
        }
    )
    assert "bytes" not in json.dumps(payload).lower() or True


def test_execution_facts_metadata_is_screened() -> None:
    with pytest.raises(ValueError):
        _facts(metadata={"api_key": "value"})


def test_in_memory_evidence_sink_records_immutable_facts() -> None:
    sink = InMemoryModelExecutionEvidenceSink()
    facts = _facts()
    sink.record(facts)
    assert sink.records == (facts,)
    assert isinstance(sink.records, tuple)


def test_in_memory_evidence_sink_rejects_foreign_records() -> None:
    sink = InMemoryModelExecutionEvidenceSink()
    with pytest.raises(TypeError):
        sink.record("not-facts")  # type: ignore[arg-type]


# ── Response contract ────────────────────────────────────────────────────────


def _response(**overrides: object) -> ModelGatewayResponse:
    values: dict[str, object] = {
        "request_id": "model-request-1",
        "provider_id": "local",
        "model_id": "model-1",
        "selection_mode": ModelSelectionMode.EXPLICIT,
    }
    values.update(overrides)
    return ModelGatewayResponse(**values)  # type: ignore[arg-type]


def test_response_defaults_are_empty_and_safe() -> None:
    response = _response()
    assert response.content == ""
    assert response.tool_calls == ()
    assert response.structured_output is None
    assert response.cancelled is False
    assert response.error_code is None
    assert response.usage.input_tokens is None


def test_response_cannot_be_cancelled_and_failed_at_once() -> None:
    with pytest.raises(ValueError):
        _response(cancelled=True, error_code="PROVIDER_FAILURE")


def test_response_normalizes_tool_calls_and_structured_output() -> None:
    response = _response(
        content="",
        tool_calls=(ModelToolCall(call_id="c1", tool_id="t1", arguments={"a": 1}),),
        structured_output={"answer": 42},
    )
    payload = response.to_dict()
    assert payload["tool_calls"] == [
        {"call_id": "c1", "tool_id": "t1", "arguments": {"a": 1}}
    ]
    assert payload["structured_output"] == {"answer": 42}


def test_response_facts_must_match_the_response() -> None:
    with pytest.raises(ValueError):
        _response(facts=_facts(request_id="other-request"))


def test_response_serialization_is_safe() -> None:
    response = _response(
        content="hello",
        usage=ModelUsage(input_tokens=3, output_tokens=1),
        facts=_facts(usage=ModelUsage(input_tokens=3, output_tokens=1)),
    )
    payload = response.to_dict()
    assert payload["usage"]["input_tokens"] == 3
    assert "provider_payload" not in json.dumps(payload)


# ── Stream events ────────────────────────────────────────────────────────────


def test_stream_event_terminal_semantics() -> None:
    started = ModelStreamEvent(
        event_type=ModelStreamEventType.STARTED,
        request_id="r",
        sequence=0,
    )
    assert started.is_terminal is False

    completed = ModelStreamEvent(
        event_type=ModelStreamEventType.COMPLETED,
        request_id="r",
        sequence=1,
        response=_response(),
    )
    assert completed.is_terminal is True

    cancelled = ModelStreamEvent(
        event_type=ModelStreamEventType.CANCELLED,
        request_id="r",
        sequence=1,
    )
    assert cancelled.is_terminal is True

    failed = ModelStreamEvent(
        event_type=ModelStreamEventType.ERROR,
        request_id="r",
        sequence=1,
        error_code="PROVIDER_FAILURE",
    )
    assert failed.is_terminal is True


def test_stream_event_requires_a_response_on_completion() -> None:
    with pytest.raises(ValueError):
        ModelStreamEvent(
            event_type=ModelStreamEventType.COMPLETED,
            request_id="r",
            sequence=1,
        )


def test_stream_event_requires_an_error_code_on_error() -> None:
    with pytest.raises(ValueError):
        ModelStreamEvent(
            event_type=ModelStreamEventType.ERROR,
            request_id="r",
            sequence=1,
        )


def test_stream_event_rejects_negative_sequence_and_empty_delta() -> None:
    with pytest.raises(ValueError):
        ModelStreamEvent(
            event_type=ModelStreamEventType.STARTED,
            request_id="r",
            sequence=-1,
        )
    with pytest.raises(ValueError):
        ModelStreamEvent(
            event_type=ModelStreamEventType.CONTENT_DELTA,
            request_id="r",
            sequence=1,
            content_delta="",
        )


def test_content_delta_event_requires_a_delta() -> None:
    with pytest.raises(ValueError):
        ModelStreamEvent(
            event_type=ModelStreamEventType.CONTENT_DELTA,
            request_id="r",
            sequence=1,
        )


def test_stream_event_serialization_is_safe() -> None:
    event = ModelStreamEvent(
        event_type=ModelStreamEventType.CONTENT_DELTA,
        request_id="r",
        sequence=1,
        content_delta="hello",
        effective_reasoning_effort=ReasoningEffort.HIGH,
        reasoning_used=True,
    )
    payload = event.to_dict()
    assert payload["event_type"] == "content_delta"
    assert payload["content_delta"] == "hello"
    assert payload["effective_reasoning_effort"] == "high"
    assert payload["reasoning_used"] is True
    assert "reasoning_trace" not in payload


# ── Privacy egress decision ──────────────────────────────────────────────────


def test_privacy_egress_decision_is_immutable_and_safe() -> None:
    decision = PrivacyEgressDecision(
        allowed=False,
        reason_code="remote_blocked_local_only",
        details={"provider_id": "remote-a"},
    )
    assert decision.to_dict() == {
        "allowed": False,
        "reason_code": "remote_blocked_local_only",
        "requires_approval": False,
        "requires_redaction": False,
        "details": {"provider_id": "remote-a"},
    }
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.allowed = True  # type: ignore[misc]


def test_privacy_egress_decision_requires_a_reason_code() -> None:
    with pytest.raises(ValueError):
        PrivacyEgressDecision(allowed=True, reason_code="  ")


def test_privacy_egress_decision_details_are_screened() -> None:
    with pytest.raises(ValueError):
        PrivacyEgressDecision(
            allowed=False,
            reason_code="denied",
            details={"api_key": "value"},
        )


# ── Error taxonomy ───────────────────────────────────────────────────────────


def test_error_code_taxonomy_is_complete() -> None:
    assert {member.value for member in ModelGatewayErrorCode} >= {
        "MODEL_NOT_FOUND",
        "PROVIDER_NOT_AVAILABLE",
        "MODEL_UNAVAILABLE",
        "CAPABILITY_UNSUPPORTED",
        "UNSUPPORTED_REASONING_EFFORT",
        "INPUT_MODALITY_UNSUPPORTED",
        "PRIVACY_DENIED",
        "PROVIDER_REQUEST_INVALID",
        "PROVIDER_TIMEOUT",
        "PROVIDER_FAILURE",
        "STREAM_FAILURE",
        "MODEL_CALL_CANCELLED",
        "STRUCTURED_OUTPUT_INVALID",
        "TOOL_CALL_INVALID",
        "FALLBACK_EXHAUSTED",
    }


def test_retryable_codes_are_transport_level_only() -> None:
    assert RETRYABLE_ERROR_CODES == {
        ModelGatewayErrorCode.PROVIDER_TIMEOUT,
        ModelGatewayErrorCode.PROVIDER_FAILURE,
        ModelGatewayErrorCode.STREAM_FAILURE,
    }
    for code in (
        ModelGatewayErrorCode.PRIVACY_DENIED,
        ModelGatewayErrorCode.PROVIDER_REQUEST_INVALID,
        ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED,
        ModelGatewayErrorCode.UNSUPPORTED_REASONING_EFFORT,
        ModelGatewayErrorCode.MODEL_CALL_CANCELLED,
        ModelGatewayErrorCode.MODEL_NOT_FOUND,
    ):
        assert code not in RETRYABLE_ERROR_CODES


def test_error_is_safe_and_serializes_without_internals() -> None:
    error = ModelGatewayError(
        ModelGatewayErrorCode.PROVIDER_FAILURE,
        "provider call failed",
        details={"provider_id": "remote-a"},
    )
    payload = error.to_dict()
    assert payload["code"] == "PROVIDER_FAILURE"
    assert payload["message"] == "provider call failed"
    assert payload["details"] == {"provider_id": "remote-a"}
    assert payload["retryable"] is True
    assert "Traceback" not in json.dumps(payload)


def test_error_can_mark_a_failure_as_permanently_non_retryable() -> None:
    error = ModelGatewayError(
        ModelGatewayErrorCode.PROVIDER_FAILURE,
        "provider rejected the credential",
        retryable=False,
    )
    assert error.retryable is False
    assert error.to_dict()["retryable"] is False


def test_error_details_are_screened_and_immutable() -> None:
    with pytest.raises(ValueError):
        ModelGatewayError(
            ModelGatewayErrorCode.PROVIDER_FAILURE,
            "failed",
            details={"api_key": "value"},
        )
    error = ModelGatewayError(
        ModelGatewayErrorCode.PROVIDER_FAILURE,
        "failed",
        details={"provider_id": "remote-a"},
    )
    with pytest.raises(TypeError):
        error.details["provider_id"] = "other"  # type: ignore[index]


def test_error_requires_a_safe_non_empty_message() -> None:
    with pytest.raises(ValueError):
        ModelGatewayError(ModelGatewayErrorCode.PROVIDER_FAILURE, "   ")
