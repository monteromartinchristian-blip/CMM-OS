"""Phase 11.21 — provider adapter boundary tests.

The gateway core must stay provider-name agnostic.  These tests fix the narrow
adapter protocol, the execution-only adapter registry (it resolves execution and
stores no provider metadata), the official in-memory adapter used by connected
acceptance, and the wrapper that adapts the pre-existing canonical
``LLMProvider`` implementations instead of forking them.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from kernel.llm.capabilities import ReasoningEffort
from kernel.llm.mock_provider import MockProvider
from kernel.llm.model_gateway_contracts import (
    ModelInputPart,
    ModelStreamEventType,
    ModelToolCall,
    ModelToolDefinition,
    ModelUsage,
    StructuredOutputRequirement,
)
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode
from kernel.llm.model_provider_adapter import (
    InMemoryModelProviderAdapter,
    LLMProviderModelAdapter,
    ModelProviderAdapter,
    ModelProviderAdapterRegistry,
    ProviderModelRequest,
    ProviderModelResponse,
)
from kernel.llm.model_streaming import ModelCallCancellation
from tests.llm.model_gateway_support import PDF_BYTES, PNG_BYTES

TEXT_ONLY = (ModelInputPart.text_part("hola"),)


def _request(
    *,
    model_id: str = "model-1",
    provider_id: str = "local",
    parts: tuple[ModelInputPart, ...] = TEXT_ONLY,
    reasoning_effort: ReasoningEffort = ReasoningEffort.DEFAULT,
    tools: tuple[ModelToolDefinition, ...] = (),
    structured_output: StructuredOutputRequirement | None = None,
) -> ProviderModelRequest:
    return ProviderModelRequest(
        request_id="model-request-1",
        provider_id=provider_id,
        model_id=model_id,
        input_parts=parts,
        reasoning_effort=reasoning_effort,
        tools=tools,
        structured_output=structured_output,
    )


# ── Execution-only adapter registry ──────────────────────────────────────────


def test_registry_resolves_adapter_by_canonical_provider_identity() -> None:
    adapter = InMemoryModelProviderAdapter("local")
    registry = ModelProviderAdapterRegistry((adapter,))

    assert registry.get("LOCAL") is adapter
    assert registry.has("local") is True
    assert registry.has("missing") is False
    assert registry.provider_ids() == ("local",)
    assert len(registry) == 1


def test_registry_rejects_duplicate_provider_identity() -> None:
    registry = ModelProviderAdapterRegistry((InMemoryModelProviderAdapter("local"),))

    with pytest.raises(ValueError):
        registry.register(InMemoryModelProviderAdapter("LOCAL"))


def test_registry_rejects_a_non_adapter() -> None:
    registry = ModelProviderAdapterRegistry()

    with pytest.raises(TypeError):
        registry.register(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        ModelProviderAdapterRegistry((object(),))  # type: ignore[arg-type]


def test_registry_missing_adapter_fails_closed_safely() -> None:
    registry = ModelProviderAdapterRegistry()

    with pytest.raises(ModelGatewayError) as error:
        registry.get("local")

    assert error.value.code is ModelGatewayErrorCode.PROVIDER_NOT_AVAILABLE
    assert error.value.retryable is False


def test_registry_exposes_provider_ids_sorted() -> None:
    registry = ModelProviderAdapterRegistry(
        (
            InMemoryModelProviderAdapter("zeta"),
            InMemoryModelProviderAdapter("alpha"),
        )
    )

    assert registry.provider_ids() == ("alpha", "zeta")


def test_registry_stores_no_provider_metadata() -> None:
    registry = ModelProviderAdapterRegistry((InMemoryModelProviderAdapter("local"),))

    assert not hasattr(registry, "register_spec")
    assert not hasattr(registry, "provider_specs")
    assert not hasattr(registry, "manifest")


# ── Official in-memory adapter ───────────────────────────────────────────────


def test_in_memory_adapter_satisfies_the_canonical_protocol() -> None:
    adapter = InMemoryModelProviderAdapter("local")

    assert adapter.provider_id == "local"
    assert isinstance(adapter, ModelProviderAdapter)


def test_in_memory_adapter_records_the_actual_received_payloads() -> None:
    adapter = InMemoryModelProviderAdapter("local")
    adapter.add_response(content="ok")
    request = _request(
        parts=(
            ModelInputPart.text_part("hola"),
            ModelInputPart.image_part(PNG_BYTES, "image/png"),
            ModelInputPart.document_part(PDF_BYTES, "application/pdf"),
        )
    )

    adapter.execute(request)

    assert adapter.call_count == 1
    fingerprints = adapter.received_input_fingerprints[0]
    assert [kind for kind, _, _ in fingerprints] == ["text", "image", "document"]
    assert fingerprints[1][1] == len(PNG_BYTES)
    assert fingerprints[2][2] == request.input_parts[2].content_digest
    assert fingerprints[1][2] == request.input_parts[1].content_digest


def test_in_memory_adapter_derives_its_result_from_the_received_bytes() -> None:
    adapter = InMemoryModelProviderAdapter("local", derive_content_from_input=True)
    adapter.add_response(content="ignored")
    first = _request(parts=(ModelInputPart.image_part(PNG_BYTES, "image/png"),))
    adapter.add_response(content="ignored")
    second = _request(
        parts=(ModelInputPart.image_part(PNG_BYTES + b"\x00", "image/png"),)
    )

    first_response = adapter.execute(first)
    second_response = adapter.execute(second)

    assert first_response.content.startswith("echo:")
    assert first_response.content != second_response.content
    summary = first_response.metadata["input_content_digest"]
    assert isinstance(summary, str) and len(summary) == 64


def test_in_memory_adapter_translates_reasoning_effort_provider_locally() -> None:
    adapter = InMemoryModelProviderAdapter(
        "local",
        reasoning_effort_map={
            ReasoningEffort.LOW: "thinking_budget_low",
            ReasoningEffort.HIGH: "thinking_budget_high",
        },
    )
    adapter.add_response(content="deep")

    response = adapter.execute(_request(reasoning_effort=ReasoningEffort.HIGH))

    assert adapter.native_efforts == ("thinking_budget_high",)
    assert response.effective_reasoning_effort is ReasoningEffort.HIGH
    assert response.reasoning_used is True
    serialized = str(response.to_dict())
    assert "thinking_budget_high" not in serialized


def test_in_memory_adapter_default_effort_sends_no_override() -> None:
    adapter = InMemoryModelProviderAdapter(
        "local",
        reasoning_effort_map={ReasoningEffort.HIGH: "thinking_budget_high"},
    )
    adapter.add_response(content="plain")

    response = adapter.execute(_request())

    assert adapter.native_efforts == (None,)
    assert response.effective_reasoning_effort is ReasoningEffort.DEFAULT
    assert response.reasoning_used is False


def test_in_memory_adapter_fails_closed_on_an_untranslatable_effort() -> None:
    adapter = InMemoryModelProviderAdapter(
        "local",
        reasoning_effort_map={ReasoningEffort.LOW: "thinking_budget_low"},
    )
    adapter.add_response(content="deep")

    with pytest.raises(ModelGatewayError) as error:
        adapter.execute(_request(reasoning_effort=ReasoningEffort.EXTRA_HIGH))

    assert error.value.code is ModelGatewayErrorCode.UNSUPPORTED_REASONING_EFFORT
    assert adapter.call_count == 1


def test_in_memory_adapter_returns_structured_output_and_usage() -> None:
    adapter = InMemoryModelProviderAdapter("local")
    adapter.add_response(
        structured_output={"answer": 42},
        usage=ModelUsage(
            input_tokens=12,
            output_tokens=3,
            cached_tokens=4,
            cost=Decimal("0.0001"),
            cost_source="provider_reported",
        ),
        finish_reason="stop",
    )

    response = adapter.execute(
        _request(
            structured_output=StructuredOutputRequirement(schema={"type": "object"})
        )
    )

    assert response.structured_output == {"answer": 42}
    assert response.usage.input_tokens == 12
    assert response.usage.cached_tokens == 4
    assert response.usage.cost_source == "provider_reported"
    assert response.finish_reason == "stop"


def test_in_memory_adapter_returns_normalized_tool_calls() -> None:
    adapter = InMemoryModelProviderAdapter("local")
    adapter.add_response(
        tool_calls=(
            ModelToolCall(
                call_id="call-1",
                tool_id="cmm.ops.list_files",
                arguments={"path": "."},
            ),
        )
    )

    response = adapter.execute(
        _request(tools=(ModelToolDefinition(tool_id="cmm.ops.list_files"),))
    )

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool_id == "cmm.ops.list_files"


def test_in_memory_adapter_normalizes_failures_without_leaking_internals() -> None:
    adapter = InMemoryModelProviderAdapter("local")
    adapter.add_failure(
        ModelGatewayErrorCode.PROVIDER_FAILURE,
        "remote provider returned 503",
        retryable=True,
    )

    with pytest.raises(ModelGatewayError) as error:
        adapter.execute(_request())

    assert error.value.code is ModelGatewayErrorCode.PROVIDER_FAILURE
    assert error.value.retryable is True
    assert "Traceback" not in str(error.value)
    assert set(error.value.details) == {"provider_id"}
    assert set(error.value.details).isdisjoint(
        {"api_key", "credential", "prompt", "payload", "exception"}
    )


def test_in_memory_adapter_can_script_a_timeout() -> None:
    adapter = InMemoryModelProviderAdapter("local")
    adapter.add_timeout(delay_seconds=0.02)

    with pytest.raises(ModelGatewayError) as error:
        adapter.execute(_request())

    assert error.value.code is ModelGatewayErrorCode.PROVIDER_TIMEOUT
    assert error.value.retryable is True


def test_in_memory_adapter_shares_one_ordered_scenario_queue() -> None:
    adapter = InMemoryModelProviderAdapter("local")
    adapter.add_response(content="first")
    adapter.add_failure(
        ModelGatewayErrorCode.PROVIDER_FAILURE, "second", retryable=False
    )

    assert adapter.execute(_request()).content == "first"
    with pytest.raises(ModelGatewayError):
        adapter.execute(_request())
    with pytest.raises(ModelGatewayError) as error:
        adapter.execute(_request())

    assert error.value.code is ModelGatewayErrorCode.PROVIDER_FAILURE
    assert error.value.retryable is False


def test_in_memory_adapter_observes_cancellation_before_execution() -> None:
    adapter = InMemoryModelProviderAdapter("local")
    adapter.add_response(content="never")
    cancellation = ModelCallCancellation()
    cancellation.cancel("caller cancelled")

    with pytest.raises(ModelGatewayError) as error:
        adapter.execute(_request(), cancellation=cancellation)

    assert error.value.code is ModelGatewayErrorCode.MODEL_CALL_CANCELLED
    assert adapter.call_count == 0


# ── Official in-memory streaming ─────────────────────────────────────────────


def test_in_memory_adapter_streams_ordered_provider_events() -> None:
    adapter = InMemoryModelProviderAdapter("local")
    adapter.add_stream(("ho", "la"), usage=ModelUsage(input_tokens=4, output_tokens=2))

    events = list(adapter.stream(_request()))

    assert [event.event_type for event in events] == [
        ModelStreamEventType.STARTED,
        ModelStreamEventType.CONTENT_DELTA,
        ModelStreamEventType.CONTENT_DELTA,
        ModelStreamEventType.USAGE,
        ModelStreamEventType.COMPLETED,
    ]
    assert [event.content_delta for event in events[1:3]] == ["ho", "la"]
    assert events[-1].response is not None
    assert events[-1].response.content == "hola"


def test_in_memory_adapter_stream_emits_tool_call_deltas() -> None:
    adapter = InMemoryModelProviderAdapter("local")
    adapter.add_stream(
        (),
        tool_calls=(ModelToolCall(call_id="call-1", tool_id="t1", arguments={"a": 1}),),
    )

    events = list(adapter.stream(_request()))

    assert ModelStreamEventType.TOOL_CALL_DELTA in [
        event.event_type for event in events
    ]


def test_in_memory_adapter_stream_observes_cancellation_and_stops() -> None:
    adapter = InMemoryModelProviderAdapter("local")
    adapter.add_stream(("a", "b", "c", "d"))
    cancellation = ModelCallCancellation()

    received: list[ModelStreamEventType] = []
    for event in adapter.stream(_request(), cancellation=cancellation):
        received.append(event.event_type)
        if event.event_type is ModelStreamEventType.CONTENT_DELTA:
            cancellation.cancel("stop here")

    assert ModelStreamEventType.CANCELLED in received
    assert received[-1] is ModelStreamEventType.CANCELLED
    assert received.count(ModelStreamEventType.CONTENT_DELTA) == 1


def test_in_memory_adapter_stream_normalizes_a_scripted_failure() -> None:
    adapter = InMemoryModelProviderAdapter("local")
    adapter.add_stream(
        ("partial",),
        fail_with=ModelGatewayErrorCode.STREAM_FAILURE,
    )

    events = list(adapter.stream(_request()))

    assert events[-1].event_type is ModelStreamEventType.ERROR
    assert events[-1].error_code == "STREAM_FAILURE"


def test_in_memory_adapter_refuses_streaming_when_not_supported() -> None:
    adapter = InMemoryModelProviderAdapter("local", supports_streaming=False)
    adapter.add_stream(("a",))

    with pytest.raises(ModelGatewayError) as error:
        list(adapter.stream(_request()))

    assert error.value.code is ModelGatewayErrorCode.STREAM_FAILURE
    assert error.value.retryable is False


def test_in_memory_adapter_stream_records_the_received_request() -> None:
    adapter = InMemoryModelProviderAdapter("local")
    adapter.add_stream(("a",))
    request = _request(parts=(ModelInputPart.image_part(PNG_BYTES, "image/png"),))

    list(adapter.stream(request))

    assert adapter.call_count == 1
    assert adapter.requests[0] is request
    assert (
        adapter.received_input_fingerprints[0][0][2]
        == request.input_parts[0].content_digest
    )


# ── Wrapper over the existing canonical provider implementations ─────────────


class _RecordingProvider(MockProvider):
    """Minimal canonical provider that records the request it received."""

    def __init__(self, response: str) -> None:
        super().__init__(response)
        self.requests: list[object] = []

    def generate(self, request):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        return super().generate(request)


def test_legacy_provider_wrapper_adapts_a_canonical_provider() -> None:
    provider = _RecordingProvider("legacy answer")
    adapter = LLMProviderModelAdapter(
        provider, provider_id="legacy", model_id="legacy-1"
    )
    adapter_response = adapter.execute(
        _request(model_id="legacy-1", provider_id="legacy")
    )

    assert isinstance(adapter_response, ProviderModelResponse)
    assert adapter_response.content == "legacy answer"
    assert provider.requests[0].prompt == "hola"


def test_legacy_provider_wrapper_concatenates_text_parts_only() -> None:
    provider = _RecordingProvider("ok")
    adapter = LLMProviderModelAdapter(
        provider, provider_id="legacy", model_id="legacy-1"
    )

    adapter.execute(
        _request(
            model_id="legacy-1",
            provider_id="legacy",
            parts=(
                ModelInputPart.text_part("first"),
                ModelInputPart.text_part("second"),
            ),
        )
    )

    assert provider.requests[0].prompt == "first\nsecond"


@pytest.mark.parametrize(
    "part",
    [
        ModelInputPart.image_part(PNG_BYTES, "image/png"),
        ModelInputPart.document_part(PDF_BYTES, "application/pdf"),
    ],
)
def test_legacy_provider_wrapper_refuses_multimodal_input(
    part: ModelInputPart,
) -> None:
    provider = _RecordingProvider("ok")
    adapter = LLMProviderModelAdapter(
        provider, provider_id="legacy", model_id="legacy-1"
    )

    with pytest.raises(ModelGatewayError) as error:
        adapter.execute(
            _request(model_id="legacy-1", provider_id="legacy", parts=(part,))
        )

    assert error.value.code is ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED
    assert provider.requests == []


def test_legacy_provider_wrapper_refuses_explicit_reasoning_effort() -> None:
    provider = _RecordingProvider("ok")
    adapter = LLMProviderModelAdapter(
        provider, provider_id="legacy", model_id="legacy-1"
    )

    with pytest.raises(ModelGatewayError) as error:
        adapter.execute(
            _request(
                model_id="legacy-1",
                provider_id="legacy",
                reasoning_effort=ReasoningEffort.HIGH,
            )
        )

    assert error.value.code is ModelGatewayErrorCode.UNSUPPORTED_REASONING_EFFORT
    assert provider.requests == []


def test_legacy_provider_wrapper_rejects_streaming_explicitly() -> None:
    adapter = LLMProviderModelAdapter(
        _RecordingProvider("ok"), provider_id="legacy", model_id="legacy-1"
    )

    with pytest.raises(ModelGatewayError) as error:
        list(adapter.stream(_request(model_id="legacy-1", provider_id="legacy")))

    assert error.value.code is ModelGatewayErrorCode.STREAM_FAILURE


def test_legacy_provider_wrapper_does_not_fabricate_token_counts() -> None:
    adapter = LLMProviderModelAdapter(
        _RecordingProvider("ok"), provider_id="legacy", model_id="legacy-1"
    )

    response = adapter.execute(_request(model_id="legacy-1", provider_id="legacy"))

    assert response.usage.input_tokens is None
    assert response.usage.output_tokens is None


def test_legacy_provider_wrapper_reports_real_token_counts() -> None:
    class _CountingProvider(MockProvider):
        def generate(self, request):  # type: ignore[no-untyped-def]
            from kernel.llm.models import LLMResponse

            return LLMResponse(
                content="counted",
                model="legacy-1",
                usage_prompt_tokens=11,
                usage_completion_tokens=5,
            )

    adapter = LLMProviderModelAdapter(
        _CountingProvider("unused"), provider_id="legacy", model_id="legacy-1"
    )

    response = adapter.execute(_request(model_id="legacy-1", provider_id="legacy"))

    assert response.usage.input_tokens == 11
    assert response.usage.output_tokens == 5


def test_provider_contracts_are_immutable() -> None:
    request = _request()
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.model_id = "other"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        ProviderModelResponse(content="x").content = "y"  # type: ignore[misc]
