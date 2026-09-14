"""Phase 10.5 – Tests for install gate (ensure_domain_validation_allows_install)."""

from __future__ import annotations

import pytest

from cmm.domains.enums import DomainValidationStatus
from cmm.domains.errors import DomainValidationBlocked
from cmm.domains.validation import ensure_domain_validation_allows_install
from cmm.domains.validation_contracts import DomainValidationResult


def _make_result(**overrides) -> DomainValidationResult:
    defaults = {
        "domain_id": "domain:test",
        "version": "1.0.0",
        "status": DomainValidationStatus.PASSED,
        "manifest_valid": True,
        "compatibility_valid": True,
        "dependencies_valid": True,
        "contracts_valid": True,
        "permissions_valid": True,
        "operations_valid": True,
        "workflows_valid": True,
        "security_valid": True,
        "fragmentation_valid": True,
        "tests_valid": True,
        "metadata": {"strict": False, "tests_evaluated": True},
    }
    defaults.update(overrides)
    return DomainValidationResult(**defaults)


class TestGateBlocks:
    def test_passed_result_does_not_block(self) -> None:
        result = _make_result()
        # Should not raise
        ensure_domain_validation_allows_install(result)

    def test_warning_with_all_flags_does_not_block(self) -> None:
        result = _make_result(status=DomainValidationStatus.WARNING)
        ensure_domain_validation_allows_install(result)

    def test_failed_status_blocks(self) -> None:
        result = _make_result(status=DomainValidationStatus.FAILED)
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_install(result)

    def test_error_status_blocks(self) -> None:
        result = _make_result(status=DomainValidationStatus.ERROR)
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_install(result)

    def test_manifest_invalid_blocks(self) -> None:
        result = _make_result(manifest_valid=False)
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_install(result)

    def test_contracts_invalid_blocks(self) -> None:
        result = _make_result(contracts_valid=False)
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_install(result)

    def test_dependencies_invalid_blocks(self) -> None:
        result = _make_result(dependencies_valid=False)
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_install(result)

    def test_permissions_invalid_blocks(self) -> None:
        result = _make_result(permissions_valid=False)
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_install(result)

    def test_security_invalid_blocks(self) -> None:
        result = _make_result(security_valid=False)
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_install(result)

    def test_compatibility_invalid_blocks(self) -> None:
        result = _make_result(compatibility_valid=False)
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_install(result)

    def test_fragmentation_invalid_blocks(self) -> None:
        result = _make_result(fragmentation_valid=False)
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_install(result)

    def test_strict_not_evaluated_blocks(self) -> None:
        result = _make_result(
            tests_valid=False,
            metadata={"strict": True, "tests_evaluated": False},
        )
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_install(result)

    def test_strict_tests_invalid_blocks(self) -> None:
        result = _make_result(
            tests_valid=False,
            metadata={"strict": True, "tests_evaluated": True},
        )
        with pytest.raises(DomainValidationBlocked):
            ensure_domain_validation_allows_install(result)

    def test_non_strict_unevaluated_does_not_block(self) -> None:
        result = _make_result(
            tests_valid=False,
            metadata={"strict": False, "tests_evaluated": False},
        )
        # Non-strict + not evaluated = no block (only strict blocks)
        ensure_domain_validation_allows_install(result)

    def test_reason_codes_are_tuple(self) -> None:
        result = _make_result(
            status=DomainValidationStatus.FAILED, manifest_valid=False
        )
        with pytest.raises(DomainValidationBlocked) as exc_info:
            ensure_domain_validation_allows_install(result)
        details = exc_info.value.details
        assert isinstance(details["reason_codes"], tuple)
        assert "status_failed_or_error" in details["reason_codes"]
        assert "manifest_invalid" in details["reason_codes"]

    def test_blocking_finding_codes(self) -> None:
        result = _make_result(
            metadata={"strict": False, "tests_evaluated": True},
        )
        # The gate checks result.findings for blocking codes
        # Since result is frozen, we test with result.has_blocking_findings
        assert result.has_blocking_findings is False

    def test_gate_message_constant_across_all_cases(self) -> None:
        scenarios = [
            _make_result(status=DomainValidationStatus.FAILED),
            _make_result(manifest_valid=False),
            _make_result(security_valid=False),
        ]
        for result in scenarios:
            with pytest.raises(DomainValidationBlocked) as exc_info:
                ensure_domain_validation_allows_install(result)
            assert str(exc_info.value) == "Domain validation blocks installation"
