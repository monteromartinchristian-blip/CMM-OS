"""Phase 11.3 — the canonical session application service.

Sessions are a public application concept, but Phase 11.3 owns no session
storage and no session authority.  :class:`SessionApplicationService` is a thin
adapter over the canonical ``cmm.runtime.sessions`` store: it validates public
input, delegates every read and write to the canonical store and projects the
committed state into the safe public :class:`ApplicationSession` value.

Three boundaries are deliberate:

- the constructor accepts only the two canonical concrete stores
  (``InMemorySessionStore`` / ``FileSessionStore``), never an arbitrary
  ``load``/``save`` object, so a cross-wired graph fails at construction;
- the service neither creates nor re-exposes a persistence surface: it has no
  ``load``/``save`` and never touches private backing state;
- optimistic concurrency stays with the canonical store.  ``require_revision``
  only *asserts* the caller's expectation against the current canonical
  revision; it never locks, caches or mutates.

A concurrent double-create is therefore surfaced by the canonical store's own
optimistic revision check rather than by a new application lock, and no global
concurrency manager is introduced.

See ``docs/reference/phase-11-application-backend.md``.
"""

from __future__ import annotations

from cmm.application.contracts import MAX_IDENTIFIER_LENGTH, ApplicationSession
from cmm.application.errors import (
    ApplicationConflictError,
    ApplicationResourceNotFoundError,
    ConcurrencyConflictError,
    InvalidApplicationRequestError,
)
from cmm.runtime.sessions import (
    FileSessionStore,
    InMemorySessionStore,
    SharedSessionState,
)

__all__ = ["SessionApplicationService"]


def _session_identifier(value: object) -> str:
    """Return the normalized session identifier or fail closed.

    Validation is deliberately narrower than the canonical store's own check:
    the public boundary owns its limits, so an oversized or non-textual
    identifier is rejected as an invalid request before any store lookup.
    """

    if not isinstance(value, str):
        raise InvalidApplicationRequestError(
            details={"reason_code": "INVALID_SESSION_ID"}
        )
    normalized = value.strip()
    if not normalized:
        raise InvalidApplicationRequestError(
            details={"reason_code": "INVALID_SESSION_ID"}
        )
    if len(normalized) > MAX_IDENTIFIER_LENGTH:
        raise InvalidApplicationRequestError(
            details={"reason_code": "INVALID_SESSION_ID"}
        )
    return normalized


def _expected_revision(value: object) -> int | None:
    """Return the caller's revision assertion or fail closed."""

    if value is None:
        return None
    # ``bool`` is an ``int`` subclass; ``True`` is a caller defect, not a
    # revision of one.
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidApplicationRequestError(
            details={"reason_code": "INVALID_EXPECTED_REVISION"}
        )
    if value < 0:
        raise InvalidApplicationRequestError(
            details={"reason_code": "INVALID_EXPECTED_REVISION"}
        )
    return value


def _to_application_session(state: SharedSessionState) -> ApplicationSession:
    """Project canonical shared session state into the public value."""

    return ApplicationSession(
        session_id=state.session_id,
        revision=state.revision,
        status=state.status,
        created_at=state.created_at.isoformat(),
        updated_at=state.updated_at.isoformat(),
    )


class SessionApplicationService:
    """Public-safe session commands and queries over the canonical store."""

    def __init__(self, store: InMemorySessionStore | FileSessionStore) -> None:
        if not isinstance(store, (InMemorySessionStore, FileSessionStore)):
            raise TypeError(
                "store must be a canonical InMemorySessionStore or FileSessionStore"
            )
        self._store = store

    # ── Commands ─────────────────────────────────────────────────────────────

    def create_session(self, session_id: str) -> ApplicationSession:
        """Create one canonical session and return its public projection.

        Creating an identifier that already exists is a conflict and never
        mutates, replaces or re-versions the existing canonical session.
        """

        normalized = _session_identifier(session_id)
        if self._store.load(normalized) is not None:
            raise ApplicationConflictError(
                details={"reason_code": "SESSION_ALREADY_EXISTS"}
            )
        committed = self._store.save(SharedSessionState(session_id=normalized))
        return _to_application_session(committed)

    # ── Queries ──────────────────────────────────────────────────────────────

    def get_session(self, session_id: str) -> ApplicationSession:
        """Return the public projection of one existing canonical session."""

        return _to_application_session(self._require_state(session_id))

    def require_revision(
        self,
        session_id: str,
        expected_revision: int | None = None,
    ) -> ApplicationSession:
        """Assert the caller's revision expectation and return the session.

        ``None`` means the caller asserts nothing about the revision; the
        session must still exist.  Any other value must equal the current
        canonical revision, otherwise the caller holds stale state.
        """

        normalized = _session_identifier(session_id)
        expected = _expected_revision(expected_revision)
        state = self._require_state(normalized)
        if expected is not None and state.revision != expected:
            raise ConcurrencyConflictError(
                details={"reason_code": "SESSION_REVISION_STALE"}
            )
        return _to_application_session(state)

    # ── Canonical delegation ─────────────────────────────────────────────────

    def _require_state(self, session_id: str) -> SharedSessionState:
        normalized = _session_identifier(session_id)
        state = self._store.load(normalized)
        if state is None:
            raise ApplicationResourceNotFoundError(
                details={"reason_code": "SESSION_NOT_FOUND"}
            )
        return state
