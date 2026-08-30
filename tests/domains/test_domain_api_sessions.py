"""Phase 10.36 — Domain API session tests.

Proves shared-session lookup through SharedSessionDomainAdapter and fail-closed
resumption through DomainSessionResumer. No session enumeration is exposed.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.api import DefaultDomainAPI
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
from cmm.runtime.sessions import InMemorySessionStore
from tests.domains.test_domain_api_contracts import _make_collaborators


def _now() -> datetime:
    return datetime(2026, 8, 31, 10, 0, 0, tzinfo=timezone.utc)


def _definition(slug: str) -> DomainDefinition:
    return DomainDefinition(
        id=DomainId(slug=slug),
        name=slug,
        display_name=f"Domain {slug}",
        version="1.0.0",
        kind=DomainKind.PERSONAL,
        description=f"Description for {slug}",
        manifest_id=DomainManifestId(slug=slug, version="1.0.0"),
    )


def _active_registry() -> DomainRegistry:
    registry = DomainRegistry()
    for slug in ("general", "health"):
        definition = _definition(slug)
        registry.register(definition)
        registry.restore_record(
            DomainRegistryRecord(
                definition=definition,
                status=DomainStatus.ACTIVE,
                registered_at=_now(),
                updated_at=_now(),
            )
        )
    return registry


def _context(session_id: str = "sess-api-1") -> DomainSessionContext:
    return DomainSessionContext(
        session_id=session_id,
        primary_domain="domain:general",
        domain_versions={"domain:general": "1.0.0"},
        revision=3,
        updated_at=_now(),
    )


def _resumer(store: InMemorySessionStore) -> DomainSessionResumer:
    return DomainSessionResumer(
        registry=_active_registry(),
        permission_evaluator=lambda a, p: tuple(p),
        operation_filter=lambda p, o: tuple(o),
        shared_session_adapter=SharedSessionDomainAdapter(store=store),
    )


def _api_with_sessions(
    store: InMemorySessionStore,
) -> tuple[DefaultDomainAPI, SharedSessionDomainAdapter]:
    collaborators = _make_collaborators()
    adapter = SharedSessionDomainAdapter(store=store)
    collaborators["session_adapter"] = adapter
    collaborators["session_resumer"] = _resumer(store)
    return DefaultDomainAPI(**collaborators), adapter


class TestGetSession:
    def test_loads_through_shared_adapter(self) -> None:
        store = InMemorySessionStore()
        api, adapter = _api_with_sessions(store)
        adapter.save_domain_session(_context())
        assert api.get_session("sess-api-1") == adapter.load_domain_session(
            "sess-api-1"
        )
        assert api.get_session("sess-api-1") is not None
        assert api.get_session("sess-api-1").primary_domain == "domain:general"

    def test_missing_session_returns_none_and_creates_nothing(self) -> None:
        store = InMemorySessionStore()
        api, adapter = _api_with_sessions(store)
        assert api.get_session("missing") is None
        assert adapter.load_shared_session("missing") is None
        assert store.load("missing") is None

    def test_no_session_enumeration_api_exists(self) -> None:
        store = InMemorySessionStore()
        api, _ = _api_with_sessions(store)
        assert not hasattr(api, "list_all_domain_sessions")
        assert not hasattr(api, "search_domain_sessions")
        assert not hasattr(type(api), "list_all_domain_sessions")
        assert not hasattr(type(api), "search_domain_sessions")


class TestResumeSession:
    def test_resume_delegates_to_resumer(self) -> None:
        store = InMemorySessionStore()
        api, adapter = _api_with_sessions(store)
        adapter.save_domain_session(_context())
        request = DomainSessionResumeRequest(
            session_id="sess-api-1", actor="user:chris"
        )
        result = api.resume_session(request)
        assert result.status.value == "RESUMED"
        assert result.recorded_resumption is True

    def test_resume_revalidates_current_state(self) -> None:
        store = InMemorySessionStore()
        api, adapter = _api_with_sessions(store)
        # Persisted snapshot references a domain that is not active in the
        # current registry -> resumption must fail closed.
        stale = DomainSessionContext(
            session_id="sess-stale",
            primary_domain="domain:missing-domain",
            domain_versions={"domain:missing-domain": "1.0.0"},
            revision=1,
            updated_at=_now(),
        )
        adapter.save_domain_session(stale)
        request = DomainSessionResumeRequest(
            session_id="sess-stale", actor="user:chris"
        )
        result = api.resume_session(request)
        assert result.status.value != "RESUMED"

    def test_resume_missing_session_fails_closed(self) -> None:
        from cmm.domains.errors import DomainSessionResumeError

        store = InMemorySessionStore()
        api, _ = _api_with_sessions(store)
        request = DomainSessionResumeRequest(
            session_id="never-existed", actor="user:chris"
        )
        # Canonical resumer fails closed with its own error type.
        with pytest.raises(DomainSessionResumeError):
            api.resume_session(request)
