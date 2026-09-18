"""Phase 11.5 — pure projection of application and authorized Domain state.

``ConversationResponseProjector`` turns one public ``ApplicationResponse`` and,
when the service has verified it, one already authorized
``ConversationalDomainView`` into one frozen ``AssistantResponse``.  The
projector is stateless and side-effect free: it calls no Domain resolution,
constructs no ``ConversationalDomainView``, fabricates no missing reference and
never exposes hidden reasoning.

This module also owns the one trusted seam through which Domain visibility may
reach the conversational boundary (remediation MAJOR-02):

- ``AuthorizedDomainProjectionSource`` is a *read-only* protocol composed at
  ``ConversationService`` construction time.  It stores nothing, resolves
  nothing, composes nothing, authorizes nothing, approves nothing, executes
  nothing and mutates nothing: it may only return an already-authorized
  Phase 10.45 ``DomainInterfaceProjection`` or ``None``.
- ``verify_domain_projection_binding`` re-verifies, before any visibility is
  projected, that the returned projection belongs to *this* request, *this*
  canonical session, *this* canonical Domain-resolution route and *this*
  application result, and that the application result's own supporting-domain
  evidence is well-formed provenance — absent, ``None``, scalar, bytes-like,
  non-sequence or mixed-type evidence fails closed and is never normalized,
  dropped or stringified (remediation MINOR_R1_02).  A mismatch fails closed and
  exposes zero Domain references; the conversational layer never reconstructs
  Domain visibility from application data, metadata, trace payloads, session
  metadata or caller references.

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

See ``docs/superpowers/specs/2026-09-18-phase-11.5-remediation-v1-design.md``
§6 and ``docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md``
(sections 7.2, 7.3, 10, 22 and 23).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, runtime_checkable

from cmm.application.contracts import ApplicationResponse, ApplicationStatus
from cmm.conversation.contracts import (
    AssistantResponse,
    ConversationActionState,
    ConversationActionStatus,
    ConversationCapabilityState,
    ConversationLineage,
    ConversationMessage,
    ConversationRole,
)
from cmm.conversation.errors import ConversationProjectionBindingError
from cmm.domains.interface_integration_contracts import (
    ConversationalDomainView,
    DomainInterfaceProjection,
)

__all__ = [
    "CANONICAL_DOMAIN_RESOLUTION_TRACE_PREFIX",
    "AuthorizedDomainProjectionSource",
    "ConversationResponseProjector",
    "canonical_domain_resolution_reference",
    "verify_domain_projection_binding",
]

#: Canonical Domain routing emits the real Domain-resolution reference as this
#: one trace reference (``cmm.orchestration.domain_router``); the binding
#: verifier reads that existing reference and invents no second identity.
CANONICAL_DOMAIN_RESOLUTION_TRACE_PREFIX = "domain-resolution:"

_BYTES_LIKE = (str, bytes, bytearray, memoryview)


@runtime_checkable
class AuthorizedDomainProjectionSource(Protocol):
    """Read-only bridge to already-authorized Phase 10.45 Domain projections.

    Composed at ``ConversationService`` construction time.  An implementation
    may only return an already-authorized ``DomainInterfaceProjection`` of the
    request it is asked about, or ``None`` when no canonical projection exists
    for that request.  It owns no storage, no resolution, no composition, no
    permission, no approval, no workflow, no session and no execution, and it
    mutates nothing.
    """

    def get_projection(
        self,
        *,
        request_id: str,
        session_id: str,
        application_response: ApplicationResponse,
    ) -> DomainInterfaceProjection | None: ...


def canonical_domain_resolution_reference(
    application_response: ApplicationResponse,
) -> str | None:
    """Return the canonical Domain-resolution reference of one application result.

    Canonical Domain routing emits ``domain-resolution:<id>`` as a trace
    reference of the orchestration decision, and the application boundary
    projects those reference strings unchanged.  This reads that one existing
    public reference — never a raw trace payload, and never a newly invented
    identifier — so the Phase 10.45 ``resolution_reference_id`` can be bound to
    the same-request canonical route.
    """

    data = application_response.data
    if not isinstance(data, Mapping):
        return None
    trace_refs = data.get("trace_refs")
    if isinstance(trace_refs, _BYTES_LIKE) or not isinstance(trace_refs, Sequence):
        return None
    for reference in trace_refs:
        if not isinstance(reference, str):
            continue
        if not reference.startswith(CANONICAL_DOMAIN_RESOLUTION_TRACE_PREFIX):
            continue
        value = reference[len(CANONICAL_DOMAIN_RESOLUTION_TRACE_PREFIX) :]
        if value:
            return value
    return None


def _bound(response: ApplicationResponse) -> Mapping[str, Any]:
    """Return the public data mapping of one application response, or fail closed."""

    data = response.data
    if not isinstance(data, Mapping):
        raise ConversationProjectionBindingError()
    return data


def _strict_public_string_sequence(value: object) -> tuple[str, ...] | None:
    """Return *value* as an exact tuple of strings, or ``None`` when malformed.

    This is the adversarial provenance boundary of the binding verifier
    (remediation MINOR_R1_02): the value must be an actual sequence — never a
    string, a bytes-like value, a mapping or an arbitrary object — whose every
    member is already a string.  Malformed evidence is never repaired: no member
    is dropped or stringified and no absent value becomes an empty sequence; a
    valid sequence is returned as the exact tuple it received, preserving order
    and membership.
    """

    if isinstance(value, _BYTES_LIKE) or not isinstance(value, Sequence):
        return None
    if not all(isinstance(item, str) for item in value):
        return None
    return tuple(value)


def verify_domain_projection_binding(
    *,
    projection: object,
    request_id: str,
    session_id: str,
    application_response: ApplicationResponse,
) -> ConversationalDomainView:
    """Return the bound conversational view of *projection*, or fail closed.

    Before any Domain visibility reaches an ``AssistantResponse``, the
    projection must prove it belongs to the current turn: the same request
    identity the service is serving, the same canonical session, the same
    canonical Domain-resolution route the application result carries, and the
    same primary/supporting Domain membership the application result reports.
    The projection must be the real content-bound Phase 10.45
    ``DomainInterfaceProjection`` — a raw mapping, a duck-typed object or a
    manually constructed view is never authorization — and its own constructor
    has already verified its content digest.

    Any mismatch raises ``ConversationProjectionBindingError``: the turn fails
    closed and exposes zero Domain references rather than a foreign one.  The
    application result's ``supporting_domains`` evidence is validated strictly
    (remediation MINOR_R1_02): the key must be present and must be a sequence
    whose every member is already a string — ``None``, a scalar, a bytes-like
    value, a non-sequence and any mixed-type sequence are malformed provenance
    and fail closed, and no member is ever dropped or stringified.
    """

    if type(projection) is not DomainInterfaceProjection:
        raise ConversationProjectionBindingError()
    data = _bound(application_response)
    conversational = projection.conversational
    if conversational is None:
        raise ConversationProjectionBindingError()
    # Request binding: the projection, the application result and the request
    # the service is serving must be one identity.
    if projection.request_id != request_id:
        raise ConversationProjectionBindingError()
    if projection.request_id != application_response.request_id:
        raise ConversationProjectionBindingError()
    # Session binding: the projection and the application result both name the
    # current canonical session, and that session is the one being served.
    if projection.session_reference_id != session_id:
        raise ConversationProjectionBindingError()
    if data.get("session_id") != session_id:
        raise ConversationProjectionBindingError()
    # Domain-membership binding: the visible Domain membership is exactly the
    # membership the canonical application result reports, and the reported
    # evidence itself must be well-formed provenance (remediation MINOR_R1_02):
    # a missing key, ``None``, a scalar, a bytes-like value, a non-sequence or
    # any non-string member fails closed instead of being normalized, dropped or
    # stringified.
    if conversational.primary_domain != data.get("primary_domain"):
        raise ConversationProjectionBindingError()
    if "supporting_domains" not in data:
        raise ConversationProjectionBindingError()
    supporting_domains = _strict_public_string_sequence(data["supporting_domains"])
    if supporting_domains is None:
        raise ConversationProjectionBindingError()
    if tuple(conversational.supporting_domains) != supporting_domains:
        raise ConversationProjectionBindingError()
    # Route binding: the projection's resolution reference is the canonical
    # Domain-resolution reference of this same application result.
    if projection.resolution_reference_id != canonical_domain_resolution_reference(
        application_response
    ):
        raise ConversationProjectionBindingError()
    return conversational


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
    view it consumes is the one the service verified against the current
    request, canonical session, canonical Domain-resolution route and
    application result (remediation MAJOR-02); the projector holds no state
    between calls, so an identical call always yields an equal response, and it
    never mutates its inputs.
    """

    def project(
        self,
        *,
        request_message: ConversationMessage,
        assistant_message_id: str,
        created_at: str,
        application_response: ApplicationResponse,
        authorized_domain_view: ConversationalDomainView | None,
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
        if authorized_domain_view is not None and not isinstance(
            authorized_domain_view, ConversationalDomainView
        ):
            raise TypeError(
                "authorized_domain_view must be a ConversationalDomainView or None"
            )
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

        action_state: tuple[ConversationActionState, ...]

        if authorized_domain_view is None:
            sources = ()
            pending_questions = ()
            approval_requests = ()
            workflow_updates = ()
            action_state = ()
            memory_updates = ()
            warnings = ()
            reasoning_summary = {}
            domain_state = {}
        else:
            sources = authorized_domain_view.source_refs
            pending_questions = authorized_domain_view.question_refs
            approval_requests = authorized_domain_view.approval_refs
            workflow_updates = authorized_domain_view.workflow_refs
            # A visible approval reference is never an approval (remediation
            # MAJOR-04): the only canonical fact a visible approval reference
            # carries is that the approval is required/pending, so the action
            # state reports exactly that and never a terminal status.
            action_state = tuple(
                ConversationActionState(
                    reference=reference,
                    status=ConversationActionStatus.APPROVAL_REQUIRED,
                    kind="approval",
                )
                for reference in authorized_domain_view.approval_refs
            )
            memory_updates = authorized_domain_view.memory_proposal_refs
            warnings = authorized_domain_view.warning_refs
            reasoning_summary = {
                "result_refs": list(authorized_domain_view.result_refs),
                "contradiction_refs": list(authorized_domain_view.contradiction_refs),
            }
            domain_state = {
                "primary_domain": authorized_domain_view.primary_domain,
                "supporting_domains": list(authorized_domain_view.supporting_domains),
                "confidence": authorized_domain_view.confidence,
                "status": authorized_domain_view.status.value,
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
            action_state=action_state,
            domain_state=domain_state,
            capability_state=capability_state,
            memory_updates=memory_updates,
            warnings=warnings,
        )
