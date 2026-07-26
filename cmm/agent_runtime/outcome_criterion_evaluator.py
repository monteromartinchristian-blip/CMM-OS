"""Phase 9.17 – Outcome Criterion Evaluator.

Evaluates SuccessCriterion objects against runtime observation states,
validations, operation results, metrics, and evidence, producing
immutable OutcomeCriterionResult contracts.
"""

from __future__ import annotations

from typing import Any

from cmm.agent_runtime.enums import (
    CriterionEvaluationStatus,
    CriterionImportance,
    OutcomeReasonCode,
)
from cmm.agent_runtime.errors import OutcomeCriterionEvaluationError
from cmm.agent_runtime.goal_contracts import SuccessCriterion
from cmm.agent_runtime.outcome_evaluation_contracts import (
    OutcomeCriterionResult,
    OutcomeEvidence,
    OutcomeUserConfirmationRequirement,
)


class OutcomeCriterionEvaluator:
    """Evaluates individual success criteria against runtime evidence and state."""

    def __init__(self, event_bus: Any = None) -> None:
        self._event_bus = event_bus

    def _publish_event(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_bus and hasattr(self._event_bus, "publish"):
            try:
                self._event_bus.publish(event_type, payload)
            except Exception:
                pass

    def evaluate_criterion(
        self,
        criterion: SuccessCriterion,
        expected_state: dict[str, Any] | None = None,
        actual_state: dict[str, Any] | None = None,
        validations: tuple[Any, ...] = (),
        metrics: tuple[Any, ...] = (),
        evidence: tuple[OutcomeEvidence, ...] = (),
        user_confirmation: OutcomeUserConfirmationRequirement | None = None,
        side_effects: tuple[Any, ...] = (),
        risks: tuple[Any, ...] = (),
        debt: tuple[Any, ...] = (),
    ) -> OutcomeCriterionResult:
        """Evaluate a single SuccessCriterion to produce an OutcomeCriterionResult."""
        if not isinstance(criterion, SuccessCriterion):
            raise OutcomeCriterionEvaluationError(
                f"Expected SuccessCriterion, got {type(criterion).__name__}"
            )

        expected_state = expected_state or {}
        actual_state = actual_state or {}

        # Determine criterion importance
        importance_str = criterion.metadata.get(
            "importance",
            "mandatory" if criterion.required else "optional",
        )
        try:
            importance = CriterionImportance(importance_str)
        except ValueError:
            importance = (
                CriterionImportance.MANDATORY
                if criterion.required
                else CriterionImportance.OPTIONAL
            )

        warnings: list[str] = []
        reason_codes: list[OutcomeReasonCode] = []
        evidence_ids: list[str] = list(criterion.evidence)
        val_result_ids: list[str] = []

        # Collect evidence matching this criterion
        for ev in evidence:
            if ev.evidence_id not in evidence_ids and (
                criterion.id in ev.description
                or criterion.id in ev.metadata.get("criterion_id", "")
            ):
                evidence_ids.append(ev.evidence_id)

        # Check for explicitly waived criteria
        is_waived = (
            criterion.metadata.get("waived", False)
            or criterion.metadata.get("status") == "waived"
        )
        waiver_authorized = bool(
            criterion.metadata.get("waived_by")
            or criterion.metadata.get("waiver_policy")
        )

        if is_waived:
            if waiver_authorized:
                status = CriterionEvaluationStatus.WAIVED
                blocking = False
                confidence = 1.0
            else:
                status = CriterionEvaluationStatus.BLOCKED
                blocking = True
                warnings.append(
                    f"Criterion {criterion.id} marked waived without explicit authorization/policy"
                )
                reason_codes.append(OutcomeReasonCode.MANDATORY_CRITERION_UNSATISFIED)
                confidence = 0.5

            res = OutcomeCriterionResult(
                criterion_id=criterion.id,
                status=status,
                importance=importance,
                expected_value=criterion.expected_value,
                actual_value=criterion.actual_value,
                evidence_ids=tuple(evidence_ids),
                validation_result_ids=tuple(val_result_ids),
                reason_codes=tuple(reason_codes),
                confidence=confidence,
                warnings=tuple(warnings),
                blocking=blocking,
                metadata=dict(criterion.metadata),
            )
            self._publish_event("OUTCOME_CRITERION_EVALUATED", res.to_dict())
            return res

        # Check validations linked to this criterion
        matching_validations = []
        for val in validations:
            val_id = getattr(val, "validation_id", getattr(val, "id", ""))
            val_success = getattr(
                val,
                "is_success",
                getattr(val, "success", getattr(val, "passed", False)),
            )
            if val_id:
                val_result_ids.append(str(val_id))
            matching_validations.append(bool(val_success))

        # Check user confirmation requirement if applicable
        if (
            criterion.metadata.get("requires_user_confirmation")
            and (user_confirmation is None or user_confirmation.status != "confirmed")
        ):
            warnings.append(
                f"Criterion {criterion.id} requires user confirmation which is absent or unconfirmed"
            )
            reason_codes.append(OutcomeReasonCode.USER_CONFIRMATION_REQUIRED)

        # Evaluate based on criterion evaluator / kind / values
        confidence = 1.0
        status = CriterionEvaluationStatus.NOT_EVALUATED

        # Case 1: Criterion expected_value vs actual_value
        exp_val = criterion.expected_value
        act_val = criterion.actual_value

        if exp_val is not None or act_val is not None:
            if act_val is None and criterion.id in actual_state:
                act_val = actual_state[criterion.id]
            if exp_val is None and criterion.id in expected_state:
                exp_val = expected_state[criterion.id]

            if exp_val is not None and act_val is not None:
                if exp_val == act_val:
                    status = CriterionEvaluationStatus.SATISFIED
                    reason_codes.append(
                        OutcomeReasonCode.ALL_MANDATORY_CRITERIA_SATISFIED
                        if importance == CriterionImportance.MANDATORY
                        else OutcomeReasonCode.PARTIAL_PROGRESS
                    )
                else:
                    status = CriterionEvaluationStatus.UNSATISFIED
                    reason_codes.append(
                        OutcomeReasonCode.MANDATORY_CRITERION_UNSATISFIED
                        if importance == CriterionImportance.MANDATORY
                        else OutcomeReasonCode.REQUIRED_CRITERION_UNSATISFIED
                    )
            elif exp_val is not None and act_val is None:
                status = CriterionEvaluationStatus.INCONCLUSIVE
                reason_codes.append(OutcomeReasonCode.EVIDENCE_INSUFFICIENT)
                warnings.append(
                    f"Criterion {criterion.id} missing actual_value for expected {exp_val!r}"
                )
                confidence = 0.5

        # Case 2: Validation-driven criterion
        elif matching_validations:
            if all(matching_validations):
                status = CriterionEvaluationStatus.SATISFIED
            else:
                status = CriterionEvaluationStatus.UNSATISFIED
                reason_codes.append(OutcomeReasonCode.VALIDATION_FAILED)
                warnings.append(f"Validation failed for criterion {criterion.id}")

        # Case 3: Evidence-driven or default state
        elif evidence_ids:
            # Evidence present
            status = CriterionEvaluationStatus.SATISFIED
        else:
            # Absence of evidence does not equal success!
            status = CriterionEvaluationStatus.INCONCLUSIVE
            reason_codes.append(OutcomeReasonCode.EVIDENCE_INSUFFICIENT)
            warnings.append(
                f"No evidence or validation provided for criterion {criterion.id}"
            )
            confidence = 0.3

        # Final blocking determination
        blocking = importance == CriterionImportance.MANDATORY and status in (
            CriterionEvaluationStatus.UNSATISFIED,
            CriterionEvaluationStatus.BLOCKED,
            CriterionEvaluationStatus.INCONCLUSIVE,
            CriterionEvaluationStatus.NOT_EVALUATED,
        )

        res = OutcomeCriterionResult(
            criterion_id=criterion.id,
            status=status,
            importance=importance,
            expected_value=exp_val,
            actual_value=act_val,
            evidence_ids=tuple(evidence_ids),
            validation_result_ids=tuple(val_result_ids),
            reason_codes=tuple(reason_codes),
            confidence=confidence,
            warnings=tuple(warnings),
            blocking=blocking,
            metadata=dict(criterion.metadata),
        )

        self._publish_event("OUTCOME_CRITERION_EVALUATED", res.to_dict())
        return res
