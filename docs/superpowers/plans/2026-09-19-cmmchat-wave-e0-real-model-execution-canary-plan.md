# CMMChat Wave E0 — CMM OS Real Model Execution Canary (Implementation Plan)

**Status:** approved by the current task (the E0 brief is the specification; see
"Spec" below). **Deliverable:** one canonical real-model execution seam inside CMM
OS, its deterministic test suite, and one real inference proven through the live
CMMChat Router on `127.0.0.1:8790`.

**Goal:** prove the minimum canonical real-model execution path inside CMM OS —
`ConversationService → ApplicationGateway → RequestApplicationService →
Orchestrator → canonical execution seam → ModelRouter / ProviderFactory /
LLMProvider → OpenAICompatibleProvider → CMMChat Router → real model → normalized
CMM OS result` — without introducing a parallel orchestrator, provider registry,
model gateway, session owner, conversation store, model catalog or provider
abstraction, and without changing any closed Phase 11.1/11.2/11.3/11.4/11.5
semantics.

**Architecture:** the seam is a new, small composition/execution glue package
`cmm/model_execution/`. It owns no routing policy, no catalog, no provider
instance and no state: it consumes the canonical `OrchestrationDecisionRecord`
produced by the Phase 11.2 pipeline, delegates model selection to the canonical
`kernel.llm.model_router.ModelRouter`, delegates provider construction to the
canonical `kernel.llm.provider_factory.ProviderFactory`, and executes through the
canonical `LLMProvider` / `OpenAICompatibleProvider`. The canonical
`ProviderRegistry` instance already bound by the Phase 11.1 composition is the
one registry the seam registers the CMMChat Router provider into; the canonical
`ModelCatalog` is bound to that same instance.

**Tech Stack:** Python 3.10+ (this worktree was verified with CPython 3.11.16),
frozen/slotted dataclasses, existing `kernel.llm` provider/model contracts,
existing `cmm.orchestration`, `cmm.application`, `cmm.conversation`,
`cmm.runtime.sessions` and the `openai` SDK only through the existing
`kernel.llm.clients.openai_compatible_client.OpenAICompatibleClient`, pytest,
Ruff.

**Spec:** the E0 brief ("Implement CMMChat Wave E0 — CMM OS Real Model Execution
Canary"), plus `docs/reference/phase-11-orchestration-layer.md`,
`docs/reference/phase-11-application-backend.md`,
`docs/reference/phase-11-conversational-interface.md` and
`docs/roadmap/phase-11-stable-integrated-platform.md` as the closed-phase
contracts that stay frozen.

**Implementation baseline:** worktree
`/Users/christian/CMM OS/.worktrees/wave-e0-real-model-canary`, branch
`feature/cmmchat-wave-e0-real-model-canary`, `START_HEAD`
`5beea9d0c32a10732a027f1c368281ddd727d89c`, `git-common-dir`
`/Users/christian/CMM OS/.git`, Dev Registry `WRITE_ALLOWED=YES`
(`CANONICAL_MACHINE`).

## Global constraints

- `NO_PARALLEL_AUTHORITY=YES`: no second orchestrator, provider registry, model
  router, model gateway, session owner, conversation store, model catalog or
  provider abstraction.
- Do not modify `cmm.orchestration`, `cmm.application`, `cmm.conversation`,
  `cmm.platform`, `cmm.runtime`, `kernel.llm` production code or any closed-phase
  test.
- Do not turn the Orchestrator into an HTTP/model client and do not make
  `ConversationService` call the router directly.
- The Router stays a `CHAT_ONLY`, loopback-only consumer; no LAN exposure, no
  remote networking.
- `CMM_ROUTERS_MODIFICATION=FORBIDDEN` by default; the preferred result is
  `CMM_ROUTERS_CHANGES=NONE`.
- No secret value may be printed, committed, copied into tests or documentation.
  The router bearer is resolved from the environment variable named by the
  canonical `ProviderSpec.api_key_env` (`CMM_ROUTER_TOKEN`).
- TDD: RED → GREEN → REFACTOR per behavior; deterministic tests never require
  live inference.
- `NO PUSH`, `NO MERGE`, no rewrite of `main`, no unrelated staging.

---

## Phase 1 — read-only trace (live baseline answers)

1. **Where `MESSAGE_SUBMIT` enters `ApplicationGateway`.**
   `cmm/application/gateway.py:228 ApplicationGateway.handle` → `_dispatch`
   (`:275`) → `_dispatch_once` (`:316`); the `MESSAGE_SUBMIT` branch at
   `:353` calls `RequestApplicationService.submit_message`.
2. **The application service method that invokes the Orchestrator.**
   `cmm/application/requests.py:187 RequestApplicationService.submit_message` →
   `_orchestrate` (`:221`) → `self._orchestrator.orchestrate(...)` (`:258`).
3. **What the Orchestrator returns for a plain conversational turn.**
   An `OrchestrationResult` with `status=ROUTED`, `intent=QUESTION` (the
   conversation channel adds the canonical `question` signal at
   `requests.py:246`), `route=ExecutionRoute.DIRECT_RESPONSE`
   (`cmm/orchestration/agent_router.py:45`) and `decision_id=
   orchestration-decision:<request_id>`; the same facts are persisted as an
   `OrchestrationDecisionRecord`. **No assistant text and no model call**: Phase
   11.2 stops at route selection (`orchestrator.py:10-13`,
   `contracts.py:227-229`).
4. **Which existing object owns downstream model execution after the decision.**
   None. `cmm.orchestration` may not import `kernel.llm` and its module set is
   frozen (`tests/orchestration/test_architecture.py:215,294`);
   `cmm.application` may not name provider/model routing
   (`tests/application/test_architecture.py:272-286,643-659`);
   `cmm.conversation` may not import `kernel.llm` and is owner-name screened
   (`docs/reference/phase-11-conversational-interface.md` §13);
   `cmm/{execution,runtime,platform,domains,…}` and `kernel` may not import
   `cmm.orchestration` (`tests/orchestration/test_architecture.py:238`). The E0
   answer: a new small package that only *consumes* the canonical decision and
   *delegates* to the canonical provider machinery, with no reverse edge from any
   frozen layer.
5. **Exact public signatures reused.**
   - `ModelRouter(*, provider_registry, model_catalog)`.
     `decide(requirements, *, ranking_policy=None, configuration_version="1",
     metadata=None) -> RoutingDecision`.
   - `ProviderFactory.create(*, provider, model, client=None) -> LLMProvider`;
     `create_from_decision(decision, *, provider_registry, model_catalog,
     client=None) -> LLMProvider`.
   - `LLMProvider.generate(request: LLMRequest) -> LLMResponse` (ABC).
   - `OpenAICompatibleProvider(*, provider_id, client, model).generate(request)`.
   - `OpenAICompatibleClient(*, client=None, api_key=None, base_url=None)`
     `.generate(*, model, system, prompt, temperature=0.0, max_tokens=None) ->
     (content, prompt_tokens, completion_tokens, finish_reason)` and
     `.list_models() -> tuple[str, ...]`.
   - `ProviderSpec(id, provider_type, api_style, api_key_env, base_url,
     base_url_env, …).resolve_api_key() / .resolve_base_url()`.
   - `ModelSpec(id, provider_id, context_window, capabilities, …).qualified_id`.
6. **How providers are registered/discovered today.** Explicit bootstraps over
   the instance-based `ProviderRegistry` + `ModelCatalog`
   (`kernel/llm/first_wave_providers.py`,
   `kernel/llm/experimental_omniroute.py:17`), discovery through
   `kernel/llm/model_discovery.py:137 discover_models(...)` over a
   `list_models()` client; the Phase 11.1 composition binds the one canonical
   registry as `provider.registry`
   (`cmm/platform/canonical.py:260`, `cmm/application/local_runtime.py:314`).
7. **Does an existing composition module have enough authority?**
   `cmm/application/local_runtime.py:339 build_local_application_runtime()`
   composes the canonical orchestration/application graph and exposes the
   container, the one gateway, the canonical orchestrator and the shared session
   store, and `container.get_service("provider.registry")` resolves the
   canonical provider registry instance. It therefore *hosts* the reuse, but it
   must not own model execution (application gates), so it is not the seam.
8. **Smallest new seam that fits the layer rules.** A new package
   `cmm/model_execution/` (contracts + executor + composition + turn driver +
   canary entry) that imports only `cmm.orchestration`, `cmm.conversation`,
   `cmm.application` and `kernel.llm`.
9. **The exact OpenAI-compatible request the CMMChat Router expects.**
   `POST http://127.0.0.1:8790/v1/chat/completions` with
   `Authorization: Bearer <bearerSecretEnv>` and body
   `{"model": "<provider>/<model>", "messages": [{"role","content"}],
   "temperature": …, "max_tokens": …?}`; `GET /v1/models` lists the namespaced
   ids (`chatgpt/…`, `claude/…`); `/v1/*` requires the bearer (401 otherwise);
   the listener is `127.0.0.1` only.
10. **Can the existing `OpenAICompatibleProvider` target `http://127.0.0.1:8790/v1`
    without modifying CMM Routers?** Yes — verified live in Phase 1: the router
    was built and started locally (`npm install && npm run build`, gitignored
    `config/shared.json`, bearer from the environment) and a raw
    `/v1/chat/completions` probe returned a real completion from
    `chatgpt/chatgpt-web/medium` (`CANARY_ROUTERS_CHANGES=NONE`).

---

## 2. Locked file map

New production package:

```text
cmm/model_execution/
├── __init__.py          # public surface (exports only)
├── contracts.py         # ModelExecutionRequest / Result / Failure / Parameters
├── errors.py            # ModelExecutionError (internal, safe message)
├── executor.py          # CanonicalModelExecutor — the seam
├── composition.py       # CMMChat Router provider registration + seam builders
├── turn.py              # canonical turn sequencing (conversation → decision → seam)
└── canary.py            # `python -m cmm.model_execution.canary` live entry
```

New tests:

```text
tests/model_execution/
├── __init__.py
├── test_contracts.py
├── test_executor.py
├── test_composition.py
├── test_turn.py
├── test_canary.py
└── test_architecture.py
```

New documentation:

```text
docs/reference/phase-11-model-execution-canary.md   # seam + canary reference
docs/superpowers/plans/2026-09-19-cmmchat-wave-e0-real-model-execution-canary-plan.md
```

No existing production file is modified. No closed-phase test is modified.

## 3. Contracts (locked)

- `ModelExecutionParameters(temperature: float = 0.0, max_tokens: int | None =
  None)` — normalized generation parameters only; rejects out-of-range values at
  construction.
- `ModelExecutionRequest(request_id, decision_id, route: ExecutionRoute, prompt,
  requirements: ModelRequirements = ModelRequirements(), parameters =
  ModelExecutionParameters())`; `from_decision(record, *, prompt, requirements,
  parameters)` is the only mapping from canonical facts.
- `ModelExecutionStatus` = `SUCCEEDED | FAILED`.
- `ModelExecutionErrorCode` = `INVALID_REQUEST | ROUTE_NOT_EXECUTABLE |
  MODEL_UNAVAILABLE | PROVIDER_UNAVAILABLE | PROVIDER_FAILURE |
  PROVIDER_RESPONSE_INVALID`.
- `ModelExecutionFailure(code, message, retryable, details)` — application-owned
  safe constants only; no provider text, no secret, no path.
- `ModelExecutionResult(status, request_id, decision_id, text, provider_id,
  model_id, routing_decision_id, usage_prompt_tokens, usage_completion_tokens,
  finish_reason, error)` with `succeeded`/`failed` constructors.
- `ModelExecutionError(RuntimeError)` — internal fail-closed defect carrier for a
  missing canonical decision; never carries internal detail.

## 4. Reuse map (no parallel authority)

| Canonical authority | How the seam uses it | Not duplicated because |
| --- | --- | --- |
| `ConversationService` | the turn driver submits the user turn through it | the seam defines no conversation service, store or transcript |
| `ApplicationGateway` | reached only through `ConversationService` | the seam never handles a request itself |
| `RequestApplicationService` / `Orchestrator` | produce the canonical decision the seam consumes | the seam makes no routing decision and holds no policy |
| `kernel.llm.model_router.ModelRouter` | `decide(requirements)` selects the model | the seam defines no router, no ranking policy, no catalog |
| `kernel.llm.provider_registry.ProviderRegistry` | the Phase 11.1-bound canonical instance receives the router provider | no second registry class or instance is created |
| `kernel.llm.model_catalog.ModelCatalog` | bound to that same registry instance | no second catalog abstraction |
| `kernel.llm.provider_factory.ProviderFactory` | materializes the provider | the seam constructs no client and reads no credential itself |
| `LLMProvider` / `OpenAICompatibleProvider` | executes the inference | no new provider protocol or adapter |
| `OpenAICompatibleClient` | the only transport to `127.0.0.1:8790/v1` | no HTTP client, no socket, no `openai` import in the package |

## 5. Tasks

- **Task 1 — contracts.** RED: `tests/model_execution/test_contracts.py` pins the
  parameter/request/result/failure contracts, `from_decision` mapping and
  fail-closed validation. GREEN: `contracts.py`, `errors.py`, `__init__.py`.
- **Task 2 — executor.** RED: `tests/model_execution/test_executor.py` proves the
  seam receives the intended canonical request, reuses `ModelRouter`,
  `ProviderFactory`, `ProviderRegistry`, `ModelCatalog` and `LLMProvider` (exact
  identity checks), maps the request to `LLMRequest` and the `LLMResponse` back
  to a normalized result, and fails closed (closed) with a normalized, safe
  failure for a non-executable route, no matching model, an unavailable
  provider, a transport failure, a malformed provider response and a secret that
  must never surface. GREEN: `executor.py`.
- **Task 3 — composition.** RED: `tests/model_execution/test_composition.py`
  pins the router `ProviderSpec` (loopback base URL, `chat_completions`,
  `api_key_env=CMM_ROUTER_TOKEN`, `provider_type=local`, canonical
  `base_url_env` override), the model registration over the canonical catalog,
  the discovery client contract, and that the composition reuses the
  Phase 11.1-bound registry *instance* and re-registration is rejected. GREEN:
  `composition.py`.
- **Task 4 — turn driver.** RED: `tests/model_execution/test_turn.py` drives one
  real canonical runtime (`build_local_application_runtime`) plus the real
  `ConversationService` with a recording seam double, proving the canonical path
  is entered once, the canonical decision is resolved by the canonical request
  identity, the seam receives the mapped request and the transcript commit is
  preserved; a missing decision fails closed. GREEN: `turn.py`.
- **Task 5 — canary entry.** RED: `tests/model_execution/test_canary.py` pins the
  evidence report format and the safe failure path (unreachable router → `FAIL`,
  no secret, non-zero exit). GREEN: `canary.py`.
- **Task 6 — architecture gate.** RED→GREEN:
  `tests/model_execution/test_architecture.py` freezes the package's module set,
  its internal/external import allowlists, forbids an HTTP/model-gateway/provider
  owner, forbids dynamic import and file/socket I/O, and proves no frozen layer
  imports `cmm.model_execution`.
- **Task 7 — documentation.** `docs/reference/phase-11-model-execution-canary.md`.
- **Task 8 — regression + real canary.** Full relevant suite green; one real
  inference through the live router.

## 6. Live canary procedure

1. `CMM-Routers`: `npm install && npm run build`; gitignored
   `config/shared.json` with the locally authenticated providers enabled and the
   unavailable ones disabled; bearer exported as `CMM_ROUTER_TOKEN` (never
   printed). No source change: `CMM_ROUTERS_CHANGES=NONE`.
2. `CMM_ROUTER_TOKEN=… /Users/christian/CMM OS/.venv/bin/python -m
   cmm.model_execution.canary --model chatgpt/chatgpt-web/medium`, which runs one
   real turn through the composed canonical runtime and prints the required
   evidence lines (`CANARY_REQUESTED_MODEL`, `CANARY_RESOLVED_MODEL`,
   `CANARY_ROUTER_ENDPOINT`, `CANARY_RESPONSE`, `CANARY_ELAPSED_MS`,
   `CANARY_RESULT`).
3. Evidence is recorded in the reference document; no secret value is recorded.

## 7. Closed-phase adjustment required by this plan (recorded, additive)

`tests/application/test_architecture.py` (closed Phase 11.3) enumerates the
sanctioned consumers of `cmm.application`.  E0's canary drives the canonical
Phase 11.4 composition (`build_local_application_runtime`), so
`cmm.model_execution` is a genuine fourth consumer.  The plan therefore includes
one additive change to that closed-phase gate — a subtree skip for
`cmm/model_execution` plus the paired honesty/liveness assertion
`test_the_model_execution_package_exemption_is_live_and_honest` — exactly the
Phase 11.5 (DP-105) pattern recorded in
`docs/reference/phase-11-conversational-interface.md` §14.1.  No assertion,
threshold or rule is weakened, and no other closed-phase test is touched.

## 8. Completion gates (from the E0 brief)

`CMM_OS_START_HEAD`, `CANONICAL_REPO`, `DEV_REGISTRY_AUTHORITY`, `NEW_WORKTREE`,
`CONVERSATION_SERVICE_REUSED`, `APPLICATION_GATEWAY_REUSED`,
`ORCHESTRATOR_REUSED`, `MODEL_ROUTER_REUSED`, `PROVIDER_REGISTRY_REUSED`,
`PROVIDER_FACTORY_REUSED`, `LLM_PROVIDER_REUSED`, `PARALLEL_*` all `NO`,
`CMMCHAT_ROUTER_ENDPOINT=127.0.0.1:8790`, `CMMCHAT_ROUTER_LOOPBACK_ONLY=PASS`,
`CMM_ROUTERS_CHANGED=NO`, `REAL_MODEL_EXECUTION=PASS`, `REAL_CANARY=PASS`,
`PHASE_11_5_REGRESSION`, `ORCHESTRATION_REGRESSION`, `LLM_REGRESSION`,
`FULL_RELEVANT_TESTS` all `PASS`, `SECRETS_COMMITTED=NO`, `PUSH=NO`, `MERGE=NO`.

## 8. Explicitly deferred (not E0 failures)

CMMChat changes, CMM Hub integration, `fake_model` replacement, CMM Auto, the
full model catalog, model selector UX, token streaming, SSE redesign, hard
cancellation, retry/fork real inference, Project/attachment/artifact
intelligence, Web Search, Computer Use, Skills, MCP, plugins, CMM Usage, Cowork,
CMM Bots, remote node transport, LAN exposure, iPhone, Web.
