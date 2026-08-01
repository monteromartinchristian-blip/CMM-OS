"""Phase 10.10 – Domain Resource Contracts.

Immutable, JSON-serializable, type-safe contracts for the Domain Resources
layer. All dataclasses are ``frozen=True``, use ``slots=True``, and never
expose mutable internal state or resource payload.

A resource exists once and may have several domain bindings; these contracts
carry lineage and interpretation metadata only, never a second copy of the
common Cognitive Layer ``Resource`` model.

No adapter execution, no filesystem, no network, no persistence.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from cmm.cognitive.enums import SensitivityLevel as Sensitivity
from cmm.domains.contracts import (
    _deep_freeze,
    _ensure_tz_aware,
    _reject_unknown_fields,
    _validate_non_empty_str,
    _validate_strict_bool,
)
from cmm.domains.enums import (
    DomainResourceDecisionCode,
    DomainResourceResolutionStatus,
    DomainResourceValidationOperator,
    DomainResourceValidationSeverity,
)
from cmm.domains.errors import DomainContractValidationError as _UpstreamContractError
from cmm.domains.errors import (
    DomainResourceContractError,
    DomainResourceSerializationError,
)
from cmm.domains.errors import DomainSerializationError as _UpstreamSerializationError
from cmm.domains.identifiers import DomainId
from cmm.domains.resolver_contracts import (
    _coerce_domain_id as _upstream_coerce_domain_id,
)
from cmm.domains.resolver_contracts import _deep_unfreeze_value
from cmm.domains.resolver_contracts import (
    _freeze_domain_ids as _upstream_freeze_domain_ids,
)
from cmm.domains.resolver_contracts import (
    _freeze_unique_str_tuple as _upstream_freeze_unique_str_tuple,
)
from cmm.domains.resolver_contracts import (
    _parse_datetime_opt as _upstream_parse_datetime_opt,
)
from cmm.domains.resolver_contracts import (
    _validate_finite_float as _upstream_validate_finite_float,
)
from cmm.domains.resolver_contracts import (
    _validate_json_safe as _upstream_validate_json_safe,
)
from cmm.domains.resolver_contracts import (
    _validate_json_safe_metadata as _upstream_validate_json_safe_metadata,
)

# ── Error translation ───────────────────────────────────────────────────────
#
# The shared validation helpers above (reused from contracts.py and
# resolver_contracts.py) raise the *Domain*-level error hierarchy. Every
# Domain Resource contract must raise Domain-Resource-level errors instead,
# so each reused helper is rebound to translate on the way out.


def _as_contract_error(fn):
    def _wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (_UpstreamContractError, _UpstreamSerializationError) as exc:
            raise DomainResourceContractError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc

    return _wrapped


def _as_serialization_error(fn):
    def _wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (_UpstreamContractError, _UpstreamSerializationError) as exc:
            raise DomainResourceSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc

    return _wrapped


_validate_non_empty_str = _as_contract_error(_validate_non_empty_str)
_validate_strict_bool = _as_contract_error(_validate_strict_bool)
_ensure_tz_aware = _as_contract_error(_ensure_tz_aware)
_deep_freeze = _as_contract_error(_deep_freeze)
_coerce_domain_id = _as_contract_error(_upstream_coerce_domain_id)
_freeze_domain_ids = _as_contract_error(_upstream_freeze_domain_ids)
_freeze_unique_str_tuple = _as_contract_error(_upstream_freeze_unique_str_tuple)
_validate_finite_float = _as_contract_error(_upstream_validate_finite_float)
_validate_json_safe = _as_contract_error(_upstream_validate_json_safe)
_validate_json_safe_metadata = _as_contract_error(_upstream_validate_json_safe_metadata)

_reject_unknown_fields = _as_serialization_error(_reject_unknown_fields)
_parse_datetime_opt = _as_serialization_error(_upstream_parse_datetime_opt)


# ── Local numeric helpers ────────────────────────────────────────────────────


def _validate_non_negative_int(val: Any, field_name: str) -> int:
    """Validate a non-negative integer, rejecting bool."""
    if isinstance(val, bool):
        raise DomainResourceContractError(
            f"{field_name} must be an integer, not a boolean", field=field_name
        )
    if not isinstance(val, int):
        raise DomainResourceContractError(
            f"{field_name} must be an integer, got {type(val).__name__}: {val!r}",
            field=field_name,
        )
    if val < 0:
        raise DomainResourceContractError(
            f"{field_name} must be non-negative, got {val!r}", field=field_name
        )
    return val


def _validate_positive_int(val: Any, field_name: str) -> int:
    """Validate a strictly positive integer, rejecting bool."""
    n = _validate_non_negative_int(val, field_name)
    if n <= 0:
        raise DomainResourceContractError(
            f"{field_name} must be positive, got {n!r}", field=field_name
        )
    return n


def _validate_unit_interval_float(val: Any, field_name: str) -> float:
    """Validate a finite float in [0.0, 1.0], rejecting bool."""
    f = _validate_finite_float(val, field_name)
    if not (0.0 <= f <= 1.0):
        raise DomainResourceContractError(
            f"{field_name} must be between 0.0 and 1.0, got {f!r}", field=field_name
        )
    return f


# ── Enum coercion helpers ────────────────────────────────────────────────────


def _coerce_sensitivity(val: Any, field_name: str) -> Sensitivity:
    """Coerce a string or Sensitivity to a Sensitivity."""
    if isinstance(val, Sensitivity):
        return val
    if isinstance(val, str):
        try:
            return Sensitivity(val)
        except ValueError as exc:
            raise DomainResourceContractError(
                f"Invalid sensitivity in {field_name}: {val!r}", field=field_name
            ) from exc
    raise DomainResourceContractError(
        f"{field_name} must be a Sensitivity or string, got {type(val).__name__}",
        field=field_name,
    )


def _coerce_resolution_status(
    val: Any, field_name: str
) -> DomainResourceResolutionStatus:
    if isinstance(val, DomainResourceResolutionStatus):
        return val
    if isinstance(val, str):
        try:
            return DomainResourceResolutionStatus(val)
        except ValueError as exc:
            raise DomainResourceContractError(
                f"Invalid resolution status in {field_name}: {val!r}", field=field_name
            ) from exc
    raise DomainResourceContractError(
        f"{field_name} must be a DomainResourceResolutionStatus or string, "
        f"got {type(val).__name__}",
        field=field_name,
    )


def _coerce_decision_code(val: Any, field_name: str) -> DomainResourceDecisionCode:
    if isinstance(val, DomainResourceDecisionCode):
        return val
    if isinstance(val, str):
        try:
            return DomainResourceDecisionCode(val)
        except ValueError as exc:
            raise DomainResourceContractError(
                f"Invalid decision code in {field_name}: {val!r}", field=field_name
            ) from exc
    raise DomainResourceContractError(
        f"{field_name} must be a DomainResourceDecisionCode or string, "
        f"got {type(val).__name__}",
        field=field_name,
    )


def _coerce_validation_severity(
    val: Any, field_name: str
) -> DomainResourceValidationSeverity:
    if isinstance(val, DomainResourceValidationSeverity):
        return val
    if isinstance(val, str):
        try:
            return DomainResourceValidationSeverity(val)
        except ValueError as exc:
            raise DomainResourceContractError(
                f"Invalid validation severity in {field_name}: {val!r}",
                field=field_name,
            ) from exc
    raise DomainResourceContractError(
        f"{field_name} must be a DomainResourceValidationSeverity or string, "
        f"got {type(val).__name__}",
        field=field_name,
    )


def _coerce_validation_operator(
    val: Any, field_name: str
) -> DomainResourceValidationOperator:
    if isinstance(val, DomainResourceValidationOperator):
        return val
    if isinstance(val, str):
        try:
            return DomainResourceValidationOperator(val)
        except ValueError as exc:
            raise DomainResourceContractError(
                f"Invalid validation operator in {field_name}: {val!r}",
                field=field_name,
            ) from exc
    raise DomainResourceContractError(
        f"{field_name} must be a DomainResourceValidationOperator or string, "
        f"got {type(val).__name__}",
        field=field_name,
    )


# ── Provenance dedup helper ──────────────────────────────────────────────────
#
# Provenance uses first-appearance, non-raising deduplication (order
# preserved), unlike the raise-on-duplicate tuples used elsewhere.


def _dedup_provenance(
    seq: Any, field_name: str, *, allow_empty: bool = True
) -> tuple[str, ...]:
    """Validate and deduplicate a provenance sequence, preserving first appearance."""
    if seq is None:
        if allow_empty:
            return ()
        raise DomainResourceContractError(
            f"{field_name} cannot be None", field=field_name
        )
    if isinstance(seq, (str, bytes)):
        raise DomainResourceContractError(
            f"{field_name} must be a sequence of strings, not a string",
            field=field_name,
        )
    if not isinstance(seq, (tuple, list, set, Sequence)):
        raise DomainResourceContractError(
            f"{field_name} must be a tuple, list, or sequence of strings",
            field=field_name,
        )
    result: list[str] = []
    seen: set[str] = set()
    for i, item in enumerate(seq):
        if not isinstance(item, str) or not item.strip():
            raise DomainResourceContractError(
                f"All items in {field_name} must be non-empty strings",
                field=field_name,
                details={"index": i, "value": item},
            )
        clean = item.strip()
        if clean not in seen:
            seen.add(clean)
            result.append(clean)
    if not allow_empty and not result:
        raise DomainResourceContractError(
            f"{field_name} must not be empty", field=field_name
        )
    return tuple(result)


# ── Temporal scope helper ────────────────────────────────────────────────────
#
# ``temporal_scope`` is a small immutable mapping of aware datetimes,
# conceptually derived from the common Cognitive Layer temporal scope
# without duplicating its mutable payload-bearing implementation.

_TEMPORAL_SCOPE_KEYS = frozenset(
    {"valid_from", "valid_until", "observed_at", "last_verified_at"}
)


def _validate_temporal_scope(
    val: Any, field_name: str
) -> MappingProxyType[str, datetime | None]:
    """Validate a mapping of known temporal-scope keys to aware datetimes."""
    if val is None:
        return MappingProxyType({})
    if isinstance(val, Mapping):
        raw = dict(val)
    else:
        raise DomainResourceContractError(
            f"{field_name} must be a mapping", field=field_name
        )
    unknown = set(raw.keys()) - _TEMPORAL_SCOPE_KEYS
    if unknown:
        raise DomainResourceContractError(
            f"{field_name} has unknown keys: {sorted(unknown)}", field=field_name
        )
    result: dict[str, datetime | None] = {}
    for key in _TEMPORAL_SCOPE_KEYS:
        if key not in raw:
            continue
        v = raw[key]
        if v is None:
            result[key] = None
            continue
        result[key] = _ensure_tz_aware(v, f"{field_name}.{key}")
    valid_from = result.get("valid_from")
    valid_until = result.get("valid_until")
    if valid_from is not None and valid_until is not None and valid_until < valid_from:
        raise DomainResourceContractError(
            f"{field_name}.valid_until must not precede valid_from", field=field_name
        )
    return MappingProxyType(result)


def _temporal_scope_to_dict(
    scope: Mapping[str, datetime | None],
) -> dict[str, str | None]:
    return {
        key: (value.isoformat() if value is not None else None)
        for key, value in scope.items()
    }


def _temporal_scope_from_dict(
    data: Any, field_name: str
) -> MappingProxyType[str, datetime | None]:
    if data is None:
        return MappingProxyType({})
    if not isinstance(data, Mapping):
        raise DomainResourceSerializationError(
            f"{field_name} must be a mapping", field=field_name
        )
    unknown = set(data.keys()) - _TEMPORAL_SCOPE_KEYS
    if unknown:
        raise DomainResourceSerializationError(
            f"{field_name} has unknown keys: {sorted(unknown)}", field=field_name
        )
    result: dict[str, datetime | None] = {}
    for key in _TEMPORAL_SCOPE_KEYS:
        if key not in data:
            continue
        result[key] = _parse_datetime_opt(data[key], f"{field_name}.{key}")
    return MappingProxyType(result)


# ── DomainResourceChecksum ───────────────────────────────────────────────────

_CHECKSUM_ALGORITHM_LENGTHS: Mapping[str, int] = MappingProxyType(
    {"sha256": 64, "sha384": 96, "sha512": 128}
)
_CHECKSUM_KNOWN = frozenset({"algorithm", "value"})


@dataclass(frozen=True, slots=True)
class DomainResourceChecksum:
    """Validated checksum reference. Never computed internally."""

    algorithm: str
    value: str

    def __post_init__(self) -> None:
        algorithm = _validate_non_empty_str(self.algorithm, "algorithm").lower()
        if algorithm not in _CHECKSUM_ALGORITHM_LENGTHS:
            raise DomainResourceContractError(
                f"algorithm must be one of {sorted(_CHECKSUM_ALGORITHM_LENGTHS)}, "
                f"got {self.algorithm!r}",
                field="algorithm",
            )
        value = _validate_non_empty_str(self.value, "value").lower()
        expected_len = _CHECKSUM_ALGORITHM_LENGTHS[algorithm]
        if len(value) != expected_len or any(
            c not in "0123456789abcdef" for c in value
        ):
            raise DomainResourceContractError(
                f"value must be a {expected_len}-character hex string for {algorithm}",
                field="value",
            )
        object.__setattr__(self, "algorithm", algorithm)
        object.__setattr__(self, "value", value)

    def to_dict(self) -> dict[str, Any]:
        return {"algorithm": self.algorithm, "value": self.value}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainResourceChecksum:
        if not isinstance(data, Mapping):
            raise DomainResourceSerializationError(
                "DomainResourceChecksum.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _CHECKSUM_KNOWN, "DomainResourceChecksum")
        missing = _CHECKSUM_KNOWN - set(data.keys())
        if missing:
            raise DomainResourceSerializationError(
                f"DomainResourceChecksum.from_dict missing required fields: "
                f"{sorted(missing)}",
                field="data",
            )
        return cls(algorithm=data["algorithm"], value=data["value"])


# ── DomainResourceTemporalPolicy ─────────────────────────────────────────────

_TEMPORAL_POLICY_KNOWN = frozenset(
    {
        "validity_window_seconds",
        "staleness_policy",
        "effective_date_required",
        "expiration_required",
        "historical_allowed",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainResourceTemporalPolicy:
    """Declarative temporal evaluation policy. No callbacks, no clock access."""

    validity_window_seconds: int | None = None
    staleness_policy: str | None = None
    effective_date_required: bool = False
    expiration_required: bool = False
    historical_allowed: bool = True
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if self.validity_window_seconds is not None:
            object.__setattr__(
                self,
                "validity_window_seconds",
                _validate_positive_int(
                    self.validity_window_seconds, "validity_window_seconds"
                ),
            )
        if self.staleness_policy is not None:
            object.__setattr__(
                self,
                "staleness_policy",
                _validate_non_empty_str(self.staleness_policy, "staleness_policy"),
            )
        object.__setattr__(
            self,
            "effective_date_required",
            _validate_strict_bool(
                self.effective_date_required, "effective_date_required"
            ),
        )
        object.__setattr__(
            self,
            "expiration_required",
            _validate_strict_bool(self.expiration_required, "expiration_required"),
        )
        object.__setattr__(
            self,
            "historical_allowed",
            _validate_strict_bool(self.historical_allowed, "historical_allowed"),
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "validity_window_seconds": self.validity_window_seconds,
            "staleness_policy": self.staleness_policy,
            "effective_date_required": self.effective_date_required,
            "expiration_required": self.expiration_required,
            "historical_allowed": self.historical_allowed,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainResourceTemporalPolicy:
        if not isinstance(data, Mapping):
            raise DomainResourceSerializationError(
                "DomainResourceTemporalPolicy.from_dict requires a mapping",
                field="data",
            )
        _reject_unknown_fields(
            data, _TEMPORAL_POLICY_KNOWN, "DomainResourceTemporalPolicy"
        )
        for bool_field in (
            "effective_date_required",
            "expiration_required",
            "historical_allowed",
        ):
            if bool_field in data and not isinstance(data[bool_field], bool):
                raise DomainResourceSerializationError(
                    f"{bool_field} must be a boolean", field=bool_field
                )
        return cls(
            validity_window_seconds=data.get("validity_window_seconds"),
            staleness_policy=data.get("staleness_policy"),
            effective_date_required=data.get("effective_date_required", False),
            expiration_required=data.get("expiration_required", False),
            historical_allowed=data.get("historical_allowed", True),
            metadata=data.get("metadata", {}),
        )


# ── DomainResourceValidationRule ─────────────────────────────────────────────

_VALIDATION_RULE_KNOWN = frozenset(
    {"id", "field", "operator", "expected", "severity", "message", "metadata"}
)


@dataclass(frozen=True, slots=True)
class DomainResourceValidationRule:
    """A single declarative validation rule. No arbitrary expressions."""

    id: str
    field: str
    operator: DomainResourceValidationOperator
    expected: Any
    severity: DomainResourceValidationSeverity
    message: str
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(self, "field", _validate_non_empty_str(self.field, "field"))
        object.__setattr__(
            self, "operator", _coerce_validation_operator(self.operator, "operator")
        )
        object.__setattr__(
            self,
            "expected",
            _deep_freeze(_validate_json_safe(self.expected, "expected")),
        )
        object.__setattr__(
            self, "severity", _coerce_validation_severity(self.severity, "severity")
        )
        object.__setattr__(
            self, "message", _validate_non_empty_str(self.message, "message")
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "field": self.field,
            "operator": self.operator.value,
            "expected": _deep_unfreeze_value(self.expected),
            "severity": self.severity.value,
            "message": self.message,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainResourceValidationRule:
        if not isinstance(data, Mapping):
            raise DomainResourceSerializationError(
                "DomainResourceValidationRule.from_dict requires a mapping",
                field="data",
            )
        _reject_unknown_fields(
            data, _VALIDATION_RULE_KNOWN, "DomainResourceValidationRule"
        )
        required = {"id", "field", "operator", "expected", "severity", "message"}
        missing = required - set(data.keys())
        if missing:
            raise DomainResourceSerializationError(
                f"DomainResourceValidationRule.from_dict missing required fields: "
                f"{sorted(missing)}",
                field="data",
            )
        return cls(
            id=data["id"],
            field=data["field"],
            operator=data["operator"],
            expected=data["expected"],
            severity=data["severity"],
            message=data["message"],
            metadata=data.get("metadata", {}),
        )


# ── DomainResourceValidationResult ───────────────────────────────────────────

_VALIDATION_RESULT_KNOWN = frozenset(
    {"rule_id", "passed", "severity", "message", "field", "observed", "metadata"}
)


@dataclass(frozen=True, slots=True)
class DomainResourceValidationResult:
    """Outcome of evaluating a single validation rule against a context."""

    rule_id: str
    passed: bool
    severity: DomainResourceValidationSeverity
    message: str
    field: str
    observed: Any = None
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "rule_id", _validate_non_empty_str(self.rule_id, "rule_id")
        )
        object.__setattr__(self, "passed", _validate_strict_bool(self.passed, "passed"))
        object.__setattr__(
            self, "severity", _coerce_validation_severity(self.severity, "severity")
        )
        object.__setattr__(
            self, "message", _validate_non_empty_str(self.message, "message")
        )
        object.__setattr__(self, "field", _validate_non_empty_str(self.field, "field"))
        object.__setattr__(
            self,
            "observed",
            _deep_freeze(_validate_json_safe(self.observed, "observed")),
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "passed": self.passed,
            "severity": self.severity.value,
            "message": self.message,
            "field": self.field,
            "observed": _deep_unfreeze_value(self.observed),
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainResourceValidationResult:
        if not isinstance(data, Mapping):
            raise DomainResourceSerializationError(
                "DomainResourceValidationResult.from_dict requires a mapping",
                field="data",
            )
        _reject_unknown_fields(
            data, _VALIDATION_RESULT_KNOWN, "DomainResourceValidationResult"
        )
        required = {"rule_id", "passed", "severity", "message", "field"}
        missing = required - set(data.keys())
        if missing:
            raise DomainResourceSerializationError(
                f"DomainResourceValidationResult.from_dict missing required fields: "
                f"{sorted(missing)}",
                field="data",
            )
        if not isinstance(data["passed"], bool):
            raise DomainResourceSerializationError(
                "passed must be a boolean", field="passed"
            )
        return cls(
            rule_id=data["rule_id"],
            passed=data["passed"],
            severity=data["severity"],
            message=data["message"],
            field=data["field"],
            observed=data.get("observed"),
            metadata=data.get("metadata", {}),
        )


# ── DomainResourceDefinition ─────────────────────────────────────────────────

_DEFINITION_KNOWN = frozenset(
    {
        "id",
        "kind",
        "domain_id",
        "adapter",
        "entity_types",
        "default_sensitivity",
        "default_permissions",
        "temporal_policy",
        "source_priority",
        "default_reliability",
        "validation_rules",
        "shareable",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainResourceDefinition:
    """Declares how a domain interprets a common resource kind."""

    id: str
    kind: str
    domain_id: DomainId
    adapter: str
    entity_types: tuple[str, ...] = ()
    default_sensitivity: Sensitivity = Sensitivity.INTERNAL
    default_permissions: tuple[str, ...] = ()
    temporal_policy: DomainResourceTemporalPolicy = field(
        default_factory=DomainResourceTemporalPolicy
    )
    source_priority: int = 0
    default_reliability: float = 1.0
    validation_rules: tuple[DomainResourceValidationRule, ...] = ()
    shareable: bool = True
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(self, "kind", _validate_non_empty_str(self.kind, "kind"))
        object.__setattr__(
            self, "domain_id", _coerce_domain_id(self.domain_id, "domain_id")
        )
        object.__setattr__(
            self, "adapter", _validate_non_empty_str(self.adapter, "adapter")
        )
        object.__setattr__(
            self,
            "entity_types",
            _freeze_unique_str_tuple(self.entity_types, "entity_types"),
        )
        object.__setattr__(
            self,
            "default_sensitivity",
            _coerce_sensitivity(self.default_sensitivity, "default_sensitivity"),
        )
        object.__setattr__(
            self,
            "default_permissions",
            _freeze_unique_str_tuple(self.default_permissions, "default_permissions"),
        )
        if not isinstance(self.temporal_policy, DomainResourceTemporalPolicy):
            raise DomainResourceContractError(
                "temporal_policy must be a DomainResourceTemporalPolicy",
                field="temporal_policy",
            )
        object.__setattr__(
            self,
            "source_priority",
            _validate_non_negative_int(self.source_priority, "source_priority"),
        )
        object.__setattr__(
            self,
            "default_reliability",
            _validate_unit_interval_float(
                self.default_reliability, "default_reliability"
            ),
        )
        rules: list[DomainResourceValidationRule] = []
        if not isinstance(self.validation_rules, (tuple, list)):
            raise DomainResourceContractError(
                "validation_rules must be a tuple or list", field="validation_rules"
            )
        for i, rule in enumerate(self.validation_rules):
            if not isinstance(rule, DomainResourceValidationRule):
                raise DomainResourceContractError(
                    f"validation_rules[{i}] must be a DomainResourceValidationRule",
                    field="validation_rules",
                )
            rules.append(rule)
        object.__setattr__(self, "validation_rules", tuple(rules))
        object.__setattr__(
            self, "shareable", _validate_strict_bool(self.shareable, "shareable")
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "domain_id": str(self.domain_id),
            "adapter": self.adapter,
            "entity_types": list(self.entity_types),
            "default_sensitivity": self.default_sensitivity.value,
            "default_permissions": list(self.default_permissions),
            "temporal_policy": self.temporal_policy.to_dict(),
            "source_priority": self.source_priority,
            "default_reliability": self.default_reliability,
            "validation_rules": [rule.to_dict() for rule in self.validation_rules],
            "shareable": self.shareable,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainResourceDefinition:
        if not isinstance(data, Mapping):
            raise DomainResourceSerializationError(
                "DomainResourceDefinition.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _DEFINITION_KNOWN, "DomainResourceDefinition")
        required = {"id", "kind", "domain_id", "adapter"}
        missing = required - set(data.keys())
        if missing:
            raise DomainResourceSerializationError(
                f"DomainResourceDefinition.from_dict missing required fields: "
                f"{sorted(missing)}",
                field="data",
            )
        for bool_field in ("shareable",):
            if bool_field in data and not isinstance(data[bool_field], bool):
                raise DomainResourceSerializationError(
                    f"{bool_field} must be a boolean", field=bool_field
                )
        temporal_policy_raw = data.get("temporal_policy")
        temporal_policy = (
            DomainResourceTemporalPolicy.from_dict(temporal_policy_raw)
            if temporal_policy_raw is not None
            else DomainResourceTemporalPolicy()
        )
        validation_rules_raw = data.get("validation_rules", [])
        if not isinstance(validation_rules_raw, list):
            raise DomainResourceSerializationError(
                "validation_rules must be a list", field="validation_rules"
            )
        validation_rules = tuple(
            DomainResourceValidationRule.from_dict(rule)
            for rule in validation_rules_raw
        )
        return cls(
            id=data["id"],
            kind=data["kind"],
            domain_id=data["domain_id"],
            adapter=data["adapter"],
            entity_types=tuple(data.get("entity_types", [])),
            default_sensitivity=data.get(
                "default_sensitivity", Sensitivity.INTERNAL.value
            ),
            default_permissions=tuple(data.get("default_permissions", [])),
            temporal_policy=temporal_policy,
            source_priority=data.get("source_priority", 0),
            default_reliability=data.get("default_reliability", 1.0),
            validation_rules=validation_rules,
            shareable=data.get("shareable", True),
            metadata=data.get("metadata", {}),
        )


# ── DomainResourceContext ────────────────────────────────────────────────────

_CONTEXT_KNOWN = frozenset(
    {
        "resource_id",
        "kind",
        "provenance",
        "applicable_domains",
        "sensitivity",
        "permissions",
        "temporal_scope",
        "source_type",
        "entity_types",
        "reliability",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainResourceContext:
    """Immutable resolution context. Not a second Resource object.

    Applicable domains are relevance hints, never authorization.
    """

    resource_id: str
    kind: str
    provenance: tuple[str, ...]
    applicable_domains: tuple[DomainId, ...] = ()
    sensitivity: Sensitivity = Sensitivity.INTERNAL
    permissions: tuple[str, ...] = ()
    temporal_scope: Mapping[str, datetime | None] = field(
        default_factory=lambda: MappingProxyType({})
    )
    source_type: str | None = None
    entity_types: tuple[str, ...] = ()
    reliability: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "resource_id",
            _validate_non_empty_str(self.resource_id, "resource_id"),
        )
        object.__setattr__(self, "kind", _validate_non_empty_str(self.kind, "kind"))
        object.__setattr__(
            self,
            "provenance",
            _dedup_provenance(self.provenance, "provenance", allow_empty=False),
        )
        object.__setattr__(
            self,
            "applicable_domains",
            _freeze_domain_ids(self.applicable_domains, "applicable_domains"),
        )
        object.__setattr__(
            self, "sensitivity", _coerce_sensitivity(self.sensitivity, "sensitivity")
        )
        object.__setattr__(
            self,
            "permissions",
            _freeze_unique_str_tuple(self.permissions, "permissions"),
        )
        object.__setattr__(
            self,
            "temporal_scope",
            _validate_temporal_scope(self.temporal_scope, "temporal_scope"),
        )
        if self.source_type is not None:
            object.__setattr__(
                self,
                "source_type",
                _validate_non_empty_str(self.source_type, "source_type"),
            )
        object.__setattr__(
            self,
            "entity_types",
            _freeze_unique_str_tuple(self.entity_types, "entity_types"),
        )
        if self.reliability is not None:
            object.__setattr__(
                self,
                "reliability",
                _validate_unit_interval_float(self.reliability, "reliability"),
            )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "kind": self.kind,
            "provenance": list(self.provenance),
            "applicable_domains": [str(d) for d in self.applicable_domains],
            "sensitivity": self.sensitivity.value,
            "permissions": list(self.permissions),
            "temporal_scope": _temporal_scope_to_dict(self.temporal_scope),
            "source_type": self.source_type,
            "entity_types": list(self.entity_types),
            "reliability": self.reliability,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainResourceContext:
        if not isinstance(data, Mapping):
            raise DomainResourceSerializationError(
                "DomainResourceContext.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _CONTEXT_KNOWN, "DomainResourceContext")
        required = {"resource_id", "kind", "provenance"}
        missing = required - set(data.keys())
        if missing:
            raise DomainResourceSerializationError(
                f"DomainResourceContext.from_dict missing required fields: "
                f"{sorted(missing)}",
                field="data",
            )
        return cls(
            resource_id=data["resource_id"],
            kind=data["kind"],
            provenance=tuple(data["provenance"]),
            applicable_domains=tuple(data.get("applicable_domains", [])),
            sensitivity=data.get("sensitivity", Sensitivity.INTERNAL.value),
            permissions=tuple(data.get("permissions", [])),
            temporal_scope=_temporal_scope_from_dict(
                data.get("temporal_scope"), "temporal_scope"
            ),
            source_type=data.get("source_type"),
            entity_types=tuple(data.get("entity_types", [])),
            reliability=data.get("reliability"),
            metadata=data.get("metadata", {}),
        )


# ── DomainResourceBinding ────────────────────────────────────────────────────

_BINDING_KNOWN = frozenset(
    {
        "id",
        "resource_id",
        "definition_id",
        "domain_id",
        "adapter",
        "provenance",
        "entity_types",
        "sensitivity",
        "permissions",
        "temporal_scope",
        "source_priority",
        "reliability",
        "validation_results",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainResourceBinding:
    """References one common resource and one definition. Carries no payload."""

    id: str
    resource_id: str
    definition_id: str
    domain_id: DomainId
    adapter: str
    provenance: tuple[str, ...]
    entity_types: tuple[str, ...] = ()
    sensitivity: Sensitivity = Sensitivity.INTERNAL
    permissions: tuple[str, ...] = ()
    temporal_scope: Mapping[str, datetime | None] = field(
        default_factory=lambda: MappingProxyType({})
    )
    source_priority: int = 0
    reliability: float = 1.0
    validation_results: tuple[DomainResourceValidationResult, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self,
            "resource_id",
            _validate_non_empty_str(self.resource_id, "resource_id"),
        )
        object.__setattr__(
            self,
            "definition_id",
            _validate_non_empty_str(self.definition_id, "definition_id"),
        )
        object.__setattr__(
            self, "domain_id", _coerce_domain_id(self.domain_id, "domain_id")
        )
        object.__setattr__(
            self, "adapter", _validate_non_empty_str(self.adapter, "adapter")
        )
        object.__setattr__(
            self,
            "provenance",
            _dedup_provenance(self.provenance, "provenance", allow_empty=False),
        )
        object.__setattr__(
            self,
            "entity_types",
            _freeze_unique_str_tuple(self.entity_types, "entity_types"),
        )
        object.__setattr__(
            self, "sensitivity", _coerce_sensitivity(self.sensitivity, "sensitivity")
        )
        object.__setattr__(
            self,
            "permissions",
            _freeze_unique_str_tuple(self.permissions, "permissions"),
        )
        object.__setattr__(
            self,
            "temporal_scope",
            _validate_temporal_scope(self.temporal_scope, "temporal_scope"),
        )
        object.__setattr__(
            self,
            "source_priority",
            _validate_non_negative_int(self.source_priority, "source_priority"),
        )
        object.__setattr__(
            self,
            "reliability",
            _validate_unit_interval_float(self.reliability, "reliability"),
        )
        results: list[DomainResourceValidationResult] = []
        if not isinstance(self.validation_results, (tuple, list)):
            raise DomainResourceContractError(
                "validation_results must be a tuple or list", field="validation_results"
            )
        for i, result in enumerate(self.validation_results):
            if not isinstance(result, DomainResourceValidationResult):
                raise DomainResourceContractError(
                    f"validation_results[{i}] must be a DomainResourceValidationResult",
                    field="validation_results",
                )
            results.append(result)
        object.__setattr__(self, "validation_results", tuple(results))
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "definition_id": self.definition_id,
            "domain_id": str(self.domain_id),
            "adapter": self.adapter,
            "provenance": list(self.provenance),
            "entity_types": list(self.entity_types),
            "sensitivity": self.sensitivity.value,
            "permissions": list(self.permissions),
            "temporal_scope": _temporal_scope_to_dict(self.temporal_scope),
            "source_priority": self.source_priority,
            "reliability": self.reliability,
            "validation_results": [r.to_dict() for r in self.validation_results],
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainResourceBinding:
        if not isinstance(data, Mapping):
            raise DomainResourceSerializationError(
                "DomainResourceBinding.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _BINDING_KNOWN, "DomainResourceBinding")
        required = {
            "id",
            "resource_id",
            "definition_id",
            "domain_id",
            "adapter",
            "provenance",
        }
        missing = required - set(data.keys())
        if missing:
            raise DomainResourceSerializationError(
                f"DomainResourceBinding.from_dict missing required fields: "
                f"{sorted(missing)}",
                field="data",
            )
        validation_results_raw = data.get("validation_results", [])
        if not isinstance(validation_results_raw, list):
            raise DomainResourceSerializationError(
                "validation_results must be a list", field="validation_results"
            )
        return cls(
            id=data["id"],
            resource_id=data["resource_id"],
            definition_id=data["definition_id"],
            domain_id=data["domain_id"],
            adapter=data["adapter"],
            provenance=tuple(data["provenance"]),
            entity_types=tuple(data.get("entity_types", [])),
            sensitivity=data.get("sensitivity", Sensitivity.INTERNAL.value),
            permissions=tuple(data.get("permissions", [])),
            temporal_scope=_temporal_scope_from_dict(
                data.get("temporal_scope"), "temporal_scope"
            ),
            source_priority=data.get("source_priority", 0),
            reliability=data.get("reliability", 1.0),
            validation_results=tuple(
                DomainResourceValidationResult.from_dict(r)
                for r in validation_results_raw
            ),
            metadata=data.get("metadata", {}),
        )


# ── DomainResourceRejection ──────────────────────────────────────────────────

_REJECTION_KNOWN = frozenset(
    {"definition_id", "domain_id", "code", "reason", "blocking", "metadata"}
)


@dataclass(frozen=True, slots=True)
class DomainResourceRejection:
    """An explicit, auditable reason a definition could not be bound."""

    definition_id: str
    domain_id: DomainId
    code: DomainResourceDecisionCode
    reason: str
    blocking: bool
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "definition_id",
            _validate_non_empty_str(self.definition_id, "definition_id"),
        )
        object.__setattr__(
            self, "domain_id", _coerce_domain_id(self.domain_id, "domain_id")
        )
        object.__setattr__(self, "code", _coerce_decision_code(self.code, "code"))
        object.__setattr__(
            self, "reason", _validate_non_empty_str(self.reason, "reason")
        )
        object.__setattr__(
            self, "blocking", _validate_strict_bool(self.blocking, "blocking")
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "definition_id": self.definition_id,
            "domain_id": str(self.domain_id),
            "code": self.code.value,
            "reason": self.reason,
            "blocking": self.blocking,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainResourceRejection:
        if not isinstance(data, Mapping):
            raise DomainResourceSerializationError(
                "DomainResourceRejection.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _REJECTION_KNOWN, "DomainResourceRejection")
        required = {"definition_id", "domain_id", "code", "reason", "blocking"}
        missing = required - set(data.keys())
        if missing:
            raise DomainResourceSerializationError(
                f"DomainResourceRejection.from_dict missing required fields: "
                f"{sorted(missing)}",
                field="data",
            )
        if not isinstance(data["blocking"], bool):
            raise DomainResourceSerializationError(
                "blocking must be a boolean", field="blocking"
            )
        return cls(
            definition_id=data["definition_id"],
            domain_id=data["domain_id"],
            code=data["code"],
            reason=data["reason"],
            blocking=data["blocking"],
            metadata=data.get("metadata", {}),
        )


# ── DomainResourceDecision ───────────────────────────────────────────────────

_DECISION_KNOWN = frozenset(
    {
        "code",
        "resource_id",
        "reason",
        "blocking",
        "definition_id",
        "domain_id",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainResourceDecision:
    """An auditable decision emitted during resolution."""

    code: DomainResourceDecisionCode
    resource_id: str
    reason: str
    blocking: bool
    definition_id: str | None = None
    domain_id: DomainId | None = None
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _coerce_decision_code(self.code, "code"))
        object.__setattr__(
            self,
            "resource_id",
            _validate_non_empty_str(self.resource_id, "resource_id"),
        )
        object.__setattr__(
            self, "reason", _validate_non_empty_str(self.reason, "reason")
        )
        object.__setattr__(
            self, "blocking", _validate_strict_bool(self.blocking, "blocking")
        )
        if self.definition_id is not None:
            object.__setattr__(
                self,
                "definition_id",
                _validate_non_empty_str(self.definition_id, "definition_id"),
            )
        if self.domain_id is not None:
            object.__setattr__(
                self, "domain_id", _coerce_domain_id(self.domain_id, "domain_id")
            )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "resource_id": self.resource_id,
            "reason": self.reason,
            "blocking": self.blocking,
            "definition_id": self.definition_id,
            "domain_id": str(self.domain_id) if self.domain_id is not None else None,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainResourceDecision:
        if not isinstance(data, Mapping):
            raise DomainResourceSerializationError(
                "DomainResourceDecision.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _DECISION_KNOWN, "DomainResourceDecision")
        required = {"code", "resource_id", "reason", "blocking"}
        missing = required - set(data.keys())
        if missing:
            raise DomainResourceSerializationError(
                f"DomainResourceDecision.from_dict missing required fields: "
                f"{sorted(missing)}",
                field="data",
            )
        if not isinstance(data["blocking"], bool):
            raise DomainResourceSerializationError(
                "blocking must be a boolean", field="blocking"
            )
        return cls(
            code=data["code"],
            resource_id=data["resource_id"],
            reason=data["reason"],
            blocking=data["blocking"],
            definition_id=data.get("definition_id"),
            domain_id=data.get("domain_id"),
            metadata=data.get("metadata", {}),
        )


# ── DomainResourceResolution ─────────────────────────────────────────────────

_RESOLUTION_KNOWN = frozenset(
    {
        "id",
        "resource_id",
        "status",
        "trace_id",
        "resolved_at",
        "bindings",
        "rejections",
        "permission_denials",
        "validation_issues",
        "shared_domains",
        "decisions",
        "metadata",
    }
)


def _has_blocking_rejection(rejections: tuple[DomainResourceRejection, ...]) -> bool:
    return any(r.blocking for r in rejections)


def _has_blocking_validation_issue(
    validation_issues: tuple[DomainResourceValidationResult, ...],
) -> bool:
    return any(
        not v.passed and v.severity == DomainResourceValidationSeverity.BLOCKING
        for v in validation_issues
    )


@dataclass(frozen=True, slots=True)
class DomainResourceResolution:
    """The immutable, auditable outcome of a resolution operation."""

    id: str
    resource_id: str
    status: DomainResourceResolutionStatus
    trace_id: str
    resolved_at: datetime
    bindings: tuple[DomainResourceBinding, ...] = ()
    rejections: tuple[DomainResourceRejection, ...] = ()
    permission_denials: tuple[DomainResourceRejection, ...] = ()
    validation_issues: tuple[DomainResourceValidationResult, ...] = ()
    shared_domains: tuple[DomainId, ...] = ()
    decisions: tuple[DomainResourceDecision, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self,
            "resource_id",
            _validate_non_empty_str(self.resource_id, "resource_id"),
        )
        object.__setattr__(
            self, "status", _coerce_resolution_status(self.status, "status")
        )
        object.__setattr__(
            self, "trace_id", _validate_non_empty_str(self.trace_id, "trace_id")
        )
        object.__setattr__(
            self, "resolved_at", _ensure_tz_aware(self.resolved_at, "resolved_at")
        )
        object.__setattr__(
            self,
            "bindings",
            _coerce_tuple_of(self.bindings, DomainResourceBinding, "bindings"),
        )
        object.__setattr__(
            self,
            "rejections",
            _coerce_tuple_of(self.rejections, DomainResourceRejection, "rejections"),
        )
        object.__setattr__(
            self,
            "permission_denials",
            _coerce_tuple_of(
                self.permission_denials, DomainResourceRejection, "permission_denials"
            ),
        )
        object.__setattr__(
            self,
            "validation_issues",
            _coerce_tuple_of(
                self.validation_issues,
                DomainResourceValidationResult,
                "validation_issues",
            ),
        )
        object.__setattr__(
            self,
            "shared_domains",
            _freeze_domain_ids(self.shared_domains, "shared_domains"),
        )
        object.__setattr__(
            self,
            "decisions",
            _coerce_tuple_of(self.decisions, DomainResourceDecision, "decisions"),
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

        binding_domains = {b.domain_id for b in self.bindings}
        unknown_shared = [d for d in self.shared_domains if d not in binding_domains]
        if unknown_shared:
            raise DomainResourceContractError(
                "shared_domains must correspond to accepted bindings",
                field="shared_domains",
                details={"unknown": [str(d) for d in unknown_shared]},
            )

        has_blocking_rejection = _has_blocking_rejection(self.rejections)
        has_blocking_issue = _has_blocking_validation_issue(self.validation_issues)

        if self.status == DomainResourceResolutionStatus.REJECTED and self.bindings:
            raise DomainResourceContractError(
                "REJECTED resolution must not contain bindings", field="status"
            )
        if self.status == DomainResourceResolutionStatus.RESOLVED:
            if not self.bindings:
                raise DomainResourceContractError(
                    "RESOLVED resolution requires at least one binding", field="status"
                )
            if has_blocking_rejection or has_blocking_issue:
                raise DomainResourceContractError(
                    "RESOLVED resolution must not contain unresolved blockers",
                    field="status",
                )
        if self.status == DomainResourceResolutionStatus.BLOCKED and not (
            has_blocking_rejection or has_blocking_issue
        ):
            raise DomainResourceContractError(
                "BLOCKED resolution requires a blocking rejection or validation issue",
                field="status",
            )
        if self.status == DomainResourceResolutionStatus.PARTIAL:
            if not self.bindings:
                raise DomainResourceContractError(
                    "PARTIAL resolution requires at least one binding", field="status"
                )
            if not (self.rejections or has_blocking_issue):
                raise DomainResourceContractError(
                    "PARTIAL resolution requires an incomplete condition",
                    field="status",
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "status": self.status.value,
            "trace_id": self.trace_id,
            "resolved_at": self.resolved_at.isoformat(),
            "bindings": [b.to_dict() for b in self.bindings],
            "rejections": [r.to_dict() for r in self.rejections],
            "permission_denials": [r.to_dict() for r in self.permission_denials],
            "validation_issues": [v.to_dict() for v in self.validation_issues],
            "shared_domains": [str(d) for d in self.shared_domains],
            "decisions": [d.to_dict() for d in self.decisions],
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainResourceResolution:
        if not isinstance(data, Mapping):
            raise DomainResourceSerializationError(
                "DomainResourceResolution.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _RESOLUTION_KNOWN, "DomainResourceResolution")
        required = {"id", "resource_id", "status", "trace_id", "resolved_at"}
        missing = required - set(data.keys())
        if missing:
            raise DomainResourceSerializationError(
                f"DomainResourceResolution.from_dict missing required fields: "
                f"{sorted(missing)}",
                field="data",
            )
        return cls(
            id=data["id"],
            resource_id=data["resource_id"],
            status=data["status"],
            trace_id=data["trace_id"],
            resolved_at=_parse_datetime_opt(data["resolved_at"], "resolved_at"),
            bindings=tuple(
                DomainResourceBinding.from_dict(b) for b in data.get("bindings", [])
            ),
            rejections=tuple(
                DomainResourceRejection.from_dict(r) for r in data.get("rejections", [])
            ),
            permission_denials=tuple(
                DomainResourceRejection.from_dict(r)
                for r in data.get("permission_denials", [])
            ),
            validation_issues=tuple(
                DomainResourceValidationResult.from_dict(v)
                for v in data.get("validation_issues", [])
            ),
            shared_domains=tuple(data.get("shared_domains", [])),
            decisions=tuple(
                DomainResourceDecision.from_dict(d) for d in data.get("decisions", [])
            ),
            metadata=data.get("metadata", {}),
        )


def _coerce_tuple_of(seq: Any, cls: type, field_name: str) -> tuple[Any, ...]:
    if not isinstance(seq, (tuple, list)):
        raise DomainResourceContractError(
            f"{field_name} must be a tuple or list", field=field_name
        )
    result = []
    for i, item in enumerate(seq):
        if not isinstance(item, cls):
            raise DomainResourceContractError(
                f"{field_name}[{i}] must be a {cls.__name__}", field=field_name
            )
        result.append(item)
    return tuple(result)


# ── DomainResourceDerivation ─────────────────────────────────────────────────

_DERIVATION_KNOWN = frozenset(
    {
        "id",
        "source_resource_id",
        "derived_resource_id",
        "definition_id",
        "transformation",
        "actor",
        "created_at",
        "version",
        "permissions",
        "sensitivity",
        "checksum",
        "provenance",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainResourceDerivation:
    """Explicit lineage record for a derived resource. No payload, no execution."""

    id: str
    source_resource_id: str
    derived_resource_id: str
    definition_id: str
    transformation: str
    actor: str
    created_at: datetime
    version: str
    permissions: tuple[str, ...] = ()
    sensitivity: Sensitivity = Sensitivity.INTERNAL
    checksum: DomainResourceChecksum | None = None
    provenance: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self,
            "source_resource_id",
            _validate_non_empty_str(self.source_resource_id, "source_resource_id"),
        )
        object.__setattr__(
            self,
            "derived_resource_id",
            _validate_non_empty_str(self.derived_resource_id, "derived_resource_id"),
        )
        if self.source_resource_id == self.derived_resource_id:
            raise DomainResourceContractError(
                "derived_resource_id must differ from source_resource_id",
                field="derived_resource_id",
            )
        object.__setattr__(
            self,
            "definition_id",
            _validate_non_empty_str(self.definition_id, "definition_id"),
        )
        object.__setattr__(
            self,
            "transformation",
            _validate_non_empty_str(self.transformation, "transformation"),
        )
        object.__setattr__(self, "actor", _validate_non_empty_str(self.actor, "actor"))
        object.__setattr__(
            self, "created_at", _ensure_tz_aware(self.created_at, "created_at")
        )
        object.__setattr__(
            self, "version", _validate_non_empty_str(self.version, "version")
        )
        object.__setattr__(
            self,
            "permissions",
            _freeze_unique_str_tuple(self.permissions, "permissions"),
        )
        object.__setattr__(
            self, "sensitivity", _coerce_sensitivity(self.sensitivity, "sensitivity")
        )
        if self.checksum is not None and not isinstance(
            self.checksum, DomainResourceChecksum
        ):
            raise DomainResourceContractError(
                "checksum must be a DomainResourceChecksum or None", field="checksum"
            )
        object.__setattr__(
            self,
            "provenance",
            _dedup_provenance(self.provenance, "provenance", allow_empty=False),
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_resource_id": self.source_resource_id,
            "derived_resource_id": self.derived_resource_id,
            "definition_id": self.definition_id,
            "transformation": self.transformation,
            "actor": self.actor,
            "created_at": self.created_at.isoformat(),
            "version": self.version,
            "permissions": list(self.permissions),
            "sensitivity": self.sensitivity.value,
            "checksum": self.checksum.to_dict() if self.checksum is not None else None,
            "provenance": list(self.provenance),
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainResourceDerivation:
        if not isinstance(data, Mapping):
            raise DomainResourceSerializationError(
                "DomainResourceDerivation.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _DERIVATION_KNOWN, "DomainResourceDerivation")
        required = {
            "id",
            "source_resource_id",
            "derived_resource_id",
            "definition_id",
            "transformation",
            "actor",
            "created_at",
            "version",
        }
        missing = required - set(data.keys())
        if missing:
            raise DomainResourceSerializationError(
                f"DomainResourceDerivation.from_dict missing required fields: "
                f"{sorted(missing)}",
                field="data",
            )
        checksum_raw = data.get("checksum")
        checksum = (
            DomainResourceChecksum.from_dict(checksum_raw)
            if checksum_raw is not None
            else None
        )
        return cls(
            id=data["id"],
            source_resource_id=data["source_resource_id"],
            derived_resource_id=data["derived_resource_id"],
            definition_id=data["definition_id"],
            transformation=data["transformation"],
            actor=data["actor"],
            created_at=_parse_datetime_opt(data["created_at"], "created_at"),
            version=data["version"],
            permissions=tuple(data.get("permissions", [])),
            sensitivity=data.get("sensitivity", Sensitivity.INTERNAL.value),
            checksum=checksum,
            provenance=tuple(data.get("provenance", [])),
            metadata=data.get("metadata", {}),
        )


__all__ = [
    "DomainResourceBinding",
    "DomainResourceChecksum",
    "DomainResourceContext",
    "DomainResourceDecision",
    "DomainResourceDefinition",
    "DomainResourceDerivation",
    "DomainResourceRejection",
    "DomainResourceResolution",
    "DomainResourceTemporalPolicy",
    "DomainResourceValidationResult",
    "DomainResourceValidationRule",
]
