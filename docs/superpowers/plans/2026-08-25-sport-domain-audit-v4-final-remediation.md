# Phase 10.28 — Sport Domain Final Closure Remediation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the next independent audit the final one by eliminating every remaining trust-boundary bypass found across Audit V1 through Re-Audit V4 and embedding the auditor's adversarial cases into the repository as a permanent closure gate.

**Architecture:** Trust is service-owned, not type-owned. Health authorization must be revalidated against the canonical permission resolver/gate using the original request context; calendar approval must be verified from records owned by `ApprovalService`; trace inventory must be assembled independently using the established hardened Languages pattern. A dedicated closure-adversarial test reproduces every exploit found by the independent auditor.

**Tech Stack:** Python >=3.10, pytest >=9,<10, Ruff >=0.9,<1, existing CMM OS permission, approval, workflow, trace, memory, resolver and domain contracts.

**Spec:** `docs/roadmap/phase-10-domain-intelligence.md` — Phase 10.28 Sport Domain

**Audit evidence:**
- `docs/audits/phase-10.28-sport-independent-audit-v1.md`
- `docs/audits/phase-10.28-sport-independent-reaudit-v2.md`
- `docs/audits/phase-10.28-sport-independent-reaudit-v3.md`
- `docs/audits/phase-10.28-sport-independent-reaudit-v4.md`

## Global Constraints

- Required branch: `feature/phase-10-domain-intelligence`.
- Re-Audit V4 candidate commit: `94ea379ce2d2ae7018c0566618cd425a43e83eb3`.
- Re-Audit V4 bundle SHA-256: `1432871f4d68086bfc1d274f7a59e28c131c1836aa41527aaf774f7c47f3164b`.
- Preserve exact 14 Sport production modules.
- Preserve exact 11 entities / 9 resources / 6 rules / 8 operations / 5 workflows.
- Preserve `domain:sport`, `SportProfile`, version `1.0.0`.
- Preserve `sport.return_to_training_with_health_constraints`.
- Preserve already independently closed gates:
  - Health field minimization;
  - measurement temporal evidence;
  - finite overload evidence;
  - explicit non-commensurate constraint semantics;
  - memory fail-closed;
  - workflow-runtime authoritative output;
  - DP-028 audit-pending status.
- No push.
- No merge.
- No Phase 10.29+ changes.
- Do not close Phase 10.28 inside this remediation.
- No new Sport production modules.
- No private Health implementation imports.
- No new permission/approval/workflow/trace runtime.
- Shared production code changes are forbidden unless a RED regression proves a generic shared contract cannot express the required invariant; stop and report before changing shared production code.
- Existing audit bundles and `tmp/` remain untouched/untracked.
- Every exploit listed in Task 1 must have an automated regression test and must be green before final handoff.

---

# Independent Re-Audit V4 Verdict

```text
PHASE10_28=NOT_CLOSED
INDEPENDENT_REAUDIT_V4=FAIL

BLOCKERS=1
MAJORS=2
MINORS=1
```

Open findings:

```text
B1  Health authorization provenance still forgeable
M4  Calendar approval provenance still forgeable
M5B Trace inventory still reads final trace identity
m1  Roadmap overstates closure
```

Already closed and frozen:

```text
M5A WORKFLOW_RUNTIME_EXECUTION_GATE=PASS
```

---

# Closure Principle

The final trust invariant is:

```text
TYPE IDENTITY != PROVENANCE
```

The following are all untrusted if a caller can construct them directly:

```text
CrossDomainPermissionDecision
PermissionGateResult
AuthorizedHealthConstraint
ApprovalRequest
ApprovalDecision
arbitrary IDs
arbitrary booleans
arbitrary mappings
```

Trusted evidence must be verifiably owned by the canonical service/runtime.

---

# Task 0 — Baseline and final-remediation evidence

- [ ] **Step 1: Capture base**

```bash
cd "/Users/chris/CMM OS" || exit 1
set -euo pipefail

test "$(git branch --show-current)" = "feature/phase-10-domain-intelligence"

FINAL_REMEDIATION_BASE="$(git rev-parse HEAD)"
echo "FINAL_REMEDIATION_BASE=$FINAL_REMEDIATION_BASE"

git merge-base --is-ancestor \
  94ea379ce2d2ae7018c0566618cd425a43e83eb3 \
  HEAD

git status --short --branch
git diff --check
```

- [ ] **Step 2: Verify audit V4 report**

Require:

```text
BLOCKERS=1
MAJORS=2
MINORS=1
```

and:

```text
1432871f4d68086bfc1d274f7a59e28c131c1836aa41527aaf774f7c47f3164b
```

- [ ] **Step 3: Fresh baseline**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_sport_domain_*.py

.venv/bin/python -m ruff check \
  cmm/domains/sport \
  tests/domains/test_sport_domain_*.py

git diff --check
```

---

# Task 1 — Add the permanent independent-auditor adversarial gate FIRST

**Files:**
- Create: `tests/domains/test_sport_domain_closure_adversarial.py`

This test file is the decisive closure gate.

It must reproduce every bypass discovered in independent audits V1–V4 without using production helpers to manufacture trusted evidence.

## Required test cases

### Health provenance

- [ ] caller Boolean cannot authorize;
- [ ] raw dict with fake `authorization_reference` cannot authorize;
- [ ] forged dict with `authorization_verified=True` cannot authorize;
- [ ] fake duck-typed object with `allowed=True` cannot authorize;
- [ ] manually constructed `CrossDomainPermissionDecision(ALLOW)` cannot authorize by itself;
- [ ] manually constructed unrelated `PermissionGateResult(ALLOW)` cannot authorize;
- [ ] manually constructed `AuthorizedHealthConstraint` cannot affect load/workout;
- [ ] missing permission source/target/action/scope fails closed;
- [ ] malformed `effective_from` fails closed;
- [ ] malformed `effective_until` fails closed;
- [ ] expired constraint fails closed;
- [ ] future-not-yet-effective constraint fails closed;
- [ ] real resolver/gate-owned Health→Sport request succeeds.

### Calendar provenance

- [ ] bare `has_approval=True` cannot authorize;
- [ ] fake request/decision strings cannot authorize;
- [ ] fake duck-typed `approval_evidence` cannot authorize;
- [ ] manually constructed `ApprovalRequest` + `ApprovalDecision` cannot authorize unless those exact records are owned by `ApprovalService`;
- [ ] manually constructed `PermissionGateResult(APPROVAL_CONSUMED)` cannot authorize without verifiable approval binding;
- [ ] mismatched stored request/decision fails;
- [ ] wrong-scope stored approval fails;
- [ ] correct stored ApprovalService request/decision succeeds.

### Trace independence

- [ ] inventory is built before final trace;
- [ ] no inventory field reads from final trace;
- [ ] expected trace ID is calculated independently;
- [ ] real `DomainResult` pairs with independent expected trace ID;
- [ ] final trace ID equals expected ID;
- [ ] fabricated baseline reference fails;
- [ ] post-construction trace tamper fails.

### Previously closed safety

- [ ] `max_intensity` remains explicit/pending;
- [ ] NaN/Inf overload evidence remains invalid;
- [ ] missing/out-of-order measurement timestamps remain handled correctly;
- [ ] memory validator exception remains fail-closed;
- [ ] workflow authoritative result remains from `DomainWorkflowExecutor`.

## RED requirement

Run the new file **before production changes**:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_sport_domain_closure_adversarial.py
```

Expected: FAIL on the V4-known provenance/trace bypasses.

Record exact failing tests.

Do not proceed without proving RED.

---

# Task 2 — Close B1 permanently: Health trust must be resolver/gate-owned

**Files:**
- Modify: `cmm/domains/sport/rules.py`
- Modify: `cmm/domains/sport/operations.py`
- Modify: `cmm/domains/sport/workflows.py`
- Modify only if required: `cmm/domains/sport/permissions.py`
- Test:
  - `tests/domains/test_sport_domain_closure_adversarial.py`
  - existing Sport Health/cross-domain/rule/operation/workflow tests

## Required architecture

Do not trust an already-created decision/artifact merely because it has the right type.

The production path must receive enough runtime-owned context to revalidate provenance.

Preferred repository-consistent design:

```text
CrossDomainPermissionRequest
+ DomainPermissionResolver / DomainPermissionGate
→ resolve/consume now
→ verify expected Health→Sport scope/action/resource
→ construct internal AuthorizedHealthConstraint
→ operation/workflow use
```

### Strong preference

Make `AuthorizedHealthConstraint` an internal implementation detail:
- do not export it as public supported trust API;
- callers cannot create a valid trusted instance by manually instantiating the dataclass;
- consumers revalidate a provenance token/decision through runtime-owned service state, or the constructor is private/factory-owned with runtime evidence.

A frozen dataclass alone is not non-forgeability.

- [ ] **Step 1: Require original permission request/context**

The adapter must validate the exact request:
- `source_domain == "domain:health"`;
- `target_domain == "domain:sport"`;
- expected capability/action;
- expected Health constraint resource kind;
- actor/session/sensitivity as supported.

- [ ] **Step 2: Re-resolve or gate the request**

Use the actual resolver/gate.

A manually instantiated `CrossDomainPermissionDecision(ALLOW)` passed without a resolver-owned request flow must be useless.

- [ ] **Step 3: Remove standalone permission-result trust**

No direct authorization based solely on:
- `PermissionGateResult`;
- `CrossDomainPermissionDecision`;
- their IDs/metadata/type.

They may be compared against a freshly resolved/gated result, but not trusted alone.

- [ ] **Step 4: Make artifact non-public/non-authoritative by construction**

Operations must not accept arbitrary caller-created `AuthorizedHealthConstraint` as sufficient proof.

Accept a validated adapter result bound to the current runtime request, or revalidate provenance at the operation boundary.

- [ ] **Step 5: Temporal parse failure is invalid**

For `effective_from` / `effective_until`:
- invalid type/string → reject;
- future `effective_from` → reject/not active;
- expired `effective_until` → reject/not active;
- no silent `except ...: pass`.

- [ ] **Step 6: Real path still succeeds**

Construct actual registry/resolver/gate path in tests and prove the authorized minimized constraint affects Sport correctly.

- [ ] **Step 7: Focused GREEN**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_closure_adversarial.py \
  tests/domains/test_sport_domain_rules.py \
  tests/domains/test_sport_domain_cross_domain.py \
  tests/domains/test_sport_domain_operations.py \
  tests/domains/test_sport_domain_workflows.py \
  tests/domains/test_sport_domain_safety.py
```

- [ ] **Step 8: Commit**

```bash
git add -- \
  cmm/domains/sport/rules.py \
  cmm/domains/sport/operations.py \
  cmm/domains/sport/workflows.py \
  cmm/domains/sport/permissions.py \
  tests/domains/test_sport_domain_closure_adversarial.py \
  tests/domains/test_sport_domain_rules.py \
  tests/domains/test_sport_domain_cross_domain.py \
  tests/domains/test_sport_domain_operations.py \
  tests/domains/test_sport_domain_workflows.py \
  tests/domains/test_sport_domain_safety.py

git diff --cached --check
git commit -m "fix(sport): bind Health authorization to runtime provenance"
```

Stage only changed files.

---

# Task 3 — Close M4 permanently: ApprovalService is the only calendar trust root

**Files:**
- Modify: `cmm/domains/sport/operations.py`
- Test:
  - `tests/domains/test_sport_domain_closure_adversarial.py`
  - `tests/domains/test_sport_domain_operations.py`
  - `tests/domains/test_sport_domain_permissions.py`

## Required architecture

Exactly one trusted path:

```text
ApprovalService
→ stored ApprovalRequest
→ stored ApprovalDecision
→ verified request/decision relation
→ APPROVE / APPROVE_WITH_CHANGES
→ expected operation scope
→ current/valid state
→ ready_for_external_execution
```

## Forbidden production fallbacks

Remove any path that authorizes solely from:
- `PermissionGateResult`;
- `ApprovalRequest` object;
- `ApprovalDecision` object;
- matching IDs;
- arbitrary evidence object;
- Boolean.

- [ ] **Step 1: Service ownership test**

A manually created `ApprovalRequest` and `ApprovalDecision` with perfect-looking fields but absent from `ApprovalService` must fail.

- [ ] **Step 2: Stored-record identity/relation**

Use IDs to retrieve canonical stored records from `ApprovalService`; compare the actual stored relation and status.

- [ ] **Step 3: Scope/status validation**

Require the expected scheduling operation.

Wrong scope/state/mismatch → pending.

- [ ] **Step 4: Remove gate-only shortcut**

A standalone `PermissionGateResult(APPROVAL_CONSUMED)` is not sufficient unless it is cross-checked against the underlying stored approval records.

- [ ] **Step 5: GREEN**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_closure_adversarial.py \
  tests/domains/test_sport_domain_operations.py \
  tests/domains/test_sport_domain_permissions.py
```

- [ ] **Step 6: Commit**

```bash
git add -- \
  cmm/domains/sport/operations.py \
  tests/domains/test_sport_domain_closure_adversarial.py \
  tests/domains/test_sport_domain_operations.py \
  tests/domains/test_sport_domain_permissions.py

git diff --cached --check
git commit -m "fix(sport): make ApprovalService the calendar trust root"
```

---

# Task 4 — Close M5-B using the hardened Languages trace pattern exactly

**Files:**
- Modify:
  - `tests/domains/test_sport_domain_trace.py`
  - `tests/domains/test_sport_domain_dp028_acceptance.py`
  - `tests/domains/test_sport_domain_closure_adversarial.py`
- Modify `cmm/domains/sport/trace.py` only if a real production gap is proven.

## Reference

Read the hardened Languages acceptance trace section completely before editing:

```text
tests/domains/test_languages_domain_dp026_acceptance.py
```

Use the repository's established canonical trace-ID construction/probe pattern.

## Required order

```text
runtime objects
→ determine expected trace ID independently
→ construct real DomainResult
→ construct DomainResultTraceReference(expected_trace_id)
→ construct full DomainTraceReferenceInventory
→ assemble final Sport trace
→ assert trace.id == expected_trace_id
→ validate trace against inventory
```

No inventory field may read:
- `trace.id`;
- `trace.domain_results`;
- `trace.all_references()`;
- any other final-trace field.

- [ ] **Step 1: RED closure test asserts construction order**

The adversarial test must detect the old pattern.

- [ ] **Step 2: Implement Languages-equivalent ID precomputation**

Use the canonical trace contract, not a hand-invented hash.

- [ ] **Step 3: Build inventory first**

The final trace object must not exist when inventory references are assembled.

- [ ] **Step 4: Final trace equality + validation**

Assert:
- final trace ID equals independently expected ID;
- validation PASS;
- fabricated baseline ref FAIL;
- post-build tamper FAIL.

- [ ] **Step 5: GREEN**

```bash
.venv/bin/python -m pytest -q \
  tests/domains/test_sport_domain_closure_adversarial.py \
  tests/domains/test_sport_domain_trace.py \
  tests/domains/test_sport_domain_dp028_acceptance.py
```

- [ ] **Step 6: Commit**

```bash
git add -- \
  cmm/domains/sport/trace.py \
  tests/domains/test_sport_domain_trace.py \
  tests/domains/test_sport_domain_dp028_acceptance.py \
  tests/domains/test_sport_domain_closure_adversarial.py

git diff --cached --check
git commit -m "test(sport): make trace inventory fully independent"
```

Stage only changed files.

---

# Task 5 — Full closure-adversarial gate: zero bypasses

**Files:**
- Modify: `tests/domains/test_sport_domain_closure_adversarial.py`
- Modify existing tests only if needed for legitimate API updates.

The dedicated closure test must now be entirely green.

Run it alone:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_sport_domain_closure_adversarial.py
```

Then prove each named gate in test output or a small deterministic verifier:

```text
V1_HEALTH_FIELD_MINIMIZATION=PASS
V1_MEMORY_FAIL_CLOSED=PASS
V1_TEMPORAL_TREND=PASS
V1_FINITE_OVERLOAD=PASS
V1_LOAD_LIMIT_SEMANTICS=PASS

V2_RAW_HEALTH_AUTH_FORGERY=PASS
V2_CALENDAR_ID_FORGERY=PASS
V2_WORKFLOW_RUNTIME=PASS
V2_TRACE_INVENTORY=PASS

V3_BOOLEAN_HEALTH_FORGERY=PASS
V3_FAKE_PERMISSION_OBJECT=PASS
V3_FORGED_HEALTH_ENVELOPE=PASS
V3_TEMPORAL_CURRENTNESS=PASS
V3_FAKE_APPROVAL_EVIDENCE=PASS
V3_FAKE_APPROVAL_OBJECTS=PASS

V4_FORGED_CANONICAL_PERMISSION_DECISION=PASS
V4_UNRELATED_PERMISSION_GATE=PASS
V4_DIRECT_AUTHORIZED_HEALTH_ARTIFACT=PASS
V4_MALFORMED_TEMPORAL_EVIDENCE=PASS
V4_FORGED_CANONICAL_APPROVAL_OBJECTS=PASS
V4_FORGED_APPROVAL_GATE=PASS
V4_TRACE_FULL_INDEPENDENCE=PASS

CLOSURE_ADVERSARIAL_GATE=PASS
```

If any is not PASS, continue remediation. Do not hand off.

- [ ] **Commit closure test**

```bash
git add -- \
  tests/domains/test_sport_domain_closure_adversarial.py \
  cmm/domains/sport \
  tests/domains/test_sport_domain_*.py

git diff --cached --check
git commit -m "test(sport): lock independent audit closure regressions"
```

Inspect staged scope first.

---

# Task 6 — AT-DP-028 final connected verification

Keep exactly 44 checkpoints.

Verify lifecycle:

```text
resolver/profile
→ Sport state
→ runtime-owned Health permission flow
→ minimized current constraint
→ DomainWorkflowExecutor authoritative output
→ schedule proposal
→ ApprovalService-owned approval
→ readiness
→ memory proposal/binding
→ real DomainResult
→ precomputed expected trace ID
→ independent inventory
→ final trace
→ validation
→ registration/rollback
→ General fallback
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_sport_domain_dp028_acceptance.py \
  tests/domains/test_sport_domain_closure_adversarial.py
```

Required:

```text
AT_DP_028=PASS
AT_DP_028_CHECKPOINTS=44
CLOSURE_ADVERSARIAL_GATE=PASS
```

---

# Task 7 — Documentation truthfulness + final verification

**Files:**
- Modify:
  - `docs/reference/sport-domain.md`
  - `docs/reference/domain-intelligence-requirements-matrix.md`
  - `docs/roadmap/phase-10-domain-intelligence.md`
- `ROADMAP.md` only if current convention requires it.

## Status before independent audit

Use:

```text
Phase 10.28 — implemented; final remediation complete; final independent re-audit pending
AT-DP-028 — candidate PASS
DP-028 — REQUIRES_PHASE_INSPECTION
```

For B1/M4/M5-B:

```text
REMEDIATED — pending independent re-audit
```

M5-A may remain independently closed.

Do not write `VERIFIED_EXISTING` yet.

## Fresh verification

```bash
echo "=== CLOSURE ADVERSARIAL ==="
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q \
  tests/domains/test_sport_domain_closure_adversarial.py

echo
echo "=== SPORT ==="
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains/test_sport_domain_*.py

echo
echo "=== DOMAINS ==="
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q tests/domains

echo
echo "=== GLOBAL ==="
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  -p no:cacheprovider -q

echo
echo "=== COMPILE ==="
.venv/bin/python -m compileall -q cmm tests

echo
echo "=== RUFF ==="
.venv/bin/python -m ruff check \
  cmm/domains/sport \
  tests/domains/test_sport_domain_*.py

echo
echo "=== FORMAT ==="
.venv/bin/python -m ruff format --check \
  cmm/domains/sport \
  tests/domains/test_sport_domain_*.py

echo
echo "=== DIFF ==="
git diff --check
```

## Canon verification

Exact:
- 14 production modules;
- 11/9/6/8/5;
- five canonical workflow IDs;
- no private Health imports;
- no parallel infrastructure.

## Documentation commit

```bash
git add -- \
  docs/reference/sport-domain.md \
  docs/reference/domain-intelligence-requirements-matrix.md \
  docs/roadmap/phase-10-domain-intelligence.md \
  ROADMAP.md

git diff --cached --check
git commit -m "docs(sport): prepare final independent closure audit"
```

Stage `ROADMAP.md` only if changed.

---

# Mandatory final agent output

```text
PHASE10_28_FINAL_REMEDIATION=COMPLETE|INCOMPLETE

AUDIT_V4_BLOCKERS_REMAINING=<n>
AUDIT_V4_MAJORS_REMAINING=<n>
AUDIT_V4_MINORS_REMAINING=<n>

CLOSURE_ADVERSARIAL_GATE=PASS|FAIL
CLOSURE_ADVERSARIAL_TESTS=<fresh>

HEALTH_RUNTIME_PROVENANCE_GATE=PASS|FAIL
CALENDAR_SERVICE_PROVENANCE_GATE=PASS|FAIL
TRACE_FULL_INDEPENDENCE_GATE=PASS|FAIL
WORKFLOW_RUNTIME_EXECUTION_GATE=PASS|FAIL
TEMPORAL_HEALTH_CURRENTNESS_GATE=PASS|FAIL

AT_DP_028=PASS|FAIL
AT_DP_028_CHECKPOINTS=44

SPORT_TESTS=<fresh>
DOMAIN_TESTS=<fresh>
GLOBAL_TESTS=<fresh>

SPORT_RUFF=PASS|FAIL
SPORT_FORMAT=PASS|FAIL
COMPILE=PASS|FAIL
DIFF_CHECK=PASS|FAIL

SPORT_MODULES=14
SPORT_CANON=11/9/6/8/5

DP_028=REQUIRES_PHASE_INSPECTION|NOT_READY

FINAL_REMEDIATION_BASE=<sha>
HEAD=<sha>

PUSH=NO
MERGE=NO
NEXT=BUILD_FINAL_REAUDIT_V6_BUNDLE|REMEDIATE
```

Also list:
- exact commits;
- exact changed files;
- every closure-adversarial test name;
- any shared production changes and the specific RED that forced them;
- confirmation prior audit bundles/tmp remain untouched.

Do not build the next bundle automatically.
Do not claim Phase 10.28 closed.
