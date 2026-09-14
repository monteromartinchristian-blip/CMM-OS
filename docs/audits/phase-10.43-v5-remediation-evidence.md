# CMM OS — Phase 10.43 V5 Remediation Evidence (V4 → V5)

**Phase:** 10.43 — Integration with Validation System
**Cycle:** targeted V4 → V5 remediation (implementation-machine evidence only;
this file is **not** the independent audit)
**Date:** 2026-09-07
**Branch:** `feature/phase-10-domain-intelligence`

```text
V5_REMEDIATION_START_HEAD=26796777eb60d0ea332aae2d0a058f113881d458
HISTORICAL_V4_IMPLEMENTATION_HEAD=a7042780daf345da99862b033088d036598add48

BLOCKER_V4_01=REMEDIATED
BLOCKER_V4_02=REMEDIATED
BLOCKER_V4_03=REMEDIATED
BLOCKER_V4_04=REMEDIATED
MAJOR_V4_01=REMEDIATED
MAJOR_V4_02=REMEDIATED

PROJECT_IMPACT_OWNER=PHASE7_CHANGE_IMPACT_ANALYZER
DOMAIN_LOCAL_IMPACT_CLASSIFIER=REMOVED

PROJECT_HOST_ROOT=CANONICAL
CALLER_ROOT_DOWNGRADE=BLOCKED

PROJECT_POST_CHANGESET=CANONICAL
PROJECT_POST_CHANGED_FILES=ACTUAL_MUTATION
PROJECT_NESTED_CHANGED_FILE_SELECTION=PASS
PROJECT_AFFECTED_TEST_RUNTIME_GATE=PASS

PROJECT_MISSING_ROOT=FAIL_CLOSED
PROJECT_SNAPSHOT_FAILURE=FAIL_CLOSED
PROJECT_IMPACT_ANALYSIS_FAILURE=FAIL_CLOSED

PROJECT_ESCALATION_ROLLBACK=CANONICAL_RESTORATION_VERIFIED

AT_DP_043=PASS_CONNECTED
DP_043=IMPLEMENTED_PENDING_REAUDIT

V4_PROCESS_DEVIATION_GIT_RESET=DISCLOSED
V4_PROCESS_DEVIATION_EFFECT_ON_FINAL_BUNDLE=NONE_DETECTED
FINAL_REPOSITORY_INTEGRITY=VERIFIED
V5_PROHIBITED_GIT_OPERATIONS_USED=NO

PYTEST_PARSER_FIX=PRESERVED
RUFF_PARSER_FIX=PRESERVED

DOCUMENTATION_STATUS=IMPLEMENTED_PENDING_INDEPENDENT_AUDIT
```

## 1. What was remediated (per finding)

### BLOCKER-V4-03 — canonical Phase 7 impact ownership

- Deleted the Domain-owned classifier in
  `cmm/domains/validation_integration.py` (`derive_host_project_change_impact`
  no longer calls `diff_python_sources`, no longer branches on
  `public_api_changed`/`signature_changed`/`symbol_changes`/`import_changes`,
  and no longer scans `root.glob("*.py")`). Module source contains zero
  references to `diff_python_sources` (locked by
  `test_domain_layer_has_no_local_impact_classifier`).
- Added minimal public Phase 7 seams (additive only, no behavior change):
  `ChangeSetBuilder.build_from_snapshots()` and `scan_project_snapshot()` in
  `cmm/validation/impact/snapshots.py`, exported via
  `cmm/validation/impact/__init__.py`.
- Added thin adapter `project_policy_impact_from_canonical_result()` mapping
  canonical `ChangeImpactResult` fields (`requires_full_suite`,
  `uncertainty`, `public_api_changed`, `affected_symbols`, `change_type`) to
  the existing Project impact names. Conservative: any escalation signal
  escalates (`full`/`public`/`structural`); only a clean local change maps
  to `small`. No source/AST inspection in Domain code.
- Snapshot-pair derivation consumes
  `ChangeSetBuilder.build_from_snapshots → ChangeImpactAnalyzer.analyze →
  project_policy_impact_from_canonical_result`, unioned monotonically with
  caller file hints (host set never removable).

### BLOCKER-V4-02 — trusted Project root, fail closed

- Canonical owner selected: the **host-registered operation
  implementation** (read via the existing `InMemoryDomainOperationRegistry`
  seam) declares its execution root via `host_project_root`. Rationale: it
  is the same host object that performs the mutation, so the validated tree
  is the mutated tree; no new registry/resolver/store/context was created.
- `DefaultDomainOperationOrchestrator._resolve_trusted_project_root`
  enforces: unresolvable implementation → fail closed; undeclared host root
  → fail closed; nonexistent/non-directory host root → fail closed; caller
  metadata `validation_project_root` mismatch → request rejected (match
  required when a hint is present; omission is allowed and uses host truth).
- `_resolve_host_validation_root` routes `project.modify_code` through the
  trusted resolver; all other operations keep legacy behavior.
- Before-snapshot capture failure raises `DomainValidationIntegrationError`
  pre-mutation (nothing executes). Builder/analyzer/after-snapshot failures
  raise post-mutation and roll back. No `except: pass`, no `small` fallback
  on the authoritative path.

### BLOCKER-V4-01 — POST validation from the actual mutation ChangeSet

- Final ordering:
  `trusted root → before snapshot → PRE (PRE-only requirements) →
  mutation → after snapshot → canonical ChangeSet → canonical
  ChangeImpactResult → actual changed files + impact → POST requirements
  from post-change truth → same canonical AgentValidationAdapter →
  accept only on CONTINUE, else canonical rollback`.
- Only PRE requirements travel with the pre-mutation `AgentOperationRequest`;
  POST requirements are recomputed post-mutation
  (`_run_post_mutation_project_validation`) with `resource_scope` from the
  actual ChangeSet (monotonically unioned with caller hints). No second
  execution runtime; `cmm/agent_runtime` is untouched.
- Closure-critical proof: nested `src/pkg/module.py` mutation with no caller
  hints (and no top-level `*.py` files in the fixture) selects
  `tests/test_module.py` via canonical selection; `affected_tests == FAILED`
  blocks acceptance; repair restores acceptance.
- POST evidence is retrievable under idempotency key
  `post-mutation-<idempotency-key>` with the canonical validation report.

### BLOCKER-V4-04 — Project AT rebuilt on canonical truth

Preserved all valid scenarios (pack lifecycle, provider omission,
empty requirements, specialized gate, workflow, cross-domain, pytest/Ruff
parsers, anti-fragmentation). Project section now proves, on the real path:
nested src-layout regression blocked by `affected_tests` (A); decoy-root
rejection (B); structural/public escalation from the real
`ChangeImpactAnalyzer` with `POST_VALIDATION_FAILED` (D); derivation-failure
fail-closed (C); and mutated-file restoration through the canonical
`CheckpointRestorationRollbackExecutor` over real `TransactionManager` /
`CheckpointManager` / `CheckpointRestorationManager` with a whole-tree
resource provider (E). Rejection code changed from V4
`VALIDATION_ESCALATION_FAILED` to `POST_VALIDATION_FAILED`.

### MAJOR-V4-01 — documentation corrected

- `docs/reference/domain-validation-integration.md`: true impact owner,
  trusted-root rule, provisional-PRE vs authoritative-POST, fail-closed
  list, canonical-restoration rollback, updated AT description.
- `docs/reference/domain-intelligence-requirements-matrix.md`: DP-043 row
  now cites `ChangeImpactAnalyzer` (not `diff_python_sources`) plus trusted
  root and authoritative POST.
- `docs/roadmap/phase-10-domain-intelligence.md`: V5 runtime paragraph
  added; V4 paragraph retained as labeled history.
- Status everywhere remains `IMPLEMENTED_PENDING_INDEPENDENT_AUDIT`;
  `AT_DP_043=PASS_CONNECTED` is implementation evidence only.
- Ruff finding-code accuracy: the committed lint fallback emits
  `RUFF_LINT_FAILED` (`cmm/validation/tools/ruff.py`); this evidence uses
  that name. (The immutable V4 evidence file's `RUFF_EXECUTION_FAILED`
  wording is left untouched as historical record.)

### MAJOR-V4-02 — process deviation disclosed

- The V4 implementation transcript used prohibited `git reset` (plus index
  reconstruction and `git checkout <commit> -- <path>`) without explicit
  Christian authorization. This incident is historical and cannot be
  undone; it is disclosed here, not hidden.
- Effect assessment: the V4 exact-HEAD bundle was independently verified
  (`EXACT_HEAD=PASS`, `BUNDLE_SHA256=PASS` in the V4 audit); the V4 audit
  commit `26796777...` is an ancestor of the V5 HEAD (verified read-only
  below); all historical audit artifacts are byte-preserved; the quarantine
  stash is preserved. Therefore:
  `V4_PROCESS_DEVIATION_EFFECT_ON_FINAL_BUNDLE=NONE_DETECTED`.
- V5 used no prohibited Git operations: no `reset`, `clean`, `stash`,
  `worktree`, destructive `checkout`/`restore`, `push`, or `merge` (only
  read-only inspection, `add`, and `commit`).
  `V5_PROHIBITED_GIT_OPERATIONS_USED=NO`.

## 2. Commits created (V5)

```text
97ed2fb fix(domains): use canonical phase7 project change impact
b7726c6 fix(domains): fail closed on project host derivation
64a7117 test(domains): connect Project AT-DP-043 to canonical post-change validation
bf407ea docs(domains): align phase 10.43 docs with canonical project post validation
<evidence> docs(audit): record phase 10.43 v5 remediation evidence
```

## 3. Production files changed

```text
cmm/validation/impact/snapshots.py        (public build_from_snapshots + scan_project_snapshot)
cmm/validation/impact/__init__.py         (export scan_project_snapshot)
cmm/domains/validation_integration.py     (canonical mapping; fail-closed derive; classifier removed)
cmm/domains/operation_execution.py        (trusted root; fail-closed snapshots; PRE-only pre-mutation; authoritative POST)
```

`cmm/agent_runtime/**` untouched. `cmm/validation/**` otherwise untouched.

## 4. Tests changed/added

```text
tests/validation/impact/test_change_set_builder.py                    (+2: public seam RED/GREEN)
tests/domains/test_domain_validation_project_integration.py           (+8: 7 canonical-ownership incl. no-local-classifier lock; 1 nested POST-scope proof)
tests/domains/test_domain_validation_project_trusted_root.py          (new, +8: decoy/omit/match/missing/nonexistent/snapshot/builder/analyzer)
tests/domains/test_domain_validation_runtime_integration.py           (host fixture declaration only)
tests/domains/test_domain_validation_integration_dp043_acceptance.py  (escalation rewritten to canonical path; +4 V5 canonical AT incl. restoration proof)
tests/domains/test_domain_permission_gate.py                          (host fixture declaration only)
tests/domains/test_project_domain_closure_adversarial.py              (host fixture declarations only)
tests/domains/test_project_domain_dp030_acceptance.py                 (host fixture declaration only)
tests/domains/test_project_domain_self_development_e2e.py             (host_project_root parameter + wiring only)
```

Locked behaviors preserved and re-verified: pack lifecycle, provider
omission, empty requirements, specialized gate, workflow/cross-domain
bridges, pytest/Ruff parsers, anti-fragmentation, dp030 method-insertion
acceptance (`small` via canonical analyzer), e2e lifecycle.

## 5. Gate evidence (observed, not fabricated)

```text
FOCUSED_TESTS=138 PASS
  (.venv/bin/python -m pytest -q tests/validation/impact \
    tests/domains/test_domain_validation_project_integration.py \
    tests/domains/test_domain_validation_project_trusted_root.py \
    tests/domains/test_domain_validation_runtime_integration.py \
    tests/domains/test_domain_validation_integration_dp043_acceptance.py \
    tests/domains/test_domain_validation_cross_domain.py \
    tests/domains/test_domain_validation_result_integration.py)
PARSER_REGRESSIONS=7 passed/8 deselected + 14 passed (pytest/Ruff, V4 counts reproduced)
DP042_TARGETED=34 PASS
VALIDATION_SUITE=533 PASS
AGENT_RUNTIME_SUITE=3434 PASS
DOMAIN_SUITE=9676 PASS
GLOBAL_SUITE=15281 PASS (= V4 15260 + 21 new V5 tests, exact)

RUFF_FULL_GATE=841 findings (historical debt, unchanged from V4; not claimed PASS)
FORMAT_FULL_GATE=318 files need reformat (historical debt, unchanged from V4; not claimed PASS)
RUFF_V5_DELTA_GATE=PASS (0 new rule codes across all 13 changed/new Python files vs baseline HEAD)
FORMAT_V5_DELTA_GATE=PASS (0 format hunks overlap V5-changed lines)
COMPILEALL=PASS (.venv/bin/python -m compileall -q cmm tests)
GIT_DIFF_CHECK=PASS

WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED (quarantine: post-audit phase 10.32 uncommitted changes)
PUSH=NO
MERGE=NO
PHASE10_44=NOT_STARTED
```

## 6. Read-only repository integrity (observed)

```text
branch = feature/phase-10-domain-intelligence
V4 audit-report commit 26796777... is ancestor of V5 HEAD (merge-base --is-ancestor PASS)
V1/V2/V3/V4 audit reports preserved (untracked-by-V5; no modifications in V5 diff)
approved spec + plan preserved (no modifications in V5 diff)
no staged changes; worktree clean
```

## 7. Out-of-scope observations (not implemented)

- Full-tree Ruff (841) / format (318) debt predates V5 and was left
  untouched per the do-not-repair-unrelated-debt rule.
- `AgentExecutionAdapter` still records a vacuous empty-requirements POST
  result for mutation ops (internal PRE+POST structure unchanged); the
  authoritative post-mutation POST result (idempotency
  `post-mutation-*`) is the acceptance evidence.
- Structural/public Project mutations fail closed (`POST_VALIDATION_FAILED`)
  because stronger canonical policy steps have no executable Phase 9
  validator mapping; per the V4 audit this safe fail-closed is acceptable
  and was kept rather than inventing weaker mappings.

## 8. Independent-audit conclusions NOT claimed

```text
BLOCKERS/MINORS/DP-043=VERIFIED_EXISTING/AT-DP-043=PASS/CLOSURE_ELIGIBLE: not claimed.
NEXT=INDEPENDENT_CHATGPT_REAUDIT_V5
```
