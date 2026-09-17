"""Phase 11.5 — the canonical conversational service over the application gateway.

``ConversationService`` is the one conversational coordinator of Phase 11.5.  It
turns one public conversational turn into exactly one canonical
``ApplicationCommand``, enters the one ``ApplicationGateway`` of the application
backend, projects the safe ``ApplicationResponse`` back into the public
conversational surface and commits the transcript through the canonical shared
session store.  It owns no authority of its own:

- session authority stays with the canonical ``SessionStore``: the service never
  opens, wraps or replaces a store and speaks only to the supplied
  ``SharedSessionConversationAdapter``;
- message submission authority stays with ``ApplicationGateway``: the service
  never resolves a domain, selects an agent, routes a model, executes a workflow
  or mutates an application session;
- the service holds no second store, no registry, no cancellation engine, no
  active-request registry, no retry loop, no clock and no hidden reasoning.
  Every identity and timestamp is caller-supplied, so a call is deterministic.

Command construction is uniform and frozen.  Every command the service builds is
an ``ApplicationCommand`` with ``api_version="v1"``, the caller's ``request_id``,
``actor_id=CONVERSATION_ACTOR_ID``, the canonical session (``None`` for
cancellation, which is request-scoped), a public payload,
``channel=ApplicationChannel.CONVERSATION`` and the caller's expected session
revision.  The service never sets an ``idempotency_key``: Phase 11.5 defines no
conversation-level idempotency owner, so no key is ever fabricated.

The application payload of a message command carries public conversational text
only: the application message identity, the content and the public
``text/plain`` content type.  Conversation ``metadata``, ``references``,
``attachments`` and the opaque ``bot_id`` stay in conversation state and never
enter the application payload; ``bot_id`` grants nothing and selects nothing.

Failure semantics: the caller's expected session revision is verified against
the canonical session *before* the gateway is entered, so a stale caller never
traverses the canonical pipeline and never writes.  A commit that loses the
canonical optimistic-concurrency race propagates as the safe
``ConversationSessionConflictError`` and is never silently retried with a new
revision.  Structured blocked/failed application responses are preserved through
the safe projection and persisted like any other outcome; no exception text ever
enters conversation state.

Operations:

- ``submit`` validates the user turn against the canonical session, verifies
  the caller's expected revision and enters the gateway exactly once;
- ``edit`` is non-destructive and append-only: the original user message is
  preserved, the service itself binds the effective replacement's lineage
  (``supersedes_message_id == original.id``) and the canonical path is re-run
  exactly once;
- ``regenerate`` is canonical re-execution: the target assistant response must
  exist, its nearest preceding user turn supplies the resubmitted content
  without being mutated or re-appended, the caller-supplied
  ``application_message_id`` is the new application message identity, and the
  new assistant response is lineage-bound through ``regenerates_message_id``;
  no hidden reasoning is reused or persisted;
- ``cancel`` delegates to the canonical gateway — at the current baseline the
  canonical answer is ``CAPABILITY_UNAVAILABLE`` — and introduces no
  active-request registry.

``regenerate`` receives the canonical ``session_id`` the target response
belongs to (the transcript is per canonical session, and the target, the
preceding user turn and the commit are all resolved from that session alone).

See ``docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md``
(sections 9, 11, 12, 14, 18, 22, 23 and 25) and the committed Phase 11.5 plan.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    ApplicationChannel,
    ApplicationCommand,
    ApplicationOperation,
    ApplicationResponse,
)
from cmm.application.gateway import ApplicationGateway
from cmm.conversation.capabilities import ConversationCapabilityResolver
from cmm.conversation.contracts import (
    AssistantResponse,
    ConversationLineage,
    ConversationMessage,
    ConversationRole,
)
from cmm.conversation.errors import (
    ConversationBoundaryError,
    ConversationSessionConflictError,
    ConversationSessionNotFoundError,
)
from cmm.conversation.projection import ConversationResponseProjector
from cmm.conversation.state import (
    ConversationState,
    SharedSessionConversationAdapter,
)

if TYPE_CHECKING:
    from cmm.domains.interface_integration_contracts import ConversationalDomainView
    from cmm.runtime.sessions import SharedSessionState

__all__ = ["CONVERSATION_ACTOR_ID", "ConversationService"]

#: The one descriptive, public-safe actor identity of every application command
#: the service builds.  ``actor_id`` is descriptive public input in Phase 11.3
#: (no authorization semantics; authentication is explicitly out of scope) and
#: the gateway's message path fails closed without one, so the conversational
#: boundary freezes one module-level constant rather than inventing per-message
#: identities.
CONVERSATION_ACTOR_ID = "conversation"

#: The one public content type of a conversational application message.
_CONTENT_TYPE = "text/plain"


def _message_command(
    *,
    request_id: str,
    session_id: str,
    message_id: str,
    content: str,
    expected_session_revision: int,
) -> ApplicationCommand:
    """Build the one canonical ``MESSAGE_SUBMIT`` command of one user turn."""

    return ApplicationCommand(
        api_version=APPLICATION_API_VERSION,
        request_id=request_id,
        operation=ApplicationOperation.MESSAGE_SUBMIT,
        actor_id=CONVERSATION_ACTOR_ID,
        session_id=session_id,
        payload={
            "message_id": message_id,
            "content": content,
            "content_type": _CONTENT_TYPE,
        },
        channel=ApplicationChannel.CONVERSATION,
        expected_session_revision=expected_session_revision,
    )


def _preceding_user_message(
    messages: tuple[ConversationMessage, ...], target: ConversationMessage
) -> ConversationMessage:
    """Return the nearest preceding ``USER`` message of *target*, read-only.

    The scan starts at the target and walks backwards through the transcript;
    the located user turn is returned unchanged — never mutated, re-appended or
    attributed a new identity — and a transcript without a preceding user turn
    fails closed with the conversational ``INVALID_REQUEST`` boundary error.
    """

    preceding: list[ConversationMessage] = []
    found = False
    for message in messages:
        if message.id == target.id:
            found = True
            break
        preceding.append(message)
    if not found:
        raise ConversationBoundaryError()
    for message in reversed(preceding):
        if message.role is ConversationRole.USER:
            return message
    raise ConversationBoundaryError()


class ConversationService:
    """Coordinates canonical multi-turn interaction over the application boundary."""

    def __init__(
        self,
        *,
        gateway: ApplicationGateway,
        state: SharedSessionConversationAdapter,
        capabilities: ConversationCapabilityResolver,
        projector: ConversationResponseProjector,
    ) -> None:
        if not isinstance(gateway, ApplicationGateway):
            raise TypeError(
                "gateway must be the canonical ApplicationGateway, "
                f"not {type(gateway).__name__}"
            )
        if not isinstance(state, SharedSessionConversationAdapter):
            raise TypeError(
                "state must be the canonical SharedSessionConversationAdapter, "
                f"not {type(state).__name__}"
            )
        if not isinstance(capabilities, ConversationCapabilityResolver):
            raise TypeError(
                "capabilities must be the canonical ConversationCapabilityResolver, "
                f"not {type(capabilities).__name__}"
            )
        if not isinstance(projector, ConversationResponseProjector):
            raise TypeError(
                "projector must be the canonical ConversationResponseProjector, "
                f"not {type(projector).__name__}"
            )
        self._gateway = gateway
        self._state = state
        self._capabilities = capabilities
        self._projector = projector

    # ── submit ───────────────────────────────────────────────────────────────

    def submit(
        self,
        message: ConversationMessage,
        *,
        request_id: str,
        expected_session_revision: int,
        requested_capabilities: tuple[str, ...] = (),
        domain_view: ConversationalDomainView | None = None,
        assistant_message_id: str,
        assistant_created_at: str,
    ) -> AssistantResponse:
        """Submit one user turn and return the projected assistant response.

        The exact order is frozen: load the canonical shared session (absent →
        ``ConversationSessionNotFoundError``), verify the caller's expected
        revision against it (mismatch → ``ConversationSessionConflictError``,
        no gateway call and no write), validate the user message (a
        non-message, a non-``USER`` role or a foreign session binding →
        ``INVALID_REQUEST``), build the one canonical command, enter the
        gateway, project the safe response with the caller's authorized
        ``domain_view`` and resolved capability state, then append the user
        message and the assistant message and commit them in one canonical
        commit carrying the same expected previous revision.
        """

        if not isinstance(message, ConversationMessage):
            raise ConversationBoundaryError()
        shared = self._require_shared_session(message.session_id)
        self._require_expected_revision(shared, expected_session_revision)
        if (
            message.role is not ConversationRole.USER
            or message.session_id != shared.session_id
        ):
            raise ConversationBoundaryError()

        command = _message_command(
            request_id=request_id,
            session_id=shared.session_id,
            message_id=message.id,
            content=message.content,
            expected_session_revision=expected_session_revision,
        )
        application_response = self._gateway.handle(command)
        response = self._project(
            request_message=message,
            assistant_message_id=assistant_message_id,
            assistant_created_at=assistant_created_at,
            application_response=application_response,
            domain_view=domain_view,
            requested_capabilities=requested_capabilities,
            lineage=ConversationLineage(),
        )
        self._commit(
            session_id=shared.session_id,
            appended=(message, response.message),
            expected_session_revision=expected_session_revision,
        )
        return response

    # ── edit ─────────────────────────────────────────────────────────────────

    def edit(
        self,
        *,
        original_message_id: str,
        replacement: ConversationMessage,
        request_id: str,
        expected_session_revision: int,
        requested_capabilities: tuple[str, ...] = (),
        domain_view: ConversationalDomainView | None = None,
        assistant_message_id: str,
        assistant_created_at: str,
    ) -> AssistantResponse:
        """Edit one user message through a lineage-bound replacement.

        Editing is non-destructive and append-only.  The original message must
        exist and be a ``USER`` message; the original is preserved
        byte-identical.  The service enforces lineage itself: the effective
        replacement is the caller's message with
        ``lineage.supersedes_message_id == original.id`` (a caller-supplied
        lineage is replaced by the enforced one).  A replacement identity equal
        to the original's and a replacement bound to a foreign session fail
        closed with ``INVALID_REQUEST``.

        The canonical gateway is traversed again exactly once with the
        replacement as the application message identity, the new assistant
        response receives the caller-supplied identity, and both the effective
        replacement and the assistant response are committed in one canonical
        commit carrying the same expected previous revision.
        """

        if not isinstance(replacement, ConversationMessage):
            raise ConversationBoundaryError()
        shared = self._require_shared_session(replacement.session_id)
        self._require_expected_revision(shared, expected_session_revision)

        original = self._require_stored_message(shared.session_id, original_message_id)
        if original.role is not ConversationRole.USER:
            raise ConversationBoundaryError()
        if replacement.id == original.id:
            raise ConversationBoundaryError()
        if replacement.session_id != shared.session_id:
            raise ConversationBoundaryError()
        effective = replace(
            replacement,
            lineage=ConversationLineage(supersedes_message_id=original.id),
        )

        command = _message_command(
            request_id=request_id,
            session_id=shared.session_id,
            message_id=effective.id,
            content=effective.content,
            expected_session_revision=expected_session_revision,
        )
        application_response = self._gateway.handle(command)
        response = self._project(
            request_message=effective,
            assistant_message_id=assistant_message_id,
            assistant_created_at=assistant_created_at,
            application_response=application_response,
            domain_view=domain_view,
            requested_capabilities=requested_capabilities,
            lineage=ConversationLineage(),
        )
        self._commit(
            session_id=shared.session_id,
            appended=(effective, response.message),
            expected_session_revision=expected_session_revision,
        )
        return response

    # ── regenerate ───────────────────────────────────────────────────────────

    def regenerate(
        self,
        *,
        session_id: str,
        response_message_id: str,
        request_id: str,
        application_message_id: str,
        expected_session_revision: int,
        domain_view: ConversationalDomainView | None = None,
        assistant_message_id: str,
        assistant_created_at: str,
    ) -> AssistantResponse:
        """Regenerate one assistant response through the canonical pipeline.

        Regeneration is canonical re-execution, not recollection: the target
        assistant response must exist and be an ``ASSISTANT`` message, and the
        nearest preceding ``USER`` message supplies the resubmitted public
        content without being mutated, re-appended or attributed a new
        identity.  The caller-supplied ``application_message_id`` is the new
        application message identity — no new conversation user message is
        appended.

        The canonical gateway is traversed again exactly once, no hidden
        reasoning is reused or persisted, the original response is preserved
        and the new assistant message carries
        ``lineage.regenerates_message_id == response_message_id``.
        """

        shared = self._require_shared_session(session_id)
        self._require_expected_revision(shared, expected_session_revision)

        state = self._require_conversation(shared.session_id)
        target = state.message(response_message_id)
        if target.role is not ConversationRole.ASSISTANT:
            raise ConversationBoundaryError()
        request_message = _preceding_user_message(state.messages, target)

        command = _message_command(
            request_id=request_id,
            session_id=shared.session_id,
            message_id=application_message_id,
            content=request_message.content,
            expected_session_revision=expected_session_revision,
        )
        application_response = self._gateway.handle(command)
        response = self._project(
            request_message=request_message,
            assistant_message_id=assistant_message_id,
            assistant_created_at=assistant_created_at,
            application_response=application_response,
            domain_view=domain_view,
            requested_capabilities=(),
            lineage=ConversationLineage(regenerates_message_id=target.id),
        )
        self._commit(
            session_id=shared.session_id,
            appended=(response.message,),
            expected_session_revision=expected_session_revision,
        )
        return response

    # ── cancel ───────────────────────────────────────────────────────────────

    def cancel(self, *, request_id: str, target_request_id: str) -> ApplicationResponse:
        """Delegate one cancellation request to the canonical gateway.

        The service owns no cancellation state and no active-request registry:
        the command is request-scoped (``session_id=None``), carries the target
        request identity in its payload and is handed to the one
        ``ApplicationGateway``, whose canonical response is returned unchanged.
        At the current baseline that response reports
        ``CAPABILITY_UNAVAILABLE`` because no canonical cancellable-request
        owner exists; the service never fabricates a cancellation or a fake
        success.
        """

        command = ApplicationCommand(
            api_version=APPLICATION_API_VERSION,
            request_id=request_id,
            operation=ApplicationOperation.REQUEST_CANCEL,
            actor_id=CONVERSATION_ACTOR_ID,
            payload={"request_id": target_request_id},
            channel=ApplicationChannel.CONVERSATION,
        )
        return self._gateway.handle(command)

    # ── Canonical session preconditions ──────────────────────────────────────

    def _require_shared_session(self, session_id: str) -> SharedSessionState:
        """Return the canonical shared session, or fail closed as not-found."""

        shared = self._state.load_shared_session(session_id)
        if shared is None:
            raise ConversationSessionNotFoundError()
        return shared

    def _require_conversation(self, session_id: str) -> ConversationState:
        """Return the conversation of one canonical session, or fail closed.

        A canonical session without a conversation extension carries no
        conversational message to resolve, so it fails closed with the
        conversational ``INVALID_REQUEST`` boundary error.
        """

        state = self._state.load_conversation(session_id)
        if state is None:
            raise ConversationBoundaryError()
        return state

    def _require_stored_message(
        self, session_id: str, message_id: str
    ) -> ConversationMessage:
        """Return one stored message of the conversation, or fail closed.

        A canonical session without a conversation, or a message ID that is not
        part of the conversation state, fails closed with the conversational
        ``INVALID_REQUEST`` boundary error.
        """

        return self._require_conversation(session_id).message(message_id)

    @staticmethod
    def _require_expected_revision(
        shared: SharedSessionState, expected_session_revision: int
    ) -> None:
        """Verify the caller's optimistic revision before anything is attempted.

        A mismatch fails closed as the safe conversation conflict *before* the
        gateway is entered and before any write, so a stale caller never
        traverses the canonical pipeline.
        """

        if shared.revision != expected_session_revision:
            raise ConversationSessionConflictError()

    # ── Projection and commit ────────────────────────────────────────────────

    def _project(
        self,
        *,
        request_message: ConversationMessage,
        assistant_message_id: str,
        assistant_created_at: str,
        application_response: ApplicationResponse,
        domain_view: ConversationalDomainView | None,
        requested_capabilities: tuple[str, ...],
        lineage: ConversationLineage,
    ) -> AssistantResponse:
        """Project one application response through the safe public projection."""

        return self._projector.project(
            request_message=request_message,
            assistant_message_id=assistant_message_id,
            created_at=assistant_created_at,
            application_response=application_response,
            domain_view=domain_view,
            capability_state=self._capabilities.resolve(requested_capabilities),
            lineage=lineage,
        )

    def _commit(
        self,
        *,
        session_id: str,
        appended: tuple[ConversationMessage, ...],
        expected_session_revision: int,
    ) -> None:
        """Append *appended* and commit once through the canonical adapter.

        The single commit carries the same expected previous revision the
        caller's assertion was verified against, so a concurrent canonical
        writer turns the commit into the safe conversation conflict — never a
        silent retry with a new revision.
        """

        state = self._state.load_conversation(session_id)
        if state is None:
            state = ConversationState(session_id=session_id)
        self._state.save_conversation(
            state.append(*appended),
            expected_previous_revision=expected_session_revision,
        )
