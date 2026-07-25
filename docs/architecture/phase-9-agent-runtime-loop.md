# Phase 9.12 — Agent Runtime Loop Architecture

## 1. Overview & Objectives

Phase 9.12 implements the **Agent Runtime Loop** for **CMM OS**. It provides an explicit, persistent, resumable, deterministic, auditable, fail-safe, and idempotent state machine that orchestrates the execution lifecycle of autonomous agents (`AgentRun`).

The Runtime Loop coordinates existing Phase 9 components (Goal System, Intake, Observation Engine, Cognitive Adapter, Information Acquisition, Workflow Planner, Policy Engine, Autonomy Levels, Human Approval System, Action Budget) without replacing or duplicating their internal domain logic.

---

## 2. Operational Cycle

Every operational cycle progresses through the following canonical pipeline:

```text
Load Goal
↓
Validate Goal
↓
Check Dependencies
↓
Observe
↓
Load Knowledge
↓
Reason
↓
Resolve Information Gaps
↓
Decide
↓
Plan
↓
Evaluate Policies
↓
Request Approval if Required
↓
Reserve Budget
↓
Execute
↓
Validate
↓
Evaluate Outcome
↓
Update Goal
↓
Update Knowledge
↓
Continue / Recover / Complete
```

Each step generates persistent state updates, reason codes, and structured transition records.

---

## 3. Explicit State Machine

### 3.1 Status Enumeration (`AgentRuntimeStatus`)
- **Active States**: `initializing`, `observing`, `reasoning`, `planning`, `executing`, `validating`, `evaluating`, `recovering`
- **Waiting States**: `waiting_for_user`, `waiting_for_resource`, `waiting_for_approval`
- **Resumable States**: `waiting_for_user`, `waiting_for_resource`, `waiting_for_approval`, `paused`, `recovering`, `blocked`
- **Terminal States**: `completed`, `cancelled`, `failed`, `aborted`

### 3.2 Key Transitions
```text
created → initializing → observing → reasoning
reasoning → planning | waiting_for_user | waiting_for_resource | completed | blocked | failed
planning → waiting_for_approval | executing | blocked | failed
executing → validating | recovering | paused | failed | aborted
validating → evaluating | recovering | failed
evaluating → observing | completed | recovering | paused | blocked
recovering → planning | executing | paused | failed | aborted
paused → observing | reasoning | planning | executing | cancelled
blocked → reasoning | cancelled | failed
```

---

## 4. Iterations, Checkpoints, and Resumption

### 4.1 `AgentIteration`
Represents an execution slice within an `AgentRun`. Holds snapshots of reasoning, decision, plan, execution, and validation references.

### 4.2 `RuntimeCheckpoint`
A persistent, immutable point of resumption containing state versions, goal versions, active lock references, budget reservations, and completed step IDs.

### 4.3 Resumption Mechanics
Resuming an `AgentRun` via `resume()`:
1. Validates that the run is in a resumable state (`paused`, `waiting_*`, `blocked`).
2. Loads the target or latest `RuntimeCheckpoint`.
3. Verifies version compatibility and lock ownership.
4. Transitions status back to `observing`, `reasoning`, or `planning`.
5. Emits a new `RuntimeCheckpoint` and updates heartbeat without duplicating completed side-effects.

---

## 5. Idempotency and Lock Management

### 5.1 Idempotency Key Processing
Each operation (`start()`, `step()`, etc.) accepts an optional `idempotency_key`.
- **Same Key + Same Payload**: Returns cached result.
- **Same Key + Conflicting Payload**: Raises `RuntimeIdempotencyConflictError`.

### 5.2 `RuntimeLockManager`
Enforces exclusive and shared lock semantics in memory:
- **Goal Lock**: Exclusive lock on `goal:{goal_id}` before active execution.
- **Resource Locks**: Exclusive or shared locks on files, repositories, or operations.
- Automatic TTL expiration (`expire_due()`) and atomic renewal (`renew()`).

---

## 6. Heartbeat and Abandonment Detection

The Runtime Loop periodically updates a persistent `RuntimeHeartbeat`:
- `last_activity_at`: Updated on every `step()`.
- `expires_at`: Calculated using configurable TTL (default 600s).
- `detect_abandoned()`: Classifies runs with expired activity into `STALLED` (e.g. >300s) or `ABANDONED` (e.g. >900s).

---

## 7. Explicit Architectural Principles

> [!IMPORTANT]
> **Key Runtime Distinction Invariants:**
> - `runtime decision != execution` — Making a decision to plan or execute does not execute the action.
> - `checkpoint != rollback` — A checkpoint marks a resumable state, not an automatic state undo mechanism.
> - `resume != restart` — Resuming restores execution context from the last valid checkpoint; restarting creates a brand new run.
> - `heartbeat expired != automatic recovery` — Expiration marks health as stalled/abandoned for audit and manual intervention, but does not trigger unsafe auto-recovery.
> - `lock acquired != permission` — Acquiring a concurrency lock does not grant policy or autonomy permission to execute an operation.

---

## 8. Public API Exports

Module `cmm.agent_runtime` exports:
- `AgentIteration`, `RuntimeCheckpoint`, `RuntimeTransition`, `RuntimeStepResult`
- `RuntimeHeartbeat`, `RuntimeLock`, `RuntimeResumeRequest`, `RuntimeStepContext`
- `AgentRuntimeRepository`, `InMemoryAgentRuntimeRepository`
- `AgentRuntimeStateMachine`, `RuntimeLockManager`, `AgentRuntimeLoop`, `RuntimeStepHandler`
- Enums & Error hierarchy for Phase 9.12
