# Phase 9.22 — Agent Runtime CLI

## Objective

Expose the Phase 9.21 Agent Runtime API as `cmm agent ...`: a stable, typed, scriptable command-line transport for human use, shell scripts, CI, n8n, and future agents. The CLI is a **thin transport layer** — it translates argv into `AgentRuntimeApiRequest`/`AgentRuntimeApiContext`, calls `AgentRuntimeApiService.execute`, and renders the resulting `AgentRuntimeApiResponse`. It never touches managers, repositories, adapters, the event bus, or the trace service directly, and it never re-implements domain logic (validation, state machines, budget arithmetic) that already lives in the API layer.

## Relation to Phase 9.21

Everything the CLI does is a translation, in both directions:

```
argv ──▶ AgentRuntimeApiRequest + AgentRuntimeApiContext ──▶ AgentRuntimeApiService.execute()
                                                                        │
stdout/stderr ◀── AgentRuntimeCliResult ◀── formatter ◀── AgentRuntimeApiResponse
```

The CLI depends on exactly one entry point into the runtime: `AgentRuntimeApiService`. Every operation the CLI can invoke corresponds 1:1 to an `AgentRuntimeApiOperation` already registered by that service — the CLI does not add, remove, or reinterpret operations.

## Modules

| Module | Responsibility |
|---|---|
| `agent_runtime_cli.py` | Public facade — the one import path for external consumers |
| `agent_runtime_cli_app.py` | `AgentRuntimeCliRunner`, `run()`, `main()` — argv in, exit code / result out |
| `agent_runtime_cli_commands.py` | The full `argparse` tree, per-operation payload builders, batch processing |
| `agent_runtime_cli_context.py` | `AgentRuntimeCliContextBuilder` — actor/permission/config/env resolution |
| `agent_runtime_cli_formatters.py` | `HumanFormatter`, `JsonFormatter`, `JsonLinesFormatter`, `QuietFormatter`, redaction |
| `agent_runtime_cli_parsers.py` | Small, independently-testable value parsers (JSON, metadata, decimal, identifiers, …) |
| `agent_runtime_cli_result.py` | `AgentRuntimeCliResult`, exit-code constants, `map_api_error_to_exit_code` |
| `agent_runtime_cli_errors.py` | CLI-local exception hierarchy (distinct from `AgentRuntimeApiException`) |

No other modules were added — the eight files above are the entire CLI surface, plus tests and this document.

## Integration with the existing CLI

The pre-existing `cmm` command is `cmm.cli:main` → `cmm/__main__.py` (`kernel/cli.py` is a separate, older single-purpose CLI — `python -m kernel.cli "<prompt>"` — unrelated to the `cmm` subcommand tree and was not touched). `cmm/__main__.py` gained one subparser entry, `agent`, registered only for `cmm --help` discoverability.

Actual dispatch happens *before* `cmm`'s top-level `argparse.ArgumentParser` ever runs: `main()` checks `sys.argv[1:][:1] == ["agent"]` and forwards the remaining argv straight to `agent_runtime_cli.main()`. This was a deliberate choice over the more obvious `nargs=argparse.REMAINDER` passthrough — `REMAINDER` does not reliably forward a leading `-`/`--` token (e.g. `cmm agent --help`) through a nested `subparsers` action; the token gets swallowed by the outer parser's own `-h/--help` handling and never reaches the inner one. A raw argv prefix check sidesteps the problem entirely and keeps the agent subtree's own `argparse.ArgumentParser` fully independent. No existing `cmm` subcommand (`validation`, `run`, `develop`) was modified.

## Commands

```
cmm agent goal        create | get | list | update | prioritize | pause | resume | cancel
cmm agent run          start | get | list | pause | resume | cancel
cmm agent approval     list | get | approve | reject
cmm agent budget       get | reserve | release
cmm agent trace        get | list | verify | export
cmm agent event        publish | list | replay
cmm agent dead-letter  list | replay
cmm agent health
cmm agent stats
cmm agent batch
```

Every leaf command maps to exactly one `AgentRuntimeApiOperation` (batch maps one operation per JSONL line). The full mapping lives in `agent_runtime_cli_commands.py`'s `_RESOURCE_BUILDERS` table plus the two dedicated `health`/`stats` branches in `dispatch_resource`.

### Global options

`--help --version --output {human,json,jsonl,quiet} --json --quiet --verbose --request-id --actor-id --permission (repeatable) --idempotency-key --config --no-color`

`--json`/`--quiet` are sugar for `--output json`/`--output quiet`; passing an incompatible combination (`--json --quiet`, or `--json` together with a conflicting `--output`) is a usage error (exit 2), not a silent override. `--verbose` never enables stack traces — there is no code path that prints one. `--no-color` is accepted and threaded through today as a no-op: `HumanFormatter` has no ANSI output to suppress, so this flag exists for forward compatibility rather than changing current behavior.

`--help`/`--version` never construct an `AgentRuntimeApiService` — `AgentRuntimeCliRunner` only builds (and then caches) a default service lazily, the first time a command actually needs to dispatch. Argument parsing runs with `sys.stdout`/`sys.stderr` redirected to in-memory buffers (only for the duration of `parser.parse_args`, since that is the one call `argparse` insists on printing through and calling `sys.exit` from); the runner catches the resulting `SystemExit` and turns it into a normal `AgentRuntimeCliResult` — `main()` is the only function allowed to hand an exit code back to the OS.

## Context and permissions

`AgentRuntimeCliContextBuilder` resolves an `AgentRuntimeApiContext` with strict precedence **CLI > environment > config file > safe defaults**, evaluated independently per field (whichever source has a value wins for that field; sources are not merged).

Environment variables consulted — and *only* these five:

```
CMM_AGENT_ACTOR_ID CMM_AGENT_PERMISSIONS CMM_AGENT_OUTPUT CMM_AGENT_CONFIG CMM_AGENT_NO_COLOR
```

Mutating operations (`goal.create/update/prioritize/pause/resume/cancel`, `run.start/pause/resume/cancel`, `approval.approve/reject`, `budget.reserve/release`, `event.publish/replay`, `dead_letter.replay` — the exact set is `MUTATING_OPERATIONS` in `agent_runtime_cli_context.py`) never fall back to a default actor: if CLI, environment, and config all leave the actor unresolved, the CLI raises a usage error (exit 2) before ever building a request. Read-only operations fall back to a fixed, documented actor (`"cli"`) so `cmm agent goal get X` doesn't require ceremony to read data. Permissions never have an implicit default for *any* operation, mutating or not — an actor is never assumed to carry permissions just because they were named; every permission must come from `--permission`, `CMM_AGENT_PERMISSIONS`, or the config file's `permissions` list.

### Config file

JSON object, capped at 64 KiB, loaded from `--config PATH` or `CMM_AGENT_CONFIG`. Recognized keys: `actor_id` (string), `permissions` (list of strings), `output` (string), `no_color` (bool) — any other key is silently ignored (forward compatible) rather than rejected. A missing file, oversized file, invalid JSON, wrong-typed field, or a symlink resolving to a nonexistent target all raise `AgentRuntimeCliConfigError` (exit 2) with a generic message — the config's own content (which may include an `actor_id` the operator doesn't want echoed) is never included in an error message.

## Parsing

All value parsing lives in `agent_runtime_cli_parsers.py` as small, pure functions: `parse_json_inline`, `parse_json_file`, `parse_metadata`, `parse_permissions`, `parse_iso_datetime`, `parse_decimal`, `parse_identifier`, `parse_enum`, `parse_output_format`, `parse_limit`, `parse_cursor`. None of them use `eval`, `exec`, `ast.literal_eval`, `pickle`, or unsafe YAML — enforced by an AST-based test, not a substring grep (a substring grep would false-positive on this very sentence).

`--payload` (inline JSON) and `--payload-file` are mutually exclusive; both parsers reject: invalid JSON, a non-object top level, oversized input (64 KiB inline / 5 MiB from file, configurable per call), and any key or string value containing a restricted marker (`chain_of_thought`, `internal_reasoning`, `private_prompt`, `password`, `token`, `api_key`, `bearer`, `private_key`, `secret`, `credential`, `authorization`, `access_token`, `refresh_token`) or a code-execution marker (`eval(`, `exec(`, `subprocess`, `__import__`, `os.system`, `pickle`). `--metadata key=value` (repeatable) applies the same restricted-key check plus a per-value size cap, and rejects a conflicting duplicate (same key, different value) while tolerating an identical repeat. Amounts (`budget reserve`/`release`) are parsed as `Decimal` and only converted to `float` at the very last step, immediately before being placed in the request payload — `AgentRuntimeApiService`'s in-memory `BudgetApiAdapter` does its own arithmetic in `float`, so a `Decimal` cannot be threaded through the existing adapter without changing 9.21 code, which is out of scope here. All resource identifiers (`goal_id`, `run_id`, trace ids, dead-letter ids, …) go through `parse_identifier`, which rejects `/`, `\`, `..`, and NUL bytes — this is also what makes the default trace-export filename (`{trace_id}.{format}`) safe to build without a separate traversal check.

## Formatting

Four formatters share one contract, `format(result: AgentRuntimeCliResult) -> str`:

- **`HumanFormatter`** — deterministic (sorted keys), no external dependencies, ISO-8601 timestamps, `Decimal`/float values as strings, enums by `.value`.
- **`JsonFormatter`** — always-valid single-line JSON (`sort_keys=True`, `ensure_ascii=True`); anything that somehow reaches `json.dumps` un-serialized is replaced by a placeholder via `default=`, never repr'd.
- **`JsonLinesFormatter`** — the same shape, compact separators, used for `batch` output.
- **`QuietFormatter`** — the single most useful scalar (a resource id, a `total`, a `status`) and nothing else on success; on error it still prints `CODE: message` — quiet never hides a failure.

Serialization and redaction are one fail-closed function, `to_serializable()`: dataclasses become dicts, enums become `.value`, `datetime`/`date` become `.isoformat()`, every `float` becomes `str(Decimal(str(value)))` (never a raw float repr), and any dict key matching the sensitive-field set (same list as the parsers, plus `internal_reasoning`) is replaced with `**REDACTED**` at any nesting depth. Anything `to_serializable` does not explicitly recognize becomes `**UNSERIALIZABLE**` rather than being `repr()`'d or `str()`'d — redaction fails closed, not open.

## Exit codes

One function, `map_api_error_to_exit_code`, is the only place this mapping exists:

| Code | Meaning | API error code(s) |
|---|---|---|
| 0 | success | — |
| 1 | internal/general failure | `INTERNAL_ERROR`, `SERIALIZATION_ERROR`, unrecognized codes |
| 2 | usage/validation | `VALIDATION_ERROR`, `CONTRACT_ERROR`, `UNSUPPORTED_OPERATION`, any CLI-local `AgentRuntimeCliError` |
| 3 | not found | `NOT_FOUND` |
| 4 | conflict | `CONFLICT`, `IDEMPOTENCY_CONFLICT` |
| 5 | permission denied | `PERMISSION_DENIED` |
| 6 | policy denied | `POLICY_DENIED` |
| 7 | approval required | `APPROVAL_REQUIRED` |
| 8 | budget exceeded | `BUDGET_EXCEEDED` |
| 9 | invalid state | `STATE_ERROR` |
| 10 | unavailable | (CLI-local `AgentRuntimeCliUnavailableError`; no current API error code produces this) |
| 130 | interrupted | `KeyboardInterrupt`, caught at the outermost boundary of `AgentRuntimeCliRunner.run` |

`KeyboardInterrupt` is never mapped through the API-error path — it is caught directly and always produces exit 130 with empty stdout/stderr, no stack trace.

## Batch

`cmm agent batch [--file PATH] [--fail-fast] [--max-lines N] [--max-bytes N] [--summary]` reads JSONL from `--file` or, if omitted, from stdin (capped at `--max-bytes`, read in one bounded call rather than an unbounded loop). Each line is a JSON object: `{"operation": "...", "payload": {...}, "request_id": "...", "idempotency_key": "...", "actor_id": "...", "permissions": [...]}` — only `operation` is required. Lines are processed strictly in order; a per-line result (tagged with its 1-based line number) is emitted to stdout as one JSON object per line, whether it succeeded or failed. A failing line does not stop the batch unless `--fail-fast` is set. `--summary` appends one final `{"summary": {...}}` line. The overall process exit code is `0` if every line succeeded and `1` otherwise — a mixed batch is not a *usage* error, it's a set of independent results, some of which failed.

## Trace export

`cmm agent trace export TRACE_ID [--format json|jsonl|summary] [--output-file PATH] [--force]` writes via a temp-file-then-`os.replace` sequence in the destination's own directory (`tempfile.mkstemp` + `fsync` + `os.replace`), so a crash mid-write can never leave a half-written file at the final path. Without `--output-file`, the destination defaults to `{trace_id}.{format}` in the current directory — safe by construction because `trace_id` already passed through `parse_identifier`. An existing destination is left untouched unless `--force` is given (exit 2 otherwise, not a silent overwrite). Export content passes through the same `to_serializable`/redaction path as every other response, so a record containing e.g. `chain_of_thought` cannot reach the file even though `TraceApiAdapter.export` already redacts on its own — this is intentional defense in depth, not distrust of the adapter specifically.

## Security invariants (tested, not just asserted)

No `eval`/`exec`/`literal_eval`/`pickle`/`subprocess`/`os.system` anywhere in the CLI (AST-checked). No stack traces in any formatter output, ever. No chain-of-thought, internal reasoning, private prompts, passwords, tokens, API keys, bearer credentials, private keys, secrets, or credentials survive `to_serializable` at any nesting depth. No actor or permission is ever assumed — both must be explicit for every mutating operation, and permissions must be explicit for every operation. No fake success, fake "valid" trace status, fake "delivered" event, or fake replay: `event.publish`/`replay` always report delivery as `"recorded"` (never `"delivered"`, since the in-memory adapter has no real subscriber to confirm against), `trace.verify` reports one of `empty`/`verified`/`tampered` based on an actual hash-chain walk, and both `event replay --dry-run` and `dead-letter replay --dry-run` call only read-only operations (`event.list`, `dead_letter.list`) and never the mutating one.

## Known limitations (real, not glossed over)

- **List filters are transport-only today.** `goal list --status/--creator-id/...`, `run list`, `trace list`, `dead-letter list --handler`, and most of `event list`'s filters are accepted and forwarded in the request payload, but the current in-memory adapters (Phase 9.21) largely ignore them and return everything the actor is allowed to see (`goal.list`/`run.list` return all records; `approval.list` always returns pending; `trace.list`/`dead_letter.list` filter only by ownership, not by the CLI's filter flags). The CLI does not fabricate client-side filtering to paper over this, since that would duplicate domain logic the task explicitly says not to re-implement.
- **`goal pause/resume/cancel --reason` and `budget reserve/release --reason` are accepted but not persisted.** `GoalApiAdapter._transition` and `BudgetApiAdapter` do not read a `reason` field from the payload at all today; the CLI still sends it (so a future adapter version that does read it works without a CLI change) but nothing currently stores it.
- **`--creator-id`/`--owner-id` on `goal create` and `--agent-id` on `run start` are accepted but not authoritative.** `GoalApiAdapter.create` always attributes `creator`/`owner` to `context.actor`, and `AgentRunApiAdapter.start` never reads an `agent_id` from the payload.
- **`--unit tokens` on `budget reserve` can trip a real Phase 9.21 `ValidationMiddleware` false positive.** That middleware scans `str(payload)` for the substring `"token"` to reject leaked credentials, which also matches the ordinary word "tokens" used as a budget unit. The CLI's own default unit is `"iteration"` (matching `BudgetApiAdapter`'s internal default) specifically to avoid tripping this by default; a user who explicitly passes `--unit tokens` gets an honest `VALIDATION_ERROR` (exit 2) rather than the CLI silently rewriting their input. Fixing the underlying substring match belongs to a future Phase 9.21 hardening pass, not this one.
- **There is no public operation to create a trace, an approval, or a dead-letter entry.** They are seeded internally (by other runtime components emitting lifecycle events, requesting approval, or routing a failed delivery) via seams like `TraceApiAdapter.create_trace`/`ApprovalApiAdapter.request_approval`/`RuntimeEventApiAdapter.route_to_dead_letter` that are not registered as API operations. `cmm agent trace get`/`approval get`/`dead-letter replay` against an id that was never seeded this way correctly returns `NOT_FOUND` — this is not a CLI gap, it's the current shape of the 9.21 API surface.
- **`--no-color` has no visible effect yet.** `HumanFormatter` emits plain, uncolored text; the flag and `CMM_AGENT_NO_COLOR` are wired through the context/config layer for when colored output is added, not because it changes anything today.

## Future integration

- **n8n**: `cmm agent ... --output json` (or `--json`) is designed to be called as an n8n Execute Command node — one JSON object on stdout on success, one JSON object on stderr on failure, and a distinguishing process exit code per the table above. `batch --file` is the natural fit for an n8n loop that needs to submit many operations in one process invocation.
- **HTTP/UI**: `AgentRuntimeCliRunner`'s three-stage shape (build request/context → `AgentRuntimeApiService.execute` → format response) is the same shape an HTTP handler would take; only `agent_runtime_cli_commands.py`'s argv-to-payload builders and `agent_runtime_cli_formatters.py`'s output rendering are CLI-specific. A future HTTP transport would reuse `AgentRuntimeApiService` directly and would not need to duplicate the payload-shaping logic already captured here per operation.

## Examples

```bash
cmm agent health --output json --permission system:read
cmm agent goal create --title "Ship 9.22" --objective "CLI transport" \
  --actor-id ops-1 --permission goal:write
cmm agent goal list --output json --actor-id ops-1 --permission goal:read
cmm agent run start goal-1 --actor-id ops-1 --permission run:write
cmm agent trace verify trace-1 --actor-id ops-1 --permission trace:read
cmm agent trace export trace-1 --output-file trace-1.json \
  --actor-id ops-1 --permission trace:read --permission trace:export
cmm agent event publish goal.created --actor-id ops-1 --permission event:write
cmm agent event replay --event-type goal.created --dry-run \
  --actor-id ops-1 --permission event:read
cmm agent batch --file requests.jsonl --summary
```

## Design decisions

- **One resource per module file, all in `agent_runtime_cli_commands.py`.** The alternative — a file per resource — was considered and rejected: the payload-shaping functions are individually small (10–40 lines each) and sharing the `argparse` parent-parser pattern and `_query_payload`/`_priority` helpers in one file avoids either duplicating them eight times or introducing a ninth module purely for shared plumbing.
- **`argparse` `parents=` over manual re-declaration.** Global options (`--output`, `--actor-id`, `--permission`, …) are defined once and attached via `parents=[global_parser]` to the root parser and to every resource/leaf parser, so `--output json` can appear before or after the subcommand (`cmm agent goal list --output json` and `cmm agent --output json goal list` both work).
- **Dry-run as a client-side read, not a fake mutation.** `event replay --dry-run` and `dead-letter replay --dry-run` have no server-side concept (the 9.21 adapters don't implement a preview mode) — implementing them by calling the real read-only list operation and filtering client-side for *display* is honest (it reports exactly what the read operation returned) without duplicating the adapters' own mutation logic.
- **Batch exit code is binary (0/1), not per-line-code-aware.** A batch run is a set of independent results; picking, say, "the worst exit code among all lines" would imply an ordering across unrelated error classes (is a `NOT_FOUND` worse than a `PERMISSION_DENIED`?) that doesn't exist. `0` (all succeeded) vs `1` (at least one failed) is the only distinction that means something at the process level; per-line detail is in the JSONL body.

## Debt carried forward

- The list-filter and `--reason`/`--creator-id`/`--agent-id` gaps above are Phase 9.21 adapter debt inherited as-is; the CLI passes the data through honestly rather than working around it.
- The `ValidationMiddleware` "token" substring false positive is a real 9.21 bug the CLI works around only via its own default, not by patching 9.21.
- `--no-color` and `CMM_AGENT_NO_COLOR` are plumbed but inert until `HumanFormatter` gains actual colored output.
