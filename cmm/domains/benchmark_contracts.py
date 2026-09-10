"""Phase 10.47 – portable, model-agnostic Domain benchmark asset contracts.

``DomainBenchmarkSuite`` and ``DomainBenchmarkCase`` are immutable, typed,
versioned, deterministic and exportable *data assets*. They describe what a
future evaluation framework must verify for a domain; they never select a model
or provider, never execute anything, and never define weighted quality metrics.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any, TypeAlias

from cmm.domains.errors import (
    DomainContractValidationError,
    DomainSerializationError,
)
from cmm.domains.identifiers import DomainId, _validate_slug

__all__ = [
    "DomainBenchmarkCase",
    "DomainBenchmarkSuite",
    "export_domain_benchmark_suite",
    "import_domain_benchmark_suite",
]

JsonValue: TypeAlias = (
    None | bool | int | float | str | Mapping[str, Any] | Sequence[Any]
)

# ── Identity ──────────────────────────────────────────────────────────────────

_SLUG_PATTERN = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
_SUITE_ID_RE = re.compile(rf"^benchmark-suite:({_SLUG_PATTERN}):({_SLUG_PATTERN})$")
_CASE_ID_RE = re.compile(rf"^benchmark-case:({_SLUG_PATTERN}):({_SLUG_PATTERN})$")


# ── Reserved model/provider authority keys ────────────────────────────────────

# Explicit identifiers that are reserved verbatim after normalization.
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

# Narrow tokenized authority grammar (no substring or fuzzy matching).
# Singular and plural subject nouns are both reserved authority names.
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
    """Deterministic, auditable model/provider authority-key predicate.

    Applies the narrow compound-authority grammar over exact normalized tokens;
    unrelated descriptive keys are never rejected on substring grounds.
    """
    if normalized_key in _EXPLICIT_RESERVED_AUTHORITY_KEYS:
        return True

    parts = normalized_key.split("_")
    head = parts[0]
    tail = parts[-1]

    # (candidate|preferred|prohibited)_(model|provider)[_(id|ids)]
    if (
        head in _AUTHORITY_QUALIFIERS
        and len(parts) in (2, 3)
        and parts[1] in _AUTHORITY_SUBJECTS
        and (len(parts) == 2 or tail in _AUTHORITY_ID_SUFFIXES)
    ):
        return True

    # (model|provider)_(candidate|candidates|preference|preferences|preferred|prohibited)
    if (
        head in _AUTHORITY_SUBJECTS
        and len(parts) == 2
        and tail in _AUTHORITY_PREFERENCE_TOKENS
    ):
        return True

    # (model|provider)_(candidate|preferred|prohibited)_(id|ids)
    if (
        head in _AUTHORITY_SUBJECTS
        and len(parts) == 3
        and parts[1] in _AUTHORITY_QUALIFIERS
        and tail in _AUTHORITY_ID_SUFFIXES
    ):
        return True

    # routing_(model|provider)[_(id|ids)]
    return (
        head == "routing"
        and len(parts) in (2, 3)
        and parts[1] in _AUTHORITY_SUBJECTS
        and (len(parts) == 2 or tail in _AUTHORITY_ID_SUFFIXES)
    )


def _reject_reserved_authority_keys(value: Any, field_name: str) -> None:
    """Reject model/provider-selection keys in metadata at any depth.

    Only mapping keys are inspected; prose values are never scanned.
    """
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


def _require_json_mapping(value: Any, field_name: str) -> MappingProxyType[str, Any]:
    """Validate a generic JSON-safe mapping and deep-freeze it.

    No model/provider authority semantics: schema property names such as
    ``provider`` or ``model`` are ordinary data, not routing authority.
    """
    if not isinstance(value, Mapping):
        raise DomainContractValidationError(
            f"{field_name} must be a mapping", field=field_name
        )
    _require_json_value(value, field_name)
    return _freeze_json(value)


def _require_benchmark_metadata(
    value: Any, field_name: str
) -> MappingProxyType[str, Any]:
    """Validate benchmark metadata, rejecting model/provider authority keys.

    Applies the generic JSON-safety rules plus a recursive, normalized
    reserved-authority-key scan over metadata keys only.
    """
    frozen = _require_json_mapping(value, field_name)
    _reject_reserved_authority_keys(value, field_name)
    return frozen


def _require_optional_json_mapping(
    value: Any, field_name: str
) -> MappingProxyType[str, Any] | None:
    if value is None:
        return None
    return _require_json_mapping(value, field_name)


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


def _require_str_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise DomainContractValidationError(
            f"{field_name} must be a tuple or list of strings", field=field_name
        )
    result: list[str] = []
    for item in value:
        result.append(_require_non_empty_str(item, field_name))
    if len(set(result)) != len(result):
        raise DomainContractValidationError(
            f"{field_name} must not contain duplicate values", field=field_name
        )
    return tuple(result)


def _require_maximum_cost(value: Any, field_name: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise DomainContractValidationError(
            f"{field_name} must be a Decimal or None, "
            f"got {type(value).__name__}: {value!r}",
            field=field_name,
        )
    if not value.is_finite():
        raise DomainContractValidationError(
            f"{field_name} must be finite, got {value!r}", field=field_name
        )
    if value < 0:
        raise DomainContractValidationError(
            f"{field_name} must be non-negative, got {value!r}", field=field_name
        )
    return value


def _canonical_decimal_text(value: Decimal) -> str:
    """Canonical numeric-value decimal text (never caller scale, never float)."""
    if value == 0:
        return "0"

    normalized = value.normalize()
    text = format(normalized, "f")

    if "." in text:
        text = text.rstrip("0").rstrip(".")

    return text


def _maximum_cost_from_dict(value: Any, field_name: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return _require_maximum_cost(value, field_name)
    if isinstance(value, str):
        try:
            parsed = Decimal(value)
        except (InvalidOperation, ValueError) as exc:
            raise DomainSerializationError(
                f"{field_name} must be a canonical decimal string, got {value!r}",
                field=field_name,
            ) from exc
        try:
            return _require_maximum_cost(parsed, field_name)
        except DomainContractValidationError as exc:
            raise DomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc
    raise DomainSerializationError(
        f"{field_name} must be a decimal string or None, got {type(value).__name__}",
        field=field_name,
    )


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


def _require_benchmark_id(
    value: Any, pattern: re.Pattern[str], domain_id: DomainId, field_name: str
) -> str:
    identifier = _require_non_empty_str(value, field_name)
    match = pattern.match(identifier)
    if match is None:
        raise DomainContractValidationError(
            f"{field_name} must match the canonical benchmark identifier form",
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


# ── DomainBenchmarkCase ───────────────────────────────────────────────────────

_CASE_KNOWN = frozenset(
    {
        "id",
        "domain_id",
        "objective",
        "knowledge_package_id",
        "input_resource_refs",
        "expected_elements",
        "required_constraints",
        "prohibited_behaviors",
        "evaluation_criteria",
        "required_format",
        "required_schema",
        "sensitivity",
        "privacy_requirement",
        "maximum_cost_eur",
        "evaluator_ids",
        "human_review_required",
        "human_review_guidance",
        "metadata",
    }
)

_CASE_STRING_TUPLES = (
    "input_resource_refs",
    "expected_elements",
    "required_constraints",
    "prohibited_behaviors",
    "evaluation_criteria",
    "evaluator_ids",
    "human_review_guidance",
)


@dataclass(frozen=True, slots=True)
class DomainBenchmarkCase:
    """Immutable, model-agnostic declaration of one representative domain case."""

    id: str
    domain_id: DomainId
    objective: str
    knowledge_package_id: str | None = None
    input_resource_refs: tuple[str, ...] = ()
    expected_elements: tuple[str, ...] = ()
    required_constraints: tuple[str, ...] = ()
    prohibited_behaviors: tuple[str, ...] = ()
    evaluation_criteria: tuple[str, ...] = ()
    required_format: str | None = None
    required_schema: Mapping[str, JsonValue] | None = None
    sensitivity: str | None = None
    privacy_requirement: str | None = None
    maximum_cost_eur: Decimal | None = None
    evaluator_ids: tuple[str, ...] = ()
    human_review_required: bool = False
    human_review_guidance: tuple[str, ...] = ()
    metadata: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        domain_id = _coerce_domain_id(self.domain_id, "domain_id")
        object.__setattr__(self, "domain_id", domain_id)
        object.__setattr__(
            self,
            "id",
            _require_benchmark_id(self.id, _CASE_ID_RE, domain_id, "id"),
        )
        object.__setattr__(
            self, "objective", _require_non_empty_str(self.objective, "objective")
        )
        object.__setattr__(
            self,
            "knowledge_package_id",
            _require_optional_str(self.knowledge_package_id, "knowledge_package_id"),
        )
        for attr_name in _CASE_STRING_TUPLES:
            object.__setattr__(
                self,
                attr_name,
                _require_str_tuple(getattr(self, attr_name), attr_name),
            )
        object.__setattr__(
            self,
            "required_format",
            _require_optional_str(self.required_format, "required_format"),
        )
        object.__setattr__(
            self,
            "required_schema",
            _require_optional_json_mapping(self.required_schema, "required_schema"),
        )
        object.__setattr__(
            self,
            "sensitivity",
            _require_optional_str(self.sensitivity, "sensitivity"),
        )
        object.__setattr__(
            self,
            "privacy_requirement",
            _require_optional_str(self.privacy_requirement, "privacy_requirement"),
        )
        object.__setattr__(
            self,
            "maximum_cost_eur",
            _require_maximum_cost(self.maximum_cost_eur, "maximum_cost_eur"),
        )
        object.__setattr__(
            self,
            "human_review_required",
            _require_strict_bool(self.human_review_required, "human_review_required"),
        )
        object.__setattr__(
            self, "metadata", _require_benchmark_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize deterministically to a JSON-compatible dictionary."""
        return {
            "id": self.id,
            "domain_id": str(self.domain_id),
            "objective": self.objective,
            "knowledge_package_id": self.knowledge_package_id,
            "input_resource_refs": list(self.input_resource_refs),
            "expected_elements": list(self.expected_elements),
            "required_constraints": list(self.required_constraints),
            "prohibited_behaviors": list(self.prohibited_behaviors),
            "evaluation_criteria": list(self.evaluation_criteria),
            "required_format": self.required_format,
            "required_schema": (
                _thaw_json(self.required_schema)
                if self.required_schema is not None
                else None
            ),
            "sensitivity": self.sensitivity,
            "privacy_requirement": self.privacy_requirement,
            "maximum_cost_eur": (
                _canonical_decimal_text(self.maximum_cost_eur)
                if self.maximum_cost_eur is not None
                else None
            ),
            "evaluator_ids": list(self.evaluator_ids),
            "human_review_required": self.human_review_required,
            "human_review_guidance": list(self.human_review_guidance),
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainBenchmarkCase:
        """Deserialize strictly, rejecting unknown or forbidden fields."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainBenchmarkCase.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _CASE_KNOWN, "DomainBenchmarkCase")
        missing = {"id", "domain_id", "objective"} - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainBenchmarkCase.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                id=data["id"],
                domain_id=data["domain_id"],
                objective=data["objective"],
                knowledge_package_id=data.get("knowledge_package_id"),
                **{
                    attr_name: data.get(attr_name, ())
                    for attr_name in _CASE_STRING_TUPLES
                },
                required_format=data.get("required_format"),
                required_schema=data.get("required_schema"),
                sensitivity=data.get("sensitivity"),
                privacy_requirement=data.get("privacy_requirement"),
                maximum_cost_eur=_maximum_cost_from_dict(
                    data.get("maximum_cost_eur"), "maximum_cost_eur"
                ),
                human_review_required=data.get("human_review_required", False),
                metadata=data.get("metadata", {}),
            )
        except DomainContractValidationError as exc:
            raise _wrap_validation_error(exc) from exc


# ── DomainBenchmarkSuite ──────────────────────────────────────────────────────

_SUITE_KNOWN = frozenset(
    {
        "id",
        "domain_id",
        "schema_version",
        "version",
        "cases",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainBenchmarkSuite:
    """Immutable, versioned, exportable collection of domain benchmark cases."""

    id: str
    domain_id: DomainId
    schema_version: str
    version: str
    cases: tuple[DomainBenchmarkCase, ...]
    metadata: Mapping[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        domain_id = _coerce_domain_id(self.domain_id, "domain_id")
        object.__setattr__(self, "domain_id", domain_id)
        object.__setattr__(
            self,
            "id",
            _require_benchmark_id(self.id, _SUITE_ID_RE, domain_id, "id"),
        )
        object.__setattr__(
            self,
            "schema_version",
            _require_non_empty_str(self.schema_version, "schema_version"),
        )
        object.__setattr__(
            self, "version", _require_non_empty_str(self.version, "version")
        )

        raw_cases = self.cases
        if isinstance(raw_cases, (str, bytes, bytearray)) or not isinstance(
            raw_cases, Sequence
        ):
            raise DomainContractValidationError(
                "cases must be a tuple or list of DomainBenchmarkCase",
                field="cases",
            )
        if not raw_cases:
            raise DomainContractValidationError(
                "cases must contain at least one case", field="cases"
            )
        cases: list[DomainBenchmarkCase] = []
        for index, item in enumerate(raw_cases):
            if not isinstance(item, DomainBenchmarkCase):
                raise DomainContractValidationError(
                    f"cases[{index}] must be a DomainBenchmarkCase, "
                    f"got {type(item).__name__}",
                    field="cases",
                )
            if item.domain_id != domain_id:
                raise DomainContractValidationError(
                    f"cases[{index}] domain_id '{item.domain_id}' must match "
                    f"suite domain_id '{domain_id}'",
                    field="cases",
                )
            cases.append(item)
        case_ids = [case.id for case in cases]
        if len(set(case_ids)) != len(case_ids):
            raise DomainContractValidationError(
                "cases must not contain duplicate case IDs", field="cases"
            )
        object.__setattr__(self, "cases", tuple(cases))
        object.__setattr__(
            self, "metadata", _require_benchmark_metadata(self.metadata, "metadata")
        )

    @property
    def content_digest(self) -> str:
        """SHA-256 digest over the canonical serialized suite content."""
        return hashlib.sha256(export_domain_benchmark_suite(self)).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize deterministically to a JSON-compatible dictionary."""
        return {
            "id": self.id,
            "domain_id": str(self.domain_id),
            "schema_version": self.schema_version,
            "version": self.version,
            "cases": [case.to_dict() for case in self.cases],
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainBenchmarkSuite:
        """Deserialize strictly, rejecting unknown or forbidden fields."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainBenchmarkSuite.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _SUITE_KNOWN, "DomainBenchmarkSuite")
        missing = {"id", "domain_id", "schema_version", "version", "cases"} - set(
            data.keys()
        )
        if missing:
            raise DomainSerializationError(
                f"DomainBenchmarkSuite.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        raw_cases = data["cases"]
        if not isinstance(raw_cases, (list, tuple)):
            raise DomainSerializationError("cases must be a list", field="cases")
        cases: list[DomainBenchmarkCase] = []
        for index, item in enumerate(raw_cases):
            if not isinstance(item, Mapping):
                raise DomainSerializationError(
                    f"cases[{index}] must be a mapping, got {type(item).__name__}",
                    field=f"cases[{index}]",
                )
            cases.append(DomainBenchmarkCase.from_dict(item))
        try:
            return cls(
                id=data["id"],
                domain_id=data["domain_id"],
                schema_version=data["schema_version"],
                version=data["version"],
                cases=tuple(cases),
                metadata=data.get("metadata", {}),
            )
        except DomainContractValidationError as exc:
            raise _wrap_validation_error(exc) from exc


# ── Deterministic export / import ─────────────────────────────────────────────


def export_domain_benchmark_suite(suite: DomainBenchmarkSuite) -> bytes:
    """Export a suite as canonical UTF-8 JSON bytes (deterministic)."""
    if not isinstance(suite, DomainBenchmarkSuite):
        raise DomainContractValidationError(
            "export_domain_benchmark_suite requires a DomainBenchmarkSuite",
            field="suite",
        )
    payload = json.dumps(
        suite.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return payload.encode("utf-8")


def import_domain_benchmark_suite(payload: bytes) -> DomainBenchmarkSuite:
    """Import a suite from canonical JSON bytes, failing closed on any defect."""
    if not isinstance(payload, (bytes, bytearray)):
        raise DomainSerializationError(
            "import_domain_benchmark_suite requires bytes", field="payload"
        )
    try:
        data = json.loads(bytes(payload).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DomainSerializationError(
            f"invalid benchmark suite payload: {exc}", field="payload"
        ) from exc
    if not isinstance(data, Mapping):
        raise DomainSerializationError(
            "benchmark suite payload must be a JSON object", field="payload"
        )
    return DomainBenchmarkSuite.from_dict(data)
