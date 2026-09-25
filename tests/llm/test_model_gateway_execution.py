"""Phase 11.21 — explicit model execution tests.

These tests freeze the authoritative explicit-model path: canonical lookup,
provider availability, capability validation, provider adaptation and normalized
response, all before any provider I/O on failure, with no silent model
substitution and safe execution evidence.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from cmm.agent_runtime.model_egress_privacy_adapter import CanonicalPrivacyEgressGate
from cmm.cognitive.privacy import (
    PrivacyMetadata,
    PrivacyPolicy,
    ProcessingLocation,
)
from kernel.llm.capabilities import ModelCapabilities, ReasoningEffort
from kernel.llm.model_catalog import ModelSpec
from kernel.llm.model_gateway import ModelGateway
from kernel.llm.model_gateway_contracts import (
    ModelGatewayRequest,
    ModelGatewayResponse,
    ModelInputPart,
    ModelSelectionMode,
    ModelToolCall,
    ModelToolDefinition,
)
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode
from kernel.llm.model_provider_adapter import (
    InMemoryModelProviderAdapter,
    ModelProviderAdapterRegistry,
)
from kernel.llm.model_selection import ModelRequirements, find_matching_models
from kernel.llm.model_streaming import ModelCallCancellation
from kernel.llm.provider_registry import ProviderSpec
from tests.llm.model_gateway_support import (
    PDF_BYTES,
    TEXT_CAPABLE,
    GatewayRuntime,
    build_canonical_graph,
    build_runtime,
)

LOCAL_ONLY = PrivacyMetadata(policy=PrivacyPolicy.LOCAL_ONLY)
REMOTE_ALLOWED = PrivacyMetadata(
    policy=PrivacyPolicy.REMOTE_ALLOWED,
    allow_remote=True,
    allowed_processing_locations=(
        ProcessingLocation.LOCAL,
        ProcessingLocation.REMOTE,
    ),
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


# ── AUTO selection reuses the canonical selection path ─────────────────────


def test_auto_selection_reuses_canonical_selection() -> None:
    graph = build_canonical_graph()
    graph.models.register(
        ModelSpec(
            id="plain",
            provider_id="local",
            context_window=32768,
            capabilities=ModelCapabilities(),
            availability="available",
        )
    )
    graph.models.register(
        ModelSpec(
            id="sees",
            provider_id="local",
            context_window=32768,
            capabilities=ModelCapabilities(vision=True),
            availability="available",
        )
    )
    adapter = InMemoryModelProviderAdapter("local")
    adapter.add_response(content="auto answer")
    gateway = ModelGateway(
        provider_registry=graph.providers,
        model_catalog=graph.models,
        adapters=ModelProviderAdapterRegistry((adapter,)),
    )

    response = gateway.execute(
        _request(
            model_id=None,
            selection_mode=ModelSelectionMode.AUTO,
            required_capabilities=("vision",),
        )
    )

    assert response.model_id == "sees"
    assert adapter.requests[0].model_id == "sees"
    assert response.facts is not None
    assert response.facts.selection_mode is ModelSelectionMode.AUTO


def test_auto_selection_fails_closed_when_no_canonical_model_matches() -> None:
    runtime = _runtime(capabilities=ModelCapabilities())
    runtime.adapter("local").add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(
                model_id=None,
                selection_mode=ModelSelectionMode.AUTO,
                required_capabilities=("vision",),
                # AUTO now evaluates every canonical candidate's own privacy
                # gate, so the fixture's remote candidate is reached before the
                # capability gate and needs real canonical privacy metadata.
                privacy=REMOTE_ALLOWED,
            )
        )

    # AUTO now evaluates each canonical candidate through the gateway's own hard
    # gates, so exhaustion reports the most specific safe canonical failure the
    # candidates produced (the canonical selector already drops the text-only
    # remote model, and the remaining local candidate lacks vision).  The
    # behaviour under test is unchanged: AUTO fails closed before provider I/O.
    assert error.value.code is ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED
    assert error.value.retryable is False
    assert error.value.details["candidates_considered"] == 1
    assert runtime.adapter("local").call_count == 0


def test_auto_selection_requires_a_declared_reasoning_effort() -> None:
    graph = build_canonical_graph()
    graph.models.register(
        ModelSpec(
            id="no-effort",
            provider_id="local",
            context_window=32768,
            capabilities=ModelCapabilities(reasoning=True),
            availability="available",
        )
    )
    graph.models.register(
        ModelSpec(
            id="declares-high",
            provider_id="local",
            context_window=32768,
            capabilities=ModelCapabilities(
                reasoning=True, reasoning_efforts=(ReasoningEffort.HIGH,)
            ),
            availability="available",
        )
    )
    adapter = InMemoryModelProviderAdapter(
        "local", reasoning_effort_map={ReasoningEffort.HIGH: "thinking_budget_high"}
    )
    adapter.add_response(content="deep")
    gateway = ModelGateway(
        provider_registry=graph.providers,
        model_catalog=graph.models,
        adapters=ModelProviderAdapterRegistry((adapter,)),
    )

    response = gateway.execute(
        _request(
            model_id=None,
            selection_mode=ModelSelectionMode.AUTO,
            reasoning_effort=ReasoningEffort.HIGH,
        )
    )

    assert response.model_id == "declares-high"
    assert adapter.native_efforts == ("thinking_budget_high",)


def test_auto_selection_respects_document_modality() -> None:
    graph = build_canonical_graph()
    graph.models.register(
        ModelSpec(
            id="text-only",
            provider_id="local",
            context_window=32768,
            capabilities=ModelCapabilities(),
            availability="available",
        )
    )
    graph.models.register(
        ModelSpec(
            id="documents",
            provider_id="local",
            context_window=32768,
            capabilities=ModelCapabilities(document_media_types=("application/pdf",)),
            availability="available",
        )
    )
    adapter = InMemoryModelProviderAdapter("local")
    adapter.add_response(content="document understood")
    gateway = ModelGateway(
        provider_registry=graph.providers,
        model_catalog=graph.models,
        adapters=ModelProviderAdapterRegistry((adapter,)),
    )

    response = gateway.execute(
        _request(
            model_id=None,
            selection_mode=ModelSelectionMode.AUTO,
            input_parts=(ModelInputPart.document_part(PDF_BYTES, "application/pdf"),),
        )
    )

    assert response.model_id == "documents"


def test_auto_selection_introduces_no_routing_policy_surface() -> None:
    runtime = _runtime()
    runtime.adapter("local").add_response(content="ok")

    for forbidden in (
        "rank_models",
        "score_models",
        "cheapest_model",
        "preferred_provider",
        "routing_policy",
    ):
        assert not hasattr(runtime.gateway, forbidden)

    response = runtime.gateway.execute(
        _request(model_id=None, selection_mode=ModelSelectionMode.AUTO)
    )
    assert response.model_id == "model-1"


# ── Remediation V1 MAJOR-01 — AUTO iterates canonical candidates through the
#    gateway's own hard execution gates and never stops on a candidate-local
#    failure (for example a canonical privacy denial for one provider).

#: Capabilities shared by the AUTO remediation fixtures: text-only, but with a
#: declared reasoning effort so the effort gate is exercised explicitly.
AUTO_EFFORT_CAPABILITIES = ModelCapabilities(
    reasoning=True,
    reasoning_efforts=(ReasoningEffort.HIGH,),
)


def _register_auto_model(
    graph,
    model_id: str,
    *,
    provider_id: str,
    input_cost: str,
    capabilities: ModelCapabilities,
) -> None:
    """Register one priced AUTO candidate so canonical cost ranking is stable."""

    graph.models.register(
        ModelSpec(
            id=model_id,
            provider_id=provider_id,
            context_window=32768,
            capabilities=capabilities,
            availability="available",
            input_cost_per_million=Decimal(input_cost),
            output_cost_per_million=Decimal(input_cost),
        )
    )


#: Sentinel distinguishing "use the canonical privacy gate" from an explicit
#: ``privacy_gate=None`` (a gateway composed with no privacy authority at all).
_DEFAULT_PRIVACY_GATE = object()


def _auto_runtime(
    *,
    remote_cost: str = "0.10",
    local_cost: str = "9.00",
    remote_capabilities: ModelCapabilities | None = None,
    local_capabilities: ModelCapabilities | None = None,
    register_remote_adapter: bool = True,
    privacy_gate: object = _DEFAULT_PRIVACY_GATE,
):
    """Compose the canonical remote-first/local-second AUTO fixture.

    The remote model is cheaper, so the canonical ``lowest_cost`` ranking puts it
    first; the local model is valid but ranked second.
    """

    resolved_gate = (
        CanonicalPrivacyEgressGate()
        if privacy_gate is _DEFAULT_PRIVACY_GATE
        else privacy_gate
    )
    graph = build_canonical_graph()
    _register_auto_model(
        graph,
        "cheap-remote",
        provider_id="remote-a",
        input_cost=remote_cost,
        capabilities=remote_capabilities or AUTO_EFFORT_CAPABILITIES,
    )
    _register_auto_model(
        graph,
        "pricey-local",
        provider_id="local",
        input_cost=local_cost,
        capabilities=local_capabilities or AUTO_EFFORT_CAPABILITIES,
    )
    remote = InMemoryModelProviderAdapter(
        "remote-a",
        reasoning_effort_map={ReasoningEffort.HIGH: "thinking_budget_high"},
    )
    remote.add_response(content="remote answer")
    local = InMemoryModelProviderAdapter(
        "local",
        reasoning_effort_map={ReasoningEffort.HIGH: "thinking_budget_high"},
    )
    local.add_response(content="local answer")
    adapters = [local]
    if register_remote_adapter:
        adapters.append(remote)
    gateway = ModelGateway(
        provider_registry=graph.providers,
        model_catalog=graph.models,
        adapters=ModelProviderAdapterRegistry(adapters),
        privacy_gate=resolved_gate,  # type: ignore[arg-type]
    )
    return graph, gateway, local, remote


def _auto_gateway(
    graph,
    adapters: list[InMemoryModelProviderAdapter] | None = None,
) -> ModelGateway:
    """Compose an AUTO gateway over the fixture graph with the given adapters."""

    return ModelGateway(
        provider_registry=graph.providers,
        model_catalog=graph.models,
        adapters=ModelProviderAdapterRegistry(adapters or ()),
        privacy_gate=CanonicalPrivacyEgressGate(),
    )


def _canonical_auto_order(graph, request: ModelGatewayRequest) -> tuple[str, ...]:
    """Return the exact canonical selection order for one AUTO request."""

    matches = find_matching_models(
        graph.models,
        graph.providers,
        ModelRequirements(
            tool_calling=bool(request.tools),
            structured_output=request.structured_output is not None,
            vision=request.has_image_input,
            reasoning=request.reasoning_effort
            not in (ReasoningEffort.DEFAULT, ReasoningEffort.NONE),
        ),
    )
    return tuple(model.qualified_id for model in matches)


def test_auto_selection_continues_past_a_privacy_denied_candidate() -> None:
    graph, gateway, local, remote = _auto_runtime()

    request = _request(
        model_id=None,
        selection_mode=ModelSelectionMode.AUTO,
        privacy=LOCAL_ONLY,
        reasoning_effort=ReasoningEffort.HIGH,
    )
    # The canonical selector genuinely ranks the remote candidate first.
    assert _canonical_auto_order(graph, request) == (
        "remote-a:cheap-remote",
        "local:pricey-local",
    )

    response = gateway.execute(request)

    assert response.model_id == "pricey-local"
    assert response.provider_id == "local"
    assert response.content == "local answer"
    assert remote.call_count == 0
    assert local.call_count == 1


def test_auto_selection_continues_past_a_candidate_without_an_adapter() -> None:
    graph, gateway, local, remote = _auto_runtime(register_remote_adapter=False)

    request = _request(
        model_id=None,
        selection_mode=ModelSelectionMode.AUTO,
        privacy=REMOTE_ALLOWED,
        reasoning_effort=ReasoningEffort.HIGH,
    )
    assert _canonical_auto_order(graph, request) == (
        "remote-a:cheap-remote",
        "local:pricey-local",
    )

    response = gateway.execute(request)

    assert response.model_id == "pricey-local"
    assert local.call_count == 1
    assert remote.call_count == 0


def test_auto_selection_continues_past_a_candidate_lacking_the_effort() -> None:
    graph, gateway, local, remote = _auto_runtime(
        remote_capabilities=ModelCapabilities(reasoning=True),
    )

    request = _request(
        model_id=None,
        selection_mode=ModelSelectionMode.AUTO,
        privacy=REMOTE_ALLOWED,
        reasoning_effort=ReasoningEffort.HIGH,
    )
    assert _canonical_auto_order(graph, request)[0] == "remote-a:cheap-remote"

    response = gateway.execute(request)

    assert response.model_id == "pricey-local"
    assert response.effective_reasoning_effort is ReasoningEffort.HIGH
    assert remote.call_count == 0
    assert local.call_count == 1


def test_auto_selection_exhaustion_is_a_deterministic_safe_failure() -> None:
    # Both canonical candidates are text-only models without an adapter, so
    # neither is executable: AUTO must fail closed safely and deterministically
    # without touching any provider.
    _graph, gateway, local, remote = _auto_runtime(register_remote_adapter=False)
    gateway = _auto_gateway(_graph)

    request = _request(
        model_id=None,
        selection_mode=ModelSelectionMode.AUTO,
        privacy=REMOTE_ALLOWED,
        reasoning_effort=ReasoningEffort.HIGH,
    )

    with pytest.raises(ModelGatewayError) as error:
        gateway.execute(request)

    assert error.value.code is ModelGatewayErrorCode.MODEL_NOT_FOUND
    assert error.value.retryable is False
    assert error.value.details["candidates_considered"] == 2
    assert remote.call_count == 0
    assert local.call_count == 0


def test_auto_selection_respects_canonical_order_exactly() -> None:
    """AUTO returns the first executable candidate in canonical order.

    The canonical ``lowest_cost`` order is remote ``cheap-remote`` (no adapter),
    then remote ``second-remote:cheap-another-remote`` (adapter present), then
    local ``pricey-local``.  AUTO must skip only the inexecutable head of that
    order and pick the very next canonical candidate -- never a re-ranked one.
    """

    graph, _gateway, local, remote = _auto_runtime()
    graph.providers.register(
        ProviderSpec(
            id="remote-b",
            provider_type="remote",
            api_style="chat_completions",
            base_url="https://remote-b.example/v1",
            availability="available",
        )
    )
    _register_auto_model(
        graph,
        "cheap-another-remote",
        provider_id="remote-b",
        input_cost="0.50",
        capabilities=ModelCapabilities(),
    )
    another_remote = InMemoryModelProviderAdapter("remote-b")
    another_remote.add_response(content="second remote answer")
    gateway = ModelGateway(
        provider_registry=graph.providers,
        model_catalog=graph.models,
        adapters=ModelProviderAdapterRegistry((local, another_remote)),
        privacy_gate=CanonicalPrivacyEgressGate(),
    )

    request = _request(
        model_id=None,
        selection_mode=ModelSelectionMode.AUTO,
        privacy=REMOTE_ALLOWED,
    )
    order = _canonical_auto_order(graph, request)
    assert order == (
        "remote-a:cheap-remote",
        "remote-b:cheap-another-remote",
        "local:pricey-local",
    )

    response = gateway.execute(request)

    # Never re-ranked: the second canonical candidate is the first executable one.
    assert response.model_id == "cheap-another-remote"
    assert response.provider_id == "remote-b"
    assert another_remote.call_count == 1
    assert local.call_count == 0
    assert remote.call_count == 0


# ── Remediation V2 MAJOR-01 — AUTO evaluates egress authority per candidate, so
#    a valid local candidate still executes when remote privacy metadata or a
#    privacy authority is absent.  Explicit remote selection stays stricter.


def _only_remote_runtime(
    *,
    privacy_gate: object = _DEFAULT_PRIVACY_GATE,
):
    """Compose two canonical remote candidates with no local candidate."""

    resolved_gate = (
        CanonicalPrivacyEgressGate()
        if privacy_gate is _DEFAULT_PRIVACY_GATE
        else privacy_gate
    )
    graph = build_canonical_graph()
    graph.providers.register(
        ProviderSpec(
            id="remote-b",
            provider_type="remote",
            api_style="chat_completions",
            base_url="https://remote-b.example/v1",
            availability="available",
        )
    )
    _register_auto_model(
        graph,
        "cheap-remote",
        provider_id="remote-a",
        input_cost="0.10",
        capabilities=AUTO_EFFORT_CAPABILITIES,
    )
    _register_auto_model(
        graph,
        "pricey-remote",
        provider_id="remote-b",
        input_cost="9.00",
        capabilities=AUTO_EFFORT_CAPABILITIES,
    )
    remote_a = InMemoryModelProviderAdapter(
        "remote-a", reasoning_effort_map={ReasoningEffort.HIGH: "thinking_budget_high"}
    )
    remote_a.add_response(content="remote a answer")
    remote_b = InMemoryModelProviderAdapter(
        "remote-b", reasoning_effort_map={ReasoningEffort.HIGH: "thinking_budget_high"}
    )
    remote_b.add_response(content="remote b answer")
    gateway = ModelGateway(
        provider_registry=graph.providers,
        model_catalog=graph.models,
        adapters=ModelProviderAdapterRegistry((remote_a, remote_b)),
        privacy_gate=resolved_gate,  # type: ignore[arg-type]
    )
    return graph, gateway, remote_a, remote_b


def test_auto_selection_reaches_a_local_candidate_without_privacy_metadata() -> None:
    """RED V2-A: AUTO remote-first/local-second with ``privacy=None``."""

    graph, gateway, local, remote = _auto_runtime()

    request = _request(
        model_id=None,
        selection_mode=ModelSelectionMode.AUTO,
        privacy=None,
        reasoning_effort=ReasoningEffort.HIGH,
    )
    # Canonical ordering is untouched: the remote candidate genuinely ranks first.
    assert _canonical_auto_order(graph, request) == (
        "remote-a:cheap-remote",
        "local:pricey-local",
    )

    response = gateway.execute(request)

    assert response.model_id == "pricey-local"
    assert response.provider_id == "local"
    assert response.content == "local answer"
    assert remote.call_count == 0
    assert local.call_count == 1


def test_auto_selection_reaches_a_local_candidate_without_a_privacy_authority() -> None:
    """RED V2-B: AUTO remote-first/local-second with no privacy gate at all."""

    graph, gateway, local, remote = _auto_runtime(privacy_gate=None)

    request = _request(
        model_id=None,
        selection_mode=ModelSelectionMode.AUTO,
        privacy=REMOTE_ALLOWED,
        reasoning_effort=ReasoningEffort.HIGH,
    )
    assert _canonical_auto_order(graph, request) == (
        "remote-a:cheap-remote",
        "local:pricey-local",
    )

    response = gateway.execute(request)

    assert response.model_id == "pricey-local"
    assert response.provider_id == "local"
    assert remote.call_count == 0
    assert local.call_count == 1


def test_explicit_remote_still_requires_privacy_metadata() -> None:
    """Regression V2-C: explicit remote + ``privacy=None`` stays fail-closed."""

    _graph, gateway, local, remote = _auto_runtime()

    with pytest.raises(ModelGatewayError) as error:
        gateway.execute(
            _request(
                model_id="remote-a:cheap-remote",
                privacy=None,
                reasoning_effort=ReasoningEffort.HIGH,
            )
        )

    assert error.value.code is ModelGatewayErrorCode.PRIVACY_DENIED
    assert remote.call_count == 0
    assert local.call_count == 0


def test_explicit_remote_still_requires_a_privacy_authority() -> None:
    """Regression V2-D: explicit remote with no privacy gate stays fail-closed."""

    _graph, gateway, local, remote = _auto_runtime(privacy_gate=None)

    with pytest.raises(ModelGatewayError) as error:
        gateway.execute(
            _request(
                model_id="remote-a:cheap-remote",
                privacy=REMOTE_ALLOWED,
                reasoning_effort=ReasoningEffort.HIGH,
            )
        )

    assert error.value.code is ModelGatewayErrorCode.PRIVACY_DENIED
    assert remote.call_count == 0
    assert local.call_count == 0


def test_auto_only_remote_still_fails_closed_without_privacy_metadata() -> None:
    """Regression V2-E: AUTO only-remote + ``privacy=None`` never egresses."""

    graph, gateway, remote_a, remote_b = _only_remote_runtime()

    request = _request(
        model_id=None,
        selection_mode=ModelSelectionMode.AUTO,
        privacy=None,
        reasoning_effort=ReasoningEffort.HIGH,
    )
    assert _canonical_auto_order(graph, request) == (
        "remote-a:cheap-remote",
        "remote-b:pricey-remote",
    )

    with pytest.raises(ModelGatewayError) as error:
        gateway.execute(request)

    assert error.value.code is ModelGatewayErrorCode.PRIVACY_DENIED
    assert remote_a.call_count == 0
    assert remote_b.call_count == 0


def test_auto_only_remote_still_fails_closed_without_a_privacy_gate() -> None:
    """Regression V2-F: AUTO only-remote with no privacy gate never egresses."""

    graph, gateway, remote_a, remote_b = _only_remote_runtime(privacy_gate=None)

    request = _request(
        model_id=None,
        selection_mode=ModelSelectionMode.AUTO,
        privacy=REMOTE_ALLOWED,
        reasoning_effort=ReasoningEffort.HIGH,
    )
    assert _canonical_auto_order(graph, request) == (
        "remote-a:cheap-remote",
        "remote-b:pricey-remote",
    )

    with pytest.raises(ModelGatewayError) as error:
        gateway.execute(request)

    assert error.value.code is ModelGatewayErrorCode.PRIVACY_DENIED
    assert remote_a.call_count == 0
    assert remote_b.call_count == 0
