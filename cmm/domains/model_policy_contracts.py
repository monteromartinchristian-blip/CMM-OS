"""Phase 10.46 – model-agnostic Domain Model Policy contract.

``DomainModelPolicy`` declares only objective, typed, serializable inference and
validation requirements intrinsic to a domain or domain operation. It contains
no concrete model or provider identifiers and performs no routing, ranking,
selection, provider construction, or provider invocation.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from cmm.domains.errors import (
    DomainContractValidationError,
    DomainSerializationError,
)
from cmm.domains.identifiers import DomainId

if TYPE_CHECKING:  # pragma: no cover - typing-only import
    from cmm.agent_runtime.model_fallback_contracts import ModelFallbackPolicy

__all__ = ["DomainModelPolicy"]

_CAPABILITY_BOOLEAN_FIELDS = (
    "require_reasoning",
    "require_tool_calling",
    "require_structured_output",
    "require_json_mode",
    "require_json_schema",
    "require_vision",
    "require_audio_input",
    "require_audio_output",
    "require_embeddings",
)

_VALIDATION_BOOLEAN_FIELDS = (
    "require_context_validation",
    "require_response_validation",
)

_BOOLEAN_FIELDS = _CAPABILITY_BOOLEAN_FIELDS + _VALIDATION_BOOLEAN_FIELDS

_POLICY_KNOWN = frozenset(
    {
        "domain_id",
        *_BOOLEAN_FIELDS,
        "minimum_context_window",
        "fallback_policy",
        "metadata",
    }
)


def _freeze_metadata(value: Any) -> Any:
    """Recursively freeze metadata using canonical domain immutability rules."""
    if isinstance(value, Mapping):
        for key in value:
            if not isinstance(key, str) or isinstance(key, bool):
                raise DomainContractValidationError(
                    "metadata keys must be strings", field="metadata"
                )
        return MappingProxyType(
            {key: _freeze_metadata(val) for key, val in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_metadata(val) for val in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze_metadata(val) for val in value)
    return value


def _thaw_metadata(value: Any) -> Any:
    """Reverse ``_freeze_metadata`` for deterministic serialization."""
    if isinstance(value, (MappingProxyType, Mapping)):
        return {key: _thaw_metadata(val) for key, val in value.items()}
    if isinstance(value, (tuple, list)):
        return [_thaw_metadata(val) for val in value]
    if isinstance(value, (frozenset, set)):
        return sorted((_thaw_metadata(val) for val in value), key=str)
    return value


def _require_strict_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise DomainContractValidationError(
            f"{field_name} must be a boolean (True or False), "
            f"got {type(value).__name__}: {value!r}",
            field=field_name,
        )
    return value


def _require_context_window(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise DomainContractValidationError(
            "minimum_context_window must be a positive integer or None",
            field="minimum_context_window",
        )
    return value


def _require_fallback_policy(value: Any) -> ModelFallbackPolicy | None:
    if value is None:
        return None
    from cmm.agent_runtime.model_fallback_contracts import ModelFallbackPolicy

    if not isinstance(value, ModelFallbackPolicy):
        raise DomainContractValidationError(
            "fallback_policy must be a ModelFallbackPolicy instance or None",
            field="fallback_policy",
        )
    return value


def _fallback_policy_from_dict(value: Any) -> ModelFallbackPolicy | None:
    if value is None:
        return None
    from cmm.agent_runtime.model_fallback_contracts import ModelFallbackPolicy

    if isinstance(value, ModelFallbackPolicy):
        return value
    if not isinstance(value, Mapping):
        raise DomainSerializationError(
            "fallback_policy must be a mapping or ModelFallbackPolicy",
            field="fallback_policy",
        )
    try:
        return ModelFallbackPolicy.from_dict(dict(value))
    except (TypeError, ValueError) as exc:
        raise DomainSerializationError(
            f"Invalid fallback_policy payload: {exc}", field="fallback_policy"
        ) from exc


def _reject_unknown_policy_fields(data: Mapping[str, Any]) -> None:
    unknown = set(data.keys()) - _POLICY_KNOWN
    if unknown:
        raise DomainSerializationError(
            f"DomainModelPolicy.from_dict got unknown fields: {sorted(unknown)}",
            field="data",
            details={"unknown_fields": sorted(unknown)},
        )


@dataclass(frozen=True, slots=True)
class DomainModelPolicy:
    """Immutable, model-agnostic declaration of domain inference requirements."""

    domain_id: DomainId

    require_reasoning: bool = False
    require_tool_calling: bool = False
    require_structured_output: bool = False
    require_json_mode: bool = False
    require_json_schema: bool = False
    require_vision: bool = False
    require_audio_input: bool = False
    require_audio_output: bool = False
    require_embeddings: bool = False

    minimum_context_window: int | None = None

    require_context_validation: bool = False
    require_response_validation: bool = False

    fallback_policy: ModelFallbackPolicy | None = None

    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.domain_id, str):
            object.__setattr__(self, "domain_id", DomainId.from_str(self.domain_id))
        elif not isinstance(self.domain_id, DomainId):
            raise DomainContractValidationError(
                "domain_id must be a DomainId instance or canonical 'domain:<slug>' string",
                field="domain_id",
            )

        for field_name in _BOOLEAN_FIELDS:
            _require_strict_bool(getattr(self, field_name), field_name)

        object.__setattr__(
            self,
            "minimum_context_window",
            _require_context_window(self.minimum_context_window),
        )
        object.__setattr__(
            self, "fallback_policy", _require_fallback_policy(self.fallback_policy)
        )
        if not isinstance(self.metadata, Mapping):
            raise DomainContractValidationError(
                "metadata must be a mapping", field="metadata"
            )
        object.__setattr__(self, "metadata", _freeze_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize deterministically to a JSON-compatible dictionary."""
        return {
            "domain_id": str(self.domain_id),
            "require_reasoning": self.require_reasoning,
            "require_tool_calling": self.require_tool_calling,
            "require_structured_output": self.require_structured_output,
            "require_json_mode": self.require_json_mode,
            "require_json_schema": self.require_json_schema,
            "require_vision": self.require_vision,
            "require_audio_input": self.require_audio_input,
            "require_audio_output": self.require_audio_output,
            "require_embeddings": self.require_embeddings,
            "minimum_context_window": self.minimum_context_window,
            "require_context_validation": self.require_context_validation,
            "require_response_validation": self.require_response_validation,
            "fallback_policy": (
                self.fallback_policy.to_dict()
                if self.fallback_policy is not None
                else None
            ),
            "metadata": _thaw_metadata(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DomainModelPolicy:
        """Deserialize strictly, rejecting unknown or forbidden fields."""
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainModelPolicy.from_dict requires a mapping", field="data"
            )
        _reject_unknown_policy_fields(data)
        if "domain_id" not in data:
            raise DomainSerializationError(
                "DomainModelPolicy.from_dict missing required field 'domain_id'",
                field="domain_id",
            )

        try:
            return cls(
                domain_id=data["domain_id"],
                **{
                    field_name: data.get(field_name, False)
                    for field_name in _BOOLEAN_FIELDS
                },
                minimum_context_window=data.get("minimum_context_window"),
                fallback_policy=_fallback_policy_from_dict(data.get("fallback_policy")),
                metadata=data.get("metadata", {}),
            )
        except DomainContractValidationError as exc:
            raise DomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc
