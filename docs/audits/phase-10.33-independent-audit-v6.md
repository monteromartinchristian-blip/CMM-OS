# CMM OS — Phase 10.33 Independent Audit V6

**Date:** 2026-08-29
**Audited branch:** `feature/phase-10-domain-intelligence`
**Audited HEAD:** `f463c121fc640baa37618f035295c34f2f0f08e1`
**Implementation base:** `b72d47b59d64b5afcc07c9f3883cbf8d9ce5b979`
**Audit V5 report HEAD:** `10d22c825f7cd4c96c1abea8f9737a52c84a1d67`
**Bundle SHA-256:** `732b5beab5b88a61217968fc540740bdd429d94ce1967fc4b0f67af441ba6d34`
**Bundle source:** `git archive f463c121fc640baa37618f035295c34f2f0f08e1`
**Verdict:** FAIL — one privacy blocker remains

## Audit summary

- BLOCKERS: 1
- MAJORS: 0
- MINORS: 0
- Phase 10.33 must remain `Implemented, pending independent re-audit`.
- Phase 10.34 must not be advanced.
- The V5 production blocker is materially remediated.
- The V5 audit-tooling scanner minor is remediated in the hardened V6 packager.
- B2 remains open because the event-wide credential/privacy invariant still has uncovered paths.

## V5 remediation disposition

| V5 finding | V6 status | Result |
|---|---|---|
| B2 — `MappingProxyType` JSON/privacy/deep-immutability bypass | PASS | Caller-supplied mappings now go through JSON-safe validation and fresh deep-freeze; arbitrary objects, sets and non-finite floats are rejected. |
| B2 — non-string unknown-field error disclosure | PASS | Non-string unknown keys fail with safe type/index diagnostics and no raw key content. |
| m5 — private-key scanner grep bug | PASS | V6 uses a fail-closed Python scanner and independently no plausible private-key block or live OpenAI-style credential material was found. |

---

## B2 — privacy validation ordering can disclose a secret-shaped mapping key

**Severity:** BLOCKER
**Scope:** validation error non-disclosure / payload and metadata privacy

`_validate_event_dict_payload()` currently performs:

```text
_validate_json_safe_event(raw)
→ _reject_credential_keys_event(validated)
→ _deep_freeze(validated)
```

Inside `_validate_json_safe_event()`, mapping recursion constructs the diagnostic path from the caller-controlled key before that key has passed privacy validation:

```python
result[k] = _validate_json_safe_event(v, f"{field_name}.{k}")
```

If the key itself contains secret-shaped data and the child value is invalid, JSON validation raises before `_reject_credential_keys_event()` runs.

### Independently reproduced

With a synthetic secret-shaped key and an arbitrary invalid object:

```text
payload = MappingProxyType({
    <synthetic secret-shaped key>: CustomObject()
})
```

direct `DomainEvent` construction failed, but the exception message contained the complete synthetic secret as part of:

```text
payload.<secret>: value must be JSON-safe ...
```

The same disclosure was reproduced for:

```text
non-finite float under the secret-shaped key
deeply nested secret-shaped key
DomainEvent.from_dict()
DomainEventFactory.create_event()
```

The same shared helper also governs `metadata`.

### Why this is a blocker

Rejecting the event is not sufficient if the rejected private value is then copied into logs or telemetry through an exception message.

The Phase 10.33 design explicitly requires:

```text
no secrets
no credentials
recursive secret rejection
strict safe event boundary
```

and prior audits established that validation-error paths are part of that boundary.

### Required remediation

Privacy-check mapping keys before using their content in any diagnostic path.

A safe order is conceptually:

```text
mapping key type validation
→ mapping key privacy validation
→ recursive JSON validation
→ recursive value privacy validation
→ deep freeze
```

Alternatively, perform a safe privacy pre-pass before JSON validation, provided:

- non-string keys fail with typed non-disclosing errors;
- secret/private keys are never interpolated into field paths;
- nested mappings receive the same treatment;
- caller data is still fully JSON-validated and deeply frozen.

Add regressions for both `payload` and `metadata`, direct/from_dict/factory paths, including nested keys.

---

## B2 — common high-confidence credential formats are accepted event-wide

**Severity:** BLOCKER
**Scope:** no-credentials / no-API-keys invariant

The current `_SECRET_VALUE_PATTERNS` detects several assignment-style secrets and `sk`/`pk` token families, but it does not recognize multiple common high-confidence credential formats when they appear as values without a credential-like field name.

### Independently reproduced

Synthetic credential-shaped values using these standard prefixes/formats were accepted:

```text
GitHub classic PAT-style token (`ghp_...`)
AWS access-key-id-style token (`AKIA...`)
Google API-key-style token (`AIza...`)
Slack bot-token-style token (`xoxb-...`)
```

For each tested family, acceptance was reproduced in:

```text
payload string value
metadata string value
event_id
DomainEventReference.reference_id
```

For DomainEvent paths, the synthetic token serialized unchanged into:

```text
DomainKernelEventPublisher
→ kernel.events.Event.payload
```

Therefore the event layer currently permits values that are unmistakably credential-shaped under the Phase 10.33 design's `no credentials / no API keys` rule.

### Required remediation

Extend the centralized event secret detector with a deliberately bounded set of high-confidence token signatures.

At minimum cover the independently reproduced families:

```text
GitHub PAT prefixes
AWS access key IDs
Google API key prefix
Slack token prefixes
```

Use synthetic values only in tests.

Avoid broad entropy heuristics that would reject ordinary IDs. Prefer provider/prefix-specific, high-confidence patterns.

Apply the same centralized validator everywhere it is already used so these formats fail closed in:

```text
event_id
reference_id
actor/sensitivity/optional IDs/permissions where applicable
payload
metadata
DomainId privacy if syntactically representable
factory/direct/from_dict
Kernel publication boundary
```

Error messages/details must not echo the token.

Add one final publication gate proving none of the newly covered credential families can reach `kernel.events.Event`.

---

## Independently confirmed PASS areas

### Bundle integrity

- SHA-256 independently matches:
  `732b5beab5b88a61217968fc540740bdd429d94ce1967fc4b0f67af441ba6d34`.
- 1,836 TAR entries inspected.
- no symlink/hardlink entries;
- no path traversal;
- no `.env`;
- no `.git`;
- no `.venv`;
- no tracked cache/`.pyc` entry in the original TAR;
- no forbidden credential/private-key filename;
- audit reports V1 through V5 are present.

### Hardened V6 scanner

Independent content inspection found no plausible live private-key block, no live OpenAI assignment, and no long literal `sk-...` credential.

The V6 scanner no longer relies on the V5 grep invocation that misinterpreted a pattern beginning with hyphens.

A tracked validation test fixture contains the standard public AWS example access-key identifier; it is fixture/example material, not evidence of a live credential.

### V5 `MappingProxyType` remediation

Independent execution confirmed:

```text
custom object in payload/metadata MappingProxyType → rejected
set/frozenset → rejected
non-finite float → rejected
non-string key → rejected
caller nested list mutation → does not mutate event
caller nested mapping mutation → does not mutate event
valid nested mapping → JSON-safe round trip
valid event → json.dumps(..., allow_nan=False) succeeds
Kernel payload → JSON-safe
```

The exact V5 regression suite executed independently against the V6 code:

```text
48 passed
```

### Accumulated audit regressions

Using an isolated module loader to avoid unrelated optional dependency `libcst`, the audit-specific suites V1 through V5 executed directly from the V6 bundle:

```text
249 passed
```

No failures occurred in those audit regression suites.

### V4 and earlier invariants

The accumulated regression run independently reconfirmed the prior behavioral gates, including:

- DomainId privacy;
- malformed-value error non-disclosure cases from V4;
- schema-version enforcement;
- permission requested/denied effective-context isolation;
- listener failure non-emission and listener error sanitization;
- strict optional identifiers;
- deterministic rejection of unordered set/frozenset event sequences;
- real conflict lifecycle integration and `primary_domain` propagation;
- no false `domain.conflict.resolved` for unresolved/non-proceeding conflict results.

### Architecture and catalog

Independent static inspection confirmed:

```text
GENERAL_EVENT_COUNT=23
GENERAL_EVENT_UNIQUE_COUNT=23
AT_DP_033_LOGICAL_CHECKPOINTS=66
AT_DP_033_RANGE=CP-01..CP-66
```

The Phase 10.33 event modules contain no `AgentRuntimeEventBus` dependency and no event persistence/replay/DLQ/durable queue.

`cmm/domains/conflict_resolution.py` contains no Domain Event or Kernel import, preserving `DomainConflictResolver` purity.

### Repository verification evidence supplied with V6

The V6 manifest reports fresh post-commit repository verification:

```text
V5_REGRESSION_TESTS=48 PASS
FOCUSED_REAUDIT_TESTS=353 PASS
AT_DP_033_LOGICAL_CHECKPOINTS=66/66 PASS
AT_DP_033_PYTEST_CASES=92 PASS
DOMAIN_TESTS=7345 PASS
GLOBAL_TESTS=12885 PASS
RUFF_DELTA=PASS
FORMAT_DELTA=PASS
COMPILE_DELTA=PASS
DIFF_CHECK=PASS
WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED
```

The normal full pytest collection cannot be reproduced from the clean `git archive` in this sandbox because `.venv` is intentionally excluded and the sandbox lacks repository dependency `libcst`. This limitation is environmental; it does not affect the independently executed audit-specific suites or adversarial probes.

## Required next state

```text
PHASE10_33_INDEPENDENT_AUDIT_V6=FAIL
BLOCKERS=1
MAJORS=0
MINORS=0

AUDITED_HEAD=f463c121fc640baa37618f035295c34f2f0f08e1
AUDIT_BUNDLE_SHA256=732b5beab5b88a61217968fc540740bdd429d94ce1967fc4b0f67af441ba6d34

B2_PRIVACY_VALIDATION_ORDERING=FAIL
B2_COMMON_CREDENTIAL_FORMATS=FAIL

V5_MAPPING_PROXY_JSON_IMMUTABILITY=PASS
V5_UNKNOWN_FIELD_NONDISCLOSURE=PASS
V5_PRIVATE_KEY_SCANNER_MINOR=PASS

GENERAL_EVENT_COUNT=23
AT_DP_033_ACCOUNTING=PASS

CLOSE_PHASE=NO
ADVANCE_PHASE10_34=NO
NEXT=REMEDIATE_AUDIT_V6
PUSH=NO
MERGE=NO
```
