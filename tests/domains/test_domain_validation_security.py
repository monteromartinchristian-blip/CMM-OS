"""Phase 10.5 – Tests for DomainSecurityValidator."""

from __future__ import annotations

import tempfile
from pathlib import Path

from cmm.domains.validation_contracts import (
    DomainValidationExecutionContext,
    DomainValidationRequest,
)
from cmm.domains.validation_scan import DomainValidationScanSession
from cmm.domains.validation_validators import DomainSecurityValidator
from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStep, ValidationStepType


def _make_request(root_path, strict=True):
    return DomainValidationRequest(pack=None, root_path=str(root_path), strict=strict)


class TestDomainSecurityValidator:
    def test_no_scan_session_returns_blocker(self) -> None:
        request = _make_request("/tmp")
        exec_ctx = DomainValidationExecutionContext(
            request=request,
            validation_context=ValidationContext(project_root=Path("/tmp")),
        )
        validator = DomainSecurityValidator(exec_ctx, scan_session=None)
        step = ValidationStep(
            name="domain.security",
            step_type=ValidationStepType.INTERNAL,
            required=True,
            dependencies=(),
        )
        result = validator.validate(None, step)
        assert any("No scan session" in f.message for f in result.findings)

    def test_comentario_con_subprocess_no_bloquea(self) -> None:
        """A comment with 'subprocess' doesn't block."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "safe.py").write_text("# no usar subprocess", encoding="utf-8")
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
            validator = DomainSecurityValidator(
                exec_ctx,
                scan_session=scan,
                max_file_bytes=1_000_000,
            )
            step = ValidationStep(
                name="domain.security",
                step_type=ValidationStepType.INTERNAL,
                required=True,
                dependencies=(),
            )
            result = validator.validate(None, step)
            # The comment should not cause a blocking finding
            blocking = [
                f
                for f in result.findings
                if f.blocking and "subprocess" in f.message.lower()
            ]
            assert len(blocking) == 0

    def test_import_real_subprocess_bloquea(self) -> None:
        """Real import of subprocess should block."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "mal.py").write_text("import subprocess\n", encoding="utf-8")
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
            validator = DomainSecurityValidator(
                exec_ctx,
                scan_session=scan,
                max_file_bytes=1_000_000,
            )
            step = ValidationStep(
                name="domain.security",
                step_type=ValidationStepType.INTERNAL,
                required=True,
                dependencies=(),
            )
            result = validator.validate(None, step)
            blocking = [
                f
                for f in result.findings
                if f.blocking and "Unauthorized import" in f.message
            ]
            assert len(blocking) >= 1

    def test_docstring_con_eval_no_bloquea_eval(self) -> None:
        """Docstring mentioning eval should only appear as prompt risk."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "doc.py").write_text('"""Uses eval."""\n', encoding="utf-8")
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
            validator = DomainSecurityValidator(
                exec_ctx,
                scan_session=scan,
                max_file_bytes=1_000_000,
            )
            step = ValidationStep(
                name="domain.security",
                step_type=ValidationStepType.INTERNAL,
                required=True,
                dependencies=(),
            )
            result = validator.validate(None, step)
            # Should not contain an "eval" import finding
            assert not any(
                "Unauthorized import" in f.message and "eval" in f.message.lower()
                for f in result.findings
            )

    def test_placeholder_secret_no_bloquea(self) -> None:
        """Placeholder secrets shouldn't block."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "cfg.py").write_text(
                'API_KEY = "your-api-key-here"\n', encoding="utf-8"
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
            validator = DomainSecurityValidator(
                exec_ctx,
                scan_session=scan,
                max_file_bytes=1_000_000,
            )
            step = ValidationStep(
                name="domain.security",
                step_type=ValidationStepType.INTERNAL,
                required=True,
                dependencies=(),
            )
            result = validator.validate(None, step)
            # Placeholder should not create a secret finding
            secrets = [f for f in result.findings if "SECRET" in f.code]
            assert len(secrets) == 0

    def test_shell_true_bloquea(self) -> None:
        """shell=True in code blocks."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "sh.py").write_text(
                "subprocess.run(['ls'], shell=True)\n", encoding="utf-8"
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
            validator = DomainSecurityValidator(
                exec_ctx,
                scan_session=scan,
                max_file_bytes=1_000_000,
            )
            step = ValidationStep(
                name="domain.security",
                step_type=ValidationStepType.INTERNAL,
                required=True,
                dependencies=(),
            )
            result = validator.validate(None, step)
            blocking = [
                f
                for f in result.findings
                if f.blocking and "Forbidden command" in f.message
            ]
            assert len(blocking) >= 1

    def test_os_system_bloquea(self) -> None:
        """os.system() blocks."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "osos.py").write_text(
                "import os\nos.system('ls')\n", encoding="utf-8"
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
            validator = DomainSecurityValidator(
                exec_ctx,
                scan_session=scan,
                max_file_bytes=1_000_000,
            )
            step = ValidationStep(
                name="domain.security",
                step_type=ValidationStepType.INTERNAL,
                required=True,
                dependencies=(),
            )
            result = validator.validate(None, step)
            blocking = [f for f in result.findings if f.blocking]
            assert len(blocking) >= 1
