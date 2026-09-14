# Phase 10.34 — Domain Sessions — Independent Audit V4

## Independent Audit V4

**Date:** 2026-08-30
**Auditor:** ChatGPT (independent project auditor)
**Audited phase:** Phase 10.34 — Domain Sessions
**Audited bundle:** `phase-10.34-audit-v4.tar.gz`
**Bundle SHA256:** `2d040d418ba23b4a8d935fcd214f91441e69a605e28e2e0ce3ae90bd8d2b54d6`
**Audited Git HEAD:** `5459214a808d3ea8ac44b7cac7ed8f980a2161d3`

```text
FINAL_INDEPENDENT_AUDIT_V4=FAIL
BLOCKERS=0
MAJORS=3
MINORS=1

DP_034=NOT_VERIFIED
AT_DP_034=FAIL
CLOSURE_ALLOWED=NO

NEXT=PHASE10_34_REMEDIATION_V5
PUSH=NO
MERGE=NO
```

---

## 1. Artifact identity and packaging verification

Independent checks against the uploaded artifact produced:

```text
SHA256=2d040d418ba23b4a8d935fcd214f91441e69a605e28e2e0ce3ae90bd8d2b54d6
ARCHIVE_HEAD=5459214a808d3ea8ac44b7cac7ed8f980a2161d3
ARCHIVE_PREFIX=CMM-OS-phase-10.34/
MEMBERS=1874
FORBIDDEN_GIT_VENV_PYC=0
```

Required Phase 10.34 production, regression, audit-V3, and roadmap files are present.

The V3 packaging-prefix defect is fixed.

---

## 2. Independent execution evidence

The audit environment does not include the repository's `libcst` dependency, so importing the complete top-level `cmm.domains` package through its normal eager initializer cannot reproduce the entire repository suite without changing the audit environment.

This is not counted as a project finding.

Using a package-isolation harness that bypasses eager package initializers while loading the exact audited source files, the following V4 tests executed independently:

```text
tests/domains/test_domain_session_audit_v3_regressions.py
tests/domains/test_domain_session_acceptance.py

80 passed
```

This corresponds to:

- 23 collected V3 regression cases;
- 57 AT-DP-034 acceptance/meta cases.

Targeted compile verification:

```text
COMPILEALL=PASS
```

Independent event-catalog probe:

```text
GENERAL_EVENT_COUNT=23
GENERAL_EVENT_UNIQUE_COUNT=23
DOMAIN_SESSION_RESUMED_PRESENT=NO
```

---

# 3. V3 blockers independently confirmed fixed

## 3.1 BLOCKER-01 — stale explicit snapshot rollback

The auditor independently persisted:

```text
revision=5
next_recommended_step=step:new
```

and attempted resumption with an explicit stale context:

```text
revision=2
next_recommended_step=step:old
```

Observed V4 result:

```text
status=FAILED
previous_revision=5
resumed_revision=5
recorded_resumption=False
blocking_finding=explicit revision does not match authoritative durable revision
```

Durable state after the rejected attempt remained:

```text
revision=5
next_recommended_step=step:new
```

The durable rollback reproduced in V3 is fixed.

The adapter also now checks the domain-session extension revision through `expected_previous_revision` and rejects stale or non-monotonic revision updates.

## 3.2 BLOCKER-02 — workflow/conflict status downgrade

Independent probes produced:

```text
conflict REPLAN_REQUIRED -> REPLAN_REQUIRED, recorded=True
conflict INCOMPATIBLE -> INCOMPATIBLE, recorded=False
conflict WAITING_FOR_USER -> WAITING_FOR_USER, recorded=True

workflow REPLAN_REQUIRED + recomposition -> REPLAN_REQUIRED
workflow WAITING_FOR_USER + recomposition -> WAITING_FOR_USER
workflow WAITING_FOR_APPROVAL + recomposition -> WAITING_FOR_APPROVAL
```

The V3 fail-open status-loss blocker is fixed.

`merge_resume_status()` now centralizes conservative precedence.

---

# 4. V3 MAJOR-03 strict JSON contracts independently confirmed fixed

Independent direct-construction probes using opaque Python objects were rejected for:

```text
DomainSessionContext.metadata
DomainSessionCheck.details
DomainSessionTransition.metadata
DomainSessionResumeRequest.metadata
```

with `DomainSessionContractError`.

The recursive strict JSON validator rejects unsupported objects and non-finite numbers.

This V3 major is fixed.

---

# 5. MAJOR-01 — Synthetic DomainResolutionResult authority still exists

## Requirement carried from Audit V3

Phase 10.34 must not manufacture an authoritative `DomainResolutionResult` merely to satisfy the composer API.

The V3 finding was not about the literal numeric value `1.0` alone. It was about fabricating a resolver result without an authoritative resolver result.

## V4 production evidence

`cmm/domains/session_resumer.py` still creates synthetic objects during recomposition.

If no resolver exists:

```python
res_result = DomainResolutionResult(
    id=last_resolution_id or f"domain-recomposition-{session_id}",
    context_id=f"ctx-recomp-{session_id}",
    status=DomainResolutionStatus.RESOLVED,
    primary_domain=...,
    supporting_domains=...,
    confidence=0.0,
    resolved_at=now_ts,
)
```

It also creates the same synthetic object when a configured resolver fails or returns a non-RESOLVED result.

Changing fabricated confidence from `1.0` to `0.0` does not make the object authoritative.

## Independent reproduction

A recomposition with:

```text
supporting domain disabled
no canonical resolver configured
spy composer configured
```

produced:

```text
final status=RECOMPOSED
composer calls=1
resolution.id=domain-recomposition-s-synth
resolution.status=RESOLVED
resolution.confidence=0.0
resolution.candidate_scores=()
resolution.reasons=()
```

The composer therefore still receives a manufactured `DomainResolutionResult`.

## Test defect

The new regression:

```text
test_no_synthetic_confidence_1_0_composition_authority
```

only rejects fabricated `confidence=1.0`.

A synthetic `confidence=0.0` result passes that test.

## Required remediation

Do not create a `DomainResolutionResult` unless it came from the real resolver or another repository-native authoritative resolution source.

If recomposition does not require re-resolution, use a typed composition reconstruction input that does not impersonate a resolver result, or adapt the composer boundary accordingly.

If the composer contract fundamentally requires a `DomainResolutionResult`, obtain a real authoritative resolution rather than fabricating one.

Add a regression that fails on any synthetic resolver result, regardless of confidence.

---

# 6. MAJOR-02 — Native resource/temporal/provenance authority is still not integrated

Audit V4 confirms that stale continuity invalidation improved, but the native authority integration required by the design and Audit V3 remains missing.

## 6.1 The request contract cannot carry native resource authority

`DomainSessionResumeRequest` still declares:

```python
current_resource_versions: Mapping[str, str]
current_knowledge_versions: Mapping[str, str]
```

and `_freeze_str_str_map()` enforces string values.

Therefore valid request construction cannot carry a real:

```text
DomainResourceContext
DomainResourceTemporalPolicy
resource resolver result
native temporal/provenance authority object
```

## 6.2 Session revalidation still interprets status/version strings

`revalidate_resource_and_knowledge_drift()` primarily classifies strings such as:

```text
MISSING
INVALIDATED
EXPIRED
STALE
DRIFT
CHANGED
```

A branch exists for `Mapping` resource metadata, but that branch is unreachable through the public `DomainSessionResumeRequest.current_resource_versions` contract because values are constrained to strings.

This is not integration with the repository-native resource temporal/provenance service.

## 6.3 Independent native temporal divergence reproduction

The auditor constructed a real native:

```text
DomainResourceContext
valid_until = one hour in the past
```

plus:

```text
DomainResourceTemporalPolicy(
    expiration_required=True,
    historical_allowed=False
)
```

The repository-native `_evaluate_temporal_policy()` returned:

```text
False
"historical use of an expired resource is not allowed"
```

The same resource reference resumed through Phase 10.34 using the only accepted request representation:

```text
current_resource_versions={"res:expired": "v1"}
```

and Phase 10.34 returned:

```text
status=RESUMED
recorded_resumption=True
resource check=PASS
message="Resource 'res:expired' is current"
```

Thus a resource that the native repository policy says is expired can still be classified current by Domain Sessions.

## 6.4 Missing current resource authority is still fail-open

Independent probe:

```text
persisted resource ref=res:unverified
current_resource_versions={}
```

observed:

```text
status=RESUMED
recorded_resumption=True
resource check=WARNING
blocking=False
message=no current version metadata (unverified)
```

The V4 remediation prompt explicitly required missing/unknown current authority to be conservative.

## Positive V4 change to preserve

Material continuity invalidation has improved:

- recomposition clears current `partial_result_refs` and `trace_refs`;
- compatible version changes clear stale derived continuity;
- drift can force `REPLAN_REQUIRED`.

## Required remediation

Introduce a narrow current-resource/knowledge authority interface using the repository-native resource/knowledge contracts.

Do not overload `current_resource_versions` with pseudo-status strings as the authoritative freshness mechanism.

At minimum:

1. resolve referenced resource IDs through the native current resource authority;
2. apply native temporal policy (`valid_from`, `valid_until`, `last_verified_at`, validity windows, historical policy);
3. classify missing/unknown authority conservatively;
4. use native knowledge freshness/provenance authority equivalently;
5. keep string version snapshots only as historical/version evidence, not current truth;
6. add an E2E test using a real expired `DomainResourceContext` and `DomainResourceTemporalPolicy`.

---

# 7. MAJOR-03 — AT-DP-034 remains a false-positive gate; required evidence manifest does not exist

This is the largest remaining closure issue.

## Required V4 remediation

Audit V3 and the V4 remediation specification required a machine-verifiable evidence manifest with fields equivalent to:

```text
checkpoint_id
description
evidence_type
evidence_reference
required
```

and HEAD/tree-bound external gate evidence.

## Independent artifact inspection

No Phase 10.34 acceptance evidence manifest or external gate artifact exists in the committed bundle.

Observed:

```text
EVIDENCE_MANIFEST_FILES=0
```

No acceptance implementation contains:

```text
AcceptanceEvidence
evidence_type
evidence_reference
verified_tree
gate_result
```

## The 56-item tuple is still only an inventory

`DOMAIN_SESSION_CHECKPOINTS_56` is a tuple of human-readable strings.

The meta-test proves:

```text
len == 56
unique == 56
one test function exists per number
```

It does not prove that each checkpoint is bound to real evidence.

## Checkpoints 48–56 remain false-positive

### Checkpoint 48

Claims focused tests pass, but only verifies that test files exist and are non-empty.

### Checkpoint 49

Claims Phase 10 domain tests pass, but only verifies that selected classes are importable/callable.

### Checkpoint 50

Claims global tests pass, but only checks `cmm.runtime.sessions` for `cmm.domains` imports.

### Checkpoint 51

Claims Ruff/format/compile/diff hygiene, but only calls Python `compile()` on six source files.

### Checkpoint 54

Claims exact committed archive generation, but only asserts hard-coded strings:

```text
phase-10.34-audit-v4.tar.gz
CMM-OS-phase-10.34/
```

### Checkpoint 55

Claims independent audit criteria, but creates a local dictionary:

```text
required_blockers=0
required_majors=0
required_minors=0
```

and asserts those constants.

### Checkpoint 56

Improved by removing `independent_audit_passed=True`, but still only checks that the roadmap mentions Phase 10.34 and that the inventory length is 56.

It does not verify a recorded independent audit result.

## Independent false-positive reproduction

Inside the extracted exact committed HEAD:

```text
phase-10.34-audit-v4.tar.gz = ABSENT
docs/audits/phase-10.34-independent-audit-v4.md = ABSENT
acceptance evidence manifest = ABSENT
```

Nevertheless the independent execution of:

```text
test_domain_session_audit_v3_regressions.py
test_domain_session_acceptance.py
```

returned:

```text
80 passed
```

including checkpoints 54–56.

Therefore `AT-DP-034=PASS` still does not prove the external gates it claims to represent.

## Additional regression-suite gap

The header of `test_domain_session_audit_v3_regressions.py` claims tests for:

```text
AT-DP manifest has exactly 56 unique checkpoints with resolvable evidence
checkpoints 48-56 bound to real gate evidence
```

but the file contains no such tests.

Its last substantive tests cover strict JSON contracts.

## Required remediation

Implement the evidence system requested in V3/V4, rather than another layer of self-checking unit tests.

Each checkpoint must resolve to real evidence.

For external gates, include a committed evidence artifact bound to an immutable tree/hash or other non-self-referential revision identifier.

The meta-gate must fail for:

- missing evidence reference;
- nonexistent pytest node;
- missing gate artifact;
- failed gate;
- wrong tree/hash;
- placeholder/self-asserted PASS.

Checkpoints 48–56 must use actual evidence, not proxies.

---

# 8. MINOR-01 — Phase 10.34 documentation remains partially stale

`ROADMAP.md` and the detailed Phase 10 roadmap were updated conservatively for V4.

However other canonical/reference material remains stale.

Examples:

`docs/reference/domain-sessions.md` still states:

```text
Focused domain session suite: 304 ... tests passing
```

`docs/reference/domain-intelligence-requirements-matrix.md` still records:

```text
304 focused domain session tests
independent re-audit V2 pending
```

This conflicts with the V4 state and the agent-reported 360 focused cases.

Before V5 audit, update all Phase 10.34 canonical references consistently and conservatively.

Do not claim independent PASS before it exists.

---

# 9. V3 finding disposition

```text
V3 BLOCKER-01 stale durable rollback
FIXED

V3 BLOCKER-02 workflow/conflict status downgrade
FIXED

V3 MAJOR-01 synthetic resolution authority
NOT_FIXED
confidence changed from 1.0 to 0.0, but synthetic RESOLVED result remains

V3 MAJOR-02 native temporal/provenance + stale continuity
PARTIALLY_FIXED
stale derived continuity invalidation improved
native resource/knowledge authority integration remains absent
missing current resource authority remains fail-open

V3 MAJOR-03 strict JSON contracts
FIXED

V3 MAJOR-04 AT-DP-034 false positive
NOT_FIXED

V3 MINOR-01 bundle prefix
FIXED

V3 MINOR-02 stale documentation
PARTIALLY_FIXED
```

---

# 10. Final verdict

V4 is a meaningful improvement.

The two V3 blockers are independently closed, the strict JSON contract issue is fixed, stale derived continuity handling is materially safer, and the archive is now packaged correctly.

However Phase 10.34 still cannot close because:

1. recomposition still fabricates an authoritative-looking `DomainResolutionResult`;
2. resource/knowledge temporal truth is still based on string snapshots rather than repository-native current authority;
3. AT-DP-034 still cannot prove its own external evidence.

```text
FINAL_INDEPENDENT_AUDIT_V4=FAIL

BLOCKERS=0
MAJORS=3
MINORS=1

DP_034=NOT_VERIFIED
AT_DP_034=FAIL

GENERAL_EVENT_COUNT=23
GENERAL_EVENT_UNIQUE_COUNT=23
DOMAIN_SESSION_RESUMED_EVENT=ABSENT

AUDITED_HEAD=5459214a808d3ea8ac44b7cac7ed8f980a2161d3
AUDIT_BUNDLE_SHA256=2d040d418ba23b4a8d935fcd214f91441e69a605e28e2e0ce3ae90bd8d2b54d6
AUDIT_BUNDLE_PREFIX=CMM-OS-phase-10.34/

CLOSURE_ALLOWED=NO
NEXT=PHASE10_34_REMEDIATION_V5
PUSH=NO
MERGE=NO
```
