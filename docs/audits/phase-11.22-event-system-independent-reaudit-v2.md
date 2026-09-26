# Phase 11.22 — Event System — Independent Re-audit V2

**Project:** CMM OS
**Phase:** 11.22 — Event System
**Audit:** Independent ChatGPT Re-audit V2
**Audited branch:** `feature/phase-11-stable-integrated-platform`
**Audited HEAD:** `e67ab1ccea691fd8e76a0dfb8e4721c03b13b51d`
**Audited tree:** `a93cce0db1eb094a5b29f9d1322b5351d232e2dc`
**Bundle:** `phase-11.22-event-system-audit-v2.tar.gz`
**Bundle SHA-256:** `172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04`
**Design Point:** `DP-122`
**Connected acceptance:** `AT-DP-122`
**Previous audit:** Independent Audit V1 at `5d7be37a3d0e48f36a709b5564ed2a3fa7badbd9`

## Verdict

```text
INDEPENDENT_REAUDIT_V2=FAIL

AUDIT_V1_FINDINGS_REMEDIATED=9/9_VERIFIED

BLOCKERS=0
MAJORS=4
MINORS=0

DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO

NEXT_STEP=REMEDIATION_V2_ONLY
```

Phase 11.22 remains open.

Phase 11.23 must not begin.

---

# 1. Audit basis

The re-audit was performed against the uploaded exact-HEAD V2 archive, not against the remediation-agent handoff.

Authoritative design and implementation artifacts inside the bundle include:

- `docs/superpowers/specs/2026-09-26-phase-11.22-event-system-design.md`
- `docs/superpowers/plans/2026-09-26-phase-11.22-event-system-implementation-plan.md`
- `docs/superpowers/prompts/2026-09-26-phase-11.22-event-system-implementation-agent-prompt.md`
- `docs/superpowers/prompts/2026-09-26-phase-11.22-remediation-v1-agent-prompt.md`
- `docs/audits/phase-11.22-event-system-independent-audit-v1.md`
- `docs/audits/phase-11.22-event-system-implementation-evidence.md`
- `docs/reference/phase-11-event-system.md`

The re-audit had two distinct duties:

1. verify every Audit V1 finding was actually remediated;
2. perform a fresh adversarial review of the resulting Phase 11.22 implementation rather than stopping after the nine known regressions.

---

# 2. Exact bundle provenance

Independent checks against the uploaded V2 archive:

```text
AUDIT_V2_SHA256=172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04
GZIP_INTEGRITY=PASS
ARCHIVE_COMMIT=e67ab1ccea691fd8e76a0dfb8e4721c03b13b51d
RECONSTRUCTED_TREE=a93cce0db1eb094a5b29f9d1322b5351d232e2dc
```

The `git archive` PAX metadata contains exactly the declared remediation HEAD.

The Git tree reconstructed independently from the archive's tracked file bytes and modes exactly equals the declared remediation tree.

The historical V1 audit report embedded in the V2 tree remains byte-identical:

```text
V1_AUDIT_REPORT_SHA256=
3d259b8ee9dd56d00da35d19d53670d625b399c35bff70e3ccd76e681beb1cb1
```

The approved design spec also remains byte-identical:

```text
DESIGN_SPEC_SHA256=
d7e3cb3de474776f591fee576103db5d80db0f53fc85dd6c3293cd58c2b72f40
```

Result:

```text
BUNDLE_INTEGRITY=PASS
EXACT_HEAD=PASS
EXACT_TREE=PASS
V1_AUDIT_HISTORY_PRESERVED=PASS
```

---

# 3. Scope review

The V1→V2 remediation delta is bounded to the audited event-system implementation, its tests, remediation prompt and documentation.

No second event bus, mutable registry, repository protocol, replay engine or DLQ authority was introduced.

No Kafka, Redis Streams, NATS, RabbitMQ, new command bus, new workflow engine, new container or service locator was found.

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

The architecture accepted in V1 remains accepted.

---

# 4. Audit V1 remediation verification — 9/9

All nine V1 findings were independently rechecked against V2.

## V1 MAJOR-001 — fingerprint completeness

**Status:** `VERIFIED_REMEDIATED`

The implementation now builds the event fingerprint from the shared complete canonical event serialization.

Independent checks verified that changing material persisted fields including correlation, causation, sensitivity, metadata, permissions and raw payload changes the fingerprint.

Same-ID changed-content attempts fail as canonical identity conflicts.

Tampering with stored correlation without updating the fingerprint produces durable persistence corruption.

---

## V1 MAJOR-002 — `publish_event()` safety/registry bypass

**Status:** `VERIFIED_REMEDIATED`

The public `EventSystem.publish_event()` now passes through `_validate_platform_event()` before persistence.

Independent adversarial publication attempts verified rejection before persistence for:

- unknown event types;
- `prompt`;
- hidden reasoning;
- credential-like payload;
- opaque payload values;
- raw payload content.

---

## V1 MAJOR-003 — wrong-subscriber dead-letter replay

**Status:** `VERIFIED_REMEDIATED`

Dead-letter replay now uses targeted subscription delivery.

Independent checks verified:

- an unrelated replay-enabled subscriber cannot satisfy another subscriber's dead-letter;
- a replay-disabled failed subscriber keeps its DLQ record;
- the original replay-enabled failed subscriber is targeted directly;
- the DLQ entry is removed only after that target succeeds.

---

## V1 MAJOR-004 — correlation/causation loss

**Status:** `VERIFIED_REMEDIATED`

The Kernel adapter now gives explicit source `correlation_id` and `causation_id` priority over fallback derivation.

A real Domain Event path preserved:

```text
CORR-ORIGINAL
CAUSE-ORIGINAL
```

unchanged through:

```text
DomainKernelEventPublisher
→ kernel.events.Event
→ PlatformKernelEventAdapter
→ EventSystem
```

---

## V1 MINOR-001 — successful retries omitted from `retry_total`

**Status:** `VERIFIED_REMEDIATED`

A fail-once/succeed-next attempt independently produced:

```text
actual retry attempts = 1
retry_total = 1
```

---

## V1 MINOR-002 — malformed stored payload shape escaped as incidental error

**Status:** `VERIFIED_REMEDIATED`

Malformed persisted payload containers including list/string/integer/null now surface through the canonical persistence-corruption error.

---

## V1 MINOR-003 — forbidden Kernel source content silently ignored

**Status:** `VERIFIED_REMEDIATED`

Forbidden/private/credential-bearing ignored source facts now fail closed, while harmless irrelevant source facts may still be ignored.

---

## V1 MINOR-004 — reserved-event count documentation

**Status:** `VERIFIED_REMEDIATED`

The canonical disposition is now documented consistently as:

```text
12 connected
2 canonical runtime
6 reserved
```

---

## V1 MINOR-005 — inaccurate Phase 9 modification wording

**Status:** `VERIFIED_REMEDIATED`

The requirements matrix now accurately records that Phase 9 remains the canonical authority while receiving bounded additive compatibility hardening under Phase 11.22.

---

## V1 remediation result

```text
AUDIT_V1_FINDINGS_REMEDIATED=9/9_VERIFIED
```

No V1 finding is carried forward into V2.

The failures below are new findings from the fresh V2 review.

---

# 5. Independent execution

The independent audit environment does not contain all repository development dependencies, notably `libcst` and `ruff`, and has no network access to install them.

Therefore the complete repository suite and exact Ruff invocation could not be independently rerun unchanged.

The committed remediation evidence reports:

```text
REMEDIATION_TESTS=86 passed
PHASE_SUITE=625 passed
AT-DP-122=45 passed
FOCUSED_EVENT_BASELINE=972 passed
EVENT_INVENTORY=1270 passed
GLOBAL_PYTEST=22694 passed, 1 warning, 0 failed
GLOBAL_RUFF_COUNT=810
```

Independent source compilation succeeded:

```text
python -m compileall -q cmm kernel
COMPILEALL=PASS
```

A dependency-isolated harness was used to execute the event-system remediation-focused tests while leaving the audited production target modules unchanged.

Result:

```text
INDEPENDENT_FOCUSED_TESTS=331 passed
```

The four new major findings below were also reproduced independently through direct executable scenarios against the audited V2 production modules.

The inability to run the full dependency-heavy suite is not the reason for this FAIL verdict.

---

# 6. New V2 findings

## MAJOR-V2-001 — Platform safety validates payload data but not persisted free-form header facts

### Affected code

- `cmm/events/event_system.py:216-265`
- `cmm/events/event_system.py:469-492`
- `cmm/agent_runtime/runtime_event_factory.py:161-231`
- `cmm/agent_runtime/runtime_event_contracts.py:55-130`

The V1 remediation correctly closes unsafe `payload.data` publication.

However the public platform publication path persists several free-form header fields that do not pass through the same privacy/credential/private-content safety policy:

- `metadata`;
- `permissions`;
- `producer`;
- `aggregate_id`;
- `source`.

`EventSystem._validate_platform_event()` checks:

1. registry membership;
2. `payload.raw is None`;
3. `validate_platform_payload(event.payload.data)`;
4. normalization.

It does not validate these persisted header facts.

The factory deep-copies metadata/permissions but does not apply the platform safety scan to them.

### Independent reproduction

Public `EventSystem.publish()` accepted and persisted all of the following:

```text
metadata={"prompt": "TOP SECRET"}                         → ACCEPTED
metadata={"api_key": "sk-..."}                           → ACCEPTED
producer="api_key=sk-..."                                → ACCEPTED
aggregate_id="sk-..."                                    → ACCEPTED
source="system_prompt=TOP SECRET"                        → ACCEPTED
permissions=["api_key=sk-..."]                           → ACCEPTED
```

These facts are part of the canonical persisted event and therefore bypass the intended security boundary even though `payload.data` is safe.

### Violated frozen requirements

The design specification requires the **event path**, not merely the payload dictionary, to reject prompts, credentials, tokens and secret values.

It also states:

```text
hidden reasoning never enters platform events
raw provider payloads never enter platform events
secrets and credentials never enter event persistence or DLQ data
```

See the frozen design sections:

- `§7 Safe payload policy`
- `§23 Security invariants`

### Impact

The Phase 11.22 security boundary remains incomplete.

A caller can move forbidden material from `payload.data` into persisted header metadata/identity fields and bypass the V1 safety remediation.

This prevents verification of:

```text
EVENT_PAYLOAD_SECURITY
SECRETS_NEVER_ENTER_EVENT_PERSISTENCE
CREDENTIALS_NEVER_ENTER_EVENT_PERSISTENCE
```

### Required Remediation V2

Create one canonical platform-event safety validation step covering every persisted free-form field that can carry user-controlled or producer-controlled text/structure.

At minimum validate:

- metadata recursively;
- permissions entries;
- source;
- producer;
- aggregate ID;

and inspect all other persisted optional identifiers for equivalent risk.

Do not create a second safety-policy authority.

Reuse the existing Phase 11.22 credential/private-content scanner.

Preserve legitimate safe identifiers and categorical values.

Add direct public-path tests proving forbidden/private/credential content in every persisted header channel fails **before persistence**.

---

## MAJOR-V2-002 — Unsupported event schema can be durably written into a repository that cannot reopen it

### Affected code

- `cmm/events/event_system.py:216-265`
- `cmm/agent_runtime/runtime_event_factory.py:152-231`
- `cmm/agent_runtime/runtime_event_repository.py:230-259`
- `cmm/agent_runtime/runtime_event_repository.py:351-419`

`AgentRuntimeEventFactory` explicitly declares:

```text
SUPPORTED_SCHEMA_VERSION = "1.0.0"
```

and canonical deserialization rejects unsupported versions.

But `create_event()` accepts an arbitrary `schema_version`, the Phase 11.22 public facade exposes that fact, and the durable repository writes it.

### Independent reproduction

```text
system.publish(
    "goal.created",
    {"status": "created"},
    schema_version="9.9.9",
)
```

Result at write time:

```text
WRITE=ACCEPTED
SCHEMA_VERSION=9.9.9
REPOSITORY_COUNT=1
```

Opening the same durable repository again:

```text
REOPEN=FAIL
AgentRuntimeEventPersistenceCorruptionError:
stored event record 1 is not a canonical event
```

### Impact

A successful public platform publication can create durable evidence that the same canonical repository immediately considers corrupt after restart.

This violates the durable round-trip contract and the requirement that malformed/unsupported persisted events fail closed **before poisoning durable storage**.

It also means a valid-looking Phase 11.22 write can make subsequent startup fail.

### Required Remediation V2

The Phase 11.22 publication/durable write boundary must reject schema versions that this build cannot deserialize before append.

Preserve generic Phase 9 compatibility if arbitrary construction has legitimate historical uses; the fix need not globally prohibit all factory construction.

The key invariant is:

```text
if FileAgentRuntimeEventRepository successfully saves a canonical event,
the same build must be able to deserialize that record after reopen
```

Add tests for:

- public `EventSystem.publish()` unsupported schema rejection before persistence;
- direct durable repository save of unsupported canonical schema if the repository contract can receive such an object;
- supported schema close/reopen round-trip.

---

## MAJOR-V2-003 — Canonical event contracts are shallow-frozen; subscribers can mutate persisted evidence and later subscriber observations

### Affected code

- `cmm/agent_runtime/runtime_event_contracts.py:55-130`
- `cmm/agent_runtime/runtime_event_bus.py`
- in-memory and file-backed event repository live-object storage

The canonical event classes are declared `@dataclass(frozen=True)`, and `AgentRuntimeEvent` is documented as an:

```text
Immutable runtime event contract
```

But nested canonical state remains mutable:

```python
permissions: list[str]
metadata: dict[str, Any]
payload.data: dict[str, Any]
```

The bus delivers the same object instance sequentially to subscribers.

The repository keeps the same live event object in memory after persistence.

### Independent reproduction

Subscriber A, during normal delivery:

```python
event.payload.data["status"] = "tampered-by-A"
event.header.metadata["tampered"] = "yes"
```

A later subscriber B then observed:

```text
status = tampered-by-A
metadata.tampered = yes
```

The repository's live `get()` result also contained the subscriber mutation.

Result:

```text
LATER_SUBSCRIBER_SAW_MUTATION=True
REPOSITORY_LIVE_EVENT_MUTATED=True
```

With the file-backed repository, the in-memory live object can diverge from the bytes already fsync'd to disk until reopen.

### Impact

A subscriber receives mutation power over:

- what later subscribers observe;
- the live repository representation of already-persisted evidence;
- the event object returned in the publication result.

This contradicts:

```text
Immutable runtime event contract
append-only evidence
content-bound identity
event receipt grants no permission
```

It also creates a split-brain condition between persisted disk bytes and the live repository object.

This is especially important because Phase 11.22 elevates Phase 9 events into a platform-wide durable evidence path.

### Required Remediation V2

Make canonical event facts effectively immutable across the Phase 11.22 publication/delivery/storage path.

A valid remediation may use one of the existing architectural owners to provide:

- recursively immutable canonical event fields; or
- defensive detached snapshots at repository and delivery boundaries.

Do not create a second event contract.

Requirements after remediation:

1. one subscriber cannot change what a later subscriber sees;
2. one subscriber cannot mutate the repository's stored event representation;
3. publication result facts remain stable;
4. file-backed live and reopened representations do not diverge because of subscriber mutation;
5. fingerprint/content identity remains stable after publication.

Preserve serialization compatibility with Phase 9 where possible.

Add adversarial subscriber-mutation tests for payload, metadata and permissions.

---

## MAJOR-V2-004 — Kernel bridge loses the mapped lifecycle facts of real Domain Events and downgrades source sensitivity

### Affected code

- `cmm/events/kernel_adapter.py:57-100`
- `cmm/events/kernel_adapter.py:147-173`
- `cmm/events/kernel_adapter.py:189-303`
- `cmm/events/event_translation.py:125-156`
- `cmm/domains/event_contracts.py:692-857`
- `docs/reference/phase-11-event-system.md` translation table

The Kernel adapter's translation table explicitly claims the following Domain projections:

```text
domain.execution.completed
→ operation.executed
→ domain_id, status, execution_id, duration_ms

domain.approval.requested
→ approval.requested
→ domain_id, status, approval_id

domain.approval.received
→ approval.resolved
→ domain_id, status, approval_id

domain.memory.updated
→ memory.updated
→ domain_id, status
```

But a real `DomainEvent.to_dict()` stores event-specific lifecycle facts inside the top-level structural:

```text
payload
```

container.

The Kernel adapter's V1 remediation safely scans that structural payload but then ignores it.

Therefore the translation table asks `_project()` for facts that never reach the adapter's flattened readable payload.

### Independent real-component reproductions

#### Execution

Real Domain source:

```text
domain.execution.completed
payload={
    "execution_id": "EXEC-1",
    "status": "completed"
}
sensitivity="restricted"
correlation_id="CORR-ORIGINAL"
causation_id="CAUSE-ORIGINAL"
```

Platform event produced:

```text
event_type=operation.executed
payload={
    "domain_id": "domain:general",
    "event_type": "domain.execution.completed"
}
aggregate_id=domain:general
sensitivity=INTERNAL
correlation_id=CORR-ORIGINAL
causation_id=CAUSE-ORIGINAL
```

The V1 correlation/causation remediation works, but `execution_id` and `status` are lost and sensitivity is downgraded.

#### Approval requested

Source:

```text
payload={
    "approval_id": "APP-1",
    "action": "delete"
}
```

Platform event loses the `approval_id`.

#### Approval resolved

Source:

```text
payload={
    "approval_id": "APP-2",
    "approved": true,
    "decision_by": "u1"
}
```

Platform event loses the approval identity and resolution facts.

#### Memory updated

Source:

```text
payload={
    "update_id": "UPD-1",
    "status": "updated"
}
```

Platform event loses `status`.

### Internal `execution_id` inconsistency

`READABLE_PAYLOAD_KEYS` explicitly allows a top-level `execution_id` and comments that it will be projected to `aggregate_id`.

But `_project()` copies `execution_id` into the platform payload, while the bounded platform payload vocabulary does not permit that key.

Independent direct Kernel Event result:

```text
domain.execution.completed
with top-level execution_id="EXEC-TOP"
→ PlatformEventPayloadError:
payload key is outside the bounded platform event vocabulary
```

### Sensitivity downgrade

The adapter reads source `sensitivity` but does not pass it as the canonical event header sensitivity.

A real Domain event with a more restrictive source classification becomes the default:

```text
EventSensitivity.INTERNAL
```

This loses a security classification already present in the canonical source event.

### Impact

The bridge is technically connected but does not faithfully transport the lifecycle facts its own contract and documentation claim it maps.

This prevents verification that the platform event catalog is genuinely connected to the existing Domain owner semantics.

It also risks under-classifying sensitive events.

### Required Remediation V2

Do not alter Phase 10.33 Domain Event contracts.

Fix the thin Kernel adapter projection so that, for explicitly mapped Domain Event sources:

1. the safe mapped facts are read from the real Domain Event serialized structure;
2. only explicitly whitelisted nested facts are projected;
3. approval/execution/memory identities and status are not invented or lost;
4. `execution_id` is handled consistently as payload fact and/or aggregate identity according to the frozen platform vocabulary;
5. source sensitivity is preserved or safely mapped without downgrade;
6. explicit correlation/causation preservation from V1 remains intact;
7. forbidden nested content still fails closed.

Use real:

```text
DomainKernelEventPublisher
→ Kernel Event
→ PlatformKernelEventAdapter
→ EventSystem
```

connected regressions.

---

# 7. Security assessment

V2 substantially improves the V1 payload-security boundary.

The V1 bypass through direct `publish_event()` is fixed.

However MAJOR-V2-001 demonstrates that forbidden material can still enter the exact same durable canonical event through persisted header channels.

MAJOR-V2-004 additionally demonstrates sensitivity downgrade at a connected adapter boundary.

Current status:

```text
PAYLOAD_DATA_SECURITY=PASS
FULL_CANONICAL_EVENT_SECURITY=FAIL
SOURCE_SENSITIVITY_PRESERVATION=FAIL
```

---

# 8. Persistence and integrity assessment

Positive:

- V1 complete-fingerprint remediation is correct;
- same-ID changed material content fails closed;
- tamper detection covers the complete canonical serialization;
- malformed payload-shape errors are normalized;
- fsync/append-only file mechanics remain intact.

But:

- unsupported schema can be appended successfully and make the store unreadable on reopen;
- shallow event mutability lets the live repository representation change after durable append.

Current status:

```text
CONTENT_BOUND_FINGERPRINT=PASS
DURABLE_TAMPER_DETECTION=PASS
SUPPORTED_SCHEMA_ROUNDTRIP=FAIL
LIVE_STORED_EVENT_IMMUTABILITY=FAIL
```

---

# 9. Replay and DLQ assessment

The V1 replay remediation is accepted.

Independent V2 checks verify:

```text
TARGETED_DLQ_REPLAY=PASS
REPLAY_POLICY_ENFORCED=PASS
UNRELATED_SUBSCRIBER_CANNOT_RESOLVE_DLQ=PASS
NO_DUPLICATE_REPERSISTENCE=PASS
```

No new replay/DLQ finding is raised in V2.

---

# 10. Adapter assessment

Explicit correlation and causation now survive the Kernel adapter.

That V1 fix is accepted.

The remaining problem is projection fidelity and sensitivity classification for real Domain Event structures.

Current status:

```text
EXPLICIT_CORRELATION_PRESERVED=PASS
EXPLICIT_CAUSATION_PRESERVED=PASS
DOMAIN_MAPPED_FACT_FIDELITY=FAIL
DOMAIN_SENSITIVITY_PRESERVATION=FAIL
```

---

# 11. DP-122 assessment

DP-122 requires a canonical event path that is:

- durable;
- content-bound;
- safe;
- replayable;
- failure-aware;
- correlation/causation preserving;
- privacy preserving;
- faithful to existing subsystem authorities.

V2 now satisfies the nine specific defects found in V1.

But the fresh V2 review proves that:

1. secrets/private material can enter persisted canonical headers;
2. the public durable path can persist a schema the repository cannot reopen;
3. subscribers can mutate supposedly immutable persisted event facts;
4. the real Domain bridge loses mapped lifecycle facts and sensitivity.

Therefore:

```text
DP-122=NOT_VERIFIED
```

---

# 12. AT-DP-122 assessment

The remediation reports:

```text
AT-DP-122=45 passed
```

and the V1 adversarial scenarios have been added.

However the connected acceptance still does not prove the newly reproduced V2 invariants:

- header-field event safety;
- unsupported-schema durable round-trip prevention;
- subscriber inability to mutate canonical/persisted evidence;
- real Domain mapped-fact fidelity and sensitivity preservation.

Since independently observed behavior contradicts DP-122, the acceptance cannot be independently verified as sufficient.

Result:

```text
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
```

This marker does not assert that the 45 committed tests themselves fail.

It means the connected acceptance remains incomplete relative to the frozen design point.

---

# 13. Documentation assessment

The V1 remediation documentation is materially improved and correctly keeps the phase pending independent re-audit.

The historical V1 report is preserved unchanged.

The catalog counts and Phase 9 hardening language are corrected.

No premature closure marker was found in the audited V2 implementation evidence/reference state.

The documentation must now be updated only to record V2 failure and subsequent Remediation V2 status; it must not erase or rewrite the V1 history.

---

# 14. Required Remediation V2 scope

Remediation V2 must fix **only** the four new V2 major findings.

## Required

1. **Full canonical event safety**
   - validate all persisted free-form header facts through the existing safety policy;
   - block prompts/reasoning/credentials/secrets before persistence regardless of whether they are placed in payload or header channels.

2. **Supported-schema durability**
   - prevent durable append of an event schema the current canonical deserializer cannot reopen;
   - prove supported-schema close/reopen round-trip.

3. **Canonical event immutability**
   - prevent subscriber mutation from changing later delivery, repository live evidence or publication-result facts;
   - preserve serialization/backward compatibility as far as possible.

4. **Real Domain bridge fidelity**
   - correctly project safe explicitly mapped Domain Event nested facts;
   - preserve source sensitivity without downgrade;
   - keep explicit correlation/causation preservation;
   - retain fail-closed nested-content scanning.

## Required acceptance additions

Strengthen `AT-DP-122` with real-component scenarios proving:

- unsafe metadata fails before persistence;
- unsafe permissions fail before persistence;
- unsafe producer/source/aggregate fields fail before persistence;
- unsupported schema is rejected before durable append;
- subscriber A cannot mutate what subscriber B sees;
- subscriber cannot mutate repository evidence;
- real `domain.execution.completed` preserves execution identity/status;
- real approval events preserve approval identity/status/decision facts according to the bounded mapping;
- real memory update preserves mapped status;
- restrictive Domain sensitivity is not silently downgraded.

## Do not

- create a second bus;
- create a second registry/repository/replayer/DLQ;
- redesign Phase 9;
- revert any of the 9 V1 fixes;
- broaden into Phase 11.23;
- broaden into Phase 11.24;
- perform unrelated Ruff cleanup;
- rewrite the V1 audit report;
- overwrite the V1 or V2 audit bundles.

---

# 15. Required gates after Remediation V2

Before the next independent re-audit:

1. new V2-finding regression tests;
2. full `tests/events/`;
3. strengthened `AT-DP-122`;
4. Phase 9 runtime-event regressions;
5. Phase 10.33 Domain Event acceptance/regressions;
6. Orchestration/Validation connected regressions;
7. `AT-DP-102`;
8. `AT-DP-103`;
9. `AT-DP-105`;
10. Phase 11.21 regression;
11. Phase 11.34 regression where relevant;
12. `AT-DP-150`;
13. complete event inventory;
14. global pytest;
15. Ruff on every changed Python file;
16. global Ruff no-new-debt gate relative to V2 count `810`;
17. format check;
18. compileall;
19. `git diff --check`;
20. architecture anti-fragmentation gates;
21. event-security gates;
22. exact tracked clean state.

The V2 implementation evidence reports global Ruff `810`; Remediation V2 must not increase it.

---

# 16. Next audit bundle

After Remediation V2:

- commit every remediation change;
- require tracked worktree clean;
- preserve V1 and V2 bundles unchanged;
- generate a new exact-HEAD bundle with `git archive`.

Required new filename:

```text
phase-11.22-event-system-audit-v3.tar.gz
```

Calculate a new SHA-256.

Do not overwrite or mutate V2.

The next independent audit must inspect V3.

---

# 17. Final V2 audit markers

```text
PHASE=11.22
INDEPENDENT_REAUDIT_V2=FAIL

AUDIT_HEAD=e67ab1ccea691fd8e76a0dfb8e4721c03b13b51d
AUDIT_TREE=a93cce0db1eb094a5b29f9d1322b5351d232e2dc
AUDIT_BUNDLE=phase-11.22-event-system-audit-v2.tar.gz
AUDIT_BUNDLE_SHA256=172f37be69af5a38603a97944104fdcbf4cac34d7dbd8e3d4b752f44cff3ad04

BUNDLE_INTEGRITY=PASS
EXACT_HEAD=PASS
EXACT_TREE=PASS
ARCHITECTURE_DIRECTION=PASS

AUDIT_V1_FINDINGS_REMEDIATED=9/9_VERIFIED

BLOCKERS=0
MAJORS=4
MINORS=0

MAJOR_V2_001=FULL_EVENT_HEADER_SECURITY_INCOMPLETE
MAJOR_V2_002=UNSUPPORTED_SCHEMA_CAN_POISON_DURABLE_STORE
MAJOR_V2_003=CANONICAL_EVENT_NOT_DEEPLY_IMMUTABLE
MAJOR_V2_004=DOMAIN_KERNEL_BRIDGE_FACT_AND_SENSITIVITY_LOSS

DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO

NEXT_STEP=REMEDIATION_V2_ONLY
```
