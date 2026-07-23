from __future__ import annotations

from pathlib import Path

from cmm.validation.context import ValidationContext
from cmm.validation.testing_catalog import default_testing_steps


def _write_test(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("def test_sample():\n    assert True\n", encoding="utf-8")


def test_default_testing_steps_do_not_duplicate_names(tmp_path: Path) -> None:
    _write_test(tmp_path / "tests" / "test_sample.py")

    context = ValidationContext(project_root=tmp_path, changed_files=(Path("tests/test_sample.py"),))
    steps = default_testing_steps(context)

    names = [step.name for step in steps]
    assert len(names) == len(set(names))
    assert names[0] == "affected_tests"
