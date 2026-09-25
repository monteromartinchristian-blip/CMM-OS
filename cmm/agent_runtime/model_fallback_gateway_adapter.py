"""Canonical fallback planner for the Model Gateway (Phase 11.21).

Phase 11.21 implements failover *mechanics*, not routing-policy intelligence.
The caller supplies an explicitly authorized fallback sequence; this adapter
plans the next candidate by delegating to the canonical Agent Runtime fallback
decision engine, so attempt bounding, exclusion of already-failed models and
the fail-closed precedence order remain owned by the existing decision
authority.

Two deliberate boundaries:

* the authorized sequence is presented to the engine as the routing decision's
  candidate list *in the caller's order*, and the injected fallback provider is
  an identity function — the gateway never re-ranks or re-routes;
* ``allow_requirement_modification`` stays disabled, so a fallback candidate can
  never relax a failed requirement.
"""

from __future__ import annotations

from collections.abc import Sequence

from cmm.agent_runtime.model_fallback_contracts import (
    ModelAttemptHistory,
    ModelAttemptResult,
    ModelFallbackContext,
    ModelFallbackDecision,
    ModelFallbackPolicy,
    ModelFallbackTrigger,
)
from cmm.agent_runtime.model_fallback_decision_engine import (
    ModelFallbackDecisionEngine,
)
from kernel.llm.model_gateway_contracts import ModelFallbackAttempt
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode
from kernel.llm.model_ranking import ModelRankingPolicy
from kernel.llm.model_router import RoutingCandidate, RoutingDecision
from kernel.llm.model_selection import ModelRequirements

__all__ = [
    "ModelGatewayFallbackPlanner",
    "fallback_trigger_for_error",
]

#: Canonical mapping from a safe gateway failure to a fallback trigger.  It
#: classifies the failure; it never selects a model.
_ERROR_TRIGGERS = {
    ModelGatewayErrorCode.MODEL_NOT_FOUND: ModelFallbackTrigger.MODEL_UNAVAILABLE,
    ModelGatewayErrorCode.PROVIDER_NOT_AVAILABLE: (
        ModelFallbackTrigger.PROVIDER_UNAVAILABLE
    ),
    ModelGatewayErrorCode.MODEL_UNAVAILABLE: ModelFallbackTrigger.MODEL_UNAVAILABLE,
    ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED: (
        ModelFallbackTrigger.CAPABILITY_MISSING
    ),
    ModelGatewayErrorCode.UNSUPPORTED_REASONING_EFFORT: (
        ModelFallbackTrigger.CAPABILITY_MISSING
    ),
    ModelGatewayErrorCode.INPUT_MODALITY_UNSUPPORTED: (
        ModelFallbackTrigger.CAPABILITY_MISSING
    ),
    ModelGatewayErrorCode.PRIVACY_DENIED: (ModelFallbackTrigger.PRIVACY_INCOMPATIBLE),
    ModelGatewayErrorCode.PROVIDER_REQUEST_INVALID: (
        ModelFallbackTrigger.PERMANENT_ERROR
    ),
    ModelGatewayErrorCode.PROVIDER_TIMEOUT: ModelFallbackTrigger.TIMEOUT,
    ModelGatewayErrorCode.PROVIDER_FAILURE: ModelFallbackTrigger.TRANSIENT_ERROR,
    ModelGatewayErrorCode.STREAM_FAILURE: ModelFallbackTrigger.TRANSIENT_ERROR,
    ModelGatewayErrorCode.MODEL_CALL_CANCELLED: (ModelFallbackTrigger.PERMANENT_ERROR),
    ModelGatewayErrorCode.STRUCTURED_OUTPUT_INVALID: (
        ModelFallbackTrigger.STRUCTURED_OUTPUT_INVALID
    ),
    ModelGatewayErrorCode.TOOL_CALL_INVALID: ModelFallbackTrigger.INVALID_RESPONSE,
    ModelGatewayErrorCode.FALLBACK_EXHAUSTED: ModelFallbackTrigger.RETRIES_EXHAUSTED,
}

_AUTHORIZED_SEQUENCE_REASON = "caller_authorized_fallback_sequence"


def fallback_trigger_for_error(error: ModelGatewayError) -> ModelFallbackTrigger:
    """Map one safe gateway failure onto the canonical fallback trigger."""

    if not isinstance(error, ModelGatewayError):
        raise TypeError("error must be a ModelGatewayError")
    if error.code is ModelGatewayErrorCode.PROVIDER_FAILURE and not error.retryable:
        return ModelFallbackTrigger.PERMANENT_ERROR
    return _ERROR_TRIGGERS.get(error.code, ModelFallbackTrigger.PERMANENT_ERROR)


class ModelGatewayFallbackPlanner:
    """Plan the next authorized fallback candidate using the canonical engine."""

    __slots__ = ("_engine", "_operation_id", "_policy", "_workflow_id")

    def __init__(
        self,
        *,
        operation_id: str = "model-gateway-call",
        workflow_id: str = "model-gateway",
        policy: ModelFallbackPolicy | None = None,
    ) -> None:
        if not isinstance(operation_id, str) or not operation_id.strip():
            raise ValueError("operation_id must be a non-empty string")
        if not isinstance(workflow_id, str) or not workflow_id.strip():
            raise ValueError("workflow_id must be a non-empty string")
        if policy is not None and not isinstance(policy, ModelFallbackPolicy):
            raise TypeError("policy must be a ModelFallbackPolicy or None")
        self._operation_id = operation_id.strip()
        self._workflow_id = workflow_id.strip()
        self._policy = policy or ModelFallbackPolicy()
        # The gateway never re-ranks: candidate order is exactly the caller's
        # authorized order, so the injected provider is an identity function.
        self._engine = ModelFallbackDecisionEngine(
            fallback_provider=lambda decision: decision.candidates
        )

    @property
    def policy(self) -> ModelFallbackPolicy:
        """Return the canonical fallback policy bounding this planner."""

        return self._policy

    def next_selection(
        self,
        *,
        candidates: Sequence[RoutingCandidate],
        attempts: Sequence[ModelFallbackAttempt],
        error: ModelGatewayError,
        requirements: ModelRequirements,
    ) -> ModelFallbackDecision:
        """Return the canonical decision for the next fallback candidate."""

        ordered = tuple(candidates)
        if not ordered:
            raise ValueError("candidates must not be empty")
        records = tuple(attempts)
        if not records:
            raise ValueError("attempts must not be empty")
        if not isinstance(requirements, ModelRequirements):
            raise TypeError("requirements must be ModelRequirements")
        if not isinstance(error, ModelGatewayError):
            raise TypeError("error must be a ModelGatewayError")

        trigger = fallback_trigger_for_error(error)
        history = tuple(
            ModelAttemptResult(
                operation_id=self._operation_id,
                attempt_index=record.attempt_index,
                model_id=record.model_id,
                provider_id=record.provider_id,
                trigger=trigger
                if record.error_code == error.code.value
                else (
                    ModelFallbackTrigger.TRANSIENT_ERROR
                    if record.retryable
                    else ModelFallbackTrigger.PERMANENT_ERROR
                ),
                success=record.success,
                latency_ms=record.latency_ms,
            )
            for record in records
        )
        latest = history[-1]

        routing = RoutingDecision(
            id=f"{self._operation_id}-authorized-fallback",
            status="selected",
            selected_model_id=latest.model_id,
            selected_provider_id=latest.provider_id,
            candidates=ordered,
            rejected_models=(),
            requirements=requirements,
            ranking_policy=ModelRankingPolicy(),
            reason_codes=(_AUTHORIZED_SEQUENCE_REASON,),
        )
        context = ModelFallbackContext(
            operation_id=self._operation_id,
            workflow_id=self._workflow_id,
            routing_decision=routing,
            effective_requirements=requirements,
            latest_result=latest,
            history=ModelAttemptHistory(attempts=history),
            policy=self._policy,
        )
        return self._engine.decide(context)
