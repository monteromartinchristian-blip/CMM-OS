# CMMChat Wave E canonical reconciliation — final evidence (2026-09-19)

Canonical CMM OS: `/Users/christian/CMM OS`. The obsolete Phase-10 clone
(`~/CMM-OS`) was quarantined and deleted after every safety gate passed.
No push, no merge; `main` untouched.

## Ported semantics (this worktree, branch `feature/cmmchat-wave-e-real-intelligence`)

- `be9fc96` feat(model-execution): chat surface on the existing seam —
  `catalog()/resolve_chat()/stream()` on `CanonicalModelExecutor`; AUTO and
  explicit selection through the canonical `ModelRouter`/`ModelCatalog`,
  streaming through the canonical provider abstraction, normalized secret-free
  failures. No new facade, no Phase-10 architecture.
- `af57a86` test(model-execution): 28 tests pinning the ported chat semantics
  (`tests/model_execution/test_chat_streaming.py`,
  `tests/llm/test_provider_streaming.py`).
- `319112e` feat + `45af96a` test + `c561e96` fix: an opt-in loopback
  local-runtime lane composed by the same seam (`local-runtime` provider id,
  `CMM_LOCAL_RUNTIME_MODEL_IDS/_BASE_URL/_API_KEY`). Ordinary `ProviderSpec` +
  `ModelSpec` in the one canonical registry/catalog; credential stays an env
  name. Absent configuration composes the router-only seam unchanged.

Focused coverage after all changes: `tests/model_execution` + `tests/llm` =
967 passed; full-suite parity vs the E0 baseline = the same 31 pre-existing
domain/validation failures (the two extra `tests/cli` failures seen once were
missing `cmm-os` editable metadata in the environment, restored with
`pip install -e . --no-deps`; both tests then passed from the worktree).

## CMMChat side (branch `feature/qwen-visual-v0`)

- `7086f8d` checkpoint(hub): intelligence boundary repointed to the canonical
  worktree seam with provenance enforcement (imports resolve from
  `/Users/christian/CMM OS/.worktrees/cmmchat-wave-e-real-intelligence`;
  obsolete-root origins raise `CMM_OS_UNAVAILABLE`). The hidden dependency this
  removed: a `cmm-os` editable install in the Hub venv pointing at the old
  clone — uninstalled.
- `6de3bc2` checkpoint(hub): root logging at INFO so the provenance line is
  visible under uvicorn:
  `CMM_OS_SOURCE_ROOT=… OBSOLETE_CMM_OS_LOADED=NO` (live in the Hub log).
- `9424498` checkpoint(test): canary reads SSE line-by-line (buffered 256-byte
  reads coalesced frames and distorted latency/cancel timing), cancels at
  `model.selected`, configurable pacing `CMM_CANARY_GAP_SECONDS`.
- Hub suite: 106 passed (before quarantine, with the old path absent, and
  again after deletion).

## Real-inference gates (§12)

Via `CMMChat → Hub(:8766) → canonical seam → CMM-Routers(:8790) → real
model` and `→ loopback local runtime → real model`:

- `REAL_MODEL_EXECUTION` / `CMM_AUTO` / `REAL_STREAMING` / `PERSISTENCE`:
  canary `RESULT PASS` (AUTO → `chatgpt/chatgpt-web/high`, run.completed,
  streamed content equals persisted assistant text).
- `EXPLICIT_MODEL`, `CANCELLATION`, post-cancel continuation:
  `~/cmmchat-waveE-evidence/local-runtime-journey.py` → `RESULT PASS` with
  `qwen3.8-27b-fp8` on the loopback vLLM runtime: explicit policy selected
  the requested model, real token streaming (first delta ≈2.1s), persistence
  matched the stream, mid-stream cancel through the canonical
  `Hub → cancel_event → client` path ended `run.cancelled`, tree intact
  (partial assistant kept as `failed` per the pre-existing Wave C message
  contract; leaf valid; continuation completed `CONTINUATION_OK`).
- No test stub satisfies any of these lines; all ran against live processes.

## External blockers (preserved, out of scope by decision)

- `CHATGPT_BRIDGE_BLOCKER=CODEX_BINARY_BRIDGE_VERSION_MISMATCH`: the
  subscription lane flaps with `provider_protocol_error`; router logs show
  `responses_websocket 426 Upgrade Required → ws://127.0.0.1:17841/v1/responses`
  and `failed to load models cache: missing field supports_parallel_tool_calls`
  (Codex Web GPT.app bridge / codex binary drift; duplicate app instances were
  found and a clean single-instance restart did not fully restore it).
- `CLAUDE_LANE=NOT_LOGGED_IN`: the claude provider returns HTTP 200 with the
  canned body `Not logged in · Please run /login`.
- Router-side data honesty: `chatgpt/chatgpt-web/extra-high` and the
  `chatgpt/gpt-*` advertisements fail at runtime while listed available; the
  canary therefore pins the configured router tiers via the canonical
  `CMM_ROUTER_MODEL` mechanism (configuration, not code).
- `CMMCHAT_ARCHITECTURAL_FAILURE=NO`, `CMM_OS_ARCHITECTURAL_FAILURE=NO`.

## Obsolete-path proof and destruction (§16–§19)

- Full-path references to `~/CMM-OS` across CMMChat, CMM OS and CMM-Routers:
  only historical plan docs (`docs/superpowers/plans/*`) and the intentional
  rejection guard in `services/hub/src/cmm_hub/intelligence.py`;
  CMM-Routers has none; `git remote` names `CMM-OS.git` are not paths.
- Backup: `cmm-os-obsolete-full-backup-20260919.bundle` (all refs;
  `git bundle verify` = complete history;
  SHA-256 `2e8c8eb5548655c2675334a9603146794503ed73827103da20f0bccd2703a363`)
  in `~/Library/Mobile Documents/com~apple~CloudDocs/Downloads/Temporales/`,
  alongside the pre-existing safety directory. The obsolete clone's
  uncommitted Wave-E edits were re-captured before quarantine:
  `~/cmmchat-waveE-evidence/cmm-os-obsolete-worktree-diff-20260919.patch`
  (412 lines, SHA-256 `d8b08934f4645af53f963f2287fecef4c8c0e71bb39634ed53004b68eb6a04a8`).
- Quarantine `~/CMM-OS.OBSOLETE-WAVE-E-QUARANTINE`: with the old path absent,
  the canary passed (`canary-without-old-path.log RESULT PASS`), the local
  journey passed, and the Hub suite passed.
- Deletion (2026-09-19, after all gates, exact-string realpath guards,
  canonical root and both worktrees verified intact):
  `DELETED_OBSOLETE_CLONE=YES`; neither obsolete path exists. Post-deletion:
  local journey `RESULT PASS`, Hub 106 passed; the subscription-lane canary
  flaked again in the same external way (documented above).
