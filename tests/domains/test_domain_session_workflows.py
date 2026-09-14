"""Phase 10.34 — Domain Session Workflow Reconciliation Tests."""

from __future__ import annotations

from datetime import datetime, timezone

from cmm.domains.contracts import DomainDefinition
from cmm.domains.enums import DomainKind, DomainStatus
from cmm.domains.identifiers import DomainId, DomainManifestId
from cmm.domains.registry import DomainRegistry
from cmm.domains.registry_contracts import DomainRegistryRecord
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
from tests.domains.domain_session_test_support import shared_session_adapter


def _now() -> datetime:
    return datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)


def _setup_registry() -> DomainRegistry:
    reg = DomainRegistry()
    d_health = DomainDefinition(
        id=DomainId(slug="health"),
        name="health",
        display_name="Health Domain",
        version="1.0.0",
        kind=DomainKind.PERSONAL,
        description="Health description",
        manifest_id=DomainManifestId(slug="health", version="1.0.0"),
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
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        active_workflow_refs=("wf:old",),
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        workflow_evaluator=lambda refs: (
            DomainSessionResumeStatus.RESUMED,
            ("wf:migrated",),
            None,
        ),
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    res = resumer.resume(req, ctx)

    assert res.status is DomainSessionResumeStatus.RESUMED
    assert res.context is not None
    assert res.context.active_workflow_refs == ("wf:migrated",)


def test_active_workflow_without_workflow_evaluator_fails_closed():
    """Active workflows without workflow authority must fail closed."""
    reg = _setup_registry()
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        active_workflow_refs=("wf:unverified_active",),
        updated_at=_now(),
    )
    resumer = DomainSessionResumer(
        registry=reg,
        workflow_evaluator=None,
        permission_evaluator=lambda a, p: p,
        operation_filter=lambda p, o: o,
        shared_session_adapter=shared_session_adapter(),
    )
    req = DomainSessionResumeRequest(session_id="session-123")
    res = resumer.resume(req, ctx)

    assert res.status is DomainSessionResumeStatus.BLOCKED
    assert res.recorded_resumption is False
    assert res.context is None
    assert any("workflow authority" in f.lower() for f in res.blocking_findings)


def test_revalidate_workflows_unknown_workflow_fails_closed():
    """Unknown workflow not present in status mapping must be classified UNKNOWN and block."""
    ctx = DomainSessionContext(
        session_id="session-123",
        primary_domain="domain:health",
        active_workflow_refs=("wf:unregistered_ghost",),
        updated_at=_now(),
    )
    checks, active_refs, overall_status = revalidate_workflows(
        ctx, workflow_statuses={}
    )

    assert overall_status is DomainSessionResumeStatus.INCOMPATIBLE
    assert active_refs == ("wf:unregistered_ghost",)
    assert len(checks) == 1
    assert checks[0].status is DomainSessionCheckStatus.INCOMPATIBLE
    assert checks[0].blocking is True
    assert checks[0].details.get("status") == "UNKNOWN"
