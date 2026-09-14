# Phase 10.34 — Domain Sessions
## Independent Audit V2

**Audit date:** 2026-08-30
**Auditor:** ChatGPT — independent project auditor
**Audit target:** Phase 10.34 — Domain Sessions, remediation after Audit V1
**Remediation HEAD:** `1291d4ab76bacc51a0ff814a1f129517c81f570d`
**Bundle:** `phase-10.34-audit-v2.tar.gz`
**Bundle SHA256:** `cf422a0b201688725b9a24d75ec8a1b97a4ff12a162a270469f6da52c184ddb5`
**Bundle members:** 1,865
**Archive prefix:** `CMM-OS-phase-10.34/`
**Git archive PAX commit:** `1291d4ab76bacc51a0ff814a1f129517c81f570d`
**Verdict:** **FAIL — additional remediation required**

```text
FINAL_INDEPENDENT_AUDIT_V2=FAIL

BLOCKERS=3
MAJORS=5
MINORS=1

DP_034=NOT_VERIFIED
AT_DP_034=FAIL
PHASE10_34_CLOSURE=BLOCKED
```

---

# 1. Audit basis

This audit was performed against the uploaded Git archive itself, not against the implementation agent's completion report.

Canonical sources reviewed:

- `docs/audits/phase-10.34-independent-audit-v1.md`;
- `docs/superpowers/specs/2026-08-30-domain-sessions-design.md`;
- `docs/superpowers/plans/2026-08-30-domain-sessions-implementation-plan.md`;
- `docs/reference/domain-sessions.md`;
- `docs/reference/domain-intelligence-requirements-matrix.md`;
- `docs/roadmap/phase-10-domain-intelligence.md`;
- `ROADMAP.md`;
- `cmm/domains/session_contracts.py`;
- `cmm/domains/session_codec.py`;
- `cmm/domains/session_revalidation.py`;
- `cmm/domains/session_resumer.py`;
- all Phase 10.34 focused tests and Audit V1 regression tests.

Archive verification:

```text
SHA256=cf422a0b201688725b9a24d75ec8a1b97a4ff12a162a270469f6da52c184ddb5
PAX_COMMIT=1291d4ab76bacc51a0ff814a1f129517c81f570d
PREFIX=CMM-OS-phase-10.34/
MEMBERS=1865
FORBIDDEN_ARCHIVE_PATHS=0
COMPILEALL=PASS
```

Required implementation/spec/audit files are present.

The implementation-side report states:

```text
Focused Domain Sessions: 304 passed
Domain suite: 8144 passed
Global suite: 13684 passed
Ruff/format/compileall/diff: PASS
```

Independent audit execution:

```text
AT-DP-034 acceptance file:
57 passed independently

Focused Domain Session tests under audit harness:
300 passed
1 environment-only failure caused by missing external `libcst`
public-API test file intentionally excluded from the harness because the
harness bypasses package __init__ specifically to avoid that unavailable
dependency.

The functional FAIL findings below were reproduced through independent
production-code probes and are unrelated to `libcst`.
```

---

# 2. V1 remediation status overview

```text
V1 BLOCKER-01 stale authorization fail-open:
PARTIALLY/FUNCTIONALLY FIXED for registry + permission + operation authorities.

V1 BLOCKER-02 nominal recomposition/re-resolution:
RECOMPOSITION IMPROVED.
RE-RESOLUTION NOT FIXED.

V1 BLOCKER-03 shared persistence:
NOT FIXED at the required architectural integration level.

V1 MAJOR-01 session ID transplantation:
FIXED.

V1 MAJOR-02 revalidation fail-open:
PARTIALLY FIXED.
Malformed explicit workflow states now fail closed, but missing authorities
and several resume gates still fail open.

V1 MAJOR-03 strict serialization:
PARTIALLY FIXED.

V1 MAJOR-04 AT-DP-034 accounting:
56 named checkpoints now exist, but executable evidence remains insufficient
and produces false PASS.

V1 MINOR-01 audit packaging:
FIXED.

V1 MINOR-02 documentation:
DP-034/AT-DP-034 entries added, but one roadmap milestone inconsistency remains.
```

---

# 3. Blockers

## BLOCKER-01 — Canonical Domain Resolver is still unused; re-resolution is fabricated through an arbitrary fallback callback

### Requirement

Phase 10.34 requires a resumed session with an invalid/unavailable primary domain to re-resolve through current Domain Intelligence resolution policy.

The approved design explicitly requires:

```text
Resolve current Domain Definitions
...
re-resolve when needed
...
high-risk or materially ambiguous replacement -> block/clarify according
to existing resolver policy
```

A `RE_RESOLVED` result must represent a real current resolution.

### Production evidence

`cmm/domains/session_resumer.py`:

```text
constructor:
resolver: Any | None
self._resolver = resolver
```

Static audit:

```text
self._resolver occurrences = 1
```

The only occurrence is assignment.

The production resolver is never invoked.

Instead, inactive primary-domain handling uses:

```text
fallback_resolver(previous_primary, supporting_domains) -> string
```

and later fabricates a `DomainResolutionResult` with:

```text
status=RESOLVED
confidence=1.0
```

for the fallback-selected domain.

### Independent reproduction

A resolver double whose `resolve()` method raises `RESOLVER_INVOKED` was supplied while the persisted primary domain was disabled.

Result:

```text
P1_RESOLVER_IGNORED BLOCKED False
```

The resolver was never invoked.

When a simple `fallback_resolver=lambda ...: "domain:general"` is supplied, the resumer returns:

```text
RE_RESOLVED
```

without using the canonical resolver or its ambiguity/high-risk policies.

Additional lineage probe:

```text
last_resolution_id old-res

transition:
resolution_id=None
composition_id=None
reason_code=RE_RESOLUTION
```

The resumed context still preserves the old `last_resolution_id`.

### Impact

An arbitrary fallback function can produce a `RE_RESOLVED` outcome that appears authoritative without passing through current Domain Resolver policy.

This is especially unsafe for high-risk or ambiguous domain transitions.

The audit lineage also cannot identify the actual new resolution/composition that supposedly justified the transition.

### Required remediation

1. Remove or strictly subordinate the free-form fallback callback to the canonical resolver.
2. Invoke the existing resolver contract when a new primary domain is required.
3. Use the resolver's actual resolution ID, confidence, status, evidence and ambiguity/escalation semantics.
4. Do not fabricate `confidence=1.0`.
5. Set:
   - `last_resolution_id`;
   - transition `resolution_id`;
   - transition `composition_id`;
   from actual authoritative results.
6. Add a regression that fails if `resolver` is provided but not invoked during real re-resolution.
7. Add high-risk/ambiguous replacement tests proving fail-closed clarification/blocking behavior.

---

## BLOCKER-02 — Shared-session persistence remains callback-only; there is still no authoritative shared Session Context integration

### Requirement

The approved architecture is:

```text
Phase 8 shared SessionContext
        ↓
DomainSessionContext
        ↓
shared session persistence
        ↓
DomainSessionResumer
```

The phase must preserve Domain Session state across pauses/process restarts using the existing shared session lifecycle/persistence boundary, without creating a separate repository.

### Production evidence

There is still no production `SessionContext` class or shared session store implementation connected to Phase 10.34.

Repository search:

```text
class SessionContext => 0 production definitions
class *Session*Store => 0 production definitions
```

The existing Agent Cognitive Layer exposes an `AgentCognitiveSessionReference` and optional `session_service.get_session(...)`, but Phase 10.34 does not provide a production adapter to that service.

`DomainSessionCodec` only:

- reads mappings or objects with `metadata`;
- attaches state to a copied `dict`;
- never writes through a shared session service.

`DomainSessionResumer` accepts:

```text
session_loader: Callable[[str], Any] | None
persistence_updater: Callable[[DomainSessionContext], None] | None
```

but these are arbitrary callbacks.

Production usage search:

```text
DomainSessionResumer:
  cmm/domains/__init__.py
  cmm/domains/session_resumer.py

DomainSessionCodec:
  cmm/domains/__init__.py
  cmm/domains/session_codec.py
  cmm/domains/session_resumer.py
```

There is no production composition/root/service wiring Domain Sessions to a shared persistent session authority.

### Acceptance-test weakness

The Audit V1 regression test named:

```text
test_resume_loads_domain_state_from_shared_session
```

uses only:

```python
envelope = {"session_id": "...", "metadata": {}}
codec.attach_to_session(envelope, ctx)
persistence_updater=lambda c: None
```

That proves dictionary attachment, not shared persistence or restart durability.

Likewise `AT-DP-034` checkpoint 2 verifies only a dictionary containing the `domain_session` key.

### Impact

The canonical Phase 10.34 API can be instantiated with a no-op lambda as "persistence authority" and then claim:

```text
recorded_resumption=True
```

because interface invocation is treated as proof of durable commit.

Nothing in production binds the Domain Session to the actual shared cognitive/session persistence service.

The phase therefore still does not establish the restart-persistent integration it was intended to add.

### Required remediation

1. Identify or add the canonical generic shared-session persistence service owned outside `cmm.domains`.
2. Add a narrow Domain Session adapter to that real service.
3. The production resume path must:
   - load the shared session by ID;
   - read the domain extension;
   - verify identity;
   - atomically update the shared session/revision;
   - persist it;
   - only then return `recorded_resumption=True`.
4. Keep dependency direction:
   `cmm.domains -> shared session infrastructure`.
5. Do not create an independent `DomainSessionRepository`.
6. Add a real integration test:
   create/persist → process-boundary reload → resume → persist → reload.
7. A no-op callback must not constitute acceptance evidence for durable shared persistence.

---

## BLOCKER-03 — Workflow and conflict revalidation authorities remain optional; stale/blocking state can resume as safe

### Requirement

On resumption Phase 10.34 must:

- detect migrated/incompatible workflows;
- re-evaluate conflicts;
- fail closed on blocking incompatibility;
- reconstruct a session safe to continue.

### Production evidence

`DomainSessionResumer` keeps the following optional:

```text
workflow_evaluator
conflict_evaluator
```

If `workflow_evaluator` is absent:

```python
effective_workflows = context.active_workflow_refs
```

and the persisted workflow refs are preserved without current verification.

If `conflict_evaluator` is absent, persisted conflict refs are never evaluated.

`revalidate_workflows()` itself contains another fail-open path:

```python
if wf_id not in workflow_statuses:
    classification = CURRENT
```

so absence of current workflow evidence is interpreted as current.

### Independent reproduction

With all currently mandatory Phase 10.34 authorities present except workflow evaluation:

```text
persisted active_workflow_refs=('wf:removed',)

result:
P2_WORKFLOW_NO_AUTHORITY RESUMED ('wf:removed',)
```

With a persisted conflict reference and no conflict evaluator:

```text
domain_conflict_refs=('conflict:blocking',)

result:
P3_CONFLICT_NO_AUTHORITY RESUMED ('conflict:blocking',)
```

### Impact

The system can explicitly claim `RESUMED` — documented as "valid, verified and safe to continue" — while workflow validity and conflict safety are unknown.

A required workflow that was deleted/incompatible or an unresolved blocking conflict can therefore survive the resume boundary unchecked.

### Required remediation

1. If relevant workflow refs exist, current workflow authority must be mandatory.
2. Missing workflow evidence must be UNKNOWN/REPLAN/BLOCKED, never `CURRENT`.
3. If conflict refs exist, current conflict evaluation must be mandatory before a continuable result.
4. Add direct regressions for:
   - workflow ref + no authority;
   - workflow status absent from current registry;
   - blocking conflict ref + no conflict authority;
   - conflict evaluator failure;
   - current workflow migration after restart.

---

# 4. Major findings

## MAJOR-01 — Compatible domain-version drift is detected but never committed into the resumed session

### Requirement

The session stores domain versions to detect drift and repeated unchanged resumption must not manufacture repeated drift.

### Production evidence

`session_resumer.py` constructs the resumed context with:

```python
domain_versions=context.domain_versions
```

even after current registry versions were checked.

### Independent reproduction

Persisted:

```text
domain:health = 1.0.0
```

Current registry:

```text
domain:health = 1.1.0
```

First successful resume:

```text
P4_VERSION_AFTER_FIRST {'domain:health': '1.0.0'}
```

Second resume from the just-resumed context:

```text
P4_SECOND_VERSION_CHECKS
[('domain_version_domain:health', 'CHANGED')]
```

The same drift is rediscovered forever.

### Impact

This violates the idempotency/no-artificial-drift requirement and prevents the resumed snapshot from representing the version state that was actually accepted.

### Required remediation

After successful current-state validation, persist the accepted current domain versions into the candidate resumed context.

Add a regression:

```text
resume old compatible version
→ new committed context stores current version
→ immediate identical resume reports version PASS, not CHANGED
```

---

## MAJOR-02 — Resource/knowledge/temporal drift checks are observational only and do not rebuild or invalidate dependent state

### Requirement

Modified/stale inputs must be re-evaluated on resume.

Partial results and traces may be preserved for audit continuity but must not be treated as fresh when their supporting resources/knowledge/temporal state changed.

### Production evidence

`revalidate_resource_and_knowledge_drift()` produces `DRIFT` or `WARNING`.

`revalidate_temporal()` treats the mere presence of a timezone-aware timestamp as:

```text
PASS — Temporal reference is timezone-aware and valid
```

It does not evaluate any temporal validity of referenced knowledge/resources.

`DomainSessionResumer` only uses:

```text
blocking == True
INCOMPATIBLE
```

to gate continuation.

`DRIFT` and `WARNING` do not cause replan/revalidation status changes.

Partial-result and trace references are copied unchanged.

### Independent reproduction

A referenced resource was explicitly marked:

```text
CHANGED:v2
```

while the persisted session contained:

```text
partial_result_refs=('result:old',)
trace_refs=('trace:old',)
```

Result:

```text
status RESUMED

checks:
primary_domain_status PASS
resource_drift_res:x DRIFT
temporal_validity PASS

partial ('result:old',)
trace ('trace:old',)
```

### Impact

The API says the session is verified/safe to continue while its source evidence has explicitly changed and its dependent partial-result/trace continuity has not been classified or invalidated.

### Required remediation

1. Define current dependency drift semantics using existing provenance/resource/knowledge contracts.
2. Map meaningful drift to:
   - `REPLAN_REQUIRED`;
   - `RECOMPOSED`;
   - `BLOCKED`;
   or another explicit safe state.
3. Revalidate dependent partial results/traces/next step.
4. Temporal validity must mean temporal freshness/validity, not just "datetime is timezone-aware".
5. Add stale temporal knowledge and changed-resource E2E tests.

---

## MAJOR-03 — Pending questions and approvals remain trusted when their evaluators are absent

### Requirement

On resume the system must recover **still-valid** questions and approvals and materially changed domains/compositions must trigger question reevaluation.

A historical approval must never silently become current authorization.

### Production evidence

Question and approval evaluators remain optional.

Without them:

```python
recovered_questions = context.pending_domain_question_refs
recovered_approvals = context.approval_refs
```

The state is copied unchanged.

### Independent reproduction

After a material recomposition removing the `fitness` supporting domain:

```text
persisted question = q:fitness-only
no question evaluator

result:
P5_QUESTION_NOT_REEVALUATED
WAITING_FOR_USER ('q:fitness-only',)
```

With:

```text
approval_refs=('approval:expired',)
no approval evaluator
```

result:

```text
P6_APPROVAL_NOT_REEVALUATED
WAITING_FOR_APPROVAL ('approval:expired',)
```

The approval is not used as operation authorization, which is positive, but it is still represented as a current pending approval without validation.

### Required remediation

When these inventories are non-empty:

- require current question/approval authority;
- or explicitly classify them UNKNOWN/REPLAN_REQUIRED until validated.

Material domain/composition changes must force question reevaluation.

---

## MAJOR-04 — Public serialization/contract strictness remains incomplete

### Requirement

Public Phase 10.34 contracts must be immutable, JSON-safe, strict and fail closed.

### Independent reproduction

`DomainSessionResumeRequest` accepts non-finite floats as actor values:

```text
ACTOR_ACCEPTED nan
ACTOR_ACCEPTED inf
```

but:

```python
json.dumps(request.to_dict(), allow_nan=False)
```

fails:

```text
ValueError: Out of range float values are not JSON compliant
```

Therefore construction accepts a value that violates the advertised JSON-safe contract.

`DomainSessionResumeResult` direct construction also accepts invalid revision types:

```text
previous_revision="1"
resumed_revision=True
```

Independent result:

```text
RESULT_BAD_REVISIONS_ACCEPTED 1 True
```

The deserialization route was hardened, but the public dataclass constructor was not.

### Additional immutability concern

`_validate_actor()` converts top-level list/tuple to `tuple(val)` without recursively freezing nested members.

JSON-safe nested mutable objects can therefore remain aliased inside a frozen request.

### Required remediation

1. Reject NaN/Infinity in every JSON-facing scalar field.
2. Apply exact revision validation in `DomainSessionResumeResult.__post_init__`.
3. Enforce result invariants such as revision ordering/recorded state coherence.
4. Recursively freeze actor collections.
5. Add construction-path tests, not only `from_dict()` tests.

---

## MAJOR-05 — `AT-DP-034` still produces a false PASS despite unmet acceptance requirements

### Positive improvement

V2 now contains exactly:

```text
56 unique checkpoint functions
+ 1 meta-test
= 57 tests
```

Independent execution:

```text
57 passed
```

That fixes the V1 absence of a numbered inventory.

### Remaining problem

Several checkpoints are placeholders rather than executable evidence:

```python
test_checkpoint_48_focused_domain_session_tests_pass:
    assert True

test_checkpoint_49_phase_10_domain_tests_pass:
    assert True

test_checkpoint_50_global_tests_pass:
    assert True

test_checkpoint_51_quality_gates_ruff_compile_hygiene:
    assert True

test_checkpoint_53_conservative_matrix_status_before_audit:
    assert True

test_checkpoint_54_git_archive_tar_gz_generation_contract:
    assert True

test_checkpoint_55_independent_audit_criteria_contract:
    assert True

test_checkpoint_56_closure_only_after_clean_audit:
    assert True
```

Other checkpoint tests verify only a subset of their stated requirement:

- checkpoint 2 tests dictionary attachment, not shared-session persistence;
- checkpoint 30 checks rule removal but not all required profile/rule/question/operation reevaluation;
- checkpoint 38 checks event count but not actual shared session revision/history persistence.

Most importantly, all 57 acceptance tests pass while the independent probes above reproduce violations of checkpoints 2, 18, 24, 27, 30, 31, 33, 37, 38 and others.

### Impact

`AT_DP_034=PASS` remains a false-positive acceptance claim.

### Required remediation

A checkpoint may point to externally produced gate evidence, but it must not become `assert True`.

Create one machine-verifiable acceptance manifest linking each checkpoint to:

- executable test node IDs;
- verified external gate artifact/evidence where appropriate;
- explicit state.

The meta-gate must fail when evidence is absent or stale.

---

# 5. Minor finding

## MINOR-01 — Phase 10.35 is named inconsistently across roadmap documents

The detailed canonical Phase 10 roadmap states:

```text
10.35 - Domain SDK
```

`ROADMAP.md` currently states:

```text
Phase 10.35 — Multi-Domain Planning & Orchestration
```

This is inconsistent with the established detailed execution order.

### Required remediation

Restore the canonical Phase 10.35 name/order from the detailed roadmap unless a separately committed roadmap redesign intentionally changed that sequence.

---

# 6. Positive V2 findings

The following V1 findings were materially improved or fixed and should be preserved:

1. Missing current registry authority now blocks.
2. Missing permission authority now blocks.
3. Missing operation authority now blocks.
4. Missing persistence callback no longer claims `recorded_resumption=True`.
5. Session-ID binding now checks request/context/shared envelope and rejects transplantation.
6. Malformed explicitly supplied workflow status now becomes incompatible rather than current.
7. String booleans are rejected on deserialization.
8. String/bool revisions are rejected on deserialization.
9. The 23-event general Domain Event catalog remains unchanged.
10. `domain.session.resumed` was not introduced.
11. Recompositions now invoke a real composer.
12. V2 adds explicit DP-034 / AT-DP-034 matrix rows.
13. The bundle is correctly prefixed.
14. The bundle SHA256 matches the implementation report.
15. The bundle PAX metadata identifies the exact reported remediation HEAD.
16. No `.git`, `.venv`, `__pycache__`, or `.pyc` entries are present.
17. The acceptance inventory now contains exactly 56 uniquely numbered checkpoint functions.
18. All 57 tests in the acceptance file pass independently.
19. `compileall` passes on the extracted Domain/test tree.
20. 300 focused Phase 10.34 tests passed independently under the audit harness; the only harness failure was the external `libcst` dependency.

These improvements are substantial, but they do not satisfy the remaining blocking requirements.

---

# 7. Required V3 remediation gate

Before generating `phase-10.34-audit-v3.tar.gz`, all of the following must be resolved:

```text
BLOCKER_01_CANONICAL_RERESOLUTION=FIXED
BLOCKER_02_SHARED_SESSION_PERSISTENCE=FIXED
BLOCKER_03_WORKFLOW_CONFLICT_FAIL_CLOSED=FIXED

MAJOR_01_DOMAIN_VERSION_COMMIT=FIXED
MAJOR_02_DRIFT_TEMPORAL_RECONCILIATION=FIXED
MAJOR_03_QUESTION_APPROVAL_REVALIDATION=FIXED
MAJOR_04_STRICT_JSON_CONTRACTS=FIXED
MAJOR_05_AT_DP_034_REAL_EVIDENCE=FIXED

MINOR_01_PHASE10_35_ROADMAP_NAME=FIXED
```

Required new regressions include:

```text
canonical resolver is invoked on inactive-primary re-resolution
high-risk/ambiguous replacement cannot bypass resolver policy
new resolution/composition IDs are recorded into transition and context

real shared-session service persists and reloads domain extension
process-boundary reload resumes the committed revision
no-op test callback is not acceptance evidence for shared durability

active workflow + absent current workflow authority cannot RESUME
workflow absent from current registry is not CURRENT
conflict refs + absent current conflict authority cannot RESUME

compatible version drift updates stored domain version
second identical resume after accepted version migration is PASS, not CHANGED

changed resource causes replan/revalidation of dependent results
temporal validity checks actual freshness, not datetime shape only

pending questions require current validation
pending approvals require current validation

NaN actor rejected
Infinity actor rejected
direct ResumeResult string/bool revisions rejected
nested actor collections deeply immutable

AT-DP-034 has no unconditional `assert True` acceptance placeholders
every checkpoint links to real executable or external verified evidence
```

Then rerun:

```text
AT-DP-034
focused Phase 10.34 suite
tests/domains
global suite
Ruff check
Ruff format --check
compileall
diff hygiene
Phase 10.33 event/credential regression gates
```

Only after a clean committed remediation HEAD may V3 be generated from `git archive`.

---

# 8. Final verdict

```text
PHASE10_34_REMEDIATION_V2=INSUFFICIENT
FINAL_INDEPENDENT_AUDIT_V2=FAIL

BLOCKERS=3
MAJORS=5
MINORS=1

DP_034=NOT_VERIFIED
AT_DP_034=FAIL

AUDITED_HEAD=1291d4ab76bacc51a0ff814a1f129517c81f570d
AUDIT_BUNDLE_SHA256=cf422a0b201688725b9a24d75ec8a1b97a4ff12a162a270469f6da52c184ddb5

CLOSURE_ALLOWED=NO
NEXT=RECORD_AUDIT_V2_AND_REMEDIATE_V3
```

Phase 10.34 must not be marked independently audited or closed.
