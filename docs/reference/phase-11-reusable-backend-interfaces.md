# Phase 11 — Reusable Backend Interfaces

**Canonical owner:** Phase 11.50 — Reusable Backend Interfaces
**Requirement:** `F11-021 — Reusable First-Party Backend Interface`
**Design Point:** `DP-150 — Canonical Reusable Client Backend Interface`
**Acceptance:** `AT-DP-150 — Canonical Reusable Client Backend Interface Acceptance`
**Design specification:** [`docs/superpowers/specs/2026-09-25-phase-11.50-reusable-backend-interfaces-design.md`](../superpowers/specs/2026-09-25-phase-11.50-reusable-backend-interfaces-design.md)
**Implementation plan:** [`docs/superpowers/plans/2026-09-25-phase-11.50-reusable-backend-interfaces-implementation-plan.md`](../superpowers/plans/2026-09-25-phase-11.50-reusable-backend-interfaces-implementation-plan.md)
**Remediation V1 design:** [`docs/superpowers/specs/2026-09-25-phase-11.50-remediation-v1-design.md`](../superpowers/specs/2026-09-25-phase-11.50-remediation-v1-design.md)
**Remediation V1 plan:** [`docs/superpowers/plans/2026-09-25-phase-11.50-remediation-v1-implementation-plan.md`](../superpowers/plans/2026-09-25-phase-11.50-remediation-v1-implementation-plan.md)
**Remediation V2 design:** [`docs/superpowers/specs/2026-09-26-phase-11.50-remediation-v2-design.md`](../superpowers/specs/2026-09-26-phase-11.50-remediation-v2-design.md)
**Remediation V2 plan:** [`docs/superpowers/plans/2026-09-26-phase-11.50-remediation-v2-implementation-plan.md`](../superpowers/plans/2026-09-26-phase-11.50-remediation-v2-implementation-plan.md)
**Independent Audit V1:** [`docs/audits/phase-11.50-reusable-backend-interfaces-independent-audit-v1.md`](../audits/phase-11.50-reusable-backend-interfaces-independent-audit-v1.md)
**Independent Re-audit V2:** [`docs/audits/phase-11.50-reusable-backend-interfaces-independent-reaudit-v2.md`](../audits/phase-11.50-reusable-backend-interfaces-independent-reaudit-v2.md)
**Status:** `PHASE11_50=IMPLEMENTED_REMEDIATION_V2_PENDING_INDEPENDENT_REAUDIT`

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

### Audit V1 remediation V1

Independent Audit V1 (`docs/audits/phase-11.50-reusable-backend-interfaces-independent-audit-v1.md`)
returned `INDEPENDENT_AUDIT_V1=FAIL` with `BLOCKERS=0`, `MAJORS=5`, `MINORS=1`
and `DP_150=NOT_VERIFIED`. Remediation V1 corrects exactly those findings,
preserves `F11-021`, `DP-150` and `AT-DP-150` unchanged, and claims no
verification:

```text
MAJOR_01  public owner escape hatch          -> closed (no live-owner accessor)
MAJOR_02  exact canonical owner types        -> exact-type gates
MAJOR_03  canonical failures re-coded        -> canonical safe identity preserved
MAJOR_04  capability truth contradiction     -> frozen attachment/stream truth
MAJOR_05  non-JSON-native serialization      -> JSON-native wrappers
MINOR_01  report evidence discipline         -> exact start HEAD and commit count
```

The remediation is implemented on `feature/phase-11-stable-integrated-platform`
and awaits independent Re-audit V2.

### Audit re-audit V2 remediation V2

Independent Re-audit V2
(`docs/audits/phase-11.50-reusable-backend-interfaces-independent-reaudit-v2.md`)
returned `INDEPENDENT_REAUDIT_V2=FAIL` with `BLOCKERS=0`, `MAJORS=1`, `MINORS=0`.
V1 MAJOR-01/03/04/05 and MINOR-01 were verified remediated. The one residual
defect (MAJOR_V2_01) was that the exact `client.backend` composition identity was
enforced **only by the convenience builder** and could be bypassed by a valid
hand-built canonical `ServiceBinding`:

```text
CLIENT_BACKEND_SUBCLASS_HAND_BUILT_BINDING=ACCEPTED
```

Remediation V2 fixes exactly that one defect, generically, at the authoritative
composition boundary:

```text
RuntimeContractMatch                    INSTANCE_OF (default) | EXACT_TYPE (opt-in)
ServiceBinding.runtime_contract_match   explicit, validated match mode
__cmm_exact_runtime_contract__          contract-level minimum semantic marker
IntegrationServiceRegistry.register()   authoritative exact gate
IntegrationServiceRegistry.replace()    same shared authoritative gate
```

The platform core stays generic: no service-ID or authority special case, no
`cmm.client_backend` import inside `cmm.platform`, and no parallel policy
registry. The inherited Phase 11.1 `INSTANCE_OF` default is unchanged, so no
closed phase changes meaning. It awaits independent Re-audit V3.

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
| `ClientBackendError` | exception | one safe client failure: a closed client-interface code, or a canonical downstream failure preserved verbatim |
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

Two additive, read-only seams were added to the closed Phase 11.5 service so the
facade can prove owner coherence and report canonical capability truth without
inventing a second authority. Remediation V1 (Audit V1 MAJOR-01) narrowed the
first of them and reviewed the second:

```text
ConversationService.uses_application_gateway(gateway) -> bool   (narrowed)
ConversationService.capability_resolver -> the exact ConversationCapabilityResolver  (kept)
```

* `ConversationService.gateway`, which returned the live canonical
  `ApplicationGateway`, was **removed**. Returning that object hands back its
  `handle(...)` entrypoint, so a public-only client could reach an application
  operation outside the frozen `ClientOperation` set. It is replaced by
  `uses_application_gateway(gateway) -> bool`: immutable, non-authoritative
  identity evidence that returns no owner, no entrypoint and no callable, and
  that the caller can only ask about a gateway it already holds.
* `ConversationService.capability_resolver` was **kept** after review: it is an
  independently closed canonical Phase 11.5 public contract, its only public
  operation returns immutable declarative `ConversationCapabilityState` values —
  the very truth the client backend must report — and it grants no session,
  conversation, routing, model or execution authority.

No replacement public owner accessor exists, and the `ClientBackend` facade
itself returns no live canonical owner at all. The Phase 11.3 `ApplicationGateway`
public surface is unchanged: its one public entrypoint remains `handle`, which the
facade uses privately for session operations.

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

Construction requires the **exact** canonical owner types —
`type(gateway) is ApplicationGateway` and `type(conversation) is
ConversationService` — and the facade refuses an incoherent pair whose
conversational service writes through a *different* gateway, using only the
narrowed non-authoritative `uses_application_gateway(...)` evidence. A duck-typed
stand-in and, since Remediation V1 (Audit V1 MAJOR-02), a *subclass* of either
owner both fail closed before any downstream operation; a facade subclass may
override authority-bearing behaviour, so the composition builder applies the same
exact-type gate to its service argument (`type(service) is ClientBackend`). Since
Remediation V2 (Re-audit V2 MAJOR_V2_01) that builder gate is fail-fast
convenience validation only: the authoritative gate is the Phase 11.1 registry,
which enforces the exact rule carried by the runtime contract itself. Official
in-memory canonical construction remains fully supported — only subclassing is
rejected.

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
attachments               attachment_effective_mode
document_upload

model_boundary_reasoning  model_boundary_multimodal  model_boundary_token_stream
end_to_end_reasoning      end_to_end_multimodal      end_to_end_token_stream
```

`attachment_effective_mode` is the narrow immutable qualifier added by
Remediation V1 (Audit V1 MAJOR-04): it carries the canonical effective mode of
the attachment row — `reference_only` at this baseline, `None` when no canonical
attachment state exists — so a first-party client can tell "conversational
reference metadata only" apart from real attachment reachability.

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
  same declarations the composed `CapabilityApplicationService` holds). The
  dedicated `response_event_stream` row is projected from the canonical
  application `streaming` declaration — the existing public response-event
  delivery — and **never** from the conversational `response_streaming` row
  (Audit V1 MAJOR-04);
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
| `response_event_stream` | `available` | canonical application `streaming` declaration (public response-event delivery) |
| `request_cancellation` | `unavailable` | canonical `request_cancellation`, `NO_CANCELLABLE_OWNER` |
| `attachments` | `degraded`, mode `reference_only` | canonical `attachments`, effective mode `reference_only` |
| `document_upload` | `unavailable` | canonical `document_upload`, `NO_CANONICAL_STORAGE_OWNER` |
| `model_boundary_*` | `unavailable` (or `boundary_only` when declared) | Phase 11.21 boundary evidence only |
| `end_to_end_reasoning` | `unavailable` | Phase 11.50 adds no reasoning effort to the payload |
| `end_to_end_multimodal` | `unavailable` | Phase 11.50 adds no upload, path resolver or URL downloader |
| `end_to_end_token_stream` | `degraded` | canonical conversational streaming row, never upgraded |

Two distinctions are load-bearing and are pinned by tests:

* **a response-event stream is not a token stream.** `response_event_stream`
  describes the existing public response-event delivery and is `available`;
  `end_to_end_token_stream` describes provider token streaming and stays
  `degraded`. They are separate fields fed by separate canonical evidence, and
  neither is ever derived from the other or upgraded from the model boundary
  (Audit V1 MAJOR-04);
* **boundary availability is not end-to-end availability.** Phase 11.21 proof at
  the model boundary produces `boundary_only`, and the matching `end_to_end_*`
  row stays `unavailable`.

Attachments are reported `degraded` with `reference_only` because the canonical
conversational row keeps attachment *references* only — they never enter the
application message payload — and Phase 11.50 adds no upload, file store, URL
fetch or filesystem access. `available` would have overstated reachability.

## 7. Fail-closed interface validation

`ClientBackendRequest` construction is itself a version gate, and
`ClientBackend.dispatch` re-runs the gate before reaching any canonical owner:

```text
interface_version != "1"           -> UNSUPPORTED_INTERFACE_VERSION, zero downstream calls
interface_version absent/blank     -> INVALID_CLIENT_CONTRACT
operation not a ClientOperation    -> INVALID_CLIENT_OPERATION, zero downstream calls
```

A malformed envelope payload (a missing required field, a non-int-typed revision,
an opaque or unsupported value, binary data, a non-string mapping key) fails
closed as `INVALID_CLIENT_CONTRACT` with zero downstream calls. A raw string is
never coerced into an operation, and no operation is ever dispatched by name.

### JSON-native serialization

Every public wrapper's `to_dict()` — `ClientBackendRequest`, `ClientBackendResult`,
`ClientBackendCapabilities` and `ClientBackendError` — returns only `None`, `bool`,
`int`, `float`, `str`, `list` and `dict[str, ...]`, so
`json.dumps(wrapper.to_dict())` succeeds for every supported value (Remediation
V1, Audit V1 MAJOR-05). A whitelisted canonical public value
(`ConversationMessage`, `AssistantResponse`, `ApplicationSession`,
`ApplicationResponse`, `ConversationCapabilityState`, `ApplicationCapability`,
`ApplicationStreamEvent`, and the rest of the frozen inventory) is serialized
through its **own** canonical safe `to_dict()` and then normalized recursively:
`Enum` → semantic value, `tuple` → `list`, `Mapping` → `dict` with string keys,
nested canonical value → the same treatment. There is no generic dataclass walk,
no `repr(...)`, no `str(...)` coercion and no identity generation: canonical IDs,
request IDs, session IDs, message IDs, revisions, timestamps and enum semantic
values are preserved verbatim. Any unsupported value fails closed as
`INVALID_CLIENT_CONTRACT` rather than surviving or being stringified.

## 8. Safe error projection

Remediation V1 (Audit V1 MAJOR-03) made the *real* client paths preserve
canonical failure identity. `ClientBackendError` is the one client-visible
failure type and carries exactly one of two disjoint kinds:

* a **client-interface** failure — one of the four reserved closed
  `ClientBackendErrorCode` values (`UNSUPPORTED_INTERFACE_VERSION`,
  `INVALID_CLIENT_OPERATION`, `INVALID_CLIENT_CONTRACT`, `INTERNAL_CLIENT_ERROR`)
  with its module-owned constant message. `canonical_code` is `None`;
* a **canonical downstream** failure — the canonical owner's own safe code and
  safe message preserved verbatim, built through
  `ClientBackendError.from_canonical(code, message)`. The code must be a real
  member of the canonical closed `ApplicationErrorCode` or
  `ConversationErrorCode` taxonomy, so no third taxonomy and no duplicate is
  created; `canonical_code` names it and `to_dict()` keeps the stable
  `{code, message}` shape.

| Situation | Reported as |
| --- | --- |
| the client-interface *shape* is wrong (version, operation, envelope) | `ClientBackendError` with a closed `ClientBackendErrorCode` and its module-owned constant message |
| a canonical application failure on a typed session method (`create_session`, `get_session`) | `ClientBackendError` preserving the canonical code and canonical safe message — e.g. `RESOURCE_NOT_FOUND` / `CONFLICT` |
| a canonical conversational failure on a typed method (`submit_message`, `edit_message`, `regenerate_response`) | the canonical `ConversationBoundaryError` subclass propagates unchanged |
| a canonical failure through generic `dispatch` | one safe client result whose `error` preserves the canonical code and message — never `INTERNAL_CLIENT_ERROR` |
| a canonical *internal* failure, or an unknown exception | `INTERNAL_CLIENT_ERROR` with the one generic safe message and no raw text |

Known canonical identities preserved verbatim include `RESOURCE_NOT_FOUND` /
`NOT_FOUND`, `CONFLICT` / `SESSION_CONFLICT`, `CAPABILITY_UNAVAILABLE`,
`POLICY_DENIED`, `APPROVAL_REQUIRED`, `CANCELLED`, `INVALID_REQUEST` and
`UNSUPPORTED_VERSION`. The client-interface `UNSUPPORTED_INTERFACE_VERSION`
remains reserved for the *Phase 11.50 interface* version and is never conflated
with a canonical application `UNSUPPORTED_VERSION`.

Never exposed: a raw exception repr, a stack trace, a credential, a provider
secret, a filesystem path, hidden reasoning or internal object repr. This is
pinned by `AT-DP-150` scenario G, which drives real canonical failures through
the facade and the generic entrypoint and walks every serialized payload of a
real connected run.

## 9. Security

* **one closed version** — `CLIENT_BACKEND_INTERFACE_VERSION = "1"` identifies the
  facade contract only; it replaces no canonical version.
* **no public live-owner access** — `ClientBackend` returns no live
  `ApplicationGateway` or `ConversationService`, defines no renamed equivalent
  (`application_gateway`, `conversation_service`, `owner`, `delegate`,
  `raw_gateway`, `raw_conversation`) and has no `handle` entrypoint, so a
  public-only client cannot reach a canonical operation outside the frozen
  `ClientOperation` set. The audited `client.gateway.handle(...) -> health.get`
  bypass has no public route (Remediation V1, Audit V1 MAJOR-01).
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
  modules and opaque runtime objects fail closed as `INVALID_CLIENT_CONTRACT`,
  and no `repr(...)` or `str(...)` fallback exists.
* **no CMMChat dependency** — no dependency from CMM OS core packages toward
  CMMChat exists, and CMMChat source is not modified.

## 10. Anti-fragmentation

Phase 11.50 creates no second authority. The package defines exactly nine
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
module_id              = phase11.client-backend
service_id             = client.backend
owner                  = cmm.client_backend
contract_version       = 1.0.0
schema_version         = 1
mode                   = local
authority              = client-backend-public-facade
runtime_contract       = cmm.client_backend.interface.ClientBackend
runtime_contract_match = exact_type
dependencies           = application.gateway, conversation.service
```

Both dependency edges point **downward** at the closed canonical owners. The
Phase 11.21 `model.gateway` is deliberately **not** a declared dependency, so the
client can never acquire model execution authority through composition; the same
gate asserts `provider.registry` is absent too. The builder constructs nothing,
accepts only the **exact** concrete facade type — an impostor and, since
Remediation V1, a facade *subclass* both fail closed (Audit V1 MAJOR-02) — and the
resolved `client.backend` service is provably the exact configured facade
instance.

Since Remediation V2 (Re-audit V2 MAJOR_V2_01) that builder check is only
fail-fast convenience validation, not the authoritative boundary. The canonical
facade declares the private `__cmm_exact_runtime_contract__ = True` marker on the
runtime contract, the binding declares `RuntimeContractMatch.EXACT_TYPE`, and
`IntegrationServiceRegistry.register()` and `replace()` compute one effective
match mode in which the contract marker wins over whatever the binding declared.
A hand-built binding can therefore neither omit `runtime_contract_match` nor set
it back to `INSTANCE_OF` to downgrade the canonical contract. Under `EXACT_TYPE`
the registry requires `type(implementation) is runtime_contract` — no subclass, no
adapter, no duck typing and no `isinstance` fallback — and fails closed when the
contract is not a real Python type. Contracts that do not opt in keep the closed
Phase 11.1 `INSTANCE_OF` semantics, including the existing safely-uncheckable
path, unchanged.

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

Focused suite (`tests/client_backend`, 192 tests):

| File | Covers |
| --- | --- |
| `test_contracts.py` | interface version, closed operation set, closed error codes, public export surface, JSON-native canonical-payload serialization and the opaque-payload fail-closed rule |
| `test_interface.py` | exact owner identity and subclass rejection, incoherent-pair rejection, absence of any public live-owner access or service locator, session and conversation delegation, canonical lineage, fail-closed version/operation, canonical failure preservation on the real typed and dispatch paths |
| `test_capabilities.py` | frozen field inventory, canonical evidence, no optimistic upgrade, boundary-only vs end-to-end, the frozen attachment/`reference_only` and response-event-stream truth, determinism and immutability |
| `test_platform_module.py` | frozen composition identities, downward dependencies, absent model-gateway edge, impostor and facade-subclass refusal, the declared `EXACT_TYPE` match mode, hand-built subclass rejection on `register()` and `replace()`, explicit and omitted-mode downgrade attempts, exact hand-built acceptance, real container composition, module hygiene |
| `test_architecture.py` | parallel-authority, forbidden-import, dynamic-dispatch, service-locator, filesystem/network, hidden-reasoning and reverse-dependency gates, plus the facade's exact runtime-contract marker with no `cmm.platform` import edge |
| `test_phase11_50_dp150_acceptance.py` | the connected `AT-DP-150` acceptance, scenarios A–K plus the Remediation V2 Scenario A2 (21 tests) |
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

Remediation V1 gate results on the remediation HEAD: the focused
finding-specific selection passed 31 tests, `tests/client_backend` passed 182,
`AT-DP-150` run separately passed 18, the seven inherited acceptance files passed
287, the `tests/application` / `tests/conversation` / `tests/llm` /
`tests/platform` / `tests/orchestration` / `tests/cli` suites passed
675 / 860 / 1153 / 369 / 498 / 459, and the global suite passed 21965 with zero
failures (the +25 over the audited implementation HEAD is exactly the
`tests/client_backend` growth from 157 to 182). `RUFF_TOUCHED`, `FORMAT`,
`COMPILEALL` and `GIT_DIFF_CHECK` all passed, and the repository-wide Ruff count
stayed at the 837 baseline with `RUFF_NEW_FINDINGS=0`.

Inherited acceptances are run as separate required gate commands, not from inside
another test module: `AT-DP-134`, `AT-DP-121`, `AT-DP-101`, `AT-DP-102`,
`AT-DP-103`, `AT-DP-104`, `AT-DP-105`.

### Remediation V2 gate results

Remediation V2 gate results on the remediation HEAD: the focused four-file
selection passed 170 tests, `tests/client_backend` passed 192, `AT-DP-150` run
separately passed 21, `tests/platform` passed 383, the seven inherited acceptance
files passed 287, and the `tests/application` / `tests/conversation` / `tests/llm`
/ `tests/orchestration` / `tests/cli` suites passed 675 / 860 / 1153 / 498 / 459 —
all identical to their pre-remediation counts, because Remediation V2 adds the
opt-in match and changes no inherited `INSTANCE_OF` behavior. The global suite
passed 21989 with zero failures and one warning; the +24 over the Remediation V1
HEAD is exactly the `tests/client_backend` growth from 182 to 192 plus the
`tests/platform` growth from 369 to 383. `RUFF_TOUCHED`, `FORMAT`, `COMPILEALL`
and `GIT_DIFF_CHECK` all passed, and the repository-wide Ruff count stayed at the
837 baseline with `RUFF_NEW_FINDINGS=0`.

The required Remediation V2 markers are:

```text
CLIENT_BACKEND_SUBCLASS_BUILDER_BINDING=REJECTED
CLIENT_BACKEND_SUBCLASS_HAND_BUILT_BINDING=REJECTED
CLIENT_BACKEND_SUBCLASS_REPLACEMENT=REJECTED
EXACT_CLIENT_BACKEND_HAND_BUILT_BINDING=ACCEPTED
EXACT_RUNTIME_CONTRACT_CANNOT_BE_DOWNGRADED=PASS
OMITTED_MATCH_CANNOT_DOWNGRADE_EXACT_CONTRACT=PASS
INHERITED_INSTANCE_OF_SEMANTICS=PRESERVED
PLATFORM_IMPORTS_CLIENT_BACKEND=NO
CLIENT_BACKEND_SPECIAL_CASE_IN_PLATFORM=ABSENT
PARALLEL_POLICY_REGISTRY=NO
```

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
* **A malformed payload is a client-contract failure.** An unsupported value — an
  opaque object, binary data, a callable, a non-string mapping key or a
  too-deeply nested structure — is never stringified and never silently passed
  through: it fails closed as `INVALID_CLIENT_CONTRACT`.

## 15. Requirements and acceptance mapping

```text
F11-021 -> DP-150 -> AT-DP-150
```

```text
F11_021=IMPLEMENTED_REMEDIATION_V2_PENDING_INDEPENDENT_REAUDIT
DP_150=IMPLEMENTED_REMEDIATION_V2_PENDING_INDEPENDENT_REAUDIT
AT_DP_150=PASS_LOCAL
CLOSURE_ELIGIBLE=NOT_CLAIMED
```

## 16. Audit state

Independent Audit V1 examined the Phase 11.50 implementation at
`AUDITED_HEAD=ed7bdc6f9c48ff94375613bb80c23ad10599710c` and returned:

```text
INDEPENDENT_AUDIT_V1=FAIL
BLOCKERS=0
MAJORS=5
MINORS=1
DP_150=NOT_VERIFIED
AT_DP_150=FAIL_INDEPENDENT
CLOSURE_ELIGIBLE=NO
```

That report is immutable historical evidence. Remediation V1 corrected exactly
those five MAJOR findings plus the MINOR-01 evidence discipline on branch
`feature/phase-11-stable-integrated-platform`. Independent Re-audit V2 then
examined the Remediation V1 state at
`AUDITED_HEAD=c626fbfead204f58e67076375dc6f497f56af700` and returned:

```text
INDEPENDENT_REAUDIT_V2=FAIL
BLOCKERS=0
MAJORS=1
MINORS=0
AUDIT_V1_MAJOR_01=VERIFIED_REMEDIATED
AUDIT_V1_MAJOR_02=PARTIALLY_REMEDIATED_RESIDUAL_OPEN
AUDIT_V1_MAJOR_03=VERIFIED_REMEDIATED
AUDIT_V1_MAJOR_04=VERIFIED_REMEDIATED
AUDIT_V1_MAJOR_05=VERIFIED_REMEDIATED
AUDIT_V1_MINOR_01=VERIFIED_REMEDIATED
DP_150=NOT_VERIFIED
AT_DP_150=FAIL_INDEPENDENT
CLOSURE_ELIGIBLE=NO
```

That report is likewise immutable historical evidence. Remediation V2 corrects
exactly the one residual defect (MAJOR_V2_01) and claims no verification:

```text
PHASE11_50=IMPLEMENTED_REMEDIATION_V2_PENDING_INDEPENDENT_REAUDIT
INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V2=FAIL
INDEPENDENT_REAUDIT_V3=NOT_PERFORMED
AT_DP_150=PASS_LOCAL
CLOSURE_ELIGIBLE=NOT_CLAIMED
```

Closure requires an independent Re-audit V3 with `BLOCKERS=0`, `MAJORS=0`,
`DP_150=VERIFIED_EXISTING`, `AT_DP_150=PASS` and `CLOSURE_ELIGIBLE=YES`, followed
by a separate docs-only closure commit. This document makes no closure claim.

<!-- PHASE11_50_IMPLEMENTED_REMEDIATION_V2_PENDING_INDEPENDENT_REAUDIT -->
