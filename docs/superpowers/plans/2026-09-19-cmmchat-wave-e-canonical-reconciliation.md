# CMMChat Wave E — Canonical Reconciliation Plan

Date: 2026-09-19
Branch: `feature/cmmchat-wave-e-real-intelligence` (descends from E0 `0c99e1a`)
Method: PORT SEMANTICS, NOT FILES. No redesign of CMMChat or CMM OS. Wave E is not restarted.

## 0. Paths and HEADs (live-confirmed)

- Canonical CMM OS: `/Users/christian/CMM OS`, baseline branch
  `feature/phase-11-stable-integrated-platform` @ `5beea9d`.
- E0 worktree (preserved, not deleted): `…/CMM OS/.worktrees/wave-e0-real-model-canary`,
  final docs-only HEAD `E0_FINAL_HEAD=0c99e1a15a60ba51a3318b95dd39e30b556c75ed`.
- Wave E canonical worktree (this branch):
  `/Users/christian/CMM OS/.worktrees/cmmchat-wave-e-real-intelligence`,
  created from `E0_FINAL_HEAD`; `DESCENDS_FROM_E0=YES`.
- Obsolete clone (inspect-only): `/Users/christian/CMM-OS` @ `c2c8c40`, branch
  `feature/phase-10-domain-intelligence`. Never a working repository again.
- CMMChat: `/Users/christian/CMMChat` `feature/qwen-visual-v0` @ `15a84cc`
  (modify only to correct an integration defect or to repoint the OS source root).
- Backups (do not delete/overwrite): `~/Library/Mobile Documents/com~apple~CloudDocs/Downloads/Temporales/cmm-old-clone-safety-20260919-045022/`
  (old-head/old-index/old-working-tree patches + audit report), and
  `~/cmmchat-waveE-evidence/cmm-os-gateway-discovery.patch`.

## 1. Canonical architecture discovered (live inspection)

| Canonical owner | Module | Owns |
|---|---|---|
| Model execution seam | `cmm/model_execution/executor.py` `CanonicalModelExecutor` | Maps one request → `LLMRequest`, invokes provider once, normalizes result. No state. |
| Composition / CMMChat Router | `cmm/model_execution/composition.py` | Registers loopback OpenAI-compatible Router (`127.0.0.1:8790/v1`) as a canonical `ProviderSpec`; discovers ids via `list_models()`. |
| Turn sequencing | `cmm/model_execution/turn.py` | conversation → canonical decision → seam. Non-streaming. |
| Live canary | `cmm/model_execution/canary.py` | Real inference through the whole canonical path; `REAL_CANARY=PASS` at E0. |
| Model routing (AUTO) | `kernel.llm/model_router.py` `ModelRouter.decide(ModelRequirements)` | Auditable `RoutingDecision`. |
| Model selection | `kernel.llm/model_selection.py` | `select_model`, `find_matching_models`, availability/capability/privacy/cost filters. |
| Model catalog | `kernel.llm/model_catalog.py` | `ModelSpec` (id, provider_id, context_window, capabilities, aliases, availability). `get()` already resolves by id / `provider:id` / alias, case-normalized. |
| Provider registry | `kernel.llm/provider_registry.py` | `ProviderSpec` (provider_type local/remote, api_style, availability, capabilities). |
| Provider factory | `kernel.llm/provider_factory.py` | Materializes a provider from a routing decision. |
| Providers | `kernel/llm/openai_compatible_provider.py`, `ollama_provider.py`, `provider.py` | **`generate()` only.** No `stream()`, no cancel, no history. |
| Discovery | `kernel/llm/model_discovery.py` `discover_models` | Provider-connection/route discovery (canonical). |
| SSE delivery | `cmm/api/streaming.py` | Projects an already-computed response into SSE frames. **Explicitly NOT a provider token stream / inference runtime.** |

Conclusion: canonical owns catalog, routing/AUTO, selection, provider materialization,
and SSE delivery. Canonical owns **no** provider token streaming, cancellation, or
multi-turn history. Those are the only genuine gaps.

## 2. Obsolete Wave E surface (commit c2c8c40 + staged + unstaged)

- `kernel/llm/gateway.py` — `ModelGateway` facade owning its own registry/catalog/router/
  factory, Ollama `/api/tags` local-runtime discovery, remote-pointer classification,
  normalized catalog/resolution, `generate_stream` dispatch.
- `kernel/llm/streaming.py` — `build_messages` (system+history+prompt),
  `stream_chat_completions` (openai SDK, cancel, history), `stream_ollama` (`/api/chat`,
  cancel, history), `stream_mock` (deterministic, cancel).
- `tests/llm/test_streaming_gateway.py` — 12 tests.

`PATCH_EQUIVALENT_CANON_COMMIT=NONE_FOUND` (audit §2). Do not re-derive.

## 3. Capability-by-capability classification (A–E)

Legend: **A** ALREADY_CANONICAL (discard), **B** USEFUL_SEMANTIC_DELTA (port into the
correct canonical module), **C** OBSOLETE_ARCHITECTURE (discard), **D** TEST_VALUE_ONLY
(adapt test to canonical namespace), **E** OUT_OF_SCOPE (discard).

| Obsolete capability / symbol | Class | Canonical target & rationale |
|---|---|---|
| Provider-independent token streaming `stream_chat_completions` | **B** | Port semantics into `OpenAICompatibleProvider.stream()` reusing the provider's own canonical client/base_url/api_key. This is the *first* canonical streaming execution owner for token deltas; `cmm/api/streaming.py` stays the SSE delivery adapter and is NOT replaced. |
| Multi-turn message construction `build_messages` | **B** | Port into a canonical seam helper (`cmm/model_execution/streaming.py`) and/or `LLMRequest.history`. Canonical `LLMRequest` today is single `prompt`+`system_prompt`; add a closed `history` field. |
| Cancellation propagation (cancel_event per delta) | **B** | Port into provider `stream(..., cancel_event)` and the seam stream generator. Canonical has none. |
| Normalized streaming deltas (yield content strings only) | **B** | Provider `stream()` yields plain text deltas; the seam/Hub normalizes into run events. No provider shape escapes. |
| Timeout / error handling in stream | **B (narrow)** | Reuse canonical `ModelExecutionErrorCode`/`ModelExecutionFailure`; provider stream raises canonical `ProviderError` (already exists). Do not invent new exception classes. |
| `stream_ollama` direct `/api/chat` | **E/C** | Ollama-direct is a *provider access* path that for CMMChat lives behind the CMMChat Router (§8), which canonical already integrates. CMMChat does not stream Ollama directly. |
| `stream_mock` | **D/A** | Canonical has `kernel/llm/mock_provider.py`; seam tests can use a scripted client (canonical canary `client` injection point). Port only test determinism, not a parallel mock streamer. |
| `ModelGateway` facade (owns registry/catalog/router/factory) | **C** | Recreating it is exactly the forbidden second gateway. Hub must compose the canonical seam (`build_local_model_execution`) + canonical catalog/router, never a `ModelGateway`. |
| `_register_default_providers`, `_register_local_runtime` (Ollama `/api/tags`) | **C/E** | Provider registration for CMMChat is canonical `composition.register_chat_only_router`. Direct Ollama discovery is the Router's job, below the seam. |
| `_fetch_local_runtime_models`, `LOCAL_BLOB_MINIMUM_BYTES`, remote-pointer honesty | **C (logic → Router) / D (test)** | Availability honesty stays as a concept; concretely the CMMChat Router advertises available ids. Preserve the AUTO-skip-unavailable *test* semantics against canonical availability filtering. |
| `NormalizedModel`/`ResolvedModel` dataclasses | **C→B** | Discard the facade types. The normalized catalog projection the Hub needs is derived from canonical `ModelSpec`+`ProviderSpec` inside the seam. |
| `_locality`/`_model_locality`/`_display_name`/`_capabilities` | **B (derive) / A (already there)** | `provider_type` gives locality; `ModelCapabilities` already carries reasoning/vision/tool_calling/structured_output. Display-name/id normalization (`_display_name`) is a small B helper if the Hub needs a friendly label; keep it out of Swift. |
| AUTO resolution `resolve(AUTO_POLICY)` | **A** | Canonical `ModelRouter.decide(ModelRequirements())` / `select_model`. AUTO is canonical policy, not gateway-owned. |
| Explicit model resolution | **A** | Canonical `ModelCatalog.get()` already resolves by id/qualified/alias, case-normalized, with an availability check. |
| `catalog()` listing | **A** | Canonical `ModelCatalog.list()` + `ProviderRegistry`; the Hub reads the catalog through the seam, not a gateway. |
| `_discover_availability` (`GET /models`) | **A/E** | Canonical discovery is `discover_chat_only_router_models` / `model_discovery.discover_models`. |
| 12 obsolete tests | **D** | Re-express each assertion against canonical modules (executor stream seam + providers), never against a `ModelGateway`. |

## 4. What will actually be ported (the semantic delta)

Canonical owns everything except a **provider token stream**. The reconciliation adds
exactly one streaming capability, in the right place, reusing all canonical authorities:

1. `kernel/llm/models.py` — add a closed `history: tuple[ChatTurn, ...]` (role+content)
   field to `LLMRequest` (default empty) so multi-turn survives the canonical contract;
   keep `frozen`/`slots`.
2. `kernel/llm/provider.py` — add `stream(self, request, *, cancel_event=None)` to the
   `LLMProvider` protocol (non-abstract default that raises `NotImplementedError`, so
   existing providers stay valid).
3. `kernel/llm/openai_compatible_provider.py` (+ compatible client) — implement
   `stream()` for `chat_completions` reusing the canonical client's base_url/api_key/model
   resolution and `build_messages`-equivalent transcript. Yields plain text deltas;
   honors `cancel_event`; raises canonical `ProviderError` on transport failure.
4. `cmm/model_execution/` — add a seam `stream()`/`execute_stream()` that: routes
   (AUTO via canonical `ModelRouter`) or resolves explicit selection (canonical
   `ModelCatalog.get`), materializes the provider via canonical `ProviderFactory`,
   builds the transcript, and yields normalized deltas + a terminal normalized result,
   propagating `cancel_event`. Extends the E0 seam; introduces NO second facade.
5. Discovery/AUTO/catalog/availability/capability/normalization: reuse canonical
   modules unchanged (Class A).

Explicitly NOT done: recreate `ModelGateway`; overwrite `cmm/application/gateway.py`
(ApplicationGateway); replace `cmm/api/streaming.py`; copy `kernel/llm/gateway.py` /
`streaming.py` wholesale; add a second router/registry/factory/catalog/session/stream
owner.

## 5. CMMChat Hub repoint (integration correctness)

`services/hub/src/cmm_hub/intelligence.py` today does
`sys.path.insert(...); from kernel.llm.gateway import ModelGateway` with default path
`Path.home()/"CMM-OS"` (the OBSOLETE clone). Reconciliation:

- Default OS source root → canonical `/Users/christian/CMM OS` (and the running canary
  points `CMM_OS_PATH` at the Wave E canonical worktree).
- Import the canonical seam (`cmm.model_execution`) and drive catalog/resolve/stream
  through it; drop the `kernel.llm.gateway.ModelGateway` dependency and the
  obsolete-exception-name mapping (`NoModelsAvailable`/`ModelUnavailable`/…) in favor of
  canonical `ModelExecutionResult`/`ProviderError`.
- Prove `OBSOLETE_CMM_OS_LOADED=NO` by asserting the loaded module file path resolves
  under the canonical worktree, never `/Users/christian/CMM-OS`.

This is a genuine integration defect (Hub currently defaults to the obsolete path), so
modifying CMMChat here is authorized.

## 6. Gate → evidence map

Each §21 gate is satisfied by a concrete command + recorded output (see HANDOFF). No
gate is claimed from code inspection. Real gates run against the canonical worktree with
`CMM_OS_PATH` set and the CMMChat Router live (real model), never a stub.

## 7. Deletion safety sequence (§16–§19)

1. Prove runtime references to `/Users/christian/CMM-OS` are 0 across CMMChat,
   canonical CMM OS, CMM-Routers (git remote name `CMM-OS.git` is not a runtime path).
2. Full git bundle of old clone (all refs) + `git bundle verify` + SHA-256; keep patch
   backups.
3. Quarantine: rename `CMM-OS` → `CMM-OS.OBSOLETE-WAVE-E-QUARANTINE`; rerun real canary
   + key integration; require `REAL_CANARY_WITH_OLD_PATH_ABSENT=PASS` and
   `CMMCHAT_REAL_CHAT_WITH_OLD_PATH_ABSENT=PASS`. If anything breaks: STOP, restore the
   name, diagnose, do NOT delete.
4. Only after all gates: guarded deletion with exact realpath guards; never touch
   `/Users/christian/CMM OS` or `/Users/christian/CMM OS/.worktrees/`.

## 8. Standing constraints

NO PUSH. NO MERGE. MAIN untouched. Do not bypass git hooks. Do not delete the canonical
E0 worktree. Do not delete/overwrite backups. Coherent local commits. Do not claim PASS
from inspection.
