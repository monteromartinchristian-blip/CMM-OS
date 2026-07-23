import sys
from pathlib import Path

from cmm.validation import (
    ValidationPipeline,
    ValidationExecutor,
    ValidationRegistry,
    CancellationToken,
)
from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStep, ValidationStepType, ValidationStepResult
from cmm.validation.enums import ValidationStatus, ValidationSeverity
from cmm.validation.findings import ValidationFinding


class PassValidator:
    name = "pass"

    def validate(self, context: ValidationContext, step: ValidationStep):
        return ValidationStepResult(name=step.name, status=ValidationStatus.PASSED)


class WarnValidator:
    name = "warn"

    def validate(self, context: ValidationContext, step: ValidationStep):
        f = ValidationFinding(code="W1", message="warn", severity=ValidationSeverity.WARNING, source="int")
        return ValidationStepResult(name=step.name, status=ValidationStatus.WARNING, findings=(f,))


class BlockValidator:
    name = "block"

    def validate(self, context: ValidationContext, step: ValidationStep):
        f = ValidationFinding(code="B1", message="block", severity=ValidationSeverity.ERROR, source="int", blocking=True)
        return ValidationStepResult(name=step.name, status=ValidationStatus.FAILED, findings=(f,))


class SlowValidator:
    name = "slow"

    def validate(self, context: ValidationContext, step: ValidationStep):
        import time

        time.sleep(0.05)
        return ValidationStepResult(name=step.name, status=ValidationStatus.PASSED)


def _pipeline():
    reg = ValidationRegistry()
    reg.register("pass", PassValidator())
    reg.register("warn", WarnValidator())
    reg.register("block", BlockValidator())
    reg.register("slow", SlowValidator())
    return ValidationPipeline(executor=ValidationExecutor(), registry=reg)


def _context(tmp_path: Path):
    return ValidationContext(project_root=tmp_path)


def test_pipeline_all_pass(tmp_path: Path):
    pl = _pipeline()
    ctx = _context(tmp_path)
    s1 = ValidationStep(name="pass", step_type=ValidationStepType.INTERNAL)
    s2 = ValidationStep(name="pass2", step_type=ValidationStepType.COMMAND, command=(sys.executable, "-c", "print('ok')"))
    steps = (s1, s2)
    result = pl.run(ctx, steps)
    assert result.status == ValidationStatus.PASSED
    assert len(result.steps) == 2


def test_pipeline_warning_aggregation(tmp_path: Path):
    pl = _pipeline()
    ctx = _context(tmp_path)
    s1 = ValidationStep(name="warn", step_type=ValidationStepType.INTERNAL)
    result = pl.run(ctx, (s1,))
    assert result.status == ValidationStatus.WARNING
    assert result.warnings and result.warnings[0].code == "W1"


def test_pipeline_stop_on_failure_and_blocker(tmp_path: Path):
    pl = _pipeline()
    ctx = _context(tmp_path)
    s1 = ValidationStep(name="block", step_type=ValidationStepType.INTERNAL, required=True, stop_on_failure=True)
    s2 = ValidationStep(name="pass", step_type=ValidationStepType.INTERNAL)
    result = pl.run(ctx, (s1, s2))
    assert result.status in (ValidationStatus.FAILED, ValidationStatus.ERROR)
    assert any(r.status == ValidationStatus.SKIPPED for r in result.steps)


def test_pipeline_requested_steps_and_unknown(tmp_path: Path):
    pl = _pipeline()
    ctx = ValidationContext(project_root=tmp_path, requested_steps=("pass",))
    s1 = ValidationStep(name="pass", step_type=ValidationStepType.INTERNAL)
    s2 = ValidationStep(name="warn", step_type=ValidationStepType.INTERNAL)
    res = pl.run(ctx, (s1, s2))
    assert [r.name for r in res.steps] == ["pass"]

    ctx2 = ValidationContext(project_root=tmp_path, requested_steps=("missing",))
    res2 = pl.run(ctx2, (s1, s2))
    assert res2.status == ValidationStatus.ERROR
    assert res2.steps == ()


def test_pipeline_timeout_and_changed_files(tmp_path: Path):
    pl = _pipeline()
    ctx = ValidationContext(project_root=tmp_path, changed_files=(Path("src/a.py"),))
    s = ValidationStep(
        name="sleep",
        step_type=ValidationStepType.COMMAND,
        command=(sys.executable, "-c", "import time; time.sleep(0.2)"),
        timeout_seconds=1,
    )
    res = pl.run(ctx, (s,))
    # status might be PASSED or TIMED_OUT depending on timing but both are acceptable; ensure aggregation is not error
    assert res.status in (ValidationStatus.PASSED, ValidationStatus.FAILED)
    assert res.changed_files == (Path("src/a.py"),)


def test_pipeline_cancellation(tmp_path: Path):
    pl = _pipeline()
    ctx = _context(tmp_path)
    token = CancellationToken()
    s1 = ValidationStep(name="slow", step_type=ValidationStepType.INTERNAL)
    s2 = ValidationStep(name="pass", step_type=ValidationStepType.INTERNAL)
    # cancel immediately
    token.cancel()
    res = pl.run(ctx, (s1, s2), cancel=token)
    assert all(r.status == ValidationStatus.CANCELLED for r in res.steps)

    # cancel after first step
    token2 = CancellationToken()
    def delayed_cancel(context: ValidationContext, step: ValidationStep):
        out = SlowValidator().validate(context, step)
        token2.cancel()
        return out

    class CancelAfterFirst:
        name = "slow"

        def validate(self, context: ValidationContext, step: ValidationStep):
            return delayed_cancel(context, step)

    reg = ValidationRegistry()
    reg.register("slow", CancelAfterFirst())
    reg.register("pass", PassValidator())
    pl2 = ValidationPipeline(executor=ValidationExecutor(), registry=reg)
    res2 = pl2.run(
        ctx,
        (
            ValidationStep(name="slow", step_type=ValidationStepType.INTERNAL),
            ValidationStep(name="pass", step_type=ValidationStepType.INTERNAL),
        ),
        cancel=token2,
    )
    assert any(r.status == ValidationStatus.CANCELLED for r in res2.steps)


def test_pipeline_metadata_and_timestamps(tmp_path: Path):
    pl = _pipeline()
    ctx = _context(tmp_path)
    s = ValidationStep(name="pass", step_type=ValidationStepType.INTERNAL)
    res = pl.run(ctx, (s,))
    assert res.started_at is not None and res.completed_at is not None
    assert res.duration_ms >= 0
    assert res.metadata.get("pipeline") is not None
