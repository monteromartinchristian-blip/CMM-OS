"""Public LLM routing and provider infrastructure."""

from typing import TYPE_CHECKING

from kernel.llm.builtin_models import register_builtin_models
from kernel.llm.model_catalog import (
    ModelSpec,
    clear_model_catalog,
    get_model_spec,
    has_model,
    list_model_specs,
    register_model,
)
from kernel.llm.model_ranking import ModelRankingPolicy, RankingStrategy
from kernel.llm.model_selection import (
    ModelRequirements,
    find_matching_models,
    model_matches_requirements,
    select_model,
)
from kernel.llm.provider_capabilities import ProviderCapabilities
from kernel.llm.provider_registry import (
    ProviderSpec,
    get_provider_spec,
    has_provider,
    list_provider_specs,
    register_provider,
)

if TYPE_CHECKING:
    from kernel.llm.model_router import ModelRoute, ModelRouter


def __getattr__(name: str) -> object:
    """Load routing classes lazily to avoid development-provider cycles."""

    if name in {"ModelRoute", "ModelRouter"}:
        from kernel.llm.model_router import ModelRoute, ModelRouter

        return {
            "ModelRoute": ModelRoute,
            "ModelRouter": ModelRouter,
        }[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ModelRankingPolicy",
    "ModelRequirements",
    "ModelRoute",
    "ModelRouter",
    "ModelSpec",
    "ProviderCapabilities",
    "ProviderSpec",
    "RankingStrategy",
    "clear_model_catalog",
    "find_matching_models",
    "get_model_spec",
    "get_provider_spec",
    "has_model",
    "has_provider",
    "list_model_specs",
    "list_provider_specs",
    "model_matches_requirements",
    "register_builtin_models",
    "register_model",
    "register_provider",
    "select_model",
]
