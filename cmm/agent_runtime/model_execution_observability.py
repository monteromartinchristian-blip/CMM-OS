"""One-way projection of execution records into canonical observability."""

from __future__ import annotations

from decimal import Decimal

from cmm.agent_runtime.agent_observability_contracts import AgentModelInvocationRecord
from cmm.agent_runtime.agent_observability_enums import AgentAuditOutcome
from cmm.agent_runtime.agent_observability_service import AgentObservabilityService
from cmm.agent_runtime.model_execution_contracts import (
    AcceptanceStatus,
    ModelExecutionRecord,
)


class ModelExecutionObservabilityProjector:
    """Project safe summary data; prompts/responses never enter observability."""

    def __init__(self, service: AgentObservabilityService) -> None:
        self._service = service

    def project(self, record: ModelExecutionRecord) -> AgentModelInvocationRecord:
        outcome = (
            AgentAuditOutcome.FAILED
            if record.execution_status.value == "failed"
            else AgentAuditOutcome.SUCCESS
        )
        if record.acceptance_status in {
            AcceptanceStatus.PENDING,
            AcceptanceStatus.ACCEPTED_WITH_WARNING,
        }:
            outcome = AgentAuditOutcome.PARTIAL
        return self._service.record_model_invocation(
            AgentModelInvocationRecord(
                id=record.id,
                timestamp=record.created_at,
                provider=record.provider_id,
                model=record.model_id,
                operation_id=record.operation_id or record.id,
                selection_reason=record.economic_decision or "model_execution",
                configuration_version=record.configuration_version or "1",
                privacy_mode=record.content_retention.value,
                agent_run_id=record.agent_run_id,
                goal_id=record.goal_id,
                input_tokens=record.input_tokens,
                output_tokens=record.output_tokens,
                cached_input_tokens=record.cached_tokens,
                estimated_cost=record.estimated_cost,
                # The canonical observability contract requires a Decimal. Zero is
                # an explicit sentinel here; metadata preserves availability so
                # estimated cost is never presented as actual cost.
                actual_cost=record.actual_cost
                if record.actual_cost is not None
                else Decimal(0),
                latency_ms=record.latency_ms,
                retry_count=record.retry_number,
                fallback=record.fallback_from is not None,
                validation_outcome=outcome,
                persisted_result=True,
                trace_id=record.trace_id,
                correlation_id=record.correlation_id,
                metadata={
                    "model_execution_record_id": record.id,
                    "actual_cost_available": record.actual_cost is not None,
                    "acceptance_status": record.acceptance_status.value,
                },
            )
        )
