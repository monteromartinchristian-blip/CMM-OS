# Phase 11 — Model Gateway

**Project:** CMM OS
**Subphase:** 11.21 — Model Gateway
**Requirement:** `F11-020`
**Design Point:** `DP-121` — Canonical Provider-Independent Model Gateway
**Acceptance test:** `AT-DP-121` — `tests/llm/test_phase_11_21_dp121_acceptance.py`
**Design specification:** `docs/superpowers/specs/2026-09-25-phase-11.21-model-gateway-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-09-25-phase-11.21-model-gateway-implementation-plan.md`
**Pre-audit state:** implemented and pending independent audit (see §16)

This document describes the behaviour that exists in this repository. It does
not describe planned Phase 11.35+ routing-policy intelligence, Phase 11.44 usage
audit persistence or the later Phase 11.50 client slice.

---

## 1. Scope

Phase 11.21 introduces exactly one new architectural authority: **provider-
independent model-call normalization and execution**. The Model Gateway is the
single execution boundary through which CMM OS performs a model call.

It owns:

- canonical model-call request normalization;
- adapter resolution for the already-selected provider/model;
- exact capability, reasoning-effort and modality validation before provider I/O;
- provider request translation and provider response normalization;
- provider token-stream normalization;
- model-call cancellation and timeout mechanics;
- bounded transport retry;
- deterministic execution of an already-authorized fallback sequence;
- canonical privacy enforcement immediately before egress;
- per-call usage, cost and latency normalization;
- safe model-call evidence.

It owns none of: provider identity, model inventory, routing policy, user model
preferences, conversation state, session or file persistence, memory,
knowledge, domain logic, agent planning, workflow execution, tool execution,
permission or approval authority, validation authority, event-system authority
or application-backend authority.

## 2. Canonical ownership

| Concern | Canonical owner reused unchanged |
|---|---|
| Provider identity | `kernel.llm.provider_registry.ProviderRegistry` |
| Model inventory | `kernel.llm.model_catalog.ModelCatalog` (bound to that registry) |
| Model requirements / basic selection | `kernel.llm.model_selection`, `kernel.llm.model_router` |
| Fallback decision authority | `cmm.agent_runtime.model_fallback_decision_engine` |
| Agent-run execution record | `cmm.agent_runtime.model_execution_contracts` |
| Privacy evaluation | `cmm.cognitive.privacy.evaluate_privacy_operation` |
| Application composition | Phase 11.1 `ApplicationContainer` / `ServiceBinding` |
| Application / conversation boundaries | Phase 11.3 `cmm/application`, Phase 11.5 `cmm/conversation` |

New production modules:

```text
kernel/llm/model_gateway.py
kernel/llm/model_gateway_contracts.py
kernel/llm/model_gateway_errors.py
kernel/llm/model_provider_adapter.py
kernel/llm/model_streaming.py
cmm/agent_runtime/model_egress_privacy_adapter.py
cmm/agent_runtime/model_fallback_gateway_adapter.py
cmm/agent_runtime/model_execution_evidence_projection.py
```

`kernel.llm` stays below the `cmm` layer: the gateway consumes canonical privacy
and canonical fallback planning through **injected narrow seams**
(`PrivacyEgressGate`, `ModelFallbackPlanner`) whose canonical implementations
live in `cmm.agent_runtime`. No parallel provider registry, model catalog,
router, policy engine, privacy engine, validation engine, tool executor,
conversation/session store, application backend, event bus or model store is
created; `tests/llm/test_model_gateway_architecture.py` fails closed if one
appears.

## 3. Public contracts

`kernel/llm/model_gateway_contracts.py` publishes the immutable, provider-
independent contract surface:

```text
ReasoningEffort                      closed effort enum (DEFAULT, NONE, LOW, MEDIUM, HIGH, EXTRA_HIGH)
ModelSelectionMode                   EXPLICIT | AUTO
InputPartKind / InputModality        TEXT | IMAGE | DOCUMENT
ModelInputPart                       real content + media type, digest, safe display name
ModelToolDefinition                  identity, description, input schema (no callback)
ModelToolCall                        call id, tool id, arguments (no authority)
StructuredOutputRequirement          required flag, schema, schema id/version
ModelGatewayRequest                  the canonical request
ModelGatewayResponse                 the canonical normalized response
ModelUsage                           input/output/cached tokens, cost, cost source, currency
ModelExecutionFacts                  safe per-call evidence
ModelStreamEventType / ModelStreamEvent   the canonical stream vocabulary
ModelCapabilityProjection            read-only capability view for clients
ModelGatewayRetryPolicy              explicit bounded retry policy
ModelFallbackAttempt                 gateway-side attempt record for the planner
PrivacyEgressDecision / PrivacyEgressGate
ModelExecutionEvidenceSink / InMemoryModelExecutionEvidenceSink
```

Safety invariants enforced at construction time:

- raw image/document bytes never appear in ordinary serialization — `to_dict()`
  exposes only `kind`, `media_type`, `byte_length`, `content_digest`,
  `display_name` and screened metadata;
- a content digest is always derived from the content, so a forged digest is
  rejected;
- public metadata must be JSON-safe and secret-free, recursively; a
  secret-shaped key fails closed;
- path- or URL-shaped display names are rejected;
- immutability is structural (`frozen=True, slots=True`), and unknown fields are
  rejected rather than ignored.

`kernel/llm/model_gateway_errors.py` publishes the closed error taxonomy:
`MODEL_NOT_FOUND`, `PROVIDER_NOT_AVAILABLE`, `MODEL_UNAVAILABLE`,
`CAPABILITY_UNSUPPORTED`, `UNSUPPORTED_REASONING_EFFORT`,
`INPUT_MODALITY_UNSUPPORTED`, `PRIVACY_DENIED`, `PROVIDER_REQUEST_INVALID`,
`PROVIDER_TIMEOUT`, `PROVIDER_FAILURE`, `STREAM_FAILURE`,
`MODEL_CALL_CANCELLED`, `STRUCTURED_OUTPUT_INVALID`, `TOOL_CALL_INVALID`,
`FALLBACK_EXHAUSTED`. Messages and details are safe; raw provider exceptions are
never propagated.

## 4. Reasoning effort

Reasoning effort is the closed `ReasoningEffort` enum. `DEFAULT` means "impose
no explicit override" and is always acceptable; every other level must be
declared by the model's canonical `ModelCapabilities.reasoning_efforts`.

- an undeclared level fails with `UNSUPPORTED_REASONING_EFFORT` **before** any
  provider I/O;
- there is no silent downgrade (`HIGH → MEDIUM`), no silent upgrade
  (`NONE → DEFAULT`) and no substitution;
- provider-native names are translated inside the adapter only
  (`reasoning_effort_map`) and never appear in a canonical contract;
- an adapter that reports a different effective effort than requested is a
  contract violation and fails closed;
- requested and effective effort are recorded in the safe evidence record.

## 5. Multimodal inputs

`IMAGE` and `DOCUMENT` parts carry the real authorized bytes. A filename, an
attachment identifier or a placeholder string cannot stand in for content: a
part cannot even be constructed without non-empty bytes, and the official
in-memory adapter records the actual `(kind, byte_length, content_digest)` it
received.

- image input requires declared `vision`; otherwise
  `INPUT_MODALITY_UNSUPPORTED` before provider I/O;
- a document part requires the model to declare that exact media type
  (`application/pdf`, `text/plain` and `text/markdown` by default);
- a PDF is transported as document content and is **never** silently converted
  to extracted text;
- the gateway owns no file store, reads no filesystem path because a request
  contains one, and fetches no URL. A path-shaped prompt is transported as
  literal text.

## 6. Provider adapter protocol

`kernel/llm/model_provider_adapter.py` defines the narrow boundary:

```python
class ModelProviderAdapter(Protocol):
    provider_id: str
    def execute(self, request: ProviderModelRequest, *, cancellation=None) -> ProviderModelResponse: ...
    def stream(self, request: ProviderModelRequest, *, cancellation=None) -> Iterator[ProviderStreamEvent]: ...
```

- `ModelProviderAdapterRegistry` resolves exactly one executor per canonical
  provider identity. It stores no provider metadata, credentials, capability
  truth or policy, so it is an execution registry and cannot become a second
  provider registry. A duplicate identity is rejected and a missing adapter
  fails closed with `PROVIDER_NOT_AVAILABLE`.
- **Gateway core never branches on a provider name.** Architecture tests fail
  closed on any provider-name dispatch chain.
- `InMemoryModelProviderAdapter` is the official in-memory adapter used by
  connected acceptance: a real implementation of the protocol with deterministic
  scripted scenarios (text, effort translation, images, documents, structured
  output, tool calls, streaming, cancellation, failures, timeouts, usage).
- `LLMProviderModelAdapter` adapts the pre-existing canonical `LLMProvider`
  implementations (OpenAI-compatible, Ollama, mock) instead of forking them, and
  honestly refuses multimodal input, explicit reasoning effort and token
  streaming before any provider call.

## 7. Tool calls

The gateway normalizes tool declarations and provider-generated calls; it never
executes a tool.

```text
canonical ModelToolDefinition
        → gateway
        → provider-native tool schema
        → provider tool call
        → canonical ModelToolCall
        → returned to the caller (Agent Runtime / operation authority)
```

`ModelToolDefinition` has no callback, handler or executor field, and
`ModelToolCall` carries no permission, approval or execution state, so a
provider tool call grants zero authority by itself. A tool call the request
never declared fails closed with `TOOL_CALL_INVALID`; matching a declared tool to
a call and granting authority remain canonical Agent Runtime / operation policy.

## 8. Structured output

A request may declare a `StructuredOutputRequirement` (required flag, optional
JSON schema, schema id/version). The gateway translates it to the adapter
boundary, normalizes the returned structured value deterministically and
requires the model to declare `structured_output` (and `json_schema` when a
schema is present) before provider I/O. A missing required result fails safely
with `STRUCTURED_OUTPUT_INVALID`; an optional result may be absent.

The gateway is not a second semantic or domain validation system: schema
conformance beyond the deterministic contract check remains owned by the
canonical Phase 7 validation authority.

## 9. Streaming

`kernel/llm/model_gateway.py::ModelGateway.stream` owns the canonical provider-
token stream, with `ModelStreamNormalizer` providing the deterministic
bookkeeping:

- exactly one leading `STARTED` event (an adapter `STARTED` is absorbed);
- contiguous sequence numbers from `0`;
- `CONTENT_DELTA`, `TOOL_CALL_DELTA` and `USAGE` events, with `USAGE` allowed
  before completion;
- exactly one terminal `COMPLETED`, `CANCELLED` or `ERROR` event, and nothing
  emitted after it (a duplicate terminal is dropped);
- a stream that ends without a terminal is closed with `STREAM_FAILURE`;
- a raw provider exception is normalized without leaking its text;
- no hidden chain-of-thought is representable: the event contract has no field
  for it and only safe requested/effective effort metadata is exposed.

`execute()` refuses a streaming-intended request (`request.stream=True`) with
`PROVIDER_REQUEST_INVALID`; `stream()` requires the declared `streaming`
capability. Streaming is deliberately **not** retried, because re-attempting
after emitted content would duplicate it.

## 10. Cancellation

`ModelCallCancellation` is a narrow, thread-safe, idempotent token scoped to one
model call, reachable through `ModelCallHandle` (`ModelGateway.open_call`).
Cancelling before or during a call or stream produces exactly one deterministic
`CANCELLED` terminal, stops every later event, and never touches another call,
workflow or session. There is no global cancellation runtime and no application
`/runs/{id}/cancel` surface.

## 11. Privacy

`kernel.llm` reaches canonical privacy only through the injected
`PrivacyEgressGate`. Its canonical implementation,
`cmm.agent_runtime.model_egress_privacy_adapter.CanonicalPrivacyEgressGate`, owns
no policy: every decision delegates to
`cmm.cognitive.privacy.evaluate_privacy_operation` and is projected into the
safe gateway decision contract (a test asserts the projection equals the
canonical decision field by field).

Enforced invariants:

- `LOCAL_ONLY` plus a remote provider is denied **before** any adapter call;
- remote transmission requires canonical privacy metadata **and** a configured
  canonical privacy authority — provider availability never grants permission;
- a failing or foreign privacy authority denies egress (fail closed);
- image and document content follow exactly the same egress decision as text;
- privacy metadata is never forwarded to the adapter;
- approval cannot widen a denial, and Phase 11.21 has no approval authority at
  all, so a policy that requires approval stays denied.

## 12. Timeout, retry and fallback

**Timeout.** A per-call timeout is finite, hard-capped by the gateway ceiling
(`max_timeout_seconds`, default 300s) and normalized to `PROVIDER_TIMEOUT`. The
call is abandoned through its cancellation token and recorded as `timed_out`
with an elapsed latency, so no call is left reported as running. A streaming
call enforces the same deadline between events.

**Retry.** `ModelGatewayRetryPolicy` is explicit and capped at
`MAX_RETRY_ATTEMPTS = 5`; the default is one attempt (no retry). Only the
canonical retryable transport codes are retried — `PROVIDER_TIMEOUT`,
`PROVIDER_FAILURE` (when the adapter marks it transient) and `STREAM_FAILURE` —
always on the exact same model and provider. Privacy denials, invalid requests,
unsupported capabilities and reasoning efforts, explicit model incompatibility
and cancellation are never retried.

**Fallback.** Fallback is mechanics, not routing-policy intelligence:

- fallback happens only after a retryable transport-level primary failure, only
  for an explicitly authorized `fallback_model_ids` sequence, and only when a
  canonical planner is injected;
- `cmm.agent_runtime.model_fallback_gateway_adapter.ModelGatewayFallbackPlanner`
  delegates to the existing `ModelFallbackDecisionEngine`, presenting the
  caller's authorized order as the candidate list with an identity fallback
  provider, so the gateway never re-ranks or re-routes;
- every candidate must still pass the full preflight (capabilities, reasoning
  effort, modalities, tools, structured output, context, canonical privacy)
  before its adapter may run; an incompatible candidate is skipped and never
  executed, and a requirement is never relaxed;
- an exhausted, unplannable or fully skipped sequence fails with
  `FALLBACK_EXHAUSTED`; an explicit model without an authorized sequence never
  changes.

## 13. Usage, cost and latency accounting

Accounting is factual and per call: provider id, model id, input/output/cached
tokens, latency, finish reason, stream/cancel outcome and cost.

- a missing provider metric stays `None` and is never fabricated as `0`; a
  provider-reported zero is preserved;
- provider-reported cost wins over any derived value;
- `derive_model_call_cost` is the single pure, deterministic helper that
  produces a `catalog_derived` cost, only when canonical pricing metadata can
  price the call (an unknown count or a missing price yields `None`); cached
  tokens are billed at the cached rate when published and at the input rate
  otherwise, and are never billed twice;
- no budget, monthly ledger, dashboard, spend alert or adaptive cheap-model
  routing is introduced (that is Phase 11.38).

## 14. Platform composition

`cmm.platform.canonical.model_gateway_binding` binds the one canonical gateway:

```text
service_id        model.gateway
owner             kernel.llm
mode              local
authority         none (the provider-registry authority stays unique)
runtime contract  kernel.llm.model_gateway.ModelGateway
dependencies      provider.registry  (the exact canonical Phase 11.34 boundary)
```

`PROVIDER_REGISTRY_CONTRACT_VERSION` is declared once and reused by
`provider_registry_binding` and the new dependency edge, because platform
compatibility is exact and the provider registry is the only canonical binding
whose versions differ from the platform defaults. A composed container is
`READY`, `container.get_service("model.gateway").provider_registry` is the exact
`provider.registry` instance and the gateway's catalog is provably bound to that
same registry. A missing or schema-mismatched provider dependency fails
readiness, a duplicate gateway service is rejected, and composition inspection
names the service without exposing any sensitive key.

## 15. Known limits

- **Capability metadata persistence.** The additive `ModelCapabilities` fields
  (`reasoning_efforts`, `document_media_types`, `streaming`) are not persisted
  by the Phase 11.34 provider-state repository, whose persistence authority and
  state schema version Phase 11.21 must not change. A model restored from
  persisted state therefore fails closed — an undeclared effort or document
  media type is unavailable — instead of guessing. Persisting the new seam
  belongs to a later provider-registry state revision.
- **Streaming retry.** A stream is never retried, even if it failed before the
  first content event.
- **Stream interruptibility.** Timeout and cancellation are enforced between
  events; a provider that blocks inside a single chunk is not interruptible
  except by adapter cooperation with the cancellation token.
- **`AUTO` selection.** `AUTO` may reuse only the existing canonical
  requirement/selection path. Phase 11.21 adds no quality scoring, cost
  optimization, preference learning, adaptive ranking or benchmark routing. An
  `AUTO` request that cannot be resolved through canonical selection fails with
  `MODEL_NOT_FOUND`; Phase 11.21 does not implement a candidate loop for it.
- **Agent-run evidence projection.** `ModelExecutionRecord` is agent-run scoped
  and its token/cost fields are non-optional integers. The projection therefore
  writes an unknown metric as the record's own default **and** marks it in
  `reason_codes`/`metadata` (`usage_unknown:<field>`); the gateway's
  `ModelExecutionFacts` remain the source of truth for unknown-versus-zero.
- **`kernel`/`cmm` direction.** Privacy and fallback planning are reached
  through injected seams; the gateway never imports `cmm`.
- No Phase 11.44 usage-audit persistence, no Phase 11.50 client surface, no
  MCP/Actions, no audio ingestion, no new event bus, no new permission or
  approval engine.

## 16. Test evidence

Local, pre-audit evidence only (`AT_DP_121=PASS` here is local test evidence,
not independent verification):

| Gate | Command | Result |
|---|---|---|
| Focused gateway suite | 17 `tests/llm/test_model_gateway_*.py` + `test_phase11_21_dp121_acceptance.py` | 366 passed |
| `AT-DP-121` | `tests/llm/test_phase11_21_dp121_acceptance.py` | 31 passed |
| LLM suite | `tests/llm` | green |
| Agent Runtime model suites | `tests/agent_runtime` model tests | green |
| Platform binding | `tests/platform/test_model_gateway_binding.py` | 11 passed |
| Inherited acceptances | `AT-DP-134`, `AT-DP-101`, `AT-DP-102`, `AT-DP-103`, `AT-DP-104`, `AT-DP-105` | all pass |
| Repository-wide Ruff | `ruff check .` | 837 findings, identical to the inspected baseline (zero new) |

Test modules:

```text
tests/llm/test_model_gateway_architecture.py
tests/llm/test_model_gateway_contracts.py
tests/llm/test_model_gateway_capabilities.py
tests/llm/test_model_gateway_adapters.py
tests/llm/test_model_gateway_execution.py
tests/llm/test_model_gateway_reasoning.py
tests/llm/test_model_gateway_multimodal.py
tests/llm/test_model_gateway_structured_output.py
tests/llm/test_model_gateway_tools.py
tests/llm/test_model_gateway_streaming.py
tests/llm/test_model_gateway_cancellation.py
tests/llm/test_model_gateway_privacy.py
tests/llm/test_model_gateway_timeout_retry.py
tests/llm/test_model_gateway_fallback.py
tests/llm/test_model_gateway_accounting.py
tests/llm/test_model_gateway_evidence.py
tests/llm/test_phase11_21_dp121_acceptance.py
tests/llm/model_gateway_support.py
tests/platform/test_model_gateway_binding.py
tests/agent_runtime/test_model_egress_privacy_adapter.py
tests/agent_runtime/test_model_fallback_gateway_adapter.py
tests/agent_runtime/test_model_execution_evidence_projection.py
```

Independent audit is pending; this phase is not closed and no closure claim is
made here.
