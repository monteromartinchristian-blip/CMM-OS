# CMM OS — Phase 10.52 — Independent Re-audit V4

**Audit date:** 2026-09-13
**Phase:** 10.52 — Mental Health Domain
**Audit type:** Independent exact-HEAD V4 remediation re-audit
**Verdict:** **PASS — closure eligible**

---

# 1. Audited artifact

```text
BUNDLE=phase-10.52-mental-health-domain-reaudit-v4-1b21e48717cf.tar.gz
AUDITED_IMPLEMENTATION_HEAD=1b21e48717cfabdade2375d438413849d54b164f
AUDIT_BUNDLE_SHA256=04bbfd2771645f59c908dbc4339dc5e10b5d31f802b8ec14a83e01b18872e44f
ARCHIVE_MEMBERS=2302
```

Independent verification:

```text
CALCULATED_SHA256=04bbfd2771645f59c908dbc4339dc5e10b5d31f802b8ec14a83e01b18872e44f
SHA256_MATCH=YES
GZIP_INTEGRITY=PASS
GIT_ARCHIVE_COMMIT_ID=1b21e48717cfabdade2375d438413849d54b164f
HEAD_MATCH=YES
```

Result:

```text
BUNDLE_INTEGRITY=PASS
EXACT_HEAD_PROVEN=YES
```

---

# 2. Frozen evidence integrity

The V4 bundle preserves all approved and historical evidence:

```text
SPEC_SHA256=e42f894f3fdf2483d5b4c34cb9d3255ab1fae8af8a109ed65e7b998f84c989f7
PLAN_SHA256=0e2c96ef6b21b1c415325599ff40186ea8513e22760157b4e4a24cc755936562

AUDIT_V1_SHA256=b75e644d2ef143a087990b27821c3403c362c4f7bb91cd74a4e5560c19a697f5
AUDIT_V2_SHA256=a915a2387e3c6d01eeb8f3fbafc2b8138cce89436de6b9051ec344f832bf1d5e
AUDIT_V3_SHA256=b33dbc320797189c5820470f31cf8f929cf8c6ea25e2ab3b7ade4b9249ddc384
```

No historical audit artifact was rewritten.

Phase 10.53 remains absent:

```text
cmm/domains/neurodivergence/=ABSENT
PHASE10_53=NOT_STARTED
```

---

# 3. V3 → V4 exact scope

Independent archive comparison shows:

```text
ADDED_FILES=1
docs/audits/phase-10.52-independent-reaudit-v3.md

REMOVED_FILES=0

CHANGED_FILES=2
tests/domains/test_mental_health_domain_dp052_acceptance.py
docs/reference/mental-health-domain.md
```

Production Mental Health code is unchanged between V3 and V4:

```text
cmm/domains/mental_health/rules.py
V3_V4_BYTE_IDENTICAL=YES
```

This is the intended V4 architecture: the V3 projection/minimization rule was
already correct; V4 fixes the connected permission/approval boundary in
AT-DP-052 using existing canonical owners.

Result:

```text
V4_SCOPE=PASS
ANTI_SCOPE_CREEP=PASS
NO_PRODUCTION_PERMISSION_ENGINE_ADDED=YES
```

---

# 4. Architecture / anti-fragmentation

Independent static review found no new parallel Mental Health infrastructure.

No production owner was introduced for:

```text
MentalHealthRegistry
MentalHealthLoader
MentalHealthResolver
MentalHealthComposer
MentalHealthRuntime
MentalHealthEngine
MentalHealthStore
MentalHealthMemoryStore
MentalHealthKnowledgeGraph
MentalHealthPlanner
MentalHealthWorkflowEngine
MentalHealthPermissionEngine
MentalHealthPrivacyEngine
MentalHealthTraceStore
MentalHealthValidationEngine
MentalHealthSafetyEngine
MentalHealthCrisisEngine
```

The connected V4 path reuses:

```text
DomainPermissionResolver
DomainPermissionGate
ApprovalService
InMemoryApprovalRepository
CrossDomainPermissionRequest
CrossDomainContextTransfer
PurposeMinimizedCrossDomainRule
```

Result:

```text
ANTI_FRAGMENTATION=PASS
CANONICAL_PERMISSION_OWNER_PRESERVED=YES
CANONICAL_APPROVAL_OWNER_PRESERVED=YES
PHASE10_53_NOT_IMPLEMENTED=YES
```

---

# 5. Independent executable verification

The audit sandbox differs from the implementation host:

```text
Python=3.13
libcst=not installed
git archive extraction has no .git metadata
```

As in V1–V3, the auditor used only external compatibility shims outside the
audited tree:

```text
import-only libcst shim
runtime-only compatibility patch for the pre-existing shared
@dataclass(slots=True) + zero-argument super() Python 3.13 issue
```

No audited file was modified.

Fresh independent results:

```text
AT_DP_052_ACCEPTANCE=32_PASSED
PHASE10_52_FOCUSED_SUITE=285_PASSED
ARCHITECTURE_PLUS_AT=43_PASSED
COMPILEALL_CMM_CMM_AGENT_KERNEL_TESTS=PASS
```

Closed-finding focused reproductions:

```text
MAJOR_01_BOOLEAN_SAFETY_HEALTH_AUTHORITY=58_PASSED
MAJOR_02_TRANSCRIPT_PROVENANCE=24_PASSED
MINOR_01_STALE_MEMORY_BINDING_REVOCATION=1_PASSED
```

A related shared-regression run produced:

```text
79 PASSED
1 FAILURE
```

The single failure was:

```text
tests/domains/test_domain_permission_gate.py::
test_orchestrator_execute_preserves_permission_authority_on_success
```

and was reproduced identically against the V3 bundle in the same audit
environment. It is therefore not a V4 delta.

A full-suite replay from the extracted `git archive` reached:

```text
2686 PASSED
1 FAILURE
```

before stopping at:

```text
tests/agent_runtime/test_observation_engine.py::test_git_observer_real_repo
```

because `GitObserver` correctly sees the extracted audit tree as not being a
live Git repository: a `git archive` contains no `.git` directory. This is an
audit-environment artifact, not a bundle defect.

The implementation/verifier reported a fresh run in the actual repository:

```text
GLOBAL_SUITE=17259_PASSED
EXIT=0
```

and:

```text
FOCUSED_10_52=285_PASSED
COMPILEALL_FULL=PASS
CHANGED_FILE_RUFF=PASS
CHANGED_FILE_FORMAT=PASS
WORKTREE=CLEAN
```

The independent V4 verdict does not depend solely on those reported counts:
the critical Phase 10.52 and permission-boundary semantics were reproduced
directly against the exact bundle.

---

# 6. V1/V2/V3 finding closure matrix

| Finding | V4 independent result |
| --- | --- |
| MAJOR-01 — malformed truthy sensitive flags | **CLOSED** |
| MAJOR-02 — therapy source provenance false positive | **CLOSED** |
| MAJOR-03 — cross-domain transfer/provenance/permission authority | **CLOSED** |
| MINOR-01 — stale memory binding revocation evidence | **CLOSED** |

Result:

```text
MAJOR_01=CLOSED
MAJOR_02=CLOSED
MAJOR_03=CLOSED
MINOR_01=CLOSED
```

---

# 7. MAJOR-03 final closure — field ↔ transfer binding remains correct

The V3 production fix remains byte-identical and continues to prove:

```text
one authorized transfer cannot authorize another field
unbound relevant field is excluded
unrelated transfer cannot authorize projection
accepted transfer cannot launder a rejected/private/non-transferable field
provenance derives only from transfers backing included fields
duplicate provenance is deterministic
```

Independent V4 acceptance and direct adversarial execution preserve:

```text
CROSS_DOMAIN_FIELD_TRANSFER_BINDING=PASS
UNBOUND_RELEVANT_FIELD_EXCLUDED=PASS
UNRELATED_TRANSFER_CANNOT_AUTHORIZE_PROJECTION=PASS
REJECTED_FIELD_NOT_LAUNDERED=PASS
CROSS_DOMAIN_PROVENANCE_PER_INCLUDED_FIELD=PASS
```

---

# 8. MAJOR-03 final closure — DENY + matching transfer

The exact residual V3 adversarial is now connected correctly.

V4 deliberately presents a structurally valid matching transfer for a field
that the real current canonical permission resolver denies.

The acceptance includes an anti-vacuity control proving:

```text
PurposeMinimizedCrossDomainRule alone
+ matching structurally valid transfer
=> field would be included
```

Then the real connected boundary evaluates:

```text
DomainPermissionResolver
    -> DENY

DomainPermissionGate
    -> DENY
```

and the matching transfer is not admitted to the projection.

Independent external reproduction against the exact V4 bundle:

```text
DENY_MATCHING_TRANSFER=BLOCKED
```

Result:

```text
CANONICAL_PERMISSION_DENY_WITH_MATCHING_TRANSFER_BLOCKED=PASS
CURRENT_PERMISSION_BOUND_TO_TRANSFER_ADMISSION=PASS
```

This closes the precise false-positive pattern identified by Re-audit V3.

---

# 9. MAJOR-03 final closure — APPROVAL_REQUIRED is not authority

The V3 positive control incorrectly treated `not DENY` as sufficient authority.

V4 now uses the real canonical gate.

Before approval:

```text
DomainPermissionResolver -> APPROVAL_REQUIRED
DomainPermissionGate -> APPROVAL_REQUIRED
gate.allowed=False
admitted_transfers=()
```

Independent external reproduction:

```text
APPROVAL_REQUIRED_WITHOUT_CONSUMPTION=BLOCKED
```

No `SENSITIVE` privacy floor was weakened to manufacture a direct `ALLOW`.

Result:

```text
APPROVAL_REQUIRED_WITHOUT_CONSUMPTION_BLOCKED=PASS
PRIVACY_FLOOR_NOT_WEAKENED=PASS
```

---

# 10. MAJOR-03 final closure — canonical approval consumption

V4 drives the real approval lifecycle:

```text
PermissionApprovalRequirement
    ↓
to_approval_requirement(...)
    ↓
ApprovalService.create_request_from_requirement(...)
    ↓
ApprovalService.approve(...)
    ↓
DomainPermissionGate.evaluate_cross_domain(...)
    ↓
APPROVAL_CONSUMED
```

Only after that gate outcome is the matching transfer admitted.

Independent external reproduction:

```text
APPROVAL_CONSUMED_MATCHING_TRANSFER=INCLUDED
```

The gate evidence binds the current canonical requirement and the approval
service validates the complete typed requirement.

Result:

```text
CANONICAL_APPROVAL_CREATED=PASS
CANONICAL_APPROVAL_GRANTED=PASS
APPROVAL_CONSUMED=PASS
APPROVED_TRANSFER_FIELD_INCLUDED=PASS
```

---

# 11. Authority tuple adversarials

Independent external V4 adversarials additionally prove:

```text
APPROVAL_FOR_A_CANNOT_AUTHORIZE_B=BLOCKED

APPROVAL_FOR_ACTOR_1_CANNOT_AUTHORIZE_ACTOR_2=BLOCKED

APPROVAL_FOR_SESSION_1_CANNOT_AUTHORIZE_SESSION_2=BLOCKED

APPROVAL_FOR_PURPOSE_A_CANNOT_AUTHORIZE_PURPOSE_B=BLOCKED
```

The canonical approval service compares the complete typed
`PermissionApprovalRequirement`; the connected projection admission also
requires transfer identifier/source/target/reason to match the current request.

Result:

```text
RESOURCE_BINDING=PASS
ACTOR_BINDING=PASS
SESSION_BINDING=PASS
PURPOSE_BINDING=PASS
```

---

# 12. Security review

`SECURITY.md` classifies cross-domain permission leakage as security-relevant.

V4 updates `docs/reference/mental-health-domain.md` with a specific threat and
abuse analysis:

```text
Threat:
structurally valid transfer without effective current permission

Abuse:
DENY or unconsumed APPROVAL_REQUIRED combined with a matching transfer

Control:
DomainPermissionResolver + DomainPermissionGate before projection admission

Positive path:
canonical approval -> APPROVAL_CONSUMED

Boundary:
PurposeMinimizedCrossDomainRule remains minimization/provenance owner,
not permission owner
```

The documented limitation is correct:

```text
structural transfer validity alone is not authority
```

Negative tests cover DENY, unconsumed approval, resource mismatch, actor mismatch
and structurally rejected transfers.

Result:

```text
SECURITY_THREAT_ANALYSIS=PASS
ABUSE_CASES=PASS
NEGATIVE_TESTS=PASS
DOCUMENTED_LIMITATION=PASS
```

---

# 13. Documentation / remediation history

The V4 reference documentation now records the real chronology:

```text
V1 independent audit    -> FAIL
V2 independent re-audit -> FAIL
V3 independent re-audit -> FAIL
V4 remediation          -> pending independent V4 re-audit
```

Historical audit reports remain immutable.

The pre-audit markers remain correct:

```text
PHASE10_52=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT
DP-052=PASS_REPORTED
AT-DP-052=PASS_REPORTED
CLOSURE_ELIGIBLE=UNKNOWN_PENDING_INDEPENDENT_REAUDIT
PHASE10_53=NOT_STARTED
```

No premature closure was claimed.

Result:

```text
DOCUMENTATION_FOLLOWUP=CLOSED
PRE_AUDIT_STATE=PASS
```

---

# 14. DP-052 independent assessment

The exact V4 bundle demonstrates the complete Mental Health specialization:

```text
canonical first-party Domain Pack
MentalHealthProfile
non-clinical ordinary emotional mode
therapy continuity / transcript provenance
epistemic separation
proposal-first sensitive memory
Health clinical authority
SENSITIVE privacy
purpose-minimized cross-domain projection
current canonical permission gating
canonical approval consumption
authority downgrade fail-closed behavior
no parallel infrastructure
Phase 10.53 absence
```

The final permission gap from V3 is closed without changing ownership or
creating a Mental Health permission subsystem.

Therefore:

```text
DP-052=VERIFIED_EXISTING
```

---

# 15. AT-DP-052 independent assessment

AT-DP-052 now uses real canonical components or official in-memory
implementations and proves the connected behavior rather than merely asserting
metadata.

Independent execution:

```text
AT_DP_052_ACCEPTANCE=32_PASSED
ARCHITECTURE_PLUS_AT=43_PASSED
```

The former false-positive cross-domain checkpoint now includes real negative and
positive authority paths.

Therefore:

```text
AT-DP-052=PASS
```

---

# 16. Independent Re-audit V4 final verdict

```text
INDEPENDENT_REAUDIT_V4=PASS

AUDITED_IMPLEMENTATION_HEAD=1b21e48717cfabdade2375d438413849d54b164f
AUDIT_BUNDLE_SHA256=04bbfd2771645f59c908dbc4339dc5e10b5d31f802b8ec14a83e01b18872e44f

BUNDLE_INTEGRITY=PASS
SPEC_INTEGRITY=PASS
PLAN_INTEGRITY=PASS
AUDIT_V1_INTEGRITY=PASS
AUDIT_V2_INTEGRITY=PASS
AUDIT_V3_INTEGRITY=PASS

V4_SCOPE=PASS
ANTI_FRAGMENTATION=PASS
SECURITY_REVIEW=PASS
DOCUMENTATION_FOLLOWUP=CLOSED

FOCUSED_TESTS=285_PASSED
AT_DP_052_ACCEPTANCE=32_PASSED
ARCHITECTURE_PLUS_AT=43_PASSED
COMPILEALL_FULL=PASS

BLOCKERS=0
MAJORS=0
MINORS=0

MAJOR_01=CLOSED
MAJOR_02=CLOSED
MAJOR_03=CLOSED
MINOR_01=CLOSED

DP-052=VERIFIED_EXISTING
AT-DP-052=PASS
CLOSURE_ELIGIBLE=YES

PHASE10_52=INDEPENDENT_REAUDIT_V4_PASS
PHASE10_53=NOT_STARTED

PUSH=NO
MERGE=NO
```

Phase 10.52 is now eligible for the separate docs-only closure commit required by
the CMM OS workflow.

It is **not yet closed** until that dedicated closure commit is created and
verified.
