"""Phase 9.19 – Agent Runtime Trace Service.

Orchestrates trace assembly, redaction, integrity verification,
persistence, query, export, and archival.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.agent_trace_assembler import AgentTraceAssembler
from cmm.agent_runtime.agent_trace_contracts import (
    AgentTrace,
    AgentTraceExportRequest,
    AgentTraceExportResult,
    AgentTraceIntegrityReport,
    AgentTraceQuery,
    AgentTraceQueryResult,
    AgentTraceRedactionReport,
)
from cmm.agent_runtime.agent_trace_integrity import AgentTraceIntegrityVerifier
from cmm.agent_runtime.agent_trace_redactor import AgentTraceRedactor
from cmm.agent_runtime.agent_trace_repository import (
    AgentTraceRepository,
    InMemoryAgentTraceRepository,
)
from cmm.agent_runtime.agent_trace_summary_builder import AgentTraceSummaryBuilder
from cmm.agent_runtime.enums import (
    AgentAutonomyLevel,
    AgentTraceExportFormat,
    AgentTraceStatus,
)
from cmm.agent_runtime.errors import (
    AgentTraceFinalizedError,
    AgentTraceIntegrityError,
)


class AgentTraceService:
    """High-level service for managing agent runtime traces."""

    def __init__(
        self,
        repository: AgentTraceRepository | None = None,
        assembler: AgentTraceAssembler | None = None,
        redactor: AgentTraceRedactor | None = None,
        integrity_verifier: AgentTraceIntegrityVerifier | None = None,
        summary_builder: AgentTraceSummaryBuilder | None = None,
    ) -> None:
        self._repository = repository or InMemoryAgentTraceRepository()
        self._assembler = assembler or AgentTraceAssembler()
        self._redactor = redactor or AgentTraceRedactor()
        self._integrity_verifier = integrity_verifier or AgentTraceIntegrityVerifier()
        self._summary_builder = summary_builder or AgentTraceSummaryBuilder()

    def start_trace(
        self,
        agent_run_id: str,
        goal_id: str,
        goal_created_by: str = "",
        agent_id: str = "",
        workflow_id: str = "",
        autonomy_level: AgentAutonomyLevel | int = AgentAutonomyLevel.ANALYZE_ONLY,
        correlation_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AgentTrace:
        """Start a new trace for an agent run."""
        trace_id = str(uuid.uuid4())
        trace = AgentTrace(
            trace_id=trace_id,
            agent_run_id=agent_run_id,
            goal_id=goal_id,
            goal_created_by=goal_created_by,
            agent_id=agent_id,
            workflow_id=workflow_id,
            autonomy_level=autonomy_level,
            status=AgentTraceStatus.OPEN.value,
            correlation_id=correlation_id or trace_id,
            metadata=dict(metadata or {}),
        )
        return self._repository.save(trace)

    def append_event(self, trace_id: str, event: dict[str, Any]) -> AgentTrace:
        """Append a single event to a trace."""
        trace = self._repository.get(trace_id)
        if trace.status in (
            AgentTraceStatus.COMPLETE.value,
            AgentTraceStatus.ARCHIVED.value,
        ):
            raise AgentTraceFinalizedError(
                f"Cannot append event to finalized trace '{trace_id}'"
            )
        # Rebuild trace with new event
        events = [event]
        return self._rebuild(trace, events)

    def append_events(self, trace_id: str, events: list[dict[str, Any]]) -> AgentTrace:
        """Append multiple events to a trace."""
        trace = self._repository.get(trace_id)
        if trace.status in (
            AgentTraceStatus.COMPLETE.value,
            AgentTraceStatus.ARCHIVED.value,
        ):
            raise AgentTraceFinalizedError(
                f"Cannot append events to finalized trace '{trace_id}'"
            )
        return self._rebuild(trace, events)

    def build_trace(
        self,
        trace_id: str,
        agent_run_id: str,
        goal_id: str,
        goal_created_by: str = "",
        agent_id: str = "",
        workflow_id: str = "",
        autonomy_level: AgentAutonomyLevel | int = AgentAutonomyLevel.ANALYZE_ONLY,
        events: list[dict[str, Any]] | None = None,
        correlation_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AgentTrace:
        """Build a complete trace from context and events."""
        trace = self._assembler.assemble(
            trace_id=trace_id,
            agent_run_id=agent_run_id,
            goal_id=goal_id,
            goal_created_by=goal_created_by,
            agent_id=agent_id,
            workflow_id=workflow_id,
            autonomy_level=autonomy_level,
            events=events,
            correlation_id=correlation_id,
            metadata=metadata,
        )
        return self._repository.save(trace)

    def finalize_trace(
        self,
        trace_id: str,
        stop_decision: dict[str, Any] | None = None,
        outcome: str = "",
        completion_decision: str = "",
        reason_codes: tuple[str, ...] | None = None,
        goal_satisfied: bool = False,
    ) -> AgentTrace:
        """Finalize a trace with a stop decision and outcome."""
        trace = self._repository.get(trace_id)
        if trace.status in (
            AgentTraceStatus.COMPLETE.value,
            AgentTraceStatus.ARCHIVED.value,
        ):
            raise AgentTraceFinalizedError(f"Trace '{trace_id}' is already finalized")

        from cmm.agent_runtime.agent_trace_contracts import (
            AgentTraceStopDecision,
            _utcnow,
        )

        now = _utcnow()
        stop = AgentTraceStopDecision(
            stop_decision_id=str(uuid.uuid4()),
            reason_codes=tuple(reason_codes or ()),
            goal_satisfied=goal_satisfied,
            outcome=outcome,
            completion_decision=completion_decision,
            timestamp=now,
        )

        duration_ms = None
        if trace.started_at:
            duration_ms = int((now - trace.started_at).total_seconds() * 1000)

        # Build summary
        updated = AgentTrace(
            trace_id=trace.trace_id,
            agent_run_id=trace.agent_run_id,
            goal_id=trace.goal_id,
            goal_created_by=trace.goal_created_by,
            agent_id=trace.agent_id,
            workflow_id=trace.workflow_id,
            autonomy_level=trace.autonomy_level,
            status=AgentTraceStatus.COMPLETE.value,
            iterations=trace.iterations,
            observations=trace.observations,
            knowledge_loads=trace.knowledge_loads,
            cognitive_profiles=trace.cognitive_profiles,
            information_gaps=trace.information_gaps,
            questions=trace.questions,
            reasoning_result_ids=trace.reasoning_result_ids,
            runtime_decisions=trace.runtime_decisions,
            plans=trace.plans,
            policy_decisions=trace.policy_decisions,
            approval_requests=trace.approval_requests,
            approval_decisions=trace.approval_decisions,
            operations=trace.operations,
            resource_changes=trace.resource_changes,
            validations=trace.validations,
            recovery_decisions=trace.recovery_decisions,
            recovery_executions=trace.recovery_executions,
            checkpoints=trace.checkpoints,
            transactions=trace.transactions,
            outcome_evaluations=trace.outcome_evaluations,
            knowledge_updates=trace.knowledge_updates,
            memory_updates=trace.memory_updates,
            budget_events=trace.budget_events,
            warnings=trace.warnings,
            errors=trace.errors,
            stop_decision=stop,
            started_at=trace.started_at,
            completed_at=now,
            duration_ms=duration_ms,
            event_count=trace.event_count,
            source_event_ids=trace.source_event_ids,
            correlation_id=trace.correlation_id,
            metadata=trace.metadata,
            fingerprint=trace.fingerprint,
        )

        # Build summary
        summary = self._summary_builder.build(updated)
        updated = AgentTrace(
            trace_id=updated.trace_id,
            agent_run_id=updated.agent_run_id,
            goal_id=updated.goal_id,
            goal_created_by=updated.goal_created_by,
            agent_id=updated.agent_id,
            workflow_id=updated.workflow_id,
            autonomy_level=updated.autonomy_level,
            status=updated.status,
            iterations=updated.iterations,
            observations=updated.observations,
            knowledge_loads=updated.knowledge_loads,
            cognitive_profiles=updated.cognitive_profiles,
            information_gaps=updated.information_gaps,
            questions=updated.questions,
            reasoning_result_ids=updated.reasoning_result_ids,
            runtime_decisions=updated.runtime_decisions,
            plans=updated.plans,
            policy_decisions=updated.policy_decisions,
            approval_requests=updated.approval_requests,
            approval_decisions=updated.approval_decisions,
            operations=updated.operations,
            resource_changes=updated.resource_changes,
            validations=updated.validations,
            recovery_decisions=updated.recovery_decisions,
            recovery_executions=updated.recovery_executions,
            checkpoints=updated.checkpoints,
            transactions=updated.transactions,
            outcome_evaluations=updated.outcome_evaluations,
            knowledge_updates=updated.knowledge_updates,
            memory_updates=updated.memory_updates,
            budget_events=updated.budget_events,
            warnings=updated.warnings,
            errors=updated.errors,
            stop_decision=updated.stop_decision,
            summary=summary,
            started_at=updated.started_at,
            completed_at=updated.completed_at,
            duration_ms=updated.duration_ms,
            event_count=updated.event_count,
            source_event_ids=updated.source_event_ids,
            correlation_id=updated.correlation_id,
            metadata=updated.metadata,
            fingerprint=updated.fingerprint,
        )

        # Recompute fingerprint after mutation
        from cmm.agent_runtime.agent_trace_contracts import _utcnow

        completed_part = (updated.completed_at or _utcnow()).isoformat()
        stop_part = (
            updated.stop_decision.stop_decision_id if updated.stop_decision else ""
        )
        status_part = updated.status or ""
        fingerprint_input = "|".join(
            [
                updated.trace_id,
                updated.agent_run_id,
                updated.goal_id,
                str(updated.event_count),
                status_part,
                completed_part,
                stop_part,
            ]
        )
        updated_fingerprint = hashlib.sha256(
            fingerprint_input.encode("utf-8")
        ).hexdigest()[:32]
        updated = AgentTrace(
            trace_id=updated.trace_id,
            agent_run_id=updated.agent_run_id,
            goal_id=updated.goal_id,
            goal_created_by=updated.goal_created_by,
            agent_id=updated.agent_id,
            workflow_id=updated.workflow_id,
            autonomy_level=updated.autonomy_level,
            status=updated.status,
            iterations=updated.iterations,
            observations=updated.observations,
            knowledge_loads=updated.knowledge_loads,
            cognitive_profiles=updated.cognitive_profiles,
            information_gaps=updated.information_gaps,
            questions=updated.questions,
            reasoning_result_ids=updated.reasoning_result_ids,
            runtime_decisions=updated.runtime_decisions,
            plans=updated.plans,
            policy_decisions=updated.policy_decisions,
            approval_requests=updated.approval_requests,
            approval_decisions=updated.approval_decisions,
            operations=updated.operations,
            resource_changes=updated.resource_changes,
            validations=updated.validations,
            recovery_decisions=updated.recovery_decisions,
            recovery_executions=updated.recovery_executions,
            checkpoints=updated.checkpoints,
            transactions=updated.transactions,
            outcome_evaluations=updated.outcome_evaluations,
            knowledge_updates=updated.knowledge_updates,
            memory_updates=updated.memory_updates,
            budget_events=updated.budget_events,
            warnings=updated.warnings,
            errors=updated.errors,
            stop_decision=updated.stop_decision,
            summary=updated.summary,
            started_at=updated.started_at,
            completed_at=updated.completed_at,
            duration_ms=updated.duration_ms,
            event_count=updated.event_count,
            source_event_ids=updated.source_event_ids,
            correlation_id=updated.correlation_id,
            metadata=updated.metadata,
            fingerprint=updated_fingerprint,
        )

        # Verify integrity
        report = self._integrity_verifier.verify(updated)
        if report.status in ("corrupted", "fingerprint_mismatch"):
            raise AgentTraceIntegrityError(
                f"Cannot finalize trace with integrity issues: {', '.join(report.issues)}"
            )

        return self._repository.save(updated)

    def rebuild_trace(self, trace_id: str) -> AgentTrace:
        """Rebuild a trace from its stored events."""
        trace = self._repository.get(trace_id)
        # Rebuild with existing data (no new events)
        return self._repository.save(trace)

    def get_trace(self, trace_id: str) -> AgentTrace:
        """Retrieve a trace by ID."""
        return self._repository.get(trace_id)

    def query_traces(self, query: AgentTraceQuery) -> AgentTraceQueryResult:
        """Query traces with filters and pagination."""
        return self._repository.query(query)

    def verify_trace(self, trace_id: str) -> AgentTraceIntegrityReport:
        """Verify the integrity of a trace."""
        trace = self._repository.get(trace_id)
        return self._integrity_verifier.verify(trace)

    def redact_trace(
        self, trace_id: str
    ) -> tuple[AgentTrace, AgentTraceRedactionReport]:
        """Redact sensitive content from a trace."""
        trace = self._repository.get(trace_id)
        redacted, report = self._redactor.redact_trace(trace)
        saved = self._repository.save(redacted)
        return saved, report

    def archive_trace(self, trace_id: str) -> AgentTrace:
        """Archive a trace."""
        return self._repository.archive(trace_id)

    def export_trace(self, request: AgentTraceExportRequest) -> AgentTraceExportResult:
        """Export a trace in the requested format."""
        trace = self._repository.get(request.trace_id)

        # Apply redaction if requested
        if request.redact:
            trace, _ = self._redactor.redact_trace(trace)

        now = datetime.now(timezone.utc)

        if request.format == AgentTraceExportFormat.SUMMARY.value:
            data = json.dumps(
                trace.summary.to_dict() if trace.summary else {}, default=str
            )
        elif request.format in (
            AgentTraceExportFormat.JSONL.value,
            AgentTraceExportFormat.NDJSON.value,
        ):
            lines = [json.dumps(trace.to_dict(), default=str)]
            data = "\n".join(lines)
        else:
            data = json.dumps(trace.to_dict(), default=str, ensure_ascii=False)

        return AgentTraceExportResult(
            trace_id=trace.trace_id,
            format=request.format,
            data=data,
            schema_version="1.0",
            fingerprint=trace.fingerprint,
            export_timestamp=now.isoformat(),
        )

    def _rebuild(
        self, trace: AgentTrace, new_events: list[dict[str, Any]]
    ) -> AgentTrace:
        """Rebuild a trace with additional events."""
        import hashlib

        from cmm.agent_runtime.agent_trace_contracts import _utcnow

        # Ensure event metadata is immutable
        frozen_events = [dict(e) for e in new_events]

        # Compute updated metadata immutably
        updated_metadata = dict(trace.metadata or {})
        updated_metadata["_pending_events"] = len(frozen_events)

        # Recompute fingerprint
        completed_part = (trace.completed_at or _utcnow()).isoformat()
        stop_part = trace.stop_decision.stop_decision_id if trace.stop_decision else ""
        status_part = trace.status or ""
        fingerprint_input = "|".join(
            [
                trace.trace_id,
                trace.agent_run_id,
                trace.goal_id,
                str(trace.event_count + len(frozen_events)),
                status_part,
                completed_part,
                stop_part,
            ]
        )
        new_fingerprint = hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()[
            :32
        ]

        updated = AgentTrace(
            trace_id=trace.trace_id,
            agent_run_id=trace.agent_run_id,
            goal_id=trace.goal_id,
            goal_created_by=trace.goal_created_by,
            agent_id=trace.agent_id,
            workflow_id=trace.workflow_id,
            autonomy_level=trace.autonomy_level,
            status=trace.status,
            iterations=trace.iterations,
            observations=trace.observations,
            knowledge_loads=trace.knowledge_loads,
            cognitive_profiles=trace.cognitive_profiles,
            information_gaps=trace.information_gaps,
            questions=trace.questions,
            reasoning_result_ids=trace.reasoning_result_ids,
            runtime_decisions=trace.runtime_decisions,
            plans=trace.plans,
            policy_decisions=trace.policy_decisions,
            approval_requests=trace.approval_requests,
            approval_decisions=trace.approval_decisions,
            operations=trace.operations,
            resource_changes=trace.resource_changes,
            validations=trace.validations,
            recovery_decisions=trace.recovery_decisions,
            recovery_executions=trace.recovery_executions,
            checkpoints=trace.checkpoints,
            transactions=trace.transactions,
            outcome_evaluations=trace.outcome_evaluations,
            knowledge_updates=trace.knowledge_updates,
            memory_updates=trace.memory_updates,
            budget_events=trace.budget_events,
            warnings=trace.warnings,
            errors=trace.errors,
            stop_decision=trace.stop_decision,
            summary=trace.summary,
            started_at=trace.started_at,
            completed_at=trace.completed_at,
            duration_ms=trace.duration_ms,
            event_count=trace.event_count + len(frozen_events),
            source_event_ids=trace.source_event_ids,
            correlation_id=trace.correlation_id,
            metadata=updated_metadata,
            fingerprint=new_fingerprint,
        )
        return self._repository.save(updated)
