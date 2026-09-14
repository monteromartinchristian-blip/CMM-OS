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
    DomainSessionCheckStatus,
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
    stub_resolver = StubDomainResolver(
        primary_slug="general", resolution_id="res-reresolv-001"
    )
    resumer = DomainSessionResumer(
        registry=reg,
        resolver=stub_resolver,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.RE_RESOLVED
    assert result.context is not None
    assert result.context.primary_domain == "domain:general"
    assert result.context.last_resolution_id == "res-reresolv-001"
    assert len(result.context.domain_transitions) == 1
    transition = result.context.domain_transitions[0]
    assert transition.resolution_id == "res-reresolv-001"
    assert transition.composition_id is not None
    assert len(stub_resolver.invoked_with) == 1


def test_inactive_primary_without_resolver_fails_closed():
    """Fallback callback alone cannot bypass canonical resolver policy."""
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:unregistered",
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        resolver=None,
        fallback_resolver=lambda p, s: "domain:general",
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.BLOCKED
    assert result.recorded_resumption is False
    assert result.context is None
    assert any("canonical resolver" in f.lower() for f in result.blocking_findings)


def test_ambiguous_resolution_fails_closed():
    from cmm.domains.enums import DomainResolutionStatus

    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:unregistered",
        updated_at=_now(),
    )
    stub_resolver = StubDomainResolver(
        primary_slug="general",
        status=DomainResolutionStatus.AMBIGUOUS,
    )
    resumer = DomainSessionResumer(
        registry=reg,
        resolver=stub_resolver,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.BLOCKED
    assert result.recorded_resumption is False
    assert result.context is None


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
    r2 = resumer.resume(req, r1.context)

    assert r1.status == r2.status == DomainSessionResumeStatus.RESUMED
    assert r1.resumed_revision == 2
    assert r2.resumed_revision == 3
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


def test_idempotent_resume_after_accepted_version_drift():
    """First resume accepts 1.1.0 version drift; second resume from updated context reports PASS without drift."""
    reg = _setup_registry()
    # Update health domain to 1.1.0 in registry
    d_health_v11 = DomainDefinition(
        id=DomainId(slug="health"),
        name="health",
        display_name="Health Domain",
        version="1.1.0",
        kind=DomainKind.PERSONAL,
        description="Health description",
        manifest_id=DomainManifestId(slug="health", version="1.1.0"),
    )
    reg.register(d_health_v11)
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_health_v11,
            status=DomainStatus.ACTIVE,
            registered_at=_now(),
            updated_at=_now(),
        )
    )

    ctx = DomainSessionContext(
        session_id="session-drift-1",
        primary_domain="domain:health",
        domain_versions={"domain:health": "1.0.0"},
        revision=1,
        updated_at=_now(),
    )
    adapter = shared_session_adapter()
    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=adapter,
    )
    req = DomainSessionResumeRequest(session_id="session-drift-1")

    # 1. First resume: detects version change 1.0.0 -> 1.1.0, accepts it, and saves updated version in context
    res1 = resumer.resume(req, ctx)
    assert res1.status is DomainSessionResumeStatus.RESUMED
    assert res1.context is not None
    assert res1.context.domain_versions["domain:health"] == "1.1.0"
    v_chk1 = next(c for c in res1.checks if c.name == "domain_version_domain:health")
    assert v_chk1.status is DomainSessionCheckStatus.CHANGED

    # 2. Second resume: starting from the resumed context (which now records 1.1.0)
    res2 = resumer.resume(req, res1.context)
    assert res2.status is DomainSessionResumeStatus.RESUMED
    assert res2.context is not None
    assert res2.context.domain_versions["domain:health"] == "1.1.0"
    v_chk2 = next(c for c in res2.checks if c.name == "domain_version_domain:health")
    assert v_chk2.status is DomainSessionCheckStatus.PASS


def test_drift_invalidates_partial_results_and_traces():
    """Resource/knowledge drift triggers REPLAN_REQUIRED and invalidates partial results/traces."""
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-drift-dep",
        primary_domain="domain:health",
        domain_resource_refs={"domain:health": ("res:vital_signs",)},
        partial_result_refs=("part:heart_rate_analysis",),
        trace_refs=("trace:sensor_ingest_001",),
        next_recommended_step="continue_vital_sign_monitoring",
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
        session_id="session-drift-dep",
        current_resource_versions={"res:vital_signs": "v_drifted"},
    )
    res = resumer.resume(req, ctx)

    assert res.status is DomainSessionResumeStatus.REPLAN_REQUIRED
    assert res.context is not None
    assert res.context.partial_result_refs == ()
    assert res.context.trace_refs == ()
    assert res.context.next_recommended_step == "replan_execution"
    assert any("invalidated" in w.lower() for w in res.warnings)
