"""Phase 11.21 — reasoning-effort semantics tests.

Reasoning effort is a mandatory Phase 11.21 capability.  These tests freeze the
closed canonical enum, explicit model-declared support, provider-local
translation, the absence of any silent downgrade or upgrade, failure before
provider I/O and safe requested/effective recording.
"""

from __future__ import annotations

import json

import pytest

from kernel.llm.capabilities import ModelCapabilities, ReasoningEffort
from kernel.llm.model_gateway_contracts import (
    ModelGatewayRequest,
    ModelInputPart,
)
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode
from kernel.llm.model_provider_adapter import (
    InMemoryModelProviderAdapter,
    ProviderModelRequest,
    ProviderModelResponse,
)
from tests.llm.model_gateway_support import TEXT_CAPABLE, build_runtime

NATIVE_NAMES = {
    ReasoningEffort.NONE: "reasoning_off",
    ReasoningEffort.LOW: "thinking_budget_low",
    ReasoningEffort.MEDIUM: "thinking_budget_medium",
    ReasoningEffort.HIGH: "thinking_budget_high",
    ReasoningEffort.EXTRA_HIGH: "thinking_budget_max",
}

LEVELS = (
    ReasoningEffort.LOW,
    ReasoningEffort.MEDIUM,
    ReasoningEffort.HIGH,
)


def _request(
    effort: ReasoningEffort = ReasoningEffort.DEFAULT,
    **overrides: object,
) -> ModelGatewayRequest:
    values: dict[str, object] = {
        "request_id": "model-request-1",
        "model_id": "local:model-1",
        "input_parts": (ModelInputPart.text_part("piensa"),),
        "reasoning_effort": effort,
    }
    values.update(overrides)
    return ModelGatewayRequest(**values)  # type: ignore[arg-type]


def _runtime(
    *,
    reasoning_efforts: tuple[ReasoningEffort, ...] = LEVELS,
    reasoning: bool = True,
    **overrides: object,
):
    capabilities = ModelCapabilities(
        reasoning=reasoning,
        reasoning_efforts=reasoning_efforts,
        structured_output=TEXT_CAPABLE.structured_output,
        tool_calling=TEXT_CAPABLE.tool_calling,
        json_schema=TEXT_CAPABLE.json_schema,
    )
    adapter = InMemoryModelProviderAdapter("local", reasoning_effort_map=NATIVE_NAMES)
    runtime = build_runtime(
        capabilities=capabilities,
        adapters=(adapter,),
        **overrides,  # type: ignore[arg-type]
    )
    return runtime


def test_default_effort_imposes_no_provider_override() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(content="ok")

    response = runtime.gateway.execute(_request())

    assert runtime.adapter().requests[0].reasoning_effort is ReasoningEffort.DEFAULT
    assert runtime.adapter().native_efforts == (None,)
    assert response.effective_reasoning_effort is ReasoningEffort.DEFAULT
    assert response.reasoning_used is False
    assert response.facts is not None
    assert response.facts.requested_reasoning_effort is ReasoningEffort.DEFAULT
    assert response.facts.effective_reasoning_effort is ReasoningEffort.DEFAULT


def test_supported_high_reaches_the_adapter_and_is_recorded() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(content="deep")

    response = runtime.gateway.execute(_request(ReasoningEffort.HIGH))

    assert runtime.adapter().requests[0].reasoning_effort is ReasoningEffort.HIGH
    assert runtime.adapter().native_efforts == ("thinking_budget_high",)
    assert response.effective_reasoning_effort is ReasoningEffort.HIGH
    assert response.reasoning_used is True
    assert response.facts is not None
    assert response.facts.requested_reasoning_effort is ReasoningEffort.HIGH
    assert response.facts.effective_reasoning_effort is ReasoningEffort.HIGH
    assert response.facts.reasoning_used is True


@pytest.mark.parametrize("effort", LEVELS)
def test_every_declared_level_is_preserved_exactly(effort: ReasoningEffort) -> None:
    runtime = _runtime()
    runtime.adapter().add_response(content="ok")

    response = runtime.gateway.execute(_request(effort))

    assert response.effective_reasoning_effort is effort
    assert runtime.adapter().native_efforts == (NATIVE_NAMES[effort],)


def test_unsupported_effort_fails_before_provider_io() -> None:
    runtime = _runtime(reasoning_efforts=(ReasoningEffort.LOW,))
    runtime.adapter().add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(ReasoningEffort.HIGH))

    assert error.value.code is ModelGatewayErrorCode.UNSUPPORTED_REASONING_EFFORT
    assert error.value.retryable is False
    assert runtime.adapter().call_count == 0


def test_effort_is_never_silently_downgraded() -> None:
    runtime = _runtime(reasoning_efforts=LEVELS)
    runtime.adapter().add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(ReasoningEffort.EXTRA_HIGH))

    assert error.value.code is ModelGatewayErrorCode.UNSUPPORTED_REASONING_EFFORT
    assert runtime.adapter().call_count == 0


def test_effort_is_never_silently_upgraded() -> None:
    runtime = _runtime(reasoning_efforts=(ReasoningEffort.MEDIUM,))
    runtime.adapter().add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(ReasoningEffort.NONE))

    assert error.value.code is ModelGatewayErrorCode.UNSUPPORTED_REASONING_EFFORT
    assert runtime.adapter().native_efforts == ()


def test_declared_none_level_is_honoured_exactly() -> None:
    runtime = _runtime(reasoning_efforts=(ReasoningEffort.NONE,))
    runtime.adapter().add_response(content="ok")

    response = runtime.gateway.execute(_request(ReasoningEffort.NONE))

    assert response.effective_reasoning_effort is ReasoningEffort.NONE
    assert runtime.adapter().native_efforts == ("reasoning_off",)
    assert response.reasoning_used is False


def test_reasoning_capability_without_declared_levels_is_unavailable() -> None:
    runtime = _runtime(reasoning=True, reasoning_efforts=())
    runtime.adapter().add_response(content="ok")

    default_response = runtime.gateway.execute(_request())
    assert default_response.content == "ok"

    runtime.adapter().add_response(content="never")
    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(ReasoningEffort.HIGH))

    assert error.value.code is ModelGatewayErrorCode.UNSUPPORTED_REASONING_EFFORT
    assert runtime.adapter().call_count == 1


def test_required_reasoning_capability_does_not_rewrite_requested_effort() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(content="ok")

    response = runtime.gateway.execute(
        _request(ReasoningEffort.HIGH, required_capabilities=("reasoning",))
    )

    assert response.effective_reasoning_effort is ReasoningEffort.HIGH
    assert response.facts is not None
    assert response.facts.requested_reasoning_effort is ReasoningEffort.HIGH
    assert response.facts.effective_reasoning_effort is ReasoningEffort.HIGH


def test_provider_native_effort_name_never_leaks_into_canonical_contracts() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(content="deep")

    response = runtime.gateway.execute(_request(ReasoningEffort.HIGH))

    serialized = json.dumps(response.to_dict())
    assert "thinking_budget_high" not in serialized
    assert response.facts is not None
    assert "thinking_budget_high" not in json.dumps(response.facts.to_dict())


class _DowngradingAdapter(InMemoryModelProviderAdapter):
    """Test adapter that violates the canonical effective-effort contract."""

    def execute(
        self,
        request: ProviderModelRequest,
        *,
        cancellation: object | None = None,
    ) -> ProviderModelResponse:
        return ProviderModelResponse(
            content="downgraded",
            effective_reasoning_effort=ReasoningEffort.MEDIUM,
            reasoning_used=True,
        )


def test_adapter_cannot_silently_change_the_requested_effort() -> None:
    adapter = _DowngradingAdapter("local")
    runtime = build_runtime(
        capabilities=ModelCapabilities(
            reasoning=True,
            reasoning_efforts=LEVELS,
        ),
        adapters=(adapter,),
    )

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(ReasoningEffort.HIGH))

    assert error.value.code is ModelGatewayErrorCode.PROVIDER_FAILURE
    assert error.value.retryable is False


def test_adapter_cannot_invent_reasoning_when_none_was_requested() -> None:
    adapter = _DowngradingAdapter("local")
    runtime = build_runtime(
        capabilities=ModelCapabilities(reasoning=True, reasoning_efforts=LEVELS),
        adapters=(adapter,),
    )

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request())

    assert error.value.code is ModelGatewayErrorCode.PROVIDER_FAILURE
