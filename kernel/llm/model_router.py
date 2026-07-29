"""Auditable deterministic routing over provider and model catalogs."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal
from uuid import uuid4

from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_ranking import ModelRankingPolicy
from kernel.llm.model_selection import (
    ModelRequirements,
    find_matching_models,
    model_matches_requirements,
)
from kernel.llm.provider_registry import ProviderRegistry

RejectionReason = Literal[
    "provider_disabled",
    "provider_unavailable",
    "model_unavailable",
    "insufficient_context",
    "provider_not_allowed",
    "provider_excluded",
    "privacy_restriction",
    "missing_capability",
    "input_cost_exceeded",
    "output_cost_exceeded",
]

RoutingStatus = Literal["selected", "no_match"]


@dataclass(frozen=True, slots=True)
class RejectedModel:
    """One model excluded from a routing decision."""

    qualified_model_id: str
    reasons: tuple[RejectionReason, ...]


@dataclass(frozen=True, slots=True)
class RoutingCandidate:
    """One suitable candidate preserved in deterministic order."""

    rank: int
    qualified_model_id: str
    provider_id: str
    model_id: str
    input_cost_per_million: Decimal | None
    output_cost_per_million: Decimal | None
    context_window: int | None


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """Complete auditable result of one routing evaluation."""

    id: str
    status: RoutingStatus
    selected_model_id: str | None
    selected_provider_id: str | None
    candidates: tuple[RoutingCandidate, ...]
    rejected_models: tuple[RejectedModel, ...]
    requirements: ModelRequirements
    ranking_policy: ModelRankingPolicy
    reason_codes: tuple[str, ...] = ()
    configuration_version: str = "1"
    metadata: dict[str, str] = field(default_factory=dict)


class ModelRouter:
    """Resolve requirements into an auditable routing decision."""

    def __init__(
        self,
        *,
        provider_registry: ProviderRegistry,
        model_catalog: ModelCatalog,
    ) -> None:
        self._provider_registry = provider_registry
        self._model_catalog = model_catalog

    def decide(
        self,
        requirements: ModelRequirements,
        *,
        ranking_policy: ModelRankingPolicy | None = None,
        configuration_version: str = "1",
        metadata: dict[str, str] | None = None,
    ) -> RoutingDecision:
        """Evaluate every model and return a deterministic decision."""

        policy = ranking_policy or ModelRankingPolicy()

        matching_models = find_matching_models(
            self._model_catalog,
            self._provider_registry,
            requirements,
            ranking_policy=policy,
        )

        candidates = tuple(
            RoutingCandidate(
                rank=index,
                qualified_model_id=model.qualified_id,
                provider_id=model.provider_id,
                model_id=model.id,
                input_cost_per_million=model.input_cost_per_million,
                output_cost_per_million=model.output_cost_per_million,
                context_window=model.context_window,
            )
            for index, model in enumerate(matching_models, start=1)
        )

        rejected = tuple(
            RejectedModel(
                qualified_model_id=model.qualified_id,
                reasons=self._rejection_reasons(model, requirements),
            )
            for model in self._model_catalog.list()
            if not model_matches_requirements(
                model,
                provider_registry=self._provider_registry,
                requirements=requirements,
            )
        )

        selected = matching_models[0] if matching_models else None

        return RoutingDecision(
            id=f"routing-{uuid4()}",
            status="selected" if selected is not None else "no_match",
            selected_model_id=selected.id if selected else None,
            selected_provider_id=selected.provider_id if selected else None,
            candidates=candidates,
            rejected_models=rejected,
            requirements=requirements,
            ranking_policy=policy,
            reason_codes=(
                ("candidate_selected",)
                if selected is not None
                else ("no_matching_model",)
            ),
            configuration_version=configuration_version,
            metadata=dict(metadata or {}),
        )

    def fallback_candidates(
        self,
        decision: RoutingDecision,
        *,
        exclude_selected: bool = True,
        limit: int | None = None,
    ) -> tuple[RoutingCandidate, ...]:
        """Return ordered fallback candidates from an existing decision."""

        candidates = decision.candidates
        if exclude_selected and candidates:
            candidates = candidates[1:]

        if limit is not None:
            if limit < 0:
                raise ValueError("limit cannot be negative")
            candidates = candidates[:limit]

        return candidates

    def _rejection_reasons(
        self,
        model: ModelSpec,
        requirements: ModelRequirements,
    ) -> tuple[RejectionReason, ...]:
        provider = self._provider_registry.get(model.provider_id)
        reasons: list[RejectionReason] = []

        if not provider.enabled:
            reasons.append("provider_disabled")

        if provider.availability in {"unavailable", "disabled"}:
            reasons.append("provider_unavailable")

        if model.availability in {"unavailable", "disabled"}:
            reasons.append("model_unavailable")

        if (
            model.context_window is None
            or model.context_window < requirements.minimum_context_window
        ):
            reasons.append("insufficient_context")

        if (
            requirements.allowed_providers
            and model.provider_id not in requirements.allowed_providers
        ):
            reasons.append("provider_not_allowed")

        if model.provider_id in requirements.excluded_providers:
            reasons.append("provider_excluded")

        if requirements.privacy in {"LOCAL_ONLY", "SENSITIVE"}:
            if provider.provider_type != "local":
                reasons.append("privacy_restriction")

        if not self._supports_capabilities(model, requirements):
            reasons.append("missing_capability")

        if not self._within_cost(
            model.input_cost_per_million,
            requirements.maximum_input_cost_per_million,
        ):
            reasons.append("input_cost_exceeded")

        if not self._within_cost(
            model.output_cost_per_million,
            requirements.maximum_output_cost_per_million,
        ):
            reasons.append("output_cost_exceeded")

        return tuple(dict.fromkeys(reasons))

    @staticmethod
    def _within_cost(
        actual: Decimal | None,
        maximum: Decimal | None,
    ) -> bool:
        if maximum is None:
            return True
        if actual is None:
            return False
        return actual <= maximum

    @staticmethod
    def _supports_capabilities(
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
        return all(
            not required or supported
            for required, supported in checks
        )
