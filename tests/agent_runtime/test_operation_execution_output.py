from __future__ import annotations

import pytest

from cmm.agent_runtime.errors import ControlledOperationExecutionError
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.operation_execution_contracts import (
    AgentOperationRequest,
    OperationDescriptor,
)


def _request() -> AgentOperationRequest:
    return AgentOperationRequest(
        id="request:output",
        agent_run_id="run:1",
        workflow_id="workflow:1",
        task_id="task:1",
        operation_name="general.summary",
        operation_version="1.0.0",
        parameters={"text": "hello"},
        idempotency_key="idem:output",
    )


def _adapter(delegate: object) -> AgentExecutionAdapter:
    adapter = AgentExecutionAdapter(execution_delegate=delegate)  # type: ignore[arg-type]
    adapter.register_operation(
        OperationDescriptor(
            name="general.summary",
            version="1.0.0",
            description="summary",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
        )
    )
    return adapter


def test_common_execution_result_transports_json_safe_output_round_trip() -> None:
    result = _adapter(
        lambda request: {"success": True, "output": {"summary": ["a"]}}
    ).execute(_request())
    assert result.output == {"summary": ("a",)}
    assert type(result).from_dict(result.to_dict()) == result


def test_common_execution_result_round_trip_preserves_transaction_references() -> None:
    result = _adapter(lambda request: {"success": True, "output": {}}).execute(
        _request()
    )
    enriched = type(result)(
        **{
            **result.to_dict(),
            "checkpoint_id": "checkpoint:1",
            "transaction_boundary_id": "transaction:1",
        }
    )
    assert type(enriched).from_dict(enriched.to_dict()) == enriched


def test_controlled_operational_failure_is_sanitized() -> None:
    def fail(request: AgentOperationRequest) -> dict[str, object]:
        raise ControlledOperationExecutionError(
            code="DEPENDENCY_UNAVAILABLE",
            message="Dependency unavailable",
            details={"dependency": "planner"},
        )

    result = _adapter(fail).execute(_request())
    assert result.success is False
    assert result.error == {
        "code": "DEPENDENCY_UNAVAILABLE",
        "message": "Dependency unavailable",
        "details": {"dependency": "planner"},
    }
    assert "Dependency unavailable" not in result.reason_codes


def test_programming_error_propagates() -> None:
    def fail(request: AgentOperationRequest) -> dict[str, object]:
        raise TypeError("wrong implementation return construction")

    with pytest.raises(TypeError, match="wrong implementation"):
        _adapter(fail).execute(_request())


def test_invalid_delegate_return_propagates_contract_error() -> None:
    with pytest.raises(TypeError, match="mapping"):
        _adapter(lambda request: "invalid").execute(_request())
