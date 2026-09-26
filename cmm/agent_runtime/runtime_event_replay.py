"""Phase 9.20 – Runtime Event Replay.

Controlled event replay with filtering, dry-run, and chronological ordering.

Phase 11.22 makes this the canonical *notification* replay owner: when a bus is
bound, replay reads the stored canonical events and re-delivers them to
replay-authorised subscribers under their original identity.  It never appends a
second repository record, never mutates the original record, and never bypasses
an event's validation: every replayed event is re-read from the canonical
repository, which fails closed on anything that is not a canonical event.

Replay is replay of event-notification evidence, not replay of business
commands.  No second replay engine is introduced.
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

    def __init__(self, repository: Any, bus: Any = None) -> None:
        """Bind the canonical repository, and optionally the canonical bus.

        ``bus`` is the Phase 9 ``AgentRuntimeEventBus``.  It is optional so every
        existing Phase 9 construction and call site keeps working unchanged.
        """

        self._repository = repository
        self._bus = bus

    @property
    def bus(self) -> Any:
        """Return the canonical transport bound for replay delivery, if any."""

        return self._bus

    def replay(
        self, request: AgentRuntimeEventReplayRequest
    ) -> AgentRuntimeEventReplayResult:
        """Execute a controlled event replay.

        With a bound bus this re-delivers stored evidence to replay-authorised
        subscribers.  Without one it preserves the historical Phase 9 behaviour
        of reporting the selected stored events.
        """
        events = self._gather_events(request)

        if request.dry_run:
            return AgentRuntimeEventReplayResult(
                replayed_count=0,
                skipped_count=len(events),
                failed_count=0,
                events=[],
                errors=[],
                dry_run=True,
            )

        seen_ids: set[str] = set()
        selected: list[AgentRuntimeEvent] = []
        skipped = 0
        for event in events:
            event_id = event.header.event_id
            if event_id in seen_ids:
                skipped += 1
                continue
            seen_ids.add(event_id)
            selected.append(event)

        if self._bus is None:
            # No transport is bound, so replay reports the canonical stored
            # evidence it selected.  It deliberately does not re-save: appending
            # a second record for an already-stored event was never replay.
            return AgentRuntimeEventReplayResult(
                replayed_count=len(selected),
                skipped_count=skipped,
                failed_count=0,
                events=list(selected),
                errors=[],
                dry_run=False,
            )

        replayed: list[AgentRuntimeEvent] = []
        errors: list[str] = []
        failed = 0

        for event in selected:
            try:
                deliveries = self._bus.deliver_replay(event)
            except Exception as exc:  # noqa: BLE001
                errors.append(type(exc).__name__)
                failed += 1
                continue

            statuses = [
                getattr(getattr(delivery, "status", None), "value", None)
                for delivery in deliveries
            ]

            if "failed" in statuses:
                errors.append("replay_delivery_failed")
                failed += 1
                continue

            if "delivered" not in statuses:
                # Nobody was authorised and able to receive this replay: no
                # subscriber was invoked, so this is not a replayed event.  A
                # dead-letter replay must therefore leave its entry unresolved.
                errors.append("replay_delivery_not_authorised")
                failed += 1
                continue

            replayed.append(event)

        return AgentRuntimeEventReplayResult(
            replayed_count=len(replayed),
            skipped_count=skipped,
            failed_count=failed,
            events=replayed,
            errors=errors,
            dry_run=False,
        )

    def replay_to_subscription(
        self,
        request: AgentRuntimeEventReplayRequest,
        subscription_id: str,
    ) -> AgentRuntimeEventReplayResult:
        """Re-deliver the selected stored events to exactly one subscriber.

        Dead-letter replay uses this targeted path: a dead-letter entry records the
        one ``subscription_id`` whose delivery failed, so the entry may only be
        resolved by retrying that subscriber.  No other subscriber is invoked, and
        the target subscriber must itself be replay-authorised.

        This is an additive capability of the one canonical replay owner; it is not
        a second replay engine, it never appends a repository record and it never
        mutates the stored event.
        """

        if not isinstance(subscription_id, str) or not subscription_id:
            raise ValueError("subscription_id must be a non-empty string")

        events = self._gather_events(request)

        if request.dry_run:
            return AgentRuntimeEventReplayResult(
                replayed_count=0,
                skipped_count=len(events),
                failed_count=0,
                events=[],
                errors=[],
                dry_run=True,
            )

        if self._bus is None:
            return AgentRuntimeEventReplayResult(
                replayed_count=0,
                skipped_count=0,
                failed_count=len(events),
                events=[],
                errors=["replay_delivery_not_authorised"] * len(events),
                dry_run=False,
            )

        seen_ids: set[str] = set()
        replayed: list[AgentRuntimeEvent] = []
        errors: list[str] = []
        failed = 0
        skipped = 0

        for event in events:
            event_id = event.header.event_id
            if event_id in seen_ids:
                skipped += 1
                continue
            seen_ids.add(event_id)

            try:
                delivery = self._bus.deliver_replay_to_subscription(
                    event, subscription_id
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(type(exc).__name__)
                failed += 1
                continue

            status = getattr(getattr(delivery, "status", None), "value", None)

            if status == "delivered":
                replayed.append(event)
            elif status == "failed":
                errors.append("replay_delivery_failed")
                failed += 1
            else:
                # The target subscriber did not accept replay, no longer exists,
                # or filtered the event: nothing was retried, so a dead-letter
                # entry must stay unresolved.
                errors.append("replay_delivery_not_authorised")
                failed += 1

        return AgentRuntimeEventReplayResult(
            replayed_count=len(replayed),
            skipped_count=skipped,
            failed_count=failed,
            events=replayed,
            errors=errors,
            dry_run=False,
        )

    def _gather_events(
        self, request: AgentRuntimeEventReplayRequest
    ) -> list[AgentRuntimeEvent]:
        """Collect events matching the replay request in stored order."""
        query: dict[str, Any] = {}
        if request.event_type:
            query["event_type"] = request.event_type
        if request.agent_run_id:
            query["agent_run_id"] = request.agent_run_id
        if request.goal_id:
            query["goal_id"] = request.goal_id
        if request.correlation_id:
            query["correlation_id"] = request.correlation_id

        events = self._repository.list(limit=request.limit, **query)

        if request.start_time or request.end_time:
            filtered: list[AgentRuntimeEvent] = []
            for event in events:
                occurred = event.header.occurred_at
                if request.start_time and occurred < request.start_time:
                    continue
                if request.end_time and occurred > request.end_time:
                    continue
                filtered.append(event)
            events = filtered

        if request.event_id:
            events = [e for e in events if e.header.event_id == request.event_id]

        return events
