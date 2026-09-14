# Phase 10.36 — Domain API Design

**Status:** Approved design
**Phase:** 10.36 — Domain API
**Base HEAD:** `be5e257e0b39a8db2f43a4b830ab2a285034b491`
**Branch:** `feature/phase-10-domain-intelligence`
**Implementation status:** Not started

## 1. Purpose

Phase 10.36 introduces a stable public API for interacting with the Domain Intelligence runtime without exposing callers to the internal wiring of every Domain subsystem.

The Domain API is a coordination facade.

It is not a new Domain Runtime.

The defining success criterion is:

> A caller can inspect, discover, validate, install, activate, resolve and use domains through one stable public contract while all runtime truth, authorization, execution, persistence, conflict resolution and trace semantics remain owned by the existing canonical Domain components.

Phase 10.36 builds on the completed and independently audited Phase 10.35 Domain SDK. The SDK remains the developer-facing create/validate/test/pack layer. The Domain API is the runtime-facing coordination layer.

---

## 2. Architectural principle

The canonical relationship is:

```text
Caller
  ↓
DomainAPI
  ↓
existing canonical Domain components
  ↓
shared Kernel / Agent Runtime / Workflow / Session / Trace infrastructure
```

The API MUST remain thin.

It MUST NOT introduce parallel versions of:

- `DomainRegistry`;
- `DomainLoader`;
- Domain Discovery;
- Domain Validation;
- Domain Resolver;
- Domain Composer;
- Domain Conflict Resolver;
- resource registries;
- profile registries;
- rule registries;
- operation registries;
- workflow registries;
- permission registries;
- approval machinery;
- operation execution machinery;
- workflow execution machinery;
- session stores;
- trace stores;
- event buses;
- memory infrastructure;
- planners;
- agent runtimes;
- workflow engines.

The API owns coordination and public ergonomics.

Existing Domain components own runtime truth.

---

## 3. Canonical infrastructure reused

Phase 10.36 MUST reuse the existing repository contracts and services.

At minimum this includes the canonical equivalents of:

- `DomainRegistry`;
- `DomainQuery`;
- `DomainDefinition`;
- `DomainRegistryRecord`;
- `DomainCapability`;
- `FileSystemDomainDiscovery`;
- `DomainSource`;
- `DomainDiscoveryResult`;
- `PipelineDomainValidator`;
- `DomainValidationRequest`;
- `DomainValidationResult`;
- `DeclarativeDomainLoader`;
- `DomainCandidate`;
- `DomainLoadResult`;
- `DomainResolver`;
- `DomainResolutionContext`;
- `DomainResolutionResult`;
- canonical resource registry/resolver infrastructure;
- canonical rule infrastructure;
- `InMemoryDomainOperationRegistry`;
- `DomainOperationRequest`;
- `DomainOperationResult`;
- the authoritative Domain Operation orchestration path;
- `InMemoryDomainWorkflowRegistry`;
- `DomainWorkflowContext`;
- `DomainWorkflowResult`;
- `DomainWorkflowExecutor`;
- `SharedSessionDomainAdapter`;
- `DomainSessionContext`;
- `DomainSessionResumeRequest`;
- `DomainSessionResumeResult`;
- `DomainSessionResumer`;
- `DomainConflictCase`;
- `DomainConflictResolutionPolicy`;
- `DomainConflictResolution`;
- `DomainConflictResolver`;
- `DomainTraceAssemblyRequest`;
- `DomainTrace`;
- `DomainTraceReferenceInventory`;
- `DomainTraceValidationResult`;
- `DomainTraceAssembler`;
- `DefaultDomainTraceReferenceValidator`.

Existing contracts remain authoritative.

The API MUST return canonical objects wherever a suitable public contract already exists. It MUST NOT create API-specific copies of Domain definitions, operation results, workflow results, sessions, conflicts, resolutions or traces merely for presentation convenience.

---

## 4. Public facade

Phase 10.36 introduces a public protocol and a default implementation:

```text
DomainAPI
DefaultDomainAPI
```

The intended module boundary is:

```text
cmm.domains.api
```

`DomainAPI` defines the stable callable surface.

`DefaultDomainAPI` coordinates injected canonical collaborators.

The facade MUST NOT own an independent mutable registry or runtime state.

Its state is limited to references to injected collaborators.

---

## 5. Required public surface

The Phase 10.36 public surface is:

```text
list_domains
get_domain
discover_domains
validate_domain
install_domain
enable_domain
disable_domain
resolve_domain
get_capabilities
get_resources
get_rules
get_operations
get_workflows
execute_operation
start_workflow
get_session
resume_session
resolve_conflict
assemble_trace
validate_trace
```

No additional lifecycle or persistence surface is required for Phase 10.36.

---

## 6. Domain inspection

### 6.1 `list_domains`

`list_domains` delegates to `DomainRegistry.list(...)`.

It accepts the existing `DomainQuery` contract or no query.

It returns canonical `DomainDefinition` values.

It MUST NOT mutate registry state.

### 6.2 `get_domain`

`get_domain` delegates to the existing registry lookup contract.

It accepts:

```text
domain_id
optional version
```

It returns:

```text
DomainDefinition | None
```

No API-side cache is introduced.

### 6.3 Capabilities

`get_capabilities` exposes the capabilities declared by the canonical `DomainDefinition`.

The API MUST NOT infer capabilities from implementation modules, naming, installed files or persisted session state.

### 6.4 Resources, rules, operations and workflows

The methods:

```text
get_resources
get_rules
get_operations
get_workflows
```

expose canonical information already owned by the corresponding Domain registries/catalogs.

Where an existing canonical typed definition is available, the API SHOULD return that typed definition rather than constructing an API-specific representation.

Where the authoritative registry currently exposes identifiers as its stable contract, the API MAY expose those identifiers directly.

The implementation plan must inspect the exact existing registry contracts and choose the narrowest truthful return type.

The API MUST NOT create a duplicate catalog.

---

## 7. Discovery

`discover_domains` delegates to canonical Domain Discovery.

Conceptually:

```text
tuple[DomainSource, ...]
    ↓
FileSystemDomainDiscovery.discover(...)
    ↓
DomainDiscoveryResult
```

Discovery remains non-executing.

Discovery MUST NOT:

- register a domain;
- enable a domain;
- authorize an operation;
- execute pack code;
- create durable installation state.

Unsupported source kinds retain canonical discovery behavior.

---

## 8. Validation

`validate_domain` delegates to the canonical Domain Validation service.

The runtime API consumes the existing `DomainValidationRequest` contract and returns `DomainValidationResult`.

Phase 10.36 MUST NOT create a second validator or weaken canonical findings.

The Phase 10.35 convenience helper:

```text
validate_domain_path(...)
```

remains an SDK path-oriented facade and is not the runtime truth source for Phase 10.36.

Validation itself MUST NOT install or enable a domain.

---

## 9. Installation semantics

For Phase 10.36:

```text
install_domain(candidate)
```

means:

```text
DeclarativeDomainLoader.load(candidate)
```

with the existing canonical validation/loading/registry semantics.

Therefore:

```text
INSTALL = CANONICAL RUNTIME LOAD + REGISTRATION
```

and explicitly:

```text
INSTALL != DURABLE FILESYSTEM INSTALLATION
INSTALL != PACKAGE PUBLICATION
INSTALL != ENABLE
INSTALL != AUTHORIZATION
```

The API does not copy, extract or publish a `.tar.gz` into a persistent Domain installation directory.

A durable package repository/store would be a separate architectural capability and is outside Phase 10.36.

The existing loader remains responsible for transactional registry mutation and rollback.

Untrusted candidates remain fail-closed by default.

If the canonical loader exposes an explicit `allow_untrusted` override, the API may expose that same opt-in parameter with the same default and semantics. It MUST NOT silently enable it.

---

## 10. Activation

### 10.1 `enable_domain`

Delegates to:

```text
DomainRegistry.enable(...)
```

### 10.2 `disable_domain`

Delegates to:

```text
DomainRegistry.disable(...)
```

Installation and activation remain separate operations.

A newly installed Domain MUST NOT become authorized merely because it was loaded.

The API MUST NOT synthesize permission grants or approvals during enablement.

---

## 11. Resolution

`resolve_domain` delegates to the injected canonical `DomainResolver`.

It consumes the existing structured resolution context and returns the existing `DomainResolutionResult`.

The API MUST NOT implement:

- another scoring algorithm;
- another fallback policy;
- another ambiguity policy;
- another domain-selection policy.

All existing resolution limits, ambiguity handling and fail-closed semantics remain authoritative.

---

## 12. Operation execution

`execute_operation` accepts the canonical `DomainOperationRequest` and returns the canonical `DomainOperationResult`.

It MUST delegate to the authoritative existing Domain Operation orchestration path.

It MUST NOT call a Domain operation implementation directly merely because the operation is already known.

The existing path continues to own:

- availability;
- permission evaluation;
- approval requirements;
- execution dispatch;
- transaction handling;
- rollback;
- result construction.

Therefore:

```text
DomainAPI.execute_operation
    ↓
canonical Domain Operation orchestrator
    ↓
permission / approval / transaction gates
    ↓
registered implementation
```

The API MUST NOT bypass permission or approval machinery.

---

## 13. Workflow execution

`start_workflow` coordinates:

```text
workflow identifier
    ↓
canonical workflow registry resolution
    ↓
DomainWorkflowExecutor
    ↓
DomainWorkflowResult
```

It accepts the canonical workflow context and inputs required by the existing workflow execution contract.

The workflow registry remains authoritative for the active definition.

The workflow executor remains authoritative for execution.

The API MUST NOT introduce another workflow engine or execute workflow nodes itself.

Existing permission gates and nested operation semantics remain authoritative.

---

## 14. Sessions

### 14.1 `get_session`

`get_session(session_id)` delegates to:

```text
SharedSessionDomainAdapter.load_domain_session(session_id)
```

and returns:

```text
DomainSessionContext | None
```

The shared `SessionStore` remains the persistence authority.

The Domain API MUST NOT create a parallel Domain Session store.

### 14.2 `resume_session`

`resume_session(request)` delegates to `DomainSessionResumer.resume(...)` and returns `DomainSessionResumeResult`.

Resumption remains fail-closed and revalidates current runtime conditions.

A persisted Domain Session snapshot does not itself grant current authorization or establish current truth.

### 14.3 No session enumeration contract

The inspected shared session boundary exposes authoritative lookup by session ID but Phase 10.36 has no established Domain-specific global enumeration contract.

Therefore Phase 10.36 does not invent:

```text
list_all_domain_sessions
search_domain_sessions
```

Such a capability requires a real shared-store contract first.

---

## 15. Conflict resolution

`resolve_conflict` delegates to the existing pure `DomainConflictResolver`.

It consumes the canonical `DomainConflictCase` plus the existing optional policy and authority inputs supported by the resolver.

It returns `DomainConflictResolution`.

The facade MUST NOT mutate the conflict case before resolution.

`DomainConflictResolver` remains pure and deterministic.

The API MUST NOT introduce an API-specific conflict policy.

---

## 16. Traces

### 16.1 `assemble_trace`

Delegates to:

```text
DomainTraceAssembler.assemble(...)
```

using `DomainTraceAssemblyRequest`.

It returns canonical `DomainTrace`.

### 16.2 `validate_trace`

Delegates to the canonical trace reference validator using:

```text
DomainTrace
DomainTraceReferenceInventory
```

and returns:

```text
DomainTraceValidationResult
```

### 16.3 No Trace Store

The existing `DomainTrace` contract is persistence-independent.

Phase 10.36 therefore MUST NOT invent:

```text
TraceStore
DomainTraceRepository
get_trace_by_id backed by hidden process state
list_traces
```

The Domain API can coordinate trace assembly and validation, but persistent trace lookup requires an explicit authoritative persistence contract in a later phase.

Traces remain reference-only and must preserve their current privacy and integrity constraints.

---

## 17. Dependency injection

`DefaultDomainAPI` is constructed from explicit collaborators.

The implementation MUST NOT discover hidden global singleton instances.

Dependencies should be required only for methods that form part of the configured runtime surface.

A production/default composition helper MAY be introduced only if the repository already has a canonical place to assemble those collaborators.

It MUST NOT become a second bootstrap/runtime system.

Tests may use canonical in-memory implementations.

---

## 18. Error model

Phase 10.36 does not introduce a parallel API error hierarchy.

Canonical errors propagate unchanged from their owning subsystem, including registry, loader, validation, resolution, operation, permission, workflow, session, conflict and trace failures.

Examples:

```text
DomainRegistryError
DomainLoaderError
DomainResolutionError
DomainOperationError
DomainSessionError
DomainTraceError
```

The facade MUST NOT catch a precise canonical error only to replace it with a generic `DomainAPIError`.

Invalid construction/wiring of `DefaultDomainAPI` may use ordinary `TypeError`/`ValueError` unless a genuinely API-specific coordination failure is discovered during implementation.

Any new API-specific error requires explicit justification and must not obscure the original canonical cause.

---

## 19. Mutation boundaries

Read-only API methods MUST be observational only:

```text
list_domains
get_domain
discover_domains
validate_domain
get_capabilities
get_resources
get_rules
get_operations
get_workflows
get_session
validate_trace
```

Mutating or executing methods are only:

```text
install_domain
enable_domain
disable_domain
execute_operation
start_workflow
resume_session
```

`resolve_domain`, `resolve_conflict` and `assemble_trace` produce derived canonical results but do not gain authority to mutate unrelated runtime state.

The facade itself MUST NOT maintain mutation history or shadow state.

---

## 20. Public exports

The stable Phase 10.36 public API MUST be intentionally exportable from the Domain package.

At minimum:

```text
DomainAPI
DefaultDomainAPI
```

must be available through the agreed public Domain import surface.

Adding the facade MUST NOT require import-time registry mutation, filesystem access, model calls, network access or runtime execution.

A fresh import must remain side-effect free.

---

## 21. CLI boundary

Phase 10.36 defines the stable Python Domain API.

Expansion of:

```text
cmm domain ...
```

beyond the four Phase 10.35 SDK commands is not required for Phase 10.36 unless a later implementation decision explicitly assigns a CLI command to this phase.

The Python API must not be distorted merely to serve argparse.

CLI and API remain separate adapters over the same canonical runtime contracts.

---

## 22. Compatibility and security invariants

Phase 10.36 MUST preserve all previously closed Domain invariants.

At minimum:

```text
install != enable
load != authorization
persisted state != current authorization
persisted state != current truth
proposal != mutation
preparation != external communication
```

Additionally:

- canonical permission gates remain authoritative;
- canonical approval requirements remain authoritative;
- operation rollback remains owned by the operation orchestrator;
- workflow execution remains owned by canonical workflow infrastructure;
- Domain Sessions remain extensions of the shared session boundary;
- `DomainConflictResolver` remains pure;
- traces remain reference-only;
- no credentials or private payloads are copied into trace metadata;
- no API-specific cache may override current canonical registry state.

The general Domain event catalog must remain exactly 23 unique general events.

`domain.session.resumed` must remain absent.

Phase 10.36 MUST NOT add that event as a shortcut for API observability.

---

## 23. Determinism

Equivalent calls against equivalent canonical state must return equivalent semantic results.

The API MUST NOT introduce nondeterminism through:

- unordered API-side aggregation;
- implicit current-directory discovery;
- hidden singleton state;
- wall-clock-derived IDs outside canonical owning components;
- API-specific fallback selection.

Ordering must follow existing canonical contracts.

---

## 24. Acceptance target — DP-036

Phase 10.36 establishes:

```text
DP-036 — Domain API
```

Acceptance intent:

> CMM OS exposes one stable public coordination facade through which callers can inspect and use Domain Intelligence capabilities while the existing canonical Domain subsystems remain authoritative and all permission, execution, persistence, conflict and trace boundaries remain intact.

The requirements matrix should add the canonical `DP-036` mapping during implementation documentation once the actual symbols exist.

Before implementation it MUST NOT be marked `VERIFIED_EXISTING`.

---

## 25. Connected acceptance — AT-DP-036

`AT-DP-036` must exercise the real facade through canonical components.

Minimum connected scenario:

```text
discover
  ↓
validate
  ↓
install
  ↓
prove installed != enabled
  ↓
list / get
  ↓
enable
  ↓
inspect capabilities/resources/rules/operations/workflows
  ↓
resolve
  ↓
execute one operation through canonical operation orchestration
  ↓
start one workflow through canonical workflow execution
  ↓
get a domain session from shared session persistence
  ↓
resume it through DomainSessionResumer
  ↓
resolve a conflict through pure DomainConflictResolver
  ↓
assemble a reference-only DomainTrace
  ↓
validate the trace against canonical inventory
  ↓
disable
```

The acceptance must use real canonical collaborators or the repository's canonical in-memory implementations.

Mocks/spies may observe boundaries but MUST NOT replace the behavior being accepted.

---

## 26. Required adversarial coverage

Tests must prove at minimum:

- install does not implicitly enable;
- install does not implicitly authorize;
- untrusted installation remains blocked by default;
- read-only API calls do not mutate registries;
- validation does not install;
- direct operation implementation bypass is impossible through the facade;
- missing permission/approval still blocks execution;
- workflow start uses the canonical workflow executor;
- session lookup does not create a session;
- persisted session state cannot grant current authorization;
- conflict resolution does not mutate its input;
- trace assembly creates no hidden persistence;
- trace validation remains reference-only;
- facade instances do not create shadow registry truth;
- canonical subsystem exceptions retain their type;
- fresh API import has no runtime side effects.

---

## 27. Test strategy

Implementation follows TDD.

Focused tests should cover:

```text
tests/domains/test_domain_api_contracts.py
tests/domains/test_domain_api_queries.py
tests/domains/test_domain_api_lifecycle.py
tests/domains/test_domain_api_execution.py
tests/domains/test_domain_api_sessions.py
tests/domains/test_domain_api_conflicts.py
tests/domains/test_domain_api_traces.py
tests/domains/test_domain_api_dp036_acceptance.py
```

The implementation plan may merge files where that improves clarity, but must keep query, lifecycle, execution and persistence boundaries independently testable.

Mandatory regression coverage includes the existing canonical tests for:

- registry;
- loader;
- discovery;
- validation;
- resolver;
- operation execution and transactions;
- permission gates;
- workflows;
- sessions;
- conflict resolution;
- traces;
- Domain SDK public API.

Full Domain and repository suites remain final implementation gates.

---

## 28. Documentation requirements

Implementation must ultimately update:

```text
docs/reference/domain-api.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
ROADMAP.md
```

Before independent audit, documentation may state only:

```text
Phase 10.36 implementation complete — independent audit pending
DP-036 = IMPLEMENTED_PENDING_AUDIT
AT-DP-036 = PASS
```

It MUST NOT claim:

```text
independently audited
closed
final PASS
```

until independent audit actually succeeds.

---

## 29. Non-goals

Phase 10.36 does not implement:

- another Domain Runtime;
- another Domain Registry;
- another Domain Loader;
- another Domain Resolver;
- another Domain Validation pipeline;
- another permission system;
- another operation executor;
- another workflow engine;
- another session store;
- a trace store;
- durable package installation;
- package publication;
- a marketplace;
- remote package distribution;
- global session search;
- persistent trace lookup;
- API authentication/HTTP transport;
- REST;
- GraphQL;
- MCP;
- UI;
- network services;
- provider routing;
- model routing;
- autonomous permission grants;
- implicit enablement;
- implicit authorization.

Those require separate explicit architecture where applicable.

---

## 30. Completion criteria

Phase 10.36 implementation is ready for independent audit only when:

1. `DomainAPI` and `DefaultDomainAPI` expose the approved surface.
2. Every method delegates to an existing canonical owner.
3. No parallel runtime/registry/loader/resolver/executor/store exists.
4. Installation is canonical runtime load/registration only.
5. Installation does not imply enablement or authorization.
6. Read-only API methods are mutation-free.
7. Operation execution uses the authoritative orchestrator path.
8. Workflow execution uses canonical workflow infrastructure.
9. Session access remains on the shared session boundary.
10. Conflict resolution remains pure.
11. Trace handling remains reference-only and persistence-independent.
12. Canonical errors remain visible.
13. `AT-DP-036` passes as a connected real-component acceptance test.
14. Adversarial API boundary tests pass.
15. Existing closed Domain regressions remain green.
16. General event catalog remains 23/23 unique.
17. `domain.session.resumed` remains absent.
18. Ruff, format, compile and diff hygiene pass.
19. Domain suite passes.
20. Full repository suite passes.
21. Worktree is clean.
22. The independent-audit bundle is generated from exact committed HEAD.

Only after independent audit PASS may Phase 10.36 be marked closed.
