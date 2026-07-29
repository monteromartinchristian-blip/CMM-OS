"""Immutable, privacy-safe contracts for Phase 9.32 model executions."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, DecimalException
from enum import Enum
from types import MappingProxyType
from typing import Any

from .model_execution_errors import InvalidModelExecutionRecordError


class _ValueEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class AcceptanceStatus(_ValueEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    ACCEPTED_WITH_WARNING = "accepted_with_warning"
    REJECTED = "rejected"
    REPAIRED = "repaired"
    REGENERATED = "regenerated"
    ESCALATED = "escalated"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ModelExecutionStatus(_ValueEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ContentRetentionMode(_ValueEnum):
    NONE = "none"
    HASHES_ONLY = "hashes_only"
    TRACE_REFERENCE = "trace_reference"
    AUTHORIZED_PAYLOAD_REFERENCE = "authorized_payload_reference"


class PrivacyClassification(_ValueEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


_SENSITIVE = re.compile(
    r"(?i)(^|[_\-.])(prompt|response|secret|credential|api[_\-]?key|token|"
    r"password|authorization|payload)([_\-.]|$)"
)
_HASH = re.compile(r"^[0-9a-f]{64}$")


def _id(value: Any, name: str, optional: bool = False) -> str | None:
    if isinstance(value, Enum):
        value = value.value
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip():
        raise InvalidModelExecutionRecordError(f"{name} must be a non-empty string")
    return value.strip()


def _optional_id(value: Any, name: str) -> str | None:
    return _id(value, name, optional=True)


def _decimal(value: Any, name: str) -> Decimal:
    if isinstance(value, (bool, float)):
        raise InvalidModelExecutionRecordError(f"{name} must use Decimal")
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (DecimalException, TypeError, ValueError) as exc:
        raise InvalidModelExecutionRecordError(f"{name} must be a Decimal") from exc
    if not result.is_finite() or result < 0:
        raise InvalidModelExecutionRecordError(f"{name} must be finite and non-negative")
    return result


def _integer(value: Any, name: str, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InvalidModelExecutionRecordError(f"{name} must be a non-negative integer")
    return value


def _utc(value: Any, name: str, *, optional: bool = False) -> datetime | None:
    if value is None and optional:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError as exc:
            raise InvalidModelExecutionRecordError(f"invalid {name}") from exc
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise InvalidModelExecutionRecordError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _enum(value: Any, enum_type: type[Enum], name: str) -> Any:
    try:
        return value if isinstance(value, enum_type) else enum_type(value)
    except (TypeError, ValueError) as exc:
        raise InvalidModelExecutionRecordError(f"invalid {name}: {value!r}") from exc


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
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
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _mapping(value: Mapping[str, Any] | None, name: str) -> MappingProxyType:
    if value is None:
        value = {}
    if not isinstance(value, Mapping):
        raise InvalidModelExecutionRecordError(f"{name} must be a mapping")
    def check(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, nested in item.items():
                if not isinstance(key, str) or _SENSITIVE.search(key):
                    raise InvalidModelExecutionRecordError(f"{name} contains sensitive key")
                check(nested)
        elif isinstance(item, (list, tuple, set, frozenset)):
            for nested in item:
                check(nested)

    check(value)
    frozen = _freeze(value)
    try:
        json.dumps(_json(frozen), sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise InvalidModelExecutionRecordError(f"{name} must be JSON serializable") from exc
    return frozen


def _hash(value: str | None, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise InvalidModelExecutionRecordError(f"{name} must be a SHA-256 hex digest")
    return value.lower()


@dataclass(frozen=True, slots=True)
class ModelExecutionContentReference:
    reference_id: str
    kind: str = "trace"
    policy_version: str = "1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "reference_id", _id(self.reference_id, "reference_id"))
        object.__setattr__(self, "kind", _id(self.kind, "kind"))
        object.__setattr__(self, "policy_version", _id(self.policy_version, "policy_version"))

    def to_dict(self) -> dict[str, str]:
        return {"reference_id": self.reference_id, "kind": self.kind, "policy_version": self.policy_version}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ModelExecutionContentReference:
        return cls(**dict(data))


@dataclass(frozen=True, slots=True)
class QualityEvaluation:
    score: Decimal | None = None
    evaluator: str | None = None
    criteria_version: str | None = None
    result_reference: str | None = None
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.score is not None:
            score = _decimal(self.score, "score")
            if score > 1:
                raise InvalidModelExecutionRecordError("score must be between 0 and 1")
            object.__setattr__(self, "score", score)
        for name in ("evaluator", "criteria_version", "result_reference"):
            object.__setattr__(self, name, _optional_id(getattr(self, name), name))
        object.__setattr__(self, "reason_codes", tuple(_id(v, "reason_code") for v in self.reason_codes))

    def to_dict(self) -> dict[str, Any]:
        return {"score": str(self.score) if self.score is not None else None, "evaluator": self.evaluator,
                "criteria_version": self.criteria_version, "result_reference": self.result_reference,
                "reason_codes": list(self.reason_codes)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> QualityEvaluation:
        values = dict(data)
        if values.get("score") is not None:
            values["score"] = Decimal(str(values["score"]))
        return cls(**values)


_TRANSITIONS = {
    AcceptanceStatus.PENDING: frozenset(AcceptanceStatus),
    AcceptanceStatus.ACCEPTED: frozenset({AcceptanceStatus.ACCEPTED_WITH_WARNING, AcceptanceStatus.REPAIRED,
                                          AcceptanceStatus.REGENERATED, AcceptanceStatus.ESCALATED}),
    AcceptanceStatus.ACCEPTED_WITH_WARNING: frozenset({AcceptanceStatus.ACCEPTED, AcceptanceStatus.REPAIRED,
                                                       AcceptanceStatus.REGENERATED, AcceptanceStatus.ESCALATED}),
    AcceptanceStatus.REJECTED: frozenset({AcceptanceStatus.REPAIRED, AcceptanceStatus.REGENERATED,
                                          AcceptanceStatus.ESCALATED}),
    AcceptanceStatus.REPAIRED: frozenset({AcceptanceStatus.ACCEPTED, AcceptanceStatus.ACCEPTED_WITH_WARNING,
                                          AcceptanceStatus.REJECTED, AcceptanceStatus.ESCALATED}),
    AcceptanceStatus.REGENERATED: frozenset({AcceptanceStatus.ACCEPTED, AcceptanceStatus.ACCEPTED_WITH_WARNING,
                                             AcceptanceStatus.REJECTED, AcceptanceStatus.ESCALATED}),
    AcceptanceStatus.ESCALATED: frozenset({AcceptanceStatus.ACCEPTED, AcceptanceStatus.ACCEPTED_WITH_WARNING,
                                           AcceptanceStatus.REJECTED, AcceptanceStatus.CANCELLED}),
    AcceptanceStatus.CANCELLED: frozenset(),
    AcceptanceStatus.FAILED: frozenset(),
}


def is_valid_acceptance_transition(current: AcceptanceStatus, target: AcceptanceStatus) -> bool:
    return target in _TRANSITIONS[current]


# Descriptive aliases retained for callers that prefer the Phase 9.32 names.
ModelExecutionAcceptanceStatus = AcceptanceStatus
ModelExecutionContentRetention = ContentRetentionMode
ModelExecutionPrivacyClassification = PrivacyClassification


@dataclass(frozen=True, slots=True)
class ModelExecutionRecord:
    id: str
    agent_run_id: str
    provider_id: str
    model_id: str
    capability: str
    goal_id: str | None = None
    workflow_id: str | None = None
    task_id: str | None = None
    operation_id: str | None = None
    domain: str | None = None
    model_version: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    estimated_cost: Decimal = Decimal(0)
    actual_cost: Decimal | None = None
    currency: str = "USD"
    latency_ms: int = 0
    cache_used: bool = False
    validation_result_ids: tuple[str, ...] = ()
    retry_number: int = 0
    fallback_from: str | None = None
    fallback_trigger: str | None = None
    fallback_action: str | None = None
    quality_evaluation: QualityEvaluation | None = None
    human_intervention: bool = False
    execution_status: ModelExecutionStatus | str = ModelExecutionStatus.PENDING
    acceptance_status: AcceptanceStatus | str = AcceptanceStatus.PENDING
    configuration_version: str | None = None
    policy_version: str | None = None
    routing_decision_id: str | None = None
    routing_provider_id: str | None = None
    routing_model_id: str | None = None
    routing_reason_codes: tuple[str, ...] = ()
    rejected_candidates_count: int = 0
    trace_id: str | None = None
    correlation_id: str | None = None
    causation_id: str | None = None
    prompt_hash: str | None = None
    response_hash: str | None = None
    content_retention: ContentRetentionMode | str = ContentRetentionMode.HASHES_ONLY
    privacy_classification: PrivacyClassification | str = PrivacyClassification.INTERNAL
    content_reference: ModelExecutionContentReference | None = None
    exclusion_reasons: tuple[str, ...] = ()
    privacy_policy_version: str = "1"
    reservation_id: str | None = None
    budget_id: str | None = None
    economic_decision: str | None = None
    economic_reason_codes: tuple[str, ...] = ()
    attempt_history_reference: str | None = None
    validation_status: str | None = None
    validation_blocking_count: int = 0
    validation_warning_count: int = 0
    reason_codes: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("id", "agent_run_id", "provider_id", "model_id", "capability"):
            value = _id(getattr(self, name), name)
            object.__setattr__(self, name, value.lower() if name in {"provider_id", "model_id"} else value)
        for name in ("goal_id", "workflow_id", "task_id", "operation_id", "domain", "model_version", "fallback_from",
                     "fallback_trigger", "fallback_action", "configuration_version", "policy_version", "routing_decision_id",
                     "trace_id", "correlation_id", "causation_id", "reservation_id", "budget_id", "economic_decision",
                     "routing_provider_id", "routing_model_id", "attempt_history_reference", "validation_status"):
            object.__setattr__(self, name, _optional_id(getattr(self, name), name))
        for name in ("input_tokens", "output_tokens", "cached_tokens", "latency_ms", "retry_number",
                     "rejected_candidates_count", "validation_blocking_count", "validation_warning_count"):
            object.__setattr__(self, name, _integer(getattr(self, name), name))
        object.__setattr__(self, "estimated_cost", _decimal(self.estimated_cost, "estimated_cost"))
        object.__setattr__(self, "actual_cost", None if self.actual_cost is None else _decimal(self.actual_cost, "actual_cost"))
        currency = _id(self.currency, "currency").upper()
        if len(currency) != 3:
            raise InvalidModelExecutionRecordError("currency must be a 3-letter code")
        object.__setattr__(self, "currency", currency)
        for name in ("cache_used", "human_intervention"):
            if not isinstance(getattr(self, name), bool):
                raise InvalidModelExecutionRecordError(f"{name} must be a bool")
        object.__setattr__(self, "validation_result_ids", tuple(_id(v, "validation_result_id") for v in self.validation_result_ids))
        object.__setattr__(self, "reason_codes", tuple(_id(v, "reason_code") for v in self.reason_codes))
        object.__setattr__(self, "routing_reason_codes", tuple(_id(v, "routing_reason_code") for v in self.routing_reason_codes))
        object.__setattr__(self, "economic_reason_codes", tuple(_id(v, "economic_reason_code") for v in self.economic_reason_codes))
        object.__setattr__(self, "exclusion_reasons", tuple(_id(v, "exclusion_reason") for v in self.exclusion_reasons))
        object.__setattr__(self, "execution_status", _enum(self.execution_status, ModelExecutionStatus, "execution_status"))
        object.__setattr__(self, "acceptance_status", _enum(self.acceptance_status, AcceptanceStatus, "acceptance_status"))
        object.__setattr__(self, "content_retention", _enum(self.content_retention, ContentRetentionMode, "content_retention"))
        object.__setattr__(self, "privacy_classification", _enum(self.privacy_classification, PrivacyClassification, "privacy_classification"))
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))
        object.__setattr__(self, "completed_at", _utc(self.completed_at, "completed_at", optional=True))
        if self.quality_evaluation is not None and not isinstance(self.quality_evaluation, QualityEvaluation):
            raise InvalidModelExecutionRecordError("quality_evaluation must be QualityEvaluation")
        if self.content_reference is not None and not isinstance(self.content_reference, ModelExecutionContentReference):
            raise InvalidModelExecutionRecordError("content_reference must be ModelExecutionContentReference")
        object.__setattr__(self, "prompt_hash", _hash(self.prompt_hash, "prompt_hash"))
        object.__setattr__(self, "response_hash", _hash(self.response_hash, "response_hash"))
        if self.content_retention is ContentRetentionMode.HASHES_ONLY and self.content_reference is not None:
            raise InvalidModelExecutionRecordError("hashes_only cannot contain a content reference")
        if self.content_retention is ContentRetentionMode.AUTHORIZED_PAYLOAD_REFERENCE:
            if self.content_reference is None or self.content_reference.kind != "payload":
                raise InvalidModelExecutionRecordError(
                    "authorized_payload_reference requires a payload reference"
                )
            if self.prompt_hash is not None or self.response_hash is not None:
                raise InvalidModelExecutionRecordError(
                    "authorized payload references cannot include payload hashes"
                )
        if self.content_retention is ContentRetentionMode.NONE and (
            self.prompt_hash is not None
            or self.response_hash is not None
            or self.content_reference is not None
        ) and not self.exclusion_reasons:
            raise InvalidModelExecutionRecordError(
                "content retention none requires exclusion reasons"
            )
        object.__setattr__(self, "metadata", _mapping(self.metadata, "metadata"))

    def to_dict(self) -> dict[str, Any]:
        result = {name: _json(getattr(self, name)) for name in self.__dataclass_fields__}
        for name in ("created_at", "completed_at"):
            result[name] = getattr(self, name).isoformat() if getattr(self, name) else None
        result["quality_evaluation"] = self.quality_evaluation.to_dict() if self.quality_evaluation else None
        result["content_reference"] = self.content_reference.to_dict() if self.content_reference else None
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ModelExecutionRecord:
        values = dict(data)
        for name in ("estimated_cost", "actual_cost"):
            if values.get(name) is not None:
                values[name] = Decimal(str(values[name]))
        if values.get("quality_evaluation"):
            values["quality_evaluation"] = QualityEvaluation.from_dict(values["quality_evaluation"])
        if values.get("content_reference"):
            values["content_reference"] = ModelExecutionContentReference.from_dict(values["content_reference"])
        return cls(**values)

    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True, default=str).encode()).hexdigest()

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, data: str) -> ModelExecutionRecord:
        return cls.from_dict(json.loads(data))
