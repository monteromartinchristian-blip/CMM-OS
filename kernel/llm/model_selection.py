"""Filtering primitives for selecting suitable LLM models."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from kernel.llm.model_catalog import ModelSpec, list_model_specs


@dataclass(frozen=True, slots=True)
class ModelRequirements:
    """Capabilities and constraints required by an LLM request."""

    minimum_context_window: int = 1

    streaming: bool = False
    tool_calling: bool = False
    vision: bool = False
    reasoning: bool = False
    json_mode: bool = False
    json_schema: bool = False
    embeddings: bool = False
    audio_input: bool = False
    audio_output: bool = False

    local_only: bool = False
    allowed_providers: tuple[str, ...] = ()
    excluded_providers: tuple[str, ...] = ()

    maximum_input_cost_per_million: Decimal | None = None
    maximum_output_cost_per_million: Decimal | None = None

    def __post_init__(self) -> None:
        if self.minimum_context_window <= 0:
            raise ValueError("minimum_context_window must be greater than zero")

        for cost in (
            self.maximum_input_cost_per_million,
            self.maximum_output_cost_per_million,
        ):
            if cost is not None and cost < 0:
                raise ValueError("Maximum model cost cannot be negative")


def model_matches_requirements(
    model: ModelSpec,
    requirements: ModelRequirements,
) -> bool:
    """Return whether a model satisfies every supplied requirement."""

    provider = model.provider.lower()

    allowed = {
        item.strip().lower() for item in requirements.allowed_providers if item.strip()
    }
    excluded = {
        item.strip().lower() for item in requirements.excluded_providers if item.strip()
    }

    if allowed and provider not in allowed:
        return False

    if provider in excluded:
        return False

    if model.context_window < requirements.minimum_context_window:
        return False

    capabilities = model.capabilities

    required_capabilities = (
        ("streaming", requirements.streaming),
        ("tool_calling", requirements.tool_calling),
        ("vision", requirements.vision),
        ("reasoning", requirements.reasoning),
        ("json_mode", requirements.json_mode),
        ("json_schema", requirements.json_schema),
        ("embeddings", requirements.embeddings),
        ("audio_input", requirements.audio_input),
        ("audio_output", requirements.audio_output),
    )

    for capability_name, required in required_capabilities:
        if required and not getattr(capabilities, capability_name):
            return False

    if requirements.local_only and not capabilities.local:
        return False

    if not _cost_is_within_limit(
        model.input_cost_per_million,
        requirements.maximum_input_cost_per_million,
    ):
        return False

    return _cost_is_within_limit(
        model.output_cost_per_million,
        requirements.maximum_output_cost_per_million,
    )


def find_matching_models(
    requirements: ModelRequirements,
) -> tuple[ModelSpec, ...]:
    """Return all catalog models satisfying the request constraints."""

    matches = (
        model
        for model in list_model_specs()
        if model_matches_requirements(model, requirements)
    )

    return tuple(sorted(matches, key=_model_sort_key))


def _cost_is_within_limit(
    model_cost: Decimal | None,
    maximum_cost: Decimal | None,
) -> bool:
    if maximum_cost is None:
        return True

    if model_cost is None:
        return False

    return model_cost <= maximum_cost


def _model_sort_key(
    model: ModelSpec,
) -> tuple[bool, Decimal, str]:
    input_cost = model.input_cost_per_million
    output_cost = model.output_cost_per_million

    has_unknown_cost = input_cost is None or output_cost is None
    total_cost = (input_cost or Decimal(0)) + (output_cost or Decimal(0))

    return (
        has_unknown_cost,
        total_cost,
        model.qualified_id.lower(),
    )


def select_model(
    requirements: ModelRequirements,
) -> ModelSpec:
    """Return the highest-ranked model satisfying all requirements."""

    matches = find_matching_models(requirements)

    if not matches:
        from kernel.llm.exceptions import ModelSelectionError

        raise ModelSelectionError(
            "No registered model satisfies the supplied requirements"
        )

    return matches[0]
