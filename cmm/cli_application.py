"""Phase 11.4 — the thin CLI-to-application adapter.

This module owns the only path from the public CLI to the canonical application
boundary.  ``CliApplicationAdapter`` wraps one ``ApplicationGateway`` and does
three things, and nothing else:

- it builds **versioned public application requests** with the CLI channel and
  explicit correlation identities, so the canonical pipeline knows the request
  came from the command line without the CLI naming any lower owner;
- it projects the **safe public application response** into the frozen
  :class:`~cmm.cli_contracts.CliResult` envelope: status, safe data, and — on a
  failure — the application's own public error code, message and details;
- it validates the little that is genuinely CLI-owned input (non-empty text, an
  explicit actor) and refuses to invent the rest.

The adapter holds exactly one collaborator, the gateway.  It does not import,
store or reach the orchestrator, a registry, a store, a workflow engine or a
provider: the CLI is a sibling adapter of HTTP over the same application
boundary, and it owns no platform truth of its own.

This module is also the CLI's one startup seam.  :func:`build_cli_application`
reuses the canonical local application composition of
``cmm.application.local_runtime`` and adapts its gateway, so a standalone CLI
process reaches the platform through exactly the same graph as an embedded
client -- and reaches it here, in the one presentation module the application
boundary sanctions as a sibling consumer of the backend.

See ``docs/reference/phase-11-cli.md``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4, uuid5

from cmm.application import (
    APPLICATION_API_VERSION,
    ApplicationChannel,
    ApplicationCommand,
    ApplicationErrorCode,
    ApplicationGateway,
    ApplicationOperation,
    ApplicationQuery,
    ApplicationResponse,
    ApplicationStatus,
)
from cmm.cli_contracts import CliError, CliResult

__all__ = ["CliApplicationAdapter", "build_cli_application"]

#: The presentation-owned message used when the application boundary returns an
#: object the CLI can not project.  It carries no internal content.
UNPROJECTABLE_RESPONSE_MESSAGE = "CLI request failed closed without a usable response"

#: Presentation fallback message for a successful session creation that carried
#: no session identity.  The CLI reports the defect instead of inventing one.
MISSING_SESSION_MESSAGE = "CLI request failed closed without a usable session"

#: Namespace for deriving a canonical message identity from an idempotency key.
#: A keyed command must describe *one* canonical message across retries, so its
#: message identity is derived from the key instead of being drawn at random;
#: the frozen command fingerprint then matches and a retry replays rather than
#: conflicting.
_MESSAGE_ID_NAMESPACE = UUID("6f9a3f4e-2b2c-5d8a-9c1e-8f7d6c5b4a39")

#: The public content type of CLI message text.
_CONTENT_TYPE = "text/plain"


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    if not value.strip():
        raise ValueError(f"{field} must be non-empty")
    return value


def _new_request_id() -> str:
    return str(uuid4())


def _message_id(idempotency_key: str | None) -> str:
    if idempotency_key is None:
        return str(uuid4())
    return str(uuid5(_MESSAGE_ID_NAMESPACE, idempotency_key))


def _failure_result(
    command: str,
    code: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> CliResult:
    return CliResult(
        command=command,
        ok=False,
        status="failed",
        error=CliError(code=code, message=message),
        metadata={} if metadata is None else metadata,
    )


def build_cli_application() -> CliApplicationAdapter:
    """Compose the canonical local application and adapt it for the CLI.

    This is the CLI's only startup path: it reuses the canonical composition of
    ``cmm.application.local_runtime`` and wraps the gateway it publishes, so a
    standalone process runs against the same official graph an embedded client
    composes -- no second graph, no service locator and no authority of its own.

    Composition happens when an operational command needs the platform, not when
    the CLI starts: help, version, a parse error and a reserved capability are
    answered without a runtime existing at all.
    """

    from cmm.application.local_runtime import build_local_application_runtime

    return CliApplicationAdapter(build_local_application_runtime().gateway)


class CliApplicationAdapter:
    """Adapts public CLI commands to the one canonical application gateway."""

    def __init__(self, gateway: ApplicationGateway) -> None:
        if not isinstance(gateway, ApplicationGateway):
            raise TypeError(
                "gateway must be the official ApplicationGateway, "
                f"not {type(gateway).__name__}"
            )
        self._gateway = gateway

    # ── Public commands ──────────────────────────────────────────────────────

    def status(self) -> CliResult:
        """Return the safe operational summary of the canonical application.

        The summary is a projection of two canonical reads — health and declared
        capabilities — performed through the one gateway.  One public command
        runs under one correlation identity, so both reads share the request id
        the result reports.  The CLI computes no readiness of its own.
        """

        request_id = _new_request_id()
        health = self._gateway.handle(
            ApplicationQuery(
                request_id=request_id,
                api_version=APPLICATION_API_VERSION,
                operation=ApplicationOperation.HEALTH_GET,
                channel=ApplicationChannel.CLI,
            )
        )
        if health.error is not None:
            return self._to_cli_result("status", health)

        capabilities = self._gateway.handle(
            ApplicationQuery(
                request_id=request_id,
                api_version=APPLICATION_API_VERSION,
                operation=ApplicationOperation.CAPABILITIES_LIST,
                channel=ApplicationChannel.CLI,
            )
        )
        if capabilities.error is not None:
            return self._to_cli_result("status", capabilities)

        if not isinstance(health.data, Mapping) or not isinstance(
            capabilities.data, Mapping
        ):
            return _failure_result(
                "status",
                ApplicationErrorCode.INTERNAL_FAILURE.value,
                UNPROJECTABLE_RESPONSE_MESSAGE,
            )

        data = self._status_projection(health.data, capabilities.data)
        return CliResult(
            command="status",
            ok=True,
            status=ApplicationStatus.SUCCESS.value,
            data=data,
            metadata={
                "request_id": request_id,
                "api_version": APPLICATION_API_VERSION,
                "quiet_value": data["platform_state"],
            },
        )

    def create_session(
        self,
        *,
        session_id: str | None = None,
        actor_id: str | None = None,
    ) -> ApplicationResponse:
        """Create one canonical session through the gateway."""

        payload: dict[str, Any] = {}
        if session_id is not None:
            payload["session_id"] = _require_text(session_id, field="session_id")

        return self._gateway.handle(
            ApplicationCommand(
                request_id=_new_request_id(),
                api_version=APPLICATION_API_VERSION,
                operation=ApplicationOperation.SESSION_CREATE,
                actor_id=actor_id,
                channel=ApplicationChannel.CLI,
                payload=payload,
            )
        )

    def ask(
        self,
        *,
        text: str,
        actor_id: str,
        session_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> CliResult:
        """Submit one one-shot request, creating one session when none is given."""

        checked_text = _require_text(text, field="text")
        checked_actor = _require_text(actor_id, field="actor_id")

        if session_id is None:
            created = self.create_session(actor_id=checked_actor)
            if (
                created.error is not None
                or created.status is not ApplicationStatus.SUCCESS
            ):
                return self._to_cli_result("ask", created)
            resolved_session = self._session_id_of(created, command="ask")
            if isinstance(resolved_session, CliResult):
                return resolved_session
        else:
            resolved_session = _require_text(session_id, field="session_id")

        return self._submit(
            command="ask",
            text=checked_text,
            actor_id=checked_actor,
            session_id=resolved_session,
            idempotency_key=idempotency_key,
        )

    def submit_message(
        self,
        *,
        text: str,
        actor_id: str,
        session_id: str,
        idempotency_key: str | None = None,
    ) -> CliResult:
        """Submit one message into an existing canonical session."""

        return self._submit(
            command="chat",
            text=_require_text(text, field="text"),
            actor_id=_require_text(actor_id, field="actor_id"),
            session_id=_require_text(session_id, field="session_id"),
            idempotency_key=idempotency_key,
        )

    # ── Application request construction ─────────────────────────────────────

    def _submit(
        self,
        *,
        command: str,
        text: str,
        actor_id: str,
        session_id: str,
        idempotency_key: str | None,
    ) -> CliResult:
        response = self._gateway.handle(
            ApplicationCommand(
                request_id=_new_request_id(),
                api_version=APPLICATION_API_VERSION,
                operation=ApplicationOperation.MESSAGE_SUBMIT,
                actor_id=actor_id,
                session_id=session_id,
                channel=ApplicationChannel.CLI,
                idempotency_key=idempotency_key,
                payload={
                    "message_id": _message_id(idempotency_key),
                    "content": text,
                    "content_type": _CONTENT_TYPE,
                    "metadata": {},
                },
            )
        )
        return self._to_cli_result(command, response)

    # ── Projection ───────────────────────────────────────────────────────────

    @staticmethod
    def _status_projection(
        health: Mapping[str, Any], capabilities: Mapping[str, Any]
    ) -> dict[str, Any]:
        declared = capabilities.get("capabilities", [])
        entries = [
            dict(entry)
            for entry in declared
            if isinstance(entry, Mapping)
            and isinstance(entry.get("capability_id"), str)
        ]
        return {
            "platform_state": str(health.get("status", "")),
            "platform_ready": bool(health.get("platform_ready", False)),
            "application_api_version": str(health.get("api_version", "")),
            "services": sorted(str(service) for service in health.get("services", [])),
            "capabilities": sorted(
                entries, key=lambda entry: str(entry["capability_id"])
            ),
        }

    @staticmethod
    def _session_id_of(
        response: ApplicationResponse, *, command: str
    ) -> str | CliResult:
        data = response.data
        session_id = data.get("session_id") if isinstance(data, Mapping) else None
        if isinstance(session_id, str) and session_id.strip():
            return session_id
        return _failure_result(
            command,
            ApplicationErrorCode.INTERNAL_FAILURE.value,
            MISSING_SESSION_MESSAGE,
            {"request_id": response.request_id, "api_version": response.api_version},
        )

    def _to_cli_result(self, command: str, response: object) -> CliResult:
        if not isinstance(response, ApplicationResponse):
            return _failure_result(
                command,
                ApplicationErrorCode.INTERNAL_FAILURE.value,
                UNPROJECTABLE_RESPONSE_MESSAGE,
            )

        metadata = {
            "request_id": response.request_id,
            "api_version": response.api_version,
        }
        data = response.data if isinstance(response.data, Mapping) else {}

        if response.error is None:
            return CliResult(
                command=command,
                ok=True,
                status=response.status.value,
                data=data,
                metadata=metadata,
            )

        return CliResult(
            command=command,
            ok=False,
            status=response.status.value,
            data=data,
            error=CliError(
                code=response.error.code.value,
                message=response.error.message,
                details=response.error.details,
            ),
            metadata=metadata,
        )
