"""Domain-facing aliases for the common safe operation schema validator."""

from cmm.agent_runtime.operation_schema import (
    OperationSchemaIssue,
    OperationSchemaValidationError,
    validate_operation_schema,
)

__all__ = [
    "OperationSchemaIssue",
    "OperationSchemaValidationError",
    "validate_operation_schema",
]
