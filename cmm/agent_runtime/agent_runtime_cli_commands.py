"""Phase 9.22 – Agent Runtime CLI Commands.

The argparse tree for `cmm agent ...` plus the per-resource translation
from parsed arguments to ``AgentRuntimeApiRequest``/``AgentRuntimeApiContext``
and back to a formatted ``AgentRuntimeCliResult``. This module is the only
place that knows the shape of each operation's payload; it never
duplicates domain logic - it only shapes a dict and calls
``AgentRuntimeApiService.execute``.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

from cmm.agent_runtime.agent_runtime_api_contracts import (
    AgentRuntimeApiRequest,
    AgentRuntimeApiResponse,
)
from cmm.agent_runtime.agent_runtime_api_enums import AgentRuntimeApiOperation
from cmm.agent_runtime.agent_runtime_api_service import AgentRuntimeApiService
from cmm.agent_runtime.agent_runtime_cli_context import AgentRuntimeCliContextBuilder
from cmm.agent_runtime.agent_runtime_cli_errors import (
    AgentRuntimeCliError,
    AgentRuntimeCliOutputError,
    AgentRuntimeCliParsingError,
    AgentRuntimeCliSecurityError,
    AgentRuntimeCliUsageError,
    AgentRuntimeCliValidationError,
)
from cmm.agent_runtime.agent_runtime_cli_formatters import (
    HumanFormatter,
    JsonFormatter,
    JsonLinesFormatter,
    QuietFormatter,
    to_serializable,
)
from cmm.agent_runtime.agent_runtime_cli_parsers import (
    parse_decimal,
    parse_identifier,
    parse_iso_datetime,
    parse_json_file,
    parse_json_inline,
    parse_metadata,
    parse_permissions,
)
from cmm.agent_runtime.agent_runtime_cli_result import (
    AgentRuntimeCliResult,
    map_api_error_to_exit_code,
)

CLI_VERSION = "9.22.0"

_OUTPUT_FORMATS = ("human", "json", "jsonl", "quiet")

_FORMATTERS: dict[str, Any] = {
    "human": HumanFormatter(),
    "json": JsonFormatter(),
    "jsonl": JsonLinesFormatter(),
    "quiet": QuietFormatter(),
}

MAX_BATCH_BYTES_DEFAULT = 10 * 1024 * 1024
MAX_BATCH_LINES_DEFAULT = 1000


def _build_global_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--output", choices=_OUTPUT_FORMATS, default=None)
    p.add_argument("--json", dest="json_flag", action="store_true", default=False)
    p.add_argument("--quiet", dest="quiet_flag", action="store_true", default=False)
    p.add_argument("--verbose", action="store_true", default=False)
    p.add_argument("--request-id", dest="request_id", default=None)
    p.add_argument("--actor-id", dest="actor_id", default=None)
    p.add_argument("--permission", dest="permissions", action="append", default=None)
    p.add_argument("--idempotency-key", dest="idempotency_key", default=None)
    p.add_argument("--config", dest="config", default=None)
    p.add_argument("--no-color", dest="no_color", action="store_true", default=False)
    return p


def build_root_parser() -> argparse.ArgumentParser:
    """Build the full `cmm agent` argparse tree."""
    g = _build_global_parser()
    root = argparse.ArgumentParser(
        prog="cmm agent",
        description="Agent Runtime CLI (Phase 9.22) - thin transport over AgentRuntimeApiService",
        parents=[g],
    )
    root.add_argument("--version", action="version", version=f"cmm agent {CLI_VERSION}")
    subparsers = root.add_subparsers(dest="resource")

    _add_goal_parser(subparsers, g)
    _add_run_parser(subparsers, g)
    _add_approval_parser(subparsers, g)
    _add_budget_parser(subparsers, g)
    _add_trace_parser(subparsers, g)
    _add_event_parser(subparsers, g)
    _add_dead_letter_parser(subparsers, g)
    subparsers.add_parser("health", parents=[g], help="Report runtime health")
    subparsers.add_parser("stats", parents=[g], help="Report runtime stats")
    _add_batch_parser(subparsers, g)

    return root


def _add_goal_parser(subparsers: Any, g: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser("goal", parents=[g], help="Manage agent goals")
    sub = p.add_subparsers(dest="command")

    create = sub.add_parser("create", parents=[g])
    create.add_argument("--title", required=True)
    create.add_argument("--objective", required=True)
    create.add_argument("--priority", default=None)
    create.add_argument("--creator-id", dest="creator_id", default=None)
    create.add_argument("--owner-id", dest="owner_id", default=None)
    create.add_argument("--metadata", action="append", default=None)

    get = sub.add_parser("get", parents=[g])
    get.add_argument("goal_id")

    listp = sub.add_parser("list", parents=[g])
    listp.add_argument("--status", default=None)
    listp.add_argument("--creator-id", dest="creator_id", default=None)
    listp.add_argument("--owner-id", dest="owner_id", default=None)
    listp.add_argument("--limit", default=None)
    listp.add_argument("--cursor", default=None)
    listp.add_argument("--sort-by", dest="sort_by", default=None)
    listp.add_argument("--sort-direction", dest="sort_direction", default=None)

    update = sub.add_parser("update", parents=[g])
    update.add_argument("goal_id")
    update.add_argument("--title", default=None)
    update.add_argument("--objective", default=None)
    update.add_argument("--metadata", action="append", default=None)

    prioritize = sub.add_parser("prioritize", parents=[g])
    prioritize.add_argument("goal_id")
    prioritize.add_argument("priority")

    for name in ("pause", "resume", "cancel"):
        transition = sub.add_parser(name, parents=[g])
        transition.add_argument("goal_id")
        transition.add_argument("--reason", default=None)


def _add_run_parser(subparsers: Any, g: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser("run", parents=[g], help="Manage agent runs")
    sub = p.add_subparsers(dest="command")

    start = sub.add_parser("start", parents=[g])
    start.add_argument("goal_id")
    start.add_argument("--agent-id", dest="agent_id", default=None)
    start.add_argument("--autonomy-level", dest="autonomy_level", default=None)
    start.add_argument("--metadata", action="append", default=None)

    get = sub.add_parser("get", parents=[g])
    get.add_argument("run_id")

    listp = sub.add_parser("list", parents=[g])
    listp.add_argument("--goal-id", dest="goal_id", default=None)
    listp.add_argument("--agent-id", dest="agent_id", default=None)
    listp.add_argument("--status", default=None)
    listp.add_argument("--limit", default=None)
    listp.add_argument("--cursor", default=None)

    for name in ("pause", "resume", "cancel"):
        transition = sub.add_parser(name, parents=[g])
        transition.add_argument("run_id")
        transition.add_argument("--reason", default=None)


def _add_approval_parser(subparsers: Any, g: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser("approval", parents=[g], help="Manage approvals")
    sub = p.add_subparsers(dest="command")

    listp = sub.add_parser("list", parents=[g])
    listp.add_argument("--status", default=None)
    listp.add_argument("--limit", default=None)

    get = sub.add_parser("get", parents=[g])
    get.add_argument("approval_id")

    approve = sub.add_parser("approve", parents=[g])
    approve.add_argument("approval_id")
    approve.add_argument("--comment", default=None)

    reject = sub.add_parser("reject", parents=[g])
    reject.add_argument("approval_id")
    reject.add_argument("--reason", default=None)


def _add_budget_parser(subparsers: Any, g: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser("budget", parents=[g], help="Manage action budgets")
    sub = p.add_subparsers(dest="command")

    get = sub.add_parser("get", parents=[g])
    get.add_argument("budget_id")

    reserve = sub.add_parser("reserve", parents=[g])
    reserve.add_argument("budget_id")
    reserve.add_argument("amount")
    # "iteration" mirrors BudgetApiAdapter's own default (used when a
    # payload omits "unit") so an un-annotated reserve always matches an
    # existing budget's unit on first use. Note "tokens" is a valid, honest
    # value a caller may pass explicitly - see the architecture doc's gaps
    # section for the pre-existing ValidationMiddleware substring quirk it
    # can trigger.
    reserve.add_argument("--unit", default="iteration")
    reserve.add_argument("--reservation-id", dest="reservation_id", default=None)
    reserve.add_argument("--reason", default=None)

    release = sub.add_parser("release", parents=[g])
    release.add_argument("budget_id")
    release.add_argument("reservation_id")
    release.add_argument("amount")
    release.add_argument("--reason", default=None)


def _add_trace_parser(subparsers: Any, g: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser("trace", parents=[g], help="Inspect agent traces")
    sub = p.add_subparsers(dest="command")

    get = sub.add_parser("get", parents=[g])
    get.add_argument("trace_id")

    listp = sub.add_parser("list", parents=[g])
    listp.add_argument("--run-id", dest="run_id", default=None)
    listp.add_argument("--goal-id", dest="goal_id", default=None)
    listp.add_argument("--status", default=None)
    listp.add_argument("--limit", default=None)
    listp.add_argument("--cursor", default=None)

    verify = sub.add_parser("verify", parents=[g])
    verify.add_argument("trace_id")

    export = sub.add_parser("export", parents=[g])
    export.add_argument("trace_id")
    export.add_argument(
        "--format",
        dest="export_format",
        choices=("json", "jsonl", "summary"),
        default="json",
    )
    export.add_argument("--output-file", dest="output_file", default=None)
    export.add_argument("--force", action="store_true", default=False)


def _add_event_parser(subparsers: Any, g: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser("event", parents=[g], help="Manage runtime events")
    sub = p.add_subparsers(dest="command")

    publish = sub.add_parser("publish", parents=[g])
    publish.add_argument("event_type")
    publish.add_argument("--payload", default=None)
    publish.add_argument("--payload-file", dest="payload_file", default=None)
    publish.add_argument("--agent-id", dest="agent_id", default=None)
    publish.add_argument("--run-id", dest="run_id", default=None)
    publish.add_argument("--goal-id", dest="goal_id", default=None)
    publish.add_argument("--workflow-id", dest="workflow_id", default=None)
    publish.add_argument("--correlation-id", dest="correlation_id", default=None)
    publish.add_argument("--causation-id", dest="causation_id", default=None)
    publish.add_argument("--sensitivity", default="internal")
    publish.add_argument("--metadata", action="append", default=None)

    listp = sub.add_parser("list", parents=[g])
    listp.add_argument("--event-type", dest="event_type", default=None)
    listp.add_argument("--run-id", dest="run_id", default=None)
    listp.add_argument("--goal-id", dest="goal_id", default=None)
    listp.add_argument("--correlation-id", dest="correlation_id", default=None)
    listp.add_argument("--from", dest="time_from", default=None)
    listp.add_argument("--to", dest="time_to", default=None)
    listp.add_argument("--limit", default=None)
    listp.add_argument("--cursor", default=None)

    replay = sub.add_parser("replay", parents=[g])
    replay.add_argument("--event-id", dest="event_id", default=None)
    replay.add_argument("--event-type", dest="event_type", default=None)
    replay.add_argument("--run-id", dest="run_id", default=None)
    replay.add_argument("--goal-id", dest="goal_id", default=None)
    replay.add_argument("--correlation-id", dest="correlation_id", default=None)
    replay.add_argument("--from", dest="time_from", default=None)
    replay.add_argument("--to", dest="time_to", default=None)
    replay.add_argument("--limit", default=None)
    replay.add_argument("--dry-run", dest="dry_run", action="store_true", default=False)


def _add_dead_letter_parser(subparsers: Any, g: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser(
        "dead-letter", parents=[g], help="Manage dead-lettered events"
    )
    sub = p.add_subparsers(dest="command")

    listp = sub.add_parser("list", parents=[g])
    listp.add_argument("--limit", default=None)
    listp.add_argument("--handler", default=None)

    replay = sub.add_parser("replay", parents=[g])
    replay.add_argument("dead_letter_id")
    replay.add_argument("--dry-run", dest="dry_run", action="store_true", default=False)


def _add_batch_parser(subparsers: Any, g: argparse.ArgumentParser) -> None:
    p = subparsers.add_parser(
        "batch", parents=[g], help="Execute many requests from JSONL"
    )
    p.add_argument("--file", dest="file", default=None)
    p.add_argument("--fail-fast", dest="fail_fast", action="store_true", default=False)
    p.add_argument(
        "--max-lines", dest="max_lines", type=int, default=MAX_BATCH_LINES_DEFAULT
    )
    p.add_argument(
        "--max-bytes", dest="max_bytes", type=int, default=MAX_BATCH_BYTES_DEFAULT
    )
    p.add_argument("--summary", dest="summary", action="store_true", default=False)


# ── Output format resolution ────────────────────────────────────────────


def resolve_output_format(args: argparse.Namespace, config: dict[str, Any]) -> str:
    if getattr(args, "json_flag", False) and getattr(args, "quiet_flag", False):
        raise AgentRuntimeCliUsageError("--json and --quiet are mutually exclusive")
    cli_output = args.output
    if getattr(args, "json_flag", False):
        if cli_output is not None and cli_output != "json":
            raise AgentRuntimeCliUsageError("--json conflicts with --output")
        cli_output = "json"
    if getattr(args, "quiet_flag", False):
        if cli_output is not None and cli_output != "quiet":
            raise AgentRuntimeCliUsageError("--quiet conflicts with --output")
        cli_output = "quiet"
    builder = AgentRuntimeCliContextBuilder()
    resolved = builder.resolve_output_format(cli_output=cli_output, config=config)
    return resolved or "human"


# ── Generic request/response plumbing ───────────────────────────────────


def _build_context(
    args: argparse.Namespace,
    operation: AgentRuntimeApiOperation,
    context_builder: AgentRuntimeCliContextBuilder,
    config: dict[str, Any],
) -> Any:
    permissions = parse_permissions(args.permissions) if args.permissions else None
    return context_builder.build(
        operation=operation.value,
        actor_id=args.actor_id,
        permissions=permissions,
        config=config,
    )


def _build_request(
    args: argparse.Namespace,
    operation: AgentRuntimeApiOperation,
    payload: dict[str, Any],
) -> AgentRuntimeApiRequest:
    kwargs: dict[str, Any] = {"operation": operation, "payload": payload}
    if args.request_id:
        kwargs["request_id"] = args.request_id
    if args.idempotency_key:
        kwargs["idempotency_key"] = args.idempotency_key
    return AgentRuntimeApiRequest(**kwargs)


def _draft_from_response(
    operation: AgentRuntimeApiOperation, response: AgentRuntimeApiResponse
) -> AgentRuntimeCliResult:
    if response.success:
        return AgentRuntimeCliResult(
            exit_code=0,
            stdout="",
            stderr="",
            request_id=response.request_id,
            operation=operation.value,
            status=response.status.value,
            data=to_serializable(response.data),
            error=None,
        )
    first = response.errors[0] if response.errors else None
    code = (
        getattr(first, "code", "INTERNAL_ERROR")
        if first is not None
        else "INTERNAL_ERROR"
    )
    code = code.value if hasattr(code, "value") else code
    message = (
        getattr(first, "message", "An error occurred")
        if first is not None
        else "An error occurred"
    )
    details = getattr(first, "details", None) if first is not None else None
    return AgentRuntimeCliResult(
        exit_code=map_api_error_to_exit_code(code),
        stdout="",
        stderr="",
        request_id=response.request_id,
        operation=operation.value,
        status=response.status.value,
        data=None,
        error={"code": code, "message": message, "details": to_serializable(details)},
    )


def _finalize(
    draft: AgentRuntimeCliResult, output_format: str
) -> AgentRuntimeCliResult:
    formatter = _FORMATTERS[output_format]
    text = formatter.format(draft)
    if draft.error is not None:
        return replace(draft, stdout="", stderr=text)
    return replace(draft, stdout=text, stderr="")


def format_usage_error(
    exc: AgentRuntimeCliError, output_format: str
) -> AgentRuntimeCliResult:
    draft = AgentRuntimeCliResult(
        exit_code=exc.exit_code,
        stdout="",
        stderr="",
        request_id=None,
        operation=None,
        status="error",
        data=None,
        error={"code": type(exc).__name__, "message": exc.message, "details": None},
    )
    return _finalize(draft, output_format)


# ── Payload builders per (resource, command) ────────────────────────────


def _priority(value: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise AgentRuntimeCliValidationError("priority must be an integer") from exc
    if parsed < 0:
        raise AgentRuntimeCliValidationError("priority must be non-negative")
    return parsed


def _optional_limit(value: str | None) -> int | None:
    if value is None:
        return None
    from cmm.agent_runtime.agent_runtime_cli_parsers import parse_limit

    return parse_limit(value)


def _query_payload(**fields: Any) -> dict[str, Any]:
    return {k: v for k, v in fields.items() if v is not None}


def _goal_operation_and_payload(
    args: argparse.Namespace,
) -> tuple[AgentRuntimeApiOperation, dict[str, Any]]:
    command = args.command
    if command == "create":
        payload: dict[str, Any] = {
            "title": args.title,
            "objective": args.objective,
            "context": parse_metadata(args.metadata),
        }
        if args.priority is not None:
            payload["priority"] = _priority(args.priority)
        if args.creator_id:
            payload["creator_id"] = parse_identifier(
                args.creator_id, field_name="creator-id"
            )
        if args.owner_id:
            payload["owner_id"] = parse_identifier(args.owner_id, field_name="owner-id")
        return AgentRuntimeApiOperation.GOAL_CREATE, payload
    if command == "get":
        return (
            AgentRuntimeApiOperation.GOAL_GET,
            {"goal_id": parse_identifier(args.goal_id, field_name="goal_id")},
        )
    if command == "list":
        query = _query_payload(
            status=args.status,
            creator_id=args.creator_id,
            owner_id=args.owner_id,
            limit=_optional_limit(args.limit),
            cursor=args.cursor,
            sort_by=args.sort_by,
            sort_direction=args.sort_direction,
        )
        return AgentRuntimeApiOperation.GOAL_LIST, {"query": query}
    if command == "update":
        goal_id = parse_identifier(args.goal_id, field_name="goal_id")
        metadata = parse_metadata(args.metadata) if args.metadata else None
        if args.title is None and args.objective is None and not metadata:
            raise AgentRuntimeCliUsageError(
                "goal update requires at least one of --title/--objective/--metadata"
            )
        payload = {"goal_id": goal_id}
        if args.title is not None:
            payload["title"] = args.title
        if args.objective is not None:
            payload["objective"] = args.objective
        if metadata:
            payload["context"] = metadata
        return AgentRuntimeApiOperation.GOAL_UPDATE, payload
    if command == "prioritize":
        return (
            AgentRuntimeApiOperation.GOAL_PRIORITIZE,
            {
                "goal_id": parse_identifier(args.goal_id, field_name="goal_id"),
                "new_priority": _priority(args.priority),
            },
        )
    if command in ("pause", "resume", "cancel"):
        op = {
            "pause": AgentRuntimeApiOperation.GOAL_PAUSE,
            "resume": AgentRuntimeApiOperation.GOAL_RESUME,
            "cancel": AgentRuntimeApiOperation.GOAL_CANCEL,
        }[command]
        payload = {"goal_id": parse_identifier(args.goal_id, field_name="goal_id")}
        if args.reason:
            payload["reason"] = args.reason
        return op, payload
    raise AgentRuntimeCliUsageError("goal requires a command")


def _run_operation_and_payload(
    args: argparse.Namespace,
) -> tuple[AgentRuntimeApiOperation, dict[str, Any]]:
    command = args.command
    if command == "start":
        payload: dict[str, Any] = {
            "goal_id": parse_identifier(args.goal_id, field_name="goal_id")
        }
        if args.autonomy_level is not None:
            payload["autonomy_level"] = _priority(args.autonomy_level)
        if args.agent_id:
            payload["agent_id"] = parse_identifier(args.agent_id, field_name="agent-id")
        if args.metadata:
            payload["metadata"] = parse_metadata(args.metadata)
        return AgentRuntimeApiOperation.RUN_START, payload
    if command == "get":
        return (
            AgentRuntimeApiOperation.RUN_GET,
            {"run_id": parse_identifier(args.run_id, field_name="run_id")},
        )
    if command == "list":
        query = _query_payload(
            goal_id=args.goal_id,
            agent_id=args.agent_id,
            status=args.status,
            limit=_optional_limit(args.limit),
            cursor=args.cursor,
        )
        return AgentRuntimeApiOperation.RUN_LIST, {"query": query}
    if command in ("pause", "resume", "cancel"):
        op = {
            "pause": AgentRuntimeApiOperation.RUN_PAUSE,
            "resume": AgentRuntimeApiOperation.RUN_RESUME,
            "cancel": AgentRuntimeApiOperation.RUN_CANCEL,
        }[command]
        payload = {"run_id": parse_identifier(args.run_id, field_name="run_id")}
        if args.reason:
            payload["reason"] = args.reason
        return op, payload
    raise AgentRuntimeCliUsageError("run requires a command")


def _approval_operation_and_payload(
    args: argparse.Namespace,
) -> tuple[AgentRuntimeApiOperation, dict[str, Any]]:
    command = args.command
    if command == "list":
        query = _query_payload(status=args.status, limit=_optional_limit(args.limit))
        return AgentRuntimeApiOperation.APPROVAL_LIST, {"query": query}
    if command == "get":
        return (
            AgentRuntimeApiOperation.APPROVAL_GET,
            {
                "approval_id": parse_identifier(
                    args.approval_id, field_name="approval_id"
                )
            },
        )
    if command == "approve":
        payload = {
            "approval_id": parse_identifier(args.approval_id, field_name="approval_id")
        }
        if args.comment:
            payload["comment"] = args.comment
        return AgentRuntimeApiOperation.APPROVAL_APPROVE, payload
    if command == "reject":
        payload = {
            "approval_id": parse_identifier(args.approval_id, field_name="approval_id")
        }
        if args.reason:
            payload["reason"] = args.reason
        return AgentRuntimeApiOperation.APPROVAL_REJECT, payload
    raise AgentRuntimeCliUsageError("approval requires a command")


def _budget_operation_and_payload(
    args: argparse.Namespace,
) -> tuple[AgentRuntimeApiOperation, dict[str, Any]]:
    command = args.command
    if command == "get":
        return (
            AgentRuntimeApiOperation.BUDGET_GET,
            {"budget_id": parse_identifier(args.budget_id, field_name="budget_id")},
        )
    if command == "reserve":
        amount = parse_decimal(args.amount, positive=True)
        payload: dict[str, Any] = {
            "budget_id": parse_identifier(args.budget_id, field_name="budget_id"),
            "amount": float(amount),
            "unit": args.unit,
        }
        if args.reservation_id:
            payload["reservation_id"] = parse_identifier(
                args.reservation_id, field_name="reservation-id"
            )
        if args.reason:
            payload["reason"] = args.reason
        return AgentRuntimeApiOperation.BUDGET_RESERVE, payload
    if command == "release":
        amount = parse_decimal(args.amount, positive=True)
        payload = {
            "budget_id": parse_identifier(args.budget_id, field_name="budget_id"),
            "reservation_id": parse_identifier(
                args.reservation_id, field_name="reservation_id"
            ),
            "amount": float(amount),
        }
        if args.reason:
            payload["reason"] = args.reason
        return AgentRuntimeApiOperation.BUDGET_RELEASE, payload
    raise AgentRuntimeCliUsageError("budget requires a command")


def _trace_operation_and_payload(
    args: argparse.Namespace,
) -> tuple[AgentRuntimeApiOperation, dict[str, Any]]:
    command = args.command
    if command == "get":
        return (
            AgentRuntimeApiOperation.TRACE_GET,
            {"trace_id": parse_identifier(args.trace_id, field_name="trace_id")},
        )
    if command == "list":
        query = _query_payload(
            run_id=args.run_id,
            goal_id=args.goal_id,
            status=args.status,
            limit=_optional_limit(args.limit),
            cursor=args.cursor,
        )
        return AgentRuntimeApiOperation.TRACE_LIST, {"query": query}
    if command == "verify":
        return (
            AgentRuntimeApiOperation.TRACE_VERIFY,
            {"trace_id": parse_identifier(args.trace_id, field_name="trace_id")},
        )
    if command == "export":
        return (
            AgentRuntimeApiOperation.TRACE_EXPORT,
            {
                "trace_id": parse_identifier(args.trace_id, field_name="trace_id"),
                "format": args.export_format.upper(),
            },
        )
    raise AgentRuntimeCliUsageError("trace requires a command")


_VALID_SENSITIVITIES = frozenset({"internal", "restricted", "public"})


def _event_operation_and_payload(
    args: argparse.Namespace,
) -> tuple[AgentRuntimeApiOperation, dict[str, Any]]:
    command = args.command
    if command == "publish":
        if args.payload is not None and args.payload_file is not None:
            raise AgentRuntimeCliUsageError(
                "--payload and --payload-file are mutually exclusive"
            )
        if args.payload is not None:
            body = parse_json_inline(args.payload)
        elif args.payload_file is not None:
            body = parse_json_file(args.payload_file)
        else:
            body = {}
        if args.metadata:
            body.update(parse_metadata(args.metadata))
        payload: dict[str, Any] = {
            "event_type": args.event_type,
            "sensitivity": args.sensitivity,
            **body,
        }
        for field_name, value in (
            ("agent_id", args.agent_id),
            ("run_id", args.run_id),
            ("goal_id", args.goal_id),
            ("workflow_id", args.workflow_id),
            ("correlation_id", args.correlation_id),
            ("causation_id", args.causation_id),
        ):
            if value:
                payload[field_name] = value
        return AgentRuntimeApiOperation.EVENT_PUBLISH, payload
    if command == "list":
        query = _query_payload(
            event_type=args.event_type,
            run_id=args.run_id,
            goal_id=args.goal_id,
            correlation_id=args.correlation_id,
            time_from=(parse_iso_datetime(args.time_from) if args.time_from else None),
            time_to=(parse_iso_datetime(args.time_to) if args.time_to else None),
            limit=_optional_limit(args.limit),
            cursor=args.cursor,
        )
        return AgentRuntimeApiOperation.EVENT_LIST, {"query": query}
    if command == "replay":
        selectors = (
            args.event_id,
            args.event_type,
            args.run_id,
            args.goal_id,
            args.correlation_id,
        )
        if not any(selectors) and args.limit is None:
            raise AgentRuntimeCliUsageError(
                "event replay requires at least one selector "
                "(--event-id/--event-type/--run-id/--goal-id/--correlation-id) or --limit"
            )
        payload = _query_payload(
            event_id=args.event_id,
            event_type=args.event_type,
            run_id=args.run_id,
            goal_id=args.goal_id,
            correlation_id=args.correlation_id,
            time_from=(parse_iso_datetime(args.time_from) if args.time_from else None),
            time_to=(parse_iso_datetime(args.time_to) if args.time_to else None),
            limit=_optional_limit(args.limit),
        )
        payload["replay_mode"] = "skip_delivered"
        return AgentRuntimeApiOperation.EVENT_REPLAY, payload
    raise AgentRuntimeCliUsageError("event requires a command")


def _dead_letter_operation_and_payload(
    args: argparse.Namespace,
) -> tuple[AgentRuntimeApiOperation, dict[str, Any]]:
    command = args.command
    if command == "list":
        query = _query_payload(limit=_optional_limit(args.limit), handler=args.handler)
        return AgentRuntimeApiOperation.DEAD_LETTER_LIST, {"query": query}
    if command == "replay":
        return (
            AgentRuntimeApiOperation.DEAD_LETTER_REPLAY,
            {
                "dead_letter_id": parse_identifier(
                    args.dead_letter_id, field_name="dead_letter_id"
                )
            },
        )
    raise AgentRuntimeCliUsageError("dead-letter requires a command")


_RESOURCE_BUILDERS = {
    "goal": _goal_operation_and_payload,
    "run": _run_operation_and_payload,
    "approval": _approval_operation_and_payload,
    "budget": _budget_operation_and_payload,
    "trace": _trace_operation_and_payload,
    "event": _event_operation_and_payload,
    "dead-letter": _dead_letter_operation_and_payload,
}


# ── Dry-run previews (event replay / dead-letter replay) ───────────────


def _event_replay_dry_run(
    args: argparse.Namespace,
    api_service: AgentRuntimeApiService,
    context_builder: AgentRuntimeCliContextBuilder,
    config: dict[str, Any],
) -> AgentRuntimeCliResult:
    """Preview a replay without ever calling the mutating operation.

    Uses the real, read-only event.list operation and filters client-side
    for display only - this never claims to know more than event.list
    actually returns.
    """
    context = _build_context(
        args, AgentRuntimeApiOperation.EVENT_LIST, context_builder, config
    )
    request = _build_request(args, AgentRuntimeApiOperation.EVENT_LIST, {"query": {}})
    response = api_service.execute(request, context)
    if not response.success:
        return _draft_from_response(AgentRuntimeApiOperation.EVENT_REPLAY, response)
    events = response.data.get("events", []) if isinstance(response.data, dict) else []
    if args.event_type:
        matching = [
            e for e in events if getattr(e, "event_type", None) == args.event_type
        ]
    else:
        matching = list(events)
    return AgentRuntimeCliResult(
        exit_code=0,
        stdout="",
        stderr="",
        request_id=response.request_id,
        operation=AgentRuntimeApiOperation.EVENT_REPLAY.value,
        status="success",
        data={"dry_run": True, "would_replay": len(matching)},
        error=None,
    )


def _dead_letter_replay_dry_run(
    args: argparse.Namespace,
    api_service: AgentRuntimeApiService,
    context_builder: AgentRuntimeCliContextBuilder,
    config: dict[str, Any],
) -> AgentRuntimeCliResult:
    context = _build_context(
        args, AgentRuntimeApiOperation.DEAD_LETTER_LIST, context_builder, config
    )
    request = _build_request(
        args, AgentRuntimeApiOperation.DEAD_LETTER_LIST, {"query": {}}
    )
    response = api_service.execute(request, context)
    if not response.success:
        return _draft_from_response(
            AgentRuntimeApiOperation.DEAD_LETTER_REPLAY, response
        )
    entries = (
        response.data.get("dead_letters", []) if isinstance(response.data, dict) else []
    )
    dead_letter_id = parse_identifier(args.dead_letter_id, field_name="dead_letter_id")
    found = any(e.get("dead_letter_id") == dead_letter_id for e in entries)
    return AgentRuntimeCliResult(
        exit_code=0,
        stdout="",
        stderr="",
        request_id=response.request_id,
        operation=AgentRuntimeApiOperation.DEAD_LETTER_REPLAY.value,
        status="success",
        data={"dry_run": True, "would_replay": found},
        error=None,
    )


# ── Trace export atomic write ────────────────────────────────────────────


def _atomic_write(path: Path, content: str) -> None:
    directory = path.parent
    fd, tmp_name = tempfile.mkstemp(dir=str(directory), prefix=".cmm-agent-tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.remove(tmp_name)
        raise


def _handle_trace_export_file(
    args: argparse.Namespace, response: AgentRuntimeApiResponse
) -> None:
    if not response.success:
        return
    trace_id = parse_identifier(args.trace_id, field_name="trace_id")
    if args.output_file:
        destination = Path(args.output_file).expanduser()
    else:
        destination = Path.cwd() / f"{trace_id}.{args.export_format}"
    if destination.exists() and not args.force:
        raise AgentRuntimeCliSecurityError(
            "output file already exists; use --force to overwrite"
        )
    export_data = getattr(response.data, "export_data", None)
    content = (
        export_data
        if isinstance(export_data, str)
        else json.dumps(to_serializable(export_data), sort_keys=True)
    )
    try:
        _atomic_write(destination, content)
    except OSError as exc:
        raise AgentRuntimeCliOutputError("failed to write export file") from exc


# ── Non-batch dispatch ───────────────────────────────────────────────────


def dispatch_resource(
    args: argparse.Namespace,
    api_service: AgentRuntimeApiService,
    context_builder: AgentRuntimeCliContextBuilder,
    config: dict[str, Any],
    output_format: str,
) -> AgentRuntimeCliResult:
    resource = args.resource

    if resource == "health":
        operation = AgentRuntimeApiOperation.RUNTIME_HEALTH
        context = _build_context(args, operation, context_builder, config)
        request = _build_request(args, operation, {})
        response = api_service.execute(request, context)
        return _finalize(_draft_from_response(operation, response), output_format)

    if resource == "stats":
        operation = AgentRuntimeApiOperation.RUNTIME_STATS
        context = _build_context(args, operation, context_builder, config)
        request = _build_request(args, operation, {})
        response = api_service.execute(request, context)
        return _finalize(_draft_from_response(operation, response), output_format)

    if resource == "event" and args.command == "replay" and args.dry_run:
        return _finalize(
            _event_replay_dry_run(args, api_service, context_builder, config),
            output_format,
        )
    if resource == "dead-letter" and args.command == "replay" and args.dry_run:
        return _finalize(
            _dead_letter_replay_dry_run(args, api_service, context_builder, config),
            output_format,
        )

    builder = _RESOURCE_BUILDERS.get(resource)
    if builder is None:
        raise AgentRuntimeCliUsageError(f"unknown resource: {resource}")
    if getattr(args, "command", None) is None:
        raise AgentRuntimeCliUsageError(f"{resource} requires a command")

    operation, payload = builder(args)
    context = _build_context(args, operation, context_builder, config)
    request = _build_request(args, operation, payload)
    response = api_service.execute(request, context)

    if resource == "trace" and args.command == "export":
        _handle_trace_export_file(args, response)

    return _finalize(_draft_from_response(operation, response), output_format)


# ── Batch ─────────────────────────────────────────────────────────────────


def _read_batch_input(args: argparse.Namespace) -> str:
    max_bytes = args.max_bytes
    if args.file:
        path = Path(args.file).expanduser()
        try:
            resolved = path.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise AgentRuntimeCliParsingError("batch file does not exist") from exc
        if not resolved.is_file():
            raise AgentRuntimeCliParsingError("batch file is not a regular file")
        try:
            size = resolved.stat().st_size
        except OSError as exc:
            raise AgentRuntimeCliParsingError("batch file could not be read") from exc
        if size > max_bytes:
            raise AgentRuntimeCliUsageError("batch input exceeds --max-bytes")
        try:
            return resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise AgentRuntimeCliParsingError("batch file could not be read") from exc
    raw = sys.stdin.buffer.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise AgentRuntimeCliUsageError("batch input exceeds --max-bytes")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AgentRuntimeCliParsingError("batch input is not valid UTF-8") from exc


def _process_batch_line(
    line_number: int,
    line: str,
    args: argparse.Namespace,
    api_service: AgentRuntimeApiService,
    context_builder: AgentRuntimeCliContextBuilder,
    config: dict[str, Any],
) -> dict[str, Any]:
    try:
        record = json.loads(line)
    except json.JSONDecodeError:
        return {
            "line": line_number,
            "status": "error",
            "error": {"code": "PARSING_ERROR", "message": "invalid JSON on this line"},
        }
    if not isinstance(record, dict) or "operation" not in record:
        return {
            "line": line_number,
            "status": "error",
            "error": {
                "code": "PARSING_ERROR",
                "message": "line must be a JSON object with an 'operation' field",
            },
        }
    try:
        operation = AgentRuntimeApiOperation.from_string(str(record["operation"]))
    except ValueError:
        return {
            "line": line_number,
            "status": "error",
            "error": {
                "code": "UNSUPPORTED_OPERATION",
                "message": "unknown operation",
            },
        }
    payload = record.get("payload") or {}
    if not isinstance(payload, dict):
        return {
            "line": line_number,
            "status": "error",
            "error": {
                "code": "PARSING_ERROR",
                "message": "'payload' must be an object",
            },
        }
    try:
        permissions = (
            parse_permissions(record.get("permissions"))
            if record.get("permissions")
            else (parse_permissions(args.permissions) if args.permissions else None)
        )
        context = context_builder.build(
            operation=operation.value,
            actor_id=record.get("actor_id") or args.actor_id,
            permissions=permissions,
            config=config,
        )
    except AgentRuntimeCliError as exc:
        return {
            "line": line_number,
            "status": "error",
            "error": {"code": type(exc).__name__, "message": exc.message},
        }
    request_kwargs: dict[str, Any] = {"operation": operation, "payload": payload}
    if record.get("request_id"):
        request_kwargs["request_id"] = record["request_id"]
    if record.get("idempotency_key"):
        request_kwargs["idempotency_key"] = record["idempotency_key"]
    request = AgentRuntimeApiRequest(**request_kwargs)
    response = api_service.execute(request, context)
    result = {
        "line": line_number,
        "operation": operation.value,
        "request_id": response.request_id,
        "status": response.status.value,
    }
    if response.success:
        result["data"] = to_serializable(response.data)
    else:
        first = response.errors[0] if response.errors else None
        code = (
            getattr(first, "code", "INTERNAL_ERROR")
            if first is not None
            else "INTERNAL_ERROR"
        )
        code = code.value if hasattr(code, "value") else code
        message = (
            getattr(first, "message", "An error occurred")
            if first is not None
            else "An error occurred"
        )
        result["error"] = {"code": code, "message": message}
    return result


def dispatch_batch(
    args: argparse.Namespace,
    api_service: AgentRuntimeApiService,
    context_builder: AgentRuntimeCliContextBuilder,
    config: dict[str, Any],
) -> AgentRuntimeCliResult:
    text = _read_batch_input(args)
    raw_lines = text.splitlines()
    if len(raw_lines) > args.max_lines:
        raise AgentRuntimeCliUsageError("batch input exceeds --max-lines")

    output_lines: list[str] = []
    succeeded = 0
    failed = 0
    for idx, raw_line in enumerate(raw_lines, start=1):
        if not raw_line.strip():
            continue
        record_result = _process_batch_line(
            idx, raw_line, args, api_service, context_builder, config
        )
        is_error = record_result.get("status") == "error"
        if is_error:
            failed += 1
        else:
            succeeded += 1
        output_lines.append(
            json.dumps(record_result, sort_keys=True, ensure_ascii=True)
        )
        if is_error and args.fail_fast:
            break

    if args.summary:
        output_lines.append(
            json.dumps(
                {
                    "summary": {
                        "total": succeeded + failed,
                        "succeeded": succeeded,
                        "failed": failed,
                    }
                },
                sort_keys=True,
            )
        )

    stdout = "\n".join(output_lines)
    if stdout:
        stdout += "\n"
    return AgentRuntimeCliResult(
        exit_code=0 if failed == 0 else 1,
        stdout=stdout,
        stderr="",
        request_id=None,
        operation="batch",
        status="success" if failed == 0 else "partial",
        data={"total": succeeded + failed, "succeeded": succeeded, "failed": failed},
        error=None,
    )


__all__ = [
    "CLI_VERSION",
    "build_root_parser",
    "dispatch_batch",
    "dispatch_resource",
    "format_usage_error",
    "resolve_output_format",
]
