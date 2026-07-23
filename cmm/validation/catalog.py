"""Factories and defaults for phase 7.3 structural validation steps."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Sequence

from cmm.validation.context import ValidationContext
from cmm.validation.enums import ValidationSeverity
from cmm.validation.findings import ValidationFinding
from cmm.validation.registry import ValidationRegistry
from cmm.validation.steps import ValidationStep, ValidationStepType
from cmm.validation.validators.ast import PythonAstValidator
from cmm.validation.validators.structural import PythonStructuralValidator
from cmm.validation.validators.syntax import PythonSyntaxValidator

_EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
}


def _normalize_relative(project_root: Path, path: Path | str) -> Path | None:
    source = Path(str(path))
    if source.is_absolute():
        try:
            return source.relative_to(project_root)
        except Exception:
            return None
    return source


def select_python_files(context: ValidationContext) -> list[Path]:
    files, _ = select_python_files_with_errors(context)
    return files


def select_python_files_with_errors(context: ValidationContext) -> tuple[list[Path], tuple[ValidationFinding, ...]]:
    project_root = context.project_root.resolve(strict=False)
    python_paths: list[Path] = []
    seen: set[Path] = set()
    errors: list[ValidationFinding] = []

    changed_files = tuple(context.changed_files or ())
    python_changed = [p for p in changed_files if str(p).endswith(".py")]
    if python_changed:
        for raw_path in python_changed:
            raw_str = str(raw_path)
            candidate = Path(raw_str)
            if candidate.is_absolute():
                candidate_path = candidate.resolve(strict=False)
                try:
                    candidate_path.relative_to(project_root)
                except Exception:
                    errors.append(
                        ValidationFinding(
                            code="PYTHON_FILE_OUTSIDE_PROJECT",
                            message=f"Changed Python file '{raw_str}' is outside the project root.",
                            severity=ValidationSeverity.ERROR,
                            source="cmm.validation.catalog",
                            file_path=Path(raw_str),
                            blocking=True,
                        )
                    )
                    continue
            else:
                candidate_path = (project_root / candidate).resolve(strict=False)
                try:
                    candidate_path.relative_to(project_root)
                except Exception:
                    errors.append(
                        ValidationFinding(
                            code="PYTHON_FILE_OUTSIDE_PROJECT",
                            message=f"Changed Python file '{raw_str}' resolves outside the project root.",
                            severity=ValidationSeverity.ERROR,
                            source="cmm.validation.catalog",
                            file_path=Path(raw_str),
                            blocking=True,
                        )
                    )
                    continue
            rel_path = Path(raw_str)
            if rel_path.is_absolute():
                try:
                    rel_path = rel_path.relative_to(project_root)
                except Exception:
                    rel_path = Path(raw_str)
            if candidate_path.exists() and candidate_path.is_file() and not candidate_path.is_symlink():
                rel_path = candidate_path.relative_to(project_root)
            else:
                errors.append(
                    ValidationFinding(
                        code="PYTHON_READ_ERROR",
                        message=f"Changed Python file '{raw_str}' does not exist or is not a regular file.",
                        severity=ValidationSeverity.ERROR,
                        source="cmm.validation.catalog",
                        file_path=Path(raw_str),
                        blocking=True,
                    )
                )
                continue
            if candidate_path.suffix != ".py":
                continue
            if rel_path not in seen:
                python_paths.append(rel_path)
                seen.add(rel_path)
        if python_paths:
            return sorted(python_paths), tuple(errors)

    for root, dirs, files in os.walk(project_root, topdown=True, followlinks=False):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(root, d)) and d not in _EXCLUDED_DIRS]
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            full_path = Path(root) / name
            if full_path.is_symlink():
                continue
            if not full_path.is_file():
                continue
            rel_path = full_path.relative_to(project_root)
            if rel_path in seen:
                continue
            seen.add(rel_path)
            python_paths.append(rel_path)

    return sorted(python_paths), tuple(errors)


def formatter_check_step(context: ValidationContext) -> ValidationStep:
    files = [str(p) for p in select_python_files(context)]
    command = (sys.executable, "-m", "ruff", "format", "--check")
    if files:
        command = command + tuple(files)
    return ValidationStep(
        name="formatter_check",
        step_type=ValidationStepType.COMMAND,
        command=command,
        required=True,
        timeout_seconds=120,
        stop_on_failure=True,
        allowed_exit_codes=(0, 1),
        working_directory=context.project_root,
        dependencies=("syntax",),
        metadata={"fix": False, "scope": files or None},
    )


def formatter_fix_step(context: ValidationContext) -> ValidationStep:
    files = [str(p) for p in select_python_files(context)]
    command = (sys.executable, "-m", "ruff", "format")
    if files:
        command = command + tuple(files)
    return ValidationStep(
        name="formatter_fix",
        step_type=ValidationStepType.COMMAND,
        command=command,
        required=False,
        timeout_seconds=120,
        stop_on_failure=True,
        allowed_exit_codes=(0,),
        working_directory=context.project_root,
        dependencies=("syntax",),
        metadata={"fix": True, "scope": files or None},
    )


def lint_check_step(context: ValidationContext) -> ValidationStep:
    files = [str(p) for p in select_python_files(context)]
    command = (sys.executable, "-m", "ruff", "check", "--output-format", "json")
    if files:
        command = command + tuple(files)
    return ValidationStep(
        name="lint_check",
        step_type=ValidationStepType.COMMAND,
        command=command,
        required=True,
        timeout_seconds=120,
        stop_on_failure=True,
        allowed_exit_codes=(0, 1),
        working_directory=context.project_root,
        dependencies=("syntax",),
        metadata={"fix": False, "scope": files or None},
    )


def lint_fix_step(context: ValidationContext) -> ValidationStep:
    files = [str(p) for p in select_python_files(context)]
    command = (sys.executable, "-m", "ruff", "check", "--fix")
    if files:
        command = command + tuple(files)
    return ValidationStep(
        name="lint_fix",
        step_type=ValidationStepType.COMMAND,
        command=command,
        required=False,
        timeout_seconds=120,
        stop_on_failure=True,
        allowed_exit_codes=(0, 1),
        working_directory=context.project_root,
        dependencies=("syntax",),
        metadata={"fix": True, "scope": files or None},
    )


def syntax_step() -> ValidationStep:
    return ValidationStep(
        name="syntax",
        step_type=ValidationStepType.INTERNAL,
        required=True,
        timeout_seconds=60,
        stop_on_failure=True,
        dependencies=(),
        metadata={"validator": "syntax"},
    )


def ast_step() -> ValidationStep:
    return ValidationStep(
        name="ast",
        step_type=ValidationStepType.INTERNAL,
        required=True,
        timeout_seconds=60,
        stop_on_failure=True,
        dependencies=("syntax",),
        metadata={"validator": "ast"},
    )


def structural_step() -> ValidationStep:
    return ValidationStep(
        name="structural",
        step_type=ValidationStepType.INTERNAL,
        required=True,
        timeout_seconds=60,
        stop_on_failure=True,
        dependencies=("ast",),
        metadata={"validator": "structural"},
    )


def change_impact_step(context: ValidationContext) -> ValidationStep:
    from cmm.validation.impact.validation import change_impact_step as _change_impact_step

    return _change_impact_step(context)


def static_type_check_step(context: ValidationContext, *, change_impact_step: ValidationStep | None = None) -> ValidationStep | None:
    from cmm.validation.static_analysis.validation import default_static_analysis_steps

    steps = default_static_analysis_steps(context, change_impact_step=change_impact_step)
    for step in steps:
        if step.name == "type_check":
            return step
    return None


def static_dead_code_step(context: ValidationContext, *, change_impact_step: ValidationStep | None = None) -> ValidationStep | None:
    from cmm.validation.static_analysis.validation import default_static_analysis_steps

    steps = default_static_analysis_steps(context, change_impact_step=change_impact_step)
    for step in steps:
        if step.name == "dead_code":
            return step
    return None


def default_static_analysis_steps(context: ValidationContext, *, change_impact_step: ValidationStep | None = None) -> tuple[ValidationStep, ...]:
    from cmm.validation.static_analysis.validation import default_static_analysis_steps as _default_static_analysis_steps

    return _default_static_analysis_steps(context, change_impact_step=change_impact_step)


def default_structural_steps(context: ValidationContext) -> tuple[ValidationStep, ...]:
    return (
        syntax_step(),
        ast_step(),
        structural_step(),
        formatter_check_step(context),
        lint_check_step(context),
    )


def build_default_validation_registry() -> ValidationRegistry:
    registry = ValidationRegistry()
    registry.register("syntax", PythonSyntaxValidator())
    registry.register("ast", PythonAstValidator())
    registry.register("structural", PythonStructuralValidator())
    from cmm.validation.impact.validation import ChangeImpactValidator

    registry.register("change_impact", ChangeImpactValidator())
    return registry
