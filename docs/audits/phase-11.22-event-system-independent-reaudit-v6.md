# Phase 11.22 — Event System — Independent Re-audit V6

**Project:** CMM OS
**Phase:** 11.22 — Event System
**Audit:** Independent ChatGPT Re-audit V6
**Audited branch:** `feature/phase-11-stable-integrated-platform`
**Audited HEAD:** `2b45244a0f1b73a46e4cf2b93db40b3fcf88b552`
**Audited tree:** `f28f95ed7ae2a4a2e37de03a618688bbdf343b3b`
**Bundle:** `phase-11.22-event-system-audit-v6.tar.gz`
**Bundle SHA-256:** `67b27f6effa5297757453aba3021a7211fe4ee88e194a6d65eefa353060f1008`
**Design Point:** `DP-122`
**Connected acceptance:** `AT-DP-122`

## Verdict

```text
INDEPENDENT_REAUDIT_V6=FAIL

V5_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED
PRIOR_REMEDIATION_REGRESSIONS=350_PASS

BLOCKERS=0
MAJORS=3
MINORS=1

MAJOR_V6_001=NUMERIC_LIFECYCLE_FACTS_ARE_NOT_ACTUALLY_BOUNDED_AND_REPOSITORY_PARITY_BREAKS
MAJOR_V6_002=FILESYSTEM_SECRET_PATHS_CAN_ENTER_PERSISTED_IDENTIFIER_FIELDS
MAJOR_V6_003=PAYLOAD_CAN_SHADOW_CANONICAL_HEADER_IDENTITY_AND_SENSITIVITY_FACTS
MINOR_V6_001=CANONICAL_TIMESTAMP_VALIDATION_ACCEPTS_INVALID_OR_AMBIGUOUS_TIMESTAMPS

DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO

NEXT_STEP=REMEDIATION_V6_ONLY
```

Phase 11.22 remains open.

Phase 11.23 must not begin.

---

# 1. Exact V6 bundle provenance

Independent verification of the uploaded V6 archive:

```text
AUDIT_V6_SHA256=
67b27f6effa5297757453aba3021a7211fe4ee88e194a6d65eefa353060f1008

GZIP_INTEGRITY=PASS
TAR_INTEGRITY=PASS

PAX_COMMIT=
2b45244a0f1b73a46e4cf2b93db40b3fcf88b552

RECONSTRUCTED_TREE=
f28f95ed7ae2a4a2e37de03a618688bbdf343b3b

RECONSTRUCTED_TRACKED_FILE_COUNT=2551
SYMLINK_COUNT=0
PATH_TRAVERSAL_HITS=0
GIT_INTERNAL_PATH_HITS=0
```

The Git tree was independently reconstructed from a clean extraction using a fresh Git index. It exactly matches the declared remediation tree.

Historical independent reports embedded in the V6 tree remain byte-identical:

```text
V1_AUDIT_REPORT_SHA256=
3d259b8ee9dd56d00da35d19d53670d625b399c35bff70e3ccd76e681beb1cb1

V2_REAUDIT_REPORT_SHA256=
20357eb6da9890900c8e8dc86c104d8b0559e8504c18afb67846147f51e5b771

V3_REAUDIT_REPORT_SHA256=
34969a29b49630e42762f17667383c3e05d3c7bafa4666bc430602723c1bf0c8

V4_REAUDIT_REPORT_SHA256=
ca025aae4896a629f5d9acd2904622b8282036228ff905b856feb41647afb0f9

V5_REAUDIT_REPORT_SHA256=
26baac2bd57055543a00abe8d37078ae14ce39c8a231e0134ca006922be6e98c

DESIGN_SPEC_SHA256=
d7e3cb3de474776f591fee576103db5d80db0f53fc85dd6c3293cd58c2b72f40
```

Historical V1–V5 bundles available to the independent audit retain their previously declared hashes.

Result:

```text
BUNDLE_INTEGRITY=PASS
EXACT_HEAD=PASS
EXACT_TREE=PASS
HISTORICAL_AUDIT_EVIDENCE_PRESERVED=PASS
```

---

# 2. V5 remediation scope review

The V5 → V6 tracked delta is narrow and auditable.

Production changes are limited to:

```text
cmm/events/event_payload_safety.py
cmm/agent_runtime/runtime_event_bus.py
```

The remaining changes are tests and current implementation/reference/roadmap evidence.

No second:

- event bus;
- registry;
- repository protocol;
- replay engine;
- DLQ authority;
- safety subsystem;
- container;
- broker abstraction

was introduced.

No reverse `cmm.agent_runtime -> cmm.domains` dependency was found.

Result:

```text
ARCHITECTURE_DIRECTION=PASS
REMEDIATION_SCOPE_CONTROL=PASS
AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
```

---

# 3. Independent executable verification

The audit environment does not contain every repository development dependency.

Unavailable:

```text
libcst
ruff
```

and network package installation is unavailable.

Therefore the complete repository suite and exact Ruff command could not be rerun unchanged.

This limitation does **not** cause the FAIL verdict. The V6 findings below were reproduced directly against the audited production modules.

Independent execution against exact V6 bytes:

```text
V5_REMEDIATION_REGRESSIONS=71 passed
V1_TO_V5_REMEDIATION_REGRESSIONS=350 passed
PHASE9_RUNTIME_EVENT_BUS=222 passed
FOCUSED_PHASE11_22_EVENT_TESTS=498 passed
DURABLE_REPOSITORY_FOCUSED=27 passed
COMPILEALL=PASS
```

A broader `tests/events/` run reached:

```text
961 passed
6 audit-environment-only failures
```

The six failures were attributable to the independent audit import shim or root-filesystem permission semantics, not reproduced product defects.

The committed V6 implementation evidence reports:

```text
PHASE_SUITE=1091 passed
AT-DP-122=124 passed
PHASE9_EVENT_REGRESSIONS=3635 passed
DOMAIN_SUITE=11824 passed
EVENT_INVENTORY=1270 passed
GLOBAL_PYTEST=23160 passed, 1 warning, 0 failed
GLOBAL_RUFF_COUNT=810
```

---

# 4. V5 concrete findings are fixed — 3/3

## V5-001 — `array.array` binary-buffer bypass

The exact V5 reproduction now fails closed.

`array.array` is recognized through the semantic buffer classifier before generic sequence handling.

Result:

```text
V5_001_ARRAY_BUFFER_REPRODUCTION=PASS
```

## V5-002 — raw prose under lifecycle keys

The exact V5 raw-user-text reproduction now fails closed for the tested identifier/category/metadata paths.

The new semantic key/value classes reject the prior raw sentence before persistence.

Result:

```text
V5_002_RAW_CONTENT_RELOCATION_REPRODUCTION=PASS
```

## V5-003 — direct bus without external categorizer

The canonical direct bus + canonical DLQ path now defaults to:

```text
SubscriberDeliveryError
```

when no external categorizer is bound.

The prior credential-shaped exception class no longer enters DLQ data.

Result:

```text
V5_003_DIRECT_BUS_DLQ_REPRODUCTION=PASS
```

Therefore:

```text
V5_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED
```

---

# 5. MAJOR-V6-001 — numeric lifecycle facts are not actually bounded, and repository parity breaks

## Affected authority

Primary area:

```text
cmm/events/event_payload_safety.py
```

The V5 remediation introduced semantic key/value classes and a helper named conceptually as bounded-number validation.

But the actual number policy only checks:

```text
value is int or float
bool is excluded
float is finite
```

It does not enforce an upper bound and does not enforce the lifecycle semantics of non-negative counts/durations/attempts/sequences.

## Independent reproduction — huge integer

Using the official in-memory repository:

```python
count = 10 ** 5000
```

through the public Phase 11.22 path:

```text
PUBLISH=ACCEPTED
REPOSITORY_COUNT=1
STORED_EVENT=YES
```

Using the official file-backed repository with the same lifecycle fact:

```text
ValueError:
Exceeds the limit (4300 digits) for integer string conversion
```

and:

```text
REPOSITORY_COUNT=0
DURABLE_APPEND=NO
```

So the same public event:

```text
succeeds with the official in-memory repository
fails with the official file-backed repository
```

because Phase 11.22 has not bounded the numeric value before it reaches repository serialization.

## Additional accepted values

Independent V6 checks also accepted values such as:

```text
count=-1
duration_ms=-5
attempts=-1
sequence=-1
duration_ms=1e308
```

where the lifecycle semantic name itself implies a bounded count, duration, attempt count or sequence.

## Why this is major

The frozen design explicitly allows:

```text
bounded counts
safe durations
```

not arbitrary finite Python numbers.

The current implementation calls the semantic class bounded while leaving it effectively unbounded.

The huge-integer case also creates observable behavioral divergence between the two official repository implementations.

This violates:

- lifecycle-fact boundedness;
- public boundary determinism;
- official repository parity;
- fail-before-persistence behavior.

## Required Remediation V6

Extend the existing semantic number authority.

Do not create a second number-policy registry.

Define explicit bounded numeric semantics sufficient for current fields.

At minimum:

```text
count / attempt / attempts / sequence
→ integer
→ non-negative where required
→ explicit finite upper bound

duration_ms / retry_after_ms
→ finite numeric
→ non-negative
→ explicit upper bound appropriate to the current contract
```

Where a field legitimately supports signed values, document and test that exception.

Required permanent regressions:

```text
huge integer rejected before repository interaction
same huge integer behaves identically with in-memory and file-backed repositories
negative count rejected
negative duration rejected
negative attempt/sequence rejected where contractually non-negative
oversized finite float rejected
legitimate small values remain green
```

Do not rely on the JSON serializer or interpreter integer-string limit as a safety boundary.

---

# 6. MAJOR-V6-002 — filesystem secret paths can enter persisted identifier fields

## Frozen design requirement

The Phase 11.22 design explicitly rejects or redacts:

```text
filesystem secrets/paths where not public-safe
```

## Affected authority

Primary area:

```text
cmm/events/event_payload_safety.py
```

The identifier policy currently permits a bounded token shape that includes characters such as:

```text
:
/
.
```

That is necessary for some legitimate references, but there is no semantic path-safety check.

As a result, non-public local filesystem paths can qualify as identifiers.

## Independent durable reproductions

The following payload identifier was accepted and persisted:

```text
request_id=file:///Users/alice/.ssh/id_rsa
```

A Windows-style secret path was also accepted and persisted:

```text
request_id=C:/Users/alice/.ssh/id_rsa
```

A canonical header identifier also accepted path-like content:

```text
producer=Users/alice/.ssh/id_rsa
```

The exact path string appears in durable event JSON.

Result:

```text
FILESYSTEM_SECRET_PATH_ACCEPTED=True
FILESYSTEM_SECRET_PATH_PERSISTED=True
```

## Why this is major

This is a direct violation of a frozen privacy rule.

The problem is not merely that slash is allowed.

The problem is that the canonical identifier authority cannot currently distinguish:

```text
safe public reference
```

from:

```text
local secret filesystem location
```

and therefore persists a class of data the design explicitly prohibits.

## Required Remediation V6

Extend the existing identifier/header safety authority with a narrow path-like/private-filesystem detector.

Do not add a new safety subsystem.

Preserve legitimate current identifiers such as:

```text
workflow:123
domain:legal
provider/model-style safe references
```

after a real inventory.

Required regression cases should cover at minimum:

```text
file:///Users/alice/.ssh/id_rsa -> reject
/Users/alice/.ssh/id_rsa -> reject
Users/alice/.ssh/id_rsa where path semantics are clear -> reject
C:/Users/alice/.ssh/id_rsa -> reject
/home/alice/.ssh/id_rsa -> reject
```

and the same class in canonical header identifiers such as `producer`.

Do not overcorrect by banning every slash or colon unless the actual producer inventory proves that safe.

The invariant is:

```text
NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE
```

---

# 7. MAJOR-V6-003 — payload can shadow canonical header identity and sensitivity facts

## Frozen design requirement

Phase 11.22 defines canonical event identity/correlation/sensitivity facts in the event header.

The design also states that when an equivalent canonical field already exists:

```text
do not add a duplicate field with equivalent semantics
```

and requires source sensitivity/privacy to be preserved.

## Problem

The current `PAYLOAD_KEY_CLASSES` still permits payload keys equivalent to canonical header facts, including examples such as:

```text
event_id
correlation_id
causation_id
producer
sensitivity
event_type
schema_version
occurred_at
```

Those payload values are independently validated but are not required to equal the canonical header value.

This allows two conflicting versions of the same event fact to coexist and be persisted.

## Independent durable reproduction

A public event was accepted with canonical header facts:

```text
header.event_id=header-event
header.correlation_id=header-corr
header.causation_id=header-cause
header.producer=header-producer
header.sensitivity=internal
```

and conflicting payload facts:

```text
payload.event_id=payload-event
payload.correlation_id=payload-corr
payload.causation_id=payload-cause
payload.producer=payload-producer
payload.sensitivity=restricted
```

Both representations were durably persisted.

Especially important:

```text
HEADER_SENSITIVITY=internal
PAYLOAD_SENSITIVITY=restricted
```

The canonical header remains the lower classification while a stricter value exists only inside payload.

Result:

```text
HEADER_PAYLOAD_IDENTITY_CONFLICT_ACCEPTED=True
HEADER_PAYLOAD_SENSITIVITY_CONFLICT_ACCEPTED=True
CONFLICTING_FACTS_PERSISTED=True
```

## Why this is major

This breaks the “one canonical fact” rule at the heart of DP-122.

It creates ambiguity about:

- event identity;
- correlation lineage;
- causation;
- producer authority;
- sensitivity/classification.

The sensitivity case is closure-critical because downstream systems are expected to trust the canonical header classification.

A payload copy cannot be allowed to silently carry a stricter classification while the authoritative header remains lower.

## Required Remediation V6

Inventory every payload key whose semantics duplicate a canonical header field.

Then choose one canonical representation.

Preferred design:

```text
canonical header remains authoritative
equivalent payload/header duplicates are not persisted
```

If a source adapter needs to consume such a source fact before event construction, treat it as source input that is translated into the canonical header rather than retained as a second platform payload fact.

Alternative equality-only support is acceptable only where the frozen design/current compatibility requires it, but conflicting values must fail closed.

At minimum cover:

```text
event_id
correlation_id
causation_id
producer
sensitivity
event_type
schema_version
occurred_at
```

and any other payload field semantically equivalent to an existing canonical header fact.

Required tests:

```text
payload event_id conflicting with header -> reject or remove canonical duplicate before persistence
payload correlation_id conflicting -> reject
payload causation_id conflicting -> reject
payload producer conflicting -> reject
payload sensitivity stricter than header -> cannot persist as conflicting fact
payload sensitivity lower than header -> cannot downgrade
canonical source sensitivity still maps to header correctly
Kernel/Domain bridge sensitivity preservation remains green
```

Do not reintroduce a second identity or classification authority.

---

# 8. MINOR-V6-001 — canonical timestamp validation accepts invalid or ambiguous timestamps

## Affected authority

Primary area:

```text
cmm/events/event_payload_safety.py
```

The timestamp validation is described as canonical ISO-8601 validation, but currently validates textual shape rather than calendar/time validity.

## Independent durable reproductions

The following values were accepted and persisted:

```text
9999-99-99T99:99Z
2026-02-31T12:00Z
2026-09-27T25:61Z
2026-09-27T12:00
```

The first three are not valid civil timestamps.

The last is timezone-ambiguous despite the canonical persisted event contract otherwise preserving timezone-aware chronology.

## Why this is minor

This does not independently demonstrate a secret leak or repository corruption, but it contradicts the semantic contract claimed by the timestamp class and permits invalid lifecycle facts into durable evidence.

## Required Remediation V6

Validate actual timestamp semantics, not only regex shape.

Use the existing datetime/canonical serialization approach where possible.

Define explicitly whether a timezone is mandatory.

Prefer requiring timezone-aware canonical values for persisted platform facts.

Required regressions:

```text
impossible month/day rejected
impossible hour/minute rejected
timezone-ambiguous timestamp rejected if timezone is required
valid canonical UTC timestamp passes
valid canonical offset timestamp passes if supported
```

Do not add a parallel timestamp subsystem.

---

# 9. Security and privacy assessment

Positive V6 results:

```text
bytes/bytearray/memoryview/array.array binary rejection = PASS
raw prose relocation reproduction from V5 = PASS
credential/private marker scanning = PASS
direct bus DLQ neutral fallback = PASS
composed EventSystem DLQ categorization = PASS
raw exception message exclusion = PASS
```

Fresh failures:

```text
bounded numeric lifecycle semantics = FAIL
non-public filesystem path exclusion = FAIL
one canonical header identity/classification authority = FAIL
canonical timestamp semantics = FAIL (minor)
```

Current result:

```text
FULL_CANONICAL_EVENT_SECURITY=FAIL
LIFECYCLE_FACT_ONLY_POLICY=FAIL
CANONICAL_HEADER_AUTHORITY=FAIL
```

---

# 10. Persistence/canonicalization assessment

Positive:

```text
structured payload canonicalization = PASS
supported nested sequence/mapping shape = PASS
caller alias isolation = PASS
subscriber isolation = PASS
repository snapshot isolation = PASS
manual sensitivity normalization = PASS
unsupported schema rejection = PASS
content-bound fingerprint = PASS
```

Fresh defects:

```text
NUMERIC_REPOSITORY_PARITY=FAIL
NON_PUBLIC_PATH_PERSISTENCE_POLICY=FAIL
HEADER_PAYLOAD_SEMANTIC_UNIQUENESS=FAIL
```

The durable store is faithfully writing facts that the public safety/canonicalization boundary should have rejected or normalized earlier.

---

# 11. Replay and DLQ assessment

The exact V5 direct-bus DLQ defect is fixed.

The canonical bus now fails safe to a neutral error category when no categorizer is bound.

Prior targeted replay and detached-snapshot behavior remained green in the focused regression runs.

No new replay/DLQ authority was found.

Result:

```text
V5_DLQ_FAIL_SAFE_FIX=VERIFIED
REPLAY_AUTHORITY=PASS
DLQ_AUTHORITY=PASS
```

---

# 12. DP-122 assessment

DP-122 requires one canonical event path that is:

- durable;
- deterministic;
- privacy preserving;
- content-bound;
- semantically bounded;
- authoritative about identity/correlation/sensitivity;
- consistent across official repository implementations.

V6 closes the V5 findings.

But independent V6 execution proves that:

1. numeric lifecycle facts called “bounded” are not actually bounded and can diverge across official repositories;
2. non-public filesystem secret paths can still enter persisted identifier/header fields;
3. payload can persist conflicting copies of canonical header identity/correlation/sensitivity facts.

Therefore:

```text
DP-122=NOT_VERIFIED
```

---

# 13. AT-DP-122 assessment

The committed V6 evidence reports:

```text
AT-DP-122=124 passed
```

and the V5 scenarios are now represented.

However the connected acceptance does not prove:

```text
huge numeric lifecycle facts fail before persistence
in-memory/file-backed repository parity for huge numbers
negative count/duration/attempt/sequence constraints
non-public filesystem path rejection
payload/header identity conflict rejection
payload/header sensitivity conflict rejection
actual calendar-valid timestamp semantics
```

Because independently observed behavior contradicts frozen DP-122 requirements:

```text
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
```

This does not claim that the 124 committed tests themselves fail.

It means the acceptance remains incomplete relative to the frozen design point.

---

# 14. Required Remediation V6 scope

Remediation V6 must fix **only**:

```text
MAJOR-V6-001
MAJOR-V6-002
MAJOR-V6-003
MINOR-V6-001
```

Preserve every V1–V5 fix.

Do not redesign Phase 11.22.

Do not begin Phase 11.23 or 11.24.

---

# 15. Required new regressions

At minimum:

```text
huge integer lifecycle value rejected before persistence
huge integer behaves identically across official repositories
negative count rejected
negative duration rejected
negative attempts/sequence rejected where non-negative
oversized finite float rejected

macOS/Linux/Windows/file:// secret-path-shaped identifiers rejected
same path class rejected in canonical header identifiers

payload/header event_id conflict rejected or canonicalized to one authority
payload/header correlation_id conflict rejected
payload/header causation_id conflict rejected
payload/header producer conflict rejected
payload/header sensitivity conflict rejected
source sensitivity still reaches canonical header correctly

impossible ISO month/day/hour/minute rejected
timezone ambiguity rejected if canonical contract requires timezone
valid canonical timestamps remain accepted
```

Retain every V1–V5 remediation regression.

---

# 16. Required gates after Remediation V6

Before another independent audit:

1. new V6 regressions;
2. all V1 remediation regressions;
3. all V2 remediation regressions;
4. all V3 remediation regressions;
5. all V4 remediation regressions;
6. all V5 remediation regressions;
7. full `tests/events/`;
8. strengthened `AT-DP-122`;
9. Phase 9 runtime-event suite;
10. Phase 10.33 Domain Event suite/acceptance;
11. Orchestration/Validation/Workflow connected regressions;
12. `AT-DP-102`;
13. `AT-DP-103`;
14. `AT-DP-105`;
15. Phase 11.21;
16. Phase 11.34 where relevant;
17. `AT-DP-150`;
18. complete event inventory;
19. global pytest;
20. changed-file Ruff;
21. global Ruff no-new-debt relative to `810`;
22. format;
23. compileall;
24. `git diff --check`;
25. architecture anti-fragmentation gates;
26. event-security gates;
27. tracked clean state.

No unrelated cleanup.

---

# 17. Historical artifacts remain immutable

Do not modify or overwrite:

```text
phase-11.22-event-system-audit-v1.tar.gz
phase-11.22-event-system-audit-v2.tar.gz
phase-11.22-event-system-audit-v3.tar.gz
phase-11.22-event-system-audit-v4.tar.gz
phase-11.22-event-system-audit-v5.tar.gz
phase-11.22-event-system-audit-v6.tar.gz

docs/audits/phase-11.22-event-system-independent-audit-v1.md
docs/audits/phase-11.22-event-system-independent-reaudit-v2.md
docs/audits/phase-11.22-event-system-independent-reaudit-v3.md
docs/audits/phase-11.22-event-system-independent-reaudit-v4.md
docs/audits/phase-11.22-event-system-independent-reaudit-v5.md
```

Historical bundle hashes:

```text
V1=a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3
V2=172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04
V3=27517348570837df2abe9fc7f11e5cc24cefc32a198ffe3e0afefaee5df3c589
V4=18adf70d86f291b5585f71b746f81139ffa01e56e7c16dcbfc6b67bb794aaa0f
V5=105203eb4ea1d0e1b3200ee30b7130961af70283d8be9fc7b28ed65279003d10
V6=67b27f6effa5297757453aba3021a7211fe4ee88e194a6d65eefa353060f1008
```

This V6 audit report becomes immutable historical evidence once committed.

---

# 18. Next bundle

After Remediation V6 create:

```text
phase-11.22-event-system-audit-v7.tar.gz
```

from the exact committed remediation HEAD via `git archive`.

Report:

```text
HEAD
TREE
SHA-256
TRACKED_WORKTREE=CLEAN
```

Do not overwrite V6.

---

# 19. Final V6 audit markers

```text
PHASE=11.22
INDEPENDENT_REAUDIT_V6=FAIL

AUDIT_HEAD=2b45244a0f1b73a46e4cf2b93db40b3fcf88b552
AUDIT_TREE=f28f95ed7ae2a4a2e37de03a618688bbdf343b3b
AUDIT_BUNDLE=phase-11.22-event-system-audit-v6.tar.gz
AUDIT_BUNDLE_SHA256=67b27f6effa5297757453aba3021a7211fe4ee88e194a6d65eefa353060f1008

BUNDLE_INTEGRITY=PASS
EXACT_HEAD=PASS
EXACT_TREE=PASS
ARCHITECTURE_DIRECTION=PASS

V5_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED
PRIOR_REMEDIATION_REGRESSIONS=350_PASS

BLOCKERS=0
MAJORS=3
MINORS=1

MAJOR_V6_001=NUMERIC_LIFECYCLE_FACTS_ARE_NOT_ACTUALLY_BOUNDED_AND_REPOSITORY_PARITY_BREAKS
MAJOR_V6_002=FILESYSTEM_SECRET_PATHS_CAN_ENTER_PERSISTED_IDENTIFIER_FIELDS
MAJOR_V6_003=PAYLOAD_CAN_SHADOW_CANONICAL_HEADER_IDENTITY_AND_SENSITIVITY_FACTS
MINOR_V6_001=CANONICAL_TIMESTAMP_VALIDATION_ACCEPTS_INVALID_OR_AMBIGUOUS_TIMESTAMPS

DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO

NEXT_STEP=REMEDIATION_V6_ONLY
```
