# Phase 10.28 — Sport Domain — Independent Re-Audit V3

Date: 2026-08-25
Auditor: ChatGPT — independent CMM OS closure auditor
Candidate bundle: `phase-10.28-audit-v4.tar.gz`

## Bundle identity

```text
AUDIT_HEAD=ed8d29bf3f8f6c1a3ddd23f5fd44e06bf7813036
SHA256=ffa84ddb5e3869daa817409893cf238b3defe875fdf8a88477987bef0c87c586
SIZE=3,595,761 bytes
MEMBERS=1738
SAFE_EXTRACT=PASS
SANITIZATION=PASS
```

No `.env`, `.git`, `.venv`, `.worktrees`, `.tokensave`, `tmp/`, or audit TAR.GZ payloads were present.

## Structural verification

```text
SPORT_PACKAGE_MODULES=14_EXACT
ENTITIES=11_EXACT
RESOURCES=9_EXACT
RULES=6_EXACT
OPERATIONS=8_EXACT
WORKFLOWS=5_EXACT
RETURN_TO_TRAINING_WORKFLOW=PASS
SPORT_TEST_FILES=17
COMPILEALL_SPORT_AND_TESTS=PASS
PRIVATE_HEALTH_IMPLEMENTATION_IMPORTS=0
PARALLEL_SPORT_INFRASTRUCTURE=0
```

## Candidate-side test evidence

The remediation agent reported:

```text
SPORT_TESTS=76_PASS
DOMAIN_TESTS=6264_PASS
GLOBAL_TESTS=11794_PASS
SPORT_RUFF=PASS
SPORT_FORMAT=PASS
COMPILE=PASS
```

These are candidate-side results. The independent audit container still cannot collect the full pytest suite because `libcst` is unavailable in the auditor environment. This remains an auditor-environment limitation and is not counted as a candidate defect.

# Verdict

## FAIL — Phase 10.28 remains open

```text
PHASE10_28=NOT_CLOSED
INDEPENDENT_REAUDIT_V3=FAIL
DP_028=NOT_VERIFIED
AT_DP_028=NOT_ACCEPTED_FOR_FINAL_CLOSURE

BLOCKERS=1
MAJORS=3
MINORS=1

PUSH=NO
MERGE=NO
NEXT=REMEDIATE_AUDIT_V3
```

The V2 remediation genuinely closes the `max_intensity` semantics finding, but the authorization/evidence chain remains bypassable.

# Re-Audit V2 findings status

| Finding | V3 result |
| --- | --- |
| B1 — Health authorization non-forgeable end-to-end | **OPEN — BLOCKER** |
| M3 — preserve `max_intensity` / explicit limits | **CLOSED** |
| M4 — scoped calendar approval anti-forgery | **OPEN — MAJOR** |
| M5-A — Return-to-Training through shared workflow runtime | **OPEN — MAJOR** |
| M5-B — independent runtime trace evidence | **OPEN — MAJOR** |

# Blocking finding

## B1 — Health authorization is still forgeable in three independent ways

### A. `is_authorized=True` still creates trusted evidence

`cmm/domains/sport/rules.py:362-455`

The public function still contains:

```python
elif is_authorized:
    auth_verified = True
```

A caller can provide:

```python
{
    "status": "active",
    "authorization_reference": "fake-auth",
    "load_limits": {"reduction_pct": 50},
}
```

with:

```python
is_authorized=True
```

and receive:

```text
applied=True
authorization_verified=True
```

The resulting envelope is accepted by `adjust_training_load_result()` and changes load from `100` to `50`.

### B. A fabricated object with `allowed=True` is accepted as a permission decision

`evaluate_health_constraint()` uses duck typing:

```python
if getattr(permission_decision, "allowed", False) is True:
```

Independent probe using:

```python
class FakePermission:
    allowed = True
    decision_id = "fake-decision"
```

produced a verified constraint and changed load from `100` to `70`.

No canonical `PermissionGateResult` / `CrossDomainPermissionDecision` relationship, domain, action, actor, session, or issued decision is verified.

### C. A caller can forge the vetted envelope directly

`cmm/domains/sport/operations.py` trusts any mapping shaped as:

```python
{
    "applied": True,
    "authorization_verified": True,
    "constraint": {...}
}
```

Independent probe:

```python
{
    "applied": True,
    "authorization_verified": True,
    "constraint": {
        "status": "active",
        "authorization_reference": "fabricated",
        "load_limits": {"reduction_pct": 60},
    },
}
```

was accepted and changed load from `100` to `40`.

The same forged envelope can block a generated workout.

### D. Temporal currentness is also caller-controlled

A constraint carrying:

```text
effective_until=2020-01-01T00:00:00+00:00
```

was still accepted when the caller supplied:

```python
is_current=True
```

The production boundary does not validate the constraint's own effective period.

### Why this remains a blocker

The V2 remediation rule was explicit:

```text
caller-controlled token
→ must never become trusted authorization evidence
```

The candidate still exposes multiple production paths where exactly that happens.

### Required remediation

- Remove `is_authorized` as an authorization source from production `evaluate_health_constraint()`.
- Require concrete canonical permission-result types and validate their expected action/domain/scope, rather than duck-typing `allowed`.
- Do not represent the vetted Health artifact as a caller-forgeable plain mapping with only Boolean metadata. Use a typed immutable artifact constructed from canonical gate evidence, or require the gate result to be revalidated at every consuming boundary.
- Operations and Return-to-Training must reject manually fabricated envelopes.
- Validate temporal currentness from canonical timestamps/effective period, not a free caller Boolean.
- Add adversarial regressions for all four bypasses above.

# Major findings

## M4 — Calendar approval remains forgeable despite string-ID tests

`cmm/domains/sport/operations.py:371-461`

The V2 remediation correctly rejects bare `has_approval=True` and bare request/decision strings.

However, two other caller-forgeable paths remain.

### A. Arbitrary `approval_evidence` object

The function accepts any object satisfying:

```python
granted is True
action in allowed actions
```

With a caller-supplied `approval_decision_id`, an arbitrary object:

```python
class FakeEvidence:
    granted = True
    action = "sport.schedule_sessions"
    request_id = "fake-req"
```

produced:

```text
status=ready_for_external_execution
approval_granted=True
approval_request_id=fake-req
approval_decision_id=fake-dec
```

### B. Arbitrary request/decision objects

The branch described as:

```text
Validated via matching ApprovalDecision and ApprovalRequest objects
```

does not type-check or consult `ApprovalService`.

Independent fabricated objects with:

```text
request.id=req-x
request.operation_id=sport.schedule_sessions
decision.request_id=req-x
decision.id=dec-x
decision.decision=approve
```

also produced `ready_for_external_execution`.

### Required remediation

There must be one canonical trust path:
- verify through `ApprovalService` / repository or an already validated shared gate result;
- reject arbitrary duck-typed objects;
- remove the unverified object-only fallback;
- verify request/decision relation, approval status, operation scope, and any actor/session/expiry constraints represented by the shared contract.

---

## M5-A — Shared workflow runtime is invoked, but the final recommendation is still disconnected

`tests/domains/test_sport_domain_dp028_acceptance.py:499-575`

Checkpoint 30 now does invoke the canonical workflow with `DomainWorkflowExecutor`. This is a real improvement.

But the actual Sport recommendation used for checkpoints 31–33 is then produced separately by:

```python
wf_res = execute_return_to_training_workflow(...)
```

The `workflow_run` output is not consumed to produce that recommendation.

Therefore the claimed connected lifecycle is still:

```text
shared workflow run
    +
separate direct helper run
```

rather than:

```text
shared workflow run
→ Sport recommendation
```

The custom `wf_op_adapter` also injects the Health constraint directly into `adjust_training_load_result()` rather than demonstrating a canonical permission artifact flowing through workflow execution.

### Required remediation

- Make the shared workflow execution produce/carry the authoritative Return-to-Training outcome.
- Checkpoints 31–33 must consume that workflow run/result, not rerun a separate helper.
- The workflow operation adapter must consume only the canonical non-forgeable Health artifact fixed under B1.
- Preserve and trace the actual workflow outcome/result reference.

---

## M5-B — Trace reference inventory is improved but still partly circular / synthetic

`tests/domains/test_sport_domain_dp028_acceptance.py:811-940`

The candidate no longer derives `references=` from `trace.all_references()`. That part is fixed.

However:

```python
runtime_domain_result_id = id_factory()
```

creates a synthetic ID without an actual runtime domain-result object.

Then:

```python
inventory = DomainTraceReferenceInventory(
    ...
    domain_results=trace.domain_results,
)
```

derives the inventory's domain-result evidence directly from the trace being validated.

This means the `DOMAIN_RESULT` pairing is still self-certified.

The acceptance's negative fabricated-reference test proves unexpected contribution references are detected, but it does not prove that baseline domain-result evidence came from a real upstream result object.

### Required remediation

- Create/use an actual runtime Domain Result object or canonical domain-result artifact.
- Build `DomainTraceReferenceInventory.domain_results` from that upstream object before trace assembly.
- Do not populate any inventory field from `trace`.
- Remove fallback/synthetic evidence such as `or "dec-001"` from baseline proof paths even if current assertions make the fallback unreachable.
- Keep fabricated and post-construction tampering negatives.

# Minor finding

## m1 — Candidate documentation overstates the remediation result

`docs/roadmap/phase-10-domain-intelligence.md:4499-4505`

The roadmap currently records B1, M4 and M5 as `CLOSED`, including statements that caller-passed authorization evidence is rejected and trace inventory is independently constructed.

The V3 adversarial probes demonstrate those statements are not yet true.

This does not alter runtime behavior, so it is classified as MINOR, but the next remediation must return those rows to an audit-pending/remediated-candidate state until the next independent audit passes.

# V3 independent adversarial replay

```text
HEALTH_FIELD_MINIMIZATION_GATE=PASS
TREND_TEMPORAL_EVIDENCE_GATE=PASS
OVERLOAD_FINITE_EVIDENCE_GATE=PASS
CONSTRAINT_VALUE_SEMANTICS_GATE=PASS
SCOPED_CALENDAR_APPROVAL_GATE=FAIL
MEMORY_VALIDATION_FAIL_CLOSED_GATE=PASS
CONNECTED_CROSS_DOMAIN_ACCEPTANCE_GATE=FAIL
RUNTIME_TRACE_EVIDENCE_GATE=FAIL
PENDING_AUDIT_STATUS_GATE=PASS

AUDIT_PROBE_TOTAL=9
AUDIT_PROBE_PASS=6
AUDIT_PROBE_FAIL=3
```

Additional V2 anti-forgery/runtime gates:

```text
HEALTH_AUTHORIZATION_ANTI_FORGERY_GATE=FAIL
CALENDAR_APPROVAL_ANTI_FORGERY_GATE=FAIL
WORKFLOW_RUNTIME_EXECUTION_GATE=FAIL
TRACE_INVENTORY_INDEPENDENCE_GATE=FAIL
```

# Independently verified closures

The following fixes are now considered stable and should not be reopened without new evidence:

```text
HEALTH_FIELD_MINIMIZATION_GATE=PASS
TREND_TEMPORAL_EVIDENCE_GATE=PASS
OVERLOAD_FINITE_EVIDENCE_GATE=PASS
CONSTRAINT_VALUE_SEMANTICS_GATE=PASS
MEMORY_VALIDATION_FAIL_CLOSED_GATE=PASS
PENDING_AUDIT_STATUS_GATE=PASS
```

In particular, `max_intensity=0.5` is now preserved as:

```text
effective_constraints.max_intensity=0.5
constraint_applied=False
constraint_pending_application=True
```

without inventing a load conversion.

# Independent probes reproduced

```text
CALLER_BOOLEAN_HEALTH_AUTH_APPLIES=True
FAKE_PERMISSION_OBJECT_APPLIES=True
FORGED_VERIFIED_ENVELOPE_APPLIES=True
EXPIRED_CONSTRAINT_WITH_CALLER_CURRENT_TRUE_APPLIES=True

FAKE_CALENDAR_EVIDENCE_AUTHORIZES=True
FAKE_CALENDAR_REQUEST_DECISION_OBJECTS_AUTHORIZE=True

MAX_INTENSITY_PRESERVED=PASS
```

# Re-Audit V4 entry criteria

Do not build the next audit bundle until all are fresh-green:

1. `evaluate_health_constraint()` has no caller Boolean authorization fallback.
2. Permission evidence is concrete canonical evidence, not duck typing.
3. Manually fabricated vetted Health envelopes cannot affect Sport.
4. Constraint effective period/currentness is validated from evidence.
5. Return-to-Training cannot accept fabricated Health authorization.
6. Calendar readiness accepts only service/gate-validated approval evidence.
7. Fake `approval_evidence` objects fail.
8. Fake request/decision objects fail.
9. Shared Return-to-Training workflow produces the authoritative Sport recommendation.
10. Checkpoints 31–33 consume the shared workflow result.
11. Trace inventory is constructed entirely before trace assembly from real runtime objects.
12. `domain_results` inventory evidence is not copied from the trace.
13. Synthetic/fallback baseline reference IDs are removed.
14. All 44 checkpoints remain connected.
15. Exact 14-module + 11/9/6/8/5 canon is unchanged.
16. All six previously closed gates remain green.
17. Focused Sport, domains, global, Ruff, format and compile gates are fresh-green.
18. Documentation says re-audit pending rather than independently closed.
19. No push, merge, or Phase 10.29+ changes.

# Final state

```text
PHASE10_28=NOT_CLOSED
INDEPENDENT_REAUDIT_V3=FAIL
DP_028=REQUIRES_PHASE_INSPECTION
AT_DP_028=CANDIDATE_ONLY

BLOCKERS=1
MAJORS=3
MINORS=1

AUDIT_BUNDLE=phase-10.28-audit-v4.tar.gz
AUDIT_HEAD=ed8d29bf3f8f6c1a3ddd23f5fd44e06bf7813036
AUDIT_SHA256=ffa84ddb5e3869daa817409893cf238b3defe875fdf8a88477987bef0c87c586

PUSH=NO
MERGE=NO
NEXT=REMEDIATE_AUDIT_V3
```
