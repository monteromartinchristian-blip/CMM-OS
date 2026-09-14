# CMM OS — Phase 10.33 Independent Audit V8

**Date:** 2026-08-29
**Audited branch:** `feature/phase-10-domain-intelligence`
**Audited HEAD:** `f3b9bf8f2a6b59212954eed25dcac454bae24e5a`
**Implementation base:** `b72d47b59d64b5afcc07c9f3883cbf8d9ce5b979`
**Audit V7 report HEAD:** `244a96a00ea2c30076647877fb8eb47729f462be`
**Bundle SHA-256:** `da37bfed9e149d0dc7a8fa6be94637f74ec427da5119786abd866ecd85bfb739`
**Bundle source:** `git archive f3b9bf8f2a6b59212954eed25dcac454bae24e5a`
**Verdict:** FAIL — runtime blocker closed; one test-policy minor remains

## Audit summary

- BLOCKERS: 0
- MAJORS: 0
- MINORS: 1
- The V7 runtime credential-policy blocker is independently confirmed remediated.
- The canonical runtime security contract is coherent and accurately scoped.
- Phase 10.33 remains `Implemented, pending independent re-audit`.
- Phase 10.34 must not be advanced until the remaining minor is closed and re-audited.

## V7 remediation disposition

| V7 finding | V8 status | Result |
|---|---|---|
| B2 — canonical credential detection policy | PASS | One canonical immutable registry exists in `cmm/domains/credential_policy.py`; Domain Event contracts and adapters consume it. |
| B2 — additional high-confidence credential families | PASS | All 20 canonical signatures were independently exercised and detected. |
| Kernel credential boundary | PASS | Independent probes confirmed no tested canonical credential reached `kernel.events.Event` or `emitted_events`. |
| DomainId credential boundary | PASS | Syntactically valid credential-shaped slugs tested independently fail at the Domain Event privacy boundary. |
| Runtime security-contract clarification | PASS | The design now explicitly distinguishes normative no-credential requirements, deterministic high-confidence enforcement, and the non-goal of arbitrary unknown-secret/entropy detection. |

---

## m8 — regression matrix is not actually registry-driven

**Severity:** MINOR
**Scope:** V7 preventive test architecture / security-regression maintainability

The approved V7 design states:

```text
Adding a credential family to the canonical registry automatically subjects it
to the full event-boundary regression matrix across all public event fields,
deserialization paths, and Kernel publication gates.
```

The implementation does not currently provide that automatic coupling.

`tests/domains/test_domain_events_audit_v7_regressions.py` defines a separate:

```python
SYNTHETIC_CREDENTIALS = [...]
```

and nearly all boundary-matrix parametrizations iterate that list, while the runtime policy separately defines:

```python
HIGH_CONFIDENCE_CREDENTIAL_SIGNATURES
```

There is no assertion that the test fixture families and registry signature names are equal, and no parametrization driven from the canonical registry.

### Independently confirmed gap

The canonical policy currently has:

```text
20 signature entries
```

but the V7 synthetic fixture list does not directly exercise five registry entries as named signature cases:

```text
generic_key_pattern
authorization_header
bearer_token
bearer_assignment
credential_assignment
```

Earlier V1/V2 regression suites do exercise the underlying structural behaviors, and independent V8 probes confirmed all 20 runtime signatures function correctly. Therefore this is **not** a runtime privacy blocker.

However, adding a future `CredentialSignature` to the canonical registry would not automatically fail or expand the V7 full-boundary matrix if the separate fixture list were left unchanged. That contradicts the explicit preventive guarantee introduced specifically to avoid another provider-by-provider audit cycle.

### Required remediation

Keep this remediation test-focused and minimal.

A suitable design is:

```text
canonical test-vector mapping keyed by exact CredentialSignature.name
+
assert set(test_vectors) == {sig.name for sig in HIGH_CONFIDENCE_CREDENTIAL_SIGNATURES}
+
derive the full event-boundary parametrization from the registry names
```

For each registry entry provide:

```text
one synthetic positive example
one safe near-miss where meaningful
```

Then the existing matrix should iterate those registry-linked cases so that:

```text
adding a registry signature without a matching test vector => immediate test failure
```

The five currently indirect structural/generic signatures must enter this registry-linked gate as well.

No production credential-detection change is required unless the new tests reveal a real runtime failure.

Do not add entropy heuristics or external scanners.

---

## Independently confirmed PASS evidence

### Bundle integrity

Independent bundle inspection confirmed:

```text
SHA256=da37bfed9e149d0dc7a8fa6be94637f74ec427da5119786abd866ecd85bfb739
TAR_ENTRIES=1842
BAD_PATHS=0
SYMLINK_OR_HARDLINK_ENTRIES=0
```

The bundle contains no:

```text
.env
.git
.venv
tracked __pycache__
tracked .pyc
credential/private-key filename path
path traversal
absolute path
```

Audit reports V1 through V7 are present.

The internal `AUDIT-MANIFEST.txt` exactly matches the uploaded manifest content before the external trailing SHA line.

### Audit-specific regression execution

Using an isolated package loader to avoid the sandbox's missing optional `libcst` dependency, the exact audit regression suites V1 through V7 were executed directly from the V8 bundle:

```text
676 passed
```

No audit-regression failure occurred.

### AT-DP-033

Independent static accounting confirms:

```text
AT_DP_033_LOGICAL_CHECKPOINTS=66
AT_DP_033_RANGE=CP-01..CP-66
```

An isolated-loader execution produced:

```text
91 passed
1 environment-induced failure
```

The sole failure was CP-32's package-level `from cmm.domains import ...` check because the isolated loader intentionally replaces `cmm.domains.__init__` to avoid the unavailable sandbox `libcst` dependency.

The repository-native V8 evidence reports:

```text
AT_DP_033_PYTEST_CASES=92 PASS
```

This sandbox limitation is not counted as a repository finding.

### Canonical credential policy

Independent inspection confirms:

```text
CREDENTIAL_POLICY_FAMILIES=20
registry type=tuple
CredentialSignature=frozen + slots
signature names unique
patterns precompiled
no network dependency
no external secret-scanning dependency
no entropy heuristic
```

Independent synthetic probes provided one matching value for each of the 20 canonical signature entries and confirmed:

```text
POLICY_SIGNATURES=20
PROBE_FAILURES=0
```

Each canonical signature was independently checked through:

```text
event_id
DomainEventReference.reference_id
payload nested value
metadata nested value
DomainKernelEventPublisher
```

For every tested signature:

```text
credential rejected
credential absent from exception string
credential absent from exception details
Kernel emitted-event count remains 0
```

### DomainId privacy

Independent probes confirmed credential-shaped slugs that are syntactically valid DomainIds, including representative `sk-...`, `key-...`, `glpat-...`, and `pypi-...` forms, are rejected by the Domain Event privacy boundary.

### JSON safety / immutability

Independent probe confirmed:

```text
caller-owned nested mutation does not mutate DomainEvent state
DomainEvent.to_dict() remains JSON serializable with allow_nan=False
```

The V5 MappingProxy remediation remains intact.

### Credential/privacy ordering

The V6 privacy ordering remains correct:

```text
mapping key type validation
→ mapping key privacy validation
→ recursive JSON validation
→ recursive value privacy validation
→ deep freeze
```

Secret/private keys are not interpolated into nested diagnostic paths before privacy validation.

### Catalog / architecture

Independent inspection confirms:

```text
GENERAL_EVENT_COUNT=23
GENERAL_EVENT_UNIQUE_COUNT=23
```

No Phase 10.33 event module adds:

```text
AgentRuntimeEventBus
event persistence
event replay
durable event queue
DLQ
```

`DomainConflictResolver` remains free of Domain Event / Kernel publication dependencies.

### Repository-native evidence supplied with V8

The manifest reports fresh final-HEAD verification:

```text
CREDENTIAL_POLICY_FAMILIES=20
V7_REGRESSION_TESTS=314 PASS
FOCUSED_REAUDIT_TESTS=780 PASS
AT_DP_033_LOGICAL_CHECKPOINTS=66/66 PASS
AT_DP_033_PYTEST_CASES=92 PASS
DOMAIN_TESTS=7772 PASS
GLOBAL_TESTS=13312 PASS
RUFF_DELTA=PASS
FORMAT_DELTA=PASS
COMPILE_DELTA=PASS
DIFF_CHECK=PASS
PHASE_10_34_UNTOUCHED=PASS
WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED
```

The full repository suites cannot be independently rerun from the clean `git archive` in this sandbox because `.venv` is intentionally excluded and the sandbox lacks optional repository dependency `libcst`. The supplied repository-native results are consistent with the independently executable audit-specific suites and probes.

### Bundle secret review

The V8 scanner self-test and final scan report PASS.

An independent wider textual pattern review found credential-shaped literals only in test/audit fixture material, including the already diagnosed AWS sanitization fixture; no production/config credential material was identified.

---

## Required next state

```text
PHASE10_33_INDEPENDENT_AUDIT_V8=FAIL
BLOCKERS=0
MAJORS=0
MINORS=1

AUDITED_HEAD=f3b9bf8f2a6b59212954eed25dcac454bae24e5a
AUDIT_BUNDLE_SHA256=da37bfed9e149d0dc7a8fa6be94637f74ec427da5119786abd866ecd85bfb739

V7_CREDENTIAL_POLICY_RUNTIME=PASS
V7_ADDITIONAL_CREDENTIAL_FAMILIES=PASS
KERNEL_CREDENTIAL_BOUNDARY=PASS
DOMAIN_ID_CREDENTIAL_BOUNDARY=PASS
SECURITY_CONTRACT_CLARIFICATION=PASS

M8_REGISTRY_DRIVEN_REGRESSION_MATRIX=FAIL

GENERAL_EVENT_COUNT=23
AT_DP_033_ACCOUNTING=PASS

CLOSE_PHASE=NO
ADVANCE_PHASE10_34=NO
NEXT=REMEDIATE_AUDIT_V8_MINOR
PUSH=NO
MERGE=NO
```
