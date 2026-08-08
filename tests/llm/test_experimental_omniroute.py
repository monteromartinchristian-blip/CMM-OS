from __future__ import annotations

from kernel.llm.experimental_omniroute import (
    OMNIROUTE_API_KEY_ENV,
    OMNIROUTE_BASE_URL_ENV,
    OMNIROUTE_DEEPSEEK_V4_FLASH,
    OMNIROUTE_DEFAULT_BASE_URL,
    OMNIROUTE_PROVIDER_ID,
    register_experimental_omniroute,
)
from kernel.llm.model_catalog import ModelCatalog
from kernel.llm.provider_registry import ProviderRegistry


def test_omniroute_registers_disabled_provider_by_default() -> None:
    providers = ProviderRegistry()
    catalog = ModelCatalog(providers)

    provider, models = register_experimental_omniroute(
        providers,
        catalog,
    )

    assert provider.id == OMNIROUTE_PROVIDER_ID
    assert provider.provider_type == "local"
    assert provider.api_style == "chat_completions"
    assert provider.enabled is False
    assert provider.base_url == OMNIROUTE_DEFAULT_BASE_URL
    assert provider.base_url_env == OMNIROUTE_BASE_URL_ENV
    assert provider.api_key_env == OMNIROUTE_API_KEY_ENV
    assert provider.capabilities.chat_completions is True
    assert [model.id for model in models] == [
        OMNIROUTE_DEEPSEEK_V4_FLASH
    ]


def test_omniroute_can_be_enabled_explicitly() -> None:
    providers = ProviderRegistry()
    catalog = ModelCatalog(providers)

    provider, _ = register_experimental_omniroute(
        providers,
        catalog,
        enabled=True,
    )

    assert provider.enabled is True


def test_omniroute_base_url_uses_environment_override(
    monkeypatch,
) -> None:
    providers = ProviderRegistry()
    catalog = ModelCatalog(providers)

    monkeypatch.setenv(
        "CMM_OMNIROUTE_BASE_URL",
        "http://127.0.0.1:29999/v1",
    )

    provider, _ = register_experimental_omniroute(
        providers,
        catalog,
    )

    assert (
        provider.resolve_base_url()
        == "http://127.0.0.1:29999/v1"
    )


def test_omniroute_api_key_is_optional(monkeypatch) -> None:
    providers = ProviderRegistry()
    catalog = ModelCatalog(providers)

    monkeypatch.delenv(
        "CMM_OMNIROUTE_API_KEY",
        raising=False,
    )

    provider, _ = register_experimental_omniroute(
        providers,
        catalog,
    )

    assert provider.resolve_api_key() is None

    monkeypatch.setenv(
        "CMM_OMNIROUTE_API_KEY",
        "example-secret",
    )

    assert provider.resolve_api_key() == "example-secret"


def test_omniroute_registers_multiple_models() -> None:
    providers = ProviderRegistry()
    catalog = ModelCatalog(providers)

    _, models = register_experimental_omniroute(
        providers,
        catalog,
        model_ids=(
            "cp/cline-pass/deepseek-v4-flash",
            "provider/another-model",
        ),
    )

    assert [model.id for model in models] == [
        "cp/cline-pass/deepseek-v4-flash",
        "provider/another-model",
    ]
    assert catalog.has(
        "cp/cline-pass/deepseek-v4-flash",
        provider_id="omniroute",
    )
    assert catalog.has(
        "provider/another-model",
        provider_id="omniroute",
    )


def test_omniroute_rejects_empty_model_ids_before_registration() -> None:
    from kernel.llm.exceptions import ProviderError

    providers = ProviderRegistry()
    catalog = ModelCatalog(providers)

    try:
        register_experimental_omniroute(
            providers,
            catalog,
            model_ids=(),
        )
    except ProviderError as error:
        assert "model_ids cannot be empty" in str(error)
    else:
        raise AssertionError("ProviderError was not raised")

    assert not providers.has("omniroute")
