"""Phase 9.22 – Agent Runtime CLI Runner.

The only place that touches argument parsing side effects (argparse's
``SystemExit`` on ``--help``/``--version``/usage errors) and the only
place ``main()`` may return an exit code to the real process. ``run()``
never calls ``sys.exit`` and never touches the real terminal - it
redirects stdout/stderr to in-memory buffers only for the duration of
argument parsing, which is the one step argparse insists on printing
through directly.
"""

from __future__ import annotations

import contextlib
import io
import sys
from collections.abc import Sequence

from cmm.agent_runtime.agent_runtime_api_service import AgentRuntimeApiService
from cmm.agent_runtime.agent_runtime_cli_commands import (
    build_root_parser,
    dispatch_batch,
    dispatch_resource,
    format_usage_error,
    resolve_output_format,
)
from cmm.agent_runtime.agent_runtime_cli_context import AgentRuntimeCliContextBuilder
from cmm.agent_runtime.agent_runtime_cli_errors import (
    AgentRuntimeCliError,
    AgentRuntimeCliUsageError,
)
from cmm.agent_runtime.agent_runtime_cli_result import (
    EXIT_INTERNAL_ERROR,
    EXIT_INTERRUPTED,
    EXIT_USAGE_ERROR,
    VALID_EXIT_CODES,
    AgentRuntimeCliResult,
)


class AgentRuntimeCliRunner:
    """Runs `cmm agent` argv against an injected ``AgentRuntimeApiService``."""

    def __init__(self, api_service: AgentRuntimeApiService | None = None) -> None:
        self._api_service = api_service
        self._context_builder = AgentRuntimeCliContextBuilder()

    def _service(self) -> AgentRuntimeApiService:
        if self._api_service is None:
            self._api_service = AgentRuntimeApiService()
        return self._api_service

    def run(self, argv: Sequence[str]) -> AgentRuntimeCliResult:
        try:
            return self._run(argv)
        except KeyboardInterrupt:
            return AgentRuntimeCliResult(
                exit_code=EXIT_INTERRUPTED,
                stdout="",
                stderr="",
                request_id=None,
                operation=None,
                status="interrupted",
                data=None,
                error=None,
            )
        except Exception:  # noqa: BLE001 - outer transport boundary: never crash
            return AgentRuntimeCliResult(
                exit_code=EXIT_INTERNAL_ERROR,
                stdout="",
                stderr="An internal error occurred",
                request_id=None,
                operation=None,
                status="error",
                data=None,
                error={
                    "code": "INTERNAL_ERROR",
                    "message": "An internal error occurred",
                    "details": None,
                },
            )

    def _run(self, argv: Sequence[str]) -> AgentRuntimeCliResult:
        parser = build_root_parser()
        stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
        try:
            with (
                contextlib.redirect_stdout(stdout_buf),
                contextlib.redirect_stderr(stderr_buf),
            ):
                args = parser.parse_args(list(argv))
        except SystemExit as exc:
            code = exc.code
            if not isinstance(code, int):
                code = 0 if code is None else 1
            if code not in VALID_EXIT_CODES:
                code = EXIT_USAGE_ERROR
            return AgentRuntimeCliResult(
                exit_code=code,
                stdout=stdout_buf.getvalue(),
                stderr=stderr_buf.getvalue(),
                request_id=None,
                operation=None,
                status="success" if code == 0 else "error",
                data=None,
                error=None,
            )

        try:
            provisional_format = resolve_output_format(args, config={})
        except AgentRuntimeCliError as exc:
            return format_usage_error(exc, "human")

        try:
            config = self._context_builder.load_config(args.config)
            output_format = resolve_output_format(args, config)
        except AgentRuntimeCliError as exc:
            return format_usage_error(exc, provisional_format)

        try:
            if args.resource is None:
                raise AgentRuntimeCliUsageError(
                    "a resource is required: goal, run, approval, budget, "
                    "trace, event, dead-letter, health, stats, batch"
                )
            if args.resource == "batch":
                return dispatch_batch(
                    args, self._service(), self._context_builder, config
                )
            return dispatch_resource(
                args, self._service(), self._context_builder, config, output_format
            )
        except AgentRuntimeCliError as exc:
            return format_usage_error(exc, output_format)


def run(
    argv: Sequence[str], api_service: AgentRuntimeApiService | None = None
) -> AgentRuntimeCliResult:
    """Run the Agent Runtime CLI against ``argv`` and return the result."""
    return AgentRuntimeCliRunner(api_service).run(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Process entry point: writes to real stdout/stderr, returns an exit code."""
    result = run(list(argv) if argv is not None else sys.argv[1:])
    if result.stdout:
        sys.stdout.write(
            result.stdout if result.stdout.endswith("\n") else result.stdout + "\n"
        )
    if result.stderr:
        sys.stderr.write(
            result.stderr if result.stderr.endswith("\n") else result.stderr + "\n"
        )
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["AgentRuntimeCliRunner", "main", "run"]
