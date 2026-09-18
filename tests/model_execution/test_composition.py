"""CMMChat Wave E0 — deterministic tests of the seam composition.

The composition is where the CMMChat Router becomes a canonical provider inside
CMM OS.  These tests pin:

* the provider definition itself (loopback-only, `chat_completions`, bearer
  resolved by the canonical ``ProviderSpec`` environment mechanism);
* the refusal of any non-loopback endpoint, so the router can never be reached
  over LAN through this seam;
* the model registration over the canonical ``ModelCatalog`` bound to the
  canonical ``ProviderRegistry`` instance the composition was handed;
* the reuse of that very instance (no second registry is created) and the
  fail-closed refusal of a foreign provider definition claiming the canonical
  router identity.
"""

from __future__ import annotations

from typing import Any

import pytest

from cmm.model_execution import composition
from cmm.model_execution.composition import (
    CHAT_ONLY_ROUTER_BASE_URL,
    CHAT_ONLY_ROUTER_BEARER_ENV,
    CHAT_ONLY_ROUTER_CONTEXT_WINDOW,
    CHAT_ONLY_ROUTER_MODEL_ENV,
    CHAT_ONLY_ROUTER_PROVIDER_ID,
    build_local_model_execution,
    chat_only_router_provider_spec,
    configured_model_ids,
    discover_chat_only_router_models,
    register_chat_only_router,
)
from cmm.model_execution.executor import CanonicalModelExecutor
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

MODEL_ID = "chatgpt/chatgpt-web/medium"


class _ScriptedDiscoveryClient:
    """The canonical discovery contract: a no-argument ``list_models()``."""

    def __init__(self, *, models: tuple[str, ...] = (MODEL_ID,)) -> None:
        self.models = models
        self.calls = 0

    def list_models(self) -> tuple[str, ...]:
        self.calls += 1
        return self.models


def _registry() -> ProviderRegistry:
    return ProviderRegistry()


# ── The canonical router provider definition ─────────────────────────────────


def test_the_router_provider_is_a_loopback_chat_completions_provider() -> None:
    spec = chat_only_router_provider_spec()

    assert spec.id == CHAT_ONLY_ROUTER_PROVIDER_ID
    assert spec.provider_type == "local"
    assert spec.api_style == "chat_completions"
    assert spec.api_key_env == CHAT_ONLY_ROUTER_BEARER_ENV
    assert spec.resolve_base_url() == CHAT_ONLY_ROUTER_BASE_URL
    assert CHAT_ONLY_ROUTER_BASE_URL == "http://127.0.0.1:8790/v1"


@pytest.mark.parametrize(
    "base_url",
    [
        "http://192.168.1.5:8790/v1",
        "http://10.0.0.4:8790/v1",
        "https://router.example.com/v1",
        "http://127.0.0.1.example.com:8790/v1",
        "",
    ],
)
def test_a_non_loopback_router_endpoint_is_refused(base_url: str) -> None:
    with pytest.raises(ValueError):
        chat_only_router_provider_spec(base_url=base_url)


def test_a_loopback_override_is_accepted() -> None:
    spec = chat_only_router_provider_spec(base_url="http://127.0.0.1:9876/v1")

    assert spec.resolve_base_url() == "http://127.0.0.1:9876/v1"


# ── Model identity configuration ─────────────────────────────────────────────


def test_an_absent_model_configuration_reports_no_explicit_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(CHAT_ONLY_ROUTER_MODEL_ENV, raising=False)

    assert configured_model_ids() is None


def test_a_configured_model_list_is_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(CHAT_ONLY_ROUTER_MODEL_ENV, f" {MODEL_ID} , claude/sonnet ,, ")

    assert configured_model_ids() == (MODEL_ID, "claude/sonnet")


# ── Discovery ────────────────────────────────────────────────────────────────


def test_models_are_discovered_through_the_canonical_discovery_contract() -> None:
    client = _ScriptedDiscoveryClient(models=(MODEL_ID, "claude/sonnet"))

    assert discover_chat_only_router_models(client=client) == (
        MODEL_ID,
        "claude/sonnet",
    )
    assert client.calls == 1


def test_discovery_targets_the_loopback_router_with_the_configured_bearer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(CHAT_ONLY_ROUTER_BEARER_ENV, "secret-bearer-value")
    recorded: dict[str, Any] = {}

    class _RecordingClient:
        def __init__(
            self, *, api_key: str | None = None, base_url: str | None = None
        ) -> None:
            recorded["api_key"] = api_key
            recorded["base_url"] = base_url

        def list_models(self) -> tuple[str, ...]:
            return (MODEL_ID,)

    monkeypatch.setattr(composition, "OpenAICompatibleClient", _RecordingClient)

    assert discover_chat_only_router_models() == (MODEL_ID,)
    assert recorded == {
        "api_key": "secret-bearer-value",
        "base_url": CHAT_ONLY_ROUTER_BASE_URL,
    }
    assert "secret-bearer-value" not in repr(CHAT_ONLY_ROUTER_BASE_URL)


# ── Registration ─────────────────────────────────────────────────────────────


def test_registration_binds_the_router_provider_to_the_given_registry() -> None:
    registry = _registry()
    catalog = ModelCatalog(registry)

    spec, models = register_chat_only_router(
        provider_registry=registry, model_catalog=catalog, model_ids=(MODEL_ID,)
    )

    assert registry.get(CHAT_ONLY_ROUTER_PROVIDER_ID) is spec
    assert [model.id for model in models] == [MODEL_ID]
    assert catalog.get(MODEL_ID, provider_id=CHAT_ONLY_ROUTER_PROVIDER_ID) is models[0]
    assert models[0].context_window == CHAT_ONLY_ROUTER_CONTEXT_WINDOW
    assert models[0].qualified_id == f"{CHAT_ONLY_ROUTER_PROVIDER_ID}:{MODEL_ID}"


def test_registration_is_idempotent_for_the_canonical_definition() -> None:
    registry = _registry()
    catalog = ModelCatalog(registry)

    first_spec, first_models = register_chat_only_router(
        provider_registry=registry, model_catalog=catalog, model_ids=(MODEL_ID,)
    )
    second_spec, second_models = register_chat_only_router(
        provider_registry=registry, model_catalog=catalog, model_ids=(MODEL_ID,)
    )

    assert first_spec is second_spec
    assert first_models[0] is second_models[0]
    assert len(registry.list()) == 1
    assert len(catalog.list()) == 1


def test_registration_refuses_an_empty_model_identity() -> None:
    registry = _registry()
    catalog = ModelCatalog(registry)

    with pytest.raises(ValueError):
        register_chat_only_router(
            provider_registry=registry, model_catalog=catalog, model_ids=()
        )


def test_registration_refuses_a_foreign_provider_claiming_the_router_identity() -> None:
    registry = _registry()
    catalog = ModelCatalog(registry)
    registry.register(
        ProviderSpec(
            id=CHAT_ONLY_ROUTER_PROVIDER_ID,
            provider_type="remote",
            api_style="chat_completions",
            base_url="https://example.com/v1",
        )
    )

    with pytest.raises(ValueError):
        register_chat_only_router(
            provider_registry=registry, model_catalog=catalog, model_ids=(MODEL_ID,)
        )


def test_registration_refuses_a_catalog_bound_to_another_registry() -> None:
    registry = _registry()
    other_catalog = ModelCatalog(_registry())

    with pytest.raises(TypeError):
        register_chat_only_router(
            provider_registry=registry,
            model_catalog=other_catalog,
            model_ids=(MODEL_ID,),
        )


# ── The composed seam ────────────────────────────────────────────────────────


def test_the_composed_seam_uses_the_registry_instance_it_was_handed() -> None:
    registry = _registry()

    graph = build_local_model_execution(
        provider_registry=registry, model_ids=(MODEL_ID,)
    )

    assert registry.has(CHAT_ONLY_ROUTER_PROVIDER_ID)
    assert graph.provider_spec is registry.get(CHAT_ONLY_ROUTER_PROVIDER_ID)
    assert graph.models[0].id == MODEL_ID
    assert isinstance(graph.executor, CanonicalModelExecutor)


def test_the_composed_seam_discoveries_models_when_none_are_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(CHAT_ONLY_ROUTER_MODEL_ENV, raising=False)
    registry = _registry()
    client = _ScriptedDiscoveryClient()

    graph = build_local_model_execution(provider_registry=registry, client=client)

    assert [model.id for model in graph.models] == [MODEL_ID]
    assert client.calls == 1


@pytest.mark.parametrize("registry", [None, object()])
def test_the_composition_refuses_a_non_canonical_registry(registry: Any) -> None:
    with pytest.raises(TypeError):
        build_local_model_execution(provider_registry=registry, model_ids=(MODEL_ID,))


def test_the_composed_seam_never_creates_a_second_registry() -> None:
    """The provider identity lives in the very registry the caller supplied."""

    registry = _registry()

    graph = build_local_model_execution(
        provider_registry=registry, model_ids=(MODEL_ID,)
    )

    assert [spec.id for spec in registry.list()] == [CHAT_ONLY_ROUTER_PROVIDER_ID]
    assert graph.provider_spec is registry.get(CHAT_ONLY_ROUTER_PROVIDER_ID)

    # A catalog bound to the same registry resolves the router provider, so no
    # registration leaked into a second, parallel registry authority.
    catalog = ModelCatalog(registry)
    catalog.register(
        ModelSpec(
            id=MODEL_ID,
            provider_id=CHAT_ONLY_ROUTER_PROVIDER_ID,
            context_window=CHAT_ONLY_ROUTER_CONTEXT_WINDOW,
        )
    )
    assert (
        catalog.get(MODEL_ID, provider_id=CHAT_ONLY_ROUTER_PROVIDER_ID).id == MODEL_ID
    )
