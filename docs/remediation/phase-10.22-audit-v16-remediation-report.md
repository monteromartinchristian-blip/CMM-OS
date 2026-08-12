# Phase 10.22 University Domain — Audit V16 Remediation Report

**Date:** 2026-08-12

**Branch:** `feature/phase-10-domain-intelligence`

**HEAD:** `f82f702 fix(domains): close phase 10.22 audit v15 findings`

**Status:** `Implemented, pending audit`

This remediation closes only the two blocking clusters reported by Independent
Audit V16. It does not declare Phase 10.22 complete; Independent Audit V17
decides closure.

## Preflight and baseline

Preflight confirmed the expected branch and HEAD, no tracked or staged changes,
and only the pre-existing untracked Independent Audit report and audit archives.
No pre-existing artifact was modified.

Baseline commands and actual results:

```text
.venv/bin/python -m pytest -q tests/domains/test_university_domain_*.py
765 passed in 2.06s

.venv/bin/python -m pytest -q tests/domains
4323 passed in 6.56s
```

## TDD evidence

Tests were written and run before any production edit. The shared V17 RED
command was:

```text
.venv/bin/python -m pytest -q \
  tests/domains/test_university_domain_source_authority.py \
  tests/domains/test_university_domain_integrity.py \
  tests/domains/test_university_domain_ects.py -k v17
```

Actual RED:

```text
64 failed, 12 passed, 197 deselected in 1.17s
```

The failures demonstrated both root causes: nested reference members were
recursively accepted as scalar references, malformed policy members were not
preserved as malformed, and caller values such as `"false"`, `"true"`, and `1`
activated ECTS critical uncertainty through Python truthiness.

After the production fix, the same selector passed. The matrix was then
strengthened with blank and mixed valid-plus-malformed members; the final V17
selector result is:

```text
86 passed, 197 deselected in 0.86s
```

## V16-B1 — strict plural-member validation

### Root cause

`_normalize_references()` correctly accepted list/tuple outer containers, but
used `_usable_reference()` for each member. That singular compatibility helper
recursively unwrapped a nested list/tuple, making `[["ref"]]` semantically
equivalent to `["ref"]`. Invalid members were also dropped without preserving
that an explicit collection was malformed.

### Production fix

A local `_ReferenceCollectionEvidence` carries both normalized `items` and a
`malformed` flag. `_normalize_references()` now:

- accepts flat list/tuple containers and the existing scalar-string singleton;
- validates every member with strict scalar-string semantics;
- marks nested collections, blank strings, numbers, booleans, mappings, and
  `None` members malformed;
- preserves valid order and de-duplication;
- preserves malformed state even when another member is valid.

Source Authority discards the entire supersession relation when any member is
malformed, exposes field-specific malformed diagnostics, and therefore leaves
equal-authority conflicts unresolved. Academic Integrity exposes
`restriction_policy_malformed` and prevents malformed policy evidence from
applying a Mode C restriction. Canonical findings preserve these diagnostics.

### Complete `_normalize_references()` caller audit

| Caller | Field | Valid flat semantics | Malformed-member semantics |
|---|---|---|---|
| `classify_academic_source_authority()` | `supersedes` | Flat list/tuple can establish a validated replacement relation. | Entire relation is unusable; malformed flag is retained; it cannot demote a candidate or resolve a conflict. |
| `classify_academic_source_authority()` | `superseded_by` | Flat list/tuple can establish the inverse validated replacement relation. | Entire relation is unusable; malformed flag is retained; it cannot establish precedence. |
| `evaluate_academic_integrity()` | `superseded_by` | Empty means current; a non-empty valid collection blocks the superseded restriction. | Treated as uncertain/blocking and marks the policy malformed; it cannot apply a restriction. |
| `evaluate_academic_integrity()` | `scope` | Flat list/tuple is retained as diagnostic policy scope. | Marks scope/policy unresolved and cannot create a matched restriction. |
| `evaluate_academic_integrity()` | `prohibited_actions` | Requested action in a valid flat collection can apply a fully grounded restriction. | Cannot authorize restriction application; Mode C remains permissive. |
| `evaluate_academic_integrity()` | `allowed_actions` | Requested action in a valid flat collection exempts it from restriction. | Cannot silently become absent and make policy more restrictive; Mode C remains permissive. |

There are no other production callers of `_normalize_references()`.

### Coverage and positive controls

Direct-helper and canonical-rule tests cover nested lists and tuples for all six
fields. The public helper matrices additionally cover blank strings, `7`,
`True`, `None`, mappings, empty nested lists/tuples, and mixed valid plus
malformed members. Flat list and tuple controls remain valid for Source
Authority and all four Integrity fields.

## V16-B2 — strict ECTS boolean semantics

### Root cause

Both the canonical adapter and base helper allowed Python truthiness to classify
the caller-controlled `critical_requirement_uncertain` field. Consequently,
truthy non-booleans became literal uncertainty.

### Production fix

The canonical adapter and the base composition now use the established
`_boolean_true()` contract. Only the boolean singleton `True` activates the
caller-provided uncertainty flag; strings and numeric/container values are not
parsed or coerced. Independently derived uncertainty (missing/ungrounded
requirements, malformed numeric evidence, or unknown records) remains intact.

### Boolean-bearing field audit

| Field/category | Raw caller coercion before? | Post-fix contract |
|---|---:|---|
| ECTS `critical_requirement_uncertain` | Yes, canonical and base composition | Literal `True` only via `_boolean_true()` |
| Integrity `ai_forbidden`, `superseded`, `ambiguous`, remembered restriction | No | Existing literal-`True` handling retained; malformed trust flags remain conservative. |
| Deadline/claim critical flags and verification `decision_critical` | No | Existing `_boolean_true()` handling retained. |
| Remaining `bool(...)` calls | No equivalent residual found | They operate on internal/derived collections, numeric comparisons, normalized strings, or already-classified booleans; no unrelated refactor made. |

Direct and canonical matrices cover `True`, `False`, `"false"`, `"true"`, `1`,
`0`, `[]`, `{}`, and `None`. Only literal `True` blocks the fully grounded 6/6
ECTS case.

## Contract invariants

```text
valid plural container != valid nested member
nested collection member != scalar reference
malformed member != absent member
truthy != boolean True
no implicit coercion
base helper safety == adapter safety == canonical wrapper safety
malformed evidence never expands epistemic or policy reach
```

## Final verification

All results below are fresh after the last production/test change:

| Verification | Result |
|---|---|
| V17 adversarial selector | `86 passed, 197 deselected in 0.86s` |
| Focal Source Authority + Integrity + ECTS | `283 passed in 0.83s` |
| Full University | `851 passed in 3.31s` |
| Domains | `4409 passed in 8.52s` |
| Global | `9920 passed in 34.00s` |
| Ruff | `All checks passed!` |
| Ruff, Python 3.10 target | `All checks passed!` |
| `compileall` | exit 0 |
| Dependency direction | `1 passed in 0.53s` |
| Fresh import | `fresh_import=OK` |
| Placeholder scan | no matches |
| `git diff --check` | clean |
| `git diff --cached --check` | clean |

Canonical counts were measured as:

```text
entities=14
resources=12
rules=10
operations=11
workflows=7
```

## Regression self-audit

```text
V16-B1 nested members fixed: YES
V16-B2 ECTS boolean fixed: YES

V15 singular scalar/reference family remains closed: YES
V15 Source Authority relation-unknown remains closed: YES

V14 source identity remains strict: YES
V14 claim identity remains strict: YES
V14 Deadline classifier remains strict: YES
V14 Performance remains strict: YES

V13 regressions remain closed: YES
V12 regressions remain closed: YES
V11 regressions remain closed: YES
V10 regressions remain closed: YES
V9 regressions remain closed: YES

canonical counts remain 14/12/10/11/7: YES
permission architecture untouched: YES
roadmap remains Implemented, pending audit: YES
public helpers remain exception-safe: YES
```

Only `cmm/domains/university/rules.py`, the three affected test owners, and this
remediation report are in remediation scope. Permission, catalog, operations,
workflows, other domains, canonical counts, and roadmap content are untouched.
The pre-existing untracked Independent Audit V16 report is not part of this
remediation.

No files were staged. No commit was created. No push was performed. Graphify was
not run.

## Recommendation

READY FOR INDEPENDENT AUDIT V17
