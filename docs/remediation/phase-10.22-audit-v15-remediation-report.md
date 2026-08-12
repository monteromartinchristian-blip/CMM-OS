# Phase 10.22 University Domain — Audit V15 Remediation Report

**Date:** 2026-08-12
**Branch:** `feature/phase-10-domain-intelligence`
**HEAD:** `b35ecd8 fix(domains): close phase 10.22 audit v14 findings`
**Status:** `Implemented, pending audit`
**Decision owner:** Independent Audit V16

Phase 10.22 is not declared complete by this remediation.

## Scope

Production changed only in:

- `cmm/domains/university/rules.py`

Affected existing test owners:

- `tests/domains/test_university_domain_ects.py`
- `tests/domains/test_university_domain_exam_attempts.py`
- `tests/domains/test_university_domain_dependencies.py`
- `tests/domains/test_university_domain_integrity.py`
- `tests/domains/test_university_domain_workload.py`
- `tests/domains/test_university_domain_deadlines.py`
- `tests/domains/test_university_domain_source_authority.py`
- `tests/domains/test_university_domain_contradiction.py`

The contradiction owner was included because its canonical finding-reference
construction was one of the wrappers capable of re-coercing a malformed claim
ID. No permission, operation, workflow, catalog, other-domain, or roadmap file
was changed.

## Preflight and baselines

Preflight matched the required state:

```text
branch = feature/phase-10-domain-intelligence
HEAD = b35ecd8
tracked changes = none
staged changes = none
git diff --check = clean
git diff --cached --check = clean
```

Baseline commands and actual results:

```bash
.venv/bin/python -m pytest -q tests/domains/test_university_domain_*.py
# 700 passed in 2.26s

.venv/bin/python -m pytest -q tests/domains
# 4258 passed in 7.16s
```

The pre-existing untracked Independent Audit V15 report and audit tarballs were
not touched.

## V15-B1 — Transversal strict singular scalar/reference enforcement

### Root cause

`_usable_scalar_string()` and `_scalar_reference_from()` already existed, but
singular identity/reference/value call-sites still used `_usable_reference()`
or `_reference_from()`. Those plural helpers recursively unwrap list/tuple
members, so `['x']` and `('x',)` could become `'x'`.

Two secondary manifestations of the same cause were also confirmed:

- an Exam attempt that failed complete-evidence validation was counted as only
  ungrounded, allowing `attempt_evidence_unknown=False`;
- an Integrity collection-shaped course/assessment scope could collapse to an
  absent/global scope instead of remaining malformed.

### RED evidence

Tests were written before any production edit. The full V16 selector was then
run:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_university_domain_ects.py \
  tests/domains/test_university_domain_exam_attempts.py \
  tests/domains/test_university_domain_dependencies.py \
  tests/domains/test_university_domain_integrity.py \
  tests/domains/test_university_domain_workload.py \
  tests/domains/test_university_domain_deadlines.py \
  tests/domains/test_university_domain_source_authority.py \
  tests/domains/test_university_domain_contradiction.py \
  -k v16
```

Actual RED:

```text
54 failed, 11 passed, 436 deselected in 1.50s
```

Representative actual failures:

```text
ECTS recognized_total: assert 6 == 0
Canonical ECTS: ECTS_REQUIREMENT_SATISFIED != ECTS_COMPLETION_BLOCKED
Exam regulation_unknown: assert False is True
Exam attempt_evidence_unknown: assert False is True
Dependency satisfied_prerequisites: ('pre1',) != ()
Integrity restriction_applies: assert True is False
Workload scenarios_malformed: assert False is True
Public deadline deadline_present: assert True is False
Deadline wrapper references: ('d1',) != ()
Source Authority wrapper references: ('junk',) != ()
Contradiction wrapper references: ('junk',) != ()
```

The initial Integrity assessment fixture used the course value and therefore
did not exercise an assessment match. It was corrected while production was
still untouched, then independently observed RED:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_university_domain_integrity.py \
  -k 'v16_integrity_scope_collection_never_matches'
```

```text
4 failed, 43 deselected in 1.62s
restriction_applies: assert True is False
```

### Production change

- Migrated every singular call-site to `_usable_scalar_string()` or
  `_scalar_reference_from()`.
- Kept `_usable_reference()` semantics unchanged for plural reference
  normalization.
- Made `_scalar_reference_from()` validate the first present ordered alias.
  A present-but-malformed primary field now fails closed rather than falling
  through to a lower-priority alias.
- Classified incomplete canonical Exam attempt evidence as unknown.
- Distinguished malformed Integrity course/assessment scope from absent/global
  scope.
- Migrated canonical finding/reference construction so wrappers cannot
  reintroduce a scalar rejected by the base helper.

### GREEN evidence

The first implementation run exposed a syntax error in a newly split Workload
condition; after the minimal syntax correction, five behavioral cases remained
RED (regulation alias fallback and assessment scope overwrite). Those were
traced to the two causes described above. Final adversarial GREEN:

```text
65 passed, 436 deselected in 0.85s
```

The V16 matrix covers:

- public deadline list/tuple and malformed runtime inputs;
- ECTS record identities, record source references, requirement source
  references, and canonical completion;
- Exam regulation references, all four required attempt scalar fields, and the
  canonical rule;
- Dependency record identities, record source references, dependency IDs, and
  the canonical rule;
- Integrity restriction reference, course/assessment scope, and canonical
  wrapper metadata/references;
- Workload scenario ID, preference dimension, constraint ID exposure, and the
  canonical rule;
- Source Authority and Contradiction canonical wrapper references.

## Complete singular-versus-plural call-site audit

The following table records every production call-site found by the required
`rg` inventory. Repeated rows are intentional: each is a distinct call-site or
consumer role.

| Call-site | Field | Classification | Helper after remediation |
|---|---|---|---|
| `_usable_reference` recursive sequence walk | member of plural list/tuple | plural | `_usable_reference` retained |
| `_reference_from` internal extraction | plural-compatible reference value; no remaining production consumer | plural | `_usable_reference` retained |
| `_scalar_reference_from` internal extraction | first present ordered alias | singular | `_usable_scalar_string` |
| `_normalize_references` element normalization | plural reference collection member | plural | `_usable_reference` retained |
| `classify_academic_source_authority` evaluated source | `source_id` | singular | `_usable_scalar_string` (pre-existing strict call-site) |
| `classify_academic_source_authority` unusable identity guard | `source_id` | singular | `_usable_scalar_string` (pre-existing strict call-site) |
| `classify_academic_source_authority` corroborated IDs | `source_id` | singular | `_usable_scalar_string` (pre-existing strict call-site) |
| `classify_academic_source_authority` winner supporting ID | `source_id` | singular | `_usable_scalar_string` (pre-existing strict call-site) |
| `_claim_source` authority descriptor | claim `id` | singular | `_usable_scalar_string` (pre-existing strict call-site) |
| `_claim_sort_key` deterministic identity | claim `id` | singular | `_usable_scalar_string` (pre-existing strict call-site) |
| `resolve_academic_conflict` unusable identity guard | claim `id` | singular | `_usable_scalar_string` (pre-existing strict call-site) |
| `check_ects_consistency` record identity | `subject_id` / `credit_id` / `id` | singular ordered aliases | `_scalar_reference_from` |
| `check_ects_consistency` record grounding | `source_reference` / `source_ref` | singular ordered aliases | `_scalar_reference_from` |
| `check_ects_consistency` degree requirement | `source_reference` / `source_ref` | singular ordered aliases | `_scalar_reference_from` |
| `evaluate_exam_attempt` regulation identity | `source_reference` / `source_ref` / `id` | singular ordered aliases | `_scalar_reference_from` |
| `evaluate_exam_attempt` complete evidence | `id` | singular | `_usable_scalar_string` |
| `evaluate_exam_attempt` complete evidence | `exam_id` | singular | `_usable_scalar_string` |
| `evaluate_exam_attempt` complete evidence | `date` | singular | `_usable_scalar_string` |
| `evaluate_exam_attempt` complete evidence | `source_reference` | singular | `_usable_scalar_string` |
| `_evaluate_structured_workload` scenario filter | scenario `id` | singular | `_usable_scalar_string` |
| `_evaluate_structured_workload` malformed scenario detection | scenario `id` | singular | `_usable_scalar_string` |
| `_evaluate_structured_workload` malformed preference detection | preference `dimension` | singular | `_usable_scalar_string` |
| `_evaluate_structured_workload` scenario evaluation | scenario `id` | singular | `_usable_scalar_string` |
| `_evaluate_structured_workload` constraint reference collection | constraint `id` | singular | `_usable_scalar_string` |
| `_evaluate_structured_workload` explicit preference filter | preference `dimension` | singular | `_usable_scalar_string` |
| `_evaluate_structured_workload` feasible ranking filter | scenario `id` | singular | `_usable_scalar_string` |
| `_evaluate_structured_workload` ranking output | scenario `id` | singular | `_usable_scalar_string` |
| `_evaluate_structured_workload` scenario output | scenario `id` | singular | `_usable_scalar_string` |
| `evaluate_academic_workload` legacy hard constraint references | hard constraint `id` | singular | `_usable_scalar_string` |
| `_resolve_dependency_credit_evidence` record identity | `subject_id` / `credit_id` / `id` | singular ordered aliases | `_scalar_reference_from` |
| `_resolve_dependency_credit_evidence` record grounding | `source_reference` / `source_ref` | singular ordered aliases | `_scalar_reference_from` |
| `evaluate_academic_dependency` record index | `subject_id` / `credit_id` / `id` | singular ordered aliases | `_scalar_reference_from` |
| `evaluate_academic_dependency` structured prerequisite | dependency `id` | singular | `_usable_scalar_string` |
| `evaluate_academic_dependency` embedded record grounding | `source_reference` / `source_ref` | singular ordered aliases | `_scalar_reference_from` |
| `evaluate_academic_dependency` legacy prerequisite | dependency `id` | singular | `_usable_scalar_string` |
| `evaluate_academic_integrity` restriction grounding | `source_reference` / `source_ref` | singular ordered aliases | `_scalar_reference_from` |
| `evaluate_academic_integrity` exact course scope | `course` | singular | `_usable_scalar_string` plus malformed-state check |
| `evaluate_academic_integrity` exact assessment scope | `assessment` | singular | `_usable_scalar_string` plus malformed-state check |
| `evaluate_deadline` public adapter | `deadline` | singular | `_usable_scalar_string` |
| `evaluate_observed_performance` observation reference | `ref` | singular | `_usable_scalar_string` (pre-existing strict call-site) |
| `evaluate_observed_performance` observation result | `outcome` | singular | `_usable_scalar_string` (pre-existing strict call-site) |
| `classify_deadline_grounding` deadline value | `value` | singular | `_usable_scalar_string` (pre-existing strict call-site) |
| `classify_deadline_grounding` source grounding | `source_reference` / `source_ref` | singular ordered aliases | `_scalar_reference_from` (pre-existing strict call-site) |
| `classify_deadline_grounding` retrieval metadata | `retrieval_date` | singular | `_usable_scalar_string` |
| `classify_deadline_grounding` effective metadata | `effective_date` | singular | `_usable_scalar_string` |
| `AcademicSourceAuthorityRule` authoritative claim lookup | claim `id` | singular | `_usable_scalar_string` |
| `AcademicSourceAuthorityRule` finding references | claim `id` | singular | `_usable_scalar_string` |
| `AcademicSourceAuthorityRule` historical references | claim `id` | singular | `_usable_scalar_string` |
| `AcademicContradictionRule` finding references | statement `id` | singular | `_usable_scalar_string` |
| `AcademicDeadlineRule` finding references | `source_reference` / `source_ref` | singular ordered aliases | `_scalar_reference_from` |
| `AcademicIntegrityRule` finding metadata/references | `source_reference` / `source_ref` | singular ordered aliases | `_scalar_reference_from` |

Post-remediation inventory:

```text
_usable_reference call-sites outside helper internals:
  _normalize_references only — intentionally plural

_reference_from call-sites:
  none
```

The `_usable_reference` and `_reference_from` definitions remain available with
their plural-compatible semantics; they are not used by any singular University
call-site.

## V15-B2 — Complete relation-unknown classification

### Root cause

The base Source Authority resolver used:

```text
relationship == "unknown" AND inline value is present
```

This allowed supplied authority-only or identity-only evidence with no known
attribute carrier to disappear while a valid grade source resolved confidently.
Relationship state is independent of inline fact-value presence.

### RED evidence

The same pre-production V16 selector produced these actual failures for both
the base helper and exported adapter:

```text
authority-only: authority_resolved — assert True is False
identity-only:  authority_resolved — assert True is False
```

### Production change

`relation_unknown` now classifies every supplied Mapping whose relationship to
the requested attribute is unknown. It no longer checks whether `value` is
present. The existing distinction remains intact:

```text
no carrier                  = relation unknown, fail closed
explicit unrelated carrier = known irrelevant, non-poisoning
explicit empty carrier     = known to supply nothing, non-poisoning
```

### Base, adapter, and canonical coverage

- Base: authority-only and identity-only relation-unknown members block
  confident grade resolution.
- Exported adapter `resolve_source_authority_by_attribute()`: identical cases
  produce `authority_resolved=False` and `authority_unknown=True`.
- Canonical `AcademicSourceAuthorityRule`: identical claim shapes remain
  unresolved through canonical findings.
- Existing positive controls for valid unrelated evidence, explicit empty
  carriers, and coherent relevant authority-only evidence remain GREEN.

## Explicit invariants

```text
["x"] != "x"
("x",) != "x"
singular field requires strict scalar validation
plural helper remains plural
relation-unknown does not require inline value
known unrelated != relation unknown
base helper safety == adapter safety == canonical wrapper safety
malformed evidence must never expand epistemic reach
```

## Verification

| Gate | Actual result |
|---|---|
| V16 adversarial selector | `65 passed, 436 deselected in 1.01s` |
| Eight affected focal owners | `501 passed in 0.97s` |
| Full University suite | `765 passed in 1.81s` |
| Domains suite | `4323 passed in 6.04s` |
| Global suite | `9834 passed in 29.51s` |
| Ruff | `All checks passed!` |
| Ruff, target Python 3.10 | `All checks passed!` |
| `compileall -q cmm tests` | exit `0`, no output |
| Dependency direction | `1 passed in 0.59s` |
| Fresh import | `fresh_import=OK` |
| Placeholder scan | no matches |
| `git diff --check` | clean |
| `git diff --cached --check` | clean |
| Canonical counts | `14/12/10/11/7` |

## Positive controls and regression self-audit

```text
scalar deadline remains supported: YES
scalar ECTS subject/reference remains supported: YES
scalar regulation/attempt references remain supported: YES
scalar dependency IDs remain supported: YES
scalar Integrity reference/scope remains supported: YES
scalar Workload scenario ID remains supported: YES
valid unrelated source remains non-poisoning: YES
valid authority-only relevant source remains supported: YES

V14 source_id collection remains closed: YES
V14 claim id collection remains closed: YES
V14 conflicting unusable identities remain unresolved: YES
V14 relation-unknown WITH value remains unresolved: YES
V14 supplied_attributes=None remains closed: YES
V14 attribute=None remains closed: YES
V14 Deadline classifier remains strict: YES
V14 Performance remains strict: YES

V13 scope regressions remain closed: YES
V13 carrier regressions remain closed: YES
V12 regressions remain closed: YES
V11 regressions remain closed: YES
V10 regressions remain closed: YES
V9 regressions remain closed: YES

public helpers remain exception-safe: YES
canonical counts remain 14/12/10/11/7: YES
permission architecture untouched: YES
roadmap remains Implemented, pending audit: YES
```

## Closure assessment

```text
V15-B1 transversal singular scalar/reference enforcement — FIXED
V15-B2 complete relation-unknown classification — FIXED

All _usable_reference/_reference_from call-sites reviewed: YES
Every singular call-site uses strict scalar semantics: YES
Every remaining plural call-site is intentionally plural: YES
ECTS collections cannot establish credits/completion: YES
Exam collections cannot establish regulation/attempt evidence: YES
Dependency collections cannot satisfy prerequisite: YES
Integrity collections cannot establish/apply restriction: YES
Workload collection ID cannot become scalar scenario: YES
evaluate_deadline collection cannot become scalar deadline: YES
Canonical wrappers cannot re-coerce malformed singular fields: YES
Relation-unknown authority-only evidence cannot disappear: YES
Relation-unknown identity-only evidence cannot disappear: YES
Valid unrelated evidence remains non-poisoning: YES
Positive scalar behavior remains supported: YES
V14 regressions remain closed: YES
V13 regressions remain closed: YES
V12 regressions remain closed: YES
V11 regressions remain closed: YES
V10 regressions remain closed: YES
V9 regressions remain closed: YES
Public helpers remain exception-safe: YES
Canonical counts remain 14/12/10/11/7: YES
Permission architecture untouched: YES
```

No files were staged. No commit was created. No push was performed.

READY FOR INDEPENDENT AUDIT V16
