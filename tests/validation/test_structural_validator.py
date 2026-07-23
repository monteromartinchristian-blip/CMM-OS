from __future__ import annotations

from pathlib import Path

from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStep, ValidationStepType
from cmm.validation.validators.structural import PythonStructuralValidator


def test_structural_validator_detects_duplicates(tmp_path: Path):
    path = tmp_path / "module.py"
    path.write_text(
        "class A:\n    pass\n\nclass A:\n    pass\n\n\ndef f():\n    return 1\n\ndef f():\n    return 2\n",
        encoding="utf-8",
    )
    ctx = ValidationContext(project_root=tmp_path, changed_files=(Path("module.py"),))

    result = PythonStructuralValidator().validate(ctx, ValidationStep(name="structural", step_type=ValidationStepType.INTERNAL))

    assert result.status.value == "failed"
    assert any(f.code == "DUPLICATE_TOP_LEVEL_CLASS" for f in result.findings)
    assert any(f.code == "DUPLICATE_TOP_LEVEL_FUNCTION" for f in result.findings)


def test_structural_validator_detects_duplicate_imports_and_methods(tmp_path: Path):
    path = tmp_path / "module.py"
    path.write_text(
        "import os\nimport os\n\nfrom pkg import Item\nfrom pkg import Item\n\nclass C:\n    def m(self):\n        return 1\n\n    def m(self):\n        return 2\n",
        encoding="utf-8",
    )
    ctx = ValidationContext(project_root=tmp_path, changed_files=(Path("module.py"),))

    result = PythonStructuralValidator().validate(ctx, ValidationStep(name="structural", step_type=ValidationStepType.INTERNAL))

    assert any(f.code == "DUPLICATE_IMPORT" for f in result.findings)
    assert any(f.code == "DUPLICATE_CLASS_METHOD" for f in result.findings)
