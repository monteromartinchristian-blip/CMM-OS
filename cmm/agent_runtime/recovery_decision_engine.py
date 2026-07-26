"""Phase 9.16 – Recovery Decision Engine.

Evaluates failure classifications, recovery policies, budget constraints, checkpoint integrity,
and precedence rules to deterministically select the safest recovery strategy.
"""

from __future__ import annotations

import uuid
from typing import Any

from cmm.agent_runtime.checkpoint_integrity import CheckpointIntegrityVerifier
from cmm.agent_runtime.enums import (
    CheckpointIntegrityStatus,
    CheckpointStatus,
    RecoveryErrorClass,
    RecoveryReasonCode,
    RecoveryStrategy,
)
from cmm.agent_runtime.recovery_backoff import RecoveryBackoffCalculator
from cmm.agent_runtime.recovery_contracts import (
    EscalationPolicy,
    RecoveryContext,
    RecoveryDecision,
    ReplanPolicy,
    RetryPolicy,
    RollbackPolicy,
)
from cmm.agent_runtime.recovery_error_classifier import ErrorClassification
from cmm.agent_runtime.recovery_policy import RecoveryPolicyResolver


class RecoveryDecisionEngine:
    """Deterministic engine selecting the highest-precedence safe recovery strategy."""

    def __init__(
        self,
        policy_resolver: RecoveryPolicyResolver | None = None,
        backoff_calculator: RecoveryBackoffCalculator | None = None,
        checkpoint_verifier: CheckpointIntegrityVerifier | None = None,
    ) -> None:
        self.policy_resolver = policy_resolver or RecoveryPolicyResolver()
        self.backoff_calculator = backoff_calculator or RecoveryBackoffCalculator()
        self.checkpoint_verifier = checkpoint_verifier or CheckpointIntegrityVerifier()

    def make_decision(
        self,
        context: RecoveryContext,
        classification: ErrorClassification,
        retry_policy: RetryPolicy | None = None,
        replan_policy: ReplanPolicy | None = None,
        rollback_policy: RollbackPolicy | None = None,
        escalation_policy: EscalationPolicy | None = None,
        checkpoint_obj: Any | None = None,
    ) -> RecoveryDecision:
        """Deterministically determine the recovery strategy to execute."""
        r_policy = retry_policy or RetryPolicy()
        rep_policy = replan_policy or ReplanPolicy()
        roll_policy = rollback_policy or RollbackPolicy()
        _ = escalation_policy or EscalationPolicy()

        reason_codes: list[RecoveryReasonCode] = list(classification.reason_codes)
        selected_strategy = RecoveryStrategy.FAIL
        checkpoint_id: str | None = None
        delay_seconds: float | None = None
        requires_approval = classification.requires_approval
        confidence = 1.0
        modified_params: dict[str, Any] = {}

        attempt_count = len(context.retry_history) + 1
        error_type = (
            context.error.get("error_type", "")
            if isinstance(context.error, dict)
            else str(context.error)
        )
        op_id = context.failed_operation_id

        # Evaluate retry policy
        retry_eval = self.policy_resolver.evaluate_retry(
            r_policy, attempt_count, error_type, op_id
        )

        # ── Precedence Rule 1: Inconsistent state / corrupted checkpoints ──────
        if (
            classification.error_class == RecoveryErrorClass.INCONSISTENT_STATE
            or RecoveryReasonCode.INCONSISTENT_STATE in reason_codes
        ):
            selected_strategy = RecoveryStrategy.ESCALATE
            requires_approval = True
            if RecoveryReasonCode.INCONSISTENT_STATE not in reason_codes:
                reason_codes.append(RecoveryReasonCode.INCONSISTENT_STATE)

        # ── Precedence Rule 2: Irreversible side effect / critical damage ─────
        elif (
            classification.severity == "critical"
            and classification.evidence.side_effects
            and any(
                isinstance(se, dict) and se.get("reversibility") == "irreversible"
                for se in classification.evidence.side_effects
            )
        ):
            selected_strategy = RecoveryStrategy.ESCALATE
            requires_approval = True
            if RecoveryReasonCode.PARTIAL_SIDE_EFFECTS not in reason_codes:
                reason_codes.append(RecoveryReasonCode.PARTIAL_SIDE_EFFECTS)

        # ── Precedence Rule 3: Permission or approval missing ─────────────────
        elif (
            classification.error_class == RecoveryErrorClass.PERMISSION
            or classification.requires_approval
        ):
            selected_strategy = RecoveryStrategy.REQUEST_APPROVAL
            requires_approval = True
            if RecoveryReasonCode.APPROVAL_REQUIRED not in reason_codes:
                reason_codes.append(RecoveryReasonCode.APPROVAL_REQUIRED)

        # ── Precedence Rule 4: Rollback or Compensation failure ────────────────
        elif (
            RecoveryReasonCode.ROLLBACK_FAILED in reason_codes
            or RecoveryReasonCode.COMPENSATION_FAILED in reason_codes
        ):
            selected_strategy = RecoveryStrategy.ESCALATE
            if RecoveryReasonCode.HIGH_IMPACT_DECISION not in reason_codes:
                reason_codes.append(RecoveryReasonCode.HIGH_IMPACT_DECISION)

        # ── Precedence Rule 5: Budget exhausted ────────────────────────────────
        elif (
            classification.error_class == RecoveryErrorClass.BUDGET
            or RecoveryReasonCode.BUDGET_EXHAUSTED in reason_codes
        ):
            selected_strategy = RecoveryStrategy.ESCALATE
            if RecoveryReasonCode.BUDGET_EXHAUSTED not in reason_codes:
                reason_codes.append(RecoveryReasonCode.BUDGET_EXHAUSTED)

        # ── Precedence Rule 6: Retries exhausted ──────────────────────────────
        elif attempt_count > r_policy.maximum_attempts or not retry_eval.is_allowed:
            if RecoveryReasonCode.RETRIES_EXHAUSTED not in reason_codes:
                reason_codes.append(RecoveryReasonCode.RETRIES_EXHAUSTED)

            # Check if Rollback is available and INTEGRITY IS VALID
            if context.checkpoint_ids and roll_policy:
                cand_checkpoint_id = context.checkpoint_ids[-1]

                # REAL Checkpoint Integrity Check
                cp_valid = True
                if checkpoint_obj is not None:
                    integrity = self.checkpoint_verifier.verify(checkpoint_obj)
                    if (
                        not integrity.is_valid
                        or integrity.status != CheckpointIntegrityStatus.VALID
                    ):
                        cp_valid = False
                elif context.metadata and context.metadata.get(
                    "checkpoint_integrity_status"
                ):
                    cp_stat = context.metadata.get("checkpoint_integrity_status")
                    if (
                        cp_stat != "valid"
                        and cp_stat != CheckpointIntegrityStatus.VALID
                    ):
                        cp_valid = False

                if cp_valid:
                    roll_eval = self.policy_resolver.evaluate_rollback(
                        roll_policy, op_id, CheckpointStatus.ACTIVE
                    )
                    if roll_eval.can_rollback:
                        selected_strategy = RecoveryStrategy.ROLLBACK
                        checkpoint_id = cand_checkpoint_id
                        requires_approval = roll_eval.requires_approval
                    elif rep_policy.allow_replan:
                        selected_strategy = RecoveryStrategy.REPLAN
                    else:
                        selected_strategy = RecoveryStrategy.ESCALATE
                else:
                    if RecoveryReasonCode.CHECKPOINT_INVALID not in reason_codes:
                        reason_codes.append(RecoveryReasonCode.CHECKPOINT_INVALID)
                    if rep_policy.allow_replan:
                        selected_strategy = RecoveryStrategy.REPLAN
                    else:
                        selected_strategy = RecoveryStrategy.ESCALATE
            elif rep_policy.allow_replan:
                selected_strategy = RecoveryStrategy.REPLAN
            else:
                selected_strategy = RecoveryStrategy.ESCALATE

        # ── Precedence Rule 7: Reobservation required ─────────────────────────
        elif retry_eval.reobservation_required or classification.requires_reobservation:
            selected_strategy = RecoveryStrategy.REOBSERVE
            if RecoveryReasonCode.RESOURCE_STALE not in reason_codes:
                reason_codes.append(RecoveryReasonCode.RESOURCE_STALE)

        # ── Precedence Rule 8: Rerun Validation ───────────────────────────────
        elif classification.requires_validation:
            selected_strategy = RecoveryStrategy.RERUN_VALIDATION

        # ── Precedence Rule 9: Standard Retry or Retry with Modified Parameters
        elif classification.retryable and retry_eval.is_allowed:
            sug_params = (
                context.metadata.get("suggested_modified_parameters")
                if context.metadata
                else None
            )
            # Safety checks for RetryWithModifiedParameters:
            # Must NOT expand scope, weaken criteria, elevate permissions, or reduce constraints
            expand_scope = (
                bool(context.metadata.get("expand_scope", False))
                if context.metadata
                else False
            )
            weaken_criteria = (
                bool(context.metadata.get("weaken_criteria", False))
                if context.metadata
                else False
            )
            elevate_perms = (
                bool(context.metadata.get("elevate_permissions", False))
                if context.metadata
                else False
            )

            from types import MappingProxyType

            if (
                sug_params
                and isinstance(sug_params, (dict, MappingProxyType))
                and not (expand_scope or weaken_criteria or elevate_perms)
            ):
                selected_strategy = RecoveryStrategy.RETRY_WITH_MODIFIED_PARAMETERS
                modified_params = dict(sug_params)
            else:
                selected_strategy = RecoveryStrategy.RETRY

            delay_seconds = self.backoff_calculator.calculate_delay(
                r_policy, attempt_count
            )

        # ── Precedence Rule 10: Fallback to Replan or Fail ────────────────────
        elif rep_policy.allow_replan:
            selected_strategy = RecoveryStrategy.REPLAN
        else:
            selected_strategy = RecoveryStrategy.FAIL

        # Build decision object
        decision_id = f"rec-dec-{uuid.uuid4().hex[:12]}"
        idempotency_key = f"dec-{context.recovery_context_id}-{selected_strategy.value}-{attempt_count}"

        return RecoveryDecision(
            recovery_decision_id=decision_id,
            recovery_context_id=context.recovery_context_id,
            strategy=selected_strategy,
            reason_codes=tuple(reason_codes),
            confidence=confidence,
            requires_approval=requires_approval,
            checkpoint_id=checkpoint_id,
            delay_seconds=delay_seconds,
            modified_parameters=modified_params,
            idempotency_key=idempotency_key,
        )
