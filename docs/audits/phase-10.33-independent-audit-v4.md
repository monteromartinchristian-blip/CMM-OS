# CMM OS — Phase 10.33 Independent Audit V4

**Date:** 2026-08-29
**Audited branch:** `feature/phase-10-domain-intelligence`
**Audited HEAD:** `b78d56e6fbf03bb56e7b12f2c68197d7f08d5c5a`
**Implementation base:** `b72d47b59d64b5afcc07c9f3883cbf8d9ce5b979`
**Audit V3 report HEAD:** `a92f224310408f8e766e76a0409b3c3593905e3a`
**Bundle SHA-256:** `cae48f9dc2287a0ceea9938b256c0e968eff8e96bfae937bb1f572eb16262e2c`
**Bundle source:** `git archive b78d56e6fbf03bb56e7b12f2c68197d7f08d5c5a`
**Verdict:** FAIL — one privacy blocker and one evidence/documentation minor remain

## Audit summary

- BLOCKERS: 1
- MAJORS: 0
- MINORS: 1
- Phase 10.33 must remain `Implemented, pending independent re-audit`.
- Phase 10.34 must not be advanced.
- V3 materially improved B2, but the public event boundary is still not fully event-wide.

## V3 remediation disposition

| V3 finding | V4 status | Result |
|---|---|---|
| B2 — event-wide privacy boundary | **FAIL** | Event IDs, reference IDs, nested string values and cookie sanitization are improved, but domain identity channels bypass privacy validation and malformed-input validation errors can still echo secret-bearing values. |

---

## B2 — Domain identity channels bypass the event-wide privacy invariant

**Severity:** BLOCKER
**Scope:** Security / privacy / Kernel publication boundary

The V3 remediation correctly applies `_validate_event_string_privacy()` to many public event strings, but `DomainId` values are parsed/accepted as structured identifiers without applying the event privacy boundary to their slug/canonical representation.

This leaves several caller-controlled, externally serialized channels capable of carrying secret-shaped material.

### Independently reproduced

A synthetically secret-shaped but syntactically valid domain slug was accepted:

```text
DomainId(slug="sk-aaaaaaaaaaaa")
```

The following paths all accepted it and published it unchanged through `DomainKernelEventPublisher → kernel.events.Event`:

```text
DomainEvent.domain_id
DomainEvent.related_domain_ids[*]
DomainEventReference.domain_id
DomainEventFactory.create_event(domain_id=...)
```

Representative Kernel payloads contained:

```text
{"domain_id": {"slug": "sk-aaaaaaaaaaaa"}}
```

or the same slug under `related_domain_ids` / `provenance[*].domain_id`.

A private-marker domain slug such as:

```text
system-prompt
```

is also syntactically valid under the generic `DomainId` slug grammar and is not rejected at the Domain Event boundary.

### Why this remains a blocker

Phase 10.33's privacy design requires:

```text
events contain no secrets
no API keys
no credentials
no private prompt capture
cross-domain events expose only authorized safe domain identities/references
malformed safety metadata fails closed
```

The event layer cannot rely on the generic `DomainId` grammar alone because that grammar establishes identifier syntax, not Phase 10.33 privacy safety.

The V3 remediation requirement also explicitly called for reviewing `DomainEventReference.domain_id / equivalent string components` so that no externally serialized caller-controlled string becomes a bypass around the same privacy invariant.

### Required remediation

Keep the fix inside the Phase 10.33 event boundary unless there is a demonstrated repository-wide reason to harden `DomainId` globally.

Add one canonical helper conceptually equivalent to:

```text
_validate_event_domain_id_privacy(domain_id, field_name)
```

It should apply the same event privacy validation to the safe canonical domain identifier/slug without changing Phase 10.1's generic identifier semantics.

Apply it to at least:

```text
DomainEvent.domain_id
DomainEvent.related_domain_ids[*]
DomainEventReference.domain_id

DomainEvent direct construction
DomainEvent.from_dict()
DomainEventReference direct construction
DomainEventReference.from_dict()
DomainEventFactory.create_event()
```

Test both:

```text
secret-shaped slug
private-marker slug
```

and prove they cannot reach `kernel.events.Event`.

Do not alter valid canonical domains such as `health`, `project`, `life-plan`, `oppositions`, etc.

---

## B2 — Validation-error non-disclosure remains incomplete for malformed values

**Severity:** BLOCKER
**Scope:** Security / error boundary

The new privacy validator no longer echoes rejected *string* secrets/private markers. That is correct.

However, several type/serialization failure paths still interpolate the raw caller-supplied value using `!r` or an underlying exception string.

### Independently reproduced

Using a JSON-valid malformed shape:

```text
event_id=["sk-" + 40 synthetic characters]
```

`DomainEvent.from_dict()` raised an error whose message contained the full synthetic secret value.

The same leakage was reproduced through:

```text
DomainEventReference.from_dict(
    {"kind": "resolution", "reference_id": [synthetic_secret]}
)

DomainEventFactory.create_event(
    ...,
    event_id=[synthetic_secret],
)
```

An invalid `occurred_at` string containing a synthetic secret was also echoed by the datetime parsing error.

### Affected patterns in the audited Phase 10.33 code

Representative error construction still includes raw values in messages such as:

```text
got {value!r}
Invalid ...: {value!r}
Invalid isoformat ...: {value!r}
...: {exc}
```

This means an attacker or malformed upstream caller can move sensitive text from an invalid event field into logs/telemetry through the validation error path even though the event itself is rejected.

### Required remediation

For Phase 10.33 public event construction/deserialization/factory paths:

- do not include raw untrusted field values in validation/serialization error messages;
- report only field name, expected type/shape, actual type, safe category/error code, and safe index where useful;
- do not embed nested underlying exception text if it may contain the rejected input;
- keep `details` equally non-disclosing.

At minimum review:

```text
DomainEvent.from_dict()
DomainEventReference.from_dict()
DomainEventFactory.create_event()
_validate_optional_str_identifier()
_validate_optional_str_from_dict()
_validate_json_safe_event()
_freeze_domain_ids_event()
_parse_datetime_event()
```

Add adversarial tests using malformed but JSON-valid containers containing synthetic secrets, not only direct secret strings.

---

## m4 — AT-DP-033 evidence conflates logical checkpoints with parametrized pytest cases

**Severity:** MINOR
**Scope:** Acceptance evidence / roadmap accuracy

The V4 manifest and roadmap report:

```text
AT_DP_033=92/92 CHECKPOINTS PASS
92 connected acceptance checkpoints (CP-01 through CP-66)
```

Independent static inspection of:

```text
tests/domains/test_domain_events_dp033_acceptance.py
```

found:

```text
66 uniquely labeled logical checkpoints
CP-01 through CP-66
66 test functions
```

The file expands to **92 pytest cases** because six checkpoints are parametrized:

```text
CP-05 → 2 cases
CP-06 → 11 cases
CP-50 → 4 cases
CP-53 → 5 cases
CP-54 → 5 cases
CP-55 → 5 cases
```

That explains the reported `92`, but 92 is the parametrized test-case count, not the logical checkpoint count.

### Required remediation

Use unambiguous evidence, for example:

```text
AT-DP-033=66/66 LOGICAL CHECKPOINTS PASS
AT-DP-033_PYTEST_CASES=92 PASS
```

Update the roadmap and future audit manifest accordingly.

No production-code change is required for this minor.

---

## Independently confirmed PASS areas

### Bundle integrity / supply-chain boundary

- SHA-256 independently matches:
  `cae48f9dc2287a0ceea9938b256c0e968eff8e96bfae937bb1f572eb16262e2c`.
- 1,832 archive entries inspected.
- No `.env`.
- No `.git`.
- No `.venv`.
- No cache/`.pyc` path.
- No private-key or forbidden credential path.
- No symlinks.
- Audit reports V1, V2 and V3 are present.

### V3 B2 fixes that do work

Independent probes confirmed:

```text
secret-shaped explicit event_id → rejected
private-marker reference_id → rejected
deep nested private-marker payload value → rejected
multi-part Cookie header → fully redacted
multi-part Set-Cookie header → fully redacted
password/session/csrf assignment sanitization → no raw secret remains
raw_prompt-like failure text → [REDACTED_ERROR]
listener exception secret text → absent from DomainEventPublicationError
```

### Retained V1/V2 invariants

Independent probes/static comparison confirmed:

- canonical general event catalog count remains exactly 23 and unique;
- schema-version mismatch fails closed;
- invalid `session_id`, `correlation_id`, `causation_id` types remain rejected;
- unordered `set`/`frozenset` sequence inputs remain rejected;
- `DomainLifecycleEventBridge` real resolver call-around still works;
- `primary_domain` reaches the real `DomainConflictResolver`;
- successful real conflict resolution emits detected → resolved in order;
- lifecycle bridge, publisher and registry are unchanged from the V3 audited implementation except for the targeted V3 remediation files where applicable;
- `DomainConflictResolver` remains free of event/Kernel publisher dependencies;
- no `AgentRuntimeEventBus` dependency exists in the Phase 10.33 event modules;
- no event persistence, replay, durable queue or DLQ was introduced;
- roadmap status remains `Implemented, pending independent re-audit`;
- Phase 10.34 has not been advanced.

## Repository verification evidence supplied with V4

The V4 manifest reports fresh post-commit verification on the audited HEAD:

```text
V3_REGRESSION_TESTS=38 PASS
FOCUSED_REAUDIT_TESTS=255 PASS
AT_DP_033=92/92 CHECKPOINTS PASS
DOMAIN_TESTS=7247 PASS
GLOBAL_TESTS=12787 PASS
RUFF_DELTA=PASS
FORMAT_DELTA=PASS
COMPILE_DELTA=PASS
DIFF_CHECK=PASS
SECRET_SCAN=PASS
WORKTREE=CLEAN
QUARANTINE_STASH=PRESERVED
```

For AT-DP-033, the test execution evidence is consistent with **92 pytest cases passing**, but the logical checkpoint count is **66**, as described in finding m4.

The independent audit sandbox could not collect the full repository pytest suite because the intentionally clean `git archive` excludes `.venv` and this environment does not provide repository dependency `libcst`.

The V4 verdict therefore uses:

- the supplied fresh repository verification evidence;
- independent bundle SHA/path verification;
- V3→V4 source comparison;
- static inspection;
- isolated direct execution of the audited event contracts, factory, registry, publisher, adapters, real conflict resolver and lifecycle bridge without executing the broad `cmm.domains.__init__`.

## Required next state

```text
PHASE10_33_INDEPENDENT_AUDIT_V4=FAIL
BLOCKERS=1
MAJORS=0
MINORS=1

AUDITED_HEAD=b78d56e6fbf03bb56e7b12f2c68197d7f08d5c5a
AUDIT_BUNDLE_SHA256=cae48f9dc2287a0ceea9938b256c0e968eff8e96bfae937bb1f572eb16262e2c

B2_EVENT_WIDE_PRIVACY=FAIL
B2_DOMAIN_ID_PRIVACY=FAIL
B2_VALIDATION_ERROR_NONDISCLOSURE=FAIL

M2_STRICT_OPTIONAL_IDENTIFIERS=PASS
M5_REAL_CONFLICT_LIFECYCLE=PASS
DETERMINISTIC_SEQUENCES=PASS

AT_DP_033_LOGICAL_CHECKPOINTS=66
AT_DP_033_PYTEST_CASES=92

CLOSE_PHASE=NO
ADVANCE_PHASE10_34=NO
NEXT=REMEDIATE_AUDIT_V4
PUSH=NO
MERGE=NO
```
