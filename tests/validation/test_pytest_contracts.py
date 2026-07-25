from __future__ import annotations

from pathlib import Path

import pytest


def test_testing_package_imports_cleanly() -> None:
    import cmm.validation.testing  # noqa: F401
    import cmm.validation.testing_catalog  # noqa: F401
    import cmm.validation.testing_defaults  # noqa: F401


def test_test_selection_is_frozen_and_serializable() -> None:
    from cmm.validation.testing.selection import TestSelection

    selection = TestSelection(
        selected_tests=(Path("tests/example/test_sample.py"),),
        related_changes={"src/module.py": ("tests/example/test_sample.py",)},
        confidence=0.75,
        reasons=("token_match_strong",),
        metadata={"source": "pytest"},
    )

    assert selection.serialize() == {
        "selected_tests": ["tests/example/test_sample.py"],
        "related_changes": {"src/module.py": ["tests/example/test_sample.py"]},
        "confidence": 0.75,
        "requires_full_suite": False,
        "reasons": ["token_match_strong"],
        "metadata": {"source": "pytest"},
    }


def test_pytest_case_result_is_frozen_and_serializable() -> None:
    from cmm.validation.testing.pytest_parser import PytestTestCaseResult

    case = PytestTestCaseResult(
        nodeid="tests/example/test_sample.py::test_sample",
        status="passed",
        duration_ms=12,
        file_path=Path("tests/example/test_sample.py"),
        class_name="TestSample",
        test_name="test_sample",
        message=None,
        traceback=None,
        metadata={"line": 17},
    )

    assert case.serialize() == {
        "nodeid": "tests/example/test_sample.py::test_sample",
        "status": "passed",
        "duration_ms": 12,
        "file_path": "tests/example/test_sample.py",
        "class_name": "TestSample",
        "test_name": "test_sample",
        "message": None,
        "traceback": None,
        "metadata": {"line": 17},
    }


def test_pytest_run_summary_is_frozen_and_serializable() -> None:
    from cmm.validation.testing.pytest_parser import (
        PytestRunSummary,
        PytestTestCaseResult,
    )

    case = PytestTestCaseResult(
        nodeid="tests/example/test_sample.py::test_sample",
        status="passed",
        duration_ms=12,
        file_path=Path("tests/example/test_sample.py"),
        class_name="TestSample",
        test_name="test_sample",
    )
    summary = PytestRunSummary(
        collected=1,
        passed=1,
        failed=0,
        errors=0,
        skipped=0,
        xfailed=0,
        xpassed=0,
        duration_ms=12,
        test_cases=(case,),
        metadata={"root_tag": "testsuite"},
    )

    assert summary.serialize() == {
        "collected": 1,
        "passed": 1,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "xfailed": 0,
        "xpassed": 0,
        "duration_ms": 12,
        "test_cases": [case.serialize()],
        "metadata": {"root_tag": "testsuite"},
    }


def test_test_escalation_decision_is_serializable() -> None:
    from cmm.validation.testing.escalation import TestEscalationDecision

    decision = TestEscalationDecision(
        include_affected_tests=True,
        include_unit_tests=False,
        include_integration_tests=False,
        requires_full_suite=True,
        confidence=0.25,
        reasons=("low_confidence",),
        metadata={"selection": "manual"},
    )

    assert decision.serialize() == {
        "include_affected_tests": True,
        "include_unit_tests": False,
        "include_integration_tests": False,
        "requires_full_suite": True,
        "confidence": 0.25,
        "reasons": ["low_confidence"],
        "metadata": {"selection": "manual"},
    }


@pytest.mark.parametrize(
    "factory",
    [
        lambda: __import__(
            "cmm.validation.testing.discovery", fromlist=["discover_tests"]
        ).discover_tests(Path(".")),
    ],
)
def test_testing_modules_importable(factory) -> None:
    assert factory() is not None
