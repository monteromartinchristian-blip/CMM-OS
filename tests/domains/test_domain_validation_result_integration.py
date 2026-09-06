"""Phase 10.43 — Specialized Domain result validation (Task 3)."""

from __future__ import annotations

import pytest

from cmm.domains.validation_integration import (
    DomainValidationIntegrationError,
    require_canonical_validation_success,
    validate_domain_specialized_result,
)
from cmm.validation import (
    ValidationFinding,
    ValidationResult,
    ValidationSeverity,
    ValidationStatus,
)
from cmm.validation.steps import ValidationStepResult


def _step(
    name: str,
    status: ValidationStatus = ValidationStatus.PASSED,
    blocking: bool = False,
) -> ValidationStepResult:
    findings = (
        (
            ValidationFinding(
                code="F",
                message="blocking",
                severity=ValidationSeverity.ERROR,
                source="test",
                blocking=True,
            ),
        )
        if blocking
        else ()
    )
    return ValidationStepResult(name=name, status=status, findings=findings)


def _result(
    result_id: str = "vr-1",
    status: ValidationStatus = ValidationStatus.PASSED,
    steps: tuple = (),
) -> ValidationResult:
    blocking = tuple(
        f for s in steps for f in s.findings if getattr(f, "blocking", False)
    )
    return ValidationResult(
        id=result_id,
        status=status,
        steps=tuple(steps),
        blocking_findings=blocking,
    )


class TestRequireCanonicalValidationSuccess:
    def test_empty_required_returns_empty(self) -> None:
        assert (
            require_canonical_validation_success(
                required_validation_ids=(), canonical_results=()
            )
            == ()
        )

    def test_passing_evidence_returns_references(self) -> None:
        res = _result("vr-1", steps=(_step("domain.contracts"),))
        refs = require_canonical_validation_success(
            required_validation_ids=("domain.contracts",),
            canonical_results=(res,),
        )
        assert refs == ("vr-1",)

    def test_fake_id_only_rejected(self) -> None:
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=("domain.contracts",),
                canonical_results=(),
            )

    def test_failed_canonical_result_rejected(self) -> None:
        failed = _result(
            "vr-bad",
            status=ValidationStatus.FAILED,
            steps=(_step("domain.contracts", ValidationStatus.FAILED),),
        )
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=("domain.contracts",),
                canonical_results=(failed,),
            )

    def test_error_timed_out_cancelled_rejected(self) -> None:
        for status in (
            ValidationStatus.ERROR,
            ValidationStatus.TIMED_OUT,
            ValidationStatus.CANCELLED,
        ):
            res = _result(
                f"vr-{status.value}",
                status=status,
                steps=(_step("domain.contracts", status),),
            )
            with pytest.raises(DomainValidationIntegrationError):
                require_canonical_validation_success(
                    required_validation_ids=("domain.contracts",),
                    canonical_results=(res,),
                )

    def test_missing_step_rejected(self) -> None:
        res = _result("vr-1", steps=(_step("domain.manifest"),))
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=("domain.contracts",),
                canonical_results=(res,),
            )

    def test_blocking_finding_rejected(self) -> None:
        res = _result("vr-1", steps=(_step("domain.contracts", blocking=True),))
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=("domain.contracts",),
                canonical_results=(res,),
            )

    def test_malformed_result_rejected(self) -> None:
        with pytest.raises(DomainValidationIntegrationError):
            require_canonical_validation_success(
                required_validation_ids=("domain.contracts",),
                canonical_results=("not-a-result",),  # type: ignore[arg-type]
            )

    def test_duplicate_required_collapses_to_single_reference(self) -> None:
        res = _result("vr-1", steps=(_step("domain.contracts"),))
        refs = require_canonical_validation_success(
            required_validation_ids=("domain.contracts", "domain.contracts"),
            canonical_results=(res, res),
        )
        assert refs == ("vr-1",)


class TestValidateDomainSpecializedResult:
    def test_domain_identity_coherence(self) -> None:
        res = _result("vr-1", steps=(_step("domain.contracts"),))
        refs = validate_domain_specialized_result(
            result={"domain_id": "domain:test", "status": "success"},
            expected_domain_id="domain:test",
            required_validation_ids=("domain.contracts",),
            canonical_validation_results=(res,),
        )
        assert refs == ("vr-1",)

    def test_domain_identity_mismatch_rejected(self) -> None:
        res = _result("vr-1", steps=(_step("domain.contracts"),))
        with pytest.raises(DomainValidationIntegrationError):
            validate_domain_specialized_result(
                result={"domain_id": "domain:other", "status": "success"},
                expected_domain_id="domain:test",
                required_validation_ids=("domain.contracts",),
                canonical_validation_results=(res,),
            )

    def test_operation_identity_coherence(self) -> None:
        res = _result("vr-1", steps=(_step("domain.contracts"),))
        refs = validate_domain_specialized_result(
            result={
                "domain_id": "domain:test",
                "operation_id": "test.op",
                "status": "success",
            },
            expected_domain_id="domain:test",
            expected_operation_id="test.op",
            required_validation_ids=("domain.contracts",),
            canonical_validation_results=(res,),
        )
        assert refs == ("vr-1",)

    def test_json_unsafe_rejected(self) -> None:
        res = _result("vr-1", steps=(_step("domain.contracts"),))
        with pytest.raises(DomainValidationIntegrationError):
            validate_domain_specialized_result(
                result={"domain_id": "domain:test", "payload": {1, 2, 3}},
                expected_domain_id="domain:test",
                required_validation_ids=("domain.contracts",),
                canonical_validation_results=(res,),
            )

    def test_validation_references_preserved(self) -> None:
        res = _result("vr-1", steps=(_step("domain.contracts"),))
        refs = validate_domain_specialized_result(
            result={
                "domain_id": "domain:test",
                "status": "success",
                "validation_result_ids": ["vr-1"],
            },
            expected_domain_id="domain:test",
            required_validation_ids=("domain.contracts",),
            canonical_validation_results=(res,),
        )
        assert refs == ("vr-1",)

    def test_dropped_validation_references_rejected(self) -> None:
        res = _result("vr-1", steps=(_step("domain.contracts"),))
        with pytest.raises(DomainValidationIntegrationError):
            validate_domain_specialized_result(
                result={
                    "domain_id": "domain:test",
                    "status": "success",
                    "validation_result_ids": ["vr-other"],
                },
                expected_domain_id="domain:test",
                required_validation_ids=("domain.contracts",),
                canonical_validation_results=(res,),
            )

    def test_success_after_failure_rejected(self) -> None:
        with pytest.raises(DomainValidationIntegrationError):
            validate_domain_specialized_result(
                result={"domain_id": "domain:test", "status": "success"},
                expected_domain_id="domain:test",
                required_validation_ids=("domain.contracts",),
                canonical_validation_results=(),
            )

    def test_malformed_confidence_rejected(self) -> None:
        res = _result("vr-1", steps=(_step("domain.contracts"),))
        with pytest.raises(DomainValidationIntegrationError):
            validate_domain_specialized_result(
                result={
                    "domain_id": "domain:test",
                    "status": "success",
                    "confidence": 2.5,
                },
                expected_domain_id="domain:test",
                required_validation_ids=("domain.contracts",),
                canonical_validation_results=(res,),
            )

    def test_does_not_rewrite_content(self) -> None:
        payload = {"domain_id": "domain:test", "status": "success", "fact": "x"}
        snapshot = dict(payload)
        res = _result("vr-1", steps=(_step("domain.contracts"),))
        validate_domain_specialized_result(
            result=payload,
            expected_domain_id="domain:test",
            required_validation_ids=("domain.contracts",),
            canonical_validation_results=(res,),
        )
        assert payload == snapshot
