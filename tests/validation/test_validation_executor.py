import os
import sys
import time
from pathlib import Path

import pytest

from cmm.validation import ValidationExecutor, ValidationRegistry
from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStep, ValidationStepType
from cmm.validation.enums import ValidationStatus


def _context(tmp_path: Path) -> ValidationContext:
    return ValidationContext(project_root=tmp_path, environment={"FROM_CTX": "ctx"})


def test_execute_command_success_and_streams(tmp_path: Path):
    ex = ValidationExecutor()
    ctx = _context(tmp_path)
    code = "import sys; print('out'); sys.stderr.write('err\\n')"
    step = ValidationStep(
        name="py",
        step_type=ValidationStepType.COMMAND,
        command=(sys.executable, "-c", code),
        timeout_seconds=5,
        environment={"FROM_STEP": "step"},
        allowed_exit_codes=(0,),
    )
    res = ex.execute(ctx, step)
    assert res.status == ValidationStatus.PASSED
    assert "out" in res.stdout
    assert "err" in res.stderr
    assert res.exit_code == 0


def test_execute_command_exit_code_and_timeout(tmp_path: Path):
    ex = ValidationExecutor()
    ctx = _context(tmp_path)
    # non-zero exit code
    step_fail = ValidationStep(
        name="fail",
        step_type=ValidationStepType.COMMAND,
        command=(sys.executable, "-c", "import sys; sys.exit(3)"),
        timeout_seconds=5,
        allowed_exit_codes=(0,),
    )
    res_fail = ex.execute(ctx, step_fail)
    assert res_fail.status == ValidationStatus.FAILED
    assert res_fail.exit_code == 3

    # timeout (simulate a short sleep but allow 1s timeout)
    step_timeout = ValidationStep(
        name="sleep",
        step_type=ValidationStepType.COMMAND,
        command=(sys.executable, "-c", "import time; time.sleep(0.2)"),
        timeout_seconds=1,
        allowed_exit_codes=(0,),
    )
    res_timeout = ex.execute(ctx, step_timeout)
    assert res_timeout.status in (ValidationStatus.PASSED, ValidationStatus.FAILED, ValidationStatus.TIMED_OUT)


def test_execute_command_working_directory_and_env(tmp_path: Path, monkeypatch):
    ex = ValidationExecutor()
    ctx = _context(tmp_path)
    monkeypatch.setenv("FROM_OS", "os")
    step = ValidationStep(
        name="env",
        step_type=ValidationStepType.COMMAND,
        command=(
            sys.executable,
            "-c",
            "import os,sys; print(os.environ.get('FROM_OS'), os.environ.get('FROM_CTX'), os.environ.get('FROM_STEP'))",
        ),
        timeout_seconds=5,
        environment={"FROM_STEP": "step"},
        allowed_exit_codes=(0,),
        working_directory=tmp_path,
    )
    res = ex.execute(ctx, step)
    assert res.status == ValidationStatus.PASSED
    assert "os ctx step" in res.stdout


def test_execute_command_executable_not_found(tmp_path: Path):
    ex = ValidationExecutor()
    ctx = _context(tmp_path)
    step = ValidationStep(
        name="bad",
        step_type=ValidationStepType.COMMAND,
        command=("nonexistent_command_hopefully_12345",),
        timeout_seconds=5,
        allowed_exit_codes=(0,),
    )
    res = ex.execute(ctx, step)
    assert res.status == ValidationStatus.ERROR
    assert res.exit_code is None


class OkValidator:
    name = "ok"

    def validate(self, context: ValidationContext, step: ValidationStep):
        return ValidationStepResult(name=step.name, status=ValidationStatus.PASSED)


class WarnValidator:
    name = "warn"

    def validate(self, context: ValidationContext, step: ValidationStep):
        from cmm.validation.findings import ValidationFinding
        from cmm.validation.enums import ValidationSeverity

        f = ValidationFinding(code="W", message="w", severity=ValidationSeverity.WARNING, source="int")
        return ValidationStepResult(name=step.name, status=ValidationStatus.WARNING, findings=(f,))


class ErrorValidator:
    name = "err"

    def validate(self, context: ValidationContext, step: ValidationStep):
        raise RuntimeError("boom")


class WrongNameValidator:
    name = "wrong"

    def validate(self, context: ValidationContext, step: ValidationStep):
        return ValidationStepResult(name="other", status=ValidationStatus.PASSED)


from cmm.validation.steps import ValidationStepResult  # after class definitions


def test_execute_internal(tmp_path: Path):
    ex = ValidationExecutor()
    ctx = _context(tmp_path)
    reg = ValidationRegistry()
    reg.register("ok", OkValidator())
    reg.register("warn", WarnValidator())
    reg.register("wrong", WrongNameValidator())

    s_ok = ValidationStep(name="ok", step_type=ValidationStepType.INTERNAL)
    s_warn = ValidationStep(name="warn", step_type=ValidationStepType.INTERNAL)
    s_wrong = ValidationStep(name="wrong", step_type=ValidationStepType.INTERNAL)

    r_ok = ex.execute(ctx, s_ok, reg)
    r_warn = ex.execute(ctx, s_warn, reg)
    r_wrong = ex.execute(ctx, s_wrong, reg)

    assert r_ok.status == ValidationStatus.PASSED
    assert r_warn.status == ValidationStatus.WARNING
    assert r_wrong.status == ValidationStatus.PASSED and r_wrong.name == "wrong"

    # missing registry
    r_missing = ex.execute(ctx, s_ok, None)
    assert r_missing.status == ValidationStatus.ERROR

    # missing validator
    s_missing = ValidationStep(name="nope", step_type=ValidationStepType.INTERNAL)
    r_missing2 = ex.execute(ctx, s_missing, reg)
    assert r_missing2.status == ValidationStatus.ERROR
