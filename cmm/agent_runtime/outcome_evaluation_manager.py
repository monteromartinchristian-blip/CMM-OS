"""Phase 9.17 – Outcome Evaluation Manager.

Orchestrates evaluation and goal completion decisions with repository persistence,
idempotency guarantees, event publishing, and optional terminal Goal state transition delegation.
"""

from __future__ import annotations

import logging
from typing import Any

from cmm.agent_runtime.enums import (
    CriterionEvaluationStatus,
    GoalCompletionDecisionKind,
    GoalStatus,
)
from cmm.agent_runtime.errors import (
    GoalError,
    OutcomeEvaluationExecutionError,
)
from cmm.agent_runtime.goal_completion_decision_engine import (
    GoalCompletionDecisionEngine,
)
from cmm.agent_runtime.outcome_evaluation_contracts import (
    GoalCompletionDecision,
    OutcomeEvaluation,
    OutcomeEvaluationContext,
    OutcomeEvaluationRequest,
    OutcomeEvaluationResult,
)
from cmm.agent_runtime.outcome_evaluation_engine import OutcomeEvaluationEngine
from cmm.agent_runtime.outcome_evaluation_repository import (
    InMemoryOutcomeEvaluationRepository,
    OutcomeEvaluationRepository,
)

logger = logging.getLogger(__name__)


class OutcomeEvaluationManager:
    """Central orchestrator for Outcome Evaluation and Goal Completion Decisions."""

    def __init__(
        self,
        repository: OutcomeEvaluationRepository | None = None,
        evaluation_engine: OutcomeEvaluationEngine | None = None,
        decision_engine: GoalCompletionDecisionEngine | None = None,
        goal_manager: Any = None,
        event_bus: Any = None,
    ) -> None:
        self.repository = repository or InMemoryOutcomeEvaluationRepository()
        self.event_bus = event_bus
        self.goal_manager = goal_manager
        self.evaluation_engine = evaluation_engine or OutcomeEvaluationEngine(
            repository=self.repository, event_bus=self.event_bus
        )
        self.decision_engine = decision_engine or GoalCompletionDecisionEngine(
            event_bus=self.event_bus
        )

    def evaluate(
        self,
        context_or_request: OutcomeEvaluationContext | OutcomeEvaluationRequest,
        goal: Any = None,
        idempotency_key: str | None = None,
    ) -> OutcomeEvaluation:
        """Execute outcome evaluation and persist in repository."""
        eval_record = self.evaluation_engine.evaluate(
            context_or_request=context_or_request, goal=goal
        )
        self.repository.save_evaluation(eval_record, idempotency_key=idempotency_key)
        return eval_record

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
        idempotency_key: str | None = None,
    ) -> GoalCompletionDecision:
        """Issue goal completion decision and persist in repository."""
        decision = self.decision_engine.decide_completion(
            evaluation=evaluation,
            goal=goal,
            policies=policies,
            approvals=approvals,
            remaining_budget=remaining_budget,
            recovery_available=recovery_available,
            checkpoint_available=checkpoint_available,
            partial_completion_allowed=partial_completion_allowed,
        )
        self.repository.save_decision(decision, idempotency_key=idempotency_key)

        # Delegate terminal Goal transition to goal_manager if configured and decision is terminal
        if self.goal_manager:
            try:
                actor_id = "outcome-evaluation-manager"

                # Update evaluated criteria on Goal if evaluate_success_criteria is supported
                if hasattr(self.goal_manager, "evaluate_success_criteria"):
                    from cmm.agent_runtime.enums import SuccessCriterionStatus

                    eval_map = {}
                    for cr in evaluation.criterion_results:
                        st_val = (
                            SuccessCriterionStatus.SATISFIED
                            if cr.status == CriterionEvaluationStatus.SATISFIED
                            else SuccessCriterionStatus.WAIVED
                            if cr.status == CriterionEvaluationStatus.WAIVED
                            else SuccessCriterionStatus.UNSATISFIED
                        )
                        eval_map[cr.criterion_id] = (st_val, cr.actual_value)
                    if eval_map:
                        try:
                            self.goal_manager.evaluate_success_criteria(
                                decision.goal_id, eval_map, actor_id=actor_id
                            )
                        except GoalError as exc:
                            logger.warning(
                                "Goal success-criteria synchronization failed "
                                "for %s: %s",
                                decision.goal_id,
                                exc,
                            )

                if decision.decision == GoalCompletionDecisionKind.COMPLETE:
                    if hasattr(self.goal_manager, "complete_goal"):
                        self.goal_manager.complete_goal(
                            decision.goal_id,
                            actor_id=actor_id,
                            reason=f"Goal completed via evaluation {evaluation.outcome_evaluation_id}",
                        )
                    elif hasattr(self.goal_manager, "change_status"):
                        self.goal_manager.change_status(
                            decision.goal_id,
                            GoalStatus.COMPLETED,
                            actor_id=actor_id,
                            reason=f"Goal completed via evaluation {evaluation.outcome_evaluation_id}",
                        )
                elif decision.decision == GoalCompletionDecisionKind.COMPLETE_PARTIALLY:
                    if hasattr(self.goal_manager, "change_status"):
                        self.goal_manager.change_status(
                            decision.goal_id,
                            GoalStatus.PARTIALLY_COMPLETED,
                            actor_id=actor_id,
                            reason=f"Goal partially completed via evaluation {evaluation.outcome_evaluation_id}",
                        )
                elif decision.decision == GoalCompletionDecisionKind.FAIL and hasattr(
                    self.goal_manager, "change_status"
                ):
                    self.goal_manager.change_status(
                        decision.goal_id,
                        GoalStatus.FAILED,
                        actor_id=actor_id,
                        reason=f"Goal failed via evaluation {evaluation.outcome_evaluation_id}",
                    )
            except Exception as exc:
                raise OutcomeEvaluationExecutionError(
                    f"Failed to delegate Goal status update for goal {decision.goal_id}: {exc}"
                ) from exc

        return decision

    def evaluate_and_decide(
        self,
        context_or_request: OutcomeEvaluationContext | OutcomeEvaluationRequest,
        goal: Any = None,
        policies: tuple[Any, ...] = (),
        approvals: tuple[Any, ...] = (),
        remaining_budget: float | None = None,
        recovery_available: bool = False,
        checkpoint_available: bool = False,
        partial_completion_allowed: bool = False,
        idempotency_key: str | None = None,
    ) -> OutcomeEvaluationResult:
        """Compose evaluation and completion decision into unified OutcomeEvaluationResult."""
        evaluation = self.evaluate(
            context_or_request=context_or_request,
            goal=goal,
            idempotency_key=idempotency_key,
        )
        target_goal = goal
        if target_goal is None and isinstance(
            context_or_request, OutcomeEvaluationContext
        ):
            target_goal = context_or_request.goal

        decision_key = f"dec-key-{idempotency_key}" if idempotency_key else None
        decision = self.decide_completion(
            evaluation=evaluation,
            goal=target_goal,
            policies=policies,
            approvals=approvals,
            remaining_budget=remaining_budget,
            recovery_available=recovery_available,
            checkpoint_available=checkpoint_available,
            partial_completion_allowed=partial_completion_allowed,
            idempotency_key=decision_key,
        )

        return OutcomeEvaluationResult(
            evaluation=evaluation,
            decision=decision,
            metadata={"idempotency_key": idempotency_key} if idempotency_key else {},
        )
