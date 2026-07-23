from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Any, Optional

from .context import ValidationContext
from .enums import ValidationStatus
from .steps import ValidationStep, ValidationStepType, ValidationStepResult
from .registry import ValidationRegistry
from .exceptions import ValidationExecutionError


@dataclass(slots=True)
class ValidationExecutor:
    """Executes validation steps (command or internal)."""

    def _build_environment(self, context_env: Mapping[str, str], step_env: Mapping[str, str]) -> Mapping[str, str]:
        env = dict(os.environ)  # base
        env.update(context_env or {})
        env.update(step_env or {})  # step has priority
        return env

    def _select_cwd(self, context: ValidationContext, step: ValidationStep) -> Optional[Path]:
        return step.working_directory or context.project_root

    def execute(self, context: ValidationContext, step: ValidationStep, registry: Optional[ValidationRegistry] = None) -> ValidationStepResult:
        if step.step_type == ValidationStepType.COMMAND:
            return self._execute_command(context, step)
        elif step.step_type == ValidationStepType.INTERNAL:
            if registry is None:
                return ValidationStepResult(
                    name=step.name,
                    status=ValidationStatus.ERROR,
                    stderr="No registry provided for internal step",
                    metadata={"error": "missing_registry"},
                )
            return self._execute_internal(context, step, registry)
        else:  # pragma: no cover - defensive
            return ValidationStepResult(name=step.name, status=ValidationStatus.ERROR, stderr="Unknown step type")

    def _execute_command(self, context: ValidationContext, step: ValidationStep) -> ValidationStepResult:
        env = self._build_environment(context.environment, step.environment)
        cwd = self._select_cwd(context, step)
        started_at = datetime.now(timezone.utc)
        start = time.monotonic()
        try:
            completed = subprocess.run(
                list(step.command),
                cwd=str(cwd) if cwd is not None else None,
                env=env,
                capture_output=True,
                text=True,
                timeout=step.timeout_seconds,
                shell=False,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            status = ValidationStatus.PASSED if completed.returncode in step.allowed_exit_codes else ValidationStatus.FAILED
            return ValidationStepResult(
                name=step.name,
                status=status,
                exit_code=completed.returncode,
                duration_ms=duration_ms,
                stdout=completed.stdout or "",
                stderr=completed.stderr or "",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                metadata={"executor": "command"},
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ValidationStepResult(
                name=step.name,
                status=ValidationStatus.TIMED_OUT,
                exit_code=None,
                duration_ms=duration_ms,
                stdout=exc.stdout or "",
                stderr=(exc.stderr or "") + f"\nTimeout after {step.timeout_seconds}s",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                metadata={"executor": "command", "timeout_seconds": step.timeout_seconds},
            )
        except FileNotFoundError as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ValidationStepResult(
                name=step.name,
                status=ValidationStatus.ERROR,
                exit_code=None,
                duration_ms=duration_ms,
                stdout="",
                stderr=str(exc),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                metadata={"executor": "command", "error": "executable_not_found"},
            )
        except Exception as exc:  # pragma: no cover - unexpected
            duration_ms = int((time.monotonic() - start) * 1000)
            return ValidationStepResult(
                name=step.name,
                status=ValidationStatus.ERROR,
                exit_code=None,
                duration_ms=duration_ms,
                stdout="",
                stderr=str(exc),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                metadata={"executor": "command", "error": "unexpected_exception"},
            )

    def _execute_internal(self, context: ValidationContext, step: ValidationStep, registry: ValidationRegistry) -> ValidationStepResult:
        started_at = datetime.now(timezone.utc)
        start = time.monotonic()
        try:
            validator = registry.get(step.name)
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ValidationStepResult(
                name=step.name,
                status=ValidationStatus.ERROR,
                duration_ms=duration_ms,
                stdout="",
                stderr=str(exc),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                metadata={"executor": "internal", "error": "validator_not_found"},
            )
        try:
            result = validator.validate(context, step)
            # ensure result is of expected type and with correct name
            if not isinstance(result, ValidationStepResult):  # type: ignore
                raise ValidationExecutionError(code="invalid_result", message="Internal validator returned invalid result type")
            if result.name != step.name:
                result = ValidationStepResult(
                    name=step.name,
                    status=result.status,
                    exit_code=result.exit_code,
                    duration_ms=result.duration_ms or int((time.monotonic() - start) * 1000),
                    stdout=result.stdout,
                    stderr=result.stderr,
                    findings=result.findings,
                    artifacts=result.artifacts,
                    started_at=result.started_at or started_at,
                    completed_at=result.completed_at or datetime.now(timezone.utc),
                    metadata={**dict(result.metadata or {}), "original_step_name": result.name},
                )
            # ensure timestamps and duration are set
            duration_ms = result.duration_ms if result.duration_ms >= 0 else int((time.monotonic() - start) * 1000)
            if result.started_at is None or result.completed_at is None:
                result = ValidationStepResult(
                    name=result.name,
                    status=result.status,
                    exit_code=result.exit_code,
                    duration_ms=duration_ms,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    findings=result.findings,
                    artifacts=result.artifacts,
                    started_at=result.started_at or started_at,
                    completed_at=result.completed_at or datetime.now(timezone.utc),
                    metadata=dict(result.metadata or {}),
                )
            return result
        except ValidationExecutionError as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ValidationStepResult(
                name=step.name,
                status=ValidationStatus.ERROR,
                duration_ms=duration_ms,
                stdout="",
                stderr=f"{exc.code}: {exc.message}",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                metadata={"executor": "internal", "error": exc.code},
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            return ValidationStepResult(
                name=step.name,
                status=ValidationStatus.ERROR,
                duration_ms=duration_ms,
                stdout="",
                stderr=str(exc),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                metadata={"executor": "internal", "error": "unexpected_exception"},
            )


__all__ = ["ValidationExecutor"]
