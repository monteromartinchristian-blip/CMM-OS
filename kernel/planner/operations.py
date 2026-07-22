"""Semantic planner operations used to describe future code changes.

The operation hierarchy is intentionally extensible so that new semantic
operations can be introduced without changing the core planner model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping, Optional
from uuid import UUID, uuid4

from kernel.planner.exceptions import InvalidOperationError
from kernel.planner.operation_metadata import OperationMetadata, OperationParameter


@dataclass(frozen=True, slots=True, kw_only=True)
class Operation:
    """Immutable base model for planner operations.

    The base class carries graph-oriented metadata for future planning layers
    while remaining backwards-compatible with the existing execution stack.
    """

    id: UUID = field(default_factory=uuid4)
    depends_on: tuple[UUID, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = field(default_factory=tuple)
    operation_type: ClassVar[str] = ""
    description: ClassVar[str] = ""
    category: ClassVar[str] = "python"
    metadata_name: ClassVar[str] = ""
    parameters: ClassVar[tuple[dict[str, Any], ...]] = ()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super(Operation, cls).__init_subclass__(**kwargs)
        if cls.operation_type:
            _OPERATION_REGISTRY[cls.operation_type] = cls

    @property
    def operation_type_value(self) -> str:
        """Return the concrete operation type for this instance."""

        return type(self).operation_type

    @classmethod
    def schema(cls) -> dict[str, Any]:
        """Return a structured description of the operation contract."""

        return cls.operation_metadata().to_dict()

    @classmethod
    def operation_metadata(cls) -> OperationMetadata:
        """Return the structured metadata object for the operation."""

        return OperationMetadata(
            name=cls.metadata_name or cls.operation_type,
            description=cls.description,
            category=cls.category,
            parameters=tuple(
                OperationParameter(
                    name=parameter["name"],
                    type=parameter["type"],
                    required=parameter["required"],
                    description=parameter["description"],
                )
                for parameter in cls.parameters
            ),
        )

    @property
    def operation_id(self) -> UUID:
        """Return the operation identifier for backwards compatibility."""

        return self.id

    @operation_id.setter
    def operation_id(self, value: UUID) -> None:
        """Set the operation identifier for backwards compatibility."""

        object.__setattr__(self, "id", value)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(operation_id={self.id}, operation_type={self.operation_type_value})"

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Operation":
        """Create an operation instance from serialized data."""

        operation_type = payload.get("operation_type")
        if not isinstance(operation_type, str) or not operation_type.strip():
            raise InvalidOperationError("Operation payload is missing a valid 'operation_type'.")

        operation_cls = _OPERATION_REGISTRY.get(operation_type)
        if operation_cls is None:
            raise InvalidOperationError(f"Unsupported operation type: {operation_type}")

        return operation_cls._from_dict_payload(payload)

    def serialize(self) -> dict[str, Any]:
        """Serialize the operation into a dictionary."""

        return {
            "id": str(self.id),
            "depends_on": [str(item) for item in self.depends_on],
            "metadata": dict(self.metadata),
            "tags": list(self.tags),
        }

    def validate(self) -> None:
        """Validate the operation payload and structure."""

        if self.id in self.depends_on:
            raise ValueError("An operation cannot depend on itself.")

    @classmethod
    def _from_dict_payload(cls, payload: Mapping[str, Any]) -> "Operation":
        """Create an instance from a payload for the specific subclass."""

        raise NotImplementedError


_OPERATION_REGISTRY: dict[str, type[Operation]] = {}


def registered_operation_classes() -> tuple[type[Operation], ...]:
    """Return all operation classes registered in declaration order."""

    return tuple(_OPERATION_REGISTRY.values())


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateClassOperation(Operation):
    """Create a new class declaration in a target module."""

    operation_type: ClassVar[str] = "create_class"
    metadata_name: ClassVar[str] = "create_class"
    description: ClassVar[str] = "Create a new Python class declaration in a target module."
    category: ClassVar[str] = "python"
    parameters: ClassVar[tuple[dict[str, Any], ...]] = (
        {
            "name": "class_name",
            "type": "str",
            "required": True,
            "description": "Class name.",
        },
        {
            "name": "module",
            "type": "str | None",
            "required": False,
            "description": "Target module path.",
        },
    )
    class_name: str = field()
    module: str | None = field(default=None)

    def serialize(self) -> dict[str, Any]:
        """Serialize the operation into a dictionary."""

        payload = super().serialize()
        payload.update(
            {
                "operation_type": self.operation_type_value,
                "class_name": self.class_name,
                "module": self.module,
            }
        )
        return payload

    def validate(self) -> None:
        """Validate that the class name is usable."""

        super().validate()
        if not isinstance(self.class_name, str) or not self.class_name.strip():
            raise InvalidOperationError("CreateClassOperation requires a non-empty class_name.")
        if self.module is not None and (not isinstance(self.module, str) or not self.module.strip()):
            raise InvalidOperationError("CreateClassOperation requires a non-empty module when provided.")

    @classmethod
    def _from_dict_payload(cls, payload: Mapping[str, Any]) -> "CreateClassOperation":
        module = payload.get("module")
        depends_on = tuple(UUID(item) for item in payload.get("depends_on", ()))
        metadata = payload.get("metadata", {}) or {}
        tags = tuple(payload.get("tags", ()))
        return cls(
            id=UUID(str(payload.get("id"))) if payload.get("id") is not None else uuid4(),
            depends_on=depends_on,
            metadata=dict(metadata),
            tags=tags,
            class_name=str(payload["class_name"]),
            module=None if module is None else str(module),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class InsertMethodOperation(Operation):
    """Insert a method into an existing class."""

    operation_type: ClassVar[str] = "insert_method"
    metadata_name: ClassVar[str] = "insert_method"
    description: ClassVar[str] = "Insert a Python method into an existing class."
    category: ClassVar[str] = "python"
    parameters: ClassVar[tuple[dict[str, Any], ...]] = (
        {
            "name": "target_class",
            "type": "str",
            "required": True,
            "description": "Target class name.",
        },
        {
            "name": "method_name",
            "type": "str",
            "required": True,
            "description": "Method name.",
        },
        {
            "name": "source_code",
            "type": "str",
            "required": True,
            "description": "Method implementation source code.",
        },
    )
    target_class: str = field()
    method_name: str = field()
    source_code: str = field()

    def serialize(self) -> dict[str, Any]:
        """Serialize the operation into a dictionary."""

        payload = super().serialize()
        payload.update(
            {
                "operation_type": self.operation_type_value,
                "target_class": self.target_class,
                "method_name": self.method_name,
                "source_code": self.source_code,
            }
        )
        return payload

    def validate(self) -> None:
        """Validate the method insertion payload."""

        super().validate()
        if not isinstance(self.target_class, str) or not self.target_class.strip():
            raise InvalidOperationError("InsertMethodOperation requires a non-empty target_class.")
        if not isinstance(self.method_name, str) or not self.method_name.strip():
            raise InvalidOperationError("InsertMethodOperation requires a non-empty method_name.")
        if not isinstance(self.source_code, str) or not self.source_code.strip():
            raise InvalidOperationError("InsertMethodOperation requires non-empty source_code.")

    @classmethod
    def _from_dict_payload(cls, payload: Mapping[str, Any]) -> "InsertMethodOperation":
        depends_on = tuple(UUID(item) for item in payload.get("depends_on", ()))
        metadata = payload.get("metadata", {}) or {}
        tags = tuple(payload.get("tags", ()))
        return cls(
            id=UUID(str(payload.get("id"))) if payload.get("id") is not None else uuid4(),
            depends_on=depends_on,
            metadata=dict(metadata),
            tags=tags,
            target_class=str(payload["target_class"]),
            method_name=str(payload["method_name"]),
            source_code=str(payload["source_code"]),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ReplaceMethodOperation(Operation):
    """Replace an existing method implementation in a class."""

    operation_type: ClassVar[str] = "replace_method"
    metadata_name: ClassVar[str] = "replace_method"
    description: ClassVar[str] = "Replace the implementation of an existing Python method while preserving its signature."
    category: ClassVar[str] = "python"
    parameters: ClassVar[tuple[dict[str, Any], ...]] = (
        {
            "name": "target_class",
            "type": "str",
            "required": True,
            "description": "Target class name.",
        },
        {
            "name": "method_name",
            "type": "str",
            "required": True,
            "description": "Method name.",
        },
        {
            "name": "source_code",
            "type": "str",
            "required": True,
            "description": "Replacement method implementation source code.",
        },
    )
    target_class: str = field()
    method_name: str = field()
    source_code: str = field()

    def serialize(self) -> dict[str, Any]:
        """Serialize the operation into a dictionary."""

        payload = super().serialize()
        payload.update(
            {
                "operation_type": self.operation_type_value,
                "target_class": self.target_class,
                "method_name": self.method_name,
                "source_code": self.source_code,
            }
        )
        return payload

    def validate(self) -> None:
        """Validate the method replacement payload."""

        super().validate()
        if not isinstance(self.target_class, str) or not self.target_class.strip():
            raise InvalidOperationError("ReplaceMethodOperation requires a non-empty target_class.")
        if not isinstance(self.method_name, str) or not self.method_name.strip():
            raise InvalidOperationError("ReplaceMethodOperation requires a non-empty method_name.")
        if not isinstance(self.source_code, str) or not self.source_code.strip():
            raise InvalidOperationError("ReplaceMethodOperation requires non-empty source_code.")

    @classmethod
    def _from_dict_payload(cls, payload: Mapping[str, Any]) -> "ReplaceMethodOperation":
        depends_on = tuple(UUID(item) for item in payload.get("depends_on", ()))
        metadata = payload.get("metadata", {}) or {}
        tags = tuple(payload.get("tags", ()))
        return cls(
            id=UUID(str(payload.get("id"))) if payload.get("id") is not None else uuid4(),
            depends_on=depends_on,
            metadata=dict(metadata),
            tags=tags,
            target_class=str(payload["target_class"]),
            method_name=str(payload["method_name"]),
            source_code=str(payload["source_code"]),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class EnsureImportOperation(Operation):
    """Ensure that an import declaration exists in a module."""

    operation_type: ClassVar[str] = "ensure_import"
    metadata_name: ClassVar[str] = "ensure_import"
    description: ClassVar[str] = "Ensure that a Python import declaration exists in a module without duplicating it."
    category: ClassVar[str] = "python"
    parameters: ClassVar[tuple[dict[str, Any], ...]] = (
        {
            "name": "module",
            "type": "str",
            "required": True,
            "description": "Import module name.",
        },
        {
            "name": "name",
            "type": "str | None",
            "required": False,
            "description": "Imported symbol for from-import statements.",
        },
    )
    module: str = field()
    name: Optional[str] = field(default=None)

    def serialize(self) -> dict[str, Any]:
        """Serialize the operation into a dictionary."""

        payload = super().serialize()
        payload.update(
            {
                "operation_type": self.operation_type_value,
                "module": self.module,
                "name": self.name,
            }
        )
        return payload

    def validate(self) -> None:
        """Validate the import operation payload."""

        super().validate()
        if not isinstance(self.module, str) or not self.module.strip():
            raise InvalidOperationError("EnsureImportOperation requires a non-empty module.")
        if self.name is not None and (not isinstance(self.name, str) or not self.name.strip()):
            raise InvalidOperationError("EnsureImportOperation requires a non-empty name when provided.")

    @classmethod
    def _from_dict_payload(cls, payload: Mapping[str, Any]) -> "EnsureImportOperation":
        depends_on = tuple(UUID(item) for item in payload.get("depends_on", ()))
        metadata = payload.get("metadata", {}) or {}
        tags = tuple(payload.get("tags", ()))
        name = payload.get("name")
        return cls(
            id=UUID(str(payload.get("id"))) if payload.get("id") is not None else uuid4(),
            depends_on=depends_on,
            metadata=dict(metadata),
            tags=tags,
            module=str(payload["module"]),
            name=None if name is None else str(name),
        )


__all__ = [
    "CreateClassOperation",
    "EnsureImportOperation",
    "ExtractFactsOperation",
    "InsertMethodOperation",
    "Operation",
    "MergeKnowledgeOperation",
    "ReadPDFOperation",
    "ReplaceMethodOperation",
]


from kernel.planner.extract_facts_operation import ExtractFactsOperation
from kernel.planner.merge_knowledge_operation import MergeKnowledgeOperation
from kernel.planner.read_pdf_operation import ReadPDFOperation
