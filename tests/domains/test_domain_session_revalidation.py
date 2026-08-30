"""Phase 10.34 — Domain Session Revalidation Tests."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.identifiers import DomainId
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import DomainRegistryRecord
from cmm.domains.session_contracts import (
    DomainSessionCheckStatus,
    DomainSessionContext,
    DomainSessionResumeRequest,
)
from cmm.domains.session_revalidation import (
    revalidate_domains,
    revalidate_resource_and_knowledge_drift,
    revalidate_session_state,
    revalidate_temporal,
)


def _now() -> datetime:
    return datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


def _make_definition(slug: str, version: str = "1.0.0") -> DomainDefinition:
    from cmm.domains.identifiers import DomainManifestId

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
    # Register and activate domain:health (1.0.0) and domain:sport (1.2.0)
    d_health = _make_definition("health", "1.0.0")
    d_sport = _make_definition("sport", "1.2.0")
    reg.register(d_health)
    reg.register(d_sport)
    now = _now()
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_health,
            status=DomainStatus.ACTIVE,
            registered_at=now,
            updated_at=now,
        )
    )
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_sport,
            status=DomainStatus.ACTIVE,
            registered_at=now,
            updated_at=now,
        )
    )
    return reg


def test_revalidate_domains_nominal():
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        supporting_domains=("domain:sport",),
        domain_versions={"domain:health": "1.0.0", "domain:sport": "1.2.0"},
        updated_at=_now(),
    )
    checks = revalidate_domains(ctx, reg)
    assert len(checks) >= 2
    assert all(chk.status is DomainSessionCheckStatus.PASS for chk in checks)
    assert not any(chk.blocking for chk in checks)


def test_revalidate_domains_primary_missing():
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:nonexistent",
        updated_at=_now(),
    )
    checks = revalidate_domains(ctx, reg)
    primary_chk = next(c for c in checks if c.name == "primary_domain_status")
    assert primary_chk.blocking is True
    assert primary_chk.status in (
        DomainSessionCheckStatus.BLOCKING,
        DomainSessionCheckStatus.FAILED,
    )


def test_revalidate_domains_primary_disabled():
    reg = _setup_registry()
    d_disabled = _make_definition("disabled-domain", "1.0.0")
    reg.register(d_disabled)
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_disabled,
            status=DomainStatus.DISABLED,
            registered_at=_now(),
            updated_at=_now(),
        )
    )
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:disabled-domain",
        updated_at=_now(),
    )
    checks = revalidate_domains(ctx, reg)
    primary_chk = next(c for c in checks if c.name == "primary_domain_status")
    assert primary_chk.blocking is True


def test_revalidate_domains_supporting_missing():
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        supporting_domains=("domain:missing_sup",),
        updated_at=_now(),
    )
    checks = revalidate_domains(ctx, reg)
    sup_chk = next(
        c for c in checks if c.name == "supporting_domain_status_domain:missing_sup"
    )
    assert sup_chk.blocking is False
    assert sup_chk.status is DomainSessionCheckStatus.CHANGED


def test_revalidate_domains_compatible_version_drift():
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        domain_versions={"domain:health": "1.0.0"},
        updated_at=_now(),
    )
    # Update registry to 1.1.0 (same major -> compatible)
    d_health_new = _make_definition("health", "1.1.0")
    reg.register(d_health_new)
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_health_new,
            status=DomainStatus.ACTIVE,
            registered_at=_now(),
            updated_at=_now(),
        )
    )
    checks = revalidate_domains(ctx, reg)
    ver_chk = next(c for c in checks if c.name == "domain_version_domain:health")
    assert ver_chk.blocking is False
    assert ver_chk.status in (
        DomainSessionCheckStatus.CHANGED,
        DomainSessionCheckStatus.PASS,
    )


def test_revalidate_domains_incompatible_version_drift():
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        domain_versions={"domain:health": "1.0.0"},
        updated_at=_now(),
    )
    # Update registry to 2.0.0 (breaking major -> incompatible)
    d_health_v2 = _make_definition("health", "2.0.0")
    reg.register(d_health_v2)
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_health_v2,
            status=DomainStatus.ACTIVE,
            registered_at=_now(),
            updated_at=_now(),
        )
    )
    checks = revalidate_domains(ctx, reg)
    ver_chk = next(c for c in checks if c.name == "domain_version_domain:health")
    assert ver_chk.blocking is True
    assert ver_chk.status is DomainSessionCheckStatus.INCOMPATIBLE


def test_revalidate_resource_and_knowledge_drift():
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        domain_resource_refs={"domain:health": ("res:1", "res:2")},
        domain_knowledge_refs={"domain:health": ("know:1",)},
        updated_at=_now(),
    )
    # Nominal request matching versions
    req = DomainSessionResumeRequest(
        session_id="session-123",
        current_resource_versions={"res:1": "v1", "res:2": "v2"},
        current_knowledge_versions={"know:1": "k1"},
    )
    checks = revalidate_resource_and_knowledge_drift(ctx, req)
    assert all(chk.status is DomainSessionCheckStatus.PASS for chk in checks)

    # Drift in resource and missing knowledge
    req_drift = DomainSessionResumeRequest(
        session_id="session-123",
        current_resource_versions={"res:1": "v1_drifted", "res:2": "MISSING"},
        current_knowledge_versions={"know:1": "k1_stale"},
    )
    drift_checks = revalidate_resource_and_knowledge_drift(ctx, req_drift)
    r1_chk = next(c for c in drift_checks if c.name == "resource_drift_res:1")
    r2_chk = next(c for c in drift_checks if c.name == "resource_drift_res:2")
    assert r1_chk.status is DomainSessionCheckStatus.DRIFT
    assert r2_chk.blocking is True


def test_revalidate_temporal():
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        updated_at=_now(),
    )
    req = DomainSessionResumeRequest(
        session_id="session-123",
        temporal_reference=_now(),
    )
    checks = revalidate_temporal(ctx, req)
    assert len(checks) >= 1
    assert checks[0].status is DomainSessionCheckStatus.PASS


def test_revalidate_session_state_orchestration():
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        supporting_domains=("domain:sport",),
        domain_versions={"domain:health": "1.0.0", "domain:sport": "1.2.0"},
        domain_resource_refs={"domain:health": ("res:1",)},
        updated_at=_now(),
    )
    req = DomainSessionResumeRequest(
        session_id="session-123",
        temporal_reference=_now(),
        current_resource_versions={"res:1": "v1"},
    )
    all_checks = revalidate_session_state(ctx, reg, req)
    assert len(all_checks) >= 3
    assert not any(chk.blocking for chk in all_checks)
