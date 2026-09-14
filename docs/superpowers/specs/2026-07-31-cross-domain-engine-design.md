# Phase 10.9 Cross-Domain Engine Design

## Status

Approved design for implementation planning.

## Objective

Implement a real runtime `CrossDomainEngine` that coordinates reasoning, planning, agent execution, workflows and knowledge across multiple domains while preserving coherence, partial results, provenance, permissions and explicit stop conditions.

The engine is an orchestrator, not a second Reasoning Engine. It must not duplicate the internals of the Cognitive Layer, Planner, Agent Runtime, Workflow Engine or Knowledge Graph.

## Architecture

```text
CrossDomainRequest
        ↓
Domain Resolver
        ↓
Domain Composition
        ↓
Cross-Domain Coordination Loop
        ├── Cognitive Port
        ├── Planner Port
        ├── Agent Runtime Port
        ├── Workflow Port
        └── Knowledge Port
        ↓
Aggregation
        ↓
CrossDomainResult
```

All integrations use narrow injectable ports. The engine may call real adapters but never embeds subsystem behavior.

## Responsibilities

The engine must:

- resolve and compose requested domains;
- coordinate primary and supporting domains;
- transfer context with provenance;
- reuse entities and timelines;
- coordinate and structurally deduplicate questions;
- detect dependencies, contradictions and cross-domain gaps;
- coordinate operations and workflows through ports;
- maintain permissions and partial results;
- stop on blockers and configured limits;
- escalate to human review;
- produce one consolidated result.

The engine must not:

- implement cognitive reasoning;
- execute operations directly;
- interpret workflows internally;
- call LLMs directly;
- access registries, stores, memory or persistence directly;
- emit events;
- implement retries, queues or distributed scheduling;
- hide adapter failures;
- infer semantic equivalence from unrestricted text.

## Runtime Model

Phase 10.9 is synchronous and deterministic. Potentially parallel groups may be represented declaratively, but actual execution remains sequential. Real concurrency is deferred.

Independent domains may continue after a partial failure. Blocking propagates only to dependent work unless the blocker is global.

## Enums

### CrossDomainStatus

```text
PENDING
RUNNING
COMPLETED
PARTIAL
BLOCKED
FAILED
REQUIRES_REVIEW
LIMIT_REACHED
```

Final results may not use `PENDING` or `RUNNING`.

### Supporting enums

Define explicit enums where useful for:

- domain result status;
- port status;
- contradiction severity;
- dependency kind;
- transfer kind;
- limit kind;
- coordination stage.

Do not use free strings where closed semantics are required.

## Core Contracts

All contracts are frozen, slotted, deeply immutable, JSON-safe and strictly serializable with unknown fields rejected.

### CrossDomainRequest

Fields:

```text
id
objective
primary_domain
supporting_domains
session_id
resources
constraints
permissions
maximum_domains
maximum_domain_hops
maximum_iterations
maximum_questions
maximum_operations
maximum_external_calls
maximum_cost
maximum_duration_ms
trace_id
metadata
```

Invariants:

- non-empty ID and objective;
- canonical primary domain;
- supporting domains unique and excluding primary;
- total domains within `maximum_domains`;
- numeric limits strictly positive;
- bool rejected as int/float;
- finite cost values;
- immutable resources, constraints and permissions;
- strict metadata validation.

### CrossDomainContextSnapshot

Fields:

```text
request_id
composition_id
active_domains
visited_domains
domain_hops
iteration
shared_entities
shared_timelines
shared_findings
open_questions
answered_questions
dependencies
contradictions
gaps
partial_results
consumed_operations
consumed_external_calls
estimated_cost
started_at
metadata
```

This is an immutable execution snapshot, not persistent state.

### CrossDomainDomainResult

Fields:

```text
domain_id
status
findings
questions
dependencies
contradictions
gaps
recommendations
operations
workflow_requests
entities
timelines
confidence
metadata
```

Partial findings remain valid when a domain is blocked or fails. Operations and workflow requests are declarative requests.

### CrossDomainDecision

Fields:

```text
code
stage
domain_id
action
reason
blocking
iteration
metadata
```

Minimum codes:

```text
DOMAIN_SELECTED
DOMAIN_SKIPPED
CONTEXT_TRANSFERRED
QUESTION_DEDUPLICATED
OPERATION_COORDINATED
WORKFLOW_COORDINATED
LIMIT_REACHED
BLOCK_PROPAGATED
HUMAN_REVIEW_REQUESTED
PORT_SKIPPED
PORT_UNAVAILABLE
PARTIAL_RESULT_RETAINED
```

### CrossDomainContradiction

Fields:

```text
id
domains
subject
statements
severity
resolved
resolution
requires_review
provenance
metadata
```

At least two unique domains are required. Unresolved contradictions are never silently discarded.

### CrossDomainDependency

Fields:

```text
source_domain
target_domain
kind
description
blocking
satisfied
provenance
metadata
```

Dependency identity is structural. Unsatisfied blocking dependencies affect dependent work only.

### CrossDomainGap

Fields:

```text
code
domain_id
description
required_information
blocking
recoverable
metadata
```

Recoverable gaps may produce questions. Blocking unrecoverable gaps stop dependent work.

### CrossDomainLimits

Fields:

```text
domains_used
domain_hops_used
iterations_used
questions_used
operations_used
external_calls_used
estimated_cost
elapsed_ms
reached_limits
metadata
```

All counters are non-negative. Reached limits are unique and deterministically ordered.

### CrossDomainResult

Fields:

```text
id
status
objective
request_id
composition_id
domain_results
shared_findings
contradictions
dependencies
cross_domain_gaps
recommendations
open_questions
decisions
limits
confidence
trace_id
started_at
completed_at
metadata
```

Invariants:

- final status only;
- completion time not before start;
- `BLOCKED` requires an unresolved blocking condition;
- `LIMIT_REACHED` requires a reached limit;
- `REQUIRES_REVIEW` requires an unresolved review condition;
- `PARTIAL` requires useful retained output plus incomplete non-blocking work;
- confidence is `None` or finite in `[0, 1]`.

## Port Contracts

### DomainResolutionPort

```python
class DomainResolutionPort(Protocol):
    def resolve(self, request: CrossDomainRequest) -> DomainResolutionResult: ...
```

The real adapter reuses Phase 10.7.

### DomainCompositionPort

```python
class DomainCompositionPort(Protocol):
    def compose(self, resolution: DomainResolutionResult) -> DomainComposition: ...
```

The adapter obtains definitions externally and reuses Phase 10.8. The engine never accesses the registry directly.

### CrossDomainCognitivePort

```python
class CrossDomainCognitivePort(Protocol):
    def reason(
        self,
        *,
        domain_id: DomainId,
        objective: str,
        context: CrossDomainContextSnapshot,
    ) -> CrossDomainDomainResult: ...
```

### CrossDomainPlannerPort

```python
class CrossDomainPlannerPort(Protocol):
    def plan(
        self,
        *,
        composition: DomainComposition,
        context: CrossDomainContextSnapshot,
    ) -> CrossDomainPlanResult: ...
```

### CrossDomainAgentPort

```python
class CrossDomainAgentPort(Protocol):
    def coordinate(
        self,
        *,
        domain_id: DomainId,
        plan: CrossDomainPlanResult,
        context: CrossDomainContextSnapshot,
    ) -> CrossDomainDomainResult: ...
```

### CrossDomainWorkflowPort

```python
class CrossDomainWorkflowPort(Protocol):
    def coordinate(
        self,
        *,
        workflow_ids: tuple[str, ...],
        context: CrossDomainContextSnapshot,
    ) -> CrossDomainWorkflowResult: ...
```

### CrossDomainKnowledgePort

```python
class CrossDomainKnowledgePort(Protocol):
    def retrieve(
        self,
        *,
        domains: tuple[DomainId, ...],
        entities: tuple[str, ...],
        timelines: tuple[str, ...],
        context: CrossDomainContextSnapshot,
    ) -> CrossDomainKnowledgeResult: ...
```

Ports return explicit statuses such as `SKIPPED`, `UNAVAILABLE`, `PARTIAL`, `BLOCKED` or `FAILED`. Unexpected exceptions propagate unless a specific adapter contract defines a safe error result.

## Engine Contract

```python
class CrossDomainEngine(Protocol):
    def execute(self, request: CrossDomainRequest) -> CrossDomainResult: ...
```

```python
class DefaultCrossDomainEngine:
    def __init__(
        self,
        *,
        resolver: DomainResolutionPort,
        composer: DomainCompositionPort,
        cognitive: CrossDomainCognitivePort | None = None,
        planner: CrossDomainPlannerPort | None = None,
        agent: CrossDomainAgentPort | None = None,
        workflow: CrossDomainWorkflowPort | None = None,
        knowledge: CrossDomainKnowledgePort | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        trace_id_factory: Callable[[], str] | None = None,
        policy: CrossDomainPolicy | None = None,
    ) -> None: ...
```

Optional ports are skipped explicitly and recorded. Required behavior is determined by policy and plan.

## CrossDomainPolicy

Fields:

```text
required_ports
stop_on_blocking_contradiction
stop_on_blocking_gap
continue_independent_domains
require_review_for_high_severity
allow_declarative_parallel_groups
question_deduplication_enabled
maximum_parallel_group_size
confidence_penalties
metadata
```

Effective limits are the most restrictive values between request and policy.

## Execution Flow

`DefaultCrossDomainEngine.execute()`:

1. Validate request and factories.
2. Generate result and trace IDs.
3. Capture timezone-aware start time.
4. Enforce initial request limits.
5. Resolve domains.
6. Reject ambiguous, unsupported, blocked or failed resolution.
7. Compose domains.
8. Propagate blocked composition.
9. Create initial context snapshot.
10. Retrieve shared knowledge when configured.
11. Ask Planner for a coordination plan when configured.
12. Derive deterministic domain order: primary, supporting order, dependencies, plan grouping.
13. For each executable domain:
    - enforce limits;
    - build transferred context;
    - invoke cognitive or agent port according to plan/policy;
    - retain partial results;
    - merge findings, entities and timelines;
    - register dependencies, contradictions and gaps;
    - deduplicate questions structurally;
    - propagate blockers to dependents only.
14. Coordinate workflow requests through the workflow port.
15. Coordinate operation requests through the agent/runtime port.
16. Re-evaluate limits and review conditions.
17. Consolidate recommendations and open questions.
18. Calculate confidence.
19. Derive final status.
20. Capture completion time.
21. Return immutable `CrossDomainResult`.

## Context Transfer

A transferable item contains:

```text
source_domain
target_domain
kind
identifier
value
reason
iteration
provenance
metadata
```

Transfer is allowed only when:

- target domain is active;
- explicit plan or dependency establishes relevance;
- permissions allow transfer;
- provenance exists;
- hop and iteration limits allow it;
- the item is not private or non-transferable.

No fuzzy or semantic relevance inference is allowed.

## Question Coordination

Question identity is structural:

```text
subject
requested_information
target_entity
time_scope
```

Exact structural duplicates collapse while preserving all requesting domains. Embeddings, fuzzy matching and keyword similarity are excluded.

## Blocking Propagation

- composition blockers are global;
- dependency blockers affect dependent domains only;
- independent domains continue when policy allows;
- partial results are retained before propagation;
- high-severity contradictions may trigger review;
- missing optional ports produce partial results only when needed work depends on them;
- missing required ports produce `BLOCKED` or `FAILED` according to explicit policy.

## Operations and Workflows

The engine coordinates but does not execute them internally.

Requests must come explicitly from composition, planner or domain results. The engine deduplicates exact requests, preserves requesting domains, enforces limits, invokes the corresponding port and records decisions/results.

## Limits

Supported limits:

- domains;
- domain hops;
- iterations;
- questions;
- operations;
- external calls;
- cost;
- duration;
- declarative parallel-group size.

Checks occur before resolution, after composition, before each port call, after merges, before operation/workflow coordination and before final aggregation.

Reaching a limit never becomes `FAILED`.

## Confidence

1. collect confidence values from domain results contributing to recommendations;
2. use the minimum as base;
3. apply deterministic penalties for unresolved contradictions, unresolved gaps, skipped required domains, unavailable mandatory ports and reached limits;
4. apply no bonuses;
5. clamp to `[0, 1]`;
6. return `None` when no supporting confidence exists.

Penalty values come from policy.

## Errors

Create:

```text
CrossDomainError
CrossDomainContractError
CrossDomainSerializationError
CrossDomainConfigurationError
CrossDomainLimitError
CrossDomainPortError
CrossDomainExecutionError
```

Requirements:

- stable codes and safe messages;
- no broad `except Exception`;
- unexpected adapter errors propagate;
- functional blockers remain result states, not exceptions.

## Determinism

- domains: primary, then composition supporting order;
- domain results: execution order;
- findings and recommendations: first appearance with exact-reference deduplication;
- questions: structural identity and first appearance;
- dependencies: source, target, kind, description;
- contradictions: blocking first, severity, domains, subject, ID;
- gaps: blocking first, domain, code, description;
- decisions: blocking first, iteration, stage, domain, code, action;
- limits: fixed policy order.

No externally visible output may depend on set iteration.

## Files

Create:

```text
cmm/domains/cross_domain_contracts.py
cmm/domains/cross_domain_ports.py
cmm/domains/cross_domain_context.py
cmm/domains/cross_domain_limits.py
cmm/domains/cross_domain_aggregation.py
cmm/domains/cross_domain_engine.py
```

Modify:

```text
cmm/domains/enums.py
cmm/domains/errors.py
cmm/domains/__init__.py
```

Tests:

```text
tests/domains/test_cross_domain_contracts.py
tests/domains/test_cross_domain_serialization.py
tests/domains/test_cross_domain_context.py
tests/domains/test_cross_domain_limits.py
tests/domains/test_cross_domain_aggregation.py
tests/domains/test_cross_domain_engine.py
tests/domains/test_cross_domain_ports.py
tests/domains/test_cross_domain_public_api.py
tests/domains/test_cross_domain_boundaries.py
```

## Deliberate Exclusions

- persistence and restart recovery;
- distributed execution and real concurrency;
- queues, retries and circuit breakers;
- metrics and events;
- HTTP integration;
- model selection and provider billing;
- human review UI;
- Domain Resources from Phase 10.10.

## Testing Requirements

Cover strict validation, strict serialization, deep immutability, resolution/composition propagation, deterministic ordering, optional/required ports, context transfer permissions, entity/timeline reuse, question deduplication, partial result retention, dependency blocking, contradictions, human review, operation/workflow coordination, all limits, confidence, factory validation, forbidden imports/access, public API and complete regressions.

## Success Criteria

Phase 10.9 is complete only when:

- real adapters can be coordinated through ports;
- subsystem logic is not duplicated;
- blockers propagate correctly;
- independent work may continue;
- partial results are preserved;
- limits are deterministic;
- questions are structurally deduplicated;
- permissions constrain transfer;
- operations/workflows are coordinated only through ports;
- outputs are immutable, serializable and auditable;
- no broad exception handling exists;
- focused, domains, validation and global suites pass;
- Ruff, compileall and diff checks pass.
