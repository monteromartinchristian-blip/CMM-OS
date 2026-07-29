from __future__ import annotations

import pytest

from kernel.llm.capabilities import ProviderCapabilities
from kernel.llm.exceptions import ProviderError
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec


def make_remote_provider(provider_id: str = "test") -> ProviderSpec:
    return ProviderSpec(
        id=provider_id,
        provider_type="remote",
        api_style="chat_completions",
        api_key_env="TEST_API_KEY",
        base_url="https://example.test/v1",
        capabilities=ProviderCapabilities(
            chat_completions=True,
            streaming=True,
        ),
    )


def test_registry_is_instance_scoped_and_empty_by_default() -> None:
    first = ProviderRegistry()
    second = ProviderRegistry()

    first.register(make_remote_provider())

    assert first.has("test")
    assert not second.has("test")


def test_registry_normalizes_provider_identifiers() -> None:
    registry = ProviderRegistry()

    registered = registry.register(make_remote_provider("  TEST  "))

    assert registered.id == "test"
    assert registry.get("TEST") == registered


def test_registry_rejects_duplicate_provider() -> None:
    registry = ProviderRegistry()
    registry.register(make_remote_provider())

    with pytest.raises(ProviderError, match="already registered"):
        registry.register(make_remote_provider())


def test_registry_can_replace_provider_explicitly() -> None:
    registry = ProviderRegistry()
    registry.register(make_remote_provider())

    replacement = ProviderSpec(
        id="test",
        provider_type="remote",
        api_style="responses",
        base_url="https://replacement.test/v1",
    )

    registry.register(replacement, replace_existing=True)

    assert registry.get("test").api_style == "responses"


def test_capabilities_are_conservative_by_default() -> None:
    capabilities = ProviderCapabilities()

    assert not capabilities.chat_completions
    assert not capabilities.responses_api
    assert not capabilities.streaming
    assert not capabilities.embeddings


def test_remote_provider_requires_base_url() -> None:
    with pytest.raises(ProviderError, match="base_url"):
        ProviderSpec(
            id="invalid",
            provider_type="remote",
            api_style="chat_completions",
        )


def test_registry_lists_and_removes_providers() -> None:
    registry = ProviderRegistry()
    registry.register(make_remote_provider("zeta"))
    registry.register(make_remote_provider("alpha"))

    assert [spec.id for spec in registry.list()] == ["alpha", "zeta"]
    assert registry.remove("alpha").id == "alpha"
    assert not registry.has("alpha")
