"""Phase 9.20 – Runtime Event Replay.

Controlled event replay with filtering, dry-run, and chronological ordering.
"""

from __future__ import annotations

from typing import Any

from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventReplayRequest,
    AgentRuntimeEventReplayResult,
)


class AgentRuntimeEventReplayer:
    """Replays events from a repository with filtering and safety."""

    def __init__(self, repository: Any) -> None:
        self._repository = repository

    def replay(
        self, request: AgentRuntimeEventReplayRequest
    ) -> AgentRuntimeEventReplayResult:
        """Execute a controlled event replay."""
        events = self._gather_events(request)
        replayed: list[AgentRuntimeEvent] = []
        errors: list[str] = []
        skipped = 0
        failed = 0

        if request.dry_run:
            return AgentRuntimeEventReplayResult(
                replayed_count=0,
                skipped_count=len(events),
                failed_count=0,
                events=[],
                errors=[],
                dry_run=True,
            )

        seen_ids: set = set()
        for event in events:
            event_id = event.header.event_id
            if event_id in seen_ids:
                skipped += 1
                continue
            seen_ids.add(event_id)

            try:
                self._repository.save(event)
                replayed.append(event)
            except (RuntimeError, ValueError, TypeError) as exc:
                errors.append(str(exc))
                failed += 1

        return AgentRuntimeEventReplayResult(
            replayed_count=len(replayed),
            skipped_count=skipped,
            failed_count=failed,
            events=replayed,
            errors=errors,
            dry_run=request.dry_run,
        )

    def _gather_events(
        self, request: AgentRuntimeEventReplayRequest
    ) -> list[AgentRuntimeEvent]:
        """Collect events matching the replay request."""
        query: dict[str, Any] = {}
        if request.event_type:
            query["event_type"] = request.event_type
        if request.agent_run_id:
            query["agent_run_id"] = request.agent_run_id
        if request.goal_id:
            query["goal_id"] = request.goal_id
        if request.correlation_id:
            query["correlation_id"] = request.correlation_id

        if request.start_time or request.end_time:
            events = self._repository.list()
            filtered: list[AgentRuntimeEvent] = []
            for event in events:
                occurred = event.header.occurred_at
                if request.start_time and occurred < request.start_time:
                    continue
                if request.end_time and occurred > request.end_time:
                    continue
                filtered.append(event)
            return filtered[: request.limit]

        return self._repository.list(limit=request.limit, **query)
