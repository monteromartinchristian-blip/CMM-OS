"""Phase 9.11 – Action Budget Repository Interface and In-Memory Implementation.

Provides persistent storage abstraction for budgets, reservations, consumptions, and adjustments.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from .action_budget_contracts import (
    ActionBudget,
    BudgetAdjustment,
    BudgetConsumption,
    BudgetReservation,
)
from .enums import BudgetReservationStatus
from .errors import (
    ActionBudgetNotFoundError,
    BudgetReservationNotFoundError,
    DuplicateActionBudgetError,
    DuplicateBudgetAdjustmentError,
    DuplicateBudgetConsumptionError,
    DuplicateBudgetReservationError,
)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class ActionBudgetRepository(ABC):
    """Abstract interface for Action Budget storage."""

    @abstractmethod
    def add_budget(self, budget: ActionBudget) -> None:
        """Store a new ActionBudget."""

    @abstractmethod
    def get_budget(self, budget_id: str) -> ActionBudget:
        """Retrieve an ActionBudget by ID or raise ActionBudgetNotFoundError."""

    @abstractmethod
    def update_budget(self, budget: ActionBudget) -> None:
        """Update an existing ActionBudget or raise ActionBudgetNotFoundError."""

    @abstractmethod
    def list_budgets(self, agent_run_id: str | None = None) -> tuple[ActionBudget, ...]:
        """List all ActionBudgets, optionally filtered by agent_run_id."""

    @abstractmethod
    def find_by_agent_run(self, agent_run_id: str) -> ActionBudget | None:
        """Find the active or latest ActionBudget for an agent run, or None."""

    @abstractmethod
    def add_reservation(self, reservation: BudgetReservation) -> None:
        """Store a new BudgetReservation."""

    @abstractmethod
    def get_reservation(self, reservation_id: str) -> BudgetReservation:
        """Retrieve a BudgetReservation by ID or raise BudgetReservationNotFoundError."""

    @abstractmethod
    def find_reservation_by_idempotency_key(
        self, budget_id: str, idempotency_key: str
    ) -> BudgetReservation | None:
        """Find reservation by budget ID and idempotency key, if any."""

    @abstractmethod
    def update_reservation(self, reservation: BudgetReservation) -> None:
        """Update an existing BudgetReservation."""

    @abstractmethod
    def list_reservations(
        self,
        budget_id: str | None = None,
        status: BudgetReservationStatus | None = None,
    ) -> tuple[BudgetReservation, ...]:
        """List reservations with optional filters."""

    @abstractmethod
    def find_active_reservations(self, budget_id: str) -> tuple[BudgetReservation, ...]:
        """Return all active (RESERVED) reservations for a budget."""

    @abstractmethod
    def add_consumption(self, consumption: BudgetConsumption) -> None:
        """Store a new BudgetConsumption audit record."""

    @abstractmethod
    def list_consumptions(
        self,
        budget_id: str | None = None,
        reservation_id: str | None = None,
    ) -> tuple[BudgetConsumption, ...]:
        """List consumptions with optional filters."""

    @abstractmethod
    def add_adjustment(self, adjustment: BudgetAdjustment) -> None:
        """Store a new BudgetAdjustment audit record."""

    @abstractmethod
    def list_adjustments(
        self, budget_id: str | None = None
    ) -> tuple[BudgetAdjustment, ...]:
        """List adjustments with optional filters."""

    @abstractmethod
    def expire_reservations(
        self, now: datetime | None = None
    ) -> tuple[BudgetReservation, ...]:
        """Find and expire due active reservations."""


class InMemoryActionBudgetRepository(ActionBudgetRepository):
    """Thread-safe, in-memory implementation of ActionBudgetRepository."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._budgets: dict[str, ActionBudget] = {}
        self._reservations: dict[str, BudgetReservation] = {}
        self._idempotency_index: dict[tuple[str, str], str] = {}
        self._consumptions: dict[str, BudgetConsumption] = {}
        self._adjustments: dict[str, BudgetAdjustment] = {}

    def add_budget(self, budget: ActionBudget) -> None:
        with self._lock:
            if budget.id in self._budgets:
                raise DuplicateActionBudgetError(
                    f"ActionBudget with ID {budget.id!r} already exists"
                )
            self._budgets[budget.id] = budget

    def get_budget(self, budget_id: str) -> ActionBudget:
        with self._lock:
            if budget_id not in self._budgets:
                raise ActionBudgetNotFoundError(
                    f"ActionBudget with ID {budget_id!r} not found"
                )
            return self._budgets[budget_id]

    def update_budget(self, budget: ActionBudget) -> None:
        with self._lock:
            if budget.id not in self._budgets:
                raise ActionBudgetNotFoundError(
                    f"Cannot update non-existent ActionBudget with ID {budget.id!r}"
                )
            self._budgets[budget.id] = budget

    def list_budgets(self, agent_run_id: str | None = None) -> tuple[ActionBudget, ...]:
        with self._lock:
            budgets = list(self._budgets.values())
            if agent_run_id is not None:
                budgets = [b for b in budgets if b.agent_run_id == agent_run_id]
            return tuple(budgets)

    def find_by_agent_run(self, agent_run_id: str) -> ActionBudget | None:
        with self._lock:
            matching = [
                b for b in self._budgets.values() if b.agent_run_id == agent_run_id
            ]
            if not matching:
                return None
            matching.sort(key=lambda x: x.created_at, reverse=True)
            return matching[0]

    def add_reservation(self, reservation: BudgetReservation) -> None:
        with self._lock:
            if reservation.id in self._reservations:
                raise DuplicateBudgetReservationError(
                    f"BudgetReservation with ID {reservation.id!r} already exists"
                )
            if reservation.budget_id not in self._budgets:
                raise ActionBudgetNotFoundError(
                    f"Cannot create reservation for non-existent budget {reservation.budget_id!r}"
                )
            if reservation.idempotency_key:
                idx_key = (reservation.budget_id, reservation.idempotency_key)
                if idx_key in self._idempotency_index:
                    existing_id = self._idempotency_index[idx_key]
                    raise DuplicateBudgetReservationError(
                        f"Reservation with idempotency key {reservation.idempotency_key!r} already exists (ID: {existing_id})"
                    )
                self._idempotency_index[idx_key] = reservation.id

            self._reservations[reservation.id] = reservation

    def get_reservation(self, reservation_id: str) -> BudgetReservation:
        with self._lock:
            if reservation_id not in self._reservations:
                raise BudgetReservationNotFoundError(
                    f"BudgetReservation with ID {reservation_id!r} not found"
                )
            return self._reservations[reservation_id]

    def find_reservation_by_idempotency_key(
        self, budget_id: str, idempotency_key: str
    ) -> BudgetReservation | None:
        with self._lock:
            idx_key = (budget_id, idempotency_key)
            res_id = self._idempotency_index.get(idx_key)
            if res_id and res_id in self._reservations:
                return self._reservations[res_id]
            return None

    def update_reservation(self, reservation: BudgetReservation) -> None:
        with self._lock:
            if reservation.id not in self._reservations:
                raise BudgetReservationNotFoundError(
                    f"Cannot update non-existent BudgetReservation with ID {reservation.id!r}"
                )
            self._reservations[reservation.id] = reservation

    def list_reservations(
        self,
        budget_id: str | None = None,
        status: BudgetReservationStatus | None = None,
    ) -> tuple[BudgetReservation, ...]:
        with self._lock:
            res_list = list(self._reservations.values())
            if budget_id is not None:
                res_list = [r for r in res_list if r.budget_id == budget_id]
            if status is not None:
                res_list = [r for r in res_list if r.status == status]
            return tuple(res_list)

    def find_active_reservations(self, budget_id: str) -> tuple[BudgetReservation, ...]:
        return self.list_reservations(
            budget_id=budget_id, status=BudgetReservationStatus.RESERVED
        )

    def add_consumption(self, consumption: BudgetConsumption) -> None:
        with self._lock:
            if consumption.id in self._consumptions:
                raise DuplicateBudgetConsumptionError(
                    f"BudgetConsumption with ID {consumption.id!r} already exists"
                )
            if consumption.budget_id not in self._budgets:
                raise ActionBudgetNotFoundError(
                    f"Cannot record consumption for non-existent budget {consumption.budget_id!r}"
                )
            self._consumptions[consumption.id] = consumption

    def list_consumptions(
        self,
        budget_id: str | None = None,
        reservation_id: str | None = None,
    ) -> tuple[BudgetConsumption, ...]:
        with self._lock:
            c_list = list(self._consumptions.values())
            if budget_id is not None:
                c_list = [c for c in c_list if c.budget_id == budget_id]
            if reservation_id is not None:
                c_list = [c for c in c_list if c.reservation_id == reservation_id]
            return tuple(c_list)

    def add_adjustment(self, adjustment: BudgetAdjustment) -> None:
        with self._lock:
            if adjustment.id in self._adjustments:
                raise DuplicateBudgetAdjustmentError(
                    f"BudgetAdjustment with ID {adjustment.id!r} already exists"
                )
            if adjustment.budget_id not in self._budgets:
                raise ActionBudgetNotFoundError(
                    f"Cannot record adjustment for non-existent budget {adjustment.budget_id!r}"
                )
            self._adjustments[adjustment.id] = adjustment

    def list_adjustments(
        self, budget_id: str | None = None
    ) -> tuple[BudgetAdjustment, ...]:
        with self._lock:
            a_list = list(self._adjustments.values())
            if budget_id is not None:
                a_list = [a for a in a_list if a.budget_id == budget_id]
            return tuple(a_list)

    def expire_reservations(
        self, now: datetime | None = None
    ) -> tuple[BudgetReservation, ...]:
        with self._lock:
            ref_time = now if now is not None else _now_utc()
            expired_list: list[BudgetReservation] = []
            for r in self._reservations.values():
                if (
                    r.status == BudgetReservationStatus.RESERVED
                    and r.expires_at <= ref_time
                ):
                    expired_list.append(r)
            return tuple(expired_list)
