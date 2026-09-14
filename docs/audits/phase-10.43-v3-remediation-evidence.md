# Phase 10.43 V3 Remediation Evidence (Implementation Machine)

Implementation-machine evidence, not an independent audit. Only the
independent ChatGPT re-audit decides final `BLOCKERS`, `MAJORS`,
`CLOSURE_ELIGIBLE`, `DP-043=VERIFIED_EXISTING`, and `AT-DP-043=PASS`.

```text
REMEDIATION_START_HEAD=351bd0f6f6bd69aeff09700bcf174ec83550e784
INTERRUPTED_CONTINUATION_HEAD=54a0f3ec239dda719ed8021a819373d76d1492b3
HISTORICAL_V2_HEAD=6faa26fec6fd835ca0f47b1c093020c83bddb67a
REMEDIATED_HEAD=d27520f8bd3c1108b3604053086746c03782bddc

BLOCKER_V2_01=REMEDIATED
BLOCKER_V2_02=REMEDIATED
BLOCKER_V2_03=REMEDIATED
MAJOR_V2_01=REMEDIATED
MAJOR_V2_02=REMEDIATED

PROVIDER_OMISSION=FAIL_CLOSED
EMPTY_RUNTIME_REQUIREMENTS=FAIL_CLOSED
SPECIALIZED_RESULT_GATE=UNCONDITIONAL

PROJECT_DOMAIN_CHANGE_POLICY_REAL_PATH=PASS
PROJECT_AFFECTED_TEST_RUNTIME_GATE=PASS
PROJECT_IMPACT_ESCALATION_RUNTIME=PASS
PROJECT_DOWNGRADE_ATTEMPT=BLOCKED
PROJECT_COMMIT_GATE_OWNERSHIP=PASS

AT_DP_043=PASS_CONNECTED
DP_043=IMPLEMENTED_PENDING_REAUDIT

PHASE10_43_FOCUSED_TESTS=281 PASS
VALIDATION_SUITE=527 PASS
AGENT_RUNTIME_SUITE=3434 PASS
DOMAIN_SUITE=9653 PASS
GLOBAL_SUITE=15252 PASS

RUFF_FULL_COMMAND=.venv/bin/python -m ruff check cmm tests
RUFF_FULL_GATE=FAIL_PRE_EXISTING_702
FORMAT_FULL_COMMAND=.venv/bin/python -m ruff format --check cmm tests
FORMAT_FULL_GATE=FAIL_PRE_EXISTING_185

COMPILEALL=PASS
GIT_DIFF_CHECK=PASS

DOCUMENTATION_STATUS=IMPLEMENTED_PENDING_INDEPENDENT_AUDIT
```

## Scope notes (auditable, no fabrication)

- `PHASE10_43_FOCUSED_TESTS=281` covers:
  `test_domain_validation_project_integration.py`,
  `test_domain_validation_runtime_integration.py`,
  `test_domain_validation_integration_dp043_acceptance.py`,
  `test_validation_integration.py` (agent_runtime),
  `test_domain_validation_policy_bindings.py`,
  `test_domain_validation_integration_adversarial.py`,
  `test_domain_validation_cross_domain.py`,
  `test_domain_validation_pack_integration.py`,
  `test_domain_validation_result_integration.py`.
- `VALIDATION_SUITE=527` is `tests/validation`.
- `AGENT_RUNTIME_SUITE=3434` is `tests/agent_runtime`.
- `DOMAIN_SUITE=9653` is `tests/domains`.
- `GLOBAL_SUITE=15252` is full `pytest -q -p no:cacheprovider`.
- Phase 10.41 regressions: 5 passed
  (`test_domain_agent_runtime_dp041_acceptance.py`).
- Phase 10.42 regressions: 34 passed
  (`test_domain_planner_workflow_dp042_acceptance.py`).
- Historical Project regressions preserved and green after V3:
  `test_project_domain_closure_adversarial.py`,
  `test_project_domain_dp030_acceptance.py`,
  `test_project_domain_self_development_e2e.py` (37 passed combined).
  Two e2e fixtures required canonical formatter compliance (double quotes
  plus `ruff format` after `ast.unparse` single-quote normalization) because
  the canonical `small_change` policy now governs the real mutation path;
  intent preserved, no policy weakened.

## Full Ruff/format reality (pre-existing, outside V3 scope)

- No `[tool.ruff]` config exists in the repository; `CONTRIBUTING.md`
  requires changed-files `ruff check`/`format --check`, and CI
  (`.github/workflows/ci.yml`) runs only `compileall` plus `pytest`.
  The mission's full `cmm tests` scope was still executed for evidence.
- `RUFF_FULL_GATE=FAIL_PRE_EXISTING_702`: 702 errors across untouched
  files (e.g. `tests/validation/custom_validators/*`, import sorting
  `I001`, unused imports `F401` pre-existing). V3 production delta is
  clean: `ruff check` on
  `cmm/agent_runtime/validation_execution_adapter.py`,
  `cmm/domains/operation_contracts.py`,
  `cmm/domains/validation_integration.py` passes; V3 test delta
  (`test_domain_validation_project_integration.py`,
  `test_domain_validation_integration_dp043_acceptance.py`) passes after
  the committed fixes.
- `FORMAT_FULL_GATE=FAIL_PRE_EXISTING_185`: 185 files would be reformatted
  repository-wide pre-existing. V3 delta files are formatted
  (`ruff format --check` passes on the five V3 core files after commit
  `d27520f`).
- `COMPILEALL=PASS` via `.venv/bin/python -m compileall -q cmm`.
- `GIT_DIFF_CHECK=PASS` via `git diff --check` on a clean worktree.

## Commits after continuation start (54a0f3e)

```text
809d261 fix(domains): apply project change policy to mutation runtime
26df740 test(domains): complete AT-DP-043 fail-closed coverage
cff4b36 docs(domains): align phase 10.43 docs with v3 remediation
d27520f style(domains): format validation_integration for v3 gate
```

## Out-of-scope observations (not implemented)

- Phase 7 `affected_tests`/`unit_tests` pytest result parsing
  (`parse_pytest_result` exists but is never wired into
  `CommandResultParser`/pipeline; pytest exit 1 stays `PASSED`) and Ruff
  lint JSON list-vs-dict (`parse_ruff_results` expects `{"messages": ...}`
  but current `ruff check --output-format json` emits a list) were observed
  while proving the affected-test gate. V3 proves the gate via the real
  `project.modify_code` path with valid syntax/AST plus failing affected
  test plus canonical formatter enforcement (all part of `small_change`);
  fixing the Phase 7 parsers is left for a separate phase.
- Kernel `PythonEditor._apply_transform` uses `ast.unparse`, which
  normalizes quotes to single; canonical `ruff format` requires double.
  V3 e2e fixtures format after insertion; fixing the editor is out of scope.
