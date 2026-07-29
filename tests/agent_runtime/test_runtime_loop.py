"""Phase 9.12 – Comprehensive Unit Test Suite for Agent Runtime Loop.

Tests contracts, state machine, repository, lock manager, step handlers,
heartbeat, abandonment detection, pause/resume, cancel/abort/complete,
idempotency, and system integrations (>75 tests).
"""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timedelta, timezone

import pytest

from cmm.agent_runtime import (
    AgentIteration,
    AgentIterationNotFoundError,
    AgentIterationStatus,
    AgentRun,
    AgentRuntimeLoop,
    AgentRuntimeStateMachine,
    AgentRuntimeStatus,
    DuplicateAgentIterationError,
    DuplicateRuntimeCheckpointError,
    DuplicateRuntimeLockError,
    DuplicateRuntimeTransitionError,
    GoalNotFoundError,
    InMemoryAgentRuntimeRepository,
    InvalidRuntimeContractError,
    RuntimeAlreadyTerminalError,
    RuntimeCheckpoint,
    RuntimeCheckpointNotFoundError,
    RuntimeHeartbeat,
    RuntimeIdempotencyConflictError,
    RuntimeLock,
    RuntimeLockConflictError,
    RuntimeLockManager,
    RuntimeLockNotFoundError,
    RuntimeRepositoryConsistencyError,
    RuntimeResumeError,
    RuntimeResumeRequest,
    RuntimeStep,
    RuntimeStepContext,
    RuntimeStepExecutionError,
    RuntimeStepHandlerNotFoundError,
    RuntimeStepResult,
    RuntimeStepStatus,
    RuntimeTransition,
    RuntimeTransitionNotAllowedError,
)
from cmm.agent_runtime.runtime_handlers import LoadGoalHandler


def _utc_now_iso(offset_seconds: int = 0) -> str:
    dt = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    return dt.isoformat()


def _utc_now_dt(offset_seconds: int = 0) -> datetime:
    return datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)


# ── 1. Contracts Tests (15 tests) ──────────────────────────────────────────────


class TestRuntimeLoopContracts:
    def test_agent_iteration_valid_and_to_from_dict(self):
        now = _utc_now_iso()
        iter_obj = AgentIteration(
            id="iter-1",
            agent_run_id="run-1",
            number=1,
            status=AgentIterationStatus.RUNNING,
            started_at=now,
            metadata={"key": "val"},
        )
        assert iter_obj.id == "iter-1"
        assert iter_obj.number == 1
        assert iter_obj.status == "running"

        d = iter_obj.to_dict()
        restored = AgentIteration.from_dict(d)
        assert restored.id == iter_obj.id
        assert restored.number == iter_obj.number
        assert restored.started_at == iter_obj.started_at
        assert restored.metadata["key"] == "val"

    def test_agent_iteration_invalid_id(self):
        now = _utc_now_iso()
        with pytest.raises(InvalidRuntimeContractError):
            AgentIteration(
                id="", agent_run_id="run-1", number=1, status="running", started_at=now
            )

    def test_agent_iteration_invalid_run_id(self):
        now = _utc_now_iso()
        with pytest.raises(InvalidRuntimeContractError):
            AgentIteration(
                id="iter-1",
                agent_run_id="   ",
                number=1,
                status="running",
                started_at=now,
            )

    def test_agent_iteration_invalid_number(self):
        now = _utc_now_iso()
        with pytest.raises(InvalidRuntimeContractError):
            AgentIteration(
                id="iter-1",
                agent_run_id="run-1",
                number=0,
                status="running",
                started_at=now,
            )

    def test_agent_iteration_invalid_timestamp(self):
        with pytest.raises(InvalidRuntimeContractError):
            AgentIteration(
                id="iter-1",
                agent_run_id="run-1",
                number=1,
                status="running",
                started_at="naive-date-str",
            )

    def test_runtime_checkpoint_valid_and_serialization(self):
        now = _utc_now_iso()
        cp = RuntimeCheckpoint(
            id="cp-1",
            agent_run_id="run-1",
            iteration_id="iter-1",
            runtime_status=AgentRuntimeStatus.OBSERVING,
            step=RuntimeStep.OBSERVE,
            last_activity_at=now,
            created_at=now,
            state_version=2,
            approval_request_ids=["app-1"],
        )
        assert cp.state_version == 2
        assert isinstance(cp.approval_request_ids, tuple)
        assert cp.approval_request_ids == ("app-1",)

        d = cp.to_dict()
        assert isinstance(d["approval_request_ids"], list)
        restored = RuntimeCheckpoint.from_dict(d)
        assert restored == cp

    def test_runtime_checkpoint_empty_id_raises(self):
        now = _utc_now_iso()
        with pytest.raises(InvalidRuntimeContractError):
            RuntimeCheckpoint(
                id="",
                agent_run_id="r1",
                iteration_id="i1",
                runtime_status="observing",
                step="observe",
                last_activity_at=now,
                created_at=now,
            )

    def test_runtime_checkpoint_invalid_state_version_raises(self):
        now = _utc_now_iso()
        with pytest.raises(InvalidRuntimeContractError):
            RuntimeCheckpoint(
                id="cp1",
                agent_run_id="r1",
                iteration_id="i1",
                runtime_status="observing",
                step="observe",
                state_version=0,
                last_activity_at=now,
                created_at=now,
            )

    def test_runtime_transition_serialization(self):
        now = _utc_now_iso()
        t = RuntimeTransition(
            id="trans-1",
            agent_run_id="run-1",
            from_status=AgentRuntimeStatus.CREATED,
            to_status=AgentRuntimeStatus.INITIALIZING,
            created_at=now,
            reason_codes=["runtime.started"],
        )
        assert t.from_status == "created"
        assert t.to_status == "initializing"
        assert t.reason_codes == ("runtime.started",)

        d = t.to_dict()
        restored = RuntimeTransition.from_dict(d)
        assert restored == t

    def test_runtime_transition_invalid_status_raises(self):
        now = _utc_now_iso()
        with pytest.raises(InvalidRuntimeContractError):
            RuntimeTransition(
                id="t1",
                agent_run_id="r1",
                from_status="",
                to_status="observing",
                created_at=now,
            )

    def test_runtime_step_result_contract(self):
        now = _utc_now_iso()
        res = RuntimeStepResult(
            agent_run_id="run-1",
            iteration_id="iter-1",
            step=RuntimeStep.OBSERVE,
            created_at=now,
            produced_ids=["obs-100"],
        )
        assert res.success is True
        assert res.produced_ids == ("obs-100",)
        res_d = res.to_dict()
        assert RuntimeStepResult.from_dict(res_d) == res

    def test_runtime_heartbeat_contract(self):
        now = _utc_now_iso()
        exp = _utc_now_iso(300)
        hb = RuntimeHeartbeat(
            agent_run_id="run-1",
            status=AgentRuntimeStatus.EXECUTING,
            last_activity_at=now,
            expires_at=exp,
        )
        assert hb.health == "healthy"
        assert RuntimeHeartbeat.from_dict(hb.to_dict()) == hb

    def test_runtime_lock_contract(self):
        now = _utc_now_iso()
        exp = _utc_now_iso(300)
        lk = RuntimeLock(
            id="lock-1",
            resource_key="goal:g1",
            owner_agent_run_id="run-1",
            acquired_at=now,
            expires_at=exp,
        )
        assert lk.lock_type == "exclusive"
        assert RuntimeLock.from_dict(lk.to_dict()) == lk

    def test_runtime_resume_request_contract(self):
        now = _utc_now_iso()
        req = RuntimeResumeRequest(
            agent_run_id="run-1",
            checkpoint_id="cp-1",
            created_at=now,
        )
        assert req.requested_by == "actor-user"
        assert RuntimeResumeRequest.from_dict(req.to_dict()) == req

    def test_runtime_step_context_immutability(self):
        now_dt = _utc_now_dt()
        now_iso = now_dt.isoformat()
        run = AgentRun(
            id="run-1",
            agent_id="agent-1",
            goal_id="goal-1",
            status=AgentRuntimeStatus.INITIALIZING,
            autonomy_level=4,
            current_iteration=1,
            started_at=now_dt,
            updated_at=now_dt,
        )
        ctx = RuntimeStepContext(
            agent_run=run,
            now=now_iso,
            current_step=RuntimeStep.OBSERVE,
            policy_results=["res1"],
        )
        from dataclasses import FrozenInstanceError

        assert ctx.policy_results == ("res1",)
        with pytest.raises(FrozenInstanceError):
            ctx.current_step = RuntimeStep.REASON


# ── 2. State Machine Tests (15 tests) ─────────────────────────────────────────


class TestAgentRuntimeStateMachine:
    def test_valid_transitions_created(self):
        sm = AgentRuntimeStateMachine()
        assert sm.can_transition("created", "initializing")
        assert sm.can_transition("created", "cancelled")
        assert sm.can_transition("created", "failed")
        assert sm.can_transition("created", "aborted")

    def test_valid_transitions_initializing(self):
        sm = AgentRuntimeStateMachine()
        assert sm.can_transition("initializing", "observing")
        assert sm.can_transition("initializing", "paused")

    def test_valid_transitions_observing(self):
        sm = AgentRuntimeStateMachine()
        assert sm.can_transition("observing", "reasoning")

    def test_valid_transitions_reasoning(self):
        sm = AgentRuntimeStateMachine()
        assert sm.can_transition("reasoning", "planning")
        assert sm.can_transition("reasoning", "waiting_for_user")
        assert sm.can_transition("reasoning", "waiting_for_resource")
        assert sm.can_transition("reasoning", "completed")
        assert sm.can_transition("reasoning", "blocked")

    def test_valid_transitions_planning(self):
        sm = AgentRuntimeStateMachine()
        assert sm.can_transition("planning", "waiting_for_approval")
        assert sm.can_transition("planning", "executing")
        assert sm.can_transition("planning", "blocked")

    def test_valid_transitions_executing_validating_evaluating(self):
        sm = AgentRuntimeStateMachine()
        assert sm.can_transition("executing", "validating")
        assert sm.can_transition("validating", "evaluating")
        assert sm.can_transition("evaluating", "completed")
        assert sm.can_transition("evaluating", "observing")

    def test_invalid_transition_created_to_executing(self):
        sm = AgentRuntimeStateMachine()
        with pytest.raises(RuntimeTransitionNotAllowedError):
            sm.validate_transition("created", "executing")

    def test_invalid_transition_terminal_to_any(self):
        sm = AgentRuntimeStateMachine()
        with pytest.raises(RuntimeTransitionNotAllowedError):
            sm.validate_transition("completed", "reasoning")
        with pytest.raises(RuntimeTransitionNotAllowedError):
            sm.validate_transition("failed", "observing")

    def test_no_op_transition_allowed(self):
        sm = AgentRuntimeStateMachine()
        assert sm.can_transition("observing", "observing")
        sm.validate_transition("reasoning", "reasoning")

    def test_is_terminal_predicates(self):
        sm = AgentRuntimeStateMachine()
        for st in ("completed", "cancelled", "failed", "aborted"):
            assert sm.is_terminal(st) is True
        assert sm.is_terminal("executing") is False

    def test_is_waiting_predicates(self):
        sm = AgentRuntimeStateMachine()
        for st in ("waiting_for_user", "waiting_for_resource", "waiting_for_approval"):
            assert sm.is_waiting(st) is True
        assert sm.is_waiting("reasoning") is False

    def test_is_resumable_predicates(self):
        sm = AgentRuntimeStateMachine()
        for st in (
            "paused",
            "waiting_for_user",
            "waiting_for_resource",
            "waiting_for_approval",
            "blocked",
            "recovering",
        ):
            assert sm.is_resumable(st) is True
        assert sm.is_resumable("completed") is False

    def test_is_active_predicates(self):
        sm = AgentRuntimeStateMachine()
        for st in (
            "initializing",
            "observing",
            "reasoning",
            "planning",
            "executing",
            "validating",
            "evaluating",
            "recovering",
        ):
            assert sm.is_active(st) is True
        assert sm.is_active("paused") is False

    def test_allowed_next_states(self):
        sm = AgentRuntimeStateMachine()
        allowed = sm.allowed_next_states("initializing")
        assert "observing" in allowed
        assert "paused" in allowed

    def test_transition_execution(self):
        now_dt = _utc_now_dt()
        now_iso = now_dt.isoformat()
        run = AgentRun(
            id="run-1",
            agent_id="agent-1",
            goal_id="goal-1",
            status=AgentRuntimeStatus.CREATED,
            autonomy_level=4,
            current_iteration=1,
            started_at=now_dt,
            updated_at=now_dt,
        )
        up_run, trans = AgentRuntimeStateMachine.transition(
            agent_run=run,
            to_status=AgentRuntimeStatus.INITIALIZING,
            reason_codes=["runtime.started"],
            now=now_iso,
        )
        assert up_run.status == AgentRuntimeStatus.INITIALIZING
        assert trans.from_status == "created"
        assert trans.to_status == "initializing"


# ── 3. Repository Tests (10 tests) ───────────────────────────────────────────


class TestInMemoryAgentRuntimeRepository:
    def test_iteration_crud_and_duplicates(self):
        repo = InMemoryAgentRuntimeRepository()
        now = _utc_now_iso()
        it = AgentIteration(
            id="i1", agent_run_id="r1", number=1, status="running", started_at=now
        )

        repo.add_iteration(it)
        assert repo.get_iteration("i1") == it

        with pytest.raises(DuplicateAgentIterationError):
            repo.add_iteration(it)

        up_it = AgentIteration(
            id="i1", agent_run_id="r1", number=1, status="completed", started_at=now
        )
        repo.update_iteration(up_it)
        assert repo.get_iteration("i1").status == "completed"

        with pytest.raises(AgentIterationNotFoundError):
            repo.get_iteration("non-existent")

    def test_update_non_existent_iteration_raises(self):
        repo = InMemoryAgentRuntimeRepository()
        now = _utc_now_iso()
        it = AgentIteration(
            id="i999", agent_run_id="r1", number=1, status="running", started_at=now
        )
        with pytest.raises(AgentIterationNotFoundError):
            repo.update_iteration(it)

    def test_checkpoint_crud_and_latest(self):
        repo = InMemoryAgentRuntimeRepository()
        now1 = _utc_now_iso(0)
        now2 = _utc_now_iso(10)

        cp1 = RuntimeCheckpoint(
            id="cp1",
            agent_run_id="r1",
            iteration_id="i1",
            runtime_status="initializing",
            step="load_goal",
            state_version=1,
            last_activity_at=now1,
            created_at=now1,
        )
        cp2 = RuntimeCheckpoint(
            id="cp2",
            agent_run_id="r1",
            iteration_id="i1",
            runtime_status="observing",
            step="observe",
            state_version=2,
            last_activity_at=now2,
            created_at=now2,
        )

        repo.add_checkpoint(cp1)
        repo.add_checkpoint(cp2)

        with pytest.raises(DuplicateRuntimeCheckpointError):
            repo.add_checkpoint(cp1)

        assert repo.get_checkpoint("cp1") == cp1
        latest = repo.get_latest_checkpoint("r1")
        assert latest == cp2
        assert repo.get_latest_checkpoint("unknown-run") is None

    def test_get_non_existent_checkpoint_raises(self):
        repo = InMemoryAgentRuntimeRepository()
        with pytest.raises(RuntimeCheckpointNotFoundError):
            repo.get_checkpoint("cp999")

    def test_transition_crud_and_list_filter(self):
        repo = InMemoryAgentRuntimeRepository()
        now = _utc_now_iso()
        t1 = RuntimeTransition(
            id="t1",
            agent_run_id="r1",
            from_status="created",
            to_status="initializing",
            created_at=now,
        )
        t2 = RuntimeTransition(
            id="t2",
            agent_run_id="r2",
            from_status="created",
            to_status="initializing",
            created_at=now,
        )
        repo.add_transition(t1)
        repo.add_transition(t2)

        assert len(repo.list_transitions("r1")) == 1
        assert repo.get_transition("t1") == t1

        with pytest.raises(DuplicateRuntimeTransitionError):
            repo.add_transition(t1)

    def test_heartbeat_save_get_list(self):
        repo = InMemoryAgentRuntimeRepository()
        now = _utc_now_iso()
        hb = RuntimeHeartbeat(
            agent_run_id="r1",
            status="initializing",
            last_activity_at=now,
            expires_at=now,
        )
        repo.save_heartbeat(hb)
        assert repo.get_heartbeat("r1") == hb
        assert len(repo.list_heartbeats()) == 1

    def test_lock_crud_and_find_active(self):
        repo = InMemoryAgentRuntimeRepository()
        now = _utc_now_iso()
        lk = RuntimeLock(
            id="lk1",
            resource_key="res:1",
            owner_agent_run_id="r1",
            acquired_at=now,
            expires_at=now,
        )
        repo.add_lock(lk)
        assert repo.get_lock("lk1") == lk
        assert len(repo.find_active_locks("res:1")) == 1

        with pytest.raises(DuplicateRuntimeLockError):
            repo.add_lock(lk)

    def test_update_non_existent_lock_raises(self):
        repo = InMemoryAgentRuntimeRepository()
        now = _utc_now_iso()
        lk = RuntimeLock(
            id="lk999",
            resource_key="res:1",
            owner_agent_run_id="r1",
            acquired_at=now,
            expires_at=now,
        )
        with pytest.raises(RuntimeLockNotFoundError):
            repo.update_lock(lk)

    def test_idempotency_store_and_retrieve(self):
        repo = InMemoryAgentRuntimeRepository()
        repo.store_idempotency_record("k1", "hash123", {"result": "ok"})
        rec = repo.get_idempotency_record("k1")
        assert rec["payload_hash"] == "hash123"
        assert rec["result"] == {"result": "ok"}
        assert repo.get_idempotency_record("non-existent") is None

    def test_repository_thread_safety(self):
        repo = InMemoryAgentRuntimeRepository()
        now = _utc_now_iso()

        def add_iter(idx: int):
            it = AgentIteration(
                id=f"iter-{idx}",
                agent_run_id="r1",
                number=idx + 1,
                status="running",
                started_at=now,
            )
            repo.add_iteration(it)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(add_iter, i) for i in range(50)]
            concurrent.futures.wait(futures)

        assert len(repo.list_iterations("r1")) == 50


# ── 4. Lock Manager Tests (10 tests) ─────────────────────────────────────────


class TestRuntimeLockManager:
    def test_acquire_and_release_lock(self):
        repo = InMemoryAgentRuntimeRepository()
        lm = RuntimeLockManager(repo)
        now = _utc_now_iso()

        lk = lm.acquire("resource:1", owner_agent_run_id="run-1", now=now)
        assert lk.resource_key == "resource:1"
        assert lk.status == "active"

        released = lm.release(lk.id, owner_agent_run_id="run-1", now=now)
        assert released.status == "released"

    def test_release_unowned_lock_raises(self):
        repo = InMemoryAgentRuntimeRepository()
        lm = RuntimeLockManager(repo)
        now = _utc_now_iso()

        lk = lm.acquire("resource:1", owner_agent_run_id="run-1", now=now)
        with pytest.raises(RuntimeLockConflictError):
            lm.release(lk.id, owner_agent_run_id="run-2", now=now)

    def test_exclusive_lock_conflict(self):
        repo = InMemoryAgentRuntimeRepository()
        lm = RuntimeLockManager(repo)
        now = _utc_now_iso()

        lm.acquire("resource:1", owner_agent_run_id="run-1", now=now)
        with pytest.raises(RuntimeLockConflictError):
            lm.acquire("resource:1", owner_agent_run_id="run-2", now=now)

    def test_goal_lock_exclusive(self):
        repo = InMemoryAgentRuntimeRepository()
        lm = RuntimeLockManager(repo)
        now = _utc_now_iso()

        gl = lm.acquire_goal_lock(goal_id="g100", owner_agent_run_id="run-1", now=now)
        assert gl.resource_key == "goal:g100"

        with pytest.raises(RuntimeLockConflictError):
            lm.acquire_goal_lock(goal_id="g100", owner_agent_run_id="run-2", now=now)

    def test_lock_renewal_and_idempotency(self):
        repo = InMemoryAgentRuntimeRepository()
        lm = RuntimeLockManager(repo)
        now = _utc_now_iso()

        lk1 = lm.acquire(
            "res:1", owner_agent_run_id="run-1", idempotency_key="key-1", now=now
        )
        lk2 = lm.acquire(
            "res:1", owner_agent_run_id="run-1", idempotency_key="key-1", now=now
        )
        assert lk1.id == lk2.id

        renewed = lm.renew(lk1.id, owner_agent_run_id="run-1", ttl_seconds=600, now=now)
        assert renewed.id == lk1.id

    def test_renew_unowned_lock_raises(self):
        repo = InMemoryAgentRuntimeRepository()
        lm = RuntimeLockManager(repo)
        now = _utc_now_iso()

        lk = lm.acquire("res:1", owner_agent_run_id="run-1", now=now)
        with pytest.raises(RuntimeLockConflictError):
            lm.renew(lk.id, owner_agent_run_id="run-2", now=now)

    def test_lock_expiration(self):
        repo = InMemoryAgentRuntimeRepository()
        lm = RuntimeLockManager(repo)
        past_now = _utc_now_iso(-500)
        current_now = _utc_now_iso(0)

        lk = lm.acquire(
            "res:expired", owner_agent_run_id="run-1", ttl_seconds=60, now=past_now
        )
        expired = lm.expire_due(now=current_now)
        assert len(expired) == 1
        assert expired[0].id == lk.id
        assert expired[0].status == "expired"

    def test_release_all_for_owner(self):
        repo = InMemoryAgentRuntimeRepository()
        lm = RuntimeLockManager(repo)
        now = _utc_now_iso()

        lm.acquire("res:1", owner_agent_run_id="run-1", now=now)
        lm.acquire("res:2", owner_agent_run_id="run-1", now=now)
        released = lm.release_all_for_owner("run-1", now=now)
        assert len(released) == 2
        assert len(lm.list_active("run-1")) == 0

    def test_assert_available_free_vs_busy(self):
        repo = InMemoryAgentRuntimeRepository()
        lm = RuntimeLockManager(repo)
        now = _utc_now_iso()

        lm.assert_available("res:free", owner_agent_run_id="run-1", now=now)
        lm.acquire("res:busy", owner_agent_run_id="run-1", now=now)

        with pytest.raises(RuntimeLockConflictError):
            lm.assert_available("res:busy", owner_agent_run_id="run-2", now=now)

    def test_list_active_filters(self):
        repo = InMemoryAgentRuntimeRepository()
        lm = RuntimeLockManager(repo)
        now = _utc_now_iso()

        lm.acquire("res:1", owner_agent_run_id="run-1", now=now)
        lm.acquire("res:2", owner_agent_run_id="run-2", now=now)

        assert len(lm.list_active("run-1")) == 1
        assert len(lm.list_active()) == 2


# ── 5. Heartbeat & Abandonment Tests (5 tests) ───────────────────────────────


class TestRuntimeHeartbeatMonitoring:
    def test_heartbeat_save_and_update(self):
        loop = AgentRuntimeLoop()
        loop.start(agent_run_id="run-hb-1")
        hb = loop.heartbeat("run-hb-1")
        assert hb.agent_run_id == "run-hb-1"
        assert hb.health == "healthy"

    def test_detect_stalled_runs(self):
        repo = InMemoryAgentRuntimeRepository()
        loop = AgentRuntimeLoop(repository=repo)
        now = _utc_now_iso()
        stalled_time = _utc_now_iso(-400)

        hb_stalled = RuntimeHeartbeat(
            agent_run_id="run-stalled",
            status="executing",
            last_activity_at=stalled_time,
            expires_at=_utc_now_iso(300),
        )
        repo.save_heartbeat(hb_stalled)

        affected = loop.detect_abandoned(
            stalled_threshold_seconds=300,
            abandoned_threshold_seconds=900,
            now=now,
        )
        assert len(affected) == 1
        assert affected[0].health == "stalled"

    def test_detect_abandoned_runs(self):
        repo = InMemoryAgentRuntimeRepository()
        loop = AgentRuntimeLoop(repository=repo)
        now = _utc_now_iso()
        abandoned_time = _utc_now_iso(-1000)

        hb_abandoned = RuntimeHeartbeat(
            agent_run_id="run-abandoned",
            status="executing",
            last_activity_at=abandoned_time,
            expires_at=_utc_now_iso(300),
        )
        repo.save_heartbeat(hb_abandoned)

        affected = loop.detect_abandoned(
            stalled_threshold_seconds=300,
            abandoned_threshold_seconds=900,
            now=now,
        )
        assert len(affected) == 1
        assert affected[0].health == "abandoned"

    def test_detect_abandoned_ignores_terminal_runs(self):
        repo = InMemoryAgentRuntimeRepository()
        loop = AgentRuntimeLoop(repository=repo)
        now = _utc_now_iso()
        abandoned_time = _utc_now_iso(-1000)

        hb_completed = RuntimeHeartbeat(
            agent_run_id="run-comp",
            status="completed",
            last_activity_at=abandoned_time,
            expires_at=_utc_now_iso(300),
        )
        repo.save_heartbeat(hb_completed)

        affected = loop.detect_abandoned(now=now)
        assert len(affected) == 0

    def test_heartbeat_unregistered_run(self):
        loop = AgentRuntimeLoop()
        hb = loop.heartbeat("unknown-run")
        assert hb.agent_run_id == "unknown-run"
        assert hb.status == "created"


# ── 6. Core Runtime Loop Tests (15 tests) ─────────────────────────────────────


class TestAgentRuntimeLoopCore:
    def test_start_and_single_step(self):
        loop = AgentRuntimeLoop()
        run = loop.start(agent_run_id="run-core-1", goal_id="g1")
        assert run.status == AgentRuntimeStatus.INITIALIZING

        res = loop.step("run-core-1")
        assert res.step == "load_goal"
        assert res.success is True
        assert res.next_status == "initializing"

    def test_step_unregistered_run_raises(self):
        loop = AgentRuntimeLoop()
        with pytest.raises(InvalidRuntimeContractError):
            loop.step("unknown-run")

    def test_run_until_waiting_multi_steps(self):
        class MockGoalRepo:
            def get_goal(self, goal_id: str):
                class MockGoal:
                    def __init__(self, id: str):
                        self.id = id
                        self.status = "active"
                        self.dependencies = ()

                return MockGoal(goal_id)

        loop = AgentRuntimeLoop(goal_repository=MockGoalRepo())
        loop.start(agent_run_id="run-core-2", goal_id="g2")

        _run, results = loop.run_until_waiting("run-core-2", max_steps=5)
        assert len(results) >= 1

    def test_run_until_waiting_invalid_max_steps(self):
        loop = AgentRuntimeLoop()
        loop.start("run-max-0")
        with pytest.raises(InvalidRuntimeContractError):
            loop.run_until_waiting("run-max-0", max_steps=0)

    def test_pause_active_run(self):
        loop = AgentRuntimeLoop()
        loop.start("run-pause-1")
        loop.step("run-pause-1")

        paused_run = loop.pause("run-pause-1", reason_codes=["user_requested"])
        assert paused_run.status == AgentRuntimeStatus.PAUSED

    def test_pause_terminal_run_raises(self):
        loop = AgentRuntimeLoop()
        loop.start("run-pause-term")
        loop.cancel("run-pause-term")
        with pytest.raises(RuntimeAlreadyTerminalError):
            loop.pause("run-pause-term")

    def test_resume_paused_run(self):
        loop = AgentRuntimeLoop()
        loop.start("run-resume-1")
        loop.step("run-resume-1")
        loop.pause("run-resume-1")

        resumed_run = loop.resume("run-resume-1")
        assert resumed_run.status in (
            AgentRuntimeStatus.OBSERVING,
            AgentRuntimeStatus.REASONING,
            AgentRuntimeStatus.PLANNING,
        )

    def test_resume_non_resumable_run_raises(self):
        loop = AgentRuntimeLoop()
        loop.start("run-no-resume")
        with pytest.raises(RuntimeResumeError):
            loop.resume("run-no-resume")

    def test_resume_with_request_version_mismatch(self):
        loop = AgentRuntimeLoop()
        loop.start("run-resume-ver")
        loop.pause("run-resume-ver")

        req = RuntimeResumeRequest(
            agent_run_id="run-resume-ver",
            checkpoint_id="cp-run-resume-ver-init",
            expected_state_version=99,
            created_at=_utc_now_iso(),
        )
        with pytest.raises(RuntimeResumeError):
            loop.resume("run-resume-ver", request=req)

    def test_cancel_active_run(self):
        loop = AgentRuntimeLoop()
        loop.start("run-term-1")

        cancelled = loop.cancel("run-term-1")
        assert cancelled.status == AgentRuntimeStatus.CANCELLED
        with pytest.raises(RuntimeAlreadyTerminalError):
            loop.step("run-term-1")

    def test_abort_active_run(self):
        loop = AgentRuntimeLoop()
        loop.start("run-term-2")

        aborted = loop.abort("run-term-2")
        assert aborted.status == AgentRuntimeStatus.ABORTED

    def test_complete_active_run(self):
        loop = AgentRuntimeLoop()
        loop.start("run-term-3")

        r3 = loop.get_run("run-term-3")
        r3_obs, _ = AgentRuntimeStateMachine.transition(
            r3, AgentRuntimeStatus.OBSERVING
        )
        r3_reas, _ = AgentRuntimeStateMachine.transition(
            r3_obs, AgentRuntimeStatus.REASONING
        )
        loop.register_run(r3_reas)
        completed = loop.complete("run-term-3")
        assert completed.status == AgentRuntimeStatus.COMPLETED

    def test_complete_already_terminal_run_raises(self):
        loop = AgentRuntimeLoop()
        loop.start("run-term-err")
        loop.cancel("run-term-err")
        with pytest.raises(RuntimeAlreadyTerminalError):
            loop.complete("run-term-err")

    def test_custom_handler_registration(self):
        loop = AgentRuntimeLoop()

        class CustomReasonHandler:
            def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
                return RuntimeStepResult(
                    agent_run_id=context.agent_run.id,
                    iteration_id="i1",
                    step=RuntimeStep.REASON,
                    created_at=context.now,
                    next_status=AgentRuntimeStatus.WAITING_FOR_USER,
                    requires_user=True,
                    reason_codes=("custom.user_needed",),
                )

        loop.register_step_handler(RuntimeStep.REASON, CustomReasonHandler())
        loop.start("run-custom-1")

        run = loop.get_run("run-custom-1")
        up1, _ = AgentRuntimeStateMachine.transition(run, AgentRuntimeStatus.OBSERVING)
        up2, _ = AgentRuntimeStateMachine.transition(up1, AgentRuntimeStatus.REASONING)
        loop.register_run(up2)

        res = loop.step("run-custom-1")
        assert res.requires_user is True
        assert res.next_status == "waiting_for_user"

    def test_get_run_lookup(self):
        loop = AgentRuntimeLoop()
        loop.start("run-lookup-1")
        assert loop.get_run("run-lookup-1") is not None
        assert loop.get_run("non-existent") is None


# ── 7. Idempotency Tests (5 tests) ───────────────────────────────────────────


class TestRuntimeIdempotency:
    def test_idempotent_start_success(self):
        loop = AgentRuntimeLoop()
        run1 = loop.start("run-idem-1", goal_id="g1", idempotency_key="key-start-1")
        run2 = loop.start("run-idem-1", goal_id="g1", idempotency_key="key-start-1")
        assert run1.id == run2.id

    def test_idempotent_start_conflict(self):
        loop = AgentRuntimeLoop()
        loop.start("run-idem-1", goal_id="g1", idempotency_key="key-start-1")
        with pytest.raises(RuntimeIdempotencyConflictError):
            loop.start(
                "run-idem-1", goal_id="g_DIFFERENT", idempotency_key="key-start-1"
            )

    def test_idempotent_step_success(self):
        loop = AgentRuntimeLoop()
        loop.start("run-idem-2")

        res1 = loop.step("run-idem-2", idempotency_key="key-step-1")
        res2 = loop.step("run-idem-2", idempotency_key="key-step-1")
        assert res1.step == res2.step
        assert res1.created_at == res2.created_at

    def test_idempotent_step_conflict(self):
        loop = AgentRuntimeLoop()
        loop.start("run-idem-3")

        loop.step("run-idem-3", idempotency_key="key-step-3")
        with pytest.raises(RuntimeIdempotencyConflictError):
            loop._repository.store_idempotency_record(
                "key-step-3", "conflicting-hash", {}
            )
            loop.step("run-idem-3", idempotency_key="key-step-3")

    def test_idempotency_record_isolation(self):
        repo = InMemoryAgentRuntimeRepository()
        repo.store_idempotency_record("k1", "h1", {"data": 123})
        rec1 = repo.get_idempotency_record("k1")
        rec1["result"] = {"data": 999}
        rec2 = repo.get_idempotency_record("k1")
        assert rec2["result"] == {"data": 123}


# ── 8. Integration & Policy/Approval/Budget Gates Tests (5 tests) ────────────


class TestRuntimeIntegrationGates:
    def _advance_to_status_with_step(
        self,
        loop: AgentRuntimeLoop,
        run_id: str,
        target_status: AgentRuntimeStatus,
        last_step: str = "plan",
    ):
        run = loop.get_run(run_id)
        curr = run
        if curr.status == AgentRuntimeStatus.CREATED:
            curr, _ = AgentRuntimeStateMachine.transition(
                curr, AgentRuntimeStatus.INITIALIZING
            )
        if (
            curr.status == AgentRuntimeStatus.INITIALIZING
            and target_status != AgentRuntimeStatus.INITIALIZING
        ):
            curr, _ = AgentRuntimeStateMachine.transition(
                curr, AgentRuntimeStatus.OBSERVING
            )
        if (
            curr.status == AgentRuntimeStatus.OBSERVING
            and target_status != AgentRuntimeStatus.OBSERVING
        ):
            curr, _ = AgentRuntimeStateMachine.transition(
                curr, AgentRuntimeStatus.REASONING
            )
        if (
            curr.status == AgentRuntimeStatus.REASONING
            and target_status != AgentRuntimeStatus.REASONING
        ):
            curr, _ = AgentRuntimeStateMachine.transition(
                curr, AgentRuntimeStatus.PLANNING
            )
        if (
            curr.status == AgentRuntimeStatus.PLANNING
            and target_status != AgentRuntimeStatus.PLANNING
        ):
            curr, _ = AgentRuntimeStateMachine.transition(curr, target_status)

        loop.register_run(curr)

        cps = loop._repository.list_checkpoints(run_id)
        if cps:
            latest = cps[-1]
            up_cp = RuntimeCheckpoint(
                id=latest.id,
                agent_run_id=run_id,
                iteration_id=latest.iteration_id,
                runtime_status=target_status.value,
                step=last_step,
                state_version=latest.state_version,
                last_activity_at=latest.last_activity_at,
                created_at=latest.created_at,
            )
            loop._repository._checkpoints[latest.id] = up_cp

    def test_policy_deny_gate(self):
        loop = AgentRuntimeLoop()

        class DenyPolicyHandler:
            def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
                return RuntimeStepResult(
                    agent_run_id=context.agent_run.id,
                    iteration_id="i1",
                    step=RuntimeStep.EVALUATE_POLICIES,
                    created_at=context.now,
                    next_status=AgentRuntimeStatus.BLOCKED,
                    success=False,
                    status=RuntimeStepStatus.FAILED,
                    reason_codes=("runtime.policy_denied",),
                )

        loop.register_step_handler(RuntimeStep.EVALUATE_POLICIES, DenyPolicyHandler())
        loop.start("run-gate-policy")
        self._advance_to_status_with_step(
            loop, "run-gate-policy", AgentRuntimeStatus.PLANNING, last_step="plan"
        )

        res = loop.step("run-gate-policy")
        assert res.next_status == "blocked"
        assert res.success is False

    def test_approval_required_gate(self):
        loop = AgentRuntimeLoop()

        class ApprovalRequiredHandler:
            def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
                return RuntimeStepResult(
                    agent_run_id=context.agent_run.id,
                    iteration_id="i1",
                    step=RuntimeStep.REQUEST_APPROVAL,
                    created_at=context.now,
                    next_status=AgentRuntimeStatus.WAITING_FOR_APPROVAL,
                    requires_approval=True,
                    reason_codes=("runtime.approval_required",),
                )

        loop.register_step_handler(
            RuntimeStep.REQUEST_APPROVAL, ApprovalRequiredHandler()
        )
        loop.start("run-gate-approval")
        self._advance_to_status_with_step(
            loop,
            "run-gate-approval",
            AgentRuntimeStatus.PLANNING,
            last_step="evaluate_policies",
        )

        res = loop.step("run-gate-approval")
        assert res.requires_approval is True
        assert res.next_status == "waiting_for_approval"

    def test_budget_exhausted_gate(self):
        loop = AgentRuntimeLoop()

        class ExhaustedBudgetHandler:
            def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
                return RuntimeStepResult(
                    agent_run_id=context.agent_run.id,
                    iteration_id="i1",
                    step=RuntimeStep.RESERVE_BUDGET,
                    created_at=context.now,
                    next_status=AgentRuntimeStatus.BLOCKED,
                    success=False,
                    status=RuntimeStepStatus.FAILED,
                    reason_codes=("runtime.budget_exhausted",),
                )

        loop.register_step_handler(RuntimeStep.RESERVE_BUDGET, ExhaustedBudgetHandler())
        loop.start("run-gate-budget")
        self._advance_to_status_with_step(
            loop,
            "run-gate-budget",
            AgentRuntimeStatus.PLANNING,
            last_step="request_approval",
        )

        res = loop.step("run-gate-budget")
        assert res.next_status == "blocked"
        assert res.reason_codes == ("runtime.budget_exhausted",)

    def test_goal_validation_failure_gate(self):
        class MockGoalRepo:
            def get_goal(self, goal_id: str):
                class MockGoal:
                    def __init__(self, id: str):
                        self.id = id
                        self.status = "active"
                        self.dependencies = ()

                return MockGoal(goal_id)

        loop = AgentRuntimeLoop(goal_repository=MockGoalRepo())

        class InvalidGoalHandler:
            def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
                return RuntimeStepResult(
                    agent_run_id=context.agent_run.id,
                    iteration_id="i1",
                    step=RuntimeStep.VALIDATE_GOAL,
                    created_at=context.now,
                    next_status=AgentRuntimeStatus.FAILED,
                    success=False,
                    status=RuntimeStepStatus.FAILED,
                    reason_codes=("runtime.goal_invalid",),
                )

        loop.register_step_handler(RuntimeStep.VALIDATE_GOAL, InvalidGoalHandler())
        loop.start("run-gate-goal")

        # Step 1 executes load_goal
        loop.step("run-gate-goal")
        # Step 2 executes validate_goal
        res = loop.step("run-gate-goal")
        assert res.next_status == "failed"
        assert res.success is False

    def test_execution_failure_recovery_gate(self):
        loop = AgentRuntimeLoop()

        class FailedExecuteHandler:
            def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
                return RuntimeStepResult(
                    agent_run_id=context.agent_run.id,
                    iteration_id="i1",
                    step=RuntimeStep.EXECUTE,
                    created_at=context.now,
                    next_status=AgentRuntimeStatus.RECOVERING,
                    success=False,
                    status=RuntimeStepStatus.FAILED,
                    retryable=True,
                    reason_codes=("runtime.execution_failed",),
                )

        loop.register_step_handler(RuntimeStep.EXECUTE, FailedExecuteHandler())
        loop.start("run-gate-exec")
        self._advance_to_status_with_step(
            loop,
            "run-gate-exec",
            AgentRuntimeStatus.EXECUTING,
            last_step="reserve_budget",
        )

        res = loop.step("run-gate-exec")
        assert res.next_status == "recovering"
        assert res.retryable is True


# ── 9. Fail-Safe Hardening Tests ──────────────────────────────────────────────


class TestRuntimeFailSafeHardening:
    def test_goal_repository_error_propagated_and_no_handler_executed(self):
        class BrokenGoalRepo:
            def get_goal(self, goal_id: str):
                raise GoalNotFoundError(f"Goal '{goal_id}' does not exist.")

        handler_called = False

        class TrackedLoadGoalHandler:
            def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
                nonlocal handler_called
                handler_called = True
                return LoadGoalHandler().execute(context)

        loop = AgentRuntimeLoop(goal_repository=BrokenGoalRepo())
        loop.register_step_handler(RuntimeStep.LOAD_GOAL, TrackedLoadGoalHandler())
        loop.start("run-fail-goal-repo")

        with pytest.raises(GoalNotFoundError):
            loop.step("run-fail-goal-repo")

        assert handler_called is False
        checkpoints = loop._repository.list_checkpoints("run-fail-goal-repo")
        assert len(checkpoints) == 1
        assert checkpoints[0].step == ""

    def test_unexpected_goal_repository_error_wrapped(self):
        class UnexpectedErrorGoalRepo:
            def get_goal(self, goal_id: str):
                raise RuntimeError("Database connection lost.")

        loop = AgentRuntimeLoop(goal_repository=UnexpectedErrorGoalRepo())
        loop.start("run-unexpected-repo")

        with pytest.raises(RuntimeRepositoryConsistencyError) as exc_info:
            loop.step("run-unexpected-repo")

        assert "Database connection lost." in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, RuntimeError)

    def test_non_existent_goal_fails_and_does_not_continue_silently(self):
        class NullGoalRepo:
            def get_goal(self, goal_id: str):
                return None

        loop = AgentRuntimeLoop(goal_repository=NullGoalRepo())
        loop.start("run-null-goal")

        with pytest.raises(RuntimeRepositoryConsistencyError):
            loop.step("run-null-goal")

        checkpoints = loop._repository.list_checkpoints("run-null-goal")
        assert len(checkpoints) == 1

    def test_missing_handler_raises_runtime_step_handler_not_found_error(self):
        loop = AgentRuntimeLoop()
        loop._step_handlers.pop(RuntimeStep.LOAD_GOAL.value)
        loop.start("run-no-handler")

        with pytest.raises(RuntimeStepHandlerNotFoundError) as exc_info:
            loop.step("run-no-handler")

        assert "load_goal" in str(exc_info.value)

    def test_missing_handler_never_falls_back_to_load_goal_handler(self):
        loop = AgentRuntimeLoop()
        loop._step_handlers.pop(RuntimeStep.OBSERVE.value)
        loop.start("run-no-observe")

        run = loop.get_run("run-no-observe")
        up, _ = AgentRuntimeStateMachine.transition(run, AgentRuntimeStatus.OBSERVING)
        loop.register_run(up)

        with pytest.raises(RuntimeStepHandlerNotFoundError):
            loop.step("run-no-observe")

        run_after = loop.get_run("run-no-observe")
        assert run_after.status == AgentRuntimeStatus.OBSERVING

    def test_unexpected_handler_exception_does_not_produce_success_true(self):
        loop = AgentRuntimeLoop()

        class BrokenObserveHandler:
            def execute(self, context: RuntimeStepContext) -> RuntimeStepResult:
                raise RuntimeStepExecutionError("Observer crash!")

        loop.register_step_handler(RuntimeStep.OBSERVE, BrokenObserveHandler())
        loop.start("run-handler-exception")

        run = loop.get_run("run-handler-exception")
        up, _ = AgentRuntimeStateMachine.transition(run, AgentRuntimeStatus.OBSERVING)
        loop.register_run(up)

        with pytest.raises(RuntimeStepExecutionError):
            loop.step("run-handler-exception")

        run_after = loop.get_run("run-handler-exception")
        assert run_after.status == AgentRuntimeStatus.OBSERVING

    def test_no_success_checkpoint_created_after_goal_loading_failure(self):
        class FailingRepo:
            def get_goal(self, goal_id: str):
                raise GoalNotFoundError("Missing goal")

        loop = AgentRuntimeLoop(goal_repository=FailingRepo())
        loop.start("run-fail-cp")

        with pytest.raises(GoalNotFoundError):
            loop.step("run-fail-cp")

        checkpoints = loop._repository.list_checkpoints("run-fail-cp")
        assert all(cp.step != "load_goal" for cp in checkpoints)

    def test_no_run_status_update_after_missing_handler(self):
        loop = AgentRuntimeLoop()
        loop._step_handlers.pop(RuntimeStep.LOAD_GOAL.value)
        loop.start("run-status-intact")

        with pytest.raises(RuntimeStepHandlerNotFoundError):
            loop.step("run-status-intact")

        run = loop.get_run("run-status-intact")
        assert run.status == AgentRuntimeStatus.INITIALIZING
