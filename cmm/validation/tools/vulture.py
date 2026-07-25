"""Helpers for interpreting Vulture output as structured validation findings."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Sequence

from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.findings import ValidationFinding

_LINE_PATTERN = re.compile(r"^(?P<path>.+?):(?P<line>\d+): (?P<message>.*)$")


def _safe_path(
    path_value: str | Path | None, project_root: Path | None = None
) -> Path | None:
    if path_value is None:
        return None
    path = Path(str(path_value))
    if project_root is None:
        return path
    if not path.is_absolute():
        path = project_root / path
    try:
        return path.relative_to(project_root)
    except Exception:
        return path


def parse_vulture_results(
    raw_output: str,
    exit_code: int,
    stdout: str,
    stderr: str,
    *,
    project_root: Path | None = None,
    command: Sequence[str] | None = None,
    selected_files: Sequence[Path] | None = None,
) -> dict[str, Any]:
    command_tuple = tuple(command or ())
    selected = tuple(str(p) for p in (selected_files or ()))
    text = raw_output or stderr

    if exit_code == 0 and not text.strip():
        artifact = ValidationArtifact(
            id="vulture-result",
            kind="dead_code_report",
            source="vulture",
            content={
                "command": list(command_tuple),
                "files": list(selected),
                "diagnostics": [],
                "complete": True,
                "reason": "passed",
                "metrics": {"diagnostic_count": 0, "files_checked": len(selected)},
            },
            findings=(),
            metrics={"diagnostic_count": 0, "files_checked": len(selected)},
        )
        return {
            "status": ValidationStatus.PASSED,
            "findings": [],
            "artifacts": [artifact],
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
        }

    if stderr and (
        "no module named vulture" in stderr.lower() or "not found" in stderr.lower()
    ):
        finding = ValidationFinding(
            code="TOOL_NOT_AVAILABLE",
            message="vulture is not available in the current environment.",
            severity=ValidationSeverity.ERROR,
            source="vulture",
            blocking=True,
            metadata={"command": list(command_tuple), "stderr": stderr},
        )
        artifact = ValidationArtifact(
            id="vulture-result",
            kind="dead_code_report",
            source="vulture",
            content={
                "command": list(command_tuple),
                "files": list(selected),
                "diagnostics": [],
                "complete": False,
                "reason": "tool_unavailable",
                "metrics": {"diagnostic_count": 0, "files_checked": len(selected)},
            },
            findings=(finding,),
            metrics={"diagnostic_count": 0, "files_checked": len(selected)},
        )
        return {
            "status": ValidationStatus.ERROR,
            "findings": [finding],
            "artifacts": [artifact],
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
        }

    findings: list[ValidationFinding] = []
    for line in text.splitlines():
        match = _LINE_PATTERN.match(line.strip())
        if not match:
            continue
        message = match.group("message").strip()
        category, code = _categorize(message)
        findings.append(
            ValidationFinding(
                code=code,
                message=message,
                severity=ValidationSeverity.WARNING,
                source="vulture",
                file_path=_safe_path(match.group("path"), project_root),
                line=int(match.group("line")),
                blocking=False,
                metadata={"category": category, "raw": line},
            )
        )

    artifact = ValidationArtifact(
        id="vulture-result",
        kind="dead_code_report",
        source="vulture",
        content={
            "command": list(command_tuple),
            "files": list(selected),
            "diagnostics": [item.serialize() for item in findings],
            "complete": True,
            "reason": "diagnostics" if findings else "unknown_failure",
            "metrics": {
                "diagnostic_count": len(findings),
                "files_checked": len(selected),
            },
        },
        findings=tuple(findings),
        metrics={"diagnostic_count": len(findings), "files_checked": len(selected)},
    )
    if findings:
        return {
            "status": ValidationStatus.WARNING,
            "findings": findings,
            "artifacts": [artifact],
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
        }

    finding = ValidationFinding(
        code="VULTURE_EXECUTION_ERROR",
        message="vulture did not report structured diagnostics.",
        severity=ValidationSeverity.ERROR,
        source="vulture",
        blocking=True,
        metadata={"command": list(command_tuple), "stderr": stderr, "stdout": stdout},
    )
    artifact = ValidationArtifact(
        id="vulture-result",
        kind="dead_code_report",
        source="vulture",
        content={
            "command": list(command_tuple),
            "files": list(selected),
            "diagnostics": [],
            "complete": False,
            "reason": "parse_failure",
            "metrics": {"diagnostic_count": 0, "files_checked": len(selected)},
        },
        findings=(finding,),
        metrics={"diagnostic_count": 0, "files_checked": len(selected)},
    )
    return {
        "status": ValidationStatus.ERROR,
        "findings": [finding],
        "artifacts": [artifact],
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
    }


def _categorize(message: str) -> tuple[str, str]:
    lower = message.lower()
    if "unused import" in lower:
        return "unused_import", "VULTURE_UNUSED_IMPORT"
    if "unused variable" in lower:
        return "unused_variable", "VULTURE_UNUSED_VARIABLE"
    if "unused function" in lower:
        return "unused_function", "VULTURE_UNUSED_FUNCTION"
    if "unused method" in lower:
        return "unused_method", "VULTURE_UNUSED_METHOD"
    if "unused property" in lower:
        return "unused_property", "VULTURE_UNUSED_PROPERTY"
    if "unused class" in lower:
        return "unused_class", "VULTURE_UNUSED_CLASS"
    if "unused attribute" in lower:
        return "unused_attribute", "VULTURE_UNUSED_ATTRIBUTE"
    return "dead_code", "VULTURE_DEAD_CODE"
