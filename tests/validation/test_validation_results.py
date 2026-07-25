from datetime import datetime, timezone, timedelta
from pathlib import Path

from cmm.validation.results import ValidationResult
from cmm.validation.enums import ValidationStatus
from cmm.validation.findings import ValidationFinding
from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.steps import ValidationStepResult
from cmm.validation.enums import ValidationSeverity


def test_validation_result_aggregation_and_serialization():
    f_block = ValidationFinding(
        code="B1",
        message="blocker",
        severity=ValidationSeverity.ERROR,
        source="s",
        blocking=True,
    )
    f_warn = ValidationFinding(
        code="W1", message="warn", severity=ValidationSeverity.WARNING, source="s"
    )

    step_res = ValidationStepResult(
        name="lint", status=ValidationStatus.PASSED, findings=(f_warn,)
    )
    artifact = ValidationArtifact(
        id="a1", kind="report", source="s", findings=(f_block,)
    )

    start = datetime.now(timezone.utc)
    end = start + timedelta(seconds=1)

    vr = ValidationResult(
        id="validation-result-123",
        status=ValidationStatus.PASSED,
        policy="small_change",
        steps=(step_res,),
        artifacts=(artifact,),
        blocking_findings=(f_block,),
        warnings=(f_warn,),
        changed_files=(Path("src/example.py"),),
        affected_tests=("tests::test_x",),
        duration_ms=12400,
        started_at=start,
        completed_at=end,
        can_commit=True,
    )

    assert vr.failed_steps == ()
    assert vr.skipped_steps == ()
    assert vr.total_findings >= 2
    assert vr.is_successful
    assert vr.has_blockers

    s = vr.serialize()
    assert s["id"] == "validation-result-123"
    assert s["status"] == "passed"
    assert s["changed_files"] == ["src/example.py"]
    assert s["can_commit"] is True
