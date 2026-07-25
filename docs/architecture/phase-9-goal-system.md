# 🎯 Phase 9.2 — Goal System Architecture

## Overview

The Goal System in Phase 9.2 provides the operational foundation for Pursuing, Prioritizing, Tracking, and Satisfying autonomous goals in CMM OS.

It represents goals as stateful operational entities, completely decoupled from agent execution, planning, LLM providers, or specific cognitive reasoning engines.

---

## Operational Goal vs Cognitive Knowledge Item

| Dimension | Operational Goal (Phase 9.2) | Cognitive Knowledge Item (Phase 8) |
| :--- | :--- | :--- |
| **Purpose** | State machine entity tracking execution, status, criteria, priority, and progress. | Declarative memory item representing extracted facts, hypotheses, decisions, or observations. |
| **Mutability** | Mutated via controlled status transitions and audit history logging. | Epistemologically versioned memory entry in the KnowledgeStore. |
| **Responsibility** | Directs agent runtime execution workflow and goal completion conditions. | Provides contextual knowledge and information during cognitive retrieval. |

---

## Core Contracts

1. **`Goal`**: Immutable dataclass representing an operational objective with status, kind, multi-factorial priority, success criteria, constraints, and timestamps.
2. **`GoalPriority`**: Quantitative structure evaluating `score`, `urgency`, `importance`, `user_priority`, `deadline_pressure`, `dependency_impact`, `risk_reduction`, and `estimated_cost`.
3. **`SuccessCriterion`**: Verifiable criterion (`required`, `measurable`, `status`, `evaluator`, `expected_value`, `actual_value`, `evidence`).
4. **`GoalConstraint`**: Operational constraint (`kind`, `severity`, `source`, `condition`).
5. **`GoalDependency`**: Directed relation between goals (`goal_id`, `depends_on_goal_id`, `dependency_type`, `blocking`).
6. **`GoalHistoryEntry`**: Immutable audit entry capturing every state transition (`previous_status`, `new_status`, `actor_id`, `reason`, `timestamp`).

---

## State Transition Finite State Machine

```text
proposed ──> accepted ──> active ──> planning ──> in_progress ──> completed / partially_completed
   │            │           │           │              │
   └───> cancelled / abandoned / superseded <──────────┴────────> failed / blocked / paused
```

### Transition Invariants & Guardrails
- **Terminal States**: `completed`, `partially_completed`, `failed`, `abandoned`, `cancelled`, `superseded` are immutable and cannot transition directly to active/in_progress without explicit reopening.
- **Required Criteria Guard**: `complete_goal()` or transition to `completed`/`partially_completed` fails with `GoalCompletionError` if any required success criterion is not `satisfied` or `waived`.
- **Pause & Resume**: `pause_goal()` stores the preceding active state; `resume_goal()` inspects audit history to restore that exact state.

---

## Goal Repository & Goal Manager

- **`GoalRepository`**: Protocol declaring `add`, `get`, `update`, `search`, `get_children`, `get_dependencies`, `append_history`, and `get_history`.
- **`InMemoryGoalRepository`**: Reference implementation enforcing deep-copy safety so caller mutations do not leak into storage state. Supports deterministic sorting by priority, created_at, and ID.
- **`GoalManager`**: High-level lifecycle coordinator enforcing transition rules, audit log preservation, subgoal hierarchies, dependency checks, and success criteria evaluations.

---

## Current Scope & Limitations

- **No Engine Coupling**: GoalManager does not execute workflows, call LLMs, or invoke cognitive engines.
- **In-Memory Default**: Persistence is handled in-memory; SQLite/durable persistence will be integrated in Phase 9.8.
- **Static Evaluators**: Success criteria evaluation receives explicit result values via `GoalManager.evaluate_success_criteria()` rather than running automated background polling scripts.

---

## Usage Example

```python
from cmm.agent_runtime import (
    Goal,
    GoalKind,
    GoalManager,
    GoalPriority,
    GoalStatus,
    SuccessCriterion,
    SuccessCriterionKind,
    SuccessCriterionStatus,
)

# Initialize Manager
manager = GoalManager()

# Define Goal with required criterion
criterion = SuccessCriterion(
    id="sc-1",
    description="All tests in test suite pass",
    kind=SuccessCriterionKind.VALIDATION,
    required=True,
)

goal = Goal(
    id="goal-project-health",
    title="Ensure project test suite health",
    description="Run and verify repository test suite clean pass",
    kind=GoalKind.MAINTENANCE,
    status=GoalStatus.PROPOSED,
    priority=GoalPriority(score=90.0, urgency=70.0, importance=95.0),
    success_criteria=(criterion,),
)

# Register & transition
manager.register_goal(goal)
manager.change_status("goal-project-health", GoalStatus.ACCEPTED, actor_id="user", reason="Approved")
manager.change_status("goal-project-health", GoalStatus.ACTIVE, actor_id="agent", reason="Activated")

# Evaluate criterion
manager.evaluate_success_criteria(
    "goal-project-health",
    {"sc-1": (SuccessCriterionStatus.SATISFIED, "1775 passed")},
    actor_id="validator",
    reason="Suite execution succeeded",
)

# Complete goal
completed_goal = manager.complete_goal(
    "goal-project-health", actor_id="agent", reason="Goal satisfied"
)
assert completed_goal.status == GoalStatus.COMPLETED
```
