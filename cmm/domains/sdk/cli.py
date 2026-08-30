"""Phase 10.35 — Domain SDK CLI Interface and Canonical Validation Facade."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from cmm.domains.enums import DomainValidationStatus
from cmm.domains.errors import DomainError
from cmm.domains.sdk.packager import DomainPackager
from cmm.domains.sdk.scaffold import DomainScaffolder
from cmm.domains.sdk.validation import validate_domain_path


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
        print(
            f"Error: {exc.message if hasattr(exc, 'message') else str(exc)}",
            file=sys.stderr,
        )
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
    path = getattr(args, "path", None)
    if path is None:
        print("Error: path is required for validation", file=sys.stderr)
        return 1

    result = validate_domain_path(path)

    blocking_findings = [f for f in result.findings if getattr(f, "blocking", False)]
    warnings = list(result.warnings)

    print(f"Domain: {result.domain_id}")
    print(f"Version: {result.version}")
    print(f"Status: {result.status.value}")
    print(f"Blocking findings: {len(blocking_findings)}")
    print(f"Warnings: {len(warnings)}")

    if blocking_findings:
        print("\nBlocking findings:")
        for f in blocking_findings:
            msg = getattr(f, "message", str(f))
            print(f"- [{getattr(f, 'code', 'error')}] {msg}")

    if warnings:
        print("\nWarnings:")
        for w in warnings:
            msg = getattr(w, "message", str(w))
            print(f"- [{getattr(w, 'code', 'warning')}] {msg}")

    if (
        result.status in (DomainValidationStatus.PASSED, DomainValidationStatus.WARNING)
        and not blocking_findings
    ):
        return 0
    return 1


def _handle_test(args: argparse.Namespace) -> int:
    path = getattr(args, "path", None)
    if path is None:
        print("Error: path is required for test", file=sys.stderr)
        return 1

    pack_root = Path(path).resolve()
    if not pack_root.exists() or not pack_root.is_dir():
        print(
            f"Error: Domain pack root does not exist or is not a directory: {path}",
            file=sys.stderr,
        )
        return 1

    # 1. Canonical validation
    result = validate_domain_path(pack_root)
    blocking = [f for f in result.findings if getattr(f, "blocking", False)]
    if (
        result.status in (DomainValidationStatus.FAILED, DomainValidationStatus.ERROR)
        or blocking
    ):
        print(
            f"Error: Domain validation failed for {pack_root} with status={result.status.value}",
            file=sys.stderr,
        )
        for f in blocking:
            print(
                f"- [{getattr(f, 'code', 'error')}] {getattr(f, 'message', str(f))}",
                file=sys.stderr,
            )
        return 1

    # 2. Check tests directory
    tests_dir = (pack_root / "tests").resolve()
    try:
        tests_dir.relative_to(pack_root)
    except ValueError:
        print(
            f"Error: Tests directory escapes domain pack root: {tests_dir}",
            file=sys.stderr,
        )
        return 1

    if not tests_dir.exists() or not tests_dir.is_dir():
        print(f"Error: No tests directory found in {pack_root}", file=sys.stderr)
        return 1

    # 3. Execute pytest safely via argv list
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(tests_dir)],
        cwd=str(pack_root),
        check=False,
    )
    return completed.returncode


def _handle_pack(args: argparse.Namespace) -> int:
    path = getattr(args, "path", None)
    if path is None:
        print("Error: path is required for pack", file=sys.stderr)
        return 1

    output = getattr(args, "output", None)
    packager = DomainPackager()
    archive_path = packager.pack(path, output=output)
    print(f"Packaged domain pack at {archive_path}")
    return 0
