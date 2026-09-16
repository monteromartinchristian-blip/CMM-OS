# Phase 11 — Orchestration Layer reference

**Status:** `CLOSED_AFTER_INDEPENDENT_REAUDIT_V2_PASS`
**Phase:** 11.2 — Orchestration Layer
**Requirement:** `F11-016 — Canonical Request Orchestration`
**Design Point:** `DP-102 — Fail-Closed Canonical Request Orchestration Pipeline`
**Acceptance Test:** `AT-DP-102` — `tests/orchestration/test_phase11_2_dp102_acceptance.py`
**Design specification:** `docs/superpowers/specs/2026-09-16-phase-11.2-orchestration-layer-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-09-16-phase-11.2-orchestration-layer-implementation-plan.md`
**Remediation design:** `docs/superpowers/specs/2026-09-16-phase-11.2-remediation-v1-design.md`
**Remediation plan:** `docs/superpowers/plans/2026-09-16-phase-11.2-remediation-v1-implementation-plan.md`
**Independent Audit V1:** `docs/audits/phase-11.2-orchestration-layer-independent-audit-v1.md` — `FAIL`, `MAJORS=2`
**Independent Re-audit V1:** `docs/audits/phase-11.2-orchestration-layer-independent-reaudit-v1.md` — `FAIL`, `BLOCKERS=0`, `MAJORS=0`, `MINORS=1`
**Independent Re-audit V2:** `docs/audits/phase-11.2-orchestration-layer-independent-reaudit-v2.md` — `PASS`, `BLOCKERS=0`, `MAJORS=0`, `MINORS=0`
**Audited implementation HEAD:** `68ff78c614d8f7a9dc3295eb22ecea62a425cce5`
**Audited tree:** `d586c439fc9b3c87d139eecab8d084d820007bce`
**Re-audit V2 bundle SHA-256:** `72d1b5b36104734308e322b2edd038875755d145db5d9ad8f77e2d45c7a7e62e`
**Re-audit V2 report commit:** `773204c7df06fced504892ed33284f39eca5b63a`
**Production package:** `cmm/orchestration/` (12 modules)
**Implementation base:** `b3aa5e3b8a7538874cbeba91030417bf4859feeb`
**Starting HEAD:** `89edfbb5ef1c134c37465e85d9a9b452aa1d3ac0`

Phase 11.2 is **implemented, independently re-audited and closed** after final
Independent Re-audit V2 `PASS`. The two Audit V1 MAJOR findings and the Re-audit
V1 documentation MINOR are `VERIFIED_REMEDIATED`; `F11-016=VERIFIED_EXISTING`,
`DP-102=VERIFIED_EXISTING`, `AT-DP-102=PASS`, and `CLOSURE_ELIGIBLE=YES`.

Audit history remains append-only: Independent Audit V1 is preserved as `FAIL`
with `MAJORS=2`; Independent Re-audit V1 is preserved as `FAIL` with `MINORS=1`;
final Independent Re-audit V2 is `PASS` with `BLOCKERS=0`, `MAJORS=0` and
`MINORS=0`.

## 1. Purpose and ownership boundary

Phase 11.2 adds one missing architectural capability: global canonical request
coordination.

```text
future clients / future 11.3 Application Backend
                ↓
        OrchestrationRequest
                ↓
             Orchestrator
                │
                ├── IntentResolver
                ├── ContextResolver
                ├── DomainRouter          (route_domain)
                ├── OrchestrationPolicy
                └── AgentRouter           (route_agent)
                ↓
        OrchestrationResult
                ↓
    canonical subsystem boundaries
```

The Orchestrator is a **control-plane coordinator**. It does not become a Domain
Resolver, Agent Resolver, Workflow Engine, Execution Engine, Validation Engine,
Memory/Knowledge/Session Store, Provider Router, Model Gateway, Event Bus or
Planner.

Direction of dependency:

```text
cmm.orchestration  ->  cmm.platform + existing canonical subsystem packages
```

Canonical subsystem packages never import `cmm.orchestration`. That is enforced
by `tests/orchestration/test_architecture.py`.

## 2. Canonicalization matrix

| Roadmap concept | Classification | Owner / Phase 11.2 treatment |
| --- | --- | --- |
| `OrchestrationRequest` | `NEW_PLATFORM_BOUNDARY` | `cmm.orchestration.contracts` |
| `OrchestrationResult` | `NEW_PLATFORM_BOUNDARY` | `cmm.orchestration.contracts` |
| `IntentResolver` | `NEW_PLATFORM_BOUNDARY` | `cmm.orchestration.intent` (global request intent only) |
| `ContextResolver` | `NEW_PLATFORM_BOUNDARY` | `cmm.orchestration.context` (read-only coordinator) |
| `DomainRouter` | `CANONICAL_ADAPTED` | facade over `cmm.domains.resolver.DefaultDomainResolver` |
| `AgentRouter` | `CANONICAL_ADAPTED` | execution-route selection; agent selection delegated to the Agent Registry |
| `OrchestrationPolicy` | `NEW_PLATFORM_BOUNDARY` | restrictive coordinator over existing evidence |
| `Session` | `CANONICAL_EXISTING` | `cmm.runtime.sessions.SessionStore` / `InMemorySessionStore` |
| `DomainResolutionResult` | `CANONICAL_EXISTING` | `cmm.domains.resolver_contracts` |
| `DomainResolutionContext` | `CANONICAL_EXISTING` | `cmm.domains.resolution_contracts` |
| `DomainPermissionRequest` / `EffectivePermissionResult` | `CANONICAL_EXISTING` | `cmm.domains.permission_contracts` / `cmm.agent_runtime.domain_permission_contracts` |
| `AgentResolution` | `CANONICAL_EXISTING` | `cmm.agent_runtime.agent_registry_contracts` |
| `AgentRequirement` | `CANONICAL_EXISTING` | `cmm.agent_runtime.agent_registry_contracts` |
| `ErrorResult` | `CANONICAL_EXISTING` | `cmm.platform.contracts.ErrorResult` |
| roadmap `reasoning_trace` | `CANONICAL_ADAPTED` | safe `trace_refs` / `reason_codes` only; never hidden reasoning |
| roadmap `memory_updates` | `CANONICAL_ADAPTED` | not implemented: Phase 11.2 has no memory authority |

## 3. Public package surface

`import cmm.orchestration` causes no registration, no repository mutation, no
event emission, no file I/O and no canonical subsystem construction; a
declarative AST gate plus a module-singleton gate enforce that.

Public exports:

```text
ALLOWED_EVENT_TYPES                       ORCHESTRATION_MODULE_ID
AgentRouteDecision                        ORCHESTRATION_SERVICE_IDS
AgentRouter                               OrchestrationChannel
AgentRoutingError                         OrchestrationConfiguration
CanonicalAgentRouter                      OrchestrationDecisionRecord
CanonicalDomainRouter                     OrchestrationDecisionRepository
ContextReferenceReader                    OrchestrationError
ContextResolutionError                    OrchestrationEventSink
ContextResolver                           OrchestrationPolicy
DecisionPersistenceError                  OrchestrationPolicyDecision
DefaultContextResolver                    OrchestrationPolicyError
DefaultOrchestrationPolicy                OrchestrationRequest
DeterministicIntentResolver               OrchestrationResult
DomainRouteDecision                       OrchestrationStatus
DomainRouter                              Orchestrator
DomainRoutingError                        OrchestratorProtocol
ExecutionRoute                            PolicyDisposition
InMemoryOrchestrationDecisionRepository   RecordedOrchestrationEvent
IntentKind                                RecordingOrchestrationEventSink
IntentResolution                          ResolvedContext
IntentResolutionError                     build_orchestration_composition_module
IntentResolver                            validate_orchestration_event
ORCHESTRATION_AUTHORITY
```

## 4. Frozen contracts

All public Phase 11.2 values are frozen dataclasses, validated at construction,
defensive against caller mutation (mappings are copied into immutable mappings,
sequences into tuples), deterministically serializable through `to_dict()`, and
reject opaque runtime objects and binary data.

### 4.1 Enums

| Enum | Values |
| --- | --- |
| `IntentKind` | `question`, `reflection`, `command`, `goal`, `workflow_request`, `information_update`, `approval_response`, `continuation`, `cancellation`, `configuration_change`, `unknown` |
| `OrchestrationChannel` | `conversation`, `cli`, `internal`, `api` |
| `ExecutionRoute` | `direct_response`, `operation`, `workflow`, `autonomous_agent`, `human_escalation`, `none` |
| `OrchestrationStatus` | `routed`, `needs_clarification`, `blocked`, `escalated`, `cancelled`, `failed` |
| `PolicyDisposition` | `allow_route`, `require_approval`, `escalate`, `deny` |

`API` is an origin identifier only: Phase 11.2 implements no API. `COMPLETED` is
deliberately absent because Phase 11.2 never executes the downstream vertical.

### 4.2 `OrchestrationRequest`

`request_id`, `user_id`, `channel` (required); `session_id`, `bot_id`, `input`,
`context`, `requested_capabilities`, `intent_hint` (defaulted). `channel` is
declared immediately after the two required identities so every remaining field
can carry a safe default; names and semantics are exactly the frozen set.
`bot_id` is an opaque reference — Phase 11.2 implements no Bot identity,
repository or runtime authority.

### 4.3 `OrchestrationResult`

`request_id`, `status`, `intent`, `primary_domain`, `supporting_domains`,
`profile_id`, `route`, `agent_id`, `workflow_id`, `approval_refs`,
`decision_id`, `trace_refs`, `reason_codes`, `error`.

No `chain_of_thought`, `hidden_reasoning`, `raw_reasoning`, `reasoning_trace`,
`prompt`, `provider_payload`, `credentials` or `memory_updates` field exists in
any public contract, decision record, event or error — enforced by an
executable gate.

### 4.4 `OrchestrationDecisionRecord`

`decision_id`, `request_id`, `session_id`, `channel`, `intent`,
`primary_domain`, `supporting_domains`, `execution_route`,
`policy_disposition`, `selected_agent_id`, `workflow_id`, `approval_refs`,
`reason_codes`, `trace_refs`, `occurred_at`.

`policy_disposition` is optional: a decision that never reached policy
evaluation (an intent-unknown or ambiguity clarification) records `None` rather
than inventing a disposition. Raw request text is never persisted.

## 5. Deterministic intent resolution

`DeterministicIntentResolver` is a pure, stateless function of the request. It
performs no I/O, no network access and no model call, and it is not the
historical `cmm_agent.router.IntentRouter` (which is neither deleted nor
repurposed; no `cmm_agent` redesign was performed).

Frozen classification precedence:

```text
approval response
cancellation
continuation
configuration change
information update
workflow request
goal
command
question / reflection
unknown
```

Structural evidence per intent:

| Intent | Request `input` shape |
| --- | --- |
| `approval_response` | `approval_id` and `decision`, both non-empty strings |
| `cancellation` | `cancel_target_id` |
| `continuation` | `continuation_id` |
| `configuration_change` | `configuration_change.path` |
| `information_update` | `information_update.subject_ref` |
| `workflow_request` | `workflow_request.workflow_type` |
| `goal` | `goal.title` |
| `command` | `command.operation` |
| `question` | `question` |
| `reflection` | `reflection` |

Rules:

* an explicit `intent_hint` has precedence; a shape-bound hint
  (`approval_response`, `cancellation`, `continuation`, `configuration_change`,
  `information_update`, `workflow_request`, `goal`, `command`) is honoured only
  when its own structured shape is present, so a hint can never upgrade a
  request into a side-effecting classification without evidence;
* a hinted `unknown` stays fail-closed;
* unstructured input returns `IntentKind.UNKNOWN` with
  `needs_clarification=True`; the resolver never guesses a side-effecting route;
* `reason_codes` make multiple simultaneous signals traceable
  (`INTENT_MULTIPLE_SIGNALS`) without changing the frozen precedence.

## 6. Two-stage authorized context resolution

`DefaultContextResolver` owns no context source. The canonical session authority
stays `cmm.runtime.sessions.SessionStore`; every additional collaborator is an
explicit constructor-injected read-only `ContextReferenceReader` seam — there is
no context registry, loader registry or cache.

```text
resolve_base(request)                          -> ResolvedContext(stage="base")
resolve_domain_context(request, base, domain)  -> ResolvedContext(stage="domain")
```

* `resolve_base` projects, in deterministic order, the canonical session
  reference, the injected reader references (`goal:`, `workflow:`, `memory:`,
  `knowledge:`, `event:`) and the allowlisted caller references (`caller:`).
  A request without a session id performs **no** session lookup.
* the caller context allowlist is exactly `context_refs`; every other key is
  withheld and only counted. Sensitive or unrelated caller context never reaches
  the result, the decision record, the events or the errors.
* an unknown referenced session is reported in `missing_refs`
  (`session:<id>`, reason `CONTEXT_SESSION_NOT_FOUND`) and is never invented.
  A referenced session with no composed canonical store fails closed with
  `ContextResolutionError`.
* the session collaborator is validated by type at construction: a request that
  references a session may only be served by a sanctioned canonical
  `cmm.runtime.sessions` store (`InMemorySessionStore` / `FileSessionStore`), so
  an arbitrary session-like object cannot stand in for session authority. The
  `SessionStore` Protocol carries no runtime check, so the sanctioned
  implementations are named explicitly rather than relaxing authority to a
  name-based duck type. `None` remains valid for requests that reference no
  session. See [§17](#17-audit-v1-remediation-v1).
* the `ContextReferenceReader` collaborators are deliberately **structural**
  read-only adapters: each owns no state, cannot mutate a canonical source and
  only returns safe reference strings, so a legitimate adapter stays acceptable
  while a non-conforming object still fails closed with `ContextResolutionError`.
* `resolve_domain_context` requires a real `DomainRouteDecision` carrying a
  selected primary domain, so domain-specific context can never be loaded before
  domain selection. It adds only the canonical domain references and the
  canonical permission references carried by that decision; it re-reads no
  source and widens nothing.

## 7. Canonical domain routing

`CanonicalDomainRouter` is a facade over Domain Intelligence. It reimplements no
scoring weight, fallback rule, ambiguity rule, permission semantic or
cross-domain authority.

Every collaborator is validated at construction against its canonical type, so
the router can only read domain availability, resolution results and permission
evidence from canonical Domain Intelligence — never from an object that merely
exposes the same method names. The one deliberate exception is
`profile_registry`, which stays the closed Phase 10 runtime-checkable
`DomainProfileRegistry` Protocol seam. See
[§17](#17-audit-v1-remediation-v1) for the full collaborator classification.

* the canonical `DomainRegistry` snapshot feeds the canonical
  `DomainResolutionContextBuilder`, which derives `available_domains` and
  `active_domains`;
* `available_domains` and `authorized_domains` are both taken from the canonical
  registry, so a caller can never widen the selectable domain set.
  `authorized_domains` states **installation-level availability**, not a
  per-actor permission grant: every action remains gated by canonical Domain
  permission evidence, and the dedicated authorization owner (Phase 11.13) will
  narrow that set when it exists. Caller-supplied `available_domains` /
  `authorized_domains` keys are ignored;
* the caller may only narrow evidence, through `context.explicit_domains` and
  structured `context.domain_signals`;
* the canonical resolution objective is taken deterministically from the
  request's explicit fields (`goal.title`, `question`, `reflection`,
  `command.operation`, `workflow_request.workflow_type`,
  `information_update.subject_ref`, `configuration_change.path`,
  `continuation_id`, `cancel_target_id`, `approval_id`) — the first non-empty
  field wins;
* canonical selection runs through `DefaultDomainResolver.resolve(...)`;
* a canonical `AMBIGUOUS` / `UNSUPPORTED` outcome (or any outcome without a
  selected primary domain that is not a canonical block) maps to
  `needs_clarification=True` and the orchestration result reports **no** primary
  domain, supporting domains or profile;
* a canonical `BLOCKED` outcome is a canonical deny and maps to `BLOCKED`;
* a canonical `FAILED` outcome raises `DomainRoutingError` (fail closed).

Canonical permission evidence is gathered only for intents that imply an action,
and only when the canonical permission layer actually holds an active policy for
a participating domain:

| Intent | Canonical capability | Required identifier |
| --- | --- | --- |
| `command` | `operation.execute` | `command.operation` |
| `goal` | `goal.update` | — |
| `workflow_request` | `workflow.execute` | `workflow_request.workflow_id` |
| `information_update` | `memory.write` | — |
| `continuation` | `workflow.execute` | `continuation_id` |
| `configuration_change` | `permission.modify` | — |

`DomainPermissionResolver.resolve(..., supporting_domains=...)` performs the
canonical restrictive intersection over primary **and** supporting domains, so a
supporting domain can only restrict — never widen — the primary restriction. By
canonical design, `DomainPermissionResolver` is only defined when at least one
active policy exists for a participating domain, so the router checks the
canonical `DomainPermissionRegistry` first. Absence of canonical policy is
**not** a deny: the route decision reports no permission evidence and the policy
decides how to treat that.

Outcome: `DomainRouteDecision` with status, primary/supporting/rejected/
ambiguous domains, profile reference, permission disposition and references,
approval references, canonical trace references and reason codes.

## 8. Canonical execution-path and agent routing

`CanonicalAgentRouter` retains the roadmap name; its Phase 11.2 responsibility is
execution-path selection. Its role method is `route_agent(...)`.

| Intent | Route |
| --- | --- |
| `question` | `direct_response` |
| `reflection` | `direct_response` |
| `command` | `operation` |
| `workflow_request` | `workflow` |
| `goal` | `autonomous_agent` |
| `information_update` | `operation` |
| `approval_response` | `operation` (the canonical approval/operation seam) |
| `continuation` | `workflow` (canonical workflow continuation seam) |
| `cancellation` | `workflow` (canonical workflow cancellation seam) |
| `configuration_change` | `human_escalation` (Phase 11.2 owns no configuration authority) |
| `unknown` | `none` |

The router performs **no** agent scoring. Agent compatibility and selection stay
owned by the canonical `cmm.agent_runtime.agent_registry_service.AgentRegistryService`
/ `AgentResolver`, and no other agent-selection authority is accepted: the
constructor rejects a noncanonical `registry_service` with a safe `TypeError`
before any routing can occur, so a fake authority can never fabricate an agent
identifier (see [§17](#17-audit-v1-remediation-v1)). `registry_service=None`
stays valid for routes that require no agent selection.

For `autonomous_agent` it builds the canonical `AgentRequirement` from the
request's declared `requested_capabilities` and calls
`AgentRegistryService.resolve_agent(...)`:

* a selected canonical descriptor is carried into the result as `agent_id` and
  `agent_version`;
* no compatible agent → `human_escalation` (`AGENT_ROUTING_NO_COMPATIBLE_AGENT`),
  never a fabricated agent;
* no declared capability evidence → `human_escalation`
  (`AGENT_ROUTING_REQUIREMENT_MISSING`): Phase 11.2 never invents an agent
  requirement;
* no injected registry service → `human_escalation`;
* a canonical resolution failure raises `AgentRoutingError`.

Non-agent routes never consult the Agent Registry, and the router never calls
Agent Runtime execution.

## 9. Restrictive orchestration policy

`DefaultOrchestrationPolicy` is a small deterministic coordinator over existing
canonical evidence — no policy DSL, policy registry, policy database or generic
policy engine.

Frozen precedence:

```text
canonical DENY                  -> DENY
canonical APPROVAL_REQUIRED     -> REQUIRE_APPROVAL
channel not enabled             -> DENY
route = HUMAN_ESCALATION        -> ESCALATE
route = NONE                    -> ESCALATE
side-effecting route without
explicit canonical ALLOW        -> ESCALATE
otherwise                       -> ALLOW_ROUTE
```

Invariants:

* a canonical deny can never become an allow, and is evaluated before every
  other signal;
* a canonical approval requirement can never become a silent allow;
* supporting-domain evidence cannot widen a primary restriction (the canonical
  intersection already applied it);
* a side-effecting route (`operation`, `workflow`, `autonomous_agent`) requires
  explicit canonical authority evidence; missing evidence escalates rather than
  being allowed by default;
* an unrecognised evidence value fails closed for side-effecting routes.

`OrchestrationConfiguration` is a small immutable configuration
(`allowed_channels`, `decision_recording_required`, `event_emission_required`).
It is not the Phase 11.12 Configuration Center and carries no secrets. Phase
11.2 keeps safe decision recording and safe event emission unconditional, so the
two flags may only state the required `True`; disabling either fails closed.

## 10. Decision repository

`OrchestrationDecisionRepository` is the only new persistence owner, with the
official in-memory `InMemoryOrchestrationDecisionRepository` (`threading.RLock`).

```text
save(record)                         -> OrchestrationDecisionRecord
get(decision_id)                     -> OrchestrationDecisionRecord | None
get_by_request_id(request_id)        -> OrchestrationDecisionRecord | None
list_for_session(session_id)         -> tuple[OrchestrationDecisionRecord, ...]
```

* an identical replay of the same decision identity is idempotent and returns
  the already-stored record (the recording timestamp is excluded from the
  identity payload);
* a contradictory reuse of a decision identity, or a request identity that
  already has a different decision, fails closed with
  `DecisionPersistenceError`;
* `list_for_session` is ordered by recording timestamp then decision id;
* no files, no SQLite, no database migration, and no session / goal / workflow /
  memory / knowledge / event storage.

## 11. Safe event sink

`OrchestrationEventSink` is an adapter seam, **not** an Event Bus: no
publish/subscribe platform, no replay engine, no durable event log, no event
registry. `RecordingOrchestrationEventSink` is the official in-memory recording
adapter for tests and local composition.

Allowed lifecycle events:

```text
orchestration.request_received     orchestration.approval_required
orchestration.intent_resolved      orchestration.blocked
orchestration.domain_resolved      orchestration.escalated
orchestration.route_selected       orchestration.routed
orchestration.failed
```

Payloads are recursively frozen, detached from the caller and structurally
restricted to safe identifiers and categorical facts. Keys naming
secret-bearing or reasoning-bearing content (`prompt`, `reasoning`,
`chain_of_thought`, `credential`, `secret`, `provider_payload`, `raw_context`,
`api_key`, `authorization`, `traceback`, …) fail closed, and opaque runtime
values are rejected.

## 12. Orchestrator pipeline

Exactly one global `Orchestrator` exists. Its constructor takes exactly the
seven frozen collaborators — `intent_resolver`, `context_resolver`,
`domain_router`, `agent_router`, `policy`, `decision_repository`, `event_sink` —
by keyword. There is no runtime service locator and no
`ApplicationContainer.get*()` call during request orchestration.

Every injected collaborator is validated at construction time against its
declared orchestration role, so role safety holds even for a directly
constructed `Orchestrator` that never passed through Phase 11.1 composition. A
cross-wired graph therefore fails with a safe `TypeError` before any request is
processed; the message names the collaborator, the expected role and the actual
implementation type, and never interpolates an object repr. See
[§17](#17-audit-v1-remediation-v1).

Frozen pipeline:

```text
 1. validate request
 2. emit orchestration.request_received
 3. resolve intent                     -> UNKNOWN stops for clarification
 4. resolve base context               -> unresolved session stops for clarification
 5. resolve canonical domain route     -> ambiguity stops; canonical block blocks
 6. resolve authorized domain context
 7. select execution route
 8. evaluate restrictive policy        -> deny / approval / escalate terminal paths
 9. construct safe decision record
10. persist decision record
11. emit terminal routing event
12. return OrchestrationResult
```

Terminal mapping:

| Outcome | `OrchestrationStatus` | Decision disposition | Terminal event |
| --- | --- | --- | --- |
| unknown intent | `needs_clarification` | `None` | `orchestration.routed` |
| unresolved session | `needs_clarification` | `None` | `orchestration.routed` |
| ambiguous domain | `needs_clarification` | `None` | `orchestration.routed` |
| canonical domain block | `blocked` | `deny` | `orchestration.blocked` |
| policy deny | `blocked` | `deny` | `orchestration.blocked` |
| policy approval required | `routed` | `require_approval` | `orchestration.approval_required` |
| policy escalate | `escalated` | `escalate` | `orchestration.escalated` |
| accepted cancellation | `cancelled` | `allow_route` | `orchestration.routed` |
| allowed route | `routed` | `allow_route` | `orchestration.routed` |
| internal failure | `failed` | — (not persisted) | `orchestration.failed` |

A clarification or cancellation terminal decision uses
`orchestration.routed` because Phase 11.2 introduces no clarification event name;
the emitted payload always carries the frozen terminal status.

Failure ordering is `malformed → failed`, `unknown intent → clarification`,
`unresolved session → clarification`, `ambiguous domain → clarification`,
`canonical deny → blocked`, `approval required → non-executing
approval-required`, `unsupported route → escalated`, `autonomous route without a
compatible agent → escalated`, `decision persistence failure → failed`. No
later side effect occurs after a terminal failure or deny.

Recovery is fail-closed: an `OrchestrationError` becomes a `FAILED` result with a
safe `ErrorResult`; any other exception is converted into a generic
`ORCHESTRATION_INTERNAL_FAILURE` result without exception text or traceback. A
failed request is not persisted as a decision.

Determinism: the same request identity always produces the same `decision_id`
(`orchestration-decision:<request_id>`) and the same intent, domain route,
execution route, policy disposition and reason codes. Only `occurred_at` is
runtime metadata.

## 13. Phase 11.1 composition

`build_orchestration_composition_module(...)` returns a side-effect-free
`StaticCompositionModule` contribution. Phase 11.1 remains the composition core:
this module adds new service bindings only and changes no Phase 11.1 semantics.
`cmm.platform` never imports `cmm.orchestration`.

| Service ID | Implementation | Runtime contract | Authority |
| --- | --- | --- | --- |
| `orchestration.agent_router` | injected `AgentRouter` | `AgentRouter` | — |
| `orchestration.context_resolver` | injected `ContextResolver` | `ContextResolver` | — |
| `orchestration.decision_repository` | injected repository | `OrchestrationDecisionRepository` | — |
| `orchestration.domain_router` | injected `DomainRouter` | `DomainRouter` | — |
| `orchestration.event_sink` | injected sink | `OrchestrationEventSink` | — |
| `orchestration.intent_resolver` | injected `IntentResolver` | `IntentResolver` | — |
| `orchestration.orchestrator` | injected `Orchestrator` | `OrchestratorProtocol` | `orchestration-request-coordinator` |
| `orchestration.policy` | injected policy | `OrchestrationPolicy` | — |

Boundary metadata: `contract_name == service_id`, `contract_version` `1.0.0`,
`schema_version` `1`, `owner` `cmm.orchestration`, mode `LOCAL`. Every builder
enforces its declared runtime contract before a binding can exist, so an
unrelated object can never claim an orchestration service identity;
`IntegrationServiceRegistry` re-checks it as defence in depth.
`orchestration.orchestrator` declares the seven collaborators as dependencies.
No orchestration binding claims provider, domain, agent, workflow, execution,
validation, memory or knowledge authority.

The eight service IDs, their contract versions and their authority labels are
unchanged by Remediation V1. What changed is that the two router role contracts
became runtime-discriminating (`route_domain` / `route_agent`), so a service for
one role can no longer satisfy another role's contract. A cross-wired graph is
now rejected by the module builder — before `ApplicationContainer` can reach
`READY` — instead of failing only on the first real request.

## 14. Security posture and side-effect boundary

The Orchestration Layer is a privilege boundary:

* no implicit permission grants and no approval bypass;
* no secrets or credentials in contracts, decisions, events or errors;
* no hidden reasoning disclosure;
* no supporting-domain privilege widening;
* no arbitrary provider/model selection;
* no side effect before the policy/permission decision;
* no downstream execution: no operation execution, no workflow start, no agent
  run, no memory or knowledge write, no provider or model call;
* the only Phase 11.2-owned side effects are safe decision persistence and safe
  event emission.

`AT-DP-102` proves the last two points with a connected boundary probe: a real
`AgentRuntimeIntegrationService` whose execution delegate records any call, plus
structural gates that Phase 11.2 holds no execution collaborator at all.

## 15. Exclusions

Phase 11.2 implements none of: HTTP API, FastAPI/Flask/Starlette, OpenAPI, REST
resources, SSE/WebSocket streaming, application-service facade, conversation
service, `GoalService`/`WorkflowService`/`KnowledgeService`/`MemoryService`,
pagination, API auth/idempotency/concurrency, CMMChat or CMM Bots integration,
Bot Registry, Model Gateway, Phase 11.35 Routing Policy Engine, provider
discovery, authentication/RBAC, secrets manager, storage migrations,
backup/recovery, plugin lifecycle, new Event Bus, distributed tracing platform,
background workers, queues, multi-agent coordination framework, scheduler, or a
new planner/workflow/execution/validation engine or memory/knowledge store.

The API and application backend remain **Phase 11.3**.

## 16. Testing

Counts below are the Remediation V1 implementation-machine results. The Audit V1
counts (426 focused / 23 `AT-DP-102` / 51 architecture gates) are superseded
because Remediation V1 added permanent tests; they remain valid evidence for the
audited HEAD `5ebc8d064fa3f29825c179eff7f41df204dc837b`.

| Suite | Command | Result |
| --- | --- | --- |
| Focused orchestration | `python -m pytest -q tests/orchestration` | 498 passed |
| `AT-DP-102` | `python -m pytest -q tests/orchestration/test_phase11_2_dp102_acceptance.py` | 33 passed |
| Affected subsystems | `python -m pytest -q tests/orchestration tests/platform tests/agent_runtime tests/domains tests/validation tests/workflows tests/execution tests/runtime tests/llm` | 17822 passed |
| Global suite | `python -m pytest -q` | 19117 passed |
| Inherited `AT-DP-101` | `tests/platform/test_phase11_1_dp101_acceptance.py` | 31 passed |
| Inherited `AT-DP-134` | `tests/llm/test_provider_registry_dp134_acceptance.py` | 67 passed |

`AT-DP-102` covers the twelve original connected scenarios plus the two
Remediation V1 scenarios:

| Scenario | Proves |
| --- | --- |
| A — simple question | `question` → canonical domain resolution → `direct_response` → `allow_route` → decision persisted → safe result |
| B — domain ambiguity | canonical ambiguity → `needs_clarification`, no invented domain |
| C — cross-domain restriction | primary/supporting identity preserved; a supporting-domain denial is not bypassed |
| D — denied command | canonical deny → `blocked`, no execution |
| E — approval required | `require_approval` with canonical references, no execution |
| F — autonomous goal | real `AgentRegistryService.resolve_agent` selection carried into the result |
| G — no compatible agent | `human_escalation` → `escalated`, never a fabricated agent |
| H — session resumption | canonical `InMemorySessionStore` loads the session; an unknown session is reported |
| I — context minimization | sensitive/unrelated caller context never reaches result, decision, events or errors |
| J — multichannel | `conversation`/`cli`/`internal`/`api` share one routing core; the channel can only narrow |
| K — decision persistence | every terminal decision recorded exactly once, with safe facts only |
| L — composition | `ApplicationContainer` reaches `READY`, contracts satisfied, graph acyclic, snapshot serializes, duplicate authority rejected |
| M — role identity (Remediation V1) | the real Domain/Agent routers are not interchangeable; both cross-wires are rejected before `READY`; a correct real graph still reaches `READY` and still routes |
| N — canonical agent authority (Remediation V1) | a noncanonical registry service is rejected before it is consulted; the real `AgentRegistryService` is accepted and still performs selection; a canonical no-match still escalates without an invented agent |

Architecture gates (`tests/orchestration/test_architecture.py`, 72 tests) cover
no duplicate canonical owner, no reverse dependency, no Phase 11.3 API/backend
leakage, no Model Gateway/provider routing, no import-time mutation, no
hidden-reasoning field, no runtime service locator, no new Event Bus /
scheduler / queue, and — added by Remediation V1 — discriminating role methods,
pairwise runtime-role exclusivity, no generic `route` method on the official
routers, no dynamic `getattr` role fallback, no generic authority framework and
no role-marker attribute. The original gates were proven non-vacuous by
injecting a deliberate violation (a duplicate `DomainRegistry`, an `EventBus`,
an extra module and an import-time call) and observing five gates fail, then
removing the probe.

## 17. Audit V1 Remediation V1

Independent Audit V1 (`FAIL`, `BLOCKERS=0`, `MAJORS=2`, `MINORS=0`) reproduced
two architectural defects. Remediation V1 corrects exactly those two and adds no
capability, no subsystem and no new infrastructure.

```text
MAJOR_01=UNSAFE_ORCHESTRATION_ROLE_RUNTIME_CONTRACTS
MAJOR_02=CANONICAL_AGENT_AUTHORITY_NOT_ENFORCED
```

### 17.1 MAJOR-01 — role contracts were not runtime-discriminating

`DomainRouter` and `AgentRouter` both exposed only a method named `route`. A
runtime `@runtime_checkable Protocol` check verifies **member presence**, not
callable signature, so each role satisfied the other. A cross-wired graph passed
composition, reached `ApplicationContainer.READY`, and failed only on the first
real orchestration request.

Remediation:

* the role methods are now explicit and distinct — `DomainRouter.route_domain(...)`
  and `AgentRouter.route_agent(...)`; the official implementations
  (`CanonicalDomainRouter`, `CanonicalAgentRouter`) expose exactly those names and
  keep **no** generic `route` alias;
* the Orchestrator calls `domain_router.route_domain(...)` and
  `agent_router.route_agent(...)`; there is no `getattr(..., "route")` fallback;
* `Orchestrator.__init__` validates all seven injected collaborators against their
  frozen roles at construction time, so role safety does not depend on Phase 11.1
  composition. A cross-wired direct construction fails immediately;
* the eight composition service IDs, contract versions and authority labels are
  unchanged — the Phase 11.1 `runtime_contract` mechanism was already correct, it
  had simply been given two colliding contracts;
* a permanent pairwise runtime-role test asserts that each official
  implementation satisfies its intended role and no other stable orchestration
  role (`IntentResolver`, `ContextResolver`, `DomainRouter`, `AgentRouter`,
  `OrchestrationPolicy`, `OrchestrationDecisionRepository`,
  `OrchestrationEventSink`, `OrchestratorProtocol`). No second structural
  collision exists, and no marker hack was needed.

### 17.2 MAJOR-02 — canonical agent authority was a naming convention

`CanonicalAgentRouter` accepted `registry_service: Any | None` and trusted any
object exposing `resolve_agent(...)`. A fake service could return
`agent_id="forged.agent"` and the router accepted it as canonical agent
selection, because the outer binding only checked that the router satisfied the
`AgentRouter` role.

Remediation: `registry_service` is now typed and runtime-validated as
`cmm.agent_runtime.agent_registry_service.AgentRegistryService | None`. A
noncanonical authority is rejected with a safe `TypeError` at construction, before
it can be consulted; a real `AgentRegistryService` is accepted; `None` remains
valid for routes that need no agent selection. No `test_mode`,
`allow_fake_registry`, `unsafe_adapter`, `skip_validation` or `trust_registry`
escape hatch exists. Agent compatibility and selection remain owned by
`AgentRegistryService` / `AgentResolver`; Phase 11.2 reimplements no scoring and
never calls Agent Runtime execution.

### 17.3 Analogous canonical collaborator review

Audit V1 additionally required review of the analogous collaborators. Every
reviewed Domain/Context collaborator is classified below. `tightened` means a
runtime/type boundary was enforced; `unchanged` means the seam was reviewed and
deliberately left as it is.

| Collaborator | Canonical type | Classification | Action |
| --- | --- | --- | --- |
| `CanonicalAgentRouter.registry_service` | `cmm.agent_runtime.agent_registry_service.AgentRegistryService` | `CANONICAL_CONCRETE_OWNER` | tightened |
| `CanonicalDomainRouter.resolver` | `cmm.domains.resolver.DefaultDomainResolver` | `CANONICAL_CONCRETE_OWNER` | tightened |
| `CanonicalDomainRouter.registry` | `cmm.domains.registry.DomainRegistry` | `CANONICAL_CONCRETE_OWNER` | tightened |
| `CanonicalDomainRouter.context_builder` | `cmm.domains.resolution_builder.DomainResolutionContextBuilder` | `CANONICAL_CONCRETE_OWNER` | tightened |
| `CanonicalDomainRouter.profile_registry` | `cmm.domains.profile_registry.DomainProfileRegistry` | `CANONICAL_PROTOCOL_SEAM` | tightened to the existing closed Phase 10 runtime-checkable Protocol |
| `CanonicalDomainRouter.permission_registry` | `cmm.domains.permission_registry.DomainPermissionRegistry` | `CANONICAL_CONCRETE_OWNER` | tightened |
| `CanonicalDomainRouter.permission_resolver` | `cmm.domains.permission_resolution.DomainPermissionResolver` | `CANONICAL_CONCRETE_OWNER` | tightened |
| `DefaultContextResolver.session_store` | `cmm.runtime.sessions.InMemorySessionStore` / `FileSessionStore` | `CANONICAL_CONCRETE_OWNER` | tightened to the sanctioned canonical implementations |
| `DefaultContextResolver.*_reader` | `cmm.orchestration.context.ContextReferenceReader` | `DELIBERATE_READ_ONLY_ADAPTER` | unchanged (already structural, role-discriminating, fails closed) |

Notes on this table:

* `SessionStore` is a **static typing** Protocol with no runtime check, so it
  cannot be used in an `isinstance` boundary. The sanctioned runtime
  implementations are therefore named explicitly. No new Session Store interface
  was created and no change was made outside `cmm/orchestration/`.
* The domain collaborators were unrestricted `Any` while representing real
  sources of truth, so they were tightened and each gained a fake-authority
  rejection test. The fakes raise if consulted, so the tests also prove the
  rejected authority is never reached.
* `profile_registry` is not tightened to a concrete class: Phase 10 deliberately
  defines `DomainProfileRegistry` as a runtime-checkable Protocol, so the seam is
  preserved and merely validated against that Protocol instead of `Any`.
* `ContextReferenceReader` owns no source-of-truth state, cannot mutate a
  canonical source and only returns safe reference strings, so it stays
  structural by design; a legitimate adapter is asserted to be accepted and a
  non-conforming object to fail closed.

No generic authority/role framework was introduced: there is no
`RoleRegistry`, `RuntimeContractRegistry`, `AuthorityTypeRegistry`,
`AdapterTrustRegistry`, `CanonicalAuthorityRegistry`, `CanonicalOwnerResolver`
or role-marker attribute anywhere in `cmm/` or `tests/`, and an architecture
gate asserts it. Validation consists of three small module-private helpers
(`_require_role` in `orchestrator.py`, `_require_canonical` in
`domain_router.py`, and the inline canonical-authority check in
`agent_router.py`) plus one inline session-store check in `context.py`.

### 17.4 Behaviour deliberately unchanged

* the Audit V1 event-failure observation (a terminal event emission failure
  yields a `FAILED` public result while a route decision record already exists)
  received no severity and was **not** redesigned: no transactionality, rollback
  or outcome-record semantics were added, and the recorded data model still
  records the route decision rather than a delivery outcome;
* Phase 11.1 and Phase 11.34 production semantics are untouched;
* no production file outside `cmm/orchestration/` changed.

## 18. Deviations and implementation decisions

The committed design, plan, scope and acceptance criteria were followed. The
following implementation decisions are recorded as required:

1. **`authorized_domains` comes from the canonical registry.** The design does
   not name a source for the resolver's `authorized_domains`. Phase 11.2 feeds
   it the canonical registry's available/active domain set and documents that
   this states installation-level availability, not a per-actor grant. Caller
   assertions are ignored, and canonical permission evidence still gates every
   action. This is the only way to reach a working canonical resolution without
   inventing a per-actor authorization owner that belongs to Phase 11.13.
2. **No standalone `cross_domain_engine` collaborator.** The plan sketches an
   optional `cross_domain_engine` parameter. Canonical cross-domain behaviour
   (supporting-domain selection plus the restrictive permission intersection) is
   already reachable through `DefaultDomainResolver` and
   `DomainPermissionResolver`, so Phase 11.2 adds no separate collaborator and
   duplicates no cross-domain authority.
3. **`CanonicalDomainRouter` also takes the canonical `DomainRegistry` and
   `DomainResolutionContextBuilder`.** The design explicitly allows additional
   canonical collaborators "if required by the real Domain Resolver fixture";
   the canonical resolver cannot receive `available_domains` without them.
4. **Permission evidence requires the canonical policy registry.** The canonical
   `DomainPermissionResolver` is only defined when at least one active policy
   exists for a participating domain, so `permission_registry` and
   `permission_resolver` are provided together or not at all. Absence of a
   canonical policy is reported as absent evidence, never as a deny.
5. **`OrchestrationDecisionRecord.policy_disposition` is optional.** A decision
   that short-circuits before policy evaluation records `None` rather than
   inventing a disposition that was never evaluated.
6. **`OrchestrationConfiguration` requires recording and emission.** Phase 11.2
   keeps safe decision recording and event emission unconditional, so the two
   plan-named flags may only state `True`; disabling either fails closed
   (`decision_recording_required` and `event_emission_required` are otherwise
   unused because the Orchestrator takes exactly the seven frozen collaborators).
7. **Clarification and cancellation use `orchestration.routed`.** The frozen
   event list contains no clarification event name, so those terminal decisions
   emit `orchestration.routed` with the frozen terminal status in the payload.
8. **`tests/platform/test_architecture.py` gained one exemption and one
   strengthening.** The Phase 11.1 dependency-direction gate scans every file
   under `cmm/`, which now includes the new `cmm.orchestration` package; the
   Phase 11.2 design explicitly places `cmm.orchestration` *above*
   `cmm.platform`. The gate now excludes `cmm/orchestration` and a new gate
   asserts that `cmm.orchestration` is the **only** package allowed to depend on
   `cmm.platform`. No invariant is weakened.
9. **`ROADMAP.md` deliberately unchanged.** The repository's top-level roadmap
   records subphase status in closed/audited terms only and contains no
   pre-audit status convention (the same reasoning recorded for Phase 11.1). The
   pre-audit status is recorded in the detailed Phase 11 roadmap §11.2 and in
   the Phase 11 requirements matrix.
10. **Ruff invocation.** `CONTRIBUTING.md` defines the canonical Ruff invocation
    as scoped to changed Python files; Phase 11.2 is validated with that
    canonical scoped invocation and does not clean unrelated baseline debt.
11. **Remediation V1 removed the generic `route` role method.** `route_domain`
    and `route_agent` replaced it rather than sitting beside it, because a
    compatibility alias would recreate the runtime structural overlap the
    remediation exists to remove. No legacy consumer was found: `cmm_agent`
    never imports `cmm.orchestration`, and `cmm_agent.router.IntentRouter`
    (whose narrow `route(goal)` surface is a different, historical seam) is
    neither touched nor repurposed.
12. **Remediation V1 tightened four Domain collaborators that were previously
    unrestricted `Any`.** Audit V1 explicitly required this review
    (`docs/audits/phase-11.2-orchestration-layer-independent-audit-v1.md` §6.5),
    and the remediation design names the canonical target type for each. No
    Domain Intelligence algorithm, registry or resolver was modified; only the
    orchestration facade's constructor contract changed.

No deviation changes the architecture, widens the scope, replaces a canonical
subsystem owner, or pulls Phase 11.3 work forward.

## 19. Traceability

| Item | Value |
| --- | --- |
| Requirement | `F11-016 — Canonical Request Orchestration` |
| Design Point | `DP-102 — Fail-Closed Canonical Request Orchestration Pipeline` |
| Acceptance test | `AT-DP-102` — `tests/orchestration/test_phase11_2_dp102_acceptance.py` |
| Production package | `cmm/orchestration/` |
| Architecture gates | `tests/orchestration/test_architecture.py` |
| Focused suite | `tests/orchestration/` |
| Inherited acceptance | `AT-DP-101`, `AT-DP-134` (unchanged, green) |
| Design specification | `docs/superpowers/specs/2026-09-16-phase-11.2-orchestration-layer-design.md` |
| Implementation plan | `docs/superpowers/plans/2026-09-16-phase-11.2-orchestration-layer-implementation-plan.md` |
| Remediation design | `docs/superpowers/specs/2026-09-16-phase-11.2-remediation-v1-design.md` |
| Remediation plan | `docs/superpowers/plans/2026-09-16-phase-11.2-remediation-v1-implementation-plan.md` |
| Independent Re-audit V1 | `docs/audits/phase-11.2-orchestration-layer-independent-reaudit-v1.md` — `FAIL`, `MINORS=1` |
| Independent Re-audit V2 | `docs/audits/phase-11.2-orchestration-layer-independent-reaudit-v2.md` — `PASS`, `BLOCKERS=0`, `MAJORS=0`, `MINORS=0`, `CLOSURE_ELIGIBLE=YES` |
| Audited HEAD (Re-audit V2) | `68ff78c614d8f7a9dc3295eb22ecea62a425cce5` |
| Re-audit V2 tree | `d586c439fc9b3c87d139eecab8d084d820007bce` |
| Re-audit V2 bundle SHA-256 | `72d1b5b36104734308e322b2edd038875755d145db5d9ad8f77e2d45c7a7e62e` |
| Re-audit V2 report commit | `773204c7df06fced504892ed33284f39eca5b63a` |
| Independent Audit V1 | `docs/audits/phase-11.2-orchestration-layer-independent-audit-v1.md` — `FAIL`, `MAJORS=2` |
| Audited HEAD (Audit V1) | `5ebc8d064fa3f29825c179eff7f41df204dc837b` |
| Audit V1 tree | `989706d15ba78b8333b1e9b3634f820e9180f5bf` |
| Audit V1 bundle SHA-256 | `85127ed1e9a437e30984f930b60fba79b7ae28959baf3296f86665ce11b93fc9` |
| Implementation base | `b3aa5e3b8a7538874cbeba91030417bf4859feeb` |
| Starting HEAD | `89edfbb5ef1c134c37465e85d9a9b452aa1d3ac0` |
| Remediation starting HEAD | `5a5403b83b77271479e7434111fb4865e68535fe` |

Phase state before independent re-audit:

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

Audit V1 remains recorded as `FAIL` with `MAJORS=2`. Neither MAJOR is claimed
verified: exclusive verification of the remediation belongs to the independent
re-audit of the new exact-HEAD bundle.

## 20. Final independent closure

Final Independent Re-audit V2 reached the closure threshold and the dedicated
docs-only closure records the audited state without changing production code,
tests, or historical audit artifacts.

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

PHASE11_1=CLOSED
DP_101=VERIFIED_EXISTING
AT_DP_101=PASS

PHASE11_34=CLOSED
DP_134=VERIFIED_EXISTING
AT_DP_134=PASS

CLOSURE_ELIGIBLE=YES
```

Audited implementation HEAD: `68ff78c614d8f7a9dc3295eb22ecea62a425cce5`.
Audited tree: `d586c439fc9b3c87d139eecab8d084d820007bce`.
Re-audit V2 bundle SHA-256: `72d1b5b36104734308e322b2edd038875755d145db5d9ad8f77e2d45c7a7e62e`.
Final report: `docs/audits/phase-11.2-orchestration-layer-independent-reaudit-v2.md`.
Audit-report commit: `773204c7df06fced504892ed33284f39eca5b63a`.

Phase 11.3 — Application Backend is the next subphase and must begin with its own
fresh repository inspection.
