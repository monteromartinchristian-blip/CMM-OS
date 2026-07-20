"""Parsing utilities for converting model output into execution plans."""

from __future__ import annotations

import json
from typing import Any

from kernel.llm.exceptions import ParserError
from kernel.llm.models import LLMResponse
from kernel.llm.operation_parsers import CreateClassOperationParser, EnsureImportOperationParser, InsertMethodOperationParser, OperationParserRegistry
from kernel.planner.execution_plan import ExecutionPlan


class OperationPlanParser:
    """Parse LLM JSON payloads into execution plans.

    The parser delegates operation-specific parsing to a registry, allowing the
    architecture to evolve without changing the main orchestration logic.
    """

    def __init__(self, registry: OperationParserRegistry | None = None) -> None:
        self.registry = registry or self._default_registry()

    def parse(self, payload: LLMResponse | str) -> ExecutionPlan:
        """Parse a JSON payload into an execution plan.

        Args:
            payload: Either a raw JSON string or an LLM response containing JSON.

        Returns:
            An execution plan instance.

        Raises:
            ParserError: If the payload is invalid JSON or missing required keys.
        """

        raw_payload = payload.content if isinstance(payload, LLMResponse) else payload

        try:
            data: Any = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            raise ParserError("Invalid JSON payload") from exc

        if not isinstance(data, dict):
            raise ParserError("Invalid JSON payload")

        if "operations" not in data:
            raise ParserError("Missing 'operations' field")

        operations = data.get("operations")
        if operations is None:
            raise ParserError("Missing 'operations' field")

        if not isinstance(operations, list):
            raise ParserError("'operations' must be a list")

        if not operations:
            return ExecutionPlan()

        plan = ExecutionPlan()
        for item in operations:
            if not isinstance(item, dict):
                raise ParserError("Each operation must be an object")

            operation_type = item.get("type")
            if not isinstance(operation_type, str) or not operation_type.strip():
                raise ParserError("Unsupported operation type: None")

            parser = self.registry.resolve(operation_type)
            operation = parser.parse(item)
            plan.add(operation)

        return plan

    @staticmethod
    def _default_registry() -> OperationParserRegistry:
        """Create the default registry with the built-in parsers."""

        registry = OperationParserRegistry()
        registry.register("create_class", CreateClassOperationParser())
        registry.register("insert_method", InsertMethodOperationParser())
        registry.register("ensure_import", EnsureImportOperationParser())
        return registry
