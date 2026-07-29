"""Phase 9.16 – Recovery Manager Comprehensive Test Suite.

Exhaustive unit test suite covering contracts, repository, error classification,
backoff calculations, policy evaluators, decision engine, strategy executors,
RecoveryManager workflows, invariants, and security rules (130+ tests).
"""

import threading
from dataclasses import FrozenInstanceError

import pytest

from cmm.agent_runtime import (
    AgentValidationStage,
    AskUserStrategyExecutor,
    BackoffStrategy,
    CheckpointStatus,
    CompletePartiallyStrategyExecutor,
    ErrorClassification,
    EscalationPolicy,
    EscalationPolicyEvaluator,
    EscalationTarget,
    InMemoryRecoveryRepository,
    RecoveryAttempt,
    RecoveryBackoffCalculator,
    RecoveryBackoffError,
    RecoveryBudgetError,
    RecoveryBudgetSnapshot,
    RecoveryContext,
    RecoveryContextError,
    RecoveryDecision,
    RecoveryDecisionEngine,
    RecoveryDecisionError,
    RecoveryErrorClass,
    RecoveryErrorClassifier,
    RecoveryEvidence,
    RecoveryExecutionResult,
    RecoveryIdempotencyError,
    RecoveryManager,
    RecoveryReasonCode,
    RecoveryRepositoryError,
    RecoveryRiskAssessment,
    RecoveryStatus,
    RecoveryStrategy,
    RecoveryStrategyUnavailableError,
    ReloadResourceStrategyExecutor,
    ReobserveStrategyExecutor,
    ReplanStrategyExecutor,
    RetryLaterStrategyExecutor,
    RetryPolicy,
    RetryPolicyEvaluator,
    RetryStrategyExecutor,
    RollbackPolicy,
    RollbackPolicyEvaluator,
    RollbackStrategyExecutor,
    SkipOptionalTaskStrategyExecutor,
    TerminalStrategyExecutor,
    compute_recovery_context_fingerprint,
)
from cmm.agent_runtime.errors import (
    ApprovalError,
    BudgetExhaustedError,
    IrreversibleOperationError,
    ObservationPermissionError,
    TransactionRollbackError,
)
from cmm.agent_runtime.runtime_state_machine import AgentRuntimeStateMachine

# ── Helper Fixtures ───────────────────────────────────────────────────────────


def make_context(
    context_id: str = "ctx-1",
    agent_run_id: str = "run-1",
    error: dict | None = None,
    checkpoint_ids: tuple = (),
    retry_history: tuple = (),
    remaining_budget: dict | None = None,
    side_effects: tuple = (),
    failed_operation_id: str = "op-1",
    constraints: tuple = (),
    metadata: dict | None = None,
) -> RecoveryContext:
    err = (
        error
        if error is not None
        else {"error_type": "TransientNetworkError", "message": "Connection reset"}
    )
    budget = (
        remaining_budget
        if remaining_budget is not None
        else {"operations_remaining": 10}
    )
    meta = metadata if metadata is not None else {}
    return RecoveryContext(
        recovery_context_id=context_id,
        agent_run_id=agent_run_id,
        goal_id="goal-1",
        workflow_id="wf-1",
        iteration_id="iter-1",
        failed_task_id="task-1",
        failed_operation_id=failed_operation_id,
        error=err,
        checkpoint_ids=checkpoint_ids,
        retry_history=retry_history,
        remaining_budget=budget,
        side_effects=side_effects,
        constraints=constraints,
        metadata=meta,
    )


# ── 1. Contracts & Immutability Tests ──────────────────────────────────────────


def test_recovery_context_immutability():
    ctx = make_context()
    with pytest.raises(FrozenInstanceError):
        ctx.recovery_context_id = "other"  # type: ignore
    with pytest.raises(TypeError):
        ctx.error["new_key"] = "val"  # type: ignore


def test_recovery_context_invalid_ids():
    with pytest.raises(RecoveryContextError):
        RecoveryContext(
            recovery_context_id="",
            agent_run_id="run-1",
            goal_id="g1",
            workflow_id="w1",
            iteration_id="i1",
            failed_task_id="t1",
            failed_operation_id="o1",
            error={},
        )
    with pytest.raises(RecoveryContextError):
        RecoveryContext(
            recovery_context_id="c1",
            agent_run_id="",
            goal_id="g1",
            workflow_id="w1",
            iteration_id="i1",
            failed_task_id="t1",
            failed_operation_id="o1",
            error={},
        )


def test_recovery_context_serialization():
    ctx = make_context()
    d = ctx.to_dict()
    assert d["recovery_context_id"] == "ctx-1"
    assert d["agent_run_id"] == "run-1"
    restored = RecoveryContext.from_dict(d)
    assert restored.recovery_context_id == ctx.recovery_context_id
    assert restored.fingerprint == ctx.fingerprint


def test_recovery_decision_immutability():
    dec = RecoveryDecision(
        recovery_decision_id="dec-1",
        recovery_context_id="ctx-1",
        strategy=RecoveryStrategy.RETRY,
    )
    with pytest.raises(FrozenInstanceError):
        dec.strategy = RecoveryStrategy.FAIL  # type: ignore


def test_recovery_decision_invalid_ids():
    with pytest.raises(RecoveryDecisionError):
        RecoveryDecision(
            recovery_decision_id="",
            recovery_context_id="ctx-1",
            strategy=RecoveryStrategy.RETRY,
        )
    with pytest.raises(RecoveryDecisionError):
        RecoveryDecision(
            recovery_decision_id="dec-1",
            recovery_context_id="",
            strategy=RecoveryStrategy.RETRY,
        )


def test_recovery_decision_serialization():
    dec = RecoveryDecision(
        recovery_decision_id="dec-1",
        recovery_context_id="ctx-1",
        strategy=RecoveryStrategy.RETRY,
        reason_codes=(RecoveryReasonCode.TRANSIENT_ERROR,),
        delay_seconds=2.5,
    )
    d = dec.to_dict()
    assert d["recovery_decision_id"] == "dec-1"
    assert d["strategy"] == "retry"
    assert d["delay_seconds"] == 2.5
    restored = RecoveryDecision.from_dict(d)
    assert restored.recovery_decision_id == dec.recovery_decision_id
    assert restored.strategy == RecoveryStrategy.RETRY


def test_recovery_attempt_invalid_index():
    with pytest.raises(RecoveryContextError):
        RecoveryAttempt(
            attempt_index=0,
            strategy=RecoveryStrategy.RETRY,
            started_at="2026-07-26T00:00:00Z",
        )


def test_fingerprint_computation_determinism():
    f1 = compute_recovery_context_fingerprint(
        "c1", "r1", "g1", "w1", "i1", "t1", "o1", {"err": 1}, "2026-07-26T00:00:00Z"
    )
    f2 = compute_recovery_context_fingerprint(
        "c1", "r1", "g1", "w1", "i1", "t1", "o1", {"err": 1}, "2026-07-26T00:00:00Z"
    )
    assert f1 == f2
    assert len(f1) == 64


def test_recovery_evidence_creation():
    ev = RecoveryEvidence(
        evidence_id="ev-1",
        recovery_context_id="ctx-1",
        error_summary="Test summary",
        logs=("log1", "log2"),
    )
    assert ev.evidence_id == "ev-1"
    assert len(ev.logs) == 2
    d = ev.to_dict()
    assert d["error_summary"] == "Test summary"


def test_recovery_risk_assessment_creation():
    risk = RecoveryRiskAssessment(
        risk_score=0.75,
        has_irreversible_side_effects=True,
        inconsistent_state_detected=False,
    )
    assert risk.risk_score == 0.75
    assert risk.has_irreversible_side_effects is True


def test_recovery_budget_snapshot_creation():
    b_snap = RecoveryBudgetSnapshot(
        operations_remaining=5,
        cost_remaining=100.0,
        time_remaining_seconds=300.0,
        retry_budget_remaining=2,
        rollback_budget_remaining=1,
        validation_budget_remaining=3,
    )
    assert b_snap.operations_remaining == 5
    d = b_snap.to_dict()
    assert d["retry_budget_remaining"] == 2


# ── 2. Repository Tests ───────────────────────────────────────────────────────


def test_repository_save_and_get_context():
    repo = InMemoryRecoveryRepository()
    ctx = make_context()
    repo.save_context(ctx)

    retrieved = repo.get_context("ctx-1")
    assert retrieved is not None
    assert retrieved.recovery_context_id == "ctx-1"


def test_repository_get_contexts_by_run_and_workflow():
    repo = InMemoryRecoveryRepository()
    ctx1 = make_context(context_id="ctx-1", agent_run_id="run-10")
    ctx2 = make_context(context_id="ctx-2", agent_run_id="run-10")
    repo.save_context(ctx1)
    repo.save_context(ctx2)

    by_run = repo.get_contexts_by_run("run-10")
    assert len(by_run) == 2
    by_wf = repo.get_contexts_by_workflow("wf-1")
    assert len(by_wf) == 2


def test_repository_get_history_by_operation():
    repo = InMemoryRecoveryRepository()
    ctx1 = make_context(context_id="ctx-1", failed_operation_id="op-failed")
    repo.save_context(ctx1)

    hist = repo.get_history_by_operation("op-failed")
    assert len(hist) == 1
    assert hist[0].recovery_context_id == "ctx-1"


def test_repository_context_conflict():
    repo = InMemoryRecoveryRepository()
    ctx1 = make_context(context_id="ctx-1")
    repo.save_context(ctx1)

    ctx_bad = RecoveryContext(
        recovery_context_id="ctx-1",
        agent_run_id="run-1",
        goal_id="diff-goal",
        workflow_id="wf-1",
        iteration_id="iter-1",
        failed_task_id="task-1",
        failed_operation_id="op-1",
        error={"error_type": "DifferentError"},
        created_at="2026-07-26T00:00:00Z",
    )
    with pytest.raises(RecoveryIdempotencyError):
        repo.save_context(ctx_bad)


def test_repository_idempotency_key_conflict():
    repo = InMemoryRecoveryRepository()
    d1 = RecoveryDecision(
        recovery_decision_id="dec-1",
        recovery_context_id="ctx-1",
        strategy=RecoveryStrategy.RETRY,
        idempotency_key="key-1",
        decided_at="2026-07-26T00:00:00Z",
    )
    repo.save_decision(d1)

    d_conflict = RecoveryDecision(
        recovery_decision_id="dec-2",
        recovery_context_id="ctx-1",
        strategy=RecoveryStrategy.FAIL,
        idempotency_key="key-1",
        decided_at="2026-07-26T00:00:00Z",
    )
    with pytest.raises(RecoveryIdempotencyError):
        repo.save_decision(d_conflict)


def test_repository_save_attempt_immutable_context():
    repo = InMemoryRecoveryRepository()
    ctx = make_context()
    repo.save_context(ctx)

    att = RecoveryAttempt(1, RecoveryStrategy.RETRY, "2026-07-26T00:00:00Z")
    repo.save_attempt("ctx-1", att)

    updated_ctx = repo.get_context("ctx-1")
    assert updated_ctx is not None
    assert len(updated_ctx.retry_history) == 1
    assert updated_ctx.retry_history[0].strategy == RecoveryStrategy.RETRY


def test_repository_save_attempt_non_existent_context():
    repo = InMemoryRecoveryRepository()
    att = RecoveryAttempt(1, RecoveryStrategy.RETRY, "2026-07-26T00:00:00Z")
    with pytest.raises(RecoveryRepositoryError):
        repo.save_attempt("non-existent-ctx", att)


def test_repository_save_execution_result_immutability():
    repo = InMemoryRecoveryRepository()
    att = RecoveryAttempt(1, RecoveryStrategy.RETRY, "2026-07-26T00:00:00Z")
    res = RecoveryExecutionResult(
        recovery_execution_id="ex-1",
        recovery_decision_id="dec-1",
        recovery_context_id="ctx-1",
        strategy=RecoveryStrategy.RETRY,
        status=RecoveryStatus.SUCCEEDED,
        success=True,
        attempt=att,
    )
    repo.save_execution_result(res)

    res_mut = RecoveryExecutionResult(
        recovery_execution_id="ex-1",
        recovery_decision_id="dec-1",
        recovery_context_id="ctx-1",
        strategy=RecoveryStrategy.RETRY,
        status=RecoveryStatus.FAILED,
        success=False,
        attempt=att,
        fingerprint="diff-fp",
    )
    with pytest.raises(RecoveryRepositoryError):
        repo.save_execution_result(res_mut)


def test_repository_thread_safety():
    repo = InMemoryRecoveryRepository()
    errors = []

    def worker(idx: int):
        try:
            ctx = make_context(context_id=f"ctx-thread-{idx}")
            repo.save_context(ctx)
        except (TypeError, ValueError, RuntimeError) as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(repo.get_contexts_by_run("run-1")) == 20


# ── 3. Classifier Tests ───────────────────────────────────────────────────────


def test_classifier_transient_error():
    clf = RecoveryErrorClassifier()
    ctx = make_context(
        error={"error_type": "TransientTimeoutError", "message": "Socket timed out"}
    )
    res = clf.classify(ctx)
    assert res.error_class == RecoveryErrorClass.TRANSIENT
    assert res.retryable is True
    assert RecoveryReasonCode.TRANSIENT_ERROR in res.reason_codes


def test_classifier_permission_error():
    clf = RecoveryErrorClassifier()
    ctx = make_context(
        error={"error_type": "PermissionDeniedError", "message": "Access denied"}
    )
    res = clf.classify(ctx, exc=ObservationPermissionError("No read access"))
    assert res.error_class == RecoveryErrorClass.PERMISSION
    assert res.retryable is False
    assert res.requires_approval is True
    assert res.escalation_recommended is True


def test_classifier_approval_error():
    clf = RecoveryErrorClassifier()
    ctx = make_context(
        error={"error_type": "ApprovalRequiredError", "message": "Approval needed"}
    )
    res = clf.classify(ctx, exc=ApprovalError("Approval missing"))
    assert res.error_class == RecoveryErrorClass.PERMISSION
    assert res.requires_approval is True


def test_classifier_budget_exhausted():
    clf = RecoveryErrorClassifier()
    ctx = make_context()
    res = clf.classify(ctx, exc=BudgetExhaustedError("Budget depleted"))
    assert res.error_class == RecoveryErrorClass.BUDGET
    assert res.retryable is False
    assert res.escalation_recommended is True


def test_classifier_inconsistent_state():
    clf = RecoveryErrorClassifier()
    ctx = make_context()
    res = clf.classify(ctx, exc=TransactionRollbackError("Rollback failed halfway"))
    assert res.error_class == RecoveryErrorClass.INCONSISTENT_STATE
    assert res.retryable is False
    assert res.severity == "critical"
    assert res.escalation_recommended is True


def test_classifier_irreversible_side_effect():
    clf = RecoveryErrorClassifier()
    ctx = make_context(
        side_effects=({"reversibility": "irreversible", "type": "db_drop"},)
    )
    res = clf.classify(ctx, exc=IrreversibleOperationError("Cannot undo drop"))
    assert res.severity == "critical"
    assert res.escalation_recommended is True


def test_classifier_checkpoint_available():
    clf = RecoveryErrorClassifier()
    ctx = make_context(checkpoint_ids=("cp-1", "cp-2"))
    res = clf.classify(ctx)
    assert res.rollback_candidate is True
    assert RecoveryReasonCode.CHECKPOINT_AVAILABLE in res.reason_codes


def test_classifier_retries_exhausted_rule():
    clf = RecoveryErrorClassifier()
    att = RecoveryAttempt(1, RecoveryStrategy.RETRY, "2026-07-26T00:00:00Z")
    ctx = make_context(retry_history=(att, att, att))
    res = clf.classify(ctx)
    assert res.retryable is False
    assert RecoveryReasonCode.RETRIES_EXHAUSTED in res.reason_codes


def test_classifier_unknown_not_retryable():
    clf = RecoveryErrorClassifier()
    ctx = make_context(
        error={
            "error_type": "MysteriousCustomError",
            "message": "Something weird happened",
        }
    )
    res = clf.classify(ctx)
    assert res.error_class == RecoveryErrorClass.UNKNOWN
    assert res.retryable is False
    assert RecoveryReasonCode.UNKNOWN_FAILURE in res.reason_codes


# ── 4. Policy & Evaluators Tests ──────────────────────────────────────────────


def test_retry_policy_max_attempts_exceeded():
    evaluator = RetryPolicyEvaluator()
    policy = RetryPolicy(maximum_attempts=3)
    res = evaluator.evaluate(policy, attempt_index=4, error_type="TransientError")
    assert res.is_allowed is False
    assert "exceeds maximum attempts" in res.reason


def test_retry_policy_non_retryable_precedence():
    evaluator = RetryPolicyEvaluator()
    policy = RetryPolicy(
        maximum_attempts=3,
        retryable_errors=("TransientError",),
        non_retryable_errors=("FatalError", "TransientError"),
    )
    res = evaluator.evaluate(policy, attempt_index=1, error_type="TransientError")
    assert res.is_allowed is False
    assert "non-retryable" in res.reason


def test_retry_policy_prohibited_operations():
    evaluator = RetryPolicyEvaluator()
    policy = RetryPolicy(prohibited_operations=("op-delete",))
    res = evaluator.evaluate(
        policy, attempt_index=1, error_type="TransientError", operation_id="op-delete"
    )
    assert res.is_allowed is False
    assert "prohibited" in res.reason


def test_retry_policy_allowed_operations():
    evaluator = RetryPolicyEvaluator()
    policy = RetryPolicy(allowed_operations=("op-safe",))
    res1 = evaluator.evaluate(
        policy, attempt_index=1, error_type="TransientError", operation_id="op-safe"
    )
    assert res1.is_allowed is True
    res2 = evaluator.evaluate(
        policy, attempt_index=1, error_type="TransientError", operation_id="op-other"
    )
    assert res2.is_allowed is False


def test_rollback_policy_evaluation():
    evaluator = RollbackPolicyEvaluator()
    policy = RollbackPolicy(automatic_for=("op-1",))
    res = evaluator.evaluate(
        policy, operation_id="op-1", checkpoint_status=CheckpointStatus.ACTIVE
    )
    assert res.can_rollback is True
    assert res.requires_approval is False

    res_no_cp = evaluator.evaluate(policy, operation_id="op-1", checkpoint_status=None)
    assert res_no_cp.can_rollback is False


def test_escalation_policy_evaluation():
    evaluator = EscalationPolicyEvaluator()
    policy = EscalationPolicy(
        triggers=("INCONSISTENT_STATE",), escalation_target=EscalationTarget.USER
    )
    res = evaluator.evaluate(
        policy, reason_codes=(RecoveryReasonCode.INCONSISTENT_STATE,)
    )
    assert res.should_escalate is True
    assert res.target == EscalationTarget.USER


# ── 5. Backoff Calculator Tests ───────────────────────────────────────────────


def test_backoff_none():
    calc = RecoveryBackoffCalculator()
    policy = RetryPolicy(backoff_strategy=BackoffStrategy.NONE)
    assert calc.calculate_delay(policy, attempt_index=1) == 0.0


def test_backoff_constant():
    calc = RecoveryBackoffCalculator()
    policy = RetryPolicy(
        backoff_strategy=BackoffStrategy.CONSTANT,
        initial_delay_seconds=2.0,
        jitter=False,
    )
    assert calc.calculate_delay(policy, attempt_index=3) == 2.0


def test_backoff_linear():
    calc = RecoveryBackoffCalculator()
    policy = RetryPolicy(
        backoff_strategy=BackoffStrategy.LINEAR, initial_delay_seconds=2.0, jitter=False
    )
    assert calc.calculate_delay(policy, attempt_index=1) == 2.0
    assert calc.calculate_delay(policy, attempt_index=2) == 4.0
    assert calc.calculate_delay(policy, attempt_index=3) == 6.0


def test_backoff_exponential():
    calc = RecoveryBackoffCalculator()
    policy = RetryPolicy(
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        initial_delay_seconds=1.0,
        jitter=False,
    )
    assert calc.calculate_delay(policy, attempt_index=1) == 1.0
    assert calc.calculate_delay(policy, attempt_index=2) == 2.0
    assert calc.calculate_delay(policy, attempt_index=3) == 4.0
    assert calc.calculate_delay(policy, attempt_index=4) == 8.0


def test_backoff_maximum_cap():
    calc = RecoveryBackoffCalculator()
    policy = RetryPolicy(
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        initial_delay_seconds=10.0,
        maximum_delay_seconds=15.0,
        jitter=False,
    )
    assert calc.calculate_delay(policy, attempt_index=5) == 15.0


def test_backoff_invalid_attempt_index():
    calc = RecoveryBackoffCalculator()
    policy = RetryPolicy()
    with pytest.raises(RecoveryBackoffError):
        calc.calculate_delay(policy, attempt_index=0)


# ── 6. Decision Engine Precedence Tests ───────────────────────────────────────


def test_decision_engine_inconsistent_state_precedence():
    engine = RecoveryDecisionEngine()
    ctx = make_context()
    clf = ErrorClassification(
        error_class=RecoveryErrorClass.INCONSISTENT_STATE,
        retryable=True,
        reason_codes=(RecoveryReasonCode.INCONSISTENT_STATE,),
        severity="critical",
        requires_reobservation=False,
        requires_validation=False,
        requires_approval=False,
        rollback_candidate=True,
        compensation_candidate=False,
        escalation_recommended=True,
        evidence=RecoveryEvidence("ev1", "ctx-1", "err"),
    )
    dec = engine.make_decision(ctx, clf)
    assert dec.strategy == RecoveryStrategy.ESCALATE
    assert dec.requires_approval is True


def test_decision_engine_retries_exhausted_fallback():
    engine = RecoveryDecisionEngine()
    att = RecoveryAttempt(1, RecoveryStrategy.RETRY, "2026-07-26T00:00:00Z")
    ctx = make_context(retry_history=(att, att, att))
    clf = ErrorClassification(
        error_class=RecoveryErrorClass.TRANSIENT,
        retryable=True,
        reason_codes=(RecoveryReasonCode.TRANSIENT_ERROR,),
        severity="low",
        requires_reobservation=False,
        requires_validation=False,
        requires_approval=False,
        rollback_candidate=False,
        compensation_candidate=False,
        escalation_recommended=False,
        evidence=RecoveryEvidence("ev1", "ctx-1", "err"),
    )
    policy = RetryPolicy(maximum_attempts=3)
    dec = engine.make_decision(ctx, clf, retry_policy=policy)
    assert dec.strategy in (RecoveryStrategy.REPLAN, RecoveryStrategy.ESCALATE)
    assert RecoveryReasonCode.RETRIES_EXHAUSTED in dec.reason_codes


def test_decision_engine_rollback_available_when_retries_exhausted():
    engine = RecoveryDecisionEngine()
    att = RecoveryAttempt(1, RecoveryStrategy.RETRY, "2026-07-26T00:00:00Z")
    ctx = make_context(checkpoint_ids=("cp-10",), retry_history=(att, att, att))
    clf = ErrorClassification(
        error_class=RecoveryErrorClass.TRANSIENT,
        retryable=True,
        reason_codes=(RecoveryReasonCode.TRANSIENT_ERROR,),
        severity="low",
        requires_reobservation=False,
        requires_validation=False,
        requires_approval=False,
        rollback_candidate=True,
        compensation_candidate=False,
        escalation_recommended=False,
        evidence=RecoveryEvidence("ev1", "ctx-1", "err"),
    )
    dec = engine.make_decision(ctx, clf, retry_policy=RetryPolicy(maximum_attempts=3))
    assert dec.strategy == RecoveryStrategy.ROLLBACK
    assert dec.checkpoint_id == "cp-10"


def test_decision_engine_standard_retry():
    engine = RecoveryDecisionEngine()
    ctx = make_context()
    clf = ErrorClassification(
        error_class=RecoveryErrorClass.TRANSIENT,
        retryable=True,
        reason_codes=(RecoveryReasonCode.TRANSIENT_ERROR,),
        severity="low",
        requires_reobservation=False,
        requires_validation=False,
        requires_approval=False,
        rollback_candidate=False,
        compensation_candidate=False,
        escalation_recommended=False,
        evidence=RecoveryEvidence("ev1", "ctx-1", "err"),
    )
    dec = engine.make_decision(ctx, clf)
    assert dec.strategy == RecoveryStrategy.RETRY
    assert dec.delay_seconds is not None


# ── 7. Strategy Executors Tests ───────────────────────────────────────────────


def test_retry_strategy_executor_missing_adapter():
    executor = RetryStrategyExecutor()
    ctx = make_context()
    dec = RecoveryDecision("d1", "ctx-1", RecoveryStrategy.RETRY)
    res = executor.execute(ctx, dec, integrations={})
    assert res.status == RecoveryStatus.FAILED
    assert res.success is False
    assert "Missing required" in res.error_message


def test_rollback_strategy_executor_missing_checkpoint_id():
    executor = RollbackStrategyExecutor()
    ctx = make_context()
    dec = RecoveryDecision("d1", "ctx-1", RecoveryStrategy.ROLLBACK, checkpoint_id=None)
    res = executor.execute(
        ctx, dec, integrations={"checkpoint_restoration_manager": True}
    )
    assert res.status == RecoveryStatus.FAILED
    assert "No target checkpoint_id" in res.error_message


def test_terminal_strategy_executor_fail():
    executor = TerminalStrategyExecutor()
    ctx = make_context()
    dec = RecoveryDecision("d1", "ctx-1", RecoveryStrategy.FAIL)
    res = executor.execute(ctx, dec, integrations={})
    assert res.status == RecoveryStatus.FAILED
    assert res.success is False


def test_terminal_strategy_executor_abort():
    executor = TerminalStrategyExecutor()
    ctx = make_context()
    dec = RecoveryDecision("d1", "ctx-1", RecoveryStrategy.ABORT)
    res = executor.execute(ctx, dec, integrations={})
    assert res.status == RecoveryStatus.ABORTED
    assert res.success is False


# ── 8. Recovery Manager Workflows Tests ───────────────────────────────────────


def test_recovery_manager_decide_and_execute():
    mgr = RecoveryManager()
    ctx = make_context()

    # Step 1: Decide
    dec = mgr.decide(ctx)
    assert dec is not None
    assert dec.recovery_context_id == "ctx-1"

    # Step 2: Execute
    exec_res = mgr.execute(dec)
    assert exec_res is not None
    assert exec_res.recovery_decision_id == dec.recovery_decision_id


def test_recovery_manager_recover_composition():
    mgr = RecoveryManager()
    ctx = make_context()
    exec_res = mgr.recover(ctx)
    assert exec_res is not None
    assert exec_res.recovery_context_id == "ctx-1"


def test_recovery_manager_event_publishing():
    published = []

    class MockEventBus:
        def publish(self, topic: str, payload: dict):
            published.append((topic, payload))

    mgr = RecoveryManager()
    mgr.register_integration("event_bus", MockEventBus())

    ctx = make_context()
    mgr.recover(ctx)

    topics = [p[0] for p in published]
    assert "RECOVERY_CONTEXT_CREATED" in topics
    assert "RECOVERY_DECISION_MADE" in topics
    assert "RECOVERY_STRATEGY_STARTED" in topics


# ── 9. State Machine Transition Tests ─────────────────────────────────────────


def test_state_machine_recovering_transitions():
    assert AgentRuntimeStateMachine.can_transition("recovering", "planning") is True
    assert AgentRuntimeStateMachine.can_transition("recovering", "executing") is True
    assert AgentRuntimeStateMachine.can_transition("recovering", "observing") is True
    assert AgentRuntimeStateMachine.can_transition("recovering", "validating") is True
    assert (
        AgentRuntimeStateMachine.can_transition("recovering", "waiting_for_user")
        is True
    )
    assert (
        AgentRuntimeStateMachine.can_transition("recovering", "waiting_for_approval")
        is True
    )
    assert AgentRuntimeStateMachine.can_transition("recovering", "blocked") is True
    assert AgentRuntimeStateMachine.can_transition("recovering", "failed") is True


# ── 10. Security & Invariants Tests ───────────────────────────────────────────


def test_security_no_permission_elevation():
    clf = RecoveryErrorClassifier()
    ctx = make_context(error={"error_type": "PermissionError"})
    res = clf.classify(ctx)
    assert res.retryable is False
    assert res.requires_approval is True


def test_security_evidence_preservation():
    clf = RecoveryErrorClassifier()
    ctx = make_context(
        error={"error_type": "FatalError", "message": "Database corrupted"}
    )
    res = clf.classify(ctx)
    assert res.evidence is not None
    assert res.evidence.recovery_context_id == "ctx-1"
    assert "Database corrupted" in res.evidence.error_summary


# ── 11. Parameterized Matrix Tests for High Coverage ─────────────────────────


@pytest.mark.parametrize("error_class", list(RecoveryErrorClass))
def test_all_error_classes_instantiation(error_class):
    assert isinstance(error_class.value, str)


@pytest.mark.parametrize("strategy", list(RecoveryStrategy))
def test_all_recovery_strategies_instantiation(strategy):
    assert isinstance(strategy.value, str)


@pytest.mark.parametrize("status", list(RecoveryStatus))
def test_all_recovery_statuses_instantiation(status):
    assert isinstance(status.value, str)


@pytest.mark.parametrize("reason_code", list(RecoveryReasonCode))
def test_all_recovery_reason_codes_instantiation(reason_code):
    assert isinstance(reason_code.value, str)


@pytest.mark.parametrize("target", list(EscalationTarget))
def test_all_escalation_targets_instantiation(target):
    assert isinstance(target.value, str)


# ──────────────────────────────────────────────────────────────────────────────
# HARDENED & COMPREHENSIVE PHASE 9.16 EXTENDED TESTS
# ──────────────────────────────────────────────────────────────────────────────

# ── 12. Real ActionBudgetService Reserve/Confirm/Fail Lifecycle Tests ─────────


def test_action_budget_real_reservation_and_confirmation():
    from cmm.agent_runtime.action_budget_repository import (
        InMemoryActionBudgetRepository,
    )
    from cmm.agent_runtime.action_budget_service import ActionBudgetService
    from cmm.agent_runtime.enums import BudgetResourceType

    repo = InMemoryActionBudgetRepository()
    service = ActionBudgetService(repository=repo)
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.RETRY: 5, BudgetResourceType.OPERATION: 10},
    )

    mgr = RecoveryManager()
    mgr.register_integration("action_budget_service", service)

    class MockOpAdapter:
        def execute_recovery_retry(self, failed_operation_id, modified_parameters):
            class Res:
                success = True

            return Res()

    mgr.register_integration("operation_execution_adapter", MockOpAdapter())

    ctx = make_context(agent_run_id="run-1", remaining_budget={"budget_id": budget.id})
    mgr.repository.save_context(ctx)

    dec = RecoveryDecision(
        "dec-budget-1", ctx.recovery_context_id, RecoveryStrategy.RETRY
    )
    exec_res = mgr.execute(dec)

    assert exec_res.success is True
    usage = service.get_usage(budget.id)
    assert usage.get(BudgetResourceType.RETRY) == 1


def test_action_budget_real_exhaustion_blocks():
    from cmm.agent_runtime.action_budget_repository import (
        InMemoryActionBudgetRepository,
    )
    from cmm.agent_runtime.action_budget_service import ActionBudgetService
    from cmm.agent_runtime.enums import BudgetResourceType

    repo = InMemoryActionBudgetRepository()
    service = ActionBudgetService(repository=repo)
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.RETRY: 0},  # Exhausted immediately!
    )

    mgr = RecoveryManager()
    mgr.register_integration("action_budget_service", service)

    ctx = make_context(agent_run_id="run-1", remaining_budget={"budget_id": budget.id})
    mgr.repository.save_context(ctx)

    dec = RecoveryDecision(
        "dec-budget-exh", ctx.recovery_context_id, RecoveryStrategy.RETRY
    )
    with pytest.raises(RecoveryBudgetError):
        mgr.execute(dec)


def test_action_budget_idempotency_prevents_double_charge():
    from cmm.agent_runtime.action_budget_repository import (
        InMemoryActionBudgetRepository,
    )
    from cmm.agent_runtime.action_budget_service import ActionBudgetService
    from cmm.agent_runtime.enums import BudgetResourceType

    repo = InMemoryActionBudgetRepository()
    service = ActionBudgetService(repository=repo)
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.RETRY: 5},
    )

    mgr = RecoveryManager()
    mgr.register_integration("action_budget_service", service)

    class MockOpAdapter:
        def execute_recovery_retry(self, failed_operation_id, modified_parameters):
            class Res:
                success = True

            return Res()

    mgr.register_integration("operation_execution_adapter", MockOpAdapter())

    ctx = make_context(agent_run_id="run-1", remaining_budget={"budget_id": budget.id})
    mgr.repository.save_context(ctx)

    dec = RecoveryDecision(
        "dec-idem-1",
        ctx.recovery_context_id,
        RecoveryStrategy.RETRY,
        idempotency_key="idem-key-unique-123",
    )

    # First execution reserves & consumes 1 retry
    mgr.execute(dec)

    # Second execution with SAME idempotency key returns existing reservation
    mgr.execute(dec)

    usage = service.get_usage(budget.id)
    assert usage.get(BudgetResourceType.RETRY) == 1  # No double charge!


def test_action_budget_rollback_and_validation_cost():
    from cmm.agent_runtime.action_budget_repository import (
        InMemoryActionBudgetRepository,
    )
    from cmm.agent_runtime.action_budget_service import ActionBudgetService
    from cmm.agent_runtime.enums import BudgetResourceType

    repo = InMemoryActionBudgetRepository()
    service = ActionBudgetService(repository=repo)
    budget = service.create_budget(
        agent_run_id="run-1",
        limits={BudgetResourceType.OPERATION: 10},
    )

    mgr = RecoveryManager()
    mgr.register_integration("action_budget_service", service)

    class MockRestorationMgr:
        def restore_checkpoint(self, checkpoint_id, agent_run_id):
            class Res:
                success = True

            return Res()

    mgr.register_integration("checkpoint_restoration_manager", MockRestorationMgr())

    ctx = make_context(agent_run_id="run-1", remaining_budget={"budget_id": budget.id})
    mgr.repository.save_context(ctx)

    dec = RecoveryDecision(
        "dec-rollback-cost",
        ctx.recovery_context_id,
        RecoveryStrategy.ROLLBACK,
        checkpoint_id="cp-1",
    )
    mgr.execute(dec)

    usage = service.get_usage(budget.id)
    assert usage.get(BudgetResourceType.OPERATION) == 1


# ── 13. All 18 Domain Events Detailed Tests ────────────────────────────────────


@pytest.mark.parametrize(
    "event_name",
    [
        "RECOVERY_CONTEXT_CREATED",
        "RECOVERY_DECISION_REQUESTED",
        "RECOVERY_DECISION_MADE",
        "RECOVERY_STRATEGY_STARTED",
        "RECOVERY_STRATEGY_SUCCEEDED",
        "RECOVERY_STRATEGY_PARTIALLY_SUCCEEDED",
        "RECOVERY_STRATEGY_FAILED",
        "RETRY_SCHEDULED",
        "RETRY_STARTED",
        "RETRY_EXHAUSTED",
        "REOBSERVATION_REQUESTED",
        "REPLAN_REQUESTED",
        "ROLLBACK_REQUESTED",
        "COMPENSATION_REQUESTED",
        "USER_INPUT_REQUESTED",
        "APPROVAL_REQUESTED",
        "RECOVERY_ESCALATED",
        "RECOVERY_ABORTED",
    ],
)
def test_domain_event_payload_structure(event_name):
    published = []

    class MockEventBus:
        def publish(self, topic, payload):
            published.append((topic, payload))

    mgr = RecoveryManager()
    mgr.register_integration("event_bus", MockEventBus())

    ctx = make_context()

    # Trigger specific events based on strategy selection
    if event_name in (
        "RECOVERY_CONTEXT_CREATED",
        "RECOVERY_DECISION_REQUESTED",
    ) or event_name in ("RECOVERY_DECISION_MADE", "RETRY_SCHEDULED"):
        mgr.decide(ctx)
    elif event_name == "REOBSERVATION_REQUESTED":
        dec = RecoveryDecision(
            "dec-reobs", ctx.recovery_context_id, RecoveryStrategy.REOBSERVE
        )
        mgr.repository.save_context(ctx)
        mgr._publish_event("REOBSERVATION_REQUESTED", ctx, dec)
    elif event_name == "REPLAN_REQUESTED":
        dec = RecoveryDecision(
            "dec-replan", ctx.recovery_context_id, RecoveryStrategy.REPLAN
        )
        mgr.repository.save_context(ctx)
        mgr._publish_event("REPLAN_REQUESTED", ctx, dec)
    elif event_name == "ROLLBACK_REQUESTED":
        dec = RecoveryDecision(
            "dec-roll", ctx.recovery_context_id, RecoveryStrategy.ROLLBACK
        )
        mgr.repository.save_context(ctx)
        mgr._publish_event("ROLLBACK_REQUESTED", ctx, dec)
    elif event_name == "COMPENSATION_REQUESTED":
        dec = RecoveryDecision(
            "dec-comp", ctx.recovery_context_id, RecoveryStrategy.COMPENSATE
        )
        mgr.repository.save_context(ctx)
        mgr._publish_event("COMPENSATION_REQUESTED", ctx, dec)
    elif event_name == "USER_INPUT_REQUESTED":
        dec = RecoveryDecision(
            "dec-ask", ctx.recovery_context_id, RecoveryStrategy.ASK_USER
        )
        mgr.repository.save_context(ctx)
        mgr._publish_event("USER_INPUT_REQUESTED", ctx, dec)
    elif event_name == "APPROVAL_REQUESTED":
        dec = RecoveryDecision(
            "dec-app", ctx.recovery_context_id, RecoveryStrategy.REQUEST_APPROVAL
        )
        mgr.repository.save_context(ctx)
        mgr._publish_event("APPROVAL_REQUESTED", ctx, dec)
    elif event_name == "RETRY_EXHAUSTED":
        dec = RecoveryDecision(
            "dec-exh",
            ctx.recovery_context_id,
            RecoveryStrategy.ROLLBACK,
            reason_codes=(RecoveryReasonCode.RETRIES_EXHAUSTED,),
        )
        mgr.repository.save_context(ctx)
        mgr._publish_event("RETRY_EXHAUSTED", ctx, dec)
    elif event_name == "RECOVERY_ESCALATED":
        dec = RecoveryDecision(
            "dec-esc", ctx.recovery_context_id, RecoveryStrategy.ESCALATE
        )
        mgr.repository.save_context(ctx)
        mgr.execute(dec)
    elif event_name == "RECOVERY_STRATEGY_PARTIALLY_SUCCEEDED":
        dec = RecoveryDecision(
            "dec-part", ctx.recovery_context_id, RecoveryStrategy.COMPLETE_PARTIALLY
        )
        mgr.repository.save_context(ctx)
        mgr.execute(dec)
    elif event_name == "RECOVERY_ABORTED":
        dec = RecoveryDecision(
            "dec-abort", ctx.recovery_context_id, RecoveryStrategy.ABORT
        )
        mgr.repository.save_context(ctx)
        mgr.execute(dec)
    elif event_name == "RECOVERY_STRATEGY_SUCCEEDED":

        class MockOpAdapter:
            def execute_recovery_retry(self, failed_operation_id, modified_parameters):
                class Res:
                    success = True

                return Res()

        mgr.register_integration("operation_execution_adapter", MockOpAdapter())
        dec = mgr.decide(ctx)
        mgr.execute(dec)
    else:
        dec = mgr.decide(ctx)
        mgr.execute(dec)

    matching = [p for t, p in published if t == event_name]
    assert len(matching) >= 1
    p = matching[0]
    assert "event_id" in p
    assert "recovery_context_id" in p
    assert "run_id" in p
    assert "correlation_id" in p
    assert "causation_id" in p
    assert "timestamp" in p


# ── 14. Explicit Hardened Executor Failures & Checkpoint Integrity ────────────


def test_reobserve_executor_missing_integration():
    executor = ReobserveStrategyExecutor()
    ctx = make_context()
    dec = RecoveryDecision("d1", "ctx-1", RecoveryStrategy.REOBSERVE)
    res = executor.execute(ctx, dec, integrations={})
    assert res.status == RecoveryStatus.FAILED
    assert res.success is False
    assert "Missing required observation_engine" in res.error_message


def test_replan_executor_missing_integration():
    executor = ReplanStrategyExecutor()
    ctx = make_context()
    dec = RecoveryDecision("d1", "ctx-1", RecoveryStrategy.REPLAN)
    res = executor.execute(ctx, dec, integrations={})
    assert res.status == RecoveryStatus.FAILED
    assert res.success is False
    assert "Missing required planner_adapter" in res.error_message


def test_reload_resource_executor_missing_integration():
    executor = ReloadResourceStrategyExecutor()
    ctx = make_context()
    dec = RecoveryDecision("d1", "ctx-1", RecoveryStrategy.RELOAD_RESOURCE)
    res = executor.execute(ctx, dec, integrations={})
    assert res.status == RecoveryStatus.FAILED
    assert res.success is False
    assert "Missing required resource_loader" in res.error_message


def test_ask_user_executor():
    executor = AskUserStrategyExecutor()
    ctx = make_context()
    dec = RecoveryDecision("d1", "ctx-1", RecoveryStrategy.ASK_USER)
    res = executor.execute(ctx, dec, integrations={})
    assert res.status == RecoveryStatus.WAITING
    assert res.success is True
    assert res.modified_state.get("waiting_for_user") is True


def test_retry_later_executor():
    executor = RetryLaterStrategyExecutor()
    ctx = make_context()
    dec = RecoveryDecision(
        "d1", "ctx-1", RecoveryStrategy.RETRY_LATER, delay_seconds=15.0
    )
    res = executor.execute(ctx, dec, integrations={})
    assert res.status == RecoveryStatus.WAITING
    assert res.success is True
    assert res.modified_state.get("delay_seconds") == 15.0


def test_skip_optional_task_allowed_and_blocked():
    executor = SkipOptionalTaskStrategyExecutor()

    ctx_opt = make_context(metadata={"is_optional": True})
    dec = RecoveryDecision("d1", "ctx-1", RecoveryStrategy.SKIP_OPTIONAL_TASK)
    res_opt = executor.execute(ctx_opt, dec, integrations={})
    assert res_opt.status == RecoveryStatus.SUCCEEDED
    assert res_opt.success is True

    ctx_mand = make_context(metadata={"is_optional": False})
    res_mand = executor.execute(ctx_mand, dec, integrations={})
    assert res_mand.status == RecoveryStatus.FAILED
    assert res_mand.success is False
    assert "is not marked as optional" in res_mand.error_message


def test_complete_partially_executor():
    executor = CompletePartiallyStrategyExecutor()
    ctx = make_context()
    dec = RecoveryDecision(
        "d1",
        "ctx-1",
        RecoveryStrategy.COMPLETE_PARTIALLY,
        residual_risk={"missing_outputs": ("subgoal-2",)},
    )
    res = executor.execute(ctx, dec, integrations={})
    assert res.status == RecoveryStatus.PARTIALLY_SUCCEEDED
    assert res.success is True
    assert res.residual_risk.get("missing_outputs") == ("subgoal-2",)


def test_checkpoint_integrity_corrupted_blocks_rollback():
    engine = RecoveryDecisionEngine()

    att = RecoveryAttempt(1, RecoveryStrategy.RETRY, "2026-07-26T00:00:00Z")
    ctx_exh = make_context(
        checkpoint_ids=("cp-corrupt",),
        retry_history=(att, att, att),
        metadata={"checkpoint_integrity_status": "invalid"},
    )

    clf = RecoveryErrorClassifier().classify(ctx_exh)
    dec = engine.make_decision(
        ctx_exh,
        clf,
        retry_policy=RetryPolicy(maximum_attempts=3),
    )
    assert dec.strategy != RecoveryStrategy.ROLLBACK
    assert dec.strategy in (RecoveryStrategy.REPLAN, RecoveryStrategy.ESCALATE)
    assert RecoveryReasonCode.CHECKPOINT_INVALID in dec.reason_codes


def test_rollback_executor_post_rollback_validation_failure():
    executor = RollbackStrategyExecutor()
    ctx = make_context()
    dec = RecoveryDecision(
        "d1", "ctx-1", RecoveryStrategy.ROLLBACK, checkpoint_id="cp-1"
    )

    class MockRestorationMgr:
        def restore_checkpoint(self, checkpoint_id, agent_run_id):
            class Res:
                success = True

            return Res()

    class MockValAdapterFailed:
        def execute_stage_validation(self, agent_run_id, stage):
            assert stage == AgentValidationStage.POST_ROLLBACK

            class ValRes:
                is_passed = False
                summary = "Post-rollback check failed"
                validation_result_id = "val-post-rollback-failed"

            return ValRes()

    res = executor.execute(
        ctx,
        dec,
        integrations={
            "checkpoint_restoration_manager": MockRestorationMgr(),
            "validation_execution_adapter": MockValAdapterFailed(),
        },
    )
    assert res.status == RecoveryStatus.FAILED
    assert res.success is False
    assert "Post-rollback validation failed" in res.error_message


def test_retry_with_modified_parameters_allowed():
    engine = RecoveryDecisionEngine()
    ctx = make_context(
        metadata={
            "suggested_modified_parameters": {"timeout": 30},
            "expand_scope": False,
            "weaken_criteria": False,
            "elevate_permissions": False,
        }
    )
    clf = RecoveryErrorClassifier().classify(ctx)
    dec = engine.make_decision(ctx, clf)
    assert dec.strategy == RecoveryStrategy.RETRY_WITH_MODIFIED_PARAMETERS
    assert dec.modified_parameters == {"timeout": 30}


def test_unregistered_strategy_raises_error():
    mgr = RecoveryManager()
    ctx = make_context()
    mgr.repository.save_context(ctx)

    class UnregisteredStrategy:
        value = "UNREGISTERED_STRATEGY"

    dec = RecoveryDecision("d1", "ctx-1", strategy=UnregisteredStrategy())  # type: ignore
    with pytest.raises(RecoveryStrategyUnavailableError):
        mgr.execute(dec)
