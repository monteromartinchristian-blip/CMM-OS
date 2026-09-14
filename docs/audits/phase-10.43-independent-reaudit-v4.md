# CMM OS — Phase 10.43 Independent Re-Audit V4

**Phase:** 10.43 — Integration with Validation System
**Audit:** Independent ChatGPT Re-Audit V4
**Date:** 2026-09-07
**Bundle:** `phase-10.43-audit-v4-a7042780daf345da99862b033088d036598add48.tar.gz`
**Audited implementation HEAD:** `a7042780daf345da99862b033088d036598add48`
**Bundle SHA-256:** `f30f6bc201374027b51c1f776784a02b19392bce81b819cc3875d296dd65ba9b`
**Historical V3 implementation HEAD:** `edfd853c3b6197a7e84137e538ec6f37f5b02230`
**Design Point:** `DP-043`
**Connected Acceptance:** `AT-DP-043`

---

## Final verdict

```text
AUDIT_RESULT=FAIL

BLOCKERS=4
MAJORS=2
MINORS=0

DP-043=NOT_VERIFIED
AT-DP-043=FAIL
CLOSURE_ELIGIBLE=NO
```

Phase 10.43 is **not yet eligible for closure**.

V4 genuinely fixes the canonical pytest and Ruff result-parsing defects identified in V3. Those fixes were independently replayed in the auditor environment and passed.

The remaining failure is concentrated in the Project code-change boundary. V4 now has before/after snapshots and monotonic hint combiners, but the actual validation requirements are still resolved before the mutation using a top-level-file heuristic rather than the actual mutation ChangeSet. The real post-execution changed-file set is computed only after Phase 9 POST validation has already finished and is then discarded. Host change derivation also fails open on missing roots/snapshot exceptions, and the validation root itself is still sourced from caller-visible request metadata. Finally, Domain code implements a local impact classifier rather than consuming the canonical Phase 7 `ChangeImpactAnalyzer`.

The Project portion of `AT-DP-043` therefore remains connected to a favorable fixture, not to the general canonical host-change truth required by the approved spec and plan.

---

# 1. Independent artifact verification

## 1.1 Bundle SHA-256

Independent calculation:

```text
f30f6bc201374027b51c1f776784a02b19392bce81b819cc3875d296dd65ba9b
```

Matches the implementation handoff.

```text
BUNDLE_SHA256=PASS
```

## 1.2 Gzip and archive integrity

Independent checks:

```text
GZIP=PASS
ARCHIVE_ENTRIES=2075
UNSAFE_PATHS=0
```

The archive is a direct `git archive` tree without an enclosing prefix directory. This is valid for exact-HEAD auditing and contains no unsafe paths.

```text
ARCHIVE_INTEGRITY=PASS
ARCHIVE_PATH_SAFETY=PASS
```

## 1.3 Exact embedded Git HEAD

Independent:

```text
git get-tar-commit-id
→ a7042780daf345da99862b033088d036598add48
```

Therefore:

```text
EXACT_HEAD=PASS
```

## 1.4 Historical artifact preservation

Independent hashes:

```text
SPEC_SHA256=
cbdf93269ebd3f77c6f44c61afd5ca8a1da918418d41c303b78aa332dd84665b

PLAN_SHA256=
0875187896b9c1c2fc620780dc8cd9692984ed2e1124e0db510b2510b4874ec7

V1_AUDIT_SHA256=
57d0e97aedbf10357fdcde01477bb8ed37274a700be624f4379929743bf19a51

V2_AUDIT_SHA256=
ff3d8cec34b8cbe133bd54972af1028336dc82e82c48762248681f6b21369f2a

V3_AUDIT_SHA256=
9ca7a793d94fe3c9a7300dc696fe59ad3f274394e08bc3dc821ba907d38ab36e
```

These match the approved/historical identities.

```text
HISTORICAL_ARTIFACTS=PRESERVED
```

## 1.5 Independent compilation

The extracted V4 tree was independently compiled:

```text
python -m compileall -q cmm tests
COMPILEALL_AUDITOR=PASS
```

---

# 2. Independent test replay

The auditor environment can import the validation parser layer but lacks `libcst`, so the complete Domain suite cannot be replayed.

This limitation does not drive the FAIL verdict.

## 2.1 V4 parser regressions independently replayed

Command:

```text
PYTHONPATH=. pytest -q \
  tests/validation/test_ruff_parser.py \
  tests/validation/test_validation_executor.py \
  -k 'pytest_command or ruff'
```

Independent result:

```text
7 passed, 8 deselected
```

Additional command:

```text
PYTHONPATH=. pytest -q \
  tests/validation/test_pytest_parser.py \
  tests/validation/test_pytest_steps.py
```

Independent result:

```text
14 passed
```

Therefore:

```text
V4_PYTEST_PARSER_REPLAY=PASS
V4_RUFF_PARSER_REPLAY=PASS
```

## 2.2 Domain integration replay limitation

Attempting to collect the Project integration test in the auditor environment fails before test execution because:

```text
ModuleNotFoundError: No module named 'libcst'
```

That is an auditor-environment dependency limitation, not a repository test failure.

The Project blockers below are established directly from committed source ordering and contracts.

---

# 3. V3 → V4 remediation matrix

| V3 finding | V4 status | Independent assessment |
|---|---|---|
| BLOCKER-V3-01 — pytest/Ruff command-result path fail-open | **REMEDIATED** | Real parser wiring exists and targeted regressions independently pass |
| BLOCKER-V3-02 — Project impact/changed files not host-derived | **PARTIALLY REMEDIATED** | snapshots and combiners added, but actual POST requirements still use pre-mutation top-level heuristic; root remains caller-visible; derivation errors fail open |
| BLOCKER-V3-03 — Project AT proof incomplete | **PARTIALLY REMEDIATED** | affected-test status is now asserted, but fixture succeeds because `main.py` is top-level and preselected before mutation; actual changed-file truth is not feeding POST validation |
| MAJOR-V3-01 — docs overstate Project behavior | **PARTIALLY REMEDIATED** | docs reflect V4 intended design but still overstate actual host derivation and connected rollback proof |

---

# 4. Positive V4 findings

These V4 changes are valid and should be preserved.

## 4.1 Canonical pytest parser is now wired

`cmm/validation/command_parsers.py` now contains a production branch for:

```text
result_parser == "pytest"
```

and calls the existing:

```text
parse_pytest_result(...)
```

with the configured JUnit XML path.

This corrects the V3 orphan-parser defect.

## 4.2 Pytest non-zero outcomes no longer survive as PASSED

`parse_pytest_result()` now maps canonical pytest failure states, including:

```text
exit 1 → FAILED / blocking test failure
exit 2 → CANCELLED
exit 3 → ERROR
exit 4 → ERROR
exit 5 → FAILED when required
```

Missing/unusable reports no longer silently preserve generic `PASSED`.

Independent parser/executor tests pass.

```text
PYTEST_RESULT_PARSER_REAL_PATH=PASS
AFFECTED_TEST_EXIT_1=FAILED
```

## 4.3 Ruff list-form JSON is now interpreted

`parse_ruff_results()` accepts current Ruff list-form JSON diagnostics:

```json
[
  {
    "code": "F401",
    "message": "...",
    "filename": "...",
    "location": {"row": 1, "column": 8}
  }
]
```

and converts diagnostics to blocking findings.

It also fails closed when Ruff returns non-zero and no diagnostics can be extracted.

Independent V4 Ruff regression tests pass.

```text
RUFF_LIST_JSON_PARSER=PASS
LINT_DIAGNOSTICS=FAILED
```

## 4.4 Provider/empty-requirements/specialized-result V3 fixes remain present

Independent source review finds no regression in the previously accepted V3 improvements:

```text
PROVIDER_OMISSION=FAIL_CLOSED
EMPTY_RUNTIME_REQUIREMENTS=FAIL_CLOSED
SPECIALIZED_RESULT_GATE=UNCONDITIONAL
```

## 4.5 Pack/workflow/cross-domain direction remains preserved

No V4 change reintroduces a second validation pipeline or moves canonical validation ownership away from Phase 7.

## 4.6 No parallel named validation subsystem

Independent search finds no new:

```text
DomainValidationEngine
DomainValidationRuntime
DomainValidationStore
DomainValidationRepository
DomainValidationEventBus
DomainValidationHistory
DomainValidationCommitGate
DomainValidationPolicyRegistry
DomainValidationExecutor
ProjectValidationEngine
CrossDomainValidationEngine
```

```text
ANTI_FRAGMENTATION_NAMED_INFRA=PASS
```

## 4.7 Quality evidence is candid about historical Ruff debt

The implementation evidence reports full-tree debt rather than claiming a false full-tree PASS, and reports zero V4 delta errors on modified files.

That evidence pattern is acceptable given the repository's established changed-file lint/format convention.

---

# 5. BLOCKER-V4-01 — actual Project changed-file scope reaches validation too early and misses real small mutations

**Severity:** BLOCKER
**Scope:** Project `affected_tests`, host-derived changed files, real mutation acceptance
**DP impact:** a small Project mutation can bypass affected tests
**AT impact:** the V4 fixture proves a favorable root-file case, not the general invariant

## 5.1 Requirements are resolved before the mutation

In:

```text
cmm/domains/operation_execution.py
```

the orchestrator constructs `AgentOperationRequest` and resolves:

```text
validation_requirements =
    self._resolve_host_validation_requirements(definition, request)
```

before it captures the pre-execution snapshot and before:

```text
self._execution_adapter.execute(common_request)
```

The common adapter then executes:

```text
PRE validation
→ operation delegate
→ POST validation
```

using that already-materialized requirement/resource scope.

Therefore the POST validator set and its `resource_scope` are determined **before the mutation exists**.

## 5.2 The no-snapshot "host derivation" is not actual change detection

When `derive_host_project_change_impact()` is called without a before/after snapshot, its fallback is:

```python
for p in sorted(root.glob("*.py")):
    ...
    derived_files.add(str(rel))
```

This:

- scans only top-level `*.py`;
- does not compare before/after state;
- does not know which file the operation will mutate;
- is a file-presence heuristic, not mutation-derived changed-file truth.

The approved implementation plan explicitly says:

> Do not hard-code file-name heuristics in Domain code if Phase 7 already owns change impact.

V4 violates that instruction directly.

## 5.3 Actual post-execution changed files are computed too late and discarded

After the common adapter has already finished POST validation, the orchestrator finally captures an after snapshot and calls:

```text
derive_host_project_change_impact(
    before_snapshot=before_snapshot,
    after_snapshot=after_snapshot
)
```

This produces:

```text
derived_impact, _derived_files
```

but `_derived_files` has no production consumer.

Independent source search:

```text
_derived_files references = 1
```

the assignment itself.

The actual changed-file set is therefore not fed back into the Phase 9 POST validation request.

## 5.4 Concrete bypass class

A common Project layout is:

```text
project/
  src/
    pkg/
      module.py
  tests/
    test_module.py
```

For a small body-only mutation in:

```text
src/pkg/module.py
```

with no caller changed-file hint:

1. pre-resolution runs before mutation;
2. `root.glob("*.py")` does not include `src/pkg/module.py`;
3. `resource_scope` is empty or unrelated;
4. `affected_tests_step` receives no actual changed file;
5. selection can become not-applicable;
6. operation executes;
7. post validation uses the same precomputed empty/unrelated scope;
8. the after snapshot may correctly identify `src/pkg/module.py`;
9. `_derived_files` is discarded;
10. body-only impact remains `small`, so the escalation branch is not entered;
11. the mutation can be accepted without its affected test running.

This directly violates the approved requirement:

```text
failing affected test blocks acceptance
```

## 5.5 Why the current V4 test passes

The V4 Project fixture uses:

```text
affproj/main.py
```

at the project root.

`main.py` is included by the pre-execution:

```text
root.glob("*.py")
```

heuristic before the mutation happens.

Therefore the test comment:

```text
host derives main.py from the mutation
```

is not what the implementation actually proves.

It proves:

```text
top-level main.py existed before the mutation and was conservatively preselected
```

That distinction is closure-critical.

## Required remediation

Do not add another heuristic.

The actual before/after Phase 7 ChangeSet must feed the POST validation scope.

Possible implementation directions must be selected only after inspecting existing runtime seams, but the invariant is:

```text
actual mutation
→ canonical host ChangeSet
→ actual changed_files
→ POST Phase 9 ValidationRequirements/resource_scope
→ AgentValidationAdapter
→ affected_tests
```

PRE validation may use pre-execution policy requirements as appropriate.

POST mutation validation must use actual post-mutation host truth.

Add a connected regression with:

```text
src/pkg/module.py
```

or equivalent nested/src-layout source, no caller changed-file hint, formatter/lint/syntax/AST clean semantic regression, and prove:

```text
affected_tests == FAILED
operation not accepted
```

---

# 6. BLOCKER-V4-02 — Project host derivation still fails open and the validation root remains caller-controlled

**Severity:** BLOCKER
**Scope:** fail-closed host truth
**Security/authority impact:** caller or infrastructure error can weaken validation scope

## 6.1 Missing project root silently becomes small

`derive_host_project_change_impact()` does:

```text
if not project_root:
    return "small", files
```

and for a nonexistent root:

```text
return "small", files
```

A code-mutating Project operation therefore does not fail closed when no trustworthy validation root exists.

## 6.2 Derivation exceptions are swallowed

The canonical-change derivation block is wrapped in:

```python
except Exception:
    pass
```

and then returns:

```text
derived_impact="small"
derived_files=()
```

or a partial set.

That is the opposite of the Phase 10.43 invariant:

```text
mandatory validation missing/unavailable/unsuccessful → fail closed
```

A failure to determine validation scope/impact is itself validation infrastructure uncertainty and may not silently become `small`.

## 6.3 Pre-snapshot capture failures disable escalation

`DefaultDomainOperationOrchestrator.execute()` catches every exception while capturing the pre snapshot and sets:

```text
before_snapshot = None
```

The post-execution escalation block requires:

```text
before_snapshot is not None
```

Therefore snapshot failure disables the post-execution host impact check rather than blocking the mutation.

No V4 regression proves snapshot/impact-derivation failure is fail-closed.

## 6.4 `validation_project_root` is still sourced from request metadata

`_resolve_host_validation_root()` obtains:

```text
request.metadata["validation_project_root"]
```

`DomainOperationRequest.metadata` is part of the public request contract, is serialized by `to_dict()`, accepted by `from_dict()`, and `DefaultDomainAPI.execute_operation()` directly delegates the public request to the orchestrator.

The root is therefore not demonstrated to be host-authoritative merely because impact/changed files are subsequently combined monotonically.

A caller capable of controlling request metadata can:

```text
point validation_project_root at another clean tree
or omit it
```

while the injected `project.modify_code` implementation mutates a different target derived from its own inputs/runtime state.

That is a more powerful downgrade channel than `validation_impact="small"`.

## Required remediation

For `project.modify_code`:

- validation root must come from an existing trusted host/runtime Project execution context, transaction/checkpoint state, or other canonical owner;
- request metadata may not be authority for that root;
- absence/mismatch/unreadable root must fail closed;
- snapshot capture failure must fail closed;
- canonical impact/change-set derivation failure must fail closed;
- if a request retains a project-root field for transport, validate it against host-owned execution state rather than trusting it.

Add adversarial tests:

```text
caller supplies benign validation root while mutation targets real root
→ rejected / ignored in favor of host root

host root missing
→ fail closed

snapshot capture raises
→ fail closed

impact derivation raises
→ fail closed
```

---

# 7. BLOCKER-V4-03 — Domain code still implements a parallel impact classifier instead of consuming canonical Phase 7 change impact

**Severity:** BLOCKER
**Scope:** architecture, Phase 7 ownership, policy escalation
**Plan violation:** explicit

## 7.1 Approved plan requirement

The approved implementation plan states:

```text
Project Domain mandatory Phase 7 validation consumes:
- Phase 7 change impact
- tests
- static/security
- commit gate
```

and explicitly:

> Do not hard-code file-name heuristics in Domain code if Phase 7 already owns change impact.

## 7.2 V4 does not use `ChangeImpactAnalyzer`

The canonical Phase 7 owner exists:

```text
cmm.validation.impact.analyzer.ChangeImpactAnalyzer
```

Its `analyze()` result includes:

```text
change_type
affected_modules
affected_symbols
affected_tests
public_api_changed
confidence
requires_full_suite
uncertainty
findings
artifacts
```

Independent search finds:

```text
ChangeImpactAnalyzer references in V4 Project integration = 0
```

## 7.3 V4 locally classifies impact in Domain code

`derive_host_project_change_impact()` manually loops through changed Python files and decides:

```text
public_api_changed → public
signature/symbol/import change → structural
else → small
```

This is a Domain-owned impact classifier.

It uses low-level Phase 7 helpers, but it does not consume the authoritative Phase 7 `ChangeImpactResult`.

## 7.4 Canonical semantics are lost

The local classifier ignores Phase 7 signals such as:

```text
requires_full_suite
confidence
uncertainty
affected dependents
affected tests
low-confidence escalation
python_change_without_diff escalation
```

The canonical `ChangeImpactAnalyzer` can require a full suite based on uncertainty/low confidence even when a local syntactic classification would otherwise look small.

V4 can therefore under-escalate relative to Phase 7.

This violates the architecture statement:

```text
Phase 7 = canonical validation owner
```

and the spec:

```text
Project Domain code changes reuse Phase 7 change-impact capabilities
```

## Required remediation

Delete the Domain-owned impact classification logic.

Use the canonical Phase 7:

```text
ChangeSetBuilder
→ ChangeImpactAnalyzer
→ ChangeImpactResult
```

or an existing public adapter over exactly those components.

Map canonical `ChangeImpactResult` to Project policy selection minimally and deterministically.

Do not recreate:

```text
public/structural/small
```

by inspecting `PythonModuleDiff` directly in Domain code.

If canonical analysis is uncertain or requests a full suite, Domain must preserve/escalate that requirement, never collapse it to `small`.

---

# 8. BLOCKER-V4-04 — AT-DP-043 still does not prove the general Project invariant

**Severity:** BLOCKER
**Scope:** acceptance
**Closure impact:** `AT-DP-043=FAIL`

V4's parser acceptance and provider/specialized-result scenarios are materially improved and should be preserved.

The Project part is still incomplete.

## 8.1 Changed-file proof is fixture-specific

`test_project_affected_test_failure_via_real_path` uses:

```text
affproj/main.py
```

and omits only `validation_changed_files`.

It still explicitly supplies:

```text
metadata["validation_project_root"] = <temp project>
```

and, because `main.py` is top-level, the implementation preselects it before mutation using `root.glob("*.py")`.

The test therefore does not prove actual changed-file derivation from the mutation.

## 8.2 No nested/src-layout acceptance

There is no connected AT case where:

```text
src/pkg/module.py
```

is mutated with no changed-file hint and is discovered from the real before/after change set before POST affected-test validation.

That is the exact path required to close BLOCKER-V4-01.

## 8.3 No derivation-failure acceptance

AT does not prove fail-closed behavior for:

```text
missing host project root
snapshot capture failure
change-impact analysis failure
caller root mismatch
```

## 8.4 Rollback evidence uses test spies

The shared Project helper constructs local:

```text
TransactionManagerSpy
RollbackSpy
```

and `RollbackSpy.rollback()` only increments a counter and returns `True`.

It does not restore the mutated filesystem.

The structural/public escalation AT asserts:

```text
DomainOperationStatus.ROLLED_BACK
```

but does not assert the code tree was actually restored through the canonical:

```text
CheckpointRestorationRollbackExecutor
```

or an official in-memory equivalent.

The approved acceptance requires a real/in-memory-official Project code-change path, not status-only rollback simulation.

Because the V4 escalation guard occurs **after mutation**, real rollback behavior is materially relevant to fail-closed semantics.

## Required AT remediation

Preserve all valid V4 scenarios and add:

```text
A. nested/src-layout small semantic regression
   caller changed-files omitted
   trusted host root supplied by canonical owner
   actual before/after ChangeSet identifies source file
   formatter/lint/syntax/AST pass
   affected_tests fails
   operation rejected

B. host-root mismatch attempt
   caller points at benign tree
   canonical root wins / request rejected

C. derivation failure
   canonical snapshot/impact failure
   operation fails closed

D. canonical impact ownership
   real ChangeImpactAnalyzer result drives escalation

E. post-validation rollback
   use canonical CheckpointRestorationRollbackExecutor or official in-memory implementation
   prove mutated file content is actually restored
```

Only after these are connected can the independent auditor verify:

```text
AT-DP-043=PASS
```

---

# 9. MAJOR-V4-01 — documentation and V4 evidence overstate Project host derivation

**Severity:** MAJOR

The reference documentation currently says:

```text
ProjectDomainChangePolicy selected by host-owned impact
resource_scope carrying host-derived changed files
canonical change scope and impact derived directly from host project directory
caller hints cannot hide host-changed files
```

and describes the AT as:

```text
host change derivation without caller hints
impact escalation via real runtime operations
fail closed with rollback
```

Those claims exceed the implementation because:

- actual POST changed files are not fed into POST validation;
- pre-resolution uses top-level-file presence, not mutation-derived scope;
- `validation_project_root` is still request metadata;
- derivation errors silently fall back;
- impact is classified in Domain code rather than by `ChangeImpactAnalyzer`;
- rollback AT uses a spy that does not restore state.

The V4 evidence also says Ruff empty-diagnostic fallback uses:

```text
RUFF_EXECUTION_FAILED
```

while committed lint code emits:

```text
RUFF_LINT_FAILED
```

The status semantics are safe, but the evidence is not byte-accurate.

## Required remediation

After the code/AT fixes:

- document the true canonical Phase 7 impact owner;
- document the trusted Project root owner;
- document that actual post-mutation changed files feed POST validation;
- document fail-closed behavior for derivation uncertainty;
- only claim rollback after canonical restoration is proven;
- correct the Ruff fallback finding-code name.

Keep phase status:

```text
IMPLEMENTED_PENDING_INDEPENDENT_AUDIT
```

until independent PASS.

---

# 10. MAJOR-V4-02 — remediation execution violated the permanent no-`git reset` rule

**Severity:** MAJOR
**Scope:** auditable workflow/process integrity

The provided V4 implementation transcript contains:

```text
rm -f .git/index && git reset
```

and later direct index reconstruction operations.

The project permanent rules explicitly prohibit:

```text
git reset
```

without explicit user authorization.

No such authorization was provided for this remediation.

The transcript also contains:

```text
git checkout 772031c cmm/agent_runtime/operation_execution_adapter.py
```

which materially rewrites a working-tree path during remediation and should be treated with the same caution even though the permanent rule names `reset` explicitly.

The final exact-HEAD bundle is independently valid, and the quarantine stash is reported preserved, so this process violation does **not** invalidate the archive bytes.

It does invalidate the claim that the V4 remediation followed the required auditable workflow without prohibited Git operations.

## Required process remediation

The historical action cannot be undone.

Before the next audit:

1. record the process deviation transparently in V5 remediation evidence;
2. run read-only repository integrity checks from the known audit history;
3. verify:
   - expected branch;
   - V3 audit-report commit is ancestor of V5;
   - all V4/V5 intended commits are present;
   - no historical audit artifacts changed;
   - quarantine stash identity/message is preserved;
   - worktree is clean;
   - no unexpected staged state;
4. do not use `reset`, `clean`, `stash`, `worktree`, or destructive checkout/restore during V5;
5. include:
   ```text
   V4_PROCESS_DEVIATION_GIT_RESET=DISCLOSED
   FINAL_REPOSITORY_INTEGRITY=VERIFIED
   ```
   in implementation evidence.

A later independent audit may consider the process incident remediated once the final state is proven and the deviation is no longer hidden.

---

# 11. Quality gate assessment

## 11.1 Implementation-machine evidence

V4 reports:

```text
PHASE10_43_FOCUSED_TESTS=285 PASS
VALIDATION_SUITE=531 PASS
AGENT_RUNTIME_SUITE=3434 PASS
DOMAIN_SUITE=9657 PASS
GLOBAL_SUITE=15260 PASS
```

The exact bundle includes this evidence.

## 11.2 Independently replayed

```text
COMPILEALL_AUDITOR=PASS

V4 parser/executor targeted:
7 passed, 8 deselected

pytest parser/steps:
14 passed
```

## 11.3 Not independently replayed

The full Domain/global suites cannot be replayed in the auditor container because `libcst` is unavailable.

This is not a basis for FAIL.

## 11.4 Ruff

The implementation reports:

```text
modified V4 Python files: Ruff check PASS
modified V4 Python files: Ruff format --check PASS

full tree:
841 historical/current Ruff findings
318 format-debt files
```

No claim of full-tree PASS is made.

This aspect is acceptable and is not a V4 blocker.

---

# 12. Architecture assessment

## Preserved ownership

Still valid:

```text
Phase 7 owns canonical ValidationPipeline
Phase 9 owns AgentValidationAdapter bridge
Phase 7 owns CommitGate
Domain packs do not own validation truth
workflow/cross-domain validation remains composed through existing bridges
```

## Remaining ownership violation

Not valid:

```text
Domain layer owns its own impact classification logic
```

That is exactly the kind of specialized parallel decision logic Phase 10.43 was meant to avoid.

---

# 13. Security / fail-closed assessment

## PASS

```text
provider omission → fail closed
empty mandatory requirements → fail closed
unknown/unmapped required validator → fail closed
pytest non-zero outcomes → canonical non-PASS
Ruff non-zero/list diagnostics → canonical non-PASS
specialized result structural gate → provider-independent
```

## FAIL

```text
missing validation project root → small fallback
nonexistent validation project root → small fallback
change derivation exception → small fallback
pre-snapshot capture exception → post-escalation skipped
caller-visible metadata selects validation root
actual small nested changed files do not feed POST affected-test validation
```

Therefore the Project change boundary is not yet globally fail-closed.

---

# 14. DP-043 assessment

V4 has resolved a substantial portion of the design:

```text
pack lifecycle = canonical
operation mandatory validation = fail-closed when provider missing
Phase 9 empty-requirement bypass = closed
pytest/Ruff result truth = corrected
workflow/cross-domain bridges = connected
specialized-result acceptance = connected
```

But `DP-043` specifically requires Project Domain code changes to use canonical Phase 7 validation and not bypass mandatory validation.

The remaining Project implementation can still miss affected tests for normal nested/src-layout small mutations and can degrade to `small` when host change derivation fails.

It also reimplements impact classification outside the canonical Phase 7 owner.

Therefore:

```text
DP-043=NOT_VERIFIED
```

---

# 15. AT-DP-043 assessment

The V4 AT is materially stronger than V3.

However its Project proof remains fixture-specific and does not exercise the general canonical host-change path required by the spec.

It also uses a rollback spy for the post-mutation escalation path.

Therefore:

```text
AT-DP-043=FAIL
```

---

# 16. Required targeted V4 → V5 remediation

This must remain narrow.

Do not reopen:

```text
pack lifecycle
provider fail-closed
empty requirements
pytest parser
Ruff parser
workflow bridge
cross-domain bridge
specialized-result gate
unknown Project policy-step fail-closed
```

unless a regression proves the V5 Project fix breaks them.

## Block A — use canonical Phase 7 change-impact owner

Remove Domain-owned impact classification.

Use:

```text
ChangeSetBuilder
→ ChangeImpactAnalyzer
→ ChangeImpactResult
```

through an existing/public Phase 7 seam.

Preserve:

```text
confidence
uncertainty
requires_full_suite
affected_tests
public_api_changed
change_type
```

Fail closed if canonical impact cannot be produced for a code mutation.

## Block B — make POST validation use the actual mutation ChangeSet

Rework the existing execution seam minimally so:

```text
before host snapshot
→ operation executes
→ after host snapshot
→ canonical ChangeSet
→ canonical ChangeImpactResult
→ actual changed_files
→ POST validation requirements/resource_scope
→ AgentValidationAdapter
→ result acceptance
```

Do not reuse the pre-mutation top-level `*.py` scan as actual changed-file truth.

Do not create a second execution runtime.

## Block C — trusted project root

Resolve Project root from canonical host/runtime/transaction state.

Do not trust free-form/public request metadata as the authority.

Missing/mismatched/unreadable root fails closed.

If a transport hint remains, validate it against host truth.

## Block D — fail-closed derivation errors

Add RED tests and fix:

```text
snapshot capture exception
ChangeSetBuilder exception
ChangeImpactAnalyzer exception
invalid/nonexistent host root
```

All must prevent mutation acceptance.

## Block E — rebuild only Project AT

Add:

```text
nested src/pkg/module.py small regression
no changed-file hint
actual affected test FAILED in canonical result
canonical host root, not metadata authority
structural/public impact from ChangeImpactAnalyzer
real restoration through canonical rollback implementation
```

Preserve all already-valid AT scenarios.

## Block F — docs/process evidence

Correct Project docs.

Disclose V4 prohibited `git reset` incident and prove final repository integrity read-only.

Do not use prohibited Git operations in V5.

---

# 17. Required V5 evidence

Implementation may report only implementation facts:

```text
PHASE10_43_REMEDIATION_V4_TO_V5=COMPLETE_PENDING_INDEPENDENT_REAUDIT

V4_AUDITED_HEAD=a7042780daf345da99862b033088d036598add48
V4_AUDIT_REPORT_COMMIT=<commit after this audit is recorded>
V5_REMEDIATED_HEAD=<exact HEAD>

V3_BLOCKER_01_PARSER_FIX=PRESERVED

PROJECT_IMPACT_OWNER=PHASE7_CHANGE_IMPACT_ANALYZER
DOMAIN_LOCAL_IMPACT_CLASSIFIER=REMOVED

PROJECT_HOST_ROOT=CANONICAL
CALLER_ROOT_DOWNGRADE=BLOCKED

PROJECT_POST_CHANGESET=CANONICAL
PROJECT_POST_CHANGED_FILES=ACTUAL_MUTATION
PROJECT_NESTED_CHANGED_FILE_SELECTION=PASS
PROJECT_AFFECTED_TEST_RUNTIME_GATE=PASS

PROJECT_SNAPSHOT_FAILURE=FAIL_CLOSED
PROJECT_IMPACT_ANALYSIS_FAILURE=FAIL_CLOSED
PROJECT_MISSING_ROOT=FAIL_CLOSED

PROJECT_ESCALATION_ROLLBACK=CANONICAL_RESTORATION_VERIFIED

AT_DP_043=PASS_CONNECTED
DP_043=IMPLEMENTED_PENDING_REAUDIT

V4_PROCESS_DEVIATION_GIT_RESET=DISCLOSED
FINAL_REPOSITORY_INTEGRITY=VERIFIED

FOCUSED_TESTS=<exact count> PASS
VALIDATION_SUITE=<exact count> PASS
AGENT_RUNTIME_SUITE=<exact count> PASS
DOMAIN_SUITE=<exact count> PASS
GLOBAL_SUITE=<exact count> PASS

RUFF_V5_DELTA_GATE=PASS
FORMAT_V5_DELTA_GATE=PASS
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS

WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED
PUSH=NO
MERGE=NO
```

Then generate a NEW:

```text
phase-10.43-audit-v5-<V5_REMEDIATED_HEAD>.tar.gz
```

from the exact committed HEAD.

---

# 18. Final V4 audit status

```text
PHASE=10.43
AUDIT_VERSION=V4

AUDITED_HEAD=a7042780daf345da99862b033088d036598add48
AUDIT_BUNDLE_SHA256=f30f6bc201374027b51c1f776784a02b19392bce81b819cc3875d296dd65ba9b

BUNDLE_SHA256=PASS
GZIP=PASS
EXACT_HEAD=PASS
ARCHIVE_PATH_SAFETY=PASS
COMPILEALL_AUDITOR=PASS

V4_PYTEST_PARSER_REPLAY=PASS
V4_RUFF_PARSER_REPLAY=PASS

V3_BLOCKER_01=REMEDIATED
V3_BLOCKER_02=PARTIALLY_REMEDIATED
V3_BLOCKER_03=PARTIALLY_REMEDIATED
V3_MAJOR_01=PARTIALLY_REMEDIATED

BLOCKER_V4_01=POST_VALIDATION_DOES_NOT_USE_ACTUAL_MUTATION_CHANGED_FILES
BLOCKER_V4_02=PROJECT_HOST_DERIVATION_AND_ROOT_FAIL_OPEN
BLOCKER_V4_03=DOMAIN_REIMPLEMENTS_PHASE7_CHANGE_IMPACT
BLOCKER_V4_04=AT_DP_043_PROJECT_PROOF_STILL_INCOMPLETE

MAJOR_V4_01=PROJECT_DOCS_AND_EVIDENCE_OVERSTATE_HOST_DERIVATION
MAJOR_V4_02=PROHIBITED_GIT_RESET_USED_DURING_V4_REMEDIATION

BLOCKERS=4
MAJORS=2
MINORS=0

DP-043=NOT_VERIFIED
AT-DP-043=FAIL
CLOSURE_ELIGIBLE=NO

NEXT=TARGETED_V4_TO_V5_REMEDIATION
```
