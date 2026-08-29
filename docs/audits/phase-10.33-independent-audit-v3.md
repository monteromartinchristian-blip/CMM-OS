# CMM OS — Phase 10.33 Independent Audit V3

**Date:** 2026-08-29
**Audited branch:** `feature/phase-10-domain-intelligence`
**Audited HEAD:** `c73fabd71a84ef28f29d1ccc7fe338d171184d00`
**Implementation base:** `b72d47b59d64b5afcc07c9f3883cbf8d9ce5b979`
**Audit V2 report HEAD:** `52cd3702485608c071c95ad8ff8c894fc4878d1c`
**Bundle SHA-256:** `c8e440493081901666fa3f53b1ee4e1dcc7a48ab1d71206a5393f371928b8e76`
**Bundle source:** `git archive c73fabd71a84ef28f29d1ccc7fe338d171184d00`
**Verdict:** FAIL — one blocker remains

## Audit summary

- BLOCKERS: 1
- MAJORS: 0
- MINORS: 0
- Phase 10.33 must remain `Implemented, pending independent re-audit`.
- Phase 10.34 must not be advanced.
- The V2 fixes for M2, M5 and deterministic ordered sequences are independently confirmed.
- The remaining failure is confined to the B2 privacy boundary.

## V2 remediation disposition

| V2 finding | V3 status | Result |
|---|---|---|
| B2 — event-wide privacy / secret boundary | **FAIL** | Top-level and nested public string channels remain capable of carrying forbidden private content; error sanitization can leave secondary cookie/token material. |
| M2 — strict optional identifiers / JSON safety | PASS | `session_id`, `correlation_id`, `causation_id` reject invalid types; valid events remain JSON-safe. |
| M5 — real conflict lifecycle integration | PASS | Real `DomainConflictResolver` call-around works, `primary_domain` is propagated, and unresolved outcomes do not emit `domain.conflict.resolved`. |
| m2 — deterministic serialized sequences | PASS | `set`/`frozenset` inputs are rejected for ordered serialized sequence fields. |

---

## B2 — Privacy boundary is still not event-wide

**Severity:** BLOCKER
**Scope:** Security / privacy / Kernel event boundary

The V2 remediation correctly strengthened:

- `actor`;
- `permissions`;
- optional string identifiers;
- `DomainEventReference.kind`;
- common secret assignments;
- failure adapter sanitization;
- publisher listener errors.

However, the approved invariant is broader:

> events contain no secrets and reject secret-like structures recursively; raw secrets, unrestricted prompts, hidden reasoning and unrelated sensitive source contents are forbidden.

The remaining implementation still validates different public string channels inconsistently.

### 1. `event_id` accepts and publishes secret-shaped values

Independent construction accepted a synthetic secret-shaped event ID equivalent to:

```text
event_id="sk-" + 40 synthetic characters
```

The event was then successfully published through:

```text
DomainKernelEventPublisher
→ kernel.events.Event
```

and the secret-shaped `event_id` was preserved unchanged in the Kernel payload.

A `password=...` shaped synthetic event ID was also accepted.

This is a direct public-boundary leak because `event_id` is externally serialized and caller-controlled when supplied explicitly.

### 2. `DomainEventReference.reference_id` rejects secret regexes but not forbidden private markers

`reference_id` currently checks `_contains_secret_value()` only.

Independent probes accepted:

```text
reference_id="system_prompt"
reference_id="raw_prompt: hidden instructions"
reference_id="pii:user@example.com"
```

Those values serialize unchanged into provenance and can be published to the Kernel event payload.

V2 explicitly required privacy validation for `DomainEventReference.reference_id`, not only secret-pattern validation.

### 3. Forbidden private markers are rejected in mapping keys but not string values

`_reject_credential_keys_event()` currently:

- checks private markers on mapping keys;
- checks secret regexes on string values;
- does **not** check forbidden private markers on string values.

Independent probes accepted and published payload/metadata values equivalent to:

```text
{"note": "system_prompt: hidden instructions"}
{"note": "chain_of_thought: private reasoning"}
{"note": "pii: alice@example.com"}
{"note": "raw_content: confidential text"}
```

This defeats the recursive privacy invariant even though payload keys themselves are safe.

### 4. Failure sanitizer can expose secondary cookie/token material

The sanitizer redacts only the first cookie segment because the cookie regex stops at delimiters such as `;`.

Independent probes produced outputs equivalent to:

```text
Cookie: foo=bar; sessionid=VERYSECRET...
→ [REDACTED_COOKIE]; sessionid=VERYSECRET...

Set-Cookie: a=b; csrftoken=TOPSECRET...
→ [REDACTED_COOKIE]; csrftoken=TOPSECRET...
```

The residual text is not detected by the current secret regex vocabulary and can therefore pass into a failure event.

This is a realistic cookie/header structure and violates the design requirement that events contain no cookies/tokens.

### 5. Validation errors should not echo rejected private content

`_validate_event_string_privacy()` currently embeds the rejected private-marker value in its exception message/details.

Once private-marker validation is correctly applied to arbitrary public string values, this would create another disclosure path through validation errors.

The safe contract should identify the field/category without reproducing the rejected content.

## Required remediation

Keep this remediation narrow. Do not modify already-passing M2/M5/determinism behavior.

### A. Centralize event-wide public-string validation

Use one canonical validation rule for every caller-controlled externally serialized string field.

At minimum cover:

```text
event_id
actor
session_id
permissions[*]
correlation_id
causation_id
sensitivity
DomainEventReference.kind
DomainEventReference.reference_id
payload string values recursively
metadata string values recursively
```

Also review `event_type` and `schema_version`.

They are registry-controlled semantically, but direct `DomainEvent` construction and `to_dict()` must not become a side channel for secret/private content before registry publication.

Do not weaken exact event-type/schema-version validation.

### B. Recursive values must reject both categories

For every nested string value in payload/metadata, reject:

1. secret-shaped values;
2. forbidden private-content markers.

A safe nested key must not make an unsafe nested value acceptable.

### C. Preserve reference-first provenance

`DomainEventReference.reference_id` must remain an opaque safe identifier/reference.

Reject raw prompt/private-content strings placed into it.

Do not copy prompt content, PII, credentials or hidden reasoning into provenance IDs.

### D. Harden failure sanitization

Cookie/authorization sanitization must cover complete sensitive header material rather than only the first delimiter-separated fragment.

A robust fail-closed strategy is preferable:

- redact the complete Authorization/Cookie/Set-Cookie header/value;
- or emit a generic `[REDACTED_ERROR]` when safe sanitization cannot be proven.

Ensure secondary cookie attributes/values such as `sessionid`, CSRF tokens or API-token-like fields cannot remain after sanitization.

### E. Safe validation errors

Privacy rejection exceptions must not include the raw rejected secret/private-content value in:

```text
message
details
repr-like diagnostics
```

Return only safe field/category information.

### F. Required regression coverage

Add adversarial tests proving rejection/non-leakage for at least:

```text
secret-shaped explicit event_id
private-marker reference_id
private-marker payload string value
private-marker metadata string value
nested private-marker string value
multi-part Cookie header
multi-part Set-Cookie header
secondary session/token cookie material
validation exception text does not echo rejected private content
Kernel publication cannot contain any of those values
```

Exercise:

```text
direct DomainEvent construction
DomainEvent.from_dict()
DomainEventFactory.create_event()
DomainEventReference direct/from_dict
failure adapters
DomainKernelEventPublisher
```

---

## Independently confirmed PASS areas

### Bundle / supply-chain boundary

- SHA-256 independently matches:
  `c8e440493081901666fa3f53b1ee4e1dcc7a48ab1d71206a5393f371928b8e76`.
- 1,830 archive entries inspected.
- No `.env`.
- No `.git`.
- No `.venv`.
- No cache/`.pyc` path.
- No private-key or credential-like forbidden path.
- No symlink in the archive.
- V2 audit report and audit manifest are present.

### Catalog and dependency direction

- Canonical general-event catalog count: exactly 23.
- All 23 names are unique.
- No `AgentRuntimeEventBus` dependency found in the Phase 10.33 modules.
- No event persistence/replay/DLQ/durable-queue implementation found.
- `DomainConflictResolver` contains no Domain Event / Kernel publisher dependency and remains pure.

### V1 retained fixes

Independently reconfirmed:

- M1 exact schema mismatch fails closed.
- M3 requested/denied capability is not inserted into effective permissions.
- Explicit authoritative effective permissions are preserved.
- M4 listener failure leaves `emitted_events` empty.
- Publisher error no longer reproduces raw listener exception secret text.
- Canonical implementation plan exists.
- Phase 10.33 roadmap remains pending independent re-audit.

### V2 M2

Independent probes rejected:

```text
session_id=123
correlation_id=object()
causation_id=False
```

Direct construction fails closed.

The corresponding direct/from-dict/factory regression coverage is present.

### V2 M5

Independent real-runtime probe:

```text
DomainLifecycleEventBridge
→ domain.conflict.detected
→ DomainConflictResolver.resolve(...)
→ domain.conflict.resolved
→ DomainKernelEventPublisher
→ kernel.events.Event
```

produced a resolved result with the primary-domain reference as winner.

A second independent real-runtime probe of a blocking unresolved/maintained conflict emitted only:

```text
domain.conflict.detected
```

and correctly did **not** emit `domain.conflict.resolved`.

### V2 m2

Independent probes confirmed `set` inputs are rejected for:

```text
permissions
related_domain_ids
```

The public contract therefore no longer serializes unordered set iteration.

## Repository verification evidence supplied with V3

The V3 manifest reports the final post-commit verification on audited HEAD:

```text
FOCUSED_REAUDIT_TESTS=211 PASS
DOMAIN_TESTS=7203 PASS
GLOBAL_TESTS=12743 PASS
RUFF_DELTA=PASS
FORMAT_DELTA=PASS
COMPILE_DELTA=PASS
DIFF_CHECK=PASS
SECRET_SCAN=PASS
WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED
```

The independent audit sandbox could not execute the repository pytest suite because the intentionally clean `git archive` excludes `.venv` and this audit environment does not provide the repository dependency `libcst`.

The V3 verdict therefore uses:

- the supplied fresh repository test evidence;
- independent bundle-integrity verification;
- static code inspection;
- isolated direct execution of the relevant audited Domain Event, registry, publisher, adapters, bridge and real conflict resolver modules without executing the broad package initializer.

## Required next state

```text
PHASE10_33_INDEPENDENT_AUDIT_V3=FAIL
BLOCKERS=1
MAJORS=0
MINORS=0
AUDITED_HEAD=c73fabd71a84ef28f29d1ccc7fe338d171184d00
AUDIT_BUNDLE_SHA256=c8e440493081901666fa3f53b1ee4e1dcc7a48ab1d71206a5393f371928b8e76
B2_EVENT_WIDE_PRIVACY=FAIL
M2_STRICT_OPTIONAL_IDENTIFIERS=PASS
M5_REAL_CONFLICT_LIFECYCLE=PASS
m2_DETERMINISTIC_SEQUENCES=PASS
CLOSE_PHASE=NO
ADVANCE_PHASE10_34=NO
NEXT=REMEDIATE_AUDIT_V3_B2
PUSH=NO
MERGE=NO
```
