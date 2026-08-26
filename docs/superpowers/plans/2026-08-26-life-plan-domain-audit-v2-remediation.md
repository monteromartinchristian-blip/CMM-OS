# Phase 10.29 — Life Plan Domain Independent Audit V2 Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining Phase 10.29 V2 findings without reopening already-accepted architecture, produce real runtime-owned permission/memory/trace evidence, synchronize canonical documentation, and generate `phase-10.29-audit-v3.tar.gz`.

**Architecture:** Preserve the exact Life Plan Domain Pack and all V2-accepted behavior. Remove caller authority from cross-domain permission results by re-evaluating the exact request through the shared `DomainPermissionGate`; root memory evidence in a memory-specific permission/approval lifecycle; trace the actual connected runtime artifacts; and make documentation exact-ID checked against the frozen catalog.

**Tech Stack:** Python >=3.10, pytest >=9,<10, Ruff >=0.9,<1, existing CMM OS Domain Permission, Approval, Memory and Trace contracts.

**Spec:** `docs/superpowers/specs/2026-08-26-life-plan-domain-design.md`

**Prior plans:**
- `docs/superpowers/plans/2026-08-26-life-plan-domain-implementation.md`
- `docs/superpowers/plans/2026-08-26-life-plan-domain-audit-v1-remediation.md`

**Independent audits:**
- `docs/audits/phase-10.29-life-plan-independent-audit-v1.md`
- `docs/audits/phase-10.29-life-plan-independent-audit-v2.md`

## Global Constraints

- Required branch: `feature/phase-10-domain-intelligence`.
- Required V2 audit ancestor: `68cbe4e`.
- Preserve exactly 14 Life Plan production modules.
- Preserve exact canon: 13 entities / 12 resources / 8 rules / 10 operations / 7 workflows.
- Preserve `life_plan.cross_domain_impact_review` public name `Major Decision Support`.
- Preserve all V2-closed findings:
  - decision-state canonical/fail-closed behavior;
  - structured scenario consistency;
  - strict memory confirmation typing;
  - direct/wrapped unverified contribution rejection;
  - public workflow name.
- Do not create Life Plan-local permission, approval, memory, trace, workflow, repository, planner or engine infrastructure.
- Do not revert accepted shared `operation_contracts.py` hyphen/underscore normalization.
- Do not use a caller-supplied `PermissionGateResult` as authorization evidence.
- A gate-issued decision ID alone is not sufficient proof that a decision belongs to the current request.
- Memory permission/approval evidence must be scoped to the memory lifecycle, not relabeled from Health→Life Plan cross-domain evidence.
- Trace evidence must be built from actual runtime artifacts and inventoried before final trace assembly.
- `docs/reference/life-plan-domain.md` must match the exact frozen IDs, not only counts.
- DP-029 remains `REQUIRES_PHASE_INSPECTION`.
- Do not mark Phase 10.29 closed.
- Do not begin Phase 10.30.
- Do not push.
- Do not merge.
- Generate V3 only from committed HEAD with `git archive`.

---

# V2 Finding Map

```text
V2-B1  BLOCKER — gate-issued decision-ID replay can authorize a forged PermissionGateResult.
V2-M1  MAJOR   — AT-DP-029 reuses cross-domain permission/approval as memory evidence.
V2-M2  MAJOR   — AT-DP-029 trace remains synthetic/reduced instead of runtime-complete.
V2-M3  MAJOR   — docs/reference/life-plan-domain.md contradicts frozen canonical IDs.
```

V1-M4 remains partially open only because the V2 adversarial gate does not exercise V2-B1 or the stronger runtime trace model.

---

# Task 0 — V3 Remediation Preflight

**Files:** none.

**Consumes:** V2 implementation candidate plus committed V2 audit.

**Produces:** verified baseline.

- [ ] **Step 1: Verify branch and audit ancestry**

```bash
cd "/Users/chris/CMM OS"

test "$(git branch --show-current)" = "feature/phase-10-domain-intelligence"
git merge-base --is-ancestor 6ef944e HEAD
git merge-base --is-ancestor 68cbe4e HEAD

git log -6 --oneline --decorate
git status --short --branch
```

Expected:
- `68cbe4e` is current/ancestor;
- no tracked/staged changes;
- unrelated untracked roadmap/spec files and prior audit bundles may remain untouched.

- [ ] **Step 2: Read binding evidence**

Read completely:

```text
docs/audits/phase-10.29-life-plan-independent-audit-v2.md
cmm/domains/permission_gate.py
cmm/domains/permission_contracts.py
cmm/domains/permission_resolution.py
cmm/agent_runtime/approval_service.py
cmm/domains/memory_contracts.py
cmm/domains/memory_validation.py
cmm/domains/trace_contracts.py
cmm/domains/trace_assembler.py
cmm/domains/trace_validation.py
cmm/domains/life_plan/rules.py
cmm/domains/life_plan/memory.py
cmm/domains/life_plan/trace.py
tests/domains/test_life_plan_domain_closure_adversarial.py
tests/domains/test_life_plan_domain_dp029_acceptance.py
```

Do not modify production during Task 0.

---

# Task 1 — Close V2-B1: Remove Caller Authority from PermissionGateResult

**Files:**
- Modify: `cmm/domains/life_plan/rules.py`
- Modify: `tests/domains/test_life_plan_domain_cross_domain.py`
- Modify: `tests/domains/test_life_plan_domain_closure_adversarial.py`

**Interfaces:**
- Consumes:
  - `CrossDomainPermissionRequest`
  - `DomainPermissionGate.evaluate_cross_domain(...)`
  - optional canonical `approval_request_id`
- Produces:
  - fresh gate-owned authorization result for the exact request
  - verified `AuthorizedCrossDomainContribution` only from that fresh result

## Required design decision

Do **not** attempt to prove a caller-supplied `PermissionGateResult` by checking:

```text
decision_id in gate._issued_decision_ids
```

That is insufficient and is the V2 exploit.

When a `permission_gate` and `permission_request` are supplied, authorization must come from:

```python
fresh_result = permission_gate.evaluate_cross_domain(
    permission_request,
    approval_request_id=approval_request_id,
)
```

Use the actual shared signature:

```python
DomainPermissionGate.evaluate_cross_domain(
    request: CrossDomainPermissionRequest | None = None,
    *,
    approval_request_id: str | None = None,
    ...
) -> PermissionGateResult
```

A caller-provided `permission_gate_result` may remain in the signature only for backwards-compatible diagnostics/comparison; it must never be the trust root.

## API change

Add or preserve a keyword-only parameter equivalent to:

```python
approval_request_id: str | None = None
```

on `evaluate_cross_domain_impact(...)`.

If a valid canonical approval is required, pass that request ID into the shared gate.

Do not inspect `ApprovalService` internals from Life Plan.

Do not call private `_approval_service`, `_issued_decision_ids`, or repository internals from Life Plan authorization logic.

- [ ] **Step 1: Add exact V2 replay RED test**

Construct one real gate.

First make it issue a real decision ID for an unrelated request/decision.

Then construct a caller-created `PermissionGateResult` that reuses that legitimate ID but claims:

```text
APPROVAL_CONSUMED
current actor/session
current source/target metadata
granted-looking approval evidence
```

Pass a current `CrossDomainPermissionRequest`.

Assert Life Plan does not accept the supplied result as authority.

The test must fail against the V2 code before remediation.

- [ ] **Step 2: Add "real gate must be called" regression**

Use a spy/wrapper or observable gate behavior so the test proves:

```text
evaluate_cross_domain(...) called for exact current request
```

A forged supplied result must not short-circuit this call.

- [ ] **Step 3: Add valid gate-owned ALLOW control**

Create a policy configuration where the exact request is allowed.

Assert:

```text
applied=True
authorization_verified=True
permission_decision_id == fresh gate result decision_id
```

- [ ] **Step 4: Add valid APPROVAL_REQUIRED → APPROVAL_CONSUMED control**

Use the actual shared `ApprovalService` lifecycle:

```text
gate evaluation -> APPROVAL_REQUIRED
create/obtain canonical approval request
submit approval decision
gate.evaluate_cross_domain(
    exact_request,
    approval_request_id=approval.id,
)
-> APPROVAL_CONSUMED
```

Then assert contribution applies.

Do not manually forge approval evidence.

- [ ] **Step 5: Implement minimal production fix**

Refactor `evaluate_cross_domain_impact(...)` so:

```text
permission_gate + permission_request present
→ fresh gate evaluation is mandatory
→ caller PermissionGateResult ignored as authorization source
→ only fresh result can authorize
```

Fail closed if:
- no gate;
- no typed request;
- fresh result deny;
- approval required but no canonical approval request ID;
- context mismatch.

- [ ] **Step 6: Verify focused tests**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_cross_domain.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py \
  -k 'permission or replay or authorization or approval'
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add -- \
  cmm/domains/life_plan/rules.py \
  tests/domains/test_life_plan_domain_cross_domain.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py

git diff --cached --check
git commit -m "fix(life-plan): require fresh gate-owned authorization"
```

---

# Task 2 — Close V2-M1: Memory-Specific Permission and Approval Evidence

**Files:**
- Modify: `tests/domains/test_life_plan_domain_dp029_acceptance.py`
- Modify: `tests/domains/test_life_plan_domain_closure_adversarial.py`
- Modify Life Plan production only if a focused RED proves a genuine production gap.

**Interfaces:**
- Consumes:
  - `DomainPermissionRequest`
  - `PermissionCapability.MEMORY_WRITE`
  - existing `DomainPermissionResolver`
  - `ApprovalService`
  - `DomainMemoryPermissionDecisionSnapshot`
  - `DomainMemoryApprovalRequestSnapshot`
  - `DomainMemoryApprovalDecisionSnapshot`
- Produces:
  - memory-specific permission resolution
  - memory-specific approval request/decision
  - memory binding referencing only those memory-specific IDs

## Required memory permission lifecycle

Build a **new** `DomainPermissionRequest` for Life Plan memory persistence:

```python
DomainPermissionRequest(
    request_id=<memory permission request id>,
    action=PermissionCapability.MEMORY_WRITE,
    domain_id=LIFE_PLAN_DOMAIN_ID,
    actor_id=<AT actor>,
    session_id=<AT session>,
    resource_id="life_plan.resource.memory_entry",
    purpose="persist-confirmed-life-plan-memory",
    context={"proposal_id": mem_proposal.proposal_id},
)
```

Resolve it through the already configured shared:

```python
DomainPermissionResolver.resolve(...)
```

Use the actual `effective_permissions` result as the authoritative runtime source.

Do not reuse:

```text
consumed_gate.decision_id
cross_approval.id
cross_decision.id
```

from Health→Life Plan access.

## Snapshot provenance

`DomainMemoryPermissionDecisionSnapshot` is a reference-only contract and has no embedded provenance service.

Therefore root its fields in the actual memory permission runtime result and give it a distinct memory-specific identity.

Preferred identity:

```text
memory-permission:<memory-request-id>
```

or another deterministic, clearly memory-scoped ID derived from the memory permission request/result.

Document in the AT that this is a reference snapshot of a real `DomainPermissionResolver` result, not a `PermissionGateResult`.

Do not call it a gate decision if it is not one.

## Required memory approval lifecycle

If the memory proposal requires confirmation:

Create a **new** shared `ApprovalService` request specifically for the proposal.

Its actual stored request must identify the memory proposal through stable fields, e.g.:

```python
metadata={
    "purpose": "life-plan-memory-confirmation",
    "proposal_id": mem_proposal.proposal_id,
    "domain_id": LIFE_PLAN_DOMAIN_ID,
}
```

and/or the strongest existing first-class approval fields supported by the contract.

Submit a real `ApprovalDecision` for that request.

Then snapshot:

```python
DomainMemoryApprovalRequestSnapshot(
    request_id=memory_approval.id,
    proposal_id=mem_proposal.proposal_id,
)

DomainMemoryApprovalDecisionSnapshot(
    decision_id=memory_decision.id,
    request_id=memory_approval.id,
    approved=True,
)
```

The IDs must come from the memory-specific ApprovalService lifecycle.

- [ ] **Step 1: Add negative regression for cross-domain evidence reuse**

Demonstrate that the AT/helper path rejects or does not use:

```text
cross-domain permission ID
cross-domain approval request ID
cross-domain approval decision ID
```

for the memory binding.

- [ ] **Step 2: Build real memory permission resolution**

Assert:

```text
action == MEMORY_WRITE
request_id is memory-specific
domain_id == domain:life-plan
effective decision allows/approval path as expected
```

- [ ] **Step 3: Build real memory approval**

Create and resolve a proposal-specific ApprovalService request.

Assert repository identity:

```text
stored request metadata proposal_id == mem_proposal.proposal_id
decision.request_id == stored request.id
```

- [ ] **Step 4: Build memory snapshots from these real artifacts**

`mem_view`, `mem_binding`, and `DomainMemoryReferenceInventory` must reference only the memory-specific permission/approval IDs.

- [ ] **Step 5: Add mismatch attacks**

At minimum:

```text
cross-domain approval substituted for memory approval -> invalid
approval for proposal A used for proposal B -> invalid
memory permission request for wrong domain -> invalid
memory permission lacking MEMORY_WRITE -> invalid
```

Use existing validators where possible.

- [ ] **Step 6: Preserve AT semantic checkpoint count**

The AT remains exactly:

```text
45 semantic checkpoints
```

Strengthen checkpoint 41/42 internals rather than adding semantic checkpoints.

- [ ] **Step 7: Verify**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_dp029_acceptance.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py \
  -k 'memory or dp029'
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add -- \
  tests/domains/test_life_plan_domain_dp029_acceptance.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py

git diff --cached --check
git commit -m "test(life-plan): root AT memory evidence in its own lifecycle"
```

If a production/shared fix was genuinely required, stage it explicitly and document why.

---

# Task 3 — Close V2-M2: Runtime-Complete Trace Evidence

**Files:**
- Modify: `tests/domains/test_life_plan_domain_dp029_acceptance.py`
- Modify: `tests/domains/test_life_plan_domain_closure_adversarial.py`
- Modify: `cmm/domains/life_plan/trace.py` only if the existing public helper cannot carry already-supported reference kinds.

**Interfaces:**
- Consumes actual runtime artifacts created in AT-DP-029.
- Produces independent reference inventory before final trace assembly.

## Runtime artifacts that must be represented when produced

Build `DomainTraceReference` objects from actual IDs for at least:

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
```

Also preserve the global:

```text
RESOLUTION_CONTEXT
RESOLUTION_RESULT
COMPOSITION
```

references.

If an actual `OPERATION_RESULT` object/ID is produced in the AT, include it too.

Do not invent IDs solely to satisfy reference diversity.

## Required inventory order

The test code must visibly follow:

```text
1. produce runtime artifacts
2. build DomainTraceReference objects from those artifacts
3. build DomainTraceReferenceInventory
4. assemble final trace
5. validate final trace
```

Do not build the inventory by inspecting the assembled final trace.

## Remove reduced probe dependency

Remove the `domain-trace:probe` pattern as the semantic source of evidence.

If the assembler's canonical trace ID requires deterministic precomputation, derive expected identity through the canonical assembler/request path using the **same complete runtime reference set**, not a reduced hand-written probe.

The expected inventory must still be assembled independently from runtime artifacts rather than from the final trace object's reference list.

- [ ] **Step 1: Build a runtime artifact ledger inside AT**

Keep explicit variables for:

```text
workflow run/result IDs
fresh permission decision ID
cross-domain approval request/decision IDs
memory permission snapshot ID
memory approval request/decision IDs
memory proposal ID
memory binding ID
presentation result ID
domain result ID
```

Do not reuse IDs across unrelated artifact kinds.

- [ ] **Step 2: Create complete trace references**

Use:

```python
build_life_plan_trace_reference(...)
```

for Life Plan-scoped references and canonical `DomainTraceReference` where global/supporting-domain semantics require it.

- [ ] **Step 3: Create independent inventory**

Construct `DomainTraceReferenceInventory.references` from that runtime ledger.

The inventory must exist before final trace validation and must not read the final trace to populate itself.

- [ ] **Step 4: Assemble final trace with complete references**

Pass the same independently constructed runtime references into:

```python
assemble_life_plan_trace(...)
```

Use actual:

```text
presentation_result_ids
supporting_domains
cross_domain_results
```

where the runtime generated them.

- [ ] **Step 5: Add real-reference tamper regressions**

At minimum:

```text
replace actual permission decision ID -> invalid
replace actual approval request ID -> invalid
replace actual memory binding ID -> invalid
remove actual workflow result -> invalid
wrong domain on actual supporting reference -> invalid
```

These attacks must operate on the complete runtime evidence model, not the old reduced probe.

- [ ] **Step 6: Rebuild adversarial trace tests**

Update the permanent closure gate so its trace independence/tamper attacks use the stronger model.

- [ ] **Step 7: Verify**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_trace.py \
  tests/domains/test_life_plan_domain_dp029_acceptance.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py \
  -k 'trace or dp029'
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add -- \
  tests/domains/test_life_plan_domain_dp029_acceptance.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py \
  cmm/domains/life_plan/trace.py

git diff --cached --check
git commit -m "test(life-plan): trace connected runtime evidence"
```

If `trace.py` did not require modification, do not stage it.

---

# Task 4 — Close V2-M3: Synchronize Canonical Reference Documentation

**Files:**
- Modify: `docs/reference/life-plan-domain.md`
- Modify: `tests/domains/test_life_plan_domain_catalog.py` or add exact-doc regression in an existing Life Plan test file
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md` only if status text needs update
- Modify: `docs/roadmap/phase-10-domain-intelligence.md` only if status text needs update

**Interfaces:**
- Consumes the frozen catalog/spec.
- Produces exact-ID documentation parity.

## Exact manifest

Required:

```text
manifest:life-plan:1.0.0
```

## Exact entities

```text
life_plan.entity.life_goal
life_plan.entity.milestone
life_plan.entity.scenario
life_plan.entity.dependency
life_plan.entity.constraint
life_plan.entity.risk
life_plan.entity.decision
life_plan.entity.financial_resource
life_plan.entity.career_path
life_plan.entity.education_path
life_plan.entity.housing_goal
life_plan.entity.family_goal
life_plan.entity.timeline
```

## Exact resources

```text
life_plan.resource.life_plan
life_plan.resource.financial_plan
life_plan.resource.academic_plan
life_plan.resource.opposition_plan
life_plan.resource.health_constraints
life_plan.resource.family_plan
life_plan.resource.housing_plan
life_plan.resource.goal
life_plan.resource.decision
life_plan.resource.calendar_event
life_plan.resource.memory_entry
life_plan.resource.user_message
```

## Exact rules

```text
life_plan.rule.goal_dependency
life_plan.rule.scenario_consistency
life_plan.rule.resource_constraint
life_plan.rule.decision_status
life_plan.rule.long_term_temporal
life_plan.rule.alternative_route
life_plan.rule.cross_domain_impact
life_plan.rule.plan_drift
```

## Exact operations

```text
life_plan.build_timeline
life_plan.compare_scenarios
life_plan.review_goals
life_plan.detect_dependencies
life_plan.identify_risks
life_plan.update_plan
life_plan.create_milestones
life_plan.generate_periodic_review
life_plan.evaluate_feasibility
life_plan.track_decisions
```

## Exact workflows

```text
life_plan.life_plan_setup
life_plan.quarterly_life_review
life_plan.scenario_comparison
life_plan.goal_dependency_review
life_plan.cross_domain_impact_review
life_plan.plan_drift_review
life_plan.annual_life_plan_update
```

- [ ] **Step 1: Correct the reference doc**

Replace wrong V2 IDs with the exact frozen lists above.

- [ ] **Step 2: Add exact-ID regression**

The regression must compare the reference document against actual catalog IDs, not just counts.

A valid pattern:

```python
def test_life_plan_reference_doc_contains_exact_catalog_ids():
    text = Path("docs/reference/life-plan-domain.md").read_text()
    for canonical_id in (
        *LIFE_PLAN_ENTITY_IDS,
        *LIFE_PLAN_RESOURCE_IDS,
        *LIFE_PLAN_RULE_IDS,
        *LIFE_PLAN_OPERATION_IDS,
        *LIFE_PLAN_WORKFLOW_IDS,
    ):
        assert canonical_id in text
```

Also explicitly assert V2-wrong IDs are absent:

```text
life_plan.entity.resource_constraint
life_plan.entity.life_domain_state
life_plan.entity.commitment
life_plan.entity.alternative_route
life_plan.entity.plan_drift
life_plan.entity.financial_plan
life_plan.entity.review_record
life_plan.resource.timeline
life_plan.resource.scenario
life_plan.resource.note
life_plan.resource.review_record
manifest:life_plan:1.0.0
```

Prefer parsing the canonical inventory section if the doc format allows exact set comparison.

- [ ] **Step 3: Update V3-pending status**

Use:

```text
Independent Audit V2 — FAIL (1 BLOCKER + 3 MAJOR).
V2 findings remediated — Independent Re-Audit V3 pending.
DP-029 — REQUIRES_PHASE_INSPECTION.
AT-DP-029 — candidate PASS, pending V3 independent acceptance.
```

Do not claim closure.

- [ ] **Step 4: Verify**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_catalog.py

git diff --check
```

- [ ] **Step 5: Commit**

```bash
git add -- \
  docs/reference/life-plan-domain.md \
  tests/domains/test_life_plan_domain_catalog.py \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/roadmap/phase-10-domain-intelligence.md

git diff --cached --check
git commit -m "docs(life-plan): restore exact canonical reference"
```

Stage only files actually changed.

---

# Task 5 — Rebuild Final V3 Adversarial Gate

**Files:**
- Modify: `tests/domains/test_life_plan_domain_closure_adversarial.py`

**Interfaces:**
- Produces the final permanent closure gate.

Keep all V2 attack coverage.

Add/strengthen these mandatory V3 attacks:

```text
A. gate-issued decision ID replay with forged PermissionGateResult
B. forged APPROVAL_CONSUMED result cannot bypass fresh gate evaluation
C. cross-domain permission cannot be relabeled as memory permission evidence
D. cross-domain approval cannot be reused for memory proposal
E. memory approval for proposal A cannot validate proposal B
F. runtime-complete trace inventory is independent of final trace
G. tampered actual permission reference fails
H. tampered actual approval reference fails
I. tampered actual memory binding reference fails
J. missing actual workflow result reference fails
K. exact canonical reference documentation IDs remain synchronized
```

The gate count may increase above 33.

Do not optimize for a fixed number.

- [ ] **Step 1: Run V2 gate before additions**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_closure_adversarial.py
```

Record baseline count.

- [ ] **Step 2: Add V3 attacks**

Every attack above must be an executable regression, not a comment.

- [ ] **Step 3: Verify full gate**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_closure_adversarial.py
```

Record fresh exact PASS count.

- [ ] **Step 4: Commit**

```bash
git add tests/domains/test_life_plan_domain_closure_adversarial.py
git diff --cached --check
git commit -m "test(life-plan): lock v3 audit regressions"
```

---

# Task 6 — Full V3 Verification and Bundle

**Files:** no intended production changes.

## 6.1 Canon

```bash
test "$(find cmm/domains/life_plan -maxdepth 1 -type f -name '*.py' | wc -l | tr -d ' ')" = "14"
```

Then verify exact IDs, not only counts, against the frozen spec.

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
PASS
45 semantic checkpoints
```

## 6.5 Direct V2 reproductions

Ensure test-backed PASS for:

```text
V2_B1_GATE_ISSUED_ID_REPLAY_REJECTED
V2_B1_FRESH_GATE_EVALUATION_REQUIRED
V2_M1_MEMORY_PERMISSION_SCOPE=PASS
V2_M1_MEMORY_APPROVAL_SCOPE=PASS
V2_M2_RUNTIME_COMPLETE_TRACE=PASS
V2_M3_EXACT_REFERENCE_DOC_CANON=PASS
```

## 6.6 Domain suite

```bash
.venv/bin/python -m pytest -q tests/domains
```

## 6.7 Global suite

```bash
.venv/bin/python -m pytest -q
```

Report the authoritative exact result.

## 6.8 Ruff / format

```bash
.venv/bin/python -m ruff check \
  cmm/domains/life_plan \
  tests/domains/test_life_plan_domain_*.py

.venv/bin/python -m ruff format --check \
  cmm/domains/life_plan \
  tests/domains/test_life_plan_domain_*.py
```

Run repo-wide Ruff if that remains the Phase 10 established gate.

## 6.9 Compile / fresh import

```bash
.venv/bin/python -m compileall -q cmm tests

.venv/bin/python - <<'PY'
import cmm.domains.life_plan
print("LIFE_PLAN_FRESH_IMPORT=PASS")
PY
```

## 6.10 Tracked tree

```bash
git diff --check
git diff --cached --check
git status --short --branch
git log -12 --oneline --decorate
```

No tracked/staged changes before bundling.

Unrelated pre-existing untracked files must remain untouched.

## 6.11 Create exact V3 bundle

```bash
git archive \
  --format=tar.gz \
  --output=phase-10.29-audit-v3.tar.gz \
  HEAD
```

Verify:

```bash
tar -tzf phase-10.29-audit-v3.tar.gz \
  >/tmp/phase-10.29-audit-v3-files.txt

grep -q '^cmm/domains/life_plan/' \
  /tmp/phase-10.29-audit-v3-files.txt

grep -q '^tests/domains/test_life_plan_domain_closure_adversarial.py$' \
  /tmp/phase-10.29-audit-v3-files.txt

grep -q '^tests/domains/test_life_plan_domain_dp029_acceptance.py$' \
  /tmp/phase-10.29-audit-v3-files.txt

grep -q '^docs/audits/phase-10.29-life-plan-independent-audit-v2.md$' \
  /tmp/phase-10.29-audit-v3-files.txt

grep -q '^docs/superpowers/plans/2026-08-26-life-plan-domain-audit-v2-remediation.md$' \
  /tmp/phase-10.29-audit-v3-files.txt

if grep -E \
  '(^|/)(\.env|\.git|\.venv|\.tokensave|\.worktrees)(/|$)|audit-v[0-9]+\.tar\.gz$' \
  /tmp/phase-10.29-audit-v3-files.txt
then
  echo "ERROR: forbidden bundle content"
  exit 1
fi

shasum -a 256 phase-10.29-audit-v3.tar.gz
ls -lh phase-10.29-audit-v3.tar.gz
git status --short --branch
```

Bundle remains untracked.

STOP after V3 bundle generation.

---

# Expected Commit Sequence

```text
fix(life-plan): require fresh gate-owned authorization
test(life-plan): root AT memory evidence in its own lifecycle
test(life-plan): trace connected runtime evidence
docs(life-plan): restore exact canonical reference
test(life-plan): lock v3 audit regressions
```

A final:

```text
fix(life-plan): close v3 pre-audit verification gaps
```

is allowed only if full verification exposes a genuine defect.

---

# Required V3 Candidate Status

```text
PHASE10_29_REMEDIATION_V2=COMPLETE
INDEPENDENT_REAUDIT_V2=FAIL

V2_BLOCKERS_REMEDIATED=1
V2_MAJORS_REMEDIATED=3
V2_MINORS_REMEDIATED=0

AT_DP_029=PASS
AT_DP_029_CHECKPOINTS=45

CLOSURE_ADVERSARIAL_GATE=PASS
CLOSURE_ADVERSARIAL_TESTS=<fresh exact count>

EXACT_REFERENCE_DOC_CANON=PASS

DP_029=REQUIRES_PHASE_INSPECTION
INDEPENDENT_REAUDIT_V3=PENDING

PUSH=NO
MERGE=NO
```

Do not say independently closed until ChatGPT accepts V3.

---

# Final Agent Response Format

```markdown
## Phase 10.29 V2 remediation

Remediated:
- V2-B1 gate-issued decision-ID replay
- V2-M1 memory-specific permission/approval evidence
- V2-M2 runtime-complete trace evidence
- V2-M3 canonical reference documentation
- V1-M4 remaining adversarial coverage

Direct reproductions:
- V2_B1_GATE_ISSUED_ID_REPLAY_REJECTED=PASS
- V2_B1_FRESH_GATE_EVALUATION_REQUIRED=PASS
- V2_M1_MEMORY_PERMISSION_SCOPE=PASS
- V2_M1_MEMORY_APPROVAL_SCOPE=PASS
- V2_M2_RUNTIME_COMPLETE_TRACE=PASS
- V2_M3_EXACT_REFERENCE_DOC_CANON=PASS

Verification:
- Life Plan focused: <exact count> PASS
- Adversarial gate: <exact count> PASS
- AT-DP-029: PASS — 45 checkpoints
- Domain suite: <exact count> PASS
- Global suite: <exact count> PASS
- Ruff: PASS
- format: PASS
- compileall: PASS
- fresh import: PASS
- diff checks: PASS

Shared code:
- <none, or exact shared files changed + reason>

Audit candidate:
- HEAD=<full SHA>
- bundle=phase-10.29-audit-v3.tar.gz
- SHA256=<sha256>

Status:
- PHASE10_29_REMEDIATION_V2=COMPLETE
- V2_BLOCKERS_REMEDIATED=1
- V2_MAJORS_REMEDIATED=3
- AT_DP_029=PASS
- AT_DP_029_CHECKPOINTS=45
- CLOSURE_ADVERSARIAL_GATE=PASS
- CLOSURE_ADVERSARIAL_TESTS=<fresh exact count>
- EXACT_REFERENCE_DOC_CANON=PASS
- DP_029=REQUIRES_PHASE_INSPECTION
- INDEPENDENT_REAUDIT_V3=PENDING
- PUSH=NO
- MERGE=NO
```
