# Phase 10.26 — Final Rule-Layer Closure Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Every semantic change uses `superpowers:test-driven-development`. Every completion claim uses `superpowers:verification-before-completion`.

**Goal:** Close the final independent closure-audit findings by making all 14 frozen Languages rules semantically sensitive, fail-closed, provenance-aware, JSON-safe, deterministic, and adversarially tested before one new closure bundle.

**Architecture:** Do not change the frozen Domain Pack architecture. Harden the existing deterministic rule helpers and their existing rule wrappers in `cmm/domains/languages/rules.py`, reusing the already-correct shared evidence/provenance utilities. Add mutation/property tests proving required inputs actually affect outcomes. No new Languages production module and no new shared subsystem are expected.

**Tech Stack:** Python 3.10+, pytest, Ruff, CMM Domain Intelligence shared rule/runtime contracts.

**Spec:** `docs/superpowers/specs/2026-08-23-languages-domain-design.md`

## Global Constraints

- Repository: `/Users/chris/CMM OS`
- Branch: `feature/phase-10-domain-intelligence`
- Final audited candidate baseline: `1f987c8`
- Domain ID remains `domain:languages`
- Display name remains `Idiomas`
- Profile remains `LanguageLearningProfile`
- Canon remains exactly:
  - 16 entities
  - 15 resources
  - 14 rules
  - 15 operations
  - 9 workflows
- Languages production package remains exactly 14 modules.
- `languages.progress_checkpoint` remains canonical.
- All V1/V2/V3 remediation must remain green.
- Do not change Phase 10.27 / Paternidad.
- Do not restore `Nil`.
- Do not push.
- Do not merge.
- Do not close Phase 10.26 before the next independent audit.
- Work autonomously. Do not STOP for a Languages-local fix proven necessary by RED.
- If a genuinely shared defect is discovered, fix it only when:
  1. a shared RED proves the root cause;
  2. the fix is generic and minimal;
  3. backward compatibility is preserved where possible;
  4. shared consumers are regression-tested;
  5. the shared change is committed separately.
- Do not create workarounds, test-only semantic bypasses, caller-controlled safety thresholds, fake provenance, or synthetic authority.

## Final independent closure audit

Read:

```text
docs/superpowers/audits/2026-08-24-phase-10-26-final-independent-closure-audit.md
```

Verdict:

```text
FAIL
1 BLOCKER
2 MAJOR
```

Root class:

```text
semantic input appears in API/test
!=
semantic input actually controls result
```

Closure requires mutation/property proof, not happy-path examples.

---

# Frozen 14-rule matrix

Every rule below must receive an explicit final status in tests:

```text
1  LanguageLevelEvidenceRule
2  SkillSeparationRule
3  LanguageVarietyValidityRule
4  ProficiencyFrameworkRule
5  ErrorPatternEvidenceRule
6  CorrectionPriorityRule
7  AdaptiveDifficultyRule
8  SpacedReviewRule
9  LearningLoadRule
10 GoalAlignmentRule
11 ProgressionEvidenceRule
12 CertificationTemporalRule
13 CulturalContextEvidenceRule
14 LanguageMemoryConsentRule
```

For every rule, the final test layer must prove, where applicable:

```text
required evidence affects outcome
removing required evidence fails closed
caller cannot lower canonical evidence threshold
duplicate provenance/items do not add support
invalid bool/numeric input does not add support
NaN/Inf do not escape
input ordering does not alter evidence semantics
strict JSON serialization succeeds
caller inputs are not mutated
```

---

# Task 0 — Baseline and exact RED ledger

**Files:**
- Test: `tests/domains/test_languages_domain_rule_closure.py` (create)
- Existing focused rule test files as needed

**Produces:** one dedicated closure test module covering all 14 rules plus exact RED records.

- [ ] **Step 1: Verify baseline**

```bash
cd "/Users/chris/CMM OS"
git branch --show-current
git rev-parse --short HEAD
git status --short --branch
```

Expected:
- correct Phase 10 branch;
- HEAD is descendant of `1f987c8`;
- tracked worktree clean;
- only pre-existing `?? tmp/`.

- [ ] **Step 2: Create `test_languages_domain_rule_closure.py`**

This file is not a replacement for existing focused tests. It is the final mutation/property contract.

Start with imports of all 14 public helpers/rule types used in final proof.

- [ ] **Step 3: Write exact RED reproductions from final audit**

Required REDs:

```python
def test_level_estimate_requires_evidence():
    result = classify_proficiency_record(
        kind="ESTIMATED",
        framework="CEFR",
        level_or_score="C1",
        evidence=(),
    )
    assert result["level_or_score"] == "unassessed"
    assert result["confidence"] == 0.0
```

```python
def test_framework_mapping_requires_provenance():
    result = evaluate_framework_mapping(
        source_framework="IELTS",
        source_value="6.5",
        target_framework="CEFR",
        mapping_evidence=({"target_range": "B2"},),
    )
    assert result["calibrated"] is False
```

```python
@pytest.mark.parametrize("threshold", [0, 1, True, -1])
def test_error_pattern_canonical_minimum_cannot_be_lowered(threshold):
    result = evaluate_error_pattern(
        observations=(),
        minimum_independent_occurrences=threshold,
    )
    assert result["eligible"] is False
    assert result["pattern_state"] == "insufficient_evidence"
```

```python
def test_adaptive_difficulty_ignores_noncomparable_high_scores():
    result = adapt_difficulty(
        current_difficulty=3,
        performance=(
            {"provenance_id":"p1","comparison_key":"same","score":0.95,"comparable":False},
            {"provenance_id":"p2","comparison_key":"same","score":0.95,"comparable":False},
        ),
    )
    assert result["action"] == "insufficient_evidence"
```

```python
def test_goal_alignment_rejects_unrelated_activity():
    result = align_activity_to_goals(
        activity={"type":"unrelated_accounting"},
        goals=(
            {"id":"cert","kind":"certification","target":"C1"},
            {"id":"conv","kind":"conversation","target":"conversation fluency"},
        ),
    )
    assert result["activity_fit"] != "aligned"
    assert result["aligned_goals"] == []
```

```python
@pytest.mark.parametrize("available_time", [float("inf"), float("-inf"), True, -10])
def test_learning_load_invalid_time_fails_closed(available_time):
    result = evaluate_learning_load(available_time=available_time)
    assert result["recommended_duration_minutes"] >= 0
```

```python
def test_spaced_review_deduplicates_logical_item():
    result = plan_spaced_review(items=(
        {"id":"v1","due":True,"mastery":0.2},
        {"id":"v1","due":True,"mastery":0.2},
    ))
    assert len(result["review_queue"]) == 1
    assert result["backlog_count"] == 1
```

- [ ] **Step 4: Verify every RED fails for the audited reason**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_languages_domain_rule_closure.py
```

Capture RED output under `tmp/phase10-26-final-rule-red/`.

Do not continue if a RED unexpectedly passes.

---

# Task 1 — Harden `LanguageLevelEvidenceRule`

**Files:**
- Modify: `cmm/domains/languages/rules.py`
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Regression: `tests/domains/test_languages_domain_proficiency.py` or existing proficiency-focused test module

## Frozen semantics

```text
certificate -> CERTIFIED
evidence-based inference -> ESTIMATED
single task/session -> OBSERVED_PERFORMANCE
no evidence -> insufficient/unassessed
```

## Required behavior

### No evidence

For caller-requested:

```text
CERTIFIED C1
ESTIMATED C1
OBSERVED_PERFORMANCE C1
```

with no usable evidence:

```text
is_certified=False
level_or_score="unassessed"
confidence=0.0
```

The kind may normalize to the safest existing canonical kind, but a level must not remain grounded.

### OBSERVED_PERFORMANCE

A concrete observed level/score requires at least one grounded task/session evidence record.

Canonical provenance comes from existing `_canonical_provenance()`.

### ESTIMATED

A stable estimate must not be produced from one isolated sample.

Require at least:
- two independent provenance units;
- relevant evidence records;
- no caller-ID-only independence.

If evidence is insufficient:
- do not preserve the caller-supplied estimated level as grounded;
- confidence must not remain the normal estimated default.

### CERTIFIED

Preserve existing strict official credential evidence behavior.

- [ ] **Step 1: Add RED matrix**

Cases:
- no evidence;
- one sample requested as ESTIMATED;
- two records same provenance;
- two independent grounded evidence units;
- certificate valid/invalid.

- [ ] **Step 2: Implement minimal fail-closed classification**

Reuse:
- `_deduplicate_evidence`;
- `_canonical_provenance`;
- `_is_certifying_evidence`.

Do not add a second evidence system.

- [ ] **Step 3: Mutation proof**

Take a valid estimated case:
- remove second provenance;
- duplicate first provenance under different caller IDs;
- remove provenance;
- change evidence to malformed mapping.

Each mutation must reduce to unassessed / insufficient evidence.

- [ ] **Step 4: Commit**

```text
fix(languages): require evidence for proficiency classification
```

---

# Task 2 — Harden `SkillSeparationRule` pronunciation evidence

**Files:**
- Modify: `cmm/domains/languages/rules.py` only if RED proves current boundary weak
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Regression: existing skill separation tests

The final audit did not assign a separate finding here, but this task is mandatory preventive closure because this is one of the 14 frozen rules.

## Required pronunciation boundary

These must **not** independently establish assessed pronunciation:

```text
audio_transcript
text transcript
user_message
self_report
generic sample with skill="pronunciation"
record with pronunciation_assessed=False
record without usable pronunciation/acoustic assessment provenance
```

These may count when grounded and explicit:

```text
acoustic_assessment
pronunciation_assessment
audio_sample with explicit pronunciation assessment result
```

Use existing provenance fields.

Do not infer pronunciation from transcript text.

- [ ] Add positive/negative mutation matrix.
- [ ] Keep other skill partition behavior unchanged.
- [ ] Commit with Task 3 if only tests are needed; otherwise:

```text
fix(languages): harden pronunciation evidence separation
```

---

# Task 3 — Confirm `LanguageVarietyValidityRule` by mutation

**Files:**
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Production only if RED exposes a real bug

Mandatory properties:

```text
preferred variety != only correct variety
known valid British/American/etc alternative != error
unknown caller variety string != silently valid
explicit incorrect form remains incorrect
missing preferred/observed -> uncertain
input order irrelevant
```

No architecture change expected.

---

# Task 4 — Require provenance for `ProficiencyFrameworkRule`

**Files:**
- Modify: `cmm/domains/languages/rules.py`
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Regression: `tests/domains/test_languages_domain_variety_framework.py`

## Required mapping evidence

A cross-framework record must include:

```text
target_range
canonical provenance
```

Canonical provenance:
- `provenance_id`;
- `source_id`;
- `official_source_id`;
or another already-established canonical provenance field.

A display string such as:

```text
"Cambridge English Concordance"
```

is not itself provenance.

## Output

Valid mapping:

```text
mapping_status=grounded_approximate_mapping
approximate=True
is_exact=False
calibrated=True
evidence/provenance preserved
```

Ungrounded mapping:

```text
mapping_status=identity_forbidden or insufficient_evidence
calibrated=False
target_estimate_range=None
```

Same-framework values may remain exact within the same framework.

- [ ] RED arbitrary dict.
- [ ] RED source-looking string without provenance.
- [ ] GREEN grounded source ID.
- [ ] Duplicate provenance does not add authority.
- [ ] Permutation invariance.
- [ ] Commit:

```text
fix(languages): require provenance for framework mappings
```

---

# Task 5 — Make `ErrorPatternEvidenceRule` canonical minimum non-bypassable

**Files:**
- Modify: `cmm/domains/languages/rules.py`
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Regression: `tests/domains/test_languages_domain_error_correction.py`

## Threshold normalization

Canonical minimum is **2**.

Caller may request a stricter threshold:

```text
3
4
...
```

Caller may never request:

```text
0
1
negative
True
False
NaN
Inf
string
mapping
```

to weaken recurrence evidence.

Normalize invalid/lower values to `2`.

## Required properties

```text
0 observations -> insufficient
1 independent observation -> insufficient
2 independent same-type comparable observations -> candidate
>2 -> evidenced according to existing state logic
same provenance duplicated -> one occurrence
different error types -> no single pattern
different comparison keys -> no single comparable pattern
```

- [ ] RED threshold bypass.
- [ ] GREEN canonical normalization.
- [ ] Mutation proof for bool.
- [ ] Commit:

```text
fix(languages): enforce canonical error recurrence minimum
```

---

# Task 6 — Harden `CorrectionPriorityRule` by semantic mutation

**Files:**
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Production only if RED proves a defect

Properties:

```text
blocking outranks recurrent
recurrent outranks goal-critical
goal-critical outranks certification-critical
assess mode defers feedback
practice mode can defer minor style
changing goal relevance changes priority
changing certification relevance changes priority
```

Critically:
- mutate the field under test;
- prove ordering changes.

Do not merely include a field in fixture data.

---

# Task 7 — Rebuild `AdaptiveDifficultyRule` on comparable independent evidence

**Files:**
- Modify: `cmm/domains/languages/rules.py`
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Regression: `tests/domains/test_languages_domain_error_correction.py`

## Current-difficulty normalization

Valid:

```text
finite
non-boolean
>=1
```

Invalid:

```text
NaN
Inf
-Inf
True
False
negative
mapping
string
```

must not crash.

If current difficulty is invalid:
- normalize safely;
- return `insufficient_evidence` or equivalent conservative action;
- never increase challenge because of malformed state.

## Valid performance evidence

Every performance unit counted toward repeated adaptation requires:

```text
Mapping
score finite
score not bool
0.0 <= score <= 1.0
comparable is True
canonical provenance exists
comparison_key exists
```

For repeated/stable adaptation:
- provenance units must be independent;
- all counted records must share one comparison key;
- duplicate provenance counts once.

## Behavior

```text
no valid comparable evidence
-> insufficient_evidence

one low valid sample
-> temporary scaffold allowed
-> stable proficiency unchanged

one high sample
-> no stable increase

two+ independent comparable high samples
-> increase

two+ independent comparable low samples
-> scaffold_reduce

adequate comparable evidence
-> maintain_and_advance
```

## Required attacks

```text
comparable=False
same provenance twice
different comparison keys
score=True
score=Inf
score=-1
score=2
current difficulty=Inf
current difficulty=True
```

None may produce unsupported increase.

- [ ] Commit:

```text
fix(languages): require comparable evidence for difficulty adaptation
```

---

# Task 8 — Rebuild `SpacedReviewRule` on logical items and bounded evidence

**Files:**
- Modify: `cmm/domains/languages/rules.py`
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Regression: `tests/domains/test_languages_domain_adaptation_progression.py`

## Logical item identity

Prefer:
1. `id`;
2. stable `item_id`;
3. stable normalized term/key;
4. canonical semantic representation only as fallback.

Exact duplicate logical item must count once.

Conflicting duplicates must not add review support.

Use permutation-invariant conflict resolution.

A conservative conflict merge is acceptable:
- due true only when grounded consistently, or explicitly mark conflict;
- malformed conflict cannot inflate;
- active-pattern support cannot be duplicated;
- one logical item remains one queue item.

## Numeric bounds

`mastery`:
- finite;
- non-boolean;
- bounded `[0,1]`.

Malformed:
- NaN;
- Inf;
- negative;
- >1;
- bool;
- string;
must not increase priority.

Use a neutral/unknown value rather than extreme priority.

## Frozen priority factors

The original implementation plan explicitly says priority responds to:

```text
mastery
recall
importance
goal relevance
active patterns
```

Final mutation tests must show each factor affects ranking.

Suggested normalized fields:

```text
mastery        [0,1]
recall         [0,1]
importance     [0,1]
goal_relevant  bool
active_pattern bool
due            bool
```

Do not make any single malformed numeric dominate queue order.

## Invariants

```text
backlog_count <= logical item count
review_queue contains unique logical items
due_items contains unique logical items
same logical input set under permutation -> same result
```

- [ ] Commit:

```text
fix(languages): harden spaced review evidence
```

---

# Task 9 — Harden `LearningLoadRule` real constraints

**Files:**
- Modify: `cmm/domains/languages/rules.py`
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Regression: `tests/domains/test_languages_domain_adaptation_progression.py`

## `available_time`

Valid:
- finite;
- non-boolean;
- `>=0`.

Invalid:
- NaN;
- ±Inf;
- bool;
- negative;
- malformed.

Invalid/missing must produce a conservative, explicit insufficient-constraint state.

Never emit negative duration.

Never crash.

## Energy

Canonicalize:

```text
low
moderate
high
```

Unknown -> conservative `moderate` or explicit unknown; no increased burden.

## Hard-constraint order

```text
available time / energy / recent load
>
preferences / priorities
```

A deadline may affect **what** is prioritized but not exceed real time/energy constraints.

`recent_load` and `deadlines` are explicit public inputs: add mutation tests proving that when grounded values are present they are either:
- deliberately consumed in recommendation semantics; or
- explicitly represented as unsupported/unused rather than silently ignored.

Prefer consuming them minimally:
- high recent load lowers or maintains burden;
- urgent deadline influences activity priority;
- neither may exceed available time.

## Invariants

```text
0 <= recommended_duration_minutes <= valid available_time
calendar_modified=False
```

when `available_time` is valid.

- [ ] Commit:

```text
fix(languages): harden learning load constraints
```

---

# Task 10 — Make `GoalAlignmentRule` evaluate the actual activity

**Files:**
- Modify: `cmm/domains/languages/rules.py`
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Regression: `tests/domains/test_languages_domain_adaptation_progression.py`

## Normalize activity semantics

Consume actual fields when present:

```text
type
kind
skill
skills
goal_id
goal_ids
purpose
```

Explicit goal references have strongest relevance.

Otherwise use deterministic semantic tags.

## Frozen examples

At minimum support relevance categories:

```text
certification / C1 / exam
-> exam_task, formal_writing, writing, reading, listening, speaking

travel
-> interaction, speaking, listening, functional_vocabulary, vocabulary, roleplay

conversation / fluency
-> conversation, speaking, interaction, listening, roleplay

writing
-> writing, grammar, register, essay
```

Do not infer universal relevance.

## Outputs

No active goals:

```text
activity_fit=no_active_goals or insufficient_evidence
aligned_goals=[]
```

Unrelated activity:

```text
activity_fit=not_aligned
aligned_goals=[]
```

Partial:

```text
activity_fit=partially_aligned
```

Activity aligned with one of several concurrent goals:

```text
aligned_goals=[only supported goals]
```

Do not claim certification goal alignment merely because certification is active.

## Mutation tests

For the same goals:

```text
roleplay -> conversation/travel alignment
unrelated_accounting -> none
formal_exam_essay -> certification/writing
```

Changing only `activity` must change result.

- [ ] Commit:

```text
fix(languages): evaluate activity goal alignment
```

---

# Task 11 — Reconfirm `ProgressionEvidenceRule`

**Files:**
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Production only if RED exposes regression

Mandatory mutation matrix:

```text
no baseline -> insufficient
one new provenance -> short-term only
two independent comparable current provenance units -> stable improvement may be supported
same current provenance duplicated -> not stable
different comparison keys -> insufficient
comparable=False -> insufficient
bool/NaN/Inf scores -> ignored/fail closed
unrelated skill -> excluded
```

This rule previously passed; preserve it.

---

# Task 12 — Harden source authority in `CertificationTemporalRule`

**Files:**
- Modify: `cmm/domains/languages/rules.py` if RED confirms
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Regression: `tests/domains/test_languages_domain_adaptation_progression.py`

The frozen source-authority section says a user statement alone does not ground:
- official certification requirement;
- current examination date;
- framework equivalence.

Current temporal ordering is already correct.

Final preventive proof must ensure **authority identity is grounded**, not caller-labeled.

A source claiming:

```python
{"source_type":"official","date_valid":True}
```

with no source/provenance identity must not become fully authoritative for a decision-critical current fact.

Require canonical source identity/provenance for top official/authoritative-secondary ranks.

Examples of acceptable identity:
- `source_id`;
- `official_source_id`;
- `provenance_id`;
- another existing canonical source reference.

Preserve:
```text
current official > current authoritative secondary > stale official > memory > guide
```

Do not reopen the V2 temporal precedence fix.

- [ ] Commit only if production changes:

```text
fix(languages): ground certification source authority
```

---

# Task 13 — Reconfirm `CulturalContextEvidenceRule`

**Files:**
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Production if RED proves current result overclaims

Required:
- universal stereotypes rejected;
- weak/no evidence cannot become an unqualified cultural fact;
- qualified tendency remains explicitly qualified;
- evidence absence remains visible if a positive tendency is returned.

If `qualified_tendency=True` currently implies evidence support even when evidence is empty, add an explicit evidence-status field or make the positive state fail closed.

Do not create cultural stereotypes.

---

# Task 14 — Reconfirm `LanguageMemoryConsentRule`

**Files:**
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Production only if RED proves defect

Properties:

```text
session observation != durable persistence
consent=True alone != valid permission chain
permission chain alone != consent
"true" != True
1 != True
candidate/proposal != applied persistence
persistence_applied always False inside Languages rule
```

The connected real PermissionGate/memory path must remain green.

---

# Task 15 — Cross-rule property suite

**Files:**
- Test: `tests/domains/test_languages_domain_rule_closure.py`
- Test: `tests/domains/test_languages_domain_adversarial.py`

Create generic property helpers.

## Strict JSON

For every public rule helper result:

```python
json.dumps(result, allow_nan=False)
```

must pass for:
- valid input;
- minimal input;
- malformed numeric input where applicable.

## Input immutability

Deep-copy all mapping/list inputs before call.

Assert unchanged.

## Determinism

Ignoring intentionally generated IDs (rule helpers should have none), identical normalized input returns equal semantic output.

## Permutation invariance

For evidence/item sets where ordering is not semantic:
- reverse;
- rotate;
- shuffle deterministically.

Result semantic support/ranking must remain equivalent.

For ordered pedagogical lists where order is itself meaningful, document and exclude.

## Required semantic sensitivity

Create mutation pairs:

```text
required field valid -> supported outcome
same field removed -> less certainty/support

comparable=True -> may count
comparable=False -> cannot count

provenance distinct -> may support recurrence
provenance duplicate -> cannot add recurrence

activity relevant -> aligns
activity irrelevant -> does not align

source grounded -> authority
source label only -> no authority
```

This is the gate that prevents another “field present but ignored” audit failure.

Commit:

```text
test(languages): enforce canonical rule semantics
```

---

# Task 16 — Re-run all previous audit reproductions

**Files:**
- Tests only

Create a table in test comments / scratch review covering:

## V1

```text
generic evidence -> CERTIFIED impossible
duplicate evidence inflation impossible
progression requires baseline/comparability
current/stale temporal precedence
real PermissionGate lifecycle
workflow invariant gates
connected acceptance
```

## V2

```text
calendar external boundary
trace typed provenance
progress no cross-skill fabrication
empty assessment/writing/speaking/certification fail closed
malformed exercise numeric fail closed
```

## V3

```text
real rule runtime ID
real permission decision ID
selected profile mode
empty exercise unknown
vocabulary mastery grounded
```

## Final closure audit

```text
no-evidence proficiency classification
framework mapping provenance
error threshold canonical minimum
adaptive comparable/provenance/numeric
spaced-review logical items/bounds
learning-load valid constraints
goal activity relevance
```

Every historical finding must have at least one living regression.

---

# Task 17 — Adversarial code review before completion

Do not use a generic “looks good” review.

Attempt mutations that should be caught:

```text
return ESTIMATED C1 with evidence=()
accept {"target_range":"B2"} as mapping evidence
set recurrence threshold to 1
remove comparable check in adaptive difficulty
remove provenance dedup in adaptive difficulty
accept True as score
accept Inf as score/time
duplicate one review item under same ID
set mastery=-100
remove recall from spaced priority
remove importance from spaced priority
ignore activity in GoalAlignment
label unprovenanced source official/current
```

For each mutation, identify the exact test that fails.

Record:
```text
Critical
Important
Minor
```

Expected final:
```text
0 / 0 / 0
```

If a mutation survives, add RED/fix before verification.

---

# Task 18 — Fresh verification

No claim before fresh evidence.

## Languages

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_languages_domain_*.py
```

## Dedicated rule closure

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_languages_domain_rule_closure.py
```

## Shared rule runtime

Run all rule-contract / rule-selection / rule-execution tests.

## Shared trace / permission / workflow / composer / resolver

Re-run all consumers touched by prior remediation.

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

Run normal and py310 over every modified file.

## compileall

Isolated `PYTHONPYCACHEPREFIX`.

## Fresh import

No registry side effects.

## Canon

```text
16/15/14/15/9
14 modules
languages.progress_checkpoint
```

## Paternidad

No Phase 10.27 change.

## Worktree

Tracked clean; only pre-existing `tmp/`.

---

# Task 19 — Required final direct markers

Print only after direct probes actually pass:

```text
LANGUAGE_LEVEL_NO_EVIDENCE_FAIL_CLOSED=PASS
LANGUAGE_LEVEL_SINGLE_SAMPLE_NOT_ESTIMATED=PASS

PRONUNCIATION_TRANSCRIPT_NOT_EVIDENCE=PASS
PRONUNCIATION_GENERIC_USER_MESSAGE_NOT_ASSESSED=PASS

VARIETY_VALID_ALTERNATIVE=PASS
VARIETY_UNKNOWN_NOT_TRUSTED=PASS

FRAMEWORK_MAPPING_PROVENANCE_REQUIRED=PASS
FRAMEWORK_MAPPING_APPROXIMATE=PASS

ERROR_PATTERN_CANONICAL_MINIMUM_2=PASS
ERROR_PATTERN_THRESHOLD_BYPASS_BLOCKED=PASS

CORRECTION_PRIORITY_MUTATION_SENSITIVE=PASS

ADAPTIVE_COMPARABILITY_REQUIRED=PASS
ADAPTIVE_INDEPENDENT_PROVENANCE_REQUIRED=PASS
ADAPTIVE_COMPARISON_KEY_REQUIRED=PASS
ADAPTIVE_INVALID_NUMERIC_FAIL_CLOSED=PASS

SPACED_REVIEW_LOGICAL_DEDUP=PASS
SPACED_REVIEW_MASTERY_BOUNDED=PASS
SPACED_REVIEW_RECALL_SENSITIVE=PASS
SPACED_REVIEW_IMPORTANCE_SENSITIVE=PASS

LEARNING_LOAD_FINITE_NONNEGATIVE=PASS
LEARNING_LOAD_HARD_CONSTRAINTS=PASS
LEARNING_LOAD_NO_CALENDAR_MUTATION=PASS

GOAL_ALIGNMENT_ACTIVITY_SENSITIVE=PASS
GOAL_ALIGNMENT_UNRELATED_REJECTED=PASS
GOAL_ALIGNMENT_NO_ACTIVE_GOALS=PASS

PROGRESSION_BASELINE_COMPARABILITY=PASS

CERTIFICATION_TEMPORAL_PRECEDENCE=PASS
CERTIFICATION_SOURCE_PROVENANCE=PASS

CULTURAL_CONTEXT_WEAK_EVIDENCE_QUALIFIED=PASS

MEMORY_CONSENT_CHAIN=PASS
MEMORY_PERSISTENCE_NOT_APPLIED=PASS

ALL_14_RULES_STRICT_JSON=PASS
ALL_14_RULES_INPUT_IMMUTABILITY=PASS
ALL_14_RULES_MUTATION_SENSITIVITY=PASS
ALL_14_RULES_CLOSURE_MATRIX=PASS

AT_DP_026_FROZEN_SEMANTIC_CHECKPOINTS=45
AT_DP_026_REAL_WORKFLOWS=9
AT_DP_026_CONNECTED=PASS
```

---

# Task 20 — Documentation

After all tests and review are green, update current status only to:

```text
Final independent closure audit: FAIL
Final findings remediated: 1 BLOCKER + 2 MAJOR
14-rule closure hardening: candidate PASS
AT-DP-026: candidate PASS
new independent closure audit: PENDING
DP-026: REQUIRES_PHASE_INSPECTION
```

Do **not** mark Phase 10.26 closed.

Suggested commit:

```text
docs(domains): record languages rule-layer hardening
```

---

# Task 21 — Build new final independent bundle

Only after:
- all tasks green;
- code review 0/0/0;
- docs committed;
- tracked worktree clean.

Bundle:

```text
phase-10-26-rule-hardened-independent-closure-audit-bundle.tar.gz
```

Must include:

```text
frozen spec
all four audit reports
all remediation plans
current docs
14 Languages modules
all Languages tests
new rule-closure tests
shared rule runtime/contracts/tests
trace/workflow/permission/composer/resolver relevant source/tests
fresh test evidence
all direct markers
adversarial review
RED records
git diff 1f987c8..HEAD
git diff 93c2679..HEAD
commit list
manifest
SHA256SUMS
```

Do not declare closure.

Final agent status only:

```text
PHASE10_26_RULE_HARDENING_STATUS:
READY_FOR_NEW_INDEPENDENT_CLOSURE_AUDIT
```

---

# Expected commits

Keep small, reviewable commits:

```text
fix(languages): require evidence for proficiency classification
fix(languages): require provenance for framework mappings
fix(languages): enforce canonical error recurrence minimum
fix(languages): require comparable evidence for difficulty adaptation
fix(languages): harden spaced review evidence
fix(languages): harden learning load constraints
fix(languages): evaluate activity goal alignment
fix(languages): harden remaining rule evidence boundaries
test(languages): enforce canonical rule semantics
docs(domains): record languages rule-layer hardening
```

Combine adjacent changes only when inseparable. Do not mix unrelated shared changes into Languages commits.

---

# Definition of Done

```text
[ ] final audit B-001 fully closed
[ ] final audit M-001 fully closed
[ ] final audit M-002 fully closed

[ ] all 14 rule contracts have mutation tests
[ ] no caller can lower canonical error-pattern minimum
[ ] no required semantic field can be ignored while positive tests still pass
[ ] no malformed bool/NaN/Inf/negative numeric can increase support
[ ] no duplicate evidence/item increases support
[ ] no unprovenanced framework mapping is calibrated
[ ] no ungrounded proficiency estimate is accepted
[ ] no unrelated activity is aligned
[ ] no impossible learning duration
[ ] no duplicated logical spaced-review backlog
[ ] recall and importance demonstrably affect spaced-review priority

[ ] V1 regressions green
[ ] V2 regressions green
[ ] V3 regressions green
[ ] connected AT-DP-026 still 45 exact semantic checkpoints
[ ] nine real workflows
[ ] trace provenance still real
[ ] permission decision identity still real

[ ] Languages tests green
[ ] all domains green
[ ] global suite green
[ ] Ruff green
[ ] Ruff py310 green
[ ] compileall green
[ ] fresh import green
[ ] canon 16/15/14/15/9
[ ] 14 production modules
[ ] Paternidad unchanged
[ ] tracked worktree clean
[ ] no push
[ ] no merge

[ ] new independent closure audit remains pending
```
