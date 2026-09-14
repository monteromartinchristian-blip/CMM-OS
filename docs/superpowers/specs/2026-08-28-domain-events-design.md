# Phase 10.33 — Domain Events Design

**Date:** 2026-08-28
**Status:** Design approved for implementation planning
**Branch:** `feature/phase-10-domain-intelligence`
**Previous boundary:** Phase 10.32 — Domain Conflict Resolution, complete and independently audited
**Next boundary:** Phase 10.34 — Domain Sessions

## 1. Objective

Phase 10.33 integrates Domain Intelligence with the existing Kernel event boundary through stable, versioned, safe domain events.

The phase must not create a second Kernel, a second Agent Runtime event bus, a second persistence layer, or a parallel source of truth. It introduces the Domain Intelligence event contract and the adapter that publishes those events through `kernel.events.Event`.

The canonical roadmap defines 23 general domain events and allows Domain Packs to declare specialized events.

## 2. Canonical sources

The implementation is constrained by:

- `ROADMAP.md` — Phase 10.33 is the next milestone after the audited closure of 10.32;
- `docs/roadmap/phase-10-domain-intelligence.md` — canonical Phase 10.33 objective, general event catalog, specialized examples, and required event properties;
- `docs/reference/domain-intelligence-requirements-matrix.md` — Phase 10.33 begins the remaining Domain Intelligence infrastructure sequence;
- `docs/superpowers/specs/2026-08-28-domain-conflict-resolution-policies-design.md` — Phase 10.32 is pure and explicitly delegates event emission to 10.33.

## 3. Existing architecture to reuse

Phase 10.33 reuses existing infrastructure rather than replacing it:

- `kernel.events.Event` is the Kernel-level event envelope;
- Phase 7 already demonstrates Kernel integration through a publisher pattern;
- Phase 9 owns the richer `AgentRuntimeEventBus` and its Agent Runtime-specific contracts;
- `DomainResolutionEvent` remains a lightweight inbound reference used by domain resolution and is not redefined as the Phase 10.33 outbound event contract;
- Phase 10.32 `DomainConflictResolver` remains pure and side-effect free.

Dependency direction must remain:

```text
Domain lifecycle/result
        ↓
DomainEvent
        ↓
DomainEventRegistry / validation
        ↓
DomainKernelEventPublisher
        ↓
kernel.events.Event
```

Domain Intelligence must not depend on `AgentRuntimeEventBus` merely to emit its own lifecycle events.

## 4. Architectural decision

The selected design is a small Domain Event layer plus an adapter to the existing Kernel event contract.

Rejected alternatives:

1. Reusing `AgentRuntimeEventBus` directly as the Domain Intelligence base event system. Rejected because it would couple Phase 10 to Phase 9-specific runtime infrastructure.
2. Expanding `kernel.events` into a new full event bus during Phase 10.33. Rejected because that is broader platform work and duplicates responsibilities assigned elsewhere.

Phase 10.33 therefore owns:

- a stable immutable `DomainEvent` contract;
- a canonical catalog of general Domain Intelligence event types;
- declaration and validation of specialized Domain Pack event types;
- safe event construction and serialization;
- conversion to `kernel.events.Event`;
- explicit publication through a Domain-to-Kernel publisher;
- event adapters around existing domain lifecycle boundaries;
- acceptance tests proving that pure components remain pure.

## 5. Non-goals

Phase 10.33 does not own:

- event persistence;
- replay;
- durable subscriptions;
- dead-letter queues;
- cross-process delivery;
- session persistence or resumption;
- workflow persistence;
- operation persistence;
- memory mutation;
- approval execution;
- permission decision execution;
- conflict truth resolution;
- domain selection policy;
- Kernel redesign;
- Agent Runtime event-bus redesign;
- Phase 11 platform-wide Event System work.

Phase 10.34 owns Domain Sessions. Later platform phases own broader persistence and delivery infrastructure.

## 6. Canonical general event catalog

The roadmap contains exactly 23 general events:

```text
domain.resolution.started
domain.resolution.completed
domain.resolution.ambiguous
domain.composition.created
domain.composition.updated
domain.execution.started
domain.execution.completed
domain.execution.failed
domain.conflict.detected
domain.conflict.resolved
domain.permission.requested
domain.permission.denied
domain.approval.requested
domain.approval.received
domain.memory.proposed
domain.memory.updated
domain.workflow.started
domain.workflow.paused
domain.workflow.resumed
domain.workflow.completed
domain.operation.started
domain.operation.completed
domain.operation.failed
```

This catalog is canonical. Tests must assert exact membership and exact cardinality to prevent silent drift.

## 7. Specialized events

Domain Packs may declare specialized events. Roadmap examples include:

```text
health.symptom.updated
health.medication.changed
university.grade.recorded
university.deadline.approaching
opposition.mock_exam.completed
life_plan.goal.updated
project.validation.failed
project.release.prepared
```

Specialized events must:

- use the same `DomainEvent` contract;
- declare an owning domain;
- use that domain's canonical event namespace;
- be versioned;
- pass the same safety and serialization rules as general events;
- never override a general event;
- never override another Domain Pack's event;
- never execute code merely by being declared or registered.

For Domain IDs containing hyphens, the event namespace follows the existing public identifier convention used by domain operations: for example `domain:life-plan` owns the `life_plan.*` namespace.

## 8. DomainEvent contract

`DomainEvent` is immutable and serializable.

Canonical semantic fields:

```python
DomainEvent(
    event_id: str,
    event_type: str,
    schema_version: str,
    domain_id: DomainId,
    related_domain_ids: tuple[DomainId, ...],
    actor: str,
    session_id: str | None,
    occurred_at: datetime,
    provenance: tuple[DomainEventReference, ...],
    sensitivity: str,
    permissions: tuple[str, ...],
    correlation_id: str | None,
    causation_id: str | None,
    payload: Mapping[str, JSONValue],
    metadata: Mapping[str, JSONValue],
)
```

`DomainEventReference` is a reference-only pointer to an authoritative upstream object. It does not copy semantic truth into the event layer.

Canonical fields:

```python
DomainEventReference(
    kind: str,
    reference_id: str,
    domain_id: DomainId | None = None,
)
```

Examples of `kind` include `resolution`, `composition`, `conflict_case`, `conflict_resolution`, `permission_request`, `approval`, `memory_proposal`, `workflow_run`, `operation_run`, `domain_result`, and `trace`.

## 9. Contract invariants

Every Domain Event must satisfy all of the following:

1. `event_id`, `event_type`, `schema_version`, `actor`, and `sensitivity` are non-empty.
2. `occurred_at` is timezone-aware.
3. `domain_id` is present and valid.
4. `related_domain_ids` are canonical, unique, and deterministic in serialized form.
5. `permissions` are identifiers describing the effective permission context; they are not permission grants and cannot broaden authority.
6. `provenance` is reference-only and cannot replace upstream provenance truth.
7. `payload` and `metadata` are JSON-safe.
8. Credential- and secret-like keys are rejected recursively from `payload` and `metadata`.
9. Raw secrets, credentials, unrestricted prompts, hidden reasoning, private chain-of-thought, and unrelated sensitive source contents are forbidden.
10. Sensitive source data should be represented by authoritative references where a reference is sufficient.
11. Unknown fields fail closed on deserialization.
12. Serialization is stable and round-trippable.
13. The event layer never changes facts, conflict status, permission decisions, memory truth, workflow truth, or operation truth.
14. Event creation does not imply that the referenced side effect occurred; the event type must correspond to an already established lifecycle fact.

## 10. Registry

`DomainEventRegistry` owns event-type declarations, not event delivery.

Required behavior:

- all 23 general events are built-in and immutable;
- built-ins cannot be unregistered or overridden;
- specialized events can be registered explicitly with `domain_id`, `event_type`, and `schema_version`;
- specialized event namespace must match the owning domain;
- duplicate registration fails;
- cross-domain namespace registration fails;
- aliasing is not required in 10.33;
- registration is side-effect free outside the registry;
- the registry may attach a pure payload validator to a specialized event;
- unknown event types fail closed before publication.

The registry must not load Domain Packs, execute plugins, call models, mutate sessions, or persist declarations.

## 11. Kernel publication

`DomainKernelEventPublisher` converts a validated `DomainEvent` into the existing `kernel.events.Event`.

The Kernel event must preserve:

```text
name      = DomainEvent.event_type
timestamp = DomainEvent.occurred_at
payload   = complete public DomainEvent serialization
```

Publication rules:

- registry validation occurs before Kernel conversion;
- no field is silently dropped;
- no event is published if validation fails;
- listener/publisher failures are surfaced as typed publication errors rather than silently presented as success;
- publication does not mutate the source result;
- repeated publication of the same event object must not mutate it;
- 10.33 does not add persistence, replay, queueing, or dead-letter handling.

## 12. Event construction

Lifecycle adapters may use a `DomainEventFactory` with injected `clock` and `id_factory` dependencies.

The factory exists only to standardize event creation. It must not:

- inspect hidden state;
- read memory directly;
- resolve domains;
- resolve conflicts;
- execute permissions;
- execute approvals;
- mutate sessions;
- perform external calls.

Tests must inject deterministic clocks and identifiers.

Pure Phase 10 components remain free of direct clock reads and random ID generation.

## 13. Lifecycle semantics

### 13.1 Resolution

- `domain.resolution.started` means an explicit resolution attempt has begun.
- `domain.resolution.ambiguous` means the authoritative resolution result is ambiguous.
- `domain.resolution.completed` means the resolution attempt reached a terminal non-ambiguous result. The payload preserves the actual authoritative status; the event name must not promote blocked, unsupported, insufficient-information, or failed states to `resolved`.

Phase 10.31 remains authoritative for the semantic resolution result.

### 13.2 Composition

- `domain.composition.created` records creation of a new authoritative composition.
- `domain.composition.updated` records a real replacement/change of an existing composition; recomputing an identical composition is not an update merely because code ran.

Phase 10.8 composition contracts remain authoritative.

### 13.3 Domain execution

`domain.execution.started`, `domain.execution.completed`, and `domain.execution.failed` describe the outer Domain Intelligence execution lifecycle. They do not replace operation- or workflow-specific events.

### 13.4 Conflict resolution

- `domain.conflict.detected` records the existence of an authoritative conflict case or adapted upstream conflict reference.
- `domain.conflict.resolved` may be emitted only when Phase 10.32 reports a genuinely semantically resolved conflict.

The following must never be mislabeled as `domain.conflict.resolved` merely because the resolver returned an object:

```text
maintain_conflict
postpone_action
ask_user
human_review
```

when the underlying conflict remains unresolved.

Phase 10.32 remains pure. Event emission happens around the resolver, never inside `DomainConflictResolver.resolve()`.

### 13.5 Permissions

- `domain.permission.requested` records an explicit permission request.
- `domain.permission.denied` records an authoritative denial.

Events cannot grant permissions or weaken fail-closed behavior.

### 13.6 Approvals

- `domain.approval.requested` records an approval request already created through the authoritative approval boundary.
- `domain.approval.received` records receipt of the authoritative response and includes its decision by reference/status.

The event layer never approves or rejects an action itself.

### 13.7 Memory

- `domain.memory.proposed` records a canonical shared-memory proposal/binding.
- `domain.memory.updated` may be emitted only after an authoritative shared-memory update has actually succeeded.

Proposal does not imply write. Binding does not imply write. Domain memory integration remains proposal/reference oriented and shared-memory ownership is unchanged.

### 13.8 Workflows

`domain.workflow.started`, `paused`, `resumed`, and `completed` record authoritative workflow lifecycle changes. Event emission cannot perform those transitions.

### 13.9 Operations

`domain.operation.started`, `completed`, and `failed` record authoritative operation lifecycle changes. Event emission cannot execute, retry, roll back, approve, or validate the operation.

## 14. Integration boundaries

Phase 10.33 adds adapters/orchestration around existing components rather than injecting event calls into pure semantic engines.

Required dependency-direction protections:

- `cmm/domains/conflict_resolution.py` must not import the Domain Event publisher/factory or Kernel event classes;
- Phase 10.31 selection policy code must not emit 10.33 lifecycle events internally;
- existing composition semantics must remain deterministic;
- event adapters consume already-produced immutable results and references;
- publication failures must not rewrite the authoritative result into another semantic state.

A thin orchestration layer may perform:

```text
create started event
↓
publish started event
↓
call authoritative component
↓
inspect returned public status only
↓
create the matching terminal event
↓
publish terminal event
```

It must not duplicate the authoritative component's decision logic.

## 15. Privacy and safety

Domain events are an observability/integration surface and therefore require strict minimization.

### 15.1 Runtime security contract

The runtime security contract is explicit:

1. **Normative caller requirement:** Callers MUST NOT place secrets or credentials in Domain Events.
2. **Active boundary rejection:** The Domain Event boundary actively rejects:
   - credential- and secret-bearing mapping keys and contexts;
   - private markers already covered by the existing privacy policy;
   - values matching canonical high-confidence credential signatures.
3. **Centralized registry:** Credential signatures are maintained centrally in one canonical policy (`cmm/domains/credential_policy.py`).
4. **Explicit non-goals:** The detector intentionally DOES NOT attempt:
   - arbitrary unknown-secret discovery;
   - entropy-based secret classification;
   - generic "long string = secret" heuristics (to prevent false positives on valid identifiers, URLs, or hashes).
5. **Deterministic enforcement guarantee:** Runtime detection guarantees rejection of:
   - structurally secret-bearing contexts; and
   - recognized high-confidence credential formats,
   not mathematically universal recognition of every possible unknown credential format.
6. **Error non-disclosure:** Rejected credentials must never be echoed in:
   - exception messages;
   - error details;
   - Kernel events;
   - emitted-event tracking.
7. **Regression matrix:** Adding a credential family to the canonical registry automatically subjects it to the full event-boundary regression matrix across all public event fields, deserialization paths, and Kernel publication gates.

### 15.2 Required safeguards

- reference-first payloads;
- recursive secret-key rejection;
- centralized high-confidence credential signature detection;
- no API keys or access tokens;
- no authorization headers;
- no cookies/session tokens;
- no hidden reasoning;
- no private prompt capture;
- no raw sensitive content when a reference is sufficient;
- sensitivity metadata is mandatory;
- effective permission identifiers are mandatory;
- cross-domain events expose only authorized domain identities/references;
- malformed safety metadata fails closed.

## 16. Proposed implementation units

The implementation plan prefers small, focused files following existing `cmm/domains/` patterns:

```text
cmm/domains/credential_policy.py
    canonical high-confidence credential signatures and detection policy

cmm/domains/event_catalog.py
    canonical 23-event general catalog and namespace helpers

cmm/domains/event_contracts.py
    DomainEventReference, DomainEvent, serialization and validation

cmm/domains/event_registry.py
    built-in and specialized event declaration registry

cmm/domains/event_factory.py
    deterministic/injectable event construction

cmm/domains/event_publisher.py
    DomainKernelEventPublisher and publication errors

cmm/domains/event_adapters.py
    pure lifecycle-to-event adaptation around existing public results
```

The exact split may be reduced if repo inspection during planning shows that a smaller arrangement better matches established Phase 10 conventions. No unrelated refactor is authorized.

## 17. Testing strategy

TDD is mandatory. No production code may precede the failing test that requires it.

The first RED must cover the minimal public surface:

1. exact 23-event canonical catalog;
2. construction of a valid `DomainEvent`;
3. rejection of an invalid/unsafe event;
4. conversion to `kernel.events.Event` without semantic loss.

Subsequent RED/GREEN cycles must cover:

- strict serialization/deserialization;
- timezone enforcement;
- recursive secret rejection;
- stable ordering/round-trip behavior;
- specialized event registration;
- duplicate/collision rejection;
- namespace ownership;
- unknown-event fail-closed behavior;
- deterministic injected clock/ID behavior;
- resolution lifecycle mapping;
- composition lifecycle mapping;
- conflict detected/resolved mapping;
- explicit proof that unresolved 10.32 outcomes do not become `domain.conflict.resolved`;
- permission and approval event mapping;
- memory proposed/updated distinction;
- workflow lifecycle mapping;
- operation lifecycle mapping;
- Kernel publication failure behavior;
- dependency-direction tests proving pure components do not gain event side effects;
- fresh-import side-effect freedom.

## 18. Acceptance gate — DP-033 / AT-DP-033

Phase 10.33 is acceptable only if all of the following hold:

1. one canonical Domain Event contract exists;
2. exactly 23 general event types are canonical;
3. all required general roadmap event names are present and no accidental extra built-ins exist;
4. specialized Domain Pack events can be declared without changing Kernel contracts;
5. specialized event ownership and namespace are validated;
6. events include domain, actor, session context when available, provenance references, sensitivity, permissions, schema version, and timestamps;
7. events contain no secrets and reject secret-like structures recursively;
8. events are immutable, JSON-safe, strictly serializable, and round-trippable;
9. unknown event types fail closed;
10. Kernel conversion preserves event type, timestamp, and complete public payload;
11. publication does not mutate authoritative domain results;
12. Phase 10.31 remains authoritative for domain selection semantics;
13. Phase 10.32 remains authoritative for conflict-resolution semantics and remains side-effect free;
14. unresolved/postponed/maintained conflicts are never mislabeled as resolved events;
15. permission events cannot grant permission;
16. approval events cannot perform approval decisions;
17. memory proposal events cannot imply a memory update;
18. workflow events cannot perform workflow transitions;
19. operation events cannot perform operation execution;
20. no event persistence/session store is added in 10.33;
21. Domain Intelligence does not depend on `AgentRuntimeEventBus` as its Kernel integration layer;
22. focused tests pass;
23. Phase 10 domain tests pass;
24. global tests pass;
25. Ruff, format check, and syntax compilation pass;
26. `AT-DP-033` passes;
27. an independent audit bundle is generated before independent audit;
28. independent audit reaches 0 blockers, 0 majors, and 0 minors before closure;
29. roadmap closure occurs only after the clean independent audit.

`DP-033` and `AT-DP-033` follow the established Phase 10 acceptance naming convention. If the repository already defines a different canonical identifier during implementation-plan inspection, the existing repository source wins and this document must be amended before production code.

## 19. Audit and closure

The standard CMM OS closure flow remains mandatory:

```text
focused verification
↓
domain verification
↓
global verification
↓
quality gates
↓
AT-DP-033
↓
TAR.GZ audit bundle
↓
independent ChatGPT audit
↓
remediation until 0 blockers / 0 majors / 0 minors
↓
closure documentation
↓
commit
```

No push or merge is performed unless explicitly requested.

The quarantine stash from Phase 10.32 must remain untouched.

## 20. Design summary

Phase 10.33 adds one event vocabulary and one safe Kernel publication boundary for Domain Intelligence.

It does not create a second event platform.

It preserves semantic ownership:

```text
10.31 owns domain selection semantics
10.32 owns conflict-resolution semantics
10.33 owns Domain Intelligence event emission
10.34 owns Domain Session continuity
Phase 9 owns Agent Runtime behavior and its richer runtime event bus
Kernel owns the common Event envelope
```

Event emission observes and reports authoritative lifecycle facts. It never becomes the authority that creates those facts.
