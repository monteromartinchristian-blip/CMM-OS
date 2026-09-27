"""Wave E real-inference closure — the local runtime lane of the seam.

The CMMChat Router is the program's provider/model access boundary, but the
real cancellation journey needs a runtime that streams token-by-token on this
machine.  The canonical seam composes a *second* ordinary ``ProviderSpec`` over
the same OpenAI-compatible contract for a loopback-only local runtime (vLLM at
127.0.0.1:8000).  No provider machinery is added: the provider is an ordinary
spec, its models are ordinary catalog entries in the same canonical catalog,
and streaming/cancellation reuse the canonical
``OpenAICompatibleProvider``/client path.
"""

from __future__ import annotations

import pytest

from cmm.model_execution.composition import (
    CHAT_ONLY_ROUTER_MODEL_ENV,
    CHAT_ONLY_ROUTER_PROVIDER_ID,
    LOCAL_RUNTIME_API_KEY_ENV,
    LOCAL_RUNTIME_BASE_URL_ENV,
    LOCAL_RUNTIME_DEFAULT_BASE_URL,
    LOCAL_RUNTIME_MODEL_IDS_ENV,
    LOCAL_RUNTIME_PROVIDER_ID,
    LocalModelExecution,
    build_local_model_execution,
    configured_local_runtime_model_ids,
    local_runtime_provider_spec,
    register_local_runtime,
)
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

LOCAL_MODEL_ID = "qwen3.8-27b-fp8"


class _ScriptedDiscoveryClient:
    def __init__(self, model_ids: tuple[str, ...]) -> None:
        self.model_ids = model_ids

    def list_models(self) -> list[str]:
        return list(self.model_ids)


def test_the_local_runtime_provider_is_a_loopback_chat_completions_provider() -> None:
    spec = local_runtime_provider_spec()
    assert spec.id == LOCAL_RUNTIME_PROVIDER_ID
    assert spec.provider_type == "local"
    assert spec.api_style == "chat_completions"
    assert spec.resolve_base_url() == LOCAL_RUNTIME_DEFAULT_BASE_URL
    # The credential is an env name, never a value in code; a loopback runtime
    # receives whatever placeholder the launcher configures.
    assert spec.api_key_env == LOCAL_RUNTIME_API_KEY_ENV
    assert spec.resolve_api_key() is None


def test_the_local_runtime_credential_resolves_through_the_env_mechanism(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LOCAL_RUNTIME_API_KEY_ENV, "placeholder-not-a-secret")
    spec = local_runtime_provider_spec()
    assert spec.resolve_api_key() == "placeholder-not-a-secret"


def test_a_non_loopback_local_runtime_endpoint_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LOCAL_RUNTIME_BASE_URL_ENV, "http://10.0.0.5:8000/v1")
    with pytest.raises(ValueError):
        local_runtime_provider_spec()
    with pytest.raises(ValueError):
        local_runtime_provider_spec(base_url="https://runtime.example/v1")


def test_a_configured_local_runtime_endpoint_override_must_stay_loopback() -> None:
    spec = local_runtime_provider_spec(base_url="http://localhost:8123/v1")
    assert spec.resolve_base_url() == "http://localhost:8123/v1"


def test_configured_local_runtime_model_ids_are_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        LOCAL_RUNTIME_MODEL_IDS_ENV, f" {LOCAL_MODEL_ID} , other/model ,, "
    )
    assert configured_local_runtime_model_ids() == (LOCAL_MODEL_ID, "other/model")


def test_an_absent_local_runtime_configuration_registers_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(LOCAL_RUNTIME_MODEL_IDS_ENV, raising=False)
    monkeypatch.delenv(LOCAL_RUNTIME_BASE_URL_ENV, raising=False)
    monkeypatch.delenv(CHAT_ONLY_ROUTER_MODEL_ENV, raising=False)
    execution = build_local_model_execution(
        provider_registry=ProviderRegistry(),
        model_ids=("chatgpt/chatgpt-web/medium",),
        client=_ScriptedDiscoveryClient(()),
    )
    provider_ids = {model.provider_id for model in execution.executor.catalog()}
    assert provider_ids == {CHAT_ONLY_ROUTER_PROVIDER_ID}


def test_the_build_registers_local_runtime_models_from_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LOCAL_RUNTIME_MODEL_IDS_ENV, LOCAL_MODEL_ID)
    monkeypatch.delenv(LOCAL_RUNTIME_BASE_URL_ENV, raising=False)
    monkeypatch.delenv(CHAT_ONLY_ROUTER_MODEL_ENV, raising=False)
    execution = build_local_model_execution(
        provider_registry=ProviderRegistry(),
        model_ids=("chatgpt/chatgpt-web/medium",),
        client=_ScriptedDiscoveryClient(()),
    )
    catalog = {model.model_id: model for model in execution.executor.catalog()}
    assert LOCAL_MODEL_ID in catalog
    local = catalog[LOCAL_MODEL_ID]
    assert local.provider_id == LOCAL_RUNTIME_PROVIDER_ID
    assert local.locality == "local"
    assert local.availability == "available"
    # The router lane stays composed untouched beside the local runtime.
    assert catalog["chatgpt/chatgpt-web/medium"].provider_id == (
        CHAT_ONLY_ROUTER_PROVIDER_ID
    )
    assert isinstance(execution, LocalModelExecution)


def test_local_runtime_registration_binds_the_same_canonical_authorities() -> None:
    registry = ProviderRegistry()
    catalog = ModelCatalog(registry)
    spec, models = register_local_runtime(
        provider_registry=registry,
        model_catalog=catalog,
        model_ids=(LOCAL_MODEL_ID,),
    )
    assert registry.get(LOCAL_RUNTIME_PROVIDER_ID) == spec
    assert (
        catalog.get(LOCAL_MODEL_ID, provider_id=LOCAL_RUNTIME_PROVIDER_ID) == models[0]
    )
    assert models[0].context_window >= 1


def test_local_runtime_registration_is_idempotent_but_refuses_divergence() -> None:
    registry = ProviderRegistry()
    catalog = ModelCatalog(registry)
    first, _ = register_local_runtime(
        provider_registry=registry,
        model_catalog=catalog,
        model_ids=(LOCAL_MODEL_ID,),
    )
    again, models = register_local_runtime(
        provider_registry=registry,
        model_catalog=catalog,
        model_ids=(LOCAL_MODEL_ID, "second/model"),
    )
    assert again == first
    assert {model.id for model in models} == {LOCAL_MODEL_ID, "second/model"}

    registry.register(
        ProviderSpec(
            id="other",
            provider_type="remote",
            api_style="chat_completions",
            base_url="http://127.0.0.1:9000/v1",
        )
    )
    with pytest.raises(ValueError):
        register_local_runtime(
            provider_registry=registry,
            model_catalog=catalog,
            model_ids=(LOCAL_MODEL_ID,),
            base_url="http://127.0.0.1:8123/v1",
        )


def test_local_runtime_registration_refuses_empty_or_malformed_ids() -> None:
    registry = ProviderRegistry()
    catalog = ModelCatalog(registry)
    with pytest.raises(ValueError):
        register_local_runtime(
            provider_registry=registry, model_catalog=catalog, model_ids=()
        )
    with pytest.raises(ValueError):
        register_local_runtime(
            provider_registry=registry, model_catalog=catalog, model_ids=("  ",)
        )
    with pytest.raises(ValueError):
        register_local_runtime(
            provider_registry=registry,
            model_catalog=catalog,
            model_ids=(3,),  # type: ignore[arg-type]
        )


def test_local_runtime_registration_requires_the_bound_canonical_catalog() -> None:
    registry = ProviderRegistry()
    with pytest.raises(TypeError):
        register_local_runtime(
            provider_registry=registry,
            model_catalog=ModelCatalog(ProviderRegistry()),
            model_ids=(LOCAL_MODEL_ID,),
        )


def test_the_local_runtime_shares_one_registry_and_one_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LOCAL_RUNTIME_MODEL_IDS_ENV, LOCAL_MODEL_ID)
    monkeypatch.delenv(CHAT_ONLY_ROUTER_MODEL_ENV, raising=False)
    registry = ProviderRegistry()
    execution = build_local_model_execution(
        provider_registry=registry,
        model_ids=("chatgpt/chatgpt-web/medium",),
        client=_ScriptedDiscoveryClient(()),
    )
    assert execution.executor._provider_registry is registry
    assert {model.provider_id for model in execution.executor.catalog()} == {
        CHAT_ONLY_ROUTER_PROVIDER_ID,
        LOCAL_RUNTIME_PROVIDER_ID,
    }
    qualified = execution.executor._model_catalog.get(
        LOCAL_MODEL_ID, provider_id=LOCAL_RUNTIME_PROVIDER_ID
    )
    assert isinstance(qualified, ModelSpec)


def test_router_disabled_composes_the_local_lane_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CMM_ROUTER_DISABLED", "1")
    monkeypatch.setenv(LOCAL_RUNTIME_MODEL_IDS_ENV, LOCAL_MODEL_ID)
    monkeypatch.delenv(CHAT_ONLY_ROUTER_MODEL_ENV, raising=False)

    class ExplodingClient:
        def list_models(self):  # pragma: no cover - must never be called
            raise AssertionError("the router must not be contacted when disabled")

    execution = build_local_model_execution(
        provider_registry=ProviderRegistry(), client=ExplodingClient()
    )
    assert execution.provider_spec.id == LOCAL_RUNTIME_PROVIDER_ID
    assert {model.provider_id for model in execution.executor.catalog()} == {
        LOCAL_RUNTIME_PROVIDER_ID
    }


def test_router_disabled_without_a_local_lane_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CMM_ROUTER_DISABLED", "true")
    monkeypatch.delenv(LOCAL_RUNTIME_MODEL_IDS_ENV, raising=False)
    with pytest.raises(ValueError):
        build_local_model_execution(provider_registry=ProviderRegistry())


def test_a_router_that_refuses_the_connection_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A router that is down is a composition failure, never a silent empty seam."""

    monkeypatch.delenv("CMM_ROUTER_DISABLED", raising=False)
    monkeypatch.delenv(CHAT_ONLY_ROUTER_MODEL_ENV, raising=False)
    monkeypatch.delenv(LOCAL_RUNTIME_MODEL_IDS_ENV, raising=False)

    class RefusingClient:
        def list_models(self):
            raise ConnectionError("[Errno 61] Connection refused")

    registry = ProviderRegistry()
    with pytest.raises(ConnectionError):
        build_local_model_execution(provider_registry=registry, client=RefusingClient())
    assert registry.list() == ()


def test_a_router_that_advertises_no_model_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CMM_ROUTER_DISABLED", raising=False)
    monkeypatch.delenv(CHAT_ONLY_ROUTER_MODEL_ENV, raising=False)
    monkeypatch.delenv(LOCAL_RUNTIME_MODEL_IDS_ENV, raising=False)

    registry = ProviderRegistry()
    with pytest.raises(ValueError):
        build_local_model_execution(
            provider_registry=registry, client=_ScriptedDiscoveryClient(())
        )
    assert registry.list() == ()


def test_the_router_endpoint_override_moves_the_port_but_never_leaves_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cmm.model_execution.composition import (
        CHAT_ONLY_ROUTER_BASE_URL_ENV,
        chat_only_router_provider_spec,
    )

    monkeypatch.setenv(CHAT_ONLY_ROUTER_BASE_URL_ENV, "http://127.0.0.1:8791/v1")
    assert (
        chat_only_router_provider_spec().base_url == "http://127.0.0.1:8791/v1"
    )
    # An explicit argument still wins over the launcher environment.
    assert (
        chat_only_router_provider_spec(base_url="http://localhost:8790/v1").base_url
        == "http://localhost:8790/v1"
    )

    monkeypatch.setenv(CHAT_ONLY_ROUTER_BASE_URL_ENV, "http://192.168.1.10:8790/v1")
    with pytest.raises(ValueError):
        chat_only_router_provider_spec()
