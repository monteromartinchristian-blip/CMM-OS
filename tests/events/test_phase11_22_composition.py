"""Phase 11.22 — event-system composition and durable storage configuration.

These tests prove the Phase 11.22 composition contributes exactly the canonical
event-system service bindings through the existing Phase 11.1 container, that the
real Orchestrator receives the real production sink through the frozen
``orchestration.event_sink`` seam, that no second container or service locator is
introduced, and that the durable storage location is explicit, deterministic,
never the source tree, and fails safely when invalid.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cmm.events.platform_module import (
    EVENT_BUS_SERVICE_ID,
    EVENT_DEAD_LETTER_QUEUE_SERVICE_ID,
    EVENT_REGISTRY_SERVICE_ID,
    EVENT_REPLAYER_SERVICE_ID,
    EVENT_REPOSITORY_SERVICE_ID,
    EVENT_SYSTEM_MODULE_ID,
    EVENT_SYSTEM_ORCHESTRATION_SINK_SERVICE_ID,
    EVENT_SYSTEM_SERVICE_ID,
    EVENT_SYSTEM_SERVICE_IDS,
    build_event_system_composition,
)
from cmm.events.storage import (
    SOURCE_TREE_STORAGE_ERROR,
    EventStorageConfigurationError,
    default_event_store_directory,
    default_event_store_path,
    event_store_path,
    is_inside_source_tree,
    resolve_data_directory,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# ── Composition bindings ─────────────────────────────────────────────────────


def test_composition_contributes_exactly_the_canonical_event_services(tmp_path) -> None:
    composition = build_event_system_composition(
        event_store_path=tmp_path / "events.jsonl"
    )

    ids = tuple(
        binding.descriptor.service_id for binding in composition.module.contribute(None)
    )

    assert composition.module.module_id == EVENT_SYSTEM_MODULE_ID
    assert sorted(ids) == sorted(EVENT_SYSTEM_SERVICE_IDS)
    assert set(ids) == {
        EVENT_BUS_SERVICE_ID,
        EVENT_DEAD_LETTER_QUEUE_SERVICE_ID,
        EVENT_REGISTRY_SERVICE_ID,
        EVENT_REPLAYER_SERVICE_ID,
        EVENT_REPOSITORY_SERVICE_ID,
        EVENT_SYSTEM_ORCHESTRATION_SINK_SERVICE_ID,
        EVENT_SYSTEM_SERVICE_ID,
    }


def test_phase11_22_module_does_not_reclaim_the_orchestration_sink_identity() -> None:
    """The frozen Phase 11.2 ``orchestration.event_sink`` identity stays Phase 11.2."""

    assert "orchestration.event_sink" not in EVENT_SYSTEM_SERVICE_IDS


def test_every_binding_declares_an_enforceable_runtime_contract(tmp_path) -> None:
    composition = build_event_system_composition(
        event_store_path=tmp_path / "events.jsonl"
    )

    for binding in composition.module.contribute(None):
        contract = binding.runtime_contract
        assert contract is not None
        assert isinstance(binding.implementation, contract), (
            binding.descriptor.service_id
        )


def test_bindings_reuse_the_real_canonical_components(tmp_path) -> None:
    from cmm.agent_runtime.runtime_event_bus import AgentRuntimeEventBus
    from cmm.agent_runtime.runtime_event_dead_letter import (
        InMemoryAgentRuntimeDeadLetterQueue,
    )
    from cmm.agent_runtime.runtime_event_registry import AgentRuntimeEventRegistry
    from cmm.agent_runtime.runtime_event_replay import AgentRuntimeEventReplayer
    from cmm.agent_runtime.runtime_event_repository import (
        FileAgentRuntimeEventRepository,
    )
    from cmm.events.event_system import EventSystem

    composition = build_event_system_composition(
        event_store_path=tmp_path / "events.jsonl"
    )

    assert isinstance(composition.registry, AgentRuntimeEventRegistry)
    assert isinstance(composition.repository, FileAgentRuntimeEventRepository)
    assert isinstance(composition.bus, AgentRuntimeEventBus)
    assert isinstance(composition.replayer, AgentRuntimeEventReplayer)
    assert isinstance(composition.dead_letters, InMemoryAgentRuntimeDeadLetterQueue)
    assert isinstance(composition.system, EventSystem)


def test_facade_binding_carries_the_one_event_authority(tmp_path) -> None:
    from cmm.events.platform_module import EVENT_SYSTEM_AUTHORITY

    composition = build_event_system_composition(
        event_store_path=tmp_path / "events.jsonl"
    )
    binding = next(
        item
        for item in composition.module.contribute(None)
        if item.descriptor.service_id == EVENT_SYSTEM_SERVICE_ID
    )

    assert binding.descriptor.authority == EVENT_SYSTEM_AUTHORITY


def test_two_compositions_share_no_mutable_state(tmp_path) -> None:
    first = build_event_system_composition(event_store_path=tmp_path / "a.jsonl")
    second = build_event_system_composition(event_store_path=tmp_path / "b.jsonl")

    first.system.publish("message.received", {"request_id": "req-1"})

    assert first.repository.count() == 1
    assert second.repository.count() == 0
    assert first.system is not second.system
    assert first.bus is not second.bus


def test_composition_path_is_the_injected_path(tmp_path) -> None:
    target = tmp_path / "nested" / "events.jsonl"
    composition = build_event_system_composition(event_store_path=target)

    assert composition.repository.path == target


def test_composition_has_no_module_level_singleton() -> None:
    import cmm.events.platform_module as module

    for name, value in vars(module).items():
        assert not (value is None) or name.startswith("_"), name
        assert getattr(value, "__class__", None).__name__ != "EventSystemComposition"


# ── Real Phase 11.1 container composition ────────────────────────────────────


def test_container_resolves_every_event_service_and_the_real_sink(tmp_path) -> None:
    """The canonical Phase 11.1 composition resolves the Phase 11.22 bindings."""

    from cmm.domains.resolver import DefaultDomainResolver
    from cmm.events.orchestration_adapter import PlatformOrchestrationEventSink
    from cmm.orchestration.agent_router import CanonicalAgentRouter
    from cmm.orchestration.context import DefaultContextResolver
    from cmm.orchestration.decision_repository import (
        InMemoryOrchestrationDecisionRepository,
    )
    from cmm.orchestration.domain_router import CanonicalDomainRouter
    from cmm.orchestration.intent import DeterministicIntentResolver
    from cmm.orchestration.orchestrator import Orchestrator
    from cmm.orchestration.platform_module import (
        ORCHESTRATION_SERVICE_IDS,
        build_orchestration_composition_module,
    )
    from cmm.orchestration.policy import DefaultOrchestrationPolicy
    from cmm.platform.configuration import CompositionConfiguration
    from cmm.platform.container import ApplicationContainer

    composition = build_event_system_composition(
        event_store_path=tmp_path / "events.jsonl"
    )

    orchestrator = Orchestrator(
        intent_resolver=DeterministicIntentResolver(),
        context_resolver=DefaultContextResolver(session_store=None),
        domain_router=CanonicalDomainRouter(resolver=DefaultDomainResolver()),
        agent_router=CanonicalAgentRouter(),
        policy=DefaultOrchestrationPolicy(),
        decision_repository=InMemoryOrchestrationDecisionRepository(),
        event_sink=composition.orchestration_sink,
    )

    orchestration_module = build_orchestration_composition_module(
        intent_resolver=DeterministicIntentResolver(),
        context_resolver=DefaultContextResolver(session_store=None),
        domain_router=CanonicalDomainRouter(resolver=DefaultDomainResolver()),
        agent_router=CanonicalAgentRouter(),
        policy=DefaultOrchestrationPolicy(),
        decision_repository=InMemoryOrchestrationDecisionRepository(),
        event_sink=composition.orchestration_sink,
        orchestrator=orchestrator,
    )

    container = ApplicationContainer.build(
        CompositionConfiguration(
            required_services=(
                *ORCHESTRATION_SERVICE_IDS,
                *EVENT_SYSTEM_SERVICE_IDS,
            ),
            enabled_modules=(EVENT_SYSTEM_MODULE_ID, "orchestration"),
        ),
        modules=(composition.module, orchestration_module),
    )

    assert container.get_service(EVENT_BUS_SERVICE_ID) is composition.bus
    assert container.get_service(EVENT_SYSTEM_SERVICE_ID) is composition.system
    # The frozen Phase 11.2 seam resolves to the real Phase 11.22 production sink.
    assert container.get_service("orchestration.event_sink") is (
        composition.orchestration_sink
    )
    assert isinstance(
        container.get_service("orchestration.event_sink"),
        PlatformOrchestrationEventSink,
    )
    # The Orchestrator really holds that same object.
    assert container.get_service("orchestration.orchestrator") is orchestrator


def test_container_composition_defines_no_second_container(tmp_path) -> None:
    import ast

    module_path = (
        Path(__file__).resolve().parents[2] / "cmm" / "events" / "platform_module.py"
    )
    tree = ast.parse(module_path.read_text())
    names = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]

    assert not any(name.endswith("Container") for name in names)


def test_composition_module_uses_no_service_locator(tmp_path) -> None:
    module_path = (
        Path(__file__).resolve().parents[2] / "cmm" / "events" / "platform_module.py"
    )
    source = module_path.read_text()

    for token in ("get_service(", "ServiceLocator", "resolve_service("):
        assert token not in source


# ── Storage configuration ────────────────────────────────────────────────────


def test_explicit_data_directory_always_wins(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CMM_OS_DATA_DIR", str(tmp_path / "from-env"))

    assert resolve_data_directory(tmp_path / "explicit") == tmp_path / "explicit"


def test_source_tree_is_never_the_default_storage(tmp_path) -> None:
    default_directory = default_event_store_directory(tmp_path / "data")
    default_path = default_event_store_path(tmp_path / "data")

    assert not is_inside_source_tree(default_directory)
    assert not is_inside_source_tree(default_path)
    assert default_path == tmp_path / "data" / "events" / "runtime_events.jsonl"


def test_default_runtime_storage_is_outside_the_source_tree() -> None:
    """The runtime default must never be the CMM OS source tree."""

    resolved = default_event_store_path()

    assert not is_inside_source_tree(resolved)
    assert REPO_ROOT not in resolved.parents


def test_default_storage_path_is_deterministic() -> None:
    first = default_event_store_path()
    second = default_event_store_path()

    assert first == second


def test_storage_inside_the_source_tree_is_refused() -> None:
    with pytest.raises(EventStorageConfigurationError) as error:
        event_store_path(REPO_ROOT / ".cmm" / "events")

    assert error.value.code == SOURCE_TREE_STORAGE_ERROR


def test_storage_refusal_can_be_bypassed_only_explicitly() -> None:
    allowed = event_store_path(REPO_ROOT / ".cmm" / "events", allow_source_tree=True)

    assert is_inside_source_tree(allowed)


def test_blank_data_directory_fails_safely() -> None:
    with pytest.raises(EventStorageConfigurationError):
        resolve_data_directory("   ")


def test_invalid_data_directory_type_fails_safely() -> None:
    with pytest.raises(TypeError):
        resolve_data_directory(123)  # type: ignore[arg-type]


def test_blank_filename_fails_safely(tmp_path) -> None:
    with pytest.raises(EventStorageConfigurationError):
        event_store_path(tmp_path / "data", filename="  ")


def test_environment_override_is_honoured(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("CMM_OS_DATA_DIR", str(tmp_path / "env-data"))

    assert default_event_store_path() == (
        tmp_path / "env-data" / "events" / "runtime_events.jsonl"
    )


def test_parent_creation_is_bounded_to_the_configured_path(tmp_path) -> None:
    from cmm.agent_runtime.runtime_event_repository import (
        FileAgentRuntimeEventRepository,
    )

    target = tmp_path / "events" / "runtime_events.jsonl"
    FileAgentRuntimeEventRepository(target)

    assert sorted(entry.name for entry in tmp_path.iterdir()) == ["events"]


def test_unwritable_configured_location_fails_safely(tmp_path) -> None:
    import os

    from cmm.agent_runtime.runtime_event_errors import (
        AgentRuntimeEventRepositoryError,
    )
    from cmm.agent_runtime.runtime_event_repository import (
        FileAgentRuntimeEventRepository,
    )

    blocked = tmp_path / "blocked"
    blocked.mkdir()
    target = blocked / "nested" / "events.jsonl"
    os.chmod(blocked, 0o500)
    try:
        with pytest.raises(AgentRuntimeEventRepositoryError):
            FileAgentRuntimeEventRepository(target)
    finally:
        os.chmod(blocked, 0o700)


def test_storage_module_introduces_no_settings_framework() -> None:
    module_path = Path(__file__).resolve().parents[2] / "cmm" / "events" / "storage.py"
    source = module_path.read_text()

    for token in ("ConfigParser", "tomllib", "yaml", "SettingsRegistry", "getenv"):
        assert token not in source
