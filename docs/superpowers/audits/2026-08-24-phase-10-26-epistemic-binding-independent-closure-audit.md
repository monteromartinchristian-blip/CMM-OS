# Phase 10.26 — Epistemic Binding Independent Closure Audit

## Audit identity

- Project: CMM OS
- Phase: 10.26 — Languages Domain
- Audit type: independent closure audit of epistemic-binding candidate
- Candidate branch: `feature/phase-10-domain-intelligence`
- Candidate HEAD: `9ea7b127d400ca664388f2d7fc084cd9527e6d88`
- Audited baseline: `b493c27`
- Bundle: `phase-10-26-epistemic-binding-independent-closure-audit-bundle.tar.gz`
- Observed SHA-256: `aa8ff67bb12726ab7726163d46ba589b7c92f2062874b1d28aa8acaf49cc882e`
- External sidecar: PASS
- Internal `SHA256SUMS`: 843 / 843 PASS
- Repository modified by this audit: NO
- Push: NO
- Merge: NO

# Verdict

```text
PHASE10_26_EPISTEMIC_BINDING_INDEPENDENT_CLOSURE_AUDIT=FAIL
BLOCKERS=1
MAJORS=3
MINORS=0
CLOSURE=NO
DP_026=REQUIRES_PHASE_INSPECTION
```

The candidate genuinely remediates the exact `1 BLOCKER + 4 MAJOR` reproductions from the previous audit in several important paths. The delivery evidence is also materially stronger: full all-domain/global/Ruff/compileall logs, RED records, direct markers, and adversarial review are present in the bundle.

Closure is nevertheless denied because framework/source binding is still not end-to-end. The implementation now contains both strict and legacy-permissive paths for the same epistemic concepts.

The decisive root cause is:

```text
epistemic binding was added per helper/test case
instead of being made one invariant shared by every Languages proficiency/mapping/source path
```

That is why new strict tests pass while older permissive tests still encode and preserve the bypass.

---

# 1. Bundle integrity and verification evidence

External SHA-256:

```text
aa8ff67bb12726ab7726163d46ba589b7c92f2062874b1d28aa8acaf49cc882e
```

Sidecar: exact match.

Internal integrity:

```text
SHA256SUMS: 843 / 843 PASS
```

Candidate identity:

```text
HEAD=9ea7b127d400ca664388f2d7fc084cd9527e6d88
BRANCH=feature/phase-10-domain-intelligence
tracked worktree clean
only tmp/ untracked
```

Fresh evidence now actually included:

```text
rule closure suite      163 passed
Languages suite         373 passed
all domains             6039 passed
global suite           11569 passed
Ruff                       PASS
Ruff py310                 PASS
compileall                 PASS
canon inventory            PASS
direct markers             present
RED evidence               present
adversarial review         present
```

Canonical inventory:

```text
entities=16
resources=15
rules=14
operations=15
workflows=9
modules=14
```

Diff from `b493c27` is tightly scoped:

```text
cmm/domains/languages/rules.py
tests/domains/test_languages_domain_adaptation_progression.py
tests/domains/test_languages_domain_adversarial.py
tests/domains/test_languages_domain_dp026_acceptance.py
tests/domains/test_languages_domain_operations.py
tests/domains/test_languages_domain_rule_closure.py
plus the installed prior audit document
```

Phase 10.27 / Paternidad production is untouched.

---

# 2. Previous `1 BLOCKER + 4 MAJOR` — disposition

## Certification source with no provenance

The exact previous reproduction is fixed:

```text
current official with no provenance
-> no rank 6
-> decision-critical verification required
```

The AT-DP-026 fixture now contains:

```text
official_source_id
```

for current/stale official sources.

## Direct ACTFL → CEFR classification leakage

The exact previous `classify_proficiency_record()` reproduction is fixed:

```text
requested CEFR
+ ACTFL-tagged evidence
-> does not ground CEFR estimate
```

## Explicit mapping applicability mutations

The new test correctly blocks records where an explicitly supplied:

```text
source_framework
target_framework
source_value
```

does not match the requested mapping.

## Learning-load semantic inputs

The previous “echo-only” behavior is improved:

```text
heavy recent load -> reduces burden
urgent deadline -> exam practice
review backlog -> spaced review priority
explicit priority -> changes activities
```

## GoalAlignment `skills` / `purpose`

The approved plural `skills` and `purpose` fields are now consumed.

## Malformed evidence containers

The common `_deduplicate_evidence()` boundary now safely treats malformed non-collection containers as no evidence instead of raising TypeError.

## Cultural arbitrary mapping

An arbitrary mapping such as:

```python
{"foo": "bar"}
```

no longer becomes grounded cultural evidence.

These are real improvements.

---

# B-001 — BLOCKER
# Framework binding is still not an end-to-end invariant

This blocker has three reproductions sharing one root cause.

---

## B-001-A — cross-framework mapping evidence is still optional about the fields that supposedly bind it

The remediation claims that mapping evidence must bind:

```text
source_framework
source_value/source_range
target_framework
target_range
provenance
```

Current `_is_applicable_mapping()` only rejects these fields **if they are present and mismatched**.

It does not require them to exist.

Therefore this mapping record:

```python
{
    "source_id": "conc-1",
    "target_range": "B2",
}
```

is still accepted for any cross-framework request.

### Independent execution against exact bundled source

```text
IELTS 6.5 + {source_id, target_range=B2}
-> grounded_approximate_mapping
-> B2
-> calibrated=True

IELTS 0 + same record
-> grounded_approximate_mapping
-> B2
-> calibrated=True

IELTS "garbage" + same record
-> grounded_approximate_mapping
-> B2
-> calibrated=True
```

So the previous root defect still exists through a legacy evidence shape:

```text
provenance proves that a concordance record exists
but does not prove that the record applies to this source framework/value/target framework
```

### Test-suite contradiction

The dedicated closure suite contains the new strict test:

```text
test_framework_mapping_source_value_and_applicability_required
```

but older tests still explicitly require this permissive behavior:

```text
test_framework_mapping_accepts_each_canonical_provenance_alias
```

constructs:

```python
{provenance_field: "concordance-v1", "target_range": "B2"}
```

with no source framework/value or target framework and asserts:

```text
grounded_approximate_mapping
calibrated=True
```

Likewise the duplicate-provenance and permutation tests use mapping records containing only provenance + target range and expect calibration.

The suite is therefore internally contradictory:

```text
new contract:
mapping applicability required

legacy contract:
provenance + target_range is sufficient
```

Production implements both by making applicability fields optional.

This must be resolved by deleting/updating the permissive contract, not by adding another branch.

---

## B-001-B — `source_range` is not implemented as a range

The remediation permits:

```text
source_value OR source_range
```

but the implementation checks:

```python
s_val.upper() in rec_src_rng.upper()
```

That is substring membership, not range membership.

Independent execution:

```text
source_value="6.5"
source_range="6.0-7.0"
```

returns:

```text
calibrated=False
mapping_status=identity_forbidden
```

even though 6.5 lies inside the declared numeric range.

Conversely, a textual range/string merely containing the characters of the source value can satisfy the check without range semantics.

If `source_range` remains part of the contract it needs an explicit deterministic range representation/parser. Otherwise remove it and require exact `source_value`.

---

## B-001-C — `evaluate_level_update()` still allows cross-framework stable-level promotion and drops framework identity

`classify_proficiency_record()` was hardened, but the other stable proficiency path was not.

`evaluate_level_update()` filters by:

```text
comparable=True
comparison_key
independent provenance
target skill
```

but never checks framework.

Independent exact-source reproduction:

Existing record:

```python
{
    "kind": "ESTIMATED",
    "skill_scope": "writing",
    "level_or_score": "B2",
    "framework": "CEFR",
}
```

Evidence:

```python
[
  {
    "provenance_id":"p1",
    "skill":"writing",
    "observed":"C1",
    "framework":"ACTFL",
    "comparable":True,
    "comparison_key":"essay",
  },
  {
    "provenance_id":"p2",
    "skill":"writing",
    "observed":"C1",
    "framework":"ACTFL",
    "comparable":True,
    "comparison_key":"essay",
  }
]
```

Actual:

```text
stable_update_supported=True
proposed_level=C1
```

and the resulting record becomes:

```python
{
    "kind":"ESTIMATED",
    "skill_scope":"writing",
    "level_or_score":"C1",
    "evidence":[ACTFL evidence...],
}
```

The output also drops `framework` entirely.

This violates both frozen requirements:

```text
framework must be explicit whenever a level or score depends on it
```

and:

```text
mapping != identity
```

The operation `languages.update_level_evidence` calls this helper directly, so this is not dead utility code.

### Required root correction

There must be one proficiency claim/evidence binding predicate used by **both**:

```text
classify_proficiency_record()
evaluate_level_update()
```

It must bind at least:

```text
skill
framework
claimed/observed value
provenance
comparability where stable inference is attempted
```

A cross-framework record may participate only through an explicit grounded framework-mapping result.

---

# M-001 — MAJOR
# Certification source authority still accepts occurrence provenance as source authority

The exact “no provenance at all” case is fixed, but `_source_has_provenance()` currently accepts:

```python
_certification_provenance(s)
or _canonical_provenance(s)
```

`_canonical_provenance()` includes:

```text
provenance_id
source_id
assessment_id
sample_id
context_id
session_id
```

The latter four are occurrence/context identifiers, not source-authority identities.

Independent exact-source reproduction:

```python
{
    "id":"x",
    "source_type":"official",
    "temporal_state":"current",
    "session_id":"s1",
}
```

returns:

```text
authority_rank=6
needs_verification=False
```

A session ID therefore upgrades a caller-labeled record to fully authoritative current official source.

The frozen source-authority requirement is about grounding **the source**, not proving that a session/sample/context exists.

### Required correction

For certification source authority use a dedicated narrow source-provenance predicate.

Accept only source-authority identity fields, e.g.:

```text
official_source_id
source_id
provenance_id only if its contract explicitly denotes source provenance
```

Do not reuse generic evidence occurrence aliases such as:

```text
session_id
sample_id
assessment_id
context_id
```

Add removal/substitution mutations for each alias.

---

# M-002 — MAJOR
# GoalAlignment still universalizes generic pedagogical activity

The new `skills` and `purpose` support works, but the function retains:

```python
if act_type in ("practice", "review", "lesson", "exercise")
or act_purpose in ("practice", "review", "lesson", "study"):
    matched = True
```

This branch runs independently for every active goal.

Independent reproduction:

Goals:

```text
g1 = certification C1
g2 = conversation fluency
```

Activity:

```python
{"type":"practice"}
```

Actual:

```text
activity_fit=aligned
aligned_goals=["g1","g2"]
```

The generic word “practice” therefore proves relevance to every active goal.

This directly contradicts the previous hardening requirement:

```text
Do not universalize generic activity to every goal.
```

and weakens the frozen purpose:

```text
Ensure activities serve one or more active goals.
```

A generic pedagogical activity can remain valid activity, but goal alignment must stay:

```text
unknown / insufficient / not specifically aligned
```

until skill/purpose/goal linkage exists.

---

# M-003 — MAJOR
# Nested LearningLoad numeric semantics still treat bool as numeric deadline evidence

The top-level `available_time` numeric boundary is correct.

However urgency checks use:

```python
isinstance(days_remaining, (int, float))
and days_remaining <= 3
```

without excluding bool.

In Python:

```text
True is an int-like value
```

Independent exact-source reproduction:

```python
evaluate_learning_load(
    available_time=30,
    energy="moderate",
    deadlines=({"days_remaining": True},),
)
```

Actual:

```text
recommended_activities=[
    "exam_practice",
    "guided_practice",
    "spaced_review",
]
```

So malformed boolean deadline data creates a real semantic priority change.

This violates the hardening-wide rule:

```text
bool is not numeric evidence
malformed numeric input must not increase support/priority
```

The same finite/non-bool helper discipline used for scores/time should be reused for nested numeric decision inputs.

---

# 3. AT-DP-026 disposition

The candidate now correctly grounds the concrete certification fixture with:

```text
official_source_id
```

and preserves:

```text
45 exact semantic checkpoints
9 real workflows
real resolver/composer
real rule execution IDs
real PermissionGate decision IDs
real WorkflowRun IDs
selected profile mode
no WorkflowEvent result-ID substitution
calendar shared external boundary
memory proposal/binding trace
```

For the exact connected scenario:

```text
AT_DP_026_CHECKPOINT_COUNT=45_PASS
AT_DP_026_REAL_WORKFLOWS=9_PASS
AT_DP_026_CERTIFICATION_FIXTURE_PROVENANCE=PASS
AT_DP_026_TRACE_RUNTIME_PROVENANCE=PASS
```

However Phase closure is still denied because canonical rule/operation behavior outside that happy path can bypass the same framework/source contracts.

Therefore:

```text
AT_DP_026_CANDIDATE_SCENARIO=PASS
DP_026_PHASE_CLOSURE=FAIL
```

---

# 4. Historical V1/V2/V3 disposition

No new regression was found in the previously repaired infrastructure and operation boundaries:

```text
typed DomainMetadata composer compatibility
accumulated WorkflowRun.outputs
trace EVIDENCE/MEMORY_PROPOSAL/MEMORY_BINDING/PRESENTATION_RESULT
presentation_result_ids
PermissionGateResult.decision_id
approval consumption ID reservation
calendar shared boundary
runtime rule result identity
runtime permission decision identity
selected profile mode
exercise missing-outcome semantics
vocabulary mastery grounding
progress cross-skill inflation protections
empty assessment/writing/speaking/certification fail-closed
exercise NaN/Inf fail-closed
```

The current failures are concentrated in Languages epistemic binding.

---

# 5. 14-rule closure matrix

```text
LanguageLevelEvidenceRule        PARTIAL PASS — direct classifier fixed; stable update path still leaks frameworks
SkillSeparationRule              PASS for audited distinctions
LanguageVarietyValidityRule      PASS for audited distinctions
ProficiencyFrameworkRule         FAIL — applicability fields optional; source_range not a range
ErrorPatternEvidenceRule         PASS
CorrectionPriorityRule           PASS for audited mutation semantics
AdaptiveDifficultyRule           PASS
SpacedReviewRule                 PASS for audited dedup/bounds
LearningLoadRule                 FAIL — nested bool deadline evidence affects recommendation
GoalAlignmentRule                FAIL — generic practice universally aligns goals
ProgressionEvidenceRule          PASS for audited baseline/comparability
CertificationTemporalRule        FAIL — generic occurrence IDs can confer source authority
CulturalContextEvidenceRule      PASS for audited grounding boundary
LanguageMemoryConsentRule        PASS
```

---

# 6. Why 163 + 373 + 6039 + 11569 green tests still miss this

The remaining defect is now visible as a **contract split inside the tests themselves**.

Example:

```text
new test:
mapping record must match source framework/value/target framework

old test:
source_id + target_range alone must calibrate
```

Both pass because production treats the binding fields as optional.

Likewise:
- certification tests mutate “no provenance” but not “wrong provenance category”;
- GoalAlignment tests mutate explicit semantic activity but not generic pedagogical activity;
- LearningLoad tests mutate top-level invalid time but not nested bool numeric fields;
- framework leakage test covers `classify_proficiency_record`, not `evaluate_level_update`.

The next gate must test the invariant across **all paths**, not one helper at a time.

---

# 7. Root-cause remediation direction

After multiple remediation rounds, another set of local `if` guards is not the right fix.

The minimal architectural correction should remain Languages-local but centralize four concepts:

## A. One framework-bound proficiency evidence predicate

Used by:

```text
classify_proficiency_record
evaluate_level_update
```

It must enforce:
- framework;
- skill;
- value;
- provenance;
- comparability/independence where stable inference is requested.

## B. One explicit framework mapping record contract

Choose one of:

```text
exact source_value binding
```

or a real structured range representation.

Do not support a textual `source_range` with substring semantics.

Every calibrated cross-framework mapping record must require:

```text
source_framework
source binding
target_framework
target_range
source provenance
```

Update/remove legacy tests that require provenance+target_range alone to calibrate.

## C. One source-authority provenance predicate

Certification authority must not reuse generic occurrence IDs.

## D. One semantic numeric normalizer

Reuse for:
- available_time;
- deadline days_remaining;
- recent-load numeric fields;
- scores/mastery/recall/importance where applicable.

Bool, NaN and Inf must never become semantic numeric evidence.

GoalAlignment should separately remove the generic “practice matches every goal” shortcut.

This is a focused internal hardening, not a new subsystem and not a shared-engine redesign.

---

# 8. Mandatory REDs before the next candidate

At minimum:

```text
mapping record {source_id,target_range} -> NOT calibrated
same minimal record + source_value 6.5/0/"garbage" -> all NOT calibrated

mapping record missing source_framework -> NOT calibrated
mapping record missing target_framework -> NOT calibrated
mapping record missing source binding -> NOT calibrated

source_range "6.0-7.0" with 6.5
-> either correctly supported by structured range semantics
or source_range feature removed/rejected

evaluate_level_update CEFR existing + ACTFL evidence
-> no stable CEFR update

evaluate_level_update successful stable estimate
-> updated record preserves explicit framework

official/current + session_id only -> not rank 6
official/current + sample_id only -> not rank 6
official/current + assessment_id only -> not rank 6
official/current + context_id only -> not rank 6

GoalAlignment {"type":"practice"} + unrelated concurrent goals
-> must not align every goal

deadline days_remaining=True
-> must not create exam-practice urgency
```

Also add a test that no legacy test asserts the now-forbidden minimal mapping contract.

---

# 9. Final markers

```text
BUNDLE_INTEGRITY=PASS
CANDIDATE_HEAD=9ea7b12

PREVIOUS_EPISTEMIC_EXACT_REPRODUCTIONS=MOSTLY_REMEDIATED
VERIFICATION_EVIDENCE_BUNDLE=PASS

FRAMEWORK_MAPPING_COMPLETE_APPLICABILITY=FAIL
FRAMEWORK_RANGE_SEMANTICS=FAIL
LEVEL_UPDATE_FRAMEWORK_BINDING=FAIL
CERTIFICATION_SOURCE_PROVENANCE_CATEGORY=FAIL
GOAL_ALIGNMENT_GENERIC_ACTIVITY=FAIL
LEARNING_LOAD_NESTED_BOOL_NUMERIC=FAIL

AT_DP_026_FROZEN_SEMANTIC_CHECKPOINTS=45_PASS
AT_DP_026_REAL_WORKFLOWS=9_PASS
AT_DP_026_CURRENT_FIXTURE_SOURCE_AUTHORITY=PASS
AT_DP_026_CANDIDATE_SCENARIO=PASS

CANON=16_15_14_15_9
PACKAGE_MODULES=14_PASS
PARENTHOOD_REGRESSION=PASS

PHASE10_26_EPISTEMIC_BINDING_INDEPENDENT_CLOSURE_AUDIT=FAIL
BLOCKERS=1
MAJORS=3
MINORS=0
CLOSURE=NO
DP_026=REQUIRES_PHASE_INSPECTION
PUSH=NO
MERGE=NO
REPO_MODIFIED=NO
```
