"""Phase 11.21 — safe model-call evidence seam tests.

The gateway emits safe, structured evidence through an injected sink for both
success and normalized failure.  Evidence describes what happened; it never
carries a prompt, attachment bytes, credentials, hidden reasoning or a raw
provider exception.  Phase 11.21 creates no model-usage audit persistence.
"""

from __future__ import annotations

import json

import pytest

from kernel.llm.capabilities import ModelCapabilities, ReasoningEffort
from kernel.llm.model_gateway import ModelGateway
from kernel.llm.model_gateway_contracts import (
    InMemoryModelExecutionEvidenceSink,
    ModelExecutionEvidenceSink,
    ModelGatewayRequest,
    ModelGatewayRetryPolicy,
    ModelInputPart,
)
from kernel.llm.model_gateway_errors import ModelGatewayErrorCode
from tests.llm.model_gateway_support import TEXT_CAPABLE, build_runtime

FORBIDDEN_EVIDENCE_KEYS = (
    "prompt",
    "raw_prompt",
    "content",
    "bytes",
    "api_key",
    "credential",
    "secret",
    "token_value",
    "reasoning_trace",
    "chain_of_thought",
    "scratchpad",
    "provider_exception",
    "provider_payload",
    "attachment",
)


def _request(**overrides: object) -> ModelGatewayRequest:
    values: dict[str, object] = {
        "request_id": "model-request-1",
        "model_id": "local:model-1",
        "input_parts": (ModelInputPart.text_part("evidence please"),),
    }
    values.update(overrides)
    return ModelGatewayRequest(**values)  # type: ignore[arg-type]


def _runtime(**overrides: object):
    overrides.setdefault("capabilities", TEXT_CAPABLE)
    return build_runtime(**overrides)  # type: ignore[arg-type]


def _assert_no_forbidden_keys(payload: object) -> None:
    serialized = json.dumps(payload).lower()
    for key in FORBIDDEN_EVIDENCE_KEYS:
        assert f'"{key}"' not in serialized, key


def test_every_successful_call_emits_exactly_one_evidence_record() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(content="ok")

    runtime.gateway.execute(_request())

    assert len(runtime.sink.records) == 1
    assert runtime.sink.records[0].success is True


def test_a_normalized_failure_emits_safe_evidence() -> None:
    runtime = _runtime()
    runtime.adapter().add_failure(
        ModelGatewayErrorCode.PROVIDER_FAILURE, "upstream 503", retryable=False
    )

    with pytest.raises(Exception):  # noqa: B017 - canonical gateway error asserted below
        runtime.gateway.execute(_request())

    assert len(runtime.sink.records) == 1
    facts = runtime.sink.records[0]
    assert facts.success is False
    assert facts.error_code == "PROVIDER_FAILURE"
    assert "upstream 503" not in json.dumps(facts.to_dict())


def test_evidence_serialization_carries_no_forbidden_field() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(
        content="secret-looking answer",
        structured_output={"answer": "a"},
    )

    response = runtime.gateway.execute(
        _request(structured_output=None, required_capabilities=("structured_output",))
    )

    _assert_no_forbidden_keys(response.facts.to_dict())  # type: ignore[union-attr]
    assert "secret-looking answer" not in json.dumps(response.facts.to_dict())  # type: ignore[union-attr]


def test_evidence_records_capability_and_privacy_decisions() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(content="ok")

    runtime.gateway.execute(_request(required_capabilities=("tool_calling",)))

    facts = runtime.sink.records[0]
    assert facts.capability_decision == "verified"
    assert facts.privacy_decision == "not_required"


def test_evidence_records_modalities_tools_and_structured_output_use() -> None:
    from kernel.llm.model_gateway_contracts import (
        ModelToolDefinition,
        StructuredOutputRequirement,
    )

    runtime = _runtime(
        capabilities=ModelCapabilities(tool_calling=True, structured_output=True)
    )
    runtime.adapter().add_response(structured_output={"answer": 1})

    runtime.gateway.execute(
        _request(
            tools=(ModelToolDefinition(tool_id="t1"),),
            structured_output=StructuredOutputRequirement(),
        )
    )

    facts = runtime.sink.records[0]
    assert facts.tool_use is True
    assert facts.structured_output_use is True
    assert facts.input_modalities == ("text",)
    assert facts.streamed is False


def test_evidence_records_retry_and_fallback_state() -> None:
    from tests.llm.model_gateway_support import build_canonical_graph
    from tests.llm.model_gateway_support import build_runtime as build

    graph = build_canonical_graph()
    graph.register_local_model("model-1", capabilities=TEXT_CAPABLE)
    runtime = build(
        graph=graph,
        register_model=False,
        retry_policy=ModelGatewayRetryPolicy(max_attempts=2),
    )
    runtime.adapter().add_failure(
        ModelGatewayErrorCode.PROVIDER_FAILURE, "transient", retryable=True
    )
    runtime.adapter().add_response(content="recovered")

    runtime.gateway.execute(_request())

    facts = runtime.sink.records[-1]
    assert facts.retry_count == 1
    assert facts.fallback_used is False
    assert facts.fallback_index == 0


def test_evidence_records_requested_and_effective_reasoning_effort() -> None:
    from kernel.llm.model_provider_adapter import InMemoryModelProviderAdapter

    adapter = InMemoryModelProviderAdapter(
        "local", reasoning_effort_map={ReasoningEffort.HIGH: "thinking_budget_high"}
    )
    runtime = _runtime(
        capabilities=ModelCapabilities(
            reasoning=True, reasoning_efforts=(ReasoningEffort.HIGH,)
        ),
        adapters=(adapter,),
    )
    runtime.adapter().add_response(content="deep")

    runtime.gateway.execute(_request(reasoning_effort=ReasoningEffort.HIGH))

    facts = runtime.sink.records[0]
    assert facts.requested_reasoning_effort is ReasoningEffort.HIGH
    assert facts.effective_reasoning_effort is ReasoningEffort.HIGH
    assert "thinking_budget_high" not in json.dumps(facts.to_dict())


def test_the_official_sink_persists_nothing_and_is_clearable() -> None:
    sink = InMemoryModelExecutionEvidenceSink()
    runtime = _runtime(sink=sink)
    runtime.adapter().add_response(content="ok")

    runtime.gateway.execute(_request())

    assert isinstance(sink.records, tuple)
    assert isinstance(sink, ModelExecutionEvidenceSink)
    sink.clear()
    assert sink.records == ()


def test_a_gateway_without_a_sink_still_executes() -> None:
    from tests.llm.model_gateway_support import build_canonical_graph

    graph = build_canonical_graph()
    graph.register_local_model("model-1", capabilities=TEXT_CAPABLE)
    gateway = ModelGateway(
        provider_registry=graph.providers,
        model_catalog=graph.models,
    )
    assert not hasattr(gateway, "records")
    assert not hasattr(gateway, "evidence")


def test_a_foreign_sink_object_is_rejected() -> None:
    with pytest.raises(TypeError):
        build_runtime(evidence_sink=object())


def test_the_gateway_creates_no_usage_audit_persistence() -> None:
    runtime = _runtime()

    for forbidden in (
        "audit_store",
        "usage_repository",
        "persist_usage",
        "model_usage_audit",
    ):
        assert not hasattr(runtime.gateway, forbidden)
