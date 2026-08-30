"""Phase 10.34 — Domain Session Questions, Approvals, Conflicts, and Traces Tests."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.session_contracts import (
    DomainSessionCheck,
    DomainSessionCheckStatus,
    DomainSessionContext,
    DomainSessionResumeRequest,
    DomainSessionResumeStatus,
)
from cmm.domains.session_resumer import DomainSessionResumer


def _now() -> datetime:
    return datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


def test_pending_questions_recovery_and_waiting_for_user():
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        pending_domain_question_refs=("q:symptom_onset", "q:prior_conditions"),
        updated_at=_now(),
    )
    # Question evaluator resolves q:prior_conditions as already answered, keeps q:symptom_onset
    resumer = DomainSessionResumer(
        question_evaluator=lambda q_refs: (
            ("q:symptom_onset",),
            ("q:prior_conditions",),
        )
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
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        approval_refs=("appr:medication_purchase", "appr:stale_grant"),
        updated_at=_now(),
    )
    # Approval evaluator keeps pending appr:medication_purchase, drops expired appr:stale_grant
    resumer = DomainSessionResumer(
        approval_evaluator=lambda a_refs: (
            ("appr:medication_purchase",),
            ("appr:stale_grant",),
        )
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.WAITING_FOR_APPROVAL
    assert result.context is not None
    assert result.context.approval_refs == ("appr:medication_purchase",)
    assert result.recovered_approval_refs == ("appr:medication_purchase",)


def test_stale_approval_does_not_become_authorization():
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        approval_refs=("appr:historical_old",),
        available_operation_ids=("op:restricted_health_action",),
        updated_at=_now(),
    )
    # Evaluator drops historical approval
    resumer = DomainSessionResumer(
        approval_evaluator=lambda a_refs: ((), ("appr:historical_old",)),
        operation_filter=lambda perms, ops: (),  # No active approval -> operation removed
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.context is not None
    assert result.context.approval_refs == ()
    assert result.context.available_operation_ids == ()


def test_blocking_conflict_blocks_resumption():
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        domain_conflict_refs=("conf:unresolved_medical_contradiction",),
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
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
        )
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    result = resumer.resume(req, ctx)

    assert result.status is DomainSessionResumeStatus.BLOCKED
    assert result.context is None
    assert any("conflict" in finding.lower() for finding in result.blocking_findings)
