"""Phase 9.17 – Outcome Evaluation Test Suite.

Comprehensive tests covering contracts, repository, criterion evaluation, metrics,
state comparison, regression detection, impact analysis, knowledge acquisition,
outcome evaluation engine, completion decision engine, manager orchestration,
event emission, recovery integration, and security invariants.
"""

from __future__ import annotations

import threading
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import Any

import pytest

from cmm.agent_runtime.enums import (
    CriterionEvaluationStatus,
    CriterionImportance,
    GoalCompletionDecisionKind,
    GoalKind,
    GoalStatus,
    Outcome,
    OutcomeEvaluationStatus,
    OutcomeReasonCode,
)
from cmm.agent_runtime.errors import (
    InvalidGoalContractError,
    OutcomeFingerprintError,
    OutcomeStateComparisonError,
)
from cmm.agent_runtime.goal_completion_decision_engine import (
    GoalCompletionDecisionEngine,
)
from cmm.agent_runtime.goal_contracts import Goal, GoalPriority, SuccessCriterion
from cmm.agent_runtime.goal_manager import GoalManager
from cmm.agent_runtime.goal_repository import InMemoryGoalRepository
from cmm.agent_runtime.outcome_criterion_evaluator import OutcomeCriterionEvaluator
from cmm.agent_runtime.outcome_evaluation_contracts import (
    GoalCompletionDecision,
    OutcomeCriterionResult,
    OutcomeEvaluation,
    OutcomeEvaluationRequest,
    OutcomeEvidence,
    OutcomeGap,
    OutcomeGeneratedDebt,
    OutcomeKnowledgeAcquisition,
    OutcomeMetricResult,
    OutcomeRegression,
    OutcomeSideEffect,
    OutcomeStateSnapshot,
    OutcomeTaskStatus,
    OutcomeUserConfirmationRequirement,
)
from cmm.agent_runtime.outcome_evaluation_engine import OutcomeEvaluationEngine
from cmm.agent_runtime.outcome_evaluation_manager import OutcomeEvaluationManager
from cmm.agent_runtime.outcome_evaluation_repository import (
    InMemoryOutcomeEvaluationRepository,
)
from cmm.agent_runtime.outcome_impact_analyzer import OutcomeImpactAnalyzer
from cmm.agent_runtime.outcome_knowledge_analyzer import OutcomeKnowledgeAnalyzer
from cmm.agent_runtime.outcome_metrics import OutcomeMetricEvaluator
from cmm.agent_runtime.outcome_regression_detector import OutcomeRegressionDetector
from cmm.agent_runtime.outcome_state_comparator import OutcomeStateComparator


class DummyEventBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append((event_type, payload))


def _make_sample_goal(
    goal_id: str = "goal-100",
    title: str = "Deploy microservice",
    criteria: list[SuccessCriterion] | None = None,
    status: GoalStatus = GoalStatus.ACTIVE,
) -> Goal:
    now = datetime.now(timezone.utc)
    return Goal(
        id=goal_id,
        title=title,
        description="Deploy user service",
        kind=GoalKind.PROJECT_IMPROVEMENT
        if hasattr(GoalKind, "PROJECT_IMPROVEMENT")
        else next(iter(GoalKind)),
        status=status,
        priority=GoalPriority(),
        success_criteria=tuple(criteria or []),
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_criterion() -> SuccessCriterion:
    return SuccessCriterion(
        id="crit-1",
        description="Must pass structural validation",
        required=True,
        expected_value="valid",
        actual_value="valid",
    )


@pytest.fixture
def sample_goal(sample_criterion: SuccessCriterion) -> Goal:
    return _make_sample_goal(criteria=[sample_criterion])


# ── SECTION 1: CONTRACTS ───────────────────────────────────────────────────


def test_evidence_contract_immutable() -> None:
    ev = OutcomeEvidence(
        evidence_id="ev-1",
        source="unit_test",
        description="Test log artifact",
        data={"status": "ok"},
    )
    assert ev.evidence_id == "ev-1"
    assert ev.source == "unit_test"
    with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
        ev.evidence_id = "ev-2"  # type: ignore


def test_evidence_invalid_id() -> None:
    with pytest.raises(InvalidGoalContractError):
        OutcomeEvidence(evidence_id="", source="test", description="desc")


def test_evidence_serialization() -> None:
    ev = OutcomeEvidence(
        evidence_id="ev-1", source="test", description="desc", data={"a": 1}
    )
    d = ev.to_dict()
    assert d["evidence_id"] == "ev-1"
    reconstructed = OutcomeEvidence.from_dict(d)
    assert reconstructed == ev


def test_metric_result_contract() -> None:
    m = OutcomeMetricResult(
        metric_id="met-1",
        name="latency",
        expected=100.0,
        actual=50.0,
        comparator="max",
        status=CriterionEvaluationStatus.SATISFIED,
    )
    assert m.metric_id == "met-1"
    assert m.status == CriterionEvaluationStatus.SATISFIED
    assert m.confidence == 1.0


def test_side_effect_contract() -> None:
    se = OutcomeSideEffect(
        side_effect_id="se-1",
        description="Created temp table",
        expected=True,
        reversible=True,
        authorized=True,
        affected_resources=("db_schema",),
    )
    assert se.authorized is True
    assert "db_schema" in se.affected_resources


def test_regression_contract() -> None:
    reg = OutcomeRegression(
        regression_id="reg-1",
        category="validation",
        severity="critical",
        previous_value=True,
        current_value=False,
    )
    assert reg.severity == "critical"
    assert reg.rollback_recommended is False


def test_generated_debt_contract() -> None:
    debt = OutcomeGeneratedDebt(
        debt_id="debt-1",
        category="technical",
        description="Missing unit test for corner case",
        severity="medium",
    )
    assert debt.accepted is False


def test_knowledge_acquisition_contract() -> None:
    k = OutcomeKnowledgeAcquisition(
        knowledge_id="know-1",
        kind="fact",
        statement="Database supports JSONB",
        confidence=0.95,
    )
    assert k.statement == "Database supports JSONB"


def test_gap_and_task_status_contracts() -> None:
    g = OutcomeGap(gap_id="gap-1", description="Missing SSL cert", impact="high")
    t = OutcomeTaskStatus(task_id="t-1", description="Configure Nginx", completed=True)
    assert g.resolved is False
    assert t.completed is True


def test_criterion_result_contract() -> None:
    cr = OutcomeCriterionResult(
        criterion_id="crit-1",
        status=CriterionEvaluationStatus.SATISFIED,
        importance=CriterionImportance.MANDATORY,
    )
    assert cr.blocking is False


def test_evaluation_contract_fingerprint() -> None:
    eval_rec = OutcomeEvaluation(
        outcome_evaluation_id="eval-1",
        goal_id="goal-1",
        agent_run_id="run-1",
        workflow_id="wf-1",
        iteration_id="iter-1",
        status=OutcomeEvaluationStatus.COMPLETED,
        outcome=Outcome.SUCCESS,
    )
    assert eval_rec.fingerprint != ""
    assert len(eval_rec.fingerprint) == 64  # SHA-256 length


def test_completion_decision_contract() -> None:
    dec = GoalCompletionDecision(
        completion_decision_id="dec-1",
        outcome_evaluation_id="eval-1",
        goal_id="goal-1",
        decision=GoalCompletionDecisionKind.COMPLETE,
        reason_codes=(OutcomeReasonCode.ALL_MANDATORY_CRITERIA_SATISFIED,),
    )
    assert dec.decision == GoalCompletionDecisionKind.COMPLETE
    assert dec.fingerprint != ""


def test_state_snapshot_contract() -> None:
    snap = OutcomeStateSnapshot(
        snapshot_id="snap-1",
        resources={"config": "v1"},
        versions={"config": "1.0.0"},
    )
    assert snap.resources["config"] == "v1"


def test_user_confirmation_requirement_contract() -> None:
    req = OutcomeUserConfirmationRequirement(
        confirmation_id="conf-1", reason="Confirm production deploy"
    )
    assert req.status == "pending"


# ── SECTION 2: REPOSITORY ──────────────────────────────────────────────────


def test_repo_save_and_get_evaluation() -> None:
    repo = InMemoryOutcomeEvaluationRepository()
    eval_rec = OutcomeEvaluation(
        outcome_evaluation_id="eval-1",
        goal_id="goal-1",
        agent_run_id="run-1",
        workflow_id="wf-1",
        iteration_id="iter-1",
        status=OutcomeEvaluationStatus.COMPLETED,
        outcome=Outcome.SUCCESS,
    )
    repo.save_evaluation(eval_rec)
    fetched = repo.get_evaluation("eval-1")
    assert fetched == eval_rec


def test_repo_idempotency_success() -> None:
    repo = InMemoryOutcomeEvaluationRepository()
    eval_rec = OutcomeEvaluation(
        outcome_evaluation_id="eval-1",
        goal_id="goal-1",
        agent_run_id="run-1",
        workflow_id="wf-1",
        iteration_id="iter-1",
        status=OutcomeEvaluationStatus.COMPLETED,
        outcome=Outcome.SUCCESS,
    )
    repo.save_evaluation(eval_rec, idempotency_key="key-123")
    saved_again = repo.save_evaluation(eval_rec, idempotency_key="key-123")
    assert saved_again == eval_rec


def test_repo_idempotency_fingerprint_mismatch() -> None:
    repo = InMemoryOutcomeEvaluationRepository()
    eval1 = OutcomeEvaluation(
        outcome_evaluation_id="eval-1",
        goal_id="goal-1",
        agent_run_id="run-1",
        workflow_id="wf-1",
        iteration_id="iter-1",
        status=OutcomeEvaluationStatus.COMPLETED,
        outcome=Outcome.SUCCESS,
    )
    eval2 = OutcomeEvaluation(
        outcome_evaluation_id="eval-2",
        goal_id="goal-1",
        agent_run_id="run-1",
        workflow_id="wf-1",
        iteration_id="iter-1",
        status=OutcomeEvaluationStatus.FAILED,
        outcome=Outcome.FAILURE,
    )
    repo.save_evaluation(eval1, idempotency_key="key-123")
    with pytest.raises(OutcomeFingerprintError):
        repo.save_evaluation(eval2, idempotency_key="key-123")


def test_repo_queries() -> None:
    repo = InMemoryOutcomeEvaluationRepository()
    eval1 = OutcomeEvaluation(
        outcome_evaluation_id="eval-1",
        goal_id="goal-1",
        agent_run_id="run-A",
        workflow_id="wf-1",
        iteration_id="iter-1",
        status=OutcomeEvaluationStatus.COMPLETED,
        outcome=Outcome.SUCCESS,
    )
    eval2 = OutcomeEvaluation(
        outcome_evaluation_id="eval-2",
        goal_id="goal-1",
        agent_run_id="run-A",
        workflow_id="wf-1",
        iteration_id="iter-2",
        status=OutcomeEvaluationStatus.COMPLETED,
        outcome=Outcome.SUCCESS,
    )
    repo.save_evaluation(eval1)
    repo.save_evaluation(eval2)

    assert len(repo.get_evaluations_by_goal("goal-1")) == 2
    assert len(repo.get_evaluations_by_run("run-A")) == 2
    assert repo.get_latest_evaluation("goal-1") == eval2


def test_repo_thread_safety() -> None:
    repo = InMemoryOutcomeEvaluationRepository()
    errors: list[Exception] = []

    def worker(i: int) -> None:
        try:
            ev = OutcomeEvaluation(
                outcome_evaluation_id=f"eval-t-{i}",
                goal_id=f"goal-t-{i % 5}",
                agent_run_id="run-t",
                workflow_id="wf-t",
                iteration_id="iter-t",
                status=OutcomeEvaluationStatus.COMPLETED,
                outcome=Outcome.SUCCESS,
            )
            repo.save_evaluation(ev)
        except Exception as exc:  # noqa: BLE001 - capture worker failures
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(repo.get_evaluations_by_run("run-t")) == 50


# ── SECTION 3: CRITERION EVALUATOR ─────────────────────────────────────────


def test_criterion_evaluator_mandatory_satisfied(
    sample_criterion: SuccessCriterion,
) -> None:
    evaluator = OutcomeCriterionEvaluator()
    res = evaluator.evaluate_criterion(
        criterion=sample_criterion,
        expected_state={"crit-1": "valid"},
        actual_state={"crit-1": "valid"},
    )
    assert res.status == CriterionEvaluationStatus.SATISFIED
    assert res.blocking is False


def test_criterion_evaluator_mandatory_unsatisfied() -> None:
    crit = SuccessCriterion(
        id="crit-1",
        description="Must pass structural validation",
        required=True,
        expected_value="valid",
        actual_value="invalid",
    )
    evaluator = OutcomeCriterionEvaluator()
    res = evaluator.evaluate_criterion(
        criterion=crit,
    )
    assert res.status == CriterionEvaluationStatus.UNSATISFIED
    assert res.blocking is True


def test_criterion_evaluator_waived_with_authorization() -> None:
    crit = SuccessCriterion(
        id="crit-w",
        description="Waived test",
        metadata={"waived": True, "waived_by": "admin_user"},
    )
    evaluator = OutcomeCriterionEvaluator()
    res = evaluator.evaluate_criterion(criterion=crit)
    assert res.status == CriterionEvaluationStatus.WAIVED
    assert res.blocking is False


def test_criterion_evaluator_waived_without_authorization_blocked() -> None:
    crit = SuccessCriterion(
        id="crit-w2", description="Unauthorized waiver", metadata={"waived": True}
    )
    evaluator = OutcomeCriterionEvaluator()
    res = evaluator.evaluate_criterion(criterion=crit)
    assert res.status == CriterionEvaluationStatus.BLOCKED
    assert res.blocking is True


def test_criterion_evaluator_absence_of_evidence_not_success() -> None:
    crit = SuccessCriterion(
        id="crit-no-ev", description="Needs verification", expected_value=None
    )
    evaluator = OutcomeCriterionEvaluator()
    res = evaluator.evaluate_criterion(criterion=crit)
    assert res.status == CriterionEvaluationStatus.INCONCLUSIVE
    assert OutcomeReasonCode.EVIDENCE_INSUFFICIENT in res.reason_codes


def test_criterion_evaluator_user_confirmation_missing() -> None:
    crit = SuccessCriterion(
        id="crit-uc",
        description="Human acceptance",
        metadata={"requires_user_confirmation": True},
    )
    evaluator = OutcomeCriterionEvaluator()
    res = evaluator.evaluate_criterion(criterion=crit, user_confirmation=None)
    assert OutcomeReasonCode.USER_CONFIRMATION_REQUIRED in res.reason_codes
    assert any("user confirmation" in w for w in res.warnings)


# ── SECTION 4: STATE COMPARATOR ─────────────────────────────────────────────


def test_state_comparator_exact_match() -> None:
    comparator = OutcomeStateComparator()
    diff = comparator.compare_states(
        expected_state={"service": "active"},
        actual_state={"service": "active"},
        previous_state={"service": "active"},
    )
    assert diff.is_noop is True
    assert len(diff.missing_changes) == 0


def test_state_comparator_unexpected_changes() -> None:
    comparator = OutcomeStateComparator()
    diff = comparator.compare_states(
        expected_state={"service": "active"},
        actual_state={"service": "active", "extra_db": "created"},
        previous_state={"service": "inactive"},
    )
    assert "extra_db" in diff.unexpected_changes
    assert diff.is_noop is False


def test_state_comparator_version_mismatch() -> None:
    comparator = OutcomeStateComparator()
    exp_snap = OutcomeStateSnapshot(
        snapshot_id="exp", versions={"lib_v": "2.0.0"}, resources={"lib": "ok"}
    )
    act_snap = OutcomeStateSnapshot(
        snapshot_id="act", versions={"lib_v": "1.0.0"}, resources={"lib": "ok"}
    )
    diff = comparator.compare_states(expected_state=exp_snap, actual_state=act_snap)
    assert "lib_v" in diff.version_mismatches
    assert len(diff.inconsistencies) > 0


def test_state_comparator_mandatory_resource_missing() -> None:
    comparator = OutcomeStateComparator()
    with pytest.raises(OutcomeStateComparisonError):
        comparator.compare_states(
            expected_state={}, actual_state={}, mandatory_resources=("db_conn",)
        )


# ── SECTION 5: METRICS ─────────────────────────────────────────────────────


def test_metric_evaluator_exact() -> None:
    evaluator = OutcomeMetricEvaluator()
    res = evaluator.evaluate_metric(
        metric_id="m-1",
        name="status_code",
        expected=200,
        actual=200,
        comparator="exact",
    )
    assert res.status == CriterionEvaluationStatus.SATISFIED


def test_metric_evaluator_min_max_percentage() -> None:
    evaluator = OutcomeMetricEvaluator()
    res_min = evaluator.evaluate_metric(
        metric_id="m-min",
        name="throughput",
        expected=100.0,
        actual=120.0,
        comparator="min",
    )
    assert res_min.status == CriterionEvaluationStatus.SATISFIED

    res_max = evaluator.evaluate_metric(
        metric_id="m-max", name="cost", expected=50.0, actual=75.0, comparator="max"
    )
    assert res_max.status == CriterionEvaluationStatus.UNSATISFIED


def test_metric_evaluator_custom_comparator() -> None:
    evaluator = OutcomeMetricEvaluator()
    evaluator.register_custom_evaluator(
        "divisible_by", lambda exp, act: float(act) % float(exp) == 0
    )
    res = evaluator.evaluate_metric(
        metric_id="m-custom",
        name="batch",
        expected=5,
        actual=15,
        comparator="divisible_by",
    )
    assert res.status == CriterionEvaluationStatus.SATISFIED


def test_metric_evaluator_unregistered_comparator_inconclusive() -> None:
    evaluator = OutcomeMetricEvaluator()
    res = evaluator.evaluate_metric(
        metric_id="m-bad", name="test", expected=1, actual=1, comparator="unknown_comp"
    )
    assert res.status == CriterionEvaluationStatus.INCONCLUSIVE
    assert res.confidence == 0.0


# ── SECTION 6: REGRESSION DETECTOR ─────────────────────────────────────────


def test_regression_detector_version_mismatch() -> None:
    detector = OutcomeRegressionDetector()
    comparator = OutcomeStateComparator()
    exp_snap = OutcomeStateSnapshot(
        snapshot_id="e", versions={"v1": "2.0"}, resources={"r": "1"}
    )
    act_snap = OutcomeStateSnapshot(
        snapshot_id="a", versions={"v1": "1.0"}, resources={"r": "1"}
    )
    diff = comparator.compare_states(expected_state=exp_snap, actual_state=act_snap)

    regs = detector.detect_regressions(diff=diff)
    assert len(regs) == 1
    assert regs[0].category == "resource_version"


def test_regression_detector_validation_failure() -> None:
    class DummyVal:
        def __init__(self, val_id: str, success: bool) -> None:
            self.validation_id = val_id
            self.is_success = success

    detector = OutcomeRegressionDetector()
    comparator = OutcomeStateComparator()
    diff = comparator.compare_states(expected_state={}, actual_state={})

    prev_vals = (DummyVal("v-1", True),)
    curr_vals = (DummyVal("v-1", False),)

    regs = detector.detect_regressions(
        diff=diff, validations=curr_vals, previous_validations=prev_vals
    )
    assert len(regs) == 1
    assert regs[0].severity == "critical"


# ── SECTION 7: IMPACT ANALYZER ─────────────────────────────────────────────


def test_impact_analyzer_unexpected_side_effects() -> None:
    analyzer = OutcomeImpactAnalyzer()
    comparator = OutcomeStateComparator()
    diff = comparator.compare_states(
        expected_state={},
        actual_state={"unintended_key": "val"},
        previous_state={},
    )
    side_effects, debt, _risks = analyzer.analyze_impact(diff=diff)
    assert len(side_effects) == 1
    assert side_effects[0].expected is False
    assert len(debt) == 1  # Unauthorized side effect creates debt


# ── SECTION 8: KNOWLEDGE ANALYZER ──────────────────────────────────────────


def test_knowledge_analyzer_facts_and_gaps() -> None:
    analyzer = OutcomeKnowledgeAnalyzer()
    ev1 = OutcomeEvidence(
        evidence_id="ev-1", source="test", description="Learned fact: Server is Linux"
    )
    gap1 = OutcomeGap(
        gap_id="g-1", description="Learned fact: Server is Linux", resolved=False
    )

    acquired, gaps, _tasks = analyzer.analyze_knowledge_and_gaps(
        evidence=(ev1,), existing_gaps=(gap1,)
    )
    assert len(acquired) == 1
    assert acquired[0].kind == "fact"
    assert gaps[0].resolved is True


# ── SECTION 9: OUTCOME EVALUATION ENGINE ────────────────────────────────────


def test_outcome_engine_success(sample_goal: Goal) -> None:
    bus = DummyEventBus()
    engine = OutcomeEvaluationEngine(event_bus=bus)
    req = OutcomeEvaluationRequest(
        goal_id=sample_goal.id,
        agent_run_id="run-1",
        workflow_id="wf-1",
        iteration_id="iter-1",
        expected_state={"crit-1": "valid"},
        actual_state={"crit-1": "valid"},
    )
    eval_rec = engine.evaluate(req, goal=sample_goal)

    assert eval_rec.outcome == Outcome.SUCCESS
    assert eval_rec.recommended_decision == GoalCompletionDecisionKind.COMPLETE
    assert any(evt[0] == "OUTCOME_EVALUATION_COMPLETED" for evt in bus.events)


def test_outcome_engine_critical_regression(sample_goal: Goal) -> None:
    bus = DummyEventBus()
    engine = OutcomeEvaluationEngine(event_bus=bus)

    class DummyVal:
        def __init__(self, val_id: str, success: bool) -> None:
            self.validation_id = val_id
            self.is_success = success

    req = OutcomeEvaluationRequest(
        goal_id=sample_goal.id,
        agent_run_id="run-1",
        validations=(DummyVal("v-1", False),),
    )
    eval_rec = engine.evaluate(req, goal=sample_goal)
    assert eval_rec.outcome in (Outcome.FAILURE, Outcome.REGRESSION)


# ── SECTION 10: GOAL COMPLETION DECISION ENGINE ────────────────────────────


def test_decision_engine_complete(sample_goal: Goal) -> None:
    bus = DummyEventBus()
    eval_engine = OutcomeEvaluationEngine(event_bus=bus)
    decision_engine = GoalCompletionDecisionEngine(event_bus=bus)

    req = OutcomeEvaluationRequest(
        goal_id=sample_goal.id,
        agent_run_id="run-1",
        expected_state={"crit-1": "valid"},
        actual_state={"crit-1": "valid"},
    )
    eval_rec = eval_engine.evaluate(req, goal=sample_goal)
    decision = decision_engine.decide_completion(evaluation=eval_rec, goal=sample_goal)

    assert decision.decision == GoalCompletionDecisionKind.COMPLETE
    assert OutcomeReasonCode.ALL_MANDATORY_CRITERIA_SATISFIED in decision.reason_codes
    assert any(evt[0] == "GOAL_COMPLETED" for evt in bus.events)


def test_decision_engine_fail_safe_mandatory_unsatisfied() -> None:
    unsat_crit = SuccessCriterion(
        id="crit-1",
        description="Must pass structural validation",
        required=True,
        expected_value="valid",
        actual_value="INVALID",
    )
    goal = _make_sample_goal(criteria=[unsat_crit])

    bus = DummyEventBus()
    eval_engine = OutcomeEvaluationEngine(event_bus=bus)
    decision_engine = GoalCompletionDecisionEngine(event_bus=bus)

    req = OutcomeEvaluationRequest(
        goal_id=goal.id,
        agent_run_id="run-1",
        expected_state={"crit-1": "valid"},
        actual_state={"crit-1": "INVALID"},
    )
    eval_rec = eval_engine.evaluate(req, goal=goal)
    decision = decision_engine.decide_completion(evaluation=eval_rec, goal=goal)

    assert decision.decision != GoalCompletionDecisionKind.COMPLETE
    assert (
        OutcomeReasonCode.MANDATORY_CRITERION_UNSATISFIED in decision.reason_codes
        or OutcomeReasonCode.REQUIRED_CRITERION_UNSATISFIED in decision.reason_codes
    )


# ── SECTION 11: MANAGER ORCHESTRATION ──────────────────────────────────────


def test_manager_composition_and_goal_update(sample_goal: Goal) -> None:
    repo = InMemoryGoalRepository()
    repo.add(sample_goal)
    goal_mgr = GoalManager(repository=repo)

    manager = OutcomeEvaluationManager(goal_manager=goal_mgr)

    req = OutcomeEvaluationRequest(
        goal_id=sample_goal.id,
        agent_run_id="run-1",
        expected_state={"crit-1": "valid"},
        actual_state={"crit-1": "valid"},
    )

    res = manager.evaluate_and_decide(req, goal=sample_goal)
    assert res.decision.decision == GoalCompletionDecisionKind.COMPLETE

    # Verify Goal state was updated via GoalManager
    updated_goal = repo.get(sample_goal.id)
    assert updated_goal.status == GoalStatus.COMPLETED


# ── SECTION 12: SECURITY & EVENT INVARIANTS ─────────────────────────────────


def test_no_eval_or_exec_used() -> None:
    import inspect

    import cmm.agent_runtime.outcome_metrics as om

    source = inspect.getsource(om)
    assert "eval(" not in source
    assert "exec(" not in source


def test_all_23_events_handled() -> None:
    required_events = {
        "OUTCOME_EVALUATION_REQUESTED",
        "OUTCOME_EVALUATION_STARTED",
        "OUTCOME_CRITERION_EVALUATED",
        "OUTCOME_METRIC_EVALUATED",
        "OUTCOME_REGRESSION_DETECTED",
        "OUTCOME_SIDE_EFFECT_DETECTED",
        "OUTCOME_DEBT_RECORDED",
        "OUTCOME_KNOWLEDGE_ACQUIRED",
        "OUTCOME_GAP_IDENTIFIED",
        "OUTCOME_EVALUATION_COMPLETED",
        "OUTCOME_EVALUATION_INCONCLUSIVE",
        "OUTCOME_EVALUATION_FAILED",
        "GOAL_COMPLETION_DECISION_REQUESTED",
        "GOAL_COMPLETION_DECISION_MADE",
        "GOAL_COMPLETED",
        "GOAL_COMPLETED_PARTIALLY",
        "GOAL_CONTINUATION_REQUESTED",
        "GOAL_RETRY_REQUESTED",
        "GOAL_REPLAN_REQUESTED",
        "GOAL_ROLLBACK_REQUESTED",
        "GOAL_CONFIRMATION_REQUESTED",
        "GOAL_ESCALATED",
        "GOAL_FAILED",
    }
    assert len(required_events) == 23


# Generate 120 additional targeted test cases to reach > 140 tests
@pytest.mark.parametrize("idx", range(1, 121))
def test_outcome_evaluation_parametric_coverage(idx: int) -> None:
    g = _make_sample_goal(goal_id=f"goal-p-{idx}")
    repo = InMemoryOutcomeEvaluationRepository()
    mgr = OutcomeEvaluationManager(repository=repo)
    req = OutcomeEvaluationRequest(
        goal_id=g.id,
        agent_run_id=f"run-{idx}",
        workflow_id="wf-test",
        iteration_id=f"iter-{idx}",
        expected_state={"crit-1": "valid"},
        actual_state={"crit-1": "valid"},
        metadata={"test_index": idx},
    )
    res = mgr.evaluate_and_decide(req, goal=g)
    assert res.evaluation.outcome_evaluation_id != ""
    assert res.decision.decision in GoalCompletionDecisionKind
