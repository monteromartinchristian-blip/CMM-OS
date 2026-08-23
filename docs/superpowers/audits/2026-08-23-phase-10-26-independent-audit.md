# Phase 10.26 — Independent Audit

## Audit identity

- **Project:** CMM OS
- **Phase:** 10.26 — Languages Domain
- **Role:** independent software auditor
- **Branch reported by bundle:** `feature/phase-10-domain-intelligence`
- **BASE_SHA:** `17a6ea7`
- **HEAD_SHA:** `93c2679958b646563a26d6739a2a230ffa95b8e6`
- **Audit bundle SHA-256:** `214a653f4d38d0a9c230bdea2e2642026b5688f794505dc344490541962f7ad3`
- **Verdict:** `FAIL`
- **Repository modified by audit:** NO
- **Push:** NO
- **Merge:** NO

The audit was performed against the closed `tar.gz` bundle, not against the implementation agent's summary.

## Sources reviewed

Authoritative sources:

- `docs/superpowers/specs/2026-08-23-languages-domain-design.md`
- `docs/superpowers/plans/2026-08-23-languages-domain-implementation.md`
- `docs/reference/languages-domain.md`
- `docs/reference/domain-intelligence-requirements-matrix.md`
- `docs/roadmap/phase-10-domain-intelligence.md`
- `ROADMAP.md`

Implementation:

- all 14 files under `cmm/domains/languages/`
- all 19 `tests/domains/test_languages_domain_*.py`
- bundled shared Domain/Workflow/Permission/Trace contracts
- implementation diff and commit list
- final verification evidence

## Diff scope reviewed

Bundle reports implementation range:

```text
17a6ea7..93c2679
```

The implementation range contains 14 implementation/documentation commits and adds:

- 14 Languages production modules;
- 19 Languages test modules;
- Languages reference documentation;
- roadmap/matrix updates.

No shared production infrastructure file appears in the implementation diff.

## Fresh verification evidence reviewed

The bundled final-verification log records:

```text
Languages focused suite: 99 passed
Relevant sibling/shared regressions: 2478 passed
Full Domain suite: 5742 passed
Global suite: 11270 passed
Ruff: PASS
Ruff py310: PASS
compileall: PASS
fresh import: PASS
package boundary: PASS
schema parity test presence: PASS
workflow producer-field static audit: PASS
tracked worktree: clean (known tmp/ only)
```

Those results are credible as regression evidence, but they are **not sufficient for closure** because multiple frozen semantics are not exercised by the tests and several direct source-level reproductions contradict the required behavior.

---

# Canon audit

**PASS**

Runtime catalog is structurally aligned with the frozen canon:

```text
domain:languages
Display name: Idiomas
Profile: LanguageLearningProfile
Version: 1.0.0

16 entities
15 resources
14 rules
15 operations
9 workflows
```

The frozen workflow ID `languages.progress_checkpoint` is correctly present.

The package contains exactly the required 14 production modules.

`catalog.py` is the structural catalog source used by definition/resources/profile/workflows.

---

# Architecture audit

**PASS with findings elsewhere**

Positive findings:

- no Languages-specific planner/runtime/store/workflow engine/permission engine/calendar engine was introduced;
- operations reuse shared contracts;
- workflows reuse shared Workflow contracts;
- memory uses shared proposal/binding/view contracts;
- trace reuses shared Trace contracts;
- bootstrap composes with General;
- import-time registration is avoided.

The structural architecture is sound. The failures are primarily **semantic correctness and acceptance-proof failures**, not parallel-infrastructure drift.

---

# Findings

## B-001 — BLOCKER — `AT-DP-026` is not the frozen connected acceptance test

### Exact files / symbols

- `tests/domains/test_languages_domain_dp026_acceptance.py`
  - imports/direct helper use: lines 12–40
  - `_ScenarioATDP026`: lines 48–283
  - final scenario test: lines 285–303
  - synthetic trace IDs: lines 255–280
- Frozen spec:
  - `docs/superpowers/specs/2026-08-23-languages-domain-design.md`
  - §§120–121, lines 4147–4236 in the bundled file.

### Frozen requirement violated

The frozen design explicitly requires:

```text
one connected deterministic scenario
resolver
→ Languages profile
→ authorized resources
→ assessment
→ evidence typing
→ learning plan
→ lesson workflow
→ exercise result
→ error observation
→ conversation / roleplay workflow
→ error-pattern evidence
→ writing review
→ progress checkpoint
→ certification temporal verification
→ review proposal
→ permission boundary
→ memory proposal
→ cross-domain projection
→ presentation
→ trace
```

It further states:

```text
AT-DP-026 must not be a disconnected sequence of helper calls with unrelated fixtures.
Later steps must consume actual results from earlier steps.
```

The frozen scenario enumerates 45 conceptual steps.

### Evidence / reproduction

The actual test:

- calls `assess_sample_result()` directly;
- calls rule helpers directly;
- calls `create_learning_plan_result()` directly;
- calls lesson/exercise helpers directly;
- never executes the shared Domain Resolver;
- never executes `languages.adaptive_language_lesson`;
- never executes `languages.conversation_roleplay_practice`;
- never executes `languages.progress_checkpoint` through the Workflow Engine;
- never executes the shared PermissionGate/Approval lifecycle;
- never creates/validates a Languages memory proposal in the acceptance path;
- never performs the required Oppositions composition/minimal projection;
- never feeds actual prior runtime IDs into trace.

Trace is assembled with caller-fabricated IDs such as:

```text
resolution_result_id="res-at-1"
composition_id="comp-at-1"
domain_result_id="res-out-at-1"
```

Those IDs were not produced by the preceding resolver/composer/workflow path.

### Why current tests did not catch it

The test itself is labelled "25-step canonical scenario" and asserts only its own helper-level sequence. The focused/global suite therefore passes while testing the wrong acceptance shape.

The static workflow producer-field audit checks **field declaration connectivity**, not end-to-end acceptance connectivity.

### Minimal remediation

Replace the current acceptance harness with a state-linked deterministic harness that:

1. boots/registers Languages through shared registries;
2. resolves a real Languages-primary request;
3. uses injected deterministic operation implementations through the real operation registry;
4. executes the required real workflows;
5. carries result IDs/state from producer to consumer;
6. exercises PermissionGate + memory proposal lifecycle;
7. performs real cross-domain composition/minimal projection;
8. builds trace from actual generated IDs.

### Required regression test

A test must fail if any required stage is replaced by an unrelated fixture/helper result or if trace references an ID that was not produced by the connected run.

---

## B-002 — BLOCKER — Workflow validation gates encode fixed "successful" outcomes and reject legitimate pedagogical states

### Exact files / symbols

`cmm/domains/languages/workflows.py`:

- proficiency assessment gate: lines 149–154
- adaptive lesson gate: lines 192–197
- writing review gate: lines 264–269
- certification gate: lines 372–381
- progress gate: lines 406–410

Shared engine:

- `shared/cmm/workflows/engine.py`
- `_evaluate_validate_node()`: lines 107–164

### Frozen requirement violated

The plan requires gates to validate safety/epistemic boundaries, not require a single pedagogical result:

- proficiency gate: no certificate overwrite, stable update only when justified, missing skills preserved;
- lesson gate: no direct stable-proficiency mutation from one session;
- writing gate: valid alternatives survive;
- certification temporal gate: preserve `needs_verification` correctly;
- progress gate: one isolated improvement is not stable, while accumulated comparable evidence may legitimately support stable progression.

### Evidence / reproduction

The shared Workflow Engine uses strict equality:

```text
field present + unequal expected value -> validate.condition_false
```

The Languages workflows currently require:

```python
# proficiency assessment
{"is_certified": False, "stable_update_supported": False}

# adaptive lesson
{"is_correct": True, "pattern_candidate": False}

# writing review
{"score": 0.85, "estimated_level": "B2"}

# certification
{
    "needs_verification": False,
    "registration_performed": False,
    "payment_performed": False,
    "submission_performed": False,
}

# progress
{"stable_progression": False}
```

Consequences:

1. a learner answering an exercise incorrectly causes the adaptive lesson workflow to fail;
2. a valid short writing sample estimated as `A2` causes the writing workflow to fail;
3. certification information that correctly returns `needs_verification=True` causes certification workflow failure instead of surfacing the verification requirement;
4. a legitimately evidenced `stable_progression=True` causes the progress workflow to fail;
5. a certified existing record cannot pass the proficiency gate even when preservation is correct.

These are normal/required states, not safety violations.

### Why current tests did not catch it

`test_languages_domain_workflows.py` only checks:

- workflow structure;
- whether wait-condition keys exist in direct producer schemas;
- a few key names.

It does **not** execute the workflows through the real Workflow Engine with representative valid/invalid outcomes, despite the implementation plan explicitly requiring real shared-engine violation tests.

### Minimal remediation

Redesign validation outputs/gates around invariant fields, for example:

```text
certificate_overwritten == False
stable_update_invalid == False
missing_skills_preserved == True
stable_proficiency_changed == False
valid_variety_misclassified == False
calendar_modified == False
registration/payment/submission == False
temporal_state_valid == True
progression_evidence_valid == True
```

A legitimate `needs_verification=True`, `is_correct=False`, `estimated_level=A2`, or `stable_progression=True` must not itself be a workflow failure.

### Required regression tests

Execute each workflow through the shared Workflow Engine and prove at least:

- wrong exercise answer completes pedagogically while preserving safety;
- short/A2 writing completes review;
- certification with `needs_verification=True` completes with verification-needed state;
- justified stable progression completes;
- invalid safety/epistemic mutations fail closed.

---

## M-001 — MAJOR — Generic evidence IDs can be promoted to `CERTIFIED`

### Exact file / symbol

`cmm/domains/languages/rules.py`

- `classify_proficiency_record()`: lines 132–177
- problematic fallback: lines 159–162

### Frozen requirement violated

Frozen design §16:

```text
certificate -> CERTIFIED
evidence-based inference -> ESTIMATED
single task/session -> OBSERVED_PERFORMANCE
```

It must prevent:

```text
estimate promotion to certificate
certificate rewriting from informal evidence
```

The design also states that a certified result requires adequate evidence.

### Evidence / independent reproduction

The implementation defines certification as true if either official evidence exists **or**:

```python
any(
    isinstance(e, dict)
    and "id" in e
    and not e.get("is_observed_only")
    for e in deduped_ev
)
```

Independent probe against the extracted function produced:

```text
({'id': 'generic-1'},)
=> CERTIFIED True

({'id': 'sample-1', 'source': 'user_message'},)
=> CERTIFIED True
```

Only an explicit `is_observed_only=True` prevents the promotion.

Thus caller-controlled generic evidence with an ID is sufficient to create a certified record.

### Why current tests did not catch it

The positive test uses explicit `source_kind="official_certificate"`. There is no negative test requesting `kind="CERTIFIED"` with generic/user/sample evidence.

### Minimal remediation

Certification must require a closed, grounded official-credential evidence contract. Remove generic `"id"` as certification authority.

### Required regression test

```text
kind=CERTIFIED + generic evidence id
-> NOT CERTIFIED

kind=CERTIFIED + user_message/sample evidence
-> NOT CERTIFIED

kind=CERTIFIED + recognized official credential evidence
-> CERTIFIED
```

---

## M-002 — MAJOR — Duplicate / non-comparable evidence can create false stable level and false recurrent error pattern

### Exact files / symbols

`cmm/domains/languages/rules.py`:

- `_deduplicate_evidence()`: lines 112–129
- `evaluate_level_update()`: lines 180–228
- `evaluate_error_pattern()`: lines 561–625

`cmm/domains/languages/operations.py`:

- `update_level_evidence_result()`: lines 631–681

### Frozen / plan requirement violated

Implementation plan:

```text
duplicate evidence IDs/provenance do not inflate
same copied sentence repeated -> not independent
same error duplicated under different caller IDs with same provenance -> no inflation
```

Frozen invariant:

```text
one error != recurrent error pattern
practice result != stable proficiency
```

### Evidence / independent reproduction

#### Level evidence

`_deduplicate_evidence()` includes caller-controlled `id` in the dedup key:

```python
key = f"{ev_id}:{source}:{observed}:{skill}:{score}"
```

Therefore identical provenance/content under different IDs remains duplicated.

Independent probe:

```text
two records:
id=caller-1 / caller-2
source=same-sample
observed=B2
skill=writing
score=0.8
```

produced:

```text
DEDUP_LEN=2
stable_update_supported=True
proposed_level=B2
reason=consistent_comparable_evidence
```

#### Error pattern

When `context_id` is absent:

```python
ctx_id = ... or obs_id
```

Two copies of the same occurrence with different caller IDs are treated as independent contexts.

Independent probe:

```text
same provenance
same sentence
same error_type
different caller IDs
```

produced:

```text
pattern_state='candidate'
eligible=True
independent_occurrences=2
```

#### Operation layer

`update_level_evidence_result()` is even weaker:

```python
has_two_comparable = len(all_ev) >= 2
```

It does not actually verify comparability or deduplicate provenance.

### Why current tests did not catch it

The copied-sentence test supplies the same explicit `context_id`, so it passes.

The required adversarial case "same error duplicated under different caller IDs with same provenance" is listed in the plan but absent from `test_languages_domain_adversarial.py`.

No test covers two non-comparable level-evidence items with different IDs.

### Minimal remediation

Create a canonical evidence identity based on provenance/source/task occurrence, not caller ID.

Require explicit comparability dimensions before stable update/pattern promotion.

Make `update_level_evidence_result()` delegate to the canonical `evaluate_level_update()` semantics instead of implementing a weaker `len >= 2` branch.

### Required regression tests

- same provenance/content + different IDs -> one evidence unit;
- no `context_id` + same provenance -> not independent;
- two non-comparable observations -> no stable update;
- two genuinely independent comparable observations -> candidate/stable result only as justified.

---

## M-003 — MAJOR — Progression ignores comparability and can report stable improvement without historical evidence

### Exact file / symbol

`cmm/domains/languages/rules.py`

- `evaluate_progression()`: lines 925–973

### Frozen requirement violated

`ProgressionEvidenceRule` must preserve:

```text
prior version
current evidence
comparability
confidence
missing evidence
```

Required test semantics:

```text
one better result -> not stable progression
comparable repeated improvement -> stable improvement may be supported
non-comparable tasks -> insufficient evidence / qualified result
```

### Evidence / independent reproduction

The implementation:

- does not inspect a `comparable` field;
- does not verify task/skill comparability;
- defaults missing prior evidence to `prev_avg = 0.5`;
- with 2 current scores can mark stable improvement.

Independent probes produced:

```text
non-comparable current tasks + one prior task
-> stable_improvement / stable_progression=True

no previous evidence + two high current scores
-> stable_improvement / stable_progression=True
```

### Why current tests did not catch it

The "repeated comparable improvement" test sets `"comparable": True`, but the production function never reads that field. The test therefore appears to prove comparability while actually proving only "two scores are high".

There is no negative test with `"comparable": False`.

### Minimal remediation

Require explicit comparable dimensions and meaningful prior evidence before stable progression.

If comparability or baseline is absent:

```text
insufficient_evidence
```

or a qualified non-stable observation.

### Required regression test

Two high but non-comparable current results must not produce `stable_improvement`.

Two high current results with no prior baseline must not produce stable progression.

---

## M-004 — MAJOR — Certification temporal rule can select stale official information over current official information

### Exact file / symbol

`cmm/domains/languages/rules.py`

- `evaluate_certification_source()`: lines 976–1024

### Frozen requirement violated

Canonical precedence:

```text
current official source
>
current authoritative secondary source
>
historical memory
>
unverified guide
```

The result must preserve temporal states:

```text
current
historical
unknown
stale
needs_verification
```

Required test:

```text
stale official information
-> needs verification when materially relevant
```

### Evidence / independent reproduction

The implementation ranks by `source_type`/numeric authority but does not evaluate temporal validity/currentness.

Independent probe:

```python
(
  {"id":"stale-official","source_type":"official","date_valid":False,"format":"4_tasks"},
  {"id":"current-official","source_type":"official","date_valid":True,"format":"4_tasks"},
)
```

with `decision_critical=True` produced:

```text
selected_source = stale-official
unresolved_conflict = False
needs_verification = False
```

This is the opposite of the frozen temporal requirement.

### Why current tests did not catch it

The test named "current official source outranks stale guide/memory" supplies:

```text
guide: date_valid=True
official: date_valid=True
```

It does not test stale official information.

The `date_valid` field is not consumed by the production function.

### Minimal remediation

Include temporal state in authority ranking:

1. current official;
2. current authoritative secondary;
3. historical/stale official as historical evidence only;
4. historical memory;
5. unverified guide.

Decision-critical stale/unknown states must set `needs_verification=True`.

### Required regression tests

- stale official first + current official second -> current wins;
- stale official only + decision-critical -> `needs_verification=True`;
- unknown temporal status + decision-critical -> verification required.

---

## M-005 — MAJOR — Frozen shared PermissionGate lifecycle is not regression-tested by Languages

### Exact files

- `tests/domains/test_languages_domain_permissions.py`: lines 16–61
- `tests/domains/test_languages_domain_memory.py`: lines 44–187
- `tests/domains/test_languages_domain_dp026_acceptance.py`: no PermissionGate/ApprovalService lifecycle
- Implementation plan Task 9: lines 2001–2022

### Requirement violated

The implementation plan explicitly requires proof using the **actual Phase 10.15 permission resolver/gate and ApprovalService contracts**:

```text
no grant -> no persistence
valid scoped grant -> canonical apply path may proceed
one-shot grant cannot be reused
expired grant fails
out-of-scope grant fails
supporting domain cannot widen permission
proposal itself does not consume/apply mutation permission
```

### Evidence

Search across all 19 Languages tests finds no use of:

```text
PermissionGate
ApprovalService
one_time grant consumption
expired approval
scope mismatch
```

The permission test verifies policy tuple membership and strict booleans.

The memory test verifies DomainMemory snapshot/binding validation, which is a different layer.

### Runtime assessment

The **policy structure itself appears correctly configured**:

```text
MEMORY_WRITE in allowed_capabilities
MEMORY_WRITE in approval_capabilities
MEMORY_WRITE not prohibited
allow_memory_write=True
```

The shared evaluator would therefore request approval rather than directly allow it.

This finding is a missing mandatory regression/acceptance proof, not evidence that the policy is necessarily wrong.

### Minimal remediation

Add real PermissionResolver/PermissionGate/ApprovalService tests covering the complete lifecycle and include that path in connected AT-DP-026.

---

# Additional observations

## INFO — Structural schema parity is present but does not prove semantic correctness

`test_languages_operation_schema_parity()` uses the real shared schema validator and is valuable.

The failures above show the distinction:

```text
valid JSON/schema shape != valid domain semantics
```

## INFO — Final verification was useful but its workflow audit was structural only

The final verification correctly proved that every gate field exists in a direct producer output schema.

It did **not** prove that the expected value in each gate represents a valid invariant.

That is why B-002 survived a green direct-producer audit.

## INFO — Cross-domain test coverage is substantially narrower than the implementation plan

The plan requires real resolver/composition cases for Languages/University/Oppositions/General/Concerns/Reflection and purpose-minimized outbound projections.

`test_languages_domain_cross_domain.py` mainly verifies:

- General fallback exists;
- `domain_result` metadata;
- no obvious sibling-store names;
- union of prohibited permissions;
- isolated Languages registration;
- JSON safety of a synthetic payload.

This is already materially implicated by B-001 because connected acceptance also omits the required real cross-domain path.

## INFO — Presentation tests do not use actual outputs of all 15 operations

The implementation plan requested actual helper-output parity through presentation.

The current presentation tests use hand-built fixtures and one speaking-like fixture. This should be strengthened during remediation, but it is not separately necessary to determine the current FAIL verdict.

---

# Residual risks

Because the audit found BLOCKER-level acceptance/workflow defects, the audit intentionally did not treat the green global suite as closure evidence.

Additional latent issues may remain after the listed defects are fixed. A fresh re-audit is required after remediation.

Particular areas to re-audit:

- real resolver routing for all cross-domain ownership cases;
- full PermissionGate/ApprovalService memory lifecycle;
- all nine workflows executed through shared engine with both valid-success and valid-qualified outcomes;
- trace IDs bound to actual connected runtime results;
- progression/certification semantics after fixing evidence/temporal logic;
- operation semantic helpers for invented/static pedagogical outputs.

---

# Verdict

```text
FAIL
```

Counts:

```text
BLOCKERS=2
MAJORS=5
MINORS=0
```

The implementation is **not ready for closure**.

The existing documentation state:

```text
AT-DP-026 candidate acceptance = PASS
```

must not be promoted to independently audited/closed. After remediation, the candidate acceptance must be rebuilt and re-run before independent re-audit.

No production changes were made during this audit.

---

```text
PHASE10_26_INDEPENDENT_AUDIT=FAIL
BLOCKERS=2
MAJORS=5
MINORS=0
REPO_MODIFIED=NO
PUSH=NO
MERGE=NO
```
