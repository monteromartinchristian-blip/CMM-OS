"""Phase 10.9 – Cross-Domain Engine Contracts.

Immutable, JSON-serializable, type-safe contracts for the Cross-Domain
Engine. All dataclasses are ``frozen=True``, use ``slots=True``, and never
expose mutable internal state.

No live registry access, no LLM calls, no network, no filesystem.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from cmm.domains.contracts import (
    _deep_freeze,
    _ensure_tz_aware,
    _freeze_str_tuple,
    _normalize_empty_to_none,
    _reject_unknown_fields,
    _validate_non_empty_str,
    _validate_strict_bool,
)
from cmm.domains.enums import CrossDomainSeverity, CrossDomainStage, CrossDomainStatus
from cmm.domains.errors import (
    CrossDomainContractError,
    CrossDomainSerializationError,
)
from cmm.domains.errors import DomainContractValidationError as _UpstreamContractError
from cmm.domains.errors import (
    DomainResolutionSerializationError as _UpstreamResolutionSerializationError,
)
from cmm.domains.errors import DomainSerializationError as _UpstreamSerializationError
from cmm.domains.identifiers import DomainId
from cmm.domains.resolver_contracts import (
    _coerce_domain_id,
    _deep_unfreeze_value,
    _freeze_domain_ids,
    _freeze_unique_str_tuple,
    _parse_datetime_opt,
    _reject_credential_keys_deep,
    _validate_confidence_opt,
    _validate_finite_float,
    _validate_json_safe,
    _validate_json_safe_metadata,
    _validate_non_negative_float,
)

# ── Error translation ───────────────────────────────────────────────────────
#
# The shared validation helpers above (reused from contracts.py and
# resolver_contracts.py) raise the *Domain*-level error hierarchy. Every
# Cross-Domain contract must raise Cross-Domain-level errors instead, so
# each reused helper is rebound to translate on the way out.


def _as_contract_error(fn):
    def _wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (
            _UpstreamContractError,
            _UpstreamSerializationError,
            _UpstreamResolutionSerializationError,
        ) as exc:
            raise CrossDomainContractError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc

    return _wrapped


def _as_serialization_error(fn):
    def _wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (
            _UpstreamContractError,
            _UpstreamSerializationError,
            _UpstreamResolutionSerializationError,
        ) as exc:
            raise CrossDomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc

    return _wrapped


_validate_non_empty_str = _as_contract_error(_validate_non_empty_str)
_validate_strict_bool = _as_contract_error(_validate_strict_bool)
_ensure_tz_aware = _as_contract_error(_ensure_tz_aware)
_freeze_str_tuple = _as_contract_error(_freeze_str_tuple)
_deep_freeze = _as_contract_error(_deep_freeze)
_coerce_domain_id = _as_contract_error(_coerce_domain_id)
_freeze_domain_ids = _as_contract_error(_freeze_domain_ids)
_freeze_unique_str_tuple = _as_contract_error(_freeze_unique_str_tuple)
_validate_confidence_opt = _as_contract_error(_validate_confidence_opt)
_validate_finite_float = _as_contract_error(_validate_finite_float)
_validate_non_negative_float = _as_contract_error(_validate_non_negative_float)
_validate_json_safe = _as_contract_error(_validate_json_safe)
_validate_json_safe_metadata = _as_contract_error(_validate_json_safe_metadata)
_reject_credential_keys_deep = _as_contract_error(_reject_credential_keys_deep)

_reject_unknown_fields = _as_serialization_error(_reject_unknown_fields)
_parse_datetime_opt = _as_serialization_error(_parse_datetime_opt)

# ── Local numeric helpers ──────────────────────────────────────────────────────


def _validate_non_negative_int(val: Any, field_name: str) -> int:
    """Validate a non-negative integer, rejecting bool."""
    if isinstance(val, bool):
        raise CrossDomainContractError(
            f"{field_name} must be an integer, not a boolean", field=field_name
        )
    if not isinstance(val, int):
        raise CrossDomainContractError(
            f"{field_name} must be an integer, got {type(val).__name__}: {val!r}",
            field=field_name,
        )
    if val < 0:
        raise CrossDomainContractError(
            f"{field_name} must be non-negative, got {val!r}", field=field_name
        )
    return val


def _validate_positive_int(val: Any, field_name: str) -> int:
    """Validate a strictly positive integer, rejecting bool."""
    n = _validate_non_negative_int(val, field_name)
    if n <= 0:
        raise CrossDomainContractError(
            f"{field_name} must be positive, got {n!r}", field=field_name
        )
    return n


def _validate_non_negative_cost_opt(val: Any, field_name: str) -> float | None:
    """Validate optional finite, non-negative cost."""
    if val is None:
        return None
    return _validate_non_negative_float(val, field_name)


def _validate_json_safe_value(value: Any, field_name: str) -> Any:
    """Validate a single JSON-safe value and deep-freeze it for storage."""
    if value is None:
        return None
    validated = _validate_json_safe(value, field_name)
    return _deep_freeze(validated)


def _coerce_severity(val: Any, field_name: str) -> CrossDomainSeverity:
    """Coerce a string or CrossDomainSeverity to CrossDomainSeverity."""
    if isinstance(val, CrossDomainSeverity):
        return val
    if isinstance(val, str):
        try:
            return CrossDomainSeverity(val)
        except ValueError as exc:
            raise CrossDomainContractError(
                f"Invalid CrossDomainSeverity: {val!r}", field=field_name
            ) from exc
    raise CrossDomainContractError(
        f"{field_name} must be a CrossDomainSeverity or string, got {type(val).__name__}",
        field=field_name,
    )


def _coerce_stage(val: Any, field_name: str) -> CrossDomainStage:
    """Coerce a string or CrossDomainStage to CrossDomainStage."""
    if isinstance(val, CrossDomainStage):
        return val
    if isinstance(val, str):
        try:
            return CrossDomainStage(val)
        except ValueError as exc:
            raise CrossDomainContractError(
                f"Invalid CrossDomainStage: {val!r}", field=field_name
            ) from exc
    raise CrossDomainContractError(
        f"{field_name} must be a CrossDomainStage or string, got {type(val).__name__}",
        field=field_name,
    )


def _coerce_status(val: Any, field_name: str) -> CrossDomainStatus:
    """Coerce a string or CrossDomainStatus to CrossDomainStatus."""
    if isinstance(val, CrossDomainStatus):
        return val
    if isinstance(val, str):
        try:
            return CrossDomainStatus(val)
        except ValueError as exc:
            raise CrossDomainContractError(
                f"Invalid CrossDomainStatus: {val!r}", field=field_name
            ) from exc
    raise CrossDomainContractError(
        f"{field_name} must be a CrossDomainStatus or string, got {type(val).__name__}",
        field=field_name,
    )


def _reject_non_terminal_status(status: CrossDomainStatus, field_name: str) -> None:
    """Reject PENDING/RUNNING wherever a final status is required."""
    if status in (CrossDomainStatus.PENDING, CrossDomainStatus.RUNNING):
        raise CrossDomainContractError(
            f"{field_name} must be a final status, got {status.value!r}",
            field=field_name,
        )


def _freeze_provenance(
    seq: Any, field_name: str, *, allow_empty: bool
) -> tuple[str, ...]:
    """Validate a provenance tuple: unique, non-empty strings, order preserved."""
    frozen = _freeze_str_tuple(seq, field_name, allow_empty=True, require_unique=True)
    if not allow_empty and len(frozen) == 0:
        raise CrossDomainContractError(
            f"{field_name} must not be empty", field=field_name
        )
    return frozen


# ── Known port names ─────────────────────────────────────────────────────────
#
# ``resolver`` and ``composer`` are mandatory constructor arguments of the
# engine and are therefore intentionally excluded — they can never be
# "required but missing" the way optional ports can.
KNOWN_CROSS_DOMAIN_PORTS: frozenset[str] = frozenset(
    {"knowledge", "planner", "cognitive", "agent", "workflow", "operation"}
)


# ── Nested-contract coercion helpers ────────────────────────────────────────


def _freeze_dependency_tuple(
    seq: Any, field_name: str
) -> tuple[CrossDomainDependency, ...]:
    """Coerce a sequence into a tuple of CrossDomainDependency instances."""
    if seq is None:
        return ()
    result: list[CrossDomainDependency] = []
    for i, item in enumerate(seq):
        if isinstance(item, CrossDomainDependency):
            result.append(item)
        elif isinstance(item, Mapping):
            result.append(CrossDomainDependency.from_dict(dict(item)))
        else:
            raise CrossDomainContractError(
                f"{field_name}[{i}] must be a CrossDomainDependency or mapping, "
                f"got {type(item).__name__}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


def _freeze_contradiction_tuple(
    seq: Any, field_name: str
) -> tuple[CrossDomainContradiction, ...]:
    """Coerce a sequence into a tuple of CrossDomainContradiction instances."""
    if seq is None:
        return ()
    result: list[CrossDomainContradiction] = []
    for i, item in enumerate(seq):
        if isinstance(item, CrossDomainContradiction):
            result.append(item)
        elif isinstance(item, Mapping):
            result.append(CrossDomainContradiction.from_dict(dict(item)))
        else:
            raise CrossDomainContractError(
                f"{field_name}[{i}] must be a CrossDomainContradiction or mapping, "
                f"got {type(item).__name__}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


def _freeze_gap_tuple(seq: Any, field_name: str) -> tuple[CrossDomainGap, ...]:
    """Coerce a sequence into a tuple of CrossDomainGap instances."""
    if seq is None:
        return ()
    result: list[CrossDomainGap] = []
    for i, item in enumerate(seq):
        if isinstance(item, CrossDomainGap):
            result.append(item)
        elif isinstance(item, Mapping):
            result.append(CrossDomainGap.from_dict(dict(item)))
        else:
            raise CrossDomainContractError(
                f"{field_name}[{i}] must be a CrossDomainGap or mapping, "
                f"got {type(item).__name__}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


def _freeze_question_tuple(
    seq: Any, field_name: str
) -> tuple[CrossDomainQuestion, ...]:
    """Coerce a sequence into a tuple of CrossDomainQuestion instances."""
    if seq is None:
        return ()
    result: list[CrossDomainQuestion] = []
    for i, item in enumerate(seq):
        if isinstance(item, CrossDomainQuestion):
            result.append(item)
        elif isinstance(item, Mapping):
            result.append(CrossDomainQuestion.from_dict(dict(item)))
        else:
            raise CrossDomainContractError(
                f"{field_name}[{i}] must be a CrossDomainQuestion or mapping, "
                f"got {type(item).__name__}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


def _freeze_decision_tuple(
    seq: Any, field_name: str
) -> tuple[CrossDomainDecision, ...]:
    """Coerce a sequence into a tuple of CrossDomainDecision instances."""
    if seq is None:
        return ()
    result: list[CrossDomainDecision] = []
    for i, item in enumerate(seq):
        if isinstance(item, CrossDomainDecision):
            result.append(item)
        elif isinstance(item, Mapping):
            result.append(CrossDomainDecision.from_dict(dict(item)))
        else:
            raise CrossDomainContractError(
                f"{field_name}[{i}] must be a CrossDomainDecision or mapping, "
                f"got {type(item).__name__}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


def _freeze_transfer_tuple(
    seq: Any, field_name: str
) -> tuple[CrossDomainContextTransfer, ...]:
    """Coerce a sequence into a tuple of CrossDomainContextTransfer instances."""
    if seq is None:
        return ()
    result: list[CrossDomainContextTransfer] = []
    for i, item in enumerate(seq):
        if isinstance(item, CrossDomainContextTransfer):
            result.append(item)
        elif isinstance(item, Mapping):
            result.append(CrossDomainContextTransfer.from_dict(dict(item)))
        else:
            raise CrossDomainContractError(
                f"{field_name}[{i}] must be a CrossDomainContextTransfer or mapping, "
                f"got {type(item).__name__}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


def _freeze_domain_result_tuple(
    seq: Any, field_name: str
) -> tuple[CrossDomainDomainResult, ...]:
    """Coerce a sequence into a tuple of CrossDomainDomainResult instances."""
    if seq is None:
        return ()
    result: list[CrossDomainDomainResult] = []
    for i, item in enumerate(seq):
        if isinstance(item, CrossDomainDomainResult):
            result.append(item)
        elif isinstance(item, Mapping):
            result.append(CrossDomainDomainResult.from_dict(dict(item)))
        else:
            raise CrossDomainContractError(
                f"{field_name}[{i}] must be a CrossDomainDomainResult or mapping, "
                f"got {type(item).__name__}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


def _freeze_finding_tuple(seq: Any, field_name: str) -> tuple[CrossDomainFinding, ...]:
    """Coerce a sequence into a tuple of CrossDomainFinding instances."""
    if seq is None:
        return ()
    result: list[CrossDomainFinding] = []
    for i, item in enumerate(seq):
        if isinstance(item, CrossDomainFinding):
            result.append(item)
        elif isinstance(item, Mapping):
            result.append(CrossDomainFinding.from_dict(dict(item)))
        else:
            raise CrossDomainContractError(
                f"{field_name}[{i}] must be a CrossDomainFinding or mapping, "
                f"got {type(item).__name__}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


# ═══════════════════════════════════════════════════════════════════════════════
# CrossDomainRequest
# ═══════════════════════════════════════════════════════════════════════════════

_REQUEST_KNOWN = frozenset(
    {
        "id",
        "objective",
        "primary_domain",
        "supporting_domains",
        "session_id",
        "resources",
        "constraints",
        "permissions",
        "maximum_domains",
        "maximum_domain_hops",
        "maximum_iterations",
        "maximum_questions",
        "maximum_operations",
        "maximum_external_calls",
        "maximum_cost",
        "maximum_duration_ms",
        "trace_id",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class CrossDomainRequest:
    """An immutable request to coordinate reasoning across multiple domains."""

    id: str
    objective: str
    primary_domain: DomainId
    supporting_domains: tuple[DomainId, ...] = ()
    session_id: str | None = None
    resources: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    maximum_domains: int = 8
    maximum_domain_hops: int = 4
    maximum_iterations: int = 8
    maximum_questions: int = 16
    maximum_operations: int = 16
    maximum_external_calls: int = 16
    maximum_cost: float | None = None
    maximum_duration_ms: int = 30_000
    trace_id: str | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self, "objective", _validate_non_empty_str(self.objective, "objective")
        )
        object.__setattr__(
            self,
            "primary_domain",
            _coerce_domain_id(self.primary_domain, "primary_domain"),
        )
        object.__setattr__(
            self,
            "supporting_domains",
            _freeze_domain_ids(self.supporting_domains, "supporting_domains"),
        )
        if self.primary_domain.slug in {d.slug for d in self.supporting_domains}:
            raise CrossDomainContractError(
                "primary_domain must not appear in supporting_domains",
                field="supporting_domains",
            )

        object.__setattr__(
            self, "session_id", _normalize_empty_to_none(self.session_id)
        )
        object.__setattr__(self, "trace_id", _normalize_empty_to_none(self.trace_id))

        for attr_name in ("resources", "constraints", "permissions"):
            object.__setattr__(
                self,
                attr_name,
                _freeze_str_tuple(
                    getattr(self, attr_name), attr_name, require_unique=True
                ),
            )

        for attr_name in (
            "maximum_domains",
            "maximum_domain_hops",
            "maximum_iterations",
            "maximum_questions",
            "maximum_operations",
            "maximum_external_calls",
            "maximum_duration_ms",
        ):
            object.__setattr__(
                self,
                attr_name,
                _validate_positive_int(getattr(self, attr_name), attr_name),
            )

        object.__setattr__(
            self,
            "maximum_cost",
            _validate_non_negative_cost_opt(self.maximum_cost, "maximum_cost"),
        )

        total_domains = 1 + len(self.supporting_domains)
        if total_domains > self.maximum_domains:
            raise CrossDomainContractError(
                f"Total domains ({total_domains}) exceeds maximum_domains "
                f"({self.maximum_domains})",
                field="supporting_domains",
            )

        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        _reject_credential_keys_deep(self.metadata, "metadata")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "objective": self.objective,
            "primary_domain": str(self.primary_domain),
            "supporting_domains": [str(d) for d in self.supporting_domains],
            "session_id": self.session_id,
            "resources": list(self.resources),
            "constraints": list(self.constraints),
            "permissions": list(self.permissions),
            "maximum_domains": self.maximum_domains,
            "maximum_domain_hops": self.maximum_domain_hops,
            "maximum_iterations": self.maximum_iterations,
            "maximum_questions": self.maximum_questions,
            "maximum_operations": self.maximum_operations,
            "maximum_external_calls": self.maximum_external_calls,
            "maximum_cost": self.maximum_cost,
            "maximum_duration_ms": self.maximum_duration_ms,
            "trace_id": self.trace_id,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrossDomainRequest:
        """Deserialize from dictionary. Raw values flow into strict constructor checks."""
        if not isinstance(data, Mapping):
            raise CrossDomainSerializationError(
                "CrossDomainRequest.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _REQUEST_KNOWN, "CrossDomainRequest")
        required = {"id", "objective", "primary_domain"}
        missing = required - set(data.keys())
        if missing:
            raise CrossDomainSerializationError(
                f"CrossDomainRequest.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        kwargs: dict[str, Any] = {
            "id": data["id"],
            "objective": data["objective"],
            "primary_domain": data["primary_domain"],
            "supporting_domains": tuple(data.get("supporting_domains", ())),
            "session_id": data.get("session_id"),
            "resources": tuple(data.get("resources", ())),
            "constraints": tuple(data.get("constraints", ())),
            "permissions": tuple(data.get("permissions", ())),
            "trace_id": data.get("trace_id"),
            "metadata": data.get("metadata"),
        }
        for k in (
            "maximum_domains",
            "maximum_domain_hops",
            "maximum_iterations",
            "maximum_questions",
            "maximum_operations",
            "maximum_external_calls",
            "maximum_cost",
            "maximum_duration_ms",
        ):
            if k in data:
                kwargs[k] = data[k]
        try:
            return cls(**kwargs)
        except CrossDomainContractError as exc:
            raise CrossDomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# CrossDomainPolicy
# ═══════════════════════════════════════════════════════════════════════════════

_POLICY_KNOWN = frozenset(
    {
        "required_ports",
        "stop_on_blocking_contradiction",
        "stop_on_blocking_gap",
        "continue_independent_domains",
        "require_review_for_high_severity",
        "allow_declarative_parallel_groups",
        "question_deduplication_enabled",
        "maximum_parallel_group_size",
        "contradiction_penalty",
        "gap_penalty",
        "skipped_required_domain_penalty",
        "unavailable_required_port_penalty",
        "limit_reached_penalty",
        "metadata",
    }
)


def _validate_penalty(val: Any, field_name: str) -> float:
    """Validate a finite penalty in [0, 1]."""
    f = _validate_finite_float(val, field_name)
    if not (0.0 <= f <= 1.0):
        raise CrossDomainContractError(
            f"{field_name} must be between 0.0 and 1.0, got {f!r}", field=field_name
        )
    return f


@dataclass(frozen=True, slots=True)
class CrossDomainPolicy:
    """Immutable configuration governing Cross-Domain Engine coordination."""

    required_ports: tuple[str, ...] = ()
    stop_on_blocking_contradiction: bool = True
    stop_on_blocking_gap: bool = True
    continue_independent_domains: bool = True
    require_review_for_high_severity: bool = True
    allow_declarative_parallel_groups: bool = True
    question_deduplication_enabled: bool = True
    maximum_parallel_group_size: int = 4
    contradiction_penalty: float = 0.15
    gap_penalty: float = 0.15
    skipped_required_domain_penalty: float = 0.20
    unavailable_required_port_penalty: float = 0.20
    limit_reached_penalty: float = 0.10
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "required_ports",
            _freeze_str_tuple(
                self.required_ports, "required_ports", require_unique=True
            ),
        )
        unknown_ports = set(self.required_ports) - KNOWN_CROSS_DOMAIN_PORTS
        if unknown_ports:
            raise CrossDomainContractError(
                f"required_ports contains unknown port names: {sorted(unknown_ports)}",
                field="required_ports",
                details={"unknown": sorted(unknown_ports)},
            )
        for attr_name in (
            "stop_on_blocking_contradiction",
            "stop_on_blocking_gap",
            "continue_independent_domains",
            "require_review_for_high_severity",
            "allow_declarative_parallel_groups",
            "question_deduplication_enabled",
        ):
            object.__setattr__(
                self,
                attr_name,
                _validate_strict_bool(getattr(self, attr_name), attr_name),
            )
        object.__setattr__(
            self,
            "maximum_parallel_group_size",
            _validate_positive_int(
                self.maximum_parallel_group_size, "maximum_parallel_group_size"
            ),
        )
        for attr_name in (
            "contradiction_penalty",
            "gap_penalty",
            "skipped_required_domain_penalty",
            "unavailable_required_port_penalty",
            "limit_reached_penalty",
        ):
            object.__setattr__(
                self, attr_name, _validate_penalty(getattr(self, attr_name), attr_name)
            )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        _reject_credential_keys_deep(self.metadata, "metadata")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "required_ports": list(self.required_ports),
            "stop_on_blocking_contradiction": self.stop_on_blocking_contradiction,
            "stop_on_blocking_gap": self.stop_on_blocking_gap,
            "continue_independent_domains": self.continue_independent_domains,
            "require_review_for_high_severity": self.require_review_for_high_severity,
            "allow_declarative_parallel_groups": self.allow_declarative_parallel_groups,
            "question_deduplication_enabled": self.question_deduplication_enabled,
            "maximum_parallel_group_size": self.maximum_parallel_group_size,
            "contradiction_penalty": self.contradiction_penalty,
            "gap_penalty": self.gap_penalty,
            "skipped_required_domain_penalty": self.skipped_required_domain_penalty,
            "unavailable_required_port_penalty": self.unavailable_required_port_penalty,
            "limit_reached_penalty": self.limit_reached_penalty,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrossDomainPolicy:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise CrossDomainSerializationError(
                "CrossDomainPolicy.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _POLICY_KNOWN, "CrossDomainPolicy")
        try:
            return cls(**{k: data[k] for k in _POLICY_KNOWN if k in data})
        except CrossDomainContractError as exc:
            raise CrossDomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# CrossDomainQuestion
# ═══════════════════════════════════════════════════════════════════════════════

_QUESTION_KNOWN = frozenset(
    {
        "id",
        "subject",
        "requested_information",
        "target_entity",
        "time_scope",
        "requesting_domains",
        "answered",
        "answer",
        "provenance",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class CrossDomainQuestion:
    """A cross-domain question with structural identity.

    Identity is exactly the tuple (subject, requested_information,
    target_entity, time_scope). No fuzzy or semantic matching is used.
    """

    id: str
    subject: str
    requested_information: str
    target_entity: str | None = None
    time_scope: str | None = None
    requesting_domains: tuple[DomainId, ...] = ()
    answered: bool = False
    answer: str | None = None
    provenance: tuple[str, ...] = ()
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self, "subject", _validate_non_empty_str(self.subject, "subject")
        )
        object.__setattr__(
            self,
            "requested_information",
            _validate_non_empty_str(
                self.requested_information, "requested_information"
            ),
        )
        object.__setattr__(
            self, "target_entity", _normalize_empty_to_none(self.target_entity)
        )
        object.__setattr__(
            self, "time_scope", _normalize_empty_to_none(self.time_scope)
        )
        object.__setattr__(
            self,
            "requesting_domains",
            _freeze_domain_ids(self.requesting_domains, "requesting_domains"),
        )
        object.__setattr__(
            self, "answered", _validate_strict_bool(self.answered, "answered")
        )
        object.__setattr__(self, "answer", _normalize_empty_to_none(self.answer))
        if self.answered and self.answer is None:
            raise CrossDomainContractError(
                "answered=True requires a non-empty answer", field="answer"
            )
        if not self.answered and self.answer is not None:
            raise CrossDomainContractError(
                "answer must be None when answered=False", field="answer"
            )
        object.__setattr__(
            self,
            "provenance",
            _freeze_provenance(self.provenance, "provenance", allow_empty=False),
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        _reject_credential_keys_deep(self.metadata, "metadata")

    def identity_key(self) -> tuple[str, str, str | None, str | None]:
        """The structural identity key used for exact deduplication."""
        return (
            self.subject,
            self.requested_information,
            self.target_entity,
            self.time_scope,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "subject": self.subject,
            "requested_information": self.requested_information,
            "target_entity": self.target_entity,
            "time_scope": self.time_scope,
            "requesting_domains": [str(d) for d in self.requesting_domains],
            "answered": self.answered,
            "answer": self.answer,
            "provenance": list(self.provenance),
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrossDomainQuestion:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise CrossDomainSerializationError(
                "CrossDomainQuestion.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _QUESTION_KNOWN, "CrossDomainQuestion")
        required = {"id", "subject", "requested_information", "provenance"}
        missing = required - set(data.keys())
        if missing:
            raise CrossDomainSerializationError(
                f"CrossDomainQuestion.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                id=data["id"],
                subject=data["subject"],
                requested_information=data["requested_information"],
                target_entity=data.get("target_entity"),
                time_scope=data.get("time_scope"),
                requesting_domains=tuple(data.get("requesting_domains", ())),
                answered=data.get("answered", False),
                answer=data.get("answer"),
                provenance=tuple(data["provenance"]),
                metadata=data.get("metadata"),
            )
        except CrossDomainContractError as exc:
            raise CrossDomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# CrossDomainFinding
# ═══════════════════════════════════════════════════════════════════════════════

_FINDING_KNOWN = frozenset(
    {
        "identifier",
        "value",
        "source_domains",
        "provenance",
        "private",
        "transferable",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class CrossDomainFinding:
    """A single finding with explicit source domains and provenance.

    Findings are never bare strings: every finding carries the domain(s)
    that produced it and the provenance chain that justifies it, so
    transfers can never fabricate or borrow provenance from elsewhere.
    """

    identifier: str
    value: Any
    source_domains: tuple[DomainId, ...]
    provenance: tuple[str, ...]
    private: bool = False
    transferable: bool = True
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "identifier", _validate_non_empty_str(self.identifier, "identifier")
        )
        object.__setattr__(
            self, "value", _validate_json_safe_value(self.value, "value")
        )
        object.__setattr__(
            self,
            "source_domains",
            _freeze_domain_ids(
                self.source_domains, "source_domains", require_unique=True
            ),
        )
        if len(self.source_domains) == 0:
            raise CrossDomainContractError(
                "source_domains must not be empty", field="source_domains"
            )
        object.__setattr__(
            self,
            "provenance",
            _freeze_provenance(self.provenance, "provenance", allow_empty=False),
        )
        object.__setattr__(
            self, "private", _validate_strict_bool(self.private, "private")
        )
        object.__setattr__(
            self,
            "transferable",
            _validate_strict_bool(self.transferable, "transferable"),
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        _reject_credential_keys_deep(self.metadata, "metadata")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "identifier": self.identifier,
            "value": _deep_unfreeze_value(self.value),
            "source_domains": [str(d) for d in self.source_domains],
            "provenance": list(self.provenance),
            "private": self.private,
            "transferable": self.transferable,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrossDomainFinding:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise CrossDomainSerializationError(
                "CrossDomainFinding.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _FINDING_KNOWN, "CrossDomainFinding")
        required = {"identifier", "value", "source_domains", "provenance"}
        missing = required - set(data.keys())
        if missing:
            raise CrossDomainSerializationError(
                f"CrossDomainFinding.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                identifier=data["identifier"],
                value=data["value"],
                source_domains=tuple(data["source_domains"]),
                provenance=tuple(data["provenance"]),
                private=data.get("private", False),
                transferable=data.get("transferable", True),
                metadata=data.get("metadata"),
            )
        except CrossDomainContractError as exc:
            raise CrossDomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# CrossDomainContextTransfer
# ═══════════════════════════════════════════════════════════════════════════════

_TRANSFER_KNOWN = frozenset(
    {
        "source_domain",
        "target_domain",
        "kind",
        "identifier",
        "value",
        "reason",
        "iteration",
        "provenance",
        "private",
        "transferable",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class CrossDomainContextTransfer:
    """A single unit of context transferred from one domain to another."""

    source_domain: DomainId
    target_domain: DomainId
    kind: str
    identifier: str
    value: Any
    reason: str
    iteration: int = 0
    provenance: tuple[str, ...] = ()
    private: bool = False
    transferable: bool = True
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_domain",
            _coerce_domain_id(self.source_domain, "source_domain"),
        )
        object.__setattr__(
            self,
            "target_domain",
            _coerce_domain_id(self.target_domain, "target_domain"),
        )
        if self.source_domain.slug == self.target_domain.slug:
            raise CrossDomainContractError(
                "source_domain and target_domain must differ", field="target_domain"
            )
        object.__setattr__(self, "kind", _validate_non_empty_str(self.kind, "kind"))
        object.__setattr__(
            self, "identifier", _validate_non_empty_str(self.identifier, "identifier")
        )
        object.__setattr__(
            self, "value", _validate_json_safe_value(self.value, "value")
        )
        object.__setattr__(
            self, "reason", _validate_non_empty_str(self.reason, "reason")
        )
        object.__setattr__(
            self, "iteration", _validate_non_negative_int(self.iteration, "iteration")
        )
        object.__setattr__(
            self,
            "provenance",
            _freeze_provenance(self.provenance, "provenance", allow_empty=False),
        )
        object.__setattr__(
            self, "private", _validate_strict_bool(self.private, "private")
        )
        object.__setattr__(
            self,
            "transferable",
            _validate_strict_bool(self.transferable, "transferable"),
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        _reject_credential_keys_deep(self.metadata, "metadata")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "source_domain": str(self.source_domain),
            "target_domain": str(self.target_domain),
            "kind": self.kind,
            "identifier": self.identifier,
            "value": _deep_unfreeze_value(self.value),
            "reason": self.reason,
            "iteration": self.iteration,
            "provenance": list(self.provenance),
            "private": self.private,
            "transferable": self.transferable,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrossDomainContextTransfer:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise CrossDomainSerializationError(
                "CrossDomainContextTransfer.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _TRANSFER_KNOWN, "CrossDomainContextTransfer")
        required = {
            "source_domain",
            "target_domain",
            "kind",
            "identifier",
            "value",
            "reason",
            "provenance",
        }
        missing = required - set(data.keys())
        if missing:
            raise CrossDomainSerializationError(
                f"CrossDomainContextTransfer.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                source_domain=data["source_domain"],
                target_domain=data["target_domain"],
                kind=data["kind"],
                identifier=data["identifier"],
                value=data["value"],
                reason=data["reason"],
                iteration=data.get("iteration", 0),
                provenance=tuple(data["provenance"]),
                private=data.get("private", False),
                transferable=data.get("transferable", True),
                metadata=data.get("metadata"),
            )
        except CrossDomainContractError as exc:
            raise CrossDomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# CrossDomainDependency
# ═══════════════════════════════════════════════════════════════════════════════

_DEPENDENCY_KNOWN = frozenset(
    {
        "source_domain",
        "target_domain",
        "kind",
        "description",
        "blocking",
        "satisfied",
        "provenance",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class CrossDomainDependency:
    """A structural dependency from one domain's work to another's."""

    source_domain: DomainId
    target_domain: DomainId
    kind: str
    description: str
    blocking: bool = False
    satisfied: bool = False
    provenance: tuple[str, ...] = ()
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_domain",
            _coerce_domain_id(self.source_domain, "source_domain"),
        )
        object.__setattr__(
            self,
            "target_domain",
            _coerce_domain_id(self.target_domain, "target_domain"),
        )
        if self.source_domain.slug == self.target_domain.slug:
            raise CrossDomainContractError(
                "source_domain and target_domain must differ", field="target_domain"
            )
        object.__setattr__(self, "kind", _validate_non_empty_str(self.kind, "kind"))
        object.__setattr__(
            self,
            "description",
            _validate_non_empty_str(self.description, "description"),
        )
        object.__setattr__(
            self, "blocking", _validate_strict_bool(self.blocking, "blocking")
        )
        object.__setattr__(
            self, "satisfied", _validate_strict_bool(self.satisfied, "satisfied")
        )
        object.__setattr__(
            self,
            "provenance",
            _freeze_provenance(self.provenance, "provenance", allow_empty=False),
        )
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def identity_key(self) -> tuple[str, str, str, str, bool]:
        """Structural identity key used for aggregation (provenance excluded)."""
        return (
            self.source_domain.slug,
            self.target_domain.slug,
            self.kind,
            self.description,
            self.blocking,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "source_domain": str(self.source_domain),
            "target_domain": str(self.target_domain),
            "kind": self.kind,
            "description": self.description,
            "blocking": self.blocking,
            "satisfied": self.satisfied,
            "provenance": list(self.provenance),
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrossDomainDependency:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise CrossDomainSerializationError(
                "CrossDomainDependency.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _DEPENDENCY_KNOWN, "CrossDomainDependency")
        required = {
            "source_domain",
            "target_domain",
            "kind",
            "description",
            "provenance",
        }
        missing = required - set(data.keys())
        if missing:
            raise CrossDomainSerializationError(
                f"CrossDomainDependency.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                source_domain=data["source_domain"],
                target_domain=data["target_domain"],
                kind=data["kind"],
                description=data["description"],
                blocking=data.get("blocking", False),
                satisfied=data.get("satisfied", False),
                provenance=tuple(data["provenance"]),
                metadata=data.get("metadata"),
            )
        except CrossDomainContractError as exc:
            raise CrossDomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# CrossDomainContradiction
# ═══════════════════════════════════════════════════════════════════════════════

_CONTRADICTION_KNOWN = frozenset(
    {
        "id",
        "domains",
        "subject",
        "statements",
        "severity",
        "resolved",
        "resolution",
        "requires_review",
        "provenance",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class CrossDomainContradiction:
    """A contradiction detected across two or more domains."""

    id: str
    domains: tuple[DomainId, ...]
    subject: str
    statements: tuple[str, ...]
    severity: CrossDomainSeverity
    resolved: bool = False
    resolution: str | None = None
    requires_review: bool = False
    provenance: tuple[str, ...] = ()
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self,
            "domains",
            _freeze_domain_ids(self.domains, "domains", require_unique=True),
        )
        if len(self.domains) < 2:
            raise CrossDomainContractError(
                "A contradiction requires at least two unique domains", field="domains"
            )
        object.__setattr__(
            self, "subject", _validate_non_empty_str(self.subject, "subject")
        )
        object.__setattr__(
            self,
            "statements",
            _freeze_str_tuple(self.statements, "statements", allow_empty=False),
        )
        if len(self.statements) == 0:
            raise CrossDomainContractError(
                "statements must not be empty", field="statements"
            )
        object.__setattr__(
            self, "severity", _coerce_severity(self.severity, "severity")
        )
        object.__setattr__(
            self, "resolved", _validate_strict_bool(self.resolved, "resolved")
        )
        object.__setattr__(
            self, "resolution", _normalize_empty_to_none(self.resolution)
        )
        if not self.resolved and self.resolution is not None:
            raise CrossDomainContractError(
                "Unresolved contradiction must not have a resolution",
                field="resolution",
            )
        object.__setattr__(
            self,
            "requires_review",
            _validate_strict_bool(self.requires_review, "requires_review"),
        )
        object.__setattr__(
            self,
            "provenance",
            _freeze_provenance(self.provenance, "provenance", allow_empty=False),
        )
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def identity_key(self) -> tuple[tuple[str, ...], str, tuple[str, ...], str, bool]:
        """Minimal key used to collapse exact duplicates while preserving provenance."""
        return (
            tuple(sorted(d.slug for d in self.domains)),
            self.subject,
            self.statements,
            self.severity.value,
            self.requires_review,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "domains": [str(d) for d in self.domains],
            "subject": self.subject,
            "statements": list(self.statements),
            "severity": self.severity.value,
            "resolved": self.resolved,
            "resolution": self.resolution,
            "requires_review": self.requires_review,
            "provenance": list(self.provenance),
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrossDomainContradiction:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise CrossDomainSerializationError(
                "CrossDomainContradiction.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _CONTRADICTION_KNOWN, "CrossDomainContradiction")
        required = {"id", "domains", "subject", "statements", "severity", "provenance"}
        missing = required - set(data.keys())
        if missing:
            raise CrossDomainSerializationError(
                f"CrossDomainContradiction.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                id=data["id"],
                domains=tuple(data["domains"]),
                subject=data["subject"],
                statements=tuple(data["statements"]),
                severity=data["severity"],
                resolved=data.get("resolved", False),
                resolution=data.get("resolution"),
                requires_review=data.get("requires_review", False),
                provenance=tuple(data["provenance"]),
                metadata=data.get("metadata"),
            )
        except CrossDomainContractError as exc:
            raise CrossDomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# CrossDomainGap
# ═══════════════════════════════════════════════════════════════════════════════

_GAP_KNOWN = frozenset(
    {
        "code",
        "domain_id",
        "description",
        "required_information",
        "blocking",
        "recoverable",
        "provenance",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class CrossDomainGap:
    """A missing piece of information detected during cross-domain coordination."""

    code: str
    domain_id: DomainId
    description: str
    required_information: tuple[str, ...] = ()
    blocking: bool = False
    recoverable: bool = True
    provenance: tuple[str, ...] = ()
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _validate_non_empty_str(self.code, "code"))
        object.__setattr__(
            self, "domain_id", _coerce_domain_id(self.domain_id, "domain_id")
        )
        object.__setattr__(
            self,
            "description",
            _validate_non_empty_str(self.description, "description"),
        )
        object.__setattr__(
            self,
            "required_information",
            _freeze_str_tuple(self.required_information, "required_information"),
        )
        object.__setattr__(
            self, "blocking", _validate_strict_bool(self.blocking, "blocking")
        )
        object.__setattr__(
            self, "recoverable", _validate_strict_bool(self.recoverable, "recoverable")
        )
        object.__setattr__(
            self,
            "provenance",
            _freeze_provenance(self.provenance, "provenance", allow_empty=True),
        )
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def identity_key(self) -> tuple[str, str, str, tuple[str, ...], bool, bool]:
        """Structural identity key used for aggregation (provenance excluded)."""
        return (
            self.code,
            self.domain_id.slug,
            self.description,
            self.required_information,
            self.blocking,
            self.recoverable,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "code": self.code,
            "domain_id": str(self.domain_id),
            "description": self.description,
            "required_information": list(self.required_information),
            "blocking": self.blocking,
            "recoverable": self.recoverable,
            "provenance": list(self.provenance),
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrossDomainGap:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise CrossDomainSerializationError(
                "CrossDomainGap.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _GAP_KNOWN, "CrossDomainGap")
        required = {"code", "domain_id", "description"}
        missing = required - set(data.keys())
        if missing:
            raise CrossDomainSerializationError(
                f"CrossDomainGap.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                code=data["code"],
                domain_id=data["domain_id"],
                description=data["description"],
                required_information=tuple(data.get("required_information", ())),
                blocking=data.get("blocking", False),
                recoverable=data.get("recoverable", True),
                provenance=tuple(data.get("provenance", ())),
                metadata=data.get("metadata"),
            )
        except CrossDomainContractError as exc:
            raise CrossDomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# CrossDomainDecision
# ═══════════════════════════════════════════════════════════════════════════════

_DECISION_KNOWN = frozenset(
    {
        "code",
        "stage",
        "domain_id",
        "action",
        "reason",
        "blocking",
        "iteration",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class CrossDomainDecision:
    """A single decision made during cross-domain coordination."""

    code: str
    stage: CrossDomainStage
    domain_id: DomainId | None
    action: str
    reason: str | None = None
    blocking: bool = False
    iteration: int = 0
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _validate_non_empty_str(self.code, "code"))
        object.__setattr__(self, "stage", _coerce_stage(self.stage, "stage"))
        if self.domain_id is not None:
            object.__setattr__(
                self, "domain_id", _coerce_domain_id(self.domain_id, "domain_id")
            )
        object.__setattr__(
            self, "action", _validate_non_empty_str(self.action, "action")
        )
        object.__setattr__(self, "reason", _normalize_empty_to_none(self.reason))
        object.__setattr__(
            self, "blocking", _validate_strict_bool(self.blocking, "blocking")
        )
        object.__setattr__(
            self, "iteration", _validate_non_negative_int(self.iteration, "iteration")
        )
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "code": self.code,
            "stage": self.stage.value,
            "domain_id": str(self.domain_id) if self.domain_id else None,
            "action": self.action,
            "reason": self.reason,
            "blocking": self.blocking,
            "iteration": self.iteration,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrossDomainDecision:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise CrossDomainSerializationError(
                "CrossDomainDecision.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _DECISION_KNOWN, "CrossDomainDecision")
        required = {"code", "stage", "action"}
        missing = required - set(data.keys())
        if missing:
            raise CrossDomainSerializationError(
                f"CrossDomainDecision.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                code=data["code"],
                stage=data["stage"],
                domain_id=data.get("domain_id"),
                action=data["action"],
                reason=data.get("reason"),
                blocking=data.get("blocking", False),
                iteration=data.get("iteration", 0),
                metadata=data.get("metadata"),
            )
        except CrossDomainContractError as exc:
            raise CrossDomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# CrossDomainDomainResult
# ═══════════════════════════════════════════════════════════════════════════════

_DOMAIN_RESULT_KNOWN = frozenset(
    {
        "domain_id",
        "status",
        "findings",
        "questions",
        "dependencies",
        "contradictions",
        "gaps",
        "recommendations",
        "operations",
        "workflow_requests",
        "entities",
        "timelines",
        "confidence",
        "external_calls_used",
        "estimated_cost",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class CrossDomainDomainResult:
    """The per-domain contribution produced during cross-domain coordination.

    Partial findings remain valid even when ``status`` is ``BLOCKED`` or
    ``FAILED``. ``operations`` and ``workflow_requests`` are declarative
    identifiers only — never runtime-executable objects.
    """

    domain_id: DomainId
    status: CrossDomainStatus
    findings: tuple[CrossDomainFinding, ...] = ()
    questions: tuple[CrossDomainQuestion, ...] = ()
    dependencies: tuple[CrossDomainDependency, ...] = ()
    contradictions: tuple[CrossDomainContradiction, ...] = ()
    gaps: tuple[CrossDomainGap, ...] = ()
    recommendations: tuple[str, ...] = ()
    operations: tuple[str, ...] = ()
    workflow_requests: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()
    timelines: tuple[str, ...] = ()
    confidence: float | None = None
    external_calls_used: int = 0
    estimated_cost: float | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "domain_id", _coerce_domain_id(self.domain_id, "domain_id")
        )
        object.__setattr__(self, "status", _coerce_status(self.status, "status"))
        _reject_non_terminal_status(self.status, "status")
        object.__setattr__(
            self, "findings", _freeze_finding_tuple(self.findings, "findings")
        )
        object.__setattr__(
            self, "questions", _freeze_question_tuple(self.questions, "questions")
        )
        object.__setattr__(
            self,
            "dependencies",
            _freeze_dependency_tuple(self.dependencies, "dependencies"),
        )
        object.__setattr__(
            self,
            "contradictions",
            _freeze_contradiction_tuple(self.contradictions, "contradictions"),
        )
        object.__setattr__(self, "gaps", _freeze_gap_tuple(self.gaps, "gaps"))
        object.__setattr__(
            self,
            "recommendations",
            _freeze_str_tuple(self.recommendations, "recommendations"),
        )
        object.__setattr__(
            self, "operations", _freeze_str_tuple(self.operations, "operations")
        )
        object.__setattr__(
            self,
            "workflow_requests",
            _freeze_str_tuple(self.workflow_requests, "workflow_requests"),
        )
        object.__setattr__(
            self, "entities", _freeze_str_tuple(self.entities, "entities")
        )
        object.__setattr__(
            self, "timelines", _freeze_str_tuple(self.timelines, "timelines")
        )
        object.__setattr__(
            self, "confidence", _validate_confidence_opt(self.confidence, "confidence")
        )
        object.__setattr__(
            self,
            "external_calls_used",
            _validate_non_negative_int(self.external_calls_used, "external_calls_used"),
        )
        object.__setattr__(
            self,
            "estimated_cost",
            _validate_non_negative_cost_opt(self.estimated_cost, "estimated_cost"),
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        _reject_credential_keys_deep(self.metadata, "metadata")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "domain_id": str(self.domain_id),
            "status": self.status.value,
            "findings": [f.to_dict() for f in self.findings],
            "questions": [q.to_dict() for q in self.questions],
            "dependencies": [d.to_dict() for d in self.dependencies],
            "contradictions": [c.to_dict() for c in self.contradictions],
            "gaps": [g.to_dict() for g in self.gaps],
            "recommendations": list(self.recommendations),
            "operations": list(self.operations),
            "workflow_requests": list(self.workflow_requests),
            "entities": list(self.entities),
            "timelines": list(self.timelines),
            "confidence": self.confidence,
            "external_calls_used": self.external_calls_used,
            "estimated_cost": self.estimated_cost,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrossDomainDomainResult:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise CrossDomainSerializationError(
                "CrossDomainDomainResult.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _DOMAIN_RESULT_KNOWN, "CrossDomainDomainResult")
        required = {"domain_id", "status"}
        missing = required - set(data.keys())
        if missing:
            raise CrossDomainSerializationError(
                f"CrossDomainDomainResult.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                domain_id=data["domain_id"],
                status=data["status"],
                findings=tuple(data.get("findings", ())),
                questions=tuple(data.get("questions", ())),
                dependencies=tuple(data.get("dependencies", ())),
                contradictions=tuple(data.get("contradictions", ())),
                gaps=tuple(data.get("gaps", ())),
                recommendations=tuple(data.get("recommendations", ())),
                operations=tuple(data.get("operations", ())),
                workflow_requests=tuple(data.get("workflow_requests", ())),
                entities=tuple(data.get("entities", ())),
                timelines=tuple(data.get("timelines", ())),
                confidence=data.get("confidence"),
                external_calls_used=data.get("external_calls_used", 0),
                estimated_cost=data.get("estimated_cost"),
                metadata=data.get("metadata"),
            )
        except CrossDomainContractError as exc:
            raise CrossDomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# CrossDomainPlanResult
# ═══════════════════════════════════════════════════════════════════════════════

_PLAN_RESULT_KNOWN = frozenset(
    {
        "status",
        "domain_order",
        "parallel_groups",
        "dependencies",
        "required_ports",
        "operation_requests",
        "workflow_requests",
        "domain_modes",
        "decisions",
        "external_calls_used",
        "estimated_cost",
        "metadata",
    }
)

_DOMAIN_MODES: frozenset[str] = frozenset({"cognitive", "agent"})


def _freeze_parallel_groups(
    seq: Any, field_name: str, domain_order: tuple[DomainId, ...]
) -> tuple[tuple[DomainId, ...], ...]:
    """Validate declarative parallel groups: only known domains, unique within group."""
    if seq is None:
        return ()
    order_slugs = {d.slug for d in domain_order}
    result: list[tuple[DomainId, ...]] = []
    for i, group in enumerate(seq):
        group_ids = tuple(_coerce_domain_id(g, f"{field_name}[{i}]") for g in group)
        slugs = [g.slug for g in group_ids]
        if len(set(slugs)) != len(slugs):
            raise CrossDomainContractError(
                f"{field_name}[{i}] contains duplicate domains", field=field_name
            )
        for slug in slugs:
            if slug not in order_slugs:
                raise CrossDomainContractError(
                    f"{field_name}[{i}] references domain {slug!r} not present in domain_order",
                    field=field_name,
                )
        result.append(group_ids)
    return tuple(result)


def _freeze_domain_modes(
    val: Any, field_name: str, domain_order: tuple[DomainId, ...]
) -> MappingProxyType[str, str]:
    """Validate a per-domain execution-mode mapping."""
    if val is None:
        return MappingProxyType({})
    if not isinstance(val, Mapping):
        raise CrossDomainContractError(
            f"{field_name} must be a mapping", field=field_name
        )
    order_slugs = {d.slug for d in domain_order}
    result: dict[str, str] = {}
    for raw_key, raw_mode in val.items():
        domain_id = _coerce_domain_id(raw_key, field_name)
        if domain_id.slug not in order_slugs:
            raise CrossDomainContractError(
                f"{field_name} references domain {domain_id.slug!r} not present in domain_order",
                field=field_name,
            )
        if not isinstance(raw_mode, str) or raw_mode not in _DOMAIN_MODES:
            raise CrossDomainContractError(
                f"{field_name}[{domain_id.slug}] must be one of {sorted(_DOMAIN_MODES)}, "
                f"got {raw_mode!r}",
                field=field_name,
            )
        result[str(domain_id)] = raw_mode
    return MappingProxyType(result)


@dataclass(frozen=True, slots=True)
class CrossDomainPlanResult:
    """A declarative coordination plan produced by the Planner port.

    Parallel groups are declarative only — the engine never executes them
    concurrently in Phase 10.9. ``domain_modes`` declares, per domain,
    whether the Cognitive or Agent port must be used; a domain absent from
    ``domain_modes`` defaults to Cognitive when available.
    """

    status: CrossDomainStatus
    domain_order: tuple[DomainId, ...] = ()
    parallel_groups: tuple[tuple[DomainId, ...], ...] = ()
    dependencies: tuple[CrossDomainDependency, ...] = ()
    required_ports: tuple[str, ...] = ()
    operation_requests: tuple[str, ...] = ()
    workflow_requests: tuple[str, ...] = ()
    domain_modes: MappingProxyType[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )
    decisions: tuple[CrossDomainDecision, ...] = ()
    external_calls_used: int = 0
    estimated_cost: float | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _coerce_status(self.status, "status"))
        _reject_non_terminal_status(self.status, "status")
        object.__setattr__(
            self,
            "domain_order",
            _freeze_domain_ids(self.domain_order, "domain_order", require_unique=True),
        )
        object.__setattr__(
            self,
            "parallel_groups",
            _freeze_parallel_groups(
                self.parallel_groups, "parallel_groups", self.domain_order
            ),
        )
        object.__setattr__(
            self,
            "dependencies",
            _freeze_dependency_tuple(self.dependencies, "dependencies"),
        )
        object.__setattr__(
            self,
            "required_ports",
            _freeze_str_tuple(
                self.required_ports, "required_ports", require_unique=True
            ),
        )
        unknown_ports = set(self.required_ports) - KNOWN_CROSS_DOMAIN_PORTS
        if unknown_ports:
            raise CrossDomainContractError(
                f"required_ports contains unknown port names: {sorted(unknown_ports)}",
                field="required_ports",
                details={"unknown": sorted(unknown_ports)},
            )
        object.__setattr__(
            self,
            "operation_requests",
            _freeze_str_tuple(
                self.operation_requests, "operation_requests", require_unique=True
            ),
        )
        object.__setattr__(
            self,
            "workflow_requests",
            _freeze_str_tuple(
                self.workflow_requests, "workflow_requests", require_unique=True
            ),
        )
        object.__setattr__(
            self,
            "domain_modes",
            _freeze_domain_modes(self.domain_modes, "domain_modes", self.domain_order),
        )
        object.__setattr__(
            self, "decisions", _freeze_decision_tuple(self.decisions, "decisions")
        )
        object.__setattr__(
            self,
            "external_calls_used",
            _validate_non_negative_int(self.external_calls_used, "external_calls_used"),
        )
        object.__setattr__(
            self,
            "estimated_cost",
            _validate_non_negative_cost_opt(self.estimated_cost, "estimated_cost"),
        )
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "status": self.status.value,
            "domain_order": [str(d) for d in self.domain_order],
            "parallel_groups": [[str(d) for d in g] for g in self.parallel_groups],
            "dependencies": [d.to_dict() for d in self.dependencies],
            "required_ports": list(self.required_ports),
            "operation_requests": list(self.operation_requests),
            "workflow_requests": list(self.workflow_requests),
            "domain_modes": dict(self.domain_modes),
            "decisions": [d.to_dict() for d in self.decisions],
            "external_calls_used": self.external_calls_used,
            "estimated_cost": self.estimated_cost,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrossDomainPlanResult:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise CrossDomainSerializationError(
                "CrossDomainPlanResult.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _PLAN_RESULT_KNOWN, "CrossDomainPlanResult")
        if "status" not in data:
            raise CrossDomainSerializationError(
                "CrossDomainPlanResult.from_dict missing required field 'status'",
                field="status",
            )
        try:
            return cls(
                status=data["status"],
                domain_order=tuple(data.get("domain_order", ())),
                parallel_groups=tuple(
                    tuple(g) for g in data.get("parallel_groups", ())
                ),
                dependencies=tuple(data.get("dependencies", ())),
                required_ports=tuple(data.get("required_ports", ())),
                operation_requests=tuple(data.get("operation_requests", ())),
                workflow_requests=tuple(data.get("workflow_requests", ())),
                domain_modes=data.get("domain_modes"),
                decisions=tuple(data.get("decisions", ())),
                external_calls_used=data.get("external_calls_used", 0),
                estimated_cost=data.get("estimated_cost"),
                metadata=data.get("metadata"),
            )
        except CrossDomainContractError as exc:
            raise CrossDomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# CrossDomainWorkflowResult
# ═══════════════════════════════════════════════════════════════════════════════

_WORKFLOW_RESULT_KNOWN = frozenset(
    {
        "status",
        "workflow_ids",
        "findings",
        "dependencies",
        "contradictions",
        "gaps",
        "recommendations",
        "external_calls_used",
        "estimated_cost",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class CrossDomainWorkflowResult:
    """The result of coordinating a set of workflow requests through the Workflow port."""

    status: CrossDomainStatus
    workflow_ids: tuple[str, ...] = ()
    findings: tuple[CrossDomainFinding, ...] = ()
    dependencies: tuple[CrossDomainDependency, ...] = ()
    contradictions: tuple[CrossDomainContradiction, ...] = ()
    gaps: tuple[CrossDomainGap, ...] = ()
    recommendations: tuple[str, ...] = ()
    external_calls_used: int = 0
    estimated_cost: float | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _coerce_status(self.status, "status"))
        _reject_non_terminal_status(self.status, "status")
        object.__setattr__(
            self,
            "workflow_ids",
            _freeze_str_tuple(self.workflow_ids, "workflow_ids", require_unique=True),
        )
        object.__setattr__(
            self, "findings", _freeze_finding_tuple(self.findings, "findings")
        )
        object.__setattr__(
            self,
            "dependencies",
            _freeze_dependency_tuple(self.dependencies, "dependencies"),
        )
        object.__setattr__(
            self,
            "contradictions",
            _freeze_contradiction_tuple(self.contradictions, "contradictions"),
        )
        object.__setattr__(self, "gaps", _freeze_gap_tuple(self.gaps, "gaps"))
        object.__setattr__(
            self,
            "recommendations",
            _freeze_str_tuple(self.recommendations, "recommendations"),
        )
        object.__setattr__(
            self,
            "external_calls_used",
            _validate_non_negative_int(self.external_calls_used, "external_calls_used"),
        )
        object.__setattr__(
            self,
            "estimated_cost",
            _validate_non_negative_cost_opt(self.estimated_cost, "estimated_cost"),
        )
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "status": self.status.value,
            "workflow_ids": list(self.workflow_ids),
            "findings": [f.to_dict() for f in self.findings],
            "dependencies": [d.to_dict() for d in self.dependencies],
            "contradictions": [c.to_dict() for c in self.contradictions],
            "gaps": [g.to_dict() for g in self.gaps],
            "recommendations": list(self.recommendations),
            "external_calls_used": self.external_calls_used,
            "estimated_cost": self.estimated_cost,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrossDomainWorkflowResult:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise CrossDomainSerializationError(
                "CrossDomainWorkflowResult.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(
            data, _WORKFLOW_RESULT_KNOWN, "CrossDomainWorkflowResult"
        )
        if "status" not in data:
            raise CrossDomainSerializationError(
                "CrossDomainWorkflowResult.from_dict missing required field 'status'",
                field="status",
            )
        try:
            return cls(
                status=data["status"],
                workflow_ids=tuple(data.get("workflow_ids", ())),
                findings=tuple(data.get("findings", ())),
                dependencies=tuple(data.get("dependencies", ())),
                contradictions=tuple(data.get("contradictions", ())),
                gaps=tuple(data.get("gaps", ())),
                recommendations=tuple(data.get("recommendations", ())),
                external_calls_used=data.get("external_calls_used", 0),
                estimated_cost=data.get("estimated_cost"),
                metadata=data.get("metadata"),
            )
        except CrossDomainContractError as exc:
            raise CrossDomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# CrossDomainOperationResult
# ═══════════════════════════════════════════════════════════════════════════════

_OPERATION_RESULT_KNOWN = frozenset(
    {
        "status",
        "operation_ids",
        "findings",
        "dependencies",
        "contradictions",
        "gaps",
        "recommendations",
        "external_calls_used",
        "estimated_cost",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class CrossDomainOperationResult:
    """The result of coordinating a set of operation requests through the Operation port."""

    status: CrossDomainStatus
    operation_ids: tuple[str, ...] = ()
    findings: tuple[CrossDomainFinding, ...] = ()
    dependencies: tuple[CrossDomainDependency, ...] = ()
    contradictions: tuple[CrossDomainContradiction, ...] = ()
    gaps: tuple[CrossDomainGap, ...] = ()
    recommendations: tuple[str, ...] = ()
    external_calls_used: int = 0
    estimated_cost: float | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _coerce_status(self.status, "status"))
        _reject_non_terminal_status(self.status, "status")
        object.__setattr__(
            self,
            "operation_ids",
            _freeze_str_tuple(self.operation_ids, "operation_ids", require_unique=True),
        )
        object.__setattr__(
            self, "findings", _freeze_finding_tuple(self.findings, "findings")
        )
        object.__setattr__(
            self,
            "dependencies",
            _freeze_dependency_tuple(self.dependencies, "dependencies"),
        )
        object.__setattr__(
            self,
            "contradictions",
            _freeze_contradiction_tuple(self.contradictions, "contradictions"),
        )
        object.__setattr__(self, "gaps", _freeze_gap_tuple(self.gaps, "gaps"))
        object.__setattr__(
            self,
            "recommendations",
            _freeze_str_tuple(self.recommendations, "recommendations"),
        )
        object.__setattr__(
            self,
            "external_calls_used",
            _validate_non_negative_int(self.external_calls_used, "external_calls_used"),
        )
        object.__setattr__(
            self,
            "estimated_cost",
            _validate_non_negative_cost_opt(self.estimated_cost, "estimated_cost"),
        )
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "status": self.status.value,
            "operation_ids": list(self.operation_ids),
            "findings": [f.to_dict() for f in self.findings],
            "dependencies": [d.to_dict() for d in self.dependencies],
            "contradictions": [c.to_dict() for c in self.contradictions],
            "gaps": [g.to_dict() for g in self.gaps],
            "recommendations": list(self.recommendations),
            "external_calls_used": self.external_calls_used,
            "estimated_cost": self.estimated_cost,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrossDomainOperationResult:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise CrossDomainSerializationError(
                "CrossDomainOperationResult.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(
            data, _OPERATION_RESULT_KNOWN, "CrossDomainOperationResult"
        )
        if "status" not in data:
            raise CrossDomainSerializationError(
                "CrossDomainOperationResult.from_dict missing required field 'status'",
                field="status",
            )
        try:
            return cls(
                status=data["status"],
                operation_ids=tuple(data.get("operation_ids", ())),
                findings=tuple(data.get("findings", ())),
                dependencies=tuple(data.get("dependencies", ())),
                contradictions=tuple(data.get("contradictions", ())),
                gaps=tuple(data.get("gaps", ())),
                recommendations=tuple(data.get("recommendations", ())),
                external_calls_used=data.get("external_calls_used", 0),
                estimated_cost=data.get("estimated_cost"),
                metadata=data.get("metadata"),
            )
        except CrossDomainContractError as exc:
            raise CrossDomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# CrossDomainKnowledgeResult
# ═══════════════════════════════════════════════════════════════════════════════

_KNOWLEDGE_RESULT_KNOWN = frozenset(
    {
        "status",
        "findings",
        "entities",
        "timelines",
        "dependencies",
        "contradictions",
        "gaps",
        "external_calls_used",
        "estimated_cost",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class CrossDomainKnowledgeResult:
    """The result of retrieving shared knowledge through the Knowledge port."""

    status: CrossDomainStatus
    findings: tuple[CrossDomainFinding, ...] = ()
    entities: tuple[str, ...] = ()
    timelines: tuple[str, ...] = ()
    dependencies: tuple[CrossDomainDependency, ...] = ()
    contradictions: tuple[CrossDomainContradiction, ...] = ()
    gaps: tuple[CrossDomainGap, ...] = ()
    external_calls_used: int = 0
    estimated_cost: float | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _coerce_status(self.status, "status"))
        _reject_non_terminal_status(self.status, "status")
        object.__setattr__(
            self, "findings", _freeze_finding_tuple(self.findings, "findings")
        )
        object.__setattr__(
            self, "entities", _freeze_str_tuple(self.entities, "entities")
        )
        object.__setattr__(
            self, "timelines", _freeze_str_tuple(self.timelines, "timelines")
        )
        object.__setattr__(
            self,
            "dependencies",
            _freeze_dependency_tuple(self.dependencies, "dependencies"),
        )
        object.__setattr__(
            self,
            "contradictions",
            _freeze_contradiction_tuple(self.contradictions, "contradictions"),
        )
        object.__setattr__(self, "gaps", _freeze_gap_tuple(self.gaps, "gaps"))
        object.__setattr__(
            self,
            "external_calls_used",
            _validate_non_negative_int(self.external_calls_used, "external_calls_used"),
        )
        object.__setattr__(
            self,
            "estimated_cost",
            _validate_non_negative_cost_opt(self.estimated_cost, "estimated_cost"),
        )
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "status": self.status.value,
            "findings": [f.to_dict() for f in self.findings],
            "entities": list(self.entities),
            "timelines": list(self.timelines),
            "dependencies": [d.to_dict() for d in self.dependencies],
            "contradictions": [c.to_dict() for c in self.contradictions],
            "gaps": [g.to_dict() for g in self.gaps],
            "external_calls_used": self.external_calls_used,
            "estimated_cost": self.estimated_cost,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrossDomainKnowledgeResult:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise CrossDomainSerializationError(
                "CrossDomainKnowledgeResult.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(
            data, _KNOWLEDGE_RESULT_KNOWN, "CrossDomainKnowledgeResult"
        )
        if "status" not in data:
            raise CrossDomainSerializationError(
                "CrossDomainKnowledgeResult.from_dict missing required field 'status'",
                field="status",
            )
        try:
            return cls(
                status=data["status"],
                findings=tuple(data.get("findings", ())),
                entities=tuple(data.get("entities", ())),
                timelines=tuple(data.get("timelines", ())),
                dependencies=tuple(data.get("dependencies", ())),
                contradictions=tuple(data.get("contradictions", ())),
                gaps=tuple(data.get("gaps", ())),
                external_calls_used=data.get("external_calls_used", 0),
                estimated_cost=data.get("estimated_cost"),
                metadata=data.get("metadata"),
            )
        except CrossDomainContractError as exc:
            raise CrossDomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# CrossDomainLimits
# ═══════════════════════════════════════════════════════════════════════════════

_LIMITS_KNOWN = frozenset(
    {
        "domains_used",
        "domain_hops_used",
        "iterations_used",
        "questions_used",
        "operations_used",
        "external_calls_used",
        "estimated_cost",
        "elapsed_ms",
        "reached_limits",
        "metadata",
    }
)

#: Canonical, deterministic ordering for ``reached_limits`` entries.
REACHED_LIMIT_ORDER: tuple[str, ...] = (
    "domains",
    "domain_hops",
    "iterations",
    "questions",
    "operations",
    "external_calls",
    "cost",
    "duration",
    "parallel_group_size",
)


def _sort_reached_limits(values: tuple[str, ...]) -> tuple[str, ...]:
    """Sort reached-limit names by the canonical order, unknowns last (alphabetically)."""
    rank = {name: i for i, name in enumerate(REACHED_LIMIT_ORDER)}
    return tuple(
        sorted(values, key=lambda v: (rank.get(v, len(REACHED_LIMIT_ORDER)), v))
    )


@dataclass(frozen=True, slots=True)
class CrossDomainLimits:
    """A snapshot of consumed limits and which limits (if any) have been reached."""

    domains_used: int = 0
    domain_hops_used: int = 0
    iterations_used: int = 0
    questions_used: int = 0
    operations_used: int = 0
    external_calls_used: int = 0
    estimated_cost: float = 0.0
    elapsed_ms: int = 0
    reached_limits: tuple[str, ...] = ()
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        for attr_name in (
            "domains_used",
            "domain_hops_used",
            "iterations_used",
            "questions_used",
            "operations_used",
            "external_calls_used",
            "elapsed_ms",
        ):
            object.__setattr__(
                self,
                attr_name,
                _validate_non_negative_int(getattr(self, attr_name), attr_name),
            )
        object.__setattr__(
            self,
            "estimated_cost",
            _validate_non_negative_float(self.estimated_cost, "estimated_cost"),
        )
        object.__setattr__(
            self,
            "reached_limits",
            _freeze_unique_str_tuple(self.reached_limits, "reached_limits"),
        )
        object.__setattr__(
            self, "reached_limits", _sort_reached_limits(self.reached_limits)
        )
        object.__setattr__(self, "metadata", _deep_freeze(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "domains_used": self.domains_used,
            "domain_hops_used": self.domain_hops_used,
            "iterations_used": self.iterations_used,
            "questions_used": self.questions_used,
            "operations_used": self.operations_used,
            "external_calls_used": self.external_calls_used,
            "estimated_cost": self.estimated_cost,
            "elapsed_ms": self.elapsed_ms,
            "reached_limits": list(self.reached_limits),
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrossDomainLimits:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise CrossDomainSerializationError(
                "CrossDomainLimits.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _LIMITS_KNOWN, "CrossDomainLimits")
        try:
            return cls(
                domains_used=data.get("domains_used", 0),
                domain_hops_used=data.get("domain_hops_used", 0),
                iterations_used=data.get("iterations_used", 0),
                questions_used=data.get("questions_used", 0),
                operations_used=data.get("operations_used", 0),
                external_calls_used=data.get("external_calls_used", 0),
                estimated_cost=data.get("estimated_cost", 0.0),
                elapsed_ms=data.get("elapsed_ms", 0),
                reached_limits=tuple(data.get("reached_limits", ())),
                metadata=data.get("metadata"),
            )
        except CrossDomainContractError as exc:
            raise CrossDomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# CrossDomainContextSnapshot
# ═══════════════════════════════════════════════════════════════════════════════

_SNAPSHOT_KNOWN = frozenset(
    {
        "request_id",
        "composition_id",
        "active_domains",
        "visited_domains",
        "domain_hops",
        "iteration",
        "shared_entities",
        "shared_timelines",
        "shared_findings",
        "open_questions",
        "answered_questions",
        "dependencies",
        "contradictions",
        "gaps",
        "partial_results",
        "transfers",
        "decisions",
        "consumed_operations",
        "consumed_external_calls",
        "estimated_cost",
        "started_at",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class CrossDomainContextSnapshot:
    """An immutable execution-time snapshot handed to ports. Never persisted."""

    request_id: str
    composition_id: str | None
    active_domains: tuple[DomainId, ...] = ()
    visited_domains: tuple[DomainId, ...] = ()
    domain_hops: int = 0
    iteration: int = 0
    shared_entities: tuple[str, ...] = ()
    shared_timelines: tuple[str, ...] = ()
    shared_findings: tuple[CrossDomainFinding, ...] = ()
    open_questions: tuple[CrossDomainQuestion, ...] = ()
    answered_questions: tuple[CrossDomainQuestion, ...] = ()
    dependencies: tuple[CrossDomainDependency, ...] = ()
    contradictions: tuple[CrossDomainContradiction, ...] = ()
    gaps: tuple[CrossDomainGap, ...] = ()
    partial_results: tuple[CrossDomainDomainResult, ...] = ()
    transfers: tuple[CrossDomainContextTransfer, ...] = ()
    decisions: tuple[CrossDomainDecision, ...] = ()
    consumed_operations: int = 0
    consumed_external_calls: int = 0
    estimated_cost: float = 0.0
    started_at: datetime = field(default_factory=lambda: _require_started_at())
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _validate_non_empty_str(self.request_id, "request_id")
        )
        object.__setattr__(
            self, "composition_id", _normalize_empty_to_none(self.composition_id)
        )
        object.__setattr__(
            self,
            "active_domains",
            _freeze_domain_ids(
                self.active_domains, "active_domains", require_unique=True
            ),
        )
        object.__setattr__(
            self,
            "visited_domains",
            _freeze_domain_ids(
                self.visited_domains, "visited_domains", require_unique=True
            ),
        )
        object.__setattr__(
            self,
            "domain_hops",
            _validate_non_negative_int(self.domain_hops, "domain_hops"),
        )
        object.__setattr__(
            self, "iteration", _validate_non_negative_int(self.iteration, "iteration")
        )
        object.__setattr__(
            self,
            "shared_entities",
            _freeze_str_tuple(
                self.shared_entities, "shared_entities", require_unique=True
            ),
        )
        object.__setattr__(
            self,
            "shared_timelines",
            _freeze_str_tuple(
                self.shared_timelines, "shared_timelines", require_unique=True
            ),
        )
        object.__setattr__(
            self,
            "shared_findings",
            _freeze_finding_tuple(self.shared_findings, "shared_findings"),
        )
        object.__setattr__(
            self,
            "open_questions",
            _freeze_question_tuple(self.open_questions, "open_questions"),
        )
        object.__setattr__(
            self,
            "answered_questions",
            _freeze_question_tuple(self.answered_questions, "answered_questions"),
        )
        object.__setattr__(
            self,
            "dependencies",
            _freeze_dependency_tuple(self.dependencies, "dependencies"),
        )
        object.__setattr__(
            self,
            "contradictions",
            _freeze_contradiction_tuple(self.contradictions, "contradictions"),
        )
        object.__setattr__(self, "gaps", _freeze_gap_tuple(self.gaps, "gaps"))
        object.__setattr__(
            self,
            "partial_results",
            _freeze_domain_result_tuple(self.partial_results, "partial_results"),
        )
        object.__setattr__(
            self, "transfers", _freeze_transfer_tuple(self.transfers, "transfers")
        )
        object.__setattr__(
            self, "decisions", _freeze_decision_tuple(self.decisions, "decisions")
        )
        object.__setattr__(
            self,
            "consumed_operations",
            _validate_non_negative_int(self.consumed_operations, "consumed_operations"),
        )
        object.__setattr__(
            self,
            "consumed_external_calls",
            _validate_non_negative_int(
                self.consumed_external_calls, "consumed_external_calls"
            ),
        )
        object.__setattr__(
            self,
            "estimated_cost",
            _validate_non_negative_float(self.estimated_cost, "estimated_cost"),
        )
        object.__setattr__(
            self, "started_at", _ensure_tz_aware(self.started_at, "started_at")
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        _reject_credential_keys_deep(self.metadata, "metadata")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "request_id": self.request_id,
            "composition_id": self.composition_id,
            "active_domains": [str(d) for d in self.active_domains],
            "visited_domains": [str(d) for d in self.visited_domains],
            "domain_hops": self.domain_hops,
            "iteration": self.iteration,
            "shared_entities": list(self.shared_entities),
            "shared_timelines": list(self.shared_timelines),
            "shared_findings": [f.to_dict() for f in self.shared_findings],
            "open_questions": [q.to_dict() for q in self.open_questions],
            "answered_questions": [q.to_dict() for q in self.answered_questions],
            "dependencies": [d.to_dict() for d in self.dependencies],
            "contradictions": [c.to_dict() for c in self.contradictions],
            "gaps": [g.to_dict() for g in self.gaps],
            "partial_results": [r.to_dict() for r in self.partial_results],
            "transfers": [t.to_dict() for t in self.transfers],
            "decisions": [d.to_dict() for d in self.decisions],
            "consumed_operations": self.consumed_operations,
            "consumed_external_calls": self.consumed_external_calls,
            "estimated_cost": self.estimated_cost,
            "started_at": self.started_at.isoformat(),
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrossDomainContextSnapshot:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise CrossDomainSerializationError(
                "CrossDomainContextSnapshot.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _SNAPSHOT_KNOWN, "CrossDomainContextSnapshot")
        required = {"request_id", "started_at"}
        missing = required - set(data.keys())
        if missing:
            raise CrossDomainSerializationError(
                f"CrossDomainContextSnapshot.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        started_at = _parse_datetime_opt(data["started_at"], "started_at")
        if started_at is None:
            raise CrossDomainSerializationError(
                "started_at is required", field="started_at"
            )
        try:
            return cls(
                request_id=data["request_id"],
                composition_id=data.get("composition_id"),
                active_domains=tuple(data.get("active_domains", ())),
                visited_domains=tuple(data.get("visited_domains", ())),
                domain_hops=data.get("domain_hops", 0),
                iteration=data.get("iteration", 0),
                shared_entities=tuple(data.get("shared_entities", ())),
                shared_timelines=tuple(data.get("shared_timelines", ())),
                shared_findings=tuple(data.get("shared_findings", ())),
                open_questions=tuple(data.get("open_questions", ())),
                answered_questions=tuple(data.get("answered_questions", ())),
                dependencies=tuple(data.get("dependencies", ())),
                contradictions=tuple(data.get("contradictions", ())),
                gaps=tuple(data.get("gaps", ())),
                partial_results=tuple(data.get("partial_results", ())),
                transfers=tuple(data.get("transfers", ())),
                decisions=tuple(data.get("decisions", ())),
                consumed_operations=data.get("consumed_operations", 0),
                consumed_external_calls=data.get("consumed_external_calls", 0),
                estimated_cost=data.get("estimated_cost", 0.0),
                started_at=started_at,
                metadata=data.get("metadata"),
            )
        except CrossDomainContractError as exc:
            raise CrossDomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


def _require_started_at() -> datetime:
    """Raise: CrossDomainContextSnapshot.started_at has no safe default."""
    raise CrossDomainContractError(
        "started_at is required and has no default", field="started_at"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# CrossDomainResult
# ═══════════════════════════════════════════════════════════════════════════════

_RESULT_KNOWN = frozenset(
    {
        "id",
        "status",
        "objective",
        "request_id",
        "composition_id",
        "domain_results",
        "shared_findings",
        "contradictions",
        "dependencies",
        "cross_domain_gaps",
        "recommendations",
        "open_questions",
        "decisions",
        "limits",
        "confidence",
        "trace_id",
        "started_at",
        "completed_at",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class CrossDomainResult:
    """The consolidated, immutable result of a Cross-Domain Engine execution."""

    id: str
    status: CrossDomainStatus
    objective: str
    request_id: str
    composition_id: str | None
    domain_results: tuple[CrossDomainDomainResult, ...] = ()
    shared_findings: tuple[CrossDomainFinding, ...] = ()
    contradictions: tuple[CrossDomainContradiction, ...] = ()
    dependencies: tuple[CrossDomainDependency, ...] = ()
    cross_domain_gaps: tuple[CrossDomainGap, ...] = ()
    recommendations: tuple[str, ...] = ()
    open_questions: tuple[CrossDomainQuestion, ...] = ()
    decisions: tuple[CrossDomainDecision, ...] = ()
    limits: CrossDomainLimits = field(default_factory=CrossDomainLimits)
    confidence: float | None = None
    trace_id: str = ""
    started_at: datetime = field(default_factory=lambda: _require_started_at())
    completed_at: datetime = field(default_factory=lambda: _require_started_at())
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(self, "status", _coerce_status(self.status, "status"))
        _reject_non_terminal_status(self.status, "status")
        object.__setattr__(
            self, "objective", _validate_non_empty_str(self.objective, "objective")
        )
        object.__setattr__(
            self, "request_id", _validate_non_empty_str(self.request_id, "request_id")
        )
        object.__setattr__(
            self, "composition_id", _normalize_empty_to_none(self.composition_id)
        )
        object.__setattr__(
            self,
            "domain_results",
            _freeze_domain_result_tuple(self.domain_results, "domain_results"),
        )
        object.__setattr__(
            self,
            "shared_findings",
            _freeze_finding_tuple(self.shared_findings, "shared_findings"),
        )
        object.__setattr__(
            self,
            "contradictions",
            _freeze_contradiction_tuple(self.contradictions, "contradictions"),
        )
        object.__setattr__(
            self,
            "dependencies",
            _freeze_dependency_tuple(self.dependencies, "dependencies"),
        )
        object.__setattr__(
            self,
            "cross_domain_gaps",
            _freeze_gap_tuple(self.cross_domain_gaps, "cross_domain_gaps"),
        )
        object.__setattr__(
            self,
            "recommendations",
            _freeze_str_tuple(self.recommendations, "recommendations"),
        )
        object.__setattr__(
            self,
            "open_questions",
            _freeze_question_tuple(self.open_questions, "open_questions"),
        )
        object.__setattr__(
            self, "decisions", _freeze_decision_tuple(self.decisions, "decisions")
        )
        if not isinstance(self.limits, CrossDomainLimits):
            if isinstance(self.limits, Mapping):
                object.__setattr__(
                    self, "limits", CrossDomainLimits.from_dict(dict(self.limits))
                )
            else:
                raise CrossDomainContractError(
                    "limits must be a CrossDomainLimits", field="limits"
                )
        object.__setattr__(
            self, "confidence", _validate_confidence_opt(self.confidence, "confidence")
        )
        object.__setattr__(
            self, "trace_id", _validate_non_empty_str(self.trace_id, "trace_id")
        )
        object.__setattr__(
            self, "started_at", _ensure_tz_aware(self.started_at, "started_at")
        )
        object.__setattr__(
            self, "completed_at", _ensure_tz_aware(self.completed_at, "completed_at")
        )
        if self.completed_at < self.started_at:
            raise CrossDomainContractError(
                "completed_at must not be before started_at", field="completed_at"
            )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        _reject_credential_keys_deep(self.metadata, "metadata")

        self._validate_status_invariants()

    def _validate_status_invariants(self) -> None:
        """Validate structurally-derivable status invariants."""
        has_blocking_gap = any(g.blocking for g in self.cross_domain_gaps)
        has_unsatisfied_blocking_dependency = any(
            d.blocking and not d.satisfied for d in self.dependencies
        )
        has_blocking_decision = any(
            d.blocking and d.code in ("PORT_UNAVAILABLE", "BLOCK_PROPAGATED")
            for d in self.decisions
        )
        is_blocked_condition = (
            has_blocking_gap
            or has_unsatisfied_blocking_dependency
            or has_blocking_decision
        )
        has_unresolved_review = any(
            c.requires_review and not c.resolved for c in self.contradictions
        ) or any(d.code == "HUMAN_REVIEW_REQUESTED" for d in self.decisions)
        has_useful_output = bool(
            self.domain_results or self.shared_findings or self.recommendations
        )
        limit_reached = bool(self.limits.reached_limits)

        if self.status == CrossDomainStatus.LIMIT_REACHED and not limit_reached:
            raise CrossDomainContractError(
                "LIMIT_REACHED status requires at least one reached limit",
                field="status",
            )
        if self.status == CrossDomainStatus.BLOCKED and not is_blocked_condition:
            raise CrossDomainContractError(
                "BLOCKED status requires an unresolved blocking condition",
                field="status",
            )
        if (
            self.status == CrossDomainStatus.REQUIRES_REVIEW
            and not has_unresolved_review
        ):
            raise CrossDomainContractError(
                "REQUIRES_REVIEW status requires an unresolved review condition",
                field="status",
            )
        if self.status == CrossDomainStatus.COMPLETED:
            if is_blocked_condition:
                raise CrossDomainContractError(
                    "COMPLETED status cannot coexist with an unresolved blocking condition",
                    field="status",
                )
            if limit_reached:
                raise CrossDomainContractError(
                    "COMPLETED status cannot coexist with a reached limit",
                    field="status",
                )
            if has_unresolved_review:
                raise CrossDomainContractError(
                    "COMPLETED status cannot coexist with an unresolved review condition",
                    field="status",
                )
            if not has_useful_output:
                raise CrossDomainContractError(
                    "COMPLETED status requires at least one useful result",
                    field="status",
                )
        if self.status == CrossDomainStatus.PARTIAL and not has_useful_output:
            raise CrossDomainContractError(
                "PARTIAL status requires at least one useful retained result",
                field="status",
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "status": self.status.value,
            "objective": self.objective,
            "request_id": self.request_id,
            "composition_id": self.composition_id,
            "domain_results": [d.to_dict() for d in self.domain_results],
            "shared_findings": [f.to_dict() for f in self.shared_findings],
            "contradictions": [c.to_dict() for c in self.contradictions],
            "dependencies": [d.to_dict() for d in self.dependencies],
            "cross_domain_gaps": [g.to_dict() for g in self.cross_domain_gaps],
            "recommendations": list(self.recommendations),
            "open_questions": [q.to_dict() for q in self.open_questions],
            "decisions": [d.to_dict() for d in self.decisions],
            "limits": self.limits.to_dict(),
            "confidence": self.confidence,
            "trace_id": self.trace_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CrossDomainResult:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise CrossDomainSerializationError(
                "CrossDomainResult.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _RESULT_KNOWN, "CrossDomainResult")
        required = {
            "id",
            "status",
            "objective",
            "request_id",
            "trace_id",
            "started_at",
            "completed_at",
        }
        missing = required - set(data.keys())
        if missing:
            raise CrossDomainSerializationError(
                f"CrossDomainResult.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        started_at = _parse_datetime_opt(data["started_at"], "started_at")
        completed_at = _parse_datetime_opt(data["completed_at"], "completed_at")
        if started_at is None or completed_at is None:
            raise CrossDomainSerializationError(
                "started_at and completed_at are required", field="data"
            )
        try:
            return cls(
                id=data["id"],
                status=data["status"],
                objective=data["objective"],
                request_id=data["request_id"],
                composition_id=data.get("composition_id"),
                domain_results=tuple(data.get("domain_results", ())),
                shared_findings=tuple(data.get("shared_findings", ())),
                contradictions=tuple(data.get("contradictions", ())),
                dependencies=tuple(data.get("dependencies", ())),
                cross_domain_gaps=tuple(data.get("cross_domain_gaps", ())),
                recommendations=tuple(data.get("recommendations", ())),
                open_questions=tuple(data.get("open_questions", ())),
                decisions=tuple(data.get("decisions", ())),
                limits=data.get("limits") or CrossDomainLimits(),
                confidence=data.get("confidence"),
                trace_id=data["trace_id"],
                started_at=started_at,
                completed_at=completed_at,
                metadata=data.get("metadata"),
            )
        except CrossDomainContractError as exc:
            raise CrossDomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


__all__ = [
    "KNOWN_CROSS_DOMAIN_PORTS",
    "REACHED_LIMIT_ORDER",
    "CrossDomainContextSnapshot",
    "CrossDomainContextTransfer",
    "CrossDomainContradiction",
    "CrossDomainDecision",
    "CrossDomainDependency",
    "CrossDomainDomainResult",
    "CrossDomainFinding",
    "CrossDomainGap",
    "CrossDomainKnowledgeResult",
    "CrossDomainLimits",
    "CrossDomainOperationResult",
    "CrossDomainPlanResult",
    "CrossDomainPolicy",
    "CrossDomainQuestion",
    "CrossDomainRequest",
    "CrossDomainResult",
    "CrossDomainWorkflowResult",
]
