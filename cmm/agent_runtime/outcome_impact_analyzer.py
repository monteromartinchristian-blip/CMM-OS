"""Phase 9.17 – Outcome Impact Analyzer.

Analyzes side effects, technical/operational debt, security risks,
and residual impacts resulting from execution.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from cmm.agent_runtime.outcome_evaluation_contracts import (
    OutcomeEvidence,
    OutcomeGeneratedDebt,
    OutcomeRiskAssessment,
    OutcomeSideEffect,
)
from cmm.agent_runtime.outcome_state_comparator import StateComparisonDiff
from cmm.agent_runtime.runtime_event_errors import AgentRuntimeEventError

logger = logging.getLogger(__name__)


class OutcomeImpactAnalyzer:
    """Analyzes execution side effects, technical/operational debt, and residual risks."""

    def __init__(self, event_bus: Any = None) -> None:
        self._event_bus = event_bus

    def _publish_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_bus and hasattr(self._event_bus, "publish"):
            try:
                self._event_bus.publish(event_type, payload)
            except AgentRuntimeEventError as exc:
                logger.warning(
                    "Runtime event publication failed for %s: %s",
                    event_type,
                    exc,
                )

    def analyze_impact(
        self,
        diff: StateComparisonDiff,
        operation_results: tuple[Any, ...] = (),
        evidence: tuple[OutcomeEvidence, ...] = (),
        explicit_side_effects: tuple[OutcomeSideEffect, ...] = (),
        explicit_debt: tuple[OutcomeGeneratedDebt, ...] = (),
    ) -> tuple[
        tuple[OutcomeSideEffect, ...],
        tuple[OutcomeGeneratedDebt, ...],
        tuple[OutcomeRiskAssessment, ...],
    ]:
        """Analyze state diff and operation history to discover side effects, generated debt, and residual risks."""
        side_effects: list[OutcomeSideEffect] = list(explicit_side_effects)
        generated_debt: list[OutcomeGeneratedDebt] = list(explicit_debt)
        risks: list[OutcomeRiskAssessment] = []

        # Publish explicit side effects and debt events
        for se in explicit_side_effects:
            self._publish_event("OUTCOME_SIDE_EFFECT_DETECTED", se.to_dict())
        for d in explicit_debt:
            self._publish_event("OUTCOME_DEBT_RECORDED", d.to_dict())

        # 1. Discover unexpected side effects from unexpected changes in diff
        for k, v in diff.unexpected_changes.items():
            se = OutcomeSideEffect(
                side_effect_id=f"se-unexp-{uuid.uuid4().hex[:8]}",
                description=f"Unexpected resource state change for '{k}'",
                expected=False,
                reversible=True,
                authorized=False,
                affected_resources=(k,),
                metadata={"new_value": str(v)},
            )
            side_effects.append(se)
            self._publish_event("OUTCOME_SIDE_EFFECT_DETECTED", se.to_dict())

        # 2. Check for unauthorized or irreversible side effects and record operational debt
        for se in side_effects:
            if not se.authorized:
                d = OutcomeGeneratedDebt(
                    debt_id=f"debt-auth-{uuid.uuid4().hex[:8]}",
                    category="operational",
                    description=f"Unauthorized side effect on {list(se.affected_resources)}: {se.description}",
                    severity="high" if not se.reversible else "medium",
                    accepted=False,
                    linked_artifacts=se.affected_resources,
                    metadata={"side_effect_id": se.side_effect_id},
                )
                generated_debt.append(d)
                self._publish_event("OUTCOME_DEBT_RECORDED", d.to_dict())

            if not se.reversible:
                r = OutcomeRiskAssessment(
                    risk_id=f"risk-irrev-{uuid.uuid4().hex[:8]}",
                    category="irreversible_side_effect",
                    level="high" if not se.authorized else "medium",
                    description=f"Irreversible change on {list(se.affected_resources)}",
                    acceptable=se.authorized,
                    metadata={"side_effect_id": se.side_effect_id},
                )
                risks.append(r)

        # 3. Analyze operation results for unhandled warnings/debt
        for op in operation_results:
            op_warnings = getattr(op, "warnings", ())
            if op_warnings:
                d = OutcomeGeneratedDebt(
                    debt_id=f"debt-op-{uuid.uuid4().hex[:8]}",
                    category="technical",
                    description=f"Operation warnings unaddressed: {list(op_warnings)[:2]}",
                    severity="low",
                    accepted=False,
                    metadata={"operation_id": getattr(op, "operation_id", "")},
                )
                generated_debt.append(d)
                self._publish_event("OUTCOME_DEBT_RECORDED", d.to_dict())

        # 4. Check for unaccepted critical debt -> generate residual risk
        for d in generated_debt:
            if d.severity == "critical" and not d.accepted:
                r = OutcomeRiskAssessment(
                    risk_id=f"risk-debt-{uuid.uuid4().hex[:8]}",
                    category="critical_unaccepted_debt",
                    level="critical",
                    description=f"Unaccepted critical debt: {d.description}",
                    acceptable=False,
                    metadata={"debt_id": d.debt_id},
                )
                risks.append(r)

        return tuple(side_effects), tuple(generated_debt), tuple(risks)
