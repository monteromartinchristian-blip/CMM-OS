"""Phase 10.34 — Domain Session Permission & Operation Re-evaluation Tests."""

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
    DomainSessionResumeStatus,
)
from cmm.domains.session_resumer import DomainSessionResumer


def _now() -> datetime:
    return datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


def _make_definition(
    slug: str,
    version: str = "1.0.0",
    operations: tuple[str, ...] = (),
    permissions: tuple[str, ...] = (),
) -> DomainDefinition:
    return DomainDefinition(
        id=DomainId(slug=slug),
        name=slug,
        display_name=f"Domain {slug}",
        version=version,
        kind=DomainKind.PERSONAL,
        description=f"Description for {slug}",
        manifest_id=DomainManifestId(slug=slug, version=version),
        operations=operations,
        permissions=permissions,
    )


def _setup_registry_with_ops() -> DomainRegistry:
    reg = DomainRegistry()
    d_health = _make_definition(
        "health",
        "1.0.0",
        operations=("op:log_symptom", "op:prescribe_medication"),
        permissions=("perm:health_read", "perm:health_write"),
    )
    reg.register(d_health)
    now = _now()
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_health,
            status=DomainStatus.ACTIVE,
            registered_at=now,
            updated_at=now,
        )
    )
    return reg


def test_persisted_permission_downgrade_removes_unauthorized_operation():
    reg = _setup_registry_with_ops()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        effective_permission_refs=("perm:health_read", "perm:health_write"),
        available_operation_ids=("op:log_symptom", "op:prescribe_medication"),
        updated_at=_now(),
    )
    # Actor only has read permission
    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda actor, perms: ("perm:health_read",),
        operation_filter=lambda perms, ops: tuple(
            op for op in ops if op != "op:prescribe_medication"
        ),
        persistence_updater=lambda c: None,
    )
    req = DomainSessionResumeRequest(session_id="session-123", actor="user-1")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.RESUMED
    assert result.context is not None
    assert "op:prescribe_medication" not in result.context.available_operation_ids
    assert "op:log_symptom" in result.context.available_operation_ids
    assert result.context.effective_permission_refs == ("perm:health_read",)


def test_persisted_permission_never_authorizes_without_reevaluation():
    reg = _setup_registry_with_ops()
    # Old snapshot claimed admin / write
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        effective_permission_refs=("perm:admin_all",),
        available_operation_ids=("op:prescribe_medication",),
        updated_at=_now(),
    )
    # Current evaluator denies all
    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda actor, perms: (),
        operation_filter=lambda perms, ops: (),
        persistence_updater=lambda c: None,
    )
    req = DomainSessionResumeRequest(session_id="session-123", actor="untrusted")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.RESUMED
    assert result.context is not None
    assert result.context.effective_permission_refs == ()
    assert result.context.available_operation_ids == ()
