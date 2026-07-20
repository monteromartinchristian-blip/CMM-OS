from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from cmm.execution import Action, ActionPlanner, ActionType
from cmm.runtime import ActionRuntime, ActionStatus


def test_enqueue_initializes_pending_actions_and_next_action_is_non_mutating() -> None:
    runtime = _runtime()
    actions = _actions()

    runtime.enqueue(actions)

    assert runtime.next_action() == actions[0]
    assert [execution.status for execution in runtime.history()] == [
        ActionStatus.PENDING,
        ActionStatus.PENDING,
    ]
    assert runtime.status().total == 2
    assert runtime.status().pending == 2
    assert runtime.status().progress == 0.0


def test_lifecycle_transitions_record_times_result_and_error() -> None:
    runtime = _runtime()
    runtime.enqueue(_actions())

    running = runtime.mark_running("action-1")
    completed = runtime.mark_completed("action-1", result={"symbols": 2})
    skipped = runtime.mark_skipped("action-2", reason="Out of scope")

    assert running.status == ActionStatus.RUNNING
    assert running.started_at is not None
    assert completed.status == ActionStatus.COMPLETED
    assert completed.started_at == running.started_at
    assert completed.finished_at is not None
    assert completed.result == {"symbols": 2}
    assert skipped.status == ActionStatus.SKIPPED
    assert skipped.finished_at is not None
    assert skipped.error == "Out of scope"
    assert runtime.next_action() is None


def test_failed_actions_contribute_to_progress_and_preserve_history_order() -> None:
    runtime = _runtime()
    runtime.enqueue(_actions())

    runtime.mark_running("action-1")
    failed = runtime.mark_failed("action-1", "Analysis failed")
    runtime.mark_skipped("action-2")

    status = runtime.status()

    assert failed.status == ActionStatus.FAILED
    assert failed.error == "Analysis failed"
    assert status.failed == 1
    assert status.skipped == 1
    assert status.progress == 100.0
    assert [execution.action.id for execution in runtime.history()] == [
        "action-1",
        "action-2",
    ]


def test_runtime_rejects_invalid_queues_and_invalid_transitions() -> None:
    runtime = _runtime()

    with pytest.raises(ValueError, match="Invalid action queue"):
        runtime.enqueue([Action("action-1", 2, ActionType.READ_CLASS, "Service", "Read")])

    runtime.enqueue(_actions())

    with pytest.raises(RuntimeError, match="expected RUNNING"):
        runtime.mark_completed("action-1")
    with pytest.raises(ValueError, match="Unknown action id"):
        runtime.mark_running("missing")
    with pytest.raises(ValueError, match="duplicate action ids"):
        runtime.enqueue([Action("action-1", 1, ActionType.READ_CLASS, "Other", "Read")])


def test_reset_clears_runtime_and_execution_records_are_immutable() -> None:
    runtime = _runtime()
    runtime.enqueue(_actions())
    execution = runtime.mark_running("action-1")

    with pytest.raises(FrozenInstanceError):
        execution.status = ActionStatus.COMPLETED

    runtime.reset()

    assert runtime.history() == []
    assert runtime.next_action() is None
    assert runtime.status().total == 0
    assert runtime.status().progress == 0.0


def _runtime() -> ActionRuntime:
    return ActionRuntime(ActionPlanner(object()))


def _actions() -> list[Action]:
    return [
        Action("action-1", 1, ActionType.READ_CLASS, "Service", "Read service"),
        Action("action-2", 2, ActionType.ANALYZE_IMPACT, "Service", "Analyze impact"),
    ]
