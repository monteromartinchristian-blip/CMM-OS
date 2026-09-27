# Phase 11 — Event System reference

**Status:** `REMEDIATED_AFTER_REAUDIT_V5_PENDING_INDEPENDENT_REAUDIT`
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
**Production package:** `cmm/events/` (9 modules) plus additive Phase 9 hardening
**Contract catalog:** `cmm/events/event_catalog.py`

`DP-122=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION`
`AT-DP-122=PASS_REPORTED`

Phase 11.22 was implemented, failed independent Audit V1, failed independent
Re-audit V2, failed independent Re-audit V3, failed independent Re-audit V4,
failed independent Re-audit V5 and has been **remediated** after each. It is not
closed, not independently verified and not complete: the `VERIFIED_EXISTING`
marker may only be written by the independent re-audit of the V6 bundle. See §27
for the Remediation V4 record and §28 for the Remediation V5 record.

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
| integer / count / duration | a real finite number (`duration_ms`, `count`, `attempts`, `sequence`) |
| version | a bounded number or bounded version token (`version`, `schema_version`) |
| timestamp | the canonical ISO-8601 string form only (`occurred_at`, `emitted_at`) |
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
scan; a persisted `metadata`/`permissions` key is itself content and is judged by
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

### 19.6 Remediation V5 measurements (current)

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
global pytest                   23131 passed, 1 warning, 0 failed
global Ruff                          810 (V5 baseline 810, no new debt)
```

The V5 production tree measured `991` in `tests/events/` and `23060` globally.
Both V5 deltas are accounted for exactly: the new V5 regression module adds `71`
and the strengthened `AT-DP-122` adds `29`, so the global suite moves
`23060 → 23131` (`+71`), `tests/events/` moves `991 → 1091` (`+100`), and
`AT-DP-122` itself moves `95 → 124`.

## 20. Global test evidence

Frozen pre-Phase-11.22 baseline: `22069 passed, 1 warning`. V1 implementation:
`22558 passed, 1 warning`. Post-remediation V1: `22694 passed, 1 warning, 0 failed`.
Post-remediation V2: `22962 passed, 1 warning, 0 failed`. Post-remediation V3:
`23025 passed, 1 warning, 0 failed` (+63 over the V2 remediation figure: 44 new V3
adversarial regressions and 19 strengthened `AT-DP-122` connected scenarios).
Post-remediation V4: `23060 passed, 1 warning, 0 failed` (+35 over the V3
remediation figure: 23 new V4 adversarial regressions and 12 strengthened
`AT-DP-122` connected scenarios). Post-remediation V5: `23131 passed, 1 warning,
0 failed` (+71 over the V4 remediation figure: 71 new V5 adversarial regressions.
The 29 strengthened `AT-DP-122` connected scenarios are already inside the global
count as part of `tests/events/`). The single retained warning is the pre-existing
unrelated `starlette` `anyio` `DeprecationWarning`.

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
Remediation V1 change, is Ruff-clean. The global count after remediation is `810`:
identical to the audited V1 HEAD and one below the frozen baseline. The only delta
against the baseline is one pre-existing violation removed while editing
`tests/conftest.py` to add the test data-directory isolation fixture. No unrelated
violation was fixed, no global auto-fix was run, and no file outside the Phase 11.22
delta was touched.

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

Fresh independent ChatGPT re-audit of the exact-HEAD Phase 11.22 **V6** bundle
(`phase-11.22-event-system-audit-v6.tar.gz`, produced with `git archive` from the
final Remediation V5 HEAD). This document states only
`REMEDIATED_AFTER_REAUDIT_V5_PENDING_INDEPENDENT_REAUDIT`; Phase 11.22 must not be
described as closed, independently verified, re-audited, passed or complete, and
Phase 11.23 has not begun.

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
