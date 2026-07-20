"""Operation-specific parsers for LLM execution plan payloads."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from kernel.llm.exceptions import ParserError
from kernel.planner.operations import CreateClassOperation, EnsureImportOperation, InsertMethodOperation, Operation


class OperationParser(ABC):
    """Parse a single operation payload into a planner operation."""

    @abstractmethod
    def parse(self, operation: dict[str, Any]) -> Operation:
        """Parse a single operation payload."""


class OperationParserRegistry:
    """Registry for resolving operation parsers by operation type."""

    def __init__(self) -> None:
        self._parsers: dict[str, OperationParser] = {}
        self.register("create_class", CreateClassOperationParser())
        self.register("insert_method", InsertMethodOperationParser())
        self.register("ensure_import", EnsureImportOperationParser())

    def register(self, operation_type: str, parser: OperationParser) -> None:
        """Register a parser for a specific operation type."""

        self._parsers[operation_type] = parser

    def resolve(self, operation_type: str) -> OperationParser:
        """Resolve the parser associated with an operation type."""

        try:
            return self._parsers[operation_type]
        except KeyError as exc:
            raise ParserError(f"Unsupported operation type: {operation_type}") from exc

    def has_parser(self, operation_type: str) -> bool:
        """Return whether a parser exists for the given operation type."""

        return operation_type in self._parsers


class CreateClassOperationParser(OperationParser):
    """Parse create_class operation payloads."""

    def parse(self, operation: dict[str, Any]) -> Operation:
        """Parse a create_class payload into a CreateClassOperation."""

        operation_type = operation.get("type")
        if operation_type != "create_class":
            raise ParserError("create_class operation requires type 'create_class'")

        module = operation.get("module")
        name = operation.get("name")
        if not isinstance(module, str) or not module.strip():
            raise ParserError("create_class operation requires a non-empty module")
        if not isinstance(name, str) or not name.strip():
            raise ParserError("create_class operation requires a non-empty name")

        return CreateClassOperation(class_name=name, module=module)


class InsertMethodOperationParser(OperationParser):
    """Parse insert_method operation payloads."""

    def parse(self, operation: dict[str, Any]) -> Operation:
        """Parse an insert_method payload into an InsertMethodOperation."""

        operation_type = operation.get("type")
        if operation_type != "insert_method":
            raise ParserError("insert_method operation requires type 'insert_method'")

        module = operation.get("module")
        target_class = operation.get("class")
        name = operation.get("name")
        code = operation.get("code")

        if not isinstance(module, str) or not module.strip():
            raise ParserError("insert_method operation requires a non-empty module")
        if not isinstance(target_class, str) or not target_class.strip():
            raise ParserError("insert_method operation requires a non-empty class")
        if not isinstance(name, str) or not name.strip():
            raise ParserError("insert_method operation requires a non-empty name")
        if not isinstance(code, str) or not code.strip():
            raise ParserError("insert_method operation requires a non-empty code")

        return InsertMethodOperation(target_class=target_class, method_name=name, source_code=code)


class EnsureImportOperationParser(OperationParser):
    """Parse ensure_import operation payloads."""

    def parse(self, operation: dict[str, Any]) -> Operation:
        """Parse an ensure_import payload into an EnsureImportOperation."""

        operation_type = operation.get("type")
        if operation_type != "ensure_import":
            raise ParserError("ensure_import operation requires type 'ensure_import'")

        module = operation.get("module")
        import_value = operation.get("import")

        if not isinstance(module, str) or not module.strip():
            raise ParserError("ensure_import operation requires a non-empty module")
        if not isinstance(import_value, str) or not import_value.strip():
            raise ParserError("ensure_import operation requires a non-empty import")

        return EnsureImportOperation(module=module, name=import_value)
