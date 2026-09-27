# Phase 11.22 — Event System — Independent Re-audit V3

**Project:** CMM OS
**Phase:** 11.22 — Event System
**Audit:** Independent ChatGPT Re-audit V3
**Audited branch:** `feature/phase-11-stable-integrated-platform`
**Audited HEAD:** `7b582312319beae9b5d0e19dc25a726ee9d65360`
**Audited tree:** `0e4938f990a764fd06591a9423da28448c47ffc0`
**Bundle:** `phase-11.22-event-system-audit-v3.tar.gz`
**Bundle SHA-256:** `27517348570837df2abe9fc7f11e5cc24cefc32a198ffe3e0afefaee5df3c589`
**Design Point:** `DP-122`
**Connected acceptance:** `AT-DP-122`
**Previous independent reports:**
- Audit V1: `docs/audits/phase-11.22-event-system-independent-audit-v1.md`
- Re-audit V2: `docs/audits/phase-11.22-event-system-independent-reaudit-v2.md`

## Verdict

```text
INDEPENDENT_REAUDIT_V3=FAIL

AUDIT_V1_FINDINGS_REMEDIATED=9/9_VERIFIED
REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_VERIFIED

BLOCKERS=0
MAJORS=2
MINORS=1

MAJOR_V3_001=FULL_PERSISTED_EVENT_SAFETY_AND_HEADER_TYPE_VALIDATION_INCOMPLETE
MAJOR_V3_002=STRUCTURED_PAYLOAD_CANONICALIZATION_AND_ROUNDTRIP_UNSTABLE
MINOR_V3_001=DLQ_SNAPSHOT_MUTABLE

DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO

NEXT_STEP=REMEDIATION_V3_ONLY
```

Phase 11.22 remains open.

Phase 11.23 must not begin.

---

# 1. Audit basis

This re-audit was performed against the uploaded exact-HEAD V3 archive rather than the remediation-agent summary.

The audit had four objectives:

1. verify the V3 bundle is exactly the declared committed remediation tree;
2. verify all nine Audit V1 fixes remain intact;
3. verify the four concrete Re-audit V2 reproductions are corrected;
4. perform a fresh adversarial review of the resulting Phase 11.22 behavior rather than stopping at the known regressions.

Authoritative frozen design inputs include:

- `docs/superpowers/specs/2026-09-26-phase-11.22-event-system-design.md`
- `docs/superpowers/plans/2026-09-26-phase-11.22-event-system-implementation-plan.md`
- `docs/superpowers/prompts/2026-09-26-phase-11.22-event-system-implementation-agent-prompt.md`
- `docs/superpowers/prompts/2026-09-26-phase-11.22-remediation-v1-agent-prompt.md`
- `docs/superpowers/prompts/2026-09-26-phase-11.22-remediation-v2-agent-prompt.md`

Historical audit evidence is treated as immutable.

---

# 2. Exact bundle provenance

Independent verification of the uploaded V3 archive produced:

```text
AUDIT_V3_SHA256=
27517348570837df2abe9fc7f11e5cc24cefc32a198ffe3e0afefaee5df3c589

GZIP_INTEGRITY=PASS
ARCHIVE_ENTRY_COUNT=2672

PAX_COMMIT=
7b582312319beae9b5d0e19dc25a726ee9d65360

RECONSTRUCTED_TREE=
0e4938f990a764fd06591a9423da28448c47ffc0

RECONSTRUCTED_TRACKED_FILE_COUNT=2542
```

The Git tree was reconstructed independently by extracting the archive, creating a temporary Git index, force-adding every archived tracked path so `.gitignore` could not hide anything, and executing `git write-tree`.

The reconstructed tree exactly equals the declared remediation tree.

Historical evidence inside the V3 tree also remains unchanged:

```text
V1_INDEPENDENT_AUDIT_REPORT_SHA256=
3d259b8ee9dd56d00da35d19d53670d625b399c35bff70e3ccd76e681beb1cb1

V2_INDEPENDENT_REAUDIT_REPORT_SHA256=
20357eb6da9890900c8e8dc86c104d8b0559e8504c18afb67846147f51e5b771

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

---

# 3. Architecture review

The V3 remediation preserves the architecture previously accepted by the independent audits.

No second production event bus, mutable registry, event-repository protocol, replay engine or dead-letter authority was introduced.

No external broker abstraction, second application container, service locator or Phase 11.23/11.24 subsystem was found.

The intended dependency direction remains:

```text
existing producer seam
→ cmm.events integration/adaptation
→ canonical Phase 9 Agent Runtime event infrastructure
```

Independent architecture-focused tests were also exercised under an import shim required by the audit container and passed when the repository's package-level exports were supplied without changing the audited production modules.

Result:

```text
ONE_CANONICAL_EVENT_BUS=PASS
ONE_CANONICAL_EVENT_REGISTRY=PASS
ONE_CANONICAL_EVENT_REPOSITORY_CONTRACT=PASS
ONE_CANONICAL_REPLAY_OWNER=PASS
NO_PARALLEL_DLQ_AUTHORITY=PASS
ARCHITECTURE_DIRECTION=PASS
REMEDIATION_SCOPE_CONTROL=PASS
```

No architecture finding is raised in V3.

---

# 4. Audit V1 regressions remain fixed — 9/9

The V1 remediation regressions were independently executed against the exact V3 production bytes:

```text
tests/events/test_phase11_22_remediation_v1_regressions.py
86 passed
```

The previously independently verified fixes remain intact:

```text
V1 MAJOR-001 complete content-bound fingerprint             = PASS
V1 MAJOR-002 publish_event registry/security boundary       = PASS
V1 MAJOR-003 subscriber-targeted DLQ replay                 = PASS
V1 MAJOR-004 explicit correlation/causation preservation    = PASS

V1 MINOR-001 retry_total accounting                         = PASS
V1 MINOR-002 canonical stored-corruption error              = PASS
V1 MINOR-003 forbidden Kernel source fail-closed            = PASS
V1 MINOR-004 reserved-event count                           = PASS
V1 MINOR-005 Phase 9 hardening documentation                = PASS
```

Result:

```text
AUDIT_V1_FINDINGS_REMEDIATED=9/9_VERIFIED
```

---

# 5. Re-audit V2 concrete reproductions are fixed — 4/4

The Remediation V2 regression module was independently executed:

```text
tests/events/test_phase11_22_remediation_v2_regressions.py
126 passed
```

Independent direct reproductions also verified the exact four V2 scenarios.

## V2-001 — header relocation examples

The exact audited examples involving ordinary string-based forbidden facts in:

- `metadata`;
- `permissions`;
- `producer`;
- `aggregate_id`;
- `source`;

are now rejected before persistence.

Status:

```text
V2_001_CONCRETE_REPRODUCTIONS=PASS
```

## V2-002 — unsupported schema durable poisoning

An unsupported platform schema is now rejected before append.

A supported `1.0.0` canonical event saves, closes and reopens correctly.

Status:

```text
V2_002_CONCRETE_REPRODUCTIONS=PASS
```

## V2-003 — subscriber/repository isolation

A subscriber that mutates its delivered detached event no longer changes:

- what a later subscriber sees;
- the repository's live stored snapshot;
- the publication result in the audited subscriber-mutation scenario;
- the file-backed event after reopen.

Status:

```text
V2_003_CONCRETE_REPRODUCTIONS=PASS
```

## V2-004 — real Domain bridge facts and sensitivity

Real connected Domain Event scenarios now preserve the previously lost mapped facts.

Examples independently observed:

```text
domain.execution.completed
→ operation.executed
→ execution_id preserved
→ status preserved
→ restricted sensitivity preserved
→ explicit correlation preserved
→ explicit causation preserved

domain.approval.requested
→ approval.requested
→ approval_id preserved

domain.approval.received
→ approval.resolved
→ approval_id + approved preserved

domain.memory.updated
→ memory.updated
→ status preserved
```

Status:

```text
V2_004_CONCRETE_REPRODUCTIONS=PASS
```

Therefore:

```text
REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_VERIFIED
```

The fresh findings below show that the broader frozen invariants are still not fully satisfied.

---

# 6. Independent execution coverage

The audit container does not contain every repository development dependency, notably `libcst` and `ruff`, and has no network access for installing them.

The complete repository suite and exact Ruff invocation therefore could not be re-executed unchanged.

The committed remediation evidence reports:

```text
REMEDIATION_V2_TESTS=126 passed
PHASE_SUITE=893 passed
AT-DP-122=64 passed
PHASE9_EVENT_REGRESSIONS=3635 passed
DOMAIN_SUITE=11824 passed
EVENT_INVENTORY=1270 passed
GLOBAL_PYTEST=22962 passed, 1 warning, 0 failed
GLOBAL_RUFF_COUNT=810
FORMAT_CHECK=PASS
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
```

Independent executable checks against the exact V3 source included:

```text
V1_REMEDIATION_REGRESSIONS=86 passed
V2_REMEDIATION_REGRESSIONS=126 passed
PHASE9_RUNTIME_EVENT_BUS=222 passed
SELECTED_EVENT_SECURITY_KERNEL_REPLAY_REGRESSIONS=485 passed
ARCHITECTURE_FOCUSED_TESTS=37 passed
COMPILEALL=PASS
```

A wider event-suite attempt under the audit import shim reached hundreds of additional passing tests; the remaining setup failures were attributable to unavailable `libcst`, package-export shimming, or root-user filesystem-permission semantics in the audit container, not to a reproduced production regression.

The FAIL verdict below is independent of those environment limitations: every finding was reproduced directly against the audited production modules.

---

# 7. MAJOR-V3-001 — Full persisted-event safety and header type validation remain incomplete

## Affected code

Primary areas:

- `cmm/events/event_payload_safety.py:366-448`
- `cmm/events/event_payload_safety.py:506-538`
- `cmm/agent_runtime/runtime_event_contracts.py:54-112`
- `cmm/agent_runtime/runtime_event_factory.py:175-245`
- `cmm/events/event_system.py:218-271`
- `cmm/events/event_system.py:475-502`

## What V3 fixed correctly

The V3 code now has one platform event-fact validator for persisted identifiers, `metadata` and `permissions`.

Ordinary string payload relocation such as:

```text
metadata={"prompt": "..."}
permissions=["api_key=..."]
producer="api_key=..."
source="system_prompt=..."
aggregate_id="..."
```

is rejected.

That part of V2-001 is genuinely fixed.

## Remaining safety gap A — persisted metadata accepts opaque/binary/non-finite values

`scan_for_forbidden_event_facts()` delegates to `_scan_forbidden_content()`.

That scanner recursively checks mappings, strings and sequences for forbidden textual content, but for every other value type it ends with:

```python
# Other value types carry no scannable string content here.
return
```

Unlike the actual platform payload validator, it does not reject:

- opaque runtime objects;
- `bytes`;
- `bytearray`;
- `NaN`;
- positive/negative infinity.

### Independent reproduction

Public Phase 11.22 publication accepted:

```text
metadata={"opaque": object()}        → ACCEPTED
metadata={"blob": b"abc"}            → ACCEPTED
metadata={"blob": bytearray(b"abc")} → ACCEPTED
metadata={"metric": NaN}             → ACCEPTED
metadata={"metric": +inf}            → ACCEPTED
```

This directly contradicts the frozen safe-event policy and the V3 reference document, which states that opaque runtime objects, arbitrary binary values and non-finite floats are rejected before persistence.

## Remaining safety gap B — opaque metadata can stringify a credential into durable JSON

The durable repository serializes the event record with:

```python
json.dumps(..., default=str, allow_nan=False)
```

Because an opaque metadata object reaches the repository, its `__str__()` can become persisted evidence.

### Independent reproduction

A custom metadata object whose string representation is:

```text
api_key=abcdef1234567890
```

was published through the public Phase 11.22 API.

Result:

```text
PUBLICATION=ACCEPTED
DURABLE_RECORD_CONTAINS_API_KEY=True
```

The resulting JSONL contained:

```json
"metadata": {
  "opaque": "api_key=abcdef1234567890"
}
```

This is a direct violation of the frozen invariant:

```text
secrets and credentials never enter event persistence
```

## Remaining safety gap C — `sensitivity` is persisted but is not runtime-type validated by the platform event gate

The canonical header annotation says:

```python
sensitivity: EventSensitivity
```

but `AgentRuntimeEventHeader.__post_init__()` does not validate that runtime type.

`validate_platform_event_facts()` validates identifiers, metadata and permissions but not sensitivity.

### Independent reproduction

The official public platform path with the official in-memory repository accepted:

```text
sensitivity="restricted"                  → ACCEPTED as str
sensitivity=123                           → ACCEPTED
sensitivity=None                          → ACCEPTED
sensitivity="api_key=abcdef1234567890"    → ACCEPTED
sensitivity="system_prompt=TOP SECRET"    → ACCEPTED
```

Thus secret/private strings can still enter persisted canonical header content through a field the V3 remediation considered a closed vocabulary but did not actually enforce as one.

On the file-backed path an invalid string sensitivity may fail later through an incidental serialization error, but fail-later is not equivalent to the required canonical pre-persistence safety boundary.

## Remaining type-coercion example — `permissions`

The factory performs:

```python
list(permissions)
```

without first requiring a real permission sequence shape.

Independent reproduction:

```text
permissions="admin"
→ ACCEPTED
→ persisted as ["a", "d", "m", "i", "n"]
```

This does not itself leak a credential in that example, but confirms the persisted-header structural type boundary remains incomplete.

## Impact

The security policy is still channel-dependent in ways the reference documentation claims are impossible.

The following cannot be independently verified:

```text
PROMPTS_NEVER_ENTER_ANY_PERSISTED_EVENT_FIELD
HIDDEN_REASONING_NEVER_ENTERS_ANY_PERSISTED_EVENT_FIELD
CREDENTIALS_NEVER_ENTER_ANY_PERSISTED_EVENT_FIELD
OPAQUE_VALUES_NEVER_ENTER_PERSISTED_EVENT_CONTENT
FULL_CANONICAL_EVENT_SECURITY=PASS
```

This is a closure-critical major finding.

## Required Remediation V3

Use the existing Phase 11.22 safety authority; do not add another policy module.

The persisted-event fact gate must validate both **content and structural value type**.

At minimum:

1. recursively validate `metadata` with the same descriptive JSON-safe value rules used by platform payloads;
2. reject bytes/bytearray, opaque runtime objects and non-finite numbers before persistence;
3. validate `sensitivity` as the canonical `EventSensitivity` type or perform one explicit safe normalization before event construction;
4. validate `permissions` structural type before factory coercion so a plain string cannot become a character list;
5. inspect every persisted header fact for equivalent unchecked runtime-type coercion;
6. retain all V1 and V2 string/credential/private-marker regressions.

Required adversarial regression:

```python
class SecretObject:
    def __str__(self):
        return "api_key=abcdef1234567890"
```

Putting that object in metadata must fail **before** a durable record is written.

---

# 8. MAJOR-V3-002 — Structured payload canonicalization and durable round-trip remain unstable

## Affected code

Primary areas:

- `cmm/events/event_payload_safety.py:540-572`
- `cmm/events/event_system.py:309-325`
- `cmm/agent_runtime/runtime_event_factory.py:337-385`
- `cmm/agent_runtime/runtime_event_contracts.py:132-205`
- durable repository serialization/deserialization path

## Problem A — valid safe nested mappings crash public `publish()`

`freeze_platform_payload()` recursively converts nested mappings to `MappingProxyType` and sequences to tuples.

`EventSystem.publish()` then calls:

```python
dict(safe_payload)
```

which converts only the top-level proxy back to a dictionary.

Nested proxies remain `MappingProxyType`.

The canonical factory subsequently calls `copy.deepcopy(payload)`, which cannot deepcopy a `MappingProxyType`.

### Independent reproduction

Both of these payloads are within the existing bounded vocabulary:

```python
{
    "result_reference": {
        "reference_id": "ref-1"
    }
}
```

and:

```python
{
    "approval_refs": [
        {"approval_id": "app-1"}
    ]
}
```

Both failed on the public Phase 11.22 `publish()` path with:

```text
TypeError: cannot pickle 'mappingproxy' object
```

This is not an invalid-payload rejection; it is an implementation crash after the safety policy has accepted the structure.

The module already contains `thaw_platform_payload()` but the public publication path does not use it.

## Problem B — allowed sequence shape changes after durable restart

The freeze path converts safe sequences to tuples.

JSON persistence necessarily emits arrays, and canonical deserialization reconstructs them as lists.

### Independent reproduction

Live publication:

```text
supporting_domains type = tuple
```

After reopening the exact durable repository:

```text
supporting_domains type = list
```

Result:

```text
live_event == reopened_event     → False
live_payload == reopened_payload → False
```

## Real connected orchestration reproduction

Using the real production `PlatformOrchestrationEventSink` with:

```text
orchestration.domain_resolved
supporting_domains=("domain:legal", "domain:health")
```

produced:

```text
live supporting_domains    = tuple
reopened supporting_domains = list
event_equal                 = False
payload_equal               = False
```

This contradicts the V3 reference invariant:

```text
FILE_LIVE_AND_REOPENED_FACTS_MATCH
```

and the documentation claim that detached snapshots preserve expected JSON-compatible container shapes.

## Problem C — manually supplied nested containers can still alias the publication result

`AgentRuntimeEventNormalizer.normalize()` copies `metadata` and `payload.data` only with shallow `dict(...)`.

A manually constructed `AgentRuntimeEvent` passed to public `publish_event()` can therefore retain aliases to nested caller-owned containers in the `PublicationResult.event`.

### Independent reproduction

A manually constructed event contained:

```python
payload.data = {
    "supporting_domains": ["domain:a"],
    "status": "selected",
}
```

After successful `publish_event()`, the caller mutated its original list:

```python
original_list.append("domain:b")
```

Result:

```text
PublicationResult.event.payload.data["supporting_domains"]
→ ["domain:a", "domain:b"]

repository stored event
→ ["domain:a"]
```

The repository evidence is protected by detached snapshots, but the public canonical result object is not stable against mutation through an alias held by the caller.

This is narrower than the V2 subscriber-isolation defect, which is correctly fixed, but it is the same canonicalization/immutability boundary.

## Impact

Phase 11.22 claims one deterministic canonical event shape that can be:

```text
validated
→ persisted
→ delivered
→ reopened
→ replayed
```

The current path does not satisfy that for supported structured payloads.

A supported nested mapping crashes, and a supported sequence changes observable canonical type after restart.

This is a closure-critical major finding because durability/replay are central DP-122 requirements, not merely API aesthetics.

## Required Remediation V3

Define one canonical JSON-compatible event-payload normalization for the Phase 11.22 boundary.

The same semantic fact must have one stable persisted/live shape.

Requirements:

1. safe nested mappings publish successfully;
2. safe nested arrays/sequences use a canonical JSON-compatible representation;
3. `publish()` must recursively normalize/thaw before the factory receives the payload;
4. normalizer/detached-copy behavior must prevent nested caller aliases from mutating the publication result;
5. live file-backed event facts must be semantically and structurally equal after reopen;
6. real orchestration `supporting_domains` must satisfy the same round-trip invariant;
7. fingerprint semantics must remain deterministic and stable;
8. do not introduce a second event contract.

A reasonable implementation is to canonicalize mappings to plain dictionaries, JSON-array-like sequences to lists and scalars to the already-approved finite descriptive scalar types before constructing the canonical event.

---

# 9. MINOR-V3-001 — DLQ APIs return mutable aliases while documenting snapshots

## Affected code

- `cmm/agent_runtime/runtime_event_dead_letter.py:24-53`
- `cmm/agent_runtime/runtime_event_contracts.py:303-317`
- `cmm/events/event_system.py:377-380`

The V2 remediation correctly stores a detached event in the dead-letter record.

However `InMemoryAgentRuntimeDeadLetterQueue.get()` returns the live stored dead-letter object, and `list()` copies only the outer list.

The dead-letter dataclass is frozen at the top level but still contains mutable nested event containers and mutable metadata.

`EventSystem.list_dead_letters()` documents that it returns:

```text
a snapshot of canonical dead-letter entries
```

but currently exposes those live nested containers.

### Independent reproduction

After obtaining a dead letter from `list_dead_letters()`, the caller mutated:

```text
entry.event.payload.data
entry.event.header.metadata
entry.metadata
```

A subsequent call to `list_dead_letters()` returned the mutated values.

Result:

```text
DLQ_SNAPSHOT_IS_DETACHED=False
```

Targeted replay still resolves the canonical repository event when it exists, so this did not reproduce an authority or wrong-subscriber bypass.

The impact is integrity of the in-memory dead-letter evidence/inspection surface.

## Required Remediation V3

Return/store detached dead-letter snapshots consistently.

At minimum ensure external `get()`, `list()`, `replay()` and removal/inspection paths do not let a caller mutate another later observation of the queue's retained evidence.

Reuse `detached_event_copy()` or an equivalent helper on the existing canonical contract.

Do not create another DLQ implementation.

---

# 10. Security assessment

Positive V3 results:

- unknown event types fail through the canonical registry;
- ordinary string-based prompt/credential relocation into the V2-audited header channels is blocked;
- raw platform payload is prohibited;
- supported-schema durability is checked before append;
- Domain adapter nested forbidden content remains fail-closed in the tested path;
- correlation/causation and source sensitivity in the V2 real-Domain scenarios are preserved.

But MAJOR-V3-001 proves the universal persisted-event safety claim remains false.

Current status:

```text
PAYLOAD_DATA_SECURITY=PASS
ORDINARY_STRING_HEADER_RELOCATION_SECURITY=PASS
OPAQUE_METADATA_SECURITY=FAIL
CANONICAL_SENSITIVITY_TYPE_SECURITY=FAIL
FULL_PERSISTED_EVENT_SECURITY=FAIL
```

---

# 11. Persistence and integrity assessment

Positive:

```text
CONTENT_BOUND_FINGERPRINT=PASS
SAME_ID_DIFFERENT_CONTENT_FAIL_CLOSED=PASS
TAMPER_DETECTION=PASS
UNSUPPORTED_SCHEMA_REJECTED_BEFORE_APPEND=PASS
SUPPORTED_SCHEMA_REOPEN=PASS
SUBSCRIBER_MUTATION_ISOLATION=PASS
REPOSITORY_DETACHED_SNAPSHOTS=PASS
```

But structured payload canonicalization is not stable:

```text
SAFE_NESTED_MAPPING_PUBLICATION=FAIL
FILE_LIVE_AND_REOPENED_FACTS_MATCH=FAIL
PUBLICATION_RESULT_NESTED_ALIAS_ISOLATION=FAIL
```

Therefore the durable event path still does not meet DP-122 in full.

---

# 12. Replay and DLQ assessment

The V1 targeted-replay fix remains good.

Independent checks and regression coverage support:

```text
REPLAY_DOES_NOT_REPERSIST=PASS
REPLAY_DEFAULT_DENY=PASS
TARGETED_DLQ_REPLAY=PASS
UNRELATED_SUBSCRIBER_CANNOT_RESOLVE_DLQ=PASS
DLQ_ENTRY_REMAINS_UNTIL_TARGET_SUCCESS=PASS
```

The only V3 DLQ finding concerns mutable inspection aliases, classified as MINOR-V3-001.

---

# 13. Domain bridge assessment

The V2 Domain bridge remediation is accepted for the concrete mapped facts and sensitivity scenarios.

The fresh V3 review did not reproduce the previous fact-loss or sensitivity-downgrade defect.

Current status:

```text
DOMAIN_EXECUTION_FACT_FIDELITY=PASS
DOMAIN_APPROVAL_FACT_FIDELITY=PASS
DOMAIN_MEMORY_FACT_FIDELITY=PASS
EXPLICIT_CORRELATION_PRESERVED=PASS
EXPLICIT_CAUSATION_PRESERVED=PASS
SOURCE_SENSITIVITY_NON_DOWNGRADE=PASS
```

No new Domain bridge finding is raised.

---

# 14. DP-122 assessment

DP-122 is stronger than the passing known regressions.

It requires a canonical event path that is:

- content-bound;
- durable;
- safely persisted;
- deterministic;
- replayable;
- failure-aware;
- privacy preserving;
- stable enough that persisted/reopened evidence represents the same canonical facts.

V3 has repaired substantial parts of that design.

However the independent re-audit proves:

1. forbidden/private content can still reach durable event storage through an opaque metadata object, and sensitivity is not a runtime-enforced closed classification;
2. valid structured platform payloads do not have one stable canonical live/persisted/reopened representation.

Therefore:

```text
DP-122=NOT_VERIFIED
```

---

# 15. AT-DP-122 assessment

The implementation evidence reports:

```text
AT-DP-122=64 passed
```

and those tests now cover the known V1/V2 scenarios.

But the connected acceptance still does not demonstrate the newly reproduced V3 invariants:

- opaque/binary/non-finite persisted header rejection;
- sensitivity runtime-type enforcement;
- no string-to-character-list permissions coercion;
- nested safe mapping publication;
- stable sequence representation across durable reopen;
- nested caller-alias isolation in `publish_event()`;
- detached DLQ inspection snapshots.

Because independent observed behavior contradicts closure-critical DP-122 invariants:

```text
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
```

This does not mean the 64 committed tests themselves fail.

It means the current acceptance remains incomplete relative to the frozen design point.

---

# 16. Documentation assessment

The V3 implementation documentation correctly leaves the phase in:

```text
REMEDIATED_AFTER_REAUDIT_V2_PENDING_INDEPENDENT_REAUDIT
```

and does not prematurely claim independent PASS or closure.

Historical Audit V1 and Re-audit V2 reports are preserved unchanged.

However the current reference documentation overstates two implementation guarantees:

1. universal, channel-independent persisted-event safety;
2. `FILE_LIVE_AND_REOPENED_FACTS_MATCH` for structured payloads.

Those claims must be corrected by implementation and then re-evidenced; historical reports must not be rewritten.

---

# 17. Required Remediation V3 scope

Remediation V3 must fix **only** the two V3 majors and one V3 minor.

## MAJOR-V3-001

Complete the existing platform event-fact safety/type boundary:

- reject opaque metadata objects;
- reject bytes/bytearray in persisted metadata;
- reject non-finite persisted metadata numbers;
- validate canonical sensitivity at runtime;
- prevent private/credential content through sensitivity;
- reject structurally invalid permissions instead of coercing strings;
- inspect equivalent persisted header type channels;
- preserve all V1/V2 security regressions.

## MAJOR-V3-002

Create one stable JSON-compatible canonical structured-payload representation:

- safe nested mappings must publish;
- safe nested lists/sequences must round-trip without live/reopen shape drift;
- real orchestration `supporting_domains` must round-trip identically;
- nested caller-owned aliases must not mutate `PublicationResult.event`;
- fingerprints/serialization must remain deterministic;
- do not create a new event contract.

## MINOR-V3-001

Make dead-letter inspection/retrieval snapshots actually detached:

- external mutation of a returned DLQ entry must not change later queue observations;
- preserve targeted replay behavior and subscriber identity/policy;
- reuse existing canonical snapshot machinery.

---

# 18. Required new acceptance/regression scenarios

Strengthen permanent regressions and `AT-DP-122`.

At minimum add:

```text
opaque metadata object rejected before any persistence
SecretObject.__str__ credential cannot reach JSONL
metadata bytes rejected
metadata bytearray rejected
metadata NaN rejected
metadata infinity rejected

sensitivity must be EventSensitivity or one explicit safe normalization
credential-bearing sensitivity rejected before persistence
invalid permissions string rejected rather than coerced

result_reference nested mapping publishes successfully
approval_refs nested mapping/list publishes successfully
supporting_domains has one canonical live/reopened shape
real PlatformOrchestrationEventSink supporting_domains round-trip is equal

manual publish_event nested input alias cannot mutate PublicationResult.event
repository and publication result remain canonically equal after caller mutation

list_dead_letters/get dead-letter mutations do not alter retained queue evidence
```

Retain every V1 and V2 remediation regression.

---

# 19. Required gates after Remediation V3

Before another independent audit:

1. all new V3-finding regression tests;
2. all V1 remediation regressions;
3. all V2 remediation regressions;
4. full `tests/events/`;
5. strengthened `AT-DP-122`;
6. Phase 9 runtime-event regressions;
7. Phase 10.33 Domain Event suite/acceptance;
8. validation/orchestration/workflow connected regressions;
9. `AT-DP-102`;
10. `AT-DP-103`;
11. `AT-DP-105`;
12. Phase 11.21;
13. Phase 11.34 where relevant;
14. `AT-DP-150`;
15. complete event inventory;
16. global pytest;
17. Ruff on all changed Python files;
18. global Ruff no-new-debt relative to current V3 evidence count `810`;
19. format check;
20. compileall;
21. `git diff --check`;
22. architecture anti-fragmentation gates;
23. event-security gates;
24. tracked clean state.

No unrelated Ruff cleanup.

---

# 20. Historical artifacts remain immutable

Do not modify or overwrite:

```text
phase-11.22-event-system-audit-v1.tar.gz
phase-11.22-event-system-audit-v2.tar.gz
phase-11.22-event-system-audit-v3.tar.gz

docs/audits/phase-11.22-event-system-independent-audit-v1.md
docs/audits/phase-11.22-event-system-independent-reaudit-v2.md
```

Historical bundle hashes:

```text
V1:
a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3

V2:
172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04

V3:
27517348570837df2abe9fc7f11e5cc24cefc32a198ffe3e0afefaee5df3c589
```

This V3 report also becomes immutable historical evidence once committed.

---

# 21. Next bundle

After Remediation V3:

- commit every change;
- require tracked worktree clean;
- preserve V1/V2/V3 bundles unchanged;
- create a **new** exact-HEAD bundle with `git archive`.

Required filename:

```text
phase-11.22-event-system-audit-v4.tar.gz
```

Calculate and report a new SHA-256.

Do not overwrite V3.

---

# 22. Final V3 audit markers

```text
PHASE=11.22
INDEPENDENT_REAUDIT_V3=FAIL

AUDIT_HEAD=7b582312319beae9b5d0e19dc25a726ee9d65360
AUDIT_TREE=0e4938f990a764fd06591a9423da28448c47ffc0
AUDIT_BUNDLE=phase-11.22-event-system-audit-v3.tar.gz
AUDIT_BUNDLE_SHA256=27517348570837df2abe9fc7f11e5cc24cefc32a198ffe3e0afefaee5df3c589

BUNDLE_INTEGRITY=PASS
EXACT_HEAD=PASS
EXACT_TREE=PASS
ARCHITECTURE_DIRECTION=PASS

AUDIT_V1_FINDINGS_REMEDIATED=9/9_VERIFIED
REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_VERIFIED

BLOCKERS=0
MAJORS=2
MINORS=1

MAJOR_V3_001=FULL_PERSISTED_EVENT_SAFETY_AND_HEADER_TYPE_VALIDATION_INCOMPLETE
MAJOR_V3_002=STRUCTURED_PAYLOAD_CANONICALIZATION_AND_ROUNDTRIP_UNSTABLE
MINOR_V3_001=DLQ_SNAPSHOT_MUTABLE

DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO

NEXT_STEP=REMEDIATION_V3_ONLY
```
