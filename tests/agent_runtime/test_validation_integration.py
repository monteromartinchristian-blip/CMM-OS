"""Phase 9.14 – Validation Integration Test Suite.

Comprehensive tests covering contracts, repository, policy selection, the real
Phase 7 Validation Pipeline / Commit Gate integration, Agent Execution Adapter
integration, Runtime Loop integration, and security/debt invariants.
"""

from __future__ import annotations

import ast
import concurrent.futures
import inspect
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from cmm.agent_runtime.contracts import AgentRun
from cmm.agent_runtime.enums import (
    AgentOperationExecutionStatus,
    AgentRuntimeStatus,
    AgentValidationDecision,
    AgentValidationStage,
    AgentValidationStatus,
    OperationEffectType,
    ValidationFailureClass,
    ValidationRequirementKind,
)
from cmm.agent_runtime.errors import (
    AgentValidationError,
    InvalidAgentContractError,
    RuntimeStepExecutionError,
    RuntimeTransitionNotAllowedError,
    ValidationAdapterError,
    ValidationPolicySelectionError,
    ValidationRepositoryError,
    ValidationRequirementError,
    ValidationResultInvalidError,
)
from cmm.agent_runtime.operation_execution_adapter import AgentExecutionAdapter
from cmm.agent_runtime.operation_execution_contracts import (
    AgentOperationRequest,
    OperationDescriptor,
)
from cmm.agent_runtime.operation_execution_repository import (
    InMemoryAgentOperationExecutionRepository,
)
from cmm.agent_runtime.operation_registry import InMemoryAgentOperationRegistry
from cmm.agent_runtime.runtime_handlers import ValidateHandler
from cmm.agent_runtime.runtime_loop_contracts import (
    AgentIteration,
    RuntimeStepContext,
    current_aware_iso,
)
from cmm.agent_runtime.runtime_state_machine import AgentRuntimeStateMachine
from cmm.agent_runtime.validation_execution_adapter import (
    AgentValidationAdapter,
    ValidationDecisionResolver,
    _resource_fingerprint,
)
from cmm.agent_runtime.validation_integration_contracts import (
    AgentValidationEvent,
    AgentValidationRequest,
    AgentValidationResult,
    CommitGateEvaluation,
    ValidationDecision,
    ValidationExecutionContext,
    ValidationFinding,
    ValidationPolicySelection,
    ValidationRequirement,
)
from cmm.agent_runtime.validation_integration_repository import (
    InMemoryAgentValidationRepository,
)
from cmm.agent_runtime.validation_policy_adapter import (
    AgentValidationPolicyAdapter,
    ValidationRequirementResolver,
)

SCRATCH_DIR = Path(tempfile.mkdtemp(prefix="cmm-validation-integration-"))


def _write_fixture(name: str, content: str) -> Path:
    path = SCRATCH_DIR / name
    path.write_text(content)
    return path


GOOD_PY = _write_fixture("val_good.py", "def ok():\n    return 1\n")
BAD_PY = _write_fixture("val_bad.py", "def broken(:\n    pass\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_agent_run(
    run_id: str = "run-loop", status: AgentRuntimeStatus = AgentRuntimeStatus.VALIDATING
) -> AgentRun:
    now = datetime.now(timezone.utc)
    return AgentRun(
        id=run_id,
        agent_id="agent-1",
        goal_id="goal-1",
        status=status,
        autonomy_level=2,
        current_iteration=1,
        started_at=now,
        updated_at=now,
    )


def _make_iteration(
    iteration_id: str = "iter-loop", run_id: str = "run-loop"
) -> AgentIteration:
    return AgentIteration(
        id=iteration_id,
        agent_run_id=run_id,
        number=1,
        status="running",
        started_at=current_aware_iso(),
    )


def _make_step_context(run: AgentRun, metadata: dict) -> RuntimeStepContext:
    return RuntimeStepContext(
        agent_run=run,
        now=current_aware_iso(),
        iteration=_make_iteration(run_id=run.id),
        metadata=metadata,
    )


class _FixedDecisionAdapter(AgentValidationAdapter):
    """Test double returning a pre-baked decision without touching Phase 7."""

    def __init__(
        self, decision: AgentValidationDecision, status: AgentValidationStatus
    ) -> None:
        self._decision = decision
        self._status = status

    def validate(self, request, exec_context=None) -> AgentValidationResult:
        return AgentValidationResult(
            request_id=request.id,
            run_id=request.run_id,
            iteration_id=request.iteration_id,
            operation_request_id=request.operation_request_id,
            stage=request.stage,
            status=self._status,
            decision=self._decision,
        )


# ── 1. CONTRATOS ─────────────────────────────────────────────────────────────


def test_validation_requirement_creation_and_immutability():
    req = ValidationRequirement(
        requirement_id="req-101",
        validation_kind=ValidationRequirementKind.SYNTAX,
        stage=AgentValidationStage.POST_EXECUTION,
        required=True,
        blocking=True,
        policy_id="policy-syntax",
        validator_ids=("syntax_validator",),
        resource_scope=("cmm/core.py",),
    )
    assert req.requirement_id == "req-101"
    assert req.validation_kind == ValidationRequirementKind.SYNTAX
    assert req.stage == AgentValidationStage.POST_EXECUTION
    with pytest.raises(AttributeError):
        req.blocking = False  # type: ignore


def test_validation_requirement_empty_id_raises():
    with pytest.raises(ValidationRequirementError):
        ValidationRequirement(
            requirement_id="",
            validation_kind=ValidationRequirementKind.PREVENTATIVE,
            stage=AgentValidationStage.PRE_EXECUTION,
        )


def test_validation_requirement_invalid_timeout_raises():
    with pytest.raises(ValidationRequirementError):
        ValidationRequirement(
            requirement_id="req-invalid-timeout",
            validation_kind=ValidationRequirementKind.PREVENTATIVE,
            stage=AgentValidationStage.PRE_EXECUTION,
            timeout_seconds=-5.0,
        )


def test_validation_requirement_zero_timeout_raises():
    with pytest.raises(ValidationRequirementError):
        ValidationRequirement(
            requirement_id="req-zero-timeout",
            validation_kind=ValidationRequirementKind.PREVENTATIVE,
            stage=AgentValidationStage.PRE_EXECUTION,
            timeout_seconds=0.0,
        )


def test_validation_requirement_string_kind_coerced_to_enum():
    req = ValidationRequirement(
        requirement_id="req-coerce",
        validation_kind="syntax",
        stage="post_execution",
    )
    assert req.validation_kind == ValidationRequirementKind.SYNTAX
    assert req.stage == AgentValidationStage.POST_EXECUTION


def test_validation_requirement_invalid_kind_raises():
    with pytest.raises(ValueError):
        ValidationRequirement(
            requirement_id="req-bad-kind",
            validation_kind="not_a_real_kind",
            stage=AgentValidationStage.PRE_EXECUTION,
        )


def test_validation_requirement_serialization():
    req = ValidationRequirement(
        requirement_id="req-serialization",
        validation_kind=ValidationRequirementKind.AST,
        stage=AgentValidationStage.POST_EXECUTION,
        validator_ids=("ast_validator",),
    )
    d = req.to_dict()
    assert d["requirement_id"] == "req-serialization"
    assert d["validation_kind"] == "ast"
    deserialized = ValidationRequirement.from_dict(d)
    assert deserialized == req


def test_validation_requirement_metadata_is_frozen():
    req = ValidationRequirement(
        requirement_id="req-meta",
        validation_kind=ValidationRequirementKind.CUSTOM,
        stage=AgentValidationStage.PRE_EXECUTION,
        metadata={"nested": {"a": 1}},
    )
    with pytest.raises(TypeError):
        req.metadata["nested"] = "x"  # type: ignore


def test_validation_finding_creation_and_serialization():
    finding = ValidationFinding(
        finding_id="f-1",
        rule_id="rule-01",
        severity="ERROR",
        message="Syntax error in line 42",
        failure_class=ValidationFailureClass.SYNTAX,
        location="cmm/test.py:42",
    )
    assert finding.finding_id == "f-1"
    assert finding.failure_class == ValidationFailureClass.SYNTAX
    d = finding.to_dict()
    assert d["failure_class"] == "syntax"
    deserialized = ValidationFinding.from_dict(d)
    assert deserialized == finding


def test_validation_finding_empty_id_raises():
    with pytest.raises(InvalidAgentContractError):
        ValidationFinding(
            finding_id="",
            rule_id="r1",
            severity="ERROR",
            message="msg",
            failure_class=ValidationFailureClass.LINT,
        )


def test_validation_finding_invalid_failure_class_raises():
    with pytest.raises(InvalidAgentContractError):
        ValidationFinding(
            finding_id="f-2",
            rule_id="r1",
            severity="ERROR",
            message="msg",
            failure_class=object(),  # type: ignore
        )


def test_validation_execution_context_serialization_and_timezone_independent():
    ctx = ValidationExecutionContext(
        run_id="run-ctx",
        iteration_id="iter-ctx",
        operation_name="op-ctx",
        resource_scope=("a.py", "b.py"),
        metadata={"k": "v"},
    )
    d = ctx.to_dict()
    restored = ValidationExecutionContext.from_dict(d)
    assert restored.run_id == "run-ctx"
    assert restored.resource_scope == ("a.py", "b.py")


def test_validation_execution_context_empty_run_id_raises():
    with pytest.raises(InvalidAgentContractError):
        ValidationExecutionContext(run_id="", iteration_id="i", operation_name="op")


def test_agent_validation_request_fingerprint():
    req = AgentValidationRequest(
        id="val-req-01",
        run_id="run-100",
        iteration_id="iter-01",
        operation_request_id="op-req-01",
        stage=AgentValidationStage.PRE_EXECUTION,
        idempotency_key="key-001",
    )
    assert req.fingerprint != ""
    fp2 = req.calculate_fingerprint()
    assert req.fingerprint == fp2


def test_agent_validation_request_fingerprint_changes_with_payload():
    req1 = AgentValidationRequest(
        id="val-req-fp1",
        run_id="run-100",
        iteration_id="iter-01",
        operation_request_id="op-req-01",
        stage=AgentValidationStage.PRE_EXECUTION,
        context_data={"a": 1},
    )
    req2 = AgentValidationRequest(
        id="val-req-fp1",
        run_id="run-100",
        iteration_id="iter-01",
        operation_request_id="op-req-01",
        stage=AgentValidationStage.PRE_EXECUTION,
        context_data={"a": 2},
    )
    assert req1.fingerprint != req2.fingerprint


def test_agent_validation_request_timezone_awareness():
    naive_timestamp = "2026-07-25T12:00:00"
    with pytest.raises(InvalidAgentContractError):
        AgentValidationRequest(
            id="val-req-naive",
            run_id="run-100",
            iteration_id="iter-01",
            operation_request_id="op-req-01",
            stage=AgentValidationStage.PRE_EXECUTION,
            created_at=naive_timestamp,
        )


def test_agent_validation_request_empty_run_id_raises():
    with pytest.raises(InvalidAgentContractError):
        AgentValidationRequest(
            id="val-req-empty-run",
            run_id="",
            iteration_id="iter-01",
            operation_request_id="op-req-01",
            stage=AgentValidationStage.PRE_EXECUTION,
        )


def test_agent_validation_request_serialization():
    req = AgentValidationRequest(
        id="val-req-ser",
        run_id="run-200",
        iteration_id="iter-02",
        operation_request_id="op-req-02",
        stage=AgentValidationStage.POST_EXECUTION,
    )
    d = req.to_dict()
    res = AgentValidationRequest.from_dict(d)
    assert res.id == req.id
    assert res.fingerprint == req.fingerprint


def test_agent_validation_result_creation():
    res = AgentValidationResult(
        request_id="val-req-01",
        run_id="run-100",
        iteration_id="iter-01",
        operation_request_id="op-req-01",
        stage=AgentValidationStage.PRE_EXECUTION,
        status=AgentValidationStatus.PASSED,
        decision=AgentValidationDecision.CONTINUE,
    )
    assert res.request_id == "val-req-01"
    assert res.status == AgentValidationStatus.PASSED
    assert res.decision == AgentValidationDecision.CONTINUE
    assert res.fingerprint != ""
    with pytest.raises(AttributeError):
        res.status = AgentValidationStatus.FAILED  # type: ignore


def test_agent_validation_result_naive_timestamp_raises():
    with pytest.raises(ValidationResultInvalidError):
        AgentValidationResult(
            request_id="val-req-01",
            run_id="run-100",
            iteration_id="iter-01",
            operation_request_id="op-req-01",
            stage=AgentValidationStage.PRE_EXECUTION,
            status=AgentValidationStatus.PASSED,
            decision=AgentValidationDecision.CONTINUE,
            started_at="2026-07-25T10:00:00",
        )


def test_agent_validation_result_empty_request_id_raises():
    with pytest.raises(ValidationResultInvalidError):
        AgentValidationResult(
            request_id="",
            run_id="run-100",
            iteration_id="iter-01",
            operation_request_id="op-req-01",
            stage=AgentValidationStage.PRE_EXECUTION,
            status=AgentValidationStatus.PASSED,
            decision=AgentValidationDecision.CONTINUE,
        )


def test_agent_validation_result_serialization_round_trip():
    res = AgentValidationResult(
        request_id="val-req-rt",
        run_id="run-100",
        iteration_id="iter-01",
        operation_request_id="op-req-01",
        stage=AgentValidationStage.POST_EXECUTION,
        status=AgentValidationStatus.PASSED_WITH_WARNINGS,
        decision=AgentValidationDecision.CONTINUE,
        warnings=("careful",),
    )
    d = res.to_dict()
    restored = AgentValidationResult.from_dict(d)
    assert restored.status == AgentValidationStatus.PASSED_WITH_WARNINGS
    assert restored.warnings == ("careful",)


def test_commit_gate_evaluation_serialization():
    cg = CommitGateEvaluation(
        authorized=True,
        decision=AgentValidationDecision.CONTINUE,
        reason_codes=("commit.authorized",),
    )
    d = cg.to_dict()
    assert d["authorized"] is True
    res = CommitGateEvaluation.from_dict(d)
    assert res.authorized is True
    assert res.decision == AgentValidationDecision.CONTINUE


def test_commit_gate_evaluation_naive_timestamp_raises():
    with pytest.raises(InvalidAgentContractError):
        CommitGateEvaluation(
            authorized=False,
            decision=AgentValidationDecision.BLOCK,
            evaluated_at="2026-07-25T10:00:00",
        )


def test_validation_policy_selection_serialization():
    req = ValidationRequirement(
        requirement_id="req-in-policy",
        validation_kind=ValidationRequirementKind.SYNTAX,
        stage=AgentValidationStage.POST_EXECUTION,
    )
    selection = ValidationPolicySelection(
        policy_id="policy-x",
        requirements=(req,),
        rationale=("because",),
    )
    d = selection.to_dict()
    restored = ValidationPolicySelection.from_dict(d)
    assert restored.policy_id == "policy-x"
    assert restored.requirements[0].requirement_id == "req-in-policy"


def test_validation_policy_selection_empty_policy_id_raises():
    with pytest.raises(InvalidAgentContractError):
        ValidationPolicySelection(policy_id="", requirements=(), rationale=())


def test_agent_validation_event_creation_and_serialization():
    ev = AgentValidationEvent(
        event_id="ev-101",
        event_type="VALIDATION_PASSED",
        run_id="run-100",
        decision="CONTINUE",
    )
    assert ev.event_type == "VALIDATION_PASSED"
    d = ev.to_dict()
    res = AgentValidationEvent.from_dict(d)
    assert res.event_id == "ev-101"


def test_agent_validation_event_empty_type_raises():
    with pytest.raises(InvalidAgentContractError):
        AgentValidationEvent(event_id="ev-2", event_type="", run_id="run-1")


def test_validation_decision_is_agent_validation_decision_alias():
    """Phase 9.14 must not introduce a second, competing ValidationDecision type."""
    assert ValidationDecision is AgentValidationDecision
    assert ValidationDecision.CONTINUE == AgentValidationDecision.CONTINUE


# ── 2. REPOSITORIO ────────────────────────────────────────────────────────────


def test_repository_save_and_get_request():
    repo = InMemoryAgentValidationRepository()
    req = AgentValidationRequest(
        id="val-req-repo-1",
        run_id="run-repo-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.PRE_EXECUTION,
    )
    repo.add_request(req)
    fetched = repo.get_request("val-req-repo-1")
    assert fetched == req


def test_repository_save_and_get_result():
    repo = InMemoryAgentValidationRepository()
    res = AgentValidationResult(
        request_id="val-req-repo-1",
        run_id="run-repo-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.PRE_EXECUTION,
        status=AgentValidationStatus.PASSED,
        decision=AgentValidationDecision.CONTINUE,
    )
    repo.add_result(res)
    fetched = repo.get_result("val-req-repo-1")
    assert fetched == res


def test_repository_idempotent_add_request_same_fingerprint_is_noop():
    repo = InMemoryAgentValidationRepository()
    req = AgentValidationRequest(
        id="val-req-same",
        run_id="run-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.PRE_EXECUTION,
    )
    repo.add_request(req)
    repo.add_request(req)  # must not raise
    assert repo.get_request("val-req-same") == req


def test_repository_add_request_same_id_conflicting_fingerprint_raises():
    repo = InMemoryAgentValidationRepository()
    req1 = AgentValidationRequest(
        id="val-req-conflict-id",
        run_id="run-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.PRE_EXECUTION,
        context_data={"v": 1},
    )
    req2 = AgentValidationRequest(
        id="val-req-conflict-id",
        run_id="run-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.PRE_EXECUTION,
        context_data={"v": 2},
    )
    repo.add_request(req1)
    with pytest.raises(ValidationRepositoryError):
        repo.add_request(req2)


def test_repository_idempotency_matching_fingerprint():
    repo = InMemoryAgentValidationRepository()
    req = AgentValidationRequest(
        id="val-req-idem",
        run_id="run-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.PRE_EXECUTION,
        idempotency_key="key-idem-1",
    )
    res = AgentValidationResult(
        request_id="val-req-idem",
        run_id="run-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.PRE_EXECUTION,
        status=AgentValidationStatus.PASSED,
        decision=AgentValidationDecision.CONTINUE,
    )
    repo.add_request(req)
    repo.add_result(res)

    found = repo.find_by_idempotency_key("key-idem-1")
    assert found == res


def test_repository_idempotency_conflicting_fingerprint_raises():
    repo = InMemoryAgentValidationRepository()
    req1 = AgentValidationRequest(
        id="val-req-1",
        run_id="run-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.PRE_EXECUTION,
        idempotency_key="key-conflict",
        context_data={"key": "val1"},
    )
    req2 = AgentValidationRequest(
        id="val-req-2",
        run_id="run-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.PRE_EXECUTION,
        idempotency_key="key-conflict",
        context_data={"key": "val2"},
    )
    repo.add_request(req1)
    with pytest.raises(ValidationRepositoryError):
        repo.add_request(req2)


def test_repository_find_by_idempotency_key_missing_returns_none():
    repo = InMemoryAgentValidationRepository()
    assert repo.find_by_idempotency_key("nonexistent") is None


def test_repository_find_by_idempotency_key_empty_string_returns_none():
    repo = InMemoryAgentValidationRepository()
    assert repo.find_by_idempotency_key("") is None


def test_repository_cannot_mutate_final_result():
    repo = InMemoryAgentValidationRepository()
    res1 = AgentValidationResult(
        request_id="val-res-final",
        run_id="run-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.PRE_EXECUTION,
        status=AgentValidationStatus.PASSED,
        decision=AgentValidationDecision.CONTINUE,
    )
    res2 = AgentValidationResult(
        request_id="val-res-final",
        run_id="run-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.PRE_EXECUTION,
        status=AgentValidationStatus.FAILED,
        decision=AgentValidationDecision.BLOCK,
    )
    repo.add_result(res1)
    with pytest.raises(ValidationRepositoryError):
        repo.add_result(res2)


def test_repository_add_result_same_fingerprint_is_noop():
    repo = InMemoryAgentValidationRepository()
    res = AgentValidationResult(
        request_id="val-res-noop",
        run_id="run-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.PRE_EXECUTION,
        status=AgentValidationStatus.PASSED,
        decision=AgentValidationDecision.CONTINUE,
    )
    repo.add_result(res)
    repo.add_result(res)  # identical fingerprint must not raise
    assert repo.get_result("val-res-noop") == res


def test_repository_get_non_existent_raises():
    repo = InMemoryAgentValidationRepository()
    with pytest.raises(ValidationRepositoryError):
        repo.get_request("non-existent")
    with pytest.raises(ValidationRepositoryError):
        repo.get_result("non-existent")


def test_repository_get_results_by_run_id():
    repo = InMemoryAgentValidationRepository()
    for i in range(3):
        repo.add_result(
            AgentValidationResult(
                request_id=f"val-run-scope-{i}",
                run_id="run-scope",
                iteration_id="iter-1",
                operation_request_id="op-1",
                stage=AgentValidationStage.PRE_EXECUTION,
                status=AgentValidationStatus.PASSED,
                decision=AgentValidationDecision.CONTINUE,
            )
        )
    results = repo.get_results_by_run_id("run-scope")
    assert len(results) == 3
    assert repo.get_results_by_run_id("other-run") == ()


def test_repository_get_results_by_operation_request_id():
    repo = InMemoryAgentValidationRepository()
    repo.add_result(
        AgentValidationResult(
            request_id="val-op-scope-1",
            run_id="run-1",
            iteration_id="iter-1",
            operation_request_id="op-scope-target",
            stage=AgentValidationStage.PRE_EXECUTION,
            status=AgentValidationStatus.PASSED,
            decision=AgentValidationDecision.CONTINUE,
        )
    )
    results = repo.get_results_by_operation_request_id("op-scope-target")
    assert len(results) == 1
    assert repo.get_results_by_operation_request_id("op-other") == ()


def test_repository_thread_safety():
    repo = InMemoryAgentValidationRepository()

    def worker(i: int):
        req = AgentValidationRequest(
            id=f"req-t-{i}",
            run_id="run-concurrent",
            iteration_id=f"iter-{i}",
            operation_request_id=f"op-{i}",
            stage=AgentValidationStage.PRE_EXECUTION,
        )
        res = AgentValidationResult(
            request_id=f"req-t-{i}",
            run_id="run-concurrent",
            iteration_id=f"iter-{i}",
            operation_request_id=f"op-{i}",
            stage=AgentValidationStage.PRE_EXECUTION,
            status=AgentValidationStatus.PASSED,
            decision=AgentValidationDecision.CONTINUE,
        )
        repo.add_request(req)
        repo.add_result(res)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker, i) for i in range(50)]
        concurrent.futures.wait(futures)

    results = repo.get_results_by_run_id("run-concurrent")
    assert len(results) == 50


# ── 3. SELECCIÓN DE POLÍTICA ──────────────────────────────────────────────────


def test_policy_adapter_read_only_operation():
    adapter = AgentValidationPolicyAdapter()
    desc = OperationDescriptor(
        name="read_file",
        description="Read file contents",
        version="1",
        effects=(OperationEffectType.READ,),
    )
    selection = adapter.select_policy(
        operation_descriptor=desc, stage=AgentValidationStage.PRE_EXECUTION
    )
    assert selection.policy_id != ""
    assert len(selection.requirements) > 0


def test_policy_adapter_mutative_operation_post_validation():
    adapter = AgentValidationPolicyAdapter()
    desc = OperationDescriptor(
        name="update_config",
        description="Update configuration",
        version="1",
        effects=(OperationEffectType.UPDATE,),
    )
    selection = adapter.select_policy(
        operation_descriptor=desc, stage=AgentValidationStage.POST_EXECUTION
    )
    kinds = [r.validation_kind for r in selection.requirements]
    assert ValidationRequirementKind.POST_CONDITION in kinds


def test_policy_adapter_destructive_operation_blocking_pre_check():
    adapter = AgentValidationPolicyAdapter()
    desc = OperationDescriptor(
        name="delete_database",
        description="Delete DB table",
        version="1",
        reversible=False,
        effects=(OperationEffectType.DELETE,),
    )
    selection = adapter.select_policy(
        operation_descriptor=desc, stage=AgentValidationStage.PRE_EXECUTION
    )
    blocking_reqs = [r for r in selection.requirements if r.blocking]
    assert len(blocking_reqs) > 0


def test_policy_adapter_python_code_modification():
    adapter = AgentValidationPolicyAdapter()
    desc = OperationDescriptor(
        name="modify_python_file",
        description="Modify python file",
        version="1",
        effects=(OperationEffectType.UPDATE,),
        metadata={"tags": ("code", "python")},
    )
    selection = adapter.select_policy(
        operation_descriptor=desc, stage=AgentValidationStage.POST_EXECUTION
    )
    kinds = [r.validation_kind for r in selection.requirements]
    assert ValidationRequirementKind.SYNTAX in kinds
    assert ValidationRequirementKind.AST in kinds
    assert ValidationRequirementKind.UNIT_TEST in kinds


def test_policy_adapter_python_requirements_carry_real_validator_ids():
    """Requirements must reference validator ids the execution adapter can resolve."""
    adapter = AgentValidationPolicyAdapter()
    desc = OperationDescriptor(
        name="modify_python_file2",
        description="Modify python file",
        version="1",
        effects=(OperationEffectType.UPDATE,),
        metadata={"tags": ("code", "python")},
    )
    selection = adapter.select_policy(
        operation_descriptor=desc, stage=AgentValidationStage.POST_EXECUTION
    )
    all_validator_ids = {vid for r in selection.requirements for vid in r.validator_ids}
    assert "syntax_validator" in all_validator_ids
    assert "ast_validator" in all_validator_ids


def test_policy_adapter_publish_commit_gate_requirement():
    adapter = AgentValidationPolicyAdapter()
    desc = OperationDescriptor(
        name="publish_release",
        description="Publish release",
        version="1",
        effects=(OperationEffectType.PUBLISH,),
    )
    selection = adapter.select_policy(
        operation_descriptor=desc,
        stage=AgentValidationStage.PRE_COMMIT,
        commit_gate_required=True,
    )
    kinds = [r.validation_kind for r in selection.requirements]
    assert ValidationRequirementKind.COMMIT_GATE in kinds


def test_policy_adapter_read_only_no_commit_gate_at_pre_commit():
    adapter = AgentValidationPolicyAdapter()
    desc = OperationDescriptor(
        name="read_only_op",
        description="Read only",
        version="1",
        effects=(OperationEffectType.READ,),
    )
    selection = adapter.select_policy(
        operation_descriptor=desc,
        stage=AgentValidationStage.PRE_COMMIT,
        commit_gate_required=False,
    )
    kinds = [r.validation_kind for r in selection.requirements]
    assert ValidationRequirementKind.COMMIT_GATE not in kinds


def test_policy_adapter_rollback_validation_requirement():
    adapter = AgentValidationPolicyAdapter()
    selection = adapter.select_policy(
        stage=AgentValidationStage.POST_ROLLBACK, is_rollback=True
    )
    kinds = [r.validation_kind for r in selection.requirements]
    assert ValidationRequirementKind.POST_CONDITION in kinds
    assert all(
        r.stage == AgentValidationStage.POST_ROLLBACK for r in selection.requirements
    )


def test_policy_adapter_human_approval_does_not_replace_validation():
    adapter = AgentValidationPolicyAdapter()
    desc = OperationDescriptor(
        name="approved_dangerous_op",
        description="Dangerous op",
        version="1",
        effects=(OperationEffectType.UPDATE,),
    )
    selection = adapter.select_policy(
        operation_descriptor=desc, stage=AgentValidationStage.POST_EXECUTION
    )
    # Technical validation is still present despite any human approval flag; the
    # resolver signature does not even accept an "approved" override.
    assert "approved" not in inspect.signature(adapter.select_policy).parameters
    assert len(selection.requirements) > 0


def test_policy_adapter_cumulative_custom_requirements_merge():
    adapter = AgentValidationPolicyAdapter()
    desc = OperationDescriptor(
        name="read_with_custom",
        description="Read with extra custom check",
        version="1",
        effects=(OperationEffectType.READ,),
    )
    custom = ValidationRequirement(
        requirement_id="req-custom-extra",
        validation_kind=ValidationRequirementKind.CUSTOM,
        stage=AgentValidationStage.PRE_EXECUTION,
    )
    baseline = adapter.select_policy(
        operation_descriptor=desc, stage=AgentValidationStage.PRE_EXECUTION
    )
    with_custom = adapter.select_policy(
        operation_descriptor=desc,
        stage=AgentValidationStage.PRE_EXECUTION,
        custom_requirements=(custom,),
    )
    assert len(with_custom.requirements) == len(baseline.requirements) + 1
    assert any(r.requirement_id == "req-custom-extra" for r in with_custom.requirements)


def test_policy_adapter_cannot_downgrade_via_duplicate_custom_id():
    """An agent cannot use a duplicate requirement_id to silently drop the resolved one."""
    adapter = AgentValidationPolicyAdapter()
    desc = OperationDescriptor(
        name="delete_op_downgrade",
        description="Delete op",
        version="1",
        reversible=False,
        effects=(OperationEffectType.DELETE,),
    )
    baseline = adapter.select_policy(
        operation_descriptor=desc, stage=AgentValidationStage.PRE_EXECUTION
    )
    blocking_id = next(r.requirement_id for r in baseline.requirements if r.blocking)
    downgraded_duplicate = ValidationRequirement(
        requirement_id=blocking_id,
        validation_kind=ValidationRequirementKind.CUSTOM,
        stage=AgentValidationStage.PRE_EXECUTION,
        blocking=False,
    )
    selection = adapter.select_policy(
        operation_descriptor=desc,
        stage=AgentValidationStage.PRE_EXECUTION,
        custom_requirements=(downgraded_duplicate,),
    )
    # The original resolved (blocking) requirement is preserved; the duplicate is dropped.
    kept = [r for r in selection.requirements if r.requirement_id == blocking_id]
    assert len(kept) == 1
    assert kept[0].blocking is True


def test_policy_adapter_deterministic_ordering():
    adapter = AgentValidationPolicyAdapter()
    desc = OperationDescriptor(
        name="modify_python_deterministic",
        description="Modify",
        version="1",
        effects=(OperationEffectType.UPDATE,),
        metadata={"tags": ("code", "python")},
    )
    kinds_a = [
        r.validation_kind
        for r in adapter.select_policy(
            operation_descriptor=desc, stage=AgentValidationStage.POST_EXECUTION
        ).requirements
    ]
    kinds_b = [
        r.validation_kind
        for r in adapter.select_policy(
            operation_descriptor=desc, stage=AgentValidationStage.POST_EXECUTION
        ).requirements
    ]
    assert kinds_a == kinds_b


def test_policy_adapter_no_default_no_operation_descriptor_is_failsafe():
    adapter = AgentValidationPolicyAdapter()
    selection = adapter.select_policy(stage=AgentValidationStage.PRE_EXECUTION)
    assert len(selection.requirements) > 0
    assert all(r.required for r in selection.requirements)


def test_policy_adapter_resolution_failure_wraps_in_policy_selection_error():
    class BrokenResolver(ValidationRequirementResolver):
        def resolve_requirements(self, **kwargs):
            raise RuntimeError("boom")

    adapter = AgentValidationPolicyAdapter(resolver=BrokenResolver())
    with pytest.raises(ValidationPolicySelectionError) as exc_info:
        adapter.select_policy(stage=AgentValidationStage.PRE_EXECUTION)
    assert exc_info.value.__cause__ is not None


# ── 4. PRE-VALIDATION ────────────────────────────────────────────────────────


def test_pre_validation_passed_with_no_requirements():
    adapter = AgentValidationAdapter()
    req = AgentValidationRequest(
        id="val-pre-pass",
        run_id="run-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.PRE_EXECUTION,
    )
    res = adapter.validate(req)
    assert res.status == AgentValidationStatus.PASSED
    assert res.decision == AgentValidationDecision.CONTINUE


def test_pre_validation_blocked_decision_resolution():
    resolver = ValidationDecisionResolver()
    decision = resolver.resolve(
        stage=AgentValidationStage.PRE_EXECUTION,
        status=AgentValidationStatus.BLOCKED,
    )
    assert decision == AgentValidationDecision.BLOCK


def test_pre_validation_timed_out_retryable():
    resolver = ValidationDecisionResolver()
    decision = resolver.resolve(
        stage=AgentValidationStage.PRE_EXECUTION,
        status=AgentValidationStatus.TIMED_OUT,
        context_data={"retryable": True},
    )
    assert decision == AgentValidationDecision.RETRY


def test_pre_validation_timed_out_non_retryable_blocks():
    resolver = ValidationDecisionResolver()
    decision = resolver.resolve(
        stage=AgentValidationStage.PRE_EXECUTION,
        status=AgentValidationStatus.TIMED_OUT,
    )
    assert decision == AgentValidationDecision.BLOCK


def test_real_pipeline_syntax_error_blocks_post_execution():
    adapter = AgentValidationAdapter()
    req = AgentValidationRequest(
        id="val-real-syntax-fail",
        run_id="run-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.POST_EXECUTION,
        requirements=(
            ValidationRequirement(
                requirement_id="r-syntax",
                validation_kind=ValidationRequirementKind.SYNTAX,
                stage=AgentValidationStage.POST_EXECUTION,
                validator_ids=("syntax_validator",),
                resource_scope=(str(BAD_PY),),
            ),
        ),
        context_data={"project_root": str(BAD_PY.parent)},
    )
    res = adapter.validate(req)
    assert res.status == AgentValidationStatus.FAILED
    assert res.decision == AgentValidationDecision.BLOCK
    assert any("PYTHON_SYNTAX_ERROR" in reason for reason in res.blocking_reasons)
    assert any(f.failure_class == ValidationFailureClass.SYNTAX for f in res.findings)


def test_real_pipeline_syntax_passes_for_valid_file():
    adapter = AgentValidationAdapter()
    req = AgentValidationRequest(
        id="val-real-syntax-pass",
        run_id="run-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.POST_EXECUTION,
        requirements=(
            ValidationRequirement(
                requirement_id="r-syntax-ok",
                validation_kind=ValidationRequirementKind.SYNTAX,
                stage=AgentValidationStage.POST_EXECUTION,
                validator_ids=("syntax_validator",),
                resource_scope=(str(GOOD_PY),),
            ),
        ),
        context_data={"project_root": str(GOOD_PY.parent)},
    )
    res = adapter.validate(req)
    assert res.status == AgentValidationStatus.PASSED
    assert res.decision == AgentValidationDecision.CONTINUE


def test_real_pipeline_ast_step_depends_on_syntax():
    adapter = AgentValidationAdapter()
    req = AgentValidationRequest(
        id="val-real-ast",
        run_id="run-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.POST_EXECUTION,
        requirements=(
            ValidationRequirement(
                requirement_id="r-syntax",
                validation_kind=ValidationRequirementKind.SYNTAX,
                stage=AgentValidationStage.POST_EXECUTION,
                validator_ids=("syntax_validator",),
                resource_scope=(str(GOOD_PY),),
            ),
            ValidationRequirement(
                requirement_id="r-ast",
                validation_kind=ValidationRequirementKind.AST,
                stage=AgentValidationStage.POST_EXECUTION,
                validator_ids=("ast_validator",),
                resource_scope=(str(GOOD_PY),),
            ),
        ),
        context_data={"project_root": str(GOOD_PY.parent)},
    )
    res = adapter.validate(req)
    assert res.status == AgentValidationStatus.PASSED
    assert "steps" in res.validation_report


def test_missing_required_validator_adapter_fails_safe():
    adapter = AgentValidationAdapter()
    req = AgentValidationRequest(
        id="val-missing-adapter",
        run_id="run-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.POST_EXECUTION,
        requirements=(
            ValidationRequirement(
                requirement_id="r-unknown",
                validation_kind=ValidationRequirementKind.CUSTOM,
                stage=AgentValidationStage.POST_EXECUTION,
                required=True,
                validator_ids=("nonexistent_validator",),
            ),
        ),
    )
    with pytest.raises(ValidationAdapterError):
        adapter.validate(req)


def test_optional_missing_validator_adapter_is_skipped_not_failed():
    adapter = AgentValidationAdapter()
    req = AgentValidationRequest(
        id="val-optional-missing",
        run_id="run-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.POST_EXECUTION,
        requirements=(
            ValidationRequirement(
                requirement_id="r-optional-unknown",
                validation_kind=ValidationRequirementKind.CUSTOM,
                stage=AgentValidationStage.POST_EXECUTION,
                required=False,
                validator_ids=("nonexistent_validator",),
            ),
        ),
    )
    res = adapter.validate(req)
    assert res.status == AgentValidationStatus.PASSED


# ── 5. POST-VALIDATION & DECISION RESOLVER ───────────────────────────────────


def test_decision_resolver_continue():
    resolver = ValidationDecisionResolver()
    decision = resolver.resolve(
        stage=AgentValidationStage.POST_EXECUTION,
        status=AgentValidationStatus.PASSED,
    )
    assert decision == AgentValidationDecision.CONTINUE


def test_decision_resolver_continue_with_warnings():
    resolver = ValidationDecisionResolver()
    decision = resolver.resolve(
        stage=AgentValidationStage.POST_EXECUTION,
        status=AgentValidationStatus.PASSED_WITH_WARNINGS,
    )
    assert decision == AgentValidationDecision.CONTINUE


def test_decision_resolver_rollback_on_regression():
    resolver = ValidationDecisionResolver()
    findings = (
        ValidationFinding(
            finding_id="f-reg",
            rule_id="rule-reg",
            severity="CRITICAL",
            message="Regression detected",
            failure_class=ValidationFailureClass.REGRESSION,
        ),
    )
    decision = resolver.resolve(
        stage=AgentValidationStage.POST_EXECUTION,
        status=AgentValidationStatus.FAILED,
        findings=findings,
        context_data={"rollback_available": True},
    )
    assert decision == AgentValidationDecision.ROLLBACK


def test_decision_resolver_no_rollback_without_availability():
    resolver = ValidationDecisionResolver()
    findings = (
        ValidationFinding(
            finding_id="f-reg2",
            rule_id="rule-reg",
            severity="CRITICAL",
            message="Regression detected",
            failure_class=ValidationFailureClass.REGRESSION,
        ),
    )
    decision = resolver.resolve(
        stage=AgentValidationStage.POST_EXECUTION,
        status=AgentValidationStatus.FAILED,
        findings=findings,
        context_data={"rollback_available": False},
    )
    assert decision == AgentValidationDecision.BLOCK


def test_decision_resolver_retry_transient_failure():
    resolver = ValidationDecisionResolver()
    decision = resolver.resolve(
        stage=AgentValidationStage.POST_EXECUTION,
        status=AgentValidationStatus.FAILED,
        context_data={"transient_failure": True, "retry_allowed": True},
    )
    assert decision == AgentValidationDecision.RETRY


def test_decision_resolver_replan_invalid_plan():
    resolver = ValidationDecisionResolver()
    decision = resolver.resolve(
        stage=AgentValidationStage.POST_EXECUTION,
        status=AgentValidationStatus.FAILED,
        context_data={"plan_invalid": True},
    )
    assert decision == AgentValidationDecision.REPLAN


def test_decision_resolver_escalate_missing_approval():
    resolver = ValidationDecisionResolver()
    decision = resolver.resolve(
        stage=AgentValidationStage.POST_EXECUTION,
        status=AgentValidationStatus.BLOCKED,
        context_data={"requires_approval": True},
    )
    assert decision == AgentValidationDecision.ESCALATE


def test_decision_resolver_escalate_on_policy_finding():
    resolver = ValidationDecisionResolver()
    findings = (
        ValidationFinding(
            finding_id="f-pol",
            rule_id="rule-pol",
            severity="ERROR",
            message="Policy finding",
            failure_class=ValidationFailureClass.POLICY,
        ),
    )
    decision = resolver.resolve(
        stage=AgentValidationStage.POST_EXECUTION,
        status=AgentValidationStatus.BLOCKED,
        findings=findings,
    )
    assert decision == AgentValidationDecision.ESCALATE


def test_decision_resolver_pause_requested():
    resolver = ValidationDecisionResolver()
    decision = resolver.resolve(
        stage=AgentValidationStage.POST_EXECUTION,
        status=AgentValidationStatus.BLOCKED,
        context_data={"requires_pause": True},
    )
    assert decision == AgentValidationDecision.PAUSE


def test_decision_resolver_escalate_requires_human():
    resolver = ValidationDecisionResolver()
    decision = resolver.resolve(
        stage=AgentValidationStage.POST_EXECUTION,
        status=AgentValidationStatus.FAILED,
        context_data={"requires_human": True},
    )
    assert decision == AgentValidationDecision.ESCALATE


def test_decision_resolver_abort_fatal_error():
    resolver = ValidationDecisionResolver()
    decision = resolver.resolve(
        stage=AgentValidationStage.POST_EXECUTION,
        status=AgentValidationStatus.FAILED,
        context_data={"fatal": True},
    )
    assert decision == AgentValidationDecision.ABORT


def test_decision_resolver_default_blocked_status_blocks():
    resolver = ValidationDecisionResolver()
    decision = resolver.resolve(
        stage=AgentValidationStage.POST_EXECUTION,
        status=AgentValidationStatus.BLOCKED,
    )
    assert decision == AgentValidationDecision.BLOCK


def test_decision_resolver_default_failed_status_blocks():
    resolver = ValidationDecisionResolver()
    decision = resolver.resolve(
        stage=AgentValidationStage.POST_EXECUTION,
        status=AgentValidationStatus.FAILED,
    )
    assert decision == AgentValidationDecision.BLOCK


def test_decision_resolver_post_rollback_timed_out_retries():
    resolver = ValidationDecisionResolver()
    decision = resolver.resolve(
        stage=AgentValidationStage.POST_ROLLBACK,
        status=AgentValidationStatus.TIMED_OUT,
    )
    assert decision == AgentValidationDecision.RETRY


# ── 6. COMMIT GATE INTEGRATION (Phase 7 real evaluator) ──────────────────────


def test_commit_gate_authorized_real_evaluator_zero_required_steps():
    adapter = AgentValidationAdapter()
    req = AgentValidationRequest(
        id="val-cg-pass",
        run_id="run-cg",
        iteration_id="iter-cg",
        operation_request_id="op-cg",
        stage=AgentValidationStage.PRE_COMMIT,
        requirements=(
            ValidationRequirement(
                requirement_id="r-gate",
                validation_kind=ValidationRequirementKind.COMMIT_GATE,
                stage=AgentValidationStage.PRE_COMMIT,
            ),
        ),
        context_data={
            "project_root": str(GOOD_PY.parent),
            "policy_name": "documentation_only",
        },
    )
    res = adapter.validate(req)
    assert res.commit_gate_result is not None
    assert res.commit_gate_result["authorized"] is True
    assert res.decision == AgentValidationDecision.CONTINUE


def test_commit_gate_denied_for_incomplete_required_steps():
    adapter = AgentValidationAdapter()
    req = AgentValidationRequest(
        id="val-cg-incomplete",
        run_id="run-cg",
        iteration_id="iter-cg",
        operation_request_id="op-cg",
        stage=AgentValidationStage.PRE_COMMIT,
        requirements=(
            ValidationRequirement(
                requirement_id="r-syntax",
                validation_kind=ValidationRequirementKind.SYNTAX,
                stage=AgentValidationStage.PRE_COMMIT,
                validator_ids=("syntax_validator",),
                resource_scope=(str(GOOD_PY),),
            ),
            ValidationRequirement(
                requirement_id="r-gate",
                validation_kind=ValidationRequirementKind.COMMIT_GATE,
                stage=AgentValidationStage.PRE_COMMIT,
            ),
        ),
        context_data={
            "project_root": str(GOOD_PY.parent),
            "policy_name": "small_change",
        },
    )
    res = adapter.validate(req)
    assert res.commit_gate_result["authorized"] is False
    assert res.status == AgentValidationStatus.BLOCKED
    assert res.decision == AgentValidationDecision.BLOCK
    assert any(
        code == "required_step_missing"
        for code in res.commit_gate_result["reason_codes"]
    )


def test_commit_gate_denied_blocks_on_real_blocking_finding():
    adapter = AgentValidationAdapter()
    req = AgentValidationRequest(
        id="val-cg-bad-syntax",
        run_id="run-cg",
        iteration_id="iter-cg",
        operation_request_id="op-cg",
        stage=AgentValidationStage.PRE_COMMIT,
        requirements=(
            ValidationRequirement(
                requirement_id="r-syntax",
                validation_kind=ValidationRequirementKind.SYNTAX,
                stage=AgentValidationStage.PRE_COMMIT,
                validator_ids=("syntax_validator",),
                resource_scope=(str(BAD_PY),),
            ),
            ValidationRequirement(
                requirement_id="r-gate",
                validation_kind=ValidationRequirementKind.COMMIT_GATE,
                stage=AgentValidationStage.PRE_COMMIT,
            ),
        ),
        context_data={
            "project_root": str(BAD_PY.parent),
            "policy_name": "documentation_only",
        },
    )
    res = adapter.validate(req)
    assert res.commit_gate_result["authorized"] is False
    assert res.decision == AgentValidationDecision.BLOCK
    assert any(
        code == "blocking_finding" for code in res.commit_gate_result["reason_codes"]
    )


def test_commit_gate_resource_fingerprint_mismatch_blocks():
    adapter = AgentValidationAdapter()
    expected_fp = _resource_fingerprint((str(GOOD_PY),))
    req = AgentValidationRequest(
        id="val-cg-fp-mismatch",
        run_id="run-cg",
        iteration_id="iter-cg",
        operation_request_id="op-cg",
        stage=AgentValidationStage.PRE_COMMIT,
        requirements=(
            ValidationRequirement(
                requirement_id="r-gate",
                validation_kind=ValidationRequirementKind.COMMIT_GATE,
                stage=AgentValidationStage.PRE_COMMIT,
                resource_scope=(str(GOOD_PY),),
            ),
        ),
        context_data={
            "project_root": str(GOOD_PY.parent),
            "policy_name": "documentation_only",
            "expected_resource_fingerprint": "stale-value-not-matching",
        },
    )
    assert expected_fp != "stale-value-not-matching"
    res = adapter.validate(req)
    assert res.commit_gate_result["authorized"] is False
    assert "resource_fingerprint_mismatch" in res.commit_gate_result["reason_codes"]
    assert res.decision == AgentValidationDecision.BLOCK


def test_commit_gate_resource_fingerprint_match_authorizes():
    adapter = AgentValidationAdapter()
    matching_fp = _resource_fingerprint((str(GOOD_PY),))
    req = AgentValidationRequest(
        id="val-cg-fp-match",
        run_id="run-cg",
        iteration_id="iter-cg",
        operation_request_id="op-cg",
        stage=AgentValidationStage.PRE_COMMIT,
        requirements=(
            ValidationRequirement(
                requirement_id="r-gate",
                validation_kind=ValidationRequirementKind.COMMIT_GATE,
                stage=AgentValidationStage.PRE_COMMIT,
                resource_scope=(str(GOOD_PY),),
            ),
        ),
        context_data={
            "project_root": str(GOOD_PY.parent),
            "policy_name": "documentation_only",
            "expected_resource_fingerprint": matching_fp,
        },
    )
    res = adapter.validate(req)
    assert res.commit_gate_result["authorized"] is True
    assert res.decision == AgentValidationDecision.CONTINUE


def test_commit_gate_denied_maps_to_escalate_on_authorization_denied():
    resolver = ValidationDecisionResolver()
    cg_eval = CommitGateEvaluation(
        authorized=False,
        decision=AgentValidationDecision.BLOCK,
        reason_codes=("authorization_denied",),
    )
    decision = resolver.resolve(
        stage=AgentValidationStage.PRE_COMMIT,
        status=AgentValidationStatus.BLOCKED,
        commit_gate_eval=cg_eval,
    )
    assert decision == AgentValidationDecision.ESCALATE


def test_commit_gate_denied_maps_to_rollback_on_repository_state_unsafe():
    resolver = ValidationDecisionResolver()
    cg_eval = CommitGateEvaluation(
        authorized=False,
        decision=AgentValidationDecision.ROLLBACK,
        reason_codes=("repository_state_unsafe",),
    )
    decision = resolver.resolve(
        stage=AgentValidationStage.PRE_COMMIT,
        status=AgentValidationStatus.BLOCKED,
        commit_gate_eval=cg_eval,
    )
    assert decision == AgentValidationDecision.ROLLBACK


def test_commit_gate_denied_defaults_to_block_for_other_reason_codes():
    resolver = ValidationDecisionResolver()
    cg_eval = CommitGateEvaluation(
        authorized=False,
        decision=AgentValidationDecision.BLOCK,
        reason_codes=("policy_forbids_commit",),
    )
    decision = resolver.resolve(
        stage=AgentValidationStage.PRE_COMMIT,
        status=AgentValidationStatus.BLOCKED,
        commit_gate_eval=cg_eval,
    )
    assert decision == AgentValidationDecision.BLOCK


def test_commit_gate_authorized_short_circuits_other_status_logic():
    resolver = ValidationDecisionResolver()
    cg_eval = CommitGateEvaluation(
        authorized=True,
        decision=AgentValidationDecision.CONTINUE,
    )
    decision = resolver.resolve(
        stage=AgentValidationStage.PRE_COMMIT,
        status=AgentValidationStatus.PASSED,
        commit_gate_eval=cg_eval,
    )
    assert decision == AgentValidationDecision.CONTINUE


# ── 7. INTEGRACIÓN CON AGENT EXECUTION ADAPTER ────────────────────────────────


def test_agent_execution_adapter_with_validation_success():
    val_adapter = AgentValidationAdapter()
    reg = InMemoryAgentOperationRegistry()
    repo = InMemoryAgentOperationExecutionRepository()

    desc = OperationDescriptor(
        name="op_test",
        description="Test operation",
        version="1",
    )
    reg.register(desc)

    def delegate(req: AgentOperationRequest) -> dict:
        return {"success": True, "artifacts": ("art-1",)}

    exec_adapter = AgentExecutionAdapter(
        registry=reg,
        repository=repo,
        execution_delegate=delegate,
        validation_adapter=val_adapter,
    )

    op_req = AgentOperationRequest(
        id="op-req-val-1",
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="t-1",
        operation_name="op_test",
        idempotency_key="key-val-1",
    )

    res = exec_adapter.execute(op_req)
    assert res.success is True
    assert res.status == AgentOperationExecutionStatus.COMPLETED
    assert len(res.validation_result_ids) == 2  # pre + post


def test_agent_execution_adapter_failsafe_missing_validation_adapter():
    reg = InMemoryAgentOperationRegistry()
    desc = OperationDescriptor(
        name="op_val_mandated",
        description="Mandated validation op",
        version="1",
    )
    reg.register(desc)

    exec_adapter = AgentExecutionAdapter(registry=reg)

    op_req = AgentOperationRequest(
        id="op-req-val-missing",
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="t-1",
        operation_name="op_val_mandated",
        idempotency_key="key-val-missing",
        metadata={"requires_validation": True},
    )

    with pytest.raises(ValidationAdapterError):
        exec_adapter.execute(op_req)


def test_agent_execution_adapter_optional_validation_no_adapter_required():
    reg = InMemoryAgentOperationRegistry()
    desc = OperationDescriptor(
        name="op_optional_val", description="Optional", version="1"
    )
    reg.register(desc)

    exec_adapter = AgentExecutionAdapter(
        registry=reg, execution_delegate=lambda req: {"success": True}
    )
    op_req = AgentOperationRequest(
        id="op-req-optional-val",
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="t-1",
        operation_name="op_optional_val",
        idempotency_key="key-optional-val",
    )
    res = exec_adapter.execute(op_req)
    assert res.success is True
    assert res.validation_result_ids == ()


def test_agent_execution_adapter_pre_validation_blocks_delegate_call():
    val_adapter = _FixedDecisionAdapter(
        AgentValidationDecision.BLOCK, AgentValidationStatus.BLOCKED
    )
    reg = InMemoryAgentOperationRegistry()
    desc = OperationDescriptor(name="op_block", description="Block op", version="1")
    reg.register(desc)

    delegate_called = False

    def delegate(req):
        nonlocal delegate_called
        delegate_called = True
        return {"success": True}

    exec_adapter = AgentExecutionAdapter(
        registry=reg, execution_delegate=delegate, validation_adapter=val_adapter
    )

    op_req = AgentOperationRequest(
        id="op-req-blocked",
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="t-1",
        operation_name="op_block",
        idempotency_key="key-blocked",
    )

    res = exec_adapter.execute(op_req)
    assert res.success is False
    assert res.status == AgentOperationExecutionStatus.BLOCKED
    assert delegate_called is False


def test_agent_execution_adapter_post_validation_blocks_completion():
    class _PrePassPostBlockAdapter(AgentValidationAdapter):
        def __init__(self):
            self._calls = 0

        def validate(self, request, exec_context=None):
            self._calls += 1
            decision = (
                AgentValidationDecision.CONTINUE
                if self._calls == 1
                else AgentValidationDecision.BLOCK
            )
            status = (
                AgentValidationStatus.PASSED
                if self._calls == 1
                else AgentValidationStatus.BLOCKED
            )
            return AgentValidationResult(
                request_id=request.id,
                run_id=request.run_id,
                iteration_id=request.iteration_id,
                operation_request_id=request.operation_request_id,
                stage=request.stage,
                status=status,
                decision=decision,
            )

    reg = InMemoryAgentOperationRegistry()
    desc = OperationDescriptor(
        name="op_post_block", description="Post block", version="1"
    )
    reg.register(desc)

    exec_adapter = AgentExecutionAdapter(
        registry=reg,
        execution_delegate=lambda req: {"success": True},
        validation_adapter=_PrePassPostBlockAdapter(),
    )
    op_req = AgentOperationRequest(
        id="op-req-post-block",
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="t-1",
        operation_name="op_post_block",
        idempotency_key="key-post-block",
    )
    res = exec_adapter.execute(op_req)
    assert res.success is False
    assert res.status == AgentOperationExecutionStatus.VALIDATION_FAILED
    assert len(res.validation_result_ids) == 2


def test_agent_execution_adapter_plain_execution_failure_not_mislabeled_as_validation():
    """A delegate-reported failure with no post-validation run must not become VALIDATION_FAILED."""
    val_adapter = AgentValidationAdapter()
    reg = InMemoryAgentOperationRegistry()
    desc = OperationDescriptor(
        name="op_exec_fail", description="Exec fail", version="1"
    )
    reg.register(desc)

    exec_adapter = AgentExecutionAdapter(
        registry=reg,
        execution_delegate=lambda req: {"success": False},
        validation_adapter=val_adapter,
    )
    op_req = AgentOperationRequest(
        id="op-req-exec-fail",
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="t-1",
        operation_name="op_exec_fail",
        idempotency_key="key-exec-fail",
    )
    res = exec_adapter.execute(op_req)
    assert res.success is False
    assert res.status == AgentOperationExecutionStatus.FAILED


def test_agent_execution_adapter_no_duplicate_execution_on_retry():
    call_count = 0

    def delegate(req):
        nonlocal call_count
        call_count += 1
        return {"success": True}

    reg = InMemoryAgentOperationRegistry()
    desc = OperationDescriptor(
        name="op_idempotent", description="Idempotent", version="1"
    )
    reg.register(desc)
    exec_adapter = AgentExecutionAdapter(registry=reg, execution_delegate=delegate)

    op_req = AgentOperationRequest(
        id="op-req-idempotent-1",
        agent_run_id="run-1",
        workflow_id="wf-1",
        task_id="t-1",
        operation_name="op_idempotent",
        idempotency_key="key-idempotent-retry",
    )
    res1 = exec_adapter.execute(op_req)
    res2 = exec_adapter.execute(op_req)
    assert call_count == 1
    assert res1.id == res2.id


# ── 8. INTEGRACIÓN CON RUNTIME LOOP ───────────────────────────────────────────


@pytest.mark.parametrize(
    "decision,status,expected_status,expect_success",
    [
        (
            AgentValidationDecision.CONTINUE,
            AgentValidationStatus.PASSED,
            AgentRuntimeStatus.EVALUATING,
            True,
        ),
        (
            AgentValidationDecision.BLOCK,
            AgentValidationStatus.BLOCKED,
            AgentRuntimeStatus.BLOCKED,
            False,
        ),
        (
            AgentValidationDecision.RETRY,
            AgentValidationStatus.FAILED,
            AgentRuntimeStatus.RECOVERING,
            False,
        ),
        (
            AgentValidationDecision.REPLAN,
            AgentValidationStatus.FAILED,
            AgentRuntimeStatus.PLANNING,
            False,
        ),
        (
            AgentValidationDecision.ROLLBACK,
            AgentValidationStatus.FAILED,
            AgentRuntimeStatus.RECOVERING,
            False,
        ),
        (
            AgentValidationDecision.ESCALATE,
            AgentValidationStatus.BLOCKED,
            AgentRuntimeStatus.WAITING_FOR_APPROVAL,
            False,
        ),
        (
            AgentValidationDecision.PAUSE,
            AgentValidationStatus.BLOCKED,
            AgentRuntimeStatus.PAUSED,
            False,
        ),
        (
            AgentValidationDecision.ABORT,
            AgentValidationStatus.FAILED,
            AgentRuntimeStatus.FAILED,
            False,
        ),
    ],
)
def test_runtime_validate_handler_maps_every_decision(
    decision, status, expected_status, expect_success
):
    handler = ValidateHandler(adapter=_FixedDecisionAdapter(decision, status))
    val_req = AgentValidationRequest(
        id=f"req-loop-{decision.value}",
        run_id="run-loop",
        iteration_id="iter-loop",
        operation_request_id="op-loop",
        stage=AgentValidationStage.POST_EXECUTION,
    )
    run = _make_agent_run("run-loop", AgentRuntimeStatus.VALIDATING)
    ctx = _make_step_context(run, {"validation_request": val_req})

    step_res = handler.execute(ctx)
    assert step_res.success is expect_success
    assert step_res.next_status == expected_status
    # Every mapped decision must be a state machine-valid transition from "validating".
    AgentRuntimeStateMachine.validate_transition("validating", expected_status.value)


def test_runtime_validate_handler_no_adapter_falls_back_to_default_continue():
    handler = ValidateHandler(adapter=None)
    run = _make_agent_run("run-loop", AgentRuntimeStatus.VALIDATING)
    ctx = _make_step_context(run, {})
    step_res = handler.execute(ctx)
    assert step_res.success is True
    assert step_res.next_status == AgentRuntimeStatus.EVALUATING


def test_runtime_validate_handler_unknown_decision_raises_not_continue():
    class _UnknownDecisionAdapter(AgentValidationAdapter):
        def validate(self, request, exec_context=None):
            result = AgentValidationResult(
                request_id=request.id,
                run_id=request.run_id,
                iteration_id=request.iteration_id,
                operation_request_id=request.operation_request_id,
                stage=request.stage,
                status=AgentValidationStatus.FAILED,
                decision=AgentValidationDecision.CONTINUE,
            )
            # Force an out-of-band decision value that the handler cannot map,
            # bypassing the closed-enum guarantee to exercise the fail-safe branch.
            object.__setattr__(result, "decision", "unmapped_decision")
            return result

    handler = ValidateHandler(adapter=_UnknownDecisionAdapter())
    val_req = AgentValidationRequest(
        id="req-loop-unknown",
        run_id="run-loop",
        iteration_id="iter-loop",
        operation_request_id="op-loop",
        stage=AgentValidationStage.POST_EXECUTION,
    )
    run = _make_agent_run("run-loop", AgentRuntimeStatus.VALIDATING)
    ctx = _make_step_context(run, {"validation_request": val_req})

    with pytest.raises(RuntimeStepExecutionError):
        handler.execute(ctx)


def test_runtime_state_machine_rejects_invalid_transition_from_validating():
    with pytest.raises(RuntimeTransitionNotAllowedError):
        AgentRuntimeStateMachine.validate_transition("validating", "completed")


def test_runtime_state_machine_rejects_transition_from_terminal_state():
    with pytest.raises(RuntimeTransitionNotAllowedError):
        AgentRuntimeStateMachine.validate_transition("failed", "validating")


def test_runtime_state_machine_allows_all_documented_validating_transitions():
    expected = {
        "evaluating",
        "recovering",
        "planning",
        "waiting_for_approval",
        "blocked",
        "failed",
        "paused",
        "aborted",
    }
    assert AgentRuntimeStateMachine.allowed_next_states("validating") == expected


# ── 9. SEGURIDAD Y DEUDA ─────────────────────────────────────────────────────


def test_infrastructure_error_wrapping_from_buggy_pipeline():
    class BuggyPipeline:
        def run(self, ctx, steps, **kwargs):
            raise ValueError("Internal pipe crash")

    adapter = AgentValidationAdapter(pipeline=BuggyPipeline())  # type: ignore
    req = AgentValidationRequest(
        id="val-req-crash",
        run_id="run-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.POST_EXECUTION,
        requirements=(
            ValidationRequirement(
                requirement_id="r1",
                validation_kind=ValidationRequirementKind.SYNTAX,
                stage=AgentValidationStage.POST_EXECUTION,
                validator_ids=("syntax_validator",),
            ),
        ),
    )

    with pytest.raises(AgentValidationError) as exc_info:
        adapter.validate(req)
    assert "infrastructure error" in str(exc_info.value).lower()
    assert exc_info.value.__cause__ is not None


def test_infrastructure_error_wrapping_from_buggy_commit_gate():
    class BuggyGate:
        @staticmethod
        def evaluate(result, policy):
            raise RuntimeError("gate crash")

    adapter = AgentValidationAdapter(commit_gate_evaluator=BuggyGate)
    req = AgentValidationRequest(
        id="val-req-gate-crash",
        run_id="run-1",
        iteration_id="iter-1",
        operation_request_id="op-1",
        stage=AgentValidationStage.PRE_COMMIT,
        context_data={"project_root": str(GOOD_PY.parent)},
    )
    with pytest.raises(AgentValidationError) as exc_info:
        adapter.validate(req)
    assert exc_info.value.__cause__ is not None


def test_no_subprocess_or_shell_usage_in_validation_adapter_sources():
    forbidden_pattern = re.compile(
        r"\bsubprocess\b|\bos\.system\(|shell\s*=\s*True|\beval\(|\bexec\("
    )
    source_files = [
        "cmm/agent_runtime/validation_execution_adapter.py",
        "cmm/agent_runtime/validation_policy_adapter.py",
        "cmm/agent_runtime/validation_integration_repository.py",
        "cmm/agent_runtime/validation_integration_contracts.py",
    ]
    for rel_path in source_files:
        text = Path(rel_path).read_text()
        assert not forbidden_pattern.search(text), (
            f"forbidden pattern found in {rel_path}"
        )


def test_no_bare_except_pass_in_validation_adapter_sources():
    source_files = [
        "cmm/agent_runtime/validation_execution_adapter.py",
        "cmm/agent_runtime/validation_policy_adapter.py",
        "cmm/agent_runtime/validation_integration_repository.py",
    ]
    for rel_path in source_files:
        tree = ast.parse(Path(rel_path).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                is_noop = len(node.body) == 1 and isinstance(node.body[0], ast.Pass)
                assert not is_noop, f"silent bare except in {rel_path}"


def test_all_agent_validation_error_raises_preserve_cause():
    """Every `raise ...Error(...)` inside an except block in the adapter must chain `from`."""
    tree = ast.parse(
        Path("cmm/agent_runtime/validation_execution_adapter.py").read_text()
    )
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                for stmt in ast.walk(handler):
                    if (
                        isinstance(stmt, ast.Raise)
                        and stmt.exc is not None
                        and isinstance(stmt.exc, ast.Call)
                    ):
                        assert stmt.cause is not None, (
                            "raise inside except block must use 'from' to preserve cause"
                        )


def test_stale_expected_fingerprint_without_resource_scope_does_not_authorize_falsely():
    """An expected fingerprint with an empty resource scope must not be silently ignored as a pass."""
    adapter = AgentValidationAdapter()
    req = AgentValidationRequest(
        id="val-cg-no-scope",
        run_id="run-cg",
        iteration_id="iter-cg",
        operation_request_id="op-cg",
        stage=AgentValidationStage.PRE_COMMIT,
        requirements=(
            ValidationRequirement(
                requirement_id="r-gate",
                validation_kind=ValidationRequirementKind.COMMIT_GATE,
                stage=AgentValidationStage.PRE_COMMIT,
            ),
        ),
        context_data={
            "project_root": str(GOOD_PY.parent),
            "policy_name": "documentation_only",
            "expected_resource_fingerprint": "irrelevant-because-no-scope",
        },
    )
    res = adapter.validate(req)
    # No resource_scope means nothing to compare; authorization follows the real
    # gate outcome only (documentation_only + zero required steps => authorized).
    assert res.commit_gate_result["authorized"] is True


def test_requires_approval_flag_does_not_bypass_blocking_syntax_failure():
    resolver = ValidationDecisionResolver()
    findings = (
        ValidationFinding(
            finding_id="f-syntax-approval",
            rule_id="PYTHON_SYNTAX_ERROR",
            severity="ERROR",
            message="invalid syntax",
            failure_class=ValidationFailureClass.SYNTAX,
        ),
    )
    decision = resolver.resolve(
        stage=AgentValidationStage.POST_EXECUTION,
        status=AgentValidationStatus.FAILED,
        findings=findings,
        context_data={"requires_approval": True},
    )
    # requires_approval only matters for BLOCKED status; a technical FAILED
    # syntax finding still results in BLOCK, never a silent CONTINUE.
    assert decision != AgentValidationDecision.CONTINUE


def test_validation_repository_protocol_export_matches_implementation():
    from cmm.agent_runtime.validation_integration_repository import (
        AgentValidationRepository,
        InMemoryAgentValidationRepository,
    )

    for name in (
        "add_request",
        "get_request",
        "add_result",
        "get_result",
        "get_results_by_run_id",
        "get_results_by_operation_request_id",
        "find_by_idempotency_key",
    ):
        assert hasattr(InMemoryAgentValidationRepository, name)
        assert hasattr(AgentValidationRepository, name)
