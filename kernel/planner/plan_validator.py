"""Validation layer for semantic planner execution plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.operations import (
    CreateClassOperation,
    EnsureImportOperation,
    InsertMethodOperation,
    Operation,
    ReplaceMethodOperation,
    registered_operation_classes,
)


@dataclass(slots=True)
class ValidationResult:
    """Result of validating an execution plan."""

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        self.errors.append(message)
        self.valid = False

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def has_errors(self) -> bool:
        return bool(self.errors)

    def has_warnings(self) -> bool:
        return bool(self.warnings)


class PlanValidator:
    """Validate the structure and basic correctness of an execution plan."""

    def __init__(self) -> None:
        self._registered_operations = {
            operation.operation_metadata().name: operation for operation in registered_operation_classes()
        }

    def validate(self, plan: ExecutionPlan) -> ValidationResult:
        result = ValidationResult()

        if not isinstance(plan, ExecutionPlan):
            result.add_error("Execution plan must be an ExecutionPlan instance.")
            return result

        if len(plan) == 0:
            result.add_error("Execution plan must contain at least one operation.")
            return result

        seen_operation_ids: set[str] = set()
        seen_signatures: set[tuple[Any, ...]] = set()

        for operation in plan:
            if not isinstance(operation, Operation):
                result.add_error("ExecutionPlan contains an invalid operation.")
                continue

            operation_name = operation.operation_type_value
            if operation_name not in self._registered_operations:
                result.add_error(f"Unsupported operation type: {operation_name}")

            operation_id = str(operation.operation_id)
            if operation_id in seen_operation_ids:
                result.add_error(f"Duplicate operation_id detected: {operation_id}")
            else:
                seen_operation_ids.add(operation_id)

            signature = self._operation_signature(operation)
            if signature in seen_signatures:
                result.add_error(f"Duplicate operation detected: {signature}")
            else:
                seen_signatures.add(signature)

            self._validate_required_fields(operation, result)

        return result

    def _validate_required_fields(self, operation: Operation, result: ValidationResult) -> None:
        schema = operation.schema()

        for parameter in schema["parameters"]:
            parameter_name = parameter["name"]
            required = bool(parameter["required"])
            value = getattr(operation, parameter_name, _MISSING)

            if value is _MISSING:
                if required:
                    result.add_error(
                        f"{operation.operation_type_value} is missing required parameter {parameter_name}."
                    )
                continue

            if value is None:
                if required:
                    result.add_error(
                        f"{operation.operation_type_value} is missing required parameter {parameter_name}."
                    )
                continue

            if isinstance(value, str) and not value.strip():
                result.add_error(
                    f"{operation.__class__.__name__} requires a non-empty {parameter_name}."
                )

    @staticmethod
    def _operation_signature(operation: Operation) -> tuple[Any, ...]:
        if isinstance(operation, CreateClassOperation):
            return ("create_class", getattr(operation, "class_name", None))
        if isinstance(operation, InsertMethodOperation):
            return (
                "insert_method",
                getattr(operation, "target_class", None),
                getattr(operation, "method_name", None),
                getattr(operation, "source_code", None),
            )
        if isinstance(operation, ReplaceMethodOperation):
            return (
                "replace_method",
                getattr(operation, "target_class", None),
                getattr(operation, "method_name", None),
                getattr(operation, "source_code", None),
            )
        if isinstance(operation, EnsureImportOperation):
            return (
                "ensure_import",
                getattr(operation, "module", None),
                getattr(operation, "name", None),
            )

        return (operation.operation_type_value, operation.serialize())


class _MissingValue:
    pass


_MISSING = _MissingValue()


__all__ = ["PlanValidator", "ValidationResult"]
