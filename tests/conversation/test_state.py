"""Phase 11.5 — conversation state persisted inside the canonical shared session.

Task 2 locks the canonical persistence boundary of the conversational
transcript: the conversation extension travels under the namespaced shared
session extension key ``conversation.v1`` and the canonical ``SessionStore``
owned by ``cmm.runtime`` stays the only persistence authority.

These tests prove the required semantics:

- the frozen serialized extension shape round-trips exactly;
- a conversation commit only happens through ``SessionStore.save`` on a
  ``SharedSessionState.with_extension`` copy, advancing the canonical revision
  and appending one canonical change-history entry;
- a missing canonical session fails with the conversation not-found boundary
  error; a stale ``expected_previous_revision`` fails with the conversation
  conflict boundary error and writes nothing;
- a persistence race at ``store.save`` is remapped to the safe conversation
  conflict error without leaking store text and without retrying;
- the committed extension is re-read, and an absent committed extension fails
  closed;
- extension/envelope ``session_id`` mismatch, an unsupported extension
  ``version``, duplicate message IDs, foreign message session IDs and an
  unresolvable ``active_message_id`` all fail closed;
- ``append`` is append-only and returns a new ``ConversationState``; ``message``
  returns the stored message and fails with code ``INVALID_REQUEST`` for an
  unknown ID;
- unrelated extensions (``domain_session``) and the envelope fields are
  preserved across a conversation save;
- ``FileSessionStore`` survives adapter reconstruction (process-style restart);
- the supplied store is the only persistence path (no side storage).

See ``docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md``.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace

import pytest

from cmm.conversation import (
    ConversationBoundaryError,
    ConversationErrorCode,
    ConversationMessage,
    ConversationRole,
    ConversationSessionConflictError,
    ConversationSessionNotFoundError,
)
from cmm.conversation.errors import CONVERSATION_ERROR_MESSAGES
from cmm.conversation.state import (
    CONVERSATION_EXTENSION_KEY,
    CONVERSATION_EXTENSION_VERSION,
    ConversationState,
    SharedSessionConversationAdapter,
)
from cmm.runtime.sessions import (
    FileSessionStore,
    InMemorySessionStore,
    SessionPersistenceError,
    SharedSessionState,
)

TIMESTAMP = "2026-09-17T09:00:00+00:00"

# ── Helpers and store doubles ────────────────────────────────────────────────


def _message(
    message_id: str = "user-001",
    *,
    session_id: str = "session-1",
    role: ConversationRole = ConversationRole.USER,
    content: str = "hello",
    **overrides: object,
) -> ConversationMessage:
    fields: dict[str, object] = {
        "id": message_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": TIMESTAMP,
    }
    fields.update(overrides)
    return ConversationMessage(**fields)  # type: ignore[arg-type]


def _state(**overrides: object) -> ConversationState:
    fields: dict[str, object] = {"session_id": "session-1"}
    fields.update(overrides)
    return ConversationState(**fields)  # type: ignore[arg-type]


class _RacingStore:
    """Test double: a competing writer commits between our read and our commit.

    ``save`` delegates to a real ``InMemorySessionStore``, so the raised
    ``SessionPersistenceError`` is the canonical store's own revision-conflict
    error and the adapter's remap is exercised against it.  ``save_calls``
    proves the adapter does not retry.
    """

    def __init__(self, inner: InMemorySessionStore) -> None:
        self._inner = inner
        self.save_calls = 0

    def load(self, session_id: str) -> SharedSessionState | None:
        return self._inner.load(session_id)

    def save(self, state: SharedSessionState) -> SharedSessionState:
        self.save_calls += 1
        existing = self._inner.load(state.session_id)
        if existing is not None and existing.revision == state.revision:
            self._inner.save(existing)
        return self._inner.save(state)


class _ExtensionDroppingStore:
    """Test double: a commit whose returned envelope lost the extension.

    The inner commit really happens (revision advances), but the returned
    committed state carries no extension, so the adapter must fail closed
    instead of returning a fabricated state.
    """

    def __init__(self, inner: InMemorySessionStore) -> None:
        self._inner = inner

    def load(self, session_id: str) -> SharedSessionState | None:
        return self._inner.load(session_id)

    def save(self, state: SharedSessionState) -> SharedSessionState:
        committed = self._inner.save(state)
        return replace(committed, extensions={})


# ── Boundary errors ──────────────────────────────────────────────────────────


def test_boundary_errors_carry_closed_codes_and_constant_safe_messages() -> None:
    cases = (
        (ConversationBoundaryError, ConversationErrorCode.INVALID_REQUEST),
        (ConversationSessionNotFoundError, ConversationErrorCode.SESSION_NOT_FOUND),
        (ConversationSessionConflictError, ConversationErrorCode.SESSION_CONFLICT),
    )
    for error_type, code in cases:
        error = error_type()
        assert isinstance(error, ConversationBoundaryError)
        assert error.code is code
        assert error.args == (CONVERSATION_ERROR_MESSAGES[code],)
        assert str(error) == CONVERSATION_ERROR_MESSAGES[code]


def test_boundary_errors_never_accept_arbitrary_text() -> None:
    """No store text, revision or path can be attached to a boundary error."""

    leak = "Revision conflict: expected 1 but got 2 for session 'session-1'"
    for error_type in (
        ConversationBoundaryError,
        ConversationSessionNotFoundError,
        ConversationSessionConflictError,
    ):
        with pytest.raises(TypeError):
            error_type(leak)


# ── Frozen serialized extension shape ────────────────────────────────────────


def test_extension_key_and_version_are_frozen() -> None:
    assert CONVERSATION_EXTENSION_KEY == "conversation.v1"
    assert CONVERSATION_EXTENSION_VERSION == 1


def test_state_defaults_and_frozen_instance() -> None:
    state = _state()
    assert state.messages == ()
    assert state.mode == "general"
    assert state.bot_id is None
    assert state.active_message_id is None
    with pytest.raises(FrozenInstanceError):
        state.mode = "other"  # type: ignore[misc]


def test_state_serializes_to_the_frozen_extension_shape() -> None:
    message = _message()
    state = _state(messages=(message,), active_message_id=message.id)
    payload = state.to_dict()
    assert list(payload) == [
        "version",
        "session_id",
        "mode",
        "bot_id",
        "active_message_id",
        "messages",
    ]
    assert payload == {
        "version": 1,
        "session_id": "session-1",
        "mode": "general",
        "bot_id": None,
        "active_message_id": "user-001",
        "messages": [message.to_dict()],
    }


def test_state_round_trips_through_json() -> None:
    state = _state(messages=(_message(),), bot_id="bot-1")
    restored = ConversationState.from_dict(json.loads(json.dumps(state.to_dict())))
    assert restored == state


def test_state_round_trips_rich_message_content() -> None:
    message = ConversationMessage(
        id="user-001",
        session_id="session-1",
        role=ConversationRole.USER,
        content="Hello",
        created_at=TIMESTAMP,
        references=("document://ref-1",),
        metadata={"channel": "web", "nested": {"items": [1, 2]}},
    )
    state = _state(messages=(message,), bot_id="bot-7")
    assert ConversationState.from_dict(state.to_dict()) == state


def test_from_dict_fails_closed_for_an_unsupported_version() -> None:
    payload = _state().to_dict()
    for version in (2, 0, "1", 1.0, True, None):
        with pytest.raises(ValueError):
            ConversationState.from_dict(dict(payload, version=version))
    without_version = {k: v for k, v in payload.items() if k != "version"}
    with pytest.raises(ValueError):
        ConversationState.from_dict(without_version)


def test_from_dict_rejects_unsupported_or_missing_fields() -> None:
    payload = _state().to_dict()
    with pytest.raises(ValueError):
        ConversationState.from_dict(dict(payload, extra=True))
    without_session = {k: v for k, v in payload.items() if k != "session_id"}
    with pytest.raises(ValueError):
        ConversationState.from_dict(without_session)
    with pytest.raises(TypeError):
        ConversationState.from_dict(["not", "a", "mapping"])


def test_state_rejects_blank_session_id_and_blank_mode() -> None:
    with pytest.raises(ValueError):
        _state(session_id="   ")
    with pytest.raises(ValueError):
        _state(mode="  ")


# ── Message integrity inside the state ───────────────────────────────────────


def test_state_rejects_duplicate_message_ids() -> None:
    duplicate = (_message("user-001"), _message("user-001", content="again"))
    with pytest.raises(ValueError):
        _state(messages=duplicate)

    payload = _state(messages=(_message(),)).to_dict()
    payload["messages"].append(_message("user-001", content="again").to_dict())
    with pytest.raises(ValueError):
        ConversationState.from_dict(payload)


def test_state_rejects_messages_from_another_session() -> None:
    foreign = _message("user-001", session_id="session-2")
    with pytest.raises(ValueError):
        _state(messages=(foreign,))

    payload = _state(messages=(_message(),)).to_dict()
    payload["messages"][0]["session_id"] = "session-2"
    with pytest.raises(ValueError):
        ConversationState.from_dict(payload)


def test_state_rejects_an_unresolvable_active_message_id() -> None:
    with pytest.raises(ValueError):
        _state(active_message_id="missing")

    payload = _state(messages=(_message(),)).to_dict()
    payload["active_message_id"] = "missing"
    with pytest.raises(ValueError):
        ConversationState.from_dict(payload)


def test_state_rejects_non_message_items() -> None:
    with pytest.raises(TypeError):
        _state(messages=("not-a-message",))


# ── append / message ─────────────────────────────────────────────────────────


def test_append_is_append_only_and_returns_a_new_state() -> None:
    first = _message("user-001")
    state = _state(messages=(first,), bot_id="bot-1")
    second = _message("assistant-002", role=ConversationRole.ASSISTANT, content="hi")

    appended = state.append(second)

    assert appended is not state
    assert state.messages == (first,)
    assert appended.messages == (first, second)
    assert appended.session_id == state.session_id
    assert appended.mode == state.mode
    assert appended.bot_id == state.bot_id


def test_append_rejects_duplicate_ids_against_existing_and_batch() -> None:
    state = _state(messages=(_message("user-001"),))
    with pytest.raises(ValueError):
        state.append(_message("user-001", content="again"))
    with pytest.raises(ValueError):
        state.append(_message("user-002"), _message("user-002", content="again"))
    assert state.messages == (_message("user-001"),)


def test_append_rejects_a_message_from_another_session() -> None:
    state = _state()
    with pytest.raises(ValueError):
        state.append(_message("user-001", session_id="session-2"))


def test_message_returns_the_stored_message() -> None:
    message = _message()
    state = _state(messages=(message,))
    assert state.message("user-001") is message


def test_message_unknown_id_raises_the_safe_invalid_request_error() -> None:
    state = _state(messages=(_message(),))
    with pytest.raises(ConversationBoundaryError) as excinfo:
        state.message("missing")
    assert excinfo.value.code is ConversationErrorCode.INVALID_REQUEST
    assert (
        str(excinfo.value)
        == CONVERSATION_ERROR_MESSAGES[ConversationErrorCode.INVALID_REQUEST]
    )


# ── Canonical adapter: commit path ───────────────────────────────────────────


def test_conversation_is_stored_under_namespaced_shared_session_extension() -> None:
    store = InMemorySessionStore()
    shared = store.save(SharedSessionState(session_id="session-1"))
    adapter = SharedSessionConversationAdapter(store)
    state = _state()

    saved, committed = adapter.save_conversation(
        state,
        expected_previous_revision=shared.revision,
    )

    assert committed.extensions["conversation.v1"]["session_id"] == "session-1"
    assert committed.extensions["conversation.v1"]["version"] == 1
    assert saved.session_id == "session-1"
    assert adapter.store is store
    durable = store.load("session-1")
    assert durable is not None
    assert durable.extensions["conversation.v1"]["session_id"] == "session-1"


def test_save_returns_the_reread_extension_and_the_committed_state() -> None:
    store = InMemorySessionStore()
    before = store.save(SharedSessionState(session_id="session-1"))
    adapter = SharedSessionConversationAdapter(store)
    message = _message()
    state = _state(messages=(message,), active_message_id=message.id)

    saved, committed = adapter.save_conversation(
        state,
        expected_previous_revision=before.revision,
    )

    assert isinstance(committed, SharedSessionState)
    assert saved == state
    assert saved == ConversationState.from_dict(
        dict(committed.extensions[CONVERSATION_EXTENSION_KEY])
    )
    # Canonical revision and change history advance on the committed envelope.
    assert committed.revision == before.revision + 1
    assert len(committed.change_history) == len(before.change_history) + 1
    assert committed.change_history[-1].from_revision == before.revision
    assert committed.change_history[-1].to_revision == committed.revision
    assert (
        committed.change_history[: len(before.change_history)] == before.change_history
    )
    assert committed.session_id == before.session_id
    assert committed.status == before.status
    assert committed.created_at == before.created_at
    assert store.load("session-1") == committed


def test_save_without_a_canonical_session_raises_not_found_without_writing() -> None:
    store = InMemorySessionStore()
    adapter = SharedSessionConversationAdapter(store)
    state = _state(messages=(_message(),))

    with pytest.raises(ConversationSessionNotFoundError) as excinfo:
        adapter.save_conversation(state, expected_previous_revision=0)

    assert excinfo.value.code is ConversationErrorCode.SESSION_NOT_FOUND
    assert (
        str(excinfo.value)
        == CONVERSATION_ERROR_MESSAGES[ConversationErrorCode.SESSION_NOT_FOUND]
    )
    assert store.load("session-1") is None


def test_stale_expected_revision_conflicts_and_writes_nothing() -> None:
    store = InMemorySessionStore()
    shared = store.save(SharedSessionState(session_id="session-1"))
    adapter = SharedSessionConversationAdapter(store)
    state = _state(messages=(_message(),))

    with pytest.raises(ConversationSessionConflictError) as excinfo:
        adapter.save_conversation(state, expected_previous_revision=shared.revision - 1)

    assert excinfo.value.code is ConversationErrorCode.SESSION_CONFLICT
    assert (
        str(excinfo.value)
        == CONVERSATION_ERROR_MESSAGES[ConversationErrorCode.SESSION_CONFLICT]
    )
    after = store.load("session-1")
    assert after is not None
    assert after.to_dict() == shared.to_dict()
    assert CONVERSATION_EXTENSION_KEY not in after.extensions


def test_canonical_store_race_raises_the_store_error_before_the_remap() -> None:
    """The remapped race is a real canonical revision conflict, not a fake."""

    store = InMemorySessionStore()
    shared = store.save(SharedSessionState(session_id="session-1"))
    payload = _state().to_dict()
    store.save(shared.with_extension(CONVERSATION_EXTENSION_KEY, payload))
    with pytest.raises(SessionPersistenceError):
        store.save(shared.with_extension(CONVERSATION_EXTENSION_KEY, payload))


def test_store_race_is_remapped_to_the_safe_conversation_conflict() -> None:
    store = InMemorySessionStore()
    shared = store.save(SharedSessionState(session_id="session-1"))
    racing = _RacingStore(store)
    adapter = SharedSessionConversationAdapter(racing)
    state = _state(messages=(_message(),))

    with pytest.raises(ConversationSessionConflictError) as excinfo:
        adapter.save_conversation(state, expected_previous_revision=shared.revision)

    error = excinfo.value
    assert error.code is ConversationErrorCode.SESSION_CONFLICT
    assert (
        str(error)
        == CONVERSATION_ERROR_MESSAGES[ConversationErrorCode.SESSION_CONFLICT]
    )
    assert "Revision conflict" not in str(error)
    assert "session-1" not in str(error)
    assert error.__cause__ is None
    assert error.__suppress_context__ is True
    assert racing.save_calls == 1
    durable = store.load("session-1")
    assert durable is not None
    assert durable.revision == shared.revision + 1
    assert CONVERSATION_EXTENSION_KEY not in durable.extensions


def test_a_commit_that_loses_the_extension_fails_closed() -> None:
    store = InMemorySessionStore()
    shared = store.save(SharedSessionState(session_id="session-1"))
    adapter = SharedSessionConversationAdapter(_ExtensionDroppingStore(store))

    with pytest.raises(ConversationSessionConflictError):
        adapter.save_conversation(_state(), expected_previous_revision=shared.revision)


def test_save_rejects_a_non_conversation_state() -> None:
    store = InMemorySessionStore()
    store.save(SharedSessionState(session_id="session-1"))
    adapter = SharedSessionConversationAdapter(store)
    with pytest.raises(TypeError):
        adapter.save_conversation(
            {"session_id": "session-1"}, expected_previous_revision=1
        )


def test_save_rejects_an_invalid_expected_previous_revision() -> None:
    store = InMemorySessionStore()
    store.save(SharedSessionState(session_id="session-1"))
    adapter = SharedSessionConversationAdapter(store)
    for invalid in (True, -1, "1"):
        with pytest.raises(ValueError):
            adapter.save_conversation(_state(), expected_previous_revision=invalid)


# ── Canonical adapter: load path ─────────────────────────────────────────────


def test_load_shared_session_returns_the_raw_canonical_state() -> None:
    store = InMemorySessionStore()
    shared = store.save(SharedSessionState(session_id="session-1"))
    adapter = SharedSessionConversationAdapter(store)
    assert adapter.load_shared_session("session-1") == shared
    assert adapter.load_shared_session("missing") is None


def test_load_conversation_returns_none_without_session_or_extension() -> None:
    store = InMemorySessionStore()
    store.save(SharedSessionState(session_id="session-1"))
    adapter = SharedSessionConversationAdapter(store)
    assert adapter.load_conversation("missing") is None
    assert adapter.load_conversation("session-1") is None


def test_load_conversation_round_trips_the_committed_state() -> None:
    store = InMemorySessionStore()
    shared = store.save(SharedSessionState(session_id="session-1"))
    adapter = SharedSessionConversationAdapter(store)
    message = _message()
    state = _state(messages=(message,), active_message_id=message.id)
    saved, _ = adapter.save_conversation(
        state, expected_previous_revision=shared.revision
    )

    loaded = adapter.load_conversation("session-1")

    assert loaded == state
    assert loaded == saved


def test_extension_session_id_must_equal_the_envelope_session_id() -> None:
    store = InMemorySessionStore()
    payload = ConversationState(session_id="session-2").to_dict()
    store.save(
        SharedSessionState(session_id="session-1").with_extension(
            CONVERSATION_EXTENSION_KEY, payload
        )
    )
    adapter = SharedSessionConversationAdapter(store)
    with pytest.raises(ConversationSessionConflictError):
        adapter.load_conversation("session-1")


def test_unsupported_stored_extension_version_fails_closed_on_load() -> None:
    payload = _state().to_dict()
    payload["version"] = 2
    store = InMemorySessionStore()
    store.save(
        SharedSessionState(session_id="session-1").with_extension(
            CONVERSATION_EXTENSION_KEY, payload
        )
    )
    adapter = SharedSessionConversationAdapter(store)
    with pytest.raises(ConversationSessionConflictError):
        adapter.load_conversation("session-1")


def test_message_session_mismatch_in_a_stored_extension_fails_closed() -> None:
    payload = _state(messages=(_message(),)).to_dict()
    payload["messages"][0]["session_id"] = "session-2"
    store = InMemorySessionStore()
    store.save(
        SharedSessionState(session_id="session-1").with_extension(
            CONVERSATION_EXTENSION_KEY, payload
        )
    )
    adapter = SharedSessionConversationAdapter(store)
    with pytest.raises(ConversationSessionConflictError):
        adapter.load_conversation("session-1")


def test_custom_extension_key_is_honored() -> None:
    store = InMemorySessionStore()
    shared = store.save(SharedSessionState(session_id="session-1"))
    adapter = SharedSessionConversationAdapter(
        store, extension_key="conversation.experimental"
    )

    saved, committed = adapter.save_conversation(
        _state(), expected_previous_revision=shared.revision
    )

    assert "conversation.experimental" in committed.extensions
    assert CONVERSATION_EXTENSION_KEY not in committed.extensions
    assert adapter.load_conversation("session-1") == saved


def test_adapter_requires_a_real_store() -> None:
    with pytest.raises(ValueError):
        SharedSessionConversationAdapter(None)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        SharedSessionConversationAdapter(object())  # type: ignore[arg-type]


# ── Unrelated extension and envelope preservation ────────────────────────────


def test_unrelated_extensions_and_envelope_fields_are_preserved() -> None:
    domain_payload = {
        "session_id": "session-1",
        "primary_domain": "domain:health",
        "active_domains": ["domain:health", "domain:finance"],
        "nested": {"revisions": [1, 2, 3], "flags": {"paused": False}},
    }
    store = InMemorySessionStore()
    shared = store.save(
        SharedSessionState(
            session_id="session-1",
            status="PAUSED",
            extensions={"domain_session": domain_payload},
        )
    )
    before = shared.to_dict()
    adapter = SharedSessionConversationAdapter(store)
    message = _message()
    adapter.save_conversation(
        _state(messages=(message,)),
        expected_previous_revision=shared.revision,
    )

    reloaded = store.load("session-1")
    assert reloaded is not None
    after = reloaded.to_dict()
    assert after["extensions"]["domain_session"] == domain_payload
    assert json.dumps(
        after["extensions"]["domain_session"], sort_keys=True
    ) == json.dumps(before["extensions"]["domain_session"], sort_keys=True)
    assert reloaded.extensions["domain_session"] == shared.extensions["domain_session"]
    assert after["extensions"][CONVERSATION_EXTENSION_KEY]["session_id"] == "session-1"
    assert after["session_id"] == before["session_id"]
    assert after["status"] == before["status"]
    assert after["created_at"] == before["created_at"]
    assert after["revision"] == before["revision"] + 1


# ── FileSessionStore durability across adapter reconstruction ────────────────


def test_file_session_store_survives_adapter_reconstruction(tmp_path) -> None:
    store = FileSessionStore(root=tmp_path)
    shared = store.save(SharedSessionState(session_id="session-1"))
    adapter = SharedSessionConversationAdapter(store)
    first = _message("user-001")
    saved, committed = adapter.save_conversation(
        _state(messages=(first,), active_message_id=first.id),
        expected_previous_revision=shared.revision,
    )

    # Process-style restart: new store and new adapter over the same durable root.
    restarted_store = FileSessionStore(root=tmp_path)
    restarted = SharedSessionConversationAdapter(restarted_store)
    loaded = restarted.load_conversation("session-1")
    assert loaded == saved
    restarted_shared = restarted.load_shared_session("session-1")
    assert restarted_shared is not None
    assert restarted_shared.revision == committed.revision

    # A second turn commits on top of the restored canonical revision.
    second = _message("assistant-002", role=ConversationRole.ASSISTANT, content="hi")
    second_saved, second_committed = restarted.save_conversation(
        loaded.append(second),
        expected_previous_revision=committed.revision,
    )
    assert second_saved.messages == (first, second)
    assert second_committed.revision == committed.revision + 1

    final_store = FileSessionStore(root=tmp_path)
    final = SharedSessionConversationAdapter(final_store).load_conversation("session-1")
    assert final is not None
    assert final.messages == (first, second)
    assert final.active_message_id == first.id

    # Exactly one canonical durable session file; the extension travels inside it.
    files = sorted(tmp_path.glob("*.json"))
    assert [path.name for path in files] == ["session-1.json"]
    raw = json.loads(files[0].read_text(encoding="utf-8"))
    assert raw["revision"] == second_committed.revision
    assert len(raw["change_history"]) == second_committed.revision
    assert (
        raw["extensions"][CONVERSATION_EXTENSION_KEY]["messages"][1]["id"]
        == "assistant-002"
    )


def test_file_session_store_loads_a_missing_session_as_none(tmp_path) -> None:
    adapter = SharedSessionConversationAdapter(FileSessionStore(root=tmp_path))
    assert adapter.load_conversation("missing") is None


# ── No side storage ──────────────────────────────────────────────────────────


def test_the_supplied_store_is_the_only_persistence_path() -> None:
    backing: dict[str, SharedSessionState] = {}
    store = InMemorySessionStore(backing=backing)
    shared = store.save(SharedSessionState(session_id="session-1"))
    adapter = SharedSessionConversationAdapter(store)
    assert adapter.store is store
    assert set(vars(adapter)) == {"_store", "_extension_key"}

    adapter.save_conversation(
        _state(messages=(_message(),)),
        expected_previous_revision=shared.revision,
    )

    # A separate adapter over the same canonical backing sees the committed state.
    other = SharedSessionConversationAdapter(InMemorySessionStore(backing=backing))
    loaded = other.load_conversation("session-1")
    assert loaded is not None
    assert loaded.messages[0].id == "user-001"
