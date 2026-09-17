"""Phase 11.5 — pure projection of application and authorized Domain state.

``ConversationResponseProjector`` turns one public ``ApplicationResponse`` and,
when supplied, one already authorized ``ConversationalDomainView`` into one
frozen ``AssistantResponse``.  The projector is stateless and side-effect free:
it calls no Domain resolution, constructs no ``ConversationalDomainView``,
fabricates no missing reference and never exposes hidden reasoning.

Every structured surface the projector emits is either a public reference
projected from the canonical Phase 10.45 view or a bounded public value.  The
only Domain value this module can consume is that authorized public projection;
a raw Domain payload, a raw exception or a malformed capability state fails
closed with ``TypeError`` instead of producing a fabricated output.  References
that are absent from the canonical view are never recreated from application
data or metadata — visibility is not authorization, so the conversational
boundary reflects exactly what canonical authority authorized.

The assistant message text is deterministic and truthful: it follows the public
application status/error semantics, calls no model and does not pretend to be a
generated domain answer.  ``proposed_actions`` stays empty at this baseline
because no public-safe application field carries actions, and it is never
invented.

Allowed imports, asserted by ``tests/conversation/test_projection.py``:
``cmm.application.contracts``, ``cmm.domains.interface_integration_contracts``,
this package and the standard library.

See ``docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md``
(sections 7.2, 7.3, 10, 22 and 23).
"""

from __future__ import annotations

from typing import Any

from cmm.application.contracts import ApplicationResponse, ApplicationStatus
from cmm.conversation.contracts import (
    AssistantResponse,
    ConversationCapabilityState,
    ConversationLineage,
    ConversationMessage,
    ConversationRole,
)
from cmm.domains.interface_integration_contracts import ConversationalDomainView

__all__ = ["ConversationResponseProjector"]


def _public_response_text(response: ApplicationResponse) -> str:
    """Return the deterministic public text of one application response.

    A public application error message is already public-safe and names the
    failure, so it is reported first; otherwise the pinned status ladder is
    used.  No model is called and no generated domain answer is pretended.
    """

    if response.error is not None:
        return response.error.message
    if response.status is ApplicationStatus.NEEDS_CLARIFICATION:
        return "Additional information is required."
    if response.status is ApplicationStatus.ROUTED:
        return "The request was routed through the canonical application boundary."
    return f"Application status: {response.status.value}."


class ConversationResponseProjector:
    """Stateless projection of authorized conversation state into a response.

    ``project`` accepts an already authorized ``ConversationalDomainView`` (or
    ``None``) and never obtains authorization itself: it resolves no domain,
    builds no view and re-derives no reference from application metadata.  The
    projector holds no state between calls, so an identical call always yields
    an equal response, and it never mutates its inputs.
    """

    def project(
        self,
        *,
        request_message: ConversationMessage,
        assistant_message_id: str,
        created_at: str,
        application_response: ApplicationResponse,
        domain_view: ConversationalDomainView | None,
        capability_state: tuple[ConversationCapabilityState, ...],
        lineage: ConversationLineage = ConversationLineage(),  # noqa: B008 - pinned frozen default
    ) -> AssistantResponse:
        """Project one authorized response into one frozen ``AssistantResponse``.

        Wrong types fail closed with ``TypeError``: a raw exception, a raw
        Domain mapping and a malformed capability state can never become a
        fabricated public response.
        """

        if not isinstance(request_message, ConversationMessage):
            raise TypeError("request_message must be a ConversationMessage")
        if not isinstance(application_response, ApplicationResponse):
            raise TypeError("application_response must be an ApplicationResponse")
        if domain_view is not None and not isinstance(
            domain_view, ConversationalDomainView
        ):
            raise TypeError("domain_view must be a ConversationalDomainView or None")
        if not isinstance(capability_state, tuple) or not all(
            isinstance(state, ConversationCapabilityState) for state in capability_state
        ):
            raise TypeError(
                "capability_state must be a tuple of ConversationCapabilityState values"
            )
        if not isinstance(lineage, ConversationLineage):
            raise TypeError("lineage must be a ConversationLineage")

        sources: tuple[str, ...]
        pending_questions: tuple[str, ...]
        approval_requests: tuple[str, ...]
        workflow_updates: tuple[str, ...]
        memory_updates: tuple[str, ...]
        warnings: tuple[str, ...]
        reasoning_summary: dict[str, Any]
        domain_state: dict[str, Any]

        if domain_view is None:
            sources = ()
            pending_questions = ()
            approval_requests = ()
            workflow_updates = ()
            memory_updates = ()
            warnings = ()
            reasoning_summary = {}
            domain_state = {}
        else:
            sources = domain_view.source_refs
            pending_questions = domain_view.question_refs
            approval_requests = domain_view.approval_refs
            workflow_updates = domain_view.workflow_refs
            memory_updates = domain_view.memory_proposal_refs
            warnings = domain_view.warning_refs
            reasoning_summary = {
                "result_refs": list(domain_view.result_refs),
                "contradiction_refs": list(domain_view.contradiction_refs),
            }
            domain_state = {
                "primary_domain": domain_view.primary_domain,
                "supporting_domains": list(domain_view.supporting_domains),
                "confidence": domain_view.confidence,
                "status": domain_view.status.value,
            }

        message = ConversationMessage(
            id=assistant_message_id,
            session_id=request_message.session_id,
            role=ConversationRole.ASSISTANT,
            content=_public_response_text(application_response),
            created_at=created_at,
            bot_id=request_message.bot_id,
            references=(),
            attachments=(),
            lineage=lineage,
        )

        return AssistantResponse(
            message=message,
            sources=sources,
            reasoning_summary=reasoning_summary,
            pending_questions=pending_questions,
            proposed_actions=(),
            approval_requests=approval_requests,
            workflow_updates=workflow_updates,
            domain_state=domain_state,
            capability_state=capability_state,
            memory_updates=memory_updates,
            warnings=warnings,
        )
