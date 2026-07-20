"""Official CMM OS CLI entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from time import perf_counter

from kernel.end_to_end_runner import EndToEndRunner


def build_parser() -> argparse.ArgumentParser:
    """Build the official CMM OS CLI parser."""

    parser = argparse.ArgumentParser(prog="cmm")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a natural-language goal against a Python project")
    run_parser.add_argument("goal", help="Natural-language goal to execute")
    run_parser.add_argument("--project", dest="project", default=Path.cwd(), type=Path)

    return parser


def _print_result(result, elapsed_seconds: float) -> None:
    print(f"Goal: {result.goal}")
    print(f"Operations: {len(result.execution_plan)}")
    print(f"Validation: {'valid' if result.validation_result.valid else 'invalid'}")

    if result.validation_result.errors:
        print("Validation errors:")
        for error in result.validation_result.errors:
            print(f"- {error}")

    executed_operations = result.execution_result.executed_operations if result.execution_result is not None else []
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

    if args.command != "run":
        parser.error("Unsupported command")

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


if __name__ == "__main__":
    raise SystemExit(main())
