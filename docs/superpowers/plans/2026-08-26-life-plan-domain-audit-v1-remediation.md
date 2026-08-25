# Phase 10.29 — Life Plan Domain Independent Audit V1 Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remediate every finding from the Phase 10.29 Independent Audit V1, rebuild the permanent adversarial gate and AT-DP-029 around real runtime-owned evidence, and produce a clean `phase-10.29-audit-v2.tar.gz` candidate without changing the frozen Life Plan architecture or canon.

**Architecture:** Preserve the existing 14-module Life Plan Domain Pack and the frozen `13/12/8/10/7` canon. Fix trust and semantic failures at their root: fail-closed decision-state validation, gate-owned cross-domain authorization, a single verified contribution extraction path, structured scenario consistency, strict memory confirmation, runtime-rooted AT-DP-029 evidence, and an adversarial gate that reproduces every V1 bypass.

**Tech Stack:** Python >=3.10, pytest >=9,<10, Ruff >=0.9,<1, existing CMM OS Domain/Permission/Approval/Workflow/Memory/Trace infrastructure.

**Spec:** `docs/superpowers/specs/2026-08-26-life-plan-domain-design.md`

**Implementation plan:** `docs/superpowers/plans/2026-08-26-life-plan-domain-implementation.md`

**Independent Audit V1:** `docs/audits/phase-10.29-life-plan-independent-audit-v1.md`

## Global Constraints

- Required branch: `feature/phase-10-domain-intelligence`.
- Required V1 candidate ancestor: `f8990d5`.
- Preserve the exact Life Plan canon: **14 modules / 13 entities / 12 resources / 8 rules / 10 operations / 7 workflows**.
- Preserve `life_plan.cross_domain_impact_review` as one of the seven canonical workflows.
- Preserve the accepted generic `operation_contracts.py` normalization unless a regression proves it defective.
- Do not redesign shared architecture.
- Do not create Life Plan-specific engines, repositories, planners, permission systems, approval systems, memory stores, trace systems or cross-domain runtimes.
- Trust is runtime/service-owned, not type-owned.
- A caller-created dataclass instance is not trusted evidence merely because its type is canonical.
- Raw IDs and booleans are never authorization/approval evidence.
- `preference != decision`.
- `scenario != decision`.
- `scenario != commitment`.
- `inference != confirmed fact`.
- Unknown decision states fail closed.
- `is_confirmed` must be strict boolean evidence.
- Cross-domain contribution acceptance must be identical whether supplied directly or wrapped.
- AT-DP-029 must carry actual runtime artifacts into memory/trace evidence where shared contracts support them.
- The trace inventory must be built independently from the final trace.
- Do not weaken tests to make them green.
- Do not mark DP-029 `VERIFIED_EXISTING`.
- Do not mark Phase 10.29 independently audited or closed.
- Do not push.
- Do not merge.
- Do not begin Phase 10.30.
- Create the next audit bundle only from committed HEAD using `git archive`.

---

# V1 Finding Map

```text
B1  DecisionStatusRule fails open for inference and unknown states.
B2  Caller-constructed PermissionGateResult can authorize cross-domain impact.
B3  Wrapped unverified AuthorizedCrossDomainContribution is accepted.

M1  ScenarioConsistencyRule relies on caller-supplied final contradictions.
M2  Memory confirmation uses truthiness instead of strict bool.
M3  AT-DP-029 synthesizes memory/approval/trace evidence instead of carrying runtime evidence.
M4  24-test adversarial gate does not cover the frozen attack surface.

m1  Public name for life_plan.cross_domain_impact_review is not Major Decision Support.
```

The V1 audit accepted the generic shared `operation_contracts.py` `- -> _` normalization. Do not revert it.

---

# Task 0 — Remediation Preflight

**Files:** none.

**Consumes:** committed V1 implementation candidate and committed audit/plan documents.

**Produces:** verified remediation baseline.

- [ ] **Step 1: Verify branch and ancestors**

```bash
cd "/Users/chris/CMM OS"

test "$(git branch --show-current)" = "feature/phase-10-domain-intelligence"
git merge-base --is-ancestor f8990d5 HEAD
git merge-base --is-ancestor 3f92b25 HEAD

git log -6 --oneline --decorate
git status --short --branch
```

Expected:
- correct branch;
- `f8990d5` and `3f92b25` are ancestors;
- no unexpected tracked/staged changes;
- old audit bundles may remain untracked.

- [ ] **Step 2: Verify audit and remediation plan are versioned**

```bash
test -f docs/audits/phase-10.29-life-plan-independent-audit-v1.md
test -f docs/superpowers/plans/2026-08-26-life-plan-domain-audit-v1-remediation.md

rg -n \
  'BLOCKERS=3|MAJORS=4|MINORS=1|B1|B2|B3|M1|M2|M3|M4' \
  docs/audits/phase-10.29-life-plan-independent-audit-v1.md
```

Do not commit in Task 0.

---

# Task 1 — Close B1: Decision-State Vocabulary Must Fail Closed

**Files:**
- Modify: `cmm/domains/life_plan/rules.py`
- Modify: `tests/domains/test_life_plan_domain_rules.py`
- Modify: `tests/domains/test_life_plan_domain_safety.py`
- Modify: `tests/domains/test_life_plan_domain_closure_adversarial.py`

**Interfaces:**
- Consumes: `evaluate_decision_status(...)`.
- Produces: canonical status validation and explicit promotion rules.

## Required canonical states

```text
idea
preference
goal
scenario
decision
commitment
```

Non-decision epistemic labels such as:

```text
inference
hypothesis
confirmed_fact
nonsense
unknown arbitrary strings
```

must not be silently accepted as valid decision-lattice states.

- [ ] **Step 1: Add RED regressions reproducing V1**

Add direct tests equivalent to:

```python
def test_inference_cannot_become_decision_without_confirmation():
    result = evaluate_decision_status(
        current_status="inference",
        proposed_status="decision",
        confirmation_evidence=None,
    )
    assert result["allowed"] is False
```

```python
def test_inference_cannot_become_commitment_without_confirmation():
    result = evaluate_decision_status(
        current_status="inference",
        proposed_status="commitment",
        confirmation_evidence=None,
    )
    assert result["allowed"] is False
```

```python
def test_unknown_current_status_fails_closed():
    result = evaluate_decision_status(
        current_status="nonsense",
        proposed_status="decision",
        confirmation_evidence=None,
    )
    assert result["allowed"] is False
```

```python
def test_unknown_proposed_status_fails_closed():
    result = evaluate_decision_status(
        current_status="idea",
        proposed_status="confirmed_fact",
        confirmation_evidence=None,
    )
    assert result["allowed"] is False
```

Use the actual result type/keys already exposed by the candidate.

- [ ] **Step 2: Verify RED reason**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_rules.py \
  tests/domains/test_life_plan_domain_safety.py \
  -k 'inference or unknown or status'
```

Expected: the V1 reproductions fail for the current implementation.

- [ ] **Step 3: Implement canonical validation**

Inside `rules.py`, introduce one canonical immutable set/tuple:

```python
LIFE_PLAN_DECISION_STATUSES = (
    "idea",
    "preference",
    "goal",
    "scenario",
    "decision",
    "commitment",
)
```

or the closest existing canonical constant style.

`evaluate_decision_status(...)` must:
1. validate current/proposed state;
2. fail closed for any noncanonical state;
3. require valid explicit confirmation for any promotion into `decision` or `commitment` from a nonconfirmed precursor;
4. preserve closed-decision reopening protections.

Do not broaden the public decision vocabulary.

- [ ] **Step 4: Add direct adversarial coverage**

Permanent gate must include:
- inference -> decision;
- inference -> commitment;
- unknown current state;
- unknown proposed state;
- scenario -> decision;
- scenario -> commitment.

- [ ] **Step 5: Verify**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_rules.py \
  tests/domains/test_life_plan_domain_safety.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -- \
  cmm/domains/life_plan/rules.py \
  tests/domains/test_life_plan_domain_rules.py \
  tests/domains/test_life_plan_domain_safety.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py

git diff --cached --check
git commit -m "fix(life-plan): fail closed on decision state promotions"
```

---

# Task 2 — Close B2: Cross-Domain Authorization Must Be Gate-Owned

**Files:**
- Modify: `cmm/domains/life_plan/rules.py`
- Modify: `tests/domains/test_life_plan_domain_cross_domain.py`
- Modify: `tests/domains/test_life_plan_domain_closure_adversarial.py`

**Interfaces:**
- Consumes:
  - `CrossDomainPermissionRequest`;
  - `DomainPermissionGate`;
  - current `PermissionGateResult`.
- Produces: cross-domain evaluation whose trust root is the canonical gate/service, not a supplied result object.

- [ ] **Step 1: Add exact V1 forged-result reproduction**

Construct a real `PermissionGateResult` dataclass with:
- allowed outcome;
- plausible decision ID;
- wrong/unrelated domain;
- attacker actor/session;
- plausible-looking metadata.

Pass a gate object whose real evaluation would deny/raise if invoked.

The current candidate must fail this RED test because it trusts the object.

- [ ] **Step 2: Add binding mismatch regressions**

Cover at minimum:
- wrong `source_domain`;
- wrong `target_domain`;
- wrong actor;
- wrong session;
- wrong capability;
- wrong resource/purpose;
- stale/invalid temporal authorization if supported by current contracts.

- [ ] **Step 3: Implement gate-owned validation**

Preferred implementation:

```text
exact CrossDomainPermissionRequest
→ DomainPermissionGate.evaluate_cross_domain(...)
→ fresh gate-owned PermissionGateResult
→ evaluate contribution
```

Do not accept a caller-supplied `PermissionGateResult` as authoritative merely because it is canonical type.

If compatibility requires accepting such an argument, treat it as non-authoritative metadata unless independently revalidated through the canonical gate/service against the exact request.

- [ ] **Step 4: Verify purpose minimization remains intact**

Valid gate-owned Health contribution still applies only the whitelisted planning projection.

Unrelated dossier fields remain rejected.

- [ ] **Step 5: Verify**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_cross_domain.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py \
  -k 'permission or authorization or cross_domain or forged'
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -- \
  cmm/domains/life_plan/rules.py \
  tests/domains/test_life_plan_domain_cross_domain.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py

git diff --cached --check
git commit -m "fix(life-plan): bind cross-domain authorization to gate runtime"
```

---

# Task 3 — Close B3: One Verified Contribution Extraction Path

**Files:**
- Modify: `cmm/domains/life_plan/workflows.py`
- Modify: `tests/domains/test_life_plan_domain_workflows.py`
- Modify: `tests/domains/test_life_plan_domain_cross_domain.py`
- Modify: `tests/domains/test_life_plan_domain_closure_adversarial.py`

**Interfaces:**
- Consumes: `AuthorizedCrossDomainContribution`.
- Produces: identical trust checks for direct and wrapped contribution forms.

- [ ] **Step 1: Add exact wrapped-artifact V1 reproduction**

Construct a normal caller-created:

```python
AuthorizedCrossDomainContribution(
    projection={"financial_impact": 999999, "status": "active"},
    permission_decision_id="fake-dec",
    permission_request_id="fake-req",
    source_domain="domain:health",
    target_domain="domain:life-plan",
)
```

Assert:

```python
getattr(forged, "_is_verified", False) is False
```

Then pass:

```python
{"authorized_artifact": forged}
```

to `execute_cross_domain_impact_workflow(...)`.

Current candidate should incorrectly apply it; remediation must reject it.

- [ ] **Step 2: Create one internal extraction validator**

Use one function for direct and mapping-wrapped contributions, e.g.:

```python
def _extract_verified_authorized_contribution(value: object) -> AuthorizedCrossDomainContribution | None:
    ...
```

It must require at least:
- canonical type;
- `_is_verified is True`;
- correct target `domain:life-plan`;
- valid non-empty request/decision identifiers;
- current temporal validity where represented;
- minimized projection.

Do not duplicate the checks in two branches.

- [ ] **Step 3: Add valid control cases**

Prove a runtime-created verified artifact succeeds:
- directly;
- wrapped in the supported mapping form.

- [ ] **Step 4: Verify**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_workflows.py \
  tests/domains/test_life_plan_domain_cross_domain.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -- \
  cmm/domains/life_plan/workflows.py \
  tests/domains/test_life_plan_domain_workflows.py \
  tests/domains/test_life_plan_domain_cross_domain.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py

git diff --cached --check
git commit -m "fix(life-plan): reject unverified wrapped contributions"
```

---

# Task 4 — Close M1: Scenario Consistency Must Compute Structured Conflicts

**Files:**
- Modify: `cmm/domains/life_plan/rules.py`
- Modify: `tests/domains/test_life_plan_domain_rules.py`
- Modify: `tests/domains/test_life_plan_domain_closure_adversarial.py`

**Interfaces:**
- Consumes structured scenario relations, milestones and constraint/resource evidence.
- Produces computed consistency status.

Do not implement natural-language world knowledge.

- [ ] **Step 1: Define structured consistency input**

Reuse existing arguments where possible. If the candidate currently accepts `assumptions`, `milestones`, `contradictions`, reinterpret `contradictions` as structured conflict evidence only if it is not already the final answer.

Preferred structures include:

```python
assumption_conflicts=[
    ("residence:madrid", "residence:tokyo"),
]
```

or repository-compatible mappings such as:

```python
{
    "left_id": "assumption:a",
    "right_id": "assumption:b",
    "relation": "mutually_exclusive",
}
```

The rule must determine final `consistent`/`conflicts` itself.

- [ ] **Step 2: RED milestone dependency inconsistency**

Use a milestone whose dependency occurs after the dependent milestone.

The scenario consistency evaluator must incorporate/reuse `evaluate_long_term_temporal(...)` and return inconsistent.

- [ ] **Step 3: RED explicit assumption conflicts**

Supply structured mutually exclusive relations but no final contradiction list.

The rule must compute conflict output.

- [ ] **Step 4: RED unknown evidence**

Unknown assumptions/resources remain uncertain rather than being treated as contradictions or false.

- [ ] **Step 5: Implement GREEN**

`evaluate_scenario_consistency(...)` must combine:
- structured assumption conflicts;
- temporal milestone consistency;
- supplied structured constraint/resource incompatibilities;
- uncertainty.

It must not require the caller to provide the final contradiction strings.

- [ ] **Step 6: Verify + commit**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_rules.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py \
  -k 'scenario or consistency or milestone'

git add -- \
  cmm/domains/life_plan/rules.py \
  tests/domains/test_life_plan_domain_rules.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py

git diff --cached --check
git commit -m "fix(life-plan): compute structured scenario consistency"
```

---

# Task 5 — Close M2: Strict Memory Confirmation

**Files:**
- Modify: `cmm/domains/life_plan/memory.py`
- Modify: `tests/domains/test_life_plan_domain_memory.py`
- Modify: `tests/domains/test_life_plan_domain_closure_adversarial.py`

**Interfaces:**
- Consumes Life Plan memory proposal content.
- Produces strict confirmation validation.

- [ ] **Step 1: Add exact V1 RED case**

```python
content = {
    "kind": "decision",
    "status": "decision",
    "original_status": "preference",
    "is_confirmed": "false",
}
```

Must be invalid.

- [ ] **Step 2: Add coercion matrix**

Reject as confirmation evidence:

```python
"false"
"true"
0
1
[]
{}
None
```

where explicit confirmation is required.

Only actual:

```python
True
False
```

are booleans; `False` must not authorize confirmed persistence.

- [ ] **Step 3: Implement strict boolean validation**

Use:

```python
type(value) is bool
```

or the repository's equivalent strict boolean contract.

Do not use generic truthiness.

- [ ] **Step 4: Preserve nonpromotion semantics**

Scenario/inference/hypothesis/unconfirmed decision remain non-confirmed memory states.

- [ ] **Step 5: Verify + commit**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_memory.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py \
  -k 'memory or confirm'

git add -- \
  cmm/domains/life_plan/memory.py \
  tests/domains/test_life_plan_domain_memory.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py

git diff --cached --check
git commit -m "fix(life-plan): require strict memory confirmation"
```

---

# Task 6 — Close M4 First: Rebuild the Permanent Adversarial Gate

**Files:**
- Rewrite/modify: `tests/domains/test_life_plan_domain_closure_adversarial.py`
- Modify production only when a RED reproduction exposes a genuine defect.

**Interfaces:**
- Produces permanent independent-auditor-style regressions.
- Must cover every V1 bypass and every frozen trust class.

## Required attack coverage

The V2 gate must contain tests covering all of:

```text
01 preference -> decision rejected without confirmation
02 scenario -> decision rejected without confirmation
03 scenario -> commitment rejected without confirmation
04 inference -> decision/confirmed status rejected
05 unknown current decision state rejected
06 unknown proposed decision state rejected
07 closed decision reopening rejected without new evidence
08 alternative route does not imply abandonment
09 missing resource evidence remains unknown
10 malformed numeric resource evidence fails closed
11 raw cross-domain mapping rejected
12 arbitrary authorization ID rejected
13 caller authorization boolean rejected
14 real forged PermissionGateResult rejected
15 permission source/target/actor/session/purpose mismatch rejected
16 most-restrictive permission wins
17 purpose minimization rejects unrelated dossier fields
18 manually constructed direct AuthorizedCrossDomainContribution rejected
19 manually constructed wrapped AuthorizedCrossDomainContribution rejected
20 automatic goal abandonment impossible
21 external commitment without canonical approval rejected
22 forged approval ID/object rejected
23 payment/spend without approved external path rejected
24 strict memory confirmation coercions rejected
25 memory cannot promote inference/scenario to confirmed state
26 trace inventory independent from final trace
27 trace tamper/orphan/wrong-domain references rejected
28 atomic registration rollback preserves exact state
29 General fallback remains intact after failed registration
30 workflow public name is Major Decision Support
```

The gate may contain **30 or more** top-level tests.

Do not preserve an artificial 24 count at the expense of attack coverage.

Documentation/status must use the fresh exact count.

- [ ] **Step 1: Remove benign filler from the old 24-count contract**

Positive success cases belong in focused tests, not as replacements for adversarial attack classes.

- [ ] **Step 2: Add all missing V1 attacks**

Especially:
- real forged `PermissionGateResult`;
- wrapped contribution forge;
- strict bool coercion;
- trace independence/tamper;
- rollback/fallback;
- most-restrictive permission;
- forged approval.

- [ ] **Step 3: Run adversarial suite in isolation**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_closure_adversarial.py
```

Record exact collected/passed count.

- [ ] **Step 4: Commit**

```bash
git add -- \
  tests/domains/test_life_plan_domain_closure_adversarial.py \
  cmm/domains/life_plan

git diff --cached --check
git commit -m "test(life-plan): rebuild independent audit adversarial gate"
```

Inspect staged scope before committing.

---

# Task 7 — Close M3: Rebuild AT-DP-029 Memory and Trace Evidence

**Files:**
- Modify: `tests/domains/test_life_plan_domain_dp029_acceptance.py`
- Modify: Life Plan production only if the connected runtime exposes a real defect.
- Modify shared production only if a generic missing API is proven and the change is small/architecture-preserving.

**Interfaces:**
- Consumes actual runtime outputs from resolver, permission, approval, workflow, memory and trace systems.
- Produces a truly connected 45-checkpoint candidate acceptance.

Keep exactly **45 semantic checkpoints** unless the frozen spec itself must change. The evidence behind checkpoints may be strengthened without increasing the semantic count.

## Required correction

The current AT must stop reinterpreting:
- a Health cross-domain permission decision as a Life Plan memory permission;
- a cross-domain approval request/decision as memory-proposal approval;
- synthetic trace IDs as substitutes for actual runtime evidence.

- [ ] **Step 1: Identify canonical memory permission/approval path**

Read the shared memory contracts/validators and sibling Languages/Sport hardened ATs completely.

Find the actual repository-supported way to produce:
- memory proposal permission evidence;
- memory approval evidence scoped to the memory proposal;
- memory binding evidence.

Do not synthesize snapshots from unrelated permission/approval lifecycles.

- [ ] **Step 2: RED current reinterpretation**

Add focused assertion(s) proving cross-domain approval/permission evidence cannot be rebound to an unrelated memory proposal without exact scope matching.

- [ ] **Step 3: Produce real memory evidence**

Use the canonical shared path to create:
- Life Plan memory proposal;
- correct permission evidence;
- correct approval evidence if required;
- memory view/binding;
- successful shared validation.

- [ ] **Step 4: Build trace references from actual runtime artifacts**

Include supported references for actual run objects, including where available:

```text
DOMAIN_RESULT
PROFILE
RESOLUTION_CONTEXT
RESOLUTION_RESULT
COMPOSITION
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

Do not invent a reference merely to satisfy a count. Use only actual artifacts from the AT run.

- [ ] **Step 5: Build independent inventory before final trace**

Correct order:

```text
runtime artifacts
→ independent inventory
→ final trace
→ validate against inventory
```

Do not create a probe trace just to predict the final trace ID unless the shared trace contract absolutely requires it. Prefer deriving deterministic IDs through the shared canonical ID function if one exists.

- [ ] **Step 6: Add tamper controls**

Within focused/AT evidence, prove:
- orphan workflow ID fails;
- permission decision mismatch fails;
- memory proposal/binding mismatch fails;
- wrong supporting domain fails;
- final trace mutation fails validation.

- [ ] **Step 7: Preserve exact 45 checkpoints**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_dp029_acceptance.py
```

and verify the semantic checkpoint count is exactly 45.

- [ ] **Step 8: Re-run adversarial gate**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_closure_adversarial.py
```

Both must pass.

- [ ] **Step 9: Commit**

```bash
git add -- \
  tests/domains/test_life_plan_domain_dp029_acceptance.py \
  tests/domains/test_life_plan_domain_closure_adversarial.py \
  cmm/domains/life_plan

git diff --cached --check
git commit -m "test(life-plan): harden AT-DP-029 runtime evidence"
```

Add shared files only if a proven generic fix was required.

---

# Task 8 — Close m1 and Update Candidate Documentation

**Files:**
- Modify: `cmm/domains/life_plan/workflows.py`
- Modify: `tests/domains/test_life_plan_domain_workflows.py`
- Modify: `docs/reference/life-plan-domain.md`
- Modify: `docs/reference/domain-intelligence-requirements-matrix.md`
- Modify: `docs/roadmap/phase-10-domain-intelligence.md`

**Interfaces:**
- Produces exact public workflow name and audit-pending remediation status.

- [ ] **Step 1: Fix workflow display name**

Required:

```text
life_plan.cross_domain_impact_review
-> Major Decision Support
```

Assert exact `DomainWorkflowDefinition.name`.

- [ ] **Step 2: Update docs to V1-remediated candidate status**

Use wording equivalent to:

```text
Phase 10.29 — implemented; Independent Audit V1 findings remediated; V2 re-audit pending.
AT-DP-029 — candidate PASS (45 connected checkpoints).
Closure adversarial gate — PASS (<fresh exact count> tests).
DP-029 — REQUIRES_PHASE_INSPECTION.
Independent Audit V1 — FAIL (3 BLOCKER + 4 MAJOR + 1 MINOR).
```

Do not mark findings independently closed. They are:

```text
REMEDIATED — pending independent V2 re-audit
```

- [ ] **Step 3: Verify no premature closure**

```bash
rg -n \
  'DP-029.*VERIFIED_EXISTING|Phase 10\.29.*Complete.*independently audited|FINAL_INDEPENDENT_CLOSURE_AUDIT=PASS' \
  docs/reference/life-plan-domain.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/roadmap/phase-10-domain-intelligence.md || true
```

Expected: no 10.29 closure claim.

- [ ] **Step 4: Verify + commit**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_workflows.py

git add -- \
  cmm/domains/life_plan/workflows.py \
  tests/domains/test_life_plan_domain_workflows.py \
  docs/reference/life-plan-domain.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/roadmap/phase-10-domain-intelligence.md

git diff --cached --check
git commit -m "docs(life-plan): prepare independent audit v2 candidate"
```

---

# Task 9 — Full V2 Verification

**Files:** no intended changes.

- [ ] **Step 1: Exact package/canon**

```bash
test "$(find cmm/domains/life_plan -maxdepth 1 -type f -name '*.py' | wc -l | tr -d ' ')" = "14"

.venv/bin/python - <<'PY'
from cmm.domains.life_plan.catalog import (
    LIFE_PLAN_ENTITY_IDS,
    LIFE_PLAN_RESOURCE_IDS,
    LIFE_PLAN_RULE_IDS,
    LIFE_PLAN_OPERATION_IDS,
    LIFE_PLAN_WORKFLOW_IDS,
)

assert len(LIFE_PLAN_ENTITY_IDS) == 13
assert len(LIFE_PLAN_RESOURCE_IDS) == 12
assert len(LIFE_PLAN_RULE_IDS) == 8
assert len(LIFE_PLAN_OPERATION_IDS) == 10
assert len(LIFE_PLAN_WORKFLOW_IDS) == 7
assert "life_plan.cross_domain_impact_review" in LIFE_PLAN_WORKFLOW_IDS
print("LIFE_PLAN_CANON=13/12/8/10/7")
PY
```

- [ ] **Step 2: Focused Life Plan**

```bash
.venv/bin/python -m pytest -q tests/domains/test_life_plan_domain_*.py
```

Record exact PASS count.

- [ ] **Step 3: Adversarial gate**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_closure_adversarial.py
```

Record exact PASS count. It must cover all Task 6 attack classes.

- [ ] **Step 4: AT-DP-029**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_life_plan_domain_dp029_acceptance.py
```

Expected: PASS, exactly 45 semantic checkpoints.

- [ ] **Step 5: Domain suite**

```bash
.venv/bin/python -m pytest -q tests/domains
```

Record exact PASS count.

- [ ] **Step 6: Global suite**

```bash
.venv/bin/python -m pytest -q
```

A final V2 candidate must report the authoritative global result. Do not omit it.

- [ ] **Step 7: Ruff / format**

```bash
.venv/bin/python -m ruff check \
  cmm/domains/life_plan \
  tests/domains/test_life_plan_domain_*.py

.venv/bin/python -m ruff format --check \
  cmm/domains/life_plan \
  tests/domains/test_life_plan_domain_*.py
```

Run repository-wide Ruff if the repository Phase 10 gate requires it.

- [ ] **Step 8: Compile / import**

```bash
.venv/bin/python -m compileall -q \
  cmm/domains/life_plan \
  tests/domains

.venv/bin/python - <<'PY'
import cmm.domains.life_plan
print("LIFE_PLAN_FRESH_IMPORT=PASS")
PY
```

- [ ] **Step 9: V1 reproduction scan**

Run focused test selections that directly exercise:
- inference promotion;
- forged permission result;
- wrapped forged contribution;
- scenario consistency;
- strict memory bool;
- trace runtime evidence;
- workflow display name.

All must be green.

- [ ] **Step 10: Diff/status**

```bash
git diff --check
git diff --cached --check
git status --short --branch
git log -12 --oneline --decorate
```

No tracked changes may remain before bundling.

---

# Task 10 — Build V2 Audit Bundle

**Files:** no tracked modifications.

- [ ] **Step 1: Capture committed candidate**

```bash
CANDIDATE_HEAD="$(git rev-parse HEAD)"
echo "CANDIDATE_HEAD=$CANDIDATE_HEAD"
git status --short --branch
```

No tracked/staged changes.

- [ ] **Step 2: Create bundle**

```bash
git archive \
  --format=tar.gz \
  --output=phase-10.29-audit-v2.tar.gz \
  HEAD
```

- [ ] **Step 3: Verify bundle contents**

```bash
tar -tzf phase-10.29-audit-v2.tar.gz \
  >/tmp/phase-10.29-audit-v2-files.txt

grep -q '^cmm/domains/life_plan/' \
  /tmp/phase-10.29-audit-v2-files.txt

grep -q '^tests/domains/test_life_plan_domain_closure_adversarial.py$' \
  /tmp/phase-10.29-audit-v2-files.txt

grep -q '^tests/domains/test_life_plan_domain_dp029_acceptance.py$' \
  /tmp/phase-10.29-audit-v2-files.txt

grep -q '^docs/audits/phase-10.29-life-plan-independent-audit-v1.md$' \
  /tmp/phase-10.29-audit-v2-files.txt

grep -q '^docs/superpowers/plans/2026-08-26-life-plan-domain-audit-v1-remediation.md$' \
  /tmp/phase-10.29-audit-v2-files.txt

if grep -E \
  '(^|/)(\.env|\.git|\.venv|\.tokensave|\.worktrees|tmp)(/|$)|audit-v[0-9]+\.tar\.gz$' \
  /tmp/phase-10.29-audit-v2-files.txt; then
  echo "ERROR: forbidden audit-bundle content"
  exit 1
fi

shasum -a 256 phase-10.29-audit-v2.tar.gz
ls -lh phase-10.29-audit-v2.tar.gz
```

- [ ] **Step 4: Keep bundle untracked**

```bash
git status --short --branch
```

Do not stage/commit the bundle.

- [ ] **Step 5: Stop**

Deliver `phase-10.29-audit-v2.tar.gz` to ChatGPT for Independent Re-Audit V2.

Do not self-audit or close Phase 10.29.

---

# Required V2 Candidate Status

If every gate passes:

```text
PHASE10_29_REMEDIATION_V1=COMPLETE
INDEPENDENT_AUDIT_V1=FAIL
V1_BLOCKERS_REMEDIATED=3
V1_MAJORS_REMEDIATED=4
V1_MINORS_REMEDIATED=1

AT_DP_029=PASS
AT_DP_029_CHECKPOINTS=45
CLOSURE_ADVERSARIAL_GATE=PASS
CLOSURE_ADVERSARIAL_TESTS=<fresh exact count>

DP_029=REQUIRES_PHASE_INSPECTION
INDEPENDENT_REAUDIT_V2=PENDING

PUSH=NO
MERGE=NO
```

Do not state that V1 findings are independently closed until V2 audit accepts them.

---

# Expected Commit Sequence

```text
fix(life-plan): fail closed on decision state promotions
fix(life-plan): bind cross-domain authorization to gate runtime
fix(life-plan): reject unverified wrapped contributions
fix(life-plan): compute structured scenario consistency
fix(life-plan): require strict memory confirmation
test(life-plan): rebuild independent audit adversarial gate
test(life-plan): harden AT-DP-029 runtime evidence
docs(life-plan): prepare independent audit v2 candidate
```

A final:

```text
fix(life-plan): close v2 pre-audit verification gaps
```

is allowed only if Task 9 exposes a genuine candidate defect.

---

# Final Agent Response Format

```markdown
## Phase 10.29 V1 remediation

Remediated:
- B1 decision-state fail-open
- B2 forged PermissionGateResult trust
- B3 wrapped contribution forge
- M1 structured scenario consistency
- M2 strict memory confirmation
- M3 AT-DP-029 runtime memory/trace evidence
- M4 permanent adversarial gate coverage
- m1 Major Decision Support display name

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

Audit candidate:
- HEAD=<full SHA>
- bundle=phase-10.29-audit-v2.tar.gz
- SHA256=<sha256>

Status:
- PHASE10_29_REMEDIATION_V1=COMPLETE
- INDEPENDENT_AUDIT_V1=FAIL
- V1_BLOCKERS_REMEDIATED=3
- V1_MAJORS_REMEDIATED=4
- V1_MINORS_REMEDIATED=1
- AT_DP_029=PASS
- AT_DP_029_CHECKPOINTS=45
- CLOSURE_ADVERSARIAL_GATE=PASS
- CLOSURE_ADVERSARIAL_TESTS=<fresh exact count>
- DP_029=REQUIRES_PHASE_INSPECTION
- INDEPENDENT_REAUDIT_V2=PENDING
- PUSH=NO
- MERGE=NO
```

If any required gate fails, do not create a V2-ready claim. Report the exact blocker and current HEAD.
