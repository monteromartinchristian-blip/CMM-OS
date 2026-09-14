# Phase 10.34 — Domain Sessions — Independent Audit V3

## Independent Audit V3

**Date:** 2026-08-30
**Auditor:** ChatGPT (independent project auditor)
**Audited phase:** Phase 10.34 — Domain Sessions
**Audited bundle:** `phase-10.34-audit-v3.tar.gz`
**Bundle SHA256:** `4d47b45eea25b93404db24033ee97311c49f2aa0e1d5d6eb0dc3898f7e3e1c1d`
**Audited Git HEAD:** `4927f42b5c11fb0d20846e2c9a087017b2b9a814`

```text
FINAL_INDEPENDENT_AUDIT_V3=FAIL
BLOCKERS=2
MAJORS=4
MINORS=2

DP_034=NOT_VERIFIED
AT_DP_034=FAIL
CLOSURE_ALLOWED=NO

NEXT=PHASE10_34_REMEDIATION_V4
PUSH=NO
MERGE=NO
```

---

## 1. Artifact identity and packaging verification

Independent checks against the uploaded artifact produced:

```text
SHA256=4d47b45eea25b93404db24033ee97311c49f2aa0e1d5d6eb0dc3898f7e3e1c1d
ARCHIVE_HEAD=4927f42b5c11fb0d20846e2c9a087017b2b9a814
MEMBERS=1871
FORBIDDEN_GIT_VENV_PYC=0
```

The embedded `git archive` commit therefore matches the remediation HEAD reported for V3.

Positive packaging properties:

- archive is a real `git archive`;
- exact commit identity is recoverable from PAX metadata;
- no `.git/`;
- no `.venv/`;
- no `__pycache__/`;
- no `.pyc`.

One packaging defect remains: the archive was generated **without** the required
`CMM-OS-phase-10.34/` prefix. Its first member is `.claude/`.

---

## 2. Independent execution evidence

The auditor environment does not contain the repository's `libcst` dependency,
so the complete repository suite cannot be independently replayed here without
altering the audit environment. This is **not** counted as a project finding.

Using a package-bypass harness that avoids eager package initializers, the
auditor independently executed the relevant Phase 10.34 code and tests.

### Acceptance gate

```text
tests/domains/test_domain_session_acceptance.py
57 passed
```

Critically, these 57 tests pass even though:

```text
phase-10.34-audit-v3.tar.gz is not present inside the extracted repository
docs/audits/phase-10.34-independent-audit-v3.md does not exist
```

That fact is relevant to MAJOR-04 below.

### Focused tests reproducible in the auditor environment

After excluding only tests whose imports require unavailable external
environment dependencies / the fake-parent-package public API surface:

```text
331 passed
1 deselected
```

### Compilation

```text
COMPILEALL=PASS
```

for the Phase 10.34 production modules and focused test files.

### Domain Events regression

Independent import of the event catalog:

```text
GENERAL_EVENT_COUNT=23
GENERAL_EVENT_UNIQUE_COUNT=23
DOMAIN_SESSION_RESUMED_PRESENT=NO
```

The exact Phase 10.33 general event count is preserved.

---

# 3. Positive V3 remediation confirmed

The following V2 problems were materially improved and should be preserved.

## 3.1 Canonical resolver is now invoked for an invalid primary domain

An independently injected resolver was called exactly once during genuine
re-resolution.

Observed result:

```text
status=RE_RESOLVED
resolver_calls=1
last_resolution_id=real-res
transition.resolution_id=real-res
transition.composition_id=<real composed id>
```

The old free-form `fallback_resolver` no longer performs production
re-resolution.

## 3.2 Missing current authorities now fail closed

Independent probes confirmed:

```text
active workflow refs + no workflow evaluator -> BLOCKED
conflict refs + no conflict evaluator -> BLOCKED
pending question refs + no question evaluator -> BLOCKED
approval refs + no approval evaluator -> BLOCKED
```

## 3.3 Compatible version drift is committed

For persisted `domain:health=1.0.0` and current registry `1.1.0`:

```text
first resumed domain_versions={'domain:health': '1.1.0'}
second resume domain_version check=PASS
```

The repeated artificial version drift reported by V2 is fixed.

## 3.4 Explicit resource-version drift now causes replan

For a resource version marked changed:

```text
status=REPLAN_REQUIRED
partial_result_refs=()
trace_refs=()
next_recommended_step=replan_execution
```

This is an improvement, although MAJOR-02 below shows the implementation is
still incomplete.

## 3.5 NaN / Infinity and revision-type validation improved

Direct-construction probes reject:

```text
actor=NaN
actor=+Infinity
actor=-Infinity
previous_revision="1"
resumed_revision=True
```

## 3.6 Callback-only persistence no longer claims durability

A `persistence_updater=lambda ...` without shared persistence now returns:

```text
status=FAILED
recorded_resumption=False
```

## 3.7 Phase 10.35 naming is corrected

Both canonical roadmaps now identify:

```text
Phase 10.35 — Domain SDK
```

The original V2 MINOR-01 is fixed.

---

# 4. BLOCKER-01 — A stale explicit DomainSessionContext can overwrite newer authoritative shared state

## Requirement

The shared session store must be the authoritative persistence boundary.

The resume path must:

1. load the current shared session by ID;
2. read the persisted Domain Session extension;
3. verify identity **and revision/currentness**;
4. build from current authoritative state;
5. atomically persist the next revision.

A stale caller-supplied snapshot must never roll durable state backwards.

## Production cause

`DomainSessionResumer.resume()` gives precedence to a caller-supplied
`DomainSessionContext`.

Only when no explicit context is supplied does it load through
`shared_session_adapter`.

At commit time `SharedSessionDomainAdapter.save_domain_session()` loads the
latest shared envelope but does **not** compare the existing persisted domain
extension revision against the candidate's `previous_revision`.

The shared store's optimistic revision protection therefore protects the
**shared envelope revision**, but not the Domain Session extension from a stale
caller snapshot.

## Independent reproduction

The auditor first persisted:

```text
DomainSession revision=5
next_recommended_step=step:new
shared envelope revision=1
```

It then called `resume()` with an old explicit snapshot:

```text
DomainSession revision=2
next_recommended_step=step:old
```

Observed:

```text
BEFORE:
domain_revision=5
next_step=step:new
shared_revision=1

RESULT:
status=RESUMED
previous_revision=2
resumed_revision=3
recorded_resumption=True

AFTER:
domain_revision=3
next_step=step:old
shared_revision=2
```

The authoritative durable domain revision moved **backward from 5 to 3** and
the newer durable next step was overwritten.

## Impact

This breaks the central invariant that shared persistence is authoritative.

It permits:

- stale writer rollback;
- loss of newer Domain Session state;
- lost questions/approvals/workflow state;
- stale authorization/composition snapshots replacing newer snapshots;
- incorrect revision lineage despite `recorded_resumption=True`.

This is a closure blocker.

## Required remediation

1. When a shared adapter is configured, always consult the authoritative shared
   session before continuing.
2. Explicit `session_context` may seed a session only when no durable extension
   exists, or must exactly match the current durable revision/identity.
3. Reject stale/future/mismatched explicit revisions fail-closed.
4. Add optimistic concurrency at the Domain Session extension level.
5. Add regressions:
   - stale explicit revision cannot overwrite newer persisted extension;
   - same-revision authoritative update succeeds;
   - concurrent shared update is rejected;
   - durable state is unchanged after stale-write rejection.
6. `recorded_resumption=True` only after the authoritative revision check and
   atomic commit both succeed.

---

# 5. BLOCKER-02 — Conflict/workflow authoritative statuses can be discarded and committed as safe

## Requirement

Current workflow/conflict authority must be authoritative.

If current evaluation reports:

```text
INCOMPATIBLE
BLOCKED
REPLAN_REQUIRED
WAITING_FOR_USER
...
```

the resumer must conservatively merge that status. It cannot silently downgrade
it to `RESUMED` or a weaker state.

## Conflict production cause

Conflict handling currently blocks only when:

- a returned check has `blocking=True`; or
- `conf_status is BLOCKED`.

Other authoritative statuses are ignored.

## Independent conflict reproduction

With a real `domain_conflict_refs` entry and an evaluator returning no checks:

```text
conf_status=REPLAN_REQUIRED -> final RESUMED, recorded=True
conf_status=INCOMPATIBLE    -> final RESUMED, recorded=True
conf_status=WAITING_FOR_USER -> final RESUMED, recorded=True
```

In particular, **INCOMPATIBLE becomes RESUMED and is durably committed**.

## Workflow precedence defect

Workflow handling applies a non-blocking workflow status only when the current
session status is exactly `RESUMED`.

During a material recomposition:

```text
current status=RECOMPOSED
workflow authority=REPLAN_REQUIRED
```

observed final result:

```text
RECOMPOSED
```

Likewise a workflow `WAITING_FOR_USER` result is lost behind `RECOMPOSED`.

## Impact

A current authoritative conflict/workflow decision can be weakened by status
ordering rather than merged by safety severity.

That contradicts fail-closed resumption semantics and can mark an unsafe
session safe to continue.

This is a closure blocker.

## Required remediation

1. Define one explicit status merge/precedence function for resumption.
2. The strongest safety state must win, independently of evaluation order.
3. At minimum:
   - `FAILED/BLOCKED/INCOMPATIBLE` must never be downgraded;
   - `REPLAN_REQUIRED` must survive recomposition/re-resolution;
   - waiting states must survive unless a stronger blocking state exists.
4. Apply the same merge semantics to workflow and conflict evaluators.
5. Add regressions for every returned status, including combinations with:
   - `RECOMPOSED`;
   - `RE_RESOLVED`;
   - resource drift;
   - pending questions/approvals.

---

# 6. MAJOR-01 — Synthetic authoritative DomainResolutionResult with fabricated confidence=1.0 remains

## V2 remediation requirement

Audit V2 explicitly required:

```text
Do not fabricate confidence=1.0.
Use actual resolver status/evidence/confidence when an authoritative
DomainResolutionResult is represented.
```

## Production evidence

When no new re-resolution occurred, `session_resumer.py` still constructs:

```python
DomainResolutionResult(
    id=last_resolution_id or f"domain-resolution-resume-{session_id}",
    status=DomainResolutionStatus.RESOLVED,
    primary_domain=...,
    supporting_domains=...,
    confidence=1.0,
)
```

This synthetic result is passed into the composer on ordinary resumes and
recompositions.

## Independent reproduction

A spy composer on a nominal unchanged resume received:

```text
id=domain-resolution-resume-s
status=RESOLVED
primary_domain=domain:health
confidence=1.0
reasons=()
candidate_scores=()
```

No resolver produced that confidence/evidence.

## Assessment

The core V2 policy-bypass blocker is fixed for actual primary re-resolution,
so this residual issue is classified **MAJOR rather than BLOCKER**.

However, an authoritative resolver contract is still being fabricated to bridge
the composer API, and the explicit V2 remediation requirement remains unmet.

## Required remediation

Do not manufacture an authoritative `DomainResolutionResult`.

Use one of:

- the actual current authoritative resolution result;
- a repository-native composition input that does not pretend to be a
  resolution;
- an explicitly non-authoritative typed reconstruction contract if the
  composer architecture genuinely requires one.

No synthetic `confidence=1.0`.

---

# 7. MAJOR-02 — Resource/temporal/provenance revalidation remains incomplete and stale dependent state survives non-resource material changes

This finding has two related parts.

## A. Existing native temporal/resource contracts are not used

The canonical design requires existing resource/knowledge metadata and
temporal/provenance services.

The repository already has native resource temporal semantics:

```text
DomainResourceContext.temporal_scope:
- valid_from
- valid_until
- observed_at
- last_verified_at

DomainResourceTemporalPolicy:
- expiration_required
- validity_window_seconds
- historical_allowed
```

`resource_resolver._evaluate_temporal_policy()` applies these semantics.

Phase 10.34 instead classifies resource/knowledge state through arbitrary
version strings such as:

```text
MISSING
INVALIDATED
changed...
drift...
stale...
```

and a session-level optional:

```text
request.metadata["max_session_age_seconds"]
```

It never consumes the native resource temporal scope/policy.

### Independent reproduction

A native resource context was constructed with:

```text
valid_until = one hour before current time
expiration_required=True
historical_allowed=False
```

The existing resource temporal evaluator returned:

```text
False, "historical use of an expired resource is not allowed"
```

The same referenced resource resumed through Phase 10.34 with a version string
`"v1"` produced:

```text
SESSION_STATUS=RESUMED
resource check=PASS
temporal check=PASS
```

Thus a resource that the repository's native temporal policy says is expired can
still be treated as current by Domain Sessions.

## B. Partial results/traces are invalidated only for DRIFT checks

The design states that partial results/traces must not be treated as fresh when
their supporting:

- resources;
- knowledge;
- temporal scope;
- domain version;
- permissions;
- composition

changed.

V3 invalidates them only when a check has status `DRIFT`.

### Independent recomposition reproduction

Persisted state:

```text
supporting domain=domain:fitness
partial=result:fitness-derived
trace=trace:fitness-derived
next=step:fitness-plan
```

Current registry disables `fitness`.

Observed:

```text
status=RECOMPOSED
supporting_domains=()
partial_result_refs=('result:fitness-derived',)
trace_refs=('trace:fitness-derived',)
next_recommended_step=step:fitness-plan
```

### Independent version-change reproduction

Persisted:

```text
domain:health=1.0.0
partial=result:v1
trace=trace:v1
next=step:v1
```

Current version:

```text
domain:health=1.1.0
```

Observed:

```text
domain version check=CHANGED
final status=RESUMED
stored version updated to 1.1.0
partial=result:v1
trace=trace:v1
next=step:v1
```

## Impact

The system can retain and present stale derived continuity state after the
inputs that justified it have changed.

## Required remediation

1. Integrate repository-native temporal/provenance/resource semantics rather
   than string parsing as the authority.
2. Classify native current/stale/missing/expired/invalidated/unknown states.
3. Define dependency freshness for partial results, traces and next step.
4. Revalidate/invalidate dependent state on:
   - resource/knowledge drift;
   - compatible domain version changes;
   - recomposition;
   - re-resolution;
   - permission changes where relevant.
5. Preserve stale refs only as explicitly historical/audit refs, never as
   current continuation state.
6. Add E2E tests with a real expired resource temporal scope.

---

# 8. MAJOR-03 — Public session contracts still accept arbitrary non-JSON metadata/details

## Requirement

Every publicly constructible Phase 10.34 contract must be JSON-safe at
construction time and serializable with:

```python
json.dumps(obj.to_dict(), allow_nan=False)
```

V3 fixed NaN/Infinity and revision types, but arbitrary Python objects remain
accepted in several metadata surfaces.

## Production cause

For `metadata` / `details`, constructors run:

```text
credential validation
NaN/Infinity validation
_deep_freeze(...)
```

They do not perform a strict JSON-serializability validation.

`_deep_freeze()` leaves an unknown arbitrary Python object unchanged.

## Independent reproduction

With:

```python
class Opaque:
    pass
```

the following all construct successfully:

```text
DomainSessionContext(metadata={"x": Opaque()})
DomainSessionCheck(details={"x": Opaque()})
DomainSessionTransition(metadata={"x": Opaque()})
DomainSessionResumeRequest(metadata={"x": Opaque()})
```

But each later fails:

```text
json.dumps(obj.to_dict(), allow_nan=False)
-> TypeError: Object of type Opaque is not JSON serializable
```

The public constructor can therefore still create an invalid contract.

## Required remediation

Create one canonical recursive strict JSON validator and apply it consistently
to all public `metadata`, `details`, actor and nested extension surfaces.

Reject arbitrary objects, sets/frozensets if they are not deliberately
normalized, NaN and infinities **before** object construction completes.

Add one parameterized gate proving every public Phase 10.34 contract can always
round-trip through strict JSON.

---

# 9. MAJOR-04 — AT-DP-034 remains a false-positive acceptance gate

## Positive V3 change

There are no longer literal `assert True` placeholders.

The acceptance module still has exactly:

```text
56 checkpoint functions
+ 1 meta test
= 57 passing pytest cases
```

## Required V2 remediation that is still absent

Audit V2 required a machine-verifiable acceptance manifest containing
equivalents of:

```text
checkpoint_id
description
evidence_type
evidence_reference
required
```

and a meta-gate that fails when external evidence is absent or stale relative
to the exact HEAD.

No such manifest exists.

Search finds no Phase 10.34 acceptance representation of:

```text
evidence_type
evidence_reference
gate_result
HEAD-bound evidence
```

## Concrete false-positive checkpoints

### Checkpoint 30

Claims:

```text
profile/rule/question/operation reevaluation
```

but still only proves removal of one old rule.

### Checkpoint 38

Claims shared session revision/history evidence but only asserts:

```text
event catalog length == 23
domain.session.resumed absent
```

It never inspects shared revision/history.

### Checkpoint 48

"Focused tests pass" merely checks that test files exist and are non-empty.

### Checkpoint 49

"Phase 10 domain tests pass" merely checks classes are importable/callable.

### Checkpoint 50

"Global tests pass" only checks that `cmm/runtime/sessions.py` does not import
`cmm.domains`.

### Checkpoint 51

"Quality gates" only calls Python `compile()` on six files; it does not verify
Ruff or the declared quality gates.

### Checkpoint 54

"git archive TAR.GZ generation" only checks a hard-coded string:

```text
phase-10.34-audit-v3.tar.gz
```

ends with `.tar.gz`.

### Checkpoint 55

"Independent audit criteria" creates a local dictionary containing three
zeroes and asserts those zeroes.

### Checkpoint 56

"Closure only after clean audit" creates:

```python
"independent_audit_passed": True
```

inside the test itself.

## Independent false-positive reproduction

Inside the extracted committed repository:

```text
phase-10.34-audit-v3.tar.gz does not exist
docs/audits/phase-10.34-independent-audit-v3.md does not exist
```

Nevertheless:

```text
57 passed
```

including checkpoints 54–56.

Therefore `AT-DP-034=PASS` remains possible without the evidence it claims to
verify.

## Required remediation

Implement the V2-required evidence manifest.

For each of all 56 logical checkpoints, bind it to real evidence:

- live pytest node IDs;
- verified gate artifact;
- exact committed HEAD;
- command/result/count where external;
- explicit state.

The meta-gate must reject:

- missing evidence;
- stale evidence;
- wrong HEAD;
- missing pytest node;
- failed external gate;
- placeholder/self-asserted evidence.

Specifically, checkpoints 30 and 38 must be bound to real tests covering their
full declared requirements.

---

# 10. MINOR-01 — Audit bundle prefix regressed

The required archive prefix was:

```text
CMM-OS-phase-10.34/
```

The V3 archive starts at repository root:

```text
.claude/
.cmm/
.github/
...
```

The exact commit is still verifiable, so this is not a blocker.

Regenerate V4 using:

```bash
git archive \
  --format=tar.gz \
  --prefix="CMM-OS-phase-10.34/" \
  ...
```

and verify the first member before delivery.

---

# 11. MINOR-02 — Phase 10.34 documentation is stale after V3

The canonical milestone name is fixed, but Phase 10.34 progress evidence was
not updated for V3.

Examples in the audited HEAD still state:

```text
304 focused domain session tests
independent re-audit V2 pending
```

in `ROADMAP.md`, the requirements matrix and detailed roadmap/reference
material.

The V3 agent itself reports a different focused count and V3 re-audit state.

Before V4 audit, documentation should conservatively state the actual current
pre-audit status and evidence, for example:

```text
Phase 10.34 implemented; independent re-audit V4 pending
```

with current verified counts only.

---

# 12. V2 finding disposition

```text
V2 BLOCKER-01 canonical resolver bypass
CORE_FIXED
RESIDUAL_SYNTHETIC_RESOLUTION=MAJOR

V2 BLOCKER-02 callback-only persistence
PARTIALLY_FIXED
AUTHORITATIVE_STALE_OVERWRITE=BLOCKER

V2 BLOCKER-03 workflow/conflict fail-open
PARTIALLY_FIXED
MISSING_AUTHORITY_FIXED
STATUS_MERGE_FAIL_OPEN=BLOCKER

V2 MAJOR-01 compatible version drift not committed
FIXED

V2 MAJOR-02 resource/knowledge/temporal drift observational
PARTIALLY_FIXED
NATIVE_TEMPORAL_PROVENANCE_GAP=MAJOR
DEPENDENT_STATE_INVALIDATION_GAP=MAJOR_SAME_FINDING

V2 MAJOR-03 questions/approvals trusted without authority
CORE_FIXED

V2 MAJOR-04 strict JSON contracts
PARTIALLY_FIXED
OPAQUE_METADATA_JSON_GAP=MAJOR

V2 MAJOR-05 AT-DP-034 false positive
NOT_FIXED=MAJOR

V2 MINOR-01 Phase 10.35 naming
FIXED
```

---

# 13. Final verdict

Phase 10.34 V3 is materially stronger than V2:

- canonical resolver is genuinely called during primary replacement;
- missing authorities fail closed;
- real shared persistence infrastructure exists;
- callback-only durability is rejected;
- compatible domain version drift becomes idempotent;
- explicit resource-version drift produces a safe replan;
- NaN/Infinity/revision validation improved;
- 23-event boundary is preserved.

However, closure is not allowed because authoritative state can still be rolled
back and authoritative workflow/conflict statuses can still be downgraded.

The acceptance gate also remains unable to prove its own external evidence.

```text
FINAL_INDEPENDENT_AUDIT_V3=FAIL

BLOCKERS=2
MAJORS=4
MINORS=2

DP_034=NOT_VERIFIED
AT_DP_034=FAIL

GENERAL_EVENT_COUNT=23
DOMAIN_SESSION_RESUMED_EVENT=ABSENT

AUDITED_HEAD=4927f42b5c11fb0d20846e2c9a087017b2b9a814
AUDIT_BUNDLE_SHA256=4d47b45eea25b93404db24033ee97311c49f2aa0e1d5d6eb0dc3898f7e3e1c1d

CLOSURE_ALLOWED=NO
NEXT=PHASE10_34_REMEDIATION_V4
PUSH=NO
MERGE=NO
```
