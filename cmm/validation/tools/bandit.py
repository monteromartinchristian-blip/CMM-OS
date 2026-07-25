"""Helpers for interpreting Bandit output as structured validation findings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.findings import ValidationFinding


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


def parse_bandit_results(
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

    if stderr and _tool_unavailable(stderr):
        finding = ValidationFinding(
            code="TOOL_NOT_AVAILABLE",
            message="Bandit is not available in the current environment.",
            severity=ValidationSeverity.ERROR,
            source="bandit",
            blocking=True,
            metadata={"command": list(command_tuple), "stderr": stderr},
        )
        artifact = ValidationArtifact(
            id="bandit-result",
            kind="code_security_report",
            source="bandit",
            content={
                "command": list(command_tuple),
                "files": list(selected),
                "status": "tool_unavailable",
                "diagnostics": [],
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

    try:
        payload = json.loads(text or "{}")
    except json.JSONDecodeError:
        finding = ValidationFinding(
            code="BANDIT_PARSE_ERROR",
            message="Bandit output could not be parsed as JSON.",
            severity=ValidationSeverity.ERROR,
            source="bandit",
            blocking=True,
            metadata={"command": list(command_tuple)},
        )
        artifact = ValidationArtifact(
            id="bandit-result",
            kind="code_security_report",
            source="bandit",
            content={
                "command": list(command_tuple),
                "files": list(selected),
                "status": "parse_error",
                "diagnostics": [],
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
    if isinstance(payload, Mapping):
        for item in payload.get("results", []) or []:
            if not isinstance(item, Mapping):
                continue
            issue_text = str(
                item.get("issue_text") or "Bandit reported a security issue"
            )
            confidence = str(item.get("issue_confidence") or "").lower()
            severity = str(item.get("issue_severity") or "").lower()
            path = _safe_path(item.get("filename"), project_root)
            code = str(item.get("test_id") or item.get("test_name") or "BANDIT")
            metadata = {
                "test_name": item.get("test_name"),
                "test_id": item.get("test_id"),
                "confidence": confidence,
                "severity": severity,
                "more_info": item.get("more_info"),
                "raw": dict(item),
            }
            findings.append(
                ValidationFinding(
                    code=code,
                    message=issue_text,
                    severity=ValidationSeverity.ERROR
                    if severity in {"high", "medium"}
                    else ValidationSeverity.WARNING,
                    source="bandit",
                    file_path=path,
                    line=_coerce_int(item.get("line_number")),
                    blocking=severity in {"high", "medium"},
                    metadata=metadata,
                )
            )

    artifact = ValidationArtifact(
        id="bandit-result",
        kind="code_security_report",
        source="bandit",
        content={
            "command": list(command_tuple),
            "files": list(selected),
            "diagnostics": [finding.serialize() for finding in findings],
            "status": "diagnostics" if findings else "passed",
            "metrics": {
                "diagnostic_count": len(findings),
                "files_checked": len(selected),
            },
        },
        findings=tuple(findings),
        metrics={"diagnostic_count": len(findings), "files_checked": len(selected)},
    )
    status = (
        ValidationStatus.FAILED
        if any(f.blocking for f in findings)
        else ValidationStatus.WARNING
        if findings
        else ValidationStatus.PASSED
    )
    return {
        "status": status,
        "findings": findings,
        "artifacts": [artifact],
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
    }


def _tool_unavailable(stderr: str) -> bool:
    text = stderr.lower()
    return "no module named bandit" in text or "not found" in text


def _coerce_int(value: Any) -> int | None:
    try:
        return None if value is None else int(value)
    except (TypeError, ValueError):
        return None
