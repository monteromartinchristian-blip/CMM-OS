"""CLI interface implementation for CMM OS Validation (Phase 7.12)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .interfaces.application import ValidationApplicationService
from .interfaces.contracts import (
    StartValidationRequest,
    ValidationArtifactResponse,
    ValidationGateResponse,
    ValidationResultResponse,
)
from .interfaces.errors import ValidationApplicationError
from .interfaces.exit_codes import ValidationExitCode
from .interfaces.presenters import (
    format_human_artifacts,
    format_human_gate,
    format_human_inspect,
    format_human_run,
    format_json_response,
)


def register_validation_cli(subparsers: argparse._SubParsersAction) -> None:
    """Register the official `validation` parser and subcommands into cmm CLI."""
    val_parser = subparsers.add_parser(
        "validation",
        help="CMM OS validation infrastructure interface",
    )
    val_subparsers = val_parser.add_subparsers(
        dest="validation_subcommand", required=True
    )

    # 1. cmm validation run
    run_p = val_subparsers.add_parser("run", help="Run validation pipeline")
    run_p.add_argument("--policy", help="Validation policy name")
    run_p.add_argument(
        "--step",
        dest="steps",
        action="append",
        help="Validation step to execute (may be repeated)",
    )
    run_p.add_argument(
        "--files",
        nargs="+",
        help="Specific files to validate",
    )
    run_p.add_argument(
        "--git-changes",
        action="store_true",
        help="Use Git status / diff changed files",
    )
    run_p.add_argument("--actor", help="Actor triggering validation")
    run_p.add_argument(
        "--output",
        choices=("human", "json"),
        default="human",
        help="Output format (human or json)",
    )
    run_p.add_argument("--verbose", action="store_true", help="Enable verbose output")
    run_p.add_argument("--quiet", action="store_true", help="Enable quiet output")
    run_p.add_argument(
        "--no-persist",
        action="store_true",
        help="Do not persist validation execution result",
    )
    run_p.add_argument(
        "--project",
        dest="project",
        default=Path.cwd(),
        type=Path,
        help="Project root directory",
    )

    # 2. cmm validation inspect <validation-id>
    inspect_p = val_subparsers.add_parser(
        "inspect", help="Inspect a stored validation record"
    )
    inspect_p.add_argument("validation_id", help="Validation execution ID")
    inspect_p.add_argument(
        "--output",
        choices=("human", "json"),
        default="human",
        help="Output format (human or json)",
    )
    inspect_p.add_argument(
        "--verbose", action="store_true", help="Enable verbose output"
    )
    inspect_p.add_argument("--quiet", action="store_true", help="Enable quiet output")
    inspect_p.add_argument(
        "--project",
        dest="project",
        default=Path.cwd(),
        type=Path,
        help="Project root directory",
    )

    # 3. cmm validation artifacts <validation-id>
    artifacts_p = val_subparsers.add_parser(
        "artifacts", help="List or inspect validation artifacts"
    )
    artifacts_p.add_argument("validation_id", help="Validation execution ID")
    artifacts_p.add_argument(
        "--artifact",
        dest="artifact_id",
        help="Specific artifact ID to inspect",
    )
    artifacts_p.add_argument(
        "--output",
        choices=("human", "json"),
        default="human",
        help="Output format (human or json)",
    )
    artifacts_p.add_argument(
        "--verbose", action="store_true", help="Enable verbose output"
    )
    artifacts_p.add_argument("--quiet", action="store_true", help="Enable quiet output")
    artifacts_p.add_argument(
        "--project",
        dest="project",
        default=Path.cwd(),
        type=Path,
        help="Project root directory",
    )

    # 4. cmm validation gate <validation-id>
    gate_p = val_subparsers.add_parser(
        "gate", help="Evaluate commit gate for a validation execution"
    )
    gate_p.add_argument("validation_id", help="Validation execution ID")
    gate_p.add_argument(
        "--output",
        choices=("human", "json"),
        default="human",
        help="Output format (human or json)",
    )
    gate_p.add_argument("--verbose", action="store_true", help="Enable verbose output")
    gate_p.add_argument("--quiet", action="store_true", help="Enable quiet output")
    gate_p.add_argument(
        "--project",
        dest="project",
        default=Path.cwd(),
        type=Path,
        help="Project root directory",
    )


def handle_validation_cli(args: argparse.Namespace) -> int:
    """Handle dispatched `validation` subcommand."""
    is_json = getattr(args, "output", "human") == "json"
    command_name = f"validation.{getattr(args, 'validation_subcommand', 'unknown')}"

    # Check mutual exclusion for quiet & verbose
    if getattr(args, "quiet", False) and getattr(args, "verbose", False):
        err_msg = "--quiet and --verbose are mutually exclusive."
        if is_json:
            out = format_json_response(
                command=command_name,
                success=False,
                exit_code=ValidationExitCode.INVALID_USAGE,
                validation_id=getattr(args, "validation_id", None),
                result=None,
                error={
                    "code": "validation_invalid_request",
                    "message": err_msg,
                    "details": {},
                },
            )
            print(out)
        else:
            print(f"Error: {err_msg}", file=sys.stderr)
        return ValidationExitCode.INVALID_USAGE

    project_root = getattr(args, "project", Path.cwd())
    service = ValidationApplicationService(project_root=project_root)

    try:
        subcommand = getattr(args, "validation_subcommand", None)
        if subcommand == "run":
            return _handle_run(service, args)
        elif subcommand == "inspect":
            return _handle_inspect(service, args)
        elif subcommand == "artifacts":
            return _handle_artifacts(service, args)
        elif subcommand == "gate":
            return _handle_gate(service, args)
        else:
            err_msg = f"Unknown validation subcommand: {subcommand}"
            if is_json:
                print(
                    format_json_response(
                        command="validation",
                        success=False,
                        exit_code=ValidationExitCode.INVALID_USAGE,
                        validation_id=None,
                        result=None,
                        error={
                            "code": "validation_invalid_request",
                            "message": err_msg,
                            "details": {},
                        },
                    )
                )
            else:
                print(f"Error: {err_msg}", file=sys.stderr)
            return ValidationExitCode.INVALID_USAGE

    except ValidationApplicationError as exc:
        if is_json:
            print(
                format_json_response(
                    command=command_name,
                    success=False,
                    exit_code=exc.exit_code,
                    validation_id=getattr(args, "validation_id", None),
                    result=None,
                    error=exc.serialize(),
                )
            )
        else:
            print(f"Error: [{exc.code}] {exc.message}", file=sys.stderr)
        return exc.exit_code
    except Exception as exc:  # noqa: BLE001
        err_dict = {
            "code": "validation_internal_error",
            "message": str(exc),
            "details": {},
        }
        if is_json:
            print(
                format_json_response(
                    command=command_name,
                    success=False,
                    exit_code=ValidationExitCode.INTERNAL_ERROR,
                    validation_id=getattr(args, "validation_id", None),
                    result=None,
                    error=err_dict,
                )
            )
        else:
            print(f"Internal error: {exc}", file=sys.stderr)
        return ValidationExitCode.INTERNAL_ERROR


def _handle_run(service: ValidationApplicationService, args: argparse.Namespace) -> int:
    is_json = args.output == "json"
    files = tuple(Path(f) for f in args.files) if args.files else None
    steps = tuple(args.steps) if args.steps else None

    req = StartValidationRequest(
        project_root=service.project_root,
        policy_name=args.policy,
        steps=steps,
        files=files,
        use_git_changes=args.git_changes,
        actor=args.actor,
        persist=not args.no_persist,
    )

    resp: ValidationResultResponse = service.start_validation(req)

    # Determine exit code from status
    if resp.status == "passed":
        exit_code = ValidationExitCode.SUCCESS
    elif resp.status in ("failed", "warning"):
        exit_code = (
            ValidationExitCode.VALIDATION_FAILED
            if resp.blocking_findings or resp.status == "failed"
            else ValidationExitCode.SUCCESS
        )
    elif resp.status == "cancelled":
        exit_code = ValidationExitCode.CANCELLED
    elif resp.status == "timed_out":
        exit_code = ValidationExitCode.TIMEOUT
    else:
        exit_code = ValidationExitCode.INTERNAL_ERROR

    if is_json:
        out = format_json_response(
            command="validation.run",
            success=(exit_code == ValidationExitCode.SUCCESS),
            exit_code=exit_code,
            validation_id=resp.validation_id,
            result=resp.serialize(),
            error=None,
        )
        print(out)
    else:
        out = format_human_run(resp, verbose=args.verbose, quiet=args.quiet)
        print(out)

    return exit_code


def _handle_inspect(
    service: ValidationApplicationService, args: argparse.Namespace
) -> int:
    is_json = args.output == "json"
    resp: ValidationResultResponse = service.get_result(args.validation_id)

    exit_code = ValidationExitCode.SUCCESS

    if is_json:
        out = format_json_response(
            command="validation.inspect",
            success=True,
            exit_code=exit_code,
            validation_id=resp.validation_id,
            result=resp.serialize(),
            error=None,
        )
        print(out)
    else:
        out = format_human_inspect(
            resp.serialize(), verbose=args.verbose, quiet=args.quiet
        )
        print(out)

    return exit_code


def _handle_artifacts(
    service: ValidationApplicationService, args: argparse.Namespace
) -> int:
    is_json = args.output == "json"
    selected: ValidationArtifactResponse | None = None

    if args.artifact_id:
        selected = service.get_artifact(args.validation_id, args.artifact_id)
        artifacts = [selected]
    else:
        artifacts = service.list_artifacts(args.validation_id)

    exit_code = ValidationExitCode.SUCCESS

    if is_json:
        res_data = (
            selected.serialize() if selected else [a.serialize() for a in artifacts]
        )
        out = format_json_response(
            command="validation.artifacts",
            success=True,
            exit_code=exit_code,
            validation_id=args.validation_id,
            result={"artifacts": res_data},
            error=None,
        )
        print(out)
    else:
        out = format_human_artifacts(
            artifacts, selected_artifact=selected, quiet=args.quiet
        )
        print(out)

    return exit_code


def _handle_gate(
    service: ValidationApplicationService, args: argparse.Namespace
) -> int:
    is_json = args.output == "json"
    resp: ValidationGateResponse = service.evaluate_gate(args.validation_id)

    exit_code = (
        ValidationExitCode.SUCCESS
        if resp.allowed
        else ValidationExitCode.VALIDATION_FAILED
    )

    if is_json:
        out = format_json_response(
            command="validation.gate",
            success=resp.allowed,
            exit_code=exit_code,
            validation_id=args.validation_id,
            result=resp.serialize(),
            error=None,
        )
        print(out)
    else:
        out = format_human_gate(resp, quiet=args.quiet)
        print(out)

    return exit_code


__all__ = [
    "handle_validation_cli",
    "register_validation_cli",
]
