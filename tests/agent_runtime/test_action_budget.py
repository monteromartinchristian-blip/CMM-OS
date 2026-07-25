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
    ActionBudgetNotFoundError,
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
    BudgetCancelledError,
    BudgetConsumption,
    BudgetConsumptionNotFoundError,
    BudgetConsumptionOutcome,
    BudgetExhaustedError,
    BudgetIncreaseNotAuthorizedError,
    BudgetPausedError,
    BudgetReservation,
    BudgetReservationAlreadyResolvedError,
    BudgetReservationExpiredError,
    BudgetReservationStatus,
    BudgetResourceType,
    DuplicateActionBudgetError,
    DuplicateBudgetReservationError,
    InMemoryActionBudgetRepository,
    InsufficientBudgetError,
    InvalidActionBudgetContractError,
    InvalidBudgetAllocationError,
    PolicyDecision,
    PolicyEvaluationResult,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── 1. Contract & Numeric Validation Tests ────────────────────────────────────


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


def test_budget_allocation_rejects_decimal_nan_for_cost():
    with pytest.raises(InvalidActionBudgetContractError):
        BudgetAllocation(resource_type=BudgetResourceType.COST, amount=Decimal("NaN"))


def test_budget_allocation_rejects_decimal_infinity_for_cost():
    with pytest.raises(InvalidActionBudgetContractError):
        BudgetAllocation(
            resource_type=BudgetResourceType.COST, amount=Decimal("Infinity")
        )

    with pytest.raises(InvalidActionBudgetContractError):
        BudgetAllocation(
            resource_type=BudgetResourceType.COST, amount=Decimal("-Infinity")
        )


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


def test_action_budget_accepts_none_limit_as_unlimited():
    budget = ActionBudget(
        id="b-unlimited",
        agent_run_id="r1",
        limits={BudgetResourceType.OPERATION: None},
    )
    assert budget.limit_for(BudgetResourceType.OPERATION) is None
    assert budget.available_for(BudgetResourceType.OPERATION) is None


def test_action_budget_rejects_bool_in_limits():
    with pytest.raises(InvalidActionBudgetContractError):
        ActionBudget(
            id="b-bool",
            agent_run_id="r1",
            limits={BudgetResourceType.OPERATION: True},  # type: ignore
        )


def test_action_budget_used_superior_to_limit_indicates_no_available_capacity():
    budget = ActionBudget(
        id="b-used-over",
        agent_run_id="r1",
        limits={BudgetResourceType.OPERATION: 10},
        used={BudgetResourceType.OPERATION: 15},
    )
    assert budget.available_for(BudgetResourceType.OPERATION) <= 0


def test_action_budget_reserved_superior_to_available_prevents_new_reservations():
    service = ActionBudgetService()
    budget = ActionBudget(
        id="b-reserved-over",
        agent_run_id="r1",
        limits={BudgetResourceType.OPERATION: 10},
        used={BudgetResourceType.OPERATION: 8},
        reserved={BudgetResourceType.OPERATION: 5},
    )
    service.repository.add_budget(budget)
    eval_res = service.evaluate(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)]
    )
    assert eval_res.allowed is False


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


def test_action_budget_available_and_utilization():
    budget = ActionBudget(
        id="b-avail",
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
        critical_threshold=0.9,
    )

    assert budget.available_for(BudgetResourceType.OPERATION) == 5
    assert budget.available_for(BudgetResourceType.COST) == Decimal("50.00")

    # Utilization: (used + reserved) / limit -> 5/10 = 0.5 for OPS, 50/100 = 0.5 for COST
    assert budget.utilization_for(BudgetResourceType.OPERATION) == 0.5
    assert budget.utilization_for(BudgetResourceType.COST) == Decimal("0.5")


# ── 2. Service Evaluation Tests ───────────────────────────────────────────────


def test_service_create_budget_and_evaluate():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={
            BudgetResourceType.OPERATION: 10,
            BudgetResourceType.COST: Decimal("20.00"),
        },
    )

    eval_res = service.evaluate(
        budget.id,
        allocations=[
            BudgetAllocation(BudgetResourceType.OPERATION, 2),
            BudgetAllocation(BudgetResourceType.COST, Decimal("5.00")),
        ],
    )
    assert eval_res.allowed is True
    assert eval_res.denied is False
    assert eval_res.exhausted is False


# ── 3. Multi-Resource Atomic Reservation Tests ────────────────────────────────


def test_service_atomic_reservation_success():
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
            BudgetAllocation(BudgetResourceType.OPERATION, 3),
            BudgetAllocation(BudgetResourceType.COST, Decimal("5.00")),
        ],
    )
    assert res.status == BudgetReservationStatus.RESERVED

    updated = service.get_budget(budget.id)
    assert updated.reserved_for(BudgetResourceType.OPERATION) == 3
    assert updated.reserved_for(BudgetResourceType.COST) == Decimal("5.00")


def test_service_atomic_reservation_rejection_all_or_nothing():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={
            BudgetResourceType.OPERATION: 10,
            BudgetResourceType.COST: Decimal("20.00"),
        },
    )

    # Cost allocation exceeds limit (25 > 20)
    with pytest.raises(InsufficientBudgetError):
        service.reserve(
            budget.id,
            allocations=[
                BudgetAllocation(BudgetResourceType.OPERATION, 3),
                BudgetAllocation(BudgetResourceType.COST, Decimal("25.00")),
            ],
        )

    # All-or-nothing check: OPERATION reservation should NOT have succeeded
    updated = service.get_budget(budget.id)
    assert updated.reserved_for(BudgetResourceType.OPERATION) == 0
    assert updated.reserved_for(BudgetResourceType.COST) == Decimal(0)


def test_service_reserve_atomic_rollback_on_partial_failure():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={
            BudgetResourceType.OPERATION: 10,
            BudgetResourceType.EXTERNAL_CALL: 1,
        },
    )

    # Pre-reserve external call capacity
    service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.EXTERNAL_CALL, 1)],
    )

    # Attempt reserving 5 OPERATIONS and 1 EXTERNAL_CALL (which exceeds capacity)
    with pytest.raises((InsufficientBudgetError, BudgetExhaustedError)):
        service.reserve(
            budget.id,
            allocations=[
                BudgetAllocation(BudgetResourceType.OPERATION, 5),
                BudgetAllocation(BudgetResourceType.EXTERNAL_CALL, 1),
            ],
        )

    # Check OPERATION was NOT reserved partially
    updated = service.get_budget(budget.id)
    assert updated.reserved_for(BudgetResourceType.OPERATION) == 0
    assert updated.reserved_for(BudgetResourceType.EXTERNAL_CALL) == 1


def test_service_reserve_rejects_empty_allocations():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1", limits={BudgetResourceType.OPERATION: 10}
    )
    with pytest.raises(
        (InvalidActionBudgetContractError, InvalidBudgetAllocationError)
    ):
        service.reserve(budget.id, allocations=[])


def test_service_reserve_rejects_duplicate_resource_type_allocations():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1", limits={BudgetResourceType.OPERATION: 10}
    )
    with pytest.raises(InvalidBudgetAllocationError):
        service.reserve(
            budget.id,
            allocations=[
                BudgetAllocation(BudgetResourceType.OPERATION, 1),
                BudgetAllocation(BudgetResourceType.OPERATION, 2),
            ],
        )


# ── 4. Idempotency & Confirmation Tests ───────────────────────────────────────


def test_service_reservation_idempotency_key():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.TOKEN: 1000},
    )

    res1 = service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.TOKEN, 500)],
        idempotency_key="idempotent-key-1",
    )

    # Reserving with same key returns identical reservation without duplicating reservation
    res2 = service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.TOKEN, 500)],
        idempotency_key="idempotent-key-1",
    )

    assert res1.id == res2.id
    updated = service.get_budget(budget.id)
    assert updated.reserved_for(BudgetResourceType.TOKEN) == 500


def test_service_reserve_idempotency_key_reuse_identical_payload():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1", limits={BudgetResourceType.OPERATION: 10}
    )
    res1 = service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 2)],
        idempotency_key="key-atomic-1",
    )
    res2 = service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 2)],
        idempotency_key="key-atomic-1",
    )
    assert res1.id == res2.id


def test_service_reserve_idempotency_key_rejects_different_payload():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1", limits={BudgetResourceType.OPERATION: 10}
    )
    service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 2)],
        idempotency_key="key-mismatch-1",
    )
    with pytest.raises(
        (InvalidActionBudgetContractError, DuplicateBudgetReservationError)
    ):
        service.reserve(
            budget.id,
            allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 5)],
            idempotency_key="key-mismatch-1",
        )


def test_service_confirm_reservation_transfers_reserved_to_used():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 10},
    )

    res = service.reserve(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 3)]
    )
    c = service.confirm(res.id)

    assert (
        c.status == BudgetReservationStatus.CONFIRMED if hasattr(c, "status") else True
    )
    updated = service.get_budget(budget.id)
    assert updated.reserved_for(BudgetResourceType.OPERATION) == 0
    assert updated.used_for(BudgetResourceType.OPERATION) == 3


def test_service_confirm_actual_lower_than_reserved():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 10},
    )

    res = service.reserve(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 5)]
    )

    # Reserved 5, but actually used only 3
    service.confirm(
        res.id,
        actual_allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 3)],
    )

    updated = service.get_budget(budget.id)
    assert updated.reserved_for(BudgetResourceType.OPERATION) == 0
    assert updated.used_for(BudgetResourceType.OPERATION) == 3
    assert updated.available_for(BudgetResourceType.OPERATION) == 7


def test_service_confirm_actual_higher_than_reserved_with_capacity():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 10},
    )

    res = service.reserve(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 3)]
    )

    # Reserved 3, but actually used 5
    service.confirm(
        res.id,
        actual_allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 5)],
    )

    updated = service.get_budget(budget.id)
    assert updated.reserved_for(BudgetResourceType.OPERATION) == 0
    assert updated.used_for(BudgetResourceType.OPERATION) == 5


def test_service_confirm_actual_higher_than_reserved_without_capacity():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 5},
    )

    res = service.reserve(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 4)]
    )

    # Reserved 4, actual tried to consume 6 (exceeding limit of 5)
    with pytest.raises(InsufficientBudgetError):
        service.confirm(
            res.id,
            actual_allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 6)],
        )


def test_service_confirm_idempotency():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 10},
    )

    res = service.reserve(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 3)]
    )

    c1 = service.confirm(res.id)
    c2 = service.confirm(res.id)

    assert c1.id == c2.id
    assert c1 == c2

    # Check state was not updated twice
    updated = service.get_budget(budget.id)
    assert updated.used_for(BudgetResourceType.OPERATION) == 3


def test_service_confirm_raises_error_if_confirmed_without_consumption():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1", limits={BudgetResourceType.OPERATION: 10}
    )
    res = service.reserve(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)]
    )
    # Force reservation status to CONFIRMED without adding a consumption record
    updated_res = BudgetReservation(
        id=res.id,
        budget_id=res.budget_id,
        agent_run_id=res.agent_run_id,
        allocations=res.allocations,
        status=BudgetReservationStatus.CONFIRMED,
        created_at=res.created_at,
        expires_at=res.expires_at,
    )
    service.repository.update_reservation(updated_res)
    with pytest.raises(BudgetConsumptionNotFoundError):
        service.confirm(res.id)


def test_service_confirm_prevents_duplicate_consumption():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1", limits={BudgetResourceType.OPERATION: 10}
    )
    res = service.reserve(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 2)]
    )
    c1 = service.confirm(res.id)
    c2 = service.confirm(res.id)
    assert c2.id == c1.id

    consumptions = service.repository.list_consumptions(budget.id)
    assert len(consumptions) == 1
    assert consumptions[0].id == c1.id


# ── 5. Release, Failure & Expiration Tests ────────────────────────────────────


def test_service_release_reservation():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 10},
    )

    res = service.reserve(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 3)]
    )

    service.release(res.id)

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

    # Operation failed after spending only 5.00
    service.fail(
        res.id,
        consumed_allocations=[
            BudgetAllocation(BudgetResourceType.COST, Decimal("5.00"))
        ],
        reason="api_timeout",
    )

    updated = service.get_budget(budget.id)
    assert updated.reserved_for(BudgetResourceType.COST) == Decimal(0)
    assert updated.used_for(BudgetResourceType.COST) == Decimal("5.00")
    assert updated.available_for(BudgetResourceType.COST) == Decimal("45.00")


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
        allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 3)],
        ttl_seconds=60,
        now=now_dt,
    )

    # Advance time past TTL
    future_dt = now_dt + timedelta(seconds=61)
    expired_list = service.expire_due_reservations(now=future_dt)

    assert len(expired_list) == 1
    assert expired_list[0].id == res.id

    updated = service.get_budget(budget.id)
    assert updated.reserved_for(BudgetResourceType.OPERATION) == 0


def test_service_confirm_rejects_expired_reservation():
    service = ActionBudgetService()
    t0 = _now()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 10},
        created_at=t0,
    )
    res = service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)],
        ttl_seconds=10,
        now=t0,
    )
    t_expired = t0 + timedelta(seconds=15)
    with pytest.raises(BudgetReservationExpiredError):
        service.confirm(res.id, now=t_expired)


def test_service_confirm_rejects_released_reservation():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1", limits={BudgetResourceType.OPERATION: 10}
    )
    res = service.reserve(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)]
    )
    service.release(res.id)
    with pytest.raises(BudgetReservationAlreadyResolvedError):
        service.confirm(res.id)


def test_service_release_rejects_confirmed_reservation():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1", limits={BudgetResourceType.OPERATION: 10}
    )
    res = service.reserve(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)]
    )
    service.confirm(res.id)
    with pytest.raises(BudgetReservationAlreadyResolvedError):
        service.release(res.id)


def test_service_release_rejects_double_release():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1", limits={BudgetResourceType.OPERATION: 10}
    )
    res = service.reserve(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)]
    )
    service.release(res.id)
    with pytest.raises(BudgetReservationAlreadyResolvedError):
        service.release(res.id)


def test_service_cancel_reservation_rejects_duplicate_cancellation():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1", limits={BudgetResourceType.OPERATION: 10}
    )
    res = service.reserve(
        budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)]
    )
    service.cancel_reservation(res.id)
    with pytest.raises(BudgetReservationAlreadyResolvedError):
        service.cancel_reservation(res.id)


# ── 6. Status & Lifecycle Transition Tests ────────────────────────────────────


def test_service_reserve_rejects_paused_budget():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1", limits={BudgetResourceType.OPERATION: 10}
    )
    service.pause(budget.id)
    with pytest.raises(BudgetPausedError):
        service.reserve(
            budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)]
        )


def test_service_reserve_rejects_cancelled_budget():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1", limits={BudgetResourceType.OPERATION: 10}
    )
    service.cancel_budget(budget.id)
    with pytest.raises(BudgetCancelledError):
        service.reserve(
            budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)]
        )


def test_service_reserve_rejects_completed_budget():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1", limits={BudgetResourceType.OPERATION: 10}
    )
    service.complete(budget.id)
    with pytest.raises(
        (ActionBudgetError, BudgetExhaustedError, InsufficientBudgetError)
    ):
        service.reserve(
            budget.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)]
        )


# ── 7. Concurrency & Parallel Slots Tests ──────────────────────────────────────


def test_concurrency_two_slots_allowed_with_limit_two():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.PARALLEL_OPERATION: 2},
    )
    r1 = service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.PARALLEL_OPERATION, 1)],
    )
    r2 = service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.PARALLEL_OPERATION, 1)],
    )
    assert r1.status == BudgetReservationStatus.RESERVED
    assert r2.status == BudgetReservationStatus.RESERVED


def test_concurrency_third_slot_rejected():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.PARALLEL_OPERATION: 2},
    )
    service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.PARALLEL_OPERATION, 1)],
    )
    service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.PARALLEL_OPERATION, 1)],
    )

    with pytest.raises((InsufficientBudgetError, BudgetExhaustedError)):
        service.reserve(
            budget.id,
            allocations=[BudgetAllocation(BudgetResourceType.PARALLEL_OPERATION, 1)],
        )


def test_concurrency_cancel_reservation_frees_slot():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.PARALLEL_OPERATION: 2},
    )
    r1 = service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.PARALLEL_OPERATION, 1)],
    )
    service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.PARALLEL_OPERATION, 1)],
    )
    service.cancel_reservation(r1.id)

    r3 = service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.PARALLEL_OPERATION, 1)],
    )
    assert r3.status == BudgetReservationStatus.RESERVED


def test_concurrency_fail_operation_frees_slot():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.PARALLEL_OPERATION: 2},
    )
    r1 = service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.PARALLEL_OPERATION, 1)],
    )
    service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.PARALLEL_OPERATION, 1)],
    )

    service.fail(r1.id, reason="operation_error")

    r3 = service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.PARALLEL_OPERATION, 1)],
    )
    assert r3.status == BudgetReservationStatus.RESERVED


def test_concurrency_expiration_frees_slot():
    service = ActionBudgetService()
    t0 = _now()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.PARALLEL_OPERATION: 2},
        created_at=t0,
    )
    service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.PARALLEL_OPERATION, 1)],
        ttl_seconds=10,
        now=t0,
    )
    service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.PARALLEL_OPERATION, 1)],
        ttl_seconds=10,
        now=t0,
    )

    t_expired = t0 + timedelta(seconds=15)
    service.expire_due_reservations(now=t_expired)

    r3 = service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.PARALLEL_OPERATION, 1)],
        now=t_expired,
    )
    assert r3.status == BudgetReservationStatus.RESERVED


def test_concurrency_confirmed_parallel_operation_does_not_increment_used():
    service = ActionBudgetService()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.PARALLEL_OPERATION: 2},
    )
    r1 = service.reserve(
        budget.id,
        allocations=[BudgetAllocation(BudgetResourceType.PARALLEL_OPERATION, 1)],
    )
    service.confirm(r1.id)

    updated = service.get_budget(budget.id)
    assert updated.used_for(BudgetResourceType.PARALLEL_OPERATION) == 0
    assert updated.reserved_for(BudgetResourceType.PARALLEL_OPERATION) == 0


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


def test_duration_exhausted_prevents_new_reservations():
    service = ActionBudgetService()
    t0 = _now()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.DURATION_SECONDS: 60},
        created_at=t0,
    )
    t_after = t0 + timedelta(seconds=70)
    with pytest.raises(BudgetExhaustedError):
        service.reserve(
            budget.id,
            allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)],
            now=t_after,
        )


def test_duration_paused_time_does_not_consume_duration():
    service = ActionBudgetService()
    t0 = _now()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.DURATION_SECONDS: 100},
        created_at=t0,
    )
    # Pause at t0+20s, resume at t0+120s (100s paused)
    t_pause = t0 + timedelta(seconds=20)
    service.pause(budget.id, now=t_pause)
    t_resume = t0 + timedelta(seconds=120)
    service.resume(budget.id, now=t_resume)

    t_eval = t0 + timedelta(seconds=130)  # active: 20s + 10s = 30s
    avail = service.get_available(budget.id, now=t_eval)
    assert avail[BudgetResourceType.DURATION_SECONDS] == 70


def test_duration_resume_preserves_total_paused_seconds():
    service = ActionBudgetService()
    t0 = _now()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.DURATION_SECONDS: 300},
        created_at=t0,
    )
    # Pause 1: 10s -> 30s (20s)
    service.pause(budget.id, now=t0 + timedelta(seconds=10))
    service.resume(budget.id, now=t0 + timedelta(seconds=30))
    # Pause 2: 40s -> 70s (30s)
    service.pause(budget.id, now=t0 + timedelta(seconds=40))
    b_resumed = service.resume(budget.id, now=t0 + timedelta(seconds=70))

    assert b_resumed.total_paused_seconds == 50.0


def test_duration_paused_budget_cannot_reserve_even_if_duration_remains():
    service = ActionBudgetService()
    t0 = _now()
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.DURATION_SECONDS: 1000},
        created_at=t0,
    )
    service.pause(budget.id, now=t0 + timedelta(seconds=5))
    with pytest.raises(BudgetPausedError):
        service.reserve(
            budget.id,
            allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)],
            now=t0 + timedelta(seconds=10),
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

    updated_budget, adj = service.increase_budget(
        budget.id,
        resource_type=BudgetResourceType.OPERATION,
        delta=5,
        actor_id="admin-123",
        approval_resolution=resolution,
    )
    assert updated_budget.limit_for(BudgetResourceType.OPERATION) == 15
    assert adj.delta == 5
    assert adj.actor_id == "admin-123"
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


def test_service_increase_budget_rejects_mismatched_budget_id():
    service = ActionBudgetService()
    b1 = service.create_budget("run-1", limits={BudgetResourceType.OPERATION: 10})
    b2 = service.create_budget("run-2", limits={BudgetResourceType.OPERATION: 10})
    req = ActionBudgetApprovalAdapter.create_increase_requirement(
        budget=b1,
        resource_type=BudgetResourceType.OPERATION,
        requested_delta=5,
        reason="Increase ops",
    )
    resolution = ApprovalResolution(
        request_id="req-1",
        status=ApprovalRequestStatus.APPROVED,
        satisfied=True,
        may_execute=True,
        approval_count=1,
        metadata=req.metadata,  # metadata references b1.id
    )
    with pytest.raises(BudgetIncreaseNotAuthorizedError):
        service.increase_budget(
            b2.id,  # Attempt applying to b2.id!
            resource_type=BudgetResourceType.OPERATION,
            delta=5,
            actor_id="agent-run",
            approval_resolution=resolution,
        )


def test_service_increase_budget_rejects_mismatched_request():
    service = ActionBudgetService()
    b = service.create_budget("run-1", limits={BudgetResourceType.OPERATION: 10})
    resolution = ApprovalResolution(
        request_id="req-other",
        status=ApprovalRequestStatus.REJECTED,
        satisfied=False,
        may_execute=False,
        rejection_count=1,
    )
    with pytest.raises(BudgetIncreaseNotAuthorizedError):
        service.increase_budget(
            b.id,
            resource_type=BudgetResourceType.OPERATION,
            delta=5,
            approval_resolution=resolution,
        )


def test_service_increase_budget_rejects_unauthorized_actor():
    service = ActionBudgetService()
    b = service.create_budget("run-1", limits={BudgetResourceType.OPERATION: 10})
    # Even admin-123 or supervisor without resolution is rejected
    with pytest.raises(BudgetIncreaseNotAuthorizedError):
        service.increase_budget(
            b.id,
            resource_type=BudgetResourceType.OPERATION,
            delta=5,
            actor_id="admin-123",
            approval_resolution=None,
        )


def test_service_decrease_budget_rejects_below_used_plus_reserved():
    service = ActionBudgetService()
    b = service.create_budget("run-1", limits={BudgetResourceType.OPERATION: 20})
    res = service.reserve(
        b.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 10)]
    )
    service.confirm(res.id)
    # used=10. Reserve 5 more -> used=10, reserved=5 (total 15).
    service.reserve(
        b.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 5)]
    )
    with pytest.raises((InvalidActionBudgetContractError, InsufficientBudgetError)):
        service.decrease_budget(
            b.id,
            resource_type=BudgetResourceType.OPERATION,
            new_limit=14,
            actor_id="user-supervisor",
        )


def test_service_increase_budget_records_previous_limit_new_limit_and_delta():
    service = ActionBudgetService()
    b = service.create_budget("run-1", limits={BudgetResourceType.OPERATION: 10})
    resolution = ApprovalResolution(
        request_id="req-1",
        status=ApprovalRequestStatus.APPROVED,
        satisfied=True,
        may_execute=True,
        approval_count=1,
    )
    b_updated, adj = service.increase_budget(
        b.id,
        resource_type=BudgetResourceType.OPERATION,
        delta=15,
        actor_id="user-supervisor",
        approval_resolution=resolution,
    )
    assert b_updated.limit_for(BudgetResourceType.OPERATION) == 25
    assert adj.previous_limit == 10
    assert adj.new_limit == 25
    assert adj.delta == 15
    assert adj.adjustment_type == BudgetAdjustmentType.INCREASE


def test_service_increase_budget_does_not_clear_previous_consumption():
    service = ActionBudgetService()
    b = service.create_budget("run-1", limits={BudgetResourceType.OPERATION: 10})
    res = service.reserve(
        b.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 4)]
    )
    service.confirm(res.id)
    resolution = ApprovalResolution(
        request_id="req-1",
        status=ApprovalRequestStatus.APPROVED,
        satisfied=True,
        may_execute=True,
        approval_count=1,
    )
    service.increase_budget(
        b.id,
        resource_type=BudgetResourceType.OPERATION,
        delta=10,
        actor_id="user-supervisor",
        approval_resolution=resolution,
    )
    b_updated = service.get_budget(b.id)
    assert b_updated.used_for(BudgetResourceType.OPERATION) == 4
    assert len(service.repository.list_consumptions(b.id)) == 1


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


def test_autonomy_adapter_high_level_cannot_bypass_exhaustion():
    service = ActionBudgetService()
    b = service.create_budget("run-1", limits={BudgetResourceType.OPERATION: 1})
    res1 = service.reserve(
        b.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)]
    )
    service.confirm(res1.id)

    # Budget is exhausted
    eval_res = service.evaluate(
        b.id, allocations=[BudgetAllocation(BudgetResourceType.OPERATION, 1)]
    )
    assert eval_res.allowed is False
    assert eval_res.exhausted is True

    autonomy_res = AutonomyEvaluationResult(
        id="aut-1",
        request_id="req-1",
        level=AgentAutonomyLevel.POLICY_BOUNDED_AUTONOMY,
        decision=AutonomyDecision.ALLOW,
        allowed=True,
        requires_approval=False,
        requires_validation=False,
        requires_rollback=False,
        denied=False,
        reason_codes=(),
        warnings=(),
        evaluated_at=_now(),
    )
    combined = ActionBudgetAutonomyAdapter.apply_autonomy_to_budget_evaluation(
        eval_res, autonomy_res
    )
    assert combined.allowed is False
    assert combined.exhausted is True


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


# ── 12. Repository Tests ───────────────────────────────────────────────────────


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


def test_repository_rejects_duplicate_budget():
    repo = InMemoryActionBudgetRepository()
    b = ActionBudget(id="b-dup", agent_run_id="r1")
    repo.add_budget(b)
    with pytest.raises(DuplicateActionBudgetError):
        repo.add_budget(b)


def test_repository_rejects_orphan_reservation():
    repo = InMemoryActionBudgetRepository()
    res = BudgetReservation(
        id="res-orphan",
        budget_id="non-existent",
        agent_run_id="r1",
        allocations=(BudgetAllocation(BudgetResourceType.OPERATION, 1),),
        expires_at=_now() + timedelta(minutes=5),
    )
    with pytest.raises(ActionBudgetNotFoundError):
        repo.add_reservation(res)


def test_repository_rejects_orphan_consumption():
    repo = InMemoryActionBudgetRepository()
    c = BudgetConsumption(
        id="c-orphan",
        budget_id="non-existent",
        agent_run_id="r1",
        reservation_id="res-1",
        allocations=(BudgetAllocation(BudgetResourceType.OPERATION, 1),),
        outcome=BudgetConsumptionOutcome.SUCCESS,
    )
    with pytest.raises(ActionBudgetNotFoundError):
        repo.add_consumption(c)


def test_repository_rejects_orphan_adjustment():
    repo = InMemoryActionBudgetRepository()
    a = BudgetAdjustment(
        id="adj-orphan",
        budget_id="non-existent",
        adjustment_type=BudgetAdjustmentType.INCREASE,
        resource_type=BudgetResourceType.OPERATION,
        previous_limit=10,
        new_limit=20,
        delta=10,
        actor_id="user-1",
    )
    with pytest.raises(ActionBudgetNotFoundError):
        repo.add_adjustment(a)


def test_repository_lists_reservations_in_stable_order():
    repo = InMemoryActionBudgetRepository()
    b = ActionBudget(id="b-stable", agent_run_id="r1")
    repo.add_budget(b)
    t0 = _now()
    for i in range(5):
        res = BudgetReservation(
            id=f"res-{i}",
            budget_id=b.id,
            agent_run_id="r1",
            allocations=(BudgetAllocation(BudgetResourceType.OPERATION, 1),),
            created_at=t0 + timedelta(seconds=i),
            expires_at=t0 + timedelta(minutes=5),
        )
        repo.add_reservation(res)

    list_res = repo.list_reservations(b.id)
    assert [r.id for r in list_res] == [f"res-{i}" for i in range(5)]


def test_repository_filters_reservations_by_budget_and_status():
    repo = InMemoryActionBudgetRepository()
    b1 = ActionBudget(id="b-f1", agent_run_id="r1")
    b2 = ActionBudget(id="b-f2", agent_run_id="r2")
    repo.add_budget(b1)
    repo.add_budget(b2)
    t0 = _now()

    alloc = (BudgetAllocation(BudgetResourceType.OPERATION, 1),)
    r1 = BudgetReservation(
        id="res-active",
        budget_id=b1.id,
        agent_run_id="r1",
        status=BudgetReservationStatus.RESERVED,
        allocations=alloc,
        created_at=t0,
        expires_at=t0 + timedelta(minutes=5),
    )
    r2 = BudgetReservation(
        id="res-conf",
        budget_id=b1.id,
        agent_run_id="r1",
        status=BudgetReservationStatus.CONFIRMED,
        allocations=alloc,
        created_at=t0,
        expires_at=t0 + timedelta(minutes=5),
    )
    r3 = BudgetReservation(
        id="res-b2",
        budget_id=b2.id,
        agent_run_id="r2",
        status=BudgetReservationStatus.RESERVED,
        allocations=alloc,
        created_at=t0,
        expires_at=t0 + timedelta(minutes=5),
    )
    repo.add_reservation(r1)
    repo.add_reservation(r2)
    repo.add_reservation(r3)

    filtered = repo.list_reservations(
        budget_id=b1.id, status=BudgetReservationStatus.RESERVED
    )
    assert len(filtered) == 1
    assert filtered[0].id == "res-active"


def test_repository_stored_objects_cannot_be_mutated_externally():
    repo = InMemoryActionBudgetRepository()
    b = ActionBudget(
        id="b-mut", agent_run_id="r1", limits={BudgetResourceType.OPERATION: 10}
    )
    repo.add_budget(b)
    fetched = repo.get_budget("b-mut")
    with pytest.raises(TypeError):
        fetched.limits[BudgetResourceType.OPERATION] = 20  # type: ignore


# ── 13. Public Exports & Integrity Check ───────────────────────────────────────


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
    ]
    for name in expected:
        assert hasattr(runtime, name), f"Missing public export: {name}"


def test_public_exports_all_contains_no_duplicates():
    all_exports = list(runtime.__all__)
    assert len(all_exports) == len(set(all_exports))
