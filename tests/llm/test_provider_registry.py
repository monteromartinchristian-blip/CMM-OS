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
