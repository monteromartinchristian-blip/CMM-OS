"""Phase 11.22 — platform event catalog and canonical contract compatibility.

These tests prove the catalog is an immutable contract catalog (not a second
registry), that every one of the twenty historical minimum Phase 11.22 event
names is registered through the one canonical registration authority, that each
carries exactly one producer disposition, and that the Phase 11.22 additive
header fields are backward compatible.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.runtime_event_contracts import (
    AgentRuntimeEvent,
    AgentRuntimeEventHeader,
    AgentRuntimeEventPayload,
    AgentRuntimeEventSubscription,
)
from cmm.agent_runtime.runtime_event_factory import (
    AgentRuntimeEventFactory,
    AgentRuntimeEventNormalizer,
    event_fingerprint,
)
from cmm.agent_runtime.runtime_event_registry import AgentRuntimeEventRegistry
from cmm.agent_runtime.runtime_event_types import (
    EVENT_TYPE_CATEGORY_MAP,
    EventType,
    is_registered_event_type,
)
from cmm.events.event_catalog import (
    PLATFORM_EVENT_CATALOG,
    PLATFORM_EVENT_NAMES,
    RESERVED_PLATFORM_EVENT_NAMES,
    PlatformEventSpec,
    ProducerDisposition,
    canonical_registration_names,
    catalog_spec,
    is_platform_event_name,
    platform_event_names,
    reserved_platform_event_names,
    specs_by_disposition,
)
from cmm.events.event_translation import (
    KERNEL_SOURCE_TRANSLATIONS,
    ORCHESTRATION_SOURCE_TRANSLATIONS,
    kernel_translation_table,
    orchestration_translation_table,
    translate_kernel_event,
    translate_orchestration_event,
)

#: The twenty frozen Phase 11.22 minimum platform event names.
EXPECTED_CATALOG: tuple[str, ...] = (
    "session.created",
    "message.received",
    "intent.resolved",
    "domain.selected",
    "reasoning.completed",
    "goal.created",
    "goal.updated",
    "workflow.started",
    "workflow.paused",
    "workflow.completed",
    "workflow.failed",
    "operation.executed",
    "validation.completed",
    "approval.requested",
    "approval.resolved",
    "knowledge.updated",
    "memory.updated",
    "backup.created",
    "plugin.failed",
    "security.alert",
)


# ── Catalog exactness ────────────────────────────────────────────────────────


def test_catalog_contains_exactly_the_frozen_minimum_event_names() -> None:
    assert PLATFORM_EVENT_NAMES == EXPECTED_CATALOG
    assert platform_event_names() == EXPECTED_CATALOG


def test_catalog_has_no_duplicate_names() -> None:
    assert len(PLATFORM_EVENT_NAMES) == len(set(PLATFORM_EVENT_NAMES))


def test_catalog_ordering_is_deterministic() -> None:
    assert PLATFORM_EVENT_NAMES == tuple(spec.name for spec in PLATFORM_EVENT_CATALOG)
    assert PLATFORM_EVENT_CATALOG == tuple(
        catalog_spec(name) for name in EXPECTED_CATALOG
    )


def test_catalog_entries_are_immutable() -> None:
    spec = PLATFORM_EVENT_CATALOG[0]

    assert isinstance(spec, PlatformEventSpec)
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.name = "mutated"  # type: ignore[misc]


def test_catalog_is_not_a_mutable_registry() -> None:
    """The catalog exposes no registration, discovery or alias surface."""

    import cmm.events.event_catalog as catalog_module

    # The catalog owns immutable values only.  The one mutable mapping reachable
    # from this module is the Phase 9 canonical registration map itself, which is
    # authoritative elsewhere; the catalog neither owns nor replaces it.
    owned_mutables = [
        name
        for name, value in vars(catalog_module).items()
        if not name.startswith("_")
        and isinstance(value, (dict, set))
        and value is not EVENT_TYPE_CATEGORY_MAP
    ]

    assert not owned_mutables, f"catalog owns mutable state: {owned_mutables}"

    assert not hasattr(catalog_module, "register")
    assert not hasattr(catalog_module, "unregister")
    assert not hasattr(catalog_module, "resolve")

    # The catalog is a frozen tuple of frozen rows.
    assert isinstance(PLATFORM_EVENT_CATALOG, tuple)
    assert isinstance(RESERVED_PLATFORM_EVENT_NAMES, frozenset)


def test_every_catalog_name_is_registered_by_the_canonical_authority() -> None:
    registry = AgentRuntimeEventRegistry(strict_mode=True)

    for name in EXPECTED_CATALOG:
        registry.ensure_registered(name)
        assert is_registered_event_type(name)
        assert name in EVENT_TYPE_CATEGORY_MAP
        assert registry.contains(name)


def test_catalog_adds_no_second_event_type_map() -> None:
    """Catalog names resolve through the Phase 9 map, not a private one."""

    assert set(canonical_registration_names()) == set(EXPECTED_CATALOG)


def test_catalog_does_not_redefine_existing_canonical_names() -> None:
    assert EventType.GOAL_CREATED == "goal.created"
    assert EventType.GOAL_UPDATED == "goal.updated"
    assert EventType.APPROVAL_REQUESTED == "approval.requested"
    assert EventType.VALIDATION_COMPLETED == "validation.completed"
    assert EventType.OPERATION_COMPLETED == "operation.completed"


def test_factory_accepts_every_catalog_event_name() -> None:
    factory = AgentRuntimeEventFactory()

    for name in EXPECTED_CATALOG:
        event = factory.create_event(name, {"reference_id": "ref-1"})
        assert event.header.event_type == name


# ── Producer disposition ─────────────────────────────────────────────────────


def test_every_catalog_event_has_exactly_one_disposition() -> None:
    for spec in PLATFORM_EVENT_CATALOG:
        assert isinstance(spec.disposition, ProducerDisposition)
        assert spec.rationale


def test_dispositions_partition_the_catalog() -> None:
    total = sum(
        len(specs_by_disposition(disposition)) for disposition in ProducerDisposition
    )

    assert total == len(PLATFORM_EVENT_CATALOG)
    assert set(
        specs_by_disposition(ProducerDisposition.CONNECTED_EXISTING_OWNER)
    ) | set(
        specs_by_disposition(ProducerDisposition.CANONICAL_EXISTING_RUNTIME_EVENT)
    ) | set(
        specs_by_disposition(
            ProducerDisposition.REGISTERED_RESERVED_OWNER_NOT_YET_AVAILABLE
        )
    ) == set(PLATFORM_EVENT_CATALOG)


#: Number words used by the module prose, so a documentation count can be derived
#: from the real disposition map instead of being restated by hand.
_NUMBER_WORDS = {
    0: "zero",
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
}


def test_module_documentation_matches_the_derived_reserved_event_count() -> None:
    """MINOR-004: the catalog prose must state the real reserved-event count.

    The expectation is derived from the disposition map, so the prose cannot
    drift away from the catalog without failing this test.
    """

    import pathlib

    from cmm.events import event_catalog

    connected = specs_by_disposition(ProducerDisposition.CONNECTED_EXISTING_OWNER)
    canonical = specs_by_disposition(
        ProducerDisposition.CANONICAL_EXISTING_RUNTIME_EVENT
    )
    reserved = specs_by_disposition(
        ProducerDisposition.REGISTERED_RESERVED_OWNER_NOT_YET_AVAILABLE
    )

    assert (len(connected), len(canonical), len(reserved)) == (12, 2, 6)

    source = pathlib.Path(event_catalog.__file__).read_text(encoding="utf-8")
    reserved_word = _NUMBER_WORDS[len(reserved)].capitalize()

    assert f"{reserved_word} of the twenty names" in source
    # The specific stale claim the audit found must be gone.
    assert "Twelve of the twenty names are therefore registered but" not in source


def test_reserved_events_name_no_owner_and_are_never_emitted() -> None:
    reserved = specs_by_disposition(
        ProducerDisposition.REGISTERED_RESERVED_OWNER_NOT_YET_AVAILABLE
    )

    assert reserved, "the catalog must be honest about events with no owner yet"
    for spec in reserved:
        assert spec.owner is None
        assert not spec.connected_evidence
        assert spec.name in RESERVED_PLATFORM_EVENT_NAMES
        assert spec.name in reserved_platform_event_names()


def test_connected_events_name_an_owner_and_cite_executable_evidence() -> None:
    connected = specs_by_disposition(ProducerDisposition.CONNECTED_EXISTING_OWNER)

    assert connected
    for spec in connected:
        assert spec.owner
        assert spec.connected_evidence
        assert spec.connected_evidence.endswith(".py")


def test_no_fabricated_owner_exists_for_reserved_capabilities() -> None:
    """Phase 11.22 must not invent backup, plugin or security producers."""

    for name in ("backup.created", "plugin.failed", "security.alert"):
        spec = catalog_spec(name)
        assert (
            spec.disposition
            is ProducerDisposition.REGISTERED_RESERVED_OWNER_NOT_YET_AVAILABLE
        )


def test_catalog_spec_fails_closed_for_unknown_name() -> None:
    assert is_platform_event_name("backup.created")
    assert not is_platform_event_name("not.a.catalog.event")

    with pytest.raises(KeyError):
        catalog_spec("not.a.catalog.event")


# ── Translation table ────────────────────────────────────────────────────────


def test_orchestration_translations_target_catalog_names() -> None:
    assert ORCHESTRATION_SOURCE_TRANSLATIONS

    for translation in ORCHESTRATION_SOURCE_TRANSLATIONS:
        assert is_platform_event_name(translation.platform_event_type)
        assert orchestration_translation_table()[translation.source_event_type] is (
            translation
        )


def test_kernel_translations_target_catalog_names() -> None:
    assert KERNEL_SOURCE_TRANSLATIONS

    for translation in KERNEL_SOURCE_TRANSLATIONS:
        assert is_platform_event_name(translation.platform_event_type)
        assert kernel_translation_table()[translation.source_event_type] is translation


def test_translation_tables_are_immutable() -> None:
    with pytest.raises(TypeError):
        orchestration_translation_table()["x"] = None  # type: ignore[index]
    with pytest.raises(TypeError):
        kernel_translation_table()["x"] = None  # type: ignore[index]


def test_unsupported_source_events_are_not_guessed() -> None:
    assert translate_orchestration_event("orchestration.route_selected") is None
    assert translate_orchestration_event("orchestration.blocked") is None
    assert translate_orchestration_event("orchestration.escalated") is None
    assert translate_kernel_event("domain.execution.started") is None
    assert translate_kernel_event("validation.step.started") is None
    assert translate_kernel_event("totally.unknown.event") is None


def test_mapping_does_not_invent_payload_fields() -> None:
    """A mapping may only name facts; it never manufactures a value."""

    for translation in (
        *ORCHESTRATION_SOURCE_TRANSLATIONS,
        *KERNEL_SOURCE_TRANSLATIONS,
    ):
        for key in translation.fact_keys:
            assert key in {
                "channel",
                "session_id",
                "intent",
                "needs_clarification",
                "status",
                "primary_domain",
                "supporting_domains",
                "approval_refs",
                "validation_id",
                "policy",
                "duration_ms",
                "workflow_id",
                "domain_id",
                "execution_id",
                "run_id",
                "node_id",
                "error_code",
                "approval_id",
            }, key


def test_translation_is_one_way_and_changes_no_source_authority() -> None:
    """The translation table returns a mapping; it publishes nothing."""

    import cmm.events.event_translation as module

    for attribute in ("publish", "emit", "dispatch"):
        assert not hasattr(module, attribute)


# ── Canonical contract compatibility ─────────────────────────────────────────


def test_legacy_header_construction_still_works() -> None:
    header = AgentRuntimeEventHeader(event_id="evt_1", event_type="goal.created")

    assert header.producer is None
    assert header.aggregate_id is None
    assert header.source == "agent_runtime"


def test_added_header_fields_are_optional_and_validated() -> None:
    header = AgentRuntimeEventHeader(
        event_id="evt_1",
        event_type="goal.created",
        producer="cmm.agent_runtime",
        aggregate_id="goal-1",
    )

    assert header.producer == "cmm.agent_runtime"
    assert header.aggregate_id == "goal-1"

    with pytest.raises(ValueError):
        AgentRuntimeEventHeader(
            event_id="evt_1", event_type="goal.created", producer=""
        )
    with pytest.raises(ValueError):
        AgentRuntimeEventHeader(
            event_id="evt_1", event_type="goal.created", aggregate_id=""
        )


def test_no_duplicate_semantic_header_field_was_introduced() -> None:
    names = [field.name for field in dataclasses.fields(AgentRuntimeEventHeader)]

    assert len(names) == len(set(names))
    assert names.count("producer") == 1
    assert names.count("aggregate_id") == 1
    # ``source`` keeps its own Phase 9 meaning and is not a producer alias.
    assert "source" in names


def test_factory_round_trips_the_new_fields_deterministically() -> None:
    factory = AgentRuntimeEventFactory()
    event = factory.create_event(
        "message.received",
        {"request_id": "req-1"},
        producer="cmm.orchestration",
        aggregate_id="req-1",
    )

    restored = factory.from_dict(factory.to_dict(event))

    assert restored.header.producer == "cmm.orchestration"
    assert restored.header.aggregate_id == "req-1"
    assert factory.to_dict(restored) == factory.to_dict(event)


def test_old_serialized_event_without_new_fields_still_deserializes() -> None:
    factory = AgentRuntimeEventFactory()
    legacy = {
        "header": {
            "event_id": "evt_legacy",
            "event_type": "goal.created",
            "schema_version": "1.0.0",
            "occurred_at": "2024-01-01T12:00:00+00:00",
            "emitted_at": "2024-01-01T12:00:00+00:00",
            "agent_id": None,
            "agent_run_id": None,
            "goal_id": "g1",
            "workflow_id": None,
            "task_id": None,
            "iteration_id": None,
            "correlation_id": "corr-1",
            "causation_id": None,
            "actor_id": None,
            "source": "agent_runtime",
            "sensitivity": "internal",
            "permissions": [],
            "metadata": {},
        },
        "payload": {"data": {"goal_id": "g1"}, "raw": None},
    }

    event = factory.from_dict(legacy)

    assert event.header.event_id == "evt_legacy"
    assert event.header.producer is None
    assert event.header.aggregate_id is None


def test_unsupported_schema_version_fails_closed_on_deserialization() -> None:
    factory = AgentRuntimeEventFactory()

    with pytest.raises(ValueError):
        factory.from_dict(
            {
                "header": {
                    "event_id": "evt_1",
                    "event_type": "goal.created",
                    "schema_version": "9.9.9",
                    "occurred_at": "2024-01-01T12:00:00+00:00",
                    "emitted_at": "2024-01-01T12:00:00+00:00",
                },
                "payload": {"data": {}},
            }
        )


def test_fingerprint_includes_identity_relevant_fields_and_is_deterministic() -> None:
    factory = AgentRuntimeEventFactory()
    occurred = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    base = factory.create_event(
        "message.received",
        {"request_id": "req-1"},
        event_id="evt_x",
        occurred_at=occurred,
        emitted_at=occurred,
        producer="cmm.orchestration",
    )
    same = factory.create_event(
        "message.received",
        {"request_id": "req-1"},
        event_id="evt_x",
        occurred_at=occurred,
        emitted_at=occurred,
        producer="cmm.orchestration",
    )
    different_producer = factory.create_event(
        "message.received",
        {"request_id": "req-1"},
        event_id="evt_x",
        occurred_at=occurred,
        emitted_at=occurred,
        producer="cmm.other",
    )
    different_payload = factory.create_event(
        "message.received",
        {"request_id": "req-2"},
        event_id="evt_x",
        occurred_at=occurred,
        emitted_at=occurred,
        producer="cmm.orchestration",
    )

    assert event_fingerprint(base) == event_fingerprint(same)
    assert event_fingerprint(base) != event_fingerprint(different_producer)
    assert event_fingerprint(base) != event_fingerprint(different_payload)


def test_fingerprint_rejects_a_non_event() -> None:
    with pytest.raises(TypeError):
        event_fingerprint("not an event")  # type: ignore[arg-type]


def test_normalizer_preserves_new_fields_and_correlation_semantics() -> None:
    factory = AgentRuntimeEventFactory()
    normalizer = AgentRuntimeEventNormalizer(factory)
    event = factory.create_event(
        "message.received",
        {"request_id": "req-1"},
        causation_id="cause-1",
        producer="cmm.orchestration",
        aggregate_id="req-1",
    )

    normalized = normalizer.normalize(event)

    assert normalized.header.producer == "cmm.orchestration"
    assert normalized.header.aggregate_id == "req-1"
    # existing canonical rule: causation implies correlation when absent
    assert normalized.header.correlation_id == "cause-1"
    assert normalized.header.causation_id == "cause-1"


def test_sensitivity_is_preserved_through_round_trip() -> None:
    from cmm.agent_runtime.runtime_event_contracts import EventSensitivity

    factory = AgentRuntimeEventFactory()
    event = factory.create_event(
        "message.received",
        {"request_id": "req-1"},
        sensitivity=EventSensitivity.CONFIDENTIAL,
    )

    restored = factory.from_dict(factory.to_dict(event))

    assert restored.header.sensitivity is EventSensitivity.CONFIDENTIAL


# ── Replay opt-in subscription contract ──────────────────────────────────────


def test_subscription_replay_opt_in_defaults_to_false() -> None:
    subscription = AgentRuntimeEventSubscription(
        id="sub_1", handler_name="sub_1", event_types=["goal.created"]
    )

    assert subscription.accept_replay is False


def test_subscription_replay_opt_in_is_backward_compatible_and_typed() -> None:
    subscription = AgentRuntimeEventSubscription(
        id="sub_1",
        handler_name="sub_1",
        event_types=["goal.created"],
        accept_replay=True,
    )

    assert subscription.accept_replay is True

    with pytest.raises(TypeError):
        AgentRuntimeEventSubscription(
            id="sub_1",
            handler_name="sub_1",
            event_types=["goal.created"],
            accept_replay="yes",  # type: ignore[arg-type]
        )


def test_payload_contract_is_unchanged() -> None:
    payload = AgentRuntimeEventPayload(data={"request_id": "req-1"})
    event = AgentRuntimeEvent(
        header=AgentRuntimeEventHeader(event_id="evt_1", event_type="message.received"),
        payload=payload,
    )

    assert event.payload.data == {"request_id": "req-1"}
    assert event.payload.raw is None
