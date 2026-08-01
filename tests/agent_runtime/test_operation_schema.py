from __future__ import annotations

import pytest

from cmm.agent_runtime.operation_schema import (
    OperationSchemaValidationError,
    validate_operation_schema,
)

SCHEMA = {
    "type": "object",
    "required": ["count", "items"],
    "properties": {
        "count": {"type": "number"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "note": {"type": ["string", "null"]},
                },
                "additionalProperties": False,
            },
        },
    },
    "additionalProperties": False,
}


def test_nested_schema_accepts_valid_json() -> None:
    assert (
        validate_operation_schema(
            {"count": 2.5, "items": [{"name": "a", "note": None}]}, SCHEMA
        )
        == ()
    )


@pytest.mark.parametrize(
    ("value", "path"),
    [
        ({"count": True, "items": []}, "$.count"),
        ({"count": float("nan"), "items": []}, "$.count"),
        ({"count": float("inf"), "items": []}, "$.count"),
        ({"count": 1, "items": [{}]}, "$.items[0].name"),
        ({"count": 1, "items": [{"name": "a", "extra": 1}]}, "$.items[0].extra"),
    ],
)
def test_schema_reports_structured_paths(value: object, path: str) -> None:
    errors = validate_operation_schema(value, SCHEMA)
    assert errors and errors[0].path == path
    with pytest.raises(OperationSchemaValidationError):
        validate_operation_schema(value, SCHEMA, raise_on_error=True)


def test_none_is_distinct_from_missing() -> None:
    nullable = {
        "type": "object",
        "required": ["value"],
        "properties": {"value": {"type": ["integer", "null"]}},
    }
    assert validate_operation_schema({"value": None}, nullable) == ()
    assert validate_operation_schema({}, nullable)[0].code == "required"


def test_remote_references_and_unknown_schema_keywords_are_rejected() -> None:
    assert (
        validate_operation_schema({}, {"$ref": "https://example.test/schema"})[0].code
        == "unsupported_keyword"
    )
    assert (
        validate_operation_schema({}, {"type": "object", "execute": "code"})[0].code
        == "unsupported_keyword"
    )
