# Phase 9.16 — Recovery Manager

## Overview

The **Recovery Manager** in CMM OS provides an explicit, configurable, deterministic, and auditable failure-handling system for the Autonomous Agent Runtime. It analyzes runtime failures, classifies errors, evaluates recovery policies (retry, replan, rollback, escalation), checks constraints (budget, permissions, state consistency, checkpoint availability), and produces structured, reproducible recovery decisions consummated by the Agent Runtime loop.

---

## Architecture & Integration

```
                                  +-----------------------+
                                  |   Runtime Failure     |
                                  +-----------+-----------+
                                              |
                                              v
                                  +-----------------------+
                                  |    RecoveryContext    |
                                  +-----------+-----------+
                                              |
                                              v
                              +-------------------------------+
                              |   RecoveryErrorClassifier     |
                              +---------------+---------------+
                                              |
                                              v
                              +-------------------------------+
                              |    RecoveryPolicyResolver     |
                              +---------------+---------------+
                                              |
                                              v
                              +-------------------------------+
                              |   RecoveryDecisionEngine      |
                              +---------------+---------------+
                                              |
                                              v
                              +-------------------------------+
                              |      RecoveryDecision         |
                              +---------------+---------------+
                                              |
                                              v
                              +-------------------------------+
                              |   RecoveryStrategyExecutors   |
                              +---------------+---------------+
                                /             |             \
                               v              v              v
                        [OperationExec] [CheckpointRest] [Approval/EventBus]
```

The Recovery Manager integrates seamlessly with:
- **Operation Execution Adapter (Phase 9.13)** for retries and modified parameter execution.
- **Validation Integration (Phase 9.14)** for post-recovery and rerun validation.
- **Checkpoints & Transactions (Phase 9.15)** for rollback and compensation.
- **Action Budget Layer (Phase 9.9)** to enforce budget limits on retries and recovery.
- **Human Approval System (Phase 9.10)** for approval-gated strategies.
- **Runtime Loop & State Machine (Phase 9.12)** for status updates.

---

## Contracts

- `RecoveryContext`: Immutable, serializable context capturing failure metadata, error dictionary, validation results, checkpoints, retry history, budget, and side effects.
- `RecoveryDecision`: Immutable decision payload containing strategy, reason codes, confidence, approval requirements, checkpoint ID, delay seconds, and fingerprint.
- `RecoveryAttempt`: Records an individual attempt index, strategy, status, and outcome.
- `RecoveryHistory`: Sequence of recovery attempts for a given context.
- `RetryPolicy`: Configures maximum attempts, backoff strategy, initial/max delays, jitter, allowed/prohibited operations, and non-retryable error filters.
- `ReplanPolicy`: Configures replan limits, criteria preservation, and prohibitions.
- `RollbackPolicy`: Configures automatic versus approval-gated rollback per operation and allowed checkpoint statuses.
- `EscalationPolicy`: Triggers, escalation target, required evidence, and state preservation flags.
- `RecoveryExecutionResult`: Final execution outcome containing status, success flag, attempt details, and strategy result.

---

## Error Classification & Decision Precedence

The `RecoveryErrorClassifier` inspects exception types, CMM OS error hierarchies, validation findings, side effect reversibility, checkpoint integrity, and budget state to generate an `ErrorClassification`.

### Fail-Safe Decision Precedence Order

1. **Inconsistent State / Corrupted Checkpoints** → `ESCALATE` / `FAIL`
2. **Irreversible Side Effect / Potential Damage** → `ESCALATE` / `REQUEST_APPROVAL`
3. **Missing Permission or Approval** → `REQUEST_APPROVAL` / `ASK_USER`
4. **Rollback or Compensation Failure** → `ESCALATE`
5. **Policy Conflict or Contradiction** → `ESCALATE`
6. **Budget Exhausted** → `ESCALATE` / `FAIL`
7. **Retries Exhausted** → `ROLLBACK` / `REPLAN` / `ESCALATE` (never `RETRY`)
8. **Non-Retryable Error** → `REPLAN` / `ROLLBACK` / `ESCALATE` / `FAIL`
9. **Safe Checkpoint Rollback Available** → `ROLLBACK`
10. **Compensation Available** → `COMPENSATE`
11. **Rerun Validation Needed** → `RERUN_VALIDATION`
12. **Reload / Reobserve Resource** → `REOBSERVE` / `RELOAD_RESOURCE`
13. **Standard Retry** → `RETRY` (with exponential/linear/constant backoff)
14. **Retry with Modified Parameters** → `RETRY_WITH_MODIFIED_PARAMETERS`
15. **Replan Goal/Workflow** → `REPLAN`
16. **Ask User / Request Approval** → `ASK_USER` / `REQUEST_APPROVAL`
17. **Escalate to Human/Operator** → `ESCALATE`
18. **Terminal Actions** → `PAUSE` / `ABORT` / `FAIL`

---

## Safety Invariants

- **No Infinite Retries**: Retries are strictly bounded by `maximum_attempts` in `RetryPolicy`.
- **Non-Retryable Precedence**: Non-retryable error rules override retryable classifications.
- **No False Rollbacks**: Rollback requires a valid, non-expired active checkpoint verified by `CheckpointIntegrityVerifier`.
- **No Hidden Failures**: All original errors, stack traces, and evidence bundles are preserved in `RecoveryEvidence`.
- **No Goal Degradation**: Replanning preserves original goal ID and success criteria; criteria cannot be silently weakened.
- **No Privilege Elevation**: Recovery strategies cannot elevate permissions or bypass validation gates.
- **Budget Compliance**: Retries and rollbacks consume action budget; budget exhaustion blocks retry and triggers escalation.
- **Deterministic Backoff**: `RecoveryBackoffCalculator` computes delays without calling real `time.sleep()`.

---

## Event Bus Notification Stream

The Recovery Manager publishes audit events:
- `RECOVERY_CONTEXT_CREATED`
- `RECOVERY_DECISION_MADE`
- `RECOVERY_STRATEGY_STARTED`
- `RECOVERY_STRATEGY_SUCCEEDED`
- `RECOVERY_STRATEGY_FAILED`
- `RECOVERY_ESCALATED`

---

## Testing Strategy

Unit test coverage (`tests/agent_runtime/test_recovery_manager.py`) verifies:
1. Immutability, serialization, and fingerprinting of contracts.
2. Thread safety, idempotency, and conflict detection in `InMemoryRecoveryRepository`.
3. Multi-dimensional error classification in `RecoveryErrorClassifier`.
4. Policy evaluator rules (max attempts, non-retryable precedence, backoff calculation).
5. Deterministic backoff calculations (NONE, CONSTANT, LINEAR, EXPONENTIAL with jitter).
6. Fail-safe decision precedence order in `RecoveryDecisionEngine`.
7. Strategy executor adapters and delegation to 9.10, 9.13, 9.14, and 9.15 services.
8. 2-step (`decide`/`execute`) and composition (`recover`) workflows in `RecoveryManager`.
9. Prevention of infinite retries, privilege elevation, goal criteria mutation, and fake rollbacks.
10. Full regression against 9.12–9.15 suites and global OS test suite.
