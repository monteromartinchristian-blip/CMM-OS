"""Phase 10.34 — AT-DP-034 Acceptance Gate Tests.

Comprehensive end-to-end acceptance suite verifying all functional, architectural,
and security checkpoints of Phase 10.34 Domain Sessions.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.errors import (
    DomainSessionContractError,
    DomainSessionSecurityError,
)
from cmm.domains.event_catalog import (
    CANONICAL_DOMAIN_EVENTS,
    CANONICAL_DOMAIN_EVENTS_SET,
)
from cmm.domains.identifiers import DomainId, DomainManifestId
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import DomainRegistryRecord
from cmm.domains.session_codec import (
    DomainSessionCodec,
)
from cmm.domains.session_contracts import (
    DOMAIN_SESSION_SCHEMA_VERSION,
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


def _setup_acceptance_registry() -> DomainRegistry:
    reg = DomainRegistry()
    d_health = _make_definition(
        "health",
        "1.0.0",
        operations=("op:health_read", "op:health_write"),
        permissions=("perm:health_read", "perm:health_write"),
    )
    d_fitness = _make_definition(
        "fitness",
        "1.2.0",
        operations=("op:log_workout",),
        permissions=("perm:fitness_write",),
    )
    d_general = _make_definition("general", "1.0.0")
    for d in (d_health, d_fitness, d_general):
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


# ── Checkpoint 1 & 2: Shared Phase 8 Session Extension & Codec ────────────────


def test_checkpoint_shared_session_extension_codec():
    codec = DomainSessionCodec()
    ctx = DomainSessionContext(
        session_id="session-001",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        domain_versions={"domain:health": "1.0.0", "domain:fitness": "1.2.0"},
        effective_profile="health_profile_v1",
        effective_rule_ids=("rule:health_guidelines",),
        effective_permission_refs=("perm:health_read",),
        active_workflow_refs=("wf:daily_log",),
        available_operation_ids=("op:health_read",),
        domain_resource_refs={"domain:health": ("res:ehr_1",)},
        domain_knowledge_refs={"domain:health": ("know:guidelines_1",)},
        pending_domain_question_refs=("q:symptom_onset",),
        domain_conflict_refs=(),
        approval_refs=("appr:data_export",),
        partial_result_refs=("part:prelim_analysis",),
        trace_refs=("trace:step_1",),
        revision=1,
        updated_at=_now(),
    )

    # Attach to shared session envelope
    envelope = {"session_id": "session-001", "metadata": {}}
    attached = codec.attach_to_session(envelope, ctx)
    assert codec.is_domain_session_attached(attached)

    # Extract round-trip
    extracted = codec.extract_from_session(attached)
    assert extracted is not None
    assert extracted.session_id == ctx.session_id
    assert extracted.primary_domain == ctx.primary_domain
    assert extracted.supporting_domains == ctx.supporting_domains
    assert extracted.revision == ctx.revision
    assert extracted.domain_resource_refs == ctx.domain_resource_refs
    assert extracted.domain_knowledge_refs == ctx.domain_knowledge_refs


# ── Checkpoint 3-10: State Integrity & Strict Invariants ──────────────────────


def test_checkpoint_state_integrity_and_invariants():
    ctx = DomainSessionContext(
        session_id="session-002",
        primary_domain="domain:health",
        domain_versions={"domain:health": "1.0.0"},
        updated_at=_now(),
    )

    # Immutability
    with pytest.raises((AttributeError, TypeError)):
        ctx.primary_domain = "domain:other"  # type: ignore

    # Revision must be positive integer >= 1
    with pytest.raises(DomainSessionContractError):
        DomainSessionContext(
            session_id="s",
            primary_domain="domain:health",
            revision=0,
            updated_at=_now(),
        )

    # Schema version
    assert DOMAIN_SESSION_SCHEMA_VERSION == 1
    d = ctx.to_dict()
    assert d["schema_version"] == 1


# ── Checkpoint 11-22: Credential Rejection & Security Boundary ────────────────


def test_checkpoint_credential_rejection_vectors():
    # Attempt credential vectors across context, request, and checks
    with pytest.raises(DomainSessionSecurityError):
        DomainSessionContext(
            session_id="session-003",
            primary_domain="domain:health",
            metadata={"api_token": "sk-ant-api03-abcdefghijklmnopqrstuvwxyz1234567890"},
            updated_at=_now(),
        )

    with pytest.raises(DomainSessionSecurityError):
        DomainSessionResumeRequest(
            session_id="session-003",
            metadata={"secret": "ghp_123456789012345678901234567890123456"},
        )


# ── Checkpoint 23-30: Revalidation, Drift & Permission Re-evaluation ──────────


def test_checkpoint_revalidation_drift_and_permission_reevaluation():
    reg = _setup_acceptance_registry()
    ctx = DomainSessionContext(
        session_id="session-004",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        domain_versions={"domain:health": "1.0.0", "domain:fitness": "1.2.0"},
        effective_permission_refs=("perm:health_read", "perm:health_write"),
        available_operation_ids=("op:health_read", "op:health_write"),
        domain_resource_refs={"domain:health": ("res:ehr_1",)},
        updated_at=_now(),
    )

    # Actor has read-only permission now
    resumer = DomainSessionResumer(
        registry=reg,
        permission_evaluator=lambda actor, perms: ("perm:health_read",),
        operation_filter=lambda perms, ops: ("op:health_read",),
    )
    req = DomainSessionResumeRequest(
        session_id="session-004",
        actor="user_readonly",
        current_resource_versions={"res:ehr_1": "v1_current"},
    )
    res = resumer.resume(req, ctx)

    assert res.status is DomainSessionResumeStatus.RESUMED
    assert res.context is not None
    # Stale write permission is stripped; write operation is stripped
    assert res.context.effective_permission_refs == ("perm:health_read",)
    assert res.context.available_operation_ids == ("op:health_read",)
    assert res.previous_revision == 1
    assert res.resumed_revision == 2


# ── Checkpoint 31-36: Recomposition, Re-resolution & Fail-Closed Blocking ─────


def test_checkpoint_recomposition_on_disabled_supporting_domain():
    reg = _setup_acceptance_registry()
    # Disable fitness domain
    d_fitness = _make_definition("fitness", "1.2.0")
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_fitness,
            status=DomainStatus.DISABLED,
            registered_at=_now(),
            updated_at=_now(),
        )
    )

    ctx = DomainSessionContext(
        session_id="session-005",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(registry=reg)
    req = DomainSessionResumeRequest(session_id="session-005")
    res = resumer.resume(req, ctx)

    assert res.status is DomainSessionResumeStatus.RECOMPOSED
    assert res.context is not None
    assert res.context.supporting_domains == ()
    assert len(res.context.domain_transitions) == 1
    assert (
        res.context.domain_transitions[0].reason_code
        == "RECOMPOSITION_SUPPORTING_DISABLED"
    )


def test_checkpoint_blocking_incompatibility_fails_closed():
    reg = _setup_acceptance_registry()
    ctx = DomainSessionContext(
        session_id="session-006",
        primary_domain="domain:health",
        domain_resource_refs={"domain:health": ("res:vital_chart",)},
        updated_at=_now(),
    )
    req = DomainSessionResumeRequest(
        session_id="session-006",
        current_resource_versions={"res:vital_chart": "INVALIDATED"},
    )
    resumer = DomainSessionResumer(registry=reg)
    res = resumer.resume(req, ctx)

    assert res.status is DomainSessionResumeStatus.BLOCKED
    assert res.context is None
    assert len(res.blocking_findings) >= 1
    assert res.recorded_resumption is False


# ── Checkpoint 37-45: Idempotency, Atomicity & Failure Recovery ────────────────


def test_checkpoint_idempotency_and_atomicity():
    reg = _setup_acceptance_registry()
    ctx = DomainSessionContext(
        session_id="session-007",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        domain_versions={"domain:health": "1.0.0", "domain:fitness": "1.2.0"},
        revision=5,
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(registry=reg)
    req = DomainSessionResumeRequest(
        session_id="session-007",
        temporal_reference=_now(),
    )

    # Resume 1
    r1 = resumer.resume(req, ctx)
    # Resume 2
    r2 = resumer.resume(req, ctx)

    assert r1.status == r2.status == DomainSessionResumeStatus.RESUMED
    assert r1.resumed_revision == r2.resumed_revision == 6
    assert r1.context is not None and r2.context is not None
    assert r1.context.primary_domain == r2.context.primary_domain
    assert r1.context.supporting_domains == r2.context.supporting_domains
    assert len(r1.context.domain_transitions) == len(r2.context.domain_transitions)


# ── Checkpoint 46-56: Event Catalog Exactness & Import Cleanliness ─────────────


def test_checkpoint_event_catalog_and_import_cleanliness():
    assert len(CANONICAL_DOMAIN_EVENTS) == 23
    assert len(CANONICAL_DOMAIN_EVENTS_SET) == 23
    assert "domain.session.resumed" not in CANONICAL_DOMAIN_EVENTS_SET

    # No forbidden repository or event bus symbols
    import cmm.domains as dom

    for banned in (
        "DomainSessionRepository",
        "AgentRuntimeEventBus",
        "DomainEventStore",
        "DomainEventQueue",
        "DomainEventDLQ",
    ):
        assert not hasattr(dom, banned)
