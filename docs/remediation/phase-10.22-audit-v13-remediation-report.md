# PHASE 10.22 UNIVERSITY DOMAIN — AUDIT V13 → V14 CLOSURE REMEDIATION

**Phase:** 10.22 University Domain
**Audit:** Independent Audit V13 → Independent Audit V14
**Date:** 2026-08-12
**Status:** Remaining blockers closed — **READY FOR INDEPENDENT AUDIT V14**
**Production scope:** `cmm/domains/university/rules.py`
**Test scope:** `tests/domains/test_university_domain_source_authority.py`,
`tests/domains/test_university_domain_contradiction.py`
**Roadmap:** unchanged — `Implemented`, pending audit (Independent Audit V14 decides closure).
**Git:** No files staged. No commit created. No push performed. All changes left UNSTAGED.

This report records the surgical closure of the two blocker clusters raised by
Independent Audit V13. Each entry follows *root cause → production change →
direct RED test → canonical RED test → GREEN behavior*.

---

## Invariants re-established

| Invariant | Meaning |
|---|---|
| **Mapping instance ≠ semantically valid evidence** | A `Mapping` with an identity-looking key is not, by itself, usable academic evidence. |
| **one identity-looking key ≠ complete academic evidence** | An `id` / `source_id` / `value` alone does not establish a valid source or claim. |
| **malformed attribute carrier ≠ irrelevant evidence** | `supplied_attributes="grade"` / `[7]` is relationship-unknown and must fail closed, not become "no relevant supplied attribute". |
| **missing claim attribute ≠ "unknown" claim safely ignored** | A claim with no usable attribute cannot be bucketed into a synthetic `"unknown"` group that resolves cleanly. |
| **absent scope ≠ malformed scope** | `None` is unscoped; `scope=7` / `scope=""` is malformed and must fail closed. |
| **malformed scope ≠ global/unscoped scope** | A malformed scope never acts as unscoped/global evidence. |
| **malformed evidence ≠ evidence allowed to disappear** | Malformed/incomplete evidence is preserved as structured uncertainty, never silently filtered away. |
| **one metadata string ≠ semantic completeness** | A single arbitrary non-empty authority string (`provenance="garbage"`) does not convert a partial source into a valid authority-only source. |

---

## V13-B1 — Semantic evidence validation still too permissive

### Root cause

V12 introduced `_source_speaks_about()` / `_source_is_incomplete_for()` /
`_claim_is_incomplete()`, but the minimum semantic requirements were too weak:

1. `_source_is_incomplete_for` treated `source_class` / `provenance` /
   `temporal` / `specificity` as "present authority identity" whenever they were
   **any non-empty string**. A partial source `{"source_id":"junk",
   "supplied_attributes":["grade"],"provenance":"garbage"}` therefore stopped
   being flagged as incomplete, letting a valid same-attribute source resolve
   confidently — even though `"garbage"` could never establish authority.
2. `_source_speaks_about` and the evaluation loop treated a **malformed
   `supplied_attributes` carrier** (bare scalar `"grade"`, `[7]`, `{}`) as "does
   not speak about the attribute", i.e. **irrelevant evidence**, instead of
   **malformed/relationship-unknown evidence**.
3. `_claim_is_incomplete` only caught *valid attribute + missing value*. A claim
   with **missing / blank / non-string `attribute`** (`{"id":"junk","value":...}`
   , `attribute=""`, `attribute=7`) fell through to `_claim_attribute` →
   `"unknown"`, a synthetic bucket treated as safely unrelated, so a valid
   same-attribute claim resolved cleanly beside it.

### Production change (`cmm/domains/university/rules.py`)

- Added `_usable_attribute_string()` and `_attribute_carrier_malformed()`: a
  present-but-non-sequence `supplied_attributes` or a sequence containing a
  non-usable member is a **malformed attribute carrier** (relationship-unknown),
  and a present bare `attribute` that is not a usable string is malformed too.
- Added `_source_has_recognized_authority()`: a source carries coherent
  authority-only identity only when its `source_class`, `provenance`
  (`grounded`), `temporal` (current), and `specificity` all normalize to
  **recognized** values. Raw arbitrary strings (`provenance="garbage"`) are
  never recognized.
- Reworked `_source_is_incomplete_for()`: a same-attribute value-less source is
  incomplete **unless** it carries the recognized authority identity above.
  This is stricter than "any non-empty string" but preserves the existing
  coherent authority-only positive fixtures (which supply the full recognized
  metadata shape).
- Reworked `_claim_is_incomplete()`: a missing / blank / non-string `attribute`
  is relationship-unknown and incomplete; a valid-attribute value-less claim
  remains incomplete (V12-B2 preserved).
- `classify_academic_source_authority` fails closed when any source has a
  malformed attribute carrier; the canonical
  `AcademicSourceAuthorityRule.evaluate` computes a rule-level
  `relation_unknown_evidence` (missing/blank/non-string attribute **or**
  malformed scope) and fails closed + emits
  `SOURCE_AUTHORITY_EVIDENCE_MALFORMED`.

### Direct RED tests (`test_university_domain_source_authority.py`,
`test_university_domain_contradiction.py`)

- `test_v13_b1_partial_arbitrary_provenance_does_not_resolve`
- `test_v13_b1_partial_source_class_only_does_not_resolve`
- `test_v13_b1_partial_temporal_only_does_not_resolve`
- `test_v13_b1_partial_specificity_only_does_not_resolve`
- `test_v13_b1_malformed_supplied_attributes_fails_closed` (parametrized: `"grade"`, `7`, `{}`, `[7]`, `[""]`, `["grade", 7]`)
- `test_v13_b1_missing_or_invalid_attribute_claim_unresolved` (parametrized: missing / `""` / `7` / empty)
- `test_v13_b1_valid_unrelated_claim_stays_safe`

### Canonical RED tests

- `test_v13_b1_canonicical_partial_arbitrary_provenance_unresolved` —
  `academic_claims=[valid deadline claim, junk provenance="garbage"]` →
  `authority_resolved=False`, `fact_resolved=False`, `authority_unknown=True`,
  `SOURCE_AUTHORITY_EVIDENCE_MALFORMED` gap.
- `test_v13_b1_canonical_relation_unknown_claim_never_buckets_relevant` —
  `academic_claims=[valid deadline claim, {"id":"junk","value":...}]` →
  deadline must NOT resolve confidently + gap.
- `test_v13_b1_canonical_missing_or_invalid_attribute_unresolved` —
  `contradiction_statements` → `CONTRADICTION_UNRESOLVED`, `resolved=False`,
  `unresolved=True`.

### GREEN behavior

- A **valid** same-attribute source still resolves (`authority_resolved=True`).
- A value-less source carrying the **full recognized authority identity** (
  coherent authority-only) still resolves — `test_v13_b1_coherent_authority_only_source_remains_supported`.
- A fully valid **unrelated** source/claim does not poison the target attribute.

---

## V13-B2 — Malformed scope collapses to unscoped/global evidence

### Root cause

`_source_scope()` and `_claim_scope()` returned `None` for **both** an absent
scope and a present-but-malformed scope (`scope=7`, `scope=""`,
`scope=[]`). Because `None` means unscoped/global, a malformed scope was
silently upgraded to global evidence:

1. Source authority treated a same-attribute `scope=7` as global, so it would
   participate under any requested scope.
2. Contradiction `_scope_matches` let a malformed-scope claim match every
   scope, creating cross-scope contradiction reach.
3. The public requested `scope` argument was typed `str | None` but a runtime
   malformed value (`7`, `""`) was trusted as unscoped.

### Production change (`cmm/domains/university/rules.py`)

- Added a lightweight **malformed-aware scope normalization** (`_scope_state`)
  preserving three states: `SCOPE_ABSENT` / `SCOPE_VALID` / `SCOPE_MALFORMED`.
  Only a non-empty string is valid; `None` is absent (existing unscoped
  semantics); anything else present is malformed.
- Added `_source_scope_malformed()` and `_claim_scope_malformed()`.
- `_scope_matches()` returns `False` for a malformed-scope claim, so it never
  matches any scope and can never create cross-scope reach or act as global.
- `_effective_scopes()` excludes malformed scopes from the collected scope set
  so they cannot default the resolution to the unscoped `None`.
- `_claim_source()` now forwards the **raw** claim scope so the delegated
  source-authority classifier can detect the malformed scope.
- `classify_academic_source_authority` fails closed on a malformed **requested**
  scope and on a **malformed source scope**.
- `resolve_academic_conflict` fails closed on a malformed **requested** scope and
  marks the result unresolved when any claim has a **malformed claim scope**.
- `AcademicSourceAuthorityRule.evaluate` fails closed + emits the gap when
  relation-unknown evidence (including malformed scope) is present.

### Direct RED tests

- `test_v13_b2_malformed_source_scope_never_global` (parametrized: `7`, `""`, `[]`, `["course:A"]`, `{}`, `0.0`) → `authority_resolved=False`.
- `test_v13_b2_malformed_claim_scope_unresolved` (parametrized) → `resolved=False`, `unresolved=True`.
- `test_v13_b2_mixed_valid_and_malformed_scope_never_broadens_reach` — a `course:A`
  claim plus a `scope=7` claim: the malformed member never acts global and is
  absent from all conflict pairs.
- `test_v13_b2_requested_scope_fails_closed` (both helpers, parametrized `7`, `""`).

### Canonical RED tests

- `test_v13_b2_canonical_source_authority_malformed_scope_never_global` — `scope=7`
  → no `scope=None` emission, `authority_resolved=False`, `fact_resolved=False`,
  `authority_unknown=True`, `SOURCE_AUTHORITY_EVIDENCE_MALFORMED` gap.
- `test_v13_b2_canonical_contradiction_malformed_scope_unresolved` — `scope=7`
  → `CONTRADICTION_UNRESOLVED`, `resolved=False`, `unresolved=True`, scope not
  normalized to `None`.

### GREEN behavior (scope positives preserved)

- `scope` absent → unscoped/global semantics preserved
  (`test_v13_b2_absent_scope_retains_unscoped_semantics`).
- `scope="course:A"` → scoped semantics preserved
  (`test_v13_b2_valid_string_scope_retains_scoped_semantics`).

---

## Adversarial V14 gate

| Question | Expected | Result |
|---|---|---|
| partial `provenance="garbage"` → authority resolved? | NO | YES |
| `source_class` only → authority resolved? | NO | YES |
| `supplied_attributes="grade"` → treated as irrelevant? | NO | YES (malformed, fail-closed) |
| claim missing attribute → resolved cleanly? | NO | YES |
| claim `attribute=""` → resolved cleanly? | NO | YES |
| claim `attribute=7` → resolved cleanly? | NO | YES |
| source `scope=7` → global? | NO | YES |
| source `scope=""` → global? | NO | YES |
| claim `scope=7` → global? | NO | YES |
| claim A `course:A` + claim B `scope=7` → B global? | NO | YES |
| requested `scope=7` → clean resolution? | NO | YES |

---

## Regression self-audit

All of the following remain `YES` (verified by the unchanged green suites):

- V12 material/unresolved truthiness remains closed (V12-B1)
- V12 `critical="false"` is non-material/non-blocking (V12-B1)
- V12 Deadline composition remains strict
- V12 Integrity composition remains strict
- V12 exact partial same-attribute Source Authority remains unresolved (V12-B2)
- V12 exact value-less Contradiction claim remains unresolved (V12-B2)
- V11 adapter malformed cases remain closed
- V11 Workload strict booleans remain closed
- V11 opaque Mapping remains conservative (V11-B3)
- V11 Performance validation remains closed
- V10 regressions remain closed
- V9 regressions remain closed
- coherent authority-only source remains valid
- valid unrelated attribute evidence remains safe
- absent scope retains unscoped semantics
- valid string scope retains scoped semantics
- canonical counts remain 14/12/10/11/7
- permission architecture untouched

`NO` anywhere ⇒ not ready; none was found.

---

## Verification

| Check | Result |
|---|---|
| focal tests (`source_authority` + `contradiction` + `rules`) | **164 passed** |
| University suite (`test_university_domain_*.py`) | **635 passed** |
| Domains suite (`tests/domains`) | **4193 passed** |
| Global suite (`pytest -q`) | **9704 passed** |
| Ruff (`default`) | passed |
| Ruff (`--target-version py310`) | passed |
| `compileall -q cmm tests` | passed |
| `test_dependency_direction.py` | 1 passed |
| fresh import (`import cmm.domains.university`) | `fresh_import=OK` |
| placeholder scan (`TBD/TODO/FIXME/PLACEHOLDER/XXX`) | none |
| `git diff --check` / `git diff --cached --check` | clean |
| `git status --short` | only `rules.py` + 2 test files modified (unstaged) |

Long-standing untracked artifacts (`phase-10.22-audit-v*.tar.gz`,
`docs/remediation/phase-10.22-audit-v13-report.md`) were present before this
work and were **not modified or staged**.

## Git state

- **No files staged.**
- **No commit created.**
- **No push performed.**

## Final recommendation

**READY FOR INDEPENDENT AUDIT V14**

Phase 10.22 is **not** declared complete; Independent Audit V14 decides closure.
