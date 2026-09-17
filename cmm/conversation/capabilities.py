"""Phase 11.5 — requested versus effective conversational capability state.

The conversational boundary reports what a caller *requests* and what CMM OS
can actually *provide* at this baseline.  A request flag is descriptive only:
it never creates execution authority, never enables an owner and never changes
an effective mode.  Effective state derives exclusively from the injected
canonical application declarations — the resolver reads nothing from a
provider, a model, a registry or any live runtime.

The nine fixed capability IDs of Phase 11.5 are always resolved, in the fixed
plan order, whether or not they were requested.  The frozen baseline truth
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

from cmm.application.contracts import ApplicationCapability, CapabilityStatus
from cmm.conversation.contracts import (
    ConversationCapabilityState,
    ConversationCapabilityStatus,
)
from cmm.conversation.errors import ConversationBoundaryError

__all__ = [
    "CONVERSATION_CAPABILITY_IDS",
    "REASON_NO_CANCELLABLE_OWNER",
    "REASON_NO_CANONICAL_STORAGE_OWNER",
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
)

#: No provider token-streaming runtime owns live generation at this baseline;
#: streaming stays a deterministic response-event delivery.
REASON_PROVIDER_TOKEN_STREAMING_UNAVAILABLE = "PROVIDER_TOKEN_STREAMING_UNAVAILABLE"

#: The cancellation surface exists on the application boundary, but no
#: canonical cancellable-request owner exists at this baseline.
REASON_NO_CANCELLABLE_OWNER = "NO_CANCELLABLE_OWNER"

#: No canonical storage owner exists for document upload in this phase.
REASON_NO_CANONICAL_STORAGE_OWNER = "NO_CANONICAL_STORAGE_OWNER"

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
#: effective, reason).  ``request_cancellation`` is resolved separately.
_BASELINE_STATES: Mapping[
    str, tuple[ConversationCapabilityStatus, str | None, str | None]
] = {
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
}


def _requested_flags(requested: Iterable[str]) -> frozenset[str]:
    """Return the deduplicated requested IDs; every invalid ID fails closed."""

    flags: set[str] = set()

    for capability_id in requested:
        if (
            not isinstance(capability_id, str)
            or capability_id not in CONVERSATION_CAPABILITY_IDS
        ):
            raise ConversationBoundaryError()

        flags.add(capability_id)

    return frozenset(flags)


class ConversationCapabilityResolver:
    """Resolves requested conversational capabilities to their effective state.

    The resolver is descriptive and reads only the canonical application
    declarations injected at construction.  Requesting a capability marks it
    as requested and changes nothing else; the resolver never creates
    authority and never mutates its inputs.
    """

    def __init__(
        self,
        application_capabilities: Sequence[ApplicationCapability] = (),
    ) -> None:
        # The injected declarations are copied to an immutable tuple; the
        # resolver never mutates its inputs and reads no other capability state.
        self._application_capabilities: tuple[ApplicationCapability, ...] = tuple(
            application_capabilities
        )

    def resolve(
        self,
        requested: Iterable[str] = (),
    ) -> tuple[ConversationCapabilityState, ...]:
        """Return the effective state of all nine fixed capabilities, in order."""

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
        leaves it ``UNAVAILABLE`` with the canonical reason code.
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
