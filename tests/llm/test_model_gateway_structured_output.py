"""Phase 11.21 — structured-output normalization tests.

The gateway translates a canonical structured-output requirement to the
provider boundary, normalizes the returned structured value deterministically
and fails safely when a required result is missing.  It does not become a second
semantic/domain validation system: schema conformance beyond the deterministic
contract check stays with the canonical Phase 7 validation authority.
"""

from __future__ import annotations

import json

import pytest

from kernel.llm.capabilities import ModelCapabilities
from kernel.llm.model_gateway_contracts import (
    ModelGatewayRequest,
    ModelInputPart,
    StructuredOutputRequirement,
    to_plain_json,
)
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode
from kernel.llm.model_provider_adapter import (
    InMemoryModelProviderAdapter,
    ProviderModelRequest,
    ProviderModelResponse,
)
from tests.llm.model_gateway_support import build_runtime

SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "integer"}},
    "required": ["answer"],
}

STRUCTURED_CAPABLE = ModelCapabilities(structured_output=True, json_schema=True)
STRUCTURED_ONLY = ModelCapabilities(structured_output=True)


def _request(
    requirement: StructuredOutputRequirement | None = None, **overrides: object
):
    values: dict[str, object] = {
        "request_id": "model-request-1",
        "model_id": "local:model-1",
        "input_parts": (ModelInputPart.text_part("answer precisely"),),
        "structured_output": requirement,
    }
    values.update(overrides)
    return ModelGatewayRequest(**values)  # type: ignore[arg-type]


def _runtime(capabilities: ModelCapabilities, adapter=None, **overrides: object):
    adapters = (adapter,) if adapter is not None else ()
    return build_runtime(
        capabilities=capabilities,
        adapters=adapters,
        **overrides,  # type: ignore[arg-type]
    )


def test_canonical_schema_reaches_the_adapter_and_round_trips() -> None:
    runtime = _runtime(STRUCTURED_CAPABLE)
    runtime.adapter().add_response(structured_output={"answer": 42})
    requirement = StructuredOutputRequirement(
        schema=SCHEMA, schema_id="cmm.answer", schema_version="1"
    )

    response = runtime.gateway.execute(_request(requirement))

    received = runtime.adapter().requests[0].structured_output
    assert received is not None
    assert received.schema_id == "cmm.answer"
    assert to_plain_json(received.schema) == SCHEMA
    assert dict(response.structured_output) == {"answer": 42}
    assert response.content == ""


def test_structured_output_serialization_is_deterministic() -> None:
    runtime = _runtime(STRUCTURED_CAPABLE)
    runtime.adapter().add_response(
        structured_output={"answer": 42, "notes": ["a", "b"]}
    )

    response = runtime.gateway.execute(
        _request(StructuredOutputRequirement(schema=SCHEMA))
    )

    payload = response.to_dict()
    assert payload["structured_output"] == {"answer": 42, "notes": ["a", "b"]}
    assert json.loads(json.dumps(payload))["structured_output"] == {
        "answer": 42,
        "notes": ["a", "b"],
    }


def test_structured_output_use_is_recorded_in_evidence() -> None:
    runtime = _runtime(STRUCTURED_CAPABLE)
    runtime.adapter().add_response(structured_output={"answer": 1})

    response = runtime.gateway.execute(
        _request(StructuredOutputRequirement(schema=SCHEMA))
    )

    assert response.facts is not None
    assert response.facts.structured_output_use is True


def test_structured_output_without_support_fails_before_provider_io() -> None:
    runtime = _runtime(ModelCapabilities())
    runtime.adapter().add_response(structured_output={"answer": 1})

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(StructuredOutputRequirement(schema=SCHEMA)))

    assert error.value.code is ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED
    assert error.value.retryable is False
    assert runtime.adapter().call_count == 0


def test_required_json_schema_needs_the_schema_capability() -> None:
    runtime = _runtime(STRUCTURED_ONLY)
    runtime.adapter().add_response(structured_output={"answer": 1})

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(StructuredOutputRequirement(schema=SCHEMA)))

    assert error.value.code is ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED
    assert runtime.adapter().call_count == 0


def test_structured_output_without_a_schema_only_needs_the_capability() -> None:
    runtime = _runtime(STRUCTURED_ONLY)
    runtime.adapter().add_response(structured_output={"answer": 1})

    response = runtime.gateway.execute(
        _request(StructuredOutputRequirement(schema_id="cmm.answer"))
    )

    assert dict(response.structured_output) == {"answer": 1}
    assert runtime.adapter().call_count == 1


def test_a_missing_required_structured_result_fails_safely() -> None:
    runtime = _runtime(STRUCTURED_CAPABLE)
    runtime.adapter().add_response(content="I could not comply")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(StructuredOutputRequirement(schema=SCHEMA)))

    assert error.value.code is ModelGatewayErrorCode.STRUCTURED_OUTPUT_INVALID
    assert error.value.retryable is False


def test_an_optional_structured_result_may_be_absent() -> None:
    runtime = _runtime(STRUCTURED_CAPABLE)
    runtime.adapter().add_response(content="plain text answer")

    response = runtime.gateway.execute(
        _request(StructuredOutputRequirement(schema=SCHEMA, required=False))
    )

    assert response.structured_output is None
    assert response.content == "plain text answer"


def test_structured_output_is_never_moved_into_text_content() -> None:
    runtime = _runtime(STRUCTURED_CAPABLE)
    runtime.adapter().add_response(structured_output={"answer": 7})

    response = runtime.gateway.execute(
        _request(StructuredOutputRequirement(schema=SCHEMA))
    )

    assert response.content == ""
    assert "answer" not in response.content


class _EmptyStructuredAdapter(InMemoryModelProviderAdapter):
    """Test adapter that answers without a structured value."""

    def execute(
        self,
        request: ProviderModelRequest,
        *,
        cancellation: object | None = None,
    ) -> ProviderModelResponse:
        return ProviderModelResponse(content="no structured value")


def test_structured_result_absence_is_detected_for_every_adapter() -> None:
    adapter = _EmptyStructuredAdapter("local")
    runtime = _runtime(STRUCTURED_CAPABLE, adapter=adapter)

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(StructuredOutputRequirement(schema=SCHEMA)))

    assert error.value.code is ModelGatewayErrorCode.STRUCTURED_OUTPUT_INVALID


def test_no_structured_requirement_sends_none_to_the_adapter() -> None:
    runtime = _runtime(STRUCTURED_CAPABLE)
    runtime.adapter().add_response(content="plain")

    runtime.gateway.execute(_request())

    assert runtime.adapter().requests[0].structured_output is None
