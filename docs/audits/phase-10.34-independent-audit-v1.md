# Phase 10.34 — Domain Sessions
## Independent Audit V1

**Audit date:** 2026-08-30
**Auditor:** ChatGPT — independent project auditor
**Audit target:** Phase 10.34 — Domain Sessions
**Implementation HEAD:** `063d0d3f2910294f54c122510a328dc2ce4cb071`
**Bundle:** `phase-10.34-audit-v1.tar.gz`
**Bundle SHA256:** `9febf39ac55117f877d7f33f71a46c503c4b554f19f098eddd7eaf382b902bcf`
**Bundle members:** 1,862
**Bundle source verification:** `git get-tar-commit-id` resolves exactly to the implementation HEAD above
**Verdict:** **FAIL — remediation required**

```text
FINAL_INDEPENDENT_AUDIT_V1=FAIL

BLOCKERS=3
MAJORS=4
MINORS=2

DP_034=NOT_VERIFIED
AT_DP_034=FAIL
PHASE10_34_CLOSURE=BLOCKED
```

---

## 1. Scope and evidence

The audit was performed against the contents of the uploaded Git archive, not against the implementation agent's prose report.

Canonical audit sources:

- `docs/superpowers/specs/2026-08-30-domain-sessions-design.md`;
- `docs/superpowers/plans/2026-08-30-domain-sessions-implementation-plan.md`;
- `docs/roadmap/phase-10-domain-intelligence.md`;
- `docs/reference/domain-intelligence-requirements-matrix.md`;
- production code under `cmm/domains/session_*.py`;
- Phase 10.34 tests under `tests/domains/test_domain_session_*.py`;
- existing Phase 10 registry, permission, operation, conflict and event infrastructure in the bundle.

Independent archive checks:

```text
SHA256=9febf39ac55117f877d7f33f71a46c503c4b554f19f098eddd7eaf382b902bcf
COMMIT_ID=063d0d3f2910294f54c122510a328dc2ce4cb071
MEMBERS=1862
FORBIDDEN_ARCHIVE_PATHS=.git/.venv/__pycache__/*.pyc => NONE
COMPILEALL=PASS
```

The full pytest suite could not be independently rerun in the audit container because the clean Git archive does not contain the repository virtualenv and the audit runtime does not have `libcst`. That environmental limitation is **not** the reason for the FAIL verdict. The verdict is based on independently reproduced functional failures in Phase 10.34 code itself.

The implementation agent reported:

```text
Focused Domain Sessions: 215 passed
Domain suite: 8055 passed
Global suite: 13595 passed
```

Those counts are retained as implementation-side evidence, but they do not override the failing independent probes below.

---

# 2. Blockers

## BLOCKER-01 — Resumption fails open when current authorization/revalidation authorities are absent

### Requirement violated

The approved Phase 10.34 design states:

```text
Persisted domain snapshot != current authorization or current truth
```

Acceptance requirements include:

- current active/enabled domains must be checked;
- current permissions must be re-evaluated;
- stale permissions must never authorize an operation;
- stale operation availability must never become current executable availability;
- malformed or unavailable authorization state must fail closed.

### Evidence

`cmm/domains/session_revalidation.py`:

- lines 58–66: missing `DomainRegistry` is reported as a **PASS** and registry validation is skipped.

`cmm/domains/session_resumer.py`:

- lines 103–105: if no registry is supplied, `_is_domain_active()` returns `True`;
- lines 289–295: if no permission evaluator is supplied, persisted `effective_permission_refs` are copied directly into the resumed context;
- lines 297–303: if no operation filter is supplied, persisted `available_operation_ids` are copied directly into the resumed context.

All of these dependencies are optional in the public constructor.

### Independent reproduction

```text
PROBE1_DEFAULT_STALE_AUTH
RESUMED ('perm:admin',) ('op:delete_all',) True
```

A persisted snapshot containing:

```text
effective_permission_refs=('perm:admin',)
available_operation_ids=('op:delete_all',)
```

was resumed with `DomainSessionResumer()` using no current permission or operation authority.

The result was:

```text
status=RESUMED
effective_permission_refs=('perm:admin',)
available_operation_ids=('op:delete_all',)
recorded_resumption=True
```

### Impact

The canonical resumer can promote stale authorization evidence into current resumed state. Even though `resume()` does not directly execute the operation, downstream continuation receives the stale permission and operation inventories as the current context.

This defeats the central security invariant of Phase 10.34.

### Required remediation

The canonical production resumer must never have a fail-open path.

At minimum:

1. current domain registry/status validation must be mandatory for a resumable session;
2. current permission resolution must be mandatory before continuation;
3. current operation availability must be recomputed from current registries/policies, not filtered from a historical allow-list alone;
4. absence/failure of a required authority must produce `BLOCKED` or `FAILED`, never `PASS`/`RESUMED`;
5. add adversarial tests proving the default/canonical construction cannot preserve stale authorization.

---

## BLOCKER-02 — Re-resolution/recomposition are nominal statuses, not reconstruction of current Domain Intelligence state

### Requirement violated

Phase 10.34 requires resumption to:

- reconstruct composition;
- re-evaluate the effective profile;
- re-evaluate effective rules;
- re-evaluate permissions;
- re-evaluate questions;
- recalculate operations;
- preserve and record a material domain transition.

The design acceptance gate explicitly requires:

```text
29. resumption reconstructs current composition
30. material composition/domain changes trigger profile/rule/question/operation reevaluation
```

### Evidence

`cmm/domains/session_resumer.py`:

- constructor lines 46–47 accepts `resolver` and `composer`;
- lines 89–90 stores them;
- neither `self._resolver` nor `self._composer` is ever read again;
- lines 272–287 may set status `RECOMPOSED` only by pruning inactive supporting domain IDs;
- lines 377–400 construct the new context while copying:
  - the old `composition_id`;
  - the old `effective_profile`;
  - the old `effective_rule_ids`;
  - and, absent optional callbacks, the old permissions and operations.

Static audit:

```text
_resolver occurrences on self = 1
_composer occurrences on self = 1
```

Both occurrences are assignment only.

### Independent reproduction

```text
PROBE5_RECOMPOSITION_NOT_REBUILT
RECOMPOSED composition:OLD profile:OLD ('rule:OLD',) ('perm:OLD',) ('op:OLD',)
```

A supporting domain was disabled and the resumer returned `RECOMPOSED`, yet the resumed context retained the old composition, profile, rules, permissions and operations.

A composer object deliberately designed to fail if invoked was never touched.

### Impact

The result status claims semantic recomposition without actually recomposing Domain Intelligence. The resumed context can therefore be internally inconsistent with its current participating domains.

This is a core functional failure of the phase objective, not a cosmetic issue.

### Required remediation

Wire the canonical existing Phase 10 resolver/composer and derived-state services into the resumption flow.

A real material domain change must produce a current authoritative composition and derive/re-evaluate:

- composition ID;
- profile;
- rules;
- permissions;
- operation availability;
- questions;
- conflicts;
- next step;
- version/current-domain state.

Tests must fail if a `RECOMPOSED` or `RE_RESOLVED` result merely copies stale effective state.

---

## BLOCKER-03 — No authoritative shared-session persistence integration; resume may claim it was recorded when nothing was persisted

### Requirement violated

The approved architecture requires:

```text
Phase 8 shared SessionContext
        ↓
DomainSessionContext
        ↓
shared session persistence
```

Acceptance requirements include:

```text
2. reuse Phase 8 session infrastructure
38. record resumption through shared session revision/history
45. persistence failure cannot leave or claim partially committed state
```

Phase 10.34 is specifically intended to survive pauses and process restarts.

### Evidence

`cmm/domains/session_codec.py`:

- operates only on arbitrary mappings / `metadata`;
- does not integrate with a production shared Session Context repository/service;
- `attach_to_session()` performs only an in-memory dictionary copy.

Production symbol usage:

```text
DomainSessionCodec:
  cmm/domains/__init__.py
  cmm/domains/session_codec.py
  cmm/domains/session_resumer.py

DomainSessionResumer:
  cmm/domains/__init__.py
  cmm/domains/session_resumer.py
```

There is no production integration point that loads/resumes a persisted shared session.

`cmm/domains/session_resumer.py`:

- requires the caller to provide the session context explicitly;
- `persistence_updater` is optional;
- lines 403–418 call persistence only when the optional callback exists;
- lines 451–464 nevertheless return `recorded_resumption=True` and increment the resumed revision even when no persistence updater exists.

The same behavior was independently observed in `PROBE1`.

### Impact

The canonical API can report a recorded resumed revision without recording anything. That invalidates restart durability and audit semantics.

The implementation is currently a domain-session data model plus callbacks, not a completed shared persistent-session integration.

### Required remediation

Integrate with the actual shared session lifecycle/persistence boundary used by the project. If the Phase 8 implementation lacks a suitable generic extension mechanism, extend that shared boundary generically without reversing dependency direction.

The canonical resume path must:

1. load the authoritative shared session by `session_id`;
2. validate the domain extension belongs to that shared session;
3. commit the new domain revision atomically through shared persistence;
4. set `recorded_resumption=True` only after that commit;
5. fail closed if the persistence authority is unavailable.

---

# 3. Major findings

## MAJOR-01 — Session identity mismatch permits state transplantation between sessions

### Evidence

`cmm/domains/session_resumer.py` line 141:

```python
session_id = request.session_id or context.session_id
```

`DomainSessionResumeRequest.session_id` is required, so the request ID always wins.

There is no equality/binding check between:

- the request session ID;
- `DomainSessionContext.session_id`;
- an outer shared-session envelope ID.

`DomainSessionCodec.attach_to_session()` also attaches a `DomainSessionContext` to an arbitrary envelope without verifying matching session IDs.

### Independent reproduction

```text
PROBE2_SESSION_ID_MISMATCH
RESUMED session-B session-B domain:health
```

Context from `session-A` was resumed under request `session-B` and returned as session B.

### Impact

State, domain references, approvals, traces, sensitive references and authorization history can be transplanted between sessions.

### Required remediation

Bind all three identities fail-closed:

```text
request.session_id
==
shared SessionContext.id
==
DomainSessionContext.session_id
```

Any mismatch must raise a structured session-integrity error before revalidation or persistence.

---

## MAJOR-02 — Resource/knowledge/temporal/workflow revalidation contains fail-open placeholders

### Evidence

`cmm/domains/session_revalidation.py`:

- lines 286–295: if no current resource version is supplied, a referenced resource is reported `PASS` as “reference preserved”;
- lines 348–357: the same occurs for knowledge;
- lines 378–385: no current temporal reference produces `PASS` as “Temporal validity preserved” without temporal evaluation;
- lines 433–437: an invalid/unrecognized workflow status is silently converted to `CURRENT`.

Independent reproduction:

```text
PROBE8_UNKNOWN_DRIFT_IS_PASS
resource => PASS
knowledge => PASS

PROBE9_TEMPORAL_WITH_NO_CURRENT_REFERENCE_IS_PASS
temporal_validity => PASS

PROBE7_WORKFLOW_MALFORMED_STATUS_FAIL_OPEN
invalid workflow status => PASS / CURRENT
```

### Impact

“Unknown/unverified” is being represented as verified current state.

This is contrary to the phase's fail-closed resumption model and can suppress required replan/block decisions.

### Required remediation

Use current canonical metadata/temporal/workflow authorities. Absence or malformed state must be represented as `UNKNOWN`, `WARNING`, `REPLAN_REQUIRED`, `BLOCKED`, or `FAILED` according to risk/policy — never fabricated `PASS`.

---

## MAJOR-03 — Serialization is not fully strict or JSON-safe

### Evidence

`cmm/domains/session_contracts.py`:

- `DomainSessionCheck.from_dict()` uses `bool(data.get("blocking", False))`;
- `DomainSessionResumeResult.from_dict()` uses `int(...)` for revisions and `bool(...)` for `recorded_resumption`;
- `DomainSessionResumeRequest.actor` is typed as `Any | None`;
- `to_dict()` emits `actor` unchanged.

Independent reproduction:

```text
blocking_input="false" -> True
recorded_resumption_input="false" -> True
previous_revision_input="1" -> accepted as integer 1
arbitrary actor object -> TypeError during JSON serialization
```

### Impact

Malformed serialized state is silently normalized instead of failing closed. In particular, the audit-relevant `recorded_resumption` flag can invert from the string `"false"` to boolean `True`.

### Required remediation

Require exact types:

- booleans must be real `bool`;
- revisions must be real non-bool integers satisfying invariants;
- actor must use a repository-native JSON-safe actor/reference contract or a validated scalar contract;
- all request/result public contracts need strict JSON round-trip tests.

---

## MAJOR-04 — `AT-DP-034=PASS` is not backed by an explicit 56-checkpoint executable inventory and failed to catch violated acceptance requirements

### Evidence

The design defines 56 acceptance conditions.

The implementation provides:

```text
tests/domains/test_domain_session_acceptance.py
```

with only 8 test functions. Section comments label broad checkpoint ranges, but there is:

- no stable 56-item checkpoint inventory;
- no executable 1:1 checkpoint-to-test mapping;
- no `AT_DP_034` accounting helper;
- no independently verifiable logical checkpoint count.

Static audit:

```text
acceptance_test_functions=8
```

The requirements matrix contains neither:

```text
DP-034
AT-DP-034
```

despite the implementation plan explicitly requiring them.

More importantly, the gate reported PASS while BLOCKER-01 through BLOCKER-03 violate multiple enumerated acceptance requirements.

### Impact

The acceptance gate does not establish the claimed Phase 10.34 contract. The “56 checks” claim is presently documentary, not executable acceptance accounting.

### Required remediation

Create a canonical checkpoint inventory for all 56 design requirements and connect every checkpoint to executable evidence.

The gate must fail when any requirement is absent.

At minimum, the newly discovered audit regressions must be explicit named checkpoints/tests.

---

# 4. Minor findings

## MINOR-01 — Audit bundle packaging deviates from the committed implementation plan

The plan required:

```text
--prefix="CMM-OS-phase-10.34/"
```

The uploaded archive has no prefix:

```text
FIRST_MEMBER=.claude/
```

The implementation agent's final report also omitted the required SHA256 and full verification block.

The bundle is still auditable:

```text
git get-tar-commit-id => 063d0d3f2910294f54c122510a328dc2ce4cb071
SHA256 => 9febf39ac55117f877d7f33f71a46c503c4b554f19f098eddd7eaf382b902bcf
forbidden paths => none
```

Therefore this is procedural rather than a bundle-integrity blocker.

### Required remediation

Generate V2 with the exact committed bundle procedure and report SHA256/verification explicitly.

---

## MINOR-02 — Pre-audit roadmap/status documentation is inconsistent

`ROADMAP.md` still states:

```text
Next milestone: Phase 10.34 — Domain Sessions
```

although the implementation-side plan required the next implementation milestone to become Phase 10.35 after the implementation gates passed.

The requirements matrix says 10.34 is implemented/pending audit, but does not contain the required `DP-034` / `AT-DP-034` entries.

### Required remediation

After functional remediation and before the next bundle:

- add canonical `DP-034` / `AT-DP-034` evidence to the matrix;
- keep 10.34 explicitly pending independent audit;
- set the next **implementation** milestone consistently to 10.35 without declaring 10.34 closed/audited.

---

# 5. Independent positive findings

The V1 implementation does establish several useful foundations that should be preserved during remediation:

1. `DomainSessionContext` is immutable/slotted and reference-first.
2. Domain/session metadata reuse the canonical Phase 10.33 credential-signature detector rather than duplicating the registry.
3. The general Domain Event catalog remains exactly 23 events.
4. No `domain.session.resumed` event was added.
5. No `AgentRuntimeEventBus`, Domain Event store, durable queue, replay mechanism or DLQ was introduced by the new session modules.
6. The archive is a genuine `git archive` of the reported implementation commit.
7. The archive excludes `.git`, `.venv`, `__pycache__` and `.pyc`.
8. `compileall` succeeds on `cmm/domains` and `tests/domains`.
9. The implementation preserves a clear reference-first session contract that can be retained while correcting the integration/revalidation layer.

These positives do not offset the blocking failures above.

---

# 6. Required V2 remediation gate

Before producing `phase-10.34-audit-v2.tar.gz`, all of the following must be true:

```text
BLOCKER_01_STALE_AUTH_FAIL_OPEN=FIXED
BLOCKER_02_REAL_RECOMPOSITION=FIXED
BLOCKER_03_SHARED_SESSION_PERSISTENCE=FIXED

MAJOR_01_SESSION_ID_BINDING=FIXED
MAJOR_02_REAL_REVALIDATION=FIXED
MAJOR_03_STRICT_SERIALIZATION=FIXED
MAJOR_04_AT_DP_034_ACCOUNTING=FIXED

MINOR_01_AUDIT_PACKAGING=FIXED
MINOR_02_DOCUMENTATION_ALIGNMENT=FIXED
```

Required adversarial regressions include at least:

```text
default resumer cannot preserve stale permissions
default resumer cannot preserve stale operation availability
missing registry/current authority fails closed
request/context/shared-session ID mismatch fails closed
RECOMPOSED actually receives a new current composition
material domain change recalculates profile/rules/permissions/questions/operations
unknown resource/knowledge state is not PASS
missing temporal authority is not fabricated PASS
malformed workflow status fails closed
"false" is rejected for boolean fields
string revisions are rejected
resume cannot claim recorded_resumption without successful shared persistence
AT-DP-034 enumerates and verifies all 56 checkpoints
```

Then rerun:

```text
focused Phase 10.34 suite
AT-DP-034
tests/domains
global suite
Ruff check
Ruff format --check
compileall
diff hygiene
Phase 10.33 event/credential regression gates
```

Only after a clean committed remediation HEAD may a new `git archive` V2 be generated.

---

# 7. Final verdict

```text
PHASE10_34_IMPLEMENTATION=REMEDIATION_REQUIRED
FINAL_INDEPENDENT_AUDIT_V1=FAIL

BLOCKERS=3
MAJORS=4
MINORS=2

DP_034=NOT_VERIFIED
AT_DP_034=FAIL

AUDITED_HEAD=063d0d3f2910294f54c122510a328dc2ce4cb071
AUDIT_BUNDLE_SHA256=9febf39ac55117f877d7f33f71a46c503c4b554f19f098eddd7eaf382b902bcf

CLOSURE_ALLOWED=NO
NEXT=RECORD_AUDIT_V1_AND_REMEDIATE
```

Phase 10.34 must **not** be marked complete or independently audited at this point.
