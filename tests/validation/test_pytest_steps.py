from __future__ import annotations

from pathlib import Path

from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStepType
from cmm.validation.testing_catalog import (
    affected_tests_step,
    full_suite_step,
    integration_tests_step,
    unit_tests_step,
)


def _context(
    project_root: Path,
    *changed_files: str,
    requested_steps: tuple[str, ...] | None = None,
) -> ValidationContext:
    return ValidationContext(
        project_root=project_root,
        changed_files=tuple(Path(item) for item in changed_files),
        requested_steps=requested_steps,
    )


def _write_test(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("def test_sample():\n    assert True\n", encoding="utf-8")


def test_affected_tests_step_uses_pytest_command_shape(tmp_path: Path) -> None:
    _write_test(tmp_path / "tests" / "test_sample.py")

    step = affected_tests_step(_context(tmp_path, "tests/test_sample.py"))

    assert step is not None
    assert step.step_type == ValidationStepType.COMMAND
    assert step.command[:3] == (str(step.command[0]), "-m", "pytest")
    assert "--junitxml" in step.command
    assert "-p" in step.command
    assert "no:cacheprovider" in step.command
    assert step.working_directory == tmp_path


def test_unit_and_integration_steps_follow_discovered_scope(tmp_path: Path) -> None:
    _write_test(tmp_path / "tests" / "core" / "test_module.py")
    _write_test(tmp_path / "tests" / "core" / "integration_test.py")

    unit_step = unit_tests_step(_context(tmp_path, "cmm/core/module.py"))
    integration_step = integration_tests_step(_context(tmp_path, "cmm/core/module.py"))

    assert unit_step is not None
    assert (
        integration_step is None
        or integration_step.step_type == ValidationStepType.COMMAND
    )


def test_full_suite_step_is_returned_for_explicit_request(tmp_path: Path) -> None:
    _write_test(tmp_path / "tests" / "test_sample.py")

    step = full_suite_step(
        _context(tmp_path, "README.md", requested_steps=("full_suite",))
    )

    assert step is not None
    assert step.metadata["pytest_full_suite"] is True


def test_integration_step_is_preserved_when_full_suite_is_required(
    tmp_path: Path,
) -> None:
    (tmp_path / "cmm").mkdir()
    (tmp_path / "cmm" / "service.py").write_text(
        "def execute() -> bool:\n    return True\n",
        encoding="utf-8",
    )
    integration_dir = tmp_path / "tests" / "integration"
    integration_dir.mkdir(parents=True)
    (integration_dir / "test_service.py").write_text(
        "def test_execute() -> None:\n    assert True\n",
        encoding="utf-8",
    )

    context = ValidationContext(
        project_root=tmp_path,
        changed_files=(Path("cmm/service.py"),),
        change_type="public_api_change",
        requested_policy="public_api_change",
    )

    step = integration_tests_step(context)

    assert step is not None
    assert step.name == "integration_tests"
    assert "tests/integration/test_service.py" in step.command


def test_required_integration_step_is_audited_when_no_tests_exist(
    tmp_path: Path,
) -> None:
    (tmp_path / "cmm").mkdir()
    (tmp_path / "cmm" / "service.py").write_text(
        "def execute() -> bool:\n    return True\n",
        encoding="utf-8",
    )

    context = ValidationContext(
        project_root=tmp_path,
        changed_files=(Path("cmm/service.py"),),
        change_type="public_api_change",
        requested_policy="public_api_change",
    )

    step = integration_tests_step(context)

    assert step is not None
    assert step.name == "integration_tests"
    assert step.metadata["not_applicable"] is True
    assert step.metadata["not_applicable_reason"] == "no_integration_tests_discovered"
    assert step.command[:3] == (
        str(step.command[0]),
        "-m",
        "cmm.validation.testing.not_applicable",
    )


def test_optional_integration_step_remains_absent_when_no_tests_exist(
    tmp_path: Path,
) -> None:
    (tmp_path / "cmm").mkdir()
    (tmp_path / "cmm" / "service.py").write_text(
        "def execute() -> bool:\n    return True\n",
        encoding="utf-8",
    )

    context = ValidationContext(
        project_root=tmp_path,
        changed_files=(Path("cmm/service.py"),),
        requested_policy="small_change",
    )

    step = integration_tests_step(context)

    assert step is None
