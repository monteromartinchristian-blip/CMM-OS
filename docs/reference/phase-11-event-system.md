# Phase 11 — Event System reference

**Status:** `REMEDIATED_AFTER_REAUDIT_V11_PENDING_INDEPENDENT_REAUDIT`
**Phase:** 11.22 — Event System
**Design Point:** `DP-122 — One Canonical, Durable, Replayable Platform Event System`
**Acceptance Test:** `AT-DP-122` — `tests/events/test_phase11_22_dp122_acceptance.py`
**Design specification:** `docs/superpowers/specs/2026-09-26-phase-11.22-event-system-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-09-26-phase-11.22-event-system-implementation-plan.md`
**Implementation agent prompt:** `docs/superpowers/prompts/2026-09-26-phase-11.22-event-system-implementation-agent-prompt.md`
**Remediation V1 agent prompt:** `docs/superpowers/prompts/2026-09-26-phase-11.22-remediation-v1-agent-prompt.md`
**Remediation V2 agent prompt:** `docs/superpowers/prompts/2026-09-26-phase-11.22-remediation-v2-agent-prompt.md`
**Remediation V3 agent prompt:** `docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v3-agent-prompt.md`
**Remediation V4 agent prompt:** `docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v4-agent-prompt.md`
**Remediation V5 agent prompt:** `docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v5-agent-prompt.md`
**Remediation V6 agent prompt:** `docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v6-agent-prompt.md`
**Remediation V7 agent prompt:** `docs/superpowers/prompts/2026-09-27-phase-11.22-remediation-v7-agent-prompt.md`
**Remediation V8 agent prompt:** `docs/superpowers/prompts/2026-09-28-phase-11.22-remediation-v8-agent-prompt.md`
**Remediation V9 agent prompt:** `docs/superpowers/prompts/2026-09-28-phase-11.22-remediation-v9-agent-prompt.md`
**Remediation V10 agent prompt:** `docs/superpowers/prompts/2026-09-28-phase-11.22-remediation-v10-agent-prompt.md`
**Remediation V11 agent prompt:** `docs/superpowers/prompts/2026-09-28-phase-11.22-remediation-v11-agent-prompt.md`
**Production package:** `cmm/events/` (9 modules) plus additive Phase 9 hardening
**Contract catalog:** `cmm/events/event_catalog.py`

`DP-122=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION`
`AT-DP-122=PASS_REPORTED`

Phase 11.22 was implemented, failed independent Audit V1, failed independent
Re-audit V2, failed independent Re-audit V3, failed independent Re-audit V4,
failed independent Re-audit V5, failed independent Re-audit V6, failed independent
Re-audit V7, failed independent Re-audit V8, failed independent Re-audit V9 and
failed independent Re-audit V10, and
has been **remediated** after each. It is not closed, not independently verified and
not complete: the `VERIFIED_EXISTING` marker may only be written by the independent
re-audit of the V12 bundle. See §27 for the Remediation V4 record, §28 for the
Remediation V5 record, §29 for the Remediation V6 record, §30 for the Remediation V7
record, §31 for the Remediation V8 record, §32 for the Remediation V9 record, §33
for the Remediation V10 record and §34 for the Remediation V11 record.

### Provenance note (recorded deviation)

The implementation agent prompt requests preflight `HEAD=d691c753…`. The actual
implementation starting HEAD was `744de6d996e0aa3dc3f9326fdb33fc38ab13ac8d`,
whose parent is exactly `d691c753c25801d1957fc8dee917ef4e6fff4694` and whose tree
`36255f0293ac23fe93c2c85c94b989dd91ca0ff2` is the required starting tree. The
only intervening change is the committed Phase 11.22 implementation-agent prompt
document itself; there are **zero production-code differences**. The user
explicitly authorized proceeding from `744de6d` with `d691c753` treated as the
frozen pre-prompt baseline. No reset, checkout, stash, clean or worktree
operation was performed.

## 1. Purpose

Phase 11.22 is an **integration and hardening** phase, not a new event subsystem.

CMM OS already had exactly one canonical in-process event transport. Phase 11.22
makes that existing infrastructure genuinely platform-usable, durable,
replayable, deduplicated, failure-aware and safely integrated, while every
existing subsystem remains the sole authority for the facts it emits.

```text
producer fact
  -> safe adapter
  -> canonical event factory
  -> canonical registry validation
  -> normalization
  -> dedup/conflict check
  -> durable append
  -> AgentRuntimeEventBus delivery
  -> bounded subscriber retry
  -> DLQ after exhaustion
```

## 2. Canonical owner map

Phase 11.22 adds **no** parallel authority. Every capability has one owner.

| Capability | Owner | Phase 11.22 treatment |
| --- | --- | --- |
| Event transport | `cmm.agent_runtime.runtime_event_bus.AgentRuntimeEventBus` | extended additively (bounded attempts, replay dispatch) |
| Mutable event registry | `cmm.agent_runtime.runtime_event_registry.AgentRuntimeEventRegistry` | reused unchanged |
| Event-type registration | `cmm.agent_runtime.runtime_event_types` | 16 additive platform names registered |
| Event repository contract | `cmm.agent_runtime.runtime_event_repository.AgentRuntimeEventRepository` | one durable implementation added |
| Replay owner | `cmm.agent_runtime.runtime_event_replay.AgentRuntimeEventReplayer` | extended to deliver stored events without re-persisting |
| Dead-letter authority | `cmm.agent_runtime.runtime_event_dead_letter.InMemoryAgentRuntimeDeadLetterQueue` | reused unchanged |
| Event contract/envelope | `cmm.agent_runtime.runtime_event_contracts.AgentRuntimeEvent` | two additive optional header fields |
| Canonical event factory | `cmm.agent_runtime.runtime_event_factory` | one exported deterministic fingerprint |
| Payload safety vocabulary | `cmm.domains.credential_policy`, `cmm.domains.event_contracts`, `cmm.orchestration.events` | composed, not replaced |
| Composition core | `cmm.platform.ApplicationContainer` / `StaticCompositionModule` | one new Phase 11.22 module |

Thin Phase 11.22 additions in `cmm/events/`:

| Module | Responsibility |
| --- | --- |
| `event_catalog.py` | immutable platform catalog plus producer dispositions |
| `event_payload_safety.py` | the single payload gate (fails before persistence) |
| `event_translation.py` | explicit one-way source-to-platform mappings |
| `event_system.py` | thin `EventSystem` composition facade; owns publication order |
| `orchestration_adapter.py` | production `OrchestrationEventSink` for the Phase 11.2 seam |
| `kernel_adapter.py` | one-way `kernel.events.Event` bridge |
| `platform_module.py` | Phase 11.1 composition contribution and composition factory |
| `storage.py` | durable event-storage location resolution |
| `__init__.py` | public exports |

## 3. Dependency graph

```text
cmm.orchestration ─┐
cmm.workflows      ├─► cmm.events ─► cmm.agent_runtime (Phase 9 transport)
cmm.validation     │        │
cmm.domains ───────┘        └─► cmm.platform (composition contracts only)
```

Enforced direction (executable in `tests/events/test_phase11_22_architecture.py`):

* `cmm.agent_runtime` **never** imports `cmm.events`, `cmm.orchestration` or
  `cmm.application`;
* `cmm.domains` **never** imports the runtime event transport;
* `cmm.platform` **never** imports `cmm.orchestration` or `cmm.events`;
* `cmm.events` may import `cmm.platform` composition contracts only;
* no module resolves services at runtime through a locator;
* event type strings never select an import path or callable.

## 4. Platform event catalog

The twenty historical minimum Phase 11.22 names, in frozen catalog order. The
catalog is a **contract catalog, not a registry**: the mutable registration
authority remains `AgentRuntimeEventRegistry`, reached through the Phase 9
event-type map.

```text
session.created          message.received         intent.resolved
domain.selected          reasoning.completed      goal.created
goal.updated             workflow.started         workflow.paused
workflow.completed       workflow.failed          operation.executed
validation.completed     approval.requested       approval.resolved
knowledge.updated        memory.updated           backup.created
plugin.failed            security.alert
```

Sixteen of these were newly registered on the canonical map; `goal.created`,
`goal.updated`, `approval.requested` and `validation.completed` were already
canonical Phase 9 runtime event types and were **not** duplicated or renamed.

## 5. Producer-disposition matrix

Exactly one disposition per catalog event. Executable in
`tests/events/test_phase11_22_producer_disposition.py`; a `CONNECTED_*` claim
requires cited evidence that actually exercises the event name.

### `CONNECTED_EXISTING_OWNER` (12)

| Event | Canonical owner | Connecting seam |
| --- | --- | --- |
| `message.received` | `cmm.orchestration` | `orchestration.request_received` → orchestration adapter |
| `intent.resolved` | `cmm.orchestration` | `orchestration.intent_resolved` → orchestration adapter |
| `domain.selected` | `cmm.orchestration` | `orchestration.domain_resolved` → orchestration adapter |
| `approval.requested` | `cmm.orchestration` | `orchestration.approval_required` → orchestration adapter |
| `workflow.started` | `cmm.workflows` | `workflow.running` → kernel adapter |
| `workflow.paused` | `cmm.workflows` | `workflow.paused` → kernel adapter |
| `workflow.completed` | `cmm.workflows` | `workflow.completed` → kernel adapter |
| `workflow.failed` | `cmm.workflows` | `workflow.failed` → kernel adapter |
| `operation.executed` | `cmm.agent_runtime` | `domain.execution.completed` → kernel adapter |
| `validation.completed` | `cmm.validation` | Phase 7 `KernelEventPublisher` → kernel adapter |
| `approval.resolved` | `cmm.domains` | `domain.approval.received` → kernel adapter |
| `memory.updated` | `cmm.domains` | `domain.memory.updated` → kernel adapter |

### `CANONICAL_EXISTING_RUNTIME_EVENT` (2)

| Event | Canonical owner | Rationale |
| --- | --- | --- |
| `goal.created` | `cmm.agent_runtime` | already a canonical Phase 9 runtime event |
| `goal.updated` | `cmm.agent_runtime` | already a canonical Phase 9 runtime event |

### `REGISTERED_RESERVED_OWNER_NOT_YET_AVAILABLE` (6)

These names are valid and resolvable but are **never emitted** by Phase 11.22.
No backup, plugin, security-alert, session, reasoning or knowledge event producer
was fabricated to make the catalog look active.

| Event | Why emission is deferred |
| --- | --- |
| `session.created` | the canonical session store owns session lifecycle but exposes no event seam |
| `reasoning.completed` | the cognitive package owns reasoning but emits no canonical lifecycle event |
| `knowledge.updated` | the knowledge subsystem exposes no canonical event seam |
| `backup.created` | no canonical backup owner exists at Phase 11.22 |
| `plugin.failed` | no canonical plugin runtime owner exists at Phase 11.22 |
| `security.alert` | no canonical security-alert detector owner exists at Phase 11.22 |

A regression gate proves no Phase 11.22 mapping targets a reserved event and that
no module outside the catalog registration surface names one.

## 6. Source-to-platform translation table

One-way and explicit. A source fact with no mapping is observed and skipped, never
guessed. Mappings may copy only facts that are actually present.

### Orchestration (`cmm/events/event_translation.py`)

| Source event | Platform event | Facts read |
| --- | --- | --- |
| `orchestration.request_received` | `message.received` | `channel`, `session_id` |
| `orchestration.intent_resolved` | `intent.resolved` | `intent`, `needs_clarification` |
| `orchestration.domain_resolved` | `domain.selected` | `status`, `primary_domain`, `supporting_domains` |
| `orchestration.approval_required` | `approval.requested` | `status`, `primary_domain`, `approval_refs` |

Unmapped by design: `orchestration.route_selected`, `orchestration.blocked`,
`orchestration.escalated`, `orchestration.routed`, `orchestration.failed`.

### Kernel events

| Source event | Platform event | Facts read |
| --- | --- | --- |
| `validation.completed` | `validation.completed` | `validation_id`, `status`, `policy`, `duration_ms`, `workflow_id` |
| `validation.failed` | `validation.completed` | same, carrying its own `failed` status |
| `domain.execution.completed` | `operation.executed` | `domain_id`, `status`\*, `execution_id`\*, `duration_ms` |
| `domain.resolution.completed` | `domain.selected` | `domain_id`, `status`\* |
| `domain.approval.requested` | `approval.requested` | `domain_id`, `status`, `approval_id`\* |
| `domain.approval.received` | `approval.resolved` | `domain_id`, `status`, `approval_id`\*, `approved`\* |
| `domain.memory.updated` | `memory.updated` | `domain_id`, `status`\* |
| `workflow.started` | `workflow.started` | `workflow_id`, `run_id`, `status` |
| `workflow.running` | `workflow.started` | `workflow_id`, `run_id`, `status` |
| `workflow.paused` | `workflow.paused` | `workflow_id`, `run_id`, `status`, `node_id` |
| `workflow.completed` | `workflow.completed` | `workflow_id`, `run_id`, `status` |
| `workflow.failed` | `workflow.failed` | `workflow_id`, `run_id`, `status`, `error_code` |

`*` A real `DomainEvent.to_dict()` stores its event-specific lifecycle facts inside
its own structural top-level `payload` container rather than at the top level of
its serialization. Each translation therefore declares an explicit
`nested_fact_keys` subset naming exactly which facts may be read from that
container. The container is never flattened generically: a nested key the
translation does not name is unreadable to the bridge, only the named keys may
cross, and each of them must already belong to the bounded platform payload
vocabulary. A fact absent from the source stays absent — an approval request with
no source status is projected with no `status`, and nothing is invented.

Unmapped by design: every `validation.step.*`, `validation.started`,
`validation.gate.*`, `domain.execution.started`, `domain.composition.*`,
`domain.conflict.*`, `domain.permission.*`, `domain.workflow.resumed`,
`node.*` and any specialized domain event.

## 7. Event contract fields

Platform transport reuses `AgentRuntimeEvent`; no new envelope exists.

| Fact | Field | Status |
| --- | --- | --- |
| stable event ID | `header.event_id` | existing |
| event type | `header.event_type` | existing |
| schema version | `header.schema_version` | existing; the publication boundary and the durable repository both refuse a schema this build cannot deserialize (Remediation V2) |
| occurrence time | `header.occurred_at` | existing |
| emission time | `header.emitted_at` | existing |
| safe producer identity | `header.producer` | **additive optional** |
| aggregate/reference identity | `header.aggregate_id` | **additive optional** |
| structured safe payload | `payload.data` | existing |
| correlation ID | `header.correlation_id` | existing |
| causation ID | `header.causation_id` | existing |
| sensitivity | `header.sensitivity` | existing |
| execution/operation reference | `payload.data["execution_id"]` | **bounded payload fact** (Remediation V2) |

`schema_version` is persisted, so a durable append whose schema the current
canonical factory could not reopen is refused before any byte is committed: a
successful save by this build is always readable by this build after a restart.

`execution_id` is decided once, deliberately: it is a **bounded platform payload
fact**, not a second aggregate identity. The design's safe payload policy
explicitly allows operation/execution references, and the source-to-platform
translation table has always named it as a read fact. It is therefore in the
bounded platform payload vocabulary, and no adapter path can emit a payload key
the payload validator rejects. `header.aggregate_id` continues to carry the
canonical subject identity (the domain, workflow, run or operation reference) and
is unchanged by this decision.

Sensitivity crosses the Kernel bridge explicitly. A source classification already
present on a canonical source event is mapped through one explicit table
(`personal`/`confidential`/`sensitive` → `CONFIDENTIAL`, `highly_sensitive`/
`restricted` → `RESTRICTED`, `internal` → `INTERNAL`, `public` → `PUBLIC`), so a
platform classification is never less restrictive than its source classification.
A source classification with no explicit mapping fails closed rather than being
guessed at or silently downgraded to the platform default.

`source` keeps its Phase 9 meaning (the emitting runtime surface) and was **not**
repurposed as a producer alias. Old constructors stay valid, and old serialized
events still deserialize. `event_fingerprint()` hashes the **complete canonical
persisted event**: every persisted header field (event ID, type, schema version,
both timestamps, agent/run/goal/workflow/task/iteration identity, correlation,
causation, actor, `source`, sensitivity, permissions, metadata, producer,
aggregate identity) plus every persisted payload field (`payload.data` and
`payload.raw`). Corrections in Remediation V1 are recorded in §24; Remediation V2
in §25.

## 8. Durable persistence semantics

`FileAgentRuntimeEventRepository` implements the existing
`AgentRuntimeEventRepository` contract as newline-delimited JSON. No second
repository protocol and no generic event-store framework exists.

One record is:

```json
{"header": {...}, "payload": {...}, "fingerprint": "<sha256>", "record_schema_version": "1.0.0"}
```

* canonical factory serialization and deserialization only — no `pickle`, no
  `eval`, no `exec`, no unsafe YAML, no arbitrary object decoding (gated by AST);
* deterministic append order, preserved across reopen/restart;
* append is flushed and `fsync`-ed before `save` reports success;
* restrictive `0o600` permissions where the platform supports them;
* parent-directory creation bounded to the explicitly configured path;
* a durable append is refused **before any byte is committed** when the canonical
  factory could not deserialize the record it would write, so a successful save by
  this build is always readable by this build after a restart;
* reading re-validates every record through the canonical factory and recomputes
  its fingerprint, so a tampered, truncated, malformed, unsupported-version or
  duplicated record raises `AgentRuntimeEventPersistenceCorruptionError`;
* every malformed stored container shape — including a non-mapping `payload` or
  `payload.data` — surfaces as that canonical corruption error, never as an
  incidental `AttributeError`;
* `payload.raw` is round-tripped faithfully, so the content-bound fingerprint of a
  reloaded record matches the fingerprint written with it;
* corrupt evidence is never silently skipped, repaired or guessed;
* tests use temporary directories only, and the suite redirects
  `CMM_OS_DATA_DIR` so no test can write to a real user data location.

### 8.1 Effective immutability of published canonical facts

A canonical event class is frozen at the top level, and its nested facts
(`payload.data`, `header.metadata`, `header.permissions`) are ordinary containers.
Phase 11.22 therefore treats published canonical facts as **effectively
immutable** at every boundary that hands an event to another party:

* `save()` stores a detached canonical snapshot, and `get()`/`list()`/`query()`
  return detached canonical snapshots, so a caller can never reach the stored
  representation;
* the canonical bus hands **each subscriber** (normal delivery and replay) its own
  detached snapshot, so one subscriber cannot change what a later subscriber
  observes;
* the dead-letter record holds a detached snapshot of the canonical facts, and
  every dead-letter retrieval/inspection path (`get()`, `list()`, `remove()`,
  `EventSystem.list_dead_letters()`) returns its own detached snapshot, so a
  caller cannot change the queue's retained evidence;
* normalization deep-detaches every nested container, so a caller cannot mutate a
  published canonical event through an alias it still holds;
* the publication result therefore keeps the same facts it reported.

The detached snapshot is canonically equal to the original: it serializes to the
same canonical dictionary and therefore to the same content fingerprint, and the
canonical payload and metadata shapes are settled **before** the canonical event is
constructed — a mapping becomes a plain `dict`, a supported sequence becomes a plain
`list`, and a scalar is an approved finite descriptive scalar. One semantic fact
therefore has exactly one shape live, persisted, reopened and replayed: a tuple
would otherwise reopen from durable JSON as a `list`. No second event contract is
introduced; the helper lives on the one canonical contract module.

Resulting invariants:

```text
LIVE_EVENT_FACTS_STABLE_AFTER_DELIVERY
FILE_LIVE_AND_REOPENED_FACTS_MATCH
SAFE_NESTED_MAPPING_PUBLICATION
SAFE_NESTED_SEQUENCE_PUBLICATION
PUBLICATION_RESULT_ALIAS_ISOLATION
FINGERPRINT_STABLE_AFTER_PUBLICATION
```

## 9. Duplicate and conflict semantics

Identity-based **and** content-bound:

```text
same event ID + same canonical fingerprint  -> idempotent duplicate
                                            -> no second record
                                            -> no second normal delivery
same event ID + different canonical content -> AgentRuntimeEventIdentityConflictError
                                            -> fail closed
                                            -> no mutation
```

## 10. Ordering guarantees (and non-guarantees)

Guaranteed:

* publication order inside one canonical process;
* FIFO delivery per the existing bus contract;
* deterministic subscriber priority (ascending `priority`, insertion order within
  an equal priority);
* append order in the durable repository;
* deterministic stored-evidence order for replay.

**Not** claimed, and asserted absent from the Phase 11.22 source: distributed
total ordering, cross-device/global ordering, exactly-once execution across
processes, transactional ordering with external systems, consensus or
replication. Phase 11.22 is synchronous and local-first; no async bus, worker,
queue, thread pool, circuit breaker or recovery framework was added.

## 11. Retry semantics

* retries are **per subscriber**;
* the default is the historical Phase 9 behaviour: `max_delivery_attempts = 1`,
  exactly one attempt, so legacy direct bus use is unchanged;
* the composed Phase 11.22 system configures a finite attempt count explicitly;
* subscriber A succeeding and subscriber B failing leaves A successful and
  retries only B;
* every attempt preserves the same event ID and creates no new event;
* `retry_total` counts retries, not initial attempts: a subscriber that fails once
  and then succeeds reports one retry, and a first-attempt success reports none;
* a successful retry produces no dead-letter entry;
* exhaustion produces **exactly one** dead-letter record;
* a subscriber is never given a second *normal* delivery for the same event.

## 12. Dead-letter semantics

A dead-letter entry means: a canonical event was persisted but one specific
subscriber delivery could not complete within the bounded policy.

Preserved safe references: event ID, event type, subscription/subscriber ID,
attempt count, final status, safe error **type**, and timestamps. The raw
exception message is never persisted — the entry stores the exception class name
and a safe category only, and no traceback text.

A dead-letter entry is **subscriber-specific**. `replay_dead_letter()` therefore
targets the `subscription_id` recorded on that entry through the one canonical
replay owner:

```text
DLQ entry for subscriber A
-> replay only to A
-> remove the entry only if A itself accepts replay and succeeds
-> leave the entry intact otherwise
-> never let an unrelated replay-enabled subscriber resolve A's entry
```

A target that did not opt in with `accept_replay=True` leaves the entry
unresolved: the dead-letter API does not bypass replay policy. No second replay
engine and no broadcast DLQ replay exists.

## 13. Replay semantics

Replay is **event-notification** replay, never business-command replay.

* reads canonical stored events and preserves event identity, correlation,
  causation and facts;
* deterministic stored order; honours request filters and `limit`;
* supports dry-run with zero subscriber invocation;
* appends no duplicate record and mutates no original record;
* delivers only to replay-authorised subscribers;
* reports `replayed_count` / `failed_count` deterministically, and treats "no
  subscriber was authorised" as *not replayed* so a dead-letter entry stays
  unresolved;
* grants no permission and bypasses no command authority.

The canonical replayer changed behaviour compatibly: it no longer attempts to
re-save an already-stored event (the previous behaviour could only ever fail and
was never replay). With no bus bound it reports the selected stored evidence; the
legacy Phase 9 replay tests were updated to the corrected semantics.

## 14. Replay opt-in rule

`AgentRuntimeEventSubscription.accept_replay` (additive, optional) defaults to
`False`.

```text
accept_replay=False -> replay skips the subscriber
accept_replay=True  -> the subscriber may receive replay
```

Normal publication is unaffected. No legacy subscriber is ever silently upgraded
to replay-enabled, so historical replay cannot re-run mutations, approvals, tool
calls, provider calls, workflow operations, memory writes or external effects.

## 15. Security and privacy policy

One gate, composed from the strongest existing closed-phase vocabulary (the
Phase 11.2 forbidden-key rule, Phase 10.33's high-confidence credential detector
and forbidden private-marker vocabulary) plus a Phase 11.22 structural allowlist.
No third competing policy exists.

Allowed: IDs and references, categorical states, bounded counts/durations,
versions, timestamps in their canonical string form, and boolean lifecycle facts.

Rejected **before** durable persistence: prompts, system/developer prompts, raw
user text, chain-of-thought, hidden/raw reasoning, provider request/response
payloads, credentials, API keys, passwords, tokens, bearer-shaped values,
authorization headers, cookies, raw tracebacks, opaque runtime objects, arbitrary
binary payloads, non-finite floats and any unrecognised payload key.

The allowlist carries the **value semantics** of every approved key, not only its
name. One canonical `PAYLOAD_KEY_CLASSES` specification in the existing safety
module assigns each allowed key exactly one explicit lifecycle value class, and a
regression asserts that the union of those classes equals the allowlist, so no
approved key can fall through to unrestricted arbitrary prose:

| Class | Meaning |
| --- | --- |
| identifier / reference | a bounded single-token value (`request_id`, `execution_id`, `domain_id`, `producer`, …) |
| category / token | a bounded token form, narrower than an identifier (`status`, `state`, `intent`, `route`, `channel`, `policy`, `error_code`, `sensitivity`, `event_type`, …) |
| boolean | a real `bool` (`approved`, `needs_clarification`, `is_success`) |
| integer / count / duration | a real integer count, or a real finite integer/float duration, inside an explicit bound (`duration_ms`, `count`, `attempts`, `sequence`) |
| version | a bounded number or bounded version token (`version`, `schema_version`) |
| timestamp | the canonical ISO-8601 string form only, and a real calendar/time value (`occurred_at`, `emitted_at`) |
| structured reference | a documented nested shape (`result_reference`, `approval_refs`) |
| reference sequence | a bounded sequence of domain/capability references (`supporting_domains`, `related_domain_ids`, `reason_codes`) |

An approved key name is therefore never a substitute for the fact it claims to
represent: raw user text cannot be relocated into `request_id`, `status`,
`approved`, `duration_ms` or any other approved key merely because the key is on
the list. The identifier rule and the categorical rule are both narrow enough to
exclude prose — any value containing whitespace cannot qualify — and unsafe values
are rejected rather than truncated.

Metadata is likewise not a prose side channel. `METADATA_KEY_CLASSES` admits only
the bounded lifecycle metadata keys current Phase 11.22 producers, adapters and
closed-phase contracts actually use (`status_code`, `attempt`, `origin`, `reason`,
`error_type`, `category`, `replay`, `flag`, `label`, `ratio`, `count`, `detail`),
each with its own bounded value class, and an unknown metadata key fails closed
instead of becoming a new mirroring path. A bounded metadata container is itself
validated recursively against its documented nested shape.

Binary/buffer classification is **semantic**, not a hand-written list of a few
Python classes. A value is binary when the interpreter can expose its raw bytes as
an unsigned byte view, so `bytes`, `bytearray`, `memoryview` and every
`array.array` typecode fail closed before any generic sequence handling. A binary
buffer can therefore never be canonicalized into an integer array, in any payload
or metadata position, including nested inside a structured reference.

The structural half of that policy applies to **every persisted container**, not
only `payload.data`. `metadata` is recursively judged by the same descriptive
JSON-safe rule — an opaque runtime object, a `bytes`/`bytearray` value or a
non-finite float fails closed before anything is persisted, so an object whose
`__str__()` returns a credential can never be stringified into durable evidence by
a serializer. The canonical serialization deliberately does **not** use
`json.dumps(default=str)`, so a value that is not canonically serializable fails
closed instead of being stringified.

### 15.1 Bounded numeric lifecycle facts (Remediation V6)

A numeric lifecycle class called "bounded" must actually be bounded. Remediation
V6 replaced the V5 rule ("is a finite Python number") with one explicit semantic
bound, because the V5 rule left the *interpreter's* integer-to-string limit as the
only obstacle: the same public event carrying `count = 10 ** 5000` was accepted by
the official in-memory repository and raised `ValueError` inside the official
file-backed repository while serializing.

One constant and one small table in the existing safety module define the policy:

```text
MAX_PLATFORM_NUMERIC_FACT = 2 ** 63 - 1   (signed 64-bit machine-integer range)

NUMERIC_FACT_SEMANTICS
  count | attempt | attempts | sequence -> count     integer, 0 <= v <= bound
  duration_ms                          -> duration  integer|float, finite, 0 <= v <= bound
  ratio                                -> ratio     integer|float, finite, 0.0 <= v <= 1.0
  (any other numeric fact)             -> bounded   integer|float, finite, |v| <= bound
```

Nineteen decimal digits is far below every serializer and interpreter conversion
limit and far above every legitimate count, attempt, sequence, millisecond duration
or version this platform produces. `1e308` and every other absurd finite float is
refused; a count-like fact must be a real integer rather than a float; a negative
count, attempt, sequence or duration is refused wherever the current contract
defines it as non-negative. The bound is enforced **before** any repository is
reached, so no repository is responsible for discovering an invalid platform number
and the two official repositories cannot diverge. `ratio` follows the normalized
`0.0 <= ratio <= 1.0` contract current producers actually publish.

### 15.2 Non-public filesystem locations (Remediation V6, extended by V7 and V8)

The identifier character set deliberately keeps `:`, `/` and `.` because
legitimate platform references need them (`workflow:123`, `domain:legal`,
`provider/model`). Safe characters are not path safety: Remediation V6 added a
narrow, purely **syntactic** path-safety classification inside the existing
identifier/header safety authority, because `file:///Users/alice/.ssh/id_rsa`,
`Users/alice/.ssh/id_rsa` and `C:/Users/alice/.ssh/id_rsa` all qualified as
identifiers and were durably persisted — including in the canonical header
`producer` fact — although the frozen design prohibits "filesystem secrets/paths
where not public-safe".

The classifier fails closed on strong filesystem signatures only:

```text
file: URI scheme
Windows drive-root path (C:/…, C:\…) and UNC share (\\server\share)
absolute POSIX path and the ~ home shorthand
a user-home directory segment (Users/, home/, Documents and Settings/)
a known secret-bearing private directory segment (.ssh, .aws, .gnupg, .kube,
  .docker, .azure, .netrc, .pgpass, .npmrc, .git-credentials)
a private key material file name (id_rsa, id_dsa, id_ecdsa, id_ed25519, known_hosts)
```

It performs no content inspection, resolves no path and performs no I/O. The rule
applies on every persisted identifier channel — `payload.data` identifiers,
canonical header identifier facts, `permissions` entries and identifier-classified
metadata facts — while `workflow:123`, `domain:legal`, `provider/model`,
`cmm.orchestration`, `CORR-ORIGINAL` and every other genuine public reference stay
valid.

Absolute-path classification alone was incomplete, so Remediation V7 extended the
**same** classifier rather than adding a second path policy:

```text
a syntactic .. traversal segment delimited by / or \ (or bounding the whole token)
a known sensitive system file in relative form (etc/shadow, etc/passwd, etc/sudoers)
the macOS private system roots in relative form (private/var, private/etc,
  private/tmp, private/root)
```

The traversal rule matches the **segment**, never a naive `".." in value`
substring, so `cmm.orchestration`, `v1..2` and `provider/model` stay valid;
`safe/../../etc/shadow` and `foo/../bar/../../private/var` do not. Both separator
characters are accepted in any mix: the identifier grammar only admits `/`, but a
Windows spelling is a filesystem path semantic too. The relative sensitive-system
file pattern also refuses the network spelling `nfs://server/etc/shadow`. There is
still no filesystem I/O and no host path resolution: the requirement is about the
*public-safety of the token*, not about the host's filesystem.

The classifier also answers this question through the public
`is_private_filesystem_reference()` predicate, which is the same function
`validate_platform_identifier()` calls.

### 15.3 One canonical header fact authority (Remediation V6)

A canonical header fact has exactly one authority. Remediation V6 closed the case
where a payload key with the same name was validated independently and persisted
alongside the header, so `header.event_id=header-event` and
`payload.event_id=payload-event` — and, critically,
`header.sensitivity=internal` alongside `payload.sensitivity=restricted` — were
durably stored together.

```text
CANONICAL_HEADER_PAYLOAD_KEYS =
    ALLOWED_PAYLOAD_KEYS ∩ CANONICAL_HEADER_FACT_KEYS
  = event_id, event_type, schema_version, occurred_at, emitted_at, agent_id,
    goal_id, workflow_id, task_id, correlation_id, causation_id, aggregate_id,
    producer, sensitivity
```

Every one of those payload keys is consumed into the canonical header before
persistence and is **not** persisted as a second platform payload fact:

* an unset header fact takes the payload value, so a source dictionary that carries
  the fact reaches the one canonical authority instead of a duplicate;
* a header fact equal to the payload value is left exactly as it is;
* a contradictory header fact and payload value fail closed before anything is
  persisted;
* `sensitivity` is the one documented non-equal resolution: the canonical header
  keeps the **stricter** classification, so a stricter source value is promoted into
  the header and a lower payload classification can never downgrade it;
* an explicit `None` for an optional reference (`workflow_id=None`) is not a
  reference value: there is nothing to adopt and nothing to contradict.

The intersection is deliberate: a payload key outside the bounded payload
vocabulary is still rejected by the ordinary gate rather than becoming a new header
channel, so the closed vocabulary stays closed. The Domain/Kernel bridge keeps its
canonical class mapping; `domain.execution.completed` with `sensitivity=restricted`
still reaches `header.sensitivity=RESTRICTED`. The kernel adapter no longer mirrors
the *source* event name into a payload `event_type` key — the canonical header owns
that fact, and the one-way source→platform mapping stays recorded in the committed
translation table.

### 15.4 Timestamp semantics (Remediation V6)

The "canonical ISO-8601" timestamp class validated text shape rather than civil
time, so `9999-99-99T99:99Z`, `2026-02-31T12:00Z` and `2026-09-27T25:61Z` reached
durable evidence, as did a timezone-less `2026-09-27T12:00` even though the
canonical chronology contract is timezone-aware.

The existing shape rule is retained, and the value must additionally parse as a
real calendar/time value and carry an explicit UTC offset. No second timestamp
subsystem was introduced and the existing canonical serialization is reused: an
invalid value fails closed instead of being silently reinterpreted or normalized,
and a valid timezone-aware value (`2026-09-27T12:00:00Z`,
`2026-09-27T12:00:00+02:00`) keeps its documented canonical string form.

Remediation V9 removed the one remaining interpreter dependency from that rule.
CPython 3.14 widened `datetime.fromisoformat()` to accept the ISO end-of-day
spelling `24:00` and roll it into the next day, so `2026-09-27T24:00:00Z` was
accepted and durably persisted on the canonical runtime although the frozen
contract admits only hours `00..23`, and the retained V6 regression case failed.
The frozen hour range is now asserted explicitly, on the value's own text and
before the parser is consulted:

```python
MAX_PLATFORM_CIVIL_HOUR = 23
_TIMESTAMP_CIVIL_TIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}[T ](?P<hour>\d{2}):")
```

The guard is deliberately limited to the hour bound, because that is the only
civil bound the canonical parser demonstrably widened: hour `25`, minute `60`,
second `60`, month `13`, day `32`, a fractional end-of-day value and an
out-of-range UTC offset are all still refused by `fromisoformat()` itself. No
second timestamp parser, no wider parser rewrite, and no change to the accepted
shape, the timezone-awareness requirement or the canonical serialization.

`sensitivity` is a real runtime-enforced classification: the persisted fact is an
`EventSensitivity` member, and the single supported string spelling of a canonical
member is normalized to that enum before the event is constructed. A number,
`None`, an arbitrary object, an unknown label or a credential-bearing/private-marker
string fails closed. `permissions` is validated as a structural sequence **before**
any factory coercion, so a plain string can never be iterated into a character list.

Invariants:

```text
EVENTS_GRANT_NO_AUTHORITY
REPLAY_GRANTS_NO_AUTHORITY
UNKNOWN_PLATFORM_EVENT_TYPE_FAILS_CLOSED
PROMPTS_NEVER_ENTER_ANY_PERSISTED_EVENT_FIELD
HIDDEN_REASONING_NEVER_ENTERS_ANY_PERSISTED_EVENT_FIELD
CREDENTIALS_NEVER_ENTER_ANY_PERSISTED_EVENT_FIELD
RAW_PROVIDER_PAYLOADS_NEVER_ENTER_ANY_PERSISTED_EVENT_FIELD
OPAQUE_VALUES_NEVER_ENTER_ANY_PERSISTED_EVENT_FIELD
BINARY_VALUES_NEVER_ENTER_ANY_PERSISTED_EVENT_FIELD
BINARY_BUFFER_VALUES_FAIL_CLOSED
BINARY_BUFFER_VALUES_NEVER_BECOME_INTEGER_ARRAYS
NONFINITE_NUMBERS_NEVER_ENTER_ANY_PERSISTED_EVENT_FIELD
RAW_USER_TEXT_CANNOT_BE_RELOCATED_INTO_LIFECYCLE_FIELDS
METADATA_IS_NOT_A_PROSE_SIDE_CHANNEL
IDENTIFIER_FIELDS_ARE_SEMANTICALLY_BOUNDED
CATEGORICAL_FIELDS_ARE_SEMANTICALLY_BOUNDED
BOOLEAN_FIELDS_REQUIRE_BOOLEAN_VALUES
NUMERIC_FIELDS_REQUIRE_NUMERIC_VALUES
NUMERIC_LIFECYCLE_FACTS_ARE_ACTUALLY_BOUNDED
NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE
PATH_EQUIVALENT_SPELLINGS_HAVE_IDENTICAL_SAFETY_CLASSIFICATION
URI_USERINFO_CREDENTIALS_REJECTED_REGARDLESS_OF_PREFIX_OR_WRAPPER
ONE_CANONICAL_HEADER_FACT_AUTHORITY
NO_HEADER_PAYLOAD_SENSITIVITY_CONFLICT
TIMESTAMP_SEMANTIC_VALIDITY
PHASE11_22_TIMESTAMP_ACCEPTANCE_IS_INTERPRETER_VERSION_INDEPENDENT
WRAPPED_FILE_URI_REFERENCES_HAVE_THE_SAME_UNSAFE_CLASSIFICATION_AS_TOP_LEVEL_FILE_URI_REFERENCES
LIFECYCLE_FACT_ONLY_POLICY
DLQ_SECRET_SAFETY_FAILS_SAFE_WITHOUT_EXTERNAL_BINDING
CANONICAL_SENSITIVITY_TYPE_ENFORCED
INVALID_PERMISSION_CONTAINER_FAILS_CLOSED
SOURCE_SENSITIVITY_IS_NOT_DOWNGRADED
CORRUPT_PERSISTED_EVENTS_FAIL_CLOSED
SAME_ID_DIFFERENT_CONTENT_FAILS_CLOSED
REPLAY_TO_SIDE_EFFECT_SUBSCRIBERS_DEFAULT_DENIED
DLQ_REPLAY_CANNOT_BYPASS_SUBSCRIBER_POLICY
```

The boundary is **universal, never route-dependent and never channel-dependent**.
`EventSystem.create_event()`, `EventSystem.publish()` and the public
`EventSystem.publish_event()` all enforce canonical registry membership, the
bounded payload vocabulary, the raw-payload prohibition and the same safety policy
for **every persisted free-form header fact** before anything is persisted, so
forbidden material can neither choose a lower-level entry point nor be relocated
from `payload.data` into `metadata`, `permissions`, `producer`, `aggregate_id`,
`source` or another persisted identifier field. A persisted identifier is a
bounded single-token value that additionally survives the credential/private-marker
scan, the occurrence-independent URI userinfo credential rule and the non-public
filesystem classifier, which classifies the pure lexical canonical analysis form of
the reference (absolute signatures, `..` traversal segments, relative private system
roots, and — since Remediation V8 — a fail-closed public-reference allowlist against
which every lexically equivalent spelling of one location receives one verdict); a
persisted `metadata`/`permissions` key is itself content and is judged by
the same canonical key rule the Phase 10.33 Domain authority applies to its own
payload and metadata keys. The durable Phase 9 repository stays a generic
persistence contract and is deliberately not turned into a Phase 11.22
platform-policy authority; it does, however, refuse to append a record this build
could not reopen.

The kernel adapter additionally fails closed on **forbidden, private or
credential-bearing source content** even for source keys it does not model, while
harmless irrelevant source facts are still ignored. The one documented exception
is the structural source envelope name `payload`, which closed-phase contracts use
as a container; the container's contents are still fully scanned, and only facts an
explicit translation names may ever be read from it. Explicit source
`correlation_id` and `causation_id` are preserved unchanged, the documented
derivation order is used only when the source carries none, and an explicit source
sensitivity classification is preserved without downgrade.

### 15.5 URI userinfo credentials (Remediation V7)

The identifier grammar deliberately admits `:`, `/` and `@` because legitimate
references need them, so URI authority syntax must be classified semantically
rather than character by character. Remediation V7 added one narrow check to the
**same** authority — not a second credential policy:

```text
<scheme>://<name>:<secret>@<authority>
```

`contains_uri_userinfo_credential()` requires a real scheme, a `//` authority,
userinfo terminated by `@`, and a colon inside that userinfo with a non-empty
password component. It percent-decodes the userinfo (`urllib.parse.unquote`) before
the colon test, so an encoded `%3A` that decodes to a password separator is refused
as the same credential. The function returns a boolean and the caller's rejection
message is a static literal, so the refused secret is never echoed into a log, an
error or a DLQ record.

Credential-free URIs stay valid (`https://example.com/model`,
`postgres://example.com/db`, `http://localhost:8080/health`,
`urn:cmm:event:message.received`, `mailto:ops@example.com`), and so does
bare-username userinfo with no password component. A password with an empty
username (`https://:secret@example.com/db`) is still a password and is refused.

### 15.6 The lexical path-analysis form and the fail-closed reference allowlist (Remediation V8)

Remediation V6 and V7 built the filesystem classifier as a tuple of patterns
matched against the **raw identifier text**. Independent Re-audit V8 showed that
this made it a list of selected spellings rather than a classification:

```text
etc/shadow                                 refused
etc//shadow                                ACCEPTED and durably persisted
etc/./shadow                               ACCEPTED and durably persisted
private/var/db/keychains                   refused
safe/private/./var/db/keychains            ACCEPTED and durably persisted
proc/self/environ                          ACCEPTED and durably persisted
Windows/System32/config/SAM                ACCEPTED and durably persisted
Library/Keychains/login.keychain-db        ACCEPTED and durably persisted
```

Two changes fix the class, not the examples, inside the **existing** identifier
safety authority.

**1. A pure lexical canonical analysis form.** `_analyze_lexical_path()` is a pure
string transformation used only for safety classification. It normalizes `\` and
`/` to one separator, collapses repeated separators, elides `.` current-directory
segments and *detects* — never elides — a `..` parent segment, so traversal is
refused before any normalization could hide it. It performs no filesystem I/O, no
host resolution and no `Path.resolve()`, and it never mutates the identifier value
that is persisted: the canonical form exists only inside the analysis, and a
producer that publishes `provider//model` still stores exactly `provider//model`.

**2. A fail-closed public-reference allowlist.** Classification then runs on the
canonical form, so lexically equivalent spellings receive one identical verdict:

```text
etc/shadow, etc//shadow, etc/./shadow, ETC/SHADOW, safe/../etc/shadow
    -> all refused, because they share the canonical form "etc/shadow"
```

A slash-bearing reference is public-safe only when its path-shaped **residue** is
one of:

```text
empty — the value is nothing but credential-free authority-bearing URI
         references (scheme://…), exempted only for the span they cover; or
rooted in a declared public logical namespace
```

The residue is what remains once every authority-bearing URI reference is removed
from the value. A value is **not** exempted merely because a `://` occurs inside
it: under POSIX path semantics `a://x` names `a/x`, so `proc/self/environ://x`,
`etc/shadow://x` and `Windows/System32/config/SAM://x` are refused exactly as their
plain spellings are. Credential-free wrapped URIs still leave a clean residue
(`jdbc:postgresql://example.com/db` leaves `jdbc:`, which carries no separator, and
`provider/https://example.com/db` leaves `provider/`, whose root is declared).

The declared namespaces are the small set a **real inventory** of every identifier
value the whole suite routes through this shared authority found in use —
`provider/model` and `cmm/orchestration/step` — so
`PUBLIC_SLASH_REFERENCE_ROOTS = {cmm, provider}`. Every other slash-bearing
spelling fails closed by default rather than being trusted for being absent from a
pattern list, which is why `proc/self/environ`, `Windows/System32/config/SAM` and
`Library/Keychains/login.keychain-db` are refused without a pattern being appended
for them. The retained V6/V7 pattern tuple is unchanged in content and is now
evaluated against the canonical form; it is explicitly **not** how the classifier
is kept correct.

A reference that carries no separator at all is not path-shaped and is not
classified here. A wrapped `file:` authority (`x:file:///…`) is the same local
location as a top-level one and is refused. Credential-free URIs survive, while a
password-bearing authority is refused by the one userinfo rule below — so the
rejection reason stays accurate rather than being reported as a path violation.

Invariants:

```text
PATH_EQUIVALENT_SPELLINGS_HAVE_IDENTICAL_SAFETY_CLASSIFICATION
NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE
```

### 15.7 Occurrence-independent URI userinfo credentials (Remediation V8)

The V7 check recognized the userinfo password structure only when the
authority-bearing URI began at character zero, so the whole wrapper family was
durably persisted:

```text
jdbc:postgresql://alice:supersecret@example.com/db
jdbc:mysql://root:hunter2hunter2@example.com/db
provider/https://alice:supersecret@example.com/db
foo:https://alice:supersecret@example.com/db
```

`contains_uri_userinfo_credential()` is still one narrow check in the same
authority — no second credential subsystem — but it is now
**occurrence-independent**: it scans every authority-bearing `://` occurrence in
the reference, splits each authority at its last `@` (where RFC 3986 ends the
userinfo), percent-decodes that userinfo and splits it at the first `:`. A
non-empty password component means the reference is credential material. A
credential that appears only in a *later* authority is therefore seen too.

Credential-free references are untouched, including credential-free wrapped URIs
(`jdbc:postgresql://example.com/db`, `provider/https://example.com/db`),
bare-username userinfo (`https://alice@example.com/db`) and an empty password
(`https://alice:@example.com/db`). The function returns a boolean and the caller's
rejection message remains a static literal, so the refused secret is never echoed
into a log, an error or a DLQ record. The percent-decoding regression is retained
at helper level even though the outer identifier grammar excludes `%`.

Invariants:

```text
URI_USERINFO_CREDENTIALS_REJECTED_REGARDLESS_OF_PREFIX_OR_WRAPPER
CREDENTIALS_NEVER_ENTER_EVENT_PERSISTENCE
```

### 15.8 Wrapped non-authority `file:` references (Remediation V9)

The V6–V8 classifier recognized a `file:` reference only as an **authority-bearing**
URI (`scheme://authority`) or at character zero (`^file:`). The outer identifier
grammar admits a public logical wrapper, and the V8 fail-closed allowlist accepted
that wrapper, so a *non-authority* `file:` reference carried by it was never
classified and was durably persisted across every shared identifier channel,
through both official repositories and through a manual `publish_event(...)` call:

```text
provider/file:C:/Windows/System32/config/SAM
cmm/file:C:/Windows/System32/config/SAM
provider/file:C:/Windows/System32/config/SECURITY
provider/file:/Windows/System32/config/SAM
provider/file:C:/ProgramData/Microsoft/Crypto/RSA/MachineKeys
provider/file:/Library/Keychains/login.keychain-db
```

The one canonical fix anchors the **existing** `file:` signature at a path *segment*
boundary instead of at character zero, inside the same
`_PRIVATE_FILESYSTEM_PATTERNS` tuple and the same classifier:

```python
re.compile(r"(?:^|/)file:", re.IGNORECASE)
```

The pattern is evaluated against the canonical lexical analysis form whose segments
are joined by `/`, so a segment boundary is exactly where the identifier grammar can
carry a scheme token — even when the wrapper is repeated (`provider//file:`), uses a
`.` segment (`provider/./file:`) or varies case (`PROVIDER/FILE:`) — and `file` is a
case-insensitive URI scheme. No literal was appended for any audited filename or
location, so an unnamed wrapped location (`provider/file:/boot/grub/grub.cfg`) is
refused by the same structural rule. The rule stays analysis-only: no filesystem
I/O, no host resolution, no `Path.resolve()` and no rewriting of an accepted
persisted identifier.

Top-level `file:` refusals, credential-free network URIs, logical slash references
(`provider/model`, `cmm/orchestration/step`) and colon-bearing logical identifiers
whose `file` token does not begin a path segment (`workflow:file:123`,
`req:file:mod`) all keep their verdicts. Windows-backslash spellings
(`provider/file:C:\Windows\…`) are refused earlier by the identifier character set;
that is a positive fail-closed fact and the grammar was not widened for them.

Invariants:

```text
WRAPPED_FILE_URI_REFERENCES_HAVE_THE_SAME_UNSAFE_CLASSIFICATION_AS_TOP_LEVEL_FILE_URI_REFERENCES
NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE
PATH_EQUIVALENT_SPELLINGS_HAVE_IDENTICAL_SAFETY_CLASSIFICATION
```

### 15.9 Wrapped raw Windows drive-root references (Remediation V10)

Remediation V9 anchored the `file:` signature at a path-segment boundary, but the
structurally identical **raw Windows drive-root** signature was left anchored at
character zero (`^[A-Za-z]:[\\/]`). Because `provider` and `cmm` are declared public
slash roots (`PUBLIC_SLASH_REFERENCE_ROOTS`), an allowlisted wrapper could carry a
raw local drive past the classifier:

```text
provider/C:/Windows/System32/config/SAM
cmm/C:/Windows/System32/config/SAM
provider//C:/Windows/System32/config/SAM
provider/./C:/Windows/System32/config/SAM
provider/C:/Windows/System32/config/SECURITY
```

Each was classified as public-safe, admitted by `validate_platform_identifier()`,
published by the canonical `EventSystem` and durably appended — across all 13 shared
identifier-bearing channels, in both official repositories and through a manual
`publish_event(...)` call.

The one canonical fix anchors the **existing** drive-root signature at a path
*segment* boundary, inside the same `_PRIVATE_FILESYSTEM_PATTERNS` tuple and the same
classifier:

```python
re.compile(r"(?:^|/)[A-Za-z]:[\\/]")
```

Because the pattern is evaluated against the canonical lexical analysis form whose
segments are joined by `/`, a segment boundary is exactly where the identifier
grammar can carry a drive token — including when the wrapper is repeated
(`provider//C:/`), uses a `.` segment (`provider/./C:/`), varies case
(`Provider/C:/`) or the drive letter is lowercase (`provider/c:/`) — and the rule
still requires real drive-root syntax: a letter, a colon **and** a path separator. No
literal was appended for `SAM`, `SECURITY`, `Windows`, `System32`, `ProgramData`,
`MachineKeys` or any audited drive letter, so fresh unwrapped-audit probes
(`provider/D:/private/example`, `cmm/Z:/tmp/example`, `cmm/E:/ProgramData/Example/…`,
`provider/A:/boot/grub/grub.cfg`) are refused by the same structural rule.

Top-level drive-root refusals (`C:/Windows/System32/config/SAM`, `D:/private/example`,
`c:/Windows/…`), logical slash references (`provider/model`,
`cmm/orchestration/step`), ordinary colon identifiers (`workflow:123`,
`domain:legal`), segment-boundary non-drive colons (`provider/a:1/model`,
`cmm/v2:3/detail`) and credential-free URIs (`https://example.com/model`,
`http://localhost:8080/health`, `jdbc:postgresql://example.com/db`,
`provider/https://example.com/model`) all keep their verdicts, as do the V9
`file:`-token-as-logical-scheme controls (`workflow:file:123`, `req:file:mod`). The
rule stays analysis-only: no filesystem I/O, no host resolution, no
`Path.resolve()` and no rewriting of an accepted persisted identifier. Windows
drive-root **backslash** spellings (`C:\Windows\…`) are refused earlier by the
identifier character set; that is a positive fail-closed fact and the grammar was not
widened for them.

Invariants:

```text
WRAPPED_WINDOWS_DRIVE_ROOT_REFERENCES_HAVE_THE_SAME_UNSAFE_CLASSIFICATION_AS_TOP_LEVEL_DRIVE_ROOT_REFERENCES
NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE
PATH_EQUIVALENT_SPELLINGS_HAVE_IDENTICAL_SAFETY_CLASSIFICATION
```

### 15.10 Windows drive-relative references (Remediation V11)

Windows defines both a drive-*root* path and a drive-*relative* path:

```text
C:/name     drive-root path
C:name      drive-relative path
```

The second form is still a drive-qualified local filesystem reference — it resolves
against that drive's current directory. The standard library confirms the syntax
lexically:

```text
ntpath.splitdrive("C:Windows") = ("C:", "Windows")
ntpath.splitdrive("C:id_rsa")  = ("C:", "id_rsa")
```

The V10 drive rule required a path separator after the colon, so no canonical
signature recognized the drive-relative spelling; and because a value such as
`C:id_rsa` contains no separator at all, the final path-shape branch also declined to
treat it as path-shaped and returned "not a private filesystem reference". The
following were therefore classified as public-safe, admitted by
`validate_platform_identifier()`, published by the canonical `EventSystem` and
durably appended — across all 13 shared identifier-bearing channels, in both official
repositories and through a manual `publish_event(...)` call:

```text
C:Windows
C:id_rsa
C:.ssh
D:ProgramData
Z:tmp
```

`id_rsa` was already a sensitive private-file marker in `_PRIVATE_FILESYSTEM_PATTERNS`,
so the drive-designator colon was shielding a known private location. Remediation V11
is a one-line structural classification of the drive **designator** inside the same
`_PRIVATE_FILESYSTEM_PATTERNS` tuple and the same classifier:

```python
re.compile(r"^[A-Za-z]:")
```

The rule is anchored to the **start of the whole reference** rather than to a
path-segment boundary, for two reasons that the frozen contract makes mandatory:

* drive-relative syntax only has that meaning at the start of a path;
* the contract deliberately preserves wrapped *segment-colon* logical identifiers
  (`provider/a:1/model`, `provider/x:0/step`, `cmm/v2:3/detail`,
  `cmm/orchestration:step`), whose colon sits inside an allowlisted public logical
  wrapper. A segment-boundary rule would refuse them.

The retained V10 segment-boundary drive-root signature is unchanged, so a *rooted*
drive token carried by an allowlisted wrapper (`provider/C:/Windows/…`, the whole V10
family) keeps its audited verdict. The rule is evaluated on the canonical lexical
analysis form **before** any separator heuristic or the generic "no separator means
not path-shaped" escape, so the bare designator (`C:`, the drive's current
directory), lowercase drive letters (`c:id_rsa`) and unnamed drives and remainders
(`C:a`, `X:foo.bar`, `E:secret.txt`) receive the identical verdict. No literal was
appended for `Windows`, `ProgramData`, `id_rsa`, `.ssh` or `tmp`, no filesystem I/O
and no `Path.resolve()` is used, no identifier grammar was widened, and no accepted
identifier is rewritten. Multi-letter colon identifiers (`workflow:123`,
`domain:legal`, `events:read`), wrapped segment-colon logical identifiers
(`provider/a:1/model`, `cmm/v2:3/detail`), the V9 `file:`-token-as-logical-scheme
controls (`workflow:file:123`, `req:file:mod`), plain slash references
(`provider/model`, `cmm/orchestration/step`) and credential-free URIs
(`https://example.com/model`, `provider/https://example.com/model`,
`jdbc:postgresql://example.com/db`) all keep their verdicts. Windows drive-relative
**backslash** spellings (`C:\Windows`) are refused earlier by the identifier
character set; that is a positive fail-closed fact and the grammar was not widened
for them.

Invariants:

```text
WINDOWS_DRIVE_RELATIVE_REFERENCES_NEVER_ENTER_EVENT_PERSISTENCE
WINDOWS_DRIVE_DESIGNATOR_PATHS_ARE_CLASSIFIED_BEFORE_SEPARATOR_HEURISTICS
NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE
PATH_EQUIVALENT_SPELLINGS_HAVE_IDENTICAL_SAFETY_CLASSIFICATION
```

## 16. Composition bindings

One Phase 11.1 module, `phase11_22_events`, owned by `cmm.events`, contributing
seven service bindings:

| Service ID | Runtime contract |
| --- | --- |
| `event.registry` | `AgentRuntimeEventRegistry` |
| `event.repository` | `AgentRuntimeEventRepository` |
| `event.bus` | `AgentRuntimeEventBus` |
| `event.replayer` | `AgentRuntimeEventReplayer` |
| `event.dead_letter_queue` | `InMemoryAgentRuntimeDeadLetterQueue` |
| `event.orchestration_sink` | `OrchestrationEventSink` |
| `event.system` | `EventSystem` (authority `platform-event-delivery-coordinator`) |

The frozen Phase 11.2 `orchestration.event_sink` identity stays owned by the
Phase 11.2 composition module, which binds the **same** Phase 11.22 production
adapter object and declares it as the Orchestrator's sink. So the Orchestrator
receives the real platform sink through existing composition, no service identity
is claimed twice, and no second container, composition root or service locator is
introduced. Nothing is registered at import time and there is no module-global
event-system singleton.

`build_local_application_runtime()` composes the Phase 11.22 module and event
storage location, so the production local runtime now carries the canonical
graph plus the event-system services.

## 17. `DP-122`

> CMM OS has exactly one canonical in-process event transport authority, reusing
> and hardening the Phase 9 runtime event infrastructure for platform-wide safe
> lifecycle facts. New platform events are validated, content-bound and durably
> appended before normal delivery; identical retries are deduplicated, conflicting
> identities fail closed, local ordering is deterministic, subscriber failures are
> isolated and bounded by retry policy, exhausted deliveries enter the canonical
> dead-letter path, and stored events can be safely replayed only to
> replay-authorized subscribers while preserving event identity, correlation,
> causation, privacy and all pre-existing subsystem authorities.

`DP-122=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION`

## 18. `AT-DP-122`

`tests/events/test_phase11_22_dp122_acceptance.py` — real components only, with no
mock in the core chain:

1. real Phase 11.1 composition including the Phase 11.22 module;
2. exactly one canonical event bus binding;
3. that bus is the Phase 9 `AgentRuntimeEventBus`;
4. real Phase 11.2 Orchestrator through the existing sink seam;
5. a real safe orchestration lifecycle event;
6. explicit mapping to the platform event;
7. canonical factory/registry validation;
8. persistence exactly once;
9. one normal subscriber receives it once;
10. identical republish ⇒ no second persistence, no second delivery;
11. same ID with changed content ⇒ fail-closed identity conflict;
12. one successful and one failing subscriber ⇒ the successful one is unaffected;
13. bounded retries target only the failing subscriber;
14. exhaustion creates exactly one canonical dead-letter record;
15. one replay-disabled and one replay-enabled subscriber;
16. replay of the stored event;
17. the disabled subscriber is not invoked;
18. the enabled subscriber receives the original event ID;
19. replay appends no further repository record;
20. correlation and causation survive replay;
21. unsafe prompt/credential/reasoning payloads are rejected before persistence;
22. Domain Events remain 23/23 and keep their own authority;
23. no second bus/registry/repository/replayer/DLQ authority exists.

Remediation V1 strengthened the same connected acceptance with the adversarial
scenarios independent Audit V1 reproduced, still against real components only:

24. same-ID difference only in `correlation_id` fails as an identity conflict;
25. same-ID difference only in `causation_id` fails as an identity conflict;
26. same-ID difference only in `sensitivity` fails as an identity conflict;
27. same-ID difference only in `metadata` fails as an identity conflict;
28. direct `publish_event()` rejects an unknown event type;
29. direct `publish_event()` rejects a prompt payload;
30. direct `publish_event()` rejects a credential payload;
31. direct `publish_event()` rejects hidden-reasoning content;
32. dead-letter replay cannot be satisfied by another replay-enabled subscriber;
33. targeted dead-letter replay removes the entry only after the failed
    subscriber itself succeeds, and never invokes the unrelated subscriber;
34. explicit Domain `correlation_id` survives the kernel adapter unchanged;
35. explicit Domain `causation_id` survives the kernel adapter unchanged.

Remediation V2 strengthened the same connected acceptance with the scenarios
Independent Re-audit V2 reproduced, still against real components only:

36. unsafe `metadata` (key and value) is rejected before persistence;
37. unsafe `permissions` entries are rejected before persistence;
38. an unsafe `producer` is rejected before persistence;
39. an unsafe `source` is rejected before persistence;
40. an unsafe `aggregate_id` is rejected before persistence;
41. a legitimate identifier/metadata combination still persists;
42. an unsupported schema is rejected before durable append;
43. a supported schema survives close and reopen with equal canonical facts;
44. subscriber A cannot change what subscriber B sees;
45. a subscriber cannot mutate repository evidence;
46. file-backed live and reopened event facts stay equal after a mutation attempt;
47. real `domain.execution.completed` preserves its mapped execution identity and
    status;
48. restrictive Domain sensitivity is not downgraded to the platform default;
49. real Domain approval events preserve their mapped identity and bounded
    resolution facts, and invent no status the source never carried;
50. real `domain.memory.updated` preserves its mapped status;
51. nested forbidden Domain content still fails closed.

`AT-DP-122=PASS_REPORTED`

## 19. Test evidence

Post-remediation (Remediation V2) measurements; the Remediation V1 figures are
preserved in §19.3, the original V1 figures in §19.2 and in the immutable Audit V1
report.

| Gate | Result |
| --- | --- |
| Phase 11.22 focused tests (`tests/events/`) | `893 passed` |
| Remediation V2 adversarial regressions | `126 passed` |
| Remediation V1 adversarial regressions (preserved) | `86 passed` |
| `AT-DP-122` connected acceptance | `64 passed` (see §18) |
| Runtime factory/repository/bus/replay sequence | `277 passed` |
| Phase 10.33 Domain Events (`DP-033` + Domain Event modules) | `930 passed` |
| Orchestration/validation kernel event modules | `33 passed` |
| Security and architecture gates | `294 passed` |
| Event inventory (`tests/**/*event*.py`) | `1270 passed` |
| Closed-phase connected regressions | see §19.1 |
| Phase 9 runtime regressions (`tests/agent_runtime`) | `3635 passed` |
| Global pytest | `22962 passed, 1 warning, 0 failed` |
| Changed/new file Ruff | `PASS` (0 violations) |
| Global Ruff count (`ruff check cmm kernel tests`) | `810` (frozen pre-existing baseline `811`, V2 HEAD `810`, no new debt) |
| Format check (`ruff format --check`, changed-file delta) | `PASS` |
| `compileall -q cmm kernel` | `PASS` |
| `git diff --check` | `PASS` |
| Architecture / security gates | `PASS` |

### 19.1 Closed-phase connected regressions

```text
AT-DP-102   Orchestration Layer                  PASS
AT-DP-103   Application Backend                  PASS
AT-DP-105   Conversational Interface             PASS
Phase 11.21 Model Gateway                        PASS
Phase 11.34 Provider Registry (where affected)   PASS
AT-DP-150   Reusable Backend Interfaces          PASS
Phase 10.33 Domain Events                        PASS
Phase 11.1  Integration Core (platform)          PASS
Phase 7     Continuous Validation                PASS
Phase 9     Autonomous Agent Runtime             PASS
Workflow subsystem                               PASS
```

The closed-phase acceptances (`AT-DP-102`, `AT-DP-103`, `AT-DP-105`, Phase 11.21,
Phase 11.34, `AT-DP-150`) ran as one gate: `218 passed`. Phase 11.1 `DP-101`, the
validation kernel event module and the orchestration event module ran as a
supporting gate: `112 passed`.

One inherited platform architecture gate was extended, not weakened:
`tests/platform/test_architecture.py` sanctions `cmm.events` as the fifth bounded
`cmm.platform` consumer, with the same one-way direction rule and no new platform
authority. One inherited Phase 11.3 acceptance assertion was updated to the
corrected production graph: the production local runtime now composes the
canonical service set **plus exactly the Phase 11.22 event-system services**.

### 19.2 Original V1 measurements (historical)

```text
tests/events/                       489 passed
AT-DP-122                            33 passed
focused event baseline              856 passed
event inventory                    1269 passed
closed-phase regressions        16703 passed
global pytest                   22558 passed, 1 warning
global Ruff                          810 (frozen baseline 811)
```

### 19.3 Remediation V1 measurements (historical)

```text
tests/events/                       625 passed
AT-DP-122                            45 passed
Remediation V1 regressions           86 passed
focused event baseline              972 passed
event inventory                    1270 passed
Phase 9 runtime regressions        3635 passed
Phase 10.33 Domain regressions    11824 passed
closed-phase acceptances            228 passed
global pytest                   22694 passed, 1 warning, 0 failed
global Ruff                          810
```

### 19.4 Remediation V3 measurements (historical)

```text
tests/events/                       956 passed
AT-DP-122                            83 passed
Remediation V3 regressions           44 passed
Remediation V2 regressions          126 passed (preserved)
Remediation V1 regressions           86 passed (preserved)
event inventory                    1270 passed
Phase 9 runtime regressions        3635 passed
Phase 10.33 Domain regressions    11824 passed
closed-phase acceptances            218 passed
closed-phase support                112 passed
global pytest                   23025 passed, 1 warning, 0 failed
global Ruff                          810 (V3 baseline 810, no new debt)
```

The V3 production tree measured `893` in `tests/events/` and `22962` globally.
Both V3 deltas are therefore accounted for exactly: the new V3 regression module
adds `44` and the strengthened `AT-DP-122` adds `19`, so the global suite moves
`22962 → 23025` (`+63`) and `tests/events/` moves `893 → 956` (`+63`), while
`AT-DP-122` itself moves `64 → 83`. The recorded `tests/events/` label was `63`
below its own per-file total; that clerical discrepancy is preserved here as
historical record rather than silently corrected.

### 19.5 Remediation V4 measurements (historical)

```text
tests/events/                       991 passed
AT-DP-122                            95 passed
Remediation V4 regressions           23 passed
global pytest                   23060 passed, 1 warning, 0 failed
global Ruff                          810 (V4 baseline 810, no new debt)
```

The V4 production tree measured `956` in `tests/events/` and `23025` globally.
Both V4 deltas are accounted for exactly: the new V4 regression module adds `23`
and the strengthened `AT-DP-122` adds `12`, so the global suite moves
`23025 → 23060` (`+35`), `tests/events/` moves `956 → 991` (`+35`), and
`AT-DP-122` itself moves `83 → 95`.

### 19.6 Remediation V5 measurements (historical)

```text
tests/events/                      1091 passed
AT-DP-122                           124 passed
Remediation V5 regressions           71 passed
Remediation V4 regressions           23 passed (preserved)
Remediation V3 regressions           44 passed (preserved)
Remediation V2 regressions          126 passed (preserved)
Remediation V1 regressions           86 passed (preserved)
event inventory                    1270 passed
Phase 9 runtime regressions        3635 passed
Phase 10.33 Domain regressions    11824 passed
Closed-phase acceptances            310 passed
Closed-phase support                579 passed
global pytest                   23160 passed, 1 warning, 0 failed
global Ruff                          810 (V5 baseline 810, no new debt)
```

The V4 production tree measured `991` in `tests/events/` and `23060` globally.
Both V5 deltas are accounted for exactly: the new V5 regression module adds `71`
and the strengthened `AT-DP-122` adds `29`, so the global suite moves
`23060 → 23160` (`+100`), `tests/events/` moves `991 → 1091` (`+100`), and
`AT-DP-122` itself moves `95 → 124`. The two deltas are the same `+100` because
the strengthened acceptance scenarios live inside `tests/events/`.

### 19.7 Remediation V6 measurements (current)

```text
tests/events/                      1271 passed
AT-DP-122                           177 passed
Remediation V6 regressions          127 passed (initial red 90 failed / 37 passed)
Remediation V5 regressions           71 passed (preserved)
Remediation V4 regressions           23 passed (preserved)
Remediation V3 regressions           44 passed (preserved)
Remediation V2 regressions          126 passed (preserved)
Remediation V1 regressions           86 passed (preserved)
prior remediation regressions      350 passed (V1-V5, exactly the re-audit figure)
Remediation V1-V6 regressions      477 passed
event inventory                    1270 passed
Phase 9 runtime regressions        3635 passed
Phase 10.33 Domain regressions    11824 passed
Closed-phase acceptances            310 passed
Closed-phase support               1077 passed
Phase 11.21 + 11.34                 106 passed
architecture + security gates       294 passed
global pytest                   23340 passed, 1 warning, 0 failed
global Ruff                          810 (V6 baseline 810, no new debt)
```

The V6 additions are `+127` new adversarial regressions in a new module and `+53`
strengthened `AT-DP-122` connected scenarios; one V5 control case was relocated
rather than removed, so the V5 module still collects `71` tests and no previously
passing test was deleted. Both deltas are therefore `+180` and they agree exactly:
`tests/events/` moves `1091 → 1271` and the global suite moves `23160 → 23340`.
`AT-DP-122` itself moves `124 → 177`.

## 20. Global test evidence

Frozen pre-Phase-11.22 baseline: `22069 passed, 1 warning`. V1 implementation:
`22558 passed, 1 warning`. Post-remediation V1: `22694 passed, 1 warning, 0 failed`.
Post-remediation V2: `22962 passed, 1 warning, 0 failed`. Post-remediation V3:
`23025 passed, 1 warning, 0 failed` (+63 over the V2 remediation figure: 44 new V3
adversarial regressions and 19 strengthened `AT-DP-122` connected scenarios).
Post-remediation V4: `23060 passed, 1 warning, 0 failed` (+35 over the V3
remediation figure: 23 new V4 adversarial regressions and 12 strengthened
`AT-DP-122` connected scenarios). Post-remediation V5: `23160 passed, 1 warning,
0 failed` (+100 over the V4 remediation figure: 71 new V5 adversarial regressions
and 29 strengthened `AT-DP-122` connected scenarios). Post-remediation V6:
`23340 passed, 1 warning, 0 failed` (+180 over the V5 remediation figure: 127 new
V6 adversarial regressions and 53 strengthened `AT-DP-122` connected scenarios;
one superseded V5 *control* case was relocated into a dedicated named control, so
the V5 module still collects `71` tests and no previously passing global test was
removed). Post-remediation V7: `23540 passed, 1 warning, 0 failed` (+200 over the
V6 remediation figure: 127 new V7 adversarial regressions and 73 strengthened
`AT-DP-122` connected scenarios; no previously passing test was removed or
weakened, so `tests/events/` moves `1271 -> 1471` and `AT-DP-122` moves
`177 -> 250`). Post-remediation V8: `24065 passed, 1 warning, 1 pre-existing
interpreter-dependent failure` (+525 over the V7 remediation figure: 289 new V8
adversarial regressions and 237 strengthened `AT-DP-122` connected scenarios; no
previously passing test was removed or weakened, so `tests/events/` moves
`1471 -> 1997` and the global collected count moves `23540 -> 24066`). Post-
remediation V9: `24604 passed, 1 warning, 0 failed` (+539 over the V8 remediation
figure: 397 new V9 adversarial regressions, 141 strengthened `AT-DP-122` connected
scenarios, and the retained V6 civil-time case now passing, so the global failure
count returns to zero; `tests/events/` moves `1997 -> 2535` and `AT-DP-122` moves
`487 -> 628`). Post-remediation V10: `25200 passed, 1 warning, 0 failed` (+596 over
the V9 remediation figure: 475 new V10 adversarial regressions and 121 strengthened
`AT-DP-122` connected scenarios; no production-repair case was needed this cycle, so
`tests/events/` moves `2535 -> 3131` and `AT-DP-122` moves `628 -> 749`).
`GLOBAL_PYTEST_FAILURES=0` is therefore met on the canonical CPython 3.14.7 runtime,
at a pass count of `25200` against the `24604` floor. The single retained warning is
the pre-existing unrelated `starlette` `anyio` `DeprecationWarning`.

One timing-sensitive, event-system-unrelated test
(`tests/llm/test_model_gateway_streaming.py::test_the_public_stream_drops_content_arriving_after_the_deadline`,
which asserts a `40 ms` wall-clock bound) failed once in an initial run that was
executed concurrently with another heavy suite on the same machine; it passes
repeatedly in isolation and in the clean, uncontended global run recorded above.
No event-system code is involved.

## 21. Ruff baseline treatment

The frozen global baseline is `811` pre-existing violations (`ruff check cmm
kernel tests`), which Phase 11.22 does **not** clean up. At the frozen
implementation base the same command reports `811`, and at the audited V1 HEAD it
reports `810`, confirming both baselines exactly.

Every Phase 11.22-created or Phase 11.22-modified Python file, including every
Remediation V1, V2, V3, V4, V5, V6, V7, V8, V9, V10 and V11 change, is Ruff-clean.
The global count after Remediation V11 is `810`: identical to the audited V1 HEAD, to
the V5, V6, V7, V8, V9 and V10 figures, and one below the frozen baseline. The only
delta against the baseline is one pre-existing violation removed while editing
`tests/conftest.py` to add the test data-directory isolation fixture. No unrelated
violation was fixed, no global auto-fix was run, and no file outside the Phase 11.22
delta was touched. Every changed and created V11 file is also `ruff format --check`
-clean, so the V11 formatting pass introduced no unrelated churn.

## 22. Known non-goals and limitations

Explicitly out of scope, per the frozen design:

* no second event bus, registry, repository protocol, replay engine or DLQ;
* no broker abstraction and no Kafka/NATS/Redis Streams/RabbitMQ support;
* no command bus, job queue, workflow engine, service locator or second container;
* no distributed consensus, cross-device federation or global ordering;
* no metrics exporter, tracing, dashboard, alerting or OpenTelemetry (Phase 11.23);
* no generalised recovery, circuit breakers or backoff framework (Phase 11.24);
* no new HTTP/SSE/WebSocket event route and no `ClientBackend` event-bus escape
  hatch;
* no CMMChat or CMM Bots integration;
* no repository-wide Ruff cleanup;
* no backup, plugin or security-alert feature implementation.

Known limitations accepted by the design:

* the durable store is a local append-only JSONL file with no compaction or
  rotation; it is local-first by design and is not optimised for very high volume;
* `session.created`, `reasoning.completed`, `knowledge.updated`, `backup.created`,
  `plugin.failed` and `security.alert` are registered but reserved, because no
  canonical owner exposes a safe emission seam at Phase 11.22;
* the dead-letter queue is the existing in-memory Phase 9 implementation;
  Phase 11.22 does not make it durable;
* a bounded retry policy is configured by composition and is not persisted across
  process restart.

## 23. Next step

Fresh independent ChatGPT re-audit of the exact-HEAD Phase 11.22 **V12** bundle
(`phase-11.22-event-system-audit-v12.tar.gz`, produced with `git archive` from the
final Remediation V11 HEAD). This document states only
`REMEDIATED_AFTER_REAUDIT_V11_PENDING_INDEPENDENT_REAUDIT`; Phase 11.22 must not be
described as closed, independently verified, re-audited, passed or complete, and
neither Phase 11.23 nor Phase 11.24 has begun.

## 24. Remediation V1 record

Independent Audit V1 (`docs/audits/phase-11.22-event-system-independent-audit-v1.md`,
immutable) returned:

```text
INDEPENDENT_AUDIT_V1=FAIL
BLOCKERS=0
MAJORS=4
MINORS=5
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_AUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V1_ONLY
```

Remediation V1 fixed exactly those nine findings under strict TDD — a red
adversarial regression first, then the minimum fix, then the nearest regressions:

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-001` | `event_fingerprint()` omitted material persisted fields, so same-ID events differing only in correlation, causation, sensitivity or metadata collided, and stored-field tampering evaded the integrity check | the fingerprint now hashes the complete canonical serialization produced by the one shared `canonical_event_dict()` used for persistence; every persisted header and payload field is covered, including `payload.raw` |
| `MAJOR-002` | public `EventSystem.publish_event()` persisted a manually constructed event without the registry or payload-safety boundary | `publish_event()` is now itself the canonical publication boundary (registry membership, raw-payload rejection, bounded payload vocabulary, normalization) and preserves the supplied event identity and header facts; no new authority was created and the generic Phase 9 repository stays policy-free |
| `MAJOR-003` | dead-letter replay broadcast the stored event, so an unrelated replay-enabled subscriber resolved another subscriber's failed delivery | dead-letter replay targets the `subscription_id` recorded on the entry through an additive targeted capability on the one canonical bus and replay owner; the entry is removed only after that subscriber itself accepts replay and succeeds |
| `MAJOR-004` | the kernel adapter derived correlation/causation from other IDs and dropped explicit source `correlation_id`/`causation_id` | both are now readable source facts; an explicit authoritative value is preserved unchanged and derivation is only a fallback |
| `MINOR-001` | `retry_total` counted only exhausted deliveries | retries are counted on eventual success as well as on exhaustion |
| `MINOR-002` | a stored `payload: []` escaped as a raw `AttributeError` | every malformed stored container shape fails deterministically in the factory and surfaces as `AgentRuntimeEventPersistenceCorruptionError` |
| `MINOR-003` | the kernel adapter silently ignored forbidden source keys such as `prompt` | forbidden, private and credential-bearing source keys/values now fail closed before persistence; harmless irrelevant facts are still ignored |
| `MINOR-004` | the catalog documentation claimed twelve reserved events | the prose now states six reserved names, and a test derives the count from the real disposition map |
| `MINOR-005` | the requirements matrix claimed Phase 9 was "not modified" while documenting its additive hardening | the matrix now states that Phase 9 remained the canonical authority, was not architecturally replaced or reopened as a new phase, and received bounded additive compatibility hardening under Phase 11.22 |

The accepted architecture was preserved and the accepted Phase 9 changes were not
reverted. No second bus, registry, repository protocol, replay engine, DLQ
subsystem, container, broker abstraction, command bus or service locator was
added.

The immutable Audit V1 report and the immutable V1 bundle
(`a88f7c82f599ad7fc4679c2d5f82aefb86fe897e593531ec5430882417427ba3`) are preserved
byte-identical. The exact remediation HEAD, tree and V2 bundle SHA-256 are
reported in the remediation handoff rather than embedded here, for the same
self-reference reason as the V1 evidence record.

## 25. Remediation V2 record

Independent Re-audit V2
(`docs/audits/phase-11.22-event-system-independent-reaudit-v2.md`, immutable)
verified every Audit V1 finding as remediated and returned four new majors against
the audited V2 implementation HEAD `e67ab1ccea691fd8e76a0dfb8e4721c03b13b51d`:

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

Remediation V2 fixed exactly those four findings under strict TDD — a reproducing
adversarial regression first, verified red, then the minimum fix, verified green,
then the nearest regressions:

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V2-001` | the V1 boundary governed `payload.data` while persisted free-form **header** channels (`metadata`, `permissions`, `producer`, `aggregate_id`, `source`, and the other persisted identifier facts) stayed ungoverned, so forbidden material could be relocated out of the payload and still reach the same durable canonical event | one canonical Phase 11.22 event-safety step now covers every persisted free-form event fact: `metadata` is scanned recursively (keys and values), each `permissions` entry is validated, and every persisted identifier is checked by a narrow safe-identifier rule plus the canonical credential/private-marker scan. The same step runs at `create_event()`, `publish()` and `publish_event()`. No second policy authority was created: the existing forbidden-key, credential and private-marker vocabulary is reused, and the persisted-container key rule now matches the Phase 10.33 key rule |
| `MAJOR-V2-002` | an arbitrary `schema_version` was accepted by the public facade and durably appended, so a successful write produced a store the same build could not reopen | the supported-schema knowledge stays in the one canonical factory (`supports_schema_version`); `create_event()`/`publish()` refuse an unsupported schema; `_persist()` refuses one before `save()`; and the durable repository refuses any record this build could not deserialize, **before any byte is committed**. The identity-conflict check keeps its documented precedence, so the Audit V1 same-ID/different-content semantics are unchanged |
| `MAJOR-V2-003` | the canonical event classes were frozen only at the top level, so a subscriber could mutate `payload.data`, `metadata` and `permissions` for later subscribers, for live repository evidence and for the file-backed live/open split | canonical published facts are now effectively immutable across the whole path: the repository stores a detached canonical snapshot and returns detached snapshots from `get()`/`list()`/`query()`; the bus hands **each** subscriber (normal and replay) its own detached snapshot; the dead-letter record holds a detached snapshot. `detached_event_copy()` lives on the one canonical contract module, preserves JSON-compatible container shapes and is canonically equal to the original, so fingerprints and serialization compatibility are unchanged |
| `MAJOR-V2-004` | the Kernel bridge safety-scanned the real `DomainEvent.to_dict()` structural `payload` container and then discarded it, so the mapped lifecycle facts its own translation table claims were lost; the top-level `execution_id` fact was readable but rejected by the bounded payload vocabulary; and an explicit restrictive source sensitivity became the platform default | `SourceTranslation` gains an explicit `nested_fact_keys` subset: only those named facts may be read from the real Domain structure, each of which must already belong to the bounded platform payload vocabulary, so arbitrary nested content is never flattened. `approved` is projected as an already-bounded resolution fact, `execution_id` is decided once as a bounded payload fact (see §7), and source sensitivity maps through one explicit non-downgrading table (`personal`/`confidential`/`sensitive` → `CONFIDENTIAL`, `highly_sensitive`/`restricted` → `RESTRICTED`) that fails closed on an unrecognised classification. Nested forbidden content still fails closed, and explicit correlation/causation preservation from V1 is unchanged |

The accepted one-authority architecture was preserved: no second event bus,
registry, repository protocol, replay engine, DLQ subsystem, application container,
service locator, broker abstraction, command bus or generic event-sourcing
framework was added, and Phase 9 was not redesigned. All nine Audit V1 fixes
remain green, and no V1 fix was reverted or weakened.

Bounded contract clarifications recorded by Remediation V2:

* `execution_id` is a **bounded platform payload fact** and is now in the bounded
  payload vocabulary; it is not a second aggregate identity, and no adapter path
  emits a payload key the validator rejects;
* the source-sensitivity mapping is explicit, ordered and non-downgrading, and an
  unmapped source classification fails closed rather than defaulting to
  `INTERNAL`;
* `approved` is a projected `domain.approval.received` fact because it is already
  inside the bounded platform payload vocabulary; `decision_by`, `action` and
  `update_id` remain outside it and are deliberately not projected;
* persisted `metadata`/`permissions` keys are themselves content and are judged by
  the same canonical key rule the Phase 10.33 Domain authority applies to its own
  payload and metadata keys.

Two tests inherited from earlier phases encoded the pre-V2 shared-object-identity
behaviour and were updated to assert the stronger canonical-equality invariant
instead of weakening it: `tests/events/test_phase11_22_replay.py` now proves a
replayed delivery is canonically equal to stored evidence and that replay leaves
the stored fingerprint unchanged; `tests/events/test_phase11_22_event_catalog.py`
now validates mapping fact keys against the bounded platform payload vocabulary
itself rather than a hand-maintained duplicate list.

The immutable Audit V1 report, the immutable Re-audit V2 report, and the immutable
V1 and V2 bundles are preserved byte-identical. The exact Remediation V2 HEAD, tree
and V3 bundle SHA-256 are reported in the remediation handoff rather than embedded
here, for the same self-reference reason as the earlier evidence records.

## 26. Remediation V3 record

Independent Re-audit V3
(`docs/audits/phase-11.22-event-system-independent-reaudit-v3.md`, immutable)
returned:

```text
INDEPENDENT_REAUDIT_V3=FAIL
BLOCKERS=0
MAJORS=2
MINORS=1
AUDIT_V1_FINDINGS_REMEDIATED=9/9_VERIFIED
REAUDIT_V2_REPRODUCTIONS_FIXED=4/4_VERIFIED
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V3_ONLY
```

Remediation V3 fixed exactly those three findings under strict TDD — a red
adversarial regression first, then the minimum fix, then the nearest regressions —
inside the existing safety authority and canonical contracts, with no new bus,
registry, repository protocol, replayer, DLQ or event contract:

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V3-001` | persisted `metadata` was scanned for forbidden *text* but never type-checked, so opaque runtime objects, `bytes`/`bytearray` and `NaN`/`inf` were accepted; an opaque object's `__str__()` could stringify a credential into durable JSONL. `sensitivity` was not runtime-validated and a plain-string `permissions` value was coerced into a character list | the one forbidden-content scanner now also applies the shared structural rule (`_reject_non_descriptive_value`) to every persisted container, so opaque/binary/non-finite values fail closed before append; `canonicalize_platform_event_sensitivity()` enforces the canonical enum with exactly one supported-string normalization and rejects credential-bearing/private-marker labels; `validate_platform_permissions()` validates the container shape before factory coercion; canonical serialization no longer uses `json.dumps(default=str)` |
| `MAJOR-V3-002` | `publish()` handed nested `MappingProxyType` views to the factory, so supported nested mappings crashed with `TypeError: cannot pickle 'mappingproxy' object`; frozen sequences reopened from JSON as lists, so live and persisted shapes differed; shallow normalization left nested caller aliases reachable through `PublicationResult.event` | `canonicalize_platform_payload()` normalizes mappings to plain `dict` and supported sequences to plain `list` at the public boundary and re-validates the result; the canonical serialization emits that same shape, so live, persisted, reopened and replayed facts are equal with a stable fingerprint; `AgentRuntimeEventNormalizer.normalize()` deep-detaches nested containers |
| `MINOR-V3-001` | `InMemoryAgentRuntimeDeadLetterQueue.get()`/`list()` and `EventSystem.list_dead_letters()` returned live nested aliases, so a caller could mutate retained dead-letter evidence | the queue stores a detached snapshot and `get()`, `list()`, `remove()` and replay all pass the record through a new `detached_dead_letter_copy()` built on the existing `detached_event_copy()` plus the canonical deep-detach helper; targeted replay is unchanged and still removes the entry only after the targeted subscriber succeeds |

Canonical structured-payload shape decision: mapping → plain `dict`,
sequence/array → plain `list`, scalar → an approved finite JSON-compatible scalar
(`None`, `bool`, `int`, finite `float`, `str`). A `datetime` is deliberately **not**
an approved persisted scalar: durable JSON stores a timestamp as an ISO-8601
string, so accepting one would reopen it as a `str` and reintroduce exactly the
live/reopen shape drift this remediation removes.

Sensitivity/permissions validation decision: `sensitivity` has one canonical runtime
representation, `EventSensitivity`; the single explicitly supported input besides a
canonical member is a string spelling one of the enum's own values, normalized
immediately to that member, and every other input (including credential-bearing and
private-marker strings, which are checked before the label lookup) fails closed.
`permissions` must be a real sequence of canonical permission identifiers; a
`str`, `bytes`, `bytearray` or `memoryview` fails closed before any factory
iteration can coerce it.

The immutable Audit V1 report, the immutable Re-audit V2 report, the immutable
Re-audit V3 report and the immutable V1, V2 and V3 bundles are preserved
byte-identical. The exact Remediation V3 HEAD, tree and V4 bundle SHA-256 are
reported in the remediation handoff rather than embedded here, for the same
self-reference reason as the earlier evidence records.

## 27. Remediation V4 record

Independent Re-audit V4
(`docs/audits/phase-11.22-event-system-independent-reaudit-v4.md`, immutable)
verified all three V3 reproductions fixed (`3/3_VERIFIED`) and returned three new
findings:

```text
INDEPENDENT_REAUDIT_V4=FAIL
BLOCKERS=0
MAJORS=3
MINORS=0
REAUDIT_V3_REPRODUCTIONS_FIXED=3/3_VERIFIED
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V4_ONLY
```

Remediation V4 fixed exactly those three findings under strict TDD — a red
adversarial regression first (initial red `18 failed / 5 passed`), then the
minimum fix, then the nearest regressions — inside the existing safety authority
and canonical contracts, with no new bus, registry, repository protocol, replayer,
DLQ, safety module or event contract:

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V4-001` | the V3 scalar binary rejection already listed `memoryview`, but the shared sequence predicate `_is_sequence()` excluded only `str`, `bytes` and `bytearray`. `memoryview` is a registered `collections.abc.Sequence`, so a binary buffer was treated as an ordinary descriptive sequence and recursively canonicalized into a plain integer list — raw binary bytes entered persisted `payload.data` and persisted header containers | the **one existing** sequence predicate now classifies `memoryview` as binary, so the already-existing scalar binary rejection is reachable for it. `_canonicalize_payload_value()` also refuses a binary container explicitly, so the shape transform can never produce an integer list even if it is reached without validation. `bytes`, `bytearray` and `memoryview` now all fail closed in every persisted Phase 11.22 content channel |
| `MAJOR-V4-002` | `validate_platform_event_facts()` called `canonicalize_platform_event_sensitivity()` and discarded its return value, and `AgentRuntimeEventNormalizer` copied `header.sensitivity` unchanged. A manually built event with `sensitivity="restricted"` therefore passed the public boundary and kept a `str`: accepted and stored by the in-memory repository, and `AttributeError: 'str' object has no attribute 'value'` for the file-backed one | `EventSystem._validate_platform_event()` now **normalizes** rather than merely validates: it applies the existing canonical sensitivity rule to the persisted fact and, when the result differs, replaces the header's sensitivity with the canonical member before normalization and persistence. The existing `create_event()` normalization is unchanged, so both public routes produce one representation and both official repository implementations agree |
| `MAJOR-V4-003` | the DLQ derived `error_type`/`error` from `type(exc).__name__` unvalidated. Python permits `type("api_key=abcdef1234567890", (Exception,), {})`, so a credential-bearing (or private-marker) class name could enter canonical DLQ data with no raw exception message involved | one bounded safe DLQ error-category derivation now guards both exception-capture sites and the single DLQ write point. The transport-local bounded-name half lives in `cmm/agent_runtime/runtime_event_bus.py`; the credential/private-marker half is `category_for_delivery_error()` in the existing `cmm/events/event_payload_safety.py`, injected through `bind_error_categorizer()` by the composed `EventSystem` because `cmm/agent_runtime` is architecturally forbidden from importing `cmm.domains`. An ordinary `RuntimeError` stays meaningfully categorized; every other name becomes the neutral bounded category `SubscriberDeliveryError`, never stored, truncated or partially echoed |

Sensitivity canonicalization decision (explicit): the **preferred minimal rule** was
chosen — a canonical string is *accepted and normalized immediately* to
`EventSensitivity`, not rejected. That is consistent with the already-established
public `publish()` contract, with `create_event()`, and with the canonical
repository contract's requirement that the persisted fact be the enum. Strict
enum-only was rejected because it would have made the two public
publication routes semantically different for the same input.

DLQ error-category rule (explicit): an exception class name is stored as the DLQ
category only when it is **both** a bounded Python-style identifier
(`^[A-Za-z_][A-Za-z0-9_]{0,127}$`) **and** free of any Phase 10.33 high-confidence
credential and any forbidden private marker. Otherwise the neutral bounded category
`SubscriberDeliveryError` is recorded. Raw exception messages and tracebacks remain
excluded from all DLQ-facing fields, and no unsafe original class name may appear
anywhere in them.

The immutable Audit V1 report, the immutable Re-audit V2 report, the immutable
Re-audit V3 report, the immutable Re-audit V4 report and the immutable V1–V4
bundles are preserved byte-identical. The exact Remediation V4 HEAD, tree and V5
bundle SHA-256 are reported in the remediation handoff rather than embedded here,
for the same self-reference reason as the earlier evidence records.

## 28. Remediation V5 record

Independent Re-audit V5
(`docs/audits/phase-11.22-event-system-independent-reaudit-v5.md`, immutable)
verified all three V4 reproductions fixed (`3/3_VERIFIED`), preserved `279`
prior remediation regressions, and returned three new findings:

```text
INDEPENDENT_REAUDIT_V5=FAIL
BLOCKERS=0
MAJORS=3
MINORS=0
V4_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED
PRIOR_REMEDIATION_REGRESSIONS=279_PASS
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V5_ONLY
```

Remediation V5 fixed exactly those three findings under strict TDD — a red
adversarial regression first (initial red `30 failed / 41 passed`), then the
minimum fix, then the nearest regressions — inside the existing safety authority
and canonical contracts, with no new bus, registry, repository protocol, replayer,
DLQ, safety module, payload registry or event contract:

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V5-001` | the V4 binary rejection enumerated `bytes`, `bytearray` and `memoryview` by exact class. `array.array` is a compact binary buffer **and** a registered `collections.abc.Sequence`, so it was treated as a descriptive integer sequence and canonicalized into a plain integer list — byte values entered persisted `payload.data`, nested payload data and persisted header containers | classification is now **semantic**: one bounded buffer-protocol probe asks whether the interpreter can expose the value's raw bytes as an unsigned byte view, so `bytes`, `bytearray`, `memoryview` and every `array.array` typecode fail closed. The probe runs before all generic sequence handling in the sequence predicate, the structural scalar rejection, the canonical shape transform, the freeze path and the permissions gate, so binary rejection is unreachable by no standard supported buffer container while `str` and the descriptive containers stay valid |
| `MAJOR-V5-002` | the boundary bounded the payload **vocabulary** but not the value semantics implied by an approved key. `request_id`, `status`, `approved`, `duration_ms` and every other allowed key accepted arbitrary prose, and `metadata` was an unrestricted side channel, so the exact raw user sentence was durably persisted under `status` and `metadata["note"]` | one canonical `PAYLOAD_KEY_CLASSES` specification in the existing safety module assigns every allowed key exactly one explicit value class (identifier, category, boolean, number, version, timestamp, structured reference, reference sequence), with a regression asserting the union equals the allowlist so nothing falls through to prose. Structured reference containers are validated recursively against their documented nested shape. `METADATA_KEY_CLASSES` admits only bounded lifecycle metadata keys actually used by current producers/adapters/closed-phase contracts, and an unknown metadata key fails closed. A `None` optional identifier remains accepted, matching the persisted header gate |
| `MAJOR-V5-003` | the V4 DLQ fix split the safe-category rule, and the credential/private-marker half was only bound when the composed `EventSystem` injected it. `AgentRuntimeEventBus` is the sole canonical transport authority, so direct canonical use of bus + DLQ + bounded retry wrote an identifier-shaped credential class name such as `api_key_abcdef1234567890` straight into DLQ `error_type`/`error` | `safe_delivery_error_type()` now returns the neutral bounded category `SubscriberDeliveryError` whenever **no** external categorizer is bound. The transport can only prove a class name's *shape*, never that it is free of a credential or private marker, so an unbound categorizer retains no attacker-influenced name at all. The composed `EventSystem` still binds the canonical categorizer, so ordinary `RuntimeError` stays useful there, and `cmm.agent_runtime` still imports `cmm.domains` zero times |

Binary/buffer classification decision (explicit): the **semantic buffer-protocol
rule** was chosen over extending the exact-class list. Extending the list would
have left the same defect class open for the next standard buffer type; the
protocol probe is bounded (it never reads, copies, resizes or exposes the buffer,
and it fast-paths `str`/`bool`/`int`/`float`/`None` so no scalar is ever probed),
and the RED suite proves it rejects every tested typecode while preserving
descriptive `list`/`tuple` identifier containers and explicit `list[int]`
references. Banning all sequences was rejected because it would break legitimate
structured reference containers.

Metadata policy (explicit): metadata is lifecycle metadata, not a content mirror.
Only keys actually used by current Phase 11.22 producers, adapters and
closed-phase contracts are admitted, each with a bounded value class; an unknown
key fails closed rather than being preserved for convenience. The documented safe
examples `{"status_code": "ok", "attempt": 1}` and `{"origin": "original"}` remain
valid, bounded numeric metadata and safe JSON-compatible nesting remain valid, and
the three prior remediation modules that used invented metadata key names now
carry the same facts under the declared vocabulary so their original invariants
are still proven.

Direct-bus DLQ fail-safe rule (explicit): no categorizer bound → neutral bounded
category. The alternative of forbidding DLQ activation without a categorizer was
rejected because it changes canonical composition and historical compatibility
behaviour; the neutral-default rule is fail-safe and minimally invasive, and it
preserves the legacy direct single-attempt bus shape exactly.

The immutable Audit V1 report, the immutable Re-audit V2, V3, V4 and V5 reports,
and the immutable V1–V5 bundles are preserved byte-identical. The exact
Remediation V5 HEAD, tree and V6 bundle SHA-256 are reported in the remediation
handoff rather than embedded here, for the same self-reference reason as the
earlier evidence records.

## 29. Remediation V6 record

Independent Re-audit V6
(`docs/audits/phase-11.22-event-system-independent-reaudit-v6.md`, immutable)
verified all three V5 reproductions fixed (`3/3_VERIFIED`), preserved `350` prior
remediation regressions, and returned three new majors and one new minor:

```text
INDEPENDENT_REAUDIT_V6=FAIL
BLOCKERS=0
MAJORS=3
MINORS=1
V5_CONCRETE_REPRODUCTIONS_FIXED=3/3_VERIFIED
PRIOR_REMEDIATION_REGRESSIONS=350_PASS
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V6_ONLY
```

Remediation V6 fixed exactly those four findings under strict TDD — a red
adversarial regression first (initial red `90 failed / 37 passed`), then the
minimum fix, then the nearest regressions — inside the existing safety authority
and canonical contracts, with no new bus, registry, repository protocol, replayer,
DLQ, safety module, payload registry, numeric-policy registry, timestamp subsystem
or event contract:

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V6-001` | the V5 numeric class was called bounded but accepted any finite Python number. `count = 10 ** 5000` was accepted by the official in-memory repository and raised `ValueError` inside the official file-backed repository while serializing, so the same public event diverged across the two official repositories; `count=-1`, `duration_ms=-5`, `attempts=-1`, `sequence=-1` and `duration_ms=1e308` were accepted too | `MAX_PLATFORM_NUMERIC_FACT = 2**63 - 1` plus one small `NUMERIC_FACT_SEMANTICS` table in the existing safety authority: count/attempt/attempts/sequence are real integers in `[0, bound]`, `duration_ms` is a finite integer/float in `[0, bound]`, `ratio` is the normalized `[0.0, 1.0]` ratio current producers publish, and every other numeric fact is finite and inside `[-bound, bound]`. Enforced before any repository interaction, so no repository is the safety boundary and the two official repositories cannot diverge |
| `MAJOR-V6-002` | the identifier character set kept `:`/`/`/`.` with no path-safety classification, so `file:///Users/alice/.ssh/id_rsa`, `Users/alice/.ssh/id_rsa` and `C:/Users/alice/.ssh/id_rsa` qualified as identifiers and were durably persisted — including in the canonical header `producer` fact — against the frozen design's "filesystem secrets/paths where not public-safe" rule | one narrow, purely syntactic classifier in the existing identifier/header safety authority (a `file:` URI scheme, a Windows drive-root path, a UNC share, an absolute POSIX path or `~` shorthand, a user-home directory segment, a known secret-bearing private directory segment, or a private key material file name). No I/O, no path resolution, no content inspection. Applied on every persisted identifier channel: payload identifiers, header identifier facts, `permissions` entries and identifier-classified metadata facts |
| `MAJOR-V6-003` | payload keys equivalent to canonical header facts were validated independently and persisted alongside the header, so `header.event_id=header-event` and `payload.event_id=payload-event` coexisted — and, critically, `header.sensitivity=internal` alongside `payload.sensitivity=restricted`, a stricter classification hidden from the canonical authority | `CANONICAL_HEADER_PAYLOAD_KEYS` is declared once, as the exact intersection of the bounded payload vocabulary with the canonical header fact names. Those payload keys are consumed into the canonical header before persistence instead of being persisted twice: an unset header fact takes the payload value, an equal one is left alone, a contradictory one fails closed, and an explicit `None` optional reference is not a value. `sensitivity` is the one non-equal resolution — the header keeps the stricter class, so a stricter source value is promoted and a lower payload value can never downgrade it. Both the factory path and the manual `publish_event` path apply the same rule, and the kernel adapter no longer mirrors the *source* event name into a payload `event_type` key |
| `MINOR-V6-001` | the "canonical ISO-8601" class validated text shape rather than civil time, so `9999-99-99T99:99Z`, `2026-02-31T12:00Z` and `2026-09-27T25:61Z` reached durable evidence, and a timezone-less `2026-09-27T12:00` was accepted despite the timezone-aware chronology contract | the existing shape rule is retained and the value must additionally parse as a real calendar/time value and carry an explicit UTC offset. The existing `datetime` and canonical serialization approach is reused, nothing is silently reinterpreted or normalized, and an invalid value fails closed |

Bounded-numeric decision (explicit): one constant — the signed 64-bit
machine-integer range — rather than invented per-field maxima. Nineteen decimal
digits is far below every serializer and interpreter conversion limit and far above
every legitimate count, attempt, sequence, millisecond duration or version this
platform produces. Per-key semantics were needed because `ratio` is a normalized
ratio in current usage while `duration_ms` is a duration; per-field maxima were
rejected because one machine-integer bound is easier to audit and cannot drift per
key.

Filesystem classifier decision (explicit): a bounded syntactic signature list, not
a ban on `/` or `:`. The audited reproduction proves the classification was
missing; the producer inventory proves legitimate references genuinely need those
characters (`workflow:123`, `domain:legal`, `provider/model`, `cmm.orchestration`,
`CORR-ORIGINAL`, `events:read`), and every one of them is asserted to still pass.
Real path resolution or filesystem inspection was rejected because the frozen
requirement is about the public-safety of the token, not about the host's
filesystem.

Canonical header authority decision (explicit): the preferred design — one
authoritative representation — was implemented, not the equality-only
compatibility alternative. The consumed key set is the intersection with the
bounded payload vocabulary, so a payload key outside that vocabulary is still
rejected by the ordinary gate and the closed vocabulary stays closed. The
alternative of simply deleting every header-named payload key was rejected because
it would silently discard a legitimate identity fact; adopting an unset header field
preserves the fact while keeping one authority. Timestamps require an explicit UTC
offset: no current producer publishes a legitimate timezone-less platform timestamp,
so no compatibility exception was needed and none was added.

Four superseded V5 *control* expectations (a payload copy of a canonical header
fact) were updated rather than preserved verbatim: the same legitimate values are
still exercised, the assertions now name the canonical header they reach, and the
conflicting cases are proved to fail closed by the V6 adversarial suite. No V5
finding, fix or invariant was weakened, and `PRIOR_REMEDIATION_REGRESSIONS=350`
matches the figure the independent Re-audit V6 reported exactly.

The immutable Audit V1 report, the immutable Re-audit V2, V3, V4, V5 and V6
reports, and the immutable V1–V6 bundles are preserved byte-identical. The exact
Remediation V6 HEAD, tree and V7 bundle SHA-256 are reported in the remediation
handoff rather than embedded here, for the same self-reference reason as the
earlier evidence records.

## 30. Remediation V7 record

Independent Re-audit V7
(`docs/audits/phase-11.22-event-system-independent-reaudit-v7.md`) verified all
four V6 findings fixed (`4/4_VERIFIED`) and preserved `477` prior remediation
regressions, while failing the phase with two new majors and no minors
(`BLOCKERS=0`):

```text
INDEPENDENT_REAUDIT_V7=FAIL
V6_CONCRETE_FINDINGS_FIXED=4/4_VERIFIED
PRIOR_REMEDIATION_REGRESSIONS=477_PASS
MAJOR_V7_001=RELATIVE_PATH_TRAVERSAL_AND_SENSITIVE_FILESYSTEM_REFERENCES_BYPASS_PATH_SAFETY
MAJOR_V7_002=URI_USERINFO_CREDENTIALS_CAN_ENTER_PERSISTED_IDENTIFIER_FIELDS
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V7_ONLY
```

Remediation V7 fixed exactly those two findings under strict TDD — a red
reproduction suite first (`89 failed / 37 passed`), then the minimum fix in the
existing authority:

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V7-001` | the V6 classifier recognized strong *absolute* filesystem signatures but had no traversal-segment rule and no relative private-system-root signature, so `safe/../../etc/shadow` and `foo/../bar/../../private/var` qualified as identifiers and were durably persisted through `payload.request_id`, `header.producer`, `metadata.error_type`, `header.permissions[]` and nested structured references | three patterns added to the **existing** `_PRIVATE_FILESYSTEM_PATTERNS` classifier: a `..` traversal segment delimited by `/` or `\` (or bounding the token), a sensitive system file in relative form (`etc/shadow`, `etc/passwd`, `etc/sudoers` — which also refuses `nfs://server/etc/shadow`), and the macOS private roots in relative form (`private/var`, `private/etc`, `private/tmp`, `private/root`). Segment-based, never a naive substring rule. No I/O, no path resolution, no new policy module |
| `MAJOR-V7-002` | the identifier grammar admits `:`, `/` and `@`, but the composed credential scanner did not treat URI userinfo password *structure* as credential material, so `https://admin:hunter2hunter2@example.com/path` and `postgres://alice:supersecret@example.com/db` were durably persisted | one narrow `contains_uri_userinfo_credential()` check in the **existing** authority: a real scheme, a `//` authority, userinfo terminated by `@`, and a colon inside that userinfo with a non-empty password component. The userinfo is percent-decoded before the colon test. Credential-free URIs and bare-username userinfo stay valid. Returns a boolean; the rejection message is a static literal, so the secret is never echoed. No second credential policy |

Both rules live in `validate_platform_identifier()`, the single shared authority
used by payload identifier fields, the canonical header facts, `permissions`,
identifier-classified metadata facts and nested structured references, so no
channel can be patched alone. The canonical transport DLQ channel was already
closed to both shapes by its bounded class-name rule (`^[A-Za-z_][A-Za-z0-9_]{0,127}$`),
so no DLQ change was needed and none was made.

```text
REMEDIATION_V7_TESTS=127 passed (initial red 89 failed / 37 passed)
PRIOR_REMEDIATION_REGRESSIONS=477 passed (V1-V6 preserved)
REMEDIATION_V1_TO_V7_REGRESSIONS=604 passed
PHASE_SUITE=tests/events/ 1471 passed
AT_DP_122=250 passed (177 prior + 73 V7)
PHASE9_EVENT_REGRESSIONS=tests/agent_runtime/ 3635 passed
DOMAIN_DP033_REGRESSIONS=tests/domains/ 11824 passed
EVENT_INVENTORY=tests/**/*event*.py 1270 passed
CLOSED_PHASE_ACCEPTANCES=310 passed
CLOSED_PHASE_SUPPORT=1077 passed
ARCHITECTURE_AND_SECURITY_GATES=294 passed
GLOBAL_PYTEST=23540 passed, 1 warning, 0 failed
CHANGED_FILE_RUFF=PASS
GLOBAL_RUFF_COUNT=810 (V7 baseline 810, no new debt)
FORMAT_CHECK=PASS
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
```

Both rules are narrow by construction and were chosen over broader alternatives.
Banning every `/`, `:` or `@` was rejected because the producer inventory proves
legitimate references genuinely need those characters (`workflow:123`,
`domain:legal`, `provider/model`, `cmm.orchestration`, `events:read`), and each is
asserted to still pass. Real path resolution and filesystem inspection were
rejected because the frozen requirement concerns the public-safety of the token,
not the host's filesystem, and boundary I/O would be slow and host-dependent.

The immutable Audit V1 report, the immutable Re-audit V2, V3, V4, V5, V6 and V7
reports, and the immutable V1–V7 bundles are preserved byte-identical. The exact
Remediation V7 HEAD, tree and V8 bundle SHA-256 are reported in the remediation
handoff rather than embedded here, for the same self-reference reason as the
earlier evidence records.

## 31. Remediation V8 record

Independent Re-audit V8
(`docs/audits/phase-11.22-event-system-independent-reaudit-v8.md`) verified both V7
findings fixed (`2/2_VERIFIED`) and preserved `604` prior remediation regressions,
while failing the phase with two new majors and one new minor (`BLOCKERS=0`):

```text
INDEPENDENT_REAUDIT_V8=FAIL
V7_CONCRETE_FINDINGS_FIXED=2/2_VERIFIED
PRIOR_REMEDIATION_REGRESSIONS=604_PASS
MAJOR_V8_001=FILESYSTEM_REFERENCE_CLASSIFIER_STILL_ACCEPTS_PATH_EQUIVALENTS_AND_UNLISTED_SENSITIVE_PATHS
MAJOR_V8_002=WRAPPED_OR_NESTED_URI_USERINFO_CREDENTIALS_BYPASS_IDENTIFIER_SAFETY
MINOR_V8_001=ROADMAP_PHASE11_SUMMARY_OMITS_REAUDIT_V7
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V8_ONLY
```

Remediation V8 fixed exactly those three findings under strict TDD — a red
reproduction suite first (`234 failed / 47 passed`), then the minimum fix in the
existing authority:

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V8-001` | the V6/V7 classifier matched the **raw identifier text**, so it was a list of selected spellings rather than a classification. Lexically equivalent forms of one location disagreed — `etc/shadow` was refused while `etc//shadow` and `etc/./shadow` were durably persisted, `private/var/db/keychains` was refused while `safe/private/./var/db/keychains` was persisted — and unmistakable system locations no pattern named (`proc/self/environ`, `etc/ssh/ssh_host_rsa_key`, `Windows/System32/config/SAM`, `Library/Keychains/login.keychain-db`) were durably persisted through every shared identifier channel | one **pure lexical canonical analysis form** (`_analyze_lexical_path()`: separators normalized, repeated separators collapsed, `.` elided, `..` detected before any elision, no I/O, no `Path.resolve()`, no mutation of the persisted value) plus a **fail-closed public-reference allowlist**: a slash-bearing reference is public-safe only when it is a credential-free authority-bearing URI reference or is rooted in a declared public logical namespace (`PUBLIC_SLASH_REFERENCE_ROOTS = {cmm, provider}`, the complete set a real inventory of every identifier value the suite routes through the authority found in use). The retained V6/V7 pattern tuple is unchanged in content and now evaluated against the canonical form. Every other slash-bearing spelling fails closed, so an unlisted local/system path cannot enter persistence because no pattern was appended for it |
| `MAJOR-V8-002` | the V7 userinfo rule recognized a password-bearing authority only when the URI began at character zero, so `jdbc:postgresql://alice:supersecret@example.com/db`, `jdbc:mysql://root:hunter2hunter2@example.com/db`, `provider/https://alice:supersecret@example.com/db` and `foo:https://alice:supersecret@example.com/db` qualified as safe identifiers and were durably persisted | the same `contains_uri_userinfo_credential()` check made **occurrence-independent**: every authority-bearing `://` occurrence is visited, each authority is split at its last `@`, the userinfo is percent-decoded and split at the first `:`, and a non-empty password component refuses the reference. A credential appearing only in a later authority is seen. Credential-free URIs, credential-free wrapped URIs, bare-username userinfo and an empty password stay valid. Returns a boolean; the rejection message is a static literal, so the secret is never echoed. No second credential policy |
| `MINOR-V8-001` | the high-level Phase 11 row in `ROADMAP.md` summarized the Phase 11.22 audit history only through Re-audit V6 and "all six", contradicting the detailed Phase 11.22 line, the detailed Phase 11 roadmap, the requirements matrix, the implementation evidence and the committed immutable V7 re-audit report | the high-level row now states Re-audits `V2/V3/V4/V5/V6/V7` and "was remediated after all seven", and additionally records the Re-audit V8 failure and the Remediation V8 state. No historical audit artifact was rewritten |

Both production rules live in `validate_platform_identifier()`, the single shared
authority used by payload identifier fields, the canonical header facts,
`permissions`, identifier-classified metadata facts and nested structured
references, so no channel can be patched alone. No second path policy, credential
scanner, URI registry or identifier subsystem was introduced, and
`AGENT_RUNTIME_TO_DOMAIN_IMPORTS` remains `0`.

```text
REMEDIATION_V8_TESTS=289 passed (initial red 234 failed / 47 passed on the 281-case module; the 8 URI-suffix residue reproductions added under TDD were independently red before their fix)
PRIOR_REMEDIATION_REGRESSIONS=604 collected, 603 passed, 1 pre-existing interpreter-dependent failure
REMEDIATION_V1_TO_V8_REGRESSIONS=893 collected, 892 passed, 1 pre-existing interpreter-dependent failure
PHASE_SUITE=tests/events/ 1997 collected, 1996 passed, 1 pre-existing interpreter-dependent failure
AT_DP_122=487 passed (250 prior + 237 V8)
PHASE9_EVENT_REGRESSIONS=tests/agent_runtime/ 3635 passed
DOMAIN_DP033_REGRESSIONS=tests/domains/ 11824 passed
EVENT_INVENTORY=tests/**/*event*.py 1270 passed
CLOSED_PHASE_ACCEPTANCES=310 passed
CLOSED_PHASE_SUPPORT=1077 passed
ARCHITECTURE_AND_SECURITY_GATES=294 passed
GLOBAL_PYTEST=24066 collected, 24065 passed, 1 warning, 1 pre-existing interpreter-dependent failure
CHANGED_FILE_RUFF=PASS
GLOBAL_RUFF_COUNT=810 (V8 baseline 810, no new debt)
FORMAT_CHECK=PASS
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
```

The lexical path rule and the fail-closed classification are documented in
§15.6, and the occurrence-independent userinfo rule in §15.7. Both were chosen
over broader alternatives: banning every `/`, `:` or `@` was rejected because the
producer inventory proves legitimate references genuinely need those characters,
real path resolution and filesystem inspection were rejected because the frozen
requirement concerns the public-safety of the token rather than the host's
filesystem, and a `contains ":" and "@"` userinfo heuristic was rejected because
the URI grammar names the component after the `:` — the rule stays structural.

The immutable Audit V1 report, the immutable Re-audit V2, V3, V4, V5, V6, V7 and V8
reports, and the immutable V1–V8 bundles are preserved byte-identical. The exact
Remediation V8 HEAD, tree and V9 bundle SHA-256 are reported in the remediation
handoff rather than embedded here, for the same self-reference reason as the
earlier evidence records.

## 32. Remediation V9 record

Independent Re-audit V9
(`docs/audits/phase-11.22-event-system-independent-reaudit-v9.md`) verified both V8
findings fixed (`2/2_VERIFIED`) and preserved the prior remediation regressions,
while failing the phase with two new majors and one new minor (`BLOCKERS=0`):

```text
INDEPENDENT_REAUDIT_V9=FAIL
V8_CONCRETE_FINDINGS_FIXED=2/2_VERIFIED
BLOCKERS=0
MAJORS=2
MINORS=1
MAJOR_V9_001=WRAPPED_NON_AUTHORITY_FILE_URI_BYPASSES_FAIL_CLOSED_FILESYSTEM_CLASSIFIER
MAJOR_V9_002=SUPPORTED_RUNTIME_TIMESTAMP_SEMANTICS_REOPEN_PRIOR_V6_FINDING_AND_KEEP_GLOBAL_GATE_RED
MINOR_V9_001=REFERENCE_TEST_EVIDENCE_COUNTS_STALE_AFTER_FINAL_V8_AT_ADDITIONS
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V9_ONLY
```

Remediation V9 fixed exactly those three findings under strict TDD — a red
reproduction suite first (`168 failed / 229 passed` on the new module, plus the
retained V6 case), then the minimum fix in the existing authority:

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V9-001` | the shared identifier/filesystem authority recognized a `file:` reference only as an authority-bearing URI (`scheme://authority`) or at character zero (`^file:`). The outer identifier grammar admits a public logical wrapper such as `provider/` or `cmm/`, and the V8 slash-root allowlist accepted that wrapper, so a **non-authority** `file:` reference reached through it was never classified: `provider/file:C:/Windows/System32/config/SAM`, `cmm/file:C:/Windows/System32/config/SAM`, `provider/file:C:/Windows/System32/config/SECURITY`, `provider/file:/Windows/System32/config/SAM` and `provider/file:C:/ProgramData/Microsoft/Crypto/RSA/MachineKeys` each returned non-private from the classifier, passed the canonical identifier validator, passed canonical `EventSystem` publication and were durably persisted — across all 13 shared identifier-bearing channels, through both official repositories and through a manual `publish_event(...)` call | the **existing** `file:` signature in `_PRIVATE_FILESYSTEM_PATTERNS` is anchored at a path *segment* boundary instead of at character zero: `re.compile(r"(?:^|/)file:", re.IGNORECASE)`. Because the pattern is evaluated against the canonical lexical analysis form whose segments are joined by `/`, a segment boundary is exactly where the identifier grammar can carry a scheme token, and `file` is a case-insensitive URI scheme — so `provider//file:`, `provider/./file:`, `PROVIDER/FILE:` and `File:` receive the identical verdict. No literal was appended for any audited filename or location, so an unnamed wrapped location is refused by the same structural rule. Analysis-only: no filesystem I/O, no host resolution, no rewriting of a persisted identifier, and no second path or URI policy module |
| `MAJOR-V9-002` | the canonical Phase 11.22 timestamp authority delegated the civil-hour bound to `datetime.fromisoformat()`. CPython 3.14 widened that parser to accept the ISO end-of-day spelling `24:00` and roll it into the next day, so on the canonical `.venv` the retained V6 regression case `2026-09-27T24:00:00Z` was accepted and durably persisted although the frozen contract admits only hours `00..23`, and `GLOBAL_PYTEST_FAILURES=0` could not be met | the frozen `00..23` hour range is asserted explicitly in the same authority, on the value's own text and **before** the parser is consulted (`MAX_PLATFORM_CIVIL_HOUR = 23` plus `_TIMESTAMP_CIVIL_TIME_PATTERN`), so an interpreter that accepts a wider ISO form cannot widen the persisted contract. The guard is deliberately limited to the hour: hour `25`, minute `60`, second `60`, month `13`, day `32`, a fractional end-of-day value and an out-of-range UTC offset are all still refused by `fromisoformat()` itself, so no wider parser rewrite was undertaken. No second timestamp parser, no accepted-form change, no normalization change and no Python support-metadata change |
| `MINOR-V9-001` | current non-historical references still carried pre-final counts — `tests/events/` `1984 collected / 1983 passed` and `AT-DP-122` `474 passed (250 prior + 224 V8)` — and a current statement claimed `NON_PUBLIC_FILESYSTEM_PATHS_NEVER_ENTER_EVENT_PERSISTENCE=PASS` while the V9-001 bypass was live | `docs/reference/phase-11-event-system.md`, `docs/reference/phase-11-stable-integrated-platform-requirements-matrix.md`, `docs/audits/phase-11.22-event-system-implementation-evidence.md`, `docs/roadmap/phase-11-stable-integrated-platform.md` and `ROADMAP.md` are synchronized to the final V9 counts (`tests/events/` `2535`, `AT-DP-122` `628`, global `24604`), the invariant is stated with its scope and only after the V9-001 remediation made it true, and every current-state marker reads `REMEDIATED_AFTER_REAUDIT_V9_PENDING_INDEPENDENT_REAUDIT`. No historical audit report was rewritten |

Both production rules live in `validate_platform_identifier()` /
`_parse_canonical_timestamp()`, the single shared authorities the phase already
had, so no channel can be patched alone. No second event, identifier, URI, path,
timestamp, registry, repository, runtime, resolver, loader, engine or policy
infrastructure was introduced, and `AGENT_RUNTIME_TO_DOMAIN_IMPORTS` remains `0`.

```text
REMEDIATION_V9_TESTS=397 passed (initial red 168 failed / 229 passed, plus the retained V6 civil-time case)
V8_REGRESSIONS=289 passed (preserved)
V7_REGRESSIONS=127 passed (preserved)
V6_REGRESSIONS=127 passed (preserved; the retained civil-time case is now green)
V5_REGRESSIONS=71 passed (preserved)
V4_REGRESSIONS=23 passed (preserved)
V3_REGRESSIONS=44 passed (preserved)
V2_REGRESSIONS=126 passed (preserved)
V1_REGRESSIONS=86 passed (preserved)
PRIOR_REMEDIATION_REGRESSIONS=1290 passed (V1-V9)
PHASE_SUITE=tests/events/ 2535 passed
AT_DP_122=628 passed (487 prior + 141 V9)
KERNEL_ADAPTER_TESTS=76 passed
PHASE9_EVENT_REGRESSIONS=tests/agent_runtime/ 3635 passed
DOMAIN_DP033_REGRESSIONS=tests/domains/ 11824 passed
DOMAIN_DP033_ACCEPTANCE=92 passed
ORCHESTRATION_EVENT_TESTS=tests/orchestration/ 498 passed
VALIDATION_EVENT_TESTS=tests/validation/ 533 passed
WORKFLOW_EVENT_TESTS=tests/workflows/ 46 passed
CLOSED_PHASE_ACCEPTANCES=185 passed, 1 warning
EVENT_INVENTORY=tests/**/*event*.py 1270 passed
ARCHITECTURE_AND_SECURITY_GATES=294 passed
GLOBAL_PYTEST=24604 collected, 24604 passed, 1 warning, 0 failed
CHANGED_FILE_RUFF=PASS
GLOBAL_RUFF_COUNT=810 (V9 baseline 810, no new debt)
GLOBAL_RUFF_NO_NEW_DEBT=PASS
FORMAT_CHECK=PASS
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
```

The wrapped-`file:` rule is documented in §15.8 and the interpreter-independent
hour bound in §15.4. Both were chosen over broader alternatives: appending the
audited Windows and macOS filenames to the pattern list was rejected because it
would leave the classifier a denylist of selected spellings (the exact V8 defect),
and bounding every civil field explicitly was rejected because only the hour bound
is demonstrably interpreter-dependent. The immutable Audit V1 report, the immutable
Re-audit V2–V9 reports, and the immutable V1–V9 bundles are preserved
byte-identical. The exact Remediation V9 HEAD, tree and V10 bundle SHA-256 are
reported in the remediation handoff rather than embedded here, for the same
self-reference reason as the earlier evidence records.

## 33. Remediation V10 record

Independent Re-audit V10
(`docs/audits/phase-11.22-event-system-independent-reaudit-v10.md`) verified all
three V9 findings fixed (`3/3_VERIFIED`) and preserved the prior remediation
regressions, while failing the phase with one new major, no minors and no blockers:

```text
INDEPENDENT_REAUDIT_V10=FAIL
V9_FINDINGS_FIXED=3/3_VERIFIED
BLOCKERS=0
MAJORS=1
MINORS=0
MAJOR_V10_001=WRAPPED_WINDOWS_DRIVE_ROOT_REFERENCE_BYPASSES_PUBLIC_ROOT_FILESYSTEM_CLASSIFIER
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V10_ONLY
EXPECTED_NEXT_BUNDLE=phase-11.22-event-system-audit-v11.tar.gz
```

Remediation V10 fixed that single finding under strict TDD — a red reproduction
suite first (`227 failed / 248 passed` on the new module, in a commit containing only
tests), then the minimum fix in the existing authority:

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V10-001` | the canonical identifier/filesystem safety authority detected a raw Windows drive-root path only at **character zero** of the whole reference (`re.compile(r"^[A-Za-z]:[\\/]")`). Remediation V9 had already moved the `file:` signature to a path-*segment* boundary, but the structurally identical raw drive-root token was left whole-value-anchored. Because `provider` and `cmm` are declared public slash roots, an allowlisted wrapper carried a raw local drive past the classifier: `provider/C:/Windows/System32/config/SAM`, `cmm/C:/Windows/System32/config/SAM`, `provider//C:/Windows/System32/config/SAM`, `provider/./C:/Windows/System32/config/SAM` and `provider/C:/Windows/System32/config/SECURITY` each returned non-private from the classifier, passed the canonical identifier validator, passed canonical `EventSystem` publication and were durably appended — across all 13 shared identifier-bearing channels, through both official repositories and through a manual `publish_event(...)` call. The defect was not the filename `SAM` but the ability of an allowlisted logical wrapper to carry an embedded raw drive-root reference | the **existing** raw drive-root signature in `_PRIVATE_FILESYSTEM_PATTERNS` is anchored at a path *segment* boundary instead of at character zero: `re.compile(r"^[A-Za-z]:[\\/]")` → `re.compile(r"(?:^|/)[A-Za-z]:[\\/]")` — the same structural repair V9 applied to the structurally identical `file:` token, not a second scanner and not a new Windows-path subsystem. Because the pattern is evaluated against the canonical lexical analysis form whose segments are joined by `/`, a segment boundary is exactly where the identifier grammar can carry a drive token, so `provider//C:/`, `provider/./C:/`, `Provider/C:/`, `PROVIDER/C:/`, `C://Windows/` and lowercase `provider/c:/` receive the identical verdict. The rule still requires real drive-root syntax — a letter, a colon and a path separator — so ordinary colon identifiers, segment-boundary non-drive colons (`provider/a:1/model`) and credential-free URIs keep their verdicts. No literal was appended for `SAM`, `SECURITY`, `Windows`, `System32`, `ProgramData`, `MachineKeys` or any audited drive letter, so fresh probes are refused by the same structural rule. Analysis-only: no filesystem I/O, no `Path.resolve()`, no rewriting of an accepted persisted identifier, and no second path/URI policy module |

The one production rule lives in `is_private_filesystem_reference()`, reached by
every persisted identifier channel through `validate_platform_identifier()` — the
single shared authority the phase already had — so no channel can be patched alone.
No second event, identifier, URI, path, drive-root, timestamp, registry, repository,
runtime, resolver, loader, engine or policy infrastructure was introduced, and
`AGENT_RUNTIME_TO_DOMAIN_IMPORTS` remains `0`.

```text
REMEDIATION_V10_TESTS=475 passed (initial red 227 failed / 248 passed)
V9_REGRESSIONS=397 passed (preserved)
V8_REGRESSIONS=289 passed (preserved)
V7_REGRESSIONS=127 passed (preserved)
V6_REGRESSIONS=127 passed (preserved)
V5_REGRESSIONS=71 passed (preserved)
V4_REGRESSIONS=23 passed (preserved)
V3_REGRESSIONS=44 passed (preserved)
V2_REGRESSIONS=126 passed (preserved)
V1_REGRESSIONS=86 passed (preserved)
PRIOR_REMEDIATION_REGRESSIONS=1765 passed (V1-V10)
PHASE_SUITE=tests/events/ 3131 passed
AT_DP_122=749 passed (628 prior + 121 V10)
KERNEL_ADAPTER_TESTS=76 passed
PHASE9_EVENT_REGRESSIONS=tests/agent_runtime/ 3635 passed
DOMAIN_DP033_REGRESSIONS=tests/domains/ 11824 passed
DOMAIN_DP033_ACCEPTANCE=92 passed
ORCHESTRATION_EVENT_TESTS=tests/orchestration/ 498 passed
VALIDATION_EVENT_TESTS=tests/validation/ 533 passed
WORKFLOW_EVENT_TESTS=tests/workflows/ 46 passed
CLOSED_PHASE_ACCEPTANCES=185 passed, 1 warning
EVENT_INVENTORY=tests/**/*event*.py 1270 passed
ARCHITECTURE_AND_SECURITY_GATES=294 passed
GLOBAL_PYTEST=25200 collected, 25200 passed, 1 warning, 0 failed
CHANGED_FILE_RUFF=PASS
GLOBAL_RUFF_COUNT=810 (V10 baseline 810, no new debt)
GLOBAL_RUFF_NO_NEW_DEBT=PASS
FORMAT_CHECK=PASS
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
```

Widening the slash-root allowlist and adding the audited Windows filenames were both
rejected: the first cannot distinguish a public namespace from a path suffix carrying
a raw local drive, and the second would leave the classifier a denylist of selected
spellings (the exact V8 defect). Segment-anchoring the drive-root token fixes the
classification structurally, in the authority that already existed. The immutable
Audit V1 report, the immutable Re-audit V2–V10 reports, and the immutable V1–V10
bundles are preserved byte-identical. The exact Remediation V10 HEAD, tree and V11
bundle SHA-256 are reported in the remediation handoff rather than embedded here, for
the same self-reference reason as the earlier evidence records.

## 34. Remediation V11 record

Independent Re-audit V11
(`docs/audits/phase-11.22-event-system-independent-reaudit-v11.md`) verified the
single V10 finding fixed (`1/1_VERIFIED`) and preserved the prior remediation
regressions, while failing the phase with one new major, no minors and no blockers:

```text
INDEPENDENT_REAUDIT_V11=FAIL
V10_FINDINGS_FIXED=1/1_VERIFIED
BLOCKERS=0
MAJORS=1
MINORS=0
MAJOR_V11_001=WINDOWS_DRIVE_RELATIVE_REFERENCE_BYPASSES_CANONICAL_FILESYSTEM_CLASSIFIER_AND_PERSISTS
DP-122=NOT_VERIFIED
AT-DP-122=FAIL_INDEPENDENT_REAUDIT
CLOSURE_ELIGIBLE=NO
NEXT_STEP=REMEDIATION_V11_ONLY
EXPECTED_NEXT_BUNDLE=phase-11.22-event-system-audit-v12.tar.gz
```

Remediation V11 fixed that single finding under strict TDD — a red reproduction
suite first (`328 failed / 380 passed` on the new module, in a commit containing only
tests), then the minimum fix in the existing authority:

| Finding | Defect | Remediation |
| --- | --- | --- |
| `MAJOR-V11-001` | Windows defines both a drive-*root* path (`C:/name`) and a drive-*relative* path (`C:name`), and the latter is still a drive-qualified local filesystem reference (`ntpath.splitdrive("C:Windows") == ("C:", "Windows")`). The retained drive signature required a path separator after the colon (`re.compile(r"(?:^|/)[A-Za-z]:[\\/]")`), so no signature recognized `C:Windows`, `C:id_rsa`, `C:.ssh`, `D:ProgramData`, `Z:tmp`, `C:` or lowercase `c:id_rsa`; and because those values contain no separator at all, the final path-shape branch also declined to treat them as path-shaped. `is_private_filesystem_reference("C:id_rsa")` returned `False`, the canonical identifier validator accepted, and the value was durably appended — across all 13 shared identifier-bearing channels, through both official repositories and through a manual `publish_event(...)` call. `id_rsa` was already a sensitive private-file marker, so the drive-designator colon was shielding a known private location rather than creating a naming ambiguity | the **existing** canonical classifier in `_PRIVATE_FILESYSTEM_PATTERNS` gains one structurally minimal signature for the drive *designator* itself — `re.compile(r"^[A-Za-z]:")` — evaluated on the canonical lexical analysis form **before** any separator heuristic or the generic "no separator means not path-shaped" escape. The rule is anchored to the start of the whole reference because that is the only position where drive-relative syntax has that meaning, and because the frozen contract deliberately preserves wrapped *segment-colon* logical identifiers (`provider/a:1/model`, `provider/x:0/step`, `cmm/v2:3/detail`). The V10 segment-boundary rule for a rooted drive token carried by an allowlisted wrapper is retained verbatim, so the whole V10 family keeps its audited verdict. No literal was appended for `Windows`, `ProgramData`, `id_rsa`, `.ssh` or `tmp`; fresh drives and remainders (`C:a`, `X:foo.bar`, `E:secret.txt`, `Q:zzz-not-a-real-location`) are refused by the same structural rule. Analysis-only: no filesystem I/O, no `Path.resolve()`, no grammar widening, no rewriting of an accepted persisted identifier, and no second path/URI/Windows policy module |

The one production rule lives in `is_private_filesystem_reference()`, reached by
every persisted identifier channel through `validate_platform_identifier()` — the
single shared authority the phase already had — so no channel can be patched alone.
No second event, identifier, URI, path, drive-root, timestamp, registry, repository,
runtime, resolver, loader, engine or policy infrastructure was introduced, and
`AGENT_RUNTIME_TO_DOMAIN_IMPORTS` remains `0`.

```text
REMEDIATION_V11_TESTS=708 passed (initial red 328 failed / 380 passed)
V10_REGRESSIONS=475 passed (preserved)
V9_REGRESSIONS=397 passed (preserved)
V8_REGRESSIONS=289 passed (preserved)
V7_REGRESSIONS=127 passed (preserved)
V6_REGRESSIONS=127 passed (preserved)
V5_REGRESSIONS=71 passed (preserved)
V4_REGRESSIONS=23 passed (preserved)
V3_REGRESSIONS=44 passed (preserved)
V2_REGRESSIONS=126 passed (preserved)
V1_REGRESSIONS=86 passed (preserved)
PRIOR_REMEDIATION_REGRESSIONS=2473 passed (V1-V11)
PHASE_SUITE=tests/events/ 3979 passed
AT_DP_122=889 passed (749 prior + 140 V11)
KERNEL_ADAPTER_TESTS=76 passed
PHASE9_EVENT_REGRESSIONS=tests/agent_runtime/ 3635 passed
DOMAIN_DP033_REGRESSIONS=tests/domains/ 11824 passed
DOMAIN_DP033_ACCEPTANCE=92 passed
ORCHESTRATION_EVENT_TESTS=tests/orchestration/ 498 passed
VALIDATION_EVENT_TESTS=tests/validation/ 533 passed
WORKFLOW_EVENT_TESTS=tests/workflows/ 46 passed
CLOSED_PHASE_ACCEPTANCES=185 passed, 1 warning
EVENT_INVENTORY=tests/**/*event*.py 1270 passed
ARCHITECTURE_AND_SECURITY_GATES=294 passed
GLOBAL_PYTEST=26048 collected, 26048 passed, 1 warning, 0 failed
CHANGED_FILE_RUFF=PASS
GLOBAL_RUFF_COUNT=810 (V11 baseline 810, no new debt)
GLOBAL_RUFF_NO_NEW_DEBT=PASS
FORMAT_CHECK=PASS
COMPILEALL=PASS
GIT_DIFF_CHECK=PASS
AGENT_RUNTIME_TO_DOMAIN_IMPORTS=0
```

Both alternative fixes were rejected. Appending the audited literals (`Windows`,
`ProgramData`, `id_rsa`, `.ssh`, `tmp`) would have left the classifier a denylist of
selected spellings — the exact V8 defect — and anchoring the drive rule at a
path-segment boundary instead of the whole reference would have refused the wrapped
segment-colon logical identifiers the frozen contract deliberately preserves. The
drive *designator* is therefore classified structurally, in the authority that already
existed. The immutable Audit V1 report, the immutable Re-audit V2–V11 reports, and the
immutable V1–V11 bundles are preserved byte-identical. The exact Remediation V11 HEAD,
tree and V12 bundle SHA-256 are reported in the remediation handoff rather than
embedded here, for the same self-reference reason as the earlier evidence records.
