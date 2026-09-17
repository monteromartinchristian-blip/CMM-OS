# Phase 11 — Conversational Interface reference

**Status:** `IMPLEMENTED — AWAITING INDEPENDENT AUDIT`
**Phase:** 11.5 — Conversational Interface
**Requirement:** `F11-019 — Canonical Conversational Interface`
**Design Point:** `DP-105 — Session-Backed Canonical Conversation Boundary`
**Acceptance Test:** `AT-DP-105 — Canonical Conversational Interaction Acceptance` — `tests/conversation/test_phase11_5_dp105_acceptance.py`
**Design specification:** `docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-09-17-phase-11.5-conversational-interface-implementation-plan.md`
**Production package:** `cmm/conversation/` (8 modules):
`__init__.py`; `contracts.py`; `errors.py`; `state.py`; `capabilities.py`;
`projection.py`; `service.py`; `platform_module.py`
**Additive seams in closed packages:** `cmm/application/contracts.py`
(`ApplicationChannel.CONVERSATION`); `cmm/application/requests.py` (channel
mapping); `cmm/application/local_runtime.py` (the canonical `session_store`
reference); `cmm/api/app.py` (the optional `conversation` keyword and the five
conversation routes); `cmm/api/models.py` (the conversation transport DTOs)
**Focused suite:** `tests/conversation/` (685 tests)
**Architecture/security gate:** `tests/conversation/test_architecture.py`
(125 tests)
**Inherited gates touched:** `tests/application/test_architecture.py`;
`tests/api/test_architecture.py`; `tests/platform/test_architecture.py`;
`tests/api/test_openapi.py`; `tests/api/test_http_v1.py`
**Documentation head while preparing this document:** `0bb2a45`

```text
PHASE11_5=IMPLEMENTED_AWAITING_INDEPENDENT_AUDIT

F11_019=IMPLEMENTED_AWAITING_INDEPENDENT_AUDIT
DP_105=IMPLEMENTED_AWAITING_INDEPENDENT_AUDIT
AT_DP_105=GREEN_IN_REPOSITORY

CLOSURE_ELIGIBLE=NO
AUDIT_STATUS=PENDING_INDEPENDENT_AUDIT
NEXT=INDEPENDENT_AUDIT
```

Phase 11.5 is **implemented and awaiting independent audit**. The canonical
conversational interface exists on `feature/phase-11-stable-integrated-platform`,
`AT-DP-105` is green in this repository, and the inherited Phase 11 acceptances
stay green — but no independent audit has examined this implementation yet.
Nothing in this document claims closure, verification or closure eligibility:
those states may only be recorded after an independent audit returns the
evidence the design specification's §35 requires. This documentation is written
to be independently re-verified, and every measurement it reports was produced
in this repository at the documentation head named above.

## 1. Purpose and ownership boundary

Phase 11.5 establishes the canonical conversational boundary of CMM OS: one
version-aware, interface-neutral, fail-closed conversational surface over the
already-closed Phase 11.1–11.4 platform. CMMChat and alternative clients are
**consumers** of these contracts; no client becomes authoritative by rendering
or initiating a conversation.

```text
Client / CMMChat / CLI / API
            |
            v
cmm/conversation   (canonical conversational boundary)
            |
            v
cmm/application    (Phase 11.3 public application semantics)
            |
            v
cmm/orchestration  (Phase 11.2 canonical central request path)
            |
            v
canonical domain / agent / workflow / approval / session authorities
```

The boundary owns exactly:

- the frozen public conversational contracts and their bounded, secret-free
  value grammar;
- the translation between those contracts and the versioned
  `conversation.v1` extension of the canonical shared session;
- the requested-versus-effective capability representation;
- the safe projection of authorized application and Phase 10.45 Domain
  projections into one public `AssistantResponse`;
- one thin coordinator (`ConversationService`) over the canonical
  `ApplicationGateway`, the canonical session adapter, the capability resolver
  and the projector;
- the Phase 11.1 composition binding `conversation.service`.

It owns none of: session persistence, application dispatch, orchestration
routing, domain or agent selection, provider or model access, workflow,
approval, execution, memory, knowledge, validation, notification or file
authority. Concretely, the package persists nothing, opens no store of its own,
holds no service singleton, calls no model, performs no network or file I/O and
defines no registry, router, planner, engine or runtime.

## 2. Canonicalization matrix

| Concern | Owner after Phase 11.5 | Phase 11.5 role |
| --- | --- | --- |
| Public conversational contracts (`ConversationMessage`, `AssistantResponse`, `ConversationCapabilityState`, `ConversationLineage`, `ConversationAttachmentRef`, the closed roles and statuses) | `cmm/conversation/contracts.py` — **new** | Definition and versioned, bounded, secret-free validation |
| Safe conversational failures | `cmm/conversation/errors.py` — **new** | Closed code vocabulary and constant public messages |
| Conversation state and its persistence translation | `cmm/conversation/state.py` — **new**, translation only | Namespaced `conversation.v1` extension inside the canonical shared session |
| Requested vs effective capability state | `cmm/conversation/capabilities.py` — **new** | Descriptive resolution over injected canonical declarations |
| Safe projection of authorized state | `cmm/conversation/projection.py` — **new** | Projection only; never a second resolver |
| Conversational coordination | `cmm/conversation/service.py` — **new** | One command per turn into the canonical gateway |
| Phase 11.1 composition | `cmm/conversation/platform_module.py` — **new binding** | One service binding, no new authority |
| Session persistence, revision, concurrency | `cmm.runtime.sessions` (`SessionStore`, `SharedSessionState`, `InMemorySessionStore`, `FileSessionStore`) — reused, unchanged | Extension translation and optimistic-revision commit |
| Application-facing submission | Phase 11.3 `ApplicationGateway` / `RequestApplicationService` — reused; one additive channel value | Delegation through the one public application entrypoint |
| Central request processing | Phase 11.2 `Orchestrator` — reused, unchanged | Never bypassed, never re-implemented |
| Domain selection and authorized projection | Phase 10.45 `cmm.domains.interface_integration` and its contracts — reused, unchanged | Consumes `ConversationalDomainView` only; never reconstructs Domain state |
| Transport exposure | `cmm/api` — reused; additive conversation routes | Thin adapter over `ConversationService` |
| Approval, workflow, execution, memory, knowledge, provider, model gateway, file/artifact store, Bot runtime, auth/RBAC, storage/migrations, CMMChat UI | owned by their canonical subsystems or not implemented | Not duplicated, not fabricated, not pulled forward |

## 3. Public package surface

### 3.1 `cmm/conversation/` — the conversational boundary

| Module | Owns |
| --- | --- |
| `contracts.py` | The frozen public conversational values: `ConversationRole` (`user`, `assistant`, `system`), `ConversationCapabilityStatus` (`available`, `degraded`, `approval_required`, `blocked`, `unavailable`), `ConversationAttachmentRef`, `ConversationLineage`, `ConversationMessage`, `ConversationCapabilityState`, `AssistantResponse`, the frozen public bounds (`MAX_METADATA_DEPTH` 6, `MAX_METADATA_ITEMS` 128, `MAX_STRING_LENGTH` 16 384, `MAX_MESSAGE_LENGTH` 64 000, `MAX_IDENTIFIER_LENGTH` 256, `MAX_COLLECTION_ITEMS` 128) and the secret/internal-detail key screens |
| `errors.py` | The closed public conversational error codes (`invalid_request`, `session_not_found`, `session_conflict`, `capability_unavailable`, `policy_denied`, `approval_required`, `internal_failure`), their constant public messages and the safe failure value `ConversationError`; the raised boundary failures `ConversationBoundaryError` (code `invalid_request`), `ConversationSessionNotFoundError`, `ConversationSessionConflictError` — none accepts an argument, so no store text, path, revision value or traceback can travel through a conversational failure |
| `state.py` | `ConversationState` (frozen, append-only, validated: unique message IDs, every message bound to the state session, an `active_message_id` that always resolves) and `SharedSessionConversationAdapter` — the translation between the frozen state and the canonical `conversation.v1` extension plus the optimistic-revision commit rules |
| `capabilities.py` | `ConversationCapabilityResolver` and the nine fixed conversational capability IDs in their frozen order |
| `projection.py` | `ConversationResponseProjector` — pure, stateless projection of one `ApplicationResponse` plus, when supplied, one already authorized `ConversationalDomainView` |
| `service.py` | `ConversationService` and `CONVERSATION_ACTOR_ID` |
| `platform_module.py` | `build_conversation_composition_module(service=...)` — the Phase 11.1 contribution (`conversation.service`, authority `conversation-public-interface`, dependency `application.gateway`) |
| `__init__.py` | The public package re-export surface |

The package is standard-library plus the four sanctioned canonical seams
(`cmm.application`, `cmm.platform`, `cmm.runtime.sessions`,
`cmm.domains.interface_integration_contracts`); the per-module liveness pin of
the architecture gate freezes exactly which module imports which seam.

### 3.2 Value grammar and bounds

Every public conversational value is frozen at construction, validated against
the frozen public limits, recursively normalized to immutable representations
(`MappingProxyType`, tuples) and deterministically serializable through
`to_dict()` / `from_dict()`, so a persisted extension round-trips exactly.

Public values use one bounded, secret-free grammar: `None`, `bool`, `int`,
finite `float`, `str`, and mappings/sequences of those values. Binary data,
opaque runtime objects, raw exceptions, non-finite numbers and unbounded
nesting fail closed. Mapping keys are screened structurally: a key must be
ASCII, must leave at least one alphanumeric character once separators are
removed, and its separator-free lowercase fragment must not contain a denied
fragment — so `Api-Key`, `apiKey`, `refreshToken`, `db-credential` and a
Cyrillic-homoglyph or full-width spelling all fail closed, while non-ASCII text
stays fully supported in values. Denied families are
`SECRET_LIKE_METADATA_KEYS` (`password`, `passwd`, `secret`, `token`, `api_key`,
`apikey`, `credential`, `private_key`, `authorization`, `cookie`) and
`INTERNAL_DETAIL_METADATA_KEYS` (`traceback`, `stacktrace`, `chainofthought`,
`scratchpad`, `hiddenreasoning`). The conversational bounds mirror the frozen
public application limits exactly, so a conversational message is never bounded
more loosely than the public application message it becomes.

## 4. `conversation.v1` — the canonical session extension

A conversation introduces **no second persistence identity or lifecycle**:

```text
conversation continuity identity == canonical session identity
```

- **Key and version.** The extension lives inside the canonical shared session
  under the namespaced key `conversation.v1`
  (`CONVERSATION_EXTENSION_KEY`), whose serialized payload carries
  `version: 1` (`CONVERSATION_EXTENSION_VERSION`). An unsupported version fails
  closed.
- **Serialized shape.** The closed extension shape is
  `{version, session_id, mode, bot_id, active_message_id, messages}`; unknown
  fields fail closed. `mode` defaults to `"general"`; `bot_id` is the optional
  opaque association; `active_message_id` is the deliberate minimal
  active-branch/head marker; `messages` is the ordered transcript of frozen
  `ConversationMessage` values.
- **The canonical `SessionStore` is the only persistence authority.** The
  adapter never subclasses, wraps, replaces or re-implements the store and
  keeps no side dictionary, cache or repository: the only write is exactly one
  `SessionStore.save` on a `SharedSessionState.with_extension` copy, and the
  committed extension is re-read from the committed envelope and returned.
- **Optimistic revision semantics.** The caller supplies an
  `expected_previous_revision`; a value that is not a non-negative, non-bool
  `int` is a caller input error (`INVALID_REQUEST`), a well-typed but stale
  revision fails closed with the safe `ConversationSessionConflictError` before
  anything is written, and the single commit carries the same expected
  revision, so a concurrent canonical writer turns the commit into the safe
  conflict — never a silent retry with a new revision. A commit must advance
  the canonical revision by exactly one; a commit that did not advance (for
  example a canonical entry deleted between read and commit) is reported as the
  conflict, never returned as success and never undone.
- **Append-only lineage.** `ConversationState.append(...)` returns a new state
  and never mutates the old one; editing never rewrites the original message,
  and lineage records relationships (`supersedes_message_id`,
  `regenerates_message_id`) rather than rewriting history.
- **Fail-closed translation.** A missing session is
  `ConversationSessionNotFoundError`; an unreadable or corrupt store, a stored
  value that is not a valid extension mapping (including a stored JSON `null`),
  an envelope whose `session_id` disagrees with the committed state, duplicate
  message IDs, a message from another session and an unresolvable
  `active_message_id` all fail closed as the safe conflict error with no store
  text, no session id, no cause chain and no retry. An absent extension key
  simply means the session has no conversation.

## 5. `ConversationService` — the public API

`ConversationService` is the one conversational coordinator. It is constructed
from exactly four canonical collaborators — the Phase 11.3
`ApplicationGateway`, the canonical `SharedSessionConversationAdapter`, the
`ConversationCapabilityResolver` and the `ConversationResponseProjector` — and
each constructor argument is type-checked against its concrete canonical class,
so a wrong or cross-wired graph cannot serve a turn.

| Operation | Signature (keyword-only after the first argument) | Behavior |
| --- | --- | --- |
| `submit` | `submit(message, *, request_id, expected_session_revision, requested_capabilities=(), domain_view=None, assistant_message_id, assistant_created_at) -> AssistantResponse` | One user turn: canonical session loaded, expected revision verified, turn validated, one canonical command, gateway entered exactly once, response projected, user and assistant messages committed in one canonical commit |
| `edit` | `edit(*, original_message_id, replacement, request_id, expected_session_revision, requested_capabilities=(), domain_view=None, assistant_message_id, assistant_created_at) -> AssistantResponse` | Non-destructive, append-only edit through a lineage-bound replacement (see §7) |
| `regenerate` | `regenerate(*, session_id, response_message_id, request_id, application_message_id, expected_session_revision, domain_view=None, assistant_message_id, assistant_created_at) -> AssistantResponse` | Canonical re-execution of one assistant response (see §7) |
| `cancel` | `cancel(*, request_id, target_request_id) -> ApplicationResponse` | Delegates one request-scoped cancellation to the gateway and returns the canonical response unchanged (see §9) |
| `load` | `load(session_id) -> ConversationState \| None` | The one read-only accessor: returns the conversation of one canonical session, or `None` when the session or its extension is absent; writes nothing |

Frozen command construction — every command the service builds is one
`ApplicationCommand` with:

- `api_version="v1"` and the caller's `request_id` carried verbatim;
- `operation=MESSAGE_SUBMIT` for a turn, `REQUEST_CANCEL` for a cancellation;
- `actor_id=CONVERSATION_ACTOR_ID` — the one module-level constant
  `CONVERSATION_ACTOR_ID = "conversation"`. `actor_id` is descriptive public
  input in Phase 11.3 (no authorization semantics), the gateway's message path
  fails closed without one, and the boundary freezes one identity rather than
  inventing per-message actors;
- the canonical session (`session_id=None` only for the request-scoped
  cancellation);
- the caller's `expected_session_revision` for a turn;
- `channel=ApplicationChannel.CONVERSATION`;
- **no idempotency key.** The service never sets `idempotency_key`: Phase 11.5
  defines no conversation-level idempotency owner, so no key is ever
  fabricated, and the HTTP conversation bodies expose no `idempotency_key`
  field either.

The message payload of a turn carries public conversational text only:
`{message_id, content, content_type}` with the one frozen content type
`text/plain`. Conversation `metadata`, `references`, `attachments` and the
opaque `bot_id` stay in conversation state and never enter the application
payload; `bot_id` grants nothing and selects nothing. Every identity and
timestamp is caller-supplied, so a call is deterministic and the service holds
no clock, no retry loop and no hidden reasoning.

Failure semantics: caller input errors — a mistyped expected revision, a
malformed request/assistant identity, a malformed assistant timestamp, an
already-stored or reused turn identity, and any caller-supplied lineage (lineage
is service-owned) — fail closed as the conversational `INVALID_REQUEST` boundary
error *before* the gateway is entered and before anything is written, so a raw
state or contract `ValueError` can never surface from a turn that already
traversed the canonical pipeline. A lost optimistic-concurrency race propagates
as the safe `ConversationSessionConflictError` and is never silently retried.
Structured blocked or failed application responses are preserved through the
safe projection and persisted like any other outcome; no exception text ever
enters conversation state.

## 6. Application conversation-channel seam

Phase 11.5 adds exactly one backward-compatible public field value to the
closed Phase 11.3 application boundary:

- `ApplicationChannel.CONVERSATION = "conversation"` is added beside the
  existing `API` and `CLI`; `API` stays the default, and both closed values keep
  their order and spelling;
- `RequestApplicationService` maps it one-to-one
  (`ApplicationChannel.CONVERSATION -> OrchestrationChannel.CONVERSATION`).
  `OrchestrationChannel.CONVERSATION` already existed in the Phase 11.2
  contracts — no orchestration code was touched by Phase 11.5;
- the channel is **descriptive origin only**: it selects no authority, grants no
  capability and changes no business rule. It participates in the request's
  deterministic public serialization, so two otherwise identical commands from
  different channels are different public commands for idempotency purposes;
- the HTTP adapter sets nothing, so the closed Phase 11.3 route, schema and
  behavior surface is unchanged.

The seam is covered by additive tests in `tests/application/test_contracts.py`
(the value, the unchanged `API` default) and `tests/application/test_requests.py`
(the exact `API`/`CLI` mappings preserved, the conversation mapping delivered to
the orchestrator), plus the frozen channel-value pin in
`tests/application/test_channels.py`.

## 7. Message editing and controlled regeneration

**Editing is non-destructive and append-only.** `edit` requires the original to
exist inside the replacement's own session and to be a `USER` message; the
original is preserved byte-identical. The service enforces lineage itself: the
effective replacement is the caller's message with
`lineage.supersedes_message_id == original.id`, and a non-empty caller-supplied
lineage is rejected rather than silently sanitized. The canonical gateway is
traversed again exactly once with the replacement as the application message
identity, and the effective replacement plus the new assistant response are
committed in one canonical commit. A replacement identity that already exists
(including the original's own) or that reuses the assistant identity of the
turn fails closed with `INVALID_REQUEST` before the gateway and before any
write.

**Regeneration is canonical re-execution, not recollection.** `regenerate`
requires the target assistant response to exist and to be an `ASSISTANT`
message; the nearest preceding `USER` message supplies the resubmitted public
content without being mutated, re-appended or attributed a new identity. The
caller-supplied `application_message_id` is the new canonical application
message identity (no new conversational user message is appended), the gateway
is traversed again exactly once, no hidden reasoning is reused or persisted, the
original response is preserved, and the new assistant message carries
`lineage.regenerates_message_id == response_message_id`.

The branch model is deliberately minimal: `lineage` plus the optional
`active_message_id` head. No generalized conversation version-control subsystem
exists, and historical approvals, workflows and results are never rewritten as
if they had not occurred.

## 8. Requested vs effective capabilities

`ConversationCapabilityResolver` resolves the nine fixed conversational
capability IDs, always in the fixed plan order, whether or not they were
requested; an unknown, blank or non-string requested ID fails closed with the
conversational `INVALID_REQUEST` boundary error. Requesting a capability marks
it as requested and changes nothing else: a request flag never creates
authority, never enables an owner and never changes an effective mode.

Frozen baseline truth table:

| Capability | Status at this baseline | Effective mode | Reason |
| --- | --- | --- | --- |
| `continuous_conversation` | `available` | `session_backed_multi_turn` | — |
| `message_editing` | `available` | `append_only_lineage` | — |
| `controlled_regeneration` | `available` | `canonical_reexecution` | — |
| `attachments` | `available` | `reference_only` | — |
| `response_streaming` | `degraded` | `response_event_stream` | `PROVIDER_TOKEN_STREAMING_UNAVAILABLE` |
| `request_cancellation` | `unavailable` | — (absent) | `NO_CANCELLABLE_OWNER`, or the injected canonical declaration's own `reason_code` when it carries one |
| `document_upload` | `unavailable` | — (absent) | `NO_CANONICAL_STORAGE_OWNER` |
| `bot_association` | `available` | `opaque_non_authoritative` | — |
| `domain_projection` | `available` | `authorized_projection_when_supplied_by_canonical_integrator` | — |

Contract rules: `effective` must be absent whenever the status is `unavailable`
and must name the provided mode whenever the status is `available`; an
`unavailable` row always carries a reason. Cancellation can only become
`available` through an injected canonical `ApplicationCapability` with ID
`request-cancellation` that explicitly reports `CapabilityStatus.AVAILABLE`, in
which case the effective mode is `canonical_cancellable_requests`; any other
status, or absence, leaves it `unavailable`. The resolver reads nothing but the
canonical declarations injected at construction: it inspects no imports,
registries or live owners, so availability can never be inferred from a module
name, route name or class. Construction is fail-closed exactly like the
application capability service — every injected entry must be a concrete
`ApplicationCapability` and no capability ID may be declared twice, so
declaration precedence cannot become ambiguous and a later declaration can
never silently unlock cancellation.

## 9. Streaming and cancellation truth

**Streaming is truthful, not provider-token generation.** At this baseline the
Phase 11.3 SSE transport delivers deterministic response events for an
already-computed application result. The conversational capability therefore
reports `requested=streaming -> effective=response_event_stream`,
`status=degraded`, reason `PROVIDER_TOKEN_STREAMING_UNAVAILABLE`. Phase 11.5
introduces no provider token-stream runtime, no second model invocation path, no
WebSocket inference ownership and no hidden active-generation registry; if a
future canonical owner supports live generation, the capability can evolve
additively.

**Cancellation is unavailable, honestly.** `ConversationService.cancel` builds
one request-scoped `REQUEST_CANCEL` command carrying the target request
identity and hands it to the canonical `ApplicationGateway`, whose response is
returned unchanged. At this baseline that response is the canonical
`CAPABILITY_UNAVAILABLE` (the application boundary's frozen safe cancellation
message), because no canonical cancellable-request runtime owns cancellation.
The service owns no cancellation state, creates no `ActiveRequestRegistry`,
cancellation engine or task runtime, and never fabricates a cancellation or a
fake success. The conversational capability state exposes the same effective
truth (§8).

## 10. Attachments and Bot association

**Attachments are references only.** `ConversationAttachmentRef` carries
`ref`, `kind` and the optional public display metadata `name` and `media_type`
— never content, never bytes, and never a second file owner. Attachments are
validated, bounded by `MAX_COLLECTION_ITEMS`, persisted with the message and
returned in projections; the conversational boundary implements no conversation
file workspace, global artifact library, object storage, file version history,
cross-device synchronization, import/export archive or global file search.
Whether Phase 11.5 can upload or ingest a document is reported by
`document_upload`, which stays `unavailable` because no canonical storage owner
exists in this phase.

**A Bot association is opaque and non-authoritative.** A conversation and its
messages may carry an optional `bot_id`; normal conversation works with
`bot_id=None`. The identifier is visible and persisted as public conversation
metadata and grants nothing: it cannot grant tools or permissions, cannot force
Agent selection, cannot select providers, cannot authorize Computer Use and
cannot change memory or privacy policy by itself. Canonical Bot identity,
configuration and runtime semantics remain outside Phase 11.5 and are reserved
for the dedicated Bot phase.

## 11. Phase 10.45 `ConversationalDomainView` reuse

The projector consumes only an **already authorized** Phase 10.45
`ConversationalDomainView` (or `None`). It resolves no Domain, constructs no
view and re-derives no reference from application data or metadata: references
absent from the canonical view stay absent — visibility is not authorization,
so the conversational boundary reflects exactly what canonical authority
authorized. A raw Domain payload, a raw exception or a malformed capability
state fails closed with `TypeError` instead of producing a fabricated output.

| `AssistantResponse` surface | Source at this baseline |
| --- | --- |
| `sources` | `domain_view.source_refs` |
| `pending_questions` | `domain_view.question_refs` |
| `approval_requests` | `domain_view.approval_refs` |
| `workflow_updates` | `domain_view.workflow_refs` |
| `memory_updates` | `domain_view.memory_proposal_refs` |
| `warnings` | `domain_view.warning_refs` |
| `reasoning_summary` | `result_refs` and `contradiction_refs` — a public, structured explanation surface only, never chain-of-thought |
| `domain_state` | `primary_domain`, `supporting_domains`, `confidence`, `status` |
| `proposed_actions` | empty at this baseline — no public-safe application field carries actions, and none is invented |

The assistant message text is deterministic and truthful: it follows the public
application status/error semantics (`response.error.message` when the
application reported a safe failure, a fixed clarification text for
`NEEDS_CLARIFICATION`, a fixed routed text for `ROUTED`, otherwise the public
status). No model is called and no generated domain answer is pretended.

This is also why the **honest boundary** of a plain conversational turn is the
same one Phase 11.3 documented: the frozen public message carries no intent
hint, so the canonical deterministic intent resolver answers
`NEEDS_CLARIFICATION` with route `none` — the conversational boundary fabricates
no model answer. `AT-DP-105` proves the composed canonical domain route is live
with an in-graph, mock-free positive control (two directly built structured
requests driven through the same real orchestrator) rather than by forcing a
routed conversational turn that the public payload cannot express.

## 12. HTTP adapter surface

`cmm/api/app.py` gains one optional keyword — `create_app(gateway, *, conversation=None)`
— and five additive routes. The handlers still only parse, delegate to the one
`ConversationService`, serialize and map safe errors; a caller that passes no
service keeps the pre-existing routes and OpenAPI of every pre-existing
endpoint unchanged, and every conversation route answers the frozen
capability-unavailable failure instead of failing at construction.

| Method | Path | Delegates to | Success status | Application operation reached |
| --- | --- | --- | --- | --- |
| `GET` | `/v1/conversations/{session_id}` | `ConversationService.load` | `200` | canonical session read via the shared-session adapter; no application operation dispatched; creates no public resource |
| `POST` | `/v1/conversations/{session_id}/messages` | `ConversationService.submit` | `200` | `MESSAGE_SUBMIT` |
| `POST` | `/v1/conversations/{session_id}/messages/{message_id}/edit` | `ConversationService.edit` | `200` | `MESSAGE_SUBMIT` |
| `POST` | `/v1/conversations/{session_id}/responses/{message_id}/regenerate` | `ConversationService.regenerate` | `200` | `MESSAGE_SUBMIT` |
| `POST` | `/v1/conversations/requests/{request_id}/cancel` | `ConversationService.cancel` | `200` | `REQUEST_CANCEL` |

Rules the adapter holds to:

- every conversation answer is the **one frozen public envelope**
  (`request_id`, `api_version`, `status`, `data`, `error`) whose `data` is the
  canonical conversational contract's own serialization
  (`AssistantResponse.to_dict()` / `ConversationState.to_dict()`), re-validated
  by the transport DTOs, so a client never sees an ad-hoc shape and a drifted
  projection is rejected at the transport boundary instead of being served;
- the session identity is the path identity, the message identity is the body
  identity, and every identity, revision and timestamp is caller-supplied: the
  adapter generates none of them, exposes no `lineage` field (the service owns
  lineage) and exposes no `metadata` field (the canonical session owns the
  committed transcript). `bot_id` is carried as the opaque association; no
  `idempotency_key` exists on any conversation body;
- conversational boundary failures map onto the application layer's own typed,
  safe failures (never a copy): `invalid_request -> 400`,
  `session_not_found -> 404`, `session_conflict -> 409`,
  `capability_unavailable -> 503`, `policy_denied -> 403`,
  `approval_required -> 409`, `internal_failure -> 500`; an unknown code falls
  to the one generic internal failure;
- caller-derived values the public conversational contract rejects while they
  are built are reported as `400 INVALID_REQUEST` with the frozen contract
  reason code and the service is never invoked; every other failure — including
  a defect inside the service's own handling and a drifted projection of a value
  the service already returned — fails closed as `500 INTERNAL_FAILURE` with the
  generic public message and empty details, so a server-side defect is never
  published as the caller's invalid request and no internal text, path or
  traceback can escape;
- the five paths, the frozen envelope, the success statuses and the generated
  OpenAPI operation ids are frozen by the API gates (`tests/api/test_openapi.py`,
  `tests/api/test_http_v1.py`) and by `AT-DP-103`'s route-surface scenarios,
  which were extended strictly additively (§14).

## 13. Architecture and security gates

`tests/conversation/test_architecture.py` (125 tests) is the Phase 11.5
architecture/anti-parallel-infrastructure and security gate. It enforces,
over the real package:

- **no parallel owner** — the frozen forbidden-owner vocabulary of the design
  (spec §24) plus an owner-suffix rule (`...Store`, `...Repository`,
  `...Runtime`, `...Engine`, `...Router`, `...Planner`, `...Manager`,
  `...Registry`, with version-suffix tolerance) screened where a name is
  declared, constructed (`type(...)`, `make_dataclass(...)`,
  `exec`/`eval` code objects, `setattr(...)`), or exported as a module-level
  alias; the exact new-owner allowlist of `cmm.conversation` is **empty**;
- **no forbidden import** — `cmm.memory`, `cmm.cognitive`, `cmm.agent_runtime`,
  `kernel.llm` and `CMMChat` are forbidden outright, `cmm.api` is *explicitly*
  forbidden (the conversation layer consumes the application boundary, never
  the transport adapter), and the internal-import allowlist is exact and
  frozen per module;
- **dynamic import machinery is banned outright** —
  `importlib.import_module`, `__import__` and `sys.modules[...]` are offenders
  by mechanism, because the static extraction cannot see a dynamic target;
- **structured reverse-dependency checks** — `cmm.runtime`, `cmm.domains`,
  `cmm.cognitive`, `cmm.agent_runtime`, `cmm.orchestration` and `kernel` never
  import `cmm.conversation` or `cmm.api`, each scanned at its real path and each
  carrying a liveness anchor so a deleted, moved or empty layer fails loudly;
- **public serialization adversaries** — a recursive structural walker over
  `ConversationMessage.to_dict()` and `AssistantResponse.to_dict()` output shows
  no secret-shaped or hidden-reasoning key and no forbidden fragment in any
  string value, with the fragment list pinned to be a superset of the production
  key screen; attacker metadata at the deepest admissible mapping depth is
  rejected before persistence;
- **runtime import closure with three attribution lenses** — a fresh subprocess
  imports every package module through a recording `builtins.__import__` and
  reports (a) modules/classes/functions/instances *bound into* a package module
  namespace that are, or are defined in, a forbidden module, (b) imports
  *executed by* a package module that resolve into a forbidden module, and
  (c) forbidden modules loaded *beyond the sanctioned seams' own closure*.
  The binding lens is what catches an allowed seam re-exporting a forbidden
  module and a bound `importlib.import_module(...)` result.

### 13.1 Measured residual limits (stated openly)

Two residual limits are measured facts, recorded here rather than softened:

1. **A structurally invisible execution path.** The structural rule bans
   `importlib.import_module`, `__import__` and `sys.modules[...]`, but an import
   whose only execution path is an `exec`/`eval` call with a **literal payload
   inside a function body** is not caught by any rule nor by the three runtime
   lenses: the dynamic-identifier rule screens an `exec`/`eval` code object only
   when its constant text spells a forbidden *owner or hidden-reasoning name*
   (not a module name), and nothing is imported at import time, so no runtime
   lens observes it either.
2. **Why the runtime check uses three lenses instead of the blanket form.**
   The blanket `sys.modules`-delta form — "no forbidden module anywhere in the
   subprocess delta" — was measured and cannot ship on this repository:
   importing `cmm.application` **or** `cmm.domains.interface_integration_contracts`
   alone already loads **271** forbidden modules (`cmm.memory` 10 /
   `cmm.cognitive` 41 / `cmm.agent_runtime` 188 / `kernel.llm` 32) through
   pre-existing eager imports outside `cmm/conversation`; `cmm.platform` loads
   **32** and `cmm.runtime.sessions` loads **10** on its own, while importing
   `cmm.conversation` alone loads **0**. A blanket check would therefore fail on
   pre-existing production behavior outside this phase's authority, and a
   baseline-subtracted variant would be blind to exactly the four prefixes it
   must screen. Attribution is the honest form of the same check.

Both limits are recorded in the gate's own comments and pins; neither weakens
any rule that *is* enforced, and every evasion form the gate covers is pinned by
injecting it into a throwaway copy of the package.

## 14. Closed-phase adjustments (all additive)

Phase 11.5 touched closed-phase test surfaces in exactly two kinds of change,
both sanctioned by the implementation plan's regression-scope rule and both
recorded here prominently.

### 14.1 The two additive closed-phase architecture-gate seams

- `tests/application/test_architecture.py` — `cmm.conversation` becomes the
  sanctioned conversational consumer of the application boundary (spec §25:
  `cmm.conversation -> cmm.application`). The exemption is a *subtree* skip with
  a paired honesty/liveness assertion
  (`test_the_conversation_package_exemption_is_live_and_honest`): the package
  must exist, at least one of its modules must really import `cmm.application`,
  and no conversation module may import `cmm.api`.
- `tests/api/test_architecture.py` — `cmm.conversation` joins the adapter's
  exact internal-import allowlist, with a paired liveness assertion
  (`test_the_conversation_adapter_seam_is_live_and_honest`) proving at least one
  `cmm.api` module really imports the conversation layer, so the exemption
  cannot go stale. Every forbidden-canonical-owner, bypass-package and
  string-dispatch rule stays in force.

`tests/platform/test_architecture.py`'s sanctioned platform-consumer allowlist
gained `conversation` beside `orchestration` and `application`, exactly as the
Phase 11.3 documentation recorded the same class of Phase 11.1 adjustment.

### 14.2 The repaired closed-phase pins

These closed-phase tests failed **only** because they freeze an exact set,
count or allowlist that the sanctioned additive change extends. Each repair is
an enumeration extension carrying a documented Phase 11.5/DP-105 comment;
no assertion, threshold or logic was weakened:

| File | Pin repaired |
| --- | --- |
| `tests/application/test_channels.py` | The frozen `ApplicationChannel` value set gained `conversation`, plus a new test proving the conversation channel is forwarded to `OrchestrationChannel.CONVERSATION` and that the conversation envelope equals the API envelope for an equal request identity |
| `tests/application/test_local_runtime.py` | The pinned attribute set of `LocalApplicationRuntime` gained the sanctioned read-only `session_store` reference (purely additive; no line removed) |
| `tests/api/test_http_v1.py` | `FROZEN_V1_PATHS` gained the five conversation paths (purely additive) |
| `tests/api/test_openapi.py` | The frozen enumerations extended: `FROZEN_V1_ROUTES`, `FROZEN_V1_OPERATION_IDS`, `FROZEN_V1_OPERATIONS`, `FROZEN_V1_SUCCESS_STATUS` and `FROZEN_APPLICATION_SCHEMAS`; the "one public envelope for every JSON operation" test needed no edit because every conversation route publishes the one envelope |
| `tests/application/test_phase11_3_dp103_acceptance.py` | Scenario G's exact `/v1` path set gained the five conversation paths; scenario M's `APIRoute` count changed `7 -> 12` |
| `tests/platform/test_architecture.py` | The sanctioned platform-consumer allowlist gained `conversation` (see §14.1) |

### 14.3 Additive test coverage in closed-phase files

`tests/application/test_contracts.py` and `tests/application/test_requests.py`
each gained new tests (§6) without changing any existing expectation.

### 14.4 Plan-scope deviation discovered during review

The committed plan's Task 4 file list named neither `tests/application/test_channels.py`
nor the architecture-gate allowlists, even though the sanctioned
`ApplicationChannel.CONVERSATION` seam genuinely had to touch them: the frozen
channel-value pin fails the moment the enum grows, and the architecture gates
must name the conversation package as a sanctioned consumer. The files were
changed anyway — minimally, additively and with the documented Phase 11.5/DP-105
comments — and the deviation is recorded here (and in the phase's SDD ledger).
The plan file itself stays untouched, as the permanent constraints require.

## 15. Security posture and side-effect boundary

- No direct external network I/O, no file I/O and no database; the only
  persistence path is the canonical `SessionStore` the composition supplies.
- No secret, credential or token is read, stored or exposed; public metadata is
  bounded, secret-free and recursively immutable, and the key screen rejects
  secret-shaped and internal-detail-shaped names structurally.
- No hidden reasoning: `reasoning_summary` is a public reference surface only,
  the gate screens every defined identifier for hidden-reasoning forms, and no
  raw exception, traceback, filesystem path or internal class name can cross
  the boundary.
- No authentication or authorization layer is implemented or faked; `actor_id`
  and `bot_id` are descriptive and confer nothing.
- The only owned side effects of one turn are one canonical gateway call, whose
  own effects are Phase 11.2/11.3-owned, and one canonical session commit
  through the canonical store.
- Constructed values that are already frozen are never mutated, and every
  public contract is immutable by construction (`frozen`, `slots`,
  `MappingProxyType`, tuples).

## 16. Explicit non-goals

Phase 11.5 implements the canonical conversational interface and deliberately
does not implement:

- CMMChat (visual UI, desktop/mobile/web shell) or any client application;
- a CMM Bots runtime, Bot registry, Bot identity/configuration layer or Bot
  tool/permission granting;
- a conversation file workspace, global artifact library, object storage, file
  version history, cross-device synchronization or file search;
- document upload or ingestion — `document_upload` stays explicitly
  `unavailable`;
- a Model Gateway, provider registry redesign, provider token-streaming runtime,
  Web Search, Browser Use or Computer Use ownership;
- a cancellable-request runtime, active-request registry, scheduler, queue or
  background worker system — cancellation stays explicitly `CAPABILITY_UNAVAILABLE`;
- live provider-token streaming — the effective streaming mode stays
  `response_event_stream`;
- WebSockets or any second transport;
- a generalized conversation branch/version-control system;
- new workflow, approval, execution, memory or knowledge runtimes or stores;
- conversation import/export, communication profiles/personas, audio ingestion,
  or the later file/artifact and Bot phases (11.55–11.59);
- authentication/authorization systems and the general storage architecture of
  later Phase 11 subphases;
- a `ConversationStore`, `ConversationRepository`, `ConversationRuntime`,
  `ConversationEngine`, `ConversationRouter`, `ConversationPlanner`,
  `ConversationApprovalManager`, `ConversationPermissionEngine`,
  `ConversationMemoryStore`, `ConversationKnowledgeStore`,
  `ConversationProviderRegistry`, `ConversationAgentRuntime`,
  `ConversationWorkflowEngine` or `ActiveRequestRegistry` — the gate's new-owner
  allowlist is empty by design.

## 17. Testing and observed evidence

`AT-DP-105` (`tests/conversation/test_phase11_5_dp105_acceptance.py`, one
connected acceptance) exercises the real canonical vertical — canonical
`SharedSessionState` -> official `InMemorySessionStore` -> `ConversationService`
-> `ApplicationGateway` -> `RequestApplicationService` -> the real Phase 11.2
`Orchestrator` -> real canonical domain routing and a genuine authorized
`ConversationalDomainView` (a real `DefaultDomainInterfaceIntegrator` projection
over the real resolver -> composer -> presentation chain) -> `AssistantResponse`
-> `conversation.v1` persisted through the canonical store. Nothing critical is
mocked; traversal is proven with instrumented *real* components (the gateway's
`handle` is wrapped, never subclassed) and cross-checked against the canonical
decision repository and event sink. The scenario map is A–I (first turn;
second-turn continuity; stale revision; edit lineage; regeneration lineage;
capabilities and cancellation; Bot and attachment non-authority; visibility is
not authorization; public safety), closed by the in-graph domain-route positive
control described in §11. Frozen traversal totals are asserted at the end so a
silently shortened run fails.

Focused suite composition (`tests/conversation/`, 685 tests):

```text
test_contracts.py                 256
test_architecture.py              125
test_service.py                    86
test_state.py                      62
test_projection.py                 48
test_capabilities.py               41
test_http_adapter.py               37
test_platform_module.py            29
test_phase11_5_dp105_acceptance.py   1
```

Pre-audit evidence observed in this repository while preparing this
documentation (CWD `/Users/chris/CMM OS`, `"/Users/chris/CMM OS/.venv/bin/python"`,
Python 3.14):

```text
tests/conversation                                     685 passed
tests/conversation/test_phase11_5_dp105_acceptance.py    1 passed
inherited connected acceptance chain                   249 passed
  (AT-DP-105 + AT-DP-104 + AT-DP-103 + AT-DP-102 + AT-DP-101 + AT-DP-134 + AT-DP-045)
```

The one `pytest` warning observed in the conversation suite is the pre-existing
third-party `StarletteDeprecationWarning` from `fastapi.testclient`; it is
unrelated to Phase 11.5. The complete Phase 11.5 gate run and the exact-HEAD
audit bundle are produced by the implementation plan's later verification tasks
and reported in their handoff, to be independently re-verified by the
independent audit. No repo-wide suite has been run for this documentation task.

## 18. Traceability

| Item | Value |
| --- | --- |
| Requirement | `F11-019 — Canonical Conversational Interface` |
| Design Point | `DP-105 — Session-Backed Canonical Conversation Boundary` |
| Acceptance test | `AT-DP-105 — Canonical Conversational Interaction Acceptance` — `tests/conversation/test_phase11_5_dp105_acceptance.py` |
| Production package | `cmm/conversation/` (8 modules) |
| Additive seams in closed packages | `cmm/application/contracts.py`, `cmm/application/requests.py`, `cmm/application/local_runtime.py`, `cmm/api/app.py`, `cmm/api/models.py` |
| Focused suite | `tests/conversation/` (685 tests) |
| Architecture/security gate | `tests/conversation/test_architecture.py` (125 tests) |
| Inherited gates touched | `tests/application/test_architecture.py`; `tests/api/test_architecture.py`; `tests/platform/test_architecture.py`; `tests/api/test_http_v1.py`; `tests/api/test_openapi.py` |
| Reference documentation | `docs/reference/phase-11-conversational-interface.md` (this document) |
| Requirements matrix | `docs/reference/phase-11-stable-integrated-platform-requirements-matrix.md` (`F11-019` -> `DP-105` -> `AT-DP-105`) |
| Detailed roadmap | `docs/roadmap/phase-11-stable-integrated-platform.md` §11.5 |
| Design specification | `docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md` |
| Implementation plan | `docs/superpowers/plans/2026-09-17-phase-11.5-conversational-interface-implementation-plan.md` |
| Inherited requirements reused | `F11-018` / `DP-104` (Phase 11.4), `F11-017` / `DP-103` (Phase 11.3), `F11-016` / `DP-102` (Phase 11.2), `F11-015` / `DP-101` (Phase 11.1) and `F11-014` / `DP-134` (Phase 11.34) — referenced, not reopened and not modified |
| Inherited acceptance regressions | `AT-DP-104` — `tests/cli/test_phase11_4_dp104_acceptance.py`; `AT-DP-103` — `tests/application/test_phase11_3_dp103_acceptance.py`; `AT-DP-102` — `tests/orchestration/test_phase11_2_dp102_acceptance.py`; `AT-DP-101` — `tests/platform/test_phase11_1_dp101_acceptance.py`; `AT-DP-134` — `tests/llm/test_provider_registry_dp134_acceptance.py`; `AT-DP-045` — `tests/domains/test_domain_interface_dp045_acceptance.py` |
| Mapping status | `IMPLEMENTED_AWAITING_INDEPENDENT_AUDIT` |
| Next step | independent audit of the exact-HEAD implementation bundle |

## 19. Verification and audit state

```text
PHASE11_5=IMPLEMENTED_AWAITING_INDEPENDENT_AUDIT

F11_019=IMPLEMENTED_AWAITING_INDEPENDENT_AUDIT
DP_105=IMPLEMENTED_AWAITING_INDEPENDENT_AUDIT
AT_DP_105=GREEN_IN_REPOSITORY

CLOSURE_ELIGIBLE=NO
AUDIT_STATUS=PENDING_INDEPENDENT_AUDIT
NEXT=INDEPENDENT_AUDIT
```

This document records the implemented pre-audit state only. Phase 11.5 may be
closed only after an independent audit returns the closure-gate evidence the
design specification's §35 requires — zero blockers, zero majors, the Design
Point verified as existing, the connected acceptance passing, and closure
eligibility granted. None of those states is claimed here, and no closure
language is written for Phase 11.5 before that audit exists. The historical
Phase 11.1–11.4 closure records referenced by this document remain unchanged
and are owned by their own reference documents
(`docs/reference/phase-11-integration-core.md`,
`docs/reference/phase-11-orchestration-layer.md`,
`docs/reference/phase-11-application-backend.md`,
`docs/reference/phase-11-cli.md`).
