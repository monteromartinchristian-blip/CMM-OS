# Phase 10.26 — Rule-Hardened Independent Closure Audit

## Audit identity

- **Project:** CMM OS
- **Phase:** 10.26 — Languages Domain
- **Audit type:** independent closure audit of rule-hardened candidate
- **Candidate branch:** `feature/phase-10-domain-intelligence`
- **Candidate HEAD:** `b493c27d16ccae73038fa7ed4234aa00e5320176`
- **Bundle:** `phase-10-26-rule-hardened-independent-closure-audit-bundle.tar.gz`
- **Observed SHA-256:** `26b33e80f886ee5af05452634ba71f28e766b39ff78132ca6f68d64b1fdec876`
- **Sidecar:** exact match
- **Internal SHA256SUMS:** 843 / 843 PASS
- **Repository modified by audit:** NO
- **Push:** NO
- **Merge:** NO

# Verdict

```text
PHASE10_26_RULE_HARDENED_INDEPENDENT_CLOSURE_AUDIT=FAIL
BLOCKERS=1
MAJORS=4
MINORS=0
CLOSURE=NO
DP_026=REQUIRES_PHASE_INSPECTION
```

The rule hardening is substantial and genuinely fixes the concrete defects reported in the previous final closure audit. However, the candidate still does **not** satisfy the frozen Phase 10.26 epistemic contract or the approved hardening plan.

The decisive issue is not test count. The dedicated 156-case suite contains several happy-path/mutation tests, but some semantically required inputs still do not control production behavior.

---

# 1. Integrity and candidate identity

External bundle checksum:

```text
26b33e80f886ee5af05452634ba71f28e766b39ff78132ca6f68d64b1fdec876
```

Sidecar contains the same checksum.

Internal `SHA256SUMS` verification:

```text
843 files verified
0 missing
0 mismatched
```

Bundle metadata:

```text
HEAD=b493c27d16ccae73038fa7ed4234aa00e5320176
BRANCH=feature/phase-10-domain-intelligence
tracked worktree clean
only tmp/ untracked
```

The diff from the previously audited `1f987c8` changes only:

```text
cmm/domains/languages/rules.py
Languages rule/proficiency/error/variety tests
hardening audit/plan documentation
```

No Paternidad / Phase 10.27 production file is changed.

Canonical package remains:

```text
entities=16
resources=15
rules=14
operations=15
workflows=9
production_modules=14
```

---

# 2. What the rule hardening genuinely fixed

The exact previous closure-audit reproductions are materially improved.

## Language level no-evidence default

Resolved:

```text
ESTIMATED C1 + evidence=()
-> unassessed
-> confidence 0
```

## Pronunciation evidence

Resolved for the audited pronunciation boundary:

```text
transcript / user message / self report
!= grounded pronunciation assessment
```

## Framework mapping provenance

Resolved for the specific previous defect:

```text
{"target_range":"B2"}
without provenance
-> not calibrated
```

Conflicting target ranges now fail closed.

`mapping_evidence=None` also fails closed.

## Error recurrence threshold

Resolved:

```text
0 / 1 / True / negative / malformed
cannot reduce canonical recurrence minimum below 2
```

## Adaptive difficulty

Resolved for the prior defects:

```text
comparable=False -> no increase
duplicate provenance -> no repeated support
mismatched comparison keys -> no repeated support
bool/NaN/Inf/out-of-range score -> ignored/fail closed
invalid current difficulty -> no crash
```

## Spaced review

Resolved for prior findings:

```text
duplicate logical ID -> one queue item
mastery bounded
bool/NaN/Inf mastery does not inflate
recall and importance affect priority
```

## Learning-load numeric boundary

Resolved:

```text
available_time=Inf -> no crash
available_time=True -> not one minute
available_time=-10 -> no negative duration
```

## Goal alignment basic activity sensitivity

Resolved for the previous exact case:

```text
roleplay -> conversation
formal_exam_essay -> certification
unrelated_tax_filing -> no aligned goals
```

## V3 remediation

No regression was found in:

```text
runtime rule execution IDs
permission decision IDs
selected profile mode
WorkflowRun IDs
no WorkflowEvent ID as result
exercise unknown semantics
vocabulary mastery grounding
calendar shared boundary
memory proposal/binding trace
```

---

# FINAL-B-001 — BLOCKER
# Epistemic source/framework binding is still bypassable

Three closely related defects remain in the core proficiency/certification evidence boundary.

They share one root cause:

```text
having an evidence/source object
!=
that evidence/source actually supports the asserted semantic claim
```

This violates the frozen source-authority and framework-separation invariants.

---

## B-001-A — `CertificationTemporalRule` grants full authority from caller labels without provenance

Frozen design §79:

```text
A user statement alone does not automatically ground:
- an official certification requirement;
- a current examination date;
- framework equivalence;
- a certified result.
```

The approved final hardening plan Task 12 explicitly required:

```text
{"source_type":"official","date_valid":True}
with no source/provenance identity
must not become fully authoritative.
```

It required canonical identity such as:

```text
source_id
official_source_id
provenance_id
```

Current implementation ranks sources using only:

```text
source_type
temporal state
```

The provenance helper is never consulted by `_auth()`.

### Independent exact-source reproduction

Input:

```python
evaluate_certification_source(
    sources=(
        {
            "id": "x",
            "source_type": "official",
            "temporal_state": "current",
            "format": "computer",
        },
    ),
    decision_critical=True,
)
```

Actual:

```text
selected_source.id=x
authority_rank=6
needs_verification=False
unresolved_conflict=False
```

Likewise:

```text
current unprovenanced secondary
-> authority_rank=5
-> needs_verification=False
```

Therefore:

```text
caller says "official/current"
-> treated as actual authoritative current source
```

### The connected AT-DP-026 currently relies on the same bypass

The candidate acceptance scenario provides:

```python
{"id": "current-official", "source_type": "official", "date_valid": True}
```

with no:

```text
source_id
official_source_id
provenance_id
```

Checkpoint 32 then passes:

```text
32-select-current-official-certification-source
```

Therefore the formal connected acceptance is not epistemically grounded under the approved hardening contract.

This is why this finding is a closure BLOCKER rather than a test-only issue.

### Process evidence

Task 17 explicitly required the adversarial mutation:

```text
label unprovenanced source official/current
```

But `review-evidence/adversarial-review.md` omits that mutation while declaring:

```text
Critical 0
Important 0
Minor 0
```

The bundle therefore marks a required adversarial gate complete without actually exercising it.

---

## B-001-B — `LanguageLevelEvidenceRule` permits silent cross-framework evidence reuse

The helper accepts:

```text
framework="CEFR"
```

as the output framework, but `_evidence_matches_proficiency_claim()` does not compare the evidence framework to the requested framework.

Independent reproduction:

```python
classify_proficiency_record(
    kind="ESTIMATED",
    framework="CEFR",
    level_or_score="C1",
    skill_scope="writing",
    evidence=(
        {
            "provenance_id":"p1",
            "skill":"writing",
            "observed":"C1",
            "framework":"ACTFL",
        },
        {
            "provenance_id":"p2",
            "skill":"writing",
            "observed":"C1",
            "framework":"ACTFL",
        },
    ),
)
```

Actual:

```text
kind=ESTIMATED
framework=CEFR
level_or_score=C1
confidence=0.75
```

Thus:

```text
ACTFL evidence
-> CEFR C1 estimate
```

without `ProficiencyFrameworkRule`.

This directly violates:

```text
framework mapping != framework identity
```

and bypasses the dedicated mapping rule.

### Required correction

Evidence carrying a framework must match the claimed framework unless an explicit, provenance-grounded framework-mapping result is supplied.

Do not silently reuse cross-framework values.

---

## B-001-C — `ProficiencyFrameworkRule` ignores `source_value` for cross-framework mapping

`source_value` is assigned to `s_val`, but for cross-framework mappings the value is never used to determine evidence applicability.

Independent reproduction with identical mapping evidence:

```text
IELTS 6.5 -> CEFR -> B2 calibrated
IELTS 0   -> CEFR -> B2 calibrated
IELTS "garbage" -> CEFR -> B2 calibrated
IELTS None -> CEFR -> B2 calibrated
```

All return:

```text
mapping_status=grounded_approximate_mapping
target_estimate_range=B2
calibrated=True
```

The mapping record:

```python
{"source_id":"conc-1","target_range":"B2"}
```

contains no binding to:

```text
source framework
source value/range
target framework
```

So provenance currently proves only that *some object exists*, not that the mapping applies to the value being converted.

Same-framework malformed/missing values are also returned as:

```text
same_framework
target_estimate_range=""
calibrated=True
```

### Required correction

A grounded mapping record must be applicable to the asserted mapping.

At minimum preserve and validate:

```text
source_framework
source_value or source_range
target_framework
target_range
canonical provenance
```

A missing/malformed/unmatched source value must fail closed.

Equivalent matching semantics may be implemented with canonical ranges when exact equality is inappropriate, but applicability must be explicit and testable.

---

# FINAL-M-001 — MAJOR
# `LearningLoadRule` still ignores most of its semantic inputs

The approved Task 9 required:

```text
available time / energy / recent load
>
preferences / priorities
```

and stated:

```text
deadlines and recent_load must either:
- be deliberately consumed in recommendation semantics; or
- be explicitly represented as unsupported/unused.
```

Preferred behavior included:

```text
high recent load -> lower/maintain burden
urgent deadline -> influence activity priority
neither may exceed available time
```

Current production now correctly validates time and energy.

However:

```text
priorities
review_backlog
deadlines
recent_load
```

do not change:

```text
recommended_duration_minutes
recommended_activities
load_status
```

They are only counted/echoed as:

```text
priorities_considered
backlog_considered
deadlines_considered
recent_load_considered
```

This is especially problematic because the output names say “considered” although the recommendation algorithm did not consume them.

### Independent reproduction

Base:

```python
evaluate_learning_load(
    available_time=30,
    energy="moderate",
)
```

Result:

```text
duration=30
activities=["guided_practice","spaced_review"]
load_status=standard
```

With deadline/recent load:

```python
evaluate_learning_load(
    available_time=30,
    energy="moderate",
    deadlines=({"urgent": True},),
    recent_load={"hours": 10},
)
```

Same semantic recommendation:

```text
duration=30
activities=["guided_practice","spaced_review"]
load_status=standard
```

Only metadata echoes change.

The same is true for explicit `priorities` and `review_backlog`.

### Test gap

The closure test is named:

```text
test_learning_load_deadlines_and_recent_load_reflection
```

but asserts only that the values/counts appear in the output. It does not prove that the rule adapts learning burden or priority.

This is exactly the root class the hardening was intended to eliminate:

```text
field appears in input/output
!=
field controls semantics
```

---

# FINAL-M-002 — MAJOR
# `GoalAlignmentRule` implements only part of its approved activity contract

Task 10 explicitly required the rule to consume, when present:

```text
type
kind
skill
skills
goal_id
goal_ids
purpose
```

Current implementation consumes:

```text
type/activity_type/kind
skill/target_skill
topic
target
goal_id/goal_ids
```

but does not consume:

```text
skills
purpose
```

### Independent reproduction

Input:

```python
align_activity_to_goals(
    activity={
        "skills": ["speaking", "listening"],
        "purpose": "conversation",
    },
    goals=(
        {
            "id":"g1",
            "kind":"conversation",
            "target":"fluency",
        },
    ),
)
```

Actual:

```text
activity_fit=not_aligned
aligned_goals=[]
```

Equivalent intent expressed using:

```python
{"type":"roleplay"}
```

returns:

```text
activity_fit=aligned
aligned_goals=["g1"]
```

Thus semantically equivalent activity intent changes outcome merely because it uses two approved fields that production ignores.

### Required correction

Normalize all approved activity representations before relevance evaluation.

At minimum:

```text
skills -> canonical skill set
purpose -> deterministic semantic tag
```

and exercise each with mutation tests.

---

# FINAL-M-003 — MAJOR
# Shared evidence-container normalization is still not fail-closed

The original implementation-plan global constraints require:

```text
Absent, malformed, unknown, conflicting, stale,
and insufficient-evidence states remain distinct where material.
```

The rule module itself states:

```text
Malformed evidence fails closed and never increases certainty.
```

Several public helpers call `_deduplicate_evidence()` directly.

`_deduplicate_evidence()` assumes the input is iterable and has no container guard.

Independent exact-source probes:

```python
classify_proficiency_record(..., evidence=None)
-> TypeError: 'NoneType' object is not iterable

separate_skill_evidence(evidence=None)
-> TypeError

evaluate_level_update(evidence=None)
-> TypeError

evaluate_progression(previous_evidence=None, current_evidence=())
-> TypeError
```

The same occurs for other malformed scalar evidence containers such as:

```text
True
False
NaN
Inf
integer
object()
```

These are not epistemically positive, but they crash the rule instead of remaining an explicit insufficient/malformed state.

### Why this matters at runtime

The rule wrappers obtain material through arbitrary metadata:

```python
mat.get("evidence", ())
```

If the field exists with value `None`, the default `()` is not used.

Thus a malformed runtime payload can reach these helpers directly.

### Required correction

Make the common evidence normalizer itself fail closed:

```text
valid collection -> normalize/dedupe
missing/malformed container -> []
```

Then add one shared mutation matrix covering every helper that consumes it.

---

# FINAL-M-004 — MAJOR
# `CulturalContextEvidenceRule` labels arbitrary mappings as grounded evidence

Current implementation defines:

```python
valid_evidence = [
    normalized mapping
    for mapping in evidence
]
has_grounded_evidence = len(valid_evidence) > 0
```

It performs no provenance/evidence-grounding check.

Independent reproduction:

```python
evaluate_cultural_context(
    claim="People commonly do X",
    evidence=({"foo":"bar"},),
)
```

Actual:

```text
has_grounded_evidence=True
evidence_status="evidenced"
qualified_tendency=True
```

The record has no source, provenance, corpus reference, observation reference, or other grounding.

This conflicts with the rule's own output vocabulary:

```text
grounded_evidence
weak_or_unprovenanced
```

and with the Phase 10.26 requirement to preserve provenance and uncertainty.

### Required correction

Do not treat “non-empty Mapping” as “grounded evidence”.

Use a conservative cultural-evidence predicate:
- canonical source/provenance reference; or
- an explicitly typed authorized user/lived-experience observation if the domain contract permits it.

Weak/unprovenanced mappings may remain visible but must not produce:

```text
has_grounded_evidence=True
evidence_status=evidenced
```

---

# 3. Rule-layer matrix after independent audit

```text
LanguageLevelEvidenceRule        FAIL — cross-framework evidence leakage
SkillSeparationRule              PASS for audited frozen distinctions
LanguageVarietyValidityRule      PASS for audited frozen distinctions
ProficiencyFrameworkRule         FAIL — mapping not bound to source value/framework
ErrorPatternEvidenceRule         PASS for audited recurrence invariants
CorrectionPriorityRule           PASS source behavior; mutation test quality incomplete
AdaptiveDifficultyRule           PASS for audited comparability/provenance/numeric boundary
SpacedReviewRule                 PASS for prior logical dedup/numeric findings
LearningLoadRule                 FAIL — semantic inputs echoed, not consumed
GoalAlignmentRule                FAIL — approved `skills` / `purpose` ignored
ProgressionEvidenceRule          PASS for valid typed input; malformed container shared failure
CertificationTemporalRule        FAIL — authority label accepted without provenance
CulturalContextEvidenceRule      FAIL — arbitrary mapping considered grounded
LanguageMemoryConsentRule        PASS
```

The shared malformed evidence-container defect additionally affects:
- LanguageLevel;
- SkillSeparation;
- level update helper;
- Progression.

---

# 4. AT-DP-026 disposition

The candidate still preserves:

```text
45 exact checkpoint names
9 real workflows
real resolver/composer
real rule execution result IDs
real permission decision IDs
real WorkflowRun IDs
no WorkflowEvent ID as workflow result
selected profile mode
calendar external boundary
memory proposal/binding path
```

However checkpoint 32 currently relies on an unprovenanced source record:

```text
current-official
source_type=official
date_valid=True
```

and accepts it as fully authoritative.

Therefore:

```text
AT_DP_026_STRUCTURAL_SEQUENCE=PASS
AT_DP_026_RUNTIME_PROVENANCE_TRACE=PASS
AT_DP_026_CERTIFICATION_SOURCE_AUTHORITY=FAIL
AT_DP_026_CLOSURE_GATE=FAIL
```

It may remain described as a **candidate structural PASS**, but not as independently closed.

---

# 5. Historical V1/V2/V3 regression disposition

The `1f987c8..b493c27` diff does not modify the shared workflow/permission/trace infrastructure.

No regression was found in the previously closed shared fixes:

```text
typed DomainMetadata compatibility
accumulated WorkflowRun.outputs
trace EVIDENCE/MEMORY_PROPOSAL/MEMORY_BINDING/PRESENTATION_RESULT
presentation_result_ids
PermissionGateResult.decision_id
approval-consumption ID reservation
calendar external boundary
```

The V3 operation fixes remain present:

```text
empty exercise -> unassessed
vocabulary mastery evidence-derived
progress result no cross-skill fabrication
empty assessment/writing/speaking/certification fail closed
NaN/Inf exercise score fail closed
```

The new failure is concentrated in Languages rule semantics and acceptance source fixtures.

---

# 6. Verification-evidence quality

The bundle contains credible focused logs for:

```text
156 dedicated rule-closure cases
366 Languages tests
```

and its README records:

```text
6032 all-domain tests
11562 global tests
Ruff PASS
Ruff py310 PASS
compileall PASS
fresh import PASS
```

However Task 21 required the bundle to include:

```text
fresh verification evidence
all direct markers
RED records
```

The actual bundle does not contain:
- an all-domains test log;
- a global test log;
- Ruff/compileall/fresh-import logs;
- Task 19 direct-marker output;
- Task 0/Task 4 RED records.

The only occurrence of markers such as:

```text
CERTIFICATION_SOURCE_PROVENANCE=PASS
ALL_14_RULES_MUTATION_SENSITIVITY=PASS
```

is inside plan/diff text, not captured successful probe output.

This is an **audit-evidence deficiency**, not counted as an additional product defect because the semantic failures above already deny closure.

The next bundle must include the actual output artifacts.

---

# 7. Required final remediation — one root-cause pass

Do not patch only the five reproductions.

The final remediation should establish a reusable semantic-binding discipline across the rule layer.

## A. Evidence container boundary

Centralize collection fail-closed normalization before deduplication.

Required:

```text
None/scalar/bool/NaN/Inf/mapping-as-container
-> empty/invalid evidence collection
-> no crash
-> no epistemic upgrade
```

## B. Claim-to-evidence binding

For proficiency evidence, validate:
- skill;
- claimed level/score;
- framework;
- provenance;
- certification source semantics where applicable.

No cross-framework reuse without explicit mapping result.

## C. Mapping applicability

Framework mapping evidence must bind:
- source framework;
- source value/range;
- target framework;
- target range;
- provenance.

Mutation of source value/framework must change or invalidate result.

## D. Source authority

`CertificationTemporalRule` must require source/provenance identity for authoritative official/secondary ranks.

Update AT-DP-026 fixtures to contain real source identity.

The test must prove removing the source identity changes:

```text
authority rank / needs_verification / selected source
```

## E. Learning-load semantic sensitivity

Every declared material input must:
- affect the recommendation where semantically supported; or
- be explicitly marked unsupported/unused.

Do not call a field “considered” if it is merely echoed.

Required mutations:
- recent load high vs absent;
- urgent deadline vs absent;
- review backlog vs absent;
- explicit priority vs absent.

## F. Goal alignment normalization

Consume all approved fields:

```text
type
kind
skill
skills
goal_id
goal_ids
purpose
```

Equivalent semantics expressed through supported representations should not diverge.

## G. Cultural grounding

Separate:
- provided context;
- grounded evidence;
- weak/unprovenanced evidence.

A non-empty arbitrary mapping is not automatically grounded.

---

# 8. Mandatory adversarial mutations before the next bundle

The next reviewer/agent must directly exercise:

```text
CERTIFIED/ESTIMATED evidence from mismatched framework
cross-framework source_value=None
cross-framework source_value mutation
mapping evidence for wrong source framework/value
unprovenanced current official source
unprovenanced current secondary source
remove provenance from otherwise valid official source
evidence=None on every common-dedup consumer
evidence=True/Inf/scalar on common-dedup consumers
high recent load vs absent
urgent deadline vs absent
review backlog vs absent
priority vs absent
activity.skills only
activity.purpose only
arbitrary cultural evidence mapping
```

Each positive semantic field must have a negative mutation whose output becomes weaker/different.

---

# 9. Final markers

```text
BUNDLE_INTEGRITY=PASS
CANDIDATE_HEAD=b493c27

PREVIOUS_FINAL_B001_EXACT_REPRODUCTIONS=REMEDIATED
PREVIOUS_FINAL_M001_NUMERIC=REMEDIATED
PREVIOUS_FINAL_M002_DEDUP_NUMERIC=REMEDIATED

FRAMEWORK_CLAIM_BINDING=FAIL
FRAMEWORK_SOURCE_VALUE_SENSITIVITY=FAIL
CERTIFICATION_SOURCE_PROVENANCE=FAIL
LEARNING_LOAD_SEMANTIC_SENSITIVITY=FAIL
GOAL_ALIGNMENT_FULL_ACTIVITY_CONTRACT=FAIL
MALFORMED_EVIDENCE_CONTAINER_FAIL_CLOSED=FAIL
CULTURAL_EVIDENCE_GROUNDING=FAIL

AT_DP_026_CHECKPOINT_COUNT=45_PASS
AT_DP_026_REAL_WORKFLOWS=9_PASS
AT_DP_026_TRACE_RUNTIME_PROVENANCE=PASS
AT_DP_026_CERTIFICATION_SOURCE_AUTHORITY=FAIL
AT_DP_026_CLOSURE_GATE=FAIL

CANON=16_15_14_15_9
PACKAGE_MODULES=14_PASS
PARENTHOOD_REGRESSION=PASS

PHASE10_26_RULE_HARDENED_INDEPENDENT_CLOSURE_AUDIT=FAIL
BLOCKERS=1
MAJORS=4
MINORS=0
CLOSURE=NO
DP_026=REQUIRES_PHASE_INSPECTION
PUSH=NO
MERGE=NO
REPO_MODIFIED=NO
```
