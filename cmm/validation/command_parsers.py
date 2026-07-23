"""Adapters that convert raw command outputs into structured validation findings."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cmm.validation.artifacts import ValidationArtifact
from cmm.validation.context import ValidationContext
from cmm.validation.enums import ValidationSeverity, ValidationStatus
from cmm.validation.findings import ValidationFinding
from cmm.validation.steps import ValidationStep, ValidationStepResult
from cmm.validation.tools.ruff import parse_ruff_results


class CommandResultParser:
    def parse(self, context: ValidationContext, step: ValidationStep, result: ValidationStepResult) -> ValidationStepResult:
        if step.name not in {"formatter_check", "formatter_fix", "lint_check", "lint_fix"}:
            return result
        if step.name.startswith("formatter"):
            parsed = parse_ruff_results(result.stdout, result.exit_code or 0, result.stdout, result.stderr, project_root=context.project_root, command=step.command, selected_files=tuple(select_files(step)), mode="formatter")
        else:
            parsed = parse_ruff_results(result.stdout, result.exit_code or 0, result.stdout, result.stderr, project_root=context.project_root, command=step.command, selected_files=tuple(select_files(step)), mode="lint")
        status = parsed["status"]
        findings = tuple(parsed["findings"])
        artifacts = tuple(parsed["artifacts"])
        return ValidationStepResult(
            name=result.name,
            status=status,
            exit_code=result.exit_code,
            duration_ms=result.duration_ms,
            stdout=result.stdout,
            stderr=result.stderr,
            findings=findings,
            artifacts=artifacts,
            started_at=result.started_at,
            completed_at=result.completed_at,
            metadata={**dict(result.metadata or {}), "parser": "ruff"},
        )


def select_files(step: ValidationStep) -> list[Path]:
    scope = step.metadata.get("scope")
    if not scope:
        return []
    return [Path(str(item)) for item in scope]
