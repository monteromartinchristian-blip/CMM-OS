"""Phase 11.4 — the canonical CLI namespace and its static command metadata.

This module owns three presentation concerns of the one public ``cmm`` front
door and nothing else:

- a **static, immutable** command table (:data:`PHASE11_4_COMMANDS`) that
  declares the frozen public command identity, its presentation availability and
  its help text;
- **registration** of the reserved roadmap namespace into the existing root
  ``argparse`` tree;
- **identity helpers** that turn one parsed namespace into a stable public
  command id, or into ``None`` when the namespace does not name a Phase 11.4
  command.

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
from collections.abc import Mapping
from types import MappingProxyType

from cmm.cli_contracts import (
    CliAvailability,
    CliCommandDescriptor,
    CliOutputFormat,
)

__all__ = [
    "PHASE11_4_COMMANDS",
    "PHASE11_4_FAMILIES",
    "is_phase11_4_command",
    "phase11_4_command_id",
    "phase11_4_descriptor",
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
