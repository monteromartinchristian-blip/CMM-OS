from __future__ import annotations

from pathlib import Path

import pytest

import cmm.__main__ as cmm_main
from cmm.development import (
    AutonomousDevelopmentService,
    CycleState,
    DeterministicPlanningProvider,
    DevelopmentService,
    FailureKind,
)


def _operation(domain: str, operation_type: str, path: str, **parameters) -> dict:
    return {
        "domain": domain,
        "type": operation_type,
        "parameters": {"path": path, **parameters},
        "reason": "Autonomous cycle test operation.",
    }


def _plan(goal: str, operations: list[dict], *, files: list[str] | None = None) -> dict:
    return {
        "goal": goal,
        "affected_files": files or list(dict.fromkeys(item["parameters"]["path"] for item in operations)),
        "operations": operations,
        "rationale": "Test a bounded autonomous development cycle.",
        "validations": ["python_ast", "python_compile"],
        "risks": [],
    }


def _cycle(provider, tmp_path: Path, *, yes: bool = True, max_attempts: int = 3, input_fn=None):
    development = DevelopmentService(
        provider,
        input_fn=input_fn or (lambda _prompt: "n"),
        output_fn=lambda _line: None,
    )
    return AutonomousDevelopmentService(provider, development=development).develop(
        "autonomous change",
        tmp_path,
        yes=yes,
        max_attempts=max_attempts,
    )


def test_successful_task_finishes_on_first_attempt(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("", encoding="utf-8")
    goal = "autonomous change"
    provider = DeterministicPlanningProvider(
        _plan(goal, [_operation("python", "create_class", "app.py", class_name="User")])
    )

    result = _cycle(provider, tmp_path)

    assert result.success is True
    assert result.attempt_count == 1
    assert result.attempts[0].states[-1] is CycleState.COMPLETE
    assert result.attempts[0].failure.kind is FailureKind.NONE
    assert "class User" in (tmp_path / "app.py").read_text(encoding="utf-8")


def test_recoverable_execution_failure_replans_after_rollback(tmp_path: Path) -> None:
    path = tmp_path / "app.py"
    original = "class Existing:\n    pass\n"
    path.write_text(original, encoding="utf-8")
    goal = "autonomous change"
    failed = _plan(
        goal,
        [_operation("python", "rename_class", "app.py", class_name="Missing", new_name="Renamed")],
    )
    corrected = _plan(
        goal,
        [_operation("python", "create_class", "app.py", class_name="Added")],
    )
    provider = DeterministicPlanningProvider(plans=[failed, corrected])

    result = _cycle(provider, tmp_path, max_attempts=3)

    assert result.success is True
    assert result.attempt_count == 2
    assert result.attempts[0].failure.kind is FailureKind.EXECUTION
    assert result.attempts[0].result.rollback_applied is True
    assert result.attempts[0].correction_requested is True
    assert result.attempts[1].failure.kind is FailureKind.NONE
    assert "class Added" in path.read_text(encoding="utf-8")


def test_correction_hook_receives_structured_failure(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("class Existing:\n    pass\n", encoding="utf-8")
    goal = "autonomous change"
    failed = _plan(
        goal,
        [_operation("python", "rename_class", "app.py", class_name="Missing", new_name="Renamed")],
    )
    corrected = _plan(goal, [_operation("python", "create_class", "app.py", class_name="Recovered")])
    provider = DeterministicPlanningProvider(failed, corrections=[corrected])

    result = _cycle(provider, tmp_path)

    assert result.success is True
    assert result.attempt_count == 2
    assert result.attempts[0].failure.recoverable is True
    assert "class Recovered" in (tmp_path / "app.py").read_text(encoding="utf-8")


def test_definitive_failure_stops_at_attempt_limit(tmp_path: Path) -> None:
    path = tmp_path / "app.py"
    original = "class Existing:\n    pass\n"
    path.write_text(original, encoding="utf-8")
    goal = "autonomous change"
    failed = _plan(
        goal,
        [_operation("python", "rename_class", "app.py", class_name="Missing", new_name="Renamed")],
    )
    provider = DeterministicPlanningProvider(plan=failed)

    result = _cycle(provider, tmp_path, max_attempts=2)

    assert result.success is False
    assert result.attempt_count == 2
    assert result.attempts[-1].failure.kind is FailureKind.LIMIT
    assert result.attempts[-1].states[-1] is CycleState.ABANDONED
    assert path.read_text(encoding="utf-8") == original
    assert result.rollback_applied is True


def test_planning_failure_is_structured_and_does_not_loop(tmp_path: Path) -> None:
    class InvalidProvider:
        def generate_plan(self, goal, context):
            return "free text is not executable"

    result = _cycle(InvalidProvider(), tmp_path, max_attempts=3)

    assert result.success is False
    assert result.attempt_count == 3
    assert result.attempts[0].failure.kind is FailureKind.PLANNING
    assert result.attempts[0].failure.recoverable is True
    assert result.attempts[-1].failure.kind is FailureKind.LIMIT
    assert result.attempts[-1].states[-1] is CycleState.ABANDONED


def test_human_rejection_is_a_non_recoverable_stop(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("", encoding="utf-8")
    goal = "autonomous change"
    provider = DeterministicPlanningProvider(
        plans=[
            _plan(goal, [_operation("python", "create_class", "app.py", class_name="Never")]),
            _plan(goal, [_operation("python", "create_class", "app.py", class_name="AlsoNever")]),
        ]
    )

    result = _cycle(provider, tmp_path, yes=False, max_attempts=3, input_fn=lambda _prompt: "n")

    assert result.success is False
    assert result.attempt_count == 1
    assert result.attempts[0].failure.kind is FailureKind.HUMAN_ABORT
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == ""


def test_invalid_attempt_limit_is_rejected() -> None:
    with pytest.raises(ValueError, match="max_attempts"):
        AutonomousDevelopmentService(DeterministicPlanningProvider()).develop("goal", Path("."), max_attempts=0)


def test_cli_parser_exposes_opt_in_autonomous_cycle() -> None:
    args = cmm_main.build_parser().parse_args(
        ["develop", "goal", "--autonomous", "--max-attempts", "4"]
    )

    assert args.autonomous is True
    assert args.max_attempts == 4
