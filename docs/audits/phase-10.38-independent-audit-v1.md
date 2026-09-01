# CMM OS — Phase 10.38 Independent Audit V1

**Date:** 2026-09-01
**Phase:** 10.38 — Security — Domain Pack Authority Boundary
**Independent auditor:** ChatGPT
**Audited branch:** `feature/phase-10-domain-intelligence`
**Audited HEAD:** `52d6bdeb57868e58976da0adcb5c08120d7fcfb7`
**Bundle:** `phase-10.38-audit-v1.tar.gz`
**Bundle SHA-256:** `d5e1c32997d02a5d36f0792e0c2777f163da7572bf33a1a9ffd5755bdbe2a212`
**Bundle size:** `5163842` bytes
**Bundle members:** `1996`
**Verdict:** **FAIL**

---

## 1. Final audit result

```text
PHASE10_38_INDEPENDENT_AUDIT_V1=FAIL

BLOCKERS=1
MAJORS=2
MINORS=3

AUDITED_HEAD=52d6bdeb57868e58976da0adcb5c08120d7fcfb7
AUDIT_BUNDLE_SHA256=d5e1c32997d02a5d36f0792e0c2777f163da7572bf33a1a9ffd5755bdbe2a212

DP_038=NOT_VERIFIED
AT_DP_038=FAIL
CLOSURE_ELIGIBLE=NO

PHASE10_39_NOT_STARTED=PASS
NO_PARALLEL_SECURITY_INFRASTRUCTURE=PASS
DOMAIN_EVENT_CATALOG_23_OF_23=PASS

NEXT=PHASE10_38_REMEDIATION_FOR_INDEPENDENT_AUDIT_V2
```

Phase 10.38 is **not closure-eligible**.

The implementation is architecturally close to the approved design and correctly avoids broad Phase 11 hardening, but one direct authority-ceiling bypass remains in the cross-domain path, terminal validation evidence is not enforced fail-closed, and the connected acceptance overclaims atomic authorization-state evidence.

No Phase 10.39 work may begin.

---

## 2. Audit object integrity

The audit object was obtained as the original stored Google Drive file after direct chat binary mounting was unavailable.

Independent SHA-256 over the downloaded bytes:

```text
d5e1c32997d02a5d36f0792e0c2777f163da7572bf33a1a9ffd5755bdbe2a212
```

This exactly matches the SHA-256 recorded before and after the user's Drive upload.

Independent exact-HEAD extraction from the Git archive itself:

```bash
gzip -dc phase-10.38-audit-v1.tar.gz | git get-tar-commit-id
```

returned:

```text
52d6bdeb57868e58976da0adcb5c08120d7fcfb7
```

The same commit is present in the archive PAX header.

Therefore:

```text
BUNDLE_SHA256_BINDING=PASS
GIT_ARCHIVE_HEAD_BINDING=PASS
AUDITED_HEAD=52d6bdeb57868e58976da0adcb5c08120d7fcfb7
```

### Archive safety

Direct inspection of the original TAR, before auditor-generated files existed, found:

```text
TAR_MEMBERS=1996
ABSOLUTE_PATHS=0
PARENT_TRAVERSAL_PATHS=0
SYMLINKS=0
HARDLINKS=0
TRACKED_.git=0
TRACKED_.venv=0
TRACKED___pycache__=0
TRACKED_.pyc=0
```

The archive uses one prefix:

```text
CMM-OS-phase-10.38/
```

Archive hygiene:

```text
AUDIT_ARCHIVE_CONTENT=PASS
```

---

## 3. Frozen spec and plan binding

The frozen spec inside the audited TAR has SHA-256:

```text
4d5dff07e45049605775052784da2a438a11adcfae0e451ad23d63d20f684b74
```

The frozen implementation plan inside the audited TAR has SHA-256:

```text
9ad961faadc345ef45b3e2b3d443118163fd5fcd3063f1e94555f6a08d853f18
```

Both match the approved artifacts exactly.

```text
SPEC_BINDING=PASS
PLAN_BINDING=PASS
```

---

## 4. Architectural audit

The implementation correctly follows the approved narrow architecture in several important respects.

### PASS — no parallel security infrastructure

The active production tree contains no new equivalents of:

```text
DomainSecurityEngine
DomainSecurityRuntime
DomainSecurityStore
DomainSecurityRegistry
DomainTrustStore
DomainTrustRegistry
DomainSecurityLoader
DomainTrustLoader
DomainSecurityEventBus
DomainSecurityTraceStore
```

Result:

```text
NO_PARALLEL_SECURITY_INFRASTRUCTURE=PASS
```

### PASS — Phase 10.39 not pre-implemented

No production `DomainArchitectureGuard` exists.

```text
PHASE10_39_NOT_STARTED=PASS
```

### PASS — Domain Events invariant

Independent AST inspection of the canonical event catalog found:

```text
GENERAL_EVENT_COUNT=23
GENERAL_EVENT_UNIQUE_COUNT=23
domain.session.resumed=ABSENT
```

Result:

```text
DOMAIN_EVENT_CATALOG_23_OF_23=PASS
NO_PHASE1038_EVENT_ADDED=PASS
```

### PASS — normal permission path is restrictive-only

`DomainPermissionResolver.resolve(...)` adds trust evidence only when the trust evaluation returns `DENY`.

The pure trust permission evaluator returns only:

```text
DENY
ABSTAIN
```

and never returns:

```text
ALLOW
APPROVAL_REQUIRED
```

This preserves the core rule that trust cannot create a grant in the normal single-domain path.

### PASS — explicit activation happens after fresh validation/trust decision

For a loaded Domain with an applicable trust policy, `DefaultDomainAPI.enable_domain(...)` performs fresh canonical validation and evaluates trust before calling the canonical registry enable mutation.

The implementation does not introduce auto-enable or a second loader.

These architectural passes do not override the findings below.

---

# 5. BLOCKER-01 — Cross-domain authority ceiling bypass

**Severity:** BLOCKER
**Primary file:** `cmm/domains/permission_resolution.py`
**Relevant audited lines:** approximately `225–356`, especially `316–356`

## Defect

The canonical cross-domain resolver correctly evaluates the actual requested capability against the source and target **Domain permission policies**.

For example, when a cross-domain request asks for:

```text
MEMORY_WRITE
```

the canonical source/target policy evaluation uses:

```python
request.capability
```

However, the Phase 10.38 trust integration does not do the same.

For both source and target trust policies it constructs only:

```python
DomainPermissionRequest(
    ...,
    PermissionCapability.DOMAIN_CROSS_ACCESS,
    ...
)
```

The trust layer therefore checks:

```text
allow_external_access
```

but never checks the **actual capability being transferred**.

Independent source probe:

```text
cross-domain trust DOMAIN_CROSS_ACCESS action occurrences = present
cross-domain trust action=request.capability occurrences = 0
```

## Concrete bypass

A request can satisfy all of the following:

```text
request.capability = MEMORY_WRITE

source canonical policy allows:
    DOMAIN_CROSS_ACCESS
    MEMORY_WRITE

target canonical policy allows:
    inbound DOMAIN_CROSS_ACCESS
    MEMORY_WRITE

source/target trust:
    allow_external_access=True
    allow_memory_write=False
```

The Phase 10.38 trust call evaluates only:

```text
DOMAIN_CROSS_ACCESS
→ allow_external_access=True
→ ABSTAIN
```

It never evaluates:

```text
MEMORY_WRITE
→ allow_memory_write=False
→ DENY trust.memory_write_denied
```

If no unrelated canonical reason denies the request, `resolve_cross_domain(...)` can return an allowed cross-domain decision despite the explicit trust ceiling denying memory writes.

The same defect class applies to cross-domain use of actual capabilities governed by:

```text
allow_code_execution
allow_sensitive_resources
allow_destructive_operations
```

when external cross-domain access itself is allowed.

## Violated approved invariants

This directly violates:

```text
TRUST != AUTHORITY
effective authority =
    canonical permission authority
    ∩ trust policy ceiling
    ∩ approval evidence
```

and DP-038 requirement:

```text
denied memory/external/sensitive/destructive capabilities remain denied
```

It also violates the implementation plan requirement that source and target trust ceilings apply to cross-domain resolution without widening authority.

## Why BLOCKER

This is not test incompleteness alone.

It is a live runtime path in the audited production implementation where an explicit trust denial can be bypassed.

For a security-boundary phase, that prevents verification of the principal Design Point.

## Required remediation

Do **not** create new infrastructure.

Inside the existing cross-domain resolver:

1. preserve the current trust check for `DOMAIN_CROSS_ACCESS`;
2. when `request.capability != DOMAIN_CROSS_ACCESS`, also evaluate each applicable source/target `DomainTrustPolicy` against the **actual `request.capability`**;
3. preserve the actual request context required for the capability:
   - operation ID;
   - workflow ID;
   - resource ID/kind;
   - sensitivity level;
   - source/target domain identity;
4. any actual-capability trust `DENY` must enter the existing `reasons` collection and make the final cross-domain decision `DENY`;
5. trust must still never return or synthesize `ALLOW`.

Required REDs include at minimum:

```text
cross-domain MEMORY_WRITE
allow_external_access=True
allow_memory_write=False
canonical source+target allow
→ DENY trust.memory_write_denied
```

and:

```text
cross-domain OPERATION_EXECUTE
allow_external_access=True
allow_code_execution=False
canonical source+target allow
→ DENY trust.code_execution_denied
```

Add equivalent parameterized coverage for sensitive and destructive/high-impact capabilities supported by the existing canonical vocabulary.

---

# 6. MAJOR-01 — Non-terminal validation states can satisfy activation trust

**Severity:** MAJOR
**Primary files:**
- `cmm/domains/trust_evaluator.py`
- `cmm/domains/api.py`
- inherited contract: `cmm/domains/validation_contracts.py`

## Defect

The canonical validation enum contains:

```text
PENDING
RUNNING
PASSED
WARNING
FAILED
ERROR
```

The Phase 10.38 evaluator defines only:

```python
_BLOCKING_VALIDATION_STATUSES = {
    DomainValidationStatus.FAILED,
    DomainValidationStatus.ERROR,
}
```

and considers validation acceptable unless:

- status is FAILED/ERROR;
- there is a blocking finding;
- `security_valid` is false.

Therefore:

```text
PENDING
RUNNING
```

are not rejected by the trust evaluator.

The API first checks:

```python
validation.is_install_allowed
```

but the inherited property likewise rejects only `FAILED` and `ERROR` plus invalid flags.

It does not require a terminal `PASSED` or `WARNING` status.

Consequently a structurally coherent `PENDING` or `RUNNING` result whose flags are true can pass the Phase 10.38 activation boundary.

This affects:

1. explicit trust-policy activation;
2. the trusted-INTERNAL/no-policy compatibility path, because that path skips `evaluate_domain_trust(...)` after the same permissive `is_install_allowed` check.

## Violated approved requirement

The frozen implementation plan explicitly requires validation evidence to be acceptable only when:

```text
validation.status is PASSED or WARNING
```

and explicitly requires:

```text
status not PASSED/WARNING
→ fail closed
```

The audited implementation does not implement that rule.

## Required remediation

Use a terminal allowlist, not a failure blacklist.

Trust evaluator:

```text
valid terminal statuses = {PASSED, WARNING}
anything else = trust.validation_failed
```

API activation must independently preserve the same terminality rule for **all** activation paths, including the narrow trusted-INTERNAL/no-policy compatibility path.

Required REDs:

```text
PENDING → activation denied
RUNNING → activation denied
registry snapshot unchanged
Domain remains disabled
reason = trust.validation_failed
```

Cover both:

```text
explicit trust policy
trusted INTERNAL compatibility
```

where applicable.

Do not weaken canonical validation contracts globally unless a separate RED proves that the canonical owner itself must change.

---

# 7. MAJOR-02 — AT-DP-038 claims atomic authorization-state evidence it does not assert

**Severity:** MAJOR
**Primary file:** `tests/domains/test_domain_security_dp038_acceptance.py`

## Defect

The connected acceptance is substantial and uses real canonical components, but several named checkpoints are labels rather than proofs.

### B4

The test records:

```python
checkpoints("B4-no-approval-created")
```

without retaining or inspecting the `InMemoryApprovalRepository` used by the `ApprovalService`.

There is no assertion proving that no approval request was created.

### I3

The test records:

```python
checkpoints("I3-permission-registry-unchanged")
```

with no state snapshot or assertion at that checkpoint.

### I4

The test records:

```python
checkpoints("I4-no-approval-consumed")
```

again without retaining the approval repository and without any assertion.

### I2

The test describes loaded-state coherence but checks only:

```python
assert apx.get_domain("external-pack", "0.1.0") is not None
```

That is registry/API presence, not exact loader-result coherence.

### Aggregate count

The test ends with:

```python
assert stack.checkpoints.count >= 24
```

which proves only a lower bound of labels reached, not exact closure-proof parity.

## Why MAJOR

The approved connected acceptance is itself a required phase gate.

The frozen spec requires it to demonstrate, using real canonical components:

```text
registry unchanged
loaded candidate/result coherent
permission registry unchanged
approval repository has no newly consumed authorization
```

The audited test **claims** these through checkpoint names, but does not prove all of them.

This matters especially because the acceptance failed to detect BLOCKER-01 and MAJOR-01.

The implementation's green `AT-DP-038` test result therefore cannot be accepted as closure evidence.

## Required remediation

Keep the existing connected scenario; do not replace it with mocks.

1. retain one real `InMemoryApprovalRepository` on the `_Dp038Stack`;
2. pass that exact repository to the real `ApprovalService`;
3. snapshot approval state before rejected paths and assert no new approval request/consumption afterward using canonical public repository/service APIs;
4. snapshot `DomainPermissionRegistry` state/policies before rejection and assert unchanged after rejection;
5. use `DeclarativeDomainLoader.get_loaded(...)` to assert exact candidate/checksum/version/load-result coherence before and after rejected activation;
6. replace label-only I3/I4 with real assertions;
7. preserve explicit registry before/after snapshots for each relevant rejection;
8. report and enforce the exact final committed checkpoint count rather than relying only on `>=`.

The remediated AT must also include the BLOCKER-01 and MAJOR-01 REDs so that the connected proof exercises those corrected boundaries.

---

# 8. MINOR-01 — `DomainTrustDecision` blocking-reason set is caller-overridable

**Severity:** MINOR
**File:** `cmm/domains/trust_contracts.py`
**Audited lines:** approximately `330–410`

## Defect

`DomainTrustDecision` declares:

```python
_BLOCKING_REASON_CODES: frozenset[str] = frozenset(...)
```

inside a dataclass without `ClassVar`.

Dataclasses therefore treat it as an instance field.

A direct constructor caller can supply a different `_BLOCKING_REASON_CODES` value, including an empty set, weakening the constructor invariant that forbids:

```text
activation_allowed=True
+
trust.blocked / trust.validation_failed / other activation-blocking reason
```

## Impact

Current runtime trust evaluation constructs the decision internally, and the decision is evidence rather than an authorization token.

No audited runtime authorization path consumes an attacker-supplied `DomainTrustDecision`.

Therefore this is not currently an authority bypass and is classified MINOR.

## Required remediation

Make the set non-instance configuration:

```python
ClassVar[frozenset[str]]
```

or a module-level immutable constant.

Add a regression proving the invariant cannot be caller-overridden.

---

# 9. MINOR-02 — Nested trust metadata is not actually JSON-serializable

**Severity:** MINOR
**File:** `cmm/domains/trust_contracts.py`

## Defect

Both contracts deep-freeze JSON-safe metadata.

Nested mappings become immutable proxy mappings.

However, serialization uses only:

```python
"metadata": dict(self.metadata)
```

That unfreezes only the outer level.

Nested immutable mappings remain proxy objects, so a structure that was accepted as JSON-safe can produce a `to_dict()` result that standard:

```python
json.dumps(...)
```

cannot serialize.

The repository already contains canonical deep-unfreeze helpers used by other Domain contracts.

## Violated requirement

The frozen spec/plan requires new public trust contracts to be:

```text
immutable
strict
JSON-safe
round-trippable
deep-frozen
```

The audited implementation satisfies immutability but not full nested JSON serialization.

## Required remediation

Reuse the canonical deep-unfreeze helper already present in Domain contract infrastructure.

Do not create a second generic serializer.

Add nested metadata tests for both:

```text
DomainTrustPolicy
DomainTrustDecision
```

including:

```python
json.dumps(contract.to_dict())
restored = Contract.from_dict(contract.to_dict())
```

with nested mapping/list content.

---

# 10. MINOR-03 — ROADMAP has contradictory stale 10.38 release-direction status

**Severity:** MINOR
**File:** `ROADMAP.md`
**Audited line:** approximately `628`

## Defect

Other Phase 10.38 documentation correctly describes implementation as pending independent audit, but the `Release direction` section still states:

```text
Phase 10.38 — Security is the next milestone and has not started
```

This contradicts the audited repository state.

## Required remediation

After recording V1 findings, update the line conservatively to the actual state, for example:

```text
Phase 10.38 — Security is implemented; independent audit V1 found
remediation requirements and the phase remains open.
```

Do not mark:

```text
closed
audited PASS
closure eligible
```

until a subsequent independent audit says so.

---

## 11. DP-038 independent disposition

The approved DP-038 requires that Domain Pack trust cannot widen authority and that denied memory/external/sensitive/destructive capabilities remain denied.

BLOCKER-01 provides a direct cross-domain path where an explicit trust ceiling over the actual capability is not applied.

Therefore:

```text
DP_038=NOT_VERIFIED
```

This is not a documentation-only failure.

Runtime remediation is required.

---

## 12. AT-DP-038 independent disposition

The implementation's connected acceptance contains substantial real-component coverage and several valid security checks.

However:

- it does not exercise the cross-domain actual-capability trust bypass;
- it does not reject PENDING/RUNNING validation evidence;
- its B4/I3/I4 atomicity checkpoints do not contain the claimed assertions.

Therefore the independent audit cannot accept the test as closure proof.

```text
AT_DP_038=FAIL
```

This means:

```text
implementation test may have been green
!=
independent acceptance verified
```

---

## 13. Test/gate evidence disposition

The audit bundle contains the committed tests and the implementation was delivered as test-clean.

The independent auditor attempted a fresh dynamic run in the isolated audit environment.

### Independent compile check

```text
compileall cmm/domains tests/domains = PASS
```

### Independent pytest limitation

Fresh pytest execution in the audit runtime could not proceed because the isolated environment does not contain the repository dependency:

```text
libcst
```

and network package installation is unavailable in the audit environment.

This is an **auditor-environment limitation**, not a Phase 10.38 finding.

The audit does not classify missing `libcst` as a repository defect.

Because the audit already finds reproducible static/runtime-path defects in the committed code, this limitation does not affect the FAIL verdict.

A V2 candidate must nevertheless provide the normal fresh repository-side focused, regression, Domain-subsystem and global-suite evidence required by the frozen plan.

---

## 14. Security/scope items independently verified as preserved

The audit found no evidence that Phase 10.38 improperly expanded into platform hardening.

Preserved:

```text
no PKI implementation
no key manager
no secrets manager
no RBAC
no OS/container sandbox
no new security runtime
no trust store
no trust registry
no new Domain loader
no new validation pipeline
no new permission engine
no new approval engine
no new Domain event
no Phase 10.39 DomainArchitectureGuard
```

The remediation must remain equally narrow.

---

## 15. Required remediation scope for V2

Remediate **only**:

```text
BLOCKER-01
MAJOR-01
MAJOR-02
MINOR-01
MINOR-02
MINOR-03
```

Do not redesign Phase 10.38.

Do not add Phase 11 hardening.

Do not add a trust store, security engine, new loader, new validator, new permission engine, PKI, sandbox, RBAC, or new Domain Event.

### Minimum V2 verification matrix

Required focused RED/GREEN additions:

```text
1. cross-domain MEMORY_WRITE trust ceiling
2. cross-domain OPERATION_EXECUTE trust ceiling
3. cross-domain sensitive ceiling
4. cross-domain destructive/high-impact ceiling
5. PENDING validation fails activation
6. RUNNING validation fails activation
7. trusted INTERNAL no-policy path also rejects non-terminal validation
8. connected AT snapshots permission registry
9. connected AT snapshots approval repository / no consumption
10. connected AT verifies exact loader state coherence
11. blocking reason set cannot be constructor-overridden
12. nested metadata json.dumps + round-trip
13. ROADMAP release-direction consistency
```

Then rerun:

```text
Phase 10.38 focused suite
loader/discovery/validation regressions
permission/approval regressions
Domain API regressions
Phase 10.35 SDK regressions
tests/domains
global pytest
Ruff
format --check
compileall
git diff --check
event 23/23 gate
no parallel security infrastructure gate
Phase 10.39-not-started gate
```

All remediation must be committed.

Worktree must be clean.

Generate a **new** exact-HEAD bundle:

```text
phase-10.38-audit-v2.tar.gz
```

using:

```text
git archive
```

Do not overwrite or mutate V1.

Record the new SHA-256.

---

## 16. Closure decision

```text
BLOCKERS=1
MAJORS=2
MINORS=3

DP_038=NOT_VERIFIED
AT_DP_038=FAIL

CLOSURE_ELIGIBLE=NO
PHASE10_38_CLOSED=NO
PHASE10_39_START_ALLOWED=NO
```

The next canonical step is:

```text
record this independent audit V1
→ commit the audit report only
→ worktree clean
→ prepare remediation prompt bound to the new audit-report HEAD
→ TDD remediation only for V1 findings
→ full gates
→ new exact-HEAD V2 bundle
→ independent ChatGPT audit V2
```

No closure documentation commit is allowed yet.

---

## 17. Audit conclusion

Phase 10.38 has the **right architectural size**.

The independent audit does not recommend adding broader security mechanisms.

The central problem is narrower and more important:

> the trust ceiling must be applied to the actual capability at every authorization boundary, including cross-domain resolution.

Once the six V1 findings are remediated and independently re-audited, Phase 10.38 can be reconsidered for closure without expanding its scope.
