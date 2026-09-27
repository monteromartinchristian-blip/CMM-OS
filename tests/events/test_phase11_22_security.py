"""Phase 11.22 — security and privacy invariants.

Events are lifecycle facts, not content mirrors.  These tests make the Phase 11.22
security invariants executable and prove that every rejection happens **before**
durable persistence, so unsafe content can never be stored and later redacted.

The governed invariants::

    EVENTS_GRANT_NO_AUTHORITY
    REPLAY_GRANTS_NO_AUTHORITY
    HIDDEN_REASONING_NEVER_PERSISTED
    RAW_PROVIDER_PAYLOAD_NEVER_PERSISTED
    CREDENTIALS_NEVER_PERSISTED
    TOKENS_NEVER_PERSISTED
    UNKNOWN_EVENT_TYPES_FAIL_ACCORDING_TO_CANONICAL_REGISTRY
    CORRUPT_PERSISTED_EVENTS_FAIL_CLOSED
    SAME_ID_DIFFERENT_CONTENT_FAILS_CLOSED
    REPLAY_TO_SIDE_EFFECT_SUBSCRIBERS_DEFAULT_DENIED
    DLQ_REPLAY_CANNOT_BYPASS_SUBSCRIBER_POLICY
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.agent_runtime.runtime_event_contracts import AgentRuntimeEvent
from cmm.agent_runtime.runtime_event_errors import (
    AgentRuntimeEventIdentityConflictError,
    AgentRuntimeEventPersistenceCorruptionError,
)
from cmm.agent_runtime.runtime_event_repository import (
    FileAgentRuntimeEventRepository,
)
from cmm.events.event_payload_safety import (
    ALLOWED_PAYLOAD_KEYS,
    FORBIDDEN_PAYLOAD_KEYS,
    PlatformEventPayloadError,
    freeze_platform_payload,
    is_forbidden_platform_payload_key,
)
from tests.events.test_phase11_22_event_system import build_system

OCCURRED = datetime(2026, 9, 26, 12, 0, 0, tzinfo=timezone.utc)

#: Forbidden key names the design explicitly rejects.
FORBIDDEN_KEYS = (
    "prompt",
    "prompts",
    "system_prompt",
    "developer_prompt",
    "chain_of_thought",
    "hidden_reasoning",
    "raw_reasoning",
    "reasoning",
    "provider_payload",
    "provider_request",
    "provider_response",
    "raw_context",
    "raw_payload",
    "raw_request",
    "request_text",
    "user_text",
    "secret",
    "secrets",
    "credential",
    "credentials",
    "password",
    "passwd",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "auth_header",
    "cookie",
    "cookies",
    "traceback",
    "stack_trace",
)

#: Credential-shaped *values* that must be rejected even under an allowed key.
FORBIDDEN_VALUES = (
    "Bearer abcdefghijklmnopqrstuvwxyz0123456",
    "api_key=abcdef1234567890",
    "password=hunter2hunter2",
    "-----BEGIN RSA PRIVATE KEY-----",
    "authorization: Bearer xyz",
)


def _system():
    return build_system()


# ── Structural rejection ─────────────────────────────────────────────────────


@pytest.mark.parametrize("key", FORBIDDEN_KEYS)
def test_forbidden_payload_keys_fail_closed(key: str) -> None:
    with pytest.raises(PlatformEventPayloadError):
        freeze_platform_payload({key: "value"})


@pytest.mark.parametrize("key", FORBIDDEN_KEYS)
def test_forbidden_key_detection_is_case_and_separator_insensitive(key: str) -> None:
    variants = (key.upper(), key.replace("_", "-"), f" {key} ")

    for variant in variants:
        assert is_forbidden_platform_payload_key(variant), variant


def test_forbidden_key_rule_is_the_documented_vocabulary() -> None:
    assert FORBIDDEN_PAYLOAD_KEYS
    assert "prompt" in FORBIDDEN_PAYLOAD_KEYS
    assert "hidden_reasoning" in FORBIDDEN_PAYLOAD_KEYS
    assert "provider_request" in FORBIDDEN_PAYLOAD_KEYS


@pytest.mark.parametrize("value", FORBIDDEN_VALUES)
def test_credential_shaped_values_fail_closed_under_an_allowed_key(value: str) -> None:
    with pytest.raises(PlatformEventPayloadError):
        freeze_platform_payload({"request_id": value})


def test_an_unrecognised_key_fails_closed_rather_than_being_trusted() -> None:
    with pytest.raises(PlatformEventPayloadError):
        freeze_platform_payload({"some_new_field": "value"})


def test_keys_outside_the_vocabulary_are_rejected_recursively() -> None:
    with pytest.raises(PlatformEventPayloadError):
        freeze_platform_payload({"supporting_domains": [{"prompt": "x"}]})


def test_binary_and_opaque_values_fail_closed() -> None:
    for value in (b"\x00\x01", bytearray(b"ab"), object(), lambda: None):
        with pytest.raises(PlatformEventPayloadError):
            freeze_platform_payload({"request_id": value})


def test_non_finite_floats_fail_closed() -> None:
    for value in (float("inf"), float("-inf"), float("nan")):
        with pytest.raises(PlatformEventPayloadError):
            freeze_platform_payload({"duration_ms": value})


def test_payload_must_be_a_mapping() -> None:
    with pytest.raises(PlatformEventPayloadError):
        freeze_platform_payload(["not", "a", "mapping"])


def test_allowed_vocabulary_is_references_and_bounded_facts_only() -> None:
    """The vocabulary contains no content-bearing key."""

    for key in ALLOWED_PAYLOAD_KEYS:
        assert not is_forbidden_platform_payload_key(key), key
        assert key.lower() == key


# ── Rejection happens before persistence ─────────────────────────────────────


@pytest.mark.parametrize("key", FORBIDDEN_KEYS)
def test_rejection_happens_before_durable_persistence(key: str) -> None:
    system = _system()
    before_count = system.repository.count()
    before_published = system.bus.stats.published_total

    with pytest.raises(PlatformEventPayloadError):
        system.publish("message.received", {key: "unsafe"})

    assert system.repository.count() == before_count
    assert system.bus.stats.published_total == before_published


def test_durable_store_never_receives_an_unsafe_record(tmp_path) -> None:
    system = build_system(
        repository=FileAgentRuntimeEventRepository(tmp_path / "events.jsonl")
    )

    with pytest.raises(PlatformEventPayloadError):
        system.publish("message.received", {"prompt": "leak"})

    assert system.repository.count() == 0
    assert not (tmp_path / "events.jsonl").exists()


def test_no_unsafe_content_reaches_a_subscriber() -> None:
    system = _system()
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"])

    with pytest.raises(PlatformEventPayloadError):
        system.publish("message.received", {"prompt": "leak"})

    assert received == []


# ── Authority invariants ─────────────────────────────────────────────────────


def test_events_grant_no_authority() -> None:
    system = _system()
    result = system.publish(
        "message.received",
        {"request_id": "req-1"},
        event_id="evt-authority",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )

    assert result.event.header.permissions == []
    assert result.event.header.sensitivity.value == "internal"


def test_an_event_cannot_select_a_model_provider_or_domain() -> None:
    """Event metadata cannot carry an authority-selecting field."""

    with pytest.raises(PlatformEventPayloadError):
        freeze_platform_payload({"model_id": "gpt-x"})
    with pytest.raises(PlatformEventPayloadError):
        freeze_platform_payload({"provider_id": "openai"})


def test_replay_grants_no_authority() -> None:
    from cmm.agent_runtime.runtime_event_contracts import (
        AgentRuntimeEventReplayRequest,
    )

    system = _system()
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["message.received"], accept_replay=True)
    system.publish(
        "message.received",
        {"request_id": "req-replay"},
        event_id="evt-replay-authority",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )
    received.clear()

    system.replay(AgentRuntimeEventReplayRequest(event_id="evt-replay-authority"))

    assert received[0].header.permissions == []


def test_replay_to_side_effect_subscribers_is_default_denied() -> None:
    from cmm.agent_runtime.runtime_event_contracts import (
        AgentRuntimeEventReplayRequest,
    )

    system = _system()
    side_effects: list[AgentRuntimeEvent] = []
    system.subscribe(side_effects.append, ["message.received"])
    system.publish(
        "message.received",
        {"request_id": "req-default-deny"},
        event_id="evt-default-deny",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )
    side_effects.clear()

    system.replay(AgentRuntimeEventReplayRequest(event_id="evt-default-deny"))

    assert side_effects == []


def test_dead_letter_replay_cannot_bypass_subscriber_policy() -> None:
    system = build_system(max_delivery_attempts=2)

    def failing(event: AgentRuntimeEvent) -> None:
        raise RuntimeError("boom")

    system.subscribe(failing, ["message.received"])  # no replay opt-in
    system.publish(
        "message.received",
        {"request_id": "req-dlq-policy"},
        event_id="evt-dlq-policy",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )
    assert system.dead_letter_count() == 1

    result = system.replay_dead_letter(0)

    # Nothing was replayed, so the entry must remain unresolved.
    assert result.replayed_count == 0
    assert system.dead_letter_count() == 1


def test_unknown_event_types_fail_according_to_the_canonical_registry() -> None:
    system = _system()

    with pytest.raises(ValueError):
        system.publish("not.a.real.event", {"request_id": "req-1"})


def test_tolerant_registry_mode_still_refuses_an_unknown_type_at_the_factory() -> None:
    """Even a tolerant registry cannot create an unregistered event type."""

    from cmm.agent_runtime.runtime_event_factory import AgentRuntimeEventFactory

    with pytest.raises(ValueError):
        AgentRuntimeEventFactory().create_event("not.a.real.event", {})


# ── Persistence failure invariants ───────────────────────────────────────────


def test_same_id_different_content_fails_closed_and_mutates_nothing(tmp_path) -> None:
    repository = FileAgentRuntimeEventRepository(tmp_path / "events.jsonl")
    system = build_system(repository=repository)
    system.publish(
        "message.received",
        {"request_id": "req-a"},
        event_id="evt-conflict",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )

    with pytest.raises(AgentRuntimeEventIdentityConflictError):
        system.publish(
            "message.received",
            {"request_id": "req-b"},
            event_id="evt-conflict",
            occurred_at=OCCURRED,
            emitted_at=OCCURRED,
        )

    assert repository.count() == 1
    assert repository.get("evt-conflict").payload.data == {"request_id": "req-a"}


def test_corrupt_persisted_events_fail_closed(tmp_path) -> None:
    store = tmp_path / "events.jsonl"
    repository = FileAgentRuntimeEventRepository(store)
    system = build_system(repository=repository)
    system.publish(
        "message.received",
        {"request_id": "req-corrupt"},
        event_id="evt-corrupt",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )

    store.write_text(store.read_text() + "{not json\n")

    with pytest.raises(AgentRuntimeEventPersistenceCorruptionError):
        FileAgentRuntimeEventRepository(store)


def test_dlq_never_stores_secret_or_reasoning_content() -> None:
    system = build_system(max_delivery_attempts=2)
    secret = "super-secret-credential-value"

    def failing(event: AgentRuntimeEvent) -> None:
        raise RuntimeError(f"failed because {secret}")

    system.subscribe(failing, ["message.received"])
    system.publish(
        "message.received",
        {"request_id": "req-dlq-failure"},
        event_id="evt-dlq-failure",
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
    )

    entry = system.list_dead_letters()[0]
    rendered = f"{entry.error}|{entry.error_type}|{dict(entry.metadata)}"

    assert secret not in rendered
    assert "Traceback" not in rendered
    assert entry.error_type == "RuntimeError"


def test_privacy_vocabulary_is_reused_not_reinvented() -> None:
    """The safety gate composes the closed-phase vocabulary."""

    import cmm.events.event_payload_safety as safety

    source = safety.__file__
    with open(source, encoding="utf-8") as handle:
        text = handle.read()

    assert "cmm.domains.credential_policy" in text
    assert "cmm.domains.event_contracts" in text


def test_frozen_payload_is_recursively_immutable() -> None:
    frozen = freeze_platform_payload(
        {"supporting_domains": ["domain:general"], "status": "ok"}
    )

    with pytest.raises(TypeError):
        frozen["status"] = "changed"  # type: ignore[index]
    with pytest.raises(TypeError):
        frozen["supporting_domains"][0] = "changed"  # type: ignore[index]


# ══════════════════════════════════════════════════════════════════════════
# Remediation V1 — the boundary is universal, not route-dependent
#
# The independent audit V1 proved that ``EventSystem.publish()`` was safe while
# the public ``publish_event()`` route could persist forbidden content.  These
# tests make the universal claims permanent for **every** public publication
# route, so safety can never again depend on the caller choosing a safe method.
# ══════════════════════════════════════════════════════════════════════════

UNSAFE_ROUTE_CASES = (
    ("unknown_event_type", "unknown.event.type", {"request_id": "req-1"}),
    ("prompt", "goal.created", {"prompt": "TOP SECRET"}),
    ("system_prompt", "goal.created", {"system_prompt": "you are"}),
    ("developer_prompt", "goal.created", {"developer_prompt": "you must"}),
    ("chain_of_thought", "goal.created", {"chain_of_thought": "step 1"}),
    ("hidden_reasoning", "goal.created", {"hidden_reasoning": "because"}),
    ("provider_request", "goal.created", {"provider_request": {"model": "x"}}),
    ("provider_response", "goal.created", {"provider_response": "text"}),
    ("api_key", "goal.created", {"api_key": "abcdef1234567890"}),
    ("password", "goal.created", {"password": "hunter2"}),
    ("credential_value", "goal.created", {"goal_id": "Bearer abcdefghijklmnop012"}),
    ("opaque_value", "goal.created", {"goal_id": object()}),
    ("binary_value", "goal.created", {"goal_id": b"\x00\x01"}),
)


@pytest.mark.parametrize(
    ("label", "event_type", "payload"),
    UNSAFE_ROUTE_CASES,
    ids=[case[0] for case in UNSAFE_ROUTE_CASES],
)
def test_every_public_publication_route_fails_closed(
    label: str, event_type: str, payload: dict
) -> None:
    """PROMPTS/REASONING/CREDENTIALS/RAW/OPAQUE never reach persistence on any route."""

    from cmm.events.event_system import EventSystem  # noqa: F401  (route surface)

    for route in ("publish", "publish_event"):
        system = _system()
        received: list[AgentRuntimeEvent] = []
        system.subscribe(received.append, ["goal.created"])
        before_published = system.bus.stats.published_total

        with pytest.raises((ValueError, PlatformEventPayloadError)):
            if route == "publish":
                system.publish(event_type, payload)
            else:
                system.publish_event(manual_runtime_event(event_type, payload))

        assert system.repository.count() == 0, (label, route)
        assert system.bus.stats.published_total == before_published, (label, route)
        assert received == [], (label, route)
        assert system.dead_letter_count() == 0, (label, route)


def test_raw_payload_content_never_reaches_persistence_on_any_route() -> None:
    """RAW_PROVIDER_PAYLOADS_NEVER_REACH_PLATFORM_PERSISTENCE."""

    system = _system()

    with pytest.raises(PlatformEventPayloadError):
        system.publish_event(
            manual_runtime_event(
                "goal.created", {"goal_id": "g1"}, raw="raw provider request body"
            )
        )

    assert system.repository.count() == 0


def test_events_and_replay_grant_no_authority_on_the_direct_route() -> None:
    """EVENTS_GRANT_NO_AUTHORITY / REPLAY_GRANTS_NO_AUTHORITY stay universal."""

    from cmm.agent_runtime.runtime_event_contracts import (
        AgentRuntimeEventReplayRequest,
    )

    system = _system()
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["goal.created"], accept_replay=True)

    result = system.publish_event(
        manual_runtime_event(
            "goal.created",
            {"goal_id": "g1"},
            event_id="evt-direct-authority",
            permissions=["not-a-real-grant"],
            metadata={"label": "model-selection"},
        )
    )

    assert result.persisted is True
    stored = system.repository.get("evt-direct-authority")
    assert stored is not None
    # Event metadata carries facts; it never becomes an executable grant.
    assert stored.header.metadata == {"label": "model-selection"}
    received.clear()

    system.replay(AgentRuntimeEventReplayRequest(event_id="evt-direct-authority"))

    assert [event.header.event_id for event in received] == ["evt-direct-authority"]
    assert received[0].header.permissions == ["not-a-real-grant"]


def manual_runtime_event(
    event_type: str,
    payload: dict,
    *,
    event_id: str = "evt-boundary",
    raw: str | None = None,
    **header_facts,
) -> AgentRuntimeEvent:
    """Build a canonical event object directly, bypassing the safe factory path."""

    from cmm.agent_runtime.runtime_event_contracts import (
        AgentRuntimeEventHeader,
        AgentRuntimeEventPayload,
    )

    header = AgentRuntimeEventHeader(
        event_id=event_id,
        event_type=event_type,
        occurred_at=OCCURRED,
        emitted_at=OCCURRED,
        **header_facts,
    )
    return AgentRuntimeEvent(
        header=header, payload=AgentRuntimeEventPayload(data=payload, raw=raw)
    )


# ══════════════════════════════════════════════════════════════════════════
# Remediation V2 — every persisted canonical event field is governed
#
# The independent Re-audit V2 proved that the V1 boundary covered
# ``payload.data`` while persisted *header* channels stayed ungoverned.  These
# tests make the universal claims permanent for **every** persisted field of the
# canonical event, so forbidden material can never be relocated from the payload
# into a header channel to bypass the boundary.
#
# Governed invariants::
#
#     PROMPTS_NEVER_ENTER_ANY_PERSISTED_EVENT_FIELD
#     HIDDEN_REASONING_NEVER_ENTERS_ANY_PERSISTED_EVENT_FIELD
#     CREDENTIALS_NEVER_ENTER_ANY_PERSISTED_EVENT_FIELD
#     RAW_PROVIDER_PAYLOADS_NEVER_ENTER_ANY_PERSISTED_EVENT_FIELD
#     OPAQUE_VALUES_NEVER_ENTER_PERSISTED_PAYLOAD
#     SOURCE_SENSITIVITY_IS_NOT_DOWNGRADED
# ══════════════════════════════════════════════════════════════════════════

#: Forbidden content in the various shapes a caller might try to smuggle it.
V2_FORBIDDEN_CONTENT = (
    ("prompt_text", "system_prompt=TOP SECRET"),
    ("prompt_word", "TOP SECRET prompt"),
    ("reasoning", "hidden reasoning about the user"),
    ("credential", "api_key=abcdef1234567890"),
    ("prefixed_key", "sk-abcdefghijklmnop"),
    ("bearer", "Bearer abcdefghijklmnopqrstuvwxyz0123456"),
    ("provider_raw", 'provider_response={"raw":"body"}'),
)

#: A setter for every producer-controlled persisted header channel plus the
#: payload channel, so no channel is left ungoverned.
V2_HEADER_CHANNELS = (
    ("metadata_value", lambda text: {"metadata": {"note": text}}),
    ("metadata_key", lambda text: {"metadata": {text: "value"}}),
    ("metadata_nested", lambda text: {"metadata": {"nested": {text: "value"}}}),
    ("permissions", lambda text: {"permissions": [text]}),
    ("producer", lambda text: {"producer": text}),
    ("aggregate_id", lambda text: {"aggregate_id": text}),
    ("source", lambda text: {"source": text}),
    ("actor_id", lambda text: {"actor_id": text}),
    ("agent_id", lambda text: {"agent_id": text}),
    ("agent_run_id", lambda text: {"agent_run_id": text}),
    ("goal_id", lambda text: {"goal_id": text}),
    ("workflow_id", lambda text: {"workflow_id": text}),
    ("task_id", lambda text: {"task_id": text}),
    ("iteration_id", lambda text: {"iteration_id": text}),
    ("correlation_id", lambda text: {"correlation_id": text}),
    ("causation_id", lambda text: {"causation_id": text}),
    ("payload_data", lambda text: {"payload": {"goal_id": text}}),
)

V2_CHANNEL_LABELS = tuple(channel[0] for channel in V2_HEADER_CHANNELS)
V2_CONTENT_LABELS = tuple(content[0] for content in V2_FORBIDDEN_CONTENT)


@pytest.mark.parametrize(
    ("channel_label", "setter"),
    V2_HEADER_CHANNELS,
    ids=V2_CHANNEL_LABELS,
)
@pytest.mark.parametrize(
    ("content_label", "text"),
    V2_FORBIDDEN_CONTENT,
    ids=V2_CONTENT_LABELS,
)
def test_no_persisted_event_field_accepts_forbidden_content(
    channel_label, setter, content_label, text
) -> None:
    """No persisted field may carry prompts, reasoning, credentials or raw payloads."""

    system = _system()
    received: list[AgentRuntimeEvent] = []
    system.subscribe(received.append, ["goal.created"])
    before_published = system.bus.stats.published_total

    facts = setter(text)
    payload = facts.pop("payload", {"goal_id": "g1"})

    with pytest.raises((ValueError, PlatformEventPayloadError)):
        system.publish("goal.created", payload, **facts)

    assert system.repository.count() == 0, (channel_label, content_label)
    assert system.bus.stats.published_total == before_published
    assert received == []
    assert system.dead_letter_count() == 0


def test_a_persisted_event_never_serializes_forbidden_content() -> None:
    """Defence in depth: the stored canonical record itself carries no forbidden token."""

    system = _system()
    system.publish(
        "goal.created",
        {"goal_id": "goal-clean", "status": "created"},
        event_id="evt-clean-record",
        producer="orchestration",
        aggregate_id="workflow:123",
        source="domain.execution.completed",
        permissions=["events:read"],
        metadata={"status_code": "ok", "attempt": 1},
    )

    stored = system.repository.get("evt-clean-record")
    assert stored is not None
    serialized = repr(
        {
            "header": {
                "event_id": stored.header.event_id,
                "source": stored.header.source,
                "producer": stored.header.producer,
                "aggregate_id": stored.header.aggregate_id,
                "correlation_id": stored.header.correlation_id,
                "causation_id": stored.header.causation_id,
                "permissions": list(stored.header.permissions),
                "metadata": dict(stored.header.metadata),
            },
            "payload": dict(stored.payload.data),
        }
    ).lower()

    for token in ("prompt", "reasoning", "api_key", "apikey", "bearer", "sk-"):
        assert token not in serialized, token


def test_opaque_values_never_enter_the_persisted_payload() -> None:
    """OPAQUE_VALUES_NEVER_ENTER_PERSISTED_PAYLOAD stays universal."""

    system = _system()

    for opaque in (object(), b"\x00\x01", {1: "non-string key"}, {object(): 1}):
        with pytest.raises(PlatformEventPayloadError):
            system.publish("goal.created", {"goal_id": opaque})

    assert system.repository.count() == 0


def test_source_sensitivity_is_not_downgraded() -> None:
    """SOURCE_SENSITIVITY_IS_NOT_DOWNGRADED at the platform publication boundary."""

    from cmm.agent_runtime.runtime_event_contracts import EventSensitivity

    system = _system()
    for source_sensitivity, expected in (
        ("public", EventSensitivity.PUBLIC),
        ("internal", EventSensitivity.INTERNAL),
        ("confidential", EventSensitivity.CONFIDENTIAL),
        ("restricted", EventSensitivity.RESTRICTED),
    ):
        event_id = f"evt-sensitivity-{source_sensitivity}"
        system.publish(
            "goal.created",
            {"goal_id": "g1"},
            event_id=event_id,
            sensitivity=expected,
        )
        stored = system.repository.get(event_id)
        assert stored is not None
        assert stored.header.sensitivity is expected


def test_unknown_platform_event_type_fails_closed_on_every_route() -> None:
    """UNKNOWN_PLATFORM_EVENT_TYPE_FAILS_CLOSED on creation and both publish routes."""

    system = _system()

    with pytest.raises(ValueError):
        system.create_event("unknown.event.type", {"goal_id": "g1"})
    with pytest.raises(ValueError):
        system.publish("unknown.event.type", {"goal_id": "g1"})
    with pytest.raises(ValueError):
        system.publish_event(
            manual_runtime_event("unknown.event.type", {"goal_id": "g1"})
        )

    assert system.repository.count() == 0
