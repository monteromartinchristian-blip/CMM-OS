# Phase 10.28 — Sport Domain Independent-Audit V1 Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remediate every finding from the first independent audit of Phase 10.28, rebuild `AT-DP-028` as a genuinely connected acceptance lifecycle, and leave `domain:sport` ready for a second independent audit without changing the frozen `11/9/6/8/5` canon.

**Architecture:** Fix root causes inside the existing 14-module Sport Domain Pack and reuse shared Phase 10 contracts for cross-domain permissions, approval gating, memory validation, trace validation, workflow execution and fallback. Health data must cross into Sport only through a minimized, authorized, current `health_constraint`; calendar readiness must carry real scoped approval evidence; memory and trace validation must fail closed. No new Sport-specific engine or shared subsystem is allowed.

**Tech Stack:** Python >=3.10, pytest >=9,<10, Ruff >=0.9,<1, existing CMM OS Domain Intelligence / Workflow / Permission / Approval / Memory / Trace contracts.

**Original implementation plan:** `docs/superpowers/plans/2026-08-25-sport-domain-implementation.md`

**Independent audit:** `docs/audits/phase-10.28-sport-independent-audit-v1.md`

## Global Constraints

- Required branch: `feature/phase-10-domain-intelligence`.
- Remediation starts from the current versioned HEAD that produced `phase-10.28-audit-v2.tar.gz`; record that SHA before mutation.
- Independent-audit bundle SHA-256: `3adef2ab6a61e80e9c51bbe3bd343f9f6f4ec198a7f1193b054ca2075e6c8146`.
- Preserve exact canonical counts: `11 entities / 9 resources / 6 rules / 8 operations / 5 workflows`.
- Preserve exact 14 production files under `cmm/domains/sport/`.
- Preserve exact workflow ID `sport.return_to_training_with_health_constraints`.
- Preserve `domain:sport`, `Sport`, `SportProfile`, version `1.0.0`.
- No push.
- No merge.
- Do not close Phase 10.28 in this remediation run.
- Do not modify Phase 10.29+ implementation/specification.
- Do not touch `tmp/` or previous audit bundles except to create the next fresh audit bundle after remediation.
- Do not weaken existing tests.
- Strict TDD: reproduce each audited defect with a failing regression before production changes.
- A RED test must fail for the audited reason.
- Shared production code may change only if a new RED regression proves the current shared contract cannot express the remediation; if so, STOP and report before broadening architecture.
- No Sport-specific planner, runtime, workflow engine, memory store, knowledge store, permission engine, approval engine, trace engine, clinical engine or scheduler.
- Sport production must not import private Health implementation modules.
- Unknown, malformed, stale, unauthorized or unvalidated evidence must fail closed or remain explicitly unknown.
- Caller-controlled booleans or strings are not sufficient evidence of permission, approval or trace integrity.
- AT-DP-028 must use real shared resolver/composer/workflow/permission/approval/memory/trace outputs and carry state forward.
- Candidate documentation after remediation must remain `pending independent re-audit`; `DP-028` must not be `VERIFIED_EXISTING` until the auditor passes it.

---

# Audit Findings to Close

```text
B1  Health → Sport minimization/authorization not enforced end-to-end
B2  Sport memory binding validation fails open

M1  MeasurementTrendRule lacks temporal evidence enforcement
M2  ProgressiveOverloadRule accepts NaN/Inf decision evidence
M3  Health load-limit semantics replaced by hard-coded 30% reduction
M4  Calendar approval represented by bare Boolean
M5  AT-DP-028 not sufficiently connected to canonical runtime evidence

m1  DP-028 marked VERIFIED_EXISTING before independent audit
```

Independent adversarial gates currently failing:

```text
HEALTH_FIELD_MINIMIZATION_GATE
TREND_TEMPORAL_EVIDENCE_GATE
OVERLOAD_FINITE_EVIDENCE_GATE
CONSTRAINT_VALUE_SEMANTICS_GATE
SCOPED_CALENDAR_APPROVAL_GATE
MEMORY_VALIDATION_FAIL_CLOSED_GATE
CONNECTED_CROSS_DOMAIN_ACCEPTANCE_GATE
RUNTIME_TRACE_EVIDENCE_GATE
PENDING_AUDIT_STATUS_GATE
```

---

# Allowed File Map

## Sport production files expected to change

```text
cmm/domains/sport/rules.py
cmm/domains/sport/operations.py
cmm/domains/sport/memory.py
cmm/domains/sport/trace.py          # only if connected trace proves a Sport adapter defect
cmm/domains/sport/workflows.py      # only if connected workflow proves a Sport defect
cmm/domains/sport/permissions.py    # only if current adapter cannot expose shared permission evidence
```

## Tests expected to change

```text
tests/domains/test_sport_domain_rules.py
tests/domains/test_sport_domain_safety.py
tests/domains/test_sport_domain_operations.py
tests/domains/test_sport_domain_permissions.py
tests/domains/test_sport_domain_memory.py
tests/domains/test_sport_domain_cross_domain.py
tests/domains/test_sport_domain_trace.py
tests/domains/test_sport_domain_workflows.py
tests/domains/test_sport_domain_dp028_acceptance.py
```

## Canonical shared references to inspect, not duplicate

```text
cmm/domains/permission_contracts.py
cmm/domains/permission_gate.py
cmm/domains/permission_adapters.py
cmm/domains/operation_execution.py
cmm/domains/memory_validation.py
cmm/domains/trace_validation.py
cmm/domains/trace_contracts.py
cmm/agent_runtime/approval_contracts.py
cmm/agent_runtime/approval_service.py

tests/domains/test_languages_domain_dp026_acceptance.py
tests/domains/test_languages_domain_adversarial.py
tests/domains/test_languages_domain_memory.py
tests/domains/test_languages_domain_trace.py
```

The hardened Languages acceptance is the strongest existing example of real `DomainPermissionGate`, `ApprovalService`, memory snapshots/bindings and `DomainTraceReferenceInventory`. Follow those shared patterns instead of inventing new Sport contracts.

## Documentation

Already installed before agent execution:

```text
docs/audits/phase-10.28-sport-independent-audit-v1.md
docs/superpowers/plans/2026-08-25-sport-domain-audit-v1-remediation.md
```

After successful remediation update:

```text
docs/reference/sport-domain.md
docs/reference/domain-intelligence-requirements-matrix.md
docs/roadmap/phase-10-domain-intelligence.md
```

Only modify `ROADMAP.md` if the current repository convention requires a Phase 10 candidate-state update.

---

# Root-Cause Map

## Root Cause A — Authorization was represented as metadata, not an enforced projection boundary

Affected:
- B1
- M3
- M5

Current defects:
- `evaluate_health_constraint()` computes `allowed_fields` but returns the original projection.
- operation helpers accept raw dictionaries and trust `status == "active"`.
- AT-DP-028 uses `is_authorized=True` rather than a real permission decision/gate.

Fix:
- sanitize once at the Health→Sport boundary;
- carry the sanitized artifact plus authorization/provenance evidence;
- require operations/workflow to consume only that vetted representation or equivalent validated mapping.

## Root Cause B — Validation wrappers turn infrastructure failure into success

Affected:
- B2

Current defect:
- `validate_sport_memory_binding()` catches every exception and returns `VALID`.

Fix:
- fail closed;
- preserve canonical validation codes/errors;
- never return success after a validator exception.

## Root Cause C — Numeric/temporal evidence validation is incomplete

Affected:
- M1
- M2

Current defects:
- trend uses caller list order and accepts missing timestamps;
- overload calculations admit non-finite values.

Fix:
- centralize small pure validation helpers inside `rules.py`;
- reject invalid evidence before decision logic.

## Root Cause D — Approval and trace checkpoints assert labels instead of runtime evidence

Affected:
- M4
- M5

Current defects:
- `has_approval=True` acts as proof;
- acceptance uses literal trace IDs and direct helper calls.

Fix:
- use canonical `ApprovalService` + `DomainPermissionGate`;
- carry request/decision IDs;
- validate trace against a real `DomainTraceReferenceInventory`.

---

# Task 0 — Baseline and remediation evidence gate

**Files:** documentation only already installed.

- [ ] **Step 1: Capture exact remediation base**

```bash
cd "/Users/chris/CMM OS" || exit 1
set -euo pipefail

test "$(git branch --show-current)" = "feature/phase-10-domain-intelligence"

REMEDIATION_BASE="$(git rev-parse HEAD)"
echo "REMEDIATION_BASE=$REMEDIATION_BASE"

git status --short --branch
git diff --check
```

Known untracked audit bundles and `tmp/` may remain; do not stage them.

- [ ] **Step 2: Verify audit report identity**

The installed report must contain:

```text
BLOCKERS=2
MAJORS=5
MINORS=1
```

and the bundle SHA above.

- [ ] **Step 3: Fresh candidate baseline**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_sport_domain_*.py

.venv/bin/python -m ruff check \
  cmm/domains/sport \
  tests/domains/test_sport_domain_*.py

.venv/bin/python -m ruff format --check \
  cmm/domains/sport \
  tests/domains/test_sport_domain_*.py

git diff --check
```

Record fresh baseline counts. They prove only that the old candidate is internally green, not that the audit findings are fixed.

---

# Task 1 — Close B1: enforce a minimized, authorized Health → Sport boundary

**Files:**
- Modify: `cmm/domains/sport/rules.py`
- Modify: `cmm/domains/sport/operations.py`
- Modify if required: `cmm/domains/sport/workflows.py`
- Test: `tests/domains/test_sport_domain_cross_domain.py`
- Test: `tests/domains/test_sport_domain_safety.py`
- Test: `tests/domains/test_sport_domain_operations.py`

**Interfaces**
- Consumes the existing typed cross-domain permission contracts.
- Produces a sanitized `health_constraint` mapping or the repository-equivalent vetted Sport representation.
- No new Health store or permission engine.

- [ ] **Step 1: RED — arbitrary clinical extras must not cross**

Add an adversarial regression using an otherwise valid constraint:

```python
projection = {
    "constraint_id": "hc-001",
    "status": "active",
    "activity_limits": ["no_running"],
    "load_limits": {"reduction_pct": 10},
    "source_reference": "health:source:1",
    "authorization_reference": "permission:decision:1",
    "diagnosis": "ACL tear",
    "treatment_plan": "surgery",
    "clinical_notes": "secret",
}

result = evaluate_health_constraint(
    projection,
    is_authorized=True,
    is_current=True,
)

assert result["applied"] is True
assert result["constraint"] == {
    "constraint_id": "hc-001",
    "status": "active",
    "activity_limits": ["no_running"],
    "load_limits": {"reduction_pct": 10},
    "source_reference": "health:source:1",
    "authorization_reference": "permission:decision:1",
}
assert "diagnosis" not in result["constraint"]
assert "treatment_plan" not in result["constraint"]
assert "clinical_notes" not in result["constraint"]
```

Adapt exact allowed fields to the current canonical contract. The important invariant is that output is newly minimized and contains no unknown clinical extras.

Run focused RED and verify the old implementation leaks them.

- [ ] **Step 2: RED — raw active dictionary is not authorization evidence**

Add operation/workflow tests proving that a raw mapping with:

```text
status=active
load_limits=...
```

but no validated authorization/currentness evidence cannot be treated as an applied Health constraint.

Do not solve by adding another caller Boolean.

- [ ] **Step 3: GREEN — sanitize at the boundary**

In `evaluate_health_constraint()`:
- validate authorization/currentness;
- construct a new dict from the allowlist;
- preserve provenance/authorization fields;
- never return the caller mapping directly.

Unknown extras may be dropped or cause explicit rejection according to the existing policy style, but they must never survive into Sport reasoning.

- [ ] **Step 4: GREEN — operations consume vetted constraint**

Refactor Sport operation/workflow inputs so the applied Health constraint is demonstrably the sanitized result or a typed validated artifact.

At minimum, operations must not infer authorization solely from `status == "active"`.

- [ ] **Step 5: Focused verification**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_cross_domain.py \
  tests/domains/test_sport_domain_safety.py \
  tests/domains/test_sport_domain_operations.py \
  tests/domains/test_sport_domain_workflows.py
```

- [ ] **Step 6: Commit**

```bash
git add -- \
  cmm/domains/sport/rules.py \
  cmm/domains/sport/operations.py \
  cmm/domains/sport/workflows.py \
  tests/domains/test_sport_domain_cross_domain.py \
  tests/domains/test_sport_domain_safety.py \
  tests/domains/test_sport_domain_operations.py \
  tests/domains/test_sport_domain_workflows.py

git diff --cached --check
git commit -m "fix(sport): enforce authorized Health projection boundary"
```

Stage only files actually changed.

---

# Task 2 — Close M1/M2/M3: temporal and numeric evidence correctness

**Files:**
- Modify: `cmm/domains/sport/rules.py`
- Modify: `cmm/domains/sport/operations.py`
- Test: `tests/domains/test_sport_domain_rules.py`
- Test: `tests/domains/test_sport_domain_safety.py`
- Test: `tests/domains/test_sport_domain_operations.py`

## 2A — Measurement trend temporal evidence

- [ ] **Step 1: RED missing timestamp**

Prove two otherwise comparable observations without timestamp return `invalid_evidence` or repository-equivalent non-trend state.

- [ ] **Step 2: RED invalid/out-of-order time**

Choose and document one deterministic contract:
- either normalize by parsing timestamps and sorting before trend calculation;
- or reject non-monotonic input.

Recommendation: parse ISO timestamps and sort, while preserving original observations/provenance. Reject unparseable timestamps and duplicate timestamps when they make ordering ambiguous.

Tests must prove caller list order cannot fabricate direction.

- [ ] **Step 3: RED metric/unit/method comparability**

Each observation must correspond to the requested metric and compatible unit/method. Do not infer comparability from only the first row.

- [ ] **Step 4: GREEN minimal implementation**

Use a small internal parser/validator. Do not add a new temporal subsystem.

## 2B — Progressive overload finite evidence

- [ ] **Step 5: RED NaN/Inf/Boolean**

Add cases for:
- baseline `NaN` / `Inf`;
- proposed `NaN` / `Inf`;
- threshold `NaN` / `Inf`;
- Boolean numeric inputs.

Expected: explicit invalid evidence, never `certainty=True`.

- [ ] **Step 6: GREEN finite checks before arithmetic**

Use `math.isfinite()` or equivalent after rejecting `bool`.

## 2C — Actual Health load-limit semantics

- [ ] **Step 7: RED constraint value must be honored**

Example:

```python
result = adjust_training_load_result(
    current_load=100.0,
    readiness_state="ready",
    health_constraint=<validated constraint with reduction_pct=10>,
)

assert result["adjusted_load"] == pytest.approx(90.0)
```

Also test:
- `reduction_pct=0`;
- invalid negative or >100 values fail closed;
- `max_intensity` follows its actual documented unit/meaning and is not converted into arbitrary 30% reduction.

- [ ] **Step 8: GREEN remove `current_load * 0.7`**

Apply the actual sanitized constraint value.

If `max_intensity` and `current_load` are not semantically commensurate, do not invent a conversion. Return an explicit limit/proposal requiring the consumer to interpret the field correctly.

- [ ] **Step 9: Verify**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_rules.py \
  tests/domains/test_sport_domain_safety.py \
  tests/domains/test_sport_domain_operations.py
```

- [ ] **Step 10: Commit**

```bash
git add -- \
  cmm/domains/sport/rules.py \
  cmm/domains/sport/operations.py \
  tests/domains/test_sport_domain_rules.py \
  tests/domains/test_sport_domain_safety.py \
  tests/domains/test_sport_domain_operations.py

git diff --cached --check
git commit -m "fix(sport): validate temporal and load evidence"
```

---

# Task 3 — Close B2: memory validation must fail closed

**Files:**
- Modify: `cmm/domains/sport/memory.py`
- Test: `tests/domains/test_sport_domain_memory.py`
- Test: `tests/domains/test_sport_domain_safety.py`

- [ ] **Step 1: RED validator exception**

Monkeypatch or inject the canonical validator path so `DefaultDomainMemoryIntegrationValidator.validate_binding()` raises a deterministic exception.

Expected:

```text
is_valid != True
code != VALID
```

Use the repository's existing validation error/result conventions. If the shared validator is specified to raise, the Sport wrapper may propagate rather than inventing a result.

- [ ] **Step 2: RED malformed inventory/binding**

Prove malformed or mismatched binding/inventory cannot become `VALID`.

- [ ] **Step 3: GREEN remove fail-open fallback**

Replace:

```python
except Exception:
    return VALID
```

with one of:
- direct propagation of the canonical validator error;
- explicit invalid/error result if the shared contract defines one.

Do not catch broad exceptions unless translating them to failure.

- [ ] **Step 4: Verify**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_memory.py \
  tests/domains/test_sport_domain_safety.py
```

- [ ] **Step 5: Commit**

```bash
git add -- \
  cmm/domains/sport/memory.py \
  tests/domains/test_sport_domain_memory.py \
  tests/domains/test_sport_domain_safety.py

git diff --cached --check
git commit -m "fix(sport): fail closed on memory validation"
```

---

# Task 4 — Close M4: replace Boolean calendar approval with scoped approval evidence

**Files:**
- Modify: `cmm/domains/sport/operations.py`
- Modify if required: `cmm/domains/sport/permissions.py`
- Test: `tests/domains/test_sport_domain_operations.py`
- Test: `tests/domains/test_sport_domain_permissions.py`

**Canonical references:**
- `cmm.agent_runtime.approval_service.ApprovalService`
- `cmm.agent_runtime.approval_contracts.ApprovalRequest`
- shared `DomainPermissionGate`
- hardened Languages approval tests/acceptance

- [ ] **Step 1: RED bare Boolean is insufficient**

Remove/replace acceptance that treats:

```python
has_approval=True
```

as proof of scoped authorization.

A direct helper may still accept a normalized approval object/status if this is the established operation API, but not a free Boolean detached from request identity/scope.

- [ ] **Step 2: RED canonical lifecycle**

Build a real shared lifecycle:

```text
operation requires approval
→ ApprovalService creates request
→ decision approves the request
→ DomainPermissionGate / operation execution receives approved status/evidence
→ Sport schedule proposal becomes ready for external execution
```

Tests must preserve:
- approval request ID;
- approval decision ID;
- target operation/resource scope;
- no implicit authorization for an unrelated schedule/action.

- [ ] **Step 3: GREEN bind schedule readiness to evidence**

Return/reference the real approval identifiers or shared normalized approval evidence in the result.

`sport.schedule_sessions` still must not mutate an external calendar itself.

- [ ] **Step 4: Verify**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_operations.py \
  tests/domains/test_sport_domain_permissions.py
```

- [ ] **Step 5: Commit**

```bash
git add -- \
  cmm/domains/sport/operations.py \
  cmm/domains/sport/permissions.py \
  tests/domains/test_sport_domain_operations.py \
  tests/domains/test_sport_domain_permissions.py

git diff --cached --check
git commit -m "fix(sport): bind scheduling to scoped approval evidence"
```

Stage only files actually changed.

---

# Task 5 — Close M5: rebuild AT-DP-028 as a real connected lifecycle

**Files:**
- Rewrite/harden: `tests/domains/test_sport_domain_dp028_acceptance.py`
- Modify only when RED proves defects:
  - `cmm/domains/sport/trace.py`
  - `cmm/domains/sport/workflows.py`
  - `cmm/domains/sport/integration.py`
  - other Sport modules already in scope
- Focused tests as needed.

## Required shared runtime objects

AT-DP-028 must use the repository's actual equivalents of:

```text
DefaultDomainResolver / domain resolution
SportProfile registry/binding
DefaultDomainComposer where Health composition is required
CrossDomainPermissionRequest
DomainPermissionResolver
DomainPermissionGate
ApprovalService
DomainWorkflowExecutor
DomainMemoryProposalSnapshot / view / binding
DefaultDomainMemoryIntegrationValidator
DomainTrace
DomainTraceReferenceInventory
Sport trace validator / shared trace validator
General fallback
```

Use the hardened Languages `AT-DP-026` as the reference for wiring, not as a source to copy domain semantics.

## State-linked lifecycle

The acceptance remains the canonical **44 semantic checkpoints**, but checkpoints must consume outputs from prior steps.

At minimum change these previously simulated sections:

### Cross-domain checkpoints 25–31

Old invalid shape:

```text
dict health projection
+ is_authorized=True
+ is_current=True
```

Required:

```text
Sport need for Health constraint
→ typed CrossDomainPermissionRequest
→ real permission resolution
→ permission gate outcome
→ authorized/minimized projection
→ Return to Training workflow consumes that exact projection
→ restrictive Sport recommendation
```

Assert the full dossier request is denied by the same permission path.

### Calendar checkpoints 34–36

Old invalid shape:

```text
has_approval=False/True
```

Required:

```text
schedule proposal
→ real ApprovalRequest
→ pending gate
→ real ApprovalDecision
→ approved gate
→ ready_for_external_execution with request/decision references
```

No calendar mutation occurs inside Sport.

### Memory checkpoints 37–38

Use:
- real memory proposal;
- real view;
- real binding;
- canonical inventory;
- `validate_sport_memory_binding()`.

Assert validation succeeds only for the correct connected inventory and fails for tampered/malformed evidence.

### Trace checkpoints 39–40

Do not prove trace integrity with arbitrary literal IDs alone.

Build the trace from actual objects/references produced in this acceptance run:
- permission decision;
- approval request/decision;
- workflow/run result;
- memory proposal/binding;
- relevant domain result IDs.

Construct `DomainTraceReferenceInventory` from those actual instances and require Sport/shared trace validation to pass.

Tamper at least one reference and prove validation fails.

### Atomic integration / fallback checkpoints 41–44

Retain:
- atomic registration;
- rollback parity;
- no parallel infrastructure;
- General fallback.

They must execute in the same scenario state, not unrelated fixtures.

- [ ] **Step 1: Rewrite acceptance into connected RED**

Before production edits, run:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_dp028_acceptance.py
```

Expected RED should expose the missing runtime wiring/evidence, not syntax/import mistakes.

- [ ] **Step 2: Fix only proven Sport defects**

Do not modify shared engines merely to make the scenario convenient.

- [ ] **Step 3: Acceptance GREEN**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_dp028_acceptance.py
```

- [ ] **Step 4: Adversarial focused suite**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_cross_domain.py \
  tests/domains/test_sport_domain_permissions.py \
  tests/domains/test_sport_domain_memory.py \
  tests/domains/test_sport_domain_trace.py \
  tests/domains/test_sport_domain_safety.py \
  tests/domains/test_sport_domain_dp028_acceptance.py
```

- [ ] **Step 5: Commit**

```bash
git add -- \
  tests/domains/test_sport_domain_dp028_acceptance.py \
  tests/domains/test_sport_domain_cross_domain.py \
  tests/domains/test_sport_domain_permissions.py \
  tests/domains/test_sport_domain_memory.py \
  tests/domains/test_sport_domain_trace.py \
  tests/domains/test_sport_domain_safety.py \
  cmm/domains/sport

git diff --cached --check
git commit -m "test(sport): harden AT-DP-028 connected lifecycle"
```

Inspect staged names and unstage unrelated Sport files before committing.

---

# Task 6 — Close m1, document remediation, and run pre-audit gates

**Files:**
- Modify: `docs/reference/sport-domain.md`
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`
- Modify `ROADMAP.md` only if current convention requires it.

- [ ] **Step 1: Fix candidate status**

Before re-audit:

```text
Phase 10.28 — implemented; independent audit V1 findings remediated; re-audit pending
AT-DP-028 — candidate PASS
DP-028 — REQUIRES_PHASE_INSPECTION
```

Use exact repository vocabulary where applicable.

Do **not** write:
- `VERIFIED_EXISTING`;
- `independently audited`;
- `COMPLETE`;
- final closure PASS.

- [ ] **Step 2: Document corrected invariants**

Reference doc must explicitly state:
- Health projection is minimized before Sport use;
- operations consume validated/current authorization evidence;
- trend observations require valid temporal/comparable evidence;
- overload inputs must be finite;
- load limits use actual authorized values;
- calendar approval is scoped and referenceable;
- memory validation fails closed;
- AT-DP-028 validates real cross-domain, approval, memory and trace evidence.

- [ ] **Step 3: Full Sport suite**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_sport_domain_*.py
```

- [ ] **Step 4: All domain tests**

```bash
.venv/bin/python -m pytest -q tests/domains
```

- [ ] **Step 5: Global suite**

```bash
.venv/bin/python -m pytest -q
```

Record fresh counts. Do not reuse historical `64` / `11782`.

- [ ] **Step 6: Compile / Ruff / format**

```bash
.venv/bin/python -m compileall -q cmm

.venv/bin/python -m ruff check \
  cmm/domains/sport \
  tests/domains/test_sport_domain_*.py

.venv/bin/python -m ruff format --check \
  cmm/domains/sport \
  tests/domains/test_sport_domain_*.py
```

Repository-wide pre-existing Ruff debt is reported separately and not “fixed” by unrelated edits unless current closure policy explicitly requires it.

- [ ] **Step 7: Canonical package/count gate**

Verify:
- 14 Sport modules exact;
- 11/9/6/8/5 unchanged;
- workflow ID unchanged;
- no Sport parallel infrastructure;
- no Health private implementation imports.

- [ ] **Step 8: Audit-finding probe gate**

Add or run regressions proving all nine V1 gates are now green:

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

- [ ] **Step 9: Documentation commit**

```bash
git add -- \
  docs/reference/sport-domain.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/roadmap/phase-10-domain-intelligence.md \
  ROADMAP.md

git diff --cached --check
git commit -m "docs(sport): record audit v1 remediation evidence"
```

Stage `ROADMAP.md` only if changed.

- [ ] **Step 10: Final remediation state**

Print:

```text
PHASE10_28_REMEDIATION_V1=COMPLETE|INCOMPLETE
AUDIT_V1_BLOCKERS_REMAINING=<n>
AUDIT_V1_MAJORS_REMAINING=<n>
AUDIT_V1_MINORS_REMAINING=<n>
AT_DP_028=PASS|FAIL
AT_DP_028_CHECKPOINTS=44
SPORT_TESTS=<fresh result>
DOMAIN_TESTS=<fresh result>
GLOBAL_TESTS=<fresh result>
SPORT_RUFF=PASS|FAIL
SPORT_FORMAT=PASS|FAIL
COMPILE=PASS|FAIL
DP_028=REQUIRES_PHASE_INSPECTION|NOT_READY
REMEDIATION_BASE=<sha>
HEAD=<sha>
PUSH=NO
MERGE=NO
NEXT=BUILD_REAUDIT_BUNDLE|REMEDIATE
```

Stop before independent re-audit.

---

# Remediation Self-Review

## Finding coverage

| Audit finding | Task |
| --- | --- |
| B1 Health minimization/authorization | 1, 5 |
| B2 memory validation fail-open | 3, 5 |
| M1 temporal trend evidence | 2, 5 |
| M2 non-finite overload evidence | 2 |
| M3 hard-coded 30% reduction | 2 |
| M4 Boolean calendar approval | 4, 5 |
| M5 disconnected AT-DP-028 | 5 |
| m1 premature DP-028 status | 6 |

## Audit gate coverage

All nine failed independent probes have a direct RED→GREEN regression requirement.

## Scope check

This remediation does not change the Sport canon, introduce new architecture, or advance Phase 10.29. It repairs the evidence/permission/validation boundaries required for 10.28 closure.
