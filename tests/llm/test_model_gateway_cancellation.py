"""Phase 11.21 — model-call cancellation tests.

Cancellation is narrow: it applies to exactly one model call.  It is
cooperative, idempotent, produces one deterministic terminal ``CANCELLED``
event, stops all later emission, and never reaches unrelated calls, workflows or
sessions.
"""

from __future__ import annotations

import dataclasses

import pytest

from kernel.llm.capabilities import ModelCapabilities
from kernel.llm.model_gateway_contracts import (
    ModelGatewayRequest,
    ModelInputPart,
    ModelStreamEventType,
)
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode
from kernel.llm.model_streaming import ModelCallCancellation, ModelCallHandle
from tests.llm.model_gateway_support import build_runtime

STREAMING = ModelCapabilities(streaming=True)


def _request(request_id: str = "model-request-1") -> ModelGatewayRequest:
    return ModelGatewayRequest(
        request_id=request_id,
        model_id="local:model-1",
        input_parts=(ModelInputPart.text_part("stream please"),),
    )


def _runtime(**overrides: object):
    return build_runtime(capabilities=STREAMING, **overrides)  # type: ignore[arg-type]


# ── Cancellation token contract ──────────────────────────────────────────────


def test_cancellation_is_idempotent_and_reports_the_first_transition() -> None:
    cancellation = ModelCallCancellation()

    assert cancellation.is_cancelled is False
    assert cancellation.cancel("first") is True
    assert cancellation.cancel("second") is False
    assert cancellation.is_cancelled is True
    assert cancellation.reason == "first"


def test_a_listener_registered_after_cancellation_fires_immediately() -> None:
    cancellation = ModelCallCancellation()
    cancellation.cancel("stop")
    fired: list[str] = []

    cancellation.add_listener(lambda: fired.append("late"))

    assert fired == ["late"]


def test_cancellation_listeners_fire_once() -> None:
    cancellation = ModelCallCancellation()
    fired: list[str] = []
    cancellation.add_listener(lambda: fired.append("once"))

    cancellation.cancel("stop")
    cancellation.cancel("again")

    assert fired == ["once"]


def test_cancellation_carries_no_session_or_workflow_scope() -> None:
    cancellation = ModelCallCancellation()
    handle = ModelCallHandle(request_id="model-request-1")

    assert {field.name for field in dataclasses.fields(ModelCallHandle)} == {
        "request_id",
        "cancellation",
    }
    for forbidden in ("workflow_id", "session_id", "run_id", "conversation_id"):
        assert not hasattr(cancellation, forbidden)
        assert not hasattr(handle, forbidden)


def test_cancellation_raise_if_cancelled_uses_the_canonical_error() -> None:
    cancellation = ModelCallCancellation()

    cancellation.raise_if_cancelled()
    cancellation.cancel("stop")
    with pytest.raises(ModelGatewayError) as error:
        cancellation.raise_if_cancelled()

    assert error.value.code is ModelGatewayErrorCode.MODEL_CALL_CANCELLED
    assert error.value.retryable is False


# ── Cancellation through the gateway stream ─────────────────────────────────


def test_cancel_before_the_first_content_yields_one_cancelled_terminal() -> None:
    runtime = _runtime()
    runtime.adapter().add_stream(("a", "b", "c"))
    cancellation = ModelCallCancellation()
    cancellation.cancel("caller cancelled")

    events = list(runtime.gateway.stream(_request(), cancellation=cancellation))

    assert [event.event_type for event in events] == [
        ModelStreamEventType.STARTED,
        ModelStreamEventType.CANCELLED,
    ]
    assert sum(event.is_terminal for event in events) == 1
    assert all(event.content_delta is None for event in events)


def test_cancel_mid_stream_stops_all_later_content() -> None:
    runtime = _runtime()
    runtime.adapter().add_stream(("a", "b", "c", "d", "e"))
    cancellation = ModelCallCancellation()

    received: list[ModelStreamEventType] = []
    deltas: list[str] = []
    for event in runtime.gateway.stream(_request(), cancellation=cancellation):
        received.append(event.event_type)
        if event.event_type is ModelStreamEventType.CONTENT_DELTA:
            deltas.append(event.content_delta or "")
            cancellation.cancel("enough content")

    assert received[-1] is ModelStreamEventType.CANCELLED
    assert received.count(ModelStreamEventType.CANCELLED) == 1
    assert deltas == ["a"]
    assert received.index(ModelStreamEventType.CANCELLED) == len(received) - 1


def test_the_provider_observes_the_cancellation() -> None:
    runtime = _runtime()
    runtime.adapter().add_stream(("a", "b", "c", "d"))
    cancellation = ModelCallCancellation()

    events = list(runtime.gateway.stream(_request(), cancellation=cancellation))
    cancellation.cancel("already finished")

    assert runtime.adapter().call_count == 1
    assert (
        sum(event.event_type is ModelStreamEventType.CONTENT_DELTA for event in events)
        == 4
    )


def test_a_cancelled_stream_records_safe_cancellation_evidence() -> None:
    runtime = _runtime()
    runtime.adapter().add_stream(("a", "b"))
    cancellation = ModelCallCancellation()
    cancellation.cancel("stop")

    list(runtime.gateway.stream(_request(), cancellation=cancellation))

    assert len(runtime.sink.records) == 1
    facts = runtime.sink.records[0]
    assert facts.cancelled is True
    assert facts.success is False
    assert facts.error_code is None
    assert facts.streamed is True


def test_cancellation_through_the_narrow_call_handle() -> None:
    runtime = _runtime()
    runtime.adapter().add_stream(("a", "b"))
    handle = runtime.gateway.open_call(_request())

    handle.cancel("user pressed stop")
    events = list(runtime.gateway.stream(_request(), cancellation=handle.cancellation))

    assert events[-1].event_type is ModelStreamEventType.CANCELLED
    assert handle.cancelled is True


def test_cancelling_one_call_does_not_cancel_another() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(content="unaffected")
    runtime.adapter().add_stream(("first",))

    first = runtime.gateway.open_call(_request("model-request-1"))
    second = runtime.gateway.open_call(_request("model-request-2"))
    first.cancel("cancel only the first call")

    first_events = list(
        runtime.gateway.stream(
            _request("model-request-1"), cancellation=first.cancellation
        )
    )
    second_response = runtime.gateway.execute(
        _request("model-request-2"), cancellation=second.cancellation
    )

    assert first_events[-1].event_type is ModelStreamEventType.CANCELLED
    assert second.cancelled is False
    assert second_response.content == "unaffected"


def test_cancellation_mid_execution_is_not_retried() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(content="never")
    cancellation = ModelCallCancellation()
    cancellation.cancel("stop before I/O")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(), cancellation=cancellation)

    assert error.value.code is ModelGatewayErrorCode.MODEL_CALL_CANCELLED
    assert runtime.adapter().call_count == 0
