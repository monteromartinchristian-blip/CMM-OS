"""Custom validator contracts, registry, and adapters (Phase 7.9 - Block 1)."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from typing import (
    Any,
    Dict,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    runtime_checkable,
)

from .context import ValidationContext
from .enums import ValidationSeverity, ValidationStatus
from .exceptions import ValidationRegistryError
from .findings import ValidationFinding
from .registry import ValidationRegistry
from .steps import ValidationStep, ValidationStepResult, ValidationStepType

NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*$")


@runtime_checkable
class CustomValidator(Protocol):
    """Public protocol contract for custom validators in CMM OS."""

    name: str

    def validate(self, context: ValidationContext) -> ValidationStepResult:
        """Execute validation against context and return a ValidationStepResult."""
        ...


class CustomValidatorAdapter:
    """Adapts a CustomValidator (validate(context)) to an InternalValidator (validate(context, step))."""

    __slots__ = ("_validator", "_step_name", "_logical_name")

    def __init__(self, validator: CustomValidator, step_name: str) -> None:
        self._validator = validator
        self._step_name = step_name
        self._logical_name = getattr(validator, "name", "")

    @property
    def name(self) -> str:
        return self._step_name

    def validate(self, context: ValidationContext, step: ValidationStep) -> ValidationStepResult:
        started_at = datetime.now(timezone.utc)
        t0 = time.monotonic()

        current_name = getattr(self._validator, "name", None)
        if current_name != self._logical_name:
            duration_ms = int((time.monotonic() - t0) * 1000)
            finding = ValidationFinding(
                code="CUSTOM_VALIDATOR_NAME_MUTATED",
                message=f"Custom validator name mutated from '{self._logical_name}' to '{current_name}'",
                severity=ValidationSeverity.ERROR,
                source="validation.custom",
                blocking=True,
            )
            return ValidationStepResult(
                name=step.name,
                status=ValidationStatus.ERROR,
                duration_ms=duration_ms,
                stderr=f"custom_validator_name_changed: Validator name mutated from '{self._logical_name}' to '{current_name}'",
                findings=(finding,),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                metadata={
                    "executor": "custom",
                    "error": "custom_validator_name_changed",
                    "registered_name": self._logical_name,
                    "current_name": str(current_name),
                },
            )

        try:
            res = self._validator.validate(context)
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            exc_type = type(exc).__name__
            finding = ValidationFinding(
                code="CUSTOM_VALIDATOR_EXECUTION_ERROR",
                message=f"Custom validator '{self._logical_name}' raised {exc_type}.",
                severity=ValidationSeverity.ERROR,
                source="validation.custom",
                blocking=True,
            )
            return ValidationStepResult(
                name=step.name,
                status=ValidationStatus.ERROR,
                duration_ms=duration_ms,
                stderr=f"custom_validator_execution_error: Custom validator '{self._logical_name}' raised {exc_type}.",
                findings=(finding,),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                metadata={
                    "executor": "custom",
                    "error": "custom_validator_execution_error",
                    "exception_type": exc_type,
                    "validator_name": self._logical_name,
                },
            )

        duration_ms = int((time.monotonic() - t0) * 1000)

        if not isinstance(res, ValidationStepResult):
            finding = ValidationFinding(
                code="INVALID_CUSTOM_VALIDATOR_RESULT",
                message=f"Custom validator '{self._logical_name}' returned invalid result type: {type(res).__name__}",
                severity=ValidationSeverity.ERROR,
                source="validation.custom",
                blocking=True,
            )
            return ValidationStepResult(
                name=step.name,
                status=ValidationStatus.ERROR,
                duration_ms=duration_ms,
                stderr=f"invalid_custom_validator_result: Validator returned {type(res).__name__} instead of ValidationStepResult",
                findings=(finding,),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                metadata={
                    "executor": "custom",
                    "error": "invalid_custom_validator_result",
                    "received_type": type(res).__name__,
                    "validator_name": self._logical_name,
                },
            )

        res_duration = res.duration_ms if res.duration_ms > 0 else duration_ms
        res_started = res.started_at or started_at
        res_completed = res.completed_at or datetime.now(timezone.utc)
        meta = dict(res.metadata or {})
        meta["custom_validator_name"] = self._logical_name

        return ValidationStepResult(
            name=step.name,
            status=res.status,
            exit_code=res.exit_code,
            duration_ms=res_duration,
            stdout=res.stdout,
            stderr=res.stderr,
            findings=res.findings,
            artifacts=res.artifacts,
            started_at=res_started,
            completed_at=res_completed,
            metadata=meta,
        )


def _validate_name_string(name: Any) -> str:
    if not isinstance(name, str) or not name or not name.strip():
        raise ValidationRegistryError(
            code="invalid_custom_validator_name",
            message="Custom validator name must be a non-empty string",
        )
    if name.startswith("custom."):
        raise ValidationRegistryError(
            code="invalid_custom_validator_name",
            message="Custom validator logical name must not start with 'custom.'",
        )
    if not NAME_PATTERN.match(name):
        raise ValidationRegistryError(
            code="invalid_custom_validator_name",
            message=f"Custom validator name '{name}' is invalid; must start with a lowercase letter and contain only lowercase letters, digits, hyphens, and underscores without trailing or double separators.",
        )
    return name


def build_custom_validation_step(
    validator: CustomValidator,
    *,
    validation_registry: Optional[ValidationRegistry] = None,
) -> ValidationStep:
    """Build a ValidationStep from a CustomValidator instance."""
    if not hasattr(validator, "name"):
        raise ValidationRegistryError(
            code="invalid_custom_validator",
            message="Custom validator must have a 'name' attribute",
        )
    val_name = _validate_name_string(getattr(validator, "name"))
    if not hasattr(validator, "validate") or not callable(getattr(validator, "validate")):
        raise ValidationRegistryError(
            code="invalid_custom_validator",
            message="Custom validator must implement a callable 'validate(context)' method",
        )

    step_name = f"custom.{val_name}"

    step = ValidationStep(
        name=step_name,
        step_type=ValidationStepType.INTERNAL,
        required=True,
        timeout_seconds=60,
        stop_on_failure=True,
        metadata={"custom_validator": True, "custom_validator_name": val_name},
    )

    if validation_registry is not None:
        adapter = CustomValidatorAdapter(validator, step_name)
        if validation_registry.has(step_name):
            existing = validation_registry.get(step_name)
            if isinstance(existing, CustomValidatorAdapter) and existing._validator is validator:
                # Idempotent re-registration of the exact same custom validator
                pass
            else:
                raise ValidationRegistryError(
                    code="custom_validator_step_collision",
                    message=f"A step handler named '{step_name}' is already registered in ValidationRegistry",
                )
        else:
            validation_registry.register(step_name, adapter)

    return step


custom_validator_step = build_custom_validation_step


class CustomValidatorRegistry:
    """In-memory registry of custom validators."""

    __slots__ = ("_validators",)

    def __init__(self) -> None:
        self._validators: Dict[str, CustomValidator] = {}

    def register(self, validator: CustomValidator) -> CustomValidator:
        if not hasattr(validator, "name"):
            raise ValidationRegistryError(
                code="invalid_custom_validator",
                message="Custom validator must have a 'name' attribute",
            )
        name = _validate_name_string(getattr(validator, "name"))
        if not hasattr(validator, "validate") or not callable(getattr(validator, "validate")):
            raise ValidationRegistryError(
                code="invalid_custom_validator",
                message="Custom validator must implement a callable 'validate(context)' method",
            )
        if name in self._validators:
            raise ValidationRegistryError(
                code="duplicate_custom_validator",
                message=f"Custom validator '{name}' is already registered",
            )
        self._validators[name] = validator
        return validator

    def unregister(self, name: str) -> CustomValidator:
        valid_name = _validate_name_string(name)
        if valid_name not in self._validators:
            raise ValidationRegistryError(
                code="unknown_custom_validator",
                message=f"Custom validator '{valid_name}' is not registered",
            )
        return self._validators.pop(valid_name)

    def get(self, name: str) -> Optional[CustomValidator]:
        valid_name = _validate_name_string(name)
        return self._validators.get(valid_name)

    def require(self, name: str) -> CustomValidator:
        valid_name = _validate_name_string(name)
        if valid_name not in self._validators:
            raise ValidationRegistryError(
                code="unknown_custom_validator",
                message=f"Custom validator '{valid_name}' is not registered",
            )
        return self._validators[valid_name]

    def contains(self, name: str) -> bool:
        if not isinstance(name, str) or not name or not name.strip():
            return False
        try:
            valid_name = _validate_name_string(name)
            return valid_name in self._validators
        except ValidationRegistryError:
            return False

    def __contains__(self, name: str) -> bool:
        return self.contains(name)

    def names(self) -> Tuple[str, ...]:
        return tuple(self._validators.keys())

    def validators(self) -> Tuple[CustomValidator, ...]:
        return tuple(self._validators.values())

    def __len__(self) -> int:
        return len(self._validators)

    def __iter__(self):
        return iter(self.names())

    def clear(self) -> None:
        self._validators.clear()

    def build_step(
        self,
        name: str,
        *,
        validation_registry: Optional[ValidationRegistry] = None,
    ) -> ValidationStep:
        validator = self.require(name)
        return build_custom_validation_step(
            validator,
            validation_registry=validation_registry,
        )

    def build_steps(
        self,
        names: Sequence[str],
        *,
        validation_registry: Optional[ValidationRegistry] = None,
    ) -> Tuple[ValidationStep, ...]:
        seen: set[str] = set()
        ordered_names: list[str] = []
        for n in names:
            valid_n = _validate_name_string(n)
            if valid_n not in self._validators:
                raise ValidationRegistryError(
                    code="unknown_custom_validator",
                    message=f"Custom validator '{valid_n}' is not registered",
                )
            if valid_n not in seen:
                seen.add(valid_n)
                ordered_names.append(valid_n)

        steps = []
        for name in ordered_names:
            steps.append(
                self.build_step(
                    name,
                    validation_registry=validation_registry,
                )
            )
        return tuple(steps)


__all__ = [
    "CustomValidator",
    "CustomValidatorRegistry",
    "CustomValidatorAdapter",
    "build_custom_validation_step",
    "custom_validator_step",
]
