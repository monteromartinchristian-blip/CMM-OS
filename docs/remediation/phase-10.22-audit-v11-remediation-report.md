# PHASE 10.22 UNIVERSITY DOMAIN — AUDIT V11 → V12 CLOSURE REMEDIATION

**Phase:** 10.22 University Domain
**Audit:** Independent Audit V11 → Independent Audit V12
**Date:** 2026-08-12
**Status:** Remaining blockers closed — **READY FOR INDEPENDENT AUDIT V12**
**Production scope:** `cmm/domains/university/rules.py` (plus affected University tests + this report)

This document records the surgical closure of the four blockers raised by
Independent Audit V11. Each entry follows *root cause → production change →
RED test → canonical RED test → GREEN behavior*.

---

## Invariants established (carried forward and hardened)

| Invariant | Meaning |
|---|---|
| **Exported adapter safety == base helper safety** | Compatibility helpers normalize malformed containers/members **before** iterating/delegating, so a malformed piece of evidence cannot be silently dropped. |
| **Truthy ≠ boolean `True`** | Runtime boolean-bearing fields accept only the literal `True`/`False` Python bool. No string parsing, no coercion of `"false"`, `1`, `0`, `[]`, `{}`. |
| **Mapping instance ≠ semantically valid evidence** | A `Mapping` shaped like evidence that is empty or opaque (`{}`, `{"foo": "bar"}`) is **malformed evidence**, not a valid claim/source/observation. |
| **Malformed evidence cannot disappear before delegation** | Normalized members are preserved and passed to the hardened resolver, which classifies the malformed evidence rather than filtering it out. |

---

## V11-B1 — Exported compatibility helpers must normalize before filtering/delegation

### Root cause
`resolve_source_authority_by_attribute` and `evaluate_academic_contradiction`
iterated over raw caller arguments and filtered out non-Mapping members
*without* running them through `_normalize_collection_value`. Malformed
containers (`7`, `"abc"`, `{"x": 1}`) and malformed members (`7`) could
therefore disappear before reaching the hardened base resolver, letting the
adapter disagree with the base fail-closed boundary.

### Production change (`cmm/domains/university/rules.py`)
- `resolve_source_authority_by_attribute` now calls
  `_normalize_collection_value(sources, require_mapping_elements=True)` and
  iterates `sources_evidence.items`, preserving every malformed member in a
  `normalized: list[Any]` before delegation.
- `evaluate_academic_contradiction` now normalizes the container up front,
  returns `CONTRADICTION_UNRESOLVED` on `container_malformed`, and — when any
  member is claim-shaped (`attribute` + `value`) — delegates **ALL** normalized
  statements (including malformed members) to
  `resolve_academic_conflict(claims=tuple(statements))`.
- The exported adapter now exposes an `unresolved` boolean on **every** return
  path (malformed container, empty input, structured delegation, flag-only
  shape), matching the base resolver and the strict `resolved=False /
  unresolved=True` fail-closed contract. Adversarial assertions
  (V12 gate) require `evaluate_academic_contradiction(7 | "abc" | {"x":1} |
  (claim, 7))` → `resolved=False` **and** `unresolved=True`.

### RED test (filled first)
- Source authority: `test_v11_b1_source_authority_*` — `sources=7` and
  `(valid, 7)` must not raise and must not resolve confidently.
- Contradiction: `test_v11_b1_contradiction_adapter_*` — `statements=7`,
  `"abc"`, `{"x": 1}`, and `(claim, 7)` must stay unresolved.

### GREEN behavior
`resolve_source_authority_by_attribute(attribute="grade", sources=(valid, 7))`
→ `authority_resolved=False`, `authority_unknown=True`.
`evaluate_academic_contradiction(statements=(claim, 7))` →
`resolved=False`, `unresolved=True`, `state="unresolved"`. Fully-valid inputs
remain green (`(claim,)` → `resolved=True`, `unresolved=False`,
`state="resolved"`).

---

## V11-B2 — Strict runtime boolean semantics on every public path

### Root cause
Public reasoning paths trusted truthy values for boolean-bearing fields:
a caller-supplied `"false"` (a non-empty string) would be treated as
`True` for `satisfied`, `conflicting`, `critical`, `decision_critical`,
`ai_forbidden`, `ambiguous`, `superseded`, and `remembered_restriction`.

### Production change (`cmm/domains/university/rules.py`)
- New helper `_boolean_true(value)`: returns `True` only for the literal
  boolean `True` (`isinstance(value, bool) and value`).
- **Workload** `satisfied`: strict per-constraint handling — only a literal
  bool is accepted; a non-bool value is recorded as `None` and sets
  `constraint_satisfaction_unknown`, driving the verdict to non-feasible and
  keeping `proposal=None`. Non-strict branch returns the bool value only when
  `isinstance(satisfied_value, bool)`, else `None`.
- **Deadline** `conflicting` / `critical`: gated through `_boolean_true`.
- **Verification** `decision_critical`: gated through `_boolean_true`.
- **Integrity** `ai_forbidden` / `ambiguous` / `superseded` /
  `remembered_restriction`: gated through `_boolean_true`; malformed values
  tracked as `*_uncertain` and treated fail-closed.

### RED tests (filled first)
`test_v11_b2_workload_satisfied_*`, `test_v11_b2_deadline_*_string/int_*`,
`test_v11_b2_verification_decision_critical_string`, and
`test_v11_b2_integrity_ai_forbidden/ambiguous/superseded_malformed`.

### GREEN behavior
`evaluate_academic_workload({...,"satisfied":"false"})` → `feasible=False`,
`proposal=None`. `classify_deadline_grounding({...,"conflicting":"false"})` →
`state != "conflicting"`. `conditional_verification_trigger(...,"false")` →
`verification_triggered=False`. `evaluate_academic_integrity(...,{"ai_forbidden":"false"})`
→ not forbidden. Literal-bool inputs continue to behave correctly.

---

## V11-B3 — Source Authority / Contradiction semantic Mapping validation

### Root cause
Malformed detection only checked container/element shape via
`_normalize_collection_value`. An **empty or opaque** Mapping (`{}`,
`{"foo": "bar"}`) is *Mapping-shaped* yet carries **no academic evidence**; it
was treated as a valid member and could participate in a clean
`no contradiction` / `authority not confident` conclusion.

### Production change (`cmm/domains/university/rules.py`)
- New identity-key set `_MAPPING_IDENTITY_KEYS` and helper
  `_mapping_evidence_is_opaque(value)` (a Mapping that contains none of the
  semantic identity keys is opaque/malformed).
- New helper `_semantic_evidence_malformed(items)` — true if any member is an
  opaque Mapping.
- Wired into the base resolvers and canonical rules:
  - `classify_academic_source_authority` /
    `AcademicSourceAuthorityRule`: `sources_evidence.malformed or
    _semantic_evidence_malformed(sources)`
  - `resolve_academic_conflict` / `AcademicContradictionRule`:
    `claims_evidence.malformed or _semantic_evidence_malformed(claims)` /
    `statements_evidence.malformed or _semantic_evidence_malformed(statements)`

### RED tests (filled first)
- Source authority: `test_v11_b3_*` — `(valid, {})` direct and canonical
  `_canonical_result([valid, {}])` yield `SOURCE_AUTHORITY_EVIDENCE_MALFORMED`
  finding and `authority_resolved=False`.
- Contradiction: `test_v11_b3_direct_conflict_opaque_claim_stays_unresolved`
  and `test_v11_b3_canonical_contradiction_opaque_statement_unresolved` —
  `[valid_claim, {}]` emits `CONTRADICTION_UNRESOLVED` and never a clean
  `resolved=True`.

### GREEN behavior
`resolve_academic_conflict(claims=(valid_claim, {}))` →
`resolved=False`, `unresolved=True`. Canonical contradiction rule with
`[valid_claim, {}]` → `CONTRADICTION_UNRESOLVED` present, no clean resolved
conclusion. Valid fixtures remain unaffected (all valid sources carry
`source_id`/`supplied_attributes`; valid claims carry `id`/`attribute`/`value`).

---

## V11-B4 — Performance must reject empty/arbitrary Mapping as observed performance

### Root cause
`evaluate_performance_capacity` (and `ObservedPerformanceCapacityRule`)
accepted `{}` — or an arbitrary Mapping — as a valid academic observation,
treating the *presence of a Mapping* as evidence of performed capacity. The
observation must be *semantically* grounded: it needs a usable `ref` and a
semantically meaningful `outcome`.

### Production change (`cmm/domains/university/rules.py`)
- `evaluate_performance_capacity` requires `_usable_reference(ref)` **and**
  `_usable_reference(outcome)`; if either is unusable it returns
  `performance_observed=False`, `capacity_inferred=False`, and
  `performance_evidence_unknown=True` without asserting a capacity.
- `ObservedPerformanceCapacityRule` gains a branch for `not
  record["performance_observed"]` that returns a **NOT-observed** finding
  (it no longer emits "Observed academic performance is…" for `{}`).

### RED tests (filled first)
`test_v11_b4_performance_empty_mapping_*` (`{}`) and
`test_v11_b4_performance_arbitrary_mapping_*` (`{"foo": "bar"}`), direct and
canonical.

### GREEN behavior
`evaluate_performance_capacity(performance_observation={})` →
`performance_observed=False`, `performance_evidence_unknown=True`,
`capacity_inferred=False`. Valid observation
`{"ref": "res-1", "outcome": "below_average"}` → `performance_observed=True`,
`capacity_inferred=False` (no fabricated capacity without more evidence).

---

## Verification matrix (final)

| Check | Result |
|---|---|
| Focal University suites (rules, source-authority, contradiction, workload, deadlines, verification, integrity) | **235 passed** |
| Full University domain suite (incl. definition / catalog reconciliation 14/12/10/11/7) | **562 passed** |
| Full domains suite | **4120 passed** |
| Full global suite | **9631 passed** |
| `ruff check` (default) `rules.py` | All checks passed |
| `ruff check --target-version py310` `rules.py` | All checks passed |
| `compileall` `rules.py` | OK |
| Canonical counts (entities=14, resources=12, rules=10, operations=11, workflows=7) | unchanged (definition assertions pass) |
| Fresh import | OK |
| Placeholder scan | none |

## Scope review

Modifications are strictly limited to:
- `cmm/domains/university/rules.py`
- `tests/domains/test_university_domain_{source_authority,contradiction,workload,deadlines,verification,integrity,rules}.py`
- `docs/remediation/phase-10.22-audit-v11-remediation-report.md` (this file)

**Not touched:** `permission_gate.py`, `permission_resolution.py`,
`university/operations.py`, `university/workflows.py`, `university/catalog.py`,
and all other domains. Untracked audit tarballs remain untouched.

**Git state:** None of the above is staged. No commit created. No push
performed. All changes remain UNSTAGED, per the remediation constraints.

## Recommendation

**READY FOR INDEPENDENT AUDIT V12**
