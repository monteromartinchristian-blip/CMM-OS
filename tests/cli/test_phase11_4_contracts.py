"""Phase 11.4 — frozen public CLI presentation contracts.

Requirement: ``F11-018`` — Canonical Operational CLI
Design Point: ``DP-104`` — Single-Front-Door Fail-Closed Operational CLI

This module owns the frozen public CLI contract values: the schema version, the
output formats, the stable exit codes, the presentation availability vocabulary,
the safe error/result envelopes and the static command descriptor.  The tests
here prove the contract is exactly the frozen one and that the presentation
grammar keeps opaque, binary, unbounded and secret-shaped content out of a
public CLI result.
"""

from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import MappingProxyType

import pytest

from cmm.application import ApplicationErrorCode
from cmm.cli_contracts import (
    CLI_SCHEMA_VERSION,
    CliAvailability,
    CliCommandDescriptor,
    CliError,
    CliExitCode,
    CliOutputFormat,
    CliResult,
    cli_exit_for_application_error,
)

CONTRACTS_PATH = Path(__file__).resolve().parents[2] / "cmm" / "cli_contracts.py"

#: Every public CLI result carries exactly these keys.
RESULT_KEYS = frozenset(
    {
        "schema_version",
        "command",
        "ok",
        "status",
        "data",
        "error",
        "metadata",
    }
)

#: The frozen application-error to CLI exit-code mapping.
APPLICATION_ERROR_EXIT_CODES = {
    ApplicationErrorCode.INVALID_REQUEST: CliExitCode.INVALID_REQUEST,
    ApplicationErrorCode.UNSUPPORTED_VERSION: CliExitCode.INVALID_REQUEST,
    ApplicationErrorCode.POLICY_DENIED: CliExitCode.PERMISSION_DENIED,
    ApplicationErrorCode.RESOURCE_NOT_FOUND: CliExitCode.NOT_FOUND,
    ApplicationErrorCode.CONFLICT: CliExitCode.CONFLICT,
    ApplicationErrorCode.IDEMPOTENCY_CONFLICT: CliExitCode.CONFLICT,
    ApplicationErrorCode.CONCURRENCY_CONFLICT: CliExitCode.CONFLICT,
    ApplicationErrorCode.APPROVAL_REQUIRED: CliExitCode.PERMISSION_DENIED,
    ApplicationErrorCode.CANCELLED: CliExitCode.CANCELLED,
    ApplicationErrorCode.CAPABILITY_UNAVAILABLE: CliExitCode.CAPABILITY_UNAVAILABLE,
    ApplicationErrorCode.INTERNAL_FAILURE: CliExitCode.INTERNAL_FAILURE,
}


# ── Frozen scalar contract ───────────────────────────────────────────────────


def test_cli_schema_version_is_frozen() -> None:
    assert CLI_SCHEMA_VERSION == "v1"


def test_cli_exit_codes_are_frozen() -> None:
    assert int(CliExitCode.SUCCESS) == 0
    assert int(CliExitCode.USAGE) == 2
    assert int(CliExitCode.INVALID_REQUEST) == 3
    assert int(CliExitCode.NOT_FOUND) == 4
    assert int(CliExitCode.CAPABILITY_UNAVAILABLE) == 5
    assert int(CliExitCode.PERMISSION_DENIED) == 6
    assert int(CliExitCode.CONFLICT) == 7
    assert int(CliExitCode.DEPENDENCY_UNHEALTHY) == 8
    assert int(CliExitCode.CANCELLED) == 9
    assert int(CliExitCode.INTERNAL_FAILURE) == 10


def test_cli_exit_codes_have_no_unfrozen_member() -> None:
    assert {int(member) for member in CliExitCode} == {0, 2, 3, 4, 5, 6, 7, 8, 9, 10}


def test_cli_output_formats_are_frozen() -> None:
    assert {member.value for member in CliOutputFormat} == {"human", "json", "yaml"}


def test_cli_availability_values_are_frozen() -> None:
    assert {member.value for member in CliAvailability} == {
        "available",
        "unavailable",
        "deferred",
    }


# ── Frozen application-error mapping ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("code", "expected"),
    sorted(APPLICATION_ERROR_EXIT_CODES.items(), key=lambda item: item[0].value),
    ids=lambda value: getattr(value, "value", None),
)
def test_application_error_mapping_is_exact(
    code: ApplicationErrorCode, expected: CliExitCode
) -> None:
    assert cli_exit_for_application_error(code) is expected


def test_every_application_error_code_maps_to_one_exit_code() -> None:
    """The mapping is total over the closed application error enum."""

    for code in ApplicationErrorCode:
        first = cli_exit_for_application_error(code)
        assert first is cli_exit_for_application_error(code)
        assert first in set(CliExitCode)


def test_application_error_mapping_rejects_a_non_member() -> None:
    with pytest.raises(TypeError):
        cli_exit_for_application_error("INVALID_REQUEST")  # type: ignore[arg-type]


# ── CLI error envelope ───────────────────────────────────────────────────────


def test_cli_error_to_dict_shape() -> None:
    error = CliError(code="CAPABILITY_UNAVAILABLE", message="Plugins are unavailable")

    assert error.to_dict() == {
        "code": "CAPABILITY_UNAVAILABLE",
        "message": "Plugins are unavailable",
        "details": {},
    }


def test_cli_error_freezes_details_and_thaws_them_for_output() -> None:
    details = {"command": "plugins.list", "nested": {"items": [1, 2]}}
    error = CliError(code="CAPABILITY_UNAVAILABLE", message="m", details=details)

    details["command"] = "mutated"

    assert error.to_dict()["details"] == {
        "command": "plugins.list",
        "nested": {"items": [1, 2]},
    }
    assert isinstance(error.details, MappingProxyType)
    assert isinstance(error.details["nested"], MappingProxyType)
    assert error.details["nested"]["items"] == (1, 2)
    with pytest.raises(TypeError):
        error.details["command"] = "mutated"  # type: ignore[index]


@pytest.mark.parametrize("code", ["", "   ", "\n"])
def test_cli_error_rejects_a_blank_code(code: str) -> None:
    with pytest.raises(ValueError):
        CliError(code=code, message="message")


@pytest.mark.parametrize("message", ["", "   ", "\n"])
def test_cli_error_rejects_a_blank_message(message: str) -> None:
    with pytest.raises(ValueError):
        CliError(code="INTERNAL_FAILURE", message=message)


def test_cli_error_rejects_a_non_text_code() -> None:
    with pytest.raises(TypeError):
        CliError(code=1, message="message")  # type: ignore[arg-type]


# ── CLI result envelope ──────────────────────────────────────────────────────


def test_cli_result_to_dict_contains_exactly_the_frozen_keys() -> None:
    result = CliResult(command="status", ok=True, status="success", data={"a": 1})

    document = result.to_dict()

    assert set(document) == RESULT_KEYS
    assert document == {
        "schema_version": "v1",
        "command": "status",
        "ok": True,
        "status": "success",
        "data": {"a": 1},
        "error": None,
        "metadata": {},
    }


def test_cli_result_to_dict_carries_the_error_envelope() -> None:
    result = CliResult(
        command="plugins.list",
        ok=False,
        status="unavailable",
        error=CliError(code="CAPABILITY_UNAVAILABLE", message="unavailable"),
    )

    assert result.to_dict()["error"] == {
        "code": "CAPABILITY_UNAVAILABLE",
        "message": "unavailable",
        "details": {},
    }
    assert result.to_dict()["data"] == {}


def test_cli_result_to_dict_is_deterministic_and_json_native() -> None:
    result = CliResult(
        command="status",
        ok=True,
        status="success",
        data={"services": ["a", "b"], "nested": {"flag": False, "count": 2}},
        metadata={"request_id": "request-1"},
    )

    first = result.to_dict()
    second = result.to_dict()

    assert first == second
    assert json.loads(json.dumps(first, sort_keys=True)) == first
    assert result.to_dict() == first


def test_cli_result_defaults_to_an_empty_successful_document() -> None:
    result = CliResult(command="status", ok=True, status="success")

    assert result.data == {}
    assert result.error is None
    assert result.metadata == {}
    assert result.schema_version == CLI_SCHEMA_VERSION


def test_cli_result_freezes_input_mappings() -> None:
    data = {"capabilities": ["status"]}
    metadata = {"request_id": "request-1"}
    result = CliResult(
        command="status", ok=True, status="success", data=data, metadata=metadata
    )

    data["capabilities"] = ["mutated"]
    metadata["request_id"] = "mutated"

    assert result.to_dict()["data"] == {"capabilities": ["status"]}
    assert result.to_dict()["metadata"] == {"request_id": "request-1"}


@pytest.mark.parametrize("command", ["", "   ", "\n"])
def test_cli_result_rejects_a_blank_command(command: str) -> None:
    with pytest.raises(ValueError):
        CliResult(command=command, ok=True, status="success")


@pytest.mark.parametrize("status", ["", "   "])
def test_cli_result_rejects_a_blank_status(status: str) -> None:
    with pytest.raises(ValueError):
        CliResult(command="status", ok=True, status=status)


def test_cli_result_rejects_a_non_bool_ok() -> None:
    with pytest.raises(TypeError):
        CliResult(command="status", ok="yes", status="success")  # type: ignore[arg-type]


def test_cli_result_rejects_a_non_error_error_field() -> None:
    with pytest.raises(TypeError):
        CliResult(
            command="status",
            ok=False,
            status="failed",
            error="INTERNAL_FAILURE",  # type: ignore[arg-type]
        )


def test_cli_result_rejects_a_foreign_schema_version() -> None:
    with pytest.raises(ValueError):
        CliResult(command="status", ok=True, status="success", schema_version="v2")


# ── Bounded presentation grammar ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "value",
    [
        object(),
        lambda: None,
        RuntimeError("internal defect"),
        b"bytes",
        bytearray(b"bytes"),
        float("nan"),
        float("inf"),
        {"object": object()},
        {"nested": [object()]},
    ],
    ids=[
        "opaque-object",
        "callable",
        "exception",
        "bytes",
        "bytearray",
        "nan",
        "inf",
        "nested-object",
        "sequence-object",
    ],
)
def test_cli_result_rejects_opaque_values(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        CliResult(command="status", ok=True, status="success", data={"value": value})


@pytest.mark.parametrize(
    "key",
    [
        "password",
        "api_key",
        "apiKey",
        "refresh-token",
        "credential",
        "private_key",
        "authorization",
        "session_cookie",
        "secrets",
    ],
)
def test_cli_result_rejects_secret_shaped_keys(key: str) -> None:
    with pytest.raises(ValueError):
        CliResult(command="status", ok=True, status="success", data={key: "value"})
    with pytest.raises(ValueError):
        CliError(code="INTERNAL_FAILURE", message="m", details={key: "value"})


def test_cli_result_rejects_an_unbounded_string() -> None:
    with pytest.raises(ValueError):
        CliResult(
            command="status",
            ok=True,
            status="success",
            data={"value": "x" * 100_000},
        )


def test_cli_result_rejects_deep_nesting() -> None:
    value: object = "leaf"
    for _ in range(20):
        value = {"nested": value}

    with pytest.raises(ValueError):
        CliResult(command="status", ok=True, status="success", data={"value": value})


def test_cli_result_rejects_too_many_items() -> None:
    with pytest.raises(ValueError):
        CliResult(
            command="status",
            ok=True,
            status="success",
            data={"value": list(range(5_000))},
        )


def test_cli_result_serially_encodes_a_large_but_bounded_document() -> None:
    result = CliResult(
        command="status",
        ok=True,
        status="success",
        data={"items": [{"index": index} for index in range(100)]},
    )

    assert json.loads(json.dumps(result.to_dict(), sort_keys=True)) == result.to_dict()


# ── Static command descriptor ────────────────────────────────────────────────


def test_cli_command_descriptor_is_immutable_metadata() -> None:
    descriptor = CliCommandDescriptor(
        command_id="plugins.list",
        availability=CliAvailability.UNAVAILABLE,
        help="List installed plugins",
    )

    assert descriptor.command_id == "plugins.list"
    assert descriptor.availability is CliAvailability.UNAVAILABLE
    assert descriptor.help == "List installed plugins"
    with pytest.raises(FrozenInstanceError):
        descriptor.command_id = "other"  # type: ignore[misc]


@pytest.mark.parametrize("command_id", ["", "   "])
def test_cli_command_descriptor_rejects_a_blank_command_id(command_id: str) -> None:
    with pytest.raises(ValueError):
        CliCommandDescriptor(
            command_id=command_id,
            availability=CliAvailability.AVAILABLE,
            help="help",
        )


def test_cli_command_descriptor_rejects_a_non_availability_member() -> None:
    with pytest.raises(TypeError):
        CliCommandDescriptor(
            command_id="status",
            availability="available",  # type: ignore[arg-type]
            help="help",
        )


# ── Dependency discipline ────────────────────────────────────────────────────


def test_cli_contracts_import_no_lower_canonical_owner() -> None:
    """The presentation contracts import nothing below ``cmm.application``."""

    tree = ast.parse(CONTRACTS_PATH.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    forbidden = ("cmm.domains", "cmm.agent_runtime", "cmm.orchestration", "kernel")
    for module in imported:
        assert not module.startswith(forbidden), module
        if module.startswith("cmm."):
            assert module.startswith("cmm.application"), module
