"""Official CMM OS CLI entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from time import perf_counter

from cmm.development import (
    AutonomousDevelopmentService,
    DevelopmentService,
    create_planning_provider,
)
from cmm.execution.development import AutonomousExecutionService
from cmm.validation.cli import handle_validation_cli, register_validation_cli
from kernel.end_to_end_runner import EndToEndRunner


def build_parser() -> argparse.ArgumentParser:
    """Build the official CMM OS CLI parser."""

    parser = argparse.ArgumentParser(prog="cmm")
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_validation_cli(subparsers)

    run_parser = subparsers.add_parser(
        "run", help="Run a natural-language goal against a Python project"
    )
    run_parser.add_argument("goal", help="Natural-language goal to execute")
    run_parser.add_argument("--project", dest="project", default=Path.cwd(), type=Path)

    develop_parser = subparsers.add_parser(
        "develop", help="Plan and apply a supervised semantic change"
    )
    develop_parser.add_argument(
        "goal", help="Natural-language or structured development goal"
    )
    develop_parser.add_argument(
        "--project", dest="project", default=Path.cwd(), type=Path
    )
    develop_parser.add_argument(
        "--yes", action="store_true", help="Apply without an interactive confirmation"
    )
    develop_parser.add_argument(
        "--provider",
        default="deterministic",
        help="Planning provider (deterministic or ollama[:model])",
    )
    develop_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show and validate the plan without applying it",
    )
    develop_parser.add_argument(
        "--autonomous", action="store_true", help="Iterate after recoverable failures"
    )
    develop_parser.add_argument(
        "--max-attempts", type=int, default=3, help="Maximum autonomous attempts"
    )
    develop_parser.add_argument(
        "--max-files",
        type=int,
        default=40,
        help="Maximum Python files included in planning context",
    )
    develop_parser.add_argument(
        "--isolate",
        action="store_true",
        help="Create an isolated Git review branch when autonomous",
    )
    develop_parser.add_argument(
        "--branch-name", help="Name for the isolated Git branch"
    )
    develop_parser.add_argument(
        "--keep-changes",
        action="store_true",
        default=True,
        help="Keep successful changes for review",
    )
    develop_parser.add_argument(
        "--restore", action="store_true", help="Restore the snapshot after execution"
    )
    develop_parser.add_argument(
        "--json", action="store_true", help="Print the structured result as JSON"
    )
    develop_parser.add_argument(
        "--validate",
        action="append",
        choices=("python_ast", "python_compile"),
        dest="validations",
        help="Controlled post-validation to run; may be repeated",
    )

    return parser


def _print_result(result, elapsed_seconds: float) -> None:
    print(f"Goal: {result.goal}")
    print(f"Operations: {len(result.execution_plan)}")
    print(f"Validation: {'valid' if result.validation_result.valid else 'invalid'}")

    if result.validation_result.errors:
        print("Validation errors:")
        for error in result.validation_result.errors:
            print(f"- {error}")

    executed_operations = (
        result.execution_result.executed_operations
        if result.execution_result is not None
        else []
    )
    print("Executed operations:")
    if executed_operations:
        for operation in executed_operations:
            print(f"- {operation.operation_type_value}")
    else:
        print("- none")

    print("Modified files:")
    if result.modified_files:
        for file_path in result.modified_files:
            print(f"- {file_path}")
    else:
        print("- none")

    print(f"Time: {elapsed_seconds:.3f}s")


def main(argv: list[str] | None = None) -> int:
    """Run the official CMM OS CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validation":
        return handle_validation_cli(args)

    if args.command == "develop":
        return _develop(args)

    project_path = Path(args.project)
    if not project_path.exists():
        print(f"Error: project path does not exist: {project_path}", file=sys.stderr)
        return 1

    runner = EndToEndRunner()
    start_time = perf_counter()
    result = runner.run(args.goal, project_path)
    elapsed_seconds = perf_counter() - start_time

    _print_result(result, elapsed_seconds)

    if not result.validation_result.valid:
        return 2

    if not result.success:
        return 1

    return 0


def _develop(args: argparse.Namespace) -> int:
    """Run the supervised development command."""

    try:
        provider = create_planning_provider(args.provider)
    except (RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    if args.autonomous:
        backend = AutonomousExecutionService(
            provider, output_fn=(lambda _message: None) if args.json else print
        )
        result = AutonomousDevelopmentService(provider, development=backend).develop(
            args.goal,
            Path(args.project),
            yes=args.yes,
            dry_run=args.dry_run,
            max_files=args.max_files,
            validations=tuple(args.validations) if args.validations else None,
            max_attempts=args.max_attempts,
            isolate=args.isolate,
            branch_name=args.branch_name,
            keep_changes=args.keep_changes,
            restore=args.restore,
        )
        if args.json:
            import json

            print(json.dumps(result.serialize(), ensure_ascii=True, sort_keys=True))
        else:
            _print_autonomous_result(result)
        return 0 if result.success else 1

    result = DevelopmentService(provider).develop(
        args.goal,
        Path(args.project),
        yes=args.yes,
        dry_run=args.dry_run,
        max_files=args.max_files,
        validations=args.validations,
    )
    _print_development_result(result)
    return 0 if result.success else 1


def _print_development_result(result) -> None:
    print(f"Result: {'success' if result.success else 'failure'}")
    print(f"Approved: {'yes' if result.approved else 'no'}")
    print(f"Dry run: {'yes' if result.dry_run else 'no'}")
    print(f"Rollback: {'yes' if result.rollback_applied else 'no'}")
    print("Modified files:")
    for path in result.modified_files:
        print(f"- {path}")
    if not result.modified_files:
        print("- none")
    print("Validations:")
    for validation in result.validations:
        print(
            f"- {validation.name}: {'ok' if validation.success else 'failed'} - {validation.message}"
        )
    if not result.validations:
        print("- none")
    if result.diff:
        print("Diff:")
        print(result.diff, end="" if result.diff.endswith("\n") else "\n")
    if result.warnings:
        print("Warnings:")
        for warning in result.warnings:
            print(f"- {warning}")
    if result.errors:
        print("Errors:")
        for error in result.errors:
            print(f"- {error}")
    print(f"Time: {result.duration_seconds:.3f}s")


def _print_autonomous_result(result) -> None:
    print(f"Result: {'success' if result.success else 'failure'}")
    print(f"Attempts: {result.attempt_count}/{result.max_attempts}")
    print(f"Stop reason: {result.stop_reason}")
    print(f"Rollback: {'yes' if result.rollback_applied else 'no'}")
    for attempt in result.attempts:
        print(
            f"Attempt {attempt.number}: {attempt.failure.kind.value} - {attempt.failure.message}"
        )
    if result.final_result is not None:
        _print_development_result(result.final_result)


if __name__ == "__main__":
    raise SystemExit(main())
