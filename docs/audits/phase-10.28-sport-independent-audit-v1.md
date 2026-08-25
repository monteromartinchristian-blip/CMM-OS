# Phase 10.28 — Sport Domain — Independent Audit V1

Date: 2026-08-25
Auditor: ChatGPT (independent Phase 10 closure auditor)
Evidence bundle: `phase-10.28-audit-v2.tar.gz`

## Bundle identity

```text
SHA256=3adef2ab6a61e80e9c51bbe3bd343f9f6f4ec198a7f1193b054ca2075e6c8146
SIZE≈3.4MB
SAFE_EXTRACT=PASS
SANITIZATION=PASS
```

The archive contains no `.env`, `.git`, `.venv`, `.worktrees`, `.tokensave`, `tmp/`, or prior/current audit bundles.

## Candidate structure

```text
SPORT_PACKAGE_MODULES=14_EXACT
ENTITIES=11_EXACT
RESOURCES=9_EXACT
RULES=6_EXACT
OPERATIONS=8_EXACT
WORKFLOWS=5_EXACT
COMPILEALL_SPORT=PASS
DIRECT_PRIVATE_HEALTH_IMPORTS=0
PLACEHOLDERS=0
```

The canonical package boundary and inventory are structurally correct.

## Independent test execution note

The auditor attempted:

```text
python -m pytest -p no:cacheprovider -q tests/domains/test_sport_domain_*.py
```

The audit container cannot collect the suite because its environment lacks the declared project dependency `libcst>=1.0`. Network installation is unavailable in the audit environment. This is an auditor-environment limitation and is not counted as a candidate defect.

The candidate's reported `64` Sport tests and `11782` global tests are therefore not independently re-executed here. The audit instead uses direct source inspection, syntax compilation, catalog extraction, and isolated adversarial execution of the exact pure-function bodies from the bundle.

# Verdict

## FAIL — remediation required before Phase 10.28 can close

```text
PHASE10_28=NOT_CLOSED
FINAL_INDEPENDENT_CLOSURE_AUDIT=FAIL
DP_028=NOT_VERIFIED
AT_DP_028=NOT_ACCEPTED_AS_CLOSURE_EVIDENCE

BLOCKERS=2
MAJORS=5
MINORS=1

PUSH=NO
MERGE=NO
NEXT=REMEDIATE_AUDIT_V1
```

# Blocking findings

## B1 — Health → Sport minimization and authorization are not enforced end-to-end

### Evidence

`cmm/domains/sport/rules.py:343-400`

`evaluate_health_constraint()` defines an allowlist in `allowed_fields`, but returns:

```python
"constraint": projection
```

rather than a minimized projection. Therefore extra clinical fields remain available inside the accepted result.

Independent reproduction used:

```python
{
    "constraint_id": "hc",
    "status": "active",
    "activity_limits": ["no_running"],
    "diagnosis": "ACL tear",
    "treatment_plan": "surgery",
    "clinical_notes": "secret",
    "authorization_reference": "auth",
}
```

with `is_authorized=True`, `is_current=True`.

Actual result:

```text
applied=True
constraint still contains diagnosis/treatment_plan/clinical_notes
```

This violates the Phase 10.15 requirement that Sport may receive only the authorized `health_constraint` projection and not the full/surplus Health context.

The boundary is also bypassable through exported operation helpers:

`cmm/domains/sport/operations.py:169-225`

`adjust_training_load_result()` and `generate_workout_result()` accept a raw dictionary and trust `status == "active"` without consuming a canonical cross-domain permission decision, current authorization proof, or sanitized projection.

### Required remediation

- Return a newly built minimized constraint containing only explicitly allowed fields.
- Reject or drop every unrecognized field; sensitive/clinical fields must never survive the boundary.
- Require a canonical sanitized/authorized constraint object or equivalent evidence at operation boundaries.
- Connect the Sport → Health acceptance path to the existing typed `CrossDomainPermissionRequest` / permission resolver/gate contract instead of manually supplying booleans.
- Add adversarial regression tests for arbitrary extra clinical fields.

---

## B2 — Sport memory binding validation fails open

### Evidence

`cmm/domains/sport/memory.py:163-182`

The validator catches every exception:

```python
except Exception:
```

and returns:

```python
DomainMemoryValidationResult(
    is_valid=True,
    code=VALID,
)
```

A validator failure therefore becomes a successful validation result.

This is opposite to the required fail-closed behavior for memory and validation.

The Sport memory tests do not exercise this failure path.

### Required remediation

- Remove the catch-all success fallback.
- Propagate the canonical validator result/error or convert failure into an explicit invalid/error result.
- Add a regression proving malformed inventory/binding or validator failure can never become `VALID`.

# Major findings

## M1 — MeasurementTrendRule does not enforce temporal evidence

### Evidence

`cmm/domains/sport/rules.py:403-478`

The function claims to use “ordered” measurements but:

- does not require timestamps;
- does not validate timestamps;
- does not sort or reject out-of-order timestamps;
- uses input list order for first/last;
- does not verify per-observation metric identity.

Independent reproductions:

```text
unsorted timestamps -> status=evaluated, direction=increasing
missing timestamps  -> status=evaluated, direction=decreasing
```

### Required remediation

Require valid comparable timestamped observations and either deterministically sort them or reject non-monotonic input according to the chosen contract. Preserve provenance and metric identity.

---

## M2 — ProgressiveOverloadRule accepts non-finite decision evidence

### Evidence

`cmm/domains/sport/rules.py:174-255`

Independent reproductions:

```text
proposed_load=NaN     -> status=accepted, certainty=True
proposed_load=Inf     -> status=exceeds_threshold, certainty=True
threshold=NaN         -> status=accepted, certainty=True
```

### Required remediation

Reject Boolean, NaN, Inf and invalid threshold values before calculating or returning a certain decision.

---

## M3 — Health load-limit semantics are replaced by a hard-coded 30% reduction

### Evidence

`cmm/domains/sport/operations.py:179-183`

Any constraint containing `max_intensity` or `reduction_pct` results in:

```python
adjusted = current_load * 0.7
```

Independent reproduction:

```text
current_load=100
reduction_pct=10
actual adjusted_load=70
expected semantics from supplied reduction=90
```

The supplied constraint value is not actually honored.

### Required remediation

Interpret the explicitly authorized constraint value according to the contract. Do not introduce an unrelated fixed reduction.

---

## M4 — Calendar approval is Boolean, not scoped authorization

### Evidence

`cmm/domains/sport/operations.py:296-319`

The public helper accepts only:

```python
has_approval: bool
```

AT-DP-028 checkpoint 36 calls it with `True` and immediately labels the checkpoint “scoped approval preserved”.

No approval ID, scope, operation, resource, expiry, actor, session or permission-gate evidence is preserved.

### Required remediation

Bind scheduling readiness to the shared approval/permission evidence or an explicit scoped approval reference. A bare Boolean must not prove authorization.

---

## M5 — AT-DP-028 is not sufficiently connected to the canonical runtime evidence paths

### Evidence

`tests/domains/test_sport_domain_dp028_acceptance.py`

Important checkpoints are satisfied by direct helper calls and manually asserted state labels rather than by canonical runtime evidence:

- Health permission is represented by `is_authorized=True`, not a typed cross-domain permission decision.
- Calendar approval is represented by `has_approval=True`.
- Trace checkpoint 40 supplies hard-coded caller strings (`req-acceptance-040`, `ctx-040`, etc.) and does not validate them against a `DomainTraceReferenceInventory`.
- The state dictionary records outputs, but many outputs are not consumed by subsequent runtime components.

This does not satisfy the implementation plan's requirement that AT-DP-028 be a connected lifecycle using actual resolver/composer/workflow/permission/memory/trace outputs where supported.

### Required remediation

Harden AT-DP-028 so that the lifecycle carries real objects/references forward:

```text
resolver
→ profile
→ rule/operation
→ typed cross-domain permission request + decision/gate
→ sanitized health_constraint
→ return-to-training workflow
→ scoped approval evidence
→ memory proposal + binding validation
→ trace assembly + inventory validation
→ General fallback
```

Helpers may support the lifecycle, but must not substitute for the shared contracts the checkpoint claims to prove.

# Minor finding

## m1 — DP-028 is marked VERIFIED_EXISTING before independent audit

### Evidence

`docs/reference/domain-intelligence-requirements-matrix.md:146`

The row simultaneously says:

```text
VERIFIED_EXISTING
```

and:

```text
pending independent audit
```

This is internally inconsistent and contradicts the implementation plan's pre-audit status rule.

### Required remediation

During remediation/audit-pending state use the repository-equivalent of:

```text
REQUIRES_PHASE_INSPECTION
```

After a clean independent closure audit, change it to `VERIFIED_EXISTING`.

# Independent adversarial gates

```text
HEALTH_FIELD_MINIMIZATION_GATE=FAIL
TREND_TEMPORAL_EVIDENCE_GATE=FAIL
OVERLOAD_FINITE_EVIDENCE_GATE=FAIL
CONSTRAINT_VALUE_SEMANTICS_GATE=FAIL
SCOPED_CALENDAR_APPROVAL_GATE=FAIL
MEMORY_VALIDATION_FAIL_CLOSED_GATE=FAIL
CONNECTED_CROSS_DOMAIN_ACCEPTANCE_GATE=FAIL
RUNTIME_TRACE_EVIDENCE_GATE=FAIL
PENDING_AUDIT_STATUS_GATE=FAIL

AUDIT_PROBE_TOTAL=9
AUDIT_PROBE_FAILS=9
```

# What already passes

The audit does **not** reject the whole implementation. The following parts are sound enough to preserve:

- exact 14-module Sport package;
- exact 11/9/6/8/5 canonical inventory;
- stable `domain:sport` identity and `SportProfile` binding;
- six declared Sport rules;
- eight declared operations;
- five canonical workflows including `sport.return_to_training_with_health_constraints`;
- no direct private Health implementation imports;
- no parallel Sport planner/runtime/memory store/workflow engine;
- atomic-registration design and rollback mechanism are structurally present;
- General bootstrap/fallback integration is structurally present;
- no audit-bundle secret/local-state contamination;
- Sport source/test syntax compilation succeeds.

# Remediation acceptance criteria

The next candidate is ready for V2 audit only when all of the following are fresh-green:

1. Authorized Health projection contains only permitted fields.
2. Arbitrary clinical extras cannot cross Health → Sport.
3. Sport operations cannot consume an unvetted raw Health dictionary as authorized evidence.
4. Memory validator fails closed.
5. Measurement trends require real temporal/comparable evidence.
6. Progressive overload rejects non-finite evidence.
7. Load adjustment honors actual constraint values.
8. Calendar approval is scoped and referenceable.
9. AT-DP-028 uses the typed cross-domain permission path.
10. AT-DP-028 validates trace references against real inventory/evidence.
11. DP-028 remains audit-pending until independent V2 passes.
12. Focused Sport tests, all domain tests and global suite remain green.
13. Ruff/format/compileall remain green on the changed surface.
14. No unrelated Phase 10.29+ changes.
15. No push or merge.

A fresh audit bundle must be generated after remediation and supplied to the same independent auditor.
