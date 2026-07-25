# Phase 9.5 — Cognitive Adapter Architecture

## Overview

The **Cognitive Adapter** (Phase 9.5) acts as a decoupled translation and coordination bridge between the **Autonomous Agent Runtime** (Goal System, Observation Engine, Agent Runs) and the **Cognitive Layer** (Phase 8).

It translates operational contracts (`Goal`, `AgentRun`, `ObservationSnapshot`, explicit resources, knowledge queries, constraints, permissions) into auditable cognitive contexts (`AgentCognitiveContext` / `ReasoningContext`), invokes the Cognitive Layer (`CognitiveCycleEngine` / `ReasoningEngine`), and translates the cognitive outcome (`CognitiveResult`) into a structured operational recommendation (`AgentCognitiveResult`).

---

## Architectural Principle

The Cognitive Adapter is strictly a **translation and coordination layer**.

### Responsibilities
* Validate cognitive requests and enforce contract invariants.
* Resolve cognitive reasoning profiles deterministically (`general`, `project`, domain profiles).
* Convert `ObservationSnapshot` into Cognitive `Resource` instances via `ObservationResourceAdapter`.
* Aggregate and deduplicate explicit resources, snapshot resources, and queried knowledge items.
* Enforce resource permissions and sensitivity boundaries (`INTERNAL`, `SENSITIVE`, `HIGHLY_SENSITIVE`, `RESTRICTED`).
* Manage Cognitive Session modes (`NEW`, `RESUME`, `FORK`, `STATELESS`).
* Invoke the Cognitive Layer without duplicating reasoning or gap-detection logic.
* Translate Cognitive Results deterministically into operational decisions (`plan`, `ask_user`, `load_resource`, `insufficient_information`, `pause`, `escalate`, `complete_without_action`, `continue_reasoning`, `fail`).
* Maintain trace and session references for full auditability.

### Boundaries & Restrictions
The Cognitive Adapter MUST NOT:
* Reason by itself or apply parallel cognitive rules.
* Detect gaps with its own logic or generate questions independently.
* Execute operations, modify system state, or plan workflows.
* Approve actions or bypass security policies.
* Persist memory proposals automatically.
* Alter cognitive results, inflate confidence, or elevate hypotheses to facts.
* Swallow exceptions or hide contradictions and uncertainty.

---

## Core Contracts

### Enums
* **`AgentCognitiveStatus`**: `pending`, `preparing`, `reasoning`, `waiting_for_user`, `waiting_for_resource`, `completed`, `partial`, `insufficient_information`, `blocked`, `failed`, `cancelled`.
* **`AgentCognitiveDecision`**: `continue_reasoning`, `ask_user`, `load_resource`, `search`, `plan`, `pause`, `escalate`, `complete_without_action`, `insufficient_information`, `fail`.
* **`CognitiveSessionMode`**: `new`, `resume`, `fork`, `stateless`.
* **`CognitiveResourceStrategy`**: `observations_only`, `knowledge_only`, `observations_and_knowledge`, `explicit_resources`, `automatic`.

### Data Models
* **`AgentCognitiveRequest`**: Contains `id`, `agent_run_id`, `goal_id`, `objective`, `reasoning_profile`, `observation_snapshot_id`, `observation_snapshot`, `resource_ids`, `resources`, `knowledge_query`, `constraints`, `permissions`, `maximum_questions`, `requested_depth`, `session_mode`, `cognitive_session_id`, `resource_strategy`, `temporal_reference`, `language`, `actor_id`, `metadata`, `created_at`.
* **`AgentCognitiveContext`**: Auditable evidence structure capturing prepared context before reasoning (Goal, AgentRun, Snapshot, derived & explicit resources, knowledge, constraints, permissions, profile, session reference).
* **`AgentCognitiveResult`**: Operational output contract delivering recommended decision, reasoning IDs, facts, hypotheses, contradictions, information gaps, questions, recommendations, confidence, and status flags.
* **`AgentCognitiveSessionReference`**: Metadata tracking session ID, mode, parent session ID, and goal linkage.
* **`AgentCognitiveTraceReference`**: Audit reference linking request/run to cognitive reasoning trace.
* **`AgentCognitiveWarning`**: Structured warning representation.
* **`AgentCognitiveConfiguration`**: Default settings (profiles, depth, limits, thresholds).

---

## Decision Translation Rules

The translation from `CognitiveResult` to `AgentCognitiveResult` is deterministic:

| Condition | Translated Decision | Status |
| :--- | :--- | :--- |
| Unhandled error / failed cognitive status | `fail` | `failed` |
| Blocking questions exist / `waiting_for_user` | `ask_user` | `waiting_for_user` |
| Blocking resource gaps exist / `waiting_for_resource` | `load_resource` | `waiting_for_resource` |
| Unresolvable blocking gaps / `insufficient_information` | `insufficient_information` | `insufficient_information` |
| Critical contradiction / human review required | `escalate` | `blocked` |
| Session paused / permission block | `pause` | `blocked` |
| Objective completely answered without operations | `complete_without_action` | `completed` |
| Reasoning partial within budget | `continue_reasoning` | `partial` |
| Actionable outcome, no blocking gaps | `plan` | `completed` |

---

## Resource Aggregation & Deduplication

1. **Derived Resources**: Extracted from `ObservationSnapshot` via `ObservationResourceAdapter`.
2. **Explicit Resources**: Provided directly in `AgentCognitiveRequest.resources`.
3. **Queried Resources**: Loaded by ID or `KnowledgeQuery`.
4. **Deduplication**: Deduplicated by `Resource.id` or domain/kind/source fingerprint while preserving first-occurrence order.
5. **Permissions**: Rejects access to `RESTRICTED` or `SENSITIVE` resources if required permissions (`restricted_access`, `sensitive_access`, `admin`) are missing.

---

## Session Management

* **`NEW`**: Instantiates a new cognitive session reference (`cog-session-{uuid}`).
* **`RESUME`**: Validates that `cognitive_session_id` exists and belongs to the requested `goal_id`.
* **`FORK`**: Creates a child session linked to `parent_session_id`.
* **`STATELESS`**: Performs one-shot reasoning without session persistence.

---

## Errors & Safety

Hierarchical exception tree under `CognitiveAdapterError`:
* `InvalidAgentCognitiveContractError`: Invariant violations on request or result.
* `CognitiveSessionNotFoundError`: Resume requested for missing session.
* `CognitiveSessionMismatchError`: Resume requested for session owned by another goal.
* `CognitiveProfileResolutionError`: Profile resolver failure.
* `CognitiveResourceAccessError`: Permission denied on sensitive resource.
* `CognitiveResultTranslationError`: Translation failure.
* `CognitiveAdapterExecutionError`: Runtime failure in Cognitive Layer.

---

## Integration with Phase 9.6 & Phase 9.7

* **Phase 9.6 (Information Acquisition Strategy)**: Consumes `AgentCognitiveResult` when decision is `load_resource`, `ask_user`, or `insufficient_information` to formulate a gap resolution strategy.
* **Phase 9.7 (Planner Adapter)**: Consumes `AgentCognitiveResult` when decision is `plan` to construct executable plans.

---

## Example Usage

```python
from cmm.agent_runtime import (
    AgentCognitiveService,
    AgentCognitiveRequest,
    AgentCognitiveDecision,
    CognitiveSessionMode,
)

service = AgentCognitiveService()

request = AgentCognitiveRequest(
    agent_run_id="agent-run-101",
    goal_id="goal-202",
    objective="Analyze refactoring safety",
    reasoning_profile="project",
    session_mode=CognitiveSessionMode.NEW,
)

result = service.analyze(request)

if result.recommended_decision == AgentCognitiveDecision.PLAN:
    print(f"Ready for planning with confidence {result.confidence}")
elif result.recommended_decision == AgentCognitiveDecision.ASK_USER:
    print(f"Questions for user: {result.questions}")
elif result.recommended_decision == AgentCognitiveDecision.LOAD_RESOURCE:
    print(f"Resources required: {result.information_gaps}")
```
