"""Phase 10.49 – Domain-owned knowledge package schemas.

Declarative, immutable, versioned Domain specialization of the canonical
Phase 8 :class:`cmm.cognitive.knowledge_packages.KnowledgePackage`.

A schema is configuration, not authority. It may narrow or reject; it may never
grant execution, provider, network, file, resource, cross-domain, approval,
privacy or permission authority.

This module never builds, stores, mutates or repairs a ``KnowledgePackage`` and
never resolves or executes an opaque validator reference. The canonical builder
remains :class:`cmm.cognitive.knowledge_packages.KnowledgePackageBuilder`.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from cmm.cognitive.enums import KnowledgeKind, SensitivityLevel
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainKnowledgePackageContractError,
    DomainKnowledgePackageSerializationError,
    DomainSerializationError,
)
from cmm.domains.identifiers import DomainId

__all__ = [
    "DomainKnowledgePackageFieldPolicy",
    "DomainKnowledgePackageSchema",
    "EffectiveDomainKnowledgePackageSchema",
]

# ── Finite canonical vocabulary ───────────────────────────────────────────────
#
# Declared literally (never derived at runtime) so the Domain surface is auditable
# against the canonical Phase 8 KnowledgePackage dataclass.

CANONICAL_KNOWLEDGE_PACKAGE_FIELDS = frozenset(
    {
        "id",
        "objective",
        "profile",
        "domain",
        "session_id",
        "current_state",
        "timeline",
        "active_goals",
        "facts",
        "observations",
        "inferences",
        "hypotheses",
        "other_knowledge",
        "contradictions",
        "unknowns",
        "constraints",
        "preferences",
        "relevant_memory",
        "prior_reasoning",
        "resources",
        "missing_information",
        "reasoning_profile",
        "domain_instructions",
        "privacy",
        "temporal_scope",
        "provenance",
        "created_at",
        "valid_until",
        "metadata",
        "schema_version",
    }
)

# Canonical Phase 8 epistemic categories that carry ``KnowledgeItem`` values.
KNOWLEDGE_ITEM_CATEGORY_FIELDS = frozenset(
    {
        "facts",
        "observations",
        "inferences",
        "hypotheses",
        "other_knowledge",
    }
)

_BASE_SCHEMA = "KnowledgePackage"


# ── Reserved model/provider authority keys ────────────────────────────────────
#
# Mirrors the hardened Phase 10.47/10.48 metadata boundary locally so the audited
# modules stay frozen. Only mapping keys are inspected, never values.

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
                raise DomainKnowledgePackageContractError(
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
            raise DomainKnowledgePackageContractError(
                f"{field_name} must not contain non-finite floats",
                field=field_name,
                details={"value": repr(value)},
            )
        return
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str) or isinstance(key, bool):
                raise DomainKnowledgePackageContractError(
                    f"{field_name} keys must be strings", field=field_name
                )
            _require_json_value(nested, field_name)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in value:
            _require_json_value(nested, field_name)
        return
    raise DomainKnowledgePackageContractError(
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


def _require_metadata(value: Any, field_name: str) -> MappingProxyType[str, Any]:
    """Validate descriptive audit metadata and deep-freeze it."""
    if not isinstance(value, Mapping):
        raise DomainKnowledgePackageContractError(
            f"{field_name} must be a mapping", field=field_name
        )
    _require_json_value(value, field_name)
    _reject_reserved_authority_keys(value, field_name)
    return _freeze_json(value)


# ── Primitive validation ──────────────────────────────────────────────────────


def _require_non_empty_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DomainKnowledgePackageContractError(
            f"{field_name} must be a non-empty string", field=field_name
        )
    return value.strip()


def _require_strict_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise DomainKnowledgePackageContractError(
            f"{field_name} must be a boolean (True or False), "
            f"got {type(value).__name__}: {value!r}",
            field=field_name,
        )
    return value


def _require_sequence(value: Any, field_name: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise DomainKnowledgePackageContractError(
            f"{field_name} must be a tuple or list", field=field_name
        )
    return value


def _require_non_empty_str_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    items = _require_sequence(value, field_name)
    return tuple(_require_non_empty_str(item, field_name) for item in items)


def _require_minimum_items(value: Any, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise DomainKnowledgePackageContractError(
            f"{field_name} must be None or a non-negative integer, "
            f"got {type(value).__name__}: {value!r}",
            field=field_name,
        )
    if value < 0:
        raise DomainKnowledgePackageContractError(
            f"{field_name} must be greater than or equal to 0, got {value!r}",
            field=field_name,
        )
    return value


def _require_field_name(value: Any, field_name: str = "field_name") -> str:
    name = _require_non_empty_str(value, field_name)
    if name not in CANONICAL_KNOWLEDGE_PACKAGE_FIELDS:
        raise DomainKnowledgePackageContractError(
            f"{field_name} must name a canonical KnowledgePackage field: {name!r}",
            field=field_name,
            details={"value": name},
        )
    return name


def _require_knowledge_kinds(
    value: Any, owner_field: str, field_name: str = "allowed_knowledge_kinds"
) -> tuple[KnowledgeKind, ...]:
    items = _require_sequence(value, field_name)
    kinds: list[KnowledgeKind] = []
    for item in items:
        if not isinstance(item, KnowledgeKind):
            raise DomainKnowledgePackageContractError(
                f"{field_name} must contain KnowledgeKind values, "
                f"got {type(item).__name__}: {item!r}",
                field=field_name,
            )
        kinds.append(item)
    if len(kinds) != len(set(kinds)):
        raise DomainKnowledgePackageContractError(
            f"{field_name} must not contain duplicate kinds", field=field_name
        )
    if kinds and owner_field not in KNOWLEDGE_ITEM_CATEGORY_FIELDS:
        raise DomainKnowledgePackageContractError(
            f"{field_name} is only valid for knowledge-item category fields",
            field=field_name,
            details={"field_name": owner_field},
        )
    return tuple(kinds)


def _require_domain_id(value: Any, field_name: str) -> DomainId:
    if not isinstance(value, DomainId):
        raise DomainKnowledgePackageContractError(
            f"{field_name} must be a DomainId, got {type(value).__name__}",
            field=field_name,
        )
    return value


def _require_sensitivity(value: Any, field_name: str) -> SensitivityLevel:
    if not isinstance(value, SensitivityLevel):
        raise DomainKnowledgePackageContractError(
            f"{field_name} must be a canonical SensitivityLevel, "
            f"got {type(value).__name__}: {value!r}",
            field=field_name,
        )
    return value


def _require_sections(value: Any, field_name: str) -> tuple[str, ...]:
    items = _require_sequence(value, field_name)
    sections: list[str] = []
    for item in items:
        section = _require_non_empty_str(item, field_name)
        if section not in CANONICAL_KNOWLEDGE_PACKAGE_FIELDS:
            raise DomainKnowledgePackageContractError(
                f"{field_name} contains unknown section {section!r}",
                field=field_name,
                details={"section": section},
            )
        sections.append(section)
    if len(sections) != len(set(sections)):
        raise DomainKnowledgePackageContractError(
            f"{field_name} must not contain duplicate sections", field=field_name
        )
    return tuple(sections)


def _require_disjoint_sections(
    required: tuple[str, ...],
    optional: tuple[str, ...],
    prohibited: tuple[str, ...],
) -> None:
    pairs = (
        ("required_sections", "optional_sections", required, optional),
        ("required_sections", "prohibited_sections", required, prohibited),
        ("optional_sections", "prohibited_sections", optional, prohibited),
    )
    for left_name, right_name, left, right in pairs:
        overlap = sorted(set(left) & set(right))
        if overlap:
            raise DomainKnowledgePackageContractError(
                f"{left_name} and {right_name} must be disjoint: {overlap}",
                field=left_name,
                details={"overlap": overlap, "other": right_name},
            )


def _require_field_policies(
    value: Any, prohibited: tuple[str, ...]
) -> tuple[DomainKnowledgePackageFieldPolicy, ...]:
    items = _require_sequence(value, "field_policies")
    policies: list[DomainKnowledgePackageFieldPolicy] = []
    seen: set[str] = set()
    prohibited_set = set(prohibited)
    for item in items:
        if not isinstance(item, DomainKnowledgePackageFieldPolicy):
            raise DomainKnowledgePackageContractError(
                "field_policies must contain DomainKnowledgePackageFieldPolicy values",
                field="field_policies",
            )
        if item.field_name in seen:
            raise DomainKnowledgePackageContractError(
                f"duplicate field policy for {item.field_name!r}",
                field="field_policies",
                details={"field_name": item.field_name},
            )
        seen.add(item.field_name)
        requires_content = item.required_non_empty or item.minimum_items is not None
        if item.field_name in prohibited_set and requires_content:
            raise DomainKnowledgePackageContractError(
                f"field policy for prohibited section {item.field_name!r} "
                "must not require content",
                field="field_policies",
                details={"field_name": item.field_name},
            )
        policies.append(item)
    return tuple(sorted(policies, key=lambda policy: policy.field_name))


def _require_validator_refs(
    value: Any, field_name: str = "validator_refs"
) -> tuple[str, ...]:
    refs = _require_non_empty_str_tuple(value, field_name)
    if len(refs) != len(set(refs)):
        raise DomainKnowledgePackageContractError(
            f"{field_name} must not contain duplicates", field=field_name
        )
    return refs


# ── Serialization helpers ─────────────────────────────────────────────────────


def _reject_unknown_fields(
    data: Mapping[str, Any], known: frozenset[str], cls_name: str
) -> None:
    unknown = set(data.keys()) - known
    if unknown:
        raise DomainKnowledgePackageSerializationError(
            f"{cls_name}.from_dict got unknown fields: {sorted(unknown)}",
            field="data",
            details={"unknown_fields": sorted(unknown)},
        )


def _wrap_contract_error(
    exc: DomainKnowledgePackageContractError,
) -> DomainKnowledgePackageSerializationError:
    if isinstance(exc, DomainKnowledgePackageSerializationError):
        return exc
    return DomainKnowledgePackageSerializationError(
        exc.message, field=exc.field, details=dict(exc.details)
    )


def _require_payload_mapping(value: Any, cls_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DomainKnowledgePackageSerializationError(
            f"{cls_name}.from_dict requires a mapping", field="data"
        )
    return value


def _require_payload_field(data: Mapping[str, Any], name: str, cls_name: str) -> Any:
    if name not in data:
        raise DomainKnowledgePackageSerializationError(
            f"{cls_name}.from_dict missing required field {name!r}", field=name
        )
    return data[name]


def _coerce_domain_id(value: Any, field_name: str) -> DomainId:
    if isinstance(value, DomainId):
        return value
    if isinstance(value, Mapping):
        try:
            return DomainId.from_dict(dict(value))
        except (DomainSerializationError, DomainContractValidationError) as exc:
            raise DomainKnowledgePackageSerializationError(
                f"{field_name} must be a canonical 'domain:<slug>' value",
                field=field_name,
            ) from exc
    if isinstance(value, str):
        try:
            return DomainId.from_str(value)
        except (DomainSerializationError, DomainContractValidationError) as exc:
            raise DomainKnowledgePackageSerializationError(
                f"{field_name} must be a canonical 'domain:<slug>' value",
                field=field_name,
            ) from exc
    raise DomainKnowledgePackageSerializationError(
        f"{field_name} must be a DomainId or canonical 'domain:<slug>' value",
        field=field_name,
    )


def _coerce_sensitivity(value: Any, field_name: str) -> SensitivityLevel:
    if isinstance(value, SensitivityLevel):
        return value
    if isinstance(value, str):
        try:
            return SensitivityLevel(value)
        except ValueError as exc:
            raise DomainKnowledgePackageContractError(
                f"{field_name} must be a canonical SensitivityLevel: {value!r}",
                field=field_name,
                details={"value": value},
            ) from exc
    raise DomainKnowledgePackageContractError(
        f"{field_name} must be a SensitivityLevel or its canonical string",
        field=field_name,
    )


def _coerce_kinds_payload(value: Any) -> tuple[KnowledgeKind, ...]:
    items = _require_sequence(value, "allowed_knowledge_kinds")
    kinds: list[KnowledgeKind] = []
    for item in items:
        if isinstance(item, KnowledgeKind):
            kinds.append(item)
            continue
        if isinstance(item, str):
            try:
                kinds.append(KnowledgeKind(item))
            except ValueError as exc:
                raise DomainKnowledgePackageContractError(
                    f"allowed_knowledge_kinds contains unknown kind {item!r}",
                    field="allowed_knowledge_kinds",
                    details={"value": item},
                ) from exc
            continue
        raise DomainKnowledgePackageContractError(
            f"allowed_knowledge_kinds must contain kind names, "
            f"got {type(item).__name__}: {item!r}",
            field="allowed_knowledge_kinds",
        )
    return tuple(kinds)


def _coerce_field_policies_payload(
    value: Any,
) -> tuple[DomainKnowledgePackageFieldPolicy, ...]:
    items = _require_sequence(value, "field_policies")
    policies: list[DomainKnowledgePackageFieldPolicy] = []
    for item in items:
        if isinstance(item, DomainKnowledgePackageFieldPolicy):
            policies.append(item)
        elif isinstance(item, Mapping):
            policies.append(DomainKnowledgePackageFieldPolicy.from_dict(item))
        else:
            raise DomainKnowledgePackageContractError(
                "field_policies must contain policies or mappings, "
                f"got {type(item).__name__}",
                field="field_policies",
            )
    return tuple(policies)


def _coerce_domain_ids_payload(value: Any) -> tuple[DomainId, ...]:
    items = _require_sequence(value, "domain_ids")
    return tuple(_coerce_domain_id(item, "domain_ids") for item in items)


# ── DomainKnowledgePackageFieldPolicy ─────────────────────────────────────────

_POLICY_KNOWN = frozenset(
    {
        "field_name",
        "required_non_empty",
        "minimum_items",
        "allowed_knowledge_kinds",
        "require_provenance",
        "require_temporal_scope",
        "preserve_uncertainty",
        "preserve_contradictions",
    }
)


@dataclass(frozen=True, slots=True)
class DomainKnowledgePackageFieldPolicy:
    """Immutable constraint over exactly one canonical package field.

    A policy can only narrow or require evidence. It never grants authority.
    """

    field_name: str
    required_non_empty: bool = False
    minimum_items: int | None = None
    allowed_knowledge_kinds: tuple[KnowledgeKind, ...] = ()
    require_provenance: bool = False
    require_temporal_scope: bool = False
    preserve_uncertainty: bool = False
    preserve_contradictions: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "field_name", _require_field_name(self.field_name, "field_name")
        )
        object.__setattr__(
            self,
            "required_non_empty",
            _require_strict_bool(self.required_non_empty, "required_non_empty"),
        )
        object.__setattr__(
            self,
            "minimum_items",
            _require_minimum_items(self.minimum_items, "minimum_items"),
        )
        object.__setattr__(
            self,
            "allowed_knowledge_kinds",
            _require_knowledge_kinds(
                self.allowed_knowledge_kinds, self.field_name, "allowed_knowledge_kinds"
            ),
        )
        object.__setattr__(
            self,
            "require_provenance",
            _require_strict_bool(self.require_provenance, "require_provenance"),
        )
        object.__setattr__(
            self,
            "require_temporal_scope",
            _require_strict_bool(self.require_temporal_scope, "require_temporal_scope"),
        )
        object.__setattr__(
            self,
            "preserve_uncertainty",
            _require_strict_bool(self.preserve_uncertainty, "preserve_uncertainty"),
        )
        object.__setattr__(
            self,
            "preserve_contradictions",
            _require_strict_bool(
                self.preserve_contradictions, "preserve_contradictions"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize deterministically."""
        return {
            "field_name": self.field_name,
            "required_non_empty": self.required_non_empty,
            "minimum_items": self.minimum_items,
            "allowed_knowledge_kinds": [
                kind.value for kind in self.allowed_knowledge_kinds
            ],
            "require_provenance": self.require_provenance,
            "require_temporal_scope": self.require_temporal_scope,
            "preserve_uncertainty": self.preserve_uncertainty,
            "preserve_contradictions": self.preserve_contradictions,
        }

    @classmethod
    def from_dict(cls, data: Any) -> DomainKnowledgePackageFieldPolicy:
        """Deserialize strictly, failing closed on malformed payloads."""
        mapping = _require_payload_mapping(data, "DomainKnowledgePackageFieldPolicy")
        _reject_unknown_fields(
            mapping, _POLICY_KNOWN, "DomainKnowledgePackageFieldPolicy"
        )
        field_name = _require_payload_field(
            mapping, "field_name", "DomainKnowledgePackageFieldPolicy"
        )
        try:
            return cls(
                field_name=field_name,
                required_non_empty=mapping.get("required_non_empty", False),
                minimum_items=mapping.get("minimum_items", None),
                allowed_knowledge_kinds=_coerce_kinds_payload(
                    mapping.get("allowed_knowledge_kinds", ())
                ),
                require_provenance=mapping.get("require_provenance", False),
                require_temporal_scope=mapping.get("require_temporal_scope", False),
                preserve_uncertainty=mapping.get("preserve_uncertainty", False),
                preserve_contradictions=mapping.get("preserve_contradictions", False),
            )
        except DomainKnowledgePackageContractError as exc:
            raise _wrap_contract_error(exc) from exc


# ── DomainKnowledgePackageSchema ──────────────────────────────────────────────

_SCHEMA_KNOWN = frozenset(
    {
        "id",
        "domain_id",
        "version",
        "base_schema",
        "required_sections",
        "optional_sections",
        "prohibited_sections",
        "field_policies",
        "minimum_sensitivity",
        "validator_refs",
        "metadata",
    }
)

_SCHEMA_REQUIRED = ("id", "domain_id", "version")


@dataclass(frozen=True, slots=True)
class DomainKnowledgePackageSchema:
    """Immutable, versioned Domain declaration narrowing the canonical package."""

    id: str
    domain_id: DomainId
    version: str
    base_schema: str = _BASE_SCHEMA
    required_sections: tuple[str, ...] = ()
    optional_sections: tuple[str, ...] = ()
    prohibited_sections: tuple[str, ...] = ()
    field_policies: tuple[DomainKnowledgePackageFieldPolicy, ...] = ()
    minimum_sensitivity: SensitivityLevel = SensitivityLevel.PUBLIC
    validator_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_non_empty_str(self.id, "id"))
        object.__setattr__(
            self, "version", _require_non_empty_str(self.version, "version")
        )
        _require_domain_id(self.domain_id, "domain_id")

        if self.base_schema != _BASE_SCHEMA:
            raise DomainKnowledgePackageContractError(
                f"base_schema must be exactly {_BASE_SCHEMA!r}, got {self.base_schema!r}",
                field="base_schema",
                details={"base_schema": self.base_schema},
            )

        required = _require_sections(self.required_sections, "required_sections")
        optional = _require_sections(self.optional_sections, "optional_sections")
        prohibited = _require_sections(self.prohibited_sections, "prohibited_sections")
        _require_disjoint_sections(required, optional, prohibited)
        object.__setattr__(self, "required_sections", required)
        object.__setattr__(self, "optional_sections", optional)
        object.__setattr__(self, "prohibited_sections", prohibited)

        object.__setattr__(
            self,
            "field_policies",
            _require_field_policies(self.field_policies, prohibited),
        )
        object.__setattr__(
            self,
            "minimum_sensitivity",
            _require_sensitivity(self.minimum_sensitivity, "minimum_sensitivity"),
        )
        object.__setattr__(
            self, "validator_refs", _require_validator_refs(self.validator_refs)
        )
        object.__setattr__(
            self, "metadata", _require_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize deterministically."""
        return {
            "id": self.id,
            "domain_id": str(self.domain_id),
            "version": self.version,
            "base_schema": self.base_schema,
            "required_sections": list(self.required_sections),
            "optional_sections": list(self.optional_sections),
            "prohibited_sections": list(self.prohibited_sections),
            "field_policies": [policy.to_dict() for policy in self.field_policies],
            "minimum_sensitivity": self.minimum_sensitivity.value,
            "validator_refs": list(self.validator_refs),
            "metadata": _thaw_json(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Any) -> DomainKnowledgePackageSchema:
        """Deserialize strictly, failing closed on malformed payloads."""
        mapping = _require_payload_mapping(data, "DomainKnowledgePackageSchema")
        _reject_unknown_fields(mapping, _SCHEMA_KNOWN, "DomainKnowledgePackageSchema")
        for name in _SCHEMA_REQUIRED:
            _require_payload_field(mapping, name, "DomainKnowledgePackageSchema")
        try:
            return cls(
                id=mapping["id"],
                domain_id=_coerce_domain_id(mapping["domain_id"], "domain_id"),
                version=mapping["version"],
                base_schema=mapping.get("base_schema", _BASE_SCHEMA),
                required_sections=mapping.get("required_sections", ()),
                optional_sections=mapping.get("optional_sections", ()),
                prohibited_sections=mapping.get("prohibited_sections", ()),
                field_policies=_coerce_field_policies_payload(
                    mapping.get("field_policies", ())
                ),
                minimum_sensitivity=_coerce_sensitivity(
                    mapping.get("minimum_sensitivity", SensitivityLevel.PUBLIC),
                    "minimum_sensitivity",
                ),
                validator_refs=mapping.get("validator_refs", ()),
                metadata=mapping.get("metadata", {}),
            )
        except DomainKnowledgePackageContractError as exc:
            raise _wrap_contract_error(exc) from exc


# ── EffectiveDomainKnowledgePackageSchema ─────────────────────────────────────

_EFFECTIVE_KNOWN = frozenset(
    {
        "source_schema_ids",
        "domain_ids",
        "required_sections",
        "optional_sections",
        "prohibited_sections",
        "field_policies",
        "minimum_sensitivity",
        "validator_refs",
    }
)


@dataclass(frozen=True, slots=True)
class EffectiveDomainKnowledgePackageSchema:
    """Immutable composition evidence over one or more Domain schemas.

    This is effective policy evidence, never a package model: it carries no
    knowledge payload and no mutable user state.
    """

    source_schema_ids: tuple[str, ...]
    domain_ids: tuple[DomainId, ...]
    required_sections: tuple[str, ...]
    optional_sections: tuple[str, ...]
    prohibited_sections: tuple[str, ...]
    field_policies: tuple[DomainKnowledgePackageFieldPolicy, ...]
    minimum_sensitivity: SensitivityLevel
    validator_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        sources = _require_non_empty_str_tuple(
            self.source_schema_ids, "source_schema_ids"
        )
        if not sources:
            raise DomainKnowledgePackageContractError(
                "EffectiveDomainKnowledgePackageSchema requires at least one "
                "source schema",
                field="source_schema_ids",
            )
        object.__setattr__(self, "source_schema_ids", tuple(sorted(sources)))

        domains = _require_sequence(self.domain_ids, "domain_ids")
        for domain in domains:
            _require_domain_id(domain, "domain_ids")
        object.__setattr__(
            self, "domain_ids", tuple(sorted(domains, key=lambda item: str(item)))
        )

        required = _require_sections(self.required_sections, "required_sections")
        optional = _require_sections(self.optional_sections, "optional_sections")
        prohibited = _require_sections(self.prohibited_sections, "prohibited_sections")
        _require_disjoint_sections(required, optional, prohibited)
        object.__setattr__(self, "required_sections", required)
        object.__setattr__(self, "optional_sections", optional)
        object.__setattr__(self, "prohibited_sections", prohibited)

        object.__setattr__(
            self,
            "field_policies",
            _require_field_policies(self.field_policies, prohibited),
        )
        object.__setattr__(
            self,
            "minimum_sensitivity",
            _require_sensitivity(self.minimum_sensitivity, "minimum_sensitivity"),
        )
        object.__setattr__(
            self, "validator_refs", _require_validator_refs(self.validator_refs)
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize deterministically."""
        return {
            "source_schema_ids": list(self.source_schema_ids),
            "domain_ids": [str(domain) for domain in self.domain_ids],
            "required_sections": list(self.required_sections),
            "optional_sections": list(self.optional_sections),
            "prohibited_sections": list(self.prohibited_sections),
            "field_policies": [policy.to_dict() for policy in self.field_policies],
            "minimum_sensitivity": self.minimum_sensitivity.value,
            "validator_refs": list(self.validator_refs),
        }

    @classmethod
    def from_dict(cls, data: Any) -> EffectiveDomainKnowledgePackageSchema:
        """Deserialize strictly, failing closed on malformed payloads."""
        mapping = _require_payload_mapping(
            data, "EffectiveDomainKnowledgePackageSchema"
        )
        _reject_unknown_fields(
            mapping, _EFFECTIVE_KNOWN, "EffectiveDomainKnowledgePackageSchema"
        )
        for name in _EFFECTIVE_KNOWN:
            _require_payload_field(
                mapping, name, "EffectiveDomainKnowledgePackageSchema"
            )
        try:
            return cls(
                source_schema_ids=mapping["source_schema_ids"],
                domain_ids=_coerce_domain_ids_payload(mapping["domain_ids"]),
                required_sections=mapping["required_sections"],
                optional_sections=mapping["optional_sections"],
                prohibited_sections=mapping["prohibited_sections"],
                field_policies=_coerce_field_policies_payload(
                    mapping["field_policies"]
                ),
                minimum_sensitivity=_coerce_sensitivity(
                    mapping["minimum_sensitivity"], "minimum_sensitivity"
                ),
                validator_refs=mapping["validator_refs"],
            )
        except DomainKnowledgePackageContractError as exc:
            raise _wrap_contract_error(exc) from exc
