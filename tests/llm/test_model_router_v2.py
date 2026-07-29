from __future__ import annotations

from decimal import Decimal

import pytest

from kernel.llm.capabilities import ModelCapabilities
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_ranking import ModelRankingPolicy
from kernel.llm.model_router import ModelRouter
from kernel.llm.model_selection import ModelRequirements
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec


@pytest.fixture
def router() -> ModelRouter:
    providers = ProviderRegistry()
    providers.register(
        ProviderSpec(
            id="local",
            provider_type="local",
            api_style="custom",
            availability="available",
        )
    )
    providers.register(
        ProviderSpec(
            id="remote",
            provider_type="remote",
            api_style="chat_completions",
            base_url="https://example.test/v1",
            availability="available",
        )
    )
    providers.register(
        ProviderSpec(
            id="disabled",
            provider_type="remote",
            api_style="chat_completions",
            base_url="https://disabled.test/v1",
            enabled=False,
        )
    )

    catalog = ModelCatalog(providers)
    catalog.register(
        ModelSpec(
            id="local-basic",
            provider_id="local",
            context_window=16_384,
            capabilities=ModelCapabilities(reasoning=True),
        )
    )
    catalog.register(
        ModelSpec(
            id="remote-cheap",
            provider_id="remote",
            context_window=128_000,
            capabilities=ModelCapabilities(
                reasoning=True,
                tool_calling=True,
                structured_output=True,
            ),
            input_cost_per_million=Decimal("0.10"),
            output_cost_per_million=Decimal("0.25"),
        )
    )
    catalog.register(
        ModelSpec(
            id="remote-premium",
            provider_id="remote",
            context_window=256_000,
            capabilities=ModelCapabilities(
                reasoning=True,
                tool_calling=True,
                structured_output=True,
                vision=True,
            ),
            input_cost_per_million=Decimal("2.00"),
            output_cost_per_million=Decimal("6.00"),
        )
    )
    catalog.register(
        ModelSpec(
            id="disabled-model",
            provider_id="disabled",
            context_window=64_000,
        )
    )

    return ModelRouter(
        provider_registry=providers,
        model_catalog=catalog,
    )


def test_decision_preserves_ranked_candidates(router: ModelRouter) -> None:
    decision = router.decide(
        ModelRequirements(reasoning=True),
        ranking_policy=ModelRankingPolicy(strategy="lowest_cost"),
        configuration_version="2026-07",
        metadata={"domain": "project"},
    )

    assert decision.status == "selected"
    assert decision.selected_model_id == "remote-cheap"
    assert decision.selected_provider_id == "remote"
    assert [candidate.qualified_model_id for candidate in decision.candidates] == [
        "remote:remote-cheap",
        "remote:remote-premium",
        "local:local-basic",
    ]
    assert [candidate.rank for candidate in decision.candidates] == [1, 2, 3]
    assert decision.configuration_version == "2026-07"
    assert decision.metadata == {"domain": "project"}
    assert decision.reason_codes == ("candidate_selected",)


def test_decision_records_rejection_reasons(router: ModelRouter) -> None:
    decision = router.decide(
        ModelRequirements(
            minimum_context_window=100_000,
            tool_calling=True,
            privacy="LOCAL_ONLY",
        )
    )

    rejected = {
        item.qualified_model_id: set(item.reasons)
        for item in decision.rejected_models
    }

    assert decision.status == "no_match"
    assert decision.reason_codes == ("no_matching_model",)
    assert rejected["local:local-basic"] == {
        "insufficient_context",
        "missing_capability",
    }
    assert "privacy_restriction" in rejected["remote:remote-cheap"]
    assert "provider_disabled" in rejected["disabled:disabled-model"]


def test_fallback_candidates_exclude_selected_by_default(
    router: ModelRouter,
) -> None:
    decision = router.decide(
        ModelRequirements(reasoning=True)
    )

    fallbacks = router.fallback_candidates(decision)

    assert [candidate.rank for candidate in fallbacks] == [2, 3]


def test_fallback_candidates_support_limit(router: ModelRouter) -> None:
    decision = router.decide(
        ModelRequirements(reasoning=True)
    )

    fallbacks = router.fallback_candidates(decision, limit=1)

    assert len(fallbacks) == 1
    assert fallbacks[0].rank == 2


def test_fallback_candidates_reject_negative_limit(
    router: ModelRouter,
) -> None:
    decision = router.decide(
        ModelRequirements(reasoning=True)
    )

    with pytest.raises(ValueError, match="cannot be negative"):
        router.fallback_candidates(decision, limit=-1)


def test_no_match_has_no_selected_model(router: ModelRouter) -> None:
    decision = router.decide(
        ModelRequirements(audio_output=True)
    )

    assert decision.status == "no_match"
    assert decision.selected_model_id is None
    assert decision.selected_provider_id is None
    assert decision.candidates == ()
