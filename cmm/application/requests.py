"""Phase 11.3 — the application-to-orchestration request adapter.

``RequestApplicationService`` is the central public request path of Phase 11.3.
It adapts one public :class:`~cmm.application.contracts.ApplicationMessage` into
the canonical Phase 11.2 ``OrchestrationRequest`` with origin channel ``API``,
calls ``Orchestrator.orchestrate`` and projects the canonical
``OrchestrationResult`` back into a safe public ``ApplicationResponse``.

The adapter is faithful in both directions and owns no authority:

- it sets no ``bot_id``, no ``intent_hint`` and no requested capability, so it
  can never fabricate a routing decision the canonical pipeline did not make;
- it copies only the safe projection of the message into the canonical input
  (``message_id``, ``content``, ``content_type`` and the frozen safe metadata)
  with ``context={}``, so no raw context, permission evidence or client object
  reaches the orchestrator;
- it projects only the approved safe categorical fields of the result, so no
  internal decision object, raw policy trace or hidden reasoning reaches a
  public response;
- it reports no downstream execution, because Phase 11.2 deliberately stops at
  route selection and Phase 11.3 introduces no executor.

Session preconditions are evaluated *before* orchestration: the canonical
session must exist and, when the caller supplied one, the expected revision must
match.  A result whose request identity does not match the request fails closed
rather than being reported under the caller's identity, and an orchestration
failure is mapped conservatively — known policy/approval/cancellation categories
become their public code, everything else becomes ``INTERNAL_FAILURE`` — always
with an application-owned message rather than canonical error text.

See ``docs/reference/phase-11-application-backend.md``.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    MAX_IDENTIFIER_LENGTH,
    ApplicationChannel,
    ApplicationError,
    ApplicationErrorCode,
    ApplicationMessage,
    ApplicationResponse,
    ApplicationStatus,
)
from cmm.application.errors import (
    ApplicationCancelledError,
    ApplicationConflictError,
    ApplicationServiceError,
    ApprovalRequiredApplicationError,
    InternalApplicationError,
    InvalidApplicationRequestError,
    PolicyDeniedApplicationError,
)
from cmm.application.sessions import SessionApplicationService
from cmm.orchestration.contracts import (
    OrchestrationChannel,
    OrchestrationRequest,
    OrchestrationResult,
    OrchestrationStatus,
)
from cmm.orchestration.orchestrator import Orchestrator

__all__ = ["RequestApplicationService"]

#: Canonical orchestration status to public application status.  The mapping is
#: exhaustive over the frozen Phase 11.2 terminal statuses and adds nothing.
_STATUS_MAP: Mapping[OrchestrationStatus, ApplicationStatus] = {
    OrchestrationStatus.ROUTED: ApplicationStatus.ROUTED,
    OrchestrationStatus.NEEDS_CLARIFICATION: ApplicationStatus.NEEDS_CLARIFICATION,
    OrchestrationStatus.BLOCKED: ApplicationStatus.BLOCKED,
    OrchestrationStatus.ESCALATED: ApplicationStatus.ESCALATED,
    OrchestrationStatus.CANCELLED: ApplicationStatus.CANCELLED,
    OrchestrationStatus.FAILED: ApplicationStatus.FAILED,
}

#: Conservative canonical failure-category mapping.  Phase 11.2 currently emits
#: the ``policy`` and ``persistence`` categories; the approval and cancellation
#: categories are mapped forward rather than being guessed at runtime.  Any
#: other category — including an unknown one — is an internal failure.
_FAILURE_CATEGORY_CODES: Mapping[str, ApplicationErrorCode] = {
    "policy": ApplicationErrorCode.POLICY_DENIED,
    "approval": ApplicationErrorCode.APPROVAL_REQUIRED,
    "cancellation": ApplicationErrorCode.CANCELLED,
    "persistence": ApplicationErrorCode.CONFLICT,
}

#: The typed failure that owns each mapped public code, so the public message is
#: always the application-owned constant and never canonical error text.
_FAILURE_EXCEPTIONS: Mapping[ApplicationErrorCode, type[ApplicationServiceError]] = {
    ApplicationErrorCode.POLICY_DENIED: PolicyDeniedApplicationError,
    ApplicationErrorCode.APPROVAL_REQUIRED: ApprovalRequiredApplicationError,
    ApplicationErrorCode.CANCELLED: ApplicationCancelledError,
    ApplicationErrorCode.CONFLICT: ApplicationConflictError,
    ApplicationErrorCode.INTERNAL_FAILURE: InternalApplicationError,
}

#: The one public application channel to canonical orchestration channel map.
#: Channel selection policy lives here and nowhere else: a transport declares
#: its origin, the adapter translates it, and the canonical pipeline sees the
#: origin it has always understood.
_APPLICATION_TO_ORCHESTRATION_CHANNEL: Mapping[
    ApplicationChannel, OrchestrationChannel
] = MappingProxyType(
    {
        ApplicationChannel.API: OrchestrationChannel.API,
        ApplicationChannel.CLI: OrchestrationChannel.CLI,
        ApplicationChannel.CONVERSATION: OrchestrationChannel.CONVERSATION,
    }
)


def _request_identifier(value: object) -> str:
    """Return the normalized public request identity or fail closed."""

    if not isinstance(value, str):
        raise InvalidApplicationRequestError(
            details={"reason_code": "INVALID_REQUEST_ID"}
        )
    normalized = value.strip()
    if not normalized or len(normalized) > MAX_IDENTIFIER_LENGTH:
        raise InvalidApplicationRequestError(
            details={"reason_code": "INVALID_REQUEST_ID"}
        )
    return normalized


def _public_error(code: ApplicationErrorCode) -> ApplicationError:
    """Return the safe public error owned by *code*."""

    return _FAILURE_EXCEPTIONS[code]().to_public_error()


def _map_canonical_failure(result: OrchestrationResult) -> ApplicationError | None:
    """Return the safe public error for a canonical failure, if any."""

    failure = result.error
    if failure is None:
        return None
    category = failure.category.strip().lower()
    return _public_error(
        _FAILURE_CATEGORY_CODES.get(category, ApplicationErrorCode.INTERNAL_FAILURE)
    )


def _project_result(result: OrchestrationResult, session_id: str) -> dict[str, Any]:
    """Return the safe public projection of one canonical orchestration result."""

    return {
        "session_id": session_id,
        "request_id": result.request_id,
        "status": result.status.value,
        "intent": result.intent.value,
        "primary_domain": result.primary_domain,
        "supporting_domains": list(result.supporting_domains),
        "profile_id": result.profile_id,
        "route": result.route.value,
        "agent_id": result.agent_id,
        "workflow_id": result.workflow_id,
        "approval_refs": list(result.approval_refs),
        "decision_id": result.decision_id,
        "trace_refs": list(result.trace_refs),
        "reason_codes": list(result.reason_codes),
    }


class RequestApplicationService:
    """Adapts public application messages to the canonical orchestrator."""

    def __init__(
        self,
        *,
        sessions: SessionApplicationService,
        orchestrator: Orchestrator,
    ) -> None:
        if not isinstance(sessions, SessionApplicationService):
            raise TypeError("sessions must be a SessionApplicationService")
        if not isinstance(orchestrator, Orchestrator):
            raise TypeError("orchestrator must be the canonical Orchestrator")
        self._sessions = sessions
        self._orchestrator = orchestrator

    def submit_message(
        self,
        *,
        request_id: str,
        message: ApplicationMessage,
        channel: ApplicationChannel = ApplicationChannel.API,
    ) -> ApplicationResponse:
        """Submit one public message and return a safe public response.

        ``channel`` is the transport-neutral origin the caller's public request
        declared.  It defaults to ``API`` so a caller that declares nothing
        keeps the closed Phase 11.3 behavior.

        Raises an ``ApplicationServiceError`` when the request can not be
        accepted or the application layer must fail closed.
        """

        if not isinstance(message, ApplicationMessage):
            raise TypeError("message must be an ApplicationMessage")
        if not isinstance(channel, ApplicationChannel):
            raise TypeError("channel must be an ApplicationChannel")
        normalized_request_id = _request_identifier(request_id)

        # Session preconditions are evaluated before the canonical pipeline, so
        # an absent or stale session can never reach orchestration.
        self._sessions.require_revision(
            message.session_id, message.expected_session_revision
        )

        result = self._orchestrate(normalized_request_id, message, channel)
        return self._to_application_response(normalized_request_id, message, result)

    # ── Canonical delegation ─────────────────────────────────────────────────

    def _orchestrate(
        self,
        request_id: str,
        message: ApplicationMessage,
        channel: ApplicationChannel,
    ) -> OrchestrationResult:
        # ``to_dict`` yields the thawed, JSON-native public projection, so the
        # canonical request never receives a frozen public container and never
        # shares mutable state with the caller.
        public_message = message.to_dict()
        orchestration_request = OrchestrationRequest(
            request_id=request_id,
            user_id=message.actor_id,
            channel=_APPLICATION_TO_ORCHESTRATION_CHANNEL[channel],
            session_id=message.session_id,
            input={
                "message_id": public_message["message_id"],
                "content": public_message["content"],
                "content_type": public_message["content_type"],
                "metadata": public_message["metadata"],
            },
            context={},
            requested_capabilities=(),
        )

        try:
            result = self._orchestrator.orchestrate(orchestration_request)
        except Exception as exc:
            raise InternalApplicationError() from exc

        if not isinstance(result, OrchestrationResult):
            raise InternalApplicationError()
        if result.request_id != request_id:
            # A result for another request is never reported as this request's.
            raise InternalApplicationError()
        return result

    # ── Public projection ────────────────────────────────────────────────────

    def _to_application_response(
        self,
        request_id: str,
        message: ApplicationMessage,
        result: OrchestrationResult,
    ) -> ApplicationResponse:
        status = _STATUS_MAP[result.status]
        error = _map_canonical_failure(result)

        if status is ApplicationStatus.FAILED:
            # A failed orchestration produced no decision to project, and the
            # public contract requires an error for this status.
            return ApplicationResponse(
                request_id=request_id,
                api_version=APPLICATION_API_VERSION,
                status=status,
                data=None,
                error=error
                if error is not None
                else _public_error(ApplicationErrorCode.INTERNAL_FAILURE),
                metadata={},
            )

        if status is ApplicationStatus.BLOCKED and error is None:
            error = _public_error(ApplicationErrorCode.POLICY_DENIED)

        return ApplicationResponse(
            request_id=request_id,
            api_version=APPLICATION_API_VERSION,
            status=status,
            data=_project_result(result, message.session_id),
            error=error,
            metadata={},
        )
