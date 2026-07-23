"""Helpers for interpreting Ruff formatter and lint outputs as validation findings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.findings import ValidationFinding


def _safe_path(path_value: str | Path | None, project_root: Path | None = None) -> Path | None:
    if path_value is None:
        return None
    path = Path(str(path_value))
    if not path.is_absolute() and project_root is not None:
        path = project_root / path
    if project_root is not None:
        try:
            return path.relative_to(project_root)
        except Exception:
            return path
    return path


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_ruff_results(
    raw_output: str,
    exit_code: int,
    stdout: str,
    stderr: str,
    *,
    project_root: Path | None = None,
    command: Sequence[str] | None = None,
    selected_files: Sequence[Path] | None = None,
    mode: str = "lint",
) -> dict[str, Any]:
    command_tuple = tuple(command or ())
    selected = tuple(str(p) for p in (selected_files or ()))

    if exit_code == 0:
        artifact = ValidationArtifact(
            id="ruff-result",
            kind="lint_report" if mode == "lint" else "formatter_report",
            source="ruff",
            content={
                "command": list(command_tuple),
                "files": list(selected),
                "diagnostics": [],
                "metrics": {"diagnostic_count": 0, "files_checked": len(selected) or 0},
            },
            findings=(),
            metrics={"diagnostic_count": 0, "files_checked": len(selected) or 0},
        )
        return {
            "status": ValidationStatus.PASSED,
            "findings": [],
            "artifacts": [artifact],
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
        }

    if mode == "formatter":
        if stderr and ("no module named ruff" in stderr.lower() or "not found" in stderr.lower()):
            finding = ValidationFinding(
                code="TOOL_NOT_AVAILABLE",
                message="Ruff is not available in the current environment.",
                severity=ValidationSeverity.ERROR,
                source="ruff",
                blocking=True,
                metadata={"command": list(command_tuple), "stderr": stderr},
            )
            artifact = ValidationArtifact(
                id="ruff-result",
                kind="formatter_report",
                source="ruff",
                content={"command": list(command_tuple), "files": list(selected), "diagnostics": [], "metrics": {"diagnostic_count": 0, "files_checked": len(selected) or 0}},
                findings=(finding,),
                metrics={"diagnostic_count": 0, "files_checked": len(selected) or 0},
            )
            return {"status": ValidationStatus.ERROR, "findings": [finding], "artifacts": [artifact], "stdout": stdout, "stderr": stderr, "exit_code": exit_code}
        finding = ValidationFinding(
            code="FORMAT_REQUIRED",
            message="Formatting changes are required.",
            severity=ValidationSeverity.ERROR,
            source="ruff",
            blocking=True,
            metadata={"command": list(command_tuple), "stdout": stdout, "stderr": stderr},
        )
        artifact = ValidationArtifact(
            id="ruff-result",
            kind="formatter_report",
            source="ruff",
            content={"command": list(command_tuple), "files": list(selected), "diagnostics": [{"code": finding.code, "message": finding.message}], "metrics": {"diagnostic_count": 1, "files_checked": len(selected) or 0}},
            findings=(finding,),
            metrics={"diagnostic_count": 1, "files_checked": len(selected) or 0},
        )
        return {"status": ValidationStatus.FAILED, "findings": [finding], "artifacts": [artifact], "stdout": stdout, "stderr": stderr, "exit_code": exit_code}

    if mode == "lint":
        if stderr and ("no module named ruff" in stderr.lower() or "not found" in stderr.lower()):
            finding = ValidationFinding(
                code="TOOL_NOT_AVAILABLE",
                message="Ruff is not available in the current environment.",
                severity=ValidationSeverity.ERROR,
                source="ruff",
                blocking=True,
                metadata={"command": list(command_tuple), "stderr": stderr},
            )
            artifact = ValidationArtifact(
                id="ruff-result",
                kind="lint_report",
                source="ruff",
                content={"command": list(command_tuple), "files": list(selected), "diagnostics": [], "metrics": {"diagnostic_count": 0, "files_checked": len(selected) or 0}},
                findings=(finding,),
                metrics={"diagnostic_count": 0, "files_checked": len(selected) or 0},
            )
            return {"status": ValidationStatus.ERROR, "findings": [finding], "artifacts": [artifact], "stdout": stdout, "stderr": stderr, "exit_code": exit_code}

        if not raw_output.strip():
            finding = ValidationFinding(
                code="TOOL_NOT_AVAILABLE",
                message="Ruff returned empty output for linting.",
                severity=ValidationSeverity.ERROR,
                source="ruff",
                blocking=True,
                metadata={"command": list(command_tuple), "stderr": stderr},
            )
            artifact = ValidationArtifact(
                id="ruff-result",
                kind="lint_report",
                source="ruff",
                content={"command": list(command_tuple), "files": list(selected), "diagnostics": [], "metrics": {"diagnostic_count": 0, "files_checked": len(selected) or 0}},
                findings=(finding,),
                metrics={"diagnostic_count": 0, "files_checked": len(selected) or 0},
            )
            return {"status": ValidationStatus.ERROR, "findings": [finding], "artifacts": [artifact], "stdout": stdout, "stderr": stderr, "exit_code": exit_code}

        try:
            payload = json.loads(raw_output)
        except json.JSONDecodeError:
            finding = ValidationFinding(
                code="TOOL_NOT_AVAILABLE",
                message="Ruff output could not be parsed as JSON.",
                severity=ValidationSeverity.ERROR,
                source="ruff",
                blocking=True,
                metadata={"command": list(command_tuple), "stderr": stderr},
            )
            artifact = ValidationArtifact(
                id="ruff-result",
                kind="lint_report",
                source="ruff",
                content={"command": list(command_tuple), "files": list(selected), "diagnostics": [], "metrics": {"diagnostic_count": 0, "files_checked": len(selected) or 0}},
                findings=(finding,),
                metrics={"diagnostic_count": 0, "files_checked": len(selected) or 0},
            )
            return {"status": ValidationStatus.ERROR, "findings": [finding], "artifacts": [artifact], "stdout": stdout, "stderr": stderr, "exit_code": exit_code}

        messages = payload.get("messages") if isinstance(payload, Mapping) else None
        findings: list[ValidationFinding] = []
        if isinstance(messages, list):
            for item in messages:
                if not isinstance(item, Mapping):
                    continue
                code = str(item.get("code") or "RUFF")
                message = str(item.get("message") or "Ruff reported a diagnostic")
                location = item.get("location") if isinstance(item.get("location"), Mapping) else {}
                row = _coerce_int(item.get("line_number") or location.get("row"))
                column = _coerce_int(item.get("column_number") or location.get("column"))
                filename = item.get("filename") or item.get("path")
                path = _safe_path(filename, project_root)
                end_location = item.get("end_location") if isinstance(item.get("end_location"), Mapping) else None
                metadata: dict[str, Any] = {
                    "rule_code": code,
                    "fix_applicability": item.get("fix", {}).get("applicability") if isinstance(item.get("fix"), Mapping) else None,
                    "end_location": end_location,
                    "raw": dict(item),
                }
                findings.append(
                    ValidationFinding(
                        code=code,
                        message=message,
                        severity=ValidationSeverity.ERROR,
                        source="ruff",
                        file_path=path,
                        line=row,
                        column=column,
                        blocking=True,
                        metadata=metadata,
                    )
                )
        artifact = ValidationArtifact(
            id="ruff-result",
            kind="lint_report",
            source="ruff",
            content={
                "command": list(command_tuple),
                "files": list(selected),
                "diagnostics": [f.serialize() for f in findings],
                "metrics": {"diagnostic_count": len(findings), "files_checked": len(selected) or 0},
            },
            findings=tuple(findings),
            metrics={"diagnostic_count": len(findings), "files_checked": len(selected) or 0},
        )
        status = ValidationStatus.FAILED if findings else ValidationStatus.PASSED
        return {"status": status, "findings": findings, "artifacts": [artifact], "stdout": stdout, "stderr": stderr, "exit_code": exit_code}

    finding = ValidationFinding(
        code="RUFF_EXECUTION_ERROR",
        message="Ruff did not complete successfully.",
        severity=ValidationSeverity.ERROR,
        source="ruff",
        blocking=True,
        metadata={"command": list(command_tuple), "stderr": stderr},
    )
    artifact = ValidationArtifact(
        id="ruff-result",
        kind="lint_report" if mode == "lint" else "formatter_report",
        source="ruff",
        content={"command": list(command_tuple), "files": list(selected), "diagnostics": [], "metrics": {"diagnostic_count": 0, "files_checked": len(selected) or 0}},
        findings=(finding,),
        metrics={"diagnostic_count": 0, "files_checked": len(selected) or 0},
    )
    return {"status": ValidationStatus.ERROR, "findings": [finding], "artifacts": [artifact], "stdout": stdout, "stderr": stderr, "exit_code": exit_code}
