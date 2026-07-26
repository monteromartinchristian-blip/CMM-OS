"""Phase 9.19 – Agent Runtime Trace Event Normalizer.

Normalizes real Event Bus events, persisted events, state transitions,
and repository results into structured AgentTraceRecordKind records.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from cmm.agent_runtime.agent_trace_contracts import (
    AgentTraceApprovalDecision,
    AgentTraceApprovalRequest,
    AgentTraceBudgetEvent,
    AgentTraceCheckpoint,
    AgentTraceCognitiveProfile,
    AgentTraceError,
    AgentTraceInformationGap,
    AgentTraceIteration,
    AgentTraceKnowledgeLoad,
    AgentTraceKnowledgeUpdate,
    AgentTraceMemoryUpdate,
    AgentTraceObservation,
    AgentTraceOperation,
    AgentTraceOutcomeEvaluation,
    AgentTracePlanReference,
    AgentTracePolicyDecision,
    AgentTraceQuestion,
    AgentTraceRecoveryDecision,
    AgentTraceRecoveryExecution,
    AgentTraceResourceChange,
    AgentTraceRuntimeDecision,
    AgentTraceStopDecision,
    AgentTraceTransaction,
    AgentTraceValidation,
    AgentTraceWarning,
    _utcnow,
)
from cmm.agent_runtime.agent_trace_event_registry import AgentTraceEventRegistry
from cmm.agent_runtime.enums import AgentTraceRecordKind
from cmm.agent_runtime.errors import (
    AgentTraceContractError,
    AgentTraceSerializationError,
    AgentTraceUnsupportedEventError,
)


class AgentTraceEventNormalizer:
    """Normalizes events into structured trace records.

    Input: real Event Bus events, persisted events, state transitions,
           repository results.
    Output: normalized records of AgentTraceRecordKind.
    """

    def __init__(
        self,
        registry: AgentTraceEventRegistry | None = None,
        strict: bool = True,
    ) -> None:
        self._registry = registry or AgentTraceEventRegistry()
        self._strict = strict
        self._custom_normalizers: dict[str, Callable[[dict[str, Any]], Any]] = {}

    def register_normalizer(
        self, event_type: str, normalizer: Callable[[dict[str, Any]], Any]
    ) -> None:
        """Register a custom normalizer for a specific event type."""
        self._custom_normalizers[event_type] = normalizer

    def normalize(self, event: dict[str, Any]) -> Any:
        """Normalize a single event dict into a trace record.

        Args:
            event: The raw event dictionary.

        Returns:
            A normalized trace record dataclass instance.

        Raises:
            AgentTraceUnsupportedEventError: If the event type is unknown
                and strict mode is enabled.
            AgentTraceContractError: If required fields are missing.
            AgentTraceSerializationError: If payload cannot be frozen.
        """
        event_type = event.get("event_type", event.get("type", ""))
        if not event_type:
            raise AgentTraceContractError("Event must have an event_type or type field")

        # Check custom normalizers first
        if event_type in self._custom_normalizers:
            return self._custom_normalizers[event_type](event)

        # Look up record kind from registry
        record_kind = self._registry.resolve(event_type)
        if record_kind is None:
            if self._strict:
                raise AgentTraceUnsupportedEventError(
                    f"Unsupported event type: {event_type}"
                )
            return None

        # Delegate to kind-specific normalizer
        normalizer = self._get_kind_normalizer(record_kind)
        if normalizer is None:
            if self._strict:
                raise AgentTraceUnsupportedEventError(
                    f"No normalizer for record kind: {record_kind}"
                )
            return None

        try:
            return normalizer(event)
        except (ValueError, TypeError, KeyError) as exc:
            raise AgentTraceContractError(
                f"Failed to normalize event {event_type}: {exc}"
            ) from exc

    def normalize_batch(self, events: list[dict[str, Any]]) -> list[Any]:
        """Normalize a batch of events.

        Invalid events are skipped unless strict mode is enabled.
        """
        results: list[Any] = []
        for event in events:
            try:
                result = self.normalize(event)
                if result is not None:
                    results.append(result)
            except AgentTraceUnsupportedEventError:
                if self._strict:
                    raise
            except (AgentTraceContractError, AgentTraceSerializationError):
                if self._strict:
                    raise
        return results

    def _get_timestamp(self, event: dict[str, Any]) -> datetime:
        ts = event.get("timestamp") or event.get("created_at") or event.get("time")
        if isinstance(ts, str):
            return datetime.fromisoformat(ts)
        if isinstance(ts, datetime):
            return ts
        return _utcnow()

    def _get_kind_normalizer(
        self, kind: AgentTraceRecordKind
    ) -> Callable[[dict[str, Any]], Any] | None:
        mapping: dict[AgentTraceRecordKind, Callable] = {
            AgentTraceRecordKind.ITERATION: self._normalize_iteration,
            AgentTraceRecordKind.OBSERVATION: self._normalize_observation,
            AgentTraceRecordKind.KNOWLEDGE_LOAD: self._normalize_knowledge_load,
            AgentTraceRecordKind.COGNITIVE_PROFILE: self._normalize_cognitive_profile,
            AgentTraceRecordKind.INFORMATION_GAP: self._normalize_information_gap,
            AgentTraceRecordKind.QUESTION: self._normalize_question,
            AgentTraceRecordKind.RUNTIME_DECISION: self._normalize_runtime_decision,
            AgentTraceRecordKind.PLAN: self._normalize_plan,
            AgentTraceRecordKind.POLICY_DECISION: self._normalize_policy_decision,
            AgentTraceRecordKind.APPROVAL_REQUEST: self._normalize_approval_request,
            AgentTraceRecordKind.APPROVAL_DECISION: self._normalize_approval_decision,
            AgentTraceRecordKind.OPERATION: self._normalize_operation,
            AgentTraceRecordKind.RESOURCE_CHANGE: self._normalize_resource_change,
            AgentTraceRecordKind.VALIDATION: self._normalize_validation,
            AgentTraceRecordKind.RECOVERY_DECISION: self._normalize_recovery_decision,
            AgentTraceRecordKind.RECOVERY_EXECUTION: self._normalize_recovery_execution,
            AgentTraceRecordKind.CHECKPOINT: self._normalize_checkpoint,
            AgentTraceRecordKind.TRANSACTION: self._normalize_transaction,
            AgentTraceRecordKind.OUTCOME_EVALUATION: self._normalize_outcome_evaluation,
            AgentTraceRecordKind.KNOWLEDGE_UPDATE: self._normalize_knowledge_update,
            AgentTraceRecordKind.MEMORY_UPDATE: self._normalize_memory_update,
            AgentTraceRecordKind.BUDGET_EVENT: self._normalize_budget_event,
            AgentTraceRecordKind.WARNING: self._normalize_warning,
            AgentTraceRecordKind.ERROR: self._normalize_error,
            AgentTraceRecordKind.STOP_DECISION: self._normalize_stop_decision,
        }
        return mapping.get(kind)

    def _safe_str(self, d: dict[str, Any], *keys: str, default: str = "") -> str:
        for key in keys:
            val = d.get(key)
            if val is not None:
                return str(val)
        return default

    def _safe_int(self, d: dict[str, Any], *keys: str, default: int = 0) -> int:
        for key in keys:
            val = d.get(key)
            if val is not None:
                try:
                    return int(val)
                except (ValueError, TypeError):
                    pass
        return default

    def _safe_bool(self, d: dict[str, Any], *keys: str, default: bool = False) -> bool:
        for key in keys:
            val = d.get(key)
            if val is not None:
                return bool(val)
        return default

    def _safe_tuple(self, d: dict[str, Any], key: str) -> tuple[str, ...]:
        val = d.get(key, [])
        if isinstance(val, (list, tuple)):
            return tuple(str(v) for v in val)
        return ()

    def _safe_dict(self, d: dict[str, Any], key: str) -> dict[str, Any]:
        val = d.get(key, {})
        if isinstance(val, dict):
            return dict(val)
        return {}

    def _normalize_iteration(self, event: dict[str, Any]) -> AgentTraceIteration:
        return AgentTraceIteration(
            iteration_id=self._safe_str(event, "iteration_id", "id"),
            sequence=self._safe_int(event, "sequence", "seq"),
            started_at=self._get_timestamp(event),
            completed_at=event.get("completed_at"),
            initial_state=self._safe_str(event, "initial_state", "state_before"),
            final_state=self._safe_str(event, "final_state", "state_after"),
            record_ids=self._safe_tuple(event, "record_ids"),
            operation_ids=self._safe_tuple(event, "operation_ids"),
            validation_ids=self._safe_tuple(event, "validation_ids"),
            recovery_ids=self._safe_tuple(event, "recovery_ids"),
            budget_event_ids=self._safe_tuple(event, "budget_event_ids"),
            decision_id=self._safe_str(event, "decision_id"),
            continue_reason_codes=self._safe_tuple(event, "continue_reason_codes"),
            stop_reason_codes=self._safe_tuple(event, "stop_reason_codes"),
            warnings=self._safe_tuple(event, "warnings"),
            errors=self._safe_tuple(event, "errors"),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_observation(self, event: dict[str, Any]) -> AgentTraceObservation:
        return AgentTraceObservation(
            observation_id=self._safe_str(event, "observation_id", "id"),
            kind=self._safe_str(event, "kind", "observation_kind"),
            summary=self._safe_str(event, "summary", "description"),
            source=self._safe_str(event, "source"),
            significance=self._safe_str(event, "significance", default="info"),
            observation_ref=self._safe_str(event, "observation_ref", "ref"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_knowledge_load(
        self, event: dict[str, Any]
    ) -> AgentTraceKnowledgeLoad:
        return AgentTraceKnowledgeLoad(
            load_id=self._safe_str(event, "load_id", "id"),
            source=self._safe_str(event, "source"),
            knowledge_ids=self._safe_tuple(event, "knowledge_ids"),
            summary=self._safe_str(event, "summary"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_cognitive_profile(
        self, event: dict[str, Any]
    ) -> AgentTraceCognitiveProfile:
        return AgentTraceCognitiveProfile(
            profile_id=self._safe_str(event, "profile_id", "id"),
            profile_name=self._safe_str(event, "profile_name", "name"),
            strategy=self._safe_str(event, "strategy"),
            session_id=self._safe_str(event, "session_id"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_information_gap(
        self, event: dict[str, Any]
    ) -> AgentTraceInformationGap:
        return AgentTraceInformationGap(
            gap_id=self._safe_str(event, "gap_id", "id"),
            description=self._safe_str(event, "description", "summary"),
            strategy=self._safe_str(event, "strategy"),
            resolved=self._safe_bool(event, "resolved"),
            resolution_ref=self._safe_str(event, "resolution_ref"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_question(self, event: dict[str, Any]) -> AgentTraceQuestion:
        return AgentTraceQuestion(
            question_id=self._safe_str(event, "question_id", "id"),
            question_summary=self._safe_str(
                event, "question_summary", "summary", "question"
            ),
            asked_to=self._safe_str(event, "asked_to", "target"),
            answer_summary=self._safe_str(event, "answer_summary", "answer"),
            answered=self._safe_bool(event, "answered"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_runtime_decision(
        self, event: dict[str, Any]
    ) -> AgentTraceRuntimeDecision:
        return AgentTraceRuntimeDecision(
            decision_id=self._safe_str(event, "decision_id", "id"),
            decision_kind=self._safe_str(event, "decision_kind", "kind", "decision"),
            state_before=self._safe_str(event, "state_before"),
            state_after=self._safe_str(event, "state_after"),
            reason_codes=self._safe_tuple(event, "reason_codes"),
            policy_refs=self._safe_tuple(event, "policy_refs"),
            evidence_refs=self._safe_tuple(event, "evidence_refs"),
            approval_refs=self._safe_tuple(event, "approval_refs"),
            budget_refs=self._safe_tuple(event, "budget_refs"),
            validation_refs=self._safe_tuple(event, "validation_refs"),
            outcome_refs=self._safe_tuple(event, "outcome_refs"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_plan(self, event: dict[str, Any]) -> AgentTracePlanReference:
        return AgentTracePlanReference(
            plan_id=self._safe_str(event, "plan_id", "id"),
            plan_status=self._safe_str(event, "plan_status", "status"),
            operation_count=self._safe_int(event, "operation_count"),
            summary=self._safe_str(event, "summary"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_policy_decision(
        self, event: dict[str, Any]
    ) -> AgentTracePolicyDecision:
        return AgentTracePolicyDecision(
            policy_decision_id=self._safe_str(event, "policy_decision_id", "id"),
            decision=self._safe_str(event, "decision", "policy_decision"),
            policy_refs=self._safe_tuple(event, "policy_refs"),
            obligations=self._safe_tuple(event, "obligations"),
            summary=self._safe_str(event, "summary"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_approval_request(
        self, event: dict[str, Any]
    ) -> AgentTraceApprovalRequest:
        return AgentTraceApprovalRequest(
            approval_request_id=self._safe_str(event, "approval_request_id", "id"),
            requested_by=self._safe_str(event, "requested_by"),
            required_approvers=self._safe_tuple(event, "required_approvers"),
            status=self._safe_str(event, "status"),
            summary=self._safe_str(event, "summary"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_approval_decision(
        self, event: dict[str, Any]
    ) -> AgentTraceApprovalDecision:
        return AgentTraceApprovalDecision(
            approval_decision_id=self._safe_str(event, "approval_decision_id", "id"),
            approval_request_id=self._safe_str(event, "approval_request_id"),
            decided_by=self._safe_str(event, "decided_by"),
            decision=self._safe_str(event, "decision"),
            summary=self._safe_str(event, "summary"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_operation(self, event: dict[str, Any]) -> AgentTraceOperation:
        return AgentTraceOperation(
            operation_id=self._safe_str(event, "operation_id", "id"),
            operation_name=self._safe_str(event, "operation_name", "name"),
            status=self._safe_str(event, "status"),
            effect=self._safe_str(event, "effect"),
            summary=self._safe_str(event, "summary"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_resource_change(
        self, event: dict[str, Any]
    ) -> AgentTraceResourceChange:
        return AgentTraceResourceChange(
            change_id=self._safe_str(event, "change_id", "id"),
            resource=self._safe_str(event, "resource"),
            change_kind=self._safe_str(event, "change_kind", "kind"),
            summary=self._safe_str(event, "summary"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_validation(self, event: dict[str, Any]) -> AgentTraceValidation:
        return AgentTraceValidation(
            validation_id=self._safe_str(event, "validation_id", "id"),
            stage=self._safe_str(event, "stage"),
            status=self._safe_str(event, "status"),
            findings_count=self._safe_int(event, "findings_count"),
            summary=self._safe_str(event, "summary"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_recovery_decision(
        self, event: dict[str, Any]
    ) -> AgentTraceRecoveryDecision:
        return AgentTraceRecoveryDecision(
            recovery_decision_id=self._safe_str(event, "recovery_decision_id", "id"),
            strategy=self._safe_str(event, "strategy"),
            reason_codes=self._safe_tuple(event, "reason_codes"),
            retry_count=self._safe_int(event, "retry_count"),
            summary=self._safe_str(event, "summary"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_recovery_execution(
        self, event: dict[str, Any]
    ) -> AgentTraceRecoveryExecution:
        return AgentTraceRecoveryExecution(
            recovery_execution_id=self._safe_str(event, "recovery_execution_id", "id"),
            strategy=self._safe_str(event, "strategy"),
            status=self._safe_str(event, "status"),
            summary=self._safe_str(event, "summary"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_checkpoint(self, event: dict[str, Any]) -> AgentTraceCheckpoint:
        return AgentTraceCheckpoint(
            checkpoint_id=self._safe_str(event, "checkpoint_id", "id"),
            status=self._safe_str(event, "status"),
            integrity_status=self._safe_str(event, "integrity_status"),
            summary=self._safe_str(event, "summary"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_transaction(self, event: dict[str, Any]) -> AgentTraceTransaction:
        return AgentTraceTransaction(
            transaction_id=self._safe_str(event, "transaction_id", "id"),
            boundary_kind=self._safe_str(event, "boundary_kind", "kind"),
            status=self._safe_str(event, "status"),
            summary=self._safe_str(event, "summary"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_outcome_evaluation(
        self, event: dict[str, Any]
    ) -> AgentTraceOutcomeEvaluation:
        return AgentTraceOutcomeEvaluation(
            evaluation_id=self._safe_str(event, "evaluation_id", "id"),
            outcome=self._safe_str(event, "outcome"),
            completion_decision=self._safe_str(event, "completion_decision"),
            criteria_satisfied=self._safe_int(event, "criteria_satisfied"),
            criteria_total=self._safe_int(event, "criteria_total"),
            regressions=self._safe_int(event, "regressions"),
            warnings=self._safe_int(event, "warnings"),
            summary=self._safe_str(event, "summary"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_knowledge_update(
        self, event: dict[str, Any]
    ) -> AgentTraceKnowledgeUpdate:
        return AgentTraceKnowledgeUpdate(
            proposal_id=self._safe_str(event, "proposal_id", "id"),
            status=self._safe_str(event, "status"),
            additions=self._safe_int(event, "additions"),
            updates=self._safe_int(event, "updates"),
            invalidations=self._safe_int(event, "invalidations"),
            merges=self._safe_int(event, "merges"),
            rejections=self._safe_int(event, "rejections"),
            summary=self._safe_str(event, "summary"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_memory_update(self, event: dict[str, Any]) -> AgentTraceMemoryUpdate:
        return AgentTraceMemoryUpdate(
            memory_update_id=self._safe_str(event, "memory_update_id", "id"),
            decision=self._safe_str(event, "decision"),
            candidates_count=self._safe_int(event, "candidates_count"),
            written_count=self._safe_int(event, "written_count"),
            summary=self._safe_str(event, "summary"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_budget_event(self, event: dict[str, Any]) -> AgentTraceBudgetEvent:
        return AgentTraceBudgetEvent(
            budget_event_id=self._safe_str(event, "budget_event_id", "id"),
            event_kind=self._safe_str(event, "event_kind", "kind"),
            resource_type=self._safe_str(event, "resource_type"),
            amount=float(event.get("amount", 0.0)),
            remaining=float(event.get("remaining", 0.0)),
            summary=self._safe_str(event, "summary"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_warning(self, event: dict[str, Any]) -> AgentTraceWarning:
        return AgentTraceWarning(
            warning_id=self._safe_str(event, "warning_id", "id"),
            message=self._safe_str(event, "message"),
            source=self._safe_str(event, "source"),
            code=self._safe_str(event, "code"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_error(self, event: dict[str, Any]) -> AgentTraceError:
        return AgentTraceError(
            error_id=self._safe_str(event, "error_id", "id"),
            kind=self._safe_str(event, "kind", "error_kind"),
            safe_message=self._safe_str(event, "safe_message", "message"),
            error_code=self._safe_str(event, "error_code", "code"),
            operation_id=self._safe_str(event, "operation_id"),
            validation_id=self._safe_str(event, "validation_id"),
            recovery_id=self._safe_str(event, "recovery_id"),
            retryable=self._safe_bool(event, "retryable"),
            resolved=self._safe_bool(event, "resolved"),
            resolution_ref=self._safe_str(event, "resolution_ref"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )

    def _normalize_stop_decision(self, event: dict[str, Any]) -> AgentTraceStopDecision:
        return AgentTraceStopDecision(
            stop_decision_id=self._safe_str(event, "stop_decision_id", "id"),
            reason_codes=self._safe_tuple(event, "reason_codes"),
            goal_satisfied=self._safe_bool(event, "goal_satisfied"),
            outcome=self._safe_str(event, "outcome"),
            completion_decision=self._safe_str(event, "completion_decision"),
            summary=self._safe_str(event, "summary"),
            timestamp=self._get_timestamp(event),
            metadata=self._safe_dict(event, "metadata"),
        )
