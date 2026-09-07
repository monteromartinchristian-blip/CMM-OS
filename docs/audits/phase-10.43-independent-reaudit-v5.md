# CMM OS — Phase 10.43 Independent Re-Audit V5

**Phase:** 10.43 — Integration with Validation System
**Audit:** Independent ChatGPT Re-Audit V5
**Date:** 2026-09-07
**Bundle:** `phase-10.43-audit-v5-1d4cb19855aaedae5eccbde3e97d700bf7a363ce.tar.gz`
**Audited implementation HEAD:** `1d4cb19855aaedae5eccbde3e97d700bf7a363ce`
**Bundle SHA-256:** `bb035756dd51403518304f3d7d16c8b92331ecca36c62fa557fb492fc4d29f81`
**Historical V4 implementation HEAD:** `a7042780daf345da99862b033088d036598add48`
**V4 audit-report commit baseline:** `26796777eb60d0ea332aae2d0a058f113881d458`
**Design Point:** `DP-043`
**Connected Acceptance:** `AT-DP-043`

---

## Final verdict

```text
AUDIT_RESULT=FAIL

BLOCKERS=0
MAJORS=1
MINORS=0

DP-043=VERIFIED_EXISTING
AT-DP-043=PASS
CLOSURE_ELIGIBLE=NO
```

V5 successfully remediates all four functional/architectural blockers from V4 and the V4 documentation/process findings.

The Phase 10.43 validation design itself is now verified: Project mutation validation uses canonical Phase 7 change-impact analysis, authoritative post-mutation changed files, a host-authoritative project root, canonical Phase 9 validation execution, and real checkpoint restoration in connected acceptance.

One non-bypass runtime-state defect remains before closure: the Domain operation orchestrator starts a real transaction/checkpoint **before** several newly fail-closed pre-mutation validation/root/snapshot operations. If any of those preflight operations raises, the exception propagates without closing, failing, or rolling back the already-created transaction. This can leave an ACTIVE transaction and checkpoint behind even though the Project mutation never executed.

That defect is a MAJOR runtime lifecycle issue, but it does not invalidate `DP-043` or the connected `AT-DP-043` validation behavior itself.

A narrow V5→V6 remediation is required before Phase 10.43 closure.

---

# 1. Independent bundle verification

## 1.1 SHA-256

Independent calculation:

```text
bb035756dd51403518304f3d7d16c8b92331ecca36c62fa557fb492fc4d29f81
```

Matches the handoff.

```text
BUNDLE_SHA256=PASS
```

## 1.2 Gzip integrity

Independent:

```text
gzip -t
→ PASS
```

```text
GZIP=PASS
```

## 1.3 Exact embedded Git HEAD

Independent:

```text
git get-tar-commit-id
→ 1d4cb19855aaedae5eccbde3e97d700bf7a363ce
```

```text
EXACT_HEAD=PASS
```

## 1.4 Archive shape and path safety

Independent:

```text
ARCHIVE_ENTRIES=2079
UNSAFE_PATHS=0
ROOT=CMM-OS-phase-10.43-1d4cb19855aaedae5eccbde3e97d700bf7a363ce
```

```text
ARCHIVE_INTEGRITY=PASS
ARCHIVE_PATH_SAFETY=PASS
```

## 1.5 No bytecode pollution

A temporary audit extraction initially contained `__pycache__` files after the auditor ran `compileall`.

The TAR.GZ itself was checked directly and contains no tracked `*.pyc` entries.

```text
ARCHIVE_PYC_POLLUTION=NO
```

---

# 2. Historical artifact preservation

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

V4_AUDIT_SHA256=
f41b06b3115fe328ecbe171246bb641cf0c00a457915817c2c58476fb2a8acbd
```

These match the approved/historical identities.

```text
SPEC=PRESERVED
PLAN=PRESERVED
V1_HISTORY=PRESERVED
V2_HISTORY=PRESERVED
V3_HISTORY=PRESERVED
V4_HISTORY=PRESERVED
```

---

# 3. Independent compilation and test replay

## 3.1 Compileall

Independent audit execution:

```text
python -m compileall -q cmm tests
```

Result:

```text
COMPILEALL_AUDITOR=PASS
```

## 3.2 V4 parser regression replay

Independent:

```text
PYTHONPATH=. pytest -q \
  tests/validation/test_ruff_parser.py \
  tests/validation/test_validation_executor.py \
  -k 'pytest_command or ruff'
```

Result:

```text
7 passed, 8 deselected
```

Independent:

```text
PYTHONPATH=. pytest -q \
  tests/validation/test_pytest_parser.py \
  tests/validation/test_pytest_steps.py
```

Result:

```text
14 passed
```

Therefore the V4 parser fixes remain intact:

```text
PYTEST_PARSER_FIX=PRESERVED
RUFF_PARSER_FIX=PRESERVED
```

## 3.3 Phase 7 ChangeSet public-seam tests

Independent:

```text
PYTHONPATH=. pytest -q tests/validation/impact/test_change_set_builder.py
```

Result:

```text
4 passed
```

## 3.4 Independent canonical nested-change probe

The auditor independently constructed:

```text
src/pkg/module.py
tests/test_module.py
```

captured canonical before/after snapshots, changed only the function body, and executed:

```text
ChangeSetBuilder.build_from_snapshots
→ ChangeImpactAnalyzer.analyze
```

Observed:

```text
CHANGESET_CHANGED_FILES=('src/pkg/module.py',)
IMPACT_AFFECTED_TESTS=('tests/test_module.py',)
IMPACT_PUBLIC_API=False
IMPACT_FULL_SUITE=False
IMPACT_UNCERTAINTY=()
```

This independently confirms that the canonical Phase 7 change path discovers the nested file and its affected test.

## 3.5 Domain-suite replay limitation

The auditor environment does not contain the repository dependency `libcst`.

Collecting the full Domain integration suite therefore fails at environment import time:

```text
ModuleNotFoundError: No module named 'libcst'
```

This is an auditor-environment limitation and is **not** a V5 repository failure.

The implementation-machine evidence records:

```text
FOCUSED_TESTS=138 PASS
VALIDATION_SUITE=533 PASS
AGENT_RUNTIME_SUITE=3434 PASS
DOMAIN_SUITE=9676 PASS
GLOBAL_SUITE=15281 PASS
```

No contrary test evidence was found in the bundle.

---

# 4. V4 → V5 remediation matrix

| V4 finding | V5 status | Independent assessment |
|---|---|---|
| BLOCKER-V4-01 — POST validation does not use actual mutation changed files | **REMEDIATED** | Project POST requirements are recomputed after mutation from canonical before/after ChangeSet; actual nested file scope reaches AgentValidationAdapter |
| BLOCKER-V4-02 — host derivation/root fail open | **REMEDIATED** | Project root comes from host-registered implementation; caller root is match-only; missing/invalid root and snapshot/change analysis failures fail closed |
| BLOCKER-V4-03 — Domain reimplements Phase 7 impact | **REMEDIATED** | Domain source-diff classifier removed; canonical `ChangeImpactAnalyzer` is the impact owner |
| BLOCKER-V4-04 — Project AT incomplete | **REMEDIATED** | AT now proves nested affected-test failure, decoy-root rejection, canonical impact escalation, derivation failure, and real checkpoint restoration |
| MAJOR-V4-01 — docs/evidence overstate runtime | **REMEDIATED** | reference/matrix/roadmap describe V5 host-root, ChangeImpactAnalyzer, authoritative POST, fail-closed behavior and restoration truthfully |
| MAJOR-V4-02 — prohibited Git reset used in V4 | **REMEDIATED** | deviation is explicitly disclosed; V4 audit history is preserved; final V5 exact-HEAD bundle is independently valid; no contrary evidence to V5 no-prohibited-ops statement |

---

# 5. BLOCKER-V4-03 remediation — canonical Phase 7 impact ownership

## 5.1 Domain local diff classifier is removed

Independent source scan:

```text
diff_python_sources refs in cmm/domains/validation_integration.py = 0
signature_changed local classification refs = 0
import_changes local classification refs = 0
symbol_changes local classification refs = 0
```

V4's Domain-owned source classifier is gone.

## 5.2 Canonical owner

V5 production imports and executes:

```text
ChangeSetBuilder
ChangeImpactAnalyzer
ChangeImpactResult
```

The authoritative post-mutation path is:

```text
scan_project_snapshot(before)
mutation
scan_project_snapshot(after)
ChangeSetBuilder.build_from_snapshots(...)
ChangeImpactAnalyzer().analyze(...)
project_policy_impact_from_canonical_result(...)
```

The Domain function:

```text
project_policy_impact_from_canonical_result(...)
```

is a thin adapter over canonical result fields.

It does not inspect source text or invoke a parallel source-diff classifier.

## 5.3 Canonical escalation signals preserved

The adapter escalates when Phase 7 reports:

```text
requires_full_suite
uncertainty
public_api_changed
affected_symbols
canonical structural/import/new/delete/rename change types
```

Only a clean local/body-only mutation maps to `small`.

Phase 7 itself converts low confidence into:

```text
requires_full_suite=True
uncertainty += low_confidence
```

so low-confidence canonical results cannot silently collapse to `small`.

## Assessment

```text
PROJECT_IMPACT_OWNER=PHASE7_CHANGE_IMPACT_ANALYZER
DOMAIN_LOCAL_IMPACT_CLASSIFIER=REMOVED
BLOCKER_V4_03=REMEDIATED
```

---

# 6. BLOCKER-V4-02 remediation — trusted host root and fail-closed derivation

## 6.1 Trusted root

For `project.modify_code`, V5 resolves the validation root from:

```text
InMemoryDomainOperationRegistry.get_implementation(...)
→ implementation.host_project_root
```

The operation implementation is the host-registered executable object that performs the mutation.

The request metadata field:

```text
validation_project_root
```

is no longer authority.

When supplied, it is only a consistency hint and must resolve to the same path as the host root.

## 6.2 Decoy root

Production behavior:

```text
caller hint != host_project_root
→ DomainValidationIntegrationError
→ mutation not executed
```

The connected V5 AT includes a decoy-root rejection scenario.

## 6.3 Missing/invalid host root

Production:

```text
missing implementation
→ fail closed

implementation without host_project_root
→ fail closed

host_project_root missing/non-directory
→ fail closed
```

## 6.4 Before snapshot

Before a Project code mutation executes, V5 requires a canonical before snapshot.

Failure raises:

```text
DomainValidationIntegrationError
reason=before_snapshot_failed
```

and the mutation does not execute.

## 6.5 After snapshot / ChangeSet / analyzer

After mutation:

```text
after snapshot failure
→ fail closed + rollback

ChangeSetBuilder failure
→ fail closed + rollback

ChangeImpactAnalyzer failure
→ fail closed + rollback

missing post requirements
→ fail closed + rollback

post validation infrastructure failure
→ fail closed + rollback
```

No V4-style:

```text
except Exception: pass
→ small
```

authoritative fallback remains.

## Assessment

```text
PROJECT_HOST_ROOT=CANONICAL
CALLER_ROOT_DOWNGRADE=BLOCKED
PROJECT_MISSING_ROOT=FAIL_CLOSED
PROJECT_SNAPSHOT_FAILURE=FAIL_CLOSED
PROJECT_IMPACT_ANALYSIS_FAILURE=FAIL_CLOSED
BLOCKER_V4_02=REMEDIATED
```

---

# 7. BLOCKER-V4-01 remediation — authoritative POST from actual ChangeSet

## 7.1 PRE-only pre-mutation requirements

For `project.modify_code`, `_resolve_host_validation_requirements()` now filters the pre-mutation materialized obligations to:

```text
AgentValidationStage.PRE_EXECUTION
```

The old precomputed POST scope is not accepted as authoritative Project post-change truth.

## 7.2 Mutation

The operation then executes through the existing:

```text
DomainOperationExecutionDelegate
→ AgentExecutionAdapter
```

No second operation runtime is introduced.

## 7.3 Actual POST truth

After successful mutation:

```text
_run_post_mutation_project_validation(...)
```

captures the actual after snapshot and calls:

```text
derive_host_project_change_impact(
    before_snapshot=before_snapshot,
    after_snapshot=after_snapshot
)
```

The resulting canonical ChangeSet provides:

```text
actual_impact
actual_files
```

## 7.4 Actual changed files reach Phase 9

V5 materializes new POST requirements with:

```text
impact=actual_impact
changed_files=actual_files
project_root=host_root
```

and executes them through the same canonical:

```text
AgentValidationAdapter
```

via a real:

```text
AgentValidationRequest(stage=POST_EXECUTION)
```

## 7.5 Acceptance gate

Only:

```text
AgentValidationDecision.CONTINUE
```

permits operation acceptance.

Any other decision raises fail closed and enters the existing Domain rollback path.

## 7.6 Nested/src-layout proof

The connected V5 fixture uses:

```text
src/pkg/module.py
tests/test_module.py
```

with no top-level `*.py` source shortcut.

It omits caller changed-file hints.

The AT asserts the authoritative POST request contains:

```text
src/pkg/module.py
```

and its canonical report contains:

```text
affected_tests.status == failed
```

The operation is not accepted.

The repaired mutation completes only after current validation passes.

Independent Phase 7 probing also confirms canonical ChangeSet/test selection for the same nested shape.

## Assessment

```text
PROJECT_POST_CHANGESET=CANONICAL
PROJECT_POST_CHANGED_FILES=ACTUAL_MUTATION
PROJECT_NESTED_CHANGED_FILE_SELECTION=PASS
PROJECT_AFFECTED_TEST_RUNTIME_GATE=PASS
BLOCKER_V4_01=REMEDIATED
```

---

# 8. BLOCKER-V4-04 remediation — connected Project AT

## 8.1 Nested semantic failure

AT proves:

```text
formatter/lint/syntax/AST-clean body mutation
→ actual nested changed file
→ affected_tests selected
→ affected_tests FAILED
→ operation rolled back
```

## 8.2 File restoration

The canonical V5 acceptance stack uses:

```text
CheckpointManager
TransactionManager
CheckpointRestorationManager
CheckpointRestorationRollbackExecutor
```

with a whole-tree resource-version provider.

The test records original file bytes, executes a failing mutation, and asserts:

```text
file after rollback == original content
```

This is no longer a status-only `RollbackSpy` proof.

## 8.3 Structural/public escalation

AT executes real runtime mutations with caller hint:

```text
small
```

while the actual Phase 7 change analysis detects structural/public impact.

The stronger host result wins and the operation fails closed where stronger mandatory validators are currently unmappable.

The mutated file is restored.

## 8.4 Decoy-root attack

AT supplies a clean alternate root in caller metadata.

Production rejects the mismatch against host-owned execution root.

## 8.5 Derivation failure

AT monkeypatches canonical ChangeSet construction to fail and proves the operation is not accepted.

## Assessment

```text
PROJECT_ESCALATION_ROLLBACK=CANONICAL_RESTORATION_VERIFIED
AT-DP-043=PASS
BLOCKER_V4_04=REMEDIATED
```

---

# 9. Previously remediated Phase 10.43 invariants remain preserved

Independent source review finds no regression in:

```text
PROVIDER_OMISSION=FAIL_CLOSED
EMPTY_RUNTIME_REQUIREMENTS=FAIL_CLOSED
SPECIALIZED_RESULT_GATE=UNCONDITIONAL

PACK_INSTALL_VALIDATION=CANONICAL
PACK_UPDATE_VALIDATION=CANONICAL
WORKFLOW_VALIDATION_BRIDGE=PRESERVED
CROSS_DOMAIN_VALIDATION_BRIDGE=PRESERVED

PYTEST_RESULT_PARSER_REAL_PATH=PASS
RUFF_LIST_JSON_PARSER=PASS

PHASE7_COMMIT_GATE_OWNERSHIP=PRESERVED
```

No new named parallel validation infrastructure was introduced.

Independent scan finds no production class named:

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
ANTI_FRAGMENTATION=PASS
```

---

# 10. Documentation assessment

V5 reference documentation and requirements matrix now accurately describe:

```text
Phase 7 ChangeImpactAnalyzer as Project impact owner
trusted host implementation root
caller root as match-only hint
PRE-only provisional obligations
authoritative POST from actual mutation ChangeSet
nested/src-layout behavior
fail-closed derivation
canonical checkpoint restoration
```

Status remains correctly:

```text
IMPLEMENTED_PENDING_INDEPENDENT_AUDIT
```

No premature closure/audit PASS claim exists in the implementation documentation.

```text
MAJOR_V4_01=REMEDIATED
```

---

# 11. V4 process deviation assessment

The immutable V4 audit recorded unauthorized use of:

```text
git reset
```

during V4 remediation.

V5 evidence explicitly discloses the incident rather than hiding it.

Independent V5 checks establish:

```text
V4 audit report bytes preserved
V3/V2/V1 reports preserved
spec preserved
plan preserved
V5 exact HEAD valid
V5 bundle SHA valid
```

The implementation-machine handoff further reports:

```text
V4 audit-report commit is ancestor of V5 HEAD
worktree clean
quarantine stash preserved
V5 prohibited Git operations used = NO
push = NO
merge = NO
```

No contrary evidence is present.

The historical V4 process incident is therefore considered remediated for auditability.

```text
MAJOR_V4_02=REMEDIATED
```

---

# 12. Remaining MAJOR-V5-01 — pre-mutation fail-closed exceptions leak an active transaction/checkpoint

**Severity:** MAJOR
**Type:** runtime lifecycle / transaction hygiene
**Validation bypass:** NO
**DP-043 impact:** does not invalidate canonical validation behavior
**Closure impact:** prevents closure until cleaned up

## 12.1 Exact ordering

`DefaultDomainOperationOrchestrator.execute()` performs:

```text
availability / permission gate
→ start_transaction(...)
→ create checkpoint
→ construct AgentOperationRequest
```

During `AgentOperationRequest` construction it invokes:

```text
_resolve_host_validation_requirements(...)
_resolve_host_validation_root(...)
```

Only after those operations does V5 capture the required Project before snapshot.

## 12.2 Newly fail-closed operations can raise after transaction creation

After `start_transaction()` has stored an ACTIVE transaction and checkpoint, the following pre-mutation paths can raise:

```text
missing operation_validation_provider
missing host implementation
missing host_project_root
invalid host_project_root
caller decoy-root mismatch
unmappable mandatory pre-validation policy step
before snapshot capture failure
```

These are correct reasons to reject the operation.

The defect is that the exception occurs after transaction creation.

## 12.3 No cleanup wrapper exists

The common-request construction and before-snapshot block are not wrapped in a preflight transaction-abort path.

On these exceptions, the orchestrator does not call:

```text
mark_failed(...)
mark_rollback_started(...)
rollback(...)
mark_rolled_back(...)
commit(...)
```

and does not otherwise remove/close the created transaction.

The exception simply propagates.

## 12.4 Canonical TransactionManager retains ACTIVE state

`TransactionManager.start_transaction()` stores:

```text
self._boundaries[boundary.id] = active_boundary
self._states[boundary.id] = ACTIVE state
```

and creates the checkpoint before returning.

Therefore a rejected pre-mutation request can leave:

```text
TransactionStatus.ACTIVE
+
checkpoint retained
```

despite no operation execution.

## 12.5 Adversarial trigger

The V5 decoy-root test proves caller metadata mismatch is rejected.

Because root validation currently occurs after transaction creation, an approved caller can repeatedly submit a mismatching root and force creation of rejected-but-still-active transaction/checkpoint state.

This does **not** bypass validation or mutate Project state, but it is a real runtime-state leak and potential resource-exhaustion vector.

## 12.6 Test gap

Current V5 root/snapshot tests correctly assert:

```text
implementation execute was not called
```

but do not assert:

```text
no active transaction remains
no orphan checkpoint remains
```

The canonical AT similarly verifies decoy-root rejection, not transaction cleanup.

## Required remediation

This should be a very narrow V5→V6 fix.

Preferred architecture:

```text
permission/approval resolution
→ validation/provider/root preflight
→ canonical before snapshot
→ only then start transaction/checkpoint
→ build AgentOperationRequest
→ PRE validation
→ mutation
→ authoritative POST
→ commit/rollback
```

This prevents preflight failures from creating transaction state at all.

If repository invariants require transaction creation earlier, an explicit canonical abort/fail path is acceptable, but it must leave no ACTIVE transaction/checkpoint residue.

Do not create a new transaction manager.

Do not change Phase 7/Phase 9 validation ownership.

## Required RED tests

Use the real `TransactionManager` / `CheckpointManager` where possible.

Prove for each representative preflight failure:

```text
decoy root mismatch
missing host root
missing validation provider
before snapshot capture failure
```

that:

```text
operation does not execute
no ACTIVE transaction remains
no orphan active transaction state remains
checkpoint lifecycle is clean according to canonical manager semantics
```

At minimum one adversarial decoy-root case must use the same connected stack as AT-DP-043.

Also add a positive test proving a valid Project mutation still creates/commits or rolls back its transaction normally.

## Required implementation evidence

```text
PROJECT_PREFLIGHT_BEFORE_TRANSACTION=PASS
PROJECT_PREFLIGHT_FAILURE_ACTIVE_TRANSACTIONS=0
PROJECT_PREFLIGHT_FAILURE_ORPHAN_CHECKPOINTS=0
VALID_PROJECT_TRANSACTION_LIFECYCLE=PASS
```

---

# 13. Quality-gate assessment

Implementation-machine evidence reports:

```text
FOCUSED_TESTS=138 PASS
VALIDATION_SUITE=533 PASS
AGENT_RUNTIME_SUITE=3434 PASS
DOMAIN_SUITE=9676 PASS
GLOBAL_SUITE=15281 PASS
```

Independent auditor replay:

```text
parser regression subset: 7 passed
pytest parser/steps: 14 passed
ChangeSetBuilder public seam: 4 passed
compileall: PASS
```

Full Domain/global replay is unavailable only because the auditor environment lacks `libcst`.

## Ruff / format

V5 evidence truthfully records historical full-tree debt:

```text
RUFF_FULL_GATE=841 findings
FORMAT_FULL_GATE=318 files
```

and reports:

```text
RUFF_V5_DELTA_GATE=PASS
FORMAT_V5_DELTA_GATE=PASS
```

No false full-tree PASS is claimed.

This is accepted under the established repository baseline/debt convention.

---

# 14. DP-043 independent assessment

The Design Point requires Domain Intelligence to integrate with the canonical validation system without creating competing validation truth, and to ensure Project mutations cannot bypass mandatory Phase 7 validation.

V5 now demonstrates:

```text
Phase 7 owns canonical impact analysis
Phase 7 owns ValidationPipeline/results
Phase 9 AgentValidationAdapter executes runtime validation
actual Project post-change scope is used
affected tests can block acceptance
host root cannot be redirected by caller
derivation failures fail closed
stronger impact cannot be downgraded
post-validation failure restores Project state
commit gate ownership remains Phase 7
```

The remaining transaction-state leak does not allow an invalid mutation to be accepted and does not alter validation authority.

Therefore:

```text
DP-043=VERIFIED_EXISTING
```

---

# 15. AT-DP-043 independent assessment

V5 connected acceptance now uses real canonical components for the closure-critical Project path:

```text
real Domain operation registry
real AgentExecutionAdapter
real AgentValidationAdapter
real Phase 7 ChangeSetBuilder
real Phase 7 ChangeImpactAnalyzer
real TransactionManager
real CheckpointManager
real CheckpointRestorationManager
real CheckpointRestorationRollbackExecutor
temp Project tree
whole-tree resource provider
```

It proves:

```text
nested source mutation
actual changed-file scope
affected-test failure
caller decoy-root rejection
structural/public escalation
derivation failure
real file restoration
```

Previously accepted pack/provider/workflow/cross-domain/specialized-result acceptance remains in the same AT.

Therefore:

```text
AT-DP-043=PASS
```

---

# 16. Closure eligibility

The validation architecture and acceptance are now verified.

However project rules require:

```text
MAJORS=0
```

before closure.

The active-transaction leak is a real MAJOR.

Therefore:

```text
CLOSURE_ELIGIBLE=NO
```

No closure commit should be created yet.

Phase 10.44 must not start.

---

# 17. Required targeted V5 → V6 remediation

This remediation should touch only transaction/preflight ordering plus tests/evidence/docs if needed.

Do **not** reopen:

```text
Phase 7 ChangeImpactAnalyzer mapping
POST mutation ChangeSet
host root authority semantics
pytest parser
Ruff parser
pack lifecycle
workflow bridge
cross-domain bridge
specialized-result gate
Project affected-test logic
canonical rollback behavior
```

unless a regression proves the transaction-order fix breaks them.

## Block A — preflight before transaction creation

Resolve before `start_transaction()`:

```text
operation validation provider availability
trusted Project root
caller-root consistency
pre-validation requirement materialization
canonical before snapshot
```

for Project code mutations.

Only after successful preflight may the transaction/checkpoint be created.

## Block B — transaction leak regressions

Add connected tests proving:

```text
decoy root → no transaction created
missing host root → no transaction created
missing provider → no transaction created
before snapshot failure → no transaction created
```

or equivalent canonical closed/failed states with zero ACTIVE transaction residue.

## Block C — positive transaction lifecycle regression

Prove:

```text
valid accepted mutation → committed transaction
post-validation rejection → rolled-back transaction + restored content
```

Existing rollback AT may be reused for the second half if it can additionally assert transaction status.

## Block D — evidence

Create:

```text
docs/audits/phase-10.43-v6-remediation-evidence.md
```

Record exact counts and:

```text
MAJOR_V5_01=REMEDIATED

PROJECT_PREFLIGHT_BEFORE_TRANSACTION=PASS
PROJECT_PREFLIGHT_FAILURE_ACTIVE_TRANSACTIONS=0
PROJECT_PREFLIGHT_FAILURE_ORPHAN_CHECKPOINTS=0
VALID_PROJECT_TRANSACTION_LIFECYCLE=PASS

DP_043=VERIFIED_EXISTING_PENDING_FINAL_REAUDIT
AT_DP_043=PASS_CONNECTED

WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED
PUSH=NO
MERGE=NO
```

Do not self-audit.

Then generate:

```text
phase-10.43-audit-v6-<HEAD>.tar.gz
```

from exact committed HEAD.

---

# 18. Final V5 audit status

```text
PHASE=10.43
AUDIT_VERSION=V5

AUDITED_HEAD=1d4cb19855aaedae5eccbde3e97d700bf7a363ce
AUDIT_BUNDLE_SHA256=bb035756dd51403518304f3d7d16c8b92331ecca36c62fa557fb492fc4d29f81

BUNDLE_SHA256=PASS
GZIP=PASS
EXACT_HEAD=PASS
ARCHIVE_PATH_SAFETY=PASS
COMPILEALL_AUDITOR=PASS

PARSER_REGRESSION_REPLAY=PASS
CHANGESET_PUBLIC_SEAM_REPLAY=PASS
CANONICAL_NESTED_CHANGE_PROBE=PASS

V4_BLOCKER_01=REMEDIATED
V4_BLOCKER_02=REMEDIATED
V4_BLOCKER_03=REMEDIATED
V4_BLOCKER_04=REMEDIATED
V4_MAJOR_01=REMEDIATED
V4_MAJOR_02=REMEDIATED

MAJOR_V5_01=PRE_MUTATION_PREFLIGHT_LEAKS_ACTIVE_TRANSACTION_STATE

BLOCKERS=0
MAJORS=1
MINORS=0

DP-043=VERIFIED_EXISTING
AT-DP-043=PASS
CLOSURE_ELIGIBLE=NO

NEXT=TARGETED_V5_TO_V6_TRANSACTION_PREFLIGHT_REMEDIATION
```
