"""Phase 11.5 — canonical conversational interface public boundary.

This package owns the public conversational surface of CMM OS: the frozen
public conversational contracts, the closed, safe conversational failure value
and the safe conversational boundary failures.  It owns no conversational
authority — canonical session persistence,
application dispatch, orchestration, approval, workflow, execution, memory and
knowledge ownership all stay with their canonical packages.

See ``docs/superpowers/specs/2026-09-17-phase-11.5-conversational-interface-design.md``.
"""

from __future__ import annotations

from cmm.conversation.contracts import (
    AssistantResponse,
    ConversationAttachmentRef,
    ConversationCapabilityState,
    ConversationCapabilityStatus,
    ConversationInteractionMode,
    ConversationLineage,
    ConversationMessage,
    ConversationRole,
)
from cmm.conversation.errors import (
    ConversationBoundaryError,
    ConversationError,
    ConversationErrorCode,
    ConversationSessionConflictError,
    ConversationSessionNotFoundError,
)

__all__ = [
    "AssistantResponse",
    "ConversationAttachmentRef",
    "ConversationBoundaryError",
    "ConversationCapabilityState",
    "ConversationCapabilityStatus",
    "ConversationError",
    "ConversationErrorCode",
    "ConversationInteractionMode",
    "ConversationLineage",
    "ConversationMessage",
    "ConversationRole",
    "ConversationSessionConflictError",
    "ConversationSessionNotFoundError",
]
