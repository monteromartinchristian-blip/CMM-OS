from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Any, Optional

from .artifacts import ValidationArtifact
from .context import ValidationContext
from .enums import ValidationStatus, ValidationSeverity
from .steps import ValidationStep, ValidationStepType, ValidationStepResult
from .registry import ValidationRegistry
from .exceptions import ValidationExecutionError
from .findings import ValidationFinding
from .command_parsers import CommandResultParser
from .security.contracts import CommandPolicy, default_command_policy
from .security.validation import evaluate_command_policy


@dataclass(slots=True)
class ValidationExecutor:
    """Executes validation steps (command or internal)."""

    def _build_environment(
        self,
        context_env: Mapping[str, str],
        step_env: Mapping[str, str],
        policy: CommandPolicy,
        *,
        strict: bool,
    ) -> Mapping[str, str]:
        if strict:
            env = {
                key: value
                for key, value in os.environ.items()
                if policy.allows_environment_key(key)
            }  # base is filtered
        else:
            env = dict(os.environ)
        env.update(context_env or {})
        env.update(step_env or {})  # step has priority
        return env

    def _select_cwd(
        self, context: ValidationContext, step: ValidationStep
    ) -> Optional[Path]:
        return step.working_directory or context.project_root

    def _resolve_command_policy(
        self, context: ValidationContext, step: ValidationStep
    ) -> CommandPolicy:
        for candidate in (
            step.metadata.get("command_policy"),
            context.metadata.get("command_policy"),
        ):
            if isinstance(candidate, Mapping):
                return CommandPolicy.from_mapping(candidate)
        return default_command_policy()

    def _security_profile(
        self, context: ValidationContext, step: ValidationStep
    ) -> str | None:
        for candidate in (
            step.metadata.get("security_profile"),
            context.metadata.get("security_profile"),
        ):
            if candidate is not None:
                return str(candidate)
        return None

    def execute(
        self,
        context: ValidationContext,
        step: ValidationStep,
        registry: Optional[ValidationRegistry] = None,
    ) -> ValidationStepResult:
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
            return ValidationStepResult(
                name=step.name,
                status=ValidationStatus.ERROR,
                stderr="Unknown step type",
            )

    def _execute_command(
        self, context: ValidationContext, step: ValidationStep
    ) -> ValidationStepResult:
        profile = self._security_profile(context, step)
        policy = self._resolve_command_policy(context, step)
        cwd = self._select_cwd(context, step)
        env = self._build_environment(
            context.environment,
            step.environment,
            policy,
            strict=profile == "validation",
        )
        started_at = datetime.now(timezone.utc)
        start = time.monotonic()
        violations = ()
        if profile == "validation":
            violations = evaluate_command_policy(
                command=step.command,
                working_directory=cwd,
                project_root=context.project_root,
                environment=env,
                policy=policy,
                step_name=step.name,
                security_profile=profile,
            )
        if violations:
            duration_ms = int((time.monotonic() - start) * 1000)
            artifact = ValidationArtifact(
                id="command-policy",
                kind="command_policy_report",
                source="validation.security",
                content={
                    "step_name": step.name,
                    "command_policy": policy.serialize(),
                    "violations": [finding.serialize() for finding in violations],
                    "working_directory": None if cwd is None else str(cwd),
                },
                findings=violations,
                metrics={"violation_count": len(violations)},
            )
            return ValidationStepResult(
                name=step.name,
                status=ValidationStatus.ERROR,
                exit_code=None,
                duration_ms=duration_ms,
                stdout="",
                stderr="Command blocked by security policy",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                findings=violations,
                artifacts=(artifact,),
                metadata={
                    "executor": "command",
                    "error": "command_policy_violation",
                    "command_policy": policy.serialize(),
                    "security_profile": profile,
                },
            )
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
            status = (
                ValidationStatus.PASSED
                if completed.returncode in step.allowed_exit_codes
                else ValidationStatus.FAILED
            )
            result = ValidationStepResult(
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
            return CommandResultParser().parse(context, step, result)
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
                metadata={
                    "executor": "command",
                    "timeout_seconds": step.timeout_seconds,
                },
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

    def _execute_internal(
        self,
        context: ValidationContext,
        step: ValidationStep,
        registry: ValidationRegistry,
    ) -> ValidationStepResult:
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
                raise ValidationExecutionError(
                    code="invalid_result",
                    message="Internal validator returned invalid result type",
                )
            if result.name != step.name:
                # normalize and attach a structured warning finding
                name_mismatch_finding = ValidationFinding(
                    code="INTERNAL_NAME_MISMATCH",
                    message=f"Validator returned result for '{result.name}' instead of '{step.name}'",
                    severity=ValidationSeverity.WARNING,
                    source="validation.internal",
                    blocking=False,
                    metadata={"original_step_name": result.name},
                )
                result = ValidationStepResult(
                    name=step.name,
                    status=result.status,
                    exit_code=result.exit_code,
                    duration_ms=result.duration_ms
                    or int((time.monotonic() - start) * 1000),
                    stdout=result.stdout,
                    stderr=result.stderr,
                    findings=tuple(result.findings) + (name_mismatch_finding,),
                    artifacts=result.artifacts,
                    started_at=result.started_at or started_at,
                    completed_at=result.completed_at or datetime.now(timezone.utc),
                    metadata={
                        **dict(result.metadata or {}),
                        "original_step_name": result.name,
                    },
                )
            # ensure timestamps and duration are set
            duration_ms = (
                result.duration_ms
                if result.duration_ms >= 0
                else int((time.monotonic() - start) * 1000)
            )
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
