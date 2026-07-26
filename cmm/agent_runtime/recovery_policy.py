"""Phase 9.16 – Recovery Policy Resolver & Evaluators.

Evaluates retry, rollback, and escalation policies against recovery context and error details.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from cmm.agent_runtime.enums import (
    CheckpointStatus,
    EscalationTarget,
    RecoveryReasonCode,
)
from cmm.agent_runtime.recovery_contracts import (
    EscalationPolicy,
    RetryPolicy,
    RollbackPolicy,
)


@dataclass(frozen=True)
class RetryPolicyEvaluation:
    """Outcome of evaluating a RetryPolicy."""

    is_allowed: bool
    reason: str
    reobservation_required: bool = False


@dataclass(frozen=True)
class RollbackPolicyEvaluation:
    """Outcome of evaluating a RollbackPolicy."""

    can_rollback: bool
    requires_approval: bool
    reason: str


@dataclass(frozen=True)
class EscalationPolicyEvaluation:
    """Outcome of evaluating an EscalationPolicy."""

    should_escalate: bool
    target: EscalationTarget
    reason: str


class RetryPolicyEvaluator:
    """Evaluates RetryPolicy rules against attempt state and failure metadata."""

    def evaluate(
        self,
        policy: RetryPolicy,
        attempt_index: int,
        error_type: str,
        operation_id: str = "",
    ) -> RetryPolicyEvaluation:
        """Evaluate if a retry attempt is permissible."""
        # 1. Maximum attempts rule
        if attempt_index > policy.maximum_attempts:
            return RetryPolicyEvaluation(
                is_allowed=False,
                reason=f"Attempt {attempt_index} exceeds maximum attempts limit ({policy.maximum_attempts}).",
            )

        # 2. Prohibited operations rule
        if operation_id and operation_id in policy.prohibited_operations:
            return RetryPolicyEvaluation(
                is_allowed=False,
                reason=f"Operation '{operation_id}' is explicitly prohibited from retry.",
            )

        # 3. Non-retryable errors have PRECEDENCE
        for non_ret in policy.non_retryable_errors:
            if non_ret and (
                non_ret == error_type or non_ret.lower() in error_type.lower()
            ):
                return RetryPolicyEvaluation(
                    is_allowed=False,
                    reason=f"Error type '{error_type}' matches non-retryable policy rule '{non_ret}'.",
                )

        # 4. Allowed operations filter if non-empty
        if (
            policy.allowed_operations
            and operation_id
            and operation_id not in policy.allowed_operations
        ):
            return RetryPolicyEvaluation(
                is_allowed=False,
                reason=f"Operation '{operation_id}' is not in allowed_operations list.",
            )

        # 5. Retryable errors filter if non-empty
        if policy.retryable_errors:
            matched = any(
                r == error_type or r.lower() in error_type.lower()
                for r in policy.retryable_errors
                if r
            )
            if not matched:
                return RetryPolicyEvaluation(
                    is_allowed=False,
                    reason=f"Error type '{error_type}' is not in retryable_errors policy list.",
                )

        # 6. Check reobservation requirements
        reobs_req = False
        if policy.require_reobservation_after:
            reobs_req = any(
                r == error_type or r.lower() in error_type.lower()
                for r in policy.require_reobservation_after
                if r
            )

        return RetryPolicyEvaluation(
            is_allowed=True,
            reason="Retry allowed by policy.",
            reobservation_required=reobs_req,
        )


class RollbackPolicyEvaluator:
    """Evaluates RollbackPolicy rules against operation recovery properties and checkpoints."""

    def evaluate(
        self,
        policy: RollbackPolicy,
        operation_id: str,
        checkpoint_status: CheckpointStatus | None,
    ) -> RollbackPolicyEvaluation:
        """Evaluate if rollback is permissible for an operation and checkpoint state."""
        if checkpoint_status is None:
            return RollbackPolicyEvaluation(
                can_rollback=False,
                requires_approval=False,
                reason="No checkpoint available for rollback.",
            )

        if checkpoint_status not in policy.allowed_checkpoint_statuses:
            return RollbackPolicyEvaluation(
                can_rollback=False,
                requires_approval=False,
                reason=f"Checkpoint status '{checkpoint_status.value}' is not allowed for rollback.",
            )

        if operation_id in policy.prohibited_for:
            return RollbackPolicyEvaluation(
                can_rollback=False,
                requires_approval=False,
                reason=f"Rollback is prohibited for operation '{operation_id}'.",
            )

        req_approval = (
            operation_id in policy.approval_required_for
            or not policy.automatic_for
            or (policy.automatic_for and operation_id not in policy.automatic_for)
        )

        return RollbackPolicyEvaluation(
            can_rollback=True,
            requires_approval=req_approval,
            reason="Rollback allowed by policy.",
        )


class EscalationPolicyEvaluator:
    """Evaluates EscalationPolicy rules based on failure triggers and evidence."""

    def evaluate(
        self,
        policy: EscalationPolicy,
        reason_codes: Sequence[RecoveryReasonCode],
        has_evidence: bool = True,
    ) -> EscalationPolicyEvaluation:
        """Evaluate if escalation to human or operator is triggered."""
        reason_strs = [
            r.value if isinstance(r, RecoveryReasonCode) else str(r)
            for r in reason_codes
        ]

        triggered = False
        match_reason = ""
        for trigger in policy.triggers:
            if trigger in reason_strs or any(trigger in r for r in reason_strs):
                triggered = True
                match_reason = f"Trigger matched: {trigger}"
                break

        if not triggered and any(
            r
            in (
                RecoveryReasonCode.INCONSISTENT_STATE,
                RecoveryReasonCode.BUDGET_EXHAUSTED,
                RecoveryReasonCode.PERMISSION_MISSING,
                RecoveryReasonCode.POLICY_CONFLICT,
                RecoveryReasonCode.ROLLBACK_FAILED,
                RecoveryReasonCode.COMPENSATION_FAILED,
            )
            for r in reason_codes
        ):
            triggered = True
            match_reason = "Mandatory safety escalation trigger."

        return EscalationPolicyEvaluation(
            should_escalate=triggered,
            target=policy.escalation_target,
            reason=match_reason if triggered else "No escalation trigger activated.",
        )


class RecoveryPolicyResolver:
    """Aggregates policy evaluators for retry, rollback, replan, and escalation."""

    def __init__(
        self,
        retry_evaluator: RetryPolicyEvaluator | None = None,
        rollback_evaluator: RollbackPolicyEvaluator | None = None,
        escalation_evaluator: EscalationPolicyEvaluator | None = None,
    ) -> None:
        self.retry_evaluator = retry_evaluator or RetryPolicyEvaluator()
        self.rollback_evaluator = rollback_evaluator or RollbackPolicyEvaluator()
        self.escalation_evaluator = escalation_evaluator or EscalationPolicyEvaluator()

    def evaluate_retry(
        self,
        policy: RetryPolicy,
        attempt_index: int,
        error_type: str,
        operation_id: str = "",
    ) -> RetryPolicyEvaluation:
        return self.retry_evaluator.evaluate(
            policy, attempt_index, error_type, operation_id
        )

    def evaluate_rollback(
        self,
        policy: RollbackPolicy,
        operation_id: str,
        checkpoint_status: CheckpointStatus | None,
    ) -> RollbackPolicyEvaluation:
        return self.rollback_evaluator.evaluate(policy, operation_id, checkpoint_status)

    def evaluate_escalation(
        self,
        policy: EscalationPolicy,
        reason_codes: Sequence[RecoveryReasonCode],
        has_evidence: bool = True,
    ) -> EscalationPolicyEvaluation:
        return self.escalation_evaluator.evaluate(policy, reason_codes, has_evidence)
