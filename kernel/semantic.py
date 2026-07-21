"""Generic semantic operation contracts and runtime primitives."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping
from uuid import uuid4


class SemanticValidationError(ValueError):
    """Raised when a semantic operation or plan is invalid."""


class SemanticExecutorNotFoundError(LookupError):
    """Raised when no executor supports a semantic operation."""


@dataclass(frozen=True, slots=True)
class SemanticOperation:
    """Domain-neutral semantic operation."""

    operation_type: str
    domain: str
    parameters: Mapping[str, Any]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    operation_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", dict(self.parameters))
        object.__setattr__(self, "metadata", dict(self.metadata))
        self.validate()

    @property
    def type_id(self) -> str:
        """Return the fully qualified operation type."""

        return f"{self.domain}.{self.operation_type}"

    def validate(self) -> None:
        """Validate the generic operation envelope."""

        if not isinstance(self.operation_type, str) or not self.operation_type.strip():
            raise SemanticValidationError("Operation type must be a non-empty string.")
        if not isinstance(self.domain, str) or not self.domain.strip():
            raise SemanticValidationError("Operation domain must be a non-empty string.")
        if not isinstance(self.parameters, Mapping):
            raise SemanticValidationError("Operation parameters must be a mapping.")
        if not isinstance(self.metadata, Mapping):
            raise SemanticValidationError("Operation metadata must be a mapping.")
        if not isinstance(self.operation_id, str) or not self.operation_id.strip():
            raise SemanticValidationError("Operation id must be a non-empty string.")

    def require(self, *names: str) -> None:
        """Require named parameters to be present and non-empty when strings."""

        for name in names:
            if name not in self.parameters:
                raise SemanticValidationError(f"Missing required parameter: {name}.")
            value = self.parameters[name]
            if isinstance(value, str) and not value.strip():
                raise SemanticValidationError(f"Parameter {name} must be non-empty.")
            if value is None:
                raise SemanticValidationError(f"Parameter {name} must not be None.")

    def serialize(self) -> dict[str, Any]:
        """Serialize the operation into primitive data."""

        return {
            "id": self.operation_id,
            "domain": self.domain,
            "type": self.operation_type,
            "parameters": dict(self.parameters),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SemanticOperation":
        """Build an operation from serialized data."""

        return cls(
            operation_id=str(payload.get("id") or uuid4()),
            domain=str(payload["domain"]),
            operation_type=str(payload["type"]),
            parameters=payload.get("parameters", {}),
            metadata=payload.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class SemanticResult:
    """Structured result returned by semantic executors."""

    success: bool
    message: str
    data: Mapping[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()
    changes: tuple[str, ...] = ()
    operation: SemanticOperation | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", dict(self.data))
        object.__setattr__(self, "errors", tuple(self.errors))
        object.__setattr__(self, "changes", tuple(str(item) for item in self.changes))


@dataclass(frozen=True, slots=True)
class SemanticPlanResult:
    """Structured result for a sequence of operations."""

    success: bool
    results: tuple[SemanticResult, ...]
    errors: tuple[str, ...] = ()

    @property
    def changes(self) -> tuple[str, ...]:
        """Return all changed artifacts from child results."""

        return tuple(change for result in self.results for change in result.changes)


class SemanticExecutor(ABC):
    """Common executor interface for semantic operations."""

    @abstractmethod
    def supports(self, operation: SemanticOperation) -> bool:
        """Return whether this executor can execute the operation."""

    @abstractmethod
    def execute(self, operation: SemanticOperation) -> SemanticResult:
        """Execute the operation and return a structured result."""

    def validate_before(self, operation: SemanticOperation) -> None:
        """Validate operation-specific preconditions before execution."""

        operation.validate()

    def validate_after(
        self,
        operation: SemanticOperation,
        result: SemanticResult,
    ) -> SemanticResult:
        """Validate postconditions after execution."""

        return result


class SemanticExecutorRegistry:
    """Single logical resolver for semantic executors."""

    def __init__(self) -> None:
        self._executors: list[SemanticExecutor] = []

    def register(self, executor: SemanticExecutor) -> None:
        """Register one executor."""

        if not isinstance(executor, SemanticExecutor):
            raise TypeError("Executor must implement SemanticExecutor.")
        self._executors.append(executor)

    def register_many(self, executors: Iterable[SemanticExecutor]) -> None:
        """Register several executors in order."""

        for executor in executors:
            self.register(executor)

    def resolve(self, operation: SemanticOperation) -> SemanticExecutor:
        """Resolve the first executor supporting an operation."""

        operation.validate()
        for executor in self._executors:
            if executor.supports(operation):
                return executor
        raise SemanticExecutorNotFoundError(
            f"No semantic executor found for operation: {operation.type_id}."
        )

    def all(self) -> tuple[SemanticExecutor, ...]:
        """Return registered executors in resolution order."""

        return tuple(self._executors)


class SemanticRuntime:
    """Generic runtime for semantic operation execution."""

    def __init__(self, registry: SemanticExecutorRegistry) -> None:
        self.registry = registry

    def execute_operation(self, operation: SemanticOperation) -> SemanticResult:
        """Validate, resolve, execute, and post-validate one operation."""

        try:
            operation.validate()
            executor = self.registry.resolve(operation)
            executor.validate_before(operation)
            result = executor.execute(operation)
            return executor.validate_after(operation, result)
        except (SemanticValidationError, SemanticExecutorNotFoundError) as error:
            return SemanticResult(
                success=False,
                message=str(error),
                errors=(str(error),),
                operation=operation if isinstance(operation, SemanticOperation) else None,
            )
        except Exception as error:  # pragma: no cover - defensive runtime boundary
            return SemanticResult(
                success=False,
                message=str(error),
                errors=(str(error),),
                operation=operation,
            )

    def execute_plan(self, operations: Iterable[SemanticOperation]) -> SemanticPlanResult:
        """Execute operations sequentially, stopping at the first failure."""

        results: list[SemanticResult] = []
        errors: list[str] = []
        for operation in operations:
            result = self.execute_operation(operation)
            results.append(result)
            if not result.success:
                errors.extend(result.errors or (result.message,))
                break
        return SemanticPlanResult(
            success=not errors,
            results=tuple(results),
            errors=tuple(errors),
        )

