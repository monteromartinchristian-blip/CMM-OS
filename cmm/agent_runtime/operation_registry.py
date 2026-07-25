"""Phase 9.13 – Agent Operation Registry.

Defines the registry interface and thread-safe in-memory implementation for operation descriptors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from threading import RLock

from cmm.agent_runtime.errors import (
    AgentOperationNotRegisteredError,
    AgentOperationParameterValidationError,
    AgentOperationVersionNotRegisteredError,
    DuplicateAgentOperationError,
)
from cmm.agent_runtime.operation_execution_contracts import (
    AgentOperationRequest,
    OperationDescriptor,
)


class AgentOperationRegistry(ABC):
    """Abstract interface for storing and resolving registered operation descriptors."""

    @abstractmethod
    def register(self, descriptor: OperationDescriptor) -> None:
        """Register an operation descriptor."""
        ...

    @abstractmethod
    def unregister(self, name: str, version: str = "1") -> OperationDescriptor:
        """Unregister an operation descriptor by exact name and version."""
        ...

    @abstractmethod
    def get(self, name: str, version: str = "1") -> OperationDescriptor:
        """Get an operation descriptor by exact name and version."""
        ...

    @abstractmethod
    def get_exact_version(self, name: str, version: str) -> OperationDescriptor:
        """Get an operation descriptor by exact version."""
        ...

    @abstractmethod
    def contains(self, name: str, version: str = "1") -> bool:
        """Check if an operation is registered with the exact version."""
        ...

    @abstractmethod
    def list_operations(self) -> list[OperationDescriptor]:
        """List all registered descriptors in stable registration order."""
        ...

    @abstractmethod
    def list_versions(self, name: str) -> list[str]:
        """List all registered versions for a specific operation name."""
        ...

    @abstractmethod
    def resolve(self, name: str, version: str = "1") -> OperationDescriptor:
        """Resolve a descriptor without dynamic fallbacks."""
        ...

    @abstractmethod
    def validate_request(self, request: AgentOperationRequest) -> bool:
        """Validate request against descriptor's parameter schema."""
        ...


class InMemoryAgentOperationRegistry(AgentOperationRegistry):
    """Thread-safe in-memory registry of operation descriptors."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._descriptors: dict[tuple[str, str], OperationDescriptor] = {}
        self._order: list[tuple[str, str]] = []

    def register(self, descriptor: OperationDescriptor) -> None:
        with self._lock:
            key = (descriptor.name, descriptor.version)
            if key in self._descriptors:
                raise DuplicateAgentOperationError(
                    f"Operation '{descriptor.name}' version '{descriptor.version}' is already registered."
                )
            self._descriptors[key] = descriptor
            self._order.append(key)

    def unregister(self, name: str, version: str = "1") -> OperationDescriptor:
        with self._lock:
            key = (name, version)
            if key not in self._descriptors:
                if not any(k[0] == name for k in self._descriptors):
                    raise AgentOperationNotRegisteredError(
                        f"Operation '{name}' is not registered."
                    )
                raise AgentOperationVersionNotRegisteredError(
                    f"Version '{version}' for operation '{name}' is not registered."
                )
            desc = self._descriptors.pop(key)
            if key in self._order:
                self._order.remove(key)
            return desc

    def get(self, name: str, version: str = "1") -> OperationDescriptor:
        return self.resolve(name, version)

    def get_exact_version(self, name: str, version: str) -> OperationDescriptor:
        return self.resolve(name, version)

    def contains(self, name: str, version: str = "1") -> bool:
        with self._lock:
            return (name, version) in self._descriptors

    def list_operations(self) -> list[OperationDescriptor]:
        with self._lock:
            return [self._descriptors[key] for key in self._order]

    def list_versions(self, name: str) -> list[str]:
        with self._lock:
            versions = [key[1] for key in self._order if key[0] == name]
            return versions

    def resolve(self, name: str, version: str = "1") -> OperationDescriptor:
        with self._lock:
            key = (name, version)
            if key not in self._descriptors:
                if not any(k[0] == name for k in self._descriptors):
                    raise AgentOperationNotRegisteredError(
                        f"Operation '{name}' is not registered."
                    )
                raise AgentOperationVersionNotRegisteredError(
                    f"Version '{version}' for operation '{name}' is not registered."
                )
            return self._descriptors[key]

    def validate_request(self, request: AgentOperationRequest) -> bool:
        desc = self.resolve(request.operation_name, request.operation_version)
        if not desc.enabled:
            raise AgentOperationNotRegisteredError(
                f"Operation '{desc.name}' is disabled."
            )

        schema = desc.input_schema
        if not schema:
            return True

        required_fields = schema.get("required", [])
        properties = schema.get("properties", {})
        allow_additional = schema.get("additionalProperties", True)

        params = request.parameters

        # Required fields check
        for req in required_fields:
            if req not in params:
                raise AgentOperationParameterValidationError(
                    f"Missing required parameter '{req}' for operation '{desc.name}'."
                )

        # Additional fields check
        if allow_additional is False:
            for k in params:
                if k not in properties:
                    raise AgentOperationParameterValidationError(
                        f"Disallowed additional parameter '{k}' for operation '{desc.name}'."
                    )

        # Basic type & schema property validation
        for k, v in params.items():
            if k in properties:
                prop_spec = properties[k]
                expected_type = prop_spec.get("type")
                if expected_type == "string" and not isinstance(v, str):
                    raise AgentOperationParameterValidationError(
                        f"Parameter '{k}' must be string, got {type(v).__name__}."
                    )
                elif expected_type == "integer" and (
                    isinstance(v, bool) or not isinstance(v, int)
                ):
                    raise AgentOperationParameterValidationError(
                        f"Parameter '{k}' must be integer, got {type(v).__name__}."
                    )
                elif expected_type == "number" and not isinstance(v, (int, float)):
                    raise AgentOperationParameterValidationError(
                        f"Parameter '{k}' must be number, got {type(v).__name__}."
                    )
                elif expected_type == "boolean" and not isinstance(v, bool):
                    raise AgentOperationParameterValidationError(
                        f"Parameter '{k}' must be boolean, got {type(v).__name__}."
                    )
                elif expected_type == "array" and not isinstance(v, (list, tuple)):
                    raise AgentOperationParameterValidationError(
                        f"Parameter '{k}' must be array/list, got {type(v).__name__}."
                    )
                elif expected_type == "object" and not isinstance(
                    v, (dict, type(request.parameters))
                ):
                    raise AgentOperationParameterValidationError(
                        f"Parameter '{k}' must be object/dict, got {type(v).__name__}."
                    )

                # Enum value check
                if "enum" in prop_spec and v not in prop_spec["enum"]:
                    raise AgentOperationParameterValidationError(
                        f"Parameter '{k}' value '{v}' not in allowed enum: {prop_spec['enum']}."
                    )

                # Range checks for numbers/integers
                if (
                    isinstance(v, (int, float))
                    and not isinstance(v, bool)
                    and "minimum" in prop_spec
                    and v < prop_spec["minimum"]
                ):
                    raise AgentOperationParameterValidationError(
                        f"Parameter '{k}' value {v} below minimum {prop_spec['minimum']}."
                    )
                if (
                    isinstance(v, (int, float))
                    and not isinstance(v, bool)
                    and "maximum" in prop_spec
                    and v > prop_spec["maximum"]
                ):
                    raise AgentOperationParameterValidationError(
                        f"Parameter '{k}' value {v} exceeds maximum {prop_spec['maximum']}."
                    )

        return True
