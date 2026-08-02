"""Immutable, Decimal-only contracts for Phase 9.31 economic controls."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, DecimalException
from enum import Enum
from types import MappingProxyType
from typing import Any

from .economic_budget_errors import InvalidEconomicBudgetContractError


class EconomicBudgetSource(str, Enum):
    GOAL = "goal"
    WORKFLOW = "workflow"
    OPERATION = "operation"
    POLICY = "policy"
    APPROVAL = "approval"


class _StrictValueEnum(str, Enum):
    @classmethod
    def from_value(cls, value: str | Enum):
        try:
            return value if isinstance(value, cls) else cls(value)
        except (TypeError, ValueError) as exc:
            raise InvalidEconomicBudgetContractError(
                f"invalid {cls.__name__} value: {value!r}"
            ) from exc


class EconomicBudgetStatus(_StrictValueEnum):
    ACTIVE = "active"
    AVAILABLE = "available"
    WARNING = "warning"
    NEAR_EXHAUSTION = "near_exhaustion"
    EXHAUSTED = "exhausted"
    PAUSED = "paused"
    APPROVAL_REQUIRED = "approval_required"
    DENIED = "denied"


class EconomicBudgetAction(_StrictValueEnum):
    ALLOW = "allow"
    ALLOW_WITH_RESERVATION = "allow_with_reservation"
    USE_LOWER_COST_MODEL = "use_lower_cost_model"
    REDUCE_SCOPE = "reduce_scope"
    ENABLE_SAVINGS_MODE = "enable_savings_mode"
    WARN = "warn"
    PAUSE = "pause"
    REQUEST_APPROVAL = "request_approval"
    ESCALATE = "escalate"
    DENY = "deny"
    COMPLETE_PARTIALLY = "complete_partially"


def _id(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidEconomicBudgetContractError(f"{name} must be a non-empty string")
    return value.strip()


def _decimal(value: Any, name: str, *, none: bool = True) -> Decimal | None:
    if value is None and none:
        return None
    if isinstance(value, bool):
        raise InvalidEconomicBudgetContractError(f"{name} cannot be boolean")
    if isinstance(value, float):
        raise InvalidEconomicBudgetContractError(f"{name} must use Decimal, not float")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (DecimalException, ValueError, TypeError) as exc:
        raise InvalidEconomicBudgetContractError(f"{name} must be a Decimal") from exc
    if not result.is_finite() or result < 0:
        raise InvalidEconomicBudgetContractError(
            f"{name} must be finite and non-negative"
        )
    return result


def _integer(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InvalidEconomicBudgetContractError(
            f"{name} must be a non-negative integer"
        )
    return value


def _mapping(value: Mapping[str, Any] | None) -> MappingProxyType:
    if value is None:
        value = {}
    if not isinstance(value, Mapping):
        raise InvalidEconomicBudgetContractError("metadata must be a mapping")
    return MappingProxyType(dict(value))


def _source(value: EconomicBudgetSource | str) -> EconomicBudgetSource:
    try:
        return (
            value
            if isinstance(value, EconomicBudgetSource)
            else EconomicBudgetSource(value)
        )
    except (TypeError, ValueError) as exc:
        raise InvalidEconomicBudgetContractError(
            f"invalid economic budget source: {value!r}"
        ) from exc


@dataclass(frozen=True, slots=True)
class EconomicBudget:
    id: str
    source: EconomicBudgetSource | str = EconomicBudgetSource.GOAL
    currency: str = "EUR"
    maximum_cost: Decimal | None = None
    maximum_estimated_cost_per_operation: Decimal | None = None
    maximum_actual_cost_per_operation: Decimal | None = None
    maximum_input_tokens: int | None = None
    maximum_output_tokens: int | None = None
    maximum_total_tokens: int | None = None
    premium_allowed: bool = False
    overrun_tolerance: Decimal = Decimal(0)
    warning_threshold_percent: int = 80
    critical_threshold_percent: int = 95
    on_warning: EconomicBudgetAction | str = EconomicBudgetAction.WARN
    on_exhaustion: EconomicBudgetAction | str = EconomicBudgetAction.PAUSE
    allow_overrun_with_approval: bool = False
    savings_mode: bool = False
    premium_reserve: Decimal | None = None
    estimated_cost: Decimal = Decimal(0)
    reserved_cost: Decimal = Decimal(0)
    actual_cost: Decimal = Decimal(0)
    status: EconomicBudgetStatus | str = EconomicBudgetStatus.AVAILABLE
    metadata: Mapping[str, Any] = field(default_factory=dict)
    goal_id: str | None = None
    workflow_id: str | None = None
    operation_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _id(self.id, "id"))
        object.__setattr__(self, "source", _source(self.source))
        object.__setattr__(
            self, "on_warning", EconomicBudgetAction.from_value(self.on_warning)
        )
        object.__setattr__(
            self, "on_exhaustion", EconomicBudgetAction.from_value(self.on_exhaustion)
        )
        object.__setattr__(self, "status", EconomicBudgetStatus.from_value(self.status))
        currency = _id(self.currency, "currency").upper()
        if len(currency) != 3 or not currency.isalpha():
            raise InvalidEconomicBudgetContractError(
                "currency must be a 3-letter ISO 4217 code"
            )
        object.__setattr__(self, "currency", currency)
        for name in (
            "maximum_cost",
            "maximum_estimated_cost_per_operation",
            "maximum_actual_cost_per_operation",
            "overrun_tolerance",
            "premium_reserve",
            "estimated_cost",
            "reserved_cost",
            "actual_cost",
        ):
            object.__setattr__(
                self,
                name,
                _decimal(
                    getattr(self, name),
                    name,
                    none=name
                    in {
                        "maximum_cost",
                        "maximum_estimated_cost_per_operation",
                        "maximum_actual_cost_per_operation",
                        "premium_reserve",
                    },
                ),
            )
        for name in (
            "maximum_input_tokens",
            "maximum_output_tokens",
            "maximum_total_tokens",
        ):
            object.__setattr__(self, name, _integer(getattr(self, name), name))
        if (
            not isinstance(self.premium_allowed, bool)
            or not isinstance(self.allow_overrun_with_approval, bool)
            or not isinstance(self.savings_mode, bool)
        ):
            raise InvalidEconomicBudgetContractError(
                "premium and overrun flags must be boolean"
            )
        if (
            isinstance(self.warning_threshold_percent, bool)
            or not isinstance(self.warning_threshold_percent, int)
            or not 0 <= self.warning_threshold_percent <= 100
        ):
            raise InvalidEconomicBudgetContractError(
                "warning_threshold_percent must be an integer from 0 to 100"
            )
        if (
            isinstance(self.critical_threshold_percent, bool)
            or not isinstance(self.critical_threshold_percent, int)
            or not 0 <= self.critical_threshold_percent <= 100
        ):
            raise InvalidEconomicBudgetContractError(
                "critical_threshold_percent must be an integer from 0 to 100"
            )
        object.__setattr__(self, "metadata", _mapping(self.metadata))
        for name in ("goal_id", "workflow_id", "operation_id"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _id(value, name))

    def to_dict(self) -> dict[str, Any]:
        result = {
            name: (
                str(value)
                if isinstance(value, Decimal)
                else value.value
                if isinstance(value, Enum)
                else dict(value)
                if isinstance(value, Mapping)
                else value
            )
            for name, value in (
                (f.name, getattr(self, f.name))
                for f in self.__dataclass_fields__.values()
            )
        }
        return result

    serialize = to_dict

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EconomicBudget:
        if not isinstance(data, Mapping):
            raise InvalidEconomicBudgetContractError(
                "economic budget payload must be a mapping"
            )
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class ResolvedEconomicBudget:
    maximum_cost: Decimal | None = None
    maximum_estimated_cost_per_operation: Decimal | None = None
    maximum_actual_cost_per_operation: Decimal | None = None
    maximum_input_tokens: int | None = None
    maximum_output_tokens: int | None = None
    maximum_total_tokens: int | None = None
    currency: str = "EUR"
    premium_allowed: bool = False
    overrun_tolerance: Decimal = Decimal(0)
    warning_threshold_percent: int = 80
    critical_threshold_percent: int = 95
    on_warning: EconomicBudgetAction | str = EconomicBudgetAction.WARN
    on_exhaustion: EconomicBudgetAction | str = EconomicBudgetAction.PAUSE
    allow_overrun_with_approval: bool = False
    savings_mode: bool = False
    provenance: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    status: EconomicBudgetStatus | str = EconomicBudgetStatus.AVAILABLE
    warning: bool = False
    near_exhaustion: bool = False
    exhausted: bool = False
    approval_required: bool = False
    estimated_cost_excessive: bool = False
    actual_cost_excessive: bool = False
    policy_denied: bool = False
    estimated_cost: Decimal = Decimal(0)
    actual_cost: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        currency = _id(self.currency, "currency").upper()
        if len(currency) != 3 or not currency.isalpha():
            raise InvalidEconomicBudgetContractError(
                "currency must be a 3-letter ISO 4217 code"
            )
        object.__setattr__(self, "currency", currency)
        object.__setattr__(
            self, "on_warning", EconomicBudgetAction.from_value(self.on_warning)
        )
        object.__setattr__(
            self, "on_exhaustion", EconomicBudgetAction.from_value(self.on_exhaustion)
        )
        object.__setattr__(self, "status", EconomicBudgetStatus.from_value(self.status))
        for name in (
            "maximum_cost",
            "maximum_estimated_cost_per_operation",
            "maximum_actual_cost_per_operation",
            "overrun_tolerance",
        ):
            object.__setattr__(self, name, _decimal(getattr(self, name), name))
        for name in (
            "maximum_input_tokens",
            "maximum_output_tokens",
            "maximum_total_tokens",
        ):
            object.__setattr__(self, name, _integer(getattr(self, name), name))
        for name in ("warning_threshold_percent", "critical_threshold_percent"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 0 <= value <= 100
            ):
                raise InvalidEconomicBudgetContractError(
                    f"{name} must be an integer from 0 to 100"
                )
        object.__setattr__(
            self, "provenance", tuple(_id(x, "provenance") for x in self.provenance)
        )
        object.__setattr__(
            self,
            "reason_codes",
            tuple(_id(x, "reason_code") for x in self.reason_codes),
        )
        object.__setattr__(self, "metadata", _mapping(self.metadata))
        for name in (
            "warning",
            "near_exhaustion",
            "exhausted",
            "approval_required",
            "estimated_cost_excessive",
            "actual_cost_excessive",
            "policy_denied",
        ):
            if not isinstance(getattr(self, name), bool):
                raise InvalidEconomicBudgetContractError(f"{name} must be boolean")
        object.__setattr__(
            self,
            "estimated_cost",
            _decimal(self.estimated_cost, "estimated_cost", none=False),
        )
        object.__setattr__(
            self, "actual_cost", _decimal(self.actual_cost, "actual_cost", none=False)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            k: (
                str(v)
                if isinstance(v, Decimal)
                else v.value
                if isinstance(v, Enum)
                else dict(v)
                if isinstance(v, Mapping)
                else list(v)
                if isinstance(v, tuple)
                else v
            )
            for k, v in (
                (f.name, getattr(self, f.name))
                for f in self.__dataclass_fields__.values()
            )
        }

    serialize = to_dict

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ResolvedEconomicBudget:
        if not isinstance(data, Mapping):
            raise InvalidEconomicBudgetContractError(
                "resolved economic budget payload must be a mapping"
            )
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class ModelCostEstimate:
    input_cost: Decimal
    cached_input_cost: Decimal
    output_cost: Decimal
    total_cost: Decimal
    currency: str = "USD"
    complete: bool = True
    missing_prices: tuple[str, ...] = ()
    known_cost: Decimal | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    total_tokens: int | None = None

    def __post_init__(self) -> None:
        for name in ("input_cost", "cached_input_cost", "output_cost", "total_cost"):
            object.__setattr__(
                self, name, _decimal(getattr(self, name), name, none=False)
            )
        object.__setattr__(self, "currency", _id(self.currency, "currency").upper())
        object.__setattr__(
            self,
            "missing_prices",
            tuple(_id(x, "missing_price") for x in self.missing_prices),
        )
        object.__setattr__(
            self,
            "known_cost",
            self.total_cost
            if self.known_cost is None
            else _decimal(self.known_cost, "known_cost", none=False),
        )
        if not isinstance(self.complete, bool):
            raise InvalidEconomicBudgetContractError("complete must be boolean")
        for name in (
            "input_tokens",
            "output_tokens",
            "cached_input_tokens",
            "total_tokens",
        ):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(self, name, _integer(value, name))

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_cost": str(self.input_cost),
            "cached_input_cost": str(self.cached_input_cost),
            "output_cost": str(self.output_cost),
            "total_cost": str(self.total_cost),
            "known_cost": str(self.known_cost),
            "currency": self.currency,
            "complete": self.complete,
            "missing_prices": list(self.missing_prices),
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "total_tokens": self.total_tokens,
        }

    serialize = to_dict

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ModelCostEstimate:
        if not isinstance(data, Mapping):
            raise InvalidEconomicBudgetContractError(
                "model cost estimate payload must be a mapping"
            )
        return cls(
            input_cost=data["input_cost"],
            cached_input_cost=data["cached_input_cost"],
            output_cost=data["output_cost"],
            total_cost=data["total_cost"],
            currency=data.get("currency", "USD"),
            complete=data.get("complete", True),
            missing_prices=tuple(data.get("missing_prices", ())),
            known_cost=data.get("known_cost"),
            input_tokens=data.get("input_tokens"),
            output_tokens=data.get("output_tokens"),
            cached_input_tokens=data.get("cached_input_tokens"),
            total_tokens=data.get("total_tokens"),
        )


ModelCostActual = ModelCostEstimate


@dataclass(frozen=True, slots=True)
class EconomicBudgetDecision:
    decision: EconomicBudgetAction | str
    reason_codes: tuple[str, ...] = ()
    resolved: ResolvedEconomicBudget = field(default_factory=ResolvedEconomicBudget)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "decision", EconomicBudgetAction.from_value(self.decision)
        )
        object.__setattr__(
            self,
            "reason_codes",
            tuple(_id(x, "reason_code") for x in self.reason_codes),
        )

    def to_snapshot(self) -> dict[str, Any]:
        snapshot = self.resolved.to_dict()
        unavailable = self.decision in {
            EconomicBudgetAction.DENY,
            EconomicBudgetAction.PAUSE,
            EconomicBudgetAction.REQUEST_APPROVAL,
        }
        snapshot.update(
            {
                "available": not unavailable,
                "decision": self.decision.value,
                "reason_codes": list(self.reason_codes),
            }
        )
        return snapshot

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> EconomicBudgetDecision:
        if not isinstance(data, Mapping):
            raise InvalidEconomicBudgetContractError(
                "economic budget decision payload must be a mapping"
            )
        return cls(
            decision=data["decision"],
            reason_codes=tuple(data.get("reason_codes", ())),
            resolved=ResolvedEconomicBudget.from_dict(data.get("resolved", data)),
        )
