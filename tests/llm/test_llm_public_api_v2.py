from __future__ import annotations

import kernel.llm as llm


def test_multimodel_contracts_are_public() -> None:
    expected = {
        "ModelCapabilities",
        "ModelCatalog",
        "ModelRankingPolicy",
        "ModelRequirements",
        "ModelRouter",
        "ModelSpec",
        "OpenAICompatibleProvider",
        "PrivacyPolicy",
        "ProviderCapabilities",
        "ProviderFactory",
        "ProviderRegistry",
        "ProviderSpec",
        "RankingStrategy",
        "RejectedModel",
        "RoutingCandidate",
        "RoutingDecision",
        "find_matching_models",
        "model_matches_requirements",
        "select_model",
    }

    assert expected <= set(llm.__all__)

    for name in expected:
        assert getattr(llm, name) is not None
