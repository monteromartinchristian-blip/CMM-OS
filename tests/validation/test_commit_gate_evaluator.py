from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.commit_gate.enums import CommitGateReasonCode
from cmm.validation.commit_gate.evaluator import CommitGateEvaluator
from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.findings import ValidationFinding
from cmm.validation.policy import DEFAULT_VALIDATION_POLICIES, ValidationPolicy
from cmm.validation.results import ValidationResult
from cmm.validation.steps import ValidationStepResult


def test_evaluator_approved() -> None:
    policy = DEFAULT_VALIDATION_POLICIES["small_change"]
    step_results = (
        ValidationStepResult(name="formatter_check", status=ValidationStatus.PASSED),
        ValidationStepResult(name="lint_check", status=ValidationStatus.PASSED),
        ValidationStepResult(name="syntax", status=ValidationStatus.PASSED),
        ValidationStepResult(name="ast", status=ValidationStatus.PASSED),
        ValidationStepResult(name="affected_tests", status=ValidationStatus.PASSED),
    )
    result = ValidationResult(
        id="val-1",
        status=ValidationStatus.PASSED,
        policy="small_change",
        steps=step_results,
        can_commit=True,
    )

    gate_res = CommitGateEvaluator.evaluate(result, policy)

    assert gate_res.allowed is True
    assert len(gate_res.reasons) == 0
    assert gate_res.validation_result_id == "val-1"
    assert gate_res.policy_name == "small_change"
    assert gate_res.commit_created is False


def test_evaluator_policy_forbids_commit() -> None:
    policy = DEFAULT_VALIDATION_POLICIES["autonomous_execution"]
    assert policy.allow_commit is False

    result = ValidationResult(
        id="val-2",
        status=ValidationStatus.PASSED,
        policy="autonomous_execution",
        can_commit=False,
    )

    gate_res = CommitGateEvaluator.evaluate(result, policy)

    assert gate_res.allowed is False
    assert any(
        r.code == CommitGateReasonCode.POLICY_FORBIDS_COMMIT for r in gate_res.reasons
    )


def test_evaluator_unresolved_policy() -> None:
    result = ValidationResult(
        id="val-3",
        status=ValidationStatus.PASSED,
        policy="non_existent_policy_12345",
        can_commit=True,
    )

    gate_res = CommitGateEvaluator.evaluate(result, policy=None)

    assert gate_res.allowed is False
    assert any(
        r.code == CommitGateReasonCode.POLICY_UNRESOLVED for r in gate_res.reasons
    )


def test_evaluator_required_step_failed() -> None:
    policy = DEFAULT_VALIDATION_POLICIES["small_change"]
    step_results = (
        ValidationStepResult(name="formatter_check", status=ValidationStatus.PASSED),
        ValidationStepResult(name="lint_check", status=ValidationStatus.FAILED),
        ValidationStepResult(name="syntax", status=ValidationStatus.PASSED),
        ValidationStepResult(name="ast", status=ValidationStatus.PASSED),
        ValidationStepResult(name="affected_tests", status=ValidationStatus.PASSED),
    )
    result = ValidationResult(
        id="val-4",
        status=ValidationStatus.FAILED,
        policy="small_change",
        steps=step_results,
        can_commit=False,
    )

    gate_res = CommitGateEvaluator.evaluate(result, policy)

    assert gate_res.allowed is False
    assert any(
        r.code == CommitGateReasonCode.REQUIRED_STEP_FAILED and r.step == "lint_check"
        for r in gate_res.reasons
    )


def test_evaluator_required_step_missing() -> None:
    policy = DEFAULT_VALIDATION_POLICIES["small_change"]
    # Missing lint_check
    step_results = (
        ValidationStepResult(name="formatter_check", status=ValidationStatus.PASSED),
        ValidationStepResult(name="syntax", status=ValidationStatus.PASSED),
    )
    result = ValidationResult(
        id="val-5",
        status=ValidationStatus.PASSED,
        policy="small_change",
        steps=step_results,
        can_commit=True,
    )

    gate_res = CommitGateEvaluator.evaluate(result, policy)

    assert gate_res.allowed is False
    assert any(
        r.code == CommitGateReasonCode.REQUIRED_STEP_MISSING and r.step == "lint_check"
        for r in gate_res.reasons
    )


def test_evaluator_blocking_finding_and_security_violation() -> None:
    policy = DEFAULT_VALIDATION_POLICIES["small_change"]
    sec_finding = ValidationFinding(
        code="S101",
        message="Use of hardcoded secret",
        severity=ValidationSeverity.CRITICAL,
        source="bandit",
        blocking=True,
    )
    step_results = (
        ValidationStepResult(name="formatter_check", status=ValidationStatus.PASSED),
        ValidationStepResult(
            name="lint_check", status=ValidationStatus.PASSED, findings=(sec_finding,)
        ),
        ValidationStepResult(name="syntax", status=ValidationStatus.PASSED),
        ValidationStepResult(name="ast", status=ValidationStatus.PASSED),
        ValidationStepResult(name="affected_tests", status=ValidationStatus.PASSED),
    )
    result = ValidationResult(
        id="val-6",
        status=ValidationStatus.FAILED,
        policy="small_change",
        steps=step_results,
        blocking_findings=(sec_finding,),
        can_commit=False,
    )

    gate_res = CommitGateEvaluator.evaluate(result, policy)

    assert gate_res.allowed is False
    assert any(
        r.code == CommitGateReasonCode.SECURITY_VIOLATION for r in gate_res.reasons
    )
    assert len(gate_res.blocking_findings) == 1


def test_evaluator_required_artifact_missing() -> None:
    policy = ValidationPolicy(
        name="custom_artifact_policy",
        required_steps=(),
        allow_commit=True,
        metadata={"required_artifacts": ["coverage_report"]},
    )
    result = ValidationResult(
        id="val-7",
        status=ValidationStatus.PASSED,
        policy="custom_artifact_policy",
        can_commit=True,
    )

    gate_res = CommitGateEvaluator.evaluate(result, policy)

    assert gate_res.allowed is False
    assert any(
        r.code == CommitGateReasonCode.REQUIRED_ARTIFACT_MISSING
        and r.artifact == "coverage_report"
        for r in gate_res.reasons
    )


def test_evaluator_required_artifact_present() -> None:
    policy = ValidationPolicy(
        name="custom_artifact_policy",
        required_steps=(),
        allow_commit=True,
        metadata={"required_artifacts": ["coverage_report"]},
    )
    artifact = ValidationArtifact(
        id="art-1",
        kind="coverage_report",
        source="pytest-cov",
    )
    result = ValidationResult(
        id="val-8",
        status=ValidationStatus.PASSED,
        policy="custom_artifact_policy",
        artifacts=(artifact,),
        can_commit=True,
    )

    gate_res = CommitGateEvaluator.evaluate(result, policy)

    assert gate_res.allowed is True


def test_evaluator_cancelled_pipeline() -> None:
    policy = DEFAULT_VALIDATION_POLICIES["small_change"]
    result = ValidationResult(
        id="val-9",
        status=ValidationStatus.CANCELLED,
        policy="small_change",
        metadata={"pipeline": {"cancelled": True}},
        can_commit=False,
    )

    gate_res = CommitGateEvaluator.evaluate(result, policy)

    assert gate_res.allowed is False
    assert any(
        r.code == CommitGateReasonCode.PIPELINE_CANCELLED for r in gate_res.reasons
    )
