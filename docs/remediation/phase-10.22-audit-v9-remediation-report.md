# Phase 10.22 — University Domain — Audit V9 Remediation Report

**Branch:** `feature/phase-10-domain-intelligence`
**HEAD:** `2cdc92f fix(domains): close phase 10.22 audit v8 findings`
**Status:** `Implemented, pending audit`
**Focal suite (V9→V10):** `231 passed`

This remediation closes the four **Independent Audit V9** blockers for the
University Domain.  It is surgical: no domain redesigned, no permissions /
cross-domain touched, no rules / operations / workflows added or removed, no
counts changed, no other domain modified.  The patch is local, deterministic,
fail-closed and minimal, confined to `cmm/domains/university/rules.py` plus its
adversarial tests.

The invariants hardened here are:

- `valid container != valid evidence` — a valid list/tuple that still holds a
  malformed member is NOT fully valid evidence.
- `malformed member != absent member` — a malformed element is never silently
  dilated into absence or an empty collection.
- `truthy != grounded` — only the literal `True` grants strict grounding.
- `truthy != authorized` — only the literal `True` grants authorization.
- `malformed numeric metadata != runtime exception` — malformed numeric metadata
  fails closed into structured uncertainty, never a caller-facing exception.

---

## V9-B1 — Workload malformed element preservation — **FIXED**

### Root cause

`_normalize_collection` only checked that the **container** was a `list` /
`tuple`.  A valid collection holding a malformed **member** (e.g.
`hard_constraints=[7]`) was silently filtered, and the remaining (empty)
evidence was evaluated as if the malformed constraint never existed.  The same
silent filtering happened for `preferences`, top-level `scenarios`, and nested
`scenario.hard_constraints`, which converted malformed evidence into definite
feasibility / proposal results.

Reproduced V9 behavior:

```text
hard_constraints=[7]  -> WORKLOAD_ASSESSED, feasible=True, proposal="s1"   (WRONG)
preferences=[7]       -> WORKLOAD_ASSESSED, proposal="s1"                  (WRONG)
scenarios=[7, valid]  -> WORKLOAD_ASSESSED, feasible=True                  (WRONG)
scenario.hard_constraints=[7] -> WORKLOAD_ASSESSED, proposal="s1"          (WRONG)
```

### Production change

- `_CollectionEvidence` gained `container_malformed` / `element_malformed`
  fields; the existing `malformed` property is now
  `container_malformed or element_malformed` (backward compatible).
- `_normalize_collection(..., require_mapping_elements=True)` marks a valid
  container as **element-malformed** when any member is not a `Mapping`.
- `AcademicWorkloadRule.evaluate` now uses `require_mapping_elements=True` for
  `hard_constraints`, `preferences` and `scenarios`.
- `_evaluate_structured_workload` treats `scenario.hard_constraints` as
  malformed when the container is not a sequence **OR any member is not a
  `Mapping`**, pushing the affected scenario into `unresolved_scenarios`.
- Valid empties (`hard_constraints=[]`, `preferences=[]`) retain their
  legitimate no-constraint semantics.

### Canonical adversarial tests

Added to `tests/domains/test_university_domain_workload.py`:

```text
hard_constraints=[7]            -> WORKLOAD_FEASIBILITY_UNCERTAIN, proposal=None
hard_constraints=["bad"]        -> WORKLOAD_FEASIBILITY_UNCERTAIN
preferences=[7]                 -> WORKLOAD_FEASIBILITY_UNCERTAIN
scenarios=[7, valid]            -> WORKLOAD_FEASIBILITY_UNCERTAIN
scenario.hard_constraints=[7]   -> WORKLOAD_FEASIBILITY_UNCERTAIN, "s1" unresolved
valid Mapping-only constraints  -> WORKLOAD_ASSESSED, feasible=True   (positive regression)
```

### GREEN behavior proven

```text
hard_constraints=[7]            -> feasibility_uncertain=True, feasible=False, proposal=None
scenario.hard_constraints=[7]   -> unresolved, proposal=None; NOT definitely feasible
preferences=[7]                 -> no deterministic clean ranking / proposal
scenarios=[7, valid]            -> malformed scenario evidence preserved; no strong all-feasible conclusion
```

---

## V9-B2 — Source Authority / Contradiction malformed evidence — **FIXED**

### Root cause

`AcademicSourceAuthorityRule` and `AcademicContradictionRule` used `_seq`, which
returned `()` for a malformed container and silently skipped non-Mapping
members.  A malformed `academic_claims` / `contradiction_statements` value thus
fell through to `RULE_NOT_APPLICABLE` or produced a confidently resolved
finding, even though the evidence was incomplete or corrupt.

### Production change

- `AcademicSourceAuthorityRule.evaluate` now normalizes `academic_claims` with
  `_normalize_collection(..., require_mapping_elements=True)`.
- `AcademicContradictionRule.evaluate` now normalizes `contradiction_statements`
  with the same element-aware normalization.
- For malformed authority evidence, the rule no longer returns
  `RULE_NOT_APPLICABLE`; it emits an applied `ATTRIBUTE_AUTHORITY` finding with
  `authority_resolved=False`, `fact_resolved=False`, `authority_unknown=True`,
  plus a `SOURCE_AUTHORITY_EVIDENCE_MALFORMED` gap when any malformed evidence
  was present.
- For malformed contradiction evidence, the conflict record is fail-closed with
  `unresolved=True`, `resolved=False`, `evidence_malformed=True`; a valid
  container holding a malformed member cannot produce a clean
  `contradiction=False + resolved=True` conclusion.

### Canonical adversarial tests

Added to `tests/domains/test_university_domain_source_authority.py` and
`tests/domains/test_university_domain_contradiction.py`:

```text
academic_claims=[7]                     -> APPLIED, not RULE_NOT_APPLICABLE,
                                          authority_resolved=False, fact_resolved=False
academic_claims=[valid, 7]              -> deadline authority_resolved=False,
                                          fact_resolved=False, authoritative_value=None
contradiction_statements=[7]            -> APPLIED, not RULE_NOT_APPLICABLE,
                                          unresolved=True, resolved=False
contradiction_statements=[valid, 7]     -> unresolved=True, resolved=False
valid claims/statements only            -> authority/contradiction resolve normally (positive regression)
```

### GREEN behavior proven

```text
malformed claims container  -> structured unknown, authority_unknown=True
malformed claim member      -> authority_resolved=False even with valid claims present
malformed statements        -> unresolved=True, resolved=False even with valid statements present
valid all-Mapping evidence  -> normal authority / contradiction resolution
```

---

## V9-B3 — Strict trust-bearing booleans — **FIXED**

### Root cause

Trust-bearing fields (`grounded`, `authorized`) were consumed with Python
truthiness: `bool(record.get("grounded"))`, `bool(regulation.get("grounded"))`,
`health_constraint.get("authorized")`, etc.  Truthy strings (`"false"`,
`"true"`), `1`, `0`, `[]`, `{}` and arbitrary objects could therefore grant
grounding or authorization even though the metadata was not a genuine boolean
trust signal.

### Production change

- Added `_grants_trust(value)` — returns `True` **only** when `value is True`;
  no coercion, no string parsing.
- Added `_trust_flag_malformed(value)` — a non-`None`, non-`bool` trust flag is
  malformed and marks the associated evidence unknown rather than cleanly
  ungrounded.
- Replaced all trust-bearing truthiness checks in:
  - `check_ects_consistency` (record and degree-requirement grounding)
  - `evaluate_exam_attempt` (regulation grounding and attempt grounding)
  - `_evaluate_structured_workload` / `evaluate_academic_workload` (Health
    `authorized`)
  - `_resolve_dependency_credit_evidence` and `evaluate_academic_dependency`
    (credit-record grounding)
  - `evaluate_academic_integrity` (restriction grounding)
- A malformed attempt trust flag (`grounded="false"`, `1`, etc.) is now treated
  as unknown attempt evidence, not a clean within-limits zero-consumption
  conclusion.

### Canonical/helper adversarial tests

Added across `test_university_domain_ects.py`,
`test_university_domain_exam_attempts.py`, `test_university_domain_integrity.py`,
`test_university_domain_dependencies.py`, and
`test_university_domain_health_projection.py`:

```text
grounded="false" ECTS record            -> ECTS_COMPLETION_BLOCKED, satisfied=False
grounded="true"/1/0 ECTS record         -> still NOT grounded
grounded="false" exam regulation        -> regulation_unknown=True, within_limits=False
grounded="false" attempt                -> attempt_evidence_unknown=True, within_limits=False
grounded="false" restriction            -> restriction_grounded=False, assistance_permitted=True
grounded=1 restriction                  -> restriction_grounded=False
grounded="false" credit record          -> credit_evidence_unknown=True, DEPENDENCY_BLOCKED
authorized="false"/"true"/1/0 Health    -> health_functional_cap NOT consumed
strict grounded=True / authorized=True  -> normal behavior retained (positive regression)
```

### GREEN behavior proven

```text
truthy != grounded: only literal True grounds
truthy != authorized: only literal True authorizes
malformed trust flags -> structured unknown, never a strong grounded/authorized conclusion
literal True -> ECTS, exam, integrity, dependency, and Health behavior unchanged
```

---

## V9-B4 — Public Workload helper numeric fail-closed — **FIXED**

### Root cause

`evaluate_academic_workload` applied `int(functional_cap)` and `int(rank)` to
caller-supplied metadata.  A malformed `functional_cap_ect` (e.g. `"abc"`) or a
malformed preference `rank` (e.g. `"abc"`) raised a `ValueError` instead of
producing a structured evaluation result.

### Production change

- `evaluate_academic_workload` now parses the Health `functional_cap_ect` with
  `_parse_non_negative_number`; a failed parse sets
  `health_functional_cap_evidence_unknown=True` and returns a fail-closed
  structured unknown result (`feasible=False`,
  `health_functional_cap_evidence_unknown=True`), never a direct exception.
- Preference ranks are parsed with `_parse_ects_integer`; a failed rank sets
  `ranking_unresolved=True` and returns a structured preferences-stage result
  with no false trade-off/conflict claim.
- Valid integral ranks retain existing behavior.

### Canonical/helper adversarial tests

Added to `tests/domains/test_university_domain_health_projection.py`:

```text
authorized malformed cap "abc"      -> feasible=False, health_functional_cap_evidence_unknown=True
authorized="false" cap              -> cap NOT consumed; feasible=True
malformed preference rank "abc"     -> ranking_unresolved=True, feasible=True
valid rank 1                        -> ranking_unresolved=None, feasible=True (positive regression)
```

### GREEN behavior proven

```text
malformed numeric metadata != runtime exception
malformed cap      -> structured evidence unknown, no ValueError
malformed rank     -> ranking_unresolved=True, no ValueError
valid cap/rank     -> existing numeric behavior unchanged
```

---

## Roadmap

- **Status:** Implemented, pending audit
- **Focal verification:** 231 passed
- Fresh University/domains/global verification was NOT run after the final
  production/test changes; only the independently verified focal suite is
  reported here.

## Invariants preserved

- `valid container != valid evidence`
- `malformed member != absent member`
- `truthy != grounded`
- `truthy != authorized`
- `malformed numeric metadata != runtime exception`
