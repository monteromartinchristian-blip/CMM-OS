"""Phase 9.11 – Action Budget Service.

Provides the core deterministic, audit-trail preserved management service for ActionBudget,
including atomic multi-resource reservation, confirmed consumption, failure accounting,
reservation expiration, pause/resume time tracking, and authorized limit adjustments.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType

from .action_budget_adapters import ActionBudgetApprovalAdapter
from .action_budget_contracts import (
    ActionBudget,
    BudgetAdjustment,
    BudgetAllocation,
    BudgetConsumption,
    BudgetEvaluationResult,
    BudgetReservation,
)
from .action_budget_repository import (
    ActionBudgetRepository,
    InMemoryActionBudgetRepository,
)
from .approval_contracts import ApprovalRequirement, ApprovalResolution
from .enums import (
    ActionBudgetStatus,
    ApprovalRequirementSource,
    BudgetAdjustmentType,
    BudgetConsumptionOutcome,
    BudgetReservationStatus,
    BudgetResourceType,
)
from .errors import (
    BudgetCancelledError,
    BudgetConsumptionNotFoundError,
    BudgetExhaustedError,
    BudgetIncreaseNotAuthorizedError,
    BudgetPausedError,
    BudgetReservationAlreadyResolvedError,
    BudgetReservationExpiredError,
    DuplicateBudgetReservationError,
    InsufficientBudgetError,
    InvalidActionBudgetContractError,
    InvalidBudgetAllocationError,
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _gen_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _serialize_amount(val: int | Decimal | None) -> int | str | None:
    if val is None:
        return None
    if isinstance(val, Decimal):
        return str(val)
    return val


def _recalculate_status(
    budget: ActionBudget,
    used: dict[BudgetResourceType, int | Decimal],
    reserved: dict[BudgetResourceType, int | Decimal],
) -> ActionBudgetStatus:
    """Recalculate budget status based on current limits, used, and reserved allocations."""
    if budget.status in (
        ActionBudgetStatus.PAUSED,
        ActionBudgetStatus.CANCELLED,
        ActionBudgetStatus.COMPLETED,
    ):
        return budget.status

    max_util = 0.0
    for res_t, limit in budget.limits.items():
        if limit is not None and limit > 0:
            res_val = reserved.get(
                res_t, Decimal(0) if res_t == BudgetResourceType.COST else 0
            )
            used_val = used.get(
                res_t, Decimal(0) if res_t == BudgetResourceType.COST else 0
            )
            u = float(used_val + res_val) / float(limit)
            max_util = max(max_util, u)

    if max_util >= 1.0:
        return ActionBudgetStatus.EXHAUSTED
    if max_util >= budget.warning_threshold:
        return ActionBudgetStatus.WARNING
    if budget.status == ActionBudgetStatus.INCREASED:
        return ActionBudgetStatus.INCREASED
    return ActionBudgetStatus.ACTIVE


class ActionBudgetService:
    """Core service orchestrating ActionBudget lifecycles, reservations, and consumptions."""

    def __init__(self, repository: ActionBudgetRepository | None = None) -> None:
        self.repository: ActionBudgetRepository = (
            repository if repository is not None else InMemoryActionBudgetRepository()
        )

    def create_budget(
        self,
        agent_run_id: str,
        limits: dict[BudgetResourceType | str, int | Decimal | None],
        currency: str = "EUR",
        warning_threshold: float = 0.8,
        critical_threshold: float = 0.95,
        budget_id: str | None = None,
        metadata: dict | None = None,
        created_at: datetime | None = None,
    ) -> ActionBudget:
        """Create and store a new ActionBudget for an agent run."""
        ref_time = created_at if created_at is not None else _now_utc()
        b_id = budget_id if budget_id is not None else _gen_id("budget")

        parsed_limits: dict[BudgetResourceType, int | Decimal | None] = {}
        parsed_used: dict[BudgetResourceType, int | Decimal] = {}
        parsed_reserved: dict[BudgetResourceType, int | Decimal] = {}

        for k, v in limits.items():
            rt = BudgetResourceType(k) if isinstance(k, str) else k
            parsed_limits[rt] = v
            zero_val = Decimal(0) if rt == BudgetResourceType.COST else 0
            parsed_used[rt] = zero_val
            parsed_reserved[rt] = zero_val

        budget = ActionBudget(
            id=b_id,
            agent_run_id=agent_run_id,
            limits=parsed_limits,
            used=parsed_used,
            reserved=parsed_reserved,
            currency=currency,
            warning_threshold=warning_threshold,
            critical_threshold=critical_threshold,
            status=ActionBudgetStatus.ACTIVE,
            version=1,
            created_at=ref_time,
            updated_at=ref_time,
            started_at=ref_time,
            metadata=metadata or {},
        )
        self.repository.add_budget(budget)
        return budget

    def get_budget(self, budget_id: str) -> ActionBudget:
        """Get ActionBudget by ID."""
        return self.repository.get_budget(budget_id)

    def get_usage(self, budget_id: str) -> dict[BudgetResourceType, int | Decimal]:
        """Return shallow copy of used quantities for a budget."""
        budget = self.repository.get_budget(budget_id)
        return dict(budget.used)

    def get_available(
        self, budget_id: str, now: datetime | None = None
    ) -> dict[BudgetResourceType, int | Decimal | None]:
        """Return available quantities for all configured limits of a budget."""
        budget = self.repository.get_budget(budget_id)
        ref_now = now if now is not None else _now_utc()
        res: dict[BudgetResourceType, int | Decimal | None] = {}
        for r_type in budget.limits:
            res[r_type] = budget.available_for(r_type, now=ref_now)
        return res

    def is_exhausted(self, budget_id: str, now: datetime | None = None) -> bool:
        """Check if budget is exhausted."""
        budget = self.repository.get_budget(budget_id)
        if budget.status == ActionBudgetStatus.EXHAUSTED:
            return True
        ref_now = now if now is not None else _now_utc()
        # Check duration limit
        dur_limit = budget.limit_for(BudgetResourceType.DURATION_SECONDS)
        if dur_limit is not None:
            avail_dur = budget.available_for(
                BudgetResourceType.DURATION_SECONDS, now=ref_now
            )
            if avail_dur is not None and avail_dur <= 0:
                return True
        return False

    def evaluate(
        self,
        budget_id: str,
        allocations: Sequence[BudgetAllocation],
        now: datetime | None = None,
    ) -> BudgetEvaluationResult:
        """Evaluate if requested allocations can be reserved on budget_id."""
        ref_now = now if now is not None else _now_utc()
        budget = self.repository.get_budget(budget_id)

        if not allocations:
            raise InvalidBudgetAllocationError("allocations sequence cannot be empty")

        seen_types: set[BudgetResourceType] = set()
        for alloc in allocations:
            if alloc.resource_type in seen_types:
                raise InvalidBudgetAllocationError(
                    f"Duplicate resource_type {alloc.resource_type.value!r} in allocations"
                )
            seen_types.add(alloc.resource_type)

        reason_codes: list[str] = []
        is_allowed = True
        is_warning = False
        is_exhausted = budget.status == ActionBudgetStatus.EXHAUSTED

        if budget.status == ActionBudgetStatus.PAUSED:
            return BudgetEvaluationResult(
                budget_id=budget_id,
                allowed=False,
                denied=True,
                warning=False,
                exhausted=False,
                status=budget.status,
                requested_allocations=tuple(allocations),
                available=self.get_available(budget_id, now=ref_now),
                reason_codes=("budget.paused",),
                evaluated_at=ref_now,
            )

        if budget.status == ActionBudgetStatus.CANCELLED:
            return BudgetEvaluationResult(
                budget_id=budget_id,
                allowed=False,
                denied=True,
                warning=False,
                exhausted=False,
                status=budget.status,
                requested_allocations=tuple(allocations),
                available=self.get_available(budget_id, now=ref_now),
                reason_codes=("budget.cancelled",),
                evaluated_at=ref_now,
            )

        if budget.status == ActionBudgetStatus.COMPLETED:
            return BudgetEvaluationResult(
                budget_id=budget_id,
                allowed=False,
                denied=True,
                warning=False,
                exhausted=False,
                status=budget.status,
                requested_allocations=tuple(allocations),
                available=self.get_available(budget_id, now=ref_now),
                reason_codes=("budget.completed",),
                evaluated_at=ref_now,
            )

        # Check duration limit expiration
        dur_avail = budget.available_for(
            BudgetResourceType.DURATION_SECONDS, now=ref_now
        )
        if dur_avail is not None and dur_avail <= 0:
            is_allowed = False
            is_exhausted = True
            reason_codes.append("budget.duration_exceeded")

        # Evaluate requested allocations against available capacity
        available_map: dict[BudgetResourceType, int | Decimal | None] = {}
        for alloc in allocations:
            res_t = alloc.resource_type
            avail = budget.available_for(res_t, now=ref_now)
            available_map[res_t] = avail

            if avail is not None and alloc.amount > avail:
                is_allowed = False
                reason_codes.append(f"budget.insufficient_{res_t.value}")

            # Check utilization thresholds
            util = budget.utilization_for(res_t, now=ref_now)
            if util >= budget.warning_threshold:
                is_warning = True
                if "budget.warning_threshold_reached" not in reason_codes:
                    reason_codes.append("budget.warning_threshold_reached")

        if is_allowed and not reason_codes:
            reason_codes.append("budget.available")

        if is_exhausted and "budget.exhausted" not in reason_codes:
            reason_codes.append("budget.exhausted")

        return BudgetEvaluationResult(
            budget_id=budget_id,
            allowed=is_allowed,
            denied=not is_allowed,
            warning=is_warning,
            exhausted=is_exhausted,
            status=budget.status,
            requested_allocations=tuple(allocations),
            available=available_map,
            reason_codes=tuple(reason_codes),
            evaluated_at=ref_now,
        )

    def reserve(
        self,
        budget_id: str,
        allocations: Sequence[BudgetAllocation],
        operation_id: str | None = None,
        workflow_id: str | None = None,
        idempotency_key: str | None = None,
        ttl_seconds: int = 300,
        reservation_id: str | None = None,
        now: datetime | None = None,
    ) -> BudgetReservation:
        """Atomically reserve all requested allocations or fail completely."""
        ref_now = now if now is not None else _now_utc()
        budget = self.repository.get_budget(budget_id)

        # Idempotency check
        if idempotency_key:
            existing = self.repository.find_reservation_by_idempotency_key(
                budget_id, idempotency_key
            )
            if existing:
                if (
                    tuple(existing.allocations) != tuple(allocations)
                    or existing.operation_id != operation_id
                    or existing.workflow_id != workflow_id
                ):
                    raise DuplicateBudgetReservationError(
                        f"Idempotency key {idempotency_key!r} already used with different payload"
                    )
                return existing

        eval_res = self.evaluate(budget_id, allocations, now=ref_now)
        if not eval_res.allowed:
            if "budget.paused" in eval_res.reason_codes:
                raise BudgetPausedError(f"Budget {budget_id!r} is paused")
            if "budget.cancelled" in eval_res.reason_codes:
                raise BudgetCancelledError(f"Budget {budget_id!r} is cancelled")
            if eval_res.exhausted or "budget.exhausted" in eval_res.reason_codes:
                raise BudgetExhaustedError(f"Budget {budget_id!r} is exhausted")
            raise InsufficientBudgetError(
                f"Insufficient budget for reservation on {budget_id!r}: {eval_res.reason_codes}"
            )

        # Perform atomic reservation updates on budget.reserved map
        new_reserved = dict(budget.reserved)
        for alloc in allocations:
            res_t = alloc.resource_type
            curr_res = new_reserved.get(
                res_t, Decimal(0) if res_t == BudgetResourceType.COST else 0
            )
            new_reserved[res_t] = curr_res + alloc.amount

        new_status = _recalculate_status(budget, dict(budget.used), new_reserved)

        updated_budget = ActionBudget(
            id=budget.id,
            agent_run_id=budget.agent_run_id,
            limits=dict(budget.limits),
            used=dict(budget.used),
            reserved=new_reserved,
            currency=budget.currency,
            warning_threshold=budget.warning_threshold,
            critical_threshold=budget.critical_threshold,
            status=new_status,
            version=budget.version + 1,
            created_at=budget.created_at,
            updated_at=ref_now,
            started_at=budget.started_at,
            paused_at=budget.paused_at,
            total_paused_seconds=budget.total_paused_seconds,
            metadata=dict(budget.metadata),
        )

        res_id = (
            reservation_id if reservation_id is not None else _gen_id("reservation")
        )
        expires = ref_now + timedelta(seconds=ttl_seconds)

        reservation = BudgetReservation(
            id=res_id,
            budget_id=budget.id,
            agent_run_id=budget.agent_run_id,
            allocations=tuple(allocations),
            operation_id=operation_id,
            workflow_id=workflow_id,
            idempotency_key=idempotency_key,
            status=BudgetReservationStatus.RESERVED,
            created_at=ref_now,
            expires_at=expires,
            metadata={},
        )

        self.repository.update_budget(updated_budget)
        self.repository.add_reservation(reservation)
        return reservation

    def confirm(
        self,
        reservation_id: str,
        actual_allocations: Sequence[BudgetAllocation] | None = None,
        outcome: BudgetConsumptionOutcome = BudgetConsumptionOutcome.SUCCESS,
        consumed_at: datetime | None = None,
        now: datetime | None = None,
    ) -> BudgetConsumption:
        """Confirm consumption of a reserved budget, transferring reserved -> used."""
        ref_now = now if now is not None else _now_utc()
        res_time = consumed_at if consumed_at is not None else ref_now
        reservation = self.repository.get_reservation(reservation_id)

        if reservation.status == BudgetReservationStatus.CONFIRMED:
            consumptions = self.repository.list_consumptions(
                reservation_id=reservation_id
            )
            if len(consumptions) == 1:
                return consumptions[0]
            raise BudgetConsumptionNotFoundError(
                f"Inconsistent state: reservation {reservation_id!r} is CONFIRMED but found {len(consumptions)} consumption records"
            )

        if reservation.status in (
            BudgetReservationStatus.RELEASED,
            BudgetReservationStatus.CANCELLED,
            BudgetReservationStatus.FAILED,
        ):
            raise BudgetReservationAlreadyResolvedError(
                f"Reservation {reservation_id!r} is already resolved as {reservation.status.value}"
            )

        if (
            reservation.status == BudgetReservationStatus.EXPIRED
            or reservation.is_expired(ref_now)
        ):
            if reservation.status != BudgetReservationStatus.EXPIRED:
                self.expire_due_reservations(now=ref_now)
            raise BudgetReservationExpiredError(
                f"Reservation {reservation_id!r} has expired"
            )

        budget = self.repository.get_budget(reservation.budget_id)

        target_allocs = (
            tuple(actual_allocations)
            if actual_allocations is not None
            else reservation.allocations
        )

        reserved_map = {a.resource_type: a.amount for a in reservation.allocations}
        actual_map = {a.resource_type: a.amount for a in target_allocs}

        # Validate that if actual > reserved, extra budget is available
        for res_t, actual_amt in actual_map.items():
            res_amt = reserved_map.get(
                res_t, Decimal(0) if res_t == BudgetResourceType.COST else 0
            )
            if actual_amt > res_amt:
                extra_delta = actual_amt - res_amt
                avail = budget.available_for(res_t, now=ref_now)
                if avail is not None and extra_delta > avail:
                    raise InsufficientBudgetError(
                        f"Actual consumption of {res_t.value} exceeds reservation and available budget"
                    )

        new_reserved = dict(budget.reserved)
        new_used = dict(budget.used)

        # Release reserved amounts
        for res_t, res_amt in reserved_map.items():
            curr_res = new_reserved.get(
                res_t, Decimal(0) if res_t == BudgetResourceType.COST else 0
            )
            new_reserved[res_t] = max(
                Decimal(0) if res_t == BudgetResourceType.COST else 0,
                curr_res - res_amt,
            )

        # Apply actual consumption to used (except PARALLEL_OPERATION which is concurrent only)
        for res_t, actual_amt in actual_map.items():
            if res_t != BudgetResourceType.PARALLEL_OPERATION:
                curr_used = new_used.get(
                    res_t, Decimal(0) if res_t == BudgetResourceType.COST else 0
                )
                new_used[res_t] = curr_used + actual_amt

        new_status = _recalculate_status(budget, new_used, new_reserved)

        updated_budget = ActionBudget(
            id=budget.id,
            agent_run_id=budget.agent_run_id,
            limits=dict(budget.limits),
            used=new_used,
            reserved=new_reserved,
            currency=budget.currency,
            warning_threshold=budget.warning_threshold,
            critical_threshold=budget.critical_threshold,
            status=new_status,
            version=budget.version + 1,
            created_at=budget.created_at,
            updated_at=ref_now,
            started_at=budget.started_at,
            paused_at=budget.paused_at,
            total_paused_seconds=budget.total_paused_seconds,
            metadata=dict(budget.metadata),
        )

        updated_reservation = BudgetReservation(
            id=reservation.id,
            budget_id=reservation.budget_id,
            agent_run_id=reservation.agent_run_id,
            allocations=reservation.allocations,
            operation_id=reservation.operation_id,
            workflow_id=reservation.workflow_id,
            idempotency_key=reservation.idempotency_key,
            status=BudgetReservationStatus.CONFIRMED,
            created_at=reservation.created_at,
            expires_at=reservation.expires_at,
            confirmed_at=res_time,
            released_at=reservation.released_at,
            failed_at=reservation.failed_at,
            metadata=dict(reservation.metadata),
        )

        consumption = BudgetConsumption(
            id=_gen_id("consumption"),
            budget_id=budget.id,
            agent_run_id=budget.agent_run_id,
            reservation_id=reservation.id,
            allocations=target_allocs,
            outcome=outcome,
            operation_id=reservation.operation_id,
            consumed_at=res_time,
            metadata={},
        )

        self.repository.update_budget(updated_budget)
        self.repository.update_reservation(updated_reservation)
        self.repository.add_consumption(consumption)
        return consumption

    def release(
        self,
        reservation_id: str,
        reason: str = "cancelled",
        now: datetime | None = None,
    ) -> BudgetReservation:
        """Release a reservation without consuming resources."""
        ref_now = now if now is not None else _now_utc()
        reservation = self.repository.get_reservation(reservation_id)

        if reservation.status != BudgetReservationStatus.RESERVED:
            raise BudgetReservationAlreadyResolvedError(
                f"Reservation {reservation_id!r} is already resolved as {reservation.status.value}"
            )

        budget = self.repository.get_budget(reservation.budget_id)

        new_reserved = dict(budget.reserved)
        for alloc in reservation.allocations:
            res_t = alloc.resource_type
            curr_res = new_reserved.get(
                res_t, Decimal(0) if res_t == BudgetResourceType.COST else 0
            )
            new_reserved[res_t] = max(
                Decimal(0) if res_t == BudgetResourceType.COST else 0,
                curr_res - alloc.amount,
            )

        new_status = _recalculate_status(budget, dict(budget.used), new_reserved)

        updated_budget = ActionBudget(
            id=budget.id,
            agent_run_id=budget.agent_run_id,
            limits=dict(budget.limits),
            used=dict(budget.used),
            reserved=new_reserved,
            currency=budget.currency,
            warning_threshold=budget.warning_threshold,
            critical_threshold=budget.critical_threshold,
            status=new_status,
            version=budget.version + 1,
            created_at=budget.created_at,
            updated_at=ref_now,
            started_at=budget.started_at,
            paused_at=budget.paused_at,
            total_paused_seconds=budget.total_paused_seconds,
            metadata=dict(budget.metadata),
        )

        updated_reservation = BudgetReservation(
            id=reservation.id,
            budget_id=reservation.budget_id,
            agent_run_id=reservation.agent_run_id,
            allocations=reservation.allocations,
            operation_id=reservation.operation_id,
            workflow_id=reservation.workflow_id,
            idempotency_key=reservation.idempotency_key,
            status=BudgetReservationStatus.RELEASED,
            created_at=reservation.created_at,
            expires_at=reservation.expires_at,
            confirmed_at=reservation.confirmed_at,
            released_at=ref_now,
            failed_at=reservation.failed_at,
            metadata=dict(reservation.metadata),
        )

        self.repository.update_budget(updated_budget)
        self.repository.update_reservation(updated_reservation)
        return updated_reservation

    def fail(
        self,
        reservation_id: str,
        consumed_allocations: Sequence[BudgetAllocation] | None = None,
        released_allocations: Sequence[BudgetAllocation] | None = None,
        reason: str = "operation_failed",
        now: datetime | None = None,
    ) -> BudgetConsumption:
        """Record a failed operation, accounting for incurred costs and releasing remaining reserved budget."""
        ref_now = now if now is not None else _now_utc()
        reservation = self.repository.get_reservation(reservation_id)

        if reservation.status in (
            BudgetReservationStatus.CONFIRMED,
            BudgetReservationStatus.RELEASED,
            BudgetReservationStatus.CANCELLED,
        ):
            raise BudgetReservationAlreadyResolvedError(
                f"Cannot fail reservation {reservation_id!r} in status {reservation.status.value}"
            )

        budget = self.repository.get_budget(reservation.budget_id)

        actual_consumed = (
            tuple(consumed_allocations) if consumed_allocations is not None else ()
        )

        reserved_map = {a.resource_type: a.amount for a in reservation.allocations}
        consumed_map = {a.resource_type: a.amount for a in actual_consumed}

        new_reserved = dict(budget.reserved)
        new_used = dict(budget.used)

        for res_t, res_amt in reserved_map.items():
            curr_res = new_reserved.get(
                res_t, Decimal(0) if res_t == BudgetResourceType.COST else 0
            )
            new_reserved[res_t] = max(
                Decimal(0) if res_t == BudgetResourceType.COST else 0,
                curr_res - res_amt,
            )

        for res_t, c_amt in consumed_map.items():
            if res_t != BudgetResourceType.PARALLEL_OPERATION:
                curr_used = new_used.get(
                    res_t, Decimal(0) if res_t == BudgetResourceType.COST else 0
                )
                new_used[res_t] = curr_used + c_amt

        updated_budget = ActionBudget(
            id=budget.id,
            agent_run_id=budget.agent_run_id,
            limits=dict(budget.limits),
            used=new_used,
            reserved=new_reserved,
            currency=budget.currency,
            warning_threshold=budget.warning_threshold,
            critical_threshold=budget.critical_threshold,
            status=budget.status,
            version=budget.version + 1,
            created_at=budget.created_at,
            updated_at=ref_now,
            started_at=budget.started_at,
            paused_at=budget.paused_at,
            total_paused_seconds=budget.total_paused_seconds,
            metadata=dict(budget.metadata),
        )

        updated_reservation = BudgetReservation(
            id=reservation.id,
            budget_id=reservation.budget_id,
            agent_run_id=reservation.agent_run_id,
            allocations=reservation.allocations,
            operation_id=reservation.operation_id,
            workflow_id=reservation.workflow_id,
            idempotency_key=reservation.idempotency_key,
            status=BudgetReservationStatus.FAILED,
            created_at=reservation.created_at,
            expires_at=reservation.expires_at,
            confirmed_at=reservation.confirmed_at,
            released_at=reservation.released_at,
            failed_at=ref_now,
            metadata=dict(reservation.metadata),
        )

        consumption = BudgetConsumption(
            id=_gen_id("consumption"),
            budget_id=budget.id,
            agent_run_id=budget.agent_run_id,
            reservation_id=reservation.id,
            allocations=actual_consumed,
            outcome=BudgetConsumptionOutcome.FAILURE,
            operation_id=reservation.operation_id,
            consumed_at=ref_now,
            metadata={"failure_reason": reason},
        )

        self.repository.update_budget(updated_budget)
        self.repository.update_reservation(updated_reservation)
        self.repository.add_consumption(consumption)
        return consumption

    def cancel_reservation(
        self, reservation_id: str, now: datetime | None = None
    ) -> BudgetReservation:
        """Cancel a reservation (alias for release with status CANCELLED)."""
        ref_now = now if now is not None else _now_utc()
        reservation = self.release(reservation_id, reason="cancelled", now=ref_now)
        updated_reservation = BudgetReservation(
            id=reservation.id,
            budget_id=reservation.budget_id,
            agent_run_id=reservation.agent_run_id,
            allocations=reservation.allocations,
            operation_id=reservation.operation_id,
            workflow_id=reservation.workflow_id,
            idempotency_key=reservation.idempotency_key,
            status=BudgetReservationStatus.CANCELLED,
            created_at=reservation.created_at,
            expires_at=reservation.expires_at,
            confirmed_at=reservation.confirmed_at,
            released_at=reservation.released_at,
            failed_at=reservation.failed_at,
            metadata=dict(reservation.metadata),
        )
        self.repository.update_reservation(updated_reservation)
        return updated_reservation

    def expire_due_reservations(
        self, now: datetime | None = None
    ) -> tuple[BudgetReservation, ...]:
        """Find and expire due active reservations."""
        ref_now = now if now is not None else _now_utc()
        due_reservations = self.repository.expire_reservations(now=ref_now)
        expired_results: list[BudgetReservation] = []

        for res in due_reservations:
            budget = self.repository.get_budget(res.budget_id)
            new_reserved = dict(budget.reserved)
            for alloc in res.allocations:
                res_t = alloc.resource_type
                curr_res = new_reserved.get(
                    res_t, Decimal(0) if res_t == BudgetResourceType.COST else 0
                )
                new_reserved[res_t] = max(
                    Decimal(0) if res_t == BudgetResourceType.COST else 0,
                    curr_res - alloc.amount,
                )

            updated_budget = ActionBudget(
                id=budget.id,
                agent_run_id=budget.agent_run_id,
                limits=dict(budget.limits),
                used=dict(budget.used),
                reserved=new_reserved,
                currency=budget.currency,
                warning_threshold=budget.warning_threshold,
                critical_threshold=budget.critical_threshold,
                status=budget.status,
                version=budget.version + 1,
                created_at=budget.created_at,
                updated_at=ref_now,
                started_at=budget.started_at,
                paused_at=budget.paused_at,
                total_paused_seconds=budget.total_paused_seconds,
                metadata=dict(budget.metadata),
            )

            updated_res = BudgetReservation(
                id=res.id,
                budget_id=res.budget_id,
                agent_run_id=res.agent_run_id,
                allocations=res.allocations,
                operation_id=res.operation_id,
                workflow_id=res.workflow_id,
                idempotency_key=res.idempotency_key,
                status=BudgetReservationStatus.EXPIRED,
                created_at=res.created_at,
                expires_at=res.expires_at,
                confirmed_at=res.confirmed_at,
                released_at=res.released_at,
                failed_at=res.failed_at,
                metadata=dict(res.metadata),
            )

            self.repository.update_budget(updated_budget)
            self.repository.update_reservation(updated_res)
            expired_results.append(updated_res)

        return tuple(expired_results)

    def pause(self, budget_id: str, now: datetime | None = None) -> ActionBudget:
        """Pause a budget run."""
        ref_now = now if now is not None else _now_utc()
        budget = self.repository.get_budget(budget_id)
        if budget.status == ActionBudgetStatus.PAUSED:
            return budget

        updated_budget = ActionBudget(
            id=budget.id,
            agent_run_id=budget.agent_run_id,
            limits=dict(budget.limits),
            used=dict(budget.used),
            reserved=dict(budget.reserved),
            currency=budget.currency,
            warning_threshold=budget.warning_threshold,
            critical_threshold=budget.critical_threshold,
            status=ActionBudgetStatus.PAUSED,
            version=budget.version + 1,
            created_at=budget.created_at,
            updated_at=ref_now,
            started_at=budget.started_at,
            paused_at=ref_now,
            total_paused_seconds=budget.total_paused_seconds,
            metadata=dict(budget.metadata),
        )
        self.repository.update_budget(updated_budget)
        return updated_budget

    def resume(self, budget_id: str, now: datetime | None = None) -> ActionBudget:
        """Resume a paused budget run."""
        ref_now = now if now is not None else _now_utc()
        budget = self.repository.get_budget(budget_id)
        if budget.status != ActionBudgetStatus.PAUSED:
            return budget

        additional_paused = 0.0
        if budget.paused_at is not None:
            additional_paused = (ref_now - budget.paused_at).total_seconds()

        total_paused = budget.total_paused_seconds + max(0.0, additional_paused)

        updated_budget = ActionBudget(
            id=budget.id,
            agent_run_id=budget.agent_run_id,
            limits=dict(budget.limits),
            used=dict(budget.used),
            reserved=dict(budget.reserved),
            currency=budget.currency,
            warning_threshold=budget.warning_threshold,
            critical_threshold=budget.critical_threshold,
            status=ActionBudgetStatus.ACTIVE,
            version=budget.version + 1,
            created_at=budget.created_at,
            updated_at=ref_now,
            started_at=budget.started_at,
            paused_at=None,
            total_paused_seconds=total_paused,
            metadata=dict(budget.metadata),
        )
        self.repository.update_budget(updated_budget)
        return updated_budget

    def complete(self, budget_id: str, now: datetime | None = None) -> ActionBudget:
        """Mark budget as COMPLETED."""
        ref_now = now if now is not None else _now_utc()
        budget = self.repository.get_budget(budget_id)
        updated_budget = ActionBudget(
            id=budget.id,
            agent_run_id=budget.agent_run_id,
            limits=dict(budget.limits),
            used=dict(budget.used),
            reserved=dict(budget.reserved),
            currency=budget.currency,
            warning_threshold=budget.warning_threshold,
            critical_threshold=budget.critical_threshold,
            status=ActionBudgetStatus.COMPLETED,
            version=budget.version + 1,
            created_at=budget.created_at,
            updated_at=ref_now,
            started_at=budget.started_at,
            paused_at=budget.paused_at,
            total_paused_seconds=budget.total_paused_seconds,
            metadata=dict(budget.metadata),
        )
        self.repository.update_budget(updated_budget)
        return updated_budget

    def cancel_budget(
        self, budget_id: str, now: datetime | None = None
    ) -> ActionBudget:
        """Cancel budget and release all active reservations."""
        ref_now = now if now is not None else _now_utc()
        budget = self.repository.get_budget(budget_id)

        active_res = self.repository.find_active_reservations(budget_id)
        for r in active_res:
            self.cancel_reservation(r.id, now=ref_now)

        updated_budget = ActionBudget(
            id=budget.id,
            agent_run_id=budget.agent_run_id,
            limits=dict(budget.limits),
            used=dict(budget.used),
            reserved={},
            currency=budget.currency,
            warning_threshold=budget.warning_threshold,
            critical_threshold=budget.critical_threshold,
            status=ActionBudgetStatus.CANCELLED,
            version=budget.version + 1,
            created_at=budget.created_at,
            updated_at=ref_now,
            started_at=budget.started_at,
            paused_at=budget.paused_at,
            total_paused_seconds=budget.total_paused_seconds,
            metadata=dict(budget.metadata),
        )
        self.repository.update_budget(updated_budget)
        return updated_budget

    def increase_budget(
        self,
        budget_id: str,
        resource_type: BudgetResourceType | str,
        new_limit: int | Decimal | None = None,
        delta: int | Decimal | None = None,
        actor_id: str = "actor-user",
        approval_request_id: str | None = None,
        approval_resolution: ApprovalResolution | None = None,
        reason_codes: Sequence[str] = (),
        now: datetime | None = None,
    ) -> tuple[ActionBudget, BudgetAdjustment]:
        """Authorized limit increase on budget."""
        ref_now = now if now is not None else _now_utc()
        res_t = (
            BudgetResourceType(resource_type)
            if isinstance(resource_type, str)
            else resource_type
        )
        budget = self.repository.get_budget(budget_id)

        if approval_resolution is None:
            raise BudgetIncreaseNotAuthorizedError(
                "Action budget limit increase requires a valid ApprovalResolution"
            )

        if not isinstance(approval_resolution, ApprovalResolution):
            raise BudgetIncreaseNotAuthorizedError(
                "approval_resolution must be an instance of ApprovalResolution"
            )

        if not ActionBudgetApprovalAdapter.validate_approval_for_increase(
            approval_resolution, budget.id, res_t, now=ref_now
        ):
            raise BudgetIncreaseNotAuthorizedError(
                "Approval resolution is invalid or not authorized for this budget increase"
            )

        if new_limit is None and delta is None:
            raise InvalidActionBudgetContractError(
                "Either new_limit or delta must be provided for budget increase"
            )

        prev_lim = budget.limit_for(res_t)

        target_limit: int | Decimal | None
        if new_limit is not None:
            target_limit = new_limit
        else:
            if prev_lim is None:
                raise InvalidActionBudgetContractError(
                    f"Cannot apply delta increase to unlimited resource {res_t.value}"
                )
            target_limit = prev_lim + delta  # type: ignore[operator]

        new_limits = dict(budget.limits)
        new_limits[res_t] = target_limit

        new_status = ActionBudgetStatus.INCREASED
        avail = budget.available_for(res_t, now=ref_now)
        if avail is not None and avail > 0:
            new_status = ActionBudgetStatus.ACTIVE

        updated_budget = ActionBudget(
            id=budget.id,
            agent_run_id=budget.agent_run_id,
            limits=new_limits,
            used=dict(budget.used),
            reserved=dict(budget.reserved),
            currency=budget.currency,
            warning_threshold=budget.warning_threshold,
            critical_threshold=budget.critical_threshold,
            status=new_status,
            version=budget.version + 1,
            created_at=budget.created_at,
            updated_at=ref_now,
            started_at=budget.started_at,
            paused_at=budget.paused_at,
            total_paused_seconds=budget.total_paused_seconds,
            metadata=dict(budget.metadata),
        )

        adj_delta = (
            target_limit - prev_lim  # type: ignore[operator]
            if (target_limit is not None and prev_lim is not None)
            else delta
        )

        codes = list(reason_codes)
        if "budget.increase_approved" not in codes:
            codes.append("budget.increase_approved")

        adjustment = BudgetAdjustment(
            id=_gen_id("adjustment"),
            budget_id=budget.id,
            adjustment_type=BudgetAdjustmentType.INCREASE,
            resource_type=res_t,
            previous_limit=prev_lim,
            new_limit=target_limit,
            delta=adj_delta,
            actor_id=actor_id,
            approval_request_id=approval_request_id,
            reason_codes=tuple(codes),
            created_at=ref_now,
            metadata={},
        )

        self.repository.update_budget(updated_budget)
        self.repository.add_adjustment(adjustment)
        return updated_budget, adjustment

    def decrease_budget(
        self,
        budget_id: str,
        resource_type: BudgetResourceType | str,
        new_limit: int | Decimal | None = None,
        delta: int | Decimal | None = None,
        actor_id: str = "actor-user",
        reason_codes: Sequence[str] = (),
        now: datetime | None = None,
    ) -> tuple[ActionBudget, BudgetAdjustment]:
        """Authorized limit decrease on budget."""
        ref_now = now if now is not None else _now_utc()
        res_t = (
            BudgetResourceType(resource_type)
            if isinstance(resource_type, str)
            else resource_type
        )
        budget = self.repository.get_budget(budget_id)

        if new_limit is None and delta is None:
            raise InvalidActionBudgetContractError(
                "Either new_limit or delta must be provided for budget decrease"
            )

        prev_lim = budget.limit_for(res_t)

        target_limit: int | Decimal | None
        if new_limit is not None:
            target_limit = new_limit
        else:
            if prev_lim is None:
                raise InvalidActionBudgetContractError(
                    f"Cannot apply delta decrease to unlimited resource {res_t.value}"
                )
            target_limit = prev_lim - delta  # type: ignore[operator]

        curr_used = budget.used_for(res_t)
        curr_res = budget.reserved_for(res_t)
        committed = curr_used + curr_res
        if target_limit is not None and target_limit < committed:
            raise InvalidActionBudgetContractError(
                f"Cannot decrease limit of {res_t.value} to {target_limit} below current committed usage ({committed})"
            )

        new_limits = dict(budget.limits)
        new_limits[res_t] = target_limit

        updated_budget = ActionBudget(
            id=budget.id,
            agent_run_id=budget.agent_run_id,
            limits=new_limits,
            used=dict(budget.used),
            reserved=dict(budget.reserved),
            currency=budget.currency,
            warning_threshold=budget.warning_threshold,
            critical_threshold=budget.critical_threshold,
            status=budget.status,
            version=budget.version + 1,
            created_at=budget.created_at,
            updated_at=ref_now,
            started_at=budget.started_at,
            paused_at=budget.paused_at,
            total_paused_seconds=budget.total_paused_seconds,
            metadata=dict(budget.metadata),
        )

        adj_delta = (
            target_limit - prev_lim  # type: ignore[operator]
            if (target_limit is not None and prev_lim is not None)
            else delta
        )

        adjustment = BudgetAdjustment(
            id=_gen_id("adjustment"),
            budget_id=budget.id,
            adjustment_type=BudgetAdjustmentType.DECREASE,
            resource_type=res_t,
            previous_limit=prev_lim,
            new_limit=target_limit,
            delta=adj_delta,
            actor_id=actor_id,
            reason_codes=tuple(reason_codes),
            created_at=ref_now,
            metadata={},
        )

        self.repository.update_budget(updated_budget)
        self.repository.add_adjustment(adjustment)
        return updated_budget, adjustment

    def request_increase(
        self,
        budget_id: str,
        resource_type: BudgetResourceType | str,
        requested_limit: int | Decimal | None = None,
        requested_delta: int | Decimal | None = None,
        requester_id: str = "agent-run",
        reason: str = "Action budget limit increase requested",
        metadata: dict | None = None,
    ) -> ApprovalRequirement:
        """Create an ApprovalRequirement compatible with Human Approval System for a budget increase."""
        res_t = (
            BudgetResourceType(resource_type)
            if isinstance(resource_type, str)
            else resource_type
        )
        budget = self.repository.get_budget(budget_id)

        meta = {
            "budget_id": budget_id,
            "agent_run_id": budget.agent_run_id,
            "resource_type": res_t.value,
            "current_limit": _serialize_amount(budget.limit_for(res_t)),
            "requested_limit": _serialize_amount(requested_limit),
            "requested_delta": _serialize_amount(requested_delta),
        }
        if metadata:
            meta.update(metadata)

        return ApprovalRequirement(
            id=f"req-budget-increase-{budget_id}-{res_t.value}",
            source=ApprovalRequirementSource.BUDGET,
            title=f"Action budget limit increase for {res_t.value}",
            description=reason,
            required_approvers=("role:supervisor", "role:admin"),
            scope="budget.increase",
            metadata=MappingProxyType(dict(meta)),
        )
