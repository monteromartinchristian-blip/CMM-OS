# CMM OS — Phase 10.52 — Independent Re-audit V3

**Audit date:** 2026-09-13
**Phase:** 10.52 — Mental Health Domain
**Audit type:** Independent exact-HEAD V3 remediation re-audit
**Verdict:** **FAIL — MAJOR-03 remains partially open at the permission-authority boundary**

---

# 1. Audited artifact

```text
BUNDLE=phase-10.52-mental-health-domain-reaudit-v3-905fd62260a3.tar.gz
AUDITED_REMEDIATION_HEAD=905fd62260a39e1b2a78e130278bd82aedaae249
AUDIT_BUNDLE_SHA256=4e0b367d3f7c02d28f29a3c0c604d4cfe4b1f9454d58ab728ce34b28df8ac767
ARCHIVE_MEMBERS=2301
```

Independent verification:

```text
CALCULATED_SHA256=4e0b367d3f7c02d28f29a3c0c604d4cfe4b1f9454d58ab728ce34b28df8ac767
SHA256_MATCH=YES
GZIP_INTEGRITY=PASS
GIT_ARCHIVE_COMMIT_ID=905fd62260a39e1b2a78e130278bd82aedaae249
HEAD_MATCH=YES
```

Result:

```text
BUNDLE_INTEGRITY=PASS
EXACT_HEAD_PROVEN=YES
```

---

# 2. Frozen evidence integrity

The V3 bundle preserves the approved design and implementation plan:

```text
SPEC_SHA256=e42f894f3fdf2483d5b4c34cb9d3255ab1fae8af8a109ed65e7b998f84c989f7
PLAN_SHA256=0e2c96ef6b21b1c415325599ff40186ea8513e22760157b4e4a24cc755936562
```

Historical audit evidence remains present:

```text
AUDIT_V1_SHA256=b75e644d2ef143a087990b27821c3403c362c4f7bb91cd74a4e5560c19a697f5
AUDIT_V2_SHA256=a915a2387e3c6d01eeb8f3fbafc2b8138cce89436de6b9051ec344f832bf1d5e
```

Phase 10.53 remains absent.

---

# 3. V2 → V3 exact scope

Independent archive comparison shows:

```text
ADDED_FILES=1
docs/audits/phase-10.52-independent-reaudit-v2.md

REMOVED_FILES=0

CHANGED_FILES=2
cmm/domains/mental_health/rules.py
tests/domains/test_mental_health_domain_dp052_acceptance.py
```

No unrelated production refactor was detected.

Result:

```text
V3_SCOPE=PASS
HISTORICAL_V2_AUDIT_PRESERVED=YES
ANTI_SCOPE_CREEP=PASS
```

---

# 4. Independent executable verification

The audit sandbox does not contain `libcst` and runs Python 3.13, which exposes
the already-documented pre-existing `@dataclass(slots=True)` + zero-argument
`super()` issue in shared Domain rule contracts.

The auditor therefore used only external audit-environment compatibility shims:

```text
import-only libcst shim outside the audited tree
runtime-only explicit-base-call patch for the pre-existing shared rule-contract issue
```

No audited file was modified.

Fresh independent V3 execution:

```text
CHECKPOINT_13_TESTS=10_PASSED
PHASE10_52_FOCUSED_TESTS=281_PASSED
ARCHITECTURE_PLUS_AT_DP_052=39_PASSED
CROSS_DOMAIN_PERMISSION_PRIVACY_REGRESSIONS=157_PASSED
COMPILEALL_CMM_CMM_AGENT_KERNEL_TESTS=PASS
```

The audit environment does not have Ruff installed; WorkBuddy reported zero new
Ruff/format debt on the changed files and baseline-equivalent global counts.

The V3 verdict below does not depend on Ruff or sandbox limitations. It rests on
a directly reproduced semantic authorization bypass.

---

# 5. What V3 fixed correctly

The V2 field/transfer laundering defect is genuinely remediated.

## 5.1 Per-field transfer binding

For:

```text
authorized_field = relevant
UNAUTHORIZED_SENSITIVE_FIELD = relevant
transfer evidence only for authorized_field
```

the exact V3 rule returns:

```text
status=APPLIED
included_fields=("authorized_field",)
unbound_fields=("UNAUTHORIZED_SENSITIVE_FIELD",)
provenance_references=("prov:A",)
```

The unbound sensitive field does not inherit provenance or authority.

## 5.2 Unrelated transfer

A valid transfer with:

```text
identifier=not_in_projection
```

produces:

```text
status=BLOCKED
included_fields=()
```

## 5.3 Rejected field cannot be laundered

With one accepted field and a second:

```text
private=True
```

or:

```text
transferable=False
```

the second field remains excluded while only the accepted field survives.

## 5.4 Deterministic duplicate evidence

Multiple accepted transfers for the same field produce a deterministic,
deduplicated provenance union.

Result:

```text
CROSS_DOMAIN_FIELD_TRANSFER_BINDING=PASS
UNBOUND_RELEVANT_FIELD_EXCLUDED=PASS
UNRELATED_TRANSFER_CANNOT_AUTHORIZE_PROJECTION=PASS
REJECTED_FIELD_NOT_LAUNDERED=PASS
CROSS_DOMAIN_PROVENANCE_PER_INCLUDED_FIELD=PASS
```

This closes the field-identity/provenance part of V2 MAJOR-03.

---

# 6. MAJOR-03 remains open — current canonical permission DENY can still be bypassed by supplied transfer evidence

## 6.1 Frozen requirement

The approved Phase 10.52 design requires cross-domain context to be imported
only when it is:

```text
relevant
authorized by canonical permissions
allowed by canonical privacy
compatible with current resolution/composition
purpose-minimized
provenance-preserving
```

The approved plan requires current permission/privacy/cross-domain authority to
be revalidated at the material boundary and stale authority to fail closed.

The immutable V2 audit required V3 to connect checkpoint 13 to current canonical
permission/privacy evidence and explicitly required:

```text
current canonical permission DENY
    -> corresponding field not included / path blocked
```

This is not a new V3 audit criterion.

## 6.2 Exact independent reproduction

Using the real Health + Mental Health permission registries from the V3 bundle:

```text
source_domain=domain:health
target_domain=domain:mental-health
resource_id=denied_field
capability=resource.read
```

the canonical `DomainPermissionResolver.resolve_cross_domain()` returns:

```text
permission_decision=DENY
granted_resources=()
```

with reasons including:

```text
source_cross_domain_denied
source_capability_denied
target_cross_domain_denied
target_capability_prohibited
```

The auditor then supplied a structurally valid canonical transfer for that
**same denied field** to `PurposeMinimizedCrossDomainRule`.

Exact V3 result:

```text
rule_status=APPLIED
included_fields=("denied_field",)
unbound_fields=()
provenance_references=("prov:denied",)
```

Therefore:

```text
CURRENT_CANONICAL_PERMISSION_DENY=YES
MATCHING_TRANSFER_PRESENT=YES
DENIED_FIELD_INCLUDED=YES
```

The permission decision and the transfer authority are still independent.

## 6.3 Why committed checkpoint 13d is a false positive

`test_checkpoint_13d_current_canonical_permission_deny_blocks_the_projection`
does correctly obtain the real canonical `DENY`.

However, it does not then present a transfer for the denied field to the
connected path.

Instead it:

```text
1. proves permission DENY separately;
2. omits transfer evidence for denied_field;
3. verifies that a field with no transfer is excluded.
```

That is already guaranteed by the V3 identifier-binding fix.

It does not prove:

```text
DENY + matching transfer
    -> blocked
```

The independent adversarial proves the opposite.

---

# 7. Positive permission control is not yet an authorization

V3 adds `_authorized_cross_domain_resolver()` by replacing canonical Health and
Mental Health policies in an in-memory registry.

This is a reasonable canonical fixture mechanism.

But the resulting real `DomainPermissionResolver` decision is:

```text
decision=APPROVAL_REQUIRED
granted_resources=()
approval_requirement=cross-domain:<request-id>
```

The test asserts only:

```python
authorized.decision is not PermissionOutcome.DENY
```

and then treats the projection transfer as authorized.

Canonical CMM permission semantics do not do that.

`DomainPermissionGate` explicitly maps an unconsumed `APPROVAL_REQUIRED`
decision to:

```text
PermissionGateOutcome.APPROVAL_REQUIRED
```

It becomes effective authority only after canonical approval validation and
consumption, producing:

```text
PermissionGateOutcome.APPROVAL_CONSUMED
```

A neighboring canonical implementation already demonstrates the correct
pattern in the Life Plan cross-domain tests:

```text
DomainPermissionResolver
+ DomainPermissionGate
+ ApprovalService
+ InMemoryApprovalRepository
+ create request from canonical requirement
+ approve
+ evaluate again
+ APPROVAL_CONSUMED
+ apply projection
```

Therefore:

```text
APPROVAL_REQUIRED_IS_AUTHORIZATION=NO
V3_POSITIVE_CONTROL_FULLY_AUTHORIZED=NO
```

---

# 8. Security significance

This is not a cosmetic acceptance issue.

`SECURITY.md` explicitly treats cross-domain permission leakage as a
security-relevant boundary.

The rule itself correctly validates structural transfer evidence, but a
`CrossDomainContextTransfer` is not the same object as a current permission
decision or a consumed approval.

V3 therefore still lacks connected proof that current permission authority is
what permits the concrete field transfer.

The required fix does not need a new permission engine or cross-domain engine.

---

# 9. Narrow V4 remediation required

Keep all V3 production field-binding behavior.

Do not reopen the already-correct identifier/provenance logic unless a RED test
proves a production seam is missing.

At minimum V4 must add a connected permission-gated projection path in the
acceptance using existing canonical components:

```text
DomainPermissionResolver
DomainPermissionGate
ApprovalService
InMemoryApprovalRepository
CrossDomainPermissionRequest
CrossDomainContextTransfer
```

Required connected cases:

### Positive approval-gated path

```text
canonical resolver -> APPROVAL_REQUIRED
no approval consumed -> projection cannot be treated as authorized

canonical approval request created
approval granted
DomainPermissionGate -> APPROVAL_CONSUMED
matching transfer for exact approved resource
-> field may enter projection
```

### DENY bypass adversarial

```text
real current canonical permission -> DENY
matching transfer object is nevertheless presented
-> connected permission-gated path must NOT pass/include the field
```

The test must not satisfy this by simply omitting the transfer.

### Binding requirements

The permission request / consumed approval / transfer must bind the same:

```text
source domain
target domain
resource identifier
purpose
actor/session where applicable
```

Do not replace real authority with a boolean.

No new runtime, registry, resolver, permission engine, privacy engine or
cross-domain engine is permitted.

---

# 10. Documentation follow-up

`docs/reference/mental-health-domain.md` still has the correct pre-audit status:

```text
PHASE10_52=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT
DP-052=PASS_REPORTED
AT-DP-052=PASS_REPORTED
CLOSURE_ELIGIBLE=UNKNOWN_PENDING_INDEPENDENT_REAUDIT
PHASE10_53=NOT_STARTED
```

However, its remediation-history prose is stale: it describes Re-audit V2 as a
future/external action and does not record the V2 FAIL or the V3 remediation
cycle.

`CONTRIBUTING.md` makes documentation part of definition of done.

This should be corrected in the same V4 remediation/documentation commit or a
dedicated remediation-doc commit before the next audit bundle.

Classification:

```text
DOCUMENTATION_FOLLOWUP=REQUIRED
```

This audit does not create a separate Major for that documentation issue.

`SECURITY.md` says security-sensitive changes **should** include threat analysis,
abuse cases, permission review, negative tests and documented limitations.
V3 contains meaningful negative tests and permission review. A concise
cross-domain threat/abuse note in the existing Mental Health reference would
strengthen the V4 evidence but is not classified as an independent blocker in
this audit.

---

# 11. Baseline-aware broader gate evidence

The implementation report records:

```text
TOTAL_ACCOUNTED_NODES=17255
PASSED=17130
FAILED=3
ENVIRONMENT_BLOCKED=122
```

The three failures were reproduced identically on the pristine V3 starting
baseline:

```text
1 SDK packager test
2 tests/execution/test_reorganization_e2e.py tests
```

The 122 environment-blocked recursive evidence nodes were also reproduced as
blocked on the pristine baseline under WorkBuddy's brokered sandbox.

The repository has historical precedent for baseline-aware audit treatment of
pre-existing/environment-only failures.

No V3-attributable broader regression was identified.

This does not convert environment-blocked nodes into PASS; it records only that
the observed delta is baseline-equivalent.

---

# 12. Closed findings remain closed

Independent V3 focused execution and source review preserve:

```text
MAJOR_01=CLOSED
MAJOR_02=CLOSED
MINOR_01=CLOSED
```

Specifically:

```text
strict sensitive boolean flags remain fail-closed
therapy source provenance remains real and required
stale memory binding remains invalid after permission revocation
```

No regression was found in those areas.

---

# 13. Architecture assessment

No new Mental Health-owned runtime, registry, resolver, permission engine,
privacy engine, cross-domain engine, memory store or safety engine was
introduced.

Phase 10.53 remains absent.

Result:

```text
ANTI_FRAGMENTATION=PASS
PHASE10_53_NOT_STARTED=YES
```

---

# 14. DP-052 assessment

Most of DP-052 is now implemented and independently demonstrated, including the
previously failing per-field cross-domain provenance/minimization behavior.

But DP-052 requires cross-domain context to be **permission-filtered under
current canonical authority**.

The exact V3 path can still include a field when the real current canonical
permission resolver says `DENY`, provided a matching transfer object is
supplied.

Therefore:

```text
DP-052=NOT_VERIFIED
```

---

# 15. AT-DP-052 assessment

The committed acceptance executes successfully:

```text
AT-DP-052_TEST_EXECUTION=PASS
```

and the independent auditor reproduced:

```text
PHASE10_52_FOCUSED_TESTS=281_PASSED
ARCHITECTURE_PLUS_AT=39_PASSED
```

However checkpoint 13d does not test the actual denied-transfer adversarial, and
the positive control stops at `APPROVAL_REQUIRED` rather than consumed approval.

Therefore:

```text
AT-DP-052=FAIL_INDEPENDENT_ADEQUACY
```

---

# 16. Independent Re-audit V3 verdict

```text
INDEPENDENT_REAUDIT_V3=FAIL

AUDITED_REMEDIATION_HEAD=905fd62260a39e1b2a78e130278bd82aedaae249
AUDIT_BUNDLE_SHA256=4e0b367d3f7c02d28f29a3c0c604d4cfe4b1f9454d58ab728ce34b28df8ac767

BUNDLE_INTEGRITY=PASS
V3_SCOPE=PASS
ANTI_FRAGMENTATION=PASS

FOCUSED_TESTS=281_PASSED
ARCHITECTURE_PLUS_AT=39_PASSED
CROSS_DOMAIN_PERMISSION_PRIVACY_REGRESSIONS=157_PASSED
COMPILEALL_FULL=PASS

BLOCKERS=0
MAJORS=1
MINORS=0

MAJOR_01=CLOSED
MAJOR_02=CLOSED
MAJOR_03=OPEN
MINOR_01=CLOSED

MAJOR_03_FIELD_TRANSFER_BINDING=PASS
MAJOR_03_CURRENT_PERMISSION_BINDING=FAIL
MAJOR_03_APPROVAL_CONSUMPTION=FAIL

DP-052=NOT_VERIFIED
AT-DP-052_TEST_EXECUTION=PASS
AT-DP-052=FAIL_INDEPENDENT_ADEQUACY

DOCUMENTATION_FOLLOWUP=REQUIRED

PHASE10_52=IMPLEMENTED_PENDING_REMEDIATION
PHASE10_53=NOT_STARTED
CLOSURE_ELIGIBLE=NO

PUSH=NO
MERGE=NO
```

Phase 10.52 must not be closed from HEAD
`905fd62260a39e1b2a78e130278bd82aedaae249`.

A narrow V4 remediation is required. It should primarily be an acceptance /
permission-gate connection correction plus documentation refresh, while
preserving the now-correct V3 per-field transfer binding.
