"""Immutable, serializable contracts for Phase 9.30 model fallback."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.model_fallback_errors import InvalidModelFallbackContractError
from cmm.agent_runtime.model_requirements_contracts import (
    model_requirements_from_dict,
    model_requirements_to_dict,
)
from kernel.llm.model_ranking import ModelRankingPolicy
from kernel.llm.model_router import (
    RejectedModel,
    RoutingCandidate,
    RoutingDecision,
)
from kernel.llm.model_selection import ModelRequirements


class _ValueEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class ModelFallbackTrigger(_ValueEnum):
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    MODEL_UNAVAILABLE = "model_unavailable"
    ROUTING_NO_MATCH = "routing_no_match"
    PARSING_FAILED = "parsing_failed"
    STRUCTURED_OUTPUT_INVALID = "structured_output_invalid"
    VALIDATION_FAILED = "validation_failed"
    QUALITY_INSUFFICIENT = "quality_insufficient"
    CONTEXT_INSUFFICIENT = "context_insufficient"
    ESTIMATED_COST_EXCESSIVE = "estimated_cost_excessive"
    ACTUAL_COST_EXCESSIVE = "actual_cost_excessive"
    BUDGET_EXHAUSTED = "budget_exhausted"
    PRIVACY_INCOMPATIBLE = "privacy_incompatible"
    CAPABILITY_MISSING = "capability_missing"
    EMPTY_RESPONSE = "empty_response"
    INVALID_RESPONSE = "invalid_response"
    TRANSIENT_ERROR = "transient_error"
    PERMANENT_ERROR = "permanent_error"
    RETRIES_EXHAUSTED = "retries_exhausted"


class ModelFallbackAction(_ValueEnum):
    RETRY_SAME_MODEL = "retry_same_model"
    RETRY_MODIFIED_PARAMETERS = "retry_modified_parameters"
    NEXT_ROUTING_CANDIDATE = "next_routing_candidate"
    SELECT_EQUIVALENT_MODEL = "select_equivalent_model"
    SELECT_LOWER_COST_MODEL = "select_lower_cost_model"
    SELECT_HIGHER_QUALITY_MODEL = "select_higher_quality_model"
    REROUTE = "reroute"
    REOBSERVE = "reobserve"
    REVALIDATE = "revalidate"
    REPLAN = "replan"
    REQUEST_APPROVAL = "request_approval"
    ESCALATE = "escalate"
    PAUSE = "pause"
    FAIL_TERMINAL = "fail_terminal"


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(_freeze(v) for v in value)
    return value


def _json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: _json(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(v) for v in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, ModelRequirements):
        return model_requirements_to_dict(value)
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


def _enum(value: Any, enum_type: type[Enum], field_name: str) -> Any:
    try:
        return value if isinstance(value, enum_type) else enum_type(str(value))
    except ValueError as exc:
        raise InvalidModelFallbackContractError(
            f"unsupported {field_name}: {value!r}"
        ) from exc


def _routing_to_dict(decision: RoutingDecision) -> dict[str, Any]:
    if not isinstance(decision, RoutingDecision):
        raise InvalidModelFallbackContractError(
            "routing_decision must be a RoutingDecision"
        )
    return {
        "id": decision.id,
        "status": decision.status,
        "selected_model_id": decision.selected_model_id,
        "selected_provider_id": decision.selected_provider_id,
        "candidates": [
            {
                "rank": candidate.rank,
                "qualified_model_id": candidate.qualified_model_id,
                "provider_id": candidate.provider_id,
                "model_id": candidate.model_id,
                "input_cost_per_million": (
                    str(candidate.input_cost_per_million)
                    if candidate.input_cost_per_million is not None
                    else None
                ),
                "output_cost_per_million": (
                    str(candidate.output_cost_per_million)
                    if candidate.output_cost_per_million is not None
                    else None
                ),
                "context_window": candidate.context_window,
            }
            for candidate in decision.candidates
        ],
        "rejected_models": [
            {
                "qualified_model_id": model.qualified_model_id,
                "reasons": list(model.reasons),
            }
            for model in decision.rejected_models
        ],
        "requirements": model_requirements_to_dict(decision.requirements),
        "ranking_policy": {
            "strategy": decision.ranking_policy.strategy,
            "preferred_providers": list(decision.ranking_policy.preferred_providers),
        },
        "reason_codes": list(decision.reason_codes),
        "configuration_version": decision.configuration_version,
        "metadata": dict(decision.metadata),
    }


def _routing_from_dict(data: Mapping[str, Any]) -> RoutingDecision:
    try:
        ranking = data.get("ranking_policy", {})
        ranking_policy = ModelRankingPolicy(
            strategy=ranking.get("strategy", "lowest_cost"),
            preferred_providers=tuple(ranking.get("preferred_providers", ())),
        )
        candidates = tuple(
            RoutingCandidate(
                rank=int(item["rank"]),
                qualified_model_id=str(item["qualified_model_id"]),
                provider_id=str(item["provider_id"]),
                model_id=str(item["model_id"]),
                input_cost_per_million=(
                    Decimal(str(item["input_cost_per_million"]))
                    if item.get("input_cost_per_million") is not None
                    else None
                ),
                output_cost_per_million=(
                    Decimal(str(item["output_cost_per_million"]))
                    if item.get("output_cost_per_million") is not None
                    else None
                ),
                context_window=item.get("context_window"),
            )
            for item in data.get("candidates", ())
        )
        rejected = tuple(
            RejectedModel(
                qualified_model_id=str(item["qualified_model_id"]),
                reasons=tuple(item.get("reasons", ())),
            )
            for item in data.get("rejected_models", ())
        )
        return RoutingDecision(
            id=str(data["id"]),
            status=data["status"],
            selected_model_id=data.get("selected_model_id"),
            selected_provider_id=data.get("selected_provider_id"),
            candidates=candidates,
            rejected_models=rejected,
            requirements=model_requirements_from_dict(data["requirements"]),
            ranking_policy=ranking_policy,
            reason_codes=tuple(data.get("reason_codes", ())),
            configuration_version=str(data.get("configuration_version", "1")),
            metadata=dict(data.get("metadata", {})),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidModelFallbackContractError(
            "invalid routing decision payload"
        ) from exc


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(_json(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ModelAttemptResult:
    operation_id: str
    attempt_index: int
    model_id: str
    provider_id: str
    trigger: ModelFallbackTrigger
    success: bool = False
    estimated_cost: Decimal | None = None
    actual_cost: Decimal | None = None
    latency_ms: int | None = None
    validation: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, str)
            for value in (
                self.operation_id,
                self.model_id,
                self.provider_id,
            )
        ):
            raise InvalidModelFallbackContractError(
                "attempt identifiers must be strings"
            )
        if (
            not self.operation_id.strip()
            or not self.model_id.strip()
            or not self.provider_id.strip()
        ):
            raise InvalidModelFallbackContractError(
                "attempt identifiers must be non-empty"
            )
        if (
            not isinstance(self.attempt_index, int)
            or isinstance(self.attempt_index, bool)
            or self.attempt_index < 1
        ):
            raise InvalidModelFallbackContractError("attempt_index must be >= 1")
        if not isinstance(self.success, bool):
            raise InvalidModelFallbackContractError("success must be a bool")
        for name in ("estimated_cost", "actual_cost"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, Decimal) or value < 0):
                raise InvalidModelFallbackContractError(
                    f"{name} must be a non-negative Decimal"
                )
        if self.latency_ms is not None and (
            not isinstance(self.latency_ms, int)
            or isinstance(self.latency_ms, bool)
            or self.latency_ms < 0
        ):
            raise InvalidModelFallbackContractError(
                "latency_ms must be a non-negative integer"
            )
        object.__setattr__(self, "operation_id", self.operation_id.strip())
        object.__setattr__(self, "model_id", self.model_id.strip().lower())
        object.__setattr__(self, "provider_id", self.provider_id.strip().lower())
        object.__setattr__(
            self, "trigger", _enum(self.trigger, ModelFallbackTrigger, "trigger")
        )
        object.__setattr__(self, "validation", _freeze(self.validation))
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return _json(
            {
                "operation_id": self.operation_id,
                "attempt_index": self.attempt_index,
                "model_id": self.model_id,
                "provider_id": self.provider_id,
                "trigger": self.trigger,
                "success": self.success,
                "estimated_cost": self.estimated_cost,
                "actual_cost": self.actual_cost,
                "latency_ms": self.latency_ms,
                "validation": self.validation,
                "metadata": self.metadata,
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ModelAttemptResult:
        values = dict(data)
        values["trigger"] = _enum(
            values.get("trigger"), ModelFallbackTrigger, "trigger"
        )
        for field_name in ("estimated_cost", "actual_cost"):
            if values.get(field_name) is not None:
                values[field_name] = Decimal(str(values[field_name]))
        return cls(**values)


@dataclass(frozen=True, slots=True)
class ModelAttemptHistory:
    attempts: tuple[ModelAttemptResult, ...] = ()

    def __post_init__(self) -> None:
        attempts = tuple(self.attempts)
        if any(not isinstance(a, ModelAttemptResult) for a in attempts):
            raise InvalidModelFallbackContractError(
                "history must contain attempt results"
            )
        seen: set[tuple[str, int, str, str]] = set()
        expected_index = 1
        operation_id: str | None = None
        for attempt in attempts:
            key = (
                attempt.operation_id,
                attempt.attempt_index,
                attempt.provider_id,
                attempt.model_id,
            )
            if key in seen or attempt.attempt_index != expected_index:
                raise InvalidModelFallbackContractError(
                    "history attempts must be ordered and logically unique"
                )
            if operation_id is None:
                operation_id = attempt.operation_id
            elif operation_id != attempt.operation_id:
                raise InvalidModelFallbackContractError(
                    "history attempts must use one operation_id"
                )
            seen.add(key)
            expected_index += 1
        object.__setattr__(self, "attempts", attempts)

    @property
    def total_attempts(self) -> int:
        return len(self.attempts)

    def count_model(self, model_id: str) -> int:
        return sum(a.model_id == model_id.strip().lower() for a in self.attempts)

    def count_provider(self, provider_id: str) -> int:
        return sum(a.provider_id == provider_id.strip().lower() for a in self.attempts)

    def model_exhausted(self, model_id: str, limit: int) -> bool:
        return self.count_model(model_id) >= limit

    def provider_exhausted(self, provider_id: str, limit: int) -> bool:
        return self.count_provider(provider_id) >= limit

    def attempts_including_latest(
        self, latest: ModelAttemptResult
    ) -> tuple[ModelAttemptResult, ...]:
        """Return the counted attempts with an explicit latest-result rule."""
        if self.attempts:
            if self.attempts[-1] != latest:
                raise InvalidModelFallbackContractError(
                    "latest result is not the final history attempt"
                )
            return self.attempts
        return (latest,)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ModelAttemptHistory:
        return cls(
            tuple(
                ModelAttemptResult.from_dict(item) for item in data.get("attempts", ())
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {"attempts": [a.to_dict() for a in self.attempts]}


@dataclass(frozen=True, slots=True)
class ModelFallbackPolicy:
    id: str = "default-model-fallback"
    version: str = "1"
    maximum_attempts: int = 3
    maximum_attempts_per_model: int = 1
    maximum_attempts_per_provider: int = 2
    retryable_triggers: tuple[ModelFallbackTrigger, ...] = (
        ModelFallbackTrigger.TIMEOUT,
        ModelFallbackTrigger.RATE_LIMIT,
        ModelFallbackTrigger.TRANSIENT_ERROR,
    )
    escalation_triggers: tuple[ModelFallbackTrigger, ...] = (
        ModelFallbackTrigger.PRIVACY_INCOMPATIBLE,
        ModelFallbackTrigger.BUDGET_EXHAUSTED,
        ModelFallbackTrigger.PERMANENT_ERROR,
    )
    actions: tuple[ModelFallbackAction, ...] = (
        ModelFallbackAction.RETRY_SAME_MODEL,
        ModelFallbackAction.NEXT_ROUTING_CANDIDATE,
        ModelFallbackAction.REROUTE,
        ModelFallbackAction.REQUEST_APPROVAL,
        ModelFallbackAction.PAUSE,
    )
    exclude_failed_model: bool = True
    exclude_failed_provider: bool = False
    allow_rerouting: bool = True
    allow_requirement_modification: bool = False
    allow_premium_with_approval: bool = False
    pause_on_escalation: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.id, str)
            or not self.id.strip()
            or not isinstance(self.version, str)
            or not self.version.strip()
        ):
            raise InvalidModelFallbackContractError(
                "policy id and version must be non-empty strings"
            )
        limits = (
            self.maximum_attempts,
            self.maximum_attempts_per_model,
            self.maximum_attempts_per_provider,
        )
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 1
            for value in limits
        ):
            raise InvalidModelFallbackContractError(
                "fallback policy identifiers and limits are invalid"
            )
        object.__setattr__(self, "id", self.id.strip())
        object.__setattr__(
            self,
            "retryable_triggers",
            tuple(
                _enum(v, ModelFallbackTrigger, "retryable_triggers")
                for v in self.retryable_triggers
            ),
        )
        object.__setattr__(
            self,
            "escalation_triggers",
            tuple(
                _enum(v, ModelFallbackTrigger, "escalation_triggers")
                for v in self.escalation_triggers
            ),
        )
        object.__setattr__(
            self,
            "actions",
            tuple(_enum(v, ModelFallbackAction, "actions") for v in self.actions),
        )
        if len(self.retryable_triggers) != len(set(self.retryable_triggers)) or len(
            self.escalation_triggers
        ) != len(set(self.escalation_triggers)):
            raise InvalidModelFallbackContractError("policy triggers must be unique")
        if len(self.actions) != len(set(self.actions)):
            raise InvalidModelFallbackContractError("policy actions must be unique")
        for name in (
            "exclude_failed_model",
            "exclude_failed_provider",
            "allow_rerouting",
            "allow_requirement_modification",
            "allow_premium_with_approval",
            "pause_on_escalation",
        ):
            if not isinstance(getattr(self, name), bool):
                raise InvalidModelFallbackContractError(f"{name} must be a bool")
        object.__setattr__(self, "metadata", _freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return _json(
            {
                "id": self.id,
                "version": self.version,
                "maximum_attempts": self.maximum_attempts,
                "maximum_attempts_per_model": self.maximum_attempts_per_model,
                "maximum_attempts_per_provider": self.maximum_attempts_per_provider,
                "retryable_triggers": self.retryable_triggers,
                "escalation_triggers": self.escalation_triggers,
                "actions": self.actions,
                "exclude_failed_model": self.exclude_failed_model,
                "exclude_failed_provider": self.exclude_failed_provider,
                "allow_rerouting": self.allow_rerouting,
                "allow_requirement_modification": self.allow_requirement_modification,
                "allow_premium_with_approval": self.allow_premium_with_approval,
                "pause_on_escalation": self.pause_on_escalation,
                "metadata": self.metadata,
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ModelFallbackPolicy:
        if not isinstance(data, Mapping):
            raise InvalidModelFallbackContractError("policy payload must be a mapping")
        values = dict(data)
        defaults = cls()

        def tuple_field(name: str, default: tuple[Any, ...]) -> tuple[Any, ...]:
            if name not in values:
                return default
            raw = values.pop(name)
            if not isinstance(raw, (list, tuple)):
                raise InvalidModelFallbackContractError(
                    f"{name} must be a list or tuple"
                )
            return tuple(raw)

        retryable = tuple_field("retryable_triggers", defaults.retryable_triggers)
        escalation = tuple_field("escalation_triggers", defaults.escalation_triggers)
        actions = tuple_field("actions", defaults.actions)
        return cls(
            **values,
            retryable_triggers=retryable,
            escalation_triggers=escalation,
            actions=actions,
        )


@dataclass(frozen=True, slots=True)
class ModelFallbackContext:
    operation_id: str
    workflow_id: str
    routing_decision: RoutingDecision | None
    effective_requirements: ModelRequirements
    latest_result: ModelAttemptResult
    history: ModelAttemptHistory = field(default_factory=ModelAttemptHistory)
    policy: ModelFallbackPolicy = field(default_factory=ModelFallbackPolicy)
    approval: Mapping[str, Any] = field(default_factory=dict)
    budget: Mapping[str, Any] = field(default_factory=dict)
    privacy: Mapping[str, Any] = field(default_factory=dict)
    policy_context: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.operation_id, str)
            or not self.operation_id.strip()
            or not isinstance(self.workflow_id, str)
            or not self.workflow_id.strip()
        ):
            raise InvalidModelFallbackContractError(
                "context operation_id and workflow_id must be non-empty"
            )
        if not isinstance(self.history, ModelAttemptHistory):
            raise InvalidModelFallbackContractError(
                "history must be a ModelAttemptHistory"
            )
        if not isinstance(self.policy, ModelFallbackPolicy):
            raise InvalidModelFallbackContractError(
                "policy must be a ModelFallbackPolicy"
            )
        if self.routing_decision is not None and not isinstance(
            self.routing_decision, RoutingDecision
        ):
            raise InvalidModelFallbackContractError(
                "routing_decision must be a RoutingDecision or None"
            )
        for name in ("approval", "budget", "privacy", "policy_context", "metadata"):
            if not isinstance(getattr(self, name), Mapping):
                raise InvalidModelFallbackContractError(f"{name} must be a Mapping")
        if not isinstance(self.effective_requirements, ModelRequirements):
            raise InvalidModelFallbackContractError(
                "effective_requirements must be ModelRequirements"
            )
        if not isinstance(self.latest_result, ModelAttemptResult):
            raise InvalidModelFallbackContractError(
                "latest_result must be ModelAttemptResult"
            )
        if self.latest_result.operation_id != self.operation_id:
            raise InvalidModelFallbackContractError(
                "latest_result operation_id conflicts with context"
            )
        if self.history.attempts and self.history.attempts[-1] != self.latest_result:
            raise InvalidModelFallbackContractError(
                "latest_result must be the final history attempt"
            )
        for name in ("approval", "budget", "privacy", "policy_context", "metadata"):
            object.__setattr__(self, name, _freeze(getattr(self, name)))

    def to_dict(self) -> dict[str, Any]:
        return _json(
            {
                "operation_id": self.operation_id,
                "workflow_id": self.workflow_id,
                "routing_decision": _routing_to_dict(self.routing_decision)
                if self.routing_decision
                else None,
                "effective_requirements": model_requirements_to_dict(
                    self.effective_requirements
                ),
                "latest_result": self.latest_result,
                "history": self.history,
                "policy": self.policy,
                "approval": self.approval,
                "budget": self.budget,
                "privacy": self.privacy,
                "policy_context": self.policy_context,
                "metadata": self.metadata,
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ModelFallbackContext:
        return cls(
            operation_id=str(data["operation_id"]),
            workflow_id=str(data["workflow_id"]),
            routing_decision=_routing_from_dict(data["routing_decision"])
            if data.get("routing_decision")
            else None,
            effective_requirements=model_requirements_from_dict(
                data["effective_requirements"]
            ),
            latest_result=ModelAttemptResult.from_dict(data["latest_result"]),
            history=ModelAttemptHistory.from_dict(data.get("history", {})),
            policy=(
                ModelFallbackPolicy.from_dict(data["policy"])
                if "policy" in data
                else ModelFallbackPolicy()
            ),
            approval=data.get("approval", {}),
            budget=data.get("budget", {}),
            privacy=data.get("privacy", {}),
            policy_context=data.get("policy_context", {}),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class ModelFallbackDecision:
    operation_id: str
    attempt_index: int
    action: ModelFallbackAction
    trigger: ModelFallbackTrigger
    selected_model_id: str | None = None
    selected_provider_id: str | None = None
    skipped_candidates: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    effective_requirements: ModelRequirements | None = None
    requires_approval: bool = False
    pause: bool = False
    recovery_strategy: str | None = None
    idempotency_key: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "action", _enum(self.action, ModelFallbackAction, "action")
        )
        object.__setattr__(
            self, "trigger", _enum(self.trigger, ModelFallbackTrigger, "trigger")
        )
        object.__setattr__(self, "skipped_candidates", tuple(self.skipped_candidates))
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "metadata", _freeze(self.metadata))
        if (
            not isinstance(self.operation_id, str)
            or not self.operation_id.strip()
            or not isinstance(self.attempt_index, int)
            or isinstance(self.attempt_index, bool)
            or self.attempt_index < 1
        ):
            raise InvalidModelFallbackContractError(
                "decision operation_id and attempt_index are invalid"
            )
        valid_strategies = {
            "retry",
            "retry_with_modified_parameters",
            "reobserve",
            "rerun_validation",
            "replan",
            "request_approval",
            "escalate",
            "pause",
            "fail",
        }
        if (
            self.recovery_strategy is not None
            and self.recovery_strategy not in valid_strategies
        ):
            raise InvalidModelFallbackContractError("invalid recovery_strategy")
        selections = {
            ModelFallbackAction.NEXT_ROUTING_CANDIDATE,
            ModelFallbackAction.SELECT_EQUIVALENT_MODEL,
            ModelFallbackAction.SELECT_LOWER_COST_MODEL,
            ModelFallbackAction.SELECT_HIGHER_QUALITY_MODEL,
        }
        if self.action in selections and (
            not self.selected_model_id or not self.selected_provider_id
        ):
            raise InvalidModelFallbackContractError(
                "selection actions require a selected model and provider"
            )
        if (
            self.action is ModelFallbackAction.REQUEST_APPROVAL
            and not self.requires_approval
        ):
            raise InvalidModelFallbackContractError(
                "REQUEST_APPROVAL requires requires_approval"
            )
        if self.action is ModelFallbackAction.PAUSE and not self.pause:
            raise InvalidModelFallbackContractError("PAUSE requires pause")
        if not self.idempotency_key:
            payload = {
                "operation_id": self.operation_id,
                "attempt_index": self.attempt_index,
                "trigger": self.trigger,
                "action": self.action,
                "selected_model_id": self.selected_model_id,
                "selected_provider_id": self.selected_provider_id,
                "skipped_candidates": self.skipped_candidates,
                "effective_requirements": self.effective_requirements,
                "metadata": self.metadata,
            }
            object.__setattr__(self, "idempotency_key", _canonical_hash(payload))

    def to_dict(self) -> dict[str, Any]:
        return _json(
            {
                "operation_id": self.operation_id,
                "attempt_index": self.attempt_index,
                "action": self.action,
                "trigger": self.trigger,
                "selected_model_id": self.selected_model_id,
                "selected_provider_id": self.selected_provider_id,
                "skipped_candidates": self.skipped_candidates,
                "reason_codes": self.reason_codes,
                "effective_requirements": model_requirements_to_dict(
                    self.effective_requirements
                )
                if self.effective_requirements
                else None,
                "requires_approval": self.requires_approval,
                "pause": self.pause,
                "recovery_strategy": self.recovery_strategy,
                "idempotency_key": self.idempotency_key,
                "metadata": self.metadata,
            }
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ModelFallbackDecision:
        values = dict(data)
        requirements = values.get("effective_requirements")
        values["effective_requirements"] = (
            model_requirements_from_dict(requirements) if requirements else None
        )
        return cls(**values)
