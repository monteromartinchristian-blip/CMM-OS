"""Safe, deterministic validation for operation input and output schemas."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class OperationSchemaIssue:
    path: str
    code: str
    message: str


class OperationSchemaValidationError(ValueError):
    """Raised when a value does not satisfy a safe operation schema."""

    def __init__(self, issues: tuple[OperationSchemaIssue, ...]) -> None:
        self.issues = issues
        first = issues[0]
        super().__init__(f"{first.path}: {first.message}")


_KEYWORDS = frozenset(
    {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "minimum",
        "maximum",
        "minItems",
        "maxItems",
        "minLength",
        "maxLength",
        "description",
        "title",
        "default",
    }
)


def _types(raw: Any) -> tuple[str, ...]:
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, list) and all(isinstance(item, str) for item in raw):
        return tuple(raw)
    return ()


def _matches(value: Any, kind: str) -> bool:
    if kind == "null":
        return value is None
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and not (isinstance(value, float) and not math.isfinite(value))
        )
    if kind == "string":
        return isinstance(value, str)
    if kind == "array":
        return isinstance(value, (list, tuple))
    if kind == "object":
        return isinstance(value, Mapping)
    return False


def validate_operation_schema(
    value: Any,
    schema: Mapping[str, Any],
    *,
    raise_on_error: bool = False,
) -> tuple[OperationSchemaIssue, ...]:
    """Validate the supported, code-free subset of JSON Schema."""

    issues: list[OperationSchemaIssue] = []

    def issue(path: str, code: str, message: str) -> None:
        issues.append(OperationSchemaIssue(path=path, code=code, message=message))

    def visit(current: Any, current_schema: Any, path: str) -> None:
        if not isinstance(current_schema, Mapping):
            issue(path, "invalid_schema", "schema must be an object")
            return
        unsupported = sorted(set(current_schema) - _KEYWORDS)
        if unsupported:
            issue(
                path,
                "unsupported_keyword",
                f"unsupported schema keyword: {unsupported[0]}",
            )
            return
        kinds = _types(current_schema.get("type"))
        if "type" in current_schema and not kinds:
            issue(path, "invalid_schema", "type must be a string or list of strings")
            return
        if kinds and not any(_matches(current, kind) for kind in kinds):
            issue(path, "type", f"expected {' or '.join(kinds)}")
            return
        if isinstance(current, float) and not math.isfinite(current):
            issue(path, "finite", "number must be finite")
            return
        if "enum" in current_schema and current not in current_schema["enum"]:
            issue(path, "enum", "value is not in the allowed enum")
        if isinstance(current, (int, float)) and not isinstance(current, bool):
            if "minimum" in current_schema and current < current_schema["minimum"]:
                issue(path, "minimum", "value is below minimum")
            if "maximum" in current_schema and current > current_schema["maximum"]:
                issue(path, "maximum", "value exceeds maximum")
        if isinstance(current, str):
            if (
                "minLength" in current_schema
                and len(current) < current_schema["minLength"]
            ):
                issue(path, "min_length", "string is shorter than minLength")
            if (
                "maxLength" in current_schema
                and len(current) > current_schema["maxLength"]
            ):
                issue(path, "max_length", "string is longer than maxLength")
        if isinstance(current, (list, tuple)):
            if (
                "minItems" in current_schema
                and len(current) < current_schema["minItems"]
            ):
                issue(path, "min_items", "array has too few items")
            if (
                "maxItems" in current_schema
                and len(current) > current_schema["maxItems"]
            ):
                issue(path, "max_items", "array has too many items")
            item_schema = current_schema.get("items")
            if item_schema is not None:
                for index, item in enumerate(current):
                    visit(item, item_schema, f"{path}[{index}]")
        if isinstance(current, Mapping):
            properties = current_schema.get("properties", {})
            required = current_schema.get("required", ())
            if not isinstance(properties, Mapping) or not isinstance(
                required, (list, tuple)
            ):
                issue(path, "invalid_schema", "properties/required have invalid types")
                return
            for name in required:
                if name not in current:
                    issue(f"{path}.{name}", "required", "required field is missing")
            for name, item in current.items():
                item_path = f"{path}.{name}"
                if name in properties:
                    visit(item, properties[name], item_path)
                elif current_schema.get("additionalProperties", True) is False:
                    issue(
                        item_path, "additional_property", "unknown field is not allowed"
                    )

    visit(value, schema, "$")
    result = tuple(issues)
    if result and raise_on_error:
        raise OperationSchemaValidationError(result)
    return result


__all__ = [
    "OperationSchemaIssue",
    "OperationSchemaValidationError",
    "validate_operation_schema",
]
