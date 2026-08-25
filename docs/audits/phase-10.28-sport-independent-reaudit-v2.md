# Phase 10.28 — Sport Domain — Independent Re-Audit V2

Date: 2026-08-25
Auditor: ChatGPT — independent CMM OS closure auditor
Candidate bundle: `phase-10.28-audit-v3.tar.gz`

## Bundle identity

```text
ARCHIVE_COMMIT=9a0df758702ebf340561f7f0d5b17e86fc5de941
SHA256=f032b92645966deed8fd882d28906c88f98c6723c5404452e58f5c80e6496cb6
MEMBERS=1736
SAFE_EXTRACT=PASS
SANITIZATION=PASS
```

The bundle contains no `.env`, `.git`, `.venv`, `.worktrees`, `.tokensave`, `tmp/`, or audit TAR.GZ payloads.

## Structural gates

```text
SPORT_PACKAGE_MODULES=14_EXACT
ENTITIES=11_EXACT
RESOURCES=9_EXACT
RULES=6_EXACT
OPERATIONS=8_EXACT
WORKFLOWS=5_EXACT
AT_DP_028_STATE_CHECKPOINTS=44_EXACT
COMPILEALL_SPORT_AND_TESTS=PASS
PRIVATE_HEALTH_IMPLEMENTATION_IMPORTS=0
PARALLEL_SPORT_INFRASTRUCTURE=0
PLACEHOLDERS=0
```

## Independent execution limitation

The auditor attempted to execute:

```bash
python -m pytest -p no:cacheprovider -q   tests/domains/test_sport_domain_dp028_acceptance.py
```

Collection is blocked by the audit environment because `libcst` is not installed:

```text
ModuleNotFoundError: No module named 'libcst'
```

This dependency is part of the candidate project environment; the missing package is an auditor-container limitation and is **not** counted as a Sport defect.

The candidate agent reports fresh remediation results of `71` Sport tests and `11789` global tests with focal Ruff green. These are candidate-side evidence, not independently re-executed test counts.

# Verdict

## FAIL — a second remediation is required

```text
PHASE10_28=NOT_CLOSED
INDEPENDENT_REAUDIT_V2=FAIL
DP_028=NOT_VERIFIED
AT_DP_028=NOT_ACCEPTED_FOR_FINAL_CLOSURE

BLOCKERS=1
MAJORS=3
MINORS=0

PUSH=NO
MERGE=NO
NEXT=REMEDIATE_AUDIT_V2
```

The V1 remediation materially improved the candidate, but the authorization/evidence chain is still bypassable.

# V1 findings status

| Finding | V2 result |
| --- | --- |
| B1 — Health → Sport authorization/minimization end-to-end | **OPEN — BLOCKER** |
| B2 — memory validation fail-open | **CLOSED** |
| M1 — temporal trend evidence | **CLOSED** |
| M2 — non-finite overload evidence | **CLOSED** |
| M3 — Health load-limit semantics | **OPEN — MAJOR** |
| M4 — scoped calendar approval | **OPEN — MAJOR** |
| M5 — connected runtime acceptance / trace evidence | **OPEN — MAJOR** |
| m1 — premature DP-028 status | **CLOSED** |

# Blocking finding

## B1 — Health authorization is still caller-forgeable at Sport operation/workflow boundaries

### Fixed portion

`cmm/domains/sport/rules.py:362-419` now creates a new allowlisted projection. Clinical extras such as `diagnosis`, `treatment_plan`, and `clinical_notes` no longer survive the minimization step.

This part of B1 is correctly remediated.

### Remaining defect

`cmm/domains/sport/operations.py:170-202` accepts either:

```text
{applied: true, constraint: {...}}
```

or an arbitrary raw dictionary.

It considers the raw dictionary authorized when:

```python
hc.get("status") == "active"
and hc.get("authorization_reference")
```

The reference is only checked for non-emptiness. It is not resolved against a permission decision, permission gate, reference inventory, or typed validated projection.

Independent reproduction with the exact candidate function body:

```python
raw = {
    "status": "active",
    "authorization_reference": "totally-fabricated",
    "load_limits": {"reduction_pct": 50},
}

adjust_training_load_result(
    current_load=100,
    health_constraint=raw,
)
```

Actual result:

```text
constraint_applied=True
adjusted_load=50.0
```

A second independent reproduction:

```python
{
    "status": "active",
    "authorization_reference": "fake",
    "activity_limits": ["no_high_impact"],
}
```

is accepted by `generate_workout_result()` and changes the workout decision.

`cmm/domains/sport/workflows.py:280-319` also still accepts a raw Health mapping plus caller-controlled:

```python
is_authorized: bool
is_current: bool
```

Independent reproduction with `is_authorized=True` and a fabricated authorization reference produced:

```text
health_constraint_applied=True
recommendation=reduce_load
```

### Why this remains a blocker

The V1 remediation acceptance criteria explicitly required that Sport operations **cannot consume an unvetted raw Health dictionary as authorized evidence**.

The connected AT-DP-028 now creates a real `DomainPermissionGate` decision, but the production operation/workflow APIs can still bypass that path.

### Required remediation

Choose one canonical boundary and enforce it:

1. Operations/workflows consume only the vetted `evaluate_health_constraint()` result carrying a real permission-decision reference; or
2. introduce/use an existing typed validated cross-domain projection object whose authorization reference is verified against canonical permission evidence.

Do not accept a free raw dictionary merely because it contains an arbitrary non-empty `authorization_reference`.

Remove caller-controlled `is_authorized=True` as sufficient proof at the workflow boundary.

Add adversarial regressions using fabricated authorization IDs.

# Major findings

## M3 — `max_intensity` is marked “applied” but its actual constraint value is discarded

### Evidence

`cmm/domains/sport/operations.py:217-255`

`reduction_pct` and `max_load` now use their real values. This part is fixed.

But the `max_intensity` branch is:

```python
elif "max_intensity" in load_limits:
    constraint_applied = True
```

No reduction is invented anymore, which is good, but the result does not expose or preserve the actual `max_intensity` value.

Independent probe:

```text
current_load=100
max_intensity=0.5
```

Actual result:

```text
adjusted_load=100
constraint_applied=True
```

The returned object contains no `max_intensity=0.5` or equivalent explicit limit.

### Why this is still wrong

The remediation plan explicitly required that when `max_intensity` is not commensurate with `current_load`, Sport must **preserve it as an explicit limit/proposal** rather than pretending the constraint has been handled.

The current response says the constraint was applied while losing the constraint itself.

### Required remediation

Return the effective authorized load/activity limits, for example through the repository-consistent equivalent of:

```text
effective_constraints
load_limits
max_intensity
```

or do not mark it as applied until a downstream consumer actually applies the constraint.

---

## M4 — fabricated approval IDs still authorize calendar readiness

### Evidence

`cmm/domains/sport/operations.py:355-402`

The Boolean-only path is fixed: `has_approval=True` by itself no longer succeeds.

However:

```python
elif approval_request_id and approval_decision_id:
    is_approved = True
```

accepts any two non-empty strings.

Independent reproduction:

```python
schedule_sessions_result(
    sessions=[{"day": "Mon"}],
    approval_request_id="fake-request",
    approval_decision_id="fake-decision",
)
```

Actual result:

```text
status=ready_for_external_execution
approval_granted=True
```

No `ApprovalService` lookup, decision/request relationship check, operation scope, actor/session scope, expiry, or permission-gate evidence is verified.

The focused test itself labels arbitrary string IDs as “Real scoped approval evidence”, which is not true.

### Required remediation

The readiness helper must consume canonical validated approval evidence, not identifiers supplied by the caller.

At minimum verify:
- the decision exists;
- it belongs to the request;
- status is approved;
- request scope is `sport.schedule_sessions` / expected calendar operation;
- any required permission-gate scope matches.

A mismatched/fabricated request or decision must return `proposal_pending_approval`.

---

## M5 — AT-DP-028 is more connected, but runtime workflow/trace proof is still incomplete

### What is fixed

The acceptance now has exactly 44 state-linked checkpoints and uses real shared objects for:
- `CrossDomainPermissionRequest`;
- `DomainPermissionGate`;
- `ApprovalService`;
- memory proposal/view/binding validation;
- domain resolution/composition;
- rule execution;
- atomic registration / rollback.

This is a substantial improvement.

### Remaining issue A — Return to Training bypasses the shared workflow executor

At checkpoint 30, the acceptance directly calls:

```python
execute_return_to_training_workflow(...)
```

There is no shared `DomainWorkflowExecutor` / workflow-run result in the connected chain.

Therefore the acceptance does not prove that the canonical workflow definition:

```text
sport.return_to_training_with_health_constraints
```

actually executes through the shared workflow runtime with the permission-approved Health projection.

### Remaining issue B — trace inventory is self-derived from the trace it validates

At `tests/domains/test_sport_domain_dp028_acceptance.py:760-771`:

```python
inventory = DomainTraceReferenceInventory(
    references=trace.all_references(),
    ...
)
```

That makes reference-existence validation circular.

A fabricated baseline reference can be placed into the trace and then automatically copied into the inventory, so the initial validation would accept it. The tampering test proves that changing the trace *after* inventory construction is detected, but it does not prove that the baseline references came from real runtime objects.

### Required remediation

- Run Return to Training through the existing shared workflow execution path and carry its actual run/result ID forward.
- Build `DomainTraceReferenceInventory` independently from the actual runtime objects produced by the scenario: resolver result, composition, rule result, permission decision, approval request/decision, workflow run/result, memory proposal/binding, domain result.
- Then assemble the trace from those references and validate it against the independently built inventory.
- Keep the tampered-reference negative test.

# V2 adversarial gate replay

After source-level and isolated exact-body probes:

```text
HEALTH_FIELD_MINIMIZATION_GATE=PASS
TREND_TEMPORAL_EVIDENCE_GATE=PASS
OVERLOAD_FINITE_EVIDENCE_GATE=PASS
CONSTRAINT_VALUE_SEMANTICS_GATE=FAIL
SCOPED_CALENDAR_APPROVAL_GATE=FAIL
MEMORY_VALIDATION_FAIL_CLOSED_GATE=PASS
CONNECTED_CROSS_DOMAIN_ACCEPTANCE_GATE=FAIL
RUNTIME_TRACE_EVIDENCE_GATE=FAIL
PENDING_AUDIT_STATUS_GATE=PASS

AUDIT_PROBE_TOTAL=9
AUDIT_PROBE_PASS=5
AUDIT_PROBE_FAIL=4
```

The connected-cross-domain gate is marked FAIL after full lifecycle review because production workflow authorization is still caller-controlled and checkpoint 30 bypasses the shared workflow executor.

# Independently verified improvements

The following V1 defects are genuinely fixed:

## Health field minimization

An accepted Health projection is rebuilt from the allowlist. Independent clinical extras are dropped.

## Measurement trend temporal evidence

Missing timestamps now return invalid evidence; unsorted valid timestamps are deterministically sorted before trend direction is calculated.

## Progressive overload finite evidence

NaN, Inf and Boolean inputs now fail as invalid evidence with `certainty=False`.

## Memory validation fail-closed

`validate_sport_memory_binding()` no longer catches validator exceptions and converts them into `VALID`. An injected validator exception propagates, which is fail-closed.

## Candidate status

`DP-028` correctly remains:

```text
REQUIRES_PHASE_INSPECTION
```

with re-audit pending.

# Re-Audit V3 entry criteria

Do not create the next audit bundle until all of the following are fresh-green:

1. Fabricated Health authorization references cannot affect Sport operations.
2. Return-to-training cannot be authorized by a caller Boolean.
3. Sport operations/workflows consume only a validated/minimized Health projection or typed equivalent.
4. `max_intensity` / non-commensurate limits remain explicitly represented and cannot be silently “applied”.
5. Fabricated/mismatched calendar approval IDs cannot yield `ready_for_external_execution`.
6. Calendar approval scope is verified against the expected operation.
7. AT-DP-028 executes Return to Training through the shared workflow runtime.
8. Trace inventory is built independently from actual runtime objects, not `trace.all_references()`.
9. Tampered and fabricated trace references both fail.
10. All 44 semantic checkpoints remain connected.
11. Exact 14-module and 11/9/6/8/5 canon remains unchanged.
12. Focused Sport, domain and global suites are fresh-green.
13. Ruff/format/compileall are fresh-green on the changed surface.
14. `DP-028=REQUIRES_PHASE_INSPECTION` until the next independent audit passes.
15. No push, merge or Phase 10.29+ implementation changes.

# Final state

```text
PHASE10_28=NOT_CLOSED
INDEPENDENT_REAUDIT_V2=FAIL
DP_028=REQUIRES_PHASE_INSPECTION
AT_DP_028=CANDIDATE_ONLY

BLOCKERS=1
MAJORS=3
MINORS=0

AUDIT_BUNDLE=phase-10.28-audit-v3.tar.gz
AUDIT_HEAD=9a0df758702ebf340561f7f0d5b17e86fc5de941
AUDIT_SHA256=f032b92645966deed8fd882d28906c88f98c6723c5404452e58f5c80e6496cb6

PUSH=NO
MERGE=NO
NEXT=REMEDIATE_AUDIT_V2
```
