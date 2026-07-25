from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Mapping

from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStep, ValidationStepType

from cmm.validation.catalog import select_python_files
from cmm.validation.impact.contracts import ChangeSet, ChangeType
from cmm.validation.impact.snapshots import ChangeSetBuilder

from .contracts import StaticAnalysisPlan, StaticAnalysisScope

def build_static_analysis_plan(
    *,
    project_root: Path,
    change_set: ChangeSet,
) -> StaticAnalysisPlan:
    root = Path(project_root).resolve(strict=False)
    scope, reason = _resolve_scope(change_set)
    files = _select_files(root, change_set, scope)
    complete = True
    if not files:
        reason = f"{reason}:no_python_files" if reason else "no_python_files"
    return StaticAnalysisPlan(
        project_root=root,
        scope=scope,
        complete=complete,
        reason=reason,
        files=tuple(files),
        change_type=change_set.change_type.value,
        public_api_changed=bool(change_set.public_api_changes),
        requires_full_suite=change_set.requires_full_suite,
        confidence=change_set.confidence,
        uncertainty=change_set.uncertainty,
        metadata={
            "change_set": change_set.serialize(),
            "change_type": change_set.change_type.value,
            "files_selected": len(files),
        },
    )


def static_type_check_step(context: ValidationContext, plan: StaticAnalysisPlan) -> ValidationStep | None:
    if not plan.files:
        return None
    from cmm.validation.security.contracts import default_command_policy

    command = (
        sys.executable,
        "-m",
        "mypy",
        "--check-untyped-defs",
        "--show-column-numbers",
        "--hide-error-context",
        "--no-color-output",
        "--no-error-summary",
        "--show-error-codes",
        "--cache-dir",
        str(_cache_dir("mypy")),
        *[str(path) for path in plan.files],
    )
    return ValidationStep(
        name="type_check",
        step_type=ValidationStepType.COMMAND,
        command=command,
        required=False,
        timeout_seconds=300,
        stop_on_failure=False,
        allowed_exit_codes=(0, 1, 2),
        working_directory=context.project_root,
        dependencies=("change_impact",),
        metadata={
            "result_parser": "mypy",
            "tool": "mypy",
            "analysis_plan": plan.serialize(),
            "analysis_scope": plan.scope.value,
            "analysis_complete": plan.complete,
            "analysis_reason": plan.reason,
            "scope": [str(path) for path in plan.files],
            "security_profile": "validation",
            "command_policy": default_command_policy().serialize(),
        },
    )


def static_dead_code_step(context: ValidationContext, plan: StaticAnalysisPlan) -> ValidationStep | None:
    if not plan.files:
        return None
    from cmm.validation.security.contracts import default_command_policy

    command = (
        sys.executable,
        "-m",
        "vulture",
        "--min-confidence",
        "60",
        *[str(path) for path in plan.files],
    )
    return ValidationStep(
        name="dead_code",
        step_type=ValidationStepType.COMMAND,
        command=command,
        required=False,
        timeout_seconds=300,
        stop_on_failure=False,
        allowed_exit_codes=(0, 1, 2, 3, 4, 5),
        working_directory=context.project_root,
        dependencies=("change_impact",),
        metadata={
            "result_parser": "vulture",
            "tool": "vulture",
            "analysis_plan": plan.serialize(),
            "analysis_scope": plan.scope.value,
            "analysis_complete": plan.complete,
            "analysis_reason": plan.reason,
            "scope": [str(path) for path in plan.files],
            "security_profile": "validation",
            "command_policy": default_command_policy().serialize(),
        },
    )


def default_static_analysis_steps(
    context: ValidationContext,
    *,
    change_impact_step: ValidationStep | None = None,
) -> tuple[ValidationStep, ...]:
    change_set = _load_change_set(context, change_impact_step)
    plan = build_static_analysis_plan(project_root=context.project_root, change_set=change_set)
    steps: list[ValidationStep] = []
    type_check = static_type_check_step(context, plan)
    dead_code = static_dead_code_step(context, plan)
    if type_check is not None:
        steps.append(type_check)
    if dead_code is not None:
        steps.append(dead_code)
    return tuple(steps)


def _load_change_set(context: ValidationContext, change_impact_step: ValidationStep | None) -> ChangeSet:
    if change_impact_step is not None:
        payload = change_impact_step.metadata.get("change_set")
        if isinstance(payload, Mapping):
            return ChangeSet.from_mapping(payload)
    builder = ChangeSetBuilder()
    return builder.build(project_root=context.project_root, changed_files=context.changed_files)


def _resolve_scope(change_set: ChangeSet) -> tuple[StaticAnalysisScope, str]:
    if change_set.change_type == ChangeType.PUBLIC_API_CHANGE or change_set.public_api_changes:
        return StaticAnalysisScope.FULL, "public_api_change"
    if change_set.requires_full_suite:
        return StaticAnalysisScope.FULL, "requires_full_suite"
    if change_set.uncertainty:
        return StaticAnalysisScope.FULL, "uncertainty"
    if change_set.confidence < 0.7:
        return StaticAnalysisScope.FULL, "low_confidence"
    return StaticAnalysisScope.AFFECTED, "affected_scope"


def _select_files(project_root: Path, change_set: ChangeSet, scope: StaticAnalysisScope) -> list[Path]:
    if scope == StaticAnalysisScope.FULL:
        return list(select_python_files(ValidationContext(project_root=project_root)))

    selected: list[Path] = []
    seen: set[Path] = set()
    for file_change in change_set.file_changes:
        candidate = file_change.after_path or file_change.before_path
        if candidate is None or not str(candidate).endswith(".py"):
            continue
        rel_path = _normalize_relative(project_root, candidate)
        if rel_path is None:
            continue
        abs_path = project_root / rel_path
        if not abs_path.exists() or not abs_path.is_file() or abs_path.is_symlink():
            continue
        if rel_path not in seen:
            selected.append(rel_path)
            seen.add(rel_path)
    return sorted(selected, key=str)


def _normalize_relative(project_root: Path, path: Path) -> Path | None:
    candidate = Path(str(path))
    if candidate.is_absolute():
        try:
            return candidate.relative_to(project_root)
        except Exception:
            return None
    return candidate


def _cache_dir(tool: str) -> Path:
    base = Path(tempfile.gettempdir()) / "cmm-os-validation-cache" / tool
    os.makedirs(base, exist_ok=True)
    return base
