"""Phase 9.16 – Recovery Error Classifier.

Analyzes agent runtime errors, validation results, side effects, checkpoint integrity,
and execution history to produce structured error classifications.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cmm.agent_runtime.enums import (
    RecoveryErrorClass,
    RecoveryReasonCode,
)
from cmm.agent_runtime.errors import (
    ApprovalError,
    BudgetExhaustedError,
    CheckpointIntegrityError,
    CheckpointInvalidError,
    IrreversibleOperationError,
    ObservationPermissionError,
    ResourceVersionMismatchError,
    TransactionRollbackError,
)
from cmm.agent_runtime.recovery_contracts import (
    RecoveryContext,
    RecoveryEvidence,
)


@dataclass(frozen=True)
class ErrorClassification:
    """Structured result of error analysis and classification."""

    error_class: RecoveryErrorClass
    retryable: bool
    reason_codes: tuple[RecoveryReasonCode, ...]
    severity: str  # "low", "medium", "high", "critical"
    requires_reobservation: bool
    requires_validation: bool
    requires_approval: bool
    rollback_candidate: bool
    compensation_candidate: bool
    escalation_recommended: bool
    evidence: RecoveryEvidence
    metadata: dict[str, Any] = field(default_factory=dict)


class RecoveryErrorClassifier:
    """Classifier evaluating failures to determine recovery eligibility and candidate strategies."""

    def classify(
        self,
        context: RecoveryContext,
        exc: Exception | None = None,
    ) -> ErrorClassification:
        """Classify a failure represented by a RecoveryContext and optional Exception instance."""
        error_dict = context.error
        error_type = (
            error_dict.get("error_type", "")
            if isinstance(error_dict, dict)
            else str(error_dict)
        )
        error_msg = (
            error_dict.get("message", "") if isinstance(error_dict, dict) else ""
        )

        reason_codes: list[RecoveryReasonCode] = []
        error_class = RecoveryErrorClass.UNKNOWN
        retryable = False
        severity = "medium"
        requires_reobservation = False
        requires_validation = False
        requires_approval = False
        rollback_candidate = False
        compensation_candidate = False
        escalation_recommended = False

        # 1. Analyze exception type & hierarchy if available
        if exc is not None:
            if isinstance(exc, BudgetExhaustedError):
                error_class = RecoveryErrorClass.BUDGET
                reason_codes.append(RecoveryReasonCode.BUDGET_EXHAUSTED)
                severity = "high"
                escalation_recommended = True
            elif isinstance(exc, (ObservationPermissionError, ApprovalError)):
                error_class = RecoveryErrorClass.PERMISSION
                reason_codes.append(RecoveryReasonCode.PERMISSION_MISSING)
                severity = "high"
                requires_approval = True
                escalation_recommended = True
            elif isinstance(
                exc,
                (
                    CheckpointIntegrityError,
                    CheckpointInvalidError,
                    ResourceVersionMismatchError,
                ),
            ):
                error_class = RecoveryErrorClass.RESOURCE
                reason_codes.append(RecoveryReasonCode.RESOURCE_VERSION_MISMATCH)
                severity = "high"
                rollback_candidate = True
                requires_reobservation = True
            elif isinstance(exc, IrreversibleOperationError):
                error_class = RecoveryErrorClass.EXTERNAL_SIDE_EFFECT
                reason_codes.append(RecoveryReasonCode.PARTIAL_SIDE_EFFECTS)
                severity = "critical"
                escalation_recommended = True
            elif isinstance(exc, TransactionRollbackError):
                error_class = RecoveryErrorClass.INCONSISTENT_STATE
                reason_codes.append(RecoveryReasonCode.ROLLBACK_FAILED)
                severity = "critical"
                escalation_recommended = True
            elif (
                isinstance(exc, TimeoutError)
                or "transient" in error_type.lower()
                or "timeout" in error_type.lower()
            ):
                error_class = RecoveryErrorClass.TRANSIENT
                reason_codes.append(RecoveryReasonCode.TRANSIENT_ERROR)
                retryable = True
                severity = "low"
            elif isinstance(exc, ValueError) or "validation" in error_type.lower():
                error_class = RecoveryErrorClass.VALIDATION
                reason_codes.append(RecoveryReasonCode.VALIDATION_FAILED)
                requires_validation = True
                severity = "medium"
        else:
            # Analyze string / dictionary error payload
            err_class_raw = (
                error_dict.get("error_class", "")
                if isinstance(error_dict, dict)
                else ""
            )
            if err_class_raw and isinstance(err_class_raw, str):
                try:
                    error_class = RecoveryErrorClass(err_class_raw)
                except ValueError:
                    error_class = RecoveryErrorClass.UNKNOWN

            if (
                "transient" in error_type.lower()
                or "timeout" in error_type.lower()
                or "connection" in error_msg.lower()
            ):
                if error_class == RecoveryErrorClass.UNKNOWN:
                    error_class = RecoveryErrorClass.TRANSIENT
                reason_codes.append(RecoveryReasonCode.TRANSIENT_ERROR)
                retryable = True
            elif (
                "validation" in error_type.lower() or "validation" in error_msg.lower()
            ):
                if error_class == RecoveryErrorClass.UNKNOWN:
                    error_class = RecoveryErrorClass.VALIDATION
                reason_codes.append(RecoveryReasonCode.VALIDATION_FAILED)
                requires_validation = True
            elif "permission" in error_type.lower() or "approval" in error_type.lower():
                if error_class == RecoveryErrorClass.UNKNOWN:
                    error_class = RecoveryErrorClass.PERMISSION
                reason_codes.append(RecoveryReasonCode.PERMISSION_MISSING)
                requires_approval = True
                escalation_recommended = True
            elif "budget" in error_type.lower() or "budget" in error_msg.lower():
                if error_class == RecoveryErrorClass.UNKNOWN:
                    error_class = RecoveryErrorClass.BUDGET
                reason_codes.append(RecoveryReasonCode.BUDGET_EXHAUSTED)
                escalation_recommended = True

        # 2. Check retry history (if maximum attempts reached, not retryable)
        attempt_count = len(context.retry_history)
        max_attempts = (
            context.constraints[0].get("maximum_attempts", 3)
            if context.constraints and isinstance(context.constraints[0], dict)
            else 3
        )
        if attempt_count >= max_attempts:
            retryable = False
            if RecoveryReasonCode.RETRIES_EXHAUSTED not in reason_codes:
                reason_codes.append(RecoveryReasonCode.RETRIES_EXHAUSTED)

        # 3. Check checkpoint availability & state integrity
        if context.checkpoint_ids:
            rollback_candidate = True
            if RecoveryReasonCode.CHECKPOINT_AVAILABLE not in reason_codes:
                reason_codes.append(RecoveryReasonCode.CHECKPOINT_AVAILABLE)

        # 4. Check side effects and partial changes
        if context.side_effects or context.partial_changes:
            if RecoveryReasonCode.PARTIAL_SIDE_EFFECTS not in reason_codes:
                reason_codes.append(RecoveryReasonCode.PARTIAL_SIDE_EFFECTS)
            has_irreversible = any(
                isinstance(se, dict) and se.get("reversibility") == "irreversible"
                for se in context.side_effects
            )
            if has_irreversible:
                severity = "critical"
                escalation_recommended = True

        # 5. Check budget remaining
        remaining_op = context.remaining_budget.get("operations_remaining", 1)
        if remaining_op <= 0:
            retryable = False
            if RecoveryReasonCode.BUDGET_EXHAUSTED not in reason_codes:
                reason_codes.append(RecoveryReasonCode.BUDGET_EXHAUSTED)

        # 6. Unknown is NOT retryable automatically
        if error_class == RecoveryErrorClass.UNKNOWN:
            if RecoveryReasonCode.UNKNOWN_FAILURE not in reason_codes:
                reason_codes.append(RecoveryReasonCode.UNKNOWN_FAILURE)
            retryable = False

        # Build evidence bundle
        evidence = RecoveryEvidence(
            evidence_id=f"evid-{context.recovery_context_id}",
            recovery_context_id=context.recovery_context_id,
            error_summary=f"[{error_class.value}] {error_type}: {error_msg}",
            logs=(error_msg,) if error_msg else (),
            validation_results=tuple(
                {"validation_result_id": result_id}
                for result_id in context.validation_result_ids
            ),
            checkpoint_ids=context.checkpoint_ids,
            side_effects=context.side_effects,
        )

        return ErrorClassification(
            error_class=error_class,
            retryable=retryable,
            reason_codes=tuple(reason_codes),
            severity=severity,
            requires_reobservation=requires_reobservation,
            requires_validation=requires_validation,
            requires_approval=requires_approval,
            rollback_candidate=rollback_candidate,
            compensation_candidate=compensation_candidate,
            escalation_recommended=escalation_recommended,
            evidence=evidence,
            metadata={"attempt_count": attempt_count},
        )
