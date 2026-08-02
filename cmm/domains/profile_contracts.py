"""Phase 10.11 – Domain Profile Contracts.

Immutable, JSON-serializable, type-safe contracts for the Domain Profiles
layer. All dataclasses are ``frozen=True``, use ``slots=True``, and never
expose mutable internal state.

Domain Profiles are declarative configuration for the Cognitive Layer
(Phase 8). They never execute reasoning, never execute rules, and never
contain executable values. No adapter execution, no filesystem, no network,
no persistence, no runtime identity resolution.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from cmm.cognitive.enums import SensitivityLevel as Sensitivity
from cmm.domains.contracts import (
    _deep_freeze,
    _ensure_tz_aware,
    _normalize_empty_to_none,
    _reject_unknown_fields,
    _validate_non_empty_str,
    _validate_strict_bool,
)
from cmm.domains.enums import (
    DomainProfileConflictSeverity,
    DomainProfileDecisionCode,
    DomainProfileResolutionStatus,
    DomainProfileSource,
    DomainReasoningDepth,
)
from cmm.domains.errors import DomainContractValidationError as _UpstreamContractError
from cmm.domains.errors import (
    DomainProfileContractError,
    DomainProfileSerializationError,
)
from cmm.domains.errors import (
    DomainResolutionSerializationError as _UpstreamResolutionSerializationError,
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
    _validate_json_safe_metadata as _upstream_validate_json_safe_metadata,
)

# ── Error translation ───────────────────────────────────────────────────────
#
# The shared validation helpers above (reused from contracts.py and
# resolver_contracts.py) raise the *Domain*-level error hierarchy. Every
# Domain Profile contract must raise Domain-Profile-level errors instead, so
# each reused helper is rebound to translate on the way out.


def _as_contract_error(fn):
    def _wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (_UpstreamContractError, _UpstreamSerializationError) as exc:
            raise DomainProfileContractError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc

    return _wrapped


def _as_serialization_error(fn):
    def _wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (
            _UpstreamContractError,
            _UpstreamResolutionSerializationError,
            _UpstreamSerializationError,
        ) as exc:
            raise DomainProfileSerializationError(
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
_validate_json_safe_metadata = _as_contract_error(_upstream_validate_json_safe_metadata)

_reject_unknown_fields = _as_serialization_error(_reject_unknown_fields)
_parse_datetime_opt = _as_serialization_error(_upstream_parse_datetime_opt)


# ── Local numeric helpers ────────────────────────────────────────────────────


def _validate_positive_int(val: Any, field_name: str) -> int:
    """Validate a strictly positive integer, rejecting bool."""
    if isinstance(val, bool):
        raise DomainProfileContractError(
            f"{field_name} must be an integer, not a boolean", field=field_name
        )
    if not isinstance(val, int):
        raise DomainProfileContractError(
            f"{field_name} must be an integer, got {type(val).__name__}: {val!r}",
            field=field_name,
        )
    if val <= 0:
        raise DomainProfileContractError(
            f"{field_name} must be positive, got {val!r}", field=field_name
        )
    return val


def _validate_positive_int_opt(val: Any, field_name: str) -> int | None:
    """Validate an optional strictly positive integer."""
    if val is None:
        return None
    return _validate_positive_int(val, field_name)


def _validate_non_negative_int(val: Any, field_name: str) -> int:
    """Validate a non-negative integer, rejecting bool."""
    if isinstance(val, bool):
        raise DomainProfileContractError(
            f"{field_name} must be an integer, not a boolean", field=field_name
        )
    if not isinstance(val, int):
        raise DomainProfileContractError(
            f"{field_name} must be an integer, got {type(val).__name__}: {val!r}",
            field=field_name,
        )
    if val < 0:
        raise DomainProfileContractError(
            f"{field_name} must be non-negative, got {val!r}", field=field_name
        )
    return val


def _validate_non_negative_int_opt(val: Any, field_name: str) -> int | None:
    """Validate an optional non-negative integer."""
    if val is None:
        return None
    return _validate_non_negative_int(val, field_name)


def _validate_confidence(val: Any, field_name: str) -> float:
    """Validate a finite confidence value in [0.0, 1.0]."""
    f = _validate_finite_float(val, field_name)
    if not (0.0 <= f <= 1.0):
        raise DomainProfileContractError(
            f"{field_name} must be between 0.0 and 1.0, got {f!r}", field=field_name
        )
    return f


def _validate_confidence_opt(val: Any, field_name: str) -> float | None:
    """Validate an optional finite confidence value in [0.0, 1.0]."""
    if val is None:
        return None
    return _validate_confidence(val, field_name)


def _validate_strict_bool_opt(val: Any, field_name: str) -> bool | None:
    """Validate an optional strict boolean."""
    if val is None:
        return None
    return _validate_strict_bool(val, field_name)


def _freeze_optional_unique_str_tuple(
    seq: Any, field_name: str
) -> tuple[str, ...] | None:
    """Freeze a sequence of unique non-empty strings, preserving ``None`` (unconstrained).

    An explicit empty tuple means "constrain to nothing"; ``None`` means the
    source does not constrain this field at all.
    """
    if seq is None:
        return None
    return _freeze_unique_str_tuple(seq, field_name)


def _validate_ordered_choice(val: Any, field_name: str, order: tuple[str, ...]) -> str:
    """Validate that ``val`` is a member of a closed, explicitly ordered string set."""
    if not isinstance(val, str) or val not in order:
        raise DomainProfileContractError(
            f"{field_name} must be one of {list(order)}, got {val!r}",
            field=field_name,
        )
    return val


def _validate_ordered_choice_opt(
    val: Any, field_name: str, order: tuple[str, ...]
) -> str | None:
    """Optional variant of :func:`_validate_ordered_choice`."""
    if val is None:
        return None
    return _validate_ordered_choice(val, field_name, order)


def _coerce_reasoning_depth(val: Any, field_name: str) -> DomainReasoningDepth:
    """Coerce a string or DomainReasoningDepth to DomainReasoningDepth."""
    if isinstance(val, DomainReasoningDepth):
        return val
    if isinstance(val, str):
        try:
            return DomainReasoningDepth(val)
        except ValueError as exc:
            raise DomainProfileContractError(
                f"Invalid DomainReasoningDepth: {val!r}", field=field_name
            ) from exc
    raise DomainProfileContractError(
        f"{field_name} must be a DomainReasoningDepth or string, got {type(val).__name__}",
        field=field_name,
    )


def _coerce_reasoning_depth_opt(
    val: Any, field_name: str
) -> DomainReasoningDepth | None:
    """Optional variant of :func:`_coerce_reasoning_depth`."""
    if val is None:
        return None
    return _coerce_reasoning_depth(val, field_name)


def _coerce_sensitivity_opt(val: Any, field_name: str) -> Sensitivity | None:
    """Coerce an optional string or SensitivityLevel to SensitivityLevel."""
    if val is None:
        return None
    if isinstance(val, Sensitivity):
        return val
    if isinstance(val, str):
        try:
            return Sensitivity(val)
        except ValueError as exc:
            raise DomainProfileContractError(
                f"Invalid sensitivity_limit: {val!r}", field=field_name
            ) from exc
    raise DomainProfileContractError(
        f"{field_name} must be a SensitivityLevel or string, got {type(val).__name__}",
        field=field_name,
    )


def _coerce_profile_source(val: Any, field_name: str) -> DomainProfileSource:
    """Coerce a string or DomainProfileSource to DomainProfileSource."""
    if isinstance(val, DomainProfileSource):
        return val
    if isinstance(val, str):
        try:
            return DomainProfileSource(val)
        except ValueError as exc:
            raise DomainProfileContractError(
                f"Invalid DomainProfileSource: {val!r}", field=field_name
            ) from exc
    raise DomainProfileContractError(
        f"{field_name} must be a DomainProfileSource or string, got {type(val).__name__}",
        field=field_name,
    )


def _coerce_decision_code(val: Any, field_name: str) -> DomainProfileDecisionCode:
    """Coerce a string or DomainProfileDecisionCode to DomainProfileDecisionCode."""
    if isinstance(val, DomainProfileDecisionCode):
        return val
    if isinstance(val, str):
        try:
            return DomainProfileDecisionCode(val)
        except ValueError as exc:
            raise DomainProfileContractError(
                f"Invalid DomainProfileDecisionCode: {val!r}", field=field_name
            ) from exc
    raise DomainProfileContractError(
        f"{field_name} must be a DomainProfileDecisionCode or string, got {type(val).__name__}",
        field=field_name,
    )


def _coerce_conflict_severity(
    val: Any, field_name: str
) -> DomainProfileConflictSeverity:
    """Coerce a string or DomainProfileConflictSeverity to DomainProfileConflictSeverity."""
    if isinstance(val, DomainProfileConflictSeverity):
        return val
    if isinstance(val, str):
        try:
            return DomainProfileConflictSeverity(val)
        except ValueError as exc:
            raise DomainProfileContractError(
                f"Invalid DomainProfileConflictSeverity: {val!r}", field=field_name
            ) from exc
    raise DomainProfileContractError(
        f"{field_name} must be a DomainProfileConflictSeverity or string, "
        f"got {type(val).__name__}",
        field=field_name,
    )


def _coerce_resolution_status(
    val: Any, field_name: str
) -> DomainProfileResolutionStatus:
    """Coerce a string or DomainProfileResolutionStatus to DomainProfileResolutionStatus."""
    if isinstance(val, DomainProfileResolutionStatus):
        return val
    if isinstance(val, str):
        try:
            return DomainProfileResolutionStatus(val)
        except ValueError as exc:
            raise DomainProfileContractError(
                f"Invalid DomainProfileResolutionStatus: {val!r}", field=field_name
            ) from exc
    raise DomainProfileContractError(
        f"{field_name} must be a DomainProfileResolutionStatus or string, "
        f"got {type(val).__name__}",
        field=field_name,
    )


def _freeze_source_tuple(seq: Any, field_name: str) -> tuple[DomainProfileSource, ...]:
    """Coerce a sequence into a tuple of DomainProfileSource, order preserved."""
    if seq is None:
        return ()
    if isinstance(seq, (str, bytes)):
        raise DomainProfileContractError(
            f"{field_name} must be a sequence of DomainProfileSource, not a string",
            field=field_name,
        )
    if not isinstance(seq, (tuple, list)):
        raise DomainProfileContractError(
            f"{field_name} must be a tuple or list", field=field_name
        )
    return tuple(
        _coerce_profile_source(item, f"{field_name}[{i}]") for i, item in enumerate(seq)
    )


# ── Closed, explicitly restrictive orderings ────────────────────────────────
#
# Ordered capability scales. Each merge helper documents whether the lower or
# higher index is the restrictive end of its scale.

DETAIL_LEVEL_ORDER: tuple[str, ...] = ("exhaustive", "detailed", "standard", "minimal")
RETENTION_SCOPE_ORDER: tuple[str, ...] = (
    "none",
    "turn",
    "session",
    "short_term",
    "long_term",
)


# ═══════════════════════════════════════════════════════════════════════════════
# DomainQuestionPolicy
# ═══════════════════════════════════════════════════════════════════════════════

_QUESTION_POLICY_KNOWN = frozenset(
    {
        "maximum_questions",
        "allow_follow_up",
        "require_deduplication",
        "allow_clarification",
        "stop_on_blocking_gap",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainQuestionPolicy:
    """Declarative question policy. Every field is optional: ``None`` means
    the source imposes no constraint on that field.
    """

    maximum_questions: int | None = None
    allow_follow_up: bool | None = None
    require_deduplication: bool | None = None
    allow_clarification: bool | None = None
    stop_on_blocking_gap: bool | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "maximum_questions",
            _validate_positive_int_opt(self.maximum_questions, "maximum_questions"),
        )
        for attr_name in (
            "allow_follow_up",
            "require_deduplication",
            "allow_clarification",
            "stop_on_blocking_gap",
        ):
            object.__setattr__(
                self,
                attr_name,
                _validate_strict_bool_opt(getattr(self, attr_name), attr_name),
            )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "maximum_questions": self.maximum_questions,
            "allow_follow_up": self.allow_follow_up,
            "require_deduplication": self.require_deduplication,
            "allow_clarification": self.allow_clarification,
            "stop_on_blocking_gap": self.stop_on_blocking_gap,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainQuestionPolicy:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainProfileSerializationError(
                "DomainQuestionPolicy.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _QUESTION_POLICY_KNOWN, "DomainQuestionPolicy")
        try:
            return cls(**{k: data[k] for k in _QUESTION_POLICY_KNOWN if k in data})
        except DomainProfileContractError as exc:
            raise DomainProfileSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# DomainPresentationPolicy
# ═══════════════════════════════════════════════════════════════════════════════

_PRESENTATION_POLICY_KNOWN = frozenset(
    {
        "detail_level",
        "include_uncertainty",
        "include_provenance",
        "include_alternatives",
        "allow_speculation",
        "require_disclaimers",
        "metadata",
        "required_sections",
        "optional_sections",
        "suppressible_sections",
        "preferred_section_order",
        "protected_terms",
        "term_glosses",
        "preferred_components",
        "preferred_views",
        "warning_position",
        "allowed_output_types",
        "preferred_output_types",
    }
)

PRESENTATION_WARNING_POSITIONS: tuple[str, ...] = (
    "before_content",
    "in_context",
    "after_content",
)

PRESENTATION_OUTPUT_TYPES: tuple[str, ...] = (
    "HUMAN_READABLE",
    "STRUCTURED",
    "UI_COMPONENTS",
    "ARTIFACT_REQUEST",
)


def _validate_term_glosses(value: Any) -> MappingProxyType[str, str]:
    """Freeze explanatory glosses without allowing terminology replacement."""
    if not isinstance(value, Mapping):
        raise DomainProfileContractError(
            "term_glosses must be a mapping", field="term_glosses"
        )
    frozen: dict[str, str] = {}
    for term, gloss in value.items():
        if not isinstance(term, str) or not term:
            raise DomainProfileContractError(
                "term_glosses keys must be non-empty strings", field="term_glosses"
            )
        if not isinstance(gloss, str) or not gloss:
            raise DomainProfileContractError(
                "term_glosses values must be non-empty strings", field="term_glosses"
            )
        frozen[term] = gloss
    return MappingProxyType(frozen)


@dataclass(frozen=True, slots=True)
class DomainPresentationPolicy:
    """Declarative presentation policy. Every field is optional: ``None`` means
    the source imposes no constraint on that field.
    """

    detail_level: str | None = None
    include_uncertainty: bool | None = None
    include_provenance: bool | None = None
    include_alternatives: bool | None = None
    allow_speculation: bool | None = None
    require_disclaimers: bool | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    # Phase 10.16 structural fields are deliberately appended to retain the
    # positional compatibility of all Phase 10.11 callers.
    required_sections: tuple[str, ...] = ()
    optional_sections: tuple[str, ...] = ()
    suppressible_sections: tuple[str, ...] = ()
    preferred_section_order: tuple[str, ...] = ()
    protected_terms: tuple[str, ...] = ()
    term_glosses: MappingProxyType[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )
    preferred_components: tuple[str, ...] = ()
    preferred_views: tuple[str, ...] = ()
    warning_position: str | None = None
    allowed_output_types: tuple[str, ...] | None = None
    preferred_output_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "detail_level",
            _validate_ordered_choice_opt(
                self.detail_level, "detail_level", DETAIL_LEVEL_ORDER
            ),
        )
        for attr_name in (
            "include_uncertainty",
            "include_provenance",
            "include_alternatives",
            "allow_speculation",
            "require_disclaimers",
        ):
            object.__setattr__(
                self,
                attr_name,
                _validate_strict_bool_opt(getattr(self, attr_name), attr_name),
            )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )
        for attr_name in (
            "required_sections",
            "optional_sections",
            "suppressible_sections",
            "preferred_section_order",
            "protected_terms",
            "preferred_components",
            "preferred_views",
            "preferred_output_types",
        ):
            object.__setattr__(
                self,
                attr_name,
                _freeze_unique_str_tuple(getattr(self, attr_name), attr_name),
            )
        object.__setattr__(
            self, "term_glosses", _validate_term_glosses(self.term_glosses)
        )
        object.__setattr__(
            self,
            "warning_position",
            _validate_ordered_choice_opt(
                self.warning_position,
                "warning_position",
                PRESENTATION_WARNING_POSITIONS,
            ),
        )
        allowed_output_types = _freeze_optional_unique_str_tuple(
            self.allowed_output_types, "allowed_output_types"
        )
        if allowed_output_types is not None:
            unknown_outputs = set(allowed_output_types) - set(PRESENTATION_OUTPUT_TYPES)
            if unknown_outputs:
                raise DomainProfileContractError(
                    "allowed_output_types contains unsupported values: "
                    f"{sorted(unknown_outputs)}",
                    field="allowed_output_types",
                )
        object.__setattr__(self, "allowed_output_types", allowed_output_types)
        unknown_preferred = set(self.preferred_output_types) - set(
            PRESENTATION_OUTPUT_TYPES
        )
        if unknown_preferred:
            raise DomainProfileContractError(
                "preferred_output_types contains unsupported values: "
                f"{sorted(unknown_preferred)}",
                field="preferred_output_types",
            )
        if (
            self.allowed_output_types is not None
            and not set(self.preferred_output_types).issubset(self.allowed_output_types)
        ):
            raise DomainProfileContractError(
                "preferred_output_types must be allowed_output_types",
                field="preferred_output_types",
            )
        required = set(self.required_sections)
        if required & set(self.suppressible_sections):
            raise DomainProfileContractError(
                "required_sections must not overlap suppressible_sections",
                field="suppressible_sections",
            )
        if not set(self.term_glosses).issubset(self.protected_terms):
            raise DomainProfileContractError(
                "term_glosses keys must be present in protected_terms",
                field="term_glosses",
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "detail_level": self.detail_level,
            "include_uncertainty": self.include_uncertainty,
            "include_provenance": self.include_provenance,
            "include_alternatives": self.include_alternatives,
            "allow_speculation": self.allow_speculation,
            "require_disclaimers": self.require_disclaimers,
            "metadata": _deep_unfreeze_value(self.metadata),
            "required_sections": list(self.required_sections),
            "optional_sections": list(self.optional_sections),
            "suppressible_sections": list(self.suppressible_sections),
            "preferred_section_order": list(self.preferred_section_order),
            "protected_terms": list(self.protected_terms),
            "term_glosses": dict(self.term_glosses),
            "preferred_components": list(self.preferred_components),
            "preferred_views": list(self.preferred_views),
            "warning_position": self.warning_position,
            "allowed_output_types": (
                list(self.allowed_output_types)
                if self.allowed_output_types is not None
                else None
            ),
            "preferred_output_types": list(self.preferred_output_types),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainPresentationPolicy:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainProfileSerializationError(
                "DomainPresentationPolicy.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(
            data, _PRESENTATION_POLICY_KNOWN, "DomainPresentationPolicy"
        )
        try:
            return cls(**{k: data[k] for k in _PRESENTATION_POLICY_KNOWN if k in data})
        except DomainProfileContractError as exc:
            raise DomainProfileSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# DomainMemoryPolicy
# ═══════════════════════════════════════════════════════════════════════════════

_MEMORY_POLICY_KNOWN = frozenset(
    {
        "allow_read",
        "allow_write",
        "allow_long_term",
        "allow_cross_domain",
        "retention_scope",
        "sensitivity_limit",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainMemoryPolicy:
    """Declarative memory policy. Every field is optional: ``None`` means
    the source imposes no constraint on that field.
    """

    allow_read: bool | None = None
    allow_write: bool | None = None
    allow_long_term: bool | None = None
    allow_cross_domain: bool | None = None
    retention_scope: str | None = None
    sensitivity_limit: Sensitivity | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        for attr_name in (
            "allow_read",
            "allow_write",
            "allow_long_term",
            "allow_cross_domain",
        ):
            object.__setattr__(
                self,
                attr_name,
                _validate_strict_bool_opt(getattr(self, attr_name), attr_name),
            )
        object.__setattr__(
            self,
            "retention_scope",
            _validate_ordered_choice_opt(
                self.retention_scope, "retention_scope", RETENTION_SCOPE_ORDER
            ),
        )
        object.__setattr__(
            self,
            "sensitivity_limit",
            _coerce_sensitivity_opt(self.sensitivity_limit, "sensitivity_limit"),
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "allow_read": self.allow_read,
            "allow_write": self.allow_write,
            "allow_long_term": self.allow_long_term,
            "allow_cross_domain": self.allow_cross_domain,
            "retention_scope": self.retention_scope,
            "sensitivity_limit": self.sensitivity_limit.value
            if self.sensitivity_limit is not None
            else None,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainMemoryPolicy:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainProfileSerializationError(
                "DomainMemoryPolicy.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _MEMORY_POLICY_KNOWN, "DomainMemoryPolicy")
        try:
            return cls(**{k: data[k] for k in _MEMORY_POLICY_KNOWN if k in data})
        except DomainProfileContractError as exc:
            raise DomainProfileSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# DomainTemporalPolicy
# ═══════════════════════════════════════════════════════════════════════════════

_TEMPORAL_POLICY_KNOWN = frozenset(
    {
        "require_current_information",
        "allow_historical_information",
        "maximum_age_seconds",
        "require_temporal_provenance",
        "allow_future_projection",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainTemporalPolicy:
    """Declarative temporal policy. Every field is optional: ``None`` means
    the source imposes no constraint on that field.
    """

    require_current_information: bool | None = None
    allow_historical_information: bool | None = None
    maximum_age_seconds: int | None = None
    require_temporal_provenance: bool | None = None
    allow_future_projection: bool | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        for attr_name in (
            "require_current_information",
            "allow_historical_information",
            "require_temporal_provenance",
            "allow_future_projection",
        ):
            object.__setattr__(
                self,
                attr_name,
                _validate_strict_bool_opt(getattr(self, attr_name), attr_name),
            )
        object.__setattr__(
            self,
            "maximum_age_seconds",
            _validate_non_negative_int_opt(
                self.maximum_age_seconds, "maximum_age_seconds"
            ),
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "require_current_information": self.require_current_information,
            "allow_historical_information": self.allow_historical_information,
            "maximum_age_seconds": self.maximum_age_seconds,
            "require_temporal_provenance": self.require_temporal_provenance,
            "allow_future_projection": self.allow_future_projection,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainTemporalPolicy:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainProfileSerializationError(
                "DomainTemporalPolicy.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _TEMPORAL_POLICY_KNOWN, "DomainTemporalPolicy")
        try:
            return cls(**{k: data[k] for k in _TEMPORAL_POLICY_KNOWN if k in data})
        except DomainProfileContractError as exc:
            raise DomainProfileSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# DomainProductionPolicy
# ═══════════════════════════════════════════════════════════════════════════════

_PRODUCTION_POLICY_KNOWN = frozenset(
    {
        "allow_draft",
        "allow_final",
        "allow_external_action",
        "require_review",
        "require_validation",
        "maximum_output_items",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainProductionPolicy:
    """Declarative production policy. Every field is optional: ``None`` means
    the source imposes no constraint on that field.
    """

    allow_draft: bool | None = None
    allow_final: bool | None = None
    allow_external_action: bool | None = None
    require_review: bool | None = None
    require_validation: bool | None = None
    maximum_output_items: int | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        for attr_name in (
            "allow_draft",
            "allow_final",
            "allow_external_action",
            "require_review",
            "require_validation",
        ):
            object.__setattr__(
                self,
                attr_name,
                _validate_strict_bool_opt(getattr(self, attr_name), attr_name),
            )
        object.__setattr__(
            self,
            "maximum_output_items",
            _validate_positive_int_opt(
                self.maximum_output_items, "maximum_output_items"
            ),
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "allow_draft": self.allow_draft,
            "allow_final": self.allow_final,
            "allow_external_action": self.allow_external_action,
            "require_review": self.require_review,
            "require_validation": self.require_validation,
            "maximum_output_items": self.maximum_output_items,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainProductionPolicy:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainProfileSerializationError(
                "DomainProductionPolicy.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _PRODUCTION_POLICY_KNOWN, "DomainProductionPolicy")
        try:
            return cls(**{k: data[k] for k in _PRODUCTION_POLICY_KNOWN if k in data})
        except DomainProfileContractError as exc:
            raise DomainProfileSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ── Nested typed-policy parsing helpers (shared by Definition/Overlay) ─────────


def _parse_question_policy(raw: Any, field_name: str) -> DomainQuestionPolicy:
    if raw is None:
        return DomainQuestionPolicy()
    if isinstance(raw, DomainQuestionPolicy):
        return raw
    if isinstance(raw, Mapping):
        return DomainQuestionPolicy.from_dict(dict(raw))
    raise DomainProfileContractError(
        f"{field_name} must be a DomainQuestionPolicy or mapping, "
        f"got {type(raw).__name__}",
        field=field_name,
    )


def _parse_presentation_policy(raw: Any, field_name: str) -> DomainPresentationPolicy:
    if raw is None:
        return DomainPresentationPolicy()
    if isinstance(raw, DomainPresentationPolicy):
        return raw
    if isinstance(raw, Mapping):
        return DomainPresentationPolicy.from_dict(dict(raw))
    raise DomainProfileContractError(
        f"{field_name} must be a DomainPresentationPolicy or mapping, "
        f"got {type(raw).__name__}",
        field=field_name,
    )


def _parse_memory_policy(raw: Any, field_name: str) -> DomainMemoryPolicy:
    if raw is None:
        return DomainMemoryPolicy()
    if isinstance(raw, DomainMemoryPolicy):
        return raw
    if isinstance(raw, Mapping):
        return DomainMemoryPolicy.from_dict(dict(raw))
    raise DomainProfileContractError(
        f"{field_name} must be a DomainMemoryPolicy or mapping, "
        f"got {type(raw).__name__}",
        field=field_name,
    )


def _parse_temporal_policy(raw: Any, field_name: str) -> DomainTemporalPolicy:
    if raw is None:
        return DomainTemporalPolicy()
    if isinstance(raw, DomainTemporalPolicy):
        return raw
    if isinstance(raw, Mapping):
        return DomainTemporalPolicy.from_dict(dict(raw))
    raise DomainProfileContractError(
        f"{field_name} must be a DomainTemporalPolicy or mapping, "
        f"got {type(raw).__name__}",
        field=field_name,
    )


def _parse_production_policy(raw: Any, field_name: str) -> DomainProductionPolicy:
    if raw is None:
        return DomainProductionPolicy()
    if isinstance(raw, DomainProductionPolicy):
        return raw
    if isinstance(raw, Mapping):
        return DomainProductionPolicy.from_dict(dict(raw))
    raise DomainProfileContractError(
        f"{field_name} must be a DomainProductionPolicy or mapping, "
        f"got {type(raw).__name__}",
        field=field_name,
    )


def _policies_to_dict(
    question_policy: DomainQuestionPolicy,
    presentation_policy: DomainPresentationPolicy,
    memory_policy: DomainMemoryPolicy,
    temporal_policy: DomainTemporalPolicy,
    production_policy: DomainProductionPolicy,
) -> dict[str, Any]:
    return {
        "question_policy": question_policy.to_dict(),
        "presentation_policy": presentation_policy.to_dict(),
        "memory_policy": memory_policy.to_dict(),
        "temporal_policy": temporal_policy.to_dict(),
        "production_policy": production_policy.to_dict(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# DomainProfileDefinition
# ═══════════════════════════════════════════════════════════════════════════════

_DEFINITION_KNOWN = frozenset(
    {
        "id",
        "domain_id",
        "profile_name",
        "required_rules",
        "optional_rules",
        "prohibited_rules",
        "allowed_resource_kinds",
        "priority_resource_kinds",
        "prohibited_resource_kinds",
        "minimum_confidence",
        "reasoning_depth",
        "allowed_inferences",
        "prohibited_inferences",
        "maximum_questions",
        "escalation_rules",
        "prohibited_actions",
        "question_policy",
        "presentation_policy",
        "memory_policy",
        "temporal_policy",
        "production_policy",
        "permissions",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainProfileDefinition:
    """A declarative, immutable cognitive profile for a single domain.

    Configures the Cognitive Layer (Phase 8); it never executes reasoning
    and never contains executable values.
    """

    id: str
    domain_id: DomainId
    profile_name: str
    required_rules: tuple[str, ...] = ()
    optional_rules: tuple[str, ...] = ()
    prohibited_rules: tuple[str, ...] = ()
    allowed_resource_kinds: tuple[str, ...] | None = None
    priority_resource_kinds: tuple[str, ...] = ()
    prohibited_resource_kinds: tuple[str, ...] = ()
    minimum_confidence: float = 0.0
    reasoning_depth: DomainReasoningDepth = DomainReasoningDepth.EXHAUSTIVE
    allowed_inferences: tuple[str, ...] | None = None
    prohibited_inferences: tuple[str, ...] = ()
    maximum_questions: int = 16
    escalation_rules: tuple[str, ...] = ()
    prohibited_actions: tuple[str, ...] = ()
    question_policy: DomainQuestionPolicy = field(default_factory=DomainQuestionPolicy)
    presentation_policy: DomainPresentationPolicy = field(
        default_factory=DomainPresentationPolicy
    )
    memory_policy: DomainMemoryPolicy = field(default_factory=DomainMemoryPolicy)
    temporal_policy: DomainTemporalPolicy = field(default_factory=DomainTemporalPolicy)
    production_policy: DomainProductionPolicy = field(
        default_factory=DomainProductionPolicy
    )
    permissions: tuple[str, ...] | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self, "domain_id", _coerce_domain_id(self.domain_id, "domain_id")
        )
        object.__setattr__(
            self,
            "profile_name",
            _validate_non_empty_str(self.profile_name, "profile_name"),
        )

        for attr_name in (
            "required_rules",
            "optional_rules",
            "prohibited_rules",
            "priority_resource_kinds",
            "prohibited_resource_kinds",
            "prohibited_inferences",
            "escalation_rules",
            "prohibited_actions",
        ):
            object.__setattr__(
                self,
                attr_name,
                _freeze_unique_str_tuple(getattr(self, attr_name), attr_name),
            )

        object.__setattr__(
            self,
            "allowed_resource_kinds",
            _freeze_optional_unique_str_tuple(
                self.allowed_resource_kinds, "allowed_resource_kinds"
            ),
        )
        object.__setattr__(
            self,
            "allowed_inferences",
            _freeze_optional_unique_str_tuple(
                self.allowed_inferences, "allowed_inferences"
            ),
        )
        object.__setattr__(
            self,
            "permissions",
            _freeze_optional_unique_str_tuple(self.permissions, "permissions"),
        )

        object.__setattr__(
            self,
            "minimum_confidence",
            _validate_confidence(self.minimum_confidence, "minimum_confidence"),
        )
        object.__setattr__(
            self,
            "reasoning_depth",
            _coerce_reasoning_depth(self.reasoning_depth, "reasoning_depth"),
        )
        object.__setattr__(
            self,
            "maximum_questions",
            _validate_positive_int(self.maximum_questions, "maximum_questions"),
        )

        if self.allowed_resource_kinds is not None:
            unknown_priority = set(self.priority_resource_kinds) - set(
                self.allowed_resource_kinds
            )
            if unknown_priority:
                raise DomainProfileContractError(
                    "priority_resource_kinds must be a subset of allowed_resource_kinds: "
                    f"{sorted(unknown_priority)}",
                    field="priority_resource_kinds",
                )
        priority_prohibited = set(self.priority_resource_kinds) & set(
            self.prohibited_resource_kinds
        )
        if priority_prohibited:
            raise DomainProfileContractError(
                "priority_resource_kinds must not overlap prohibited_resource_kinds: "
                f"{sorted(priority_prohibited)}",
                field="priority_resource_kinds",
            )

        object.__setattr__(
            self,
            "question_policy",
            _parse_question_policy(self.question_policy, "question_policy"),
        )
        object.__setattr__(
            self,
            "presentation_policy",
            _parse_presentation_policy(self.presentation_policy, "presentation_policy"),
        )
        object.__setattr__(
            self,
            "memory_policy",
            _parse_memory_policy(self.memory_policy, "memory_policy"),
        )
        object.__setattr__(
            self,
            "temporal_policy",
            _parse_temporal_policy(self.temporal_policy, "temporal_policy"),
        )
        object.__setattr__(
            self,
            "production_policy",
            _parse_production_policy(self.production_policy, "production_policy"),
        )

        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "domain_id": str(self.domain_id),
            "profile_name": self.profile_name,
            "required_rules": list(self.required_rules),
            "optional_rules": list(self.optional_rules),
            "prohibited_rules": list(self.prohibited_rules),
            "allowed_resource_kinds": (
                list(self.allowed_resource_kinds)
                if self.allowed_resource_kinds is not None
                else None
            ),
            "priority_resource_kinds": list(self.priority_resource_kinds),
            "prohibited_resource_kinds": list(self.prohibited_resource_kinds),
            "minimum_confidence": self.minimum_confidence,
            "reasoning_depth": self.reasoning_depth.value,
            "allowed_inferences": (
                list(self.allowed_inferences)
                if self.allowed_inferences is not None
                else None
            ),
            "prohibited_inferences": list(self.prohibited_inferences),
            "maximum_questions": self.maximum_questions,
            "escalation_rules": list(self.escalation_rules),
            "prohibited_actions": list(self.prohibited_actions),
            **_policies_to_dict(
                self.question_policy,
                self.presentation_policy,
                self.memory_policy,
                self.temporal_policy,
                self.production_policy,
            ),
            "permissions": (
                list(self.permissions) if self.permissions is not None else None
            ),
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainProfileDefinition:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainProfileSerializationError(
                "DomainProfileDefinition.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _DEFINITION_KNOWN, "DomainProfileDefinition")
        required = {"id", "domain_id", "profile_name"}
        missing = required - set(data.keys())
        if missing:
            raise DomainProfileSerializationError(
                f"DomainProfileDefinition.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        kwargs: dict[str, Any] = {k: v for k, v in data.items() if k != "metadata"}
        kwargs["metadata"] = data.get("metadata")
        try:
            return cls(**kwargs)
        except DomainProfileContractError as exc:
            raise DomainProfileSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# DomainProfileOverlay
# ═══════════════════════════════════════════════════════════════════════════════

_OVERLAY_KNOWN = frozenset(
    {
        "id",
        "source",
        "source_id",
        "priority",
        "required_rules",
        "optional_rules",
        "prohibited_rules",
        "allowed_resource_kinds",
        "priority_resource_kinds",
        "prohibited_resource_kinds",
        "minimum_confidence",
        "reasoning_depth",
        "allowed_inferences",
        "prohibited_inferences",
        "maximum_questions",
        "escalation_rules",
        "prohibited_actions",
        "question_policy",
        "presentation_policy",
        "memory_policy",
        "temporal_policy",
        "production_policy",
        "permissions",
        "reason",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainProfileOverlay:
    """A partial, declarative modification contributed by a single source.

    Absent (``None``) fields mean "no change". Overlays never carry
    executable callbacks and can only narrow, never broaden.
    """

    id: str
    source: DomainProfileSource
    source_id: str | None = None
    priority: int = 0
    required_rules: tuple[str, ...] | None = None
    optional_rules: tuple[str, ...] | None = None
    prohibited_rules: tuple[str, ...] | None = None
    allowed_resource_kinds: tuple[str, ...] | None = None
    priority_resource_kinds: tuple[str, ...] | None = None
    prohibited_resource_kinds: tuple[str, ...] | None = None
    minimum_confidence: float | None = None
    reasoning_depth: DomainReasoningDepth | None = None
    allowed_inferences: tuple[str, ...] | None = None
    prohibited_inferences: tuple[str, ...] | None = None
    maximum_questions: int | None = None
    escalation_rules: tuple[str, ...] | None = None
    prohibited_actions: tuple[str, ...] | None = None
    question_policy: DomainQuestionPolicy | None = None
    presentation_policy: DomainPresentationPolicy | None = None
    memory_policy: DomainMemoryPolicy | None = None
    temporal_policy: DomainTemporalPolicy | None = None
    production_policy: DomainProductionPolicy | None = None
    permissions: tuple[str, ...] | None = None
    reason: str | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self, "source", _coerce_profile_source(self.source, "source")
        )
        object.__setattr__(self, "source_id", _normalize_empty_to_none(self.source_id))
        if self.source != DomainProfileSource.GLOBAL_POLICY and self.source_id is None:
            raise DomainProfileContractError(
                "source_id is required for contextual overlays",
                field="source_id",
                details={"source": self.source.value},
            )
        if self.source_id is not None:
            object.__setattr__(
                self,
                "source_id",
                _validate_non_empty_str(self.source_id, "source_id"),
            )
        object.__setattr__(
            self, "priority", _validate_non_negative_int(self.priority, "priority")
        )

        for attr_name in (
            "required_rules",
            "optional_rules",
            "prohibited_rules",
            "allowed_resource_kinds",
            "priority_resource_kinds",
            "prohibited_resource_kinds",
            "allowed_inferences",
            "prohibited_inferences",
            "escalation_rules",
            "prohibited_actions",
            "permissions",
        ):
            object.__setattr__(
                self,
                attr_name,
                _freeze_optional_unique_str_tuple(getattr(self, attr_name), attr_name),
            )

        object.__setattr__(
            self,
            "minimum_confidence",
            _validate_confidence_opt(self.minimum_confidence, "minimum_confidence"),
        )
        object.__setattr__(
            self,
            "reasoning_depth",
            _coerce_reasoning_depth_opt(self.reasoning_depth, "reasoning_depth"),
        )
        object.__setattr__(
            self,
            "maximum_questions",
            _validate_positive_int_opt(self.maximum_questions, "maximum_questions"),
        )

        if (
            self.allowed_resource_kinds is not None
            and self.priority_resource_kinds is not None
        ):
            unknown_priority = set(self.priority_resource_kinds) - set(
                self.allowed_resource_kinds
            )
            if unknown_priority:
                raise DomainProfileContractError(
                    "priority_resource_kinds must be a subset of allowed_resource_kinds: "
                    f"{sorted(unknown_priority)}",
                    field="priority_resource_kinds",
                )
        if (
            self.priority_resource_kinds is not None
            and self.prohibited_resource_kinds is not None
        ):
            overlap = set(self.priority_resource_kinds) & set(
                self.prohibited_resource_kinds
            )
            if overlap:
                raise DomainProfileContractError(
                    "priority_resource_kinds must not overlap prohibited_resource_kinds: "
                    f"{sorted(overlap)}",
                    field="priority_resource_kinds",
                )

        if self.question_policy is not None:
            object.__setattr__(
                self,
                "question_policy",
                _parse_question_policy(self.question_policy, "question_policy"),
            )
        if self.presentation_policy is not None:
            object.__setattr__(
                self,
                "presentation_policy",
                _parse_presentation_policy(
                    self.presentation_policy, "presentation_policy"
                ),
            )
        if self.memory_policy is not None:
            object.__setattr__(
                self,
                "memory_policy",
                _parse_memory_policy(self.memory_policy, "memory_policy"),
            )
        if self.temporal_policy is not None:
            object.__setattr__(
                self,
                "temporal_policy",
                _parse_temporal_policy(self.temporal_policy, "temporal_policy"),
            )
        if self.production_policy is not None:
            object.__setattr__(
                self,
                "production_policy",
                _parse_production_policy(self.production_policy, "production_policy"),
            )

        object.__setattr__(self, "reason", _normalize_empty_to_none(self.reason))
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "source": self.source.value,
            "source_id": self.source_id,
            "priority": self.priority,
            "required_rules": (
                list(self.required_rules) if self.required_rules is not None else None
            ),
            "optional_rules": (
                list(self.optional_rules) if self.optional_rules is not None else None
            ),
            "prohibited_rules": (
                list(self.prohibited_rules)
                if self.prohibited_rules is not None
                else None
            ),
            "allowed_resource_kinds": (
                list(self.allowed_resource_kinds)
                if self.allowed_resource_kinds is not None
                else None
            ),
            "priority_resource_kinds": (
                list(self.priority_resource_kinds)
                if self.priority_resource_kinds is not None
                else None
            ),
            "prohibited_resource_kinds": (
                list(self.prohibited_resource_kinds)
                if self.prohibited_resource_kinds is not None
                else None
            ),
            "minimum_confidence": self.minimum_confidence,
            "reasoning_depth": (
                self.reasoning_depth.value if self.reasoning_depth is not None else None
            ),
            "allowed_inferences": (
                list(self.allowed_inferences)
                if self.allowed_inferences is not None
                else None
            ),
            "prohibited_inferences": (
                list(self.prohibited_inferences)
                if self.prohibited_inferences is not None
                else None
            ),
            "maximum_questions": self.maximum_questions,
            "escalation_rules": (
                list(self.escalation_rules)
                if self.escalation_rules is not None
                else None
            ),
            "prohibited_actions": (
                list(self.prohibited_actions)
                if self.prohibited_actions is not None
                else None
            ),
            "question_policy": (
                self.question_policy.to_dict()
                if self.question_policy is not None
                else None
            ),
            "presentation_policy": (
                self.presentation_policy.to_dict()
                if self.presentation_policy is not None
                else None
            ),
            "memory_policy": (
                self.memory_policy.to_dict() if self.memory_policy is not None else None
            ),
            "temporal_policy": (
                self.temporal_policy.to_dict()
                if self.temporal_policy is not None
                else None
            ),
            "production_policy": (
                self.production_policy.to_dict()
                if self.production_policy is not None
                else None
            ),
            "permissions": (
                list(self.permissions) if self.permissions is not None else None
            ),
            "reason": self.reason,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainProfileOverlay:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainProfileSerializationError(
                "DomainProfileOverlay.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _OVERLAY_KNOWN, "DomainProfileOverlay")
        required = {"id", "source"}
        missing = required - set(data.keys())
        if missing:
            raise DomainProfileSerializationError(
                f"DomainProfileOverlay.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        kwargs: dict[str, Any] = {k: v for k, v in data.items() if k != "metadata"}
        kwargs["metadata"] = data.get("metadata")
        try:
            return cls(**kwargs)
        except DomainProfileContractError as exc:
            raise DomainProfileSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# DomainProfileResolutionRequest
# ═══════════════════════════════════════════════════════════════════════════════

_REQUEST_KNOWN = frozenset(
    {
        "id",
        "primary_domain",
        "supporting_domains",
        "workflow_ids",
        "operation_ids",
        "risk_level",
        "actor_context",
        "autonomy_level",
        "explicit_requirements",
        "permissions",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainProfileResolutionRequest:
    """An immutable, declarative request to resolve an effective Domain Profile."""

    id: str
    primary_domain: DomainId
    supporting_domains: tuple[DomainId, ...] = ()
    workflow_ids: tuple[str, ...] = ()
    operation_ids: tuple[str, ...] = ()
    risk_level: str | None = None
    actor_context: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )
    autonomy_level: str | None = None
    explicit_requirements: tuple[str, ...] = ()
    permissions: tuple[str, ...] | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
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
            raise DomainProfileContractError(
                "primary_domain must not appear in supporting_domains",
                field="supporting_domains",
            )
        object.__setattr__(
            self,
            "workflow_ids",
            _freeze_unique_str_tuple(self.workflow_ids, "workflow_ids"),
        )
        object.__setattr__(
            self,
            "operation_ids",
            _freeze_unique_str_tuple(self.operation_ids, "operation_ids"),
        )
        object.__setattr__(
            self, "risk_level", _normalize_empty_to_none(self.risk_level)
        )
        object.__setattr__(
            self,
            "actor_context",
            _validate_json_safe_metadata(self.actor_context, "actor_context"),
        )
        object.__setattr__(
            self, "autonomy_level", _normalize_empty_to_none(self.autonomy_level)
        )
        object.__setattr__(
            self,
            "explicit_requirements",
            _freeze_unique_str_tuple(
                self.explicit_requirements, "explicit_requirements"
            ),
        )
        object.__setattr__(
            self,
            "permissions",
            _freeze_optional_unique_str_tuple(self.permissions, "permissions"),
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "primary_domain": str(self.primary_domain),
            "supporting_domains": [str(d) for d in self.supporting_domains],
            "workflow_ids": list(self.workflow_ids),
            "operation_ids": list(self.operation_ids),
            "risk_level": self.risk_level,
            "actor_context": _deep_unfreeze_value(self.actor_context),
            "autonomy_level": self.autonomy_level,
            "explicit_requirements": list(self.explicit_requirements),
            "permissions": (
                list(self.permissions) if self.permissions is not None else None
            ),
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainProfileResolutionRequest:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainProfileSerializationError(
                "DomainProfileResolutionRequest.from_dict requires a mapping",
                field="data",
            )
        _reject_unknown_fields(data, _REQUEST_KNOWN, "DomainProfileResolutionRequest")
        required = {"id", "primary_domain"}
        missing = required - set(data.keys())
        if missing:
            raise DomainProfileSerializationError(
                "DomainProfileResolutionRequest.from_dict missing required fields: "
                f"{sorted(missing)}",
                field="data",
            )
        kwargs: dict[str, Any] = {k: v for k, v in data.items() if k != "metadata"}
        kwargs["metadata"] = data.get("metadata")
        try:
            return cls(**kwargs)
        except DomainProfileContractError as exc:
            raise DomainProfileSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# DomainProfileModification
# ═══════════════════════════════════════════════════════════════════════════════

_MODIFICATION_KNOWN = frozenset(
    {
        "field",
        "source",
        "source_id",
        "operation",
        "previous_value",
        "new_value",
        "reason",
        "restrictive",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainProfileModification:
    """A single, auditable trace record of a change made during composition."""

    field: str
    source: DomainProfileSource
    source_id: str | None
    operation: str
    previous_value: Any
    new_value: Any
    reason: str | None = None
    restrictive: bool = True
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "field", _validate_non_empty_str(self.field, "field"))
        object.__setattr__(
            self, "source", _coerce_profile_source(self.source, "source")
        )
        object.__setattr__(self, "source_id", _normalize_empty_to_none(self.source_id))
        object.__setattr__(
            self, "operation", _validate_non_empty_str(self.operation, "operation")
        )
        object.__setattr__(
            self,
            "previous_value",
            _deep_freeze(
                _validate_json_safe_metadata(
                    {"v": self.previous_value}, "previous_value"
                )["v"]
                if self.previous_value is not None
                else None
            ),
        )
        object.__setattr__(
            self,
            "new_value",
            _deep_freeze(
                _validate_json_safe_metadata({"v": self.new_value}, "new_value")["v"]
                if self.new_value is not None
                else None
            ),
        )
        object.__setattr__(self, "reason", _normalize_empty_to_none(self.reason))
        object.__setattr__(
            self, "restrictive", _validate_strict_bool(self.restrictive, "restrictive")
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "field": self.field,
            "source": self.source.value,
            "source_id": self.source_id,
            "operation": self.operation,
            "previous_value": _deep_unfreeze_value(self.previous_value),
            "new_value": _deep_unfreeze_value(self.new_value),
            "reason": self.reason,
            "restrictive": self.restrictive,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainProfileModification:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainProfileSerializationError(
                "DomainProfileModification.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _MODIFICATION_KNOWN, "DomainProfileModification")
        required = {"field", "source", "operation", "previous_value", "new_value"}
        missing = required - set(data.keys())
        if missing:
            raise DomainProfileSerializationError(
                f"DomainProfileModification.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                field=data["field"],
                source=data["source"],
                source_id=data.get("source_id"),
                operation=data["operation"],
                previous_value=data["previous_value"],
                new_value=data["new_value"],
                reason=data.get("reason"),
                restrictive=data.get("restrictive", True),
                metadata=data.get("metadata"),
            )
        except DomainProfileContractError as exc:
            raise DomainProfileSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# DomainProfileConflict
# ═══════════════════════════════════════════════════════════════════════════════

_CONFLICT_KNOWN = frozenset(
    {
        "code",
        "field",
        "severity",
        "sources",
        "description",
        "blocking",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainProfileConflict:
    """A conflict detected during Domain Profile composition or resolution."""

    code: str
    field: str
    severity: DomainProfileConflictSeverity
    sources: tuple[DomainProfileSource, ...]
    description: str
    blocking: bool = False
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _validate_non_empty_str(self.code, "code"))
        object.__setattr__(self, "field", _validate_non_empty_str(self.field, "field"))
        object.__setattr__(
            self, "severity", _coerce_conflict_severity(self.severity, "severity")
        )
        object.__setattr__(
            self, "sources", _freeze_source_tuple(self.sources, "sources")
        )
        if len(self.sources) == 0:
            raise DomainProfileContractError(
                "sources must not be empty", field="sources"
            )
        object.__setattr__(
            self,
            "description",
            _validate_non_empty_str(self.description, "description"),
        )
        object.__setattr__(
            self, "blocking", _validate_strict_bool(self.blocking, "blocking")
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "code": self.code,
            "field": self.field,
            "severity": self.severity.value,
            "sources": [s.value for s in self.sources],
            "description": self.description,
            "blocking": self.blocking,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainProfileConflict:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainProfileSerializationError(
                "DomainProfileConflict.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _CONFLICT_KNOWN, "DomainProfileConflict")
        required = {"code", "field", "severity", "sources", "description"}
        missing = required - set(data.keys())
        if missing:
            raise DomainProfileSerializationError(
                f"DomainProfileConflict.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                code=data["code"],
                field=data["field"],
                severity=data["severity"],
                sources=tuple(data["sources"]),
                description=data["description"],
                blocking=data.get("blocking", False),
                metadata=data.get("metadata"),
            )
        except DomainProfileContractError as exc:
            raise DomainProfileSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# DomainProfileRejection
# ═══════════════════════════════════════════════════════════════════════════════

_REJECTION_KNOWN = frozenset(
    {"source", "source_id", "field", "reason", "blocking", "metadata"}
)


@dataclass(frozen=True, slots=True)
class DomainProfileRejection:
    """A record of a source (usually an overlay) that was rejected during resolution."""

    source: DomainProfileSource
    source_id: str | None
    field: str
    reason: str
    blocking: bool = False
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source", _coerce_profile_source(self.source, "source")
        )
        object.__setattr__(self, "source_id", _normalize_empty_to_none(self.source_id))
        object.__setattr__(self, "field", _validate_non_empty_str(self.field, "field"))
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
        """Serialize to dictionary."""
        return {
            "source": self.source.value,
            "source_id": self.source_id,
            "field": self.field,
            "reason": self.reason,
            "blocking": self.blocking,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainProfileRejection:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainProfileSerializationError(
                "DomainProfileRejection.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _REJECTION_KNOWN, "DomainProfileRejection")
        required = {"source", "field", "reason"}
        missing = required - set(data.keys())
        if missing:
            raise DomainProfileSerializationError(
                f"DomainProfileRejection.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                source=data["source"],
                source_id=data.get("source_id"),
                field=data["field"],
                reason=data["reason"],
                blocking=data.get("blocking", False),
                metadata=data.get("metadata"),
            )
        except DomainProfileContractError as exc:
            raise DomainProfileSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# DomainProfileDecision
# ═══════════════════════════════════════════════════════════════════════════════

_DECISION_KNOWN = frozenset(
    {"code", "field", "source", "source_id", "reason", "blocking", "metadata"}
)


@dataclass(frozen=True, slots=True)
class DomainProfileDecision:
    """A single decision made during Domain Profile composition or resolution."""

    code: DomainProfileDecisionCode
    field: str | None
    source: DomainProfileSource
    source_id: str | None = None
    reason: str | None = None
    blocking: bool = False
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", _coerce_decision_code(self.code, "code"))
        if self.field is not None:
            object.__setattr__(
                self, "field", _validate_non_empty_str(self.field, "field")
            )
        object.__setattr__(
            self, "source", _coerce_profile_source(self.source, "source")
        )
        object.__setattr__(self, "source_id", _normalize_empty_to_none(self.source_id))
        object.__setattr__(self, "reason", _normalize_empty_to_none(self.reason))
        object.__setattr__(
            self, "blocking", _validate_strict_bool(self.blocking, "blocking")
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "code": self.code.value,
            "field": self.field,
            "source": self.source.value,
            "source_id": self.source_id,
            "reason": self.reason,
            "blocking": self.blocking,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainProfileDecision:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainProfileSerializationError(
                "DomainProfileDecision.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _DECISION_KNOWN, "DomainProfileDecision")
        required = {"code", "source"}
        missing = required - set(data.keys())
        if missing:
            raise DomainProfileSerializationError(
                f"DomainProfileDecision.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                code=data["code"],
                field=data.get("field"),
                source=data["source"],
                source_id=data.get("source_id"),
                reason=data.get("reason"),
                blocking=data.get("blocking", False),
                metadata=data.get("metadata"),
            )
        except DomainProfileContractError as exc:
            raise DomainProfileSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ── Nested modification-tuple coercion (shared by Draft/ResolvedDomainProfile) ─


def _freeze_modification_tuple(
    seq: Any, field_name: str
) -> tuple[DomainProfileModification, ...]:
    if seq is None:
        return ()
    result: list[DomainProfileModification] = []
    for i, item in enumerate(seq):
        if isinstance(item, DomainProfileModification):
            result.append(item)
        elif isinstance(item, Mapping):
            result.append(DomainProfileModification.from_dict(dict(item)))
        else:
            raise DomainProfileContractError(
                f"{field_name}[{i}] must be a DomainProfileModification or mapping, "
                f"got {type(item).__name__}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


def _freeze_conflict_tuple(
    seq: Any, field_name: str
) -> tuple[DomainProfileConflict, ...]:
    if seq is None:
        return ()
    result: list[DomainProfileConflict] = []
    for i, item in enumerate(seq):
        if isinstance(item, DomainProfileConflict):
            result.append(item)
        elif isinstance(item, Mapping):
            result.append(DomainProfileConflict.from_dict(dict(item)))
        else:
            raise DomainProfileContractError(
                f"{field_name}[{i}] must be a DomainProfileConflict or mapping, "
                f"got {type(item).__name__}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


def _freeze_rejection_tuple(
    seq: Any, field_name: str
) -> tuple[DomainProfileRejection, ...]:
    if seq is None:
        return ()
    result: list[DomainProfileRejection] = []
    for i, item in enumerate(seq):
        if isinstance(item, DomainProfileRejection):
            result.append(item)
        elif isinstance(item, Mapping):
            result.append(DomainProfileRejection.from_dict(dict(item)))
        else:
            raise DomainProfileContractError(
                f"{field_name}[{i}] must be a DomainProfileRejection or mapping, "
                f"got {type(item).__name__}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


def _freeze_decision_tuple(
    seq: Any, field_name: str
) -> tuple[DomainProfileDecision, ...]:
    if seq is None:
        return ()
    result: list[DomainProfileDecision] = []
    for i, item in enumerate(seq):
        if isinstance(item, DomainProfileDecision):
            result.append(item)
        elif isinstance(item, Mapping):
            result.append(DomainProfileDecision.from_dict(dict(item)))
        else:
            raise DomainProfileContractError(
                f"{field_name}[{i}] must be a DomainProfileDecision or mapping, "
                f"got {type(item).__name__}",
                field=f"{field_name}[{i}]",
            )
    return tuple(result)


# ═══════════════════════════════════════════════════════════════════════════════
# DomainProfileDraft
# ═══════════════════════════════════════════════════════════════════════════════
#
# Produced by the pure DomainProfileComposer. Carries the same effective
# fields as ResolvedDomainProfile, but never fabricates an id, trace_id, or
# timestamp — those are materialized later, exclusively by the resolver.

_DRAFT_KNOWN = frozenset(
    {
        "primary_domain",
        "supporting_domains",
        "profile_names",
        "required_rules",
        "optional_rules",
        "prohibited_rules",
        "allowed_resource_kinds",
        "priority_resource_kinds",
        "prohibited_resource_kinds",
        "minimum_confidence",
        "reasoning_depth",
        "allowed_inferences",
        "prohibited_inferences",
        "maximum_questions",
        "escalation_rules",
        "prohibited_actions",
        "question_policy",
        "presentation_policy",
        "memory_policy",
        "temporal_policy",
        "production_policy",
        "permissions",
        "modifications",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainProfileDraft:
    """The pure, unmaterialized result of Domain Profile composition."""

    primary_domain: DomainId
    supporting_domains: tuple[DomainId, ...] = ()
    profile_names: tuple[str, ...] = ()
    required_rules: tuple[str, ...] = ()
    optional_rules: tuple[str, ...] = ()
    prohibited_rules: tuple[str, ...] = ()
    allowed_resource_kinds: tuple[str, ...] | None = None
    priority_resource_kinds: tuple[str, ...] = ()
    prohibited_resource_kinds: tuple[str, ...] = ()
    minimum_confidence: float = 0.0
    reasoning_depth: DomainReasoningDepth = DomainReasoningDepth.EXHAUSTIVE
    allowed_inferences: tuple[str, ...] | None = None
    prohibited_inferences: tuple[str, ...] = ()
    maximum_questions: int = 16
    escalation_rules: tuple[str, ...] = ()
    prohibited_actions: tuple[str, ...] = ()
    question_policy: DomainQuestionPolicy = field(default_factory=DomainQuestionPolicy)
    presentation_policy: DomainPresentationPolicy = field(
        default_factory=DomainPresentationPolicy
    )
    memory_policy: DomainMemoryPolicy = field(default_factory=DomainMemoryPolicy)
    temporal_policy: DomainTemporalPolicy = field(default_factory=DomainTemporalPolicy)
    production_policy: DomainProductionPolicy = field(
        default_factory=DomainProductionPolicy
    )
    permissions: tuple[str, ...] | None = None
    modifications: tuple[DomainProfileModification, ...] = ()
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
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
        object.__setattr__(
            self,
            "profile_names",
            _freeze_unique_str_tuple(self.profile_names, "profile_names"),
        )

        for attr_name in (
            "required_rules",
            "optional_rules",
            "prohibited_rules",
            "priority_resource_kinds",
            "prohibited_resource_kinds",
            "prohibited_inferences",
            "escalation_rules",
            "prohibited_actions",
        ):
            object.__setattr__(
                self,
                attr_name,
                _freeze_unique_str_tuple(getattr(self, attr_name), attr_name),
            )

        object.__setattr__(
            self,
            "allowed_resource_kinds",
            _freeze_optional_unique_str_tuple(
                self.allowed_resource_kinds, "allowed_resource_kinds"
            ),
        )
        object.__setattr__(
            self,
            "allowed_inferences",
            _freeze_optional_unique_str_tuple(
                self.allowed_inferences, "allowed_inferences"
            ),
        )
        object.__setattr__(
            self,
            "permissions",
            _freeze_optional_unique_str_tuple(self.permissions, "permissions"),
        )

        object.__setattr__(
            self,
            "minimum_confidence",
            _validate_confidence(self.minimum_confidence, "minimum_confidence"),
        )
        object.__setattr__(
            self,
            "reasoning_depth",
            _coerce_reasoning_depth(self.reasoning_depth, "reasoning_depth"),
        )
        object.__setattr__(
            self,
            "maximum_questions",
            _validate_positive_int(self.maximum_questions, "maximum_questions"),
        )

        object.__setattr__(
            self,
            "question_policy",
            _parse_question_policy(self.question_policy, "question_policy"),
        )
        object.__setattr__(
            self,
            "presentation_policy",
            _parse_presentation_policy(self.presentation_policy, "presentation_policy"),
        )
        object.__setattr__(
            self,
            "memory_policy",
            _parse_memory_policy(self.memory_policy, "memory_policy"),
        )
        object.__setattr__(
            self,
            "temporal_policy",
            _parse_temporal_policy(self.temporal_policy, "temporal_policy"),
        )
        object.__setattr__(
            self,
            "production_policy",
            _parse_production_policy(self.production_policy, "production_policy"),
        )

        object.__setattr__(
            self,
            "modifications",
            _freeze_modification_tuple(self.modifications, "modifications"),
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "primary_domain": str(self.primary_domain),
            "supporting_domains": [str(d) for d in self.supporting_domains],
            "profile_names": list(self.profile_names),
            "required_rules": list(self.required_rules),
            "optional_rules": list(self.optional_rules),
            "prohibited_rules": list(self.prohibited_rules),
            "allowed_resource_kinds": (
                list(self.allowed_resource_kinds)
                if self.allowed_resource_kinds is not None
                else None
            ),
            "priority_resource_kinds": list(self.priority_resource_kinds),
            "prohibited_resource_kinds": list(self.prohibited_resource_kinds),
            "minimum_confidence": self.minimum_confidence,
            "reasoning_depth": self.reasoning_depth.value,
            "allowed_inferences": (
                list(self.allowed_inferences)
                if self.allowed_inferences is not None
                else None
            ),
            "prohibited_inferences": list(self.prohibited_inferences),
            "maximum_questions": self.maximum_questions,
            "escalation_rules": list(self.escalation_rules),
            "prohibited_actions": list(self.prohibited_actions),
            **_policies_to_dict(
                self.question_policy,
                self.presentation_policy,
                self.memory_policy,
                self.temporal_policy,
                self.production_policy,
            ),
            "permissions": (
                list(self.permissions) if self.permissions is not None else None
            ),
            "modifications": [m.to_dict() for m in self.modifications],
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainProfileDraft:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainProfileSerializationError(
                "DomainProfileDraft.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _DRAFT_KNOWN, "DomainProfileDraft")
        if "primary_domain" not in data:
            raise DomainProfileSerializationError(
                "DomainProfileDraft.from_dict missing required field 'primary_domain'",
                field="primary_domain",
            )
        kwargs: dict[str, Any] = {k: v for k, v in data.items() if k != "metadata"}
        kwargs["metadata"] = data.get("metadata")
        try:
            return cls(**kwargs)
        except DomainProfileContractError as exc:
            raise DomainProfileSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# ResolvedDomainProfile
# ═══════════════════════════════════════════════════════════════════════════════

_RESOLVED_KNOWN = frozenset(_DRAFT_KNOWN | {"id", "trace_id", "resolved_at"})


@dataclass(frozen=True, slots=True)
class ResolvedDomainProfile:
    """The final, materialized, effective Domain Profile produced by resolution."""

    id: str
    primary_domain: DomainId
    supporting_domains: tuple[DomainId, ...]
    profile_names: tuple[str, ...]
    required_rules: tuple[str, ...]
    optional_rules: tuple[str, ...]
    prohibited_rules: tuple[str, ...]
    allowed_resource_kinds: tuple[str, ...] | None
    priority_resource_kinds: tuple[str, ...]
    prohibited_resource_kinds: tuple[str, ...]
    minimum_confidence: float
    reasoning_depth: DomainReasoningDepth
    allowed_inferences: tuple[str, ...] | None
    prohibited_inferences: tuple[str, ...]
    maximum_questions: int
    escalation_rules: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    question_policy: DomainQuestionPolicy
    presentation_policy: DomainPresentationPolicy
    memory_policy: DomainMemoryPolicy
    temporal_policy: DomainTemporalPolicy
    production_policy: DomainProductionPolicy
    permissions: tuple[str, ...] | None
    modifications: tuple[DomainProfileModification, ...]
    trace_id: str
    resolved_at: datetime
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
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
        object.__setattr__(
            self,
            "profile_names",
            _freeze_unique_str_tuple(self.profile_names, "profile_names"),
        )

        for attr_name in (
            "required_rules",
            "optional_rules",
            "prohibited_rules",
            "priority_resource_kinds",
            "prohibited_resource_kinds",
            "prohibited_inferences",
            "escalation_rules",
            "prohibited_actions",
        ):
            object.__setattr__(
                self,
                attr_name,
                _freeze_unique_str_tuple(getattr(self, attr_name), attr_name),
            )

        object.__setattr__(
            self,
            "allowed_resource_kinds",
            _freeze_optional_unique_str_tuple(
                self.allowed_resource_kinds, "allowed_resource_kinds"
            ),
        )
        object.__setattr__(
            self,
            "allowed_inferences",
            _freeze_optional_unique_str_tuple(
                self.allowed_inferences, "allowed_inferences"
            ),
        )
        object.__setattr__(
            self,
            "permissions",
            _freeze_optional_unique_str_tuple(self.permissions, "permissions"),
        )

        object.__setattr__(
            self,
            "minimum_confidence",
            _validate_confidence(self.minimum_confidence, "minimum_confidence"),
        )
        object.__setattr__(
            self,
            "reasoning_depth",
            _coerce_reasoning_depth(self.reasoning_depth, "reasoning_depth"),
        )
        object.__setattr__(
            self,
            "maximum_questions",
            _validate_positive_int(self.maximum_questions, "maximum_questions"),
        )

        object.__setattr__(
            self,
            "question_policy",
            _parse_question_policy(self.question_policy, "question_policy"),
        )
        object.__setattr__(
            self,
            "presentation_policy",
            _parse_presentation_policy(self.presentation_policy, "presentation_policy"),
        )
        object.__setattr__(
            self,
            "memory_policy",
            _parse_memory_policy(self.memory_policy, "memory_policy"),
        )
        object.__setattr__(
            self,
            "temporal_policy",
            _parse_temporal_policy(self.temporal_policy, "temporal_policy"),
        )
        object.__setattr__(
            self,
            "production_policy",
            _parse_production_policy(self.production_policy, "production_policy"),
        )

        object.__setattr__(
            self,
            "modifications",
            _freeze_modification_tuple(self.modifications, "modifications"),
        )
        object.__setattr__(
            self, "trace_id", _validate_non_empty_str(self.trace_id, "trace_id")
        )
        object.__setattr__(
            self, "resolved_at", _ensure_tz_aware(self.resolved_at, "resolved_at")
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

        # Cross-field invariants: the resolved profile must never contain a
        # silent contradiction.
        if set(self.required_rules) & set(self.optional_rules):
            raise DomainProfileContractError(
                "required_rules must not overlap optional_rules",
                field="optional_rules",
            )
        if set(self.prohibited_rules) & set(self.optional_rules):
            raise DomainProfileContractError(
                "prohibited_rules must not overlap optional_rules",
                field="optional_rules",
            )
        if set(self.required_rules) & set(self.prohibited_rules):
            raise DomainProfileContractError(
                "required_rules must not overlap prohibited_rules",
                field="prohibited_rules",
            )
        if self.allowed_inferences is not None:
            leaked = set(self.prohibited_inferences) & set(self.allowed_inferences)
            if leaked:
                raise DomainProfileContractError(
                    "prohibited_inferences must not remain in allowed_inferences: "
                    f"{sorted(leaked)}",
                    field="allowed_inferences",
                )
        if self.allowed_resource_kinds is not None:
            unknown_priority = set(self.priority_resource_kinds) - set(
                self.allowed_resource_kinds
            )
            if unknown_priority:
                raise DomainProfileContractError(
                    "priority_resource_kinds must remain within allowed_resource_kinds: "
                    f"{sorted(unknown_priority)}",
                    field="priority_resource_kinds",
                )
        priority_prohibited = set(self.priority_resource_kinds) & set(
            self.prohibited_resource_kinds
        )
        if priority_prohibited:
            raise DomainProfileContractError(
                "priority_resource_kinds must not remain in prohibited_resource_kinds: "
                f"{sorted(priority_prohibited)}",
                field="priority_resource_kinds",
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "primary_domain": str(self.primary_domain),
            "supporting_domains": [str(d) for d in self.supporting_domains],
            "profile_names": list(self.profile_names),
            "required_rules": list(self.required_rules),
            "optional_rules": list(self.optional_rules),
            "prohibited_rules": list(self.prohibited_rules),
            "allowed_resource_kinds": (
                list(self.allowed_resource_kinds)
                if self.allowed_resource_kinds is not None
                else None
            ),
            "priority_resource_kinds": list(self.priority_resource_kinds),
            "prohibited_resource_kinds": list(self.prohibited_resource_kinds),
            "minimum_confidence": self.minimum_confidence,
            "reasoning_depth": self.reasoning_depth.value,
            "allowed_inferences": (
                list(self.allowed_inferences)
                if self.allowed_inferences is not None
                else None
            ),
            "prohibited_inferences": list(self.prohibited_inferences),
            "maximum_questions": self.maximum_questions,
            "escalation_rules": list(self.escalation_rules),
            "prohibited_actions": list(self.prohibited_actions),
            **_policies_to_dict(
                self.question_policy,
                self.presentation_policy,
                self.memory_policy,
                self.temporal_policy,
                self.production_policy,
            ),
            "permissions": (
                list(self.permissions) if self.permissions is not None else None
            ),
            "modifications": [m.to_dict() for m in self.modifications],
            "trace_id": self.trace_id,
            "resolved_at": self.resolved_at.isoformat(),
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResolvedDomainProfile:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainProfileSerializationError(
                "ResolvedDomainProfile.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _RESOLVED_KNOWN, "ResolvedDomainProfile")
        required = {"id", "primary_domain", "trace_id", "resolved_at"}
        missing = required - set(data.keys())
        if missing:
            raise DomainProfileSerializationError(
                f"ResolvedDomainProfile.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        resolved_at_raw = data["resolved_at"]
        resolved_at = _parse_datetime_opt(resolved_at_raw, "resolved_at")
        if resolved_at is None:
            raise DomainProfileSerializationError(
                "resolved_at must not be null", field="resolved_at"
            )
        kwargs: dict[str, Any] = {
            k: v for k, v in data.items() if k not in ("metadata", "resolved_at")
        }
        kwargs["resolved_at"] = resolved_at
        kwargs["metadata"] = data.get("metadata")
        try:
            return cls(**kwargs)
        except DomainProfileContractError as exc:
            raise DomainProfileSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# DomainProfileCompositionResult
# ═══════════════════════════════════════════════════════════════════════════════

_COMPOSITION_RESULT_KNOWN = frozenset(
    {"profile", "conflicts", "rejections", "decisions", "modifications", "metadata"}
)


@dataclass(frozen=True, slots=True)
class DomainProfileCompositionResult:
    """The pure output of :class:`DomainProfileComposer`."""

    profile: DomainProfileDraft | None
    conflicts: tuple[DomainProfileConflict, ...] = ()
    rejections: tuple[DomainProfileRejection, ...] = ()
    decisions: tuple[DomainProfileDecision, ...] = ()
    modifications: tuple[DomainProfileModification, ...] = ()
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        if self.profile is not None and not isinstance(
            self.profile, DomainProfileDraft
        ):
            raise DomainProfileContractError(
                "profile must be a DomainProfileDraft or None", field="profile"
            )
        object.__setattr__(
            self, "conflicts", _freeze_conflict_tuple(self.conflicts, "conflicts")
        )
        object.__setattr__(
            self, "rejections", _freeze_rejection_tuple(self.rejections, "rejections")
        )
        object.__setattr__(
            self, "decisions", _freeze_decision_tuple(self.decisions, "decisions")
        )
        object.__setattr__(
            self,
            "modifications",
            _freeze_modification_tuple(self.modifications, "modifications"),
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "profile": self.profile.to_dict() if self.profile is not None else None,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "rejections": [r.to_dict() for r in self.rejections],
            "decisions": [d.to_dict() for d in self.decisions],
            "modifications": [m.to_dict() for m in self.modifications],
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainProfileCompositionResult:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainProfileSerializationError(
                "DomainProfileCompositionResult.from_dict requires a mapping",
                field="data",
            )
        _reject_unknown_fields(
            data, _COMPOSITION_RESULT_KNOWN, "DomainProfileCompositionResult"
        )
        profile_raw = data.get("profile")
        profile = (
            DomainProfileDraft.from_dict(dict(profile_raw))
            if isinstance(profile_raw, Mapping)
            else None
        )
        try:
            return cls(
                profile=profile,
                conflicts=tuple(data.get("conflicts", ())),
                rejections=tuple(data.get("rejections", ())),
                decisions=tuple(data.get("decisions", ())),
                modifications=tuple(data.get("modifications", ())),
                metadata=data.get("metadata"),
            )
        except DomainProfileContractError as exc:
            raise DomainProfileSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# DomainProfileResolution
# ═══════════════════════════════════════════════════════════════════════════════

_RESOLUTION_KNOWN = frozenset(
    {
        "id",
        "status",
        "profile",
        "conflicts",
        "rejections",
        "decisions",
        "trace_id",
        "resolved_at",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainProfileResolution:
    """The complete, auditable result of resolving a Domain Profile."""

    id: str
    status: DomainProfileResolutionStatus
    profile: ResolvedDomainProfile | None
    conflicts: tuple[DomainProfileConflict, ...] = ()
    rejections: tuple[DomainProfileRejection, ...] = ()
    decisions: tuple[DomainProfileDecision, ...] = ()
    trace_id: str = ""
    resolved_at: datetime | None = None
    metadata: MappingProxyType[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _validate_non_empty_str(self.id, "id"))
        object.__setattr__(
            self, "status", _coerce_resolution_status(self.status, "status")
        )
        if self.profile is not None and not isinstance(
            self.profile, ResolvedDomainProfile
        ):
            raise DomainProfileContractError(
                "profile must be a ResolvedDomainProfile or None", field="profile"
            )
        object.__setattr__(
            self, "conflicts", _freeze_conflict_tuple(self.conflicts, "conflicts")
        )
        object.__setattr__(
            self, "rejections", _freeze_rejection_tuple(self.rejections, "rejections")
        )
        object.__setattr__(
            self, "decisions", _freeze_decision_tuple(self.decisions, "decisions")
        )
        object.__setattr__(
            self, "trace_id", _validate_non_empty_str(self.trace_id, "trace_id")
        )
        object.__setattr__(
            self, "resolved_at", _ensure_tz_aware(self.resolved_at, "resolved_at")
        )
        object.__setattr__(
            self, "metadata", _validate_json_safe_metadata(self.metadata, "metadata")
        )

        has_blocking_conflict = any(c.blocking for c in self.conflicts)

        if self.status == DomainProfileResolutionStatus.RESOLVED:
            if self.profile is None:
                raise DomainProfileContractError(
                    "RESOLVED status requires a profile", field="profile"
                )
            if has_blocking_conflict:
                raise DomainProfileContractError(
                    "RESOLVED status requires no blocking conflict", field="status"
                )
        elif self.status == DomainProfileResolutionStatus.PARTIAL:
            if self.profile is None:
                raise DomainProfileContractError(
                    "PARTIAL status requires a profile", field="profile"
                )
            if has_blocking_conflict:
                raise DomainProfileContractError(
                    "PARTIAL status requires no blocking conflict", field="status"
                )
            if len(self.rejections) == 0:
                raise DomainProfileContractError(
                    "PARTIAL status requires at least one rejection", field="rejections"
                )
        elif self.status == DomainProfileResolutionStatus.BLOCKED:
            if self.profile is not None:
                raise DomainProfileContractError(
                    "BLOCKED status must not carry a resolved profile", field="profile"
                )
            if not has_blocking_conflict:
                raise DomainProfileContractError(
                    "BLOCKED status requires at least one blocking conflict",
                    field="conflicts",
                )
        elif self.status == DomainProfileResolutionStatus.FAILED:
            if self.profile is not None:
                raise DomainProfileContractError(
                    "FAILED status must not carry a resolved profile", field="profile"
                )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "status": self.status.value,
            "profile": self.profile.to_dict() if self.profile is not None else None,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "rejections": [r.to_dict() for r in self.rejections],
            "decisions": [d.to_dict() for d in self.decisions],
            "trace_id": self.trace_id,
            "resolved_at": self.resolved_at.isoformat()
            if self.resolved_at is not None
            else None,
            "metadata": _deep_unfreeze_value(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainProfileResolution:
        """Deserialize from dictionary."""
        if not isinstance(data, Mapping):
            raise DomainProfileSerializationError(
                "DomainProfileResolution.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _RESOLUTION_KNOWN, "DomainProfileResolution")
        required = {"id", "status", "trace_id", "resolved_at"}
        missing = required - set(data.keys())
        if missing:
            raise DomainProfileSerializationError(
                f"DomainProfileResolution.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        resolved_at = _parse_datetime_opt(data["resolved_at"], "resolved_at")
        if resolved_at is None:
            raise DomainProfileSerializationError(
                "resolved_at must not be null", field="resolved_at"
            )
        profile_raw = data.get("profile")
        profile = (
            ResolvedDomainProfile.from_dict(dict(profile_raw))
            if isinstance(profile_raw, Mapping)
            else None
        )
        try:
            return cls(
                id=data["id"],
                status=data["status"],
                profile=profile,
                conflicts=tuple(data.get("conflicts", ())),
                rejections=tuple(data.get("rejections", ())),
                decisions=tuple(data.get("decisions", ())),
                trace_id=data["trace_id"],
                resolved_at=resolved_at,
                metadata=data.get("metadata"),
            )
        except DomainProfileContractError as exc:
            raise DomainProfileSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


__all__ = [
    "DETAIL_LEVEL_ORDER",
    "RETENTION_SCOPE_ORDER",
    "DomainMemoryPolicy",
    "DomainPresentationPolicy",
    "DomainProductionPolicy",
    "DomainProfileCompositionResult",
    "DomainProfileConflict",
    "DomainProfileDecision",
    "DomainProfileDefinition",
    "DomainProfileDraft",
    "DomainProfileModification",
    "DomainProfileOverlay",
    "DomainProfileRejection",
    "DomainProfileResolution",
    "DomainProfileResolutionRequest",
    "DomainQuestionPolicy",
    "DomainTemporalPolicy",
    "ResolvedDomainProfile",
]
