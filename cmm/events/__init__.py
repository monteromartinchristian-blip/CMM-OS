"""Phase 11.22 — the CMM OS platform event system.

Phase 11.22 is an **integration and hardening** phase, not a new event subsystem.
CMM OS already has exactly one canonical event transport, owned by Phase 9:

* :class:`~cmm.agent_runtime.runtime_event_bus.AgentRuntimeEventBus` — transport;
* :class:`~cmm.agent_runtime.runtime_event_registry.AgentRuntimeEventRegistry` —
  the one mutable event-type registration authority;
* :class:`~cmm.agent_runtime.runtime_event_repository.AgentRuntimeEventRepository`
  — the one repository contract, which this package gives a durable
  implementation of;
* :class:`~cmm.agent_runtime.runtime_event_replay.AgentRuntimeEventReplayer` —
  the one replay owner;
* the existing runtime-event dead-letter contracts and queue.

This package therefore contains **thin composition and adaptation only**:

* :mod:`~cmm.events.event_catalog` — the immutable platform event catalog and the
  producer disposition of every catalog entry;
* :mod:`~cmm.events.event_payload_safety` — the single payload gate that makes an
  unsafe payload fail before persistence;
* :mod:`~cmm.events.event_translation` — explicit one-way source-to-platform
  mappings;
* :mod:`~cmm.events.event_system` — the thin :class:`EventSystem` composition
  facade that owns the persist-before-deliver ordering;
* :mod:`~cmm.events.orchestration_adapter` — the production
  ``OrchestrationEventSink`` for the Phase 11.2 seam;
* :mod:`~cmm.events.kernel_adapter` — the one-way ``kernel.events.Event`` bridge;
* :mod:`~cmm.events.platform_module` — the Phase 11.1 composition contribution.

Dependency direction::

    producer seam -> cmm.events adapters -> Phase 9 event transport

and never the reverse.  Nothing here is registered at import time, no global
singleton is created, and no second bus, registry, repository contract, replay
engine, dead-letter queue or broker abstraction exists.

See ``docs/reference/phase-11-event-system.md``.
"""

from __future__ import annotations

from cmm.events.event_catalog import (
    PLATFORM_EVENT_CATALOG,
    PLATFORM_EVENT_NAMES,
    RESERVED_PLATFORM_EVENT_NAMES,
    PlatformEventSpec,
    ProducerDisposition,
    catalog_spec,
    is_platform_event_name,
)
from cmm.events.event_payload_safety import (
    ALLOWED_PAYLOAD_KEYS,
    PlatformEventPayloadError,
    freeze_platform_payload,
    validate_platform_payload,
)
from cmm.events.event_system import (
    EventSystem,
    EventSystemStats,
    PublicationOutcome,
    PublicationResult,
)
from cmm.events.event_translation import (
    KERNEL_SOURCE_TRANSLATIONS,
    ORCHESTRATION_SOURCE_TRANSLATIONS,
    SourceTranslation,
    kernel_translation_table,
    orchestration_translation_table,
    translate_kernel_event,
    translate_orchestration_event,
)
from cmm.events.kernel_adapter import PlatformKernelEventAdapter
from cmm.events.orchestration_adapter import PlatformOrchestrationEventSink
from cmm.events.platform_module import (
    EVENT_SYSTEM_MODULE_ID,
    EVENT_SYSTEM_SERVICE_IDS,
    EventSystemComposition,
    build_event_system_composition,
    build_event_system_composition_module,
)
from cmm.events.storage import (
    default_event_store_directory,
    default_event_store_path,
    event_store_path,
)

__all__ = [
    "ALLOWED_PAYLOAD_KEYS",
    "EVENT_SYSTEM_MODULE_ID",
    "EVENT_SYSTEM_SERVICE_IDS",
    "KERNEL_SOURCE_TRANSLATIONS",
    "ORCHESTRATION_SOURCE_TRANSLATIONS",
    "PLATFORM_EVENT_CATALOG",
    "PLATFORM_EVENT_NAMES",
    "RESERVED_PLATFORM_EVENT_NAMES",
    "EventSystem",
    "EventSystemComposition",
    "EventSystemStats",
    "PlatformEventPayloadError",
    "PlatformEventSpec",
    "PlatformKernelEventAdapter",
    "PlatformOrchestrationEventSink",
    "ProducerDisposition",
    "PublicationOutcome",
    "PublicationResult",
    "SourceTranslation",
    "build_event_system_composition",
    "build_event_system_composition_module",
    "catalog_spec",
    "default_event_store_directory",
    "default_event_store_path",
    "event_store_path",
    "freeze_platform_payload",
    "is_platform_event_name",
    "kernel_translation_table",
    "orchestration_translation_table",
    "translate_kernel_event",
    "translate_orchestration_event",
    "validate_platform_payload",
]
