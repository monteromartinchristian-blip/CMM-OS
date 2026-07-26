# Phase 9.17 – Outcome Evaluation Architecture

## Overview

Phase 9.17 introduces the **Outcome Evaluation Layer** into the CMM OS Autonomous Agent Runtime. This subsystem provides a deterministic, traceable, fail-safe, and immutable evaluation framework that determines whether an executed workflow or agent run actually satisfies a Goal, meets its mandatory Success Criteria, introduces regressions, technical/operational debt, or unauthorized side effects, and issues formal completion decisions (`GoalCompletionDecision`).

Unlike low-level technical execution outcomes (such as `AgentResultOutcome.SUCCESS`), the Outcome Evaluation Layer focuses on higher-level Goal satisfaction, domain invariants, state verification, evidence sufficiency, and human-in-the-loop authorization.

---

## 1. Architecture & Components

The Outcome Evaluation Layer is structured into modular components operating under strict separation of concerns:

```
[Agent Runtime / Execution]
           │
           ▼
┌────────────────────────────────────────────────────────────────────────┐
│                      OutcomeEvaluationManager                          │
│  (Orchestrates Evaluation Pipeline & GoalManager Status Delegation)   │
└──────────┬─────────────────────────────────────────────────┬───────────┘
           │                                                 │
           ▼                                                 ▼
┌──────────────────────────────┐              ┌───────────────────────────┐
│   OutcomeEvaluationEngine    │              │ GoalCompletionDecision    │
│ (Evaluates State, Criteria,  │              │          Engine           │
│ Regressions, Debt, Knowledge)│              │(Fail-Safe Decision Matrix)│
└──────────┬───────────────────┘              └──────────────┬────────────┘
           │                                                 │
           ├───────────────────────────────┬─────────────────┤
           │                               │                 │
           ▼                               ▼                 ▼
┌──────────────────────┐        ┌────────────────────┐   ┌────────────────┐
│ OutcomeCriterion     │        │ OutcomeState       │   │ OutcomeMetric  │
│ Evaluator            │        │ Comparator         │   │ Evaluator      │
└──────────────────────┘        └────────────────────┘   └────────────────┘
           │                               │                 │
           ▼                               ▼                 ▼
┌──────────────────────┐        ┌────────────────────┐   ┌────────────────┐
│ OutcomeRegression    │        │ OutcomeImpact      │   │ Outcome        │
│ Detector             │        │ Analyzer           │   │ Knowledge      │
│                      │        │                    │   │ Analyzer       │
└──────────────────────┘        └────────────────────┘   └────────────────┘
                                           │
                                           ▼
                                ┌────────────────────┐
                                │ OutcomeEvaluation  │
                                │ Repository         │
                                └────────────────────┘
```

### Component Roles

1. **`OutcomeEvaluationManager`**: Entry point orchestrator. Accepts evaluation requests or contexts, delegates evaluation execution to `OutcomeEvaluationEngine`, obtains completion decisions from `GoalCompletionDecisionEngine`, persists records in `OutcomeEvaluationRepository`, and delegates terminal Goal status transitions to `GoalManager`.
2. **`OutcomeEvaluationEngine`**: Pipeline orchestrator. Computes state comparison diffs, evaluates Success Criteria, calculates quantitative metrics, detects regressions, analyzes side effects/debt, extracts acquired knowledge/gaps, and determines overall evaluation `Outcome` and confidence level.
3. **`GoalCompletionDecisionEngine`**: Pure decision engine applying a strict 12-level fail-safe precedence matrix to issue formal `GoalCompletionDecision` records without mutating Goals directly.
4. **`OutcomeCriterionEvaluator`**: Evaluates individual `SuccessCriterion` definitions against expected vs. actual states, metadata waivers, evidence, and required confirmations.
5. **`OutcomeStateComparator`**: Performs immutable structural comparison between expected state snapshots and actual post-execution state snapshots, returning `StateComparisonDiff`.
6. **`OutcomeMetricEvaluator`**: Evaluates quantitative targets using type-safe comparators (`exact`, `minimum`, `maximum`, `range`, `percentage`, `boolean`, `count`, `duration`, `cost`, custom evaluators) without dynamic code execution (`eval`/`exec`).
7. **`OutcomeRegressionDetector`**: Analyzes state diffs and historical baselines to identify critical, high, medium, and low severity regressions.
8. **`OutcomeImpactAnalyzer`**: Evaluates authorized vs. unauthorized and reversible vs. irreversible side effects, recording generated technical/operational debt.
9. **`OutcomeKnowledgeAnalyzer`**: Identifies acquired facts, deductions, and invalidated knowledge, resolving or recording operational gaps and remaining tasks.
10. **`OutcomeEvaluationRepository`**: Immutable storage for evaluations and decisions supporting thread-safe retrieval and idempotency checks (`InMemoryOutcomeEvaluationRepository`).

---

## 2. Immutable Contracts & Data Models

All contracts in the Outcome Evaluation Layer are frozen Python `@dataclass(frozen=True)` instances with type enforcement, frozen collection fields (`tuple`, `mappingproxy`), ISO-8601 timezone-aware timestamps, and SHA-256 fingerprinting.

Key contracts include:

- **`OutcomeEvaluationRequest`**: Request container specifying `goal_id`, `agent_run_id`, `workflow_id`, `iteration_id`, expected/actual states, evidence, and configuration flags.
- **`OutcomeEvaluationResult`**: Intermediate evaluation result summarizing evaluated criteria, metrics, regressions, debt, and recommended decision.
- **`OutcomeEvaluationContext`**: Execution context combining Goal instance, run reference, state snapshots, policies, approvals, and budget constraints.
- **`OutcomeCriterionResult`**: Evaluated result for a single criterion with `status`, `importance`, `expected_value`, `actual_value`, `evidence_ids`, `confidence`, and `blocking` flags.
- **`OutcomeStateSnapshot`**: Immutable state snapshot recording resources, versions, and metadata at a specific point in time.
- **`OutcomeRegression`**: Detected regression record containing `regression_id`, `severity`, `previous_value`, `current_value`, `reversible`, and `rollback_recommended`.
- **`OutcomeGeneratedDebt`**: Technical or operational debt entry with `debt_id`, `category`, `severity`, `accepted`, `mitigation_plan`, and linked artifacts.
- **`OutcomeSideEffect`**: Recorded side effect with `side_effect_id`, `expected`, `reversible`, `authorized`, and `affected_resources`.
- **`OutcomeKnowledgeAcquisition`**: Acquired knowledge entry with `knowledge_id`, `kind` (`fact`, `inference`, `invalidation`), `statement`, `confidence`, and evidence.
- **`OutcomeGap`**: Operational or information gap remaining after execution.
- **`OutcomeRiskAssessment`**: Risk assessment record with `risk_id`, `category`, `level` (`low`, `medium`, `high`, `critical`), and `acceptable`.
- **`OutcomeEvaluation`**: Immutable aggregate evaluation record containing deterministic SHA-256 `fingerprint`.
- **`GoalCompletionDecision`**: Formal completion decision record containing `decision` kind, `reason_codes`, criteria breakdown, `residual_risk`, and deterministic `fingerprint`.

---

## 3. Success Criteria Evaluation & Importance Rules

`OutcomeCriterionEvaluator` evaluates each `SuccessCriterion` associated with a Goal.

### Criterion Importance Classification

- **`MANDATORY`**: Core goal requirements. Unsatisfied mandatory criteria immediately block Goal completion and trigger `RETRY`, `REPLAN`, or `FAIL`.
- **`REQUIRED`**: Necessary operational criteria. Unsatisfied required criteria block full completion (`COMPLETE`), allowing `COMPLETE_PARTIALLY` if explicitly permitted.
- **`OPTIONAL`**: Secondary criteria. Unsatisfied optional criteria generate warnings or technical debt but do not block Goal completion.
- **`ADVISORY`**: Informational criteria used for optimization and knowledge gathering.

### Evaluation Statuses (`CriterionEvaluationStatus`)

- `SATISFIED`: Expected vs. actual state matched or condition satisfied.
- `PARTIALLY_SATISFIED`: Partial requirement satisfied; never counts as fully satisfied.
- `UNSATISFIED`: Condition failed or state mismatched.
- `WAIVED`: Criterion explicitly exumed by authorized decision.
- `NOT_EVALUATED`: Insufficient data or unexecuted condition; degrades to `INCONCLUSIVE`.
- `INCONCLUSIVE`: Conflicting evidence or evaluation error.

---

## 4. Authorized Waivers

CMM OS permits criterion exemption (`WAIVED`) only under strict authorization controls:

- A criterion is marked `WAIVED` **only if** `metadata.get("waived") is True` AND contains explicit authorization metadata: `waived_by`, `waived_reason`, or `policy_id`.
- Attempting to waive a criterion without explicit authorization raises `OutcomeCriterionEvaluationError("Waiver for criterion ... requires explicit authorization")`.
- Authorized waivers allow a criterion to be treated as satisfied for Goal completion without generating fictitious state matches.

---

## 5. State Comparison & State Comparison Diff

`OutcomeStateComparator` compares an expected `OutcomeStateSnapshot` (or dictionary) against an actual `OutcomeStateSnapshot`.

- **Version Drift Detection**: Detects mismatched resource versions between expected and actual snapshots.
- **Resource Mismatches**: Computes added, removed, modified, and unchanged resources.
- **`StateComparisonDiff`**: Immutable summary object output containing:
  - `snapshot_ids`: `(expected_snapshot_id, actual_snapshot_id)`
  - `added_resources`: Tuple of resource keys present only in actual state.
  - `removed_resources`: Tuple of resource keys missing from actual state.
  - `modified_resources`: Tuple of resource keys with value/version differences.
  - `unchanged_resources`: Tuple of identical resource keys.
  - `version_mismatches`: Dictionary of resource version drift.
  - `is_identical`: Boolean indicating perfect state match.

---

## 6. Metrics & Type-Safe Comparators

`OutcomeMetricEvaluator` evaluates quantitative metric targets against actual values without using unsafe dynamic code execution (`eval()` or `exec()`).

### Supported Comparators

1. **`exact` / `exact_match`**: Strict equality (`actual == expected`).
2. **`minimum` / `min`**: Numerical inequality (`float(actual) >= float(expected)`). Calculates `deviation = actual - expected`.
3. **`maximum` / `max`**: Numerical inequality (`float(actual) <= float(expected)`). Calculates `deviation = actual - expected`.
4. **`range`**: Tuple/list bounds (`min_v <= float(actual) <= max_v`).
5. **`percentage`**: Numerical percentage threshold (`float(actual) >= float(expected)`).
6. **`boolean`**: Boolean match (`bool(actual) == bool(expected)`).
7. **`count` / `duration` / `cost`**: Maximum bound comparison (`float(actual) <= float(expected)`).
8. **Custom Evaluators**: Type-safe evaluators registered via `register_custom_evaluator(name, callable)`.
9. **Unregistered Comparators**: Unregistered or missing comparators evaluate to `status=INCONCLUSIVE` and `confidence=0.0` (never fictitious success).
10. **Type Mismatches**: Unparseable values raise `ValueError`/`TypeError` internally, degrading safely to `INCONCLUSIVE` with error details in metadata.

---

## 7. Evidences, Regressions, Debt & Side Effects

### Evidence Integration

- Evidence records (`OutcomeEvidence`) link evaluation claims to underlying log entries, tool outputs, or verification traces.
- Insufficient evidence (`confidence < 0.5` or missing required evidence) causes `OutcomeEvaluationEngine` to emit `Outcome.INCONCLUSIVE`.

### Regression Detection (`OutcomeRegressionDetector`)

- Compares pre- and post-execution states and validation findings.
- Assigns severity levels: `low`, `medium`, `high`, `critical`.
- A `critical` severity regression immediately blocks Goal completion (`COMPLETE`), triggering `ROLLBACK` (if checkpoints exist) or `ESCALATE`.

### Impact & Technical Debt Analysis (`OutcomeImpactAnalyzer`)

- Identifies unauthorized or unexpected side effects (`OutcomeSideEffect`).
- Unauthorized side effects automatically record technical/operational debt (`OutcomeGeneratedDebt`).
- Unaccepted critical technical debt (`severity == "critical"` and `accepted is False`) triggers decision `ESCALATE`.

---

## 8. Knowledge Acquisition & Operational Gaps

`OutcomeKnowledgeAnalyzer` processes execution evidence and state changes to extract structured domain knowledge:

- **Facts**: Confirmed statements extracted from execution evidence.
- **Inferences**: Deductions derived from multi-step execution traces.
- **Invalidations**: Invalidated prior assumptions or stale knowledge items.
- **Gap Resolution**: Automatically marks operational gaps (`OutcomeGap`) as resolved when corresponding evidence is acquired.

---

## 9. Evaluation Outcomes (`Outcome`)

`OutcomeEvaluationEngine` assigns one of six canonical evaluation outcomes:

1. **`SUCCESS`**: All mandatory/required criteria satisfied, no critical regressions, high confidence.
2. **`PARTIAL_SUCCESS`**: Partial criteria satisfied without mandatory failures.
3. **`NO_CHANGE`**: Execution completed but system state remained unchanged.
4. **`FAILURE`**: Validation failure, unsatisfied mandatory criterion, or unhandled execution error.
5. **`REGRESSION`**: Unintended side effect or state degradation detected.
6. **`INCONCLUSIVE`**: Insufficient evidence, missing evaluators, or state ambiguity.

---

## 10. Goal Completion Decisions & Fail-Safe Precedence Matrix

`GoalCompletionDecisionEngine` processes `OutcomeEvaluation` records to issue one of nine formal completion decisions (`GoalCompletionDecisionKind`):

- **`COMPLETE`**: Goal fully satisfied.
- **`COMPLETE_PARTIALLY`**: Goal partially satisfied under authorized partial completion rules.
- **`CONTINUE`**: Execution should proceed (insufficient evidence or partial progress).
- **`RETRY`**: Transient failure or recovery viable; re-execute operation.
- **`REPLAN`**: Goal insatisified with no state change; trigger workflow replanning.
- **`ROLLBACK`**: Critical regression detected; revert to last valid checkpoint.
- **`PAUSE`**: State inconsistency or unconfirmed user requirement; pause execution.
- **`ESCALATE`**: Unaccepted critical debt or unresolvable error; escalate to operator.
- **`FAIL`**: Terminal failure, exhausted budget, or unsatisfied mandatory criteria without recovery options.

### Fail-Safe Precedence Matrix

`GoalCompletionDecisionEngine` evaluates rules in exact, non-overridable order:

```
┌──────┬──────────────────────────────────────────┬────────────────────────────┐
│ Step │ Condition                                │ Decision Output            │
├──────┼──────────────────────────────────────────┼────────────────────────────┤
│ 1    │ State inconsistency or version drift     │ PAUSE                      │
│ 2    │ Critical regression detected             │ ROLLBACK (if checkpoint)   │
│      │                                          │ / ESCALATE                 │
│ 3    │ Mandatory/blocking criterion unsatisfied │ RETRY (if recovery)        │
│      │                                          │ / REPLAN (if NO_CHANGE)    │
│      │                                          │ / FAIL                     │
│ 4    │ Blocking validation failure              │ FAIL                       │
│ 5    │ Inconclusive outcome / confidence < 0.5  │ CONTINUE                   │
│ 6    │ User confirmation required (unconfirmed) │ PAUSE                      │
│ 7    │ Critical unaccepted debt generated       │ ESCALATE                   │
│ 8    │ Action budget exhausted (budget <= 0)    │ FAIL                       │
│ 9    │ Recovery viable on FAILURE/REGRESSION    │ RETRY                      │
│ 10   │ Partial success outcome                  │ COMPLETE_PARTIALLY (if ok) │
│      │                                          │ / CONTINUE                 │
│ 11   │ Outcome == SUCCESS                       │ COMPLETE                   │
│ 12   │ Fallback / Unknown outcome               │ CONTINUE                   │
└──────┴──────────────────────────────────────────┴────────────────────────────┘
```

---

## 11. User Confirmation Requirements

Structured human confirmation requirements (`OutcomeUserConfirmationRequirement`) are integrated directly into evaluation:

- If `requires_user_confirmation` is set on a criterion or evaluation context, `GoalCompletionDecisionEngine` evaluates Precedence 6, issuing `GoalCompletionDecisionKind.PAUSE` and emitting `GOAL_CONFIRMATION_REQUESTED`.
- User confirmation **cannot** override prior technical validation failures (Precedences 1–4). If a mandatory criterion fails technically, the system retries or fails without requesting user confirmation.

---

## 12. Subsystem Integrations

### GoalManager Integration

- `OutcomeEvaluationManager` does not mutate Goals directly. Instead, when a terminal decision (`COMPLETE`, `COMPLETE_PARTIALLY`, `FAIL`) is issued, it delegates status transitions to `GoalManager` via `complete_goal()` or `change_status()`.
- Evaluated criterion statuses are synced to `GoalManager` via `evaluate_success_criteria()`.

### Runtime Loop & State Machine Integration

- `runtime_state_machine.py` explicitly supports transitions from state `evaluating` to `observing`, `planning`, `executing`, `recovering`, `paused`, `blocked`, `failed`, `cancelled`, `aborted`, and `completed`.

### Recovery Manager Integration

- When `recovery_available=True`, `GoalCompletionDecisionEngine` routes technical failures to `RETRY` or `ROLLBACK`, delegating resolution to Phase 9.16 `RecoveryManager`.

---

## 13. System Events (23 Events)

The Outcome Evaluation Layer publishes 23 fine-grained domain events via the system `EventBus`:

1. `OUTCOME_EVALUATION_REQUESTED`: Evaluation pipeline requested.
2. `OUTCOME_EVALUATION_STARTED`: Evaluation processing initiated.
3. `OUTCOME_CRITERION_EVALUATED`: Individual criterion evaluated.
4. `OUTCOME_METRIC_EVALUATED`: Quantitative metric evaluated.
5. `OUTCOME_REGRESSION_DETECTED`: State regression detected.
6. `OUTCOME_SIDE_EFFECT_DETECTED`: Side effect recorded.
7. `OUTCOME_DEBT_RECORDED`: Technical/operational debt logged.
8. `OUTCOME_KNOWLEDGE_ACQUIRED`: Domain knowledge acquired.
9. `OUTCOME_GAP_IDENTIFIED`: Operational gap recorded.
10. `OUTCOME_EVALUATION_COMPLETED`: Evaluation pipeline successfully completed.
11. `OUTCOME_EVALUATION_INCONCLUSIVE`: Evaluation completed with inconclusive outcome.
12. `OUTCOME_EVALUATION_FAILED`: Evaluation execution failed.
13. `GOAL_COMPLETION_DECISION_REQUESTED`: Decision computation requested.
14. `GOAL_COMPLETION_DECISION_MADE`: Completion decision record created.
15. `GOAL_COMPLETED`: Goal fully completed event.
16. `GOAL_COMPLETED_PARTIALLY`: Goal partially completed event.
17. `GOAL_CONTINUATION_REQUESTED`: Execution continuation requested.
18. `GOAL_RETRY_REQUESTED`: Operation retry requested.
19. `GOAL_REPLAN_REQUESTED`: Workflow replan requested.
20. `GOAL_ROLLBACK_REQUESTED`: Checkpoint rollback requested.
21. `GOAL_CONFIRMATION_REQUESTED`: User confirmation requested.
22. `GOAL_ESCALATED`: Issue escalated to operator.
23. `GOAL_FAILED`: Goal execution failed.

---

## 14. Custom Error Hierarchy

All error classes inherit from `AgentRuntimeError`:

```
AgentRuntimeError
 └── OutcomeEvaluationError
      ├── OutcomeEvaluationContextError
      ├── OutcomeEvaluationExecutionError
      ├── OutcomeEvaluationRepositoryError
      ├── OutcomeEvaluationPolicyError
      ├── OutcomeCriterionError
      │    ├── OutcomeCriterionEvaluationError
      │    └── OutcomeCriterionNotFoundError
      ├── OutcomeMetricError
      ├── OutcomeRegressionError
      ├── OutcomeSideEffectError
      ├── OutcomeDebtError
      ├── OutcomeKnowledgeError
      ├── OutcomeEvidenceError
      │    └── OutcomeEvidenceInsufficientError
      ├── GoalCompletionDecisionError
      ├── GoalCompletionBlockedError
      ├── OutcomeInconclusiveError
      ├── OutcomeUserConfirmationRequiredError
      ├── OutcomeStateComparisonError
      └── OutcomeFingerprintError
```

---

## 15. Security Invariants

- **No Code Execution**: `OutcomeMetricEvaluator` strictly avoids dynamic `eval()` or `exec()` execution. All comparators use static, type-safe comparison logic.
- **Immutability & Tamper-Proof Fingerprinting**: All evaluation contracts use `@dataclass(frozen=True)` and compute SHA-256 fingerprints over normalized fields.
- **Fail-Safe Precedence**: Security, regression, and mandatory criterion checks precede any progress or completion decisions.

---

## 16. Usage Example

```python
from cmm.agent_runtime import (
    GoalManager,
    InMemoryGoalRepository,
    InMemoryOutcomeEvaluationRepository,
    OutcomeEvaluationManager,
    OutcomeEvaluationRequest,
    SuccessCriterion,
    GoalStatus,
)

# 1. Initialize repository and managers
goal_repo = InMemoryGoalRepository()
goal_mgr = GoalManager(repository=goal_repo)
eval_repo = InMemoryOutcomeEvaluationRepository()

eval_manager = OutcomeEvaluationManager(
    repository=eval_repo,
    goal_manager=goal_mgr,
)

# 2. Prepare evaluation request
request = OutcomeEvaluationRequest(
    goal_id="goal-service-deploy-101",
    agent_run_id="run-8821",
    workflow_id="wf-deploy",
    iteration_id="iter-3",
    expected_state={"service_status": "running", "http_code": 200},
    actual_state={"service_status": "running", "http_code": 200},
)

# 3. Execute evaluation and decision
decision = eval_manager.evaluate_and_decide(request)

print(f"Decision: {decision.decision.value}")
print(f"Reason Codes: {[rc.value for rc in decision.reason_codes]}")
print(f"Fingerprint: {decision.fingerprint}")
```

---

## 17. Testing Strategy

The test suite in `tests/agent_runtime/test_outcome_evaluation.py` provides 164 dedicated unit tests covering:

- **Contract Immutability**: Verifies `@dataclass(frozen=True)` immutability and fingerprint consistency.
- **Criterion Evaluation**: Tests mandatory, required, optional, advisory, partial match, and waiver authorization rules.
- **Metric Evaluation**: Tests all 12 comparator types, type safety, custom evaluators, and error degradation.
- **State Comparison**: Verifies version drift detection and diff calculations.
- **Regression & Debt Analysis**: Tests regression severity assignment and debt generation for unauthorized side effects.
- **Decision Engine Precedence**: Tests all 12 fail-safe precedence levels individually.
- **Repository Idempotency**: Tests thread-safety, query filters, and deduplication.
- **Event Publishing**: Verifies emission of all 23 domain events with accurate payloads.
- **Security Audit**: Validates absence of `eval()` or `exec()` in evaluation components.
