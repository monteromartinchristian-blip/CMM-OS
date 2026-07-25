from __future__ import annotations

import json
from pathlib import Path

from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.tools.bandit import parse_bandit_results
from cmm.validation.tools.pip_audit import parse_pip_audit_results


def test_bandit_parser_builds_code_security_report(tmp_path: Path) -> None:
    payload = {
        "results": [
            {
                "filename": "pkg/module.py",
                "line_number": 12,
                "issue_severity": "HIGH",
                "issue_confidence": "HIGH",
                "issue_text": "Use of assert detected.",
                "test_id": "B101",
                "test_name": "assert_used",
                "more_info": "https://bandit.readthedocs.io/",
            }
        ]
    }
    result = parse_bandit_results(
        json.dumps(payload),
        1,
        json.dumps(payload),
        "",
        project_root=tmp_path,
        command=("bandit", "-f", "json"),
        selected_files=(Path("pkg/module.py"),),
    )
    assert result["status"] == ValidationStatus.FAILED
    finding = result["findings"][0]
    assert finding.code == "B101"
    assert finding.severity == ValidationSeverity.ERROR
    assert finding.metadata["test_name"] == "assert_used"
    assert result["artifacts"][0].kind == "code_security_report"


def test_bandit_parser_reports_missing_tool(tmp_path: Path) -> None:
    result = parse_bandit_results(
        "",
        127,
        "",
        "No module named bandit",
        project_root=tmp_path,
        command=("bandit", "-f", "json"),
    )
    assert result["status"] == ValidationStatus.ERROR
    assert result["findings"][0].code == "TOOL_NOT_AVAILABLE"
    assert result["artifacts"][0].kind == "code_security_report"


def test_pip_audit_parser_preserves_dependency_metadata(tmp_path: Path) -> None:
    payload = {
        "dependencies": [
            {
                "name": "requests",
                "version": "2.31.0",
                "vulns": [
                    {
                        "id": "CVE-2024-12345",
                        "aliases": ["PYSEC-2024-1"],
                        "fix_versions": ["2.32.0"],
                        "description": "requests is vulnerable",
                    }
                ],
            }
        ]
    }
    result = parse_pip_audit_results(
        json.dumps(payload),
        1,
        json.dumps(payload),
        "",
        project_root=tmp_path,
        command=("python", "-m", "pip_audit", "-f", "json"),
        selected_files=(Path("requirements.txt"),),
    )
    assert result["status"] == ValidationStatus.FAILED
    finding = result["findings"][0]
    assert finding.code == "DEPENDENCY_VULNERABILITY"
    assert finding.metadata["package"] == "requests"
    assert finding.metadata["installed_version"] == "2.31.0"
    assert finding.metadata["advisory_id"] == "CVE-2024-12345"
    assert finding.metadata["fixed_versions"] == ["2.32.0"]
    assert finding.metadata["aliases"] == ["PYSEC-2024-1"]
    assert result["artifacts"][0].kind == "dependency_security_report"


def test_pip_audit_parser_reports_missing_tool(tmp_path: Path) -> None:
    result = parse_pip_audit_results(
        "",
        127,
        "",
        "No module named pip_audit",
        project_root=tmp_path,
        command=("python", "-m", "pip_audit", "-f", "json"),
    )
    assert result["status"] == ValidationStatus.ERROR
    assert result["findings"][0].code == "DEPENDENCY_TOOL_UNAVAILABLE"
    assert result["artifacts"][0].kind == "dependency_security_report"
