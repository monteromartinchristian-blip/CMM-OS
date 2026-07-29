"""Phase 9.13 – Operation Selection and Execution Adapter Test Suite.

Contains comprehensive unit tests verifying contracts, registry, capabilities, parameter validation,
security gates, approval immutability, budget reservation, idempotency, execution adapter delegation,
Runtime Loop ExecuteHandler integration, repository persistence, and public API exports.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

import cmm.agent_runtime as runtime
from cmm.agent_runtime.enums import (
    AgentOperationExecutionStatus,
    AgentRuntimeStatus,
    ApprovalRequestStatus,
    OperationEffectType,
    OperationEnvironment,
    PolicyDecision,
)
from cmm.agent_runtime.errors import (
    AgentOperationCapabilityError,
    AgentOperationCapabilityExceededError,
    AgentOperationIdempotencyConflictError,
    AgentOperationNotRegisteredError,
    AgentOperationParameterValidationError,
    AgentOperationRequestNotFoundError,
    AgentOperationResultNotFoundError,
    AgentOperationVersionNotRegisteredError,
    DuplicateAgentOperationError,
    DuplicateAgentOperationRequestError,
    DuplicateAgentOperationResultError,
    InvalidAgentOperationContractError,
    RuntimeStepExecutionError,
)
from cmm.agent_runtime.operation_execution_adapter import (
    AgentExecutionAdapter,
    AgentOperationResolver,
)
from cmm.agent_runtime.operation_execution_contracts import (
    AgentOperationExecutionResult,
    AgentOperationRequest,
    OperationCapability,
    OperationDescriptor,
    OperationExecutionGateResult,
)
from cmm.agent_runtime.operation_execution_gates import OperationExecutionGateEvaluator
from cmm.agent_runtime.operation_execution_integrations import (
    InMemoryResourceVersionProvider,
    TransformationExecutionEngineAdapter,
)
from cmm.agent_runtime.operation_execution_repository import (
    InMemoryAgentOperationExecutionRepository,
)
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.agent_runtime.runtime_handlers import ExecuteHandler
from cmm.agent_runtime.runtime_loop_contracts import RuntimeStepContext


def _make_sample_request(**kwargs) -> AgentOperationRequest:
    defaults = {
        "id": "req-1",
        "agent_run_id": "run-1",
        "workflow_id": "wf-1",
        "task_id": "task-1",
        "operation_name": "python.replace_method",
        "operation_version": "1",
        "parameters": {"target": "foo", "replacement": "bar"},
        "idempotency_key": "idem-key-1",
        "environment": "local",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    defaults.update(kwargs)
    return AgentOperationRequest(**defaults)


def _make_sample_descriptor(**kwargs) -> OperationDescriptor:
    defaults = {
        "name": "python.replace_method",
        "version": "1",
        "description": "Replace a method using semantic AST editing",
        "input_schema": {
            "type": "object",
            "required": ["target", "replacement"],
            "properties": {
                "target": {"type": "string"},
                "replacement": {"type": "string"},
                "timeout": {"type": "integer", "minimum": 1, "maximum": 60},
            },
            "additionalProperties": False,
        },
        "effects": (OperationEffectType.UPDATE,),
        "reversible": True,
        "rollback_operation_name": "python.restore_method",
        "compatible_environments": (OperationEnvironment.LOCAL,),
    }
    defaults.update(kwargs)
    return OperationDescriptor(**defaults)


# ── 1. Contract Tests ─────────────────────────────────────────────────────────


def test_agent_operation_request_valid() -> None:
    req = _make_sample_request()
    assert req.id == "req-1"
    assert req.operation_name == "python.replace_method"
    assert req.parameters["target"] == "foo"


def test_agent_operation_request_empty_id_raises() -> None:
    with pytest.raises(InvalidAgentOperationContractError):
        _make_sample_request(id="")


def test_agent_operation_request_empty_operation_name_raises() -> None:
    with pytest.raises(InvalidAgentOperationContractError):
        _make_sample_request(operation_name="")


def test_agent_operation_request_empty_idempotency_key_raises() -> None:
    with pytest.raises(InvalidAgentOperationContractError):
        _make_sample_request(idempotency_key="")


def test_agent_operation_request_naive_timestamp_raises() -> None:
    with pytest.raises(InvalidAgentOperationContractError):
        _make_sample_request(created_at="2026-07-25T20:00:00")


def test_agent_operation_request_non_serializable_params_raises() -> None:
    with pytest.raises(InvalidAgentOperationContractError):
        _make_sample_request(parameters={"func": lambda x: x})


def test_agent_operation_request_fingerprint_deterministic() -> None:
    req1 = _make_sample_request()
    req2 = _make_sample_request()
    assert req1.calculate_fingerprint() == req2.calculate_fingerprint()

    req3 = _make_sample_request(parameters={"target": "foo", "replacement": "baz"})
    assert req1.calculate_fingerprint() != req3.calculate_fingerprint()


def test_agent_operation_request_serialization_roundtrip() -> None:
    req = _make_sample_request()
    d = req.to_dict()
    restored = AgentOperationRequest.from_dict(d)
    assert restored.id == req.id
    assert restored.calculate_fingerprint() == req.calculate_fingerprint()


def test_operation_descriptor_valid() -> None:
    desc = _make_sample_descriptor()
    assert desc.name == "python.replace_method"
    assert desc.version == "1"


def test_operation_descriptor_empty_name_raises() -> None:
    with pytest.raises(InvalidAgentOperationContractError):
        _make_sample_descriptor(name="")


def test_operation_descriptor_invalid_timeout_raises() -> None:
    with pytest.raises(InvalidAgentOperationContractError):
        _make_sample_descriptor(timeout_seconds=0)


def test_operation_capability_valid() -> None:
    cap = OperationCapability(
        operation_name="python.replace_method",
        operation_version="1",
        allowed=True,
        maximum_uses=5,
    )
    assert cap.allowed is True
    assert cap.maximum_uses == 5


def test_operation_capability_empty_name_raises() -> None:
    with pytest.raises(InvalidAgentOperationContractError):
        OperationCapability(operation_name="")


def test_operation_capability_naive_expires_at_raises() -> None:
    with pytest.raises(InvalidAgentOperationContractError):
        OperationCapability(operation_name="test", expires_at="2026-07-25T20:00:00")


def test_gate_result_valid() -> None:
    gate = OperationExecutionGateResult(request_id="req-1", allowed=True)
    assert gate.allowed is True
    assert gate.denied is False


def test_gate_result_empty_request_id_raises() -> None:
    with pytest.raises(InvalidAgentOperationContractError):
        OperationExecutionGateResult(request_id="")


def test_execution_result_valid() -> None:
    res = AgentOperationExecutionResult(
        id="res-1",
        request_id="req-1",
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="task-1",
        operation_name="python.replace_method",
        idempotency_key="idem-1",
    )
    assert res.success is True
    assert res.status == AgentOperationExecutionStatus.COMPLETED.value


def test_execution_result_serialization_roundtrip() -> None:
    res = AgentOperationExecutionResult(
        id="res-1",
        request_id="req-1",
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="task-1",
        operation_name="python.replace_method",
        idempotency_key="idem-1",
    )
    d = res.to_dict()
    assert d["id"] == "res-1"
    assert d["status"] == "completed"


# ── 2. Registry Tests ─────────────────────────────────────────────────────────


def test_registry_register_and_get() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)
    assert reg.contains("python.replace_method", "1")
    resolved = reg.get("python.replace_method", "1")
    assert resolved.name == "python.replace_method"


def test_registry_register_duplicate_raises() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)
    with pytest.raises(DuplicateAgentOperationError):
        reg.register(desc)


def test_registry_unregister() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)
    unreg = reg.unregister("python.replace_method", "1")
    assert unreg.name == desc.name
    assert not reg.contains("python.replace_method", "1")


def test_registry_unregister_missing_raises() -> None:
    reg = InMemoryAgentOperationRegistry()
    with pytest.raises(AgentOperationNotRegisteredError):
        reg.unregister("unknown", "1")


def test_registry_unregister_missing_version_raises() -> None:
    reg = InMemoryAgentOperationRegistry()
    reg.register(_make_sample_descriptor(version="1"))
    with pytest.raises(AgentOperationVersionNotRegisteredError):
        reg.unregister("python.replace_method", "2")


def test_registry_resolve_exact_version() -> None:
    reg = InMemoryAgentOperationRegistry()
    reg.register(_make_sample_descriptor(version="1"))
    reg.register(_make_sample_descriptor(version="2"))
    v1 = reg.resolve("python.replace_method", "1")
    v2 = reg.resolve("python.replace_method", "2")
    assert v1.version == "1"
    assert v2.version == "2"


def test_registry_resolve_no_fallback() -> None:
    reg = InMemoryAgentOperationRegistry()
    reg.register(_make_sample_descriptor(version="1"))
    with pytest.raises(AgentOperationVersionNotRegisteredError):
        reg.resolve("python.replace_method", "99")


def test_registry_list_operations_stable_order() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc1 = _make_sample_descriptor(name="op1")
    desc2 = _make_sample_descriptor(name="op2")
    reg.register(desc1)
    reg.register(desc2)
    ops = reg.list_operations()
    assert [o.name for o in ops] == ["op1", "op2"]


def test_registry_list_versions() -> None:
    reg = InMemoryAgentOperationRegistry()
    reg.register(_make_sample_descriptor(version="1"))
    reg.register(_make_sample_descriptor(version="2"))
    versions = reg.list_versions("python.replace_method")
    assert versions == ["1", "2"]


# ── 3. Capability & Resolver Tests ────────────────────────────────────────────


def test_resolver_allowed_capability() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)
    resolver = AgentOperationResolver(reg)
    d, c = resolver.resolve("python.replace_method", "1")
    assert d.name == desc.name
    assert c.allowed is True


def test_resolver_disallowed_capability_raises() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)
    cap = OperationCapability(
        operation_name=desc.name, operation_version=desc.version, allowed=False
    )
    resolver = AgentOperationResolver(reg, {(desc.name, desc.version): cap})
    with pytest.raises(AgentOperationCapabilityError):
        resolver.resolve(desc.name, desc.version)


def test_resolver_maximum_uses_exceeded_raises() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)
    cap = OperationCapability(
        operation_name=desc.name,
        operation_version=desc.version,
        allowed=True,
        maximum_uses=2,
    )
    resolver = AgentOperationResolver(reg, {(desc.name, desc.version): cap})
    resolver.resolve(desc.name, desc.version, uses_count=1)
    with pytest.raises(AgentOperationCapabilityExceededError):
        resolver.resolve(desc.name, desc.version, uses_count=2)


# ── 4. Parameter Validation Tests ─────────────────────────────────────────────


def test_validate_request_valid_parameters() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)
    req = _make_sample_request(parameters={"target": "foo", "replacement": "bar"})
    assert reg.validate_request(req) is True


def test_validate_request_missing_required_raises() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)
    req = _make_sample_request(parameters={"target": "foo"})
    with pytest.raises(AgentOperationParameterValidationError):
        reg.validate_request(req)


def test_validate_request_wrong_type_raises() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)
    req = _make_sample_request(parameters={"target": "foo", "replacement": 12345})
    with pytest.raises(AgentOperationParameterValidationError):
        reg.validate_request(req)


def test_validate_request_disallowed_additional_raises() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)
    req = _make_sample_request(
        parameters={"target": "foo", "replacement": "bar", "unknown": "baz"}
    )
    with pytest.raises(AgentOperationParameterValidationError):
        reg.validate_request(req)


def test_validate_request_out_of_range_minimum_raises() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)
    req = _make_sample_request(
        parameters={"target": "foo", "replacement": "bar", "timeout": 0}
    )
    with pytest.raises(AgentOperationParameterValidationError):
        reg.validate_request(req)


def test_validate_request_out_of_range_maximum_raises() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)
    req = _make_sample_request(
        parameters={"target": "foo", "replacement": "bar", "timeout": 100}
    )
    with pytest.raises(AgentOperationParameterValidationError):
        reg.validate_request(req)


def test_validate_request_enum_value_validation() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = OperationDescriptor(
        name="op_enum",
        version="1",
        description="Enum test",
        input_schema={
            "type": "object",
            "required": ["mode"],
            "properties": {"mode": {"type": "string", "enum": ["fast", "slow"]}},
        },
    )
    reg.register(desc)
    req_valid = _make_sample_request(
        operation_name="op_enum", parameters={"mode": "fast"}
    )
    assert reg.validate_request(req_valid) is True

    req_invalid = _make_sample_request(
        operation_name="op_enum", parameters={"mode": "invalid"}
    )
    with pytest.raises(AgentOperationParameterValidationError):
        reg.validate_request(req_invalid)


# ── 5. Security Gates Tests ───────────────────────────────────────────────────


def test_gate_unregistered_operation_denied() -> None:
    reg = InMemoryAgentOperationRegistry()
    evaluator = OperationExecutionGateEvaluator(reg)
    req = _make_sample_request(operation_name="unregistered")
    res = evaluator.evaluate(req)
    assert res.allowed is False
    assert res.registered is False
    assert "operation.not_registered" in res.reason_codes


def test_gate_disabled_operation_denied() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor(enabled=False)
    reg.register(desc)
    evaluator = OperationExecutionGateEvaluator(reg)
    req = _make_sample_request()
    res = evaluator.evaluate(req)
    assert res.allowed is False
    assert res.registered is False
    assert "operation.disabled" in res.reason_codes


def test_gate_environment_denied() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor(
        compatible_environments=(OperationEnvironment.SANDBOX,)
    )
    reg.register(desc)
    evaluator = OperationExecutionGateEvaluator(reg)
    req = _make_sample_request(environment="local")
    res = evaluator.evaluate(req)
    assert res.allowed is False
    assert res.environment_satisfied is False


def test_gate_missing_required_permissions_denied() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor(required_permissions=("admin",))
    reg.register(desc)
    evaluator = OperationExecutionGateEvaluator(reg)
    req = _make_sample_request(permissions=())
    res = evaluator.evaluate(req)
    assert res.allowed is False
    assert res.permissions_satisfied is False


def test_gate_resource_version_conflict_denied() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)
    ver_provider = InMemoryResourceVersionProvider({"file:src/module.py": "sha256:new"})
    evaluator = OperationExecutionGateEvaluator(
        reg, resource_version_provider=ver_provider
    )
    req = _make_sample_request(resource_versions={"file:src/module.py": "sha256:old"})
    res = evaluator.evaluate(req)
    assert res.allowed is False
    assert res.resource_versions_satisfied is False


def test_gate_stale_checkpoint_denied() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)
    evaluator = OperationExecutionGateEvaluator(reg)
    req = _make_sample_request()
    res = evaluator.evaluate(req, checkpoint_valid=False)
    assert res.allowed is False
    assert res.checkpoint_satisfied is False


def test_gate_all_passed() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)
    evaluator = OperationExecutionGateEvaluator(reg)
    req = _make_sample_request()
    res = evaluator.evaluate(req)
    assert res.allowed is True
    assert res.denied is False


# ── 6. Approval Immutability & Fingerprint Tests ──────────────────────────────


def test_approval_fingerprint_mismatch_denied() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)

    req1 = _make_sample_request(
        approval_request_id="app-1",
        parameters={"target": "foo", "replacement": "bar"},
    )
    fp1 = req1.calculate_fingerprint()

    # Mock approval service returning approval for req1 fingerprint
    class DummyApproval:
        status = ApprovalRequestStatus.APPROVED
        request_fingerprint = fp1

    class DummyApprovalService:
        def get_request(self, app_id: str):
            return DummyApproval()

    evaluator = OperationExecutionGateEvaluator(
        reg, approval_service=DummyApprovalService()
    )

    # Request with modified parameter after approval
    req_modified = _make_sample_request(
        approval_request_id="app-1",
        parameters={"target": "foo", "replacement": "MODIFIED"},
    )

    res = evaluator.evaluate(
        req_modified,
        capability=OperationCapability(
            operation_name=desc.name, requires_approval=True
        ),
    )

    assert res.allowed is False
    assert res.approval_satisfied is False
    assert "operation.approval_mismatch" in res.reason_codes


# ── 7. Idempotency Tests ──────────────────────────────────────────────────────


def test_adapter_idempotency_same_key_same_payload_replays() -> None:
    adapter = AgentExecutionAdapter(
        execution_delegate=lambda req: {"success": True, "effects": ("done",)}
    )
    desc = _make_sample_descriptor()
    adapter.register_operation(desc)

    req = _make_sample_request(idempotency_key="key-123")
    res1 = adapter.execute(req)
    assert res1.success is True

    # Re-invoke with identical payload
    res2 = adapter.execute(req)
    assert res2.id == res1.id


def test_adapter_idempotency_same_key_conflicting_payload_raises() -> None:
    adapter = AgentExecutionAdapter(execution_delegate=lambda req: {"success": True})
    desc = _make_sample_descriptor()
    adapter.register_operation(desc)

    req1 = _make_sample_request(
        id="req-1",
        idempotency_key="key-123",
        parameters={"target": "foo", "replacement": "bar"},
    )
    res1 = adapter.execute(req1)
    assert res1.success is True

    req2 = _make_sample_request(
        id="req-2",
        idempotency_key="key-123",
        parameters={"target": "foo", "replacement": "DIFFERENT"},
    )
    with pytest.raises(AgentOperationIdempotencyConflictError):
        adapter.execute(req2)


# ── 8. Execution Adapter Delegation & Execution Tests ─────────────────────────


def test_adapter_delegation_success() -> None:
    delegate_calls = []

    def mock_delegate(req: AgentOperationRequest) -> dict:
        delegate_calls.append(req)
        return {
            "success": True,
            "effects": ("method_replaced",),
            "artifacts": ("patch.diff",),
        }

    adapter = AgentExecutionAdapter(execution_delegate=mock_delegate)
    desc = _make_sample_descriptor()
    adapter.register_operation(desc)

    req = _make_sample_request()
    res = adapter.execute(req)

    assert len(delegate_calls) == 1
    assert res.success is True
    assert res.status == "completed"
    assert "method_replaced" in res.effects
    assert "patch.diff" in res.artifacts


def test_adapter_delegation_exception_handled() -> None:
    def failing_delegate(req: AgentOperationRequest) -> dict:
        raise RuntimeError("Execution engine crashed")

    adapter = AgentExecutionAdapter(execution_delegate=failing_delegate)
    desc = _make_sample_descriptor()
    adapter.register_operation(desc)

    req = _make_sample_request()
    res = adapter.execute(req)

    assert res.success is False
    assert res.status == "failed"
    assert "operation.execution_failed" in res.reason_codes


def test_adapter_unregistered_operation_fails() -> None:
    adapter = AgentExecutionAdapter(execution_delegate=lambda req: {"success": True})
    req = _make_sample_request(operation_name="unknown")
    res = adapter.execute(req)
    assert res.success is False
    assert res.status == "blocked"


def _make_sample_agent_run(**kwargs) -> runtime.AgentRun:
    now_dt = datetime.now(timezone.utc)
    defaults = {
        "id": "run-1",
        "agent_id": "def-1",
        "goal_id": "goal-1",
        "status": AgentRuntimeStatus.EXECUTING,
        "autonomy_level": 4,
        "current_iteration": 1,
        "started_at": now_dt,
        "updated_at": now_dt,
    }
    defaults.update(kwargs)
    return runtime.AgentRun(**defaults)


def _make_step_context(**kwargs) -> RuntimeStepContext:
    defaults = {
        "agent_run": _make_sample_agent_run(),
        "now": datetime.now(timezone.utc).isoformat(),
        "metadata": {},
    }
    defaults.update(kwargs)
    return RuntimeStepContext(**defaults)


# ── 9. Runtime Loop ExecuteHandler Integration Tests ──────────────────────────


def test_execute_handler_delegates_to_adapter() -> None:
    adapter = AgentExecutionAdapter(
        execution_delegate=lambda req: {"success": True, "effects": ("done",)}
    )
    desc = _make_sample_descriptor()
    adapter.register_operation(desc)

    handler = ExecuteHandler(adapter=adapter)

    req = _make_sample_request()
    ctx = _make_step_context(metadata={"operation_request": req})

    res = handler.execute(ctx)
    assert res.success is True
    assert res.next_status == AgentRuntimeStatus.VALIDATING.value


def test_execute_handler_without_adapter_or_func_raises() -> None:
    handler = ExecuteHandler()
    ctx = _make_step_context()
    with pytest.raises(RuntimeStepExecutionError):
        handler.execute(ctx)


def test_execute_handler_with_explicit_executor_func() -> None:
    def my_executor(ctx: RuntimeStepContext) -> str:
        return "custom-exec-id"

    handler = ExecuteHandler(executor_func=my_executor)
    ctx = _make_step_context()
    res = handler.execute(ctx)
    assert res.success is True
    assert "custom-exec-id" in res.produced_ids


def test_execute_handler_adapter_execution_failure_transitions_to_recovering() -> None:
    adapter = AgentExecutionAdapter(execution_delegate=lambda req: {"success": False})
    desc = _make_sample_descriptor()
    adapter.register_operation(desc)

    handler = ExecuteHandler(adapter=adapter)
    req = _make_sample_request()
    ctx = _make_step_context(metadata={"operation_request": req})

    res = handler.execute(ctx)
    assert res.success is False
    assert res.next_status == AgentRuntimeStatus.RECOVERING.value


# ── 10. Repository Persistence Tests ──────────────────────────────────────────


def test_repository_requests_and_results_persistence() -> None:
    repo = InMemoryAgentOperationExecutionRepository()
    req = _make_sample_request()
    repo.add_request(req)

    assert repo.get_request("req-1").id == "req-1"
    assert len(repo.list_requests("run-1")) == 1

    res = AgentOperationExecutionResult(
        id="res-1",
        request_id="req-1",
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="task-1",
        operation_name="python.replace_method",
        idempotency_key="idem-key-1",
    )
    repo.add_result(res)

    assert repo.get_result("res-1").id == "res-1"
    assert len(repo.list_results("run-1")) == 1
    assert repo.count_uses("run-1", "python.replace_method", "1") == 1


def test_repository_orphaned_result_raises() -> None:
    repo = InMemoryAgentOperationExecutionRepository()
    res = AgentOperationExecutionResult(
        id="res-1",
        request_id="non-existent-req",
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="task-1",
        operation_name="python.replace_method",
        idempotency_key="idem-key-1",
    )
    with pytest.raises(AgentOperationRequestNotFoundError):
        repo.add_result(res)


def test_repository_duplicate_request_raises() -> None:
    repo = InMemoryAgentOperationExecutionRepository()
    req = _make_sample_request()
    repo.add_request(req)
    with pytest.raises(DuplicateAgentOperationRequestError):
        repo.add_request(req)


def test_repository_duplicate_result_raises() -> None:
    repo = InMemoryAgentOperationExecutionRepository()
    req = _make_sample_request()
    repo.add_request(req)
    res = AgentOperationExecutionResult(
        id="res-1",
        request_id="req-1",
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="task-1",
        operation_name="python.replace_method",
        idempotency_key="idem-key-1",
    )
    repo.add_result(res)
    with pytest.raises(DuplicateAgentOperationResultError):
        repo.add_result(res)


def test_repository_get_non_existent_request_raises() -> None:
    repo = InMemoryAgentOperationExecutionRepository()
    with pytest.raises(AgentOperationRequestNotFoundError):
        repo.get_request("missing-id")


def test_repository_get_non_existent_result_raises() -> None:
    repo = InMemoryAgentOperationExecutionRepository()
    with pytest.raises(AgentOperationResultNotFoundError):
        repo.get_result("missing-id")


def test_repository_find_by_idempotency_key_none() -> None:
    repo = InMemoryAgentOperationExecutionRepository()
    assert repo.find_by_idempotency_key("unknown-key") is None


def test_validate_request_boolean_type_check() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = OperationDescriptor(
        name="op_bool",
        version="1",
        description="Bool test",
        input_schema={
            "type": "object",
            "properties": {"flag": {"type": "boolean"}},
        },
    )
    reg.register(desc)
    req_valid = _make_sample_request(
        operation_name="op_bool", parameters={"flag": True}
    )
    assert reg.validate_request(req_valid) is True

    req_invalid = _make_sample_request(
        operation_name="op_bool", parameters={"flag": "yes"}
    )
    with pytest.raises(AgentOperationParameterValidationError):
        reg.validate_request(req_invalid)


def test_validate_request_integer_type_check() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = OperationDescriptor(
        name="op_int",
        version="1",
        description="Int test",
        input_schema={
            "type": "object",
            "properties": {"count": {"type": "integer"}},
        },
    )
    reg.register(desc)
    req_valid = _make_sample_request(operation_name="op_int", parameters={"count": 5})
    assert reg.validate_request(req_valid) is True

    req_invalid = _make_sample_request(
        operation_name="op_int", parameters={"count": 5.5}
    )
    with pytest.raises(AgentOperationParameterValidationError):
        reg.validate_request(req_invalid)


def test_validate_request_number_type_check() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = OperationDescriptor(
        name="op_num",
        version="1",
        description="Num test",
        input_schema={
            "type": "object",
            "properties": {"ratio": {"type": "number"}},
        },
    )
    reg.register(desc)
    req_valid = _make_sample_request(
        operation_name="op_num", parameters={"ratio": 0.75}
    )
    assert reg.validate_request(req_valid) is True

    req_invalid = _make_sample_request(
        operation_name="op_num", parameters={"ratio": "0.75"}
    )
    with pytest.raises(AgentOperationParameterValidationError):
        reg.validate_request(req_invalid)


def test_validate_request_array_type_check() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = OperationDescriptor(
        name="op_arr",
        version="1",
        description="Array test",
        input_schema={
            "type": "object",
            "properties": {"items": {"type": "array"}},
        },
    )
    reg.register(desc)
    req_valid = _make_sample_request(
        operation_name="op_arr", parameters={"items": ["a", "b"]}
    )
    assert reg.validate_request(req_valid) is True

    req_invalid = _make_sample_request(
        operation_name="op_arr", parameters={"items": "not a list"}
    )
    with pytest.raises(AgentOperationParameterValidationError):
        reg.validate_request(req_invalid)


def test_validate_request_object_type_check() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = OperationDescriptor(
        name="op_obj",
        version="1",
        description="Object test",
        input_schema={
            "type": "object",
            "properties": {"config": {"type": "object"}},
        },
    )
    reg.register(desc)
    req_valid = _make_sample_request(
        operation_name="op_obj", parameters={"config": {"key": "val"}}
    )
    assert reg.validate_request(req_valid) is True

    req_invalid = _make_sample_request(
        operation_name="op_obj", parameters={"config": 123}
    )
    with pytest.raises(AgentOperationParameterValidationError):
        reg.validate_request(req_invalid)


def test_gate_autonomy_denied() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)

    class MockAutonomy:
        def evaluate(self, req):
            class Res:
                decision = "deny"

            return Res()

    evaluator = OperationExecutionGateEvaluator(reg, autonomy_evaluator=MockAutonomy())
    req = _make_sample_request()
    res = evaluator.evaluate(req)
    assert res.allowed is False
    assert res.autonomy_satisfied is False


def test_gate_policy_denied() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)

    class MockPolicy:
        def evaluate(self, req):
            class Res:
                decision = PolicyDecision.DENY

            return Res()

    evaluator = OperationExecutionGateEvaluator(reg, policy_evaluator=MockPolicy())
    req = _make_sample_request()
    res = evaluator.evaluate(req)
    assert res.allowed is False
    assert res.policy_satisfied is False


def test_gate_budget_exhausted_denied() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)

    class MockBudgetService:
        def check_budget(self, req):
            return False

    evaluator = OperationExecutionGateEvaluator(reg, budget_service=MockBudgetService())
    req = _make_sample_request()
    res = evaluator.evaluate(req)
    assert res.allowed is False
    assert res.budget_satisfied is False


def test_gate_lock_conflict_denied() -> None:
    reg = InMemoryAgentOperationRegistry()
    desc = _make_sample_descriptor()
    reg.register(desc)

    class MockLockManager:
        def is_locked(self, key):
            return True

    evaluator = OperationExecutionGateEvaluator(reg, lock_manager=MockLockManager())
    req = _make_sample_request()
    res = evaluator.evaluate(req)
    assert res.allowed is False
    assert res.locks_satisfied is False


def test_transformation_engine_adapter_execution() -> None:
    adapter = TransformationExecutionEngineAdapter()
    req = _make_sample_request()
    out = adapter.execute(req)
    assert out["success"] is True
    assert "executed:python.replace_method" in out["effects"]


# ── 11. Public API & Export Tests ─────────────────────────────────────────────


def test_public_api_exports() -> None:
    expected_exports = [
        "AgentOperationRequest",
        "OperationDescriptor",
        "OperationCapability",
        "OperationExecutionGateResult",
        "AgentOperationExecutionResult",
        "AgentOperationRegistry",
        "InMemoryAgentOperationRegistry",
        "AgentOperationExecutionRepository",
        "InMemoryAgentOperationExecutionRepository",
        "AgentOperationResolver",
        "AgentExecutionAdapter",
        "OperationExecutionGateEvaluator",
        "AgentOperationExecutionStatus",
        "OperationEffectType",
        "OperationReversibility",
        "OperationEnvironment",
        "AgentOperationError",
        "InvalidAgentOperationContractError",
        "AgentOperationNotRegisteredError",
        "AgentOperationVersionNotRegisteredError",
        "DuplicateAgentOperationError",
        "AgentOperationRequestNotFoundError",
        "DuplicateAgentOperationRequestError",
        "AgentOperationResultNotFoundError",
        "DuplicateAgentOperationResultError",
        "AgentOperationCapabilityError",
        "AgentOperationCapabilityExceededError",
        "AgentOperationParameterValidationError",
        "AgentOperationEnvironmentError",
        "AgentOperationPermissionError",
        "AgentOperationPolicyError",
        "AgentOperationAutonomyError",
        "AgentOperationApprovalError",
        "AgentOperationBudgetError",
        "AgentOperationCheckpointError",
        "AgentOperationResourceVersionError",
        "AgentOperationLockError",
        "AgentOperationRollbackError",
        "AgentOperationExecutionError",
        "AgentOperationValidationError",
        "AgentOperationIdempotencyConflictError",
        "AgentOperationRepositoryConsistencyError",
    ]

    missing = [name for name in expected_exports if not hasattr(runtime, name)]
    assert missing == [], f"Missing exported symbols in cmm.agent_runtime: {missing}"

    all_exports = runtime.__all__
    duplicates = [name for name in all_exports if all_exports.count(name) > 1]
    assert duplicates == [], f"Duplicate entries in __all__: {set(duplicates)}"
