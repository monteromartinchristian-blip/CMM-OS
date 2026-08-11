# PHASE 10.22 UNIVERSITY DOMAIN — AUDIT V12 → V13 CLOSURE REMEDIATION

**Phase:** 10.22 University Domain
**Audit:** Independent Audit V12 → Independent Audit V13
**Date:** 2026-08-12
**Status:** Remaining blockers closed — **READY FOR INDEPENDENT AUDIT V13**
**Production scope:** `cmm/domains/university/rules.py` (plus affected University tests + this report)

This document records the surgical closure of the two blocker clusters raised by
Independent Audit V12. Each entry follows *root cause → production change →
RED test → canonical RED test → GREEN behavior*.

---

## Invariants re-established (composition boundaries)

| Invariant | Meaning |
|---|---|
| **strict helper == strict wrapper composition** | Adapters/wrappers delegate the raw runtime value to the strict helper; they never re-coerce with `bool(...)` / truthiness before delegation. |
| **`"false"` ≠ `False`** | A non-empty string is a malformed boolean, not a signal. No string parsing of `"false"`/`"true"`, and no `1` / `0` coercion. Only literal `True` is a real signal. |
| **truthy ≠ `True`** | Python truthiness of caller metadata is never trusted for boolean-bearing fields. |
| **partial same-attribute source ≠ ignorable source** | A source that claims the target attribute but lacks minimum semantic content cannot be dropped; it forces target uncertainty. |
| **claim identity ≠ claim fact** | `id` + `attribute` alone does not prove no contradiction; a value-less same-attribute claim is incomplete evidence. |
| **missing value ≠ corroboration** | A fact value that is absent cannot corroborate, contradict, or differ; it is not proof of a clean conclusion. |

---

## V12-B1 — Residual strict boolean semantics at composition boundaries

### Root cause
V11 hardened the base helpers, but several **composition points** recomposed
runtime metadata with Python truthiness before or instead of the strict helper:

1. `evaluate_academic_contradiction` legacy flag-only path used
   `statement.get("material")` / `statement.get("unresolved")` truthiness.
2. `_claim_critical` used `bool(claim.get("critical"))`.
3. `AcademicDeadlineRule.evaluate` used
   `bool(metadata.get("deadline_decision_critical") or metadata.get("deadline_required"))`
   and `bool(deadline.get("critical"))`.
4. `AcademicIntegrityRule.evaluate` pre-coerced
   `remembered_restriction=bool(integrity.get("remembered_restriction"))`.

So `"false"` (a non-empty string) became `True` everywhere a wrapper guarded the
already-strict base helper.

### Production change (`cmm/domains/university/rules.py`)
- Reused the existing strict helper `_boolean_true` (the precise `value is True`
  semantic). No new ad-hoc expressions.
- **Contradiction flag-only path:** reads `material` and `unresolved` per
  statement; only a literal `True` is a real signal; a truthy string / `1` / `0`
  is recorded as malformed/unknown; malformed flag-only evidence is never
  `material=True` and stays conservatively unresolved.
- **`_claim_critical`:** `return _boolean_true(_claim_field(claim, "critical"))`.
  This one change fixes every call site (contradiction materiality/blocking,
  canonical source-authority ``decision_critical``, etc.).
- **Deadline wrapper:** `context_critical = _boolean_true(
  metadata.get("deadline_decision_critical")) or _boolean_true(
  metadata.get("deadline_required"))` and `effective_critical = context_critical
  or _boolean_true(deadline.get("critical"))`.
- **Integrity wrapper:** pass the raw `integrity.get("remembered_restriction")`
  (no `bool(...)`), letting the strict helper classify it; surfaced
  `remembered_not_official` in the finding metadata so the canonical result is
  observable and testable.

### RED tests
- Contradiction flag-only: `test_v12_b1_flag_only_material_string_never_material_true`
  (`"false"` / `"true"` / `1` / `0` → `material is False`),
  `test_v12_b1_flag_only_unresolved_string_not_truthy`
  (`{"material":"false","unresolved":"false"}` → not material, unresolved).
- Claim critical: `test_v12_b1_claim_critical_string_false_does_not_block`
  (`critical="false"` on equal-authority incompatible claims → `material=False`,
  `blocked=False`; the contradiction stays unresolved).
- Deadline: `test_v12_b1_deadline_decision_critical_string_false_not_critical`,
  `test_v12_b1_deadline_required_string_false_not_critical`,
  `test_v12_b1_deadline_required_truthy_never_critical`,
  `test_v12_b1_deadline_payload_critical_string_false_not_critical`.
- Integrity: `test_v12_b1_integrity_remembered_restriction_malformed_not_true`
  (`"false"` / `"true"` / `1` / `0` → `remembered_not_official is False`).

### Canonical RED tests
- `test_v12_b1_deadline_*` go through `AcademicDeadlineRule.evaluate` with
  context metadata and the deadline payload — the wrapper-composition sites.
- `test_v12_b1_integrity_*` go through `AcademicIntegrityRule.evaluate`.

### GREEN behavior
`evaluate_academic_contradiction({"material":"false","unresolved":"false"})` →
`material=False`, `resolved=False`, `unresolved=True`. `critical="false"` on an
equal-authority conflict → `contradiction=True`, `resolved=False`,
`unresolved=True`, `material=False`, `blocked=False`. `deadline_decision_critical="false"`
with no deadline → `NOT_APPLICABLE`. `remembered_restriction="false"` →
`remembered_not_official=False`. Literal `True`/`False` regressions remain green
(`material=True` is material; `remembered_restriction=True` is remembered).

---

## V12-B2 — Resolver-specific minimum semantic validation of partial evidence

### Root cause
V11's opaque-Mapping check (`_semantic_evidence_malformed`) treated any
non-opaque Mapping (one broad identity-looking key present) as usable evidence.
Evidence that was **partially shaped for the same attribute** — e.g.
`{"source_id":"junk","supplied_attributes":["grade"]}` or
`{"id":"junk","attribute":"deadline"}` — slipped through and either let a valid
same-attribute source resolve alone (Source Authority) or produced a clean
`contradiction=False + resolved=True` (Contradiction).

### Production change (`cmm/domains/university/rules.py`)
Small **resolver-specific** private predicates (no global schema):

- `_source_speaks_about(source, attribute)` — a source names the target
  attribute via `supplied_attributes` or a bare `attribute`. This draws the
  "same-attribute" vs "irrelevant unrelated evidence" boundary.
- `_source_is_incomplete_for(source, attribute)` — a source that speaks about
  the target attribute but carries **neither a usable fact value nor any
  authority/grounding identity** (`source_class` / `provenance` / `temporal` /
  `specificity`). An authority-establishing source without an inline value stays
  usable.
- `_claim_is_incomplete(claim)` — a contradiction claim that names an attribute
  (usable `attribute` string) but lacks a usable fact `value`.

Wiring:
- `classify_academic_source_authority`: detects incomplete same-attribute
  sources (respecting scope relevance) and returns
  `authority_resolved=False`, `fact_resolved=False`, `authority_unknown=True`
  with `reason="incomplete_same_attribute_evidence"`.
- `resolve_academic_conflict`: forces `unresolved=True` when any claim is
  incomplete, and the returned `unresolved` field now surfaces true unresolved
  (no longer gated on a conflicting pair existing).
- `AcademicSourceAuthorityRule.evaluate`: per-attribute-scope, forces unresolved
  for incomplete evidence and emits a `SOURCE_AUTHORITY_EVIDENCE_MALFORMED`
  gap ("Malformed or incomplete source authority evidence…").

### RED tests
- Direct Source Authority: `test_v12_b2_source_partial_supplied_attributes_not_resolved`
  and `test_v12_b2_source_partial_bare_attribute_not_resolved`.
- Direct Contradiction: `test_v12_b2_direct_partial_same_attribute_claim_unresolved`.

### Canonical RED tests
- `test_v12_b2_canonical_partial_same_attribute_evidence_unresolved`
  (`academic_claims=[valid, {"id":"junk","attribute":"deadline"}]` →
  `ATTRIBUTE_AUTHORITY` `authority_resolved=False`, `fact_resolved=False`,
  `authority_unknown=True`, gap emitted).
- `test_v12_b2_canonical_partial_same_attribute_claim_unresolved`
  (`contradiction_statements=[valid, partial]` →
  `CONTRADICTION_UNRESOLVED`, never a clean resolved state).

### GREEN behavior
`(valid grade source, {"source_id":"junk","supplied_attributes":["grade"]})` →
no confident grade resolution. `(valid claim, {"id":"junk","attribute":"deadline"})`
→ `resolved=False`, `unresolved=True`. **Preserved positives:** valid
authority-only sources (no inline value) still resolve
(`test_v12_b2_source_valid_authority_only_still_resolves`); fully valid
unrelated-attribute evidence does not poison the target attribute
(`test_v12_b2_source_valid_unrelated_attribute_does_not_poison`); valid
same-attribute corroboration resolves (`test_v12_b2_direct_valid_corroboration_stays_resolved`).

---

## Verification matrix (final)

| Check | Result |
|---|---|
| Focal University files (contradiction, deadlines, integrity, source_authority, rules, workload, verification) | **266 passed** |
| Full University suite | **593 passed** (baseline 562 + 31) |
| Full domains suite | **4151 passed** |
| Full global suite | **9662 passed** |
| `ruff check` (default) `cmm/domains/university` + University tests | All checks passed |
| `ruff check --target-version py310` | All checks passed |
| `compileall -q cmm tests` | OK |
| `tests/agent_runtime/test_dependency_direction.py` | 1 passed |
| Fresh import (`import cmm.domains.university`) | OK |
| Placeholder scan (TBD/TODO/FIXME/PLACEHOLDER/XXX) | none |
| `git diff --check` / `git diff --cached --check` | clean |
| Canonical counts entities/resources/rules/operations/workflows | 14/12/10/11/7 unchanged |

## Scope review

Modified: `cmm/domains/university/rules.py`
+ `tests/domains/test_university_domain_{contradiction,deadlines,integrity,source_authority}.py`
+ `docs/remediation/phase-10.22-audit-v12-remediation-report.md` (this file).

**Not touched:** `permission_gate.py`, `permission_resolution.py`,
`university/operations.py`, `university/workflows.py`, `university/catalog.py`,
and all other domains. Untracked audit tarballs v1–v12 remain untouched.

**Git state:** None of the above is staged. No commit created. No push performed.
All changes remain UNSTAGED, per the remediation constraints.

## Recommendation

**READY FOR INDEPENDENT AUDIT V13**
