# Phase 10.34 — Domain Sessions Design

**Date:** 2026-08-30
**Status:** Design approved for implementation planning
**Branch:** `feature/phase-10-domain-intelligence`
**Baseline:** `2ce12df24c5eb5093ce0349a95300eac6619680c`
**Previous boundary:** Phase 10.33 — Domain Events, complete and independently audited
**Next boundary:** Phase 10.35 — Domain SDK

## 1. Objective

Phase 10.34 extends the existing Phase 8 `SessionContext` so a paused or resumed
session can preserve and safely reconstruct Domain Intelligence state.

Phase 10.34 must not introduce a second session engine, second memory store,
second workflow engine, second approval store, second permission engine, or
parallel persistence authority.

The architectural ownership remains:

```text
Phase 8 SessionContext / shared session lifecycle
        ↓
DomainSessionContext
        ↓
shared session persistence boundary
        ↓
DomainSessionResumer
        ↓
current Domain Registry / Resolver / Composition / Permissions / temporal state
        ↓
validated resumed DomainSessionContext
```

The stored domain state is a resumable specialization snapshot, not an
authoritative replacement for current registries, policies, workflows,
knowledge, memory, approvals, or resources.

## 2. Canonical sources

The implementation is constrained by:

- `ROADMAP.md`;
- `docs/roadmap/phase-10-domain-intelligence.md`, Section 10.34 — Domain Sessions;
- `docs/reference/domain-intelligence-requirements-matrix.md`;
- Phase 8 Session Context and its persistence/resumption semantics;
- Phase 10.18 Domain Memory Integration reference-only / no-parallel-store boundary;
- Phase 10.31 Domain Selection Policies, especially session continuity,
  reevaluation, and main-domain changes;
- Phase 10.32 Domain Conflict Resolution;
- Phase 10.33 Domain Events and its exact 23-event general catalog.

At the Phase 10.33 closure baseline, the requirements matrix does not yet define
`DP-034`. Phase 10.34 therefore introduces `DP-034` / `AT-DP-034` using the
established Phase 10 acceptance naming convention unless repository inspection
reveals an already committed canonical alternative.

## 3. Canonical roadmap requirements

The Domain Session must preserve at least:

- primary domain;
- supporting domains;
- composition;
- effective profile;
- effective rules;
- effective permissions;
- resources by domain;
- knowledge by domain;
- workflows;
- operations;
- pending questions;
- conflicts;
- approvals;
- partial results;
- domain changes;
- traces;
- next recommended step.

On resumption the system must:

- check active domains;
- check domain versions;
- check compatibility;
- detect modified resources;
- re-evaluate permissions;
- re-evaluate temporal validity;
- reconstruct composition;
- detect migrated/incompatible workflows;
- recover pending questions;
- recover approvals;
- record the resumption.

## 4. Architectural decision

Phase 10.34 adds a typed, immutable, reference-first domain-session extension
over the existing shared session lifecycle.

Selected design:

1. `DomainSessionContext` stores canonical references and resumable domain
   specialization state.
2. Phase 8 remains authoritative for session identity, lifecycle, persistence,
   pause/resume/cancel/complete semantics, and session timestamps.
3. Phase 10.34 persists its serialized state only through the existing shared
   Session Context persistence boundary or a narrow adapter to that boundary.
4. `DomainSessionResumer` treats the persisted domain snapshot as untrusted,
   potentially stale input and rebuilds current effective domain state before
   continuation.
5. Resumption is fail-closed: continuation is allowed only after mandatory
   revalidation succeeds.
6. Resumption never executes an operation merely because an old session said it
   was available.
7. Main-domain changes reuse Phase 10.31 semantics and must preserve a structured
   transition record.

Rejected alternatives:

- storing all Phase 10 state inside an untyped `SessionContext.metadata` blob;
- creating a `DomainSessionRepository` as an independent source of truth;
- duplicating workflow, approval, permission, memory, or knowledge objects inside
  the domain session;
- trusting a persisted effective permission set or operation list without
  re-evaluation;
- adding a new general `domain.session.resumed` event to the Phase 10.33 catalog.

## 5. Non-goals

Phase 10.34 does not own:

- a new session database;
- Phase 11 application persistence;
- workflow-engine persistence redesign;
- approval execution;
- permission decision execution;
- operation execution;
- knowledge mutation;
- memory mutation;
- resource fetching;
- a new temporal engine;
- a new domain resolver;
- a new composition engine;
- a new event bus;
- event persistence/replay/DLQ;
- provider/model session state;
- conversational rendering;
- Phase 11 multidevice synchronization.

## 6. DomainSessionContext contract

The implementation should provide an immutable, slotted, strictly validated,
JSON-safe contract equivalent in responsibility to:

```python
DomainSessionContext(
    session_id="session-123",
    primary_domain="domain:health",
    supporting_domains=(),
    domain_versions={},
    composition_id="domain-composition-123",
    effective_profile=None,
    effective_rule_ids=(),
    effective_permission_refs=(),
    active_workflow_refs=(),
    available_operation_ids=(),
    domain_resource_refs={},
    domain_knowledge_refs={},
    pending_domain_question_refs=(),
    domain_conflict_refs=(),
    approval_refs=(),
    partial_result_refs=(),
    trace_refs=(),
    domain_transitions=(),
    last_resolution_id="domain-resolution-123",
    next_recommended_step=None,
    revision=1,
    updated_at="...",
    metadata={},
)
```

Exact field names may follow existing repository conventions discovered during
implementation planning, but the canonical semantics above may not be dropped.

### 6.1 Reference-first invariant

The context must store identifiers or compact declarative snapshots where
required for safe reconstruction.

It must not copy authoritative:

- Knowledge Items;
- Resource bodies;
- Memory records;
- Approval payloads;
- Permission objects;
- Workflow runtime internals;
- operation implementation objects;
- Domain Definitions;
- Domain Traces containing unnecessary sensitive content.

Reference inventories must be deterministic and deduplicated.

### 6.2 Domain versions

The session must preserve the versions needed to detect drift between the
persisted specialization and currently registered Domain Definitions.

The stored version is evidence of the prior state, not authority over the
current registry.

### 6.3 Effective profile, rules, and permissions

The session may retain the previous effective profile/rule/permission
references for continuity and auditability.

They must be re-evaluated before continuation when current policy could differ.

### 6.4 Operations

`available_operation_ids` is a historical/resumable snapshot.

Availability must be recalculated from current domain composition, permissions,
operation registry state, actor/session policy, approvals, conflicts, and any
other existing gate before execution.

## 7. Domain transition contract

A main-domain or supporting-domain change must be explicit and auditable.

A transition record should capture, by reference:

```python
DomainSessionTransition(
    previous_primary_domain=...,
    new_primary_domain=...,
    previous_supporting_domains=...,
    new_supporting_domains=...,
    reason_code=...,
    resolution_id=...,
    composition_id=...,
    occurred_at=...,
)
```

A transition must not silently discard prior context.

For a material domain change Phase 10.31 still requires:

- a grounded reason;
- context preservation;
- permission reevaluation;
- profile reevaluation;
- rule reevaluation;
- question reevaluation;
- operation deduplication;
- session update.

## 8. Serialization and integrity

The public contract must be:

- immutable;
- JSON-safe;
- strictly serializable;
- strictly deserializable;
- deterministic;
- round-trippable;
- duplicate-resistant;
- schema/version aware;
- timezone-safe;
- fail-closed on malformed identifiers, mappings, timestamps, and unknown
  structural fields according to repository convention.

Serialized state must not contain credentials.

Phase 10.34 should reuse the existing canonical credential policy introduced by
Phase 10.33 rather than create a second detector.

Unknown or unsupported serialized versions must not be silently accepted.

## 9. Shared persistence boundary

Phase 8 remains owner of persistent Session Context.

Phase 10.34 may provide a codec/adapter that attaches the serialized
`DomainSessionContext` to the existing session persistence model, but:

- no independent durable repository is created;
- no second session lifecycle is created;
- domain-session writes follow existing Session Context update semantics;
- persistence failures do not partially advance the in-memory authoritative
  session state;
- rollback/atomicity follow existing shared session mechanisms where available.

If the existing Session Context persistence surface cannot carry a typed
extension safely, the smallest compatible extension to that shared surface is
allowed. It must remain generic enough that Phase 8 still owns persistence.

## 10. Resumption input and output

Resumption should be explicit, side-effect bounded, and structured.

Conceptually:

```python
DomainSessionResumeRequest(
    session_id=...,
    actor=...,
    temporal_reference=...,
    current_resource_versions=...,
    metadata={},
)
```

and:

```python
DomainSessionResumeResult(
    status=...,
    session_id=...,
    previous_revision=...,
    resumed_revision=...,
    context=...,
    checks=...,
    warnings=...,
    blocking_findings=...,
    recovered_question_refs=...,
    recovered_approval_refs=...,
    next_recommended_step=...,
    recorded_resumption=...,
)
```

Exact repository-native types should be reused where they already exist.

## 11. Resumption algorithm

Canonical order:

```text
Load shared SessionContext
↓
Load/deserialize DomainSessionContext extension
↓
Validate structural integrity
↓
Resolve current Domain Definitions
↓
Check active/enabled domain status
↓
Compare stored/current domain versions
↓
Check compatibility
↓
Detect relevant resource drift
↓
Re-evaluate temporal validity
↓
Re-evaluate permissions
↓
Re-resolve/reconstruct domain composition
↓
Re-evaluate profile and rules
↓
Recalculate available operations
↓
Validate/migrate workflow references
↓
Re-evaluate conflicts
↓
Recover still-valid pending questions
↓
Recover still-valid approvals
↓
Reconstruct next step
↓
Record resumption revision/history
↓
Persist through shared session boundary
↓
Return structured result
```

The implementation may internally group pure checks where existing services
already combine them, but it must preserve these semantic gates.

## 12. Resumption statuses

Use repository-native status contracts where available. Otherwise define a
small closed set with semantics equivalent to:

```text
RESUMED
RE_RESOLVED
RECOMPOSED
REPLAN_REQUIRED
WAITING_FOR_USER
WAITING_FOR_APPROVAL
BLOCKED
INCOMPATIBLE
FAILED
```

Status must not hide blocking findings.

`RESUMED` means the session is safe to continue; it does not mean any operation
has executed.

## 13. Active domains and version drift

A stored primary/supporting domain that is now disabled, missing, incompatible,
or unauthorized must not be silently treated as active.

Required behavior:

- primary domain unavailable + safe re-resolution possible -> structured
  re-resolution;
- high-risk or materially ambiguous replacement -> block/clarify according to
  existing resolver policy;
- supporting domain unavailable -> recompute composition and record the change;
- incompatible version -> migrate only through an explicit compatible path;
  otherwise fail closed.

Version changes alone do not prove incompatibility; compatibility is determined
by the existing domain compatibility contracts.

## 14. Resource and knowledge drift

The session must detect that referenced resources or knowledge changed,
disappeared, were invalidated, or became temporally stale.

Phase 10.34 does not fetch or duplicate source content itself.

It uses existing resource/knowledge metadata and temporal/provenance services to
classify the snapshot as current, changed, stale, missing, invalidated, or
unknown according to repository-native contracts.

A stale or missing high-impact dependency may block continuation.

## 15. Permission reevaluation

Persisted permissions are never authoritative.

On every resumption that may continue domain work, effective permissions are
recomputed using the existing restrictive intersection and current actor,
session, domain, operation/workflow, autonomy, approval, and sensitivity
policies.

A permission downgrade must immediately remove no-longer-authorized operations
from the resumed context.

A permission upgrade must not silently authorize an operation that separately
requires approval.

## 16. Composition reconstruction

The previous `composition_id` is continuity evidence.

The current effective composition must be reconstructed from current valid
domains and current policy.

If reconstruction produces a materially different composition:

- preserve the prior composition reference;
- create/update the current composition through existing Phase 10 composition
  services;
- record the domain transition/change;
- reevaluate profile, rules, permissions, questions, conflicts, workflows,
  operations, and next step.

## 17. Workflow migration and compatibility

Phase 10.34 stores workflow references, not a second workflow runtime.

On resume, every active workflow reference must be classified using the existing
workflow contracts as applicable:

```text
CURRENT
MIGRATED
REPLAN_REQUIRED
INCOMPATIBLE
MISSING
COMPLETED
CANCELLED
```

Migration must be explicit and traceable.

An incompatible/missing required workflow must not be silently dropped while
the session reports success.

## 18. Pending questions and approvals

Question and approval inventories must be recovered by reference.

Before recovery:

- remove entries already resolved/answered;
- preserve still-pending entries;
- detect entries invalidated by domain/composition/permission changes;
- avoid duplicate questions;
- avoid duplicate approval requests;
- never convert a historical approval into current authorization unless the
  canonical approval contract says it remains valid.

## 19. Partial results and traces

Partial result and trace references are continuity/audit inputs.

They must not be treated as fresh conclusions when their supporting resources,
knowledge, temporal scope, domain version, permissions, or composition changed.

The resumed context must preserve references needed to explain why a replan,
re-resolution, or block occurred.

## 20. Resumption recording

The roadmap requires that resumption be recorded.

Phase 10.34 will satisfy this through the shared session revision/history plus a
typed resumption/transition record inside the domain-session extension.

It must not expand the exact Phase 10.33 general event catalog beyond 23 events.

Existing Domain Events may be emitted only where an already-defined lifecycle
actually occurs during resumption, for example a real new resolution or
composition update. The mere fact of loading a session does not justify
inventing or misusing a lifecycle event.

## 21. Event integration

Phase 10.33 remains the only Domain-to-Kernel event boundary.

Phase 10.34:

- may use existing event adapters/publisher after authoritative lifecycle
  results exist;
- must not mutate resolver/composer/permission/workflow results to produce
  events;
- must not publish an event before successful shared-session persistence if that
  event would claim a committed session transition;
- must preserve the credential-safe event policy;
- must not add AgentRuntimeEventBus as a dependency.

## 22. Determinism and idempotency

Given the same persisted session snapshot, same current registries/policies,
same temporal reference, and same external version metadata, resumption must be
deterministic.

Repeated resumption without intervening changes must not:

- duplicate transitions;
- duplicate pending questions;
- duplicate approvals;
- duplicate workflow references;
- duplicate operation IDs;
- create artificial version drift;
- create an endless revision loop solely because resumption was retried after an
  uncommitted persistence failure.

## 23. Atomicity and failure behavior

The resumed domain session must not be partially committed.

If mandatory revalidation fails:

- no operation executes;
- no approval is granted;
- no memory/knowledge mutation occurs;
- the previous persisted context remains recoverable;
- the result exposes structured blocking findings;
- any in-memory candidate context is discarded or explicitly marked
  uncommitted.

If persistence of a valid resumed revision fails, the method reports failure
without claiming the revision is committed.

## 24. Security and privacy

Domain Sessions may contain highly sensitive references.

Requirements:

- least-data/reference-first state;
- no credentials;
- no secret-bearing metadata;
- no raw provider prompts;
- no private chain-of-thought;
- no copied sensitive resource bodies merely for convenience;
- no permission escalation from truthy/malformed input;
- strict authorization for cross-domain references;
- fail-closed malformed authorization state;
- no weakening of Health/Mental Health/Neurodivergence or other specialized
  privacy boundaries.

## 25. Public API boundary

Expose only stable contracts/services required by Domain Intelligence
consumers.

Private persistence internals, mutable builder state, credential helpers, and
implementation-only migration details must not leak through the public
`cmm.domains` surface unless existing project convention explicitly requires
them.

Fresh import must remain side-effect free.

## 26. TDD implementation order

First RED/GREEN cycle:

1. immutable `DomainSessionContext`;
2. strict validation;
3. deterministic serialization/round-trip;
4. reference deduplication;
5. version/timestamp integrity;
6. credential-safe metadata.

Subsequent cycles:

- shared Session Context attachment/codec;
- persistence atomicity;
- current-domain validation;
- version/compatibility drift;
- resource/knowledge drift;
- temporal reevaluation;
- permission reevaluation;
- composition reconstruction;
- profile/rule/operation recalculation;
- workflow migration/incompatibility;
- pending question recovery;
- pending approval recovery;
- domain-transition recording;
- partial result/trace continuity;
- idempotent resumption;
- persistence-failure rollback;
- event integration where an actual existing lifecycle occurs;
- public API/fresh-import boundary;
- adversarial malformed-state tests;
- cross-domain tests;
- E2E pause/persist/resume tests.

## 27. DP-034 / AT-DP-034 acceptance gate

Phase 10.34 is acceptable only if all of the following hold:

1. one canonical Domain Session extension exists;
2. it extends/reuses Phase 8 session infrastructure rather than creating a
   parallel session engine;
3. primary and supporting domains are preserved;
4. stored domain versions permit drift detection;
5. composition continuity is preserved;
6. effective profile continuity is preserved;
7. effective rule continuity is preserved;
8. effective permission continuity is preserved but never trusted as current
   authorization;
9. resource references are grouped/preserved by domain;
10. knowledge references are grouped/preserved by domain;
11. workflow references are preserved;
12. operation availability snapshots are preserved;
13. pending questions are preserved/recovered without duplication;
14. conflict references are preserved;
15. approvals are preserved/recovered without turning stale approval into
    authorization;
16. partial result references are preserved;
17. trace references are preserved;
18. domain changes are explicitly recorded;
19. next recommended step is preserved/reconstructed;
20. contract serialization is strict, deterministic, JSON-safe, round-trippable,
    and version aware;
21. session state contains no credentials and reuses the canonical credential
    policy;
22. no independent Domain Session repository/source of truth exists;
23. resumption checks active/enabled domains;
24. resumption checks stored/current domain versions;
25. resumption checks compatibility;
26. resumption detects relevant modified/missing/invalidated resources or
    knowledge;
27. resumption re-evaluates temporal validity;
28. resumption re-evaluates current permissions;
29. resumption reconstructs current composition;
30. material composition/domain changes trigger profile/rule/question/operation
    reevaluation;
31. resumption detects workflow migration/incompatibility;
32. resumption recovers still-valid questions;
33. resumption recovers still-valid approvals;
34. stale permissions never authorize an operation;
35. stale operation availability never executes an operation;
36. blocking incompatibility prevents continuation;
37. repeated unchanged resumption is idempotent with respect to inventories and
    transitions;
38. resumption is recorded through shared session revision/history without
    expanding the 23-event general catalog;
39. actual new resolution/composition lifecycle events, if emitted, use Phase
    10.33 contracts only after authoritative results exist;
40. pure Phase 10.31/10.32 components remain pure;
41. no AgentRuntimeEventBus dependency is introduced;
42. no memory or knowledge mutation occurs merely from resume;
43. no approval decision is executed merely from resume;
44. no operation executes merely from resume;
45. persistence failure cannot leave a partially committed resumed session;
46. fresh import is side-effect free;
47. malformed serialized state fails closed;
48. focused Domain Sessions tests pass;
49. Phase 10 domain tests pass;
50. global tests pass;
51. Ruff, format check, syntax compilation, and diff hygiene pass;
52. `AT-DP-034` passes;
53. documentation and requirements matrix record implementation conservatively
    before independent audit;
54. a `git archive` TAR.GZ is generated from the exact committed implementation
    HEAD before independent audit;
55. independent ChatGPT audit reaches 0 blockers, 0 majors, and 0 minors before
    closure;
56. closure documentation occurs only after that clean audit.

If repository inspection during implementation reveals an existing canonical
`DP-034` or stronger acceptance contract, repository truth wins and this design
must be amended before production code.

## 28. Documentation and audit boundary

Implementation documentation should update:

- `docs/roadmap/phase-10-domain-intelligence.md`;
- `docs/reference/domain-intelligence-requirements-matrix.md`;
- a dedicated Domain Sessions reference document if consistent with current
  Phase 10 conventions;
- `ROADMAP.md` only according to the established milestone/status convention.

Before independent audit, documentation may say only implemented/pending audit
and candidate implementation-side acceptance results.

It must not claim:

- independently audited;
- complete;
- final audit PASS;
- 0 blockers/majors/minors.

The standard CMM OS flow remains:

```text
design/spec commit
↓
implementation plan
↓
TDD implementation
↓
focused verification
↓
Phase 10 domain verification
↓
global verification
↓
quality/security gates
↓
AT-DP-034
↓
implementation commit
↓
git archive TAR.GZ from exact HEAD
↓
independent ChatGPT audit
↓
remediation / re-audit until clean
↓
audit report commit
↓
closure documentation
↓
closure commit
```

No push or merge unless explicitly requested.

The quarantine stash from Phase 10.32 must remain untouched.

## 29. Design summary

Phase 10.34 makes Domain Intelligence state safely resumable without creating a
parallel session architecture.

The persisted state is continuity evidence. Current registries, policies,
resources, temporal validity, workflows, approvals, and permissions remain
authoritative at resumption time.

The key invariant is:

```text
Persisted domain snapshot
!=
current authorization or current truth
```

A session may resume only after current Domain Intelligence state has been
revalidated and reconstructed through shared infrastructure.
