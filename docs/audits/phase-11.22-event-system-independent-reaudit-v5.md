# Phase 11.22 — Event System — Independent Re-audit V5

**Project:** CMM OS
**Phase:** 11.22 — Event System
**Audit:** Independent ChatGPT Re-audit V5
**Audited branch:** `feature/phase-11-stable-integrated-platform`
**Audited HEAD:** `8187ec9064247ca3a26d764fa7386c241b21f302`
**Audited tree:** `1268d3f066e49632d25f5e0bce6ff76f2b97bcad`
**Bundle:** `phase-11.22-event-system-audit-v5.tar.gz`
**Bundle SHA-256:** `105203eb4ea1d0e1b3200ee30b7130961af70283d8be9fc7b28ed65279003d10`
**Design Point:** `DP-122`
**Connected acceptance:** `AT-DP-122`

## Verdict

```text
INDEPENDENT_REAUDIT_V5=FAIL

V4_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED
PRIOR_REMEDIATION_REGRESSIONS=279_PASS

BLOCKERS=0
MAJORS=3
MINORS=0

MAJOR_V5_001=ARRAY_BUFFER_BINARY_BYPASSES_CANONICAL_EVENT_SAFETY
MAJOR_V5_002=BOUNDED_PAYLOAD_SEMANTICS_DO_NOT_PREVENT_RAW_CONTENT_MIRRORING
MAJOR_V5_003=CANONICAL_BUS_DLQ_SECRET_SAFETY_DEPENDS_ON_EXTERNAL_CATEGORIZER_BINDING

DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO

NEXT_STEP=REMEDIATION_V5_ONLY
```

Phase 11.22 remains open.

Phase 11.23 must not begin.

---

# 1. Exact V5 bundle provenance

Independent verification of the uploaded V5 archive:

```text
AUDIT_V5_SHA256=
105203eb4ea1d0e1b3200ee30b7130961af70283d8be9fc7b28ed65279003d10

GZIP_INTEGRITY=PASS

PAX_COMMIT=
8187ec9064247ca3a26d764fa7386c241b21f302

RECONSTRUCTED_TREE=
1268d3f066e49632d25f5e0bce6ff76f2b97bcad

RECONSTRUCTED_TRACKED_FILE_COUNT=2548
SYMLINK_COUNT=0
SENSITIVE_PATH_HITS=0
GIT_PATH_HITS=0
```

The Git tree was independently reconstructed from the archive with a fresh Git index and exactly matches the declared remediation tree.

Historical independent reports embedded in the exact V5 tree remain byte-identical:

```text
V1_AUDIT_REPORT_SHA256=
3d259b8ee9dd56d00da35d19d53670d625b399c35bff70e3ccd76e681beb1cb1

V2_REAUDIT_REPORT_SHA256=
20357eb6da9890900c8e8dc86c104d8b0559e8504c18afb67846147f51e5b771

V3_REAUDIT_REPORT_SHA256=
34969a29b49630e42762f17667383c3e05d3c7bafa4666bc430602723c1bf0c8

V4_REAUDIT_REPORT_SHA256=
ca025aae4896a629f5d9acd2904622b8282036228ff905b856feb41647afb0f9

DESIGN_SPEC_SHA256=
d7e3cb3de474776f591fee576103db5d80db0f53fc85dd6c3293cd58c2b72f40
```

The historical V1–V4 bundles available to the independent audit also retain their exact prior hashes.

Result:

```text
BUNDLE_INTEGRITY=PASS
EXACT_HEAD=PASS
EXACT_TREE=PASS
HISTORICAL_AUDIT_EVIDENCE_PRESERVED=PASS
```

---

# 2. V4 remediation scope review

Comparing V4 and V5 exact archive contents shows a narrow remediation delta.

Production changes are limited to:

```text
cmm/events/event_payload_safety.py
cmm/events/event_system.py
cmm/agent_runtime/runtime_event_bus.py
```

plus the new V4 regression module, strengthened AT-DP-122 and current evidence/reference/roadmap documents.

No second bus, repository protocol, replay engine, DLQ authority, event contract, application container or safety subsystem was introduced.

Result:

```text
ARCHITECTURE_DIRECTION=PASS
REMEDIATION_SCOPE_CONTROL=PASS
```

---

# 3. Independent executable verification

The audit container lacks repository development dependencies including:

```text
libcst
ruff
```

and cannot install them from the network.

Therefore the complete repository suite and exact Ruff gate could not be re-executed unchanged.

This limitation does **not** cause the FAIL verdict below. All three V5 findings were reproduced directly against the audited V5 production modules.

Independent executable checks against the exact V5 bytes:

```text
V4_REMEDIATION_REGRESSIONS=23 passed
V1_TO_V4_REMEDIATION_REGRESSIONS=279 passed
PHASE9_RUNTIME_EVENT_BUS=222 passed
FOCUSED_PHASE11_22_EVENT_TESTS=498 passed
DURABLE_REPOSITORY_FOCUSED=27 passed
COMPILEALL=PASS
```

The committed V5 remediation evidence reports:

```text
PHASE_SUITE=991 passed
AT-DP-122=95 passed
PHASE9_EVENT_REGRESSIONS=3635 passed
DOMAIN_SUITE=11824 passed
EVENT_INVENTORY=1270 passed
GLOBAL_PYTEST=23060 passed, 1 warning, 0 failed
GLOBAL_RUFF_COUNT=810
```

The independent broader `tests/events/` attempt reached hundreds of passing tests. Remaining collection/setup failures were caused by unavailable `libcst`, the audit import shim or root filesystem permission semantics.

---

# 4. V4 concrete findings are fixed — 3/3

The exact V4 regression module independently passes:

```text
tests/events/test_phase11_22_remediation_v4_regressions.py
23 passed
```

## V4-001 — `memoryview`

`memoryview` is now classified as binary rather than a descriptive sequence.

The exact previous bypass fails closed before persistence.

Status:

```text
V4_001_MEMORYVIEW_REPRODUCTION=PASS
```

## V4-002 — manual sensitivity

A manual event passed through `publish_event()` with:

```text
sensitivity="restricted"
```

is now normalized to:

```text
EventSensitivity.RESTRICTED
```

before persistence.

In-memory and file-backed repository behavior is aligned.

Status:

```text
V4_002_MANUAL_SENSITIVITY_REPRODUCTION=PASS
```

## V4-003 — composed EventSystem DLQ class-name sanitization

When the canonical composed `EventSystem` is used, credential-bearing and private-marker dynamic exception class names are neutralized to a bounded category.

Ordinary `RuntimeError` remains useful.

Status:

```text
V4_003_COMPOSED_DLQ_REPRODUCTION=PASS
```

Therefore:

```text
V4_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED
```

The fresh findings below concern broader frozen invariants not exercised by the V4 regressions.

---

# 5. MAJOR-V5-001 — `array.array` binary buffer bypasses canonical event safety

## Affected code

Primary area:

```text
cmm/events/event_payload_safety.py
```

Relevant mechanisms:

```text
_is_sequence()
_reject_non_descriptive_value()
_scan()
_scan_for_forbidden_event_facts()
_canonicalize_payload_value()
```

## Problem

Remediation V4 closed the exact `memoryview` gap by excluding:

```text
str
bytes
bytearray
memoryview
```

from the generic sequence predicate.

But the policy still defines binary by a short explicit type tuple rather than the binary/buffer nature of the value.

`array.array` is a compact binary buffer and also behaves as a sequence.

Therefore:

```python
array.array("B", b"secret-binary")
```

is treated as a descriptive integer sequence.

It is accepted and canonicalized to:

```text
[115, 101, 99, 114, 101, 116, 45, 98, 105, 110, 97, 114, 121]
```

## Independent durable reproduction

Public Phase 11.22 call:

```python
system.publish(
    "message.received",
    {
        "request_id": "arr",
        "channel": "conversation",
        "supporting_domains": array.array("B", b"secret-binary"),
    },
    event_id="evt-array",
)
```

was accepted.

The file-backed repository durably stored the integer array.

Result:

```text
ARRAY_BUFFER_ACCEPTED=True
ARRAY_BUFFER_PERSISTED=True
```

## Why this is major

The frozen design explicitly requires rejection of:

```text
arbitrary binary payloads
```

and the current reference contract states that binary values never enter persisted event content.

The fix currently enumerates a few binary Python classes, but the invariant is semantic: binary/buffer content must fail closed regardless of which standard binary container exposes it.

This is the same closure-critical security class as V4-001, reached through a different standard-library buffer type.

## Required Remediation V5

Strengthen the **existing** binary/value classifier.

At minimum cover:

```text
bytes
bytearray
memoryview
array.array
```

and preferably use a bounded buffer-protocol check if it can be done safely and compatibly.

Required permanent regressions:

```text
array.array("B", ...) in payload -> reject
nested array.array in payload -> reject
array.array in metadata -> reject
nested array.array in metadata -> reject
manual publish_event array.array -> reject
durable file remains unchanged
```

Do not add a second safety module.

---

# 6. MAJOR-V5-002 — bounded payload semantics do not prevent raw content mirroring

## Affected code

Primary area:

```text
cmm/events/event_payload_safety.py
```

The current Phase 11.22 boundary strongly validates:

- allowed key names;
- forbidden key names;
- credentials/private markers;
- JSON-safe structural types;
- binary/non-finite values.

However it does **not** validate the semantic value class implied by the allowed key.

Examples:

```text
request_id      -> identifier/reference
status          -> categorical state
count           -> bounded number
approved        -> boolean lifecycle fact
duration_ms     -> numeric duration
```

are not type/value constrained according to those semantics.

Any ordinary string that does not contain the private-marker or credential vocabulary is accepted for all of them.

## Independent reproduction — raw user text in categorical payload

The frozen design says:

```text
Platform events are lifecycle facts, not content mirrors.
```

and explicitly requires rejecting:

```text
raw user text
```

unless an existing contract defines a safe projection.

Nevertheless this public call is accepted:

```python
raw = (
    "My landlord entered my flat without permission yesterday "
    "and I need legal advice."
)

system.publish(
    "message.received",
    {
        "request_id": "raw-user-1",
        "status": raw,
    },
    metadata={"note": raw},
    event_id="evt-raw",
)
```

The exact raw sentence is durably present in the JSONL record in both:

```text
payload.data["status"]
header.metadata["note"]
```

Result:

```text
RAW_USER_TEXT_ACCEPTED=True
RAW_USER_TEXT_PERSISTED=True
```

## Independent reproduction — identity key used as content mirror

Even a field documented as an identifier/reference accepts prose:

```python
system.publish(
    "message.received",
    {
        "request_id":
            "My landlord entered my flat without permission yesterday "
            "and I need legal advice.",
        "channel": "conversation",
    },
    event_id="evt-prose-id",
)
```

Result:

```text
REQUEST_ID_PROSE_ACCEPTED=True
REQUEST_ID_PROSE_PERSISTED=True
```

## Independent reproduction — unbounded categorical text

A `status` value containing 10,000 arbitrary characters is accepted and persisted.

The key allowlist is therefore bounded, but the semantic fact is not.

## Why this is major

The design's safety model is stronger than:

```text
only approved key names
```

It explicitly says the platform may persist:

```text
IDs/references
categorical states
bounded counts/durations
versions
boolean lifecycle facts
```

and must reject raw user text.

The current implementation checks key vocabulary but not the value contract associated with those keys.

Therefore a producer can move content into an innocuous allowed field without using a forbidden key or recognizable credential/private marker.

This violates the central privacy invariant:

```text
platform events are lifecycle facts, not content mirrors
```

## Required Remediation V5

Extend the **existing** Phase 11.22 payload-safety authority with bounded semantic value classes.

Do not create a second payload registry.

At minimum establish explicit groups for:

```text
identifier/reference fields
categorical/token fields
boolean fields
numeric/count/duration fields
timestamp/version fields
structured reference containers
```

Examples of required behavior:

```text
request_id="req-123"                    -> allowed
request_id="<raw sentence/prose>"       -> rejected

status="completed"                      -> allowed
status="<raw sentence/prose>"           -> rejected

approved=True                           -> allowed
approved="<raw text>"                   -> rejected

duration_ms=125                         -> allowed
duration_ms="<raw text>"                -> rejected
```

Persisted metadata must also remain lifecycle metadata rather than an unrestricted prose side channel.

The implementation must preserve legitimate existing metadata such as:

```text
{"status_code": "ok", "attempt": 1}
{"origin": "original"}
```

while refusing raw free-form content mirroring.

Strengthen `AT-DP-122` with real file-backed evidence proving raw user text cannot be relocated into:

```text
identifier keys
categorical keys
metadata
```

before persistence.

---

# 7. MAJOR-V5-003 — canonical bus DLQ secret safety depends on external categorizer binding

## Affected code

Primary area:

```text
cmm/agent_runtime/runtime_event_bus.py
cmm/events/event_system.py
```

The V4 remediation splits the DLQ error-category policy:

```text
transport-local bounded identifier check
+
credential/private-marker categorizer injected by EventSystem
```

The canonical composed `EventSystem` binds the second half correctly.

But `AgentRuntimeEventBus` remains the sole canonical transport authority and exposes public:

```text
bind_dead_letter_queue()
bind_error_categorizer()
```

The categorizer defaults to `None`.

When absent, `safe_delivery_error_type()` accepts every bounded Python identifier-shaped exception class name.

That includes credential-bearing identifier-shaped names such as:

```text
api_key_abcdef1234567890
```

## Independent reproduction

Using the canonical Phase 9/11.22 components directly:

```python
bus = AgentRuntimeEventBus(max_delivery_attempts=2)
dlq = InMemoryAgentRuntimeDeadLetterQueue()
bus.bind_dead_letter_queue(dlq)

Evil = type(
    "api_key_abcdef1234567890",
    (Exception,),
    {},
)

def failing(event):
    raise Evil("boom")

bus.subscribe(failing, ["message.received"])
bus.publish(canonical_event)
```

produces a canonical dead-letter entry with:

```text
error_type = "api_key_abcdef1234567890"
error      = "api_key_abcdef1234567890"
```

Result:

```text
DIRECT_CANONICAL_BUS_DLQ_SECRET_PRESENT=True
```

## Why this is major

The design explicitly declares:

```text
AgentRuntimeEventBus remains the sole event transport authority.
```

and:

```text
the existing runtime-event dead-letter contracts and queue remain canonical.
```

It also requires:

```text
secrets and credentials never enter event persistence or DLQ data
```

The compatibility requirement for legacy direct bus use is only that default behavior must not unexpectedly multiply handler invocations.

It does not grant a privacy exception to the new bounded-retry/DLQ path.

The safety of the canonical transport therefore cannot silently depend on a caller remembering an optional second binding before using the canonical DLQ feature.

## Required Remediation V5

Keep the architecture direction intact: `cmm.agent_runtime` must not import `cmm.domains`.

A minimal safe design can enforce one of these equivalent invariants:

```text
no categorizer bound
→ neutral error category for bounded retry/DLQ paths
```

or:

```text
DLQ-enabled bounded delivery cannot be activated until the canonical categorizer is bound
```

while preserving historical direct single-attempt behavior.

Ordinary composed `EventSystem` behavior should continue to preserve useful categories such as `RuntimeError`.

Required regressions:

```text
direct bus + bounded retries + canonical DLQ + no categorizer
+ credential-shaped class name
→ no secret in DLQ

same path with private-marker identifier name
→ no private marker in DLQ

legacy direct single-attempt behavior remains compatible

composed EventSystem RuntimeError remains useful
```

Do not import Domain policy into `cmm.agent_runtime`.

Do not create a second DLQ subsystem.

---

# 8. Security assessment

Positive V5 results:

```text
memoryview binary rejection = PASS
bytes/bytearray rejection = PASS
opaque object rejection = PASS
non-finite number rejection = PASS
manual sensitivity canonicalization = PASS
composed EventSystem dynamic exception sanitization = PASS
raw exception message exclusion from composed DLQ = PASS
```

Fresh failures:

```text
array.array binary rejection = FAIL
raw user text/content-mirroring prevention = FAIL
direct canonical bus DLQ credential safety = FAIL
```

Therefore:

```text
FULL_CANONICAL_EVENT_SECURITY=FAIL
LIFECYCLE_FACT_ONLY_POLICY=FAIL
DLQ_SECRET_SAFETY=FAIL
```

---

# 9. Persistence/canonicalization assessment

Positive:

```text
nested mapping canonicalization = PASS
sequence live/reopen canonical shape = PASS
caller alias isolation = PASS
subscriber isolation = PASS
repository snapshot isolation = PASS
manual sensitivity repository parity = PASS
unsupported schema rejection = PASS
content-bound fingerprint = PASS
```

Fresh failures are policy-boundary failures, not durable-store integrity failures:

```text
BINARY_BUFFER_POLICY_COMPLETE=FAIL
SEMANTIC_VALUE_BOUNDING=FAIL
```

The file-backed repository faithfully stores what the platform boundary incorrectly accepts.

---

# 10. Replay/DLQ assessment

Previously fixed targeted replay behavior remains intact in the focused event regression set.

Detached DLQ inspection remains fixed.

The V5 DLQ issue is a different boundary:

```text
canonical bus + canonical DLQ + no injected categorizer
```

can still retain credential-bearing class-name text.

No second replay/DLQ authority was found.

---

# 11. DP-122 assessment

DP-122 requires one canonical event path that is:

- durable;
- deterministic;
- content-bound;
- privacy preserving;
- bounded to safe lifecycle facts;
- failure-aware without leaking sensitive data.

V5 successfully closes the exact V4 defects.

However:

1. another standard binary buffer class still bypasses the binary policy;
2. the value semantics of allowed keys do not prevent raw user text from becoming durable lifecycle evidence;
3. the canonical bus's bounded retry/DLQ path is not fail-safe when the external error categorizer has not been bound.

Therefore:

```text
DP-122=NOT_VERIFIED
```

---

# 12. AT-DP-122 assessment

The implementation evidence reports:

```text
AT-DP-122=95 passed
```

and V4 scenarios are now represented.

But AT-DP-122 does not cover:

```text
array.array binary buffers
raw user text under an allowed identity/categorical key
raw user text through ordinary metadata
canonical bus + canonical DLQ without categorizer binding
```

Because independent observed behavior contradicts frozen DP-122 privacy/security invariants:

```text
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
```

This does not assert that the 95 committed tests themselves fail.

It means the acceptance remains incomplete relative to the design point.

---

# 13. Required Remediation V5 scope

Remediation V5 must fix **only** these three V5 majors.

## MAJOR-V5-001

Complete binary/buffer classification inside the existing safety authority.

## MAJOR-V5-002

Make the existing allowed payload vocabulary enforce the bounded semantic type/value class of each lifecycle fact, including raw-content prevention in metadata.

## MAJOR-V5-003

Make bounded retry/DLQ secret safety fail-safe at the canonical bus boundary even when the external categorizer has not been bound.

Preserve all previous V1–V4 fixes.

Do not redesign Phase 11.22.

Do not begin Phase 11.23 or 11.24.

---

# 14. Required new regressions

At minimum:

```text
array.array payload rejected before persistence
nested array.array rejected
metadata array.array rejected
manual event array.array rejected

request_id prose/raw-user-text rejected
status prose/raw-user-text rejected
approved raw text rejected
duration_ms raw text rejected
metadata raw prose rejected

legitimate request/status/bool/numeric/reference facts still pass
existing safe metadata examples still pass

direct canonical bus + canonical DLQ without categorizer:
credential-shaped identifier exception name -> neutral/no secret
private-marker identifier exception name -> neutral/no private marker

legacy direct single-attempt compatibility remains green
composed EventSystem ordinary RuntimeError remains useful
```

Retain every V1–V4 remediation regression.

---

# 15. Required gates after Remediation V5

Before another independent audit:

1. new V5 regressions;
2. all V1 remediation regressions;
3. all V2 remediation regressions;
4. all V3 remediation regressions;
5. all V4 remediation regressions;
6. full `tests/events/`;
7. strengthened `AT-DP-122`;
8. Phase 9 runtime-event suite;
9. Phase 10.33 Domain Event suite/acceptance;
10. orchestration/validation/workflow connected regressions;
11. `AT-DP-102`;
12. `AT-DP-103`;
13. `AT-DP-105`;
14. Phase 11.21;
15. Phase 11.34 where relevant;
16. `AT-DP-150`;
17. complete event inventory;
18. global pytest;
19. changed-file Ruff;
20. global Ruff no-new-debt relative to count `810`;
21. format;
22. compileall;
23. `git diff --check`;
24. architecture anti-fragmentation gates;
25. event-security gates;
26. tracked clean state.

No unrelated cleanup.

---

# 16. Historical artifacts remain immutable

Do not modify or overwrite:

```text
phase-11.22-event-system-audit-v1.tar.gz
phase-11.22-event-system-audit-v2.tar.gz
phase-11.22-event-system-audit-v3.tar.gz
phase-11.22-event-system-audit-v4.tar.gz
phase-11.22-event-system-audit-v5.tar.gz

docs/audits/phase-11.22-event-system-independent-audit-v1.md
docs/audits/phase-11.22-event-system-independent-reaudit-v2.md
docs/audits/phase-11.22-event-system-independent-reaudit-v3.md
docs/audits/phase-11.22-event-system-independent-reaudit-v4.md
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

V5:
105203eb4ea1d0e1b3200ee30b7130961af70283d8be9fc7b28ed65279003d10
```

This V5 audit report also becomes immutable historical evidence once committed.

---

# 17. Next bundle

After Remediation V5 create:

```text
phase-11.22-event-system-audit-v6.tar.gz
```

from the exact committed remediation HEAD via `git archive`.

Report:

```text
HEAD
TREE
SHA-256
TRACKED_WORKTREE=CLEAN
```

Do not overwrite V5.

---

# 18. Final V5 audit markers

```text
PHASE=11.22
INDEPENDENT_REAUDIT_V5=FAIL

AUDIT_HEAD=8187ec9064247ca3a26d764fa7386c241b21f302
AUDIT_TREE=1268d3f066e49632d25f5e0bce6ff76f2b97bcad
AUDIT_BUNDLE=phase-11.22-event-system-audit-v5.tar.gz
AUDIT_BUNDLE_SHA256=105203eb4ea1d0e1b3200ee30b7130961af70283d8be9fc7b28ed65279003d10

BUNDLE_INTEGRITY=PASS
EXACT_HEAD=PASS
EXACT_TREE=PASS
ARCHITECTURE_DIRECTION=PASS

V4_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED
PRIOR_REMEDIATION_REGRESSIONS=279_PASS

BLOCKERS=0
MAJORS=3
MINORS=0

MAJOR_V5_001=ARRAY_BUFFER_BINARY_BYPASSES_CANONICAL_EVENT_SAFETY
MAJOR_V5_002=BOUNDED_PAYLOAD_SEMANTICS_DO_NOT_PREVENT_RAW_CONTENT_MIRRORING
MAJOR_V5_003=CANONICAL_BUS_DLQ_SECRET_SAFETY_DEPENDS_ON_EXTERNAL_CATEGORIZER_BINDING

DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO

NEXT_STEP=REMEDIATION_V5_ONLY
```
