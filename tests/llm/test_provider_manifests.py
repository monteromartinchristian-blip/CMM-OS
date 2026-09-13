"""Contract tests for declarative provider manifests and the registry.

The HTTPS rule under test is deliberately narrow: ``default_base_url`` must use
``https`` unless the host is a local development target (``localhost``,
``127.0.0.1`` or ``::1``), which may use plain ``http``. Nothing else — no
arbitrary host, no non-HTTP scheme — is allowed through.
"""

import dataclasses

import pytest

from kernel.llm.provider_connections import BillingClass
from kernel.llm.provider_manifests import (
    FIRST_WAVE_AUTH_SCHEME,
    ProviderManifest,
    ProviderManifestRegistry,
)

# Field names that would mean a manifest persists credential material.
_FORBIDDEN_FIELD_NAMES = ("api_key", "token", "secret")


def _manifest(
    provider_id: str = "deepseek",
    display_name: str = "DeepSeek",
    default_base_url: str = "https://api.deepseek.com/v1",
    auth_scheme: str = FIRST_WAVE_AUTH_SCHEME,
    **overrides: object,
) -> ProviderManifest:
    kwargs: dict[str, object] = {
        "provider_id": provider_id,
        "display_name": display_name,
        "billing_class": BillingClass.PAYG,
        "default_base_url": default_base_url,
        "auth_scheme": auth_scheme,
    }
    kwargs.update(overrides)
    return ProviderManifest(**kwargs)  # type: ignore[arg-type]


def test_manifest_carries_all_declared_fields() -> None:
    manifest = ProviderManifest(
        provider_id="nvidia-nim",
        display_name="NVIDIA NIM",
        billing_class=BillingClass.FREE_OR_API,
        default_base_url="https://integrate.api.nvidia.com/v1",
        auth_scheme="bearer",
        models_path="/models",
        api_styles=("chat_completions",),
        activation_allowlist=(),
    )

    assert manifest.provider_id == "nvidia-nim"
    assert manifest.display_name == "NVIDIA NIM"
    assert manifest.billing_class is BillingClass.FREE_OR_API
    assert manifest.default_base_url == "https://integrate.api.nvidia.com/v1"
    assert manifest.auth_scheme == "bearer"
    assert manifest.models_path == "/models"
    assert manifest.api_styles == ("chat_completions",)
    assert manifest.activation_allowlist == ()


def test_manifest_defaults_match_plan_contract() -> None:
    manifest = _manifest()

    assert manifest.models_path == "/models"
    assert manifest.api_styles == ("chat_completions",)
    assert manifest.activation_allowlist == ()


def test_manifest_is_frozen_and_slots_backed() -> None:
    manifest = _manifest()

    assert dataclasses.is_dataclass(manifest)
    assert not hasattr(manifest, "__dict__")
    with pytest.raises(dataclasses.FrozenInstanceError):
        manifest.provider_id = "other"  # type: ignore[misc]


def test_manifest_normalizes_provider_id_and_display_name() -> None:
    manifest = _manifest(provider_id="  DeepSeek  ", display_name="  DeepSeek  ")

    assert manifest.provider_id == "deepseek"
    assert manifest.display_name == "DeepSeek"


def test_manifest_normalizes_tuple_fields() -> None:
    manifest = _manifest(
        api_styles="chat_completions",  # type: ignore[arg-type]
        activation_allowlist=["kimi-k3"],  # type: ignore[arg-type]
    )

    assert manifest.api_styles == ("chat_completions",)
    assert manifest.activation_allowlist == ("kimi-k3",)


def test_manifest_coerces_string_billing_class() -> None:
    manifest = _manifest(billing_class="payg")  # type: ignore[arg-type]

    assert manifest.billing_class is BillingClass.PAYG


def test_manifest_rejects_blank_provider_id() -> None:
    with pytest.raises(ValueError, match="Provider id cannot be empty"):
        _manifest(provider_id="   ")


def test_manifest_rejects_blank_display_name() -> None:
    with pytest.raises(ValueError, match="display_name cannot be empty"):
        _manifest(display_name="   ")


def test_manifest_billing_class_is_required() -> None:
    with pytest.raises(TypeError):
        ProviderManifest(  # type: ignore[call-arg]
            provider_id="x",
            display_name="X",
            default_base_url="https://example.invalid/v1",
            auth_scheme="bearer",
        )


def test_manifest_rejects_non_https_base_url_for_public_hosts() -> None:
    with pytest.raises(ValueError, match="default_base_url must use https"):
        _manifest(default_base_url="http://api.deepseek.com/v1")


def test_manifest_allows_http_localhost_development_targets() -> None:
    manifest = _manifest(
        provider_id="custom-local",
        default_base_url="http://localhost:11434/v1",
    )
    loopback = _manifest(
        provider_id="custom-loopback",
        default_base_url="http://127.0.0.1:8000/v1",
    )

    assert manifest.default_base_url == "http://localhost:11434/v1"
    assert loopback.default_base_url == "http://127.0.0.1:8000/v1"


def test_manifest_requires_https_for_localhost_without_the_allowance() -> None:
    # Pins the narrowness of the rule: the allowance is the documented
    # localhost/loopback exception, not a blanket "dev mode" escape hatch.
    with pytest.raises(ValueError, match="default_base_url must use https"):
        _manifest(default_base_url="http://dev.internal.example/v1")
    with pytest.raises(ValueError, match="default_base_url must use https"):
        _manifest(default_base_url="http://localhost.evil.example/v1")


def test_manifest_rejects_blank_and_unsupported_base_url() -> None:
    with pytest.raises(ValueError, match="default_base_url cannot be empty"):
        _manifest(default_base_url="   ")
    with pytest.raises(ValueError, match="default_base_url must use https"):
        _manifest(default_base_url="ftp://api.deepseek.com/v1")
    with pytest.raises(ValueError, match="default_base_url must use https"):
        _manifest(default_base_url="api.deepseek.com/v1")


def test_manifest_requires_first_wave_bearer_auth_scheme() -> None:
    with pytest.raises(ValueError, match="auth_scheme must be 'bearer'"):
        _manifest(auth_scheme="basic")
    with pytest.raises(ValueError, match="auth_scheme must be 'bearer'"):
        _manifest(auth_scheme="   ")


def test_manifest_normalizes_bearer_auth_scheme_case() -> None:
    manifest = _manifest(auth_scheme="  BEARER ")

    assert manifest.auth_scheme == FIRST_WAVE_AUTH_SCHEME


def test_manifest_requires_leading_slash_models_path() -> None:
    with pytest.raises(ValueError, match="models_path must be absolute"):
        _manifest(models_path="models")
    with pytest.raises(ValueError, match="models_path cannot be empty"):
        _manifest(models_path="   ")


def test_manifest_rejects_blank_api_style_entries() -> None:
    with pytest.raises(ValueError, match="api_styles cannot contain empty values"):
        _manifest(api_styles=("chat_completions", "  "))


def test_manifest_has_no_credential_field() -> None:
    names = [field.name for field in dataclasses.fields(ProviderManifest)]

    assert names == [
        "provider_id",
        "display_name",
        "billing_class",
        "default_base_url",
        "auth_scheme",
        "models_path",
        "api_styles",
        "activation_allowlist",
    ]
    for forbidden in _FORBIDDEN_FIELD_NAMES:
        assert forbidden not in names
        assert not hasattr(_manifest(), forbidden)


def test_registry_rejects_duplicate_provider_id() -> None:
    registry = ProviderManifestRegistry()
    registry.register(_manifest())
    duplicate = _manifest(display_name="DeepSeek Duplicate")

    with pytest.raises(ValueError, match="duplicate provider_id: deepseek"):
        registry.register(duplicate)


def test_registry_rejects_duplicate_across_normalization() -> None:
    registry = ProviderManifestRegistry()
    registry.register(_manifest(provider_id="DeepSeek"))

    with pytest.raises(ValueError, match="duplicate provider_id: deepseek"):
        registry.register(_manifest(provider_id="  DEEPSEEK  "))


def test_registry_get_normalizes_and_returns_none_for_misses() -> None:
    registry = ProviderManifestRegistry()
    registered = registry.register(_manifest(provider_id="  DeepSeek  "))

    assert registry.get("deepseek") is registered
    assert registry.get("  DEEPSEEK ") is registered
    assert registry.get("missing-provider") is None
    assert registry.get("   ") is None
    assert registry.get("") is None


def test_registry_list_is_sorted_by_provider_id() -> None:
    registry = ProviderManifestRegistry()
    for provider_id in ["openrouter", "commandcode", "deepseek"]:
        registry.register(_manifest(provider_id=provider_id, display_name=provider_id))

    assert [m.provider_id for m in registry.list()] == [
        "commandcode",
        "deepseek",
        "openrouter",
    ]


def test_registry_list_filters_by_normalized_provider_id() -> None:
    registry = ProviderManifestRegistry()
    deepseek = registry.register(_manifest(provider_id="deepseek"))
    other = registry.register(
        _manifest(
            provider_id="openrouter", default_base_url="https://openrouter.ai/api/v1"
        )
    )

    assert registry.list(provider_id="  DEEPSEEK ") == (deepseek,)
    assert registry.list(provider_id="   ") == ()
    assert registry.list(provider_id="unknown-provider") == ()
    assert set(registry.list()) == {deepseek, other}
