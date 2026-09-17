# Phase 11 — CLI reference

**Status:** `CLOSED_AFTER_INDEPENDENT_REAUDIT_V1_PASS`
**Phase:** 11.4 — CLI
**Requirement:** `F11-018 — Canonical Operational CLI`
**Design Point:** `DP-104 — Single-Front-Door Fail-Closed Operational CLI`
**Acceptance Test:** `AT-DP-104 — Canonical CLI Integration Acceptance` — `tests/cli/test_phase11_4_dp104_acceptance.py`
**Design specification:** `docs/superpowers/specs/2026-09-16-phase-11.4-cli-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-09-16-phase-11.4-cli-implementation-plan.md`
**Presentation modules:** `cmm/cli.py`; `cmm/__main__.py`; `cmm/cli_contracts.py`; `cmm/cli_output.py`; `cmm/cli_commands.py`; `cmm/cli_application.py`; `cmm/cli_doctor.py`
**Application compatibility additions:** `cmm/application/contracts.py` (`ApplicationChannel`); `cmm/application/requests.py` (channel mapping); `cmm/application/gateway.py` (channel forwarding); `cmm/application/local_runtime.py` (canonical local composition)
**Focused suite:** `tests/cli/` (459 tests)
**Architecture gates:** `tests/cli/test_phase11_4_architecture.py` (52 tests); `tests/application/test_architecture.py`; `tests/api/test_architecture.py`; `tests/platform/test_architecture.py`; `tests/orchestration/test_architecture.py`
**OpenAPI gate:** `tests/api/test_openapi.py`

```text
PHASE11_4=CLOSED
F11_018=VERIFIED_EXISTING
DP_104=VERIFIED_EXISTING
AT_DP_104=PASS

CLOSURE_ELIGIBLE=YES
```

Phase 11.4 is **independently re-audited and closed after Independent Re-audit V1 PASS**. `AT-DP-104` is
green in this repository, the inherited Phase 11 acceptances stay green, and the
documented states above are the maximum this documentation may claim before an
independent audit. Nothing here is `CLOSED`, `VERIFIED_EXISTING` or
closed-eligible, and no production semantics of a closed phase were reopened.

## 1. Purpose and ownership boundary

Phase 11.4 exposes **one** canonical command-line front door over the closed
Phase 11 platform. The CLI is a *presentation adapter*: it declares a public
command namespace, renders results deterministically, maps public errors to
stable process exit codes and delegates every operational command to a canonical
owner.

It owns no platform truth. Concretely, the CLI owns only:

- public parser topology and the reserved command namespace;
- global output options and global output format selection;
- deterministic rendering of one public result document;
- the stable public exit-code vocabulary and its mapping;
- delegation to canonical adapters;
- help/version UX and capability-unavailable presentation.

It owns none of: business logic, domain routing, agent routing, workflow
execution authority, session persistence, approval authority, provider
authority, configuration source of truth, backup engine, migration engine,
plugin runtime, metrics engine, observability backend or a database.

The verification task observed the following at implementation HEAD
`78bd24ca2e371f11c29ee6c82764042161acf224` (Python 3.14, `.venv`):

```text
tests/cli                                     459 passed
inherited CLI regression                      368 passed
tests/application + tests/api                 857 passed
connected Phase 11 acceptances                247 passed
tests/platform + tests/orchestration          856 passed
relevant domain/agent/session regressions     622 passed
global suite                                  20433 passed (exit code 0)
```

## 2. Public entrypoint

Package metadata remains the single authority for the public command:

```toml
[project.scripts]
cmm = "cmm.cli:main"
```

Both public execution forms are equivalent and share one parser:

```text
cmm ...
python -m cmm ...
```

| File | Role |
|---|---|
| `cmm/cli.py` | Console-script wrapper: delegates to `cmm.__main__.main` |
| `cmm/__main__.py` | Root `argparse` parser, dispatch and automation semantics |
| `cmm/cli_contracts.py` | Frozen presentation contracts (schema version, formats, exit codes, availability, safe envelopes, static command descriptor) |
| `cmm/cli_output.py` | Deterministic rendering and stream selection |
| `cmm/cli_commands.py` | Reserved namespace registration, static command table, explicit dispatch |
| `cmm/cli_application.py` | The one CLI-to-`ApplicationGateway` adapter and startup seam |
| `cmm/cli_doctor.py` | Read-only canonical diagnostic aggregator |

No second CLI root, no `cmm/cli/` package, no alternative framework (`typer`,
`click`, `fire`, `docopt`, `textual`, `prompt_toolkit`) and no parallel CLI
authority (`CommandRegistry`, `CommandRouter`, `CommandBus`, `CommandRuntime`,
`CommandEngine`, `CLIService`, `CLIStateStore`, `CLIRepository`,
`CLIHistoryStore`) exists. `kernel/cli.py` stays an inherited lower-level
surface and is not a competing public product entrypoint.

## 3. Command namespace

The public namespace is *reserved*: every roadmap family is reachable from the
root parser whether or not a canonical owner backs it today. A reserved command
is a **known** command with an explicit availability status, never an unknown
one; an unknown command remains an ordinary `argparse` usage error.

### 3.1 Available commands

| Command | Shape | Canonical owner |
|---|---|---|
| `cmm status` | `[--output ...] [--quiet] [--verbose]` | `ApplicationGateway` (`health.get` + `capabilities.list`) |
| `cmm doctor` | `[--output ...] [--quiet] [--verbose]` | Read-only aggregation over the same gateway |
| `cmm ask` | `[TEXT] --actor ACTOR [--session SESSION] [--idempotency-key KEY]` | `ApplicationGateway` (`sessions.create`, `messages.submit`) |
| `cmm chat` | `--actor ACTOR [--session SESSION]` | `ApplicationGateway` (`sessions.create`, `messages.submit`) |

`cmm status` projects the canonical health and capability declarations into one
safe document: `platform_state`, `platform_ready`, `application_api_version`,
the sorted canonical `services` and the sorted declared `capabilities`. The CLI
computes no readiness of its own.

`cmm ask` submits exactly one one-shot canonical request and creates exactly one
canonical session when the caller names none. Its request text comes from the
positional argument or from piped standard input — exactly one of the two: both
at once, or neither, is refused before any canonical request exists
(`INVALID_REQUEST`, exit `3`). An interactive terminal is never read, so `ask`
cannot block on input nobody piped into it.

`cmm chat` runs the minimal interactive loop over one canonical session. It
keeps no conversation of its own: no transcript, no history file, no editing, no
regeneration, no attachments and no local notion of a message. Empty lines are
skipped, `/exit` and `/quit` terminate the loop, and end of input terminates it
as well. Each turn's outcome is rendered as its own document; the final result
reports `session_id`, `submitted`, `failed` and `termination`, with status
`success` or `degraded`. An internal failure is terminal for local interaction
rather than a spin.

### 3.2 Reserved commands (unavailable in this build)

Every reserved command parses, is listed in help with the explicit label
`(unavailable in this build)`, and fails closed on dispatch with
`CAPABILITY_UNAVAILABLE` and exit code `5`. None of them starts the platform, and
none of them fabricates a success, an empty list or a placeholder object.

| Family | Reserved commands |
|---|---|
| `config` | `config show`, `config set` |
| `goals` | `goals list`, `goals create`, `goals show`, `goals pause`, `goals resume` |
| `workflows` | `workflows list`, `workflows show`, `workflows run`, `workflows pause`, `workflows resume`, `workflows cancel` |
| `approvals` | `approvals list`, `approvals approve`, `approvals reject` |
| `memory` | `memory search` |
| `knowledge` | `knowledge inspect` |
| `domains` | `domains list` |
| `plugins` | `plugins list` |
| `backup` | `backup create`, `backup restore` |
| standalone | `migrate`, `logs`, `metrics` |

The frozen static table declares **29** command identities: **4 available** and
**25 unavailable**. `cmm --help` derives its closing line from that table, so
help text cannot drift from the metadata:

```text
Available in this build: status, doctor, ask, chat. Reserved commands stay
listed so they are discoverable, and fail closed with CAPABILITY_UNAVAILABLE
until a canonical owner is wired.
```

`domain` (Domain SDK developer tooling, Phase 10.35) and `domains` (reserved
operational runtime/domain inspection) deliberately coexist with distinct
semantics. No `agents` family was added beside the inherited `agent` subtree.

A reserved command is answered from the frozen table alone:

```json
{"command":"backup.create","data":{},"error":{"code":"CAPABILITY_UNAVAILABLE","details":{"command":"backup.create"},"message":"Backup is not available in this platform build."},"metadata":{},"ok":false,"schema_version":"v1","status":"unavailable"}
```

## 4. Output formats

`--output {human,json,yaml}` selects the representation (default `human`).
`--quiet` and `--verbose` are global presentation options.

Exactly one output document is emitted, with exactly one trailing newline:

- **success** payload is written to **stdout**;
- **failure** diagnostics are written to **stderr**, so structured stdout stays
  parseable and free of incidental noise.

Every representation renders the identical semantic document — the thawed,
plain form of the frozen `CliResult` — so no representation can drift from
another. JSON uses canonical sorted compact encoding; YAML uses `yaml.safe_dump`
with sorted keys; human mode prints the command, its status and the data entries
in sorted key order.

```console
$ cmm status --output json
{"command":"status","data":{...},"error":null,"metadata":{...},"ok":true,"schema_version":"v1","status":"success"}

$ cmm status --quiet
ok
```

Every structured document carries the frozen marker `schema_version: "v1"`.

`--quiet` suppresses non-essential human commentary only: a human success prints
just the handler-declared primary value (for `status`, the platform state) or
nothing at all, while structured output stays complete because quiet must never
remove required data. `--verbose` appends only already-safe metadata the handler
supplied; it never adds a traceback, hidden reasoning or a live object, and never
changes a structured document. There is no color, no progress indicator and no
logging on the structured stream.

## 5. Exit codes

Exit codes are frozen, stable and chosen by the result — never by a handler:

| Code | Name | Meaning |
|---|---|---|
| `0` | `SUCCESS` | Command succeeded |
| `2` | `USAGE` | `argparse` usage error (unknown command, bad option) |
| `3` | `INVALID_REQUEST` | A request the CLI itself must refuse (e.g. ambiguous `ask` input) |
| `4` | `NOT_FOUND` | Canonical resource not found |
| `5` | `CAPABILITY_UNAVAILABLE` | Reserved capability, or a capability the platform rejects as unavailable |
| `6` | `PERMISSION_DENIED` | Canonical policy denial or approval required |
| `7` | `CONFLICT` | Idempotency, concurrency or state conflict |
| `8` | `DEPENDENCY_UNHEALTHY` | Doctor found a failing core check |
| `9` | `CANCELLED` | The local interaction was interrupted |
| `10` | `INTERNAL_FAILURE` | Fail-closed internal defect; no internal detail is leaked |

Public application error categories map one-to-one onto these codes:
`INVALID_REQUEST`/`UNSUPPORTED_VERSION` → `3`, `POLICY_DENIED`/
`APPROVAL_REQUIRED` → `6`, `RESOURCE_NOT_FOUND` → `4`, `CONFLICT`/
`IDEMPOTENCY_CONFLICT`/`CONCURRENCY_CONFLICT` → `7`, `CANCELLED` → `9`,
`CAPABILITY_UNAVAILABLE` → `5`, `INTERNAL_FAILURE` → `10`. An unrecognized error
code fails closed as `INTERNAL_FAILURE` rather than being reported as success.

## 6. Application channel semantics

A CLI request is a public application request like any other; the CLI is a
sibling adapter of HTTP over the same canonical boundary. Phase 11.4 adds one
backward-compatible public field, `ApplicationRequest.channel`, with two frozen
values (`api`, `cli`) and the default `API`:

- the channel is **descriptive origin only** — it selects no authority, grants no
  capability and changes no business rule;
- it participates in the request's deterministic public serialization, so two
  otherwise identical commands from different channels have different
  fingerprints and can never share one idempotency replay record;
- `RequestApplicationService` maps it to the canonical `OrchestrationChannel`
  (`ApplicationChannel.CLI` → `OrchestrationChannel.CLI`) when it builds the
  canonical `OrchestrationRequest`, so the canonical pipeline sees the command
  line as its origin;
- the HTTP adapter sets nothing, so the closed Phase 11.3 route, schema and
  behavior surface is unchanged.

A keyed CLI request derives its canonical message identity from the idempotency
key (UUID5 over a frozen namespace) instead of drawing a random identity, so a
retry replays rather than conflicting.

The CLI holds exactly one collaborator — `ApplicationGateway`. It does not
import, store or reach the orchestrator, a registry, a store, a workflow engine
or a provider: `CliApplicationAdapter` builds versioned public requests, projects
the safe public response into the frozen `CliResult` envelope, and validates the
little that is genuinely CLI-owned (non-empty text, an explicit actor).

Startup is lazy and canonical: `build_cli_application()` reuses
`cmm.application.local_runtime.build_local_application_runtime()` — the Phase
11.3 application package's composition root — so a standalone CLI process runs
against the same official in-memory graph an embedded client composes. No second
graph, no service locator, no socket, no worker, no server. Composition happens
when an operational command needs the platform: help, version, a parse error and
a reserved capability are all answered without a runtime existing at all.

## 7. Doctor semantics

`cmm doctor` is a **read-only** diagnostic aggregator over canonical evidence. It
issues queries only — never a session create, a message submit or a cancellation
— reads no secret, resolves no network address and mutates nothing: it does not
repair, migrate, install, rotate, restart or reconfigure anything.

The frozen check set is declared once, in order:

| Check | Core | Evidence |
|---|---|---|
| `application.health` | yes | Canonical application readiness |
| `application.capabilities` | yes | Canonical declared capability state |
| `services` | yes | Canonical service readiness |
| `kernel` | yes | Canonical kernel surface loadability (`kernel`, `kernel.end_to_end_runner`, `kernel.llm.provider_registry` module resolution only — nothing executed) |
| `configuration`, `database`, `storage`, `models`, `permissions`, `migrations`, `secrets`, `network`, `plugins` | no | Reported `unavailable` with reason code `NO_CANONICAL_OWNER`, because no canonical owner exists in this build |

Check statuses are `pass`, `warn`, `fail`, `unavailable` and `skipped`. The result
document carries `checks`, a `summary` count per status, and the `failed` list.

An `unavailable` check is a fact, not a defect. A failing **core** check fails the
run closed: the result reports `failed` with code `DEPENDENCY_UNHEALTHY` and the
dispatcher maps it to exit code `8`. Overall status is `ok`, `degraded` (a
warning) or `failed`.

```console
$ cmm doctor --quiet
ok
```

## 8. Security boundaries

- The public result envelope is validated against one bounded presentation
  grammar (maximum depth, item count and string length; JSON-safe values only;
  no binary data, no non-finite numbers, no opaque runtime objects). A
  secret-shaped key (`password`, `secret`, `token`, `api_key`, `credential`,
  `private_key`, `authorization`, `cookie`, …) fails closed at construction, so a
  secret can never enter a public CLI document.
- Errors are presentation-owned constants or canonical public messages. No
  traceback, exception repr, filesystem path, credential value or hidden
  reasoning reaches an output document.
- `config show` remains unavailable precisely because safe redaction cannot yet
  be guaranteed from a canonical owner.
- Doctor reports module resolution and canonical state; it neither reads
  configuration values nor prints environment contents, and `--verbose` does not
  disable privacy.
- The CLI owns no shell execution authority: it runs no subprocess, spawns no
  worker and holds no daemon.
- A broken pipe ends the command quietly and successfully — a reader that stopped
  reading is not a failure of the command — while `KeyboardInterrupt` yields a
  `CANCELLED` result (exit `9`) that states the local fact and explicitly does
  **not** claim a canonical cancellation was requested, because the CLI owns no
  cancellation path.

## 9. Inherited CLI compatibility

Existing command surfaces are compatibility contracts and were preserved
unchanged, with their own parsers, handlers and exit semantics:

| Inherited surface | Owner |
|---|---|
| `cmm validation ...` | `cmm/validation/cli.py` |
| `cmm domain ...` (Domain SDK) | `cmm/domains/sdk/cli.py` |
| `cmm agent ...` (Agent Runtime, Phase 9.22) | `cmm/agent_runtime/agent_runtime_cli*.py` |
| `cmm run ...` | `kernel/end_to_end_runner.EndToEndRunner` |
| `cmm develop ...` | `cmm/development`, `cmm/execution.development` |

The `agent` subtree keeps its own independent `argparse` root and its raw-argv
dispatch, because a nested `subparsers` action cannot forward a leading `-`/`--`
token (such as `--help`) reliably. The inherited CLI regression baseline of
`368 passed` is unchanged by Phase 11.4.

## 10. Automation semantics

- `cmm ask` reads a request from an argument or from piped stdin; ambiguous
  simultaneous sources fail clearly instead of guessing.
- No color, no spinner and no progress indicator exists, so non-interactive
  automation cannot be broken by presentation.
- Output is deterministic: the same input yields byte-identical documents
  (volatile correlation identifiers aside).
- Shell redirection is sufficient — no generic `--output-file` is introduced, and
  no command writes files.
- There is no CLI-local history database, no `readline` state and no persisted
  sensitive chat content.
- Unknown commands stay `argparse` usage errors (exit `2`); known-but-reserved
  commands exit `5`. The distinction is deliberate and stable for automation.

## 11. Limitations and deferred scope

Phase 11.4 implements the CLI as a presentation adapter and deliberately does
not:

- implement goals, workflows, approvals, memory, knowledge, domains, plugins,
  backup, restore, migrate, logs, metrics or configuration commands — the names
  are reserved and fail closed until a canonical owner exists;
- implement a Plugin System, backup engine, restore engine, migration engine,
  metrics backend, new observability or logging service, Goal subsystem, new
  approval system, new workflow engine, new memory engine, new knowledge store,
  new configuration authority, new provider registry or new model gateway;
- implement cancellation as a CLI feature, file-attachment ingestion, multimodal
  input, output-file options, confirmation prompts for destructive operations,
  shell completion or any product UI (CMMChat, web, desktop, mobile, bots);
- add a second entrypoint, a second parser root or a second application
  composition;
- execute anything on behalf of a request: the local composition installs the
  canonical `AgentExecutionAdapter` with no execution delegate on purpose, so it
  fails closed (`operation.no_execution_delegate`) instead of pretending to
  execute, and the local agent registry is composed empty rather than seeded with
  an invented agent.

Because the public message shape carries no intent, a real `cmm ask "hello"`
reaches the canonical deterministic intent resolver and honestly reports
`needs_clarification` with `route: "none"` — the CLI fabricates no model answer.

## 12. Verification and audit state

`AT-DP-104` (`tests/cli/test_phase11_4_dp104_acceptance.py`, 69 connected tests)
exercises the entrypoint identity, inherited command preservation, `status`,
`ask`, reserved-unavailable behavior, backup unavailability, `doctor`, output
safety, exit codes, no-parallel-authority, current capability truth and platform
compatibility over real canonical components.

Focused suite composition (`tests/cli/`, 459 tests):

```text
test_phase11_4_contracts.py      74
test_phase11_4_output.py         39
test_phase11_4_parser.py         63
test_phase11_4_application.py    28
test_phase11_4_doctor.py         19
test_phase11_4_unavailable.py    83
test_phase11_4_interactive.py    19
test_phase11_4_automation.py     13
test_phase11_4_architecture.py   52
test_phase11_4_dp104_acceptance.py 69
```

The exact-HEAD audit bundle, the global suite record, Ruff, format check,
compileall and `git diff --check` are produced by the implementation plan's
verification task and reported in its handoff, to be independently re-verified.
The single `pytest` warning observed in the application suites is a pre-existing
third-party `StarletteDeprecationWarning` from `fastapi.testclient` and is
unrelated to Phase 11.4.

```text
PHASE11_4=CLOSED
F11_018=VERIFIED_EXISTING
DP_104=VERIFIED_EXISTING
AT_DP_104=PASS

ONE_PUBLIC_CLI_FRONT_DOOR=YES
ARGPARSE_PRESERVED=YES
EXISTING_CLI_SUBTREES_PRESERVED=YES
ROADMAP_NAMESPACE_RESERVED=YES
UNAVAILABLE_CAPABILITIES_FAIL_CLOSED=YES
APPLICATION_GATEWAY_REUSED=YES

NO_COMMAND_REGISTRY=YES
NO_COMMAND_ROUTER=YES
NO_CLI_RUNTIME=YES
NO_CLOSED_PHASE_AUTHORITY_REOPENED=YES

CLOSURE_ELIGIBLE=YES
NEXT=VERIFY_CLOSURE_COMMIT_THEN_INSPECT_PHASE11_5_CONVERSATIONAL_INTERFACE
```

## Final independent audit closure

Phase 11.4 — CLI is closed after Independent Re-audit V1 `PASS`.

```text
PHASE11_4=CLOSED
INDEPENDENT_AUDIT_V1=FAIL
INDEPENDENT_REAUDIT_V1=PASS
BLOCKERS=0
MAJORS=0
MINORS=0
MINOR_01=VERIFIED_REMEDIATED
F11_018=VERIFIED_EXISTING
DP_104=VERIFIED_EXISTING
AT_DP_104=PASS
AT_DP_103=PASS
AT_DP_102=PASS
AT_DP_101=PASS
AT_DP_134=PASS
AUDITED_HEAD=1d6208d3ad849a0d59e5e4c85f63f36a331557d9
AUDITED_TREE=65f897686a1509e0bf889eb33c665bda51486337
REAUDIT_BUNDLE_SHA256=7086611069256b01c13a007f64584343382b39c66cef75cd2a2e601ab5ad5a26
AUDIT_V1_REPORT_COMMIT=22b240ec0ebd9fb81958905ec02414d525efba99
REAUDIT_V1_REPORT_COMMIT=0aae35764d74eb992db9c7af96f2086d0933d821
CLOSURE_ELIGIBLE=YES
AUDIT_STATUS=CLOSED_AFTER_INDEPENDENT_REAUDIT_V1_PASS
NEXT=VERIFY_CLOSURE_COMMIT_THEN_INSPECT_PHASE11_5_CONVERSATIONAL_INTERFACE
```

Historical Audit V1 `FAIL` remains preserved in
`docs/audits/phase-11.4-cli-independent-audit-v1.md`. Final independent
Re-audit V1 `PASS` is recorded in
`docs/audits/phase-11.4-cli-independent-reaudit-v1.md`.
