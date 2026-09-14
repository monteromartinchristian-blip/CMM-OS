# Phase 10.53 — Independent Re-audit V3 Redo

**Phase:** 10.53 — Neurodivergence Domain
**Audit type:** Independent re-audit of the trusted-authority V3 redo
**Audited implementation HEAD:** `5f779ad8573ca68974ba1d52e4a75b07691a5bb3`
**Audit bundle:** `phase-10.53-neurodivergence-domain-reaudit-v3-redo-5f779ad8573c.tar.gz`
**Bundle SHA-256:** `495f34150fea82b1687e5328185b6c34b32b7abf92097a550a064089250b7a81`
**Verdict:** **FAIL — one major remains**

```text
INDEPENDENT_REAUDIT_V3_REDO=FAIL
BLOCKERS=0
MAJORS=1
MINORS=1
MAJOR_01=OPEN
MINOR_01=OPEN
DP-053=NOT_VERIFIED
AT-DP-053_TEST_EXECUTION=PASS
AT-DP-053=FAIL_INDEPENDENT_ADEQUACY
CLOSURE_ELIGIBLE=NO
PHASE10_53=IMPLEMENTED_PENDING_REMEDIATION
PHASE11=NOT_STARTED
```

---

## 1. Executive summary

The V3 redo materially fixes the defect that caused the discarded V3 attempt
to fail.

The following boundary now works:

```text
caller-controlled metadata
-> cannot reconstruct trusted authority
-> cannot manufacture CONFIRMED
```

The implementation introduces a shared runtime-only
`ReasoningAuthorityContext`, keeps it separate from
`ReasoningRuleContext.metadata`, strips it from serialization, rejects
caller-side rehydration, and makes the Neurodivergence certainty rule ignore
metadata authority flags and canonical-looking serialized objects.

Independent execution confirms those protections.

However, the approved design amendment also requires the trusted authority
channel to preserve **source provenance** and bind an authoritative clinical
claim to the actual Health-owned evidence that established it.

That part is not implemented.

`ReasoningAuthorityContext` contains no source-provenance field, and
`build_reasoning_authority_context(...)` accepts a naked
`authoritative_claim_ids` tuple without a provenance-bearing Health authority
projection.

As a result, a trusted context can promote a clinical claim to `CONFIRMED`
without carrying any canonical source provenance for the clinical evidence.

This is a direct mismatch with the approved design amendment and keeps
`DP-053` open.

---

## 2. Bundle integrity

Independent verification:

```text
BUNDLE_SHA256=495f34150fea82b1687e5328185b6c34b32b7abf92097a550a064089250b7a81
GZIP_INTEGRITY=PASS
ARCHIVE_MEMBERS=2342
GIT_ARCHIVE_COMMIT=5f779ad8573ca68974ba1d52e4a75b07691a5bb3
HEAD_MATCH=PASS
```

The archive contains no:

```text
.git/
.pytest_cache/
__pycache__/
*.pyc
.venv/
```

---

## 3. Immutable artifact verification

Exact SHA-256 verification passed:

```text
ORIGINAL_PHASE10_53_SPEC=
81a5ac43f05eecb262aab184705a9e4a2573bac9ff3814a401bcb932f11de79b

TRUSTED_AUTHORITY_DESIGN_AMENDMENT=
449dbd25a3cfb5d112fc91067bde541e82d3aa3587f881c36e5c6211101bd7ee

ORIGINAL_PHASE10_53_PLAN=
2645cf94c0acb32d6ec7fde607e883b3910a44e5dac361ac15082d029231667c

V3_REDO_IMPLEMENTATION_PLAN=
1e18cbda93413d7c5c7cd4ebf77cd53d581267e36fc4e8734b9a46135958fac6

INDEPENDENT_AUDIT_V1=
9c1b7ecb541d09e6bc4f1d86eea40ff6e91a6a5b583e12cf6fe5ec61ee52f931

INDEPENDENT_REAUDIT_V2=
bbed4a15b79b1bada9187f35f7104a3948c63b8b000ac316cab9a62c865b4208
```

The discarded pre-redo V3 FAIL report is absent from the audited repository:

```text
DISCARDED_V3_FAIL_REPORT_PRESENT=NO
```

---

## 4. V2 → V3-redo scope

Direct archive comparison against the V2 audited bundle found:

```text
ADDED=3
REMOVED=0
CHANGED=13
```

Added:

```text
docs/audits/phase-10.53-independent-reaudit-v2.md
docs/superpowers/plans/2026-09-13-phase-10.53-trusted-authority-v3-redo-implementation-plan.md
docs/superpowers/specs/2026-09-13-phase-10.53-trusted-authority-channel-design-amendment.md
```

Changed production:

```text
cmm/cognitive/__init__.py
cmm/cognitive/reasoning_rule_contracts.py
cmm/domains/cognitive_integration.py
cmm/domains/neurodivergence/rules.py
```

Changed tests:

```text
tests/cognitive/test_reasoning_rule_contracts.py
tests/cognitive/test_reasoning_rule_serialization.py
tests/domains/test_domain_cognitive_integration.py
tests/domains/test_neurodivergence_domain_architecture.py
tests/domains/test_neurodivergence_domain_contracts.py
tests/domains/test_neurodivergence_domain_dp053_acceptance.py
```

Changed live documentation:

```text
docs/reference/domain-intelligence-requirements-matrix.md
docs/reference/neurodivergence-domain.md
docs/roadmap/phase-10-domain-intelligence.md
```

No Phase 11 file was changed.

No prohibited parallel authority owner was found.

```text
PARALLEL_AUTHORITY_REGISTRY=NONE
PARALLEL_AUTHORITY_STORE=NONE
PARALLEL_PERMISSION_ENGINE=NONE
PHASE11_BEHAVIOR_ADDED=NO
```

---

## 5. What the V3 redo fixes successfully

### 5.1 Runtime-only authority channel

The implementation adds:

```text
ReasoningAuthorityContext
```

to shared Cognitive contracts.

`ReasoningRuleContext` now contains:

```text
metadata
authority_context
```

as separate channels.

This matches the approved architecture.

### 5.2 Authority is stripped from serialization

`ReasoningRuleContext.to_dict()` does not serialize `authority_context`.

`ReasoningRuleContext.from_dict()` explicitly rejects caller-supplied
`authority_context`.

Independent probe:

```text
SERIALIZED_HAS_AUTHORITY_CONTEXT=False
CALLER_REHYDRATION=BLOCKED
```

This closes the serialized-authority reconstruction class that defeated the
discarded V3 attempt.

### 5.3 Metadata-only authority forgery is blocked

Independent probe supplied:

```text
permission_authority=True
fake permission decision id
fake approval state
Health-definitive-looking mapping
canonical-looking transfer
canonical-looking provenance
matching claim
matching purpose
```

with no trusted `authority_context`.

Observed:

```text
FORGED_METADATA_STATE=hypothesis
FORGED_METADATA_AUTH=False
```

Therefore:

```text
METADATA_ONLY_AUTHORITY_FORGERY=BLOCKED
```

### 5.4 Permission authority uses the typed runtime seam

`build_reasoning_authority_context(...)` accepts a typed
`PermissionGateResult` and rejects:

```text
DENY
APPROVAL_REQUIRED
non-cross-domain action
missing/invalid binding material
```

The trusted context preserves:

```text
actor
session
source domain
target domain
resource ids
purpose
permission decision id
permission outcome
approval-consumed state
```

### 5.5 Neurodivergence consumes trusted authority, not metadata authority

The clinical confirmation check now requires:

```text
authority_context.source_domain == domain:health
authority_context.target_domain == domain:neurodivergence
claim in authority_context.resource_ids
claim in authority_context.authoritative_claim_ids
purpose == authority_context.purpose
```

The old metadata authority booleans/mappings have no authority effect.

### 5.6 Exploratory behavior remains intact

Focused tests continue to pass for:

```text
EXPLORATORY_MODEL_INFERENCE=ALLOWED
WORKING_HYPOTHESES=ALLOWED
DIFFERENTIAL_REASONING=BALANCED_NOT_ADVERSARIAL
```

No blanket disclaimer behavior was introduced.

---

## 6. Independent test execution

The audit container is Python 3.13.5 and does not include LibCST.

To execute repository tests without altering the audited tree, the audit used
external-only compatibility shims under `/mnt/data/audit_shims_1053`:

```text
- import-only LibCST compatibility shim;
- pytest-only patch for the pre-existing Python 3.13
  dataclass(slots=True) + zero-argument super() issue in
  cmm/domains/rule_contracts.py.
```

No audited source file was modified.

### 6.1 Cognitive + integration focused gate

```text
124 passed
```

### 6.2 Full Phase 10.53 focused suite

```text
286 passed
```

### 6.3 Architecture + AT-DP-053 execution

```text
46 passed
```

Therefore:

```text
AT-DP-053_TEST_EXECUTION=PASS
```

### 6.4 Relevant-regression audit environment

A broader relevant-regression run reached the known audit-environment baseline
node after:

```text
601 passed
1 failed
```

Failure:

```text
tests/domains/test_domain_permission_gate.py::
test_orchestrator_execute_preserves_permission_authority_on_success
```

The same node independently fails on the V2 audited baseline in this audit
environment.

Therefore this is not evidence of a new V3-redo regression.

```text
KNOWN_AUDIT_ENV_BASELINE_NODE=CONFIRMED
NEW_FAILURE_FROM_THIS_NODE=NO
```

### 6.5 Compile

```text
python -m compileall -q cmm cmm_agent kernel tests
COMPILEALL=PASS
```

---

# 7. MAJOR-01 — trusted Health source provenance is not carried by the authority channel

**Severity:** MAJOR

**Status:** OPEN

## 7.1 Approved requirement

The approved trusted-authority design amendment states:

> The trusted authority channel must preserve source identity and provenance.

It further requires authoritative source-domain evidence to remain bound to:

```text
source domain
resource / claim identity
purpose
source provenance
current execution context
```

It also states that caller-supplied provenance is informational only until
canonical runtime code promotes the corresponding fact into the trusted
authority channel.

## 7.2 Implemented contract omits source provenance

The audited `ReasoningAuthorityContext` contains:

```text
actor_id
session_id
source_domain
target_domain
resource_ids
purpose
permission_decision_id
permission_outcome
approval_consumed
authoritative_claim_ids
```

It contains no:

```text
source provenance
Health evidence reference
canonical source artifact reference
provenance-bearing authoritative claim projection
```

Independent introspection confirmed:

```text
AUTH_FIELDS=(
  actor_id,
  session_id,
  source_domain,
  target_domain,
  resource_ids,
  purpose,
  permission_decision_id,
  permission_outcome,
  approval_consumed,
  authoritative_claim_ids
)
```

## 7.3 Builder accepts naked authoritative claim IDs

The production seam is:

```python
build_reasoning_authority_context(
    gate_result,
    *,
    authoritative_claim_ids=(...),
)
```

`authoritative_claim_ids` is a naked trusted tuple.

The builder does not accept or preserve a canonical Health evidence/provenance
projection for those claims.

The permission gate can prove that cross-domain access is authorized.

It does not prove which clinical source artifact established the claim.

## 7.4 Connected acceptance does not promote provenance into trusted authority

The connected AT calls the real Health diagnostic validator and obtains a
definitive semantic result.

It then converts that result into:

```text
authoritative_claim_ids=("clinical_status",)
```

before building the trusted context.

The canonical clinical transfer in the test contains
`ResourceProvenance`, but that provenance is not promoted into
`ReasoningAuthorityContext` and is not required for the positive confirmation
path.

The positive path therefore proves:

```text
real permission gate
+ Health definitive boolean semantics
+ naked trusted claim id
-> CONFIRMED
```

It does not prove:

```text
real permission gate
+ Health definitive status
+ canonical source provenance bound to that status
-> CONFIRMED
```

## 7.5 Independent behavioral proof

A `ReasoningAuthorityContext` was constructed with all required current fields
and **no provenance field exists to populate**.

The same clinical transition then produced:

```text
TRUSTED_NO_PROVENANCE_FIELD_STATE=confirmed
TRUSTED_NO_PROVENANCE_FIELD_AUTH=True
```

This is sufficient to demonstrate that trusted clinical confirmation is not
bound to source provenance.

## 7.6 Why this matters

The central caller-metadata forgery is fixed.

However, the source-authority guarantee is still weaker than the approved
design.

A permission decision for a generic Health resource plus a manually asserted
authoritative claim ID can authorize confirmation without tying that claim to
the actual Health-owned source evidence that established it.

That breaks the approved source-authority/provenance invariant and prevents
independent verification of `DP-053`.

## 7.7 Required remediation

Do not revert to metadata authority.

Do not add a registry/store/resolver.

Keep the runtime-only trusted channel.

The smallest remediation must make the trusted source-domain claim
provenance-bearing.

At minimum:

```text
1. bind each authoritative Health claim to canonical source provenance
   inside ReasoningAuthorityContext or its smallest shared typed projection;

2. ensure the trusted builder/integration path receives that provenance from
   canonical source-owner evaluation, not caller metadata;

3. require the Neurodivergence confirmation path to use the provenance-bound
   trusted claim;

4. extend the connected AT:
   definitive Health semantics + no trusted source provenance -> BLOCKED
   definitive Health semantics + canonical trusted source provenance -> CONFIRMED

5. preserve:
   AUTHORITY_SERIALIZATION=STRIPPED
   CALLER_REHYDRATION_OF_AUTHORITY=BLOCKED
   METADATA_ONLY_AUTHORITY_FORGERY=BLOCKED
```

This is a targeted remediation.

No new architecture redesign is required.

---

# 8. MINOR-01 — live Phase 10.53 status text is internally inconsistent

**Severity:** MINOR

**Status:** OPEN

The V3-redo live status is now:

```text
PHASE10_53=IMPLEMENTED_PENDING_INDEPENDENT_REAUDIT
```

but some live documentation still says:

```text
PHASE10_53=IMPLEMENTED_PENDING_INDEPENDENT_AUDIT
```

or:

```text
CLOSURE_ELIGIBLE=UNKNOWN_PENDING_INDEPENDENT_AUDIT
```

Observed examples:

```text
docs/reference/domain-core-conformance.md
docs/reference/mental-health-domain.md
docs/roadmap/phase-10-domain-intelligence.md
```

The status is not falsely closed, so this is documentary rather than
architectural.

Remediation:

```text
normalize the current Phase 10.53 live status to independent re-audit wording
without changing historical audit/closure evidence.
```

---

# 9. DP-053 / AT-DP-053 conclusion

The connected acceptance executes successfully:

```text
AT-DP-053_TEST_EXECUTION=PASS
```

It proves the new runtime-only metadata-forgery boundary.

However, its positive trusted clinical path does not prove the approved
source-provenance binding.

Therefore:

```text
DP-053=NOT_VERIFIED
AT-DP-053=FAIL_INDEPENDENT_ADEQUACY
```

This is not a claim that the acceptance test is broken.

It means the acceptance is not yet sufficient to prove the full approved
design invariant.

---

# 10. Final independent verdict

```text
INDEPENDENT_REAUDIT_V3_REDO=FAIL

BLOCKERS=0
MAJORS=1
MINORS=1

MAJOR_01=OPEN
MAJOR_01_NAME=TRUSTED_HEALTH_SOURCE_PROVENANCE_NOT_BOUND

MINOR_01=OPEN
MINOR_01_NAME=PHASE10_53_LIVE_STATUS_REAUDIT_WORDING_INCONSISTENT

METADATA_ONLY_AUTHORITY_FORGERY=BLOCKED
AUTHORITY_SERIALIZATION=STRIPPED
CALLER_REHYDRATION_OF_AUTHORITY=BLOCKED
TRUSTED_PERMISSION_INJECTION=PASS
REAL_PERMISSION_GATE_PATH=PASS
HEALTH_DEFINITIVE_SEMANTICS_EXERCISED=PASS
TRUSTED_SOURCE_PROVENANCE_BINDING=FAIL

EXPLORATORY_MODEL_INFERENCE=PASS
DIFFERENTIAL_REASONING=BALANCED_NOT_ADVERSARIAL

FOCUSED_COGNITIVE_TESTS=124_PASS
PHASE10_53_FOCUSED=286_PASS
ARCHITECTURE_PLUS_AT=46_PASS
KNOWN_AUDIT_ENV_BASELINE_NODE=CONFIRMED
COMPILEALL=PASS

DP-053=NOT_VERIFIED
AT-DP-053_TEST_EXECUTION=PASS
AT-DP-053=FAIL_INDEPENDENT_ADEQUACY
CLOSURE_ELIGIBLE=NO

PHASE10_53=IMPLEMENTED_PENDING_REMEDIATION
PHASE11=NOT_STARTED
```

The V3 redo is substantially better than V2 and correctly fixes the
caller-metadata authority-forgery class.

Phase 10.53 needs one focused source-provenance remediation and the small live
documentation normalization before a new exact-HEAD re-audit bundle.
