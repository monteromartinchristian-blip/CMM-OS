# Phase 9.21 — Agent Runtime API

## Objective

Build a stable, typed, decoupled application API that exposes Agent Runtime capabilities to CLI, UI, n8n, external integrations, and future agents — without coupling those consumers to internal managers, repositories, or services. The API acts as an **application facade**, not an HTTP server.

## Contracts

Immutable, serializable contracts:

| Contract | Description |
|---|---|
| `AgentRuntimeApiRequest` | Inbound request with operation, payload, context, idempotency_key |
| `AgentRuntimeApiResponse` | Outbound response with status, data, errors, request_id |
| `AgentRuntimeApiError` | Structured error with code, message, details |
| `AgentRuntimeApiPage` | Paginated result with items, total, cursor, limit |
| `AgentRuntimeApiQuery` | Query parameters: filters, sort, range, pagination |
| `AgentRuntimeApiContext` | Request context: actor, permissions, request_id, timestamp |
| `AgentRuntimeApiPermissions` | Permission flags for resource access |
| `AgentRuntimeApiHealth` | System health status |
| `AgentRuntimeApiStats` | Aggregated runtime statistics |

### Specific Request/Response Contracts

- **Goals**: `CreateGoalRequest`, `GetGoalRequest`, `ListGoalsRequest`, `UpdateGoalRequest`, `PrioritizeGoalRequest`, `PauseGoalRequest`, `ResumeGoalRequest`, `CancelGoalRequest` → `GoalResponse`
- **Runs**: `StartAgentRunRequest`, `GetAgentRunRequest`, `ListAgentRunsRequest`, `PauseAgentRunRequest`, `ResumeAgentRunRequest`, `CancelAgentRunRequest` → `AgentRunResponse`
- **Approvals**: `ListApprovalRequestsRequest`, `GetApprovalRequest`, `ApproveRequest`, `RejectRequest` → `ApprovalResponse`
- **Budgets**: `GetBudgetRequest`, `ReserveBudgetRequest`, `ReleaseBudgetRequest` → `BudgetResponse`
- **Traces**: `GetAgentTraceRequest`, `ListAgentTracesRequest`, `VerifyAgentTraceRequest`, `ExportAgentTraceRequest` → `TraceResponse`
- **Events**: `PublishRuntimeEventRequest`, `ListRuntimeEventsRequest`, `ReplayRuntimeEventsRequest`, `GetDeadLettersRequest`, `ReplayDeadLetterRequest` → `EventResponse`
- **System**: `GetRuntimeHealthRequest`, `GetRuntimeStatsRequest` → `RuntimeHealthResponse`, `RuntimeStatsResponse`

## Operations

Enum `AgentRuntimeApiOperation` with 28 registered operations:

```
goal.create, goal.get, goal.list, goal.update, goal.prioritize,
goal.pause, goal.resume, goal.cancel,
run.start, run.get, run.list, run.pause, run.resume, run.cancel,
approval.list, approval.get, approval.approve, approval.reject,
budget.get, budget.reserve, budget.release,
trace.get, trace.list, trace.verify, trace.export,
event.publish, event.list, event.replay,
dead_letter.list, dead_letter.replay,
runtime.health, runtime.stats
```

## Router

`AgentRuntimeApiRouter` provides:

- `register(operation, handler, alias)` — register a handler
- `unregister(operation)` — remove a handler
- `resolve(operation)` — find handler + middleware
- `dispatch(request, context)` — execute with middleware chain
- `list_operations()` — list all registered operations

### Rules

- Single operation per handler
- Duplicate prevention on register
- Typed handlers with `Callable[[AgentRuntimeApiRequest, AgentRuntimeApiContext], AgentRuntimeApiResponse]`
- Unknown operations rejected with `UNSUPPORTED_OPERATION`
- Optional aliases for backward compatibility
- Ordered middleware execution
- Mandatory context
- No arbitrary dynamic execution

## Middleware

Protocol `AgentRuntimeApiMiddleware` with ordered `AgentRuntimeApiMiddlewareChain`:

| Middleware | Purpose |
|---|---|
| `RequestIdMiddleware` | Ensures request_id is always present |
| `AuthenticationContextMiddleware` | Validates auth context |
| `PermissionMiddleware` | Permission check before execution |
| `ValidationMiddleware` | Request payload validation |
| `RedactionMiddleware` | Redacts sensitive fields from response |
| `AuditMiddleware` | Logs audit records for mutable operations |
| `MetricsMiddleware` | Records latency and counter metrics |
| `ErrorMappingMiddleware` | Converts exceptions to structured error responses |

### Rules

- Deterministic middleware order
- Permissions checked before execution
- Redaction before response return
- Errors mapped to structured responses
- No middleware can bypass authorization
- No chain-of-thought storage

## Adapters

Seven resource adapters translating between public contracts and internal components:

| Adapter | Internal Component |
|---|---|
| `GoalApiAdapter` | GoalManager / GoalRepository |
| `AgentRunApiAdapter` | GoalManager (run lifecycle) |
| `ApprovalApiAdapter` | ApprovalService |
| `BudgetApiAdapter` | ActionBudgetService |
| `TraceApiAdapter` | AgentTraceService (Phase 9.19) |
| `RuntimeEventApiAdapter` | RuntimeEventBus (Phase 9.20) |
| `RuntimeSystemApiAdapter` | System health/stats aggregation |

Each adapter:
- Translates public request → internal contract
- Calls existing domain component
- Translates internal result → public response
- Maps errors to `AgentRuntimeApiError`
- Respects permissions
- Never exposes mutable internal objects
- Is unaware of UI/transport layer

## Service / Facade

`AgentRuntimeApiService` exposes:

- `execute(request, context)` — single operation
- `execute_many(requests, context)` — batch (ordered, isolated failures)
- `health()` — system health
- `stats()` — aggregated statistics

Delegates to adapters; never duplicates domain logic.

## Permissions

`AgentRuntimeApiPermissions` with boolean flags per resource kind. Enforced in `PermissionMiddleware` before any adapter call. Sensitive operations require explicit permission grants.

## Idempotency

`AgentRuntimeApiIdempotencyStore` and `InMemoryAgentRuntimeApiIdempotencyStore`:

- `idempotency_key + same payload → same result` (replay protection)
- `idempotency_key + different payload → CONFLICT`
- Deterministic fingerprint via SHA-256
- Configurable TTL expiration
- Thread-safe storage

## Error Handling

Hierarchical exception classes:

```
AgentRuntimeApiException
├── AgentRuntimeApiContractError        — Contract violation
├── AgentRuntimeApiValidationError      — Invalid input
├── AgentRuntimeApiNotFoundError        — Resource not found
├── AgentRuntimeApiConflictError        — State/version conflict
├── AgentRuntimeApiPermissionError      — Unauthorized access
├── AgentRuntimeApiPolicyDeniedError    — Policy rejection
├── AgentRuntimeApiApprovalRequiredError— Approval needed
├── AgentRuntimeApiBudgetExceededError  — Budget limit hit
├── AgentRuntimeApiStateError           — Invalid state transition
├── AgentRuntimeApiSerializationError   — Serialization failure
├── AgentRuntimeApiUnsupportedOperationError — Unknown op
└── AgentRuntimeApiInternalError        — Internal failure (no stack leak)
```

### Rules

- Internal errors never leak stack traces, secrets, or sensitive details
- All errors map to structured `AgentRuntimeApiResponse` with code, message, details
- `ErrorMappingMiddleware` converts unhandled exceptions to safe error responses

## Pagination

`AgentRuntimeApiPage` supports:

- `limit` (1–500)
- `cursor` (opaque string)
- `offset` (when repository supports)
- `sort_by`, `sort_direction`
- Filters: `status`, `ids`, `time_range`

Unknown filters are rejected or explicitly ignored based on strict mode.

## Health

`RuntimeHealthResponse` reports:

- Status (`healthy` / `degraded` / `unavailable`)
- Version string
- Managers availability (goal, autonomy, approval, budget)
- Repositories availability
- Event bus status (open/closed)
- Trace service availability
- Timestamp
- Non-sensitive warnings

## Stats

`RuntimeStatsResponse` reports:

- Goals by status count
- Runs by status count
- Pending approvals
- Budget consumption
- Trace counts
- Event counts
- Dead letter counts
- API errors
- Operations executed
- Accumulated / average latency (when available)

No invented data. Unavailable components indicated as such.

## Audit

Each mutable operation emits:

- `request_id`
- `actor`
- `operation`
- `resource`
- `status`
- `duration`
- `error_code` (if any)

Audit records are created via `AuditMiddleware`. No secrets or sensitive content is logged.

## Integration with Trace (Phase 9.19) and Event Bus (Phase 9.20)

- `TraceApiAdapter` reuses `AgentTraceService` from Phase 9.19 (get, list, verify, export)
- `RuntimeEventApiAdapter` reuses `RuntimeEventBus` from Phase 9.20 (publish, list, replay, dead letters)
- Each mutable API operation emits Phase 9.20 events (e.g., `goal.created`, `goal.paused`, `run.started`)
- Trace integrity is never faked as `VALID`; export supports JSON, JSONL, SUMMARY formats
- Events are append-only, traceably replayed, with no fake delivery status

## Security

- No chain-of-thought exposure
- No private prompts, passwords, tokens, API keys, bearer tokens, or private keys in responses
- No stack traces in API responses
- No mutable internal objects exposed
- No `eval`, `exec`, `subprocess`, `shell` in API code
- Permission bypass prevention in `PermissionMiddleware`
- Idempotency collision detection
- No silent event drops — dead letters are tracked and replayable

## Limits

- Pagination limit: 1–500 per page
- Idempotency key TTL: configurable (default 3600s)
- Request payload size: bounded by contract serialization
- Middleware chain: 8 default middlewares (ordered)
- Batch execution: preserves item order; failures isolated

## Usage Examples (Python)

### Single execution

```python
request = AgentRuntimeApiRequest(
    operation=AgentRuntimeApiOperation.GOAL_CREATE,
    payload={"title": "My Goal", "objective": "Achieve X"},
    context=AgentRuntimeApiContext(actor="agent-1"),
)
response = service.execute(request, context)
```

### Batch execution

```python
requests = [
    AgentRuntimeApiRequest(operation=..., payload=...),
    AgentRuntimeApiRequest(operation=..., payload=...),
]
responses = service.execute_many(requests, context)
```

### Health check

```python
health = service.health()
```

### Custom middleware

```python
class MyMiddleware(AgentRuntimeApiMiddleware):
    def process(self, request, context, next_handler):
        # pre-processing
        response = next_handler(request, context)
        # post-processing
        return response
```

## Future Adaptation

- **CLI**: Route `AgentRuntimeApiOperation` values directly to `execute()`
- **HTTP**: Wrap `execute()` in a Flask/FastAPI endpoint with JSON serialization
- **n8n**: Expose as custom node calling `execute()`
- **Agents**: Call `execute()` directly with agent-generated requests

## Hardening Notes (BLE001 cleanup + gap fixes)

Real gaps found while eliminating blind `except Exception` catches and expanding
the test suite to 150+ tests; all fixed in production, not papered over in tests:

- **Critical**: `AgentRuntimeApiMiddleware` declared a `before()` hook that
  `AgentRuntimeApiMiddlewareChain.execute()` never called (it calls `forward()`).
  Any middleware without its own `forward()` override (`ErrorMappingMiddleware`,
  `AuditMiddleware`, `RedactionMiddleware`) crashed every request through the
  default chain — i.e. every call through `AgentRuntimeApiService`. Renamed the
  hook to `forward()`.
- Adapters built `errors=[{"code": ..., "message": ...}]` (plain dicts) instead
  of `AgentRuntimeApiError` instances. `AuditMiddleware` accessing `e.code.value`
  on a dict raised `AttributeError` on any adapter-level error response. All
  adapters now go through a shared `_error()` helper.
- `AgentRuntimeApiService.execute_many` called `_handle_internal_error(req, exc)`
  against a one-argument method — a `TypeError` on any unexpected failure.
  `execute()` now always returns a response (idempotency conflicts and
  unexpected failures are converted, never raised) and `execute_many` is a
  simple order-preserving map over it.
- `AgentRuntimeApiInternalError` was constructed with `str(exc)`, i.e. the raw
  unexpected-exception text could reach the response message. Call sites now
  pass no message at all, relying on the fixed safe default.
- Audit/metrics failures previously ran unguarded in `after()`; a malformed
  request could turn a *successful* operation into a fake internal error.
  Both middlewares now catch their own failures, record them (typed, no
  raw exception text), and always return the real response.
- `RuntimeSystemApiAdapter.health()/stats()` reported every manager/repository/
  event bus/trace service as `"available"` unconditionally — none of them are
  actually wired by `AgentRuntimeApiService` today. Health now reflects only
  components explicitly registered via `set_component_wired(...)`.
- `TraceApiAdapter.verify()` unconditionally set `integrity_status = "valid"`.
  Records now form a hash chain (`append_record`); `verify()` recomputes it and
  reports `"tampered"` on mismatch. `export()` redacts sensitive keys from
  records before serializing, since the outer `RedactionMiddleware` cannot see
  inside an already-serialized JSON string.
- `RuntimeEventApiAdapter.publish()` accepted arbitrary `event_type` strings and
  always reported `delivery.status = "delivered"` with no real subscriber to
  confirm it. Event types are now validated against the Phase 9.20 registry,
  delivery is reported as `"recorded"` (honest for an unwired in-memory queue),
  duplicate `dedup_key`s are idempotent, and `replay_dead_letter` does a real
  lookup (`NOT_FOUND` instead of always claiming success).
- `AgentRunApiAdapter.start()` never checked the referenced goal; a run could be
  started against a missing, paused, or cancelled goal. It now takes an optional
  `goal_lookup` callback, wired to `GoalApiAdapter.lookup_status` in the service.
- `ApprovalApiAdapter` had no way to create a pending approval — and, by design,
  still doesn't expose one over the public API (no `approval.create` operation),
  so an external caller can never manufacture and then approve its own request.
  `request_approval()` is the internal seam for runtime flows; `_decide()` now
  also enforces expiry and an optional assigned-approver check.
- `GoalResponse` exposed the adapter's internal `context`/`constraints`/
  `success_criteria` containers by reference; mutating a response mutated
  server-side state. `_build_response` now deep-copies them.
- The default `AgentRuntimeApiRouter.dispatch()` had two parallel exception-handling
  branches (with/without middleware) built around a bare `except RuntimeError`
  that silently let every other exception type escape. It now always builds the
  middleware chain (even with zero middleware) so there is exactly one place
  (`AgentRuntimeApiMiddlewareChain.execute`) that converts unexpected handler
  exceptions into a safe `AgentRuntimeApiInternalError`.
- `AgentRuntimeApiErrorCode.IDEMPOTENCY_CONFLICT` was defined in the enum but
  never used: reusing an idempotency key with a different payload raised the
  generic `AgentRuntimeApiConflictError` (`code="CONFLICT"`), indistinguishable
  from a resource conflict. Added `AgentRuntimeApiIdempotencyConflictError`
  (`code="IDEMPOTENCY_CONFLICT"`) and wired it into `_check_idempotency`.
