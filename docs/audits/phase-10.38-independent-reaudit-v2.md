# CMM OS — Phase 10.38 Independent Re-audit V2

**Date:** 2026-09-01
**Phase:** 10.38 — Security — Domain Pack Authority Boundary
**Independent auditor:** ChatGPT
**Audited branch:** `feature/phase-10-domain-intelligence`
**Audited HEAD:** `f123673e20f6d5bed0d9387da1f146a282d5db10`
**Bundle:** `phase-10.38-audit-v2.tar.gz`
**Bundle SHA-256:** `c5d04f74d7e0c45ce06132eb6d1b4f6657ca9ce91a088a17f9394e1b1e9f8081`
**Bundle size:** `5176173` bytes
**Bundle members:** `1997`
**Verdict:** **FAIL — one MINOR acceptance-evidence defect remains**

---

## 1. Final re-audit result

```text
PHASE10_38_INDEPENDENT_REAUDIT_V2=FAIL

BLOCKERS=0
MAJORS=0
MINORS=1

AUDITED_HEAD=f123673e20f6d5bed0d9387da1f146a282d5db10
AUDIT_BUNDLE_SHA256=c5d04f74d7e0c45ce06132eb6d1b4f6657ca9ce91a088a17f9394e1b1e9f8081

V1_BLOCKER_01=CLOSED
V1_MAJOR_01=CLOSED
V1_MAJOR_02=SUBSTANTIVELY_CLOSED_WITH_V2_MINOR
V1_MINOR_01=CLOSED
V1_MINOR_02=CLOSED
V1_MINOR_03=CLOSED

DP_038=VERIFIED_EXISTING
AT_DP_038=PASS
AT_DP_038_EVIDENCE_CLEAN=NO
CLOSURE_ELIGIBLE=NO

DOMAIN_EVENT_CATALOG_23_OF_23=PASS
NO_PHASE1038_EVENT_ADDED=PASS
NO_PARALLEL_SECURITY_INFRASTRUCTURE=PASS
PHASE10_39_NOT_STARTED=PASS

NEXT=PHASE10_38_V2_MINOR_REMEDIATION_FOR_INDEPENDENT_REAUDIT_V3
```

Phase 10.38 is not closure-eligible yet.

The remaining defect is **not** a runtime authority bypass and does **not**
invalidate DP-038. It is a residual acceptance-evidence defect in one named
checkpoint that the V1 audit explicitly required to be converted from a label
into a real state comparison.

---

## 2. Audit-object integrity

The V2 archive was downloaded directly from the connected Google Drive folder
that contains the distinct V1 and V2 audit bundles.

Independent SHA-256 over the downloaded V2 bytes:

```text
c5d04f74d7e0c45ce06132eb6d1b4f6657ca9ce91a088a17f9394e1b1e9f8081
```

Independent exact-HEAD binding from the Git archive itself:

```bash
gzip -dc phase-10.38-audit-v2.tar.gz | git get-tar-commit-id
```

returned:

```text
f123673e20f6d5bed0d9387da1f146a282d5db10
```

Therefore:

```text
BUNDLE_SHA256_BINDING=PASS
GIT_ARCHIVE_HEAD_BINDING=PASS
AUDITED_HEAD=f123673e20f6d5bed0d9387da1f146a282d5db10
```

The V1 bundle remains separately available with its prior SHA-256:

```text
d5e1c32997d02a5d36f0792e0c2777f163da7572bf33a1a9ffd5755bdbe2a212
```

V1 was not replaced by V2.

---

## 3. Archive safety and frozen-artifact binding

Direct inspection of the original V2 TAR found:

```text
TAR_MEMBERS=1997
ABSOLUTE_PATHS=0
PARENT_TRAVERSAL_PATHS=0
SYMLINKS=0
HARDLINKS=0
TRACKED_.git=0
TRACKED_.venv=0
TRACKED___pycache__=0
TRACKED_.pyc=0
```

Result:

```text
AUDIT_ARCHIVE_CONTENT=PASS
```

Frozen artifact SHA-256 values inside V2:

```text
SPEC_SHA256=
4d5dff07e45049605775052784da2a438a11adcfae0e451ad23d63d20f684b74

PLAN_SHA256=
9ad961faadc345ef45b3e2b3d443118163fd5fcd3063f1e94555f6a08d853f18

V1_AUDIT_REPORT_SHA256=
69d57bb25c7682488cae58edc6b4fcc4d5c4037fa9795723136a7d03cb57ee75
```

All three exactly match the approved/recorded artifacts.

```text
SPEC_BINDING=PASS
PLAN_BINDING=PASS
V1_AUDIT_REPORT_BINDING=PASS
```

---

## 4. Remediation scope audit

A clean V1 → V2 archive comparison found:

```text
ADDED=1
REMOVED=0
CHANGED=13
```

The only added file is:

```text
docs/audits/phase-10.38-independent-audit-v1.md
```

The 13 changed files are exactly:

```text
ROADMAP.md
cmm/domains/api.py
cmm/domains/permission_resolution.py
cmm/domains/trust_contracts.py
cmm/domains/trust_evaluator.py
docs/reference/domain-intelligence-requirements-matrix.md
docs/reference/domain-security.md
docs/roadmap/phase-10-domain-intelligence.md
tests/domains/test_domain_security_dp038_acceptance.py
tests/domains/test_domain_trust_contracts.py
tests/domains/test_domain_trust_evaluator.py
tests/domains/test_domain_trust_lifecycle.py
tests/domains/test_domain_trust_permissions.py
```

There are no unrelated production changes.

```text
REMEDIATION_SCOPE=PASS
```

---

# 5. V1 BLOCKER-01 — CLOSED

## Finding

V1 found that `resolve_cross_domain(...)` applied trust only to
`DOMAIN_CROSS_ACCESS`, not to the actual transferred capability.

## V2 implementation

The canonical cross-domain resolver now evaluates each applicable source and
target trust policy against both:

```text
PermissionCapability.DOMAIN_CROSS_ACCESS
```

and, where different:

```text
request.capability
```

Independent AST/source inspection found four trust calls in the cross-domain
path:

```text
source DOMAIN_CROSS_ACCESS
target DOMAIN_CROSS_ACCESS
source request.capability
target request.capability
```

The actual-capability request preserves the canonical request context used by
the existing resolver, including operation/workflow/resource and sensitivity
bindings where applicable.

Any trust `DENY` enters the existing `reasons` collection; the final resolver
continues to use the existing fail-closed decision path.

Trust still does not synthesize `ALLOW`.

## V2 tests

The committed remediation adds focused coverage for:

```text
cross-domain MEMORY_WRITE
cross-domain OPERATION_EXECUTE
cross-domain sensitive capability
cross-domain destructive capability
canonical deny cannot be widened by permissive trust
```

The connected AT also contains a cross-domain memory-write trust-ceiling
checkpoint.

Disposition:

```text
V1_BLOCKER_01=CLOSED
```

No residual authority bypass was found in this path.

---

# 6. V1 MAJOR-01 — CLOSED

## Finding

V1 found that structurally coherent `PENDING` / `RUNNING` validation evidence
could satisfy activation because the implementation used a failure blacklist.

## V2 implementation

V2 introduces a positive terminal allowlist:

```text
PASSED
WARNING
```

through:

```text
is_terminal_validation_evidence(...)
```

`evaluate_domain_trust(...)` now fails closed for every non-terminal status.

`DefaultDomainAPI.enable_domain(...)` independently enforces the same
terminal-evidence rule before registry enablement, including the narrow trusted
INTERNAL/no-policy compatibility path.

Therefore:

```text
PENDING -> DENY
RUNNING -> DENY
FAILED -> DENY
ERROR -> DENY
PASSED -> may continue
WARNING -> may continue
```

subject to all other canonical validation/trust checks.

## V2 tests

Focused tests cover:

```text
PENDING explicit-policy activation denied
RUNNING explicit-policy activation denied
PENDING trusted-INTERNAL compatibility denied
RUNNING trusted-INTERNAL compatibility denied
registry state unchanged
```

The connected AT contains an explicit PENDING activation rejection.

Disposition:

```text
V1_MAJOR_01=CLOSED
```

---

# 7. V1 MINOR-01 — CLOSED

`DomainTrustDecision._BLOCKING_REASON_CODES` is now:

```python
ClassVar[frozenset[str]]
```

rather than a dataclass instance field.

A caller can no longer pass an alternate blocking-reason set through the
constructor.

The contract still rejects:

```text
activation_allowed=True
+
trust.blocked / other activation-blocking reason
```

Disposition:

```text
V1_MINOR_01=CLOSED
```

---

# 8. V1 MINOR-02 — CLOSED

Both trust contracts now serialize metadata with the existing canonical:

```python
_deep_unfreeze(...)
```

rather than a shallow `dict(...)`.

This preserves deep immutability while producing ordinary JSON-compatible
nested structures.

The committed tests explicitly exercise:

```text
json.dumps(contract.to_dict())
from_dict(to_dict())
nested mappings
nested lists
deep caller-owned mutation isolation
```

for both:

```text
DomainTrustPolicy
DomainTrustDecision
```

Disposition:

```text
V1_MINOR_02=CLOSED
```

---

# 9. V1 MINOR-03 — CLOSED

The stale `ROADMAP.md` statement that Phase 10.38 “has not started” is gone.

The four canonical current-state documents now consistently describe:

```text
Phase 10.38 implemented
Independent Audit V1 = FAIL
V1 findings remediated
independent re-audit V2 pending
```

without claiming closure or V2 PASS.

No stale `Phase 10.38 ... has not started`,
`DP-038=IMPLEMENTED_PENDING_AUDIT`, or plain pre-V1
`AT-DP-038=PASS` current-state marker remains in the audited current-state
documents.

Disposition:

```text
V1_MINOR_03=CLOSED
```

---

# 10. V1 MAJOR-02 — Substantively remediated

V1 found that AT-DP-038 used checkpoint labels that did not prove the claimed
authorization-state atomicity.

V2 makes substantial and correct improvements.

## Real approval repository

The connected stack now owns one real:

```text
InMemoryApprovalRepository
```

shared with its canonical `ApprovalService` / gates.

The AT uses public repository APIs to inspect request and consumption state.

## Real permission-registry snapshots

The AT uses:

```text
DomainPermissionRegistry.snapshot_state()
```

and performs genuine before/after equality assertions for rejected paths,
including unauthorized-source, BLOCKED and non-terminal activation cases.

Independent source accounting finds three real comparisons of the form:

```text
assert stack.permission_snapshot() == permission_before_...
```

## Real approval-state comparisons

Independent source accounting finds three real before/after approval snapshot
comparisons, plus explicit empty request/consumed-ID assertions.

## Loader-state coherence

Unauthorized-source and BLOCKED rejection paths use canonical:

```text
DeclarativeDomainLoader.get_loaded(...)
```

and compare candidate identity/checksum, load status, manifest identity/version
and full loaded-result equality.

The final connected scenario also checks coherent loaded state using
`get_loaded(...)`.

## Exact checkpoint accounting

The AT now enforces an exact committed count:

```text
33 before L1
34 after L1
```

instead of the prior `>= 24`.

## Connected V1 runtime remediations

The AT now includes connected checks for:

```text
cross-domain memory-write trust denial
PENDING validation activation denial
```

These changes remove the substantive reason V1 classified MAJOR-02 as MAJOR.

However, one residual checkpoint defect remains and is recorded below.

---

# 11. V2 MINOR-01 — Tautological I3 permission-registry checkpoint

**Severity:** MINOR
**File:** `tests/domains/test_domain_security_dp038_acceptance.py`
**Audited lines:** approximately `655–656`

## Defect

The final Scenario I checkpoint is:

```python
assert stack.permission_snapshot() == stack.permission_snapshot()
checkpoints("I3-permission-registry-unchanged")
```

This assertion is tautological.

It compares two snapshots taken back-to-back from the same current state and
cannot detect a permission-registry mutation that happened earlier in the
scenario.

The V1 audit explicitly required:

```text
replace label-only I3/I4 with real assertions
```

and the V1 remediation prompt likewise required each named checkpoint to
follow a real state assertion.

`I4` is now real.

`I3` is not.

## Why only MINOR in V2

This is no longer a missing behavioral proof for the authority boundary as a
whole.

The same connected test now contains genuine before/after permission-registry
comparisons for the rejected activation paths:

```text
C1p — unauthorized source
D1p — BLOCKED policy
K2 path — non-terminal validation
```

Therefore the runtime atomicity requirement is independently demonstrated in
the same connected test.

The defect is now localized to a redundant summary checkpoint and to the
agent's claim that I3 itself is a “real snapshot equality”.

It does not create an authorization bypass and does not invalidate DP-038.

It nevertheless remains an objective incomplete remediation of a V1
acceptance-evidence requirement and must be corrected before closure under the
CMM OS audit discipline.

## Required remediation

No production code change is required.

Use one stable baseline snapshot, for example immediately after Scenario B's
proof that no Domain permission was granted:

```python
permission_baseline = stack.permission_snapshot()
```

Then make I3 meaningful:

```python
assert stack.permission_snapshot() == permission_baseline
checkpoints("I3-permission-registry-unchanged")
```

Equivalent placement is acceptable if the snapshot is captured before the
rejected paths whose mutation-freedom is being summarized.

Preserve the existing real per-rejection C/D/K assertions.

Preserve exact checkpoint count `34` unless the test structure deliberately
changes; if it changes, recalculate and lock the new exact count.

Required RED discipline:

1. mutate the permission registry in a test-local probe / temporarily alter the
   expected baseline so the new I3 assertion is shown capable of failing;
2. restore the intended acceptance setup;
3. run the connected AT GREEN.

Do not change production code to repair this finding.

---

# 12. DP-038 disposition

The independent V2 source review confirms the core design point:

> Domain Pack provenance, trust labels, loading and content do not create
> authority; trust is an additional restrictive ceiling over canonical
> validation, permission and approval owners.

Verified properties include:

```text
discovery != authorization
load != enable
allow_untrusted=True != authorization
trusted=True cannot bypass BLOCKED/source rules
activation requires fresh terminal validation
trust permission layer remains DENY/ABSTAIN only
canonical permission DENY cannot be widened by trust
cross-domain trust applies to actual transferred capability
memory/code/sensitive/destructive ceilings remain restrictive
prompt/configuration is not authorization evidence
no partial registry authorization state on rejected activation
no parallel security infrastructure
```

Therefore:

```text
DP_038=VERIFIED_EXISTING
```

The remaining V2 MINOR is acceptance-proof hygiene, not a DP failure.

---

# 13. AT-DP-038 disposition

The connected acceptance now uses real canonical/official in-memory components
and materially proves the approved boundary.

Its substantive runtime scenarios are sufficient to verify the acceptance
behavior.

The I3 tautology is redundant because real permission-registry before/after
assertions exist elsewhere in the same connected AT.

Therefore the behavioral acceptance disposition is:

```text
AT_DP_038=PASS
AT_DP_038_CHECKPOINTS=34
```

but:

```text
AT_DP_038_EVIDENCE_CLEAN=NO
```

until V2 MINOR-01 is corrected.

This distinction is the reason closure remains disallowed despite DP/AT
behavioral verification.

---

# 14. Test and gate evidence

The remediation execution record provides fresh repository-side evidence for:

```text
FOCUSED_TESTS=110
LOADER_VALIDATION_REGRESSIONS=315
PERMISSION_APPROVAL_REGRESSIONS=129
DOMAIN_API_REGRESSIONS=54
SDK_REGRESSIONS=50
DOMAIN_SUITE=8809
GLOBAL_SUITE=14364

RUFF=PASS
FORMAT=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS
WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED
```

The independent auditor separately verified:

```text
compileall of cmm/domains + tests/domains = PASS
archive/source syntax = PASS
archive hygiene = PASS
spec/plan/V1-report hashes = PASS
V1 -> V2 scope = PASS
event catalog 23/23 = PASS
no Phase 10.38 event added = PASS
no parallel security infrastructure = PASS
Phase 10.39 not started = PASS
```

Independent pytest execution in the isolated audit environment cannot collect
the Domain test modules because this runtime lacks the repository dependency:

```text
libcst
```

and network installation is unavailable.

This is an auditor-environment limitation, not a repository finding.

The V2 verdict does not depend on that limitation: the single remaining
finding is directly present in the committed acceptance source.

---

# 15. Architecture and scope disposition

V2 remains inside the deliberately narrow Phase 10.38 boundary.

No evidence was found of:

```text
PKI
key-management framework
secrets manager
RBAC
container/process sandbox
network sandbox
supply-chain platform
new security runtime
trust store
trust registry
new Domain loader
new validation pipeline
new permission engine
new approval engine
new Domain event
Phase 10.39 DomainArchitectureGuard
```

Result:

```text
ARCHITECTURE_SCOPE=PASS
NO_PARALLEL_SECURITY_INFRASTRUCTURE=PASS
PHASE10_39_NOT_STARTED=PASS
```

---

# 16. Closure decision

```text
BLOCKERS=0
MAJORS=0
MINORS=1

DP_038=VERIFIED_EXISTING
AT_DP_038=PASS
AT_DP_038_EVIDENCE_CLEAN=NO

CLOSURE_ELIGIBLE=NO
PHASE10_38_CLOSED=NO
PHASE10_39_START_ALLOWED=NO
```

The phase is one test-only remediation away from a closure-eligible re-audit.

---

# 17. Required V3 remediation scope

Remediate **only V2 MINOR-01**.

Expected changed code/test surface:

```text
tests/domains/test_domain_security_dp038_acceptance.py
```

Current-state documentation may also be updated conservatively after recording
the V2 audit result, but no production module requires a change.

Do not modify:

```text
cmm/domains/api.py
cmm/domains/permission_resolution.py
cmm/domains/trust_contracts.py
cmm/domains/trust_evaluator.py
```

unless a new RED demonstrates an unexpected direct dependency; if so, stop
rather than broadening the remediation silently.

After the I3 correction, rerun:

```text
AT-DP-038
Phase 10.38 focused suite
permission/approval regressions
Domain API regressions
tests/domains
global pytest
Ruff
format --check
compileall
git diff --check
event catalog 23/23
no-parallel-security-infrastructure gate
Phase 10.39-not-started gate
```

Commit all remediation.

Worktree must be clean.

Preserve quarantine stash.

Create a **new** exact-HEAD:

```text
phase-10.38-audit-v3.tar.gz
```

with a new recorded SHA-256.

Do not modify V1 or V2 bundles.

---

# 18. Re-audit conclusion

The V1 runtime-security defects are resolved.

Phase 10.38 now has the correct architectural boundary and the audited code
satisfies DP-038.

V2 does **not** require another security-design cycle or any broader hardening.

The only remaining issue is one tautological acceptance checkpoint:

```text
I3-permission-registry-unchanged
```

Fix that test evidence, regenerate exact-HEAD V3, and perform one final
independent re-audit before the docs-only closure commit.
