"""Phase 10.37 — Domain Observability Contracts.

Immutable, JSON-serializable, reference-first read models for the Domain
Observability projection. All dataclasses are ``frozen=True`` with
``slots=True`` and never expose mutable state.

Phase 10.37 is a downstream, read-only projection over canonical Domain
evidence. These contracts own no operational truth, no persistence and no
runtime behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.domains.contracts import _deep_unfreeze
from cmm.domains.errors import (
    DomainSerializationError,
    InvalidDomainObservabilityContractError,
)

# ── Validation helpers ────────────────────────────────────────────────────────

_DIGEST_RE_LENGTH = 64
_MAX_METADATA_DEPTH = 4
_MAX_METADATA_ITEMS = 32
_MAX_METADATA_STRING_LENGTH = 256


def _non_empty_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidDomainObservabilityContractError(
            f"{field_name} must be a non-empty string",
            field=field_name,
        )
    return value


def _optional_str(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or isinstance(value, bool):
        raise InvalidDomainObservabilityContractError(
            f"{field_name} must be a string or None",
            field=field_name,
        )
    stripped = value.strip()
    return stripped or None


def _strict_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise InvalidDomainObservabilityContractError(
            f"{field_name} must be a boolean",
            field=field_name,
        )
    return value


def _aware(value: Any, field_name: str) -> datetime:
    """Return a timezone-aware datetime or raise the phase contract error."""
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise InvalidDomainObservabilityContractError(
            f"{field_name} must be timezone-aware",
            field=field_name,
        )
    return value


def _finite_number(value: Any, field_name: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidDomainObservabilityContractError(
            f"{field_name} must be a finite number, not a boolean",
            field=field_name,
        )
    if not math.isfinite(value):
        raise InvalidDomainObservabilityContractError(
            f"{field_name} must be a finite number",
            field=field_name,
        )
    return value


def _optional_finite_number(value: Any, field_name: str) -> int | float | None:
    if value is None:
        return None
    return _finite_number(value, field_name)


def _safe_identifier(value: Any, field_name: str) -> str:
    """Validate a public reference identifier (stable ID, domain ID, code)."""
    result = _non_empty_str(value, field_name)
    if len(result) > 256:
        raise InvalidDomainObservabilityContractError(
            f"{field_name} exceeds maximum length",
            field=field_name,
        )
    return result


def _safe_label(value: Any, field_name: str) -> str:
    """Validate a short public status/category label."""
    result = _non_empty_str(value, field_name)
    if len(result) > 64:
        raise InvalidDomainObservabilityContractError(
            f"{field_name} exceeds maximum length",
            field=field_name,
        )
    return result


def _freeze_metadata(value: Any, field_name: str = "metadata", depth: int = 0) -> Any:
    """Deep-freeze caller-supplied metadata, protecting against alias mutation."""
    if depth > _MAX_METADATA_DEPTH:
        raise InvalidDomainObservabilityContractError(
            f"{field_name} exceeds maximum depth",
            field=field_name,
        )
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise InvalidDomainObservabilityContractError(
                f"{field_name} floats must be finite",
                field=field_name,
            )
        return value
    if isinstance(value, str):
        if len(value) > _MAX_METADATA_STRING_LENGTH:
            raise InvalidDomainObservabilityContractError(
                f"{field_name} strings must be bounded",
                field=field_name,
            )
        return value
    if isinstance(value, Mapping):
        if len(value) > _MAX_METADATA_ITEMS:
            raise InvalidDomainObservabilityContractError(
                f"{field_name} has too many entries",
                field=field_name,
            )
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key.strip():
                raise InvalidDomainObservabilityContractError(
                    f"{field_name} keys must be non-empty strings",
                    field=field_name,
                )
            frozen[key] = _freeze_metadata(item, field_name, depth + 1)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        if len(value) > _MAX_METADATA_ITEMS:
            raise InvalidDomainObservabilityContractError(
                f"{field_name} has too many values",
                field=field_name,
            )
        return tuple(_freeze_metadata(item, field_name, depth + 1) for item in value)
    raise InvalidDomainObservabilityContractError(
        f"{field_name} must be JSON-safe",
        field=field_name,
    )


def _sorted_unique_ids(values: Any, field_name: str) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise InvalidDomainObservabilityContractError(
            f"{field_name} must be a sequence of strings",
            field=field_name,
        )
    result = tuple(_safe_identifier(value, field_name) for value in values)
    return tuple(sorted(set(result)))


def _digest_payload(payload: Mapping[str, Any]) -> str:
    """Compute the canonical SHA-256 digest of a JSON-safe payload."""
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise InvalidDomainObservabilityContractError(
            "payload must be JSON-serializable for digest computation",
            field="payload",
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def _validate_supplied_digest(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise InvalidDomainObservabilityContractError(
            f"{field_name} must be a SHA-256 hex digest string",
            field=field_name,
        )
    if len(value) != _DIGEST_RE_LENGTH or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise InvalidDomainObservabilityContractError(
            f"{field_name} must be a SHA-256 hex digest",
            field=field_name,
        )
    return value


def _reject_unknown_fields(
    data: Mapping[str, Any], known: frozenset[str], cls_name: str
) -> None:
    if not isinstance(data, Mapping):
        raise DomainSerializationError(
            f"{cls_name}.from_dict requires a mapping",
            field="data",
        )
    unknown = set(data.keys()) - known
    if unknown:
        raise DomainSerializationError(
            f"{cls_name}.from_dict got unknown fields: {sorted(unknown)}",
            field="data",
            details={"unknown_fields": sorted(unknown)},
        )


def _require_fields(data: Mapping[str, Any], required: set[str], cls_name: str) -> None:
    missing = required - set(data.keys())
    if missing:
        raise DomainSerializationError(
            f"{cls_name}.from_dict missing required fields: {sorted(missing)}",
            field="data",
        )


# ── Enums ─────────────────────────────────────────────────────────────────────


class DomainMetricStatus(str, Enum):
    """Status of one observability metric measurement.

    ``OBSERVED`` means authoritative canonical evidence exists.
    ``UNAVAILABLE`` means canonical evidence is insufficient to calculate the
    metric honestly. Unavailable is never encoded as zero.
    """

    OBSERVED = "observed"
    UNAVAILABLE = "unavailable"


class DomainHealthStatus(str, Enum):
    """Semantic health state of one Domain.

    ``healthy``: every required dimension positively verified, no blocking
    finding. ``degraded``: usable but one or more dimensions could not be
    positively verified. ``unhealthy``: a blocking integrity prerequisite
    fails. ``unknown``: the domain or required evidence cannot be evaluated
    without inventing state.
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# ── Metric contracts ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DomainMetricBucket:
    """One deterministic breakdown bucket (e.g. count per domain)."""

    key: str
    value: int | float

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _safe_identifier(self.key, "key"))
        object.__setattr__(self, "value", _finite_number(self.value, "value"))

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "value": self.value}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainMetricBucket:
        _reject_unknown_fields(data, {"key", "value"}, cls.__name__)
        _require_fields(data, {"key", "value"}, cls.__name__)
        try:
            return cls(key=data["key"], value=data["value"])
        except InvalidDomainObservabilityContractError as exc:
            raise DomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


@dataclass(frozen=True, slots=True)
class DomainMetricMeasurement:
    """One canonical metric measurement: exact value or explicit unavailability.

    Invariants:
    - an observed metric carries ``value`` or ``buckets`` and never an
      ``unavailable_reason``;
    - an unavailable metric carries a stable ``unavailable_reason`` and never
      a value or buckets (unavailable is never encoded as zero);
    - evidence references are public IDs only;
    - metadata is deep-frozen and caller-alias safe.
    """

    name: str
    status: DomainMetricStatus
    unit: str
    value: int | float | None = None
    buckets: tuple[DomainMetricBucket, ...] = ()
    evidence_reference_ids: tuple[str, ...] = ()
    unavailable_reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _safe_identifier(self.name, "name"))
        if not isinstance(self.status, DomainMetricStatus):
            object.__setattr__(self, "status", DomainMetricStatus(self.status))
        object.__setattr__(self, "unit", _safe_label(self.unit, "unit"))
        object.__setattr__(
            self,
            "value",
            _optional_finite_number(self.value, "value"),
        )
        buckets = tuple(
            bucket
            if isinstance(bucket, DomainMetricBucket)
            else DomainMetricBucket.from_dict(bucket)
            for bucket in self.buckets
        )
        object.__setattr__(
            self, "buckets", tuple(sorted(buckets, key=lambda item: item.key))
        )
        object.__setattr__(
            self,
            "evidence_reference_ids",
            _sorted_unique_ids(self.evidence_reference_ids, "evidence_reference_ids"),
        )
        object.__setattr__(
            self,
            "unavailable_reason",
            _optional_str(self.unavailable_reason, "unavailable_reason"),
        )
        object.__setattr__(
            self, "metadata", _freeze_metadata(self.metadata, "metadata")
        )

        if self.status is DomainMetricStatus.OBSERVED:
            if self.value is None and not self.buckets:
                raise InvalidDomainObservabilityContractError(
                    "observed metric requires a value or buckets",
                    field="value",
                )
            if self.unavailable_reason is not None:
                raise InvalidDomainObservabilityContractError(
                    "observed metric cannot claim an unavailable reason",
                    field="unavailable_reason",
                )
        else:
            if self.value is not None:
                raise InvalidDomainObservabilityContractError(
                    "unavailable metric must not carry a value",
                    field="value",
                )
            if self.buckets:
                raise InvalidDomainObservabilityContractError(
                    "unavailable metric must not carry buckets",
                    field="buckets",
                )
            if self.unavailable_reason is None:
                raise InvalidDomainObservabilityContractError(
                    "unavailable metric requires a stable reason code",
                    field="unavailable_reason",
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "unit": self.unit,
            "value": self.value,
            "buckets": [bucket.to_dict() for bucket in self.buckets],
            "evidence_reference_ids": list(self.evidence_reference_ids),
            "unavailable_reason": self.unavailable_reason,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainMetricMeasurement:
        _reject_unknown_fields(
            data, {name for name in cls.__dataclass_fields__}, cls.__name__
        )
        _require_fields(data, {"name", "status", "unit"}, cls.__name__)
        try:
            return cls(
                name=data["name"],
                status=data["status"],
                unit=data["unit"],
                value=data.get("value"),
                buckets=tuple(data.get("buckets", ())),
                evidence_reference_ids=tuple(data.get("evidence_reference_ids", ())),
                unavailable_reason=data.get("unavailable_reason"),
                metadata=data.get("metadata", {}),
            )
        except DomainSerializationError:
            raise
        except InvalidDomainObservabilityContractError:
            raise
        except (TypeError, ValueError) as exc:
            raise DomainSerializationError(
                "invalid DomainMetricMeasurement payload", field="data"
            ) from exc


@dataclass(frozen=True, slots=True)
class DomainMetricsSnapshot:
    """Immutable, deterministic snapshot of all canonical metric measurements."""

    generated_at: datetime
    measurements: tuple[DomainMetricMeasurement, ...]
    evidence_event_ids: tuple[str, ...] = ()
    evidence_trace_ids: tuple[str, ...] = ()
    evidence_session_ids: tuple[str, ...] = ()
    digest: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "generated_at", _aware(self.generated_at, "generated_at")
        )
        measurements = tuple(
            measurement
            if isinstance(measurement, DomainMetricMeasurement)
            else DomainMetricMeasurement.from_dict(measurement)
            for measurement in self.measurements
        )
        names = [measurement.name for measurement in measurements]
        if len(names) != len(set(names)):
            raise InvalidDomainObservabilityContractError(
                "measurements must not contain duplicate metric names",
                field="measurements",
            )
        object.__setattr__(self, "measurements", tuple(measurements))
        object.__setattr__(
            self,
            "evidence_event_ids",
            _sorted_unique_ids(self.evidence_event_ids, "evidence_event_ids"),
        )
        object.__setattr__(
            self,
            "evidence_trace_ids",
            _sorted_unique_ids(self.evidence_trace_ids, "evidence_trace_ids"),
        )
        object.__setattr__(
            self,
            "evidence_session_ids",
            _sorted_unique_ids(self.evidence_session_ids, "evidence_session_ids"),
        )
        object.__setattr__(
            self, "metadata", _freeze_metadata(self.metadata, "metadata")
        )
        if self.digest:
            _validate_supplied_digest(self.digest, "digest")
            expected = self.calculate_digest()
            if self.digest != expected:
                raise InvalidDomainObservabilityContractError(
                    "supplied digest does not match snapshot content",
                    field="digest",
                )
        else:
            object.__setattr__(self, "digest", self.calculate_digest())

    def calculate_digest(self) -> str:
        payload = self.to_dict()
        payload.pop("digest")
        return _digest_payload(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "measurements": [
                measurement.to_dict() for measurement in self.measurements
            ],
            "evidence_event_ids": list(self.evidence_event_ids),
            "evidence_trace_ids": list(self.evidence_trace_ids),
            "evidence_session_ids": list(self.evidence_session_ids),
            "digest": self.digest,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainMetricsSnapshot:
        _reject_unknown_fields(
            data, {name for name in cls.__dataclass_fields__}, cls.__name__
        )
        _require_fields(data, {"generated_at", "measurements"}, cls.__name__)
        raw_digest = data.get("digest", "")
        if raw_digest:
            if not isinstance(raw_digest, str) or len(raw_digest) != _DIGEST_RE_LENGTH:
                raise DomainSerializationError(
                    "digest must be a SHA-256 hex digest string", field="digest"
                )
            if any(character not in "0123456789abcdef" for character in raw_digest):
                raise DomainSerializationError(
                    "digest must be a SHA-256 hex digest string", field="digest"
                )
        try:
            return cls(
                generated_at=datetime.fromisoformat(data["generated_at"]),
                measurements=tuple(data["measurements"]),
                evidence_event_ids=tuple(data.get("evidence_event_ids", ())),
                evidence_trace_ids=tuple(data.get("evidence_trace_ids", ())),
                evidence_session_ids=tuple(data.get("evidence_session_ids", ())),
                digest=data.get("digest", ""),
                metadata=data.get("metadata", {}),
            )
        except DomainSerializationError:
            raise
        except InvalidDomainObservabilityContractError as exc:
            raise DomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc
        except (TypeError, ValueError) as exc:
            raise DomainSerializationError(
                "invalid DomainMetricsSnapshot payload", field="data"
            ) from exc


# ── Log entry contract ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DomainObservabilityLogEntry:
    """Derived, immutable, privacy-minimized observability log entry.

    This is a read model, not a persisted log record. Only explicitly safe
    public fields extracted from canonical evidence are carried.
    """

    source_kind: str
    source_id: str
    category: str
    status: str
    occurred_at: datetime
    primary_domain: str | None = None
    supporting_domains: tuple[str, ...] = ()
    session_id: str | None = None
    duration_ms: int | float | None = None
    reference_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_kind", _safe_label(self.source_kind, "source_kind")
        )
        object.__setattr__(
            self, "source_id", _safe_identifier(self.source_id, "source_id")
        )
        object.__setattr__(self, "category", _safe_label(self.category, "category"))
        object.__setattr__(self, "status", _safe_label(self.status, "status"))
        object.__setattr__(self, "occurred_at", _aware(self.occurred_at, "occurred_at"))
        object.__setattr__(
            self, "primary_domain", _optional_str(self.primary_domain, "primary_domain")
        )
        supporting = tuple(
            _safe_identifier(item, "supporting_domains")
            for item in self.supporting_domains
        )
        object.__setattr__(self, "supporting_domains", tuple(sorted(set(supporting))))
        object.__setattr__(
            self, "session_id", _optional_str(self.session_id, "session_id")
        )
        duration = _optional_finite_number(self.duration_ms, "duration_ms")
        if duration is not None and duration < 0:
            raise InvalidDomainObservabilityContractError(
                "duration_ms must not be negative",
                field="duration_ms",
            )
        object.__setattr__(self, "duration_ms", duration)
        object.__setattr__(
            self,
            "reference_ids",
            _sorted_unique_ids(self.reference_ids, "reference_ids"),
        )
        object.__setattr__(
            self, "metadata", _freeze_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "source_id": self.source_id,
            "category": self.category,
            "status": self.status,
            "occurred_at": self.occurred_at.isoformat(),
            "primary_domain": self.primary_domain,
            "supporting_domains": list(self.supporting_domains),
            "session_id": self.session_id,
            "duration_ms": self.duration_ms,
            "reference_ids": list(self.reference_ids),
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainObservabilityLogEntry:
        _reject_unknown_fields(
            data, {name for name in cls.__dataclass_fields__}, cls.__name__
        )
        _require_fields(
            data,
            {"source_kind", "source_id", "category", "status", "occurred_at"},
            cls.__name__,
        )
        try:
            return cls(
                source_kind=data["source_kind"],
                source_id=data["source_id"],
                category=data["category"],
                status=data["status"],
                occurred_at=datetime.fromisoformat(data["occurred_at"]),
                primary_domain=data.get("primary_domain"),
                supporting_domains=tuple(data.get("supporting_domains", ())),
                session_id=data.get("session_id"),
                duration_ms=data.get("duration_ms"),
                reference_ids=tuple(data.get("reference_ids", ())),
                metadata=data.get("metadata", {}),
            )
        except DomainSerializationError:
            raise
        except InvalidDomainObservabilityContractError as exc:
            raise DomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc
        except (TypeError, ValueError) as exc:
            raise DomainSerializationError(
                "invalid DomainObservabilityLogEntry payload", field="data"
            ) from exc


# ── Health contracts ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DomainHealthFinding:
    """One structured, non-secret health finding."""

    code: str
    component: str
    severity: str
    message: str
    reference_ids: tuple[str, ...] = ()
    blocking: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _safe_identifier(self.code, "code"))
        object.__setattr__(self, "component", _safe_label(self.component, "component"))
        object.__setattr__(self, "severity", _safe_label(self.severity, "severity"))
        message = _non_empty_str(self.message, "message")
        if len(message) > 512:
            raise InvalidDomainObservabilityContractError(
                "message exceeds maximum length",
                field="message",
            )
        object.__setattr__(self, "message", message)
        object.__setattr__(
            self,
            "reference_ids",
            _sorted_unique_ids(self.reference_ids, "reference_ids"),
        )
        object.__setattr__(self, "blocking", _strict_bool(self.blocking, "blocking"))
        object.__setattr__(
            self, "metadata", _freeze_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "component": self.component,
            "severity": self.severity,
            "message": self.message,
            "reference_ids": list(self.reference_ids),
            "blocking": self.blocking,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainHealthFinding:
        _reject_unknown_fields(
            data, {name for name in cls.__dataclass_fields__}, cls.__name__
        )
        _require_fields(
            data, {"code", "component", "severity", "message"}, cls.__name__
        )
        try:
            return cls(
                code=data["code"],
                component=data["component"],
                severity=data["severity"],
                message=data["message"],
                reference_ids=tuple(data.get("reference_ids", ())),
                blocking=data.get("blocking", False),
                metadata=data.get("metadata", {}),
            )
        except DomainSerializationError:
            raise
        except InvalidDomainObservabilityContractError as exc:
            raise DomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


@dataclass(frozen=True, slots=True)
class DomainHealthResult:
    """Read-only per-domain health result with positive-verification flags.

    Every boolean means "positively verified by canonical evidence", never
    "the check merely did not raise an exception".
    """

    domain_id: str
    status: DomainHealthStatus
    manifest: bool
    registry: bool
    resources: bool
    rules: bool
    operations: bool
    workflows: bool
    permissions: bool
    dependencies: bool
    last_checked_at: datetime
    findings: tuple[DomainHealthFinding, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "domain_id", _safe_identifier(self.domain_id, "domain_id")
        )
        if not isinstance(self.status, DomainHealthStatus):
            object.__setattr__(self, "status", DomainHealthStatus(self.status))
        for name in (
            "manifest",
            "registry",
            "resources",
            "rules",
            "operations",
            "workflows",
            "permissions",
            "dependencies",
        ):
            object.__setattr__(self, name, _strict_bool(getattr(self, name), name))
        object.__setattr__(
            self,
            "last_checked_at",
            _aware(self.last_checked_at, "last_checked_at"),
        )
        findings = tuple(
            finding
            if isinstance(finding, DomainHealthFinding)
            else DomainHealthFinding.from_dict(finding)
            for finding in self.findings
        )
        object.__setattr__(self, "findings", findings)
        object.__setattr__(
            self, "metadata", _freeze_metadata(self.metadata, "metadata")
        )

        if self.status is DomainHealthStatus.HEALTHY:
            unverified = [
                name
                for name in (
                    "manifest",
                    "registry",
                    "resources",
                    "rules",
                    "operations",
                    "workflows",
                    "permissions",
                    "dependencies",
                )
                if not getattr(self, name)
            ]
            if unverified:
                raise InvalidDomainObservabilityContractError(
                    f"healthy status requires all dimensions verified: {unverified}",
                    field="status",
                )
            if any(finding.blocking for finding in findings):
                raise InvalidDomainObservabilityContractError(
                    "healthy status cannot contain a blocking finding",
                    field="findings",
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain_id": self.domain_id,
            "status": self.status.value,
            "manifest": self.manifest,
            "registry": self.registry,
            "resources": self.resources,
            "rules": self.rules,
            "operations": self.operations,
            "workflows": self.workflows,
            "permissions": self.permissions,
            "dependencies": self.dependencies,
            "last_checked_at": self.last_checked_at.isoformat(),
            "findings": [finding.to_dict() for finding in self.findings],
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainHealthResult:
        _reject_unknown_fields(
            data, {name for name in cls.__dataclass_fields__}, cls.__name__
        )
        _require_fields(
            data,
            {
                "domain_id",
                "status",
                "manifest",
                "registry",
                "resources",
                "rules",
                "operations",
                "workflows",
                "permissions",
                "dependencies",
                "last_checked_at",
            },
            cls.__name__,
        )
        try:
            return cls(
                domain_id=data["domain_id"],
                status=data["status"],
                manifest=data["manifest"],
                registry=data["registry"],
                resources=data["resources"],
                rules=data["rules"],
                operations=data["operations"],
                workflows=data["workflows"],
                permissions=data["permissions"],
                dependencies=data["dependencies"],
                last_checked_at=datetime.fromisoformat(data["last_checked_at"]),
                findings=tuple(data.get("findings", ())),
                metadata=data.get("metadata", {}),
            )
        except DomainSerializationError:
            raise
        except InvalidDomainObservabilityContractError:
            raise
        except (TypeError, ValueError) as exc:
            raise DomainSerializationError(
                "invalid DomainHealthResult payload", field="data"
            ) from exc


# ── Report contract ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class DomainObservabilityReport:
    """Ephemeral, immutable aggregate for one observability request.

    Not a stored audit log, not a replacement for DomainTrace and not a
    replacement for Phase 9 audit records.
    """

    generated_at: datetime
    log_entries: tuple[DomainObservabilityLogEntry, ...]
    metrics: DomainMetricsSnapshot
    health_results: tuple[DomainHealthResult, ...]
    source_event_ids: tuple[str, ...] = ()
    source_trace_ids: tuple[str, ...] = ()
    source_session_ids: tuple[str, ...] = ()
    findings: tuple[DomainHealthFinding, ...] = ()
    digest: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "generated_at", _aware(self.generated_at, "generated_at")
        )
        log_entries = tuple(
            entry
            if isinstance(entry, DomainObservabilityLogEntry)
            else DomainObservabilityLogEntry.from_dict(entry)
            for entry in self.log_entries
        )
        object.__setattr__(self, "log_entries", log_entries)
        metrics = (
            self.metrics
            if isinstance(self.metrics, DomainMetricsSnapshot)
            else DomainMetricsSnapshot.from_dict(self.metrics)
        )
        object.__setattr__(self, "metrics", metrics)
        health_results = tuple(
            result
            if isinstance(result, DomainHealthResult)
            else DomainHealthResult.from_dict(result)
            for result in self.health_results
        )
        domain_ids = [result.domain_id for result in health_results]
        if len(domain_ids) != len(set(domain_ids)):
            raise InvalidDomainObservabilityContractError(
                "health_results must not contain duplicate domain IDs",
                field="health_results",
            )
        object.__setattr__(self, "health_results", health_results)
        object.__setattr__(
            self,
            "source_event_ids",
            _sorted_unique_ids(self.source_event_ids, "source_event_ids"),
        )
        object.__setattr__(
            self,
            "source_trace_ids",
            _sorted_unique_ids(self.source_trace_ids, "source_trace_ids"),
        )
        object.__setattr__(
            self,
            "source_session_ids",
            _sorted_unique_ids(self.source_session_ids, "source_session_ids"),
        )
        findings = tuple(
            finding
            if isinstance(finding, DomainHealthFinding)
            else DomainHealthFinding.from_dict(finding)
            for finding in self.findings
        )
        object.__setattr__(self, "findings", findings)
        object.__setattr__(
            self, "metadata", _freeze_metadata(self.metadata, "metadata")
        )
        if self.digest:
            _validate_supplied_digest(self.digest, "digest")
            expected = self.calculate_digest()
            if self.digest != expected:
                raise InvalidDomainObservabilityContractError(
                    "supplied digest does not match report content",
                    field="digest",
                )
        else:
            object.__setattr__(self, "digest", self.calculate_digest())

    def calculate_digest(self) -> str:
        payload = self.to_dict()
        payload.pop("digest")
        return _digest_payload(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "log_entries": [entry.to_dict() for entry in self.log_entries],
            "metrics": self.metrics.to_dict(),
            "health_results": [result.to_dict() for result in self.health_results],
            "source_event_ids": list(self.source_event_ids),
            "source_trace_ids": list(self.source_trace_ids),
            "source_session_ids": list(self.source_session_ids),
            "findings": [finding.to_dict() for finding in self.findings],
            "digest": self.digest,
            "metadata": _deep_unfreeze(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainObservabilityReport:
        _reject_unknown_fields(
            data, {name for name in cls.__dataclass_fields__}, cls.__name__
        )
        _require_fields(
            data,
            {"generated_at", "log_entries", "metrics", "health_results"},
            cls.__name__,
        )
        raw_digest = data.get("digest", "")
        if raw_digest:
            if not isinstance(raw_digest, str) or len(raw_digest) != _DIGEST_RE_LENGTH:
                raise DomainSerializationError(
                    "digest must be a SHA-256 hex digest string", field="digest"
                )
            if any(character not in "0123456789abcdef" for character in raw_digest):
                raise DomainSerializationError(
                    "digest must be a SHA-256 hex digest string", field="digest"
                )
        try:
            return cls(
                generated_at=datetime.fromisoformat(data["generated_at"]),
                log_entries=tuple(data["log_entries"]),
                metrics=data["metrics"],
                health_results=tuple(data["health_results"]),
                source_event_ids=tuple(data.get("source_event_ids", ())),
                source_trace_ids=tuple(data.get("source_trace_ids", ())),
                source_session_ids=tuple(data.get("source_session_ids", ())),
                findings=tuple(data.get("findings", ())),
                digest=data.get("digest", ""),
                metadata=data.get("metadata", {}),
            )
        except DomainSerializationError:
            raise
        except InvalidDomainObservabilityContractError as exc:
            raise DomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc
        except (TypeError, ValueError) as exc:
            raise DomainSerializationError(
                "invalid DomainObservabilityReport payload", field="data"
            ) from exc


__all__ = [
    "DomainHealthFinding",
    "DomainHealthResult",
    "DomainHealthStatus",
    "DomainMetricBucket",
    "DomainMetricMeasurement",
    "DomainMetricStatus",
    "DomainMetricsSnapshot",
    "DomainObservabilityLogEntry",
    "DomainObservabilityReport",
]
