import pytest

from kernel.llm.provider_connections import (
    BillingClass,
    ConnectionStatus,
    ProviderConnection,
    ProviderConnectionRegistry,
)


def test_connection_keeps_credential_reference_not_secret() -> None:
    connection = ProviderConnection(
        connection_id="qwen-token-plan:main",
        provider_id="qwen-token-plan",
        display_name="Qwen Token Plan",
        billing_class=BillingClass.SUBSCRIPTION,
        credential_ref="keychain://cmm/providers/qwen-token-plan/main",
        endpoint="https://example.invalid/v1",
        isolation_profile_ref=None,
        status=ConnectionStatus.CONNECTED,
    )

    assert connection.credential_ref.startswith("keychain://")
    assert not hasattr(connection, "api_key")
    assert not hasattr(connection, "secret")

def test_registry_rejects_duplicate_connection_id() -> None:
    registry = ProviderConnectionRegistry()
    connection = ProviderConnection(
        connection_id="deepseek:main",
        provider_id="deepseek",
        display_name="DeepSeek",
        billing_class=BillingClass.PAYG,
        credential_ref="keychain://cmm/providers/deepseek/main",
        endpoint="https://api.deepseek.com",
        isolation_profile_ref=None,
        status=ConnectionStatus.CONNECTED,
    )
    registry.register(connection)

    duplicate = ProviderConnection(
        connection_id="deepseek:main",
        provider_id="deepseek",
        display_name="DeepSeek Duplicate",
        billing_class=BillingClass.PAYG,
        credential_ref="keychain://cmm/providers/deepseek/main",
        endpoint="https://api.deepseek.com",
        isolation_profile_ref=None,
        status=ConnectionStatus.CONNECTED,
    )

    with pytest.raises(ValueError, match="duplicate connection_id"):
        registry.register(duplicate)

def test_connection_rejects_empty_provider_id() -> None:
    with pytest.raises(ValueError, match="Provider id cannot be empty"):
        ProviderConnection(
            connection_id="x:main",
            provider_id="   ",
            display_name="X",
            billing_class=BillingClass.API,
            credential_ref=None,
            endpoint="https://example.invalid/v1",
            isolation_profile_ref=None,
            status=ConnectionStatus.CONNECTED,
        )

def test_connection_rejects_empty_endpoint() -> None:
    with pytest.raises(ValueError, match="endpoint cannot be empty"):
        ProviderConnection(
            connection_id="x:main",
            provider_id="x",
            display_name="X",
            billing_class=BillingClass.API,
            credential_ref=None,
            endpoint="   ",
            isolation_profile_ref=None,
            status=ConnectionStatus.CONNECTED,
        )

def test_connection_rejects_plaintext_credential_shapes() -> None:
    with pytest.raises(ValueError, match="credential_ref must not contain plaintext secrets"):
        ProviderConnection(
            connection_id="x:main",
            provider_id="x",
            display_name="X",
            billing_class=BillingClass.API,
            credential_ref="sk-plaintext-secret",
            endpoint="https://example.invalid/v1",
            isolation_profile_ref=None,
            status=ConnectionStatus.CONNECTED,
        )

def test_connection_allows_null_credential_ref_for_subscription_bridges() -> None:
    connection = ProviderConnection(
        connection_id="claude-pro:main",
        provider_id="claude-pro",
        display_name="Claude Pro",
        billing_class=BillingClass.SUBSCRIPTION,
        credential_ref=None,
        endpoint="https://example.invalid/claude",
        isolation_profile_ref="cmm-isolated-claude-profile",
        status=ConnectionStatus.CONNECTED,
    )
    assert connection.credential_ref is None
    assert connection.isolation_profile_ref is not None
