# CMM OS — Phase 10.41 — Independent Audit V1

## 1. Verdict

```text
PHASE=10.41
AUDIT=INDEPENDENT_AUDIT_V1

AUDITED_HEAD=331e7e1235d416c9883701edc3da576a6527112e
AUDIT_BUNDLE_SHA256=bf49ce5ef625763433a0586e5a679b90b4870804611e633013b0090673bf2e7d

BUNDLE_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
ARCHIVE_HYGIENE=PASS
SPEC_SHA256=500f753347e321061cf7df168f023dcf80db1f20c9c5612bfd0a72304b871093
PLAN_SHA256=9d93683c1487cf8216005d9bdb39a36d3464292cfd8d89f34b52f14b2cd8b5a4

BLOCKERS=2
MAJORS=3
MINORS=0

DP-041=NOT_VERIFIED
AT-DP-041=FAIL
CLOSURE_ELIGIBLE=NO
AUDIT_RESULT=FAIL
```

Phase 10.41 is **not eligible for closure**.

The implementation preserves the principal one-way Domain → Agent Runtime architecture and avoids parallel runtime ownership, but independent exact-byte review found two authority/security blockers and three major scope/acceptance defects.

No Phase 10.42 work should start. Remediation should stay narrowly inside Phase 10.41.

---

## 2. Audit target

```text
Phase 10.41 — Integration with Agent Runtime
```

Submitted archive:

```text
phase-10.41-audit-331e7e1235d416c9883701edc3da576a6527112e.tar.gz
```

Independent SHA-256:

```text
bf49ce5ef625763433a0586e5a679b90b4870804611e633013b0090673bf2e7d
```

Embedded `git archive` commit:

```text
331e7e1235d416c9883701edc3da576a6527112e
```

The embedded commit ID exactly matches the claimed implementation HEAD.

The committed design and plan hashes also match the approved artifacts:

```text
SPEC_SHA256=500f753347e321061cf7df168f023dcf80db1f20c9c5612bfd0a72304b871093
PLAN_SHA256=9d93683c1487cf8216005d9bdb39a36d3464292cfd8d89f34b52f14b2cd8b5a4
```

---

## 3. Bundle integrity and hygiene

Independent archive inspection confirmed:

```text
UNSAFE_PATHS=0
SYMLINKS_OR_HARDLINKS=0
TRACKED_BYTECODE=0
EXTRACT=PASS
COMPILEALL=PASS
```

No absolute-path entries, path traversal, symlinks/hardlinks, tracked `__pycache__`, or tracked `.pyc` files were present in the submitted archive.

Result:

```text
BUNDLE_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
ARCHIVE_HYGIENE=PASS
```

---

## 4. Positive architecture findings

Independent AST/static review of the exact audited bytes confirmed:

```text
AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
FORBIDDEN_PARALLEL_OWNER_CLASSES=0
```

The new production surface is limited to the intended Domain-owned boundary:

```text
cmm/domains/agent_runtime_integration_contracts.py
cmm/domains/agent_runtime_integration.py
```

Core Phase 10.41 classes are limited to:

```text
DomainAgentRuntimeIntegrator
DefaultDomainAgentRuntimeIntegrator
DomainAgentRuntimeDecisionCode
DomainActionBudget
DomainAgentRuntimeDecision
DomainAgentRuntimeIntegrationRequest
DomainAgentRuntimeIntegrationResult
```

No second Agent Runtime, planner, approval service, budget service, state machine, store, event bus, memory store, trace store, or cognitive engine was introduced in the Phase 10.41 production modules.

This is aligned with the approved DP-041 ownership model.

---

## 5. Positive contract and documentation findings

The implementation correctly preserves several approved invariants:

- Domain → Agent Runtime dependency direction remains one-way.
- `DomainActionBudget` is an immutable value object, not a mutable budget owner.
- Phase 9 `ActionBudgetService` remains the only mutable Action Budget owner.
- No budget increase path is referenced from Phase 10.41 production code.
- `IntegratedAgentExecutionRequest.cognitive_context` is used as the Domain cognitive projection seam.
- Domain/Agent trace linkage is reference-only in the Phase 10.41 result.
- Memory bindings are reference IDs; Phase 10.41 production code performs no direct Knowledge Store mutation.
- Phase 10.42 Planner/Workflow Engine integration remains explicitly out of scope.
- Documentation correctly says `implemented and pending independent audit`; it does not prematurely claim closure.

The current ROADMAP and requirements matrix are therefore correctly staged for pre-audit state, but they must not be advanced to closure while this V1 is FAIL.

---

## 6. Independent focused execution

A normal pytest collection from the extracted archive is not possible in the auditor environment because the repository package aggregator reaches optional dependency `libcst`, which is not installed here.

Using an auditor-only namespace bootstrap that changes only package `__init__.py` aggregation in a disposable copy — while leaving the exact Phase 10.41 production/test bytes under review unchanged — the four focused Phase 10.41 files produced:

```text
115 passed
6 failed
```

The six failures all occur while constructing the pre-existing canonical Domain reasoning-rule catalog under Python 3.13:

```text
TypeError: super(type, obj): obj (instance of DomainReasoningRuleDefinition)
```

The same class of auditor-environment incompatibility was already encountered during Phase 10.40 independent auditing. It is not classified as a Phase 10.41 product finding.

The FAIL verdict below instead rests on exact-byte static evidence plus auditor-only adversarial reproductions against the submitted production code.

---

# 7. BLOCKER-01 — Canonical DomainPermissionGate is injected but never evaluated

## Severity

```text
BLOCKER
```

## Requirement violated

The approved spec requires Domain permissions to use existing Domain permission infrastructure and preserve canonical approval/gate semantics.

The approved implementation plan Task 5 explicitly requires:

```text
Consumes DomainPermissionResolver, DomainPermissionGate, PermissionGateResult
Produces a narrowed AgentPermissionContext and approval hint only when backed by a canonical Domain gate result.
```

It also requires a real Domain `DENY` / `APPROVAL_REQUIRED` evaluation through:

```text
DomainPermissionResolver + DomainPermissionGate
```

## Production evidence

`DefaultDomainAgentRuntimeIntegrator.__init__` requires and stores `permission_gate`:

```text
_require_dependency(permission_gate, "permission_gate", "evaluate_operation")
self._permission_gate = permission_gate
```

but no Phase 10.41 production path ever calls:

```text
self._permission_gate.evaluate_operation(...)
self._permission_gate.evaluate_operation_definition(...)
```

Instead `run()` derives DENY / APPROVAL_REQUIRED directly from:

```text
self._permission_resolver.resolve(...)
```

and then manufactures the Phase 9 `requires_approval` hint from that resolver result.

This bypasses the mandatory Domain Permission Gate abstraction that Phase 10.15 documents as the immediate pre-execution authority boundary and that the Phase 10.41 plan explicitly required as the source of the gate result.

## Independent adversarial reproduction

The exact `DefaultDomainAgentRuntimeIntegrator` was constructed with a gate object whose `evaluate_operation(...)` increments a counter and raises if called.

A real approval-requiring Domain policy was used.

Observed:

```text
GATE_CALLS=0
AGENT_SERVICE_CALLS=1
BLOCKED=False
DECISIONS=[
  DOMAIN_RESOLVED,
  DOMAIN_COMPOSED,
  PROFILE_RESOLVED,
  DOMAIN_APPROVAL_REQUIRED,
  DOMAIN_OPERATION_SELECTED,
  DOMAIN_RUNTIME_COMPLETED
]
```

Therefore the Phase 10.41 boundary can delegate an approval-requiring request without ever evaluating the injected canonical Domain gate.

## Why this is a blocker

This is not a cosmetic unused dependency. `DomainPermissionGate` owns pre-dispatch re-evaluation, approval requirement binding, approval scope/fingerprint semantics, and fail-closed gate evidence. The approved design forbids replacing that authority boundary with an ad-hoc interpretation of resolver output.

The connected acceptance does not catch this because it constructs a real `DomainPermissionGate` but merely passes it into the integrator; the gate is never exercised.

---

# 8. BLOCKER-02 — `prohibited_resources` can survive permission narrowing

## Severity

```text
BLOCKER
```

## Requirement violated

The approved spec requires:

```text
Domain permissions must only restrict Agent Runtime authority.
Supporting Domains cannot widen the primary/effective permission set.
```

Task 5 requires:

```text
For prohibited capabilities/actions:
prohibition wins
```

and more generally:

```text
effective = incoming ∩ domain_allowed
```

with no widening of canonical Agent authority.

## Production evidence

`_narrow_permission_context(...)` subtracts `prohibited_resources` only inside this branch:

```python
if allowed_resource_constraints:
    effective_resources = ...
    for policy in domain_policies:
        effective_resources -= set(policy.prohibited_resources)
    data["allowed_resources"] = ...
```

If a policy has:

```text
allowed_resources=None
prohibited_resources=(...)
```

then `allowed_resource_constraints` is empty and `prohibited_resources` are never applied.

## Independent adversarial reproduction

Incoming Phase 9 permission context:

```text
allowed_resources=('doc-1', 'doc-2')
```

Canonical Domain policy:

```text
allowed_resources=None
prohibited_resources=('doc-1',)
```

Observed exact Phase 10.41 narrowing:

```text
INCOMING_RESOURCES=('doc-1', 'doc-2')
PROHIBITED_RESOURCES=('doc-1',)
NARROWED_RESOURCES=('doc-1', 'doc-2')
```

The explicitly prohibited resource remains authorized in the request sent toward Phase 9.

## Why this is a blocker

This is a concrete authority-widening/security defect at the Domain → Agent Runtime boundary. A Domain prohibition must never disappear merely because the same policy does not also define an allowlist.

The committed tests cover operation prohibition but do not cover resource-prohibition-only narrowing.

---

# 9. MAJOR-01 — Canonical Question/Iteration/External-Call budget ceilings are ignored

## Severity

```text
MAJOR
```

## Requirement violated

The approved spec requires restrictive composition for every supported canonical `BudgetResourceType`.

Task 7 explicitly instructs the implementer to inspect the current Phase 9 enum and states:

```text
maximum_iterations / maximum_questions / maximum_external_calls
may be enforced if an existing Phase 9 counter/limit is found.
```

The submitted repository's `BudgetResourceType` contains:

```text
ITERATION
QUESTION
EXTERNAL_CALL
```

## Production evidence

The Phase 10.41 mapping contains only:

```text
OPERATION -> maximum_operations
DURATION_SECONDS -> maximum_duration_seconds
COST -> maximum_cost
```

while `DomainActionBudget` also exposes:

```text
maximum_iterations
maximum_questions
maximum_external_calls
```

No other Phase 10.41 code enforces or fail-closes those dimensions.

## Independent adversarial reproduction

Canonical Phase 9 budget initialized with:

```text
QUESTION=10
ITERATION=10
EXTERNAL_CALL=10
```

Domain constraint:

```text
maximum_questions=3
maximum_iterations=4
maximum_external_calls=2
```

After Phase 10.41 execution:

```text
question LIMIT=10
iteration LIMIT=10
external_call LIMIT=10
```

All three Domain ceilings are silently ignored despite native Phase 9 support.

## Required remediation

Extend the existing mapping to the native Phase 9 enum members and use only `ActionBudgetService.decrease_budget(...)` with the same preserve-or-reduce semantics already used for operation/duration/cost.

Do not create a new Domain budget service or ledger.

---

# 10. MAJOR-02 — Reversible/irreversible Domain autonomy constraints are not integrated

## Severity

```text
MAJOR
```

## Requirement violated

The approved spec states:

```text
Equivalent fail-closed logic applies to reversible and irreversible change capabilities.
```

Task 6 Step 3 explicitly requires:

```text
Domain false can disable incoming true,
Domain true cannot enable incoming false.
```

for reversible/irreversible capability monotonicity where current contracts represent it.

## Production evidence

Canonical `DomainAutonomyLimits` includes:

```text
allow_reversible_changes
allow_irreversible_changes
```

The Phase 9 `AgentPermissionContext` includes a destructive-action authority flag:

```text
allow_destructive_actions
```

Yet `agent_runtime_integration.py` never references:

```text
allow_reversible_changes
allow_irreversible_changes
```

and the Task 6 tests never exercise those fields.

The implementation enforces only `maximum_autonomy_level` plus unrelated explicit prohibited-capability mappings.

## Why this is major

The approved autonomy boundary is only partially implemented. Domain autonomy false values are not currently guaranteed to reduce the corresponding incoming Agent capability.

Remediation should reuse existing canonical permission/autonomy fields; do not invent a second autonomy model.

---

# 11. MAJOR-03 — AT-DP-041 is not connected through all required canonical owners

## Severity

```text
MAJOR
```

## Requirement violated

The approved AT-DP-041 scenario requires the connected path:

```text
real Domain permission resolution/gate
→ DefaultDomainCognitiveIntegrator
→ DefaultDomainAgentRuntimeIntegrator
→ real AgentRuntimeIntegrationService stack
→ canonical operation registry / execution path
→ canonical approval path
→ canonical ActionBudgetService
→ Phase 9 validation/recovery owners
→ results
```

Task 8 additionally requires the connected operation proof to include:

```text
DefaultDomainAgentRuntimeIntegrator
→ AgentRuntimeIntegrationService.execute
→ AgentExecutionAdapter
→ DomainOperationExecutionDelegate
→ DefaultDomainOperationOrchestrator
```

## Acceptance evidence

The main connected acceptance `_Phase9Stack` builds:

```text
AgentExecutionAdapter(
    registry=common_registry,
    execution_delegate=DomainOperationExecutionDelegate(domain_registry),
)
```

but never constructs or invokes `DefaultDomainOperationOrchestrator`.

The counting implementation is therefore reached by the Phase 9 adapter/delegate path, not by the full Domain orchestrator permission/transaction/rollback path required by Task 8.

A separate unit-level helper in `test_domain_agent_runtime_integration.py` does construct `DefaultDomainOperationOrchestrator`, but it is not connected to `DefaultDomainAgentRuntimeIntegrator` → `AgentRuntimeIntegrationService`.

The main AT also substitutes several core Phase 9 collaborators with local test doubles:

```text
_RecordingMemoryService
_NoopRecoveryService
_NoopCheckpointService
_NoopDelegationService
```

and passes no canonical validation service into `AgentRuntimeIntegrationService`.

Most importantly, the injected real `DomainPermissionGate` is never exercised because BLOCKER-01 leaves it unused.

## Consequence

Checkpoint labels such as:

```text
12-registered-orchestration-path
```

do not prove the exact connected path frozen by the approved plan/spec.

Therefore:

```text
AT-DP-041=FAIL
```

until the connected acceptance actually traverses the required canonical owners (or their official in-memory implementations) from the Phase 10.41 boundary.

---

## 12. DP-041 assessment

The following DP-041 properties are verified in the submitted snapshot:

```text
one-way cmm.domains -> cmm.agent_runtime dependency
no reverse cmm.agent_runtime -> cmm.domains imports
Domain-owned thin integration boundary
no parallel Agent Runtime owner
no parallel budget owner
no direct Domain memory writes
reference-only trace binding
Phase 10.42 not implemented
cognitive projection uses existing Phase 9 seam
```

However DP-041 also requires the most-restrictive permission/autonomy/budget boundary and connected use of canonical owners.

Because BLOCKER-01, BLOCKER-02, MAJOR-01, MAJOR-02, and MAJOR-03 remain:

```text
DP-041=NOT_VERIFIED
```

---

## 13. Closure decision

Required closure condition:

```text
BLOCKERS=0
MAJORS=0
DP-041=VERIFIED_EXISTING
AT-DP-041=PASS
CLOSURE_ELIGIBLE=YES
```

Current independent result:

```text
BLOCKERS=2
MAJORS=3
MINORS=0
DP-041=NOT_VERIFIED
AT-DP-041=FAIL
CLOSURE_ELIGIBLE=NO
AUDIT_RESULT=FAIL
```

No closure commit is permitted from this V1.

---

## 14. Narrow remediation scope

Remediation should fix only the findings above.

### R1 — restore canonical Domain permission gate authority

- Make Phase 10.41 obtain its operative Domain gate result from the canonical `DomainPermissionGate` at the correct safe/pre-execution boundary.
- Preserve Phase 9 as the actual approval lifecycle owner.
- Do not create any new approval service.
- Add tests that fail if the injected gate is not called.
- Cover DENY, APPROVAL_REQUIRED, valid scoped approval, stale/consumed/mismatched approval, and reevaluation.

### R2 — make permission projection strictly monotonic

- Apply `prohibited_resources` even when `allowed_resources is None`.
- Add adversarial tests for resource-prohibition-only policies.
- Recheck other list/set dimensions for the same shape of bug.
- Preserve `incoming ∩ Domain` and prohibition-wins semantics.

### R3 — map all native budget dimensions already supported by Phase 9

At minimum add:

```text
BudgetResourceType.ITERATION -> maximum_iterations
BudgetResourceType.QUESTION -> maximum_questions
BudgetResourceType.EXTERNAL_CALL -> maximum_external_calls
```

using only canonical decrease semantics.

### R4 — complete autonomy monotonicity

- Integrate canonical `allow_reversible_changes` / `allow_irreversible_changes` constraints into existing Agent authority representation where the repository already defines the mapping.
- Domain false must reduce; Domain true must never elevate.
- Add explicit RED/GREEN tests.

### R5 — repair connected AT-DP-041

- Make the main acceptance actually exercise the real Domain permission gate.
- Connect specialized operation execution through the authoritative Domain operation orchestration path required by Task 8.
- Use canonical/official in-memory Phase 9 validation/recovery/checkpoint/memory owners where available; local doubles may remain only for truly external side effects.
- Keep all 20 acceptance checkpoints, but make their mechanics prove the labels.
- Preserve AT-DP-040 regression.

---

## 15. Required post-remediation gates

Before re-audit:

```text
focused Phase 10.41 tests
AT-DP-041
AT-DP-040 regression
Domain permission/gate regressions
Domain operation/orchestrator regressions
Action Budget regressions
Phase 9 Agent Runtime subsystem suite
Domain subsystem suite
full global pytest suite
Ruff check
Ruff format --check
compileall
git diff --check
AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
fragmentation gates
```

Then:

1. commit the remediation fully;
2. verify worktree clean;
3. preserve quarantine stash;
4. generate a **new** exact-HEAD `git archive` bundle;
5. calculate a new SHA-256;
6. submit it as Phase 10.41 independent re-audit V2.

Do not modify or replace the V1 bundle.

---

# 16. Final V1 result

```text
PHASE10_41_INDEPENDENT_AUDIT_V1=FAIL
AUDITED_HEAD=331e7e1235d416c9883701edc3da576a6527112e
AUDIT_BUNDLE_SHA256=bf49ce5ef625763433a0586e5a679b90b4870804611e633013b0090673bf2e7d

BLOCKERS=2
MAJORS=3
MINORS=0

DP-041=NOT_VERIFIED
AT-DP-041=FAIL
CLOSURE_ELIGIBLE=NO
NEXT=REMEDIATE_PHASE10_41_FINDINGS_ONLY
```
