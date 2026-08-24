# Languages Final Epistemic Invariant Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate Phase 10.26 Languages epistemic semantics into a single invariant layer so the final candidate cannot accept the same proficiency/framework/source/numeric claim through a legacy-permissive alternate path.

**Architecture:** Keep the change Languages-local, primarily in `cmm/domains/languages/rules.py`. Introduce/reuse a small set of private invariant helpers for proficiency evidence binding, strict framework mapping applicability, certification source authority, and finite semantic numbers. Route every relevant public rule helper through those invariants, remove contradictory legacy test expectations, and add cross-path meta-tests that prove semantic mutations are rejected consistently.

**Tech Stack:** Python 3.10-compatible code, pytest, Ruff, existing CMM OS domain runtime and Phase 10.26 Languages package.

**Spec:** `docs/superpowers/specs/2026-08-24-languages-final-epistemic-invariant-consolidation-design.md`

## Global Constraints

- Work only on `feature/phase-10-domain-intelligence`.
- Required execution ancestry: `070d1a2` (audited design baseline) and `e238821` (implementation-plan handoff) must both be ancestors of the current HEAD.
- Do not reset, rewrite history, push, merge, or close Phase 10.26.
- Preserve frozen canon exactly: 16 entities / 15 resources / 14 rules / 15 operations / 9 workflows / 14 Languages production modules.
- Do not touch Phase 10.27 / Paternidad.
- Prefer changes in `cmm/domains/languages/rules.py` plus existing Languages tests.
- No new Languages production module.
- No shared-engine change unless a RED demonstrates an unavoidable generic defect; if unavoidable, keep it minimal, RED-proven, separately committed, and fully regressed.
- Every semantic change follows RED → verify RED reason → minimal GREEN → focused regression → adversarial mutation → commit.
- Do not create the final audit bundle until every mandatory direct marker and contract-consistency gate is PASS.
- Do not preserve tests whose expectations contradict the final design merely to keep historical tests green; update those tests to the canonical final invariant.

---

## File structure / ownership

Primary production:

```text
cmm/domains/languages/rules.py
```

Primary closure tests:

```text
tests/domains/test_languages_domain_rule_closure.py
```

Related existing tests, modify only when the canonical invariant requires it:

```text
tests/domains/test_languages_domain_adaptation_progression.py
tests/domains/test_languages_domain_adversarial.py
tests/domains/test_languages_domain_dp026_acceptance.py
tests/domains/test_languages_domain_operations.py
```

Other `tests/domains/test_languages_domain_*.py` files may be updated only when a legacy expectation directly contradicts the final invariant contract.

Evidence artifacts under `tmp/`:

```text
tmp/phase10-26-final-invariant-red.txt
tmp/phase10-26-final-contract-consistency.txt
tmp/phase10-26-final-adversarial-review.md
tmp/phase10-26-final-direct-markers.txt
tmp/phase10-26-final-rule-tests.txt
tmp/phase10-26-final-languages-tests.txt
tmp/phase10-26-final-connected-tests.txt
tmp/phase10-26-final-shared-regressions.txt
tmp/phase10-26-final-all-domains.txt
tmp/phase10-26-final-global.txt
tmp/phase10-26-final-ruff.txt
tmp/phase10-26-final-ruff-py310.txt
tmp/phase10-26-final-compileall.txt
tmp/phase10-26-final-fresh-import.txt
tmp/phase10-26-final-canon.txt
tmp/phase10-26-final-git-diff-check.txt
tmp/phase10-26-final-parenthood-scope.txt
```

Final bundle:

```text
tmp/phase-10-26-final-invariant-independent-closure-audit-bundle.tar.gz
```

---

### Task 0: Freeze baseline and build the final RED ledger

**Files:**
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Test: `tests/domains/test_languages_domain_adaptation_progression.py`
- Test: `tests/domains/test_languages_domain_adversarial.py`
- Evidence: `tmp/phase10-26-final-invariant-red.txt`

**Interfaces:**
- Consumes: current canonical public helpers in `cmm/domains/languages/rules.py`.
- Produces: one reproducible RED ledger containing every known surviving bypass before production changes.

- [ ] **Step 1: Verify baseline identity**

Run:

```bash
cd "/Users/chris/CMM OS"
test "$(git branch --show-current)" = "feature/phase-10-domain-intelligence"
git merge-base --is-ancestor 070d1a2 HEAD
git merge-base --is-ancestor e238821 HEAD
git status --short --branch
```

Expected:

```text
tracked worktree clean
only tmp/ untracked
```

- [ ] **Step 2: Run current Languages baseline**

Run:

```bash
pytest -q tests/domains/test_languages_domain_*.py
```

Expected: current suite GREEN before adding final REDs.

- [ ] **Step 3: Add REDs for incomplete framework mapping records**

Add tests proving all of these are rejected for cross-framework calibration:

```python
{"source_id": "conc-1", "target_range": "B2"}
{"source_framework": "IELTS", "source_id": "conc-1", "target_range": "B2"}
{"source_value": "6.5", "source_id": "conc-1", "target_range": "B2"}
{"target_framework": "CEFR", "source_id": "conc-1", "target_range": "B2"}
```

A fully applicable positive record must include:

```python
{
    "source_id": "conc-1",
    "source_framework": "IELTS",
    "source_value": "6.5",
    "target_framework": "CEFR",
    "target_range": "B2",
}
```

- [ ] **Step 4: Add REDs for textual `source_range`**

Add a test establishing final policy:

```python
{
    "source_id": "conc-1",
    "source_framework": "IELTS",
    "source_range": "6.0-7.0",
    "target_framework": "CEFR",
    "target_range": "B2",
}
```

must **not** calibrate in Phase 10.26 final closure.

The test must assert:

```text
calibrated=False
```

unless the implementation already contains a fully structured, property-tested range contract. Do not add such a subsystem merely to preserve this field.

- [ ] **Step 5: Add RED for cross-framework `evaluate_level_update()`**

Create existing CEFR B2 writing record plus two independent ACTFL C1 writing observations with matching comparison key.

Assert:

```text
stable_update_supported=False
```

and no CEFR C1 proposal from ACTFL identity evidence.

- [ ] **Step 6: Add RED that stable update preserves framework**

For a valid CEFR B2 → CEFR C1 stable update, assert the resulting record contains:

```python
"framework": "CEFR"
```

- [ ] **Step 7: Add source-authority category REDs**

For each of:

```text
session_id
sample_id
assessment_id
context_id
```

construct:

```python
{
    "source_type": "official",
    "temporal_state": "current",
    <occurrence_alias>: "x",
}
```

Assert:

```text
authority_rank != 6
needs_verification=True
```

- [ ] **Step 8: Add GoalAlignment generic-practice RED**

Two active goals:

```text
certification C1
conversation fluency
```

Activity:

```python
{"type": "practice"}
```

Assert it does not align both goals.

- [ ] **Step 9: Add nested bool numeric RED**

Call `evaluate_learning_load()` with:

```python
deadlines=({"days_remaining": True},)
```

Assert `exam_practice` is not added solely because of the bool.

- [ ] **Step 10: Run only new REDs and capture exact failures**

Run the exact test node IDs. Capture output:

```bash
pytest -q <new-node-ids...> | tee tmp/phase10-26-final-invariant-red.txt
```

Expected: every new test FAILS for the intended semantic reason.

If any test is already GREEN, inspect whether production is already correct or the test is not exercising the bypass. Do not manufacture a failure.

- [ ] **Step 11: Commit RED tests only**

```bash
git add tests/domains/test_languages_domain_*.py tmp/phase10-26-final-invariant-red.txt
git commit -m "test(languages): expose final epistemic invariant bypasses"
```

If `tmp/` is intentionally ignored, do not force-add it in this commit; include it later in the audit bundle.

---

### Task 1: Centralize framework-bound proficiency evidence

**Files:**
- Modify: `cmm/domains/languages/rules.py`
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Test: `tests/domains/test_languages_domain_adaptation_progression.py`

**Interfaces:**
- Consumes: canonical evidence mappings already accepted by Languages.
- Produces: one private predicate used by direct classification and stable level update.

- [ ] **Step 1: Identify existing duplicated predicates**

Read all logic used by:

```text
classify_proficiency_record
evaluate_level_update
```

and list the currently duplicated checks for framework, skill, observed value, provenance, comparability.

- [ ] **Step 2: Implement one private predicate**

Implement one private helper equivalent to:

```python
def _proficiency_evidence_supports_claim(
    record: Mapping[str, Any],
    *,
    requested_framework: str,
    requested_skill: str | None,
    requested_value: Any | None,
    require_comparable: bool,
) -> bool:
    ...
```

Required properties:

```text
mapping input only
non-empty canonical provenance
framework match when evidence declares framework
skill match when claim is skill-scoped
requested value supported
comparability required when requested
bool/non-finite numeric values never become support
```

Do not implement framework conversion here.

- [ ] **Step 3: Route `classify_proficiency_record()` through it**

Remove duplicated claim-binding conditions now superseded by the helper.

- [ ] **Step 4: Route `evaluate_level_update()` through it**

The stable-update path must use the same helper and requested framework from the existing record / explicit call context.

- [ ] **Step 5: Preserve framework in updated record**

When returning a framework-dependent estimated level, include the normalized framework explicitly.

- [ ] **Step 6: Run focused REDs**

Expected:

```text
cross-framework classifier blocked
cross-framework level update blocked
valid same-framework stable update preserved
framework preserved in output
```

- [ ] **Step 7: Run all proficiency/progression tests**

```bash
pytest -q \
  tests/domains/test_languages_domain_adaptation_progression.py \
  tests/domains/test_languages_domain_rule_closure.py \
  tests/domains/test_languages_domain_operations.py
```

- [ ] **Step 8: Mutation review**

Temporarily reason/test that removing the framework check would make both classifier and level-update tests fail. The test suite must cover both paths.

- [ ] **Step 9: Commit**

```bash
git add cmm/domains/languages/rules.py tests/domains/
git commit -m "fix(languages): unify proficiency evidence binding"
```

---

### Task 2: Make framework mapping records complete and non-permissive

**Files:**
- Modify: `cmm/domains/languages/rules.py`
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Test: any existing Languages framework-mapping tests that encode the old permissive contract

**Interfaces:**
- Consumes: cross-framework mapping request and evidence records.
- Produces: calibrated mapping only from a complete applicable record.

- [ ] **Step 1: Define the final complete mapping record**

A calibrated record requires exactly these semantic components:

```text
source provenance
source_framework
source_value
target_framework
target_range
```

Use existing canonical aliases only for provenance identity.

- [ ] **Step 2: Reject incomplete records before applicability checks**

Do not write:

```python
if field_present and mismatched: reject
```

Write semantics equivalent to:

```text
required field missing -> not applicable
required field malformed -> not applicable
required field mismatched -> not applicable
```

- [ ] **Step 3: Reject textual `source_range` as calibration evidence**

Do not use substring matching.

A record containing only `source_range` instead of `source_value` remains visible as insufficient mapping evidence but cannot set:

```text
calibrated=True
```

- [ ] **Step 4: Normalize exact source values deterministically**

Use a conservative normalization that preserves type semantics. Do not make `True == 1`.

For numeric source values:
- bool rejected;
- finite numeric accepted;
- normalized numeric equality permitted.

For strings:
- trim and case-normalize only where the existing framework contract already treats the value as symbolic text.

- [ ] **Step 5: Update legacy tests**

Search all Languages tests asserting:

```text
grounded_approximate_mapping
calibrated=True
```

and inspect their mapping record.

Any test relying on:

```python
{"source_id": "...", "target_range": "..."}
```

alone must be updated to a full applicable record.

Do not delete useful provenance-alias coverage; enrich each fixture with the required applicability fields.

- [ ] **Step 6: Add explicit legacy minimal-record rejection test**

Required:

```python
minimal = {"source_id": "conc-1", "target_range": "B2"}
```

for `IELTS 6.5 -> CEFR` must not calibrate.

- [ ] **Step 7: Run all framework mapping tests**

Expected all GREEN.

- [ ] **Step 8: Commit**

```bash
git add cmm/domains/languages/rules.py tests/domains/
git commit -m "fix(languages): require complete framework mapping records"
```

---

### Task 3: Narrow certification source authority provenance

**Files:**
- Modify: `cmm/domains/languages/rules.py`
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Test: `tests/domains/test_languages_domain_dp026_acceptance.py`

**Interfaces:**
- Consumes: certification source records.
- Produces: authority rank based on source identity, not occurrence identity.

- [ ] **Step 1: Create a dedicated authority predicate**

Implement a private predicate equivalent to:

```python
def _has_certification_source_authority_identity(
    source: Mapping[str, Any],
) -> bool:
    ...
```

Accepted identities:

```text
official_source_id
source_id
```

If retaining `provenance_id`, document/test that it denotes source provenance in this context. Otherwise exclude it.

Explicitly do not accept:

```text
session_id
sample_id
assessment_id
context_id
```

- [ ] **Step 2: Route certification authority ranking through it**

Do not call the generic evidence provenance helper for source authority.

- [ ] **Step 3: Preserve temporal ordering**

Existing semantics for:

```text
current grounded official
stale grounded official
current grounded secondary
conflict / verification
```

must remain intact.

- [ ] **Step 4: Strengthen AT-DP-026 mutation**

The acceptance fixture retains its grounded `official_source_id`.

Add a test/probe that removing that exact source identity weakens the source authority result.

Keep the exact 45 checkpoint names and 9 real workflows.

- [ ] **Step 5: Run focused tests**

Expected:

```text
official + official_source_id -> rank 6 when otherwise valid
official + source_id -> rank 6 when otherwise valid
official + session_id only -> not rank 6
official + sample_id only -> not rank 6
official + assessment_id only -> not rank 6
official + context_id only -> not rank 6
```

- [ ] **Step 6: Commit**

```bash
git add cmm/domains/languages/rules.py tests/domains/
git commit -m "fix(languages): narrow certification source authority"
```

---

### Task 4: Centralize semantic numeric validation

**Files:**
- Modify: `cmm/domains/languages/rules.py`
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Test: `tests/domains/test_languages_domain_adaptation_progression.py`

**Interfaces:**
- Consumes: decision-driving numeric inputs.
- Produces: finite non-bool validated numbers or `None`.

- [ ] **Step 1: Consolidate existing numeric helpers**

Implement/reuse one helper equivalent to:

```python
def _finite_semantic_number(
    value: Any,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    ...
```

Required:

```text
bool -> None
NaN -> None
+Inf/-Inf -> None
non-numeric -> None
below minimum -> None
above maximum -> None
valid int/float -> finite float
```

- [ ] **Step 2: Route `deadline.days_remaining` through it**

Urgency may be inferred only from a valid semantic number.

`True` must not mean one day.

- [ ] **Step 3: Audit every decision-driving numeric in `rules.py`**

Search for:

```text
isinstance(..., (int, float))
float(
int(
math.isnan
math.isfinite
```

Review every match.

Where the value can increase certainty, priority, difficulty, mastery, review priority, or workload, use the common semantic numeric boundary.

Do not refactor cosmetic counts that cannot influence an epistemic/pedagogical decision.

- [ ] **Step 4: Add nested numeric mutation tests**

At minimum:

```text
deadline True
deadline NaN
deadline Inf
adaptive True/NaN/Inf
mastery True/NaN/Inf
recall True/NaN/Inf
importance True/NaN/Inf
```

All invalid values must fail closed.

- [ ] **Step 5: Run focused rule suite**

Expected GREEN.

- [ ] **Step 6: Commit**

```bash
git add cmm/domains/languages/rules.py tests/domains/
git commit -m "fix(languages): centralize semantic numeric guards"
```

---

### Task 5: Remove universal generic GoalAlignment shortcut

**Files:**
- Modify: `cmm/domains/languages/rules.py`
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Test: `tests/domains/test_languages_domain_adversarial.py`

**Interfaces:**
- Consumes: normalized activity representations and active goals.
- Produces: alignment only from goal-specific semantic relations.

- [ ] **Step 1: Remove generic universal alignment**

Delete/refactor semantics equivalent to:

```text
type in practice/review/lesson/exercise -> every goal aligned
purpose in practice/review/lesson/study -> every goal aligned
```

- [ ] **Step 2: Keep supported linkage paths**

Alignment may be supported by:

```text
explicit goal_id/goal_ids
skill/skills overlap
specific purpose relation
specific activity type relation
```

- [ ] **Step 3: Keep generic activity valid but epistemically weak**

Generic `practice` may produce:

```text
not specifically aligned
```

rather than being rejected as an invalid activity.

- [ ] **Step 4: Add concurrent-goal adversarial test**

With unrelated active goals, generic practice must not align all.

- [ ] **Step 5: Verify existing roleplay/writing/certification positives**

Specific semantic activities must still align correctly.

- [ ] **Step 6: Commit**

```bash
git add cmm/domains/languages/rules.py tests/domains/
git commit -m "fix(languages): require semantic goal alignment"
```

---

### Task 6: Add cross-path invariant meta-tests

**Files:**
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Test: `tests/domains/test_languages_domain_adversarial.py`

**Interfaces:**
- Consumes: final invariant helpers indirectly through public rule APIs.
- Produces: a closure gate that fails when one path becomes more permissive than another.

- [ ] **Step 1: Add proficiency cross-path matrix**

Exercise:

```text
classify_proficiency_record
evaluate_level_update
evaluate_framework_mapping
```

with matching and mismatching frameworks.

Required invariant:

```text
direct same-framework evidence may support
cross-framework identity evidence may not
mapping requires complete grounded applicability
```

- [ ] **Step 2: Add authority cross-path matrix**

Exercise:

```text
evaluate_certification_source
AT-DP-026 fixture mutation
```

with source identity present/removed.

- [ ] **Step 3: Add numeric cross-path matrix**

For representative decision-driving numeric fields:

```text
valid numeric -> used
True/NaN/Inf -> no semantic upgrade
```

- [ ] **Step 4: Add goal-alignment representation matrix**

Check coherent semantics for:

```text
type
skill
skills
purpose
goal_id
goal_ids
```

and generic `practice`.

- [ ] **Step 5: Give the meta-tests explicit names**

Names must make source grep/review easy, including:

```text
single_source
cross_path
legacy_contract
semantic_numeric
source_authority
```

- [ ] **Step 6: Run meta-tests alone**

Expected GREEN only after Tasks 1–5.

- [ ] **Step 7: Commit**

```bash
git add tests/domains/
git commit -m "test(languages): enforce cross-path epistemic invariants"
```

---

### Task 7: Eliminate contradictory legacy test contracts

**Files:**
- Review: all `tests/domains/test_languages_domain_*.py`
- Evidence: `tmp/phase10-26-final-contract-consistency.txt`

**Interfaces:**
- Consumes: entire Languages test suite.
- Produces: reviewer-inspected proof that no old test requires a forbidden permissive contract.

- [ ] **Step 1: Search material assertions**

Run searches for:

```bash
rg -n \
  'grounded_approximate_mapping|calibrated|authority_rank|needs_verification|stable_update_supported|aligned_goals|activity_fit' \
  tests/domains/test_languages_domain_*.py
```

- [ ] **Step 2: Inspect every result manually**

For each assertion, determine whether its fixture satisfies the final spec.

Specifically reject tests requiring:

```text
provenance + target_range only -> calibrated
generic occurrence ID -> source authority
generic practice -> all goals aligned
cross-framework identity evidence -> stable proficiency
```

- [ ] **Step 3: Update contradictory fixtures/expectations**

Preserve test intent where possible. Remove only the permissive assumption.

- [ ] **Step 4: Run a second search for minimal mapping fixtures**

Search:

```bash
rg -n -U \
  'source_id.{0,160}target_range|target_range.{0,160}source_id' \
  tests/domains/test_languages_domain_*.py
```

Inspect every hit that expects calibration.

- [ ] **Step 5: Create consistency evidence**

Write:

```text
LEGACY_CONTRACT_CONTRADICTIONS=0
MAPPING_MINIMAL_LEGACY_EXPECTATIONS=0
GENERIC_OCCURRENCE_AUTHORITY_EXPECTATIONS=0
GENERIC_PRACTICE_UNIVERSAL_EXPECTATIONS=0
CROSS_FRAMEWORK_LEVEL_UPDATE_EXPECTATIONS=0
```

to:

```text
tmp/phase10-26-final-contract-consistency.txt
```

Only write zeros after manual inspection.

- [ ] **Step 6: Run all Languages tests**

```bash
pytest -q tests/domains/test_languages_domain_*.py
```

- [ ] **Step 7: Commit test-contract normalization**

```bash
git add tests/domains/
git commit -m "test(languages): remove legacy permissive contracts"
```

---

### Task 8: Historical bypass adversarial closure

**Files:**
- Test: existing Languages tests as needed
- Evidence: `tmp/phase10-26-final-adversarial-review.md`

**Interfaces:**
- Consumes: all historical audit findings V1/V2/V3/rule-hardening/epistemic-binding.
- Produces: one explicit no-survivor adversarial review.

- [ ] **Step 1: Build historical bypass ledger**

Include every item from the final design §14:

```text
no-evidence estimate
wrong skill
wrong framework
cross-framework level update
incomplete mapping records
minimal legacy mapping
textual source_range
unprovenanced official
session/sample/assessment/context authority aliases
threshold=1
adaptive comparable=False
adaptive duplicate provenance
bool/Inf adaptive score
duplicate spaced review
negative/bool mastery
bool deadline
generic practice universal alignment
arbitrary cultural mapping
exercise unknown
vocabulary grounding
runtime trace/permission identity
calendar boundary
```

- [ ] **Step 2: Map each bypass to an exact living test**

The review must name the test node or file/test function for each item.

No “covered by suite” generic claims.

- [ ] **Step 3: Attempt new alternate-path bypasses**

Search public helpers in `rules.py` for:
- duplicated framework comparisons;
- generic provenance helpers used for authority;
- direct `isinstance(int,float)` decisions;
- hard-coded positive pedagogical defaults;
- ignored semantic parameters.

- [ ] **Step 4: Fix any surviving bypass using the central invariant, not a local exception**

If a new bypass is found, return to RED before production changes.

- [ ] **Step 5: Write adversarial review**

Required conclusion:

```text
Critical=0
Important=0
Minor=0
ALL_HISTORICAL_BYPASSES_BLOCKED=PASS
```

If not zero, do not proceed.

---

### Task 9: Connected AT-DP-026 final invariant gate

**Files:**
- Test: `tests/domains/test_languages_domain_dp026_acceptance.py`
- Production: only if a real connected defect is discovered

**Interfaces:**
- Consumes: final canonical 45 checkpoints and 9 workflows.
- Produces: connected candidate PASS with source-authority mutation.

- [ ] **Step 1: Verify exact frozen checkpoint names/count**

Assert exactly 45 canonical checkpoint identifiers.

- [ ] **Step 2: Verify exactly 9 real workflows execute**

Do not accept static/fake workflow IDs.

- [ ] **Step 3: Verify runtime trace identity**

Preserve:
- real rule execution result IDs;
- real PermissionGate decision IDs;
- WorkflowRun IDs;
- selected profile mode;
- presentation result references;
- memory proposal/binding references.

- [ ] **Step 4: Verify certification fixture is grounded**

Current official source must contain real source authority identity.

- [ ] **Step 5: Add source-authority negative mutation**

Remove the source authority identity from an equivalent source and assert the certification authority gate weakens/fails.

- [ ] **Step 6: Run connected suite**

Expected all PASS.

- [ ] **Step 7: Commit if tests changed**

```bash
git add tests/domains/test_languages_domain_dp026_acceptance.py
git commit -m "test(languages): close DP-026 source authority mutation"
```

---

### Task 10: Full verification and direct markers

**Files:**
- Evidence under `tmp/`
- No production change unless a verification failure reveals a real defect

**Interfaces:**
- Consumes: completed implementation.
- Produces: fresh independent-audit evidence.

- [ ] **Step 1: Dedicated invariant/rule suite**

```bash
pytest -q tests/domains/test_languages_domain_rule_closure.py \
  | tee tmp/phase10-26-final-rule-tests.txt
```

- [ ] **Step 2: All Languages**

```bash
pytest -q tests/domains/test_languages_domain_*.py \
  | tee tmp/phase10-26-final-languages-tests.txt
```

- [ ] **Step 3: Connected acceptance**

Run the DP-026 acceptance file and capture:

```text
tmp/phase10-26-final-connected-tests.txt
```

- [ ] **Step 4: Shared regressions**

Run relevant shared rule runtime, trace, permission, workflow, composer, resolver tests and capture:

```text
tmp/phase10-26-final-shared-regressions.txt
```

- [ ] **Step 5: All domains**

```bash
pytest -q tests/domains/ \
  | tee tmp/phase10-26-final-all-domains.txt
```

- [ ] **Step 6: Global**

```bash
pytest -q \
  | tee tmp/phase10-26-final-global.txt
```

- [ ] **Step 7: Ruff**

Capture normal and py310-compatible checks separately:

```text
tmp/phase10-26-final-ruff.txt
tmp/phase10-26-final-ruff-py310.txt
```

- [ ] **Step 8: Isolated compileall**

Capture:

```text
tmp/phase10-26-final-compileall.txt
```

- [ ] **Step 9: Fresh import + canon**

Capture:
- import of Languages package in a fresh interpreter;
- counts 16/15/14/15/9;
- 14 production modules.

Files:

```text
tmp/phase10-26-final-fresh-import.txt
tmp/phase10-26-final-canon.txt
```

- [ ] **Step 10: Git diff and Paternidad scope**

Capture:

```bash
git diff --check
git diff 070d1a2..HEAD --name-only
git diff 070d1a2..HEAD -- cmm/domains/parenthood docs | ...
```

Ensure no Phase 10.27 production change.

- [ ] **Step 11: Generate direct markers from real probes**

Create:

```text
tmp/phase10-26-final-direct-markers.txt
```

Required exact markers:

```text
PROFICIENCY_BINDING_SINGLE_SOURCE=PASS
CLASSIFY_FRAMEWORK_BINDING=PASS
LEVEL_UPDATE_FRAMEWORK_BINDING=PASS
LEVEL_UPDATE_PRESERVES_FRAMEWORK=PASS

FRAMEWORK_MAPPING_COMPLETE_RECORD_REQUIRED=PASS
FRAMEWORK_MINIMAL_LEGACY_RECORD_REJECTED=PASS
FRAMEWORK_TEXTUAL_RANGE_NOT_PERMISSIVE=PASS
FRAMEWORK_MAPPING_MUTATION_SENSITIVE=PASS

CERTIFICATION_SOURCE_AUTHORITY_NARROW_PROVENANCE=PASS
CERTIFICATION_SESSION_ID_NOT_AUTHORITY=PASS
CERTIFICATION_SAMPLE_ID_NOT_AUTHORITY=PASS
CERTIFICATION_ASSESSMENT_ID_NOT_AUTHORITY=PASS
CERTIFICATION_CONTEXT_ID_NOT_AUTHORITY=PASS

SEMANTIC_NUMERIC_BOOL_REJECTED=PASS
SEMANTIC_NUMERIC_NAN_INF_REJECTED=PASS
DEADLINE_BOOL_NOT_URGENT=PASS

GOAL_ALIGNMENT_GENERIC_PRACTICE_NOT_UNIVERSAL=PASS
GOAL_ALIGNMENT_SUPPORTED_FIELDS=PASS

LEGACY_CONTRACT_CONTRADICTIONS=0

ALL_EPISTEMIC_PATHS_SHARE_INVARIANTS=PASS
ALL_HISTORICAL_BYPASSES_BLOCKED=PASS

AT_DP_026_FROZEN_SEMANTIC_CHECKPOINTS=45
AT_DP_026_REAL_WORKFLOWS=9
AT_DP_026_SOURCE_AUTHORITY_MUTATION=PASS
AT_DP_026_CONNECTED=PASS

CANON=16/15/14/15/9
MODULES=14
PARENTHOOD_UNCHANGED=PASS
```

Every marker must be backed by either an exact test or direct executable probe.

---

### Task 11: Definition-of-done review and documentation

**Files:**
- Modify only existing Phase 10.26 documentation needed to record candidate status
- Evidence under `tmp/`

**Interfaces:**
- Consumes: all verification artifacts.
- Produces: accurate pre-audit status.

- [ ] **Step 1: Review all verification logs for failures/skips/errors**

Do not infer PASS from process exit alone if output contains collection errors or unexpected skips.

- [ ] **Step 2: Review git scope**

Expected production diff should be narrowly concentrated in:

```text
cmm/domains/languages/rules.py
```

plus Languages tests/docs.

- [ ] **Step 3: Update Phase 10.26 status conservatively**

Allowed wording only:

```text
Epistemic-binding independent audit: FAIL
remaining findings remediated: 1 BLOCKER + 3 MAJOR
epistemic invariant consolidation: candidate PASS
AT-DP-026: candidate PASS
final independent closure audit: PENDING
DP-026: REQUIRES_PHASE_INSPECTION
```

Do not write `closed`, `complete`, or `DP-026 PASS`.

- [ ] **Step 4: Commit documentation/status**

Use a separate docs commit.

---

### Task 12: Build the final independent audit bundle

**Files:**
- Create: `tmp/phase-10-26-final-invariant-independent-closure-audit-bundle.tar.gz`
- Create bundle manifest and internal `SHA256SUMS`

**Interfaces:**
- Consumes: exact current candidate and all verification evidence.
- Produces: self-contained audit bundle for independent closure review.

- [ ] **Step 1: Refuse bundle creation unless all mandatory gates pass**

Check:

```text
LEGACY_CONTRACT_CONTRADICTIONS=0
ALL_EPISTEMIC_PATHS_SHARE_INVARIANTS=PASS
ALL_HISTORICAL_BYPASSES_BLOCKED=PASS
AT_DP_026_CONNECTED=PASS
all Languages GREEN
all domains GREEN
global GREEN
Ruff GREEN
compileall GREEN
canon GREEN
Paternidad unchanged
tracked worktree clean except tmp/
```

If any is not PASS, stop bundle creation and fix the root cause.

- [ ] **Step 2: Include exact relevant source/tests/docs**

Include:
- all 14 Languages production modules;
- all Languages tests;
- Phase 10.26 design/spec/roadmap/reference docs;
- prior audit reports;
- this implementation plan;
- implementation commits/diffs from `070d1a2`;
- full Phase 10.26 diff;
- all fresh logs from Task 10;
- RED ledger;
- contract consistency artifact;
- adversarial review;
- direct markers;
- candidate metadata;
- manifest.

- [ ] **Step 3: Create internal `SHA256SUMS`**

Verify every bundled file.

- [ ] **Step 4: Create archive and external SHA**

Archive:

```text
tmp/phase-10-26-final-invariant-independent-closure-audit-bundle.tar.gz
```

Print its SHA-256.

- [ ] **Step 5: Final repo state**

Required:

```text
tracked worktree clean
only tmp/ untracked
no push
no merge
```

- [ ] **Step 6: Final agent status**

Print only:

```text
PHASE10_26_FINAL_INVARIANT_CONSOLIDATION_STATUS:
READY_FOR_FINAL_INDEPENDENT_CLOSURE_AUDIT
```

plus:
- final HEAD;
- bundle path;
- SHA-256;
- file count;
- internal SHA status;
- test counts.

Do not claim Phase 10.26 closed.
