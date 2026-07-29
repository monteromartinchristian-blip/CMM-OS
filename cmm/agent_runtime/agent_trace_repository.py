"""Phase 9.19 – Agent Runtime Trace Repository.

Persistent and in-memory storage for AgentTrace records with
query, pagination, idempotency, and thread safety.
"""

from __future__ import annotations

import threading

from cmm.agent_runtime.agent_trace_contracts import (
    AgentTrace,
    AgentTracePage,
    AgentTraceQuery,
    AgentTraceQueryResult,
)
from cmm.agent_runtime.enums import AgentTraceStatus
from cmm.agent_runtime.errors import (
    AgentTraceFinalizedError,
    AgentTraceNotFoundError,
)


class AgentTraceRepository:
    """Abstract interface for trace persistence."""

    def save(self, trace: AgentTrace) -> AgentTrace:
        raise NotImplementedError

    def get(self, trace_id: str) -> AgentTrace:
        raise NotImplementedError

    def get_by_agent_run(self, agent_run_id: str) -> AgentTrace | None:
        raise NotImplementedError

    def get_by_goal(self, goal_id: str) -> tuple[AgentTrace, ...]:
        raise NotImplementedError

    def query(self, query: AgentTraceQuery) -> AgentTraceQueryResult:
        raise NotImplementedError

    def list(
        self,
        limit: int = 100,
        cursor: str = "",
        status: str | None = None,
    ) -> AgentTracePage:
        raise NotImplementedError

    def archive(self, trace_id: str) -> AgentTrace:
        raise NotImplementedError

    def delete(self, trace_id: str) -> None:
        raise NotImplementedError


class InMemoryAgentTraceRepository(AgentTraceRepository):
    """Thread-safe in-memory implementation of AgentTraceRepository."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._traces: dict[str, AgentTrace] = {}
        self._versions: dict[str, list[AgentTrace]] = {}
        self._run_index: dict[str, str] = {}
        self._goal_index: dict[str, set[str]] = {}

    def save(self, trace: AgentTrace) -> AgentTrace:
        with self._lock:
            existing = self._traces.get(trace.trace_id)
            if existing is not None:
                # Always protect finalized traces from overwrite
                if existing.status in (
                    AgentTraceStatus.COMPLETE.value,
                    "COMPLETE",
                    AgentTraceStatus.ARCHIVED.value,
                    "ARCHIVED",
                ):
                    raise AgentTraceFinalizedError(
                        f"Cannot overwrite finalized trace '{trace.trace_id}'"
                    )
                # Idempotency only when fingerprints match and trace is non-final
                if (
                    existing.fingerprint
                    and trace.fingerprint
                    and existing.fingerprint == trace.fingerprint
                ):
                    return existing
                # Versioning: store previous version when not same fingerprint
                if trace.trace_id not in self._versions:
                    self._versions[trace.trace_id] = []
                if existing not in self._versions[trace.trace_id]:
                    self._versions[trace.trace_id].append(existing)

            self._traces[trace.trace_id] = trace
            self._run_index[trace.agent_run_id] = trace.trace_id
            if trace.goal_id not in self._goal_index:
                self._goal_index[trace.goal_id] = set()
            self._goal_index[trace.goal_id].add(trace.trace_id)
            return trace

    def get(self, trace_id: str) -> AgentTrace:
        with self._lock:
            trace = self._traces.get(trace_id)
            if trace is None:
                raise AgentTraceNotFoundError(f"Trace '{trace_id}' not found")
            return trace

    def get_by_agent_run(self, agent_run_id: str) -> AgentTrace | None:
        with self._lock:
            trace_id = self._run_index.get(agent_run_id)
            if trace_id is None:
                return None
            return self._traces.get(trace_id)

    def get_by_goal(self, goal_id: str) -> tuple[AgentTrace, ...]:
        with self._lock:
            trace_ids = self._goal_index.get(goal_id, set())
            return tuple(self._traces[tid] for tid in trace_ids if tid in self._traces)

    def query(self, query: AgentTraceQuery) -> AgentTraceQueryResult:
        with self._lock:
            results = list(self._traces.values())

            # Apply filters
            filters = query.filters
            if "status" in filters:
                results = [t for t in results if t.status == filters["status"]]
            if "agent_run_id" in filters:
                results = [
                    t for t in results if t.agent_run_id == filters["agent_run_id"]
                ]
            if "goal_id" in filters:
                results = [t for t in results if t.goal_id == filters["goal_id"]]
            if "agent_id" in filters:
                results = [t for t in results if t.agent_id == filters["agent_id"]]
            if filters.get("outcome"):
                results = [
                    t
                    for t in results
                    if t.stop_decision and t.stop_decision.outcome == filters["outcome"]
                ]

            # Sort
            reverse = query.sort.startswith("-")
            sort_key = query.sort.lstrip("-")
            if sort_key == "started_at":
                results.sort(key=lambda t: t.started_at, reverse=reverse)
            elif sort_key == "event_count":
                results.sort(key=lambda t: t.event_count, reverse=reverse)
            else:
                results.sort(key=lambda t: t.started_at, reverse=reverse)

            total = len(results)

            # Apply cursor-based pagination
            if query.cursor:
                cursor_idx = next(
                    (i for i, t in enumerate(results) if t.trace_id == query.cursor),
                    None,
                )
                if cursor_idx is not None:
                    results = results[cursor_idx + 1 :]

            # Apply limit
            results = results[: query.limit]

            next_cursor = (
                results[-1].trace_id
                if len(results) == query.limit and total > len(results)
                else ""
            )

            return AgentTraceQueryResult(
                traces=tuple(results),
                total=total,
                next_cursor=next_cursor,
            )

    def list(
        self,
        limit: int = 100,
        cursor: str = "",
        status: str | None = None,
    ) -> AgentTracePage:
        with self._lock:
            results = list(self._traces.values())
            if status:
                results = [t for t in results if t.status == status]
            results.sort(key=lambda t: t.started_at, reverse=True)

            # Find cursor position
            start = 0
            if cursor:
                for i, t in enumerate(results):
                    if t.trace_id == cursor:
                        start = i + 1
                        break

            page = results[start : start + limit]
            has_next = (start + limit) < len(results)

            return AgentTracePage(
                items=tuple(page),
                total=len(results),
                page=(start // limit) + 1,
                page_size=limit,
                has_next=has_next,
            )

    def archive(self, trace_id: str) -> AgentTrace:
        with self._lock:
            trace = self.get(trace_id)
            archived = AgentTrace(
                trace_id=trace.trace_id,
                agent_run_id=trace.agent_run_id,
                goal_id=trace.goal_id,
                goal_created_by=trace.goal_created_by,
                agent_id=trace.agent_id,
                workflow_id=trace.workflow_id,
                autonomy_level=trace.autonomy_level,
                status=AgentTraceStatus.ARCHIVED.value,
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
            self._traces[trace_id] = archived
            return archived

    def delete(self, trace_id: str) -> None:
        with self._lock:
            trace = self._traces.pop(trace_id, None)
            if trace is None:
                raise AgentTraceNotFoundError(f"Trace '{trace_id}' not found")
            self._run_index.pop(trace.agent_run_id, None)
            if trace.goal_id in self._goal_index:
                self._goal_index[trace.goal_id].discard(trace_id)

    def get_versions(self, trace_id: str) -> tuple[AgentTrace, ...]:
        """Return historical versions of a trace."""
        with self._lock:
            versions = list(self._versions.get(trace_id, []))
            current = self._traces.get(trace_id)
            if current:
                versions.append(current)
            return tuple(versions)

    def count(self) -> int:
        with self._lock:
            return len(self._traces)
