"""Phase 11.4 — deterministic rendering of one public CLI result.

This module is the one presentation seam of the public CLI.  It turns a frozen
:class:`~cmm.cli_contracts.CliResult` into exactly one output document and
writes it to the correct stream: the required payload of a successful command
goes to stdout, diagnostics and errors go to stderr.  It reports the process
exit code it was given rather than deciding one, so exit-code policy stays with
the dispatcher that owns it.

Determinism is the contract: JSON uses canonical sorted compact encoding, YAML
uses ``yaml.safe_dump`` with sorted keys over the same document, and human mode
prints the command, its status and the data entries in sorted key order.  Both
structured representations carry the identical semantic document as
``CliResult.to_dict()``, so no representation can drift from another.

Quiet mode suppresses non-essential commentary: a human success prints only the
handler-declared primary value (``metadata["quiet_value"]``) or nothing at all,
while structured output stays complete because quiet must never remove required
data.  Verbose mode appends only the already-safe metadata the handler supplied;
it never adds a traceback, hidden reasoning or a live object, and it never
changes a structured document.

No color, progress indicator or logging is emitted here: structured stdout must
stay parseable and free of incidental noise.

See ``docs/reference/phase-11-cli.md``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, TextIO

import yaml

from cmm.cli_contracts import CliExitCode, CliOutputFormat, CliResult

__all__ = ["emit_cli_result", "render_cli_result"]

#: The presentation-owned message for an inconsistent result that reports
#: failure without carrying a public error.  Rendering stays total: a caller
#: defect becomes a safe diagnostic rather than a traceback.
UNREPORTED_FAILURE_CODE = "INTERNAL_FAILURE"
UNREPORTED_FAILURE_MESSAGE = "CLI command failed closed without a public error"

#: The metadata key a handler uses to declare the primary human scalar value.
QUIET_VALUE_KEY = "quiet_value"


def _require_result(result: object) -> CliResult:
    if not isinstance(result, CliResult):
        raise TypeError(f"result must be a CliResult, not {type(result).__name__}")
    return result


def _require_output_format(output_format: object) -> CliOutputFormat:
    if not isinstance(output_format, CliOutputFormat):
        raise TypeError(
            f"output_format must be a CliOutputFormat, not "
            f"{type(output_format).__name__}"
        )
    return output_format


def _compact_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


# ── Human value formatting ───────────────────────────────────────────────────


def _human_scalar(value: object) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return value
    if isinstance(value, int | float):
        return str(value)
    return _compact_json(value)


def _human_value(value: object) -> str:
    """Return one deterministic human-readable rendering of a safe value."""

    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return _compact_json(dict(value))
    if isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        items = list(value)
        if not items:
            return "none"
        if all(
            item is None or isinstance(item, bool | int | float | str) for item in items
        ):
            return ", ".join(_human_scalar(item) for item in items)
        return _compact_json(items)
    return _human_scalar(value)


def _render_human_success(result: CliResult, *, quiet: bool, verbose: bool) -> str:
    if quiet:
        quiet_value = result.metadata.get(QUIET_VALUE_KEY)
        return "" if quiet_value is None else _human_value(quiet_value)

    lines = [f"{result.command}: {result.status}"]
    for key in sorted(result.data):
        lines.append(f"{key}: {_human_value(result.data[key])}")
    if verbose and result.metadata:
        lines.append(f"metadata: {_compact_json(dict(result.metadata))}")
    return "\n".join(lines)


def _render_human_failure(result: CliResult, *, verbose: bool) -> str:
    error = result.error
    if error is None:
        return f"{UNREPORTED_FAILURE_CODE}: {UNREPORTED_FAILURE_MESSAGE}"

    lines = [f"{error.code}: {error.message}"]
    if verbose and error.details:
        lines.append(f"details: {_compact_json(dict(error.details))}")
    return "\n".join(lines)


def _render_human(result: CliResult, *, quiet: bool, verbose: bool) -> str:
    if not result.ok:
        return _render_human_failure(result, verbose=verbose)
    return _render_human_success(result, quiet=quiet, verbose=verbose)


# ── Representation renderers ─────────────────────────────────────────────────


def _render_json(result: CliResult) -> str:
    return json.dumps(
        result.to_dict(),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _render_yaml(result: CliResult) -> str:
    document = yaml.safe_dump(
        result.to_dict(),
        sort_keys=True,
        allow_unicode=True,
    )
    # ``safe_dump`` always terminates its document; emission owns the single
    # trailing newline so every representation emits exactly one document.
    return document.removesuffix("\n")


def render_cli_result(
    result: CliResult,
    *,
    output_format: CliOutputFormat,
    quiet: bool = False,
    verbose: bool = False,
) -> str:
    """Render *result* into one deterministic output document.

    The returned text never ends with a newline: emission owns the single
    trailing newline so exactly one document reaches the stream.
    """

    checked_result = _require_result(result)
    checked_format = _require_output_format(output_format)

    if checked_format is CliOutputFormat.JSON:
        return _render_json(checked_result)
    if checked_format is CliOutputFormat.YAML:
        return _render_yaml(checked_result)
    return _render_human(checked_result, quiet=quiet, verbose=verbose)


def _require_stream(stream: object, name: str) -> TextIO:
    if not callable(getattr(stream, "write", None)):
        raise TypeError(f"{name} must be a writable text stream")
    return stream  # type: ignore[return-value]


def emit_cli_result(
    result: CliResult,
    *,
    output_format: CliOutputFormat,
    quiet: bool = False,
    verbose: bool = False,
    stdout: TextIO,
    stderr: TextIO,
    exit_code: CliExitCode,
) -> int:
    """Emit *result* to the correct stream and return the process exit code.

    A successful result is written to *stdout* and a failed result to *stderr*,
    so a structured error envelope stays machine-readable on the diagnostic
    stream while stdout keeps carrying only real payload.
    """

    if not isinstance(exit_code, CliExitCode):
        raise TypeError(
            f"exit_code must be a CliExitCode, not {type(exit_code).__name__}"
        )
    checked_stdout = _require_stream(stdout, "stdout")
    checked_stderr = _require_stream(stderr, "stderr")

    text = render_cli_result(
        result,
        output_format=output_format,
        quiet=quiet,
        verbose=verbose,
    )
    if text:
        stream: Any = checked_stdout if result.ok else checked_stderr
        stream.write(f"{text}\n")

    return int(exit_code)
