# CMM OS — Phase 10.41 — Independent Re-Audit V2

## 1. Verdict

```text
PHASE=10.41
AUDIT=INDEPENDENT_REAUDIT_V2

AUDITED_HEAD=e54836dde65ae453075fec546751a01b357e7289
AUDIT_BUNDLE_SHA256=7db6a29d540520fb871773609c42adb278d66349a25709762db01b8850377fdf

BUNDLE_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
ARCHIVE_HYGIENE=PASS

SPEC_SHA256=500f753347e321061cf7df168f023dcf80db1f20c9c5612bfd0a72304b871093
PLAN_SHA256=9d93683c1487cf8216005d9bdb39a36d3464292cfd8d89f34b52f14b2cd8b5a4
AUDIT_V1_REPORT_SHA256=ab762d8de29f7aade03b21c9861b7e3b395bebeda6508bf8b371f238771bf11a

V1_BLOCKER_01=PARTIALLY_FIXED_NOT_CLOSED
V1_BLOCKER_02=FIXED
V1_MAJOR_01=FIXED
V1_MAJOR_02=FIXED
V1_MAJOR_03=NOT_FIXED

BLOCKERS=2
MAJORS=1
MINORS=0

DP-041=NOT_VERIFIED
AT-DP-041=FAIL
CLOSURE_ELIGIBLE=NO
AUDIT_RESULT=FAIL
```

Phase 10.41 is **not eligible for closure** after V2.

The remediation materially improves the implementation and fully fixes three of the five original V1 findings. However, canonical Domain Permission Gate authority is still incomplete at the actual execution boundary, and the connected acceptance still does not exercise the authoritative Domain operation orchestrator.

No Phase 10.42 work should start.

---

## 2. Audit target

Submitted bundle:

```text
phase-10.41-audit-v2-e54836dde65ae453075fec546751a01b357e7289.tar.gz
```

Submitted checksum sidecar:

```text
phase-10.41-audit-v2-e54836dde65ae453075fec546751a01b357e7289.tar.gz.sha256
```

Independent SHA-256:

```text
7db6a29d540520fb871773609c42adb278d66349a25709762db01b8850377fdf
```

The checksum sidecar contains the same SHA-256.

Embedded `git archive` PAX commit:

```text
e54836dde65ae453075fec546751a01b357e7289
```

The embedded commit exactly matches the claimed V2 remediation HEAD.

---

## 3. Bundle integrity and hygiene

Independent archive inspection found:

```text
ARCHIVE_MEMBERS=2028
UNSAFE_PATHS=0
SYMLINKS_OR_HARDLINKS=0
TRACKED_BYTECODE=0

MIMOSA_ENTRIES=0
V2C_ENTRIES=0
AUDIT_RUNTIME_ENTRIES=0
SUPERPOWERS_RUNTIME_ENTRIES=0

EXTRACT=PASS
COMPILEALL=PASS
```

The archive contains no path traversal, absolute paths, symlink/hardlink entries, tracked `__pycache__`/`.pyc`, or local plugin runtime directories.

Result:

```text
BUNDLE_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
ARCHIVE_HYGIENE=PASS
```

---

## 4. Frozen artifact integrity

The V2 snapshot preserves the approved design, plan, and V1 audit report byte-for-byte.

Independent hashes:

```text
SPEC_SHA256=500f753347e321061cf7df168f023dcf80db1f20c9c5612bfd0a72304b871093
PLAN_SHA256=9d93683c1487cf8216005d9bdb39a36d3464292cfd8d89f34b52f14b2cd8b5a4
AUDIT_V1_REPORT_SHA256=ab762d8de29f7aade03b21c9861b7e3b395bebeda6508bf8b371f238771bf11a
```

No historical audit artifact was silently rewritten.

---

## 5. Remediation scope

Exact V1 → V2 archive comparison shows changes only in:

```text
cmm/domains/agent_runtime_integration.py
tests/domains/test_domain_agent_runtime_integration.py
tests/domains/test_domain_agent_runtime_dp041_acceptance.py
docs/audits/phase-10.41-independent-audit-v1.md
```

The V1 audit report appears only because V2 includes the dedicated audit-report commit made after the V1 implementation snapshot.

No `cmm/agent_runtime/**` production file changed between the V1 implementation archive and the V2 remediation archive.

This is appropriately narrow remediation scope.

---

## 6. Architecture gates

Independent AST scan:

```text
AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
```

No reverse `cmm.agent_runtime → cmm.domains` dependency was introduced.

The changed Phase 10.41 production module still defines only the existing integration boundary classes:

```text
DomainAgentRuntimeIntegrator
_PreparedDomainContext
DefaultDomainAgentRuntimeIntegrator
```

No second runtime, planner, approval owner, budget owner, persistent store, trace owner, memory owner, or state machine was introduced.

Result:

```text
DEPENDENCY_DIRECTION=PASS
PARALLEL_INFRASTRUCTURE=PASS
PROTECTED_AGENT_RUNTIME_FILES_MODIFIED=NO
```

---

# 7. V1 BLOCKER-02 — FIXED

## Original issue

`prohibited_resources` could disappear when a Domain policy had:

```text
allowed_resources=None
prohibited_resources=(...)
```

## V2 production change

`_narrow_permission_context(...)` now always begins from the incoming Agent resource set, optionally intersects a primary Domain allowlist, and then subtracts every Domain prohibition regardless of whether an allowlist is present.

Relevant V2 behavior:

```text
effective_resources = set(incoming)
if Domain allowlist exists:
    intersect
for every Domain policy:
    effective_resources -= prohibited_resources
```

## Independent reproduction

Input:

```text
INCOMING_RESOURCES=('doc-1', 'doc-2')
DOMAIN_ALLOWED_RESOURCES=None
DOMAIN_PROHIBITED_RESOURCES=('doc-1',)
```

Observed:

```text
EFFECTIVE_RESOURCES=('doc-2',)
```

Result:

```text
V1_BLOCKER_02=FIXED
PROHIBITION_WINS=PASS
```

---

# 8. V1 MAJOR-01 — FIXED

## Original issue

The V1 implementation omitted native Phase 9 ceilings for:

```text
ITERATION
QUESTION
EXTERNAL_CALL
```

## V2 production change

The canonical mapping now includes:

```text
BudgetResourceType.OPERATION      -> maximum_operations
BudgetResourceType.ITERATION      -> maximum_iterations
BudgetResourceType.QUESTION       -> maximum_questions
BudgetResourceType.EXTERNAL_CALL  -> maximum_external_calls
BudgetResourceType.DURATION_SECONDS -> maximum_duration_seconds
BudgetResourceType.COST           -> maximum_cost
```

The integration continues to use only:

```text
ActionBudgetService.get_budget(...)
ActionBudgetService.decrease_budget(...)
```

No increase path or second ledger was added.

## Independent reproduction

Canonical Phase 9 master budget:

```text
operation=10
iteration=10
question=10
external_call=10
duration_seconds=600
cost=20
```

Domain ceilings:

```text
operation=5
iteration=4
question=3
external_call=2
duration_seconds=300
cost=10
```

Observed effective limits:

```text
operation=5
iteration=4
question=3
external_call=2
duration_seconds=300
cost=10
```

A Domain value higher than the existing Phase 9 limit is skipped and does not increase the master budget.

Result:

```text
V1_MAJOR_01=FIXED
DOMAIN_BUDGET_MOST_RESTRICTIVE=PASS
```

---

# 9. V1 MAJOR-02 — FIXED

## Original issue

The V1 implementation ignored:

```text
DomainAutonomyLimits.allow_reversible_changes
DomainAutonomyLimits.allow_irreversible_changes
```

## V2 production change

V2 composes both flags restrictively across Domain policies.

Observed logic:

```text
all Domain reversible flags
all Domain irreversible flags
```

A false irreversible flag clears:

```text
AgentPermissionContext.allow_destructive_actions
```

and the autonomy ceiling is reduced consistently with canonical Phase 9 levels:

```text
reversible false   -> maximum level <= 1
irreversible false -> maximum level <= 2
```

## Independent reproduction

Incoming:

```text
maximum_autonomy_level=3
allow_destructive_actions=True
```

Domain:

```text
allow_reversible_changes=False
allow_irreversible_changes=False
```

Observed:

```text
effective maximum_autonomy_level=1
allow_destructive_actions=False
```

Global false + Domain true remains false.

Result:

```text
V1_MAJOR_02=FIXED
AUTONOMY_NO_WIDENING=PASS
```

---

# 10. V1 BLOCKER-01 — PARTIALLY FIXED, NOT CLOSED

V2 now invokes the injected `DomainPermissionGate`, so the original `GATE_CALLS=0` defect is partially corrected.

For a single operation, independent reproduction confirms:

```text
R1_SINGLE_GATE_CALLS=1
R1_SINGLE_SERVICE_CALLS=0
R1_SINGLE_BLOCKED=True
```

A denying gate can therefore stop the initial single-operation delegation.

However the gate is still placed at the wrong granularity and lifecycle boundary.

Two independent blocker-grade bypasses remain.

---

# 11. BLOCKER-01A — Batch execution gates only `operations[0]`

## Severity

```text
BLOCKER
```

## Production evidence

`_evaluate_gate(...)` contains:

```python
if request.agent_request.operations:
    op = request.agent_request.operations[0]
    return self._permission_gate.evaluate_operation(...)
```

It evaluates exactly one operation and immediately returns.

The canonical `IntegratedAgentExecutionRequest` supports:

```text
operations: tuple[AgentOperationRequest, ...]
```

and the Phase 9 integration service executes the tuple sequentially:

```python
for operation in operations:
    ...
    result = self._execution_adapter.execute(prepared)
```

The Domain Permission Gate contract itself states that it is the mandatory gate that must be evaluated before executing any Domain operation or workflow.

## Independent adversarial reproduction

A valid two-operation request was built.

The injected gate was stateful:

```text
first evaluation  -> ALLOW
second evaluation -> DENY
```

Observed:

```text
R1_BATCH_GATE_CALLS=1
R1_BATCH_SERVICE_CALLS=1
R1_BATCH_DELEGATED_OPS=2
R1_BATCH_BLOCKED=False
```

The complete two-operation batch was delegated after only the first operation was gated.

The second Domain operation received no Domain Permission Gate evaluation at the Phase 10.41 boundary.

## Why blocker

A request-level allow for the first operation is being treated as authority for subsequent operations.

This violates the canonical pre-operation gate contract and is security/authority relevant.

Required invariant:

```text
EVERY_DOMAIN_OPERATION_HAS_CURRENT_GATE_DECISION=YES
```

Current result:

```text
EVERY_DOMAIN_OPERATION_HAS_CURRENT_GATE_DECISION=NO
```

---

# 12. BLOCKER-01B — Approval pause/resume bypasses fresh Domain gate evaluation

## Severity

```text
BLOCKER
```

## Requirement

The frozen Phase 10.41 design requires:

```text
no valid approval -> no sensitive operation execution
valid scoped approval -> execution may proceed only if all remaining gates allow
expired/mismatched/consumed approval -> fail closed
Domain change invalidating scope -> approval cannot be reused
```

The canonical `DomainPermissionGate` documentation requires re-evaluation immediately before Domain operation execution and explicitly avoids stale cached decisions.

## Production lifecycle

Current V2 flow:

```text
DefaultDomainAgentRuntimeIntegrator
    -> DomainPermissionGate once
    -> AgentRuntimeIntegrationService.execute
        -> WAITING_APPROVAL
        -> Phase 9 approval
        -> AgentRuntimeIntegrationService.resume
            -> Phase 9 security permission check
            -> operation execution
```

`AgentRuntimeIntegrationService.resume(...)` cannot re-evaluate Domain policy because Phase 9 remains Domain-agnostic.

Phase 10.41 provides no Domain-aware resume boundary and the canonical Domain orchestrator is not in this execution path.

Therefore the Domain gate result obtained before the approval pause may become stale before dispatch.

## Independent canonical adversarial reproduction

This reproduction used:

- real `DomainPermissionRegistry`;
- real `DomainPermissionResolver`;
- real `DomainPermissionGate`;
- real Phase 9 `AgentRuntimeIntegrationService`;
- real Phase 9 `ApprovalService`;
- canonical registered Domain operation path used by the submitted AT stack.

Initial Domain policy version `1.0.0`:

```text
operation allowed
OPERATION_EXECUTE requires approval
```

Observed initial result:

```text
INITIAL_STATE=waiting_approval
IMPL_BEFORE=0
```

While the execution was paused, a newer Domain policy version `2.0.0` was registered:

```text
prohibited_operations=('university.prepare_exam',)
```

Independent direct re-evaluation of the canonical Domain gate after the policy change produced:

```text
POST_CHANGE_GATE_OUTCOME=deny
```

The already-created Phase 9 approval was then approved and the canonical Phase 9 execution was resumed.

Observed:

```text
RESUMED_STATE=completed
IMPL_AFTER=1
```

The operation executed even though the current canonical Domain Permission Gate denied it.

This independently proves that stale Domain authority can survive an approval pause/resume.

## Consequence

The V2 implementation does not yet satisfy:

```text
CURRENT_DOMAIN_AUTHORITY_AT_DISPATCH=REQUIRED
```

and:

```text
DOMAIN_CHANGE_INVALIDATES_STALE_AUTHORITY=REQUIRED
```

Result:

```text
V1_BLOCKER_01=PARTIALLY_FIXED_NOT_CLOSED
BLOCKER_01A=OPEN
BLOCKER_01B=OPEN
```

---

# 13. V1 MAJOR-03 — NOT FIXED

## Severity

```text
MAJOR
```

## Frozen requirement

Task 8 requires a connected proof equivalent to:

```text
DefaultDomainAgentRuntimeIntegrator
→ AgentRuntimeIntegrationService.execute
→ AgentExecutionAdapter
→ DomainOperationExecutionDelegate
→ DefaultDomainOperationOrchestrator
```

The frozen design requires specialized operations to execute through the registered Agent/Domain operation orchestration stack and `AT-DP-041` to use canonical components or official in-memory implementations.

The canonical Domain orchestrator is the owner that coordinates Domain permission gating, approval semantics, transaction boundaries, rollback, schema validation, and operation-level authority.

## V2 acceptance evidence

The V2 acceptance creates:

```python
orchestrator = DefaultDomainOperationOrchestrator(dom_reg, adapter)
```

but then explicitly states:

```text
Instead of invoking full orchestrator (...) we verify wiring
```

It performs only structural assertions:

```text
orchestrator is not None
isinstance(orchestrator, DefaultDomainOperationOrchestrator)
adapter._execution_delegate is not None
```

`orchestrator.execute(...)` is never invoked by the added V2 test.

The `_Phase9Stack` still wires:

```python
AgentExecutionAdapter(
    registry=common_registry,
    execution_delegate=DomainOperationExecutionDelegate(domain_registry),
)
```

directly into `AgentRuntimeIntegrationService`.

That path reaches the Domain implementation through `DomainOperationExecutionDelegate`; it does not traverse `DefaultDomainOperationOrchestrator`.

The V2 acceptance therefore still does not prove the required permission/approval/transaction/rollback Domain orchestration path.

## Remaining non-canonical acceptance collaborators

The connected `_Phase9Stack` still substitutes core collaborators with local test doubles:

```text
_RecordingMemoryService
_NoopRecoveryService
_NoopCheckpointService
_NoopDelegationService
```

and does not inject the canonical Phase 9 validation owner into the integration service.

Local probes are acceptable for observation, but they cannot replace core owners in the acceptance scenario required by the frozen spec.

## Result

```text
V1_MAJOR_03=NOT_FIXED
AT_DP_041_CONNECTED_ORCHESTRATOR=FAIL
```

---

## 14. Focused execution in auditor environment

The normal extracted repository cannot collect the focused tests because optional dependency `libcst` is unavailable in the auditor environment.

As in V1, an auditor-only disposable namespace bootstrap was used solely to bypass package-level `__init__.py` aggregation. The Phase 10.41 production and test files under review remained byte-identical.

Four focused Phase 10.41 files:

```text
115 passed
7 failed
```

All seven failures reach the same pre-existing Python 3.13 Domain reasoning-rule construction issue:

```text
TypeError:
super(type, obj): obj
(instance of DomainReasoningRuleDefinition)
is not an instance or subtype of type
```

Five failures are existing cognitive integration tests, one is the original connected AT-DP-041, and the new V2 acceptance fails only when it directly invokes AT-DP-040 at the end of its body.

This Python 3.13 issue is not classified as a new Phase 10.41 finding.

Importantly, the added V2 test reaches all of its preceding assertions before the unrelated AT-DP-040 environment failure. Those assertions still do not prove actual orchestrator traversal because they assert only construction/wiring.

---

## 15. Changed-file hygiene

Independent whitespace scan:

```text
cmm/domains/agent_runtime_integration.py                  trailing whitespace=0
tests/domains/test_domain_agent_runtime_integration.py    trailing whitespace=0
tests/domains/test_domain_agent_runtime_dp041_acceptance.py trailing whitespace=0
docs/audits/phase-10.41-independent-audit-v1.md           trailing whitespace=0
```

`compileall` passes in the extracted V2 snapshot.

Ruff is not installed in the independent auditor environment, so the agent's focused Ruff/format claim cannot be independently re-executed here. This is not the basis of the FAIL verdict.

---

## 16. Documentation state

The V2 bundle continues to describe Phase 10.41 as:

```text
implemented and pending independent audit
DP-041=IMPLEMENTED_PENDING_AUDIT
AT-DP-041=PASS
```

and does not claim:

```text
DP-041=VERIFIED_EXISTING
CLOSURE_ELIGIBLE=YES
CLOSED
```

This is correct pre-closure staging.

Because this independent V2 audit is FAIL, the local `AT-DP-041=PASS` claim remains only an implementation-side test claim and must not be promoted to independent verification.

---

## 17. DP-041 assessment

Verified V2 properties:

```text
BUNDLE_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
PARALLEL_RUNTIME_INFRASTRUCTURE=NO
V1_BLOCKER_02_PROHIBITION_WINS=FIXED
V1_MAJOR_01_BUDGET_COMPLETENESS=FIXED
V1_MAJOR_02_AUTONOMY_FLAGS=FIXED
SINGLE_OPERATION_GATE_DENY=WORKING
```

Unverified/failed required properties:

```text
EVERY_OPERATION_CURRENT_DOMAIN_GATE=FAIL
DOMAIN_GATE_RECHECK_AFTER_APPROVAL_PAUSE=FAIL
STALE_DOMAIN_AUTHORITY_INVALIDATION_AT_DISPATCH=FAIL
CONNECTED_DEFAULT_DOMAIN_OPERATION_ORCHESTRATOR=FAIL
AT-DP-041=FAIL
```

Therefore:

```text
DP-041=NOT_VERIFIED
```

---

## 18. V2 closure decision

Required closure condition:

```text
BLOCKERS=0
MAJORS=0
DP-041=VERIFIED_EXISTING
AT-DP-041=PASS
CLOSURE_ELIGIBLE=YES
```

Current V2 result:

```text
BLOCKERS=2
MAJORS=1
MINORS=0
DP-041=NOT_VERIFIED
AT-DP-041=FAIL
CLOSURE_ELIGIBLE=NO
AUDIT_RESULT=FAIL
```

No Phase 10.41 closure commit is permitted from V2.

No Phase 10.42 implementation should start.

---

## 19. Narrow remediation V2 → V3

The remaining work should stay narrow.

### R6 — Move/guarantee Domain gate authority at the actual per-operation dispatch boundary

The final architecture must guarantee:

```text
for every Domain operation:
    current Domain permission/gate decision immediately before dispatch
```

Do not treat `operations[0]` as authority for a batch.

A two-operation request must produce two current gate evaluations, or the canonical execution path must independently gate each Domain operation.

Add an adversarial acceptance where:
- operation 1 is allowed;
- operation 2 is denied at its own gate;
- operation 2 implementation call count remains zero.

### R7 — Re-evaluate Domain authority after approval pause before actual execution

A Phase 9 approval may satisfy the approval lifecycle, but it must not bypass a newer Domain denial.

Add a connected test:

```text
Domain policy = approval required
→ Phase 9 pauses
→ Domain policy changes to DENY
→ Phase 9 approval is granted
→ attempted resume
→ Domain gate re-evaluates current policy
→ execution remains blocked
→ implementation calls = 0
```

Do not make `cmm.agent_runtime` import `cmm.domains`.

Prefer satisfying this through the already-canonical Domain operation orchestration boundary rather than adding a second resume/runtime subsystem.

### R8 — Actually connect `DefaultDomainOperationOrchestrator`

The connected acceptance must call the orchestrator behaviorally, not assert that an object exists.

It must demonstrate the real operation execution path including:
- Domain permission gate;
- canonical approval binding;
- transaction/checkpoint behavior where applicable;
- rollback behavior where applicable;
- `AgentExecutionAdapter`;
- `DomainOperationExecutionDelegate`;
- actual final implementation call.

Use canonical/official in-memory Phase 9 collaborators where they exist.

### R9 — Repair AT-DP-041 labels so they prove mechanics

Remove structural assertions masquerading as connected proof.

A checkpoint named for orchestration must be backed by observed orchestrator execution.

A stale-authority checkpoint must cover an authority change during pause/resume, not only a brand-new top-level integration call.

---

## 20. Required V3 gates

Before V3:

```text
focused Phase 10.41 tests
new batch-gate adversarial test
new approval-resume stale-authority test
actual orchestrator connected test
AT-DP-041
AT-DP-040 regression
DomainPermissionGate regressions
Domain operation/orchestrator regressions
ActionBudget regressions
Phase 9 Agent Runtime relevant suite
Domain subsystem suite
global pytest suite
changed-file Ruff
changed-file format
compileall
git diff --check
AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
anti-fragmentation gates
```

Then:
1. commit remediation fully;
2. worktree clean;
3. quarantine stash preserved;
4. generate a new exact-HEAD V3 `git archive`;
5. calculate a new SHA-256;
6. submit it for independent V3 re-audit.

Do not modify or replace the V1 or V2 bundles.

---

# 21. Final V2 result

```text
PHASE10_41_INDEPENDENT_REAUDIT_V2=FAIL

AUDITED_HEAD=e54836dde65ae453075fec546751a01b357e7289
AUDIT_BUNDLE_SHA256=7db6a29d540520fb871773609c42adb278d66349a25709762db01b8850377fdf

V1_BLOCKER_01=PARTIALLY_FIXED_NOT_CLOSED
V1_BLOCKER_02=FIXED
V1_MAJOR_01=FIXED
V1_MAJOR_02=FIXED
V1_MAJOR_03=NOT_FIXED

BLOCKERS=2
MAJORS=1
MINORS=0

DP-041=NOT_VERIFIED
AT-DP-041=FAIL
CLOSURE_ELIGIBLE=NO

NEXT=REMEDIATE_PHASE10_41_V2_FINDINGS_ONLY
```
