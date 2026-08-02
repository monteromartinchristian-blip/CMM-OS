"""Narrow translation from model fallback decisions to generic recovery."""

from __future__ import annotations

from cmm.agent_runtime.enums import RecoveryReasonCode, RecoveryStrategy
from cmm.agent_runtime.model_fallback_contracts import ModelFallbackDecision
from cmm.agent_runtime.model_fallback_errors import InvalidModelFallbackContractError
from cmm.agent_runtime.recovery_contracts import RecoveryDecision


class ModelFallbackRecoveryAdapter:
    """Translate without adding model-specific logic to RecoveryDecisionEngine."""

    def to_recovery_decision(
        self,
        decision: ModelFallbackDecision,
        *,
        recovery_context_id: str,
    ) -> RecoveryDecision:
        try:
            strategy = RecoveryStrategy(decision.recovery_strategy or "fail")
        except ValueError as exc:
            raise InvalidModelFallbackContractError(
                "decision contains an unsupported recovery strategy"
            ) from exc
        reason_map = {
            "validation_failed": RecoveryReasonCode.VALIDATION_FAILED,
            "revalidation_required": RecoveryReasonCode.VALIDATION_FAILED,
            "budget_exhausted": RecoveryReasonCode.BUDGET_EXHAUSTED,
            "approval_required": RecoveryReasonCode.APPROVAL_REQUIRED,
            "maximum_attempts_exhausted": RecoveryReasonCode.RETRIES_EXHAUSTED,
            "retries_exhausted": RecoveryReasonCode.RETRIES_EXHAUSTED,
            "privacy_conflict": RecoveryReasonCode.POLICY_CONFLICT,
            "policy_denied": RecoveryReasonCode.POLICY_CONFLICT,
            "premium_not_allowed": RecoveryReasonCode.POLICY_CONFLICT,
            "permanent_error": RecoveryReasonCode.NON_RETRYABLE_ERROR,
        }
        transient = {"timeout", "rate_limit", "provider_unavailable", "transient_error"}
        reasons = tuple(
            reason_map.get(code, RecoveryReasonCode.TRANSIENT_ERROR)
            if code not in transient
            else RecoveryReasonCode.TRANSIENT_ERROR
            for code in decision.reason_codes
        ) or (RecoveryReasonCode.UNKNOWN_FAILURE,)
        return RecoveryDecision(
            recovery_decision_id=f"model-fallback-{decision.idempotency_key[:16]}",
            recovery_context_id=recovery_context_id,
            strategy=strategy,
            reason_codes=reasons,
            requires_approval=decision.requires_approval,
            modified_parameters={
                "model_id": decision.selected_model_id,
                "provider_id": decision.selected_provider_id,
            },
            idempotency_key=decision.idempotency_key,
            metadata={
                "model_fallback_action": decision.action.value,
                **dict(decision.metadata),
            },
        )
