# Phase 11 — Application Backend reference

**Status:** `CLOSED_AFTER_INDEPENDENT_REAUDIT_V1_PASS`
**Phase:** 11.3 — Application Backend
**Requirement:** `F11-017 — Canonical Application Backend`
**Design Point:** `DP-103 — Versioned, Fail-Closed Application Gateway`
**Acceptance Test:** `AT-DP-103` — `tests/application/test_phase11_3_dp103_acceptance.py`
**Design specification:** `docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-09-16-phase-11.3-application-backend-implementation-plan.md`
**Remediation V1 design:** `docs/superpowers/specs/2026-09-16-phase-11.3-remediation-v1-design.md`
**Remediation V1 plan:** `docs/superpowers/plans/2026-09-16-phase-11.3-remediation-v1-implementation-plan.md`
**Production packages:** `cmm/application/` (10 modules), `cmm/api/` (5 modules)
**Focused suites:** `tests/application/`, `tests/api/`
**Architecture gates:** `tests/application/test_architecture.py` (58 tests), `tests/api/test_architecture.py` (51 tests)
**OpenAPI gate:** `tests/api/test_openapi.py` (22 tests)
**Design commit:** `3a2bc9e` — `docs(phase11): design 11.3 application backend`
**Plan commit:** `325bc40` — `docs(phase11): plan 11.3 application backend`
**First implementation commit:** `ffadb94` — `build(application): add phase 11.3 http boundary`
**AT-DP-103 implementation milestone HEAD:** `2201d0009b47db7128bab895f4ad25f069712781` — an intermediate implementation milestone observed while preparing the first documentation, not the exact audit candidate
**Independent Audit V1:** `docs/audits/phase-11.3-application-backend-independent-audit-v1.md` — `FAIL`; audited HEAD `5fd8cc3b171faec88b802be920ad09ac53224e75`; audited tree `1cfbe114369ac89d1c2563a9787c5ebf096c64df`; bundle SHA-256 `17377075eae659d123ca4ee909fa8f0cef01f625f40c2d498b34f22a47690199`; report commit `c111a57` — immutable and unmodified
**Remediation V1:** implemented and independently re-audited; `MAJOR_01=VERIFIED_REMEDIATED`, `MINOR_01=VERIFIED_REMEDIATED`
**Independent Re-audit V1:** `docs/audits/phase-11.3-application-backend-independent-reaudit-v1.md` — `PASS`; `BLOCKERS=0`; `MAJORS=0`; `MINORS=0`; `F11_017=VERIFIED_EXISTING`; `DP_103=VERIFIED_EXISTING`; `AT_DP_103=PASS`; audited HEAD `4525f72391792e623730af69e95bcd054ce3cddf`; audited tree `0b650c8133111754452940c74a1bc72f24a0df23`; bundle SHA-256 `152276776b9e2765edb67adcd95b6ee3d2b565d416e1e4bce665777a078d9618`; report commit `c21f2e257a1995b748b78b65b622ff68ca3e6d38`; `CLOSURE_ELIGIBLE=YES`

Phase 11.3 is **implemented, independently re-audited and closed after
Independent Re-audit V1 `PASS`**. Historical Independent Audit V1 `FAIL`
(`BLOCKERS=0`, `MAJORS=1`, `MINORS=1`) remains immutable. Remediation V1 repaired
exactly `MAJOR_01` and `MINOR_01`, and the independent re-audit verified both
findings as remediated while preserving the canonical Application Backend
architecture.

```text
PHASE11_3=CLOSED

INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V1=PASS

BLOCKERS=0
MAJORS=0
MINORS=0

MAJOR_01=VERIFIED_REMEDIATED
MINOR_01=VERIFIED_REMEDIATED

F11_017=VERIFIED_EXISTING
DP_103=VERIFIED_EXISTING
AT_DP_103=PASS

AT_DP_102=PASS
AT_DP_101=PASS
AT_DP_134=PASS

AUDITED_HEAD=4525f72391792e623730af69e95bcd054ce3cddf
AUDITED_TREE=0b650c8133111754452940c74a1bc72f24a0df23
REAUDIT_BUNDLE_SHA256=152276776b9e2765edb67adcd95b6ee3d2b565d416e1e4bce665777a078d9618

CLOSURE_ELIGIBLE=YES
```

## 1. Purpose and ownership boundary

Phase 11.3 adds the missing product boundary between clients and the canonical
platform: one versioned, transport-neutral, fail-closed application backend.

```text
Client
  |
  v
cmm/api  (HTTP / OpenAPI / SSE adapter)
  |
  v
cmm/application  (public application semantics)
  |
  +--> Phase 11.1 ApplicationContainer (composition/readiness)
  |
  +--> canonical session boundary (cmm.runtime.sessions)
  |
  v
cmm/orchestration  (canonical central request path)
  |
  v
existing canonical owners (domain, agent runtime, ...)
```

The backend is a **projection and adaptation layer**. It owns public
application semantics — contracts, error mapping, command/query services, the
narrow idempotency seam, health/capability projection and transport-neutral
stream envelopes — and owns no canonical subsystem authority. It is
deliberately built as a stable product boundary, not as a second platform
kernel.

No phase before Phase 11.3 owned an HTTP surface, an application-service facade
or API versioning; `docs/reference/phase-11-orchestration-layer.md` §15 and
`docs/reference/phase-11-integration-core.md` both record that surface as
deferred to Phase 11.3. This phase delivers it.

## 2. Canonicalization matrix

| Concern | Owner after Phase 11.3 | Phase 11.3 role |
| --- | --- | --- |
| Public application contracts (`ApplicationRequest`, `ApplicationResponse`, `ApplicationError`, `ApplicationStreamEvent`, ...) | `cmm/application/contracts.py` — **new** | Definition and versioned evolution |
| Public error model and safe mapping | `cmm/application/errors.py` — **new** | Fail-closed mapping, safe messages |
| Application commands/queries | `cmm/application/gateway.py`, `sessions.py`, `requests.py`, `capabilities.py`, `health.py` — **new** | Explicit dispatch, no second authority |
| Idempotency seam | `cmm/application/idempotency.py` — **new**, in-memory only | Repeatable public commands |
| Transport adaptation, HTTP status mapping, OpenAPI, SSE framing | `cmm/api/` — **new** | Adapter only, never an owner |
| Composition and readiness | Phase 11.1 `cmm/platform/` — reused, unchanged | One new service binding |
| Central request processing | Phase 11.2 `cmm/orchestration/` — reused, unchanged | Delegation through `Orchestrator.orchestrate` |
| Session state, revision, concurrency | `cmm.runtime.sessions` (`InMemorySessionStore` / `FileSessionStore`) — reused, unchanged | Public projection + revision assertion |
| Domain selection | `cmm.domains` canonical resolver/registry — reused, unchanged | Never reselected |
| Agent selection | `cmm.agent_runtime` canonical registry/resolver — reused, unchanged | Never reselected |
| Provider identity/state | Phase 11.34 `kernel/llm` Provider Registry — reused, unchanged | Not reached by the public path |
| Model routing / Model Gateway / Routing Policy Engine | not implemented (later Phase 11 work) | Explicitly out of scope |
| Event Bus, workflow/operation/execution/validation engines, memory/knowledge stores, plugin lifecycle, auth/RBAC, durable application storage | owned by their canonical/closed subsystems or not implemented | Not duplicated, not fabricated |

## 3. Public package surface

### 3.1 `cmm/application/` — transport-neutral application core

| Module | Owns |
| --- | --- |
| `contracts.py` | The frozen versioned public contracts and their bounds (`APPLICATION_API_VERSION = "v1"`, `ApplicationOperation`, `ApplicationStatus`, `ApplicationErrorCode`, `CapabilityStatus`, `StreamEventKind`, `ApplicationRequest`/`ApplicationCommand`/`ApplicationQuery`, `ApplicationResponse`, `ApplicationSession`, `ApplicationMessage`, `ApplicationHealth`, `ApplicationCapability`, `ApplicationStreamEvent`, `ApplicationCancellationRequest`) and the closed command/query separation sets |
| `errors.py` | The safe public error model (`ApplicationServiceError` and its typed subclasses), `safe_error_from_exception` and `failed_response` |
| `idempotency.py` | `IdempotencyRepository` (Protocol), `InMemoryIdempotencyRepository`, `IdempotencyRecord`, `fingerprint_command` |
| `sessions.py` | `SessionApplicationService` — session create/read and `require_revision` over the canonical session store |
| `requests.py` | `RequestApplicationService` — the public message path into the canonical `Orchestrator` and the safe projection of its result |
| `health.py` | `HealthApplicationService` — safe readiness projection |
| `capabilities.py` | `CapabilityApplicationService` and the frozen `build_default_capabilities()` declarations |
| `gateway.py` | `ApplicationGateway` — the one canonical public entrypoint (`handle`) |
| `platform_module.py` | `build_application_composition_module()` — the Phase 11.1 composition contribution |
| `__init__.py` | The public package re-export surface |

The package imports no web framework, performs no direct network I/O, and holds
no service singleton or module-global state.

### 3.2 `cmm/api/` — HTTP/OpenAPI/SSE adapter

| Module | Owns |
| --- | --- |
| `app.py` | `create_app(gateway)` — the FastAPI application, the seven `/v1` routes, the correlation/idempotency header handling and the fail-closed exception handlers |
| `models.py` | Transport DTOs (`ApiVersion`, `CreateSessionBody`, `MessageBody`, response/error/health/capability/session models) and their projections |
| `errors.py` | The frozen application-error-code → HTTP status map, framework-status classification and the one public error envelope |
| `streaming.py` | `serialize_sse`, `events_for_response`, `sse_frames`, `SSE_MEDIA_TYPE = "text/event-stream"` |
| `__init__.py` | The adapter package re-export surface |

The adapter never reaches a canonical internal owner directly: it invokes
`cmm.application` only, and the architecture gates enforce that.

## 4. The `/v1` surface

The published surface is exactly seven routes and is frozen by
`tests/api/test_openapi.py`:

| Method | Path | Operation | Success status | Idempotent |
| --- | --- | --- | --- | --- |
| `GET` | `/v1/health` | `health.get` | `200` | no (query) |
| `GET` | `/v1/capabilities` | `capabilities.list` | `200` | no (query) |
| `POST` | `/v1/sessions` | `sessions.create` | `201` | yes |
| `GET` | `/v1/sessions/{session_id}` | `sessions.get` | `200` | no (query) |
| `POST` | `/v1/sessions/{session_id}/messages` | `messages.submit` | `200` | yes |
| `POST` | `/v1/sessions/{session_id}/messages/stream` | SSE stream of the same `messages.submit` command | `200` (`text/event-stream`) | yes |
| `POST` | `/v1/requests/{request_id}/cancel` | `requests.cancel` | `200` | no |

Public headers:

| Header | Direction | Meaning |
| --- | --- | --- |
| `X-Request-ID` | request/response | Public correlation identity; an unusable caller value is rejected, and every response — success, error or stream — carries the correlation identity |
| `Idempotency-Key` | request | Opt-in repeatable replay for the two idempotent commands; the session and message identity come from the path and body, never from a header |

Deliberately absent from v1 (see §17): `GET /v1/domains`, `GET /v1/agents`, and
every route for goals, workflows, operations, approvals, memory, knowledge,
bots, tools, configuration, events, metrics, backups and plugins. There is no
unversioned twin of any route, and no `/v2` surface.

The frozen success status of the cancellation route is `200`, but no canonical
cancellable owner exists, so that route currently always answers
`503 CAPABILITY_UNAVAILABLE` and never a success (see §11). The written answer to
a cancellation request is the safe failure envelope, and no cancellation key is
ever recorded.

## 5. Public contracts and versioning

- `APPLICATION_API_VERSION = "v1"` is the single supported public version. A
  request that does not agree with it fails closed with `UNSUPPORTED_VERSION`;
  the HTTP adapter serves no version-2 path at all.
- Request role is validated before dispatch: the gateway rejects a request whose
  role, operation and version do not agree, so a query can never carry a command
  operation and vice versa.
- Command/query separation is closed by construction: `QUERY_OPERATIONS` is
  `{health.get, capabilities.list, sessions.get}` and `COMMAND_OPERATIONS` is
  `{sessions.create, messages.submit, requests.cancel}`.
- Public inputs are bounded before any internal call: identifiers (256),
  idempotency keys (256), message content (64 000), generic strings (16 384),
  public metadata (128 items, nesting depth 6) and message metadata must be
  secret-free, JSON-native and recursively immutable.
- Responses are frozen envelopes (`request_id`, `api_version`, `status`,
  `data`, `error`) so clients never see an ad-hoc shape.

## 6. Safe public error model

`cmm/application/contracts.py` declares eleven closed public error codes, and
`cmm/api/errors.py` maps them to HTTP status. The mapping is frozen and total:

| Public code | HTTP | Raised when |
| --- | --- | --- |
| `INVALID_REQUEST` | `400` | Malformed role/operation/version, unbounded or missing public field, unusable `X-Request-ID` |
| `UNSUPPORTED_VERSION` | `400` | `api_version` other than `v1` |
| `POLICY_DENIED` | `403` | Canonical policy denied the request |
| `RESOURCE_NOT_FOUND` | `404` | Unknown session, or an unknown public route |
| `CONFLICT` | `409` | Duplicate session creation (`SESSION_ALREADY_EXISTS`) |
| `IDEMPOTENCY_CONFLICT` | `409` | Same key with a materially different command (`IDEMPOTENCY_KEY_REUSED`) |
| `CONCURRENCY_CONFLICT` | `409` | Stale session revision (`SESSION_REVISION_STALE`) |
| `APPROVAL_REQUIRED` | `409` | Canonical approval requirement |
| `CANCELLED` | `409` | A cancelled public result |
| `CAPABILITY_UNAVAILABLE` | `503` | Deferred/unowned capability, e.g. cancellation |
| `INTERNAL_FAILURE` | `500` | Any unexpected internal defect, reported without detail |

Rules the implementation holds to:

- the gateway's `handle` is the fail-closed public boundary: every accepted
  request that raises becomes a safe failure response, and no exception text,
  traceback, internal path, class name, provider credential, hidden reasoning or
  raw internal payload can cross it;
- HTTP status mapping lives only in `cmm/api`; application status and HTTP
  status are deliberately different contracts;
- framework routing outcomes are typed public failures (`UNKNOWN_ROUTE`,
  `METHOD_NOT_ALLOWED`), and transport validation failures become the one public
  `INVALID_REQUEST` envelope;
- a malformed body never reaches a handler, and an unexpected defect is reported
  as `INTERNAL_FAILURE` with a safe message only;
- `details` carries at most a public `reason_code`, never internal state.

## 7. Session behavior and revision semantics

`SessionApplicationService` is the only public session surface and it delegates
to the canonical session store:

- `create_session` creates one canonical session and returns its public
  projection; creating an existing identifier is a `CONFLICT`
  (`SESSION_ALREADY_EXISTS`) and never mutates, replaces or re-versions the
  existing session;
- `get_session` projects the current canonical state — it is not a cached copy;
- `require_revision(session_id, expected_revision)` asserts the caller's
  revision expectation. `None` asserts nothing beyond existence; any other value
  must equal the current canonical revision, otherwise the caller holds stale
  state and receives `CONCURRENCY_CONFLICT` (`SESSION_REVISION_STALE`).

Phase 11.3 invents no concurrency subsystem. `POST
/v1/sessions/{session_id}/messages` accepts an optional
`expected_session_revision` (`StrictInt`, `>= 0`, so `true` cannot be read as
revision `1`), and the session preconditions are evaluated **before** the
canonical pipeline, so an absent or stale session can never reach orchestration.

## 8. Idempotency

Phase 11.3 introduces exactly one narrow backend-owned seam because idempotency
is part of a public command boundary:

- `IdempotencyRepository` is a two-method protocol (`get`, `put`);
  `InMemoryIdempotencyRepository` is the official in-memory implementation
  (bounded to 1024 records by default, with deterministic insertion-ordered
  eviction, deliberately not thread-safe and not durable) and
  `IdempotencyRecord` binds one key to one fingerprint and one safe response;
- `fingerprint_command` is a SHA-256 digest over the canonical JSON of the
  public command minus `request_id` and `idempotency_key`. It is stable across
  processes and independent of mapping order or `hash()`, and it excludes
  secrets, volatile timestamps and implementation details;
- only `sessions.create` and `messages.submit` opt into replay, and only when
  the caller supplies an `Idempotency-Key`;
- replay requires the same key **and** the same fingerprint: an equivalent
  repeat returns the stored safe response, while the same key with a materially
  different command fails closed with `IDEMPOTENCY_CONFLICT`;
- recording happens strictly after a terminal safe response exists, so a raised
  failure is never recorded and a key is never bound to a defect;
- a generated message identity is a pure function of the idempotency key, so a
  keyed retry is canonically the same command and replays instead of conflicting,
  while two independent submissions remain two public messages;
- the complete keyed `get -> execute -> put` sequence is **one atomic critical
  section** for a gateway instance: `ApplicationGateway` owns exactly one
  private, in-process `threading.Lock` (`self._idempotency_lock`) and holds it
  across fingerprint resolution, the stored-record read, the replay/conflict
  decision, the canonical execution and the record write. A second caller of the
  same key therefore can never observe the absent record while the first is
  still executing, so one keyed semantic command enters the canonical owner at
  most once while an equivalent keyed command is in flight;
- the lock is an implementation detail of one gateway instance: it is not a
  constructor argument, not a collaborator, not registered in
  `ApplicationContainer`, not persisted and not exported, and the v1 guarantee is
  deliberately local rather than distributed. Commands without an idempotency key
  and every query keep their lock-free dispatch path, so the repair serializes
  only keyed command traffic;
- no `IdempotencyDatabase`, durable store, distributed lock service, lock
  registry, transaction manager, background coordinator or per-key lock lifecycle
  is introduced. Durable idempotency persistence is deferred to storage work
  (Phase 11.15).

The atomic critical section is the Remediation V1 repair of Independent Audit V1
`MAJOR_01=NON_ATOMIC_IDEMPOTENCY_UNDER_CONCURRENT_REQUESTS`. Before it, two
concurrent same-key commands could both observe `get(key) -> None` and both enter
the canonical owner, which the audit reproduced as two orchestration
`request_received` events and two canonical decision records. The public
repository contract, the fingerprint semantics and the UUID5 retry identity are
unchanged by the repair: the recorded defect was interleaving, not semantics.

## 9. Orchestration adapter

`RequestApplicationService.submit_message` is the one public path into
canonical orchestration:

1. it re-validates the message contract and the session precondition;
2. it builds a canonical `OrchestrationRequest` (`channel=API`, session identity,
   message id/content/content_type/metadata) from the thawed public projection,
   so the orchestrator never receives a frozen public container or shared
   mutable state;
3. it calls the real Phase 11.2 `Orchestrator.orchestrate` exactly once;
4. it fails closed with `INTERNAL_FAILURE` if the orchestrator raises, returns a
   non-result, or returns a result for a different request;
5. it projects the canonical decision into the safe public response.

Domain and agent authority stays canonical: the application layer has no domain
or agent selection surface at all, and no application-layer reselection is
possible. The canonical, deterministic outcome is projected faithfully — a
public message carries no intent hint, so the canonical intent resolver answers
`NEEDS_CLARIFICATION` and no model response is fabricated (see §19).

## 10. Health and capability discovery

- `GET /v1/health` reports safe readiness derived from the Phase 11.1
  `ApplicationContainer` and the application services, plus static version
  information. It exposes no secrets, provider credentials, internal paths, raw
  dependency objects, arbitrary configuration or stack traces, and no
  implementation identity (no class or module names).
- `GET /v1/capabilities` projects an explicit, frozen declaration list. The
  service inspects no imports, registries or live owners, so availability can
  never be inferred from a module name, route name, import path or the existence
  of a class, and discovery cannot become a second registry.
- The initial v1 declarations distinguish honestly:
  - `AVAILABLE` — `capabilities`, `health`, `messages`, `sessions`, `streaming`;
  - `UNAVAILABLE` — `request-cancellation` with reason `NO_CANCELLABLE_OWNER`
    (the stable cancellation surface exists, but no canonical cancellable owner
    does);
  - `DEFERRED` — `agents`, `backups`, `domains`, `metrics`, `model-routing`,
    `plugins`, each with reason `OWNER_NOT_IMPLEMENTED`.
- Declaration order is canonical (sorted by capability id) so two processes
  produce the same public result, and no declaration carries a class name,
  module name or runtime object.

## 11. Streaming and cancellation

Streaming is a public delivery contract, not a new inference engine or event
system:

- the application layer owns the transport-neutral `ApplicationStreamEvent` with
  the closed kinds `started`, `data`, `completed`, `error`, `cancelled`; events
  are public-safe projections with session/request correlation identity, no
  hidden reasoning and no raw internal payload, and completion/error is explicit
  with deterministic order inside one stream;
- `cmm/api` adapts that to Server-Sent Events (`text/event-stream`) through
  `serialize_sse` / `events_for_response` / `sse_frames`. WebSockets are not
  implemented;
- `POST /v1/sessions/{session_id}/messages/stream` dispatches the same versioned
  `messages.submit` command **once**, before the response body starts, and
  streams that single already-computed result. A command can therefore never
  re-run inside a stream, and no exception text, traceback or internal payload
  can enter a frame;
- a failed application response is delivered in-band as a terminal `error`
  event with HTTP `200`, which is what makes the failure readable by an SSE
  client; a malformed body never reaches the route and answers with the one
  public error envelope;
- cancellation is explicit and honest: `POST /v1/requests/{request_id}/cancel`
  always answers `503 CAPABILITY_UNAVAILABLE` with the frozen safe message
  (`CANCELLATION_UNAVAILABLE_MESSAGE`) and empty error details, because the
  synchronous orchestration boundary has no active-request runtime to cancel.
  The `request-cancellation` capability declaration carries the reason code
  `NO_CANCELLABLE_OWNER`. No active-request repository, cancellation registry,
  scheduler, queue or background worker system is created, no canonical owner is
  consulted on that path, no idempotency record is written and no runtime owner
  is fabricated to make the surface look complete.

## 12. OpenAPI and the HTTP framework

- The HTTP adapter uses FastAPI, matching the spec's §36 framework decision; the
  framework is imported only in `cmm/api`, never in `cmm/application`.
- The published OpenAPI document is deterministic and frozen: exactly the seven
  `/v1` paths, one published operation per route/method, unique and frozen
  client-visible operation ids, a summary and the frozen success status for
  every operation, the one public response envelope, the closed public error
  schema for every JSON operation, the bounded public request bodies and the
  frozen schema set.
- The document exposes no internal implementation name, no private schema class,
  no secret- or debug-shaped field and declares no authentication or
  authorization scheme (auth/RBAC is a later Phase 11 subphase).
- The streaming route is deliberately **not** published as the JSON envelope; it
  takes the same frozen message command and is documented as an SSE operation.

## 13. Dependency direction and architecture gates

The dependency rule is one-way:

```text
cmm/api  ->  cmm/application  ->  cmm/platform + cmm/orchestration + sanctioned canonical read adapters
```

Forbidden and gate-enforced: `cmm.platform`, `cmm.orchestration`, `kernel`,
`cmm.domains`, `cmm.agent_runtime` and every other lower layer importing
`cmm.application` or `cmm.api`.

Architecture gates:

| Gate | File | Tests | Enforces |
| --- | --- | --- | --- |
| Application architecture | `tests/application/test_architecture.py` | 58 | Lower layers never import the backend packages; only the backend packages import them; frozen internal/external import allowlists; the application core imports no transport or serialization stack; no parallel owner class; no second container; no active-request repository; no owner-shaped module; no durable storage driver; no migration directory; no provider/model-routing import or symbol; no service singleton |
| API architecture | `tests/api/test_architecture.py` | 51 | The API package imports no lower layer or canonical owner; internal imports are the application layer only; transport imports are the frozen allowlist; no string/reflection dispatch; lower layers do not import the API; no parallel owner class; frozen new-owner allowlist; no active-request repository; no owner-shaped module; no durable storage driver; no migration directory; no provider/model routing; no service singleton |
| OpenAPI | `tests/api/test_openapi.py` | 22 | The frozen §12 document properties |

The Phase 11.1 platform gate was adjusted once, as a documented Phase 11.1 test
adjustment: `tests/platform/test_architecture.py` now names the sanctioned
platform consumers as the allowlist `("orchestration", "application")` instead of
exempting `cmm.orchestration` alone, and `cmm.application` consumes the Phase
11.1 `ApplicationContainer` and composition contracts exactly as
`cmm.orchestration` does. Phase 11.1 and Phase 11.34 production semantics are
unchanged.

## 14. Phase 11.1 composition

`build_application_composition_module` returns a side-effect-free
`StaticCompositionModule` contribution containing exactly one public binding:

```text
service id        application.gateway
authority         application-public-gateway
owner             cmm.application
contract version  1.0.0
schema version    1
dependency        orchestration.orchestrator
runtime contract  the concrete cmm.application.gateway.ApplicationGateway
```

The module constructs nothing: the gateway is an already-built object supplied by
the composition root, and the declared runtime contract is the concrete
`ApplicationGateway`, so an unrelated object can never claim the public
application identity. `application-public-gateway` is the only authority claimed
— no provider, domain, agent, workflow, execution, validation, memory,
knowledge, session or orchestration authority is claimed, claimed twice or
re-declared — and the one declared dependency is a real graph edge: composing
the application module without the orchestration contribution fails closed
instead of reaching `READY`. Phase 11.1 remains the composition core and
`cmm.platform` still never imports `cmm.application`.

Construction-time validation is explicit rather than structural-guesswork: the
gateway and each application service reject a non-canonical collaborator with a
`TypeError` (the gateway accepts only the official application services and the
v1 in-memory idempotency repository; the session service accepts only a
canonical `InMemorySessionStore` or `FileSessionStore`; the request service
accepts only the canonical `Orchestrator`), so a wrong or cross-wired graph
cannot serve a request.

## 15. Security posture and side-effect boundary

- No direct external network I/O, no file I/O beyond the canonical
  `FileSessionStore` the session service may be composed with, and no database
  — no SQL/ORM driver, no migration directory, no durable application store.
- No secret, credential or token is read, stored or exposed; public metadata is
  bounded, secret-free and recursively immutable, and safe identifiers and
  timestamps are constrained by the public contracts.
- The public path reaches no provider, model, routing policy, plugin or
  background worker. The only owned side effects are one canonical session
  write through the canonical store, one orchestrator call whose own effects are
  Phase 11.2-owned (a safe decision record and a safe lifecycle event through
  the injected sink), and the bounded idempotency record.
- No authentication or authorization layer is implemented or faked; the OpenAPI
  document declares no auth scheme, and auth/RBAC remains a later Phase 11
  subphase.
- No hidden reasoning, raw internal exception, internal path or implementation
  identity is exposed on any public surface.

## 16. Test doubles

Tests use the official in-memory implementations of their canonical owners
(`InMemorySessionStore`, `InMemoryOrchestrationDecisionRepository`,
`RecordingOrchestrationEventSink`, `InMemoryIdempotencyRepository`) plus real
domain/agent objects. The connected acceptance test composes that graph itself
rather than importing fixtures, so it needs no cross-package import and no test
order.

## 17. Exclusions and deferred capabilities

Recorded with `F11-017` and implemented nowhere in Phase 11.3:

- **Domain/agent listing routes** (`GET /v1/domains`, `GET /v1/agents`) — optional
  in the spec and unnecessary for `DP-103`; absence is clearer than a
  placeholder.
- **Goals, workflows, operations, approvals, memory, knowledge, bots, tools,
  configuration, events, metrics, backups, plugins routes** — no canonical owner
  or safe adapter exists yet, so no route fabricates behavior.
- **Request cancellation runtime** — the surface is stable and honest
  (`CAPABILITY_UNAVAILABLE`, `503`, with the `request-cancellation` capability
  declaring the reason `NO_CANCELLABLE_OWNER`), but no active-request repository,
  cancellation registry or background worker system is created; the
  orchestration boundary is synchronous and exposes one safe result.
- **Durable idempotency persistence** — Phase 11.15 storage work; the official
  in-memory repository is the only Phase 11.3 implementation.
- **Model Gateway / Phase 11.35 Routing Policy Engine** — later routing work; the
  public path reaches no provider or model.
- **Authentication/authorization and RBAC** — Phase 11.13.
- **Plugin System lifecycle** — Phase 11.19.
- **Event Bus, scheduler, queue, distributed tracing, metrics infrastructure** —
  later Phase 11 observability/platform work; Phase 11.3 propagates existing
  references only.
- **CMMChat / CMM Bots consumption of the backend** — after Phase 11.3; no
  CMMChat integration is introduced.
- **Pagination, filters and sorting** — no list surface large enough to need them
  exists in v1; no pagination contract is invented.
- **WebSockets** — SSE is the only streaming transport.

No parallel Provider Registry, Domain Registry, Agent Registry, Session Store,
Workflow Registry, Operation Registry, validation runtime, memory/knowledge
store, Model Router, Model Gateway, Event Bus, plugin runtime, auth service or
durable storage is introduced by Phase 11.3.

## 18. Testing

The first table below is the historical pre-audit observation of the intermediate
implementation milestone `2201d0009b47db7128bab895f4ad25f069712781` (Python 3.14
in `.venv`, `python -m pytest -q`); it is preserved as the observation the Audit
V1 candidate evolved from.

| Suite | Command | Result |
| --- | --- | --- |
| Focused application | `python -m pytest -q tests/application` | 625 passed |
| Focused API | `python -m pytest -q tests/api` | 193 passed |
| `AT-DP-103` | `python -m pytest -q tests/application/test_phase11_3_dp103_acceptance.py` | 44 passed |

Remediation V1 observations on the committed remediation HEAD (same environment):

| Suite | Command | Result |
| --- | --- | --- |
| Focused application (whole subsystem) | `python -m pytest -q tests/application` | 630 passed |
| Focused gateway + idempotency | `python -m pytest -q tests/application/test_gateway.py tests/application/test_idempotency.py` | 135 passed |
| Connected `AT-DP-103` | `python -m pytest -q tests/application/test_phase11_3_dp103_acceptance.py` | 46 passed |
| Focused API | `python -m pytest -q tests/api` | 193 passed |
| Inherited acceptances (`AT-DP-102` / `AT-DP-101` / `AT-DP-134`) | `python -m pytest -q tests/orchestration/test_phase11_2_dp102_acceptance.py tests/platform/test_phase11_1_dp101_acceptance.py tests/llm/test_provider_registry_dp134_acceptance.py` | 131 passed |
| Architecture + OpenAPI gates | `python -m pytest -q tests/application/test_architecture.py tests/api/test_architecture.py tests/api/test_openapi.py tests/platform/test_architecture.py tests/orchestration/test_architecture.py` | 272 passed |

Remediation V1 added exactly five tests, all of them concurrency regressions:

| Test | Proves |
| --- | --- |
| `tests/application/test_gateway.py::test_concurrent_equivalent_idempotent_commands_execute_once` | Two simultaneous equivalent keyed commands enter the canonical dispatch exactly once and both observe the one stored response |
| `tests/application/test_gateway.py::test_concurrent_conflicting_idempotent_commands_reject_before_second_execution` | A simultaneous same-key conflicting command is rejected before it can execute anything; only one of the two competing semantic commands takes effect |
| `tests/application/test_gateway.py::test_a_raised_keyed_failure_releases_the_critical_section` | A command that raises inside the keyed critical section records nothing and leaves the section free for later commands |
| `tests/application/test_phase11_3_dp103_acceptance.py::test_scenario_i_concurrent_equivalent_commands_reach_the_owner_once` | On the real composed graph: one `orchestration.request_received` event, one canonical decision record and one idempotency record for two simultaneous equivalent keyed commands |
| `tests/application/test_phase11_3_dp103_acceptance.py::test_scenario_j_concurrent_conflicting_commands_reject_before_execution` | On the real composed graph: one canonical execution maximum, exactly one `IDEMPOTENCY_CONFLICT` and no second canonical decision |

All five force the audited interleaving deterministically with a test-only
two-party `threading.Barrier` gate at the repository lookup and bounded worker
joins; none of them relies on `time.sleep`. Against the pre-remediation gateway
the two focused and the two connected concurrent tests fail with duplicate
canonical execution (`entered 2 times` / `assert 2 == 1` over two
`orchestration.request_received` identities), which is the Audit V1 `MAJOR_01`
reproduction recorded in the Remediation V1 handoff.

Gate file sizes: `tests/application/test_architecture.py` 58 tests,
`tests/api/test_architecture.py` 51, `tests/api/test_openapi.py` 22,
`tests/api/test_http_v1.py` 70, `tests/api/test_streaming.py` 20.

`tests/application/test_phase11_3_dp103_acceptance.py` is a **connected**
acceptance test: it composes the real Phase 11.1 `ApplicationContainer`, the real
Phase 11.2 `Orchestrator` over its real collaborators, the canonical domain and
agent owners, the official `InMemorySessionStore` and the official in-memory
idempotency repository, and drives them through the real `ApplicationGateway`
and the real `create_app` factory with a `TestClient`. It is not a mock-only
endpoint test.

| Scenario | Proves |
| --- | --- |
| A — backend composition | The real container reaches `READY` with the Phase 11.3 module; the gateway identity is exact; the application module alone cannot become ready |
| B — health | Safe readiness on `/v1/health` with no implementation identity |
| C — create/read session | Creation and read use the canonical store; the read reflects canonical state, duplicate creation conflicts, and the session is usable by the canonical graph |
| D — message → orchestrator | A public message reaches the real orchestrator, the public data is the canonical decision projection, and the message never reaches the downstream vertical |
| E — domain/agent authority | Canonical domain and agent authority decides on this graph; the application layer projects and never reselects; agent authority is unreachable from the public path |
| F — malformed input | Malformed message/session/transport input and malformed session creation fail closed before orchestration |
| G — unsupported version | The public contract rejects an unsupported version; a tampered version fails safely before orchestration; no `/v2` route is served |
| H — internal defect | A canonical defect and an application-service defect both become safe failures |
| I — idempotent replay | Same key + equivalent command replays one orchestration and is not an authority bypass; two *simultaneous* equivalent keyed commands reach the canonical owner once (one `request_received` event, one decision record, one idempotency record) |
| J — idempotency conflict | Same key with changed content, or against another session, is a conflict; the connected concurrent conflict rejects the second command before any canonical execution |
| K — session revision | A stale expected revision is a concurrency conflict; a matching revision is accepted |
| L — unavailable capability | Cancellation reports `CAPABILITY_UNAVAILABLE` and creates no cancellation runtime |
| M — no transport bypass | HTTP reaches only the application gateway; route wiring exposes application contracts only; the gateway is the one public entrypoint |

Scenario N (inherited `AT-DP-102` / `AT-DP-101` / `AT-DP-134`) is represented by
separate required gate commands, not by invoking other test modules from inside
`AT-DP-103`.

## 19. Deviations and implementation decisions

- **Scenario D honest boundary** — the frozen public message contract carries no
  intent hint and no structured intent shape, so the canonical deterministic
  intent resolver answers `NEEDS_CLARIFICATION` before domain or agent routing,
  and `AT-DP-103` asserts that canonical outcome instead of fabricating a model
  response.
- **Scenario E honest boundary** — canonical domain/agent authority is proven
  live and deterministic on the composed graph, and the application layer is
  proven to be a faithful projection rather than a second selector.
- **Streaming route status** — a failed streamed command is delivered in-band as
  a terminal `error` event with HTTP `200`; this is the deliberate, documented
  choice that makes an SSE failure readable by a client, and it is why the
  streaming route is not published as the JSON error envelope.
- **`streaming` capability declares no operation** — the frozen public operation
  identity set has no streaming entry, and inventing one would fabricate a public
  identity; streaming is declared available because the SSE surface exists.
- **Cancellation returns `CAPABILITY_UNAVAILABLE`** — the design's explicit
  rejection of a not-yet-owned capability, chosen over a placeholder route or a
  fabricated active-request owner.
- **Phase 11.1 platform gate adjustment** — the sanctioned-consumer allowlist
  named in §13 is the only closed-phase test change made by Phase 11.3; no Phase
  11.1 or Phase 11.34 production semantics were modified. The gate command
  `git diff 3a2bc9e..HEAD -- cmm/platform cmm/orchestration kernel/llm cmm/domains
  cmm/agent_runtime` produced no output at this documentation task, so the
  closed-phase production directories are byte-identical to the design commit.
- **No cross-package fixture import** — `AT-DP-103` copies the canonical graph
  construction from the Phase 11.2 acceptance test instead of importing it, so no
  cross-package fixture coupling or test-order dependency is introduced.

Remediation V1 added two test-file changes beyond its two expected test files,
both of them forced by the authorized production repair and both recorded here
because they touch files the remediation brief did not list:

- **`tests/application/test_architecture.py` — frozen stdlib root `threading`.**
  The architecture gate freezes the exact standard-library roots the
  transport-neutral core may import and documents that a new root "must be frozen
  here". The authorized repair requires `from threading import Lock`, so the gate
  failed with `unfrozen application-core import: ['gateway.py -> threading']`
  until the single root `threading` was added to that exact allowlist. No
  wildcard, no third-party dependency and no concurrency subsystem is authorized
  by the entry: the production diff stays `cmm/application/gateway.py`, the
  `pyproject.toml` diff stays empty, and the closed lower layers already use
  `threading` (`cmm/orchestration/decision_repository.py`, `cmm/domains/`,
  `cmm/agent_runtime/`).
- **`tests/application/test_phase11_3_dp103_acceptance.py` — Scenario E gateway
  instance surface.** Scenario E asserted the set of instance-attribute types of
  the gateway, which the mandated private lock necessarily extends. The
  assertion was made *exact* rather than loosened: it now pins the complete
  attribute-name set (the five official collaborators plus `_idempotency_lock`),
  the exact types of the five collaborators, the exact lock type, and still
  asserts that no held value is a canonical authority object.

No other file outside `cmm/application/gateway.py`, the two expected test files,
`ROADMAP.md` and the four Phase 11.3 status documents was touched by Remediation
V1, and no closed-phase production file was touched at all.

## 20. Traceability

| Item | Value |
| --- | --- |
| Requirement | `F11-017 — Canonical Application Backend` |
| Design Point | `DP-103 — Versioned, Fail-Closed Application Gateway` |
| Acceptance test | `AT-DP-103` — `tests/application/test_phase11_3_dp103_acceptance.py` |
| Production packages | `cmm/application/` (10 modules), `cmm/api/` (5 modules) |
| Focused suites | `tests/application/`, `tests/api/` |
| Architecture gates | `tests/application/test_architecture.py`, `tests/api/test_architecture.py` |
| OpenAPI gate | `tests/api/test_openapi.py` |
| Inherited acceptances | `AT-DP-102` — `tests/orchestration/test_phase11_2_dp102_acceptance.py`; `AT-DP-101` — `tests/platform/test_phase11_1_dp101_acceptance.py`; `AT-DP-134` — `tests/llm/test_provider_registry_dp134_acceptance.py` |
| Inherited requirements reused | `F11-015` / `DP-101` (Phase 11.1), `F11-016` / `DP-102` (Phase 11.2) and `F11-014` / `DP-134` (Phase 11.34) — referenced, **not reopened and not modified** |
| Requirements matrix | `docs/reference/phase-11-stable-integrated-platform-requirements-matrix.md` (`F11-017` → `DP-103` → `AT-DP-103`) |
| Detailed roadmap | `docs/roadmap/phase-11-stable-integrated-platform.md` §11.3 |
| Design specification | `docs/superpowers/specs/2026-09-16-phase-11.3-application-backend-design.md` |
| Implementation plan | `docs/superpowers/plans/2026-09-16-phase-11.3-application-backend-implementation-plan.md` |
| Design commit | `3a2bc9e` |
| Plan commit | `325bc40` |
| Implementation commits | `ffadb94`, `53bcdff`, `1545441`, `d022e25`, `443ae1f`, `e769dde`, `54459f7`, `6414c5a`, `8226386`, `d411dcb`, `9f239a9`, `2460ab0`, `22c061c`, `2201d00` |
| AT-DP-103 implementation milestone HEAD | `2201d0009b47db7128bab895f4ad25f069712781` — intermediate implementation milestone, **not** the exact audit candidate |
| Independent Audit V1 | `docs/audits/phase-11.3-application-backend-independent-audit-v1.md` — `FAIL`; `BLOCKERS=0`; `MAJORS=1`; `MINORS=1`; `MAJOR_01=NON_ATOMIC_IDEMPOTENCY_UNDER_CONCURRENT_REQUESTS`; `MINOR_01=STALE_UNQUALIFIED_IMPLEMENTATION_HEAD_IN_ROOT_ROADMAP`; `AUDITED_HEAD=5fd8cc3b171faec88b802be920ad09ac53224e75`; `AUDITED_TREE=1cfbe114369ac89d1c2563a9787c5ebf096c64df`; `AUDIT_BUNDLE_SHA256=17377075eae659d123ca4ee909fa8f0cef01f625f40c2d498b34f22a47690199`; report commit `c111a57` — immutable |
| Remediation V1 design | `docs/superpowers/specs/2026-09-16-phase-11.3-remediation-v1-design.md` — commit `0eb802b`; SHA-256 `4b9ff2bd8861ce28f20bdc426639acc868975793c2ee4fa636ddb68a1903c868` |
| Remediation V1 plan | `docs/superpowers/plans/2026-09-16-phase-11.3-remediation-v1-implementation-plan.md` — commit `a185134`; SHA-256 `4cc539c7259ff2c183829f3e447f05d7c80e2e7e99dd529d15bc50f364a15778` |
| Remediation V1 commits | `test(application): reproduce concurrent idempotency race`; `fix(application): make keyed idempotency atomic`; `test(application): freeze the threading root the atomic lock needs`; `test(application): pin the gateway's exact instance surface`; `test(application): prove atomic idempotency through dp103`; `docs(phase11): correct 11.3 implementation head wording`; `docs(phase11): record 11.3 remediation v1` |
| Remediation V1 production diff | exactly `cmm/application/gateway.py` (one private `threading.Lock`, one atomic keyed critical section) |
| Mapping status | `VERIFIED_EXISTING` after Independent Re-audit V1 `PASS` |
| Next step | verify the dedicated docs-only Phase 11.3 closure commit and clean repository state; then inspect Phase 11.4 — CLI before implementation |

## 21. Final independently re-audited closure state

Independent Re-audit V1 returned `PASS` and is the authority for verification
and closure eligibility:

```text
PHASE11_3=CLOSED
INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V1=PASS

BLOCKERS=0
MAJORS=0
MINORS=0

MAJOR_01=VERIFIED_REMEDIATED
MINOR_01=VERIFIED_REMEDIATED

F11_017=VERIFIED_EXISTING
DP_103=VERIFIED_EXISTING
AT_DP_103=PASS

AT_DP_102=PASS
AT_DP_101=PASS
AT_DP_134=PASS

PHASE11_2=CLOSED
PHASE11_1=CLOSED
PHASE11_34=CLOSED

AUDITED_HEAD=4525f72391792e623730af69e95bcd054ce3cddf
AUDITED_TREE=0b650c8133111754452940c74a1bc72f24a0df23
REAUDIT_BUNDLE_SHA256=152276776b9e2765edb67adcd95b6ee3d2b565d416e1e4bce665777a078d9618
REAUDIT_V1_REPORT_COMMIT=c21f2e257a1995b748b78b65b622ff68ca3e6d38

CLOSURE_ELIGIBLE=YES
AUDIT_STATUS=CLOSED_AFTER_INDEPENDENT_REAUDIT_V1_PASS
NEXT=VERIFY_CLOSURE_COMMIT_THEN_INSPECT_PHASE11_4_CLI
```

The historical Audit V1 `FAIL` remains immutable and is not rewritten; the final
Re-audit V1 `PASS` verifies its two findings as remediated. This closure section
changes documentation only and introduces no production semantics.
