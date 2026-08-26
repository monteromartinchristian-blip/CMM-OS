# CMM OS — Phase 10.29 Life Plan Domain
# Independent Re-Audit V4

**Audit date:** 2026-08-26
**Auditor:** ChatGPT — independent project auditor
**Artifact audited:** `phase-10.29-audit-v4.tar.gz`
**Independent SHA256:** `b5aef157e17cbe01ad57e6f656d8ee3fce679b73054d7fbbedd2c7eec86904bb`

---

## 1. Executive verdict

```text
PHASE10_29=NOT_CLOSED
INDEPENDENT_REAUDIT_V4=FAIL

BLOCKERS=0
MAJORS=1
MINORS=0

V3_B1_DUCK_TYPED_AUTHORIZATION_SERVICE=CLOSED
V3_M1_MEMORY_PERMISSION_OUTCOME=CLOSED
V3_M2_TRACE_EVIDENCE=OPEN
V3_m1_DOCUMENTATION_STATUS=CLOSED

AT_DP_029=NOT_ACCEPTED_FOR_FINAL_CLOSURE
DP_029=REQUIRES_PHASE_INSPECTION

REMEDIATION_REQUIRED=YES
NEXT_AUDIT=V5

PUSH=NO
MERGE=NO
NEXT_PHASE=10.29_REMEDIATION_V4
```

V4 closes three of the four V3 findings. The remaining issue is narrow and isolated to
the construction of the independent trace inventory.

The final trace is now assembled **after** the reference inventory and the memory-specific
permission/approval lifecycle is represented. However, the acceptance test and its permanent
adversarial fixture still construct a synthetic `DomainTrace(id="domain-trace:probe", ...)`
and use `probe.canonical_id` to manufacture the expected final trace ID before building the
inventory.

That is the exact local probe/fake-trace mechanism the binding V3→V4 remediation plan
explicitly prohibited.

---

# 2. Bundle integrity

Independent archive inspection:

```text
SHA256=b5aef157e17cbe01ad57e6f656d8ee3fce679b73054d7fbbedd2c7eec86904bb
ARCHIVE_MEMBERS=1786
UNSAFE_PATHS=0
FORBIDDEN_ARCHIVE_CONTENT=0
```

No embedded:

```text
.git
.venv
.env
.tokensave
.worktrees
audit-v*.tar.gz
```

were found.

Disposition:

```text
BUNDLE_INTEGRITY=PASS
```

---

# 3. Frozen canon

Independent static inspection:

```text
LIFE_PLAN_PRODUCTION_MODULES=14
LIFE_PLAN_TEST_FILES=18

ENTITIES=13
RESOURCES=12
RULES=8
OPERATIONS=10
WORKFLOWS=7
```

Exact canonical IDs remain unchanged and correct.

Manifest:

```text
manifest:life-plan:1.0.0
```

Public workflow:

```text
life_plan.cross_domain_impact_review
→ Major Decision Support
```

Reference documentation contains every canonical ID and no old
`manifest:life_plan:1.0.0` identifier.

Disposition:

```text
FROZEN_CANON=PASS
CANONICAL_REFERENCE=PASS
```

---

# 4. V3-B1 — Duck-typed authorization service

## V4 implementation

`evaluate_cross_domain_impact(...)` now imports and requires canonical contracts:

```text
DomainPermissionGate
PermissionGateResult
DomainPermissionResolver
CrossDomainPermissionDecision
```

The authorization branches use:

```python
isinstance(permission_gate, DomainPermissionGate)
isinstance(gate_res, PermissionGateResult)
```

and:

```python
isinstance(permission_resolver, DomainPermissionResolver)
isinstance(res_dec, CrossDomainPermissionDecision)
```

The old trust roots:

```python
hasattr(permission_gate, "evaluate_cross_domain")
hasattr(permission_resolver, "resolve_cross_domain")
```

are absent.

The old provenance fallback patterns are also gone. In particular, V4 no longer substitutes
the expected request actor/session into missing result fields.

Gate evidence additionally requires:

```text
allowed is True
outcome in {ALLOW, APPROVAL_CONSUMED}
actor_id exact match
session_id exact match
non-empty decision_id
```

Resolver evidence is limited to the actual canonical result contract, which carries
`request_id` but not actor/session/source/target provenance.

## Permanent attacks

The V4 adversarial gate contains dedicated tests for:

```text
fake duck-typed gate
fake duck-typed resolver
missing/incomplete provenance
request-ID mismatch
V2 real gate-issued decision replay
```

Disposition:

```text
V3_B1_DUCK_TYPED_AUTHORIZATION_SERVICE=CLOSED
V2_B1_GATE_ISSUED_ID_REPLAY=CLOSED
```

### Threat-model note

This audit does not reopen the excluded problem of an actor with arbitrary Python execution
inside the trusted process who deliberately constructs or subclasses canonical runtime
services. The frozen Phase 10.29 design explicitly excludes process-level capability security.

---

# 5. V3-M1 — Memory permission evidence

## V4 implementation

The V3 defect was:

```text
MEMORY_WRITE
→ real resolver DENY
→ manual allowed=True / PROPOSE snapshot
```

V4 removes that contradiction.

The acceptance scenario now uses:

```python
DomainPermissionRequest(
    action=PermissionCapability.OPERATION_EXECUTE,
    operation_id="life_plan.update_plan",
    purpose="propose-confirmed-life-plan-memory",
)
```

The selected operation is semantically compatible with proposal behavior:
`life_plan.update_plan` is documented in production as:

```text
"Propose plan updates without silent persistence or unconfirmed promotions."
```

The acceptance scenario requires the actual shared permission result to be:

```text
PermissionOutcome.ALLOW
```

and derives the snapshot flag directly from that result:

```python
allowed=(
    mem_perm_res.effective_permissions.decision
    is PermissionOutcome.ALLOW
)
```

The snapshot grants only:

```text
DomainMemoryCapability.PROPOSE
```

not durable direct-write authority.

## Denied direct-write regression

V4 separately resolves a real:

```text
PermissionCapability.MEMORY_WRITE
```

request.

The Life Plan policy returns `DENY`, and the resulting memory snapshot therefore has:

```text
allowed=False
```

A binding built from that denied snapshot is required to fail validation.

Memory-specific ApprovalService request/decision evidence remains distinct and proposal-bound.

Disposition:

```text
V3_M1_DENIED_MEMORY_PERMISSION_CANNOT_ALLOW_PROPOSE=PASS
V3_M1_MEMORY_PERMISSION_OUTCOME_BOUND=PASS
V2_M1_MEMORY_APPROVAL_SCOPE=PASS
V3_M1_MEMORY_PERMISSION_OUTCOME=CLOSED
```

---

# 6. V3-M2 — Trace evidence

## 6.1 Material improvements in V4

V4 does fix the two largest semantic problems from V3:

1. `DomainTraceReferenceInventory` is now created before the **final**
   `assemble_life_plan_trace(...)` call.
2. The connected reference set now contains 16 runtime references, including distinct
   memory-specific permission and approval artifacts.

The V4 AT reference set includes:

```text
DOMAIN_RESULT
PROFILE
WORKFLOW_RUN
WORKFLOW_RESULT

cross-domain PERMISSION_DECISION
cross-domain APPROVAL_REQUEST
cross-domain APPROVAL_DECISION

memory PERMISSION_DECISION
memory APPROVAL_REQUEST
memory APPROVAL_DECISION
MEMORY_PROPOSAL
MEMORY_BINDING

RESOLUTION_CONTEXT
RESOLUTION_RESULT
COMPOSITION
PRESENTATION_RESULT
```

This closes the V3 omission of the memory-specific permission/approval lifecycle.

## 6.2 Remaining defect: local synthetic probe trace

The binding V3→V4 remediation plan required:

```text
1. produce runtime artifacts
2. build runtime ledger
3. build references
4. build DomainTraceReferenceInventory
5. assemble final trace
6. validate
```

and explicitly stated:

```text
do not create a Life Plan-local fake/probe trace
```

If deterministic pre-assembly trace identity was needed, the plan required an existing
canonical pre-assembly identity API or the smallest generic shared helper.

V4 instead performs, in the AT-DP-029 acceptance scenario:

```python
probe = DomainTrace(
    id="domain-trace:probe",
    digest="0" * 64,
    ...
    domain_results=(
        DomainResultTraceReference(
            ...,
            trace_id="domain-trace:probe",
        ),
    ),
)
expected_trace_id = probe.canonical_id
```

Only then does it construct the inventory.

The permanent adversarial fixture repeats the same pattern.

So the actual V4 ordering is:

```text
runtime artifacts
→ references
→ locally reconstructed synthetic DomainTrace probe
→ derive expected_trace_id
→ reference inventory
→ final shared trace assembly
→ validation
```

rather than the required:

```text
runtime artifacts
→ shared deterministic pre-assembly trace identity
→ reference inventory
→ final shared trace assembly
→ validation
```

## 6.3 Why this remains a Major

The synthetic probe is not an authoritative runtime artifact. It duplicates the private
identity-preimage construction already present inside `DomainTraceAssembler.assemble()`.

The shared assembler itself internally uses a probe to calculate the canonical digest and ID,
but that implementation detail is not exposed as the pre-assembly identity contract required
by the acceptance scenario.

The acceptance scenario therefore reproduces shared assembly semantics manually in test code
to generate part of its own expected inventory.

This is substantially safer than V3, because the inventory is no longer derived from the
final trace object, but it still fails the explicit independent-inventory construction
contract frozen for V4.

The adversarial test named:

```text
test_closure_gate_26_trace_inventory_independent_from_final_trace
```

also uses the local synthetic probe fixture, so it cannot prove the stronger V4 invariant
that the inventory is built without a Life Plan-local reconstructed trace.

Disposition:

```text
V3_M2_MEMORY_LIFECYCLE_TRACED=PASS
V3_M2_FINAL_TRACE_POSTDATES_INVENTORY=PASS
V3_M2_NO_LOCAL_PROBE_TRACE=FAIL
V3_M2_TRACE_EVIDENCE=OPEN
SEVERITY=MAJOR
```

---

# 7. Required V5 remediation

No Life Plan architecture redesign is needed.

The remaining remediation should be one narrow generic trace change.

Recommended shape:

```text
DomainTraceAssemblyRequest
→ shared deterministic identity helper
→ {digest, trace_id}
```

For example, expose a generic shared helper from the trace assembly layer that computes the
same digest/ID that `DomainTraceAssembler.assemble()` will use.

Then:

1. `DomainTraceAssembler.assemble()` uses that helper internally;
2. AT-DP-029 calls the helper using authoritative assembly inputs;
3. AT-DP-029 builds `DomainTraceReferenceInventory` using that predicted canonical ID;
4. only then is the final trace assembled;
5. assert final trace ID/digest equal the precomputed shared identity;
6. validate against the already-existing inventory;
7. rebuild the permanent adversarial fixture identically;
8. delete both Life Plan-local `DomainTrace(id="domain-trace:probe", ...)` constructions.

Do not create a Life Plan-specific trace identity algorithm.

Suggested V5 permanent attack:

```text
assert no local DomainTrace probe is used to construct expected inventory
```

and/or test the shared helper directly against final `DomainTraceAssembler` output.

---

# 8. V3-m1 — Documentation status

V4 documentation now says:

```text
Phase 10.29 — V3 Remediation Complete; Ready for Independent Audit V4
```

The requirements matrix says:

```text
V3 remediation complete, awaiting independent audit v4
```

and keeps:

```text
DP-029 = REQUIRES_PHASE_INSPECTION
```

The old `awaiting independent audit v2` state is gone.

The old exact `129 Tests` string is gone; the reference uses non-exact lower-bound wording
instead of claiming the stale V3 count.

Canonical manifest/permission-policy/reference entries remain present.

Disposition:

```text
V3_m1_DOCUMENTATION_STATUS=CLOSED
```

---

# 9. Adversarial gate assessment

Independent AST inspection found:

```text
CLOSURE_ADVERSARIAL_TOP_LEVEL_TESTS=58
```

The permanent suite includes the required V4 security/memory attacks.

However, because its valid trace fixture itself still constructs the local probe trace,
the trace-independence portion cannot be accepted as the final V4 closure proof.

Disposition:

```text
CLOSURE_ADVERSARIAL_GATE=PARTIAL
TRACE_INDEPENDENCE_ATTACK_CLASS=NOT_ACCEPTED
```

---

# 10. Independent execution evidence

The independent audit environment completed:

```text
SHA256 verification=PASS
archive path safety=PASS
forbidden archive content=PASS
compileall cmm tests=PASS
AST parse / test inventory=PASS
canonical catalog extraction=PASS
canonical reference parity=PASS
static V3-B1 remediation inspection=PASS
static V3-M1 remediation inspection=PASS
static V3-M2 ordering inspection=FAIL (local probe remains)
```

Independent pytest collection could not run because this audit environment does not have the
project dependency:

```text
libcst
```

Collection stops while importing CMM execution modules. This is an audit-environment
limitation, not a repository failure.

The submitted V4 execution report states that the developer environment completed:

```text
AT-DP-029: 1 PASS / 45 checkpoints
Closure adversarial: 58 PASS
Life Plan suite: 159 PASS
Domain suite: 6457 PASS
Global suite: 11987 PASS
Ruff/format: PASS
Compileall: PASS
Fresh import: PASS
```

Those reported green suites are consistent with the static V4 bundle inspection, but they do
not override the remaining semantic trace finding.

---

# 11. Finding map

```text
V2_B1_GATE_ISSUED_ID_REPLAY=CLOSED
V3_B1_DUCK_TYPED_AUTHORIZATION_SERVICE=CLOSED

V2_M1_MEMORY_EVIDENCE=CLOSED
V3_M1_MEMORY_PERMISSION_OUTCOME=CLOSED

V2_M2_TRACE_EVIDENCE=OPEN
V3_M2_TRACE_EVIDENCE=OPEN

V2_M3_CANONICAL_REFERENCE=CLOSED
V3_m1_DOCUMENTATION_STATUS=CLOSED

V1_DECISION_STATUS=CLOSED
V1_SCENARIO_CONSISTENCY=CLOSED
V1_STRICT_MEMORY_BOOL=CLOSED
V1_WRAPPED_CONTRIBUTION=CLOSED
V1_WORKFLOW_NAME=CLOSED
```

---

# 12. Final status

```text
PHASE10_29=NOT_CLOSED
INDEPENDENT_REAUDIT_V4=FAIL

BLOCKERS=0
MAJORS=1
MINORS=0

V3_B1_DUCK_TYPED_AUTHORIZATION_SERVICE=CLOSED
V3_M1_MEMORY_PERMISSION_OUTCOME=CLOSED
V3_M2_TRACE_EVIDENCE=OPEN
V3_m1_DOCUMENTATION_STATUS=CLOSED

AT_DP_029=NOT_ACCEPTED_FOR_FINAL_CLOSURE
CLOSURE_ADVERSARIAL_GATE=PARTIAL
DP_029=REQUIRES_PHASE_INSPECTION

REMEDIATION_REQUIRED=YES
NEXT_AUDIT=V5

PUSH=NO
MERGE=NO
NEXT_PHASE=10.29_REMEDIATION_V4
```
