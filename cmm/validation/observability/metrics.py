"""Structured metrics for Phase 7.11 — Observability and Persistence.

:class:`ValidationMetrics`
    Immutable snapshot of aggregated validation statistics.

:class:`ValidationMetricsCalculator`
    Pure, side-effect-free calculator that derives
    :class:`ValidationMetrics` from a :class:`ValidationResult` and an
    optional :class:`CommitGateResult`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..commit_gate.models import CommitGateResult
    from ..results import ValidationResult

from ..enums import ValidationSeverity, ValidationStatus

# ---------------------------------------------------------------------------
# ValidationMetrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ValidationMetrics:
    """Aggregated metrics for one validation execution.

    All numeric fields default to ``0``; the ``metadata`` mapping is
    copied defensively.  The object is immutable and serializable.
    """

    total_duration_ms: int = 0
    step_durations_ms: Mapping[str, int] = field(default_factory=dict)

    # Steps breakdown
    total_steps: int = 0
    passed_steps: int = 0
    failed_steps: int = 0
    warning_steps: int = 0
    skipped_steps: int = 0
    timed_out_steps: int = 0
    cancelled_steps: int = 0
    error_steps: int = 0

    # Tests
    tests_executed: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0

    # Findings
    findings_by_severity: Mapping[str, int] = field(default_factory=dict)

    # Artifacts
    artifacts_count: int = 0

    # Suite
    full_suite_executed: bool = False

    # Gate
    gate_allowed: bool | None = None

    # Errors / timeouts / cancellations at execution level
    timeout_count: int = 0
    cancellation_count: int = 0

    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "step_durations_ms", dict(self.step_durations_ms or {})
        )
        object.__setattr__(
            self, "findings_by_severity", dict(self.findings_by_severity or {})
        )
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def serialize(self) -> dict[str, Any]:
        return {
            "total_duration_ms": self.total_duration_ms,
            "step_durations_ms": dict(self.step_durations_ms),
            "total_steps": self.total_steps,
            "passed_steps": self.passed_steps,
            "failed_steps": self.failed_steps,
            "warning_steps": self.warning_steps,
            "skipped_steps": self.skipped_steps,
            "timed_out_steps": self.timed_out_steps,
            "cancelled_steps": self.cancelled_steps,
            "error_steps": self.error_steps,
            "tests_executed": self.tests_executed,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "tests_skipped": self.tests_skipped,
            "findings_by_severity": dict(self.findings_by_severity),
            "artifacts_count": self.artifacts_count,
            "full_suite_executed": self.full_suite_executed,
            "gate_allowed": self.gate_allowed,
            "timeout_count": self.timeout_count,
            "cancellation_count": self.cancellation_count,
            "metadata": dict(self.metadata or {}),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ValidationMetrics:
        return cls(
            total_duration_ms=int(payload.get("total_duration_ms") or 0),
            step_durations_ms=dict(payload.get("step_durations_ms") or {}),
            total_steps=int(payload.get("total_steps") or 0),
            passed_steps=int(payload.get("passed_steps") or 0),
            failed_steps=int(payload.get("failed_steps") or 0),
            warning_steps=int(payload.get("warning_steps") or 0),
            skipped_steps=int(payload.get("skipped_steps") or 0),
            timed_out_steps=int(payload.get("timed_out_steps") or 0),
            cancelled_steps=int(payload.get("cancelled_steps") or 0),
            error_steps=int(payload.get("error_steps") or 0),
            tests_executed=int(payload.get("tests_executed") or 0),
            tests_passed=int(payload.get("tests_passed") or 0),
            tests_failed=int(payload.get("tests_failed") or 0),
            tests_skipped=int(payload.get("tests_skipped") or 0),
            findings_by_severity=dict(payload.get("findings_by_severity") or {}),
            artifacts_count=int(payload.get("artifacts_count") or 0),
            full_suite_executed=bool(payload.get("full_suite_executed", False)),
            gate_allowed=payload.get("gate_allowed"),
            timeout_count=int(payload.get("timeout_count") or 0),
            cancellation_count=int(payload.get("cancellation_count") or 0),
            metadata=dict(payload.get("metadata") or {}),
        )

    @property
    def error_rate(self) -> float:
        """Fraction of steps that failed (0.0–1.0), or 0.0 if no steps."""
        if self.total_steps == 0:
            return 0.0
        return self.failed_steps / self.total_steps

    @property
    def test_pass_rate(self) -> float:
        """Fraction of tests that passed (0.0–1.0), or 0.0 if none ran."""
        if self.tests_executed == 0:
            return 0.0
        return self.tests_passed / self.tests_executed


# ---------------------------------------------------------------------------
# ValidationMetricsCalculator
# ---------------------------------------------------------------------------

# Tags that indicate the step is a full test suite
_FULL_SUITE_TAGS: frozenset[str] = frozenset({"full_suite", "full-suite", "suite"})


class ValidationMetricsCalculator:
    """Pure, deterministic metrics calculator.

    * Does not perform I/O.
    * Does not mutate input data.
    * Tolerates partially filled ``ValidationResult`` gracefully.
    * Raises only on logically impossible data that would produce
      meaningless metrics.
    """

    @classmethod
    def calculate(
        cls,
        validation_result: ValidationResult,
        gate_result: CommitGateResult | None = None,
    ) -> ValidationMetrics:
        """Derive :class:`ValidationMetrics` from *validation_result*.

        Parameters
        ----------
        validation_result:
            The completed (or partial) validation result.
        gate_result:
            Optional commit-gate evaluation result.  When provided, the
            ``gate_allowed`` field is populated.

        Returns
        -------
        ValidationMetrics
            Freshly computed, immutable metrics object.
        """
        steps = tuple(validation_result.steps or ())

        # --- Step counts ---
        status_map: dict[str, int] = {
            ValidationStatus.PASSED.value: 0,
            ValidationStatus.FAILED.value: 0,
            ValidationStatus.WARNING.value: 0,
            ValidationStatus.SKIPPED.value: 0,
            ValidationStatus.TIMED_OUT.value: 0,
            ValidationStatus.CANCELLED.value: 0,
            ValidationStatus.ERROR.value: 0,
        }
        step_durations: dict[str, int] = {}
        full_suite_executed = False

        for step_res in steps:
            st = (
                step_res.status.value
                if hasattr(step_res.status, "value")
                else str(step_res.status)
            )
            if st in status_map:
                status_map[st] += 1
            step_durations[step_res.name] = int(step_res.duration_ms or 0)
            # Detect full-suite step by tags or name
            step_name_lower = step_res.name.lower()
            if any(tag in step_name_lower for tag in _FULL_SUITE_TAGS):
                full_suite_executed = True

        # --- Test metrics (extracted from step metadata) ---
        tests_executed = tests_passed = tests_failed = tests_skipped = 0
        for step_res in steps:
            meta = step_res.metadata or {}
            tests_executed += int(meta.get("tests_executed") or 0)
            tests_passed += int(meta.get("tests_passed") or 0)
            tests_failed += int(meta.get("tests_failed") or 0)
            tests_skipped += int(meta.get("tests_skipped") or 0)

        # --- Findings ---
        findings_by_severity: dict[str, int] = {s.value: 0 for s in ValidationSeverity}
        all_findings = list(validation_result.blocking_findings or ()) + list(
            validation_result.warnings or ()
        )
        for step_res in steps:
            all_findings.extend(step_res.findings or ())
        for artifact in validation_result.artifacts or ():
            all_findings.extend(artifact.findings or ())

        for finding in all_findings:
            sev = (
                finding.severity.value
                if hasattr(finding.severity, "value")
                else str(finding.severity)
            )
            findings_by_severity[sev] = findings_by_severity.get(sev, 0) + 1

        # --- Artifacts ---
        artifacts_count = len(validation_result.artifacts or ())

        # --- Timeouts / cancellations ---
        timeout_count = status_map.get(ValidationStatus.TIMED_OUT.value, 0)
        cancellation_count = status_map.get(ValidationStatus.CANCELLED.value, 0)

        # --- Gate ---
        gate_allowed: bool | None = None
        if gate_result is not None:
            gate_allowed = bool(gate_result.allowed)

        return ValidationMetrics(
            total_duration_ms=int(validation_result.duration_ms or 0),
            step_durations_ms=step_durations,
            total_steps=len(steps),
            passed_steps=status_map[ValidationStatus.PASSED.value],
            failed_steps=status_map[ValidationStatus.FAILED.value],
            warning_steps=status_map[ValidationStatus.WARNING.value],
            skipped_steps=status_map[ValidationStatus.SKIPPED.value],
            timed_out_steps=status_map[ValidationStatus.TIMED_OUT.value],
            cancelled_steps=status_map[ValidationStatus.CANCELLED.value],
            error_steps=status_map[ValidationStatus.ERROR.value],
            tests_executed=tests_executed,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            tests_skipped=tests_skipped,
            findings_by_severity=findings_by_severity,
            artifacts_count=artifacts_count,
            full_suite_executed=full_suite_executed,
            gate_allowed=gate_allowed,
            timeout_count=timeout_count,
            cancellation_count=cancellation_count,
        )


__all__ = ["ValidationMetrics", "ValidationMetricsCalculator"]
