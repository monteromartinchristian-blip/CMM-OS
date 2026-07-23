"""Adapters that convert raw command outputs into structured validation findings."""

from __future__ import annotations

from pathlib import Path

from cmm.validation.context import ValidationContext
from cmm.validation.steps import ValidationStep, ValidationStepResult
from cmm.validation.tools.mypy import parse_mypy_results
from cmm.validation.tools.ruff import parse_ruff_results
from cmm.validation.tools.vulture import parse_vulture_results


class CommandResultParser:
    def parse(self, context: ValidationContext, step: ValidationStep, result: ValidationStepResult) -> ValidationStepResult:
        parser = str(step.metadata.get("result_parser") or step.name)
        selected_files = tuple(select_files(step))
        if parser in {"ruff", "formatter_check", "formatter_fix", "lint_check", "lint_fix"}:
            mode = "formatter" if step.name.startswith("formatter") else "lint"
            parsed = parse_ruff_results(
                result.stdout,
                result.exit_code or 0,
                result.stdout,
                result.stderr,
                project_root=context.project_root,
                command=step.command,
                selected_files=selected_files,
                mode=mode,
            )
        elif parser in {"mypy", "type_check"}:
            parsed = parse_mypy_results(
                result.stdout,
                result.exit_code or 0,
                result.stdout,
                result.stderr,
                project_root=context.project_root,
                command=step.command,
                selected_files=selected_files,
            )
        elif parser in {"vulture", "dead_code"}:
            parsed = parse_vulture_results(
                result.stdout,
                result.exit_code or 0,
                result.stdout,
                result.stderr,
                project_root=context.project_root,
                command=step.command,
                selected_files=selected_files,
            )
        else:
            return result
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
            metadata={**dict(result.metadata or {}), "parser": parser},
        )


def select_files(step: ValidationStep) -> list[Path]:
    for key in ("scope", "files", "analysis_files", "scope_files"):
        scope = step.metadata.get(key)
        if scope:
            return [Path(str(item)) for item in scope]
    return []
