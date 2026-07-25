from __future__ import annotations

from cmm.validation.tools.ruff import parse_ruff_results
from cmm.validation.steps import ValidationStep
from cmm.validation.context import ValidationContext


def test_parse_ruff_results_empty_json():
    result = parse_ruff_results("{}", 0, "", "")
    assert result["status"] == "passed"
    assert result["findings"] == []


def test_parse_ruff_results_with_single_diagnostic():
    payload = '{"violation_count": 1, "messages": [{"code": "F401", "message": "unused import", "filename": "src/a.py", "line_number": 1, "column_number": 2, "fix": {"applicability": "unsafe"}}]}'
    result = parse_ruff_results(payload, 1, "", "")
    assert result["status"] == "failed"
    assert len(result["findings"]) == 1
    finding = result["findings"][0]
    assert finding.code == "F401"
    assert finding.file_path is not None
    assert finding.line == 1
    assert finding.column == 2


def test_parse_ruff_results_invalid_json():
    result = parse_ruff_results("{not-json", 2, "stderr", "")
    assert result["status"] == "error"
    assert result["findings"][0].code == "TOOL_NOT_AVAILABLE"
