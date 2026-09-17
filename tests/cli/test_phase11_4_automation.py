"""Phase 11.4 — root automation behavior of the one public front door.

Design Point: ``DP-104`` — Single-Front-Door Fail-Closed Operational CLI

The root ``cmm`` command is what a person types and what a script or CI job
calls.  These tests freeze the behavior that automation depends on: a version
that comes from the canonical package metadata rather than a second hard-coded
string, help that lists every inherited and new command while still labeling the
reserved ones as unavailable, a structured failure that a script can parse with
no traceback on stderr, and a broken downstream pipe that ends the process
quietly instead of as an error.

They also prove the startup promise: help, version and a usage error never
compose the application runtime, and an operational command composes it for real
in a real process.

The real-process checks run the documented automation commands verbatim from the
repository root, so what they prove is exactly what a CI job would observe.
"""

from __future__ import annotations

import importlib.metadata
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
import tomllib

import cmm.__main__ as cli_main
from cmm.application.local_runtime import build_local_application_runtime
from cmm.cli_application import CliApplicationAdapter
from cmm.cli_commands import PHASE11_4_COMMANDS
from cmm.cli_contracts import CliAvailability, CliExitCode
from cmm.cli_doctor import CliDoctor

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
DISTRIBUTION_NAME = "cmm-os"
ANSI_ESCAPE = "\x1b"
COMMAND_TIMEOUT_SECONDS = 300

#: The command families that existed before Phase 11.4 and must stay listed.
INHERITED_FAMILIES = ("run", "develop", "validation", "domain", "agent")

#: Every new Phase 11.4 roadmap family, operational or reserved.
NEW_FAMILIES = (
    "status",
    "doctor",
    "config",
    "chat",
    "ask",
    "goals",
    "workflows",
    "approvals",
    "memory",
    "knowledge",
    "domains",
    "plugins",
    "backup",
    "migrate",
    "logs",
    "metrics",
)

#: The command ids this build actually backs.
AVAILABLE_COMMAND_IDS = tuple(
    descriptor.command_id
    for descriptor in PHASE11_4_COMMANDS
    if descriptor.availability is CliAvailability.AVAILABLE
)


class _ClosedPipe:
    """A standard output whose reader is gone.

    Every write fails exactly like a pipe whose read end was closed, including
    the flush the interpreter performs while shutting down.
    """

    def write(self, text: str) -> int:
        raise BrokenPipeError(32, "Broken pipe")

    def flush(self) -> None:
        raise BrokenPipeError(32, "Broken pipe")

    def isatty(self) -> bool:
        return False


@pytest.fixture(scope="module")
def dependencies() -> tuple[CliApplicationAdapter, CliDoctor]:
    runtime = build_local_application_runtime()
    adapter = CliApplicationAdapter(runtime.gateway)
    return adapter, CliDoctor(adapter)


def _package_version() -> str:
    return importlib.metadata.version(DISTRIBUTION_NAME)


# ── Version ──────────────────────────────────────────────────────────────────


def test_version_comes_from_the_canonical_package_metadata(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli_main.main(["--version"])

    assert exit_info.value.code == int(CliExitCode.SUCCESS)
    assert capsys.readouterr().out.strip() == f"cmm {_package_version()}"


def test_the_version_has_exactly_one_source() -> None:
    """The distribution metadata and the project declaration must agree."""

    declared = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    assert declared["project"]["version"] == _package_version()


def test_version_needs_no_subcommand_and_writes_no_diagnostic(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli_main.main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().err == ""


# ── Help ─────────────────────────────────────────────────────────────────────


def test_help_lists_every_inherited_and_new_command_family(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli_main.main(["--help"])

    assert exit_info.value.code == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    for family in (*INHERITED_FAMILIES, *NEW_FAMILIES):
        assert family in captured.out, family


def test_help_labels_the_reserved_commands_without_pretending_availability(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        cli_main.main(["--help"])

    help_text = capsys.readouterr().out
    lines = {line.split()[0]: line for line in help_text.splitlines() if line.strip()}

    for family in ("plugins", "goals", "workflows", "backup"):
        assert "unavailable in this build" in lines[family], family

    for family in ("status", "doctor", "ask", "chat"):
        assert "unavailable in this build" not in lines[family], family


def test_help_names_the_commands_this_build_actually_backs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        cli_main.main(["--help"])

    assert ", ".join(AVAILABLE_COMMAND_IDS) in capsys.readouterr().out


# ── Lazy startup ─────────────────────────────────────────────────────────────


def test_help_version_and_a_usage_error_build_no_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []

    def _forbidden_factory() -> object:
        calls.append(1)
        raise AssertionError("the runtime must not be composed here")

    monkeypatch.setattr(
        "cmm.application.local_runtime.build_local_application_runtime",
        _forbidden_factory,
    )

    with pytest.raises(SystemExit) as help_exit:
        cli_main.main(["--help"])
    with pytest.raises(SystemExit) as version_exit:
        cli_main.main(["--version"])
    with pytest.raises(SystemExit) as usage_exit:
        cli_main.main(["explode"])

    assert help_exit.value.code == 0
    assert version_exit.value.code == 0
    assert usage_exit.value.code == int(CliExitCode.USAGE)
    assert calls == []


def test_a_usage_error_reports_usage_and_never_a_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli_main.main(["explode"])

    captured = capsys.readouterr()

    assert exit_info.value.code == 2
    assert captured.out == ""
    assert "usage:" in captured.err
    assert "Traceback" not in captured.err


# ── Real process behavior ────────────────────────────────────────────────────


def test_help_in_a_real_process_shares_the_root_parser() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "cmm", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    for family in (*INHERITED_FAMILIES, *NEW_FAMILIES):
        assert family in completed.stdout, family


def test_a_reserved_command_in_a_real_process_is_deterministic_and_fail_closed() -> (
    None
):
    first = subprocess.run(
        [sys.executable, "-m", "cmm", "plugins", "list", "--output", "json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=False,
    )
    second = subprocess.run(
        [sys.executable, "-m", "cmm", "plugins", "list", "--output", "json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=False,
    )

    assert first.returncode == second.returncode == 5
    assert first.stdout == ""
    assert first.stderr == second.stderr
    document = json.loads(first.stderr)
    assert document["schema_version"] == "v1"
    assert document["command"] == "plugins.list"
    assert document["ok"] is False
    assert document["error"]["code"] == "CAPABILITY_UNAVAILABLE"
    assert document["error"]["details"] == {"command": "plugins.list"}
    assert "Traceback" not in first.stderr
    assert ANSI_ESCAPE not in first.stderr


def test_an_operational_command_in_a_real_process_composes_the_runtime() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "cmm", "status", "--output", "json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    document = json.loads(completed.stdout)
    assert document["command"] == "status"
    assert document["ok"] is True
    assert document["data"]["platform_ready"] is True


# ── Broken downstream pipe ───────────────────────────────────────────────────


def test_a_closed_pipe_ends_the_process_quietly(
    dependencies: tuple[CliApplicationAdapter, CliDoctor],
) -> None:
    adapter, doctor = dependencies
    stderr = io.StringIO()

    code = cli_main.main(
        ["status", "--output", "json"],
        application=adapter,
        doctor=doctor,
        stdin=io.StringIO(""),
        stdout=_ClosedPipe(),  # type: ignore[arg-type]
        stderr=stderr,
    )

    assert code == int(CliExitCode.SUCCESS)
    assert stderr.getvalue() == ""


def test_a_closed_pipe_in_a_real_process_is_not_a_failure() -> None:
    process = subprocess.Popen(
        [sys.executable, "-m", "cmm", "--help"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    assert process.stderr is not None
    # The downstream consumer goes away before the command can write anything.
    process.stdout.close()

    stderr = process.stderr.read()
    process.stderr.close()
    code = process.wait(timeout=COMMAND_TIMEOUT_SECONDS)

    assert code == int(CliExitCode.SUCCESS)
    assert "Traceback" not in stderr
    assert "BrokenPipeError" not in stderr
