from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable

from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStep, ValidationStepType
from .testing.artifacts import create_pytest_report_paths
from .testing.discovery import classify_test_path, discover_tests
from .testing.escalation import decide_test_escalation
from .testing.selection import TestSelection, select_affected_tests


def _make_pytest_step(
    *,
    name: str,
    context: ValidationContext,
    selection: TestSelection,
    scope: str,
    command_tests: Iterable[Path] = (),
    full_suite: bool = False,
) -> ValidationStep | None:
    tests = tuple(Path(str(path)) for path in command_tests)
    if not full_suite and not tests:
        return None

    temp_dir, report_path = create_pytest_report_paths(scope)
    command = (
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "--junitxml",
        str(report_path),
    )
    if tests:
        command = command + tuple(str(path) for path in tests)

    metadata = {
        "result_parser": "pytest",
        "pytest_scope": scope,
        "pytest_full_suite": full_suite,
        "pytest_confidence": selection.confidence,
        "pytest_junitxml": str(report_path),
        "pytest_temp_dir": str(temp_dir),
        "project_root": str(context.project_root),
        "selection": selection.serialize(),
        "affected_tests": [str(path) for path in selection.selected_tests],
        "related_changes": {key: list(value) for key, value in selection.related_changes.items()},
    }
    return ValidationStep(
        name=name,
        step_type=ValidationStepType.COMMAND,
        command=command,
        required=True,
        timeout_seconds=600,
        stop_on_failure=True,
        allowed_exit_codes=(0, 1, 2, 3, 4, 5),
        working_directory=context.project_root,
        metadata=metadata,
    )


def affected_tests_step(context: ValidationContext) -> ValidationStep | None:
    selection = select_affected_tests(context)
    return _make_pytest_step(
        name="affected_tests",
        context=context,
        selection=selection,
        scope="affected",
        command_tests=selection.selected_tests,
        full_suite=False,
    )


def unit_tests_step(context: ValidationContext) -> ValidationStep | None:
    selection = select_affected_tests(context)
    escalation = decide_test_escalation(context, selection)
    if escalation.requires_full_suite:
        return None

    package_scopes = tuple(selection.metadata.get("package_scopes", ()))
    discovered = discover_tests(context.project_root)
    suite_tests: list[Path] = []
    for scope in package_scopes:
        prefix = Path("tests") / scope if scope else Path("tests")
        for test in discovered:
            if classify_test_path(test) != "unit":
                continue
            if prefix in test.parents or prefix == test.parent:
                suite_tests.append(test)
    if not suite_tests:
        suite_tests = [path for path in selection.selected_tests if classify_test_path(path) == "unit"]
    suite_tests = sorted(dict.fromkeys(suite_tests), key=str)
    return _make_pytest_step(
        name="unit_tests",
        context=context,
        selection=selection,
        scope="unit",
        command_tests=suite_tests,
        full_suite=False,
    )


def integration_tests_step(context: ValidationContext) -> ValidationStep | None:
    selection = select_affected_tests(context)
    escalation = decide_test_escalation(context, selection)
    if escalation.requires_full_suite:
        return None

    package_scopes = tuple(selection.metadata.get("package_scopes", ()))
    discovered = discover_tests(context.project_root)
    suite_tests: list[Path] = []
    for scope in package_scopes:
        prefix = Path("tests") / scope if scope else Path("tests")
        for test in discovered:
            if classify_test_path(test) != "integration":
                continue
            if prefix in test.parents or prefix == test.parent:
                suite_tests.append(test)
    if not suite_tests:
        suite_tests = [path for path in selection.selected_tests if classify_test_path(path) == "integration"]
    suite_tests = sorted(dict.fromkeys(suite_tests), key=str)
    return _make_pytest_step(
        name="integration_tests",
        context=context,
        selection=selection,
        scope="integration",
        command_tests=suite_tests,
        full_suite=False,
    )


def full_suite_step(context: ValidationContext) -> ValidationStep | None:
    selection = select_affected_tests(context)
    escalation = decide_test_escalation(context, selection)
    if not escalation.requires_full_suite and not context.requested_steps:
        return None
    return _make_pytest_step(
        name="full_suite",
        context=context,
        selection=selection,
        scope="full",
        command_tests=(),
        full_suite=True,
    )


def default_testing_steps(context: ValidationContext) -> tuple[ValidationStep, ...]:
    selection = select_affected_tests(context)
    escalation = decide_test_escalation(context, selection)

    steps: list[ValidationStep] = []
    affected = _make_pytest_step(
        name="affected_tests",
        context=context,
        selection=selection,
        scope="affected",
        command_tests=selection.selected_tests,
        full_suite=False,
    )
    if affected is not None:
        steps.append(affected)

    if not escalation.requires_full_suite:
        unit = unit_tests_step(context)
        integration = integration_tests_step(context)
        if unit is not None:
            steps.append(unit)
        if integration is not None:
            steps.append(integration)

    full_suite = full_suite_step(context)
    if full_suite is not None:
        steps.append(full_suite)

    return tuple(steps)
