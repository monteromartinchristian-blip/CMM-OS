from datetime import datetime
from pathlib import Path

import pytest

from cmm.validation.findings import ValidationFinding
from cmm.validation.enums import ValidationSeverity
from cmm.validation.errors import ValidationContractError


def test_create_and_serialize_finding():
    f = ValidationFinding(
        code="F401",
        message="Imported module is not used",
        severity=ValidationSeverity.WARNING,
        source="ruff",
        file_path=Path("src/example.py"),
        line=12,
        column=1,
        blocking=False,
        suggested_fix=None,
        documentation_url=None,
        metadata={"rule": "F401"},
    )

    s = f.serialize()
    assert s["code"] == "F401"
    assert s["severity"] == "warning"
    assert s["file_path"] == "src/example.py"
    assert s["line"] == 12
    assert s["column"] == 1
    assert s["metadata"] == {"rule": "F401"}


def test_invalid_line_column():
    with pytest.raises(ValidationContractError):
        ValidationFinding(
            code="X",
            message="m",
            severity=ValidationSeverity.INFO,
            source="s",
            line=0,
        )
    with pytest.raises(ValidationContractError):
        ValidationFinding(
            code="X",
            message="m",
            severity=ValidationSeverity.INFO,
            source="s",
            column=0,
        )


def test_required_fields_invalid():
    with pytest.raises(ValidationContractError):
        ValidationFinding(code="", message="m", severity=ValidationSeverity.INFO, source="s")
    with pytest.raises(ValidationContractError):
        ValidationFinding(code="C", message="", severity=ValidationSeverity.INFO, source="s")
    with pytest.raises(ValidationContractError):
        ValidationFinding(code="C", message="m", severity=ValidationSeverity.INFO, source="")


def test_metadata_isolation():
    meta = {"a": 1}
    f = ValidationFinding(
        code="C",
        message="m",
        severity=ValidationSeverity.INFO,
        source="s",
        metadata=meta,
    )
    meta["a"] = 2
    assert f.metadata["a"] == 1
