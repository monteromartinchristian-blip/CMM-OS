# Phase 10.28 — Sport Domain Independent Re-Audit V2 Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining independent re-audit V2 findings for `domain:sport` by making Health authorization, calendar approval, Return-to-Training workflow execution, and trace evidence non-forgeable end-to-end while preserving the frozen Sport canon.

**Architecture:** Keep the existing 14-module Sport Domain Pack and reuse shared CMM OS permission, approval, workflow, memory, trace, and resolver contracts. Caller-provided strings/booleans are metadata only and must never constitute authorization evidence. Production paths must consume validated shared-runtime artifacts or results produced by canonical services.

**Tech Stack:** Python >=3.10, pytest >=9,<10, Ruff >=0.9,<1, existing Domain Intelligence / Agent Runtime / Workflow / Permission / Approval / Memory / Trace contracts.

**Spec:** `docs/roadmap/phase-10-domain-intelligence.md` — Phase 10.28 Sport Domain

**Prior plans:**
- `docs/superpowers/plans/2026-08-25-sport-domain-implementation.md`
- `docs/superpowers/plans/2026-08-25-sport-domain-audit-v1-remediation.md`

**Independent audit evidence:**
- `docs/audits/phase-10.28-sport-independent-audit-v1.md`
- `docs/audits/phase-10.28-sport-independent-reaudit-v2.md`

## Global Constraints

- Required branch: `feature/phase-10-domain-intelligence`.
- Re-audit V2 candidate commit: `9a0df758702ebf340561f7f0d5b17e86fc5de941`.
- Re-audit V2 bundle SHA-256: `f032b92645966deed8fd882d28906c88f98c6723c5404452e58f5c80e6496cb6`.
- Preserve exact package boundary: **14 Sport production modules**.
- Preserve exact inventory: **11 entities / 9 resources / 6 rules / 8 operations / 5 workflows**.
- Preserve `domain:sport`, `SportProfile`, version `1.0.0`.
- Preserve `sport.return_to_training_with_health_constraints`.
- Preserve all V1 fixes that passed re-audit V2:
  - Health field minimization;
  - temporal trend evidence;
  - finite overload evidence;
  - fail-closed memory validation;
  - `DP-028=REQUIRES_PHASE_INSPECTION`.
- No push.
- No merge.
- Do not close Phase 10.28.
- Do not advance Phase 10.29+.
- No new Sport-specific permission engine, approval engine, workflow engine, trace engine, memory store, planner, runtime, Health store, clinical engine, or scheduler.
- Do not import private Health implementation modules.
- Do not accept any free caller Boolean/string as sufficient proof of:
  - cross-domain authorization;
  - calendar approval;
  - runtime reference existence.
- Shared production code may change only if a RED regression proves the shared contract cannot express the required invariant. Stop and report before such a change.
- Strict TDD for each remaining finding.
- Stage exact files only.
- Existing audit bundles and `tmp/` remain untracked and untouched.

---

# Re-Audit V2 Verdict to Close

```text
PHASE10_28=NOT_CLOSED
INDEPENDENT_REAUDIT_V2=FAIL

BLOCKERS=1
MAJORS=3
MINORS=0
```

Open findings:

```text
B1  Health authorization still caller-forgeable end-to-end
M3  max_intensity marked applied but actual value discarded
M4  fabricated approval IDs authorize schedule readiness
M5  AT-DP-028 bypasses shared workflow execution and trace inventory is circular
```

Current failed gates:

```text
CONSTRAINT_VALUE_SEMANTICS_GATE
SCOPED_CALENDAR_APPROVAL_GATE
CONNECTED_CROSS_DOMAIN_ACCEPTANCE_GATE
RUNTIME_TRACE_EVIDENCE_GATE
```

The following gates are already closed and must remain green:

```text
HEALTH_FIELD_MINIMIZATION_GATE
TREND_TEMPORAL_EVIDENCE_GATE
OVERLOAD_FINITE_EVIDENCE_GATE
MEMORY_VALIDATION_FAIL_CLOSED_GATE
PENDING_AUDIT_STATUS_GATE
```

---

# File Scope

## Production expected to change

```text
cmm/domains/sport/operations.py
cmm/domains/sport/workflows.py
cmm/domains/sport/trace.py          # only if the current adapter needs to expose/validate runtime references
cmm/domains/sport/permissions.py    # only if needed to bind the existing shared permission result
```

## Tests expected to change

```text
tests/domains/test_sport_domain_cross_domain.py
tests/domains/test_sport_domain_operations.py
tests/domains/test_sport_domain_permissions.py
tests/domains/test_sport_domain_workflows.py
tests/domains/test_sport_domain_trace.py
tests/domains/test_sport_domain_dp028_acceptance.py
tests/domains/test_sport_domain_safety.py
```

## Shared runtime references to inspect and reuse

```text
cmm/domains/permission_contracts.py
cmm/domains/permission_resolution.py
cmm/domains/permission_gate.py
cmm/domains/operation_execution.py

cmm/agent_runtime/approval_contracts.py
cmm/agent_runtime/approval_service.py

cmm/domains/workflow_execution.py
cmm/domains/workflow_contracts.py
cmm/domains/workflow_registry.py

cmm/domains/trace_contracts.py
cmm/domains/trace_validation.py

tests/domains/test_languages_domain_dp026_acceptance.py
```

If actual names differ, use the currently imported production/shared types from the repository. Do not create replacements merely to satisfy this plan.

---

# Root-Cause Rule

The remaining four findings are one class of defect:

```text
caller-controlled token
→ treated as trusted evidence
→ privileged Sport behavior
```

The remediation must replace that pattern with:

```text
canonical shared service
→ typed request/result/decision
→ verified relation/scope/status
→ trusted runtime artifact
→ Sport behavior
```

No fix is accepted if it merely renames:
- `is_authorized`;
- `has_approval`;
- `approval_request_id`;
- `approval_decision_id`;
- `authorization_reference`;
- arbitrary trace IDs;

without verifying them against canonical runtime evidence.

---

# Task 0 — Baseline and evidence installation

- [ ] **Step 1: Record remediation base**

```bash
cd "/Users/chris/CMM OS" || exit 1
set -euo pipefail

test "$(git branch --show-current)" = "feature/phase-10-domain-intelligence"

REMEDIATION_V2_BASE="$(git rev-parse HEAD)"
echo "REMEDIATION_V2_BASE=$REMEDIATION_V2_BASE"

git status --short --branch
git diff --check
```

Verify `9a0df758702ebf340561f7f0d5b17e86fc5de941` is an ancestor.

- [ ] **Step 2: Read the V2 report completely**

Confirm the versioned report contains:

```text
BLOCKERS=1
MAJORS=3
MINORS=0
```

and SHA-256:

```text
f032b92645966deed8fd882d28906c88f98c6723c5404452e58f5c80e6496cb6
```

- [ ] **Step 3: Fresh pre-remediation regression baseline**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_sport_domain_*.py

.venv/bin/python -m ruff check \
  cmm/domains/sport \
  tests/domains/test_sport_domain_*.py

git diff --check
```

Record fresh counts.

---

# Task 1 — Close B1: make Health authorization non-forgeable in production

**Files:**
- Modify: `cmm/domains/sport/operations.py`
- Modify: `cmm/domains/sport/workflows.py`
- Modify only if required: `cmm/domains/sport/permissions.py`
- Test: `tests/domains/test_sport_domain_cross_domain.py`
- Test: `tests/domains/test_sport_domain_operations.py`
- Test: `tests/domains/test_sport_domain_workflows.py`
- Test: `tests/domains/test_sport_domain_safety.py`

## Required production invariant

Sport operations/workflows may apply a Health constraint only when the supplied object is demonstrably derived from the canonical cross-domain permission path.

A raw dictionary such as:

```python
{
    "status": "active",
    "authorization_reference": "fake",
    "load_limits": {"reduction_pct": 50},
}
```

must not be applied.

A caller Boolean:

```python
is_authorized=True
```

must not authorize Return-to-Training.

## Recommended representation

Prefer an existing typed shared result if one is already available.

If the current Sport rule returns a plain mapping, require a normalized vetted envelope with all of:

```text
applied = True
constraint = minimized mapping
authorization_reference = actual permission decision ID
authorization_verified = True or existing typed equivalent
authorization_source = canonical permission gate/resolver result
```

Do not let the caller fabricate `authorization_verified`; construct this only inside the adapter that consumes a real permission result.

- [ ] **Step 1: RED — forged raw Health authorization**

Add tests:

```python
def test_raw_health_constraint_with_fabricated_authorization_is_not_applied():
    result = adjust_training_load_result(
        current_load=100.0,
        health_constraint={
            "status": "active",
            "authorization_reference": "fake",
            "load_limits": {"reduction_pct": 50},
        },
    )
    assert result["constraint_applied"] is False
    assert result["adjusted_load"] == 100.0
```

and equivalent `generate_workout_result()` protection.

Expected current candidate: RED.

- [ ] **Step 2: RED — workflow Boolean cannot authorize**

Call the current Return-to-Training public execution function with:
- valid-looking raw constraint;
- `is_authorized=True`;
- fabricated authorization reference.

Expected after remediation:
- no Health constraint applied;
- workflow returns unknown/hold/request-authorization or repository-equivalent safe state.

The test must prove the Boolean is insufficient.

- [ ] **Step 3: RED — real permission decision succeeds**

Construct the repository's real:
- `CrossDomainPermissionRequest`;
- permission resolution;
- `DomainPermissionGate` result.

Feed that actual decision into the Sport Health projection adapter and assert:
- minimized allowed fields only;
- actual decision/reference preserved;
- Sport operation can use the vetted result.

- [ ] **Step 4: GREEN — remove raw-dict trust**

Refactor `_extract_authorized_health_constraint()` or equivalent so:
- raw dictionaries are not authorization evidence;
- `authorization_reference` non-emptiness is not enough;
- only the result of the vetted adapter/path can be applied.

Do not silently fall back to the old path for compatibility inside Phase 10.28 tests.

- [ ] **Step 5: GREEN — remove caller authorization Boolean**

Refactor `execute_return_to_training_workflow()` or equivalent to consume:
- vetted Health constraint result; or
- typed permission evidence + projection.

A Boolean may remain descriptive metadata only, never the authorization gate.

- [ ] **Step 6: Verify**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_cross_domain.py \
  tests/domains/test_sport_domain_operations.py \
  tests/domains/test_sport_domain_workflows.py \
  tests/domains/test_sport_domain_safety.py
```

- [ ] **Step 7: Commit**

```bash
git add -- \
  cmm/domains/sport/operations.py \
  cmm/domains/sport/workflows.py \
  cmm/domains/sport/permissions.py \
  tests/domains/test_sport_domain_cross_domain.py \
  tests/domains/test_sport_domain_operations.py \
  tests/domains/test_sport_domain_workflows.py \
  tests/domains/test_sport_domain_safety.py

git diff --cached --check
git commit -m "fix(sport): require verified Health authorization evidence"
```

Stage only changed files.

---

# Task 2 — Close M3: preserve non-commensurate Health limits explicitly

**Files:**
- Modify: `cmm/domains/sport/operations.py`
- Test: `tests/domains/test_sport_domain_operations.py`
- Test: `tests/domains/test_sport_domain_cross_domain.py`

## Required behavior

For an authorized vetted constraint:

```python
{"load_limits": {"max_intensity": 0.5}}
```

Sport must not:
- invent a conversion to `current_load`;
- discard the value;
- claim it was fully applied while returning no effective limit.

- [ ] **Step 1: RED — `max_intensity` remains observable**

Write:

```python
result = adjust_training_load_result(
    current_load=100.0,
    health_constraint=vetted_constraint(
        load_limits={"max_intensity": 0.5},
    ),
)

assert result["adjusted_load"] == 100.0
assert result["effective_constraints"]["max_intensity"] == 0.5
assert result["constraint_applied"] is False
assert result["constraint_pending_application"] is True
```

Use repository-consistent field names. If the result model already exposes a general `limits`/`constraints` field, use it rather than adding parallel metadata.

- [ ] **Step 2: RED — `reduction_pct` and `max_load` remain actually applied**

Preserve V1 fixes:

```text
reduction_pct=10 → 100 becomes 90
max_load=80      → 100 becomes <=80
```

- [ ] **Step 3: GREEN — explicit effective limits**

Return non-commensurate limits as explicit validated constraints for downstream workout/session logic.

Only set `constraint_applied=True` when the current operation actually enforced a commensurate limit.

- [ ] **Step 4: Verify**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_operations.py \
  tests/domains/test_sport_domain_cross_domain.py
```

- [ ] **Step 5: Commit**

```bash
git add -- \
  cmm/domains/sport/operations.py \
  tests/domains/test_sport_domain_operations.py \
  tests/domains/test_sport_domain_cross_domain.py

git diff --cached --check
git commit -m "fix(sport): preserve explicit Health load limits"
```

---

# Task 3 — Close M4: schedule readiness must verify canonical approval evidence

**Files:**
- Modify: `cmm/domains/sport/operations.py`
- Modify only if required: `cmm/domains/sport/permissions.py`
- Test: `tests/domains/test_sport_domain_operations.py`
- Test: `tests/domains/test_sport_domain_permissions.py`

## Required invariant

These strings are never sufficient:

```python
approval_request_id="fake-request"
approval_decision_id="fake-decision"
```

Schedule readiness must be based on the actual canonical approval decision/request relationship.

- [ ] **Step 1: RED — fabricated IDs fail**

```python
result = schedule_sessions_result(
    sessions=[{"day": "Mon"}],
    approval_request_id="fake-request",
    approval_decision_id="fake-decision",
)

assert result["status"] == "proposal_pending_approval"
assert result["approval_granted"] is False
```

Expected current candidate: RED.

- [ ] **Step 2: RED — mismatched real IDs fail**

Using `ApprovalService`:
- create request A;
- create/obtain approved decision A;
- create request B;
- pair request B with decision A.

Expected:
- pending/denied;
- no readiness for external execution.

- [ ] **Step 3: RED — wrong operation scope fails**

Create/approve a request for an unrelated operation/resource.

Supply it to Sport scheduling.

Expected:
- pending/denied.

- [ ] **Step 4: RED — correct canonical approval succeeds**

Use actual service-generated request + approved decision scoped to the expected schedule/calendar operation.

Expected:
- `ready_for_external_execution`;
- actual request/decision IDs preserved;
- no calendar mutation performed by Sport.

- [ ] **Step 5: GREEN — consume validated approval artifact**

Prefer passing the canonical `ApprovalDecision` plus request/service-derived validation context into `schedule_sessions_result()` rather than two caller strings.

If existing operation execution infrastructure has a normalized approval outcome type, use it.

Do not add a Sport approval registry.

- [ ] **Step 6: Verify**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_operations.py \
  tests/domains/test_sport_domain_permissions.py
```

- [ ] **Step 7: Commit**

```bash
git add -- \
  cmm/domains/sport/operations.py \
  cmm/domains/sport/permissions.py \
  tests/domains/test_sport_domain_operations.py \
  tests/domains/test_sport_domain_permissions.py

git diff --cached --check
git commit -m "fix(sport): verify scoped calendar approval evidence"
```

Stage only changed files.

---

# Task 4 — Close M5-A: execute Return to Training through the shared workflow runtime

**Files:**
- Modify if required: `cmm/domains/sport/workflows.py`
- Test: `tests/domains/test_sport_domain_workflows.py`
- Rewrite relevant section: `tests/domains/test_sport_domain_dp028_acceptance.py`

## Required invariant

AT-DP-028 checkpoint 30 must not prove:

```text
direct helper call succeeded
```

It must prove:

```text
canonical workflow definition
→ shared workflow executor
→ workflow run/result
→ vetted Health projection consumed
→ Sport recommendation
```

- [ ] **Step 1: Inspect current executor contract**

Read the existing shared workflow executor and a working Phase 10 acceptance that executes a domain workflow.

Identify:
- workflow definition lookup;
- execution request/context type;
- executor entrypoint;
- run/result identifier;
- produced output/evidence.

Do not write a Sport executor.

- [ ] **Step 2: RED acceptance checkpoint 30**

Replace the direct helper checkpoint with the shared runtime call.

Before any production change, run:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_dp028_acceptance.py
```

Expected RED if Sport workflow wiring is incomplete.

- [ ] **Step 3: GREEN only proven Sport wiring gaps**

If the canonical Sport workflow already runs, this task may be tests-only.

If not, minimally adapt the Sport workflow definition/handler registration to the shared executor.

- [ ] **Step 4: Preserve actual workflow run evidence**

Carry the real workflow run/result reference into acceptance state for Task 5 trace construction.

- [ ] **Step 5: Verify**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_workflows.py \
  tests/domains/test_sport_domain_dp028_acceptance.py
```

- [ ] **Step 6: Commit**

```bash
git add -- \
  cmm/domains/sport/workflows.py \
  tests/domains/test_sport_domain_workflows.py \
  tests/domains/test_sport_domain_dp028_acceptance.py

git diff --cached --check
git commit -m "test(sport): execute return-to-training through workflow runtime"
```

Stage only changed files.

---

# Task 5 — Close M5-B: build trace inventory independently from real runtime artifacts

**Files:**
- Modify only if required: `cmm/domains/sport/trace.py`
- Modify: `tests/domains/test_sport_domain_trace.py`
- Modify: `tests/domains/test_sport_domain_dp028_acceptance.py`

## Forbidden pattern

Do not use:

```python
DomainTraceReferenceInventory(
    references=trace.all_references(),
)
```

as proof that trace references exist.

The inventory must exist independently of the trace.

## Required evidence sources

Build inventory references from the actual objects produced in the same AT-DP-028 run, including where the current trace schema supports them:

```text
domain resolution result/context reference
composition/reference
Sport rule/operation result reference
cross-domain permission request
permission decision
permission-gate outcome
approval request
approval decision
shared workflow run/result
memory proposal
memory binding
final domain/result reference
```

- [ ] **Step 1: RED — fabricated baseline reference fails**

Construct a trace with one reference not present in independently assembled runtime evidence.

Expected:
- invalid trace.

This test must fail on the current circular approach.

- [ ] **Step 2: Build independent inventory before final trace**

Pseudo-shape:

```python
runtime_refs = {
    actual_permission_request.request_id,
    actual_permission_decision.decision_id,
    actual_approval_request.request_id,
    actual_approval_decision.decision_id,
    actual_workflow_run.run_id,
    actual_memory_proposal.proposal_id,
    actual_memory_binding.binding_id,
    ...
}

inventory = DomainTraceReferenceInventory(
    references=frozenset(runtime_refs),
    ...
)

trace = build_sport_trace(
    ... references drawn from those runtime objects ...
)
```

Use actual field names.

The key ordering invariant:

```text
runtime objects → inventory
runtime objects → trace
inventory never derives from trace
```

- [ ] **Step 3: RED/GREEN tampering**

Keep two negative cases:
1. fabricated reference present in trace but absent from inventory;
2. valid trace mutated after inventory construction.

Both must fail.

- [ ] **Step 4: Acceptance checkpoint 40**

Checkpoint 40 passes only after validation against the independently constructed inventory.

- [ ] **Step 5: Verify**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_trace.py \
  tests/domains/test_sport_domain_dp028_acceptance.py
```

- [ ] **Step 6: Commit**

```bash
git add -- \
  cmm/domains/sport/trace.py \
  tests/domains/test_sport_domain_trace.py \
  tests/domains/test_sport_domain_dp028_acceptance.py

git diff --cached --check
git commit -m "test(sport): validate traces against runtime evidence"
```

Stage only changed files.

---

# Task 6 — Full AT-DP-028 adversarial closure

**Files:**
- Modify: `tests/domains/test_sport_domain_dp028_acceptance.py`
- Modify focused tests only if a newly exposed defect requires it.

The connected 44-checkpoint scenario must now carry these real artifacts forward:

```text
resolver/profile
→ Sport state
→ CrossDomainPermissionRequest
→ permission decision
→ DomainPermissionGate
→ minimized verified Health constraint
→ shared Return-to-Training workflow execution
→ Sport recommendation
→ schedule proposal
→ ApprovalService request
→ approval decision
→ validated schedule readiness
→ memory proposal/view/binding validation
→ independent runtime trace inventory
→ trace validation
→ atomic registration
→ rollback
→ General fallback
```

- [ ] **Step 1: Verify exact 44 checkpoints remain**

No checkpoint may be removed or replaced by a weaker assertion.

- [ ] **Step 2: Add explicit anti-forgery acceptance assertions**

Inside the same scenario prove:

```text
fake Health authorization reference → cannot affect Sport
fake approval IDs → cannot authorize scheduling
wrong-scope approval → cannot authorize scheduling
fabricated trace reference → trace invalid
```

- [ ] **Step 3: Fresh AT-DP-028**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_sport_domain_dp028_acceptance.py
```

- [ ] **Step 4: Focused adversarial suite**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_cross_domain.py \
  tests/domains/test_sport_domain_operations.py \
  tests/domains/test_sport_domain_permissions.py \
  tests/domains/test_sport_domain_workflows.py \
  tests/domains/test_sport_domain_trace.py \
  tests/domains/test_sport_domain_safety.py \
  tests/domains/test_sport_domain_dp028_acceptance.py
```

- [ ] **Step 5: Commit**

```bash
git add -- \
  tests/domains/test_sport_domain_dp028_acceptance.py \
  tests/domains/test_sport_domain_cross_domain.py \
  tests/domains/test_sport_domain_operations.py \
  tests/domains/test_sport_domain_permissions.py \
  tests/domains/test_sport_domain_workflows.py \
  tests/domains/test_sport_domain_trace.py \
  tests/domains/test_sport_domain_safety.py \
  cmm/domains/sport

git diff --cached --check
git commit -m "test(sport): close audit v2 anti-forgery gates"
```

Inspect staged scope before commit.

---

# Task 7 — Documentation and pre-re-audit V3 verification

**Files:**
- Modify: `docs/reference/sport-domain.md`
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`
- Modify `ROADMAP.md` only if current convention requires it.

- [ ] **Step 1: Candidate status**

Before independent audit V3:

```text
Phase 10.28 — implemented; audit V2 findings remediated; re-audit pending
AT-DP-028 — candidate PASS
DP-028 — REQUIRES_PHASE_INSPECTION
```

Do not claim closure or `VERIFIED_EXISTING`.

- [ ] **Step 2: Document final evidence semantics**

State explicitly:
- Health authorization must resolve to canonical permission evidence;
- arbitrary `authorization_reference` values are untrusted;
- non-commensurate constraints remain explicit;
- calendar readiness requires verified request/decision relationship and operation scope;
- Return to Training uses shared workflow execution;
- trace inventories derive independently from real runtime artifacts.

- [ ] **Step 3: Fresh Sport**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_sport_domain_*.py
```

- [ ] **Step 4: Domains**

```bash
.venv/bin/python -m pytest -q tests/domains
```

- [ ] **Step 5: Global**

```bash
.venv/bin/python -m pytest -q
```

- [ ] **Step 6: Compile/Ruff/format**

```bash
.venv/bin/python -m compileall -q cmm

.venv/bin/python -m ruff check \
  cmm/domains/sport \
  tests/domains/test_sport_domain_*.py

.venv/bin/python -m ruff format --check \
  cmm/domains/sport \
  tests/domains/test_sport_domain_*.py
```

- [ ] **Step 7: Canonical invariant gates**

Verify exact:
- 14 production modules;
- 11/9/6/8/5;
- five workflow IDs;
- no Health private imports;
- no parallel Sport infrastructure.

- [ ] **Step 8: Nine V1/V2 audit gates**

All must now be:

```text
HEALTH_FIELD_MINIMIZATION_GATE=PASS
TREND_TEMPORAL_EVIDENCE_GATE=PASS
OVERLOAD_FINITE_EVIDENCE_GATE=PASS
CONSTRAINT_VALUE_SEMANTICS_GATE=PASS
SCOPED_CALENDAR_APPROVAL_GATE=PASS
MEMORY_VALIDATION_FAIL_CLOSED_GATE=PASS
CONNECTED_CROSS_DOMAIN_ACCEPTANCE_GATE=PASS
RUNTIME_TRACE_EVIDENCE_GATE=PASS
PENDING_AUDIT_STATUS_GATE=PASS
```

Additionally print:

```text
HEALTH_AUTHORIZATION_ANTI_FORGERY_GATE=PASS
CALENDAR_APPROVAL_ANTI_FORGERY_GATE=PASS
WORKFLOW_RUNTIME_EXECUTION_GATE=PASS
TRACE_INVENTORY_INDEPENDENCE_GATE=PASS
```

- [ ] **Step 9: Documentation commit**

```bash
git add -- \
  docs/reference/sport-domain.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/roadmap/phase-10-domain-intelligence.md \
  ROADMAP.md

git diff --cached --check
git commit -m "docs(sport): record audit v2 remediation evidence"
```

Stage `ROADMAP.md` only if changed.

- [ ] **Step 10: Final report**

```text
PHASE10_28_REMEDIATION_V2=COMPLETE|INCOMPLETE
AUDIT_V2_BLOCKERS_REMAINING=<n>
AUDIT_V2_MAJORS_REMAINING=<n>
AUDIT_V2_MINORS_REMAINING=<n>

AT_DP_028=PASS|FAIL
AT_DP_028_CHECKPOINTS=44

SPORT_TESTS=<fresh>
DOMAIN_TESTS=<fresh>
GLOBAL_TESTS=<fresh>

SPORT_RUFF=PASS|FAIL
SPORT_FORMAT=PASS|FAIL
COMPILE=PASS|FAIL

DP_028=REQUIRES_PHASE_INSPECTION|NOT_READY
REMEDIATION_V2_BASE=<sha>
HEAD=<sha>

PUSH=NO
MERGE=NO
NEXT=BUILD_REAUDIT_V4_BUNDLE|REMEDIATE
```

Stop before building the audit bundle unless the user explicitly directs the next step.

---

# Plan Self-Review

## Finding coverage

| Finding | Task |
| --- | --- |
| B1 forged Health authorization | 1, 4, 6 |
| M3 lost `max_intensity` semantics | 2 |
| M4 forged calendar approval IDs | 3, 6 |
| M5 shared workflow execution | 4, 6 |
| M5 circular trace inventory | 5, 6 |
| candidate documentation | 7 |

## Previously closed V1 findings

Tasks 1–7 must retain regression coverage for:
- field minimization;
- timestamped trend evidence;
- finite overload values;
- memory fail-closed;
- audit-pending DP-028 status.

## Scope lock

No canon changes, no new Domain Pack modules, no Phase 10.29 work, no push/merge, no closure claim.
