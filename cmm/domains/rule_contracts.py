"""Strict Domain Rule contracts built on the common Cognitive Layer contract."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from cmm.cognitive.errors import (
    ReasoningRuleContractError,
    ReasoningRuleSerializationError,
)
from cmm.cognitive.knowledge import Contradiction, KnowledgeItem
from cmm.cognitive.reasoning_rule_contracts import (
    ReasoningEscalation,
    ReasoningFinding,
    ReasoningGap,
    ReasoningRecommendation,
    ReasoningRuleDefinition,
    ReasoningRuleResult,
    ReasoningRuleTraceEntry,
    _aware,
    _domain_id,
    _enum,
    _json_freeze,
    _json_thaw,
    _non_empty,
    _parse_datetime,
    _reject_unknown,
    _require,
    _rule_id,
    _semver,
    _str_tuple,
)
from cmm.domains.enums import (
    DomainRuleConflictSeverity,
    DomainRuleExecutionStatus,
    DomainRuleSelectionDecisionCode,
    DomainRuleSelectionStatus,
    DomainRuleSource,
)
from cmm.domains.errors import (
    DomainRuleContractError,
    DomainRuleSerializationError,
)

DOMAIN_RULE_CONTRACT_VERSION = "1.0.0"
MAX_AGGREGATE_CONFIDENCE_DELTA = 1.0


def _convert_contract(exc: ReasoningRuleContractError) -> DomainRuleContractError:
    return DomainRuleContractError(exc.message, field=exc.field, details=dict(exc.details))


def _construct(cls: type, values: dict[str, Any]) -> Any:
    try:
        return cls(**values)
    except (DomainRuleContractError, ReasoningRuleContractError) as exc:
        raise DomainRuleSerializationError(
            getattr(exc, "message", "invalid domain rule contract"),
            field=getattr(exc, "field", None),
            details=dict(getattr(exc, "details", {})),
        ) from exc


def _from_dict(cls: type, data: Mapping[str, Any], required: set[str]) -> Any:
    if not isinstance(data, Mapping):
        raise DomainRuleSerializationError(f"{cls.__name__}.from_dict requires a mapping", field="data")
    try:
        _reject_unknown(data, set(cls.__dataclass_fields__), cls.__name__)
        _require(data, required, cls.__name__)
    except ReasoningRuleSerializationError as exc:
        raise DomainRuleSerializationError(exc.message, field=exc.field, details=dict(exc.details)) from exc
    return _construct(cls, dict(data))


def _nested(value: Any, cls: type, field_name: str) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise DomainRuleContractError(f"{field_name} must be a sequence", field=field_name)
    result = []
    for index, item in enumerate(value):
        if isinstance(item, cls):
            result.append(item)
        elif isinstance(item, Mapping):
            try:
                result.append(cls.from_dict(item))
            except (DomainRuleSerializationError, ReasoningRuleSerializationError) as exc:
                raise DomainRuleContractError(
                    getattr(exc, "message", "invalid nested contract"),
                    field=f"{field_name}[{index}].{getattr(exc, 'field', 'data') or 'data'}",
                ) from exc
        else:
            raise DomainRuleContractError(
                f"{field_name}[{index}] must be a {cls.__name__}", field=f"{field_name}[{index}]"
            )
    return tuple(result)


@dataclass(frozen=True, slots=True)
class DomainReasoningRuleDefinition(ReasoningRuleDefinition):
    def __post_init__(self) -> None:
        try:
            super().__post_init__()
        except ReasoningRuleContractError as exc:
            raise _convert_contract(exc) from exc
        if self.domain_id is None or self.scope.value != "domain":
            raise DomainRuleContractError(
                "DomainReasoningRuleDefinition requires domain scope and domain_id", field="domain_id"
            )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainReasoningRuleDefinition:
        return _from_dict(
            cls, data,
            {"id", "name", "version", "scope", "category", "status", "priority", "risk_level", "domain_id"},
        )


@dataclass(frozen=True, slots=True)
class DomainRuleResult(ReasoningRuleResult):
    def __post_init__(self) -> None:
        try:
            super().__post_init__()
        except ReasoningRuleContractError as exc:
            raise _convert_contract(exc) from exc
        if self.domain_id is None:
            raise DomainRuleContractError("DomainRuleResult requires domain_id", field="domain_id")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainRuleResult:
        if not isinstance(data, Mapping):
            raise DomainRuleSerializationError("DomainRuleResult.from_dict requires a mapping", field="data")
        try:
            common = ReasoningRuleResult.from_dict(data)
        except ReasoningRuleSerializationError as exc:
            raise DomainRuleSerializationError(exc.message, field=exc.field, details=dict(exc.details)) from exc
        return _construct(cls, {name: getattr(common, name) for name in cls.__dataclass_fields__})


@dataclass(frozen=True, slots=True)
class DomainRuleSelectionPolicy:
    include_optional: bool = True
    include_requested: bool = True
    denied_permissions: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = DOMAIN_RULE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.include_optional, bool):
            raise DomainRuleContractError("include_optional must be a strict boolean", field="include_optional")
        if not isinstance(self.include_requested, bool):
            raise DomainRuleContractError("include_requested must be a strict boolean", field="include_requested")
        try:
            object.__setattr__(self, "denied_permissions", _str_tuple(self.denied_permissions, "denied_permissions"))
            object.__setattr__(self, "metadata", _json_freeze(self.metadata))
            object.__setattr__(self, "contract_version", _semver(self.contract_version, "contract_version"))
        except ReasoningRuleContractError as exc:
            raise _convert_contract(exc) from exc

    def to_dict(self) -> dict[str, Any]:
        return {"include_optional": self.include_optional, "include_requested": self.include_requested,
                "denied_permissions": list(self.denied_permissions), "metadata": _json_thaw(self.metadata),
                "contract_version": self.contract_version}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainRuleSelectionPolicy:
        return _from_dict(cls, data, set())


@dataclass(frozen=True, slots=True)
class DomainRuleExecutionPolicy:
    stop_on_required_failure: bool = True
    aggregate_confidence_limit: float = MAX_AGGREGATE_CONFIDENCE_DELTA
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = DOMAIN_RULE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.stop_on_required_failure, bool):
            raise DomainRuleContractError("stop_on_required_failure must be a strict boolean", field="stop_on_required_failure")
        if isinstance(self.aggregate_confidence_limit, bool) or not isinstance(self.aggregate_confidence_limit, (int, float)):
            raise DomainRuleContractError("aggregate_confidence_limit must be numeric", field="aggregate_confidence_limit")
        limit = float(self.aggregate_confidence_limit)
        if (
            not math.isfinite(limit)
            or not 0.0 < limit <= MAX_AGGREGATE_CONFIDENCE_DELTA
        ):
            raise DomainRuleContractError("aggregate_confidence_limit must be finite and in (0, 1]", field="aggregate_confidence_limit")
        object.__setattr__(self, "aggregate_confidence_limit", limit)
        try:
            object.__setattr__(self, "metadata", _json_freeze(self.metadata))
            object.__setattr__(self, "contract_version", _semver(self.contract_version, "contract_version"))
        except ReasoningRuleContractError as exc:
            raise _convert_contract(exc) from exc

    def to_dict(self) -> dict[str, Any]:
        return {"stop_on_required_failure": self.stop_on_required_failure,
                "aggregate_confidence_limit": self.aggregate_confidence_limit,
                "metadata": _json_thaw(self.metadata), "contract_version": self.contract_version}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainRuleExecutionPolicy:
        return _from_dict(cls, data, set())


@dataclass(frozen=True, slots=True)
class DomainRuleSourceRecord:
    source: DomainRuleSource
    reference: str
    required: bool
    domain_id: str | None = None
    profile_name: str | None = None
    precedence: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "source", _enum(self.source, DomainRuleSource, "source"))
            object.__setattr__(self, "reference", _non_empty(self.reference, "reference"))
            object.__setattr__(self, "domain_id", _domain_id(self.domain_id, "domain_id", optional=True))
            if self.profile_name is not None:
                object.__setattr__(self, "profile_name", _non_empty(self.profile_name, "profile_name"))
            object.__setattr__(self, "metadata", _json_freeze(self.metadata))
        except ReasoningRuleContractError as exc:
            raise _convert_contract(exc) from exc
        if not isinstance(self.required, bool):
            raise DomainRuleContractError("required must be a strict boolean", field="required")
        if isinstance(self.precedence, bool) or not isinstance(self.precedence, int) or self.precedence < 0:
            raise DomainRuleContractError("precedence must be a non-negative integer", field="precedence")

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source.value, "reference": self.reference, "required": self.required,
                "domain_id": self.domain_id, "profile_name": self.profile_name,
                "precedence": self.precedence, "metadata": _json_thaw(self.metadata)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainRuleSourceRecord:
        return _from_dict(cls, data, {"source", "reference", "required"})


@dataclass(frozen=True, slots=True)
class DomainRuleSelectionDecision:
    code: DomainRuleSelectionDecisionCode
    rule_id: str
    included: bool
    message: str
    sources: tuple[DomainRuleSourceRecord, ...] = ()
    missing_permissions: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "code", _enum(self.code, DomainRuleSelectionDecisionCode, "code"))
            object.__setattr__(self, "rule_id", _rule_id(self.rule_id, "rule_id"))
            object.__setattr__(self, "message", _non_empty(self.message, "message"))
            object.__setattr__(self, "missing_permissions", _str_tuple(self.missing_permissions, "missing_permissions"))
            object.__setattr__(self, "metadata", _json_freeze(self.metadata))
        except ReasoningRuleContractError as exc:
            raise _convert_contract(exc) from exc
        if not isinstance(self.included, bool):
            raise DomainRuleContractError("included must be a strict boolean", field="included")
        object.__setattr__(self, "sources", _nested(self.sources, DomainRuleSourceRecord, "sources"))

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code.value, "rule_id": self.rule_id, "included": self.included,
                "message": self.message, "sources": [x.to_dict() for x in self.sources],
                "missing_permissions": list(self.missing_permissions), "metadata": _json_thaw(self.metadata)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainRuleSelectionDecision:
        return _from_dict(cls, data, {"code", "rule_id", "included", "message"})


@dataclass(frozen=True, slots=True)
class DomainRuleSelectionConflict:
    code: str
    rule_id: str
    message: str
    severity: DomainRuleConflictSeverity = DomainRuleConflictSeverity.BLOCKING
    sources: tuple[DomainRuleSourceRecord, ...] = ()
    missing_permissions: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "code", _non_empty(self.code, "code"))
            object.__setattr__(self, "rule_id", _rule_id(self.rule_id, "rule_id"))
            object.__setattr__(self, "message", _non_empty(self.message, "message"))
            object.__setattr__(self, "severity", _enum(self.severity, DomainRuleConflictSeverity, "severity"))
            object.__setattr__(self, "missing_permissions", _str_tuple(self.missing_permissions, "missing_permissions"))
            object.__setattr__(self, "metadata", _json_freeze(self.metadata))
        except ReasoningRuleContractError as exc:
            raise _convert_contract(exc) from exc
        object.__setattr__(self, "sources", _nested(self.sources, DomainRuleSourceRecord, "sources"))

    @property
    def blocking(self) -> bool:
        return self.severity is DomainRuleConflictSeverity.BLOCKING

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "rule_id": self.rule_id, "message": self.message,
                "severity": self.severity.value, "sources": [x.to_dict() for x in self.sources],
                "missing_permissions": list(self.missing_permissions), "metadata": _json_thaw(self.metadata)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainRuleSelectionConflict:
        return _from_dict(cls, data, {"code", "rule_id", "message"})


@dataclass(frozen=True, slots=True)
class SelectedReasoningRule:
    definition: ReasoningRuleDefinition
    sources: tuple[DomainRuleSourceRecord, ...]
    group: DomainRuleSource
    required: bool

    def __post_init__(self) -> None:
        if isinstance(self.definition, Mapping):
            try:
                object.__setattr__(self, "definition", ReasoningRuleDefinition.from_dict(self.definition))
            except ReasoningRuleSerializationError as exc:
                raise DomainRuleContractError(exc.message, field="definition") from exc
        if not isinstance(self.definition, ReasoningRuleDefinition):
            raise DomainRuleContractError("definition must be a ReasoningRuleDefinition", field="definition")
        object.__setattr__(self, "sources", _nested(self.sources, DomainRuleSourceRecord, "sources"))
        if not self.sources:
            raise DomainRuleContractError("sources must not be empty", field="sources")
        try:
            object.__setattr__(self, "group", _enum(self.group, DomainRuleSource, "group"))
        except ReasoningRuleContractError as exc:
            raise _convert_contract(exc) from exc
        if not isinstance(self.required, bool):
            raise DomainRuleContractError("required must be a strict boolean", field="required")

    def to_dict(self) -> dict[str, Any]:
        return {"definition": self.definition.to_dict(), "sources": [x.to_dict() for x in self.sources],
                "group": self.group.value, "required": self.required}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SelectedReasoningRule:
        return _from_dict(cls, data, {"definition", "sources", "group", "required"})


@dataclass(frozen=True, slots=True)
class DomainRuleExecutionPlan:
    id: str
    status: DomainRuleSelectionStatus
    created_at: datetime
    selected_rules: tuple[SelectedReasoningRule, ...] = ()
    decisions: tuple[DomainRuleSelectionDecision, ...] = ()
    conflicts: tuple[DomainRuleSelectionConflict, ...] = ()
    omitted_rule_ids: tuple[str, ...] = ()
    blocked_rule_ids: tuple[str, ...] = ()
    missing_permissions: tuple[str, ...] = ()
    contributing_profiles: tuple[str, ...] = ()
    contributing_domains: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = DOMAIN_RULE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "id", _non_empty(self.id, "id"))
            object.__setattr__(self, "status", _enum(self.status, DomainRuleSelectionStatus, "status"))
            object.__setattr__(self, "created_at", _aware(self.created_at, "created_at"))
            object.__setattr__(self, "omitted_rule_ids", tuple(_rule_id(x, "omitted_rule_ids") for x in _str_tuple(self.omitted_rule_ids, "omitted_rule_ids")))
            object.__setattr__(self, "blocked_rule_ids", tuple(_rule_id(x, "blocked_rule_ids") for x in _str_tuple(self.blocked_rule_ids, "blocked_rule_ids")))
            object.__setattr__(self, "missing_permissions", _str_tuple(self.missing_permissions, "missing_permissions"))
            object.__setattr__(self, "contributing_profiles", _str_tuple(self.contributing_profiles, "contributing_profiles"))
            object.__setattr__(self, "contributing_domains", tuple(_domain_id(x, "contributing_domains") for x in _str_tuple(self.contributing_domains, "contributing_domains")))
            object.__setattr__(self, "metadata", _json_freeze(self.metadata))
            object.__setattr__(self, "contract_version", _semver(self.contract_version, "contract_version"))
        except ReasoningRuleContractError as exc:
            raise _convert_contract(exc) from exc
        object.__setattr__(self, "selected_rules", _nested(self.selected_rules, SelectedReasoningRule, "selected_rules"))
        object.__setattr__(self, "decisions", _nested(self.decisions, DomainRuleSelectionDecision, "decisions"))
        object.__setattr__(self, "conflicts", _nested(self.conflicts, DomainRuleSelectionConflict, "conflicts"))
        keys = [(x.definition.id, x.definition.version) for x in self.selected_rules]
        if len(keys) != len(set(keys)):
            raise DomainRuleContractError("selected_rules must be unique by id/version", field="selected_rules")
        if self.status is DomainRuleSelectionStatus.BLOCKED and not self.conflicts and not self.blocked_rule_ids:
            raise DomainRuleContractError("blocked plan requires conflicts or blocked rules", field="status")
        if self.status is DomainRuleSelectionStatus.READY and any(x.blocking for x in self.conflicts):
            raise DomainRuleContractError("ready plan cannot contain blocking conflicts", field="status")

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "status": self.status.value,
                "selected_rules": [x.to_dict() for x in self.selected_rules],
                "decisions": [x.to_dict() for x in self.decisions],
                "conflicts": [x.to_dict() for x in self.conflicts],
                "omitted_rule_ids": list(self.omitted_rule_ids), "blocked_rule_ids": list(self.blocked_rule_ids),
                "missing_permissions": list(self.missing_permissions),
                "contributing_profiles": list(self.contributing_profiles),
                "contributing_domains": list(self.contributing_domains),
                "created_at": self.created_at.isoformat(), "metadata": _json_thaw(self.metadata),
                "contract_version": self.contract_version}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainRuleExecutionPlan:
        if not isinstance(data, Mapping):
            raise DomainRuleSerializationError("DomainRuleExecutionPlan.from_dict requires a mapping", field="data")
        values = dict(data)
        try:
            _reject_unknown(data, set(cls.__dataclass_fields__), cls.__name__)
            _require(data, {"id", "status", "created_at"}, cls.__name__)
            values["created_at"] = _parse_datetime(values["created_at"], "created_at")
        except (ReasoningRuleSerializationError, ReasoningRuleContractError) as exc:
            raise DomainRuleSerializationError(getattr(exc, "message", "invalid plan"), field=getattr(exc, "field", None)) from exc
        return _construct(cls, values)


@dataclass(frozen=True, slots=True)
class DomainRuleExecutionResult:
    id: str
    plan_id: str
    status: DomainRuleExecutionStatus
    started_at: datetime
    completed_at: datetime
    rule_results: tuple[ReasoningRuleResult, ...] = ()
    findings: tuple[ReasoningFinding, ...] = ()
    produced_knowledge: tuple[Any, ...] = ()
    contradictions: tuple[Any, ...] = ()
    gaps: tuple[ReasoningGap, ...] = ()
    recommendations: tuple[ReasoningRecommendation, ...] = ()
    escalations: tuple[ReasoningEscalation, ...] = ()
    confidence_delta: float = 0.0
    applied_rule_ids: tuple[str, ...] = ()
    skipped_rule_ids: tuple[str, ...] = ()
    blocked_rule_ids: tuple[str, ...] = ()
    failed_rule_ids: tuple[str, ...] = ()
    trace_entries: tuple[ReasoningRuleTraceEntry, ...] = ()
    decisions: tuple[DomainRuleSelectionDecision, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    contract_version: str = DOMAIN_RULE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "id", _non_empty(self.id, "id"))
            object.__setattr__(self, "plan_id", _non_empty(self.plan_id, "plan_id"))
            object.__setattr__(self, "status", _enum(self.status, DomainRuleExecutionStatus, "status"))
            object.__setattr__(self, "started_at", _aware(self.started_at, "started_at"))
            object.__setattr__(self, "completed_at", _aware(self.completed_at, "completed_at"))
            for name in ("applied_rule_ids", "skipped_rule_ids", "blocked_rule_ids", "failed_rule_ids"):
                object.__setattr__(self, name, tuple(_rule_id(x, name) for x in _str_tuple(getattr(self, name), name)))
            object.__setattr__(self, "metadata", _json_freeze(self.metadata))
            object.__setattr__(self, "contract_version", _semver(self.contract_version, "contract_version"))
        except ReasoningRuleContractError as exc:
            raise _convert_contract(exc) from exc
        if self.completed_at < self.started_at:
            raise DomainRuleContractError("completed_at must not precede started_at", field="completed_at")
        object.__setattr__(self, "rule_results", _nested(self.rule_results, ReasoningRuleResult, "rule_results"))
        object.__setattr__(self, "findings", _nested(self.findings, ReasoningFinding, "findings"))
        object.__setattr__(self, "gaps", _nested(self.gaps, ReasoningGap, "gaps"))
        object.__setattr__(self, "recommendations", _nested(self.recommendations, ReasoningRecommendation, "recommendations"))
        object.__setattr__(self, "escalations", _nested(self.escalations, ReasoningEscalation, "escalations"))
        object.__setattr__(self, "trace_entries", _nested(self.trace_entries, ReasoningRuleTraceEntry, "trace_entries"))
        object.__setattr__(self, "decisions", _nested(self.decisions, DomainRuleSelectionDecision, "decisions"))
        if (
            isinstance(self.produced_knowledge, (str, bytes))
            or not isinstance(self.produced_knowledge, Sequence)
            or not all(isinstance(item, KnowledgeItem) for item in self.produced_knowledge)
        ):
            raise DomainRuleContractError(
                "produced_knowledge must contain KnowledgeItem values",
                field="produced_knowledge",
            )
        if (
            isinstance(self.contradictions, (str, bytes))
            or not isinstance(self.contradictions, Sequence)
            or not all(isinstance(item, Contradiction) for item in self.contradictions)
        ):
            raise DomainRuleContractError(
                "contradictions must contain Contradiction values",
                field="contradictions",
            )
        object.__setattr__(self, "produced_knowledge", tuple(self.produced_knowledge))
        object.__setattr__(self, "contradictions", tuple(self.contradictions))
        if isinstance(self.confidence_delta, bool) or not isinstance(
            self.confidence_delta, (int, float)
        ):
            raise DomainRuleContractError(
                "confidence_delta must be numeric", field="confidence_delta"
            )
        confidence_delta = float(self.confidence_delta)
        if (
            not math.isfinite(confidence_delta)
            or abs(confidence_delta) > MAX_AGGREGATE_CONFIDENCE_DELTA
        ):
            raise DomainRuleContractError(
                "confidence_delta must be finite and within the aggregate limit",
                field="confidence_delta",
            )
        object.__setattr__(self, "confidence_delta", confidence_delta)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "plan_id": self.plan_id, "status": self.status.value,
                "rule_results": [x.to_dict() for x in self.rule_results],
                "findings": [x.to_dict() for x in self.findings],
                "produced_knowledge": [x.to_dict() for x in self.produced_knowledge],
                "contradictions": [x.to_dict() for x in self.contradictions],
                "gaps": [x.to_dict() for x in self.gaps],
                "recommendations": [x.to_dict() for x in self.recommendations],
                "escalations": [x.to_dict() for x in self.escalations],
                "confidence_delta": self.confidence_delta,
                "applied_rule_ids": list(self.applied_rule_ids), "skipped_rule_ids": list(self.skipped_rule_ids),
                "blocked_rule_ids": list(self.blocked_rule_ids), "failed_rule_ids": list(self.failed_rule_ids),
                "trace_entries": [x.to_dict() for x in self.trace_entries],
                "decisions": [x.to_dict() for x in self.decisions],
                "started_at": self.started_at.isoformat(), "completed_at": self.completed_at.isoformat(),
                "metadata": _json_thaw(self.metadata), "contract_version": self.contract_version}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainRuleExecutionResult:
        if not isinstance(data, Mapping):
            raise DomainRuleSerializationError("DomainRuleExecutionResult.from_dict requires a mapping", field="data")
        values = dict(data)
        try:
            _reject_unknown(data, set(cls.__dataclass_fields__), cls.__name__)
            _require(data, {"id", "plan_id", "status", "started_at", "completed_at"}, cls.__name__)
            values["started_at"] = _parse_datetime(values["started_at"], "started_at")
            values["completed_at"] = _parse_datetime(values["completed_at"], "completed_at")
            values["produced_knowledge"] = tuple(
                item if isinstance(item, KnowledgeItem) else KnowledgeItem.from_dict(dict(item))
                for item in values.get("produced_knowledge", ())
            )
            values["contradictions"] = tuple(
                item if isinstance(item, Contradiction) else Contradiction.from_dict(dict(item))
                for item in values.get("contradictions", ())
            )
        except (ReasoningRuleSerializationError, ReasoningRuleContractError) as exc:
            raise DomainRuleSerializationError(getattr(exc, "message", "invalid execution result"), field=getattr(exc, "field", None)) from exc
        except (KeyError, TypeError, ValueError) as exc:
            raise DomainRuleSerializationError(
                "invalid Phase 8 cognitive output", field="produced_knowledge"
            ) from exc
        return _construct(cls, values)


__all__ = [
    "DOMAIN_RULE_CONTRACT_VERSION", "MAX_AGGREGATE_CONFIDENCE_DELTA",
    "DomainReasoningRuleDefinition", "DomainRuleExecutionPlan",
    "DomainRuleExecutionPolicy", "DomainRuleExecutionResult", "DomainRuleResult",
    "DomainRuleSelectionConflict", "DomainRuleSelectionDecision", "DomainRuleSelectionPolicy",
    "DomainRuleSourceRecord", "SelectedReasoningRule",
]
