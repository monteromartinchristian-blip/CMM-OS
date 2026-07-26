"""Phase 9.17 – Goal Completion Decision Engine.

Makes formal completion decisions (COMPLETE, COMPLETE_PARTIALLY, CONTINUE, RETRY, REPLAN,
ROLLBACK, PAUSE, ESCALATE, FAIL) by applying strict fail-safe precedence rules.

NOTE: GoalCompletionDecisionEngine ONLY computes and produces GoalCompletionDecision.
It DOES NOT mutate or update Goal status directly.
"""

from __future__ import annotations

import uuid
from typing import Any

from cmm.agent_runtime.enums import (
    CriterionEvaluationStatus,
    CriterionImportance,
    GoalCompletionDecisionKind,
    Outcome,
    OutcomeReasonCode,
)
from cmm.agent_runtime.errors import (
    GoalCompletionDecisionError,
)
from cmm.agent_runtime.outcome_evaluation_contracts import (
    GoalCompletionDecision,
    OutcomeEvaluation,
)


class GoalCompletionDecisionEngine:
    """Evaluates OutcomeEvaluation records against fail-safe rules to issue GoalCompletionDecision."""

    def __init__(self, event_bus: Any = None) -> None:
        self._event_bus = event_bus

    def _publish_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_bus and hasattr(self._event_bus, "publish"):
            try:
                self._event_bus.publish(event_type, payload)
            except Exception:
                pass

    def decide_completion(
        self,
        evaluation: OutcomeEvaluation,
        goal: Any = None,
        policies: tuple[Any, ...] = (),
        approvals: tuple[Any, ...] = (),
        remaining_budget: float | None = None,
        recovery_available: bool = False,
        checkpoint_available: bool = False,
        partial_completion_allowed: bool = False,
    ) -> GoalCompletionDecision:
        """Issue a formal GoalCompletionDecision applying strict fail-safe precedence."""
        if not isinstance(evaluation, OutcomeEvaluation):
            raise GoalCompletionDecisionError(
                f"Expected OutcomeEvaluation, got {type(evaluation).__name__}"
            )

        self._publish_event(
            "GOAL_COMPLETION_DECISION_REQUESTED",
            {
                "evaluation_id": evaluation.outcome_evaluation_id,
                "goal_id": evaluation.goal_id,
            },
        )

        satisfied: list[str] = []
        unsatisfied: list[str] = []
        waived: list[str] = []
        blocking: list[str] = []
        reason_codes: list[OutcomeReasonCode] = []

        for cr in evaluation.criterion_results:
            if cr.status == CriterionEvaluationStatus.SATISFIED:
                satisfied.append(cr.criterion_id)
            elif cr.status == CriterionEvaluationStatus.WAIVED:
                waived.append(cr.criterion_id)
            else:
                unsatisfied.append(cr.criterion_id)
                if cr.blocking or cr.importance == CriterionImportance.MANDATORY:
                    blocking.append(cr.criterion_id)

        # ── Fail-Safe Precedence Check ──────────────────────────────────────

        # Precedence 1: Inconsistent state or missing evaluation
        inconsistent_warnings = [
            w
            for w in evaluation.warnings
            if "inconsistent" in w.lower() or "version" in w.lower()
        ]
        if inconsistent_warnings:
            decision = GoalCompletionDecisionKind.PAUSE
            reason_codes.append(OutcomeReasonCode.INCONSISTENT_STATE)

        # Precedence 2: Critical regression detected
        elif any(r.severity == "critical" for r in evaluation.regressions):
            decision = (
                GoalCompletionDecisionKind.ROLLBACK
                if checkpoint_available
                else GoalCompletionDecisionKind.ESCALATE
            )
            reason_codes.append(OutcomeReasonCode.REGRESSION_DETECTED)

        # Precedence 3: Mandatory criterion unsatisfied
        elif blocking or any(
            cr.importance == CriterionImportance.MANDATORY
            and cr.status != CriterionEvaluationStatus.SATISFIED
            and cr.status != CriterionEvaluationStatus.WAIVED
            for cr in evaluation.criterion_results
        ):
            decision = (
                GoalCompletionDecisionKind.RETRY
                if recovery_available
                else GoalCompletionDecisionKind.REPLAN
                if evaluation.outcome == Outcome.NO_CHANGE
                else GoalCompletionDecisionKind.RETRY
                if evaluation.outcome == Outcome.FAILURE
                else GoalCompletionDecisionKind.FAIL
            )
            reason_codes.append(OutcomeReasonCode.MANDATORY_CRITERION_UNSATISFIED)

        # Precedence 4: Blocking validation failure
        elif evaluation.outcome == Outcome.FAILURE and not recovery_available:
            decision = GoalCompletionDecisionKind.FAIL
            reason_codes.append(OutcomeReasonCode.VALIDATION_FAILED)

        # Precedence 5: Evidence insufficient
        elif evaluation.outcome == Outcome.INCONCLUSIVE or evaluation.confidence < 0.5:
            decision = GoalCompletionDecisionKind.CONTINUE
            reason_codes.append(OutcomeReasonCode.EVIDENCE_INSUFFICIENT)

        # Precedence 6: User confirmation required but missing/unconfirmed
        elif evaluation.requires_user_confirmation:
            decision = GoalCompletionDecisionKind.PAUSE
            reason_codes.append(OutcomeReasonCode.USER_CONFIRMATION_REQUIRED)

        # Precedence 7: Critical unaccepted debt or unauthorized side effects
        elif any(
            d.severity == "critical" and not d.accepted
            for d in evaluation.generated_debt
        ):
            decision = GoalCompletionDecisionKind.ESCALATE
            reason_codes.append(OutcomeReasonCode.DEBT_GENERATED)

        # Precedence 8: Action budget exhausted
        elif remaining_budget is not None and remaining_budget <= 0:
            decision = GoalCompletionDecisionKind.FAIL
            reason_codes.append(OutcomeReasonCode.BUDGET_EXHAUSTED)

        # Precedence 9: Recovery viable
        elif (
            evaluation.outcome in (Outcome.FAILURE, Outcome.REGRESSION)
            and recovery_available
        ):
            decision = GoalCompletionDecisionKind.RETRY
            reason_codes.append(OutcomeReasonCode.RECOVERY_REQUIRED)

        # Precedence 10: Partial success
        elif evaluation.outcome == Outcome.PARTIAL_SUCCESS:
            if (
                partial_completion_allowed
                or goal
                and getattr(goal, "allow_partial", False)
            ):
                decision = GoalCompletionDecisionKind.COMPLETE_PARTIALLY
                reason_codes.append(OutcomeReasonCode.PARTIAL_PROGRESS)
            else:
                decision = GoalCompletionDecisionKind.CONTINUE
                reason_codes.append(OutcomeReasonCode.PARTIAL_PROGRESS)

        # Precedence 11: All mandatory criteria satisfied -> COMPLETE
        elif evaluation.outcome == Outcome.SUCCESS:
            decision = GoalCompletionDecisionKind.COMPLETE
            reason_codes.append(OutcomeReasonCode.ALL_MANDATORY_CRITERIA_SATISFIED)

        else:
            decision = GoalCompletionDecisionKind.CONTINUE
            reason_codes.append(OutcomeReasonCode.UNKNOWN_OUTCOME)

        # Calculate residual risk
        residual_risk = 0.0
        if evaluation.risks:
            risk_weights = {"low": 0.1, "medium": 0.3, "high": 0.6, "critical": 1.0}
            residual_risk = min(
                1.0,
                sum(risk_weights.get(r.level, 0.2) for r in evaluation.risks)
                / (len(evaluation.risks) or 1),
            )

        dec_record = GoalCompletionDecision(
            completion_decision_id=f"dec-{uuid.uuid4().hex[:12]}",
            outcome_evaluation_id=evaluation.outcome_evaluation_id,
            goal_id=evaluation.goal_id,
            decision=decision,
            satisfied_criteria=tuple(satisfied),
            unsatisfied_criteria=tuple(unsatisfied),
            waived_criteria=tuple(waived),
            blocking_criteria=tuple(blocking),
            evidence=evaluation.evidence,
            confidence=evaluation.confidence,
            requires_user_confirmation=evaluation.requires_user_confirmation,
            reason_codes=tuple(reason_codes),
            residual_risk=residual_risk,
            metadata={
                "eval_outcome": evaluation.outcome.value,
                "recovery_available": recovery_available,
            },
        )

        # Emit decision made event and target decision event
        self._publish_event("GOAL_COMPLETION_DECISION_MADE", dec_record.to_dict())

        event_map = {
            GoalCompletionDecisionKind.COMPLETE: "GOAL_COMPLETED",
            GoalCompletionDecisionKind.COMPLETE_PARTIALLY: "GOAL_COMPLETED_PARTIALLY",
            GoalCompletionDecisionKind.CONTINUE: "GOAL_CONTINUATION_REQUESTED",
            GoalCompletionDecisionKind.RETRY: "GOAL_RETRY_REQUESTED",
            GoalCompletionDecisionKind.REPLAN: "GOAL_REPLAN_REQUESTED",
            GoalCompletionDecisionKind.ROLLBACK: "GOAL_ROLLBACK_REQUESTED",
            GoalCompletionDecisionKind.PAUSE: "GOAL_CONFIRMATION_REQUESTED",
            GoalCompletionDecisionKind.ESCALATE: "GOAL_ESCALATED",
            GoalCompletionDecisionKind.FAIL: "GOAL_FAILED",
        }
        target_evt = event_map.get(decision)
        if target_evt:
            self._publish_event(target_evt, dec_record.to_dict())

        return dec_record
