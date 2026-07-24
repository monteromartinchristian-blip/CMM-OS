# 7.13 — Integration with the Existing System

Continuous Validation is fully integrated as a transversal capability across CMM OS, connecting directly into the Semantic Engine, Execution Engine, Planner, Kernel Events, and Technical Memory.

## Architecture & Integration Overview

```
Semantic Engine (Operations & ChangeSets)
          │
          ▼
Execution Engine (ActionRuntime & Executors) ◄──► ValidationIntegrationService
          │                                              │
          ▼                                              ├─► KernelEventPublisher (kernel.events)
Planner (Execution Graphs & DAG Nodes)                   ├─► ValidationMemoryAdapter (TechnicalMemory)
          │                                              └─► CommitGateEvaluator
          ▼
Validation Decision & Rollback Coordinator
```

## Subsystem Integrations

### 1. Semantic Engine Integration (`SemanticValidationAdapter`)
- Adapts semantic operations and `ChangeSet` instances into `ValidationContext`.
- Dynamically resolves impact policies (`fast_static_only`, `structural_only`, `default`).
- Preserves `validation_id` without executing Git mutations (`git commit`, `git push`).
- Supports opt-in integration via `validation_enabled=False` or `validation_service=None` for backward compatibility.

### 2. Execution Engine Integration (`ExecutionValidationCoordinator`)
- Pre-execution validation check: Ensures pre-conditions are met prior to mutating project state; halts execution without rollback if preconditions fail.
- Post-execution validation check: Evaluates actual changes against continuous validation rules.
- Rollback execution: Triggers transactional rollback handlers upon blocking failures, preserving the original validation error trace.

### 3. Planner Integration (`PlannerValidationAdapter`)
- Extends planner execution graphs with `ValidationPlanNode` data structures.
- Enforces structural correctness: cycle detection, step/policy validation, and dependency resolution.
- Maps validation outcomes to plan action decisions (`continue`, `retry`, `replan`, `rollback`, `stop`, `ask_user`, `escalate`).

### 4. Kernel Event System (`KernelEventPublisher`)
- Emits typed, versioned lifecycle events (`validation.started`, `validation.step.started`, `validation.step.completed`, `validation.failed`, `validation.completed`, `validation.gate.approved`, `validation.gate.rejected`).
- Uses `kernel.events.event.Event`.
- Supports `best_effort` policy preventing event transport issues from corrupting validation results.
- Strips authorization tokens, credentials, and sensitive headers from metadata.

### 5. Technical Memory (`ValidationMemoryAdapter`)
- Persists structured summaries (`ValidationMemoryRecord`) to `TechnicalMemory`.
- Configurable retention policy (`blocking_only`, `always`, `failed_only`, `gate_rejected`, `recurring`, `never`).
- Enforces confidentiality by excluding raw binary artifacts, environment variables, and un-sanitized log streams.

### 6. Public Facade (`ValidationIntegrationService`)
- Central entry point coordinating pipeline execution, gate evaluations, event notifications, memory persistence, and decision logic.
- Exposed via `cmm.validation` and `cmm.validation.integration`.

## Security & Confidentiality

- Path Traversal Guards: Enforces `changed_files` to remain strictly within `project_root`.
- Non-destructive Git Policy: Performs no automated git commits, pushes, rebase, or destructive branch modifications.
- Secret Sanitization: Automatically redacts passwords, tokens, API keys, and authorization headers from event payloads and memory records.

## Guideline for Future Autonomous Agents (Phases 8 & 9)

Future Phase 8 (Autonomous Repair) and Phase 9 (Continuous Improvement) agents should consume `ValidationDecision` and `ValidationMemoryRecord` instances directly from `ValidationIntegrationService` to determine whether to apply code patches, request user clarification, or trigger iterative replanning.
