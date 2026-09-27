# Phase 11 — Stable Integrated Platform

## Objective

Integrate all capabilities developed in previous phases into a usable, stable, observable, secure, and extensible personal platform.

Phase 11 will not add a new cognitive engine or replace existing components. Its purpose is to turn the kernel, semantic engines, validation, memory, the Cognitive Layer, the autonomous agent, and domain intelligence into one coherent product.

CMM OS must stop behaving like a collection of technical modules and begin operating as a personal operating system capable of:

- receiving requests through different interfaces;
- retrieving the appropriate context;
- selecting the domain and reasoning profile;
- maintaining persistent goals and workflows;
- reasoning over dispersed information;
- detecting gaps and uncertainty;
- asking questions;
- planning actions;
- executing operations;
- validating results;
- requesting approval when appropriate;
- preserving memory and knowledge;
- showing what it knows, what it has inferred, and what remains uncertain;
- recovering state after errors or restarts;
- integrating with external services;
- operating locally and, when configured, through remote services.

The phase must prioritize vertical integration and real-world usability. Every intermediate release must end with a functional end-to-end system.

---

## Integration Principle

Phase 11 must not rebuild or duplicate existing capabilities.

Each component must preserve a clear responsibility:

```text
Kernel
↓
Contracts and execution lifecycle

Semantic Engine
↓
Structural understanding and transformation

Planner
↓
Plans, dependencies, and workflows

Execution Engine
↓
Execution, transactions, and rollback

Validation System
↓
Verification and acceptance

Memory and Knowledge Graph
↓
Persistence and knowledge representation

Cognitive Layer
↓
Structured reasoning

Agent Runtime
↓
Goal pursuit and controlled autonomy

Domain Intelligence
↓
Contextual specialization

Orchestration Layer
↓
Coordination of all components

User Interfaces
↓
Interaction, supervision, and control
```

---

## Final Architecture

```text
User Interfaces
↓
Application Gateway
↓
Orchestration Layer
↓
Intent and Context Resolution
↓
Domain Selection
↓
Cognitive Layer
↓
Agent Runtime / Workflow Planner
↓
Operations and Semantic Engine
↓
Validation and Approval Gates
↓
Memory and Knowledge Update
↓
Event Bus and Observability
↓
Kernel
↓
Storage, Models and External Services
```

---

## Complete Operational Flow

```text
User Request
↓
Authenticate and Authorize
↓
Create or Resume Session
↓
Resolve Intent
↓
Load Relevant Context
↓
Select Domain
↓
Select Reasoning Profile
↓
Evaluate Information Gaps
↓
Ask / Search / Infer / Continue
↓
Generate Response or Workflow
↓
Create Execution Plan
↓
Check Permissions
↓
Request Approval if Required
↓
Execute Operations
↓
Validate Results
↓
Evaluate Outcome
↓
Update Knowledge and Memory
↓
Emit Events and Metrics
↓
Return Structured Result
↓
Resolve Communication Profile
↓
Render and Validate Response
↓
Persist Session State
```

This flow must work both for a simple query and for a workflow lasting days, weeks, or months.

---

# 11.1 — Integration Core

## Objective

Build the integration core that composes all components through stable contracts without direct coupling.

## Main Components

### Application Container

Responsible for initializing and connecting:

- kernel;
- event buses;
- repositories;
- engines;
- services;
- agents;
- domains;
- validators;
- external adapters;
- configuration;
- observability.

Conceptual example:

```python
ApplicationContainer(
    kernel=kernel,
    planner=planner,
    executor=executor,
    validator=validator,
    memory=memory,
    knowledge_graph=knowledge_graph,
    cognitive_layer=cognitive_layer,
    agent_runtime=agent_runtime,
    domain_registry=domain_registry,
    orchestrator=orchestrator,
)
```

### Service Registry

Explicit registry of available services.

It must support:

- service registration;
- dependency resolution;
- implementation replacement;
- test adapters;
- plugin loading;
- missing-dependency detection;
- incompatible-registration prevention.

### Public Contracts

Stable contracts between components.

Minimum contracts:

- `Command`;
- `Query`;
- `Event`;
- `Operation`;
- `Workflow`;
- `Goal`;
- `Session`;
- `ApprovalRequest`;
- `ValidationResult`;
- `ReasoningResult`;
- `KnowledgeItem`;
- `MemoryRecord`;
- `DomainDefinition`;
- `AgentResult`;
- `ErrorResult`.

### Versioning

All public contracts must include a version.

Example:

```python
ContractMetadata(
    contract_name="WorkflowResult",
    version="1.0",
    schema_version="2026-01",
)
```

## Expected Capabilities

- initialize the complete system;
- detect invalid configuration;
- replace implementations without modifying consumers;
- run tests with simulated components;
- load components modularly;
- inspect active services;
- verify contract compatibility;
- prevent circular dependencies;
- support local and remote execution.

## Completion Criteria

- functional Application Container;
- service registry;
- versioned public contracts;
- dependency injection;
- validated configuration;
- composition tests;
- incompatibility detection;
- integration documentation.

### 11.1 implementation status

**Status:** `CLOSED_AFTER_INDEPENDENT_REAUDIT_V1_PASS`

Implemented by the `cmm/platform/` integration-core package:

- requirement `F11-015 — Canonical Integration Core`;
- Design Point `DP-101 — Canonical Application Composition Root`;
- acceptance test `AT-DP-101` — `tests/platform/test_phase11_1_dp101_acceptance.py`;
- reference documentation — [`docs/reference/phase-11-integration-core.md`](../reference/phase-11-integration-core.md).

Independent Audit V1 returned `FAIL` (`BLOCKERS=0`; `MAJORS=3`; `MINORS=0`;
`DP-101=NOT_VERIFIED`; `CLOSURE_ELIGIBLE=NO`) and remains immutable historical
evidence at
[`docs/audits/phase-11.1-integration-core-independent-audit-v1.md`](../audits/phase-11.1-integration-core-independent-audit-v1.md).
Remediation V1 fixed exactly those three MAJOR findings inside the Phase 11.1
boundary, and final Independent Re-audit V1 returned `PASS` (`BLOCKERS=0`;
`MAJORS=0`; `MINORS=0`; `MAJOR_01=VERIFIED_REMEDIATED`;
`MAJOR_02=VERIFIED_REMEDIATED`; `MAJOR_03=VERIFIED_REMEDIATED`;
`F11-015=VERIFIED_EXISTING`; `DP-101=VERIFIED_EXISTING`; `AT-DP-101=PASS`;
`AT-DP-134=PASS`; `CLOSURE_ELIGIBLE=YES`). Final report:
[`docs/audits/phase-11.1-integration-core-independent-reaudit-v1.md`](../audits/phase-11.1-integration-core-independent-reaudit-v1.md);
audited HEAD `80dd0e70ebb1c5619fb5e0b3c69cbbe382fb0bf4`; audited tree `63a69f2f25922695f1e3d1f4b006ae1172b34949`; bundle SHA-256
`aacb9c8452710d37f28473ee1d8b9e8010e1f2d8337a3279adc845913da609bb`; report commit `54603acf83f06819409601dcd62aae19120c9baf`. The dedicated docs-only closure
therefore records `PHASE11_1=CLOSED`.

Remediation V1 changed only the Phase 11.1 public boundary:

- `MAJOR-01` — every canonical binding declares and enforces its canonical
  runtime boundary while explicit replacement/test adapters remain supported;
- `MAJOR-02` — descriptor metadata is secret-free, recursively immutable and
  still excluded from public inspection snapshots;
- `MAJOR-03` — descriptor/inspection service modes are strict `ServiceMode`
  values, so malformed modes fail before readiness and READY snapshots serialize;
- `AT-DP-101` permanently retains all three Audit V1 reproducers;
- `AT-DP-134` remains green and unchanged.

The integration core composes **already-existing** canonical subsystem instances
through explicit version-aware service bindings. It holds references and owns no
subsystem state. `IntegrationServiceRegistry` registers platform composition
bindings only — not providers, agents, domains, workflows, operations, tools,
validators, rules or models.

Explicitly **not** implemented by 11.1 and reserved to later subphases: the
Phase 11.2 Orchestrator, `IntentResolver`, `ContextResolver`, `DomainRouter`,
`AgentRouter`, `OrchestrationRequest`, `OrchestrationResult`, API/backend
endpoints, conversational flow, plugin lifecycle, Model Gateway, routing policy,
remote transport, authentication/authorization, secrets management, storage
migrations and a new Event System.

Phase 11.1 neither reopens nor modifies the closed Phase 11.34 Provider
Registry (`F11-014` / `DP-134`). The platform binds the canonical registry
object itself, by reference, and creates no second provider registry. The
remediation added an enforceable runtime boundary to that binding; the bound
object is still the exact canonical instance and Phase 11.34 production
semantics are unchanged.

The independent re-audit has now returned the reserved closure state:
`BLOCKERS=0`, `MAJORS=0`, `MINORS=0`, `DP-101=VERIFIED_EXISTING`,
`AT-DP-101=PASS`, `AT-DP-134=PASS`, `F11-015=VERIFIED_EXISTING` and
`CLOSURE_ELIGIBLE=YES`. Phase 11.1 is closed by the dedicated docs-only closure
commit; no production or test code is part of the closure.

---

# 11.2 — Orchestration Layer

## Objective

Build the layer that determines which components must participate, in what order, and under which policies.

## Orchestrator

Central coordination point:

```python
OrchestrationRequest(
    user_id="user-123",
    session_id="session-456",
    bot_id=None,
    input={...},
    channel="conversation",
    context={...},
    requested_capabilities=[...],
)
```

Result:

```python
OrchestrationResult(
    status="completed",
    response={...},
    domain="health",
    profile="HealthProfile",
    workflow_id=None,
    operations=[],
    approvals=[],
    reasoning_trace={...},
    memory_updates=[...],
)
```

## Responsibilities

- classify intent;
- decide whether the request is a query, operation, goal, or workflow;
- load the required context;
- select the domain;
- select the cognitive profile;
- decide whether an agent must participate;
- resolve requested PlatformCapabilities against user, session, Domain, resource, privacy, sensitivity, availability, autonomy, budget, and approval constraints;
- distinguish requested capabilities from effective authority;
- determine which compatible tools and canonical operations may satisfy the resulting effective capability set;
- prevent Bot configuration, Agent binding, fallback, or model/provider output from widening authority;
- determine which tools and operations are allowed;
- check permissions;
- create or resume sessions;
- control approvals;
- manage errors;
- persist results;
- emit events.

## Intent Resolver

Initial request classification.

Minimum types:

- `question`;
- `reflection`;
- `command`;
- `goal`;
- `workflow_request`;
- `information_update`;
- `approval_response`;
- `continuation`;
- `cancellation`;
- `configuration_change`.

## Context Resolver

Determine which information must be loaded.

Possible sources:

- current session;
- episodic memory;
- semantic memory;
- Knowledge Graph;
- active goals;
- open workflows;
- selected domain;
- recent events;
- preferences;
- constraints;
- user configuration.

## Domain Router

Select:

- primary domain;
- supporting domains;
- handoff requirements;
- specific permissions;
- allowed resources.

## Agent Router

Choose between:

- direct response;
- operation execution;
- deterministic workflow;
- autonomous agent;
- human escalation.

## Orchestration Policy

Configure decisions according to:

- channel;
- user;
- domain;
- sensitivity;
- autonomy level;
- cost;
- risk;
- action type;
- session state.

## Expected Capabilities

- coordinate simple queries;
- coordinate complex workflows;
- avoid unnecessary model calls;
- reuse existing results;
- detect related sessions;
- maintain cross-domain coherence;
- stop unauthorized operations;
- resume processes;
- record every operational decision.

## Completion Criteria

- functional Orchestrator;
- intent resolution;
- context resolution;
- domain selection;
- agent selection;
- configurable policies;
- decision persistence;
- multichannel tests;
- end-to-end orchestration tests.

### 11.2 implementation status

**Status:** `CLOSED_AFTER_INDEPENDENT_REAUDIT_V2_PASS`

Implemented by the `cmm/orchestration/` orchestration-layer package:

- requirement `F11-016 — Canonical Request Orchestration`;
- Design Point `DP-102 — Fail-Closed Canonical Request Orchestration Pipeline`;
- acceptance test `AT-DP-102` — `tests/orchestration/test_phase11_2_dp102_acceptance.py`
  (12 connected scenarios A–L over real canonical components, plus the two
  Remediation V1 scenarios M–N);
- architecture gates — `tests/orchestration/test_architecture.py`;
- reference documentation — [`docs/reference/phase-11-orchestration-layer.md`](../reference/phase-11-orchestration-layer.md);
- remediation design — `docs/superpowers/specs/2026-09-16-phase-11.2-remediation-v1-design.md`;
- remediation plan — `docs/superpowers/plans/2026-09-16-phase-11.2-remediation-v1-implementation-plan.md`.
- Independent Re-audit V1 — `docs/audits/phase-11.2-orchestration-layer-independent-reaudit-v1.md` (`FAIL`, `MINORS=1`);
- final Independent Re-audit V2 — `docs/audits/phase-11.2-orchestration-layer-independent-reaudit-v2.md` (`PASS`, `BLOCKERS=0`, `MAJORS=0`, `MINORS=0`, `CLOSURE_ELIGIBLE=YES`).

The layer coordinates existing canonical owners and duplicates none of them:
intent resolution is Phase 11.2-owned and deterministic; context resolution is a
read-only two-stage projection over the canonical `cmm.runtime.sessions`
session authority and explicit read-only seams; domain selection delegates to
`cmm.domains.resolver.DefaultDomainResolver` and canonical Domain permission
resources; execution-path selection delegates agent selection to
`cmm.agent_runtime.agent_registry_service.AgentRegistryService` /
`cmm.agent_runtime.agent_resolver.AgentResolver`; the restrictive policy only
preserves or narrows canonical authority. Decision persistence and safe event
emission are the only Phase 11.2-owned side effects.

Phase 11.2 does **not** execute the downstream vertical (no operation, workflow,
agent run, memory/knowledge write or provider/model call) and does **not**
implement the Phase 11.3 Application Backend: no HTTP API, FastAPI/Flask,
OpenAPI, REST resources, streaming, pagination, API idempotency/concurrency,
application-service facade or conversation service is introduced. **Phase 11.3
remains the Application Backend.**

`AT-DP-101` and `AT-DP-134` remain green and unchanged. Phase 11.1 and Phase
11.34 stay closed; no closed-phase production semantics were modified. The only
Phase 11.1 test adjustment is the documented dependency-direction exemption for
the new `cmm.orchestration` package, with a stronger gate confirming that
`cmm.orchestration` is the one sanctioned `cmm.platform` consumer.

#### 11.2 Audit V1 and Remediation V1

Independent Audit V1 recorded `INDEPENDENT_AUDIT_V1=FAIL` (`BLOCKERS=0`,
`MAJORS=2`, `MINORS=0`) against `AUDITED_HEAD=5ebc8d064fa3f29825c179eff7f41df204dc837b`
with report `docs/audits/phase-11.2-orchestration-layer-independent-audit-v1.md`:

```text
MAJOR_01=UNSAFE_ORCHESTRATION_ROLE_RUNTIME_CONTRACTS
MAJOR_02=CANONICAL_AGENT_AUTHORITY_NOT_ENFORCED
```

Remediation V1 corrects exactly those two MAJOR findings and adds no capability,
subsystem or infrastructure:

- the ambiguous `route` role method was replaced by explicit
  `DomainRouter.route_domain(...)` / `AgentRouter.route_agent(...)` with no
  compatibility alias, so the two runtime role contracts are now discriminating
  and a cross-wired graph is rejected before `ApplicationContainer.READY`;
- `Orchestrator.__init__` validates all seven injected collaborators against their
  frozen roles at construction time;
- `CanonicalAgentRouter` accepts only a canonical
  `cmm.agent_runtime.agent_registry_service.AgentRegistryService` (or `None`), so
  a fake registry service can no longer fabricate an agent selection;
- the analogous canonical collaborators of `CanonicalDomainRouter` and
  `DefaultContextResolver` were reviewed and their canonical boundaries tightened
  (full classification table in
  [`docs/reference/phase-11-orchestration-layer.md`](../reference/phase-11-orchestration-layer.md)
  §17).

The eight orchestration composition service IDs, contract versions and authority
labels are unchanged; Phase 11.1 `runtime_contract` usage is preserved.

Before independent re-audit the recorded state is:

```text
PHASE11_2=IMPLEMENTED_REMEDIATION_V1_PENDING_REAUDIT

MAJOR_01=REMEDIATED_PENDING_REAUDIT
MAJOR_02=REMEDIATED_PENDING_REAUDIT

F11_016=IMPLEMENTED_REMEDIATION_V1_PENDING_REAUDIT
DP_102=IMPLEMENTED_REMEDIATION_V1_PENDING_REAUDIT
AT_DP_102=PASS

PHASE11_1=CLOSED
DP_101=VERIFIED_EXISTING
AT_DP_101=PASS

PHASE11_34=CLOSED
DP_134=VERIFIED_EXISTING
AT_DP_134=PASS

CLOSURE_ELIGIBLE=NO
```

The block above is preserved as the pre-re-audit implementation state.
Independent Audit V1 remains immutable `FAIL` evidence with `MAJORS=2`.
Independent Re-audit V1 is preserved as `FAIL` with `MINORS=1`. Final
Independent Re-audit V2 is `PASS` and independently records:

```text
PHASE11_2=CLOSED
INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V2=PASS

BLOCKERS=0
MAJORS=0
MINORS=0

MAJOR_01=VERIFIED_REMEDIATED
MAJOR_02=VERIFIED_REMEDIATED
MINOR_01=VERIFIED_REMEDIATED

F11_016=VERIFIED_EXISTING
DP_102=VERIFIED_EXISTING
AT_DP_102=PASS
AT_DP_101=PASS
AT_DP_134=PASS

CLOSURE_ELIGIBLE=YES
```

Audited HEAD: `68ff78c614d8f7a9dc3295eb22ecea62a425cce5`. Audited tree: `d586c439fc9b3c87d139eecab8d084d820007bce`.
Re-audit V2 bundle SHA-256: `72d1b5b36104734308e322b2edd038875755d145db5d9ad8f77e2d45c7a7e62e`. Final report:
`docs/audits/phase-11.2-orchestration-layer-independent-reaudit-v2.md`.
Audit-report commit: `773204c7df06fced504892ed33284f39eca5b63a`.

Phase 11.2 is therefore closed by a dedicated docs-only closure commit. Phase
11.3 — Application Backend followed that closure, was independently audited
(`INDEPENDENT_AUDIT_V1=FAIL`, `BLOCKERS=0`, `MAJORS=1`, `MINORS=1`), remediated
under Remediation V1, and independently re-audited with final
`INDEPENDENT_REAUDIT_V1=PASS`, `BLOCKERS=0`, `MAJORS=0`, `MINORS=0`,
`DP_103=VERIFIED_EXISTING`, `AT_DP_103=PASS` and `CLOSURE_ELIGIBLE=YES`.
Phase 11.3 is closed by the dedicated docs-only closure commit; see *11.3
implementation status* below.

---

# 11.3 — Application Backend

## Objective

Build the product backend that exposes CMM OS capabilities to interfaces, integrations, and external clients.

## API

The API must expose stable resources for:

- conversations;
- sessions;
- goals;
- workflows;
- operations;
- approvals;
- memory;
- knowledge;
- domains;
- agents;
- bots;
- capabilities;
- tools;
- configuration;
- events;
- metrics;
- backups;
- plugins.

Conceptual endpoints:

```text
POST   /sessions
GET    /sessions/{id}
POST   /sessions/{id}/messages

POST   /goals
GET    /goals
PATCH  /goals/{id}

POST   /workflows
GET    /workflows/{id}
POST   /workflows/{id}/pause
POST   /workflows/{id}/resume
POST   /workflows/{id}/cancel

GET    /approvals
POST   /approvals/{id}/approve
POST   /approvals/{id}/reject

GET    /knowledge
GET    /knowledge/{id}
POST   /knowledge/{id}/invalidate

GET    /memory
POST   /memory/search

GET    /domains
GET    /agents
GET    /bots
POST   /bots
GET    /bots/{id}
PATCH  /bots/{id}
POST   /bots/{id}/duplicate
POST   /bots/{id}/archive

GET    /capabilities
GET    /capabilities/{id}

GET    /tools
GET    /tools/{id}

GET    /system/health
```

## Application Services

Application services connecting the API to the internal domain.

Examples:

- `ConversationService`;
- `GoalService`;
- `WorkflowService`;
- `ApprovalService`;
- `KnowledgeService`;
- `MemoryService`;
- `ConfigurationService`;
- `BackupService`;
- `PluginService`.

## Command and Query Separation

Separate:

```text
Queries
↓
Read without side effects

Commands
↓
Controlled modification
```

Example:

```python
CreateGoalCommand(...)
GetActiveGoalsQuery(...)
```

## Idempotency

Operations that may be repeated must accept idempotency keys.

## Error Contract

All errors must follow a shared format:

```python
ErrorResult(
    code="APPROVAL_REQUIRED",
    message="The operation requires approval",
    category="authorization",
    retryable=False,
    details={...},
    trace_id="trace-123",
)
```

## Expected Capabilities

- synchronous API;
- persistent asynchronous operations;
- response streaming;
- cancellation;
- safe retries;
- concurrency control;
- pagination;
- filters;
- traceability;
- documented contracts.

## Bot and Capability Application Services

Phase 11 adds conceptual `BotService`, `CapabilityService`, and `ToolCatalogService` application seams. They expose product configuration, effective capability resolution, and implementation availability without owning Agent execution, canonical operations, approvals, autonomy, budgets, validation, or secrets.

`/tools` is an implementation and availability inspection surface; it is not a second executable operation endpoint.

## Completion Criteria

- stable API;
- application services;
- error contracts;
- idempotency;
- streaming;
- OpenAPI documentation;
- contract tests;
- concurrency tests;
- API versioning.

### 11.3 implementation status

**Status:** `CLOSED_AFTER_INDEPENDENT_REAUDIT_V1_PASS`

Implemented by the `cmm/application/` transport-neutral application core and the
`cmm/api/` HTTP/OpenAPI/SSE adapter:

- requirement `F11-017 — Canonical Application Backend`;
- Design Point `DP-103 — Versioned, Fail-Closed Application Gateway`;
- acceptance test `AT-DP-103` — `tests/application/test_phase11_3_dp103_acceptance.py`
  (46 connected tests over real canonical components, covering scenarios A–M plus
  the two concurrent idempotency scenarios added by Remediation V1; scenario N is
  represented by the separate inherited gate commands, not by invoking other test
  modules);
- architecture gates — `tests/application/test_architecture.py` (58 tests),
  `tests/api/test_architecture.py` (51 tests);
- OpenAPI gate — `tests/api/test_openapi.py` (22 tests);
- reference documentation — [`docs/reference/phase-11-application-backend.md`](../reference/phase-11-application-backend.md);
- requirements matrix row — `F11-017` → `DP-103` → `AT-DP-103` in
  [`docs/reference/phase-11-stable-integrated-platform-requirements-matrix.md`](../reference/phase-11-stable-integrated-platform-requirements-matrix.md);
- design specification — `docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md`;
- implementation plan — `docs/superpowers/plans/2026-09-16-phase-11.3-application-backend-implementation-plan.md`;
- Remediation V1 design — `docs/superpowers/specs/2026-09-16-phase-11.3-remediation-v1-design.md` (commit `0eb802b`);
- Remediation V1 plan — `docs/superpowers/plans/2026-09-16-phase-11.3-remediation-v1-implementation-plan.md` (commit `a185134`).

The subphase introduces exactly two packages and one new public surface:

- `cmm/application/` — public application semantics: versioned public contracts,
  the safe public error model, the session/request/capability/health application
  services, the bounded in-memory idempotency seam and the one canonical
  `ApplicationGateway`;
- `cmm/api/` — transport adaptation only: the seven frozen `/v1` routes, HTTP
  status mapping, OpenAPI metadata and SSE framing;
- the frozen `/v1` surface — `GET /v1/health`, `GET /v1/capabilities`,
  `POST /v1/sessions`, `GET /v1/sessions/{session_id}`,
  `POST /v1/sessions/{session_id}/messages`,
  `POST /v1/sessions/{session_id}/messages/stream` (SSE) and
  `POST /v1/requests/{request_id}/cancel`.

Phase 11.3 is a projection and adaptation layer and duplicates no canonical
owner. User-request processing reaches the real Phase 11.2 `Orchestrator` exactly
once per public message; domain and agent authority stay canonical and are never
reselected in the application layer; session state, revision and concurrency stay
with the canonical session store; provider identity, model routing and the Model
Gateway are not reached; and there is no new Event Bus, workflow/operation/
execution/validation engine, memory/knowledge store, auth/RBAC layer, plugin
lifecycle, durable application storage, scheduler, queue or background worker
system. HTTP is an adapter, never an owner: it reaches the platform only through
`cmm.application`, and both architecture gates enforce that direction.

Phase 11.3 deliberately does **not** implement the deferred surfaces: no domain
or agent listing routes and no goals/workflows/operations/approvals/memory/
knowledge/bots/tools/configuration/events/metrics/backups/plugins routes; request
cancellation is exposed as a stable public surface that rejects explicitly
(`CAPABILITY_UNAVAILABLE`, `503`, with the `request-cancellation` capability
declaring the reason `NO_CANCELLABLE_OWNER`) instead of fabricating a
cancellation runtime; durable idempotency persistence is deferred to Phase 11.15
storage work; and no authentication/authorization, Model Gateway/Routing Policy
Engine, plugin lifecycle, pagination or WebSocket surface is introduced.

Pre-audit evidence observed on the committed intermediate implementation milestone
`2201d0009b47db7128bab895f4ad25f069712781` while preparing the Phase 11.3
documentation (Python 3.14, `.venv`, `python -m pytest -q`). It is preserved as
the historical observation the Audit V1 candidate evolved from:

```text
tests/application                 625 passed
tests/api                         193 passed
AT-DP-103                          44 passed
```

Independent Audit V1 of the Phase 11.3 candidate then returned `FAIL`
(`BLOCKERS=0`, `MAJORS=1`, `MINORS=1`):

- `MAJOR_01=NON_ATOMIC_IDEMPOTENCY_UNDER_CONCURRENT_REQUESTS` — the keyed
  `get -> execute -> put` sequence was not atomic, so two concurrent equivalent
  same-key commands both entered the canonical owner (the audit reproduced two
  `orchestration.request_received` events and two canonical decision records);
- `MINOR_01=STALE_UNQUALIFIED_IMPLEMENTATION_HEAD_IN_ROOT_ROADMAP` — root
  `ROADMAP.md` presented the intermediate milestone above as an unqualified
  implementation HEAD.

The immutable audit report is
`docs/audits/phase-11.3-application-backend-independent-audit-v1.md`
(`AUDITED_HEAD=5fd8cc3b171faec88b802be920ad09ac53224e75`,
`AUDITED_TREE=1cfbe114369ac89d1c2563a9787c5ebf096c64df`,
`AUDIT_BUNDLE_SHA256=17377075eae659d123ca4ee909fa8f0cef01f625f40c2d498b34f22a47690199`,
report commit `c111a57`).

Remediation V1 repaired exactly those two findings and added deterministic
concurrency regressions:

- `cmm/application/gateway.py` now owns one private, in-process
  `threading.Lock` (`self._idempotency_lock`) held across the complete keyed
  critical section — fingerprint resolution, stored-record read, replay/conflict
  decision, canonical execution and record write — so one keyed semantic command
  enters the canonical owner at most once while an equivalent keyed command is in
  flight. Commands without an idempotency key and every query keep their
  lock-free path, and the public idempotency repository contract, the fingerprint
  semantics and the UUID5 retry identity are unchanged;
- three focused regression tests in `tests/application/test_gateway.py` and two
  connected concurrent scenarios in `tests/application/test_phase11_3_dp103_acceptance.py`
  force the audited interleaving deterministically with a test-only two-party
  `threading.Barrier` gate at the repository lookup and bounded worker joins, and
  assert canonical effect counts rather than response codes alone. Against the
  pre-remediation gateway all four concurrent tests fail with duplicate canonical
  execution, which is the recorded RED evidence;
- root `ROADMAP.md` now qualifies `2201d0009b47db7128bab895f4ad25f069712781` as an
  **AT-DP-103 intermediate implementation milestone**, not the exact audit
  candidate or the re-audit candidate.

Evidence observed on the committed remediation HEAD (same environment):

```text
tests/application                 630 passed
tests/api                         193 passed
tests/application (gateway + idempotency focused)
                                  135 passed
AT-DP-103                          46 passed
AT-DP-102 + AT-DP-101 + AT-DP-134 131 passed
architecture + OpenAPI gates      272 passed
```

The exact-HEAD re-audit bundle, the subsystem/global suite record, Ruff, format
check, compileall and `git diff --check` are produced by the Remediation V1
implementation-plan task and reported in its handoff, to be independently
re-verified by the re-audit.

The Phase 11.1 platform architecture gate was adjusted once, as a documented
Phase 11.1 test adjustment: it now names its sanctioned platform consumers as the
allowlist `("orchestration", "application")` instead of exempting
`cmm.orchestration` alone. No Phase 11.1, Phase 11.2 or Phase 11.34 production
semantics were modified — `git diff 3a2bc9e..HEAD -- cmm/platform
cmm/orchestration kernel/llm cmm/domains cmm/agent_runtime` produced no output —
and `AT-DP-101`, `AT-DP-102` and `AT-DP-134` remain green and unchanged.

Final independently re-audited closure state:

```text
PHASE11_3=CLOSED

INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V1=PASS

BLOCKERS=0
MAJORS=0
MINORS=0

MAJOR_01=VERIFIED_REMEDIATED
MINOR_01=VERIFIED_REMEDIATED

F11_017=VERIFIED_EXISTING
DP_103=VERIFIED_EXISTING
AT_DP_103=PASS

AT_DP_102=PASS
AT_DP_101=PASS
AT_DP_134=PASS

PHASE11_2=CLOSED
PHASE11_1=CLOSED
PHASE11_34=CLOSED

AUDITED_HEAD=4525f72391792e623730af69e95bcd054ce3cddf
AUDITED_TREE=0b650c8133111754452940c74a1bc72f24a0df23
REAUDIT_BUNDLE_SHA256=152276776b9e2765edb67adcd95b6ee3d2b565d416e1e4bce665777a078d9618
REAUDIT_V1_REPORT_COMMIT=c21f2e257a1995b748b78b65b622ff68ca3e6d38

CLOSURE_ELIGIBLE=YES
AUDIT_STATUS=CLOSED_AFTER_INDEPENDENT_REAUDIT_V1_PASS
NEXT=VERIFY_CLOSURE_COMMIT_THEN_INSPECT_PHASE11_4_CLI
```

Historical Audit V1 `FAIL` remains immutable. Independent Re-audit V1 verified
both findings as remediated and is the authority for `F11_017`,
`DP_103`, `AT_DP_103` and closure eligibility. Phase 11.4 — CLI must begin with
a fresh repository inspection only after this docs-only closure commit is
verified and the worktree is clean.

---

# 11.4 — CLI

## Objective

Provide a complete operational interface for development, administration, automation, and advanced use.

## Main Commands

```text
cmm status
cmm doctor
cmm config show
cmm config set

cmm chat
cmm ask

cmm goals list
cmm goals create
cmm goals show
cmm goals pause
cmm goals resume

cmm workflows list
cmm workflows show
cmm workflows run
cmm workflows pause
cmm workflows resume
cmm workflows cancel

cmm approvals list
cmm approvals approve
cmm approvals reject

cmm memory search
cmm knowledge inspect

cmm domains list
cmm plugins list

cmm backup create
cmm backup restore
cmm migrate
cmm logs
cmm metrics
```

## Output Modes

- human;
- JSON;
- YAML;
- quiet;
- verbose.

Example:

```bash
cmm goals list --status active --output json
```

## Doctor

The `cmm doctor` command must check:

- configuration;
- database;
- storage;
- models;
- services;
- permissions;
- migrations;
- secrets;
- network;
- plugins;
- kernel state.

## Expected Capabilities

- interactive execution;
- scripted execution;
- stable exit codes;
- autocompletion;
- cancellation;
- workflow tracking;
- CI compatibility;
- system administration.

## Completion Criteria

- complete CLI;
- structured output;
- functional doctor command;
- documentation;
- E2E tests;
- Linux and macOS compatibility;
- commands reusable from automation.

### 11.4 implementation status

**Status:** `CLOSED_AFTER_INDEPENDENT_REAUDIT_V1_PASS`

Implemented by the `cmm/` presentation modules over the existing root
`argparse` command tree, plus the sanctioned Phase 11.3 compatibility and
composition additions in `cmm/application/`:

- requirement `F11-018 — Canonical Operational CLI`;
- Design Point `DP-104 — Single-Front-Door Fail-Closed Operational CLI`;
- acceptance test `AT-DP-104` — `tests/cli/test_phase11_4_dp104_acceptance.py`
  (69 connected tests over real canonical components, covering entrypoint
  identity, inherited command preservation, `status`, `ask`, reserved
  unavailable behavior, backup unavailability, `doctor`, output safety, exit
  codes, no parallel authority, current capability truth and platform
  compatibility);
- focused suite — `tests/cli/` (459 tests across ten modules);
- architecture gate — `tests/cli/test_phase11_4_architecture.py` (52 tests)
  plus the inherited application/API/platform/orchestration architecture gates
  and the API OpenAPI gate;
- reference documentation — [`docs/reference/phase-11-cli.md`](../reference/phase-11-cli.md);
- requirements matrix rows — `F11-018` → `DP-104` → `AT-DP-104` in
  [`docs/reference/phase-11-stable-integrated-platform-requirements-matrix.md`](../reference/phase-11-stable-integrated-platform-requirements-matrix.md);
- design specification — `docs/superpowers/specs/2026-09-16-phase-11.4-cli-design.md`;
- implementation plan — `docs/superpowers/plans/2026-09-16-phase-11.4-cli-implementation-plan.md`.

The subphase introduces one public front door and seven presentation modules,
and no new authority:

- `cmm/cli.py` — the console-script wrapper, unchanged in identity
  (`cmm = "cmm.cli:main"`, exactly one occurrence in `pyproject.toml`);
- `cmm/__main__.py` — the one root parser, explicit dispatch, lazy composition
  and automation semantics;
- `cmm/cli_contracts.py` — the frozen presentation vocabulary: schema version
  `v1`, three output formats, ten stable exit codes, the availability labels,
  the bounded safe result/error envelopes and the static command descriptor;
- `cmm/cli_output.py` — deterministic human/JSON/YAML rendering with
  stdout-for-payload and stderr-for-diagnostics stream selection;
- `cmm/cli_commands.py` — the reserved namespace (16 families, 29 frozen command
  identities: 4 available, 25 unavailable), the fail-closed unavailable result
  and straight-line dispatch with no registry, router or runtime;
- `cmm/cli_application.py` — the thin CLI-to-`ApplicationGateway` adapter and
  the CLI's only startup seam, reusing the canonical local runtime composition;
- `cmm/cli_doctor.py` — the read-only diagnostic aggregator (13 declared checks,
  4 core).

Operationally available in this build: `cmm status`, `cmm doctor`, `cmm ask` and
`cmm chat`. Every other reserved roadmap command is listed in help with an
explicit unavailable label and fails closed with `CAPABILITY_UNAVAILABLE` and
exit code `5` — without starting the platform, importing a canonical owner or
fabricating an empty success. Inherited surfaces (`validation`, `domain`,
`agent`, `run`, `develop`) keep their own parsers, handlers and exit semantics:
the inherited CLI regression baseline of `368 passed` is unchanged.

Phase 11.4 is a presentation and adaptation layer and duplicates no canonical
owner. The CLI reaches the platform only through the Phase 11.3
`ApplicationGateway`; the request's new `ApplicationChannel` records transport
origin only, selects no authority and participates in the public request
serialization so a CLI command and an API command can never share one idempotency
replay record. There is no new Command Registry, Command Router, command bus,
CLI service locator, CLI runtime, CLI state store or CLI history store, and no
plugin system, backup engine, restore engine, migration engine, metrics backend,
observability backend, Goal subsystem, approval system, workflow engine, memory
engine, knowledge store, configuration authority, provider registry or model
gateway.

Pre-audit evidence observed on the committed implementation HEAD
`78bd24ca2e371f11c29ee6c82764042161acf224` while preparing the Phase 11.4
documentation (Python 3.14, `.venv`, `python -m pytest -q`):

```text
tests/cli                                     459 passed
inherited CLI regression                      368 passed
tests/application + tests/api                 857 passed
connected Phase 11 acceptances                247 passed
tests/platform + tests/orchestration          856 passed
relevant domain/agent/session regressions     622 passed
global suite                                  20433 passed (exit code 0)
```

The exact-HEAD audit bundle, the global suite record, Ruff, format check,
compileall and `git diff --check` are produced by the Phase 11.4 implementation
plan's verification task and reported in its handoff, to be independently
re-verified by the independent audit.

Remediation V1 documentary state:

```text
PHASE11_4=CLOSED
F11_018=VERIFIED_EXISTING
DP_104=VERIFIED_EXISTING
AT_DP_104=PASS

AT_DP_103=PASS
AT_DP_102=PASS
AT_DP_101=PASS
AT_DP_134=PASS

PHASE11_3=CLOSED
PHASE11_2=CLOSED
PHASE11_1=CLOSED
PHASE11_34=CLOSED

CLOSURE_ELIGIBLE=YES
AUDIT_STATUS=PENDING_INDEPENDENT_AUDIT
NEXT=INDEPENDENT_AUDIT
```

Phase 11.4 is not closed and is not closure-eligible before that audit passes.
No closed-phase production semantics were reopened: the only changes inside
`cmm/application/` are the transport-neutral `ApplicationChannel` public field,
its application-to-orchestration mapping, channel forwarding through the gateway,
the canonical local application runtime composition helper and the public
exports those require.

---

## 11.4 Final independent audit closure

Phase 11.4 — CLI is closed after Independent Re-audit V1 `PASS`.

```text
PHASE11_4=CLOSED
INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V1=PASS
BLOCKERS=0
MAJORS=0
MINORS=0
MINOR_01=VERIFIED_REMEDIATED
F11_018=VERIFIED_EXISTING
DP_104=VERIFIED_EXISTING
AT_DP_104=PASS
AT_DP_103=PASS
AT_DP_102=PASS
AT_DP_101=PASS
AT_DP_134=PASS
AUDITED_HEAD=1d6208d3ad849a0d59e5e4c85f63f36a331557d9
AUDITED_TREE=65f897686a1509e0bf889eb33c665bda51486337
REAUDIT_BUNDLE_SHA256=7086611069256b01c13a007f64584343382b39c66cef75cd2a2e601ab5ad5a26
AUDIT_V1_REPORT_COMMIT=22b240ec0ebd9fb81958905ec02414d525efba99
REAUDIT_V1_REPORT_COMMIT=0aae35764d74eb992db9c7af96f2086d0933d821
CLOSURE_ELIGIBLE=YES
AUDIT_STATUS=CLOSED_AFTER_INDEPENDENT_REAUDIT_V1_PASS
NEXT=VERIFY_CLOSURE_COMMIT_THEN_INSPECT_PHASE11_5_CONVERSATIONAL_INTERFACE
```

Historical Audit V1 `FAIL` remains preserved in
`docs/audits/phase-11.4-cli-independent-audit-v1.md`. Final independent
Re-audit V1 `PASS` is recorded in
`docs/audits/phase-11.4-cli-independent-reaudit-v1.md`.

# 11.5 — Conversational Interface

## Objective

Build the main natural-interaction interface for CMM OS.

## Capabilities

- continuous conversation;
- automatic context selection;
- references to previous sessions;
- source visualization;
- visualization of facts, inferences, and hypotheses;
- interactive questions;
- workflow execution;
- document upload;
- operation tracking;
- action approval;
- pause and resume;
- message editing;
- controlled regeneration;
- streamed responses;
- cancellation;
- attachments;
- quick commands;
- optional Bot association;
- requested/effective capability visibility;
- optional canonical Agent-backed status.

## Conversation Message

```python
ConversationMessage(
    id="message-123",
    session_id="session-456",
    bot_id=None,
    role="user",
    content=[...],
    created_at="...",
    references=[...],
    attachments=[...],
    metadata={...},
)
```

A conversation may be associated with a `bot_id`, but normal conversation must remain possible without Bot or Agent binding. The interface must distinguish requested capabilities from effective capability state and show blocked, unavailable, or approval-required states without treating them as executable authority.

## Assistant Response

```python
AssistantResponse(
    message={...},
    sources=[...],
    reasoning_summary={...},
    pending_questions=[...],
    proposed_actions=[...],
    approval_requests=[...],
    workflow_updates=[...],
)
```

## Interaction Modes

- general conversation;
- domain conversation;
- session linked to a goal;
- session linked to a workflow;
- reflection session;
- review session;
- configuration session.

## Transparency

When relevant, the interface must show:

- which context was used;
- which domain is active;
- which sources were consulted;
- which actions are proposed;
- which actions require approval;
- which information is missing;
- what will be stored in memory.

## Completion Criteria

- functional conversation;
- streaming;
- attachments;
- persistent sessions;
- dynamic questions;
- proposed actions;
- approvals;
- visible sources;
- complete Orchestrator integration;
- E2E tests.

### 11.5 implementation status

**Status:** `CLOSED_AFTER_INDEPENDENT_REAUDIT_V2_PASS`

Implemented by the new `cmm/conversation/` package over the closed Phase 11.1–11.4
platform, plus strictly additive seams in the closed packages:

- requirement `F11-019 — Canonical Conversational Interface`;
- Design Point `DP-105 — Session-Backed Canonical Conversation Boundary`;
- acceptance test `AT-DP-105 — Canonical Conversational Interaction Acceptance`
  — `tests/conversation/test_phase11_5_dp105_acceptance.py` (one connected
  acceptance over the real canonical vertical: canonical shared session ->
  official `InMemorySessionStore` -> `ConversationService` ->
  `ApplicationGateway` -> `RequestApplicationService` -> the real Phase 11.2
  `Orchestrator` -> real canonical domain routing and a genuine authorized
  Phase 10.45 `ConversationalDomainView` -> `AssistantResponse` ->
  `conversation.v1` persisted through the canonical store; scenarios A–I plus
  the in-graph domain-route positive control);
- focused suite — `tests/conversation/` (860 tests across nine modules at the
  Remediation V2 implementation state);
- architecture/security gate — `tests/conversation/test_architecture.py`
  (132 tests) plus the inherited application/API/platform architecture gates
  and the API OpenAPI and frozen-route-surface gates;
- reference documentation —
  [`docs/reference/phase-11-conversational-interface.md`](../reference/phase-11-conversational-interface.md);
- requirements matrix rows — `F11-019` -> `DP-105` -> `AT-DP-105` in
  [`docs/reference/phase-11-stable-integrated-platform-requirements-matrix.md`](../reference/phase-11-stable-integrated-platform-requirements-matrix.md);
- design specification — `docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md`;
- implementation plan — `docs/superpowers/plans/2026-09-17-phase-11.5-conversational-interface-implementation-plan.md`.

The subphase introduces one conversational boundary package and no new authority:

- `cmm/conversation/contracts.py` — the frozen public conversational contracts
  and their bounded, secret-free value grammar;
- `cmm/conversation/errors.py` — the closed safe conversational failure
  vocabulary;
- `cmm/conversation/state.py` — the versioned `conversation.v1` extension of the
  canonical shared session and its optimistic-revision commit rules (the
  canonical `SessionStore` stays the only persistence authority);
- `cmm/conversation/capabilities.py` — the requested-versus-effective capability
  representation;
- `cmm/conversation/projection.py` — the safe projection of authorized
  application and Phase 10.45 Domain projections;
- `cmm/conversation/service.py` — `ConversationService` over the canonical
  `ApplicationGateway` (actor constant `CONVERSATION_ACTOR_ID = "conversation"`;
  no idempotency key is ever set);
- `cmm/conversation/platform_module.py` — the Phase 11.1 composition binding
  `conversation.service`;
- `cmm/conversation/__init__.py` — the public re-export surface.

Additive seams in the closed packages: the
`ApplicationChannel.CONVERSATION` value and its one-to-one mapping to the
pre-existing `OrchestrationChannel.CONVERSATION`; the canonical local-runtime
`session_store` reference; and the optional `conversation` keyword with the five
additive `/v1/conversations/...` routes in the HTTP adapter. No Phase 11.1–11.4
production semantics were reopened. The closed-phase test surfaces touched are
exactly two additive architecture-gate seams (`tests/application/test_architecture.py`,
`tests/api/test_architecture.py`) and the exact-set/allowlist pins of
`tests/application/test_channels.py`, `tests/application/test_local_runtime.py`,
`tests/api/test_http_v1.py`, `tests/api/test_openapi.py`,
`tests/application/test_phase11_3_dp103_acceptance.py` and
`tests/platform/test_architecture.py` — every change additive and documented,
with no assertion weakened.

Conversational capability truth at this baseline:
`continuous_conversation` / `message_editing` / `controlled_regeneration` /
`attachments` / `bot_association` are `available`
(`session_backed_multi_turn` / `append_only_lineage` / `canonical_reexecution` /
`reference_only` / `opaque_non_authoritative`); `domain_projection` is
composition-aware (remediation V2 MAJOR_R1_01): `available` with the effective
mode `authorized_projection_when_supplied_by_canonical_integrator` while
`ConversationService` composes an authorized read-only projection source, and
`unavailable` with `effective=None` and reason
`NO_AUTHORIZED_DOMAIN_PROJECTION_SOURCE` otherwise — a request flag never
changes availability. `response_streaming` is `degraded` with the effective mode
`response_event_stream` (no provider token-streaming runtime exists);
`request_cancellation` is `unavailable` with reason `NO_CANCELLABLE_OWNER` (the
canonical cancellation answer stays `CAPABILITY_UNAVAILABLE`); `document_upload`
is `unavailable` with reason `NO_CANONICAL_STORAGE_OWNER`.

Remediation V2 implementation evidence observed in this repository (CWD
`/Users/chris/CMM OS`, `"/Users/chris/CMM OS/.venv/bin/python"`, Python 3.14):

```text
tests/conversation                                     860 passed
tests/conversation/test_phase11_5_dp105_acceptance.py    1 passed
inherited connected acceptance chain                   249 passed
```

The complete Phase 11.5 gate run and the exact-HEAD audit bundle are produced by
the implementation plan's later verification tasks and reported in their
handoff, to be independently re-verified by the independent audit.

Remediation V2 documentary state:

```text
PHASE11_5=CLOSED

F11_019=VERIFIED_EXISTING
DP_105=VERIFIED_EXISTING
AT_DP_105=PASS

INDEPENDENT_AUDIT_V1=FAIL_RECORDED
INDEPENDENT_REAUDIT_V1=FAIL_RECORDED
REMEDIATION_V2=INDEPENDENTLY_REAUDITED_PASS
CLOSURE_ELIGIBLE=YES
AUDIT_STATUS=CLOSED_AFTER_INDEPENDENT_REAUDIT_V2_PASS
NEXT=PHASE11_NEXT_SUBPHASE_REQUIRES_FRESH_INSPECTION
```

Phase 11.5 is remediated (Remediation V2 after the independent Re-audit V1
`FAIL`; `INDEPENDENT_AUDIT_V1=FAIL_RECORDED`,
`INDEPENDENT_REAUDIT_V1=FAIL_RECORDED`) and closed after Independent Re-audit V2 `PASS`; it
is closed and closure-eligible because that re-audit returned its
evidence. The next subphase must not be described as started.

Historical numbering collision, recorded explicitly: this document also carries
a historical version-plan entry whose secondary heading is
`## 11.5 — Operational Workspace` (preserved below, unrenumbered). Its canonical
identity is **not** the current subphase: the canonical Phase 11.5 is
Conversational Interface (`F11-019`, `DP-105`, `AT-DP-105`), and the historical
entry is a version-summary listing that must never be read as a second Phase 11.5
requirement. No historical artifact is renumbered or rewritten here.

---

# 11.6 — Goal Workspace

## Objective

Provide an operational view of every goal maintained by the system.

## Goal Dashboard

Display:

- active goals;
- blocked goals;
- paused goals;
- completed goals;
- priority;
- progress;
- dependencies;
- risks;
- next action;
- review date;
- pending decisions;
- associated workflows.

## Goal View

```python
GoalView(
    id="goal-123",
    title="Complete CMM OS",
    status="active",
    progress=0.72,
    priority=90,
    next_action="Complete Integration Core",
    blockers=[...],
    dependencies=[...],
    workflows=[...],
    decisions=[...],
)
```

## Capabilities

- create goals;
- decompose goals;
- establish success criteria;
- assign priority;
- relate goals;
- pause;
- resume;
- cancel;
- review;
- complete;
- reopen;
- inspect history;
- show deviations;
- compare planned and actual progress.

## Goal Review

Structured review:

```python
GoalReview(
    goal_id="goal-123",
    progress_delta=0.08,
    completed_items=[...],
    blockers=[...],
    risks=[...],
    new_information=[...],
    recommended_actions=[...],
)
```

## Completion Criteria

- functional dashboard;
- persistence;
- filters;
- goal relationships;
- periodic review;
- history;
- agent integration;
- workflow integration;
- E2E tests.

---

# 11.7 — Workflow Manager

## Objective

Allow users to visualize, control, and audit active workflows.

## Workflow View

Display:

- state;
- objective;
- tasks;
- dependencies;
- operations;
- results;
- errors;
- questions;
- approvals;
- retries;
- duration;
- cost;
- next step.

## States

```text
created
queued
running
waiting_for_user
waiting_for_resource
waiting_for_approval
paused
retrying
rolling_back
completed
failed
cancelled
```

## Capabilities

- start;
- pause;
- resume;
- cancel;
- retry;
- replan;
- inspect operations;
- view logs;
- view dependencies;
- answer questions;
- approve actions;
- compare plan versions;
- view rollback;
- clone workflows;
- create templates.

## Workflow Templates

Examples:

- `MedicalFollowUp`;
- `UniversitySemesterReview`;
- `OppositionWeeklyReview`;
- `ProjectDevelopmentIteration`;
- `RelationshipTimelineAnalysis`;
- `LifePlanReview`;
- `DocumentAnalysis`;
- `RepositoryRefactor`.

## Completion Criteria

- workflow view;
- persistent states;
- manual control;
- retries;
- visible rollback;
- templates;
- history;
- event integration;
- interruption and resume tests.

---

# 11.8 — Review Center

## Objective

Centralize every action that requires human supervision.

## Approval Request

```python
ApprovalRequest(
    id="approval-123",
    action="send_email",
    risk_level="high",
    reason="External communication",
    requested_by="agent-1",
    workflow_id="workflow-123",
    payload_preview={...},
    consequences=[...],
    reversible=False,
    expires_at=None,
)
```

## Approval Types

- sensitive operation execution;
- destructive change;
- external communication;
- publishing;
- permission modification;
- financial expenditure;
- sensitive-information access;
- critical knowledge update;
- data deletion;
- implementation of a high-impact recommendation.

## Possible Decisions

```text
approved
rejected
modified
expired
cancelled
```

## Capabilities

- review context;
- inspect payload;
- inspect consequences;
- modify the proposal;
- approve partially;
- reject;
- request more information;
- record justification;
- establish recurring approvals;
- revoke permissions;
- audit decisions.

## Approval Policies

Configure:

- actions that are always allowed;
- actions allowed by domain;
- actions requiring approval;
- prohibited actions;
- cost limits;
- sensitivity limits;
- temporary permissions;
- per-workflow permissions.

## Completion Criteria

- functional Review Center;
- policies;
- history;
- approval and rejection;
- expiration;
- modification before approval;
- auditability;
- E2E tests for sensitive actions.

---

# 11.9 — Timeline

## Objective

Build a unified temporal view of relevant events across all domains.

## Timeline Event

```python
TimelineEvent(
    id="event-123",
    domain="health",
    event_type="appointment",
    title="Pulmonology appointment",
    occurred_at="2026-09-04T10:00:00",
    source="calendar:event-123",
    confidence=1.0,
    entities=[...],
    related_goals=[...],
    related_knowledge=[...],
)
```

## Sources

- episodic memory;
- Knowledge Graph;
- calendar;
- workflows;
- decisions;
- goals;
- documents;
- operations;
- conversations;
- external events.

## Capabilities

- filter by domain;
- filter by entity;
- filter by type;
- relate events;
- detect gaps;
- detect inconsistencies;
- compare versions;
- show future events;
- show periods;
- navigate to source;
- create temporal summaries;
- add events manually;
- correct events;
- invalidate events.

## Views

- global;
- health;
- university;
- relationships;
- project;
- decisions;
- goals;
- system activity.

## Completion Criteria

- global timeline;
- filters;
- relationships;
- source navigation;
- supervised editing;
- cross-domain integration;
- temporal tests;
- timezone handling.

---

# 11.10 — Knowledge Explorer

## Objective

Allow the user to inspect and supervise knowledge stored by CMM OS.

## Main Views

### Knowledge Items

Display:

- statement;
- epistemic kind;
- confidence;
- sources;
- date;
- validity;
- domain;
- entities;
- relationships;
- versions;
- contradictions.

### Source View

Display:

- original source;
- relevant excerpt;
- date;
- authorship;
- reliability;
- performed transformations;
- derived knowledge.

### Contradiction View

Display:

- incompatible claims;
- sources;
- dates;
- confidence;
- proposed resolution;
- impact.

### Stale Knowledge View

Display:

- expired information;
- potentially outdated information;
- undated knowledge;
- unavailable sources;
- items requiring review.

## Capabilities

- search;
- filter;
- navigate relationships;
- review provenance;
- correct;
- invalidate;
- merge;
- split;
- mark as uncertain;
- add source;
- resolve contradiction;
- export;
- inspect history.

## Prohibited Behavior

The system must not allow:

- silent modification of facts;
- removal of provenance;
- conversion of inferences into facts;
- overwriting knowledge without a new version;
- hiding contradictions;
- invalidating critical information without an audit trail.

## Completion Criteria

- functional explorer;
- search;
- navigation;
- provenance;
- temporal validity;
- contradictions;
- versions;
- supervised editing;
- complete audit trail.

---

# 11.11 — Memory Workspace

## Objective

Allow users to review what CMM OS remembers and control its retention.

## Memory Types

- episodic;
- semantic;
- procedural;
- preferences;
- decisions;
- goals;
- session context;
- results;
- operational memory;
- temporal memory.

## Capabilities

- inspect memories;
- search;
- filter;
- view origin;
- view date;
- view recent use;
- correct;
- forget;
- archive;
- consolidate;
- limit retention;
- mark sensitivity;
- block use;
- export;
- import.

## Memory Policy

Configure:

- what may be stored;
- retention duration;
- what requires consent;
- what must expire;
- what may not be shared across domains;
- what an agent may use;
- what may be sent to remote models.

## Memory Update Preview

Before saving sensitive or relevant information, the system may show:

```python
MemoryUpdateProposal(
    additions=[...],
    updates=[...],
    invalidations=[...],
    sensitivity="high",
    reason="Information provided by the user",
)
```

## Completion Criteria

- memory view;
- search;
- correction;
- forgetting;
- retention policies;
- sensitivity control;
- audit trail;
- export;
- privacy tests.

---

# 11.12 — Configuration Center

## Objective

Centralize technical and functional system configuration.

## Areas

### Models

- local models;
- remote models;
- routing;
- fallback;
- limits;
- cost;
- temperature;
- context window;
- availability.

### Privacy

- local only;
- hybrid;
- remote allowed;
- excluded data;
- sensitive domains;
- anonymization;
- retention.

### Autonomy

- global level;
- level by domain;
- authorized actions;
- approvals;
- budgets;
- iteration limits;
- cost limits.

### Bots

- identity and description;
- instructions;
- Communication Profile;
- model and routing policy;
- Domains;
- knowledge and memory scope;
- requested PlatformCapabilities;
- autonomy preference within the canonical ceiling;
- optional Agent binding;
- versioning;
- import and export.

Bot configuration expresses requested product behavior. It does not grant effective permissions, approvals, autonomy, budgets, secrets, or execution authority.

### Tools / Capabilities

- Platform Capability Catalog;
- requested and effective capability state;
- implementation availability;
- connection and health state;
- local or remote execution metadata;
- privacy and sensitivity requirements;
- scopes;
- approvals;
- audit;
- replaceable implementation adapters.

### Domains

- enable;
- disable;
- configure resources;
- configure permissions;
- select profiles;
- review operations.

### Integrations

- n8n;
- email;
- calendar;
- storage;
- Git;
- external APIs;
- models;
- webhooks.

### System

- language;
- timezone;
- storage;
- logs;
- backups;
- updates;
- telemetry;
- development mode.

## Configuration Schema

All configuration must be validated and versioned.

```python
Configuration(
    version="1.0",
    runtime={...},
    models={...},
    privacy={...},
    autonomy={...},
    domains={...},
    integrations={...},
)
```

## Completion Criteria

- navigable configuration;
- validation;
- versioning;
- per-environment configuration;
- separated secrets;
- import and export;
- configuration rollback;
- invalid-configuration tests.

---

# 11.13 — Authentication and Authorization

## Objective

Protect system access and control which user, agent, domain, or integration may perform each operation.

## Identities

- user;
- service;
- agent;
- plugin;
- external integration;
- administrator.

## Permission

```python
Permission(
    subject="agent:project-agent",
    action="repository.modify",
    resource="project:cmm-os",
    effect="allow",
    constraints={...},
)
```

## Permission Model

```text
RBAC
+
Policy-Based Access Control
+
Resource-Level Permissions
```

## Bot and Capability Authorization Boundary

A Bot may request PlatformCapabilities, but Bot configuration is never itself an authorization source.

Effective capability authority must be derived through the canonical permission and policy owners. Agent binding cannot grant permissions, increase autonomy or budgets, remove approvals, transfer secrets, or activate Computer Use by implication.

For sensitive or mutating capabilities, missing authority fails closed. Explicit deny wins.

## Capabilities

- local authentication;
- sessions;
- tokens;
- revocation;
- roles;
- per-resource permissions;
- per-domain permissions;
- temporary permissions;
- conditional permissions;
- auditability;
- credential rotation;
- lockout;
- expiration.

## Least Privilege

No agent, plugin, or service may receive more permissions than strictly necessary.

## Completion Criteria

- authentication;
- authorization;
- roles;
- per-resource permissions;
- temporary permissions;
- audit trail;
- revocation;
- privilege-escalation tests;
- unauthorized-access tests.

---

# 11.14 — Security and Secrets

## Objective

Protect data, credentials, operations, and communications.

## Secret Management

- secrets outside source code;
- encrypted storage;
- per-environment variables;
- rotation;
- audited access;
- separation between development and production;
- no exposure in logs;
- no persistence in prompts.

## Encryption

- data in transit;
- data at rest;
- backups;
- credentials;
- highly sensitive information.

## Security Policies

- allowed commands;
- allowed paths;
- allowed hosts;
- network limits;
- sandboxing;
- process control;
- injection protection;
- sanitization;
- input validation;
- file controls;
- Bot definitions must never contain credentials, API keys, refresh tokens, cookies, or operating-system authorization tokens;
- authenticated-browser sessions must use independently authorized and scoped session/origin access;
- Computer Use must use explicit application/resource scope, visible execution state, cancellation, human takeover, and revalidation before automated resume;
- destructive-operation blocking.

Bot configuration, Agent binding, model output, provider payloads, fallback, and imported configuration must never be treated as permission or capability-escalation authorities.

## Threat Model

Minimum threats:

- prompt injection;
- tool injection;
- malicious plugin;
- secret leakage;
- privilege escalation;
- memory manipulation;
- false knowledge;
- arbitrary execution;
- exfiltration;
- backup corruption;
- compromised dependency;
- user impersonation.

## Completion Criteria

- secrets manager;
- encryption;
- documented threat model;
- sandbox;
- input validation;
- log protection;
- dependency scanning;
- security tests;
- permission audit.

---

# 11.15 — Storage and Persistence

## Objective

Provide reliable persistence for every system state.

## Storage Types

### Relational Storage

For:

- users;
- sessions;
- goals;
- workflows;
- operations;
- approvals;
- configuration;
- audit records.

### Graph Storage

For:

- entities;
- relationships;
- knowledge;
- provenance;
- contradictions;
- temporal information.

### Vector Storage

For:

- semantic search;
- contextual retrieval;
- documents;
- memory;
- embeddings.

### Object Storage

For:

- documents;
- attachments;
- backups;
- artifacts;
- large logs;
- results.

Phase 11 persistence must also cover versioned Bot definitions, Bot capability requests, PlatformCapability descriptors or references, and effective capability-policy decision records. Secrets remain outside those records.

## Storage Abstraction

Provider-independent contracts:

- `SessionRepository`;
- `GoalRepository`;
- `WorkflowRepository`;
- `KnowledgeRepository`;
- `MemoryRepository`;
- `EventRepository`;
- `DocumentRepository`;
- planned `BotRepository`;
- planned `CapabilityDecisionRepository`.

## Capabilities

- transactions;
- optimistic locking;
- versioning;
- retention;
- archiving;
- recovery;
- migrations;
- optional replication;
- referential integrity;
- controlled cleanup.

## Completion Criteria

- complete persistence;
- repositories;
- migrations;
- transactions;
- integrity;
- concurrency tests;
- failure recovery;
- storage documentation.

---

# 11.16 — Migrations

## Objective

Allow structures, contracts, and data to evolve without information loss.

## Types

- schema migrations;
- data migrations;
- contract migrations;
- knowledge migrations;
- configuration migrations;
- plugin migrations.

## Migration

```python
Migration(
    id="2026_07_001",
    version_from="1.0",
    version_to="1.1",
    reversible=True,
    operations=[...],
)
```

## Capabilities

- detect version;
- apply migrations;
- preview;
- validate;
- roll back;
- record results;
- stop on incompatibilities;
- migrate backups;
- test migrations on copies.

## Completion Criteria

- migration framework;
- history;
- rollback;
- validation;
- safe automatic migrations;
- upgrade and downgrade tests;
- documentation.

---

# 11.17 — Backup and Recovery

## Objective

Ensure the system can recover from errors, corruption, or data loss.

## Backup Contents

A backup must include:

- relational database;
- Knowledge Graph;
- memory;
- documents;
- configuration;
- encrypted secrets;
- plugins;
- version metadata.

## Types

- full;
- incremental;
- manual;
- scheduled;
- pre-migration;
- pre-update;
- pre-critical-operation.

## Recovery Capabilities

- list backups;
- verify integrity;
- restore;
- restore partially;
- restore into a test environment;
- compare a backup with current state;
- recover after migration failure.

## Backup Manifest

```python
BackupManifest(
    id="backup-123",
    created_at="...",
    system_version="1.0.0",
    components=[...],
    checksum="...",
    encrypted=True,
)
```

## Completion Criteria

- creation;
- encryption;
- verification;
- restoration;
- partial restoration;
- scheduled backups;
- real recovery tests;
- documentation.

---

# 11.18 — Import and Export

## Objective

Prevent technological lock-in and allow CMM OS data to be moved.

## Export

Formats:

- JSON;
- JSONL;
- CSV;
- Markdown;
- GraphML;
- compressed archives;
- complete backup.

Exportable elements:

- conversations;
- memory;
- knowledge;
- goals;
- workflows;
- decisions;
- timeline;
- documents;
- configuration;
- versioned Bot definitions;
- portable Bot requested-capability policies.

## Import

It must support:

- format validation;
- duplicate detection;
- schema mapping;
- provenance preservation;
- version preservation;
- conflict display;
- change preview;
- cancellation;
- rollback.

## Bot Portability Rule

Portable Bot configuration is not portable effective authority.

Bot import/export must exclude credentials, tokens, cookies, hidden approval decisions, operating-system grants, and other secrets. Requested capabilities may travel as declarative configuration; privileged effective capability state must always be recomputed on the destination system.

Imported Bot definitions default to no privileged effective authority until canonical policy resolution explicitly permits it.

## Completion Criteria

- complete export;
- selective export;
- import;
- preview;
- conflict resolution;
- documentation;
- portability tests.

---

# 11.19 — Plugin System

## Objective

Allow CMM OS to be extended without modifying the core.

## Plugin Contract

```python
PluginDefinition(
    name="calendar-plugin",
    version="1.0.0",
    api_version="1",
    capabilities=[...],
    permissions=[...],
    entrypoint="...",
)
```

A plugin's declared capabilities describe what its implementation may satisfy; they do not grant user or Bot authority. Side-effecting tool implementations remain behind canonical permission, approval, validation, operation, and runtime boundaries.

## Plugin Types

- resource provider;
- operation provider;
- domain extension;
- model provider;
- UI extension;
- workflow provider;
- validator;
- event consumer;
- storage adapter;
- integration connector.

## Lifecycle

```text
discover
install
validate
enable
initialize
run
disable
upgrade
uninstall
```

## Security

- manifest;
- explicit permissions;
- optional signature;
- sandbox;
- limits;
- auditability;
- fault isolation;
- incompatibility detection before loading.

## Plugin SDK

It must include:

- contracts;
- types;
- examples;
- validation tools;
- test environment;
- documentation;
- plugin template.

## Completion Criteria

- registry;
- loading;
- activation;
- deactivation;
- permissions;
- versioning;
- SDK;
- example plugin;
- isolation tests;
- documentation.

---

# 11.20 — External Integrations

## Objective

Connect CMM OS to external services without coupling them to the core.

## Initial Integrations

- n8n;
- email;
- calendar;
- storage;
- Git;
- GitHub;
- local models;
- remote models;
- APIs;
- webhooks;
- search services;
- browser automation adapters;
- Computer Use adapters;
- document systems.

A concrete integration may implement one or more PlatformCapabilities, but implementation availability never grants effective authority. Capability authorization remains a CMM OS policy decision.

## Integration Adapter

```python
IntegrationAdapter(
    name="n8n",
    capabilities=[...],
    auth={...},
    rate_limits={...},
    permissions=[...],
)
```

## Capabilities

- authentication;
- synchronization;
- polling;
- webhooks;
- retries;
- circuit breaker;
- rate limiting;
- deduplication;
- idempotency;
- auditability;
- disconnection;
- simulation.

## n8n

The n8n integration must support:

- triggering workflows;
- receiving events;
- sending data;
- querying states;
- retrieving results;
- cancelling executions;
- recording traces.

## Completion Criteria

- adapter architecture;
- n8n integration;
- at least one calendar integration;
- at least one email integration;
- Git integration;
- error management;
- rate limiting;
- disconnection tests;
- documentation.

---

# 11.21 — Model Gateway

## Objective

Provide a single provider-independent access layer for local and remote models.

The Model Gateway must isolate the Cognitive Layer, Agent Runtime, Domain Intelligence, workflows, clients, and external adapters from concrete provider APIs.

## Responsibilities

- provider registration and resolution;
- model discovery;
- request normalization;
- response normalization;
- structured output;
- tool calling;
- multimodal requests;
- streaming;
- timeout and retry control;
- circuit breakers;
- provider failover;
- context preparation;
- provider cache support;
- cost estimation and accounting;
- latency measurement;
- privacy enforcement;
- audit generation;
- local and remote execution.

## Capability and Tool-Call Boundary

Model tool calls are normalized requests for capability use; they are not permission grants. A provider response cannot enable a PlatformCapability, widen scope, lower an approval requirement, increase autonomy or budget, or activate Computer Use.

Fallback and provider substitution must preserve or strengthen the effective capability envelope established before the model call.

## Model Request

```python
ModelRequest(
    id="model-request-123",
    task="reasoning",
    domain="health",
    operation="health.build_medical_timeline",
    knowledge_package_id="knowledge-package-123",
    required_capabilities=["structured_output"],
    context_size=12000,
    privacy="LOCAL_PREFERRED",
    maximum_cost_eur=0.05,
    latency_policy="normal",
    premium_allowed=False,
    preferred_providers=[],
    excluded_providers=[],
    metadata={},
)
```

## Model Response

```python
ModelResponse(
    request_id="model-request-123",
    provider_id="provider-123",
    model_id="model-123",
    content={},
    tool_calls=[],
    structured_output={},
    input_tokens=0,
    output_tokens=0,
    cached_tokens=0,
    estimated_cost_eur=0.0,
    actual_cost_eur=0.0,
    latency_ms=0,
    finish_reason="completed",
    metadata={},
)
```

## Provider Adapters

Initial adapters may include:

- Anthropic;
- OpenAI;
- Z.AI / GLM;
- Moonshot / Kimi;
- DeepSeek;
- Alibaba / Qwen;
- Google / Gemini;
- Ollama;
- OpenAI-compatible providers;
- preferred `OpenCodeGoProvider` adapter for direct access to the OpenCode Go multimodel subscription through provider-compatible APIs;
- experimental `ClineCliProvider` for ClinePass-backed models and Cline-specific external-worker workflows.

The architecture must not depend on a closed provider list.

### Preferred OpenCode Go Adapter

The Model Gateway should prioritize an `OpenCodeGoProvider` as the first subscription-backed multimodel adapter for everyday CMM OS operation. The provider must connect through supported OpenAI-compatible or Anthropic-compatible interfaces and normalize every request and response into the shared `ModelRequest` and `ModelResponse` contracts.

OpenCode Go is preferred over routing ordinary CMM OS requests through Cline because it allows CMM OS to remain the sole orchestrator. CMM OS must retain direct control over:

- prompt and context construction;
- domain and reasoning-profile selection;
- tools and operation permissions;
- memory and Knowledge Package use;
- privacy and sensitivity policies;
- response validation and escalation;
- model routing, fallback, latency, and cost accounting.

Initial use cases include:

- general and domain conversation;
- personal-assistant workflows;
- preparation of medical appointments and structured health summaries, subject to health-domain safeguards;
- long-context analysis;
- document and knowledge processing;
- coding and repository tasks when a direct model call is preferable to a second agent runtime.

Required safeguards:

- configuration-driven model discovery and enablement;
- provider and model capability metadata;
- per-model privacy, retention, and sensitivity restrictions;
- deterministic routing and explicit exclusions;
- timeout, retry, circuit-breaker, and fallback policies;
- token, latency, and cost accounting;
- audit records for the selected provider, model, policy, and validation result;
- no assumption that every model in the subscription is suitable for sensitive domains.

The first evaluation set should compare available models by domain, operation, quality, privacy, latency, and effective subscription limits. Exact model availability and commercial limits must remain configurable rather than hard-coded.

### Experimental Cline CLI Adapter

The Model Gateway may expose an optional `ClineCliProvider` that invokes Cline through its non-interactive CLI and normalizes its event stream into the shared `ModelResponse` contract.

The adapter is an external worker integration, not a replacement for the Model Gateway, Agent Runtime, routing, memory, validation, or policy layers. It must remain disabled by default and explicitly marked experimental.

Initial execution profiles:

- `repository_worker`: controlled repository and terminal access for long-running analysis or development tasks;
- `personal_assistant`: isolated working directory, no repository access, no terminal tools, and conversational use such as organizing concerns or preparing medical appointments.

Required safeguards:

- feature-flagged activation;
- executable discovery and version capture;
- subprocess isolation, timeout, cancellation, and output-size limits;
- structured event parsing and deterministic error normalization;
- no provider-side weakening of domain permissions, privacy, cost, or approval policies;
- explicit tool allowlists per execution profile;
- audit records identifying Cline, ClinePass, the selected underlying model when available, and all granted capabilities;
- fallback only to providers compatible with the original privacy and permission constraints.

The first supported experimental target is Kimi K3 through ClinePass, without assuming that the subscription provides a general-purpose model API outside Cline. This adapter is secondary to `OpenCodeGoProvider` for ordinary conversational, domain, and Model Gateway traffic.

## Provider Priority

Initial implementation priority:

1. direct provider adapters and `OpenCodeGoProvider`;
2. provider registry, routing, validation, privacy, and cost controls;
3. experimental `ClineCliProvider` for workflows that specifically benefit from Cline as an external agent.

Provider priority is an implementation default, not a permanent lock-in. Continuous evaluation may change routing preferences without coupling the core to any subscription or vendor.

## Policies

- `LOCAL_ONLY` information never leaves the local runtime;
- secrets are never included in model requests;
- provider and model selection remain traceable;
- every call records cost, latency, policy, and validation;
- unauthorized providers are blocked;
- provider payloads are treated as data, not policy;
- fallback cannot weaken privacy, permission, or budget constraints.

## Completion Criteria

- shared gateway;
- provider adapters;
- normalized requests and responses;
- local and remote execution;
- structured output;
- tool calling;
- streaming;
- fallback;
- privacy enforcement;
- cost accounting;
- observability;
- provider-failure tests;
- provider-independent contract tests.

---

# 11.22 — Event System

**Implementation status:** `REMEDIATED_AFTER_REAUDIT_V6_PENDING_INDEPENDENT_REAUDIT`
**Independent Audit V1:** `FAIL` — `BLOCKERS=0`, `MAJORS=4`, `MINORS=5`; report `docs/audits/phase-11.22-event-system-independent-audit-v1.md` (immutable)
**Independent Re-audit V2:** `FAIL` — `BLOCKERS=0`, `MAJORS=4`, `MINORS=0`; `AUDIT_V1_FINDINGS_REMEDIATED=9/9_VERIFIED`; report `docs/audits/phase-11.22-event-system-independent-reaudit-v2.md` (immutable)
**Independent Re-audit V3:** `FAIL` — `BLOCKERS=0`, `MAJORS=2`, `MINORS=1`; `AUDIT_V1_FINDINGS_REMEDIATED=9/9_VERIFIED`, `REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_VERIFIED`; report `docs/audits/phase-11.22-event-system-independent-reaudit-v3.md` (immutable)
**Independent Re-audit V4:** `FAIL` — `BLOCKERS=0`, `MAJORS=3`, `MINORS=0`; `REAUDIT_V3_REPRODUCTIONS_FIXED=3/3_VERIFIED`; report `docs/audits/phase-11.22-event-system-independent-reaudit-v4.md` (immutable)
**Independent Re-audit V5:** `FAIL` — `BLOCKERS=0`, `MAJORS=3`, `MINORS=0`; `V4_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED`, `PRIOR_REMEDIATION_REGRESSIONS=279_PASS`; report `docs/audits/phase-11.22-event-system-independent-reaudit-v5.md` (immutable)
**Independent Re-audit V6:** `FAIL` — `BLOCKERS=0`, `MAJORS=3`, `MINORS=1`; `V5_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED`, `PRIOR_REMEDIATION_REGRESSIONS=350_PASS`; report `docs/audits/phase-11.22-event-system-independent-reaudit-v6.md` (immutable)
**Design Point:** `DP-122`
**Acceptance:** `AT-DP-122` — `tests/events/test_phase11_22_dp122_acceptance.py`
**Reference:** [`docs/reference/phase-11-event-system.md`](../reference/phase-11-event-system.md)
**Design specification:** `docs/superpowers/specs/2026-09-26-phase-11.22-event-system-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-09-26-phase-11.22-event-system-implementation-plan.md`
**Remediation V1 prompt:** `docs/superpowers/prompts/2026-09-26-phase-11.22-remediation-v1-agent-prompt.md`
**Remediation V2 prompt:** `docs/superpowers/prompts/2026-09-26-phase-11.22-remediation-v2-agent-prompt.md`
**Remediation V3 prompt:** `docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v3-agent-prompt.md`
**Remediation V4 prompt:** `docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v4-agent-prompt.md`
**Remediation V5 prompt:** `docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v5-agent-prompt.md`
**Remediation V6 prompt:** `docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v6-agent-prompt.md`

> The broad roadmap wording below is preserved unchanged. The scoped
> implementation record follows it.

# 11.22 — Event System

## Objective

Connect components through events without creating direct dependencies.
# 11.22 — Event System

## Objective

Connect components through events without creating direct dependencies.

## Scoped implementation record

Phase 11.22 is an **integration and hardening** phase over the existing Phase 9
runtime event infrastructure. It adds no second event system.

```text
DP-122=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION
AT-DP-122=PASS_REPORTED
INDEPENDENT_AUDIT_V1=FAIL
REMEDIATION_V1=REMEDIATED_AFTER_AUDIT_V1_PENDING_INDEPENDENT_REAUDIT
INDEPENDENT_REAUDIT_V2=FAIL
AUDIT_V1_FINDINGS_REMEDIATED=9/9_VERIFIED
REMEDIATION_V2=REMEDIATED_AFTER_REAUDIT_V2_PENDING_INDEPENDENT_REAUDIT
INDEPENDENT_REAUDIT_V3=FAIL
REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_VERIFIED
REMEDIATION_V3=REMEDIATED_AFTER_REAUDIT_V3_PENDING_INDEPENDENT_REAUDIT
INDEPENDENT_REAUDIT_V4=FAIL
REAUDIT_V3_REPRODUCTIONS_FIXED=3/3_VERIFIED
REMEDIATION_V4=REMEDIATED_AFTER_REAUDIT_V4_PENDING_INDEPENDENT_REAUDIT
INDEPENDENT_REAUDIT_V5=FAIL
V4_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED
PRIOR_REMEDIATION_REGRESSIONS=279_PASS
REMEDIATION_V5=REMEDIATED_AFTER_REAUDIT_V5_PENDING_INDEPENDENT_REAUDIT
INDEPENDENT_REAUDIT_V6=FAIL
V5_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED
PRIOR_REMEDIATION_REGRESSIONS=350_PASS
REMEDIATION_V6=REMEDIATED_AFTER_REAUDIT_V6_PENDING_INDEPENDENT_REAUDIT
```

What was implemented:

- one canonical transport, reused: `AgentRuntimeEventBus` (now with an additive
  finite per-subscriber attempt count, replay-authorised dispatch and canonical
  dead-letter binding);
- one canonical registry, reused: `AgentRuntimeEventRegistry` through the Phase 9
  event-type map, extended additively with sixteen platform event names;
- one canonical repository contract, reused and implemented durably:
  `FileAgentRuntimeEventRepository` (append-only JSONL, canonical
  serialization/deserialization, `fsync` before success, restrictive permissions,
  content-bound deduplication, fail-closed corruption handling);
- one canonical replay owner, extended: `AgentRuntimeEventReplayer` now
  re-notifies stored events instead of attempting to re-save them;
- one canonical dead-letter authority, reused unchanged;
- an immutable twenty-name platform event catalog with exactly one producer
  disposition per name, registered through the canonical authority rather than a
  second registry;
- explicit one-way translation tables for orchestration and kernel events, with
  unmapped facts observed and skipped rather than guessed;
- one payload safety gate that rejects unsafe content before persistence;
- the thin `EventSystem` composition facade owning the persist-before-deliver
  ordering, idempotent duplicate handling and fail-closed identity conflicts;
- a production `OrchestrationEventSink` adapter and a one-way
  `kernel.events.Event` adapter;
- one Phase 11.1 composition module (`phase11_22_events`) with seven enforceable
  service bindings, composed into the production local runtime;
- an explicit, deterministic durable-storage location that is never the source
  tree;
- read-only stats/health projection for Phase 11.23.

What Phase 11.22 does **not** add, by explicit design ruling:

```text
SECOND_EVENT_BUS=FORBIDDEN
SECOND_EVENT_REGISTRY=FORBIDDEN
SECOND_REPOSITORY_PROTOCOL=FORBIDDEN
SECOND_REPLAY_ENGINE=FORBIDDEN
SECOND_DLQ_AUTHORITY=FORBIDDEN
BROKER_ABSTRACTION=FORBIDDEN
COMMAND_BUS=FORBIDDEN
JOB_QUEUE=FORBIDDEN
SERVICE_LOCATOR=FORBIDDEN
SECOND_APPLICATION_CONTAINER=FORBIDDEN
EXTERNAL_BROKER_DEPENDENCY=FORBIDDEN
HTTP_SSE_WEBSOCKET_EVENT_ROUTE=FORBIDDEN
CMMCHAT_INTEGRATION=NOT_IMPLEMENTED
OBSERVABILITY_BACKEND=PHASE_11_23
GENERAL_RECOVERY=PHASE_11_24
```

Six catalog names are registered but reserved because no canonical owner exposes
a safe emission seam yet: `session.created`, `reasoning.completed`,
`knowledge.updated`, `backup.created`, `plugin.failed`, `security.alert`. No
producer was fabricated to make the catalog appear active.

Gate results are recorded in the reference document and the requirements matrix.

## Remediation V1 record

Independent Audit V1 returned `FAIL` (`BLOCKERS=0`, `MAJORS=4`, `MINORS=5`) against
implementation HEAD `4e3bfa8067099e2efd3c2fb793a2e640f5d1859e`. Remediation V1
fixed exactly those nine findings — content-bound fingerprint, universal
`publish_event()` publication boundary, subscriber-targeted dead-letter replay,
preserved explicit source correlation/causation, `retry_total` on successful
retries, canonical corruption errors for malformed persisted payload shapes,
fail-closed forbidden kernel source content, corrected reserved-event count
documentation, and corrected Phase 9 modification wording — using strict TDD with
adversarial regressions per finding. The accepted one-authority architecture was
preserved: no second bus, registry, repository protocol, replay engine or DLQ was
added.

The immutable Audit V1 report
(`docs/audits/phase-11.22-event-system-independent-audit-v1.md`) and the immutable
V1 bundle (`phase-11.22-event-system-audit-v1.tar.gz`, SHA-256
`a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3`) are preserved
unchanged.

## Independent Re-audit V2 and Remediation V2 record

Independent Re-audit V2 (`docs/audits/phase-11.22-event-system-independent-reaudit-v2.md`,
immutable) verified all nine Audit V1 findings as remediated
(`AUDIT_V1_FINDINGS_REMEDIATED=9/9_VERIFIED`) and raised exactly four new majors
against the audited V2 implementation HEAD
`e67ab1ccea691fd8e76a0dfb8e4721c03b13b51d`:

```text
INDEPENDENT_REAUDIT_V2=FAIL
BLOCKERS=0
MAJORS=4
MINORS=0
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V2_ONLY
```

Remediation V2 fixed exactly those four findings under strict TDD (a reproducing
adversarial regression first, then the minimum fix, then the nearest regressions):

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V2-001` | persisted free-form header channels (`metadata`, `permissions`, `producer`, `aggregate_id`, `source` and the other persisted identifiers) bypassed the safety policy, so forbidden material could be moved out of `payload.data` into a persisted header fact | one canonical safety step now covers every persisted free-form event fact — recursively scanned `metadata`, per-entry `permissions`, and every persisted identifier validated by a narrow safe-identifier rule plus the canonical credential/private-marker scan; the same policy is applied at `create_event()`, `publish()` and `publish_event()` |
| `MAJOR-V2-002` | an unsupported `schema_version` could be published and durably appended, leaving a store the same build could not reopen | the publication boundary and the durable repository both refuse a schema (and a record) the canonical factory cannot deserialize, reusing the factory's one supported-schema knowledge, before any byte is committed |
| `MAJOR-V2-003` | the event classes were frozen only at the top level, so a subscriber could mutate `payload.data`, `metadata` and `permissions` for later subscribers and for live repository evidence | canonical facts are effectively immutable at every boundary: the repository stores and returns detached canonical snapshots, the bus hands each subscriber its own detached snapshot, and the dead-letter record holds a detached snapshot; fingerprints and JSON-compatible container shapes are unchanged |
| `MAJOR-V2-004` | the Kernel bridge scanned but discarded the real `DomainEvent` structural `payload`, losing mapped lifecycle facts, and downgraded a restrictive source sensitivity to the platform default | the translation table declares an explicit `nested_fact_keys` subset read from the real Domain structure (only named, vocabulary-bounded facts may cross), `approved` is projected as an already-bounded resolution fact, `execution_id` is decided once as a bounded payload fact, and an explicit source sensitivity maps through an explicit non-downgrading table that fails closed on an unmapped classification |

The accepted one-authority architecture was preserved, all nine Audit V1 fixes
remain green, and no second bus, registry, repository protocol, replay engine, DLQ,
container, broker abstraction, command bus or service locator was added. The
immutable Audit V1 report, the immutable Re-audit V2 report, and the immutable V1
and V2 bundles are preserved byte-identical.

## Independent Re-audit V3 and Remediation V3 record

Independent Re-audit V3 (`docs/audits/phase-11.22-event-system-independent-reaudit-v3.md`,
immutable) verified all nine Audit V1 findings and all four Re-audit V2
reproductions as fixed (`9/9_VERIFIED`, `4/4_VERIFIED`) and raised exactly two
majors and one minor against the audited V3 implementation HEAD
`7b582312319beae9b5d0e19dc25a726ee9d65360`:

```text
INDEPENDENT_REAUDIT_V3=FAIL
BLOCKERS=0
MAJORS=2
MINORS=1
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V3_ONLY
```

Remediation V3 fixed exactly those three findings under strict TDD (a reproducing
adversarial regression first, then the minimum fix, then the nearest regressions),
inside the existing safety authority and canonical contracts:

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V3-001` | persisted `metadata` was content-scanned but never type-checked, so opaque runtime objects, `bytes`/`bytearray` and `NaN`/`inf` were accepted and an opaque object's `__str__()` could stringify a credential into durable JSONL; `sensitivity` was not runtime-validated; a plain-string `permissions` value was coerced into a character list | the one scanner now applies the shared structural descriptive-value rule to every persisted container so opaque/binary/non-finite values fail closed before append; `canonicalize_platform_event_sensitivity()` enforces the canonical `EventSensitivity` enum with exactly one supported-string normalization and rejects credential-bearing/private-marker labels; `validate_platform_permissions()` validates the container shape before factory coercion; canonical serialization no longer uses `json.dumps(default=str)` |
| `MAJOR-V3-002` | `publish()` handed nested `MappingProxyType` views to the factory, so supported nested mappings crashed; frozen sequences reopened from JSON as lists, so live and persisted shapes drifted; shallow normalization left nested caller aliases reachable through `PublicationResult.event` | `canonicalize_platform_payload()` normalizes mappings to plain `dict` and supported sequences to plain `list` at the public boundary and re-validates the result; the canonical serialization emits that same shape, so live, persisted, reopened and replayed facts are equal with a stable fingerprint; `AgentRuntimeEventNormalizer.normalize()` deep-detaches nested containers |
| `MINOR-V3-001` | `InMemoryAgentRuntimeDeadLetterQueue.get()`/`list()` and `EventSystem.list_dead_letters()` returned live nested aliases, so a caller could mutate retained dead-letter evidence | the queue stores a detached snapshot and `get()`, `list()`, `remove()` and replay all pass the record through `detached_dead_letter_copy()`, built on the existing `detached_event_copy()` plus the canonical deep-detach helper; targeted replay is unchanged |

The accepted one-authority architecture was preserved, all nine Audit V1 fixes and
all four Re-audit V2 reproductions remain green, and no second bus, registry,
repository protocol, replay engine, DLQ, container, broker abstraction or event
contract was added. The immutable Audit V1 report, the immutable Re-audit V2
report, the immutable Re-audit V3 report and the immutable V1, V2 and V3 bundles are
preserved byte-identical.

## Independent Re-audit V4 and Remediation V4 record

Independent Re-audit V4 (`docs/audits/phase-11.22-event-system-independent-reaudit-v4.md`,
immutable) verified all three Re-audit V3 reproductions as fixed
(`REAUDIT_V3_REPRODUCTIONS_FIXED=3/3_VERIFIED`) and raised exactly three majors
against the audited V4 implementation HEAD
`621cf5f67c2935f05cdc1ceb2ab966b562b1381e`:

```text
INDEPENDENT_REAUDIT_V4=FAIL
BLOCKERS=0
MAJORS=3
MINORS=0
MAJOR_V4_001=MEMORYVIEW_BINARY_BYPASSES_CANONICAL_EVENT_SAFETY
MAJOR_V4_002=MANUAL_PUBLISH_EVENT_SENSITIVITY_NOT_CANONICALIZED
MAJOR_V4_003=DLQ_ERROR_TYPE_CAN_LEAK_SECRET_TEXT
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V4_ONLY
```

Remediation V4 fixed exactly those three findings under strict TDD (a reproducing
adversarial regression first — initial red `18 failed / 5 passed` — then the
minimum fix, then the nearest regressions), inside the existing safety authority
and canonical contracts:

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V4-001` | the V3 scalar binary rejection already listed `memoryview`, but the shared sequence predicate excluded only `str`, `bytes` and `bytearray`. `memoryview` is a registered `collections.abc.Sequence`, so a binary buffer was treated as an ordinary descriptive sequence and recursively canonicalized into a plain integer list, putting raw binary bytes into persisted `payload.data` and persisted header containers | the one existing sequence predicate now classifies `memoryview` as binary, so the already-existing scalar binary rejection is reachable for it; the payload shape transform also refuses a binary container explicitly. `bytes`, `bytearray` and `memoryview` now all fail closed in every persisted Phase 11.22 content channel |
| `MAJOR-V4-002` | the publication boundary validated a canonical sensitivity string without replacing it, and the normalizer copied `header.sensitivity` unchanged, so a manually built event with `sensitivity="restricted"` kept a `str`: accepted and stored in memory, and `AttributeError: 'str' object has no attribute 'value'` for the durable repository | the publication boundary now normalizes rather than merely validates: it applies the existing canonical sensitivity rule to the persisted fact and, when the result differs, replaces the header sensitivity with the canonical member before normalization and persistence. Both public routes produce one representation and both official repository implementations agree |
| `MAJOR-V4-003` | the DLQ derived `error_type`/`error` from `type(exc).__name__` unvalidated, so a dynamically created credential-bearing or private-marker class name could enter canonical DLQ data with no raw exception message involved | one bounded safe DLQ error-category derivation now guards both exception-capture sites and the single DLQ write point: the transport-local bounded-name half lives in `runtime_event_bus.py`, and the credential/private-marker half is `category_for_delivery_error()` in the existing `cmm/events/event_payload_safety.py`, injected through `bind_error_categorizer()` because `cmm/agent_runtime` is architecturally forbidden from importing `cmm.domains`. An ordinary `RuntimeError` stays meaningfully categorized; every other name becomes the neutral bounded category `SubscriberDeliveryError` |

The accepted one-authority architecture was preserved, all nine Audit V1 fixes, all
four Re-audit V2 reproductions and all three Re-audit V3 reproductions remain green,
`AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0` is still enforced, and no second bus, registry,
repository protocol, replay engine, DLQ, safety module, container, broker
abstraction or event contract was added. The immutable Audit V1 report, the
immutable Re-audit V2 report, the immutable Re-audit V3 report, the immutable
Re-audit V4 report and the immutable V1-V4 bundles are preserved byte-identical.

The phase remained open, not independently verified and not complete until the
fresh independent re-audit of the exact-HEAD **V5** bundle passed.

## Remediation V5 record

Independent Re-audit V5 verified all three Re-audit V4 reproductions fixed
(`V4_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED`) with `279` prior remediation
regressions preserved, and returned `FAIL` with three new majors (`BLOCKERS=0`,
`MAJORS=3`, `MINORS=0`). Remediation V5 fixed exactly those three under strict TDD
— a red adversarial regression first (initial red `30 failed / 41 passed`), then
the minimum fix, then the nearest regressions:

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V5-001` | the V4 binary rejection enumerated `bytes`, `bytearray` and `memoryview` by exact class, but `array.array` is both a compact binary buffer and a registered `collections.abc.Sequence`, so its byte values were canonicalized into a plain integer list and persisted through `payload.data`, nested payload data and metadata | binary/buffer classification is now **semantic**: one bounded buffer-protocol probe asks whether the interpreter can expose the value's raw bytes as an unsigned byte view, so `bytes`, `bytearray`, `memoryview` and every `array.array` typecode fail closed before all generic sequence handling. `str` and the descriptive containers support no buffer protocol and stay valid, and banning all sequences was explicitly rejected because a `list`/`tuple` of identifiers and an explicit `list[int]` reference must remain valid |
| `MAJOR-V5-002` | the boundary bounded the payload vocabulary but not the value semantics implied by an approved key, so raw user text was durably persisted under `status`, `request_id` and `metadata["note"]` | one canonical `PAYLOAD_KEY_CLASSES` specification gives every allowed payload key exactly one explicit lifecycle value class (identifier, category, boolean, number, version, timestamp, structured reference, reference sequence), with a regression asserting the union equals the allowlist so nothing falls through to prose; structured references are validated recursively against their documented nested shape; `METADATA_KEY_CLASSES` admits only bounded lifecycle metadata keys actually used by current producers, adapters and closed-phase contracts, and an unknown metadata key fails closed |
| `MAJOR-V5-003` | the V4 DLQ fix was only secret-safe once the composed `EventSystem` had injected the credential/private-marker categorizer, so direct canonical use of `AgentRuntimeEventBus` + DLQ + bounded retry wrote an identifier-shaped credential class name into DLQ `error_type`/`error` | `safe_delivery_error_type()` now records the neutral bounded category `SubscriberDeliveryError` whenever no external categorizer is bound. The transport can only prove a class name's shape, never that it is free of a credential or private marker, so an unbound categorizer retains no attacker-influenced name. The composed `EventSystem` still binds the canonical categorizer, so ordinary `RuntimeError` stays useful, and the legacy direct single-attempt bus shape is unchanged |

The accepted one-authority architecture was preserved: no second bus, registry,
repository protocol, replay engine, DLQ, safety module, payload registry,
container, broker abstraction or event contract was added, and
`AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0` is still enforced. All nine Audit V1 fixes, all
four Re-audit V2 reproductions, all three Re-audit V3 reproductions and all three
Re-audit V4 reproductions remain green (`PRIOR_REMEDIATION_REGRESSIONS=279_PASS`).
The immutable Audit V1 report, the immutable Re-audit V2, V3, V4 and V5 reports,
and the immutable V1-V5 bundles are preserved byte-identical.

The phase remained open, not independently verified and not complete until the
fresh independent re-audit of the exact-HEAD **V6** bundle passed.

## Remediation V6 record

Independent Re-audit V6 verified all three Re-audit V5 reproductions fixed
(`V5_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED`) with `350` prior remediation
regressions preserved, and returned `FAIL` with three new majors and one new minor
(`BLOCKERS=0`, `MAJORS=3`, `MINORS=1`). Remediation V6 fixed exactly those four
under strict TDD — a red adversarial regression first (initial red
`90 failed / 37 passed`), then the minimum fix, then the nearest regressions:

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V6-001` | the V5 numeric class was called bounded but accepted any finite Python number, so `count = 10 ** 5000` was accepted by the official in-memory repository and raised `ValueError` inside the official file-backed repository while serializing — the same public event diverged across the two official repositories — and negative counts/durations/attempts/sequences plus `1e308` were accepted too | one explicit bound `MAX_PLATFORM_NUMERIC_FACT = 2**63 - 1` and one small `NUMERIC_FACT_SEMANTICS` table in the existing safety authority: count/attempt/attempts/sequence are real integers in `[0, bound]`, `duration_ms` is a finite integer/float in `[0, bound]`, `ratio` is the normalized `[0.0, 1.0]` ratio current producers publish, and every other numeric fact is finite and inside `[-bound, bound]`. Enforced before any repository interaction, so no repository is the safety boundary and the two official repositories cannot diverge |
| `MAJOR-V6-002` | the identifier character set kept `:`/`/`/`.` with no path-safety classification, so `file:///Users/alice/.ssh/id_rsa`, `Users/alice/.ssh/id_rsa` and `C:/Users/alice/.ssh/id_rsa` qualified as identifiers and were durably persisted — including in the canonical header `producer` fact — against the frozen design's "filesystem secrets/paths where not public-safe" rule | one narrow, purely syntactic classifier in the existing identifier/header safety authority: a `file:` URI scheme, a Windows drive-root path, a UNC share, an absolute POSIX path or `~` shorthand, a user-home directory segment, a known secret-bearing private directory segment (`.ssh`, `.aws`, `.gnupg`, `.kube`, `.docker`, `.azure`, `.netrc`, `.pgpass`, `.npmrc`, `.git-credentials`) or a private key material file name. No I/O, no path resolution, no content inspection. Applied on every persisted identifier channel, while `workflow:123`, `domain:legal` and `provider/model` stay valid |
| `MAJOR-V6-003` | payload keys equivalent to canonical header facts were validated independently and persisted alongside the header, so `header.event_id=header-event` and `payload.event_id=payload-event` coexisted — and, critically, `header.sensitivity=internal` alongside `payload.sensitivity=restricted`, a stricter classification hidden from the canonical authority | `CANONICAL_HEADER_PAYLOAD_KEYS` is declared once as the exact intersection of the bounded payload vocabulary with the canonical header fact names, and those payload keys are consumed into the canonical header before persistence instead of being persisted twice: an unset header fact takes the payload value, an equal one is left alone, a contradictory one fails closed, and an explicit `None` optional reference is not a value. `sensitivity` is the one non-equal resolution — the header keeps the stricter class, so a stricter source value is promoted and a lower payload value can never downgrade it. Both the factory path and the manual `publish_event` path apply the rule, and the kernel adapter no longer mirrors the source event name into a payload `event_type` key |
| `MINOR-V6-001` | the "canonical ISO-8601" class validated text shape rather than civil time, so `9999-99-99T99:99Z`, `2026-02-31T12:00Z` and `2026-09-27T25:61Z` reached durable evidence, and a timezone-less `2026-09-27T12:00` was accepted despite the timezone-aware chronology contract | the existing shape rule is retained and the value must additionally parse as a real calendar/time value and carry an explicit UTC offset; the existing `datetime` and canonical serialization approach is reused, nothing is silently reinterpreted or normalized, and an invalid value fails closed |

The accepted one-authority architecture was preserved: no second bus, registry,
repository protocol, replay engine, DLQ, safety module, payload registry,
numeric-policy registry, timestamp subsystem, container, broker abstraction or
event contract was added, and `AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0` is still
enforced. All nine Audit V1 fixes, all four Re-audit V2 reproductions, all three
Re-audit V3 reproductions, all three Re-audit V4 reproductions and all three
Re-audit V5 reproductions remain green
(`PRIOR_REMEDIATION_REGRESSIONS=350_PASS`). Four superseded V5 *control*
expectations were updated rather than preserved verbatim — the same legitimate
values are still exercised, the assertions now name the canonical header they
reach, and the conflicting cases are proved to fail closed by the V6 adversarial
suite; no V5 finding, fix or invariant was weakened. The immutable Audit V1 report,
the immutable Re-audit V2, V3, V4, V5 and V6 reports, and the immutable V1-V6
bundles are preserved byte-identical.

The phase remains open, not independently verified and not complete until the fresh
independent re-audit of the exact-HEAD **V7** bundle passes. Only that re-audit may
write `BLOCKERS=0`, `MAJORS=0`, `DP-122=VERIFIED_EXISTING`, `AT-DP-122=PASS` and
`CLOSURE_ELIGIBLE=YES`.

## Event

```python
Event(
    id="event-123",
    type="workflow.completed",
    aggregate_id="workflow-456",
    occurred_at="...",
    producer="agent-runtime",
    payload={...},
    correlation_id="correlation-123",
    causation_id="event-122",
)
```

## Minimum Events

- `session.created`;
- `message.received`;
- `intent.resolved`;
- `domain.selected`;
- `reasoning.completed`;
- `goal.created`;
- `goal.updated`;
- `workflow.started`;
- `workflow.paused`;
- `workflow.completed`;
- `workflow.failed`;
- `operation.executed`;
- `validation.completed`;
- `approval.requested`;
- `approval.resolved`;
- `knowledge.updated`;
- `memory.updated`;
- `backup.created`;
- `plugin.failed`;
- `security.alert`.

Additional Phase 11 events for Bots and platform capabilities include:

- `bot.created`;
- `bot.updated`;
- `bot.disabled`;
- `bot.enabled`;
- `bot.archived`;
- `bot.imported`;
- `bot.exported`;
- `bot.agent_binding.updated`;
- `bot.capability.requested`;
- `bot.capability.updated`;
- `capability.resolution.completed`;
- `capability.allowed`;
- `capability.blocked`;
- `capability.approval_required`;
- `tool.selected`;
- `tool.execution.started`;
- `tool.execution.completed`;
- `tool.execution.failed`;
- `computer_use.started`;
- `computer_use.waiting_for_human`;
- `computer_use.human_control`;
- `computer_use.resumed`;
- `computer_use.cancelled`;
- `computer_use.completed`;
- `computer_use.failed`.

These events reuse the canonical Event System. No Bot-specific or Computer-Use-specific parallel event bus is permitted.

## Capabilities

- publishing;
- subscription;
- persistence;
- replay;
- deduplication;
- correlation;
- ordering;
- retries;
- dead-letter queue;
- observability.

## Completion Criteria

- event bus;
- contracts;
- persistence;
- replay;
- deduplication;
- dead-letter queue;
- delivery tests;
- documentation.

---

# 11.23 — Observability

## Objective

Enable the system to explain what is happening and why.

## Logs

Structured logs containing:

- timestamp;
- level;
- component;
- event;
- `trace_id`;
- `correlation_id`;
- `session_id`;
- `workflow_id`;
- anonymized `user_id`;
- duration;
- result.

Bot/capability-aware logs should include optional `bot_id`, `capability_id`, and tool implementation identity where applicable, without exposing secrets.

## Metrics

Minimum metrics:

- requests;
- errors;
- latency;
- operations;
- workflows;
- retries;
- rollbacks;
- approvals;
- tokens;
- cost;
- model usage;
- memory;
- storage;
- events;
- plugins;
- integrations;
- Bot usage;
- capability resolutions and policy blocks;
- tool executions;
- Computer Use sessions, cancellations, and human handoffs.

## Tracing

Distributed traces:

```text
User Request
↓
Orchestrator
↓
Cognitive Layer
↓
Planner
↓
Executor
↓
Validator
↓
Memory Update
```

## Health Checks

- liveness;
- readiness;
- storage;
- models;
- integrations;
- events;
- plugins;
- migrations;
- backups.

## Completion Criteria

- structured logs;
- metrics;
- traces;
- health checks;
- dashboards;
- alerts;
- complete correlation;
- observability tests.

---

# 11.24 — Error Management and Recovery

## Objective

Manage failures without losing state or producing inconsistent behavior.

## Error Categories

- validation;
- execution;
- configuration;
- authentication;
- authorization;
- storage;
- model;
- integration;
- plugin;
- cognitive;
- workflow;
- timeout;
- cancellation;
- unknown.

## Recovery Policy

```text
Error
↓
Classify
↓
Retry?
↓
Fallback?
↓
Rollback?
↓
Ask user?
↓
Pause?
↓
Escalate?
↓
Fail safely
```

## Capabilities

- structured errors;
- retries;
- backoff;
- circuit breaker;
- fallback;
- rollback;
- compensation;
- pause;
- resume;
- dead-letter handling;
- alerts;
- diagnosis.

## Completion Criteria

- taxonomy;
- contracts;
- policies;
- retries;
- rollback;
- circuit breakers;
- recovery;
- chaos tests;
- documentation.

---

# 11.25 — Local Runtime and Docker

## Objective

Allow CMM OS to be installed and executed reproducibly on local hardware.

## Minimum Services

- application;
- API;
- UI;
- relational database;
- graph database;
- vector database;
- object storage;
- event bus;
- Ollama;
- n8n;
- observability stack.

## Profiles

```text
development
testing
production-local
minimal
offline
```

## Commands

```bash
docker compose up
docker compose down
docker compose logs
docker compose pull
docker compose run migrate
docker compose run backup
```

## Capabilities

- per-environment configuration;
- volumes;
- health checks;
- ordered dependencies;
- restart;
- resource limits;
- offline mode;
- updates;
- recovery.

## Completion Criteria

- functional Docker Compose;
- profiles;
- persistence;
- clean installation;
- updates;
- backup;
- restore;
- documentation;
- tests on a new machine.

---

# 11.26 — User Interface Architecture

## Objective

Build a modular interface capable of evolving without coupling itself to internal implementations.

## Modules

- Conversation;
- Bots;
- Tools / Capabilities;
- Goals;
- Workflows;
- Review Center;
- Timeline;
- Knowledge Explorer;
- Memory;
- Domains;
- Agents;
- Configuration;
- System Health.

## First-Party Client Boundary

**CMMChat** is the first-party conversational client/UI for CMM OS and is already under active interface development.

CMMChat consumes versioned CMM OS application contracts. CMM OS remains authoritative for intelligence, capabilities, tools, permissions, Agents, data, validation, privacy, approvals, budgets, autonomy, and execution.

CMM OS Core/Runtime must not depend on the CMMChat implementation. Alternative clients remain possible through the same stable interfaces.

Bots are the user-facing assistant/product abstraction. Agents remain the advanced persistent runtime/execution abstraction.

## Principles

- API-first;
- reusable components;
- predictable state;
- accessibility;
- responsive design;
- visible errors;
- progressive loading;
- consistent navigation;
- confirmation for sensitive actions;
- traceability.

## Common States

```text
loading
empty
ready
partial
stale
error
offline
unauthorized
```

## Capabilities

- real-time updates;
- notifications;
- filters;
- search;
- deep links;
- dark mode;
- accessibility;
- mobile support;
- reload recovery.

## Completion Criteria

- application shell;
- navigation;
- integrated modules;
- error states;
- responsive behavior;
- basic accessibility;
- interface tests;
- E2E tests.

---

# 11.27 — Search

## Objective

Provide unified search across the entire system.

## Sources

- conversations;
- memory;
- knowledge;
- documents;
- goals;
- workflows;
- events;
- decisions;
- timeline;
- code;
- plugins.

## Search Types

- textual;
- semantic;
- filtered;
- temporal;
- by entity;
- by domain;
- by source;
- by confidence;
- by state.

## Search Result

```python
SearchResult(
    type="knowledge",
    title="...",
    snippet="...",
    score=0.91,
    source="...",
    domain="health",
    timestamp="...",
    references=[...],
)
```

## Capabilities

- hybrid ranking;
- filters;
- pagination;
- facets;
- global search;
- contextual search;
- source navigation;
- permission enforcement;
- sensitive-data exclusion.

## Completion Criteria

- unified index;
- hybrid search;
- filters;
- permissions;
- navigation;
- relevance tests;
- isolation tests.

---

# 11.28 — Notifications

## Objective

Inform the user about relevant events without generating noise.

## Types

- pending approval;
- blocked workflow;
- at-risk goal;
- failed operation;
- required information;
- disconnected integration;
- failed backup;
- contradictory knowledge;
- scheduled review;
- completed goal.

## Notification

```python
Notification(
    id="notification-123",
    type="approval_required",
    priority="high",
    title="Pending approval",
    target="/approvals/123",
    created_at="...",
    read=False,
)
```

## Policies

- priority;
- grouping;
- muting;
- frequency;
- channels;
- schedule;
- domain;
- expiration.

## Completion Criteria

- notification center;
- priorities;
- read state;
- grouping;
- preferences;
- workflow integration;
- tests.

---

# 11.29 — Audit Trail

## Objective

Maintain an immutable history of relevant actions and decisions.

## Audit Record

```python
AuditRecord(
    id="audit-123",
    actor="agent:project-agent",
    action="knowledge.invalidate",
    resource="knowledge:item-456",
    before={...},
    after={...},
    reason="Outdated source",
    occurred_at="...",
    trace_id="...",
)
```

## Required Records

- permission changes;
- approvals;
- operations;
- memory modifications;
- knowledge modifications;
- deletions;
- configuration changes;
- plugins;
- migrations;
- backups;
- sensitive access;
- agent actions;
- Bot definition and Agent-binding changes;
- requested/effective capability decisions;
- tool implementation selection and execution;
- Computer Use lifecycle, scope, approvals, cancellation, and human handoff.

## Capabilities

- search;
- filters;
- export;
- integrity verification;
- retention;
- correlation;
- suspicious-change detection.

## Completion Criteria

- centralized audit trail;
- immutable records;
- filters;
- export;
- integrity;
- tampering tests;
- documentation.

---

# 11.30 — Performance and Resource Management

## Objective

Ensure the platform remains usable on local hardware and can scale.

## Capabilities

- caching;
- queues;
- batch processing;
- concurrency limits;
- prioritization;
- streaming;
- lazy loading;
- compression;
- indexes;
- archiving;
- token control;
- memory limits;
- CPU limits;
- cancellation.

## Resource Budget

```python
ResourceBudget(
    max_tokens=20000,
    max_model_calls=10,
    max_operations=30,
    max_duration_seconds=600,
    max_cost=2.0,
)
```

## Modes

- normal;
- low-resource;
- offline;
- high-accuracy;
- low-cost;
- background-safe.

## Completion Criteria

- budgets;
- limits;
- metrics;
- benchmarks;
- load tests;
- controlled degradation;
- documentation.

---

# 11.31 — Testing Strategy

## Objective

Validate the platform as a complete system.

## Levels

### Unit Tests

For contracts, services, and rules.

### Integration Tests

For connections between:

- Orchestrator and Cognitive Layer;
- Agent Runtime and Planner;
- Executor and Validation;
- Memory and Knowledge Graph;
- API and services;
- Bot services and the canonical Agent Registry;
- PlatformCapability resolution and Domain permissions;
- tool implementations and the canonical Operation Registry;
- Computer Use approvals, cancellation, and human handoff;
- plugins and integrations.

### Contract Tests

For:

- API;
- events;
- plugins;
- storage;
- models;
- Bot definitions;
- PlatformCapability descriptors and resolution states;
- external interfaces.

### End-to-End Tests

Minimum scenarios:

1. Simple contextual query.
2. Goal creation.
3. Workflow with multiple tasks.
4. Missing-information detection.
5. User question.
6. Session resumption.
7. Action requiring approval.
8. Approval and execution.
9. Failed validation.
10. Rollback.
11. Memory update.
12. Knowledge contradiction.
13. Model outage.
14. Integration outage.
15. Restore from backup.
16. Migration between versions.
17. Incompatible plugin.
18. Restart during a workflow.
19. Export and import.
20. Complete offline execution.

### Security Tests

- authentication;
- permissions;
- prompt injection;
- execution;
- plugins;
- secrets;
- sensitive data;
- privilege escalation.

### Resilience Tests

- network loss;
- database outage;
- timeout;
- partial corruption;
- unavailable service;
- duplicate operation;
- repeated events;
- restart.

## Completion Criteria

- unit suite;
- integration suite;
- contract tests;
- E2E tests;
- security tests;
- resilience tests;
- load tests;
- stable CI;
- defined coverage;
- globally green suite.

---

# 11.32 — Documentation

## Objective

Make it possible to install, use, administer, extend, and maintain CMM OS.

## User Documentation

- installation;
- quick start;
- conversation;
- Bots;
- Tools / Capabilities;
- Computer Use and human takeover;
- goals;
- workflows;
- approvals;
- memory;
- knowledge;
- domains;
- privacy;
- backups.

## Technical Documentation

- architecture;
- contracts;
- API;
- events;
- storage;
- security;
- agents;
- Bot contracts and lifecycle;
- PlatformCapability and tool-resolution architecture;
- Web, Browser, authenticated-browser, and Computer Use security;
- Cognitive Layer;
- plugins;
- migrations;
- observability;
- testing.

## Operational Documentation

- deployment;
- update;
- backup;
- restore;
- diagnosis;
- incidents;
- recovery;
- logs;
- performance.

## Developer Guide

- environment;
- structure;
- conventions;
- service creation;
- domain creation;
- operation creation;
- workflow creation;
- plugin creation;
- testing;
- release.

## Completion Criteria

- complete documentation;
- examples;
- diagrams;
- tutorials;
- reference;
- runbooks;
- changelog;
- contribution guide.

---

# 11.33 — Release Engineering

## Objective

Prepare a stable, reproducible, and updatable release.

## Versioning

Semantic Versioning:

```text
MAJOR.MINOR.PATCH
```

## Artifacts

- Docker images;
- CLI package;
- frontend;
- manifests;
- checksums;
- SBOM;
- changelog;
- release notes;
- migrations;
- compatible backups.

## Pipeline

```text
Build
↓
Unit Tests
↓
Integration Tests
↓
Contract Tests
↓
Security Tests
↓
E2E Tests
↓
Migration Tests
↓
Package
↓
Sign
↓
Release Candidate
↓
Acceptance Tests
↓
Stable Release
```

## Channels

- development;
- alpha;
- beta;
- release candidate;
- stable.

## Completion Criteria

- release pipeline;
- versioning;
- artifacts;
- signing;
- SBOM;
- release candidate;
- rollback;
- tested update;
- stable release.

---

# 11.34 — Provider Registry

## Status

```text
PHASE11_34=CLOSED
INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V2=FAIL
INDEPENDENT_REAUDIT_V3=FAIL
INDEPENDENT_REAUDIT_V4=FAIL
INDEPENDENT_REAUDIT_V5=FAIL
INDEPENDENT_REAUDIT_V6=FAIL
INDEPENDENT_REAUDIT_V7=PASS
BLOCKERS=0
MAJORS=0
MINORS=0
MAJOR-V6-01=VERIFIED_REMEDIATED
MAJOR-V5-01=VERIFIED_REMEDIATED
MAJOR-V5-02=VERIFIED_REMEDIATED
F11-014=VERIFIED_EXISTING
DP-134=VERIFIED_EXISTING
AT-DP-134=PASS
CLOSURE_ELIGIBLE=YES
AUDIT_STATUS=CLOSED_AFTER_INDEPENDENT_REAUDIT_V7_PASS
```

Phase 11 began with 11.34 as an intentional out-of-order bootstrap. The
implementation and Remediations V1–V6 are complete, final Independent Re-audit
V7 returned `PASS`, and the subphase is now closed by the dedicated docs-only
closure commit.

Historical Independent Audit V1 —
`docs/audits/phase-11.34-provider-registry-independent-audit-v1.md`: verdict
`FAIL`, remediated by Remediation V1.

Historical Independent Re-audit V2 —
`docs/audits/phase-11.34-provider-registry-independent-reaudit-v2.md`: verdict
`FAIL` on the exact-HEAD Remediation V1 bundle (`INDEPENDENT_REAUDIT_V2=FAIL`;
`BLOCKERS=0`; `MAJORS=5`; `MINORS=0`; findings `MAJOR-V2-01`…`MAJOR-V2-05`;
audited HEAD `1c54a720c57c6a84d990e8eb8dfc502c7423599e`; bundle SHA-256
`9f186aa51abc2533cfe171363cd760b8b6f7ff618223dc7c1358120e0499fdd4`). This
verdict is historical evidence, not a current result.

Historical Independent Re-audit V3 —
`docs/audits/phase-11.34-provider-registry-independent-reaudit-v3.md`: verdict
`FAIL` on the exact-HEAD Remediation V2 bundle (`INDEPENDENT_REAUDIT_V3=FAIL`;
`BLOCKERS=0`; `MAJORS=2`; `MINORS=1`; findings `MAJOR-V3-01`, `MAJOR-V3-02`,
`MINOR-V3-01`; audited HEAD `b0ff1169d022ba821f3a9e777497175bf003f47a`; bundle
SHA-256 `37eb5579d19d499b55c73f5eda16afe6052af2832ff58c86f9df4116e7e8c679`).
That audit verified `MAJOR-V2-03`, `MAJOR-V2-04` and `MAJOR-V2-05` as
remediated, and carried `MAJOR-V2-01`/`MAJOR-V2-02` forward as `MAJOR-V3-01`/
`MAJOR-V3-02`. Its verdict is historical evidence, not a current result.

Historical Independent Re-audit V4 —
`docs/audits/phase-11.34-provider-registry-independent-reaudit-v4.md`: verdict
`FAIL` on the exact-HEAD Remediation V3 bundle (`INDEPENDENT_REAUDIT_V4=FAIL`;
`BLOCKERS=0`; `MAJORS=3`; `MINORS=1`; findings `MAJOR-V4-01`, `MAJOR-V4-02`,
`MAJOR-V4-03`, `MINOR-V4-01`; audited HEAD
`46ef38ae477c801975b55b92c5f31f9137a3bc12`; audited tree
`4f24aed198e86d702791bef46d71df7d281a767d`; bundle SHA-256
`d8a21eac304d56789ee54b08bc6e96fa4e7ed995ef829897e9e1c268771c4f64`). That
audit verified `MAJOR-V3-01` and `MAJOR-V3-02` as remediated and confirmed the
V3 delta was findings-only, so the three V4 majors are a deeper authority/
coherence layer, not a reopening of V3. This verdict is historical evidence, not
a current result.

Historical Independent Re-audit V5 —
`docs/audits/phase-11.34-provider-registry-independent-reaudit-v5.md`: verdict
`FAIL` on the exact-HEAD Remediation V4 bundle (`INDEPENDENT_REAUDIT_V5=FAIL`;
`BLOCKERS=0`; `MAJORS=2`; `MINORS=0`; findings `MAJOR-V5-01`, `MAJOR-V5-02`;
audited HEAD `30dec367279b0b80a9692ee0f067365c6e93b0a7`; audited tree
`e058dca561efba5d9c0bc58165b12c19761e797c`; bundle SHA-256
`b72e03d78622b2927a9081bea4b180e1343ba9b8e2aea326bf44604ca3580d32`). That
audit confirmed the four V4 remediations materially improved the subphase, then
found two deeper operation-boundary defects: a stale provider-bound connection
could still reach discovery I/O before the coordinator failed closed, and the
route-only monotonic floor did not cover every state-changing discovery pass, so
`MINOR-V4-01` was only partially remediated. This verdict is historical
evidence, not a current result.

Historical Independent Re-audit V6 —
`docs/audits/phase-11.34-provider-registry-independent-reaudit-v6.md`: verdict
`FAIL` on the exact-HEAD Remediation V5 bundle (`INDEPENDENT_REAUDIT_V6=FAIL`;
`BLOCKERS=0`; `MAJORS=1`; `MINORS=0`; finding `MAJOR-V6-01`; audited HEAD
`cd780e3b7d74d2054470f277107986769ebb39a4`; audited tree
`ff534595fdc841bd77f40a271c8e50284c0b40e7`; bundle SHA-256
`af0e5f141ef865479946f3882cc13597bf06e33db50a90add22c38dc0d729e3a`). That
audit verified `MAJOR-V5-02` as remediated, held `MAJOR-V5-01` partially
remediated (the coordinator and `register()`/`restore()` boundaries are fixed;
`ModelRouteCatalog.restore_all()` remained a fresh-binding/rebinding bypass),
and opened `MAJOR-V6-01`: `restore_all()` could still create a fresh route
binding through a stale provider-bound connection and could preserve an old
connection-registration marker while the incoming route declared a different
connection id. This verdict is historical evidence, not a current result.

Final Independent Re-audit V7 —
`docs/audits/phase-11.34-provider-registry-independent-reaudit-v7.md`: verdict
`PASS` on the exact-HEAD Remediation V6 bundle (`INDEPENDENT_REAUDIT_V7=PASS`;
`BLOCKERS=0`; `MAJORS=0`; `MINORS=0`; `MAJOR-V6-01=VERIFIED_REMEDIATED`;
`MAJOR-V5-01=VERIFIED_REMEDIATED`; `MAJOR-V5-02=VERIFIED_REMEDIATED`;
`DP-134=VERIFIED_EXISTING`; `F11-014=VERIFIED_EXISTING`; `AT-DP-134=PASS`;
`CLOSURE_ELIGIBLE=YES`; audited HEAD
`a96468094d39f7bd8afe5a2d7a4daab67c0b55be`; audited tree
`583a260596bdd5eef331be8b3d9a0017fb5628d7`; bundle SHA-256
`09fd8ae76a64a898a8dca6b1397749defe9145c1f7ca865228646a66c6364100`;
audit-report commit `59a4c774b647d980927d02f4cea6476075235ca4`). This is
the final independent closure evidence for Phase 11.34.


Remediation V1, Remediation V2, Remediation V3, Remediation V4 and Remediation
V5 are historical context only: each was implemented and committed, then
independently re-audited `FAIL`. None is a current-state marker. Historical
artifacts: design
`docs/superpowers/specs/2026-09-14-phase-11.34-provider-registry-remediation-v1-design.md`;
plan
`docs/superpowers/plans/2026-09-14-phase-11.34-provider-registry-remediation-v1-implementation-plan.md`;
design
`docs/superpowers/specs/2026-09-15-phase-11.34-provider-registry-remediation-v2-design.md`;
plan
`docs/superpowers/plans/2026-09-15-phase-11.34-provider-registry-remediation-v2-implementation-plan.md`;
design
`docs/superpowers/specs/2026-09-15-phase-11.34-provider-registry-remediation-v3-design.md`;
plan
`docs/superpowers/plans/2026-09-15-phase-11.34-provider-registry-remediation-v3-implementation-plan.md`;
design
`docs/superpowers/specs/2026-09-15-phase-11.34-provider-registry-remediation-v4-design.md`;
plan
`docs/superpowers/plans/2026-09-15-phase-11.34-provider-registry-remediation-v4-implementation-plan.md`;
design
`docs/superpowers/specs/2026-09-15-phase-11.34-provider-registry-remediation-v5-design.md`;
plan
`docs/superpowers/plans/2026-09-15-phase-11.34-provider-registry-remediation-v5-implementation-plan.md`.

Remediation V6 implemented the intended remediation for exactly the one Re-audit
V6 finding and has now been independently verified by final Re-audit V7 `PASS`.
`MAJOR-V6-01`, `MAJOR-V5-01` and `MAJOR-V5-02` are
`VERIFIED_REMEDIATED`. Design
`docs/superpowers/specs/2026-09-15-phase-11.34-provider-registry-remediation-v6-design.md`;
plan
`docs/superpowers/plans/2026-09-15-phase-11.34-provider-registry-remediation-v6-implementation-plan.md`.
It changes no design point: `DP-134` remains the single closure design point for
Phase 11.34, and no new requirement identifier was introduced.

CMM Usage integration remains deferred and not performed; CMMChat integration
remains deferred by the user.

## Design Point

`DP-134` — Canonical, Persistent and Fail-Closed Provider Registry: CMM OS
maintains exactly one authoritative provider identity inventory through the
canonical `ProviderRegistry`, with `ModelCatalog`, accepted provider
connections and provider-specific model routes referentially bound to that
authority; Provider Registry state is locally persisted through one versioned,
deterministic, no-secret repository boundary with atomic restore/save behavior
and sanitized audit history; provider detection never grants connection
authority; subscription providers requiring isolation cannot become connected
without a validated CMM-owned isolation outcome; onboarding is atomic and
failed operations cannot mutate pre-existing credentials, connection state or
persisted revision; dynamic discovery remains administrative and performs no
inference; Qwen Token Plan and Qwen Cloud PAYG remain distinct
provider/account surfaces; no parallel provider inventory, persistence
framework, isolation runtime, routing engine or usage catalog is introduced.

**Owners:** `kernel/llm/provider_registry.py` (identity authority);
`kernel/llm/provider_state.py` + `kernel/llm/provider_state_repository.py`
(persistence); `kernel/llm/provider_state_coordinator.py` (the one
revision/audit commit path for connection acceptance, route discovery lifecycle
and validation transitions); `kernel/llm/provider_onboarding.py` +
`kernel/llm/subscription_profiles.py` (isolation/onboarding);
`kernel/llm/provider_manifests.py` (provider-bound metadata).

## Requirements Traceability

`F11-014` — canonical, persistent, auditable and fail-closed Provider Registry
— maps `Phase 11` → `11.34` → `DP-134` → `AT-DP-134` in the canonical Phase 11
requirements matrix:
[`docs/reference/phase-11-stable-integrated-platform-requirements-matrix.md`](../reference/phase-11-stable-integrated-platform-requirements-matrix.md).
That document is the Phase 11 owner for `F11-014`; the inherited/preassigned
planning rows `F11-001`…`F11-013` stay normatively owned by the
[Domain Intelligence Requirements Matrix](../reference/domain-intelligence-requirements-matrix.md)
(Phase 10). `F11-014` is `VERIFIED_EXISTING` after final Independent Re-audit V7 `PASS` and
Phase 11.34 docs-only closure.

## Connected Acceptance

`AT-DP-134` —
`tests/llm/test_provider_registry_dp134_acceptance.py` (scenarios A–M plus the
Remediation V2 adversaries for `MAJOR-V2-01`…`MAJOR-V2-05`, the Remediation V3
adversaries for `MAJOR-V3-01`/`MAJOR-V3-02`, the Remediation V4 adversaries
for `MAJOR-V4-01`…`MAJOR-V4-03`/`MINOR-V4-01`, the Remediation V5 adversaries
for `MAJOR-V5-01`/`MAJOR-V5-02` and the Remediation V6 adversaries for
`MAJOR-V6-01` (`V6-A` fresh route under a stale provider-bound connection,
`V6-B` coherent same-route-id rebind to a declared current connection, `V6-C`
exact rollback under a stale parent), over the real canonical
components and their official in-memory implementations).
Final Independent Re-audit V7 executed and verified the connected acceptance:
`AT-DP-134=PASS` (`67 passed`), with `DP-134=VERIFIED_EXISTING`,
`F11-014=VERIFIED_EXISTING` and `CLOSURE_ELIGIBLE=YES`.

## Objective

Maintain a dynamic, versioned, and auditable registry of providers and models.

## Provider Definition

```python
ProviderDefinition(
    id="provider:zai",
    provider_type="remote",
    api_compatibility="openai",
    enabled=True,
    region=None,
    data_policy={},
    authentication_reference="secret:zai",
    rate_limits={},
    health_status="available",
    metadata={},
)
```

## Model Definition

```python
ModelDefinition(
    id="model:glm",
    provider_id="provider:zai",
    version=None,
    capabilities=[
        "reasoning",
        "coding",
        "tool_calling",
        "structured_output",
    ],
    context_window=None,
    modalities=[],
    pricing={},
    cache_support={},
    latency_history={},
    quality_history={},
    error_rate=None,
    availability="available",
    limits={},
    metadata={},
)
```

The registry must manage providers, models, versions, capabilities, context windows, modalities, API compatibility, pricing, historical latency and quality, error rates, cache support, tool calling, structured output, availability, data policies, regions, and operational health.

Registry data must be configurable and updateable without modifying the core.

---

# 11.35 — Routing Policy Engine

## Objective

Select the most appropriate model through deterministic, explicit, and auditable rules.

## Routing Factors

- domain;
- operation;
- required capability;
- complexity;
- context length;
- privacy;
- sensitivity;
- estimated cost;
- remaining budget;
- latency;
- historical quality;
- reliability;
- availability;
- tool-calling support;
- structured-output support;
- multimodal support;
- workflow policy;
- domain policy;
- user consumption mode;
- provider exclusions.

## Routing Decision

```python
RoutingDecision(
    id="routing-decision-123",
    request_id="model-request-123",
    selected_provider_id="provider:zai",
    selected_model_id="model:glm",
    candidate_models=[],
    rejected_models=[],
    reason_codes=[],
    estimated_cost_eur=0.0,
    expected_quality=None,
    expected_latency_ms=None,
    fallback_policy_id=None,
    configuration_version="1",
    created_at="...",
    metadata={},
)
```

The first router must be deterministic and configurable. It must not initially depend on machine learning.

---

# 11.36 — Model Evaluation Framework

## Objective

Compare models using general benchmarks and the domain suites introduced in Phase 10.

## Capabilities

- load benchmark suites;
- execute the same case against several models;
- preserve requests and outputs;
- apply automatic evaluators;
- support human evaluation;
- calculate cost and latency;
- compare provider and model versions;
- detect regressions;
- generate rankings;
- recommend models by operation and domain;
- export evaluation reports;
- feed historical evidence to the router.

---

# 11.37 — Response Validation

## Objective

Validate generated responses before they are accepted, persisted, executed, or delivered.

## Decisions

```text
accept
accept_with_warning
repair
regenerate
fallback
escalate
request_approval
reject
```

## Checks

- required format;
- schema compliance;
- valid JSON;
- correct use of context;
- unsupported claims;
- contradictions;
- missing required information;
- reasoning-profile compliance;
- domain-policy compliance;
- privacy compliance;
- tool-call validity;
- cost-limit compliance;
- need for premium review.

Response Validation must reuse Phase 7 validation contracts where appropriate and must not alter source knowledge silently.

---

# 11.38 — Cost Management Layer

## Objective

Provide native economic control across providers, models, sessions, domains, goals, workflows, and operations.

## Budget Configuration

```python
CostConfiguration(
    monthly_limit_eur=30.00,
    daily_limit_eur=None,
    premium_limit_eur=8.00,
    warning_threshold_percent=80,
    hard_limit=True,
    allow_manual_override=True,
    savings_mode="automatic",
    metadata={},
)
```

The values are configurable and must not be hard-coded.

## Capabilities

- monthly budget;
- daily budget;
- session budget;
- goal budget;
- workflow budget;
- domain budget;
- operation budget;
- premium budget;
- estimated cost;
- actual cost;
- reservations;
- warnings;
- hard blocking;
- savings mode;
- approval for overruns;
- provider comparisons;
- model comparisons;
- cost per accepted result;
- historical reporting.

---

# 11.39 — Consumption Modes

## Objective

Allow the user to select a global or scoped balance between quality, cost, speed, and privacy.

## Initial Modes

```text
QUALITY
BALANCED
SAVINGS
LOCAL_ONLY
CUSTOM
```

Modes may be configured globally or overridden by domain, workflow, goal, session, or operation, subject to more restrictive policies.

---

# 11.40 — Model and Cost Dashboard

## Objective

Expose model usage, routing outcomes, quality, cache efficiency, and spending in a single operational view.

## Required Views

- monthly spending;
- remaining budget;
- spending by provider;
- spending by model;
- spending by domain;
- spending by workflow;
- input, output, and cached tokens;
- cognitive-cache usage;
- provider-cache usage;
- fallback count;
- escalation count;
- acceptance rate;
- average quality;
- latency;
- provider errors;
- avoided cost;
- premium usage.

## Dashboard Result

```python
ModelCostDashboard(
    period="2026-07",
    monthly_limit_eur=30.0,
    spent_eur=0.0,
    remaining_eur=30.0,
    by_provider=[],
    by_model=[],
    by_domain=[],
    by_workflow=[],
    cache_metrics={},
    quality_metrics={},
    routing_metrics={},
    generated_at="...",
    metadata={},
)
```

The dashboard must preserve drill-down links to routing decisions, model execution records, validations, approvals, and audit entries.

---

# 11.41 — Continuous Provider Evaluation

## Objective

Detect provider and model changes over time instead of assuming that a previously selected model remains optimal.

## Evaluation Triggers

- manual execution;
- scheduled execution;
- new model discovery;
- provider version change;
- price change;
- capability change;
- latency degradation;
- error-rate increase;
- benchmark regression;
- routing anomaly;
- user-requested review.

## Capabilities

- discover new models;
- compare model versions;
- detect price changes;
- detect capability changes;
- detect latency changes;
- detect provider failures;
- rerun domain benchmark suites;
- detect regressions;
- update quality history;
- update availability;
- propose routing-policy changes;
- require approval before activating material policy changes.

Rankings must be scoped by domain, operation, cost, privacy, context length, quality, and availability.

---

# 11.42 — Provider Cache and Prompt Optimization

## Objective

Complement the Phase 8 Cognitive Cache with provider-level caching and safe prompt optimization.

## Capabilities

- prompt caching;
- prefix reuse;
- system-instruction reuse;
- context deduplication;
- unchanged-content detection;
- incremental summaries;
- safe compression;
- token reduction;
- provider-specific cache adaptation;
- cache-hit accounting;
- avoided-cost accounting.

## Restrictions

Optimization must not:

- alter the meaning of the context;
- remove provenance;
- hide uncertainty;
- remove blocking contradictions;
- weaken privacy;
- reuse content across unauthorized sessions;
- bypass Knowledge Package validation;
- treat provider cache as cognitive truth.

---

# 11.43 — Knowledge Package Export

## Objective

Export provider-independent context for use outside CMM OS.

## Formats

```text
JSON
Markdown
YAML
compressed bundle
portable prompt
provider bundle
```

## Use Cases

- consult Claude;
- consult ChatGPT;
- change provider;
- share context with a professional;
- migrate between installations;
- create an audit copy;
- use CMM OS as a context layer for another AI.

Every export must preserve:

- schema version;
- provenance;
- epistemological types;
- temporal validity;
- privacy classification;
- permissions;
- exclusions;
- checksum;
- export actor;
- export date.

Export must be blocked when the effective privacy policy forbids it.

---

# 11.44 — Model Usage Audit

## Objective

Make every model call auditable without storing secrets or unnecessary sensitive payloads.

## Required Audit Data

- information included;
- information excluded;
- provider;
- model;
- provider and model versions;
- applied privacy policy;
- applied routing policy;
- selection reason;
- estimated cost;
- actual cost;
- latency;
- cache usage;
- validation results;
- fallback;
- escalation;
- approval;
- final acceptance status;
- persistence decision;
- memory updates;
- configuration version;
- trace and correlation identifiers.

## Privacy Requirements

The audit must avoid storing:

- credentials;
- secrets;
- unrestricted prompt contents;
- full sensitive responses when retention is prohibited;
- unrelated personal data.

When payload retention is forbidden, the audit must preserve hashes, classifications, exclusions, policy decisions, and trace references.

---

# 11.45 — Platform Layer Boundaries

## Objective

Separate CMM OS into stable layers so deployment, clients, providers, storage, and integrations can evolve without changing the cognitive core.

## Layers

```text
Core
Runtime
Data
Clients
Adapters
```

### Core

Contains provider-independent contracts and domain logic:

- knowledge;
- cognition;
- validation;
- goals;
- workflows;
- agents;
- domains;
- permissions;
- platform capability contracts;
- policies.

### Runtime

Coordinates execution:

- orchestration;
- scheduling;
- events;
- approvals;
- model routing;
- retries;
- recovery;
- background workers.

### Data

Provides persistence and synchronization:

- relational storage;
- Knowledge Graph;
- vector storage;
- object storage;
- migrations;
- backups;
- export;
- synchronization adapters.

CMMChat is the first-party conversational client/UI and is already under active interface development. It consumes the same versioned contracts available to alternative clients.

### Clients

Expose the platform:

- web client;
- desktop client;
- mobile client;
- CLI;
- external AI clients.

### Adapters

Connect external systems:

- model providers;
- storage providers;
- integrations;
- MCP;
- REST;
- Actions;
- plugins.

Dependencies must point inward toward stable contracts. Core and Runtime must not depend on CMMChat or any other client, provider, deployment target, or cloud service.

---

# 11.46 — Private Deployment Architecture

## Objective

Run CMM OS as a private personal platform rather than a publicly exposed service.

## Initial Topology

```text
Mac principal
├── CMM OS backend
├── databases
├── workers
├── local models through Ollama
├── web interface
└── encrypted backups and optional synchronization
```

The Mac principal is the initial authoritative runtime node.

The platform must support later migration to:

- Mac mini;
- another Mac;
- private server;
- NAS;
- VPS;
- hybrid deployment.

Migration must not require changing Core contracts or rebuilding user knowledge.

## Network Policy

- no mandatory public exposure;
- authenticated access only;
- encrypted transport;
- least-privilege services;
- configurable local-network access;
- configurable secure remote access;
- no direct database exposure;
- no unauthenticated administration endpoints.

---

# 11.47 — Mac Principal and Optional iCloud Integration

## Objective

Use the Mac principal as the execution node while allowing optional Apple-native synchronization and backup support.

## iCloud Roles

iCloud Drive or CloudKit may be used for:

- encrypted backups;
- exported Knowledge Packages;
- user documents;
- configuration snapshots;
- client synchronization metadata;
- selected portable state;
- recovery artifacts.

## Restrictions

iCloud must not be treated as:

- an application server;
- a Docker host;
- an Ollama runtime;
- a worker runtime;
- an API host;
- a replacement for the primary database engine.

CMM OS must remain functional when iCloud is unavailable.

Live SQLite files must never be synchronized directly through iCloud Drive.

Synchronization must use exported snapshots, application-level records, or an explicit synchronization protocol.

---

# 11.48 — Secure Remote Access and Context Synchronization

## Objective

Allow private use from iPhone and other Macs without exposing the platform as a public service.

## Remote Access

Supported approaches may include:

- private VPN;
- authenticated reverse proxy;
- device-bound access;
- private network overlay;
- secure tunnel;
- native client synchronization.

## Context Synchronization

Synchronization may include:

- active goals;
- workflow status;
- approvals;
- selected memories;
- Knowledge Packages;
- timeline events;
- notifications;
- configuration;
- client state.

## Requirements

- conflict detection;
- versioned records;
- resumable synchronization;
- encrypted transport;
- device authorization;
- selective synchronization;
- privacy-aware exclusions;
- offline client behavior;
- audit trail;
- recovery from partial synchronization.

The primary runtime remains authoritative until a later multi-node architecture is explicitly introduced.

---

# 11.49 — Safe Updates, Rollback, and Recovery

## Objective

Apply improvements and corrections without risking accumulated context or operational continuity.

## Update Flow

```text
Preflight
↓
Verified backup
↓
Compatibility check
↓
Migration dry run
↓
Update
↓
Health verification
↓
Acceptance tests
↓
Commit or rollback
```

## Requirements

- signed or verified release artifacts;
- schema compatibility checks;
- automatic pre-update backup;
- migration dry run;
- application rollback;
- data rollback when safe;
- forward-recovery procedure;
- version compatibility matrix;
- release channels;
- update logs;
- recovery runbook;
- clean-environment restore test.

Updates must separate:

- application code;
- configuration;
- secrets;
- user data;
- generated indexes;
- caches;
- backups.

No update may silently overwrite user knowledge, audit history, policies, or custom Domain Packs.

---

# 11.50 — Reusable Backend Interfaces

## Objective

Expose CMM OS capabilities through stable interfaces so the platform can serve its own clients and external AI systems without duplicating logic.

## Supported Interfaces

- REST API;
- streaming API;
- CMMChat through versioned application and streaming contracts;
- MCP server;
- OpenAI Actions-compatible endpoints;
- CLI;
- internal application services;
- event subscriptions.

## Interface Rules

All interfaces must reuse the same:

- authentication;
- authorization;
- permissions;
- PlatformCapability resolution;
- privacy policies;
- validation;
- routing;
- budgets;
- audit trail;
- error contracts;
- versioned schemas.

Clients must not bypass the Orchestrator, Model Gateway, Validation System, PlatformCapability resolution, canonical operations, or permission checks.

CMMChat is a first-party client, not an execution authority owner.

---

## 11.50 implementation state (Phase 11.50 / DP-150)

**Status:** `CLOSED_AFTER_INDEPENDENT_REAUDIT_V4_PASS`.

Independent Audit V1 examined the Phase 11.50 implementation and returned
`INDEPENDENT_AUDIT_V1=FAIL` with `BLOCKERS=0`, `MAJORS=5`, `MINORS=1`,
`DP_150=NOT_VERIFIED` and `CLOSURE_ELIGIBLE=NO`. Remediation V1 corrected exactly
those findings — the public owner escape hatch (MAJOR-01), exact canonical owner
types (MAJOR-02), canonical error preservation on the real client paths
(MAJOR-03), the attachment/response-event-stream capability truth (MAJOR-04) and
JSON-native public serialization (MAJOR-05) — plus the MINOR-01 evidence
discipline. `F11-021`, `DP-150` and `AT-DP-150` are unchanged.

Independent Re-audit V2 then examined that Remediation V1 state and returned
`INDEPENDENT_REAUDIT_V2=FAIL` with `BLOCKERS=0`, `MAJORS=1`, `MINORS=0`: V1
MAJOR-01/03/04/05 and MINOR-01 `VERIFIED_REMEDIATED`, with one residual defect
(MAJOR_V2_01) — the exact `client.backend` composition identity was enforced only
by the convenience builder and could be bypassed by a hand-built canonical
`ServiceBinding`, which registered a facade *subclass* successfully
(`CLIENT_BACKEND_SUBCLASS_HAND_BUILT_BINDING=ACCEPTED`). Remediation V2 corrects
exactly that defect at the authoritative boundary, generically and without
reopening the closed Phase 11.1 semantics.

```text
PHASE11_50=CLOSED
F11_021=VERIFIED_EXISTING
DP_150=VERIFIED_EXISTING
AT_DP_150=PASS
INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V2=FAIL
INDEPENDENT_REAUDIT_V3=FAIL
INDEPENDENT_REAUDIT_V4=PASS
BLOCKERS=0
MAJORS=0
MINORS=0
CLOSURE_ELIGIBLE=YES
```

Remediation V2 adds one reusable opt-in platform primitive — an explicit
`RuntimeContractMatch` mode on `ServiceBinding` (`INSTANCE_OF` remains the
default, `EXACT_TYPE` is the opt-in) plus a private contract-level
`__cmm_exact_runtime_contract__` marker that acts as a *minimum* semantic, so no
hand-built binding can omit the field or declare `INSTANCE_OF` to downgrade an
exact contract. `IntegrationServiceRegistry.register()` and `replace()` share the
one authoritative assertion path, an exact binding requires
`type(implementation) is runtime_contract` with no `isinstance` fallback, and an
exact-but-uncheckable contract fails closed. The `cmm.platform` core stays
generic: no service-ID or authority special case, no `cmm.client_backend` import
and no parallel policy registry. The canonical facade opts in, its binding
declares `exact_type`, and the existing builder exact-type check remains as
fail-fast convenience validation only.

```text
CLIENT_BACKEND_SUBCLASS_HAND_BUILT_BINDING=REJECTED
CLIENT_BACKEND_SUBCLASS_REPLACEMENT=REJECTED
EXACT_CLIENT_BACKEND_HAND_BUILT_BINDING=ACCEPTED
EXACT_RUNTIME_CONTRACT_CANNOT_BE_DOWNGRADED=PASS
OMITTED_MATCH_CANNOT_DOWNGRADE_EXACT_CONTRACT=PASS
INHERITED_INSTANCE_OF_SEMANTICS=PRESERVED
```

Independent Re-audit V3 then examined the Remediation V2 state and returned
`INDEPENDENT_REAUDIT_V3=FAIL` with `BLOCKERS=0`, `MAJORS=1`, `MINORS=0`: the one
residual defect was

```text
MAJOR_V3_01=
EXACT_CLIENT_BACKEND_IDENTITY_REMAINS_CALLER_ASSERTED_BECAUSE_A_HAND_BUILT_BINDING_CAN_REPLACE_THE_RUNTIME_CONTRACT_AND_BYPASS_THE_EXACT_MARKER
```

because the V2 rule derived the effective exactness from
`ServiceBinding.runtime_contract` — a field of the very binding being validated.
Keeping the canonical `client.backend` descriptor and service ID while replacing
only that field restored acceptance, on `register()` and equally on `replace()`:

```text
CLIENT_BACKEND_SUBCLASS_RUNTIME_CONTRACT_NONE=ACCEPTED
CLIENT_BACKEND_SUBCLASS_RUNTIME_CONTRACT_OBJECT=ACCEPTED
CLIENT_BACKEND_SUBCLASS_RUNTIME_CONTRACT_SUBCLASS=ACCEPTED
```

Remediation V3 makes the runtime identity of a configured canonical service
authoritative through the **existing Phase 11.1 configuration path** instead of
the caller-authored binding field:

```text
CompositionConfiguration.expected_contracts
        ↓
ServiceExpectation(service_id, contract, runtime_contract, runtime_contract_match)
        ↓
IntegrationServiceRegistry
        ↓
ServiceBinding must agree
        ↓
ApplicationContainer READY
```

`ServiceExpectation` gains the optional authoritative runtime policy while the
legacy `ServiceExpectation(service_id, contract)` construction keeps working
unchanged and imposes no exact-type requirement. The canonical
`client_backend_service_expectation()` declares `runtime_contract=ClientBackend`
with `runtime_contract_match=EXACT_TYPE`; the configured registry requires the
binding to declare exactly that contract and match rule and then judges the bound
implementation against the expectation, so `None`, `object` and the facade
subclass can no longer be substituted, omitted or downgraded on either
`register()` or `replace()`. A rebuilt descriptor carrying the canonical service
ID cannot bypass the expectation, because the lookup is by service identity. The
V2 `__cmm_exact_runtime_contract__` marker remains as defense in depth only.

`ApplicationContainer.build(...)` attaches `configuration.expected_contracts`
before any module contribution registers for a registry it creates, and attaches
them atomically to a caller-supplied pre-populated registry before READY, so a
pre-populated forged `client.backend` binding is rejected before
`ContainerState.READY` with the expectation, binding and freeze state untouched.
Attachment is monotonic and idempotent: an identical set is a no-op and a weaker,
removed or conflicting set fails closed. The platform core stays generic — no
service-ID or authority special case, no `cmm.client_backend` import, no parallel
registry, runtime-type map or container — and `cmm.client_backend.__all__` is
unchanged.

```text
CLIENT_BACKEND_SUBCLASS_RUNTIME_CONTRACT_NONE=REJECTED
CLIENT_BACKEND_SUBCLASS_RUNTIME_CONTRACT_OBJECT=REJECTED
CLIENT_BACKEND_SUBCLASS_RUNTIME_CONTRACT_SUBCLASS=REJECTED
CLIENT_BACKEND_SUBCLASS_REPLACEMENT_RUNTIME_CONTRACT_NONE=REJECTED
CLIENT_BACKEND_SUBCLASS_REPLACEMENT_RUNTIME_CONTRACT_OBJECT=REJECTED
CLIENT_BACKEND_SUBCLASS_REPLACEMENT_RUNTIME_CONTRACT_SUBCLASS=REJECTED
EXPECTED_RUNTIME_CONTRACT_CANNOT_BE_OMITTED=PASS
EXPECTED_EXACT_MATCH_CANNOT_BE_DOWNGRADED=PASS
REBUILT_CLIENT_BACKEND_DESCRIPTOR_CANNOT_BYPASS_EXPECTATION=PASS
REPLACEMENT_CANNOT_CHANGE_SERVICE_EXPECTATION=PASS
EXPECTATION_ATTACHMENT_ATOMIC=PASS
EXPECTATION_DOWNGRADE=REJECTED
IDENTICAL_EXPECTATION_RECONFIGURATION=IDEMPOTENT
PREPOPULATED_FORGED_CLIENT_BACKEND=REJECTED
CONTAINER_READY_WITH_FORGED_CLIENT_BACKEND=NO
EXACT_CLIENT_BACKEND_CONFIGURED_BINDING=ACCEPTED
LEGACY_SERVICE_EXPECTATION_CONSTRUCTION=PRESERVED
CANONICAL_RUNTIME_IDENTITY_SOURCE=SERVICE_EXPECTATION
BINDING_RUNTIME_CONTRACT_IS_AUTHORITY=NO
```

Independent Re-audit V4 then examined the exact Remediation V3 state at
`AUDITED_HEAD=a405e883edbafd04acad9d26f357ad54723041f7`,
`AUDITED_TREE=0bcd8f69710a28f3c372ac559afc17846a0baeb3` with bundle
`AUDITED_BUNDLE_SHA256=526f575a20524dccbc9b1901ee9f4fe4f7dfc34add47fd4ca420144a118aa194` and returned
`INDEPENDENT_REAUDIT_V4=PASS` with `BLOCKERS=0`, `MAJORS=0`, `MINORS=0`,
`F11_021=VERIFIED_EXISTING`, `DP_150=VERIFIED_EXISTING`, `AT_DP_150=PASS` and
`CLOSURE_ELIGIBLE=YES`. All Audit V1 findings and the V2/V3 residual findings are
`VERIFIED_REMEDIATED`. Final report: `docs/audits/phase-11.50-reusable-backend-interfaces-independent-reaudit-v4.md`; audit-report commit
`bc101c74aa7e29edceafc47e20e69ed816be7b6d`. Phase 11.50 is closed by this dedicated docs-only closure
commit.

`AT-DP-150` is extended in place with Scenario A3 — configuration-anchored
canonical `client.backend` identity — over real components and a real
`ApplicationContainer`; no new acceptance identifier is created.

The broad interface list above is the historical roadmap wording and is preserved
unchanged. Phase 11.50 implements a deliberately narrower, scoped slice of it —
the reusable first-party client seam — and reuses what Phase 11.3 and Phase 11.4
already closed:

| Historical roadmap item | Phase 11.50 disposition |
|---|---|
| REST API | already provided by the closed Phase 11.3 `cmm.api` HTTP/OpenAPI adapter; **reused, not duplicated**; regression-checked only |
| streaming API | already provided by the closed Phase 11.3 SSE response-event delivery; **reused**; `cmm.client_backend` reports its truth — `response_event_stream=available` — and never relabels it as token streaming, whose separate row stays `degraded` (Audit V1 MAJOR-04) |
| CMMChat through versioned application and streaming contracts | **implemented here as the seam**: `cmm/client_backend` provides the versioned, transport-neutral first-party facade (`CLIENT_BACKEND_INTERFACE_VERSION="1"`); CMMChat source is not modified (`CMMCHAT_CODE_CHANGES=NONE`) |
| MCP server | deferred — `PHASE11_51=NOT_IMPLEMENTED` |
| OpenAI Actions-compatible endpoints | deferred — `PHASE11_51=NOT_IMPLEMENTED` |
| CLI | already owned and closed by Phase 11.4; untouched by Phase 11.50 |
| internal application services | already provided by the closed Phase 11.3 `ApplicationGateway` and Phase 11.5 `ConversationService`; **reused, not duplicated** |
| event subscriptions | deferred; no new event bus and no subscription store is created |

Phase 11.50 adds exactly one new top-layer package, `cmm/client_backend`, and one
new Phase 11.1 service binding, `client.backend`. It introduces **no** new
execution, backend, session, routing or model authority, and creates no second
application gateway, conversation service, orchestrator, model gateway, provider
registry, model catalog, session store, conversation store, router, runtime,
engine, registry, repository, resolver, service locator, HTTP server or event
bus. The Model Gateway remains an internal canonical boundary and is never
exposed to a client as an escape hatch: after Audit V1 MAJOR-01 the facade
returns no live canonical owner at all, so the audited
`client.gateway.handle(...) -> health.get` bypass has no public route.

Model-boundary capability truth (Phase 11.21 reasoning effort, real
image/document input, provider token streaming and model-call cancellation) is
reported honestly as `boundary_only`, while the matching `end_to_end_*` rows
report the actual conversational truth. Establishing whether a narrow canonical
end-to-end bridge is missing for each of them is a separate post-11.50
inspection, per design §63.

See [`docs/reference/phase-11-reusable-backend-interfaces.md`](../reference/phase-11-reusable-backend-interfaces.md).

<!-- PHASE11_50_CLOSED_AFTER_INDEPENDENT_REAUDIT_V4_PASS -->

---

# 11.51 — MCP, REST, and Actions Adapters

## Objective

Provide thin adapters that allow Claude, ChatGPT, local clients, automations, and other compatible systems to use CMM OS safely.

## MCP Capabilities

Initial MCP tools may expose:

- search knowledge;
- retrieve a Knowledge Package;
- create or inspect goals;
- inspect workflows;
- request a validated operation;
- review approvals;
- inspect audit records;
- inspect authorized PlatformCapabilities and implementation availability;
- export authorized context.

## REST Capabilities

The REST API may expose:

```text
/api/v1/goals
/api/v1/workflows
/api/v1/knowledge
/api/v1/memory
/api/v1/domains
/api/v1/bots
/api/v1/capabilities
/api/v1/tools
/api/v1/models
/api/v1/evaluations
/api/v1/audit
/api/v1/exports
```

## Actions Compatibility

Actions-compatible endpoints must:

- use explicit schemas;
- expose only authorized operations;
- avoid unrestricted arbitrary execution;
- preserve provider-independent contracts;
- return structured errors;
- record every external invocation;
- enforce rate and budget limits.

Adapters must remain replaceable and must not contain domain logic. They may expose or implement PlatformCapabilities, but they must never grant capability authority or create a parallel executable registry.

---

# 11.52 — Skills and Plugin Packaging

## Objective

Package useful CMM OS capabilities as reusable skills or plugins for external assistants and development environments.

## Packaging Targets

- Claude skills;
- ChatGPT-compatible actions or GPT tools;
- MCP tool bundles;
- local assistant plugins;
- IDE assistant integrations;
- n8n nodes or workflow templates;
- standalone CLI commands.

## Package Contents

A package may include:

- manifest;
- operation schemas;
- PlatformCapability descriptors or requirements;
- prompts;
- validation rules;
- permissions;
- privacy requirements;
- Knowledge Package schema;
- examples;
- tests;
- version;
- compatibility metadata.

## Restrictions

A skill or plugin must not:

- contain secrets;
- silently broaden permissions;
- create an alternative capability/permission authority;
- create a second executable Tool Registry or Agent Runtime;
- bypass CMM OS validation;
- duplicate the primary memory store;
- couple the core to one assistant vendor;
- export restricted knowledge automatically;
- become the only usable form of a capability.

---

# 11.53 — Context Layer Mode

## Objective

Allow CMM OS to operate as a private context and validation layer behind another AI interface.

## Flow

```text
External assistant
↓
Authorized CMM OS interface
↓
Context resolution
↓
Knowledge Package
↓
Privacy and permission filtering
↓
Model or external-assistant execution
↓
Response validation
↓
Audit and optional memory update
```

## Capabilities

- context retrieval;
- portable Knowledge Packages;
- prompt-independent provenance;
- privacy filtering;
- response validation;
- provider comparison;
- model-independent memory;
- optional write-back;
- explicit approval before persistent updates.

Context Layer Mode must work even when the external assistant changes.

---

# 11.54 — Exit and Portability Strategy

## Objective

Ensure that accumulated knowledge, workflows, policies, and domain logic remain usable if CMM OS changes direction, a provider disappears, or the full platform is discontinued.

## Portable Assets

- Knowledge Packages;
- domain schemas;
- prompts;
- validation rules;
- workflows;
- operation definitions;
- benchmark suites;
- model policies;
- privacy policies;
- audit records;
- exported memory;
- documentation;
- skills and plugins;
- versioned Bot definitions;
- portable requested-capability policies without secrets or effective grants.

Portable Bot configuration must remain provider-independent. Credentials, cookies, operating-system grants, and privileged effective capability state are not portable assets; effective authority must be recomputed by the destination runtime.

## Exit Modes

```text
Full CMM OS platform
CMM OS as private backend
CMM OS as context layer
CMM OS as MCP server
CMM OS skills and plugins
Portable Knowledge Package archive
Standalone domain tools
```

## Requirements

- documented export formats;
- versioned schemas;
- provider-independent data;
- reproducible migrations;
- checksum verification;
- restore tests;
- no mandatory proprietary cloud;
- no provider lock-in;
- clear deprecation paths;
- preserved auditability.

Failure of the complete product must not invalidate the reusable infrastructure already built.

---


# 11.55 — Communication Profiles and Conversational Persona

## Objective

Allow CMM OS to present the same structured system result through configurable communication profiles without altering reasoning, policies, permissions, validation, confidence, or execution decisions.

Communication style is a presentation concern. It must remain independent from the Cognitive Layer, Agent Runtime, domain logic, model providers, routing, and operational policy.

## Architecture

```text
Structured System Result
        ↓
Communication Profile Resolver
        ↓
Response Renderer
        ↓
CLI / Web / Mobile / Voice / External Client
```

## Communication Profile Contract

```python
CommunicationProfile(
    id="calm_authority",
    display_name="Calm Authority",
    language="es-ES",
    register="formal",
    verbosity="concise",
    warmth="restrained",
    authority="high",
    emotional_expression="low",
    preferred_phrasing=[],
    prohibited_phrasing=[],
    address_policy={},
    channel_overrides={},
    fallback_profile="neutral",
    version="1.0",
    metadata={},
)
```

## Required Capabilities

- define versioned communication profiles;
- configure language, register, warmth, authority, verbosity, directness, and conversational rhythm;
- define preferred and prohibited phrasing;
- adapt presentation by client or channel;
- select profiles globally, per user, session, domain, or interaction;
- preserve the underlying structured result unchanged;
- expose the profile and version used to render each response;
- fall back safely to a neutral profile;
- support text clients and future voice clients;
- allow profiles to be exported as reusable configuration or skills.

## Separation of Responsibilities

Communication profiles may control:

- wording;
- sentence length;
- degree of formality;
- warmth;
- directness;
- use of the user's name;
- acknowledgement, warning, success, and decision phrasing;
- channel-specific formatting.

Communication profiles must not control:

- facts;
- conclusions;
- confidence or uncertainty;
- permissions;
- privacy;
- routing;
- budgets;
- approval requirements;
- action selection;
- validation decisions;
- memory updates;
- agent autonomy.

## Initial Profiles

### Neutral

Clear, professional, minimally styled, and always available as the fallback profile.

### Calm Authority

A restrained, precise, observant, and confident voice inspired by calm fictional machine interlocutors without copying protected dialogue or implying omniscience.

Characteristics:

- short and deliberate sentences;
- formal but natural Spanish;
- measured use of the user's name;
- calm presentation of risks;
- explicit distinction between facts, inference, and uncertainty;
- no artificial enthusiasm;
- no threats, manipulation, degradation, or false certainty.

## Auditability

Each rendered response must preserve metadata equivalent to:

```python
RenderedResponseMetadata(
    profile_id="calm_authority",
    profile_version="1.0",
    language="es-ES",
    channel="web",
    source_result_id="result-123",
    rendered_at="...",
)
```

The original structured result must remain available so the response can be reproduced or rendered through another profile.

## Preservation Validation

The renderer must verify that style transformation:

- preserves facts and qualifications;
- preserves uncertainty and warnings;
- does not remove approval requests;
- does not soften or exaggerate risks;
- does not introduce new claims;
- does not expose hidden reasoning or restricted information;
- remains compatible with the selected client.

## Completion Criteria

- versioned `CommunicationProfile` contract;
- profile registry and resolver;
- response renderer;
- neutral fallback;
- initial `calm_authority` profile;
- global, user, session, domain, interaction, and channel selection rules;
- rendered-response audit metadata;
- preservation validation;
- configuration interface;
- unit tests;
- integration tests;
- E2E validation across at least two clients;
- documentation;
- green global suite.

---

# 11.56 — External Audio Ingestion and Plaud MCP Integration

## Objective

Allow CMM OS to discover, import, transcribe, structure, and process audio recordings from Plaud through a replaceable MCP adapter while keeping the core ingestion pipeline independent from Plaud, MCP, and any concrete transcription provider.

Plaud is an initial external source, not a mandatory platform dependency.

## Architecture

```text
Plaud
  ↓
Plaud MCP Adapter
  ↓
External Audio Ingestion Pipeline
  ↓
Transcription Provider
  ↓
AudioResource + TranscriptResource
  ↓
Cognitive Layer
  ↓
Knowledge / Timeline / Memory
```

The same ingestion pipeline must support future sources such as uploaded files, watched folders, mobile clients, voice notes, and other recorder integrations.

## Resource Contracts

```python
AudioResource(
    id="resource-audio-123",
    source="plaud",
    external_id="plaud-recording-123",
    recording_started_at="...",
    duration_seconds=1800,
    checksum="...",
    storage_location="...",
    privacy={},
    provenance={},
    metadata={},
)
```

```python
TranscriptResource(
    id="resource-transcript-123",
    audio_resource_id="resource-audio-123",
    transcription_provider="...",
    language="es",
    text="...",
    segments=[],
    speakers=[],
    confidence=None,
    created_at="...",
    privacy={},
    provenance={},
    metadata={},
)
```

## Required Capabilities

- connect to Plaud through a replaceable MCP adapter;
- discover recordings through manual synchronization or scheduled polling;
- import recordings idempotently through external identifiers and checksums;
- preserve original audio and source metadata;
- select local or approved remote transcription through the Model Gateway;
- generate timestamped transcripts;
- support speaker diarization with graceful fallback;
- detect or configure language;
- preserve confidence and uncertainty per segment when available;
- resume interrupted imports and transcription jobs;
- retry transient failures without creating duplicates;
- expose ingestion and transcription status;
- version corrected transcripts without overwriting originals;
- link transcripts to timelines, sessions, people, domains, and Knowledge Packages;
- require human review before sensitive knowledge or memory updates;
- remain usable when Plaud or its MCP adapter is unavailable.

## Privacy and Security

Plaud recordings must default to `SENSITIVE` unless explicitly reclassified.

The pipeline must support `LOCAL_ONLY`, `LOCAL_PREFERRED`, and approved remote transcription; require explicit approval before sending sensitive audio remotely; avoid raw sensitive content in logs; protect credentials; apply independent retention and deletion policies to audio and transcripts; preserve provenance; and prevent automatic memory updates from unreviewed sensitive inferences.

## MCP Boundary

The Plaud MCP adapter may authenticate, list recordings, retrieve metadata and authorized audio, and expose synchronization health.

It must not write directly to memory or the Knowledge Store, bypass ingestion validation, choose privacy policy, select transcription models independently, or convert model output directly into facts.

## Completion Criteria

- provider-independent `AudioResource` and `TranscriptResource`;
- external-audio ingestion service;
- replaceable Plaud MCP adapter;
- manual and scheduled synchronization;
- idempotent import and duplicate prevention;
- resumable transcription jobs;
- local and approved remote transcription;
- timestamped segments;
- diarization with graceful fallback;
- language and confidence metadata;
- privacy, approval, retention, and deletion controls;
- transcript versioning and human correction;
- Cognitive Layer, Timeline, and Knowledge Package integration;
- structured audit records;
- unit, integration, and E2E tests;
- documentation;
- green global suite.

---

# 11.57 — Conversation Files, Global Artifact Library and Cross-Device Access

## Objective

Provide every conversation with an organized file workspace containing user-uploaded files and artifacts generated by models, tools, or workflows, while also exposing a global file library across conversations and authorized devices.

Files must remain accessible independently from the device that created or uploaded them.

## Conversation File Workspace

Each conversation must expose a dedicated `Files` tab containing:

- files uploaded by the user;
- files generated by a model;
- files generated by tools or workflows;
- derived versions;
- processing state;
- source-message links;
- preview and download actions.

The interface must distinguish clearly between:

```text
Uploaded by user
Generated by CMM OS
Generated by tool or workflow
```

## Global File Library

The platform must aggregate authorized files from all conversations and support:

- search;
- filters by conversation, domain, origin, format, date, author, and sensitivity;
- sorting;
- recent files;
- favorites or pinned files;
- source-conversation and source-message navigation;
- preview;
- individual and bulk download;
- deletion and retention controls;
- duplicate detection;
- storage-usage visibility.

## Artifact Contract

```python
ConversationArtifact(
    id="artifact-123",
    conversation_id="conversation-456",
    source_message_id="message-789",
    source_workflow_id=None,
    created_by="user|model|tool|workflow",
    filename="report.pdf",
    media_type="application/pdf",
    size_bytes=0,
    checksum="...",
    storage_key="...",
    version=1,
    status="available",
    sensitivity="SENSITIVE",
    created_at="...",
    metadata={},
)
```

## Preview and Download

Initial previews should support PDF, images, Markdown, plain text, source code, and common office documents when a safe renderer is available.

Downloads must support desktop and mobile browsers, authorized remote devices, resumable transfer when available, individual files, multiple-file archives, original files, and selected versions.

Artifact delivery must use authenticated backend access or short-lived signed download URLs. Clients must not receive permanent object-storage credentials.

## Cross-Device Availability

Artifacts must be stored in CMM OS object storage rather than only in temporary client state.

The platform must support access from the main Mac, iPhone, other authorized Macs or devices, encrypted transport, device authorization, permission-aware synchronization, selective offline availability, and recovery from interrupted synchronization.

## Versioning and Provenance

Regenerated or modified artifacts must create new versions rather than silently replacing prior files.

Every version must preserve its source conversation, source message or workflow, generating model or tool, checksum, creation time, transformation history, privacy classification, and deletion state.

## Privacy and Deletion

The system must enforce conversation, domain, and resource permissions; preserve privacy classifications; clarify whether deletion removes only a conversation link or the stored object; prevent orphaned sensitive objects; minimize audit payloads; and revoke access promptly when permissions change.

## Completion Criteria

- conversation-level `Files` tab;
- global file library;
- unified artifact contract;
- user, model, tool, and workflow origin metadata;
- source-message and source-conversation navigation;
- preview for initial supported formats;
- authenticated cross-device download;
- mobile-compatible access;
- artifact versioning;
- checksum and duplicate detection;
- privacy, retention, deletion, and audit controls;
- unit, integration, mobile-web, and E2E tests;
- documentation;
- green global suite.

---

# 11.58 — Conversation Import, Export and Supervised Memory Integration

## Objective

Allow CMM OS to import conversations from Claude, ChatGPT, and compatible Markdown exports, continue them inside CMM OS, export complete or selected conversations, and integrate candidate memory or knowledge only through supervised review.

## Architecture

```text
Claude / ChatGPT Markdown
        ↓
Conversation Importer
        ↓
Format Detection and Parsing
        ↓
Import Preview
        ↓
CMM OS Conversation
        ↓
Optional Memory and Knowledge Extraction
        ↓
Human Review
        ↓
Approved Updates
```

## Conversation Import

Initial imports must support Markdown exports from Claude and ChatGPT through replaceable format adapters.

The importer must:

- detect the source format when possible;
- preserve the original file and checksum;
- parse title, roles, messages, timestamps when present, code blocks, citations, and file references;
- create a new conversation or append to an existing one;
- preserve message order;
- distinguish imported messages from later CMM OS messages;
- support long conversations through bounded or resumable processing;
- detect duplicate and partial imports;
- expose a preview before persistence;
- allow correction of parsing errors;
- preserve source provider, format, importer version, and provenance;
- fail safely when the structure is ambiguous.

## Import Modes

```text
ARCHIVE_ONLY
CONTINUE_CONVERSATION
CONTINUE_AND_REVIEW_MEMORY
```

- `ARCHIVE_ONLY`: preserve the source as a consultable artifact without creating an active session.
- `CONTINUE_CONVERSATION`: create or extend a CMM OS conversation.
- `CONTINUE_AND_REVIEW_MEMORY`: continue the conversation and generate supervised memory and knowledge proposals.

## Supervised Memory and Knowledge Integration

```text
Imported Conversation
        ↓
Candidate Facts / Preferences / Events / Decisions
        ↓
MemoryUpdateProposal / KnowledgeUpdateProposal
        ↓
Accept / Reject / Edit / Merge
        ↓
Memory and Knowledge Store
```

The review interface must distinguish user statements, assistant statements, quoted third-party content, inferred information, uncertain or contradictory claims, already-known information, and sensitive candidates.

The system must not automatically persist model hypotheses or hallucinations, unconfirmed inferences, quoted third-party claims, jokes or role-play, context-dependent statements without sufficient scope, stale information, sensitive inferences, or duplicates.

Each accepted update must preserve provenance back to the imported conversation, source message, original file, and review decision.

## Conversation Export

The interface must support exporting:

- the complete conversation;
- a contiguous message range;
- individually selected messages;
- user messages only;
- assistant messages only;
- both roles.

Initial formats:

- Markdown;
- PDF.

Export options must include title, timestamps, author labels, sources, citations, attachments, generated artifacts, code blocks, tables, conversation metadata, page layout, and a table of contents for PDF when appropriate.

The user must receive a preview of the selected scope before generation.

## Export Contract

```python
ConversationExportRequest(
    conversation_id="conversation-123",
    scope="complete|range|selection",
    message_ids=[],
    role_filter="all|user|assistant",
    format="markdown|pdf",
    include_sources=True,
    include_attachments=False,
    include_generated_artifacts=False,
    metadata={},
)
```

## Validation, Privacy and Portability

Import and export must validate format and schema, preserve provenance and ordering, enforce permissions and sensitivity, exclude unselected or unauthorized content, detect duplicates and conflicts, support cancellation and rollback, keep provider-specific parsing outside the core, and avoid treating imported assistant output as trusted knowledge.

## Completion Criteria

- provider-independent conversation-import contract;
- Claude Markdown adapter;
- ChatGPT Markdown adapter;
- source-format detection;
- original-file preservation and checksums;
- archive, continuation, and memory-review modes;
- import preview and parsing correction;
- duplicate and partial-import detection;
- continuation inside CMM OS;
- supervised memory and knowledge proposals;
- accept, reject, edit, and merge review actions;
- complete and selective chat export;
- Markdown and PDF renderers;
- export preview;
- role filtering;
- optional inclusion of authorized files and artifacts;
- unit, adapter-contract, memory-integration, and E2E tests;
- documentation;
- green global suite.

---

# Phase 10 Domain Integration Addendum — Health, Mental Health and Neurodivergence

## Objective

Integrate the canonical Phase 10 sibling Domain Packs `domain:health`, `domain:mental-health`, and `domain:neurodivergence` through the existing Phase 11 platform services without creating domain-specific platform infrastructure.

Phase 11 must consume the Domain Intelligence contracts generically. It must not introduce a separate Health router, Mental Health router, Neurodivergence router, independent domain memory, domain-specific orchestration runtime, or second Knowledge Model.

## Canonical Domain Identities

```text
domain:health             -> HealthProfile
domain:mental-health      -> MentalHealthProfile
domain:neurodivergence    -> NeurodivergenceProfile
```

The three domains are siblings.

Health remains authoritative for clinical diagnosis status, medication, treatment, medical tests and specialists, medical risk and red flags, and clinical documentation.

Mental Health remains authoritative for its non-clinical emotional and therapy-continuity specialization.

Neurodivergence remains authoritative for its neurodevelopmental evidence, certainty-state, longitudinal, functional, and differential-overlap specialization.

Supporting domains receive only the minimum authorized projection required for the active purpose.

## Orchestrator, Domain Router and Context Resolver

The existing Orchestrator, Domain Router, and Context Resolver must:

- resolve `health`, `mental-health`, and `neurodivergence` as distinct canonical domain identities;
- select one primary domain and zero or more supporting domains;
- preserve primary/supporting identity through orchestration results and Domain Trace references;
- apply the existing restrictive permission intersection before cross-domain context is exposed;
- preserve provenance, epistemic kind, temporal validity, uncertainty, sensitivity, and source-domain authority;
- prohibit a supporting domain from widening permissions;
- prohibit a supporting domain from promoting a hypothesis or inference to a stronger epistemic status;
- avoid defaulting Mental Health requests to Health merely because the content is emotionally or psychiatrically adjacent;
- avoid defaulting Neurodivergence requests to Health merely because medication or clinical evidence may be relevant;
- route clinical diagnosis, treatment, medication, and medical-risk authority to Health when those semantics are required.

Representative compositions:

```text
primary=domain:mental-health
supporting=[domain:relationships, domain:neurodivergence, domain:health]
```

```text
primary=domain:neurodivergence
supporting=[domain:health, domain:mental-health]
```

```text
primary=domain:health
supporting=[domain:mental-health, domain:neurodivergence]
```

No supporting domain is implied merely because it is listed as a possible composition.

## Configuration and Domain Lifecycle

All installed domains, including Mental Health and Neurodivergence, must be supported by the existing domain configuration and lifecycle surfaces:

- discovery;
- registration;
- enablement and disablement;
- version and compatibility status;
- health checks;
- per-domain permissions;
- per-domain privacy and provider policy;
- per-domain autonomy constraints;
- Domain Pack installation and update state.

Disabling one sibling domain must not disable the others.

## Timeline

Timeline events must retain the canonical domain identity that owns the event or derived interpretation.

The Timeline must:

- filter separately by `health`, `mental-health`, and `neurodivergence`;
- preserve source-domain identity for cross-domain projections;
- avoid silently reclassifying an existing Health event as Mental Health or Neurodivergence;
- support authorized multi-domain references without duplicating the underlying event;
- preserve sensitivity and permission boundaries in every view.

## Search and Knowledge Explorer

Search and Knowledge Explorer must:

- expose canonical domain facets for `health`, `mental-health`, and `neurodivergence`;
- keep the three result identities distinct;
- apply authorization before snippets, previews, facets, counts, or related-item expansion are returned;
- preserve epistemic status and provenance in results;
- avoid treating absence from an unauthorized domain as confirmed absence;
- support explicit cross-domain queries only through existing permission-filtered composition.

A `SearchResult.domain` value that refers to the Health Domain must use `health`, not `medical`.

## Memory Workspace and Knowledge

Memory Workspace and Knowledge interfaces must reuse the shared Phase 8 and Phase 10.18 contracts.

They must:

- preserve domain references without creating per-domain copies of the Knowledge Store;
- show the source domain of claims, hypotheses, decisions, and corrections;
- keep sensitive Mental Health and Neurodivergence inferences non-persistent unless the applicable memory permission and approval permit persistence;
- preserve revision, invalidation, temporal succession, contradiction, and provenance history;
- prohibit silent migration or duplication of existing Health knowledge into either new domain;
- keep cross-domain projections purpose-limited and revocable.

## Workflows and Operations

Workflow routing and templates must be able to target the two new Domain Packs through the existing Workflow Engine.

Examples include:

- Mental Health therapy-session preparation and post-session processing;
- Mental Health therapy-transcript review under sensitive-data controls;
- Neurodivergence longitudinal evidence organization;
- Neurodivergence assessment-preparation workflows;
- mixed-domain workflows in which Health supplies authorized medication or diagnosis-state context.

Workflow selection must not change domain authority, permissions, or epistemic status.

## Model Gateway and Routing

Model Gateway and Routing Policy Engine must support all installed domains generically, including the two new domains.

For `domain:mental-health` and `domain:neurodivergence`:

- default domain privacy is `SENSITIVE`;
- provider/model routing must not weaken the effective privacy policy;
- remote egress requires the same permission and provider-policy checks as any other sensitive domain;
- model selection may use domain benchmark and quality evidence from Phase 10;
- provider selection must not change which domain is authoritative;
- routing metadata must remain outside private chain-of-thought content.

Health continues to use canonical `domain="health"` in model requests.

## Model Evaluation and Continuous Provider Evaluation

The Model Evaluation Framework and continuous provider evaluation must support evaluation by canonical domain.

The platform must be able to:

- evaluate models separately for Health, Mental Health, and Neurodivergence;
- consume each Domain Pack's benchmark suites and quality metrics;
- compare provider/model performance without flattening domain-specific safety or epistemic requirements;
- block a provider/model combination that violates effective domain privacy or minimum quality policy;
- preserve evaluator version, model version, provider, benchmark, cost, latency, and blocking-failure evidence.

A strong result in one sibling domain must not be treated as evidence of equivalent quality in another.

## Cost Management and Dashboards

Cost and model-usage dashboards must support canonical by-domain attribution for:

```text
health
mental-health
neurodivergence
```

The platform must keep domain identity separate when reporting requests, tokens, latency, cache use, provider, model, cost, fallback, validation failures, and blocked egress.

Sensitive content itself must not be copied into cost telemetry.

## Knowledge Package Export and Portability

Knowledge Package export must:

- preserve the canonical source domain;
- apply the Domain Knowledge Package schema selected by Phase 10;
- preserve privacy, provenance, epistemic status, contradictions, uncertainty, and temporal validity;
- exclude unauthorized supporting-domain content;
- preserve restrictive permission intersection for composed packages;
- avoid provider-specific domain formats.

Mental Health and Neurodivergence exports remain `SENSITIVE` unless an explicit, authorized policy produces a more restrictive result.

## Audit and Traceability

Phase 11 audit and trace surfaces must make it possible to determine:

- the resolved primary domain;
- supporting domains;
- why each domain participated;
- which permission decisions authorized cross-domain context;
- which Knowledge Package and domain schema were used;
- which provider/model routing decision applied;
- which privacy policy was effective;
- which domain benchmark/evaluation evidence influenced model selection;
- which external egress occurred;
- which persistent updates were proposed, approved, rejected, or applied.

Audit records must retain IDs and safe categorical facts rather than duplicating sensitive source content or private reasoning.

## Required E2E Domain-Integration Scenarios

Phase 11 E2E validation must include at least these scenarios:

1. **Mental Health routing isolation**
   An ordinary emotional or therapy-continuity request resolves to `domain:mental-health` and does not inherit Health clinical presentation or clinical authority by default.

2. **Neurodivergence minimized Health projection**
   A Neurodivergence request resolves to `domain:neurodivergence`; Health data is exposed only when authorized and only as the minimum purpose-required projection.

3. **Mixed sibling-domain composition**
   A request requiring multiple sibling domains selects exactly one primary domain plus explicit supporting domains, applies restrictive permission intersection, and preserves source-domain epistemic authority.

4. **Search, Timeline and dashboard identity**
   Search results, Timeline views, Knowledge Explorer facets, model-usage records, and cost attribution keep `health`, `mental-health`, and `neurodivergence` distinct without duplicating underlying knowledge.

5. **Sensitive provider-routing enforcement**
   A provider/model route that would weaken `SENSITIVE` privacy for Mental Health or Neurodivergence is rejected or rerouted according to existing policy, with the decision visible in audit metadata.

These scenarios extend the existing Phase 11 integration test surface. They do not introduce a separate test framework or runtime.

## Completion Constraint

Phase 11 integration is incomplete if either new Domain Pack requires a parallel platform subsystem to function.

The correct integration path is always:

```text
existing Phase 11 service
        +
canonical Phase 10 Domain Pack contracts
        +
existing permissions / privacy / validation
```

not:

```text
new domain-specific platform stack
```

---

# Version Plan

## 11.1 — Integration Core

### Objective

Connect all components through contracts and an application container.

### Deliverables

- Application Container;
- Service Registry;
- public contracts;
- configuration;
- service composition;
- basic integration tests.

### Outcome

CMM OS will be able to start as a single application and verify that all components are compatible.

---

## 11.2 — Orchestration Backend

### Objective

Build the Orchestrator, API, and application services.

### Deliverables

- Orchestrator;
- Intent Resolver;
- Context Resolver;
- Domain Router;
- Agent Router;
- API;
- application services;
- error contracts;
- initial events.

### Outcome

A request will be able to traverse the complete system and return a structured response.

---

## Vertical Slice milestone

Vertical Slice milestone — deferred integration milestone; not the canonical
Phase 11.3 identifier. The canonical Phase 11.3 is the Application Backend
defined above (`11.3 — Application Backend`, requirement `F11-017`, Design Point
`DP-103`); this historical version-summary entry is preserved unnumbered so it
cannot create a second Phase 11.3 or a duplicate subphase identifier.

### Objective

Complete the first functional end-to-end flow.

### Mandatory Flow

```text
User Request
↓
Session
↓
Orchestrator
↓
Domain
↓
Cognitive Layer
↓
Response or Plan
↓
Operation
↓
Validation
↓
Memory Update
↓
User Response
```

The vertical slice must include:

- one domain;
- one profile;
- one operation;
- one validation policy;
- one approval;
- persistence;
- observability;
- a minimal interface.

### Outcome

CMM OS will operate as an integrated product for the first time.

---

## Historical version-plan entry — Conversational Product

### Objective

Build the complete conversational interface.

### Deliverables

- conversational UI;
- sessions;
- streaming;
- attachments;
- questions;
- sources;
- actions;
- approvals;
- history.

### Outcome

The user will be able to use CMM OS through natural conversation.

---

## 11.5 — Operational Workspace

Historical version-plan entry — deferred integration summary; not the canonical
Phase 11.5 identifier. The canonical Phase 11.5 is the Conversational Interface
defined above (`11.5 — Conversational Interface`, requirement `F11-019`, Design
Point `DP-105`); this historical version-summary entry is preserved unrenumbered
so it cannot create a second Phase 11.5 or a duplicate subphase identifier.

### Objective

Add operational control surfaces.

### Deliverables

- Goal Workspace;
- Workflow Manager;
- Review Center;
- notifications;
- recent activity.

### Outcome

The user will be able to supervise goals, workflows, and actions.

---

## 11.6 — Knowledge Workspace

### Objective

Make memory and knowledge navigable.

### Deliverables

- Timeline;
- Knowledge Explorer;
- Memory Workspace;
- global search;
- contradictions;
- provenance;
- temporal validity.

### Outcome

The user will be able to review what CMM OS knows and control its memory.

---

## 11.7 — Platform Services

### Objective

Add the capabilities required for secure and durable operation.

### Deliverables

- authentication;
- authorization;
- permissions;
- secrets;
- encryption;
- migrations;
- backups;
- import;
- export;
- audit trail.

### Outcome

CMM OS will be able to maintain real data with operational guarantees.

---

## 11.8 — Extensibility

### Objective

Open the platform to new capabilities.

### Deliverables

- Plugin System;
- Plugin SDK;
- Model Gateway;
- adapters;
- n8n;
- external integrations;
- public events.

### Outcome

CMM OS will be extensible without modifying the core.

---

## 11.9 — Reliability and Observability

### Objective

Prepare the system for real failures.

### Deliverables

- logs;
- metrics;
- traces;
- health checks;
- alerts;
- recovery;
- circuit breakers;
- resilience tests;
- optimization.

### Outcome

CMM OS will be able to diagnose and recover from failures.

---

## 11.10 — Product Hardening

### Objective

Complete security, performance, testing, and installation experience.

### Deliverables

- threat model;
- security audit;
- E2E tests;
- load tests;
- accessibility;
- documentation;
- Docker;
- clean installation;
- update;
- restore.

### Outcome

CMM OS will be ready for a release candidate.

---

## 11.11 — Stable Release

### Objective

Publish the first stable CMM OS release.

### Deliverables

- validated release candidate;
- globally green suite;
- tested migrations;
- verified backups;
- final documentation;
- signed artifacts;
- SBOM;
- changelog;
- stable version.

### Outcome

CMM OS will stop being an experimental project and become an operational personal platform.

---

# Mandatory Vertical Slices

The phase must not be developed by completing every technical layer first and postponing integration until the end.

Every block must include:

```text
Interface
↓
Application Service
↓
Orchestrator
↓
Domain / Agent
↓
Cognitive Layer
↓
Operation
↓
Validation
↓
Persistence
↓
Observability
↓
Test
```

## Initial Slices

### Slice 1 — Contextual Query

The user asks a question and the system:

- creates a session;
- loads context;
- selects a domain;
- reasons;
- returns sources;
- persists the result.

### Slice 2 — Persistent Goal

The user creates a goal and the system:

- registers it;
- defines criteria;
- generates next actions;
- creates a review;
- maintains state.

### Slice 3 — Workflow with Approval

The system:

- plans;
- executes reversible actions;
- reaches a sensitive action;
- requests approval;
- pauses;
- resumes;
- executes;
- validates;
- completes.

### Slice 4 — Contradictory Knowledge

The system:

- loads two sources;
- detects a contradiction;
- preserves both versions;
- requests resolution;
- updates knowledge without losing provenance.

### Slice 5 — Recovery

The system:

- starts a workflow;
- encounters an integration failure;
- applies retry;
- pauses;
- restarts;
- recovers state;
- continues.

---

# Non-Functional Requirements

## Stability

- recoverable workflows;
- idempotent operations;
- structured errors;
- safe migrations;
- rollback;
- verified backups.

## Security

- least privilege;
- protected secrets;
- encryption;
- sandbox;
- audit trail;
- human approval;
- data policies.

## Privacy

- local execution;
- control over remote models;
- sensitivity;
- retention;
- export;
- forgetting;
- transparency.

## Performance

- progressive response;
- streaming;
- caching;
- limits;
- budgets;
- indexed search;
- controlled degradation.

## Extensibility

- contracts;
- plugins;
- adapters;
- events;
- versioning;
- SDK.

## Observability

- logs;
- metrics;
- traces;
- health checks;
- alerts;
- audit trail.

## Usability

- natural conversation;
- visible state;
- understandable errors;
- clear approvals;
- consistent navigation;
- human control.

---

# Design Principles

## API-First

Every important capability must be available through the API before depending on the UI.

## Local-First

The platform must be able to operate locally without mandatory reliance on external providers.

## Human-in-Control

Sensitive decisions must remain under human supervision.

## Explicit State

Every goal, workflow, session, operation, and approval must have an explicit and persistent state.

## Structured Results

Components must not communicate through free-form text when a structured contract exists.

## Traceability

Every relevant conclusion, action, and update must be related to its sources and events.

## Reversibility

Operations must be reversible whenever technically possible.

## Progressive Autonomy

Autonomy must be expanded through policies and never through implicit behavior.

## No Silent Knowledge Mutation

Knowledge must not be modified silently or without preserving versions.

## No Hidden Side Effects

Every side-effecting operation must be explicit, recorded, and observable.

## No Architectural Duplication

Interfaces and domains must not rebuild capabilities already present in the core.

---

# Dependencies

Phase 11 depends on previous phases providing functional and stable contracts.

## Phases 0–6

- kernel;
- planning;
- semantic engines;
- execution;
- memory;
- Knowledge Graph;
- operations;
- protocols.

## Phase 7

- Validation Pipeline;
- policies;
- commit gate;
- structured results.

## Phase 8

- resources;
- Knowledge Model;
- rules;
- profiles;
- gap analysis;
- questions;
- traceability;
- cognitive sessions.

## Phase 9

- goals;
- Agent Runtime;
- observation;
- planning;
- autonomy;
- approvals;
- recovery;
- evaluation.

## Phase 10

- domains;
- specialized profiles;
- rules;
- resources;
- operations;
- workflows;
- permissions.

Phase 11 may introduce adapters or facades, but it must not address structural deficiencies from previous phases through duplication.

When a blocking deficiency is detected, it must be corrected in the original component while preserving the integration contract.

---

# Initially Out of Scope

The first stable release does not need to include:

- unrestricted autonomy;
- autonomous modification of the core without approval;
- massive multi-agent coordination;
- continuous weight learning;
- in-house model training;
- large-scale distributed infrastructure;
- a public plugin marketplace;
- a native mobile application;
- complete enterprise multi-user support;
- geographic replication;
- multi-node execution;
- self-replication;
- self-publishing;
- autonomous medical, legal, or financial decisions.

These capabilities may be developed after the platform has been stabilized.

---

# Global Completion Criteria

## Architecture

- components integrated through stable contracts;
- Application Container;
- Service Registry;
- Orchestrator;
- Event System;
- versioned contracts;
- no circular dependencies.

## Product

- conversational interface;
- configurable communication profiles;
- neutral and Calm Authority presentation profiles;
- Goal Workspace;
- Workflow Manager;
- Review Center;
- Timeline;
- Knowledge Explorer;
- Memory Workspace;
- Configuration Center;
- global search;
- notifications.

## Backend

- API;
- CLI;
- streaming;
- sessions;
- persistence;
- idempotency;
- structured errors;
- concurrency control.

## Cognition and Agents

- integrated Cognitive Layer;
- integrated autonomous agent;
- domain selection;
- reasoning-profile selection;
- communication-profile selection;
- response rendering with semantic preservation;
- gap analysis;
- questions;
- workflows;
- evaluation;
- memory update.

## Security

- authentication;
- authorization;
- permissions;
- secrets;
- encryption;
- sandbox;
- human approval;
- audit trail;
- threat model;
- security tests.

## Data

- relational storage;
- Knowledge Graph;
- vector store;
- object storage;
- migrations;
- backups;
- restore;
- import;
- export;
- retention.

## Extensibility

- Plugin System;
- SDK;
- Model Gateway;
- Provider Registry;
- Routing Policy Engine;
- Model Evaluation Framework;
- Response Validation;
- Cost Management Layer;
- consumption modes;
- model and cost dashboard;
- continuous provider evaluation;
- provider cache and prompt optimization;
- Knowledge Package export;
- model usage audit;
- reusable backend interfaces;
- MCP, REST, and Actions adapters;
- skills and plugin packaging;
- Context Layer Mode;
- exit and portability strategy;
- adapters;
- n8n;
- integrations;
- public events.

## Operations

- Docker;
- per-environment configuration;
- health checks;
- logs;
- metrics;
- traces;
- alerts;
- recovery;
- updates;
- private deployment;
- Mac principal runtime;
- optional iCloud synchronization;
- secure remote access;
- synchronization recovery;
- verified rollback.

## Quality

- unit tests;
- integration tests;
- contract tests;
- E2E tests;
- security tests;
- resilience tests;
- load tests;
- clean installation;
- upgrade;
- downgrade;
- globally green suite.

## Documentation

- installation;
- usage;
- architecture;
- API;
- plugins;
- security;
- operations;
- recovery;
- contribution;
- release.

## Release

- stable version;
- reproducible artifacts;
- tested migrations;
- verified backup;
- SBOM;
- changelog;
- final documentation.

---

# 11.59 — Bot Identity and Configuration Layer

## Status

Planned. This subphase is architecturally designed but not yet implemented, independently audited, or closed.

## Objective

Introduce a first-class user-facing Bot abstraction without duplicating the Phase 9 Agent Runtime or any canonical execution authority.

## Core Boundary

```text
Bot
= product identity and configuration

Agent
= persistent execution/runtime entity

Bot != Agent
```

A Bot may define or reference identity, instructions, Communication Profile, model/routing policy, Domain context, knowledge scope, memory scope, requested PlatformCapabilities, autonomy preference within the canonical ceiling, optional Agent binding, and version/lifecycle state.

## Bot Modes

```text
CONVERSATIONAL
TOOL_ENABLED
AGENT_BACKED
```

- `CONVERSATIONAL`: normal conversation with no persistent Agent requirement.
- `TOOL_ENABLED`: may request authorized PlatformCapabilities without becoming an Agent.
- `AGENT_BACKED`: presents a user-facing identity while execution is delegated to an existing canonical Phase 9 Agent.

## Authority Invariants

A Bot must never own a second Agent Runtime; grant effective permissions; increase canonical autonomy or budgets; suppress approvals; bypass Domain permissions, canonical operations, or validation; activate Computer Use merely through Agent binding; or persist credentials, API keys, refresh tokens, cookies, operating-system authorization tokens, or other secrets.

Imported Bot configuration carries requested behavior only. Effective privileged authority must be recomputed by CMM OS.

## CMMChat Product Surface

CMMChat is the first-party client/UI expected to expose the Bot workspace. Its current interface development is independent from implementation of this runtime contract.

CMMChat may create, edit, display, import, export, and bind Bots through versioned application contracts, but CMM OS remains authoritative for runtime policy and execution.

## Design Point

`DP-059` — CMM OS must support a first-class, versioned, provider-independent Bot definition that remains distinct from Agent, Domain, Operation, PlatformCapability, ToolImplementation, and model provider, with optional Agent binding that cannot grant execution authority.

## Future Connected Acceptance

`AT-DP-059` is planned and not yet implemented. It must eventually prove through canonical or official in-memory components that conversational, tool-enabled, and Agent-backed Bots preserve all authority boundaries, invalid bindings fail closed, Computer Use is not implied, serialization excludes secrets, and versioned definitions round-trip deterministically.

---

# 11.60 — Platform Capability Catalog and Tool Resolution

## Status

Planned. This subphase is architecturally designed but not yet implemented, independently audited, or closed.

## Objective

Introduce provider-independent platform capability descriptors and most-restrictive capability resolution without creating a second executable Tool Registry.

## Core Distinctions

```text
PlatformCapability
!= DomainCapability
!= ToolImplementation
!= Operation
```

`PlatformCapability` describes a stable functional ability; `DomainCapability` retains existing Phase 10 specialization semantics; `ToolImplementation` is replaceable; `Operation` remains the canonical executable contract.

## PlatformCapabilityCatalog

The catalog is descriptive/resolutive. It may register and resolve descriptors, report availability, expose compatible implementation references, and surface risk/privacy/approval metadata.

It must not execute tools, grant permissions, own Agent runtime state, approval state, autonomy, budgets, secrets, or replace the canonical Operation Registry.

## Effective Capability Resolution

```text
Bot requested capabilities
∩ user policy
∩ session policy
∩ Domain permissions
∩ resource permissions
∩ privacy policy
∩ sensitivity rules
∩ integration availability
∩ operation availability
∩ autonomy ceiling
∩ budget limits
∩ approval policy
= effective capability set
```

Explicit deny wins. Sensitive or mutating capability with missing authority fails closed. Domain policy, Agent binding, model/provider output, and fallback may never widen effective authority.

## Tool Resolution

```text
PlatformCapability
↓
effective capability resolution
↓
compatible implementation candidates
↓
policy-compatible implementation
↓
canonical Operation
↓
canonical Runtime / Execution
```

## Design Point

`DP-060` — CMM OS must expose a provider-independent Platform Capability Catalog that describes and resolves effective capability availability without executing capabilities directly or replacing the canonical Operation Registry.

## Future Connected Acceptance

`AT-DP-060` is planned and not yet implemented. It must eventually prove that requested capability never implies authorization, deny wins, unavailable implementations remain unavailable, approval-required state is not executable authority, execution uses the canonical operation/runtime path, no second executable registry exists, and concrete implementation replacement preserves the PlatformCapability contract.

---

# 11.61 — Web, Browser and Computer Use

## Status

Planned. This subphase is architecturally designed but not yet implemented, independently audited, or closed.

## Objective

Introduce Web Search, Browser, authenticated-browser access, and Computer Use as separate independently authorized PlatformCapabilities with progressively stronger safety requirements.

## Capability Separation

```text
web.search
!= browser.navigate
!= browser.read_authenticated
!= computer.use
```

Granting one capability never implicitly grants another.

## Web Search

`web.search` supports authorized discovery and source retrieval. It does not imply browser control, authenticated sessions, filesystem mutation, arbitrary network access, or Computer Use.

## Browser

`browser.navigate` and `browser.read` support controlled navigation and page inspection. Authenticated browser access requires separate authority through `browser.read_authenticated` or a later equivalent capability and must preserve scoped session/origin access, credential isolation, audit, human takeover, and approval for sensitive side effects.

## Computer Use

`computer.use` is high impact and requires explicit fail-closed authorization, application/resource scope, least privilege, visible active state, cancellation, human takeover, canonical approval for sensitive or irreversible effects, credential isolation, audit, timeout/recovery, validation after mutations where applicable, and no activation merely because a Bot is Agent-backed.

## Human-in-the-Loop State

```text
RUNNING_AUTOMATED
WAITING_FOR_HUMAN
HUMAN_CONTROL
RESUMING_AUTOMATION
COMPLETED
FAILED
CANCELLED
```

Automated resume after human control must recompute effective authority.

## Provider Independence

Concrete implementations may later include native browser adapters, OpenBot, Tencent BrowserSkill, platform Computer Use providers, remote desktop adapters, or other local/remote automation runtimes. No concrete implementation becomes the core contract.

## Design Point

`DP-061` — Web Search, Browser, authenticated-browser access, and Computer Use must remain separate independently authorized capabilities, with Computer Use explicitly scoped, cancellable, auditable, human-takeover capable, and subject to stronger canonical approval rules.

## Future Connected Acceptance

`AT-DP-061` is planned and not yet implemented. It must eventually prove independent authorization of Web, Browser, authenticated-browser, and Computer Use; no Agent-binding escalation; canonical approval for sensitive actions; human handoff, cancellation, resume revalidation, credential isolation, canonical audit/event evidence, and implementation-independent semantics.

---

# Final Acceptance Test

The phase will be considered complete when CMM OS can reliably execute the following scenario:

1. The user starts CMM OS locally through Docker.
2. The system validates configuration, storage, models, and migrations.
3. The user opens the conversational interface.
4. The user submits a request related to one of their domains.
5. The Orchestrator identifies the intent.
6. It loads the session and relevant context.
7. It selects the domain and reasoning profile.
8. The Cognitive Layer distinguishes facts, inferences, and uncertainty.
9. It detects missing information.
10. It asks a question.
11. The user responds.
12. The system creates a goal.
13. It generates a workflow.
14. It executes a reversible operation.
15. It validates the result.
16. It reaches a sensitive action.
17. It creates an approval request.
18. The user reviews and approves it.
19. The agent continues.
20. An integration failure occurs.
21. The system retries.
22. It persists state.
23. The application is restarted.
24. The workflow is recovered.
25. The operation completes.
26. The result is validated.
27. The goal is marked as completed.
28. Memory is updated.
29. The Knowledge Graph preserves provenance.
30. The Timeline records the event.
31. The user can review the structured reasoning.
32. The system resolves the active communication profile.
33. The response is rendered through that profile without changing facts, uncertainty, warnings, or approvals.
34. The user can switch to the neutral profile and reproduce the response from the same structured result.
35. Logs, metrics, and traces show the entire path.
36. A backup is created.
37. The backup is successfully restored in a clean environment.
38. The global suite remains green.
39. The user opens the Bot workspace through a first-party client such as CMMChat.
40. A `TOOL_ENABLED` Bot requests `web.search` without becoming an Agent.
41. Effective capability resolution permits Web Search while independently denying Browser and Computer Use.
42. Computer Use is explicitly granted for a scoped target and a sensitive effect reaches the canonical approval path.
43. The Computer Use session enters human takeover and recomputes authority before automated resume.
44. An `AGENT_BACKED` Bot resolves through the canonical Agent Registry without receiving wider permissions, autonomy, budgets, or approvals.
45. A concrete tool implementation is replaced without changing the Bot or PlatformCapability contract.
46. Export/import preserves portable Bot configuration while excluding secrets and privileged effective authority.

---

# Phase Outcome

CMM OS will stop being a set of specialized engines and become a complete personal platform capable of:

- understanding;
- remembering;
- relating knowledge;
- reasoning;
- preserving uncertainty;
- detecting missing information;
- asking questions;
- maintaining goals;
- planning workflows;
- executing actions;
- validating results;
- requesting approval;
- recovering from failures;
- coordinating domains;
- integrating with external services;
- exposing configurable user-facing Bots without duplicating the Agent Runtime;
- resolving provider-independent PlatformCapabilities through canonical policy and operations;
- supporting independently authorized Web Search, Browser, and supervised Computer Use;
- serving CMMChat as a first-party client without coupling Core/Runtime to its implementation;
- operating locally;
- presenting results through configurable communication profiles;
- preserving meaning while adapting language, register, and channel;
- selecting local or remote models without provider coupling;
- controlling cost and privacy;
- validating and escalating model responses;
- serving as a reusable private backend;
- exposing authorized capabilities through MCP, REST, Actions, and plugins;
- exporting portable provider-independent context;
- remaining useful through partial or full exit modes;
- showing its state;
- justifying its conclusions;
- preserving human control.

Completing this phase will establish the first stable CMM OS release.

From that point onward, the project will stop focusing on building its foundational architecture and begin evolving on top of a consolidated platform.

---

# Post-Phase Evolution

After Phase 11, a new stage will begin, focused on advanced capabilities:

- goals that persist for years;
- periodic review of life plans;
- controlled proactivity;
- autonomous detection of relevant changes;
- multi-agent coordination;
- operational learning;
- continuous improvement;
- workflow optimization;
- anticipation of needs;
- scenario simulation;
- strategic planning;
- autonomous system maintenance;
- evolution without redesigning the core.

## Consolidated Vision

```text
Phases 0–6
Understand, transform, execute, and remember
↓
Phase 7
Modify without degrading
↓
Phase 8
Reason structurally
↓
Phase 9
Pursue goals
↓
Phase 10
Specialize intelligence
↓
Phase 11
Integrate everything into a stable platform
↓
Future evolution
Persistent, proactive, and supervised personal system
```

<!-- PHASE11_5_FINAL_CLOSURE_EVIDENCE -->
## Phase 11.5 — Final closure evidence

```text
PHASE11_5=CLOSED
F11_019=VERIFIED_EXISTING
DP_105=VERIFIED_EXISTING
AT_DP_105=PASS
INDEPENDENT_AUDIT_V1=FAIL_RECORDED
INDEPENDENT_REAUDIT_V1=FAIL_RECORDED
INDEPENDENT_REAUDIT_V2=PASS
BLOCKERS=0
MAJORS=0
MINORS=0
MAJOR_R1_01=VERIFIED_REMEDIATED
MINOR_R1_01=VERIFIED_REMEDIATED
MINOR_R1_02=VERIFIED_REMEDIATED
REMEDIATION_V2=INDEPENDENTLY_REAUDITED_PASS
CLOSURE_ELIGIBLE=YES
AUDIT_STATUS=CLOSED_AFTER_INDEPENDENT_REAUDIT_V2_PASS
AUDITED_HEAD=9fde9db154c5ff957565f8f4ab6ca2391037b15c
AUDITED_TREE=937f4312592baf33a6aedf59e37a2ca475a8e036
AUDITED_BUNDLE_SHA256=56d5eee4f2d1f908465f1b65bc16237ea4b4d40b64f3fc49bc2c6840bef13511
FINAL_REPORT=docs/audits/phase-11.5-conversational-interface-independent-reaudit-v2.md
FINAL_REPORT_SHA256=f5a4f72c12734052f24df63250bb1c28d5017e90d99129e5d56afbf5d71bd67c
AUDIT_REPORT_COMMIT=e3a713bfdb2b108c4db7a38a4da556cc1ce83c86
NEXT=PHASE11_NEXT_SUBPHASE_REQUIRES_FRESH_INSPECTION
```

Phase 11.5 is closed by the dedicated docs-only closure commit after the
Independent Re-audit V2 `PASS`. Historical Audit V1 and Re-audit V1 `FAIL`
evidence remains immutable.

<!-- PHASE11_21_IMPLEMENTATION_STATE -->
# 11.21 — Model Gateway implementation state (2026-09-25)

**Status:** closed after Independent Re-audit V3 `PASS`. This section records the final independently verified Phase 11.21 implementation and its immutable audit history. The Phase 11.21 scope is frozen by
`docs/superpowers/specs/2026-09-25-phase-11.21-model-gateway-design.md` and
`docs/superpowers/plans/2026-09-25-phase-11.21-model-gateway-implementation-plan.md`,
and the residual correction by
`docs/superpowers/specs/2026-09-25-phase-11.21-remediation-v2-design.md` and
`docs/superpowers/plans/2026-09-25-phase-11.21-remediation-v2-implementation-plan.md`.

## Implementation boundary

Phase 11.21 introduces exactly one new authority — provider-independent
model-call normalization and execution — and reuses every canonical owner it
needs. It implements no routing-policy intelligence (11.35+), no cost
management layer (11.38), no model usage audit persistence (11.44) and no
CMMChat-facing client surface (11.50).

## Exact canonical owners reused

```text
kernel/llm/provider_registry.py      ProviderRegistry (exact instance identity)
kernel/llm/model_catalog.py          ModelCatalog (bound to that same registry)
kernel/llm/model_selection.py        ModelRequirements and find_matching_models
                                     (fallback planning and AUTO selection only)
kernel/llm/model_router.py           RoutingCandidate (fallback planning only)
cmm/agent_runtime/model_fallback_decision_engine.py   attempt/fallback decisions
cmm/agent_runtime/model_fallback_contracts.py         attempt and policy contracts
cmm/agent_runtime/model_execution_contracts.py        agent-run execution record
cmm/cognitive/privacy.py             evaluate_privacy_operation (only privacy authority)
cmm/platform/                        Phase 11.1 composition root
cmm/application/, cmm/conversation/  Phase 11.3 / 11.5 boundaries (untouched)
```

## Files introduced

```text
kernel/llm/model_gateway.py
kernel/llm/model_gateway_contracts.py
kernel/llm/model_gateway_errors.py
kernel/llm/model_provider_adapter.py
kernel/llm/model_streaming.py
cmm/agent_runtime/model_egress_privacy_adapter.py
cmm/agent_runtime/model_fallback_gateway_adapter.py
cmm/agent_runtime/model_execution_evidence_projection.py
tests/llm/model_gateway_support.py
tests/llm/test_model_gateway_architecture.py
tests/llm/test_model_gateway_contracts.py
tests/llm/test_model_gateway_capabilities.py
tests/llm/test_model_gateway_adapters.py
tests/llm/test_model_gateway_execution.py
tests/llm/test_model_gateway_reasoning.py
tests/llm/test_model_gateway_multimodal.py
tests/llm/test_model_gateway_structured_output.py
tests/llm/test_model_gateway_tools.py
tests/llm/test_model_gateway_streaming.py
tests/llm/test_model_gateway_cancellation.py
tests/llm/test_model_gateway_privacy.py
tests/llm/test_model_gateway_timeout_retry.py
tests/llm/test_model_gateway_fallback.py
tests/llm/test_model_gateway_accounting.py
tests/llm/test_model_gateway_evidence.py
tests/llm/test_phase11_21_dp121_acceptance.py
tests/platform/test_model_gateway_binding.py
tests/agent_runtime/test_model_egress_privacy_adapter.py
tests/agent_runtime/test_model_fallback_gateway_adapter.py
tests/agent_runtime/test_model_execution_evidence_projection.py
```

## Inherited closed phases

Phase 11.34, 11.1, 11.2, 11.3, 11.4 and 11.5 remain closed and are not
redesigned. The only changes inside closed packages are documented additive,
backwards-compatible seams:

```text
kernel/llm/capabilities.py    ReasoningEffort enum; ModelCapabilities gains
                              reasoning_efforts, document_media_types and
                              streaming, all defaulted to unknown/unsupported
kernel/llm/provider_state.py  Phase 11.21 Remediation V1 additive state-schema
                              revision: SCHEMA_VERSION "2" -> "3" now persists
                              the Phase 11.21 capability fields; Phase 11.34
                              persistence ownership is unchanged and no second
                              store is introduced
cmm/platform/canonical.py     PROVIDER_REGISTRY_CONTRACT_VERSION,
                              _provider_registry_dependency and
                              model_gateway_binding
cmm/platform/__init__.py      additive export
```

No closed-phase production semantics were changed, no persistence authority was
changed and no closed phase was reopened. `kernel/llm/__init__.py` is
deliberately left unchanged: Phase 11.21 introduces no new `kernel.llm` package
export, so the gateway surface is imported from its own modules.

## DP-121 / AT-DP-121

`DP-121` — Canonical Provider-Independent Model Gateway — is implemented.
Independent Audit V1 returned `FAIL` (`BLOCKERS=0`, `MAJORS=5`, `MINORS=1`) and
that report is preserved unchanged in
`docs/audits/phase-11.21-model-gateway-independent-audit-v1.md`. Remediation V1
implemented the six Audit V1 findings locally: `AUTO` iterates canonical
candidates through the gateway's hard execution gates, one cancellation token
stays authoritative across the whole call including fallback, the public stream
deadline is bounded by a private per-call pump, the legacy adapter fails closed
on unrepresentable tools and structured output, and the Phase 11.34 state owner
persists the Phase 11.21 capability fields under schema version `"3"`.

Independent Re-audit V2 then returned `FAIL` (`BLOCKERS=0`, `MAJORS=1`,
`MINORS=0`, `PROCESS_DEVIATIONS=1`) and recorded exactly one residual finding —
the candidate-set-wide `AUTO` egress precheck still aborted the whole request
before a valid local candidate when privacy metadata was absent. That report is
preserved unchanged in
`docs/audits/phase-11.21-model-gateway-independent-reaudit-v2.md` and is not
rewritten. Remediation V2 removes the precheck and evaluates egress/privacy
authority only inside the per-candidate hard gate: a remote candidate whose
egress lacks canonical privacy authority is skipped, a following valid local
candidate executes, `AUTO` with only remote candidates still fails closed before
provider I/O, and explicit remote selection stays strictly fail-closed. The
canonical `find_matching_models` ordering is untouched.

`AT-DP-121` passes (`tests/llm/test_phase11_21_dp121_acceptance.py`, 38 passed, including Remediation V2 Scenario S; focused Phase 11.21 gateway suite 404 passed) and Independent Re-audit V3 independently verified the closure-critical behavior. `DP_121=VERIFIED_EXISTING`, `AT_DP_121=PASS`, and `CLOSURE_ELIGIBLE=YES`.

Inherited acceptances remain green:

```text
AT_DP_134=PASS   tests/llm/test_provider_registry_dp134_acceptance.py
AT_DP_101=PASS   tests/platform/test_phase11_1_dp101_acceptance.py
AT_DP_102=PASS   tests/orchestration/test_phase11_2_dp102_acceptance.py
AT_DP_103=PASS   tests/application/test_phase11_3_dp103_acceptance.py
AT_DP_104=PASS   tests/cli/test_phase11_4_dp104_acceptance.py
AT_DP_105=PASS   tests/conversation/test_phase11_5_dp105_acceptance.py
```

## Known Ruff baseline debt

Repository-wide `ruff check .` reports 837 findings both before and after
Phase 11.21: the pre-existing repository debt is unchanged and Phase 11.21
introduces zero new findings. Every new or touched Python file passes
`ruff check` and `ruff format --check`.

## Independent Re-audit V3 PASS and formal closure

Independent Audit V1 `FAIL` and Independent Re-audit V2 `FAIL` remain preserved
unchanged. Remediation V2 exact HEAD `fe5eda5ccba327d3002979910f9cf4d8a4053ddc` (tree
`0e8a1ac75e5fdf32a5e5e240790a0d8ff986ced7`) was independently audited from bundle SHA-256
`1873217d10222e87e9d5e319a319eaddf7741c4ef05d384377bb4548f47a5bd3`.

Independent Re-audit V3 returned:

```text
INDEPENDENT_REAUDIT_V3=PASS
BLOCKERS=0
MAJORS=0
MINORS=0
MAJOR_01=VERIFIED_REMEDIATED
MAJOR_02=VERIFIED_REMEDIATED
MAJOR_03=VERIFIED_REMEDIATED
MAJOR_04=VERIFIED_REMEDIATED
MAJOR_05=VERIFIED_REMEDIATED
MINOR_01=VERIFIED_REMEDIATED
F11_020=VERIFIED_EXISTING
DP_121=VERIFIED_EXISTING
AT_DP_121=PASS
CLOSURE_ELIGIBLE=YES
```

The final independent report is `docs/audits/phase-11.21-model-gateway-independent-reaudit-v3.md`, recorded by audit-report commit
`749dd87df5a919775058d116ba17a878cf5adc5f`.

This dedicated docs-only closure records:

```text
PHASE11_21=CLOSED
AUDIT_STATUS=CLOSED_AFTER_INDEPENDENT_REAUDIT_V3_PASS
NEXT=PHASE11_50_FRESH_REPOSITORY_INSPECTION
```

No code or tests are part of closure. Historical audit reports, the frozen
Phase 11.21 design/plan and both remediation design/plan pairs remain immutable.
The implemented surface, enforced invariants, known limits and final evidence are
documented in
[`docs/reference/phase-11-model-gateway.md`](../reference/phase-11-model-gateway.md).
