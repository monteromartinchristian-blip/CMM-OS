# Phase 10.29 — Life Plan Domain — Independent Re-Audit V2

**Date:** 2026-08-26
**Auditor:** ChatGPT — independent CMM OS closure auditor
**Candidate bundle:** `phase-10.29-audit-v2.tar.gz`
**Candidate HEAD:** `6ef944e8347bc37a9212c7862d7917ad12fef3d2`
**Bundle SHA-256:** `ede85981040d4473b072c28fe3857c0c1e049002b8b7bd2bc3776ceb4c923639`

---

## 1. Executive verdict

# FAIL — one blocker and three majors remain

Phase 10.29 has improved substantially since V1. Five V1 findings are independently closed, the frozen production canon is intact, the package boundary remains correct, and no architectural redesign is required.

However, the V2 candidate still contains a reproducible cross-domain authorization bypass and still does not satisfy the runtime-evidence requirements frozen for AT-DP-029. The permanent adversarial gate does not cover the surviving authorization replay, and the canonical Life Plan reference document contradicts the actual frozen catalog.

```text
PHASE10_29=NOT_CLOSED
INDEPENDENT_REAUDIT_V2=FAIL

BLOCKERS=1
MAJORS=3
MINORS=0

DP_029=REQUIRES_PHASE_INSPECTION
AT_DP_029=NOT_ACCEPTED_FOR_FINAL_CLOSURE

REMEDIATION_REQUIRED=YES
NEXT_AUDIT=V3
```

No Phase 10.30 work should begin yet.

---

## 2. Bundle integrity and frozen canon

The exact uploaded bundle was hashed and extracted independently.

```text
SHA256=ede85981040d4473b072c28fe3857c0c1e049002b8b7bd2bc3776ceb4c923639
FILES=1675
LIFE_PLAN_MODULES=14
LIFE_PLAN_TEST_FILES=18
```

No forbidden archive content was present:

```text
.git
.venv
.env
.tokensave
.worktrees
nested audit tarballs
```

The exact production package remains the frozen 14-module Domain Pack.

The bundle's `catalog.py` was independently parsed and compared against the frozen design.

```text
ENTITIES=13 PASS
RESOURCES=12 PASS
RULES=8 PASS
OPERATIONS=10 PASS
WORKFLOWS=7 PASS
EXACT_FROZEN_CANON_STATIC=PASS
```

`life_plan.cross_domain_impact_review` remains inside the seven-workflow canon.

The generic shared `operation_contracts.py` normalization accepted in V1 is unchanged in V2.

---

## 3. Independent execution limits

The exact Life Plan implementation and tests compile successfully in the audit environment:

```text
COMPILEALL_LIFE_PLAN=PASS
AST_PARSE_FILES=32
AST_PARSE=PASS
```

Full pytest collection cannot run in the independent container because the container lacks repository dependency `libcst`.

The collection failure occurs before Life Plan tests execute:

```text
ModuleNotFoundError: No module named 'libcst'
```

This remains an auditor-environment limitation rather than a candidate defect.

The implementation agent reports a successful repository run including:

```text
Life Plan focused: 129 PASS
Closure adversarial: 33 PASS
AT-DP-029: 45 checkpoints PASS
Domain suite: 6427 PASS
Global suite: 11957 PASS
Ruff / format / compile / fresh import: PASS
```

Those are implementation-side results. The closure verdict below is based on independent source inspection and direct execution of isolated exact candidate functions where possible.

---

## 4. V1 findings independently closed in V2

### V1-B1 — CLOSED

The V2 `evaluate_decision_status(...)` now enforces the canonical vocabulary:

```text
idea
preference
goal
scenario
decision
commitment
```

Exact candidate logic was executed independently.

The following all fail closed:

```text
inference -> decision
inference -> commitment
nonsense -> decision
idea -> confirmed_fact
scenario -> decision without confirmation
scenario -> commitment without confirmation
```

Independent result:

```text
B1_DIRECT_REPRODUCTIONS=CLOSED
```

### V1-B3 — CLOSED

V2 now uses a single `_extract_verified_authorized_contribution(...)` path for both direct and wrapped artifacts.

A manually constructed artifact has:

```text
_is_verified=False
```

and both forms are rejected:

```text
direct -> None
{"authorized_artifact": forged} -> None
```

Independent result:

```text
B3_DIRECT_AND_WRAPPED_REPRODUCTIONS=CLOSED
```

### V1-M1 — CLOSED

Structured scenario consistency now computes:

```text
structured mutually-exclusive assumptions -> inconsistent
milestone prerequisite ordering conflict -> inconsistent
resource infeasibility -> inconsistent
unknown assumptions -> coherent + uncertainty preserved
```

Independent result:

```text
M1_STRUCTURED_REPRODUCTIONS=CLOSED
```

### V1-M2 — CLOSED

Strict memory confirmation now rejects:

```text
"false"
"true"
0
1
[]
{}
None
```

as privileged confirmation evidence.

Independent result:

```text
M2_DIRECT_REPRODUCTIONS=CLOSED
```

### V1-m1 — CLOSED

The exact workflow mapping is now:

```text
life_plan.cross_domain_impact_review -> Major Decision Support
```

---

## 5. BLOCKER V2-B1 — Gate-issued decision-ID replay still authorizes a forged `PermissionGateResult`

This is the surviving form of V1-B2.

### Frozen trust contract

The design requires:

```text
runtime/service-owned evidence
caller object != authorization
raw ID != authorization
canonical dataclass type != authorization
```

### V2 implementation

`evaluate_cross_domain_impact(...)` now checks whether a supplied `PermissionGateResult.decision_id` belongs to:

```python
permission_gate._issued_decision_ids
```

and checks several visible fields.

This is stronger than V1 but still insufficient.

`DomainPermissionGate` stores only:

```python
self._issued_decision_ids: set[str]
```

It does not expose a gate-owned mapping from each decision ID to the exact result/request that produced it.

Therefore an ID proves only:

```text
this gate emitted this string at some point
```

not:

```text
this exact result belongs to this exact request
```

### Critical `APPROVAL_CONSUMED` branch

For a supplied `PermissionGateResult` with outcome `APPROVAL_CONSUMED`, Life Plan checks caller-supplied `approval_evidence`.

It then tries:

```python
permission_gate._approval_service.get_request(...)
```

but the actual shared `ApprovalService` does not expose `get_request`; it exposes its repository through `.repository`.

Because `hasattr(app_svc, "get_request")` is false, the V2 code reaches a fallback branch that sets:

```text
auth_verified=True
```

without canonical re-validation/consumption of the approval for the current request.

### Independent reproduction

The exact V2 `evaluate_cross_domain_impact(...)` body was executed with the exact candidate `PermissionGateResult` semantics and an actual-`ApprovalService`-shaped gate object.

An attacker reused a decision ID already present in the gate's issued-ID set, but fabricated a new `PermissionGateResult`:

```text
decision_id = ID previously emitted for unrelated decision
outcome = APPROVAL_CONSUMED
actor/session = current actor/session
metadata source/target = plausible current values
approval_evidence.granted = True
approval request = unrelated/fake scope
```

The real gate evaluation method was configured to fail if called.

Observed result:

```text
EXACT_PERMISSION_GATE_RESULT=PermissionGateResult
B2_APPLIED=True
B2_AUTH_VERIFIED=True
B2_REAL_GATE_CALLED=False
B2_V2_BYPASS=REPRODUCED
```

Life Plan then creates an internally verified `AuthorizedCrossDomainContribution` from the forged decision.

### Required remediation

Do not treat a supplied `PermissionGateResult` as authoritative based on membership in `_issued_decision_ids`.

The safest Life Plan path is:

```text
CrossDomainPermissionRequest
+ canonical approval request ID when required
-> permission_gate.evaluate_cross_domain(...)
-> fresh gate-owned result
-> Life Plan contribution
```

A suitable implementation may add an `approval_request_id` keyword and always ask the shared gate to evaluate the exact request.

Alternative acceptable path: expose/use a true gate-owned decision registry bound to the complete request identity/digest. A bare issued-ID set is not enough.

Required permanent attack:

```text
reuse a real gate-issued ID from an unrelated/denied decision
+ forge APPROVAL_CONSUMED result
+ plausible current actor/session/source/target
-> MUST reject
```

Disposition: **BLOCKER — OPEN**.

---

## 6. MAJOR V2-M1 — AT-DP-029 still reuses unrelated cross-domain evidence as memory authorization/approval

This is the surviving core of V1-M3.

AT-DP-029 obtains a real cross-domain gate decision for:

```text
Health -> Life Plan
```

Then manually constructs:

```python
DomainMemoryPermissionDecisionSnapshot(
    decision_id=consumed_gate.decision_id,
    allowed=consumed_gate.allowed,
    capabilities=(DomainMemoryCapability.PROPOSE,),
    source_domain_id=domain:life-plan,
    target_domain_id=domain:life-plan,
)
```

This changes the semantics of the same decision ID from:

```text
cross-domain Health access
```

to:

```text
Life Plan memory PROPOSE permission
```

No runtime service produced that memory decision.

The same AT also manually binds the cross-domain approval to the memory proposal:

```python
DomainMemoryApprovalRequestSnapshot(
    request_id=cross_approval.id,
    proposal_id=mem_proposal_id,
)
```

and:

```python
DomainMemoryApprovalDecisionSnapshot(
    decision_id=cross_decision.id,
    request_id=cross_approval.id,
    approved=True,
)
```

The original approval was for cross-domain permission, not for the memory proposal.

### Required remediation

Memory evidence must be scoped to the memory lifecycle.

At minimum:

- do not reuse the Health cross-domain permission decision ID as a memory permission ID;
- do not reuse the cross-domain approval as memory-proposal confirmation;
- create/derive memory-specific permission evidence according to the shared memory contract;
- create a real ApprovalService request specifically scoped to the memory proposal when confirmation is required;
- snapshot the actual memory-specific approval request/decision;
- if part of the memory layer is intentionally reference-inventory-only, describe it honestly instead of claiming it is runtime-owned.

Disposition: **MAJOR — OPEN**.

---

## 7. MAJOR V2-M2 — AT-DP-029 trace remains synthetic and omits the runtime lifecycle it claims to prove

AT-DP-029 still constructs:

```text
domain-trace:probe
```

manually to calculate the expected trace ID.

Its independent inventory remains centered on:

```text
DOMAIN_RESULT
PROFILE
RESOLUTION_CONTEXT
RESOLUTION_RESULT
COMPOSITION
```

The final trace does not carry the connected runtime evidence already produced during the same acceptance lifecycle for:

```text
workflow execution
permission decision
approval request
approval decision
memory proposal
memory binding
presentation result
```

although `DomainTraceReferenceKind` explicitly supports:

```text
OPERATION_RESULT
WORKFLOW_RUN
WORKFLOW_RESULT
PERMISSION_DECISION
APPROVAL_REQUEST
APPROVAL_DECISION
MEMORY_PROPOSAL
MEMORY_BINDING
PRESENTATION_RESULT
```

The rebuilt adversarial tests named for trace independence/tampering use the same reduced `domain-trace:probe` model.

They prove mutation detection for that small synthetic reference set, but they do not prove that actual connected runtime artifacts are inventoried and carried into final trace evidence.

### Required remediation

Rebuild final AT trace evidence around actual objects produced during the connected lifecycle:

```text
actual runtime artifacts
-> independently constructed reference inventory
-> final trace assembly
-> validation
```

Where real runtime artifacts exist, trace them.

Do not omit permission/approval/workflow/memory evidence while claiming the trace demonstrates that lifecycle.

Disposition: **MAJOR — OPEN**.

Until corrected:

```text
AT_DP_029=NOT_ACCEPTED_FOR_FINAL_CLOSURE
```

---

## 8. MAJOR V2-M3 — Canonical Life Plan reference documentation contradicts the frozen implementation canon

Production `catalog.py` is correct.

`docs/reference/life-plan-domain.md` is not.

### Wrong manifest ID

Document:

```text
manifest:life_plan:1.0.0
```

Frozen design and code:

```text
manifest:life-plan:1.0.0
```

### Wrong entity inventory

Document-only IDs:

```text
life_plan.entity.resource_constraint
life_plan.entity.life_domain_state
life_plan.entity.commitment
life_plan.entity.alternative_route
life_plan.entity.plan_drift
life_plan.entity.financial_plan
life_plan.entity.review_record
```

Required catalog IDs omitted by the document:

```text
life_plan.entity.constraint
life_plan.entity.risk
life_plan.entity.financial_resource
life_plan.entity.career_path
life_plan.entity.education_path
life_plan.entity.housing_goal
life_plan.entity.family_goal
```

### Wrong resource inventory

Document-only IDs:

```text
life_plan.resource.timeline
life_plan.resource.scenario
life_plan.resource.note
life_plan.resource.review_record
```

Required catalog IDs omitted by the document:

```text
life_plan.resource.academic_plan
life_plan.resource.opposition_plan
life_plan.resource.family_plan
life_plan.resource.housing_plan
```

Counts remain 13/12, which allowed count-only checks to miss the drift.

`docs/reference/life-plan-domain.md` is linked as the implementation reference from DP-029. Leaving it wrong would seed incorrect identifiers into future phases.

### Required remediation

Regenerate the identity/inventory section directly from the frozen design/catalog and add an exact-ID documentation check rather than count-only validation.

Disposition: **MAJOR — OPEN**.

---

## 9. V1-M4 adversarial-gate disposition

The V2 gate is substantially improved:

```text
33 top-level tests
30 explicitly numbered attack classes
```

However it is not yet accepted as complete because:

1. its forged `PermissionGateResult` test uses a non-issued/obviously invalid decision ID and does not exercise the surviving replay of a real gate-issued ID;
2. its trace-independence/tamper tests use the same reduced synthetic probe pattern described in V2-M2.

Therefore V1-M4 is **PARTIAL**, not closed.

---

## 10. Areas accepted in V2

Preserve these without redesign:

- exact 14-module package boundary;
- exact `13/12/8/10/7` production catalog;
- `LifePlanProfile`;
- decision-state canonical vocabulary;
- closed-decision protection;
- structured scenario consistency;
- finite numeric resource handling;
- alternative-route non-abandonment;
- direct and wrapped unverified-contribution rejection;
- strict memory-confirmation typing;
- purpose-minimization whitelist and dossier rejection;
- `Major Decision Support` public name;
- atomic integration/rollback architecture;
- General fallback;
- no Life Plan-specific parallel engine/repository/planner;
- accepted generic `operation_contracts.py` normalization;
- audit stop boundary;
- `DP_029=REQUIRES_PHASE_INSPECTION`.

---

## 11. Required V3 remediation — minimal scope

The next round should be narrow:

1. **Fix authorization trust root**
   - eliminate authority of caller-supplied `PermissionGateResult`;
   - re-evaluate the exact request through the shared gate;
   - add issued-ID replay attack.

2. **Fix AT-DP-029 memory evidence**
   - use memory-specific permission/approval evidence;
   - stop relabeling cross-domain evidence.

3. **Fix AT-DP-029 trace evidence**
   - carry actual workflow/permission/approval/memory/presentation references;
   - strengthen trace adversarial tests.

4. **Fix canonical reference documentation**
   - exact manifest, entity, resource, rule, operation and workflow IDs.

5. **Run full verification**
   - focused;
   - adversarial;
   - AT-DP-029;
   - domains;
   - global;
   - Ruff/format;
   - compileall;
   - fresh import;
   - diff checks.

6. **Create**
   - `phase-10.29-audit-v3.tar.gz`
   - from exact committed HEAD.

---

## 12. Final V2 status

```text
PHASE10_29=NOT_CLOSED
INDEPENDENT_REAUDIT_V2=FAIL

V1_B1_DECISION_STATUS=CLOSED
V1_B2_PERMISSION_TRUST=OPEN
V1_B3_WRAPPED_CONTRIBUTION=CLOSED
V1_M1_SCENARIO_CONSISTENCY=CLOSED
V1_M2_MEMORY_BOOL=CLOSED
V1_M3_AT_RUNTIME_EVIDENCE=OPEN
V1_M4_ADVERSARIAL_GATE=PARTIAL
V1_m1_WORKFLOW_NAME=CLOSED

V2_BLOCKERS=1
V2_MAJORS=3
V2_MINORS=0

DP_029=REQUIRES_PHASE_INSPECTION
AT_DP_029=NOT_ACCEPTED_FOR_FINAL_CLOSURE

NEXT=PHASE10_29_REMEDIATION_V2
NEXT_AUDIT=V3
PUSH=NO
MERGE=NO
```

No repository files were modified by this independent V2 audit.
