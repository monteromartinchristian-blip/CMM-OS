from __future__ import annotations

from pathlib import Path

import pytest

from cmm.validation.context import ValidationContext
from cmm.validation.enums import ValidationStatus
from cmm.validation.steps import ValidationStep, ValidationStepResult, ValidationStepType
from cmm.validation.testing.pytest_parser import parse_pytest_result


def _step(project_root: Path) -> ValidationStep:
    return ValidationStep(
        name="affected_tests",
        step_type=ValidationStepType.COMMAND,
        command=("pytest",),
        required=True,
        timeout_seconds=60,
        working_directory=project_root,
        metadata={
            "pytest_scope": "affected",
            "pytest_full_suite": False,
            "pytest_confidence": 1.0,
            "pytest_junitxml": str(project_root / "report.xml"),
            "project_root": str(project_root),
            "selection": {"selected_tests": ["tests/test_sample.py"], "related_changes": {"cmm/sample.py": ["tests/test_sample.py"]}},
        },
    )


def _generic_result(status: ValidationStatus = ValidationStatus.PASSED, exit_code: int = 0) -> ValidationStepResult:
    return ValidationStepResult(name="affected_tests", status=status, exit_code=exit_code, duration_ms=5, stdout="out", stderr="err")


def test_parse_pytest_result_handles_testsuites_root(tmp_path: Path) -> None:
    project_root = tmp_path
    xml = """\
<testsuites>
  <testsuite name="suite" tests="2" failures="1" errors="0" skipped="1" time="0.2">
    <testcase classname="tests.test_sample" name="test_pass" file="tests/test_sample.py" line="10" time="0.05" />
    <testcase classname="tests.test_sample" name="test_fail" file="tests/test_sample.py" line="20" time="0.07">
      <failure message="boom">traceback here</failure>
    </testcase>
    <testcase classname="tests.test_sample" name="test_skip" file="tests/test_sample.py" line="30" time="0.02">
      <skipped message="not needed" />
    </testcase>
  </testsuite>
</testsuites>
"""
    (project_root / "report.xml").write_text(xml, encoding="utf-8")

    result = parse_pytest_result(step=_step(project_root), generic_result=_generic_result(), junit_xml=project_root / "report.xml")

    assert result.status == ValidationStatus.FAILED
    assert result.exit_code == 0
    assert result.stdout == "out"
    assert result.stderr == "err"
    assert result.metadata["pytest_test_count"] == 3
    assert result.artifacts[0].kind == "pytest_report"
    assert result.artifacts[0].content["summary"]["failed"] == 1
    assert result.artifacts[0].content["tests"][1]["status"] == "failed"


def test_parse_pytest_result_handles_invalid_xml(tmp_path: Path) -> None:
    project_root = tmp_path
    bad_xml = "<testsuites><broken>"
    (project_root / "report.xml").write_text(bad_xml, encoding="utf-8")

    result = parse_pytest_result(step=_step(project_root), generic_result=_generic_result(), junit_xml=project_root / "report.xml")

    assert result.status == ValidationStatus.ERROR
    assert any(f.code == "PYTEST_REPORT_PARSE_ERROR" for f in result.findings)


def test_parse_pytest_result_handles_missing_report(tmp_path: Path) -> None:
    project_root = tmp_path

    result = parse_pytest_result(step=_step(project_root), generic_result=_generic_result(exit_code=1), junit_xml=project_root / "missing.xml")

    assert result.status == ValidationStatus.ERROR
    assert any(f.code == "PYTEST_REPORT_MISSING" for f in result.findings)


@pytest.mark.parametrize(
    "exit_code, expected_status, expected_code",
    [
        (2, ValidationStatus.CANCELLED, "PYTEST_INTERRUPTED"),
        (3, ValidationStatus.ERROR, "PYTEST_INTERNAL_ERROR"),
        (4, ValidationStatus.ERROR, "PYTEST_USAGE_ERROR"),
        (5, ValidationStatus.FAILED, "PYTEST_NO_TESTS_COLLECTED"),
    ],
)
def test_parse_pytest_result_maps_exit_codes(tmp_path: Path, exit_code: int, expected_status: ValidationStatus, expected_code: str) -> None:
    project_root = tmp_path
    (project_root / "report.xml").write_text("<testsuites />", encoding="utf-8")

    result = parse_pytest_result(step=_step(project_root), generic_result=_generic_result(exit_code=exit_code), junit_xml=project_root / "report.xml")

    assert result.status == expected_status
    assert any(f.code == expected_code for f in result.findings)
