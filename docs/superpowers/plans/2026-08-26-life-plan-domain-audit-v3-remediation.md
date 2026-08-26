# Phase 10.29 — Life Plan Domain Independent Audit V3 Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the four remaining Independent Audit V3 findings without reopening accepted Life Plan architecture, then produce `phase-10.29-audit-v4.tar.gz`.

**Architecture:** Keep the V3 gate-issued replay fix and exact canon intact. Tighten cross-domain authorization to canonical shared service/result contracts, make memory proposal evidence reflect a real shared authorization outcome instead of converting DENY into ALLOW, construct trace inventory independently before final trace assembly, and synchronize status documentation.

**Tech Stack:** Python >=3.10, pytest >=9,<10, Ruff >=0.9,<1, existing CMM OS Domain Permission, Approval, Memory, Trace, Workflow and Presentation contracts.

**Spec:** `docs/superpowers/specs/2026-08-26-life-plan-domain-design.md`

**Prior plans:**
- `docs/superpowers/plans/2026-08-26-life-plan-domain-implementation.md`
- `docs/superpowers/plans/2026-08-26-life-plan-domain-audit-v1-remediation.md`
- `docs/superpowers/plans/2026-08-26-life-plan-domain-audit-v2-remediation.md`

**Independent audits:**
- `docs/audits/phase-10.29-life-plan-independent-audit-v1.md`
- `docs/audits/phase-10.29-life-plan-independent-audit-v2.md`
- `docs/audits/phase-10.29-life-plan-independent-audit-v3.md`

## Global Constraints

- Required branch: `feature/phase-10-domain-intelligence`.
- Required V3 candidate ancestor: `fc61411`.
- Preserve exactly 14 Life Plan production modules.
- Preserve exact canon: 13 entities / 12 resources / 8 rules / 10 operations / 7 workflows.
- Preserve `life_plan.cross_domain_impact_review` public name `Major Decision Support`.
- Preserve V3-closed findings:
  - V2 gate-issued decision-ID replay;
  - exact canonical reference documentation;
  - decision-state fail-closed behavior;
  - wrapped contribution rejection;
  - structured scenario consistency;
  - strict memory confirmation typing.
- Do not create Life Plan-local permission, approval, memory, trace, workflow, repository, planner or engine infrastructure.
- Do not weaken Health or Life Plan real policies merely to manufacture passing authorization.
- Missing service/result provenance must fail closed.
- Do not treat duck-typed authorization services as canonical trust roots.
- Do not translate `MEMORY_WRITE=DENY` into a manual `allowed=True` memory snapshot.
- Trace inventory must be independently constructed before final trace assembly.
- DP-029 remains `REQUIRES_PHASE_INSPECTION`.
- Do not mark Phase 10.29 closed.
- Do not begin Phase 10.30.
- Do not push.
- Do not merge.
- Generate V4 only from committed HEAD with `git archive`.

---

# V3 Finding Map

```text
V3-B1  BLOCKER — duck-typed fake gate/resolver can authorize Life Plan mutation.
V3-M1  MAJOR   — real MEMORY_WRITE result DENY is converted to manual allowed=True PROPOSE snapshot.
V3-M2  MAJOR   — trace inventory is constructed after final trace and depends on trace.id.
V3-m1  MINOR   — roadmap/matrix/test-count status drift.
```

---

# Task 0 — V4 Remediation Preflight

**Files:** none.

- [ ] **Step 1: Verify branch and ancestry**

```bash
cd "/Users/chris/CMM OS"

test "$(git branch --show-current)" = "feature/phase-10-domain-intelligence"
git merge-base --is-ancestor fc61411 HEAD

git log -8 --oneline --decorate
git status --short --branch
```

- [ ] **Step 2: Read binding evidence**

Read completely:

```text
docs/superpowers/specs/2026-08-26-life-plan-domain-design.md
docs/audits/phase-10.29-life-plan-independent-audit-v3.md
docs/superpowers/plans/2026-08-26-life-plan-domain-audit-v3-remediation.md

cmm/domains/life_plan/rules.py
cmm/domains/life_plan/memory.py
cmm/domains/life_plan/trace.py

cmm/domains/permission_gate.py
cmm/domains/permission_resolution.py
cmm/domains/permission_contracts.py
cmm/domains/memory_contracts.py
cmm/domains/memory_validation.py
cmm/domains/trace_contracts.py
cmm/domains/trace_assembler.py
cmm/domains/trace_validation.py

tests/domains/test_life_plan_domain_cross_domain.py
tests/domains/test_life_plan_domain_dp029_acceptance.py
tests/domains/test_life_plan_domain_closure_adversarial.py
```

Do not modify production during Task 0.

---

# Task 1 — Close V3-B1: Canonical Authorization Services and Results Only

**Files:**
- Modify: `cmm/domains/life_plan/rules.py`
- Modify: `tests/domains/test_life_plan_domain_cross_domain.py`
- Modify: `tests/domains/test_life_plan_domain_closure_adversarial.py`

## Required behavior

`evaluate_cross_domain_impact(...)` must not authorize through generic:

```python
hasattr(permission_gate, "evaluate_cross_domain")
hasattr(permission_resolver, "resolve_cross_domain")
```

A fake object with those methods must fail closed.

Require canonical shared service types:

```python
DomainPermissionGate
DomainPermissionResolver
```

and canonical result types:

```python
PermissionGateResult
CrossDomainPermissionDecision
```

Use exact repository import paths after inspection.

Do not accept missing provenance fields by substituting expected current request values.

Forbidden pattern:

```python
getattr(result, "actor_id", permission_request.actor_id)
```

for security-significant provenance.

Required pattern:

```text
missing field
→ mismatch / unverified
→ fail closed
```

For resolver-origin evidence, verify every provenance field the canonical result actually carries. If the canonical `CrossDomainPermissionDecision` does not carry actor/session/domain fields, do not infer them from absence. Bind validation to fields that genuinely exist in the canonical contract plus exact request identity and canonical resolver service provenance.

## Mandatory RED attacks

1. `FakeGate.evaluate_cross_domain(...) -> fake allow result`
   - expect `applied=False`
   - expect `authorization_verified=False`

2. `FakeResolver.resolve_cross_domain(...) -> fake allow decision`
   - expect fail closed.

3. Canonical-looking fake result object missing provenance fields
   - expect fail closed.

4. Preserve V2 gate-issued replay regression
   - still fail closed.

5. Preserve real canonical ALLOW control for internal sensitivity.

6. Preserve real restricted `APPROVAL_REQUIRED -> APPROVAL_CONSUMED` control.

- [ ] **Step 1: Write fake-gate RED regression**
- [ ] **Step 2: Run and confirm V3 code fails**
- [ ] **Step 3: Write fake-resolver RED regression**
- [ ] **Step 4: Run and confirm V3 code fails**
- [ ] **Step 5: Implement minimal canonical service/result checks**
- [ ] **Step 6: Remove provenance defaulting**
- [ ] **Step 7: Verify focused tests**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_cross_domain.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py \
  -k 'gate or resolver or replay or authorization or permission'
```

- [ ] **Step 8: Ruff / format**
- [ ] **Step 9: Commit**

```bash
git add -- \
  cmm/domains/life_plan/rules.py \
  tests/domains/test_life_plan_domain_cross_domain.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py

git diff --cached --check
git commit -m "fix(life-plan): require canonical authorization services"
```

Required evidence:

```text
V3_B1_FAKE_GATE_REJECTED=PASS
V3_B1_FAKE_RESOLVER_REJECTED=PASS
V3_B1_MISSING_PROVENANCE_REJECTED=PASS
V2_B1_GATE_ISSUED_ID_REPLAY_REJECTED=PASS
```

---

# Task 2 — Close V3-M1: Memory Evidence Must Match Real Authorization

**Files:**
- Modify: `tests/domains/test_life_plan_domain_dp029_acceptance.py`
- Modify: `tests/domains/test_life_plan_domain_closure_adversarial.py`
- Modify production/shared code only if a RED proves an actual contract gap.

## Problem to eliminate

V3 currently proves:

```text
DomainPermissionRequest(action=MEMORY_WRITE)
→ resolver result DENY
→ DomainMemoryPermissionDecisionSnapshot(allowed=True, PROPOSE)
```

This is invalid evidence construction.

## Required design ruling

`DomainMemoryCapability.PROPOSE` is a **proposal/confirmation lifecycle**, not direct durable memory mutation.

Therefore do not use a denied direct `MEMORY_WRITE` permission result as the source of an allowed `PROPOSE` snapshot.

Use the existing shared permission capability/path that semantically authorizes the proposal itself.

Executor must inspect the canonical contracts and choose an existing permission action whose semantics are actually compatible with proposing a memory change without directly writing durable memory.

Preferred order:

1. existing proposal/approval-specific permission capability if one exists;
2. existing operation/workflow permission for the canonical proposal action;
3. explicit reference-only memory permission evidence only if that is the intended shared contract and is clearly documented as not a `MEMORY_WRITE` authorization.

Do **not** invent a new capability unless the shared architecture demonstrably lacks any correct representation and a focused generic change is required.

## Mandatory invariants

- actual shared permission result must authorize the semantic action represented by the memory snapshot;
- snapshot `allowed` must be derived from that real result;
- denied shared result must never produce `allowed=True`;
- memory approval remains distinct and proposal-specific;
- cross-domain permission/approval IDs remain forbidden for memory binding;
- AT-DP-029 remains exactly 45 semantic checkpoints.

## Required RED regression

Construct the exact V3 pattern:

```text
real shared MEMORY_WRITE result = DENY
→ attempt to construct/use allowed memory PROPOSE evidence
```

Expected after remediation:

```text
rejected / not used as trusted evidence
```

Add an explicit assertion tying snapshot allowed state to the actual selected shared permission outcome.

- [ ] **Step 1: Inspect canonical permission capabilities for proposal semantics**
- [ ] **Step 2: Add denied-result-to-allowed-snapshot RED regression**
- [ ] **Step 3: Build a semantically correct real permission request**
- [ ] **Step 4: Derive memory snapshot allowed/capabilities from actual result**
- [ ] **Step 5: Preserve distinct real ApprovalService memory confirmation**
- [ ] **Step 6: Re-run memory mismatch attacks**
- [ ] **Step 7: Preserve 45 checkpoints**
- [ ] **Step 8: Verify**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_dp029_acceptance.py \
  tests/domains/test_life_plan_domain_memory.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py \
  -k 'memory or dp029'
```

- [ ] **Step 9: Commit**

```bash
git add -- \
  tests/domains/test_life_plan_domain_dp029_acceptance.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py

git diff --cached --check
git commit -m "test(life-plan): bind memory evidence to real permission outcome"
```

If production/shared files are required, stage them explicitly and document the generic reason.

Required evidence:

```text
V3_M1_DENIED_MEMORY_PERMISSION_CANNOT_ALLOW_PROPOSE=PASS
V3_M1_MEMORY_PERMISSION_OUTCOME_BOUND=PASS
V2_M1_MEMORY_APPROVAL_SCOPE=PASS
```

---

# Task 3 — Close V3-M2: Independent Pre-Assembly Trace Inventory

**Files:**
- Modify: `tests/domains/test_life_plan_domain_dp029_acceptance.py`
- Modify: `tests/domains/test_life_plan_domain_closure_adversarial.py`
- Modify: `cmm/domains/life_plan/trace.py` only if needed.
- Modify shared trace API only if a focused RED proves deterministic pre-assembly identity cannot otherwise be represented.

## Required ordering

The code must visibly execute:

```text
1. produce runtime artifacts
2. create runtime artifact ledger
3. build DomainTraceReference objects
4. build DomainTraceReferenceInventory
5. assemble final trace
6. validate final trace against the pre-existing inventory
```

Forbidden:

```text
assemble trace
→ read trace.id
→ build inventory
```

## Trace identity

If `DomainTraceReferenceInventory` requires `trace_id` before final assembly:

- use an existing canonical deterministic pre-assembly trace identity API if available;
- otherwise add the smallest generic shared helper to compute the same canonical ID from the assembly inputs;
- do not create a Life Plan-local fake/probe trace;
- do not derive the expected inventory from the final trace.

## Required lifecycle references

Carry actual IDs for all produced connected artifacts:

```text
PROFILE
WORKFLOW_RUN
WORKFLOW_RESULT
PERMISSION_DECISION
APPROVAL_REQUEST
APPROVAL_DECISION
MEMORY_PROPOSAL
MEMORY_BINDING
PRESENTATION_RESULT
DOMAIN_RESULT
RESOLUTION_CONTEXT
RESOLUTION_RESULT
COMPOSITION
```

Additionally include the distinct memory-specific permission and approval artifacts created by Task 2 when they are part of the connected AT lifecycle.

Do not reuse one ID across unrelated artifact kinds.

## Required adversarial regressions

- inventory object exists before final trace object is created;
- final trace tamper fails;
- permission decision tamper fails;
- cross-domain approval tamper fails;
- memory-specific permission tamper fails;
- memory-specific approval request/decision tamper fails;
- memory binding tamper fails;
- workflow result omission/tamper fails;
- supporting-domain mismatch fails.

- [ ] **Step 1: Inspect canonical trace ID calculation**
- [ ] **Step 2: Add ordering RED regression**
- [ ] **Step 3: Build runtime ledger**
- [ ] **Step 4: Build complete references**
- [ ] **Step 5: Build inventory before trace**
- [ ] **Step 6: Assemble final trace**
- [ ] **Step 7: Validate against pre-existing inventory**
- [ ] **Step 8: Rebuild adversarial fixture with same ordering**
- [ ] **Step 9: Verify**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_trace.py \
  tests/domains/test_life_plan_domain_dp029_acceptance.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py \
  -k 'trace or dp029'
```

- [ ] **Step 10: Commit**

```bash
git add -- \
  tests/domains/test_life_plan_domain_dp029_acceptance.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py \
  cmm/domains/life_plan/trace.py

git diff --cached --check
git commit -m "test(life-plan): build trace inventory before assembly"
```

Stage only files actually changed.

Required evidence:

```text
V3_M2_TRACE_INVENTORY_PREASSEMBLY=PASS
V3_M2_TRACE_INVENTORY_INDEPENDENT=PASS
V3_M2_MEMORY_LIFECYCLE_TRACED=PASS
```

---

# Task 4 — Close V3-m1: Documentation Status Drift

**Files:**
- Modify: `docs/reference/life-plan-domain.md`
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`

Required status:

```text
Independent Audit V3 — FAIL (1 BLOCKER + 2 MAJOR + 1 MINOR).
V3 findings remediated — Independent Re-Audit V4 pending.
DP-029 — REQUIRES_PHASE_INSPECTION.
AT-DP-029 — candidate PASS, pending V4 independent acceptance.
```

Remove or update stale:

```text
awaiting independent audit v2
129 Tests
```

Prefer wording that avoids brittle hard-coded suite counts unless the docs intentionally track exact current counts.

- [ ] **Step 1: Update status docs**
- [ ] **Step 2: Remove/correct stale test count**
- [ ] **Step 3: Run doc regressions**
- [ ] **Step 4: Commit**

```bash
git add -- \
  docs/reference/life-plan-domain.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/roadmap/phase-10-domain-intelligence.md

git diff --cached --check
git commit -m "docs(life-plan): record v4 pending remediation status"
```

---

# Task 5 — Rebuild Permanent V4 Adversarial Gate

**Files:**
- Modify: `tests/domains/test_life_plan_domain_closure_adversarial.py`

Keep all valid V3 attacks.

Add/strengthen mandatory V4 attacks:

```text
A. fake duck-typed gate rejected
B. fake duck-typed resolver rejected
C. missing result provenance rejected
D. real gate-issued decision replay still rejected
E. denied shared memory permission cannot become allowed memory snapshot
F. cross-domain permission cannot become memory permission
G. cross-domain approval cannot become memory approval
H. proposal-A approval cannot validate proposal-B
I. trace inventory exists before final trace assembly
J. memory-specific permission/approval refs included and tamper-checked
K. actual workflow/permission/approval/memory/result trace tampering rejected
L. exact canonical reference docs remain synchronized
```

The test count may exceed 50.

Do not optimize for a fixed count.

- [ ] **Step 1: Add all V4 attacks**
- [ ] **Step 2: Run full adversarial gate**
- [ ] **Step 3: Ruff / format**
- [ ] **Step 4: Commit**

```bash
git add tests/domains/test_life_plan_domain_closure_adversarial.py
git diff --cached --check
git commit -m "test(life-plan): lock v4 audit regressions"
```

---

# Task 6 — Full V4 Verification and Bundle

## 6.1 Exact module/canon

Required:

```text
LIFE_PLAN_MODULES=14
FROZEN_CANON=13/12/8/10/7
EXACT_CANONICAL_IDS=PASS
```

## 6.2 Focused Life Plan

```bash
.venv/bin/python -m pytest -q tests/domains/test_life_plan_domain_*.py
```

Record exact count.

## 6.3 Adversarial gate

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_closure_adversarial.py
```

Record exact count.

## 6.4 AT-DP-029

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_dp029_acceptance.py
```

Required:

```text
AT_DP_029=PASS
AT_DP_029_CHECKPOINTS=45
```

## 6.5 Direct V3 reproductions

Required test-backed evidence:

```text
V3_B1_FAKE_GATE_REJECTED=PASS
V3_B1_FAKE_RESOLVER_REJECTED=PASS
V3_B1_MISSING_PROVENANCE_REJECTED=PASS

V3_M1_DENIED_MEMORY_PERMISSION_CANNOT_ALLOW_PROPOSE=PASS
V3_M1_MEMORY_PERMISSION_OUTCOME_BOUND=PASS

V3_M2_TRACE_INVENTORY_PREASSEMBLY=PASS
V3_M2_TRACE_INVENTORY_INDEPENDENT=PASS
V3_M2_MEMORY_LIFECYCLE_TRACED=PASS

V3_m1_DOCUMENTATION_STATUS=PASS
```

## 6.6 Domain suite

```bash
.venv/bin/python -m pytest -q tests/domains
```

Record exact count.

## 6.7 Global suite

```bash
.venv/bin/python -m pytest -q
```

Record exact authoritative count.

## 6.8 Ruff / format

```bash
.venv/bin/python -m ruff check \
  cmm/domains/life_plan \
  tests/domains/test_life_plan_domain_*.py

.venv/bin/python -m ruff format --check \
  cmm/domains/life_plan \
  tests/domains/test_life_plan_domain_*.py
```

Run repo-wide Ruff if that remains the established Phase 10 gate.

## 6.9 Compile / fresh import

```bash
.venv/bin/python -m compileall -q cmm tests

.venv/bin/python - <<'PY'
import cmm.domains.life_plan
print("LIFE_PLAN_FRESH_IMPORT=PASS")
PY
```

## 6.10 Final tracked tree

```bash
git diff --check
git diff --cached --check
git status --short --branch
git log -14 --oneline --decorate
```

No tracked/staged changes before bundling.

## 6.11 Generate V4

```bash
git archive \
  --format=tar.gz \
  --output=phase-10.29-audit-v4.tar.gz \
  HEAD
```

Verify required files and reject:

```text
.git
.venv
.env
.tokensave
.worktrees
audit-v*.tar.gz
```

Then:

```bash
shasum -a 256 phase-10.29-audit-v4.tar.gz
ls -lh phase-10.29-audit-v4.tar.gz
git status --short --branch
```

Bundle remains untracked.

STOP after bundle generation.

---

# Expected Commit Sequence

```text
fix(life-plan): require canonical authorization services
test(life-plan): bind memory evidence to real permission outcome
test(life-plan): build trace inventory before assembly
docs(life-plan): record v4 pending remediation status
test(life-plan): lock v4 audit regressions
```

A final verification-gap commit is allowed only if the full verification matrix exposes a genuine defect.

---

# Required V4 Candidate Status

```text
PHASE10_29_REMEDIATION_V3=COMPLETE
INDEPENDENT_REAUDIT_V3=FAIL

V3_BLOCKERS_REMEDIATED=1
V3_MAJORS_REMEDIATED=2
V3_MINORS_REMEDIATED=1

AT_DP_029=PASS
AT_DP_029_CHECKPOINTS=45

CLOSURE_ADVERSARIAL_GATE=PASS
CLOSURE_ADVERSARIAL_TESTS=<fresh exact count>

DP_029=REQUIRES_PHASE_INSPECTION
INDEPENDENT_REAUDIT_V4=PENDING

PUSH=NO
MERGE=NO
```

Do not claim independent closure until ChatGPT accepts V4.
