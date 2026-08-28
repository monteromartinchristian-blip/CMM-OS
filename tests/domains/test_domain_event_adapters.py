"""Phase 10.33 — Domain Event Adapters Tests.

Tests covering:
- Resolution lifecycle adapter (started, completed, ambiguous)
- Composition lifecycle adapter (created, updated, rejection of identical recomputation)
- Execution lifecycle adapter (started, completed, failed)
- Conflict lifecycle adapter (detected, resolved)
- Critical invariant: unresolved conflict outcomes NEVER emit domain.conflict.resolved
- Permission lifecycle adapter (requested, denied)
- Approval lifecycle adapter (requested, received)
- Memory lifecycle adapter (proposed vs updated distinction)
- Workflow lifecycle adapter (started, paused, resumed, completed)
- Operation lifecycle adapter (started, completed, failed)
"""

from __future__ import annotations

from cmm.domains.composition_contracts import DomainComposition, DomainCompositionStatus
from cmm.domains.conflict_resolution_contracts import (
    DomainConflictAuthority,
    DomainConflictCase,
    DomainConflictKind,
    DomainConflictReasonCode,
    DomainConflictReference,
    DomainConflictResolution,
    DomainConflictSeverity,
    DomainConflictSourceKind,
    DomainConflictStatus,
    DomainConflictStrategy,
)
from cmm.domains.enums import DomainResolutionStatus
from cmm.domains.event_adapters import (
    adapt_approval_received,
    adapt_approval_requested,
    adapt_composition_created,
    adapt_composition_updated,
    adapt_conflict_detected,
    adapt_conflict_resolution,
    adapt_execution_completed,
    adapt_execution_failed,
    adapt_execution_started,
    adapt_memory_proposed,
    adapt_memory_updated,
    adapt_operation_completed,
    adapt_operation_failed,
    adapt_operation_started,
    adapt_permission_denied,
    adapt_permission_requested,
    adapt_resolution_result,
    adapt_resolution_started,
    adapt_workflow_completed,
    adapt_workflow_paused,
    adapt_workflow_resumed,
    adapt_workflow_started,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.resolver_contracts import DomainResolutionResult


def _make_conflict_ref(source_id: str = "ref-1") -> DomainConflictReference:
    return DomainConflictReference(
        source_kind=DomainConflictSourceKind.DOMAIN_SPECIFIC_CONFLICT,
        source_id=source_id,
        domain_id=DomainId(slug="health"),
        blocking=False,
        severity=DomainConflictSeverity.MATERIAL,
        authority_kind=DomainConflictAuthority.UNCLASSIFIED,
    )


# 1. Resolution
def test_adapt_resolution_started() -> None:
    evt = adapt_resolution_started(
        context_id="ctx-100",
        actor="system",
        domain_id=DomainId(slug="project"),
    )
    assert evt.event_type == "domain.resolution.started"
    assert evt.payload["context_id"] == "ctx-100"


def test_adapt_resolution_result_resolved() -> None:
    res = DomainResolutionResult(
        id="res-1",
        context_id="ctx-100",
        status=DomainResolutionStatus.RESOLVED,
        primary_domain=DomainId(slug="project"),
        confidence=0.95,
    )
    evt = adapt_resolution_result(res, actor="system")
    assert evt.event_type == "domain.resolution.completed"
    assert evt.domain_id == DomainId(slug="project")
    assert evt.payload["status"] == "resolved"
    assert evt.payload["confidence"] == 0.95


def test_adapt_resolution_result_ambiguous() -> None:
    res = DomainResolutionResult(
        id="res-2",
        context_id="ctx-101",
        status=DomainResolutionStatus.AMBIGUOUS,
        ambiguous_domains=(DomainId(slug="project"), DomainId(slug="health")),
        requires_clarification=True,
        recommended_question="Which domain is relevant?",
    )
    evt = adapt_resolution_result(res, actor="system")
    assert evt.event_type == "domain.resolution.ambiguous"
    assert evt.payload["status"] == "ambiguous"
    assert evt.payload["requires_clarification"] is True


# 2. Composition
def test_adapt_composition_created() -> None:
    comp = DomainComposition(
        id="comp-1",
        resolution_id="res-1",
        primary_domain=DomainId(slug="project"),
        status=DomainCompositionStatus.COMPOSED,
    )
    evt = adapt_composition_created(comp, actor="system")
    assert evt.event_type == "domain.composition.created"
    assert evt.domain_id == DomainId(slug="project")
    assert evt.payload["composition_id"] == "comp-1"


def test_adapt_composition_updated_different_composition() -> None:
    comp1 = DomainComposition(
        id="comp-1",
        resolution_id="res-1",
        primary_domain=DomainId(slug="project"),
        status=DomainCompositionStatus.COMPOSED,
    )
    comp2 = DomainComposition(
        id="comp-2",
        resolution_id="res-1",
        primary_domain=DomainId(slug="project"),
        supporting_domains=(DomainId(slug="health"),),
        status=DomainCompositionStatus.COMPOSED,
    )
    evt = adapt_composition_updated(comp1, comp2, actor="system")
    assert evt is not None
    assert evt.event_type == "domain.composition.updated"
    assert evt.payload["previous_composition_id"] == "comp-1"
    assert evt.payload["composition_id"] == "comp-2"


def test_adapt_composition_updated_identical_returns_none() -> None:
    comp1 = DomainComposition(
        id="comp-1",
        resolution_id="res-1",
        primary_domain=DomainId(slug="project"),
        status=DomainCompositionStatus.COMPOSED,
    )
    comp2 = DomainComposition(
        id="comp-1",
        resolution_id="res-1",
        primary_domain=DomainId(slug="project"),
        status=DomainCompositionStatus.COMPOSED,
    )
    evt = adapt_composition_updated(comp1, comp2, actor="system")
    assert evt is None


# 3. Execution
def test_adapt_execution_lifecycle() -> None:
    evt_start = adapt_execution_started("exec-1", DomainId(slug="health"), actor="user")
    assert evt_start.event_type == "domain.execution.started"

    evt_comp = adapt_execution_completed(
        "exec-1", DomainId(slug="health"), actor="user"
    )
    assert evt_comp.event_type == "domain.execution.completed"

    evt_fail = adapt_execution_failed(
        "exec-1", DomainId(slug="health"), error="timeout", actor="user"
    )
    assert evt_fail.event_type == "domain.execution.failed"
    assert evt_fail.payload["error"] == "timeout"


# 4. Conflict Resolution
def test_adapt_conflict_detected() -> None:
    case = DomainConflictCase(
        id="case-1",
        domains=(DomainId(slug="health"), DomainId(slug="sport")),
        kind=DomainConflictKind.COMPOSITION,
        severity=DomainConflictSeverity.MATERIAL,
        status=DomainConflictStatus.OPEN,
        references=(_make_conflict_ref("ref-case-1"),),
        blocking=False,
    )
    evt = adapt_conflict_detected(case, actor="system")
    assert evt.event_type == "domain.conflict.detected"
    assert evt.domain_id == DomainId(slug="health")
    assert evt.payload["conflict_id"] == "case-1"


def test_adapt_conflict_resolution_resolved() -> None:
    res = DomainConflictResolution(
        conflict_id="case-1",
        status=DomainConflictStatus.RESOLVED,
        strategy=DomainConflictStrategy.PRIMARY_DOMAIN_PRECEDENCE,
        winning_reference_ids=("ref-1",),
        reason_codes=(DomainConflictReasonCode.PRIMARY_PRECEDENCE,),
        can_proceed=True,
    )
    evt = adapt_conflict_resolution(
        res, primary_domain=DomainId(slug="project"), actor="system"
    )
    assert evt is not None
    assert evt.event_type == "domain.conflict.resolved"
    assert evt.payload["conflict_id"] == "case-1"
    assert evt.payload["can_proceed"] is True


def test_adapt_conflict_unresolved_never_emits_resolved() -> None:
    res = DomainConflictResolution(
        conflict_id="case-unres",
        status=DomainConflictStatus.UNRESOLVED,
        strategy=DomainConflictStrategy.MAINTAIN_CONFLICT,
        conflict_preserved=True,
        preserved_reference_ids=("ref-1",),
        reason_codes=(DomainConflictReasonCode.PRESERVED,),
        can_proceed=False,
    )
    assert (
        adapt_conflict_resolution(res, primary_domain=DomainId(slug="project")) is None
    )


def test_adapt_conflict_postponed_never_emits_resolved() -> None:
    res = DomainConflictResolution(
        conflict_id="case-postponed",
        status=DomainConflictStatus.POSTPONED,
        strategy=DomainConflictStrategy.POSTPONE_ACTION,
        action_postponed=True,
        conflict_preserved=True,
        preserved_reference_ids=("ref-1",),
        reason_codes=(DomainConflictReasonCode.ACTION_POSTPONED,),
        can_proceed=False,
    )
    assert (
        adapt_conflict_resolution(res, primary_domain=DomainId(slug="project")) is None
    )


def test_adapt_conflict_awaiting_user_never_emits_resolved() -> None:
    res = DomainConflictResolution(
        conflict_id="case-user",
        status=DomainConflictStatus.AWAITING_USER,
        strategy=DomainConflictStrategy.ASK_USER,
        requires_user_input=True,
        conflict_preserved=True,
        preserved_reference_ids=("ref-1",),
        reason_codes=(DomainConflictReasonCode.USER_INPUT_REQUIRED,),
        can_proceed=False,
    )
    assert (
        adapt_conflict_resolution(res, primary_domain=DomainId(slug="project")) is None
    )


def test_adapt_conflict_awaiting_human_review_never_emits_resolved() -> None:
    res = DomainConflictResolution(
        conflict_id="case-hr",
        status=DomainConflictStatus.AWAITING_HUMAN_REVIEW,
        strategy=DomainConflictStrategy.HUMAN_REVIEW,
        requires_human_review=True,
        conflict_preserved=True,
        preserved_reference_ids=("ref-1",),
        reason_codes=(DomainConflictReasonCode.HUMAN_REVIEW_REQUIRED,),
        can_proceed=False,
    )
    assert (
        adapt_conflict_resolution(res, primary_domain=DomainId(slug="project")) is None
    )


def test_adapt_conflict_blocked_never_emits_resolved() -> None:
    res = DomainConflictResolution(
        conflict_id="case-blocked",
        status=DomainConflictStatus.BLOCKED,
        strategy=DomainConflictStrategy.MOST_RESTRICTIVE,
        conflict_preserved=True,
        preserved_reference_ids=("ref-1",),
        reason_codes=(DomainConflictReasonCode.SAFETY_PRECEDENCE,),
        can_proceed=False,
    )
    assert (
        adapt_conflict_resolution(res, primary_domain=DomainId(slug="project")) is None
    )


# 5. Permissions
def test_adapt_permission_lifecycle() -> None:
    evt_req = adapt_permission_requested(
        "domain.project.read", DomainId(slug="project"), actor="agent"
    )
    assert evt_req.event_type == "domain.permission.requested"

    evt_den = adapt_permission_denied(
        "domain.project.read",
        DomainId(slug="project"),
        reason="forbidden",
        actor="guard",
    )
    assert evt_den.event_type == "domain.permission.denied"
    assert evt_den.payload["reason"] == "forbidden"


# 6. Approvals
def test_adapt_approval_lifecycle() -> None:
    evt_req = adapt_approval_requested(
        "appr-1", DomainId(slug="project"), action="deploy", actor="user"
    )
    assert evt_req.event_type == "domain.approval.requested"

    evt_rec = adapt_approval_received(
        "appr-1",
        DomainId(slug="project"),
        approved=True,
        decision_by="lead",
        actor="lead",
    )
    assert evt_rec.event_type == "domain.approval.received"
    assert evt_rec.payload["approved"] is True
    assert evt_rec.payload["decision_by"] == "lead"


# 7. Memory (proposed vs updated)
def test_adapt_memory_lifecycle() -> None:
    evt_prop = adapt_memory_proposed(
        "prop-1", DomainId(slug="reflection"), actor="agent"
    )
    assert evt_prop.event_type == "domain.memory.proposed"
    assert evt_prop.payload["proposal_id"] == "prop-1"

    evt_upd = adapt_memory_updated("upd-1", DomainId(slug="reflection"), actor="agent")
    assert evt_upd.event_type == "domain.memory.updated"
    assert evt_upd.payload["update_id"] == "upd-1"


# 8. Workflows
def test_adapt_workflow_lifecycle() -> None:
    evt_start = adapt_workflow_started("wf-1", DomainId(slug="project"), actor="runner")
    assert evt_start.event_type == "domain.workflow.started"

    evt_pause = adapt_workflow_paused("wf-1", DomainId(slug="project"), actor="runner")
    assert evt_pause.event_type == "domain.workflow.paused"

    evt_resume = adapt_workflow_resumed(
        "wf-1", DomainId(slug="project"), actor="runner"
    )
    assert evt_resume.event_type == "domain.workflow.resumed"

    evt_comp = adapt_workflow_completed(
        "wf-1", DomainId(slug="project"), actor="runner"
    )
    assert evt_comp.event_type == "domain.workflow.completed"


# 9. Operations
def test_adapt_operation_lifecycle() -> None:
    evt_start = adapt_operation_started("op-1", DomainId(slug="health"), actor="exec")
    assert evt_start.event_type == "domain.operation.started"

    evt_comp = adapt_operation_completed("op-1", DomainId(slug="health"), actor="exec")
    assert evt_comp.event_type == "domain.operation.completed"

    evt_fail = adapt_operation_failed(
        "op-1", DomainId(slug="health"), error="failed", actor="exec"
    )
    assert evt_fail.event_type == "domain.operation.failed"
    assert evt_fail.payload["error"] == "failed"
