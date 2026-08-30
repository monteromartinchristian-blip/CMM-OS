"""Phase 10.34 — Domain Session Workflow Reconciliation Tests."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.session_contracts import (
    DomainSessionCheckStatus,
    DomainSessionContext,
    DomainSessionResumeRequest,
    DomainSessionResumeStatus,
)
from cmm.domains.session_resumer import DomainSessionResumer
from cmm.domains.session_revalidation import (
    DomainWorkflowClassification,
    revalidate_workflows,
)


def _now() -> datetime:
    return datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


def test_revalidate_workflows_nominal_current():
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        active_workflow_refs=("wf:workout_plan",),
        updated_at=_now(),
    )
    statuses = {"wf:workout_plan": DomainWorkflowClassification.CURRENT.value}
    checks, active_refs, overall_status = revalidate_workflows(ctx, statuses)

    assert active_refs == ("wf:workout_plan",)
    assert overall_status is None
    assert len(checks) == 1
    assert checks[0].status is DomainSessionCheckStatus.PASS


def test_revalidate_workflows_migrated():
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        active_workflow_refs=("wf:old_plan_v1",),
        updated_at=_now(),
    )
    statuses = {"wf:old_plan_v1": "MIGRATED"}
    migrations = {"wf:old_plan_v1": "wf:new_plan_v2"}
    checks, active_refs, _ = revalidate_workflows(ctx, statuses, migrations)

    assert active_refs == ("wf:new_plan_v2",)
    assert len(checks) == 1
    assert checks[0].status is DomainSessionCheckStatus.CHANGED


def test_revalidate_workflows_completed_and_cancelled_retired():
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        active_workflow_refs=("wf:done", "wf:aborted", "wf:active"),
        updated_at=_now(),
    )
    statuses = {
        "wf:done": "COMPLETED",
        "wf:aborted": "CANCELLED",
        "wf:active": "CURRENT",
    }
    checks, active_refs, _ = revalidate_workflows(ctx, statuses)

    assert active_refs == ("wf:active",)
    assert len(checks) == 3


def test_revalidate_workflows_replan_required():
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        active_workflow_refs=("wf:drifted_plan",),
        updated_at=_now(),
    )
    statuses = {"wf:drifted_plan": "REPLAN_REQUIRED"}
    _, active_refs, overall_status = revalidate_workflows(ctx, statuses)

    assert overall_status is DomainSessionResumeStatus.REPLAN_REQUIRED
    assert active_refs == ("wf:drifted_plan",)


def test_revalidate_workflows_incompatible_or_missing_blocks():
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        active_workflow_refs=("wf:incompatible",),
        updated_at=_now(),
    )
    statuses = {"wf:incompatible": "INCOMPATIBLE"}
    checks, _, overall_status = revalidate_workflows(ctx, statuses)

    assert overall_status is DomainSessionResumeStatus.INCOMPATIBLE
    assert any(c.blocking for c in checks)


def test_resumer_integrates_workflow_reconciliation():
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        active_workflow_refs=("wf:old",),
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        workflow_evaluator=lambda refs: (
            DomainSessionResumeStatus.RESUMED,
            ("wf:migrated",),
            None,
        )
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    res = resumer.resume(req, ctx)

    assert res.status is DomainSessionResumeStatus.RESUMED
    assert res.context is not None
    assert res.context.active_workflow_refs == ("wf:migrated",)
