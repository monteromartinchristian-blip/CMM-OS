"""Phase 11.3 — canonical session application service tests.

``SessionApplicationService`` is the public session concept of Phase 11.3, but
it owns no session storage: it delegates every read and write to the canonical
``cmm.runtime.sessions`` store, which keeps optimistic revision semantics and
durable persistence exactly where they already live.

These tests lock the constructor authority boundary (only the two canonical
concrete stores are accepted), the public projection, the fail-closed input
validation and the concurrency behavior.

See ``docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from cmm.application.contracts import MAX_IDENTIFIER_LENGTH, ApplicationSession
from cmm.application.errors import (
    ApplicationConflictError,
    ApplicationResourceNotFoundError,
    ConcurrencyConflictError,
    InvalidApplicationRequestError,
)
from cmm.application.sessions import SessionApplicationService
from cmm.runtime.sessions import (
    FileSessionStore,
    InMemorySessionStore,
    SharedSessionState,
)


class _DuckTypedStore:
    """A store-shaped object that is not one of the two canonical stores."""

    def __init__(self) -> None:
        self.state: dict[str, SharedSessionState] = {}
        self.saved: int = 0

    def load(self, session_id: str) -> SharedSessionState | None:
        return self.state.get(session_id)

    def save(self, state: SharedSessionState) -> SharedSessionState:
        self.saved += 1
        self.state[state.session_id] = state
        return state


def _memory_service() -> tuple[SessionApplicationService, InMemorySessionStore]:
    store = InMemorySessionStore()
    return SessionApplicationService(store), store


def _file_service(root: Path) -> SessionApplicationService:
    return SessionApplicationService(FileSessionStore(root))


# ── Constructor authority boundary ───────────────────────────────────────────


def test_memory_store_is_accepted() -> None:
    service, _store = _memory_service()

    assert isinstance(service.create_session("session-1"), ApplicationSession)


def test_file_store_is_accepted(tmp_path: Path) -> None:
    service = _file_service(tmp_path)

    assert service.create_session("session-1").revision == 1


def test_arbitrary_load_save_object_is_rejected() -> None:
    with pytest.raises(TypeError):
        SessionApplicationService(_DuckTypedStore())  # type: ignore[arg-type]


@pytest.mark.parametrize("store", [None, {}, object(), "session-1"])
def test_non_store_values_are_rejected(store: object) -> None:
    with pytest.raises(TypeError):
        SessionApplicationService(store)  # type: ignore[arg-type]


def test_service_is_not_a_store() -> None:
    """The service delegates; it never re-exposes a persistence surface."""

    service, _store = _memory_service()

    assert not hasattr(service, "load")
    assert not hasattr(service, "save")


# ── create_session ───────────────────────────────────────────────────────────


def test_create_session_projects_the_committed_canonical_state() -> None:
    service, _store = _memory_service()

    session = service.create_session("session-1")

    assert session.session_id == "session-1"
    assert session.revision == 1
    assert session.status == "ACTIVE"
    assert session.to_dict() == {
        "session_id": "session-1",
        "revision": 1,
        "status": "ACTIVE",
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


def test_create_session_delegates_to_the_canonical_store() -> None:
    service, store = _memory_service()

    service.create_session("session-1")

    canonical = store.load("session-1")
    assert canonical is not None
    assert canonical.revision == 1
    assert canonical.status == "ACTIVE"


def test_create_session_normalizes_the_canonical_identifier() -> None:
    service, store = _memory_service()

    session = service.create_session("  session-1  ")

    assert session.session_id == "session-1"
    assert store.load("session-1") is not None
    assert store.load("  session-1  ") is None


def test_create_session_projects_aware_timestamps() -> None:
    service, _store = _memory_service()

    session = service.create_session("session-1")

    for field in (session.created_at, session.updated_at):
        parsed = datetime.fromisoformat(field)
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() is not None


def test_creating_an_existing_session_conflicts() -> None:
    service, store = _memory_service()
    service.create_session("session-1")

    with pytest.raises(ApplicationConflictError) as raised:
        service.create_session("session-1")

    assert dict(raised.value.details) == {"reason_code": "SESSION_ALREADY_EXISTS"}
    canonical = store.load("session-1")
    assert canonical is not None
    assert canonical.revision == 1


def test_creating_an_existing_session_never_bumps_the_revision() -> None:
    service, store = _memory_service()
    service.create_session("session-1")

    with pytest.raises(ApplicationConflictError):
        service.create_session("session-1")

    assert store.load("session-1").revision == 1  # type: ignore[union-attr]


def test_creating_a_conflicting_session_preserves_the_original_status() -> None:
    service, store = _memory_service()
    service.create_session("session-1")
    state = store.load("session-1")
    assert state is not None
    store.save(state.with_status("CLOSED"))

    with pytest.raises(ApplicationConflictError):
        service.create_session("session-1")

    canonical = store.load("session-1")
    assert canonical is not None
    assert canonical.status == "CLOSED"


@pytest.mark.parametrize("session_id", ["", "   ", None, 1, b"session-1"])
def test_create_session_rejects_an_invalid_identifier(session_id: object) -> None:
    service, _store = _memory_service()

    with pytest.raises(InvalidApplicationRequestError):
        service.create_session(session_id)  # type: ignore[arg-type]


def test_create_session_rejects_an_oversized_identifier() -> None:
    service, _store = _memory_service()

    with pytest.raises(InvalidApplicationRequestError):
        service.create_session("s" * (MAX_IDENTIFIER_LENGTH + 1))


# ── get_session ──────────────────────────────────────────────────────────────


def test_get_session_returns_the_public_projection() -> None:
    service, _store = _memory_service()
    created = service.create_session("session-1")

    fetched = service.get_session("session-1")

    assert fetched == created
    assert fetched.to_dict() == created.to_dict()


def test_get_session_normalizes_the_identifier() -> None:
    service, _store = _memory_service()
    created = service.create_session("session-1")

    assert service.get_session(" session-1 ") == created


def test_get_absent_session_is_a_not_found() -> None:
    service, _store = _memory_service()

    with pytest.raises(ApplicationResourceNotFoundError) as raised:
        service.get_session("session-absent")

    assert dict(raised.value.details) == {"reason_code": "SESSION_NOT_FOUND"}


def test_get_session_rejects_an_invalid_identifier() -> None:
    service, _store = _memory_service()

    with pytest.raises(InvalidApplicationRequestError):
        service.get_session("")  # type: ignore[arg-type]


def test_reads_never_mutate_the_canonical_store() -> None:
    service, store = _memory_service()
    service.create_session("session-1")
    before = store.load("session-1")
    assert before is not None

    service.get_session("session-1")
    service.require_revision("session-1", 1)
    with pytest.raises(ApplicationResourceNotFoundError):
        service.get_session("session-absent")

    after = store.load("session-1")
    assert after is not None
    assert after.revision == before.revision
    assert after.updated_at == before.updated_at


# ── require_revision ─────────────────────────────────────────────────────────


def test_require_revision_accepts_the_current_revision() -> None:
    service, _store = _memory_service()
    created = service.create_session("session-1")

    assert service.require_revision("session-1", created.revision) == created


def test_require_revision_without_an_assertion() -> None:
    service, _store = _memory_service()
    created = service.create_session("session-1")

    assert service.require_revision("session-1", None) == created


def test_require_revision_rejects_a_stale_revision() -> None:
    service, _store = _memory_service()
    service.create_session("session-1")

    with pytest.raises(ConcurrencyConflictError) as raised:
        service.require_revision("session-1", 0)

    assert dict(raised.value.details) == {"reason_code": "SESSION_REVISION_STALE"}
    assert raised.value.retryable is True


def test_require_revision_reads_the_current_canonical_revision() -> None:
    service, store = _memory_service()
    service.create_session("session-1")
    state = store.load("session-1")
    assert state is not None
    committed = store.save(state.with_status("CLOSED"))
    assert committed.revision == 2

    with pytest.raises(ConcurrencyConflictError):
        service.require_revision("session-1", 1)

    assert service.require_revision("session-1", 2).status == "CLOSED"


def test_require_revision_on_an_absent_session_is_a_not_found() -> None:
    service, _store = _memory_service()

    with pytest.raises(ApplicationResourceNotFoundError):
        service.require_revision("session-absent", None)

    with pytest.raises(ApplicationResourceNotFoundError):
        service.require_revision("session-absent", 0)


@pytest.mark.parametrize("expected", [True, -1, "1", 1.0])
def test_require_revision_rejects_an_invalid_expectation(expected: object) -> None:
    service, _store = _memory_service()
    service.create_session("session-1")

    with pytest.raises(InvalidApplicationRequestError):
        service.require_revision("session-1", expected)  # type: ignore[arg-type]


def test_malformed_input_fails_before_the_store_is_read() -> None:
    """Public validation happens before any canonical lookup."""

    service, _store = _memory_service()

    with pytest.raises(InvalidApplicationRequestError):
        service.require_revision("session-absent", -1)


# ── Canonical durability boundary ────────────────────────────────────────────


def test_shared_memory_backing_is_visible_across_service_instances() -> None:
    backing: dict[str, SharedSessionState] = {}
    first = SessionApplicationService(InMemorySessionStore(backing))
    second = SessionApplicationService(InMemorySessionStore(backing))

    created = first.create_session("session-1")

    assert second.get_session("session-1") == created


def test_file_store_survives_a_service_restart(tmp_path: Path) -> None:
    created = _file_service(tmp_path).create_session("session-1")

    restarted = _file_service(tmp_path).get_session("session-1")

    assert restarted == created
    assert restarted.revision == 1
