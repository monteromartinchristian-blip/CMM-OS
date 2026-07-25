"""Phase 9.11 – Action Budget Unit Test Suite.

Comprehensive tests covering contracts, invariants, numeric validation, atomic reservations,
confirmations, release/failure, expiration, concurrency, duration/pause/resume,
warning/exhaustion thresholds, adjustments, approval/policy/autonomy adapters, repository,
and public API exports.
"""

import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

import cmm.agent_runtime as runtime
from cmm.agent_runtime import (
    ActionBudget,
    ActionBudgetApprovalAdapter,
    ActionBudgetAutonomyAdapter,
    ActionBudgetError,
    ActionBudgetPolicyAdapter,
    ActionBudgetService,
    ActionBudgetStatus,
    AgentAutonomyLevel,
    ApprovalRequest,
    ApprovalRequestStatus,
    ApprovalRequirementSource,
    ApprovalResolution,
    AutonomyDecision,
    AutonomyEvaluationResult,
    BudgetAdjustment,
    BudgetAdjustmentType,
    BudgetAllocation,
    BudgetConsumption,
    BudgetConsumptionOutcome,
    BudgetExhaustedError,
    BudgetIncreaseNotAuthorizedError,
    BudgetPausedError,
    BudgetReservation,
    BudgetReservationExpiredError,
    BudgetReservationStatus,
    BudgetResourceType,
    InMemoryActionBudgetRepository,
    InsufficientBudgetError,
    InvalidActionBudgetContractError,
    PolicyDecision,
    PolicyEvaluationResult,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── 1. Contract Tests ──────────────────────────────────────────────────────────


def test_budget_allocation_valid_and_roundtrip():
    alloc = BudgetAllocation(resource_type=BudgetResourceType.OPERATION, amount=5)
    assert alloc.resource_type == BudgetResourceType.OPERATION
    assert alloc.amount == 5

    data = alloc.to_dict()
    assert data["resource_type"] == "operation"
    assert data["amount"] == 5

    reconstructed = BudgetAllocation.from_dict(data)
    assert reconstructed == alloc


def test_budget_allocation_cost_decimal():
    alloc = BudgetAllocation(
        resource_type=BudgetResourceType.COST, amount=Decimal("12.50")
    )
    assert alloc.resource_type == BudgetResourceType.COST
    assert alloc.amount == Decimal("12.50")

    data = alloc.to_dict()
    assert data["amount"] == "12.50"

    reconstructed = BudgetAllocation.from_dict(data)
    assert reconstructed.amount == Decimal("12.50")


def test_budget_allocation_rejects_bool_and_float_and_negative():
    with pytest.raises(InvalidActionBudgetContractError):
        BudgetAllocation(resource_type=BudgetResourceType.OPERATION, amount=True)  # type: ignore

    with pytest.raises(InvalidActionBudgetContractError):
        BudgetAllocation(resource_type=BudgetResourceType.COST, amount=12.5)  # type: ignore

    with pytest.raises(InvalidActionBudgetContractError):
        BudgetAllocation(resource_type=BudgetResourceType.OPERATION, amount=-1)


def test_action_budget_creation_and_roundtrip():
    now_dt = _now()
    budget = ActionBudget(
        id="budget-101",
        agent_run_id="run-101",
        limits={
            BudgetResourceType.OPERATION: 50,
            BudgetResourceType.COST: Decimal("10.00"),
        },
        used={
            BudgetResourceType.OPERATION: 10,
            BudgetResourceType.COST: Decimal("2.50"),
        },
        reserved={
            BudgetResourceType.OPERATION: 2,
            BudgetResourceType.COST: Decimal("0.50"),
        },
        currency="EUR",
        created_at=now_dt,
        updated_at=now_dt,
        started_at=now_dt,
    )

    assert budget.id == "budget-101"
    assert budget.agent_run_id == "run-101"
    assert budget.limit_for(BudgetResourceType.OPERATION) == 50
    assert budget.used_for(BudgetResourceType.OPERATION) == 10
    assert budget.reserved_for(BudgetResourceType.OPERATION) == 2
    assert budget.currency == "EUR"

    data = budget.to_dict()
    reconstructed = ActionBudget.from_dict(data)
    assert reconstructed.id == budget.id
    assert reconstructed.limits[BudgetResourceType.OPERATION] == 50
    assert reconstructed.limits[BudgetResourceType.COST] == Decimal("10.00")


def test_action_budget_rejects_naive_datetime():
    naive_dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)
    with pytest.raises(InvalidActionBudgetContractError):
        ActionBudget(id="b1", agent_run_id="r1", created_at=naive_dt)


def test_action_budget_rejects_invalid_thresholds():
    with pytest.raises(InvalidActionBudgetContractError):
        ActionBudget(id="b1", agent_run_id="r1", warning_threshold=1.5)

    with pytest.raises(InvalidActionBudgetContractError):
        ActionBudget(
            id="b1", agent_run_id="r1", warning_threshold=0.8, critical_threshold=0.7
        )


def test_budget_reservation_contracts_roundtrip():
    now_dt = _now()
    exp_dt = now_dt + timedelta(minutes=5)
    allocs = (BudgetAllocation(BudgetResourceType.OPERATION, 1),)
    res = BudgetReservation(
        id="res-1",
        budget_id="b-1",
        agent_run_id="r-1",
        allocations=allocs,
        created_at=now_dt,
        expires_at=exp_dt,
    )
    assert res.id == "res-1"
    assert not res.is_expired(now_dt)
    assert res.is_expired(exp_dt + timedelta(seconds=1))

    data = res.to_dict()
    reconstructed = BudgetReservation.from_dict(data)
    assert reconstructed.id == res.id
    assert len(reconstructed.allocations) == 1


def test_budget_consumption_and_adjustment_roundtrip():
    now_dt = _now()
    consumption = BudgetConsumption(
        id="c-1",
        budget_id="b-1",
        agent_run_id="r-1",
        reservation_id="res-1",
        allocations=(BudgetAllocation(BudgetResourceType.OPERATION, 1),),
        outcome=BudgetConsumptionOutcome.SUCCESS,
        consumed_at=now_dt,
    )
    assert consumption.id == "c-1"
    c_recon = BudgetConsumption.from_dict(consumption.to_dict())
    assert c_recon.id == consumption.id

    adjustment = BudgetAdjustment(
        id="adj-1",
        budget_id="b-1",
        adjustment_type=BudgetAdjustmentType.INCREASE,
        resource_type=BudgetResourceType.OPERATION,
        previous_limit=50,
        new_limit=75,
        delta=25,
        actor_id="user-1",
        created_at=now_dt,
    )
    assert adjustment.id == "adj-1"
    adj_recon = BudgetAdjustment.from_dict(adjustment.to_dict())
    assert adj_recon.id == adjustment.id


# ── 2. ActionBudget Calculations & Helpers ─────────────────────────────────────


def test_action_budget_available_and_utilization():
    now_dt = _now()
    budget = ActionBudget(
        id="b1",
        agent_run_id="r1",
        limits={
            BudgetResourceType.OPERATION: 10,
            BudgetResourceType.COST: Decimal("100.00"),
        },
        used={
            BudgetResourceType.OPERATION: 4,
            BudgetResourceType.COST: Decimal("40.00"),
        },
        reserved={
            BudgetResourceType.OPERATION: 1,
            BudgetResourceType.COST: Decimal("10.00"),
        },
        warning_threshold=0.8,
        started_at=now_dt,
    )

    assert budget.available_for(BudgetResourceType.OPERATION) == 5
    assert budget.available_for(BudgetResourceType.COST) == Decimal("50.00")
    assert budget.is_unlimited(BudgetResourceType.TOKEN) is True
    assert budget.available_for(BudgetResourceType.TOKEN) is None

    assert budget.utilization_for(BudgetResourceType.OPERATION) == 0.5
    assert budget.utilization_for(BudgetResourceType.COST) == 0.5


# ── 3. ActionBudgetService & Reservations ──────────────────────────────────────


def test_service_create_budget_and_evaluate():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 5, BudgetResourceType.EXTERNAL_CALL: 2},
    )
    assert budget.id.startswith("budget-")
    assert budget.status == ActionBudgetStatus.ACTIVE

    eval_res = service.evaluate(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)],
    )
    assert eval_res.allowed is True
    assert eval_res.denied is False


def test_service_atomic_reservation_success():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 5, BudgetResourceType.EXTERNAL_CALL: 2},
    )

    allocs = [
        BudgetAllocation(BudgetResourceType.OPERATION, 1),
        BudgetAllocation(BudgetResourceType.EXTERNAL_CALL, 1),
    ]
    res = service.reserve(budget.id, allocations=allocs, operation_id="op-1")

    assert res.id.startswith("reservation-")
    assert res.status == BudgetReservationStatus.RESERVED
    updated = service.get_budget(budget.id)
    assert updated.reserved_for(BudgetResourceType.OPERATION) == 1
    assert updated.reserved_for(BudgetResourceType.EXTERNAL_CALL) == 1


def test_service_atomic_reservation_rejection_all_or_nothing():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 5, BudgetResourceType.EXTERNAL_CALL: 1},
    )

    # EXTERNAL_CALL requests 2 when only 1 available
    allocs = [
        BudgetAllocation(BudgetResourceType.OPERATION, 1),
        BudgetAllocation(BudgetResourceType.EXTERNAL_CALL, 2),
    ]

    with pytest.raises(InsufficientBudgetError):
        service.reserve(budget.id, allocations=allocs)

    # Verify atomic roll-back / nothing reserved
    updated = service.get_budget(budget.id)
    assert updated.reserved_for(BudgetResourceType.OPERATION) == 0
    assert updated.reserved_for(BudgetResourceType.EXTERNAL_CALL) == 0


def test_service_reservation_idempotency_key():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 10},
    )

    allocs = [BudgetAllocation(BudgetResourceType.OPERATION, 1)]
    res1 = service.reserve(budget.id, allocations=allocs, idempotency_key="idem-key-1")
    res2 = service.reserve(budget.id, allocations=allocs, idempotency_key="idem-key-1")

    assert res1.id == res2.id
    updated = service.get_budget(budget.id)
    assert updated.reserved_for(BudgetResourceType.OPERATION) == 1


# ── 4. Confirmation Tests ──────────────────────────────────────────────────────


def test_service_confirm_reservation_transfers_reserved_to_used():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={
            BudgetResourceType.OPERATION: 10,
            BudgetResourceType.COST: Decimal("20.00"),
        },
    )

    res = service.reserve(
        budget.id,
        allocations=[
            BudgetAllocation(BudgetResourceType.OPERATION, 2),
            BudgetAllocation(BudgetResourceType.COST, Decimal("5.00")),
        ],
    )

    consumption = service.confirm(res.id)
    assert consumption.reservation_id == res.id
    assert consumption.outcome == BudgetConsumptionOutcome.SUCCESS

    updated = service.get_budget(budget.id)
    assert updated.reserved_for(BudgetResourceType.OPERATION) == 0
    assert updated.used_for(BudgetResourceType.OPERATION) == 2
    assert updated.reserved_for(BudgetResourceType.COST) == Decimal("0.00")
    assert updated.used_for(BudgetResourceType.COST) == Decimal("5.00")


def test_service_confirm_actual_lower_than_reserved():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.TOKEN: 1000},
    )

    res = service.reserve(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.TOKEN, 500)]
    )

    # Confirm only 300 actual tokens
    consumption = service.confirm(
        res.id, actual_allocations=[BudgetAllocation(BudgetResourceType.TOKEN, 300)]
    )
    assert consumption.allocations[0].amount == 300

    updated = service.get_budget(budget.id)
    assert updated.reserved_for(BudgetResourceType.TOKEN) == 0
    assert updated.used_for(BudgetResourceType.TOKEN) == 300
    assert updated.available_for(BudgetResourceType.TOKEN) == 700


def test_service_confirm_actual_higher_than_reserved_with_capacity():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.TOKEN: 1000},
    )

    res = service.reserve(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.TOKEN, 500)]
    )

    # Confirm 600 tokens (extra 100 available)
    service.confirm(
        res.id, actual_allocations=[BudgetAllocation(BudgetResourceType.TOKEN, 600)]
    )

    updated = service.get_budget(budget.id)
    assert updated.reserved_for(BudgetResourceType.TOKEN) == 0
    assert updated.used_for(BudgetResourceType.TOKEN) == 600


def test_service_confirm_actual_higher_than_reserved_without_capacity():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.TOKEN: 550},
    )

    res = service.reserve(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.TOKEN, 500)]
    )

    # Confirm 600 tokens when limit is 550 (available delta is 50, needed is 100)
    with pytest.raises(InsufficientBudgetError):
        service.confirm(
            res.id, actual_allocations=[BudgetAllocation(BudgetResourceType.TOKEN, 600)]
        )


def test_service_confirm_idempotency():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 10},
    )
    res = service.reserve(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)]
    )

    c1 = service.confirm(res.id)
    c2 = service.confirm(res.id)

    assert c1.id == c2.id
    updated = service.get_budget(budget.id)
    assert updated.used_for(BudgetResourceType.OPERATION) == 1


# ── 5. Release & Fail Tests ────────────────────────────────────────────────────


def test_service_release_reservation():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 10},
    )
    res = service.reserve(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 3)]
    )

    released_res = service.release(res.id)
    assert released_res.status == BudgetReservationStatus.RELEASED

    updated = service.get_budget(budget.id)
    assert updated.reserved_for(BudgetResourceType.OPERATION) == 0
    assert updated.used_for(BudgetResourceType.OPERATION) == 0


def test_service_fail_operation_with_partial_cost():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.COST: Decimal("50.00")},
    )
    res = service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.COST, Decimal("20.00"))],
    )

    # Failed after incurring 5.00 cost
    consumption = service.fail(
        res.id,
        consumed_allocations=[
            BudgetAllocation(BudgetResourceType.COST, Decimal("5.00"))
        ],
        reason="api_timeout",
    )
    assert consumption.outcome == BudgetConsumptionOutcome.FAILURE

    updated = service.get_budget(budget.id)
    assert updated.reserved_for(BudgetResourceType.COST) == Decimal("0.00")
    assert updated.used_for(BudgetResourceType.COST) == Decimal("5.00")


# ── 6. Expiration Tests ────────────────────────────────────────────────────────


def test_service_expire_due_reservations():
    service = ActionBudgetService()
    now_dt = _now()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 10},
        created_at=now_dt,
    )

    res = service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 2)],
        ttl_seconds=10,
        now=now_dt,
    )

    # Advance time by 15s
    future_now = now_dt + timedelta(seconds=15)
    expired = service.expire_due_reservations(now=future_now)
    assert len(expired) == 1
    assert expired[0].id == res.id

    updated = service.get_budget(budget.id)
    assert updated.reserved_for(BudgetResourceType.OPERATION) == 0

    with pytest.raises(BudgetReservationExpiredError):
        service.confirm(res.id, now=future_now)


# ── 7. Concurrency Tests (PARALLEL_OPERATION) ─────────────────────────────────


def test_concurrency_parallel_operation_slot_management():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.PARALLEL_OPERATION: 2},
    )

    res1 = service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.PARALLEL_OPERATION, 1)],
    )
    service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.PARALLEL_OPERATION, 1)],
    )

    # 3rd reservation should fail since limit is 2
    with pytest.raises((InsufficientBudgetError, BudgetExhaustedError)):
        service.reserve(
            budget.id,
            allocations=[BudgetAllocation(BudgetResourceType.PARALLEL_OPERATION, 1)],
        )

    # Confirming res1 releases its slot (does NOT accumulate in used)
    service.confirm(res1.id)
    updated = service.get_budget(budget.id)
    assert updated.used_for(BudgetResourceType.PARALLEL_OPERATION) == 0
    assert updated.reserved_for(BudgetResourceType.PARALLEL_OPERATION) == 1

    # Now a new parallel slot can be reserved
    res3 = service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.PARALLEL_OPERATION, 1)],
    )
    assert res3.status == BudgetReservationStatus.RESERVED


# ── 8. Duration & Pause/Resume Tests ──────────────────────────────────────────


def test_duration_and_pause_resume():
    service = ActionBudgetService()
    start_t = _now()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.DURATION_SECONDS: 100},
        created_at=start_t,
    )

    # 30 seconds elapsed
    t1 = start_t + timedelta(seconds=30)
    assert (
        service.get_available(budget.id, now=t1)[BudgetResourceType.DURATION_SECONDS]
        == 70
    )

    # Pause at t1
    paused_budget = service.pause(budget.id, now=t1)
    assert paused_budget.status == ActionBudgetStatus.PAUSED

    # While paused, reserving fails
    with pytest.raises(BudgetPausedError):
        service.reserve(
            budget.id,
            allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)],
            now=t1 + timedelta(seconds=20),
        )

    # Resume at t1 + 50s (paused for 50s)
    t2 = t1 + timedelta(seconds=50)
    resumed_budget = service.resume(budget.id, now=t2)
    assert resumed_budget.status == ActionBudgetStatus.ACTIVE
    assert resumed_budget.total_paused_seconds == 50.0

    # At t2 + 10s (total elapsed real time 90s, active time 40s), available duration is 60s
    t3 = t2 + timedelta(seconds=10)
    assert (
        service.get_available(budget.id, now=t3)[BudgetResourceType.DURATION_SECONDS]
        == 60
    )


# ── 9. Warning & Exhaustion Thresholds ────────────────────────────────────────


def test_warning_and_exhaustion_thresholds():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 10},
        warning_threshold=0.8,
    )

    # Reserve 8 operations (80% utilization)
    res1 = service.reserve(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 8)]
    )
    updated1 = service.get_budget(budget.id)
    assert updated1.status == ActionBudgetStatus.WARNING

    # Confirm 8 and reserve remaining 2 -> 100% utilization -> EXHAUSTED
    service.confirm(res1.id)
    service.reserve(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 2)]
    )
    updated2 = service.get_budget(budget.id)
    assert updated2.status == ActionBudgetStatus.EXHAUSTED

    with pytest.raises(BudgetExhaustedError):
        service.reserve(
            budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)]
        )


# ── 10. Budget Adjustments & Approval Integration ─────────────────────────────


def test_service_increase_budget_with_authorized_actor():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 10},
    )

    updated_budget, adj = service.increase_budget(
        budget.id,
        resource_type=BudgetResourceType.OPERATION,
        delta=5,
        actor_id="user-supervisor",
    )
    assert updated_budget.limit_for(BudgetResourceType.OPERATION) == 15
    assert adj.delta == 5
    assert adj.adjustment_type == BudgetAdjustmentType.INCREASE


def test_service_increase_budget_with_approval_resolution():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 10},
    )

    request = ApprovalRequest(
        id="appr-req-1",
        title="Increase budget",
        description="Increase budget description",
        requested_by="agent-run",
        agent_run_id="run-1",
        status=ApprovalRequestStatus.APPROVED,
    )
    resolution = ApprovalResolution(
        request_id=request.id,
        status=ApprovalRequestStatus.APPROVED,
        satisfied=True,
        may_execute=True,
        approval_count=1,
    )

    updated_budget, _adj = service.increase_budget(
        budget.id,
        resource_type=BudgetResourceType.OPERATION,
        new_limit=20,
        actor_id="agent-run",
        approval_resolution=resolution,
    )
    assert updated_budget.limit_for(BudgetResourceType.OPERATION) == 20


def test_service_increase_budget_rejects_unapproved_resolution():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 10},
    )

    request = ApprovalRequest(
        id="appr-req-1",
        title="Increase budget",
        description="Increase budget description",
        requested_by="agent-run",
        agent_run_id="run-1",
        status=ApprovalRequestStatus.REJECTED,
    )
    resolution = ApprovalResolution(
        request_id=request.id,
        status=ApprovalRequestStatus.REJECTED,
        satisfied=False,
        may_execute=False,
        rejection_count=1,
    )

    with pytest.raises(BudgetIncreaseNotAuthorizedError):
        service.increase_budget(
            budget.id,
            resource_type=BudgetResourceType.OPERATION,
            delta=5,
            approval_resolution=resolution,
        )


# ── 11. Adapters Tests ─────────────────────────────────────────────────────────


def test_action_budget_policy_adapter_deny_overrides_availability():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 10},
    )

    eval_res = service.evaluate(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)]
    )
    assert eval_res.allowed is True

    # Policy decision DENY
    policy_res = PolicyEvaluationResult(
        id="pol-res-1",
        request_id="req-1",
        status=runtime.PolicyEvaluationStatus.COMPLETED,
        decision=PolicyDecision.DENY,
        allowed=False,
        denied=True,
        requires_approval=False,
        requires_validation=False,
        requires_information=False,
        paused=False,
        reason_codes=("policy.security_block",),
    )

    combined_eval = ActionBudgetPolicyAdapter.apply_policy_to_budget_evaluation(
        eval_res, policy_res
    )
    assert combined_eval.allowed is False
    assert combined_eval.denied is True
    assert "budget.policy_denied" in combined_eval.reason_codes


def test_action_budget_autonomy_adapter_deny_overrides_availability():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 10},
    )

    eval_res = service.evaluate(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)]
    )

    autonomy_res = AutonomyEvaluationResult(
        id="aut-res-1",
        request_id="req-1",
        level=AgentAutonomyLevel.SUPERVISED_AUTONOMY,
        decision=AutonomyDecision.DENY,
        allowed=False,
        requires_approval=False,
        requires_validation=False,
        requires_rollback=False,
        denied=True,
        reason_codes=("autonomy.level_too_low",),
        warnings=(),
        evaluated_at=_now(),
    )

    combined_eval = ActionBudgetAutonomyAdapter.apply_autonomy_to_budget_evaluation(
        eval_res, autonomy_res
    )
    assert combined_eval.allowed is False
    assert combined_eval.denied is True
    assert "budget.autonomy_denied" in combined_eval.reason_codes


def test_action_budget_approval_adapter_requirement_creation():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.COST: Decimal("100.00")},
    )

    req = ActionBudgetApprovalAdapter.create_increase_requirement(
        budget=budget,
        resource_type=BudgetResourceType.COST,
        requested_delta=Decimal("50.00"),
        reason="Extra compute required",
    )
    assert req.source == ApprovalRequirementSource.BUDGET
    assert req.metadata["budget_id"] == budget.id
    assert req.metadata["resource_type"] == "cost"


# ── 12. Repository Thread Safety ───────────────────────────────────────────────


def test_in_memory_repository_thread_safety():
    repo = InMemoryActionBudgetRepository()
    budget = ActionBudget(
        id="b-concurrent",
        agent_run_id="r-concurrent",
        limits={BudgetResourceType.OPERATION: 1000},
    )
    repo.add_budget(budget)

    errors = []

    def _worker(idx: int):
        try:
            res = BudgetReservation(
                id=f"res-{idx}",
                budget_id="b-concurrent",
                agent_run_id="r-concurrent",
                allocations=(BudgetAllocation(BudgetResourceType.OPERATION, 1),),
                expires_at=_now() + timedelta(minutes=5),
            )
            repo.add_reservation(res)
        except ActionBudgetError as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    list_res = repo.list_reservations(budget_id="b-concurrent")
    assert len(list_res) == 50


# ── 13. Public Exports Check ───────────────────────────────────────────────────


def test_public_exports_completeness():
    expected = [
        "ActionBudget",
        "BudgetAllocation",
        "BudgetReservation",
        "BudgetConsumption",
        "BudgetAdjustment",
        "BudgetEvaluationResult",
        "ActionBudgetRepository",
        "InMemoryActionBudgetRepository",
        "ActionBudgetService",
        "ActionBudgetPolicyAdapter",
        "ActionBudgetAutonomyAdapter",
        "ActionBudgetApprovalAdapter",
        "BudgetResourceType",
        "ActionBudgetStatus",
        "BudgetReservationStatus",
        "BudgetConsumptionOutcome",
        "BudgetAdjustmentType",
        "ActionBudgetError",
        "InvalidActionBudgetContractError",
        "ActionBudgetNotFoundError",
        "DuplicateActionBudgetError",
        "BudgetReservationNotFoundError",
        "DuplicateBudgetReservationError",
        "BudgetConsumptionNotFoundError",
        "DuplicateBudgetConsumptionError",
        "BudgetAdjustmentNotFoundError",
        "DuplicateBudgetAdjustmentError",
        "BudgetExhaustedError",
        "BudgetPausedError",
        "BudgetCancelledError",
        "InsufficientBudgetError",
        "InvalidBudgetAllocationError",
        "BudgetReservationExpiredError",
        "BudgetReservationAlreadyResolvedError",
        "BudgetIncreaseNotAuthorizedError",
        "BudgetApprovalIntegrationError",
        "BudgetPolicyIntegrationError",
        "BudgetConcurrencyError",
    ]

    for item in expected:
        assert hasattr(runtime, item), f"Missing public export: {item}"
        assert item in runtime.__all__, f"Missing in __all__: {item}"
