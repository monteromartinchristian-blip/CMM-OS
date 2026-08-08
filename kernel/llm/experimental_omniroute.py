"""Experimental OmniRoute registration on existing LLM contracts."""

from __future__ import annotations

from kernel.llm.capabilities import ProviderCapabilities
from kernel.llm.exceptions import ProviderError
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

OMNIROUTE_PROVIDER_ID = "omniroute"
OMNIROUTE_DEFAULT_BASE_URL = "http://localhost:20128/v1"
OMNIROUTE_BASE_URL_ENV = "CMM_OMNIROUTE_BASE_URL"
OMNIROUTE_API_KEY_ENV = "CMM_OMNIROUTE_API_KEY"
OMNIROUTE_DEEPSEEK_V4_FLASH = "cp/cline-pass/deepseek-v4-flash"


def register_experimental_omniroute(
    provider_registry: ProviderRegistry,
    model_catalog: ModelCatalog,
    *,
    enabled: bool = False,
    model_ids: tuple[str, ...] = (
        OMNIROUTE_DEEPSEEK_V4_FLASH,
    ),
) -> tuple[ProviderSpec, tuple[ModelSpec, ...]]:
    """Register the experimental OmniRoute provider and explicit models."""

    if not model_ids:
        raise ProviderError("model_ids cannot be empty")

    provider = provider_registry.register(
        ProviderSpec(
            id=OMNIROUTE_PROVIDER_ID,
            provider_type="local",
            api_style="chat_completions",
            api_key_env=OMNIROUTE_API_KEY_ENV,
            base_url=OMNIROUTE_DEFAULT_BASE_URL,
            base_url_env=OMNIROUTE_BASE_URL_ENV,
            enabled=enabled,
            capabilities=ProviderCapabilities(
                chat_completions=True,
            ),
        )
    )

    models = tuple(
        model_catalog.register(
            ModelSpec(
                id=model_id,
                provider_id=OMNIROUTE_PROVIDER_ID,
            )
        )
        for model_id in model_ids
    )

    return provider, models
