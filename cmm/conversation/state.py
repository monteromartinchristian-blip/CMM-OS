"""Phase 11.5 — conversation state persisted inside the canonical shared session.

The conversational transcript owns no persistence of its own: Phase 11.5
introduces no second persistence owner, so ``ConversationState`` travels inside
the canonical shared session owned by ``cmm.runtime`` under the namespaced
extension key ``conversation.v1``.  This module owns only the translation
between the frozen conversational state and that extension plus the
optimistic-revision commit rules; durability, atomicity, revision assignment and
change history stay with the canonical ``SessionStore``.

Architecture (dependency direction is mandatory):

    cmm.runtime (canonical shared session infrastructure — generic)
            ↑
    cmm.conversation.state (this adapter)
            ↑
    cmm.conversation.service (later Phase 11.5 tasks)

The adapter never subclasses, wraps, replaces or re-implements the store and
keeps no side dictionary, cache or repository: the supplied ``SessionStore`` is
the only persistence path, and the only write is one ``SessionStore.save`` on a
``SharedSessionState.with_extension`` copy.

Commit semantics:

- a missing canonical session fails with ``ConversationSessionNotFoundError``;
- an unreadable or corrupt canonical store fails closed as the safe
  ``ConversationSessionConflictError`` — on the pre-read and on the commit
  alike — with a constant message, no store text, no session id and no cause
  chain (``raise ... from None``);
- a stale ``expected_previous_revision`` fails with the safe
  ``ConversationSessionConflictError`` before anything is written;
- an envelope whose ``session_id`` disagrees with the committed state fails
  with the same safe conflict *before* any durable write (re-verified on the
  committed envelope afterwards, as defence in depth);
- a canonical race at ``store.save`` (the store's ``SessionPersistenceError``
  revision guard) is remapped to the same safe conversation conflict error,
  with no leaked store text and no retry;
- a commit must advance the canonical revision by exactly one: a commit whose
  committed revision did not advance (for example a canonical entry deleted
  between the read and the commit, which the store then commits as a brand-new
  session) fails with the safe conflict error — the durable write that already
  happened is the competitor's own session, so it is reported, never returned
  as success, never retried and never undone;
- the committed extension is re-read from the committed envelope and returned;
  a commit that did not durably carry the extension fails closed.

Load semantics: the caller-supplied ``session_id`` is validated with the
package's identifier check before any store call, and an unreadable or corrupt
store fails closed as the safe conflict error.  An unsupported extension
``version``, an extension whose ``session_id`` disagrees with the envelope
``session_id``, duplicate message IDs, a message from another session, an
unresolvable ``active_message_id`` and any other payload that fails the frozen
extension contract fail closed as the conversation conflict error — as does a
present stored value that is not a mapping (including a stored JSON ``null``;
an absent extension key simply means the session has no conversation).  The
boundary never exposes a raw payload ``ValueError``, a store ``TypeError`` or
internal store text.

See ``docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md`` §8.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

from cmm.conversation.contracts import (
    ConversationMessage,
    _identifier,
    _optional_identifier,
)
from cmm.conversation.errors import (
    ConversationBoundaryError,
    ConversationSessionConflictError,
    ConversationSessionNotFoundError,
)

if TYPE_CHECKING:
    from cmm.runtime.sessions import SessionStore, SharedSessionState

__all__ = [
    "CONVERSATION_EXTENSION_KEY",
    "CONVERSATION_EXTENSION_VERSION",
    "ConversationState",
    "SharedSessionConversationAdapter",
]

#: The canonical namespaced shared-session extension key of the conversation.
CONVERSATION_EXTENSION_KEY = "conversation.v1"

#: The one supported version of the serialized conversation extension.
CONVERSATION_EXTENSION_VERSION = 1

#: The closed serialized extension shape; unknown fields fail closed.
_STATE_FIELDS = frozenset(
    {"version", "session_id", "mode", "bot_id", "active_message_id", "messages"}
)

_BYTES_LIKE = (str, bytes, bytearray, memoryview)


# ── Serialized payload readers ────────────────────────────────────────────────


def _message_tuple(value: object) -> tuple[ConversationMessage, ...]:
    """Require real conversational messages; raw payloads are never coerced."""

    if isinstance(value, _BYTES_LIKE) or not isinstance(value, Sequence):
        raise TypeError("messages must be a sequence of ConversationMessage values")
    messages: list[ConversationMessage] = []
    for item in value:
        if not isinstance(item, ConversationMessage):
            raise TypeError("messages must contain ConversationMessage values")
        messages.append(item)
    return tuple(messages)


def _serialized_messages(value: object) -> tuple[ConversationMessage, ...]:
    """Read messages back out of a serialized or frozen extension payload."""

    if value is None:
        return ()
    if isinstance(value, _BYTES_LIKE) or not isinstance(value, Sequence):
        raise TypeError("messages must be a sequence of serialized messages")
    messages: list[ConversationMessage] = []
    for item in value:
        if isinstance(item, ConversationMessage):
            messages.append(item)
        elif isinstance(item, Mapping):
            messages.append(ConversationMessage.from_dict(item))
        else:
            raise TypeError("messages must contain ConversationMessage values")
    return tuple(messages)


def _checked_expected_revision(value: object) -> None:
    """Fail closed on a malformed optimistic-revision guard value."""

    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(
            "expected_previous_revision must be a non-negative int or None"
        )


def _checked_session_id(value: object) -> str:
    """Validate one canonical session id before any store call.

    The grammar is the package's ``_identifier`` check — a stripped, non-empty
    string within ``MAX_IDENTIFIER_LENGTH`` — so an id is read and normalized
    exactly like every other conversational identifier.  Caller misuse (a
    non-string, a blank and an oversized id alike) fails as the module's one
    consistent ``ValueError`` whatever the store implementation — the same
    misuse convention as ``_checked_expected_revision`` — so the store is never
    reached with a malformed id and no raw store ``TypeError`` can escape the
    conversational boundary.
    """

    # Caller misuse is the module's one consistent ValueError at the adapter
    # entry (the same misuse convention as ``_checked_expected_revision``):
    # never a raw store error, whatever the store implementation.
    if not isinstance(value, str) or not value.strip():
        raise ValueError("session_id must be a non-empty string")
    return _identifier(value, "session_id")


# ── Conversation state ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ConversationState:
    """Frozen, append-only conversational state of one canonical session.

    The state is public-safe by construction (its messages are frozen public
    conversational contracts), deterministic through ``to_dict()`` and
    ``from_dict()``, and structurally validated: message IDs are unique, every
    message belongs to the state session and a non-null ``active_message_id``
    always resolves.  ``append`` never mutates this value; it returns a new one.
    """

    session_id: str
    messages: tuple[ConversationMessage, ...] = ()
    mode: str = "general"
    bot_id: str | None = None
    active_message_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "session_id", _identifier(self.session_id, "session_id")
        )
        messages = _message_tuple(self.messages)
        object.__setattr__(self, "messages", messages)
        object.__setattr__(self, "mode", _identifier(self.mode, "mode"))
        object.__setattr__(self, "bot_id", _optional_identifier(self.bot_id, "bot_id"))
        object.__setattr__(
            self,
            "active_message_id",
            _optional_identifier(self.active_message_id, "active_message_id"),
        )
        message_ids = [message.id for message in messages]
        if len(set(message_ids)) != len(message_ids):
            raise ValueError("conversation message IDs must be unique within the state")
        if any(message.session_id != self.session_id for message in messages):
            raise ValueError("every message must belong to the conversation session")
        if self.active_message_id is not None and self.active_message_id not in set(
            message_ids
        ):
            raise ValueError("active_message_id must refer to a stored message")

    # ── serialization ────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Return the frozen serialized extension shape of this state."""

        return {
            "version": CONVERSATION_EXTENSION_VERSION,
            "session_id": self.session_id,
            "mode": self.mode,
            "bot_id": self.bot_id,
            "active_message_id": self.active_message_id,
            "messages": [message.to_dict() for message in self.messages],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ConversationState:
        """Read a conversation state back, failing closed on any violation."""

        if not isinstance(data, Mapping):
            raise TypeError("conversation state requires a mapping")
        for key in data:
            if not isinstance(key, str) or key not in _STATE_FIELDS:
                raise ValueError("conversation state contains an unsupported field")
        for required in ("version", "session_id"):
            if required not in data:
                raise ValueError(
                    f"conversation state is missing required field {required!r}"
                )
        version = data["version"]
        if (
            isinstance(version, bool)
            or not isinstance(version, int)
            or version != CONVERSATION_EXTENSION_VERSION
        ):
            raise ValueError("conversation extension version is not supported")
        return cls(
            session_id=data["session_id"],
            messages=_serialized_messages(data.get("messages", ())),
            mode=data.get("mode", "general"),
            bot_id=data.get("bot_id"),
            active_message_id=data.get("active_message_id"),
        )

    # ── append-only editing ──────────────────────────────────────────────────

    def append(self, *messages: ConversationMessage) -> ConversationState:
        """Return a new state with *messages* appended (never mutating this one)."""

        for message in messages:
            if not isinstance(message, ConversationMessage):
                raise TypeError("append requires ConversationMessage values")
        return replace(self, messages=self.messages + messages)

    def message(self, message_id: str) -> ConversationMessage:
        """Return the stored message with *message_id*.

        An ID that is not part of this state fails closed with the safe
        conversational boundary error (code ``INVALID_REQUEST``); it is never
        inlined into the failure message.
        """

        wanted = _identifier(message_id, "message_id")
        for message in self.messages:
            if message.id == wanted:
                return message
        raise ConversationBoundaryError()


# ── Canonical shared-session adapter ──────────────────────────────────────────


class SharedSessionConversationAdapter:
    """Loads/saves ``ConversationState`` through the canonical shared store.

    The shared ``SessionStore`` is the authoritative persistence boundary; this
    adapter only translates between the generic shared envelope and the typed
    conversation extension.  All durability/atomicity/revision semantics are
    owned by the shared store, which is never subclassed, wrapped or replaced.
    """

    def __init__(
        self,
        store: SessionStore,
        extension_key: str = CONVERSATION_EXTENSION_KEY,
    ) -> None:
        if store is None:
            raise ValueError("store (shared SessionStore) is required")
        for required in ("load", "save"):
            if not callable(getattr(store, required, None)):
                raise TypeError(f"store must implement {required}()")
        if not isinstance(extension_key, str) or not extension_key.strip():
            raise ValueError("extension_key must be a non-empty string")
        self._store = store
        self._extension_key = extension_key

    @property
    def store(self) -> SessionStore:
        return self._store

    def load_shared_session(self, session_id: str) -> SharedSessionState | None:
        """Load the raw canonical shared session state by ID.

        The id is validated before any store call and a failing store fails
        closed as the safe conversation conflict error: no store text and no
        session id may escape the conversational boundary.
        """

        return self._load_shared(_checked_session_id(session_id))

    def load_conversation(self, session_id: str) -> ConversationState | None:
        """Load and validate the conversation extension of a shared session.

        Returns ``None`` when the canonical session is absent or when its
        envelope carries no extension under the conversation key; a present
        stored value that is not a valid extension mapping (including a stored
        JSON ``null``) and any unreadable store fail closed as the safe
        conversation conflict error.
        """

        shared = self._load_shared(_checked_session_id(session_id))
        if shared is None:
            return None
        extensions = shared.extensions
        if self._extension_key not in extensions:
            return None
        return self._extension_state(shared, extensions[self._extension_key])

    def save_conversation(
        self,
        state: ConversationState,
        *,
        expected_previous_revision: int | None,
    ) -> tuple[ConversationState, SharedSessionState]:
        """Commit *state* as the conversation extension of its shared session.

        The write is exactly one ``SessionStore.save`` on a
        ``SharedSessionState.with_extension`` copy; the committed extension is
        re-read and returned together with the committed envelope.  Every
        failure fails closed as a safe conversation error: a missing session as
        not-found; an unreadable store, a stale revision, an envelope whose
        ``session_id`` disagrees with the committed state (checked before the
        write) and a commit that did not advance the canonical revision by
        exactly one as conflict — with no store text, no retry and no attempt
        to undo a competing write.
        """

        if not isinstance(state, ConversationState):
            raise TypeError("state must be a ConversationState")
        session_id = _checked_session_id(state.session_id)
        _checked_expected_revision(expected_previous_revision)
        shared = self._load_shared(session_id)
        if shared is None:
            raise ConversationSessionNotFoundError()
        if state.session_id != shared.session_id:
            # A hand-edited or foreign canonical envelope conflicts *before*
            # anything is written; the committed envelope is re-verified below
            # as defence in depth.
            raise ConversationSessionConflictError()
        if (
            expected_previous_revision is not None
            and shared.revision != expected_previous_revision
        ):
            raise ConversationSessionConflictError()
        updated = shared.with_extension(self._extension_key, state.to_dict())
        committed = self._save_shared(updated)
        if committed.revision != shared.revision + 1:
            # The canonical revision did not advance by one: a competing delete
            # made the store commit this write as a brand-new session (from
            # revision 0).  The durable write that already happened is the
            # competitor's own new session — it is reported as the conflict,
            # never returned as success, never retried and never undone.
            raise ConversationSessionConflictError()
        # The committed extension is re-read; a committed envelope that did not
        # durably carry a valid extension fails closed inside ``_extension_state``.
        return (
            self._extension_state(
                committed, committed.extensions.get(self._extension_key)
            ),
            committed,
        )

    # ── internals ────────────────────────────────────────────────────────────

    def _load_shared(self, session_id: str) -> SharedSessionState | None:
        """Load the canonical envelope, remapping every store failure.

        A store failure may carry store text (paths, the session id), so it
        fails closed as the safe conversation conflict with no cause chain; an
        absent session is the store's ``None`` result and never an exception.
        ``BaseException`` (``KeyboardInterrupt``/``SystemExit``) is not caught;
        every ``Exception`` is, because *any* store failure must fail closed.
        """

        try:
            return self._store.load(session_id)
        except Exception:  # noqa: BLE001
            raise ConversationSessionConflictError() from None

    def _save_shared(self, state: SharedSessionState) -> SharedSessionState:
        """Commit the canonical envelope, remapping every store failure.

        A canonical revision race (the store's own optimistic-concurrency
        guard) and any other persistence failure become the safe conversation
        conflict, with no leaked store text, no cause chain and no retry.
        """

        try:
            return self._store.save(state)
        except Exception:  # noqa: BLE001
            raise ConversationSessionConflictError() from None

    def _extension_state(
        self, shared: SharedSessionState, raw: object
    ) -> ConversationState:
        """Read one stored extension, failing closed on any violation."""

        if not isinstance(raw, Mapping):
            raise ConversationSessionConflictError()
        try:
            state = ConversationState.from_dict(raw)
        except (TypeError, ValueError, KeyError):
            raise ConversationSessionConflictError() from None
        if state.session_id != shared.session_id:
            raise ConversationSessionConflictError()
        return state
