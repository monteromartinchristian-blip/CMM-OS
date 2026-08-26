# Phase 10.30 — Project Domain Independent Re-Audit V3

**Date:** 2026-08-27
**Candidate HEAD:** `dc6b10ff9ac7e1bc2b681cdf368f8acb97eb0945`
**Bundle:** `phase-10.30-audit-v3.tar.gz`
**Bundle SHA-256:** `ab194434000d3175cb150e1a1ab2eb497f65ef0a8b5ec1c4de3d51705ba0e139`
**Independent verdict:** **FAIL — one targeted M2 remediation remains**

```text
PHASE10_30_INDEPENDENT_REAUDIT_V3=FAIL
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

DP_030=REQUIRES_PHASE_INSPECTION
AT_DP_030=NOT_INDEPENDENTLY_ACCEPTED
CLOSURE_ADVERSARIAL_GATE=NOT_INDEPENDENTLY_ACCEPTED
NEXT=TARGETED_M2_REMEDIATION_V3
```

---

## 1. Independent bundle verification

The uploaded V3 archive is a valid full versioned snapshot.

Independent verification:

```text
SHA256=ab194434000d3175cb150e1a1ab2eb497f65ef0a8b5ec1c4de3d51705ba0e139
ARCHIVE_ENTRIES=1830
ROOT_PREFIX=ABSENT
ROADMAP.md=PRESENT
FULL CMM SOURCE TREE=PRESENT
```

`git get-tar-commit-id` independently identifies:

```text
dc6b10ff9ac7e1bc2b681cdf368f8acb97eb0945
```

Independent static/structural checks:

```text
PROJECT_PRODUCTION_MODULES=14
PROJECT_TEST_FILES=18
ENTITIES=27 unique=27
RESOURCES=22 unique=22
RULES=18 unique=18
OPERATIONS=20 unique=20
WORKFLOWS=12 unique=12
AT_DP_030_CHECKPOINT_INVOCATIONS=56 unique=56
ADVERSARIAL_ATTACK_CLASSES=34 unique=34
DOC_CATALOG_SET_EQUALITY=(True, True, True, True, True)
COMPILEALL_FULL=PASS
FORBIDDEN_PROJECT_INFRA=ABSENT
DOMAIN_TRACE_PROBE=ABSENT
PROJECT_DIRECT_EXECUTION_TOKEN=ABSENT
```

The independent audit container does not have the repository dependency `libcst`, so the full pytest suite cannot be independently re-executed here. This is an auditor-environment limitation, not a candidate defect. The implementation agent reported `12,112 passed`; that report is treated as supporting evidence only, not as the basis for this independent verdict.

---

# 2. V2 finding disposition

## B1 — Runtime-owned Project → Life Plan authorization

**Status: CLOSED**

The authorizer signature is now:

```python
authorize_project_life_plan_contribution(
    raw_payload,
    *,
    permission_request,
    permission_gate=None,
    permission_resolver=None,
    now=None,
)
```

There is no caller-supplied `permission_decision` or generic `authorization_evidence` parameter.

The function requires exactly one real shared evaluator:

```text
DomainPermissionGate
or
DomainPermissionResolver
```

and obtains the decision inside the call.

The shared request is checked for:

```text
source = domain:project
target = domain:life-plan
authorized capability
expiry
```

The gate path additionally binds the returned runtime result to the exact request context through:

```text
action
domain
actor
session
decision id
cross_domain_request metadata
```

AT-DP-030 checkpoints 27/28 now execute a real successful Project → Life Plan authorization path and then consume the minimized contribution through the Life Plan cross-domain evaluator.

The adversarial gate explicitly rejects the V2 typed-decision forgery.

```text
B1_RUNTIME_OWNED_AUTHORIZATION_ONLY=PASS
B1_CALLER_TYPED_DECISION_REJECTED=PASS
B1_SUCCESSFUL_AUTHORIZED_LIFE_PLAN_PATH=PASS
```

---

## B2 — Caller-controlled committed state

**Status: CLOSED**

`build_prepare_commit_readiness_result(...)` remains readiness-only and returns:

```python
"committed": False
```

Caller-provided commit references cannot make Project claim a commit occurred.

No Project-local Git commit implementation was introduced.

```text
B2_REMAINS_CLOSED=PASS
```

---

## M1 — Standard bootstrap extends Life Plan

**Status: CLOSED**

`build_standard_project_domain_bootstrap()` still begins with:

```python
prior = build_standard_life_plan_domain_bootstrap()
```

and reuses the prior registries.

```text
M1_REMAINS_CLOSED=PASS
```

---

## M2 — Authoritative self-development runtime chain

**Status: OPEN — MAJOR**

V3 closes a large part of M2:

```text
real temporary Git/Python repository = PASS
real ProjectAnalyzer / analyzer-issued ProjectContext = PASS
shared DeterministicPlanningProvider + DevelopmentPlan = PASS
real permission resolution = PASS
real ApprovalService request/grant/one-time consumption = PASS
real semantic Runtime mutation = PASS
real Phase 7 ValidationPipeline execution = PASS
failed validation path = PASS
successful validation path = PASS
CommitGateEvaluator = PASS
prepare_commit readiness only = PASS
Git HEAD unchanged = PASS
```

However, two mandatory integration boundaries from the frozen V2 remediation plan remain unproven.

### M2-A — mutation bypasses the canonical Project/shared operation path

The remediation plan explicitly required:

```text
Register/inject project.modify_code using the existing operation registry/delegate mechanism.

Execute through the canonical Project/shared operation path after permission + approval.
```

The V3 E2E obtains the implementation from the Project operation registry:

```python
injected_impl = dev_bootstrap.operation_registry.get_implementation(
    "project.modify_code", "1.0.0"
)
```

but then executes it directly:

```python
op_result = injected_impl.execute(op_request)
```

There is no:

```text
DefaultDomainOperationOrchestrator
DomainOperationExecutionDelegate
AgentExecutionAdapter
```

in the V3 self-development E2E.

The direct implementation itself only reads:

```python
request.parameters["runtime_action"]
```

and executes the semantic runtime. It does not verify the approval evidence.

The approval lifecycle is therefore real but disconnected from the mutation execution path:

```text
permission/gate check
→ approval created and consumed
→ direct implementation call
```

instead of:

```text
permission/gate
→ approved DomainOperationRequest
→ shared operation orchestrator
→ operation delegate
→ semantic mutation
```

This means the test still does not prove that the actual Project operation boundary enforces the approval before mutation.

### M2-B — rollback is state-marked but file restoration is manual

The plan required:

```text
forced downstream failure
→ actual shared rollback restores source bytes and working-tree state
```

The V3 E2E does:

```python
tx_manager.mark_rollback_started(trial_tx.id)
init_file.write_bytes(initial_bytes)
rolled_back_tx = tx_manager.mark_rolled_back(trial_tx.id)
```

The source restoration is performed manually by the test itself.

`TransactionManager.mark_rollback_started()` and `mark_rolled_back()` only transition transaction state. Actual operation rollback in the shared runtime is performed by the Domain Operation orchestrator through its configured rollback executor:

```text
orchestrator failure
→ rollback_executor.rollback(transaction_id, checkpoint_id)
→ TransactionManager marks rolled back
```

That path is not executed by the V3 E2E.

Therefore the test proves:

```text
TransactionManager state lifecycle + manual file restoration
```

not:

```text
shared rollback execution restores the mutation
```

### M2-C — connected AT-DP-030 repeats both shortcuts

Checkpoint 44:

```text
"controlled semantic mutation runs in temp repo"
```

directly calls:

```python
_dummy_modify_impl.execute(acc_op_req)
```

with:

```text
approval_request_id="approval:acc:1"
```

but no real approval/gate/orchestrator execution.

Checkpoint 45:

```text
"shared rollback/transaction path is present"
```

again manually corrupts and restores the file between:

```python
mark_rollback_started(...)
mark_rolled_back(...)
```

Checkpoint 46 is now a real Phase 7 validation pipeline execution and is accepted.

Thus:

```text
36 repository observation = PASS
38 shared planning = PASS
44 controlled mutation through authoritative operation path = FAIL
45 actual shared rollback execution = FAIL
46 real Phase 7 validation = PASS
```

### M2-D — runtime artifact trace binding remains incomplete

The V2 remediation plan also required Project memory/trace evidence to bind actual:

```text
ProjectContext
planning artifact
approval artifact
mutation result
rollback/successful transaction outcome
validation result
commit-readiness result
```

The V3 memory proposal includes the real validation and approval references, but the final Project trace still uses generic fixed operation/rule references and does not bind the complete real self-development artifact chain.

This is secondary to M2-A/M2-B but should be corrected in the same targeted remediation.

### Required targeted remediation

Do not redesign Project Domain.

Replace the remaining shortcuts with the existing shared path:

```text
real ApprovalService grant
→ DomainOperationRequest carrying the real approval request
→ DefaultDomainOperationOrchestrator
→ DomainPermissionGate
→ DomainOperationExecutionDelegate / AgentExecutionAdapter
→ injected project.modify_code implementation
→ semantic mutation
```

Then create a failure after the mutation through that same orchestrated transaction path and use a real rollback executor so that:

```text
rollback_executor.rollback(...)
```

performs the restoration.

Assert:

```text
without approval → no mutation
valid approval → mutation executes
forced downstream failure → DomainOperationResult reports rollback
rollback result attempted=True
rollback result succeeded=True
source bytes restored
working tree restored
transaction state rolled back/compensated
```

Update AT-DP-030 checkpoints 44/45 to carry the actual orchestrated mutation and rollback results.

Bind the real planning/approval/mutation/rollback-or-transaction/validation/readiness artifacts into memory/trace evidence as required by the frozen plan.

Keep:

```text
56 checkpoints
34 top-level attack classes
```

---

## M3 — Independent trace inventory

**Status: CLOSED**

The independent preassembly `DomainTraceReferenceInventory` and real `validate_project_trace(...)` flow remain present.

```text
M3_REMAINS_CLOSED=PASS
```

---

## M4 — Documentation/catalog consistency and audit lineage

**Status: CLOSED**

The V3 bundle contains a mechanical exact-set regression that parses:

```text
docs/reference/project-domain.md
```

and checks exact equality against all five canonical catalogs.

Independent comparison confirms:

```text
ENTITY_SET_EQUALITY=PASS
RESOURCE_SET_EQUALITY=PASS
RULE_SET_EQUALITY=PASS
OPERATION_SET_EQUALITY=PASS
WORKFLOW_SET_EQUALITY=PASS
```

All required status documents now record:

```text
Independent Audit V1 = FAIL recorded
Independent Re-audit V2 = FAIL recorded
Remediation V2 = implemented/candidate
Independent Re-audit V3 = pending
DP-030 = REQUIRES_PHASE_INSPECTION
```

```text
M4_REFERENCE_CATALOG_EXACT_MATCH=PASS
M4_CATALOG_DOC_DRIFT_TEST=PASS
M4_AUDIT_LINEAGE_ACCURATE=PASS
```

---

## M5 — Software capability activation

**Status: CLOSED**

`project_software_capability_active(...)` now ignores caller-owned primitive activation signals and returns only:

```python
is_analyzer_issued_project_context(repository_context)
```

The shared `ProjectAnalyzer` records identity-backed provenance using a weak reference to the exact issued `ProjectContext`.

The adversarial suite rejects:

```text
fake workflow prefix
canonical-looking workflow string
canonical-looking operation string
suffix collision
canonical resource ID string
bare resource kind
capability string
repository_backed=True
repo_path mapping
repository_id mapping
manually-created ProjectContext
fake typed-looking context
cloned definitions
```

and accepts a real analyzer-issued context.

```text
M5_REPOSITORY_MAPPING_REJECTED=PASS
M5_CALLER_CAPABILITY_STRING_REJECTED=PASS
M5_BARE_RESOURCE_KIND_REJECTED=PASS
M5_RESOLVED_SOFTWARE_CONTEXT_REQUIRED=PASS
```

---

# 3. AT-DP-030 disposition

Independent AST inspection confirms:

```text
AT_DP_030_CHECKPOINT_INVOCATIONS=56
AT_DP_030_UNIQUE_LABELS=56
```

The count is correct.

However checkpoints 44 and 45 still do not execute the authoritative behavior their labels claim.

Therefore:

```text
AT_DP_030=NOT_INDEPENDENTLY_ACCEPTED
```

The total must remain 56; only the bodies/artifact flow for the remaining M2 path must change.

---

# 4. Permanent adversarial gate disposition

Independent AST inspection confirms:

```text
PROJECT_CLOSURE_ATTACK_CLASSES=34
UNIQUE_ATTACK_CLASSES=34
```

B1 and M5 adversarial coverage is materially hardened and accepted.

The remaining M2 adversarial coverage only proves declarative properties such as:

```text
project.modify_code is reversible
rollback_policy_id is declared
unapproved gate evaluation is rejected
```

It does not prove:

```text
direct operation-path bypass is impossible in the integrated flow
orchestrated failure invokes the shared rollback executor
```

Because M2 remains open:

```text
PROJECT_CLOSURE_ADVERSARIAL_GATE=NOT_INDEPENDENTLY_ACCEPTED
```

Keep 34 top-level attacks and strengthen the relevant existing attack with the orchestrated mutation/rollback subcases.

---

# 5. Re-audit V3 acceptance matrix

```text
B1_RUNTIME_OWNED_AUTHORIZATION_ONLY=PASS
B1_CALLER_TYPED_DECISION_REJECTED=PASS
B1_SUCCESSFUL_AUTHORIZED_LIFE_PLAN_PATH=PASS

B2_REMAINS_CLOSED=PASS

M1_REMAINS_CLOSED=PASS

M2_REAL_PROJECT_ANALYSIS=PASS
M2_REAL_SHARED_PLANNING=PASS
M2_REAL_APPROVAL_CREATED_AND_CONSUMED=PASS
M2_MUTATION_THROUGH_PROJECT_OPERATION_PATH=FAIL
M2_REAL_TRANSACTION_STATE=PASS
M2_REAL_SHARED_ROLLBACK_EXECUTOR=FAIL
M2_REAL_PHASE7_VALIDATION=PASS
M2_FAILED_VALIDATION_NOT_READY=PASS
M2_SUCCESSFUL_VALIDATION_READY_NOT_COMMITTED=PASS
M2_PREPARE_COMMIT_HEAD_UNCHANGED=PASS
M2_COMPLETE_RUNTIME_ARTIFACT_TRACE_BINDING=FAIL

M3_REMAINS_CLOSED=PASS

M4_REFERENCE_CATALOG_EXACT_MATCH=PASS
M4_CATALOG_DOC_DRIFT_TEST=PASS
M4_AUDIT_LINEAGE_ACCURATE=PASS

M5_REPOSITORY_MAPPING_REJECTED=PASS
M5_CALLER_CAPABILITY_STRING_REJECTED=PASS
M5_BARE_RESOURCE_KIND_REJECTED=PASS
M5_RESOLVED_SOFTWARE_CONTEXT_REQUIRED=PASS

AT_DP_030_CHECKPOINTS=56
AT_DP_030=NOT_INDEPENDENTLY_ACCEPTED

PROJECT_CLOSURE_ATTACK_CLASSES=34
PROJECT_CLOSURE_ADVERSARIAL_GATE=NOT_INDEPENDENTLY_ACCEPTED
```

---

# 6. Non-counted reporting note

The implementation agent's final prose reports the workflow partition as:

```text
7 generic + 5 software workflows
```

The actual frozen candidate remains:

```text
4 generic + 8 software workflows
```

because:

```python
GENERIC_PROJECT_WORKFLOW_IDS = CANONICAL_PROJECT_WORKFLOW_IDS[:4]
SOFTWARE_PROJECT_WORKFLOW_IDS = CANONICAL_PROJECT_WORKFLOW_IDS[4:]
```

The canonical total of 12 is correct. This is a reporting-only discrepancy and is **not counted as a candidate finding**.

---

# 7. Final independent verdict

```text
PHASE10_30_INDEPENDENT_REAUDIT_V3=FAIL

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

DP_030=REQUIRES_PHASE_INSPECTION
INDEPENDENT_REAUDIT_V4=REQUIRED

PUSH=NO
MERGE=NO

NEXT=TARGETED_M2_REMEDIATION_V3
```

Phase 10.30 is now very close to closure. The remaining work is narrowly bounded to proving the authoritative `project.modify_code` operation path, real shared rollback execution, and binding those actual runtime artifacts into the connected acceptance/trace evidence.
