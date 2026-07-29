"""Phase 9.20 – Runtime Event Bus.

Core event bus implementation with synchronous delivery, FIFO ordering,
multiple subscribers, filters, backpressure, and idempotency.
"""

from __future__ import annotations

import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventBusStats,
    AgentRuntimeEventDelivery,
    AgentRuntimeEventFilter,
    AgentRuntimeEventSubscription,
    EventDeliveryStatus,
)
from cmm.agent_runtime.runtime_event_errors import (
    AgentRuntimeEventBusClosedError,
    AgentRuntimeEventDuplicateError,
    AgentRuntimeEventQueueFullError,
)
from cmm.agent_runtime.runtime_event_registry import AgentRuntimeEventRegistry

HandlerType = Callable[[AgentRuntimeEvent], None]


@dataclass
class _QueuedEvent:
    event: AgentRuntimeEvent
    event_id: str


@dataclass
class _SubscriberRecord:
    subscription: AgentRuntimeEventSubscription
    handler: HandlerType
    filter: AgentRuntimeEventFilter
    delivered_ids: set


class AgentRuntimeEventBus:
    """Thread-safe, synchronous event bus with FIFO delivery."""

    def __init__(
        self,
        registry: AgentRuntimeEventRegistry | None = None,
        max_queue_size: int = 10000,
    ) -> None:
        self._registry = registry or AgentRuntimeEventRegistry(strict_mode=True)
        self._max_queue_size = max_queue_size
        self._lock = threading.Lock()
        self._subscribers: dict[str, _SubscriberRecord] = {}
        self._queue: deque[_QueuedEvent] = deque()
        self._published_ids: set = set()
        self._closed = False
        self._stats = AgentRuntimeEventBusStats()
        self._subscriber_counter = 0

    @property
    def registry(self) -> AgentRuntimeEventRegistry:
        return self._registry

    @property
    def stats(self) -> AgentRuntimeEventBusStats:
        with self._lock:
            return AgentRuntimeEventBusStats(
                published_total=self._stats.published_total,
                delivered_total=self._stats.delivered_total,
                filtered_total=self._stats.filtered_total,
                duplicate_total=self._stats.duplicate_total,
                failed_total=self._stats.failed_total,
                dead_letter_total=self._stats.dead_letter_total,
                active_subscriptions=len(self._subscribers),
                queue_size=len(self._queue),
                replay_count=self._stats.replay_count,
            )

    def is_closed(self) -> bool:
        with self._lock:
            return self._closed

    def publish(self, event: AgentRuntimeEvent) -> None:
        """Publish an event synchronously to all matching subscribers."""
        if self._closed:
            raise AgentRuntimeEventBusClosedError("Event bus is closed")

        with self._lock:
            event_id = event.header.event_id
            if event_id in self._published_ids:
                raise AgentRuntimeEventDuplicateError(
                    f"Duplicate event_id '{event_id}'"
                )

            if len(self._queue) >= self._max_queue_size:
                raise AgentRuntimeEventQueueFullError("Event queue is full")

            self._queue.append(_QueuedEvent(event=event, event_id=event_id))
            self._published_ids.add(event_id)
            self._stats.published_total += 1

        self._dispatch_sync(event)

    def publish_many(self, events: list[AgentRuntimeEvent]) -> None:
        """Publish multiple events in order."""
        for event in events:
            self.publish(event)

    def subscribe(
        self,
        handler: HandlerType,
        event_types: list[str],
        filters: dict[str, Any] | None = None,
        priority: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Subscribe a handler to events matching criteria."""
        if self._closed:
            raise AgentRuntimeEventBusClosedError("Event bus is closed")

        with self._lock:
            self._subscriber_counter += 1
            sub_id = f"sub_{self._subscriber_counter}"

        subscription = AgentRuntimeEventSubscription(
            id=sub_id,
            handler_name=sub_id,
            event_types=list(event_types),
            filters=filters or {},
            priority=priority,
            metadata=metadata or {},
        )

        filter_obj = AgentRuntimeEventFilter(
            event_type=subscription.filters.get("event_type"),
            agent_id=subscription.filters.get("agent_id"),
            agent_run_id=subscription.filters.get("agent_run_id"),
            goal_id=subscription.filters.get("goal_id"),
            workflow_id=subscription.filters.get("workflow_id"),
            correlation_id=subscription.filters.get("correlation_id"),
            custom=subscription.filters.get("custom", {}),
        )

        record = _SubscriberRecord(
            subscription=subscription,
            handler=handler,
            filter=filter_obj,
            delivered_ids=set(),
        )

        with self._lock:
            self._subscribers[sub_id] = record

        return sub_id

    def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscription."""
        with self._lock:
            if subscription_id not in self._subscribers:
                raise KeyError(f"subscription '{subscription_id}' not found")
            del self._subscribers[subscription_id]

    def dispatch(self, event: AgentRuntimeEvent) -> None:
        """Dispatch a single event immediately and synchronously."""
        self._dispatch_sync(event)

    def drain(self) -> None:
        """Drain all queued events."""
        with self._lock:
            while self._queue:
                self._queue.popleft()

    def close(self) -> None:
        """Close the bus, rejecting further publishes."""
        with self._lock:
            self._closed = True

    def _dispatch_sync(self, event: AgentRuntimeEvent) -> None:
        """Deliver event synchronously to all matching subscribers."""
        event_id = event.header.event_id

        with self._lock:
            if event_id not in self._published_ids:
                return
            subscribers = sorted(
                self._subscribers.values(),
                key=lambda rec: rec.subscription.priority,
            )
            delivery_records: list[AgentRuntimeEventDelivery] = []

        for record in subscribers:
            delivery = self._deliver_to_subscriber(event, record)
            delivery_records.append(delivery)

        with self._lock:
            self._stats.delivered_total += sum(
                1 for d in delivery_records if d.status == EventDeliveryStatus.DELIVERED
            )
            self._stats.filtered_total += sum(
                1 for d in delivery_records if d.status == EventDeliveryStatus.FILTERED
            )
            self._stats.duplicate_total += sum(
                1 for d in delivery_records if d.status == EventDeliveryStatus.DUPLICATE
            )
            self._stats.failed_total += sum(
                1 for d in delivery_records if d.status == EventDeliveryStatus.FAILED
            )
            self._stats.dead_letter_total += sum(
                1
                for d in delivery_records
                if d.status == EventDeliveryStatus.DEAD_LETTERED
            )

    def _deliver_to_subscriber(
        self, event: AgentRuntimeEvent, record: _SubscriberRecord
    ) -> AgentRuntimeEventDelivery:
        """Deliver an event to a single subscriber."""
        event_id = event.header.event_id
        subscription = record.subscription

        if not record.filter.matches(event):
            return AgentRuntimeEventDelivery(
                event_id=event_id,
                subscription_id=subscription.id,
                handler_name=subscription.handler_name,
                status=EventDeliveryStatus.FILTERED,
            )

        if event_id in record.delivered_ids:
            return AgentRuntimeEventDelivery(
                event_id=event_id,
                subscription_id=subscription.id,
                handler_name=subscription.handler_name,
                status=EventDeliveryStatus.DUPLICATE,
            )

        try:
            record.handler(event)
            record.delivered_ids.add(event_id)
            return AgentRuntimeEventDelivery(
                event_id=event_id,
                subscription_id=subscription.id,
                handler_name=subscription.handler_name,
                status=EventDeliveryStatus.DELIVERED,
            )
        except Exception as exc:  # noqa: BLE001
            return AgentRuntimeEventDelivery(
                event_id=event_id,
                subscription_id=subscription.id,
                handler_name=subscription.handler_name,
                status=EventDeliveryStatus.FAILED,
                error=str(exc),
            )
