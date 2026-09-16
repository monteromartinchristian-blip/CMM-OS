"""Phase 11.2 — safe orchestration event sink tests.

The sink is an adapter seam, not an Event Bus.  These tests freeze the allowed
lifecycle event names, the payload safety boundary and the deterministic
recording adapter.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from cmm.orchestration.events import (
    ALLOWED_EVENT_TYPES,
    OrchestrationEventSink,
    RecordingOrchestrationEventSink,
    validate_orchestration_event,
)

EVENTS_MODULE = (
    Path(__file__).resolve().parents[2] / "cmm" / "orchestration" / "events.py"
)

FROZEN_EVENT_TYPES = (
    "orchestration.request_received",
    "orchestration.intent_resolved",
    "orchestration.domain_resolved",
    "orchestration.route_selected",
    "orchestration.approval_required",
    "orchestration.blocked",
    "orchestration.escalated",
    "orchestration.routed",
    "orchestration.failed",
)


# ── Frozen event names ───────────────────────────────────────────────────────


def test_allowed_event_types_are_frozen() -> None:
    assert set(ALLOWED_EVENT_TYPES) == set(FROZEN_EVENT_TYPES)


def test_unknown_event_type_fails_closed() -> None:
    sink = RecordingOrchestrationEventSink()

    with pytest.raises(ValueError):
        sink.emit("orchestration.something_else", request_id="request-1", payload={})


def test_sink_satisfies_its_protocol() -> None:
    assert isinstance(RecordingOrchestrationEventSink(), OrchestrationEventSink)


# ── Payload safety ───────────────────────────────────────────────────────────


def test_validate_accepts_safe_categorical_facts() -> None:
    payload = validate_orchestration_event(
        "orchestration.routed",
        {
            "intent": "question",
            "route": "direct_response",
            "primary_domain": "domain:health",
            "supporting_domains": ["domain:university"],
            "reason_codes": ["ORCHESTRATION_ROUTED"],
        },
    )

    assert payload["route"] == "direct_response"
    assert payload["supporting_domains"] == ("domain:university",)


@pytest.mark.parametrize(
    "key",
    [
        "prompt",
        "reasoning",
        "chain_of_thought",
        "credentials",
        "credential",
        "secret",
        "provider_payload",
        "raw_context",
        "hidden_reasoning",
        "raw_reasoning",
        "api_key",
        "authorization",
        "traceback",
    ],
)
def test_payload_rejects_unsafe_keys(key: str) -> None:
    sink = RecordingOrchestrationEventSink()

    with pytest.raises(ValueError):
        sink.emit(
            "orchestration.request_received",
            request_id="request-1",
            payload={key: "value"},
        )


def test_payload_rejects_a_nested_unsafe_key() -> None:
    with pytest.raises(ValueError):
        validate_orchestration_event(
            "orchestration.routed",
            {"nested": {"provider_payload": {"raw": "..."}}},
        )


def test_payload_rejects_an_opaque_runtime_object() -> None:
    with pytest.raises(TypeError):
        validate_orchestration_event("orchestration.routed", {"client": object()})


def test_payload_rejects_binary_content() -> None:
    with pytest.raises(TypeError):
        validate_orchestration_event("orchestration.routed", {"blob": b"bytes"})


def test_payload_rejects_a_non_mapping() -> None:
    with pytest.raises(TypeError):
        validate_orchestration_event("orchestration.routed", ["route"])  # type: ignore[arg-type]


def test_payload_rejects_non_string_keys() -> None:
    with pytest.raises(TypeError):
        validate_orchestration_event("orchestration.routed", {1: "route"})


def test_emit_requires_a_request_identifier() -> None:
    sink = RecordingOrchestrationEventSink()

    with pytest.raises(ValueError):
        sink.emit("orchestration.routed", request_id="  ", payload={})


# ── Deterministic recording adapter ──────────────────────────────────────────


def test_recording_sink_preserves_deterministic_order() -> None:
    sink = RecordingOrchestrationEventSink()

    sink.emit("orchestration.request_received", request_id="request-1", payload={})
    sink.emit(
        "orchestration.intent_resolved",
        request_id="request-1",
        payload={"intent": "question"},
    )
    sink.emit("orchestration.routed", request_id="request-1", payload={})

    assert [event.event_type for event in sink.events()] == [
        "orchestration.request_received",
        "orchestration.intent_resolved",
        "orchestration.routed",
    ]
    assert [event.sequence for event in sink.events()] == [0, 1, 2]


def test_recording_sink_returns_a_deterministic_event_reference() -> None:
    first = RecordingOrchestrationEventSink()
    second = RecordingOrchestrationEventSink()

    reference = first.emit("orchestration.routed", request_id="request-1", payload={})

    assert reference == "orchestration.routed:request-1:0"
    assert reference == second.emit(
        "orchestration.routed", request_id="request-1", payload={}
    )
    assert (
        first.emit("orchestration.routed", request_id="request-1", payload={})
        == "orchestration.routed:request-1:1"
    )


def test_recorded_payloads_are_immutable_and_detached() -> None:
    sink = RecordingOrchestrationEventSink()
    payload = {"reason_codes": ["ORCHESTRATION_ROUTED"]}

    sink.emit("orchestration.routed", request_id="request-1", payload=payload)
    payload["reason_codes"].append("MUTATED")

    recorded = sink.events()[0]
    assert recorded.payload["reason_codes"] == ("ORCHESTRATION_ROUTED",)
    with pytest.raises(TypeError):
        recorded.payload["reason_codes"] = ()  # type: ignore[index]


def test_recording_sink_events_are_a_copy_safe_tuple() -> None:
    sink = RecordingOrchestrationEventSink()
    sink.emit("orchestration.routed", request_id="request-1", payload={})

    first = sink.events()
    second = sink.events()

    assert isinstance(first, tuple)
    assert first == second
    assert first is not second


def test_recorded_events_serialize_without_forbidden_content() -> None:
    sink = RecordingOrchestrationEventSink()
    sink.emit(
        "orchestration.routed",
        request_id="request-1",
        payload={"intent": "question", "reason_codes": ["ORCHESTRATION_ROUTED"]},
    )

    serialized = json.dumps(sink.events()[0].to_dict(), sort_keys=True)

    for forbidden in (
        "chain_of_thought",
        "hidden_reasoning",
        "raw_reasoning",
        "prompt",
        "provider_payload",
        "credential",
        "secret",
    ):
        assert forbidden not in serialized
    assert json.loads(serialized)["request_id"] == "request-1"


def test_recording_sink_is_not_an_event_bus() -> None:
    sink = RecordingOrchestrationEventSink()

    for forbidden in (
        "subscribe",
        "unsubscribe",
        "register_handler",
        "publish",
        "replay",
        "handlers",
    ):
        assert not hasattr(sink, forbidden), f"event sink must not expose {forbidden}"


def test_events_module_defines_no_event_bus_owner() -> None:
    tree = ast.parse(EVENTS_MODULE.read_text())

    offenders = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and any(
            token in node.name
            for token in ("EventBus", "EventRegistry", "EventBroker", "EventDispatcher")
        )
    ]

    assert not offenders, f"event sink must not define an event bus: {offenders}"


def test_events_module_performs_no_persistence() -> None:
    tree = ast.parse(EVENTS_MODULE.read_text())

    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    for forbidden in ("json", "sqlite3", "pathlib", "os", "pickle", "tempfile"):
        assert forbidden not in imported, (
            f"event sink must not persist events through {forbidden!r}"
        )
