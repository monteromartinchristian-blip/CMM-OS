# Phase 10.26 — Final Epistemic Invariant Consolidation Design

**Date:** 2026-08-24
**Project:** CMM OS
**Phase:** 10.26 — Languages Domain
**Status:** design approved in chat; implementation pending
**Audited candidate baseline:** `9ea7b127d400ca664388f2d7fc084cd9527e6d88`

## 1. Goal

Make the next Phase 10.26 candidate the final closure candidate by replacing helper-specific epistemic guards with a small set of **single-source-of-truth invariants inside the existing Languages rule layer**.

The target is not to add features. The target is to make it impossible for two Languages paths to interpret the same proficiency, framework, source-authority, or numeric evidence differently.

## 2. Scope

Primary production file:

```text
cmm/domains/languages/rules.py
```

Tests:

```text
tests/domains/test_languages_domain_rule_closure.py
tests/domains/test_languages_domain_adaptation_progression.py
tests/domains/test_languages_domain_adversarial.py
tests/domains/test_languages_domain_dp026_acceptance.py
tests/domains/test_languages_domain_operations.py
```

Additional existing Languages test files may be updated only where they encode a legacy contract that directly contradicts this design.

No new Languages production module is introduced.

No shared-engine change is expected.

## 3. Frozen architecture

Must remain exactly:

```text
domain:languages
display: Idiomas
profile: LanguageLearningProfile

16 entities
15 resources
14 rules
15 operations
9 workflows
14 production modules
```

`languages.progress_checkpoint` remains canonical.

No Phase 10.27 / Paternidad changes.

No `Nil` restoration.

No push.

No merge.

No Phase 10.26 closure before a fresh independent audit.

## 4. Root cause being eliminated

Repeated audits found the same architectural smell:

```text
one helper validates an epistemic claim strictly
while another helper accepts the same claim through a legacy-permissive path
```

Examples already observed:

```text
classify_proficiency_record blocks ACTFL -> CEFR leakage
but evaluate_level_update still accepts it

new framework-mapping tests require applicability
but legacy tests still accept provenance + target_range only

CertificationTemporal blocks no-provenance sources
but generic occurrence IDs can still masquerade as source authority

LearningLoad validates top-level numerics
but nested bool numerics can still affect decisions
```

The final design therefore makes the invariant itself reusable and central, not merely the test case.

---

# 5. Invariant A — one framework-bound proficiency evidence contract

Create one internal Languages predicate/normalizer used by every path that can establish or update a proficiency claim.

Conceptual interface:

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

The exact private name may differ, but there must be **one implementation**, not duplicated logic.

It must bind:

```text
framework
skill scope
claimed/observed value
canonical evidence provenance
comparability when stable inference/update requires it
```

It must be used by at least:

```text
classify_proficiency_record()
evaluate_level_update()
```

## Required semantics

### Framework

If evidence explicitly declares a framework:

```text
evidence.framework == requested framework
```

is required for direct use.

Cross-framework evidence may never be treated as identity.

A cross-framework record may participate only after an explicit, grounded framework-mapping result has established applicability.

### Skill

Evidence for an unrelated skill cannot ground the requested skill.

### Value

Evidence must semantically support the requested/proposed value.

A caller label alone cannot upgrade evidence.

### Provenance

Stable inference requires canonical, independent provenance.

Duplicate provenance must not increase support.

### Stable update output

`evaluate_level_update()` must preserve an explicit `framework` in every resulting record whose `level_or_score` is framework-dependent.

---

# 6. Invariant B — one strict cross-framework mapping record contract

A calibrated cross-framework mapping record must be **complete**.

Required fields:

```text
source_framework
source binding
target_framework
target_range
canonical source provenance
```

## Source binding choice

For final Phase 10.26 closure, use a single unambiguous representation.

Preferred design:

```text
source_value
```

with deterministic normalized equality.

Do **not** keep permissive textual `source_range` semantics unless a real structured range parser is implemented and fully property-tested.

Given Phase 10.26 scope, the recommended final choice is:

```text
source_value required for calibration
textual source_range rejected as insufficient/unsupported
```

This is deliberately narrower and safer.

## Required mapping rule

A record missing any of:

```text
source_framework
source_value
target_framework
target_range
source provenance
```

cannot produce:

```text
calibrated=True
grounded_approximate_mapping
```

Mutation of any applicability field must invalidate or materially change the result.

## Legacy contract removal

Any existing test asserting that this is sufficient:

```python
{"source_id": "...", "target_range": "B2"}
```

must be updated or removed.

The test suite must not contain simultaneous strict and permissive contracts for the same mapping.

---

# 7. Invariant C — dedicated certification source-authority provenance

Certification source authority must not reuse generic evidence-occurrence provenance.

Create one narrow internal predicate, conceptually:

```python
def _has_certification_source_authority_identity(
    source: Mapping[str, Any],
) -> bool:
    ...
```

Accept only identifiers that establish the source itself.

Recommended accepted fields:

```text
official_source_id
source_id
```

`provenance_id` may be accepted only if the existing Languages contract clearly denotes source provenance rather than an observation occurrence.

Explicitly reject as source-authority identity:

```text
session_id
sample_id
assessment_id
context_id
```

A source may still be visible without authority identity, but:

```text
caller label "official/current"
!=
fully authoritative official/current source
```

Removing source identity from an otherwise valid source must lower authority and/or require verification.

`AT-DP-026` must use a genuinely grounded source fixture and contain a mutation proving that provenance removal invalidates the authority gate.

---

# 8. Invariant D — one semantic numeric normalizer

Create/reuse a single private Languages numeric boundary for decision-driving numeric fields.

Conceptual interface:

```python
def _finite_semantic_number(
    value: Any,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    ...
```

It must reject:

```text
bool
NaN
+Inf
-Inf
non-numeric scalar
out-of-domain values
```

It must be reused for all decision-driving numeric fields touched by Phase 10.26 rules, including nested inputs such as:

```text
deadline.days_remaining
available_time
scores
mastery
recall
importance
```

No bool may become numeric evidence because `bool` subclasses `int` in Python.

---

# 9. GoalAlignment final semantics

Remove the shortcut:

```text
practice/review/lesson/exercise
-> aligned with every active goal
```

Generic pedagogical activity is not itself proof of goal relevance.

Normalize all approved activity representations:

```text
type
kind
skill
skills
goal_id
goal_ids
purpose
```

Alignment requires at least one real semantic relation:

```text
explicit goal reference
skill relevance
purpose relevance
activity-type relevance
```

Generic activity with no goal-specific semantics must remain:

```text
not specifically aligned / insufficient evidence
```

It may still be pedagogically valid; it simply cannot claim goal alignment.

---

# 10. LearningLoad final semantics

Keep the corrected semantic sensitivity for:

```text
recent_load
deadlines
review_backlog
priorities
```

All nested numeric values used to trigger changes must pass Invariant D.

Example:

```text
days_remaining=True
```

must not trigger urgent exam preparation.

Every declared “considered” input must either:

```text
change the recommendation
```

or be explicitly represented as:

```text
unsupported / insufficient / not applied
```

It must never be merely echoed while output claims it was considered.

Hard constraints remain dominant:

```text
0 <= recommended_duration <= valid available_time
calendar_modified=False
```

---

# 11. Cross-path meta-test — mandatory closure gate

Create a dedicated meta-test layer whose purpose is not another happy-path matrix, but detecting **contract divergence**.

The gate must enumerate every path that can establish or mutate:

```text
proficiency level
framework mapping
certification source authority
decision-driving numeric priority
goal alignment
```

For each concept, a common mutation must have the same semantic effect across all relevant paths.

## Required cross-path pairs

### Proficiency/framework

```text
classify_proficiency_record
evaluate_level_update
evaluate_framework_mapping
```

Mutation:

```text
matching framework -> supported
mismatched framework -> not supported
```

No path may bypass mapping.

### Certification source authority

```text
evaluate_certification_source
AT-DP-026 certification-source fixture
```

Mutation:

```text
source identity present -> authority possible
source identity removed -> authority weakened / verification required
```

### Numerics

```text
available_time
deadline.days_remaining
adaptive score
mastery
recall
importance
```

Mutation:

```text
valid number -> semantic use
True/NaN/Inf -> no semantic upgrade
```

### Goal alignment

Equivalent supported representations:

```text
type
skill
skills
purpose
explicit goal id
```

must produce coherent results.

Generic `practice` without semantic linkage must never align every goal.

---

# 12. Legacy-contract contradiction gate

Before creating the final bundle, scan the entire Languages test suite for assertions that contradict the new invariant layer.

The implementation agent must explicitly review every test containing:

```text
grounded_approximate_mapping
calibrated
authority_rank
needs_verification
stable_update_supported
aligned_goals
activity_fit
```

No test may require a behavior forbidden by this design.

Mandatory example to remove/update:

```python
mapping evidence = {
    provenance_alias: "...",
    "target_range": "B2",
}
assert calibrated is True
```

without full applicability binding.

This gate must produce an artifact:

```text
tmp/phase10-26-final-contract-consistency.txt
```

with:

```text
LEGACY_CONTRACT_CONTRADICTIONS=0
```

Only after a reviewer has inspected the matching tests.

---

# 13. Historical regression gate

The final candidate must preserve all prior fixes.

## V1

```text
generic evidence cannot become CERTIFIED
duplicate evidence cannot inflate
progression baseline/comparability
temporal authority ordering
real permission lifecycle
workflow invariant gates
```

## V2

```text
calendar external boundary
typed trace provenance
progress no cross-skill fabrication
empty assessment/writing/speaking/certification fail closed
malformed exercise numeric fail closed
```

## V3

```text
real rule execution result IDs
real permission decision IDs
selected profile mode
empty exercise unknown
vocabulary mastery grounded
```

## Rule hardening

```text
error recurrence minimum >=2
adaptive comparable/provenance checks
spaced review dedup/bounds
LearningLoad hard constraints
GoalAlignment activity sensitivity
cultural arbitrary mapping not grounded
malformed evidence collection fail closed
```

---

# 14. Adversarial mutation gate

Before final verification, actively attempt to reintroduce **every historical bypass**.

At minimum:

```text
ESTIMATED with no evidence
wrong-skill evidence
wrong-framework evidence
cross-framework level update
mapping record missing source_framework
mapping record missing source_value
mapping record missing target_framework
mapping record missing target_range
mapping record missing source provenance
minimal {source_id,target_range} mapping
textual source_range shortcut
unprovenanced official source
official source with session_id only
official source with sample_id only
official source with assessment_id only
official source with context_id only
error threshold=1
adaptive comparable=False
adaptive duplicate provenance
bool/Inf adaptive score
duplicate spaced item
negative/bool mastery
deadline days_remaining=True
generic practice aligns every goal
arbitrary cultural mapping
```

For every mutation, identify the exact test that fails.

Review result must be:

```text
Critical=0
Important=0
Minor=0
```

No bundle creation if any mutation survives.

---

# 15. Verification evidence gate

The final bundle must contain actual command output, not README claims.

Required captured logs:

```text
dedicated invariant/meta-tests
all Languages tests
connected AT-DP-026
shared rule runtime
shared trace/permission/workflow/composer/resolver regressions
all tests/domains
global pytest
Ruff
Ruff py310
compileall isolated
fresh import
canon inventory
git diff --check
Paternidad scope diff
direct markers
legacy-contract consistency scan
adversarial review
RED evidence
```

---

# 16. Required final direct markers

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

---

# 17. Completion status

After implementation and verification, documentation may say only:

```text
Epistemic-binding independent audit: FAIL
remaining findings remediated: 1 BLOCKER + 3 MAJOR
epistemic invariant consolidation: candidate PASS
AT-DP-026: candidate PASS
final independent closure audit: PENDING
DP-026: REQUIRES_PHASE_INSPECTION
```

Do not mark Phase 10.26 closed.

The implementation agent may end only with:

```text
PHASE10_26_FINAL_INVARIANT_CONSOLIDATION_STATUS:
READY_FOR_FINAL_INDEPENDENT_CLOSURE_AUDIT
```

The independent auditor alone decides closure.
