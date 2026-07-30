"""Phase 10.5 – Tests for DomainTestsValidator and gate semantics."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from cmm.domains.enums import DomainValidationStatus
from cmm.domains.validation import ensure_domain_validation_allows_install
from cmm.domains.validation_contracts import (
    DomainValidationExecutionContext,
    DomainValidationRequest,
    DomainValidationResult,
)
from cmm.domains.validation_validators import DomainTestsValidator
from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStep, ValidationStepType


def _make_request(root_path, strict=True, run_tests=True):
    return DomainValidationRequest(
        pack=None,
        root_path=str(root_path),
        strict=strict,
        run_tests=run_tests,
    )


class TestDomainTestsValidator:
    def test_strict_without_tests_dir_returns_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            request = _make_request(td, strict=True)
            exec_ctx = DomainValidationExecutionContext(
                request=request,
                validation_context=ValidationContext(project_root=root),
            )
            validator = DomainTestsValidator(exec_ctx)
            step = ValidationStep(
                name="domain.tests",
                step_type=ValidationStepType.INTERNAL,
                required=True,
                dependencies=(),
            )
            result = validator.validate(None, step)
            # In strict mode, should have blocking findings
            blocking = [f for f in result.findings if f.blocking]
            assert len(blocking) >= 1
            # tests_evaluated is always False
            assert result.metadata.get("tests_evaluated") is False

    def test_strict_with_tests_dir_but_no_execution(self) -> None:
        """Even with a tests/ directory, strict mode blocks since tests aren't executed."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tests").mkdir()
            (root / "tests" / "test_example.py").write_text(
                "def test_pass(): pass\n", encoding="utf-8"
            )
            request = _make_request(td, strict=True)
            exec_ctx = DomainValidationExecutionContext(
                request=request,
                validation_context=ValidationContext(project_root=root),
            )
            validator = DomainTestsValidator(exec_ctx)
            step = ValidationStep(
                name="domain.tests",
                step_type=ValidationStepType.INTERNAL,
                required=True,
                dependencies=(),
            )
            result = validator.validate(None, step)
            # Even with structure, strict mode should block
            blocking = [f for f in result.findings if f.blocking]
            assert len(blocking) >= 1
            assert result.metadata["tests_evaluated"] is False
            assert result.metadata["structure_valid"] is True
            assert result.metadata["not_evaluated"] is True
            assert result.metadata["reason"] == "execution_deferred"

    def test_non_strict_with_tests_dir_produces_warning(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "tests").mkdir()
            (root / "tests" / "test_example.py").write_text(
                "def test_pass(): pass\n", encoding="utf-8"
            )
            request = _make_request(td, strict=False, run_tests=False)
            exec_ctx = DomainValidationExecutionContext(
                request=request,
                validation_context=ValidationContext(project_root=root),
            )
            validator = DomainTestsValidator(exec_ctx)
            step = ValidationStep(
                name="domain.tests",
                step_type=ValidationStepType.INTERNAL,
                required=False,
                dependencies=(),
            )
            result = validator.validate(None, step)
            # Non-strict with run_tests=False: warning, no blockers
            blocking = [f for f in result.findings if f.blocking]
            assert len(blocking) == 0

    def test_tests_evaluated_always_false(self) -> None:
        """tests_evaluated is always False in 10.5."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            request = _make_request(td)
            exec_ctx = DomainValidationExecutionContext(
                request=request,
                validation_context=ValidationContext(project_root=root),
            )
            validator = DomainTestsValidator(exec_ctx)
            step = ValidationStep(
                name="domain.tests",
                step_type=ValidationStepType.INTERNAL,
                required=True,
                dependencies=(),
            )
            result = validator.validate(None, step)
            assert result.metadata["tests_evaluated"] is False
            assert result.metadata["not_evaluated"] is True
            assert result.metadata["reason"] == "execution_deferred"


class TestGateStrictBlocks:
    """Gate behavior with strict mode and tests."""

    def test_gate_blocks_strict_when_tests_not_evaluated(self) -> None:
        result = DomainValidationResult(
            domain_id="domain:test",
            version="1.0.0",
            status=DomainValidationStatus.WARNING,
            manifest_valid=True,
            compatibility_valid=True,
            dependencies_valid=True,
            contracts_valid=True,
            permissions_valid=True,
            operations_valid=True,
            workflows_valid=True,
            security_valid=True,
            fragmentation_valid=True,
            tests_valid=False,  # tests didn't pass
            metadata={"strict": True, "tests_evaluated": False},
        )
        with pytest.raises(Exception) as exc_info:
            ensure_domain_validation_allows_install(result)
        assert "Domain validation blocks installation" in str(exc_info.value)
        assert "tests_not_evaluated_strict" in str(
            exc_info.value.details.get("reason_codes", ())
        )

    def test_gate_blocks_when_failed(self) -> None:
        result = DomainValidationResult(
            domain_id="domain:test",
            version="1.0.0",
            status=DomainValidationStatus.FAILED,
            manifest_valid=True,
            compatibility_valid=True,
            dependencies_valid=True,
            contracts_valid=True,
            permissions_valid=True,
            operations_valid=True,
            workflows_valid=True,
            security_valid=True,
            fragmentation_valid=True,
            tests_valid=True,
            metadata={"strict": True, "tests_evaluated": True},
        )
        with pytest.raises(Exception) as exc_info:
            ensure_domain_validation_allows_install(result)
        assert "status_failed_or_error" in str(
            exc_info.value.details.get("reason_codes", ())
        )

    def test_gate_message_is_constant(self) -> None:
        result = DomainValidationResult(
            domain_id="domain:test",
            version="1.0.0",
            status=DomainValidationStatus.FAILED,
            manifest_valid=True,
            compatibility_valid=True,
            dependencies_valid=True,
            contracts_valid=True,
            permissions_valid=True,
            operations_valid=True,
            workflows_valid=True,
            security_valid=True,
            fragmentation_valid=True,
            tests_valid=True,
            metadata={"strict": True, "tests_evaluated": True},
        )
        with pytest.raises(Exception) as exc_info:
            ensure_domain_validation_allows_install(result)
        assert str(exc_info.value) == "Domain validation blocks installation"

    def test_gate_details_structured(self) -> None:
        result = DomainValidationResult(
            domain_id="domain:health",
            version="2.0.0",
            status=DomainValidationStatus.FAILED,
            manifest_valid=True,
            compatibility_valid=True,
            dependencies_valid=True,
            contracts_valid=True,
            permissions_valid=True,
            operations_valid=True,
            workflows_valid=True,
            security_valid=True,
            fragmentation_valid=True,
            tests_valid=True,
            metadata={"strict": True, "tests_evaluated": True},
        )
        with pytest.raises(Exception) as exc_info:
            ensure_domain_validation_allows_install(result)
        details = exc_info.value.details
        assert hasattr(details, "__getitem__")
        assert "domain_id" in details
        assert details["domain_id"] == "domain:health"
        assert "version" in details
        assert details["version"] == "2.0.0"
        assert "reason_codes" in details
        assert "blocking_finding_codes" in details
