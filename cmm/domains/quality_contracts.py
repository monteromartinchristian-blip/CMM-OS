"""Phase 10.48 – domain-owned quality policy and human-review evidence.

``DomainQualityMetric`` declares *what a domain considers quality*: a weighted,
versioned, provider-independent policy dimension with an opaque evaluator
reference, a minimum score and an optional blocking flag.
``DomainQualityHumanReviewResult`` is an immutable evidence container only — it
never schedules, contacts, authenticates or approves anything.

Phase 10.48 validates and deterministically aggregates evidence produced
elsewhere. It never executes a benchmark, evaluator, model or provider.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from fractions import Fraction
from types import MappingProxyType
from typing import Any, TypeAlias

from cmm.domains.errors import (
    DomainContractValidationError,
    DomainSerializationError,
)
from cmm.domains.identifiers import DomainId, _validate_slug

__all__ = [
    "DomainQualityAssessment",
    "DomainQualityHumanReviewResult",
    "DomainQualityMetric",
    "DomainQualityMetricResult",
    "assess_domain_quality",
    "build_domain_quality_metric_result",
    "export_domain_quality_assessment",
    "import_domain_quality_assessment",
]

JsonValue: TypeAlias = (
    None | bool | int | float | str | Mapping[str, Any] | Sequence[Any]
)

_ZERO = Decimal(0)
_ONE = Decimal(1)

# ── Identity ──────────────────────────────────────────────────────────────────

_SLUG_PATTERN = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
_METRIC_ID_RE = re.compile(rf"^quality-metric:({_SLUG_PATTERN}):({_SLUG_PATTERN})$")


# ── Reserved model/provider authority keys ────────────────────────────────────
#
# Mirrors the hardened Phase 10.47 metadata boundary locally so the audited
# 10.47 module stays frozen. Only mapping keys are inspected, never values.

_EXPLICIT_RESERVED_AUTHORITY_KEYS = frozenset(
    {
        "model",
        "models",
        "model_id",
        "model_ids",
        "model_family",
        "provider",
        "providers",
        "provider_id",
        "provider_ids",
        "routing_weight",
        "routing_weights",
    }
)

_AUTHORITY_QUALIFIERS = frozenset({"candidate", "preferred", "prohibited"})
_AUTHORITY_SUBJECTS = frozenset({"model", "models", "provider", "providers"})
_AUTHORITY_ID_SUFFIXES = frozenset({"id", "ids"})
_AUTHORITY_PREFERENCE_TOKENS = frozenset(
    {
        "candidate",
        "candidates",
        "preference",
        "preferences",
        "preferred",
        "prohibited",
    }
)

_CAMEL_BOUNDARY_1 = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_CAMEL_BOUNDARY_2 = re.compile(r"(?<=[A-Z])(?=[A-Z][a-z])")
_NON_IDENTIFIER = re.compile(r"[^A-Za-z0-9]+")


def _normalize_key(key: str) -> str:
    """Normalize a metadata key so casing/style variants cannot bypass the check."""
    key = _CAMEL_BOUNDARY_2.sub("_", _CAMEL_BOUNDARY_1.sub("_", key))
    return _NON_IDENTIFIER.sub("_", key).strip("_").lower()


def _is_reserved_authority_key(normalized_key: str) -> bool:
    """Deterministic, auditable model/provider authority-key predicate."""
    if normalized_key in _EXPLICIT_RESERVED_AUTHORITY_KEYS:
        return True

    parts = normalized_key.split("_")
    head = parts[0]
    tail = parts[-1]

    if (
        head in _AUTHORITY_QUALIFIERS
        and len(parts) in (2, 3)
        and parts[1] in _AUTHORITY_SUBJECTS
        and (len(parts) == 2 or tail in _AUTHORITY_ID_SUFFIXES)
    ):
        return True

    if (
        head in _AUTHORITY_SUBJECTS
        and len(parts) == 2
        and tail in _AUTHORITY_PREFERENCE_TOKENS
    ):
        return True

    if (
        head in _AUTHORITY_SUBJECTS
        and len(parts) == 3
        and parts[1] in _AUTHORITY_QUALIFIERS
        and tail in _AUTHORITY_ID_SUFFIXES
    ):
        return True

    return (
        head == "routing"
        and len(parts) in (2, 3)
        and parts[1] in _AUTHORITY_SUBJECTS
        and (len(parts) == 2 or tail in _AUTHORITY_ID_SUFFIXES)
    )


def _reject_reserved_authority_keys(value: Any, field_name: str) -> None:
    """Reject model/provider-selection keys in metadata at any depth."""
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if isinstance(key, str) and _is_reserved_authority_key(_normalize_key(key)):
                raise DomainContractValidationError(
                    f"{field_name} must not declare model/provider authority key {key!r}",
                    field=field_name,
                    details={"reserved_key": key},
                )
            _reject_reserved_authority_keys(nested, field_name)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in value:
            _reject_reserved_authority_keys(nested, field_name)


# ── JSON-safety, freezing and thawing ─────────────────────────────────────────


def _require_json_value(value: Any, field_name: str) -> None:
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise DomainContractValidationError(
                f"{field_name} must not contain non-finite floats",
                field=field_name,
                details={"value": repr(value)},
            )
        return
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str) or isinstance(key, bool):
                raise DomainContractValidationError(
                    f"{field_name} keys must be strings", field=field_name
                )
            _require_json_value(nested, field_name)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in value:
            _require_json_value(nested, field_name)
        return
    raise DomainContractValidationError(
        f"{field_name} must be JSON-safe, got {type(value).__name__}",
        field=field_name,
    )


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_json(val) for key, val in value.items()})
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return tuple(_freeze_json(val) for val in value)
    return value


def _thaw_json(value: Any) -> Any:
    if isinstance(value, (MappingProxyType, Mapping)):
        return {key: _thaw_json(val) for key, val in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_thaw_json(val) for val in value]
    return value


def _require_quality_metadata(
    value: Any, field_name: str
) -> MappingProxyType[str, Any]:
    """Validate descriptive audit metadata and deep-freeze it.

    Rejects non-JSON values and reserved model/provider/routing authority keys
    (inspecting mapping keys only).
    """
    if not isinstance(value, Mapping):
        raise DomainContractValidationError(
            f"{field_name} must be a mapping", field=field_name
        )
    _require_json_value(value, field_name)
    _reject_reserved_authority_keys(value, field_name)
    return _freeze_json(value)


# ── Primitive validation ──────────────────────────────────────────────────────


def _require_non_empty_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DomainContractValidationError(
            f"{field_name} must be a non-empty string", field=field_name
        )
    return value.strip()


def _require_optional_str(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty_str(value, field_name)


def _require_strict_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise DomainContractValidationError(
            f"{field_name} must be a boolean (True or False), "
            f"got {type(value).__name__}: {value!r}",
            field=field_name,
        )
    return value


def _require_decimal(
    value: Any,
    field_name: str,
    *,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
    exclusive_minimum: Decimal | None = None,
) -> Decimal:
    """Validate a strict, finite ``Decimal`` inside its declared range."""
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise DomainContractValidationError(
            f"{field_name} must be a Decimal, got {type(value).__name__}: {value!r}",
            field=field_name,
        )
    if not value.is_finite():
        raise DomainContractValidationError(
            f"{field_name} must be finite, got {value!r}", field=field_name
        )
    if exclusive_minimum is not None and not value > exclusive_minimum:
        raise DomainContractValidationError(
            f"{field_name} must be greater than {exclusive_minimum}, got {value!r}",
            field=field_name,
        )
    if minimum is not None and value < minimum:
        raise DomainContractValidationError(
            f"{field_name} must be greater than or equal to {minimum}, got {value!r}",
            field=field_name,
        )
    if maximum is not None and value > maximum:
        raise DomainContractValidationError(
            f"{field_name} must be less than or equal to {maximum}, got {value!r}",
            field=field_name,
        )
    return value


def _require_optional_decimal(
    value: Any,
    field_name: str,
    *,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
) -> Decimal | None:
    if value is None:
        return None
    return _require_decimal(value, field_name, minimum=minimum, maximum=maximum)


def _require_str_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise DomainContractValidationError(
            f"{field_name} must be a tuple or list of strings", field=field_name
        )
    return tuple(_require_non_empty_str(item, field_name) for item in value)


def _coerce_domain_id(value: Any, field_name: str) -> DomainId:
    if isinstance(value, DomainId):
        return value
    if isinstance(value, str):
        try:
            return DomainId.from_str(value)
        except DomainSerializationError as exc:
            raise DomainContractValidationError(
                f"{field_name} must be a canonical 'domain:<slug>' string",
                field=field_name,
            ) from exc
    raise DomainContractValidationError(
        f"{field_name} must be a DomainId or canonical 'domain:<slug>' string",
        field=field_name,
    )


def _require_quality_metric_id(value: Any, domain_id: DomainId, field_name: str) -> str:
    identifier = _require_non_empty_str(value, field_name)
    match = _METRIC_ID_RE.match(identifier)
    if match is None:
        raise DomainContractValidationError(
            "must match 'quality-metric:<domain-slug>:<metric-slug>'",
            field=field_name,
            details={"value": identifier},
        )
    embedded_slug = match.group(1)
    _validate_slug(embedded_slug, field_name)
    if embedded_slug != domain_id.slug:
        raise DomainContractValidationError(
            f"{field_name} domain '{embedded_slug}' must match domain_id "
            f"'{domain_id.slug}'",
            field=field_name,
            details={"embedded": embedded_slug, "domain_id": domain_id.slug},
        )
    return identifier


# ── Canonical decimal text ────────────────────────────────────────────────────


def _canonical_decimal_text(value: Decimal) -> str:
    """Exact, context-independent fixed-point text for a quality decimal.

    Built directly from the stored coefficient and exponent so ambient
    ``decimal`` context precision can never round or reformat the value.
    """
    if value == 0:
        return "0"

    _, digits, exponent = value.as_tuple()
    coefficient = "".join(str(digit) for digit in digits)

    if exponent >= 0:
        text = coefficient + "0" * exponent
    else:
        point = len(coefficient) + exponent
        if point > 0:
            text = f"{coefficient[:point]}.{coefficient[point:]}"
        else:
            text = f"0.{'0' * -point}{coefficient}"

    if "." in text:
        text = text.rstrip("0").rstrip(".")

    return text


def _decimal_from_dict(
    value: Any,
    field_name: str,
    *,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
    exclusive_minimum: Decimal | None = None,
) -> Decimal:
    """Parse a canonical decimal string (or an already-validated Decimal)."""
    if isinstance(value, bool):
        raise DomainSerializationError(
            f"{field_name} must be a decimal string, got bool", field=field_name
        )
    if isinstance(value, Decimal):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise DomainSerializationError(
                f"{field_name} must be a canonical decimal string, got {value!r}",
                field=field_name,
            ) from exc
    else:
        raise DomainSerializationError(
            f"{field_name} must be a decimal string, got {type(value).__name__}",
            field=field_name,
        )
    try:
        return _require_decimal(
            parsed,
            field_name,
            minimum=minimum,
            maximum=maximum,
            exclusive_minimum=exclusive_minimum,
        )
    except DomainContractValidationError as exc:
        raise DomainSerializationError(
            exc.message, field=exc.field, details=dict(exc.details)
        ) from exc


def _optional_decimal_from_dict(
    value: Any,
    field_name: str,
    *,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
) -> Decimal | None:
    if value is None:
        return None
    return _decimal_from_dict(value, field_name, minimum=minimum, maximum=maximum)


# ── Exact, context-independent weighted mean ──────────────────────────────────


def _terminating_decimal(value: Fraction) -> Decimal | None:
    """Exactly reconstruct a terminating ``Fraction`` as ``Decimal``.

    Returns ``None`` when the reduced denominator is not ``2**a * 5**b``.
    """
    numerator = value.numerator
    denominator = value.denominator

    twos = 0
    while denominator % 2 == 0:
        denominator //= 2
        twos += 1
    fives = 0
    while denominator % 5 == 0:
        denominator //= 5
        fives += 1
    if denominator != 1:
        return None

    scale = max(twos, fives)
    scaled = numerator * (2 ** (scale - twos)) * (5 ** (scale - fives))
    sign = 1 if scaled < 0 else 0
    digits = tuple(int(char) for char in str(abs(scaled)))
    return Decimal((sign, digits, -scale))


def _bounded_decimal(numerator: Fraction, denominator: Fraction) -> Decimal:
    """Deterministic, context-independent conversion of a non-terminating ratio.

    Precision is derived from the operand magnitudes, so the ambient decimal
    context can never change the outcome. The process-global context is never
    mutated.
    """
    precision = max(
        28,
        len(str(abs(numerator.numerator)))
        + len(str(numerator.denominator))
        + len(str(abs(denominator.numerator)))
        + len(str(denominator.denominator))
        + 8,
    )
    with localcontext() as ctx:
        ctx.prec = precision
        ctx.rounding = ROUND_HALF_EVEN
        return Decimal(numerator.numerator * denominator.denominator) / Decimal(
            numerator.denominator * denominator.numerator
        )


def _weighted_mean(terms: Sequence[tuple[Decimal, Decimal]]) -> Decimal:
    """Normalized weighted mean ``sum(value * weight) / sum(weight)``.

    Computed with exact rational arithmetic and reconstructed as ``Decimal``,
    so the ambient decimal context cannot change the result. Finite ``Decimal``
    operands normally yield a terminating result; a non-terminating ratio is
    rounded deterministically instead.
    """
    numerator = Fraction(0)
    denominator = Fraction(0)
    for value, weight in terms:
        numerator += Fraction(value) * Fraction(weight)
        denominator += Fraction(weight)
    if denominator == 0:
        raise DomainContractValidationError(
            "quality weights must not total zero", field="metrics"
        )
    ratio = numerator / denominator
    exact = _terminating_decimal(ratio)
    if exact is not None:
        return exact
    return _bounded_decimal(numerator, denominator)


# ── JSON helpers for deserialization ──────────────────────────────────────────


def _reject_unknown_fields(
    data: Mapping[str, Any], known: frozenset[str], cls_name: str
) -> None:
    unknown = set(data.keys()) - known
    if unknown:
        raise DomainSerializationError(
            f"{cls_name}.from_dict got unknown fields: {sorted(unknown)}",
            field="data",
            details={"unknown_fields": sorted(unknown)},
        )


def _wrap_validation_error(
    exc: DomainContractValidationError,
) -> DomainSerializationError:
    return DomainSerializationError(
        exc.message, field=exc.field, details=dict(exc.details)
    )


# ── DomainQualityMetric ───────────────────────────────────────────────────────

_METRIC_KNOWN = frozenset(
    {
        "id",
        "domain_id",
        "schema_version",
        "version",
        "name",
        "weight",
        "evaluator_id",
        "minimum_score",
        "blocking",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainQualityMetric:
    """Immutable, versioned, provider-independent declaration of a quality dimension."""

    id: str
    domain_id: DomainId
    schema_version: str
    version: str
    name: str
    weight: Decimal
    evaluator_id: str
    minimum_score: Decimal
    blocking: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        domain_id = _coerce_domain_id(self.domain_id, "domain_id")
        object.__setattr__(self, "domain_id", domain_id)
        object.__setattr__(
            self, "id", _require_quality_metric_id(self.id, domain_id, "id")
        )
        object.__setattr__(
            self,
            "schema_version",
            _require_non_empty_str(self.schema_version, "schema_version"),
        )
        object.__setattr__(
            self, "version", _require_non_empty_str(self.version, "version")
        )
        object.__setattr__(self, "name", _require_non_empty_str(self.name, "name"))
        object.__setattr__(
            self,
            "weight",
            _require_decimal(
                self.weight, "weight", exclusive_minimum=_ZERO, maximum=_ONE
            ),
        )
        object.__setattr__(
            self,
            "evaluator_id",
            _require_non_empty_str(self.evaluator_id, "evaluator_id"),
        )
        object.__setattr__(
            self,
            "minimum_score",
            _require_decimal(
                self.minimum_score, "minimum_score", minimum=_ZERO, maximum=_ONE
            ),
        )
        object.__setattr__(
            self, "blocking", _require_strict_bool(self.blocking, "blocking")
        )
        object.__setattr__(
            self, "metadata", _require_quality_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize deterministically to a JSON-compatible dictionary."""
        return {
            "id": self.id,
            "domain_id": str(self.domain_id),
            "schema_version": self.schema_version,
            "version": self.version,
            "name": self.name,
            "weight": _canonical_decimal_text(self.weight),
            "evaluator_id": self.evaluator_id,
            "minimum_score": _canonical_decimal_text(self.minimum_score),
            "blocking": self.blocking,
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainQualityMetric:
        """Deserialize strictly, rejecting unknown or forbidden fields."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainQualityMetric.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _METRIC_KNOWN, "DomainQualityMetric")
        missing = {
            "id",
            "domain_id",
            "schema_version",
            "version",
            "name",
            "weight",
            "evaluator_id",
            "minimum_score",
        } - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainQualityMetric.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                id=data["id"],
                domain_id=data["domain_id"],
                schema_version=data["schema_version"],
                version=data["version"],
                name=data["name"],
                weight=_decimal_from_dict(
                    data["weight"],
                    "weight",
                    exclusive_minimum=_ZERO,
                    maximum=_ONE,
                ),
                evaluator_id=data["evaluator_id"],
                minimum_score=_decimal_from_dict(
                    data["minimum_score"], "minimum_score", minimum=_ZERO, maximum=_ONE
                ),
                blocking=data.get("blocking", False),
                metadata=data.get("metadata", {}),
            )
        except DomainContractValidationError as exc:
            raise _wrap_validation_error(exc) from exc


# ── DomainQualityHumanReviewResult ────────────────────────────────────────────

_REVIEW_KNOWN = frozenset(
    {
        "id",
        "schema_version",
        "status",
        "score",
        "confidence",
        "reviewer_ref",
        "notes",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainQualityHumanReviewResult:
    """Immutable human-review *evidence*: stored, never scheduled or executed."""

    id: str
    schema_version: str
    status: str
    score: Decimal | None = None
    confidence: Decimal | None = None
    reviewer_ref: str | None = None
    notes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_non_empty_str(self.id, "id"))
        object.__setattr__(
            self,
            "schema_version",
            _require_non_empty_str(self.schema_version, "schema_version"),
        )
        object.__setattr__(
            self, "status", _require_non_empty_str(self.status, "status")
        )
        object.__setattr__(
            self,
            "score",
            _require_optional_decimal(self.score, "score", minimum=_ZERO, maximum=_ONE),
        )
        object.__setattr__(
            self,
            "confidence",
            _require_optional_decimal(
                self.confidence, "confidence", minimum=_ZERO, maximum=_ONE
            ),
        )
        object.__setattr__(
            self,
            "reviewer_ref",
            _require_optional_str(self.reviewer_ref, "reviewer_ref"),
        )
        object.__setattr__(self, "notes", _require_str_tuple(self.notes, "notes"))
        object.__setattr__(
            self, "metadata", _require_quality_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize deterministically to a JSON-compatible dictionary."""
        return {
            "id": self.id,
            "schema_version": self.schema_version,
            "status": self.status,
            "score": (
                _canonical_decimal_text(self.score) if self.score is not None else None
            ),
            "confidence": (
                _canonical_decimal_text(self.confidence)
                if self.confidence is not None
                else None
            ),
            "reviewer_ref": self.reviewer_ref,
            "notes": list(self.notes),
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainQualityHumanReviewResult:
        """Deserialize strictly, rejecting unknown or forbidden fields."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainQualityHumanReviewResult.from_dict requires a mapping",
                field="data",
            )
        _reject_unknown_fields(data, _REVIEW_KNOWN, "DomainQualityHumanReviewResult")
        missing = {"id", "schema_version", "status"} - set(data.keys())
        if missing:
            raise DomainSerializationError(
                "DomainQualityHumanReviewResult.from_dict missing required "
                f"fields: {sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                id=data["id"],
                schema_version=data["schema_version"],
                status=data["status"],
                score=_optional_decimal_from_dict(
                    data.get("score"), "score", minimum=_ZERO, maximum=_ONE
                ),
                confidence=_optional_decimal_from_dict(
                    data.get("confidence"), "confidence", minimum=_ZERO, maximum=_ONE
                ),
                reviewer_ref=data.get("reviewer_ref"),
                notes=tuple(data.get("notes", ()) or ()),
                metadata=data.get("metadata", {}),
            )
        except DomainContractValidationError as exc:
            raise _wrap_validation_error(exc) from exc


# ── DomainQualityMetricResult ─────────────────────────────────────────────────

_RESULT_KNOWN = frozenset(
    {
        "metric_id",
        "domain_id",
        "schema_version",
        "metric_version",
        "metric_name",
        "score",
        "weight",
        "minimum_score",
        "blocking",
        "evaluator_id",
        "evaluator_version",
        "confidence",
        "human_review_results",
        "metadata",
    }
)


def _require_review_tuple(value: Any, field_name: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise DomainContractValidationError(
            f"{field_name} must be a tuple or list of DomainQualityHumanReviewResult",
            field=field_name,
        )
    reviews: list[Any] = []
    for index, item in enumerate(value):
        if not isinstance(item, DomainQualityHumanReviewResult):
            raise DomainContractValidationError(
                f"{field_name}[{index}] must be a DomainQualityHumanReviewResult, "
                f"got {type(item).__name__}",
                field=field_name,
            )
        reviews.append(item)
    review_ids = [review.id for review in reviews]
    if len(set(review_ids)) != len(review_ids):
        raise DomainContractValidationError(
            f"{field_name} must not contain duplicate review IDs", field=field_name
        )
    return tuple(reviews)


@dataclass(frozen=True, slots=True)
class DomainQualityMetricResult:
    """Immutable evidence that snapshots the exact policy that produced it."""

    metric_id: str
    domain_id: DomainId
    schema_version: str
    metric_version: str
    metric_name: str
    score: Decimal
    weight: Decimal
    minimum_score: Decimal
    blocking: bool
    evaluator_id: str
    evaluator_version: str
    confidence: Decimal
    human_review_results: tuple[DomainQualityHumanReviewResult, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        domain_id = _coerce_domain_id(self.domain_id, "domain_id")
        object.__setattr__(self, "domain_id", domain_id)
        object.__setattr__(
            self,
            "metric_id",
            _require_quality_metric_id(self.metric_id, domain_id, "metric_id"),
        )
        object.__setattr__(
            self,
            "schema_version",
            _require_non_empty_str(self.schema_version, "schema_version"),
        )
        object.__setattr__(
            self,
            "metric_version",
            _require_non_empty_str(self.metric_version, "metric_version"),
        )
        object.__setattr__(
            self, "metric_name", _require_non_empty_str(self.metric_name, "metric_name")
        )
        object.__setattr__(
            self,
            "score",
            _require_decimal(self.score, "score", minimum=_ZERO, maximum=_ONE),
        )
        object.__setattr__(
            self,
            "weight",
            _require_decimal(
                self.weight, "weight", exclusive_minimum=_ZERO, maximum=_ONE
            ),
        )
        object.__setattr__(
            self,
            "minimum_score",
            _require_decimal(
                self.minimum_score, "minimum_score", minimum=_ZERO, maximum=_ONE
            ),
        )
        object.__setattr__(
            self, "blocking", _require_strict_bool(self.blocking, "blocking")
        )
        object.__setattr__(
            self,
            "evaluator_id",
            _require_non_empty_str(self.evaluator_id, "evaluator_id"),
        )
        object.__setattr__(
            self,
            "evaluator_version",
            _require_non_empty_str(self.evaluator_version, "evaluator_version"),
        )
        object.__setattr__(
            self,
            "confidence",
            _require_decimal(
                self.confidence, "confidence", minimum=_ZERO, maximum=_ONE
            ),
        )
        object.__setattr__(
            self,
            "human_review_results",
            _require_review_tuple(self.human_review_results, "human_review_results"),
        )
        object.__setattr__(
            self, "metadata", _require_quality_metadata(self.metadata, "metadata")
        )

    @property
    def threshold_passed(self) -> bool:
        """Derived: the score met or exceeded the declared minimum."""
        return self.score >= self.minimum_score

    @property
    def blocking_failure(self) -> bool:
        """Derived: a blocking metric missed its declared minimum."""
        return self.blocking and not self.threshold_passed

    def to_dict(self) -> dict[str, Any]:
        """Serialize deterministically to a JSON-compatible dictionary."""
        return {
            "metric_id": self.metric_id,
            "domain_id": str(self.domain_id),
            "schema_version": self.schema_version,
            "metric_version": self.metric_version,
            "metric_name": self.metric_name,
            "score": _canonical_decimal_text(self.score),
            "weight": _canonical_decimal_text(self.weight),
            "minimum_score": _canonical_decimal_text(self.minimum_score),
            "blocking": self.blocking,
            "evaluator_id": self.evaluator_id,
            "evaluator_version": self.evaluator_version,
            "confidence": _canonical_decimal_text(self.confidence),
            "human_review_results": [
                review.to_dict() for review in self.human_review_results
            ],
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainQualityMetricResult:
        """Deserialize strictly, rejecting unknown or forbidden fields."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainQualityMetricResult.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _RESULT_KNOWN, "DomainQualityMetricResult")
        missing = {
            "metric_id",
            "domain_id",
            "schema_version",
            "metric_version",
            "metric_name",
            "score",
            "weight",
            "minimum_score",
            "blocking",
            "evaluator_id",
            "evaluator_version",
            "confidence",
        } - set(data.keys())
        if missing:
            raise DomainSerializationError(
                "DomainQualityMetricResult.from_dict missing required fields: "
                f"{sorted(missing)}",
                field="data",
            )
        reviews_raw = data.get("human_review_results", ())
        if reviews_raw is None:
            reviews_raw = ()
        if isinstance(reviews_raw, (str, bytes, bytearray)) or not isinstance(
            reviews_raw, (list, tuple)
        ):
            raise DomainSerializationError(
                "human_review_results must be a list", field="human_review_results"
            )
        reviews: list[DomainQualityHumanReviewResult] = []
        for index, item in enumerate(reviews_raw):
            if not isinstance(item, Mapping):
                raise DomainSerializationError(
                    f"human_review_results[{index}] must be a mapping, "
                    f"got {type(item).__name__}",
                    field=f"human_review_results[{index}]",
                )
            try:
                reviews.append(DomainQualityHumanReviewResult.from_dict(dict(item)))
            except DomainContractValidationError as exc:
                raise _wrap_validation_error(exc) from exc
        try:
            return cls(
                metric_id=data["metric_id"],
                domain_id=data["domain_id"],
                schema_version=data["schema_version"],
                metric_version=data["metric_version"],
                metric_name=data["metric_name"],
                score=_decimal_from_dict(
                    data["score"], "score", minimum=_ZERO, maximum=_ONE
                ),
                weight=_decimal_from_dict(
                    data["weight"], "weight", exclusive_minimum=_ZERO, maximum=_ONE
                ),
                minimum_score=_decimal_from_dict(
                    data["minimum_score"], "minimum_score", minimum=_ZERO, maximum=_ONE
                ),
                blocking=data["blocking"],
                evaluator_id=data["evaluator_id"],
                evaluator_version=data["evaluator_version"],
                confidence=_decimal_from_dict(
                    data["confidence"], "confidence", minimum=_ZERO, maximum=_ONE
                ),
                human_review_results=tuple(reviews),
                metadata=data.get("metadata", {}),
            )
        except DomainContractValidationError as exc:
            raise _wrap_validation_error(exc) from exc


def build_domain_quality_metric_result(
    metric: DomainQualityMetric,
    *,
    score: Decimal,
    evaluator_version: str,
    confidence: Decimal,
    human_review_results: Sequence[DomainQualityHumanReviewResult] = (),
    metadata: Mapping[str, Any] | None = None,
) -> DomainQualityMetricResult:
    """Snapshot a declared metric policy into supplied evidence.

    Only the *observed* values (``score``, ``evaluator_version``,
    ``confidence``, evidence, metadata) come from the caller. Identity,
    version, name, weight, threshold, blocking flag and evaluator ID are
    copied from the declared metric and cannot be overridden.
    """
    if not isinstance(metric, DomainQualityMetric):
        raise DomainContractValidationError(
            "metric must be a DomainQualityMetric", field="metric"
        )
    return DomainQualityMetricResult(
        metric_id=metric.id,
        domain_id=metric.domain_id,
        schema_version=metric.schema_version,
        metric_version=metric.version,
        metric_name=metric.name,
        score=score,
        weight=metric.weight,
        minimum_score=metric.minimum_score,
        blocking=metric.blocking,
        evaluator_id=metric.evaluator_id,
        evaluator_version=evaluator_version,
        confidence=confidence,
        human_review_results=tuple(human_review_results),
        metadata={} if metadata is None else metadata,
    )


# ── DomainQualityAssessment ───────────────────────────────────────────────────

_ASSESSMENT_KNOWN = frozenset(
    {
        "domain_id",
        "schema_version",
        "metric_results",
        "aggregate_score",
        "confidence",
        "blocking_failures",
        "passed",
        "metadata",
    }
)


def _require_metric_result_tuple(
    value: Any, field_name: str
) -> tuple[DomainQualityMetricResult, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise DomainContractValidationError(
            f"{field_name} must be a tuple or list of DomainQualityMetricResult",
            field=field_name,
        )
    if not value:
        raise DomainContractValidationError(
            f"{field_name} must contain at least one result", field=field_name
        )
    results: list[DomainQualityMetricResult] = []
    for index, item in enumerate(value):
        if not isinstance(item, DomainQualityMetricResult):
            raise DomainContractValidationError(
                f"{field_name}[{index}] must be a DomainQualityMetricResult, "
                f"got {type(item).__name__}",
                field=field_name,
            )
        results.append(item)
    result_ids = [result.metric_id for result in results]
    if len(set(result_ids)) != len(result_ids):
        raise DomainContractValidationError(
            f"{field_name} must not contain duplicate metric IDs", field=field_name
        )
    return tuple(results)


@dataclass(frozen=True, slots=True)
class DomainQualityAssessment:
    """Immutable, deterministic aggregate of already-produced metric evidence."""

    domain_id: DomainId
    schema_version: str
    metric_results: tuple[DomainQualityMetricResult, ...]
    aggregate_score: Decimal
    confidence: Decimal
    blocking_failures: tuple[str, ...]
    passed: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        domain_id = _coerce_domain_id(self.domain_id, "domain_id")
        object.__setattr__(self, "domain_id", domain_id)
        object.__setattr__(
            self,
            "schema_version",
            _require_non_empty_str(self.schema_version, "schema_version"),
        )
        results = _require_metric_result_tuple(self.metric_results, "metric_results")
        object.__setattr__(self, "metric_results", results)
        for index, result in enumerate(results):
            if result.domain_id != domain_id:
                raise DomainContractValidationError(
                    f"metric_results[{index}] domain_id '{result.domain_id}' must "
                    f"match assessment domain_id '{domain_id}'",
                    field="metric_results",
                )

        expected_aggregate = _weighted_mean(
            [(result.score, result.weight) for result in results]
        )
        expected_confidence = _weighted_mean(
            [(result.confidence, result.weight) for result in results]
        )
        expected_failures = tuple(
            result.metric_id for result in results if result.blocking_failure
        )

        aggregate_score = _require_decimal(
            self.aggregate_score, "aggregate_score", minimum=_ZERO, maximum=_ONE
        )
        confidence = _require_decimal(
            self.confidence, "confidence", minimum=_ZERO, maximum=_ONE
        )
        if aggregate_score != expected_aggregate:
            raise DomainContractValidationError(
                "aggregate_score must equal the canonical weighted mean "
                f"{expected_aggregate}, got {aggregate_score}",
                field="aggregate_score",
            )
        if confidence != expected_confidence:
            raise DomainContractValidationError(
                "confidence must equal the canonical weighted mean "
                f"{expected_confidence}, got {confidence}",
                field="confidence",
            )
        object.__setattr__(self, "aggregate_score", aggregate_score)
        object.__setattr__(self, "confidence", confidence)

        blocking_failures = _require_str_tuple(
            self.blocking_failures, "blocking_failures"
        )
        if blocking_failures != expected_failures:
            raise DomainContractValidationError(
                "blocking_failures must equal the canonical derived failures "
                f"{expected_failures}",
                field="blocking_failures",
            )
        object.__setattr__(self, "blocking_failures", blocking_failures)

        passed = _require_strict_bool(self.passed, "passed")
        if passed is not (not expected_failures):
            raise DomainContractValidationError(
                f"passed must be {not expected_failures} for this evidence",
                field="passed",
            )
        object.__setattr__(self, "passed", passed)
        object.__setattr__(
            self, "metadata", _require_quality_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize deterministically to a JSON-compatible dictionary."""
        return {
            "domain_id": str(self.domain_id),
            "schema_version": self.schema_version,
            "metric_results": [result.to_dict() for result in self.metric_results],
            "aggregate_score": _canonical_decimal_text(self.aggregate_score),
            "confidence": _canonical_decimal_text(self.confidence),
            "blocking_failures": list(self.blocking_failures),
            "passed": self.passed,
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainQualityAssessment:
        """Deserialize strictly, rejecting unknown or forbidden fields."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainQualityAssessment.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _ASSESSMENT_KNOWN, "DomainQualityAssessment")
        missing = {
            "domain_id",
            "schema_version",
            "metric_results",
            "aggregate_score",
            "confidence",
            "blocking_failures",
            "passed",
        } - set(data.keys())
        if missing:
            raise DomainSerializationError(
                "DomainQualityAssessment.from_dict missing required fields: "
                f"{sorted(missing)}",
                field="data",
            )
        results_raw = data["metric_results"]
        if isinstance(results_raw, (str, bytes, bytearray)) or not isinstance(
            results_raw, (list, tuple)
        ):
            raise DomainSerializationError(
                "metric_results must be a list", field="metric_results"
            )
        results: list[DomainQualityMetricResult] = []
        for index, item in enumerate(results_raw):
            if not isinstance(item, Mapping):
                raise DomainSerializationError(
                    f"metric_results[{index}] must be a mapping, "
                    f"got {type(item).__name__}",
                    field=f"metric_results[{index}]",
                )
            try:
                results.append(DomainQualityMetricResult.from_dict(dict(item)))
            except DomainContractValidationError as exc:
                raise _wrap_validation_error(exc) from exc

        blocking_failures_raw = data["blocking_failures"]
        if isinstance(blocking_failures_raw, (str, bytes, bytearray)) or not isinstance(
            blocking_failures_raw, (list, tuple)
        ):
            raise DomainSerializationError(
                "blocking_failures must be a list", field="blocking_failures"
            )
        try:
            return cls(
                domain_id=data["domain_id"],
                schema_version=data["schema_version"],
                metric_results=tuple(results),
                aggregate_score=_decimal_from_dict(
                    data["aggregate_score"],
                    "aggregate_score",
                    minimum=_ZERO,
                    maximum=_ONE,
                ),
                confidence=_decimal_from_dict(
                    data["confidence"], "confidence", minimum=_ZERO, maximum=_ONE
                ),
                blocking_failures=tuple(blocking_failures_raw),
                passed=data["passed"],
                metadata=data.get("metadata", {}),
            )
        except DomainContractValidationError as exc:
            raise _wrap_validation_error(exc) from exc


def _require_policy_binding(
    metric: DomainQualityMetric, result: DomainQualityMetricResult
) -> None:
    """Fail closed unless the evidence snapshots the declared policy exactly."""
    if result.domain_id != metric.domain_id:
        raise DomainContractValidationError(
            f"result '{result.metric_id}' domain_id '{result.domain_id}' must match "
            f"declared domain '{metric.domain_id}'",
            field="metric_results",
        )
    mismatches: list[str] = []
    if result.metric_version != metric.version:
        mismatches.append("metric_version")
    if result.metric_name != metric.name:
        mismatches.append("metric_name")
    if result.weight != metric.weight:
        mismatches.append("weight")
    if result.minimum_score != metric.minimum_score:
        mismatches.append("minimum_score")
    if result.blocking is not metric.blocking:
        mismatches.append("blocking")
    if result.evaluator_id != metric.evaluator_id:
        mismatches.append("evaluator_id")
    if mismatches:
        raise DomainContractValidationError(
            f"result '{result.metric_id}' does not match the declared policy "
            f"(fields: {sorted(mismatches)})",
            field="metric_results",
            details={"metric_id": result.metric_id, "fields": sorted(mismatches)},
        )


def assess_domain_quality(
    metrics: Sequence[DomainQualityMetric],
    results: Sequence[DomainQualityMetricResult],
    *,
    metadata: Mapping[str, Any] | None = None,
) -> DomainQualityAssessment:
    """Deterministically aggregate already-produced evidence for a declared policy.

    Validation and arithmetic only: no benchmark, evaluator, model or provider
    is ever executed, and the ambient decimal context cannot change the result.
    """
    if isinstance(metrics, (str, bytes, bytearray)) or not isinstance(
        metrics, Sequence
    ):
        raise DomainContractValidationError(
            "metrics must be a tuple or list of DomainQualityMetric", field="metrics"
        )
    if not metrics:
        raise DomainContractValidationError(
            "metrics must contain at least one declared metric", field="metrics"
        )
    declared: list[DomainQualityMetric] = []
    for index, metric in enumerate(metrics):
        if not isinstance(metric, DomainQualityMetric):
            raise DomainContractValidationError(
                f"metrics[{index}] must be a DomainQualityMetric, "
                f"got {type(metric).__name__}",
                field="metrics",
            )
        declared.append(metric)
    declared_ids = [metric.id for metric in declared]
    if len(set(declared_ids)) != len(declared_ids):
        raise DomainContractValidationError(
            "metrics must not contain duplicate metric IDs", field="metrics"
        )
    domain_id = declared[0].domain_id
    for metric in declared:
        if metric.domain_id != domain_id:
            raise DomainContractValidationError(
                "all declared metrics must belong to the same domain",
                field="metrics",
            )

    if isinstance(results, (str, bytes, bytearray)) or not isinstance(
        results, Sequence
    ):
        raise DomainContractValidationError(
            "results must be a tuple or list of DomainQualityMetricResult",
            field="results",
        )
    provided: list[DomainQualityMetricResult] = []
    for index, result in enumerate(results):
        if not isinstance(result, DomainQualityMetricResult):
            raise DomainContractValidationError(
                f"results[{index}] must be a DomainQualityMetricResult, "
                f"got {type(result).__name__}",
                field="results",
            )
        provided.append(result)
    provided_ids = [result.metric_id for result in provided]
    if len(set(provided_ids)) != len(provided_ids):
        raise DomainContractValidationError(
            "results must not contain duplicate metric IDs", field="results"
        )

    declared_set = set(declared_ids)
    provided_set = set(provided_ids)
    missing = sorted(declared_set - provided_set)
    if missing:
        raise DomainContractValidationError(
            f"missing declared metric results: {missing}",
            field="results",
            details={"missing": missing},
        )
    unexpected = sorted(provided_set - declared_set)
    if unexpected:
        raise DomainContractValidationError(
            f"unexpected metric results: {unexpected}",
            field="results",
            details={"unexpected": unexpected},
        )

    by_id = {result.metric_id: result for result in provided}
    ordered: list[DomainQualityMetricResult] = []
    for metric in declared:
        result = by_id[metric.id]
        _require_policy_binding(metric, result)
        ordered.append(result)

    aggregate_score = _weighted_mean(
        [(result.score, result.weight) for result in ordered]
    )
    confidence = _weighted_mean(
        [(result.confidence, result.weight) for result in ordered]
    )
    blocking_failures = tuple(
        result.metric_id for result in ordered if result.blocking_failure
    )

    return DomainQualityAssessment(
        domain_id=domain_id,
        schema_version=declared[0].schema_version,
        metric_results=tuple(ordered),
        aggregate_score=aggregate_score,
        confidence=confidence,
        blocking_failures=blocking_failures,
        passed=not blocking_failures,
        metadata={} if metadata is None else metadata,
    )


# ── Deterministic assessment export / import ──────────────────────────────────


def export_domain_quality_assessment(assessment: DomainQualityAssessment) -> bytes:
    """Export an assessment as canonical UTF-8 JSON bytes (deterministic)."""
    if not isinstance(assessment, DomainQualityAssessment):
        raise DomainContractValidationError(
            "export_domain_quality_assessment requires a DomainQualityAssessment",
            field="assessment",
        )
    payload = json.dumps(
        assessment.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return payload.encode("utf-8")


def import_domain_quality_assessment(payload: bytes) -> DomainQualityAssessment:
    """Import an assessment from canonical JSON bytes, failing closed on defect."""
    if not isinstance(payload, (bytes, bytearray)):
        raise DomainSerializationError(
            "import_domain_quality_assessment requires bytes", field="payload"
        )
    try:
        data = json.loads(bytes(payload).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DomainSerializationError(
            f"invalid domain quality assessment payload: {exc}", field="payload"
        ) from exc
    if not isinstance(data, Mapping):
        raise DomainSerializationError(
            "domain quality assessment payload must be a JSON object", field="payload"
        )
    return DomainQualityAssessment.from_dict(data)
