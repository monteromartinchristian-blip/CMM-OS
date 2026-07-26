"""Phase 9.17 – Outcome Evaluation Engine.

Orchestrates multi-stage outcome evaluation across criterion evaluators, metrics,
state comparators, regression detectors, impact analyzers, and knowledge analyzers.
"""

from __future__ import annotations

import uuid
from typing import Any

from cmm.agent_runtime.enums import (
    CriterionEvaluationStatus,
    CriterionImportance,
    GoalCompletionDecisionKind,
    Outcome,
    OutcomeEvaluationStatus,
)
from cmm.agent_runtime.errors import (
    OutcomeEvaluationContextError,
    OutcomeEvaluationExecutionError,
)
from cmm.agent_runtime.outcome_criterion_evaluator import OutcomeCriterionEvaluator
from cmm.agent_runtime.outcome_evaluation_contracts import (
    OutcomeCriterionResult,
    OutcomeEvaluation,
    OutcomeEvaluationContext,
    OutcomeEvaluationRequest,
)
from cmm.agent_runtime.outcome_evaluation_repository import (
    OutcomeEvaluationRepository,
)
from cmm.agent_runtime.outcome_impact_analyzer import OutcomeImpactAnalyzer
from cmm.agent_runtime.outcome_knowledge_analyzer import OutcomeKnowledgeAnalyzer
from cmm.agent_runtime.outcome_metrics import OutcomeMetricEvaluator
from cmm.agent_runtime.outcome_regression_detector import OutcomeRegressionDetector
from cmm.agent_runtime.outcome_state_comparator import OutcomeStateComparator


class OutcomeEvaluationEngine:
    """Core evaluation engine evaluating whether execution results satisfy Goal requirements."""

    def __init__(
        self,
        repository: OutcomeEvaluationRepository | None = None,
        event_bus: Any = None,
        criterion_evaluator: OutcomeCriterionEvaluator | None = None,
        state_comparator: OutcomeStateComparator | None = None,
        metric_evaluator: OutcomeMetricEvaluator | None = None,
        regression_detector: OutcomeRegressionDetector | None = None,
        impact_analyzer: OutcomeImpactAnalyzer | None = None,
        knowledge_analyzer: OutcomeKnowledgeAnalyzer | None = None,
    ) -> None:
        self._repository = repository
        self._event_bus = event_bus
        self._criterion_evaluator = criterion_evaluator or OutcomeCriterionEvaluator(
            event_bus=event_bus
        )
        self._state_comparator = state_comparator or OutcomeStateComparator()
        self._metric_evaluator = metric_evaluator or OutcomeMetricEvaluator(
            event_bus=event_bus
        )
        self._regression_detector = regression_detector or OutcomeRegressionDetector(
            event_bus=event_bus
        )
        self._impact_analyzer = impact_analyzer or OutcomeImpactAnalyzer(
            event_bus=event_bus
        )
        self._knowledge_analyzer = knowledge_analyzer or OutcomeKnowledgeAnalyzer(
            event_bus=event_bus
        )

    def _publish_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_bus and hasattr(self._event_bus, "publish"):
            try:
                self._event_bus.publish(event_type, payload)
            except Exception:
                pass

    def evaluate(
        self,
        context_or_request: OutcomeEvaluationContext | OutcomeEvaluationRequest,
        goal: Any = None,
    ) -> OutcomeEvaluation:
        """Execute comprehensive evaluation for a Goal."""
        if isinstance(context_or_request, OutcomeEvaluationContext):
            context = context_or_request
        elif isinstance(context_or_request, OutcomeEvaluationRequest):
            if goal is None:
                raise OutcomeEvaluationContextError(
                    "goal must be provided when passing an OutcomeEvaluationRequest"
                )
            context = OutcomeEvaluationContext(
                goal=goal,
                request=context_or_request,
                evaluation_id=f"eval-{uuid.uuid4().hex[:12]}",
            )
        else:
            raise OutcomeEvaluationContextError(
                f"Invalid context_or_request type: {type(context_or_request).__name__}"
            )

        req = context.request
        target_goal = context.goal

        self._publish_event(
            "OUTCOME_EVALUATION_REQUESTED",
            {
                "evaluation_id": context.evaluation_id,
                "goal_id": req.goal_id,
                "agent_run_id": req.agent_run_id,
            },
        )
        self._publish_event(
            "OUTCOME_EVALUATION_STARTED",
            {
                "evaluation_id": context.evaluation_id,
                "goal_id": req.goal_id,
                "agent_run_id": req.agent_run_id,
            },
        )

        try:
            # 1. State comparison
            diff = self._state_comparator.compare_states(
                expected_state=req.expected_state,
                actual_state=req.actual_state,
                previous_state=req.previous_state,
            )

            # 2. Evaluate metrics
            metric_results = []
            for m in req.metrics:
                m_res = self._metric_evaluator.evaluate_metric(
                    metric_id=m.get("metric_id", f"m-{uuid.uuid4().hex[:6]}"),
                    name=m.get("name", "metric"),
                    expected=m.get("expected"),
                    actual=m.get("actual"),
                    comparator=m.get("comparator", "exact"),
                    evidence_ids=tuple(m.get("evidence_ids", [])),
                    metadata=m.get("metadata", {}),
                )
                metric_results.append(m_res)

            # 3. Evaluate criteria
            criteria_results: list[OutcomeCriterionResult] = []
            goal_criteria = getattr(
                target_goal,
                "success_criteria",
                getattr(target_goal, "criteria", ()),
            )
            for crit in goal_criteria:
                c_res = self._criterion_evaluator.evaluate_criterion(
                    criterion=crit,
                    expected_state=req.expected_state,
                    actual_state=req.actual_state,
                    validations=req.validations,
                    metrics=tuple(metric_results),
                    evidence=req.evidence,
                    user_confirmation=req.user_confirmation,
                )
                criteria_results.append(c_res)

            # 4. Detect regressions
            regressions = self._regression_detector.detect_regressions(
                diff=diff,
                validations=req.validations,
                evidence=req.evidence,
            )

            # 5. Analyze impact (side effects, debt, risks)
            side_effects, generated_debt, risks = self._impact_analyzer.analyze_impact(
                diff=diff,
                operation_results=req.operation_results,
                evidence=req.evidence,
            )

            # 6. Analyze knowledge acquisition and remaining gaps
            (
                acquired_knowledge,
                remaining_gaps,
                remaining_tasks,
            ) = self._knowledge_analyzer.analyze_knowledge_and_gaps(
                operation_results=req.operation_results,
                evidence=req.evidence,
            )

            # Collect warnings and validation IDs
            warnings = []
            val_ids = []
            for val in req.validations:
                v_id = getattr(val, "validation_id", getattr(val, "id", ""))
                if v_id:
                    val_ids.append(str(v_id))
            for cr in criteria_results:
                warnings.extend(cr.warnings)

            # 7. Determine overall Outcome & Confidence
            has_cancelled = req.metadata.get("cancelled", False)
            has_critical_regression = any(r.severity == "critical" for r in regressions)
            has_mandatory_unsatisfied = any(
                cr.importance == CriterionImportance.MANDATORY
                and cr.status != CriterionEvaluationStatus.SATISFIED
                and cr.status != CriterionEvaluationStatus.WAIVED
                for cr in criteria_results
            )
            has_required_unsatisfied = any(
                cr.importance == CriterionImportance.REQUIRED
                and cr.status != CriterionEvaluationStatus.SATISFIED
                and cr.status != CriterionEvaluationStatus.WAIVED
                for cr in criteria_results
            )
            has_inconclusive = any(
                cr.status
                in (
                    CriterionEvaluationStatus.INCONCLUSIVE,
                    CriterionEvaluationStatus.NOT_EVALUATED,
                )
                for cr in criteria_results
            )

            validation_failed = any(
                not getattr(
                    v,
                    "is_success",
                    getattr(v, "success", getattr(v, "passed", True)),
                )
                for v in req.validations
            )

            # Determine Outcome enum value
            if has_cancelled:
                outcome = Outcome.CANCELLED
                recommended_decision = GoalCompletionDecisionKind.FAIL
                confidence = 1.0

            elif has_critical_regression:
                outcome = Outcome.REGRESSION
                recommended_decision = GoalCompletionDecisionKind.ROLLBACK
                confidence = 0.9

            elif has_mandatory_unsatisfied or validation_failed:
                if diff.is_noop and not req.operation_results:
                    outcome = Outcome.NO_CHANGE
                    recommended_decision = GoalCompletionDecisionKind.REPLAN
                    confidence = 0.8
                elif has_inconclusive:
                    outcome = Outcome.INCONCLUSIVE
                    recommended_decision = GoalCompletionDecisionKind.CONTINUE
                    confidence = 0.5
                else:
                    outcome = Outcome.FAILURE
                    recommended_decision = GoalCompletionDecisionKind.RETRY
                    confidence = 0.9

            elif has_required_unsatisfied or remaining_gaps or remaining_tasks:
                outcome = Outcome.PARTIAL_SUCCESS
                recommended_decision = GoalCompletionDecisionKind.CONTINUE
                confidence = 0.85

            elif diff.is_noop and not criteria_results:
                outcome = Outcome.NO_CHANGE
                recommended_decision = GoalCompletionDecisionKind.REPLAN
                confidence = 0.8

            else:
                outcome = Outcome.SUCCESS
                recommended_decision = GoalCompletionDecisionKind.COMPLETE
                confidence = 0.95

            # User confirmation requirement check
            requires_user_confirmation = False
            if (
                req.user_confirmation is not None
                and req.user_confirmation.status != "confirmed"
            ) or target_goal.metadata.get("requires_user_confirmation"):
                requires_user_confirmation = True

            evaluation = OutcomeEvaluation(
                outcome_evaluation_id=context.evaluation_id,
                goal_id=req.goal_id,
                agent_run_id=req.agent_run_id,
                workflow_id=req.workflow_id,
                iteration_id=req.iteration_id,
                status=OutcomeEvaluationStatus.COMPLETED,
                outcome=outcome,
                criterion_results=tuple(criteria_results),
                expected_state=req.expected_state,
                actual_state=req.actual_state,
                validation_result_ids=tuple(val_ids),
                evidence=req.evidence,
                side_effects=side_effects,
                regressions=regressions,
                generated_debt=generated_debt,
                acquired_knowledge=acquired_knowledge,
                remaining_gaps=remaining_gaps,
                remaining_tasks=remaining_tasks,
                risks=risks,
                warnings=tuple(warnings),
                confidence=confidence,
                recommended_decision=recommended_decision,
                requires_user_confirmation=requires_user_confirmation,
                metadata=dict(req.metadata),
            )

            # Persist if repository configured
            if self._repository:
                self._repository.save_evaluation(evaluation)

            # Emit events
            if outcome == Outcome.INCONCLUSIVE:
                self._publish_event(
                    "OUTCOME_EVALUATION_INCONCLUSIVE", evaluation.to_dict()
                )
            elif outcome == Outcome.FAILURE:
                self._publish_event("OUTCOME_EVALUATION_FAILED", evaluation.to_dict())

            self._publish_event("OUTCOME_EVALUATION_COMPLETED", evaluation.to_dict())

            return evaluation

        except Exception as exc:
            self._publish_event(
                "OUTCOME_EVALUATION_FAILED",
                {
                    "evaluation_id": context.evaluation_id,
                    "goal_id": req.goal_id,
                    "error": str(exc),
                },
            )
            if not isinstance(
                exc, (OutcomeEvaluationContextError, GoalCompletionDecisionKind)
            ):
                raise OutcomeEvaluationExecutionError(
                    f"Outcome evaluation failed for goal {req.goal_id!r}: {exc}"
                ) from exc
            raise
