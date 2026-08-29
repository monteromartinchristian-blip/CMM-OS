# CMM OS — Phase 10.33 Independent Audit V5

**Date:** 2026-08-29
**Audited branch:** `feature/phase-10-domain-intelligence`
**Audited HEAD:** `c57279b7403a3099830b0d8ef7d9f2e836cb1679`
**Implementation base:** `b72d47b59d64b5afcc07c9f3883cbf8d9ce5b979`
**Audit V4 report HEAD:** `67de38d17a88c3ddcd1d019a5ed6c5c4b9f0ffb0`
**Bundle SHA-256:** `133471f200a8422a147857819b3e1d8aa18affff9947a7c1f5d466192b70568b`
**Bundle source:** `git archive c57279b7403a3099830b0d8ef7d9f2e836cb1679`
**Verdict:** FAIL — one blocker and one audit-tooling minor remain

## Audit summary

- BLOCKERS: 1
- MAJORS: 0
- MINORS: 1
- Phase 10.33 must remain `Implemented, pending independent re-audit`.
- Phase 10.34 must not be advanced.
- V4's DomainId privacy remediation, malformed-value non-disclosure cases, and AT-DP-033 count distinction are independently confirmed.
- A separate `MappingProxyType` fast path bypasses the canonical JSON-safety / deep-immutability / privacy validation pipeline.

## V4 remediation disposition

| V4 finding | V5 status | Result |
|---|---|---|
| B2 — DomainId privacy bypass | PASS | Secret-shaped and private-marker domain slugs are rejected across direct event/reference and factory paths. |
| B2 — validation-error non-disclosure | PASS for the V4 attack set; edge gap remains | The JSON-valid malformed values from V4 no longer echo secrets. A separate non-string unknown-field-key path still echoes untrusted content and is included in the blocker remediation below. |
| m4 — AT-DP-033 evidence terminology | PASS | Source contains 66 unique logical CP labels (`CP-01` through `CP-66`); manifest correctly distinguishes 66 logical checkpoints from 92 parametrized pytest cases. |

---

## B2 — `MappingProxyType` bypasses JSON safety, deep immutability, and privacy

**Severity:** BLOCKER
**Scope:** DomainEvent contract / Kernel publication boundary

The canonical design requires all events to be immutable, JSON-safe, strictly serializable, round-trippable, and free of secret-like structures.

The audited implementation has a special branch in `_validate_event_dict_payload()`:

```python
if isinstance(raw, MappingProxyType):
    _reject_credential_keys_event(raw, field_name)
    return raw
```

This treats a top-level `MappingProxyType` as already validated and already deeply immutable.

That assumption is false.

### Independently reproduced — arbitrary non-JSON object crosses the Kernel boundary

A payload equivalent to:

```python
MappingProxyType({
    "opaque": SecretCarrier(SYNTHETIC_SECRET)
})
```

was accepted by direct `DomainEvent` construction.

The object then survived:

```text
DomainEvent
→ DomainEvent.to_dict()
→ DomainKernelEventPublisher
→ kernel.events.Event.payload
```

unchanged.

`json.dumps(event.to_dict())` failed with `TypeError` because the object is not JSON serializable.

The same bypass was reproduced for `metadata`.

The same bypass is reachable through:

```text
DomainEvent.from_dict()
DomainEventFactory.create_event()
```

when the caller supplies a top-level `MappingProxyType`.

This reopens both:

- the B2 event-wide privacy boundary, because arbitrary opaque objects are not recursively privacy-scanned;
- the strict JSON-safety guarantee from the Phase 10.33 contract.

### Independently reproduced — frozen event still contains mutable nested state

A payload equivalent to:

```python
nested = ["safe"]
payload = MappingProxyType({"items": nested})
event = DomainEvent(..., payload=payload)
```

retained the original list.

Both of the following mutated the supposedly immutable event state after construction:

```text
nested.append(...)
event.payload["items"].append(...)
```

The same behavior was reproduced for `metadata`.

Therefore `frozen=True` is not sufficient in this path: the event is not deeply immutable.

### Independently reproduced — non-finite / invalid JSON values bypass validation

A top-level `MappingProxyType` containing:

```text
float("inf")
custom object
set
```

was accepted.

Normal mapping input goes through `_validate_json_safe_event()` and rejects these values. `MappingProxyType` skips that function entirely.

A `MappingProxyType` with a non-string key also produced an uncontrolled raw `TypeError` instead of a typed Domain Event contract error.

### Required remediation

Remove the trust shortcut.

Every `payload` / `metadata` mapping must pass the exact same pipeline regardless of concrete mapping implementation:

```text
Mapping
→ JSON-safe recursive validation
→ privacy/secret recursive validation
→ canonical deep freeze into fresh immutable state
```

A safe implementation may conceptually do:

```python
validated = _validate_json_safe_event(raw, field_name)
_reject_credential_keys_event(validated, field_name)
return _deep_freeze(validated)
```

for `MappingProxyType` as well as ordinary mappings.

Do not return a caller-supplied `MappingProxyType` by reference.

Required behavior:

- no arbitrary object survives;
- no bytes/set/custom object survives;
- non-finite float fails closed;
- all mapping keys must be strings;
- nested lists/mappings are copied/frozen;
- external mutation after construction cannot affect the event;
- `json.dumps(event.to_dict(), allow_nan=False)` succeeds for every valid event;
- the Kernel payload contains only canonical JSON-safe public data.

Apply and test through:

```text
DomainEvent direct construction
DomainEvent.from_dict()
DomainEventFactory.create_event()
payload
metadata
DomainKernelEventPublisher
```

---

## B2 — unknown non-string field names can still disclose rejected content

**Severity:** included in the blocker above
**Scope:** validation-error non-disclosure

`_reject_unknown_event_fields()` validates unknown field names only when they are strings, then emits:

```python
sorted(unknown)
details={"unknown_fields": sorted(unknown)}
```

A Python mapping with an unknown tuple key containing a synthetic secret was independently reproduced to leak that secret in both:

```text
str(exception)
exception.details
```

for:

```text
DomainEvent.from_dict()
DomainEventReference.from_dict()
```

This input is not representable as a normal JSON object, so it is narrower than the V4 malformed-value cases, but it still violates the public validation non-disclosure rule.

### Required remediation

Fail closed on non-string mapping keys before interpolating or storing them.

Do not include raw unknown key objects in messages/details.

Safe evidence may contain:

```text
field category
actual key type
safe count/index
```

For unknown *string* keys, validate privacy before including their names in diagnostics.

Add regression coverage for non-string unknown keys whose nested representation contains synthetic secret text.

---

## m5 — V5 bundle private-key scanner reports PASS through a grep invocation bug

**Severity:** MINOR
**Scope:** audit packaging / evidence integrity

The V5 bundle itself was independently checked and no real-looking private key block was found.

However, the V5 packager's private-key content check is not functioning as intended.

It invokes a grep pattern beginning with:

```text
-----BEGIN ...
```

as a positional pattern after `grep -E`, without `-e` / `--`.

On standard grep implementations, the leading hyphens are parsed as an option and grep exits with an error code rather than performing the match.

The script redirects stderr and treats every non-zero status as "no match", so this condition is reported as:

```text
TRACKED_TEXT_SECRET_CONTENT=PASS
EXTRACTED_TEXT_SECRET_CONTENT=PASS
```

even when matching synthetic private-key header fixtures exist in the tracked tree.

Independent V5 inspection found known synthetic/example private-key header strings in validation/Agent Runtime test fixtures and scanner source. No complete real key material was found.

### Required remediation for the V6 packager

- use `grep -e "$pattern"` / an equivalent safe invocation, or preferably a small deterministic Python scanner;
- distinguish expected synthetic fixture/header strings from high-confidence actual key material;
- fail the packaging gate on scanner execution errors instead of treating them as a negative match;
- continue forbidding `.env`, private-key filenames, `.venv`, `.git`, caches, etc.;
- never print detected secret values.

This finding does not require production-code changes inside Phase 10.33, but the next audit bundle generator must be corrected.

---

## Independently confirmed PASS areas

### Bundle identity and contents

- SHA-256 independently matches:
  `133471f200a8422a147857819b3e1d8aa18affff9947a7c1f5d466192b70568b`.
- 1,834 archive entries inspected.
- no `.env`;
- no `.git`;
- no `.venv`;
- no cache/`.pyc` path;
- no forbidden credential/private-key filename;
- no symlinks;
- audit reports V1 through V4 are present.

### V4 regression suite

The V4-specific audit regression file was independently executed from the clean audit tree using an isolated package loader:

```text
50 passed
```

### V4 DomainId privacy

Independent probes rejected:

```text
DomainEvent(domain_id=DomainId(slug="sk-..."))
DomainEvent(domain_id=DomainId(slug="system-prompt"))
related_domain_ids containing secret-shaped DomainId
DomainEventReference.domain_id containing secret-shaped DomainId
```

No tested V4 domain-identity attack reached the Kernel publisher.

### V4 validation-error non-disclosure attack set

Independent probes confirmed that the synthetic secret was absent from both error message and details for:

```text
DomainEvent.from_dict(event_id=[secret])
DomainEventReference.from_dict(reference_id=[secret])
DomainEventFactory.create_event(event_id=[secret])
DomainEvent.from_dict(occurred_at="invalid-<secret>")
malformed domain_id mapping containing secret
malformed related_domain_ids mapping containing secret
malformed provenance domain mapping containing secret
unknown secret-shaped string field name
```

### M5 / conflict lifecycle

Independent real-runtime probes confirmed:

```text
resolved conflict
→ domain.conflict.detected
→ domain.conflict.resolved
```

with the primary-domain reference winning.

A blocking unresolved conflict independently produced:

```text
domain.conflict.detected
```

only, with no false `domain.conflict.resolved`.

### Retained architecture

Independent static checks confirmed:

- exactly 23 canonical general event names;
- all 23 are unique;
- no `AgentRuntimeEventBus` dependency in Phase 10.33 event modules;
- no event persistence/replay/DLQ/durable queue;
- `DomainConflictResolver` remains free of Domain Event / Kernel publication dependencies.

### AT-DP-033 accounting

Independent source inspection found exactly:

```text
66 unique logical CP labels
CP-01 through CP-66
```

The V5 manifest reports:

```text
AT_DP_033_LOGICAL_CHECKPOINTS=66/66 PASS
AT_DP_033_PYTEST_CASES=92 PASS
```

which is the correct distinction.

## Repository verification evidence supplied with V5

The V5 manifest reports fresh post-commit repository verification:

```text
V4_REGRESSION_TESTS=50 PASS
FOCUSED_REAUDIT_TESTS=305 PASS
AT_DP_033_LOGICAL_CHECKPOINTS=66/66 PASS
AT_DP_033_PYTEST_CASES=92 PASS
DOMAIN_TESTS=7297 PASS
GLOBAL_TESTS=12837 PASS
RUFF_DELTA=PASS
FORMAT_DELTA=PASS
COMPILE_DELTA=PASS
DIFF_CHECK=PASS
SECRET_SCAN=PASS
WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED
```

The independent sandbox additionally compiled the Phase 10.33 event modules successfully.

The clean audit bundle excludes `.venv`, and this sandbox does not provide the repository dependency `libcst`, so the full repository suite cannot be normally collected from the bundle. Independent execution therefore used the V4 regression suite plus isolated adversarial runtime probes and static verification.

## Required next state

```text
PHASE10_33_INDEPENDENT_AUDIT_V5=FAIL
BLOCKERS=1
MAJORS=0
MINORS=1

AUDITED_HEAD=c57279b7403a3099830b0d8ef7d9f2e836cb1679
AUDIT_BUNDLE_SHA256=133471f200a8422a147857819b3e1d8aa18affff9947a7c1f5d466192b70568b

B2_MAPPING_PROXY_PRIVACY_JSON_IMMUTABILITY=FAIL
B2_UNKNOWN_FIELD_ERROR_NONDISCLOSURE=FAIL

V4_DOMAIN_ID_PRIVACY=PASS
V4_MALFORMED_VALUE_NONDISCLOSURE=PASS
AT_DP_033_ACCOUNTING=PASS

CLOSE_PHASE=NO
ADVANCE_PHASE10_34=NO
NEXT=REMEDIATE_AUDIT_V5
PUSH=NO
MERGE=NO
```
