"""Phase 11.21 — ``AT-DP-121`` connected acceptance.

Connected acceptance for ``DP-121`` (Canonical Provider-Independent Model
Gateway) under requirement ``F11-020``.  It uses the real canonical Phase 11.34
``ProviderRegistry`` and ``ModelCatalog``, the real Phase 11.1 composition root,
the real :class:`~kernel.llm.model_gateway.ModelGateway` and the official
in-memory provider adapter, so the demonstrated behaviour is canonical rather
than a chain of isolated mocks.

Scenarios A to M mirror the frozen design section 24 and the implementation plan
Task 19.  Inherited acceptances (Scenario L) are executed by the same gate
command as this file and their traceability is asserted here.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from cmm.agent_runtime.model_egress_privacy_adapter import CanonicalPrivacyEgressGate
from cmm.agent_runtime.model_fallback_gateway_adapter import (
    ModelGatewayFallbackPlanner,
)
from cmm.cognitive.privacy import (
    PrivacyMetadata,
    PrivacyOperation,
    PrivacyOperationContext,
    PrivacyPolicy,
    ProcessingLocation,
    evaluate_privacy_operation,
)
from cmm.platform.canonical import model_gateway_binding, provider_registry_binding
from cmm.platform.configuration import CompositionConfiguration
from cmm.platform.container import ApplicationContainer, ContainerState
from cmm.platform.modules import StaticCompositionModule
from kernel.llm.capabilities import ModelCapabilities, ReasoningEffort
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_gateway import ModelGateway
from kernel.llm.model_gateway_contracts import (
    InMemoryModelExecutionEvidenceSink,
    InputPartKind,
    ModelGatewayRequest,
    ModelInputPart,
    ModelStreamEventType,
    ModelToolCall,
    ModelToolDefinition,
    ModelUsage,
    StructuredOutputRequirement,
)
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode
from kernel.llm.model_provider_adapter import (
    InMemoryModelProviderAdapter,
    ModelProviderAdapterRegistry,
)
from kernel.llm.model_streaming import ModelCallCancellation
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec
from tests.llm.model_gateway_support import (
    PDF_BYTES,
    PNG_BYTES,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_ROOTS = ("kernel", "cmm", "cmm_agent")

REASONING_MAP = {
    ReasoningEffort.NONE: "reasoning_off",
    ReasoningEffort.LOW: "thinking_budget_low",
    ReasoningEffort.MEDIUM: "thinking_budget_medium",
    ReasoningEffort.HIGH: "thinking_budget_high",
    ReasoningEffort.EXTRA_HIGH: "thinking_budget_max",
}

FULL_CAPABILITIES = ModelCapabilities(
    reasoning=True,
    reasoning_efforts=(
        ReasoningEffort.LOW,
        ReasoningEffort.MEDIUM,
        ReasoningEffort.HIGH,
        ReasoningEffort.EXTRA_HIGH,
    ),
    tool_calling=True,
    structured_output=True,
    json_schema=True,
    vision=True,
    streaming=True,
    document_media_types=("application/pdf", "text/plain", "text/markdown"),
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


class AcceptanceRuntime:
    """A fully composed canonical runtime for connected acceptance."""

    def __init__(self) -> None:
        self.providers = ProviderRegistry()
        self.providers.register(
            ProviderSpec(
                id="local",
                provider_type="local",
                api_style="chat_completions",
                availability="available",
            )
        )
        self.providers.register(
            ProviderSpec(
                id="remote-a",
                provider_type="remote",
                api_style="chat_completions",
                base_url="https://remote-a.example/v1",
                availability="available",
            )
        )
        self.models = ModelCatalog(self.providers)
        self.models.register(
            ModelSpec(
                id="multimodal-1",
                provider_id="local",
                context_window=200000,
                capabilities=FULL_CAPABILITIES,
                availability="available",
                input_cost_per_million=Decimal("1.50"),
                output_cost_per_million=Decimal("6.00"),
                cached_input_cost_per_million=Decimal("0.15"),
            )
        )
        self.models.register(
            ModelSpec(
                id="text-only-1",
                provider_id="local",
                context_window=32768,
                capabilities=ModelCapabilities(),
                availability="available",
            )
        )
        self.models.register(
            ModelSpec(
                id="remote-1",
                provider_id="remote-a",
                context_window=32768,
                capabilities=FULL_CAPABILITIES,
                availability="available",
            )
        )
        self.models.register(
            ModelSpec(
                id="fallback-1",
                provider_id="local",
                context_window=32768,
                capabilities=FULL_CAPABILITIES,
                availability="available",
            )
        )
        self.local = InMemoryModelProviderAdapter(
            "local",
            reasoning_effort_map=REASONING_MAP,
            derive_content_from_input=True,
        )
        self.remote = InMemoryModelProviderAdapter(
            "remote-a", reasoning_effort_map=REASONING_MAP
        )
        self.sink = InMemoryModelExecutionEvidenceSink()
        self.privacy = CanonicalPrivacyEgressGate()
        self.gateway = ModelGateway(
            provider_registry=self.providers,
            model_catalog=self.models,
            adapters=ModelProviderAdapterRegistry((self.local, self.remote)),
            privacy_gate=self.privacy,
            evidence_sink=self.sink,
            fallback_planner=ModelGatewayFallbackPlanner(),
        )


@pytest.fixture
def runtime() -> AcceptanceRuntime:
    return AcceptanceRuntime()


def _request(**overrides: object) -> ModelGatewayRequest:
    values: dict[str, object] = {
        "request_id": "model-request-1",
        "model_id": "local:multimodal-1",
        "input_parts": (ModelInputPart.text_part("hola"),),
    }
    values.update(overrides)
    return ModelGatewayRequest(**values)  # type: ignore[arg-type]


# ── Scenario A — canonical authority identity ───────────────────────────────


def test_scenario_a_canonical_authority_identity(runtime: AcceptanceRuntime) -> None:
    module = StaticCompositionModule(
        "canonical",
        (
            provider_registry_binding(runtime.providers),
            model_gateway_binding(runtime.gateway),
        ),
    )
    container = ApplicationContainer.build(
        CompositionConfiguration(
            required_services=("model.gateway", "provider.registry"),
            enabled_modules=("canonical",),
        ),
        modules=(module,),
    )

    assert container.state is ContainerState.READY
    bound_gateway = container.get_service("model.gateway")
    bound_registry = container.get_service("provider.registry")
    assert bound_gateway is runtime.gateway
    assert bound_registry is runtime.providers
    assert bound_gateway.provider_registry is runtime.providers
    assert bound_gateway.model_catalog is runtime.models
    assert bound_gateway.model_catalog.provider_registry is runtime.providers
    assert isinstance(runtime.providers, ProviderRegistry)
    assert isinstance(runtime.models, ModelCatalog)


# ── Scenario B — explicit reasoning effort end to end ───────────────────────


def test_scenario_b_reasoning_effort_end_to_end(runtime: AcceptanceRuntime) -> None:
    runtime.local.add_response(content="deep answer")

    response = runtime.gateway.execute(_request(reasoning_effort=ReasoningEffort.HIGH))

    assert runtime.local.requests[0].reasoning_effort is ReasoningEffort.HIGH
    assert runtime.local.native_efforts == ("thinking_budget_high",)
    assert response.effective_reasoning_effort is ReasoningEffort.HIGH
    assert response.facts is not None
    assert response.facts.requested_reasoning_effort is ReasoningEffort.HIGH
    assert response.facts.effective_reasoning_effort is ReasoningEffort.HIGH
    assert response.reasoning_used is True


def test_scenario_b_unsupported_effort_stops_before_provider_io(
    runtime: AcceptanceRuntime,
) -> None:
    runtime.local.add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(
                model_id="local:text-only-1",
                reasoning_effort=ReasoningEffort.EXTRA_HIGH,
            )
        )

    assert error.value.code is ModelGatewayErrorCode.UNSUPPORTED_REASONING_EFFORT
    assert runtime.local.call_count == 0


# ── Scenario C — real image input ───────────────────────────────────────────


def test_scenario_c_real_image_content_reaches_the_provider(
    runtime: AcceptanceRuntime,
) -> None:
    runtime.local.add_response(content="ignored")
    image = ModelInputPart.image_part(PNG_BYTES, "image/png", display_name="pixel.png")

    response = runtime.gateway.execute(
        _request(input_parts=(ModelInputPart.text_part("describe"), image))
    )

    fingerprints = runtime.local.received_input_fingerprints[0]
    assert fingerprints[1] == (
        "image",
        len(PNG_BYTES),
        hashlib.sha256(PNG_BYTES).hexdigest(),
    )
    expected = hashlib.sha256(
        "|".join(entry[2] for entry in fingerprints).encode("utf-8")
    ).hexdigest()
    assert response.content == f"echo:{expected}"


def test_scenario_c_filename_only_evidence_is_insufficient(
    runtime: AcceptanceRuntime,
) -> None:
    with pytest.raises(ValueError):
        ModelInputPart(
            kind=InputPartKind.IMAGE,
            media_type="image/png",
            display_name="pixel.png",
        )
    with pytest.raises(ValueError):
        ModelInputPart.image_part(b"", "image/png")

    runtime.local.add_response(content="never")
    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(
                model_id="local:text-only-1",
                input_parts=(
                    ModelInputPart.text_part("describe"),
                    ModelInputPart.image_part(PNG_BYTES, "image/png"),
                ),
            )
        )
    assert error.value.code is ModelGatewayErrorCode.INPUT_MODALITY_UNSUPPORTED
    assert runtime.local.call_count == 0


# ── Scenario D — real PDF/document input ────────────────────────────────────


def test_scenario_d_real_pdf_content_reaches_the_provider(
    runtime: AcceptanceRuntime,
) -> None:
    runtime.local.add_response(content="ignored")

    runtime.gateway.execute(
        _request(
            input_parts=(ModelInputPart.document_part(PDF_BYTES, "application/pdf"),)
        )
    )

    received = runtime.local.requests[0].input_parts[0]
    assert received.kind.value == "document"
    assert received.content == PDF_BYTES
    assert received.content_digest == hashlib.sha256(PDF_BYTES).hexdigest()
    assert received.text is None


def test_scenario_d_unsupported_document_model_fails_before_io(
    runtime: AcceptanceRuntime,
) -> None:
    runtime.local.add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(
                model_id="local:text-only-1",
                input_parts=(
                    ModelInputPart.document_part(PDF_BYTES, "application/pdf"),
                ),
            )
        )

    assert error.value.code is ModelGatewayErrorCode.INPUT_MODALITY_UNSUPPORTED
    assert runtime.local.call_count == 0


# ── Scenario E — structured output ──────────────────────────────────────────


def test_scenario_e_structured_output_round_trips(runtime: AcceptanceRuntime) -> None:
    runtime.local.add_response(structured_output={"answer": 42})
    requirement = StructuredOutputRequirement(
        schema={"type": "object", "properties": {"answer": {"type": "integer"}}},
        schema_id="cmm.answer",
    )

    response = runtime.gateway.execute(_request(structured_output=requirement))

    assert runtime.local.requests[0].structured_output is not None
    assert dict(response.structured_output) == {"answer": 42}
    assert json.loads(json.dumps(response.to_dict()))["structured_output"] == {
        "answer": 42
    }


def test_scenario_e_malformed_structured_output_fails_safely(
    runtime: AcceptanceRuntime,
) -> None:
    runtime.local.add_response(content="not structured")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(structured_output=StructuredOutputRequirement())
        )

    assert error.value.code is ModelGatewayErrorCode.STRUCTURED_OUTPUT_INVALID


# ── Scenario F — tool calling without execution ─────────────────────────────


def test_scenario_f_tool_call_is_normalized_and_never_executed(
    runtime: AcceptanceRuntime,
) -> None:
    tool = ModelToolDefinition(
        tool_id="cmm.ops.list_files",
        description="List files in an approved workspace",
        input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
    )
    runtime.local.add_response(
        content="",
        tool_calls=(
            ModelToolCall(
                call_id="call-1",
                tool_id="cmm.ops.list_files",
                arguments={"path": "."},
            ),
        ),
    )

    response = runtime.gateway.execute(_request(tools=(tool,)))

    assert runtime.local.requests[0].tools[0].tool_id == "cmm.ops.list_files"
    assert response.tool_calls[0].call_id == "call-1"
    assert response.facts is not None
    assert response.facts.tool_use is True
    assert runtime.local.call_count == 1
    for forbidden in ("execute_tool", "invoke_tool", "executor"):
        assert not hasattr(runtime.gateway, forbidden)


# ── Scenario G — provider token streaming ───────────────────────────────────


def test_scenario_g_stream_is_ordered_with_one_terminal(
    runtime: AcceptanceRuntime,
) -> None:
    runtime.local.add_stream(
        ("ho", "la"), usage=ModelUsage(input_tokens=4, output_tokens=2)
    )

    events = list(runtime.gateway.stream(_request()))

    assert [event.event_type for event in events] == [
        ModelStreamEventType.STARTED,
        ModelStreamEventType.CONTENT_DELTA,
        ModelStreamEventType.CONTENT_DELTA,
        ModelStreamEventType.USAGE,
        ModelStreamEventType.COMPLETED,
    ]
    assert [event.sequence for event in events] == [0, 1, 2, 3, 4]
    assert sum(event.is_terminal for event in events) == 1
    assert events[-1].response is not None
    assert events[-1].response.content.startswith("echo:")
    for event in events:
        for forbidden in ("reasoning_trace", "chain_of_thought", "scratchpad"):
            assert forbidden not in event.to_dict()


# ── Scenario H — cancellation ───────────────────────────────────────────────


def test_scenario_h_cancellation_yields_one_terminal_and_stops_content(
    runtime: AcceptanceRuntime,
) -> None:
    runtime.local.add_stream(("a", "b", "c", "d"))
    cancellation = ModelCallCancellation()

    received: list[ModelStreamEventType] = []
    deltas: list[str] = []
    for event in runtime.gateway.stream(_request(), cancellation=cancellation):
        received.append(event.event_type)
        if event.event_type is ModelStreamEventType.CONTENT_DELTA:
            deltas.append(event.content_delta or "")
            cancellation.cancel("stop")

    assert received[-1] is ModelStreamEventType.CANCELLED
    assert received.count(ModelStreamEventType.CANCELLED) == 1
    assert deltas == ["a"]
    assert runtime.sink.records[-1].cancelled is True


# ── Scenario I — canonical privacy ──────────────────────────────────────────


def test_scenario_i_local_only_blocks_remote_and_allows_local(
    runtime: AcceptanceRuntime,
) -> None:
    runtime.remote.add_response(content="never")
    runtime.local.add_response(content="local answer")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(model_id="remote-a:remote-1", privacy=LOCAL_ONLY)
        )

    assert error.value.code is ModelGatewayErrorCode.PRIVACY_DENIED
    assert runtime.remote.call_count == 0

    response = runtime.gateway.execute(_request(privacy=LOCAL_ONLY))

    assert response.content.startswith("echo:")
    assert runtime.local.call_count == 1


def test_scenario_i_approval_cannot_widen_a_privacy_denial(
    runtime: AcceptanceRuntime,
) -> None:
    approved = evaluate_privacy_operation(
        LOCAL_ONLY,
        PrivacyOperation.TRANSMIT_TO_PROVIDER,
        PrivacyOperationContext(
            provider_id="remote-a",
            processing_location=ProcessingLocation.REMOTE,
            approval_granted=True,
        ),
    )

    assert approved.allowed is False
    assert approved.reason_code == "remote_blocked_local_only"

    runtime.remote.add_response(content="never")
    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(model_id="remote-a:remote-1", privacy=LOCAL_ONLY)
        )
    assert error.value.code is ModelGatewayErrorCode.PRIVACY_DENIED
    assert runtime.remote.call_count == 0


# ── Scenario J — fallback safety ────────────────────────────────────────────


def test_scenario_j_authorized_compatible_fallback_succeeds(
    runtime: AcceptanceRuntime,
) -> None:
    runtime.local.add_failure(
        ModelGatewayErrorCode.PROVIDER_FAILURE, "transient", retryable=True
    )
    runtime.local.add_response(content="fallback answer")

    response = runtime.gateway.execute(
        _request(
            model_id="local:text-only-1",
            fallback_model_ids=("local:multimodal-1",),
            reasoning_effort=ReasoningEffort.DEFAULT,
        )
    )

    assert response.content.startswith("echo:")
    assert response.model_id == "multimodal-1"
    assert response.facts is not None
    assert response.facts.fallback_used is True
    assert response.facts.fallback_index == 1
    assert runtime.local.call_count == 2


def test_scenario_j_incompatible_fallback_does_not_execute(
    runtime: AcceptanceRuntime,
) -> None:
    runtime.local.add_failure(
        ModelGatewayErrorCode.PROVIDER_FAILURE, "transient", retryable=True
    )

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(
                input_parts=(
                    ModelInputPart.text_part("describe"),
                    ModelInputPart.image_part(PNG_BYTES, "image/png"),
                ),
                fallback_model_ids=("local:text-only-1",),
            )
        )

    assert error.value.code is ModelGatewayErrorCode.FALLBACK_EXHAUSTED
    assert runtime.local.call_count == 1


def test_scenario_j_remote_fallback_is_blocked_under_local_only(
    runtime: AcceptanceRuntime,
) -> None:
    runtime.local.add_failure(
        ModelGatewayErrorCode.PROVIDER_FAILURE, "transient", retryable=True
    )
    runtime.remote.add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(
                model_id="local:text-only-1",
                privacy=LOCAL_ONLY,
                fallback_model_ids=("remote-a:remote-1",),
            )
        )

    assert error.value.code is ModelGatewayErrorCode.FALLBACK_EXHAUSTED
    assert runtime.remote.call_count == 0


def test_scenario_j_explicit_model_without_authorization_never_changes(
    runtime: AcceptanceRuntime,
) -> None:
    runtime.local.add_failure(
        ModelGatewayErrorCode.PROVIDER_FAILURE, "transient", retryable=True
    )

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(
            _request(model_id="local:text-only-1", fallback_model_ids=())
        )

    assert error.value.code is ModelGatewayErrorCode.PROVIDER_FAILURE
    assert runtime.local.requests[0].model_id == "text-only-1"


# ── Scenario K — accounting truth ───────────────────────────────────────────


def test_scenario_k_provider_usage_is_normalized_and_cost_is_derived(
    runtime: AcceptanceRuntime,
) -> None:
    runtime.local.add_response(
        usage=ModelUsage(
            input_tokens=1000000, output_tokens=500000, cached_tokens=100000
        ),
        finish_reason="stop",
    )

    response = runtime.gateway.execute(_request())

    assert response.usage.input_tokens == 1000000
    assert response.usage.output_tokens == 500000
    assert response.usage.cached_tokens == 100000
    assert response.usage.cost_source == "catalog_derived"
    assert response.usage.cost == Decimal("4.36500000")
    assert response.finish_reason == "stop"
    assert response.facts is not None
    assert response.facts.latency_ms is not None


def test_scenario_k_absent_metrics_remain_unknown(runtime: AcceptanceRuntime) -> None:
    runtime.local.add_response(content="ok")

    response = runtime.gateway.execute(_request())

    assert response.usage.input_tokens is None
    assert response.usage.output_tokens is None
    assert response.usage.cached_tokens is None
    assert response.usage.cost is None
    assert response.usage.cost_source is None
    assert response.usage.total_tokens is None


# ── Scenario L — inherited acceptance traceability ──────────────────────────


@pytest.mark.parametrize(
    "relative_path",
    [
        "tests/llm/test_provider_registry_dp134_acceptance.py",
        "tests/platform/test_phase11_1_dp101_acceptance.py",
        "tests/orchestration/test_phase11_2_dp102_acceptance.py",
        "tests/application/test_phase11_3_dp103_acceptance.py",
        "tests/cli/test_phase11_4_dp104_acceptance.py",
        "tests/conversation/test_phase11_5_dp105_acceptance.py",
    ],
)
def test_scenario_l_inherited_acceptance_modules_are_intact(
    relative_path: str,
) -> None:
    path = REPO_ROOT / relative_path
    assert path.exists(), relative_path
    ast.parse(path.read_text(encoding="utf-8"))


def test_scenario_l_inherited_acceptances_are_not_redefined_here() -> None:
    """This acceptance composes canonical owners; it never restates them."""

    tree = ast.parse(
        (REPO_ROOT / "tests/llm/test_phase11_21_dp121_acceptance.py").read_text(
            encoding="utf-8"
        )
    )
    classes = {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}
    functions = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }

    assert classes.isdisjoint({"ProviderRegistry", "ModelCatalog"})
    assert "evaluate_privacy_operation" not in functions


# ── Scenario M — anti-fragmentation ─────────────────────────────────────────


def test_scenario_m_no_parallel_canonical_authority_exists() -> None:
    authorities = {
        "ProviderRegistry": "kernel/llm/provider_registry.py",
        "ModelCatalog": "kernel/llm/model_catalog.py",
        "ModelRouter": "kernel/llm/model_router.py",
    }
    production = [
        path for root in PRODUCTION_ROOTS for path in (REPO_ROOT / root).rglob("*.py")
    ]
    for authority, canonical in authorities.items():
        pattern = re.compile(rf"^class {authority}\b", re.MULTILINE)
        found = {
            str(path.relative_to(REPO_ROOT))
            for path in production
            if pattern.search(path.read_text(encoding="utf-8"))
        }
        assert found == {canonical}, authority

    for forbidden in (
        "cmm/provider_registry.py",
        "cmm/model_catalog.py",
        "cmm/model_router.py",
        "cmm/model_runtime.py",
        "cmm/model_store.py",
        "kernel/llm/privacy.py",
        "kernel/llm/validation_engine.py",
        "kernel/llm/tool_executor.py",
        "kernel/llm/conversation_store.py",
        "kernel/llm/session_store.py",
    ):
        assert not (REPO_ROOT / forbidden).exists(), forbidden


def test_scenario_m_the_gateway_owns_no_other_authority(
    runtime: AcceptanceRuntime,
) -> None:
    gateway = runtime.gateway

    for forbidden in (
        "register_provider",
        "register_model",
        "evaluate_privacy_operation",
        "validate",
        "execute_tool",
        "create_session",
        "persist_conversation",
        "run_workflow",
    ):
        assert not hasattr(gateway, forbidden), forbidden


def test_scenario_m_exactly_one_gateway_service_is_composed() -> None:
    runtime = AcceptanceRuntime()
    module = StaticCompositionModule(
        "canonical",
        (
            provider_registry_binding(runtime.providers),
            model_gateway_binding(runtime.gateway),
        ),
    )
    container = ApplicationContainer.build(
        CompositionConfiguration(
            required_services=("model.gateway", "provider.registry"),
            enabled_modules=("canonical",),
        ),
        modules=(module,),
    )

    gateway_services = [
        entry.service_id
        for entry in container.snapshot().services
        if entry.service_id == "model.gateway"
    ]
    assert gateway_services == ["model.gateway"]
    assert container.get_service("model.gateway") is runtime.gateway


def test_scenario_m_no_model_usage_audit_or_event_bus_is_created() -> None:
    for forbidden in (
        "cmm/model_usage_audit.py",
        "kernel/llm/model_event_bus.py",
        "kernel/llm/model_store.py",
        "cmm/model_gateway_event_bus.py",
    ):
        assert not (REPO_ROOT / forbidden).exists(), forbidden
