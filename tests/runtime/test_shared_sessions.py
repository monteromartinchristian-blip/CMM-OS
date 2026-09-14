"""Phase 10.34 V3 — Shared Session Infrastructure Tests (BLOCKER-02).

Verifies the generic shared session persistence service owned by
``cmm.runtime`` (outside ``cmm.domains``):

- ``SharedSessionState``: immutable, JSON-safe, revisioned session envelope
  with typed generic extensions and change history.
- ``SessionStore`` protocol + ``FileSessionStore``: durable, atomic,
  process-restart-safe persistence with optimistic revision checking.

Dependency direction: ``cmm.runtime`` must never import ``cmm.domains``.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from cmm.runtime.sessions import (
    FileSessionStore,
    InMemorySessionStore,
    SessionNotFoundError,
    SessionPersistenceError,
    SessionStore,
    SharedSessionState,
)


def _now() -> datetime:
    return datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


# ── SharedSessionState contract ──────────────────────────────────────────────


def test_shared_session_state_is_immutable_and_json_safe():
    state = SharedSessionState(
        session_id="sess-1",
        status="ACTIVE",
        extensions={"domain_session": {"session_id": "sess-1", "rev": 1}},
        created_at=_now(),
        updated_at=_now(),
    )
    with pytest.raises(FrozenInstanceError):
        state.session_id = "other"  # type: ignore[misc]
    payload = json.dumps(state.to_dict(), allow_nan=False)
    restored = SharedSessionState.from_dict(json.loads(payload))
    assert restored == state


def test_shared_session_state_extensions_are_deeply_frozen():
    ext = {"domain_session": {"nested": ["a", "b"]}}
    state = SharedSessionState(
        session_id="sess-1",
        status="ACTIVE",
        extensions=ext,
    )
    # mutating the original input must not alias into the frozen state
    ext["domain_session"]["nested"].append("c")
    got = state.extensions["domain_session"]
    assert list(got["nested"]) == ["a", "b"]


def test_shared_session_state_rejects_empty_session_id():
    with pytest.raises(ValueError):
        SharedSessionState(session_id="   ", status="ACTIVE")


def test_shared_session_state_rejects_non_json_safe_payload():
    class Opaque:
        pass

    with pytest.raises(ValueError):
        SharedSessionState(
            session_id="sess-1",
            status="ACTIVE",
            extensions={"bad": Opaque()},
        )


def test_shared_session_state_default_revision_is_zero_until_committed():
    state = SharedSessionState(session_id="sess-1", status="ACTIVE")
    assert state.revision == 0
    assert state.change_history == ()


# ── FileSessionStore: durable + restart-safe persistence ─────────────────────


def test_save_and_load_roundtrip(tmp_path):
    store = FileSessionStore(root=tmp_path)
    state = SharedSessionState(
        session_id="sess-persist",
        status="ACTIVE",
        extensions={"domain_session": {"session_id": "sess-persist"}},
        created_at=_now(),
        updated_at=_now(),
    )
    saved = store.save(state)
    assert saved.revision == 1

    # Process-restart boundary: a brand new store instance reads durable state
    reloaded_store = FileSessionStore(root=tmp_path)
    reloaded = reloaded_store.load("sess-persist")
    assert reloaded is not None
    assert reloaded.session_id == "sess-persist"
    assert reloaded.extensions["domain_session"] == {"session_id": "sess-persist"}


def test_save_increments_revision_and_records_history(tmp_path):
    store = FileSessionStore(root=tmp_path)
    s1 = store.save(SharedSessionState(session_id="sess-h", status="ACTIVE"))
    assert s1.revision == 1
    s2 = store.save(s1.with_status("PAUSED"))
    assert s2.revision == 2
    assert s2.change_history[-1].from_revision == 1
    assert s2.change_history[-1].to_revision == 2
    assert s2.change_history[-1].reason == "status:PAUSED"


def test_load_missing_session_returns_none(tmp_path):
    store = FileSessionStore(root=tmp_path)
    assert store.load("nope") is None


def test_optimistic_revision_conflict_fails(tmp_path):
    store = FileSessionStore(root=tmp_path)
    s1 = store.save(SharedSessionState(session_id="sess-c", status="ACTIVE"))
    # Another writer commits revision 2 first
    store.save(s1.with_status("PAUSED"))
    # Stale writer tries to commit on top of revision 1
    with pytest.raises(SessionPersistenceError):
        store.save(s1.with_status("ACTIVE"))


def test_corrupt_store_file_fails_closed(tmp_path):
    store = FileSessionStore(root=tmp_path)
    store.save(SharedSessionState(session_id="sess-x", status="ACTIVE"))
    target = tmp_path / "sess-x.json"
    target.write_text("{ not json", encoding="utf-8")
    with pytest.raises(SessionPersistenceError):
        store.load("sess-x")


def test_session_store_is_a_protocol():
    from typing import runtime_checkable  # noqa: F401

    store: SessionStore = FileSessionStore(root=None)
    assert callable(store.load)
    assert callable(store.save)


def test_in_memory_store_shares_durable_backing_across_instances():
    backing: dict[str, SharedSessionState] = {}
    writer = InMemorySessionStore(backing=backing)
    writer.save(SharedSessionState(session_id="sess-m", status="ACTIVE"))
    # restart boundary: new service instance over the same backing
    reader = InMemorySessionStore(backing=backing)
    loaded = reader.load("sess-m")
    assert loaded is not None
    assert loaded.session_id == "sess-m"


def test_shared_session_core_does_not_import_cmm_domains():
    from pathlib import Path

    runtime_dir = Path("cmm/runtime")
    for py_file in runtime_dir.glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        assert "cmm.domains" not in text, (
            f"Illegal import of cmm.domains in shared runtime core: {py_file}"
        )


def test_timezone_aware_datetimes_encode_as_iso():
    state = SharedSessionState(
        session_id="sess-t",
        status="ACTIVE",
        created_at=_now(),
        updated_at=_now() + timedelta(minutes=5),
    )
    encoded = state.to_dict()
    assert encoded["created_at"].endswith("+00:00")
    assert SharedSessionState.from_dict(encoded) == state


def test_session_not_found_error_carries_no_secrets():
    err = SessionNotFoundError("sess-1")
    assert "sess-1" in str(err)
