"""Phase 9.11 – Action Budget Contracts.

Defines the immutable, serializable, strictly validated contracts that constitute
the Action Budget system of the Autonomous Agent Runtime:

* :class:`BudgetAllocation` — resource type and discrete/monetary amount.
* :class:`ActionBudget` — global resource budget definition and state for an AgentRun.
* :class:`BudgetReservation` — atomic pre-execution resource reservation.
* :class:`BudgetConsumption` — audit record of confirmed resource consumption.
* :class:`BudgetAdjustment` — audit record of authorized budget limit changes.
* :class:`BudgetEvaluationResult` — structured evaluation result before execution.

All contracts are:
* `@dataclass(frozen=True, slots=True)`
* strictly validated in ``__post_init__``;
* serializable via ``to_dict()`` / ``serialize()``;
* reconstructible from mapping via ``from_dict()`` / ``from_mapping()``;
* immutable.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, DecimalException
from types import MappingProxyType
from typing import Any

from .enums import (
    ActionBudgetStatus,
    BudgetAdjustmentType,
    BudgetConsumptionOutcome,
    BudgetReservationStatus,
    BudgetResourceType,
)
from .errors import InvalidActionBudgetContractError

# ── Internal Helpers ──────────────────────────────────────────────────────────


def _now_utc() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def _ensure_aware_dt(val: Any, field_name: str) -> datetime:
    """Ensure ``val`` is a timezone-aware ``datetime``."""
    if not isinstance(val, datetime):
        raise InvalidActionBudgetContractError(
            f"{field_name} must be a datetime instance, got {type(val).__name__}"
        )
    if val.tzinfo is None:
        raise InvalidActionBudgetContractError(f"{field_name} must be timezone-aware")
    return val


def _parse_dt(val: Any, field_name: str) -> datetime:
    """Parse ISO string or datetime into a timezone-aware datetime."""
    if isinstance(val, datetime):
        return _ensure_aware_dt(val, field_name)
    if isinstance(val, str):
        try:
            parsed = datetime.fromisoformat(val)
        except ValueError as exc:
            raise InvalidActionBudgetContractError(
                f"Invalid isoformat datetime string for {field_name}: {val!r}"
            ) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    raise InvalidActionBudgetContractError(
        f"{field_name} must be an ISO string or datetime instance"
    )


def _validate_non_empty_str(val: Any, field_name: str) -> str:
    """Validate that ``val`` is a non-empty string."""
    if not isinstance(val, str) or not val.strip():
        raise InvalidActionBudgetContractError(
            f"{field_name} must be a non-empty string"
        )
    return val.strip()


def _validate_optional_str(val: Any, field_name: str) -> str | None:
    """Validate optional string."""
    if val is None:
        return None
    if not isinstance(val, str):
        raise InvalidActionBudgetContractError(f"{field_name} must be a string or None")
    stripped = val.strip()
    return stripped if stripped else None


def _validate_resource_type(val: Any) -> BudgetResourceType:
    """Coerce string or BudgetResourceType enum into a valid BudgetResourceType."""
    if isinstance(val, BudgetResourceType):
        return val
    if isinstance(val, str):
        try:
            return BudgetResourceType(val)
        except ValueError:
            pass
    raise InvalidActionBudgetContractError(
        f"Invalid resource type: {val!r}. Must be a valid BudgetResourceType."
    )


def _validate_amount_value(
    val: Any,
    field_name: str,
    resource_type: BudgetResourceType | None = None,
    allow_none: bool = False,
    allow_zero: bool = True,
) -> int | Decimal | None:
    """Strictly validate numeric values for budget limits, allocations, used, reserved.

    Rejects:
    * bool values (e.g. True/False)
    * float values (to avoid precision issues)
    * non-finite Decimals (NaN, Infinity)
    * negative amounts
    """
    if val is None:
        if allow_none:
            return None
        raise InvalidActionBudgetContractError(f"{field_name} cannot be None")

    if isinstance(val, bool):
        raise InvalidActionBudgetContractError(
            f"{field_name} cannot be a boolean value"
        )

    if isinstance(val, float):
        raise InvalidActionBudgetContractError(
            f"{field_name} cannot be float; use int or Decimal to avoid precision loss"
        )

    if not isinstance(val, (int, Decimal)):
        raise InvalidActionBudgetContractError(
            f"{field_name} must be int or Decimal, got {type(val).__name__}"
        )

    if isinstance(val, Decimal) and not val.is_finite():
        raise InvalidActionBudgetContractError(
            f"{field_name} Decimal value must be finite, got {val}"
        )

    if resource_type == BudgetResourceType.COST and not isinstance(val, Decimal):
        val = Decimal(str(val))

    if allow_zero:
        if val < 0:
            raise InvalidActionBudgetContractError(
                f"{field_name} cannot be negative, got {val}"
            )
    else:
        if val <= 0:
            raise InvalidActionBudgetContractError(
                f"{field_name} must be strictly positive, got {val}"
            )

    return val


def _serialize_amount(val: int | Decimal | None) -> int | str | None:
    """Serialize numeric amount for JSON compatibility."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return str(val)
    return val


def _deserialize_amount(
    val: Any, field_name: str, resource_type: BudgetResourceType | None = None
) -> int | Decimal | None:
    """Deserialize numeric amount from dict."""
    if val is None:
        return None
    if isinstance(val, bool):
        raise InvalidActionBudgetContractError(
            f"{field_name} cannot be a boolean value"
        )
    if isinstance(val, int):
        if resource_type == BudgetResourceType.COST:
            return Decimal(str(val))
        return val
    if isinstance(val, str):
        try:
            return Decimal(val)
        except (ValueError, DecimalException) as exc:
            raise InvalidActionBudgetContractError(
                f"Invalid Decimal string for {field_name}: {val!r}"
            ) from exc
    raise InvalidActionBudgetContractError(
        f"{field_name} must be int or Decimal string representation"
    )


# ── Contracts ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class BudgetAllocation:
    """Represents a specific quantity allocation for a controlled resource type."""

    resource_type: BudgetResourceType
    amount: int | Decimal

    def __post_init__(self) -> None:
        res_type = _validate_resource_type(self.resource_type)
        object.__setattr__(self, "resource_type", res_type)
        amt = _validate_amount_value(
            self.amount,
            field_name=f"BudgetAllocation.amount({res_type.value})",
            resource_type=res_type,
            allow_none=False,
            allow_zero=False,
        )
        object.__setattr__(self, "amount", amt)

    def to_dict(self) -> dict[str, Any]:
        """Serialize allocation into a JSON-compatible dictionary."""
        return {
            "resource_type": self.resource_type.value,
            "amount": _serialize_amount(self.amount),
        }

    def serialize(self) -> dict[str, Any]:
        """Alias for to_dict()."""
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BudgetAllocation:
        """Reconstruct BudgetAllocation from mapping."""
        if not isinstance(data, Mapping):
            raise InvalidActionBudgetContractError(
                "BudgetAllocation data must be a Mapping"
            )
        res_type = _validate_resource_type(data.get("resource_type"))
        raw_amt = data.get("amount")
        amt = _deserialize_amount(
            raw_amt,
            field_name=f"BudgetAllocation.amount({res_type.value})",
            resource_type=res_type,
        )
        if amt is None:
            raise InvalidActionBudgetContractError(
                "BudgetAllocation amount cannot be None"
            )
        return cls(resource_type=res_type, amount=amt)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> BudgetAllocation:
        """Alias for from_dict()."""
        return cls.from_dict(data)


@dataclass(frozen=True, slots=True)
class ActionBudget:
    """Represents the global resource budget definition and state for an AgentRun."""

    id: str
    agent_run_id: str
    limits: Mapping[BudgetResourceType, int | Decimal | None] = field(
        default_factory=dict
    )
    used: Mapping[BudgetResourceType, int | Decimal] = field(default_factory=dict)
    reserved: Mapping[BudgetResourceType, int | Decimal] = field(default_factory=dict)
    currency: str = "EUR"
    warning_threshold: float = 0.8
    critical_threshold: float = 0.95
    status: ActionBudgetStatus = ActionBudgetStatus.ACTIVE
    version: int = 1
    created_at: datetime = field(default_factory=_now_utc)
    updated_at: datetime = field(default_factory=_now_utc)
    started_at: datetime = field(default_factory=_now_utc)
    paused_at: datetime | None = None
    total_paused_seconds: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "id", _validate_non_empty_str(self.id, "ActionBudget.id")
        )
        object.__setattr__(
            self,
            "agent_run_id",
            _validate_non_empty_str(self.agent_run_id, "ActionBudget.agent_run_id"),
        )
        object.__setattr__(
            self,
            "currency",
            _validate_non_empty_str(self.currency, "ActionBudget.currency").upper(),
        )

        if (
            isinstance(self.warning_threshold, bool)
            or not isinstance(self.warning_threshold, (int, float))
            or not (0.0 < float(self.warning_threshold) <= 1.0)
        ):
            raise InvalidActionBudgetContractError(
                "warning_threshold must be a float > 0.0 and <= 1.0"
            )
        object.__setattr__(self, "warning_threshold", float(self.warning_threshold))

        if (
            isinstance(self.critical_threshold, bool)
            or not isinstance(self.critical_threshold, (int, float))
            or not (self.warning_threshold <= float(self.critical_threshold) <= 1.0)
        ):
            raise InvalidActionBudgetContractError(
                "critical_threshold must be a float between warning_threshold and 1.0"
            )
        object.__setattr__(self, "critical_threshold", float(self.critical_threshold))

        if not isinstance(self.status, ActionBudgetStatus):
            if isinstance(self.status, str):
                try:
                    object.__setattr__(self, "status", ActionBudgetStatus(self.status))
                except ValueError as exc:
                    raise InvalidActionBudgetContractError(
                        f"Invalid status: {self.status!r}"
                    ) from exc
            else:
                raise InvalidActionBudgetContractError(
                    f"Invalid status type: {type(self.status).__name__}"
                )

        if isinstance(self.version, bool) or not isinstance(self.version, int):
            raise InvalidActionBudgetContractError("version must be an int")
        if self.version < 1:
            raise InvalidActionBudgetContractError("version must be >= 1")

        object.__setattr__(
            self, "created_at", _ensure_aware_dt(self.created_at, "created_at")
        )
        object.__setattr__(
            self, "updated_at", _ensure_aware_dt(self.updated_at, "updated_at")
        )
        object.__setattr__(
            self, "started_at", _ensure_aware_dt(self.started_at, "started_at")
        )

        if self.paused_at is not None:
            object.__setattr__(
                self, "paused_at", _ensure_aware_dt(self.paused_at, "paused_at")
            )

        if (
            isinstance(self.total_paused_seconds, bool)
            or not isinstance(self.total_paused_seconds, (int, float))
            or float(self.total_paused_seconds) < 0.0
        ):
            raise InvalidActionBudgetContractError(
                "total_paused_seconds must be a non-negative number"
            )
        object.__setattr__(
            self, "total_paused_seconds", float(self.total_paused_seconds)
        )

        # Validate Mappings
        clean_limits: dict[BudgetResourceType, int | Decimal | None] = {}
        for r_k, r_v in self.limits.items():
            res_t = _validate_resource_type(r_k)
            validated_v = _validate_amount_value(
                r_v,
                field_name=f"limits[{res_t.value}]",
                resource_type=res_t,
                allow_none=True,
                allow_zero=True,
            )
            clean_limits[res_t] = validated_v

        clean_used: dict[BudgetResourceType, int | Decimal] = {}
        for r_k, r_v in self.used.items():
            res_t = _validate_resource_type(r_k)
            validated_v = _validate_amount_value(
                r_v,
                field_name=f"used[{res_t.value}]",
                resource_type=res_t,
                allow_none=False,
                allow_zero=True,
            )
            if validated_v is not None:
                clean_used[res_t] = validated_v

        clean_reserved: dict[BudgetResourceType, int | Decimal] = {}
        for r_k, r_v in self.reserved.items():
            res_t = _validate_resource_type(r_k)
            validated_v = _validate_amount_value(
                r_v,
                field_name=f"reserved[{res_t.value}]",
                resource_type=res_t,
                allow_none=False,
                allow_zero=True,
            )
            if validated_v is not None:
                clean_reserved[res_t] = validated_v

        meta_dict = dict(self.metadata) if self.metadata else {}

        object.__setattr__(self, "limits", MappingProxyType(clean_limits))
        object.__setattr__(self, "used", MappingProxyType(clean_used))
        object.__setattr__(self, "reserved", MappingProxyType(clean_reserved))
        object.__setattr__(self, "metadata", MappingProxyType(meta_dict))

    def limit_for(self, resource: BudgetResourceType | str) -> int | Decimal | None:
        """Return limit for a given resource type, or None if unlimited or unset."""
        res_t = _validate_resource_type(resource)
        return self.limits.get(res_t, None)

    def used_for(self, resource: BudgetResourceType | str) -> int | Decimal:
        """Return used quantity for a given resource type, defaulting to 0/Decimal(0)."""
        res_t = _validate_resource_type(resource)
        if res_t in self.used:
            return self.used[res_t]
        return Decimal(0) if res_t == BudgetResourceType.COST else 0

    def reserved_for(self, resource: BudgetResourceType | str) -> int | Decimal:
        """Return reserved quantity for a given resource type, defaulting to 0/Decimal(0)."""
        res_t = _validate_resource_type(resource)
        if res_t in self.reserved:
            return self.reserved[res_t]
        return Decimal(0) if res_t == BudgetResourceType.COST else 0

    def is_unlimited(self, resource: BudgetResourceType | str) -> bool:
        """Return True if resource has no limit configured (or explicitly set to None)."""
        res_t = _validate_resource_type(resource)
        return res_t not in self.limits or self.limits[res_t] is None

    def available_for(
        self, resource: BudgetResourceType | str, now: datetime | None = None
    ) -> int | Decimal | None:
        """Calculate available remaining capacity for a resource.

        Returns None if unlimited.
        For temporal DURATION_SECONDS, computes remaining seconds based on elapsed active time.
        For concurrent PARALLEL_OPERATION, remaining = limit - reserved.
        For cumulative resources, remaining = limit - used - reserved.
        """
        res_t = _validate_resource_type(resource)
        limit = self.limit_for(res_t)
        if limit is None:
            return None

        if res_t == BudgetResourceType.DURATION_SECONDS:
            eval_time = now if now is not None else _now_utc()
            eval_time = _ensure_aware_dt(eval_time, "now")
            if self.paused_at is not None:
                elapsed = (
                    self.paused_at - self.started_at
                ).total_seconds() - self.total_paused_seconds
            else:
                elapsed = (
                    eval_time - self.started_at
                ).total_seconds() - self.total_paused_seconds
            elapsed_sec = max(0, int(elapsed))
            remaining = int(limit) - elapsed_sec - int(self.reserved_for(res_t))
            return max(0, remaining)

        if res_t == BudgetResourceType.PARALLEL_OPERATION:
            remaining = int(limit) - int(self.reserved_for(res_t))
            return max(0, remaining)

        used_val = self.used_for(res_t)
        res_val = self.reserved_for(res_t)
        avail = limit - (used_val + res_val)
        zero_val = Decimal(0) if isinstance(limit, Decimal) else 0
        return max(zero_val, avail)

    def utilization_for(
        self, resource: BudgetResourceType | str, now: datetime | None = None
    ) -> float:
        """Return utilization ratio (0.0 to 1.0) for a resource.

        If unlimited, returns 0.0.
        """
        res_t = _validate_resource_type(resource)
        limit = self.limit_for(res_t)
        if limit is None or (isinstance(limit, (int, Decimal)) and limit == 0):
            return 0.0

        if res_t == BudgetResourceType.DURATION_SECONDS:
            eval_time = now if now is not None else _now_utc()
            eval_time = _ensure_aware_dt(eval_time, "now")
            if self.paused_at is not None:
                elapsed = (
                    self.paused_at - self.started_at
                ).total_seconds() - self.total_paused_seconds
            else:
                elapsed = (
                    eval_time - self.started_at
                ).total_seconds() - self.total_paused_seconds
            active_sec = max(0.0, elapsed + float(self.reserved_for(res_t)))
            ratio = active_sec / float(limit)
            return min(1.0, max(0.0, ratio))

        if res_t == BudgetResourceType.PARALLEL_OPERATION:
            ratio = float(self.reserved_for(res_t)) / float(limit)
            return min(1.0, max(0.0, ratio))

        used_res = float(self.used_for(res_t) + self.reserved_for(res_t))
        ratio = used_res / float(limit)
        return min(1.0, max(0.0, ratio))

    def to_dict(self) -> dict[str, Any]:
        """Serialize budget into a JSON-compatible dictionary."""
        return {
            "id": self.id,
            "agent_run_id": self.agent_run_id,
            "limits": {k.value: _serialize_amount(v) for k, v in self.limits.items()},
            "used": {k.value: _serialize_amount(v) for k, v in self.used.items()},
            "reserved": {
                k.value: _serialize_amount(v) for k, v in self.reserved.items()
            },
            "currency": self.currency,
            "warning_threshold": self.warning_threshold,
            "critical_threshold": self.critical_threshold,
            "status": self.status.value,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "started_at": self.started_at.isoformat(),
            "paused_at": self.paused_at.isoformat() if self.paused_at else None,
            "total_paused_seconds": self.total_paused_seconds,
            "metadata": dict(self.metadata),
        }

    def serialize(self) -> dict[str, Any]:
        """Alias for to_dict()."""
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ActionBudget:
        """Reconstruct ActionBudget from dictionary."""
        if not isinstance(data, Mapping):
            raise InvalidActionBudgetContractError(
                "ActionBudget data must be a Mapping"
            )

        raw_limits = data.get("limits", {})
        parsed_limits: dict[BudgetResourceType, int | Decimal | None] = {}
        for k, v in raw_limits.items():
            rt = _validate_resource_type(k)
            parsed_limits[rt] = _deserialize_amount(
                v, field_name=f"limits[{rt.value}]", resource_type=rt
            )

        raw_used = data.get("used", {})
        parsed_used: dict[BudgetResourceType, int | Decimal] = {}
        for k, v in raw_used.items():
            rt = _validate_resource_type(k)
            amt = _deserialize_amount(
                v, field_name=f"used[{rt.value}]", resource_type=rt
            )
            if amt is not None:
                parsed_used[rt] = amt

        raw_reserved = data.get("reserved", {})
        parsed_reserved: dict[BudgetResourceType, int | Decimal] = {}
        for k, v in raw_reserved.items():
            rt = _validate_resource_type(k)
            amt = _deserialize_amount(
                v, field_name=f"reserved[{rt.value}]", resource_type=rt
            )
            if amt is not None:
                parsed_reserved[rt] = amt

        paused_at_raw = data.get("paused_at")
        paused_at_dt = _parse_dt(paused_at_raw, "paused_at") if paused_at_raw else None

        return cls(
            id=data.get("id", ""),
            agent_run_id=data.get("agent_run_id", ""),
            limits=parsed_limits,
            used=parsed_used,
            reserved=parsed_reserved,
            currency=data.get("currency", "EUR"),
            warning_threshold=data.get("warning_threshold", 0.8),
            critical_threshold=data.get("critical_threshold", 0.95),
            status=ActionBudgetStatus(data.get("status", ActionBudgetStatus.ACTIVE)),
            version=data.get("version", 1),
            created_at=_parse_dt(data.get("created_at"), "created_at")
            if "created_at" in data
            else _now_utc(),
            updated_at=_parse_dt(data.get("updated_at"), "updated_at")
            if "updated_at" in data
            else _now_utc(),
            started_at=_parse_dt(data.get("started_at"), "started_at")
            if "started_at" in data
            else _now_utc(),
            paused_at=paused_at_dt,
            total_paused_seconds=data.get("total_paused_seconds", 0.0),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> ActionBudget:
        """Alias for from_dict()."""
        return cls.from_dict(data)


@dataclass(frozen=True, slots=True)
class BudgetReservation:
    """Represents an atomic pre-execution reservation of budget resources."""

    id: str
    budget_id: str
    agent_run_id: str
    allocations: tuple[BudgetAllocation, ...]
    operation_id: str | None = None
    workflow_id: str | None = None
    idempotency_key: str | None = None
    status: BudgetReservationStatus = BudgetReservationStatus.RESERVED
    created_at: datetime = field(default_factory=_now_utc)
    expires_at: datetime = field(default_factory=_now_utc)
    confirmed_at: datetime | None = None
    released_at: datetime | None = None
    failed_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "id", _validate_non_empty_str(self.id, "BudgetReservation.id")
        )
        object.__setattr__(
            self,
            "budget_id",
            _validate_non_empty_str(self.budget_id, "BudgetReservation.budget_id"),
        )
        object.__setattr__(
            self,
            "agent_run_id",
            _validate_non_empty_str(
                self.agent_run_id, "BudgetReservation.agent_run_id"
            ),
        )
        object.__setattr__(
            self,
            "operation_id",
            _validate_optional_str(self.operation_id, "BudgetReservation.operation_id"),
        )
        object.__setattr__(
            self,
            "workflow_id",
            _validate_optional_str(self.workflow_id, "BudgetReservation.workflow_id"),
        )
        object.__setattr__(
            self,
            "idempotency_key",
            _validate_optional_str(
                self.idempotency_key, "BudgetReservation.idempotency_key"
            ),
        )

        if not isinstance(self.allocations, (tuple, list, Sequence)):
            raise InvalidActionBudgetContractError(
                "allocations must be a sequence of BudgetAllocation instances"
            )
        clean_allocs = tuple(self.allocations)
        if not clean_allocs:
            raise InvalidActionBudgetContractError(
                "allocations cannot be empty for a reservation"
            )
        for idx, alloc in enumerate(clean_allocs):
            if not isinstance(alloc, BudgetAllocation):
                raise InvalidActionBudgetContractError(
                    f"allocations[{idx}] must be a BudgetAllocation, got {type(alloc).__name__}"
                )
        object.__setattr__(self, "allocations", clean_allocs)

        if not isinstance(self.status, BudgetReservationStatus):
            if isinstance(self.status, str):
                try:
                    object.__setattr__(
                        self, "status", BudgetReservationStatus(self.status)
                    )
                except ValueError as exc:
                    raise InvalidActionBudgetContractError(
                        f"Invalid reservation status: {self.status!r}"
                    ) from exc
            else:
                raise InvalidActionBudgetContractError(
                    f"Invalid status type: {type(self.status).__name__}"
                )

        object.__setattr__(
            self, "created_at", _ensure_aware_dt(self.created_at, "created_at")
        )
        object.__setattr__(
            self, "expires_at", _ensure_aware_dt(self.expires_at, "expires_at")
        )
        if self.expires_at <= self.created_at:
            raise InvalidActionBudgetContractError(
                "expires_at must be strictly greater than created_at"
            )

        if self.confirmed_at is not None:
            object.__setattr__(
                self,
                "confirmed_at",
                _ensure_aware_dt(self.confirmed_at, "confirmed_at"),
            )
        if self.released_at is not None:
            object.__setattr__(
                self,
                "released_at",
                _ensure_aware_dt(self.released_at, "released_at"),
            )
        if self.failed_at is not None:
            object.__setattr__(
                self, "failed_at", _ensure_aware_dt(self.failed_at, "failed_at")
            )

        meta_dict = dict(self.metadata) if self.metadata else {}
        object.__setattr__(self, "metadata", MappingProxyType(meta_dict))

    def is_expired(self, now: datetime | None = None) -> bool:
        """Return True if reservation expires_at is before or equal to now."""
        ref = now if now is not None else _now_utc()
        ref = _ensure_aware_dt(ref, "now")
        return self.expires_at <= ref

    def to_dict(self) -> dict[str, Any]:
        """Serialize reservation into a JSON-compatible dictionary."""
        return {
            "id": self.id,
            "budget_id": self.budget_id,
            "agent_run_id": self.agent_run_id,
            "allocations": [a.to_dict() for a in self.allocations],
            "operation_id": self.operation_id,
            "workflow_id": self.workflow_id,
            "idempotency_key": self.idempotency_key,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "confirmed_at": self.confirmed_at.isoformat()
            if self.confirmed_at
            else None,
            "released_at": self.released_at.isoformat() if self.released_at else None,
            "failed_at": self.failed_at.isoformat() if self.failed_at else None,
            "metadata": dict(self.metadata),
        }

    def serialize(self) -> dict[str, Any]:
        """Alias for to_dict()."""
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BudgetReservation:
        """Reconstruct BudgetReservation from dictionary."""
        if not isinstance(data, Mapping):
            raise InvalidActionBudgetContractError(
                "BudgetReservation data must be a Mapping"
            )
        raw_allocs = data.get("allocations", [])
        parsed_allocs = tuple(BudgetAllocation.from_dict(a) for a in raw_allocs)

        return cls(
            id=data.get("id", ""),
            budget_id=data.get("budget_id", ""),
            agent_run_id=data.get("agent_run_id", ""),
            allocations=parsed_allocs,
            operation_id=data.get("operation_id"),
            workflow_id=data.get("workflow_id"),
            idempotency_key=data.get("idempotency_key"),
            status=BudgetReservationStatus(
                data.get("status", BudgetReservationStatus.RESERVED)
            ),
            created_at=_parse_dt(data.get("created_at"), "created_at")
            if "created_at" in data
            else _now_utc(),
            expires_at=_parse_dt(data.get("expires_at"), "expires_at")
            if "expires_at" in data
            else _now_utc(),
            confirmed_at=_parse_dt(data.get("confirmed_at"), "confirmed_at")
            if data.get("confirmed_at")
            else None,
            released_at=_parse_dt(data.get("released_at"), "released_at")
            if data.get("released_at")
            else None,
            failed_at=_parse_dt(data.get("failed_at"), "failed_at")
            if data.get("failed_at")
            else None,
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> BudgetReservation:
        """Alias for from_dict()."""
        return cls.from_dict(data)


@dataclass(frozen=True, slots=True)
class BudgetConsumption:
    """Audit record of confirmed budget consumption."""

    id: str
    budget_id: str
    agent_run_id: str
    reservation_id: str
    allocations: tuple[BudgetAllocation, ...]
    outcome: BudgetConsumptionOutcome = BudgetConsumptionOutcome.SUCCESS
    operation_id: str | None = None
    consumed_at: datetime = field(default_factory=_now_utc)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "id", _validate_non_empty_str(self.id, "BudgetConsumption.id")
        )
        object.__setattr__(
            self,
            "budget_id",
            _validate_non_empty_str(self.budget_id, "BudgetConsumption.budget_id"),
        )
        object.__setattr__(
            self,
            "agent_run_id",
            _validate_non_empty_str(
                self.agent_run_id, "BudgetConsumption.agent_run_id"
            ),
        )
        object.__setattr__(
            self,
            "reservation_id",
            _validate_non_empty_str(
                self.reservation_id, "BudgetConsumption.reservation_id"
            ),
        )
        object.__setattr__(
            self,
            "operation_id",
            _validate_optional_str(self.operation_id, "BudgetConsumption.operation_id"),
        )

        if not isinstance(self.allocations, (tuple, list, Sequence)):
            raise InvalidActionBudgetContractError(
                "allocations must be a sequence of BudgetAllocation instances"
            )
        clean_allocs = tuple(self.allocations)
        for idx, alloc in enumerate(clean_allocs):
            if not isinstance(alloc, BudgetAllocation):
                raise InvalidActionBudgetContractError(
                    f"allocations[{idx}] must be a BudgetAllocation, got {type(alloc).__name__}"
                )
        object.__setattr__(self, "allocations", clean_allocs)

        if not isinstance(self.outcome, BudgetConsumptionOutcome):
            if isinstance(self.outcome, str):
                try:
                    object.__setattr__(
                        self, "outcome", BudgetConsumptionOutcome(self.outcome)
                    )
                except ValueError as exc:
                    raise InvalidActionBudgetContractError(
                        f"Invalid outcome: {self.outcome!r}"
                    ) from exc
            else:
                raise InvalidActionBudgetContractError(
                    f"Invalid outcome type: {type(self.outcome).__name__}"
                )

        object.__setattr__(
            self, "consumed_at", _ensure_aware_dt(self.consumed_at, "consumed_at")
        )

        meta_dict = dict(self.metadata) if self.metadata else {}
        object.__setattr__(self, "metadata", MappingProxyType(meta_dict))

    def to_dict(self) -> dict[str, Any]:
        """Serialize consumption into a JSON-compatible dictionary."""
        return {
            "id": self.id,
            "budget_id": self.budget_id,
            "agent_run_id": self.agent_run_id,
            "reservation_id": self.reservation_id,
            "allocations": [a.to_dict() for a in self.allocations],
            "outcome": self.outcome.value,
            "operation_id": self.operation_id,
            "consumed_at": self.consumed_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def serialize(self) -> dict[str, Any]:
        """Alias for to_dict()."""
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BudgetConsumption:
        """Reconstruct BudgetConsumption from dictionary."""
        if not isinstance(data, Mapping):
            raise InvalidActionBudgetContractError(
                "BudgetConsumption data must be a Mapping"
            )
        raw_allocs = data.get("allocations", [])
        parsed_allocs = tuple(BudgetAllocation.from_dict(a) for a in raw_allocs)

        return cls(
            id=data.get("id", ""),
            budget_id=data.get("budget_id", ""),
            agent_run_id=data.get("agent_run_id", ""),
            reservation_id=data.get("reservation_id", ""),
            allocations=parsed_allocs,
            outcome=BudgetConsumptionOutcome(
                data.get("outcome", BudgetConsumptionOutcome.SUCCESS)
            ),
            operation_id=data.get("operation_id"),
            consumed_at=_parse_dt(data.get("consumed_at"), "consumed_at")
            if "consumed_at" in data
            else _now_utc(),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> BudgetConsumption:
        """Alias for from_dict()."""
        return cls.from_dict(data)


@dataclass(frozen=True, slots=True)
class BudgetAdjustment:
    """Audit record of an authorized increase or decrease to budget limits."""

    id: str
    budget_id: str
    adjustment_type: BudgetAdjustmentType
    resource_type: BudgetResourceType
    previous_limit: int | Decimal | None
    new_limit: int | Decimal | None
    delta: int | Decimal | None
    actor_id: str
    approval_request_id: str | None = None
    reason_codes: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_now_utc)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "id", _validate_non_empty_str(self.id, "BudgetAdjustment.id")
        )
        object.__setattr__(
            self,
            "budget_id",
            _validate_non_empty_str(self.budget_id, "BudgetAdjustment.budget_id"),
        )
        object.__setattr__(
            self,
            "actor_id",
            _validate_non_empty_str(self.actor_id, "BudgetAdjustment.actor_id"),
        )
        object.__setattr__(
            self,
            "approval_request_id",
            _validate_optional_str(
                self.approval_request_id, "BudgetAdjustment.approval_request_id"
            ),
        )

        res_t = _validate_resource_type(self.resource_type)
        object.__setattr__(self, "resource_type", res_t)

        if not isinstance(self.adjustment_type, BudgetAdjustmentType):
            if isinstance(self.adjustment_type, str):
                try:
                    object.__setattr__(
                        self,
                        "adjustment_type",
                        BudgetAdjustmentType(self.adjustment_type),
                    )
                except ValueError as exc:
                    raise InvalidActionBudgetContractError(
                        f"Invalid adjustment_type: {self.adjustment_type!r}"
                    ) from exc
            else:
                raise InvalidActionBudgetContractError(
                    f"Invalid adjustment_type type: {type(self.adjustment_type).__name__}"
                )

        prev_lim = _validate_amount_value(
            self.previous_limit,
            field_name="previous_limit",
            resource_type=res_t,
            allow_none=True,
            allow_zero=True,
        )
        object.__setattr__(self, "previous_limit", prev_lim)

        new_lim = _validate_amount_value(
            self.new_limit,
            field_name="new_limit",
            resource_type=res_t,
            allow_none=True,
            allow_zero=True,
        )
        object.__setattr__(self, "new_limit", new_lim)

        object.__setattr__(
            self,
            "reason_codes",
            tuple(
                _validate_non_empty_str(r, "reason_codes item")
                for r in self.reason_codes
            ),
        )

        object.__setattr__(
            self, "created_at", _ensure_aware_dt(self.created_at, "created_at")
        )

        meta_dict = dict(self.metadata) if self.metadata else {}
        object.__setattr__(self, "metadata", MappingProxyType(meta_dict))

    def to_dict(self) -> dict[str, Any]:
        """Serialize adjustment into a JSON-compatible dictionary."""
        return {
            "id": self.id,
            "budget_id": self.budget_id,
            "adjustment_type": self.adjustment_type.value,
            "resource_type": self.resource_type.value,
            "previous_limit": _serialize_amount(self.previous_limit),
            "new_limit": _serialize_amount(self.new_limit),
            "delta": _serialize_amount(self.delta),
            "actor_id": self.actor_id,
            "approval_request_id": self.approval_request_id,
            "reason_codes": list(self.reason_codes),
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def serialize(self) -> dict[str, Any]:
        """Alias for to_dict()."""
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BudgetAdjustment:
        """Reconstruct BudgetAdjustment from dictionary."""
        if not isinstance(data, Mapping):
            raise InvalidActionBudgetContractError(
                "BudgetAdjustment data must be a Mapping"
            )

        res_t = _validate_resource_type(data.get("resource_type"))
        prev_lim = _deserialize_amount(
            data.get("previous_limit"),
            field_name="previous_limit",
            resource_type=res_t,
        )
        new_lim = _deserialize_amount(
            data.get("new_limit"), field_name="new_limit", resource_type=res_t
        )
        delta_val = _deserialize_amount(
            data.get("delta"), field_name="delta", resource_type=res_t
        )

        return cls(
            id=data.get("id", ""),
            budget_id=data.get("budget_id", ""),
            adjustment_type=BudgetAdjustmentType(
                data.get("adjustment_type", BudgetAdjustmentType.INCREASE)
            ),
            resource_type=res_t,
            previous_limit=prev_lim,
            new_limit=new_lim,
            delta=delta_val,
            actor_id=data.get("actor_id", ""),
            approval_request_id=data.get("approval_request_id"),
            reason_codes=tuple(data.get("reason_codes", ())),
            created_at=_parse_dt(data.get("created_at"), "created_at")
            if "created_at" in data
            else _now_utc(),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> BudgetAdjustment:
        """Alias for from_dict()."""
        return cls.from_dict(data)


@dataclass(frozen=True, slots=True)
class BudgetEvaluationResult:
    """Structured result of evaluating budget availability for requested allocations."""

    budget_id: str
    allowed: bool
    denied: bool
    warning: bool
    exhausted: bool
    status: ActionBudgetStatus
    requested_allocations: tuple[BudgetAllocation, ...]
    available: Mapping[BudgetResourceType, int | Decimal | None]
    reason_codes: tuple[str, ...]
    evaluated_at: datetime = field(default_factory=_now_utc)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "budget_id", _validate_non_empty_str(self.budget_id, "budget_id")
        )
        if isinstance(self.allowed, bool) and isinstance(self.denied, bool):
            if self.allowed == self.denied:
                raise InvalidActionBudgetContractError(
                    "allowed and denied must be strictly opposite booleans"
                )
        else:
            raise InvalidActionBudgetContractError(
                "allowed and denied must be booleans"
            )

        if not isinstance(self.warning, bool) or not isinstance(self.exhausted, bool):
            raise InvalidActionBudgetContractError(
                "warning and exhausted must be booleans"
            )

        if not isinstance(self.status, ActionBudgetStatus):
            if isinstance(self.status, str):
                try:
                    object.__setattr__(self, "status", ActionBudgetStatus(self.status))
                except ValueError as exc:
                    raise InvalidActionBudgetContractError(
                        f"Invalid status: {self.status!r}"
                    ) from exc
            else:
                raise InvalidActionBudgetContractError(
                    f"Invalid status type: {type(self.status).__name__}"
                )

        if not isinstance(self.requested_allocations, (tuple, list, Sequence)):
            raise InvalidActionBudgetContractError(
                "requested_allocations must be a sequence of BudgetAllocation instances"
            )
        clean_allocs = tuple(self.requested_allocations)
        for idx, alloc in enumerate(clean_allocs):
            if not isinstance(alloc, BudgetAllocation):
                raise InvalidActionBudgetContractError(
                    f"requested_allocations[{idx}] must be a BudgetAllocation, got {type(alloc).__name__}"
                )
        object.__setattr__(self, "requested_allocations", clean_allocs)

        clean_avail: dict[BudgetResourceType, int | Decimal | None] = {}
        for r_k, r_v in self.available.items():
            res_t = _validate_resource_type(r_k)
            v = _validate_amount_value(
                r_v,
                field_name=f"available[{res_t.value}]",
                resource_type=res_t,
                allow_none=True,
                allow_zero=True,
            )
            clean_avail[res_t] = v
        object.__setattr__(self, "available", MappingProxyType(clean_avail))

        object.__setattr__(
            self,
            "reason_codes",
            tuple(
                _validate_non_empty_str(r, "reason_codes item")
                for r in self.reason_codes
            ),
        )
        object.__setattr__(
            self, "evaluated_at", _ensure_aware_dt(self.evaluated_at, "evaluated_at")
        )

        meta_dict = dict(self.metadata) if self.metadata else {}
        object.__setattr__(self, "metadata", MappingProxyType(meta_dict))

    def to_dict(self) -> dict[str, Any]:
        """Serialize evaluation result into a JSON-compatible dictionary."""
        return {
            "budget_id": self.budget_id,
            "allowed": self.allowed,
            "denied": self.denied,
            "warning": self.warning,
            "exhausted": self.exhausted,
            "status": self.status.value,
            "requested_allocations": [a.to_dict() for a in self.requested_allocations],
            "available": {
                k.value: _serialize_amount(v) for k, v in self.available.items()
            },
            "reason_codes": list(self.reason_codes),
            "evaluated_at": self.evaluated_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def serialize(self) -> dict[str, Any]:
        """Alias for to_dict()."""
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BudgetEvaluationResult:
        """Reconstruct BudgetEvaluationResult from dictionary."""
        if not isinstance(data, Mapping):
            raise InvalidActionBudgetContractError(
                "BudgetEvaluationResult data must be a Mapping"
            )
        raw_allocs = data.get("requested_allocations", [])
        parsed_allocs = tuple(BudgetAllocation.from_dict(a) for a in raw_allocs)

        raw_avail = data.get("available", {})
        parsed_avail: dict[BudgetResourceType, int | Decimal | None] = {}
        for k, v in raw_avail.items():
            rt = _validate_resource_type(k)
            parsed_avail[rt] = _deserialize_amount(
                v, field_name=f"available[{rt.value}]", resource_type=rt
            )

        return cls(
            budget_id=data.get("budget_id", ""),
            allowed=data.get("allowed", False),
            denied=data.get("denied", True),
            warning=data.get("warning", False),
            exhausted=data.get("exhausted", False),
            status=ActionBudgetStatus(data.get("status", ActionBudgetStatus.ACTIVE)),
            requested_allocations=parsed_allocs,
            available=parsed_avail,
            reason_codes=tuple(data.get("reason_codes", ())),
            evaluated_at=_parse_dt(data.get("evaluated_at"), "evaluated_at")
            if "evaluated_at" in data
            else _now_utc(),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> BudgetEvaluationResult:
        """Alias for from_dict()."""
        return cls.from_dict(data)
