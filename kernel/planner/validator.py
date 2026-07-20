"""Validation layer for Semantic Planner execution plans.

The validator is intentionally independent from the semantic Python engine and
only inspects an execution plan structure and the validity of its operations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kernel.planner.exceptions import InvalidOperationError
from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.operations import (
    CreateClassOperation,
    EnsureImportOperation,
    InsertMethodOperation,
    Operation,
    ReplaceMethodOperation,
)


@dataclass(slots=True)
class ValidationResult:
    """Result of validating an execution plan."""

    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def add_error(self, message: str) -> None:
        """Register a validation error."""

        self.errors.append(message)
        self.valid = False

    def add_warning(self, message: str) -> None:
        """Register a validation warning."""

        self.warnings.append(message)

    def has_errors(self) -> bool:
        """Return whether the validation collected errors."""

        return bool(self.errors)

    def has_warnings(self) -> bool:
        """Return whether the validation collected warnings."""

        return bool(self.warnings)


class PlanValidator:
    """Validate the structure and basic correctness of an execution plan."""

    def validate(self, plan: ExecutionPlan | None) -> ValidationResult:
        """Validate an execution plan and return a structured result.

        Args:
            plan: The execution plan to validate.

        Returns:
            A validation result containing errors and warnings.
        """

        result = ValidationResult()

        if plan is None:
            result.add_error("Execution plan cannot be None.")
            return result

        if len(plan) == 0:
            result.add_error("Execution plan must contain at least one operation.")
            return result

        seen_operation_ids: set[str] = set()
        seen_operations: list[tuple[str, Any]] = []

        for operation in plan:
            operation_id = str(operation.operation_id)
            if operation_id in seen_operation_ids:
                result.add_error(f"Duplicate operation_id detected: {operation_id}")
            else:
                seen_operation_ids.add(operation_id)

            operation_key = self._operation_signature(operation)
            if operation_key in {item[0] for item in seen_operations}:
                result.add_error(f"Duplicate operation detected: {operation_key}")
            else:
                seen_operations.append((operation_key, operation))

            try:
                operation.validate()
            except InvalidOperationError as exc:
                result.add_error(str(exc))

            if isinstance(operation, CreateClassOperation):
                if not operation.class_name.strip():
                    result.add_error("CreateClassOperation requires a non-empty class_name.")
            elif isinstance(operation, InsertMethodOperation):
                if not operation.target_class.strip():
                    result.add_error("InsertMethodOperation requires a non-empty target_class.")
                if not operation.method_name.strip():
                    result.add_error("InsertMethodOperation requires a non-empty method_name.")
                if not operation.source_code.strip():
                    result.add_error("InsertMethodOperation requires non-empty source_code.")
            elif isinstance(operation, ReplaceMethodOperation):
                if not operation.source_code.strip():
                    result.add_error("ReplaceMethodOperation requires non-empty source_code.")
            elif isinstance(operation, EnsureImportOperation):
                if not operation.module.strip():
                    result.add_error("EnsureImportOperation requires a non-empty module.")
                if not operation.name or not operation.name.strip():
                    result.add_error("EnsureImportOperation requires a non-empty name.")

        return result

    @staticmethod
    def _operation_signature(operation: Operation) -> str:
        """Create a stable signature for duplicate detection."""

        if isinstance(operation, CreateClassOperation):
            return f"create_class:{operation.class_name}"
        if isinstance(operation, InsertMethodOperation):
            return f"insert_method:{operation.target_class}:{operation.method_name}:{operation.source_code}"
        if isinstance(operation, ReplaceMethodOperation):
            return f"replace_method:{operation.target_class}:{operation.method_name}:{operation.source_code}"
        if isinstance(operation, EnsureImportOperation):
            return f"ensure_import:{operation.module}:{operation.name or ''}"
        return operation.__class__.__name__


__all__ = ["PlanValidator", "ValidationResult"]
