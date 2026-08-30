"""Phase 10.34 V3 Remediation — Domain Session Resumer production path (B02).

from tests.domains.domain_session_test_support import shared_session_adapter
The resumer's production persistence path must bind to the real shared
session infrastructure (``cmm.runtime.sessions``) through the
``SharedSessionDomainAdapter`` — the ``persistence_updater`` callback alone
is not evidence of shared persistence, and ``recorded_resumption=True``
must mean a real shared commit.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.identifiers import DomainId, DomainManifestId
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import DomainRegistryRecord
from cmm.domains.session_contracts import (
    DomainSessionContext,
    DomainSessionResumeRequest,
)
from cmm.domains.session_persistence import SharedSessionDomainAdapter
from cmm.domains.session_resumer import DomainSessionResumer
from cmm.runtime.sessions import FileSessionStore, InMemorySessionStore


def _now() -> datetime:
    return datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


def _make_registry() -> DomainRegistry:
    reg = DomainRegistry()
    defs = [
        _make_definition("general", "1.0.0"),
        _make_definition("health", "1.0.0"),
    ]
    for d in defs:
        reg.register(d)
        reg.restore_record(
            DomainRegistryRecord(
                definition=d,
                status=DomainStatus.ACTIVE,
                registered_at=_now(),
                updated_at=_now(),
            )
        )
    return reg


def _make_definition(slug: str, version: str = "1.0.0") -> DomainDefinition:
    return DomainDefinition(
        id=DomainId(slug=slug),
        name=slug,
        display_name=f"Domain {slug}",
        version=version,
        kind=DomainKind.PERSONAL,
        description=f"Description for {slug}",
        manifest_id=DomainManifestId(slug=slug, version=version),
    )


def _request(session_id: str = "sess-prod-1") -> DomainSessionResumeRequest:
    return DomainSessionResumeRequest(
        session_id=session_id,
        actor="user:chris",
    )


def _context(session_id: str = "sess-prod-1") -> DomainSessionContext:
    return DomainSessionContext(
        session_id=session_id,
        primary_domain="domain:general",
        domain_versions={"domain:general": "1.0.0"},
        revision=3,
        updated_at=_now(),
    )


def _resumer(store, **kw) -> DomainSessionResumer:
    adapter = SharedSessionDomainAdapter(store=store)
    return DomainSessionResumer(
        registry=kw.pop("registry", _make_registry()),
        permission_evaluator=kw.pop("permission_evaluator", lambda a, p: tuple(p)),
        operation_filter=kw.pop("operation_filter", lambda p, o: tuple(o)),
        shared_session_adapter=adapter,
        **kw,
    )


# ── §6: resumer binds to the real shared session service ────────────────────


def test_domain_session_uses_real_shared_session_service(tmp_path):
    store = FileSessionStore(root=tmp_path)
    resumer = _resumer(store)
    ctx = _context()
    result = resumer.resume(_request(), session_context=ctx)
    assert result.status.value == "RESUMED"
    # The shared store durably holds the domain extension after resume
    reloaded = SharedSessionDomainAdapter(
        store=FileSessionStore(root=tmp_path)
    ).load_domain_session("sess-prod-1")
    assert reloaded is not None
    assert reloaded.primary_domain == "domain:general"


def test_domain_session_roundtrip_through_shared_persistence(tmp_path):
    store = FileSessionStore(root=tmp_path)
    resumer = _resumer(store)
    result = resumer.resume(_request(), session_context=_context())
    assert result.recorded_resumption is True
    adapter = SharedSessionDomainAdapter(store=FileSessionStore(root=tmp_path))
    restored = adapter.load_domain_session("sess-prod-1")
    assert restored is not None
    assert restored.revision == result.resumed_revision


def test_pause_persist_reload_resume_persist_reload(tmp_path):
    store = FileSessionStore(root=tmp_path)
    adapter = SharedSessionDomainAdapter(store=store)
    adapter.save_domain_session(_context())

    # restart boundary
    r1 = _resumer(FileSessionStore(root=tmp_path))
    # resumer must load the persisted context through the shared store when
    # no explicit context is supplied
    loaded_ctx = SharedSessionDomainAdapter(
        store=FileSessionStore(root=tmp_path)
    ).load_domain_session("sess-prod-1")
    assert loaded_ctx is not None
    resumed = r1.resume(_request(), session_context=loaded_ctx)
    assert resumed.recorded_resumption is True

    # second restart shows the durable revision advanced
    after = SharedSessionDomainAdapter(
        store=FileSessionStore(root=tmp_path)
    ).load_domain_session("sess-prod-1")
    assert after is not None
    assert after.revision > loaded_ctx.revision


def test_resumed_revision_survives_new_service_instance(tmp_path):
    r1 = _resumer(FileSessionStore(root=tmp_path))
    result = r1.resume(_request(), session_context=_context())
    adapter2 = SharedSessionDomainAdapter(store=FileSessionStore(root=tmp_path))
    ctx2 = adapter2.load_domain_session("sess-prod-1")
    assert ctx2 is not None
    assert ctx2.revision == result.resumed_revision


def test_recorded_resumption_requires_real_shared_commit(tmp_path):
    """persistence_updater callback alone must not claim recorded_resumption."""
    store = InMemorySessionStore()
    resumer = DomainSessionResumer(
        registry=_make_registry(),
        permission_evaluator=lambda a, p: tuple(p),
        operation_filter=lambda p, o: tuple(o),
        # Intentional negative regression: legacy callback alone is not
        # authoritative shared persistence.
        persistence_updater=lambda c: None,
    )
    result = resumer.resume(_request(), session_context=_context())
    # Without a real shared-store commit, the resumer must not claim a
    # durable resumption nor fabricate one via the legacy callback.
    assert store.load("sess-prod-1") is None
    assert result.recorded_resumption is False
    assert result.blocking_findings  # fail closed with explicit finding


def test_shared_session_revision_matches_domain_revision_after_commit(tmp_path):
    store = FileSessionStore(root=tmp_path)
    resumer = _resumer(store)
    resumer.resume(_request(), session_context=_context())
    adapter = SharedSessionDomainAdapter(store=FileSessionStore(root=tmp_path))
    committed = adapter.load_domain_session("sess-prod-1")
    assert committed is not None
    shared = adapter.load_shared_session("sess-prod-1")
    assert shared is not None
    assert shared.extensions["domain_session"]["revision"] == committed.revision


def test_shared_persistence_failure_keeps_previous_durable_revision(tmp_path):
    class FailingStore:
        def __init__(self, inner):
            self.inner = inner
            self.fail = False

        def load(self, sid):
            return self.inner.load(sid)

        def save(self, state):
            if self.fail:
                raise RuntimeError("disk on fire")
            return self.inner.save(state)

    inner = FileSessionStore(root=tmp_path)
    store = FailingStore(inner)
    resumer = _resumer(store)
    ok = resumer.resume(_request(), session_context=_context())
    assert ok.recorded_resumption is True

    store.fail = True
    failed = resumer.resume(_request(), session_context=ok.context)
    assert failed.status.value == "FAILED"
    assert failed.recorded_resumption is False
    # durable state keeps the previous committed revision
    durable = SharedSessionDomainAdapter(
        store=FileSessionStore(root=tmp_path)
    ).load_domain_session("sess-prod-1")
    assert durable is not None
    assert durable.revision == ok.resumed_revision


def test_resumer_without_any_persistence_authority_fails_closed():
    resumer = DomainSessionResumer(
        registry=_make_registry(),
        permission_evaluator=lambda a, p: tuple(p),
        operation_filter=lambda p, o: tuple(o),
    )
    result = resumer.resume(_request(), session_context=_context())
    assert result.status.value in ("BLOCKED", "FAILED")
    assert result.recorded_resumption is False
