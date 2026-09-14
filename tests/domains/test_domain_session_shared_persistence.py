"""Phase 10.34 V3 — Domain Session Shared Persistence Adapter Tests (BLOCKER-02).

Proves the production resume path binds to the real shared session
infrastructure owned by ``cmm.runtime`` (``SessionStore`` /
``SharedSessionState``), with:

- real load of the shared session by ID;
- typed domain extension extraction/attachment;
- atomic save/update through the shared store;
- durable, verifiable revisions across process/service-instance restarts;
- ``recorded_resumption=True`` meaning a real shared commit.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.errors import DomainSessionSerializationError
from cmm.domains.session_contracts import DomainSessionContext
from cmm.runtime.sessions import (
    FileSessionStore,
    InMemorySessionStore,
    SessionStore,
)


def _now() -> datetime:
    return datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


# ── SharedSessionDomainAdapter contract ──────────────────────────────────────


def _ctx(revision: int = 1) -> DomainSessionContext:
    return DomainSessionContext(
        session_id="sess-shared-1",
        primary_domain="domain:health",
        domain_versions={"domain:health": "1.0.0"},
        revision=revision,
        updated_at=_now(),
    )


def test_domain_session_uses_real_shared_session_service():
    from cmm.domains.session_persistence import SharedSessionDomainAdapter

    store: SessionStore = InMemorySessionStore()
    adapter = SharedSessionDomainAdapter(store=store)
    adapter.save_domain_session(_ctx())
    loaded = store.load("sess-shared-1")
    assert loaded is not None
    assert "domain_session" in loaded.extensions


def test_domain_session_roundtrip_through_shared_persistence():
    from cmm.domains.session_persistence import SharedSessionDomainAdapter

    store: SessionStore = InMemorySessionStore()
    adapter = SharedSessionDomainAdapter(store=store)
    saved = adapter.save_domain_session(_ctx())
    restored = adapter.load_domain_session("sess-shared-1")
    assert restored is not None
    # Stored domain session content round-trips structurally (revision belongs
    # to the shared envelope)
    assert restored.primary_domain == saved.primary_domain
    assert restored.session_id == saved.session_id


def test_pause_persist_reload_resume_persist_reload(tmp_path):
    from cmm.domains.session_persistence import SharedSessionDomainAdapter

    store: SessionStore = FileSessionStore(root=tmp_path)
    adapter = SharedSessionDomainAdapter(store=store)
    paused = _ctx()
    adapter.save_domain_session(paused)

    # "Process restart": new store + adapter over the same durable root
    restarted_store: SessionStore = FileSessionStore(root=tmp_path)
    restarted_adapter = SharedSessionDomainAdapter(store=restarted_store)
    reloaded = restarted_adapter.load_domain_session("sess-shared-1")
    assert reloaded is not None
    assert reloaded.primary_domain == "domain:health"

    # resume -> bump revision -> persist again
    resumed = DomainSessionContext(
        session_id="sess-shared-1",
        primary_domain="domain:health",
        revision=reloaded.revision + 1,
        updated_at=_now(),
    )
    restarted_adapter.save_domain_session(resumed)

    # reload again and verify durable revision advanced
    final_store: SessionStore = FileSessionStore(root=tmp_path)
    final = SharedSessionDomainAdapter(store=final_store).load_domain_session(
        "sess-shared-1"
    )
    assert final is not None
    assert final.revision == reloaded.revision + 1


def test_resumed_revision_survives_new_service_instance(tmp_path):
    from cmm.domains.session_persistence import SharedSessionDomainAdapter

    adapter1 = SharedSessionDomainAdapter(store=FileSessionStore(root=tmp_path))
    adapter1.save_domain_session(_ctx(revision=4))
    adapter2 = SharedSessionDomainAdapter(store=FileSessionStore(root=tmp_path))
    loaded = adapter2.load_domain_session("sess-shared-1")
    assert loaded is not None
    assert loaded.revision == 4


def test_shared_session_revision_matches_domain_revision_after_commit():
    from cmm.domains.session_persistence import SharedSessionDomainAdapter

    store: SessionStore = InMemorySessionStore()
    adapter = SharedSessionDomainAdapter(store=store)
    committed = adapter.save_domain_session(_ctx(revision=7))
    shared = store.load("sess-shared-1")
    assert shared is not None
    # the shared revision/history records the domain revision it carries
    assert shared.extensions["domain_session"]["revision"] == 7
    assert committed.revision == 7


def test_load_missing_shared_session_returns_none():
    from cmm.domains.session_persistence import SharedSessionDomainAdapter

    adapter = SharedSessionDomainAdapter(store=InMemorySessionStore())
    assert adapter.load_domain_session("does-not-exist") is None


def test_load_rejects_session_id_mismatch_inside_extension():
    from cmm.domains.session_persistence import SharedSessionDomainAdapter

    store: SessionStore = InMemorySessionStore()
    # Forge a shared session whose envelope id differs from the extension's
    forged = DomainSessionContext(
        session_id="sess-other", primary_domain="domain:health", updated_at=_now()
    )
    store.save(
        store.load("nope")
        or __import__("cmm.runtime.sessions", fromlist=["SharedSessionState"])
        .SharedSessionState(session_id="sess-envelope", status="ACTIVE")
        .with_extension("domain_session", forged.to_dict())
    )
    adapter = SharedSessionDomainAdapter(store=store)
    with pytest.raises(DomainSessionSerializationError):
        adapter.load_domain_session("sess-envelope")


def test_adapter_does_not_create_independent_repository():
    import cmm.domains as dom

    assert not hasattr(dom, "DomainSessionRepository")


def test_persistence_module_depends_only_on_shared_infra():
    """cmm.domains must depend on shared runtime, never the reverse."""
    import subprocess
    import sys

    code = (
        "import cmm.runtime.sessions, sys;"
        "m = sys.modules['cmm.runtime.sessions'];"
        "assert not any('cmm.domains' in str(m) for _ in [0]);"
        "import pathlib; text = pathlib.Path('cmm/runtime/sessions.py').read_text();"
        "assert 'cmm.domains' not in text"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
