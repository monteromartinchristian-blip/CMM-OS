"""Phase 9.17 – Outcome Regression Detector.

Detects regressions across validations, metrics, resource versions, test suites,
capability losses, data losses, and criterion degradation.
"""

from __future__ import annotations

import uuid
from typing import Any

from cmm.agent_runtime.outcome_evaluation_contracts import (
    OutcomeEvidence,
    OutcomeRegression,
)
from cmm.agent_runtime.outcome_state_comparator import StateComparisonDiff


class OutcomeRegressionDetector:
    """Detects performance, functional, and state regressions resulting from execution."""

    def __init__(self, event_bus: Any = None) -> None:
        self._event_bus = event_bus

    def _publish_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_bus and hasattr(self._event_bus, "publish"):
            try:
                self._event_bus.publish(event_type, payload)
            except Exception:
                pass

    def detect_regressions(
        self,
        diff: StateComparisonDiff,
        validations: tuple[Any, ...] = (),
        previous_validations: tuple[Any, ...] = (),
        metrics: tuple[Any, ...] = (),
        previous_metrics: tuple[Any, ...] = (),
        evidence: tuple[OutcomeEvidence, ...] = (),
    ) -> tuple[OutcomeRegression, ...]:
        """Analyze runtime state changes and test/validation results to identify regressions."""
        regressions: list[OutcomeRegression] = []

        # 1. State comparison version mismatches and unexpected resource deletions
        for res_name, (exp_v, act_v) in diff.version_mismatches.items():
            reg = OutcomeRegression(
                regression_id=f"reg-ver-{uuid.uuid4().hex[:8]}",
                category="resource_version",
                severity="high",
                previous_value=exp_v,
                current_value=act_v,
                affected_resources=(res_name,),
                reversible=True,
                rollback_recommended=True,
                metadata={"reason": "Resource version degradation or mismatch"},
            )
            regressions.append(reg)
            self._publish_event("OUTCOME_REGRESSION_DETECTED", reg.to_dict())

        # 2. Validation regressions (previously passing, now failing)
        prev_val_map = {
            getattr(v, "validation_id", getattr(v, "id", str(i))): bool(
                getattr(
                    v,
                    "is_success",
                    getattr(v, "success", getattr(v, "passed", False)),
                )
            )
            for i, v in enumerate(previous_validations)
        }

        for i, val in enumerate(validations):
            val_id = getattr(val, "validation_id", getattr(val, "id", str(i)))
            is_success = bool(
                getattr(
                    val,
                    "is_success",
                    getattr(val, "success", getattr(val, "passed", False)),
                )
            )
            if val_id in prev_val_map and prev_val_map[val_id] and not is_success:
                reg = OutcomeRegression(
                    regression_id=f"reg-val-{uuid.uuid4().hex[:8]}",
                    category="validation_failure",
                    severity="critical",
                    previous_value=True,
                    current_value=False,
                    affected_resources=(str(val_id),),
                    reversible=False,
                    rollback_recommended=True,
                    metadata={
                        "validation_id": str(val_id),
                        "reason": "Validation previously passed, now failing",
                    },
                )
                regressions.append(reg)
                self._publish_event("OUTCOME_REGRESSION_DETECTED", reg.to_dict())

        # 3. Metric degradation regressions
        prev_metric_map = {
            m.get("metric_id", str(i)): m for i, m in enumerate(previous_metrics)
        }
        for i, m in enumerate(metrics):
            m_id = m.get("metric_id", str(i))
            if m_id in prev_metric_map:
                prev_m = prev_metric_map[m_id]
                prev_val = prev_m.get("actual")
                curr_val = m.get("actual")
                comp = m.get("comparator", "max")

                # If comparator indicates smaller is better, higher actual is regression
                if (
                    prev_val is not None
                    and curr_val is not None
                    and isinstance(prev_val, (int, float))
                    and isinstance(curr_val, (int, float))
                ):
                    is_degraded = False
                    if comp in ("maximum", "max", "cost", "duration", "count"):
                        is_degraded = curr_val > prev_val
                    elif comp in ("minimum", "min", "percentage"):
                        is_degraded = curr_val < prev_val

                    if is_degraded:
                        severity = (
                            "critical"
                            if abs(curr_val - prev_val) / (abs(prev_val) or 1) > 0.2
                            else "high"
                        )
                        reg = OutcomeRegression(
                            regression_id=f"reg-met-{uuid.uuid4().hex[:8]}",
                            category="metric_degradation",
                            severity=severity,
                            previous_value=prev_val,
                            current_value=curr_val,
                            affected_resources=(m_id,),
                            reversible=True,
                            rollback_recommended=severity == "critical",
                            metadata={
                                "metric_id": m_id,
                                "comparator": comp,
                                "reason": "Metric performance degraded compared to baseline",
                            },
                        )
                        regressions.append(reg)
                        self._publish_event(
                            "OUTCOME_REGRESSION_DETECTED", reg.to_dict()
                        )

        # 4. State missing unexpected deletions / data loss
        for k, exp_v in diff.missing_changes.items():
            if k in diff.divergences:
                prev_v, curr_v = diff.divergences[k]
                reg = OutcomeRegression(
                    regression_id=f"reg-state-{uuid.uuid4().hex[:8]}",
                    category="state_divergence",
                    severity="high",
                    previous_value=prev_v,
                    current_value=curr_v,
                    affected_resources=(k,),
                    reversible=True,
                    rollback_recommended=False,
                    metadata={"resource": k, "reason": "Resource state divergence"},
                )
                regressions.append(reg)
                self._publish_event("OUTCOME_REGRESSION_DETECTED", reg.to_dict())

        return tuple(regressions)
