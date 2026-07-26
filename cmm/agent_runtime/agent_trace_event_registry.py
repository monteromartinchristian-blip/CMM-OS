"""Phase 9.19 – Agent Runtime Trace Event Registry.

Maps events from phases 9.1–9.18 to AgentTraceRecordKind values.
Explicit mapping only; no fallback to UNKNOWN as success.
"""

from __future__ import annotations

from cmm.agent_runtime.enums import AgentTraceRecordKind


class AgentTraceEventRegistry:
    """Maps event type strings to AgentTraceRecordKind values.

    The registry is immutable after initialization.  Unknown event types
    return None (caller must decide whether to reject or store as unsupported).
    """

    def __init__(self) -> None:
        self._mapping: dict[str, AgentTraceRecordKind] = {}
        self._aliases: dict[str, str] = {}
        self._build_default_mapping()

    def _build_default_mapping(self) -> None:
        """Build the default mapping of event types to record kinds.

        Covers events from phases 9.1 through 9.18.
        """
        # ── Phase 9.1 – Agent Runtime ──────────────────────────────────────
        self.register("agent_run.created", AgentTraceRecordKind.HEADER)
        self.register("agent_run.started", AgentTraceRecordKind.HEADER)
        self.register("agent_run.completed", AgentTraceRecordKind.HEADER)
        self.register("agent_run.failed", AgentTraceRecordKind.HEADER)
        self.register("agent_run.cancelled", AgentTraceRecordKind.HEADER)
        self.register("runtime_decision", AgentTraceRecordKind.RUNTIME_DECISION)

        # ── Phase 9.2 – Goal System ────────────────────────────────────────
        self.register("goal.created", AgentTraceRecordKind.HEADER)
        self.register("goal.accepted", AgentTraceRecordKind.HEADER)
        self.register("goal.completed", AgentTraceRecordKind.HEADER)
        self.register("goal.failed", AgentTraceRecordKind.HEADER)

        # ── Phase 9.3 – Goal Intake ────────────────────────────────────────
        self.register("goal_proposal.created", AgentTraceRecordKind.HEADER)
        self.register("goal_proposal.accepted", AgentTraceRecordKind.HEADER)
        self.register("goal_proposal.rejected", AgentTraceRecordKind.HEADER)

        # ── Phase 9.4 – Observation Engine ─────────────────────────────────
        self.register("observation.created", AgentTraceRecordKind.OBSERVATION)
        self.register("observation.completed", AgentTraceRecordKind.OBSERVATION)
        self.register("observation.snapshot", AgentTraceRecordKind.OBSERVATION)
        self.register("observation.change_detected", AgentTraceRecordKind.OBSERVATION)

        # ── Phase 9.5 – Cognitive Adapter ──────────────────────────────────
        self.register("cognitive.requested", AgentTraceRecordKind.COGNITIVE_PROFILE)
        self.register("cognitive.completed", AgentTraceRecordKind.COGNITIVE_PROFILE)
        self.register("cognitive.profile_used", AgentTraceRecordKind.COGNITIVE_PROFILE)
        self.register("cognitive.result", AgentTraceRecordKind.REASONING_REFERENCE)

        # ── Phase 9.6 – Information Acquisition ────────────────────────────
        self.register("information_gap.detected", AgentTraceRecordKind.INFORMATION_GAP)
        self.register("information_gap.resolved", AgentTraceRecordKind.INFORMATION_GAP)
        self.register("question.asked", AgentTraceRecordKind.QUESTION)
        self.register("question.answered", AgentTraceRecordKind.QUESTION)
        self.register("knowledge.loaded", AgentTraceRecordKind.KNOWLEDGE_LOAD)

        # ── Phase 9.7 – Workflow Planner ───────────────────────────────────
        self.register("plan.created", AgentTraceRecordKind.PLAN)
        self.register("plan.validated", AgentTraceRecordKind.PLAN)
        self.register("plan.approved", AgentTraceRecordKind.PLAN)
        self.register("plan.replanning", AgentTraceRecordKind.PLAN)

        # ── Phase 9.8 – Policy Engine ──────────────────────────────────────
        self.register("policy.evaluated", AgentTraceRecordKind.POLICY_DECISION)
        self.register("policy.decision", AgentTraceRecordKind.POLICY_DECISION)
        self.register("policy.violation", AgentTraceRecordKind.POLICY_DECISION)

        # ── Phase 9.9 – Autonomy Level ─────────────────────────────────────
        self.register("autonomy.evaluated", AgentTraceRecordKind.RUNTIME_DECISION)
        self.register("autonomy.transition", AgentTraceRecordKind.RUNTIME_DECISION)

        # ── Phase 9.10 – Human Approval ────────────────────────────────────
        self.register("approval.requested", AgentTraceRecordKind.APPROVAL_REQUEST)
        self.register("approval.decided", AgentTraceRecordKind.APPROVAL_DECISION)
        self.register("approval.expired", AgentTraceRecordKind.APPROVAL_REQUEST)

        # ── Phase 9.11 – Action Budget ─────────────────────────────────────
        self.register("budget.reserved", AgentTraceRecordKind.BUDGET_EVENT)
        self.register("budget.confirmed", AgentTraceRecordKind.BUDGET_EVENT)
        self.register("budget.released", AgentTraceRecordKind.BUDGET_EVENT)
        self.register("budget.exceeded", AgentTraceRecordKind.BUDGET_EVENT)
        self.register("budget.consumed", AgentTraceRecordKind.BUDGET_EVENT)

        # ── Phase 9.12 – Runtime Loop ──────────────────────────────────────
        self.register("iteration.started", AgentTraceRecordKind.ITERATION)
        self.register("iteration.completed", AgentTraceRecordKind.ITERATION)
        self.register("runtime.transition", AgentTraceRecordKind.RUNTIME_DECISION)
        self.register("runtime.heartbeat", AgentTraceRecordKind.HEADER)

        # ── Phase 9.13 – Operation Execution ───────────────────────────────
        self.register("operation.started", AgentTraceRecordKind.OPERATION)
        self.register("operation.completed", AgentTraceRecordKind.OPERATION)
        self.register("operation.failed", AgentTraceRecordKind.OPERATION)
        self.register("resource.changed", AgentTraceRecordKind.RESOURCE_CHANGE)

        # ── Phase 9.14 – Validation Integration ────────────────────────────
        self.register("validation.started", AgentTraceRecordKind.VALIDATION)
        self.register("validation.completed", AgentTraceRecordKind.VALIDATION)
        self.register("validation.failed", AgentTraceRecordKind.VALIDATION)

        # ── Phase 9.15 – Checkpoints & Transactions ────────────────────────
        self.register("checkpoint.created", AgentTraceRecordKind.CHECKPOINT)
        self.register("checkpoint.restored", AgentTraceRecordKind.CHECKPOINT)
        self.register("transaction.started", AgentTraceRecordKind.TRANSACTION)
        self.register("transaction.committed", AgentTraceRecordKind.TRANSACTION)
        self.register("transaction.rolled_back", AgentTraceRecordKind.TRANSACTION)

        # ── Phase 9.16 – Recovery Manager ──────────────────────────────────
        self.register("recovery.decided", AgentTraceRecordKind.RECOVERY_DECISION)
        self.register("recovery.executed", AgentTraceRecordKind.RECOVERY_EXECUTION)
        self.register("recovery.failed", AgentTraceRecordKind.RECOVERY_EXECUTION)

        # ── Phase 9.17 – Outcome Evaluation ────────────────────────────────
        self.register("outcome.evaluated", AgentTraceRecordKind.OUTCOME_EVALUATION)
        self.register("outcome.completed", AgentTraceRecordKind.OUTCOME_EVALUATION)
        self.register("goal.completion_decided", AgentTraceRecordKind.STOP_DECISION)

        # ── Phase 9.18 – Knowledge & Memory Update ─────────────────────────
        self.register("knowledge.proposed", AgentTraceRecordKind.KNOWLEDGE_UPDATE)
        self.register("knowledge.applied", AgentTraceRecordKind.KNOWLEDGE_UPDATE)
        self.register("knowledge.rejected", AgentTraceRecordKind.KNOWLEDGE_UPDATE)
        self.register("memory.written", AgentTraceRecordKind.MEMORY_UPDATE)
        self.register("memory.rejected", AgentTraceRecordKind.MEMORY_UPDATE)

        # ── Warnings and Errors ────────────────────────────────────────────
        self.register("warning", AgentTraceRecordKind.WARNING)
        self.register("error", AgentTraceRecordKind.ERROR)
        self.register("runtime.warning", AgentTraceRecordKind.WARNING)
        self.register("runtime.error", AgentTraceRecordKind.ERROR)

        # ── Aliases ────────────────────────────────────────────────────────
        self.register_alias("agent_run.started", "run.started")
        self.register_alias("agent_run.completed", "run.completed")
        self.register_alias("observation.created", "obs.created")
        self.register_alias("policy.evaluated", "policy.evaluation")
        self.register_alias("approval.requested", "approval.create")
        self.register_alias("budget.reserved", "budget.reserve")
        self.register_alias("operation.started", "op.started")
        self.register_alias("operation.completed", "op.completed")
        self.register_alias("validation.started", "val.started")
        self.register_alias("validation.completed", "val.completed")

    def register(self, event_type: str, kind: AgentTraceRecordKind) -> None:
        """Register a mapping from event_type to record kind."""
        if event_type in self._mapping:
            raise ValueError(
                f"Duplicate event type registration: {event_type} "
                f"(existing: {self._mapping[event_type]})"
            )
        self._mapping[event_type] = kind

    def register_alias(self, canonical: str, alias: str) -> None:
        """Register an alias for a canonical event type."""
        if canonical not in self._mapping:
            raise ValueError(
                f"Cannot register alias '{alias}' for unknown canonical '{canonical}'"
            )
        if alias in self._aliases:
            raise ValueError(f"Duplicate alias registration: {alias}")
        self._aliases[alias] = canonical

    def resolve(self, event_type: str) -> AgentTraceRecordKind | None:
        """Resolve an event type to its record kind.

        Returns None if the event type is unknown.
        """
        if event_type in self._mapping:
            return self._mapping[event_type]
        canonical = self._aliases.get(event_type)
        if canonical is not None:
            return self._mapping.get(canonical)
        return None

    def known_event_types(self) -> frozenset[str]:
        """Return all registered event types (canonical only)."""
        return frozenset(self._mapping.keys())

    def known_aliases(self) -> frozenset[str]:
        """Return all registered aliases."""
        return frozenset(self._aliases.keys())

    def __contains__(self, event_type: str) -> bool:
        return event_type in self._mapping or event_type in self._aliases
