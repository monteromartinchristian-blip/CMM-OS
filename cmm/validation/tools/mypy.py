"""Helpers for interpreting mypy output as structured validation findings."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Sequence

from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.findings import ValidationFinding

_LINE_PATTERN = re.compile(
    r"^(?P<path>.+?):(?P<line>\d+)(?::(?P<column>\d+))?: (?P<kind>error|note|warning): (?P<message>.*?)(?:  \[(?P<code>[^\]]+)\])?$"
)


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


def parse_mypy_results(
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

    if exit_code == 0:
        artifact = ValidationArtifact(
            id="mypy-result",
            kind="type_check_report",
            source="mypy",
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
        "no module named mypy" in stderr.lower() or "not found" in stderr.lower()
    ):
        finding = ValidationFinding(
            code="TOOL_NOT_AVAILABLE",
            message="mypy is not available in the current environment.",
            severity=ValidationSeverity.ERROR,
            source="mypy",
            blocking=True,
            metadata={"command": list(command_tuple), "stderr": stderr},
        )
        artifact = ValidationArtifact(
            id="mypy-result",
            kind="type_check_report",
            source="mypy",
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
        if match.group("kind") == "note":
            continue
        code = match.group("code") or "error"
        category = _categorize(code, match.group("message"))
        file_path = _safe_path(match.group("path"), project_root)
        findings.append(
            ValidationFinding(
                code=category,
                message=match.group("message").strip(),
                severity=ValidationSeverity.WARNING,
                source="mypy",
                file_path=file_path,
                line=int(match.group("line")),
                column=int(match.group("column")) if match.group("column") else None,
                blocking=False,
                metadata={
                    "mypy_code": code,
                    "mypy_kind": match.group("kind"),
                    "raw": line,
                },
            )
        )

    artifact = ValidationArtifact(
        id="mypy-result",
        kind="type_check_report",
        source="mypy",
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
    status = ValidationStatus.WARNING if findings else ValidationStatus.ERROR
    if findings:
        return {
            "status": status,
            "findings": findings,
            "artifacts": [artifact],
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
        }

    finding = ValidationFinding(
        code="MYPY_EXECUTION_ERROR",
        message="mypy did not report structured diagnostics.",
        severity=ValidationSeverity.ERROR,
        source="mypy",
        blocking=True,
        metadata={"command": list(command_tuple), "stderr": stderr, "stdout": stdout},
    )
    artifact = ValidationArtifact(
        id="mypy-result",
        kind="type_check_report",
        source="mypy",
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


def _categorize(code: str, message: str) -> str:
    normalized = code.replace("-", "_").lower()
    if normalized in {"name_defined", "used_before_def", "possibly_undefined"}:
        return "MYPY_UNDEFINED_REFERENCE"
    if normalized in {"return_value", "return"}:
        return "MYPY_INCONSISTENT_RETURN"
    if normalized in {
        "call_arg",
        "arg_type",
        "call_overload",
        "assignment",
        "operator",
        "union_attr",
        "valid_type",
        "typeddict_item",
        "index",
        "misc",
    }:
        return "MYPY_TYPE_ERROR"
    if normalized in {"override", "no_overload_impl"}:
        return "MYPY_SIGNATURE_INCOMPATIBLE"
    if "undefined" in message.lower():
        return "MYPY_UNDEFINED_REFERENCE"
    return "MYPY_STATIC_ERROR"
