"""Provider-independent common reasoning-rule contracts (Phase 10.12)."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from functools import total_ordering
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from cmm.cognitive.enums import (
    ReasoningRiskLevel,
    ReasoningRuleCategory,
    ReasoningRuleResultStatus,
    ReasoningRuleScope,
    ReasoningRuleStatus,
    ReasoningSeverity,
)
from cmm.cognitive.errors import (
    ReasoningRuleContractError,
    ReasoningRuleSerializationError,
)
from cmm.cognitive.knowledge import Contradiction, KnowledgeItem

REASONING_RULE_CONTRACT_VERSION = "1.0.0"
MIN_RULE_PRIORITY = -10_000
MAX_RULE_PRIORITY = 10_000
MIN_CONFIDENCE_DELTA = -1.0
MAX_CONFIDENCE_DELTA = 1.0

_RULE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_DOMAIN_ID_RE = re.compile(r"^domain:[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_CODE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def _contract(message: str, field_name: str) -> ReasoningRuleContractError:
    return ReasoningRuleContractError(message, field=field_name)


def _non_empty(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _contract(f"{field_name} must be a non-empty string", field_name)
    return value.strip()


def _rule_id(value: Any, field_name: str = "id") -> str:
    value = _non_empty(value, field_name)
    if not _RULE_ID_RE.fullmatch(value):
        raise _contract(f"{field_name} must be a canonical dotted rule id", field_name)
    return value


def _domain_id(value: Any, field_name: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    value = _non_empty(value, field_name)
    if not _DOMAIN_ID_RE.fullmatch(value):
        raise _contract(f"{field_name} must be a canonical domain id", field_name)
    return value


def _semver(value: Any, field_name: str = "version") -> str:
    value = _non_empty(value, field_name)
    if not _SEMVER_RE.fullmatch(value):
        raise _contract(f"{field_name} must be a valid semantic version", field_name)
    return value


@total_ordering
class _SemanticVersion:
    __slots__ = ("major", "minor", "patch", "pre")

    def __init__(self, value: str) -> None:
        match = _SEMVER_RE.fullmatch(value)
        if match is None:
            raise _contract("version must be a valid semantic version", "version")
        self.major, self.minor, self.patch = (int(match.group(i)) for i in range(1, 4))
        self.pre = tuple(
            int(part) if part.isdigit() else part for part in (match.group(4) or "").split(".") if part
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _SemanticVersion):
            return NotImplemented
        return (self.major, self.minor, self.patch, self.pre) == (
            other.major, other.minor, other.patch, other.pre
        )

    def __lt__(self, other: _SemanticVersion) -> bool:
        core = (self.major, self.minor, self.patch)
        other_core = (other.major, other.minor, other.patch)
        if core != other_core:
            return core < other_core
        if not self.pre:
            return False
        if not other.pre:
            return True
        for left, right in zip(self.pre, other.pre):
            if left == right:
                continue
            if isinstance(left, int) and not isinstance(right, int):
                return True
            if not isinstance(left, int) and isinstance(right, int):
                return False
            return left < right  # type: ignore[operator]
        return len(self.pre) < len(other.pre)


def _semver_key(value: str) -> _SemanticVersion:
    return _SemanticVersion(value)


def _enum(value: Any, enum_type: type, field_name: str) -> Any:
    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str):
        raise _contract(f"{field_name} must be a {enum_type.__name__}", field_name)
    try:
        return enum_type(value)
    except ValueError as exc:
        raise _contract(f"unknown {enum_type.__name__}: {value!r}", field_name) from exc


def _aware(value: Any, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise _contract(f"{field_name} must be a datetime", field_name)
    if value.tzinfo is None or value.utcoffset() is None:
        raise _contract(f"{field_name} must be timezone-aware", field_name)
    return value


def _json_freeze(value: Any, field_name: str = "metadata") -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise _contract(f"{field_name} contains a non-finite float", field_name)
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, nested in value.items():
            if not isinstance(key, str):
                raise _contract(f"{field_name} keys must be strings", field_name)
            frozen[key] = _json_freeze(nested, f"{field_name}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_json_freeze(item, f"{field_name}[]") for item in value)
    raise _contract(f"{field_name} must contain only JSON-safe values", field_name)


def _json_thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _json_thaw(nested) for key, nested in value.items()}
    if isinstance(value, tuple):
        return [_json_thaw(item) for item in value]
    return value


def _str_tuple(value: Any, field_name: str, *, unique: bool = True) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise _contract(f"{field_name} must be a sequence, not a string", field_name)
    result = tuple(_non_empty(item, f"{field_name}[]") for item in value)
    if unique and len(set(result)) != len(result):
        raise _contract(f"{field_name} must not contain duplicates", field_name)
    return result


def _domain_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    result = _str_tuple(value, field_name)
    return tuple(_domain_id(item, field_name) for item in result)  # type: ignore[misc]


def _reject_unknown(data: Mapping[str, Any], known: set[str], name: str) -> None:
    unknown = set(data) - known
    if unknown:
        raise ReasoningRuleSerializationError(
            f"{name}.from_dict got unknown fields: {sorted(unknown)}",
            field="data",
            details={"unknown_fields": sorted(unknown)},
        )


def _require(data: Mapping[str, Any], required: set[str], name: str) -> None:
    missing = required - set(data)
    if missing:
        raise ReasoningRuleSerializationError(
            f"{name}.from_dict missing required fields: {sorted(missing)}", field="data"
        )


def _parse_datetime(value: Any, field_name: str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ReasoningRuleSerializationError(
                f"{field_name} must be an ISO datetime", field=field_name
            ) from exc
    else:
        raise ReasoningRuleSerializationError(
            f"{field_name} must be an ISO datetime", field=field_name
        )
    try:
        return _aware(parsed, field_name)
    except ReasoningRuleContractError as exc:
        raise ReasoningRuleSerializationError(exc.message, field=exc.field) from exc


def _construct(cls: type, values: dict[str, Any]) -> Any:
    try:
        return cls(**values)
    except ReasoningRuleContractError as exc:
        raise ReasoningRuleSerializationError(
            exc.message, field=exc.field, details=dict(exc.details)
        ) from exc


@dataclass(frozen=True, slots=True)
class ReasoningRuleDefinition:
    id: str
    name: str
    version: str
    scope: ReasoningRuleScope
    category: ReasoningRuleCategory
    status: ReasoningRuleStatus
    priority: int
    risk_level: ReasoningRiskLevel
    required_permissions: tuple[str, ...] = ()
    deterministic: bool = True
    domain_id: str | None = None
    description: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = REASONING_RULE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _rule_id(self.id))
        object.__setattr__(self, "name", _non_empty(self.name, "name"))
        object.__setattr__(self, "version", _semver(self.version))
        object.__setattr__(self, "scope", _enum(self.scope, ReasoningRuleScope, "scope"))
        object.__setattr__(self, "category", _enum(self.category, ReasoningRuleCategory, "category"))
        object.__setattr__(self, "status", _enum(self.status, ReasoningRuleStatus, "status"))
        object.__setattr__(self, "risk_level", _enum(self.risk_level, ReasoningRiskLevel, "risk_level"))
        if isinstance(self.priority, bool) or not isinstance(self.priority, int):
            raise _contract("priority must be an integer and not bool", "priority")
        if not MIN_RULE_PRIORITY <= self.priority <= MAX_RULE_PRIORITY:
            raise _contract(
                f"priority must be between {MIN_RULE_PRIORITY} and {MAX_RULE_PRIORITY}", "priority"
            )
        object.__setattr__(self, "required_permissions", _str_tuple(self.required_permissions, "required_permissions"))
        if not isinstance(self.deterministic, bool):
            raise _contract("deterministic must be a strict boolean", "deterministic")
        domain_id = _domain_id(self.domain_id, "domain_id", optional=True)
        if self.scope is ReasoningRuleScope.GLOBAL and domain_id is not None:
            raise _contract("global scope must not declare domain_id", "domain_id")
        if self.scope is ReasoningRuleScope.DOMAIN and domain_id is None:
            raise _contract("domain scope requires domain_id", "domain_id")
        object.__setattr__(self, "domain_id", domain_id)
        if self.description is not None:
            object.__setattr__(self, "description", _non_empty(self.description, "description"))
        object.__setattr__(self, "metadata", _json_freeze(self.metadata))
        object.__setattr__(self, "contract_version", _semver(self.contract_version, "contract_version"))

    def __hash__(self) -> int:
        return hash(json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "version": self.version,
            "scope": self.scope.value, "category": self.category.value,
            "status": self.status.value, "priority": self.priority,
            "required_permissions": list(self.required_permissions),
            "risk_level": self.risk_level.value, "deterministic": self.deterministic,
            "domain_id": self.domain_id, "description": self.description,
            "metadata": _json_thaw(self.metadata), "contract_version": self.contract_version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReasoningRuleDefinition:
        if not isinstance(data, Mapping):
            raise ReasoningRuleSerializationError("ReasoningRuleDefinition.from_dict requires a mapping", field="data")
        known = set(cls.__dataclass_fields__)
        _reject_unknown(data, known, cls.__name__)
        _require(data, {"id", "name", "version", "scope", "category", "status", "priority", "risk_level"}, cls.__name__)
        return _construct(cls, dict(data))


@dataclass(frozen=True, slots=True)
class _ReasoningMessage:
    code: str
    message: str
    severity: ReasoningSeverity
    rule_id: str
    domain_id: str | None = None
    references: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        code = _non_empty(self.code, "code")
        if not _CODE_RE.fullmatch(code):
            raise _contract("code must use stable uppercase underscore format", "code")
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "message", _non_empty(self.message, "message"))
        object.__setattr__(self, "severity", _enum(self.severity, ReasoningSeverity, "severity"))
        object.__setattr__(self, "rule_id", _rule_id(self.rule_id, "rule_id"))
        object.__setattr__(self, "domain_id", _domain_id(self.domain_id, "domain_id", optional=True))
        object.__setattr__(self, "references", _str_tuple(self.references, "references"))
        object.__setattr__(self, "metadata", _json_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code, "message": self.message, "severity": self.severity.value,
            "rule_id": self.rule_id, "domain_id": self.domain_id,
            "references": list(self.references), "metadata": _json_thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> _ReasoningMessage:
        if not isinstance(data, Mapping):
            raise ReasoningRuleSerializationError(f"{cls.__name__}.from_dict requires a mapping", field="data")
        _reject_unknown(data, set(_ReasoningMessage.__dataclass_fields__), cls.__name__)
        _require(data, {"code", "message", "severity", "rule_id"}, cls.__name__)
        return _construct(cls, dict(data))


@dataclass(frozen=True, slots=True)
class ReasoningFinding(_ReasoningMessage):
    """Safe structured finding emitted by a reasoning rule."""


@dataclass(frozen=True, slots=True)
class ReasoningRecommendation(_ReasoningMessage):
    """Safe structured recommendation emitted by a reasoning rule."""


@dataclass(frozen=True, slots=True)
class ReasoningEscalation(_ReasoningMessage):
    """Non-authorizing escalation recommendation emitted by a rule."""


@dataclass(frozen=True, slots=True)
class ReasoningGap(_ReasoningMessage):
    """Structured information or evidence gap emitted by a rule."""


@dataclass(frozen=True, slots=True)
class ReasoningRuleTraceEntry:
    code: str
    message: str
    rule_id: str
    occurred_at: datetime
    domain_id: str | None = None
    status: ReasoningRuleResultStatus | None = None
    references: tuple[str, ...] = ()
    output_count: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        code = _non_empty(self.code, "code")
        if not _CODE_RE.fullmatch(code):
            raise _contract("code must use stable uppercase underscore format", "code")
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "message", _non_empty(self.message, "message"))
        object.__setattr__(self, "rule_id", _rule_id(self.rule_id, "rule_id"))
        object.__setattr__(self, "domain_id", _domain_id(self.domain_id, "domain_id", optional=True))
        object.__setattr__(self, "occurred_at", _aware(self.occurred_at, "occurred_at"))
        if self.status is not None:
            object.__setattr__(self, "status", _enum(self.status, ReasoningRuleResultStatus, "status"))
        object.__setattr__(self, "references", _str_tuple(self.references, "references"))
        if isinstance(self.output_count, bool) or not isinstance(self.output_count, int) or self.output_count < 0:
            raise _contract("output_count must be a non-negative integer", "output_count")
        object.__setattr__(self, "metadata", _json_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code, "message": self.message, "rule_id": self.rule_id,
            "domain_id": self.domain_id, "occurred_at": self.occurred_at.isoformat(),
            "status": self.status.value if self.status else None,
            "references": list(self.references), "output_count": self.output_count,
            "metadata": _json_thaw(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReasoningRuleTraceEntry:
        if not isinstance(data, Mapping):
            raise ReasoningRuleSerializationError("ReasoningRuleTraceEntry.from_dict requires a mapping", field="data")
        _reject_unknown(data, set(cls.__dataclass_fields__), cls.__name__)
        _require(data, {"code", "message", "rule_id", "occurred_at"}, cls.__name__)
        values = dict(data)
        values["occurred_at"] = _parse_datetime(values["occurred_at"], "occurred_at")
        return _construct(cls, values)


def _nested_tuple(value: Any, cls: type, field_name: str) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise _contract(f"{field_name} must be a sequence", field_name)
    result = []
    for index, item in enumerate(value):
        if isinstance(item, cls):
            result.append(item)
        elif isinstance(item, Mapping):
            try:
                result.append(cls.from_dict(item))
            except ReasoningRuleSerializationError as exc:
                raise _contract(exc.message, f"{field_name}[{index}].{exc.field or 'data'}") from exc
        else:
            raise _contract(f"{field_name}[{index}] must be a {cls.__name__}", f"{field_name}[{index}]")
    return tuple(result)


@dataclass(frozen=True, slots=True)
class ReasoningRuleContext:
    reasoning_id: str
    timestamp: datetime
    session_id: str | None = None
    knowledge_items: tuple[KnowledgeItem, ...] = ()
    contradictions: tuple[Contradiction, ...] = ()
    gaps: tuple[ReasoningGap, ...] = ()
    active_domains: tuple[str, ...] = ()
    primary_domain: str | None = None
    supporting_domains: tuple[str, ...] = ()
    effective_permissions: tuple[str, ...] = ()
    effective_risk: ReasoningRiskLevel = ReasoningRiskLevel.LOW
    effective_sensitivity: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = REASONING_RULE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasoning_id", _non_empty(self.reasoning_id, "reasoning_id"))
        if self.session_id is not None:
            object.__setattr__(self, "session_id", _non_empty(self.session_id, "session_id"))
        if isinstance(self.knowledge_items, (str, bytes)) or not isinstance(self.knowledge_items, Sequence):
            raise _contract("knowledge_items must be a sequence", "knowledge_items")
        if not all(isinstance(item, KnowledgeItem) for item in self.knowledge_items):
            raise _contract("knowledge_items must contain KnowledgeItem values", "knowledge_items")
        object.__setattr__(self, "knowledge_items", tuple(self.knowledge_items))
        if isinstance(self.contradictions, (str, bytes)) or not isinstance(self.contradictions, Sequence):
            raise _contract("contradictions must be a sequence", "contradictions")
        if not all(isinstance(item, Contradiction) for item in self.contradictions):
            raise _contract("contradictions must contain Contradiction values", "contradictions")
        object.__setattr__(self, "contradictions", tuple(self.contradictions))
        object.__setattr__(self, "gaps", _nested_tuple(self.gaps, ReasoningGap, "gaps"))
        active = _domain_tuple(self.active_domains, "active_domains")
        primary = _domain_id(self.primary_domain, "primary_domain", optional=True)
        supporting = _domain_tuple(self.supporting_domains, "supporting_domains")
        if primary is not None and primary not in active:
            raise _contract("primary_domain must be present in active_domains", "primary_domain")
        if any(domain not in active for domain in supporting):
            raise _contract("supporting_domains must be present in active_domains", "supporting_domains")
        if primary is not None and primary in supporting:
            raise _contract("primary_domain must not be supporting", "supporting_domains")
        object.__setattr__(self, "active_domains", active)
        object.__setattr__(self, "primary_domain", primary)
        object.__setattr__(self, "supporting_domains", supporting)
        object.__setattr__(self, "effective_permissions", _str_tuple(self.effective_permissions, "effective_permissions"))
        object.__setattr__(self, "effective_risk", _enum(self.effective_risk, ReasoningRiskLevel, "effective_risk"))
        if self.effective_sensitivity is not None:
            object.__setattr__(self, "effective_sensitivity", _non_empty(self.effective_sensitivity, "effective_sensitivity"))
        object.__setattr__(self, "timestamp", _aware(self.timestamp, "timestamp"))
        object.__setattr__(self, "metadata", _json_freeze(self.metadata))
        object.__setattr__(self, "contract_version", _semver(self.contract_version, "contract_version"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "reasoning_id": self.reasoning_id, "session_id": self.session_id,
            "knowledge_items": [item.to_dict() for item in self.knowledge_items],
            "contradictions": [item.to_dict() for item in self.contradictions],
            "gaps": [item.to_dict() for item in self.gaps],
            "active_domains": list(self.active_domains), "primary_domain": self.primary_domain,
            "supporting_domains": list(self.supporting_domains),
            "effective_permissions": list(self.effective_permissions),
            "effective_risk": self.effective_risk.value,
            "effective_sensitivity": self.effective_sensitivity,
            "timestamp": self.timestamp.isoformat(), "metadata": _json_thaw(self.metadata),
            "contract_version": self.contract_version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReasoningRuleContext:
        if not isinstance(data, Mapping):
            raise ReasoningRuleSerializationError("ReasoningRuleContext.from_dict requires a mapping", field="data")
        _reject_unknown(data, set(cls.__dataclass_fields__), cls.__name__)
        _require(data, {"reasoning_id", "timestamp"}, cls.__name__)
        values = dict(data)
        values["timestamp"] = _parse_datetime(values["timestamp"], "timestamp")
        try:
            values["knowledge_items"] = tuple(
                item if isinstance(item, KnowledgeItem) else KnowledgeItem.from_dict(dict(item))
                for item in values.get("knowledge_items", ())
            )
            values["contradictions"] = tuple(
                item if isinstance(item, Contradiction) else Contradiction.from_dict(dict(item))
                for item in values.get("contradictions", ())
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ReasoningRuleSerializationError("invalid Phase 8 cognitive item", field="knowledge_items") from exc
        return _construct(cls, values)


@dataclass(frozen=True, slots=True)
class ReasoningRuleResult:
    rule_id: str
    rule_name: str
    rule_version: str
    status: ReasoningRuleResultStatus
    started_at: datetime
    completed_at: datetime
    domain_id: str | None = None
    findings: tuple[ReasoningFinding, ...] = ()
    produced_knowledge: tuple[KnowledgeItem, ...] = ()
    contradictions: tuple[Contradiction, ...] = ()
    gaps: tuple[ReasoningGap, ...] = ()
    recommendations: tuple[ReasoningRecommendation, ...] = ()
    escalation: ReasoningEscalation | None = None
    confidence_delta: float = 0.0
    trace_entries: tuple[ReasoningRuleTraceEntry, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = REASONING_RULE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", _rule_id(self.rule_id, "rule_id"))
        object.__setattr__(self, "rule_name", _non_empty(self.rule_name, "rule_name"))
        object.__setattr__(self, "rule_version", _semver(self.rule_version, "rule_version"))
        object.__setattr__(self, "status", _enum(self.status, ReasoningRuleResultStatus, "status"))
        object.__setattr__(self, "domain_id", _domain_id(self.domain_id, "domain_id", optional=True))
        object.__setattr__(self, "findings", _nested_tuple(self.findings, ReasoningFinding, "findings"))
        object.__setattr__(self, "gaps", _nested_tuple(self.gaps, ReasoningGap, "gaps"))
        object.__setattr__(self, "recommendations", _nested_tuple(self.recommendations, ReasoningRecommendation, "recommendations"))
        object.__setattr__(self, "trace_entries", _nested_tuple(self.trace_entries, ReasoningRuleTraceEntry, "trace_entries"))
        if isinstance(self.produced_knowledge, (str, bytes)) or not isinstance(self.produced_knowledge, Sequence) or not all(isinstance(x, KnowledgeItem) for x in self.produced_knowledge):
            raise _contract("produced_knowledge must contain KnowledgeItem values", "produced_knowledge")
        object.__setattr__(self, "produced_knowledge", tuple(self.produced_knowledge))
        if isinstance(self.contradictions, (str, bytes)) or not isinstance(self.contradictions, Sequence) or not all(isinstance(x, Contradiction) for x in self.contradictions):
            raise _contract("contradictions must contain Contradiction values", "contradictions")
        object.__setattr__(self, "contradictions", tuple(self.contradictions))
        if self.escalation is not None and not isinstance(self.escalation, ReasoningEscalation):
            if isinstance(self.escalation, Mapping):
                object.__setattr__(self, "escalation", ReasoningEscalation.from_dict(self.escalation))
            else:
                raise _contract("escalation must be a ReasoningEscalation", "escalation")
        if isinstance(self.confidence_delta, bool) or not isinstance(self.confidence_delta, (int, float)) or not math.isfinite(float(self.confidence_delta)):
            raise _contract("confidence_delta must be finite", "confidence_delta")
        delta = float(self.confidence_delta)
        if not MIN_CONFIDENCE_DELTA <= delta <= MAX_CONFIDENCE_DELTA:
            raise _contract("confidence_delta must be between -1.0 and 1.0", "confidence_delta")
        object.__setattr__(self, "confidence_delta", delta)
        object.__setattr__(self, "started_at", _aware(self.started_at, "started_at"))
        object.__setattr__(self, "completed_at", _aware(self.completed_at, "completed_at"))
        if self.completed_at < self.started_at:
            raise _contract("completed_at must not be before started_at", "completed_at")
        object.__setattr__(self, "metadata", _json_freeze(self.metadata))
        object.__setattr__(self, "contract_version", _semver(self.contract_version, "contract_version"))

    @property
    def duration_seconds(self) -> float:
        return (self.completed_at - self.started_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id, "rule_name": self.rule_name, "rule_version": self.rule_version,
            "domain_id": self.domain_id, "status": self.status.value,
            "findings": [x.to_dict() for x in self.findings],
            "produced_knowledge": [x.to_dict() for x in self.produced_knowledge],
            "contradictions": [x.to_dict() for x in self.contradictions],
            "gaps": [x.to_dict() for x in self.gaps],
            "recommendations": [x.to_dict() for x in self.recommendations],
            "escalation": self.escalation.to_dict() if self.escalation else None,
            "confidence_delta": self.confidence_delta,
            "trace_entries": [x.to_dict() for x in self.trace_entries],
            "started_at": self.started_at.isoformat(), "completed_at": self.completed_at.isoformat(),
            "metadata": _json_thaw(self.metadata), "contract_version": self.contract_version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReasoningRuleResult:
        if not isinstance(data, Mapping):
            raise ReasoningRuleSerializationError("ReasoningRuleResult.from_dict requires a mapping", field="data")
        _reject_unknown(data, set(cls.__dataclass_fields__), cls.__name__)
        _require(data, {"rule_id", "rule_name", "rule_version", "status", "started_at", "completed_at"}, cls.__name__)
        values = dict(data)
        values["started_at"] = _parse_datetime(values["started_at"], "started_at")
        values["completed_at"] = _parse_datetime(values["completed_at"], "completed_at")
        try:
            values["produced_knowledge"] = tuple(
                item if isinstance(item, KnowledgeItem) else KnowledgeItem.from_dict(dict(item))
                for item in values.get("produced_knowledge", ())
            )
            values["contradictions"] = tuple(
                item if isinstance(item, Contradiction) else Contradiction.from_dict(dict(item))
                for item in values.get("contradictions", ())
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ReasoningRuleSerializationError("invalid Phase 8 cognitive output", field="produced_knowledge") from exc
        return _construct(cls, values)


@runtime_checkable
class ReasoningRule(Protocol):
    @property
    def definition(self) -> ReasoningRuleDefinition: ...

    def evaluate(self, context: ReasoningRuleContext) -> ReasoningRuleResult: ...


__all__ = [
    "MAX_CONFIDENCE_DELTA", "MAX_RULE_PRIORITY", "MIN_CONFIDENCE_DELTA",
    "MIN_RULE_PRIORITY", "REASONING_RULE_CONTRACT_VERSION", "ReasoningEscalation",
    "ReasoningFinding", "ReasoningGap", "ReasoningRecommendation", "ReasoningRule",
    "ReasoningRuleContext", "ReasoningRuleDefinition", "ReasoningRuleResult",
    "ReasoningRuleTraceEntry",
]
