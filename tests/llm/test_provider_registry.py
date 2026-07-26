from __future__ import annotations

import pytest

from kernel.llm.exceptions import ProviderError
from kernel.llm.provider_registry import (
    ProviderSpec,
    get_provider_spec,
    has_provider,
    list_provider_specs,
    register_provider,
)


def test_nvidia_is_registered() -> None:
    spec = get_provider_spec("nvidia")

    assert spec.name == "nvidia"
    assert spec.api_style == "chat_completions"
    assert spec.default_model == "z-ai/glm-5.2"
    assert spec.api_key_env == "NVIDIA_API_KEY"
    assert spec.resolve_base_url() == ("https://integrate.api.nvidia.com/v1")


def test_registry_is_case_insensitive() -> None:
    assert has_provider("NVIDIA")
    assert get_provider_spec("NVIDIA").name == "nvidia"


def test_registered_specs_are_sorted() -> None:
    names = [spec.name for spec in list_provider_specs()]

    assert names == sorted(names)


def test_duplicate_registration_is_rejected() -> None:
    with pytest.raises(
        ProviderError,
        match="already registered",
    ):
        register_provider(
            ProviderSpec(
                name="nvidia",
                api_style="chat_completions",
                default_model="other-model",
                api_key_env="OTHER_API_KEY",
            )
        )


def test_openrouter_is_registered() -> None:
    spec = get_provider_spec("openrouter")

    assert spec.name == "openrouter"
    assert spec.api_style == "chat_completions"
    assert spec.default_model == "openrouter/free"
    assert spec.api_key_env == "OPENROUTER_API_KEY"
    assert spec.resolve_base_url() == "https://openrouter.ai/api/v1"


def test_groq_is_registered() -> None:
    spec = get_provider_spec("groq")

    assert spec.name == "groq"
    assert spec.api_style == "chat_completions"
    assert spec.default_model == "llama-3.3-70b-versatile"
    assert spec.api_key_env == "GROQ_API_KEY"
    assert spec.resolve_base_url() == "https://api.groq.com/openai/v1"


def test_registered_providers_expose_capabilities() -> None:
    from kernel.llm.provider_registry import get_provider_spec

    nvidia = get_provider_spec("nvidia")
    openrouter = get_provider_spec("openrouter")
    groq = get_provider_spec("groq")

    assert nvidia.capabilities.streaming
    assert nvidia.capabilities.tool_calling
    assert nvidia.capabilities.max_context_tokens == 131_072

    assert openrouter.capabilities.streaming
    assert openrouter.capabilities.tool_calling
    assert openrouter.capabilities.vision

    assert groq.capabilities.streaming
    assert groq.capabilities.tool_calling
    assert not groq.capabilities.responses_api
    assert groq.capabilities.max_context_tokens == 131_072


def test_provider_name_normalization_preserves_capabilities() -> None:
    from kernel.llm.provider_capabilities import ProviderCapabilities
    from kernel.llm.provider_registry import (
        ProviderSpec,
        get_provider_spec,
        register_provider,
    )

    capabilities = ProviderCapabilities(
        reasoning=True,
        local=True,
        max_context_tokens=32_768,
    )

    register_provider(
        ProviderSpec(
            name="  TEST-CAPABILITIES  ",
            api_style="chat_completions",
            default_model="test-model",
            api_key_env="TEST_CAPABILITIES_API_KEY",
            capabilities=capabilities,
        ),
        replace=True,
    )

    registered = get_provider_spec("test-capabilities")

    assert registered.capabilities == capabilities


def test_together_is_registered_with_capabilities() -> None:
    spec = get_provider_spec("together")

    assert spec.name == "together"
    assert spec.api_style == "chat_completions"
    assert spec.default_model == "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    assert spec.api_key_env == "TOGETHER_API_KEY"
    assert spec.resolve_base_url() == "https://api.together.xyz/v1"

    assert spec.capabilities.streaming
    assert spec.capabilities.tool_calling
    assert spec.capabilities.vision
    assert spec.capabilities.reasoning
    assert spec.capabilities.embeddings
