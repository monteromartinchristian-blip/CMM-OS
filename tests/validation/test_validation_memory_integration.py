"""Integration tests for Technical Memory Adapter (Subphase 7.13)."""

from cmm.validation.enums import ValidationStatus
from cmm.validation.findings import ValidationFinding, ValidationSeverity
from cmm.validation.integration.contracts import ValidationDecision
from cmm.validation.integration.memory import ValidationMemoryAdapter
from cmm.validation.results import ValidationResult


def test_memory_adapter_retention_policy_blocking_only():
    adapter = ValidationMemoryAdapter(retention_policy="blocking_only")

    passed_res = ValidationResult(
        id="val-p1", status=ValidationStatus.PASSED, duration_ms=5
    )
    rec1 = adapter.remember_validation(passed_res)
    assert rec1 is None
    assert len(adapter.records) == 0

    finding = ValidationFinding(
        code="ERR_SYNTAX",
        message="Syntax error",
        severity=ValidationSeverity.ERROR,
        source="syntax_check",
    )
    failed_res = ValidationResult(
        id="val-f1",
        status=ValidationStatus.FAILED,
        blocking_findings=(finding,),
        duration_ms=10,
    )
    dec = ValidationDecision.from_validation_result(failed_res)
    rec2 = adapter.remember_validation(
        failed_res, decision=dec, rollback_requested=True
    )

    assert rec2 is not None
    assert rec2.validation_id == "val-f1"
    assert rec2.status == "failed"
    assert "ERR_SYNTAX" in rec2.recurring_finding_codes
    assert len(adapter.records) == 1


def test_memory_adapter_retention_policy_always():
    adapter = ValidationMemoryAdapter(retention_policy="always")
    passed_res = ValidationResult(
        id="val-p2", status=ValidationStatus.PASSED, duration_ms=5
    )
    rec = adapter.remember_validation(passed_res)
    assert rec is not None
    assert rec.validation_id == "val-p2"
    assert len(adapter.records) == 1
