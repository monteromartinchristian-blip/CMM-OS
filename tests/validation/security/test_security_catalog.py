from __future__ import annotations

from pathlib import Path

from cmm.validation import ValidationContext
from cmm.validation.catalog import build_default_validation_registry, change_impact_step
from cmm.validation.security import (
    SecurityScope,
    bandit_step,
    default_security_steps,
    pip_audit_step,
    security_step,
)
from cmm.validation.testing_defaults import default_validation_steps


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_security_step_uses_change_impact_metadata(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "module.py", "def func(x):\n    return x\n")
    context = ValidationContext(
        project_root=tmp_path, changed_files=(Path("pkg/module.py"),)
    )

    impact = change_impact_step(context)
    step = security_step(context, change_impact_step=impact, planned_steps=(impact,))

    assert step.name == "security"
    assert step.step_type.value == "internal"
    assert step.dependencies == ("change_impact",)
    assert step.metadata["validator"] == "security"
    assert step.metadata["security_plan"]["scope"] in {
        SecurityScope.AFFECTED.value,
        SecurityScope.FULL.value,
    }


def test_security_step_is_inserted_before_tests(tmp_path: Path) -> None:
    _write(tmp_path / "pkg" / "module.py", "def func(x):\n    return x\n")
    _write(tmp_path / "tests" / "test_module.py", "def test_func():\n    assert True\n")
    context = ValidationContext(
        project_root=tmp_path, changed_files=(Path("pkg/module.py"),)
    )

    steps = default_validation_steps(context)
    names = [step.name for step in steps]
    assert "security" in names
    assert names.index("security") < names.index("affected_tests")


def test_default_security_steps_returns_internal_step(tmp_path: Path) -> None:
    context = ValidationContext(project_root=tmp_path)
    steps = default_security_steps(context)
    assert len(steps) == 1
    assert steps[0].step_type.value == "internal"


def test_optional_security_steps_include_profile_when_tools_are_available(
    tmp_path: Path, monkeypatch
) -> None:
    context = ValidationContext(
        project_root=tmp_path, changed_files=(Path("pkg/module.py"),)
    )
    impact = change_impact_step(context)

    monkeypatch.setattr(
        "cmm.validation.security.validation._tool_available", lambda name: True
    )

    bandit = bandit_step(context, change_impact_step=impact)
    pip_audit = pip_audit_step(context, change_impact_step=impact)

    assert bandit is not None
    assert pip_audit is not None
    assert bandit.metadata["security_profile"] == "validation"
    assert pip_audit.metadata["security_profile"] == "validation"


def test_security_registry_is_present() -> None:
    registry = build_default_validation_registry()
    assert registry.has("security")
