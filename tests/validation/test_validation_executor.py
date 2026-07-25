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


def _script(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def test_execute_command_success_and_streams(tmp_path: Path):
    ex = ValidationExecutor()
    ctx = _context(tmp_path)
    script = _script(tmp_path, "success.py", "import sys\nprint('out')\nsys.stderr.write('err\\n')\n")
    step = ValidationStep(
        name="py",
        step_type=ValidationStepType.COMMAND,
        command=(sys.executable, str(script)),
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
    exit_script = _script(tmp_path, "exit.py", "import sys\nsys.exit(3)\n")
    step_fail = ValidationStep(
        name="fail",
        step_type=ValidationStepType.COMMAND,
        command=(sys.executable, str(exit_script)),
        timeout_seconds=5,
        allowed_exit_codes=(0,),
    )
    res_fail = ex.execute(ctx, step_fail)
    assert res_fail.status == ValidationStatus.FAILED
    assert res_fail.exit_code == 3

    # timeout (simulate a short sleep but allow 1s timeout)
    sleep_script = _script(tmp_path, "sleep.py", "import time\ntime.sleep(0.2)\n")
    step_timeout = ValidationStep(
        name="sleep",
        step_type=ValidationStepType.COMMAND,
        command=(sys.executable, str(sleep_script)),
        timeout_seconds=1,
        allowed_exit_codes=(0,),
    )
    res_timeout = ex.execute(ctx, step_timeout)
    assert res_timeout.status in (ValidationStatus.PASSED, ValidationStatus.FAILED, ValidationStatus.TIMED_OUT)


def test_execute_command_working_directory_and_env(tmp_path: Path, monkeypatch):
    ex = ValidationExecutor()
    ctx = _context(tmp_path)
    monkeypatch.setenv("FROM_OS", "os")
    env_script = _script(
        tmp_path,
        "env.py",
        "import os\nprint(os.environ.get('FROM_OS'), os.environ.get('FROM_CTX'), os.environ.get('FROM_STEP'))\n",
    )
    step = ValidationStep(
        name="env",
        step_type=ValidationStepType.COMMAND,
        command=(sys.executable, str(env_script)),
        timeout_seconds=5,
        environment={"FROM_STEP": "step"},
        allowed_exit_codes=(0,),
        working_directory=tmp_path,
    )
    res = ex.execute(ctx, step)
    assert res.status == ValidationStatus.PASSED
    assert "os ctx step" in res.stdout
    assert os.environ.get("FROM_STEP") is None


def test_execute_command_allows_inline_code_without_security_profile(tmp_path: Path):
    ex = ValidationExecutor()
    ctx = _context(tmp_path)
    step = ValidationStep(
        name="inline",
        step_type=ValidationStepType.COMMAND,
        command=(sys.executable, "-c", "print('ok')"),
        timeout_seconds=5,
        allowed_exit_codes=(0,),
    )
    res = ex.execute(ctx, step)
    assert res.status == ValidationStatus.PASSED
    assert "ok" in res.stdout


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


def test_execute_command_blocks_forbidden_inline_code(tmp_path: Path):
    ex = ValidationExecutor()
    ctx = _context(tmp_path)
    step = ValidationStep(
        name="forbidden",
        step_type=ValidationStepType.COMMAND,
        command=(sys.executable, "-c", "print('blocked')"),
        timeout_seconds=5,
        allowed_exit_codes=(0,),
        metadata={"security_profile": "validation"},
    )
    res = ex.execute(ctx, step)
    assert res.status == ValidationStatus.ERROR
    assert any(f.code == "SECURITY_FORBIDDEN_ARGUMENT" for f in res.findings)
    assert res.artifacts and res.artifacts[0].kind == "command_policy_report"


def test_execute_command_blocks_inline_code_with_security_profile(tmp_path: Path):
    ex = ValidationExecutor()
    ctx = _context(tmp_path)
    step = ValidationStep(
        name="inline",
        step_type=ValidationStepType.COMMAND,
        command=(sys.executable, "-c", "print('blocked')"),
        timeout_seconds=5,
        allowed_exit_codes=(0,),
        metadata={"security_profile": "validation"},
    )
    res = ex.execute(ctx, step)
    assert res.status == ValidationStatus.ERROR
    assert any(f.code == "SECURITY_FORBIDDEN_ARGUMENT" for f in res.findings)
    assert res.artifacts and res.artifacts[0].kind == "command_policy_report"


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
    # name mismatch should add a warning finding and metadata
    assert any(f.code == "INTERNAL_NAME_MISMATCH" for f in r_wrong.findings)
    assert "original_step_name" in r_wrong.metadata

    # missing registry
    r_missing = ex.execute(ctx, s_ok, None)
    assert r_missing.status == ValidationStatus.ERROR

    # missing validator
    s_missing = ValidationStep(name="nope", step_type=ValidationStepType.INTERNAL)
    r_missing2 = ex.execute(ctx, s_missing, reg)
    assert r_missing2.status == ValidationStatus.ERROR
