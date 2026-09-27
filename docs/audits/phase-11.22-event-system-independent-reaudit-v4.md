# Phase 11.22 — Event System — Independent Re-audit V4

**Project:** CMM OS
**Phase:** 11.22 — Event System
**Audit:** Independent ChatGPT Re-audit V4
**Audited branch:** `feature/phase-11-stable-integrated-platform`
**Audited HEAD:** `621cf5f67c2935f05cdc1ceb2ab966b562b1381e`
**Audited tree:** `9ce4e8eed31196529aa51825ebf8229ddf0f774a`
**Bundle:** `phase-11.22-event-system-audit-v4.tar.gz`
**Bundle SHA-256:** `18adf70d86f291b5585f71b746f81139ffa01e56e7c16dcbfc6b67bb794aaa0f`
**Design Point:** `DP-122`
**Connected acceptance:** `AT-DP-122`

## Verdict

```text
INDEPENDENT_REAUDIT_V4=FAIL

BLOCKERS=0
MAJORS=3
MINORS=0

MAJOR_V4_001=MEMORYVIEW_BINARY_BYPASSES_CANONICAL_EVENT_SAFETY
MAJOR_V4_002=MANUAL_PUBLISH_EVENT_SENSITIVITY_NOT_CANONICALIZED
MAJOR_V4_003=DLQ_ERROR_TYPE_CAN_LEAK_SECRET_TEXT

DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO

NEXT_STEP=REMEDIATION_V4_ONLY
```

Phase 11.22 remains open.

Phase 11.23 must not begin.

---

# 1. Exact bundle provenance

Independent checks against the uploaded V4 bundle:

```text
AUDIT_V4_SHA256=
18adf70d86f291b5585f71b746f81139ffa01e56e7c16dcbfc6b67bb794aaa0f

GZIP_INTEGRITY=PASS
PAX_COMMIT=
621cf5f67c2935f05cdc1ceb2ab966b562b1381e

RECONSTRUCTED_TREE=
9ce4e8eed31196529aa51825ebf8229ddf0f774a

RECONSTRUCTED_TRACKED_FILE_COUNT=2545
```

The reconstructed tree exactly matches the declared remediation tree.

Historical evidence embedded in V4 remains byte-identical:

```text
V1_AUDIT_REPORT_SHA256=
3d259b8ee9dd56d00da35d19d53670d625b399c35bff70e3ccd76e681beb1cb1

V2_REAUDIT_REPORT_SHA256=
20357eb6da9890900c8e8dc86c104d8b0559e8504c18afb67846147f51e5b771

V3_REAUDIT_REPORT_SHA256=
34969a29b49630e42762f17667383c3e05d3c7bafa4666bc430602723c1bf0c8

DESIGN_SPEC_SHA256=
d7e3cb3de474776f591fee576103db5d80db0f53fc85dd6c3293cd58c2b72f40
```

Result:

```text
BUNDLE_INTEGRITY=PASS
EXACT_HEAD=PASS
EXACT_TREE=PASS
HISTORICAL_AUDIT_EVIDENCE_PRESERVED=PASS
```

No symlinks, sensitive-key paths or files larger than 10 MiB were found in the archive.

---

# 2. Architecture review

The accepted one-authority architecture remains intact.

No second production:

- event bus;
- mutable event registry;
- repository contract;
- replay engine;
- dead-letter subsystem;
- application container;
- service locator;
- external broker abstraction

was found.

No reverse dependency from `cmm.agent_runtime` into `cmm.events` was found.

Result:

```text
ONE_CANONICAL_EVENT_BUS=PASS
ONE_CANONICAL_EVENT_REGISTRY=PASS
ONE_CANONICAL_EVENT_REPOSITORY_CONTRACT=PASS
ONE_CANONICAL_REPLAY_OWNER=PASS
NO_PARALLEL_DLQ_AUTHORITY=PASS
ARCHITECTURE_DIRECTION=PASS
```

---

# 3. V3 remediation concrete reproductions

The specific V3 failures that drove Remediation V3 were independently reproduced against V4 and now pass.

## Persisted metadata safety

The public path now rejects before persistence:

```text
opaque object
bytes
bytearray
NaN
+inf
SecretObject whose __str__ returns an API key
invalid numeric sensitivity
credential-bearing sensitivity
plain-string permissions
```

No durable mutation occurred in those tested rejection cases.

## Structured payload canonicalization

Safe nested structures now publish and reopen correctly:

```text
result_reference -> dict
approval_refs -> list[dict]
supporting_domains -> list
```

The independently observed live/reopen event equality is now:

```text
LIVE_EVENT_EQUALS_REOPENED_EVENT=True
```

The prior caller-alias reproduction is also fixed: mutating the caller-owned nested list/dict after `publish_event()` does not mutate the publication result or repository snapshot.

## DLQ snapshot detachment

Mutating a value returned from DLQ `get()` no longer changes a later queue observation.

Result:

```text
V3_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED
```

---

# 4. Prior fixes regression review

The V4 remediation did not reintroduce the major previously verified defects.

Independent direct checks confirmed, among others:

```text
CONTENT_BOUND_FINGERPRINT_CORRELATION_CHANGE=PASS
DIRECT_PUBLISH_EVENT_PROMPT_REJECTION=PASS
UNSUPPORTED_SCHEMA_REJECTED_BEFORE_PERSISTENCE=PASS
SUBSCRIBER_MUTATION_ISOLATION=PASS
TARGETED_DLQ_REPLAY=PASS
```

The historical V1/V2/V3 reports remain unchanged.

No prior architecture or Domain bridge regression was found in the V4 delta.

---

# 5. Independent execution limitations

The independent audit container does not contain all repository development dependencies.

Specifically:

```text
libcst = unavailable
ruff   = unavailable
```

and network installation is unavailable.

Therefore the complete repository pytest suite and exact Ruff command could not be rerun unchanged.

The committed V4 remediation evidence reports:

```text
REMEDIATION_V3_TESTS=44 passed
PHASE_SUITE=956 passed
AT-DP-122=83 passed
PHASE9_EVENT_REGRESSIONS=3635 passed
DOMAIN_SUITE=11824 passed
EVENT_INVENTORY=1270 passed
GLOBAL_PYTEST=23025 passed, 1 warning, 0 failed
GLOBAL_RUFF_COUNT=810
```

Independent compilation succeeded:

```text
python -m compileall -q cmm kernel
COMPILEALL=PASS
```

The FAIL verdict below is not caused by missing dependencies. Each finding was reproduced directly against the audited V4 production modules.

---

# 6. MAJOR-V4-001 — `memoryview` binary values bypass canonical event safety

## Affected code

Primary area:

```text
cmm/events/event_payload_safety.py:295-298
cmm/events/event_payload_safety.py:301-366
cmm/events/event_payload_safety.py:672-706
```

The V3 remediation correctly added `memoryview` to the scalar binary rejection:

```python
if isinstance(value, (bytes, bytearray, memoryview)):
    raise PlatformEventPayloadError(...)
```

But the rejection is unreachable for `memoryview` in payload scanning because `_is_sequence()` excludes only:

```text
str
bytes
bytearray
```

and does not exclude `memoryview`.

In Python, `memoryview(...)` is a `collections.abc.Sequence`.

Therefore the scanner treats a binary buffer as a normal sequence and recursively accepts its integer bytes.

The canonicalizer then converts the binary buffer into a plain integer list.

## Independent reproduction

Public Phase 11.22 publication:

```python
system.publish(
    "message.received",
    {
        "request_id": "mv",
        "channel": "conversation",
        "supporting_domains": memoryview(b"secret-binary"),
    },
)
```

was accepted.

The live canonical payload became:

```text
[115, 101, 99, 114, 101, 116, 45, 98, 105, 110, 97, 114, 121]
```

and those values were durably written to JSONL.

Result:

```text
BINARY_MEMORYVIEW_ACCEPTED=True
BINARY_MEMORYVIEW_PERSISTED=True
```

The same structural problem also affects the forbidden-content scanner used for persisted header containers. A manually constructed event with metadata containing a `memoryview` can be normalized to a list of integers instead of being rejected.

## Why this is major

The frozen Phase 11.22 design explicitly prohibits:

```text
arbitrary binary payloads
```

and Remediation V3 explicitly claimed:

```text
BINARY_VALUES_NEVER_ENTER_ANY_PERSISTED_EVENT_FIELD
```

This is a direct bypass of that closure-critical security invariant.

## Required remediation

The one existing sequence predicate/safety authority must classify `memoryview` as binary, not as an ordinary descriptive sequence.

At minimum:

```text
payload.data memoryview -> reject
nested payload memoryview -> reject
metadata memoryview -> reject
nested metadata memoryview -> reject
manual publish_event memoryview -> reject
```

before canonicalization or persistence.

Do not add another safety-policy module.

---

# 7. MAJOR-V4-002 — manual `publish_event()` does not canonicalize an accepted sensitivity string

## Affected code

Primary areas:

```text
cmm/events/event_payload_safety.py:541-584
cmm/events/event_payload_safety.py:607-644
cmm/events/event_system.py:287-321
cmm/events/event_system.py:487-514
cmm/agent_runtime/runtime_event_factory.py:394-445
```

The V3 remediation defines one canonical sensitivity normalization:

```text
EventSensitivity member
or
canonical string -> EventSensitivity
```

and `create_event()` correctly uses the returned canonical enum.

However `validate_platform_event_facts()` merely calls:

```python
canonicalize_platform_event_sensitivity(...)
```

and discards its return value.

`EventSystem._validate_platform_event()` then passes the original event to `AgentRuntimeEventNormalizer`.

The normalizer currently copies:

```python
sensitivity=header.sensitivity
```

unchanged.

Therefore a manually constructed event with:

```text
sensitivity="restricted"
```

passes the public `publish_event()` safety check but does not become `EventSensitivity.RESTRICTED`.

## Independent reproduction — official in-memory repository

With the official in-memory repository:

```text
publish_event(manual_event_with_sensitivity_string)
→ ACCEPTED
```

and both the publication result and stored event contain:

```text
sensitivity = "restricted"
type = str
```

not the canonical enum.

## Independent reproduction — durable repository

With the official file-backed repository, the same public event produces:

```text
AttributeError: 'str' object has no attribute 'value'
```

when canonical serialization expects:

```python
header.sensitivity.value
```

Thus the exact same public `publish_event()` call:

```text
succeeds with one official repository implementation
fails with the other
```

because the supposed canonical normalization was validation-only rather than normalization.

## Why this is major

Remediation V3 explicitly established:

```text
sensitivity has one canonical runtime representation
```

and the Phase 11.22 public `publish_event()` method was already established in Audit V1 as a canonical publication boundary, not a trusted bypass.

The current behavior breaks:

- one canonical header representation;
- consistency between official in-memory and durable repository implementations;
- deterministic publication semantics across the canonical repository contract.

## Required remediation

At the Phase 11.22 publication boundary, either:

1. canonically normalize a valid sensitivity string to `EventSensitivity` before the normalized event is returned/persisted; or
2. make manual `publish_event()` strictly require `EventSensitivity` and reject bare strings before persistence.

Whichever rule is chosen, it must be explicit and consistent with the public `publish()` contract and documentation.

The same event must not succeed with the in-memory repository and crash with the durable implementation.

---

# 8. MAJOR-V4-003 — DLQ `error_type` can itself contain secret text

## Affected code

Primary area:

```text
cmm/agent_runtime/runtime_event_bus.py:389-442
cmm/agent_runtime/runtime_event_bus.py:515-540
```

The existing V1 hardening correctly stopped storing the raw exception message in the canonical DLQ path.

It now stores only:

```python
type(exc).__name__
```

as `error_type` and `error`.

That is safer for ordinary exception classes, but the class name itself is not validated or sanitized before becoming DLQ data.

Python permits dynamically created exception classes with arbitrary names.

## Independent reproduction

A replay/delivery subscriber raised an exception whose class was created as:

```python
Evil = type(
    "api_key=abcdef1234567890",
    (Exception,),
    {},
)
```

After bounded delivery exhaustion:

```text
dead_lettered = True
```

and the retained canonical DLQ entry contained:

```text
error_type = "api_key=abcdef1234567890"
error      = "api_key=abcdef1234567890"
```

Result:

```text
SECRET_TEXT_ENTERED_DLQ_DATA=True
```

No raw exception message or traceback was needed.

## Why this is major

The frozen security invariant states:

```text
secrets and credentials never enter event persistence or DLQ data
```

and the design requires a:

```text
safe error category/type
```

not merely any raw Python class name.

This is a direct violation of a closure-critical security invariant.

## Required remediation

Keep raw exception messages excluded.

Derive one bounded safe DLQ error category.

A valid minimal strategy is:

- accept an exception type name only if it passes a narrow safe identifier policy and the existing private/credential scanners;
- otherwise store a neutral category such as `Exception` or `SubscriberDeliveryError`.

Do not store the original unsafe class name anywhere in the DLQ record or DLQ-facing delivery metadata.

Add adversarial tests for:

```text
credential-bearing exception class name
private-marker exception class name
ordinary RuntimeError remains safely categorized
```

Do not create a second DLQ subsystem.

---

# 9. Security assessment

Positive:

```text
ordinary payload prompt/credential rejection = PASS
opaque object rejection = PASS
bytes/bytearray rejection = PASS
NaN/infinity rejection = PASS
ordinary header relocation rejection = PASS
raw payload prohibition = PASS
```

But:

```text
memoryview binary rejection = FAIL
DLQ safe error category = FAIL
```

Current result:

```text
FULL_CANONICAL_EVENT_SECURITY=FAIL
DLQ_SECRET_SAFETY=FAIL
```

---

# 10. Canonicalization and persistence assessment

Positive:

```text
nested mapping publication = PASS
nested list publication = PASS
live/reopen structured shape = PASS
caller nested-alias isolation = PASS
subscriber isolation = PASS
repository snapshot isolation = PASS
unsupported schema rejection = PASS
content-bound fingerprint = PASS
```

But manual sensitivity normalization remains inconsistent:

```text
IN_MEMORY_REPOSITORY + manual sensitivity string = ACCEPTED AS str
FILE_REPOSITORY + same event = AttributeError
```

Current result:

```text
CANONICAL_SENSITIVITY_REPRESENTATION=FAIL
REPOSITORY_IMPLEMENTATION_PARITY=FAIL
```

---

# 11. Replay and DLQ assessment

The previously fixed targeted replay semantics remain intact in the independent direct check:

```text
TARGETED_DLQ_REPLAY=PASS
UNRELATED_SUBSCRIBER_NOT_INVOKED=PASS
DLQ_REMOVED_AFTER_TARGET_SUCCESS=PASS
```

Detached DLQ inspection snapshots also pass.

The V4 DLQ finding is strictly the unsanitized `error_type` content channel.

---

# 12. DP-122 assessment

DP-122 requires the event path to be:

- canonical;
- durable;
- content-bound;
- privacy preserving;
- safely failure-aware;
- deterministic across the official repository contract.

V4 now satisfies the concrete V3 structured payload and snapshot issues.

However independent V4 execution proves:

1. binary data can still enter canonical durable event content through `memoryview`;
2. the public manual publication boundary does not produce one canonical sensitivity representation across official repository implementations;
3. secret text can enter canonical DLQ data through an exception class name.

Therefore:

```text
DP-122=NOT_VERIFIED
```

---

# 13. AT-DP-122 assessment

The implementation evidence reports:

```text
AT-DP-122=83 passed
```

but the connected acceptance does not cover the independently reproduced V4 cases:

- payload `memoryview`;
- metadata/manual-event `memoryview`;
- valid bare sensitivity string through manual `publish_event()`;
- repository parity for that manual event;
- credential-bearing dynamic exception type reaching DLQ.

Because independently observed behavior still contradicts DP-122:

```text
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
```

This does not assert that the 83 committed tests themselves fail.

It means the acceptance remains incomplete relative to the frozen design point.

---

# 14. Required Remediation V4 scope

Remediation V4 must fix **only** the three V4 majors.

## MAJOR-V4-001

Close the `memoryview` binary sequence bypass in the existing safety authority.

## MAJOR-V4-002

Make manual `publish_event()` sensitivity handling canonical and identical across official repository implementations.

## MAJOR-V4-003

Sanitize/fail closed on unsafe exception type names before any DLQ data is created.

Preserve all earlier V1/V2/V3 fixes.

Do not redesign Phase 11.22.

Do not begin Phase 11.23 or 11.24.

---

# 15. Required new regressions

At minimum:

```text
payload memoryview rejected before persistence
nested payload memoryview rejected
metadata memoryview rejected
manual publish_event metadata memoryview rejected

manual publish_event sensitivity="restricted":
  either canonicalizes to EventSensitivity.RESTRICTED everywhere
  or is explicitly rejected everywhere
  in-memory and file-backed behavior identical

credential-bearing exception class name:
  no credential appears in DLQ error/error_type/metadata

private-marker exception class name:
  no private marker appears in DLQ data

ordinary RuntimeError:
  bounded safe category remains useful
```

Retain all V1/V2/V3 remediation regressions.

---

# 16. Required gates after Remediation V4

Before the next independent re-audit:

1. V4 regression tests;
2. V1 remediation regressions;
3. V2 remediation regressions;
4. V3 remediation regressions;
5. full `tests/events/`;
6. strengthened `AT-DP-122`;
7. Phase 9 runtime-event suite;
8. Phase 10.33 Domain Event suite/acceptance;
9. orchestration/validation/workflow connected regressions;
10. `AT-DP-102`;
11. `AT-DP-103`;
12. `AT-DP-105`;
13. Phase 11.21;
14. Phase 11.34 where relevant;
15. `AT-DP-150`;
16. complete event inventory;
17. global pytest;
18. changed-file Ruff;
19. global Ruff no-new-debt relative to V4 evidence count `810`;
20. format;
21. compileall;
22. `git diff --check`;
23. architecture anti-fragmentation gates;
24. event-security gates;
25. tracked clean state.

No unrelated cleanup.

---

# 17. Historical artifacts remain immutable

Do not modify or overwrite:

```text
phase-11.22-event-system-audit-v1.tar.gz
phase-11.22-event-system-audit-v2.tar.gz
phase-11.22-event-system-audit-v3.tar.gz
phase-11.22-event-system-audit-v4.tar.gz

docs/audits/phase-11.22-event-system-independent-audit-v1.md
docs/audits/phase-11.22-event-system-independent-reaudit-v2.md
docs/audits/phase-11.22-event-system-independent-reaudit-v3.md
```

Historical bundle hashes:

```text
V1:
a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3

V2:
172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04

V3:
27517348570837df2abe9fc7f11e5cc24cefc32a198ffe3e0afefaee5df3c589

V4:
18adf70d86f291b5585f71b746f81139ffa01e56e7c16dcbfc6b67bb794aaa0f
```

This V4 audit report also becomes immutable once committed.

---

# 18. Next bundle

After Remediation V4:

```text
phase-11.22-event-system-audit-v5.tar.gz
```

must be generated from the exact final committed HEAD using `git archive`.

Report:

- exact HEAD;
- exact tree;
- SHA-256;
- tracked worktree clean.

Do not overwrite V4.

---

# 19. Final V4 audit markers

```text
PHASE=11.22
INDEPENDENT_REAUDIT_V4=FAIL

AUDIT_HEAD=621cf5f67c2935f05cdc1ceb2ab966b562b1381e
AUDIT_TREE=9ce4e8eed31196529aa51825ebf8229ddf0f774a
AUDIT_BUNDLE=phase-11.22-event-system-audit-v4.tar.gz
AUDIT_BUNDLE_SHA256=18adf70d86f291b5585f71b746f81139ffa01e56e7c16dcbfc6b67bb794aaa0f

BUNDLE_INTEGRITY=PASS
EXACT_HEAD=PASS
EXACT_TREE=PASS
ARCHITECTURE_DIRECTION=PASS

V3_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED

BLOCKERS=0
MAJORS=3
MINORS=0

MAJOR_V4_001=MEMORYVIEW_BINARY_BYPASSES_CANONICAL_EVENT_SAFETY
MAJOR_V4_002=MANUAL_PUBLISH_EVENT_SENSITIVITY_NOT_CANONICALIZED
MAJOR_V4_003=DLQ_ERROR_TYPE_CAN_LEAK_SECRET_TEXT

DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO

NEXT_STEP=REMEDIATION_V4_ONLY
```
