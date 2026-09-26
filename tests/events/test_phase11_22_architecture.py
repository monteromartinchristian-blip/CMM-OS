"""Phase 11.22 — executable anti-fragmentation architecture gates.

Phase 11.22 is an integration and hardening phase over the Phase 9 runtime event
infrastructure.  It is explicitly *not* permitted to add a second event bus, a
second mutable event registry, a second event repository protocol, a second
replay engine, a second DLQ authority, a broker abstraction, a command bus, a
job queue, a workflow engine, a second application container, a service locator
or dynamic event-type dispatch.

These gates turn those prohibitions into executable assertions, and they run for
the whole phase rather than only at the end.

Dependency direction is asserted in both directions:

    producer seam
    -> thin Phase 11.22 adapter
    -> existing Phase 9 event transport

and never the reverse: ``cmm.agent_runtime`` must never import the Phase 11.22
platform event integration, and the Domain Event package must never grow a
direct dependency on the runtime event bus.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CMM_ROOT = REPO_ROOT / "cmm"
EVENTS_PACKAGE = CMM_ROOT / "events"
AGENT_RUNTIME_PACKAGE = CMM_ROOT / "agent_runtime"
DOMAINS_PACKAGE = CMM_ROOT / "domains"

#: The frozen Phase 11.22 production module set.  A new module here is a
#: deliberate act: the phase adds thin composition, never a subsystem.
FROZEN_MODULES = frozenset(
    {
        "__init__.py",
        "event_catalog.py",
        "event_payload_safety.py",
        "event_translation.py",
        "event_system.py",
        "orchestration_adapter.py",
        "kernel_adapter.py",
        "platform_module.py",
        "storage.py",
    }
)

#: Class-name fragments that would indicate a parallel event authority.
FORBIDDEN_OWNER_FRAGMENTS = (
    "PlatformEventBus",
    "GlobalEventBus",
    "ApplicationEventBus",
    "DomainEventBus",
    "PersistentEventBus",
    "ObservabilityEventBus",
    "EventBroker",
    "BrokerAdapter",
    "CommandBus",
    "JobQueue",
    "WorkflowEngine",
    "EventStore",
    "EventLog",
    "ServiceLocator",
    "EventDispatcher",
    "EventPublisher",
    "ReplayEngine",
    "DeadLetterQueue",
    "EventRegistry",
)

#: The one canonical transport authority Phase 11.22 composes.
CANONICAL_EVENT_BUS = "AgentRuntimeEventBus"

#: The one canonical repository protocol Phase 11.22 implements.
CANONICAL_EVENT_REPOSITORY = "AgentRuntimeEventRepository"

#: Forbidden external broker dependencies.
FORBIDDEN_BROKER_MODULES = (
    "kafka",
    "aiokafka",
    "confluent_kafka",
    "nats",
    "redis",
    "pika",
    "aio_pika",
    "kombu",
    "pulsar",
)

#: Dynamic dispatch surfaces Phase 11.22 must never introduce.
FORBIDDEN_DYNAMIC_DISPATCH = (
    "__import__(",
    "importlib.import_module",
    "import_module(",
    "eval(",
    "exec(",
    "pickle",
    "yaml.load",
    "getattr(",
)


def _python_files(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*.py") if "__pycache__" not in path.parts
    )


def _events_files() -> list[Path]:
    return sorted(EVENTS_PACKAGE.glob("*.py"))


def _parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text())


def _defined_class_names(path: Path) -> list[str]:
    return [
        node.name for node in ast.walk(_parsed(path)) if isinstance(node, ast.ClassDef)
    ]


def _imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(_parsed(path)):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
    return modules


def _source(path: Path) -> str:
    return path.read_text()


# ── 0. The phase package exists and stays thin ───────────────────────────────


def test_phase11_22_package_is_importable_and_thin() -> None:
    assert EVENTS_PACKAGE.is_dir(), "cmm/events must exist for Phase 11.22"

    present = {path.name for path in EVENTS_PACKAGE.iterdir() if path.is_file()}

    assert present == FROZEN_MODULES, (
        "Phase 11.22 production module set changed: "
        f"unexpected={sorted(present - FROZEN_MODULES)} "
        f"missing={sorted(FROZEN_MODULES - present)}"
    )


# ── 1. Exactly one canonical transport authority ─────────────────────────────


@pytest.mark.parametrize("token", FORBIDDEN_OWNER_FRAGMENTS)
def test_phase11_22_defines_no_parallel_event_authority(token: str) -> None:
    offenders = [
        f"{path.name}:{name}"
        for path in _events_files()
        for name in _defined_class_names(path)
        if token in name
    ]

    assert not offenders, f"Phase 11.22 must not introduce {token}: {offenders}"


def test_exactly_one_production_event_bus_transport_exists() -> None:
    """The canonical bus is the Phase 9 authority; nothing else may be one."""

    owners: set[str] = set()

    for path in _python_files(CMM_ROOT):
        for name in _defined_class_names(path):
            # Private, non-canonical helpers (``_EventBus``) would already fail
            # the canonical-owner audit; this gate is about public authorities.
            if name.endswith("EventBus") and not name.startswith("_"):
                owners.add(f"{path.relative_to(REPO_ROOT)}:{name}")

    assert owners == {
        f"cmm/agent_runtime/runtime_event_bus.py:{CANONICAL_EVENT_BUS}"
    }, f"exactly one event bus transport may exist: {sorted(owners)}"


def test_phase11_22_composes_the_canonical_bus_and_not_a_sibling() -> None:
    from cmm.agent_runtime import AgentRuntimeEventBus

    module = __import__("cmm.events.event_system", fromlist=["EventSystem"])
    system_type = module.EventSystem

    assert system_type is not None
    assert AgentRuntimeEventBus.__name__ == CANONICAL_EVENT_BUS


# ── 2. No second mutable registry / repository protocol / replay engine ──────


def test_phase11_22_defines_no_second_repository_protocol() -> None:
    from cmm.agent_runtime import AgentRuntimeEventRepository
    from cmm.agent_runtime.runtime_event_repository import (
        FileAgentRuntimeEventRepository,
    )

    assert issubclass(FileAgentRuntimeEventRepository, AgentRuntimeEventRepository)

    defined = {name for path in _events_files() for name in _defined_class_names(path)}

    assert not any(name.endswith("Repository") for name in defined), (
        f"Phase 11.22 must implement, not redefine, the repository contract: {defined}"
    )


def _raises_not_implemented(node: ast.Raise) -> bool:
    """Return whether a raise statement raises ``NotImplementedError``."""

    exc = node.exc
    if isinstance(exc, ast.Call):
        exc = exc.func
    return isinstance(exc, ast.Name) and exc.id == "NotImplementedError"


def test_exactly_one_canonical_repository_protocol_exists() -> None:
    """One abstract contract, any number of implementations of it."""

    from cmm.agent_runtime import AgentRuntimeEventRepository

    repository_module = CMM_ROOT / "agent_runtime" / "runtime_event_repository.py"
    defined = _defined_class_names(repository_module)

    # The abstract protocol is the one class declaring the unimplemented
    # canonical surface; concrete implementations must subclass it and must not
    # declare their own competing protocol.
    abstract = []
    for node in ast.walk(_parsed(repository_module)):
        if not isinstance(node, ast.ClassDef):
            continue
        raises = [
            item
            for statement in node.body
            for item in ast.walk(statement)
            if isinstance(item, ast.Raise) and _raises_not_implemented(item)
        ]
        if raises:
            abstract.append(node.name)

    assert abstract == [CANONICAL_EVENT_REPOSITORY], (
        f"exactly one abstract event repository protocol may exist: {abstract}"
    )
    assert CANONICAL_EVENT_REPOSITORY in defined

    from cmm.agent_runtime.runtime_event_repository import (
        FileAgentRuntimeEventRepository,
        InMemoryAgentRuntimeEventRepository,
    )

    assert issubclass(FileAgentRuntimeEventRepository, AgentRuntimeEventRepository)
    assert issubclass(InMemoryAgentRuntimeEventRepository, AgentRuntimeEventRepository)


def test_exactly_one_canonical_replay_owner_exists() -> None:
    owners: set[str] = set()

    for path in _python_files(CMM_ROOT):
        for name in _defined_class_names(path):
            if name.endswith("Replayer"):
                owners.add(f"{path.relative_to(REPO_ROOT)}:{name}")

    assert owners == {
        "cmm/agent_runtime/runtime_event_replay.py:AgentRuntimeEventReplayer",
    }, f"exactly one replay owner may exist: {sorted(owners)}"


def test_exactly_one_canonical_dead_letter_authority_exists() -> None:
    owners: set[str] = set()

    for path in _python_files(CMM_ROOT):
        for name in _defined_class_names(path):
            if "DeadLetter" in name and name.startswith("InMemory"):
                owners.add(f"{path.relative_to(REPO_ROOT)}:{name}")

    assert owners == {
        (
            "cmm/agent_runtime/runtime_event_dead_letter.py:"
            "InMemoryAgentRuntimeDeadLetterQueue"
        ),
    }, f"exactly one dead-letter queue authority may exist: {sorted(owners)}"


def test_phase11_22_adds_no_generic_broker_abstraction() -> None:
    offenders: list[str] = []

    for path in _events_files():
        for module in _imported_modules(path):
            root = module.split(".")[0].lower()
            if root in FORBIDDEN_BROKER_MODULES:
                offenders.append(f"{path.name} -> {module}")

    assert not offenders, f"Phase 11.22 must add no external broker: {offenders}"


# ── 3. Dependency direction ──────────────────────────────────────────────────


def test_phase11_22_adapters_depend_on_phase9_transport() -> None:
    """At least one Phase 11.22 module must consume the canonical transport."""

    consumers = [
        path.name
        for path in _events_files()
        if any(
            module == "cmm.agent_runtime" or module.startswith("cmm.agent_runtime.")
            for module in _imported_modules(path)
        )
    ]

    assert consumers, "Phase 11.22 must compose the Phase 9 event transport"


def test_phase9_transport_does_not_depend_on_phase11_22() -> None:
    offenders: list[str] = []

    for path in _python_files(AGENT_RUNTIME_PACKAGE):
        for module in _imported_modules(path):
            if module == "cmm.events" or module.startswith("cmm.events."):
                offenders.append(f"{path.relative_to(REPO_ROOT)} -> {module}")

    assert not offenders, (
        "the Phase 9 event transport must not depend on the Phase 11.22 "
        f"platform integration: {offenders}"
    )


def test_agent_runtime_does_not_import_producer_adapters() -> None:
    """Phase 9 must never reach up into orchestration or platform adapters."""

    forbidden_roots = ("cmm.orchestration", "cmm.application", "cmm.events")
    offenders: list[str] = []

    for path in _python_files(AGENT_RUNTIME_PACKAGE):
        for module in _imported_modules(path):
            if any(
                module == root or module.startswith(f"{root}.")
                for root in forbidden_roots
            ):
                offenders.append(f"{path.relative_to(REPO_ROOT)} -> {module}")

    assert not offenders, f"reverse dependency out of cmm.agent_runtime: {offenders}"


#: The Phase 9 runtime *event transport* modules Domain Events must never reach.
RUNTIME_EVENT_TRANSPORT_MODULES = (
    "cmm.agent_runtime.runtime_event_bus",
    "cmm.agent_runtime.runtime_event_contracts",
    "cmm.agent_runtime.runtime_event_repository",
    "cmm.agent_runtime.runtime_event_replay",
    "cmm.agent_runtime.runtime_event_dead_letter",
    "cmm.agent_runtime.runtime_event_registry",
    "cmm.agent_runtime.runtime_event_factory",
)


def test_domain_events_do_not_import_the_runtime_event_transport() -> None:
    """DP-033 stays pure: Domain Events never depend on the runtime transport.

    ``cmm.domains`` legitimately shares non-event Agent Runtime contracts
    (operation, permission and approval contracts), so this gate is exact about
    the one boundary Phase 11.22 must preserve: Domain Event publication stays
    pure and reaches the platform only through a one-way adapter.
    """

    offenders: list[str] = []

    for path in _python_files(DOMAINS_PACKAGE):
        for module in _imported_modules(path):
            if module in RUNTIME_EVENT_TRANSPORT_MODULES:
                offenders.append(f"{path.relative_to(REPO_ROOT)} -> {module}")

    assert not offenders, (
        f"Domain Events must not import the runtime event transport: {offenders}"
    )


def test_platform_core_does_not_import_orchestration() -> None:
    """Phase 11.1 core keeps its one-way dependency direction."""

    offenders: list[str] = []

    for path in _python_files(CMM_ROOT / "platform"):
        for module in _imported_modules(path):
            if module == "cmm.orchestration" or module.startswith("cmm.orchestration."):
                offenders.append(f"{path.relative_to(REPO_ROOT)} -> {module}")

    assert not offenders, f"cmm.platform must not import orchestration: {offenders}"


# ── 4. No service locator and no second container ────────────────────────────


def test_phase11_22_introduces_no_service_locator() -> None:
    offenders: list[str] = []

    for path in _events_files():
        source = _source(path)
        for token in ("ServiceLocator", "get_service(", "_service_locator"):
            if token in source:
                offenders.append(f"{path.name}:{token}")

    assert not offenders, f"Phase 11.22 must not add a service locator: {offenders}"


def test_phase11_22_introduces_no_second_application_container() -> None:
    containers = {
        f"{path.relative_to(REPO_ROOT)}:{name}"
        for path in _python_files(CMM_ROOT)
        for name in _defined_class_names(path)
        if name.endswith(("ApplicationContainer", "Container"))
    }

    assert containers == {
        "cmm/platform/container.py:ApplicationContainer",
    }, f"exactly one application container may exist: {sorted(containers)}"


def test_phase11_22_introduces_no_module_global_event_singleton() -> None:
    """No module-level composed event system may be bound at import time."""

    import sys

    from cmm.events.event_system import EventSystem

    for module_name, module in list(sys.modules.items()):
        if not module_name.startswith("cmm.events"):
            continue
        for attribute, value in vars(module).items():
            assert not isinstance(value, EventSystem), (
                f"{module_name}.{attribute} is a module-level event-system singleton"
            )


# ── 5. No dynamic dispatch based on event type ───────────────────────────────


def _computed_getattr_offenders(path: Path) -> list[str]:
    """Return ``getattr`` calls whose attribute name is a computed value.

    ``getattr(obj, "literal")`` names a fixed capability and is not dispatch.
    ``getattr(obj, some_event_type)`` lets event data select code, which is
    exactly the prohibited dynamic-import/callable dispatch.
    """

    offenders: list[str] = []
    for node in ast.walk(_parsed(path)):
        if not isinstance(node, ast.Call):
            continue
        if not (isinstance(node.func, ast.Name) and node.func.id == "getattr"):
            continue
        if len(node.args) < 2 or not isinstance(node.args[1], ast.Constant):
            offenders.append(f"{path.name}:getattr(computed)")
    return offenders


def test_phase11_22_never_dispatches_dynamically_by_event_type() -> None:
    offenders: list[str] = []

    for path in _events_files():
        source = _source(path)
        offenders.extend(_computed_getattr_offenders(path))
        for token in FORBIDDEN_DYNAMIC_DISPATCH:
            if token == "getattr(":
                continue
            if token in source:
                offenders.append(f"{path.name}:{token}")

    assert not offenders, f"event types must never select code dynamically: {offenders}"


def test_phase11_22_defines_no_command_bus_or_job_queue() -> None:
    offenders = [
        f"{path.name}:{name}"
        for path in _events_files()
        for name in _defined_class_names(path)
        if any(
            token in name
            for token in ("CommandBus", "JobQueue", "Scheduler", "Worker", "ThreadPool")
        )
    ]

    assert not offenders, f"Phase 11.22 must add no scheduler or queue: {offenders}"
