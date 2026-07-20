"""Parse plain-text planner responses into execution plans."""

from __future__ import annotations

import re
from typing import Any

from kernel.planner.execution_plan import ExecutionPlan
from kernel.planner.exceptions import PlannerError
from kernel.planner.operation_catalog import OperationCatalog
from kernel.planner.operations import Operation, registered_operation_classes

_OPERATION_CLASSES = {
    operation.operation_metadata().name: operation for operation in registered_operation_classes()
}


def parse(response: str, catalog: OperationCatalog) -> ExecutionPlan:
    """Parse a plain-text LLM response into an execution plan."""

    if not isinstance(response, str) or not response.strip():
        raise PlannerError("LLM response must be a non-empty string.")

    plan = ExecutionPlan()
    for block in _split_blocks(response):
        fields = _parse_block(block)
        operation_name = _extract_operation_name(fields)

        if catalog.get(operation_name) is None:
            raise PlannerError(f"Unsupported operation from LLM response: {operation_name}")

        operation_cls = _OPERATION_CLASSES.get(operation_name)
        if operation_cls is None:
            raise PlannerError(f"Operation class not registered: {operation_name}")

        plan.add(_instantiate_operation(operation_cls, fields))

    if plan.is_empty():
        raise PlannerError("LLM response did not contain any operations.")

    return plan


def _split_blocks(response: str) -> list[str]:
    blocks = [block.strip() for block in re.split(r"^\s*---\s*$", response.strip(), flags=re.MULTILINE)]
    return [block for block in blocks if block]


def _parse_block(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    current_key: str | None = None

    for raw_line in block.splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line:
            if current_key is not None:
                fields[current_key] = f"{fields[current_key]}\n"
            continue

        match = re.match(r"^([A-Z_]+)\s*(?::\s*|\s+)(.*)$", stripped_line)
        if not match:
            if current_key is None:
                raise PlannerError(f"Invalid LLM response line: {stripped_line}")

            fields[current_key] = f"{fields[current_key]}\n{raw_line.rstrip()}"
            continue

        key = match.group(1).strip().upper()
        value = match.group(2).strip()
        fields[key] = value
        current_key = key

    return fields


def _extract_operation_name(fields: dict[str, str]) -> str:
    operation_name = fields.pop("OPERATION", None)
    if not isinstance(operation_name, str) or not operation_name.strip():
        raise PlannerError("LLM response block is missing OPERATION.")

    return operation_name.strip()


def _instantiate_operation(operation_cls: type[Operation], fields: dict[str, str]) -> Operation:
    schema = operation_cls.schema()
    kwargs: dict[str, Any] = {}

    for parameter in schema["parameters"]:
        parameter_name = parameter["name"]
        raw_value = _resolve_field_value(operation_cls.operation_type, parameter_name, fields)

        if raw_value is None:
            if parameter["required"]:
                default_value = _default_value(operation_cls.operation_type, parameter_name, fields)
                if default_value is None:
                    raise PlannerError(f"Missing value for {operation_cls.operation_type}.{parameter_name}")
                kwargs[parameter_name] = default_value
                continue

            kwargs[parameter_name] = None
            continue

        kwargs[parameter_name] = raw_value

    operation = operation_cls(**kwargs)
    operation.validate()
    return operation


def _default_value(operation_type: str, parameter_name: str, fields: dict[str, str]) -> str | None:
    if operation_type in {"insert_method", "replace_method"} and parameter_name == "source_code":
        method_name = _resolve_field_value(operation_type, "method_name", fields)
        if method_name is None:
            return None
        return f"def {method_name}(self):\n    pass"

    return None


def _resolve_field_value(operation_type: str, parameter_name: str, fields: dict[str, str]) -> str | None:
    aliases = {
        "create_class": {
            "class_name": ("NAME", "CLASS", "CLASS_NAME"),
            "module": ("MODULE",),
        },
        "insert_method": {
            "target_class": ("CLASS", "TARGET_CLASS"),
            "method_name": ("METHOD", "METHOD_NAME"),
            "source_code": ("SOURCE_CODE", "CODE"),
        },
        "replace_method": {
            "target_class": ("CLASS", "TARGET_CLASS"),
            "method_name": ("METHOD", "METHOD_NAME"),
            "source_code": ("SOURCE_CODE", "CODE"),
        },
        "ensure_import": {
            "module": ("MODULE",),
            "name": ("NAME", "IMPORT_NAME"),
        },
    }

    keys = aliases.get(operation_type, {}).get(parameter_name, (parameter_name.upper(),))
    for key in keys:
        value = fields.get(key)
        if value is not None:
            if value.strip().lower() == "none":
                return None
            return value
    return None
