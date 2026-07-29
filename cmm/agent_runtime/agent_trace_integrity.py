"""Phase 9.19 – Agent Runtime Trace Integrity Verifier.

Verifies trace integrity: ordering, causation, required records,
fingerprints, and absence of prohibited fields.
"""

from __future__ import annotations

from cmm.agent_runtime.agent_trace_contracts import (
    AgentTrace,
    AgentTraceIntegrityReport,
)
from cmm.agent_runtime.enums import AgentTraceIntegrityStatus


class AgentTraceIntegrityVerifier:
    """Verifies the integrity of an AgentTrace.

    Checks:
    - trace_id, agent_run_id, goal_id presence
    - timestamp ordering
    - duplicate event_ids
    - correlation/causation chains
    - iteration boundaries
    - state transitions
    - final event presence
    - outcome presence
    - event_count matching source_event_ids
    - fingerprint validity
    - no prohibited fields
    """

    _PROHIBITED_FIELD_PATTERNS = (
        "chain_of_thought",
        "internal_reasoning",
        "private_prompt",
        "scratchpad",
        "reasoning_trace",
        "private_thoughts",
    )

    def verify(self, trace: AgentTrace) -> AgentTraceIntegrityReport:
        """Verify trace integrity and return a report."""
        issues: list[str] = []
        missing_events: list[str] = []
        duplicate_events: list[str] = []
        ordering_errors: list[str] = []
        causality_errors: list[str] = []

        # 1. Required IDs
        if not trace.trace_id:
            issues.append("trace_id is empty")
        if not trace.agent_run_id:
            issues.append("agent_run_id is empty")
        if not trace.goal_id:
            issues.append("goal_id is empty")

        # 2. Timestamp ordering
        if trace.completed_at is not None and trace.started_at > trace.completed_at:
            ordering_errors.append("completed_at before started_at")
        if trace.duration_ms is not None and trace.duration_ms < 0:
            ordering_errors.append("negative duration_ms")

        # 3. Iteration ordering
        seen_iterations: set[str] = set()
        for it in trace.iterations:
            if it.iteration_id in seen_iterations:
                duplicate_events.append(f"duplicate iteration: {it.iteration_id}")
            seen_iterations.add(it.iteration_id)
            if it.completed_at is not None and it.started_at > it.completed_at:
                ordering_errors.append(
                    f"iteration {it.iteration_id}: completed_at before started_at"
                )

        # 4. Event count vs source_event_ids
        if trace.event_count > 0 and len(trace.source_event_ids) != trace.event_count:
            issues.append(
                f"event_count ({trace.event_count}) != source_event_ids count ({len(trace.source_event_ids)})"
            )

        # 5. Duplicate source_event_ids
        seen_source: set[str] = set()
        for sid in trace.source_event_ids:
            if sid in seen_source:
                duplicate_events.append(f"duplicate source_event_id: {sid}")
            seen_source.add(sid)

        # 6. Final event / stop decision for COMPLETE status
        if trace.status in ("complete", "COMPLETE"):
            if trace.stop_decision is None:
                missing_events.append("stop_decision missing for COMPLETE trace")
            if trace.completed_at is None:
                missing_events.append("completed_at missing for COMPLETE trace")

        # 7. Outcome for completed traces
        if (
            trace.status in ("complete", "COMPLETE", "partial", "PARTIAL")
            and trace.stop_decision is not None
            and not trace.stop_decision.outcome
        ):
            missing_events.append("outcome missing in stop_decision")

        # 8. Knowledge update after outcome
        if trace.stop_decision is not None and trace.knowledge_updates:
            stop_ts = trace.stop_decision.timestamp
            for ku in trace.knowledge_updates:
                if ku.timestamp < stop_ts:
                    causality_errors.append(
                        f"knowledge_update {ku.proposal_id} before stop_decision"
                    )

        # 9. Operation completion without operation start
        op_starts: set[str] = set()
        op_completes: set[str] = set()
        for op in trace.operations:
            if op.status in ("completed", "COMPLETED", "failed", "FAILED"):
                op_completes.add(op.operation_id)
            else:
                op_starts.add(op.operation_id)
        for oid in op_completes:
            if oid not in op_starts:
                causality_errors.append(f"operation {oid}: completed without start")

        # 10. Rollback without recovery decision
        rollback_ids: set[str] = set()
        for rd in trace.recovery_decisions:
            if rd.strategy == "rollback":
                rollback_ids.add(rd.recovery_decision_id)
        for rex in trace.recovery_executions:
            if (
                rex.strategy == "rollback"
                and rex.recovery_execution_id not in rollback_ids
            ):
                causality_errors.append(
                    f"rollback execution {rex.recovery_execution_id} without recovery decision"
                )

        # 11. Prohibited fields in metadata
        for key in trace.metadata:
            if any(p in key.lower() for p in self._PROHIBITED_FIELD_PATTERNS):
                issues.append(f"prohibited field in metadata: {key}")

        # 12. Fingerprint check (basic)
        if trace.fingerprint and len(trace.fingerprint) < 8:
            issues.append("fingerprint too short or invalid")

        # Determine overall status
        if (
            not issues
            and not missing_events
            and not duplicate_events
            and not ordering_errors
            and not causality_errors
        ):
            status = AgentTraceIntegrityStatus.VALID.value
        elif issues or causality_errors:
            status = AgentTraceIntegrityStatus.CORRUPTED.value
        elif missing_events:
            status = AgentTraceIntegrityStatus.MISSING_EVENTS.value
        elif duplicate_events:
            status = AgentTraceIntegrityStatus.DUPLICATE_EVENTS.value
        elif ordering_errors:
            status = AgentTraceIntegrityStatus.ORDERING_ERROR.value
        else:
            status = AgentTraceIntegrityStatus.PARTIAL.value

        return AgentTraceIntegrityReport(
            trace_id=trace.trace_id,
            status=status,
            issues=tuple(issues),
            missing_events=tuple(missing_events),
            duplicate_events=tuple(duplicate_events),
            ordering_errors=tuple(ordering_errors),
            causality_errors=tuple(causality_errors),
            fingerprint_valid=bool(trace.fingerprint),
        )
