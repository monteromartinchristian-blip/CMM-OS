from kernel.llm import (
    ModelRankingPolicy,
    ModelRequirements,
    ModelRouter,
    ModelSpec,
    ProviderCapabilities,
    ProviderSpec,
    RankingStrategy,
    clear_model_catalog,
    find_matching_models,
    get_model_spec,
    get_provider_spec,
    has_model,
    has_provider,
    list_model_specs,
    list_provider_specs,
    model_matches_requirements,
    register_builtin_models,
    register_model,
    register_provider,
    select_model,
)


def test_public_llm_api_exports_core_components() -> None:
    assert ModelRouter is not None
    assert ModelRequirements is not None
    assert ModelRankingPolicy is not None
    assert ModelSpec is not None
    assert ProviderSpec is not None
    assert ProviderCapabilities is not None
    assert RankingStrategy is not None

    assert callable(register_builtin_models)
    assert callable(register_model)
    assert callable(register_provider)
    assert callable(select_model)
    assert callable(find_matching_models)
    assert callable(model_matches_requirements)
    assert callable(get_model_spec)
    assert callable(get_provider_spec)
    assert callable(has_model)
    assert callable(has_provider)
    assert callable(list_model_specs)
    assert callable(list_provider_specs)
    assert callable(clear_model_catalog)
