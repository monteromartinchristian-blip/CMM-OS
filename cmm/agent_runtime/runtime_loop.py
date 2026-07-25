"""Phase 9.12 – Agent Runtime Loop.

Orchestrates the autonomous agent execution cycle using an explicit, resumable, and idempotent state machine.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from threading import RLock
from typing import Any

from cmm.agent_runtime.contracts import AgentRun
from cmm.agent_runtime.enums import (
    AgentIterationStatus,
    AgentRuntimeStatus,
    RuntimeHealthStatus,
    RuntimeStep,
    RuntimeStepStatus,
)
from cmm.agent_runtime.errors import (
    GoalError,
    GoalNotFoundError,
    InvalidRuntimeContractError,
    RuntimeAlreadyTerminalError,
    RuntimeIdempotencyConflictError,
    RuntimeRepositoryConsistencyError,
    RuntimeResumeError,
    RuntimeStepHandlerNotFoundError,
)
from cmm.agent_runtime.runtime_handlers import (
    CheckDependenciesHandler,
    CompleteHandler,
    DecideHandler,
    EvaluateOutcomeHandler,
    EvaluatePoliciesHandler,
    ExecuteHandler,
    LoadGoalHandler,
    LoadKnowledgeHandler,
    ObserveHandler,
    PlanHandler,
    ReasonHandler,
    RecoverHandler,
    RequestApprovalHandler,
    ReserveBudgetHandler,
    ResolveInformationGapsHandler,
    RuntimeStepHandler,
    UpdateGoalHandler,
    UpdateKnowledgeHandler,
    ValidateGoalHandler,
    ValidateHandler,
)
from cmm.agent_runtime.runtime_lock_manager import RuntimeLockManager
from cmm.agent_runtime.runtime_loop_contracts import (
    AgentIteration,
    RuntimeCheckpoint,
    RuntimeHeartbeat,
    RuntimeResumeRequest,
    RuntimeStepContext,
    RuntimeStepResult,
    current_aware_iso,
)
from cmm.agent_runtime.runtime_repository import (
    AgentRuntimeRepository,
    InMemoryAgentRuntimeRepository,
)
from cmm.agent_runtime.runtime_state_machine import AgentRuntimeStateMachine


def _status_str(status: AgentRuntimeStatus | str) -> str:
    return status.value if hasattr(status, "value") else str(status)


class AgentRuntimeLoop:
    """Deterministic, persistent, resumable, and idempotent orchestrator for agent runs."""

    def __init__(
        self,
        repository: AgentRuntimeRepository | None = None,
        lock_manager: RuntimeLockManager | None = None,
        state_machine: AgentRuntimeStateMachine | None = None,
        step_handlers: Mapping[RuntimeStep | str, RuntimeStepHandler] | None = None,
        goal_repository: Any | None = None,
        policy_engine: Any | None = None,
        approval_service: Any | None = None,
        action_budget_service: Any | None = None,
    ) -> None:
        self._repository = repository or InMemoryAgentRuntimeRepository()
        self._lock_manager = lock_manager or RuntimeLockManager(self._repository)
        self._state_machine = state_machine or AgentRuntimeStateMachine()
        self._goal_repository = goal_repository
        self._policy_engine = policy_engine
        self._approval_service = approval_service
        self._action_budget_service = action_budget_service
        self._rlock = RLock()

        # Initialize default step handlers
        self._step_handlers: dict[str, RuntimeStepHandler] = {}
        defaults: dict[RuntimeStep, RuntimeStepHandler] = {
            RuntimeStep.LOAD_GOAL: LoadGoalHandler(),
            RuntimeStep.VALIDATE_GOAL: ValidateGoalHandler(),
            RuntimeStep.CHECK_DEPENDENCIES: CheckDependenciesHandler(),
            RuntimeStep.OBSERVE: ObserveHandler(),
            RuntimeStep.LOAD_KNOWLEDGE: LoadKnowledgeHandler(),
            RuntimeStep.REASON: ReasonHandler(),
            RuntimeStep.RESOLVE_INFORMATION_GAPS: ResolveInformationGapsHandler(),
            RuntimeStep.DECIDE: DecideHandler(),
            RuntimeStep.PLAN: PlanHandler(),
            RuntimeStep.EVALUATE_POLICIES: EvaluatePoliciesHandler(),
            RuntimeStep.REQUEST_APPROVAL: RequestApprovalHandler(),
            RuntimeStep.RESERVE_BUDGET: ReserveBudgetHandler(),
            RuntimeStep.EXECUTE: ExecuteHandler(),
            RuntimeStep.VALIDATE: ValidateHandler(),
            RuntimeStep.EVALUATE_OUTCOME: EvaluateOutcomeHandler(),
            RuntimeStep.UPDATE_GOAL: UpdateGoalHandler(),
            RuntimeStep.UPDATE_KNOWLEDGE: UpdateKnowledgeHandler(),
            RuntimeStep.RECOVER: RecoverHandler(),
            RuntimeStep.COMPLETE: CompleteHandler(),
        }
        for k, v in defaults.items():
            self._step_handlers[k.value] = v

        if step_handlers:
            for k, v in step_handlers.items():
                key_str = k.value if isinstance(k, RuntimeStep) else str(k)
                self._step_handlers[key_str] = v

        # Internal active runs lookup
        self._runs: dict[str, AgentRun] = {}

    def register_step_handler(
        self, step: RuntimeStep | str, handler: RuntimeStepHandler
    ) -> None:
        """Register or override a handler for a specific RuntimeStep."""
        key_str = step.value if isinstance(step, RuntimeStep) else str(step)
        self._step_handlers[key_str] = handler

    def register_run(self, run: AgentRun) -> None:
        """Register an existing AgentRun with the loop."""
        with self._rlock:
            self._runs[run.id] = run

    def get_run(self, agent_run_id: str) -> AgentRun | None:
        """Fetch AgentRun by ID."""
        with self._rlock:
            return self._runs.get(agent_run_id)

    # ── Operational Cycle Methods ──────────────────────────────────────────────

    def start(
        self,
        agent_run_id: str,
        agent_id: str = "agent-default",
        goal_id: str | None = None,
        autonomy_level: int = 4,
        idempotency_key: str | None = None,
        now: str | None = None,
    ) -> AgentRun:
        """Initialize and start an AgentRun."""
        with self._rlock:
            timestamp_str = now or current_aware_iso()
            dt_timestamp = datetime.fromisoformat(timestamp_str)

            # Handle Idempotency
            if idempotency_key:
                payload = f"start:{agent_run_id}:{agent_id}:{goal_id}:{autonomy_level}"
                payload_hash = hashlib.sha256(payload.encode()).hexdigest()
                existing = self._repository.get_idempotency_record(idempotency_key)
                if existing:
                    if existing["payload_hash"] == payload_hash:
                        return self._runs[agent_run_id]
                    raise RuntimeIdempotencyConflictError(
                        f"Idempotency key '{idempotency_key}' already used with conflicting payload."
                    )

            if agent_run_id in self._runs:
                run = self._runs[agent_run_id]
                if self._state_machine.is_terminal(run.status):
                    raise RuntimeAlreadyTerminalError(
                        f"AgentRun '{agent_run_id}' is already in terminal state '{_status_str(run.status)}'."
                    )
                return run

            # Acquire goal lock if goal_id provided
            if goal_id:
                self._lock_manager.acquire_goal_lock(
                    goal_id=goal_id,
                    owner_agent_run_id=agent_run_id,
                    idempotency_key=idempotency_key,
                    now=timestamp_str,
                )

            initial_run = AgentRun(
                id=agent_run_id,
                agent_id=agent_id,
                goal_id=goal_id or "goal-default",
                status=AgentRuntimeStatus.CREATED,
                autonomy_level=autonomy_level,
                current_iteration=1,
                started_at=dt_timestamp,
                updated_at=dt_timestamp,
            )
            self._runs[agent_run_id] = initial_run

            # Transition to INITIALIZING
            updated_run, transition = self._state_machine.transition(
                agent_run=initial_run,
                to_status=AgentRuntimeStatus.INITIALIZING,
                reason_codes=("runtime.started",),
                triggered_by="runtime",
                idempotency_key=idempotency_key,
                now=timestamp_str,
            )
            self._runs[agent_run_id] = updated_run
            self._repository.add_transition(transition)

            # Create Iteration 1
            iter_1 = AgentIteration(
                id=f"iter-{agent_run_id}-1",
                agent_run_id=agent_run_id,
                number=1,
                status=AgentIterationStatus.CREATED.value,
                started_at=timestamp_str,
            )
            self._repository.add_iteration(iter_1)

            # Create initial checkpoint with empty step (ready for first step)
            cp_1 = RuntimeCheckpoint(
                id=f"cp-{agent_run_id}-init",
                agent_run_id=agent_run_id,
                iteration_id=iter_1.id,
                runtime_status=AgentRuntimeStatus.INITIALIZING.value,
                step="",
                last_activity_at=timestamp_str,
                created_at=timestamp_str,
                state_version=1,
            )
            self._repository.add_checkpoint(cp_1)

            # Create Heartbeat
            exp_time = (dt_timestamp + timedelta(seconds=600)).isoformat()
            hb_1 = RuntimeHeartbeat(
                agent_run_id=agent_run_id,
                status=AgentRuntimeStatus.INITIALIZING.value,
                current_iteration=1,
                last_activity_at=timestamp_str,
                expires_at=exp_time,
                health=RuntimeHealthStatus.HEALTHY.value,
            )
            self._repository.save_heartbeat(hb_1)

            if idempotency_key:
                payload = f"start:{agent_run_id}:{agent_id}:{goal_id}:{autonomy_level}"
                payload_hash = hashlib.sha256(payload.encode()).hexdigest()
                self._repository.store_idempotency_record(
                    key=idempotency_key,
                    payload_hash=payload_hash,
                    result=updated_run.id,
                )

            return updated_run

    def step(
        self,
        agent_run_id: str,
        idempotency_key: str | None = None,
        now: str | None = None,
    ) -> RuntimeStepResult:
        """Execute a single operational step of the runtime cycle."""
        with self._rlock:
            timestamp_str = now or current_aware_iso()
            run = self._runs.get(agent_run_id)
            if not run:
                raise InvalidRuntimeContractError(
                    f"AgentRun '{agent_run_id}' is not registered."
                )

            st_val = _status_str(run.status)
            if self._state_machine.is_terminal(st_val):
                raise RuntimeAlreadyTerminalError(
                    f"Cannot execute step on terminal AgentRun '{agent_run_id}' (status={st_val})."
                )

            # Check idempotency
            if idempotency_key:
                payload = f"step:{agent_run_id}:{st_val}"
                payload_hash = hashlib.sha256(payload.encode()).hexdigest()
                rec = self._repository.get_idempotency_record(idempotency_key)
                if rec:
                    if rec["payload_hash"] == payload_hash:
                        raw_res = rec["result"]
                        return RuntimeStepResult.from_dict(raw_res)
                    raise RuntimeIdempotencyConflictError(
                        f"Idempotency key '{idempotency_key}' conflicts with previous execution payload."
                    )

            # Get latest checkpoint and iteration
            cp = self._repository.get_latest_checkpoint(agent_run_id)
            iterations = self._repository.list_iterations(agent_run_id)
            current_iter = iterations[-1] if iterations else None

            if not current_iter or current_iter.status in (
                "completed",
                "failed",
                "cancelled",
            ):
                num = (current_iter.number + 1) if current_iter else 1
                current_iter = AgentIteration(
                    id=f"iter-{agent_run_id}-{num}",
                    agent_run_id=agent_run_id,
                    number=num,
                    status=AgentIterationStatus.RUNNING.value,
                    started_at=timestamp_str,
                )
                self._repository.add_iteration(current_iter)

            # Map current status to step
            step_to_exec = self._determine_step(st_val, cp)
            step_key = (
                step_to_exec.value
                if isinstance(step_to_exec, RuntimeStep)
                else str(step_to_exec)
            )
            handler = self._step_handlers.get(step_key)
            if not handler:
                raise RuntimeStepHandlerNotFoundError(
                    f"No step handler registered for RuntimeStep '{step_key}'."
                )

            # Assemble context
            goal_obj = None
            steps_requiring_goal = {
                RuntimeStep.LOAD_GOAL.value,
                RuntimeStep.VALIDATE_GOAL.value,
                RuntimeStep.CHECK_DEPENDENCIES.value,
                RuntimeStep.UPDATE_GOAL.value,
            }

            if self._goal_repository is not None:
                if hasattr(self._goal_repository, "get_goal"):
                    try:
                        goal_obj = self._goal_repository.get_goal(run.goal_id)
                    except (GoalNotFoundError, GoalError):
                        if step_key in steps_requiring_goal:
                            raise
                        goal_obj = None
                    except Exception as exc:
                        raise RuntimeRepositoryConsistencyError(
                            f"Unexpected error retrieving goal '{run.goal_id}' from repository: {exc}"
                        ) from exc
                if goal_obj is None and step_key in steps_requiring_goal:
                    raise RuntimeRepositoryConsistencyError(
                        f"Goal '{run.goal_id}' was not found in goal repository for step '{step_key}'."
                    )
            else:
                if step_key in {
                    RuntimeStep.VALIDATE_GOAL.value,
                    RuntimeStep.CHECK_DEPENDENCIES.value,
                    RuntimeStep.UPDATE_GOAL.value,
                }:
                    raise RuntimeRepositoryConsistencyError(
                        f"Goal repository is required for step '{step_key}' but none is configured."
                    )

            locks = self._lock_manager.list_active(owner_agent_run_id=agent_run_id)
            context = RuntimeStepContext(
                agent_run=run,
                goal=goal_obj,
                iteration=current_iter,
                checkpoint=cp,
                current_step=step_to_exec,
                locks=locks,
                idempotency_key=idempotency_key,
                now=timestamp_str,
            )

            # Execute step handler
            result = handler.execute(context)

            # Perform state transition if next_status differs
            next_st_val = _status_str(result.next_status)
            if next_st_val != st_val:
                updated_run, transition = self._state_machine.transition(
                    agent_run=run,
                    to_status=next_st_val,
                    reason_codes=result.reason_codes,
                    iteration_id=current_iter.id,
                    triggered_by="runtime",
                    idempotency_key=idempotency_key,
                    now=timestamp_str,
                )
                self._runs[agent_run_id] = updated_run
                self._repository.add_transition(transition)
            else:
                updated_run = run

            # Update iteration status if completed/failed
            if result.status == RuntimeStepStatus.FAILED.value or not result.success:
                up_iter = AgentIteration(
                    id=current_iter.id,
                    agent_run_id=current_iter.agent_run_id,
                    number=current_iter.number,
                    status=AgentIterationStatus.FAILED.value,
                    started_at=current_iter.started_at,
                    completed_at=timestamp_str,
                    metadata=current_iter.metadata,
                )
                self._repository.update_iteration(up_iter)
            elif next_st_val in ("completed", AgentRuntimeStatus.COMPLETED.value):
                up_iter = AgentIteration(
                    id=current_iter.id,
                    agent_run_id=current_iter.agent_run_id,
                    number=current_iter.number,
                    status=AgentIterationStatus.COMPLETED.value,
                    started_at=current_iter.started_at,
                    completed_at=timestamp_str,
                    metadata=current_iter.metadata,
                )
                self._repository.update_iteration(up_iter)

            # Create Checkpoint
            new_state_ver = (cp.state_version + 1) if cp else 1
            new_cp = RuntimeCheckpoint(
                id=f"cp-{agent_run_id}-{new_state_ver}",
                agent_run_id=agent_run_id,
                iteration_id=current_iter.id,
                runtime_status=_status_str(updated_run.status),
                step=result.step,
                state_version=new_state_ver,
                last_activity_at=timestamp_str,
                created_at=timestamp_str,
                lock_ids=tuple(lk.id for lk in locks),
            )
            self._repository.add_checkpoint(new_cp)

            # Update Heartbeat
            self.heartbeat(agent_run_id=agent_run_id, now=timestamp_str)

            if idempotency_key:
                payload = f"step:{agent_run_id}:{st_val}"
                payload_hash = hashlib.sha256(payload.encode()).hexdigest()
                self._repository.store_idempotency_record(
                    key=idempotency_key,
                    payload_hash=payload_hash,
                    result=result.to_dict(),
                )

            return result

    def run_until_waiting(
        self,
        agent_run_id: str,
        max_steps: int,
        idempotency_key: str | None = None,
        now: str | None = None,
    ) -> tuple[AgentRun, tuple[RuntimeStepResult, ...]]:
        """Run step() iteratively until a waiting state, terminal state, or max_steps limit is reached."""
        if max_steps <= 0:
            raise InvalidRuntimeContractError(
                "max_steps must be a positive integer >= 1."
            )

        results: list[RuntimeStepResult] = []
        with self._rlock:
            timestamp_str = now or current_aware_iso()
            for i in range(max_steps):
                run = self._runs.get(agent_run_id)
                st_val = _status_str(run.status) if run else ""
                if (
                    not run
                    or self._state_machine.is_terminal(st_val)
                    or self._state_machine.is_waiting(st_val)
                    or st_val == "paused"
                ):
                    break

                step_key = (
                    f"{idempotency_key}:step-{i + 1}" if idempotency_key else None
                )
                res = self.step(
                    agent_run_id=agent_run_id,
                    idempotency_key=step_key,
                    now=timestamp_str,
                )
                results.append(res)

                # Stop conditions
                if res.requires_user or res.requires_approval or res.requires_resource:
                    break
                if not res.success or res.status in (
                    "failed",
                    RuntimeStepStatus.FAILED.value,
                ):
                    break
                next_st = _status_str(res.next_status)
                if (
                    self._state_machine.is_terminal(next_st)
                    or self._state_machine.is_waiting(next_st)
                    or next_st == "paused"
                ):
                    break

            final_run = self._runs[agent_run_id]
            return final_run, tuple(results)

    def pause(
        self,
        agent_run_id: str,
        reason_codes: Sequence[str] = (),
        now: str | None = None,
    ) -> AgentRun:
        """Pause an active AgentRun."""
        with self._rlock:
            timestamp_str = now or current_aware_iso()
            run = self._runs.get(agent_run_id)
            if not run:
                raise InvalidRuntimeContractError(
                    f"AgentRun '{agent_run_id}' not found."
                )
            st_val = _status_str(run.status)
            if self._state_machine.is_terminal(st_val):
                raise RuntimeAlreadyTerminalError(
                    f"Cannot pause terminal AgentRun '{agent_run_id}'."
                )

            updated_run, transition = self._state_machine.transition(
                agent_run=run,
                to_status=AgentRuntimeStatus.PAUSED,
                reason_codes=reason_codes or ("runtime.paused",),
                now=timestamp_str,
            )
            self._runs[agent_run_id] = updated_run
            self._repository.add_transition(transition)

            # Checkpoint & heartbeat
            cps = self._repository.list_checkpoints(agent_run_id)
            latest_cp = cps[-1] if cps else None
            state_ver = (latest_cp.state_version + 1) if latest_cp else 1
            iter_id = latest_cp.iteration_id if latest_cp else "iter-0"

            new_cp = RuntimeCheckpoint(
                id=f"cp-{agent_run_id}-pause-{state_ver}",
                agent_run_id=agent_run_id,
                iteration_id=iter_id,
                runtime_status=AgentRuntimeStatus.PAUSED.value,
                step=RuntimeStep.REASON.value,
                state_version=state_ver,
                last_activity_at=timestamp_str,
                created_at=timestamp_str,
            )
            self._repository.add_checkpoint(new_cp)
            self.heartbeat(agent_run_id, now=timestamp_str)
            return updated_run

    def resume(
        self,
        agent_run_id: str,
        checkpoint_id: str | None = None,
        request: RuntimeResumeRequest | None = None,
        now: str | None = None,
    ) -> AgentRun:
        """Resume a paused, waiting, or resumable AgentRun."""
        with self._rlock:
            timestamp_str = now or current_aware_iso()
            run = self._runs.get(agent_run_id)
            if not run:
                raise InvalidRuntimeContractError(
                    f"AgentRun '{agent_run_id}' not found."
                )

            st_val = _status_str(run.status)
            if not self._state_machine.is_resumable(st_val):
                raise RuntimeResumeError(
                    f"AgentRun '{agent_run_id}' in state '{st_val}' is not resumable."
                )

            target_cp = None
            if request:
                if request.agent_run_id != agent_run_id:
                    raise RuntimeResumeError(
                        f"Resume request agent_run_id '{request.agent_run_id}' mismatches target '{agent_run_id}'."
                    )
                target_cp = self._repository.get_checkpoint(request.checkpoint_id)
                if (
                    request.expected_state_version
                    and target_cp.state_version != request.expected_state_version
                ):
                    raise RuntimeResumeError(
                        f"Checkpoint version mismatch: expected {request.expected_state_version}, found {target_cp.state_version}."
                    )
            elif checkpoint_id:
                target_cp = self._repository.get_checkpoint(checkpoint_id)
                if target_cp.agent_run_id != agent_run_id:
                    raise RuntimeResumeError(
                        f"Checkpoint '{checkpoint_id}' does not belong to run '{agent_run_id}'."
                    )
            else:
                target_cp = self._repository.get_latest_checkpoint(agent_run_id)

            if not target_cp:
                raise RuntimeResumeError(
                    f"No valid checkpoint found to resume AgentRun '{agent_run_id}'."
                )

            # Determine next active status to transition into
            next_st = AgentRuntimeStatus.OBSERVING
            if st_val in (
                "waiting_for_user",
                AgentRuntimeStatus.WAITING_FOR_USER.value,
            ):
                next_st = AgentRuntimeStatus.REASONING
            elif st_val in (
                "waiting_for_approval",
                AgentRuntimeStatus.WAITING_FOR_APPROVAL.value,
            ):
                next_st = AgentRuntimeStatus.PLANNING
            elif st_val in (
                "waiting_for_resource",
                AgentRuntimeStatus.WAITING_FOR_RESOURCE.value,
            ) or st_val in ("blocked", AgentRuntimeStatus.BLOCKED.value):
                next_st = AgentRuntimeStatus.REASONING

            updated_run, transition = self._state_machine.transition(
                agent_run=run,
                to_status=next_st,
                reason_codes=("runtime.resumed",),
                iteration_id=target_cp.iteration_id,
                now=timestamp_str,
            )
            self._runs[agent_run_id] = updated_run
            self._repository.add_transition(transition)

            # Create resume checkpoint
            state_ver = target_cp.state_version + 1
            new_cp = RuntimeCheckpoint(
                id=f"cp-{agent_run_id}-resume-{state_ver}",
                agent_run_id=agent_run_id,
                iteration_id=target_cp.iteration_id,
                runtime_status=_status_str(updated_run.status),
                step=RuntimeStep.OBSERVE.value,
                state_version=state_ver,
                last_activity_at=timestamp_str,
                created_at=timestamp_str,
            )
            self._repository.add_checkpoint(new_cp)
            self.heartbeat(agent_run_id, now=timestamp_str)
            return updated_run

    def cancel(
        self,
        agent_run_id: str,
        reason_codes: Sequence[str] = (),
        now: str | None = None,
    ) -> AgentRun:
        """Cancel an AgentRun gracefully and release active locks."""
        with self._rlock:
            timestamp_str = now or current_aware_iso()
            run = self._runs.get(agent_run_id)
            if not run:
                raise InvalidRuntimeContractError(
                    f"AgentRun '{agent_run_id}' not found."
                )
            st_val = _status_str(run.status)
            if self._state_machine.is_terminal(st_val):
                return run

            updated_run, transition = self._state_machine.transition(
                agent_run=run,
                to_status=AgentRuntimeStatus.CANCELLED,
                reason_codes=reason_codes or ("runtime.cancelled",),
                now=timestamp_str,
            )
            self._runs[agent_run_id] = updated_run
            self._repository.add_transition(transition)

            # Release owned locks
            self._lock_manager.release_all_for_owner(
                owner_agent_run_id=agent_run_id, now=timestamp_str
            )
            self.heartbeat(agent_run_id, now=timestamp_str)
            return updated_run

    def abort(
        self,
        agent_run_id: str,
        reason_codes: Sequence[str] = (),
        now: str | None = None,
    ) -> AgentRun:
        """Abort an AgentRun immediately (failsafe termination) and release active locks."""
        with self._rlock:
            timestamp_str = now or current_aware_iso()
            run = self._runs.get(agent_run_id)
            if not run:
                raise InvalidRuntimeContractError(
                    f"AgentRun '{agent_run_id}' not found."
                )
            st_val = _status_str(run.status)
            if self._state_machine.is_terminal(st_val):
                return run

            updated_run, transition = self._state_machine.transition(
                agent_run=run,
                to_status=AgentRuntimeStatus.ABORTED,
                reason_codes=reason_codes or ("runtime.aborted", "runtime.failsafe"),
                now=timestamp_str,
            )
            self._runs[agent_run_id] = updated_run
            self._repository.add_transition(transition)

            self._lock_manager.release_all_for_owner(
                owner_agent_run_id=agent_run_id, now=timestamp_str
            )
            self.heartbeat(agent_run_id, now=timestamp_str)
            return updated_run

    def complete(
        self,
        agent_run_id: str,
        reason_codes: Sequence[str] = (),
        now: str | None = None,
    ) -> AgentRun:
        """Mark an AgentRun as successfully completed and release active locks."""
        with self._rlock:
            timestamp_str = now or current_aware_iso()
            run = self._runs.get(agent_run_id)
            if not run:
                raise InvalidRuntimeContractError(
                    f"AgentRun '{agent_run_id}' not found."
                )
            st_val = _status_str(run.status)
            if self._state_machine.is_terminal(st_val):
                if st_val == AgentRuntimeStatus.COMPLETED.value:
                    return run
                raise RuntimeAlreadyTerminalError(
                    f"Cannot complete run in terminal state '{st_val}'."
                )

            updated_run, transition = self._state_machine.transition(
                agent_run=run,
                to_status=AgentRuntimeStatus.COMPLETED,
                reason_codes=reason_codes or ("runtime.completed",),
                now=timestamp_str,
            )
            self._runs[agent_run_id] = updated_run
            self._repository.add_transition(transition)

            self._lock_manager.release_all_for_owner(
                owner_agent_run_id=agent_run_id, now=timestamp_str
            )
            self.heartbeat(agent_run_id, now=timestamp_str)
            return updated_run

    # ── Heartbeat and Abandonment Monitoring ───────────────────────────────────

    def heartbeat(
        self,
        agent_run_id: str,
        now: str | None = None,
    ) -> RuntimeHeartbeat:
        """Update or emit a heartbeat for an active AgentRun."""
        with self._rlock:
            timestamp_str = now or current_aware_iso()
            run = self._runs.get(agent_run_id)
            status_val = (
                _status_str(run.status) if run else AgentRuntimeStatus.CREATED.value
            )

            iterations = self._repository.list_iterations(agent_run_id)
            iter_num = iterations[-1].number if iterations else 0

            locks = self._lock_manager.list_active(owner_agent_run_id=agent_run_id)
            dt_now = datetime.fromisoformat(timestamp_str)
            exp_time = (dt_now + timedelta(seconds=600)).isoformat()

            hb = RuntimeHeartbeat(
                agent_run_id=agent_run_id,
                status=status_val,
                current_iteration=iter_num,
                current_lock_ids=tuple(lk.id for lk in locks),
                last_activity_at=timestamp_str,
                expires_at=exp_time,
                health=RuntimeHealthStatus.HEALTHY.value,
            )
            self._repository.save_heartbeat(hb)
            return hb

    def detect_abandoned(
        self,
        stalled_threshold_seconds: float = 300.0,
        abandoned_threshold_seconds: float = 900.0,
        now: str | None = None,
    ) -> tuple[RuntimeHeartbeat, ...]:
        """Detect active runs whose heartbeat is stalled or abandoned."""
        with self._rlock:
            timestamp_str = now or current_aware_iso()
            dt_now = datetime.fromisoformat(timestamp_str)
            heartbeats = self._repository.list_heartbeats()
            affected = []

            for hb in heartbeats:
                if self._state_machine.is_terminal(hb.status):
                    continue

                dt_last = datetime.fromisoformat(hb.last_activity_at)
                elapsed = (dt_now - dt_last).total_seconds()

                new_health = hb.health
                if elapsed >= abandoned_threshold_seconds:
                    new_health = RuntimeHealthStatus.ABANDONED.value
                elif elapsed >= stalled_threshold_seconds:
                    new_health = RuntimeHealthStatus.STALLED.value

                if new_health != hb.health:
                    updated_hb = RuntimeHeartbeat(
                        agent_run_id=hb.agent_run_id,
                        status=hb.status,
                        current_iteration=hb.current_iteration,
                        current_task_id=hb.current_task_id,
                        current_lock_ids=hb.current_lock_ids,
                        budget_id=hb.budget_id,
                        next_action=hb.next_action,
                        health=new_health,
                        last_activity_at=hb.last_activity_at,
                        expires_at=hb.expires_at,
                        metadata=hb.metadata,
                    )
                    self._repository.save_heartbeat(updated_hb)
                    affected.append(updated_hb)

            return tuple(affected)

    # ── Helper ────────────────────────────────────────────────────────────────

    def _determine_step(
        self, status: str | AgentRuntimeStatus, checkpoint: RuntimeCheckpoint | None
    ) -> RuntimeStep:
        st = _status_str(status)
        cp_step = checkpoint.step if checkpoint else None
        if isinstance(cp_step, RuntimeStep):
            cp_step = cp_step.value
        else:
            cp_step = str(cp_step) if cp_step else None

        if st in ("created", "initializing"):
            if cp_step == "load_goal":
                return RuntimeStep.VALIDATE_GOAL
            elif cp_step == "validate_goal":
                return RuntimeStep.CHECK_DEPENDENCIES
            return RuntimeStep.LOAD_GOAL

        elif st == "observing":
            return RuntimeStep.OBSERVE

        elif st == "reasoning":
            if cp_step == "observe":
                return RuntimeStep.LOAD_KNOWLEDGE
            elif cp_step == "load_knowledge":
                return RuntimeStep.REASON
            elif cp_step == "reason":
                return RuntimeStep.DECIDE
            return RuntimeStep.REASON

        elif st == "planning":
            if cp_step in (None, "", "reason", "decide", "observe", "load_goal"):
                return RuntimeStep.PLAN
            elif cp_step == "plan":
                return RuntimeStep.EVALUATE_POLICIES
            elif cp_step == "evaluate_policies":
                return RuntimeStep.REQUEST_APPROVAL
            elif cp_step == "request_approval":
                return RuntimeStep.RESERVE_BUDGET
            elif cp_step == "reserve_budget":
                return RuntimeStep.EXECUTE
            return RuntimeStep.PLAN

        elif st == "waiting_for_user" or st == "waiting_for_resource":
            return RuntimeStep.RESOLVE_INFORMATION_GAPS

        elif st == "waiting_for_approval":
            return RuntimeStep.REQUEST_APPROVAL

        elif st == "executing":
            return RuntimeStep.EXECUTE

        elif st == "validating":
            return RuntimeStep.VALIDATE

        elif st == "evaluating":
            if cp_step == "validate":
                return RuntimeStep.EVALUATE_OUTCOME
            elif cp_step == "evaluate_outcome":
                return RuntimeStep.UPDATE_GOAL
            elif cp_step == "update_goal":
                return RuntimeStep.UPDATE_KNOWLEDGE
            return RuntimeStep.EVALUATE_OUTCOME

        elif st == "recovering":
            return RuntimeStep.RECOVER

        elif st in ("paused", "blocked"):
            return RuntimeStep.REASON

        elif st == "completed":
            return RuntimeStep.COMPLETE

        return RuntimeStep.OBSERVE
