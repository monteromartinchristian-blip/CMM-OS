"""Phase 10.34 — Domain Session Event Integration Tests."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.event_catalog import CANONICAL_DOMAIN_EVENTS
from cmm.domains.event_publisher import DomainKernelEventPublisher
from cmm.domains.identifiers import DomainId, DomainManifestId
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import DomainRegistryRecord
from cmm.domains.session_contracts import (
    DomainSessionContext,
    DomainSessionResumeRequest,
    DomainSessionResumeStatus,
)
from cmm.domains.session_resumer import DomainSessionResumer
from tests.domains.domain_session_test_support import (
    StubDomainResolver,
    failing_shared_session_adapter,
    shared_session_adapter,
)


def _now() -> datetime:
    return datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


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


def _setup_registry() -> DomainRegistry:
    reg = DomainRegistry()
    d_health = _make_definition("health", "1.0.0")
    d_sport = _make_definition("sport", "1.2.0")
    d_general = _make_definition("general", "1.0.0")
    reg.register(d_health)
    reg.register(d_sport)
    reg.register(d_general)
    now = _now()
    for d in (d_health, d_sport, d_general):
        reg.restore_record(
            DomainRegistryRecord(
                definition=d,
                status=DomainStatus.ACTIVE,
                registered_at=now,
                updated_at=now,
            )
        )
    return reg


def test_canonical_catalog_remains_exact_23():
    assert len(CANONICAL_DOMAIN_EVENTS) == 23
    assert len(set(CANONICAL_DOMAIN_EVENTS)) == 23
    assert "domain.session.resumed" not in CANONICAL_DOMAIN_EVENTS


def test_nominal_resume_emits_no_invented_event():
    reg = _setup_registry()
    published_events = []
    publisher = DomainKernelEventPublisher(
        event_listener=lambda evt: published_events.append(evt)
    )

    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        supporting_domains=("domain:sport",),
        domain_versions={"domain:health": "1.0.0", "domain:sport": "1.2.0"},
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        event_publisher=publisher,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.RESUMED
    # Mere resume should not emit any event
    assert len(published_events) == 0


def test_re_resolution_emits_resolution_completed_event():
    reg = _setup_registry()
    published_events = []
    publisher = DomainKernelEventPublisher(
        event_listener=lambda evt: published_events.append(evt)
    )

    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:missing_old",
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        resolver=StubDomainResolver(primary_slug="general"),
        event_publisher=publisher,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.RE_RESOLVED
    assert len(published_events) == 1
    assert published_events[0].name == "domain.resolution.completed"


def test_recomposition_emits_composition_updated_event():
    reg = _setup_registry()
    # Disable sport domain
    d_sport = _make_definition("sport", "1.2.0")
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_sport,
            status=DomainStatus.DISABLED,
            registered_at=_now(),
            updated_at=_now(),
        )
    )
    published_events = []
    publisher = DomainKernelEventPublisher(
        event_listener=lambda evt: published_events.append(evt)
    )

    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        supporting_domains=("domain:sport",),
        domain_versions={"domain:health": "1.0.0", "domain:sport": "1.2.0"},
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        event_publisher=publisher,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.RECOMPOSED
    assert len(published_events) == 1
    assert published_events[0].name == "domain.composition.updated"


def test_persistence_failure_prevents_event_emission():
    reg = _setup_registry()
    published_events = []
    publisher = DomainKernelEventPublisher(
        event_listener=lambda evt: published_events.append(evt)
    )

    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:missing_old",
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        resolver=StubDomainResolver(primary_slug="general"),
        event_publisher=publisher,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=failing_shared_session_adapter(RuntimeError("DB dead")),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.FAILED
    assert len(published_events) == 0
