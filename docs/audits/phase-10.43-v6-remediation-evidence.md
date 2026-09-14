# CMM OS — Phase 10.43 V6 Remediation Evidence (V5 → V6)

**Phase:** 10.43 — Integration with Validation System
**Cycle:** targeted V5 → V6 transaction preflight remediation
  (implementation-machine evidence only; this file is **not** the independent
  audit)
**Date:** 2026-09-07
**Branch:** `feature/phase-10-domain-intelligence`

```text
V6_REMEDIATION_START_HEAD=ebbfcdc7ce1f736ea31ac507804a009fc0885883
HISTORICAL_V5_IMPLEMENTATION_HEAD=1d4cb19855aaedae5eccbde3e97d700bf7a363ce

MAJOR_V5_01=REMEDIATED

PROJECT_PREFLIGHT_BEFORE_TRANSACTION=PASS
PROJECT_PREFLIGHT_FAILURE_ACTIVE_TRANSACTIONS=0
PROJECT_PREFLIGHT_FAILURE_ORPHAN_CHECKPOINTS=0
VALID_PROJECT_TRANSACTION_LIFECYCLE=PASS

DECOY_ROOT_PREFLIGHT_TRANSACTION_LEAK=BLOCKED
MISSING_HOST_ROOT_TRANSACTION_LEAK=BLOCKED
MISSING_PROVIDER_TRANSACTION_LEAK=BLOCKED
BEFORE_SNAPSHOT_FAILURE_TRANSACTION_LEAK=BLOCKED

POST_VALIDATION_ROLLBACK_DOMAIN_STATUS=ROLLED_BACK
POST_VALIDATION_ROLLBACK_TRANSACTION_STATE=COMPENSATED
POST_VALIDATION_ROLLBACK_FILE_RESTORATION=PASS
VALID_MUTATION_TRANSACTION_STATE=COMMITTED

DP_043=VERIFIED_EXISTING_PENDING_FINAL_REAUDIT
AT_DP_043=PASS_CONNECTED

PYTEST_PARSER_FIX=PRESERVED
RUFF_PARSER_FIX=PRESERVED
PROJECT_IMPACT_OWNER=PHASE7_CHANGE_IMPACT_ANALYZER
PROJECT_POST_CHANGED_FILES=ACTUAL_MUTATION
PROJECT_HOST_ROOT=CANONICAL

FOCUSED_TESTS=144 PASS
VALIDATION_SUITE=533 PASS
AGENT_RUNTIME_SUITE=3434 PASS
DOMAIN_SUITE=9682 PASS
GLOBAL_SUITE=15287 PASS

RUFF_FULL_GATE=841 findings (historical debt; not claimed PASS)
FORMAT_FULL_GATE=318 files need reformat (historical debt; not claimed PASS)
RUFF_V6_DELTA_GATE=PASS
FORMAT_V6_DELTA_GATE=PASS

COMPILEALL=PASS
GIT_DIFF_CHECK=PASS

V6_PROHIBITED_GIT_OPERATIONS_USED=NO
WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED
PUSH=NO
MERGE=NO
```

Note on `POST_VALIDATION_ROLLBACK_TRANSACTION_STATE`: the Domain operation
result status is `ROLLED_BACK`. The canonical `TransactionManager` boundary
and execution state for the orchestrator's `kind="compensable"` transaction
is `COMPENSATED` (via `mark_rollback_started` → `COMPENSATING` then
`mark_rolled_back` → `COMPENSATED`). Both denote successful canonical
rollback with zero `ACTIVE` residue; file content restoration is verified.
No `ACTIVE` transaction or orphan checkpoint remains.

## 1. Root cause (MAJOR-V5-01)

`DefaultDomainOperationOrchestrator.execute()` in
`cmm/domains/operation_execution.py` called
`TransactionManager.start_transaction()` (which stores an `ACTIVE` boundary
plus an `ACTIVE` checkpoint via `CheckpointManager.create_checkpoint`)
**before** invoking pre-mutation fail-closed preflight:

- `_resolve_host_validation_requirements()` (missing provider,
  missing host implementation, missing/invalid host root, caller
  decoy-root mismatch, unmappable mandatory pre-validation policy step),
- `_resolve_host_validation_root()` (same trusted-root checks),
- canonical `scan_project_snapshot(..., source="before")`
  (`before_snapshot_failed`).

Those exceptions propagated with no `mark_failed` / `mark_rollback_started`
/ `rollback` / `mark_rolled_back` / `commit` cleanup, leaving
`TransactionStatus.ACTIVE` + retained checkpoint despite no mutation.

RED proof (pre-fix): the 4 new connected tests failed with
`assert ['txb-...'] == []` — one leaked `ACTIVE` transaction each.

## 2. Execution-order change

New ordering in `DefaultDomainOperationOrchestrator.execute()`:

```text
availability / permission gate
→ validation/provider preflight
  (_resolve_host_validation_requirements)
→ trusted Project root resolution
  (_resolve_host_validation_root, match-only caller hint)
→ pre-validation requirement materialization
→ required canonical before snapshot
→ ONLY THEN start_transaction/checkpoint
→ construct AgentOperationRequest (precomputed requirements/root)
→ PRE validation (AgentExecutionAdapter)
→ mutation
→ authoritative POST validation
  (_run_post_mutation_project_validation)
→ commit or rollback
```

No new transaction manager, no new preflight engine, no duplicated
validation logic. The same three resolution calls were moved before
`start_transaction`; `AgentOperationRequest` now consumes the precomputed
`validation_requirements` / `validation_project_root`. Post-mutation
`_run_post_mutation_project_validation`, `_failure_with_rollback`,
`_cancel_with_rollback`, `commit`, and canonical restoration are untouched.

## 3. Production files changed

```text
cmm/domains/operation_execution.py (only)
```

`cmm/agent_runtime/**` untouched. `cmm/validation/**` untouched.
`cmm/domains/validation_integration.py` untouched (Phase 7 ownership,
trusted-root semantics, authoritative POST preserved).

## 4. Transaction/checkpoint APIs used

Existing public lifecycle only; no private-dict manipulation:

```text
TransactionManager.start_transaction
TransactionManager.register_operation
TransactionManager.commit
TransactionManager.mark_rollback_started
TransactionManager.mark_rolled_back
TransactionManager.mark_failed (via getattr guard in rollback paths)
TransactionManager.get_boundary / get_state (tests only)
CheckpointManager.create_checkpoint (via start_transaction)
InMemoryCheckpointRepository.find_active (tests only)
CheckpointRestorationRollbackExecutor.rollback (unchanged rollback path)
```

No ad hoc deletion of `_boundaries` / `_states` / `_checkpoints`.

## 5. RED tests (prior leak) and post-fix assertions

New file `tests/domains/test_project_preflight_transaction_lifecycle.py`
(+6 tests, real `TransactionManager` / `CheckpointManager` /
`CheckpointRestorationManager` /
`CheckpointRestorationRollbackExecutor` + whole-tree resource provider,
same connected shape as AT-DP-043):

```text
test_project_decoy_root_preflight_does_not_leave_active_transaction
test_project_missing_host_root_preflight_does_not_leave_active_transaction
test_project_missing_provider_preflight_does_not_leave_active_transaction
test_project_before_snapshot_failure_does_not_leave_active_transaction
test_valid_project_mutation_commits_transaction
test_post_validation_rejection_rolls_back_and_restores
```

Pre-fix RED: the 4 preflight tests failed with one leaked `ACTIVE`
transaction each (`assert ['txb-...'] == []`); the 2 lifecycle tests passed.

Post-fix GREEN: all 6 pass. Each preflight failure asserts:

```text
pytest.raises(DomainValidationIntegrationError)
implementation execute call count = 0
_ACTIVE transaction ids via _boundaries/get_state = []
len(_boundaries) = 0
checkpoint_repo.find_active() = ()
len(_checkpoints) = 0
```

Positive lifecycle:

```text
valid mutation → COMPLETED, execute called, transaction COMMITTED
  (boundary + state), zero ACTIVE
post-validation rejection (nested affected-test failure) →
  domain ROLLED_BACK, file bytes restored, canonical transaction
  COMPENSATED (compensable kind), zero ACTIVE
```

Canonical ACTIVE enumeration uses manager state (`_boundaries` +
`get_state` status `== "active"`) and repository `find_active()`; no mock
counter.

## 6. Gate evidence (observed, not fabricated)

```text
FOCUSED_TESTS=144 PASS
  (.venv/bin/python -m pytest -q tests/validation/impact
    tests/domains/test_domain_validation_project_integration.py
    tests/domains/test_domain_validation_project_trusted_root.py
    tests/domains/test_domain_validation_runtime_integration.py
    tests/domains/test_domain_validation_integration_dp043_acceptance.py
    tests/domains/test_domain_validation_cross_domain.py
    tests/domains/test_domain_validation_result_integration.py
    tests/domains/test_project_preflight_transaction_lifecycle.py)
VALIDATION_SUITE=533 PASS (.venv/bin/python -m pytest -q tests/validation)
AGENT_RUNTIME_SUITE=3434 PASS (.venv/bin/python -m pytest -q tests/agent_runtime)
DOMAIN_SUITE=9682 PASS (.venv/bin/python -m pytest -q tests/domains)
GLOBAL_SUITE=15287 PASS (.venv/bin/python -m pytest -q)
  (= V5 15281 + 6 new V6 tests, exact)

RUFF_FULL_GATE=841 findings (historical debt; .venv/bin/python -m ruff check .)
FORMAT_FULL_GATE=318 files need reformat (historical debt;
  .venv/bin/python -m ruff format --check .)
RUFF_V6_DELTA_GATE=PASS
  (.venv/bin/python -m ruff check cmm/domains/operation_execution.py
    tests/domains/test_project_preflight_transaction_lifecycle.py → All checks passed)
FORMAT_V6_DELTA_GATE=PASS
  (.venv/bin/python -m ruff format --check <same two files> → 2 files already formatted)
COMPILEALL=PASS (.venv/bin/python -m compileall -q cmm tests)
GIT_DIFF_CHECK=PASS

WORKTREE=CLEAN (after commits)
QUARANTINE_STASH=PRESERVED (quarantine: post-audit phase 10.32 uncommitted changes)
PUSH=NO
MERGE=NO
PHASE10_44=NOT_STARTED
```

Parser preservation (untouched, re-verified via suites): pytest/Ruff parser
regressions remain in the passing validation/domain suites; no parser files
changed in V6 diff.

## 7. Commits created (V6)

```text
fix(domains): run project preflight before transaction start
test(domains): cover project preflight transaction lifecycle
docs(audit): record phase 10.43 v6 remediation evidence
```

Or atomically combined if preferred; all three concerns are present and
pushed as committed HEAD history (no push to remote).

## 8. Read-only repository integrity (observed)

```text
branch = feature/phase-10-domain-intelligence
V6 start HEAD ebbfcdc... is ancestor of V6 HEAD (merge-base --is-ancestor PASS)
V1/V2/V3/V4/V5 audit reports preserved (no modifications in V6 diff)
approved spec + plan preserved (no modifications in V6 diff)
no staged changes; worktree clean
quarantine stash preserved
Phase 10.44 not started
```

## 9. Out-of-scope observations (not implemented)

- Full-tree Ruff (841) / format (318) debt predates V6 and was left
  untouched per the do-not-repair-unrelated-debt rule; V6 delta is clean.
- Compensable-kind rollback yields canonical `COMPENSATED` transaction
  state with domain `ROLLED_BACK`; this is existing manager semantics,
  preserved unchanged.
- No Phase 7 / Phase 9 ownership, policy mapping, parser, pack, workflow,
  cross-domain, specialized-gate, or commit-gate behavior was altered.

## 10. Independent-audit conclusions NOT claimed

```text
BLOCKERS/MAJORS/MINORS/DP-043=VERIFIED/AT-DP-043=PASS/CLOSURE_ELIGIBLE: not claimed.
NEXT=INDEPENDENT_CHATGPT_FINAL_REAUDIT_V6
```
