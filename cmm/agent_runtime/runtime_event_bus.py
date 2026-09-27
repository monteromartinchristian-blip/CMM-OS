"""Phase 9.20 – Runtime Event Bus.

Core event bus implementation with synchronous delivery, FIFO ordering,
multiple subscribers, filters, backpressure, and idempotency.

Phase 11.22 extends this one canonical transport additively:

* an optional finite per-subscriber delivery-attempt count (``max_attempts``),
  defaulting to the historical single attempt so legacy direct bus use keeps its
  exact behaviour;
* replay-authorised dispatch, which delivers stored events only to subscribers
  that explicitly opted in with ``accept_replay=True``.

No second bus, retry engine, replay engine or dead-letter authority is added.
"""

from __future__ import annotations

import re
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventBusStats,
    AgentRuntimeEventDeadLetter,
    AgentRuntimeEventDelivery,
    AgentRuntimeEventFilter,
    AgentRuntimeEventSubscription,
    EventDeliveryStatus,
    detached_event_copy,
)
from cmm.agent_runtime.runtime_event_errors import (
    AgentRuntimeEventBusClosedError,
    AgentRuntimeEventDuplicateError,
    AgentRuntimeEventQueueFullError,
)
from cmm.agent_runtime.runtime_event_registry import AgentRuntimeEventRegistry

HandlerType = Callable[[AgentRuntimeEvent], None]

#: Historical Phase 9 behaviour: exactly one delivery attempt per subscriber.
DEFAULT_MAX_DELIVERY_ATTEMPTS = 1

#: The neutral bounded category recorded when an exception class name is not itself
#: a safe bounded category.  It names *what failed* (subscriber delivery) without
#: carrying any attacker-controlled text.
NEUTRAL_DELIVERY_ERROR_TYPE = "SubscriberDeliveryError"

#: A safe DLQ error category is a plain Python-style class name and nothing else.
#: The name is attacker-influenced: Python permits ``type("api_key=...", ...)``, so
#: assignments, whitespace, punctuation, dotted paths and free prose — every shape a
#: leaked credential or private marker arrives in — are refused outright.
_SAFE_ERROR_TYPE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")


class _UnsafeDeadLetterErrorType(ValueError):
    """Raised when an unsafe error category would be recorded in the DLQ."""


def _is_safe_error_type_name(name: object) -> bool:
    """Return whether *name* is a bounded, content-safe DLQ error category.

    This is the single safety predicate behind :func:`safe_delivery_error_type`, so
    classification and the defensive check at the DLQ write are provably the same
    rule rather than two drifting copies.
    """

    if not isinstance(name, str):
        return False
    if not _SAFE_ERROR_TYPE_PATTERN.match(name):
        return False
    # Imported lazily so this transport module keeps its place in the canonical
    # dependency direction and no import cycle is introduced.
    from cmm.domains.credential_policy import contains_high_confidence_credential
    from cmm.domains.event_contracts import _contains_private_marker

    if contains_high_confidence_credential(name):
        return False
    return not _contains_private_marker(name)


def safe_delivery_error_type(exception: BaseException) -> str:
    """Return one bounded, content-safe DLQ error category for *exception*.

    The canonical DLQ must never retain attacker-controlled text.  The raw
    exception message and the traceback were already excluded, but
    ``type(exc).__name__`` is itself attacker-influenced: Python lets a caller create
    ``type("api_key=abcdef1234567890", (Exception,), {})`` and raise it.

    This is the one derivation of a DLQ error category.  It reuses the existing
    Phase 10.33 credential detector and forbidden private-marker vocabulary — the
    same scanners the canonical event-safety gate composes — rather than inventing
    a second policy:

    * an exception class name that is a narrow bounded safe identifier **and** passes
      the existing credential/private-marker scanning is retained, so an ordinary
      ``RuntimeError`` stays meaningfully categorized; and
    * every other name falls back to the neutral bounded category
      :data:`NEUTRAL_DELIVERY_ERROR_TYPE`.

    The original unsafe class name is never stored, truncated or partially echoed.
    """

    name = type(exception).__name__
    if _is_safe_error_type_name(name):
        return name
    return NEUTRAL_DELIVERY_ERROR_TYPE


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
        max_delivery_attempts: int = DEFAULT_MAX_DELIVERY_ATTEMPTS,
    ) -> None:
        if isinstance(max_delivery_attempts, bool) or not isinstance(
            max_delivery_attempts, int
        ):
            raise TypeError("max_delivery_attempts must be an int")
        if max_delivery_attempts < 1:
            raise ValueError("max_delivery_attempts must be at least 1")

        self._registry = registry or AgentRuntimeEventRegistry(strict_mode=True)
        self._max_queue_size = max_queue_size
        self._max_delivery_attempts = max_delivery_attempts
        self._lock = threading.Lock()
        self._subscribers: dict[str, _SubscriberRecord] = {}
        self._queue: deque[_QueuedEvent] = deque()
        self._published_ids: set = set()
        self._closed = False
        self._stats = AgentRuntimeEventBusStats()
        self._subscriber_counter = 0
        #: Phase 11.22 DLQ collaboration, bound by the composed event system.
        #: ``None`` preserves the historical bus-only behaviour exactly.
        self._dead_letter_queue: Any = None

    @property
    def registry(self) -> AgentRuntimeEventRegistry:
        return self._registry

    @property
    def max_delivery_attempts(self) -> int:
        """Return the configured finite per-subscriber delivery attempt count."""

        return self._max_delivery_attempts

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
                retry_total=self._stats.retry_total,
            )

    def is_closed(self) -> bool:
        with self._lock:
            return self._closed

    def bind_dead_letter_queue(self, dead_letter_queue: Any) -> None:
        """Bind the canonical dead-letter queue used after retry exhaustion.

        The queue remains owned by the Phase 9 dead-letter implementation; the
        bus only appends to it, and only when a bounded delivery policy is
        configured.
        """

        with self._lock:
            self._dead_letter_queue = dead_letter_queue

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
        accept_replay: bool = False,
    ) -> str:
        """Subscribe a handler to events matching criteria.

        ``accept_replay`` defaults to ``False``: a legacy subscriber is never
        silently upgraded to replay-enabled, so historical replay can not re-run
        its side effects.
        """
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
            accept_replay=accept_replay,
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

    def deliver_replay(
        self, event: AgentRuntimeEvent
    ) -> list[AgentRuntimeEventDelivery]:
        """Deliver a stored event to replay-authorised subscribers only.

        The event identity, correlation, causation and facts are the original
        stored ones: this call re-notifies subscribers and neither persists nor
        re-publishes anything.  Subscribers that did not opt in with
        ``accept_replay=True`` are skipped, and the historical per-subscriber
        published-ID delivery guard does not apply to replay, because replay is
        exactly the act of re-notifying a stored event.
        """

        with self._lock:
            subscribers = sorted(
                self._subscribers.values(),
                key=lambda rec: rec.subscription.priority,
            )

        records: list[AgentRuntimeEventDelivery] = []
        for record in subscribers:
            records.append(self._deliver_replay_to_subscriber(event, record))

        with self._lock:
            self._stats.replay_count += sum(
                1 for item in records if item.status == EventDeliveryStatus.DELIVERED
            )

        return records

    def deliver_replay_to_subscription(
        self, event: AgentRuntimeEvent, subscription_id: str
    ) -> AgentRuntimeEventDelivery:
        """Re-notify exactly one replay-authorised subscriber with a stored event.

        This is the additive Phase 11.22 remediation capability dead-letter replay
        needs: a dead-letter entry names one failed ``subscription_id``, so replay
        must target that subscriber instead of broadcasting the stored event to
        every replay-enabled subscriber.

        It reuses the same replay-policy and replay-delivery rules as
        :meth:`deliver_replay`; it never broadcasts, never persists, and never
        bypasses ``accept_replay``.  No second replay engine is introduced.
        """

        if not isinstance(subscription_id, str) or not subscription_id:
            raise ValueError("subscription_id must be a non-empty string")

        with self._lock:
            record = self._subscribers.get(subscription_id)

        if record is None:
            # The original subscription is gone, so no delivery can be resolved.
            return AgentRuntimeEventDelivery(
                event_id=event.header.event_id,
                subscription_id=subscription_id,
                handler_name=subscription_id,
                status=EventDeliveryStatus.SKIPPED,
                metadata={"reason": "subscription_not_found"},
            )

        delivery = self._deliver_replay_to_subscriber(event, record)

        if delivery.status == EventDeliveryStatus.DELIVERED:
            with self._lock:
                self._stats.replay_count += 1

        return delivery

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
                1
                for d in delivery_records
                if d.status
                in (EventDeliveryStatus.FAILED, EventDeliveryStatus.DEAD_LETTERED)
            )
            self._stats.dead_letter_total += sum(
                1
                for d in delivery_records
                if d.status == EventDeliveryStatus.DEAD_LETTERED
            )

    @staticmethod
    def _subscriber_accepts(
        event: AgentRuntimeEvent, record: _SubscriberRecord
    ) -> bool:
        """Return whether *record* accepts *event*.

        A subscription declares both the event types it accepts and an optional
        filter.  Both are honoured: a subscriber to ``goal.created`` must never
        receive an unrelated event merely because the optional filter is empty.
        """

        if event.header.event_type not in record.subscription.event_types:
            return False
        return record.filter.matches(event)

    def _deliver_to_subscriber(
        self, event: AgentRuntimeEvent, record: _SubscriberRecord
    ) -> AgentRuntimeEventDelivery:
        """Deliver an event to a single subscriber within its bounded policy.

        Delivery is per subscriber: a failing subscriber retries only itself and
        can never delay, repeat or block delivery to an independent subscriber.
        Every attempt carries the same event identity, and no attempt creates a
        new event.
        """

        event_id = event.header.event_id
        subscription = record.subscription

        if not self._subscriber_accepts(event, record):
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

        attempts = 0
        last_error: str | None = None
        last_error_type: str | None = None

        while attempts < self._max_delivery_attempts:
            attempts += 1
            try:
                # Every attempt receives its own detached canonical snapshot, so a
                # subscriber can never mutate what a later subscriber observes or
                # what the repository has already recorded.
                record.handler(detached_event_copy(event))
            except Exception as exc:  # noqa: BLE001
                last_error_type = safe_delivery_error_type(exc)
                last_error = str(exc)
                continue

            record.delivered_ids.add(event_id)
            if attempts > 1:
                # A subscriber that failed and then succeeded really did retry:
                # the counter reflects attempts actually made, not only exhausted
                # deliveries.  A first-attempt success adds nothing.
                with self._lock:
                    self._stats.retry_total += attempts - 1
            return AgentRuntimeEventDelivery(
                event_id=event_id,
                subscription_id=subscription.id,
                handler_name=subscription.handler_name,
                status=EventDeliveryStatus.DELIVERED,
                metadata={"attempts": attempts},
            )

        with self._lock:
            self._stats.retry_total += attempts - 1
            dead_letter_queue = self._dead_letter_queue

        safe_error_type = last_error_type or NEUTRAL_DELIVERY_ERROR_TYPE

        if dead_letter_queue is not None:
            # A configured bounded delivery policy exhausted: the canonical
            # dead-letter path records exactly one entry for this delivery, and
            # no raw exception text is stored or returned.
            self._dead_letter(
                event=event,
                record=record,
                attempts=attempts,
                error_type=safe_error_type,
            )
            return AgentRuntimeEventDelivery(
                event_id=event_id,
                subscription_id=subscription.id,
                handler_name=subscription.handler_name,
                status=EventDeliveryStatus.DEAD_LETTERED,
                error=safe_error_type,
                metadata={"attempts": attempts, "error_type": safe_error_type},
            )

        # No canonical dead-letter queue is bound, so this is direct legacy bus
        # use.  A single attempt keeps the historical Phase 9 failure shape
        # exactly; a multi-attempt configuration reports only the safe error
        # category rather than raw exception text.
        return AgentRuntimeEventDelivery(
            event_id=event_id,
            subscription_id=subscription.id,
            handler_name=subscription.handler_name,
            status=EventDeliveryStatus.FAILED,
            error=last_error if self._max_delivery_attempts == 1 else safe_error_type,
            metadata={"attempts": attempts},
        )

    def _deliver_replay_to_subscriber(
        self, event: AgentRuntimeEvent, record: _SubscriberRecord
    ) -> AgentRuntimeEventDelivery:
        """Re-notify one replay-authorised subscriber with a stored event."""

        event_id = event.header.event_id
        subscription = record.subscription

        if not subscription.accept_replay:
            return AgentRuntimeEventDelivery(
                event_id=event_id,
                subscription_id=subscription.id,
                handler_name=subscription.handler_name,
                status=EventDeliveryStatus.SKIPPED,
                metadata={"reason": "replay_not_accepted"},
            )

        if not self._subscriber_accepts(event, record):
            return AgentRuntimeEventDelivery(
                event_id=event_id,
                subscription_id=subscription.id,
                handler_name=subscription.handler_name,
                status=EventDeliveryStatus.FILTERED,
            )

        attempts = 0
        last_error_type: str | None = None

        while attempts < self._max_delivery_attempts:
            attempts += 1
            try:
                record.handler(detached_event_copy(event))
            except Exception as exc:  # noqa: BLE001
                last_error_type = safe_delivery_error_type(exc)
                continue

            return AgentRuntimeEventDelivery(
                event_id=event_id,
                subscription_id=subscription.id,
                handler_name=subscription.handler_name,
                status=EventDeliveryStatus.DELIVERED,
                metadata={"attempts": attempts, "replay": True},
            )

        return AgentRuntimeEventDelivery(
            event_id=event_id,
            subscription_id=subscription.id,
            handler_name=subscription.handler_name,
            status=EventDeliveryStatus.FAILED,
            metadata={
                "attempts": attempts,
                "replay": True,
                "error_type": last_error_type or NEUTRAL_DELIVERY_ERROR_TYPE,
            },
        )

    def _dead_letter(
        self,
        *,
        event: AgentRuntimeEvent,
        record: _SubscriberRecord,
        attempts: int,
        error_type: str,
    ) -> None:
        """Append exactly one canonical dead-letter entry for an exhausted delivery.

        The recorded category is re-checked here, at the single write point, so no
        caller can put an unsafe exception class name into DLQ data even if it
        bypasses :func:`safe_delivery_error_type`.
        """

        if not _is_safe_error_type_name(error_type):
            raise _UnsafeDeadLetterErrorType(
                "dead-letter error category failed the bounded safe-category rule"
            )

        subscription = record.subscription
        now = datetime.now(timezone.utc)
        entry = AgentRuntimeEventDeadLetter(
            event=detached_event_copy(event),
            subscription_id=subscription.id,
            handler_name=subscription.handler_name,
            error=error_type,
            error_type=error_type,
            attempts=attempts,
            first_failed_at=now,
            last_failed_at=now,
            metadata={"category": "subscriber_delivery_exhausted"},
        )
        with self._lock:
            queue = self._dead_letter_queue
        if queue is not None:
            queue.add(entry)
