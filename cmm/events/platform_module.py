"""Phase 11.22 — Phase 11.1 composition contribution.

``build_event_system_composition_module`` returns a side-effect-free
``StaticCompositionModule`` contribution containing the one canonical set of
Phase 11.22 event-system service bindings.

Phase 11.1 remains the composition core: this module adds new service bindings
only, changes no Phase 11.1 semantics, and ``cmm.platform`` never imports this
package.

Every binding declares an enforceable runtime contract, so an unrelated object
can never claim an event-system service identity:

* the event bus must really be the one canonical ``AgentRuntimeEventBus``;
* the registry must really be the canonical ``AgentRuntimeEventRegistry``;
* the repository must implement the canonical ``AgentRuntimeEventRepository``;
* the dead-letter queue must be the canonical in-memory dead-letter queue;
* the orchestration sink must satisfy the frozen Phase 11.2
  ``OrchestrationEventSink`` protocol.

No global singleton is created, no service locator is introduced, and the
builder constructs no subsystem: every collaborator is an already-constructed
object supplied by the composition root.

See ``docs/reference/phase-11-event-system.md``.
"""

from __future__ import annotations

from typing import Any

from cmm.agent_runtime.runtime_event_bus import AgentRuntimeEventBus
from cmm.agent_runtime.runtime_event_dead_letter import (
    InMemoryAgentRuntimeDeadLetterQueue,
)
from cmm.agent_runtime.runtime_event_registry import AgentRuntimeEventRegistry
from cmm.agent_runtime.runtime_event_replay import AgentRuntimeEventReplayer
from cmm.agent_runtime.runtime_event_repository import AgentRuntimeEventRepository
from cmm.platform.contracts import (
    ContractMetadata,
    ServiceBinding,
    ServiceDependency,
    ServiceDescriptor,
    ServiceMode,
)
from cmm.platform.modules import StaticCompositionModule

__all__ = [
    "EVENT_BUS_SERVICE_ID",
    "EVENT_DEAD_LETTER_QUEUE_SERVICE_ID",
    "EVENT_REGISTRY_SERVICE_ID",
    "EVENT_REPLAYER_SERVICE_ID",
    "EVENT_REPOSITORY_SERVICE_ID",
    "EVENT_SYSTEM_AUTHORITY",
    "EVENT_SYSTEM_CONTRACT_VERSION",
    "EVENT_SYSTEM_MODULE_ID",
    "EVENT_SYSTEM_ORCHESTRATION_SINK_SERVICE_ID",
    "EVENT_SYSTEM_OWNER",
    "EVENT_SYSTEM_SCHEMA_VERSION",
    "EVENT_SYSTEM_SERVICE_ID",
    "EVENT_SYSTEM_SERVICE_IDS",
    "EventSystemComposition",
    "build_event_system_composition",
    "build_event_system_composition_module",
]

EVENT_SYSTEM_MODULE_ID = "phase11_22_events"
EVENT_SYSTEM_OWNER = "cmm.events"
EVENT_SYSTEM_CONTRACT_VERSION = "1.0.0"
EVENT_SYSTEM_SCHEMA_VERSION = "1"

#: The one exclusive authority the Phase 11.22 event system owns.
EVENT_SYSTEM_AUTHORITY = "platform-event-delivery-coordinator"

EVENT_REGISTRY_SERVICE_ID = "event.registry"
EVENT_REPOSITORY_SERVICE_ID = "event.repository"
EVENT_BUS_SERVICE_ID = "event.bus"
EVENT_REPLAYER_SERVICE_ID = "event.replayer"
EVENT_DEAD_LETTER_QUEUE_SERVICE_ID = "event.dead_letter_queue"
EVENT_SYSTEM_SERVICE_ID = "event.system"

#: The Phase 11.22 production orchestration sink, exposed under an event-system
#: identity.  The frozen Phase 11.2 ``orchestration.event_sink`` identity stays
#: owned by the Phase 11.2 composition module, which binds this same object, so no
#: service identity is claimed twice.
EVENT_SYSTEM_ORCHESTRATION_SINK_SERVICE_ID = "event.orchestration_sink"

#: Stable Phase 11.22 service IDs this module contributes, in sorted order.
EVENT_SYSTEM_SERVICE_IDS: tuple[str, ...] = (
    EVENT_BUS_SERVICE_ID,
    EVENT_DEAD_LETTER_QUEUE_SERVICE_ID,
    EVENT_REGISTRY_SERVICE_ID,
    EVENT_REPLAYER_SERVICE_ID,
    EVENT_REPOSITORY_SERVICE_ID,
    EVENT_SYSTEM_ORCHESTRATION_SINK_SERVICE_ID,
    EVENT_SYSTEM_SERVICE_ID,
)

#: The composition dependency the composed facade declares.
FACADE_DEPENDENCY_IDS: tuple[str, ...] = (
    EVENT_BUS_SERVICE_ID,
    EVENT_DEAD_LETTER_QUEUE_SERVICE_ID,
    EVENT_REGISTRY_SERVICE_ID,
    EVENT_REPLAYER_SERVICE_ID,
    EVENT_REPOSITORY_SERVICE_ID,
)

#: The composition dependencies the orchestration sink adapter declares.  The sink
#: reaches the transport only through the composed facade, so its dependencies are
#: the facade plus the canonical components the facade itself depends on.
SINK_DEPENDENCY_IDS: tuple[str, ...] = (
    EVENT_BUS_SERVICE_ID,
    EVENT_DEAD_LETTER_QUEUE_SERVICE_ID,
    EVENT_REGISTRY_SERVICE_ID,
    EVENT_REPLAYER_SERVICE_ID,
    EVENT_REPOSITORY_SERVICE_ID,
    EVENT_SYSTEM_SERVICE_ID,
)


def _boundary_contract(
    service_id: str, *, owner: str = EVENT_SYSTEM_OWNER
) -> ContractMetadata:
    return ContractMetadata(
        contract_name=service_id,
        contract_version=EVENT_SYSTEM_CONTRACT_VERSION,
        schema_version=EVENT_SYSTEM_SCHEMA_VERSION,
        owner=owner,
    )


def _dependency(
    service_id: str, *, owner: str = EVENT_SYSTEM_OWNER
) -> ServiceDependency:
    return ServiceDependency(
        service_id=service_id,
        contract=_boundary_contract(service_id, owner=owner),
    )


def _implementation_id(implementation: Any) -> str:
    implementation_type = type(implementation)
    return f"{implementation_type.__module__}.{implementation_type.__qualname__}"


def _require_role_implementation(
    implementation: Any, service_id: str, runtime_contract: Any
) -> None:
    """Fail closed unless *implementation* satisfies its declared role boundary."""

    if not isinstance(implementation, runtime_contract):
        raise TypeError(
            f"{service_id} implementation does not satisfy its event-system "
            f"runtime contract {runtime_contract.__name__}"
        )


def _binding(
    implementation: Any,
    service_id: str,
    runtime_contract: Any,
    *,
    authority: str | None = None,
    dependencies: tuple[ServiceDependency, ...] = (),
) -> ServiceBinding:
    _require_role_implementation(implementation, service_id, runtime_contract)

    return ServiceBinding(
        descriptor=ServiceDescriptor(
            service_id=service_id,
            contract=_boundary_contract(service_id),
            implementation_id=_implementation_id(implementation),
            dependencies=dependencies,
            mode=ServiceMode.LOCAL,
            authority=authority,
        ),
        implementation=implementation,
        runtime_contract=runtime_contract,
    )


def build_event_system_composition_module(
    *,
    registry: Any,
    repository: Any,
    bus: Any,
    replayer: Any,
    dead_letters: Any,
    event_system: Any,
    orchestration_sink: Any,
) -> StaticCompositionModule:
    """Return the Phase 11.1 contribution for the Phase 11.22 event system.

    The builder constructs no subsystem: every collaborator is an
    already-constructed object supplied by the composition root, and anything that
    does not satisfy its declared runtime contract fails closed here.
    """

    facade_dependencies = tuple(
        _dependency(service_id) for service_id in FACADE_DEPENDENCY_IDS
    )
    sink_dependencies = tuple(
        _dependency(service_id) for service_id in SINK_DEPENDENCY_IDS
    )

    from cmm.events.event_system import EventSystem
    from cmm.orchestration.events import OrchestrationEventSink

    bindings = (
        _binding(registry, EVENT_REGISTRY_SERVICE_ID, AgentRuntimeEventRegistry),
        _binding(repository, EVENT_REPOSITORY_SERVICE_ID, AgentRuntimeEventRepository),
        _binding(bus, EVENT_BUS_SERVICE_ID, AgentRuntimeEventBus),
        _binding(replayer, EVENT_REPLAYER_SERVICE_ID, AgentRuntimeEventReplayer),
        _binding(
            dead_letters,
            EVENT_DEAD_LETTER_QUEUE_SERVICE_ID,
            InMemoryAgentRuntimeDeadLetterQueue,
        ),
        _binding(
            event_system,
            EVENT_SYSTEM_SERVICE_ID,
            EventSystem,
            authority=EVENT_SYSTEM_AUTHORITY,
            dependencies=facade_dependencies,
        ),
        _binding(
            orchestration_sink,
            EVENT_SYSTEM_ORCHESTRATION_SINK_SERVICE_ID,
            OrchestrationEventSink,
            dependencies=sink_dependencies,
        ),
    )

    return StaticCompositionModule(EVENT_SYSTEM_MODULE_ID, bindings)


class EventSystemComposition:
    """One composed, independent Phase 11.22 event-system graph.

    Holds the canonical components the Phase 11.1 module binds, so a composition
    root can wire the orchestrator to the real production event sink and keep a
    reference to the same facade for inspection.
    """

    __slots__ = (
        "bus",
        "dead_letters",
        "module",
        "orchestration_sink",
        "registry",
        "replayer",
        "repository",
        "system",
    )

    def __init__(
        self,
        *,
        module: StaticCompositionModule,
        registry: AgentRuntimeEventRegistry,
        repository: AgentRuntimeEventRepository,
        bus: AgentRuntimeEventBus,
        replayer: AgentRuntimeEventReplayer,
        dead_letters: InMemoryAgentRuntimeDeadLetterQueue,
        system: Any,
        orchestration_sink: Any,
    ) -> None:
        self.module = module
        self.registry = registry
        self.repository = repository
        self.bus = bus
        self.replayer = replayer
        self.dead_letters = dead_letters
        self.system = system
        self.orchestration_sink = orchestration_sink


def build_event_system_composition(
    *,
    event_store_path: Any,
    max_delivery_attempts: int = 1,
) -> EventSystemComposition:
    """Build one fresh Phase 11.22 event system and its composition module.

    Every canonical component is the real Phase 9 implementation.  Nothing global
    is created or cached, so two calls yield two fully independent graphs.  The
    durable repository is bound to the explicitly supplied storage path, which the
    caller owns (see :mod:`cmm.events.storage`).
    """

    from cmm.agent_runtime.runtime_event_repository import (
        FileAgentRuntimeEventRepository,
    )
    from cmm.events.event_system import EventSystem
    from cmm.events.orchestration_adapter import PlatformOrchestrationEventSink

    registry = AgentRuntimeEventRegistry(strict_mode=True)
    repository = FileAgentRuntimeEventRepository(event_store_path)
    bus = AgentRuntimeEventBus(
        registry=registry, max_delivery_attempts=max_delivery_attempts
    )
    dead_letters = InMemoryAgentRuntimeDeadLetterQueue()
    system = EventSystem(
        registry=registry,
        repository=repository,
        bus=bus,
        dead_letters=dead_letters,
    )
    replayer = system._replayer
    orchestration_sink = PlatformOrchestrationEventSink(system)

    module = build_event_system_composition_module(
        registry=registry,
        repository=repository,
        bus=bus,
        replayer=replayer,
        dead_letters=dead_letters,
        event_system=system,
        orchestration_sink=orchestration_sink,
    )

    return EventSystemComposition(
        module=module,
        registry=registry,
        repository=repository,
        bus=bus,
        replayer=replayer,
        dead_letters=dead_letters,
        system=system,
        orchestration_sink=orchestration_sink,
    )
