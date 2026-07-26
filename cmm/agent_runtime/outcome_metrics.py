"""Phase 9.17 – Outcome Metric Evaluator.

Evaluates metric targets (exact, min, max, range, percentage, boolean, count,
duration, cost, custom registered evaluators) without dynamic code execution.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from cmm.agent_runtime.enums import CriterionEvaluationStatus
from cmm.agent_runtime.errors import OutcomeMetricError
from cmm.agent_runtime.outcome_evaluation_contracts import OutcomeMetricResult


class OutcomeMetricEvaluator:
    """Evaluates quantitative metrics against expected targets using type-safe comparators."""

    def __init__(self, event_bus: Any = None) -> None:
        self._event_bus = event_bus
        self._custom_evaluators: dict[str, Callable[[Any, Any], bool]] = {}

    def register_custom_evaluator(
        self, name: str, evaluator: Callable[[Any, Any], bool]
    ) -> None:
        """Register a custom metric evaluator function."""
        if not callable(evaluator):
            raise OutcomeMetricError("Custom evaluator must be a callable")
        self._custom_evaluators[name] = evaluator

    def _publish_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_bus and hasattr(self._event_bus, "publish"):
            try:
                self._event_bus.publish(event_type, payload)
            except Exception:
                pass

    def evaluate_metric(
        self,
        metric_id: str,
        name: str,
        expected: Any,
        actual: Any,
        comparator: str,
        evidence_ids: tuple[str, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> OutcomeMetricResult:
        """Evaluate a single metric against expected target using requested comparator."""
        metadata = metadata or {}
        comp_norm = comparator.lower().strip()

        status = CriterionEvaluationStatus.UNSATISFIED
        deviation: float | None = None
        confidence = 1.0

        if actual is None:
            status = CriterionEvaluationStatus.INCONCLUSIVE
            confidence = 0.0
            res = OutcomeMetricResult(
                metric_id=metric_id,
                name=name,
                expected=expected,
                actual=actual,
                comparator=comparator,
                status=status,
                deviation=None,
                confidence=confidence,
                evidence_ids=evidence_ids,
                metadata=metadata,
            )
            self._publish_event("OUTCOME_METRIC_EVALUATED", res.to_dict())
            return res

        try:
            if comp_norm in ("exact", "exact_match"):
                passed = actual == expected
                status = (
                    CriterionEvaluationStatus.SATISFIED
                    if passed
                    else CriterionEvaluationStatus.UNSATISFIED
                )

            elif comp_norm in ("minimum", "min"):
                actual_num = float(actual)
                exp_num = float(expected)
                passed = actual_num >= exp_num
                deviation = actual_num - exp_num
                status = (
                    CriterionEvaluationStatus.SATISFIED
                    if passed
                    else CriterionEvaluationStatus.UNSATISFIED
                )

            elif comp_norm in ("maximum", "max"):
                actual_num = float(actual)
                exp_num = float(expected)
                passed = actual_num <= exp_num
                deviation = actual_num - exp_num
                status = (
                    CriterionEvaluationStatus.SATISFIED
                    if passed
                    else CriterionEvaluationStatus.UNSATISFIED
                )

            elif comp_norm == "range":
                actual_num = float(actual)
                # expected can be a tuple/list (min, max)
                if isinstance(expected, (list, tuple)) and len(expected) == 2:
                    min_v, max_v = float(expected[0]), float(expected[1])
                    passed = min_v <= actual_num <= max_v
                    status = (
                        CriterionEvaluationStatus.SATISFIED
                        if passed
                        else CriterionEvaluationStatus.UNSATISFIED
                    )
                else:
                    raise OutcomeMetricError(
                        f"Range comparator requires tuple/list (min, max) for expected, got {expected!r}"
                    )

            elif comp_norm == "percentage":
                actual_pct = float(actual)
                exp_pct = float(expected)
                passed = actual_pct >= exp_pct
                deviation = actual_pct - exp_pct
                status = (
                    CriterionEvaluationStatus.SATISFIED
                    if passed
                    else CriterionEvaluationStatus.UNSATISFIED
                )

            elif comp_norm == "boolean":
                passed = bool(actual) == bool(expected)
                status = (
                    CriterionEvaluationStatus.SATISFIED
                    if passed
                    else CriterionEvaluationStatus.UNSATISFIED
                )

            elif comp_norm in ("count", "duration", "cost"):
                actual_val = float(actual)
                exp_val = float(expected)
                passed = actual_val <= exp_val
                deviation = actual_val - exp_val
                status = (
                    CriterionEvaluationStatus.SATISFIED
                    if passed
                    else CriterionEvaluationStatus.UNSATISFIED
                )

            elif comp_norm in self._custom_evaluators:
                passed = bool(self._custom_evaluators[comp_norm](expected, actual))
                status = (
                    CriterionEvaluationStatus.SATISFIED
                    if passed
                    else CriterionEvaluationStatus.UNSATISFIED
                )

            else:
                # Missing/unregistered comparator -> INCONCLUSIVE/BLOCKED, never fictitious success!
                status = CriterionEvaluationStatus.INCONCLUSIVE
                confidence = 0.0

        except (ValueError, TypeError) as exc:
            status = CriterionEvaluationStatus.INCONCLUSIVE
            confidence = 0.0
            metadata = {**metadata, "evaluation_error": str(exc)}

        res = OutcomeMetricResult(
            metric_id=metric_id,
            name=name,
            expected=expected,
            actual=actual,
            comparator=comparator,
            status=status,
            deviation=deviation,
            confidence=confidence,
            evidence_ids=evidence_ids,
            metadata=metadata,
        )

        self._publish_event("OUTCOME_METRIC_EVALUATED", res.to_dict())
        return res
