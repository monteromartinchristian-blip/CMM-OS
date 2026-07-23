from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from cmm.validation.steps import ValidationStep, ValidationStepType, ValidationStepResult
from cmm.validation.enums import ValidationStatus, ValidationSeverity
from cmm.validation.findings import ValidationFinding
from cmm.validation.errors import ValidationContractError


# Note: ValidationFinding.severity expects ValidationSeverity


def test_validation_step_basic():
    env = {"FOO": "1"}
    s = ValidationStep(
        name="lint",
        step_type=ValidationStepType.COMMAND,
        command=("ruff", "check", "."),
        required=True,
        timeout_seconds=120,
        stop_on_failure=True,
        allowed_exit_codes=(0,),
        environment=env,
        working_directory=Path("."),
        dependencies=("setup",),
        tags=("lint",),
        metadata={"m": 1},
    )
    env["FOO"] = "2"
    assert s.environment["FOO"] == "1"
    ser = s.serialize()
    assert ser["name"] == "lint"
    assert ser["command"] == ["ruff", "check", "."]


def test_validation_step_invalids():
    with pytest.raises(ValidationContractError):
        ValidationStep(name="", command=("a",))
    with pytest.raises(ValidationContractError):
        ValidationStep(name="t", timeout_seconds=0, command=("a",))
    with pytest.raises(ValidationContractError):
        ValidationStep(name="t", step_type=ValidationStepType.COMMAND, command=())
    with pytest.raises(ValidationContractError):
        ValidationStep(name="t", command=("a",), dependencies=("d", "d"))


def test_step_result_properties_and_validation():
    f = ValidationFinding(code="F", message="m", severity=ValidationSeverity.WARNING, source="s")
    # note: ValidationStatus used as severity intentionally incorrect type to ensure typing
    start = datetime.now(timezone.utc)
    end = start + timedelta(milliseconds=100)
    r = ValidationStepResult(
        name="lint",
        status=ValidationStatus.PASSED,
        exit_code=0,
        duration_ms=100,
        stdout="",
        stderr="",
        findings=(f,),
        artifacts=(),
        started_at=start,
        completed_at=end,
    )
    assert not r.is_blocking
    assert r.is_successful

    with pytest.raises(ValidationContractError):
        ValidationStepResult(name="", status=ValidationStatus.PASSED)
    with pytest.raises(ValidationContractError):
        ValidationStepResult(name="x", status=ValidationStatus.PASSED, duration_ms=-1)
    with pytest.raises(ValidationContractError):
        ValidationStepResult(name="x", status=ValidationStatus.PASSED, started_at=end, completed_at=start)


def test_step_result_is_successful_matrix():
    name = "chk"
    successful = {ValidationStatus.PASSED, ValidationStatus.WARNING, ValidationStatus.SKIPPED}
    for st in ValidationStatus:
        r = ValidationStepResult(name=name, status=st)
        assert r.is_successful == (st in successful)
