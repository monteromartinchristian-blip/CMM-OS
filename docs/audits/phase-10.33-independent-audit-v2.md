# CMM OS — Phase 10.33 Independent Audit V2

**Date:** 2026-08-29
**Audited branch:** `feature/phase-10-domain-intelligence`
**Audited HEAD:** `d3d7207544cd495c563660a188486cddc8e2b88e`
**Implementation base:** `b72d47b59d64b5afcc07c9f3883cbf8d9ce5b979`
**Audit V1 report HEAD:** `b3f341e7d819575935883933afa6f4e78e3328db`
**Bundle SHA-256:** `398dac899197f7696267a9269ccca89ce019e8da302bd690b17cde6b08911c16`
**Bundle source:** `git archive d3d7207544cd495c563660a188486cddc8e2b88e`
**Verdict:** FAIL — remediation required before closure

## Audit summary

- BLOCKERS: 1
- MAJORS: 2
- MINORS: 1
- Phase 10.33 must remain `Implemented, pending independent re-audit`.
- Phase 10.34 must not be advanced.
- No closure commit should be created until all V2 findings are remediated and a clean V3 audit bundle is generated.

## V1 remediation disposition

| V1 finding | V2 status | Result |
|---|---|---|
| B1 — audit bundle leaked `.env` / credential | PASS | V2 is built from `git archive`; bundle path and content checks pass; no `.env`, `.venv`, `.git`, private-key or credential path was found. |
| B2 — DomainEvent privacy boundary fail-open | **FAIL** | Payload/metadata scanning improved, but several secret channels remain open. |
| M1 — schema version not enforced | PASS | Built-in and specialized declaration versions are validated/enforced; mismatched built-in version independently rejects. |
| M2 — strict construction/deserialization fail-open | **FAIL** | Required fields improved, but optional identifier fields remain type/JSON fail-open. |
| M3 — permission events misstate effective context | PASS | Requested/denied capability stays in payload; effective permissions default empty and explicit authoritative context is preserved. |
| M4 — failed listener recorded as emitted | PASS | Independent probe confirms publication error leaves `emitted_events` empty. |
| M5 — no production lifecycle path | **FAIL** | Bridge exists, but its real conflict call-around path is broken and does not pass authoritative primary-domain input to the resolver. |
| m1 — missing implementation plan | PASS | Canonical plan exists at the roadmap-referenced path. |

---

## B2 — Privacy boundary still leaks secrets through unscanned fields and incomplete value sanitization

**Severity:** BLOCKER
**Scope:** Security / privacy / public event boundary

The V1 remediation added recursive privacy-marker scanning and several secret-value regexes to `payload` and `metadata`. That materially improves the contract, but the event as a whole is still not fail-closed.

### Independently reproduced

The audited `DomainEvent` accepts a secret-shaped value in top-level public fields that are serialized into the Kernel event:

```text
actor="sk-" + 40 synthetic characters
→ ACCEPTED

permissions=("Bearer abcdefghijklmnop",)
→ ACCEPTED
```

`DomainEventReference` is also not privacy-validated:

```text
reference_id="Authorization: Bearer SECRET1234567890"
→ ACCEPTED

kind="system_prompt"
→ ACCEPTED
```

Because provenance is part of `DomainEvent.to_dict()`, those values cross the public event boundary unchanged.

### Secret-value coverage remains incomplete

The current value detector rejects some forms such as `Authorization: ...`, bearer tokens, `sk-*`, `key-*`, and `session_token=...`, but independently accepted:

```text
payload={"error": "password=hunter2"}
payload={"error": "secret=supersecret"}
payload={"error": "credential=mysecret"}
payload={"error": "cookie: abcdefghijklmnop"}
```

The failure adapter sanitizer has the same gap. `adapt_operation_failed()` independently accepted and emitted unsanitized synthetic error strings for:

```text
password=...
secret=...
credential=...
cookie: ...
```

while correctly redacting an `Authorization: Bearer ...` example.

### Publication errors can re-expose listener secrets

`DomainKernelEventPublisher.publish()` currently wraps listener failure as:

```python
f"Failed to deliver ...: {exc}"
```

An independent probe with a listener exception containing a synthetic Authorization/Bearer value confirmed the resulting `DomainEventPublicationError` string still contained both the authorization marker and the secret value.

This is not stored in `emitted_events`, so M4 is fixed, but it remains a secret-bearing error surface.

### Why this remains a blocker

The approved design requires:

```text
events contain no secrets
no credentials
no API keys
no authorization headers
no cookies/tokens
no hidden reasoning
no private prompt capture
reference-first provenance
```

The invariant is event-wide, not limited to dictionary keys under `payload` and `metadata`.

### Required remediation

1. Apply privacy/secret validation to every externally serialized string-bearing event field, including:
   - `actor`
   - `session_id`
   - `permissions`
   - `correlation_id`
   - `causation_id`
   - `DomainEventReference.kind`
   - `DomainEventReference.reference_id`
   - any other public string field capable of carrying arbitrary caller text.
2. Extend secret-value detection/sanitization to cover at least password/secret/credential assignments and cookie/header variants.
3. Ensure failure adapters cannot pass unrestricted raw error text after sanitization.
4. Do not include raw listener exception text in `DomainEventPublicationError`; expose a safe error type/code/reference instead.
5. Add adversarial tests for all of the above, including nested and top-level fields.

---

## M2 — Optional identifier fields remain non-strict and can break JSON serialization

**Severity:** MAJOR
**Scope:** Contract strictness / serialization

The V1 examples for `actor`, scalar `permissions`, invalid `payload`, invalid provenance and explicit empty `event_id` are fixed.

However, the public contract still accepts invalid types for optional string identifiers.

### Independently reproduced

Direct construction accepted:

```text
session_id=123
→ ACCEPTED

correlation_id=object()
→ ACCEPTED
```

Strict deserialization also accepted:

```text
DomainEvent.from_dict(..., session_id=123)
→ ACCEPTED
```

`causation_id` follows the same validation path.

The cause is that `DomainEvent.__post_init__()` calls `_normalize_empty_to_none()` for these fields, and that helper returns non-string values unchanged. `from_dict()` passes the fields through without a strict type check.

### Serialization failure reproduced

A `DomainEvent` created with:

```text
correlation_id=object()
```

successfully constructs and `to_dict()` returns that object. A subsequent:

```python
json.dumps(event.to_dict())
```

raises `TypeError`.

This violates the approved invariant that `DomainEvent` is strictly serializable and JSON-safe.

### Required remediation

- Enforce `str | None` for `session_id`, `correlation_id`, and `causation_id` in direct construction, factory construction and `from_dict()`.
- Reject invalid explicit types instead of normalizing/passing them through.
- Add round-trip and `json.dumps(event.to_dict())` adversarial tests for these fields.
- Review all public event fields for the same optional-type gap.

---

## M5 — Conflict lifecycle call-around is broken and omits authoritative primary-domain input

**Severity:** MAJOR
**Scope:** Production integration / semantic preservation

`DomainLifecycleEventBridge` is a valid production module and is correctly kept outside the pure Phase 10.31/10.32 engines. Its direct `emit_*` methods successfully reach `DomainKernelEventPublisher → kernel.events.Event`.

However, the actual conflict call-around method is broken.

### Independently reproduced

The bridge contains:

```python
resolution = resolver.resolve(case, policy)
```

but `DomainConflictResolver.resolve()` declares:

```python
def resolve(
    self,
    case: DomainConflictCase,
    *,
    policy: DomainConflictResolutionPolicy | None = None,
    primary_domain: DomainId | None = None,
    ...
)
```

`policy` is keyword-only.

Calling:

```text
DomainLifecycleEventBridge.resolve_conflict_with_events(...)
```

with the real `DomainConflictResolver` independently produced:

```text
TypeError:
DomainConflictResolver.resolve() takes 2 positional arguments but 3 were given
```

### Primary-domain semantic input is also dropped

The bridge accepts:

```python
primary_domain: DomainId | str
```

but uses it only when adapting the emitted event. It does **not** pass it to `DomainConflictResolver.resolve(primary_domain=...)`.

That means even after correcting the keyword-only call, the bridge would still be capable of resolving with different semantics from the authoritative Phase 10.32 invocation expected by its own input.

### Test gap

The V1 regression and AT-DP-033 tests exercise:

```text
emit_resolution_result()
emit_conflict_detected()
emit_conflict_resolution()
```

but do not exercise the real:

```text
resolve_conflict_with_events()
```

call-around with `DomainConflictResolver`.

The broken production path therefore remained green.

### Required remediation

- Invoke the real resolver with keyword arguments, including the authoritative primary domain, e.g. conceptually:

```python
resolver.resolve(
    case,
    policy=policy,
    primary_domain=<validated DomainId>,
)
```

- Preserve any other authoritative resolver arguments if the bridge exposes them.
- Add an integration test that invokes `resolve_conflict_with_events()` with the real `DomainConflictResolver` and asserts:
  - conflict detected event emitted;
  - resolver executes successfully;
  - resolved event emitted only when the actual returned status permits it;
  - unresolved/maintained/human-review paths do not emit `domain.conflict.resolved`;
  - primary-domain semantics are preserved.
- Keep `DomainConflictResolver` itself event-free and side-effect free.

---

## m2 — Direct DomainEvent construction accepts unordered sets, making serialization nondeterministic

**Severity:** MINOR
**Scope:** Determinism / contract hygiene

The approved design requires `related_domain_ids` to be deterministic in serialized form and defines tuple-based public contracts.

`_freeze_domain_ids_event()` currently explicitly accepts `set`, and `_freeze_str_tuple_unique_event()` does the same for string tuples such as permissions.

### Independently reproduced

Constructing a `DomainEvent` with:

```python
related_domain_ids={
    DomainId(slug="project"),
    DomainId(slug="health"),
    DomainId(slug="university"),
}
```

produced different serialized ordering under different `PYTHONHASHSEED` values, including:

```text
["university", "project", "health"]
["university", "health", "project"]
["health", "project", "university"]
["project", "health", "university"]
```

### Required remediation

Either:

- reject unordered set/frozenset inputs and require an ordered sequence matching the public tuple contract; or
- canonicalize unordered inputs deterministically before freezing.

Apply the same rule to permissions and any other serialized sequence where set input is currently accepted.

Add a deterministic serialization regression test.

---

## Positive findings

The V2 audit independently confirmed:

- bundle SHA-256 matches the supplied manifest;
- audited HEAD is `d3d7207544cd495c563660a188486cddc8e2b88e`;
- V2 contains 1,828 archive entries and no forbidden `.env`, `.git`, `.venv`, cache, private-key or credential path;
- no symlinks are present in the extracted audit tree;
- exact canonical general-event count is 23;
- no `AgentRuntimeEventBus` dependency appears in the Phase 10.33 event modules;
- no persistence/replay/durable-queue implementation appears in the Phase 10.33 event modules;
- `DomainConflictResolver` remains free of Domain Event / Kernel publication dependencies;
- schema-version mismatch for built-in events independently fails closed;
- permission request/denial events independently preserve empty default effective permissions and explicit authoritative effective permissions;
- failed listener publication independently raises `DomainEventPublicationError` and leaves `emitted_events` empty;
- the canonical implementation plan exists;
- roadmap status remains `Implemented, pending independent re-audit`;
- Phase 10.34 has not been advanced.

## Verification evidence

The V2 manifest reports fresh repository verification before bundling:

```text
FOCUSED_REAUDIT_TESTS=135 PASS
GLOBAL_TESTS=12667 PASS
RUFF_DELTA=PASS
FORMAT_DELTA=PASS
COMPILE_DELTA=PASS
SECRET_SCAN=PASS
WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED
```

The independent audit sandbox verified the bundle identity, archive contents, dependency direction, static contracts and custom adversarial probes.

The repository pytest suite could not be independently collected in the audit sandbox because the bundle intentionally excludes `.venv` and this environment does not provide the repository dependency `libcst`. This is an environment limitation, not a basis for any finding above.

## Required next state

```text
PHASE10_33_INDEPENDENT_AUDIT_V2=FAIL
BLOCKERS=1
MAJORS=2
MINORS=1
AUDITED_HEAD=d3d7207544cd495c563660a188486cddc8e2b88e
AUDIT_BUNDLE_SHA256=398dac899197f7696267a9269ccca89ce019e8da302bd690b17cde6b08911c16
NEXT=REMEDIATE_V2_FINDINGS
CLOSE_PHASE=NO
ADVANCE_PHASE10_34=NO
PUSH=NO
MERGE=NO
```
