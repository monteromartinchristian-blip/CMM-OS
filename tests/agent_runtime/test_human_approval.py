"""Phase 9.10 – Human Approval System Tests.

Comprehensive test suite verifying contracts, repository, service, state machine,
authorization, fail-safe rules, adapters, and public API exports of the Human Approval System.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

import cmm.agent_runtime as runtime
from cmm.agent_runtime.approval_adapters import (
    create_requirement_from_autonomy,
    create_requirement_from_policy,
    create_requirement_from_workflow_plan,
)
from cmm.agent_runtime.approval_contracts import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalRequirement,
    ApprovalResolution,
)
from cmm.agent_runtime.approval_repository import (
    InMemoryApprovalRepository,
)
from cmm.agent_runtime.approval_service import (
    ApprovalService,
)
from cmm.agent_runtime.enums import (
    ApprovalDecisionType,
    ApprovalRequestStatus,
    ApprovalRequirementSource,
    AutonomyDecision,
    PolicyDecision,
    PolicyRiskLevel,
)
from cmm.agent_runtime.errors import (
    ApprovalActorNotAuthorizedError,
    ApprovalAlreadyResolvedError,
    ApprovalAutonomyIntegrationError,
    ApprovalDecisionNotFoundError,
    ApprovalExpiredError,
    ApprovalPolicyIntegrationError,
    ApprovalRequestNotFoundError,
    ApprovalSupersessionError,
    DuplicateApprovalDecisionError,
    DuplicateApprovalRequestError,
    InvalidApprovalContractError,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class DummyPolicyResult:
    def __init__(
        self,
        decision: PolicyDecision = PolicyDecision.REQUIRE_APPROVAL,
        denied: bool = False,
        requires_approval: bool = True,
        reason_codes: tuple[str, ...] = ("policy.approval_required",),
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.id = "pol-res-123"
        self.request_id = "pol-req-123"
        self.decision = decision
        self.denied = denied
        self.requires_approval = requires_approval
        self.reason_codes = reason_codes
        self.obligations = ()
        self.metadata = metadata or {"risk_level": "high"}


class DummyAutonomyResult:
    def __init__(
        self,
        decision: AutonomyDecision = AutonomyDecision.REQUIRE_APPROVAL,
        denied: bool = False,
        requires_approval: bool = True,
        level: int = 3,
        reason_codes: tuple[str, ...] = ("autonomy.approval_required",),
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.id = "auto-res-123"
        self.request_id = "auto-req-123"
        self.decision = decision
        self.denied = denied
        self.requires_approval = requires_approval
        self.level = level
        self.reason_codes = reason_codes
        self.metadata = metadata or {}


class DummyWorkflowPlan:
    def __init__(self) -> None:
        self.id = "plan-123"
        self.goal_id = "goal-456"
        self.workflow_id = "wf-789"
        self.risk = PolicyRiskLevel.HIGH


# ── Contracts Tests ──────────────────────────────────────────────────────────


def test_approval_requirement_creation_and_roundtrip() -> None:
    req = ApprovalRequirement(
        id="req-1",
        source=ApprovalRequirementSource.POLICY,
        title="Approve API Change",
        description="Public API modification requires human review.",
        reason_codes=("policy.approval_required",),
        required_approvers=("user-alice", "user-bob"),
        minimum_approvals=2,
        risk_level=PolicyRiskLevel.HIGH,
        scope="operation",
        agent_run_id="run-1",
        goal_id="goal-1",
        workflow_id="wf-1",
        operation_id="op-1",
        expires_at=_now_utc() + timedelta(hours=1),
        metadata={"category": "breaking_change"},
    )
    assert req.id == "req-1"
    assert req.source == ApprovalRequirementSource.POLICY
    assert req.minimum_approvals == 2
    assert req.risk_level == PolicyRiskLevel.HIGH

    d = req.to_dict()
    reconstructed = ApprovalRequirement.from_dict(d)
    assert reconstructed == req


def test_approval_requirement_validation_errors() -> None:
    with pytest.raises(
        InvalidApprovalContractError, match="id must be a non-empty string"
    ):
        ApprovalRequirement(
            id="", source=ApprovalRequirementSource.POLICY, title="T", description="D"
        )

    with pytest.raises(
        InvalidApprovalContractError, match="minimum_approvals must be >= 1"
    ):
        ApprovalRequirement(
            id="r",
            source=ApprovalRequirementSource.POLICY,
            title="T",
            description="D",
            minimum_approvals=0,
        )

    with pytest.raises(
        InvalidApprovalContractError, match="minimum_approvals must be an integer"
    ):
        ApprovalRequirement(
            id="r",
            source=ApprovalRequirementSource.POLICY,
            title="T",
            description="D",
            minimum_approvals=True,
        )  # type: ignore


def test_approval_request_creation_and_fingerprint() -> None:
    now = _now_utc()
    req = ApprovalRequest(
        id="app-1",
        title="Destructive Data Wipe",
        description="Clear historical database tables.",
        requested_by="agent-cleanup",
        agent_run_id="run-100",
        goal_id="goal-200",
        reason_codes=("security.destructive_action",),
        risk_level=PolicyRiskLevel.CRITICAL,
        required_approvers=("admin-user",),
        minimum_approvals=1,
        created_at=now,
        updated_at=now,
    )

    assert req.id == "app-1"
    assert req.status == ApprovalRequestStatus.PENDING
    assert len(req.request_fingerprint) == 64  # SHA-256 hex string

    d = req.to_dict()
    rec = ApprovalRequest.from_dict(d)
    assert rec == req


def test_approval_request_validation_errors() -> None:
    with pytest.raises(
        InvalidApprovalContractError, match="title must be a non-empty string"
    ):
        ApprovalRequest(id="1", title=" ", description="D", requested_by="A")

    with pytest.raises(
        InvalidApprovalContractError, match="requested_by must be a non-empty string"
    ):
        ApprovalRequest(id="1", title="T", description="D", requested_by="")


def test_approval_decision_creation_and_roundtrip() -> None:
    dec = ApprovalDecision(
        id="dec-1",
        request_id="app-1",
        decision=ApprovalDecisionType.APPROVE_WITH_CHANGES,
        actor_id="user-alice",
        conditions=("Run full test suite before deployment",),
        modified_parameters={"timeout": 60, "retry_count": 3},
        comment="Approved with extended timeout.",
    )
    assert dec.id == "dec-1"
    assert dec.decision == ApprovalDecisionType.APPROVE_WITH_CHANGES
    assert dec.modified_parameters["timeout"] == 60

    d = dec.to_dict()
    rec = ApprovalDecision.from_dict(d)
    assert rec == dec


def test_approval_decision_structural_invariant_error() -> None:
    with pytest.raises(
        InvalidApprovalContractError,
        match="modified_parameters can only be specified when decision is 'approve_with_changes'",
    ):
        ApprovalDecision(
            id="dec-1",
            request_id="app-1",
            decision=ApprovalDecisionType.APPROVE,
            actor_id="user-alice",
            modified_parameters={"timeout": 60},
        )


def test_approval_resolution_creation_and_validation() -> None:
    res = ApprovalResolution(
        request_id="app-1",
        status=ApprovalRequestStatus.APPROVED,
        satisfied=True,
        may_execute=True,
        approval_count=1,
        rejection_count=0,
        required_approval_count=1,
    )
    assert res.satisfied is True
    assert res.may_execute is True

    d = res.to_dict()
    rec = ApprovalResolution.from_dict(d)
    assert rec == res

    with pytest.raises(
        InvalidApprovalContractError,
        match="may_execute cannot be True when satisfied is False",
    ):
        ApprovalResolution(
            request_id="app-1",
            status=ApprovalRequestStatus.PENDING,
            satisfied=False,
            may_execute=True,
        )


# ── Repository Tests ──────────────────────────────────────────────────────────


def test_in_memory_repository_requests() -> None:
    repo = InMemoryApprovalRepository()
    now = _now_utc()
    req1 = ApprovalRequest(
        id="req-1",
        title="Title 1",
        description="Desc 1",
        requested_by="agent-1",
        agent_run_id="run-1",
        goal_id="goal-1",
        operation_id="op-1",
        created_at=now,
        updated_at=now,
    )
    repo.add_request(req1)

    assert repo.get_request("req-1") == req1

    with pytest.raises(DuplicateApprovalRequestError):
        repo.add_request(req1)

    with pytest.raises(ApprovalRequestNotFoundError):
        repo.get_request("non-existent")

    # List filtering
    listed = repo.list_requests(agent_run_id="run-1")
    assert len(listed) == 1
    assert listed[0] == req1

    listed_empty = repo.list_requests(agent_run_id="run-999")
    assert len(listed_empty) == 0


def test_in_memory_repository_decisions() -> None:
    repo = InMemoryApprovalRepository()
    req = ApprovalRequest(id="req-1", title="T", description="D", requested_by="A")
    repo.add_request(req)

    dec = ApprovalDecision(
        id="dec-1",
        request_id="req-1",
        decision=ApprovalDecisionType.APPROVE,
        actor_id="user-1",
    )
    repo.add_decision(dec)

    assert repo.get_decision("dec-1") == dec
    assert repo.list_decisions("req-1") == (dec,)

    with pytest.raises(DuplicateApprovalDecisionError):
        repo.add_decision(dec)

    # Orphan decision error
    orphan_dec = ApprovalDecision(
        id="dec-2",
        request_id="req-orphan",
        decision=ApprovalDecisionType.APPROVE,
        actor_id="user-1",
    )
    with pytest.raises(ApprovalRequestNotFoundError, match="Orphan decision"):
        repo.add_decision(orphan_dec)


def test_in_memory_repository_expiration() -> None:
    repo = InMemoryApprovalRepository()
    past_dt = _now_utc() - timedelta(minutes=10)
    future_dt = _now_utc() + timedelta(minutes=10)

    req_exp = ApprovalRequest(
        id="req-exp", title="T", description="D", requested_by="A", expires_at=past_dt
    )
    req_active = ApprovalRequest(
        id="req-act", title="T", description="D", requested_by="A", expires_at=future_dt
    )

    repo.add_request(req_exp)
    repo.add_request(req_active)

    expired = repo.expire_requests()
    assert len(expired) == 1
    assert expired[0].id == "req-exp"
    assert repo.get_request("req-exp").status == ApprovalRequestStatus.EXPIRED
    assert repo.get_request("req-act").status == ApprovalRequestStatus.PENDING


# ── Service & State Machine Tests ────────────────────────────────────────────


def test_approval_service_approve_flow() -> None:
    svc = ApprovalService()
    req = svc.create_request(
        title="Production Deployment",
        description="Deploy phase 9.10 to production.",
        requested_by="agent-deployer",
        required_approvers=("user-alice", "user-bob"),
        minimum_approvals=2,
    )
    assert req.status == ApprovalRequestStatus.PENDING

    # First approval vote
    res1 = svc.approve(req.id, actor_id="user-alice", comment="Looks good.")
    assert res1.satisfied is False
    assert res1.may_execute is False
    assert res1.status == ApprovalRequestStatus.PENDING
    assert res1.approval_count == 1

    # Second approval vote
    res2 = svc.approve(req.id, actor_id="user-bob", comment="Approved.")
    assert res2.satisfied is True
    assert res2.may_execute is True
    assert res2.status == ApprovalRequestStatus.APPROVED
    assert res2.approval_count == 2
    assert svc.may_execute(req.id) is True


def test_approval_service_approve_with_changes_flow() -> None:
    svc = ApprovalService()
    req = svc.create_request(
        title="Database Schema Migration",
        description="Add new column to users table.",
        requested_by="agent-db",
        required_approvers=("user-alice",),
        minimum_approvals=1,
    )

    res = svc.approve_with_changes(
        req.id,
        actor_id="user-alice",
        modified_parameters={"lock_timeout_ms": 5000},
        conditions=("Run migration during maintenance window",),
    )

    assert res.status == ApprovalRequestStatus.APPROVED_WITH_CHANGES
    assert res.satisfied is True
    assert res.may_execute is False  # Must undergo revalidation before execution!
    assert res.requires_policy_reevaluation is True
    assert res.requires_validation is True
    assert res.requires_budget_recalculation is True
    assert res.requires_plan_update is True
    assert res.approved_parameters["lock_timeout_ms"] == 5000
    assert "Run migration during maintenance window" in res.conditions


def test_approval_service_rejection_precedence() -> None:
    svc = ApprovalService()
    req = svc.create_request(
        title="Feature Rollout",
        description="Enable feature flag.",
        requested_by="agent-flag",
        required_approvers=("user-alice", "user-bob"),
        minimum_approvals=2,
    )

    # First vote: Approve by Alice (1 of 2 required approvals -> still pending)
    svc.approve(req.id, actor_id="user-alice")

    # Second vote: Reject by Bob -> Rejection prevails immediately
    res_reject = svc.reject(req.id, actor_id="user-bob", comment="Too risky right now.")
    assert res_reject.status == ApprovalRequestStatus.REJECTED
    assert res_reject.satisfied is False
    assert res_reject.may_execute is False
    assert svc.may_execute(req.id) is False


def test_approval_service_postpone_and_cancel() -> None:
    svc = ApprovalService()
    req1 = svc.create_request(title="T1", description="D1", requested_by="A")
    res_postpone = svc.postpone(
        req1.id, actor_id="user-alice", comment="Hold off until tomorrow."
    )
    assert res_postpone.status == ApprovalRequestStatus.POSTPONED
    assert res_postpone.may_execute is False

    req2 = svc.create_request(title="T2", description="D2", requested_by="A")
    res_cancel = svc.cancel(req2.id, actor_id="user-alice", comment="No longer needed.")
    assert res_cancel.status == ApprovalRequestStatus.CANCELLED
    assert res_cancel.may_execute is False


def test_approval_service_expiration() -> None:
    svc = ApprovalService()
    past_dt = _now_utc() - timedelta(minutes=5)
    req = svc.create_request(
        title="T", description="D", requested_by="A", expires_at=past_dt
    )

    svc.expire_due_requests()
    assert svc.may_execute(req.id) is False

    # Attempting to submit decision on expired request raises ApprovalExpiredError
    with pytest.raises(ApprovalExpiredError, match="expired"):
        svc.approve(req.id, actor_id="user-alice")


def test_approval_service_terminal_state_error_and_idempotency() -> None:
    svc = ApprovalService()
    req = svc.create_request(title="T", description="D", requested_by="A")
    res1 = svc.approve(req.id, actor_id="user-alice")
    assert res1.status == ApprovalRequestStatus.APPROVED

    # Idempotent retry with exact same decision object returns existing resolution
    dec = svc.repository.list_decisions(req.id)[0]
    res_retry = svc.submit_decision(dec)
    assert res_retry == res1

    # Attempting to submit a NEW decision on already resolved request raises ApprovalAlreadyResolvedError
    with pytest.raises(ApprovalAlreadyResolvedError, match="terminal status"):
        svc.reject(req.id, actor_id="user-bob")


def test_approval_service_supersede() -> None:
    svc = ApprovalService()
    req_old = svc.create_request(
        title="Old Plan", description="Original approach", requested_by="A"
    )

    req_new_req = ApprovalRequirement(
        id="req-new-spec",
        source=ApprovalRequirementSource.WORKFLOW,
        title="New Safer Plan",
        description="Refactored approach",
    )

    req_new = svc.supersede(req_old.id, req_new_req)

    assert req_new.supersedes_request_id == req_old.id
    assert (
        svc.repository.get_request(req_old.id).status
        == ApprovalRequestStatus.SUPERSEDED
    )
    assert svc.repository.get_request(req_old.id).superseded_by_request_id == req_new.id
    assert svc.may_execute(req_old.id) is False

    # Superseding already superseded request raises error
    with pytest.raises(ApprovalSupersessionError, match="terminal status"):
        svc.supersede(req_old.id, req_new_req)


# ── Approvers & Authorization Tests ──────────────────────────────────────────


def test_unauthorized_actor_rejected() -> None:
    svc = ApprovalService()
    req = svc.create_request(
        title="T",
        description="D",
        requested_by="A",
        required_approvers=("user-alice", "user-bob"),
    )

    with pytest.raises(
        ApprovalActorNotAuthorizedError, match="not in required_approvers"
    ):
        svc.approve(req.id, actor_id="user-charlie")


def test_duplicate_vote_by_same_actor_rejected() -> None:
    svc = ApprovalService()
    req = svc.create_request(
        title="T",
        description="D",
        requested_by="A",
        required_approvers=("user-alice", "user-bob"),
        minimum_approvals=2,
    )

    svc.approve(req.id, actor_id="user-alice")

    with pytest.raises(
        ApprovalActorNotAuthorizedError, match="already submitted a decision"
    ):
        svc.approve(req.id, actor_id="user-alice")


# ── Security & Fail-Safe Tests ────────────────────────────────────────────────


def test_failsafe_blocked_by_default() -> None:
    svc = ApprovalService()
    req = svc.create_request(title="T", description="D", requested_by="A")

    # Pending request must never execute
    assert svc.is_approval_satisfied(req.id) is False
    assert svc.may_execute(req.id) is False


# ── Adapters Tests ───────────────────────────────────────────────────────────


def test_adapter_policy_to_requirement_success() -> None:
    pol_res = DummyPolicyResult(
        decision=PolicyDecision.REQUIRE_APPROVAL, requires_approval=True
    )
    req_spec = create_requirement_from_policy(pol_res, title="Policy Requirement")

    assert req_spec.source == ApprovalRequirementSource.POLICY
    assert req_spec.title == "Policy Requirement"
    assert "policy.approval_required" in req_spec.reason_codes


def test_adapter_policy_deny_cannot_be_approved() -> None:
    pol_res_deny = DummyPolicyResult(decision=PolicyDecision.DENY, denied=True)

    with pytest.raises(
        ApprovalPolicyIntegrationError, match="Policy DENY cannot be converted"
    ):
        create_requirement_from_policy(pol_res_deny)


def test_adapter_autonomy_to_requirement_success() -> None:
    auto_res = DummyAutonomyResult(
        decision=AutonomyDecision.REQUIRE_APPROVAL, requires_approval=True
    )
    req_spec = create_requirement_from_autonomy(auto_res, title="Autonomy Requirement")

    assert req_spec.source == ApprovalRequirementSource.AUTONOMY
    assert req_spec.title == "Autonomy Requirement"


def test_adapter_autonomy_deny_cannot_be_approved() -> None:
    auto_res_deny = DummyAutonomyResult(decision=AutonomyDecision.DENY, denied=True)

    with pytest.raises(
        ApprovalAutonomyIntegrationError, match="Autonomy DENY cannot be converted"
    ):
        create_requirement_from_autonomy(auto_res_deny)


def test_adapter_workflow_plan_to_requirement() -> None:
    plan = DummyWorkflowPlan()
    req_spec = create_requirement_from_workflow_plan(plan, node_id="node-1")

    assert req_spec.source == ApprovalRequirementSource.WORKFLOW
    assert req_spec.workflow_id == "wf-789"
    assert req_spec.operation_id == "node-1"


# ── Public API & Exports Verification ─────────────────────────────────────────


def test_public_api_exports() -> None:
    all_items = runtime.__all__
    duplicates = [x for x in set(all_items) if all_items.count(x) > 1]
    assert duplicates == [], f"Found duplicate exports in __all__: {duplicates}"

    expected_symbols = [
        "ApprovalRequest",
        "ApprovalDecision",
        "ApprovalResolution",
        "ApprovalRequirement",
        "ApprovalRequestStatus",
        "ApprovalDecisionType",
        "ApprovalRequirementSource",
        "ApprovalRepository",
        "InMemoryApprovalRepository",
        "ApprovalService",
        "create_requirement_from_policy",
        "create_requirement_from_autonomy",
        "create_requirement_from_workflow_plan",
        "ApprovalError",
        "InvalidApprovalContractError",
        "ApprovalRequestNotFoundError",
        "ApprovalDecisionNotFoundError",
        "DuplicateApprovalRequestError",
        "DuplicateApprovalDecisionError",
        "ApprovalAlreadyResolvedError",
        "ApprovalActorNotAuthorizedError",
        "ApprovalExpiredError",
        "InvalidApprovalTransitionError",
        "ApprovalSupersessionError",
        "ApprovalPolicyIntegrationError",
        "ApprovalAutonomyIntegrationError",
    ]

    for sym in expected_symbols:
        assert hasattr(runtime, sym), f"Runtime package is missing public export {sym}"
        assert sym in runtime.__all__, f"Symbol {sym} is not listed in __all__"


# ── Additional Granular & Edge Case Tests ────────────────────────────────────


def test_fingerprint_variation_on_operation_param_change() -> None:
    now = _now_utc()
    req1 = ApprovalRequest(
        id="a-1",
        title="Operation Execution",
        description="Run script",
        requested_by="agent-1",
        operation_id="op-100",
        created_at=now,
        updated_at=now,
        metadata={"operation_parameters": {"force": False}},
    )

    req2 = ApprovalRequest(
        id="a-2",
        title="Operation Execution",
        description="Run script",
        requested_by="agent-1",
        operation_id="op-100",
        created_at=now,
        updated_at=now,
        metadata={"operation_parameters": {"force": True}},
    )

    assert req1.request_fingerprint != req2.request_fingerprint


def test_non_serializable_metadata_raises_contract_error() -> None:
    class UnserializableObj:
        pass

    with pytest.raises(InvalidApprovalContractError, match="JSON-serializable"):
        ApprovalRequest(
            id="a-1",
            title="T",
            description="D",
            requested_by="A",
            metadata={"obj": UnserializableObj()},
        )


def test_repository_find_pending_for_run_and_operation() -> None:
    repo = InMemoryApprovalRepository()
    req1 = ApprovalRequest(
        id="r1",
        title="T1",
        description="D1",
        requested_by="A",
        agent_run_id="run-A",
        operation_id="op-X",
    )
    req2 = ApprovalRequest(
        id="r2",
        title="T2",
        description="D2",
        requested_by="A",
        agent_run_id="run-A",
        operation_id="op-Y",
    )
    req3 = ApprovalRequest(
        id="r3",
        title="T3",
        description="D3",
        requested_by="A",
        agent_run_id="run-B",
        operation_id="op-X",
    )

    repo.add_request(req1)
    repo.add_request(req2)
    repo.add_request(req3)

    pending_run = repo.find_pending_for_run("run-A")
    assert len(pending_run) == 2
    assert {r.id for r in pending_run} == {"r1", "r2"}

    pending_op = repo.find_pending_for_operation("op-X")
    assert len(pending_op) == 2
    assert {r.id for r in pending_op} == {"r1", "r3"}


def test_repository_list_decisions_insertion_order() -> None:
    repo = InMemoryApprovalRepository()
    req = ApprovalRequest(id="r1", title="T", description="D", requested_by="A")
    repo.add_request(req)

    dec1 = ApprovalDecision(
        id="d1", request_id="r1", decision=ApprovalDecisionType.APPROVE, actor_id="u1"
    )
    dec2 = ApprovalDecision(
        id="d2", request_id="r1", decision=ApprovalDecisionType.APPROVE, actor_id="u2"
    )
    repo.add_decision(dec1)
    repo.add_decision(dec2)

    decisions = repo.list_decisions("r1")
    assert decisions == (dec1, dec2)


def test_approve_with_changes_merges_multiple_actors_parameters() -> None:
    svc = ApprovalService()
    req = svc.create_request(
        title="Multi-approver modification",
        description="Adjust system config",
        requested_by="agent-sys",
        required_approvers=("user-alice", "user-bob"),
        minimum_approvals=2,
    )

    svc.approve_with_changes(
        req.id,
        actor_id="user-alice",
        modified_parameters={"mem_limit": "2GB"},
        conditions=("Condition 1",),
    )

    res = svc.approve_with_changes(
        req.id,
        actor_id="user-bob",
        modified_parameters={"cpu_limit": "4"},
        conditions=("Condition 2",),
    )

    assert res.status == ApprovalRequestStatus.APPROVED_WITH_CHANGES
    assert res.satisfied is True
    assert res.approved_parameters["mem_limit"] == "2GB"
    assert res.approved_parameters["cpu_limit"] == "4"
    assert "Condition 1" in res.conditions
    assert "Condition 2" in res.conditions


def test_postponed_request_can_be_approved() -> None:
    svc = ApprovalService()
    req = svc.create_request(title="T", description="D", requested_by="A")

    svc.postpone(req.id, actor_id="user-alice")
    assert svc.repository.get_request(req.id).status == ApprovalRequestStatus.POSTPONED

    res = svc.approve(req.id, actor_id="user-bob")
    assert res.status == ApprovalRequestStatus.APPROVED
    assert res.satisfied is True
    assert res.may_execute is True


def test_postponed_request_expiration() -> None:
    svc = ApprovalService()
    now = _now_utc()
    future_dt = now + timedelta(minutes=5)
    req = svc.create_request(
        title="T", description="D", requested_by="A", expires_at=future_dt
    )

    svc.postpone(req.id, actor_id="user-alice")
    assert svc.repository.get_request(req.id).status == ApprovalRequestStatus.POSTPONED

    expired_time = future_dt + timedelta(seconds=1)
    svc.expire_due_requests(now=expired_time)
    assert svc.repository.get_request(req.id).status == ApprovalRequestStatus.EXPIRED


def test_supersede_with_approval_request_instance() -> None:
    svc = ApprovalService()
    req_old = svc.create_request(title="Old", description="D", requested_by="A")
    req_new_obj = ApprovalRequest(
        id="req-new-direct", title="New", description="D", requested_by="A"
    )

    created = svc.supersede(req_old.id, req_new_obj)
    assert created.id == "req-new-direct"
    assert created.supersedes_request_id == req_old.id


def test_supersede_non_existent_request_raises_not_found() -> None:
    svc = ApprovalService()
    req_new = ApprovalRequirement(
        id="r", source=ApprovalRequirementSource.WORKFLOW, title="T", description="D"
    )
    with pytest.raises(ApprovalRequestNotFoundError):
        svc.supersede("non-existent-id", req_new)


def test_iso_string_datetime_parsing_in_contracts() -> None:
    iso_str = "2026-07-25T12:00:00+00:00"
    req = ApprovalRequirement(
        id="r1",
        source=ApprovalRequirementSource.POLICY,
        title="T",
        description="D",
        expires_at=iso_str,  # type: ignore
    )
    assert isinstance(req.expires_at, datetime)
    assert req.expires_at.tzinfo is not None


def test_empty_actor_id_in_decision_raises_error() -> None:
    with pytest.raises(
        InvalidApprovalContractError, match="actor_id must be a non-empty string"
    ):
        ApprovalDecision(
            id="d1", request_id="r1", decision=ApprovalDecisionType.APPROVE, actor_id=""
        )


def test_empty_request_id_in_decision_raises_error() -> None:
    with pytest.raises(
        InvalidApprovalContractError, match="request_id must be a non-empty string"
    ):
        ApprovalDecision(
            id="d1",
            request_id=" ",
            decision=ApprovalDecisionType.APPROVE,
            actor_id="user-1",
        )


class DummyObligation:
    def __init__(self, kind: str) -> None:
        self.kind = kind


def test_adapter_policy_with_require_approval_obligation() -> None:
    pol_res = DummyPolicyResult(
        decision=PolicyDecision.ALLOW_WITH_RESTRICTIONS,
        requires_approval=False,
    )
    pol_res.obligations = (DummyObligation("require_approval"),)  # type: ignore

    req = create_requirement_from_policy(pol_res)
    assert req.source == ApprovalRequirementSource.POLICY


def test_adapter_policy_without_approval_requirement_raises_error() -> None:
    pol_res = DummyPolicyResult(
        decision=PolicyDecision.ALLOW,
        requires_approval=False,
    )
    pol_res.obligations = ()  # type: ignore

    with pytest.raises(InvalidApprovalContractError, match="does not require approval"):
        create_requirement_from_policy(pol_res)


def test_adapter_autonomy_without_approval_requirement_raises_error() -> None:
    auto_res = DummyAutonomyResult(
        decision=AutonomyDecision.ALLOW,
        requires_approval=False,
    )

    with pytest.raises(InvalidApprovalContractError, match="does not require approval"):
        create_requirement_from_autonomy(auto_res)


def test_adapter_workflow_plan_risk_level_mapping() -> None:
    plan = DummyWorkflowPlan()
    plan.risk = "critical"  # type: ignore

    req = create_requirement_from_workflow_plan(plan)
    assert req.risk_level == PolicyRiskLevel.CRITICAL


def test_conjunctive_authorization_check_simulation() -> None:
    # Simulation: effective_auth = policy_allows AND autonomy_allows AND approval_satisfied
    policy_allows = True
    autonomy_allows = True

    svc = ApprovalService()
    req = svc.create_request(title="T", description="D", requested_by="A")

    # Before approval:
    approval_satisfied = svc.is_approval_satisfied(req.id)
    may_execute_approval = svc.may_execute(req.id)
    effective_auth = (
        policy_allows
        and autonomy_allows
        and approval_satisfied
        and may_execute_approval
    )
    assert effective_auth is False

    # Approve
    svc.approve(req.id, actor_id="user-alice")
    approval_satisfied = svc.is_approval_satisfied(req.id)
    may_execute_approval = svc.may_execute(req.id)
    effective_auth = (
        policy_allows
        and autonomy_allows
        and approval_satisfied
        and may_execute_approval
    )
    assert effective_auth is True


def test_repository_update_non_existent_request_raises_error() -> None:
    repo = InMemoryApprovalRepository()
    req = ApprovalRequest(
        id="non-existent", title="T", description="D", requested_by="A"
    )
    with pytest.raises(ApprovalRequestNotFoundError):
        repo.update_request(req)


def test_repository_get_non_existent_decision_raises_error() -> None:
    repo = InMemoryApprovalRepository()
    with pytest.raises(ApprovalDecisionNotFoundError):
        repo.get_decision("non-existent-dec")


def test_repository_get_resolution() -> None:
    repo = InMemoryApprovalRepository()
    req = ApprovalRequest(id="r1", title="T", description="D", requested_by="A")
    repo.add_request(req)

    assert repo.get_resolution("r1") is None

    res = ApprovalResolution(
        request_id="r1",
        status=ApprovalRequestStatus.APPROVED,
        satisfied=True,
        may_execute=True,
    )
    repo.resolve_request(res)

    assert repo.get_resolution("r1") == res
