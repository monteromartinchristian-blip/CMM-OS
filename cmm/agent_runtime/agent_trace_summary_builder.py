"""Phase 9.19 – Agent Runtime Trace Summary Builder.

Produces a structured AgentTraceSummary capable of answering key questions
about the execution without generating reasoning narrative.
"""

from __future__ import annotations

from cmm.agent_runtime.agent_trace_contracts import (
    AgentTrace,
    AgentTraceSummary,
)


class AgentTraceSummaryBuilder:
    """Builds a structured summary for an AgentTrace.

    The summary contains reason codes, IDs, and counts — no free reasoning text.
    """

    def build(self, trace: AgentTrace) -> AgentTraceSummary:
        """Build a summary from a completed or partial trace."""
        operations = trace.operations
        validations = trace.validations
        recovery_decisions = trace.recovery_decisions
        budget_events = trace.budget_events

        retry_count = sum(
            1
            for rd in recovery_decisions
            if rd.strategy in ("retry", "retry_later", "retry_with_modified_parameters")
        )
        rollback_count = sum(
            1 for rd in recovery_decisions if rd.strategy == "rollback"
        )
        replan_count = sum(1 for rd in recovery_decisions if rd.strategy == "replan")

        # Budget consumed: sum by resource_type
        budget_consumed: dict[str, float] = {}
        for be in budget_events:
            if be.event_kind in ("confirmed", "consumed"):
                budget_consumed[be.resource_type] = (
                    budget_consumed.get(be.resource_type, 0.0) + be.amount
                )

        # Modified resources from resource_changes
        modified_resources = tuple(rc.resource for rc in trace.resource_changes)

        # Warnings
        warnings = tuple(w.message for w in trace.warnings)

        # Stop reason codes
        stop_reason_codes = (
            trace.stop_decision.reason_codes if trace.stop_decision else ()
        )

        # Goal satisfaction
        goal_satisfied = (
            trace.stop_decision.goal_satisfied if trace.stop_decision else False
        )

        # Outcome
        outcome = trace.stop_decision.outcome if trace.stop_decision else ""
        completion_decision = (
            trace.stop_decision.completion_decision if trace.stop_decision else ""
        )

        # Knowledge and memory updates
        knowledge_updates = len(trace.knowledge_updates)
        memory_updates = len(trace.memory_updates)

        return AgentTraceSummary(
            goal_status=trace.status,
            outcome=outcome,
            completion_decision=completion_decision,
            operation_count=len(operations),
            validation_count=len(validations),
            retry_count=retry_count,
            rollback_count=rollback_count,
            replan_count=replan_count,
            budget_consumed=budget_consumed,
            modified_resources=modified_resources,
            warnings=warnings,
            stop_reason_codes=stop_reason_codes,
            goal_satisfied=goal_satisfied,
            knowledge_updates=knowledge_updates,
            memory_updates=memory_updates,
        )
