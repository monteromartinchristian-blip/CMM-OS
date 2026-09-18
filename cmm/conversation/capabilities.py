"""Phase 11.5 — requested versus effective conversational capability state.

The conversational boundary reports what a caller *requests* and what CMM OS
can actually *provide* at this baseline.  A request flag is descriptive only:
it never creates execution authority, never enables an owner and never changes
an effective mode.  Effective state derives exclusively from the injected
canonical application declarations — the resolver reads nothing from a
provider, a model, a registry or any live runtime.

The sixteen fixed capability IDs of Phase 11.5 are always resolved, in the
fixed plan order, whether or not they were requested.  Remediation MAJOR-04
added the seven explicit control capabilities (``approval_response``, the five
workflow controls and ``action_execution``): no canonical application command
owns them at this baseline, so each stays ``UNAVAILABLE`` with ``effective=None``
and a canonical reason code, and availability is never inferred from a workflow
reference, an approval reference, a registered workflow, an Orchestrator route,
a Bot ID or a Domain package.  The frozen baseline truth
table is honest about the current phase:

- streaming is ``DEGRADED``: the public SSE boundary delivers deterministic
  response events for an already-computed application result, not provider
  token streaming, so the effective mode is ``response_event_stream``;
- ``request_cancellation`` is ``UNAVAILABLE``: the application surface exists
  but no canonical cancellable-request owner does.  It may only become
  ``AVAILABLE`` when an injected canonical ``ApplicationCapability`` with ID
  ``request-cancellation`` explicitly reports ``CapabilityStatus.AVAILABLE``;
- ``document_upload`` is ``UNAVAILABLE``: no canonical storage owner exists in
  this phase and the later file/artifact authority stays reserved;
- ``attachments`` are ``reference_only`` and ``bot_association`` is
  ``opaque_non_authoritative`` — a bot association can never grant tools,
  permissions, provider selection or memory policy by itself.

An unknown, blank or non-string requested capability ID fails closed with the
conversational ``INVALID_REQUEST`` boundary error; it never silently becomes
available and never fabricates an entry.

This module consumes the canonical application declaration types
(``cmm.conversation -> cmm.application``, sanctioned by design section 25) and
defines no registry, no cancellation engine and no active-request store.

See ``docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md``
(sections 16-20, 25) and the committed Phase 11.5 implementation plan.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from types import MappingProxyType

from cmm.application.contracts import ApplicationCapability, CapabilityStatus
from cmm.conversation.contracts import (
    ConversationCapabilityState,
    ConversationCapabilityStatus,
)
from cmm.conversation.errors import ConversationBoundaryError

__all__ = [
    "CONVERSATION_CAPABILITY_IDS",
    "REASON_NO_CANCELLABLE_OWNER",
    "REASON_NO_CANONICAL_ACTION_EXECUTOR",
    "REASON_NO_CANONICAL_APPROVAL_COMMAND",
    "REASON_NO_CANONICAL_STORAGE_OWNER",
    "REASON_NO_CANONICAL_WORKFLOW_CONTROL",
    "REASON_PROVIDER_TOKEN_STREAMING_UNAVAILABLE",
    "ConversationCapabilityResolver",
]

#: The fixed conversational capability IDs of Phase 11.5, in the fixed order
#: pinned by the committed plan.
CONVERSATION_CAPABILITY_IDS = (
    "continuous_conversation",
    "message_editing",
    "controlled_regeneration",
    "attachments",
    "response_streaming",
    "request_cancellation",
    "document_upload",
    "bot_association",
    "domain_projection",
    "approval_response",
    "workflow_pause",
    "workflow_resume",
    "workflow_cancel",
    "workflow_retry",
    "workflow_replan",
    "action_execution",
)

#: No provider token-streaming runtime owns live generation at this baseline;
#: streaming stays a deterministic response-event delivery.
REASON_PROVIDER_TOKEN_STREAMING_UNAVAILABLE = "PROVIDER_TOKEN_STREAMING_UNAVAILABLE"

#: The cancellation surface exists on the application boundary, but no
#: canonical cancellable-request owner exists at this baseline.
REASON_NO_CANCELLABLE_OWNER = "NO_CANCELLABLE_OWNER"

#: No canonical storage owner exists for document upload in this phase.
REASON_NO_CANONICAL_STORAGE_OWNER = "NO_CANONICAL_STORAGE_OWNER"

#: No canonical application command submits an approval response at this
#: baseline, so approving from the conversational boundary stays unavailable.
REASON_NO_CANONICAL_APPROVAL_COMMAND = "NO_CANONICAL_APPROVAL_COMMAND"

#: No canonical application command controls a workflow (pause, resume, cancel,
#: retry, replan) at this baseline; workflow control is never inferred from a
#: visible workflow reference or a registered workflow.
REASON_NO_CANONICAL_WORKFLOW_CONTROL = "NO_CANONICAL_WORKFLOW_CONTROL"

#: No canonical application command executes an action at this baseline.
REASON_NO_CANONICAL_ACTION_EXECUTOR = "NO_CANONICAL_ACTION_EXECUTOR"

#: The conversational ID of the cancellation capability.
_CANCELLATION_CAPABILITY = "request_cancellation"

#: The canonical application capability ID that may authorize cancellation.
_APPLICATION_CANCELLATION_CAPABILITY_ID = "request-cancellation"

#: The effective mode of cancellation once a canonical declaration reports it
#: available.  It names the canonical cancellable requests the application
#: boundary can now own; it is never granted by a request flag.
_CANCELLABLE_EFFECTIVE = "canonical_cancellable_requests"

#: The frozen baseline state of every capability whose effective mode does not
#: depend on an injected canonical declaration: capable ID -> (status,
#: effective, reason).  ``request_cancellation`` is resolved separately.  The
#: table is frozen at runtime too (``MappingProxyType``), so a later rewrite
#: raises ``TypeError`` instead of silently changing resolved state.
_BASELINE_STATES: Mapping[
    str, tuple[ConversationCapabilityStatus, str | None, str | None]
] = MappingProxyType(
    {
        "continuous_conversation": (
            ConversationCapabilityStatus.AVAILABLE,
            "session_backed_multi_turn",
            None,
        ),
        "message_editing": (
            ConversationCapabilityStatus.AVAILABLE,
            "append_only_lineage",
            None,
        ),
        "controlled_regeneration": (
            ConversationCapabilityStatus.AVAILABLE,
            "canonical_reexecution",
            None,
        ),
        "attachments": (
            ConversationCapabilityStatus.AVAILABLE,
            "reference_only",
            None,
        ),
        "response_streaming": (
            ConversationCapabilityStatus.DEGRADED,
            "response_event_stream",
            REASON_PROVIDER_TOKEN_STREAMING_UNAVAILABLE,
        ),
        "document_upload": (
            ConversationCapabilityStatus.UNAVAILABLE,
            None,
            REASON_NO_CANONICAL_STORAGE_OWNER,
        ),
        "bot_association": (
            ConversationCapabilityStatus.AVAILABLE,
            "opaque_non_authoritative",
            None,
        ),
        "domain_projection": (
            ConversationCapabilityStatus.AVAILABLE,
            "authorized_projection_when_supplied_by_canonical_integrator",
            None,
        ),
        "approval_response": (
            ConversationCapabilityStatus.UNAVAILABLE,
            None,
            REASON_NO_CANONICAL_APPROVAL_COMMAND,
        ),
        "workflow_pause": (
            ConversationCapabilityStatus.UNAVAILABLE,
            None,
            REASON_NO_CANONICAL_WORKFLOW_CONTROL,
        ),
        "workflow_resume": (
            ConversationCapabilityStatus.UNAVAILABLE,
            None,
            REASON_NO_CANONICAL_WORKFLOW_CONTROL,
        ),
        "workflow_cancel": (
            ConversationCapabilityStatus.UNAVAILABLE,
            None,
            REASON_NO_CANONICAL_WORKFLOW_CONTROL,
        ),
        "workflow_retry": (
            ConversationCapabilityStatus.UNAVAILABLE,
            None,
            REASON_NO_CANONICAL_WORKFLOW_CONTROL,
        ),
        "workflow_replan": (
            ConversationCapabilityStatus.UNAVAILABLE,
            None,
            REASON_NO_CANONICAL_WORKFLOW_CONTROL,
        ),
        "action_execution": (
            ConversationCapabilityStatus.UNAVAILABLE,
            None,
            REASON_NO_CANONICAL_ACTION_EXECUTOR,
        ),
    }
)


def _validated_requested_id(capability_id: object) -> str:
    """Return the requested ID unchanged when it is a known capability ID."""

    if (
        not isinstance(capability_id, str)
        or capability_id not in CONVERSATION_CAPABILITY_IDS
    ):
        raise ConversationBoundaryError()

    return capability_id


def _requested_flags(requested: Iterable[str]) -> frozenset[str]:
    """Return the requested conversational IDs, deduplicated by construction.

    Every ID is validated as it is consumed and the ``frozenset`` is built
    directly from the validated iterable, so set membership — never a separate
    dedupe step — is the deduplication: a repeated request is indistinguishable
    from a single one.  An unknown, blank or non-string ID fails closed with
    the conversational ``INVALID_REQUEST`` boundary error.
    """

    return frozenset(
        _validated_requested_id(capability_id) for capability_id in requested
    )


class ConversationCapabilityResolver:
    """Resolves requested conversational capabilities to their effective state.

    The resolver is descriptive and reads only the canonical application
    declarations injected at construction.  Requesting a capability marks it
    as requested and changes nothing else; the resolver never creates
    authority and never mutates its inputs.

    Construction is fail-closed and mirrors
    ``cmm.application.capabilities.CapabilityApplicationService``: every
    injected entry must be a concrete ``ApplicationCapability`` (otherwise
    ``TypeError``) and no capability ID may be declared twice (otherwise
    ``ValueError``).  Rejecting duplicates keeps declaration precedence
    unconstructible rather than ambiguous: an ``(UNAVAILABLE, AVAILABLE)`` pair
    can never exist, so no later declaration can silently unlock cancellation.
    Should a duplicate ever exist, the first declaration in injection order
    would win — a later declaration never overrides an earlier one.
    """

    def __init__(
        self,
        application_capabilities: Sequence[ApplicationCapability] = (),
    ) -> None:
        # The injected declarations are copied to an immutable tuple; the
        # resolver never mutates its inputs and reads no other capability state.
        declarations = tuple(application_capabilities)

        for declaration in declarations:
            if not isinstance(declaration, ApplicationCapability):
                raise TypeError(
                    "application capabilities must contain ApplicationCapability "
                    f"values, not {type(declaration).__name__}"
                )

        identifiers = [declaration.capability_id for declaration in declarations]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("capabilities must not declare a duplicate capability ID")

        self._application_capabilities: tuple[ApplicationCapability, ...] = declarations

    def resolve(
        self,
        requested: Iterable[str] = (),
    ) -> tuple[ConversationCapabilityState, ...]:
        """Return the effective state of all sixteen fixed capabilities, in order.

        Every requested ID must be one of the sixteen fixed conversational
        capability IDs; an unknown, blank or non-string ID *inside* the
        iterable fails closed with the conversational ``INVALID_REQUEST``
        boundary error.  A ``None`` (or otherwise non-iterable) ``requested``
        value is a Python-boundary type defect of the call site and raises the
        natural ``TypeError`` instead — the same fail-closed convention the
        application boundary uses for malformed call-site types.
        """

        flags = _requested_flags(requested)

        return tuple(
            self._state_for(capability_id, capability_id in flags)
            for capability_id in CONVERSATION_CAPABILITY_IDS
        )

    def _state_for(
        self, capability_id: str, requested: bool
    ) -> ConversationCapabilityState:
        if capability_id == _CANCELLATION_CAPABILITY:
            return self._cancellation_state(requested)

        status, effective, reason = _BASELINE_STATES[capability_id]

        return ConversationCapabilityState(
            capability=capability_id,
            requested=requested,
            effective=effective,
            status=status,
            reason=reason,
        )

    def _cancellation_state(self, requested: bool) -> ConversationCapabilityState:
        """Report cancellation from the injected canonical declaration only.

        Cancellation becomes available only when an injected
        ``ApplicationCapability`` with ID ``request-cancellation`` explicitly
        reports ``CapabilityStatus.AVAILABLE``.  Any other status, or absence,
        leaves it ``UNAVAILABLE``: the reason is the declaration's canonical
        ``reason_code`` when it carries one, and the canonical
        ``NO_CANCELLABLE_OWNER`` code otherwise — an ``UNAVAILABLE`` row never
        resolves without a reason.

        Construction rejects duplicate declarations, so this first-match
        lookup is unambiguous by construction; the first declaration in
        injection order is the one that counts and a later declaration never
        overrides an earlier one.
        """

        declaration = next(
            (
                capability
                for capability in self._application_capabilities
                if capability.capability_id == _APPLICATION_CANCELLATION_CAPABILITY_ID
            ),
            None,
        )

        if declaration is not None and declaration.status is CapabilityStatus.AVAILABLE:
            return ConversationCapabilityState(
                capability=_CANCELLATION_CAPABILITY,
                requested=requested,
                effective=_CANCELLABLE_EFFECTIVE,
                status=ConversationCapabilityStatus.AVAILABLE,
                reason=None,
            )

        reason = REASON_NO_CANCELLABLE_OWNER
        if declaration is not None and declaration.reason_code is not None:
            reason = declaration.reason_code

        return ConversationCapabilityState(
            capability=_CANCELLATION_CAPABILITY,
            requested=requested,
            effective=None,
            status=ConversationCapabilityStatus.UNAVAILABLE,
            reason=reason,
        )
