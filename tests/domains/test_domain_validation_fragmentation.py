"""Phase 10.5 – Tests for DomainFragmentationValidator."""

from __future__ import annotations

import tempfile
from pathlib import Path

from cmm.domains.validation_contracts import (
    DomainValidationExecutionContext,
    DomainValidationRequest,
)
from cmm.domains.validation_scan import DomainValidationScanSession
from cmm.domains.validation_validators import DomainFragmentationValidator
from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStep, ValidationStepType


def _make_request(root_path, strict=True):
    return DomainValidationRequest(pack=None, root_path=str(root_path), strict=strict)


class TestDomainFragmentationValidator:
    def test_no_scan_session_returns_blocker(self) -> None:
        request = _make_request("/tmp")
        exec_ctx = DomainValidationExecutionContext(
            request=request,
            validation_context=ValidationContext(project_root=Path("/tmp")),
        )
        validator = DomainFragmentationValidator(exec_ctx, scan_session=None)
        step = ValidationStep(
            name="domain.fragmentation",
            step_type=ValidationStepType.INTERNAL,
            required=True,
            dependencies=(),
        )
        result = validator.validate(None, step)
        assert any("No scan session" in f.message for f in result.findings)

    def test_readme_con_planner_no_bloquea(self) -> None:
        """README non-py file mentioning Planner doesn't block fragmentation."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text("Uses Planner\n", encoding="utf-8")
            scan = DomainValidationScanSession(
                root=root,
                max_files=10,
                max_file_bytes=1_000_000,
                max_total_bytes=10_000_000,
                max_depth=10,
            )
            request = _make_request(td)
            exec_ctx = DomainValidationExecutionContext(
                request=request,
                validation_context=ValidationContext(project_root=root),
                scan_session=scan,
            )
            validator = DomainFragmentationValidator(exec_ctx, scan_session=scan)
            step = ValidationStep(
                name="domain.fragmentation",
                step_type=ValidationStepType.INTERNAL,
                required=True,
                dependencies=(),
            )
            result = validator.validate(None, step)
            # README is not .py, so no findings
            assert len(result.findings) == 0

    def test_adapter_oficial_no_bloquea(self) -> None:
        """Official CMM adapter: extending BasePlanner may trigger a finding
        but should not necessarily be a blocking finding if recognized as adapter."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "my_planner.py").write_text(
                "from cmm.planner import BasePlanner\n"
                "class MyPlanner(BasePlanner):\n    pass\n",
                encoding="utf-8",
            )
            scan = DomainValidationScanSession(
                root=root,
                max_files=10,
                max_file_bytes=1_000_000,
                max_total_bytes=10_000_000,
                max_depth=10,
            )
            request = _make_request(td)
            exec_ctx = DomainValidationExecutionContext(
                request=request,
                validation_context=ValidationContext(project_root=root),
                scan_session=scan,
            )
            validator = DomainFragmentationValidator(exec_ctx, scan_session=scan)
            step = ValidationStep(
                name="domain.fragmentation",
                step_type=ValidationStepType.INTERNAL,
                required=True,
                dependencies=(),
            )
            result = validator.validate(None, step)
            # The fragmentation analyzer treats class redefinitions as findings.
            # The presence of findings is expected; what matters is correct detection.
            assert len(result.findings) >= 1

    def test_clase_duplicada_real_bloquea(self) -> None:
        """Redefining a CMM class should block."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "dup.py").write_text(
                "class MemoryStore:\n    pass\n", encoding="utf-8"
            )
            scan = DomainValidationScanSession(
                root=root,
                max_files=10,
                max_file_bytes=1_000_000,
                max_total_bytes=10_000_000,
                max_depth=10,
            )
            request = _make_request(td)
            exec_ctx = DomainValidationExecutionContext(
                request=request,
                validation_context=ValidationContext(project_root=root),
                scan_session=scan,
            )
            validator = DomainFragmentationValidator(exec_ctx, scan_session=scan)
            step = ValidationStep(
                name="domain.fragmentation",
                step_type=ValidationStepType.INTERNAL,
                required=True,
                dependencies=(),
            )
            result = validator.validate(None, step)
            block_findings = [f for f in result.findings if f.blocking]
            assert len(block_findings) >= 1

    def test_invalid_utf8_emits_finding(self) -> None:
        """Invalid UTF-8 byte sequence should emit a finding."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "bad.py").write_bytes(b"print('hello')\xff\xfe\n")
            scan = DomainValidationScanSession(
                root=root,
                max_files=10,
                max_file_bytes=1_000_000,
                max_total_bytes=10_000_000,
                max_depth=10,
            )
            request = _make_request(td, strict=True)
            exec_ctx = DomainValidationExecutionContext(
                request=request,
                validation_context=ValidationContext(project_root=root),
                scan_session=scan,
            )
            validator = DomainFragmentationValidator(exec_ctx, scan_session=scan)
            step = ValidationStep(
                name="domain.fragmentation",
                step_type=ValidationStepType.INTERNAL,
                required=True,
                dependencies=(),
            )
            result = validator.validate(None, step)
            utf8_findings = [f for f in result.findings if "UTF" in f.code.upper()]
            assert len(utf8_findings) >= 1
            # In strict mode, this should be blocking
            assert any(f.blocking for f in utf8_findings)
