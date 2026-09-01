# Phase 10.37 — Domain Observability — Independent Re-audit V5

**Audit date:** 2026-09-01
**Auditor:** ChatGPT — independent CMM OS audit
**Phase:** 10.37 — Domain Observability
**Branch:** `feature/phase-10-domain-intelligence`
**V4 audit-report baseline:** `2fe19a62c646e47c3ad39c4744eb5b12ba32b322`
**Audited V5 HEAD:** `5d782e85b2d8164a8e8b6836ce340d2352616082`
**Audit bundle:** `phase-10.37-audit-v5.tar.gz`
**Audit bundle SHA-256:** `781176e9572055184d6124a55b5834e0dec7bb06ca4209428b710950ef26c784`

## 1. Verdict

```text
PHASE10_37_INDEPENDENT_REAUDIT_V5=FAIL

BLOCKERS=0
MAJORS=1
MINORS=1

V4_MAJOR_01=PARTIALLY_REMEDIATED

DP-037=NOT_VERIFIED
AT-DP-037=PASS
CLOSURE_ELIGIBLE=NO

PHASE10_38_STARTED=NO
NEXT=PHASE10_37_AUDIT_V5_REMEDIATION
```

V5 correctly introduces a fail-closed approval identity validator and closes
the previously demonstrated conflicts for `operation_id` and `action`.

However, the validator does not compare all canonical material fields of
`PermissionApprovalRequirement`, so same-ID approvals may still differ in
security/approval semantics without failing closed.

The exact candidate also fails Ruff in the newly added regression test.

No Phase 10.38 work may start.

---

## 2. Artifact integrity

Independent evidence verifies:

```text
TAR_SHA256=781176e9572055184d6124a55b5834e0dec7bb06ca4209428b710950ef26c784
GIT_ARCHIVE_HEAD=5d782e85b2d8164a8e8b6836ce340d2352616082
LOCAL_HEAD=5d782e85b2d8164a8e8b6836ce340d2352616082

SHA256_MATCH=PASS
GZIP_INTEGRITY=PASS
EXACT_HEAD_BINDING=PASS
BRANCH_BINDING=PASS
WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED

ARCHIVE_MEMBERS=1983
ARCHIVE_LINKS=0
UNSAFE_ARCHIVE_ENTRIES=0
ARCHIVE_PATH_SAFETY=PASS
```

Required spec, plan, V1–V4 audit history, production modules, AT and the new
approval-conflict regression are present.

---

## 3. Passing V5 behavior

V5 adds `_validate_approval_identity_conflicts()` at the public evidence
boundary.

The following behavior is positively verified:

```text
same requirement_id + different operation_id
→ InvalidDomainObservabilityEvidenceError

same requirement_id + different action
→ InvalidDomainObservabilityEvidenceError

identical duplicate approval
→ accepted / one logical occurrence

different requirement_id
→ distinct occurrences

conflict error
→ reference-safe
```

The targeted V5 regression passes:

```text
5 passed
```

The connected acceptance passes:

```text
AT-DP-037: 3 passed
```

The broader suites also pass:

```text
Phase 10.37 focused: 223 passed
Full Domain suite: 8681 passed
Global suite: 14236 passed
```

Architecture and closure-related gates pass except Ruff:

```text
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

---

## 4. MAJOR-01 — approval material identity is still incomplete

### Requirement

Once `PermissionApprovalRequirement.requirement_id` is adopted as the
observability occurrence identity, any materially conflicting canonical
requirement sharing that ID must fail closed.

The approved V4 remediation explicitly required inspection of the real
canonical contract rather than a hand-selected subset.

### Canonical contract

`PermissionApprovalRequirement` contains canonical fields including:

```text
requirement_id
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

The contract validates `reason_code` and `risk` as non-empty canonical strings,
normalizes `purpose`, canonicalizes `sensitivity`, validates/freezes
`constraints`, and treats these values as part of the approval requirement
object.

These fields are therefore not arbitrary transient metadata.

### V5 implementation

The V5 validator compares:

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
```

but omits:

```text
reason_code
risk
purpose
sensitivity
constraints
```

### Impact

Two valid canonical requirements may have:

```text
same requirement_id
same operation/action/context identity
different risk
```

or:

```text
different sensitivity
different purpose
different effective constraints
different reason_code
```

and V5 will treat them as materially equivalent.

That violates the intended fail-closed invariant for contradictory same-ID
approval evidence.

In particular, `risk`, `sensitivity` and `constraints` are directly relevant
to security/permission semantics and cannot be silently ignored.

### Required remediation

The same-ID conflict identity must cover the complete canonical material
semantics of `PermissionApprovalRequirement`.

Preferred approaches, after inspecting the real contract:

```text
A. compare the complete normalized canonical requirement excluding only
   requirement_id where appropriate; or

B. construct a complete deterministic canonical material identity including all
   public semantic fields.
```

Do not use:

```text
repr()
object identity
private payload
transient metadata
```

Add RED coverage for at least:

```text
same requirement_id + different risk → fail closed
same requirement_id + different sensitivity → fail closed
same requirement_id + different constraints → fail closed
```

Also cover `reason_code`/`purpose` if they are confirmed as canonical semantic
fields by the existing contract.

Preserve:

```text
identical duplicate → accepted
different requirement_id → distinct
safe error diagnostics
```

Classification:

```text
MAJOR
```

---

## 5. MINOR-01 — Ruff gate fails on the new V5 regression

The exact V5 candidate fails:

```text
RUFF_EXIT=1
```

with three issues in:

```text
tests/domains/test_domain_observability_approval_conflict_red.py
```

Specifically:

```text
C408 — unnecessary dict() call
I001 — import block unsorted
I001 — import block unsorted
```

All other static gates pass.

This does not invalidate the production semantics by itself, but CMM OS
requires Ruff PASS before audit closure.

Classification:

```text
MINOR
```

The fix must remain test-only:

```text
dict(...) → literal
organize local imports
```

Do not use `--unsafe-fixes`.

---

## 6. AT-DP-037

The connected acceptance itself passes and the earlier V3 occurrence-identity
false positive remains fixed.

The remaining V5 defect is a focused same-ID approval semantic completeness
case outside the current connected AT.

Therefore:

```text
AT-DP-037=PASS
```

This does not imply DP verification while a production MAJOR remains.

---

## 7. DP-037 assessment

DP-037 requires a canonical, deterministic, fail-closed projection over
authoritative Domain evidence.

V5 now has the correct fail-closed mechanism structurally, but its canonical
approval material identity remains incomplete.

Therefore:

```text
DP-037=NOT_VERIFIED
```

---

## 8. V5 remediation scope lock

Remediate only:

```text
MAJOR-01
complete PermissionApprovalRequirement same-ID material comparison

MINOR-01
Ruff cleanup in the V5 regression test
```

Expected production target:

```text
cmm/domains/observability_metrics.py
```

Expected test target:

```text
tests/domains/test_domain_observability_approval_conflict_red.py
```

No changes are expected to:

```text
DomainAPI
Domain Events
Domain Trace
PermissionApprovalRequirement public contract
registries
runtime
persistence
source precedence
health
sessions
```

No new subsystem is permitted.

---

## 9. Required V6 evidence

After TDD remediation:

```text
new approval semantic RED tests
→ GREEN
→ focused Phase 10.37
→ closed regressions
→ full Domain suite
→ global suite
→ Ruff PASS
→ format PASS
→ compileall PASS
→ diff-check PASS
→ architecture gates
→ secret-path gate
→ historical audits unchanged
→ worktree clean
→ quarantine stash preserved
```

Then create a new exact-HEAD bundle:

```text
phase-10.37-audit-v6.tar.gz
```

with a new SHA-256.

Do not overwrite V1–V5 bundles.

---

## 10. Final V5 status

```text
PHASE10_37_INDEPENDENT_REAUDIT_V5=FAIL

AUDITED_HEAD=5d782e85b2d8164a8e8b6836ce340d2352616082
AUDIT_V5_BUNDLE_SHA256=781176e9572055184d6124a55b5834e0dec7bb06ca4209428b710950ef26c784

BLOCKERS=0
MAJORS=1
MINORS=1

V4_MAJOR_01=PARTIALLY_REMEDIATED

DP-037=NOT_VERIFIED
AT-DP-037=PASS
CLOSURE_ELIGIBLE=NO

PHASE10_38_STARTED=NO
NEXT=PHASE10_37_AUDIT_V5_REMEDIATION
```
