"""Phase 10.34 — Domain Session Questions, Approvals, Conflicts, and Traces Tests."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.identifiers import DomainId, DomainManifestId
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import DomainRegistryRecord
from cmm.domains.session_contracts import (
    DomainSessionCheck,
    DomainSessionCheckStatus,
    DomainSessionContext,
    DomainSessionResumeRequest,
    DomainSessionResumeStatus,
)
from cmm.domains.session_resumer import DomainSessionResumer
from tests.domains.domain_session_test_support import shared_session_adapter


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


def test_pending_questions_recovery_and_waiting_for_user():
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        pending_domain_question_refs=("q:symptom_onset", "q:prior_conditions"),
        updated_at=_now(),
    )
    # Question evaluator resolves q:prior_conditions as already answered, keeps q:symptom_onset
    resumer = DomainSessionResumer(
        registry=reg,
        question_evaluator=lambda q_refs: (
            ("q:symptom_onset",),
            ("q:prior_conditions",),
        ),
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.WAITING_FOR_USER
    assert result.context is not None
    assert result.context.pending_domain_question_refs == ("q:symptom_onset",)
    assert result.recovered_question_refs == ("q:symptom_onset",)
    assert len(result.warnings) == 1
    assert "q:prior_conditions" not in result.context.pending_domain_question_refs


def test_pending_approvals_recovery_and_waiting_for_approval():
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        approval_refs=("appr:medication_purchase", "appr:stale_grant"),
        updated_at=_now(),
    )
    # Approval evaluator keeps pending appr:medication_purchase, drops expired appr:stale_grant
    resumer = DomainSessionResumer(
        registry=reg,
        approval_evaluator=lambda a_refs: (
            ("appr:medication_purchase",),
            ("appr:stale_grant",),
        ),
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.WAITING_FOR_APPROVAL
    assert result.context is not None
    assert result.context.approval_refs == ("appr:medication_purchase",)
    assert result.recovered_approval_refs == ("appr:medication_purchase",)


def test_stale_approval_does_not_become_authorization():
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        approval_refs=("appr:historical_old",),
        available_operation_ids=("op:restricted_health_action",),
        updated_at=_now(),
    )
    # Evaluator drops historical approval
    resumer = DomainSessionResumer(
        registry=reg,
        approval_evaluator=lambda a_refs: ((), ("appr:historical_old",)),
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda perms, ops: (),  # No active approval -> operation removed
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.context is not None
    assert result.context.approval_refs == ()
    assert result.context.available_operation_ids == ()


def test_blocking_conflict_blocks_resumption():
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        domain_conflict_refs=("conf:unresolved_medical_contradiction",),
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        # Conflict checker detects unresolved blocking conflict
        conflict_evaluator=lambda conf_refs: (
            DomainSessionResumeStatus.BLOCKED,
            (
                DomainSessionCheck(
                    name="domain_conflict_check",
                    status=DomainSessionCheckStatus.BLOCKING,
                    message="Unresolved blocking conflict in health domain",
                    blocking=True,
                ),
            ),
        ),
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.BLOCKED
    assert result.context is None
    assert any("conflict" in finding.lower() for finding in result.blocking_findings)


def test_pending_questions_without_evaluator_fails_closed():
    """Pending questions without question authority must fail closed."""
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        pending_domain_question_refs=("q:unverified_question",),
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        question_evaluator=None,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.BLOCKED
    assert result.recorded_resumption is False
    assert result.context is None
    assert any("question authority" in f.lower() for f in result.blocking_findings)


def test_pending_approvals_without_evaluator_fails_closed():
    """Pending approvals without approval authority must fail closed."""
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        approval_refs=("appr:unverified_approval",),
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        approval_evaluator=None,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.BLOCKED
    assert result.recorded_resumption is False
    assert result.context is None
    assert any("approval authority" in f.lower() for f in result.blocking_findings)


def test_conflict_refs_without_evaluator_fails_closed():
    """Conflict references without conflict authority must fail closed."""
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        domain_conflict_refs=("conf:unverified",),
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        conflict_evaluator=None,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.BLOCKED
    assert result.recorded_resumption is False
    assert result.context is None
    assert any("conflict authority" in f.lower() for f in result.blocking_findings)


def test_material_recomposition_drops_questions_for_removed_domain():
    """Material recomposition must re-evaluate questions and drop questions of removed domains."""
    reg = _setup_registry()
    d_fitness = _make_definition("fitness", "1.0.0")
    reg.register(d_fitness)
    # Disable fitness domain
    reg.restore_record(
        DomainRegistryRecord(
            definition=d_fitness,
            status=DomainStatus.DISABLED,
            registered_at=_now(),
            updated_at=_now(),
        )
    )
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        supporting_domains=("domain:fitness",),
        pending_domain_question_refs=("q:health_symptoms", "q:fitness_intensity"),
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        question_evaluator=lambda q_refs: (q_refs, ()),
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.WAITING_FOR_USER
    assert result.context is not None
    assert "q:fitness_intensity" not in result.context.pending_domain_question_refs
    assert result.context.pending_domain_question_refs == ("q:health_symptoms",)
    assert any("dropped" in w.lower() for w in result.warnings)
