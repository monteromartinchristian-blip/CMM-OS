"""CMMChat Wave E0 — the canonical turn sequencing of one real model execution.

One E0 turn is three canonical steps in a frozen order:

1. the user turn is submitted through the canonical
   :class:`~cmm.conversation.service.ConversationService`, which reaches the
   application gateway, the application request adapter and the Phase 11.2
   orchestrator exactly as Phase 11.5 defined — nothing here replaces, wraps or
   duplicates that path;
2. the canonical ``OrchestrationDecisionRecord`` the orchestrator persisted for
   that turn's *canonical request identity* is resolved from the canonical
   orchestration decision repository — the decision is looked up, never
   re-derived and never re-classified;
3. that canonical decision, the turn's text and the canonical
   ``ModelRequirements`` are mapped onto one
   :class:`~cmm.model_execution.contracts.ModelExecutionRequest` and executed by
   the canonical :class:`~cmm.model_execution.executor.CanonicalModelExecutor`.

This module is sequencing glue only.  It owns no session, no transcript, no
store, no registry, no provider and no routing policy: session authority stays
with the canonical `SessionStore` through `ConversationService`, decision
authority stays with the canonical repository, and model authority stays with
the canonical `ModelRouter` / `ProviderFactory` / `LLMProvider` stack the
executor delegates to.  The transcript commit performed by the conversation
service is preserved whatever the model outcome is: a normalized execution
failure is reported, not retried, and never rewritten into a success.
"""

from __future__ import annotations

from dataclasses import dataclass

from cmm.conversation.contracts import (
    AssistantResponse,
    ConversationMessage,
    ConversationRole,
)
from cmm.conversation.service import ConversationService
from cmm.model_execution.contracts import (
    ModelExecutionParameters,
    ModelExecutionRequest,
    ModelExecutionResult,
)
from cmm.model_execution.errors import ModelExecutionError
from cmm.model_execution.executor import CanonicalModelExecutor
from cmm.orchestration.contracts import OrchestrationDecisionRecord
from cmm.orchestration.decision_repository import OrchestrationDecisionRepository
from kernel.llm.model_selection import ModelRequirements

__all__ = [
    "ModelTurnRequest",
    "ModelTurnResult",
    "execute_conversational_turn",
]

#: The safe reason code reported when the canonical decision of a turn that
#: already traversed the canonical pipeline cannot be resolved.
CANONICAL_DECISION_UNAVAILABLE = "CANONICAL_DECISION_UNAVAILABLE"


def _non_empty_text(value: object, *, label: str) -> str:
    """Return a non-empty stripped text value or fail closed."""

    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} must be non-empty")
    return normalized


@dataclass(frozen=True, slots=True)
class ModelTurnRequest:
    """One conversational turn whose answer must come from a real model.

    Every identity and timestamp is caller-supplied, so a turn is deterministic:
    ``request_id`` is the canonical request identity the decision is resolved by,
    ``user_message_id`` is the user message identity, and
    ``assistant_message_id`` / ``assistant_created_at`` belong to the assistant
    message the canonical conversational boundary commits.
    """

    session_id: str
    user_message_id: str
    content: str
    user_created_at: str
    request_id: str
    expected_session_revision: int
    assistant_message_id: str
    assistant_created_at: str
    requested_capabilities: tuple[str, ...] = ()
    requirements: ModelRequirements | None = None
    parameters: ModelExecutionParameters | None = None

    def __post_init__(self) -> None:
        for name in (
            "session_id",
            "user_message_id",
            "content",
            "user_created_at",
            "request_id",
            "assistant_message_id",
            "assistant_created_at",
        ):
            object.__setattr__(
                self, name, _non_empty_text(getattr(self, name), label=name)
            )
        object.__setattr__(
            self,
            "requested_capabilities",
            tuple(self.requested_capabilities),
        )
        if self.requirements is not None and not isinstance(
            self.requirements, ModelRequirements
        ):
            raise TypeError("requirements must be ModelRequirements or None")
        if self.parameters is not None and not isinstance(
            self.parameters, ModelExecutionParameters
        ):
            raise TypeError("parameters must be ModelExecutionParameters or None")


@dataclass(frozen=True, slots=True)
class ModelTurnResult:
    """One completed turn: the canonical response, decision and model result."""

    response: AssistantResponse
    decision: OrchestrationDecisionRecord
    execution: ModelExecutionResult

    @property
    def text(self) -> str | None:
        """Return the normalized model text, or ``None`` when it failed."""

        return self.execution.text


def execute_conversational_turn(
    *,
    conversation: ConversationService,
    decisions: OrchestrationDecisionRepository,
    executor: CanonicalModelExecutor,
    turn: ModelTurnRequest,
) -> ModelTurnResult:
    """Run one canonical turn and execute its real model inference.

    The conversational submit happens first and exactly once, so the canonical
    transcript is committed even when the model execution fails: the failure is
    then reported as the normalized ``execution`` result.  A turn whose
    canonical decision cannot be resolved fails closed with
    :class:`~cmm.model_execution.errors.ModelExecutionError` — the seam never
    invents a decision, a route or an answer.
    """

    if not isinstance(conversation, ConversationService):
        raise TypeError("conversation must be the canonical ConversationService")
    if not isinstance(executor, CanonicalModelExecutor):
        raise TypeError("executor must be the canonical CanonicalModelExecutor")
    if not isinstance(turn, ModelTurnRequest):
        raise TypeError("turn must be a ModelTurnRequest")
    if not isinstance(decisions, OrchestrationDecisionRepository):
        raise TypeError(
            "decisions must be the canonical orchestration decision repository"
        )

    message = ConversationMessage(
        id=turn.user_message_id,
        session_id=turn.session_id,
        role=ConversationRole.USER,
        content=turn.content,
        created_at=turn.user_created_at,
    )
    response = conversation.submit(
        message,
        request_id=turn.request_id,
        expected_session_revision=turn.expected_session_revision,
        requested_capabilities=turn.requested_capabilities,
        assistant_message_id=turn.assistant_message_id,
        assistant_created_at=turn.assistant_created_at,
    )

    decision = decisions.get_by_request_id(turn.request_id)
    if decision is None:
        raise ModelExecutionError(
            "The canonical orchestration decision of this turn is unavailable",
            code=CANONICAL_DECISION_UNAVAILABLE,
            details={"request_id": turn.request_id, "session_id": turn.session_id},
        )

    request = ModelExecutionRequest.from_decision(
        decision,
        prompt=turn.content,
        requirements=turn.requirements,
        parameters=turn.parameters,
    )
    return ModelTurnResult(
        response=response,
        decision=decision,
        execution=executor.execute(request),
    )
