"""Phase 10.5 – Tests for domain validation contracts."""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from cmm.domains.enums import DomainValidationStatus
from cmm.domains.errors import DomainContractValidationError
from cmm.domains.validation_contracts import (
    DomainValidationExecutionContext,
    DomainValidationRequest,
    DomainValidationResult,
)


def _make_naive_datetime() -> datetime:
    return datetime.fromisoformat("2025-01-01T00:00:00")


class DummyPack:
    """Minimal pack for testing."""

    def __init__(self, domain_id="domain:test", version="1.0.0"):
        self.id = domain_id
        self.version = version
        self.manifest = None
        self.definition = None


class TestDomainValidationStatus:
    def test_all_status_values(self) -> None:
        assert DomainValidationStatus.PENDING.value == "pending"
        assert DomainValidationStatus.RUNNING.value == "running"
        assert DomainValidationStatus.PASSED.value == "passed"
        assert DomainValidationStatus.WARNING.value == "warning"
        assert DomainValidationStatus.FAILED.value == "failed"
        assert DomainValidationStatus.ERROR.value == "error"

    def test_from_str(self) -> None:
        assert DomainValidationStatus("passed") == DomainValidationStatus.PASSED
        assert DomainValidationStatus("failed") == DomainValidationStatus.FAILED

    def test_invalid_value(self) -> None:
        with pytest.raises(ValueError):
            DomainValidationStatus("invalid")


class TestDomainValidationRequest:
    def test_valid_construction(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(
            pack=pack,
            root_path="/tmp/test",
        )
        assert request.strict is True
        assert request.allow_untrusted is False
        assert request.run_tests is True
        assert request.root_path == "/tmp/test"

    def test_strict_bool_validation(self) -> None:
        pack = DummyPack()
        with pytest.raises(
            DomainContractValidationError, match="strict must be a boolean"
        ):
            DomainValidationRequest(pack=pack, root_path="/tmp", strict=1)  # type: ignore[arg-type]

        with pytest.raises(
            DomainContractValidationError, match="allow_untrusted must be a boolean"
        ):
            DomainValidationRequest(pack=pack, root_path="/tmp", allow_untrusted="yes")  # type: ignore[arg-type]

        with pytest.raises(
            DomainContractValidationError, match="run_tests must be a boolean"
        ):
            DomainValidationRequest(pack=pack, root_path="/tmp", run_tests=1)  # type: ignore[arg-type]

    def test_credential_keys_rejected(self) -> None:
        pack = DummyPack()
        with pytest.raises(DomainContractValidationError, match="Credential-like key"):
            DomainValidationRequest(
                pack=pack,
                root_path="/tmp",
                metadata={"password": "secret123"},
            )

        with pytest.raises(DomainContractValidationError, match="Credential-like key"):
            DomainValidationRequest(
                pack=pack,
                root_path="/tmp",
                metadata={"api_key": "key123"},
            )

    def test_empty_root_path_rejected(self) -> None:
        pack = DummyPack()
        with pytest.raises(DomainContractValidationError):
            DomainValidationRequest(pack=pack, root_path="")

    def test_frozen_dataclass(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(pack=pack, root_path="/tmp")
        with pytest.raises(FrozenInstanceError):
            request.strict = False  # type: ignore[misc]

    def test_requested_steps_normalized(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(
            pack=pack,
            root_path="/tmp",
            requested_steps=("domain.manifest", "domain.security"),
        )
        assert request.requested_steps == ("domain.manifest", "domain.security")

    def test_excluded_steps_normalized(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(
            pack=pack,
            root_path="/tmp",
            excluded_steps=("domain.tests",),
        )
        assert request.excluded_steps == ("domain.tests",)

    def test_metadata_frozen(self) -> None:
        pack = DummyPack()
        request = DomainValidationRequest(
            pack=pack,
            root_path="/tmp",
            metadata={"key": "value"},
        )
        with pytest.raises(TypeError):
            request.metadata["key"] = "new_value"


class TestDomainValidationResult:
    def test_valid_construction(self) -> None:
        result = DomainValidationResult(
            domain_id="domain:health",
            version="1.0.0",
            status=DomainValidationStatus.PASSED,
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
            duration_ms=640,
            validated_at=datetime.now(timezone.utc),
        )
        assert result.domain_id == "domain:health"
        assert result.status == DomainValidationStatus.PASSED
        assert result.duration_ms == 640

    def test_duration_ms_int_not_bool(self) -> None:
        with pytest.raises(
            DomainContractValidationError, match="must be an int, not a boolean"
        ):
            DomainValidationResult(
                domain_id="domain:test",
                version="1.0.0",
                status=DomainValidationStatus.PASSED,
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
                duration_ms=True,  # type: ignore[arg-type]
            )

    def test_duration_ms_non_negative(self) -> None:
        with pytest.raises(DomainContractValidationError, match="must be >= 0"):
            DomainValidationResult(
                domain_id="domain:test",
                version="1.0.0",
                status=DomainValidationStatus.PASSED,
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
                duration_ms=-1,
            )

    def test_timezone_aware_datetime_accepted(self) -> None:
        result = DomainValidationResult(
            domain_id="domain:test",
            version="1.0.0",
            status=DomainValidationStatus.PASSED,
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
            validated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        assert result.validated_at == datetime(2025, 1, 1, tzinfo=timezone.utc)

    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(
            DomainContractValidationError, match="must be timezone-aware"
        ):
            DomainValidationResult(
                domain_id="domain:test",
                version="1.0.0",
                status=DomainValidationStatus.PASSED,
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
                validated_at=_make_naive_datetime(),
            )

    def test_passed_with_blocking_finding_invariant(self) -> None:
        from cmm.validation.enums import ValidationSeverity
        from cmm.validation.findings import ValidationFinding

        finding = ValidationFinding(
            code="TEST_ERROR",
            message="Test error",
            severity=ValidationSeverity.ERROR,
            source="test",
            blocking=True,
        )

        with pytest.raises(
            DomainContractValidationError, match="status is PASSED but blocking finding"
        ):
            DomainValidationResult(
                domain_id="domain:test",
                version="1.0.0",
                status=DomainValidationStatus.PASSED,
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
                findings=(finding,),
            )

    def test_frozen_dataclass(self) -> None:
        result = DomainValidationResult(
            domain_id="domain:test",
            version="1.0.0",
            status=DomainValidationStatus.PASSED,
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
        )
        with pytest.raises(FrozenInstanceError):
            result.domain_id = "new"  # type: ignore[misc]

    def test_is_install_allowed_passed(self) -> None:
        result = DomainValidationResult(
            domain_id="domain:test",
            version="1.0.0",
            status=DomainValidationStatus.PASSED,
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
        )
        assert result.is_install_allowed is True

    def test_is_install_allowed_failed(self) -> None:
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
        )
        assert result.is_install_allowed is False

    def test_is_install_allowed_flag_false(self) -> None:
        result = DomainValidationResult(
            domain_id="domain:test",
            version="1.0.0",
            status=DomainValidationStatus.WARNING,
            manifest_valid=False,
            compatibility_valid=True,
            dependencies_valid=True,
            contracts_valid=True,
            permissions_valid=True,
            operations_valid=True,
            workflows_valid=True,
            security_valid=True,
            fragmentation_valid=True,
            tests_valid=True,
        )
        assert result.is_install_allowed is False

    def test_to_dict_json_roundtrip(self) -> None:
        result = DomainValidationResult(
            domain_id="domain:test",
            version="1.0.0",
            status=DomainValidationStatus.PASSED,
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
            duration_ms=100,
            validated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        d = result.to_dict()
        json_str = json.dumps(d)
        assert "domain:test" in json_str
        assert "passed" in json_str

    def test_has_blocking_findings(self) -> None:
        from cmm.validation.enums import ValidationSeverity
        from cmm.validation.findings import ValidationFinding

        blocking = ValidationFinding(
            code="BLOCK",
            message="block",
            severity=ValidationSeverity.ERROR,
            source="test",
            blocking=True,
        )
        non_blocking = ValidationFinding(
            code="WARN",
            message="warn",
            severity=ValidationSeverity.WARNING,
            source="test",
            blocking=False,
        )

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
            tests_valid=True,
            findings=(non_blocking, blocking),
        )
        assert result.has_blocking_findings is True


class TestDomainValidationExecutionContext:
    def test_construction(self) -> None:
        from pathlib import Path

        from cmm.validation.context import ValidationContext

        pack = DummyPack()
        request = DomainValidationRequest(pack=pack, root_path="/tmp")
        ctx = ValidationContext(project_root=Path("/tmp"))
        exec_ctx = DomainValidationExecutionContext(
            request=request, validation_context=ctx
        )

        assert exec_ctx.request is request
        assert exec_ctx.validation_context is ctx

    def test_frozen(self) -> None:
        from pathlib import Path

        from cmm.validation.context import ValidationContext

        pack = DummyPack()
        request = DomainValidationRequest(pack=pack, root_path="/tmp")
        ctx = ValidationContext(project_root=Path("/tmp"))
        exec_ctx = DomainValidationExecutionContext(
            request=request, validation_context=ctx
        )

        with pytest.raises(FrozenInstanceError):
            exec_ctx.request = None  # type: ignore[misc]
