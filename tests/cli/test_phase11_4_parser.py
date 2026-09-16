"""Phase 11.4 — canonical namespace reservation in the existing argparse root.

Design Point: ``DP-104`` — Single-Front-Door Fail-Closed Operational CLI

Phase 11.4 reserves the complete roadmap command namespace in the one existing
``cmm`` parser tree.  Reservation is a *parse* contract only: this module proves
the new families and subcommands are recognized, that their frozen metadata is
static and immutable, that the inherited subtrees keep their own registration,
and that the reserved operational namespace is distinct from the inherited
Domain SDK developer namespace.
"""

from __future__ import annotations

import argparse
import io
import json
from types import MappingProxyType

import pytest

import cmm.__main__ as cli_main
from cmm.__main__ import build_parser
from cmm.application.local_runtime import build_local_application_runtime
from cmm.cli_application import CliApplicationAdapter
from cmm.cli_commands import (
    PHASE11_4_COMMANDS,
    PHASE11_4_FAMILIES,
    is_phase11_4_command,
    phase11_4_command_id,
    phase11_4_descriptor,
    register_phase11_4_cli,
)
from cmm.cli_contracts import CliAvailability, CliCommandDescriptor
from cmm.cli_doctor import CliDoctor

#: The families that are operationally backed in Phase 11.4.
OPERATIONAL_FAMILIES = ("status", "doctor", "ask", "chat")

#: Every reserved roadmap command identity frozen for Phase 11.4.
RESERVED_COMMAND_IDS = frozenset(
    {
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
    }
)

AVAILABLE_COMMAND_IDS = frozenset(OPERATIONAL_FAMILIES)


def _parse(argv: list[str]) -> argparse.Namespace:
    return build_parser().parse_args(argv)


# ── New operational namespace ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "argv", [["status"], ["doctor"], ["chat", "--actor", "user-1"]]
)
def test_new_leaf_commands_parse(argv: list[str]) -> None:
    args = _parse(argv)

    assert args.command == argv[0]
    assert args.output == "human"
    assert args.quiet is False
    assert args.verbose is False


def test_status_and_doctor_accept_every_output_format() -> None:
    for output_format in ("human", "json", "yaml"):
        assert _parse(["status", "--output", output_format]).output == output_format
        assert _parse(["doctor", "--output", output_format]).output == output_format


def test_status_and_doctor_accept_quiet_and_verbose_flags() -> None:
    args = _parse(["status", "--quiet", "--verbose"])

    assert args.quiet is True
    assert args.verbose is True


def test_status_rejects_an_unknown_output_format() -> None:
    with pytest.raises(SystemExit) as exit_info:
        _parse(["status", "--output", "xml"])

    assert exit_info.value.code == 2


def test_ask_parses_text_actor_session_and_idempotency_key() -> None:
    args = _parse(
        [
            "ask",
            "hello",
            "--actor",
            "user-1",
            "--session",
            "session-1",
            "--idempotency-key",
            "key-1",
        ]
    )

    assert args.command == "ask"
    assert args.text == "hello"
    assert args.actor_id == "user-1"
    assert args.session_id == "session-1"
    assert args.idempotency_key == "key-1"


def test_ask_text_is_optional_so_stdin_can_supply_it() -> None:
    args = _parse(["ask", "--actor", "user-1"])

    assert args.text is None
    assert args.actor_id == "user-1"
    assert args.session_id is None
    assert args.idempotency_key is None


def test_ask_requires_an_explicit_actor() -> None:
    with pytest.raises(SystemExit) as exit_info:
        _parse(["ask", "hello"])

    assert exit_info.value.code == 2


def test_chat_parses_actor_and_session() -> None:
    args = _parse(["chat", "--actor", "user-1", "--session", "session-1"])

    assert args.command == "chat"
    assert args.actor_id == "user-1"
    assert args.session_id == "session-1"
    assert args.output == "human"


def test_chat_requires_an_explicit_actor() -> None:
    with pytest.raises(SystemExit) as exit_info:
        _parse(["chat"])

    assert exit_info.value.code == 2


# ── Reserved roadmap namespace ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "argv",
    [
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
    ],
)
def test_reserved_commands_parse(argv: list[str]) -> None:
    args = _parse(argv)

    assert is_phase11_4_command(args) is True
    assert phase11_4_command_id(args) in RESERVED_COMMAND_IDS
    assert args.output == "human"


def test_reserved_commands_accept_structured_output() -> None:
    args = _parse(["plugins", "list", "--output", "json"])

    assert phase11_4_command_id(args) == "plugins.list"
    assert args.output == "json"

    assert _parse(["backup", "create", "--output", "yaml"]).output == "yaml"


def test_reserved_families_require_a_subcommand() -> None:
    for family in ("config", "goals", "workflows", "approvals", "memory", "knowledge"):
        with pytest.raises(SystemExit) as exit_info:
            _parse([family])
        assert exit_info.value.code == 2


def test_reserved_identifier_commands_require_their_identifier() -> None:
    for argv in (["goals", "pause"], ["workflows", "cancel"], ["backup", "restore"]):
        with pytest.raises(SystemExit) as exit_info:
            _parse(argv)
        assert exit_info.value.code == 2


def test_unknown_command_remains_a_parser_error() -> None:
    for argv in (["explode"], ["agents", "list"], ["plugin", "list"]):
        with pytest.raises(SystemExit) as exit_info:
            _parse(argv)
        assert exit_info.value.code == 2


# ── Inherited subtrees ───────────────────────────────────────────────────────


def test_inherited_commands_still_parse() -> None:
    assert _parse(["run", "do something"]).command == "run"
    assert _parse(["develop", "do something"]).command == "develop"
    assert _parse(["validation", "run"]).validation_subcommand == "run"
    assert _parse(["domain", "validate", "path"]).domain_subcommand == "validate"
    assert _parse(["agent"]).command == "agent"


def test_inherited_commands_are_not_phase_11_4_commands() -> None:
    for argv in (["run", "goal"], ["develop", "goal"], ["validation", "run"]):
        args = _parse(argv)
        assert is_phase11_4_command(args) is False
        assert phase11_4_command_id(args) is None


def test_domain_and_domains_are_distinct_namespaces() -> None:
    developer = _parse(["domain", "validate", "path"])
    operational = _parse(["domains", "list"])

    assert is_phase11_4_command(developer) is False
    assert is_phase11_4_command(operational) is True
    assert phase11_4_command_id(operational) == "domains.list"

    parser = build_parser()
    help_text = parser.format_help()

    assert "domain" in help_text
    assert "domains" in help_text


# ── Frozen static metadata ───────────────────────────────────────────────────


def test_phase_11_4_command_table_covers_every_frozen_id() -> None:
    ids = [descriptor.command_id for descriptor in PHASE11_4_COMMANDS]

    assert len(ids) == len(set(ids))
    assert set(ids) == RESERVED_COMMAND_IDS | AVAILABLE_COMMAND_IDS


def test_phase_11_4_command_table_is_a_module_level_immutable_tuple() -> None:
    assert isinstance(PHASE11_4_COMMANDS, tuple)
    assert all(
        isinstance(descriptor, CliCommandDescriptor)
        for descriptor in PHASE11_4_COMMANDS
    )
    with pytest.raises(AttributeError):
        PHASE11_4_COMMANDS.append("static table")  # type: ignore[attr-defined]


def test_only_the_frozen_families_are_operationally_available() -> None:
    available = {
        descriptor.command_id
        for descriptor in PHASE11_4_COMMANDS
        if descriptor.availability is CliAvailability.AVAILABLE
    }
    unavailable = {
        descriptor.command_id
        for descriptor in PHASE11_4_COMMANDS
        if descriptor.availability is CliAvailability.UNAVAILABLE
    }

    assert available == AVAILABLE_COMMAND_IDS
    assert unavailable == RESERVED_COMMAND_IDS
    assert not {
        descriptor.command_id
        for descriptor in PHASE11_4_COMMANDS
        if descriptor.availability is CliAvailability.DEFERRED
    }


def test_every_descriptor_declares_help_text() -> None:
    for descriptor in PHASE11_4_COMMANDS:
        assert descriptor.help.strip()
        assert descriptor.help == descriptor.help.strip()


def test_descriptor_lookup_is_total_for_frozen_ids_and_closed_elsewhere() -> None:
    for command_id in sorted(RESERVED_COMMAND_IDS | AVAILABLE_COMMAND_IDS):
        descriptor = phase11_4_descriptor(command_id)

        assert descriptor is not None
        assert descriptor.command_id == command_id
    assert phase11_4_descriptor("run") is None
    assert phase11_4_descriptor("") is None
    assert phase11_4_descriptor("plugins.explode") is None


def test_phase_11_4_families_are_frozen_and_unique() -> None:
    assert isinstance(PHASE11_4_FAMILIES, tuple)
    assert len(PHASE11_4_FAMILIES) == len(set(PHASE11_4_FAMILIES))
    assert set(PHASE11_4_FAMILIES) == {
        command_id.split(".")[0] for command_id in RESERVED_COMMAND_IDS
    } | set(AVAILABLE_COMMAND_IDS)


def test_registering_twice_is_a_parser_defect_not_a_silent_success() -> None:
    """A duplicated namespace is an argparse conflict, never a silent override."""

    parser = argparse.ArgumentParser(prog="cmm")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_phase11_4_cli(subparsers)

    with pytest.raises(ValueError, match="conflicting subparser"):
        register_phase11_4_cli(subparsers)


def test_command_id_is_none_for_a_namespace_without_a_command() -> None:
    assert phase11_4_command_id(argparse.Namespace()) is None
    assert phase11_4_command_id(argparse.Namespace(command="status")) == "status"
    assert phase11_4_command_id(argparse.Namespace(command="config")) is None


def test_descriptor_index_is_not_a_mutable_registry() -> None:
    """The static table exposes no registration lifecycle."""

    import cmm.cli_commands as commands_module

    public = {
        name
        for name in vars(commands_module)
        if not name.startswith("_") and callable(getattr(commands_module, name))
    }

    assert "register" not in public
    assert "unregister" not in public
    assert not [name for name in public if "registry" in name.lower()]
    index = commands_module._DESCRIPTOR_BY_ID
    assert isinstance(index, MappingProxyType)


# ── Explicit dispatch of the new operational commands ────────────────────────


@pytest.fixture(scope="module")
def dependencies() -> tuple[CliApplicationAdapter, CliDoctor]:
    runtime = build_local_application_runtime()
    adapter = CliApplicationAdapter(runtime.gateway)
    return adapter, CliDoctor(adapter)


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


def test_status_dispatches_through_the_root_main(
    dependencies: tuple[CliApplicationAdapter, CliDoctor],
) -> None:
    adapter, doctor = dependencies

    code, out, err = _run(
        ["status", "--output", "json"], adapter=adapter, doctor=doctor
    )

    assert code == 0
    assert err == ""
    document = json.loads(out)
    assert set(document) == {
        "schema_version",
        "command",
        "ok",
        "status",
        "data",
        "error",
        "metadata",
    }
    assert document["command"] == "status"
    assert document["ok"] is True
    assert document["error"] is None
    assert document["schema_version"] == "v1"


def test_doctor_dispatches_through_the_root_main(
    dependencies: tuple[CliApplicationAdapter, CliDoctor],
) -> None:
    adapter, doctor = dependencies

    code, out, err = _run(
        ["doctor", "--output", "json"], adapter=adapter, doctor=doctor
    )

    assert code == 0
    assert err == ""
    document = json.loads(out)
    assert document["command"] == "doctor"
    assert document["ok"] is True
    assert document["data"]["summary"]["fail"] == 0


def test_status_human_output_names_the_command_and_its_status(
    dependencies: tuple[CliApplicationAdapter, CliDoctor],
) -> None:
    adapter, doctor = dependencies

    code, out, err = _run(["status"], adapter=adapter, doctor=doctor)

    assert code == 0
    assert err == ""
    assert out.splitlines()[0] == "status: success"
    assert "platform_state: ok" in out


def test_status_quiet_emits_only_the_primary_value(
    dependencies: tuple[CliApplicationAdapter, CliDoctor],
) -> None:
    adapter, doctor = dependencies

    code, out, err = _run(["status", "--quiet"], adapter=adapter, doctor=doctor)

    assert (code, err) == (0, "")
    assert out == "ok\n"


def test_verbose_human_output_adds_only_safe_metadata(
    dependencies: tuple[CliApplicationAdapter, CliDoctor],
) -> None:
    adapter, doctor = dependencies

    plain = _run(["status"], adapter=adapter, doctor=doctor)[1]
    verbose = _run(["status", "--verbose"], adapter=adapter, doctor=doctor)[1]

    assert verbose.startswith(plain)
    assert "metadata: " in verbose
    assert "AKIA" not in verbose


def test_a_failing_core_check_makes_doctor_exit_unhealthy(
    monkeypatch: pytest.MonkeyPatch,
    dependencies: tuple[CliApplicationAdapter, CliDoctor],
) -> None:
    adapter, doctor = dependencies
    gateway = vars(adapter)["_gateway"]

    def _defective_health() -> object:
        raise RuntimeError("internal defect at /private/tmp with AKIA-EXAMPLE")

    monkeypatch.setattr(vars(gateway)["_health"], "get_health", _defective_health)

    code, out, err = _run(
        ["doctor", "--output", "json"], adapter=adapter, doctor=doctor
    )

    assert code == 8
    assert out == ""
    document = json.loads(err)
    assert document["ok"] is False
    assert document["status"] == "failed"
    assert document["error"]["code"] == "DEPENDENCY_UNHEALTHY"
    assert "AKIA" not in err
    assert "Traceback" not in err


def test_a_failing_status_read_maps_to_the_stable_application_exit(
    monkeypatch: pytest.MonkeyPatch,
    dependencies: tuple[CliApplicationAdapter, CliDoctor],
) -> None:
    adapter, doctor = dependencies
    gateway = vars(adapter)["_gateway"]

    def _defective_capabilities() -> object:
        raise RuntimeError("internal defect with AKIA-EXAMPLE")

    monkeypatch.setattr(
        vars(gateway)["_capabilities"], "list_capabilities", _defective_capabilities
    )

    code, out, err = _run(
        ["status", "--output", "json"], adapter=adapter, doctor=doctor
    )

    assert code == 10
    assert out == ""
    document = json.loads(err)
    assert document["error"]["code"] == "INTERNAL_FAILURE"
    assert "AKIA" not in err


def test_injected_dependencies_are_used_instead_of_building_a_runtime(
    monkeypatch: pytest.MonkeyPatch,
    dependencies: tuple[CliApplicationAdapter, CliDoctor],
) -> None:
    adapter, doctor = dependencies

    def _forbidden_factory() -> object:
        raise AssertionError("injected dependencies must be used")

    monkeypatch.setattr(
        "cmm.application.local_runtime.build_local_application_runtime",
        _forbidden_factory,
    )

    code, out, _ = _run(["status", "--output", "json"], adapter=adapter, doctor=doctor)

    assert code == 0
    assert json.loads(out)["ok"] is True


def test_the_operational_commands_build_the_canonical_runtime_when_nothing_is_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cmm.application import local_runtime

    real_factory = local_runtime.build_local_application_runtime
    built: list[int] = []

    def _observed_factory() -> object:
        built.append(1)
        return real_factory()

    monkeypatch.setattr(
        local_runtime, "build_local_application_runtime", _observed_factory
    )

    code, out, _ = _run(["status", "--output", "json"])

    assert built == [1]
    assert code == 0
    assert json.loads(out)["data"]["platform_ready"] is True


def test_help_needs_no_dependency_and_no_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbidden_factory() -> object:
        raise AssertionError("--help must not build the runtime")

    monkeypatch.setattr(
        "cmm.application.local_runtime.build_local_application_runtime",
        _forbidden_factory,
    )

    with pytest.raises(SystemExit) as exit_info:
        cli_main.main(["--help"])

    assert exit_info.value.code == 0


def test_main_keeps_the_backward_compatible_signature() -> None:
    """``main(argv)`` stays valid for every embedded caller and test."""

    with pytest.raises(SystemExit) as exit_info:
        cli_main.main(["--help"])

    assert exit_info.value.code == 0
