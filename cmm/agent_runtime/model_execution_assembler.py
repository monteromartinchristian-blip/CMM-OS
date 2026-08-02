"""Pure adapters that assemble a model execution record from runtime contracts."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from .economic_budget_contracts import ModelCostEstimate
from .model_execution_contracts import (
    ModelExecutionContentReference,
    ModelExecutionRecord,
    QualityEvaluation,
)
from .model_execution_errors import InvalidModelExecutionRecordError
from .model_fallback_contracts import ModelAttemptResult


class ModelExecutionRecordAssembler:
    @staticmethod
    def _value(value: Any) -> Any:
        return value.value if hasattr(value, "value") else value

    @staticmethod
    def from_attempt(
        attempt: ModelAttemptResult,
        *,
        record_id: str,
        agent_run_id: str,
        goal_id: str | None = None,
        workflow_id: str | None = None,
        task_id: str | None = None,
        capability: str = "unknown",
        model_version: str | None = None,
        routing_decision: Any = None,
        estimate: ModelCostEstimate | None = None,
        actual: ModelCostEstimate | None = None,
        currency: str | None = None,
        trace_id: str | None = None,
        correlation_id: str | None = None,
        policy_version: str | None = None,
        configuration_version: str | None = None,
        fallback_from: str | None = None,
        fallback_trigger: Any = None,
        fallback_action: Any = None,
        attempt_history_reference: str | None = None,
        budget_id: str | None = None,
        reservation_id: str | None = None,
        economic_decision: Any = None,
        economic_reason_codes: tuple[str, ...] = (),
        validation_result_ids: tuple[str, ...] = (),
        validation_status: str | None = None,
        validation_blocking_count: int = 0,
        validation_warning_count: int = 0,
        quality_evaluation: QualityEvaluation | None = None,
        causation_id: str | None = None,
        content_reference: ModelExecutionContentReference | None = None,
        content_retention: Any = "hashes_only",
        privacy_classification: Any = "internal",
        exclusion_reasons: tuple[str, ...] = (),
        privacy_policy_version: str = "1",
    ) -> ModelExecutionRecord:
        if (
            estimate is not None
            and actual is not None
            and estimate.currency != actual.currency
        ):
            raise InvalidModelExecutionRecordError(
                "estimate and actual costs must use the same currency"
            )
        resolved_currency = (
            estimate.currency
            if estimate is not None
            else actual.currency
            if actual is not None
            else currency or "USD"
        )
        return ModelExecutionRecord(
            id=record_id,
            agent_run_id=agent_run_id,
            goal_id=goal_id,
            workflow_id=workflow_id,
            operation_id=attempt.operation_id,
            provider_id=attempt.provider_id,
            model_id=attempt.model_id,
            model_version=model_version,
            capability=capability,
            input_tokens=estimate.input_tokens or 0 if estimate else 0,
            output_tokens=estimate.output_tokens or 0 if estimate else 0,
            cached_tokens=estimate.cached_input_tokens or 0 if estimate else 0,
            estimated_cost=estimate.total_cost
            if estimate
            else (attempt.estimated_cost or Decimal(0)),
            actual_cost=actual.total_cost if actual else attempt.actual_cost,
            currency=resolved_currency,
            latency_ms=attempt.latency_ms or 0,
            retry_number=attempt.attempt_index - 1,
            routing_decision_id=getattr(routing_decision, "id", None),
            routing_provider_id=getattr(routing_decision, "selected_provider_id", None),
            routing_model_id=getattr(routing_decision, "selected_model_id", None),
            routing_reason_codes=tuple(getattr(routing_decision, "reason_codes", ())),
            rejected_candidates_count=len(
                getattr(routing_decision, "rejected_models", ())
            ),
            fallback_from=fallback_from,
            fallback_trigger=ModelExecutionRecordAssembler._value(
                fallback_trigger if fallback_trigger is not None else attempt.trigger
            ),
            fallback_action=ModelExecutionRecordAssembler._value(fallback_action),
            attempt_history_reference=attempt_history_reference
            or f"operation:{attempt.operation_id}",
            budget_id=budget_id,
            reservation_id=reservation_id,
            economic_decision=ModelExecutionRecordAssembler._value(economic_decision),
            economic_reason_codes=economic_reason_codes,
            validation_result_ids=validation_result_ids,
            validation_status=validation_status,
            validation_blocking_count=validation_blocking_count,
            validation_warning_count=validation_warning_count,
            quality_evaluation=quality_evaluation,
            trace_id=trace_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            content_reference=content_reference,
            content_retention=ModelExecutionRecordAssembler._value(content_retention),
            privacy_classification=ModelExecutionRecordAssembler._value(
                privacy_classification
            ),
            exclusion_reasons=exclusion_reasons,
            privacy_policy_version=privacy_policy_version,
            policy_version=policy_version,
            configuration_version=configuration_version
            or getattr(routing_decision, "configuration_version", None),
            execution_status="completed" if attempt.success else "failed",
            acceptance_status="pending",
            created_at=datetime.now(timezone.utc),
        )
