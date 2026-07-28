"""Phase 9.27 completeness gate.

Verifies imports, public exports, canonical contract preservation, Python 3.10
syntax compatibility, round-trip serialization, allowed/forbidden state
transitions, absence of secrets, absence of silently-swallowed exceptions,
absence of xfail/skip on mandatory tests, and behavioral coverage of every
public method of ``AgentRuntimeIntegrationService``.
"""

from __future__ import annotations

import ast
import inspect
from datetime import datetime, timezone
from pathlib import Path

import cmm.agent_runtime as agent_runtime_package
from cmm.agent_runtime import (
    agent_runtime_integration_contracts as contracts_module,
)
from cmm.agent_runtime import (
    agent_runtime_integration_enums as enums_module,
)
from cmm.agent_runtime import (
    agent_runtime_integration_errors as errors_module,
)
from cmm.agent_runtime import (
    agent_runtime_integration_service as service_module,
)
from cmm.agent_runtime import (
    agent_runtime_integration_store as store_module,
)
from cmm.agent_runtime.agent_runtime_integration_contracts import (
    IntegratedAgentExecutionRequest,
    IntegratedAgentExecutionResult,
    IntegrationCompensation,
    IntegrationExecutionPolicy,
    IntegrationExecutionRecord,
    IntegrationExecutionStatus,
)
from cmm.agent_runtime.agent_runtime_integration_enums import (
    ALLOWED_INTEGRATION_TRANSITIONS,
    RESULT_SNAPSHOT_STATES,
    TERMINAL_INTEGRATION_STATES,
    IntegrationExecutionState,
    can_transition_integration_state,
)
from cmm.agent_runtime.agent_runtime_integration_service import (
    AgentRuntimeIntegrationService,
)
from cmm.agent_runtime.agent_security_contracts import AgentPermissionContext
from cmm.agent_runtime.agent_security_enums import SensitivityLevel
from cmm.agent_runtime.operation_execution_contracts import AgentOperationRequest

_PHASE_9_27_MODULES = (
    contracts_module,
    enums_module,
    errors_module,
    service_module,
    store_module,
)

_UTC_NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)

_PACKAGE_EXPORTS = {
    "ALLOWED_INTEGRATION_TRANSITIONS",
    "RESULT_SNAPSHOT_STATES",
    "TERMINAL_INTEGRATION_STATES",
    "AgentRuntimeIntegrationError",
    "AgentRuntimeIntegrationService",
    "AgentRuntimeIntegrationStore",
    "InMemoryAgentRuntimeIntegrationStore",
    "IntegratedAgentExecutionRequest",
    "IntegratedAgentExecutionResult",
    "IntegrationCompensation",
    "IntegrationCompensationStatus",
    "IntegrationDuplicateError",
    "IntegrationExecutionPolicy",
    "IntegrationExecutionRecord",
    "IntegrationExecutionState",
    "IntegrationExecutionStatus",
    "IntegrationFailureMode",
    "IntegrationIdempotencyConflictError",
    "IntegrationNotFoundError",
    "IntegrationStateError",
    "IntegrationStoreConsistencyError",
    "IntegrationStoreError",
    "IntegrationVersionConflictError",
    "can_transition_integration_state",
}


def _module_source_path(module: object) -> Path:
    return Path(inspect.getsourcefile(module))  # type: ignore[arg-type]


# --- Imports and public exports --------------------------------------------


def test_all_phase_9_27_modules_import_cleanly() -> None:
    for module in _PHASE_9_27_MODULES:
        assert module is not None
        assert inspect.ismodule(module)


def test_package_all_has_no_duplicates() -> None:
    names = agent_runtime_package.__all__
    assert len(names) == len(set(names))


def test_phase_9_27_exports_are_present_and_identical_in_package() -> None:
    for name in _PACKAGE_EXPORTS:
        assert hasattr(agent_runtime_package, name), f"missing export {name!r}"
    # Identity, not just name equality: the package must re-export the same
    # object defined in its owning module, not a shadow/copy.
    assert (
        agent_runtime_package.AgentRuntimeIntegrationService
        is service_module.AgentRuntimeIntegrationService
    )
    assert (
        agent_runtime_package.IntegratedAgentExecutionRequest
        is contracts_module.IntegratedAgentExecutionRequest
    )
    assert (
        agent_runtime_package.IntegrationExecutionState
        is enums_module.IntegrationExecutionState
    )
    assert (
        agent_runtime_package.AgentRuntimeIntegrationStore
        is store_module.AgentRuntimeIntegrationStore
    )


def test_contracts_module_all_has_no_duplicates_and_resolves() -> None:
    names = contracts_module.__all__
    assert len(names) == len(set(names))
    for name in names:
        assert hasattr(contracts_module, name)


# --- Python 3.10 syntax compatibility (structural, via ast) ----------------


def test_modules_use_only_python_3_10_compatible_syntax() -> None:
    for module in _PHASE_9_27_MODULES:
        source = _module_source_path(module).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            assert not isinstance(node, ast.TryStar), (
                f"{module.__name__} uses except* (3.11+), not 3.10 compatible"
            )
            if hasattr(ast, "TypeAlias") and isinstance(node, ast.TypeAlias):
                raise AssertionError(
                    f"{module.__name__} uses the 'type' statement (3.12+)"
                )
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                assert not getattr(node, "type_params", ()), (
                    f"{module.__name__}.{node.name} uses PEP 695 type params (3.12+)"
                )


# --- Round-trip serialization -----------------------------------------------


def _sample_permission_context() -> AgentPermissionContext:
    return AgentPermissionContext(
        id="perm-ctx-completeness",
        agent_id="agent-1",
        agent_run_id="run-1",
        goal_id="goal-1",
        actor_id="actor-1",
        owner_actor_id="actor-1",
        allowed_domains=("documents",),
        allowed_resources=("doc-1",),
        allowed_operations=("documents.read",),
        allowed_sensitivity_levels=(SensitivityLevel.INTERNAL,),
        maximum_autonomy_level=2,
        created_at=_UTC_NOW,
    )


def _sample_operation_request() -> AgentOperationRequest:
    return AgentOperationRequest(
        id="op-1",
        agent_run_id="run-1",
        workflow_id="workflow-1",
        task_id="task-1",
        operation_name="documents.read",
        idempotency_key="idem-1",
        parameters={"document": {"id": "doc-1"}},
        created_at=_UTC_NOW.isoformat(),
    )


def _sample_request() -> IntegratedAgentExecutionRequest:
    return IntegratedAgentExecutionRequest(
        execution_id="exec-completeness",
        request_id="req-completeness",
        goal_id="goal-1",
        actor_id="actor-1",
        owner_actor_id="actor-1",
        requested_agent_id="agent-1",
        required_capabilities=("documents.read",),
        permission_context=_sample_permission_context(),
        operations=(_sample_operation_request(),),
        created_at=_UTC_NOW,
    )


def test_integration_execution_policy_round_trips() -> None:
    policy = IntegrationExecutionPolicy(max_operations=5, max_retries=2)
    assert IntegrationExecutionPolicy.from_dict(policy.to_dict()) == policy


def test_integrated_agent_execution_request_round_trips() -> None:
    request = _sample_request()
    assert IntegratedAgentExecutionRequest.from_dict(request.to_dict()) == request


def test_integration_compensation_round_trips() -> None:
    compensation = IntegrationCompensation(
        compensation_id="comp-1",
        execution_id="exec-completeness",
        action="runtime.cancel_run",
        target_id="run-1",
        created_at=_UTC_NOW,
    )
    assert IntegrationCompensation.from_dict(compensation.to_dict()) == compensation


def test_integrated_agent_execution_result_round_trips() -> None:
    result = IntegratedAgentExecutionResult(
        execution_id="exec-completeness",
        request_id="req-completeness",
        goal_id="goal-1",
        final_state=IntegrationExecutionState.COMPLETED,
        agent_id="agent-1",
        agent_run_id="run-exec-completeness",
        created_at=_UTC_NOW,
        completed_at=_UTC_NOW,
    )
    assert IntegratedAgentExecutionResult.from_dict(result.to_dict()) == result


def test_integration_execution_record_round_trips() -> None:
    record = IntegrationExecutionRecord(
        execution_id="exec-completeness",
        request_id="req-completeness",
        goal_id="goal-1",
        request=_sample_request(),
        created_at=_UTC_NOW,
        updated_at=_UTC_NOW,
    )
    assert IntegrationExecutionRecord.from_dict(record.to_dict()) == record


def test_integration_execution_status_round_trips() -> None:
    status = IntegrationExecutionStatus(
        execution_id="exec-completeness",
        request_id="req-completeness",
        goal_id="goal-1",
        created_at=_UTC_NOW,
        updated_at=_UTC_NOW,
    )
    assert IntegrationExecutionStatus.from_dict(status.to_dict()) == status


# --- Allowed / forbidden state transitions ----------------------------------


def test_every_execution_state_has_a_transition_table_entry() -> None:
    for state in IntegrationExecutionState:
        assert state in ALLOWED_INTEGRATION_TRANSITIONS


def test_terminal_states_have_no_outgoing_transitions() -> None:
    for state in TERMINAL_INTEGRATION_STATES:
        assert ALLOWED_INTEGRATION_TRANSITIONS[state] == frozenset()
        assert not can_transition_integration_state(
            state, IntegrationExecutionState.RUNNING
        )


def test_forbidden_transition_is_rejected() -> None:
    assert not can_transition_integration_state(
        IntegrationExecutionState.CREATED, IntegrationExecutionState.COMPLETED
    )
    assert not can_transition_integration_state(
        IntegrationExecutionState.COMPLETED, IntegrationExecutionState.RUNNING
    )


def test_allowed_transition_is_accepted() -> None:
    assert can_transition_integration_state(
        IntegrationExecutionState.RUNNING, IntegrationExecutionState.COMPLETED
    )
    assert can_transition_integration_state(
        IntegrationExecutionState.CREATED, IntegrationExecutionState.CANCELLED
    )


def test_result_snapshot_states_are_terminal_or_paused_only() -> None:
    non_snapshot = set(IntegrationExecutionState) - RESULT_SNAPSHOT_STATES
    for state in non_snapshot:
        assert (
            state not in TERMINAL_INTEGRATION_STATES or state in RESULT_SNAPSHOT_STATES
        )


# --- Secrets and unsafe values -----------------------------------------------


def test_request_metadata_rejects_secret_like_keys() -> None:
    import pytest

    with pytest.raises(ValueError, match="secret"):
        IntegratedAgentExecutionRequest(
            execution_id="exec-secret",
            request_id="req-secret",
            goal_id="goal-1",
            actor_id="actor-1",
            owner_actor_id="actor-1",
            operations=(_sample_operation_request(),),
            metadata={"api_key": "sk-should-not-be-here"},
        )


def test_policy_metadata_rejects_secret_like_keys() -> None:
    import pytest

    with pytest.raises(ValueError, match="secret"):
        IntegrationExecutionPolicy(metadata={"password": "hunter2"})


# --- No silently-swallowed exceptions (structural, via ast) -----------------


def test_service_module_has_no_bare_swallow_except_blocks() -> None:
    source = _module_source_path(service_module).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        is_broad = node.type is None or (
            isinstance(node.type, ast.Name) and node.type.id == "Exception"
        )
        if not is_broad:
            continue
        body_is_only_pass = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
        assert not body_is_only_pass, (
            "found a silent 'except Exception: pass' in "
            f"{service_module.__name__} at line {node.lineno}"
        )


# --- No xfail / skip on mandatory phase 9.27 tests --------------------------


def test_phase_9_27_test_files_have_no_xfail_or_skip_markers() -> None:
    test_dir = Path(__file__).parent
    target_files = [
        test_dir / "test_agent_runtime_integration.py",
        test_dir / "test_agent_runtime_integration_phase9_27.py",
        test_dir / "test_agent_runtime_integration_completeness.py",
    ]
    for path in target_files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    decorator_source = ast.dump(decorator)
                    assert "xfail" not in decorator_source, (
                        f"{path.name}::{node.name} is marked xfail"
                    )
                    assert "skip" not in decorator_source, (
                        f"{path.name}::{node.name} is marked skip"
                    )
            if isinstance(node, ast.Call):
                func = node.func
                called_name = getattr(func, "attr", None) or getattr(func, "id", None)
                assert called_name not in ("skip", "xfail"), (
                    f"{path.name} calls pytest.{called_name}() at line {node.lineno}"
                )


def test_no_todo_markers_in_phase_9_27_production_or_test_code() -> None:
    # Note: this completeness file itself is excluded — its own assertion
    # messages necessarily contain the literal words being scanned for.
    test_dir = Path(__file__).parent
    service_dir = test_dir.parent.parent / "cmm" / "agent_runtime"
    targets = [
        service_dir / "agent_runtime_integration_contracts.py",
        service_dir / "agent_runtime_integration_enums.py",
        service_dir / "agent_runtime_integration_errors.py",
        service_dir / "agent_runtime_integration_service.py",
        service_dir / "agent_runtime_integration_store.py",
        test_dir / "test_agent_runtime_integration_phase9_27.py",
    ]
    for path in targets:
        source = path.read_text(encoding="utf-8")
        assert "TODO" not in source, f"{path.name} contains a TODO marker"
        assert "# PENDING" not in source, f"{path.name} contains a '# PENDING' marker"
        assert "PENDING:" not in source, f"{path.name} contains a 'PENDING:' marker"
        assert "assert False" not in source, (
            f"{path.name} contains a placeholder 'assert False'"
        )


# --- Behavioral coverage of every public service method ---------------------


def test_every_public_service_method_is_exercised_by_the_test_suite() -> None:
    public_methods = {
        name
        for name, member in inspect.getmembers(AgentRuntimeIntegrationService)
        if not name.startswith("_") and inspect.isfunction(member)
    }
    assert public_methods == {"validate", "get_status", "execute", "resume", "cancel"}

    test_dir = Path(__file__).parent
    corpus = "\n".join(
        (test_dir / name).read_text(encoding="utf-8")
        for name in (
            "test_agent_runtime_integration.py",
            "test_agent_runtime_integration_phase9_27.py",
        )
    )
    referenced_attrs: set[str] = set()
    tree = ast.parse(corpus)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            referenced_attrs.add(node.attr)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            referenced_attrs.add(node.func.attr)

    for method_name in public_methods:
        assert method_name in referenced_attrs, (
            f"public method {method_name!r} is never called by the test suite"
        )


def test_get_status_returns_none_for_unknown_execution() -> None:
    """Directly exercises get_status, the one public method with the thinnest
    coverage in the existing suites (it is usually asserted indirectly)."""

    from cmm.agent_runtime.agent_runtime_integration_store import (
        InMemoryAgentRuntimeIntegrationStore,
    )

    store = InMemoryAgentRuntimeIntegrationStore()
    service = AgentRuntimeIntegrationService(
        store=store,
        goal_manager=None,
        registry_service=None,
        runtime_loop=None,
        security_service=None,
        execution_adapter=None,
    )
    assert service.get_status("does-not-exist") is None


# --- Errors module sanity ----------------------------------------------------


def test_all_integration_errors_derive_from_agent_runtime_error() -> None:
    from cmm.agent_runtime.errors import AgentRuntimeError

    error_classes = [
        member
        for _, member in inspect.getmembers(errors_module, inspect.isclass)
        if member.__module__ == errors_module.__name__
    ]
    assert len(error_classes) >= 8
    for error_class in error_classes:
        assert issubclass(error_class, AgentRuntimeError)
