# Phase 10.22 — Audit V10 Remediation Report

**Status:** Implemented, pending audit

**Scope:** `cmm/domains/university/rules.py` + affected University tests only

**HEAD:** `5541bca fix(domains): close phase 10.22 audit v9 findings`

## Invariants restored

- Helper safety does not depend on caller-supplied malformed flags.
- Absent Mapping is not equal to malformed Mapping.
- Numeric-looking string is not equal to numeric value.
- Truthy is not equal to boolean `True`.
- Mapping instance is not equal to semantically valid Workload evidence.
- Malformed runtime metadata is represented as structured uncertainty, not a runtime exception.

## V10-B1 — Deterministic helper boundary fail-closed validation — FIXED

**Root cause:** `classify_academic_source_authority`, `resolve_academic_conflict`,
`check_ects_consistency`, `evaluate_exam_attempt`, `evaluate_academic_workload`,
`evaluate_academic_dependency`, `classify_deadline_grounding`,
`evaluate_performance_capacity` and related helpers consumed raw caller
collections/Mappings before canonical wrappers had normalized them.

**Production change:** Added `_normalize_collection_value` for direct helper
collection arguments and `_MappingEvidence` / `_normalize_mapping` for
Mapping-shaped rule payloads. Helpers now derive malformed state from the
argument itself and return conservative structured results.

**Direct-helper RED tests:** malformed containers (`sources=7`, `claims=7`,
`records=7`, `attempts=7`, `hard_constraints=7`, `preferences=7`,
`scenarios=7`, `dependencies=7`, `academic_records=7`, `deadline=7`,
`performance_observation=7`, `degree_requirement=7`) and malformed members
(`(valid, 7)`, `(valid_scenario, 7)`, `[7]`).

**GREEN behavior:** no accidental `TypeError`/`ValueError`/`AttributeError`;
authority/contradiction/feasibility/completion remain unresolved or unknown.

## V10-B2 — Absent vs malformed Mapping preservation — FIXED

**Root cause:** `_mapping(metadata, key)` returned `None` both when the key was
absent and when the supplied value was not a Mapping.

**Production change:** Canonical rules now call `_normalize_mapping` first.
Absent payloads remain `RULE_NOT_APPLICABLE`; supplied malformed payloads
produce rule-specific conservative APPLIED results with
`malformed_mapping_evidence=True`.

**Canonical RED tests:** `deadline=7`, `ects=7`, `exam_attempt=7`, `workload=7`,
`dependency=7`, `performance_observation=7`, `integrity=7`,
`decision_support=7`.

**GREEN behavior:** all malformed Mapping payloads are not `RULE_NOT_APPLICABLE`;
genuine absence still returns `RULE_NOT_APPLICABLE`.

## V10-B3 — Strict no-coercion numeric/boolean semantics — FIXED

**Root cause:** `_parse_ects_integer` used `int(value)`, and boolean-bearing
fields such as `grounded_passed`, `regulation_active`, and Workload hard
constraint actual/expected comparisons used truthiness.

**Production change:** `_parse_ects_integer` now accepts only native `int`
(rejecting `bool`, strings, floats, Decimal and non-finite values). The strict
boolean path requires `is True` / `is False`; malformed values produce unknown
state. Workload boolean hard-constraint comparisons require both sides to be
exact booleans.

**Direct-helper/canonical RED tests:** `completed="abc"`, `ects="30"`,
`required="180"`, `max_attempts="3"`, `grounded_passed="false"/"true"/1/0`,
`regulation_active="false"/"true"/1/0`, Workload `prereq_met="false"` vs
`expected=True`.

**GREEN behavior:** numeric strings are never implicitly accepted; malformed
booleans never grant satisfaction or active regulation status.

## V10-B4 — Workload minimum semantic element validation — FIXED

**Root cause:** `require_mapping_elements=True` proved Mapping membership but
not usable preference/scenario evidence, and unknown preference direction
silently behaved as minimize/ascending.

**Production change:** Workload now validates minimum semantic shape:

- Preferences must have a usable `dimension`.
- Direction is closed over `maximize` / `minimize`; omitted direction keeps the
  documented default; unknown directions make ranking incomplete.
- Scenarios participating in a set must have a usable string `id`.

**RED tests:** `preferences=[{}]`, `scenarios=[{}, valid]`,
`direction="sideways"`; positive regressions for omitted direction and closed
maximize/minimize direction.

**GREEN behavior:** malformed semantic elements preserve uncertainty and no
deterministic proposal is emitted.

## Verification

- Focal University suites: passed
- University suite: passed
- Domains suite: passed
- Global suite: passed
- Ruff (default + py310): passed
- compileall: passed
- dependency direction: passed
- fresh import: OK
- placeholder scan: clean
- diff check: clean

## Scope

- Production: `cmm/domains/university/rules.py`
- Tests: affected University domain test files
- Documentation: this report
- Permission architecture and other domains: untouched

No files staged. No commit created. No push performed.
