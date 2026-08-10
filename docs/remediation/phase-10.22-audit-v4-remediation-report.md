# Phase 10.22 University Domain — Audit V4 Remediation Report

This report documents the surgical remediation for the remaining Independent
Audit V4 findings. It does not close Phase 10.22: the roadmap remains
**Implemented, pending audit** and Independent Audit V5 decides closure.

## V4-B1 — Scope-aware authority/current value — FIXED

- Cause: canonical source authority grouped claims only by attribute and used
  the first claim's scope. Contradiction resolution also collapsed scoped
  values into one attribute-level scalar. Non-winning current sources were
  mislabeled as historical.
- Production change: canonical authority and conflict resolution now partition
  each attribute into deterministic effective scopes. Unscoped evidence retains
  the existing global applicability semantics. Contradiction metadata preserves
  independent values in `current_values_by_scope`; the legacy scalar remains
  only when exactly one scoped value exists. Historical IDs now require actual
  validated supersession or explicit expiration.
- Canonical rule paths: `AcademicSourceAuthorityRule.evaluate()` and
  `AcademicContradictionRule.evaluate()`.
- Adversarial tests: subject-a/subject-b facts are preserved in both input
  orders, with no contradiction, no verification, and no false historical IDs.
- Behavior proven: different scopes coexist deterministically without losing
  either current fact.

## V4-B2.1 — Validated supersession — FIXED

- Cause: a `supersedes` declaration alone demoted the named candidate;
  `superseded_by` was normalized but did not participate in resolution.
- Production change: both relation spellings normalize into one validation path.
  A replacement must be grounded, referenceable, currently applicable,
  scope-compatible, and at least as authoritative and specific in the existing
  attribute-specific hierarchy. A current source cannot become historical until
  that validation succeeds.
- Canonical rule path: `AcademicSourceAuthorityRule.evaluate()` through
  `classify_academic_source_authority()`.
- Adversarial tests: a personal note cannot supersede an official grade; a
  less-specific peer cannot replace a more-specific source; valid specific
  official supersession and the reciprocal `superseded_by` form preserve the
  older source as history.
- Behavior proven: declared supersession is evidence, not authority.

## V4-B2.2 — Unknown temporal fail-closed — FIXED

- Cause: grounded `temporal=unknown` candidates were silently excluded, which
  allowed a weaker valid source to become definitive.
- Production change: unknown-temporal grounded evidence remains in canonical
  authority evaluation. If it could match or outrank the selected current value
  and has an incompatible value, resolution remains unresolved unless a valid
  supersession relation settles it. Explicitly expired evidence remains
  non-current.
- Canonical rule paths: `AcademicSourceAuthorityRule.evaluate()` and
  `AcademicContradictionRule.evaluate()`.
- Adversarial tests: a valid calendar value conflicts with a stronger official
  call of unknown temporality, yielding no authoritative value and the existing
  `OFFICIAL_ONLY`, read-only verification need; an expired stronger call does
  not block the valid calendar value.
- Behavior proven: temporal unknown is not treated as non-current.

## V4-B2.3 — Missing authoritative fact value — FIXED

- Cause: a resolved authority source with `None` or a blank value followed the
  confirmed-official path even though the requested fact was absent.
- Production change: canonical authority now separates `authority_resolved`
  from `fact_value_known` and `fact_resolved`. Missing values are exactly
  `None` or blank strings; zero and `False` remain valid values. Missing
  decision-critical facts use the existing verification representation.
- Canonical rule path: `AcademicSourceAuthorityRule.evaluate()`.
- Adversarial tests: `None` and blank authoritative values remain unconfirmed
  and trigger missing-data verification; `0` and `False` remain confirmed fact
  values.
- Behavior proven: authoritative source identity does not fabricate a fact.

## V4-B3 — Strict structured ECTS grounding — FIXED

- Cause: strict structured credit completion accepted a `grounded=True` record
  without a usable source reference, and degree requirements did not require
  current temporal validity.
- Production change: records used for strict completion require identity,
  grounding, a usable source reference, current temporal validity, a valid
  credit amount, and recognized state semantics. Degree requirements require
  grounding, usable provenance, usable credits, and `valid` or existing
  `timeless` temporality; expired, future, unknown, and missing temporality do
  not establish a current requirement.
- Canonical rule path: `EctsConsistencyRule.evaluate()` through
  `check_ects_consistency()`.
- Adversarial tests: missing or blank record references, expired/future/unknown
  or missing requirement temporality all block completion; valid and timeless
  grounded referenced evidence still confirms 180 ECTS.
- Behavior proven: boolean grounding alone cannot establish current degree
  completion.

## Verification evidence

- Focused authority, contradiction, and ECTS tests: 58 passed.
- Focused verification and rule tests: 30 passed.
- University-domain suite: 356 passed.
- Domains suite: 3,914 passed.
- Full suite: 9,423 passed; two unrelated tests failed only because `pip-audit`
  could not resolve its advisory host (`socket.gaierror: [Errno 8] nodename nor
  servname provided, or not known`):
  `tests/validation/impact/test_change_impact_validation.py::test_change_impact_runs_through_validation_pipeline`
  and
  `tests/validation/static_analysis/test_static_analysis_pipeline_e2e.py::test_static_analysis_pipeline_e2e_reports_warnings`.
- Ruff and Ruff with `--target-version py310`: passed.
- `compileall`, dependency-direction test, and fresh University import: passed.
- Placeholder scan: clean.

No files were staged, no commit was created, and no push was performed.
