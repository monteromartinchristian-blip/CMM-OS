"""Phase 11.21 — canonical provider-token streaming tests.

The gateway owns the provider-token stream: exactly one ``STARTED``, contiguous
deterministic sequence numbers, usage allowed before completion, exactly one
terminal event and no event after it.  Raw provider objects and hidden reasoning
never appear, and an adapter that misbehaves is normalized rather than trusted.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator

import pytest

from kernel.llm.capabilities import ModelCapabilities, ReasoningEffort
from kernel.llm.model_gateway_contracts import (
    ModelGatewayRequest,
    ModelInputPart,
    ModelStreamEventType,
    ModelToolCall,
    ModelToolDefinition,
    ModelUsage,
)
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode
from kernel.llm.model_provider_adapter import (
    InMemoryModelProviderAdapter,
    ProviderModelRequest,
    ProviderStreamEvent,
)
from kernel.llm.model_streaming import ModelCallCancellation
from tests.llm.model_gateway_support import MULTIMODAL, build_runtime

STREAMING = ModelCapabilities(streaming=True)


def _request(**overrides: object) -> ModelGatewayRequest:
    values: dict[str, object] = {
        "request_id": "model-request-1",
        "model_id": "local:model-1",
        "input_parts": (ModelInputPart.text_part("stream please"),),
    }
    values.update(overrides)
    return ModelGatewayRequest(**values)  # type: ignore[arg-type]


def _runtime(
    capabilities: ModelCapabilities = STREAMING, adapter=None, **overrides: object
):
    adapters = (adapter,) if adapter is not None else ()
    return build_runtime(
        capabilities=capabilities,
        adapters=adapters,
        **overrides,  # type: ignore[arg-type]
    )


def test_canonical_stream_is_ordered_and_terminates_once() -> None:
    runtime = _runtime()
    runtime.adapter().add_stream(
        ("ho", "la"), usage=ModelUsage(input_tokens=4, output_tokens=2)
    )

    events = list(runtime.gateway.stream(_request()))

    assert [event.event_type for event in events] == [
        ModelStreamEventType.STARTED,
        ModelStreamEventType.CONTENT_DELTA,
        ModelStreamEventType.CONTENT_DELTA,
        ModelStreamEventType.USAGE,
        ModelStreamEventType.COMPLETED,
    ]
    assert [event.sequence for event in events] == [0, 1, 2, 3, 4]
    assert [event.content_delta for event in events[1:3]] == ["ho", "la"]
    assert sum(event.is_terminal for event in events) == 1
    assert events[-1].is_terminal is True


def test_completed_event_carries_the_normalized_response_and_evidence() -> None:
    runtime = _runtime()
    runtime.adapter().add_stream(
        ("ho", "la"), usage=ModelUsage(input_tokens=4, output_tokens=2)
    )

    events = list(runtime.gateway.stream(_request()))

    completed = events[-1]
    assert completed.response is not None
    assert completed.response.content == "hola"
    assert completed.response.finish_reason == "stop"
    assert completed.response.usage.input_tokens == 4
    assert completed.response.facts is not None
    assert completed.response.facts.streamed is True
    assert completed.response.facts.success is True
    assert len(runtime.sink.records) == 1
    assert runtime.sink.records[0].streamed is True


def test_stream_requires_declared_streaming_capability_before_provider_io() -> None:
    runtime = _runtime(ModelCapabilities(structured_output=True))
    runtime.adapter().add_stream(("never",))

    with pytest.raises(ModelGatewayError) as error:
        list(runtime.gateway.stream(_request()))

    assert error.value.code is ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED
    assert error.value.retryable is False
    assert runtime.adapter().call_count == 0


def test_a_streaming_request_cannot_be_executed_through_execute() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(stream=True))

    assert error.value.code is ModelGatewayErrorCode.PROVIDER_REQUEST_INVALID
    assert runtime.adapter().call_count == 0


def test_usage_may_arrive_before_completion() -> None:
    runtime = _runtime()
    runtime.adapter().add_stream(
        ("a",), usage=ModelUsage(input_tokens=1, output_tokens=1)
    )

    events = list(runtime.gateway.stream(_request()))

    usage_index = [event.event_type for event in events].index(
        ModelStreamEventType.USAGE
    )
    assert usage_index < len(events) - 1
    assert events[usage_index].usage is not None
    assert events[usage_index].usage.input_tokens == 1


def test_tool_call_deltas_are_normalized() -> None:
    runtime = _runtime(MULTIMODAL)
    runtime.adapter().add_stream(
        (),
        tool_calls=(ModelToolCall(call_id="call-1", tool_id="t1", arguments={"a": 1}),),
    )

    events = list(
        runtime.gateway.stream(_request(tools=(ModelToolDefinition(tool_id="t1"),)))
    )

    assert events[1].event_type is ModelStreamEventType.TOOL_CALL_DELTA
    assert events[1].tool_call is not None
    assert events[1].tool_call.call_id == "call-1"
    assert events[-1].event_type is ModelStreamEventType.COMPLETED


def test_hidden_reasoning_never_appears_in_the_stream() -> None:
    runtime = _runtime(ModelCapabilities(streaming=True, reasoning=True))
    runtime.adapter().add_stream(("visible",))

    events = list(runtime.gateway.stream(_request()))

    for event in events:
        payload = event.to_dict()
        for forbidden in (
            "reasoning_trace",
            "chain_of_thought",
            "scratchpad",
            "hidden_reasoning",
        ):
            assert forbidden not in payload
    started = events[0]
    assert started.effective_reasoning_effort is ReasoningEffort.DEFAULT
    assert started.reasoning_used is False


def test_stream_serialization_is_safe() -> None:
    runtime = _runtime()
    runtime.adapter().add_stream(("visible",))

    events = list(runtime.gateway.stream(_request()))

    serialized = json.dumps([event.to_dict() for event in events])
    assert "visible" in serialized
    assert "provider_payload" not in serialized
    assert set(events[0].to_dict()) == {
        "event_type",
        "request_id",
        "sequence",
        "content_delta",
        "tool_call",
        "usage",
        "response",
        "error_code",
        "provider_id",
        "model_id",
        "effective_reasoning_effort",
        "reasoning_used",
        "is_terminal",
    }


def test_adapter_stream_failure_is_normalized() -> None:
    runtime = _runtime()
    runtime.adapter().add_stream(
        ("partial",), fail_with=ModelGatewayErrorCode.STREAM_FAILURE
    )

    events = list(runtime.gateway.stream(_request()))

    assert events[-1].event_type is ModelStreamEventType.ERROR
    assert events[-1].error_code == "STREAM_FAILURE"
    assert sum(event.is_terminal for event in events) == 1
    assert runtime.sink.records[-1].error_code == "STREAM_FAILURE"


class _ScriptedAdapter(InMemoryModelProviderAdapter):
    """Test adapter that yields an arbitrary canonical event script."""

    def __init__(
        self, provider_id: str, script: tuple[ProviderStreamEvent, ...]
    ) -> None:
        super().__init__(provider_id)
        self._script = script

    def stream(
        self,
        request: ProviderModelRequest,
        *,
        cancellation: object | None = None,
    ) -> Iterator[ProviderStreamEvent]:
        self._record(request)
        yield from self._script


def test_no_event_is_emitted_after_a_terminal_event() -> None:
    adapter = _ScriptedAdapter(
        "local",
        (
            ProviderStreamEvent(event_type=ModelStreamEventType.STARTED),
            ProviderStreamEvent(
                event_type=ModelStreamEventType.CONTENT_DELTA, content_delta="first"
            ),
            ProviderStreamEvent(
                event_type=ModelStreamEventType.COMPLETED,
                response=_provider_response("first"),
            ),
            ProviderStreamEvent(
                event_type=ModelStreamEventType.CONTENT_DELTA, content_delta="late"
            ),
        ),
    )
    runtime = _runtime(adapter=adapter)

    events = list(runtime.gateway.stream(_request()))

    assert [event.content_delta for event in events] == [None, "first", None]
    assert events[-1].event_type is ModelStreamEventType.COMPLETED
    assert all(event.content_delta != "late" for event in events)


def test_duplicate_terminal_events_are_normalized() -> None:
    adapter = _ScriptedAdapter(
        "local",
        (
            ProviderStreamEvent(
                event_type=ModelStreamEventType.COMPLETED,
                response=_provider_response("done"),
            ),
            ProviderStreamEvent(
                event_type=ModelStreamEventType.COMPLETED,
                response=_provider_response("again"),
            ),
            ProviderStreamEvent(event_type=ModelStreamEventType.CANCELLED),
        ),
    )
    runtime = _runtime(adapter=adapter)

    events = list(runtime.gateway.stream(_request()))

    assert sum(event.is_terminal for event in events) == 1
    assert events[-1].event_type is ModelStreamEventType.COMPLETED


def test_a_stream_without_a_terminal_fails_safely() -> None:
    adapter = _ScriptedAdapter(
        "local",
        (
            ProviderStreamEvent(event_type=ModelStreamEventType.STARTED),
            ProviderStreamEvent(
                event_type=ModelStreamEventType.CONTENT_DELTA, content_delta="only"
            ),
        ),
    )
    runtime = _runtime(adapter=adapter)

    events = list(runtime.gateway.stream(_request()))

    assert events[-1].event_type is ModelStreamEventType.ERROR
    assert events[-1].error_code == "STREAM_FAILURE"
    assert sum(event.is_terminal for event in events) == 1


def test_an_adapter_started_event_is_never_duplicated() -> None:
    adapter = _ScriptedAdapter(
        "local",
        (
            ProviderStreamEvent(event_type=ModelStreamEventType.STARTED),
            ProviderStreamEvent(event_type=ModelStreamEventType.STARTED),
            ProviderStreamEvent(
                event_type=ModelStreamEventType.COMPLETED,
                response=_provider_response(""),
            ),
        ),
    )
    runtime = _runtime(adapter=adapter)

    events = list(runtime.gateway.stream(_request()))

    assert [event.event_type for event in events].count(
        ModelStreamEventType.STARTED
    ) == 1


class _ExplodingAdapter(InMemoryModelProviderAdapter):
    """Test adapter whose stream raises a raw provider exception."""

    def stream(
        self,
        request: ProviderModelRequest,
        *,
        cancellation: object | None = None,
    ) -> Iterator[ProviderStreamEvent]:
        self._record(request)
        raise RuntimeError("raw provider internals: api_key=sk-secret")


def test_a_raw_provider_exception_is_normalized_without_leaking_details() -> None:
    runtime = _runtime(adapter=_ExplodingAdapter("local"))

    events = list(runtime.gateway.stream(_request()))

    assert events[-1].event_type is ModelStreamEventType.ERROR
    assert events[-1].error_code == "PROVIDER_FAILURE"
    serialized = json.dumps([event.to_dict() for event in events])
    assert "sk-secret" not in serialized
    assert "RuntimeError" not in serialized


def test_streaming_facts_record_effective_reasoning_effort() -> None:
    adapter = InMemoryModelProviderAdapter(
        "local", reasoning_effort_map={ReasoningEffort.HIGH: "thinking_budget_high"}
    )
    runtime = _runtime(
        ModelCapabilities(
            streaming=True,
            reasoning=True,
            reasoning_efforts=(ReasoningEffort.HIGH,),
        ),
        adapter=adapter,
    )
    runtime.adapter().add_stream(("deep",))

    events = list(
        runtime.gateway.stream(_request(reasoning_effort=ReasoningEffort.HIGH))
    )

    facts = runtime.sink.records[-1]
    assert facts.requested_reasoning_effort is ReasoningEffort.HIGH
    assert facts.effective_reasoning_effort is ReasoningEffort.HIGH
    assert events[-1].response is not None
    assert events[-1].response.effective_reasoning_effort is ReasoningEffort.HIGH


def _provider_response(content: str):
    from kernel.llm.model_provider_adapter import ProviderModelResponse

    return ProviderModelResponse(content=content)


# ── Remediation V1 MAJOR-03 — the public stream deadline is authoritative.
#
# The gateway must never call a potentially blocking provider ``next()`` directly
# on the public consumer path.  After the deadline no CONTENT_DELTA,
# TOOL_CALL_DELTA, USAGE or COMPLETED may be emitted, exactly one
# PROVIDER_TIMEOUT terminal is produced, and a permanently blocked provider
# iterator cannot make the public stream or the test process wait without bound.


class _LateContentAdapter(InMemoryModelProviderAdapter):
    """Yield STARTED, block past the deadline, then yield late content."""

    def __init__(self, provider_id: str, *, sleep_seconds: float) -> None:
        super().__init__(provider_id)
        self._sleep_seconds = sleep_seconds

    def stream(
        self,
        request: ProviderModelRequest,
        *,
        cancellation: object | None = None,
    ) -> Iterator[ProviderStreamEvent]:
        self._record(request)
        yield ProviderStreamEvent(event_type=ModelStreamEventType.STARTED)
        time.sleep(self._sleep_seconds)
        yield ProviderStreamEvent(
            event_type=ModelStreamEventType.CONTENT_DELTA,
            content_delta="LATE",
        )
        yield ProviderStreamEvent(
            event_type=ModelStreamEventType.TOOL_CALL_DELTA,
            tool_call=ModelToolCall(call_id="late-call", tool_id="t1"),
        )
        yield ProviderStreamEvent(
            event_type=ModelStreamEventType.USAGE,
            usage=ModelUsage(input_tokens=99, output_tokens=99),
        )
        yield ProviderStreamEvent(
            event_type=ModelStreamEventType.COMPLETED,
            response=_provider_response("LATE"),
        )


class _BlockingAdapter(InMemoryModelProviderAdapter):
    """Block ``next()`` on a real event until the test releases it."""

    def __init__(
        self,
        provider_id: str,
        *,
        gate: threading.Event,
        follow_with: tuple[ProviderStreamEvent, ...] = (),
    ) -> None:
        super().__init__(provider_id)
        self._gate = gate
        self._follow_with = follow_with

    def stream(
        self,
        request: ProviderModelRequest,
        *,
        cancellation: object | None = None,
    ) -> Iterator[ProviderStreamEvent]:
        self._record(request)
        yield ProviderStreamEvent(event_type=ModelStreamEventType.STARTED)
        # A bounded wait keeps the test process safe even if the pump is leaked;
        # the gateway must already have returned by then.
        self._gate.wait(timeout=5.0)
        yield from self._follow_with


def _streaming_adapter_runtime(adapter: InMemoryModelProviderAdapter):
    return build_runtime(
        capabilities=ModelCapabilities(streaming=True),
        adapters=(adapter,),
    )


def test_the_public_stream_drops_content_arriving_after_the_deadline() -> None:
    adapter = _LateContentAdapter("local", sleep_seconds=0.05)
    runtime = _streaming_adapter_runtime(adapter)

    started = time.monotonic()
    events = list(runtime.gateway.stream(_request(timeout_seconds=0.02)))
    elapsed = time.monotonic() - started

    assert [event.event_type for event in events] == [
        ModelStreamEventType.STARTED,
        ModelStreamEventType.ERROR,
    ]
    assert events[-1].error_code == "PROVIDER_TIMEOUT"
    assert sum(event.is_terminal for event in events) == 1
    assert all(event.content_delta != "LATE" for event in events)
    assert all(event.tool_call is None for event in events)
    assert all(event.usage is None for event in events)
    assert all(event.response is None for event in events)
    # The public wait is bounded by the deadline, not by the provider's 50 ms.
    assert elapsed < 0.04


def test_a_permanently_blocked_provider_iterator_is_publicly_bounded() -> None:
    gate = threading.Event()
    adapter = _BlockingAdapter("local", gate=gate)
    runtime = _streaming_adapter_runtime(adapter)

    try:
        started = time.monotonic()
        events = list(runtime.gateway.stream(_request(timeout_seconds=0.02)))
        elapsed = time.monotonic() - started

        assert [event.event_type for event in events] == [
            ModelStreamEventType.STARTED,
            ModelStreamEventType.ERROR,
        ]
        assert events[-1].error_code == "PROVIDER_TIMEOUT"
        assert elapsed < 0.5
    finally:
        gate.set()


def test_a_provider_exception_inside_the_deadline_is_normalized() -> None:
    class _ExplodingPumpAdapter(InMemoryModelProviderAdapter):
        def stream(
            self,
            request: ProviderModelRequest,
            *,
            cancellation: object | None = None,
        ) -> Iterator[ProviderStreamEvent]:
            self._record(request)
            yield ProviderStreamEvent(event_type=ModelStreamEventType.STARTED)
            raise RuntimeError("raw provider internals: api_key=sk-secret")

    runtime = _streaming_adapter_runtime(_ExplodingPumpAdapter("local"))

    events = list(runtime.gateway.stream(_request(timeout_seconds=5.0)))

    assert events[-1].event_type is ModelStreamEventType.ERROR
    assert events[-1].error_code == "PROVIDER_FAILURE"
    serialized = json.dumps([event.to_dict() for event in events])
    assert "sk-secret" not in serialized
    assert "RuntimeError" not in serialized


def test_user_cancellation_while_the_provider_blocks_terminates_as_cancelled() -> None:
    gate = threading.Event()
    adapter = _BlockingAdapter("local", gate=gate)
    runtime = _streaming_adapter_runtime(adapter)
    cancellation = ModelCallCancellation()

    received: list[ModelStreamEventType] = []
    codes: list[str | None] = []
    try:
        for event in runtime.gateway.stream(
            _request(timeout_seconds=5.0), cancellation=cancellation
        ):
            received.append(event.event_type)
            codes.append(event.error_code)
            if event.event_type is ModelStreamEventType.STARTED:
                cancellation.cancel("user pressed stop")
    finally:
        gate.set()

    assert received[0] is ModelStreamEventType.STARTED
    assert received[-1] is ModelStreamEventType.CANCELLED
    assert received.count(ModelStreamEventType.CANCELLED) == 1
    assert "PROVIDER_TIMEOUT" not in codes


def test_the_stream_deadline_is_distinct_from_user_cancellation() -> None:
    adapter = _LateContentAdapter("local", sleep_seconds=0.05)
    runtime = _streaming_adapter_runtime(adapter)
    cancellation = ModelCallCancellation()

    events = list(
        runtime.gateway.stream(
            _request(timeout_seconds=0.02), cancellation=cancellation
        )
    )

    # A deadline expiration is a timeout, never a cancellation.
    assert events[-1].event_type is ModelStreamEventType.ERROR
    assert events[-1].error_code == "PROVIDER_TIMEOUT"
    assert cancellation.is_cancelled is True
