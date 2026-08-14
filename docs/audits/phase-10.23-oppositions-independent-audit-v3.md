# Phase 10.23 Opposition Domain — Independent Audit V3

Date: 2026-08-14

## Scope

Independent re-audit of the definitive Audit V2 remediation.

Candidate:

```text
branch: feature/phase-10-domain-intelligence
HEAD: f986574
commit: fix(domains): close phase 10.23 audit v2 findings
```

Evidence bundle:

```text
cmm-phase-10.23-audit-v3-evidence-20260814-113447.tar.gz
SHA-256: 2e8007b57e3db2c70815adf76ec6e15f7295208a59d748e96b66eee79c815238
```

The uploaded bundle hash matches the collector output. Its internal SHA-256 manifest was independently verified with zero mismatches.

---

# Executive verdict

**REMEDIATION REQUIRED**

The V2 remediation is materially successful and closes the large defect classes identified in Audit V2.

V3 does **not** reopen those findings.

However, independent review found three remaining Important edge-contract defects and one Minor provenance defect:

```text
Critical: 0
Important: 3
Minor: 1
Notes: 2
```

Correct current state:

```text
Phase 10.23 — Implemented, remediation required after Independent Audit V3
```

Do not mark Phase 10.23 audited/closed yet.

---

# Fresh verification evidence

The V3 collector ran from clean committed `f986574`.

All repository/test/static gates passed:

```text
pytest-v2-closure=0
pytest-oppositions=0
pytest-v3-semantic-targeted=0
pytest-domains=0
pytest-global=0
ruff-oppositions=0
ruff-oppositions-py310=0
syntax-compile-in-memory=0
fresh-import=0
git-diff-check-v2-remediation=0
```

Fresh totals:

```text
V2 closure suite: 17 passed
Opposition: 271 passed
V3 semantic targeted: 101 passed
Domains: 4797 passed
Global: 10308 passed
Ruff: PASS
Ruff py310: PASS
In-memory syntax compile: 14 modules
Fresh import: PASS
Diff check: PASS
Tracked worktree parity: PASS
```

Independent V3 hard-gate summary:

```text
TARGET_EQUIVALENCE_GATE=FAIL
CROSS_DOMAIN_COMPOSITION_GATE=PASS
SYLLABUS_NORMALIZATION_GATE=PASS
MOCK_NORMALIZATION_GATE=PASS
ALTERNATIVE_NORMALIZATION_GATE=PASS
RULE_PARITY_GATE=FAIL
STRICT_JSON_GATE=PASS
INPUT_NON_MUTATION_GATE=PASS
NO_EXCEPTION_TYPE_MATRIX_GATE=PASS
ALL_HARD_GATES_PASS=false
```

One of those two FAILs is a **collector false positive** and is explicitly dismissed below.

---

# V3 closure assessment of Audit V2 findings

## V2-I1 — Target-date fail-closed behavior

**Status: FIXED.**

V3 exercised:

```text
None
text
bool
negative
float
NaN
infinity
zero
positive
zero remaining work
```

For positive work:

- malformed target → unresolved, not feasible;
- missing target → unresolved, not feasible;
- zero target → infeasible;
- valid target → normal feasibility.

For zero remaining work, missing target does not create a false unresolved state.

### Collector false positive

`TARGET_EQUIVALENCE_GATE=FAIL` is not a product defect.

The V3 probe incorrectly required:

```text
target_date_invalid=True
```

for the `target_days=None` case.

But the intended semantic distinction is:

```text
None → missing
malformed supplied value → invalid
```

The implementation correctly returns for missing target:

```text
feasible=False
unresolved=True
target_date_invalid=False
```

This is the correct absent-vs-malformed distinction and matches the definitive remediation contract.

**No V3 finding.**

---

## V2-I2 — Syllabus per-identity normalization

**Core helper normalization: FIXED.**

V3 independently confirmed:

- exact duplicate identities do not double-count depth;
- review-due and mock-linked dimensions do not inflate under exact duplicates;
- compatible partial evidence merges deterministically;
- conflicting depth is preserved as conflict;
- all tested permutations produce the same normalized helper result;
- conflicting topics do not establish completion.

A remaining canonical Rule propagation defect is recorded separately as V3-I1.

---

## V2-I3 — Mock chronology / JSON safety

**Core chronology/JSON remediation: FIXED.**

V3 confirmed:

- mixed date-only / `Z` / timezone-offset chronology does not raise;
- public helper results are strict JSON-safe;
- denominator mismatch does not establish a raw-score trend;
- conflict timelines are deterministic and JSON-safe.

A remaining strict temporal-order edge case is recorded separately as V3-I2.

---

## V2-I4 — Mock duplicate identity conflict

**FIXED.**

V3 independently confirmed:

- conflicting mock identity is represented explicitly;
- no arbitrary first observation becomes authoritative;
- full helper result is permutation-invariant for the audited conflict set;
- conflict reaches `MockExamInterpretationRule` metadata;
- conflict produces WARNING severity;
- conflicting identity does not participate in trend inference.

---

## V2-I5 — Alternative duplicate identity conflict

**FIXED for duplicate conflict semantics.**

V3 confirmed:

- exact duplicates do not become conflicts;
- conflicting duplicates are order-invariant;
- conflicting route IDs remain explicit;
- `resolved=False`;
- definitive recommendation is suppressed;
- canonical `AlternativeRouteRule` preserves duplicate conflict.

A separate unknown/conditional-requirement resolution bug is recorded as V3-I3.

---

## V2-I6 — University malformed constraint

**FIXED.**

Malformed authorized University workload/availability is fail-closed and does not establish normal feasibility.

---

## V2-M1 — Health binding provenance

**Health-specific case fixed.**

A wider/equal Health cap no longer claims to be the binding source.

V3 found a neighboring University/composite provenance issue, recorded as V3-M1.

---

## V2-M2 — Documentation/comment reconciliation

**FIXED.**

No blocking namespace/documentation defect was found in the V2 remediation surface.

---

# V3 findings

## V3-I1 — Important — Syllabus conflict is still not preserved explicitly through canonical `SyllabusCoverageRule`

### Requirement

Phase 10 presentation must preserve:

```text
uncertainty
contradictions
information gaps
coverage dimensions
```

and must not hide unresolved conflict.

The definitive V2 remediation also required helper → Rule parity for conflict states.

### Helper behavior

The helper correctly returns structured conflict information:

```text
conflicting_count
conflicting_topics
conflict_blocks_complete
dimensions.conflicting
```

### Canonical Rule behavior

`SyllabusCoverageRule.evaluate(...)` currently emits finding metadata containing:

```python
{
    "complete": ...,
    "studied_count": ...,
    "pending_count": ...,
    "unknown_count": ...,
    "forgetting_proven": False,
    "review_cue": ...,
    "dimensions": ...,
}
```

It does **not** propagate:

```text
conflicting_count
conflicting_topics
conflict_blocks_complete
```

Its human-facing message for every incomplete state is:

```text
"Syllabus coverage is not complete
(pending/unknown topics or unresolved syllabus version)."
```

Conflict is not named.

### Independent V3 evidence

The helper→Rule probe supplied two incompatible records for the same topic identity.

The Rule finding was WARNING and `complete=False`, but its metadata had no explicit `conflicting_count` / `conflicting_topics`.

The V3 `RULE_PARITY_GATE` therefore failed.

The existing closure test named:

```text
test_syllabus_coverage_rule_preserves_conflict
```

only asserts:

```text
complete is False
severity is WARNING
```

It does not prove that the contradiction itself survives the canonical Rule boundary.

### Why this matters

`pending`, `unknown`, `outdated version`, and `conflicting evidence` are semantically distinct Phase 10 states.

Converting all of them into a generic incomplete result loses the exact reason downstream and weakens presentation/traceability.

### Required remediation

Propagate structured conflict metadata through `SyllabusCoverageRule`, at minimum:

```text
conflicting_count
conflicting_topics
conflict_blocks_complete
```

The message must distinguish a conflict from ordinary pending/unknown coverage.

Add a canonical Rule regression that asserts the actual conflict fields, not merely WARNING.

---

## V3-I2 — Important — Equal timestamps can establish a directional mock trend without temporal ordering

### Requirement

Frozen design:

```text
Multiple mocks establish a trend only when enough evidence is comparable
and temporally ordered.
```

Comparability explicitly requires:

```text
valid chronology
```

Unknown chronology must not produce a temporal trend.

### Current implementation

Comparable observations are sorted by:

```python
entry["parsed_date"]
```

and when at least two exist:

```python
trend_state = "trend"
trend_inferred = True
trend_slope = ordered[-1]["score"] - ordered[0]["score"]
```

There is no requirement that chronological positions are **strictly distinct**.

### Independent V3 reproduction

Two observations:

```text
2027-04-01T00:00:00Z
2027-04-01T02:00:00+02:00
```

represent the exact same instant.

Normalized output confirms both:

```text
parsed_date = 1806537600.0
```

Yet the helper returns:

```text
trend_inferred = true
trend_slope = 1
trend_state = "trend"
```

The apparent direction therefore comes from deterministic record ordering, not temporal progression.

The same class also affects two date-only mocks on the same date: no before/after relation exists inside that date.

### Expected

Equal chronology does not establish direction.

A directional trend requires at least two strictly ordered temporal points.

If multiple observations occupy the same normalized time and differ materially, they must not be used to manufacture an earlier→later slope.

### Required remediation

Normalize trend evidence by chronological instant before directional inference.

At minimum:

```text
< 2 distinct normalized timestamps
→ no temporal trend
```

For repeated timestamp observations, define a conservative deterministic policy:

- compatible identical point → deduplicate/aggregate safely;
- incompatible scores at same instant → chronology/evidence conflict or no trend.

Add regressions for:

```text
same instant via Z vs offset
same date-only value
same instant with different IDs/scores
three mocks where two share the first timestamp
```

---

## V3-I3 — Important — Conditional/unknown alternative requirements are recorded but comparison still reports `resolved=True`

### Requirement

Frozen Error / Unknown-State Policy:

```text
unknown route requirement
→ comparison remains conditional
```

Alternative Route Tests also require:

```text
missing official requirements leave affected comparison conditional
```

### Current implementation

For a missing eligibility value:

```python
if eligibility_known is None:
    conditional_requirements.append(route_id)
```

But final resolution is:

```python
resolved = not malformed_route_member and not has_conflict
```

`conditional_requirements` does not participate.

Therefore a comparison may return simultaneously:

```text
conditional_requirements = ("alt1",)
resolved = True
```

The canonical Rule then uses `resolved=True` to emit an INFO "compared" result rather than an unresolved/conditional WARNING.

### Existing test weakness

The existing test:

```text
test_missing_official_requirements_leave_comparison_conditional
```

asserts only:

```python
"alt1" in result["conditional_requirements"]
```

It never asserts:

```python
result["resolved"] is False
```

### Additional state-normalization issue

Any non-empty eligibility string is treated as known by `_usable_scalar_string`.

Thus explicit states such as:

```text
"unknown"
"conditional"
```

do not enter `conditional_requirements`.

V3 diagnostics demonstrated:

```text
eligibility="conditional"
conditional_requirements=[]
resolved=True
recommendation=None
```

This is not a cleanly resolved comparison.

### Expected

At minimum:

```text
conditional_requirements non-empty
→ resolved=False
```

Normalize eligibility into a conservative closed semantic set.

Conceptually:

```text
eligible
ineligible
unknown/conditional/missing
```

Unknown/conditional/missing requirements must remain conditional and block a definitive route-comparison resolution.

Do not silently reinterpret arbitrary non-empty strings as a known ineligible state.

Canonical `AlternativeRouteRule` must emit unresolved/conditional semantics when such requirements exist.

### Stale diagnostic

V3 also observed that a stale route may still be recommended while `stale_route_ids` remains explicit.

This is **not promoted to a V3 blocker** because the frozen test contract explicitly requires stale state preservation but does not unambiguously state that every stale route must suppress a proposal-level recommendation.

The stale state is currently visible through helper and Rule metadata, so V3 does not invent a stronger contract here.

---

# Minor finding

## V3-M1 — University/composite capacity provenance is still inaccurate

### Current behavior

`capacity_source` is updated when Health becomes binding.

University availability/workload can then further reduce capacity, but `capacity_source` is not updated.

Examples from the V3 composition surface:

```text
user capacity = 8
Health cap = 20
University availability = 10
University workload = 2
→ effective capacity = 6
→ capacity_source remains "user"
```

or:

```text
user = 11
Health = 8
University availability = 7
University workload = 2
→ effective capacity = 5
→ capacity_source may remain "health"
```

The numeric capacity is correctly restrictive; only provenance is inaccurate.

### Impact

No permission/certainty widening was found, so this is non-blocking.

It weakens traceability of the effective feasibility constraint.

### Required remediation

When University availability/workload materially determines the final capacity, expose correct provenance.

If one scalar source is insufficient for composed constraints, use a backward-compatible structured source representation or a deterministic composite label consistent with existing public contracts.

---

# V3 notes

## V3-N1 — The target hard-gate FAIL is a probe bug

Do not change production merely to make `target_days=None` report `target_date_invalid=True`.

The correct distinction is:

```text
missing != malformed
```

The implementation currently preserves that distinction while still failing closed.

## V3-N2 — Stale alternative recommendation is not a blocking finding

The diagnostic is worth retaining for future semantics, but the frozen Phase 10.23 contract does not clearly require proposal suppression solely because `call_state="stale"`.

Current code preserves:

```text
stale_route_ids
target_unchanged
proposal_only
```

Therefore no V3 blocking finding is issued on that point.

---

# Findings total

```text
Critical: 0
Important: 3
Minor: 1
Notes: 2
```

Blocking:

```text
V3-I1 syllabus conflict lost at canonical Rule boundary
V3-I2 equal-time mocks can manufacture a directional trend
V3-I3 conditional/unknown alternative requirements still appear resolved
```

Non-blocking remediation:

```text
V3-M1 University/composite capacity provenance
```

---

# Why V3 is much narrower than V1/V2

The following hardening classes now survived independent V3 variation:

```text
target malformed/missing fail-closed behavior
strict bool authorization
Health most-restrictive cap
University malformed workload
cross-domain composition numeric result
syllabus per-identity aggregation
syllabus depth conflict
syllabus full helper permutation invariance
mixed timezone chronology
strict JSON public output
mock duplicate conflict
mock full helper permutation invariance
alternative duplicate conflict
alternative helper permutation invariance
input non-mutation
primitive/type no-exception matrix
Opposition full suite
Domains full suite
Global full suite
Ruff / py310
fresh import
repository parity
```

The remaining defects are not another broad architecture failure. They are three missing edge conditions at already-defined boundaries.

---

# Required final remediation scope

Keep the next remediation extremely small.

Expected production changes:

```text
cmm/domains/oppositions/rules.py
```

Documentation/audit status updates as usual.

No shared infrastructure change is justified.

Required permanent regressions:

```text
1. SyllabusCoverageRule exposes conflicting_count/topics
2. SyllabusCoverageRule message distinguishes conflict
3. same normalized mock timestamp cannot establish directional trend
4. same date-only mock timestamp cannot establish directional trend
5. equal-time score disagreement cannot create slope
6. conditional_requirements => resolved=False
7. eligibility="unknown"/"conditional" stays conditional
8. AlternativeRouteRule preserves conditional unresolved state
9. University/composite capacity provenance is truthful
```

After those tests and focused RED→GREEN cycles, rerun the existing permanent V2 closure suite plus full Opposition/Domain/Global verification.

---

# Final verdict

**REMEDIATION REQUIRED**

Do not reopen or redesign the Phase 10.23 architecture.

Do not touch already-closed V2 behavior without a regression proving necessity.

The next pass should be a surgical final remediation of:

```text
V3-I1
V3-I2
V3-I3
V3-M1
```

followed by one final independent closure audit.
