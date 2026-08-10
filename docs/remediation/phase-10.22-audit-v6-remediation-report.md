# Phase 10.22 University Domain — Audit V6 Remediation

Date: 2026-08-10

This remediation is limited to the five Independent Audit V6 blockers. The
roadmap remains **Implemented, pending audit**; Independent Audit V7 decides
closure.

## V6-B1.1 — Deadline traceable grounding — FIXED

- Cause: grounded provenance, an appropriate source class, and current
  temporality could confirm a deadline without a usable evidence reference.
- Production change: `_deadline_confirmed_by()` now also requires a usable
  `source_reference` or `source_ref`; no identifier is synthesized.
- Canonical rule path: `AcademicDeadlineRule.evaluate()` through
  `university.academic_deadline` in `build_university_rules()`.
- Adversarial test: an otherwise current official critical deadline with a
  missing or blank reference returns `DEADLINE_VERIFICATION_NEEDED`.
- Behavior proven: an unreferenced official deadline is not confirmed; the
  equivalent referenced deadline remains `confirmed_official` without a
  verification need.

## V6-B1.2 — Integrity traceable grounding — FIXED

- Cause: an otherwise valid caller mapping could make a restriction operative
  without traceable regulatory evidence.
- Production change: `evaluate_academic_integrity()` now requires a usable
  `source_reference` or `source_ref` before a grounded official restriction can
  be operative.
- Canonical rule path: `AcademicIntegrityRule.evaluate()` through
  `university.academic_integrity` in `build_university_rules()`.
- Adversarial test: missing and blank restriction references preserve Mode C
  permissiveness even when course, assessment, and requested action match.
- Behavior proven: unreferenced restrictions cannot prohibit assistance;
  referenced, scoped restrictions continue to prohibit their listed action.

## V6-B2 — ExamAttempt fail-closed semantics — FIXED

- Cause: a missing limit became an implicit within-limits conclusion; malformed
  limits could raise or coerce; missing or unsupported kinds defaulted to an
  ordinary consumed attempt.
- Production change: `evaluate_exam_attempt()` reuses the safe positive integer
  parser for limits, reports `limit_unknown`, and records unsupported/missing
  kinds or statuses as `unknown_attempts` / `attempt_evidence_unknown` instead
  of counting them. `ExamAttemptRule` routes either uncertainty to official
  verification rather than a permitted-limit conclusion.
- Canonical rule path: `ExamAttemptRule.evaluate()` through
  `university.exam_attempt` in `build_university_rules()`.
- Adversarial test: missing limits and `"abc"`, `-1`, `0`, `1.5`, `True`, and
  `Decimal("Infinity")` all remain unresolved without raising; `"mystery"`,
  missing kinds, and opaque non-mapping entries are not counted as ordinary.
- Behavior proven: valid ordinary/reassessment evidence and valid limits retain
  their prior deterministic consumed, remaining, and exceeded-limit behavior.

## V6-B3.1 — Workload malformed/incomplete evidence — FIXED

- Cause: preference ranking sorted missing values and raised `TypeError`; the
  canonical wrapper directly coerced malformed ECTS metadata.
- Production change: safe numeric parsing rejects bool, non-finite, negative,
  and non-numeric workload values. Structured ranking only orders scenarios
  with known comparable non-negative numeric values and exposes
  `ranking_incomplete`; malformed canonical metadata becomes
  `feasibility_uncertain` with `numeric_metadata_unknown`.
- Canonical rule path: `AcademicWorkloadRule.evaluate()` through
  `university.academic_workload` in `build_university_rules()`.
- Adversarial test: a feasible scenario without `hours` alongside one with
  `hours=5` yields no ranking rather than an exception; malformed `total_ect`
  and `full_time_ect` yield structured uncertainty.
- Behavior proven: complete comparable scenarios still rank deterministically,
  and incomplete-ranking results remain semantic-order invariant.

## V6-B3.2 / V6-B3.3 / V6-B3.4 — Dependency fail-closed evidence — FIXED

- Cause: a prerequisite without an ID was silently skipped; credit thresholds
  used direct coercion; identityless or unknown-state academic records could
  affect credited totals.
- Production change: `evaluate_academic_dependency()` tracks anonymous
  prerequisite edges as a blocking diagnostic count without fabricating an
  academic identity, uses the safe positive integer parser for thresholds, and
  counts credit evidence only when it is identified, grounded, referenced,
  current, state-supported, and non-negative. Incomplete credit evidence makes
  an otherwise unsatisfied threshold unknown rather than satisfied or open.
- Canonical rule path: `AcademicDependencyRule.evaluate()` through
  `university.academic_dependency` in `build_university_rules()`.
- Adversarial test: missing IDs remain blocking; `-1`, `0`, `1.5`, `True`, and
  `"abc"` thresholds cannot satisfy; an identityless 180-credit record and an
  unknown credit state cannot meet a 180-credit prerequisite.
- Behavior proven: six identified, grounded, referenced, current completed
  30-credit records satisfy a valid 180-credit threshold.

## Verification evidence

- Focal remediation tests: `96 passed`.
- University verification/rules tests: `30 passed`.
- University suite: `392 passed`.
- Domains suite: `3,950 passed`.
- Global suite: `9,459 passed`, with exactly two known unrelated validation
  tests failing because `pip_audit` cannot resolve `pypi.org`:
  `tests/validation/impact/test_change_impact_validation.py::test_change_impact_runs_through_validation_pipeline`
  and
  `tests/validation/static_analysis/test_static_analysis_pipeline_e2e.py::test_static_analysis_pipeline_e2e_reports_warnings`.
  The exact network error is `Failed to resolve 'pypi.org' ([Errno 8] nodename
  nor servname provided, or not known)` while requesting
  `/pypi/annotated-types/0.8.0/json`.
- Ruff (default and Python 3.10 target): clean.
- `compileall`, dependency-direction test, fresh University import, and the
  requested placeholder scan: passed.

No files were staged. No commit was created. No push was performed.
