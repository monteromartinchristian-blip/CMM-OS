"""Phase 10.34 — Domain Session Resumer Tests."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.identifiers import DomainId, DomainManifestId
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import DomainRegistryRecord
from cmm.domains.session_codec import DomainSessionCodec
from cmm.domains.session_contracts import (
    DomainSessionContext,
    DomainSessionResumeRequest,
    DomainSessionResumeStatus,
)
from cmm.domains.session_resumer import DomainSessionResumer
from tests.domains.domain_session_test_support import (
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


def test_nominal_resume():
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        supporting_domains=("domain:sport",),
        domain_versions={"domain:health": "1.0.0", "domain:sport": "1.2.0"},
        effective_profile="health_profile",
        revision=1,
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.RESUMED
    assert result.session_id == "session-123"
    assert result.previous_revision == 1
    assert result.resumed_revision == 2
    assert result.recorded_resumption is True
    assert result.context is not None
    assert result.context.primary_domain == "domain:health"
    assert result.context.supporting_domains == ("domain:sport",)
    assert result.context.revision == 2


def test_resume_with_dict_payload_via_codec():
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        revision=3,
        updated_at=_now(),
    )
    codec = DomainSessionCodec()
    session_envelope = {"id": "session-123", "domain_session": ctx.to_dict()}

    resumer = DomainSessionResumer(
        registry=reg,
        codec=codec,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, session_envelope)

    assert result.status is DomainSessionResumeStatus.RESUMED
    assert result.previous_revision == 3
    assert result.resumed_revision == 4
    assert result.context is not None


def test_recomposition_when_supporting_domain_disabled():
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
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        supporting_domains=("domain:sport",),
        domain_versions={"domain:health": "1.0.0", "domain:sport": "1.2.0"},
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.RECOMPOSED
    assert result.context is not None
    assert result.context.supporting_domains == ()
    assert len(result.context.domain_transitions) == 1
    assert (
        result.context.domain_transitions[0].reason_code
        == "RECOMPOSITION_SUPPORTING_DISABLED"
    )


def test_re_resolution_when_primary_domain_missing():
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:unregistered",
        updated_at=_now(),
    )
    # Resolver that falls back safely to general domain
    resumer = DomainSessionResumer(
        registry=reg,
        fallback_resolver=lambda primary, supporting: "domain:general",
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.RE_RESOLVED
    assert result.context is not None
    assert result.context.primary_domain == "domain:general"
    assert len(result.context.domain_transitions) == 1


def test_blocking_check_fails_closed():
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        domain_resource_refs={"domain:health": ("res:1",)},
        updated_at=_now(),
    )
    req = DomainSessionResumeRequest(
        session_id="session-123",
        current_resource_versions={"res:1": "MISSING"},
    )
    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.BLOCKED
    assert result.context is None
    assert len(result.blocking_findings) >= 1
    assert result.recorded_resumption is False


def test_persistence_failure_rollback():
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        revision=2,
        updated_at=_now(),
    )

    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=failing_shared_session_adapter(
            RuntimeError("Database connection failure")
        ),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.FAILED
    assert result.context is None
    assert result.recorded_resumption is False
    assert result.resumed_revision == 2


def test_idempotent_resume():
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        supporting_domains=("domain:sport",),
        domain_versions={"domain:health": "1.0.0", "domain:sport": "1.2.0"},
        revision=1,
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(
        session_id="session-123",
        temporal_reference=_now(),
    )
    r1 = resumer.resume(req, ctx)
    r2 = resumer.resume(req, ctx)

    assert r1.status == r2.status
    assert r1.resumed_revision == r2.resumed_revision
    assert r1.context is not None and r2.context is not None
    assert r1.context.primary_domain == r2.context.primary_domain
    assert r1.context.supporting_domains == r2.context.supporting_domains
    assert len(r1.context.domain_transitions) == len(r2.context.domain_transitions)


def test_retry_after_failed_persistence_does_not_skip_revision():
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        revision=2,
        updated_at=_now(),
    )

    resumer_failing = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=failing_shared_session_adapter(
            RuntimeError("Transient DB glitch")
        ),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    res1 = resumer_failing.resume(req, ctx)
    assert res1.status is DomainSessionResumeStatus.FAILED
    assert res1.resumed_revision == 2

    # Retry through a healthy authoritative shared store.
    adapter = shared_session_adapter()
    resumer_ok = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=adapter,
    )
    res2 = resumer_ok.resume(req, ctx)
    assert res2.status is DomainSessionResumeStatus.RESUMED
    assert res2.resumed_revision == 3

    persisted = adapter.load_domain_session("session-123")
    assert persisted is not None
    assert persisted.revision == 3
