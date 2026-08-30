"""Phase 10.35 — Domain SDK CLI Interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cmm.domains.errors import DomainError
from cmm.domains.sdk.scaffold import DomainScaffolder


def register_domain_cli(subparsers: argparse._SubParsersAction) -> None:
    """Register the official `domain` parser and subcommands into cmm CLI."""
    domain_parser = subparsers.add_parser(
        "domain",
        help="Domain SDK tooling for CMM OS Domain Packs (Phase 10.35)",
    )
    domain_subparsers = domain_parser.add_subparsers(
        dest="domain_subcommand", required=True
    )

    # 1. cmm domain create <name>
    create_p = domain_subparsers.add_parser(
        "create",
        help="Create a new Domain Pack scaffold",
    )
    create_p.add_argument("name", help="Domain slug name (e.g. 'my-domain')")
    create_p.add_argument(
        "--path",
        "--destination",
        dest="destination",
        default=None,
        type=Path,
        help="Destination directory (defaults to ./<name>)",
    )
    create_p.add_argument(
        "--template",
        default="basic_domain",
        help="Scaffold template (default: basic_domain)",
    )

    # 2. cmm domain validate <path>
    validate_p = domain_subparsers.add_parser(
        "validate",
        help="Validate a Domain Pack with canonical Domain Validation",
    )
    validate_p.add_argument(
        "path",
        type=Path,
        help="Path to Domain Pack root directory",
    )

    # 3. cmm domain test <path>
    test_p = domain_subparsers.add_parser(
        "test",
        help="Execute isolated development tests for a Domain Pack",
    )
    test_p.add_argument(
        "path",
        type=Path,
        help="Path to Domain Pack root directory",
    )

    # 4. cmm domain pack <path>
    pack_p = domain_subparsers.add_parser(
        "pack",
        help="Package a Domain Pack into a deterministic transport archive",
    )
    pack_p.add_argument(
        "path",
        type=Path,
        help="Path to Domain Pack root directory",
    )
    pack_p.add_argument(
        "--output",
        "-o",
        dest="output",
        default=None,
        type=Path,
        help="Output path for .tar.gz archive",
    )


def handle_domain_cli(args: argparse.Namespace) -> int:
    """Dispatch `domain` subcommand to appropriate handler."""
    subcommand = getattr(args, "domain_subcommand", None)

    try:
        if subcommand == "create":
            return _handle_create(args)
        elif subcommand == "validate":
            return _handle_validate(args)
        elif subcommand == "test":
            return _handle_test(args)
        elif subcommand == "pack":
            return _handle_pack(args)
        else:
            print(f"Error: Unknown domain subcommand: {subcommand}", file=sys.stderr)
            return 2
    except DomainError as exc:
        print(f"Error: {exc.message if hasattr(exc, 'message') else str(exc)}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _handle_create(args: argparse.Namespace) -> int:
    scaffolder = DomainScaffolder()
    destination = getattr(args, "destination", None)
    template = getattr(args, "template", "basic_domain")
    dest_path = scaffolder.create(
        name=args.name,
        destination=destination,
        template=template,
    )
    print(f"Created domain pack '{args.name}' at {dest_path}")
    return 0


def _handle_validate(args: argparse.Namespace) -> int:
    # Will be connected in Task 3
    print("validate not yet implemented", file=sys.stderr)
    return 1


def _handle_test(args: argparse.Namespace) -> int:
    # Will be connected in Task 5
    print("test not yet implemented", file=sys.stderr)
    return 1


def _handle_pack(args: argparse.Namespace) -> int:
    # Will be connected in Task 6
    print("pack not yet implemented", file=sys.stderr)
    return 1
