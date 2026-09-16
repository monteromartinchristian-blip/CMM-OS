"""Phase 11.4 — deterministic human/JSON/YAML CLI rendering.

Design Point: ``DP-104`` — Single-Front-Door Fail-Closed Operational CLI

The renderer is the one presentation seam of the public CLI: it turns one
frozen :class:`~cmm.cli_contracts.CliResult` into exactly one output document,
writes success payloads to stdout and errors to stderr, and reports the frozen
process exit code.  The tests here prove the three representations carry the
same semantics, that structured output is parseable and free of ANSI and
incidental noise, and that quiet/verbose change commentary rather than data.
"""

from __future__ import annotations

import io
import json

import pytest
import yaml

from cmm.cli_contracts import (
    CliError,
    CliExitCode,
    CliOutputFormat,
    CliResult,
)
from cmm.cli_output import emit_cli_result, render_cli_result

ANSI_ESCAPE = "\x1b"

SUCCESS_RESULT = CliResult(
    command="status",
    ok=True,
    status="success",
    data={"platform_state": "ready", "services": ["domain.registry", "orchestration"]},
    metadata={"request_id": "request-1"},
)

ERROR_RESULT = CliResult(
    command="plugins.list",
    ok=False,
    status="unavailable",
    error=CliError(
        code="CAPABILITY_UNAVAILABLE",
        message="Plugins are not available in this platform build.",
        details={"command": "plugins.list"},
    ),
)


def _emit(
    result: CliResult,
    *,
    output_format: CliOutputFormat = CliOutputFormat.HUMAN,
    quiet: bool = False,
    verbose: bool = False,
    exit_code: CliExitCode = CliExitCode.SUCCESS,
) -> tuple[int, str, str]:
    """Emit *result* into buffers and return ``(code, stdout, stderr)``."""

    out, err = io.StringIO(), io.StringIO()
    code = emit_cli_result(
        result,
        output_format=output_format,
        quiet=quiet,
        verbose=verbose,
        stdout=out,
        stderr=err,
        exit_code=exit_code,
    )
    return code, out.getvalue(), err.getvalue()


# ── JSON ─────────────────────────────────────────────────────────────────────


def test_json_success_is_the_frozen_document_on_stdout() -> None:
    code, out, err = _emit(
        SUCCESS_RESULT,
        output_format=CliOutputFormat.JSON,
        exit_code=CliExitCode.SUCCESS,
    )

    assert code == 0
    assert err == ""
    assert json.loads(out) == SUCCESS_RESULT.to_dict()


def test_json_error_is_the_frozen_document_on_stderr() -> None:
    code, out, err = _emit(
        ERROR_RESULT,
        output_format=CliOutputFormat.JSON,
        exit_code=CliExitCode.CAPABILITY_UNAVAILABLE,
    )

    assert code == 5
    assert out == ""
    assert json.loads(err) == ERROR_RESULT.to_dict()
    assert json.loads(err)["error"]["code"] == "CAPABILITY_UNAVAILABLE"


def test_json_document_is_compact_deterministic_and_unpadded() -> None:
    text = render_cli_result(SUCCESS_RESULT, output_format=CliOutputFormat.JSON)

    assert text == json.dumps(
        SUCCESS_RESULT.to_dict(),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    assert "\n" not in text
    assert ", " not in text


def test_json_renders_non_ascii_without_escapes_and_without_ansi() -> None:
    result = CliResult(
        command="ask", ok=True, status="needs_clarification", data={"text": "¿Qué?"}
    )

    text = render_cli_result(result, output_format=CliOutputFormat.JSON)

    assert "¿Qué?" in text
    assert ANSI_ESCAPE not in text
    assert json.loads(text)["data"]["text"] == "¿Qué?"


# ── YAML ─────────────────────────────────────────────────────────────────────


def test_yaml_success_is_the_frozen_document_on_stdout() -> None:
    code, out, err = _emit(
        SUCCESS_RESULT,
        output_format=CliOutputFormat.YAML,
        exit_code=CliExitCode.SUCCESS,
    )

    assert code == 0
    assert err == ""
    assert yaml.safe_load(out) == SUCCESS_RESULT.to_dict()


def test_yaml_error_is_the_frozen_document_on_stderr() -> None:
    code, out, err = _emit(
        ERROR_RESULT,
        output_format=CliOutputFormat.YAML,
        exit_code=CliExitCode.CAPABILITY_UNAVAILABLE,
    )

    assert code == 5
    assert out == ""
    assert yaml.safe_load(err) == ERROR_RESULT.to_dict()


def test_yaml_matches_json_semantics_without_drift() -> None:
    result = CliResult(
        command="doctor",
        ok=True,
        status="ok",
        data={"checks": [{"check_id": "kernel", "status": "pass"}]},
        metadata={"request_id": "request-2"},
    )

    as_json = json.loads(render_cli_result(result, output_format=CliOutputFormat.JSON))
    as_yaml = yaml.safe_load(
        render_cli_result(result, output_format=CliOutputFormat.YAML)
    )

    assert as_yaml == as_json == result.to_dict()
    assert ANSI_ESCAPE not in render_cli_result(
        result, output_format=CliOutputFormat.YAML
    )


# ── Human ────────────────────────────────────────────────────────────────────


def test_human_success_prints_command_status_then_data_lines() -> None:
    text = render_cli_result(SUCCESS_RESULT, output_format=CliOutputFormat.HUMAN)

    lines = text.splitlines()

    assert lines[0] == "status: success"
    assert "platform_state: ready" in lines
    assert "services: domain.registry, orchestration" in lines
    assert ANSI_ESCAPE not in text


def test_human_error_prints_the_error_code_and_message() -> None:
    code, out, err = _emit(
        ERROR_RESULT,
        output_format=CliOutputFormat.HUMAN,
        exit_code=CliExitCode.CAPABILITY_UNAVAILABLE,
    )

    assert code == 5
    assert out == ""
    assert err.strip() == (
        "CAPABILITY_UNAVAILABLE: Plugins are not available in this platform build."
    )


def test_human_output_is_deterministic_across_calls() -> None:
    first = render_cli_result(SUCCESS_RESULT, output_format=CliOutputFormat.HUMAN)
    second = render_cli_result(SUCCESS_RESULT, output_format=CliOutputFormat.HUMAN)

    assert first == second


def test_human_rendering_of_nested_values_is_stable() -> None:
    result = CliResult(
        command="status",
        ok=True,
        status="success",
        data={
            "nested": {"b": 2, "a": 1},
            "empty": [],
            "flag": True,
            "nothing": None,
        },
    )

    text = render_cli_result(result, output_format=CliOutputFormat.HUMAN)

    assert 'nested: {"a":1,"b":2}' in text
    assert "empty: none" in text
    assert "flag: true" in text
    assert "nothing: none" in text
    assert text == render_cli_result(result, output_format=CliOutputFormat.HUMAN)


def test_human_error_never_prints_a_traceback() -> None:
    text = render_cli_result(ERROR_RESULT, output_format=CliOutputFormat.HUMAN)

    assert "Traceback" not in text
    assert "RuntimeError" not in text


def test_human_rendering_handles_a_frozen_nested_result() -> None:
    """A real result is frozen all the way down; human mode still renders it."""

    result = CliResult(
        command="status",
        ok=True,
        status="success",
        data={
            "platform_state": "ok",
            "capabilities": [
                {"capability_id": "orchestration", "status": "available"},
                {"capability_id": "sessions", "status": "available"},
            ],
            "metadata_note": {"nested": {"deeper": [1, 2]}},
        },
        metadata={"request_id": "request-3", "quiet_value": "ok"},
    )

    text = render_cli_result(result, output_format=CliOutputFormat.HUMAN)
    verbose = render_cli_result(
        result, output_format=CliOutputFormat.HUMAN, verbose=True
    )

    assert text.splitlines()[0] == "status: success"
    assert "platform_state: ok" in text
    assert (
        'capabilities: [{"capability_id":"orchestration","status":"available"},'
        '{"capability_id":"sessions","status":"available"}]'
    ) in text
    assert 'metadata_note: {"nested":{"deeper":[1,2]}}' in text
    assert "metadata: " in verbose
    assert render_cli_result(
        result, output_format=CliOutputFormat.HUMAN, quiet=True
    ) == ("ok")


def test_human_failure_rendering_handles_frozen_details() -> None:
    result = CliResult(
        command="doctor",
        ok=False,
        status="failed",
        error=CliError(
            code="DEPENDENCY_UNHEALTHY",
            message="Doctor reported failing canonical checks",
            details={"failed": ["application.health"], "counts": {"fail": 1}},
        ),
    )

    text = render_cli_result(result, output_format=CliOutputFormat.HUMAN, verbose=True)

    assert text.splitlines()[0] == (
        "DEPENDENCY_UNHEALTHY: Doctor reported failing canonical checks"
    )
    assert 'details: {"counts":{"fail":1},"failed":["application.health"]}' in text


# ── Quiet ────────────────────────────────────────────────────────────────────


def test_quiet_human_success_emits_only_the_primary_quiet_value() -> None:
    result = CliResult(
        command="status",
        ok=True,
        status="success",
        data={"platform_state": "ready"},
        metadata={"quiet_value": "ready"},
    )

    assert render_cli_result(
        result, output_format=CliOutputFormat.HUMAN, quiet=True
    ) == ("ready")


def test_quiet_human_success_without_a_quiet_value_emits_no_prose() -> None:
    assert (
        render_cli_result(
            SUCCESS_RESULT, output_format=CliOutputFormat.HUMAN, quiet=True
        )
        == ""
    )


def test_quiet_human_error_still_reports_the_error() -> None:
    code, out, err = _emit(
        ERROR_RESULT,
        output_format=CliOutputFormat.HUMAN,
        quiet=True,
        exit_code=CliExitCode.CAPABILITY_UNAVAILABLE,
    )

    assert code == 5
    assert out == ""
    assert "CAPABILITY_UNAVAILABLE" in err


def test_quiet_keeps_every_structured_field() -> None:
    loud = render_cli_result(SUCCESS_RESULT, output_format=CliOutputFormat.JSON)
    quiet = render_cli_result(
        SUCCESS_RESULT, output_format=CliOutputFormat.JSON, quiet=True
    )

    assert quiet == loud
    assert json.loads(quiet) == SUCCESS_RESULT.to_dict()
    assert (
        yaml.safe_load(
            render_cli_result(
                SUCCESS_RESULT, output_format=CliOutputFormat.YAML, quiet=True
            )
        )
        == SUCCESS_RESULT.to_dict()
    )


def test_quiet_success_creates_no_stdout_and_no_stderr_noise() -> None:
    code, out, err = _emit(
        SUCCESS_RESULT,
        output_format=CliOutputFormat.HUMAN,
        quiet=True,
    )

    assert (code, out, err) == (0, "", "")


# ── Verbose ──────────────────────────────────────────────────────────────────


def test_verbose_human_success_appends_safe_metadata_only() -> None:
    plain = render_cli_result(SUCCESS_RESULT, output_format=CliOutputFormat.HUMAN)
    verbose = render_cli_result(
        SUCCESS_RESULT, output_format=CliOutputFormat.HUMAN, verbose=True
    )

    assert verbose.startswith(plain)
    assert verbose != plain
    assert "request-1" in verbose
    assert ANSI_ESCAPE not in verbose


def test_verbose_human_success_without_metadata_adds_nothing() -> None:
    result = CliResult(command="status", ok=True, status="success")

    assert render_cli_result(
        result, output_format=CliOutputFormat.HUMAN, verbose=True
    ) == render_cli_result(result, output_format=CliOutputFormat.HUMAN)


def test_verbose_does_not_alter_structured_documents() -> None:
    for output_format in (CliOutputFormat.JSON, CliOutputFormat.YAML):
        assert render_cli_result(
            SUCCESS_RESULT, output_format=output_format, verbose=True
        ) == render_cli_result(SUCCESS_RESULT, output_format=output_format)


def test_verbose_never_adds_a_traceback_or_hidden_reasoning() -> None:
    text = render_cli_result(
        ERROR_RESULT, output_format=CliOutputFormat.HUMAN, verbose=True
    )

    assert "Traceback" not in text
    assert "reasoning" not in text.lower()


# ── Stream and exit-code contract ────────────────────────────────────────────


@pytest.mark.parametrize("output_format", list(CliOutputFormat))
def test_success_payloads_never_touch_stderr(
    output_format: CliOutputFormat,
) -> None:
    code, out, err = _emit(SUCCESS_RESULT, output_format=output_format)

    assert err == ""
    assert out != ""
    assert code == 0


@pytest.mark.parametrize("output_format", list(CliOutputFormat))
def test_errors_never_touch_stdout(output_format: CliOutputFormat) -> None:
    code, out, err = _emit(
        ERROR_RESULT,
        output_format=output_format,
        exit_code=CliExitCode.CAPABILITY_UNAVAILABLE,
    )

    assert out == ""
    assert err != ""
    assert code == 5


@pytest.mark.parametrize(
    "exit_code",
    [
        CliExitCode.SUCCESS,
        CliExitCode.USAGE,
        CliExitCode.INVALID_REQUEST,
        CliExitCode.NOT_FOUND,
        CliExitCode.CAPABILITY_UNAVAILABLE,
        CliExitCode.PERMISSION_DENIED,
        CliExitCode.CONFLICT,
        CliExitCode.DEPENDENCY_UNHEALTHY,
        CliExitCode.CANCELLED,
        CliExitCode.INTERNAL_FAILURE,
    ],
)
def test_emit_returns_the_exact_process_exit_code(exit_code: CliExitCode) -> None:
    result = SUCCESS_RESULT if exit_code is CliExitCode.SUCCESS else ERROR_RESULT

    code, _, _ = _emit(result, exit_code=exit_code)

    assert type(code) is int
    assert code == int(exit_code)
