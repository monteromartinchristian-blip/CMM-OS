"""Phase 11.21 — model-call timeout and bounded transport retry tests.

Timeout must be finite, normalized and must never leave a call reported as
running.  Retry is bounded, transport-level only, on the exact same model and
provider, and never applies to a privacy denial, an invalid request, an
unsupported capability, cancellation or an explicit model incompatibility.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

import pytest

from kernel.llm.capabilities import ModelCapabilities
from kernel.llm.model_gateway_contracts import (
    MAX_RETRY_ATTEMPTS,
    ModelGatewayRequest,
    ModelGatewayRetryPolicy,
    ModelInputPart,
    ModelStreamEventType,
)
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode
from kernel.llm.model_provider_adapter import (
    InMemoryModelProviderAdapter,
    ProviderModelRequest,
    ProviderStreamEvent,
)
from kernel.llm.model_streaming import ModelCallCancellation
from tests.llm.model_gateway_support import TEXT_CAPABLE, build_runtime


def _request(**overrides: object) -> ModelGatewayRequest:
    values: dict[str, object] = {
        "request_id": "model-request-1",
        "model_id": "local:model-1",
        "input_parts": (ModelInputPart.text_part("respond"),),
    }
    values.update(overrides)
    return ModelGatewayRequest(**values)  # type: ignore[arg-type]


def _runtime(**overrides: object):
    overrides.setdefault("capabilities", TEXT_CAPABLE)
    return build_runtime(**overrides)  # type: ignore[arg-type]


# ── Timeout ─────────────────────────────────────────────────────────────────


def test_a_slow_provider_times_out_with_the_canonical_code() -> None:
    runtime = _runtime()
    runtime.adapter().add_timeout(delay_seconds=0.25)

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(timeout_seconds=0.05))

    assert error.value.code is ModelGatewayErrorCode.PROVIDER_TIMEOUT
    assert error.value.retryable is True
    assert error.value.details["timeout_seconds"] == 0.05


def test_a_timed_out_call_is_recorded_and_never_left_running() -> None:
    runtime = _runtime()
    runtime.adapter().add_timeout(delay_seconds=0.25)

    with pytest.raises(ModelGatewayError):
        runtime.gateway.execute(_request(timeout_seconds=0.05))

    assert len(runtime.sink.records) == 1
    facts = runtime.sink.records[0]
    assert facts.timed_out is True
    assert facts.success is False
    assert facts.error_code == "PROVIDER_TIMEOUT"
    assert facts.latency_ms is not None


def test_a_timeout_abandons_the_call_through_its_token() -> None:
    runtime = _runtime()
    runtime.adapter().add_timeout(delay_seconds=0.25)
    cancellation = ModelCallCancellation()

    with pytest.raises(ModelGatewayError):
        runtime.gateway.execute(
            _request(timeout_seconds=0.05), cancellation=cancellation
        )

    assert cancellation.is_cancelled is True


def test_a_streaming_deadline_yields_a_timeout_terminal() -> None:
    runtime = _runtime(
        capabilities=ModelCapabilities(streaming=True),
        adapters=(_SlowStreamAdapter("local"),),
    )

    events = list(runtime.gateway.stream(_request(timeout_seconds=0.05)))

    assert events[-1].event_type is ModelStreamEventType.ERROR
    assert events[-1].error_code == "PROVIDER_TIMEOUT"
    assert sum(event.is_terminal for event in events) == 1


class _SlowStreamAdapter(InMemoryModelProviderAdapter):
    """Test adapter that stalls between provider stream events."""

    def stream(
        self,
        request: ProviderModelRequest,
        *,
        cancellation: object | None = None,
    ) -> Iterator[ProviderStreamEvent]:
        self._record(request)
        yield ProviderStreamEvent(event_type=ModelStreamEventType.STARTED)
        time.sleep(0.15)
        yield ProviderStreamEvent(
            event_type=ModelStreamEventType.CONTENT_DELTA, content_delta="late"
        )


# ── Bounded transport retry ─────────────────────────────────────────────────


def test_no_retry_happens_by_default() -> None:
    runtime = _runtime()
    runtime.adapter().add_failure(
        ModelGatewayErrorCode.PROVIDER_FAILURE, "transient", retryable=True
    )

    with pytest.raises(ModelGatewayError):
        runtime.gateway.execute(_request())

    assert runtime.adapter().call_count == 1
    assert runtime.sink.records[0].retry_count == 0


def test_a_retryable_failure_is_retried_within_the_bound_then_succeeds() -> None:
    runtime = _runtime(retry_policy=ModelGatewayRetryPolicy(max_attempts=3))
    runtime.adapter().add_failure(
        ModelGatewayErrorCode.PROVIDER_FAILURE, "transient", retryable=True
    )
    runtime.adapter().add_response(content="recovered")

    response = runtime.gateway.execute(_request())

    assert response.content == "recovered"
    assert runtime.adapter().call_count == 2
    assert runtime.sink.records[-1].retry_count == 1
    assert runtime.sink.records[-1].success is True


def test_the_retry_bound_is_enforced() -> None:
    runtime = _runtime(retry_policy=ModelGatewayRetryPolicy(max_attempts=2))
    for _ in range(3):
        runtime.adapter().add_failure(
            ModelGatewayErrorCode.PROVIDER_FAILURE, "transient", retryable=True
        )

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request())

    assert error.value.code is ModelGatewayErrorCode.PROVIDER_FAILURE
    assert runtime.adapter().call_count == 2
    assert runtime.sink.records[0].retry_count == 1


def test_retry_reuses_the_exact_same_model_and_provider() -> None:
    runtime = _runtime(retry_policy=ModelGatewayRetryPolicy(max_attempts=2))
    runtime.adapter().add_failure(
        ModelGatewayErrorCode.PROVIDER_FAILURE, "transient", retryable=True
    )
    runtime.adapter().add_response(content="ok")

    runtime.gateway.execute(_request())

    assert runtime.adapter().call_count == 2
    assert {request.model_id for request in runtime.adapter().requests} == {"model-1"}
    assert {request.provider_id for request in runtime.adapter().requests} == {"local"}


def test_a_permanent_provider_failure_is_not_retried() -> None:
    runtime = _runtime(retry_policy=ModelGatewayRetryPolicy(max_attempts=4))
    runtime.adapter().add_failure(
        ModelGatewayErrorCode.PROVIDER_FAILURE,
        "credential rejected",
        retryable=False,
    )

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request())

    assert error.value.retryable is False
    assert runtime.adapter().call_count == 1


def test_cancellation_is_never_retried() -> None:
    runtime = _runtime(retry_policy=ModelGatewayRetryPolicy(max_attempts=4))
    runtime.adapter().add_failure(
        ModelGatewayErrorCode.MODEL_CALL_CANCELLED, "cancelled"
    )

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request())

    assert error.value.code is ModelGatewayErrorCode.MODEL_CALL_CANCELLED
    assert runtime.adapter().call_count == 1


@pytest.mark.parametrize(
    "required_capabilities",
    [("vision",), ("tool_calling",)],
)
def test_a_preflight_refusal_is_never_retried(
    required_capabilities: tuple[str, ...],
) -> None:
    runtime = _runtime(
        capabilities=ModelCapabilities(),
        retry_policy=ModelGatewayRetryPolicy(max_attempts=4),
    )
    runtime.adapter().add_response(content="never")

    with pytest.raises(ModelGatewayError):
        runtime.gateway.execute(_request(required_capabilities=required_capabilities))

    assert runtime.adapter().call_count == 0


def test_retry_policy_is_bounded_at_construction() -> None:
    assert ModelGatewayRetryPolicy(max_attempts=MAX_RETRY_ATTEMPTS).max_attempts == 5

    for invalid in (0, -1, MAX_RETRY_ATTEMPTS + 1):
        with pytest.raises(ValueError):
            ModelGatewayRetryPolicy(max_attempts=invalid)
    with pytest.raises(ValueError):
        ModelGatewayRetryPolicy(backoff_seconds=-1.0)
    with pytest.raises(ValueError):
        ModelGatewayRetryPolicy(backoff_seconds=float("inf"))


def test_gateway_rejects_a_foreign_retry_policy() -> None:
    with pytest.raises(TypeError):
        build_runtime(retry_policy=object())

    with pytest.raises(TypeError):
        build_runtime(retry_policy="max_attempts=3")
