# Phase 10.26 — Final Independent Closure Audit

## Audit identity

- **Project:** CMM OS
- **Phase:** 10.26 — Languages Domain
- **Audit type:** final independent closure audit
- **Candidate branch:** `feature/phase-10-domain-intelligence`
- **Candidate HEAD:** `1f987c8da798b329adcd6840386e8365d8a82231`
- **Bundle:** `phase-10-26-final-independent-closure-audit-bundle.tar.gz`
- **Expected / observed SHA-256:** `067f1c4087547e9dfbe8d22dca3806ac52266dd830a71e102d706589db600097`
- **Internal `SHA256SUMS`:** PASS
- **Bundle file count:** 1788
- **Repository modified by this audit:** NO
- **Push:** NO
- **Merge:** NO

# Final verdict

```text
PHASE10_26_FINAL_INDEPENDENT_CLOSURE_AUDIT=FAIL
BLOCKERS=1
MAJORS=2
MINORS=0
CLOSURE=NO
```

The final V3 remediation is genuine and closes the previously reported V3 findings. However, an independent source-level audit of the **14 frozen canonical Languages rules** found additional contract failures not exercised by the 15-operation semantic sweep.

The closure bundle therefore cannot support `DP-026 = PASS` yet.

---

# Evidence reviewed

The audit reviewed:

- frozen Phase 10.26 design;
- original implementation plan;
- V1 independent audit + remediation;
- V2 independent audit + remediation;
- V3 independent audit + definitive remediation;
- all 14 Languages production modules;
- all 19 Languages test modules;
- shared rule / trace / workflow / composition / resolver / permission contracts included in the bundle;
- git history and diffs through `1f987c8`;
- final adversarial review artifacts;
- captured fresh verification evidence;
- direct isolated execution probes against the exact bundled `rules.py`.

The final bundle is integrity-valid.

Captured candidate verification includes:

```text
Languages focused             210 passed
all domains                  5876 passed
global suite                11406 passed
Ruff                           PASS
Ruff py310                     PASS
compileall                     PASS
fresh import                   PASS
git diff --check               PASS
canon                  16/15/14/15/9
production modules               14
tracked worktree               CLEAN
Paternidad / Phase 10.27   unchanged
```

The tarball is an audit package rather than a complete runnable repository snapshot: some full-repo dependencies such as `kernel` / `cmm.validation` are not bundled. Therefore the independent audit did not treat a standalone pytest run inside the extracted tar as authoritative. The captured test evidence was reviewed, while the closure findings below were independently reproduced directly from the exact bundled source.

---

# What is now genuinely closed

The audit confirms the V3 remediation fixed the V3 findings rather than merely changing tests.

## V3-B-001 — runtime trace provenance

**RESOLVED**

The connected scenario now uses:

```text
DomainRuleExecutionPlan.id          -> RULE_PLAN
DomainRuleExecutionResult.id        -> RULE_RESULT
PermissionGateResult.decision_id    -> PERMISSION_DECISION
WorkflowRun.run_id                  -> WORKFLOW_RUN
real evidence IDs                   -> EVIDENCE
real memory proposal ID             -> MEMORY_PROPOSAL
real memory binding ID              -> MEMORY_BINDING
real presentation result ID         -> PRESENTATION_RESULT
```

The selected profile mode is an actual runtime value (`practice`), is used by the lesson path, and is preserved in trace metadata.

The acceptance builds independent `expected_id_to_kind` and `expected_id_to_owner` maps before trace assembly.

No `WorkflowEvent.event_id` is traced as a workflow result.

## V3-M-001 — missing exercise outcome

**RESOLVED**

Missing exercise outcome now remains unassessed rather than becoming `True / 1.0 / Great job!`.

## V3-M-002 — hard-coded vocabulary mastery

**RESOLVED**

Vocabulary mastery is now derived from actual candidate item state. The constant `mastered=5` defect is gone, `review_results` participates in candidate state derivation, and persistence remains proposal-only.

## Previously remediated V1/V2 areas

No new closure-breaking regression was found in:

```text
CERTIFIED evidence authority
level-update provenance/comparability
progression baseline/comparability
error recurrence provenance under normal canonical threshold
certification current/stale precedence
workflow invariant gates
real resolver/composer
all 9 Languages workflows
accumulated run.outputs
calendar external-action boundary
PermissionGate + ApprovalService lifecycle
memory proposal/binding path
minimal cross-domain projection
shared trace kinds/carriers
Paternidad non-regression
```

---

# FINAL-B-001 — BLOCKER
# The frozen canonical rule layer is still semantically incomplete

Five of the fourteen frozen rule contracts can be made to assert unsupported semantics or bypass their defining evidence boundary.

This is a closure blocker because the Phase 10.26 frozen canon explicitly includes all fourteen rules. Passing the connected happy path is not sufficient when canonical rules themselves do not implement their stated behavior.

---

## B-001-A — `LanguageLevelEvidenceRule` accepts an estimate with zero evidence

Frozen requirement:

```text
certificate              -> CERTIFIED
evidence-based inference -> ESTIMATED
single task/session       -> OBSERVED_PERFORMANCE
```

The result is explicitly allowed to say:

```text
insufficient evidence
```

Exact bundled helper:

```python
classify_proficiency_record(
    kind="ESTIMATED",
    framework="CEFR",
    level_or_score="C1",
    evidence=(),
)
```

Independent result:

```text
kind=ESTIMATED
level_or_score=C1
evidence=[]
confidence=0.75
```

Likewise, caller-supplied `OBSERVED_PERFORMANCE C1` with no evidence is retained with positive confidence.

Therefore:

```text
caller level label
!=
evidence-based inference
```

but the helper currently treats them as equivalent.

### Required remediation

At minimum:

```text
no usable evidence
-> unassessed / insufficient evidence
-> confidence 0
-> no caller-supplied level accepted as grounded

ESTIMATED
-> requires grounded inference evidence beyond a single isolated task

OBSERVED_PERFORMANCE with a concrete level
-> requires actual task/session evidence
```

---

## B-001-B — `ProficiencyFrameworkRule` calls arbitrary mapping data “grounded”

Frozen requirement:

```text
Mappings may be used only when their provenance
and approximate nature are preserved.

mapping != identity
```

Original implementation plan additionally requires:

```text
Mapping requires explicit evidence/provenance.
```

Exact probe:

```python
evaluate_framework_mapping(
    source_framework="IELTS",
    source_value="6.5",
    target_framework="CEFR",
    mapping_evidence=(
        {"target_range": "B2"},
    ),
)
```

Actual:

```text
mapping_status=grounded_approximate_mapping
target_estimate_range=B2
calibrated=True
```

There is no source ID, provenance ID, official-source ID, authority kind, or other grounding.

The implementation only checks whether the deduplicated evidence list is non-empty.

### Why tests missed it

The existing “known approximate” test uses:

```python
{"source": "Cambridge English Concordance", "target_range": "7.0-8.0"}
```

but never proves that the `source` string itself has authoritative provenance. Any arbitrary mapping object would pass.

### Required remediation

A cross-framework mapping must require explicit canonical provenance and preserve it in output.

An arbitrary non-empty mapping must remain:

```text
uncalibrated / insufficient_evidence
```

not `grounded_approximate_mapping`.

---

## B-001-C — `ErrorPatternEvidenceRule` allows the caller to defeat the “one error != pattern” invariant

Frozen requirement:

```text
A single observation cannot establish a recurrent pattern.
```

The default threshold is `2`, and normal tests are good. But the public rule material may override:

```python
minimum_independent_occurrences
```

without validation.

Exact probes:

```python
evaluate_error_pattern(
    observations=(),
    minimum_independent_occurrences=0,
)
```

Actual:

```text
pattern_state=candidate
eligible=True
independent_occurrences=0
```

And with one genuine observation:

```python
minimum_independent_occurrences=1
```

Actual:

```text
pattern_state=candidate
eligible=True
independent_occurrences=1
```

`True` also behaves as threshold `1`.

This directly bypasses the frozen canonical invariant.

### Required remediation

The semantic minimum must never be caller-reducible below `2`.

Malformed/bool/non-positive threshold values must normalize fail-closed to the canonical minimum.

---

## B-001-D — `AdaptiveDifficultyRule` does not actually enforce comparable, independent performance

Original implementation plan requires:

```text
repeated too-easy comparable performance -> increase
one bad session -> stable proficiency unchanged
malformed performance -> insufficient evidence
```

The helper docstring itself says:

```text
accumulated comparable performance
```

But the actual filter only checks:

```python
isinstance(score, (int, float))
and not math.isnan(score)
```

It never requires:

```text
comparable=True
canonical provenance
independent provenance
shared comparison key
```

### Independent reproductions

Two explicitly non-comparable records:

```python
[
    {"score": 0.95, "comparable": False, "provenance_id": "p1"},
    {"score": 0.95, "comparable": False, "provenance_id": "p2"},
]
```

Actual:

```text
action=increase
```

Same provenance duplicated twice:

```text
p1
p1
```

Actual:

```text
action=increase
```

Boolean scores:

```text
True
True
```

Actual:

```text
action=increase
```

Infinite score:

```text
+Inf
0.90
```

Actual:

```text
action=increase
```

Infinite current difficulty:

```python
current_difficulty=float("inf")
```

Actual:

```text
OverflowError: cannot convert float infinity to integer
```

The helper therefore fails both the evidence-comparability contract and the public fail-closed numeric contract.

### Why tests missed it

The positive tests include `comparable=True`, but there is no negative mutation proving `comparable=False` changes the decision. The implementation can ignore the field while all current tests still pass.

---

## B-001-E — `GoalAlignmentRule` never evaluates the activity

Frozen purpose:

```text
Ensure activities serve one or more active goals.
```

Examples map goal types to relevant activity classes:

```text
C1 certification
-> formal writing + exam tasks

travel
-> interaction + functional vocabulary

conversation fluency
-> speaking + interaction + listening
```

Current helper receives:

```python
activity
goals
```

but never reads `activity`.

Exact probe:

```python
align_activity_to_goals(
    activity={"type": "unrelated_accounting"},
    goals=(
        {"id": "c1", "type": "certification"},
        {"id": "conv", "type": "conversation_fluency"},
    ),
)
```

Actual:

```text
activity_fit=aligned
aligned_goals=["c1", "conv"]
```

Even:

```python
goals=()
```

returns:

```text
activity_fit=aligned
```

The rule therefore proves coexistence of goal IDs, but not alignment.

### Why tests missed it

The current test only asserts that two goal IDs coexist. It never mutates the activity into an unrelated activity and expects the alignment result to change.

---

# FINAL-M-001 — MAJOR
# `LearningLoadRule` does not fail closed on invalid real-world constraints

Frozen purpose:

```text
Adapt learning burden to real constraints.
```

Inputs include:

```text
available time
energy
priority
other goals
deadline
recent workload
review backlog
difficulty
```

Current numeric normalization:

```python
int(available_time)
```

for any `int/float` except NaN.

Independent probes:

```python
evaluate_learning_load(available_time=float("inf"))
```

Actual:

```text
OverflowError
```

```python
evaluate_learning_load(available_time=True)
```

Actual:

```text
recommended_duration_minutes=1
```

```python
evaluate_learning_load(available_time=-10)
```

Actual:

```text
recommended_duration_minutes=-10
```

A negative learning duration is semantically impossible.

The function also accepts `deadlines` and `recent_load` but does not currently use them; this is a secondary coverage gap for explicit inputs, although the closure finding is grounded primarily in the invalid real-constraint behavior above.

### Required remediation

Use one finite, non-boolean, non-negative time boundary.

Invalid/missing constraints must produce a conservative/insufficient-constraint result rather than a crash or impossible duration.

---

# FINAL-M-002 — MAJOR
# `SpacedReviewRule` allows duplicate logical items and malformed mastery to distort review state

Frozen purpose:

```text
Prioritize temporally distributed review.
```

Original implementation plan requires review priority to respond to:

```text
mastery
recall
importance
goal relevance
active patterns
```

Current implementation:

- does not deduplicate logical item identity;
- treats duplicated IDs as separate review items;
- accepts negative mastery;
- accepts bool mastery as numeric;
- does not actually consume explicit recall/importance inputs.

## Duplicate reproduction

Input:

```python
items=(
    {"id": "v1", "due": True, "mastery": 0.2},
    {"id": "v1", "due": True, "mastery": 0.2},
)
```

Actual:

```text
review_queue contains v1 twice
due_items contains v1 twice
backlog_count=2
```

One logical item becomes two units of workload.

## Malformed mastery reproduction

Input:

```text
v1 mastery=-100.0, not due
v2 mastery=0.9, due=True
```

Actual prioritization places the malformed `v1` before the actually due item because:

```python
(1.0 - mastery) * 20
```

becomes an enormous positive score.

### Required remediation

- canonical item identity deduplication;
- finite non-boolean mastery normalization;
- bounded mastery domain;
- malformed mastery cannot increase priority;
- explicitly exercise recall and importance if they are accepted rule semantics;
- backlog/counts reflect logical items, not duplicate input records.

---

# 14-rule closure matrix

The final audit performed a direct contract-oriented pass over the frozen rule layer.

```text
LanguageLevelEvidenceRule        FAIL — no-evidence estimate accepted
SkillSeparationRule              no new closure blocker found
LanguageVarietyValidityRule      no new closure blocker found
ProficiencyFrameworkRule         FAIL — provenance not required
ErrorPatternEvidenceRule         FAIL — canonical minimum bypassable
CorrectionPriorityRule           no new closure blocker found
AdaptiveDifficultyRule           FAIL — comparability/provenance/numeric boundary
SpacedReviewRule                 FAIL — duplicate/malformed review state
LearningLoadRule                 FAIL — invalid real constraints
GoalAlignmentRule                FAIL — activity ignored
ProgressionEvidenceRule          PASS for previously audited semantics
CertificationTemporalRule        PASS for previously audited temporal ordering
CulturalContextEvidenceRule      no new closure blocker found
LanguageMemoryConsentRule        no new closure blocker found
```

This matrix is the principal reason closure is denied.

---

# Why 11,406 green tests did not detect this

The regression suite is broad but several tests prove only the positive example, not that the semantic input matters.

Examples:

```text
AdaptiveDifficulty test passes comparable=True
but never proves comparable=False cannot increase.

GoalAlignment test proves both goals remain listed
but never proves unrelated activity is rejected.

Framework test supplies a source-looking string
but never proves source provenance is required.

ErrorPattern tests use default threshold
but never attack threshold=0/1/True.

LearningLoad test uses available_time=20
but never attacks Inf/bool/negative.

SpacedReview test uses sane unique records
but never attacks duplicate IDs or malformed mastery.
```

This is a classic mutation/property-testing gap:

```text
field appears in test input
!=
implementation actually depends on field
```

The next remediation must therefore test **semantic sensitivity**, not only expected happy-path output.

---

# Required closure strategy

Do not patch the seven reproductions independently.

Perform one complete rule-layer hardening pass with property/mutation tests for **all 14 frozen rules**.

For every rule, prove:

```text
required evidence changes outcome
removing required evidence fails closed
malformed numeric values fail closed
bool is not numeric evidence
duplicate provenance/items do not increase support
caller cannot lower canonical safety/evidence thresholds
irrelevant inputs do not become aligned/relevant evidence
input order does not change evidence semantics
strict JSON output
input immutability
```

Specific mandatory REDs:

```text
ESTIMATED C1 + no evidence -> not grounded
framework mapping + no provenance -> not calibrated
pattern threshold 0/1/True -> still requires >=2
adaptive comparable=False -> cannot increase
adaptive duplicate provenance -> cannot increase
adaptive Inf/bool score -> insufficient evidence
goal unrelated activity -> not aligned
goal no active goals -> not aligned / insufficient
learning load Inf/bool/negative -> no crash/impossible duration
spaced duplicate ID -> one logical item
spaced negative/bool/Inf mastery -> no priority inflation
recall/importance mutations -> observable review-priority effect
```

---

# Final status

```text
BUNDLE_INTEGRITY=PASS
V1_FINDINGS_REMEDIATION=PRESERVED
V2_FINDINGS_REMEDIATION=PRESERVED
V3_FINDINGS_REMEDIATION=PASS

TRACE_RUNTIME_PROVENANCE=PASS
PERMISSION_RUNTIME_IDENTITY=PASS
SELECTED_PROFILE_MODE=PASS
EXERCISE_UNKNOWN_SEMANTICS=PASS
VOCABULARY_MASTERY=PASS
CALENDAR_BOUNDARY=PASS
REAL_WORKFLOWS=9_PASS
CANON=16_15_14_15_9
PACKAGE_MODULES=14_PASS
PARENTHOOD_REGRESSION=PASS

FINAL_RULE_LAYER_CLOSURE=FAIL

PHASE10_26_FINAL_INDEPENDENT_CLOSURE_AUDIT=FAIL
BLOCKERS=1
MAJORS=2
MINORS=0
CLOSURE=NO
DP_026=REQUIRES_PHASE_INSPECTION
AT_DP_026=CANDIDATE_PASS_NOT_CLOSURE_PASS
PUSH=NO
MERGE=NO
REPO_MODIFIED=NO
```
