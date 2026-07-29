# Agent Runtime Integration Design

## Scope

Phase 9.27 adds a composition root that coordinates the existing Agent Runtime
subsystems from goal validation through terminal closure. It does not replace
`AgentRun`, `AgentRuntimeLoop`, `AgentExecutionAdapter`, or any canonical domain
service, and it does not extend `AgentRuntimeApiService`.

## Architecture

`AgentRuntimeIntegrationService` owns orchestration only. Dependencies are
injected as public services or narrow protocols and all mutable integration
state is delegated to `AgentRuntimeIntegrationStore`. Actual operations are
always resolved through the canonical operation registry and executed through
`AgentExecutionAdapter`.

`IntegrationExecutionState` is a separate application-level state machine. It
maps to canonical `AgentRuntimeStatus` transitions without changing or aliasing
that enum. The integration layer records the relationship between execution,
request, goal, selected agent descriptor/version, canonical run, approvals,
budget reservations, operation results, checkpoints, delegations, trace, and
terminal result.

## Store

The public store protocol supports create, compare-and-update, lookup by
execution/request/run, pending approval management, compensation journaling,
terminal result persistence, pause/resume/cancel markers, delete, and clear.
The in-memory implementation has one instance-local re-entrant lock and no
module-level mutable state.

Indexes are maintained bidirectionally:

- `execution_id -> IntegrationExecutionRecord`
- `request_id -> execution_id`
- `run_id -> execution_id`
- `approval_id -> execution_id` for pending approvals only
- `state -> execution_ids`

Deleting or clearing a record removes every secondary index. Mutation validates
the expected current version/state and refuses inconsistent or stale indexes.
Terminal results are immutable and idempotently reusable only when identical.

## Contracts

All new value objects are frozen dataclasses with timezone-aware UTC timestamps,
immutable nested mappings, validated identifiers, safe round-trip serialization,
and recursive metadata sanitization. Secret-like keys and unsafe values are
rejected or redacted before persistence.

`IntegratedAgentExecutionRequest` identifies both `execution_id` and
`request_id`, the canonical goal ID, actor/owner, optional requested agent and
required capabilities, canonical operation requests or workflow reference,
permission/cognitive context, resources, sensitivity, autonomy, budget,
available approvals, deadline/timeout, delegation/recovery/observability policy,
trace lineage, and metadata.

`IntegratedAgentExecutionResult` is the immutable terminal or paused snapshot
containing canonical IDs and references, operation outcomes, validation,
memory/delegation/approval/budget/checkpoint/recovery details, events, trace,
metrics, audit references, errors/warnings, timestamps, and metadata.

## State Machine

The states are `created`, `validating`, `authorized`, `planning`,
`waiting_approval`, `scheduled`, `running`, `waiting`, `delegating`,
`recovering`, `completed`, `partially_completed`, `failed`, `cancelled`,
`denied`, `timed_out`, and `kill_switch_blocked`.

Transitions are declared as data and enforced by the store. Terminal states
have no outgoing transitions. Resume is valid only from approval/wait/recovery
states after revalidation. Cancellation is idempotent and may move any
non-terminal state to `cancelled`.

## Execution Flow

1. Validate the request and canonical goal before creating side effects.
2. Resolve a registered active agent and create it with the canonical factory.
3. Create exactly one canonical `AgentRun` through `AgentRuntimeLoop`.
4. Build canonical permission checks; deny, expiry, kill switch, and policy
   errors fail closed.
5. Resolve and validate every operation against the registry, capabilities, and
   allowlists.
6. Estimate/evaluate/reserve the canonical action budget before execution.
7. Persist real approval requests and pause; resume revalidates approval,
   permission, budget, deadline, and kill switch.
8. Acquire locks, checkpoint sensitive operations, and execute only through
   `AgentExecutionAdapter`.
9. Classify failures and call canonical recovery/checkpoint restoration services
   within retry limits.
10. Delegate only through `AgentDelegationService`, preserving restricted
    permissions and parent/child trace links.
11. Validate output and update memory only with valid output, policy permission,
    and provenance.
12. Record canonical events, spans, audit, metrics, and model invocation links.
13. Persist terminal state before publishing success, then release resources and
    close run/goal/trace idempotently.

## Integration Criticality

- Mandatory fail-closed: request/goal validation, registry/factory resolution,
  security, operation resolution, permissioned memory writes, terminal store
  persistence, and security audit persistence.
- Mandatory with compensation: run creation/update, budget reservations,
  approvals, locks, checkpoints, operation execution, delegation, recovery,
  goal updates, and trace closure.
- Best-effort with visible warning/audit: non-security lifecycle events,
  non-critical telemetry, derived metrics, and optional health snapshots.

No exception is silently ignored. Best-effort failures become warnings and an
attempted audit record; mandatory failures become structured integration errors.

## Atomicity and Compensation

Before each external mutation, the record is persisted in its current state.
After a successful mutation, an idempotent compensation entry is appended.
On failure, entries execute in reverse order and each outcome is persisted.
Compensations cover budget/lock release, approval cancellation, trace closure,
run cancellation/failure reconciliation, and safe checkpoint restoration.
Memory writes and success events occur only after valid results, preventing
compensation from pretending irreversible writes did not happen.

## Testing

Tests are written first and cover contract round-trips, every allowed/forbidden
state transition, store index consistency, idempotent/concurrent execute,
approval pause/resume, cancellation, failure injection and compensation,
recovery, terminal closure, and non-duplication of runs/events/reservations/
operations. End-to-end tests use existing in-memory implementations wherever
their public APIs are stable. Completeness tests verify exports, signatures,
failure classification, secret hygiene, no `xfail`, and compatibility with
phases 9.19-9.26.

## Deliberate Limits

There is no new scheduler implementation because the repository contains no
canonical execution scheduler. A narrow optional scheduling protocol may mark
work scheduled, while the default service executes synchronously through the
canonical adapter. No REST, CLI, provider, model router, distributed worker,
cloud, or tracing replacement is added.
