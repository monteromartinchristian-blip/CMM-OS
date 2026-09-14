# Phase 10.23 — Opposition Domain Implementation Plan

**Date:** 2026-08-13
**Phase:** 10.23 — Opposition Domain
**Canonical domain ID:** `domain:oppositions`
**Canonical operation prefix (registered):** `oppositions.`
**Frozen design:** `docs/superpowers/specs/2026-08-13-oppositions-domain-design.md`
**Status:** Implemented, pending audit (goal)

---

## 0. Baseline (verified before edits)

- Repository: `/Users/christian/CMM-OS`
- Branch: `feature/phase-10-domain-intelligence`; HEAD `69ff719` (frozen spec commit)
- Working tree clean; no pending Phase 10.23 changes.
- Domain suite: `4526 passed` (`tests/domains`).
- University domain tests: `968 passed`.
- Global suite: `9 failed, 10028 passed`. The 9 failures are unrelated to domain
  packs and are pre-existing (they involve git observer/executor and validation
  commit-gate tests that interact with the sandboxed git environment). They are
  documented, not hidden, and not caused by Opposition changes.
- Ruff: `0.16.1` installed. Python target: `>=3.10` (CI matrix runs 3.10/3.11/3.12).
- Validation pipeline: CI uses `python -m cmm validation run --policy ci --files <files>`.
  Local acceptance uses pytest + ruff + compileall.

## 1. Spec self-map

| Spec section | Production file(s) | Test file(s) |
|---|---|---|
| §5–7 catalog counts / entities | `catalog.py` | `test_oppositions_domain_catalog_reconciliation.py`, `_audit.py` |
| §6 entities | `catalog.py`, `resources.py` | `_resources.py` |
| §7 resources | `resources.py` | `_resources.py` |
| §8 profile | `profile.py` | `_profile.py` |
| §10 OfficialCallPriorityRule | `rules.py` | `_official_call_priority.py`, `_rules.py` |
| §11 TemporalValidityRule + monitoring | `rules.py` | `_temporal_validity.py`, `_verification.py` |
| §12 SyllabusCoverageRule | `rules.py` | `_syllabus_coverage.py` |
| §13 StudyFeasibilityRule + projections | `rules.py` | `_study_feasibility.py`, `_health_projection.py`, `_university_projection.py` |
| §14 MockExamInterpretationRule | `rules.py` | `_mock_exam.py` |
| §15 AlternativeRouteRule + strategy | `rules.py` | `_alternative_routes.py`, `_strategy.py` |
| §19 operations | `operations.py` | `_operations.py` |
| §20 workflows | `workflows.py` | `_workflows.py` |
| §22 permissions | `permissions.py` | `_permissions.py`, `_permission_gates.py`, `_permission_lifecycle.py` |
| §24 memory | `memory.py` | `_memory.py` |
| §25 presentation | `presentation.py` | `_presentation.py` |
| §26 trace | `trace.py` | `_trace.py` |
| §27 integration/rollback | `integration.py` | `_integration.py`, `_validation_first_matrix.py`, `_rollback.py` |
| §28 bootstrap/resolution | `bootstrap.py` | `_bootstrap.py`, `_resolution.py` |
| §46 public API/safety/clean import | `__init__.py` | `_public_api.py`, `_safety.py` |

## 2. Exact canonical contracts (must hold)

```text
entities   = 14
resources  = 11
rules      = 6
operations = 10
workflows  = 7
```

- Entities: opposition, public_body, call, exam, syllabus, topic, block,
  mock_exam, score, study_session, deadline, requirement, merit, alternative_route.
- Resource IDs (`oppositions.<kind>`): official_call, syllabus, regulation,
  study_plan, mock_exam, score_record, calendar_event, note, user_message,
  external_official_source, memory_entry.
- **Namespace reconciliation (discovered during implementation):** The frozen
  design recorded the canonical operation prefix as `opposition.` (singular).
  Repository inspection during implementation established that the shared
  `cmm/domains/operation_contracts.py` `DomainOperationDefinition` contract
  requires the operation-identifier prefix to equal the slug of `domain_id`
  (`domain:oppositions` → `oppositions`). The frozen notation was a
  design-document error; the valid registered namespace is consequently
  `oppositions.`. This is a documentation reconciliation with the pre-existing
  shared contract (not a Domain Intelligence architecture or behavior change),
  and the plural canonical prefix is used for every ID family (rules,
  operations, workflows, resources). The frozen semantic concepts/names are
  preserved exactly (6 rules, 10 operations, 7 workflow concepts).
- Rules: `oppositions.official_call_priority`, `oppositions.temporal_validity`,
  `oppositions.syllabus_coverage`, `oppositions.study_feasibility`,
  `oppositions.mock_exam_interpretation`, `oppositions.alternative_route`.
- Operation IDs: `oppositions.create_study_plan`, `oppositions.divide_syllabus`,
  `oppositions.track_progress`, `oppositions.review_mock_exam`,
  `oppositions.compare_bodies`, `oppositions.review_call`,
  `oppositions.generate_weekly_review`, `oppositions.identify_risks`,
  `oppositions.generate_revision_plan`, `oppositions.update_progress`.
- Workflow IDs: `oppositions.setup`, `oppositions.weekly_review`,
  `oppositions.mock_exam_review`, `oppositions.call_analysis`,
  `oppositions.syllabus_revision`, `oppositions.alternative_route_comparison`,
  `oppositions.exam_readiness`.

## 3. TDD task order

Each task is red → green → refactor. `catalog.py` must be green before the
rest of the pack because every other module derives identifiers from it.

1. **Catalog + definition contract** → `catalog.py`, `definition.py`,
   `test_oppositions_domain_catalog_reconciliation.py`, `_definition.py`, `_audit.py`.
2. **Resources + profile binding** → `resources.py`, `profile.py`, tests.
3. **Permissions** → `permissions.py`, permission gate/lifecycle tests.
4. **OfficialCallPriorityRule** → `rules.py` helpers + rule, tests.
5. **OppositionTemporalValidityRule + call-monitoring signal** → tests.
6. **SyllabusCoverageRule** → tests.
7. **StudyFeasibilityRule + Health/University projections** → tests.
8. **MockExamInterpretationRule** → tests.
9. **AlternativeRouteRule + versioned strategy preservation** → tests.
10. **Operations** → `operations.py`, tests.
11. **Workflows** → `workflows.py`, tests.
12. **Memory + presentation + trace** → tests.
13. **Integration + rollback + bootstrap + resolution + public API** → tests.
14. **Adversarial audit matrix / safety / clean import** → tests.
15. **Documentation + DP-023 matrix + roadmap state**.
16. **Full verification + self-audit + final commit**.

All public helpers and canonical `Rule.evaluate(context)` paths share the same
epistemic hardening: strict booleans (`is True`), order invariance, malformed
scope never global, provenance ≠ truth, caller `official` label not trusted,
equal-authority agreement/conflict handling, and no silent evidence deletion.

## 4. Verification ladder

```bash
.venv/bin/python -m pytest -q tests/domains/test_oppositions_domain_*.py     # focused
.venv/bin/python -m pytest -q tests/domains                                  # domain suite
.venv/bin/python -m pytest -q                                                # global suite
.venv/bin/ruff check cmm/domains/oppositions tests/domains/test_oppositions_domain_*.py
.venv/bin/python -m compileall -q cmm/domains/oppositions                    # compile
.venv/bin/python - <<'PY'                                                    # fresh import
import cmm.domains.oppositions
print("fresh_import=OK")
PY
git diff --check && git diff --cached --check                                 # whitespace
```

Expected pre-existing global failures (documented above, unrelated to domains):
9 git-observer/executor/validation tests.