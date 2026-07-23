"""Helpers for interpreting pip-audit output as structured validation findings."""

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
    if project_root is None:
        return path
    if not path.is_absolute():
        path = project_root / path
    try:
        return path.relative_to(project_root)
    except Exception:
        return path


def parse_pip_audit_results(
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
            code="DEPENDENCY_TOOL_UNAVAILABLE",
            message="pip-audit is not available in the current environment.",
            severity=ValidationSeverity.ERROR,
            source="pip-audit",
            blocking=True,
            metadata={"command": list(command_tuple), "stderr": stderr},
        )
        artifact = ValidationArtifact(
            id="pip-audit-result",
            kind="dependency_security_report",
            source="pip-audit",
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
        return {"status": ValidationStatus.ERROR, "findings": [finding], "artifacts": [artifact], "stdout": stdout, "stderr": stderr, "exit_code": exit_code}

    try:
        payload = json.loads(text or "[]")
    except json.JSONDecodeError:
        finding = ValidationFinding(
            code="PIP_AUDIT_PARSE_ERROR",
            message="pip-audit output could not be parsed as JSON.",
            severity=ValidationSeverity.ERROR,
            source="pip-audit",
            blocking=True,
            metadata={"command": list(command_tuple)},
        )
        artifact = ValidationArtifact(
            id="pip-audit-result",
            kind="dependency_security_report",
            source="pip-audit",
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
        return {"status": ValidationStatus.ERROR, "findings": [finding], "artifacts": [artifact], "stdout": stdout, "stderr": stderr, "exit_code": exit_code}

    findings: list[ValidationFinding] = []
    dependencies = payload.get("dependencies") if isinstance(payload, Mapping) else payload
    if isinstance(dependencies, list):
        for dep in dependencies:
            if not isinstance(dep, Mapping):
                continue
            name = str(dep.get("name") or "unknown")
            version = str(dep.get("version") or "")
            vulns = dep.get("vulns") or []
            if not isinstance(vulns, list):
                continue
            for vuln in vulns:
                if not isinstance(vuln, Mapping):
                    continue
                advisory_id = str(vuln.get("id") or vuln.get("advisory") or "PIP-AUDIT")
                aliases = tuple(str(item) for item in vuln.get("aliases", ()) or ())
                fixed_versions = tuple(str(item) for item in vuln.get("fix_versions", ()) or ())
                message = str(vuln.get("description") or f"{name} has a known vulnerability")
                metadata = {
                    "package": name,
                    "installed_version": version,
                    "advisory_id": advisory_id,
                    "fixed_versions": list(fixed_versions),
                    "aliases": list(aliases),
                    "raw": dict(vuln),
                }
                findings.append(
                    ValidationFinding(
                        code="DEPENDENCY_VULNERABILITY",
                        message=message,
                        severity=ValidationSeverity.ERROR,
                        source="pip-audit",
                        blocking=True,
                        metadata=metadata,
                    )
                )

    artifact = ValidationArtifact(
        id="pip-audit-result",
        kind="dependency_security_report",
        source="pip-audit",
        content={
            "command": list(command_tuple),
            "files": list(selected),
            "diagnostics": [finding.serialize() for finding in findings],
            "status": "vulnerabilities" if findings else "passed",
            "metrics": {"diagnostic_count": len(findings), "files_checked": len(selected)},
        },
        findings=tuple(findings),
        metrics={"diagnostic_count": len(findings), "files_checked": len(selected)},
    )
    status = ValidationStatus.FAILED if findings else ValidationStatus.PASSED
    return {"status": status, "findings": findings, "artifacts": [artifact], "stdout": stdout, "stderr": stderr, "exit_code": exit_code}


def _tool_unavailable(stderr: str) -> bool:
    text = stderr.lower()
    return "no module named pip_audit" in text or "not found" in text
