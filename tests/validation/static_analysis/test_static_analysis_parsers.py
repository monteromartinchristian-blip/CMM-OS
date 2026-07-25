from __future__ import annotations

from pathlib import Path

from cmm.validation.tools.mypy import parse_mypy_results
from cmm.validation.tools.vulture import parse_vulture_results


def test_parse_mypy_results_detects_undefined_reference() -> None:
    payload = '/tmp/project/pkg/module.py:2:12: error: Name "missing" is not defined  [name-defined]'

    result = parse_mypy_results(
        payload,
        1,
        payload,
        "",
        project_root=Path("/tmp/project"),
        command=("python", "-m", "mypy"),
        selected_files=(Path("pkg/module.py"),),
    )

    assert result["status"].value == "warning"
    assert result["findings"][0].code == "MYPY_UNDEFINED_REFERENCE"
    assert result["findings"][0].file_path == Path("pkg/module.py")
    assert result["artifacts"][0].content["complete"] is True


def test_parse_vulture_results_detects_dead_code() -> None:
    payload = "/tmp/project/pkg/module.py:1: unused function 'unused' (60% confidence)"

    result = parse_vulture_results(
        payload,
        3,
        payload,
        "",
        project_root=Path("/tmp/project"),
        command=("python", "-m", "vulture"),
        selected_files=(Path("pkg/module.py"),),
    )

    assert result["status"].value == "warning"
    assert result["findings"][0].code == "VULTURE_UNUSED_FUNCTION"
    assert result["findings"][0].file_path == Path("pkg/module.py")
    assert result["artifacts"][0].kind == "dead_code_report"
