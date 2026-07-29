"""Requirement filtering and deterministic model selection."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_ranking import ModelRankingPolicy
from kernel.llm.provider_registry import ProviderRegistry

PrivacyPolicy = Literal[
    "LOCAL_ONLY",
    "LOCAL_PREFERRED",
    "REMOTE_ALLOWED",
    "PREMIUM_ALLOWED",
    "SENSITIVE",
]


@dataclass(frozen=True, slots=True)
class ModelRequirements:
    """Capabilities and constraints required by a model-assisted operation."""

    minimum_context_window: int = 1

    reasoning: bool = False
    tool_calling: bool = False
    structured_output: bool = False
    json_mode: bool = False
    json_schema: bool = False
    vision: bool = False
    audio_input: bool = False
    audio_output: bool = False
    embeddings: bool = False

    privacy: PrivacyPolicy = "REMOTE_ALLOWED"
    allowed_providers: tuple[str, ...] = ()
    excluded_providers: tuple[str, ...] = ()

    maximum_input_cost_per_million: Decimal | None = None
    maximum_output_cost_per_million: Decimal | None = None
    premium_allowed: bool = False

    def __post_init__(self) -> None:
        if self.minimum_context_window <= 0:
            raise ValueError(
                "minimum_context_window must be greater than zero"
            )

        for value, label in (
            (
                self.maximum_input_cost_per_million,
                "maximum_input_cost_per_million",
            ),
            (
                self.maximum_output_cost_per_million,
                "maximum_output_cost_per_million",
            ),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{label} cannot be negative")

        allowed = _normalize_provider_ids(self.allowed_providers)
        excluded = _normalize_provider_ids(self.excluded_providers)

        overlap = set(allowed) & set(excluded)
        if overlap:
            names = ", ".join(sorted(overlap))
            raise ValueError(
                f"Providers cannot be both allowed and excluded: {names}"
            )

        object.__setattr__(self, "allowed_providers", allowed)
        object.__setattr__(self, "excluded_providers", excluded)


def _normalize_provider_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            value.strip().lower()
            for value in values
            if value.strip()
        )
    )


def _supports_required_capabilities(
    model: ModelSpec,
    requirements: ModelRequirements,
) -> bool:
    capabilities = model.capabilities

    checks = (
        (requirements.reasoning, capabilities.reasoning),
        (requirements.tool_calling, capabilities.tool_calling),
        (
            requirements.structured_output,
            capabilities.structured_output,
        ),
        (requirements.json_mode, capabilities.json_mode),
        (requirements.json_schema, capabilities.json_schema),
        (requirements.vision, capabilities.vision),
        (requirements.audio_input, capabilities.audio_input),
        (requirements.audio_output, capabilities.audio_output),
        (requirements.embeddings, capabilities.embeddings),
    )

    return all(not required or supported for required, supported in checks)


def _within_cost_limit(
    actual: Decimal | None,
    maximum: Decimal | None,
) -> bool:
    if maximum is None:
        return True
    if actual is None:
        return False
    return actual <= maximum


def model_matches_requirements(
    model: ModelSpec,
    *,
    provider_registry: ProviderRegistry,
    requirements: ModelRequirements,
) -> bool:
    """Return whether one model satisfies all hard constraints."""

    provider = provider_registry.get(model.provider_id)

    if not provider.enabled:
        return False

    if provider.availability in {"unavailable", "disabled"}:
        return False

    if model.availability in {"unavailable", "disabled"}:
        return False

    if (
        model.context_window is None
        or model.context_window < requirements.minimum_context_window
    ):
        return False

    if (
        requirements.allowed_providers
        and model.provider_id not in requirements.allowed_providers
    ):
        return False

    if model.provider_id in requirements.excluded_providers:
        return False

    if requirements.privacy == "LOCAL_ONLY":
        if provider.provider_type != "local":
            return False

    if requirements.privacy == "SENSITIVE":
        if provider.provider_type == "remote":
            return False

    if not _supports_required_capabilities(model, requirements):
        return False

    if not _within_cost_limit(
        model.input_cost_per_million,
        requirements.maximum_input_cost_per_million,
    ):
        return False

    if not _within_cost_limit(
        model.output_cost_per_million,
        requirements.maximum_output_cost_per_million,
    ):
        return False

    return True


def find_matching_models(
    catalog: ModelCatalog,
    provider_registry: ProviderRegistry,
    requirements: ModelRequirements,
    *,
    ranking_policy: ModelRankingPolicy | None = None,
) -> tuple[ModelSpec, ...]:
    """Filter and deterministically rank all suitable models."""

    matches = tuple(
        model
        for model in catalog.list()
        if model_matches_requirements(
            model,
            provider_registry=provider_registry,
            requirements=requirements,
        )
    )

    policy = ranking_policy or ModelRankingPolicy()
    return policy.rank(matches)


def select_model(
    catalog: ModelCatalog,
    provider_registry: ProviderRegistry,
    requirements: ModelRequirements,
    *,
    ranking_policy: ModelRankingPolicy | None = None,
) -> ModelSpec | None:
    """Return the first deterministic candidate, or None when no match exists."""

    matches = find_matching_models(
        catalog,
        provider_registry,
        requirements,
        ranking_policy=ranking_policy,
    )
    return matches[0] if matches else None
