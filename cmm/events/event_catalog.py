"""Phase 11.22 — the canonical platform event catalog.

This module declares the twenty historical minimum Phase 11.22 platform event
names together with the producer disposition of each one.

It is a **contract catalog, not a registry**.  The mutable registration authority
for event types remains the Phase 9
:class:`~cmm.agent_runtime.runtime_event_registry.AgentRuntimeEventRegistry`, and
the canonical names are registered through the Phase 9
:mod:`cmm.agent_runtime.runtime_event_types` surface.  Nothing here is
discovered, resolved, aliased or mutated at import time.

The catalog is immutable: it is a tuple of frozen entries, and no module-level
mutable mapping is exposed.

Producer truth rule
-------------------

An event may be emitted only when a real canonical owner supplies evidence for
that lifecycle fact.  Twelve of the twenty names are therefore registered but
**reserved**: the owning subsystem either does not exist at Phase 11.22 or has no
safe emission seam, so the name is valid and resolvable while never being
synthetically emitted.  Phase 11.22 must not invent backup, plugin, security,
model-gateway or memory owners merely to make the catalog look active.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from cmm.agent_runtime.runtime_event_types import EVENT_TYPE_CATEGORY_MAP

__all__ = [
    "PLATFORM_EVENT_CATALOG",
    "PLATFORM_EVENT_NAMES",
    "RESERVED_PLATFORM_EVENT_NAMES",
    "PlatformEventSpec",
    "ProducerDisposition",
    "canonical_registration_names",
    "catalog_spec",
    "is_platform_event_name",
    "platform_event_names",
    "reserved_platform_event_names",
    "specs_by_disposition",
]


class ProducerDisposition(str, Enum):
    """How one catalog event can actually be produced at Phase 11.22 time."""

    #: An existing canonical owner already emits the fact and is connected by an
    #: explicit Phase 11.22 adapter, with executable proof.
    CONNECTED_EXISTING_OWNER = "CONNECTED_EXISTING_OWNER"
    #: The fact is already a canonical Phase 9 runtime event in its own right.
    CANONICAL_EXISTING_RUNTIME_EVENT = "CANONICAL_EXISTING_RUNTIME_EVENT"
    #: The name is registered and reserved; no owner exists yet, so it is never
    #: emitted by Phase 11.22.
    REGISTERED_RESERVED_OWNER_NOT_YET_AVAILABLE = (
        "REGISTERED_RESERVED_OWNER_NOT_YET_AVAILABLE"
    )


@dataclass(frozen=True, slots=True)
class PlatformEventSpec:
    """One immutable row of the Phase 11.22 platform event catalog.

    ``owner`` names the canonical subsystem that owns the lifecycle fact, and is
    ``None`` exactly when the owner does not exist yet.  ``connected_evidence``
    names the executable Phase 11.22 test that proves a connected disposition.
    """

    name: str
    disposition: ProducerDisposition
    owner: str | None
    rationale: str
    connected_evidence: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("catalog event name is required")
        if not isinstance(self.disposition, ProducerDisposition):
            raise TypeError("disposition must be a ProducerDisposition")
        if not self.rationale:
            raise ValueError("catalog rationale is required")

        reserved = (
            self.disposition
            is ProducerDisposition.REGISTERED_RESERVED_OWNER_NOT_YET_AVAILABLE
        )
        if reserved and self.owner is not None:
            raise ValueError("a reserved catalog event cannot name an owner")
        if not reserved and not self.owner:
            raise ValueError("a non-reserved catalog event must name its owner")
        if (
            self.disposition is ProducerDisposition.CONNECTED_EXISTING_OWNER
            and not self.connected_evidence
        ):
            raise ValueError(
                "a connected catalog event must cite its executable evidence"
            )


def _connected(
    name: str, owner: str, rationale: str, evidence: str
) -> PlatformEventSpec:
    return PlatformEventSpec(
        name=name,
        disposition=ProducerDisposition.CONNECTED_EXISTING_OWNER,
        owner=owner,
        rationale=rationale,
        connected_evidence=evidence,
    )


def _canonical(name: str, owner: str, rationale: str) -> PlatformEventSpec:
    return PlatformEventSpec(
        name=name,
        disposition=ProducerDisposition.CANONICAL_EXISTING_RUNTIME_EVENT,
        owner=owner,
        rationale=rationale,
    )


def _reserved(name: str, rationale: str) -> PlatformEventSpec:
    return PlatformEventSpec(
        name=name,
        disposition=ProducerDisposition.REGISTERED_RESERVED_OWNER_NOT_YET_AVAILABLE,
        owner=None,
        rationale=rationale,
    )


#: The twenty historical minimum Phase 11.22 platform events, in catalog order.
PLATFORM_EVENT_CATALOG: tuple[PlatformEventSpec, ...] = (
    _reserved(
        "session.created",
        "the canonical session store owns session lifecycle but exposes no event "
        "seam at Phase 11.22; Phase 11.5/DP-105 shares the store without an event",
    ),
    _connected(
        "message.received",
        "cmm.orchestration",
        "the Orchestrator emits orchestration.request_received for every accepted "
        "inbound request; the adapter translates it one-way",
        "tests/events/test_phase11_22_orchestration_adapter.py",
    ),
    _connected(
        "intent.resolved",
        "cmm.orchestration",
        "the Orchestrator emits orchestration.intent_resolved after intent "
        "resolution; the adapter translates it one-way",
        "tests/events/test_phase11_22_orchestration_adapter.py",
    ),
    _connected(
        "domain.selected",
        "cmm.orchestration",
        "the Orchestrator emits orchestration.domain_resolved once a domain route is "
        "resolved; the adapter translates it one-way",
        "tests/events/test_phase11_22_orchestration_adapter.py",
    ),
    _reserved(
        "reasoning.completed",
        "the cognitive reasoning package owns reasoning but emits no canonical "
        "lifecycle event at Phase 11.22",
    ),
    _canonical(
        "goal.created",
        "cmm.agent_runtime",
        "already a canonical Phase 9 runtime event (goal.created) used directly by "
        "the runtime transport",
    ),
    _canonical(
        "goal.updated",
        "cmm.agent_runtime",
        "already a canonical Phase 9 runtime event (goal.updated) used directly by "
        "the runtime transport",
    ),
    _connected(
        "workflow.started",
        "cmm.workflows",
        "the canonical workflow engine emits workflow.running in its own "
        "WorkflowEvent contract; the kernel adapter maps the lifecycle fact",
        "tests/events/test_phase11_22_kernel_adapter.py",
    ),
    _connected(
        "workflow.paused",
        "cmm.workflows",
        "the canonical workflow engine emits workflow.<status> for its run statuses; "
        "the kernel adapter maps the paused lifecycle fact",
        "tests/events/test_phase11_22_kernel_adapter.py",
    ),
    _connected(
        "workflow.completed",
        "cmm.workflows",
        "the canonical workflow engine emits workflow.completed; the kernel adapter "
        "maps the lifecycle fact",
        "tests/events/test_phase11_22_kernel_adapter.py",
    ),
    _connected(
        "workflow.failed",
        "cmm.workflows",
        "the canonical workflow engine emits workflow.failed; the kernel adapter maps "
        "the lifecycle fact",
        "tests/events/test_phase11_22_kernel_adapter.py",
    ),
    _connected(
        "operation.executed",
        "cmm.agent_runtime",
        "the Phase 9 runtime already carries operation.executed facts; the kernel "
        "adapter maps the domain execution completion into it",
        "tests/events/test_phase11_22_kernel_adapter.py",
    ),
    _connected(
        "validation.completed",
        "cmm.validation",
        "the Phase 7 KernelEventPublisher publishes validation.completed; the kernel "
        "adapter maps it one-way",
        "tests/events/test_phase11_22_kernel_adapter.py",
    ),
    _connected(
        "approval.requested",
        "cmm.orchestration",
        "the Orchestrator emits orchestration.approval_required when policy requires "
        "approval; the adapter translates it one-way",
        "tests/events/test_phase11_22_orchestration_adapter.py",
    ),
    _connected(
        "approval.resolved",
        "cmm.domains",
        "Phase 10.33 publishes the canonical domain.approval.received fact; the "
        "kernel adapter maps it one-way",
        "tests/events/test_phase11_22_kernel_adapter.py",
    ),
    _reserved(
        "knowledge.updated",
        "the knowledge subsystem owns knowledge state but exposes no canonical event "
        "seam at Phase 11.22",
    ),
    _connected(
        "memory.updated",
        "cmm.domains",
        "Phase 10.33 publishes the canonical domain.memory.updated fact; the kernel "
        "adapter maps it one-way",
        "tests/events/test_phase11_22_kernel_adapter.py",
    ),
    _reserved(
        "backup.created",
        "no canonical backup owner exists at Phase 11.22; the name is reserved rather "
        "than satisfied by an invented producer",
    ),
    _reserved(
        "plugin.failed",
        "no canonical plugin runtime owner exists at Phase 11.22; the name is "
        "reserved rather than satisfied by an invented producer",
    ),
    _reserved(
        "security.alert",
        "no canonical security-alert detector owner exists at Phase 11.22; the name "
        "is reserved rather than satisfied by an invented producer",
    ),
)

#: The catalog names in catalog order.
PLATFORM_EVENT_NAMES: tuple[str, ...] = tuple(
    spec.name for spec in PLATFORM_EVENT_CATALOG
)

#: The names that are registered but never emitted by Phase 11.22.
RESERVED_PLATFORM_EVENT_NAMES: frozenset[str] = frozenset(
    spec.name
    for spec in PLATFORM_EVENT_CATALOG
    if spec.disposition
    is ProducerDisposition.REGISTERED_RESERVED_OWNER_NOT_YET_AVAILABLE
)

_CATALOG_BY_NAME: dict[str, PlatformEventSpec] = {
    spec.name: spec for spec in PLATFORM_EVENT_CATALOG
}


def platform_event_names() -> tuple[str, ...]:
    """Return the catalog names in catalog order."""

    return PLATFORM_EVENT_NAMES


def reserved_platform_event_names() -> frozenset[str]:
    """Return the catalog names Phase 11.22 must never emit."""

    return RESERVED_PLATFORM_EVENT_NAMES


def is_platform_event_name(event_type: str) -> bool:
    """Return whether *event_type* is one of the twenty catalog names."""

    return event_type in _CATALOG_BY_NAME


def catalog_spec(name: str) -> PlatformEventSpec:
    """Return the catalog row for *name*, failing closed when it is absent."""

    try:
        return _CATALOG_BY_NAME[name]
    except KeyError as exc:
        raise KeyError(f"'{name}' is not a Phase 11.22 platform event") from exc


def specs_by_disposition(
    disposition: ProducerDisposition,
) -> tuple[PlatformEventSpec, ...]:
    """Return every catalog row carrying *disposition*, in catalog order."""

    if not isinstance(disposition, ProducerDisposition):
        raise TypeError("disposition must be a ProducerDisposition")
    return tuple(
        spec for spec in PLATFORM_EVENT_CATALOG if spec.disposition is disposition
    )


def canonical_registration_names() -> tuple[str, ...]:
    """Return the subset of catalog names registered by the canonical map.

    Used by the catalog tests to prove the catalog is closed against the one
    canonical registration authority rather than carrying its own registry.
    """

    return tuple(
        name for name in PLATFORM_EVENT_NAMES if name in EVENT_TYPE_CATEGORY_MAP
    )
