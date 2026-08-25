# Phase 10.28 — Sport Domain — Independent Re-Audit V4

Date: 2026-08-25
Auditor: ChatGPT — independent CMM OS closure auditor
Candidate bundle: `phase-10.28-audit-v5.tar.gz`

## Bundle identity

```text
AUDIT_HEAD=94ea379ce2d2ae7018c0566618cd425a43e83eb3
SHA256=1432871f4d68086bfc1d274f7a59e28c131c1836aa41527aaf774f7c47f3164b
SIZE=3,605,294 bytes
MEMBERS=1740
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
COMPILEALL_SPORT_AND_TESTS=PASS
PRIVATE_HEALTH_IMPLEMENTATION_IMPORTS=0
PARALLEL_SPORT_INFRASTRUCTURE=0
```

## Candidate-side verification evidence

The remediation agent reports:

```text
SPORT_TESTS=80_PASS
DOMAIN_TESTS=6268_PASS
GLOBAL_TESTS=11798_PASS
SPORT_RUFF=PASS
SPORT_FORMAT=PASS
COMPILE=PASS
```

These remain candidate-side results.

The independent auditor attempted:

```bash
python -m pytest -p no:cacheprovider -q   tests/domains/test_sport_domain_dp028_acceptance.py
```

Collection is still blocked by the auditor container because `libcst` is not installed:

```text
ModuleNotFoundError: No module named 'libcst'
```

This is an auditor-environment limitation and is not counted as a Sport defect.

# Verdict

## FAIL — Phase 10.28 remains open

```text
PHASE10_28=NOT_CLOSED
INDEPENDENT_REAUDIT_V4=FAIL
DP_028=NOT_VERIFIED
AT_DP_028=NOT_ACCEPTED_FOR_FINAL_CLOSURE

BLOCKERS=1
MAJORS=2
MINORS=1

PUSH=NO
MERGE=NO
NEXT=REMEDIATE_AUDIT_V4
```

The V3 remediation closes the workflow-authority finding, but the Health and calendar trust boundaries still equate **being an instance of a canonical class** with **having been issued/validated by the canonical runtime**.

# Re-Audit V3 finding status

| Finding | V4 result |
| --- | --- |
| B1 — Health authorization non-forgeable | **OPEN — BLOCKER** |
| M4 — calendar approval non-forgeable | **OPEN — MAJOR** |
| M5-A — shared workflow runtime authoritative | **CLOSED** |
| M5-B — trace inventory wholly independent/runtime-backed | **OPEN — MAJOR** |
| m1 — documentation does not overstate independent closure | **OPEN — MINOR** |

# Blocking finding

## B1 — Canonical type identity is still treated as authorization provenance

The V3 remediation removes the free Boolean authorization path, rejects duck-typed objects, and introduces `AuthorizedHealthConstraint`. Those are real improvements.

However the production boundary still trusts objects that callers can construct directly.

### B1-A — caller-constructed `CrossDomainPermissionDecision(ALLOW)` authorizes Health

`cmm/domains/sport/rules.py:455-462`

```python
elif (
    isinstance(permission_decision, CrossDomainPermissionDecision)
    and permission_decision.decision is PermissionOutcome.ALLOW
):
    auth_verified = True
    auth_ref = permission_decision.request_id
    req_id = permission_decision.request_id
```

`CrossDomainPermissionDecision` is a public frozen dataclass. Its contract contains no source-domain or target-domain field that this function can verify.

The Sport tests themselves construct it directly:

```python
CrossDomainPermissionDecision(
    request_id="auth.scope.sport_return_to_training",
    decision=PermissionOutcome.ALLOW,
)
```

without using `DomainPermissionResolver`.

### Independent exact-body probe

Using the exact `evaluate_health_constraint()` AST from the candidate bundle with the candidate contract shape:

```text
FORGED_CROSS_DOMAIN_DECISION_APPLIED=True
```

A manually created ALLOW decision produced a trusted `AuthorizedHealthConstraint`.

### B1-B — caller-constructed `PermissionGateResult` can authorize an unrelated action/domain

`cmm/domains/sport/rules.py:433-454`

The implementation checks source/target only when those keys happen to exist in `metadata`.

Missing source/target metadata is accepted.

An exact-body probe with a concrete `PermissionGateResult` shaped as:

```text
outcome=ALLOW
action=unrelated.action
domain_id=domain:other
metadata={}
decision_id=fake-other
```

produced:

```text
applied=True
```

Sport does not require:
- expected permission action/capability;
- `domain:health → domain:sport`;
- canonical request identity;
- a resolver/gate-owned issuance record.

### B1-C — `AuthorizedHealthConstraint` is public and directly constructible

`cmm/domains/sport/rules.py:363-373`

```python
@dataclass(frozen=True, slots=True)
class AuthorizedHealthConstraint:
    ...
```

It is also exported in `rules.py::__all__`.

`cmm/domains/sport/operations.py:183-194` trusts any instance:

```python
if isinstance(health_constraint, AuthorizedHealthConstraint):
    artifact = health_constraint
```

There is no provenance lookup or private construction token.

### Independent exact-body probe

A manually constructed artifact:

```python
AuthorizedHealthConstraint(
    constraint={
        "status": "active",
        "authorization_reference": "fake",
        "load_limits": {"reduction_pct": 60},
    },
    permission_decision_id="fake-dec",
    permission_request_id="fake-req",
    source_domain="domain:health",
    target_domain="domain:sport",
)
```

was accepted by the exact candidate `adjust_training_load_result()` body:

```text
original_load=100.0
adjusted_load=40.0
constraint_applied=True
```

So the alleged “non-forgeable” value object is immutable after construction but not non-forgeable.

### B1-D — malformed temporal evidence fails open

`cmm/domains/sport/rules.py:478-530`

Invalid ISO timestamps are caught with:

```python
except (ValueError, TypeError):
    pass
```

and execution continues.

Independent exact-body probe:

```text
effective_until=not-a-date
```

with an ALLOW decision produced:

```text
applied=True
effective_until_runtime=None
```

Malformed temporal evidence must not silently become “no expiry”.

### Required remediation

Use one real trust boundary.

Acceptable patterns include:

1. `evaluate_health_constraint()` receives the original `CrossDomainPermissionRequest` plus a decision and re-resolves/verifies them against a `DomainPermissionResolver`/registry; or
2. consume a permission-gate artifact that can be looked up in a runtime-owned decision/reference inventory; or
3. introduce a private/internal Sport adapter whose factory requires a verified runtime record and whose resulting artifact cannot be constructed through a public supported API.

Whichever repository-consistent pattern is selected:

- a manually instantiated canonical decision must not authorize;
- a manually instantiated `AuthorizedHealthConstraint` must not authorize;
- missing source/target/action metadata must fail closed;
- malformed temporal bounds must fail closed;
- real resolver/gate-produced Health→Sport evidence must still succeed.

# Major finding

## M4 — Calendar approval still has two service-bypass trust paths

`cmm/domains/sport/operations.py:411-474`

The new `ApprovalService` repository lookup path is good.

But it is optional.

### M4-A — direct `PermissionGateResult` trust

Branch 1 accepts any concrete `PermissionGateResult` with:

```text
outcome=APPROVAL_CONSUMED
allowed=True
action/metadata matching schedule_sessions
```

There is no lookup/binding to the underlying approval request/decision record.

Because `PermissionGateResult` is publicly constructible, a caller can manufacture one.

Independent exact-body probe:

```text
FAKE_PERMISSION_GATE_CALENDAR_STATUS=ready_for_external_execution
FAKE_PERMISSION_GATE_APPROVAL_GRANTED=True
```

### M4-B — canonical `ApprovalRequest` + `ApprovalDecision` bypasses `ApprovalService`

Branch 3 explicitly permits:

```python
isinstance(approval_decision, ApprovalDecision)
and isinstance(approval_request, ApprovalRequest)
and approval_decision.request_id == approval_request.id
...
```

without repository lookup.

Both are public dataclasses.

A caller can construct a matching request and approved decision directly.

### Independent exact-body probe

Manually constructed concrete canonical request/decision objects produced:

```text
status=ready_for_external_execution
approval_granted=True
approval_request_id=req-forged
approval_decision_id=dec-forged
```

No `ApprovalService` record existed.

### Required remediation

Collapse scheduling to one validated path:

```text
ApprovalService / canonical approval repository
→ stored request
→ stored decision
→ matching relationship
→ approved state
→ correct operation scope
→ temporal/status checks
→ ready_for_external_execution
```

If a `PermissionGateResult(APPROVAL_CONSUMED)` is supported, it must be tied to verifiable canonical approval evidence rather than accepted solely by class/type/fields.

Remove the bare canonical-object fallback.

# Major finding

## M5-B — trace inventory still depends on the trace it is validating

The V3 remediation improves this substantially:

- `DomainResult` is now a concrete object;
- baseline reference IDs come from upstream objects;
- fabricated and tampered references have negative tests;
- `trace.all_references()` is no longer used to populate inventory.

However the explicit V3 independence invariant is still violated.

`tests/domains/test_sport_domain_dp028_acceptance.py:944-973`

The trace is built first:

```python
trace = assemble_sport_trace(...)
```

Then inventory is built with:

```python
DomainResultTraceReference(
    result_id=runtime_domain_result_id,
    domain_id=SPORT_DOMAIN_ID,
    trace_id=trace.id,
)
```

So `inventory.domain_results` still consumes a value from `trace`.

The focused trace test uses the same pattern.

### Why this remains material

The acceptance is meant to prove:

```text
runtime evidence → inventory
runtime evidence → trace
inventory independently validates trace
```

The current order is:

```text
runtime evidence → trace
runtime evidence + trace.id → inventory
inventory validates trace
```

That is much better than V2/V3, but not fully independent.

### Repository-consistent reference

The hardened Languages acceptance already solves this by determining the expected trace ID independently from a probe/canonical-id construction, then building `DomainResultTraceReference` before validating the final trace.

Sport should use the same established trace pattern rather than weakening the V3 gate.

### Required remediation

- determine the expected trace ID independently using the trace contract's canonical-ID pattern;
- build the domain-result pairing from the real `DomainResult` plus that expected ID;
- build inventory without reading any field from the final trace;
- then assemble/finalize trace and assert its ID equals the independently expected ID;
- keep fabricated/tampered negatives.

# Closed V3 finding

## M5-A — workflow runtime is now authoritative

This finding is closed.

AT-DP-028 now executes:

```text
sport.return_to_training_with_health_constraints
```

through `DomainWorkflowExecutor`.

The COMPLETE node invokes the Sport return-to-training computation inside the workflow execution adapter, and checkpoints 31–33 consume:

```python
workflow_run.execution_result.node_results["complete"].output
```

There is no second post-executor helper call used as the authoritative result.

```text
WORKFLOW_RUNTIME_EXECUTION_GATE=PASS
```

# Minor finding

## m1 — roadmap again records unaudited findings as `CLOSED`

`docs/roadmap/phase-10-domain-intelligence.md:4501-4504`

The candidate-level status correctly says:

```text
implemented; audit V3 findings remediated; re-audit pending
```

and DP-028 correctly remains `REQUIRES_PHASE_INSPECTION`.

However the finding table marks B1, M4, M5-A and M5-B as `CLOSED`.

M5-A is now independently closed, but B1, M4 and M5-B are not.

Use wording such as:

```text
REMEDIATED — pending independent re-audit
```

until the independent audit passes.

# V4 adversarial gate replay

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

Additional hardening gates:

```text
HEALTH_AUTHORIZATION_ANTI_FORGERY_GATE=FAIL
CALENDAR_APPROVAL_ANTI_FORGERY_GATE=FAIL
WORKFLOW_RUNTIME_EXECUTION_GATE=PASS
TRACE_INVENTORY_INDEPENDENCE_GATE=FAIL
TEMPORAL_HEALTH_CURRENTNESS_GATE=FAIL
```

# Independently verified stable closures

These remain stable:

```text
HEALTH_FIELD_MINIMIZATION_GATE=PASS
TREND_TEMPORAL_EVIDENCE_GATE=PASS
OVERLOAD_FINITE_EVIDENCE_GATE=PASS
CONSTRAINT_VALUE_SEMANTICS_GATE=PASS
MEMORY_VALIDATION_FAIL_CLOSED_GATE=PASS
PENDING_AUDIT_STATUS_GATE=PASS
WORKFLOW_RUNTIME_EXECUTION_GATE=PASS
```

`max_intensity` remains explicit/pending rather than being incorrectly converted to load.

# Independent V4 reproductions

Using exact candidate function bodies in isolated harnesses:

```text
FORGED_CROSS_DOMAIN_DECISION_APPLIED=True
UNRELATED_PERMISSION_GATE_APPLIED=True

FORGED_AUTHORIZED_HEALTH_ARTIFACT:
  original_load=100.0
  adjusted_load=40.0
  constraint_applied=True

MALFORMED_EFFECTIVE_UNTIL_APPLIED=True

FORGED_CANONICAL_APPROVAL_OBJECTS:
  status=ready_for_external_execution
  approval_granted=True

FORGED_PERMISSION_GATE_APPROVAL:
  status=ready_for_external_execution
  approval_granted=True
```

# Re-Audit V5 entry criteria

Do not build another audit bundle until all are fresh-green:

1. Caller-constructed `CrossDomainPermissionDecision(ALLOW)` cannot authorize Health.
2. Caller-constructed/unrelated `PermissionGateResult` cannot authorize Health.
3. Caller-constructed `AuthorizedHealthConstraint` cannot affect Sport.
4. Missing source/target/action/scope permission evidence fails closed.
5. Malformed `effective_from` / `effective_until` fails closed.
6. Expired/future Health constraints still fail closed.
7. Real resolver/gate-produced Health→Sport evidence succeeds.
8. Calendar readiness requires runtime-owned approval evidence.
9. Caller-constructed `ApprovalRequest`/`ApprovalDecision` cannot authorize.
10. Caller-constructed `PermissionGateResult(APPROVAL_CONSUMED)` cannot authorize without verifiable approval binding.
11. Correct stored ApprovalService request/decision succeeds.
12. Workflow-runtime authoritative output remains green.
13. Trace inventory contains no value read from final trace.
14. Expected trace ID/domain-result pairing is determined independently.
15. Fabricated and tampered trace negatives remain green.
16. Exactly 44 connected AT-DP-028 checkpoints remain.
17. Exact 14-module + 11/9/6/8/5 canon remains unchanged.
18. All seven independently closed gates remain green.
19. Documentation says `REMEDIATED — pending independent re-audit` for unverified findings.
20. Fresh Sport, domains, global, Ruff, format, compileall and diff hygiene are green.
21. No push, merge, or Phase 10.29+ changes.

# Final state

```text
PHASE10_28=NOT_CLOSED
INDEPENDENT_REAUDIT_V4=FAIL
DP_028=REQUIRES_PHASE_INSPECTION
AT_DP_028=CANDIDATE_ONLY

BLOCKERS=1
MAJORS=2
MINORS=1

AUDIT_BUNDLE=phase-10.28-audit-v5.tar.gz
AUDIT_HEAD=94ea379ce2d2ae7018c0566618cd425a43e83eb3
AUDIT_SHA256=1432871f4d68086bfc1d274f7a59e28c131c1836aa41527aaf774f7c47f3164b

PUSH=NO
MERGE=NO
NEXT=REMEDIATE_AUDIT_V4
```
