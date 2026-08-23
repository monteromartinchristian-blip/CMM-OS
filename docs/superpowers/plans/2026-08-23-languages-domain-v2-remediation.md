# Phase 10.26 — Final V2 Re-Audit Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Strict TDD is mandatory.

**Goal:** Close the five remaining findings from the Phase 10.26 independent re-audit V2 and leave the Languages Domain ready for one final independent V3 audit.

**Frozen spec:** `docs/superpowers/specs/2026-08-23-languages-domain-design.md`

**V2 audit:** `docs/superpowers/audits/2026-08-23-phase-10-26-independent-reaudit-v2.md`

## Scope

Starting candidate before this remediation:

```text
a2833ea
```

Remaining findings:

```text
V2-B-001  connected AT-DP-026 lacks the real calendar mutation request → shared approval/external-action path
V2-B-002  connected trace is incomplete and mislabels WorkflowEvent IDs as WORKFLOW_RESULT
V2-M-001  generate_progress_review_result fabricates unrelated/positive progress under insufficient evidence
V2-M-002  evidence-dependent helpers fabricate assessment/feedback/readiness from empty evidence
V2-M-003  review_exercise_result leaks NaN/Inf/malformed numeric values/exceptions
```

Preserve:

```text
domain:languages
Idiomas
LanguageLearningProfile
16 entities
15 resources
14 rules
15 operations
9 workflows
14 production modules
languages.progress_checkpoint
```

No push.
No merge.
No Phase 10.27 changes.
No new Languages production module.
No new Languages planner/runtime/workflow engine/permission engine/store.
Do not revert or weaken any first-audit remediation.
Do not change the two already-authorized shared fixes unless a new RED proves a new shared defect and human approval is obtained.

---

# Task 1 — Fail closed for evidence-free operation results

**Modify:**
- `cmm/domains/languages/operations.py`
- `tests/domains/test_languages_domain_operations.py`
- `tests/domains/test_languages_domain_presentation.py`
- `tests/domains/test_languages_domain_adversarial.py`

Write RED tests before production changes.

## `assess_sample_result`

A schema-valid empty/minimal sample must not produce:

```text
A2
0.75 confidence
positive strengths
```

Required fail-closed semantics when no usable sample evidence exists:

```text
observed_performance = unknown / absent according to schema
confidence = 0 or absent
strengths = []
missing_evidence explicitly includes the required sample evidence
```

No fabricated proficiency level.

## `review_writing_result`

For `writing_sample={}` or empty text:

Must not produce:

```text
score=0.85
estimated_level=A2
Coherent structure
Appropriate register
Formal and appropriate
```

Required:

```text
word_count=0
score unknown/absent or neutral fail-closed value permitted by schema
estimated_level unknown/absent
strengths=[]
register feedback unknown/not assessed
missing evidence explicit
proficiency_upgraded_without_evidence=False only if payload actually contains no unsupported proficiency judgment
```

Add a test deriving the invariant from the content, not merely checking the boolean flag.

## `review_speaking_result`

For empty transcript / no acoustic evidence:

Must not produce:

```text
fluency_score=0.80
```

Required:

```text
fluency not assessed
pronunciation_assessed=False
missing evidence explicit
```

A real transcript may support textual/interaction observations only if the frozen contract allows them; pronunciation still requires acoustic evidence.

## `prepare_certification_result`

`current_profile` must actually influence readiness/gaps.

When profile evidence is absent:

```text
readiness unknown / insufficient evidence
skill_gaps not fabricated
needs_verification/insufficient evidence preserved
```

Do not return constant `0.72` or fixed gaps.

When real profile evidence exists, readiness/gaps must derive from it and the certification target/source.

## Presentation parity

Pass the new fail-closed outputs through `present_languages_result()` and prove the unknown/missing-evidence state survives unchanged.

Commit:

```text
fix(domains): fail closed on missing languages evidence
```

---

# Task 2 — Make progress review fully evidence-derived

**Modify:**
- `cmm/domains/languages/operations.py`
- `tests/domains/test_languages_domain_operations.py`
- `tests/domains/test_languages_domain_adaptation_progression.py`
- `tests/domains/test_languages_domain_presentation.py`
- `tests/domains/test_languages_domain_adversarial.py`

Write RED tests first.

`generate_progress_review_result()` must not hardcode:

```text
writing=improving
reading=consolidated
active_patterns_count=1
certification_readiness=in_progress
recommended_next_focus=Writing coherence and timed tasks
```

Derive all fields from actual arguments/evidence.

Required cases:

### No evidence

```text
overall_progression=insufficient_evidence
stable_progression=False
skill_progress={}
active_patterns_count=0 unless pattern input actually exists
certification_readiness=unknown/not_assessed
recommended_next_focus absent/unknown unless grounded by a real goal/gap/pattern
cross_skill_inflation=False
```

### Writing-only evidence

`skill_progress` must not contain `reading`, `speaking`, etc.

### Multiple skill evidence

Only evidenced skills may appear.

### Cross-skill invariant

Add a content-derived helper/test:

```text
set(skill_progress) <= set(evidenced_skills)
```

unless an explicitly evidenced cross-skill inference contract exists. No such inference is allowed here.

If violated, the operation must not emit `cross_skill_inflation=False`.

### Insufficient evidence

No positive progress claim may coexist with `overall_progression=insufficient_evidence`.

### Pattern count

Must derive from actual pattern state supplied to the operation.

### Certification readiness

Must derive only from certification-specific evidence/profile/target state.

Commit:

```text
fix(domains): ground languages progress review outputs
```

---

# Task 3 — Strict numeric fail-closed semantics

**Modify:**
- `cmm/domains/languages/operations.py`
- `tests/domains/test_languages_domain_operations.py`
- `tests/domains/test_languages_domain_adversarial.py`

Write RED matrix for `review_exercise_result()`:

```text
score=NaN
score=+Inf
score=-Inf
score=True
score=False
score="not-a-number"
score={}
score=[]
score=None
```

For every case:

```text
no uncaught TypeError
no uncaught ValueError
no NaN/Inf in output
strict json.dumps(..., allow_nan=False) succeeds
invalid score does not improve correctness/proficiency/evidence certainty
```

Use one canonical finite-number normalization path.

Do not accept bool as numeric.

If input score is malformed, deterministic fail-closed semantics are required.

Also scan the other 14 operation result builders for equivalent unsafe `float(...)` / numeric coercions and add focused regressions only where the same defect exists.

Commit:

```text
fix(domains): harden languages numeric result handling
```

---

# Task 4 — Restore frozen calendar external-action path in connected AT-DP-026

**Modify:**
- `tests/domains/test_languages_domain_dp026_acceptance.py`
- `tests/domains/test_languages_domain_permissions.py` if reusable boundary coverage belongs there
- production only if RED exposes a real Languages defect

Do not merely increase checkpoint count.

The frozen semantic acceptance must explicitly prove:

```text
Languages produces pedagogical review schedule
→ calendar_modified=False
→ user asks to add calendar event
→ Languages does not mutate calendar
→ request enters existing shared permission/approval/external-operation boundary
→ no external mutation before authorization
```

Use the real shared permission capability corresponding to calendar/schedule mutation.

Do not use `MEMORY_WRITE` as substitute.

Do not add `languages.add_calendar_event`.

If no existing canonical permission capability/path can represent calendar mutation, STOP and ask for human approval before touching shared infrastructure.

## Canonical checkpoints

Maintain exactly 45 **frozen semantic** checkpoints.

Implementation diagnostics such as:
- bootstrap constructed;
- second stale-only run;
- run.outputs visibility;

may be asserted separately but must not replace frozen semantic checkpoints.

Add a regression comparing the exact semantic checkpoint sequence/set against a canonical constant derived from the frozen 45-step spec.

The test must fail if:
- calendar request/routing is removed;
- another technical checkpoint is inserted to keep length 45.

Commit together with Task 5 if both belong to acceptance:

```text
fix(domains): complete connected DP-026 boundaries
```

---

# Task 5 — Rebuild connected trace as typed runtime provenance

**Modify:**
- `tests/domains/test_languages_domain_dp026_acceptance.py`
- `tests/domains/test_languages_domain_trace.py`
- `cmm/domains/languages/trace.py` only if a genuine Languages trace assembly defect is RED-proven
- shared trace contracts only with explicit human approval if frozen semantics cannot be represented

## No self-validating inventory

Forbidden as sole proof:

```python
DomainTraceReferenceInventory(
    references=trace.all_references(),
)
```

Build the expected inventory independently from actual runtime objects/state first.

Then assemble trace.

Then validate trace against that independently collected inventory.

## Correct semantic kinds

Do not label:

```text
WorkflowEvent.event_id
```

as:

```text
WORKFLOW_RESULT
```

A trace reference kind must match the owning runtime object.

If shared contracts do not expose a workflow-result identifier, use the correct shared canonical representation rather than fabricating one.

## Required frozen trace categories

Connected acceptance must represent, where shared trace contracts support them:

```text
primary/supporting domain resolution
LanguageLearningProfile / mode
language
preferred variety
active goal refs
evidence refs
skill scope
proficiency kind
framework
uncertainty
selected rule decisions
operation result refs
workflow run/result state
observed error/pattern decision refs
progression decision
certification-source authority
permission decision
memory proposal/binding state
cross-domain result ref
presentation/result ref
```

At minimum prove exact required categories from frozen trace tests:

```text
profile/mode
operation/workflow runtime refs
evidence refs
proficiency kind
skill scope
rule decisions
permission decisions
memory proposal state
cross-domain result refs
```

If an existing `DomainTraceReferenceKind` does not have a dedicated memory-proposal kind, use an existing semantically correct shared carrier only if the contract defines it. Do not map memory proposal to arbitrary `FINDING` merely to make validation pass.

If the shared trace contract genuinely cannot express one frozen category, STOP and request authorization for the smallest shared-contract extension.

## Actual-ID audit

Build:

```python
expected_id_to_kind: dict[str, DomainTraceReferenceKind]
```

from actual runtime objects.

For every trace ref:

```text
ref_id exists in expected_id_to_kind
ref.kind == expected_id_to_kind[ref_id]
```

And assert every required frozen category is present.

Commit:

```text
fix(domains): complete connected DP-026 trace
```

or combined with Task 4:

```text
fix(domains): complete connected DP-026 boundaries
```

---

# Task 6 — Metamorphic invariant tests

**Modify:**
- `tests/domains/test_languages_domain_adversarial.py`
- relevant focused tests

Add final regressions against false invariant flags.

Required:

```text
cross_skill_inflation=False
→ actual skill_progress contains no unsupported skill

proficiency_upgraded_without_evidence=False
→ no level/score is emitted when required evidence is absent

progression_evidence_valid=True
→ no positive progression payload contradicts insufficient_evidence

temporal_evidence_valid=True
→ source selection actually obeys temporal ranking

pronunciation_evidence_valid=True
→ pronunciation judgment actually has required evidence

pattern_evidence_valid=True
→ pattern content actually has independent comparable recurrence
```

The test must inspect payload content, not just the flag.

Also strict JSON serialize all outputs from all 15 result builders with representative:
- valid input;
- schema-valid minimal input;
- malformed numeric input where applicable.

Commit:

```text
test(domains): enforce languages semantic invariants
```

---

# Task 7 — Final fresh verification

Must run fresh.

## Languages

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_languages_domain_*.py
```

## Shared workflow/composition/permissions

Run:
- workflow engine/execution suites;
- composer/resolver suites;
- permission gate/approval suites;
- Languages permission/memory/cross-domain suites.

## All domains

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains
```

## Global

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q
```

## Ruff

```bash
.venv/bin/ruff check \
  cmm/domains/languages \
  tests/domains/test_languages_domain_*.py

.venv/bin/ruff check --target-version py310 \
  cmm/domains/languages \
  tests/domains/test_languages_domain_*.py
```

## Compileall

Use temporary pycache.

## Fresh import

Assert no registration side effects.

## Canon

```text
16/15/14/15/9
14 modules
languages.progress_checkpoint
```

## Direct V2 probes

Print explicit PASS markers:

```text
EMPTY_ASSESSMENT_FAIL_CLOSED=PASS
EMPTY_WRITING_FAIL_CLOSED=PASS
EMPTY_SPEAKING_FAIL_CLOSED=PASS
EMPTY_CERTIFICATION_PROFILE_FAIL_CLOSED=PASS
NO_EVIDENCE_PROGRESS_FAIL_CLOSED=PASS
WRITING_ONLY_NO_READING_INFLATION=PASS
PROGRESS_PAYLOAD_INVARIANT=PASS
NAN_EXERCISE_SCORE_FAIL_CLOSED=PASS
INF_EXERCISE_SCORE_FAIL_CLOSED=PASS
MALFORMED_EXERCISE_SCORE_FAIL_CLOSED=PASS
CALENDAR_EXTERNAL_BOUNDARY=PASS
TRACE_EXPECTED_KIND_MAP=PASS
TRACE_NO_EVENT_AS_WORKFLOW_RESULT=PASS
TRACE_REQUIRED_CATEGORIES=PASS
```

## AT-DP-026 markers

Required:

```text
AT_DP_026_FROZEN_SEMANTIC_CHECKPOINTS=45
AT_DP_026_CALENDAR_REQUEST=PASS
AT_DP_026_CALENDAR_SHARED_BOUNDARY=PASS
AT_DP_026_REAL_WORKFLOWS=9
AT_DP_026_ACTUAL_TRACE_IDS=PASS
AT_DP_026_TRACE_KIND_PARITY=PASS
AT_DP_026_TRACE_REQUIRED_CATEGORIES=PASS
AT_DP_026_CONNECTED=PASS
```

---

# Task 8 — Documentation

After every remediation gate is green, update status only to:

```text
V2 independent re-audit: FAIL
V2 findings remediated: 2 BLOCKER + 3 MAJOR
candidate connected AT-DP-026: PASS
independent V3 audit: PENDING
DP-026: REQUIRES_PHASE_INSPECTION
```

Do not mark closed/audited.

Commit:

```text
docs(domains): record phase 10.26 V2 remediation
```

---

# Expected commit sequence

```text
fix(domains): fail closed on missing languages evidence
fix(domains): ground languages progress review outputs
fix(domains): harden languages numeric result handling
fix(domains): complete connected DP-026 boundaries
fix(domains): complete connected DP-026 trace
test(domains): enforce languages semantic invariants
docs(domains): record phase 10.26 V2 remediation
```

Tasks 4 and 5 may be one commit if the connected acceptance and trace changes are inseparable.

---

# Definition of Done

```text
[ ] V2-B-001 calendar path genuinely connected
[ ] frozen 45 semantic checkpoints exact, not merely length 45
[ ] V2-B-002 trace uses independently built expected-kind inventory
[ ] WorkflowEvent ID never mislabeled WORKFLOW_RESULT
[ ] frozen trace categories covered
[ ] V2-M-001 no fabricated cross-skill progress
[ ] V2-M-001 no positive progress under insufficient evidence
[ ] V2-M-002 empty assessment fails closed
[ ] V2-M-002 empty writing fails closed
[ ] V2-M-002 empty speaking fails closed
[ ] V2-M-002 certification readiness/gaps derive from current profile evidence
[ ] V2-M-003 NaN/Inf/malformed scores fail closed
[ ] all public outputs strict JSON-safe
[ ] metamorphic invariant tests inspect payload content
[ ] all 9 workflows still real
[ ] real PermissionGate lifecycle still green
[ ] real resolver/composer still green
[ ] Languages suite green
[ ] tests/domains green
[ ] global suite green
[ ] Ruff green
[ ] Ruff py310 green
[ ] compileall green
[ ] fresh import green
[ ] canon 16/15/14/15/9
[ ] package 14 modules
[ ] Paternidad unchanged
[ ] tracked worktree clean
[ ] no push
[ ] no merge
[ ] independent V3 audit pending
```

Final status only if all remediation gates are green:

```text
PHASE10_26_V2_REMEDIATION_STATUS:
READY_FOR_INDEPENDENT_V3_AUDIT
```
