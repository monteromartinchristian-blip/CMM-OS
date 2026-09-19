# Wave F — First Usable: Web Intelligence + Computer Use + Trusted Tool Execution

Date: 2026-09-19. Status: executable plan (no TBD architecture).
Descends from canonical Wave E: CMMChat `feature/qwen-visual-v0` @ 9424498,
CMM OS worktree `feature/cmmchat-wave-e-real-intelligence` @ c3fce1c.
Wave F CMM OS worktree: `/Users/christian/CMM OS/.worktrees/cmmchat-wave-f-first-usable`
(branch `feature/cmmchat-wave-f-first-usable`, created from c3fce1c).

## 1. Authority boundaries (no duplicate owners)

| Concern | Owner |
|---|---|
| Capability contracts, search/retrieval/computer policy + execution, tool reasoning, approvals gating, error normalization, egress classification | CMM OS (new `cmm/web`, `cmm/computer`, `cmm/capabilities`) |
| Product persistence (ToolRun, sources/citations, approval state), SSE event bridge, run coordination, conversation tree, Projects/Files/Artifacts | CMM Hub |
| Rendering + supervision (cards, citations, approvals UI, stop, permission onboarding, settings-lite) | CMMChat Apple |
| Provider/model access | CMM Routers (untouched) |

Swift never invokes search engines, browsers, AX APIs, providers or shells.
Hub never learns backend identity (DDG vs Brave vs …) — only normalized events.
CMM OS reuses: the Wave E model-execution seam (`cmm/model_execution`),
`InformationAcquisitionService` (handler registration for `search_external_source`),
`ExternalSourceRequirement`-style domain policy, roadmap 11.22 event names
(`tool.*`, `computer_use.*`, `capability.approval_required`), roadmap 11.61
capability split (`web.search` ≠ `computer.use`) and human-control states
(RUNNING_AUTOMATED / WAITING_FOR_HUMAN / HUMAN_CONTROL / RESUMING_AUTOMATION).
No second gateway, router, registry, event bus, approval system or SSE engine.

## 2. CMM OS `cmm/web` — real Web Search + retrieval + research loop

Contracts (`cmm/web/contracts.py`, frozen dataclasses):
- `WebSearchRequest(query, limit=8, allowed_domains=(), prohibited_domains=())`
- `WebResultItem(title, url, domain, snippet, rank, backend_id, searched_at)`
- `WebSearchResult(query, items, backend_id, searched_at, warnings)`
- `FetchRequest(url, max_bytes=2_000_000, timeout=15.0)`
- `FetchedSource(url, final_url, domain, title, text, content_type, retrieved_at, truncated, fetched: bool)`
- `Citation(index, title, url, domain, snippet, retrieved_at|None, inspected: bool)`
- `WebCapabilityError(message, code)` codes: `SEARCH_BACKEND_UNAVAILABLE`,
  `SEARCH_TIMEOUT`, `SEARCH_BLOCKED`, `FETCH_FAILED`, `SOURCE_BLOCKED`,
  `CAPABILITY_UNSUPPORTED`, `CANCELLED`.

Backends (`cmm/web/backends/`): `duckduckgo_html.py` — POST
`https://html.duckduckgo.com/lite|html`, browser UA, stdlib `html.parser`
extraction (title/url(decode `uddg=`)/domain/snippet/rank), retry with
backoff on 202/403 (challenge = soft failure → next backend), verified live
from this machine (200, 30 links/10 snippets). `wikipedia_rest.py` —
`/w/rest.php/v1/search/page` structured JSON fallback/enrichment.
Backend selection lives only here; `WebSearchService` exposes one
provider-independent `search(request, cancel_event)` and iterates backends in
configured order. New dependency: `httpx` promoted from dev extra to runtime
extra `web = ["httpx>=0.28,<1"]` (already installed in both venvs).

Retrieval (`cmm/web/retrieval.py`): httpx GET with timeout, ≤5 redirects,
2 MB cap, content-type allowlist (text/html, text/plain, application/xhtml),
SSRF guard (resolve host, refuse private/link-local/loopback/metadata IPs),
stdlib text extraction (strip script/style, collapse whitespace, 24 000-char
window), preserves `final_url` + `retrieved_at`; failures normalize (no fake
citation when retrieval failed — `inspected=False` items cite search snippet
only and are marked as such).

Research loop (`cmm/web/research.py` — `WebResearchService`): bounded
iterative research over the canonical seam executor. Structured action
protocol via one system-prompt contract (model answers strict JSON):
`{"action":"search","query":…} | {"action":"read","url":…} |
{"action":"answer","text":…,"citations":[indices]}`. Limits: 3 searches,
4 reads, 8 model turns; trivial questions answer directly (no forced search).
Citations reference only actually inspected/retrieved sources (or explicitly
snippet-only). Emits `CapabilityEvent`s (see §4). Cancellation checked between
every step. Also registers an `InformationAcquisitionHandler` adapter for
`SEARCH_EXTERNAL_SOURCE` so the canonical Agent Runtime resolves external
search through the same single backend implementation.

## 3. CMM OS `cmm/computer` — real macOS Computer Use

Runtime (`runtime_macos.py`, pyobjc lazy-imported; installed in Hub + CMM OS
venvs; verified live: AXIsProcessTrusted=True, CGWindowList, CG screenshot
4276×2346): observation = AX tree of frontmost app (roles/titles/values/
positions, depth-limited), window/app metadata via CGWindowList + NSWorkspace,
optional CG screenshot to **ephemeral** `tempfile` path (deleted after run;
never persisted by default — §8 privacy). Actions (`actions.py`) normalized
model: `app.open`, `app.activate`, `window.focus`, `ui.press` (AXPress on
matched element — structured target preferred over coordinates),
`ui.set_value`, `keyboard.type`, `keyboard.shortcut`, `pointer.move/click/
scroll` (CGEvent), `wait`. Each action carries `target_description`,
`risk: read_only|sensitive`, `egress: none|screen_content`.

Policy (`policy.py`): read-only actions auto-execute; approval REQUIRED for:
typing into secure/password fields, sending messages/email/posts, publishing,
deleting user data, destructive file ops, install/uninstall, permission or
security-setting changes, meaningful form submissions, purchases, secret
entry, uploads, legal/financial acceptance, account changes. Deny outright:
Terminal `rm -rf`-class shell, keychain access. Uses canonical approval
semantics (allow-once consumption; no second approval system; Hub is the
approval transport).

Loop (`loop.py` — `ComputerUseService`): observe → plan (canonical executor,
strict JSON next-action protocol over structured AX observation; screenshots
only when the selected model declares vision — capability-mismatch otherwise
routes cleanly, never cloud-only by design) → policy check → (approval gate)
→ execute → re-observe → continue/finish. Max 12 steps; `cancel_event`
checked before every action (cancellation prevents the next click/type);
human states per roadmap 11.61; permissions detected honestly
(`COMPUTER_PERMISSION_DENIED` with which permission; UI must not show the
capability as available when denied).

## 4. CMM OS `cmm/capabilities` — one normalized execution surface

`CapabilityEvent(kind, data)` kinds (roadmap-11.22 names): `tool.requested`,
`tool.started`, `tool.progress`, `tool.completed`, `tool.failed`,
`tool.cancelled`, `approval.requested`, `approval.resolved`,
`computer.observation`, `message.delta`, `run.done`. Payloads normalized:
`tool_run_id, capability("web.search"|"web.fetch"|"computer.use"), tool,
status, summary(safe), sources[], approval{id,action_description,target,
reason,consequence,egress}, error{code,message}` — never provider- or
automation-library-specific, never secrets/raw screenshots.
`ApprovalGate` protocol (`request(proposal) -> "allow_once"|"reject"`,
blocking; Hub implements over SSE + REST). `CapabilityExecution.execute(...)`:
intent routing (web-enabled runs go through research loop; computer-use
requests through the loop; cross-capability composition = sequential canonical
steps, no hard-coded Web→Computer chain), egress classification per run
(`processing: local|remote` from resolved model locality; `screen_content`
egress flagged when observation text/screenshots go to a remote model).
`capability_status()` → permission/availability report for onboarding.

## 5. Hub persistence + events (forward-safe only)

Migration `0006_tool_runs`: tables `tool_runs` (id uuid7, run_id, conversation_id,
message_id, capability, tool, status, input_summary, output_summary,
approval_state, egress jsonb, error_code, started_at, completed_at) and
`run_sources` (id, tool_run_id, run_id, message_id, title, url, domain,
snippet, rank, retrieved_at, inspected, content_excerpt ≤2KB, content_hash);
columns on `conversations`: `web_search_mode` (auto|on|off, default auto),
`computer_use_enabled` (bool, default false). NO reset/drop; Wave C/D/E rows
untouched; migration tests upgrade the existing Wave E DB.
New SSE event types registered in all five contract places (schemas Literal,
run-event.schema.json, cmmchat-v1.yaml + test_openapi, fixtures ndjson, Swift
EventType). RunManager consumes `CapabilityEvent`s in the existing
commit-before-yield boundary pattern; approvals: `approval.requested`
persisted + emitted, run thread blocks on gate; `POST
/v1/runs/{run_id}/approvals {tool_run_id, decision}` resolves (allow_once |
reject), 300 s timeout → `APPROVAL_TIMEOUT` normalized failure of that tool
run only; cancel sets the same `cancel_event_for(run)` the capability loops
poll. Sources attach to the assistant message; citations persist via
`run_sources`. `GET /v1/capabilities` proxies `capability_status()`.

## 6. Apple UI (Claude as observable reference; palette frozen)

Composer: globe toggle (Búsqueda web: Automática/Activada/Desactivada) +
computer-use toggle with honest permission state. Transcript: ToolActivityCard
(running = expanded-enough-to-supervise with live summary "Buscando en la
web…", "Leyendo boe.es", "Usando el ordenador…"; completed = compact row
"Consultadas 6 fuentes" expandable to sources/details), SourceCards
(title/domain, click opens), citation markers [n] resolving to persisted
sources, ApprovalCard (what/where/why/consequence/egress + Permitir una vez /
Rechazar, keyboard-operable, VoiceOver-labelled), ComputerUsePanel (active
state, app/window, current step, recent actions, timer, Stop, Tomar control
stretch). Permission onboarding sheet with System Settings deep links
(x-apple.systempreferences:…Privacy_Accessibility / Privacy_ScreenCapture).
Settings-lite popover: approval policy display + privacy/egress explanation
(local vs remote processing). All strings en + es-ES (String Catalog).
No sidebar IA/theme/brand/Projects/Artifact/model-selector redesign.

## 7. Tests, canaries, evidence

TDD everywhere. CMM OS: tests/web (contract, adapter via deterministic httpx
double + one guarded live test, normalization, fetch guards, citations,
cancellation, errors, acquisition-handler binding), tests/computer (action
model, policy, approvals boundary, cancellation, fake runtime + guarded real
macOS smoke), tests/capabilities (event grammar, routing, egress, no parallel
authority) + architecture gates per package. Hub: ToolRun/source persistence,
tool event streaming, approvals, cancellation, tree integrity, Project
association, Artifact regression, migration 0006 (existing-DB upgrade).
Apple: event decoding (shared fixtures), ChatStore flows, UI tests for
toggles/approval card, Wave C/D/E regression suites.
Real canaries (§39–43) on the healthy lane (loopback vLLM `qwen3.8-27b-fp8`
or router when healthy — external chatgpt-bridge/claude-login blockers are
documented, not repaired): live DDG search with current-information query →
real citations persisted; real computer task (open TextEdit → approval-gated
type → Safari to searched URL); approval reject-prevents + allow-once;
mid-task cancellation; web+computer composition. §44 E2E journey in the
normal app; §52 visual evidence Black/Dark/Light + Claude side-by-side.

## 8. Commits (§49) — local only, NO PUSH/NO MERGE, main untouched

1 docs(plan) both repos · 2 CMM OS web contracts+backends+retrieval ·
3 CMM OS research loop · 4 CMM OS computer runtime+policy+loop ·
5 CMM OS capabilities facade+gates · 6 Hub contracts+migration+persistence ·
7 Hub run-manager capability bridge+approvals · 8 Apple decoding+store ·
9 Apple UI+localization · 10 tests/canaries · 11 docs/evidence FIRST_USABLE.
