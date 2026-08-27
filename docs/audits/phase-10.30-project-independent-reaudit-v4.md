# Phase 10.30 — Project Domain Independent Re-Audit V4

**Date:** 2026-08-27
**Candidate HEAD:** `29d567379480bf319d7ee230c6bf2d841a393fc7`
**Bundle:** `phase-10.30-audit-v4.tar.gz`
**Bundle SHA-256:** `4eed0c529bfef4fa7cba35cdde01291f46390a7894a6626e39686d56ef11d79a`
**Independent verdict:** **FAIL — M2 improved materially, but V4 introduces two permission-boundary blockers and leaves three majors**

```text
PHASE10_30_INDEPENDENT_REAUDIT_V4=FAIL

BLOCKERS=2
MAJORS=3
MINORS=0

B1=CLOSED
B2=CLOSED
M1=CLOSED
M2=OPEN
M3=CLOSED
M4=CLOSED
M5=CLOSED

V4_B1_FILE_MODIFY_CAPABILITY_DETACHED=OPEN
V4_B2_RESOURCE_KIND_ALLOWLIST_FAIL_OPEN=OPEN

V4_M1_RUNTIME_ARTIFACT_TRACE_BINDING_INCOMPLETE=OPEN
V4_M2_ROLLBACK_FAILURE_CONTRACT_UNSTRUCTURED=OPEN
V4_M3_GLOBAL_SUITE_NOT_VERIFIED=OPEN

DP_030=REQUIRES_PHASE_INSPECTION
AT_DP_030=NOT_INDEPENDENTLY_ACCEPTED
PROJECT_CLOSURE_ADVERSARIAL_GATE=NOT_INDEPENDENTLY_ACCEPTED

NEXT=V4_SECURITY_AND_M2_REMEDIATION
```

---

## 1. Independent bundle verification

The uploaded V4 archive is a valid full committed snapshot.

Independent verification:

```text
SHA256=4eed0c529bfef4fa7cba35cdde01291f46390a7894a6626e39686d56ef11d79a
ARCHIVE_ENTRIES=1834
ROOT_PREFIX=ABSENT
GIT_ARCHIVE_COMMIT=29d567379480bf319d7ee230c6bf2d841a393fc7
ROADMAP.md=PRESENT
V3_REAUDIT_REPORT=PRESENT
TARGETED_M2_PLAN=PRESENT
```

Frozen structural invariants remain intact:

```text
PROJECT_PRODUCTION_MODULES=14

ENTITIES=27 unique=27
RESOURCES=22 unique=22
RULES=18 unique=18
OPERATIONS=20 unique=20
WORKFLOWS=12 unique=12

DOC_CATALOG_SET_EQUALITY=(True, True, True, True, True)

AT_DP_030_CHECKPOINT_INVOCATIONS=56 unique=56
PROJECT_CLOSURE_ATTACK_CLASSES=34 unique=34

FORBIDDEN_PROJECT_LOCAL_INFRA=ABSENT
COMPILEALL_FULL=PASS
```

The audit container still lacks repository dependency `libcst`, so the full pytest suite cannot be independently executed here. This environment limitation is not counted as a candidate finding.

---

# 2. What V4 genuinely fixed

V4 materially fixes the direct-execution and manual-rollback shortcuts identified in V3.

## M2-A — authoritative Domain Operation dispatch

**Underlying dispatch path: PASS**

The E2E now builds and uses:

```text
InMemoryAgentOperationRegistry
→ InMemoryDomainOperationRegistry
→ DomainOperationExecutionDelegate
→ AgentExecutionAdapter
→ DefaultDomainOperationOrchestrator
→ injected project.modify_code implementation
```

The mutation proof calls:

```python
op_result = orchestrator.execute(approved_op_req)
```

rather than:

```python
injected_impl.execute(...)
```

The unapproved path asserts the implementation execution count remains zero and source bytes remain unchanged.

AT-DP-030 checkpoint 44 also uses `DefaultDomainOperationOrchestrator.execute(...)`.

```text
M2_MUTATION_DISPATCH_THROUGH_ORCHESTRATOR=PASS
```

This PASS is limited by V4-B1 below: the operation is now dispatched through the real gate, but the gate no longer evaluates the required `FILE_MODIFY` capability because the operation definition was weakened.

---

## M2-B — real shared rollback success path

**Underlying rollback success path: PASS**

`DefaultDomainOperationOrchestrator` now starts reversible operations with:

```python
requires_checkpoint=True
```

V4 adds the generic shared adapter:

```text
CheckpointRestorationRollbackExecutor
```

which connects:

```text
transaction_id + checkpoint_id
→ TransactionManager boundary
→ CheckpointRestorationRequest
→ CheckpointRestorationManager.restore_checkpoint(...)
```

The self-development E2E now forces a post-mutation failure through the orchestrator and verifies:

```text
DomainOperationStatus.ROLLED_BACK
rollback_result.attempted=True
rollback_result.succeeded=True
source bytes restored
git diff --stat empty
```

No manual restoration is performed after the mutation.

AT-DP-030 checkpoint 45 likewise executes the real orchestrator/rollback path.

```text
M2_REAL_TRANSACTION_CHECKPOINT_CREATED=PASS
M2_SHARED_CHECKPOINT_RESTORATION_SUCCESS_PATH=PASS
M2_ROLLBACK_RESULT_ATTEMPTED=PASS
M2_ROLLBACK_RESULT_SUCCEEDED=PASS
M2_ROLLBACK_RESTORES_SOURCE_BYTES=PASS
```

The rollback failure/error contract itself still has a major defect; see V4-M2.

---

# 3. V4-B1 — BLOCKER: `project.modify_code` no longer requires FILE_MODIFY

**Status: OPEN — BLOCKER**

This is the most important regression in V4.

The frozen Project implementation plan explicitly requires:

```text
project.modify_code must require file-modification capability and approval under policy
```

and the frozen design states:

```text
file modification requires effective permission and canonical approval where policy requires it
FILE_MODIFY is approval-gated
```

V3 declared Project operations as:

```python
req_permissions = ["domain-permission:project:1.0.0"]
if requires_approval:
    req_permissions.append("permission.file.modify")
...
required_permissions=tuple(req_permissions)
```

The V4 candidate changes all 20 Project operations to:

```python
required_permissions=()
```

The implementation agent explicitly reports this as:

```text
Aligned build_project_operation_definitions() ... to use required_permissions=()
uniformly across all operations
```

This is not a harmless normalization.

`evaluate_domain_operation(...)` evaluates capability requirements only by iterating:

```python
operation.required_permissions
```

With `required_permissions=()`, `project.modify_code` never resolves:

```text
PermissionCapability.FILE_MODIFY
```

The approval that permits the V4 E2E mutation comes only from:

```python
operation.requires_approval
→ _approval_for_operation(...)
→ action=PermissionCapability.OPERATION_EXECUTE
```

Therefore the connected mutation chain is now:

```text
OPERATION_EXECUTE policy
→ generic operation approval
→ project.modify_code
```

not the frozen:

```text
OPERATION_EXECUTE
+ FILE_MODIFY capability evaluation
+ canonical FILE_MODIFY approval
→ project.modify_code
```

The standalone adversarial test still proves that an isolated `DomainPermissionRequest(FILE_MODIFY)` returns `APPROVAL_REQUIRED`, but that result is not connected to the actual operation execution.

AT-DP-030 has the same disconnect:

```text
checkpoint 41:
    resolves FILE_MODIFY separately

checkpoints 42/44:
    evaluate/execute project.modify_code whose required_permissions is empty
```

So checkpoint 41 does not authorize checkpoint 44.

### Required fix

Do **not** restore the old invalid policy-ID token as a capability.

Use the real capability value expected by `evaluate_domain_operation(...)`, e.g. the repository-canonical equivalent of:

```python
required_permissions=(PermissionCapability.FILE_MODIFY.value,)
```

for `project.modify_code`.

Other Project operations should declare only real capability values they actually require; a domain permission policy ID is not a `PermissionCapability`.

Then prove in the orchestrated E2E that the actual approval requirement consumed by the gate has:

```text
action = FILE_MODIFY
actor/session/domain bound
request fingerprint bound
one-time consumption
```

and prove that disabling/prohibiting FILE_MODIFY blocks `project.modify_code` even if OPERATION_EXECUTE itself remains allowed.

```text
V4_B1_FILE_MODIFY_CAPABILITY_DETACHED=FAIL
```

---

# 4. V4-B2 — BLOCKER: global resource-kind allowlist became fail-open

**Status: OPEN — BLOCKER**

V4 modifies the shared global permission evaluator.

V3 behavior:

```python
elif policy.allowed_resource_kinds is not None and not _allowlist(
    policy.allowed_resource_kinds,
    request.resource_kind,
):
    denied_reason = "resource_kind_allowlist_not_matched"
```

Because `_allowlist(non_empty_allowlist, None)` returns false, a policy that restricts resource kinds denied a request that omitted `resource_kind`.

V4 changes this to:

```python
elif (
    request.resource_kind is not None
    and policy.allowed_resource_kinds is not None
    and not _allowlist(policy.allowed_resource_kinds, request.resource_kind)
):
    denied_reason = "resource_kind_allowlist_not_matched"
```

Now a caller can provide:

```text
action=RESOURCE_READ
resource_id=<some id>
resource_kind=None
```

and entirely skip a non-empty `allowed_resource_kinds` restriction.

`DomainPermissionRequest` explicitly allows this shape: `RESOURCE_READ` requires `resource_id OR resource_kind`, not both.

This is a global authorization regression affecting every domain using `allowed_resource_kinds`, not merely Project.

The V4 change in `evaluate_domain_operation(...)` that derives and supplies `resource_kind` for declared operation resources may be legitimate. The global fail-open relaxation in `evaluate_domain_policy(...)` is not required for that fix and violates the system's fail-closed permission model.

### Required fix

Restore fail-closed behavior:

```text
policy.allowed_resource_kinds is not None
+ request.resource_kind missing
→ DENY
```

Add a shared regression test:

```python
policy.allowed_resource_kinds = ("clinical",)

RESOURCE_READ(
    resource_id="resource:any",
    resource_kind=None,
)
→ DENY
reason = resource_kind_allowlist_not_matched
```

Also preserve the positive case where the canonical resolved resource kind is explicitly supplied.

```text
V4_B2_RESOURCE_KIND_ALLOWLIST_FAIL_OPEN=FAIL
```

---

# 5. V4-M1 — MAJOR: complete runtime artifact trace binding remains synthetic

**Status: OPEN — MAJOR**

V4 adds more real runtime references, which is an improvement, but the complete chain is still not identity-bound.

In the self-development E2E:

```python
proposal_content = {
    "project_context_reference": str(project_context.files[0].path),
    "plan_reference": str(dev_plan.goal),
    "approval_reference": app_request.id,
    "operation_result_reference": str(op_result.result_id),
    "transaction_reference": str(op_result.transaction_id),
    "validation_reference": str(pass_res.id),
    "readiness_reference": str(readiness_ready["change_id"]),
}
```

The actual memory proposal then uses only:

```python
affected_reference_ids=("ref:project:arch:auth",)
```

The validated `proposal_content` is not itself bound into the proposal snapshot.

The final trace uses:

```python
ref_ctx = "ctx:project:{total_python_files}"
ref_plan = "plan:project.self_development:auth_service"
```

These are synthetic labels, not identities/content digests of the actual `ProjectContext` and `DevelopmentPlan`.

Two unrelated project contexts with the same number of Python files can produce the same context reference. Different plans for the same fixed scenario can produce the same plan reference.

AT-DP-030 checkpoint 54 is also still declarative:

```text
op:project.run_validation:1.0.0
op:project.prepare_commit:1.0.0
```

rather than carrying the actual operation/validation/readiness artifacts created in checkpoints 44–48.

### Required fix

Bind deterministic identities/digests of the actual serialized runtime artifacts.

For example, using existing shared digest/reference facilities:

```text
ProjectContext.serialize() → digest/reference
DevelopmentPlan.serialize() → digest/reference
ApprovalRequest.id
DomainOperationResult.result_id
transaction_id
rollback result / failed operation result
ValidationResult.id
readiness change/result reference
```

The memory proposal/binding and final trace inventory must carry those actual references, not merely validate a detached dictionary beside them.

```text
V4_M1_RUNTIME_ARTIFACT_TRACE_BINDING_INCOMPLETE=FAIL
```

---

# 6. V4-M2 — MAJOR: rollback failure path is not converted to structured failure

**Status: OPEN — MAJOR**

The new `CheckpointRestorationRollbackExecutor` proves the success path, but its failure behavior does not satisfy the targeted remediation plan's fail-closed structured contract.

The adapter directly executes:

```python
boundary = self._transaction_manager.get_boundary(transaction_id)
result = self._restoration_manager.restore_checkpoint(...)
return bool(result.success)
```

`CheckpointRestorationManager.restore_checkpoint(...)` can raise, among others:

```text
CheckpointExpiredError
CheckpointInvalidError
CheckpointIntegrityError
CheckpointRestorationBlockedError
CheckpointRestorationError
CheckpointRestorationValidationError
...
```

The normal `_failure_with_rollback(...)` path in `DefaultDomainOperationOrchestrator` does not catch these exceptions around:

```python
self._rollback_executor.rollback(...)
```

So a restoration error can escape the Domain Operation contract instead of producing:

```text
DomainOperationResult(status=FAILED)
rollback_result.attempted=True
rollback_result.succeeded=False
```

and can leave the transaction in `ROLLING_BACK`.

The targeted remediation plan explicitly required the shared adapter to fail closed on restoration failure.

### Required fix

Either:

1. make `CheckpointRestorationRollbackExecutor.rollback(...)` catch the established restoration/runtime exceptions and return `False`; or
2. make `_failure_with_rollback(...)` catch the shared rollback exception contract and emit a structured failed `DomainOperationResult`.

Add real regressions for:

```text
missing/invalid checkpoint
restoration provider failure
post-restoration validation failure
```

and assert no exception escapes the operation boundary and the transaction ends in an explicit failed/rollback-failed terminal state.

```text
V4_M2_ROLLBACK_FAILURE_CONTRACT_UNSTRUCTURED=FAIL
```

---

# 7. V4-M3 — MAJOR: required global suite was not executed

**Status: OPEN — MAJOR**

The targeted remediation plan explicitly required:

```bash
.venv/bin/python -m pytest -q
```

after the Project and Domain suites.

The implementation transcript records focused Project/rollback suites and:

```bash
.venv/bin/python -m pytest -q tests/domains
```

but contains no final standalone full-repository:

```bash
.venv/bin/python -m pytest -q
```

for this V4 candidate.

The agent's final report consequently gives:

```text
Project Domain Suite = 114 / 114
Runtime rollback suites = 10 / 10
Full Domain Suite = 6,581 / 6,581
```

but no `GLOBAL_TESTS` count.

This matters more than a routine process omission because V4 changes shared runtime and shared permission code:

```text
cmm/domains/operation_execution.py
cmm/domains/permission_adapters.py
cmm/domains/permission_evaluator.py
cmm/agent_runtime/checkpoint_rollback_executor.py
```

A green Domain suite alone does not verify non-domain execution/runtime/validation tests.

### Required fix

After repairing the blockers/majors, run fresh:

```bash
.venv/bin/python -m pytest -q
```

and report the exact total.

```text
V4_M3_GLOBAL_SUITE_NOT_VERIFIED=FAIL
```

---

# 8. Original V2/V3 finding disposition

The previous findings remain:

```text
B1 Runtime-owned Project→Life Plan authorization = CLOSED
B2 Caller-controlled committed state = CLOSED
M1 Bootstrap extends Life Plan = CLOSED
M3 Independent trace inventory validation = CLOSED
M4 Catalog/docs exact equality + lineage = CLOSED
M5 Analyzer-issued software context = CLOSED
```

M2 remains OPEN because the authoritative chain is not yet accepted end-to-end after the V4 permission regression and incomplete artifact binding.

Detailed M2 matrix:

```text
M2_REAL_PROJECT_ANALYSIS=PASS
M2_REAL_SHARED_PLANNING=PASS

M2_DOMAIN_OPERATION_ORCHESTRATOR_USED=PASS
M2_UNAPPROVED_GENERIC_OPERATION_BLOCKED=PASS

M2_FILE_MODIFY_CAPABILITY_EVALUATED_IN_OPERATION_PATH=FAIL
M2_FILE_MODIFY_APPROVAL_BOUND_TO_OPERATION=FAIL

M2_REAL_TRANSACTION_CHECKPOINT_CREATED=PASS
M2_SHARED_ROLLBACK_SUCCESS_PATH=PASS
M2_ROLLBACK_RESULT_ATTEMPTED=PASS
M2_ROLLBACK_RESULT_SUCCEEDED=PASS
M2_ROLLBACK_RESTORES_SOURCE_BYTES=PASS
M2_ROLLBACK_RESTORES_WORKTREE=PASS
M2_ROLLBACK_FAILURE_CONTRACT_STRUCTURED=FAIL

M2_REAL_PHASE7_VALIDATION=PASS
M2_FAILED_VALIDATION_NOT_READY=PASS
M2_SUCCESSFUL_VALIDATION_READY_NOT_COMMITTED=PASS
M2_PREPARE_COMMIT_HEAD_UNCHANGED=PASS

M2_COMPLETE_RUNTIME_ARTIFACT_TRACE_BINDING=FAIL
```

---

# 9. AT-DP-030 disposition

Independent AST inspection confirms:

```text
AT_DP_030_CHECKPOINT_INVOCATIONS=56
AT_DP_030_UNIQUE_LABELS=56
```

Checkpoints 44/45 now execute real orchestrator/rollback behavior and materially improve V3.

However:

```text
41 resolves FILE_MODIFY separately
42/44 execute an operation definition with required_permissions=()
```

so the connected gate does not prove that the FILE_MODIFY capability from checkpoint 41 is the authority consumed by the mutation in checkpoint 44.

Checkpoint 54 also remains detached from the actual runtime artifacts.

Therefore:

```text
AT_DP_030=NOT_INDEPENDENTLY_ACCEPTED
AT_DP_030_CHECKPOINTS=56
```

---

# 10. Permanent adversarial gate disposition

Independent AST inspection confirms:

```text
PROJECT_CLOSURE_ATTACK_CLASSES=34
UNIQUE_ATTACK_CLASSES=34
```

The new orchestrated rollback adversarial subcase is useful.

But:

- `FILE_MODIFY_WITHOUT_APPROVAL_REJECTED` only tests an isolated resolver request, not the real `project.modify_code` operation path;
- no adversarial test catches `allowed_resource_kinds` omission bypass;
- the operation definition has been weakened so that the mutation path does not require FILE_MODIFY.

Therefore:

```text
PROJECT_CLOSURE_ADVERSARIAL_GATE=NOT_INDEPENDENTLY_ACCEPTED
PROJECT_CLOSURE_ATTACK_CLASSES=34
```

Keep the top-level count at exactly 34; strengthen existing attack functions with subcases rather than adding top-level attacks.

---

# 11. Verification evidence disposition

Agent-reported evidence:

```text
PROJECT_TESTS=114 PASS
RUNTIME_TRANSACTION_ROLLBACK_TESTS=10 PASS
DOMAIN_TESTS=6581 PASS
RUFF=PASS (reported)
FORMAT=PASS (reported)
COMPILEALL=PASS (reported)
```

Independent V4 structural evidence:

```text
FULL_HEAD_ARCHIVE=PASS
COMPILEALL_FULL=PASS
PROJECT_MODULES=14
CATALOG=27/22/18/20/12
DOC_CATALOG_SET_EQUALITY=PASS
AT_DP_030_CHECKPOINTS=56
PROJECT_CLOSURE_ATTACK_CLASSES=34
```

Missing candidate evidence:

```text
GLOBAL_TESTS=NOT_RUN / NOT_REPORTED
```

The implementation transcript itself shows no final full-repository pytest invocation for V4.

---

# 12. Required V4 remediation scope

Do not redesign Phase 10.30 and do not reopen closed B1/B2/M1/M3/M4/M5.

The next remediation should be narrowly limited to:

```text
1. restore real FILE_MODIFY capability binding for project.modify_code
   - use canonical PermissionCapability value
   - do not put policy IDs in required_permissions
   - prove the gate consumes FILE_MODIFY approval

2. revert the global resource-kind fail-open relaxation
   - missing resource_kind + configured allowlist = DENY
   - keep explicit canonical resource-kind binding in operation adapter

3. make rollback restoration failures return structured fail-closed operation results

4. bind actual ProjectContext/DevelopmentPlan/runtime artifact identities/digests
   into memory/trace evidence and AT-DP-030

5. rerun:
   Project
   shared rollback/permission regressions
   all domains
   full repository suite

6. preserve:
   14 modules
   27/22/18/20/12 catalog
   56 AT-DP checkpoints
   34 top-level adversarial attacks
```

No push. No merge. No Phase 10.30 closure before independent Re-audit V5.

---

# 13. Final independent verdict

```text
PHASE10_30_INDEPENDENT_REAUDIT_V4=FAIL

BLOCKERS=2
MAJORS=3
MINORS=0

B1=CLOSED
B2=CLOSED
M1=CLOSED
M2=OPEN
M3=CLOSED
M4=CLOSED
M5=CLOSED

V4_B1_FILE_MODIFY_CAPABILITY_DETACHED=OPEN
V4_B2_RESOURCE_KIND_ALLOWLIST_FAIL_OPEN=OPEN

V4_M1_RUNTIME_ARTIFACT_TRACE_BINDING_INCOMPLETE=OPEN
V4_M2_ROLLBACK_FAILURE_CONTRACT_UNSTRUCTURED=OPEN
V4_M3_GLOBAL_SUITE_NOT_VERIFIED=OPEN

DP_030=REQUIRES_PHASE_INSPECTION
INDEPENDENT_REAUDIT_V5=REQUIRED

AT_DP_030=NOT_INDEPENDENTLY_ACCEPTED
PROJECT_CLOSURE_ADVERSARIAL_GATE=NOT_INDEPENDENTLY_ACCEPTED

PUSH=NO
MERGE=NO

NEXT=V4_SECURITY_AND_M2_REMEDIATION
```
