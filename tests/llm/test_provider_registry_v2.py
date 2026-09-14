from __future__ import annotations

import dataclasses

import pytest

from kernel.llm.capabilities import ProviderCapabilities
from kernel.llm.exceptions import ProviderError
from kernel.llm.model_routes import ModelRoute, ModelRouteCatalog
from kernel.llm.provider_connections import (
    BillingClass,
    ConnectionStatus,
    ProviderConnection,
    ProviderConnectionRegistry,
)
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


def make_connection(
    connection_id: str,
    provider_id: str,
) -> ProviderConnection:
    return ProviderConnection(
        connection_id=connection_id,
        provider_id=provider_id,
        display_name="Test connection",
        billing_class=BillingClass.SUBSCRIPTION,
        credential_ref="keychain://cmm/providers/test/main",
        endpoint="https://example.test/v1",
        isolation_profile_ref=None,
        status=ConnectionStatus.CONNECTED,
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


def test_provider_spec_duplicate_rules_unchanged_with_new_inventory() -> None:
    registry = ProviderRegistry()
    connection_registry = ProviderConnectionRegistry(registry)
    route_catalog = ModelRouteCatalog(connection_registry)

    registry.register(make_remote_provider())
    connection_registry.register(make_connection("test:main", "test"))
    route_catalog.register(
        ModelRoute(
            route_id="test:model-x",
            connection_id="test:main",
            provider_model_id="model-x",
            canonical_model_id="model-x",
        )
    )

    with pytest.raises(ProviderError, match="already registered"):
        registry.register(make_remote_provider())

    assert registry.get("test").id == "test"


def test_registering_provider_connection_does_not_mutate_provider_registry() -> None:
    registry = ProviderRegistry()
    connection_registry = ProviderConnectionRegistry(registry)

    registered = registry.register(make_remote_provider("qwen-token-plan"))
    connection_registry.register(
        make_connection("qwen-token-plan:main", "qwen-token-plan")
    )

    assert registry.get("qwen-token-plan") == registered
    assert [spec.id for spec in registry.list()] == ["qwen-token-plan"]
    with pytest.raises(ProviderError, match="Unknown registered provider"):
        registry.get("qwen-token-plan:main")


def test_provider_spec_fields_untouched_by_connection_types() -> None:
    field_names = {f.name for f in dataclasses.fields(ProviderSpec)}

    assert "connection_id" not in field_names
    assert "credential_ref" not in field_names
    assert "status" not in field_names
    assert "billing_class" not in field_names
