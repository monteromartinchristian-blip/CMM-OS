"""Phase 9.25 – Agent Security, Permissions, and Isolation Store.

In-memory consistent store for permission contexts, audit entries, and kill switch state.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from cmm.agent_runtime.agent_security_contracts import (
    AgentPermissionContext,
    KillSwitchReport,
    SecurityAuditEntry,
)
from cmm.agent_runtime.agent_security_errors import (
    InvalidSecurityContractError,
)


class InMemorySecurityStore:
    """
    Thread-safe in-memory store for security artifacts.

    Maintains indexes for fast lookups by agent, run, goal, and actor.
    Ensures idempotency by rejecting duplicates.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._permission_contexts: dict[str, AgentPermissionContext] = {}
        self._audit_entries: dict[str, SecurityAuditEntry] = {}
        self._kill_switch_report: KillSwitchReport | None = None

        # Indexes
        self._by_agent_id: dict[str, set[str]] = {}
        self._by_run_id: dict[str, set[str]] = {}
        self._by_goal_id: dict[str, set[str]] = {}
        self._by_actor_id: dict[str, set[str]] = {}

    # ── Permission Contexts ────────────────────────────────────────────────────

    def add_permission_context(self, context: AgentPermissionContext) -> None:
        """Add a permission context. Raises on duplicate ID."""
        with self._lock:
            if context.id in self._permission_contexts:
                raise InvalidSecurityContractError(
                    f"Duplicate permission context ID: {context.id}",
                    {"field": "id", "value": context.id},
                )
            self._permission_contexts[context.id] = context
            self._by_agent_id.setdefault(context.agent_id, set()).add(context.id)
            self._by_run_id.setdefault(context.agent_run_id, set()).add(context.id)
            self._by_goal_id.setdefault(context.goal_id, set()).add(context.id)
            self._by_actor_id.setdefault(context.actor_id, set()).add(context.id)

    def get_permission_context(self, context_id: str) -> AgentPermissionContext | None:
        """Get a permission context by ID."""
        with self._lock:
            return self._permission_contexts.get(context_id)

    def get_permission_contexts_for_agent(
        self, agent_id: str
    ) -> tuple[AgentPermissionContext, ...]:
        """Get all contexts for an agent."""
        with self._lock:
            ids = self._by_agent_id.get(agent_id, set())
            return tuple(self._permission_contexts[cid] for cid in sorted(ids))

    def get_permission_contexts_for_run(
        self, run_id: str
    ) -> tuple[AgentPermissionContext, ...]:
        """Get all contexts for a run."""
        with self._lock:
            ids = self._by_run_id.get(run_id, set())
            return tuple(self._permission_contexts[cid] for cid in sorted(ids))

    def get_permission_contexts_for_goal(
        self, goal_id: str
    ) -> tuple[AgentPermissionContext, ...]:
        """Get all contexts for a goal."""
        with self._lock:
            ids = self._by_goal_id.get(goal_id, set())
            return tuple(self._permission_contexts[cid] for cid in sorted(ids))

    def get_permission_contexts_for_actor(
        self, actor_id: str
    ) -> tuple[AgentPermissionContext, ...]:
        """Get all contexts for an actor."""
        with self._lock:
            ids = self._by_actor_id.get(actor_id, set())
            return tuple(self._permission_contexts[cid] for cid in sorted(ids))

    def list_active_permission_contexts(
        self, as_of: datetime | None = None
    ) -> tuple[AgentPermissionContext, ...]:
        """List all non-expired contexts."""
        with self._lock:
            if as_of is None:
                as_of = datetime.now(timezone.utc)
            return tuple(
                ctx
                for ctx in self._permission_contexts.values()
                if ctx.expires_at is None or ctx.expires_at > as_of
            )

    def list_expired_permission_contexts(
        self, as_of: datetime | None = None
    ) -> tuple[AgentPermissionContext, ...]:
        """List all expired contexts."""
        with self._lock:
            if as_of is None:
                as_of = datetime.now(timezone.utc)
            return tuple(
                ctx
                for ctx in self._permission_contexts.values()
                if ctx.expires_at is not None and ctx.expires_at <= as_of
            )

    def update_permission_context(self, context: AgentPermissionContext) -> None:
        """Update an existing context (same ID)."""
        with self._lock:
            if context.id not in self._permission_contexts:
                raise InvalidSecurityContractError(
                    f"Permission context not found: {context.id}",
                    {"field": "id", "value": context.id},
                )
            old = self._permission_contexts[context.id]
            self._permission_contexts[context.id] = context
            # Update indexes if identity fields changed
            if old.agent_id != context.agent_id:
                self._by_agent_id.get(old.agent_id, set()).discard(context.id)
                self._by_agent_id.setdefault(context.agent_id, set()).add(context.id)
            if old.agent_run_id != context.agent_run_id:
                self._by_run_id.get(old.agent_run_id, set()).discard(context.id)
                self._by_run_id.setdefault(context.agent_run_id, set()).add(context.id)
            if old.goal_id != context.goal_id:
                self._by_goal_id.get(old.goal_id, set()).discard(context.id)
                self._by_goal_id.setdefault(context.goal_id, set()).add(context.id)
            if old.actor_id != context.actor_id:
                self._by_actor_id.get(old.actor_id, set()).discard(context.id)
                self._by_actor_id.setdefault(context.actor_id, set()).add(context.id)

    def delete_permission_context(self, context_id: str) -> None:
        """Delete a permission context."""
        with self._lock:
            ctx = self._permission_contexts.pop(context_id, None)
            if ctx is not None:
                self._by_agent_id.get(ctx.agent_id, set()).discard(context_id)
                self._by_run_id.get(ctx.agent_run_id, set()).discard(context_id)
                self._by_goal_id.get(ctx.goal_id, set()).discard(context_id)
                self._by_actor_id.get(ctx.actor_id, set()).discard(context_id)

    # ── Audit Entries ──────────────────────────────────────────────────────────

    def add_audit_entry(self, entry: SecurityAuditEntry) -> None:
        """Add an audit entry. Raises on duplicate ID."""
        with self._lock:
            if entry.id in self._audit_entries:
                raise InvalidSecurityContractError(
                    f"Duplicate audit entry ID: {entry.id}",
                    {"field": "id", "value": entry.id},
                )
            self._audit_entries[entry.id] = entry

    def get_audit_entry(self, entry_id: str) -> SecurityAuditEntry | None:
        """Get an audit entry by ID."""
        with self._lock:
            return self._audit_entries.get(entry_id)

    def get_audit_entries_for_run(self, run_id: str) -> tuple[SecurityAuditEntry, ...]:
        """Get all audit entries for a run."""
        with self._lock:
            return tuple(
                e for e in self._audit_entries.values() if e.agent_run_id == run_id
            )

    def get_audit_entries_for_goal(
        self, goal_id: str
    ) -> tuple[SecurityAuditEntry, ...]:
        """Get all audit entries for a goal."""
        with self._lock:
            return tuple(
                e for e in self._audit_entries.values() if e.goal_id == goal_id
            )

    def get_audit_entries_by_decision(
        self, decision: str
    ) -> tuple[SecurityAuditEntry, ...]:
        """Get audit entries by decision effect."""
        with self._lock:
            return tuple(
                e for e in self._audit_entries.values() if e.decision.value == decision
            )

    # ── Kill Switch ────────────────────────────────────────────────────────────

    def set_kill_switch_report(self, report: KillSwitchReport) -> None:
        """Set the global kill switch report."""
        with self._lock:
            self._kill_switch_report = report

    def get_kill_switch_report(self) -> KillSwitchReport | None:
        """Get the current kill switch report."""
        with self._lock:
            return self._kill_switch_report

    # ── Utility ────────────────────────────────────────────────────────────────

    def clear(self) -> None:
        """Clear all data."""
        with self._lock:
            self._permission_contexts.clear()
            self._audit_entries.clear()
            self._kill_switch_report = None
            self._by_agent_id.clear()
            self._by_run_id.clear()
            self._by_goal_id.clear()
            self._by_actor_id.clear()

    def count_permission_contexts(self) -> int:
        with self._lock:
            return len(self._permission_contexts)

    def count_audit_entries(self) -> int:
        with self._lock:
            return len(self._audit_entries)


# Public type alias (duck-typing friendly)
SecurityStore = InMemorySecurityStore

__all__ = ["InMemorySecurityStore", "SecurityStore"]
