"""Phase 9.29 – Provider-independent model requirement contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Any

from cmm.agent_runtime.model_requirements_errors import (
    InvalidModelRequirementsContractError,
)
from kernel.llm.model_selection import ModelRequirements


def model_requirements_to_dict(
    requirements: ModelRequirements,
) -> dict[str, Any]:
    """Serialize ModelRequirements without using float monetary values."""

    if not isinstance(requirements, ModelRequirements):
        raise InvalidModelRequirementsContractError(
            "requirements must be a ModelRequirements instance"
        )

    return {
        "minimum_context_window": requirements.minimum_context_window,
        "reasoning": requirements.reasoning,
        "tool_calling": requirements.tool_calling,
        "structured_output": requirements.structured_output,
        "json_mode": requirements.json_mode,
        "json_schema": requirements.json_schema,
        "vision": requirements.vision,
        "audio_input": requirements.audio_input,
        "audio_output": requirements.audio_output,
        "embeddings": requirements.embeddings,
        "privacy": requirements.privacy,
        "allowed_providers": list(requirements.allowed_providers),
        "excluded_providers": list(requirements.excluded_providers),
        "maximum_input_cost_per_million": (
            str(requirements.maximum_input_cost_per_million)
            if requirements.maximum_input_cost_per_million is not None
            else None
        ),
        "maximum_output_cost_per_million": (
            str(requirements.maximum_output_cost_per_million)
            if requirements.maximum_output_cost_per_million is not None
            else None
        ),
        "premium_allowed": requirements.premium_allowed,
    }


def _optional_decimal(value: Any, field_name: str) -> Decimal | None:
    if value is None:
        return None

    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise InvalidModelRequirementsContractError(
            f"{field_name} must be a valid decimal"
        ) from exc

    if not decimal_value.is_finite():
        raise InvalidModelRequirementsContractError(
            f"{field_name} must be finite"
        )

    return decimal_value


def model_requirements_from_dict(
    data: Mapping[str, Any],
) -> ModelRequirements:
    """Deserialize a validated ModelRequirements contract."""

    if not isinstance(data, Mapping):
        raise InvalidModelRequirementsContractError(
            "Model requirements payload must be a mapping"
        )

    try:
        return ModelRequirements(
            minimum_context_window=int(
                data.get("minimum_context_window", 1)
            ),
            reasoning=bool(data.get("reasoning", False)),
            tool_calling=bool(data.get("tool_calling", False)),
            structured_output=bool(
                data.get("structured_output", False)
            ),
            json_mode=bool(data.get("json_mode", False)),
            json_schema=bool(data.get("json_schema", False)),
            vision=bool(data.get("vision", False)),
            audio_input=bool(data.get("audio_input", False)),
            audio_output=bool(data.get("audio_output", False)),
            embeddings=bool(data.get("embeddings", False)),
            privacy=str(data.get("privacy", "REMOTE_ALLOWED")),
            allowed_providers=tuple(data.get("allowed_providers", ())),
            excluded_providers=tuple(
                data.get("excluded_providers", ())
            ),
            maximum_input_cost_per_million=_optional_decimal(
                data.get("maximum_input_cost_per_million"),
                "maximum_input_cost_per_million",
            ),
            maximum_output_cost_per_million=_optional_decimal(
                data.get("maximum_output_cost_per_million"),
                "maximum_output_cost_per_million",
            ),
            premium_allowed=bool(
                data.get("premium_allowed", False)
            ),
        )
    except (
        TypeError,
        ValueError,
        InvalidModelRequirementsContractError,
    ) as exc:
        if isinstance(exc, InvalidModelRequirementsContractError):
            raise
        raise InvalidModelRequirementsContractError(
            f"Invalid model requirements payload: {exc}"
        ) from exc


@dataclass(frozen=True, slots=True)
class ModelRequirementsSource:
    """One declared requirement layer contributing to resolution."""

    source_kind: str
    source_id: str
    requirements: ModelRequirements
    priority: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.source_kind, str) or not self.source_kind.strip():
            raise InvalidModelRequirementsContractError(
                "source_kind must be a non-empty string"
            )
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise InvalidModelRequirementsContractError(
                "source_id must be a non-empty string"
            )
        if not isinstance(self.requirements, ModelRequirements):
            raise InvalidModelRequirementsContractError(
                "requirements must be a ModelRequirements instance"
            )
        if not isinstance(self.priority, int) or isinstance(
            self.priority, bool
        ):
            raise InvalidModelRequirementsContractError(
                "priority must be an integer"
            )
        if not isinstance(self.metadata, Mapping):
            raise InvalidModelRequirementsContractError(
                "metadata must be a mapping"
            )

        object.__setattr__(self, "source_kind", self.source_kind.strip())
        object.__setattr__(self, "source_id", self.source_id.strip())
        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(dict(self.metadata)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "source_id": self.source_id,
            "requirements": model_requirements_to_dict(
                self.requirements
            ),
            "priority": self.priority,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> ModelRequirementsSource:
        return cls(
            source_kind=str(data.get("source_kind", "")),
            source_id=str(data.get("source_id", "")),
            requirements=model_requirements_from_dict(
                data.get("requirements", {})
            ),
            priority=int(data.get("priority", 0)),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class ResolvedModelRequirements:
    """Effective requirements plus complete resolution provenance."""

    effective: ModelRequirements
    sources: tuple[ModelRequirementsSource, ...]
    requires_premium_approval: bool = False
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.effective, ModelRequirements):
            raise InvalidModelRequirementsContractError(
                "effective must be a ModelRequirements instance"
            )
        if not isinstance(self.sources, tuple):
            raise InvalidModelRequirementsContractError(
                "sources must be a tuple"
            )
        if any(
            not isinstance(source, ModelRequirementsSource)
            for source in self.sources
        ):
            raise InvalidModelRequirementsContractError(
                "sources must contain ModelRequirementsSource values"
            )
        if not isinstance(self.requires_premium_approval, bool):
            raise InvalidModelRequirementsContractError(
                "requires_premium_approval must be a bool"
            )
        if not isinstance(self.metadata, Mapping):
            raise InvalidModelRequirementsContractError(
                "metadata must be a mapping"
            )

        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(dict(self.metadata)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "effective": model_requirements_to_dict(self.effective),
            "sources": [source.to_dict() for source in self.sources],
            "requires_premium_approval": self.requires_premium_approval,
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> ResolvedModelRequirements:
        return cls(
            effective=model_requirements_from_dict(
                data.get("effective", {})
            ),
            sources=tuple(
                ModelRequirementsSource.from_dict(source)
                for source in data.get("sources", ())
            ),
            requires_premium_approval=bool(
                data.get("requires_premium_approval", False)
            ),
            warnings=tuple(data.get("warnings", ())),
            metadata=data.get("metadata", {}),
        )


__all__ = [
    "ModelRequirementsSource",
    "ResolvedModelRequirements",
    "model_requirements_from_dict",
    "model_requirements_to_dict",
]
