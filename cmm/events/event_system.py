"""Phase 11.22 — the canonical EventSystem composition facade.

``EventSystem`` is a **thin composition facade** over the Phase 9 canonical event
infrastructure.  It owns no algorithm of its own: it holds references to the
already-canonical event factory/normalizer, event registry, durable event
repository, event bus, replay owner and dead-letter queue, and it sequences them.

Its whole reason to exist is the one ordering guarantee Phase 11.22 adds:

.. code-block:: text

    producer fact
    -> safe adapter
    -> canonical event factory
    -> canonical registry validation
    -> normalization
    -> dedup/conflict check
    -> durable append
    -> AgentRuntimeEventBus delivery
    -> bounded subscriber retry
    -> DLQ after exhaustion

Persistence happens **before** normal delivery.  If persistence fails, delivery
must not start.  If persistence succeeds and delivery fails, the event remains
persisted.

What this facade deliberately does not contain: its own subscriber registry, its
own event storage collection, its own mutable event registry, its own replay
engine, its own retry queue or any command execution logic.  Construction is
dependency-injected through the Phase 11.1 composition module, and there is no
global singleton.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventBusStats,
    AgentRuntimeEventReplayRequest,
    AgentRuntimeEventReplayResult,
    EventSensitivity,
)
from cmm.agent_runtime.runtime_event_dead_letter import (
    InMemoryAgentRuntimeDeadLetterQueue,
)
from cmm.agent_runtime.runtime_event_errors import (
    AgentRuntimeEventBusClosedError,
)
from cmm.agent_runtime.runtime_event_factory import (
    AgentRuntimeEventFactory,
    AgentRuntimeEventNormalizer,
)
from cmm.agent_runtime.runtime_event_registry import AgentRuntimeEventRegistry
from cmm.agent_runtime.runtime_event_replay import AgentRuntimeEventReplayer
from cmm.events.event_payload_safety import (
    PlatformEventPayloadError,
    freeze_platform_payload,
    validate_platform_payload,
)

__all__ = [
    "EventSystem",
    "EventSystemStats",
    "PublicationOutcome",
    "PublicationResult",
]


class PublicationOutcome(str, Enum):
    """The deterministic result of one canonical publication attempt."""

    #: The event was newly persisted and normal delivery ran.
    PUBLISHED = "published"
    #: The exact same event identity and content was already persisted.
    IDEMPOTENT_DUPLICATE = "idempotent_duplicate"
    #: The event was persisted but the bus is closed, so delivery did not run.
    PERSISTED_DELIVERY_UNAVAILABLE = "persisted_delivery_unavailable"


@dataclass(frozen=True, slots=True)
class PublicationResult:
    """Immutable, inspectable outcome of one ``publish`` call."""

    outcome: PublicationOutcome
    event: AgentRuntimeEvent
    persisted: bool
    delivered: bool
    dead_lettered: bool
    attempts: int = 0
    failed_subscriptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, PublicationOutcome):
            raise TypeError("outcome must be a PublicationOutcome")


@dataclass(frozen=True, slots=True)
class EventSystemStats:
    """Read-only projection of event-system facts for Phase 11.23.

    Every field is a copy of a fact already owned by a canonical component; this
    is a projection, never a second source of truth.  No metrics backend, exporter
    or tracing is implemented.
    """

    published_total: int
    delivered_total: int
    failed_total: int
    retry_total: int
    dead_letter_total: int
    replay_count: int
    active_subscriptions: int
    repository_event_count: int
    bus_ready: bool
    queue_size: int = 0
    filtered_total: int = 0
    duplicate_total: int = 0
    bus_stats: AgentRuntimeEventBusStats | None = field(default=None, repr=False)


class EventSystem:
    """The one Phase 11.22 event-system composition facade.

    All collaborators are injected.  Nothing is constructed globally, and two
    instances in one process share no mutable state.
    """

    __slots__ = (
        "_bus",
        "_dead_letter_policy",
        "_dead_letters",
        "_factory",
        "_normalizer",
        "_registry",
        "_replayer",
        "_repository",
    )

    def __init__(
        self,
        *,
        registry: AgentRuntimeEventRegistry,
        repository: Any,
        bus: Any,
        dead_letters: InMemoryAgentRuntimeDeadLetterQueue | None = None,
        factory: AgentRuntimeEventFactory | None = None,
        normalizer: AgentRuntimeEventNormalizer | None = None,
        replayer: AgentRuntimeEventReplayer | None = None,
    ) -> None:
        if registry is None:
            raise TypeError("registry is required")
        if repository is None:
            raise TypeError("repository is required")
        if bus is None:
            raise TypeError("bus is required")

        self._registry = registry
        self._repository = repository
        self._bus = bus
        self._dead_letters = (
            dead_letters
            if dead_letters is not None
            else InMemoryAgentRuntimeDeadLetterQueue()
        )
        self._factory = factory or AgentRuntimeEventFactory()
        self._normalizer = normalizer or AgentRuntimeEventNormalizer(self._factory)
        if replayer is not None and replayer.bus is not None:
            self._replayer = replayer
        else:
            # The canonical replay owner is bound to the one canonical transport so
            # replay really re-notifies subscribers instead of merely re-listing
            # stored rows.  No second replay engine is created.
            self._replayer = AgentRuntimeEventReplayer(repository, bus)

        # The bus keeps delivery authority, but a bounded policy and the canonical
        # dead-letter queue are bound here so an exhausted delivery is recorded by
        # the one existing DLQ authority rather than a Phase 11.22 side channel.
        if hasattr(bus, "bind_dead_letter_queue"):
            bus.bind_dead_letter_queue(self._dead_letters)

    # ── Canonical collaborator access ────────────────────────────────────────

    @property
    def registry(self) -> AgentRuntimeEventRegistry:
        return self._registry

    @property
    def repository(self) -> Any:
        return self._repository

    @property
    def bus(self) -> Any:
        return self._bus

    @property
    def dead_letters(self) -> InMemoryAgentRuntimeDeadLetterQueue:
        return self._dead_letters

    @property
    def dead_letter_policy(self) -> bool:
        """Return whether bounded retry and dead-letter recording are active."""

        return int(getattr(self._bus, "max_delivery_attempts", 1)) > 1

    @property
    def normalizer(self) -> AgentRuntimeEventNormalizer:
        return self._normalizer

    # ── Publication ──────────────────────────────────────────────────────────

    def create_event(
        self,
        event_type: str,
        payload: Mapping[str, object] | None = None,
        **facts: Any,
    ) -> AgentRuntimeEvent:
        """Create a validated, normalized canonical event without publishing it.

        The event type is validated by the canonical registry and the payload is
        restricted to the bounded platform vocabulary, so an unsafe payload can
        never become an event in the first place.
        """

        safe_payload = dict(payload) if payload is not None else {}
        self._registry.ensure_registered(event_type)
        validate_platform_payload(safe_payload)

        optional = dict(facts)
        event_id = optional.pop("event_id", None)
        schema_version = optional.pop("schema_version", "1.0.0")
        occurred_at = optional.pop("occurred_at", None)
        emitted_at = optional.pop("emitted_at", None)
        sensitivity = optional.pop("sensitivity", EventSensitivity.INTERNAL)

        event = self._factory.create_event(
            event_type,
            safe_payload,
            event_id=event_id,
            schema_version=schema_version,
            occurred_at=occurred_at,
            emitted_at=emitted_at,
            agent_id=optional.pop("agent_id", None),
            agent_run_id=optional.pop("agent_run_id", None),
            goal_id=optional.pop("goal_id", None),
            workflow_id=optional.pop("workflow_id", None),
            task_id=optional.pop("task_id", None),
            iteration_id=optional.pop("iteration_id", None),
            correlation_id=optional.pop("correlation_id", None),
            causation_id=optional.pop("causation_id", None),
            actor_id=optional.pop("actor_id", None),
            source=optional.pop("source", "platform"),
            sensitivity=sensitivity,
            permissions=optional.pop("permissions", None),
            metadata=optional.pop("metadata", None),
            producer=optional.pop("producer", None),
            aggregate_id=optional.pop("aggregate_id", None),
        )
        if optional:
            raise TypeError(f"unexpected event fact(s): {', '.join(sorted(optional))}")
        return self._normalizer.normalize(event)

    def publish_event(self, event: AgentRuntimeEvent) -> PublicationResult:
        """Persist *event* durably, then deliver it, in that order.

        This is a **publication boundary**, not a trusted back door: a manually
        constructed canonical event is re-validated against the same canonical
        registry and the same bounded platform payload policy that ``publish``
        applies, so safety never depends on the caller choosing a safe method.
        The supplied event identity and canonical header facts are preserved.

        * a brand new event is appended once and delivered once;
        * the exact same event identity and content is an idempotent duplicate: it
          is not persisted again and not delivered again;
        * the same event identity with different content raises the canonical
          identity conflict and mutates nothing;
        * if persistence fails, delivery never starts;
        * if persistence succeeds but the bus is closed, the event stays persisted
          and the outcome says so.
        """

        if not isinstance(event, AgentRuntimeEvent):
            raise TypeError("event must be an AgentRuntimeEvent")

        validated = self._validate_platform_event(event)

        persisted_now = self._persist(validated)
        if not persisted_now:
            return PublicationResult(
                outcome=PublicationOutcome.IDEMPOTENT_DUPLICATE,
                event=validated,
                persisted=False,
                delivered=False,
                dead_lettered=False,
            )

        return self._deliver(validated)

    def publish(
        self,
        event_type: str,
        payload: Mapping[str, object] | None = None,
        **facts: Any,
    ) -> PublicationResult:
        """Create one platform event and publish it through the canonical path.

        The payload is restricted to the bounded platform vocabulary *before*
        creation, so an unsafe payload is rejected before anything is persisted.
        """

        self._registry.ensure_registered(event_type)
        safe_payload = freeze_platform_payload(payload if payload is not None else {})
        return self.publish_event(
            self.create_event(event_type, dict(safe_payload), **facts)
        )

    def subscribe(
        self,
        handler: Callable[[AgentRuntimeEvent], None],
        event_types: list[str],
        *,
        filters: dict[str, Any] | None = None,
        priority: int = 0,
        metadata: dict[str, Any] | None = None,
        accept_replay: bool = False,
    ) -> str:
        """Subscribe through the canonical bus and return its subscription ID.

        The facade keeps no subscription registry of its own; the returned
        identifier is the bus's own identity.
        """

        return self._bus.subscribe(
            handler,
            event_types,
            filters=filters,
            priority=priority,
            metadata=metadata,
            accept_replay=accept_replay,
        )

    def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscription through the canonical bus."""

        self._bus.unsubscribe(subscription_id)

    # ── Replay ───────────────────────────────────────────────────────────────

    def replay(
        self, request: AgentRuntimeEventReplayRequest
    ) -> AgentRuntimeEventReplayResult:
        """Replay stored events to replay-authorised subscribers.

        Uses the canonical replay owner bound to the canonical bus: replay reads
        canonical storage, preserves event identity, correlation and causation,
        honours the request filters, supports dry-run, never appends a duplicate
        record and never invokes a subscriber that did not opt in.
        """

        if not isinstance(request, AgentRuntimeEventReplayRequest):
            raise TypeError("request must be an AgentRuntimeEventReplayRequest")

        return self._replayer.replay(request)

    # ── Dead letters ─────────────────────────────────────────────────────────

    def list_dead_letters(self) -> list[Any]:
        """Return a snapshot of canonical dead-letter entries."""

        return self._dead_letters.list()

    def dead_letter_count(self) -> int:
        return self._dead_letters.count()

    def replay_dead_letter(
        self,
        index: int,
        *,
        request: AgentRuntimeEventReplayRequest | None = None,
    ) -> AgentRuntimeEventReplayResult:
        """Replay one exhausted delivery to the subscriber whose delivery failed.

        A dead-letter entry records the original event **and** the specific failed
        ``subscription_id``, so this targets that subscriber through the one
        canonical replay owner.  An unrelated replay-enabled subscriber can never
        stand in for the failed delivery, and the entry is removed **only** after
        the targeted subscriber accepts replay and succeeds.  A target that did not
        opt in with ``accept_replay=True`` leaves the entry unresolved: the DLQ API
        does not bypass replay policy.

        The original event identity is preserved, no second event is persisted, and
        this is not generalised recovery: it resolves exactly one entry.
        """

        entry = self._dead_letters.get(index)

        stored = self._repository.get(entry.event.header.event_id)
        event = stored if stored is not None else entry.event

        replay_request = request or AgentRuntimeEventReplayRequest(
            event_type=event.header.event_type
        )

        result = self._replayer.replay_to_subscription(
            AgentRuntimeEventReplayRequest(
                event_id=event.header.event_id,
                event_type=replay_request.event_type,
                start_time=replay_request.start_time,
                end_time=replay_request.end_time,
                correlation_id=replay_request.correlation_id,
                agent_run_id=replay_request.agent_run_id,
                goal_id=replay_request.goal_id,
                limit=replay_request.limit,
                dry_run=replay_request.dry_run,
            ),
            entry.subscription_id,
        )

        if result.dry_run:
            return result

        if result.failed_count == 0 and result.replayed_count > 0:
            self._dead_letters.remove(index)

        return result

    # ── Read-only stats/health ───────────────────────────────────────────────

    def stats(self) -> EventSystemStats:
        """Return the read-only event-system projection."""

        bus_stats = self._bus.stats
        bus_ready = not self._bus.is_closed()
        repository_count = self._repository.count()

        return EventSystemStats(
            published_total=bus_stats.published_total,
            delivered_total=bus_stats.delivered_total,
            failed_total=bus_stats.failed_total,
            retry_total=bus_stats.retry_total,
            dead_letter_total=self._dead_letters.count(),
            replay_count=bus_stats.replay_count,
            active_subscriptions=bus_stats.active_subscriptions,
            repository_event_count=repository_count,
            bus_ready=bus_ready,
            queue_size=bus_stats.queue_size,
            filtered_total=bus_stats.filtered_total,
            duplicate_total=bus_stats.duplicate_total,
            bus_stats=bus_stats,
        )

    def health(self) -> dict[str, Any]:
        """Return a small read-only health mapping for later phases."""

        stats = self.stats()
        return {
            "bus_ready": stats.bus_ready,
            "active_subscriptions": stats.active_subscriptions,
            "repository_event_count": stats.repository_event_count,
            "dead_letter_count": stats.dead_letter_total,
        }

    # ── Internals ────────────────────────────────────────────────────────────

    def _validate_platform_event(self, event: AgentRuntimeEvent) -> AgentRuntimeEvent:
        """Apply the one canonical platform publication boundary to *event*.

        This is a helper inside the existing facade, not a second validator
        authority: it composes the canonical registry and the existing Phase 11.22
        bounded payload policy that ``publish`` already uses.

        Order:

        1. canonical registry membership;
        2. no raw payload content on a platform event;
        3. the bounded platform payload vocabulary, including forbidden keys,
           credential/private content, opaque values and non-finite numbers;
        4. canonical normalization, which preserves the event ID, correlation,
           causation and every other canonical header fact the caller supplied.
        """

        self._registry.ensure_registered(event.header.event_type)
        if event.payload.raw is not None:
            raise PlatformEventPayloadError(
                "platform events must not carry raw payload content"
            )
        validate_platform_payload(event.payload.data)
        return self._normalizer.normalize(event)

    def _persist(self, event: AgentRuntimeEvent) -> bool:
        """Durably append *event*; return ``False`` for an idempotent duplicate.

        Raises before any delivery can start when persistence fails or the event
        identity conflicts with different stored content.
        """

        from cmm.agent_runtime.runtime_event_factory import event_fingerprint

        existing = self._repository.get(event.header.event_id)
        if existing is not None:
            if event_fingerprint(existing) == event_fingerprint(event):
                return False
            raise self._identity_conflict(event)

        self._repository.save(event)
        return True

    def _identity_conflict(self, event: AgentRuntimeEvent) -> Exception:
        from cmm.agent_runtime.runtime_event_errors import (
            AgentRuntimeEventIdentityConflictError,
        )

        return AgentRuntimeEventIdentityConflictError(
            f"event '{event.header.event_id}' already exists with different content"
        )

    def _deliver(self, event: AgentRuntimeEvent) -> PublicationResult:
        """Deliver an already-persisted event through the canonical bus."""

        if self._bus.is_closed():
            return PublicationResult(
                outcome=PublicationOutcome.PERSISTED_DELIVERY_UNAVAILABLE,
                event=event,
                persisted=True,
                delivered=False,
                dead_lettered=False,
            )

        before = self._dead_letters.count()
        try:
            self._bus.publish(event)
        except AgentRuntimeEventBusClosedError:
            return PublicationResult(
                outcome=PublicationOutcome.PERSISTED_DELIVERY_UNAVAILABLE,
                event=event,
                persisted=True,
                delivered=False,
                dead_lettered=False,
            )
        except Exception:  # noqa: BLE001
            # The event is already durably recorded, so a delivery-side failure
            # must never be reported as though persistence had failed.
            return PublicationResult(
                outcome=PublicationOutcome.PERSISTED_DELIVERY_UNAVAILABLE,
                event=event,
                persisted=True,
                delivered=False,
                dead_lettered=self._dead_letters.count() > before,
            )

        dead_lettered = self._dead_letters.count() > before
        return PublicationResult(
            outcome=PublicationOutcome.PUBLISHED,
            event=event,
            persisted=True,
            delivered=True,
            dead_lettered=dead_lettered,
        )
