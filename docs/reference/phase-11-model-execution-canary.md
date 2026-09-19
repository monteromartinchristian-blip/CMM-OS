# Phase 11 — canonical model execution seam (CMMChat Wave E0) reference

This document records the CMMChat Wave E0 deliverable inside CMM OS: the minimum
canonical real-model execution path, its ownership boundary, its reuse of the
existing authorities, the frozen closed-phase adjustments it required and the
observed live canary evidence.

## 1. Purpose and ownership boundary

Before E0, CMM OS had a closed conversational pipeline
(`ConversationService → ApplicationGateway → RequestApplicationService →
Orchestrator`) that stopped at route selection, and it had the canonical model
machinery (`ModelRouter`, `ProviderRegistry`, `ProviderFactory`, `LLMProvider`,
`OpenAICompatibleProvider`) — but nothing connected the two. No canonical owner
existed for "execute the model inference the orchestrator's decision implies":

| Layer | Why it could not own model execution |
| --- | --- |
| `cmm.orchestration` | frozen module set; may not import `kernel.llm`; deliberately stops at route selection |
| `cmm.application` | may not name provider/model routing (composition root may bind only `ProviderRegistry`) |
| `cmm.conversation` | may not import `kernel.llm`; owner-name screened |
| `cmm.runtime`, `cmm.execution`, `cmm.platform`, `kernel`, … | may not import `cmm.orchestration` |

E0 therefore adds one small **composition/execution glue** package,
`cmm/model_execution/`, which owns no authority: it consumes the canonical
decision, delegates selection to the canonical router, construction to the
canonical factory and generation to the canonical provider. It defines no
orchestrator, provider registry, model router, model gateway, model catalog,
provider abstraction, session owner, conversation store or usage owner.

## 2. Public surface

```text
cmm/model_execution/
├── __init__.py      public exports only
├── contracts.py     ModelExecutionParameters / Request / Result / Failure / Status / ErrorCode
├── errors.py        ModelExecutionError (internal fail-closed defect carrier)
├── executor.py      CanonicalModelExecutor — the seam
├── composition.py   CMMChat Router provider registration + seam builders
├── turn.py          execute_conversational_turn — canonical turn sequencing
└── canary.py        python -m cmm.model_execution.canary — the live canary
```

### Input contract

`ModelExecutionRequest(request_id, decision_id, route, prompt, requirements,
parameters)`, built from the canonical artifact with
`ModelExecutionRequest.from_decision(record, *, prompt, requirements=None,
parameters=None)`:

- `request_id` / `decision_id` / `route` are copied from the canonical
  `OrchestrationDecisionRecord` the Phase 11.2 pipeline persisted;
- `prompt` is the conversational text of the turn;
- `requirements` is the canonical `kernel.llm.model_selection.ModelRequirements`;
- `parameters` is `ModelExecutionParameters(temperature, max_tokens)` — the only
  generation parameters the canonical LLM contracts already understand.

The mapping is total and faithful: a non-executable route is copied unchanged and
refused by the executor, never silently re-classified.

### Output contract

`ModelExecutionResult` is either:

- `status=SUCCEEDED` with `text` (the normalized assistant text), the resolved
  `provider_id` and `model_id`, the canonical `routing_decision_id`, token usage
  and `finish_reason`; or
- `status=FAILED` with one `ModelExecutionFailure(code, message, retryable,
  details)` whose `message` is an application-owned constant and whose `details`
  carry safe identifiers only.

Closed failure vocabulary: `ROUTE_NOT_EXECUTABLE`, `MODEL_UNAVAILABLE`,
`PROVIDER_UNAVAILABLE`, `PROVIDER_FAILURE`, `PROVIDER_RESPONSE_INVALID`. No
provider text, response body, credential, path or traceback can reach a result;
only the canonical `direct_response` route may reach a model at all.

### Turn sequencing

`execute_conversational_turn(conversation=…, decisions=…, executor=…, turn=…)`
runs the frozen order: canonical conversational submit (exactly once) → resolve
the canonical decision by canonical request identity → execute the seam. The
canonical transcript commit is preserved whatever the model outcome is; a missing
canonical decision fails closed with `ModelExecutionError`.

## 3. Reuse map — no parallel authority

| Canonical authority | How E0 uses it | What is *not* created |
| --- | --- | --- |
| `ConversationService` | the turn is submitted through it | no second conversation service or store |
| `ApplicationGateway` | reached through `ConversationService` only | no second gateway or entrypoint |
| `RequestApplicationService` / `Orchestrator` | produce the decision the seam consumes | no second orchestrator, no routing policy |
| `ModelRouter` | `decide(requirements)` selects the model | no second router, ranking or selection rule |
| `ProviderRegistry` | the **Phase 11.1-bound instance** (`provider.registry`) receives the router provider | no second registry instance or class |
| `ModelCatalog` | bound to that same registry instance | no second catalog abstraction |
| `ProviderFactory` | materializes the provider from the decision | no provider construction in the seam |
| `LLMProvider` / `OpenAICompatibleProvider` | performs the inference | no new provider protocol or adapter |
| `OpenAICompatibleClient` | the only transport to the router | no HTTP client, socket or `openai` import in the package |

`ModelRouter`, `ProviderFactory`, `ProviderRegistry`, `ModelCatalog`,
`LLMProvider`, `ConversationService`, `OrchestrationDecisionRepository` and
`OrchestrationDecisionRecord` are imported **by identity** — the architecture gate
asserts `cmm.model_execution.composition.ModelRouter is
kernel.llm.model_router.ModelRouter`, and likewise for every other authority.

## 4. Router boundary

- **Endpoint:** `http://127.0.0.1:8790/v1` (the CMMChat Router's documented
  loopback OpenAI-compatible root), registered as the canonical
  `ProviderSpec(id="cmmchat-router", provider_type="local", api_style=
  "chat_completions", api_key_env="CMM_ROUTER_TOKEN")`.
- **Contract consumed unchanged:** `POST /v1/chat/completions` with
  `Authorization: Bearer <CMM_ROUTER_TOKEN>` and
  `{"model": "<provider>/<model>", "messages": […], "temperature": …}`; model
  identities are the router's own namespaced ids, discoverable through
  `GET /v1/models` (13 identities advertised at the observed baseline:
  `chatgpt/chatgpt-web/{light,medium,high,extra-high}`, `chatgpt/gpt-5.5`,
  `chatgpt/gpt-5.6-{sol,terra,luna}`, `chatgpt/gpt-daybreak-blue-latest`,
  `claude/{default,sonnet,haiku,opus[1m]}`).
- **CMM Routers code changed: NO** (`CMM_ROUTERS_CHANGES=NONE`). The local
  router was built (`npm install && npm run build`) and run with its documented
  environment bearer mechanism; only gitignored local runtime state
  (`config/shared.json`, `dist/`, `node_modules/`) was created.
- **Loopback only:** the router binds `127.0.0.1:8790` and the seam *refuses at
  composition time* any non-loopback endpoint, so no LAN exposure can be
  introduced by configuration. Nothing in this seam reaches a routable
  interface.
- **Credentials:** the bearer is read only through the canonical
  `ProviderSpec.resolve_api_key()` mechanism from `CMM_ROUTER_TOKEN`. No secret
  value appears in code, tests, documentation, reports or commits; the gate
  rejects a credential-shaped literal anywhere in the package.
- **Model identity configuration:** `--model`, then `CMM_ROUTER_MODEL`, then the
  router's own `/v1/models` advertisement — all through existing mechanisms. No
  configuration subsystem was invented.

## 5. Architecture gate

`tests/model_execution/test_architecture.py` (95 tests) enforces over the real
package:

- **frozen module set** — exactly the seven modules above;
- **exact owner vocabulary** — the defined class set is exactly the twelve E0
  value/consumer classes; no class may be or end with a canonical owner name, and
  no class may be owner-shaped (`…Router`, `…Registry`, `…Catalog`, `…Gateway`,
  `…Store`, `…Repository`, `…Engine`, `…Runtime`, `…Manager`, `…Planner`,
  `…Bus`, `…Broker`, `…Pool`, `…Scheduler`, `…Client`, `…Adapter`,
  `…Provider`, `…Protocol`);
- **exact import allowlists** — internal roots are exactly
  `cmm.application`, `cmm.conversation`, `cmm.model_execution`,
  `cmm.orchestration`, `kernel.llm`; external roots are an exact frozen set;
  `urllib.parse` is the only permitted `urllib` member; the transport
  (`cmm.api`), the composition core (`cmm.platform`), every HTTP/socket/storage
  root, dynamic import machinery, `eval`/`exec` and file I/O are forbidden;
- **no import-time side effect and no module-level singleton**;
- **canonical reuse by identity** and **delegation instead of duplication** —
  the executor must call `self._model_router.decide(...)`,
  `self._provider_factory.create_from_decision(...)` and `provider.generate(...)`
  and must not name a ranking policy, a selection helper, `ProviderSpec(`,
  `ModelSpec(` or `OpenAICompatibleClient(` itself;
- **reverse-dependency closure** — with liveness anchors for each layer, no
  module under `cmm/{agent_runtime,api,application,cognitive,conversation,domains,
  execution,memory,orchestration,platform,planner,runtime,validation,workflows}`
  or `kernel` imports `cmm.model_execution`;
- **secret hygiene** — no credential-shaped literal and no bearer read outside
  the canonical mechanism.

## 6. Closed-phase adjustment (this task, additive)

`tests/application/test_architecture.py` is a closed Phase 11.3 gate whose closing
scan asserts that only the backend packages, the conversation package and the
sanctioned CLI adapter import `cmm.application`. E0's canary drives the canonical
Phase 11.4 local runtime composition, so `cmm.model_execution` genuinely is a
fourth sanctioned consumer of the application boundary. The change is exactly the
Phase 11.5 (DP-105) pattern:

- a subtree skip for `cmm/model_execution` in
  `test_only_the_backend_packages_and_the_cli_adapter_import_the_backend`;
- a paired honesty/liveness assertion,
  `test_the_model_execution_package_exemption_is_live_and_honest`, proving the
  package exists, really imports `cmm.application` and never imports `cmm.api`.

No assertion, threshold or rule was weakened, and no other closed-phase test was
touched. The seam's own gate (`tests/model_execution/test_architecture.py`)
independently keeps the package from importing `cmm.api` or `cmm.platform`, so
the exemption is bounded twice.

## 7. Observed evidence

Test commands (worktree `/Users/christian/CMM OS/.worktrees/wave-e0-real-model-canary`,
interpreter `/Users/christian/CMM OS/.venv/bin/python`, CPython 3.14.7):

```text
python -m pytest tests/model_execution -q                     → 200 passed
python -m pytest tests -q                                     → 21505 passed, 2 warnings in 496.20s (0:08:16), 0 failed
ruff check cmm/model_execution tests/model_execution tests/application/test_architecture.py → All checks passed
ruff format --check …                                          → 15 files already formatted
```

Live canary (`python -m cmm.model_execution.canary --model
chatgpt/chatgpt-web/medium`, real router on `127.0.0.1:8790`, real subscription
model, two consecutive runs):

```text
CANARY_REQUESTED_MODEL=chatgpt/chatgpt-web/medium
CANARY_RESOLVED_MODEL=chatgpt/chatgpt-web/medium
CANARY_ROUTER_ENDPOINT=http://127.0.0.1:8790/v1
CANARY_RESPONSE=CMM\_OS\_ROUTER\_CANARY\_OK
CANARY_ELAPSED_MS=18791 / 19823
CANARY_RESULT=PASS
CMM_OS_ACCEPTED_REQUEST=wave-e0-canary-request-<uuid>
CANONICAL_SESSION=wave-e0-canary-<uuid>
ORCHESTRATOR_PATH_REACHED=orchestration-decision:<request-id>|route=direct_response|intent=question
EXECUTION_SEAM_REACHED=CanonicalModelExecutor
MODEL_ROUTER_SELECTION=routing-<uuid>|provider=cmmchat-router|model=chatgpt/chatgpt-web/medium
PROVIDER_MATERIALIZED=cmmchat-router|model=chatgpt/chatgpt-web/medium
ROUTER_REQUEST_SENT=http://127.0.0.1:8790/v1
ROUTER_RESPONSE_RECEIVED=finish_reason=stop|tokens=18670 / 18673
NORMALIZED_ASSISTANT_RESULT=succeeded|chars=27
COMPOSED_ROUTER_MODELS=chatgpt/chatgpt-web/medium
```

The model answered `CMM\_OS\_ROUTER\_CANARY\_OK` (Markdown-escaped underscores, a
property of the model's own formatting, not of the seam) through the canonical
path; the canonical decision was persisted and resolved by canonical request
identity; the transcript was committed through the canonical session store.

## 8. Not implemented (explicitly deferred, not E0 failures)

CMMChat changes, CMM Hub integration, `fake_model` replacement, CMM Auto, full
model catalog, model selector UX, token streaming, SSE redesign, hard
cancellation, retry/fork real inference, Project/attachment/artifact
intelligence, Web Search, Computer Use, Skills, MCP, plugins, CMM Usage, Cowork,
CMM Bots, remote node transport, LAN exposure, iPhone, Web.

<!-- WAVE_E0_HERMETIC_FINAL_VERIFICATION -->

### Final hermetic verification — 2026-09-19

The earlier non-hermetic full-tree runs that reported 36/33 failures were environment-invalid for closure purposes: the test environment had validation tooling installed but did not have the `cmm-os` project itself installed as a distribution for subprocess/fresh-import tests. They are superseded by the isolated verification below.

Measured final evidence on exact E0 HEAD `1cab7f622629ed9acacb76c1c8dc0c0db8206772`:

- isolated E0 environment: `cmm-os[dev]` installed from the E0 worktree;
- isolated baseline environment: `cmm-os[dev]` installed from baseline `5beea9d0c32a10732a027f1c368281ddd727d89c`;
- package metadata / fresh import sanity: PASS in both environments;
- `tests/validation`: `533 passed` on E0;
- baseline `tests/validation`: `533 passed`;
- full E0 tree: `21505 passed, 2 warnings in 496.20s (0:08:16)`;
- E0 full-tree failures: `0`;
- E0 worktree remained clean after verification;
- `PUSH=NO`;
- `MERGE=NO`.

Closure gates:

```text
E0_VALIDATION=PASS
FULL_TREE=PASS
E0_INTRODUCED_FULL_TREE_FAILURES=0
REAL_MODEL_EXECUTION=PASS
REAL_CANARY=PASS
CMM_ROUTERS_CHANGED=NO
CMMCHAT_ROUTER_LOOPBACK_ONLY=PASS
```
