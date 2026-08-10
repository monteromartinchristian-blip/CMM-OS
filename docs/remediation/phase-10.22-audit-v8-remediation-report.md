# Phase 10.22 Audit V8 To V9 Remediation Report

Roadmap: Implemented, pending audit

The governing invariant for this remediation is:

```text
absent != valid empty != malformed
```

Malformed collection evidence is never coerced into an empty collection when
that coercion would permit a strong conclusion.

## V8-B1: Malformed collection epistemic preservation - FIXED

Root cause: collection-shaped metadata such as `prerequisites`, `attempts`,
`records`, `hard_constraints`, `preferences`, `scenarios`,
`double_counted` and `contradictory` were normalized through `_seq(...) or ()`,
so a malformed scalar or mapping disappeared into an empty tuple. An empty
tuple can justify a strong conclusion such as "no prerequisites", "no
attempts", "no constraints" or "no conflicts".

Production change: added private `_CollectionEvidence` and
`_normalize_collection` in `cmm/domains/university/rules.py`. The result keeps
`items`, `present` and `malformed` state. Canonical rules now pass malformed
flags into their private evaluators and emit conservative uncertainty/blocked
findings instead of rewriting malformed evidence as an empty collection.

Canonical RED test examples:

- `prerequisites=7` must produce `DEPENDENCY_BLOCKED`, never
  `DEPENDENCY_SATISFIED`.
- `attempts=7` with a valid regulation must produce
  `attempt_evidence_unknown=True` and `within_limits=False`, never
  `EXAM_ATTEMPT_EVALUATED`.
- Fully grounded otherwise-complete ECTS with `double_counted=7` or
  `contradictory=7` must not confirm completion.
- Malformed `academic_records` cannot establish a credit prerequisite.

GREEN behavior:

- `prerequisites=[]` remains legitimate empty prerequisite semantics.
- `attempts=[]` remains valid zero-attempt evidence.
- `hard_constraints=[]` remains feasible when no constraint is violated.
- Malformed ECTS conflict metadata is reported and blocks completion.

## V8-B2: Nested Workload collection safety - FIXED

Root cause: `_evaluate_structured_workload` attempted to iterate
`scenario.get("hard_constraints")` even when the key was absent and returned
`None`, leaking `TypeError`. A malformed nested value was also treated as
missing rather than as unresolved constraint evidence.

Production change: the nested workload evaluator now checks whether
`hard_constraints` is present before iterating. A present but malformed nested
collection is tracked as unresolved and never certifies the scenario as
definitely feasible. Top-level `hard_constraints`, `preferences` and
`scenarios` malformed state is propagated into the compatibility helpers and
forced to feasibility uncertainty with no proposal.

Canonical RED test examples:

- `scenario.hard_constraints=7` must not raise `TypeError`.
- The affected scenario must appear in `unresolved_scenarios`, not in
  `feasible_scenarios`.
- `selected_scenario` pointing at that scenario must not produce a proposal.
- Top-level `hard_constraints=7`, `preferences=7` and `scenarios=7` must
  preserve uncertainty.

GREEN behavior:

- A scenario without a `hard_constraints` key continues to evaluate normally.
- `hard_constraints=[]` remains valid absence of nested constraints and does
  not make a feasible workload uncertain.

## V8-B3: Integrity finding-code consistency - FIXED

Root cause: `AcademicIntegrityRule` emitted `INTEGRITY_RESTRICTION_APPLIED`
whenever `restriction_grounded` was true, even when exact scope matching made
`restriction_applies=False`.

Production change: the finding code is now selected from
`resolved["restriction_applies"]`, so `INTEGRITY_RESTRICTION_APPLIED` is
emitted only when the grounded restriction actually applies.

Canonical RED test examples:

- `restriction_grounded=True` with missing current course, wrong current
  course, or missing current assessment must not produce
  `INTEGRITY_RESTRICTION_APPLIED`.
- Exact matching scope plus prohibited action still produces
  `INTEGRITY_RESTRICTION_APPLIED`.

GREEN behavior:

- Non-applying grounded restrictions produce `INTEGRITY_MODE_PRESERVED` with
  `restriction_applies=False`.
- Applying grounded restrictions preserve source class, temporal state and
  source reference in the finding.

## Verification

Focal and full verification passed:

```text
tests/domains/test_university_domain_*.py: 445 passed
tests/domains: 4003 passed
full suite: 9514 passed
```

Ruff, compileall, dependency direction and fresh import all passed.

## Canonical counts

```text
entities   = 14
resources  = 12
rules      = 10
operations = 11
workflows  = 7
```
