"""Contract tests for provider-connection identity and the registry."""

from datetime import datetime, timezone

import pytest

from kernel.llm.exceptions import ProviderError
from kernel.llm.provider_connections import (
    BillingClass,
    ConnectionStatus,
    ProviderConnection,
    ProviderConnectionRegistry,
)
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec


def _registry(*provider_ids: str) -> ProviderConnectionRegistry:
    """Build a connection registry whose providers exist canonically."""
    providers = ProviderRegistry()
    for provider_id in provider_ids:
        providers.register(
            ProviderSpec(
                id=provider_id,
                provider_type="remote",
                api_style="chat_completions",
                base_url="https://example.invalid/v1",
            )
        )
    return ProviderConnectionRegistry(providers)


def _connection(
    connection_id: str = "x:main",
    provider_id: str = "x",
    display_name: str = "X",
    credential_ref: str | None = None,
    **overrides: object,
) -> ProviderConnection:
    kwargs: dict[str, object] = {
        "connection_id": connection_id,
        "provider_id": provider_id,
        "display_name": display_name,
        "billing_class": BillingClass.API,
        "credential_ref": credential_ref,
        "endpoint": "https://example.invalid/v1",
        "isolation_profile_ref": None,
        "status": ConnectionStatus.CONNECTED,
    }
    kwargs.update(overrides)
    return ProviderConnection(**kwargs)  # type: ignore[arg-type]


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

    assert connection.credential_ref is not None
    assert connection.credential_ref.startswith("keychain://")
    assert not hasattr(connection, "api_key")
    assert not hasattr(connection, "secret")


def test_connection_registry_rejects_unknown_provider() -> None:
    """An accepted connection can never reference an unregistered provider."""
    providers = ProviderRegistry()
    connections = ProviderConnectionRegistry(providers)
    connection = _connection(
        connection_id="deepseek:main",
        provider_id="deepseek",
        display_name="DeepSeek API",
        billing_class=BillingClass.PAYG,
    )

    with pytest.raises(ProviderError, match="Unknown registered provider"):
        connections.register(connection)

    assert connections.list() == ()


@pytest.mark.parametrize("value", [None, object(), "providers"])
def test_connection_registry_rejects_a_non_canonical_registry(
    value: object,
) -> None:
    """Only a real ``ProviderRegistry`` may back the connection catalog."""
    with pytest.raises(TypeError, match="ProviderRegistry"):
        ProviderConnectionRegistry(value)  # type: ignore[arg-type]


def test_connection_registry_exposes_its_canonical_registry() -> None:
    """The bound authority is inspectable so no parallel inventory can appear."""
    providers = ProviderRegistry()

    connections = ProviderConnectionRegistry(providers)

    assert connections.provider_registry is providers


def test_registry_rejects_duplicate_connection_id() -> None:
    registry = _registry("deepseek")
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
        _connection(provider_id="   ")


def test_connection_rejects_empty_endpoint() -> None:
    with pytest.raises(ValueError, match="endpoint cannot be empty"):
        _connection(endpoint="   ")


def test_connection_rejects_plaintext_credential_shapes() -> None:
    with pytest.raises(
        ValueError, match="credential_ref must not contain plaintext secrets"
    ):
        _connection(credential_ref="sk-pla...cret")


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


def test_registry_round_trips_whitespace_padded_connection_id() -> None:
    registry = _registry("x")
    registered = registry.register(_connection(connection_id="  Acme:Main  "))

    assert registered.connection_id == "acme:main"
    assert registry.get(registered.connection_id) is registered
    assert registry.get("  ACME:MAIN ") is registered


def test_registry_get_returns_none_for_unknown_or_blank_id() -> None:
    registry = _registry()
    assert registry.get("missing:id") is None
    assert registry.get("   ") is None
    assert registry.get("") is None


def test_construction_rejects_blank_connection_id() -> None:
    with pytest.raises(ValueError, match="Connection id cannot be empty"):
        _connection(connection_id="   ")


def test_list_is_sorted_and_filters_by_normalized_provider_id() -> None:
    registry = _registry("beta", "alpha")
    for connection_id, provider_id in [
        ("beta:main", "beta"),
        ("alpha:main", "Alpha"),
        ("alpha:second", "alpha"),
    ]:
        registry.register(
            _connection(
                connection_id=connection_id,
                provider_id=provider_id,
                display_name=connection_id,
            )
        )

    assert [c.connection_id for c in registry.list()] == [
        "alpha:main",
        "alpha:second",
        "beta:main",
    ]
    assert [c.connection_id for c in registry.list("  ALPHA ")] == [
        "alpha:main",
        "alpha:second",
    ]
    assert registry.list("unknown-provider") == ()


def test_update_status_applies_status_and_validated_at() -> None:
    registry = _registry("deepseek")
    registry.register(
        _connection(
            connection_id="  DeepSeek:Main ",
            provider_id="deepseek",
            display_name="DeepSeek",
            billing_class=BillingClass.PAYG,
            credential_ref="keychain://cmm/providers/deepseek/main",
            endpoint="https://api.deepseek.com",
        )
    )
    validated_at = datetime(2026, 9, 13, tzinfo=timezone.utc)

    updated = registry.update_status(
        " DEEPSEEK:MAIN ", ConnectionStatus.WARNING, validated_at=validated_at
    )

    assert updated.status is ConnectionStatus.WARNING
    assert updated.last_validated_at == validated_at
    assert registry.get("deepseek:main") is updated


def test_update_status_keeps_previous_validated_at_when_omitted() -> None:
    registry = _registry("kira")
    first_validated = datetime(2026, 1, 2, tzinfo=timezone.utc)
    registry.register(
        _connection(
            connection_id="kira:main",
            provider_id="kira",
            display_name="Kira AI",
            billing_class=BillingClass.FREE_OR_API,
            credential_ref="keychain://cmm/providers/kira/main",
            endpoint="https://kiraai.vn/api/v1",
            last_validated_at=first_validated,
        )
    )

    updated = registry.update_status("Kira:Main", ConnectionStatus.AUTH_REQUIRED)

    assert updated.status is ConnectionStatus.AUTH_REQUIRED
    assert updated.last_validated_at == first_validated


def test_update_status_unknown_id_raises_value_error() -> None:
    registry = _registry()
    with pytest.raises(ValueError, match="unknown connection_id"):
        registry.update_status("nope:missing", ConnectionStatus.WARNING)
    with pytest.raises(ValueError, match="unknown connection_id"):
        registry.update_status("   ", ConnectionStatus.WARNING)


def test_update_status_rejects_non_enum_status() -> None:
    registry = _registry("x")
    registry.register(_connection())
    with pytest.raises(ValueError):
        registry.update_status(
            "x:main",
            "bogus-string-status",  # type: ignore[arg-type]
        )


def test_construction_rejects_empty_display_name() -> None:
    with pytest.raises(ValueError, match="display_name cannot be empty"):
        _connection(display_name="   ")


def test_construction_coerces_string_enum_values() -> None:
    connection = _connection(
        billing_class="payg",  # type: ignore[arg-type]
        status="detected",  # type: ignore[arg-type]
    )
    assert connection.billing_class is BillingClass.PAYG
    assert connection.status is ConnectionStatus.DETECTED


def test_rejects_secret_marker_embedded_in_keychain_ref() -> None:
    with pytest.raises(ValueError, match="plaintext secrets"):
        _connection(
            credential_ref=("keychain://cmm/providers/x/main?token=«redacted:sk-…»")
        )


def test_rejects_unapproved_credential_scheme_with_honest_message() -> None:
    with pytest.raises(ValueError, match="secure ref scheme: keychain://"):
        _connection(credential_ref="vault://cmm/providers/x/main")
