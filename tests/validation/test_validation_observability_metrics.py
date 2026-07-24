"""Unit tests for Phase 7.11 — ValidationMetrics and ValidationMetricsCalculator.

Covers:
- Metrics from passed/failed/warning/skipped/cancelled/timed_out results
- Test counts from step metadata
- Findings by severity
- Artifacts count
- Full suite detection
- Gate allowed/denied
- Metadata tolerance
- Empty result
- Determinism
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.findings import ValidationFinding
from cmm.validation.observability.metrics import (
    ValidationMetrics,
    ValidationMetricsCalculator,
)
from cmm.validation.results import ValidationResult
from cmm.validation.steps import ValidationStepResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_step(
    name: str = "step",
    status: ValidationStatus = ValidationStatus.PASSED,
    duration_ms: int = 100,
    findings: tuple[ValidationFinding, ...] = (),
    metadata: dict | None = None,
) -> ValidationStepResult:
    return ValidationStepResult(
        name=name,
        status=status,
        duration_ms=duration_ms,
        findings=findings,
        metadata=metadata or {},
    )


def _make_result(
    steps: tuple[ValidationStepResult, ...] = (),
    status: ValidationStatus = ValidationStatus.PASSED,
    duration_ms: int = 0,
    artifacts: tuple[ValidationArtifact, ...] = (),
    blocking_findings: tuple[ValidationFinding, ...] = (),
    warnings: tuple[ValidationFinding, ...] = (),
) -> ValidationResult:
    return ValidationResult(
        id="validation-metrics-test",
        status=status,
        steps=steps,
        artifacts=artifacts,
        blocking_findings=blocking_findings,
        warnings=warnings,
        duration_ms=duration_ms,
        started_at=_now(),
        completed_at=_now(),
    )


def _make_finding(
    severity: ValidationSeverity, blocking: bool = False
) -> ValidationFinding:
    return ValidationFinding(
        code="TEST_FINDING",
        message="test",
        severity=severity,
        source="test",
        blocking=blocking,
    )


# ---------------------------------------------------------------------------
# ValidationMetrics — construction and serialisation
# ---------------------------------------------------------------------------


def test_metrics_defaults() -> None:
    m = ValidationMetrics()
    assert m.total_duration_ms == 0
    assert m.total_steps == 0
    assert m.gate_allowed is None


def test_metrics_serialize_round_trip() -> None:
    m = ValidationMetrics(
        total_duration_ms=1000,
        total_steps=5,
        passed_steps=4,
        failed_steps=1,
        gate_allowed=True,
    )
    d = m.serialize()
    restored = ValidationMetrics.from_mapping(d)
    assert restored.total_duration_ms == 1000
    assert restored.total_steps == 5
    assert restored.passed_steps == 4
    assert restored.failed_steps == 1
    assert restored.gate_allowed is True


def test_metrics_step_durations_defensive_copy() -> None:
    durations = {"step_a": 100}
    m = ValidationMetrics(step_durations_ms=durations)
    durations["step_a"] = 999
    assert m.step_durations_ms["step_a"] == 100


def test_metrics_findings_by_severity_defensive_copy() -> None:
    fbs = {"info": 5}
    m = ValidationMetrics(findings_by_severity=fbs)
    fbs["info"] = 999
    assert m.findings_by_severity["info"] == 5


def test_metrics_error_rate_zero_steps() -> None:
    m = ValidationMetrics()
    assert m.error_rate == 0.0


def test_metrics_error_rate() -> None:
    m = ValidationMetrics(total_steps=10, failed_steps=2)
    assert m.error_rate == pytest.approx(0.2)


def test_metrics_test_pass_rate_zero_tests() -> None:
    m = ValidationMetrics()
    assert m.test_pass_rate == 0.0


def test_metrics_test_pass_rate() -> None:
    m = ValidationMetrics(tests_executed=50, tests_passed=48)
    assert m.test_pass_rate == pytest.approx(0.96)


# ---------------------------------------------------------------------------
# ValidationMetricsCalculator
# ---------------------------------------------------------------------------


def test_calculate_empty_result() -> None:
    result = _make_result()
    m = ValidationMetricsCalculator.calculate(result)
    assert m.total_steps == 0
    assert m.total_duration_ms == 0
    assert m.gate_allowed is None


def test_calculate_passed_result() -> None:
    steps = (
        _make_step("lint", ValidationStatus.PASSED, 100),
        _make_step("tests", ValidationStatus.PASSED, 200),
    )
    result = _make_result(steps=steps, duration_ms=300, status=ValidationStatus.PASSED)
    m = ValidationMetricsCalculator.calculate(result)
    assert m.total_steps == 2
    assert m.passed_steps == 2
    assert m.failed_steps == 0
    assert m.total_duration_ms == 300
    assert m.step_durations_ms["lint"] == 100
    assert m.step_durations_ms["tests"] == 200


def test_calculate_failed_result() -> None:
    steps = (
        _make_step("lint", ValidationStatus.FAILED, 50),
        _make_step("tests", ValidationStatus.PASSED, 200),
    )
    result = _make_result(steps=steps, duration_ms=250, status=ValidationStatus.FAILED)
    m = ValidationMetricsCalculator.calculate(result)
    assert m.failed_steps == 1
    assert m.passed_steps == 1


def test_calculate_warning_result() -> None:
    steps = (_make_step("lint", ValidationStatus.WARNING, 100),)
    result = _make_result(steps=steps, status=ValidationStatus.WARNING)
    m = ValidationMetricsCalculator.calculate(result)
    assert m.warning_steps == 1


def test_calculate_skipped_result() -> None:
    steps = (_make_step("tests", ValidationStatus.SKIPPED, 0),)
    result = _make_result(steps=steps, status=ValidationStatus.PASSED)
    m = ValidationMetricsCalculator.calculate(result)
    assert m.skipped_steps == 1


def test_calculate_cancelled_result() -> None:
    steps = (_make_step("tests", ValidationStatus.CANCELLED, 0),)
    result = _make_result(steps=steps, status=ValidationStatus.CANCELLED)
    m = ValidationMetricsCalculator.calculate(result)
    assert m.cancelled_steps == 1
    assert m.cancellation_count == 1


def test_calculate_timed_out_result() -> None:
    steps = (_make_step("tests", ValidationStatus.TIMED_OUT, 60000),)
    result = _make_result(steps=steps, status=ValidationStatus.FAILED)
    m = ValidationMetricsCalculator.calculate(result)
    assert m.timed_out_steps == 1
    assert m.timeout_count == 1


def test_calculate_tests_from_metadata() -> None:
    steps = (
        _make_step(
            "pytest",
            ValidationStatus.PASSED,
            1000,
            metadata={
                "tests_executed": 42,
                "tests_passed": 41,
                "tests_failed": 1,
                "tests_skipped": 0,
            },
        ),
    )
    result = _make_result(steps=steps, status=ValidationStatus.PASSED)
    m = ValidationMetricsCalculator.calculate(result)
    assert m.tests_executed == 42
    assert m.tests_passed == 41
    assert m.tests_failed == 1
    assert m.tests_skipped == 0


def test_calculate_findings_by_severity() -> None:
    blocking = _make_finding(ValidationSeverity.ERROR, blocking=True)
    warn = _make_finding(ValidationSeverity.WARNING)
    info = _make_finding(ValidationSeverity.INFO)
    # Add info finding via step
    step = _make_step("lint", ValidationStatus.FAILED, findings=(info,))
    result2 = _make_result(
        steps=(step,),
        blocking_findings=(blocking,),
        warnings=(warn,),
        status=ValidationStatus.FAILED,
    )
    m = ValidationMetricsCalculator.calculate(result2)
    assert m.findings_by_severity["error"] >= 1
    assert m.findings_by_severity["warning"] >= 1
    assert m.findings_by_severity["info"] >= 1


def test_calculate_artifacts_count() -> None:
    from datetime import datetime, timezone

    artifact = ValidationArtifact(
        id="art1",
        kind="report",
        source="lint",
        created_at=datetime.now(timezone.utc),
    )
    result = _make_result(artifacts=(artifact,), status=ValidationStatus.PASSED)
    m = ValidationMetricsCalculator.calculate(result)
    assert m.artifacts_count == 1


def test_calculate_full_suite_detected() -> None:
    steps = (_make_step("run_full_suite", ValidationStatus.PASSED, 5000),)
    result = _make_result(steps=steps, status=ValidationStatus.PASSED)
    m = ValidationMetricsCalculator.calculate(result)
    assert m.full_suite_executed is True


def test_calculate_no_full_suite() -> None:
    steps = (_make_step("lint", ValidationStatus.PASSED, 100),)
    result = _make_result(steps=steps, status=ValidationStatus.PASSED)
    m = ValidationMetricsCalculator.calculate(result)
    assert m.full_suite_executed is False


def test_calculate_gate_allowed() -> None:
    from cmm.validation.commit_gate.models import CommitGateResult

    gate = CommitGateResult(
        allowed=True,
        validation_result_id="validation-abc",
    )
    result = _make_result(status=ValidationStatus.PASSED)
    m = ValidationMetricsCalculator.calculate(result, gate_result=gate)
    assert m.gate_allowed is True


def test_calculate_gate_denied() -> None:
    from cmm.validation.commit_gate.enums import CommitGateReasonCode
    from cmm.validation.commit_gate.models import CommitGateReason, CommitGateResult

    gate = CommitGateResult(
        allowed=False,
        validation_result_id="validation-abc",
        reasons=(
            CommitGateReason(
                code=CommitGateReasonCode.VALIDATION_NOT_PASSED,
                message="Tests failed",
            ),
        ),
    )
    result = _make_result(status=ValidationStatus.FAILED)
    m = ValidationMetricsCalculator.calculate(result, gate_result=gate)
    assert m.gate_allowed is False


def test_calculate_partial_metadata_tolerant() -> None:
    # Step metadata with missing keys should not crash
    step = ValidationStepResult(
        name="partial",
        status=ValidationStatus.PASSED,
        metadata={"tests_executed": None},  # type: ignore[arg-type]
    )
    result = _make_result(steps=(step,), status=ValidationStatus.PASSED)
    m = ValidationMetricsCalculator.calculate(result)
    # Should not raise; tests_executed defaults to 0
    assert m.tests_executed == 0


def test_calculate_deterministic() -> None:
    """Same input should always produce the same output."""
    steps = (
        _make_step("lint", ValidationStatus.PASSED, 100),
        _make_step("tests", ValidationStatus.FAILED, 200),
    )
    result = _make_result(steps=steps, status=ValidationStatus.FAILED, duration_ms=300)
    m1 = ValidationMetricsCalculator.calculate(result)
    m2 = ValidationMetricsCalculator.calculate(result)
    assert m1.serialize() == m2.serialize()
