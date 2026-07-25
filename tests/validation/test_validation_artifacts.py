from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.findings import ValidationFinding
from cmm.validation.enums import ValidationSeverity
from pathlib import Path


def test_create_and_serialize_artifact():
    f = ValidationFinding(
        code="F1",
        message="m",
        severity=ValidationSeverity.INFO,
        source="s",
    )
    meta = {"x": 1}
    a = ValidationArtifact(
        id="artifact-123",
        kind="lint_report",
        source="ruff",
        path=Path("reports/lint.json"),
        content={"issues": 1},
        findings=(f,),
        metrics={"count": 1},
        metadata=meta,
    )
    s = a.serialize()
    assert s["id"] == "artifact-123"
    assert s["path"] == "reports/lint.json"
    assert s["findings"] and s["findings"][0]["code"] == "F1"
    # isolation
    meta["x"] = 2
    assert a.metadata["x"] == 1
