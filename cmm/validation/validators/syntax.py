"""Python syntax validator for phase 7.3."""

from __future__ import annotations

import codecs
from pathlib import Path
from typing import Any

from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.context import ValidationContext
from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.findings import ValidationFinding
from cmm.validation.protocols import InternalValidator
from cmm.validation.steps import ValidationStep, ValidationStepResult
class PythonSyntaxValidator(InternalValidator):
    name = "syntax"

    def validate(self, context: ValidationContext, step: ValidationStep) -> ValidationStepResult:
        from cmm.validation.catalog import select_python_files

        files = select_python_files(context)
        findings: list[ValidationFinding] = []
        passed_files: list[str] = []
        failed_files: list[str] = []
        for rel_path in files:
            abs_path = context.project_root / rel_path
            try:
                data = abs_path.read_bytes()
                text = data.decode("utf-8")
            except (UnicodeDecodeError, LookupError) as exc:
                findings.append(
                    ValidationFinding(
                        code="PYTHON_ENCODING_ERROR",
                        message=f"Unable to decode {rel_path}: {exc}",
                        severity=ValidationSeverity.ERROR,
                        source="python.compile",
                        file_path=rel_path,
                        blocking=True,
                    )
                )
                failed_files.append(str(rel_path))
                continue
            except OSError as exc:
                findings.append(
                    ValidationFinding(
                        code="PYTHON_READ_ERROR",
                        message=f"Unable to read {rel_path}: {exc}",
                        severity=ValidationSeverity.ERROR,
                        source="python.compile",
                        file_path=rel_path,
                        blocking=True,
                    )
                )
                failed_files.append(str(rel_path))
                continue
            try:
                compile(text, str(abs_path), "exec")
            except SyntaxError as exc:
                code = "PYTHON_SYNTAX_ERROR"
                if isinstance(exc, IndentationError):
                    code = "PYTHON_INDENTATION_ERROR"
                elif isinstance(exc, TabError):
                    code = "PYTHON_TAB_ERROR"
                findings.append(
                    ValidationFinding(
                        code=code,
                        message=str(exc),
                        severity=ValidationSeverity.ERROR,
                        source="python.compile",
                        file_path=rel_path,
                        line=exc.lineno,
                        column=exc.offset,
                        blocking=True,
                        metadata={"exception_type": type(exc).__name__},
                    )
                )
                failed_files.append(str(rel_path))
            else:
                passed_files.append(str(rel_path))

        artifact = ValidationArtifact(
            id="syntax-report",
            kind="syntax_report",
            source="python.compile",
            content={
                "checked_files": [str(p) for p in files],
                "passed_files": passed_files,
                "failed_files": failed_files,
            },
            findings=tuple(findings),
            metrics={
                "files_checked": len(files),
                "files_passed": len(passed_files),
                "files_failed": len(failed_files),
            },
        )
        status = ValidationStatus.FAILED if findings else ValidationStatus.PASSED
        return ValidationStepResult(
            name=step.name,
            status=status,
            findings=tuple(findings),
            artifacts=(artifact,),
            metadata={"files": [str(p) for p in files]},
        )
