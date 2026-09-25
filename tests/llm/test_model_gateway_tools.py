"""Phase 11.21 — tool-call normalization tests.

The gateway normalizes tool declarations and model-generated tool calls.  It
never executes a tool, and a provider tool call grants no authority: the
canonical tool call carries no permission, approval or execution state.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from kernel.llm.capabilities import ModelCapabilities
from kernel.llm.model_gateway_contracts import (
    ModelGatewayRequest,
    ModelInputPart,
    ModelToolCall,
    ModelToolDefinition,
)
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode
from tests.llm.model_gateway_support import build_runtime

TOOL_CAPABLE = ModelCapabilities(tool_calling=True)

LIST_FILES = ModelToolDefinition(
    tool_id="cmm.ops.list_files",
    description="List files in an approved workspace",
    input_schema={
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
)


def _request(
    tools: tuple[ModelToolDefinition, ...] = (LIST_FILES,),
    **overrides: object,
) -> ModelGatewayRequest:
    values: dict[str, object] = {
        "request_id": "model-request-1",
        "model_id": "local:model-1",
        "input_parts": (ModelInputPart.text_part("list the workspace"),),
        "tools": tools,
    }
    values.update(overrides)
    return ModelGatewayRequest(**values)  # type: ignore[arg-type]


def _runtime(capabilities: ModelCapabilities = TOOL_CAPABLE, **overrides: object):
    return build_runtime(capabilities=capabilities, **overrides)  # type: ignore[arg-type]


def test_canonical_tool_definitions_reach_the_adapter_unchanged() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(content="ok")

    runtime.gateway.execute(_request())

    assert runtime.adapter().requests[0].tools == (LIST_FILES,)
    assert (
        runtime.adapter().requests[0].tools[0].input_schema == LIST_FILES.input_schema
    )


def test_tool_calling_capability_is_required_before_provider_io() -> None:
    runtime = _runtime(ModelCapabilities())
    runtime.adapter().add_response(content="never")

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request())

    assert error.value.code is ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED
    assert error.value.retryable is False
    assert runtime.adapter().call_count == 0


def test_provider_tool_call_is_normalized() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(
        content="",
        tool_calls=(
            ModelToolCall(
                call_id="call-1",
                tool_id="cmm.ops.list_files",
                arguments={"path": "."},
            ),
        ),
    )

    response = runtime.gateway.execute(_request())

    assert len(response.tool_calls) == 1
    call = response.tool_calls[0]
    assert call.call_id == "call-1"
    assert call.tool_id == "cmm.ops.list_files"
    assert dict(call.arguments) == {"path": "."}
    assert response.facts is not None
    assert response.facts.tool_use is True


def test_tool_call_serialization_is_safe_and_complete() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(
        content="",
        tool_calls=(
            ModelToolCall(call_id="call-1", tool_id="t", arguments={"path": "."}),
        ),
    )

    payload = runtime.gateway.execute(_request()).to_dict()

    assert payload["tool_calls"] == [
        {"call_id": "call-1", "tool_id": "t", "arguments": {"path": "."}}
    ]
    for forbidden in ("permission", "granted", "approved", "authority", "executed"):
        assert forbidden not in json.dumps(payload["tool_calls"])


def test_a_tool_call_is_never_text_content() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(
        content="",
        tool_calls=(ModelToolCall(call_id="call-1", tool_id="t"),),
    )

    response = runtime.gateway.execute(_request())

    assert response.content == ""
    assert response.tool_calls != ()


def test_an_unsolicited_tool_call_fails_closed() -> None:
    runtime = _runtime(ModelCapabilities(tool_calling=True))
    runtime.adapter().add_response(
        content="",
        tool_calls=(ModelToolCall(call_id="call-1", tool_id="t"),),
    )

    with pytest.raises(ModelGatewayError) as error:
        runtime.gateway.execute(_request(tools=()))

    assert error.value.code is ModelGatewayErrorCode.TOOL_CALL_INVALID
    assert error.value.retryable is False


def test_an_undeclared_tool_id_still_grants_no_authority() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(
        content="",
        tool_calls=(ModelToolCall(call_id="call-1", tool_id="undeclared.tool"),),
    )

    response = runtime.gateway.execute(_request())

    assert response.tool_calls[0].tool_id == "undeclared.tool"
    assert {field.name for field in dataclasses.fields(ModelToolCall)} == {
        "call_id",
        "tool_id",
        "arguments",
    }


def test_tool_declarations_carry_no_executable_callback() -> None:
    field_names = {field.name for field in dataclasses.fields(ModelToolDefinition)}

    assert field_names == {"tool_id", "description", "input_schema"}
    for forbidden in ("callback", "handler", "executor", "function", "callable"):
        assert forbidden not in field_names


def test_gateway_owns_no_tool_execution_surface() -> None:
    runtime = _runtime()
    runtime.adapter().add_response(
        content="",
        tool_calls=(ModelToolCall(call_id="call-1", tool_id="t"),),
    )

    for forbidden in ("execute_tool", "invoke_tool", "run_tool", "executor"):
        assert not hasattr(runtime.gateway, forbidden)

    runtime.gateway.execute(_request())

    assert runtime.adapter().call_count == 1


def test_tool_declarations_are_optional() -> None:
    runtime = _runtime(ModelCapabilities())
    runtime.adapter().add_response(content="no tools needed")

    response = runtime.gateway.execute(_request(tools=()))

    assert response.content == "no tools needed"
    assert response.facts is not None
    assert response.facts.tool_use is False
