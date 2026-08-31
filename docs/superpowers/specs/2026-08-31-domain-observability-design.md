# Phase 10.37 — Domain Observability Design

**Date:** 2026-08-31
**Status:** Design approved for repository commit; implementation not started
**Phase:** 10.37 — Observability
**Branch:** `feature/phase-10-domain-intelligence`
**Base HEAD:** `a9a4184575900be9113a467ccee43772465673ce`
**Previous boundary:** Phase 10.36 — Domain API, complete, independently audited and closed
**Next boundary:** Phase 10.38 — Security
**Design Point:** `DP-037`
**Acceptance Test:** `AT-DP-037`

---

## 1. Purpose

Phase 10.37 makes Domain Intelligence observable without introducing another
observability platform.

The roadmap objective is to measure how domains are discovered, loaded,
selected, combined and used, and to expose a per-domain health result.

The implementation MUST treat already-existing Domain Intelligence evidence as
authoritative. Phase 10.37 therefore provides a deterministic, read-only
projection over canonical events, traces, sessions, registries and public
results.

The defining success criterion is:

> Given canonical Domain Intelligence evidence, CMM OS can produce
> privacy-minimized structured observability logs, exact metrics when evidence
> exists, explicit unavailability when evidence does not exist, and a
> fail-closed per-domain health result, without creating a second event bus,
> trace system, store, runtime, resolver, registry or source of truth.

Phase 10.37 is not a replacement for Phase 7 Validation Observability, Phase 9
Agent Observability or the future Phase 11 platform-wide observability layer.

---

## 2. Repository baseline and inspected evidence

The design is based on the Phase 10.37 repository inspection executed against:

```text
BRANCH=feature/phase-10-domain-intelligence
HEAD=a9a4184575900be9113a467ccee43772465673ce
WORKTREE=CLEAN
PHASE10_36_CLOSURE=VERIFIED
QUARANTINE_STASH=PRESERVED
DESIGN_STARTED=NO
IMPLEMENTATION_STARTED=NO
```

The inspection identified existing observability-like infrastructure including:

```text
cmm/agent_runtime/agent_observability_contracts.py
cmm/agent_runtime/agent_observability_enums.py
cmm/agent_runtime/agent_observability_errors.py
cmm/agent_runtime/agent_observability_service.py
cmm/agent_runtime/agent_observability_store.py
cmm/agent_runtime/agent_trace_*.py
cmm/agent_runtime/runtime_event_*.py
cmm/validation/observability/
cmm/domains/event_catalog.py
cmm/domains/event_contracts.py
cmm/domains/event_factory.py
cmm/domains/event_publisher.py
cmm/domains/event_adapters.py
cmm/domains/trace_contracts.py
cmm/domains/trace_assembler.py
cmm/domains/trace_validation.py
```

This inventory is a hard architectural constraint.

Phase 10.37 MUST NOT recreate any of those systems under Domain-specific names.

---

## 3. Canonical roadmap requirements

Phase 10.37 must cover the roadmap objective:

```text
measure how domains are selected, combined and used
```

The roadmap expects observability around:

- discovered domains;
- loaded domains;
- loading failures;
- resolution;
- resolution confidence;
- composition;
- conflicts;
- profiles;
- rules;
- resources;
- operations;
- workflows;
- permissions;
- approvals;
- multi-domain transfers;
- results;
- duration;
- errors;
- memory-related evidence.

The initial metric vocabulary includes:

- installed domains;
- active domains;
- load time;
- load failures;
- decisions by domain;
- average resolution confidence;
- ambiguous resolutions;
- fallback usage;
- multi-domain executions;
- mean domains per execution;
- domain conflicts;
- rejected permissions;
- approvals requested;
- operations by domain;
- workflows by domain;
- workflow duration;
- domain rules;
- loaded resources;
- multi-domain transfers;
- reused knowledge;
- questions avoided by sharing context;
- duplicates prevented;
- errors by Domain Pack;
- degraded sessions;
- active external domains.

The roadmap also requires a per-domain health explanation equivalent to:

```python
DomainHealthResult(
    domain_id="domain:health",
    status="healthy",
    manifest=True,
    registry=True,
    resources=True,
    rules=True,
    operations=True,
    workflows=True,
    permissions=True,
    dependencies=True,
    last_checked_at="...",
    findings=[],
    metadata={},
)
```

These requirements define the vocabulary. They do not authorize creation of a
parallel logging or metrics backend.

---

## 4. Architectural decision

### 4.1 Selected approach — derived Domain Observability projection

Phase 10.37 will implement a thin, read-only Domain Observability layer that
derives its outputs from canonical evidence.

```text
Canonical Domain Intelligence truth
│
├── Domain Registry / Loader / Validation
├── Domain Resolution / Selection Policies
├── Domain Composition / Conflict Resolution
├── Domain Events
├── Domain Trace
├── Domain Sessions
├── Permissions / Approvals
├── Operations / Workflows
└── Shared Memory proposal/reference evidence
        │
        ▼
Domain Observability projection
        │
        ├── reference-only log entries
        ├── deterministic metric snapshot
        └── DomainHealthResult
```

The projection owns no operational truth.

It MUST NOT alter the evidence it observes.

### 4.2 Rejected alternative — standalone Domain observability backend

Rejected:

```text
DomainObservabilityStore
DomainObservabilityRepository
DomainObservabilityEventBus
DomainObservabilityTraceStore
```

Reason:

- duplicates Phase 7/9 infrastructure;
- creates a second source of truth;
- risks divergence from Domain Events and Domain Trace;
- adds persistence not requested by Phase 10.37;
- violates the repository's established anti-fragmentation architecture.

### 4.3 Rejected alternative — reuse Agent Observability as the Domain backend

Rejected as the base architecture.

Agent Observability is owned by Phase 9 and models Agent Runtime telemetry,
metrics and audit records. Domain Intelligence must not become semantically
owned by the Agent Runtime merely to gain metrics.

Phase 10.37 MAY reuse small generic implementation patterns where dependency
direction remains valid, but it MUST NOT make Domain observability depend on an
Agent-specific store or Agent-specific metric contract.

### 4.4 Rejected alternative — extend Validation Observability into Domain truth

Rejected as the base architecture.

Validation Observability measures validation execution. Domain Observability
measures Domain Intelligence selection, composition and use.

The two may coexist and correlate through references, but neither owns the
other's domain model.

---

## 5. Core invariant

The central invariant is:

```text
Domain observability output
=
deterministic projection of canonical public evidence

Domain observability output
!=
new operational truth
```

Corollaries:

1. metrics MUST NOT drive Domain Resolution;
2. metrics MUST NOT change Domain Composition;
3. metrics MUST NOT resolve conflicts;
4. health checks MUST NOT enable, disable, load, reload or repair domains;
5. observability MUST NOT grant permissions;
6. observability MUST NOT approve actions;
7. observability MUST NOT execute operations or workflows;
8. observability MUST NOT write memory;
9. observability MUST NOT persist copied sensitive payloads;
10. absence of evidence MUST NOT be converted into a guessed metric.

---

## 6. Existing canonical infrastructure to reuse

Phase 10.37 MUST reuse the repository's current canonical owners.

### 6.1 Domain lifecycle and registry truth

Reuse the canonical equivalents of:

- `DomainRegistry`;
- `DomainQuery`;
- `DomainDefinition`;
- `DomainRegistryRecord`;
- Domain statuses and enablement state;
- Domain kind/source metadata;
- Domain discovery results;
- `DomainLoadResult`;
- Domain validation results;
- dependency/conflict information.

The Registry remains authoritative for current installed/registered/active
state.

The Loader remains authoritative for load outcomes.

Observability does not maintain an independent installed-domain inventory.

### 6.2 Resolution and composition truth

Reuse the canonical equivalents of:

- `DomainResolutionContext`;
- `DomainResolutionResult`;
- Phase 10.31 Domain Selection Policies;
- `DomainComposition`;
- composition results;
- Phase 10.32 conflict contracts and resolution results.

Phase 10.37 MUST NOT re-run scoring logic merely to compute a metric.

A resolution metric is derived from the resolution outcome already produced by
the authoritative resolver.

### 6.3 Domain Events

Phase 10.33 remains the canonical Domain lifecycle/integration event boundary.

Reuse:

- exact canonical 23-event general catalog;
- `DomainEvent`;
- `DomainEventReference`;
- `DomainEventFactory`;
- Domain lifecycle adapters;
- Domain-to-Kernel publication boundary.

Phase 10.37 MUST NOT add a second general Domain event catalog.

It MUST NOT change the meaning of an existing event merely to satisfy a metric.

If new event evidence is genuinely required, it must be added only by extending
the existing Phase 10.33 event architecture under its existing namespace and
validation rules. Any such extension must preserve the exact closed invariant
that the general built-in catalog remains 23/23 unless the Phase 10.33 contract
is explicitly amended before implementation.

The preferred design is to avoid new events and derive metrics from already
available events and public results.

### 6.4 Domain Trace

Phase 10.17 remains authoritative for the final reference-only Domain Trace.

Reuse trace references for:

- resolution;
- composition;
- participating domains;
- resource resolution;
- profiles;
- rule execution;
- operation results;
- workflow results;
- permissions;
- approvals;
- cross-domain results;
- memory proposals;
- final status;
- duration.

Phase 10.37 MUST NOT create `DomainObservabilityTrace`.

### 6.5 Domain Sessions

Phase 10.34 remains authoritative for Domain session continuity through the
shared session infrastructure.

Reuse:

- `DomainSessionContext`;
- `SharedSessionDomainAdapter`;
- current session status/revision;
- canonical degraded or blocked session evidence when it exists.

Phase 10.37 MUST NOT create a `DomainSessionRepository` or enumerate sessions
through a new store.

### 6.6 Domain API

Phase 10.36 remains the runtime-facing public coordination facade.

Phase 10.37 MUST NOT expand or alter the `DomainAPI` protocol as a requirement
of this phase.

No new REST/HTTP/GraphQL/MCP endpoints are required.

Future external exposure belongs to Phase 11 unless a later explicit design
amends this boundary.

### 6.7 Phase 7 and Phase 9 observability

Phase 10.37 may correlate with:

- Validation Observability;
- Agent Runtime observability;
- Agent traces;
- runtime events.

It must do so through IDs/references and stable public contracts.

It must not copy their internal stores.

---

## 7. Proposed public Domain Observability surface

The implementation should remain small.

The preferred public surface is:

```text
DomainObservabilityLogEntry
DomainMetricStatus
DomainMetricBucket
DomainMetricMeasurement
DomainMetricsSnapshot
DomainHealthStatus
DomainHealthFinding
DomainHealthResult
DomainObservabilityReport
DomainMetricsCalculator
DomainHealthChecker
DomainObservabilityService
```

Exact names may be adjusted only if repository naming conventions discovered
during implementation make an equivalent name clearly canonical. The semantics
below are normative.

No store, repository, bus, registry, runtime, engine or resolver is part of the
approved design.

---

## 8. DomainObservabilityLogEntry

`DomainObservabilityLogEntry` is a derived, immutable, privacy-minimized read
model.

It is not a persisted log record.

Conceptual contract:

```python
DomainObservabilityLogEntry(
    source_kind="domain_event",
    source_id="domain-event-123",
    category="resolution",
    status="completed",
    occurred_at="2026-08-31T12:00:00+00:00",
    primary_domain="domain:health",
    supporting_domains=("domain:general",),
    session_id="session-123",
    duration_ms=12,
    reference_ids=(
        "domain-resolution-123",
        "domain-trace-123",
    ),
    metadata={},
)
```

### Required properties

- frozen/immutable;
- deterministic field ordering;
- timezone-aware timestamps;
- JSON-safe serialization;
- reference-first;
- no raw user input;
- no prompt capture;
- no chain-of-thought;
- no copied knowledge payload;
- no copied resource body;
- no credentials or secrets;
- no silent confidence reconstruction;
- no synthetic duration.

### Source precedence

A log entry may be derived from:

1. canonical `DomainEvent`;
2. canonical `DomainTrace`;
3. canonical public operation/workflow/session result when no event/trace
   represents the required roadmap field.

The same authoritative occurrence MUST NOT be double-counted merely because it
appears in both an event and a trace.

Deduplication must use explicit source/reference identity, not fuzzy matching.

---

## 9. Metric model

### 9.1 Principle

Metrics are deterministic projections.

Every metric must have one of two states:

```text
OBSERVED
UNAVAILABLE
```

`UNAVAILABLE` is not zero.

`UNAVAILABLE` means Phase 10.37 does not possess sufficient canonical evidence
to calculate the value honestly.

### 9.2 DomainMetricStatus

Conceptual values:

```text
observed
unavailable
```

No `estimated`, `guessed`, `inferred_from_text` or probabilistic state is
permitted in Phase 10.37.

### 9.3 DomainMetricBucket

Used for deterministic breakdowns such as counts by domain.

```python
DomainMetricBucket(
    key="domain:health",
    value=12,
)
```

Buckets MUST be canonically sorted.

### 9.4 DomainMetricMeasurement

Conceptual contract:

```python
DomainMetricMeasurement(
    name="resolution.decisions_by_domain",
    status="observed",
    value=None,
    unit="count",
    buckets=(
        DomainMetricBucket(key="domain:general", value=3),
        DomainMetricBucket(key="domain:health", value=7),
    ),
    evidence_reference_ids=(
        "domain-event-001",
        "domain-event-002",
    ),
    unavailable_reason=None,
    metadata={},
)
```

Rules:

- scalar metrics use `value`;
- breakdown metrics use `buckets`;
- an observed metric cannot simultaneously claim no evidence;
- an unavailable metric must include a stable reason code/message;
- unavailable metrics do not use zero as a placeholder;
- evidence references must be public IDs only;
- metadata must remain privacy-minimized and JSON-safe.

### 9.5 DomainMetricsSnapshot

Conceptual contract:

```python
DomainMetricsSnapshot(
    generated_at="...",
    measurements=(...),
    evidence_event_ids=(...),
    evidence_trace_ids=(...),
    evidence_session_ids=(...),
    digest="...",
    metadata={},
)
```

The snapshot:

- is immutable;
- is deterministic for the same canonical evidence and injected clock;
- has a canonical metric ordering;
- carries an integrity digest over its public serialized form;
- contains no independent persistence semantics.

---

## 10. Canonical Phase 10.37 metric catalog

The implementation SHOULD define one constant canonical metric catalog, not a
runtime registry.

The initial names and semantics are:

| Metric | Type | Authoritative evidence |
| --- | --- | --- |
| `domains.installed` | scalar count | canonical Domain Registry/runtime definitions |
| `domains.active` | scalar count | canonical registry status/enablement |
| `loading.duration.mean_ms` | scalar mean | explicit successful/failed load durations |
| `loading.failures` | scalar count | explicit load failure results/events |
| `resolution.decisions_by_domain` | buckets | canonical resolution results/events |
| `resolution.confidence.mean` | scalar mean | explicit resolution confidence only |
| `resolution.ambiguous` | scalar count | explicit ambiguous resolution status |
| `resolution.fallback` | scalar count | explicit fallback evidence only |
| `execution.multi_domain` | scalar count | trace/composition with more than one participating domain |
| `execution.domains.mean` | scalar mean | canonical participating-domain counts |
| `conflicts.detected` | scalar count | canonical conflict cases/events |
| `permissions.rejected` | scalar count | canonical denied permission decisions/events |
| `approvals.requested` | scalar count | canonical approval request evidence |
| `operations.by_domain` | buckets | canonical operation lifecycle/results |
| `workflows.by_domain` | buckets | canonical workflow lifecycle/results |
| `workflows.duration.mean_ms` | scalar mean | explicit workflow timing evidence |
| `rules.applied_by_domain` | buckets | Domain Trace rule references/results |
| `resources.loaded_by_domain` | buckets | canonical resource-resolution/load references |
| `cross_domain.transfers` | scalar count | explicit cross-domain transfer evidence |
| `knowledge.reused` | scalar count | explicit reuse evidence only |
| `questions.avoided_shared_context` | scalar count | explicit avoided-question evidence only |
| `duplicates.prevented` | scalar count | explicit deduplication evidence only |
| `errors.by_domain_pack` | buckets | explicit domain-attributed errors |
| `sessions.degraded` | scalar count | canonical degraded session evidence |
| `external_domains.active` | scalar count | canonical active external-domain state |

### 10.1 Metrics that MUST NOT be inferred by proxy

The following rules are mandatory:

```text
primary domain == domain:general
does NOT automatically mean fallback

supporting_domains > 0
does NOT automatically mean a cross-domain transfer occurred

same knowledge reference in two traces
does NOT automatically mean knowledge was reused

absence of repeated questions
does NOT mean a question was avoided

absence of duplicate objects
does NOT mean a duplicate was prevented
```

If the authoritative evidence does not explicitly support these semantics, the
corresponding metric is `UNAVAILABLE`.

### 10.2 Zero versus unavailable

Examples:

```text
0 rejected permissions
=
there is authoritative permission-decision evidence and no rejection occurred

permissions.rejected unavailable
=
no authoritative permission-decision evidence was supplied
```

This distinction is required for auditability.

---

## 11. Metrics calculation rules

`DomainMetricsCalculator` must be pure.

Conceptual responsibility:

```text
canonical evidence in
↓
validate evidence identity and chronology
↓
deduplicate by authoritative IDs
↓
calculate exact measurements
↓
mark unsupported measurements unavailable
↓
canonicalize ordering
↓
compute digest
↓
DomainMetricsSnapshot out
```

It MUST NOT:

- publish events;
- mutate registries;
- load domains;
- resume sessions;
- execute workflows;
- execute operations;
- resolve domains;
- resolve conflicts;
- update memory;
- query external systems;
- persist snapshots.

### 11.1 Time-window behavior

If the implementation exposes a time range:

- both bounds must be timezone-aware;
- end must not precede start;
- only explicit occurrence timestamps may be filtered;
- no timestamp may be synthesized from current time except
  `generated_at`;
- metric meaning must not depend on local timezone formatting.

### 11.2 Mean calculations

Means must:

- use only observed numeric samples;
- never treat missing values as zero;
- be `UNAVAILABLE` when no observed sample exists;
- have deterministic numeric behavior;
- document rounding if rounding is exposed.

---

## 12. Domain health model

### 12.1 DomainHealthStatus

Canonical semantic states:

```text
healthy
degraded
unhealthy
unknown
```

Meaning:

- `healthy`: every required health dimension is positively verified and there
  is no blocking finding;
- `degraded`: the domain remains usable but one or more required dimensions
  have a non-blocking failure or cannot be fully verified;
- `unhealthy`: a blocking integrity/runtime prerequisite fails;
- `unknown`: the requested domain or required health evidence cannot be
  evaluated without inventing state.

### 12.2 DomainHealthFinding

Conceptual contract:

```python
DomainHealthFinding(
    code="DOMAIN_HEALTH_PERMISSION_POLICY_UNVERIFIED",
    component="permissions",
    severity="warning",
    message="Permission policy could not be positively verified",
    reference_ids=("domain:health",),
    blocking=False,
    metadata={},
)
```

Findings:

- are structured;
- never copy secret values;
- never echo unsafe payloads;
- use stable codes;
- identify the affected component;
- distinguish warning from blocking failure.

### 12.3 DomainHealthResult

The public result preserves the roadmap fields:

```python
DomainHealthResult(
    domain_id="domain:health",
    status="healthy",
    manifest=True,
    registry=True,
    resources=True,
    rules=True,
    operations=True,
    workflows=True,
    permissions=True,
    dependencies=True,
    last_checked_at="...",
    findings=(),
    metadata={},
)
```

The booleans are positive-verification flags.

They MUST NOT mean "no error happened while checking".

For every boolean:

```text
True
=
canonical evidence positively verifies the dimension

False
=
the dimension failed OR could not be positively verified
```

The distinction between failure and unavailable verification is preserved in
`findings`.

---

## 13. Domain health dimensions

### 13.1 manifest

`manifest=True` only when canonical manifest/validation evidence positively
verifies the currently registered Domain version.

Observability MUST NOT parse an arbitrary package path independently if a
canonical loader/validator result exists.

### 13.2 registry

`registry=True` only when the current canonical Domain Registry can resolve the
Domain definition/record consistently.

A missing or contradictory registry record is blocking.

### 13.3 resources

`resources=True` only when declared resource IDs can be resolved through the
canonical resource infrastructure required for the Domain.

The health checker must not instantiate a parallel resource registry.

### 13.4 rules

`rules=True` only when declared required rules can be resolved through the
canonical rule infrastructure.

Optional unavailable rules must be handled according to the Domain definition,
not automatically treated as blocking.

### 13.5 operations

`operations=True` means declared operation contracts are registered consistently.

It does not mean every operation is executable.

A deliberately `UNAVAILABLE` operation may still be structurally healthy when
the Domain contract declares that state legitimately.

Health MUST NOT equate operational availability with structural registration.

### 13.6 workflows

`workflows=True` means declared workflow contracts are registered consistently.

It does not execute a workflow as a health probe.

### 13.7 permissions

`permissions=True` means the Domain's current permission contract/policy can be
resolved and is structurally valid.

It does not mean a specific user is authorized for every Domain operation.

Health MUST NOT grant permissions.

### 13.8 dependencies

`dependencies=True` only when required Domain dependencies are present and
compatible according to canonical dependency semantics.

Optional dependencies may produce degraded findings when appropriate but must
not be silently promoted to required dependencies.

---

## 14. DomainHealthChecker

`DomainHealthChecker` is read-only.

Conceptual flow:

```text
domain_id
↓
canonical registry lookup
↓
existing manifest/validation evidence
↓
canonical component registries
↓
canonical dependency state
↓
structured findings
↓
DomainHealthResult
```

It MUST NOT:

- install;
- load;
- reload;
- unload;
- enable;
- disable;
- mutate permissions;
- repair registrations;
- run arbitrary Domain code;
- execute operations;
- execute workflows;
- create sessions;
- persist health state.

Health checks are observations, not remediation.

---

## 15. DomainObservabilityReport

The report is an ephemeral aggregate for one observability request.

Conceptual contract:

```python
DomainObservabilityReport(
    generated_at="...",
    log_entries=(...),
    metrics=DomainMetricsSnapshot(...),
    health_results=(...),
    source_event_ids=(...),
    source_trace_ids=(...),
    source_session_ids=(...),
    findings=(...),
    digest="...",
    metadata={},
)
```

The report is:

- immutable;
- reference-first;
- deterministic apart from an injected generation clock;
- JSON-safe;
- serializable;
- not a stored audit log;
- not a replacement for `DomainTrace`;
- not a replacement for Phase 9 audit records.

---

## 16. DomainObservabilityService

The service coordinates projection only.

Preferred conceptual methods:

```python
class DomainObservabilityService:
    def build_report(...canonical evidence...) -> DomainObservabilityReport:
        ...

    def calculate_metrics(...canonical evidence...) -> DomainMetricsSnapshot:
        ...

    def check_domain_health(domain_id: str, ...) -> DomainHealthResult:
        ...
```

The service may compose pure helpers.

It MUST NOT own:

- a store;
- a repository;
- a bus;
- a runtime;
- a registry;
- a resolver;
- a loader;
- a workflow engine;
- an operation executor.

Dependency injection should use existing canonical owners directly.

No dependency should be created merely to make testing convenient if an
official in-memory implementation already exists.

---

## 17. Observability log category mapping

The normalized read model may use stable categories such as:

```text
discovery
loading
resolution
composition
conflict
profile
rule
resource
operation
workflow
permission
approval
cross_domain
result
session
memory
error
```

These are projection categories.

They are not a new event namespace.

A `DomainEvent.event_type` remains authoritative.

The category merely allows observability consumers to group already-existing
evidence.

---

## 18. Data ownership and dependency direction

Required dependency direction:

```text
Domain Registry / Loader / Resolver / Composer / Sessions / Execution
                         │
                         ├── Domain Events
                         │
                         └── Domain Trace / public results
                                  │
                                  ▼
                         Domain Observability
```

Forbidden direction:

```text
Domain Resolver
      ↓
Domain Observability metrics
      ↓
decision
```

Operational components MUST NOT consult Phase 10.37 metrics to decide behavior.

Observability remains downstream.

---

## 19. Privacy and security boundary

Phase 10.37 deals with cross-cutting operational evidence and therefore has a
strict minimization requirement.

### 19.1 Prohibited content

Observability output MUST NOT contain:

- passwords;
- API keys;
- tokens;
- cookies;
- credentials;
- authorization headers;
- private prompts;
- hidden reasoning;
- chain-of-thought;
- raw sensitive user messages when a reference is sufficient;
- full medical/relationship/legal/financial resource bodies;
- copied KnowledgeItems merely for metric calculation;
- copied memory content;
- arbitrary exception payloads that may contain secrets.

### 19.2 Allowed evidence

Prefer:

- stable IDs;
- Domain IDs;
- event types;
- statuses;
- public reason codes;
- counts;
- durations;
- confidence values already exposed by authoritative results;
- public sensitivity labels;
- public permission IDs;
- trace IDs;
- session IDs where authorized;
- operation/workflow IDs.

### 19.3 Metric labels

Metric names and bucket keys MUST NOT become a covert PII channel.

Allowed bucket keys for the Phase 10.37 canonical catalog are primarily stable
Domain IDs and stable public categories.

User-generated text must not become a metric label.

### 19.4 Error sanitization

Malformed or unsafe evidence must fail closed.

Diagnostics should identify:

- source type;
- safe source ID when available;
- stable error code;
- affected field/component.

Diagnostics must not echo unsafe values.

---

## 20. Error semantics

Phase 10.37 errors should extend the existing canonical Domain error family in
`cmm/domains/errors.py`.

The design does not authorize a separate errors package.

Expected semantic categories include:

```text
invalid observability evidence
invalid metric contract
duplicate/conflicting evidence identity
unsafe observability payload
invalid health-check contract
unsupported metric evidence
```

Unsupported evidence for a metric normally produces an `UNAVAILABLE`
measurement rather than an exception.

An exception is appropriate when the supplied evidence is malformed,
contradictory at the identity level, unsafe or violates a public contract.

---

## 21. Determinism and integrity

All new contracts must follow established Phase 10 deterministic conventions.

Required:

- frozen/slotted dataclasses where consistent with adjacent contracts;
- stable serialization;
- canonical tuple ordering;
- no mutable alias leakage;
- timezone-aware datetimes;
- deterministic injected clock for tests;
- deterministic digest;
- no random ID generation in pure calculators;
- side-effect-free imports.

If a report/snapshot ID is introduced, it must be content-bound or supplied
through an injectable deterministic factory.

A random opaque ID generated inside a pure calculator is not approved.

---

## 22. Relationship with Phase 10.33 Domain Events

Phase 10.37 consumes existing Domain Events as evidence.

It does not redefine them.

The exact 23-event general catalog remains a regression invariant.

The implementation MUST include a guard proving:

```text
len(CANONICAL_DOMAIN_EVENTS) == 23
len(set(CANONICAL_DOMAIN_EVENTS)) == 23
```

and that Phase 10.37 imports do not register, publish or mutate event state.

If a roadmap metric cannot be derived from the existing event catalog, the
first response is `UNAVAILABLE`, not silent event-semantic expansion.

Any change to the Phase 10.33 event contract requires a separate explicit
design amendment before implementation.

---

## 23. Relationship with Domain Trace

`DomainTrace` already provides the canonical final reference-only execution
aggregate.

Phase 10.37 must prefer trace references for "what participated" questions.

Examples:

- primary/supporting domains;
- profile references;
- rule references;
- resources;
- operations;
- workflows;
- permissions;
- approvals;
- cross-domain results;
- memory proposals;
- status;
- duration.

Phase 10.37 MUST NOT copy traced upstream result payloads into an observability
report.

---

## 24. Relationship with Domain Sessions

Domain session persistence remains owned by the shared session store.

Phase 10.37 may observe a supplied canonical session context/result.

It MUST NOT:

- scan the shared session store globally;
- create its own session index;
- mutate a session to mark it observed;
- resume a session as a health check;
- treat persisted session state as current authorization.

The Phase 10.34 invariant remains:

```text
Persisted domain snapshot
!=
current authorization or current truth
```

---

## 25. Relationship with Domain API

Phase 10.36 explicitly established that the API is a thin facade over canonical
owners and does not create parallel stores.

Phase 10.37 preserves that closure.

No change to `DomainAPI` is necessary to satisfy `DP-037`.

An implementation MAY export Phase 10.37 contracts/services from
`cmm.domains` as a Python public surface, following existing Phase 10
conventions.

Network/API exposure is outside this phase.

---

## 26. Relationship with Phase 11 Observability

Phase 11 owns platform-wide observability such as:

- central structured logs;
- platform metrics;
- distributed tracing;
- dashboards;
- alerts;
- model/provider telemetry;
- integration health;
- storage health;
- plugin health;
- complete request correlation.

Phase 10.37 provides Domain Intelligence-specific read models that Phase 11 may
later consume.

Phase 10.37 MUST NOT pre-implement Phase 11 dashboards, alerting or
OpenTelemetry infrastructure.

---

## 27. Proposed implementation units

The implementation plan should prefer small files matching current
`cmm/domains/` conventions.

Preferred layout:

```text
cmm/domains/observability_contracts.py
    immutable log, metric, health and report contracts

cmm/domains/observability_metrics.py
    canonical metric catalog + pure DomainMetricsCalculator

cmm/domains/observability_health.py
    read-only DomainHealthChecker

cmm/domains/observability_service.py
    thin composition/orchestration of projections

cmm/domains/errors.py
    minimal extension of existing Domain error taxonomy if required

cmm/domains/__init__.py
    intentional public exports
```

The plan MAY collapse files if implementation inspection shows that a smaller
split better matches repository conventions.

The plan MUST NOT introduce files named or equivalent to:

```text
observability_store.py
observability_repository.py
observability_event_bus.py
observability_runtime.py
observability_engine.py
observability_registry.py
observability_loader.py
observability_trace.py
```

---

## 28. TDD strategy

Implementation is mandatory TDD:

```text
TEST RED
→ minimal implementation
→ GREEN
→ controlled refactor
→ next block
```

No production implementation should precede the failing test that requires it.

### 28.1 RED 1 — contracts

First RED should prove:

1. valid immutable `DomainMetricMeasurement`;
2. observed versus unavailable distinction;
3. unavailable cannot masquerade as zero;
4. deterministic `DomainMetricsSnapshot`;
5. valid `DomainHealthResult`;
6. timezone-aware timestamps;
7. JSON-safe/reference-first serialization.

### 28.2 RED 2 — metric calculation

Cover:

- installed domains;
- active domains;
- decisions by domain;
- mean resolution confidence;
- ambiguous resolution;
- explicit fallback;
- multi-domain executions;
- mean domains per execution;
- conflicts;
- rejected permissions;
- approvals;
- operations/workflows by domain;
- workflow duration;
- rules/resources;
- cross-domain transfers;
- errors by Domain Pack;
- degraded sessions;
- active external domains;
- unsupported metrics become unavailable.

### 28.3 RED 3 — anti-inference/adversarial metrics

Explicitly prove:

- General Domain selection alone is not counted as fallback;
- supporting domains alone are not counted as transfer;
- repeated reference alone is not counted as reused knowledge;
- missing duplicate alone is not counted as duplicate prevented;
- missing repeated question alone is not counted as question avoided;
- absent evidence is not converted to zero.

### 28.4 RED 4 — health

Cover:

- healthy Domain with all required components verified;
- missing registry record;
- missing required dependency;
- invalid/missing permission policy;
- unavailable optional dependency;
- intentionally unavailable operation does not automatically make the Domain
  unhealthy;
- health check performs no mutation;
- unknown Domain fails closed.

### 28.5 RED 5 — projection/deduplication/privacy

Cover:

- event + trace describing the same occurrence do not double count;
- canonical source ID deduplication;
- conflicting duplicate IDs fail closed;
- raw sensitive content is not copied;
- unsafe secret-like metadata is rejected;
- log ordering is deterministic;
- report digest is stable.

---

## 29. DP-037 — Domain Observability Projection

`DP-037` is:

> Domain Intelligence has one read-only observability projection that derives
> logs, metrics and per-domain health exclusively from existing canonical
> Domain evidence, distinguishes observed values from unavailable values,
> remains reference-first and privacy-minimized, and creates no parallel
> runtime, registry, loader, resolver, event bus, trace, session store,
> observability store or source of truth.

Required DP invariants:

```text
DP037-I01  Observability is downstream of authoritative Domain components.
DP037-I02  Domain Events remain the lifecycle event authority.
DP037-I03  Domain Trace remains the reference-only execution trace authority.
DP037-I04  Domain Sessions remain on shared session persistence.
DP037-I05  Domain Registry remains current Domain state authority.
DP037-I06  Metrics do not influence resolution/composition/execution.
DP037-I07  Health checks are read-only.
DP037-I08  Missing evidence is UNAVAILABLE, never guessed.
DP037-I09  UNAVAILABLE is distinct from zero.
DP037-I10  Observability is reference-first and privacy-minimized.
DP037-I11  No parallel observability persistence exists.
DP037-I12  Phase 10.33 general event catalog remains exactly 23/23.
DP037-I13  Phase 10.36 DomainAPI contract remains unchanged.
DP037-I14  Phase 11 platform observability remains out of scope.
```

---

## 30. AT-DP-037 — connected acceptance test

`AT-DP-037` MUST prove real behavior using canonical Domain components or their
official in-memory implementations.

Mocks of every dependency are insufficient.

The acceptance scenario should connect as many existing canonical components as
the repository supports without inventing new infrastructure.

### 30.1 Connected scenario

Target flow:

```text
canonical Domain registries
↓
real registered internal domains
↓
real Domain resolution result
↓
real Domain composition / multi-domain evidence
↓
real Domain Event construction/adaptation
↓
real Domain operation/workflow public results
↓
real permission/approval evidence
↓
real/shared Domain session evidence
↓
real Domain Trace
↓
Domain Observability projection
↓
DomainMetricsSnapshot
+
DomainHealthResult
↓
assert exact metrics, references, privacy and no mutation
```

### 30.2 Minimum acceptance checkpoints

`AT-DP-037` passes only if all of the following hold:

1. canonical internal domains are registered using existing registries;
2. at least one specialized Domain is active;
3. one real resolution outcome is consumed;
4. one explicit ambiguous or blocked resolution evidence path is covered;
5. one multi-domain composition/trace is consumed;
6. Domain Events use the Phase 10.33 contract;
7. the 23/23 general event catalog remains unchanged;
8. Domain Trace is used as reference-only evidence;
9. a shared Domain session object/result is consumed without new persistence;
10. permission evidence is consumed from the canonical permission boundary;
11. approval evidence is consumed from the canonical approval boundary;
12. operation evidence uses the canonical operation path/result;
13. workflow evidence uses canonical workflow infrastructure/result;
14. observed scalar metrics equal the actual evidence;
15. domain bucket metrics equal the actual evidence;
16. mean metrics ignore missing samples rather than treating them as zero;
17. explicit zero remains distinguishable from unavailable;
18. unsupported reuse/avoided-question/dedup metrics become `UNAVAILABLE` unless
    explicit authoritative evidence exists;
19. General Domain is not automatically counted as fallback;
20. a supporting Domain is not automatically counted as a transfer;
21. event/trace overlap does not double-count the same authoritative occurrence;
22. a healthy Domain positively verifies all required health dimensions;
23. a broken required dependency yields a non-healthy health result with a
    structured finding;
24. intentionally unavailable operation implementation does not by itself make
    structural operation registration unhealthy;
25. health checks mutate no registry, permission, session, workflow or
    operation state;
26. observability output contains no raw sensitive payload copied from
    resources/knowledge/memory;
27. unsafe secret-like data fails closed;
28. timestamps are timezone-aware;
29. serialization round-trips deterministically where the contract supports
    round-trip;
30. report/snapshot ordering and digest are deterministic;
31. imports are side-effect free;
32. no new store/repository/event bus/runtime/engine/registry/loader exists;
33. the `DomainAPI` public protocol is unchanged;
34. focused Phase 10.37 tests pass;
35. relevant Phase 10.17/10.31/10.32/10.33/10.34/10.36 regressions pass;
36. Domain suite passes;
37. global suite passes;
38. Ruff passes;
39. format check passes;
40. `compileall` passes;
41. `git diff --check` passes;
42. exact implementation HEAD is committed before audit;
43. audit bundle is generated from exact committed HEAD;
44. independent ChatGPT audit verifies `DP-037`;
45. independent ChatGPT audit verifies `AT-DP-037=PASS`.

---

## 31. Regression boundaries

At minimum, implementation verification must preserve the closed behavior of:

### Phase 10.17 — Domain Trace

- final reference-only aggregate;
- typed reference validation;
- no copied upstream content;
- deterministic ordering/digest.

### Phase 10.18 — Domain Memory Integration

- one shared memory;
- reference-only views/bindings;
- `READ != PROPOSE != APPROVE != APPLY`;
- no Domain-specific memory store.

### Phase 10.31 — Domain Selection Policies

- selection policy remains authoritative;
- observability never changes resolution scores;
- high-impact fail-closed behavior remains unchanged.

### Phase 10.32 — Domain Conflict Resolution

- resolver remains pure;
- unresolved cases cannot become resolved through observability;
- no observability-derived winner.

### Phase 10.33 — Domain Events

- exact 23-event general catalog;
- no AgentRuntimeEventBus dependency introduced;
- secret rejection;
- reference-first event payloads;
- pure components remain pure.

### Phase 10.34 — Domain Sessions

- shared session persistence only;
- no DomainSessionRepository;
- current authorization remains authoritative at resume;
- no new `domain.session.resumed` general event.

### Phase 10.35 — Domain SDK

- SDK test harness remains developer tooling;
- observability does not become a second test harness or packager.

### Phase 10.36 — Domain API

- thin facade remains thin;
- protocol remains unchanged by 10.37;
- no session enumeration;
- no trace store;
- no new persistence authority.

---

## 32. Required test and quality gates

Before Phase 10.37 may be marked implementation-complete/pending-audit, run:

1. focused Phase 10.37 contract tests;
2. focused metrics tests;
3. focused health-check tests;
4. adversarial privacy/deduplication tests;
5. `AT-DP-037`;
6. Phase 10.33 Domain Events regressions;
7. Phase 10.17 Domain Trace regressions;
8. Phase 10.31 selection-policy regressions;
9. Phase 10.32 conflict-resolution regressions;
10. Phase 10.34 Domain Sessions regressions;
11. Phase 10.36 Domain API regressions;
12. full Domain suite;
13. relevant Agent/Validation observability regressions if shared generic
    utilities are touched;
14. full global suite;
15. Ruff;
16. formatter check;
17. Python `compileall`;
18. `git diff --check`;
19. any repository-specific Phase 10 closure/portability gate already canonical
    at implementation time.

If a regression fails, implementation stops until it is resolved.

---

## 33. Documentation requirements

Implementation should add a dedicated reference document consistent with
existing Phase 10 patterns, for example:

```text
docs/reference/domain-observability.md
```

It should document:

- ownership boundaries;
- contracts;
- metric catalog;
- observed versus unavailable semantics;
- health semantics;
- privacy;
- exact non-goals;
- acceptance evidence.

Implementation should also update:

```text
docs/roadmap/phase-10-domain-intelligence.md
docs/reference/domain-intelligence-requirements-matrix.md
ROADMAP.md
```

only according to the established implementation-pending-audit status
convention.

Before independent audit, documentation may state only:

```text
Phase 10.37 implementation complete — independent audit pending
DP-037 = IMPLEMENTED_PENDING_AUDIT
AT-DP-037 = PASS
```

It MUST NOT claim:

```text
independently audited
closed
final PASS
BLOCKERS=0
MAJORS=0
MINORS=0
```

until the independent audit actually establishes those facts.

---

## 34. Audit bundle boundary

The implementation to be audited must be fully committed.

The worktree must be clean.

The audit bundle MUST be generated from exact committed HEAD, preferably with
`git archive`.

The implementation workflow must record:

```text
AUDITED_HEAD=<exact commit>
AUDIT_BUNDLE=<tar.gz>
AUDIT_BUNDLE_SHA256=<sha256>
WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED
```

No uncommitted worktree state may be included in the audit candidate.

If remediation is required:

1. fix only the findings;
2. rerun all relevant gates;
3. commit remediation;
4. generate a new exact-HEAD bundle;
5. calculate a new SHA-256;
6. re-audit the new bundle.

The previous bundle must not be silently replaced.

---

## 35. Closure criteria

Phase 10.37 may be closed only after independent audit reports at minimum:

```text
BLOCKERS=0
MAJORS=0
DP-037=VERIFIED_EXISTING
AT-DP-037=PASS
CLOSURE_ELIGIBLE=YES
```

Any minors must also be handled according to the project's current closure
policy.

The final closure commit must be documentation-only.

It must not contain new production code.

The next phase must not begin until:

- closure documentation is committed;
- the worktree is clean;
- the quarantine stash remains preserved;
- repository state identifies Phase 10.38 as next.

---

## 36. Non-goals

Phase 10.37 does not implement:

- a new event bus;
- a new event repository;
- a new Domain Trace;
- a trace repository;
- a Domain observability store;
- a metrics store;
- a metrics registry;
- a telemetry backend;
- a logging backend;
- a session repository;
- a Domain runtime;
- a Domain resolver;
- a Domain composer;
- a conflict resolver;
- a Domain loader;
- a Domain registry;
- a permission system;
- an approval system;
- an operation executor;
- a workflow engine;
- an Agent Runtime;
- a Validation system;
- OpenTelemetry;
- Prometheus;
- Grafana;
- dashboards;
- alerts;
- distributed tracing;
- provider/model metrics;
- token/cost metrics for Model Gateway;
- platform-wide health;
- API authentication;
- HTTP/REST endpoints;
- GraphQL;
- MCP;
- CLI observability commands;
- UI;
- durable observability persistence;
- external monitoring integrations;
- Phase 10.38 security architecture;
- Phase 11.23 platform observability;
- Phase 10.52/10.53 domain quality benchmarks.

---

## 37. Explicitly prohibited implementation shortcuts

The implementation agent MUST NOT:

1. count `domain:general` as fallback without explicit fallback evidence;
2. count supporting domains as transfers without explicit transfer evidence;
3. fabricate reuse/duplicate/question-avoidance metrics;
4. use `0` for missing evidence;
5. copy raw `DomainEvent.payload` wholesale into observability output;
6. copy `DomainTrace` upstream payloads;
7. create a persistence layer for convenience;
8. add an in-memory DomainObservabilityStore "just for tests";
9. modify Domain Resolver behavior to expose easier metrics;
10. modify conflict-resolution semantics to expose easier metrics;
11. add event publication side effects to pure Phase 10.31/10.32 components;
12. use AgentObservabilityStore as Domain truth;
13. use ValidationObservability repository as Domain truth;
14. extend DomainAPI solely to expose 10.37;
15. create a global singleton metrics object;
16. add background threads/tasks;
17. add network calls;
18. add model calls;
19. log secrets or raw sensitive data;
20. weaken Phase 10.33 secret-key validation;
21. alter the quarantine stash;
22. use `git stash`, `git reset`, `git clean` or `git worktree`;
23. push or merge unless explicitly authorized.

---

## 38. Implementation-plan constraints

The implementation plan generated after this spec is committed must:

- begin from the exact post-spec commit HEAD;
- identify every expected production/test/documentation file;
- separate RED/GREEN blocks;
- specify which canonical owners each block reuses;
- include the exact anti-duplication checks;
- include `AT-DP-037` as a first-class task;
- include privacy/adversarial testing;
- include the full regression/gate sequence;
- include documentation and implementation commit boundaries;
- include exact-HEAD audit bundle creation;
- preserve the quarantine stash;
- prohibit push/merge.

No implementation starts before that plan is committed.

---

## 39. Design summary

Phase 10.37 does not add "observability infrastructure" in the broad platform
sense.

It adds one Domain Intelligence-specific read-only projection over evidence
that already exists.

The key architecture is:

```text
Existing canonical Domain evidence
              ↓
privacy-minimized normalization
              ↓
exact metrics OR explicit unavailable
              ↓
read-only per-domain health
              ↓
ephemeral deterministic report
```

The most important semantic rule is:

```text
no evidence
!=
zero
!=
guess
```

The most important architectural rule is:

```text
observe canonical truth
do not create another truth
```

The most important closure rule is:

```text
implementation
→ exact tests/gates
→ committed clean HEAD
→ exact-HEAD TAR.GZ
→ independent ChatGPT audit
→ remediation if needed
→ PASS
→ docs-only closure commit
```
