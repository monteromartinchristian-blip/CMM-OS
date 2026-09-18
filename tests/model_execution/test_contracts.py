"""CMMChat Wave E0 — deterministic contract tests of the model execution seam.

The seam's input is derived from a canonical Phase 11.2
``OrchestrationDecisionRecord`` and its output is a normalized, secret-free
result.  These tests pin both ends of that boundary: the exact mapping from the
canonical decision, the fail-closed validation of every public field, and the
guarantee that a failure never carries anything but safe identifiers.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.model_execution.contracts import (
    ModelExecutionErrorCode,
    ModelExecutionFailure,
    ModelExecutionParameters,
    ModelExecutionRequest,
    ModelExecutionResult,
    ModelExecutionStatus,
)
from cmm.orchestration.contracts import (
    ExecutionRoute,
    IntentKind,
    OrchestrationChannel,
    OrchestrationDecisionRecord,
    PolicyDisposition,
)

REQUEST_ID = "request-wave-e0-1"
DECISION_ID = f"orchestration-decision:{REQUEST_ID}"
PROMPT = "Reply with exactly: CMM_OS_ROUTER_CANARY_OK"


def _record(
    *,
    route: ExecutionRoute = ExecutionRoute.DIRECT_RESPONSE,
    request_id: str = REQUEST_ID,
    decision_id: str = DECISION_ID,
) -> OrchestrationDecisionRecord:
    """Return one canonical decision record as the orchestrator persists it."""

    return OrchestrationDecisionRecord(
        decision_id=decision_id,
        request_id=request_id,
        channel=OrchestrationChannel.CONVERSATION,
        intent=IntentKind.QUESTION,
        execution_route=route,
        policy_disposition=PolicyDisposition.ALLOW_ROUTE,
        session_id="session-wave-e0-1",
        occurred_at=datetime(2026, 9, 19, 10, 0, 0, tzinfo=timezone.utc),
    )


# ── Generation parameters ────────────────────────────────────────────────────


def test_parameters_default_to_the_canonical_generation_defaults() -> None:
    parameters = ModelExecutionParameters()

    assert parameters.temperature == 0.0
    assert parameters.max_tokens is None


def test_parameters_accept_a_bounded_temperature_and_a_positive_max_tokens() -> None:
    parameters = ModelExecutionParameters(temperature=0.2, max_tokens=64)

    assert parameters.temperature == 0.2
    assert parameters.max_tokens == 64


@pytest.mark.parametrize("temperature", [-0.1, 2.1, float("inf"), float("nan")])
def test_parameters_reject_an_out_of_range_temperature(temperature: float) -> None:
    with pytest.raises(ValueError):
        ModelExecutionParameters(temperature=temperature)


@pytest.mark.parametrize("temperature", [True, "0.5", None])
def test_parameters_reject_a_non_numeric_temperature(temperature: object) -> None:
    with pytest.raises(TypeError):
        ModelExecutionParameters(temperature=temperature)  # type: ignore[arg-type]


@pytest.mark.parametrize("max_tokens", [0, -1, True, "64", 1.5])
def test_parameters_reject_an_invalid_max_tokens(max_tokens: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        ModelExecutionParameters(max_tokens=max_tokens)  # type: ignore[arg-type]


# ── Request ──────────────────────────────────────────────────────────────────


def test_request_defaults_carry_the_canonical_requirements_and_parameters() -> None:
    request = ModelExecutionRequest(
        request_id=REQUEST_ID,
        decision_id=DECISION_ID,
        route=ExecutionRoute.DIRECT_RESPONSE,
        prompt=PROMPT,
    )

    assert request.request_id == REQUEST_ID
    assert request.decision_id == DECISION_ID
    assert request.route is ExecutionRoute.DIRECT_RESPONSE
    assert request.prompt == PROMPT
    assert request.requirements.minimum_context_window == 1
    assert request.parameters == ModelExecutionParameters()


@pytest.mark.parametrize("field", ["request_id", "decision_id", "prompt"])
@pytest.mark.parametrize("value", ["", "   ", None, 7])
def test_request_rejects_a_malformed_identifier_or_prompt(
    field: str, value: object
) -> None:
    arguments: dict[str, object] = {
        "request_id": REQUEST_ID,
        "decision_id": DECISION_ID,
        "route": ExecutionRoute.DIRECT_RESPONSE,
        "prompt": PROMPT,
    }
    arguments[field] = value

    with pytest.raises((TypeError, ValueError)):
        ModelExecutionRequest(**arguments)  # type: ignore[arg-type]


def test_request_rejects_a_route_that_is_not_the_canonical_route_enum() -> None:
    with pytest.raises(TypeError):
        ModelExecutionRequest(
            request_id=REQUEST_ID,
            decision_id=DECISION_ID,
            route="direct_response",  # type: ignore[arg-type]
            prompt=PROMPT,
        )


def test_request_maps_the_canonical_decision_without_inventing_facts() -> None:
    record = _record()

    request = ModelExecutionRequest.from_decision(record, prompt=PROMPT)

    assert request.request_id == record.request_id
    assert request.decision_id == record.decision_id
    assert request.route is record.execution_route
    assert request.prompt == PROMPT


def test_request_maps_a_non_executable_route_without_reclassifying_it() -> None:
    """The mapping is faithful: refusing the route is the executor's decision."""

    record = _record(route=ExecutionRoute.WORKFLOW)

    request = ModelExecutionRequest.from_decision(record, prompt=PROMPT)

    assert request.route is ExecutionRoute.WORKFLOW


def test_request_mapping_rejects_a_non_decision_value() -> None:
    with pytest.raises(TypeError):
        ModelExecutionRequest.from_decision({"request_id": REQUEST_ID}, prompt=PROMPT)  # type: ignore[arg-type]


def test_request_mapping_carries_explicit_requirements_and_parameters() -> None:
    from kernel.llm.model_selection import ModelRequirements

    requirements = ModelRequirements(minimum_context_window=4096)
    parameters = ModelExecutionParameters(temperature=0.5, max_tokens=8)
    record = _record()

    request = ModelExecutionRequest.from_decision(
        record, prompt=PROMPT, requirements=requirements, parameters=parameters
    )

    assert request.requirements is requirements
    assert request.parameters is parameters


# ── Failure and result ───────────────────────────────────────────────────────


def test_failure_freezes_its_safe_details_and_requires_a_code_and_message() -> None:
    failure = ModelExecutionFailure(
        code=ModelExecutionErrorCode.PROVIDER_UNAVAILABLE,
        message="The configured model provider is not available",
        retryable=True,
        details={"provider_id": "cmmchat-router"},
    )

    assert failure.code is ModelExecutionErrorCode.PROVIDER_UNAVAILABLE
    assert failure.retryable is True
    with pytest.raises(TypeError):
        failure.details["provider_id"] = "other"  # type: ignore[index]


def test_failure_rejects_a_blank_message_and_a_non_boolean_retryable() -> None:
    with pytest.raises((TypeError, ValueError)):
        ModelExecutionFailure(
            code=ModelExecutionErrorCode.PROVIDER_FAILURE,
            message="   ",
            retryable=True,
        )
    with pytest.raises(TypeError):
        ModelExecutionFailure(
            code=ModelExecutionErrorCode.PROVIDER_FAILURE,
            message="safe",
            retryable="yes",  # type: ignore[arg-type]
        )


def test_successful_result_carries_the_normalized_assistant_text() -> None:
    result = ModelExecutionResult.succeeded(
        request_id=REQUEST_ID,
        decision_id=DECISION_ID,
        text="CMM_OS_ROUTER_CANARY_OK",
        provider_id="cmmchat-router",
        model_id="chatgpt/chatgpt-web/medium",
        routing_decision_id="routing-1",
        usage_prompt_tokens=12,
        usage_completion_tokens=4,
        finish_reason="stop",
    )

    assert result.status is ModelExecutionStatus.SUCCEEDED
    assert result.is_successful is True
    assert result.text == "CMM_OS_ROUTER_CANARY_OK"
    assert result.error is None
    assert result.total_tokens == 16


def test_failed_result_carries_a_normalized_failure_and_no_text() -> None:
    failure = ModelExecutionFailure(
        code=ModelExecutionErrorCode.MODEL_UNAVAILABLE,
        message="No canonical model satisfies the request",
        retryable=False,
    )

    result = ModelExecutionResult.failed(
        request_id=REQUEST_ID, decision_id=DECISION_ID, error=failure
    )

    assert result.status is ModelExecutionStatus.FAILED
    assert result.is_successful is False
    assert result.text is None
    assert result.error is failure
    assert result.model_id is None


def test_a_failed_result_cannot_be_built_without_a_failure() -> None:
    with pytest.raises((TypeError, ValueError)):
        ModelExecutionResult(
            status=ModelExecutionStatus.FAILED,
            request_id=REQUEST_ID,
            decision_id=DECISION_ID,
        )


def test_a_successful_result_cannot_be_built_without_assistant_text() -> None:
    with pytest.raises((TypeError, ValueError)):
        ModelExecutionResult(
            status=ModelExecutionStatus.SUCCEEDED,
            request_id=REQUEST_ID,
            decision_id=DECISION_ID,
        )


def test_the_public_result_serialization_carries_no_secret_shaped_field() -> None:
    result = ModelExecutionResult.succeeded(
        request_id=REQUEST_ID,
        decision_id=DECISION_ID,
        text="ok",
        provider_id="cmmchat-router",
        model_id="chatgpt/chatgpt-web/medium",
        routing_decision_id="routing-1",
    )

    serialized = result.to_dict()

    assert sorted(serialized) == sorted(
        {
            "status",
            "request_id",
            "decision_id",
            "text",
            "provider_id",
            "model_id",
            "routing_decision_id",
            "usage_prompt_tokens",
            "usage_completion_tokens",
            "finish_reason",
            "error",
        }
    )
    lowered = repr(serialized).lower()
    for fragment in ("api_key", "bearer", "token=", "secret", "password"):
        assert fragment not in lowered
