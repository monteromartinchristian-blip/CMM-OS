# Phase 9.28 — Integration with the Existing System

## Scope

Phase 9.28 wires `AgentRuntimeIntegrationService` (Phase 9.27) to the
Cognitive Layer adapter (9.5), the Workflow Planner adapter (9.7), and the
Validation Integration adapter (9.14). It does not introduce a new runtime,
planner, cognitive engine, validation system, workflow engine, or store. Every
new code path calls an existing canonical service through its existing public
API (`CognitiveRuntimeAdapter.analyze`, `WorkflowPlannerAdapter.plan`/
`replan`, `AgentValidationAdapter.validate`, `AgentValidationPolicyAdapter.
select_policy`).

## Composition root changes

`AgentRuntimeIntegrationService.__init__` gained four **optional**,
protocol-backed (duck-typed `Any | None`) dependencies:

- `cognitive_service` — expected to expose `.analyze(AgentCognitiveRequest)`
  (satisfied by `AgentCognitiveService` / `DefaultCognitiveRuntimeAdapter`).
- `planning_service` — expected to expose `.plan(...)`, `.replan(...)`,
  `.validate_plan(...)` (satisfied by `AgentPlanningService`).
- `validation_service` — expected to expose `.validate(AgentValidationRequest)`
  (satisfied by `AgentValidationAdapter`).
- `validation_policy_service` — expected to expose `.select_policy(...)`
  (satisfied by `AgentValidationPolicyAdapter`).

No new parallel state is kept by the service. All cognitive/plan/validation
outcomes are persisted through the **existing** generic bags already present
on `IntegrationExecutionRecord.metadata` and
`IntegratedAgentExecutionResult.metadata` / `.validation_results`
(`_save_snapshot` now also threads `record.metadata` into the final result's
`metadata` field and accepts a `validation_results` tuple). No new dataclass
fields were added to any Phase 9.27 contract.

One contract relaxation was required: `IntegratedAgentExecutionRequest`
previously rejected a request with neither `operations` nor `workflow`. That
combination now signals "produce operations via `planning_service` before
execution" and is accepted (still rejecting `operations` *and* `workflow`
together). `to_dict`/`from_dict` are unchanged, so existing serialized
payloads round-trip identically — this is an additive relaxation, not a
breaking change. `AgentRuntimeIntegrationService.validate()` still fails
closed with `AgentRuntimeIntegrationError` if neither is provided *and* no
`planning_service` is configured.

## Cognitive wiring

`_run_cognitive_analysis` builds `AgentCognitiveRequest` from `agent_run_id`
(the bound canonical run), `goal_id`, `actor_id`, `permission_context.
allowed_domains`, and stashes `request.resources`, `request.cognitive_context`,
`correlation_id`, and `causation_id` into `AgentCognitiveRequest.metadata`
(there is no lossless typed mapping from the integration layer's untyped
`resources: Mapping[str, Any]` to the Cognitive Layer's structured
`Resource` dataclass, so raw resources travel as an audit-visible metadata
hint rather than being fabricated into fake `Resource` objects — see
"Residual risks").

It is invoked only when either (a) the request carries no operations/workflow
(the planning-required path) or (b) `request.policy.metadata["require_cognitive"]`
is `True`. This keeps direct-execution requests (operations already present,
no cognitive required) byte-for-byte compatible with Phase 9.27 behavior —
zero calls to `cognitive_service` when it isn't needed.

`analyze()`'s `AgentCognitiveResult` is persisted into `record.metadata`:
`cognitive_result_id`, `cognitive_session_id`, `cognitive_trace_id`,
`cognitive_status`, `cognitive_decision`, `cognitive_confidence`, and gap/
question/contradiction counts. `EventType.COGNITIVE_ANALYSIS_COMPLETED` (plus
`QUESTION_CREATED`/`INFORMATION_GAP_DETECTED` when present) are published on
the existing Event Bus. A blocking result (`result.blocked`, or status
`WAITING_FOR_USER` / `WAITING_FOR_RESOURCE` / `INSUFFICIENT_INFORMATION` /
`BLOCKED` / `FAILED`) short-circuits the execution to a structured `FAILED`
terminal snapshot with `errors` populated from `result.errors` (or a
status-derived reason) — no further planning, validation, or operation
execution happens. A non-blocking warning is recorded on `obs.warnings` and
execution continues. If `require_cognitive` is `True` and no
`cognitive_service` is configured, `validate()` fails closed before any
side effect is created.

`resume()` on the cognitive adapter (session continuation) and knowledge
search / contradiction detection / confidence scoring are **not**
reimplemented here — they remain entirely inside the Cognitive Layer and its
adapter, exactly as Phase 9.5 built them.

## Planner wiring

`_resolve_operations` decides whether operations already exist
(`request.operations`), a workflow was supplied directly (`request.workflow`),
or a plan must be produced. In the last case, `_build_planning_request`
constructs `AgentPlanningRequest` (goal, run, objective, resolved
`cognitive_result_id`, permissions, autonomy, correlation/causation in
metadata) and calls `planning_service.plan(...)`, then
`planning_service.validate_plan(...)` using the canonical
`AgentWorkflowPlanValidator` (via the service facade — no ad hoc validation
logic added here). An invalid plan raises `AgentRuntimeIntegrationError`
(`MANDATORY_FAIL_CLOSED`) before any operation runs.

Plan ID, workflow ID, version, task/dependency/operation counts, checkpoint
IDs, and validation status are persisted into `record.metadata`;
`EventType.WORKFLOW_PLAN_CREATED` / `WORKFLOW_PLAN_VALIDATED` /
`WORKFLOW_PLAN_REJECTED` are published. `_operations_from_workflow_plan`
converts `AgentWorkflowOperation` entries into `AgentOperationRequest`
instances **in the order the plan's own tasks already declare** (the planner
already linearizes its dependency chain when building `AgentWorkflowTask.
dependency_ids`); the integration service does not recompute or store a
second DAG.

Reaching a fully planned goal does not, by itself, mark anything complete:
`AgentPlanningDecision.COMPLETE_WITHOUT_WORKFLOW` only changes the *plan's*
status (handled entirely inside `DefaultWorkflowPlannerAdapter.plan`); the
integration service still runs its own operation loop / validation / memory
gates before ever writing `COMPLETED`.

**Replan during recovery**: when an operation fails and the execution used a
plan (`record.metadata["plan_id"]` present), `_attempt_replan` builds
`AgentReplanningRequest(reason=WorkflowPlanChangeReason.OPERATION_FAILED,
failed_operation_id=...)` and calls `planning_service.replan(...)`. The new
plan's ID/version supersede the old one in `record.metadata`
(`previous_plan_id` retains the link), `EventType.WORKFLOW_PLAN_REPLANNED` is
published, and the (fresh) plan's operations are retried once. A
`replan_count` counter in `record.metadata`, capped at `1`, makes the loop
provably finite — a second failure after a replan fails the execution
outright rather than replanning again.

## Validation wiring

Two stages, both routed exclusively through `AgentValidationPolicyAdapter.
select_policy` (`_resolve_validation_requirements`) and
`AgentValidationAdapter.validate` (`_run_validation_stage`) — no direct Ruff,
pytest, or subprocess invocation anywhere in the composition root:

- **Pre-execution** (`AgentValidationStage.PRE_EXECUTION`), run once resolved
  `operations` are known, before the checkpoint/operation loop. A resolved
  policy whose `AgentValidationResult.decision` is not `CONTINUE` fails the
  execution closed (`FAILED`, no operations run).
- **Post-execution** (`AgentValidationStage.POST_EXECUTION`), run after every
  operation succeeds, before budget confirmation / delegation / memory write.
  A non-`CONTINUE` decision fails closed with no memory write and no
  `COMPLETED` result. When it passes and
  `request.policy.require_terminal_validation` is `True` (the existing 9.27
  policy field — no new field was needed), a `PRE_COMMIT`-stage validation is
  also run; `AgentValidationAdapter._execute_validation` already invokes the
  real `CommitGateEvaluator` for that stage, so the commit gate is exercised
  through its one canonical code path.

Every stage's `AgentValidationResult.to_dict()` (findings, decision, blocking
reasons) is appended to the final result's `validation_results` tuple, and
`EventType.VALIDATION_STARTED/COMPLETED/FAILED` are published. When either
`validation_service` or `validation_policy_service` is absent, or the policy
resolves no requirements for the operation, the stage is a no-op (`True`) —
Phase 9.27 executions that never configured validation keep working exactly
as before.

## Workflow lifecycle

`AgentRuntimeIntegrationService` still owns exactly one workflow/execution
lifecycle: `IntegrationExecutionState` (create → validate → authorize → plan
→ [wait approval] → run → complete/fail/cancel), delegated entirely to the
existing `AgentRuntimeIntegrationStore`. Phase 9.28 adds one new transition
edge to the *runtime path* (not the state machine, which already allowed it):
`WAITING_APPROVAL` now resumes into `PLANNING` (previously straight to
`RUNNING`), so an approval-gated execution that also needs planning/cognitive
analysis runs that pipeline exactly once, after approval, instead of skipping
it. `pause`/`resume`/`cancel` and blocked-task detection continue to use the
canonical `IntegrationExecutionState` transitions and
`ALLOWED_INTEGRATION_TRANSITIONS` table unchanged. No second workflow/state
system was created; the Workflow Planner's `AgentWorkflowPlan`/
`WorkflowPlanStatus` remain the sole source of truth for plan-level state,
referenced (by ID) from the integration record, never duplicated.

## Kernel boundary

There is no `kernel.py` module in this codebase. The runtime already shares
one set of cross-cutting contracts and this phase adds no alternative:

| Concern | Canonical source | Reused by 9.28 via |
| --- | --- | --- |
| IDs | `_identifier`/`_optional_identifier` validators, `uuid4`-based `generate_*_id()` factories per contract module | plan/replan/validation request IDs built with the same `f"{prefix}-{execution_id}"` convention already used for checkpoints/compensations |
| Actors | `actor_id`/`owner_actor_id` on `IntegratedAgentExecutionRequest` | passed through unchanged into `AgentCognitiveRequest.actor_id`, `AgentPlanningRequest.actor_id` |
| Permissions | `AgentPermissionContext` (9.25) | read (not re-derived) for cognitive `permissions`/planning `permissions` |
| Timestamps | `datetime.now(timezone.utc)` / `_now_iso()` helpers per contract module | `AgentRuntimeIntegrationService._now()` reused for all new record mutations |
| Correlation/causation | `correlation_id`/`causation_id` on `IntegratedAgentExecutionRequest` | threaded into cognitive/planning request metadata; already threaded into events |
| Structured errors | `AgentRuntimeIntegrationError(failure_mode=...)`, adapter-specific errors (`CognitiveAdapterExecutionError`, `PlannerExecutionError`, `ValidationAdapterError`, ...) | new fail-closed paths raise the existing `AgentRuntimeIntegrationError` with `IntegrationFailureMode.MANDATORY_FAIL_CLOSED`; adapter errors propagate un-wrapped |
| Cancellation | `AgentRuntimeIntegrationService.cancel()` + `IntegrationCompensation` journal | unchanged; new cognitive/plan/validation side effects have no compensations because they only *read* or persist metadata, they never mutate external state |
| Event Bus | `AgentRuntimeEventBus` + `AgentRuntimeEventFactory` + `EventType` | new `COGNITIVE_ANALYSIS_COMPLETED`, `WORKFLOW_PLAN_*`, `VALIDATION_*`, `RECOVERY_REPLAN_REQUESTED` events (already defined in `runtime_event_types.py`, unused before this phase) are now published via the existing `obs.event(...)` helper |
| Stores/repositories | `AgentRuntimeIntegrationStore`, `InMemoryWorkflowPlanStore` (inside `planning_service`), `AgentValidationRepository` (inside `validation_service`) | each subsystem keeps its own store; the integration service reads results and writes only its own record's `metadata` |

## Semantic Engine seam (optional)

No Semantic Engine dependency was added. The seam is
`AgentCognitiveRequest.knowledge_query: KnowledgeQuery | dict[str, Any] |
None` and `AgentCognitiveContext.combined_resources` (already defined in
9.5's contracts) — a future Semantic Engine can populate `knowledge_query`
or supply resources through the existing `cognitive_layer`/`knowledge_store`
constructor parameters of `DefaultCognitiveRuntimeAdapter` without any change
to `AgentRuntimeIntegrationService`. Phase 9.28 leaves both fields at their
defaults (`None` / `()`), i.e. it depends on Cognitive Layer only, never
directly on a semantic/knowledge subsystem.

## Future Domain Intelligence

No domain-specific runtime was added. `IntegratedAgentExecutionRequest.
cognitive_context: Mapping[str, Any]` and `.metadata: Mapping[str, Any]`
(existing, unchanged fields) are the contract-only extension seam: a future
domain-intelligence layer can populate `cognitive_context` (consumed
verbatim by `_run_cognitive_analysis` and handed to the Cognitive Layer) or
add policy hints under `policy.metadata` (already read for
`require_cognitive`) without `AgentRuntimeIntegrationService` importing or
instantiating any domain-specific code.

## Requirement matrix

| Roadmap requirement | Canonical subsystem | Adapter used | Wiring point | Test | Status |
| --- | --- | --- | --- | --- | --- |
| Cognitive `analyze()` invoked before planning | Cognitive Layer (9.5) | `CognitiveRuntimeAdapter.analyze` via `AgentCognitiveService` | `AgentRuntimeIntegrationService._run_cognitive_analysis` | `test_cognitive_analyze_real_result_persisted` | Done |
| Cognitive result persisted (id, session, trace, warnings, gaps, questions, contradictions, confidence) | Cognitive Layer (9.5) | `AgentCognitiveResult` | `_run_cognitive_analysis` → `record.metadata` / `result.metadata` | `test_cognitive_analyze_real_result_persisted` | Done |
| Cognitive gap/question blocks execution | Cognitive Layer (9.5) | `AgentCognitiveResult.blocked`/`status` | `_cognitive_blocks_execution` | `test_cognitive_blocking_gap_fails_closed`, `test_cognitive_blocking_question_fails_closed` | Done |
| Cognitive non-blocking warning surfaces, execution continues | Cognitive Layer (9.5) | `AgentCognitiveResult.warnings` | `_run_cognitive_analysis` → `obs.warnings` | `test_cognitive_non_blocking_warning_continues` | Done |
| Cognitive required by policy, fail-closed if absent | Cognitive Layer (9.5) | n/a (absence) | `_validate_cognitive_availability` | `test_cognitive_required_by_policy_fails_closed_when_absent` | Done |
| Direct execution when operations already present | Execution Engine (9.9/9.27) | `AgentExecutionAdapter` | `_resolve_operations` short-circuit | `test_direct_execution_without_cognitive_or_planner` | Done |
| Planning invoked when operations/workflow missing | Planner (9.7) | `AgentPlanningService.plan` | `_resolve_operations` | `test_planning_real_when_operations_missing` | Done |
| Invalid plan fails closed | Planner (9.7) | `AgentPlanningService.validate_plan` | `_resolve_operations` | `test_invalid_plan_fails_closed` | Done |
| Plan version preserved across replan | Planner (9.7) | `AgentWorkflowPlan.version`/`previous_version_id` | `_attempt_replan` | `test_workflow_version_preserved` | Done |
| Replan during recovery, bounded | Planner (9.7) | `AgentPlanningService.replan` | `_attempt_replan` | `test_replan_during_recovery` | Done |
| Pre-execution validation approved/rejected | Validation System (9.14) | `AgentValidationAdapter.validate` | `_run_pre_execution_validation` | `test_pre_validation_approved`, `test_pre_validation_rejected_blocks_execution` | Done |
| Post-execution validation approved/rejected, no memory write on failure | Validation System (9.14) | `AgentValidationAdapter.validate` | `_run_post_execution_validation` | `test_post_validation_approved_writes_memory`, `test_post_validation_rejected_no_memory_write` | Done |
| Commit gate denial blocks completion | Validation System (9.14) | `CommitGateEvaluator` (via `AgentValidationAdapter`) | `_run_post_execution_validation` (`PRE_COMMIT` stage) | `test_commit_gate_denied_blocks_completion` | Done |
| Validation findings persisted | Validation System (9.14) | `AgentValidationResult.findings` | `_save_snapshot(validation_results=...)` | `test_validation_findings_persisted` | Done |
| Cancellation propagated through new stages | Kernel / Execution Engine | `AgentRuntimeIntegrationService.cancel` | unchanged compensation journal | `test_cancellation_propagates_with_cognitive_and_planning` | Done |
| Correlation/causation preserved | Kernel | `IntegratedAgentExecutionRequest.correlation_id/causation_id` | threaded into cognitive/planning request metadata | `test_correlation_causation_preserved_across_services` | Done |
| Idempotency with Cognitive/Planner/Validation | Kernel / Workflow System | `AgentRuntimeIntegrationStore` idempotent `execute()` | existing `request_id` short-circuit | `test_idempotent_execute_does_not_reinvoke_services` | Done |
| Concurrent execute does not duplicate analysis/plan/validation | Kernel | `threading.RLock` in `AgentRuntimeIntegrationService` | existing lock + idempotency check | `test_concurrent_execute_does_not_duplicate_side_effects` | Done |
| Cognitive failure visible | Cognitive Layer (9.5) | adapter exception propagation | no swallowing in `_run_cognitive_analysis` | `test_cognitive_failure_is_visible` | Done |
| Planner failure visible | Planner (9.7) | adapter exception propagation | no swallowing in `_resolve_operations` | `test_planner_failure_is_visible` | Done |
| Validation failure visible | Validation System (9.14) | adapter exception propagation | no swallowing in `_run_validation_stage` | `test_validation_failure_is_visible` | Done |
| No duplicate runtime/planner/cognitive system | Kernel | n/a | single composition root, single store per subsystem | `test_no_duplicate_subsystems_created` | Done |
| Semantic Engine seam documented, optional | Cognitive Layer (9.5) | `AgentCognitiveRequest.knowledge_query` | not wired (seam only) | this document | Done (documented) |
| Future Domain Intelligence extension seam | Kernel | `cognitive_context`/`metadata` mappings | not wired (contract-only seam) | this document | Done (documented) |
| Full roadmap → test matrix | — | — | — | `test_roadmap_matrix_is_complete` (completeness suite) | Done |

## Residual risks

- Cognitive blocking (`ASK_USER`, `LOAD_RESOURCE`, `ESCALATE`, `PAUSE`, ...)
  is surfaced as a structured `FAILED` terminal result rather than a
  resumable "waiting for human input" pause state. Building a genuine
  resumable pause (mirroring `WAITING_APPROVAL`) for cognitive gaps was out
  of scope for this phase; the roadmap explicitly allows either "paused
  state or structured failure."
- `_run_cognitive_analysis` cannot losslessly translate
  `IntegratedAgentExecutionRequest.resources` (untyped `Mapping[str, Any]`)
  into the Cognitive Layer's typed `Resource` objects, so raw resources are
  passed as metadata context rather than as `AgentCognitiveRequest.resources`.
  A future phase that wants typed resource resolution should extend the
  caller (not this composition root) to supply pre-built `Resource` objects.
- Replan-on-failure re-executes the *entire* freshly replanned operation
  list rather than resuming from the failed step; the execution's
  `operation_results`/audit trail therefore contains both the original
  (partial, failed) attempt and the full replanned attempt. This is bounded
  (one replan) and fully auditable, but is not a minimal-diff resume.
