# Phase 10.37 — Domain Observability — Independent Re-audit V6

**Audit date:** 2026-09-01
**Auditor:** ChatGPT — independent CMM OS audit
**Phase:** 10.37 — Domain Observability
**Branch:** `feature/phase-10-domain-intelligence`
**V5 audit-report baseline:** `57e7002c0b3cc91459121d6054ac5cfde7252f3a`
**Audited V6 HEAD:** `a17326421daa2479f58d7ab45b6a66b1bef75936`
**Audit bundle:** `phase-10.37-audit-v6.tar.gz`
**Audit bundle SHA-256:** `401d7fa4eb1b3ee057fed9e1fd2b299804de43e5c383271bd249e4ad1ca3c56c`

## 1. Verdict

```text
PHASE10_37_INDEPENDENT_REAUDIT_V6=PASS

AUDITED_HEAD=a17326421daa2479f58d7ab45b6a66b1bef75936
AUDIT_V6_BUNDLE_SHA256=401d7fa4eb1b3ee057fed9e1fd2b299804de43e5c383271bd249e4ad1ca3c56c

BLOCKERS=0
MAJORS=0
MINORS=0

V5_MAJOR_01=REMEDIATED
V5_MINOR_01=REMEDIATED
V4_MAJOR_01=REMEDIATED

DP-037=VERIFIED_EXISTING
AT-DP-037=PASS
CLOSURE_ELIGIBLE=YES

PHASE10_38_STARTED=NO
NEXT=RECORD_AUDIT_V6_AND_CLOSE_PHASE10_37
```

Phase 10.37 is technically eligible for closure.

The required next steps are:

1. record this V6 audit PASS as immutable historical evidence;
2. verify a clean worktree and preserved quarantine stash;
3. make a separate docs-only Phase 10.37 closure commit;
4. verify the closure commit and clean repository state;
5. only then may Phase 10.38 begin.

---

## 2. Artifact integrity and exact-HEAD binding

Independent V6 evidence establishes:

```text
TAR_SIZE=5099706
TAR_SHA256=401d7fa4eb1b3ee057fed9e1fd2b299804de43e5c383271bd249e4ad1ca3c56c
GIT_ARCHIVE_HEAD=a17326421daa2479f58d7ab45b6a66b1bef75936
LOCAL_HEAD=a17326421daa2479f58d7ab45b6a66b1bef75936
LOCAL_BRANCH=feature/phase-10-domain-intelligence

GZIP_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
BRANCH_BINDING=PASS
WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED
```

Archive safety:

```text
ARCHIVE_MEMBERS=1984
ARCHIVE_LINKS=0
UNSAFE_ARCHIVE_ENTRIES=0
ARCHIVE_PATH_SAFETY=PASS
```

The bundle contains:

```text
V1 audit
V2 audit
V3 audit
V4 audit
V5 audit
approved Phase 10.37 spec
approved Phase 10.37 implementation plan
observability production modules
approval conflict regression
AT-DP-037
```

The candidate is therefore bound to the exact committed source being audited.

---

## 3. V6 remediation scope

The V6 remediation consists of one commit:

```text
a173264 fix(domains): complete approval evidence identity
```

Scope:

```text
M cmm/domains/observability_metrics.py
M tests/domains/test_domain_observability_approval_conflict_red.py
```

No unrelated Phase 10.38 implementation is present.

No public API, Domain Event catalog, Domain Trace contract, registry, runtime,
store or persistence subsystem is introduced or modified by the remediation.

---

## 4. V5 MAJOR-01 — REMEDIATED

### V5 defect

V5 had adopted:

```text
PermissionApprovalRequirement.requirement_id
```

as the canonical approval occurrence identity but omitted canonical semantic
fields from its material-equivalence comparison.

The omitted fields were:

```text
reason_code
risk
purpose
sensitivity
constraints
```

This allowed same-ID approval requirements with materially different security
or approval semantics to be treated as equivalent.

### V6 production fix

V6 extends `_validate_approval_identity_conflicts()` so the material comparison
now includes the complete canonical approval semantics:

```text
action
actor_id
session_id
domain_id
resource_id
resource_kind
operation_id
operation_version
workflow_id
workflow_version
node_id
source_domain
target_domain
fingerprint
expires_at
scope
one_time
reusable
reason_code
risk
purpose
sensitivity
constraints
```

The canonical identity itself remains:

```text
requirement_id
```

Therefore:

```text
same requirement_id + same complete canonical semantics
→ equivalent duplicate

same requirement_id + any material canonical semantic difference
→ InvalidDomainObservabilityEvidenceError

different requirement_id
→ distinct observability occurrences
```

### Constraints

V6 compares already validated, normalized and frozen canonical constraint
contents.

The canonical permission contract normalizes legal constraints before
`PermissionApprovalRequirement` reaches observability.

The V6 regression proves a real legal constraint difference:

```text
{"allow_external_access": True}
vs
{"allow_external_access": False}
```

with the same `requirement_id` fails closed.

The auxiliary audit probe reports:

```text
APPROVAL_CONSTRAINTS_CONFLICT=NOT_PROBED
```

because its own fallback candidate-selection routine did not find a candidate
from its hard-coded probe list. This is not a product failure: the exact V6
regression itself constructs legal canonical `allow_external_access`
constraints and passes.

### Direct V6 semantic coverage

The V6 regression proves:

```text
same requirement_id + different operation_id → fail closed
same requirement_id + different action → fail closed
same requirement_id + different risk → fail closed
same requirement_id + different sensitivity → fail closed
same requirement_id + different constraints → fail closed
same requirement_id + different reason_code → fail closed
same requirement_id + different purpose → fail closed

identical duplicate approval → accepted
identical duplicate with full semantic fields → accepted
different requirement_id → distinct occurrences
error diagnostics → reference-safe
```

Independent direct probes additionally establish:

```text
APPROVAL_RISK_CONFLICT=PASS
APPROVAL_REASON_CODE_CONFLICT=PASS
APPROVAL_PURPOSE_CONFLICT=PASS
APPROVAL_SENSITIVITY_CONFLICT=PASS
```

Result:

```text
V5_MAJOR_01=REMEDIATED
V4_MAJOR_01=REMEDIATED
```

---

## 5. V5 MINOR-01 — REMEDIATED

V5 failed Ruff with:

```text
C408 unnecessary dict() call
I001 import block unsorted
I001 import block unsorted
```

V6 fixes the test-only style issues:

```text
dict(...) → dictionary literal
local import blocks organized
```

Exact V6 result:

```text
RUFF_EXIT=0
FORMAT_EXIT=0
```

Result:

```text
V5_MINOR_01=REMEDIATED
```

---

## 6. Test and quality evidence

Independent V6 execution records:

```text
Approval conflict regression: 11 passed
AT-DP-037:                  3 passed
Phase 10.37 focused:      229 passed
Full Domain suite:       8687 passed
Global suite:           14242 passed
```

Static and closure gates:

```text
RUFF_EXIT=0
FORMAT_EXIT=0
COMPILEALL_EXIT=0
DIFF_CHECK_EXIT=0

HISTORICAL_AUDITS_UNCHANGED=PASS
DOMAIN_API_UNCHANGED=PASS
DOMAIN_EVENT_CATALOG_23_OF_23=PASS
NO_PARALLEL_OBSERVABILITY_INFRASTRUCTURE=PASS
NO_REVERSE_RUNTIME_DEPENDENCY=PASS
SECRET_PATH_GATE=PASS

WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED
COLLECTOR_COMMAND_FAILURES=0
```

No test, quality, architecture or artifact-integrity gate remains red.

---

## 7. Preservation of earlier audit remediations

V6 preserves the previously verified corrections:

```text
operation execution occurrence identity uses result_id
workflow execution occurrence identity uses run_id
definition IDs do not collapse distinct executions/runs
source precedence requires canonical occurrence linkage
transfer identity includes source/target/kind/identifier/iteration
permission identity includes operation_id + operation_version
contradictory permission decisions fail closed
all canonical DomainObservabilityEvidence tuple types validate at runtime
approval class-name fallback remains removed
health current-version validation remains enforced
knowledge.reused remains UNAVAILABLE absent explicit evidence
single report clock remains preserved
deterministic ordering/digest remains preserved
```

Historical audit reports V1–V5 remain unchanged.

---

## 8. Architecture and scope assessment

The approved Phase 10.37 architecture remains intact:

```text
canonical existing Domain evidence
        ↓
read-only deterministic projection
        ↓
structured observability logs
exact metric OR UNAVAILABLE
read-only health
```

Verified invariants:

```text
one Domain Event system
one Domain Trace system
canonical registries
shared Domain Session authority preserved
DomainAPI unchanged
23/23 canonical Domain Events
no observability store
no observability repository
no observability event bus
no observability runtime
no observability engine
no observability registry
no observability loader
no observability trace
no reverse runtime dependency
no persistence
no Phase 10.38 implementation
```

The Phase 10.37 implementation remains a bounded internal read model.

---

## 9. DP-037 verification

`DP-037 — Domain Observability Projection` requires the projection to be:

```text
canonical
read-only
deterministic
privacy-minimized
exact where evidence exists
UNAVAILABLE where evidence does not exist
deduplicated by authoritative occurrence identity
fail-closed on malformed or contradictory canonical evidence
```

The V1–V6 remediation sequence now establishes all of those properties,
including the final same-ID approval semantic-conflict boundary.

Therefore:

```text
DP-037=VERIFIED_EXISTING
```

---

## 10. AT-DP-037 verification

The connected acceptance test executes successfully against the exact V6
candidate:

```text
AT-DP-037: 3 passed
```

It continues to demonstrate the corrected execution-occurrence model and the
Phase 10.37 architecture using canonical components.

Therefore:

```text
AT-DP-037=PASS
```

---

## 11. Closure assessment

All required closure criteria are now satisfied:

```text
BLOCKERS=0
MAJORS=0
MINORS=0
DP-037=VERIFIED_EXISTING
AT-DP-037=PASS
CLOSURE_ELIGIBLE=YES
```

Phase 10.37 may now enter the final documentation-only closure step.

The closure commit must contain no production code or tests.

It should update only the canonical documentation required to record that
Phase 10.37 has passed independent audit V6 and is closed.

Phase 10.38 must not begin until that docs-only closure commit is made and the
repository is verified clean.

---

## 12. Final V6 status

```text
PHASE10_37_INDEPENDENT_REAUDIT_V6=PASS

AUDITED_HEAD=a17326421daa2479f58d7ab45b6a66b1bef75936
AUDIT_V6_BUNDLE_SHA256=401d7fa4eb1b3ee057fed9e1fd2b299804de43e5c383271bd249e4ad1ca3c56c

BLOCKERS=0
MAJORS=0
MINORS=0

V5_MAJOR_01=REMEDIATED
V5_MINOR_01=REMEDIATED
V4_MAJOR_01=REMEDIATED

DP-037=VERIFIED_EXISTING
AT-DP-037=PASS
CLOSURE_ELIGIBLE=YES

WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED

PHASE10_38_STARTED=NO
NEXT=RECORD_AUDIT_V6_AND_CLOSE_PHASE10_37
```
