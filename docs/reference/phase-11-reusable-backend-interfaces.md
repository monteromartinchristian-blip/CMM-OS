# Phase 11 — Reusable Backend Interfaces

**Canonical owner:** Phase 11.50 — Reusable Backend Interfaces
**Requirement:** `F11-021 — Reusable First-Party Backend Interface`
**Design Point:** `DP-150 — Canonical Reusable Client Backend Interface`
**Acceptance:** `AT-DP-150 — Canonical Reusable Client Backend Interface Acceptance`
**Design specification:** [`docs/superpowers/specs/2026-09-25-phase-11.50-reusable-backend-interfaces-design.md`](../superpowers/specs/2026-09-25-phase-11.50-reusable-backend-interfaces-design.md)
**Implementation plan:** [`docs/superpowers/plans/2026-09-25-phase-11.50-reusable-backend-interfaces-implementation-plan.md`](../superpowers/plans/2026-09-25-phase-11.50-reusable-backend-interfaces-implementation-plan.md)
**Status:** `PHASE11_50=IMPLEMENTED_PENDING_INDEPENDENT_AUDIT`

---

## 1. Scope

Phase 11.50 creates the smallest stable backend seam a **first-party client** —
CMMChat first among them — can consume, over the already-closed Phase 11.3
application backend and Phase 11.5 conversational interface.

```text
first-party client
      ↓
cmm.client_backend
      ↓
ConversationService        (Phase 11.5, reused)
      ↓
ApplicationGateway         (Phase 11.3, reused)
      ↓
Orchestrator / existing canonical owners   (Phase 11.2, reused)
```

The phase is deliberately narrower than the broad historical roadmap wording of
§11.50. It implements **one versioned client-facing facade** and the capability
truth that goes with it. It does not implement MCP, OpenAI Actions, an external
REST expansion, a Claude or ChatGPT adapter, or any external automation adapter;
those stay in Phase 11.51 (`PHASE11_51=NOT_IMPLEMENTED`).

The facade is a **facade and capability projection only**. It adds no execution
authority, no backend authority, no session authority, no routing authority and
no model authority.

## 2. Canonical ownership

| Concern | Canonical owner | Phase 11.50 role |
| --- | --- | --- |
| Application entrypoint, dispatch, idempotency, fail-closed failures | `cmm.application.gateway.ApplicationGateway` (Phase 11.3) | delegate only |
| Session persistence and revision semantics | `cmm.runtime.sessions` through `SessionApplicationService` | delegate only |
| Conversation turns, edit/regenerate lineage, cancellation surface | `cmm.conversation.service.ConversationService` (Phase 11.5) | delegate only |
| Routing, intent, domain/agent selection | `cmm.orchestration` (Phase 11.2) | reached *through* the gateway, never named |
| Model execution, reasoning effort, multimodal bytes, token streaming, model-call cancellation | `kernel.llm.ModelGateway` (Phase 11.21) | **not exposed, not imported, not executed** |
| HTTP/OpenAPI/SSE transport adaptation | `cmm.api` (Phase 11.3) | untouched |
| CLI front door | `cmm.cli` (Phase 11.4) | untouched |

Phase 11.50 introduces exactly one new top-layer package, `cmm/client_backend`,
and exactly one new Phase 11.1 service binding, `client.backend`.

## 3. Public exports

A first-party client needs one import path and no internal module:

```python
from cmm.client_backend import (
    CLIENT_BACKEND_INTERFACE_VERSION,
    ClientBackend,
    ClientBackendCapabilities,
    ClientBackendCapabilityStatus,
    ClientBackendError,
    ClientBackendErrorCode,
    ClientOperation,
)
```

The complete frozen `__all__` is:

| Export | Kind | Purpose |
| --- | --- | --- |
| `CLIENT_BACKEND_INTERFACE_VERSION` | constant | the one client-interface version, `"1"` |
| `APPLICATION_API_VERSION` | re-export | the canonical application version, visible and never redefined |
| `CLIENT_BACKEND_ERROR_MESSAGES` | constant | module-owned constant message per client error code |
| `CLIENT_BACKEND_MODULE_ID`, `CLIENT_BACKEND_SERVICE_ID` | constant | the frozen Phase 11.1 composition identity |
| `ClientBackend` | class | the facade |
| `ClientBackendCapabilities` | class | the immutable capability projection |
| `ClientBackendCapabilityStatus` | enum | the closed four-state capability vocabulary |
| `ClientBackendError` | exception | one safe client-interface failure |
| `ClientBackendErrorCode` | enum | the closed interface-shape error vocabulary |
| `ClientBackendRequest`, `ClientBackendResult` | class | the narrow transport-neutral envelope and its safe result |
| `ClientOperation` | enum | the closed operation identity set |
| `build_client_backend_composition_module` | function | the Phase 11.1 composition contribution |

Internal projection helpers are deliberately **not** exported.

## 4. Canonical dependencies

`cmm.client_backend` imports only:

```text
cmm.application.contracts      canonical public application values
cmm.application.errors         canonical typed failures and safe projection
cmm.application.gateway        the one canonical application entrypoint
cmm.conversation.capabilities  the canonical conversational capability resolver
cmm.conversation.contracts     canonical public conversational values
cmm.conversation.errors        canonical conversational failure codes
cmm.conversation.service       the canonical conversational coordinator
cmm.conversation.state         the canonical conversation state value
cmm.platform.contracts         Phase 11.1 composition contracts
cmm.platform.modules           Phase 11.1 static composition module
```

There is **no** import of `kernel.llm`, `cmm.orchestration`, `cmm.api`,
`cmm.agent_runtime`, `cmm.domains`, `cmm.memory`, `cmm.cognitive`, any web
framework or CMMChat. The per-module seam allowlist is pinned in
`tests/client_backend/test_architecture.py`, and the reverse direction is pinned
too: `cmm.application`, `cmm.conversation`, `cmm.platform`, `cmm.orchestration`
and `kernel` never import `cmm.client_backend`.

Two additive, read-only identity accessors were added to the closed Phase 11.5
service so the facade can prove owner coherence and report canonical capability
truth without inventing a second authority:

```text
ConversationService.gateway              -> the exact ApplicationGateway instance
ConversationService.capability_resolver  -> the exact ConversationCapabilityResolver
```

Neither accessor grants authority, mutates state, replaces an owner or creates a
registry. The Phase 11.3 `ApplicationGateway` public surface is unchanged: its
one public entrypoint remains `handle`, which the facade uses for session
operations.

## 5. Operation map

The closed operation set is `ClientOperation`. Every operation delegates:

| `ClientOperation` | Canonical call | Returned value |
| --- | --- | --- |
| `CAPABILITIES` | `ConversationCapabilityResolver.resolve` + canonical declarations | `ClientBackendCapabilities` |
| `CREATE_SESSION` | `ApplicationGateway.handle(SESSION_CREATE command)` | `ApplicationSession` |
| `GET_SESSION` | `ApplicationGateway.handle(SESSION_GET query)` | `ApplicationSession` |
| `LOAD_CONVERSATION` | `ConversationService.load` | `ConversationState \| None` |
| `SUBMIT_MESSAGE` | `ConversationService.submit` | `AssistantResponse` |
| `EDIT_MESSAGE` | `ConversationService.edit` | `AssistantResponse` |
| `REGENERATE_RESPONSE` | `ConversationService.regenerate` | `AssistantResponse` |
| `CANCEL_REQUEST` | `ConversationService.cancel` | `ApplicationResponse` |

Two entry styles exist and both are supported:

* **explicit typed methods** — `create_session`, `get_session`,
  `load_conversation`, `submit_message`, `edit_message`, `regenerate_response`,
  `cancel_request`, `capabilities`. They take canonical values and return
  canonical values unchanged;
* **one generic envelope** — `ClientBackendRequest` /
  `ClientBackend.dispatch(request)` for a transport-neutral caller. The envelope
  carries `interface_version`, `request_id`, `operation` and a primitive-safe
  `payload` that may contain canonical public values verbatim. It is not a second
  message or session schema.

There is no handler registry, no reflection, no import-by-string, no service
name and no callable anywhere in the surface.

## 6. Capability truth

`ClientBackendCapabilities` is one immutable projection with the exact frozen
field inventory:

```text
interface_version
application_api_version

session_create            session_get
conversation_load         conversation_submit
conversation_edit         conversation_regenerate

response_event_stream     request_cancellation
attachments               document_upload

model_boundary_reasoning  model_boundary_multimodal  model_boundary_token_stream
end_to_end_reasoning      end_to_end_multimodal      end_to_end_token_stream
```

Every row is a member of the closed four-state vocabulary
`ClientBackendCapabilityStatus`:

| Status | Meaning |
| --- | --- |
| `available` | a real, end-to-end reachable capability of this client surface |
| `degraded` | reachable in a reduced form the canonical owner reports honestly |
| `unavailable` | not reachable at this baseline |
| `boundary_only` | proven available at the canonical *model* boundary and deliberately not proven end to end — never an end-to-end claim |

Sources of truth, all canonical:

* **application-level rows** — `ApplicationCapability` declarations supplied by
  the composition root through `ClientBackend.from_capability_declarations` (the
  same declarations the composed `CapabilityApplicationService` holds);
* **conversational and end-to-end rows** — the exact
  `ConversationCapabilityResolver` of the composed `ConversationService`;
* **model-boundary rows** — explicitly injected `ApplicationCapability`
  declarations carrying the frozen Phase 11.50 capacity IDs
  (`model-boundary-reasoning`, `model-boundary-multimodal`,
  `model-boundary-token-stream`). Only a canonical `AVAILABLE` declaration proves
  the boundary fact, and even then the row is `boundary_only`.

Nothing is inferred from a provider name, a model name or a vendor capability
list. When no declaration is supplied, the row is `unavailable` with
`MODEL_BOUNDARY_CAPABILITY_NOT_DECLARED` — never guessed.

### Current truth at this baseline

| Row | Value | Reason / evidence |
| --- | --- | --- |
| `session_create`, `session_get` | `available` | canonical `continuous_conversation` |
| `conversation_load`, `conversation_submit` | `available` | canonical `continuous_conversation` |
| `conversation_edit` | `available` | canonical `message_editing` (`append_only_lineage`) |
| `conversation_regenerate` | `available` | canonical `controlled_regeneration` (`canonical_reexecution`) |
| `response_event_stream` | `degraded` | canonical `response_streaming` = `response_event_stream`, `PROVIDER_TOKEN_STREAMING_UNAVAILABLE` |
| `request_cancellation` | `unavailable` | canonical `request_cancellation`, `NO_CANCELLABLE_OWNER` |
| `attachments` | `available` | canonical `attachments`, effective mode `reference_only` |
| `document_upload` | `unavailable` | canonical `document_upload`, `NO_CANONICAL_STORAGE_OWNER` |
| `model_boundary_*` | `unavailable` (or `boundary_only` when declared) | Phase 11.21 boundary evidence only |
| `end_to_end_reasoning` | `unavailable` | Phase 11.50 adds no reasoning effort to the payload |
| `end_to_end_multimodal` | `unavailable` | Phase 11.50 adds no upload, path resolver or URL downloader |
| `end_to_end_token_stream` | `degraded` | canonical conversational streaming row, never upgraded |

Two distinctions are load-bearing and are pinned by tests:

* **a response-event stream is not a token stream.** `response_event_stream`
  describes the existing public response-event delivery. It is never relabelled
  as conversational token streaming, and the matching `end_to_end_token_stream`
  row is never upgraded from the model boundary.
* **boundary availability is not end-to-end availability.** Phase 11.21 proof at
  the model boundary produces `boundary_only`, and the matching `end_to_end_*`
  row stays `unavailable`.

## 7. Fail-closed interface validation

`ClientBackendRequest` construction is itself a version gate, and
`ClientBackend.dispatch` re-runs the gate before reaching any canonical owner:

```text
interface_version != "1"           -> UNSUPPORTED_INTERFACE_VERSION, zero downstream calls
interface_version absent/blank     -> INVALID_CLIENT_CONTRACT
operation not a ClientOperation    -> INVALID_CLIENT_OPERATION, zero downstream calls
```

A malformed envelope payload (a missing required field, a non-int-typed revision)
fails closed as `INVALID_CLIENT_CONTRACT` with zero downstream calls. A raw
string is never coerced into an operation, and no operation is ever dispatched by
name.

## 8. Safe error projection

Three layers of failure handling, each with a fixed shape:

| Situation | Reported as |
| --- | --- |
| the client-interface *shape* is wrong (version, operation, envelope) | `ClientBackendError` with a closed `ClientBackendErrorCode` and its module-owned constant message |
| a canonical owner fails and the caller holds a canonical typed contract (explicit methods) | the canonical failure propagates unchanged — `ApplicationServiceError` subclass or `ConversationBoundaryError` subclass |
| a generic `dispatch` caller has no canonical typed contract | one safe client result; an unexpected internal failure becomes `INTERNAL_CLIENT_ERROR` |
| a caller needs to render a canonical failure it caught | `ClientBackend.project_canonical_failure(error)` returns `{code, message}` from the canonical safe projection, or the generic client error |

Never exposed: a raw exception repr, a stack trace, a credential, a provider
secret, a filesystem path, hidden reasoning or internal object repr. This is
pinned by `AT-DP-150` scenario G, which walks every serialized payload of a real
connected run.

## 9. Security

* **one closed version** — `CLIENT_BACKEND_INTERFACE_VERSION = "1"` identifies the
  facade contract only; it replaces no canonical version.
* **no arbitrary service invocation** — no `get_service`, `resolve_service`,
  `resolve_any` or `invoke` surface exists, and `tests/client_backend/test_architecture.py`
  fails if one appears.
* **no dynamic dispatch** — no `importlib`, `__import__` or `sys.modules` access.
  `getattr` is permitted only as frozen-dataclass introspection over the facade's
  own declared fields.
* **no filesystem or network authority** — no `open`, no `pathlib`, no `os`, no
  `requests`/`httpx`/`urllib`/`aiohttp`/`socket`. The facade cannot become a file
  store, an uploader, a path resolver or an egress path.
* **no hidden reasoning** — no identifier or constant names chain-of-thought,
  scratchpad, private reasoning or hidden reasoning, and every failure message is
  a bounded constant.
* **no secret or path in a public value** — the envelope accepts primitive-safe
  data plus frozen canonical public contract values; binary data, callables,
  modules and opaque runtime objects fail closed.
* **no CMMChat dependency** — no dependency from CMM OS core packages toward
  CMMChat exists, and CMMChat source is not modified.

## 10. Anti-fragmentation

Phase 11.50 creates no second authority. The package defines exactly eight
classes, none of which is an owner shape, and the architecture gate rejects any
class whose version-stripped normalized name ends in `Store`, `Repository`,
`Registry`, `Router`, `Runtime`, `Engine`, `Resolver`, `Manager`, `Executor`,
`Planner`, `Service`, `Locator` or `Bus`. The package has no subpackage and its
module list is frozen.

Explicitly absent from `cmm.client_backend`:

```text
second ApplicationGateway      second ConversationService
second Orchestrator            second ModelGateway
second ProviderRegistry        second ModelCatalog
second SessionStore            second conversation store
router  runtime  engine  registry  repository  store  resolver
service locator  HTTP server  event bus
direct ModelGateway execution path
```

## 11. Composition

`build_client_backend_composition_module` contributes exactly one Phase 11.1
service binding:

```text
module_id        = phase11.client-backend
service_id       = client.backend
owner            = cmm.client_backend
contract_version = 1.0.0
schema_version   = 1
mode             = local
authority        = client-backend-public-facade
runtime_contract = cmm.client_backend.interface.ClientBackend
dependencies     = application.gateway, conversation.service
```

Both dependency edges point **downward** at the closed canonical owners. The
Phase 11.21 `model.gateway` is deliberately **not** a declared dependency, so the
client can never acquire model execution authority through composition; the same
gate asserts `provider.registry` is absent too. The builder constructs nothing,
accepts only the concrete facade (an impostor fails closed), and the resolved
`client.backend` service is provably the exact configured facade instance.

The module composes beside the closed Phase 11.2/11.3/11.5 contributions and
reaches `READY`; omitting the conversation contribution fails the build closed.

`cmm.client_backend` is not wired into `cmm.application.local_runtime`,
`cmm.api` or the CLI in this phase: those closed surfaces keep their exact
service sets and are regression-checked unchanged.

## 12. Reasoning, multimodal, streaming and cancellation

* **reasoning effort** — not added to the submit-message payload. The boundary
  fact is exposed separately and honestly; no end-to-end row claims availability
  and no reasoning setting is smuggled into generic metadata.
* **multimodal** — no image bytes, no document bytes, no file upload, no path
  resolver and no URL downloader. Attachment references stay references.
* **token streaming** — `ModelGateway.stream()` is not wired and no stream
  runtime is created. Only current response-event stream truth is exposed.
* **cancellation** — `ModelCallCancellationToken` is not wired to first-party
  clients. The existing conversational/application cancellation surface is used,
  and its current honest answer is `CAPABILITY_UNAVAILABLE`.

A separate post-11.50 inspection (design §63) establishes whether a narrow
canonical E2E bridge is missing for each of these.

## 13. Testing

Focused suite (`tests/client_backend`, 157 tests):

| File | Covers |
| --- | --- |
| `test_contracts.py` | interface version, closed operation set, closed error codes, public export surface |
| `test_interface.py` | owner identity, incoherent-pair rejection, session and conversation delegation, canonical lineage, fail-closed version/operation, safe error projection |
| `test_capabilities.py` | frozen field inventory, canonical evidence, no optimistic upgrade, boundary-only vs end-to-end, determinism and immutability |
| `test_platform_module.py` | frozen composition identities, downward dependencies, absent model-gateway edge, impostor refusal, real container composition, module hygiene |
| `test_architecture.py` | parallel-authority, forbidden-import, dynamic-dispatch, service-locator, filesystem/network, hidden-reasoning and reverse-dependency gates |
| `test_phase11_50_dp150_acceptance.py` | the connected `AT-DP-150` acceptance, scenarios A–J |
| `_canonical_graph.py` | the shared real canonical graph helper (test-only) |

Every graph is the repository's own official composition root
(`build_local_application_runtime`) plus the canonical
`SharedSessionConversationAdapter`, `ConversationService` and `ClientBackend`.
Nothing is mocked, subclassed or replaced in the primary acceptance path; the
only instrumentation is a recording delegate wrapped around the real gateway's
bound method, which is how "exactly one canonical traversal" and "zero downstream
calls" are measured.

Gate commands:

```bash
.venv/bin/python -m pytest -q tests/client_backend
.venv/bin/python -m pytest -q tests/client_backend/test_phase11_50_dp150_acceptance.py
```

Inherited acceptances are run as separate required gate commands, not from inside
another test module: `AT-DP-134`, `AT-DP-121`, `AT-DP-101`, `AT-DP-102`,
`AT-DP-103`, `AT-DP-104`, `AT-DP-105`.

## 14. Known limits

* **CMMChat integration is not implemented.** Phase 11.50 builds the seam CMMChat
  will consume; it does not modify CMMChat.
* **No MCP, no OpenAI Actions, no external Claude/ChatGPT adapter and no external
  REST expansion.** `PHASE11_51=NOT_IMPLEMENTED`.
* **No new HTTP server and no SSE change.** `cmm.api` remains the existing Phase
  11.3 adapter and is regression-checked only.
* **No CLI change.** The Phase 11.4 front door is untouched and still green.
* **No event subscription runtime and no new event bus.** Only the existing
  response-event delivery is described.
* **No authentication.** No client authentication owner exists in this phase and
  the interface claims none; external authentication belongs with external
  adapters and deployment work.
* **Reasoning effort, real image/document input, provider token streaming and
  model-call cancellation are not end-to-end reachable from a first-party client
  at this baseline**, and the capability manifest says so.
* **`dispatch` flattens canonical failures.** The generic envelope path responds
  with its own safe result codes rather than a canonical typed error, because a
  generic transport-neutral caller has no canonical contract to match. A typed
  caller uses the explicit methods and keeps the canonical error objects.

## 15. Requirements and acceptance mapping

```text
F11-021 -> DP-150 -> AT-DP-150
```

```text
F11_021=IMPLEMENTED_PENDING_INDEPENDENT_AUDIT
DP_150=IMPLEMENTED_PENDING_INDEPENDENT_AUDIT
AT_DP_150=PASS_LOCAL
CLOSURE_ELIGIBLE=NOT_CLAIMED
```

## 16. Audit state

Phase 11.50 implementation is complete on branch
`feature/phase-11-stable-integrated-platform` with a clean worktree and an empty
stash. No independent audit has examined it yet.

```text
PHASE11_50=IMPLEMENTED_PENDING_INDEPENDENT_AUDIT
INDEPENDENT_AUDIT=NOT_PERFORMED
CLOSURE_ELIGIBLE=NOT_CLAIMED
```

Closure requires an independent audit with `BLOCKERS=0`, `MAJORS=0`,
`DP_150=VERIFIED_EXISTING`, `AT_DP_150=PASS` and `CLOSURE_ELIGIBLE=YES`, followed
by a separate docs-only closure commit. This document makes no closure claim.

<!-- PHASE11_50_IMPLEMENTED_PENDING_INDEPENDENT_AUDIT -->
