"""Phase 9.19 – Agent Runtime Trace Assembler.

Constructs an AgentTrace from an agent_run, goal, assigned agent,
event stream, repositories, runtime transitions, outcome evaluation,
and knowledge update result.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

from cmm.agent_runtime.agent_trace_contracts import (
    AgentTrace,
    _utcnow,
)
from cmm.agent_runtime.agent_trace_event_normalizer import AgentTraceEventNormalizer
from cmm.agent_runtime.agent_trace_integrity import AgentTraceIntegrityVerifier
from cmm.agent_runtime.agent_trace_summary_builder import AgentTraceSummaryBuilder
from cmm.agent_runtime.enums import (
    AgentAutonomyLevel,
    AgentTraceIntegrityStatus,
    AgentTraceStatus,
)
from cmm.agent_runtime.errors import (
    AgentTraceContractError,
    AgentTraceIntegrityError,
)


class AgentTraceAssembler:
    """Assembles a complete AgentTrace from raw events and context.

    Flow:
    1. Validate context
    2. Load events by agent_run_id
    3. Deterministic sort
    4. Deduplicate event_id
    5. Verify correlation/causation
    6. Normalize
    7. Redact
    8. Classify record kinds
    9. Group by iteration_id
    10. Resolve references
    11. Build summary
    12. Calculate duration
    13. Calculate fingerprint
    14. Verify integrity
    15. Return built trace
    """

    def __init__(
        self,
        normalizer: AgentTraceEventNormalizer | None = None,
        integrity_verifier: AgentTraceIntegrityVerifier | None = None,
        summary_builder: AgentTraceSummaryBuilder | None = None,
    ) -> None:
        self._normalizer = normalizer or AgentTraceEventNormalizer()
        self._integrity_verifier = integrity_verifier or AgentTraceIntegrityVerifier()
        self._summary_builder = summary_builder or AgentTraceSummaryBuilder()

    def assemble(
        self,
        trace_id: str,
        agent_run_id: str,
        goal_id: str,
        goal_created_by: str = "",
        agent_id: str = "",
        workflow_id: str = "",
        autonomy_level: AgentAutonomyLevel | int = AgentAutonomyLevel.ANALYZE_ONLY,
        events: Sequence[dict[str, Any]] | None = None,
        correlation_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AgentTrace:
        """Assemble a trace from context and raw events."""
        if not trace_id:
            raise AgentTraceContractError("trace_id is required")
        if not agent_run_id:
            raise AgentTraceContractError("agent_run_id is required")
        if not goal_id:
            raise AgentTraceContractError("goal_id is required")

        # 1. Normalize events
        normalized = self._normalize_events(list(events) if events else [])

        # 2. Sort deterministically by timestamp then event_id
        sorted_records = self._sort_records(normalized)

        # 3. Deduplicate by record ID
        deduped = self._deduplicate(sorted_records)

        # 4. Classify into categories
        classified = self._classify_records(deduped)

        # 5. Calculate duration
        started_at = classified.get("started_at", _utcnow())
        completed_at = classified.get("completed_at")
        duration_ms = None
        if started_at and completed_at:
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)

        # 6. Compute event count and source_event_ids from deduplicated records.
        # Contract (phase-9-agent-runtime-trace.md §Integrity): event_count must
        # match source_event_ids count, both computed AFTER deduplication.
        event_count = len(deduped)
        source_event_ids = tuple(self._extract_record_id(rec) for rec in deduped)

        # 7. Build trace
        trace = AgentTrace(
            trace_id=trace_id,
            agent_run_id=agent_run_id,
            goal_id=goal_id,
            goal_created_by=goal_created_by,
            agent_id=agent_id,
            workflow_id=workflow_id,
            autonomy_level=autonomy_level,
            status=AgentTraceStatus.BUILDING.value,
            iterations=classified.get("iterations", ()),
            observations=classified.get("observations", ()),
            knowledge_loads=classified.get("knowledge_loads", ()),
            cognitive_profiles=classified.get("cognitive_profiles", ()),
            information_gaps=classified.get("information_gaps", ()),
            questions=classified.get("questions", ()),
            reasoning_result_ids=classified.get("reasoning_result_ids", ()),
            runtime_decisions=classified.get("runtime_decisions", ()),
            plans=classified.get("plans", ()),
            policy_decisions=classified.get("policy_decisions", ()),
            approval_requests=classified.get("approval_requests", ()),
            approval_decisions=classified.get("approval_decisions", ()),
            operations=classified.get("operations", ()),
            resource_changes=classified.get("resource_changes", ()),
            validations=classified.get("validations", ()),
            recovery_decisions=classified.get("recovery_decisions", ()),
            recovery_executions=classified.get("recovery_executions", ()),
            checkpoints=classified.get("checkpoints", ()),
            transactions=classified.get("transactions", ()),
            outcome_evaluations=classified.get("outcome_evaluations", ()),
            knowledge_updates=classified.get("knowledge_updates", ()),
            memory_updates=classified.get("memory_updates", ()),
            budget_events=classified.get("budget_events", ()),
            warnings=classified.get("warnings", ()),
            errors=classified.get("errors", ()),
            stop_decision=classified.get("stop_decision"),
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            event_count=event_count,
            source_event_ids=source_event_ids,
            correlation_id=correlation_id,
            metadata=dict(metadata or {}),
        )

        # 8. Build summary
        if trace.stop_decision or trace.iterations:
            summary = self._summary_builder.build(trace)
            trace = AgentTrace(
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
                summary=summary,
                started_at=trace.started_at,
                completed_at=trace.completed_at,
                duration_ms=trace.duration_ms,
                event_count=trace.event_count,
                source_event_ids=trace.source_event_ids,
                correlation_id=trace.correlation_id,
                metadata=trace.metadata,
                fingerprint=trace.fingerprint,
            )

        # 9. Compute fingerprint
        status_part = trace.status or ""
        completed_part = (trace.completed_at or _utcnow()).isoformat()
        stop_part = trace.stop_decision.stop_decision_id if trace.stop_decision else ""
        fingerprint_input = "|".join(
            [
                trace.trace_id,
                trace.agent_run_id,
                trace.goal_id,
                str(trace.event_count),
                status_part,
                completed_part,
                stop_part,
            ]
        )
        fingerprint = hashlib.sha256(fingerprint_input.encode("utf-8")).hexdigest()[:32]
        trace = AgentTrace(
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
            event_count=trace.event_count,
            source_event_ids=trace.source_event_ids,
            correlation_id=trace.correlation_id,
            metadata=trace.metadata,
            fingerprint=fingerprint,
        )

        # 10. Verify integrity
        report = self._integrity_verifier.verify(trace)
        if report.status == AgentTraceIntegrityStatus.CORRUPTED.value:
            raise AgentTraceIntegrityError(
                f"Trace integrity check failed: {', '.join(report.issues)}"
            )

        # 11. Update status
        if trace.stop_decision:
            final_status = AgentTraceStatus.COMPLETE.value
        elif trace.errors:
            final_status = AgentTraceStatus.FAILED.value
        elif trace.event_count > 0 and not trace.stop_decision:
            final_status = AgentTraceStatus.PARTIAL.value
        else:
            final_status = AgentTraceStatus.BUILDING.value

        trace = AgentTrace(
            trace_id=trace.trace_id,
            agent_run_id=trace.agent_run_id,
            goal_id=trace.goal_id,
            goal_created_by=trace.goal_created_by,
            agent_id=trace.agent_id,
            workflow_id=trace.workflow_id,
            autonomy_level=trace.autonomy_level,
            status=final_status,
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
            event_count=trace.event_count,
            source_event_ids=trace.source_event_ids,
            correlation_id=trace.correlation_id,
            metadata=trace.metadata,
            fingerprint=trace.fingerprint,
        )

        return trace

    def _normalize_events(self, events: list[dict[str, Any]]) -> list[Any]:
        return self._normalizer.normalize_batch(events)

    # Field priority for extracting a stable record ID from any normalized
    # AgentTrace* dataclass. Listed by kind-specific primary key.
    _RECORD_ID_FIELDS: tuple[str, ...] = (
        "iteration_id",
        "observation_id",
        "load_id",
        "profile_id",
        "gap_id",
        "question_id",
        "reasoning_result_id",
        "decision_id",
        "plan_id",
        "policy_decision_id",
        "approval_request_id",
        "approval_decision_id",
        "operation_id",
        "change_id",
        "validation_id",
        "recovery_decision_id",
        "recovery_execution_id",
        "checkpoint_id",
        "transaction_id",
        "evaluation_id",
        "proposal_id",
        "memory_update_id",
        "budget_event_id",
        "warning_id",
        "error_id",
        "stop_decision_id",
        "event_id",
        "record_id",
    )

    def _extract_record_id(self, record: Any) -> str:
        """Extract a stable, deterministic ID from any normalized record."""
        for field_name in self._RECORD_ID_FIELDS:
            value = getattr(record, field_name, None)
            if value:
                return str(value)
        # Fallback: object identity (stable per process), only if no real ID.
        return str(id(record))

    def _sort_records(self, records: list[Any]) -> list[Any]:
        """Sort records deterministically by timestamp then by id."""

        def _sort_key(record: Any) -> tuple:
            ts = getattr(record, "timestamp", _utcnow())
            rid = self._extract_record_id(record)
            return (ts.isoformat() if hasattr(ts, "isoformat") else str(ts), str(rid))

        return sorted(records, key=_sort_key)

    def _deduplicate(self, records: list[Any]) -> list[Any]:
        seen: set[str] = set()
        result: list[Any] = []
        for record in records:
            rid = self._extract_record_id(record)
            if rid not in seen:
                seen.add(rid)
                result.append(record)
        return result

    def _classify_records(self, records: list[Any]) -> dict[str, Any]:
        """Classify normalized records into trace fields."""
        result: dict[str, Any] = {
            "iterations": [],
            "observations": [],
            "knowledge_loads": [],
            "cognitive_profiles": [],
            "information_gaps": [],
            "questions": [],
            "reasoning_result_ids": [],
            "runtime_decisions": [],
            "plans": [],
            "policy_decisions": [],
            "approval_requests": [],
            "approval_decisions": [],
            "operations": [],
            "resource_changes": [],
            "validations": [],
            "recovery_decisions": [],
            "recovery_executions": [],
            "checkpoints": [],
            "transactions": [],
            "outcome_evaluations": [],
            "knowledge_updates": [],
            "memory_updates": [],
            "budget_events": [],
            "warnings": [],
            "errors": [],
            "stop_decision": None,
            "started_at": None,
            "completed_at": None,
        }
        for record in records:
            class_name = type(record).__name__
            if class_name == "AgentTraceIteration":
                result["iterations"].append(record)
                if result["started_at"] is None or (
                    hasattr(record, "started_at")
                    and record.started_at < result["started_at"]
                ):
                    result["started_at"] = record.started_at
                if (
                    hasattr(record, "completed_at")
                    and record.completed_at
                    and (
                        result["completed_at"] is None
                        or record.completed_at > result["completed_at"]
                    )
                ):
                    result["completed_at"] = record.completed_at
            elif class_name == "AgentTraceObservation":
                result["observations"].append(record)
            elif class_name == "AgentTraceKnowledgeLoad":
                result["knowledge_loads"].append(record)
            elif class_name == "AgentTraceCognitiveProfile":
                result["cognitive_profiles"].append(record)
            elif class_name == "AgentTraceInformationGap":
                result["information_gaps"].append(record)
            elif class_name == "AgentTraceQuestion":
                result["questions"].append(record)
            elif class_name == "AgentTraceRuntimeDecision":
                result["runtime_decisions"].append(record)
            elif class_name == "AgentTracePlanReference":
                result["plans"].append(record)
            elif class_name == "AgentTracePolicyDecision":
                result["policy_decisions"].append(record)
            elif class_name == "AgentTraceApprovalRequest":
                result["approval_requests"].append(record)
            elif class_name == "AgentTraceApprovalDecision":
                result["approval_decisions"].append(record)
            elif class_name == "AgentTraceOperation":
                result["operations"].append(record)
            elif class_name == "AgentTraceResourceChange":
                result["resource_changes"].append(record)
            elif class_name == "AgentTraceValidation":
                result["validations"].append(record)
            elif class_name == "AgentTraceRecoveryDecision":
                result["recovery_decisions"].append(record)
            elif class_name == "AgentTraceRecoveryExecution":
                result["recovery_executions"].append(record)
            elif class_name == "AgentTraceCheckpoint":
                result["checkpoints"].append(record)
            elif class_name == "AgentTraceTransaction":
                result["transactions"].append(record)
            elif class_name == "AgentTraceOutcomeEvaluation":
                result["outcome_evaluations"].append(record)
            elif class_name == "AgentTraceKnowledgeUpdate":
                result["knowledge_updates"].append(record)
            elif class_name == "AgentTraceMemoryUpdate":
                result["memory_updates"].append(record)
            elif class_name == "AgentTraceBudgetEvent":
                result["budget_events"].append(record)
            elif class_name == "AgentTraceWarning":
                result["warnings"].append(record)
            elif class_name == "AgentTraceError":
                result["errors"].append(record)
            elif class_name == "AgentTraceStopDecision":
                result["stop_decision"] = record

        # Convert lists to tuples
        for key in list(result.keys()):
            if isinstance(result[key], list):
                result[key] = tuple(result[key])

        return result
