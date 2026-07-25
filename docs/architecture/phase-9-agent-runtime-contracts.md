# Phase 9.1 — Agent Runtime Contracts

## Overview

This module (`cmm.agent_runtime`) defines the foundational, immutable, typed, and serializable contracts for the CMM OS Autonomous Agent Runtime.

## Responsibilities of Each Contract

- **`AgentDefinition`**: Declarative configuration profile specifying an agent's reasoning profile, policies, permitted/prohibited operations, autonomy level, budget, and recovery policies. Contains no execution logic.
- **`AgentRun`**: Active execution tracking contract referencing exactly one agent (`agent_id`) and one goal (`goal_id`), tracking current status, iteration counter, active workflows/tasks, reasoning sessions, and timestamps.
- **`RuntimeDecision`**: Structured audit log contract for transitions emitted by the runtime state machine, recording decision types, confidence score, reason codes, inputs, policy results, and approval requirements.
- **`AgentResult`**: Final outcome contract produced at the termination of an agent run, capturing final status, outcome, confidence, trace ID, duration, workflow/operation execution summaries, validations, and knowledge/memory updates.

## Boundaries of Phase 9.1

Phase 9.1 is strictly restricted to foundational contracts, enums, errors, and immutability invariants. It does **not** include:
- `Goal` system or goal management/persistence (Phase 9.2+);
- `ObservationEngine` or `PolicyEngine`;
- Approval systems, budget managers, or recovery strategies;
- Runtime execution loop, CLI, or API endpoints;
- AI provider integrations or LLM client calls.

## Integration & Relationship with Other Layers

```
                     ┌─────────────────────────┐
                     │     Agent Runtime       │
                     │  (cmm.agent_runtime)    │
                     └────────────┬────────────┘
                                  │
    ┌─────────────────┬───────────┼───────────┬─────────────────┐
    ▼                 ▼           ▼           ▼                 ▼
Cognitive Layer   Knowledge    Planner    Execution System  Validation System
  (Phase 8)        Store      (Phase 4)      (Phase 5)         (Phase 7)
```

- **Cognitive Layer**: Agent profiles select reasoning profiles and process cognitive insights without duplicating reasoning logic.
- **Planner & Execution**: Agent runtime decisions reference workflow plans and task executions without duplicating planning algorithms or operational dispatchers.
- **Validation System**: Validation results and findings are referenced in `RuntimeDecision` and `AgentResult` without re-implementing verification rules.

## Key Architectural Invariants

1. `AgentDefinition` configures the runtime but executes no logic.
2. `AgentRun` references exactly one agent and one goal.
3. Autonomy levels and iteration counters cannot be negative (`>= 0`).
4. Timestamps must be timezone-aware; completion timestamps cannot precede start timestamps (`started_at <= completed_at`).
5. Internal collections (`tuples`, `MappingProxyType`) enforce deep immutability across instances.
6. Contracts serialize (`to_dict`/`serialize`) and deserialize (`from_dict`/`from_mapping`) with 100% roundtrip fidelity.
7. Unknown enum string values are rejected with `InvalidAgentContractError`.
8. Metadata keys must be strings and do not modify public contract properties.
9. No direct coupling to concrete AI models, backends, or execution engines.

## Construction and Serialization Example

```python
from datetime import datetime, timezone
from cmm.agent_runtime import (
    AgentDefinition,
    AgentRun,
    AgentRuntimeStatus,
    RuntimeDecision,
    RuntimeDecisionType,
)

# 1. Create declarative agent definition
agent_def = AgentDefinition(
    id="agent-maintenance",
    name="Project Maintenance Agent",
    version="1.0.0",
    description="Maintains project structure and standards",
    reasoning_profile="project",
    runtime_policy="maintenance-policy",
    observation_profile="repo-observer",
    autonomy_level=2,
    allowed_goal_types=("project_improvement",),
)

# 2. Track an active agent run
now = datetime.now(timezone.utc)
run = AgentRun(
    id="agent-run-101",
    agent_id=agent_def.id,
    goal_id="goal-202",
    status=AgentRuntimeStatus.REASONING,
    autonomy_level=agent_def.autonomy_level,
    current_iteration=1,
    started_at=now,
    updated_at=now,
)

# 3. Serialize and reconstruct
run_data = run.to_dict()
reconstructed_run = AgentRun.from_dict(run_data)
assert reconstructed_run == run
```
