# CMM OS — Phase 10.22 University Domain — Audit V3 Remediation Report

**Date:** 2026-08-10
**Branch:** `feature/phase-10-domain-intelligence`
**HEAD:** `8805971 fix(domains): complete phase 10.22 audit remediation`
**Roadmap:** `Implemented, pending audit`

This remediation is limited to the three Independent Audit V3 semantic
blockers and the explicitly permitted conditional-dependency diagnostic
cleanup. No permissions, cross-domain code, architecture, canonical counts,
operations, workflows, or other domains were changed. No Git staging,
commit, push, reset, restore, checkout, clean, stash, or rebase was performed.

## Findings

| Finding | Status | Canonical production-path evidence |
|---|---|---|
| V3-B1 — Equal-authority agreement falsely classified as conflict | **FIXED** | `AcademicSourceAuthorityRule.evaluate()` now preserves claim values and classifies equal top values as corroboration with `authority_conflict=False`, deterministic `supporting_source_ids`, and no conflict verification trigger. |
| V3-B2 — Multi-source contradiction resolution depended on input order | **FIXED** | `AcademicContradictionRule.evaluate()` now gathers all relevant evidence per attribute, invokes the shared authority classifier once over the complete current claim set, derives the current value from the complete set, preserves conflict evidence, and sorts output deterministically. |
| V3-B3 — Canonical ECTS accepted ungrounded legacy aggregates | **FIXED** | `EctsConsistencyRule.evaluate()` always invokes strict grounding. Legacy aggregates remain diagnostic only; completion requires grounded structured records and a grounded degree requirement. Missing grounding exposes a verification need and gap. |
| Conditional prerequisite IDs absent from canonical `blocked_ids` | **FIXED** | The canonical dependency finding now includes open, unknown, and conditional prerequisite IDs in deterministic references; decision semantics are unchanged. |

## Production-path test evidence

- `tests/domains/test_university_domain_source_authority.py`: **15 passed**, including equal-authority same-value corroboration.
- `tests/domains/test_university_domain_contradiction.py`: **15 passed**, including the three-source `18 / 17 / 18` case, all six permutations, highest-authority corroboration, and unresolved equal-authority conflict.
- `tests/domains/test_university_domain_ects.py`: **14 passed**, including the legacy aggregate bypass and grounded positive path.
- `tests/domains/test_university_domain_dependencies.py`: **14 passed**, including conditional prerequisite diagnostics.
- Verification/rules integration tests: **30 passed**.
- Combined focal and optional remediation suites: **58 passed**.

The RED tests were observed failing before each corresponding production fix;
the final tests exercise `rule.evaluate(context)` through the canonical rule
registry rather than testing helpers alone.

## Verification

| Check | Result |
|---|---|
| University domain tests | **342 passed** |
| Domain tests | **3900 passed** |
| Full suite | **9409 passed, 2 failed** |
| Ruff default target | **Clean** |
| Ruff `--target-version py310` | **Clean** |
| `compileall -q cmm tests` | **OK** |
| Dependency direction | **1 passed** |
| Fresh `import cmm.domains.university` | **OK** |
| Placeholder scan | **No matches** |
| Canonical counts | **14 entities / 12 resources / 10 rules / 11 operations / 7 workflows** |

The two full-suite failures are unrelated validation-pipeline E2E tests:
`test_change_impact_runs_through_validation_pipeline` and
`test_static_analysis_pipeline_e2e_reports_warnings`. Their default pipeline
stops at `pip_audit`, which attempts to reach PyPI and fails DNS/network
resolution in this restricted environment; subsequent nested test steps are
skipped. No University remediation code is involved, and no unrelated fix was
made.

## Scope and review state

Expected remediation files are limited to:

```text
cmm/domains/university/rules.py
tests/domains/test_university_domain_source_authority.py
tests/domains/test_university_domain_contradiction.py
tests/domains/test_university_domain_ects.py
tests/domains/test_university_domain_dependencies.py
docs/remediation/phase-10.22-audit-v3-remediation-report.md
```

The roadmap remains **Implemented, pending audit**. Independent Audit V4 and
the human reviewer remain the closure authority.
