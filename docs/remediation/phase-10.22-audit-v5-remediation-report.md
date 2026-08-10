# Phase 10.22 University Domain — Audit V5 Remediation Report

This report documents the small, fail-closed remediation for the remaining
Independent Audit V5 blockers. It does not close Phase 10.22: the roadmap
remains **Implemented, pending audit** and Independent Audit V6 decides
closure.

## V5-B1 — Usable evidence reference required for authority — FIXED

- Cause: a grounded, current source with a recognized official class could be
  selected despite a missing or blank source identifier. The canonical wrapper
  could then expose that claim's value while no authoritative source existed.
- Production change: current and temporally unresolved authority candidates now
  require the existing normalized usable `source_id`. The canonical rule only
  associates a claim with an authority result when that authoritative ID exists;
  unmatched evidence remains available in `matched_sources` diagnostically.
- Canonical production path: `AcademicSourceAuthorityRule.evaluate()` through
  `classify_academic_source_authority()`.
- Adversarial test: missing, empty, and blank claim IDs cannot resolve an
  official grade and trigger the existing `OFFICIAL_ONLY`, read-only
  verification signal when decision-critical. The same grounded claim with an
  ID remains authoritative.
- Behavior proven: a grounded label and source class are not traceable evidence.

## V5-B2 — Unknown ECTS states preserved as conditional — FIXED

- Cause: structurally valid records whose state was not an ECTS bucket were
  omitted from both totals and `unknown_records`, making the completion result
  overly definitive.
- Production change: the canonical ECTS parser treats only existing bucket
  states plus `failed` and `not_completed` as known. Unsupported, blank, or
  unknown states add their identity to `unknown_records`, block determinacy,
  and do not contribute earned credits. `unknown_records` is now sorted and
  stable under record permutation.
- Canonical production path: `EctsConsistencyRule.evaluate()` through
  `check_ects_consistency()`.
- Adversarial tests: `unknown` and `mystery` states block 174/180 completion
  conditionally and remain visible; a known `failed` record remains a
  deterministic non-earned state; unknown-record output is order invariant.
- Behavior proven: an unknown state is not silently interpreted as zero
  contribution or discarded evidence.

## V5-B3 — Malformed/invalid ECTS requirements fail closed — FIXED

- Cause: malformed `required_ects` values could raise during `int()` parsing;
  negative or zero requirements could become valid completion thresholds; the
  strict canonical rule eagerly parsed malformed legacy diagnostic aggregates.
- Production change: one small `_parse_ects_integer()` helper safely accepts
  valid integral ECTS values and returns `None` for malformed, boolean,
  fractional, or below-minimum values. Structured requirements require a
  positive parsed value. Canonical legacy diagnostic aggregates are safely
  parsed and cannot override valid structured records or requirements.
- Canonical production path: `EctsConsistencyRule.evaluate()` through
  `check_ects_consistency()`.
- Adversarial tests: nonnumeric, negative, and zero structured requirements
  return a blocked, unknown requirement without exceptions; malformed legacy
  values do not crash either structured completion or the no-structure path.
- Behavior proven: malformed requirement metadata cannot raise or fabricate a
  valid degree-completion threshold.

## Verification evidence

- Focused authority and ECTS tests: 49 passed.
- Focused verification and rule tests: 30 passed.
- University-domain suite: 364 passed.
- Domains suite: 3,922 passed.
- Full suite: 9,431 passed; two unrelated tests failed only because `pip-audit`
  could not resolve its advisory host (`socket.gaierror: [Errno 8] nodename nor
  servname provided, or not known`):
  `tests/validation/impact/test_change_impact_validation.py::test_change_impact_runs_through_validation_pipeline`
  and
  `tests/validation/static_analysis/test_static_analysis_pipeline_e2e.py::test_static_analysis_pipeline_e2e_reports_warnings`.
- Ruff and Ruff with `--target-version py310`: passed.
- `compileall`, dependency-direction test, fresh University import, and
  placeholder scan: passed.

No files were staged, no commit was created, and no push was performed.
