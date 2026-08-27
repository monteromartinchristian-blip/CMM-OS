# Phase 10.30 — Project Domain Independent Re-Audit V5

**Date:** 2026-08-27
**Candidate HEAD:** `de5211c81df7ae912f243f0b3e2edec8467accb5`
**Bundle:** `phase-10.30-audit-v5.tar.gz`
**Bundle SHA-256:** `170898dc1cd44e38c48e3f114073f63dd21575d15b876fdfb94c884a578152da`
**Independent verdict:** **FAIL — one targeted trace-authority binding remediation remains**

```text
PHASE10_30_INDEPENDENT_REAUDIT_V5=FAIL

BLOCKERS=0
MAJORS=1
MINORS=0

B1=CLOSED
B2=CLOSED
M1=CLOSED
M2=OPEN
M3=CLOSED
M4=CLOSED
M5=CLOSED

V4_B1_FILE_MODIFY_CAPABILITY_DETACHED=CLOSED
V4_B2_RESOURCE_KIND_ALLOWLIST_FAIL_OPEN=CLOSED
V4_M1_RUNTIME_ARTIFACT_TRACE_BINDING_INCOMPLETE=OPEN
V4_M2_ROLLBACK_FAILURE_CONTRACT_UNSTRUCTURED=CLOSED
V4_M3_GLOBAL_SUITE_NOT_VERIFIED=CLOSED

DP_030=REQUIRES_PHASE_INSPECTION
AT_DP_030=NOT_INDEPENDENTLY_ACCEPTED
PROJECT_CLOSURE_ADVERSARIAL_GATE=NOT_INDEPENDENTLY_ACCEPTED

INDEPENDENT_REAUDIT_V6=REQUIRED
NEXT=TARGETED_TRACE_AUTHORITY_BINDING_REMEDIATION_V5
```

---

## 1. Independent bundle verification

The uploaded V5 artifact is a valid full committed-HEAD snapshot.

```text
SHA256=170898dc1cd44e38c48e3f114073f63dd21575d15b876fdfb94c884a578152da
ARCHIVE_ENTRIES=1836
ROOT_PREFIX=ABSENT
FULL_HEAD_ARCHIVE=PASS
TAR_COMMIT_ID=de5211c81df7ae912f243f0b3e2edec8467accb5
CANDIDATE_HEAD=de5211c81df7ae912f243f0b3e2edec8467accb5
COMMIT_ID_MATCH=PASS
```

Required Phase 10.30 paths are present, including:

```text
cmm/domains/project/operations.py
cmm/domains/permission_evaluator.py
cmm/domains/operation_execution.py
cmm/agent_runtime/checkpoint_rollback_executor.py
cmm/agent_runtime/transaction_manager.py
tests/domains/test_project_domain_self_development_e2e.py
tests/domains/test_project_domain_dp030_acceptance.py
tests/domains/test_project_domain_closure_adversarial.py
docs/audits/phase-10.30-project-independent-reaudit-v4.md
ROADMAP.md
```

Independent structural/static verification:

```text
PROJECT_PRODUCTION_MODULES=14

ENTITIES=27
RESOURCES=22
RULES=18
OPERATIONS=20
WORKFLOWS=12

CATALOG_UNIQUENESS=PASS
WORKFLOW_PARTITION=4_GENERIC_PLUS_8_SOFTWARE

AT_DP_030_CHECKPOINT_INVOCATIONS=56
AT_DP_030_UNIQUE_CHECKPOINTS=56

PROJECT_CLOSURE_ATTACK_CLASSES=34
PROJECT_CLOSURE_UNIQUE_ATTACK_CLASSES=34

FORBIDDEN_PROJECT_LOCAL_INFRA=ABSENT
DOMAIN_TRACE_PROBE=ABSENT

COMPILEALL_FULL=PASS
```

The independent audit environment does not contain the repository dependency `libcst`, so the repository pytest suites cannot be independently re-executed here. This is an auditor-environment limitation rather than a candidate defect.

The implementation transcript does show the Project, Domain and full repository test commands being launched and reports:

```text
PROJECT_TESTS=117
DOMAIN_TESTS=6587
GLOBAL_TESTS=12125
RUFF=PASS
FORMAT=PASS
COMPILEALL=PASS
```

That evidence is accepted as supporting evidence for V4-M3. It is not used to override independent source inspection.

---

# 2. V4 finding disposition

## V4-B1 — FILE_MODIFY detached from `project.modify_code`

**Status: CLOSED**

V5 restores the canonical capability directly on the mutation operation:

```python
required_permissions = (
    (PermissionCapability.FILE_MODIFY.value,)
    if op_id == "project.modify_code"
    else ()
)
```

Therefore:

```text
project.modify_code.required_permissions=("file.modify",)
```

The invalid historical strings are not restored as capabilities:

```text
domain-permission:project:1.0.0
permission.file.modify
```

The connected operation path now evaluates both the declared FILE_MODIFY requirement and the generic operation-execution approval requirement.

The E2E helper creates canonical approval requests for every typed requirement, binds them to the concrete `DomainOperationRequest.calculate_fingerprint()`, approves them without pre-consuming them, and sends the complete:

```text
requirement_id -> approval_request_id
```

mapping through:

```python
metadata["approval_request_ids"]
```

The shared `DomainPermissionGate` validates and consumes that approval batch before dispatch.

The adversarial closure test now includes connected cases proving:

```text
generic OPERATION_EXECUTE approval alone cannot authorize mutation
FILE_MODIFY-prohibited policy blocks mutation
forged/mismatched FILE_MODIFY approval blocks mutation
valid OPERATION_EXECUTE + FILE_MODIFY approvals allow mutation
```

Result:

```text
V4_B1_FILE_MODIFY_CAPABILITY_DETACHED=CLOSED
M2_FILE_MODIFY_CAPABILITY_EVALUATED_IN_OPERATION_PATH=PASS
M2_FILE_MODIFY_APPROVAL_BOUND_TO_OPERATION=PASS
M2_GENERIC_OPERATION_APPROVAL_ALONE_CANNOT_MUTATE=PASS
```

---

## V4-B2 — resource-kind allowlist fail-open

**Status: CLOSED**

V5 restores the fail-closed evaluator semantics.

The V4 relaxation:

```python
request.resource_kind is not None
and policy.allowed_resource_kinds is not None
and ...
```

is gone.

The current decision path is effectively:

```python
elif policy.allowed_resource_kinds is not None and not _allowlist(
    policy.allowed_resource_kinds,
    request.resource_kind,
):
    denied_reason = "resource_kind_allowlist_not_matched"
```

Therefore, when a policy configures `allowed_resource_kinds`, omitting `resource_kind` no longer bypasses the allowlist.

Positive matched-kind behavior remains supported.

Result:

```text
V4_B2_RESOURCE_KIND_ALLOWLIST_FAIL_OPEN=CLOSED
RESOURCE_KIND_ALLOWLIST_MISSING_KIND_FAIL_CLOSED=PASS
```

---

## V4-M2 — rollback failure contract unstructured

**Status: CLOSED**

The V4 successful restoration path remains intact.

V5 additionally adds a terminal failed-rollback path.

`CheckpointRestorationRollbackExecutor` now converts established runtime restoration errors into a failed rollback result rather than allowing them to escape.

`TransactionManager` exposes a generic:

```python
mark_failed(...)
```

terminal transition.

`DefaultDomainOperationOrchestrator._failure_with_rollback(...)` now handles rollback failure by returning a structured Domain Operation result:

```text
DomainOperationResult.status=FAILED
rollback_result.attempted=True
rollback_result.succeeded=False
rollback_result.error=<structured DomainOperationRollbackError>
transaction status=FAILED
```

Tests cover:

```text
invalid/missing checkpoint
resource-provider restoration failure
post-restoration validation failure
rollback-executor exception
```

while preserving the successful rollback:

```text
ROLLED_BACK
source restored
worktree restored
```

Result:

```text
V4_M2_ROLLBACK_FAILURE_CONTRACT_UNSTRUCTURED=CLOSED
M2_ROLLBACK_FAILURE_CONTRACT_STRUCTURED=PASS
M2_ROLLBACK_FAILURE_TRANSACTION_TERMINAL=PASS
```

---

## V4-M3 — global suite not verified

**Status: CLOSED**

Unlike V4, the V5 implementation transcript contains a full repository invocation:

```bash
.venv/bin/python -m pytest -q
```

and reports:

```text
PROJECT_TESTS=117
DOMAIN_TESTS=6587
GLOBAL_TESTS=12125
```

The independent audit environment cannot re-run pytest because `libcst` is absent, but the missing-execution defect from V4 is no longer present.

Result:

```text
V4_M3_GLOBAL_SUITE_NOT_VERIFIED=CLOSED
```

---

# 3. Remaining MAJOR — authoritative permission/approval evidence is still absent from the final trace

## V4-M1 — Runtime artifact trace binding incomplete

**Status: OPEN — MAJOR**

V5 materially improves artifact identity binding.

The self-development E2E now derives deterministic references for real runtime artifacts:

```python
project_context_ref = (
    "project-context:sha256:"
    + sha256_digest(project_context.serialize())
)

development_plan_ref = (
    "development-plan:sha256:"
    + sha256_digest(dev_plan.serialize())
)

rollback_ref = (
    "rollback-result:sha256:"
    + sha256_digest(trial_result.rollback_result.to_dict())
)

readiness_ref = (
    "prepare-commit-readiness:sha256:"
    + sha256_digest(readiness_ready)
)
```

It also uses actual runtime IDs for:

```text
ApprovalRequest.id
DomainOperationResult.result_id
transaction_id
ValidationResult.id
```

This closes the V4 criticism about using only scenario labels such as:

```text
ctx:project:{total_python_files}
plan:project.self_development:auth_service
ref:project:arch:auth
```

However, the frozen trace contract is broader than artifact identity alone.

The Phase 10.30 design requires the trace to expose/reference the actual:

```text
permission decisions
approval decisions
execution references
validation references
rollback references
commit-readiness
```

The V5 final E2E trace still omits the authoritative permission/approval chain that actually allowed `project.modify_code`.

### 3.1 No permission-decision reference in the final E2E trace

Independent source inspection finds no final:

```python
DomainTraceReferenceKind.PERMISSION_DECISION
```

for the successful mutation path.

Observed:

```text
E2E_PERMISSION_DECISION_REF=ABSENT
```

### 3.2 Only one approval request is traced

The final E2E trace contains a single `APPROVAL_REQUEST` reference:

```python
ref_app_req = build_project_trace_reference(
    ref_id=app_request.id,
    kind=DomainTraceReferenceKind.APPROVAL_REQUEST,
)
```

`app_request` is the primary generic operation approval used for availability.

But V5 correctly requires a **dual authority chain** for mutation:

```text
OPERATION_EXECUTE approval
+
FILE_MODIFY approval
```

The FILE_MODIFY approval request that is present in the actual `approval_request_ids` mapping is not independently represented in the final Project memory/trace evidence.

Observed:

```text
E2E_APPROVAL_REQUEST_REF_COUNT=1
FILE_MODIFY_APPROVAL_TRACE_REF=ABSENT
```

### 3.3 No approval-decision/evidence reference

The final E2E trace does not contain:

```python
DomainTraceReferenceKind.APPROVAL_DECISION
```

or an equivalent concrete reference to the actual consumed dual-approval decision/evidence.

Observed:

```text
E2E_APPROVAL_DECISION_REF=ABSENT
```

### 3.4 Successful DomainOperationResult drops the permission gate evidence

Blocked/waiting outcomes preserve permission-gate trace metadata.

The successful execution result, however, does not carry the authoritative gate evidence forward in a reference-safe form.

Consequently, downstream Project trace construction must currently reconstruct or side-channel approval identifiers from local test variables rather than consuming authoritative permission/approval evidence from the successful Domain Operation result.

That leaves the production lifecycle incomplete:

```text
permission/approval authority
→ operation execution
→ successful DomainOperationResult
→ trace
```

The first arrow is now real; the last binding is not.

### 3.5 AT-DP-030 checkpoint 54 still overstates its connected evidence

Checkpoint 54 is labeled as proving:

```text
software trace includes permission/execution/validation refs
```

but the assembled `sw_trace_refs` contains execution/transaction/rollback/validation/readiness references and still does not include:

```text
PERMISSION_DECISION
APPROVAL_REQUEST
APPROVAL_DECISION
```

Independent disposition:

```text
DP54_PERMISSION_DECISION_REF=ABSENT
DP54_APPROVAL_REQUEST_REF=ABSENT
DP54_APPROVAL_DECISION_REF=ABSENT
```

Therefore checkpoint 54 is not yet a connected proof of the trace contract it claims.

---

# 4. Why this remains an M2 closure defect

The frozen self-development requirement is not merely:

```text
code mutates safely
rollback works
validation works
```

It is a complete controlled lifecycle.

V5 now proves the actual authority chain at execution time:

```text
FILE_MODIFY
+
OPERATION_EXECUTE
+
real approvals
→ DomainPermissionGate
→ orchestrator
→ mutation
```

But the final trace drops that authority chain.

A complete Project self-development trace must permit an auditor to determine, from reference-only runtime evidence, which permission/approval decisions authorized the mutation that produced the traced operation result.

Without those references, the runtime execution is secure but the lifecycle provenance remains incomplete.

Result:

```text
V4_M1_RUNTIME_ARTIFACT_TRACE_BINDING_INCOMPLETE=OPEN
M2_COMPLETE_RUNTIME_ARTIFACT_TRACE_BINDING=FAIL
M2=OPEN
```

---

# 5. AT-DP-030 disposition

Independent AST inspection confirms:

```text
AT_DP_030_CHECKPOINT_INVOCATIONS=56
AT_DP_030_UNIQUE_LABELS=56
```

The V5 security repairs materially improve checkpoints 41, 42, 44 and 45.

Accepted:

```text
41 real FILE_MODIFY requirement
42 project.modify_code declares canonical file.modify
44 real multi-approval orchestrated mutation
45 real multi-approval forced failure + shared rollback
46 real Phase 7 validation
```

Not yet accepted:

```text
54 complete software trace authority binding
```

Therefore:

```text
AT_DP_030=NOT_INDEPENDENTLY_ACCEPTED
AT_DP_030_CHECKPOINTS=56
```

Keep the count exactly 56.

---

# 6. Permanent adversarial closure gate disposition

Independent AST inspection confirms:

```text
PROJECT_CLOSURE_ATTACK_CLASSES=34
UNIQUE_ATTACK_CLASSES=34
```

The V5 permission and rollback adversarial coverage is materially stronger and closes the V4 security defects.

However the permanent closure gate does not yet catch the remaining lifecycle provenance omission: a successful mutation trace can omit FILE_MODIFY/approval authority evidence while the closure suite remains green.

The next remediation should strengthen an existing trace-related `test_attack_*` function with subcases rather than create a 35th top-level attack.

Therefore:

```text
PROJECT_CLOSURE_ADVERSARIAL_GATE=NOT_INDEPENDENTLY_ACCEPTED
PROJECT_CLOSURE_ATTACK_CLASSES=34
```

---

# 7. Previously closed findings remain closed

Independent V5 review does not reopen:

```text
Original B1 — Project→Life Plan runtime-owned authorization
Original B2 — caller cannot forge committed state
Original M1 — Project bootstrap extends Life Plan
Original M3 — independent trace inventory/validation machinery
Original M4 — canonical docs/catalog equality
Original M5 — analyzer-issued software context
```

The remaining finding is limited to the self-development trace’s authority provenance.

---

# 8. Required V5 → V6 remediation scope

Do not redesign Project Domain.

Do not reopen the fixed V4 permission/rollback behavior.

The next remediation should be limited to:

```text
1. preserve authoritative permission-gate evidence on successful
   DomainOperationResult in a reference-safe form

2. ensure successful project.modify_code trace includes actual
   permission decision reference(s)

3. include all real approval authorities used by the mutation:
   - OPERATION_EXECUTE approval request/evidence
   - FILE_MODIFY approval request/evidence

4. connect those authoritative refs into:
   - Project memory proposal/binding evidence
   - final Project self-development trace
   - independent trace inventory

5. repair AT-DP-030 checkpoint 54 so its label is literally true

6. strengthen one existing trace-related adversarial test so successful
   mutation trace cannot omit or substitute FILE_MODIFY authority evidence

7. preserve exactly:
   - 14 Project modules
   - 27/22/18/20/12 catalog
   - 56 AT-DP checkpoints
   - 34 top-level attack functions
   - 4 generic + 8 software workflows

8. rerun:
   - focused permission/trace/runtime suites
   - Project suite
   - Domain suite
   - full repository suite
   - Ruff
   - format
   - compileall

9. generate full committed HEAD:
   phase-10.30-audit-v6.tar.gz
```

No push.
No merge.
No Phase 10.30 closure before independent Re-audit V6.

---

# 9. Final independent verdict

```text
PHASE10_30_INDEPENDENT_REAUDIT_V5=FAIL

BLOCKERS=0
MAJORS=1
MINORS=0

B1=CLOSED
B2=CLOSED
M1=CLOSED
M2=OPEN
M3=CLOSED
M4=CLOSED
M5=CLOSED

V4_B1_FILE_MODIFY_CAPABILITY_DETACHED=CLOSED
V4_B2_RESOURCE_KIND_ALLOWLIST_FAIL_OPEN=CLOSED
V4_M1_RUNTIME_ARTIFACT_TRACE_BINDING_INCOMPLETE=OPEN
V4_M2_ROLLBACK_FAILURE_CONTRACT_UNSTRUCTURED=CLOSED
V4_M3_GLOBAL_SUITE_NOT_VERIFIED=CLOSED

DP_030=REQUIRES_PHASE_INSPECTION

AT_DP_030=NOT_INDEPENDENTLY_ACCEPTED
AT_DP_030_CHECKPOINTS=56

PROJECT_CLOSURE_ADVERSARIAL_GATE=NOT_INDEPENDENTLY_ACCEPTED
PROJECT_CLOSURE_ATTACK_CLASSES=34

INDEPENDENT_REAUDIT_V6=REQUIRED

PUSH=NO
MERGE=NO
NEXT=TARGETED_TRACE_AUTHORITY_BINDING_REMEDIATION_V5
```
