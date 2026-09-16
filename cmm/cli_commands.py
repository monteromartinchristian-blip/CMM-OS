"""Phase 11.4 — the canonical CLI namespace and its static command metadata.

This module owns four presentation concerns of the one public ``cmm`` front
door and nothing else:

- a **static, immutable** command table (:data:`PHASE11_4_COMMANDS`) that
  declares the frozen public command identity, its presentation availability and
  its help text;
- **registration** of the reserved roadmap namespace into the existing root
  ``argparse`` tree;
- **identity helpers** that turn one parsed namespace into a stable public
  command id, or into ``None`` when the namespace does not name a Phase 11.4
  command;
- **explicit dispatch** of one parsed command into exactly one handler, its
  fail-closed result, or its frozen exit code -- as straight-line branches, with
  no registry, router or runtime of its own.

The table is metadata, not authority: it executes nothing, resolves nothing,
holds no state and exposes no register/unregister lifecycle.  A command exists
in the parser whether or not a canonical owner backs it, and its availability
label is a presentation label derived from the frozen Phase 11.4 scope -- never
a substitute for a real canonical capability.  Reserved commands that parse here
fail closed when they are dispatched.

See ``docs/reference/phase-11-cli.md``.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping
from types import MappingProxyType
from typing import TextIO

from cmm.cli_application import CliApplicationAdapter
from cmm.cli_contracts import (
    CliAvailability,
    CliCommandDescriptor,
    CliError,
    CliExitCode,
    CliOutputFormat,
    CliResult,
    cli_exit_for_result,
)
from cmm.cli_doctor import CliDoctor
from cmm.cli_output import emit_cli_result

__all__ = [
    "PHASE11_4_COMMANDS",
    "PHASE11_4_FAMILIES",
    "dispatch_phase11_4",
    "emit_phase11_4_result",
    "is_phase11_4_command",
    "phase11_4_command_id",
    "phase11_4_descriptor",
    "phase11_4_requires_application",
    "phase11_4_unavailable_result",
    "register_phase11_4_cli",
]

#: Every public family the Phase 11.4 roadmap namespace reserves, including the
#: families that are operationally backed in this phase.
PHASE11_4_FAMILIES: tuple[str, ...] = (
    "status",
    "doctor",
    "ask",
    "chat",
    "config",
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

#: The global presentation label appended to a reserved command's help text.
UNAVAILABLE_LABEL = " (unavailable in this build)"

#: Families that expose `cmm <family> <subcommand>` and the argparse destination
#: that records the chosen subcommand.
_SUBCOMMAND_DEST: Mapping[str, str] = MappingProxyType(
    {
        "config": "config_subcommand",
        "goals": "goals_subcommand",
        "workflows": "workflows_subcommand",
        "approvals": "approvals_subcommand",
        "memory": "memory_subcommand",
        "knowledge": "knowledge_subcommand",
        "domains": "domains_subcommand",
        "plugins": "plugins_subcommand",
        "backup": "backup_subcommand",
    }
)

#: Short help of each reserved family parser.
_FAMILY_HELP: Mapping[str, str] = MappingProxyType(
    {
        "config": "Configuration inspection and mutation (unavailable in this build)",
        "goals": "Goal administration (unavailable in this build)",
        "workflows": "Workflow administration (unavailable in this build)",
        "approvals": "Approval administration (unavailable in this build)",
        "memory": "Operational memory inspection (unavailable in this build)",
        "knowledge": "Knowledge inspection (unavailable in this build)",
        "domains": "Available domain capability inspection (unavailable in this build)",
        "plugins": "Plugin inspection (unavailable in this build)",
        "backup": "Backup and restore (unavailable in this build)",
    }
)

#: The frozen Phase 11.4 command table.  Module-level, immutable, static.
PHASE11_4_COMMANDS: tuple[CliCommandDescriptor, ...] = (
    CliCommandDescriptor(
        command_id="status",
        availability=CliAvailability.AVAILABLE,
        help="Report platform state and canonical capability readiness",
    ),
    CliCommandDescriptor(
        command_id="doctor",
        availability=CliAvailability.AVAILABLE,
        help="Run read-only canonical diagnostics",
    ),
    CliCommandDescriptor(
        command_id="ask",
        availability=CliAvailability.AVAILABLE,
        help="Submit one canonical one-shot request",
    ),
    CliCommandDescriptor(
        command_id="chat",
        availability=CliAvailability.AVAILABLE,
        help="Run a minimal interactive canonical session",
    ),
    CliCommandDescriptor(
        command_id="config.show",
        availability=CliAvailability.UNAVAILABLE,
        help="Show redacted canonical configuration",
    ),
    CliCommandDescriptor(
        command_id="config.set",
        availability=CliAvailability.UNAVAILABLE,
        help="Set one canonical configuration value",
    ),
    CliCommandDescriptor(
        command_id="goals.list",
        availability=CliAvailability.UNAVAILABLE,
        help="List goals",
    ),
    CliCommandDescriptor(
        command_id="goals.create",
        availability=CliAvailability.UNAVAILABLE,
        help="Create a goal",
    ),
    CliCommandDescriptor(
        command_id="goals.show",
        availability=CliAvailability.UNAVAILABLE,
        help="Show one goal",
    ),
    CliCommandDescriptor(
        command_id="goals.pause",
        availability=CliAvailability.UNAVAILABLE,
        help="Pause one goal",
    ),
    CliCommandDescriptor(
        command_id="goals.resume",
        availability=CliAvailability.UNAVAILABLE,
        help="Resume one goal",
    ),
    CliCommandDescriptor(
        command_id="workflows.list",
        availability=CliAvailability.UNAVAILABLE,
        help="List workflows",
    ),
    CliCommandDescriptor(
        command_id="workflows.show",
        availability=CliAvailability.UNAVAILABLE,
        help="Show one workflow",
    ),
    CliCommandDescriptor(
        command_id="workflows.run",
        availability=CliAvailability.UNAVAILABLE,
        help="Run a workflow",
    ),
    CliCommandDescriptor(
        command_id="workflows.pause",
        availability=CliAvailability.UNAVAILABLE,
        help="Pause a workflow",
    ),
    CliCommandDescriptor(
        command_id="workflows.resume",
        availability=CliAvailability.UNAVAILABLE,
        help="Resume a workflow",
    ),
    CliCommandDescriptor(
        command_id="workflows.cancel",
        availability=CliAvailability.UNAVAILABLE,
        help="Cancel a workflow",
    ),
    CliCommandDescriptor(
        command_id="approvals.list",
        availability=CliAvailability.UNAVAILABLE,
        help="List pending approvals",
    ),
    CliCommandDescriptor(
        command_id="approvals.approve",
        availability=CliAvailability.UNAVAILABLE,
        help="Approve one pending approval",
    ),
    CliCommandDescriptor(
        command_id="approvals.reject",
        availability=CliAvailability.UNAVAILABLE,
        help="Reject one pending approval",
    ),
    CliCommandDescriptor(
        command_id="memory.search",
        availability=CliAvailability.UNAVAILABLE,
        help="Search operational memory",
    ),
    CliCommandDescriptor(
        command_id="knowledge.inspect",
        availability=CliAvailability.UNAVAILABLE,
        help="Inspect one knowledge item",
    ),
    CliCommandDescriptor(
        command_id="domains.list",
        availability=CliAvailability.UNAVAILABLE,
        help="List currently available domain capabilities",
    ),
    CliCommandDescriptor(
        command_id="plugins.list",
        availability=CliAvailability.UNAVAILABLE,
        help="List installed plugins",
    ),
    CliCommandDescriptor(
        command_id="backup.create",
        availability=CliAvailability.UNAVAILABLE,
        help="Create a platform backup",
    ),
    CliCommandDescriptor(
        command_id="backup.restore",
        availability=CliAvailability.UNAVAILABLE,
        help="Restore a platform backup",
    ),
    CliCommandDescriptor(
        command_id="migrate",
        availability=CliAvailability.UNAVAILABLE,
        help="Apply pending platform migrations",
    ),
    CliCommandDescriptor(
        command_id="logs",
        availability=CliAvailability.UNAVAILABLE,
        help="Query canonical platform logs",
    ),
    CliCommandDescriptor(
        command_id="metrics",
        availability=CliAvailability.UNAVAILABLE,
        help="Report canonical platform metrics",
    ),
)

#: Immutable index of the frozen table.  A mapping, not a registry: it has no
#: lifecycle, no mutation and no discovery, and an unknown id stays unknown.
_DESCRIPTOR_BY_ID: Mapping[str, CliCommandDescriptor] = MappingProxyType(
    {descriptor.command_id: descriptor for descriptor in PHASE11_4_COMMANDS}
)


# ── Static metadata helpers ──────────────────────────────────────────────────


def phase11_4_descriptor(command_id: str) -> CliCommandDescriptor | None:
    """Return the frozen descriptor of *command_id*, or ``None`` when unknown."""

    if not isinstance(command_id, str):
        raise TypeError("command_id must be a string")
    return _DESCRIPTOR_BY_ID.get(command_id)


def phase11_4_command_id(args: argparse.Namespace) -> str | None:
    """Return the stable public command id named by one parsed namespace.

    ``None`` means the namespace does not name a frozen Phase 11.4 command, so a
    partially written or inherited namespace can never be mistaken for a
    reserved capability.
    """

    family = getattr(args, "command", None)
    if not isinstance(family, str) or family not in PHASE11_4_FAMILIES:
        return None

    subcommand_dest = _SUBCOMMAND_DEST.get(family)
    if subcommand_dest is None:
        return family if family in _DESCRIPTOR_BY_ID else None

    subcommand = getattr(args, subcommand_dest, None)
    if not isinstance(subcommand, str) or not subcommand:
        return None

    command_id = f"{family}.{subcommand}"
    return command_id if command_id in _DESCRIPTOR_BY_ID else None


def is_phase11_4_command(args: argparse.Namespace) -> bool:
    """Return whether one parsed namespace names a frozen Phase 11.4 command."""

    return phase11_4_command_id(args) is not None


# ── Parser registration ──────────────────────────────────────────────────────


def _command_help(command_id: str) -> str:
    """Return the parser help of one frozen command, labeled by availability."""

    descriptor = _DESCRIPTOR_BY_ID[command_id]
    if descriptor.availability is CliAvailability.AVAILABLE:
        return descriptor.help
    return f"{descriptor.help}{UNAVAILABLE_LABEL}"


def _build_common_parser() -> argparse.ArgumentParser:
    """Return the parent parser carrying the global presentation options."""

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--output",
        dest="output",
        choices=tuple(member.value for member in CliOutputFormat),
        default=CliOutputFormat.HUMAN.value,
        help="Output representation",
    )
    common.add_argument(
        "--quiet",
        dest="quiet",
        action="store_true",
        default=False,
        help="Suppress non-essential human commentary",
    )
    common.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        default=False,
        help="Add safe diagnostic detail",
    )
    return common


def _register_reserved_families(
    subparsers: argparse._SubParsersAction,
    common: argparse.ArgumentParser,
) -> None:
    """Register the reserved roadmap families and their subcommands."""

    for family, subcommands in _RESERVED_SUBCOMMANDS.items():
        family_parser = subparsers.add_parser(family, help=_FAMILY_HELP[family])
        family_subparsers = family_parser.add_subparsers(
            dest=_SUBCOMMAND_DEST[family], required=True
        )
        for subcommand, build_arguments in subcommands:
            leaf = family_subparsers.add_parser(
                subcommand,
                parents=[common],
                help=_command_help(f"{family}.{subcommand}"),
            )
            if build_arguments is not None:
                build_arguments(leaf)


def _no_arguments(parser: argparse.ArgumentParser) -> None:
    """Declare that one reserved subcommand accepts no further argument."""


def _identifier_argument(name: str, help_text: str):
    def _build(parser: argparse.ArgumentParser) -> None:
        parser.add_argument(name, help=help_text)

    return _build


def _config_set_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("key", help="Configuration key")
    parser.add_argument("value", help="Configuration value")


#: Reserved family shape: each subcommand and the arguments its roadmap shape
#: requires.  A reserved command declares only the identity/value arguments the
#: roadmap names; it declares no operational option of its own.
_RESERVED_SUBCOMMANDS: Mapping[str, tuple[tuple[str, object], ...]] = MappingProxyType(
    {
        "config": (
            ("show", None),
            ("set", _config_set_arguments),
        ),
        "goals": (
            ("list", None),
            ("create", _identifier_argument("title", "Goal title")),
            ("show", _identifier_argument("goal_id", "Goal identifier")),
            ("pause", _identifier_argument("goal_id", "Goal identifier")),
            ("resume", _identifier_argument("goal_id", "Goal identifier")),
        ),
        "workflows": (
            ("list", None),
            ("show", _identifier_argument("workflow_id", "Workflow identifier")),
            ("run", _identifier_argument("workflow_id", "Workflow identifier")),
            ("pause", _identifier_argument("workflow_id", "Workflow identifier")),
            ("resume", _identifier_argument("workflow_id", "Workflow identifier")),
            ("cancel", _identifier_argument("workflow_id", "Workflow identifier")),
        ),
        "approvals": (
            ("list", None),
            ("approve", _identifier_argument("approval_id", "Approval identifier")),
            ("reject", _identifier_argument("approval_id", "Approval identifier")),
        ),
        "memory": (("search", _identifier_argument("query", "Search query")),),
        "knowledge": (
            ("inspect", _identifier_argument("item_id", "Knowledge item identifier")),
        ),
        "domains": (("list", None),),
        "plugins": (("list", None),),
        "backup": (
            ("create", None),
            ("restore", _identifier_argument("backup_id", "Backup identifier")),
        ),
    }
)


def register_phase11_4_cli(subparsers: argparse._SubParsersAction) -> None:
    """Register the frozen Phase 11.4 namespace into the one root parser.

    Registration adds parser surface only: no handler runs, no canonical owner
    is imported and no capability is resolved while the parser tree is built.
    """

    common = _build_common_parser()

    subparsers.add_parser("status", parents=[common], help=_command_help("status"))
    subparsers.add_parser("doctor", parents=[common], help=_command_help("doctor"))

    ask_parser = subparsers.add_parser(
        "ask", parents=[common], help=_command_help("ask")
    )
    ask_parser.add_argument(
        "text",
        nargs="?",
        default=None,
        help="Request text; omit it to read the request from stdin",
    )
    ask_parser.add_argument(
        "--actor", dest="actor_id", required=True, help="Explicit actor identity"
    )
    ask_parser.add_argument(
        "--session", dest="session_id", default=None, help="Existing session id"
    )
    ask_parser.add_argument(
        "--idempotency-key",
        dest="idempotency_key",
        default=None,
        help="Idempotency key for repeatable replay",
    )

    chat_parser = subparsers.add_parser(
        "chat", parents=[common], help=_command_help("chat")
    )
    chat_parser.add_argument(
        "--actor", dest="actor_id", required=True, help="Explicit actor identity"
    )
    chat_parser.add_argument(
        "--session", dest="session_id", default=None, help="Existing session id"
    )

    for command_id in ("migrate", "logs", "metrics"):
        subparsers.add_parser(
            command_id, parents=[common], help=_command_help(command_id)
        )

    _register_reserved_families(subparsers, common)


# ── Presentation options, results and explicit dispatch ──────────────────────

#: The public code of a reserved capability this build can not serve.
CAPABILITY_UNAVAILABLE_CODE = "CAPABILITY_UNAVAILABLE"

#: The one public message shape of a reserved capability.  It names what was
#: asked for and states the fact; it never suggests the command ran.
UNAVAILABLE_MESSAGE_TEMPLATE = "{capability} is not available in this platform build."

#: The public code of a request this build declares available but does not wire.
UNWIRED_COMMAND_CODE = "INTERNAL_FAILURE"

#: The public message of an available command without a dispatch branch.  It
#: carries no internal content.
UNWIRED_COMMAND_MESSAGE = "The command has no canonical handler in this platform build"

#: The frozen public code and status of a request the CLI itself must refuse.
#: Both are the canonical public names, so the frozen exit table resolves them
#: without the presentation layer importing a lower owner.
INVALID_REQUEST_CODE = "INVALID_REQUEST"
CANCELLED_CODE = "CANCELLED"
CANCELLED_STATUS = "cancelled"

#: The message of a one-shot command that was given two request texts at once.
ASK_INPUT_CONFLICT_MESSAGE = (
    "Ask accepts its request text either as an argument or on stdin, not both"
)

#: The message of a one-shot command that was given no request text at all.
ASK_INPUT_MISSING_MESSAGE = "Ask requires its request text as an argument or on stdin"

#: The message of an interrupted local interaction.  It states the local fact
#: and never claims a canonical request was cancelled: the CLI owns no
#: cancellation path, so a claim like that would be a lie.
INTERRUPTED_MESSAGE = (
    "The local CLI interaction was interrupted; no canonical cancellation was requested"
)

#: The message of a text option the caller left empty.
EMPTY_OPTION_MESSAGE_TEMPLATE = "{command} requires {option} to be a non-empty value"

#: The lines a chat loop reads as a local termination request.
CHAT_EXIT_COMMANDS: tuple[str, ...] = ("/exit", "/quit")

#: The presentation status of a chat loop that terminated with failed turns.
CHAT_DEGRADED_STATUS = "degraded"


def _capability_label(command_id: str) -> str:
    """Return the public capability name that one command id refers to."""

    family = command_id.split(".", 1)[0]
    return family.replace("_", " ").capitalize()


def phase11_4_unavailable_result(command_id: str) -> CliResult:
    """Return the frozen fail-closed result of one reserved capability.

    Reserved means reserved: the command is recognized, it names what was asked
    for, and it reports that no canonical owner can answer in this build.  No
    runtime is composed, no canonical owner is imported and no empty list is
    dressed up as a successful one.

    A command this build does serve is refused here, because a result claiming
    ``unavailable`` for a capability the platform does back would be a lie, and
    an unknown identity is refused because the frozen table is the only
    authority on what exists.
    """

    descriptor = phase11_4_descriptor(command_id)
    if descriptor is None:
        raise ValueError(f"unknown Phase 11.4 command id: {command_id!r}")
    if descriptor.availability is not CliAvailability.UNAVAILABLE:
        raise ValueError(f"{command_id!r} is available in this build")

    return CliResult(
        command=command_id,
        ok=False,
        status=CliAvailability.UNAVAILABLE.value,
        error=CliError(
            code=CAPABILITY_UNAVAILABLE_CODE,
            message=UNAVAILABLE_MESSAGE_TEMPLATE.format(
                capability=_capability_label(command_id)
            ),
            details={"command": command_id},
        ),
    )


def phase11_4_requires_application(args: argparse.Namespace) -> bool:
    """Return whether one Phase 11.4 command needs the canonical application.

    Only the operationally backed commands talk to the application boundary.  A
    reserved command is answered from the frozen table, so it must never start
    the platform -- and neither must a namespace that names no Phase 11.4
    command at all.
    """

    command_id = phase11_4_command_id(args)
    if command_id is None:
        return False
    return _DESCRIPTOR_BY_ID[command_id].availability is CliAvailability.AVAILABLE


def emit_phase11_4_result(
    result: CliResult,
    args: argparse.Namespace,
    *,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Emit one Phase 11.4 result under the parsed global presentation options.

    The exit code is not chosen here and not chosen by a handler: it is the
    frozen consequence of the result itself, so no command can report a process
    status other than the one its public result declares.  A namespace without
    the global options keeps their defaults, which lets an embedded caller emit
    a bare result without inventing presentation state.
    """

    return emit_cli_result(
        result,
        output_format=CliOutputFormat(
            getattr(args, "output", CliOutputFormat.HUMAN.value)
        ),
        quiet=bool(getattr(args, "quiet", False)),
        verbose=bool(getattr(args, "verbose", False)),
        stdout=stdout,
        stderr=stderr,
        exit_code=cli_exit_for_result(result),
    )


def _unwired_command_result(command_id: str) -> CliResult:
    """Return the fail-closed result of an available command without a handler.

    A descriptor marked available with no dispatch branch is a defect of this
    build, not a capability of the platform: reporting it as an internal failure
    keeps the table honest instead of claiming a success that nothing produced.
    """

    return CliResult(
        command=command_id,
        ok=False,
        status="failed",
        error=CliError(code=UNWIRED_COMMAND_CODE, message=UNWIRED_COMMAND_MESSAGE),
    )


def dispatch_phase11_4(
    args: argparse.Namespace,
    *,
    application: CliApplicationAdapter,
    doctor: CliDoctor,
    stdout: TextIO,
    stderr: TextIO,
    stdin: TextIO | None = None,
) -> int:
    """Dispatch one Phase 11.4 command and return its frozen process exit code.

    Dispatch is one explicit branch per command identity: no registry, no
    handler lookup, no mutable routing state and no second authority.  A command
    either projects the canonical application through the injected adapter,
    aggregates read-only diagnostics through the doctor, or fails closed because
    this build has no canonical owner for it.

    The reserved branch is answered from the frozen table alone and reads no
    dependency, so this dispatcher stays total and side-effect free for every
    frozen identity; the ordinary root entry point answers reserved capabilities
    before a runtime is ever composed, and reaches here only for the commands
    that genuinely need the application.

    *stdin* is the stream the interactive commands read; it is optional and only
    the conversational commands ever touch it, so every other command stays a
    pure function of its arguments.
    """

    command_id = phase11_4_command_id(args)
    if command_id is None:
        raise ValueError("args must name a frozen Phase 11.4 command")

    if _DESCRIPTOR_BY_ID[command_id].availability is CliAvailability.UNAVAILABLE:
        result = phase11_4_unavailable_result(command_id)
    elif command_id == "status":
        result = application.status()
    elif command_id == "doctor":
        result = doctor.run()
    elif command_id == "ask":
        return _run_ask(
            args,
            application=application,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
        )
    elif command_id == "chat":
        return _run_chat(
            args,
            application=application,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
        )
    else:
        result = _unwired_command_result(command_id)

    return emit_phase11_4_result(result, args, stdout=stdout, stderr=stderr)


# ── The conversational commands ──────────────────────────────────────────────


def _invalid_request_result(command_id: str, message: str) -> CliResult:
    """Return the fail-closed result of a request the CLI itself must refuse."""

    return CliResult(
        command=command_id,
        ok=False,
        status=INVALID_REQUEST_CODE.lower(),
        error=CliError(code=INVALID_REQUEST_CODE, message=message),
    )


def _interrupted_result(command_id: str) -> CliResult:
    """Return the result of a local interaction the user interrupted."""

    return CliResult(
        command=command_id,
        ok=False,
        status=CANCELLED_STATUS,
        error=CliError(code=CANCELLED_CODE, message=INTERRUPTED_MESSAGE),
    )


def _optional_text_option(
    args: argparse.Namespace, name: str, *, command_id: str
) -> str | CliResult | None:
    """Return one optional text option, the command's refusal, or ``None``.

    A blank value is refused instead of being read as absent: the caller asked
    for something specific, and the CLI will not guess which of the two they
    meant.
    """

    value = getattr(args, name, None)
    if value is None:
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return _invalid_request_result(
        command_id,
        EMPTY_OPTION_MESSAGE_TEMPLATE.format(
            command=_capability_label(command_id),
            option=f"--{name.replace('_', '-')}",
        ),
    )


def _piped_text(stdin: TextIO | None) -> str:
    """Return the request text a piped standard input supplies, or ``""``.

    An interactive terminal is never read: ``ask`` is a scriptable command and
    must not block on input nobody piped into it.  A stream that can not be read
    supplies nothing rather than turning a usability limit into a defect of the
    request.
    """

    stream = sys.stdin if stdin is None else stdin
    if bool(getattr(stream, "isatty", _not_interactive)()):
        return ""

    try:
        piped = stream.read()
    except (OSError, ValueError):
        return ""

    return piped.strip() if isinstance(piped, str) else ""


def _not_interactive() -> bool:
    """Return ``False`` for a stream that publishes no terminal state."""

    return False


def _one_shot_text(args: argparse.Namespace, stdin: TextIO | None) -> str | CliResult:
    """Return the one request text of a one-shot command, or its refusal.

    ``ask`` is scriptable input, so it takes its text from exactly one place:
    the positional argument or a piped standard input.  Both at once is an
    ambiguous request and neither is an empty one, and each is refused before
    any canonical request exists -- a one-shot command never guesses.
    """

    argument = getattr(args, "text", None)
    provided = argument.strip() if isinstance(argument, str) else ""
    piped = _piped_text(stdin)

    if provided and piped:
        return _invalid_request_result("ask", ASK_INPUT_CONFLICT_MESSAGE)
    if provided or piped:
        return provided or piped
    return _invalid_request_result("ask", ASK_INPUT_MISSING_MESSAGE)


def _run_ask(
    args: argparse.Namespace,
    *,
    application: CliApplicationAdapter,
    stdin: TextIO | None,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Run one one-shot request through the canonical application boundary."""

    session_id = _optional_text_option(args, "session_id", command_id="ask")
    idempotency_key = _optional_text_option(args, "idempotency_key", command_id="ask")
    for option in (session_id, idempotency_key):
        if isinstance(option, CliResult):
            return emit_phase11_4_result(option, args, stdout=stdout, stderr=stderr)

    text = _one_shot_text(args, stdin)
    if isinstance(text, CliResult):
        return emit_phase11_4_result(text, args, stdout=stdout, stderr=stderr)

    try:
        result = application.ask(
            text=text,
            actor_id=args.actor_id,
            session_id=session_id,
            idempotency_key=idempotency_key,
        )
    except KeyboardInterrupt:
        # The user stopped waiting locally.  Whether the canonical request ran
        # is unknown to the CLI, so it reports only what it knows: this local
        # interaction was cancelled, and no canonical cancellation was sent.
        result = _interrupted_result("ask")

    return emit_phase11_4_result(result, args, stdout=stdout, stderr=stderr)


def _read_chat_line(stdin: TextIO | None) -> str | None:
    """Return the next line of a chat input, or ``None`` at end of input."""

    stream = sys.stdin if stdin is None else stdin
    line = stream.readline()
    if not line:
        return None
    return line


def _chat_termination_result(
    session_id: str,
    *,
    submitted: int,
    failed: int,
    termination: str,
) -> CliResult:
    """Return the result that describes one locally terminated chat loop.

    The result describes the *local* loop, not the platform: a chat that ends on
    request or at end of input ended as asked, and every turn's own outcome was
    already reported in its own document.  The turn counts are published so a
    caller can tell an uneventful conversation from a degraded one.
    """

    return CliResult(
        command="chat",
        ok=True,
        status="success" if failed == 0 else CHAT_DEGRADED_STATUS,
        data={
            "session_id": session_id,
            "submitted": submitted,
            "failed": failed,
            "termination": termination,
        },
        metadata={"quiet_value": session_id},
    )


def _run_chat_loop(
    args: argparse.Namespace,
    *,
    application: CliApplicationAdapter,
    session_id: str,
    stdin: TextIO | None,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Read, submit and render one line at a time in one canonical session."""

    submitted = 0
    failed = 0

    while True:
        line = _read_chat_line(stdin)
        if line is None:
            termination = "eof"
            break

        text = line.rstrip("\r\n")
        if not text.strip():
            continue
        if text.strip() in CHAT_EXIT_COMMANDS:
            termination = text.strip().lstrip("/")
            break

        result = application.submit_message(
            text=text,
            actor_id=args.actor_id,
            session_id=session_id,
        )
        submitted += 1
        exit_code = emit_phase11_4_result(result, args, stdout=stdout, stderr=stderr)
        if result.ok:
            continue

        failed += 1
        if exit_code == int(CliExitCode.INTERNAL_FAILURE):
            # An internal failure is terminal for local interaction: repeating
            # the same call against a defect produces the same defect, and the
            # loop must not spin on it.
            return exit_code

    return emit_phase11_4_result(
        _chat_termination_result(
            session_id, submitted=submitted, failed=failed, termination=termination
        ),
        args,
        stdout=stdout,
        stderr=stderr,
    )


def _run_chat(
    args: argparse.Namespace,
    *,
    application: CliApplicationAdapter,
    stdin: TextIO | None,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    """Run the minimal interactive loop over one canonical session.

    The loop keeps no conversation of its own: no transcript, no history file,
    no editing, no regeneration, no attachments and no local notion of a
    message.  It resolves one canonical session (creating exactly one when the
    caller named none), submits each line through the canonical boundary and
    renders what comes back, so every turn is the platform's answer rather than
    the CLI's memory of one.
    """

    session_id = _optional_text_option(args, "session_id", command_id="chat")
    if isinstance(session_id, CliResult):
        return emit_phase11_4_result(session_id, args, stdout=stdout, stderr=stderr)

    try:
        resolved = application.resolve_session(
            session_id=session_id,
            actor_id=args.actor_id,
            command="chat",
        )
        if isinstance(resolved, CliResult):
            return emit_phase11_4_result(resolved, args, stdout=stdout, stderr=stderr)

        return _run_chat_loop(
            args,
            application=application,
            session_id=resolved,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
        )
    except KeyboardInterrupt:
        return emit_phase11_4_result(
            _interrupted_result("chat"), args, stdout=stdout, stderr=stderr
        )
