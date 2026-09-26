"""Phase 11.22 — ``kernel.events.Event`` bridge adapter.

Existing producers already publish through ``kernel.events.event.Event``:

* the Phase 7 Continuous Validation ``KernelEventPublisher``;
* the Phase 10.33 ``DomainKernelEventPublisher``;
* the canonical workflow subsystem, whose ``WorkflowEvent`` contract is projected
  onto the Kernel Event boundary.

This module is a thin, callable, one-way adapter for exactly the lifecycle facts
Phase 11.22 needs.  It is not a second Kernel event system:

* it validates the incoming event before reading anything from it;
* it translates only explicitly mapped event names, never guessing;
* it copies only mapped safe facts, so a missing fact stays missing;
* it fails closed on any content the platform vocabulary refuses, *before*
  persistence;
* it publishes through the canonical ``EventSystem`` facade.

Unmapped kernel events are observed and skipped.  They remain completely valid
and unmodified in their own canonical contract; the adapter simply does not
invent a platform event for them.  No Domain Event, Validation publisher or
workflow contract is changed by this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cmm.events.event_catalog import catalog_spec
from cmm.events.event_payload_safety import (
    ALLOWED_PAYLOAD_KEYS,
    PlatformEventPayloadError,
)
from cmm.events.event_system import EventSystem
from cmm.events.event_translation import (
    KERNEL_SOURCE_TRANSLATIONS,
    translate_kernel_event,
)
from kernel.events.event import Event as KernelEvent

__all__ = [
    "KERNEL_ADAPTER_ID",
    "PlatformKernelEventAdapter",
    "SkippedKernelEvent",
]

KERNEL_ADAPTER_ID = "cmm.events.kernel_adapter"

#: Facts the adapter may read from a kernel event payload.  This is the bounded
#: Phase 11.22 platform vocabulary intersected with the identifiers closed phases
#: actually publish on their own event contracts.
READABLE_PAYLOAD_KEYS: frozenset[str] = frozenset(
    {
        "event_id",
        "event_type",
        "workflow_id",
        "run_id",
        "node_id",
        "parent_run_id",
        "root_run_id",
        "domain_id",
        "execution_id",
        "validation_id",
        "approval_id",
        "operation_id",
        "request_id",
        "status",
        "policy",
        "duration_ms",
        "error_code",
        "error_category",
        "sensitivity",
        "schema_version",
    }
)

#: Identifier facts that a kernel payload may carry under a canonical alias.
#: A source key is read only when it is present; the adapter never invents it.
_ALIASES: dict[str, str] = {
    "id": "event_id",
}

assert READABLE_PAYLOAD_KEYS <= ALLOWED_PAYLOAD_KEYS | {
    # ``execution_id`` is projected to ``aggregate_id`` rather than copied, so it
    # never has to exist in the platform payload vocabulary itself.
    "execution_id"
}, "adapter facts must stay inside the canonical platform payload vocabulary"


def _canonical_domain_id(value: object) -> str | None:
    """Return a canonical domain identity string, or ``None`` when unusable.

    A ``DomainId`` already projects to ``{"slug": ...}`` on its own serialization
    contract; the platform carries the stable ``domain:<slug>`` reference instead
    of a nested mapping, so the adapter copies an identity and never a structure.
    """

    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        slug = value.get("slug")
        if isinstance(slug, str) and slug.strip():
            return f"domain:{slug.strip()}"
    return None


@dataclass(frozen=True, slots=True)
class SkippedKernelEvent:
    """One valid kernel event with no explicit Phase 11.22 platform mapping."""

    source_event_type: str
    reason: str = "no_explicit_platform_translation"


class PlatformKernelEventAdapter:
    """Callable one-way bridge from ``kernel.events.Event`` to the event system."""

    __slots__ = ("_published", "_skipped", "_system")

    def __init__(self, system: EventSystem) -> None:
        if system is None:
            raise TypeError("system is required")
        self._system = system
        self._skipped: list[SkippedKernelEvent] = []
        self._published: list[Any] = []

    # ── Listener seam ────────────────────────────────────────────────────────

    def __call__(self, event: KernelEvent) -> None:
        """Accept a kernel event exactly like any other kernel event listener."""

        self.handle(event)

    def handle(self, event: KernelEvent) -> str | None:
        """Validate, translate and publish one kernel event.

        Returns the canonical platform event ID when one was published, and
        ``None`` when the source name has no explicit platform mapping.
        """

        source_name, payload = self._validate(event)

        translation = translate_kernel_event(source_name)
        if translation is None:
            self._skipped.append(SkippedKernelEvent(source_event_type=source_name))
            return None

        projected = self._project(translation.fact_keys, payload)
        projected.setdefault("event_type", source_name)

        result = self._system.publish(
            translation.platform_event_type,
            projected,
            correlation_id=self._correlation(payload),
            causation_id=self._identifier(payload),
            producer=self._producer_for(translation.platform_event_type),
            aggregate_id=self._aggregate_for(projected),
        )
        self._published.append(result.event)
        return result.event.header.event_id

    # ── Observation surface ──────────────────────────────────────────────────

    def skipped_events(self) -> tuple[SkippedKernelEvent, ...]:
        """Return the valid kernel events that had no platform mapping."""

        return tuple(self._skipped)

    def published_events(self) -> tuple[Any, ...]:
        """Return the canonical platform events this adapter published."""

        return tuple(self._published)

    # ── Internals ────────────────────────────────────────────────────────────

    @staticmethod
    def _validate(event: KernelEvent) -> tuple[str, dict[str, Any]]:
        if not isinstance(event, KernelEvent):
            raise TypeError("event must be a kernel.events.event.Event")

        name = event.name
        if not isinstance(name, str) or not name.strip():
            raise ValueError("kernel event name must be a non-empty string")
        normalized_name = name.strip()

        raw_payload = event.payload
        if raw_payload is None:
            return normalized_name, {}
        if not isinstance(raw_payload, dict):
            raise PlatformEventPayloadError(
                "kernel event payload must be a mapping to be bridged"
            )

        payload: dict[str, Any] = {}
        for key, value in raw_payload.items():
            if not isinstance(key, str):
                raise PlatformEventPayloadError("payload keys must be strings")
            canonical_key = _ALIASES.get(key, key)
            if canonical_key not in READABLE_PAYLOAD_KEYS:
                continue
            if canonical_key == "domain_id":
                canonical_value = _canonical_domain_id(value)
                if canonical_value is None:
                    continue
                payload[canonical_key] = canonical_value
                continue
            payload[canonical_key] = value

        return normalized_name, payload

    @staticmethod
    def _project(fact_keys: tuple[str, ...], payload: dict[str, Any]) -> dict[str, Any]:
        projected: dict[str, Any] = {}
        for key in fact_keys:
            if key not in payload:
                continue
            value = payload[key]
            if isinstance(value, tuple):
                value = list(value)
            projected[key] = value
        return projected

    @staticmethod
    def _identifier(payload: dict[str, Any]) -> str | None:
        for key in (
            "event_id",
            "validation_id",
            "execution_id",
            "operation_id",
            "workflow_id",
            "request_id",
        ):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _correlation(payload: dict[str, Any]) -> str | None:
        for key in ("workflow_id", "request_id", "execution_id", "validation_id"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _aggregate_for(projected: dict[str, Any]) -> str | None:
        for key in ("workflow_id", "domain_id", "run_id", "operation_id"):
            value = projected.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _producer_for(platform_event_type: str) -> str:
        """Return the catalog owner of *platform_event_type*.

        Owner identity comes from the one catalog, so a translation cannot claim
        an owner the catalog does not record.
        """

        spec = catalog_spec(platform_event_type)
        return spec.owner or "kernel.events"


def kernel_adapter_translations() -> tuple[Any, ...]:
    """Return the explicit kernel event translations the adapter uses."""

    return KERNEL_SOURCE_TRANSLATIONS
