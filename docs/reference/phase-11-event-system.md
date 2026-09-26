# Phase 11 — Event System reference

**Status:** `IMPLEMENTED_PENDING_INDEPENDENT_AUDIT`
**Phase:** 11.22 — Event System
**Design Point:** `DP-122 — One Canonical, Durable, Replayable Platform Event System`
**Acceptance Test:** `AT-DP-122` — `tests/events/test_phase11_22_dp122_acceptance.py`
**Design specification:** `docs/superpowers/specs/2026-09-26-phase-11.22-event-system-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-09-26-phase-11.22-event-system-implementation-plan.md`
**Implementation agent prompt:** `docs/superpowers/prompts/2026-09-26-phase-11.22-event-system-implementation-agent-prompt.md`
**Production package:** `cmm/events/` (9 modules) plus additive Phase 9 hardening
**Contract catalog:** `cmm/events/event_catalog.py`

`DP-122=IMPLEMENTED_PENDING_INDEPENDENT_VERIFICATION`
`AT-DP-122=PASS_REPORTED`

Phase 11.22 is **implemented and awaiting independent audit**. It is not closed,
audited, verified or complete, and the `VERIFIED_EXISTING` marker may only be
written by the independent audit.

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
| `domain.execution.completed` | `operation.executed` | `domain_id`, `status`, `execution_id`, `duration_ms` |
| `domain.resolution.completed` | `domain.selected` | `domain_id`, `status` |
| `domain.approval.requested` | `approval.requested` | `domain_id`, `status`, `approval_id` |
| `domain.approval.received` | `approval.resolved` | `domain_id`, `status`, `approval_id` |
| `domain.memory.updated` | `memory.updated` | `domain_id`, `status` |
| `workflow.started` | `workflow.started` | `workflow_id`, `run_id`, `status` |
| `workflow.running` | `workflow.started` | `workflow_id`, `run_id`, `status` |
| `workflow.paused` | `workflow.paused` | `workflow_id`, `run_id`, `status`, `node_id` |
| `workflow.completed` | `workflow.completed` | `workflow_id`, `run_id`, `status` |
| `workflow.failed` | `workflow.failed` | `workflow_id`, `run_id`, `status`, `error_code` |

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
| schema version | `header.schema_version` | existing, deserialization now fails closed on an unsupported version |
| occurrence time | `header.occurred_at` | existing |
| emission time | `header.emitted_at` | existing |
| safe producer identity | `header.producer` | **additive optional** |
| aggregate/reference identity | `header.aggregate_id` | **additive optional** |
| structured safe payload | `payload.data` | existing |
| correlation ID | `header.correlation_id` | existing |
| causation ID | `header.causation_id` | existing |
| sensitivity | `header.sensitivity` | existing |

`source` keeps its Phase 9 meaning (the emitting runtime surface) and was **not**
repurposed as a producer alias. Old constructors stay valid, old serialized
events still deserialize, and `event_fingerprint()` covers event ID, type, schema
version, both timestamps, producer, aggregate identity and a canonical rendering
of the payload.

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
* reading re-validates every record through the canonical factory and recomputes
  its fingerprint, so a tampered, truncated, malformed, unsupported-version or
  duplicated record raises `AgentRuntimeEventPersistenceCorruptionError`;
* corrupt evidence is never silently skipped, repaired or guessed;
* tests use temporary directories only, and the suite redirects
  `CMM_OS_DATA_DIR` so no test can write to a real user data location.

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
versions, and boolean lifecycle facts.

Rejected **before** durable persistence: prompts, system/developer prompts, raw
user text, chain-of-thought, hidden/raw reasoning, provider request/response
payloads, credentials, API keys, passwords, tokens, bearer-shaped values,
authorization headers, cookies, raw tracebacks, opaque runtime objects, arbitrary
binary payloads, non-finite floats and any unrecognised payload key.

Invariants:

```text
EVENTS_GRANT_NO_AUTHORITY
REPLAY_GRANTS_NO_AUTHORITY
HIDDEN_REASONING_NEVER_PERSISTED
RAW_PROVIDER_PAYLOAD_NEVER_PERSISTED
CREDENTIALS_NEVER_PERSISTED
TOKENS_NEVER_PERSISTED
UNKNOWN_EVENT_TYPES_FAIL_ACCORDING_TO_CANONICAL_REGISTRY
CORRUPT_PERSISTED_EVENTS_FAIL_CLOSED
SAME_ID_DIFFERENT_CONTENT_FAILS_CLOSED
REPLAY_TO_SIDE_EFFECT_SUBSCRIBERS_DEFAULT_DENIED
DLQ_REPLAY_CANNOT_BYPASS_SUBSCRIBER_POLICY
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

`AT-DP-122=PASS_REPORTED`

## 19. Test evidence

| Gate | Result |
| --- | --- |
| Phase 11.22 focused tests (`tests/events/`) | `489 passed` |
| `AT-DP-122` connected acceptance | `PASS` (see §18) |
| Focused event baseline | `856 passed` (frozen baseline `856`) |
| Event inventory (`tests/**/*event*`) | `1269 passed` (baseline `1204`, +65) |
| Closed-phase connected regressions | see §19.1 |
| Global pytest | `22558 passed, 1 warning` |
| Changed/new file Ruff | `PASS` (0 violations) |
| Global Ruff count | `810` (frozen pre-existing baseline `811`, no new debt) |
| Format check (`ruff format --check`, phase delta) | `PASS` |
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

One inherited platform architecture gate was extended, not weakened:
`tests/platform/test_architecture.py` sanctions `cmm.events` as the fifth bounded
`cmm.platform` consumer, with the same one-way direction rule and no new platform
authority. One inherited Phase 11.3 acceptance assertion was updated to the
corrected production graph: the production local runtime now composes the
canonical service set **plus exactly the Phase 11.22 event-system services**.

## 20. Global test evidence

Frozen baseline: `22069 passed, 1 warning`. Post-implementation:
`22558 passed, 1 warning` (489 new Phase 11.22 tests). The single retained warning
is the pre-existing unrelated `starlette` `anyio` `DeprecationWarning`.

## 21. Ruff baseline treatment

The frozen global baseline is `811` pre-existing violations, which Phase 11.22
does **not** clean up. At the frozen implementation base the same command reports
`811`, confirming the baseline is exact.

Every Phase 11.22-created or Phase 11.22-modified Python file is Ruff-clean. The
global count after implementation is `810`: the only delta is one pre-existing
violation removed while editing `tests/conftest.py` to add the test data-directory
isolation fixture. No unrelated violation was fixed, no global auto-fix was run,
and no file outside the Phase 11.22 delta was touched.

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

Independent ChatGPT audit of the exact committed implementation bundle. This
document states only `IMPLEMENTED_PENDING_INDEPENDENT_AUDIT`; Phase 11.22 must not
be described as closed, audited, verified or complete, and Phase 11.23 has not
begun.
