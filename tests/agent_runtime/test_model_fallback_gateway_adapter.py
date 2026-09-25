"""Phase 11.21 — canonical fallback planner adapter tests.

The planner must delegate attempt bounding and candidate validity to the
canonical Agent Runtime fallback decision engine while treating the caller's
authorized sequence as the only candidate ordering — no re-ranking, no
requirement relaxation, no invented routing policy.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cmm.agent_runtime.model_fallback_contracts import (
    ModelFallbackAction,
    ModelFallbackPolicy,
    ModelFallbackTrigger,
)
from cmm.agent_runtime.model_fallback_gateway_adapter import (
    ModelGatewayFallbackPlanner,
    fallback_trigger_for_error,
)
from kernel.llm.model_gateway_contracts import ModelFallbackAttempt
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode
from kernel.llm.model_router import RoutingCandidate
from kernel.llm.model_selection import ModelRequirements


def _candidate(rank: int, provider_id: str, model_id: str) -> RoutingCandidate:
    return RoutingCandidate(
        rank=rank,
        qualified_model_id=f"{provider_id}:{model_id}",
        provider_id=provider_id,
        model_id=model_id,
        input_cost_per_million=Decimal("0.1"),
        output_cost_per_million=Decimal("0.2"),
        context_window=32768,
    )


def _attempt(
    index: int,
    *,
    provider_id: str = "local",
    model_id: str = "primary",
    error_code: str = ModelGatewayErrorCode.PROVIDER_FAILURE.value,
    retryable: bool = True,
    success: bool = False,
) -> ModelFallbackAttempt:
    return ModelFallbackAttempt(
        attempt_index=index,
        model_id=model_id,
        provider_id=provider_id,
        success=success,
        error_code=error_code,
        retryable=retryable,
        latency_ms=5,
    )


def _transient() -> ModelGatewayError:
    return ModelGatewayError(
        ModelGatewayErrorCode.PROVIDER_FAILURE, "transient failure", retryable=True
    )


def _timeout() -> ModelGatewayError:
    return ModelGatewayError(
        ModelGatewayErrorCode.PROVIDER_TIMEOUT, "timeout", retryable=True
    )


def _privacy() -> ModelGatewayError:
    return ModelGatewayError(ModelGatewayErrorCode.PRIVACY_DENIED, "denied")


def _planner(**overrides: object) -> ModelGatewayFallbackPlanner:
    return ModelGatewayFallbackPlanner(**overrides)  # type: ignore[arg-type]


def test_selects_the_next_authorized_candidate() -> None:
    planner = _planner()

    decision = planner.next_selection(
        candidates=(
            _candidate(1, "local", "primary"),
            _candidate(2, "remote-b", "secondary"),
            _candidate(3, "remote-c", "tertiary"),
        ),
        attempts=(_attempt(1),),
        error=_transient(),
        requirements=ModelRequirements(),
    )

    assert decision.action is ModelFallbackAction.NEXT_ROUTING_CANDIDATE
    assert decision.selected_provider_id == "remote-b"
    assert decision.selected_model_id == "secondary"


def test_preserves_the_caller_authorized_order() -> None:
    planner = _planner()

    decision = planner.next_selection(
        candidates=(
            _candidate(1, "zeta", "last-alphabetically"),
            _candidate(2, "alpha", "first-alphabetically"),
        ),
        attempts=(_attempt(1, provider_id="local", model_id="primary"),),
        error=_transient(),
        requirements=ModelRequirements(),
    )

    assert decision.selected_provider_id == "zeta"
    assert decision.selected_model_id == "last-alphabetically"


def test_the_failed_model_is_excluded() -> None:
    planner = _planner()

    decision = planner.next_selection(
        candidates=(
            _candidate(1, "local", "primary"),
            _candidate(2, "remote-b", "secondary"),
        ),
        attempts=(_attempt(1, provider_id="local", model_id="primary"),),
        error=_transient(),
        requirements=ModelRequirements(),
    )

    assert decision.selected_model_id == "secondary"
    assert "local:primary" in decision.skipped_candidates


def test_exhaustion_returns_a_non_selection_decision() -> None:
    planner = _planner()

    decision = planner.next_selection(
        candidates=(_candidate(1, "local", "primary"),),
        attempts=(_attempt(1, provider_id="local", model_id="primary"),),
        error=_transient(),
        requirements=ModelRequirements(),
    )

    assert decision.action is not ModelFallbackAction.NEXT_ROUTING_CANDIDATE
    assert decision.selected_model_id is None


def test_the_policy_bounds_the_attempt_sequence() -> None:
    planner = _planner(
        policy=ModelFallbackPolicy(maximum_attempts=2, maximum_attempts_per_model=1)
    )

    decision = planner.next_selection(
        candidates=(_candidate(2, "remote-b", "secondary"),),
        attempts=(
            _attempt(1, provider_id="local", model_id="primary"),
            _attempt(2, provider_id="remote-b", model_id="secondary"),
        ),
        error=_transient(),
        requirements=ModelRequirements(),
    )

    assert decision.action is ModelFallbackAction.FAIL_TERMINAL
    assert "maximum_attempts_exhausted" in decision.reason_codes


def test_a_cycling_candidate_is_rejected() -> None:
    planner = _planner()

    decision = planner.next_selection(
        candidates=(
            _candidate(1, "local", "primary"),
            _candidate(2, "remote-b", "secondary"),
        ),
        attempts=(
            _attempt(1, provider_id="local", model_id="primary"),
            _attempt(
                2,
                provider_id="remote-b",
                model_id="secondary",
                error_code=ModelGatewayErrorCode.PROVIDER_TIMEOUT.value,
            ),
        ),
        error=_timeout(),
        requirements=ModelRequirements(),
    )

    assert decision.action is not ModelFallbackAction.NEXT_ROUTING_CANDIDATE


def test_requirements_are_never_relaxed() -> None:
    requirements = ModelRequirements(
        vision=True,
        tool_calling=True,
        structured_output=True,
        minimum_context_window=8192,
    )
    planner = _planner()

    decision = planner.next_selection(
        candidates=(_candidate(2, "remote-b", "secondary"),),
        attempts=(_attempt(1),),
        error=_transient(),
        requirements=requirements,
    )

    assert planner.policy.allow_requirement_modification is False
    assert decision.effective_requirements == requirements


def test_privacy_incompatibility_is_restricted_not_relaxed() -> None:
    planner = _planner()

    decision = planner.next_selection(
        candidates=(_candidate(2, "remote-b", "secondary"),),
        attempts=(
            _attempt(
                1,
                error_code=ModelGatewayErrorCode.PRIVACY_DENIED.value,
                retryable=False,
            ),
        ),
        error=_privacy(),
        requirements=ModelRequirements(privacy="LOCAL_ONLY"),
    )

    assert decision.action is not ModelFallbackAction.NEXT_ROUTING_CANDIDATE
    assert "privacy_conflict" in decision.reason_codes


def test_a_context_limited_candidate_is_skipped() -> None:
    planner = _planner()
    narrow = RoutingCandidate(
        rank=1,
        qualified_model_id="remote-b:secondary",
        provider_id="remote-b",
        model_id="secondary",
        input_cost_per_million=None,
        output_cost_per_million=None,
        context_window=1024,
    )

    decision = planner.next_selection(
        candidates=(
            narrow,
            _candidate(2, "remote-c", "tertiary"),
        ),
        attempts=(_attempt(1),),
        error=_transient(),
        requirements=ModelRequirements(minimum_context_window=8192),
    )

    assert decision.selected_model_id == "tertiary"
    assert "remote-b:secondary" in decision.skipped_candidates


def test_decision_records_policy_and_history_metadata() -> None:
    planner = _planner()

    decision = planner.next_selection(
        candidates=(_candidate(2, "remote-b", "secondary"),),
        attempts=(_attempt(1),),
        error=_transient(),
        requirements=ModelRequirements(),
    )

    assert decision.metadata["policy_id"] == planner.policy.id
    assert decision.metadata["history_size"] == 1
    assert decision.idempotency_key


def test_planner_rejects_invalid_inputs() -> None:
    planner = _planner()

    with pytest.raises(ValueError):
        planner.next_selection(
            candidates=(),
            attempts=(_attempt(1),),
            error=_transient(),
            requirements=ModelRequirements(),
        )
    with pytest.raises(ValueError):
        planner.next_selection(
            candidates=(_candidate(1, "local", "primary"),),
            attempts=(),
            error=_transient(),
            requirements=ModelRequirements(),
        )


@pytest.mark.parametrize(
    ("code", "retryable", "expected"),
    [
        (ModelGatewayErrorCode.PROVIDER_TIMEOUT, True, ModelFallbackTrigger.TIMEOUT),
        (
            ModelGatewayErrorCode.PROVIDER_FAILURE,
            True,
            ModelFallbackTrigger.TRANSIENT_ERROR,
        ),
        (
            ModelGatewayErrorCode.PROVIDER_FAILURE,
            False,
            ModelFallbackTrigger.PERMANENT_ERROR,
        ),
        (
            ModelGatewayErrorCode.STREAM_FAILURE,
            True,
            ModelFallbackTrigger.TRANSIENT_ERROR,
        ),
        (
            ModelGatewayErrorCode.PRIVACY_DENIED,
            False,
            ModelFallbackTrigger.PRIVACY_INCOMPATIBLE,
        ),
        (
            ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED,
            False,
            ModelFallbackTrigger.CAPABILITY_MISSING,
        ),
        (
            ModelGatewayErrorCode.MODEL_UNAVAILABLE,
            False,
            ModelFallbackTrigger.MODEL_UNAVAILABLE,
        ),
        (
            ModelGatewayErrorCode.PROVIDER_NOT_AVAILABLE,
            False,
            ModelFallbackTrigger.PROVIDER_UNAVAILABLE,
        ),
        (
            ModelGatewayErrorCode.STRUCTURED_OUTPUT_INVALID,
            False,
            ModelFallbackTrigger.STRUCTURED_OUTPUT_INVALID,
        ),
        (
            ModelGatewayErrorCode.MODEL_CALL_CANCELLED,
            False,
            ModelFallbackTrigger.PERMANENT_ERROR,
        ),
    ],
)
def test_trigger_mapping(
    code: ModelGatewayErrorCode,
    retryable: bool,
    expected: ModelFallbackTrigger,
) -> None:
    error = ModelGatewayError(code, "failed", retryable=retryable)

    assert fallback_trigger_for_error(error) is expected


def test_trigger_mapping_rejects_foreign_input() -> None:
    with pytest.raises(TypeError):
        fallback_trigger_for_error("PROVIDER_TIMEOUT")  # type: ignore[arg-type]
