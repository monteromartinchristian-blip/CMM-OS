"""CMMChat Wave E0 — deterministic tests of the canonical turn sequencing.

These tests compose the *real* Phase 11.4 local canonical runtime and the *real*
Phase 11.5 `ConversationService` over it, and drive one turn end to end with a
scripted transport client.  No live inference is required, and the properties
pinned here are exactly the E0 ones:

* the canonical conversational path is entered and preserved
  (`ConversationService` → `ApplicationGateway` → `RequestApplicationService` →
  `Orchestrator`) and the canonical transcript is committed;
* the canonical decision is resolved by the canonical request identity from the
  canonical orchestration decision repository;
* the seam receives one canonical execution request mapped faithfully from that
  decision — the selected route, the identities and the conversational text;
* a normalized execution failure is reported without inventing an answer and
  without discarding the committed turn.
"""

from __future__ import annotations

from typing import Any

import pytest

from cmm.application.contracts import (
    APPLICATION_API_VERSION,
    ApplicationChannel,
    ApplicationCommand,
    ApplicationOperation,
    ApplicationStatus,
)
from cmm.application.local_runtime import build_local_application_runtime
from cmm.conversation.capabilities import ConversationCapabilityResolver
from cmm.conversation.projection import ConversationResponseProjector
from cmm.conversation.service import ConversationService
from cmm.conversation.state import SharedSessionConversationAdapter
from cmm.model_execution.composition import (
    build_local_model_execution,
    register_chat_only_router,
)
from cmm.model_execution.contracts import (
    ModelExecutionErrorCode,
    ModelExecutionParameters,
    ModelExecutionRequest,
    ModelExecutionResult,
    ModelExecutionStatus,
)
from cmm.model_execution.errors import ModelExecutionError
from cmm.model_execution.executor import CanonicalModelExecutor
from cmm.model_execution.turn import (
    ModelTurnRequest,
    execute_conversational_turn,
)
from cmm.orchestration.contracts import ExecutionRoute, IntentKind
from cmm.orchestration.decision_repository import (
    InMemoryOrchestrationDecisionRepository,
)
from kernel.llm.exceptions import ProviderError
from kernel.llm.model_catalog import ModelCatalog
from kernel.llm.model_router import ModelRouter
from kernel.llm.provider_factory import ProviderFactory

MODEL_ID = "chatgpt/chatgpt-web/medium"
SESSION_ID = "session-wave-e0-turn"
REQUEST_ID = "request-wave-e0-turn-1"
USER_MESSAGE_ID = "user-message-wave-e0-1"
ASSISTANT_MESSAGE_ID = "assistant-message-wave-e0-1"
USER_CREATED_AT = "2026-09-19T10:00:00+00:00"
ASSISTANT_CREATED_AT = "2026-09-19T10:00:01+00:00"
PROMPT = "Reply with exactly: CMM_OS_ROUTER_CANARY_OK"
CANNED_TEXT = "CMM_OS_ROUTER_CANARY_OK"


class _ScriptedClient:
    """The canonical factory's injected transport client, scripted per test."""

    def __init__(
        self, *, result: Any = None, error: BaseException | None = None
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._result = result if result is not None else (CANNED_TEXT, 17, 7, "stop")
        self._error = error

    def generate(
        self,
        *,
        model: str,
        system: str | None,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> Any:
        self.calls.append(
            {
                "model": model,
                "system": system,
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self._error is not None:
            raise self._error
        return self._result


class _RecordingExecutor(CanonicalModelExecutor):
    """The canonical seam, recording the canonical requests it received."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.requests: list[ModelExecutionRequest] = []

    def execute(self, request: ModelExecutionRequest) -> ModelExecutionResult:
        self.requests.append(request)
        return super().execute(request)


def _composed() -> tuple[Any, ConversationService, Any, _RecordingExecutor]:
    """Return the canonical runtime, its conversational service, its decisions
    repository and the canonical seam recording over the same registry."""

    runtime = build_local_application_runtime()
    conversation = ConversationService(
        gateway=runtime.gateway,
        state=SharedSessionConversationAdapter(runtime.session_store),
        capabilities=ConversationCapabilityResolver(),
        projector=ConversationResponseProjector(),
    )
    decisions = runtime.container.get_service("orchestration.decision_repository")
    registry = runtime.container.get_service("provider.registry")
    catalog = ModelCatalog(registry)
    register_chat_only_router(
        provider_registry=registry, model_catalog=catalog, model_ids=(MODEL_ID,)
    )
    executor = _RecordingExecutor(
        model_router=ModelRouter(provider_registry=registry, model_catalog=catalog),
        provider_factory=ProviderFactory(),
        provider_registry=registry,
        model_catalog=catalog,
        client=_ScriptedClient(),
    )
    return runtime, conversation, decisions, executor


def _create_session(runtime: Any, *, session_id: str = SESSION_ID) -> int:
    """Create one canonical session through the canonical gateway."""

    response = runtime.gateway.handle(
        ApplicationCommand(
            api_version=APPLICATION_API_VERSION,
            request_id=f"{session_id}-create",
            operation=ApplicationOperation.SESSION_CREATE,
            payload={"session_id": session_id},
            channel=ApplicationChannel.CONVERSATION,
        )
    )
    assert response.status is ApplicationStatus.SUCCESS
    return int(response.data["revision"])


def _turn(
    *,
    expected_session_revision: int,
    parameters: ModelExecutionParameters | None = None,
) -> ModelTurnRequest:
    return ModelTurnRequest(
        session_id=SESSION_ID,
        user_message_id=USER_MESSAGE_ID,
        content=PROMPT,
        user_created_at=USER_CREATED_AT,
        request_id=REQUEST_ID,
        expected_session_revision=expected_session_revision,
        assistant_message_id=ASSISTANT_MESSAGE_ID,
        assistant_created_at=ASSISTANT_CREATED_AT,
        parameters=parameters,
    )


# ── The canonical turn ───────────────────────────────────────────────────────


def test_one_turn_reaches_the_canonical_decision_and_the_canonical_seam() -> None:
    runtime, conversation, decisions, executor = _composed()
    revision = _create_session(runtime)

    result = execute_conversational_turn(
        conversation=conversation,
        decisions=decisions,
        executor=executor,
        turn=_turn(expected_session_revision=revision),
    )

    # The canonical pipeline decided, and the decision is the persisted record.
    assert result.decision.request_id == REQUEST_ID
    assert result.decision.decision_id == f"orchestration-decision:{REQUEST_ID}"
    assert result.decision.execution_route is ExecutionRoute.DIRECT_RESPONSE
    assert result.decision.intent is IntentKind.QUESTION
    assert result.decision.session_id == SESSION_ID
    assert decisions.get_by_request_id(REQUEST_ID) is result.decision
    assert [
        record.decision_id for record in decisions.list_for_session(SESSION_ID)
    ] == [result.decision.decision_id]

    # The seam received exactly one canonical request, mapped faithfully.
    assert len(executor.requests) == 1
    request = executor.requests[0]
    assert request.request_id == REQUEST_ID
    assert request.decision_id == result.decision.decision_id
    assert request.route is ExecutionRoute.DIRECT_RESPONSE
    assert request.prompt == PROMPT

    # The model answer is the normalized result of the canonical provider.
    assert result.execution.status is ModelExecutionStatus.SUCCEEDED
    assert result.text == CANNED_TEXT
    assert result.execution.model_id == MODEL_ID
    assert result.execution.provider_id == "cmmchat-router"


def test_the_canonical_transcript_is_committed_by_the_conversational_owner() -> None:
    runtime, conversation, decisions, executor = _composed()
    revision = _create_session(runtime)

    execute_conversational_turn(
        conversation=conversation,
        decisions=decisions,
        executor=executor,
        turn=_turn(expected_session_revision=revision),
    )

    state = conversation.load(SESSION_ID)
    assert state is not None
    assert [message.id for message in state.messages] == [
        USER_MESSAGE_ID,
        ASSISTANT_MESSAGE_ID,
    ]
    assert state.messages[0].content == PROMPT
    assert runtime.session_store.load(SESSION_ID).revision == revision + 1


def test_the_canonical_exchange_carries_the_turn_text_to_the_model() -> None:
    runtime, conversation, decisions, executor = _composed()
    revision = _create_session(runtime)
    turn = _turn(
        expected_session_revision=revision,
        parameters=ModelExecutionParameters(temperature=0.0, max_tokens=24),
    )

    execute_conversational_turn(
        conversation=conversation, decisions=decisions, executor=executor, turn=turn
    )

    client = executor._client  # the scripted canonical transport
    assert client.calls == [
        {
            "model": MODEL_ID,
            "system": None,
            "prompt": PROMPT,
            "temperature": 0.0,
            "max_tokens": 24,
        }
    ]


def test_a_failed_model_execution_is_reported_without_inventing_an_answer() -> None:
    runtime, conversation, decisions, executor = _composed()
    executor._client = _ScriptedClient(  # scripted transport
        error=ProviderError("OpenAI-compatible request failed: Connection refused")
    )
    revision = _create_session(runtime)

    result = execute_conversational_turn(
        conversation=conversation,
        decisions=decisions,
        executor=executor,
        turn=_turn(expected_session_revision=revision),
    )

    assert result.execution.status is ModelExecutionStatus.FAILED
    assert result.execution.error is not None
    assert result.execution.error.code is ModelExecutionErrorCode.PROVIDER_FAILURE
    assert result.text is None
    assert result.response.message.content == (
        "The request was routed through the canonical application boundary."
    )
    # The canonical turn is still committed: a model failure never discards it.
    assert runtime.session_store.load(SESSION_ID).revision == revision + 1


def test_a_turn_without_a_canonical_decision_fails_closed() -> None:
    runtime, conversation, _, executor = _composed()
    revision = _create_session(runtime)

    with pytest.raises(ModelExecutionError) as error:
        execute_conversational_turn(
            conversation=conversation,
            decisions=InMemoryOrchestrationDecisionRepository(),
            executor=executor,
            turn=_turn(expected_session_revision=revision),
        )

    assert error.value.code == "CANONICAL_DECISION_UNAVAILABLE"
    assert executor.requests == []


@pytest.mark.parametrize(
    "collaborator",
    ["conversation", "decisions", "executor", "turn"],
)
def test_the_turn_driver_rejects_a_non_canonical_collaborator(
    collaborator: str,
) -> None:
    runtime, conversation, decisions, executor = _composed()
    revision = _create_session(runtime)
    arguments: dict[str, Any] = {
        "conversation": conversation,
        "decisions": decisions,
        "executor": executor,
        "turn": _turn(expected_session_revision=revision),
    }
    arguments[collaborator] = object()

    with pytest.raises(TypeError):
        execute_conversational_turn(**arguments)


def test_a_malformed_turn_contract_fails_closed_at_construction() -> None:
    with pytest.raises((TypeError, ValueError)):
        ModelTurnRequest(
            session_id=SESSION_ID,
            user_message_id=USER_MESSAGE_ID,
            content="   ",
            user_created_at=USER_CREATED_AT,
            request_id=REQUEST_ID,
            expected_session_revision=1,
            assistant_message_id=ASSISTANT_MESSAGE_ID,
            assistant_created_at=ASSISTANT_CREATED_AT,
        )


def test_the_turn_driver_uses_the_composed_seam_from_the_public_composition() -> None:
    """The public composition produces the seam the driver accepts."""

    runtime = build_local_application_runtime()
    graph = build_local_model_execution(
        provider_registry=runtime.container.get_service("provider.registry"),
        model_ids=(MODEL_ID,),
        client=_ScriptedClient(),
    )

    assert isinstance(graph.executor, CanonicalModelExecutor)
    assert graph.provider_spec.id == "cmmchat-router"
