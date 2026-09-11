# Phase 10.50 — Domain Privacy Policies — Independent Audit V1

**Date:** 2026-09-11
**Audit type:** Independent ChatGPT audit
**Result:** `FAIL`
**Audited implementation HEAD:** `bdc6850c68b26c78e44e172a880a384acaa29046`
**Audit bundle:** `phase-10.50-domain-privacy-policies-audit-bdc6850c68b2.tar.gz`
**Audit bundle SHA-256:** `f862b5c20c0ec94c691a117a8dfaa96b16a97da1df5c06ec549d29ecf31bc7ce`
**Design spec:** `docs/superpowers/specs/2026-09-11-phase-10.50-domain-privacy-policies-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-09-11-phase-10.50-domain-privacy-policies-implementation-plan.md`

```text
INDEPENDENT_AUDIT_V1=FAIL
BLOCKERS=0
MAJORS=2
MINORS=0
DP-050=NOT_VERIFIED
AT-DP-050=FAIL
CLOSURE_ELIGIBLE=NO
```

---

## 1. Executive conclusion

Phase 10.50 is **not closure-eligible** at audited HEAD
`bdc6850c68b26c78e44e172a880a384acaa29046`.

The implementation gets the main architectural direction right:

- the canonical Phase 8 `PrivacyMetadata` / resolver / evaluator remain the
  privacy owners;
- no parallel Domain privacy engine, resolver, registry, store or runtime was
  introduced;
- `PrivacyPolicy.SENSITIVE` was not added;
- cross-domain permission authority remains separate from the privacy contract;
- `DomainDefinition.privacy_policy` is additive;
- the canonical declarative Domain Pack path is reused;
- all 12 implemented first-party Domains have the expected posture, with 11
  explicit policies and General as the explicit no-default case;
- the remote-approval projection is restrictive and does not widen
  `LOCAL_ONLY`.

However, two normative requirements are not satisfied:

1. the nested canonical `default_privacy` payload is not fail-closed at the
   Domain privacy declaration boundary, allowing unknown authority-like fields
   to be silently ignored and credential-like metadata to be serialized;
2. the Domain Trace change only adds the `PRIVACY_DECISION` reference category;
   no production path binds a real canonical `PrivacyDecision` to a resolvable
   trace reference, and the current tests explicitly remove status/reason
   evidence instead of proving that identity/status/reason codes remain
   auditable.

Both are `MAJOR` findings because they affect explicit security/contract and
traceability requirements in the approved design.

---

## 2. Bundle integrity and provenance

### 2.1 SHA-256

Independently recomputed:

```text
f862b5c20c0ec94c691a117a8dfaa96b16a97da1df5c06ec549d29ecf31bc7ce
```

This exactly matches the implementation-agent report.

Result:

```text
BUNDLE_SHA256=PASS
```

### 2.2 Archive integrity

The gzip stream validates and the archive extracts successfully.

The archive contains 2,250 members and no unsafe absolute / `..` traversal
paths and no symlink/hardlink entries.

Result:

```text
BUNDLE_INTEGRITY=PASS
ARCHIVE_PATH_SAFETY=PASS
```

### 2.3 Exact commit identity

`git get-tar-commit-id` over the decompressed `git archive` payload reports:

```text
bdc6850c68b26c78e44e172a880a384acaa29046
```

This exactly matches the claimed audited implementation HEAD.

Result:

```text
AUDITED_IMPLEMENTATION_HEAD=PASS
```

### 2.4 Frozen spec and plan provenance

The bundle contains the committed design and implementation plan with the
previously frozen hashes:

```text
DESIGN_SPEC_SHA256=d73752e3fc5b2699ad2df75ce1754d2588fa0ab2471e5c057b3f0fedb10ef808
IMPLEMENTATION_PLAN_SHA256=573f949798bae19a3afd25d4874078a44cf444c56b7427a9bd60cb623b6c12c5
```

Both match the approved pre-implementation artifacts.

Result:

```text
SPEC_PROVENANCE=PASS
PLAN_PROVENANCE=PASS
```

---

## 3. Independent execution evidence

### 3.1 Compile verification

The extracted audited snapshot passes:

```text
python3 -m compileall -q cmm
```

and the focused Phase 10.50 test modules compile.

Result:

```text
COMPILEALL_INDEPENDENT=PASS
```

### 3.2 Pytest re-execution limitation

The audit environment cannot import the full repository test graph because the
audit runtime does not have the repository dependency `libcst>=1.0` installed.

Independent focused pytest collection stops before Phase 10.50 tests execute:

```text
ModuleNotFoundError: No module named 'libcst'
```

The audited repository itself declares `libcst>=1.0` in `pyproject.toml`; an
attempt to install it in the isolated audit environment failed because network
access is disabled.

Therefore:

```text
FOCUSED_TESTS_AGENT_REPORTED=108 passed
GLOBAL_SUITE_AGENT_REPORTED=16850 passed
INDEPENDENT_PYTEST_REEXECUTION=NOT_REPRODUCED_ENVIRONMENT_DEPENDENCY_MISSING
```

This audit does **not** convert the agent-reported test counts into independent
test evidence. The V1 audit result is determined by direct code/spec inspection
and the two majors below, so this environment limitation does not mask a PASS.

---

## 4. Architecture review

### 4.1 Canonical privacy ownership

`cmm/domains/privacy_policy_contracts.py` imports and wraps canonical:

- `PrivacyMetadata`;
- `ProcessingLocation`.

The projection helper uses immutable `dataclasses.replace` only to add
`requires_approval=True` for a remote attempt where the Domain requires it.

It does not resolve effective privacy or evaluate operations.

Result:

```text
CANONICAL_PRIVACY_METADATA_REUSE=PASS
PARALLEL_PRIVACY_ENGINE=NONE
PARALLEL_PRIVACY_RESOLVER=NONE
PARALLEL_PRIVACY_REGISTRY=NONE
PARALLEL_PRIVACY_STORE=NONE
PARALLEL_PRIVACY_RUNTIME=NONE
```

### 4.2 Sensitivity/privacy separation

No `PrivacyPolicy.SENSITIVE` was added. First-party policies use canonical
`SensitivityLevel.SENSITIVE` / `INTERNAL` separately from canonical processing
policies.

Result:

```text
PRIVACY_POLICY_SENSITIVE_ENUM_ADDED=NO
SENSITIVITY_PRIVACY_SEPARATION=PASS
```

### 4.3 Permission boundary

`allow_cross_domain` is not part of the new `DomainPrivacyPolicy`, and the
acceptance uses existing Phase 10.15 permission components.

Result:

```text
CROSS_DOMAIN_PRIVACY_AUTHORITY_ADDED=NO
PHASE10_15_PERMISSION_OWNER_PRESERVED=PASS
```

### 4.4 Declarative path

`DomainDefinition` receives additive final field:

```python
privacy_policy: DomainPrivacyPolicy | None = None
```

`ParsedDomainPack.from_declarative_dict(...)` parses the declaration through
the existing pack path. `DomainManifest` does not gain a stored competing
privacy owner; `privacy_policy` is only admitted as a definition-level
declarative asset.

Result:

```text
DOMAIN_DEFINITION_ADDITIVE_FIELD=PASS
CANONICAL_PACK_PATH_REUSED=PASS
PARALLEL_PACK_PARSER=NONE
```

---

## 5. First-party policy review

The audited snapshot has exactly 11 first-party privacy declaration modules:

```text
health
relationships
reflection
concerns
parenthood
sport
life_plan
university
oppositions
languages
project
```

General intentionally has no privacy module / no Domain-wide default.

The declared postures match the approved matrix:

```text
health         LOCAL_ONLY / SENSITIVE
relationships  LOCAL_ONLY / SENSITIVE
reflection     LOCAL_ONLY / SENSITIVE
concerns       LOCAL_ONLY / SENSITIVE
parenthood     LOCAL_ONLY / SENSITIVE
sport          LOCAL_ONLY / SENSITIVE
life_plan      LOCAL_ONLY / SENSITIVE

university     REMOTE_ALLOWED / INTERNAL
oppositions    REMOTE_ALLOWED / INTERNAL
languages      REMOTE_ALLOWED / INTERNAL

project        LOCAL_PREFERRED / INTERNAL
general        privacy_policy=None
```

The sensitive group is local-only with remote disabled, premium disabled,
export disabled, cache allowed, and remote approval declared as an additional
obligation.

University/Oppositions/Languages are remote-capable only through the canonical
privacy + permission chain.

Project is local-preferred with remote enabled only as a policy possibility and
an added remote-approval obligation.

Result:

```text
FIRST_PARTY_DOMAINS=12
FIRST_PARTY_DECLARED_PRIVACY_POLICIES=11
GENERAL_DOMAIN_PRIVACY_DEFAULT=NONE
FIRST_PARTY_POLICY_MATRIX=PASS
```

---

# 6. Findings

## MAJOR-01 — Nested `default_privacy` is not fail-closed at the Domain declaration boundary

**Severity:** `MAJOR`

### Requirement

The approved design requires:

```text
Validation must fail closed for:
- malformed PrivacyMetadata;
- unknown fields;
- invalid metadata;
- credential/secret-like declarative fields;
- attempts to represent cross-domain permission in the privacy policy.
```

It also requires public serialization to contain:

```text
no credentials
no provider API keys
```

### Audited implementation

`DomainPrivacyPolicy.from_dict(...)` validates unknown fields only at the
wrapper level and then delegates the nested payload directly to:

```python
PrivacyMetadata.from_mapping(mapping["default_privacy"])
```

in:

```text
cmm/domains/privacy_policy_contracts.py:294-321
```

The canonical Phase 8 `PrivacyMetadata.from_mapping(...)` intentionally reads
known values with `payload.get(...)` but does not reject unknown keys and copies
`payload["metadata"]` without the Domain declarative credential-key filter:

```text
cmm/cognitive/privacy.py:500-540
```

### Independent proof

The canonical parser independently accepted this payload during audit:

```python
PrivacyMetadata.from_mapping({
    "schema_version": 1,
    "policy": "remote_allowed",
    "allowed_processing_locations": ["local", "remote"],
    "allow_remote": True,
    "allow_cross_domain": True,
    "metadata": {
        "api_key": "SHOULD_NOT_BE_IN_DECLARATIVE_PACK",
    },
})
```

Observed:

```text
PRIVACY_FROM_MAPPING_ACCEPTED_UNKNOWN=remote_allowed True
METADATA={'api_key': 'SHOULD_NOT_BE_IN_DECLARATIVE_PACK'}
```

`allow_cross_domain` is silently ignored rather than rejected, while the
credential-like metadata is retained and would be serialized by the outer
`DomainPrivacyPolicy.to_dict()`.

The constructor path also accepts an already-created canonical
`PrivacyMetadata` whose `metadata` contains such credential-like keys, because
`DomainPrivacyPolicy.__post_init__` only applies the secret-key filter to
`DomainPrivacyPolicy.metadata`, not to `default_privacy.metadata`.

### Why this is a major

This violates the approved fail-closed Domain Pack declaration boundary and the
explicit no-credentials/no-provider-API-keys contract. It also allows an
authority-like `allow_cross_domain` declaration to appear inside the nested
privacy block and be silently discarded rather than rejected, which is exactly
the ambiguity the design prohibited.

### Required remediation

Without modifying canonical Phase 8 behavior globally, Phase 10.50 must validate
the nested Domain-declarative `default_privacy` payload at its own boundary.

At minimum:

1. define the exact canonical serialized `PrivacyMetadata` field set for the
   Domain declaration adapter;
2. reject unknown nested keys before calling `PrivacyMetadata.from_mapping`;
3. reject cross-domain / authority-like nested keys explicitly through the
   unknown-field rule;
4. recursively reject credential/secret-like keys inside
   `default_privacy.metadata`;
5. enforce the same protection for the direct-constructor path where
   `default_privacy` is already a `PrivacyMetadata`;
6. add RED→GREEN tests proving:
   - nested `allow_cross_domain` is rejected;
   - nested unknown fields are rejected;
   - nested `metadata.api_key` / `token` / `credentials` are rejected;
   - direct-constructor `PrivacyMetadata(metadata={"api_key": ...})` is rejected;
   - valid canonical `PrivacyMetadata` still round-trips exactly.

Do **not** modify Phase 8 `PrivacyMetadata.from_mapping` unless a separate
repository-level requirement explicitly authorizes that broader change.

---

## MAJOR-02 — `PRIVACY_DECISION` trace references are not bound to an auditable canonical privacy decision

**Severity:** `MAJOR`

### Requirement

The approved design requires:

```text
trace stores/reference-links the canonical privacy decision or its existing safe
reference/evidence representation;

privacy decision identity/status/reason codes must remain auditable.
```

`AT-DP-050` scenario K must prove that the canonical privacy decision or a safe
decision reference is observable through the existing Domain Trace seam.

### Audited implementation

Production adds only:

```python
PRIVACY_DECISION = "privacy_decision"
```

to `DomainTraceReferenceKind`:

```text
cmm/domains/trace_contracts.py:394-427
```

No production Phase 10.50 path constructs a `PRIVACY_DECISION` reference from
an actual `PrivacyDecision`. A production search finds the enum member but no
producer/adapter/bridge that binds it to the result of
`evaluate_privacy_operation(...)`.

The focused trace test manually constructs:

```python
DomainTraceReference(
    ref_id="privacy-decision:1",
    kind=DomainTraceReferenceKind.PRIVACY_DECISION,
    domain_id="domain:health",
)
```

and explicitly asserts that the real decision's status/reason evidence is
**not** present in the reference payload:

```text
tests/domains/test_domain_privacy_policy_trace_integration.py:67-82
```

`AT-DP-050` scenario K repeats the same pattern with a synthesized:

```text
privacy-decision:<resource-id>
```

reference:

```text
tests/domains/test_domain_privacy_policy_dp050_acceptance.py:646-671
```

The `PrivacyDecision` contract itself has no canonical persistent ID. No
Phase 10.50 producer creates a content-bound/reference-bound identity, and no
resolver/evidence owner is shown that can resolve the synthetic reference back
to status/reason evidence.

### Why this is a major

The implementation proves that Domain Trace can *represent the label*
`privacy_decision`; it does not prove that a real privacy decision is actually
traceable.

A free-form `ref_id` manufactured in the test is not a reference to canonical
evidence unless a production binding exists. Therefore the explicit requirement
that decision identity/status/reason codes remain auditable is not satisfied,
and `AT-DP-050` scenario K is not independently verified.

### Required remediation

Reuse the existing Domain Trace/evidence seam and keep it reference-only. Do not
create a new privacy trace store.

The remediation must establish a real production binding from a canonical
`PrivacyDecision` to safe, resolvable/content-bound trace evidence. The exact
shape should follow the existing trace/evidence architecture discovered in the
repo.

The remediation must prove all of:

1. a real canonical `PrivacyDecision` produces or is bound to a deterministic
   safe evidence identity/reference;
2. the reference is inserted through the existing Domain Trace assembly /
   inventory seam, not manually fabricated only in tests;
3. status and reason code remain auditable through the referenced safe evidence
   representation;
4. sensitive raw inputs, provider payloads, prompts, source documents, secrets,
   chain-of-thought and complete `PrivacyMetadata` payloads are not copied into
   Domain Trace;
5. the reference is domain-bound and deterministic;
6. stale/fake/mismatched privacy-decision references fail closed wherever the
   existing trace validation architecture supports binding validation;
7. `AT-DP-050` scenario K exercises the actual production binding path.

If the existing canonical trace/evidence contracts cannot express this safely,
stop and produce a narrowly scoped remediation design amendment before changing
architecture.

---

## 7. `DP-050` assessment

The central Domain Privacy Defaults design is substantially present:

- immutable declarative wrapper;
- canonical privacy reuse;
- additive `DomainDefinition` attachment;
- first-party defaults;
- monotonic projection;
- separation from permissions and sensitivity;
- no parallel privacy subsystem.

But the Design Point includes strict declarative safety and auditable Domain
Trace behavior. Because MAJOR-01 and MAJOR-02 remain, the independent audit
cannot mark the Design Point verified.

```text
DP-050=NOT_VERIFIED
```

---

## 8. `AT-DP-050` assessment

Scenarios A–J are structurally represented in the connected acceptance and use
the intended canonical components.

Scenario K does not prove the required production trace binding; it manually
constructs an unbound reference.

The acceptance suite also lacks the adversarial nested-declarative cases exposed
by MAJOR-01.

Therefore:

```text
AT-DP-050=FAIL
```

This does not mean every acceptance assertion is wrong. It means the acceptance
does not prove all normative `DP-050` behavior required for closure.

---

## 9. Documentation assessment

The pre-audit documentation correctly avoids claiming closure:

```text
PHASE10_50=IMPLEMENTED_PENDING_INDEPENDENT_AUDIT
DP-050=PASS_REPORTED
AT-DP-050=PASS_REPORTED
```

No premature `PHASE10_50=CLOSED` marker was found in the Phase 10.50 status.

The reference and matrix accurately describe the intended architecture, but the
trace documentation currently overstates implementation by saying privacy
decisions are not omitted and carry canonical decision identity by reference.
That statement must be corrected or made true during remediation.

Result:

```text
PRE_AUDIT_STATUS_DISCIPLINE=PASS
TRACE_DOCUMENTATION_ACCURACY=REQUIRES_REMEDIATION
```

---

## 10. Security assessment

Positive findings:

- no new provider/model routing authority in first-party privacy modules;
- no `allow_cross_domain` field in `DomainPrivacyPolicy`;
- no duplicate privacy engine/resolver/store/runtime;
- no secret-bearing first-party default metadata observed;
- trace reference shape does not embed raw `PrivacyMetadata`.

Negative finding:

- MAJOR-01 permits credential-like data in nested
  `default_privacy.metadata` at the Domain declarative boundary.

Result:

```text
SECURITY=FAIL_MAJOR_01
```

---

## 11. Independent audit verdict

```text
INDEPENDENT_AUDIT_V1=FAIL

BLOCKERS=0
MAJORS=2
MINORS=0

MAJOR_01=NESTED_DEFAULT_PRIVACY_NOT_FAIL_CLOSED
MAJOR_02=PRIVACY_DECISION_TRACE_REFERENCE_NOT_CANONICALLY_BOUND

DP-050=NOT_VERIFIED
AT-DP-050=FAIL
CLOSURE_ELIGIBLE=NO

AUDITED_IMPLEMENTATION_HEAD=bdc6850c68b26c78e44e172a880a384acaa29046
AUDIT_BUNDLE_SHA256=f862b5c20c0ec94c691a117a8dfaa96b16a97da1df5c06ec549d29ecf31bc7ce
```

Phase 10.50 must enter a **Remediation V1** cycle limited to these findings.

Do not close Phase 10.50 and do not start Phase 10.52/10.53 or Phase 11.

After remediation:

1. rerun focused Phase 10.50 tests;
2. rerun relevant regressions;
3. rerun Domain suite;
4. rerun global suite;
5. rerun Ruff/baseline-aware Ruff;
6. rerun format;
7. rerun `compileall`;
8. rerun `git diff --check`;
9. rerun architecture guards;
10. rerun strengthened `AT-DP-050`;
11. commit all remediation;
12. leave worktree clean;
13. generate a **new** exact-HEAD TAR.GZ;
14. compute a **new** SHA-256;
15. submit the new bundle for Independent Re-audit V2.

The V1 bundle must remain unchanged as historical audit evidence.
