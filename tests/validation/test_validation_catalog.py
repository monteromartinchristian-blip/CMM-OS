from __future__ import annotations

from pathlib import Path

from cmm.validation.catalog import (
    formatter_check_step,
    lint_check_step,
    syntax_step,
    ast_step,
    structural_step,
    default_structural_steps,
    build_default_validation_registry,
)
from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStepType


def test_catalog_steps_have_expected_names_and_dependencies(tmp_path: Path):
    ctx = ValidationContext(project_root=tmp_path)
    steps = default_structural_steps(ctx)
    names = [step.name for step in steps]
    assert names == ["syntax", "ast", "structural", "formatter_check", "lint_check"]
    assert steps[0].dependencies == ()
    assert steps[1].dependencies == ("syntax",)
    assert steps[2].dependencies == ("ast",)


def test_catalog_steps_are_command_or_internal_and_required(tmp_path: Path):
    ctx = ValidationContext(project_root=tmp_path)
    assert formatter_check_step(ctx).step_type == ValidationStepType.COMMAND
    assert lint_check_step(ctx).step_type == ValidationStepType.COMMAND
    assert syntax_step().step_type == ValidationStepType.INTERNAL
    assert ast_step().step_type == ValidationStepType.INTERNAL
    assert structural_step().step_type == ValidationStepType.INTERNAL


def test_default_registry_contains_internal_validators():
    registry = build_default_validation_registry()
    assert registry.has("syntax")
    assert registry.has("ast")
    assert registry.has("structural")
