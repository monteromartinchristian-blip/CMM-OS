"""Phase 11.4 — fail-closed behavior of the reserved roadmap namespace.

Design Point: ``DP-104`` — Single-Front-Door Fail-Closed Operational CLI

A command whose canonical owner does not exist yet must still be *recognized* and
must still *fail*: it parses, it names the capability it was asked for, it
returns the stable ``CAPABILITY_UNAVAILABLE`` result with the stable exit code 5,
and it performs no side effect of any kind.  It must never pretend to have run:
no empty list presented as success, no fabricated store, no runtime built to
answer a question nothing can answer.

The only new operational families in this phase are ``status``, ``doctor``,
``ask`` and ``chat``; every other frozen roadmap identity is reserved here.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from types import ModuleType

import pytest

import cmm.__main__ as cli_main
from cmm.application.local_runtime import build_local_application_runtime
from cmm.cli_application import CliApplicationAdapter
from cmm.cli_commands import PHASE11_4_COMMANDS, phase11_4_descriptor
from cmm.cli_contracts import CliAvailability, CliExitCode
from cmm.cli_doctor import CliDoctor

#: One representative invocation of every frozen reserved capability.
RESERVED_INVOCATIONS = (
    ["config", "show"],
    ["config", "set", "key", "value"],
    ["goals", "list"],
    ["goals", "create", "Ship phase 11.4"],
    ["goals", "show", "goal-1"],
    ["goals", "pause", "goal-1"],
    ["goals", "resume", "goal-1"],
    ["workflows", "list"],
    ["workflows", "show", "wf-1"],
    ["workflows", "run", "wf-1"],
    ["workflows", "pause", "wf-1"],
    ["workflows", "resume", "wf-1"],
    ["workflows", "cancel", "wf-1"],
    ["approvals", "list"],
    ["approvals", "approve", "approval-1"],
    ["approvals", "reject", "approval-1"],
    ["memory", "search", "foo"],
    ["knowledge", "inspect", "item-1"],
    ["domains", "list"],
    ["plugins", "list"],
    ["backup", "create"],
    ["backup", "restore", "backup-1"],
    ["migrate"],
    ["logs"],
    ["metrics"],
)

#: The frozen command id each reserved invocation names.
RESERVED_COMMAND_IDS = (
    "config.show",
    "config.set",
    "goals.list",
    "goals.create",
    "goals.show",
    "goals.pause",
    "goals.resume",
    "workflows.list",
    "workflows.show",
    "workflows.run",
    "workflows.pause",
    "workflows.resume",
    "workflows.cancel",
    "approvals.list",
    "approvals.approve",
    "approvals.reject",
    "memory.search",
    "knowledge.inspect",
    "domains.list",
    "plugins.list",
    "backup.create",
    "backup.restore",
    "migrate",
    "logs",
    "metrics",
)

#: The command ids this phase backs with a real handler.
OPERATIONAL_COMMAND_IDS = ("status", "doctor", "ask", "chat")


def _reserved_ids_from_table() -> dict[str, str]:
    return {
        descriptor.command_id: descriptor.availability.value
        for descriptor in PHASE11_4_COMMANDS
    }


def _run(
    argv: list[str],
    *,
    adapter: CliApplicationAdapter | None = None,
    doctor: CliDoctor | None = None,
) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = cli_main.main(
        argv, application=adapter, doctor=doctor, stdout=out, stderr=err
    )
    return code, out.getvalue(), err.getvalue()


@pytest.fixture(scope="module")
def dependencies() -> tuple[CliApplicationAdapter, CliDoctor]:
    runtime = build_local_application_runtime()
    adapter = CliApplicationAdapter(runtime.gateway)
    return adapter, CliDoctor(adapter)


# ── Every reserved capability fails closed ───────────────────────────────────


@pytest.mark.parametrize(
    ("argv", "command_id"),
    tuple(zip(RESERVED_INVOCATIONS, RESERVED_COMMAND_IDS, strict=True)),
)
def test_a_reserved_capability_is_recognized_and_fails_closed(
    argv: list[str],
    command_id: str,
    dependencies: tuple[CliApplicationAdapter, CliDoctor],
) -> None:
    adapter, doctor = dependencies

    code, out, err = _run([*argv, "--output", "json"], adapter=adapter, doctor=doctor)

    assert code == int(CliExitCode.CAPABILITY_UNAVAILABLE) == 5
    assert out == ""
    document = json.loads(err)
    assert document["command"] == command_id
    assert document["ok"] is False
    assert document["status"] == CliAvailability.UNAVAILABLE.value
    assert document["error"]["code"] == "CAPABILITY_UNAVAILABLE"
    assert document["error"]["details"] == {"command": command_id}
    assert "not available in this platform build" in document["error"]["message"]
    assert document["data"] == {}


@pytest.mark.parametrize("argv", RESERVED_INVOCATIONS)
def test_a_reserved_capability_never_touches_the_canonical_graph(
    argv: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = build_local_application_runtime()
    seen: list[object] = []
    original = runtime.gateway.handle

    def recording(request: object) -> object:
        seen.append(request)
        return original(request)

    monkeypatch.setattr(runtime.gateway, "handle", recording)
    adapter = CliApplicationAdapter(runtime.gateway)

    _run(argv, adapter=adapter, doctor=CliDoctor(adapter))

    assert seen == []


@pytest.mark.parametrize("argv", RESERVED_INVOCATIONS)
def test_a_reserved_capability_builds_no_runtime(
    argv: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A reserved command must not start the platform to answer 'unavailable'."""

    calls: list[int] = []

    def _forbidden_factory() -> object:
        calls.append(1)
        raise AssertionError("a reserved command must not build the runtime")

    monkeypatch.setattr(
        "cmm.application.local_runtime.build_local_application_runtime",
        _forbidden_factory,
    )

    code, out, err = _run([*argv, "--output", "json"])

    assert calls == []
    assert code == 5
    assert out == ""
    assert json.loads(err)["error"]["code"] == "CAPABILITY_UNAVAILABLE"


def test_a_reserved_capability_reports_a_human_diagnostic_on_stderr(
    dependencies: tuple[CliApplicationAdapter, CliDoctor],
) -> None:
    adapter, doctor = dependencies

    code, out, err = _run(["plugins", "list"], adapter=adapter, doctor=doctor)

    assert code == 5
    assert out == ""
    assert err.strip() == (
        "CAPABILITY_UNAVAILABLE: Plugins is not available in this platform build."
    )
    assert "Traceback" not in err


def test_a_reserved_backup_creates_no_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    dependencies: tuple[CliApplicationAdapter, CliDoctor],
) -> None:
    """Fail-closed backup: no tar, no snapshot, no store mutation."""

    adapter, doctor = dependencies
    monkeypatch.chdir(tmp_path)
    before = sorted(path.name for path in tmp_path.iterdir())

    code, _, _ = _run(
        ["backup", "create", "--output", "json"], adapter=adapter, doctor=doctor
    )

    assert code == 5
    assert sorted(path.name for path in tmp_path.iterdir()) == before
    assert before == []


def test_a_reserved_operation_never_creates_an_environment_supplied_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No reserved command may invent an owner from environment configuration."""

    for name in ("CMM_BACKUP_DIR", "CMM_PLUGIN_DIR", "CMM_LOG_FILE"):
        monkeypatch.setenv(name, "/tmp/cmm-should-not-be-used")

    code, _, err = _run(["backup", "create", "--output", "json"])

    assert code == 5
    assert "/tmp/cmm-should-not-be-used" not in err


# ── The frozen table is the authority for availability ───────────────────────


def test_the_command_table_marks_exactly_four_commands_available() -> None:
    table = _reserved_ids_from_table()

    available = {
        command_id
        for command_id, availability in table.items()
        if availability == CliAvailability.AVAILABLE.value
    }

    assert available == set(OPERATIONAL_COMMAND_IDS)


def test_every_unavailable_command_id_has_a_failing_dispatch_path() -> None:
    for command_id in RESERVED_COMMAND_IDS:
        descriptor = phase11_4_descriptor(command_id)

        assert descriptor is not None
        assert descriptor.availability is CliAvailability.UNAVAILABLE


def test_the_operational_commands_are_never_reported_unavailable(
    dependencies: tuple[CliApplicationAdapter, CliDoctor],
) -> None:
    adapter, doctor = dependencies

    status_code, _, _ = _run(
        ["status", "--output", "json"], adapter=adapter, doctor=doctor
    )
    doctor_code, _, _ = _run(
        ["doctor", "--output", "json"], adapter=adapter, doctor=doctor
    )

    assert status_code == 0
    assert doctor_code == 0


def test_an_unknown_command_is_still_a_usage_error() -> None:
    """Reservation is not a licence to invent commands outside the namespace."""

    with pytest.raises(SystemExit) as exit_info:
        cli_main.main(["explode"])

    assert exit_info.value.code == int(CliExitCode.USAGE)


def test_the_reserved_families_declare_no_command_bus_or_registry() -> None:
    """Availability is a frozen table, not a mutable runtime structure."""

    module: ModuleType = __import__("cmm.cli_commands", fromlist=["_DESCRIPTOR_BY_ID"])

    assert isinstance(module.PHASE11_4_COMMANDS, tuple)
    assert not [name for name in dir(module) if "register_command" in name]
    assert not [name for name in dir(module) if "unregister" in name]
