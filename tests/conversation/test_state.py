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
- every canonical store call is remapped: an unreadable/corrupt store (a
  store double and a real corrupt ``FileSessionStore`` entry) fails closed as
  the safe conflict error, on load and on save, with no store text, no session
  id and no cause chain;
- a persistence race at ``store.save`` is remapped to the safe conversation
  conflict error without leaking store text and without retrying;
- a commit that does not advance the canonical revision by exactly one (a
  delete race between the read and the commit) fails closed instead of
  reporting a non-advancing revision as success;
- an envelope whose ``session_id`` disagrees with the committed state fails
  closed before any durable write;
- an absent extension key means "no conversation"; a present stored value that
  is not a valid extension mapping (including a stored JSON ``null``) fails
  closed;
- caller misuse of a session id fails as ``ValueError`` at every store-reaching
  entry point, before any store call and identically for both store types;
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
from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace

import pytest

from cmm.conversation import (
    ConversationBoundaryError,
    ConversationErrorCode,
    ConversationInteractionMode,
    ConversationMessage,
    ConversationRole,
    ConversationSessionConflictError,
    ConversationSessionNotFoundError,
)
from cmm.conversation.contracts import MAX_IDENTIFIER_LENGTH
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
    """Test double: a commit whose *returned* envelope carries no extension.

    The inner commit really happens and is durable (the canonical revision
    advances and the extension key is persisted); only the envelope handed back
    to the adapter has the key stripped.  This double therefore pins fail-closed
    *reporting* only — the adapter must not report a success it cannot verify —
    and does not simulate a durable loss of the extension.
    """

    def __init__(self, inner: InMemorySessionStore) -> None:
        self._inner = inner

    def load(self, session_id: str) -> SharedSessionState | None:
        return self._inner.load(session_id)

    def save(self, state: SharedSessionState) -> SharedSessionState:
        committed = self._inner.save(state)
        return replace(committed, extensions={})


class _CorruptStore:
    """Test double: every canonical call fails like a corrupt store entry.

    The failure text is deliberately leaky (it is the canonical
    ``FileSessionStore`` wording, including the session id): the adapter must
    never let either the text or the id escape the conversational boundary.
    """

    def __init__(self) -> None:
        self.load_calls = 0
        self.save_calls = 0

    def load(self, session_id: str) -> SharedSessionState | None:
        self.load_calls += 1
        raise SessionPersistenceError(
            f"Corrupt shared session store entry for '{session_id}'"
        )

    def save(self, state: SharedSessionState) -> SharedSessionState:
        self.save_calls += 1
        raise SessionPersistenceError(
            f"Corrupt shared session store entry for '{state.session_id}'"
        )


class _ExplodingStore:
    """Test double: a read failure that is not a ``SessionPersistenceError``.

    The brief's ruling is that *any* exception raised by the store fails
    closed; this double pins the non-typed failure (with leaky text) too.
    """

    def __init__(self) -> None:
        self.load_calls = 0

    def load(self, session_id: str) -> SharedSessionState | None:
        self.load_calls += 1
        raise RuntimeError(f"internal store fault at /var/sessions/{session_id}")

    def save(self, state: SharedSessionState) -> SharedSessionState:
        raise AssertionError("save must not be reached")


class _FailingSaveStore:
    """Test double: reads work, the commit fails with leaky store text."""

    def __init__(self, inner: InMemorySessionStore) -> None:
        self._inner = inner
        self.save_calls = 0

    def load(self, session_id: str) -> SharedSessionState | None:
        return self._inner.load(session_id)

    def save(self, state: SharedSessionState) -> SharedSessionState:
        self.save_calls += 1
        raise SessionPersistenceError(
            f"Corrupt shared session store entry for '{state.session_id}'"
        )


class _DeletingStore:
    """Test double: the canonical entry disappears between the read and the commit.

    ``save`` deletes the durable entry (a concurrent canonical delete) and then
    delegates to the inner store, whose canonical ``_commit`` sees
    ``existing=None`` and treats the write as a brand-new session (from
    revision 0).  The adapter must detect that the committed revision did not
    advance by exactly one, fail closed, and neither retry nor undo the durable
    write that already happened.
    """

    def __init__(
        self,
        inner: InMemorySessionStore | FileSessionStore,
        delete: Callable[[str], None],
    ) -> None:
        self._inner = inner
        self._delete = delete
        self.save_calls = 0

    def load(self, session_id: str) -> SharedSessionState | None:
        return self._inner.load(session_id)

    def save(self, state: SharedSessionState) -> SharedSessionState:
        self.save_calls += 1
        self._delete(state.session_id)
        return self._inner.save(state)


class _ForeignEnvelopeStore:
    """Test double: the committed envelope comes back with a foreign session id.

    The durable write is a normal commit; only the returned envelope's
    ``session_id`` is replaced, so this pins the post-commit re-verification
    (defence in depth) rather than the pre-save equality check.
    """

    def __init__(self, inner: InMemorySessionStore) -> None:
        self._inner = inner

    def load(self, session_id: str) -> SharedSessionState | None:
        return self._inner.load(session_id)

    def save(self, state: SharedSessionState) -> SharedSessionState:
        return replace(self._inner.save(state), session_id="other")


class _NeverCalledStore:
    """Test double: any store call at all is a defect in the adapter."""

    def __init__(self) -> None:
        self.calls = 0

    def load(self, session_id: str) -> SharedSessionState | None:
        self.calls += 1
        raise AssertionError("the store must not be reached for caller misuse")

    def save(self, state: SharedSessionState) -> SharedSessionState:
        self.calls += 1
        raise AssertionError("the store must not be reached for caller misuse")


class _UnvalidatedState(ConversationState):
    """Defence-in-depth double: a state that bypassed the frozen validation.

    ``ConversationState`` normalizes and validates ``session_id`` in
    ``__post_init__``; this subclass skips that, so the adapter entry point sees
    exactly the value a caller passed in.
    """

    def __post_init__(self) -> None:
        pass


#: The three adapter entry points that reach the canonical store.
_ENTRY_POINTS = ("load_shared_session", "load_conversation", "save_conversation")

#: Real corrupt-entry documents whose load must never leak store text.
_CORRUPT_DOCUMENTS = (
    "{ this is not a session document",
    '{"session_id": "session-1", "revision": -1}',
)


def _call_entry_point(adapter: SharedSessionConversationAdapter, entry: str) -> object:
    """Call one store-reaching adapter entry point by name."""

    if entry == "save_conversation":
        return adapter.save_conversation(
            _state(messages=(_message(),)), expected_previous_revision=None
        )
    return getattr(adapter, entry)("session-1")


def _assert_safe_conflict(error: BaseException, *forbidden: str) -> None:
    """Assert one failure is the safe conversation conflict and leaks nothing."""

    assert isinstance(error, ConversationSessionConflictError)
    assert error.code is ConversationErrorCode.SESSION_CONFLICT
    expected = CONVERSATION_ERROR_MESSAGES[ConversationErrorCode.SESSION_CONFLICT]
    assert str(error) == expected
    assert error.args == (expected,)
    assert error.__cause__ is None
    assert "Corrupt" not in str(error)
    assert "Corrupt" not in repr(error)
    for text in forbidden:
        assert text not in str(error)
        assert text not in repr(error)


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


def test_state_rejects_blank_session_id() -> None:
    with pytest.raises(ValueError):
        _state(session_id="   ")


# ── Closed interaction modes (remediation MINOR-01) ──────────────────────────


def test_unsupported_interaction_mode_fails_closed() -> None:
    """Remediation MINOR-01: an unknown mode is never accepted.

    The V1 audit reproduced ``totally-unsupported-mode`` being accepted by the
    open ``ConversationState.mode`` string; the closed contract must fail
    closed in the direct constructor and in ``from_dict`` alike.
    """

    with pytest.raises((TypeError, ValueError)):
        _state(mode="totally-unsupported-mode")

    payload = dict(_state().to_dict(), mode="totally-unsupported-mode")
    with pytest.raises(ValueError):
        ConversationState.from_dict(payload)


def test_unsupported_interaction_mode_fails_closed_on_conversation_v1_load() -> None:
    """The canonical ``conversation.v1`` load path fails closed too."""

    store = InMemorySessionStore()
    shared = store.save(SharedSessionState(session_id="session-1"))
    store.save(
        shared.with_extension(
            CONVERSATION_EXTENSION_KEY,
            dict(_state().to_dict(), mode="totally-unsupported-mode"),
        )
    )
    adapter = SharedSessionConversationAdapter(store)

    with pytest.raises(ConversationSessionConflictError):
        adapter.load_conversation("session-1")


def test_conversation_v1_load_rejects_hidden_reasoning_and_prompt_keys() -> None:
    """Remediation MAJOR-03: a stored prompt/reasoning key fails closed on load."""

    store = InMemorySessionStore()
    store.save(SharedSessionState(session_id="session-1"))
    for hidden_key in ("private_reasoning", "rawPrompt", "system_prompt", "prompt"):
        shared = store.load("session-1")
        assert shared is not None
        payload = _state(messages=(_message(),)).to_dict()
        payload["messages"][0]["metadata"] = {hidden_key: "hidden"}
        store.save(shared.with_extension(CONVERSATION_EXTENSION_KEY, payload))
        adapter = SharedSessionConversationAdapter(store)
        with pytest.raises(ConversationSessionConflictError):
            adapter.load_conversation("session-1")


def test_every_canonical_interaction_mode_round_trips_deterministically() -> None:
    """The seven canonical modes serialize as their exact string value."""

    for mode in ConversationInteractionMode:
        state = _state(mode=mode)
        assert state.mode is mode
        assert state.to_dict()["mode"] == mode.value
        restored = ConversationState.from_dict(state.to_dict())
        assert restored == state
        assert restored.mode is mode
        # A JSON round trip (the persisted extension shape) is equally exact.
        assert (
            ConversationState.from_dict(json.loads(json.dumps(state.to_dict()))).mode
            is mode
        )


def test_a_raw_string_interaction_mode_is_never_coerced() -> None:
    """The direct constructor requires the closed member, exactly like ``role``."""

    with pytest.raises(TypeError):
        _state(mode="domain")
    assert _state(mode=ConversationInteractionMode.DOMAIN).mode is (
        ConversationInteractionMode.DOMAIN
    )


def test_from_dict_reads_every_canonical_mode_back_from_its_string_value() -> None:
    for mode in ConversationInteractionMode:
        payload = dict(_state().to_dict(), mode=mode.value)
        assert ConversationState.from_dict(payload).mode is mode
    for value in (None, 1, True, ["general"], {"mode": "general"}):
        with pytest.raises((TypeError, ValueError)):
            ConversationState.from_dict(dict(_state().to_dict(), mode=value))


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
    """A commit whose *returned* envelope cannot be verified fails closed.

    ``_ExtensionDroppingStore`` keeps the durable write and only strips the
    extension from the returned envelope, so this pins fail-closed reporting
    only — durable loss of the extension is not simulated.
    """

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


# ── Store boundary: fail closed on unreadable stores (fix round 1) ───────────


@pytest.mark.parametrize("entry", _ENTRY_POINTS)
def test_a_corrupt_store_double_fails_closed_without_leaking_store_text(
    entry: str,
) -> None:
    """A ``SessionPersistenceError`` read never escapes raw from any entry."""

    adapter = SharedSessionConversationAdapter(_CorruptStore())

    with pytest.raises(ConversationSessionConflictError) as excinfo:
        _call_entry_point(adapter, entry)

    error = excinfo.value
    _assert_safe_conflict(error, "session-1")
    assert error.__suppress_context__ is True


@pytest.mark.parametrize("entry", _ENTRY_POINTS)
def test_a_non_persistence_store_fault_fails_closed_too(entry: str) -> None:
    """Any exception raised by the store is remapped, not just the typed one."""

    adapter = SharedSessionConversationAdapter(_ExplodingStore())

    with pytest.raises(ConversationSessionConflictError) as excinfo:
        _call_entry_point(adapter, entry)

    _assert_safe_conflict(excinfo.value, "session-1", "internal store fault")


@pytest.mark.parametrize("entry", _ENTRY_POINTS)
@pytest.mark.parametrize("document", _CORRUPT_DOCUMENTS)
def test_a_real_corrupt_file_session_store_fails_closed(
    entry: str, document: str, tmp_path
) -> None:
    """A real on-disk corrupt entry never leaks text or id, and never writes."""

    store = FileSessionStore(root=tmp_path)
    corrupt = tmp_path / "session-1.json"
    corrupt.write_text(document, encoding="utf-8")
    adapter = SharedSessionConversationAdapter(store)

    with pytest.raises(ConversationSessionConflictError) as excinfo:
        _call_entry_point(adapter, entry)

    error = excinfo.value
    _assert_safe_conflict(error, "session-1")
    assert error.__suppress_context__ is True
    # None of the read paths writes: the corrupt entry is exactly as found.
    assert [path.name for path in sorted(tmp_path.iterdir())] == ["session-1.json"]
    assert corrupt.read_text(encoding="utf-8") == document


def test_a_failing_commit_fails_closed_without_leaking_store_text_or_retrying() -> None:
    """The store's own commit failure is remapped and never retried."""

    store = InMemorySessionStore()
    shared = store.save(SharedSessionState(session_id="session-1"))
    failing = _FailingSaveStore(store)
    adapter = SharedSessionConversationAdapter(failing)

    with pytest.raises(ConversationSessionConflictError) as excinfo:
        adapter.save_conversation(
            _state(messages=(_message(),)),
            expected_previous_revision=shared.revision,
        )

    error = excinfo.value
    _assert_safe_conflict(error, "session-1")
    assert error.__suppress_context__ is True
    assert failing.save_calls == 1  # the commit is never retried
    durable = store.load("session-1")
    assert durable is not None
    assert durable.to_dict() == shared.to_dict()


# ── Commit must advance the canonical revision by exactly one (fix round 1) ──


@pytest.mark.parametrize("kind", ["memory", "file"])
def test_a_delete_race_between_the_read_and_the_commit_fails_closed(
    kind: str, tmp_path
) -> None:
    """A commit that did not advance the revision is never returned as success."""

    backing: dict[str, SharedSessionState] = {}
    inner: InMemorySessionStore | FileSessionStore
    if kind == "memory":
        inner = InMemorySessionStore(backing=backing)

        def delete(session_id: str) -> None:
            backing.pop(session_id, None)

    else:
        inner = FileSessionStore(root=tmp_path)

        def delete(session_id: str) -> None:
            (tmp_path / f"{session_id}.json").unlink(missing_ok=True)

    shared = inner.save(SharedSessionState(session_id="session-1"))
    adapter = SharedSessionConversationAdapter(inner)
    loaded, committed = adapter.save_conversation(
        _state(messages=(_message(),)), expected_previous_revision=shared.revision
    )
    assert committed.revision == 2

    racing = _DeletingStore(inner, delete)
    racing_adapter = SharedSessionConversationAdapter(racing)
    before = racing_adapter.load_conversation("session-1")
    assert before == loaded
    assert before is not None

    message = _message("assistant-002", role=ConversationRole.ASSISTANT, content="hi")
    with pytest.raises(ConversationSessionConflictError) as excinfo:
        racing_adapter.save_conversation(
            before.append(message), expected_previous_revision=committed.revision
        )

    error = excinfo.value
    _assert_safe_conflict(error, "session-1")
    assert error.__suppress_context__ is False  # raised directly, no store text
    assert racing.save_calls == 1  # no retry, no second write

    durable = inner.load("session-1")
    assert durable is not None
    # The durable write that did happen is the competitor's brand-new session:
    # the deleted entry made the canonical ``_commit`` start over at revision 0.
    # It is reported as a conflict — never returned as success, never undone.
    assert durable.revision == 1
    assert durable.change_history[-1].from_revision == 0
    assert durable.change_history[-1].to_revision == 1


def test_consecutive_commits_advance_the_canonical_revision_one_at_a_time() -> None:
    """The normal path still commits: 8 sequential commits advance revision 1..8."""

    backing: dict[str, SharedSessionState] = {}
    # The canonical entry starts at revision 0 (never committed), so the eight
    # adapter commits below advance the canonical revision 1..8.
    backing["session-1"] = SharedSessionState(session_id="session-1")
    store = InMemorySessionStore(backing=backing)
    adapter = SharedSessionConversationAdapter(store)
    state = _state()
    expected_revision = 0

    for index in range(1, 9):
        state = state.append(_message(f"user-{index:03d}", content=f"turn {index}"))
        saved, committed = adapter.save_conversation(
            state, expected_previous_revision=expected_revision
        )
        assert saved == state
        assert committed.revision == index
        expected_revision = committed.revision

    durable = store.load("session-1")
    assert durable is not None
    assert durable.revision == 8
    assert [
        (change.from_revision, change.to_revision) for change in durable.change_history
    ] == [(index, index + 1) for index in range(8)]
    assert adapter.load_conversation("session-1") == state


def test_save_rejects_a_foreign_envelope_session_id_before_any_write() -> None:
    """A hand-edited envelope id conflicts before the durable write, not after."""

    backing: dict[str, SharedSessionState] = {}
    store = InMemorySessionStore(backing=backing)
    adapter = SharedSessionConversationAdapter(store)
    foreign = SharedSessionState(session_id="other")
    backing["w1"] = foreign

    with pytest.raises(ConversationSessionConflictError) as excinfo:
        adapter.save_conversation(_state(session_id="w1"), expected_previous_revision=0)

    error = excinfo.value
    _assert_safe_conflict(error, "w1")
    # No durable write precedes the conflict: the backing map is untouched,
    # no new revision exists and no extension was committed anywhere.
    assert set(backing) == {"w1"}
    assert backing["w1"] is foreign
    assert backing["w1"].revision == 0
    assert CONVERSATION_EXTENSION_KEY not in backing["w1"].extensions


def test_a_committed_envelope_with_a_foreign_session_id_fails_closed() -> None:
    """Defence in depth: the committed envelope is re-verified after the commit."""

    store = InMemorySessionStore()
    shared = store.save(SharedSessionState(session_id="session-1"))
    adapter = SharedSessionConversationAdapter(_ForeignEnvelopeStore(store))

    with pytest.raises(ConversationSessionConflictError) as excinfo:
        adapter.save_conversation(_state(), expected_previous_revision=shared.revision)

    _assert_safe_conflict(excinfo.value, "session-1")


# ── Stored JSON null vs absent extension (fix round 1) ───────────────────────


@pytest.mark.parametrize("kind", ["memory", "file"])
def test_load_conversation_distinguishes_key_absence_from_a_stored_null(
    kind: str, tmp_path
) -> None:
    """An absent key means "no conversation"; a stored null fails closed."""

    inner: InMemorySessionStore | FileSessionStore = (
        InMemorySessionStore() if kind == "memory" else FileSessionStore(root=tmp_path)
    )
    inner.save(SharedSessionState(session_id="session-1"))
    adapter = SharedSessionConversationAdapter(inner)
    assert adapter.load_conversation("session-1") is None

    inner.save(
        SharedSessionState(
            session_id="session-2",
            extensions={CONVERSATION_EXTENSION_KEY: None},
        )
    )
    with pytest.raises(ConversationSessionConflictError) as excinfo:
        adapter.load_conversation("session-2")

    _assert_safe_conflict(excinfo.value, "session-2")


# ── Read-path session id validation (fix round 1) ────────────────────────────


def test_entry_points_reject_caller_misuse_of_the_session_id_before_any_store_call(
    tmp_path,
) -> None:
    """All store-reaching entry points reject a bad session id identically."""

    bad_ids = (None, 5, "", "   ", "x" * (MAX_IDENTIFIER_LENGTH + 1))

    memory = _NeverCalledStore()
    memory_adapter = SharedSessionConversationAdapter(memory)
    file_adapter = SharedSessionConversationAdapter(FileSessionStore(root=tmp_path))

    for bad in bad_ids:
        for adapter in (memory_adapter, file_adapter):
            with pytest.raises(ValueError):
                adapter.load_shared_session(bad)  # type: ignore[arg-type]
            with pytest.raises(ValueError):
                adapter.load_conversation(bad)  # type: ignore[arg-type]

    # ``save_conversation`` validates the state's session id the same way
    # (the subclass double bypasses the frozen value-object validation).
    for bad in (None, 5, ""):
        for adapter in (memory_adapter, file_adapter):
            with pytest.raises(ValueError):
                adapter.save_conversation(
                    _UnvalidatedState(session_id=bad),  # type: ignore[arg-type]
                    expected_previous_revision=0,
                )

    assert memory.calls == 0  # caller misuse never reaches the store
    assert list(tmp_path.iterdir()) == []  # and never writes anything


def test_entry_points_normalize_the_session_id_before_the_store_call() -> None:
    """The identifier check normalizes like every other package identifier."""

    store = InMemorySessionStore()
    shared = store.save(SharedSessionState(session_id="session-1"))
    adapter = SharedSessionConversationAdapter(store)

    assert adapter.load_shared_session("  session-1  ") == shared
    assert adapter.load_conversation("  session-1  ") is None
