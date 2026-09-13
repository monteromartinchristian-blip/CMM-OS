# CMM OS — Phase 10.53 — Independent Re-audit V2

**Audit date:** 2026-09-13
**Phase:** 10.53 — Neurodivergence Domain
**Audit type:** Independent exact-HEAD V2 remediation re-audit
**Verdict:** **FAIL — MAJOR-01 remains open**

---

# 1. Audited artifact

```text
BUNDLE=phase-10.53-neurodivergence-domain-reaudit-v2-f5c51d6b08a8.tar.gz
AUDITED_IMPLEMENTATION_HEAD=f5c51d6b08a8254e9f40d1f5bf62d89a727c4db8
AUDIT_BUNDLE_SHA256=4cffe34a4510c943b82b1c5a6ede192e0ff6c57d83c9ee096022557395032586
ARCHIVE_MEMBERS=2339
```

Independent verification:

```text
CALCULATED_SHA256=4cffe34a4510c943b82b1c5a6ede192e0ff6c57d83c9ee096022557395032586
SHA256_MATCH=YES
GZIP_INTEGRITY=PASS
GIT_ARCHIVE_COMMIT_ID=f5c51d6b08a8254e9f40d1f5bf62d89a727c4db8
HEAD_MATCH=YES
```

Result:

```text
BUNDLE_INTEGRITY=PASS
EXACT_HEAD_PROVEN=YES
```

---

# 2. Immutable evidence integrity

The V2 bundle preserves the approved specification, plan, and Audit V1 report:

```text
SPEC_SHA256=81a5ac43f05eecb262aab184705a9e4a2573bac9ff3814a401bcb932f11de79b
PLAN_SHA256=2645cf94c0acb32d6ec7fde607e883b3910a44e5dac361ac15082d029231667c
AUDIT_V1_SHA256=9c1b7ecb541d09e6bc4f1d86eea40ff6e91a6a5b583e12cf6fe5ec61ee52f931
```

No historical audit/spec/plan artifact was rewritten.

Result:

```text
SPEC_INTEGRITY=PASS
PLAN_INTEGRITY=PASS
AUDIT_V1_INTEGRITY=PASS
```

---

# 3. Exact V1 → V2 remediation scope

The auditor compared the original V1 and V2 `git archive` TAR.GZ artifacts
directly, without relying on previously extracted test trees.

Exact archive delta:

```text
ADDED_FILES=1
docs/audits/phase-10.53-independent-audit-v1.md

REMOVED_FILES=0

CHANGED_FILES=4
cmm/domains/neurodivergence/rules.py
docs/roadmap/phase-10-domain-intelligence.md
tests/domains/test_neurodivergence_domain_contracts.py
tests/domains/test_neurodivergence_domain_dp053_acceptance.py
```

No shared/core production file was changed.

No parallel infrastructure was introduced.

Result:

```text
V2_SCOPE=PASS
CORE_PRODUCTION_MUTATION=NONE
ANTI_FRAGMENTATION=PASS
```

---

# 4. Correction to Audit V1 — MINOR-01 was a false positive

Audit V1 reported that:

```text
.pytest_cache/v/cache/nodeids
```

had been modified and committed.

That statement was incorrect.

The V2 re-audit rechecked both **original exact TAR.GZ artifacts**:

```text
phase-10.53-neurodivergence-domain-audit-c55d8733842c.tar.gz
phase-10.53-neurodivergence-domain-reaudit-v2-f5c51d6b08a8.tar.gz
```

Direct archive inspection proves:

```text
V1_ARCHIVE_CONTAINS_.pytest_cache/v/cache/nodeids=NO
V2_ARCHIVE_CONTAINS_.pytest_cache/v/cache/nodeids=NO
```

The previous finding came from an extracted V1 audit tree that had subsequently
been modified by the auditor's own pytest execution, which generated
`.pytest_cache`.

Therefore:

```text
MINOR_01=WITHDRAWN_FALSE_POSITIVE
```

The historical V1 report remains immutable. This V2 report is the corrective
audit record.

---

# 5. Independent executable verification

The audit environment is Python 3.13 and lacks `libcst`.

As in the previous audit, only external audit-environment shims were used:

```text
/mnt/data/audit_shims_1053
```

They provide:

```text
- import-only libcst compatibility;
- runtime-only compatibility for the pre-existing Python 3.13
  @dataclass(slots=True) + zero-argument super() issue.
```

No audited source file was modified.

Fresh independent results:

```text
AT_DP_053_FILE=30_PASSED
PHASE10_53_FOCUSED_SUITE=275_PASSED
ARCHITECTURE_PLUS_AT=45_PASSED
COMPILEALL_CMM_CMM_AGENT_KERNEL_TESTS=PASS
```

Relevant sibling/canonical sample:

```text
502 PASSED
1 FAILED
```

The single failure remains:

```text
tests/domains/test_domain_permission_gate.py::
test_orchestrator_execute_preserves_permission_authority_on_success
```

and was already independently reproduced against the pre-10.53 Phase 10.52
baseline in the same audit environment.

Therefore:

```text
RELEVANT_REGRESSION_NEW_FAILURES=0
KNOWN_AUDIT_ENV_BASELINE_FAILURE=1
```

---

# 6. V1 original free-form mapping defect — materially improved

V2 removes the old rule path in which this alone could grant clinical
authority:

```python
{
    "documented": True,
    "domain": "domain:health",
    "source_ref": "fabricated:1",
}
```

The V2 focused suite independently proves:

```text
FABRICATED_FREE_FORM_HEALTH_MAPPING_TO_CONFIRMED=BLOCKED
FABRICATED_FREE_FORM_HEALTH_MAPPING_TO_RULED_OUT=BLOCKED
```

V2 also validates `source_domain` through canonical `DomainId`.

The original Audit V1 example:

```text
source_domain="not-a-domain"
```

now fails closed.

Result:

```text
FREE_FORM_AUTHORITY_MAPPING_DEFECT=REMEDIATED
INVALID_SOURCE_DOMAIN=BLOCKED
```

---

# 7. V1 MINOR-02 — stale roadmap wording closed

The live detailed roadmap now states:

```text
AT-DP-053 is implemented and PASS_REPORTED;
independent verification remains pending.
```

The stale sentence describing `AT-DP-053` as a future/unpassed acceptance gate
is gone.

Historical earlier-phase evidence remains intact.

Therefore:

```text
MINOR_02=CLOSED
```

---

# 8. Connected canonical positive path — PASS

V2 adds a real connected positive acceptance path using:

```text
DomainPermissionResolver
DomainPermissionGate
ApprovalService
canonical approval requirement conversion
CrossDomainContextTransfer
ResourceProvenance
```

The connected acceptance demonstrates:

```text
resolver -> APPROVAL_REQUIRED

gate before approval -> APPROVAL_REQUIRED
transfer admission -> ()

canonical approval created/granted

gate after approval -> APPROVAL_CONSUMED
transfer admission -> exact matching Health transfer

certainty rule -> CONFIRMED
```

It also demonstrates:

```text
same transfer without permission authority -> BLOCKED

real canonical DENY -> transfer not admitted -> BLOCKED
```

The connected AT behavior itself is valid.

Result:

```text
CONNECTED_HEALTH_AUTHORITY_HAPPY_PATH=PASS
DENY_REGRESSION=PASS
APPROVAL_REQUIRED_REGRESSION=PASS
APPROVAL_CONSUMED_REGRESSION=PASS
```

---

# 9. MAJOR-01 residual A — permission authority remains an unbound caller boolean

**Severity:** MAJOR
**Status:** OPEN

The remediation introduces `_canonical_health_authority(request)`.

It correctly requires:

```text
canonical DomainId(source=health)
CrossDomainContextTransfer
ResourceProvenance
matching claim identifier
matching purpose
non-private transfer
transferable=True
```

However, current permission authority is still represented inside the
certainty request as:

```python
"permission_authority": True
```

and evaluated only through a strict boolean check:

```python
if not _strict_flag(request, "permission_authority"):
    return None
```

No `PermissionGateResult`, authority-reference record, permission decision ID,
approval evidence, or other canonical gate output is bound by the production
certainty helper.

The repository already has a canonical pattern for retaining gate authority:

```text
PermissionGateResult.to_authority_reference_dict()
```

which carries at least:

```text
permission_decision_id
outcome
approval requirement/request/decision references
```

Neurodivergence certainty promotion currently does not use it.

### Independent external adversarial

The auditor created, outside the Phase 10.53 tests:

```text
- a valid DomainId("health");
- a structurally valid CrossDomainContextTransfer;
- a syntactically valid ResourceProvenance;
- a matching claim id;
- a matching purpose;
- permission_authority=True;
```

No `DomainPermissionResolver` was executed.

No `DomainPermissionGate` was executed.

No approval was created or consumed.

The production helper still returned:

```text
certainty_state=confirmed
authoritative_evidence=True
health_authority_supplied=True
```

Therefore the V1 defect has moved from:

```text
free-form authority mapping
```

to:

```text
free-form permission-authority boolean
+ caller-constructible canonical-shaped transfer/provenance
```

The boundary remains forgeable through production metadata.

Required result was:

```text
CURRENT_PERMISSION_AUTHORITY_MUST_BE_CANONICALLY_BOUND
```

Actual result is:

```text
CURRENT_PERMISSION_AUTHORITY_CAN_BE_ASSERTED_BY_BOOLEAN
```

Therefore:

```text
MAJOR_01_CURRENT_PERMISSION_BINDING=FAIL
```

---

# 10. MAJOR-01 residual B — the Health payload is documented, not definitively confirmed

**Severity:** MAJOR, same root finding
**Status:** OPEN

The V2 positive Health transfer carries:

```python
{
    "documented_diagnosis": True,
    "provenance": ResourceProvenance(...).to_dict(),
}
```

The Neurodivergence rule treats that payload as sufficient Health clinical truth
for:

```text
HYPOTHESIS / IN_EVALUATION -> CONFIRMED
```

But the canonical Health Domain's own diagnostic rule explicitly requires:

```text
confirmed
AND documented
AND evidence
AND NOT provisional
```

for a diagnosis to be definitive.

Canonical Health helper:

```text
validate_diagnostic_claim(
    evidence=True,
    documented=True,
    confirmed=False,
    provisional=False
)
```

independently returns:

```text
is_definitive=False
may_present_as_definitive=False
supported_category=provisional_diagnosis
```

The Health Domain documentation/tests expressly state:

```text
documented + evidence without explicit confirmation is NOT definitive
```

V2's `documented_diagnosis=True` transfer therefore does not prove the stronger
Health semantic required for Neurodivergence `CONFIRMED`.

The remediation has introduced a Neurodivergence interpretation of Health data
that is stronger than Health's own definitive-diagnosis rule.

Therefore:

```text
MAJOR_01_HEALTH_DEFINITIVE_STATUS_BINDING=FAIL
```

This is not a request for a new Health status subsystem.

The remediation must reuse Health's existing semantics.

---

# 11. Why the connected AT does not close the residual

The new connected acceptance test correctly generates:

```text
APPROVAL_CONSUMED
```

before passing the transfer to the rule.

That proves the **test's happy path** is correctly gated.

It does not prove the production certainty rule cannot be invoked with:

```text
permission_authority=True
```

and a hand-constructed canonical-shaped transfer.

A second unit test explicitly constructs its positive request as:

```text
permission_authority=True
transfers=(canonical-shaped Health transfer,)
```

without running the permission gate.

The production rule cannot distinguish that unit request from the connected
acceptance request.

Therefore the V2 AT covers a valid connected path, but it does not close the
adversarial authority-injection path.

---

# 12. Required V3 remediation

Do not add a Neurodivergence authority engine.

Do not weaken exploratory reasoning.

Do not add a new Health registry.

The next remediation must close **both** residuals of MAJOR-01.

## 12.1 Bind current permission authority to the canonical gate evidence

Replace the unbound boolean authority assertion with the existing canonical
authority representation or an existing connected composition seam.

At minimum, the production certainty path must no longer accept:

```text
permission_authority=True
```

as sufficient proof of permission.

Prefer the repository's existing authority-reference shape derived from:

```text
PermissionGateResult.to_authority_reference_dict()
```

or another already-canonical equivalent discovered during remediation.

The positive path must carry an actual current permission decision identity and,
when approval-gated, the matching approval references/outcome.

Required RED:

```text
canonical-shaped transfer
+ canonical-shaped provenance
+ permission_authority=True only
+ NO gate evidence
-> CONFIRMED blocked
```

Required connected GREEN:

```text
real DomainPermissionResolver
-> real DomainPermissionGate
-> APPROVAL_CONSUMED / ALLOW
-> canonical authority reference
-> exact admitted Health transfer
-> CONFIRMED allowed
```

## 12.2 Bind CONFIRMED to Health's own definitive-diagnosis semantics

A Health-owned record being merely documented is not enough.

The positive transfer/projection must carry a Health-derived status that is
definitive under the **existing Health rule semantics**.

Do not duplicate Health's clinical logic inside Neurodivergence.

Required RED:

```text
Health documented diagnosis
+ evidence/provenance
+ confirmed=False / no definitive Health verdict
-> Neurodivergence CONFIRMED blocked
```

Required GREEN:

```text
Health canonical definitive verdict
derived under existing Health semantics
+ canonical provenance
+ current permission authority
-> Neurodivergence CONFIRMED allowed
```

## 12.3 Preserve already-correct V2 behavior

Must remain green:

```text
free-form authority mapping blocked
RULED_OUT free-form path blocked
invalid DomainId blocked
exploratory inference allowed
balanced differential reasoning
DENY + matching transfer blocked
APPROVAL_REQUIRED without consumption blocked
APPROVAL_CONSUMED exact admission
field-transfer binding
proposal-first sensitive memory
SENSITIVE privacy
anti-fragmentation
```

---

# 13. Findings status

```text
BLOCKERS=0
MAJORS=1
MINORS=0

MAJOR_01=OPEN
MAJOR_01_FREE_FORM_MAPPING=REMEDIATED
MAJOR_01_DOMAIN_ID_VALIDATION=REMEDIATED
MAJOR_01_CONNECTED_GATE_HAPPY_PATH=PASS
MAJOR_01_CURRENT_PERMISSION_BINDING=FAIL
MAJOR_01_HEALTH_DEFINITIVE_STATUS_BINDING=FAIL

MINOR_01=WITHDRAWN_FALSE_POSITIVE
MINOR_02=CLOSED
```

---

# 14. DP-053 assessment

The implementation continues to satisfy the exploration-friendly half of
DP-053.

However, the central epistemic boundary still permits a caller to create an
effective `CONFIRMED` state without proving:

```text
current canonical permission authority
```

and without proving:

```text
Health-definitive confirmed diagnostic status
```

Therefore:

```text
DP-053=NOT_VERIFIED
```

---

# 15. AT-DP-053 assessment

The connected acceptance executes successfully:

```text
AT_DP_053_TEST_EXECUTION=PASS
```

The new connected Health happy path is useful and real.

But AT-DP-053 still lacks the adversarial that proves:

```text
permission_authority=True alone cannot impersonate gate authority
```

and its positive transfer does not demonstrate Health's own definitive
diagnostic semantics.

Therefore:

```text
AT-DP-053=FAIL_INDEPENDENT_ADEQUACY
```

---

# 16. Independent Re-audit V2 final verdict

```text
INDEPENDENT_REAUDIT_V2=FAIL

AUDITED_IMPLEMENTATION_HEAD=f5c51d6b08a8254e9f40d1f5bf62d89a727c4db8
AUDIT_BUNDLE_SHA256=4cffe34a4510c943b82b1c5a6ede192e0ff6c57d83c9ee096022557395032586

BUNDLE_INTEGRITY=PASS
SPEC_INTEGRITY=PASS
PLAN_INTEGRITY=PASS
AUDIT_V1_INTEGRITY=PASS

V2_SCOPE=PASS
ANTI_FRAGMENTATION=PASS

PHASE10_53_FOCUSED_SUITE=275_PASSED
AT_DP_053_FILE=30_PASSED
ARCHITECTURE_PLUS_AT=45_PASSED
COMPILEALL_FULL=PASS
RELEVANT_REGRESSION_NEW_FAILURES=0

BLOCKERS=0
MAJORS=1
MINORS=0

MAJOR_01=OPEN
MINOR_01=WITHDRAWN_FALSE_POSITIVE
MINOR_02=CLOSED

DP-053=NOT_VERIFIED
AT-DP-053_TEST_EXECUTION=PASS
AT-DP-053=FAIL_INDEPENDENT_ADEQUACY
CLOSURE_ELIGIBLE=NO

PHASE10_53=IMPLEMENTED_PENDING_REMEDIATION
PHASE11=NOT_STARTED

NEXT=SCOPED_REMEDIATION_V3

PUSH=NO
MERGE=NO
```

Phase 10.53 must not be closed.

The next workflow step is:

```text
commit this immutable Re-audit V2 report
-> verify clean repository
-> prepare V3 scoped remediation
-> bind clinical certainty to canonical gate authority evidence
-> bind CONFIRMED to Health's own definitive-status semantics
-> preserve V1/V2 historical evidence
-> rerun gates
-> commit remediation
-> generate new exact-HEAD V3 bundle
-> independent Re-audit V3
```
