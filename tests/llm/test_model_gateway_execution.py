"""Phase 11.21 — explicit model execution tests.

These tests freeze the authoritative explicit-model path: canonical lookup,
provider availability, capability validation, provider adaptation and normalized
response, all before any provider I/O on failure, with no silent model
substitution and safe execution evidence.
"""

from __future__ import annotations

import json

import pytest

from kernel.llm.capabilities import ModelCapabilities
from kernel.llm.model_catalog import ModelSpec
from kernel.llm.model_gateway import ModelGateway
from kernel.llm.model_gateway_contracts import (
    ModelGatewayRequest,
    ModelGatewayResponse,
    ModelInputPart,
    ModelToolCall,
    ModelToolDefinition,
)
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode
from kernel.llm.model_provider_adapter import (
    InMemoryModelProviderAdapter,
    ModelProviderAdapterRegistry,
)
from kernel.llm.model_streaming import ModelCallCancellation
from kernel.llm.provider_registry import ProviderSpec
from tests.llm.model_gateway_support import (
    TEXT_CAPABLE,
    GatewayRuntime,
    build_canonical_graph,
    build_runtime,
)


def _runtime(**overrides: object) -> GatewayRuntime:
    """Compose a gateway whose default model declares text/tool/schema support."""

    overrides.setdefault("capabilities", TEXT_CAPABLE)
    return build_runtime(**overrides)  # type: ignore[arg-type]


def _request(**overrides: object) -> ModelGatewayRequest:
    values: dict[str, object] = {
        "request_id": "model-request-1",
        "model_id": "local:model-1",
        "input_parts": (ModelInputPart.text_part("hola"),),
    }
    values.update(overrides)
    return ModelGatewayRequest(**values)  # type: ignore[arg-type]


# ── Successful explicit execution ────────────────────────────────────────────


def test_explicit_execution_end_to_end() -> None:
    runtime = _runtime()
    runtime.adapter("local").add_response(content="respuesta", finish_reason="stop")

    response = runtime.gateway.execute(_request())

    assert isinstance(response, ModelGatewayResponse)
    assert response.content == "respuesta"
    assert response.provider_id == "local"
    assert response.model_id == "model-1"
    assert response.finish_reason == "stop"
    assert response.cancelled is False
    assert response.error_code is None
    assert response.tool_calls == ()
    assert response.structured_output is None
    assert runtime.adapter("local").call_count == 1


def test_explicit_execution_sends_the_requested_model_identity() -> None:
    runtime = _runtime()
    runtime.adapter("local").add_response(content="ok")

    runtime.gateway.execute(_request())

    received = runtime.adapter("local").requests[0]
    assert received.model_id == "model-1"
    assert received.provider_id == "local"
    assert received.request_id == "model-request-1"


def test_successful_execution_emits_safe_evidence() -> None:
    runtime = _runtime()
    runtime.adapter("local").add_response(content="ok")

    response = runtime.gateway.execute(_request())

    assert response.facts is not None
    facts = response.facts
    assert facts.success is True
    assert facts.request_id == "model-request-1"
    assert facts.provider_id == "local"
    assert facts.model_id == "model-1"
    assert facts.capability_decision == "verified"
    assert facts.privacy_decision == "not_required"
    assert facts.input_modalities == ("text",)
    assert facts.latency_ms is not None and facts.latency_ms >= 0
    assert facts.retry_count == 0
    assert facts.fallback_used is False
    assert runtime.sink.records == (facts,)


def test_evidence_serialization_never_carries_provider_metadata() -> None:
    runtime = _runtime(derive_content_from_input=True)
    runtime.adapter("local").add_response(content="ok")

    response = runtime.gateway.execute(_request())

    serialized = json.dumps(response.to_dict())
    assert "input_content_digest" not in serialized
    assert "input_parts" not in serialized


def test_gateway_exposes_the_adapter_registry_read_only() -> None:
    runtime = _runtime()

    assert isinstance(runtime.gateway.adapter_registry, ModelProviderAdapterRegistry)
    assert runtime.gateway.adapter_registry.get("local") is runtime.adapter("local")


# ── Preflight failures never reach the provider ──────────────────────────────


def test_gateway_without_adapters_fails_closed() -> None:
    graph = build_canonical_graph()
    graph.register_local_model("model-1")
    gateway = ModelGateway(
        provider_registry=graph.providers,
        model_catalog=graph.models,
    )

    with pytest.raises(ModelGatewayError) as error:
        gateway.execute(_request())

    assert error.value.code is ModelGatewayErrorCode.PROVIDER_NOT_AVAILABLE


def test_model_not_found_fails_before_provider_io() -> None:
    runtime = _runtime()
    runtime.adapter("local").add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(model_id="local:missing"))

    assert error.value.code is ModelGatewayErrorCode.MODEL_NOT_FOUND
    assert runtime.adapter("local").call_count == 0


def test_disabled_provider_fails_before_provider_io() -> None:
    graph = build_canonical_graph()
    graph.providers.register(
        ProviderSpec(
            id="disabled",
            provider_type="local",
            api_style="chat_completions",
            enabled=False,
        )
    )
    graph.models.register(
        ModelSpec(id="model-1", provider_id="disabled", context_window=1000)
    )
    adapter = InMemoryModelProviderAdapter("disabled")
    adapter.add_response(content="never")
    gateway = ModelGateway(
        provider_registry=graph.providers,
        model_catalog=graph.models,
        adapters=ModelProviderAdapterRegistry((adapter,)),
    )

    with pytest.raises(ModelGatewayError) as error:
        gateway.execute(_request(model_id="disabled:model-1"))

    assert error.value.code is ModelGatewayErrorCode.PROVIDER_NOT_AVAILABLE
    assert adapter.call_count == 0


def test_unavailable_provider_fails_before_provider_io() -> None:
    graph = build_canonical_graph()
    graph.providers.register(
        ProviderSpec(
            id="flaky",
            provider_type="remote",
            api_style="chat_completions",
            base_url="https://flaky.example/v1",
            availability="unavailable",
        )
    )
    graph.models.register(
        ModelSpec(id="model-1", provider_id="flaky", context_window=1000)
    )
    adapter = InMemoryModelProviderAdapter("flaky")
    adapter.add_response(content="never")
    gateway = ModelGateway(
        provider_registry=graph.providers,
        model_catalog=graph.models,
        adapters=ModelProviderAdapterRegistry((adapter,)),
    )

    with pytest.raises(ModelGatewayError) as error:
        gateway.execute(_request(model_id="flaky:model-1"))

    assert error.value.code is ModelGatewayErrorCode.PROVIDER_NOT_AVAILABLE
    assert adapter.call_count == 0


def test_unavailable_model_fails_before_provider_io() -> None:
    runtime = _runtime()
    runtime.graph.models.register(
        ModelSpec(
            id="withdrawn",
            provider_id="local",
            context_window=1000,
            availability="disabled",
        )
    )
    runtime.adapter("local").add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(model_id="local:withdrawn"))

    assert error.value.code is ModelGatewayErrorCode.MODEL_UNAVAILABLE
    assert runtime.adapter("local").call_count == 0


def test_stale_model_authority_fails_before_provider_io() -> None:
    runtime = _runtime()
    runtime.graph.providers.register(
        ProviderSpec(
            id="local",
            provider_type="local",
            api_style="chat_completions",
            availability="available",
        ),
        replace_existing=True,
    )
    runtime.adapter("local").add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request())

    assert error.value.code is ModelGatewayErrorCode.MODEL_UNAVAILABLE
    assert runtime.adapter("local").call_count == 0


def test_missing_adapter_fails_before_provider_io() -> None:
    graph = build_canonical_graph()
    graph.register_local_model("model-1")
    gateway = ModelGateway(
        provider_registry=graph.providers,
        model_catalog=graph.models,
        adapters=ModelProviderAdapterRegistry(),
    )

    with pytest.raises(ModelGatewayError) as error:
        gateway.execute(_request())

    assert error.value.code is ModelGatewayErrorCode.PROVIDER_NOT_AVAILABLE


def test_unsupported_required_capability_fails_before_provider_io() -> None:
    runtime = _runtime(capabilities=ModelCapabilities())
    runtime.adapter("local").add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(required_capabilities=("vision",)))

    assert error.value.code is ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED
    assert runtime.adapter("local").call_count == 0


def test_supported_required_capability_executes() -> None:
    runtime = _runtime(capabilities=ModelCapabilities(vision=True, tool_calling=True))
    runtime.adapter("local").add_response(content="ok")

    response = runtime.gateway.execute(
        _request(required_capabilities=("vision", "tool_calling"))
    )

    assert response.content == "ok"
    assert runtime.adapter("local").call_count == 1


def test_unknown_or_stale_capability_is_never_assumed() -> None:
    runtime = _runtime(capabilities=ModelCapabilities())
    runtime.adapter("local").add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(required_capabilities=("document",)))

    assert error.value.code is ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED
    assert runtime.adapter("local").call_count == 0


# ── Explicit authority is never substituted ─────────────────────────────────


def test_explicit_model_is_never_silently_substituted() -> None:
    graph = build_canonical_graph()
    graph.register_local_model("primary")
    graph.register_local_model("alternative")
    primary = InMemoryModelProviderAdapter("local")
    primary.add_failure(
        ModelGatewayErrorCode.PROVIDER_FAILURE, "transient", retryable=True
    )
    gateway = ModelGateway(
        provider_registry=graph.providers,
        model_catalog=graph.models,
        adapters=ModelProviderAdapterRegistry((primary,)),
    )

    with pytest.raises(ModelGatewayError) as error:
        gateway.execute(_request(model_id="local:primary", fallback_model_ids=()))

    assert error.value.code is ModelGatewayErrorCode.PROVIDER_FAILURE
    assert primary.call_count == 1
    assert primary.requests[0].model_id == "primary"


# ── Cancellation and narrow call handles ────────────────────────────────────


def test_cancellation_before_execution_fails_closed() -> None:
    runtime = _runtime()
    runtime.adapter("local").add_response(content="never")
    cancellation = ModelCallCancellation()
    cancellation.cancel("user cancelled")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(), cancellation=cancellation)

    assert error.value.code is ModelGatewayErrorCode.MODEL_CALL_CANCELLED
    assert runtime.adapter("local").call_count == 0


def test_open_call_produces_a_narrow_cancellable_handle() -> None:
    runtime = _runtime()
    runtime.adapter("local").add_response(content="ok")

    handle = runtime.gateway.open_call(_request())

    assert handle.request_id == "model-request-1"
    assert handle.cancelled is False
    assert handle.cancel("stop") is True
    assert handle.cancel("stop again") is False
    assert handle.cancelled is True


def test_execution_without_privacy_metadata_allows_a_local_provider() -> None:
    runtime = _runtime()
    runtime.adapter("local").add_response(content="ok")

    response = runtime.gateway.execute(_request(privacy=None))

    assert response.content == "ok"
    assert response.facts is not None
    assert response.facts.privacy_decision == "not_required"


# ── Timeout ceiling and argument validation ─────────────────────────────────


def test_request_timeout_above_the_gateway_ceiling_fails_closed() -> None:
    runtime = _runtime(max_timeout_seconds=1.0)
    runtime.adapter("local").add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(timeout_seconds=30.0))

    assert error.value.code is ModelGatewayErrorCode.PROVIDER_REQUEST_INVALID
    assert runtime.adapter("local").call_count == 0


def test_gateway_rejects_a_foreign_request_object() -> None:
    runtime = _runtime()

    with pytest.raises(TypeError):
        runtime.gateway.execute(object())  # type: ignore[arg-type]


# ── Tool declarations reach the adapter without execution ───────────────────


def test_tool_declarations_reach_the_adapter_unexecuted() -> None:
    runtime = _runtime()
    runtime.adapter("local").add_response(
        content="",
        tool_calls=(ModelToolCall(call_id="call-1", tool_id="t1", arguments={"a": 1}),),
    )
    tool = ModelToolDefinition(tool_id="t1", description="example tool")

    response = runtime.gateway.execute(_request(tools=(tool,)))

    assert runtime.adapter("local").requests[0].tools == (tool,)
    assert response.tool_calls[0].call_id == "call-1"
    assert response.facts is not None
    assert response.facts.tool_use is True
