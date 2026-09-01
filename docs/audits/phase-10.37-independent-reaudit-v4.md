# Phase 10.37 — Domain Observability — Independent Re-audit V4

**Audit date:** 2026-09-01
**Auditor:** ChatGPT — independent CMM OS audit
**Phase:** 10.37 — Domain Observability
**Branch:** `feature/phase-10-domain-intelligence`
**V3 audit-report baseline:** `273c32e6c72d273b33499d7c3df29d5c73bba059`
**Audited V4 HEAD:** `47726934c8a08dca83fb07158cafd492163fea04`
**Audit bundle:** `phase-10.37-audit-v4.tar.gz`
**Audit bundle SHA-256:** `a41e39180fe55d317610f49ac1720decfc669cbca6f8cd2fba69ad02163eb15f`
**Historical audits:** V1, V2 and V3 preserved unchanged

## 1. Verdict

```text
PHASE10_37_INDEPENDENT_REAUDIT_V4=FAIL

BLOCKERS=0
MAJORS=1
MINORS=0

V3_MAJOR_01=REMEDIATED
V3_MAJOR_02=PARTIALLY_REMEDIATED
V3_MAJOR_03=REMEDIATED

DP-037=NOT_VERIFIED
AT-DP-037=PASS
CLOSURE_ELIGIBLE=NO

PHASE10_38_STARTED=NO
NEXT=PHASE10_37_AUDIT_V4_REMEDIATION
```

V4 closes the operation/workflow occurrence-identity defect, completes runtime
type validation for the declared evidence tuples, closes contradictory
permission evidence, and repairs the connected acceptance model.

One narrow production-contract defect remains in approval identity
normalization: the service now treats `PermissionApprovalRequirement.requirement_id`
as a canonical occurrence identity, but contradictory canonical approval
requirements carrying that same identity are not rejected before source
precedence.

This is a residual part of V3 MAJOR-02, not a new architectural requirement.

No Phase 10.38 work may start.

---

## 2. Artifact integrity and exact-HEAD binding

Independent V4 evidence establishes:

```text
TAR_SIZE=5091386
TAR_SHA256=a41e39180fe55d317610f49ac1720decfc669cbca6f8cd2fba69ad02163eb15f
GIT_ARCHIVE_HEAD=47726934c8a08dca83fb07158cafd492163fea04
LOCAL_HEAD=47726934c8a08dca83fb07158cafd492163fea04
LOCAL_BRANCH=feature/phase-10-domain-intelligence

GZIP_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
BRANCH_BINDING=PASS
WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED

ARCHIVE_MEMBERS=1981
ARCHIVE_LINKS=0
UNSAFE_ARCHIVE_ENTRIES=0
ARCHIVE_PATH_SAFETY=PASS
```

The exact candidate contains:

```text
V1 audit
V2 audit
V3 audit
approved Phase 10.37 spec
approved Phase 10.37 implementation plan
all four observability production modules
AT-DP-037
reference documentation
```

The remediation delta from the committed V3 audit-report baseline is limited to:

```text
cmm/domains/observability_metrics.py
cmm/domains/observability_service.py
tests/domains/test_domain_observability_dp037_acceptance.py
tests/domains/test_domain_observability_major01_v3_red.py
tests/domains/test_domain_observability_major02_v3_red.py
tests/domains/test_domain_observability_major03_red.py
tests/domains/test_domain_observability_v2_red.py
```

No Phase 10.38 scope is present.

---

## 3. Verification and quality gates

The V4 evidence records:

```text
V2 audit-regression tests:       21 passed
AT-DP-037 pytest nodes:           3 passed
Phase 10.37 focused:            218 passed
Full Domain suite:             8676 passed
Global suite:                 14231 passed

RUFF=PASS
FORMAT=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS

HISTORICAL_AUDITS_UNCHANGED=PASS
DOMAIN_API_UNCHANGED=PASS
DOMAIN_EVENT_CATALOG_23_OF_23=PASS
NO_PARALLEL_OBSERVABILITY_INFRASTRUCTURE=PASS
NO_REVERSE_RUNTIME_DEPENDENCY=PASS
SECRET_PATH_GATE=PASS
```

The full Domain suite was executed against the extracted exact V4 TAR snapshot.
The global suite was executed from the real Git repository after exact
bundle/repository HEAD parity had been established.

### Collector bookkeeping note

The collector reports:

```text
COLLECTOR_COMMAND_FAILURES=1
```

This is not a Phase 10.37 implementation failure.

The single failing collector subcommand is:

```text
L1. V3 audit-regression tests
NO_V3_RED_FILE
EXIT_CODE=1
```

because the audit harness looked only for the non-existent consolidated path:

```text
tests/domains/test_domain_observability_v3_red.py
```

V4 actually stores the new V3 regressions in:

```text
tests/domains/test_domain_observability_major01_v3_red.py
tests/domains/test_domain_observability_major02_v3_red.py
```

Both are included by:

```text
tests/domains/test_domain_observability_*.py
```

and therefore participate in the independently executed `218 passed` focused
suite and the `8676 passed` Domain suite.

This collector filename mismatch is classified as audit-harness bookkeeping,
not BLOCKER, MAJOR or MINOR against the product candidate.

---

## 4. V3 MAJOR-01 — REMEDIATED

V3 incorrectly used reusable definition identifiers as execution-occurrence
identities:

```text
DomainOperationResult.operation_id
WorkflowRun.workflow_id
```

V4 corrects the production occurrence keys.

### Operation occurrence identity

`DomainOperationResult.result_id` is now the execution occurrence identity:

```text
("operation_result", result.result_id)
("operation", result.result_id)
```

`operation_id` and `operation_version` remain definition identity and are not
used to merge separate executions.

### Workflow occurrence identity

`DomainWorkflowResult.run_id` is now the workflow execution occurrence identity:

```text
("workflow_result", result.run_id)
("workflow", result.run_id)
```

`workflow_id` remains workflow-definition identity and is not used to merge
separate runs.

### Cross-channel precedence

V4 applies the correct rule:

```text
explicit shared execution reference
→ Event > Trace > public result
```

and does not infer a public-result link from a reusable operation/workflow
definition ID.

The expanded V4 tests cover:

```text
same operation definition + distinct result/request IDs → distinct occurrences
same workflow definition + distinct run IDs → distinct occurrences
explicitly linked Event/Trace/result via result occurrence → one occurrence
definition-linked Event/Trace without public-result occurrence link
    → Event/Trace may merge, public results remain distinct
reordered evidence → deterministic report/digest
```

Result:

```text
V3_MAJOR_01=REMEDIATED
```

---

## 5. V3 MAJOR-02 — PARTIALLY REMEDIATED

V4 fixes most of MAJOR-02.

### 5.1 Runtime evidence-type validation — REMEDIATED

`DomainObservabilityEvidence.__post_init__` now validates canonical element
types for all declared evidence tuple fields:

```text
registry_definitions
registry_records
load_results
resolution_results
compositions
conflict_results
events
traces
sessions
session_resume_results
permission_evidence
approval_evidence
operation_evidence
workflow_evidence
rule_evidence
resource_evidence
cross_domain_transfers
```

Malformed evidence now fails at the public evidence boundary with
`InvalidDomainObservabilityEvidenceError` rather than leaking into arbitrary
later attribute/type failures.

Diagnostics remain reference-safe and do not echo arbitrary malformed object
payloads.

### 5.2 Same-identity contradictory permission evidence — REMEDIATED

V4 adds explicit permission identity conflict validation using:

```text
operation_id + operation_version
```

For one such canonical identity:

```text
ALLOW + DENY
→ InvalidDomainObservabilityEvidenceError
```

while identical duplicates remain admissible and different versions remain
distinct identities.

### 5.3 Approval class-name fallback — REMEDIATED

V3 used a fallback equivalent to:

```text
("approval", type(result).__name__)
```

which could merge unrelated approval requirements merely because they were the
same class.

V4 removes that fallback.

The service now uses:

```text
PermissionApprovalRequirement.requirement_id
```

when present, and otherwise exposes no synthetic approval occurrence key.

This correctly prevents unrelated approvals with different requirement IDs
from collapsing by class name.

### 5.4 Residual MAJOR — same `requirement_id` conflicts do not fail closed

The V3 remediation contract required:

```text
same requirement_id
+ materially conflicting canonical approval fields
→ fail closed before source precedence
```

once `requirement_id` is adopted as the approval occurrence identity.

V4 adopts exactly that identity in `_approval_occurrence_keys()`:

```text
("approval", requirement_id)
```

but the V4 evidence boundary adds only:

```text
_validate_permission_identity_conflicts(...)
```

after element-type validation.

No corresponding approval identity-conflict validation is present in the
submitted V4 production source.

Therefore two valid canonical `PermissionApprovalRequirement` objects can carry:

```text
same requirement_id
different material canonical approval content
```

and enter occurrence normalization with the same:

```text
("approval", requirement_id)
```

instead of failing closed.

That contradicts the Phase 10.37 invariant that contradictory same-identity
evidence must not be silently normalized into one observability occurrence.

It also contradicts the V3 source-precedence implementation's own assumption
that conflicting same-source identity has already been handled before
projection.

### Impact

This is materially narrower than V3 MAJOR-02, but it remains a production
correctness and determinism defect at a canonical identity boundary.

It can suppress or arbitrarily choose between contradictory approval evidence
sharing one canonical occurrence identity.

Classification:

```text
MAJOR
```

Required remediation is local to Phase 10.37 and does not justify changes to
DomainAPI, approval public contracts, Domain Events, Domain Trace, registries,
runtime or persistence.

Result:

```text
V3_MAJOR_02=PARTIALLY_REMEDIATED
```

---

## 6. V3 MAJOR-03 — REMEDIATED

V3's connected AT-DP-037 was a false positive because it manufactured operation
occurrence identity from a reusable definition ID.

V4 expands the acceptance to prove the actual execution model.

It now covers:

```text
two operation executions
same operation_id
different result_id/request_id
→ remain distinct

two workflow executions
same workflow_id
different run_id
→ remain distinct

explicit execution-instance Event/Trace/result reference
→ source precedence applies

malformed core canonical evidence
→ fail closed

same permission identity ALLOW + DENY
→ fail closed

unrelated approval requirements
→ do not merge through class-name fallback
```

It also preserves the previously accepted checkpoints for:

```text
transfer identifier + iteration
permission version distinction
permission canonical status
resource attribution
knowledge.reused = UNAVAILABLE where unsupported
session degradation semantics
health current-version validation
stale-version rejection
single-clock capture
order-independent digest
Domain Events 23/23
DomainAPI unchanged
no parallel observability infrastructure
privacy minimization
```

The three connected acceptance pytest nodes pass against the exact candidate.

The remaining same-`requirement_id` approval conflict is a focused production
MAJOR-02 residue. The V3 MAJOR-03 occurrence-identity false positive itself is
closed.

Result:

```text
V3_MAJOR_03=REMEDIATED
AT-DP-037=PASS
```

---

## 7. Architecture and invariant assessment

V4 continues to preserve the approved Phase 10.37 architecture:

```text
canonical existing Domain evidence
        ↓
read-only deterministic projection
        ↓
structured observability logs
exact metric OR UNAVAILABLE
read-only health
```

Verified boundaries:

```text
one Domain Event system
one Domain Trace system
canonical registries
shared Domain Session authority preserved
DomainAPI unchanged
23/23 general Domain Events
no observability store
no observability repository
no observability event bus
no observability runtime
no observability engine
no observability registry
no observability loader
no observability trace
no reverse runtime dependency
no Phase 11 observability expansion
```

Previously accepted `UNAVAILABLE` semantics remain preserved where canonical
evidence cannot honestly support a metric.

No architecture redesign is required for the remaining finding.

---

## 8. DP-037 assessment

DP-037 requires the Domain Observability projection to be:

```text
canonical
read-only
exact
deterministic
privacy-safe
deduplicated by authoritative occurrence identity
fail-closed on malformed or contradictory same-identity evidence
```

V4 now satisfies the operation/workflow occurrence identity, runtime type
validation, permission-conflict, architecture, privacy and quality boundaries.

However, because approval evidence is explicitly grouped by `requirement_id`
without rejecting contradictory canonical values for that same identity, the
fail-closed same-identity invariant is not yet complete.

Therefore:

```text
DP-037=NOT_VERIFIED
```

---

## 9. Required V4 remediation

The V5 remediation must be narrow.

### Production

Expected target:

```text
cmm/domains/observability_metrics.py
```

`cmm/domains/observability_service.py` should change only if direct inspection
shows the fail-closed check cannot correctly live at the evidence-normalization
boundary.

Add approval identity conflict validation before log occurrence precedence.

For canonical `PermissionApprovalRequirement` evidence:

```text
identity = requirement_id
```

Then:

```text
same requirement_id + identical canonical content
→ may collapse / remain equivalent

same requirement_id + materially conflicting canonical content
→ InvalidDomainObservabilityEvidenceError

different requirement_id
→ distinct approval occurrences
```

The validator must use only safe canonical fields and must not echo sensitive
payloads or arbitrary object representations in errors.

### Mandatory RED

Add a direct RED regression using real canonical
`PermissionApprovalRequirement` objects:

```text
same requirement_id
different material canonical field
→ fail closed
```

The field difference should be chosen after inspecting the real contract and
should not require any public contract changes.

Also preserve/verify:

```text
different requirement IDs of the same class remain distinct
identical same-ID duplicates remain valid/equivalent
error text contains safe identity/type information only
```

### Gates

After the minimal fix, rerun:

```text
targeted new RED/GREEN
Phase 10.37 focused suite
relevant closed Phase 10 regressions
full Domain suite
global suite
Ruff
format
compileall
git diff --check
architecture gates
secret-path gate
worktree clean
quarantine stash preserved
```

Then create:

```text
phase-10.37-audit-v5.tar.gz
```

from the exact committed remediation HEAD and calculate a new SHA-256.

Do not overwrite V1/V2/V3/V4 bundles.

---

## 10. Final V4 status

```text
PHASE10_37_INDEPENDENT_REAUDIT_V4=FAIL

AUDITED_HEAD=47726934c8a08dca83fb07158cafd492163fea04
AUDIT_V4_BUNDLE_SHA256=a41e39180fe55d317610f49ac1720decfc669cbca6f8cd2fba69ad02163eb15f

BLOCKERS=0
MAJORS=1
MINORS=0

V3_MAJOR_01=REMEDIATED
V3_MAJOR_02=PARTIALLY_REMEDIATED
V3_MAJOR_03=REMEDIATED

DP-037=NOT_VERIFIED
AT-DP-037=PASS
CLOSURE_ELIGIBLE=NO

COLLECTOR_FILENAME_MISMATCH=NON_PRODUCT_HARNESS_ISSUE

PHASE10_38_STARTED=NO
NEXT=PHASE10_37_AUDIT_V4_REMEDIATION
```

Phase 10.37 is not closed.

The V4 audit report must be committed as immutable historical evidence before
starting the narrow V4 remediation.
