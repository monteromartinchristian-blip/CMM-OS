"""Phase 9.6 – Information Acquisition Contracts.

Defines dataclasses, value objects, and contracts for information acquisition requests,
candidates, decisions, policies, contexts, costs, and results.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.enums import (
    InformationAcquisitionDecisionType,
    InformationAcquisitionRisk,
    InformationAcquisitionSource,
    InformationAcquisitionStatus,
    InformationAcquisitionStrategy,
)
from cmm.agent_runtime.errors import InvalidInformationAcquisitionContractError


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _freeze_metadata(metadata: Any) -> MappingProxyType[str, Any]:
    if isinstance(metadata, MappingProxyType):
        return metadata
    if isinstance(metadata, Mapping):
        return MappingProxyType(dict(metadata))
    return MappingProxyType({})


def _validate_non_empty_str(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise InvalidInformationAcquisitionContractError(
            f"{name} must be a non-empty string"
        )


def _validate_non_negative_number(value: Any, name: str) -> None:
    if not isinstance(value, (int, float)) or value < 0:
        raise InvalidInformationAcquisitionContractError(
            f"{name} must be a non-negative number"
        )


def _validate_bounded_float(
    value: Any, name: str, min_val: float = 0.0, max_val: float = 1.0
) -> None:
    if not isinstance(value, (int, float)) or not (min_val <= float(value) <= max_val):
        raise InvalidInformationAcquisitionContractError(
            f"{name} must be a float between {min_val} and {max_val}"
        )


def generate_acquisition_request_id() -> str:
    """Generate a deterministic acquisition request identifier."""
    return f"acq-req-{uuid.uuid4().hex[:12]}"


def generate_acquisition_decision_id() -> str:
    """Generate a deterministic acquisition decision identifier."""
    return f"acq-dec-{uuid.uuid4().hex[:12]}"


def generate_acquisition_context_id() -> str:
    """Generate a deterministic acquisition context identifier."""
    return f"acq-ctx-{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True, slots=True)
class InformationAcquisitionCost:
    """Quantitative cost breakdown preview for an acquisition operation."""

    questions: int = 0
    internal_calls: int = 0
    external_calls: int = 0
    model_calls: int = 0
    tokens: int = 0
    monetary_cost: float = 0.0
    time_seconds: float = 0.0
    data_volume_bytes: int = 0
    risk: InformationAcquisitionRisk = InformationAcquisitionRisk.NONE
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_negative_number(self.questions, "questions")
        _validate_non_negative_number(self.internal_calls, "internal_calls")
        _validate_non_negative_number(self.external_calls, "external_calls")
        _validate_non_negative_number(self.model_calls, "model_calls")
        _validate_non_negative_number(self.tokens, "tokens")
        _validate_non_negative_number(self.monetary_cost, "monetary_cost")
        _validate_non_negative_number(self.time_seconds, "time_seconds")
        _validate_non_negative_number(self.data_volume_bytes, "data_volume_bytes")

        if isinstance(self.risk, str):
            try:
                object.__setattr__(self, "risk", InformationAcquisitionRisk(self.risk))
            except ValueError:
                raise InvalidInformationAcquisitionContractError(
                    f"Unknown InformationAcquisitionRisk: {self.risk}"
                )

        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        return {
            "questions": self.questions,
            "internal_calls": self.internal_calls,
            "external_calls": self.external_calls,
            "model_calls": self.model_calls,
            "tokens": self.tokens,
            "monetary_cost": self.monetary_cost,
            "time_seconds": self.time_seconds,
            "data_volume_bytes": self.data_volume_bytes,
            "risk": self.risk.value,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> InformationAcquisitionCost:
        if not isinstance(mapping, Mapping):
            raise InvalidInformationAcquisitionContractError(
                "mapping must be a Mapping instance"
            )

        risk_val = mapping.get("risk", InformationAcquisitionRisk.NONE)
        if isinstance(risk_val, str):
            try:
                risk_val = InformationAcquisitionRisk(risk_val)
            except ValueError:
                raise InvalidInformationAcquisitionContractError(
                    f"Unknown InformationAcquisitionRisk: {risk_val}"
                )

        return cls(
            questions=int(mapping.get("questions", 0)),
            internal_calls=int(mapping.get("internal_calls", 0)),
            external_calls=int(mapping.get("external_calls", 0)),
            model_calls=int(mapping.get("model_calls", 0)),
            tokens=int(mapping.get("tokens", 0)),
            monetary_cost=float(mapping.get("monetary_cost", 0.0)),
            time_seconds=float(mapping.get("time_seconds", 0.0)),
            data_volume_bytes=int(mapping.get("data_volume_bytes", 0)),
            risk=risk_val,
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> InformationAcquisitionCost:
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class InformationAcquisitionEstimate:
    """Estimated cost, duration, and confidence gain for candidate strategies."""

    cost: InformationAcquisitionCost
    duration_seconds: float = 0.0
    probability_of_success: float = 1.0
    confidence_gain: float = 0.0
    resource_count: int = 0
    call_count: int = 0
    uncertainty: float = 0.0
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        if not isinstance(self.cost, InformationAcquisitionCost):
            raise InvalidInformationAcquisitionContractError(
                "cost must be an InformationAcquisitionCost instance"
            )
        _validate_non_negative_number(self.duration_seconds, "duration_seconds")
        _validate_bounded_float(self.probability_of_success, "probability_of_success")
        _validate_bounded_float(self.confidence_gain, "confidence_gain")
        _validate_non_negative_number(self.resource_count, "resource_count")
        _validate_non_negative_number(self.call_count, "call_count")
        _validate_bounded_float(self.uncertainty, "uncertainty")

        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        return {
            "cost": self.cost.serialize(),
            "duration_seconds": self.duration_seconds,
            "probability_of_success": self.probability_of_success,
            "confidence_gain": self.confidence_gain,
            "resource_count": self.resource_count,
            "call_count": self.call_count,
            "uncertainty": self.uncertainty,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> InformationAcquisitionEstimate:
        if not isinstance(mapping, Mapping):
            raise InvalidInformationAcquisitionContractError(
                "mapping must be a Mapping instance"
            )

        cost_val = mapping.get("cost")
        if isinstance(cost_val, Mapping):
            cost_obj = InformationAcquisitionCost.from_mapping(cost_val)
        elif isinstance(cost_val, InformationAcquisitionCost):
            cost_obj = cost_val
        else:
            cost_obj = InformationAcquisitionCost()

        return cls(
            cost=cost_obj,
            duration_seconds=float(mapping.get("duration_seconds", 0.0)),
            probability_of_success=float(mapping.get("probability_of_success", 1.0)),
            confidence_gain=float(mapping.get("confidence_gain", 0.0)),
            resource_count=int(mapping.get("resource_count", 0)),
            call_count=int(mapping.get("call_count", 0)),
            uncertainty=float(mapping.get("uncertainty", 0.0)),
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> InformationAcquisitionEstimate:
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class InformationAcquisitionWarning:
    """Warning item produced during acquisition resolution."""

    code: str
    message: str
    timestamp: str = field(default_factory=_now_iso)
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.code, "code")
        _validate_non_empty_str(self.message, "message")
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> InformationAcquisitionWarning:
        if not isinstance(mapping, Mapping):
            raise InvalidInformationAcquisitionContractError(
                "mapping must be a Mapping instance"
            )
        return cls(
            code=str(mapping.get("code", "")),
            message=str(mapping.get("message", "")),
            timestamp=str(mapping.get("timestamp", _now_iso())),
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> InformationAcquisitionWarning:
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class InformationAcquisitionContext:
    """Runtime context for evaluating information acquisition strategies."""

    request_id: str
    agent_run_id: str
    goal_id: str
    gap_id: str
    sources_available: tuple[InformationAcquisitionSource, ...] = ()
    permissions: tuple[str, ...] = ()
    sensitivity: str = "internal"
    current_question_count: int = 0
    current_internal_call_count: int = 0
    current_external_call_count: int = 0
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.request_id, "request_id")
        _validate_non_empty_str(self.agent_run_id, "agent_run_id")
        _validate_non_empty_str(self.goal_id, "goal_id")
        _validate_non_empty_str(self.gap_id, "gap_id")
        _validate_non_negative_number(
            self.current_question_count, "current_question_count"
        )
        _validate_non_negative_number(
            self.current_internal_call_count, "current_internal_call_count"
        )
        _validate_non_negative_number(
            self.current_external_call_count, "current_external_call_count"
        )

        norm_sources: list[InformationAcquisitionSource] = []
        for s in self.sources_available:
            if isinstance(s, str):
                try:
                    norm_sources.append(InformationAcquisitionSource(s))
                except ValueError:
                    raise InvalidInformationAcquisitionContractError(
                        f"Unknown InformationAcquisitionSource: {s}"
                    )
            elif isinstance(s, InformationAcquisitionSource):
                norm_sources.append(s)
            else:
                raise InvalidInformationAcquisitionContractError(
                    f"Invalid source type: {type(s)}"
                )

        object.__setattr__(self, "sources_available", tuple(norm_sources))
        object.__setattr__(self, "permissions", tuple(str(p) for p in self.permissions))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "gap_id": self.gap_id,
            "sources_available": [s.value for s in self.sources_available],
            "permissions": list(self.permissions),
            "sensitivity": self.sensitivity,
            "current_question_count": self.current_question_count,
            "current_internal_call_count": self.current_internal_call_count,
            "current_external_call_count": self.current_external_call_count,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> InformationAcquisitionContext:
        if not isinstance(mapping, Mapping):
            raise InvalidInformationAcquisitionContractError(
                "mapping must be a Mapping instance"
            )

        sources_raw = mapping.get("sources_available", ())
        sources_tuple = tuple(
            InformationAcquisitionSource(s) if isinstance(s, str) else s
            for s in sources_raw
        )

        return cls(
            request_id=str(mapping["request_id"]),
            agent_run_id=str(mapping["agent_run_id"]),
            goal_id=str(mapping["goal_id"]),
            gap_id=str(mapping["gap_id"]),
            sources_available=sources_tuple,
            permissions=tuple(str(p) for p in mapping.get("permissions", ())),
            sensitivity=str(mapping.get("sensitivity", "internal")),
            current_question_count=int(mapping.get("current_question_count", 0)),
            current_internal_call_count=int(
                mapping.get("current_internal_call_count", 0)
            ),
            current_external_call_count=int(
                mapping.get("current_external_call_count", 0)
            ),
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> InformationAcquisitionContext:
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class InformationAcquisitionPolicy:
    """Configurable governing rules for information acquisition resolution."""

    preferred_strategies: tuple[InformationAcquisitionStrategy, ...] = (
        InformationAcquisitionStrategy.SEARCH_KNOWLEDGE,
        InformationAcquisitionStrategy.LOAD_INTERNAL_RESOURCE,
        InformationAcquisitionStrategy.ASK_USER,
        InformationAcquisitionStrategy.SEARCH_REPOSITORY,
        InformationAcquisitionStrategy.SEARCH_EXTERNAL_SOURCE,
        InformationAcquisitionStrategy.INFER_WITH_PERMISSION,
        InformationAcquisitionStrategy.REQUEST_HUMAN_REVIEW,
        InformationAcquisitionStrategy.ACCEPT_UNCERTAINTY,
        InformationAcquisitionStrategy.PAUSE,
        InformationAcquisitionStrategy.ABORT,
    )
    allowed_strategies: tuple[InformationAcquisitionStrategy, ...] = (
        InformationAcquisitionStrategy.ASK_USER,
        InformationAcquisitionStrategy.LOAD_INTERNAL_RESOURCE,
        InformationAcquisitionStrategy.SEARCH_KNOWLEDGE,
        InformationAcquisitionStrategy.SEARCH_REPOSITORY,
        InformationAcquisitionStrategy.SEARCH_EXTERNAL_SOURCE,
        InformationAcquisitionStrategy.INFER_WITH_PERMISSION,
        InformationAcquisitionStrategy.REQUEST_HUMAN_REVIEW,
        InformationAcquisitionStrategy.ACCEPT_UNCERTAINTY,
        InformationAcquisitionStrategy.PAUSE,
        InformationAcquisitionStrategy.ABORT,
    )
    prohibited_strategies: tuple[InformationAcquisitionStrategy, ...] = ()
    maximum_risk: InformationAcquisitionRisk = InformationAcquisitionRisk.CRITICAL
    maximum_cost: float = 100.0
    allow_questions: bool = True
    allow_internal_search: bool = True
    allow_external_search: bool = True
    allow_inference: bool = True
    allow_human_review: bool = True
    allow_accept_uncertainty: bool = True
    sensitivity_rules: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    require_approval: bool = False
    question_limit: int = 5
    internal_call_limit: int = 20
    external_call_limit: int = 5
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_negative_number(self.maximum_cost, "maximum_cost")
        _validate_non_negative_number(self.question_limit, "question_limit")
        _validate_non_negative_number(self.internal_call_limit, "internal_call_limit")
        _validate_non_negative_number(self.external_call_limit, "external_call_limit")

        if isinstance(self.maximum_risk, str):
            try:
                object.__setattr__(
                    self, "maximum_risk", InformationAcquisitionRisk(self.maximum_risk)
                )
            except ValueError:
                raise InvalidInformationAcquisitionContractError(
                    f"Unknown InformationAcquisitionRisk: {self.maximum_risk}"
                )

        norm_preferred: list[InformationAcquisitionStrategy] = []
        for s in self.preferred_strategies:
            if isinstance(s, str):
                try:
                    norm_preferred.append(InformationAcquisitionStrategy(s))
                except ValueError:
                    raise InvalidInformationAcquisitionContractError(
                        f"Unknown InformationAcquisitionStrategy: {s}"
                    )
            elif isinstance(s, InformationAcquisitionStrategy):
                norm_preferred.append(s)

        norm_allowed: list[InformationAcquisitionStrategy] = []
        for s in self.allowed_strategies:
            if isinstance(s, str):
                try:
                    norm_allowed.append(InformationAcquisitionStrategy(s))
                except ValueError:
                    raise InvalidInformationAcquisitionContractError(
                        f"Unknown InformationAcquisitionStrategy: {s}"
                    )
            elif isinstance(s, InformationAcquisitionStrategy):
                norm_allowed.append(s)

        norm_prohibited: list[InformationAcquisitionStrategy] = []
        for s in self.prohibited_strategies:
            if isinstance(s, str):
                try:
                    norm_prohibited.append(InformationAcquisitionStrategy(s))
                except ValueError:
                    raise InvalidInformationAcquisitionContractError(
                        f"Unknown InformationAcquisitionStrategy: {s}"
                    )
            elif isinstance(s, InformationAcquisitionStrategy):
                norm_prohibited.append(s)

        object.__setattr__(self, "preferred_strategies", tuple(norm_preferred))
        object.__setattr__(self, "allowed_strategies", tuple(norm_allowed))
        object.__setattr__(self, "prohibited_strategies", tuple(norm_prohibited))
        object.__setattr__(
            self, "sensitivity_rules", _freeze_metadata(self.sensitivity_rules)
        )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        return {
            "preferred_strategies": [s.value for s in self.preferred_strategies],
            "allowed_strategies": [s.value for s in self.allowed_strategies],
            "prohibited_strategies": [s.value for s in self.prohibited_strategies],
            "maximum_risk": self.maximum_risk.value,
            "maximum_cost": self.maximum_cost,
            "allow_questions": self.allow_questions,
            "allow_internal_search": self.allow_internal_search,
            "allow_external_search": self.allow_external_search,
            "allow_inference": self.allow_inference,
            "allow_human_review": self.allow_human_review,
            "allow_accept_uncertainty": self.allow_accept_uncertainty,
            "sensitivity_rules": dict(self.sensitivity_rules),
            "require_approval": self.require_approval,
            "question_limit": self.question_limit,
            "internal_call_limit": self.internal_call_limit,
            "external_call_limit": self.external_call_limit,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> InformationAcquisitionPolicy:
        if not isinstance(mapping, Mapping):
            raise InvalidInformationAcquisitionContractError(
                "mapping must be a Mapping instance"
            )

        pref_raw = mapping.get("preferred_strategies", ())
        pref_tuple = tuple(
            InformationAcquisitionStrategy(s) if isinstance(s, str) else s
            for s in pref_raw
        )

        all_raw = mapping.get("allowed_strategies", ())
        all_tuple = tuple(
            InformationAcquisitionStrategy(s) if isinstance(s, str) else s
            for s in all_raw
        )

        proh_raw = mapping.get("prohibited_strategies", ())
        proh_tuple = tuple(
            InformationAcquisitionStrategy(s) if isinstance(s, str) else s
            for s in proh_raw
        )

        risk_val = mapping.get("maximum_risk", InformationAcquisitionRisk.CRITICAL)
        if isinstance(risk_val, str):
            try:
                risk_val = InformationAcquisitionRisk(risk_val)
            except ValueError:
                raise InvalidInformationAcquisitionContractError(
                    f"Unknown InformationAcquisitionRisk: {risk_val}"
                )

        return cls(
            preferred_strategies=pref_tuple if pref_raw else cls.preferred_strategies,
            allowed_strategies=all_tuple if all_raw else cls.allowed_strategies,
            prohibited_strategies=proh_tuple,
            maximum_risk=risk_val,
            maximum_cost=float(mapping.get("maximum_cost", 100.0)),
            allow_questions=bool(mapping.get("allow_questions", True)),
            allow_internal_search=bool(mapping.get("allow_internal_search", True)),
            allow_external_search=bool(mapping.get("allow_external_search", True)),
            allow_inference=bool(mapping.get("allow_inference", True)),
            allow_human_review=bool(mapping.get("allow_human_review", True)),
            allow_accept_uncertainty=bool(
                mapping.get("allow_accept_uncertainty", True)
            ),
            sensitivity_rules=mapping.get("sensitivity_rules", {}),
            require_approval=bool(mapping.get("require_approval", False)),
            question_limit=int(mapping.get("question_limit", 5)),
            internal_call_limit=int(mapping.get("internal_call_limit", 20)),
            external_call_limit=int(mapping.get("external_call_limit", 5)),
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> InformationAcquisitionPolicy:
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class InformationAcquisitionCandidate:
    """Evaluated acquisition strategy candidate prior to selection."""

    strategy: InformationAcquisitionStrategy
    applicability: float = 1.0
    availability: bool = True
    estimated_cost: InformationAcquisitionCost = field(
        default_factory=InformationAcquisitionCost
    )
    estimated_duration_seconds: float = 0.0
    expected_confidence_gain: float = 0.0
    probability_of_resolution: float = 1.0
    risk: InformationAcquisitionRisk = InformationAcquisitionRisk.NONE
    required_permissions: tuple[str, ...] = ()
    requires_approval: bool = False
    sensitivity: str = "internal"
    reasons: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        if isinstance(self.strategy, str):
            try:
                object.__setattr__(
                    self, "strategy", InformationAcquisitionStrategy(self.strategy)
                )
            except ValueError:
                raise InvalidInformationAcquisitionContractError(
                    f"Unknown InformationAcquisitionStrategy: {self.strategy}"
                )

        if isinstance(self.risk, str):
            try:
                object.__setattr__(self, "risk", InformationAcquisitionRisk(self.risk))
            except ValueError:
                raise InvalidInformationAcquisitionContractError(
                    f"Unknown InformationAcquisitionRisk: {self.risk}"
                )

        if not isinstance(self.estimated_cost, InformationAcquisitionCost):
            raise InvalidInformationAcquisitionContractError(
                "estimated_cost must be an InformationAcquisitionCost instance"
            )

        _validate_bounded_float(self.applicability, "applicability")
        _validate_non_negative_number(
            self.estimated_duration_seconds, "estimated_duration_seconds"
        )
        _validate_bounded_float(
            self.expected_confidence_gain, "expected_confidence_gain"
        )
        _validate_bounded_float(
            self.probability_of_resolution, "probability_of_resolution"
        )

        object.__setattr__(
            self,
            "required_permissions",
            tuple(str(p) for p in self.required_permissions),
        )
        object.__setattr__(self, "reasons", tuple(str(r) for r in self.reasons))
        object.__setattr__(self, "blockers", tuple(str(b) for b in self.blockers))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "applicability": self.applicability,
            "availability": self.availability,
            "estimated_cost": self.estimated_cost.serialize(),
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "expected_confidence_gain": self.expected_confidence_gain,
            "probability_of_resolution": self.probability_of_resolution,
            "risk": self.risk.value,
            "required_permissions": list(self.required_permissions),
            "requires_approval": self.requires_approval,
            "sensitivity": self.sensitivity,
            "reasons": list(self.reasons),
            "blockers": list(self.blockers),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(
        cls, mapping: Mapping[str, Any]
    ) -> InformationAcquisitionCandidate:
        if not isinstance(mapping, Mapping):
            raise InvalidInformationAcquisitionContractError(
                "mapping must be a Mapping instance"
            )

        strat_val = mapping["strategy"]
        if isinstance(strat_val, str):
            strat_val = InformationAcquisitionStrategy(strat_val)

        cost_val = mapping.get("estimated_cost")
        if isinstance(cost_val, Mapping):
            cost_obj = InformationAcquisitionCost.from_mapping(cost_val)
        elif isinstance(cost_val, InformationAcquisitionCost):
            cost_obj = cost_val
        else:
            cost_obj = InformationAcquisitionCost()

        risk_val = mapping.get("risk", InformationAcquisitionRisk.NONE)
        if isinstance(risk_val, str):
            risk_val = InformationAcquisitionRisk(risk_val)

        return cls(
            strategy=strat_val,
            applicability=float(mapping.get("applicability", 1.0)),
            availability=bool(mapping.get("availability", True)),
            estimated_cost=cost_obj,
            estimated_duration_seconds=float(
                mapping.get("estimated_duration_seconds", 0.0)
            ),
            expected_confidence_gain=float(
                mapping.get("expected_confidence_gain", 0.0)
            ),
            probability_of_resolution=float(
                mapping.get("probability_of_resolution", 1.0)
            ),
            risk=risk_val,
            required_permissions=tuple(
                str(p) for p in mapping.get("required_permissions", ())
            ),
            requires_approval=bool(mapping.get("requires_approval", False)),
            sensitivity=str(mapping.get("sensitivity", "internal")),
            reasons=tuple(str(r) for r in mapping.get("reasons", ())),
            blockers=tuple(str(b) for b in mapping.get("blockers", ())),
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> InformationAcquisitionCandidate:
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class InformationAcquisitionRequest:
    """Formal request to acquire information for resolving a specific gap."""

    id: str
    agent_run_id: str
    goal_id: str
    gap_id: str
    gap: Any
    cognitive_result_id: str = ""
    available_resource_ids: tuple[str, ...] = ()
    available_resources: tuple[Any, ...] = ()
    permissions: tuple[str, ...] = ()
    sensitivity: str = "internal"
    allowed_strategies: tuple[InformationAcquisitionStrategy, ...] = ()
    prohibited_strategies: tuple[InformationAcquisitionStrategy, ...] = ()
    maximum_questions_remaining: int = 5
    maximum_internal_calls_remaining: int = 20
    maximum_external_calls_remaining: int = 5
    maximum_cost: float = 100.0
    deadline: str | None = None
    temporal_reference: str = ""
    actor_id: str = "system"
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    created_at: str = field(default_factory=_now_iso)

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.id, "id")
        _validate_non_empty_str(self.agent_run_id, "agent_run_id")
        _validate_non_empty_str(self.goal_id, "goal_id")
        _validate_non_empty_str(self.gap_id, "gap_id")
        if self.gap is None:
            raise InvalidInformationAcquisitionContractError("gap cannot be None")

        _validate_non_negative_number(
            self.maximum_questions_remaining, "maximum_questions_remaining"
        )
        _validate_non_negative_number(
            self.maximum_internal_calls_remaining, "maximum_internal_calls_remaining"
        )
        _validate_non_negative_number(
            self.maximum_external_calls_remaining, "maximum_external_calls_remaining"
        )
        _validate_non_negative_number(self.maximum_cost, "maximum_cost")

        norm_allowed: list[InformationAcquisitionStrategy] = []
        for s in self.allowed_strategies:
            if isinstance(s, str):
                try:
                    norm_allowed.append(InformationAcquisitionStrategy(s))
                except ValueError:
                    raise InvalidInformationAcquisitionContractError(
                        f"Unknown InformationAcquisitionStrategy: {s}"
                    )
            elif isinstance(s, InformationAcquisitionStrategy):
                norm_allowed.append(s)

        norm_prohibited: list[InformationAcquisitionStrategy] = []
        for s in self.prohibited_strategies:
            if isinstance(s, str):
                try:
                    norm_prohibited.append(InformationAcquisitionStrategy(s))
                except ValueError:
                    raise InvalidInformationAcquisitionContractError(
                        f"Unknown InformationAcquisitionStrategy: {s}"
                    )
            elif isinstance(s, InformationAcquisitionStrategy):
                norm_prohibited.append(s)

        object.__setattr__(
            self,
            "available_resource_ids",
            tuple(str(r) for r in self.available_resource_ids),
        )
        object.__setattr__(self, "available_resources", tuple(self.available_resources))
        object.__setattr__(self, "permissions", tuple(str(p) for p in self.permissions))
        object.__setattr__(self, "allowed_strategies", tuple(norm_allowed))
        object.__setattr__(self, "prohibited_strategies", tuple(norm_prohibited))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        gap_ser = (
            self.gap.serialize()
            if hasattr(self.gap, "serialize")
            else (self.gap.to_dict() if hasattr(self.gap, "to_dict") else str(self.gap))
        )
        return {
            "id": self.id,
            "agent_run_id": self.agent_run_id,
            "goal_id": self.goal_id,
            "gap_id": self.gap_id,
            "gap": gap_ser,
            "cognitive_result_id": self.cognitive_result_id,
            "available_resource_ids": list(self.available_resource_ids),
            "available_resources": [
                r.serialize() if hasattr(r, "serialize") else str(r)
                for r in self.available_resources
            ],
            "permissions": list(self.permissions),
            "sensitivity": self.sensitivity,
            "allowed_strategies": [s.value for s in self.allowed_strategies],
            "prohibited_strategies": [s.value for s in self.prohibited_strategies],
            "maximum_questions_remaining": self.maximum_questions_remaining,
            "maximum_internal_calls_remaining": self.maximum_internal_calls_remaining,
            "maximum_external_calls_remaining": self.maximum_external_calls_remaining,
            "maximum_cost": self.maximum_cost,
            "deadline": self.deadline,
            "temporal_reference": self.temporal_reference,
            "actor_id": self.actor_id,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> InformationAcquisitionRequest:
        if not isinstance(mapping, Mapping):
            raise InvalidInformationAcquisitionContractError(
                "mapping must be a Mapping instance"
            )

        required_keys = {"id", "agent_run_id", "goal_id", "gap_id", "gap"}
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidInformationAcquisitionContractError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )

        allowed_raw = mapping.get("allowed_strategies", ())
        allowed_tuple = tuple(
            InformationAcquisitionStrategy(s) if isinstance(s, str) else s
            for s in allowed_raw
        )

        prohib_raw = mapping.get("prohibited_strategies", ())
        prohib_tuple = tuple(
            InformationAcquisitionStrategy(s) if isinstance(s, str) else s
            for s in prohib_raw
        )

        return cls(
            id=str(mapping["id"]),
            agent_run_id=str(mapping["agent_run_id"]),
            goal_id=str(mapping["goal_id"]),
            gap_id=str(mapping["gap_id"]),
            gap=mapping["gap"],
            cognitive_result_id=str(mapping.get("cognitive_result_id", "")),
            available_resource_ids=tuple(
                str(r) for r in mapping.get("available_resource_ids", ())
            ),
            available_resources=tuple(mapping.get("available_resources", ())),
            permissions=tuple(str(p) for p in mapping.get("permissions", ())),
            sensitivity=str(mapping.get("sensitivity", "internal")),
            allowed_strategies=allowed_tuple,
            prohibited_strategies=prohib_tuple,
            maximum_questions_remaining=int(
                mapping.get("maximum_questions_remaining", 5)
            ),
            maximum_internal_calls_remaining=int(
                mapping.get("maximum_internal_calls_remaining", 20)
            ),
            maximum_external_calls_remaining=int(
                mapping.get("maximum_external_calls_remaining", 5)
            ),
            maximum_cost=float(mapping.get("maximum_cost", 100.0)),
            deadline=mapping.get("deadline"),
            temporal_reference=str(mapping.get("temporal_reference", "")),
            actor_id=str(mapping.get("actor_id", "system")),
            metadata=mapping.get("metadata", {}),
            created_at=str(mapping.get("created_at", _now_iso())),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> InformationAcquisitionRequest:
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class InformationAcquisitionDecision:
    """Structured decision output specifying the selected acquisition strategy."""

    id: str
    request_id: str
    gap_id: str
    decision: InformationAcquisitionDecisionType
    strategy: InformationAcquisitionStrategy
    expected_cost: InformationAcquisitionCost
    reason_codes: tuple[str, ...] = ()
    selected_candidate: InformationAcquisitionCandidate | None = None
    rejected_candidates: tuple[InformationAcquisitionCandidate, ...] = ()
    expected_confidence_gain: float = 0.0
    requires_permission: bool = False
    requires_approval: bool = False
    requires_user_input: bool = False
    requires_resource: bool = False
    blocked: bool = False
    created_at: str = field(default_factory=_now_iso)
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        _validate_non_empty_str(self.id, "id")
        _validate_non_empty_str(self.request_id, "request_id")
        _validate_non_empty_str(self.gap_id, "gap_id")
        _validate_bounded_float(
            self.expected_confidence_gain, "expected_confidence_gain"
        )

        if isinstance(self.decision, str):
            try:
                object.__setattr__(
                    self, "decision", InformationAcquisitionDecisionType(self.decision)
                )
            except ValueError:
                raise InvalidInformationAcquisitionContractError(
                    f"Unknown InformationAcquisitionDecisionType: {self.decision}"
                )

        if isinstance(self.strategy, str):
            try:
                object.__setattr__(
                    self, "strategy", InformationAcquisitionStrategy(self.strategy)
                )
            except ValueError:
                raise InvalidInformationAcquisitionContractError(
                    f"Unknown InformationAcquisitionStrategy: {self.strategy}"
                )

        if not isinstance(self.expected_cost, InformationAcquisitionCost):
            raise InvalidInformationAcquisitionContractError(
                "expected_cost must be an InformationAcquisitionCost instance"
            )

        object.__setattr__(
            self, "reason_codes", tuple(str(rc) for rc in self.reason_codes)
        )
        object.__setattr__(self, "rejected_candidates", tuple(self.rejected_candidates))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "gap_id": self.gap_id,
            "decision": self.decision.value,
            "strategy": self.strategy.value,
            "reason_codes": list(self.reason_codes),
            "selected_candidate": (
                self.selected_candidate.serialize() if self.selected_candidate else None
            ),
            "rejected_candidates": [c.serialize() for c in self.rejected_candidates],
            "expected_cost": self.expected_cost.serialize(),
            "expected_confidence_gain": self.expected_confidence_gain,
            "requires_permission": self.requires_permission,
            "requires_approval": self.requires_approval,
            "requires_user_input": self.requires_user_input,
            "requires_resource": self.requires_resource,
            "blocked": self.blocked,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> InformationAcquisitionDecision:
        if not isinstance(mapping, Mapping):
            raise InvalidInformationAcquisitionContractError(
                "mapping must be a Mapping instance"
            )

        required_keys = {"id", "request_id", "gap_id", "decision", "strategy"}
        missing = required_keys - set(mapping.keys())
        if missing:
            raise InvalidInformationAcquisitionContractError(
                f"Missing required fields in mapping: {sorted(missing)}"
            )

        dec_val = mapping["decision"]
        if isinstance(dec_val, str):
            dec_val = InformationAcquisitionDecisionType(dec_val)

        strat_val = mapping["strategy"]
        if isinstance(strat_val, str):
            strat_val = InformationAcquisitionStrategy(strat_val)

        cost_val = mapping.get("expected_cost")
        if isinstance(cost_val, Mapping):
            cost_obj = InformationAcquisitionCost.from_mapping(cost_val)
        elif isinstance(cost_val, InformationAcquisitionCost):
            cost_obj = cost_val
        else:
            cost_obj = InformationAcquisitionCost()

        sel_cand_raw = mapping.get("selected_candidate")
        sel_cand = (
            InformationAcquisitionCandidate.from_mapping(sel_cand_raw)
            if isinstance(sel_cand_raw, Mapping)
            else (
                sel_cand_raw
                if isinstance(sel_cand_raw, InformationAcquisitionCandidate)
                else None
            )
        )

        rej_cands_raw = mapping.get("rejected_candidates", ())
        rej_cands = tuple(
            InformationAcquisitionCandidate.from_mapping(c)
            if isinstance(c, Mapping)
            else c
            for c in rej_cands_raw
        )

        return cls(
            id=str(mapping["id"]),
            request_id=str(mapping["request_id"]),
            gap_id=str(mapping["gap_id"]),
            decision=dec_val,
            strategy=strat_val,
            expected_cost=cost_obj,
            reason_codes=tuple(str(rc) for rc in mapping.get("reason_codes", ())),
            selected_candidate=sel_cand,
            rejected_candidates=rej_cands,
            expected_confidence_gain=float(
                mapping.get("expected_confidence_gain", 0.0)
            ),
            requires_permission=bool(mapping.get("requires_permission", False)),
            requires_approval=bool(mapping.get("requires_approval", False)),
            requires_user_input=bool(mapping.get("requires_user_input", False)),
            requires_resource=bool(mapping.get("requires_resource", False)),
            blocked=bool(mapping.get("blocked", False)),
            created_at=str(mapping.get("created_at", _now_iso())),
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> InformationAcquisitionDecision:
        return cls.from_mapping(mapping)


@dataclass(frozen=True, slots=True)
class InformationAcquisitionResult:
    """Complete structured outcome of an information acquisition resolution cycle."""

    request: InformationAcquisitionRequest
    context: InformationAcquisitionContext
    decision: InformationAcquisitionDecision
    candidates: tuple[InformationAcquisitionCandidate, ...] = ()
    status: InformationAcquisitionStatus = InformationAcquisitionStatus.COMPLETED
    warnings: tuple[InformationAcquisitionWarning, ...] = ()
    errors: tuple[str, ...] = ()
    confidence: float = 1.0
    created_at: str = field(default_factory=_now_iso)
    completed_at: str | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        if not isinstance(self.request, InformationAcquisitionRequest):
            raise InvalidInformationAcquisitionContractError(
                "request must be an InformationAcquisitionRequest instance"
            )
        if not isinstance(self.context, InformationAcquisitionContext):
            raise InvalidInformationAcquisitionContractError(
                "context must be an InformationAcquisitionContext instance"
            )
        if not isinstance(self.decision, InformationAcquisitionDecision):
            raise InvalidInformationAcquisitionContractError(
                "decision must be an InformationAcquisitionDecision instance"
            )

        _validate_bounded_float(self.confidence, "confidence")

        if isinstance(self.status, str):
            try:
                object.__setattr__(
                    self, "status", InformationAcquisitionStatus(self.status)
                )
            except ValueError:
                raise InvalidInformationAcquisitionContractError(
                    f"Unknown InformationAcquisitionStatus: {self.status}"
                )

        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "errors", tuple(str(e) for e in self.errors))
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def serialize(self) -> dict[str, Any]:
        return {
            "request": self.request.serialize(),
            "context": self.context.serialize(),
            "decision": self.decision.serialize(),
            "candidates": [c.serialize() for c in self.candidates],
            "status": self.status.value,
            "warnings": [w.serialize() for w in self.warnings],
            "errors": list(self.errors),
            "confidence": self.confidence,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any]) -> InformationAcquisitionResult:
        if not isinstance(mapping, Mapping):
            raise InvalidInformationAcquisitionContractError(
                "mapping must be a Mapping instance"
            )

        req_raw = mapping["request"]
        req_obj = (
            InformationAcquisitionRequest.from_mapping(req_raw)
            if isinstance(req_raw, Mapping)
            else req_raw
        )

        ctx_raw = mapping["context"]
        ctx_obj = (
            InformationAcquisitionContext.from_mapping(ctx_raw)
            if isinstance(ctx_raw, Mapping)
            else ctx_raw
        )

        dec_raw = mapping["decision"]
        dec_obj = (
            InformationAcquisitionDecision.from_mapping(dec_raw)
            if isinstance(dec_raw, Mapping)
            else dec_raw
        )

        cands_raw = mapping.get("candidates", ())
        cands_tuple = tuple(
            InformationAcquisitionCandidate.from_mapping(c)
            if isinstance(c, Mapping)
            else c
            for c in cands_raw
        )

        warns_raw = mapping.get("warnings", ())
        warns_tuple = tuple(
            InformationAcquisitionWarning.from_mapping(w)
            if isinstance(w, Mapping)
            else w
            for w in warns_raw
        )

        stat_val = mapping.get("status", InformationAcquisitionStatus.COMPLETED)
        if isinstance(stat_val, str):
            stat_val = InformationAcquisitionStatus(stat_val)

        return cls(
            request=req_obj,
            context=ctx_obj,
            decision=dec_obj,
            candidates=cands_tuple,
            status=stat_val,
            warnings=warns_tuple,
            errors=tuple(str(e) for e in mapping.get("errors", ())),
            confidence=float(mapping.get("confidence", 1.0)),
            created_at=str(mapping.get("created_at", _now_iso())),
            completed_at=mapping.get("completed_at"),
            metadata=mapping.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, mapping: Mapping[str, Any]) -> InformationAcquisitionResult:
        return cls.from_mapping(mapping)
