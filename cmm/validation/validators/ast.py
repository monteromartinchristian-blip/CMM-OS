"""Python AST validator for phase 7.3."""

from __future__ import annotations

import ast
from pathlib import Path

from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.context import ValidationContext
from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.findings import ValidationFinding
from cmm.validation.protocols import InternalValidator
from cmm.validation.steps import ValidationStep, ValidationStepResult
class PythonAstValidator(InternalValidator):
    name = "ast"

    def validate(self, context: ValidationContext, step: ValidationStep) -> ValidationStepResult:
        from cmm.validation.catalog import select_python_files

        files = select_python_files(context)
        findings: list[ValidationFinding] = []
        passed_files: list[str] = []
        failed_files: list[str] = []
        for rel_path in files:
            abs_path = context.project_root / rel_path
            try:
                source = abs_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError) as exc:
                findings.append(
                    ValidationFinding(
                        code="PYTHON_AST_READ_ERROR" if isinstance(exc, OSError) else "PYTHON_AST_ENCODING_ERROR",
                        message=str(exc),
                        severity=ValidationSeverity.ERROR,
                        source="python.ast",
                        file_path=rel_path,
                        blocking=True,
                    )
                )
                failed_files.append(str(rel_path))
                continue
            try:
                ast.parse(source, filename=str(abs_path))
            except SyntaxError as exc:
                findings.append(
                    ValidationFinding(
                        code="PYTHON_AST_PARSE_ERROR",
                        message=str(exc),
                        severity=ValidationSeverity.ERROR,
                        source="python.ast",
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
            id="ast-report",
            kind="ast_report",
            source="python.ast",
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
