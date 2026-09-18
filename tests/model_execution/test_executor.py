"""CMMChat Wave E0 — deterministic tests of the canonical model execution seam.

Every test here is a double-based test: no live inference, no network and no
credential is required.  The seam is exercised over the *real* canonical
`ModelRouter`, `ProviderRegistry`, `ModelCatalog` and `ProviderFactory`; only the
transport client — the canonical factory's own documented injection point — is
scripted.

The claims pinned here are:

* the seam validates its canonical collaborators at construction and reuses them
  instead of duplicating any authority;
* the canonical request is mapped to the canonical `LLMRequest` faithfully;
* the canonical `LLMResponse` is normalized into the seam's result;
* every failure path (non-executable route, no model, provider refusal, transport
  failure, malformed response, unexpected defect) becomes a normalized, safe,
  secret-free failure instead of an exception.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from cmm.model_execution.contracts import (
    ModelExecutionErrorCode,
    ModelExecutionParameters,
    ModelExecutionRequest,
    ModelExecutionStatus,
)
from cmm.model_execution.executor import CanonicalModelExecutor
from cmm.orchestration.contracts import (
    ExecutionRoute,
    IntentKind,
    OrchestrationChannel,
    OrchestrationDecisionRecord,
    PolicyDisposition,
)
from kernel.llm.exceptions import ProviderError
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_router import ModelRouter, RoutingDecision
from kernel.llm.model_selection import ModelRequirements
from kernel.llm.openai_compatible_provider import OpenAICompatibleProvider
from kernel.llm.provider import LLMProvider
from kernel.llm.provider_factory import ProviderFactory
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

PROVIDER_ID = "cmmchat-router"
MODEL_ID = "chatgpt/chatgpt-web/medium"
REQUEST_ID = "request-wave-e0-1"
DECISION_ID = f"orchestration-decision:{REQUEST_ID}"
PROMPT = "Reply with exactly: CMM_OS_ROUTER_CANARY_OK"
BEARER_ENV = "CMM_ROUTER_TOKEN"
BASE_URL = "http://127.0.0.1:8790/v1"


class _ScriptedClient:
    """The canonical factory's injected transport client, scripted per test."""

    def __init__(
        self, *, result: Any = None, error: BaseException | None = None
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self._result = result if result is not None else ("ok", 1, 1, "stop")
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


class _RecordingModelRouter(ModelRouter):
    """The canonical router, recording the decision it really produced."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.decisions: list[RoutingDecision] = []

    def decide(self, requirements: ModelRequirements, **kwargs: Any) -> RoutingDecision:
        decision = super().decide(requirements, **kwargs)
        self.decisions.append(decision)
        return decision


class _RecordingProviderFactory(ProviderFactory):
    """The canonical factory, recording the collaborators it was given."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def create_from_decision(
        self, decision: RoutingDecision, **kwargs: Any
    ) -> LLMProvider:
        provider = super().create_from_decision(decision, **kwargs)
        self.calls.append(
            {"decision": decision, "kwargs": kwargs, "provider": provider}
        )
        return provider


class _Lookalike:
    """A duck-typed object that must never claim a canonical collaborator role."""

    def decide(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a lookalike router must never be used")

    def create_from_decision(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a lookalike factory must never be used")

    def get(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a lookalike registry or catalog must never be used")

    def register(self, *args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a lookalike registry or catalog must never be used")


def _record(
    *, route: ExecutionRoute = ExecutionRoute.DIRECT_RESPONSE
) -> OrchestrationDecisionRecord:
    return OrchestrationDecisionRecord(
        decision_id=DECISION_ID,
        request_id=REQUEST_ID,
        channel=OrchestrationChannel.CONVERSATION,
        intent=IntentKind.QUESTION,
        execution_route=route,
        policy_disposition=PolicyDisposition.ALLOW_ROUTE,
        session_id="session-wave-e0-1",
        occurred_at=datetime(2026, 9, 19, 10, 0, 0, tzinfo=timezone.utc),
    )


def _request(
    *,
    route: ExecutionRoute = ExecutionRoute.DIRECT_RESPONSE,
    prompt: str = PROMPT,
    parameters: ModelExecutionParameters | None = None,
) -> ModelExecutionRequest:
    return ModelExecutionRequest.from_decision(
        _record(route=route),
        prompt=prompt,
        requirements=_requirements(),
        parameters=parameters,
    )


def _requirements() -> ModelRequirements:
    return ModelRequirements(minimum_context_window=1, allowed_providers=(PROVIDER_ID,))


def _registry(
    *, enabled: bool = True, api_style: str = "chat_completions"
) -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register(
        ProviderSpec(
            id=PROVIDER_ID,
            provider_type="local",
            api_style=api_style,  # type: ignore[arg-type]
            api_key_env=BEARER_ENV,
            base_url=BASE_URL,
            enabled=enabled,
        )
    )
    return registry


def _catalog(
    registry: ProviderRegistry, *, models: tuple[str, ...] = (MODEL_ID,)
) -> ModelCatalog:
    catalog = ModelCatalog(registry)
    for model_id in models:
        catalog.register(
            ModelSpec(id=model_id, provider_id=PROVIDER_ID, context_window=32000)
        )
    return catalog


def _seam(
    *,
    client: Any | None = None,
    registry: ProviderRegistry | None = None,
    models: tuple[str, ...] = (MODEL_ID,),
    enabled: bool = True,
    api_style: str = "chat_completions",
) -> tuple[
    CanonicalModelExecutor,
    _RecordingModelRouter,
    _RecordingProviderFactory,
    Any,
    ModelCatalog,
    ProviderRegistry,
]:
    """Build the seam over the real canonical authorities and a scripted client."""

    registry = registry or _registry(enabled=enabled, api_style=api_style)
    catalog = _catalog(registry, models=models)
    router = _RecordingModelRouter(provider_registry=registry, model_catalog=catalog)
    factory = _RecordingProviderFactory()
    transport = client or _ScriptedClient(
        result=("CMM_OS_ROUTER_CANARY_OK", 9, 3, "stop")
    )
    executor = CanonicalModelExecutor(
        model_router=router,
        provider_factory=factory,
        provider_registry=registry,
        model_catalog=catalog,
        client=transport,
    )
    return executor, router, factory, transport, catalog, registry


# ── Canonical collaborator reuse ─────────────────────────────────────────────


def test_the_seam_reuses_the_canonical_model_router() -> None:
    executor, router, _, _, _, _ = _seam()

    result = executor.execute(_request())

    assert len(router.decisions) == 1
    assert router.decisions[0].status == "selected"
    assert result.routing_decision_id == router.decisions[0].id


@pytest.mark.parametrize(
    "collaborator",
    ["model_router", "provider_factory", "provider_registry", "model_catalog"],
)
def test_the_seam_rejects_a_lookalike_collaborator(collaborator: str) -> None:
    """Identity is not authority: only the canonical classes are accepted."""

    registry = _registry()
    catalog = _catalog(registry)
    arguments: dict[str, Any] = {
        "model_router": _RecordingModelRouter(
            provider_registry=registry, model_catalog=catalog
        ),
        "provider_factory": _RecordingProviderFactory(),
        "provider_registry": registry,
        "model_catalog": catalog,
        "client": None,
    }
    arguments[collaborator] = _Lookalike()

    with pytest.raises(TypeError):
        CanonicalModelExecutor(**arguments)


def test_the_seam_rejects_a_catalog_bound_to_another_registry() -> None:
    _, _, _, _, catalog, registry = _seam()
    other_registry = _registry()
    other_catalog = _catalog(other_registry)

    assert catalog.provider_registry is registry
    with pytest.raises(TypeError):
        CanonicalModelExecutor(
            model_router=_RecordingModelRouter(
                provider_registry=other_registry, model_catalog=other_catalog
            ),
            provider_factory=_RecordingProviderFactory(),
            provider_registry=other_registry,
            model_catalog=catalog,
        )


def test_the_seam_delegates_provider_construction_to_the_canonical_factory() -> None:
    executor, _, factory, _, catalog, registry = _seam()

    result = executor.execute(_request())

    assert len(factory.calls) == 1
    call = factory.calls[0]
    assert call["kwargs"]["provider_registry"] is registry
    assert call["kwargs"]["model_catalog"] is catalog
    provider = call["provider"]
    assert isinstance(provider, OpenAICompatibleProvider)
    assert isinstance(provider, LLMProvider)
    assert provider.provider_id == PROVIDER_ID
    assert provider.model == MODEL_ID
    assert result.provider_id == PROVIDER_ID
    assert result.model_id == MODEL_ID


def test_execute_rejects_a_non_request_at_the_python_boundary() -> None:
    executor, _, _, _, _, _ = _seam()

    with pytest.raises(TypeError):
        executor.execute("Reply with exactly: CMM_OS_ROUTER_CANARY_OK")  # type: ignore[arg-type]


# ── Normalized request and response mapping ──────────────────────────────────


def test_the_seam_maps_the_canonical_request_to_the_canonical_llm_request() -> None:
    executor, _, _, transport, _, _ = _seam()
    request = _request(
        parameters=ModelExecutionParameters(temperature=0.25, max_tokens=32)
    )

    executor.execute(request)

    assert transport.calls == [
        {
            "model": MODEL_ID,
            "system": None,
            "prompt": PROMPT,
            "temperature": 0.25,
            "max_tokens": 32,
        }
    ]


def test_the_seam_normalizes_the_canonical_provider_response() -> None:
    executor, _, _, _, _, _ = _seam(
        client=_ScriptedClient(result=("CMM_OS_ROUTER_CANARY_OK", 11, 5, "stop"))
    )

    result = executor.execute(_request())

    assert result.status is ModelExecutionStatus.SUCCEEDED
    assert result.is_successful is True
    assert result.text == "CMM_OS_ROUTER_CANARY_OK"
    assert result.provider_id == PROVIDER_ID
    assert result.model_id == MODEL_ID
    assert result.usage_prompt_tokens == 11
    assert result.usage_completion_tokens == 5
    assert result.total_tokens == 16
    assert result.finish_reason == "stop"
    assert result.error is None
    assert result.request_id == REQUEST_ID
    assert result.decision_id == DECISION_ID


# ── Normalized failures ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "route",
    [
        ExecutionRoute.OPERATION,
        ExecutionRoute.WORKFLOW,
        ExecutionRoute.AUTONOMOUS_AGENT,
        ExecutionRoute.HUMAN_ESCALATION,
        ExecutionRoute.NONE,
    ],
)
def test_a_non_executable_route_fails_closed_without_reaching_a_model(
    route: ExecutionRoute,
) -> None:
    executor, router, factory, transport, _, _ = _seam()

    result = executor.execute(_request(route=route))

    assert result.status is ModelExecutionStatus.FAILED
    assert result.error is not None
    assert result.error.code is ModelExecutionErrorCode.ROUTE_NOT_EXECUTABLE
    assert router.decisions == []
    assert factory.calls == []
    assert transport.calls == []


def test_no_matching_model_fails_closed_as_model_unavailable() -> None:
    executor, _, factory, transport, _, _ = _seam(models=())

    result = executor.execute(_request())

    assert result.error is not None
    assert result.error.code is ModelExecutionErrorCode.MODEL_UNAVAILABLE
    assert result.error.retryable is False
    assert factory.calls == []
    assert transport.calls == []


def test_an_unpublished_provider_model_fails_closed_as_model_unavailable() -> None:
    executor, _, factory, transport, _, _ = _seam()

    result = executor.execute(
        ModelExecutionRequest.from_decision(
            _record(),
            prompt=PROMPT,
            requirements=ModelRequirements(
                minimum_context_window=1, allowed_providers=("some-other-provider",)
            ),
        )
    )

    assert result.error is not None
    assert result.error.code is ModelExecutionErrorCode.MODEL_UNAVAILABLE
    assert factory.calls == []
    assert transport.calls == []


def test_a_provider_the_canonical_factory_refuses_fails_closed_as_unavailable() -> None:
    executor, _, transport, _, _, _ = _seam(api_style="responses")

    result = executor.execute(_request())

    assert result.error is not None
    assert result.error.code is ModelExecutionErrorCode.PROVIDER_UNAVAILABLE
    assert result.error.retryable is True
    assert transport.calls == []


def test_an_unreachable_router_becomes_a_safe_normalized_failure() -> None:
    executor, _, _, _, _, _ = _seam(
        client=_ScriptedClient(
            error=ProviderError("OpenAI-compatible request failed: Connection refused")
        )
    )

    result = executor.execute(_request())

    assert result.status is ModelExecutionStatus.FAILED
    assert result.text is None
    assert result.error is not None
    assert result.error.code is ModelExecutionErrorCode.PROVIDER_FAILURE
    assert result.error.retryable is True
    assert result.error.message == "The model provider failed to complete the request"
    assert "connection refused" not in repr(result.to_dict()).lower()


def test_a_malformed_provider_response_fails_closed_as_invalid() -> None:
    executor, _, _, _, _, _ = _seam(client=_ScriptedClient(result=(None, 0, 0, "stop")))

    result = executor.execute(_request())

    assert result.error is not None
    assert result.error.code is ModelExecutionErrorCode.PROVIDER_RESPONSE_INVALID
    assert result.text is None


@pytest.mark.parametrize("content", ["", "   ", None, 42])
def test_an_empty_or_non_textual_completion_fails_closed_as_invalid(
    content: object,
) -> None:
    executor, _, _, _, _, _ = _seam(
        client=_ScriptedClient(result=(content, 0, 0, "stop"))
    )

    result = executor.execute(_request())

    assert result.error is not None
    assert result.error.code is ModelExecutionErrorCode.PROVIDER_RESPONSE_INVALID


def test_an_unexpected_runtime_defect_fails_closed_without_leaking_its_text() -> None:
    executor, _, _, _, _, _ = _seam(
        client=_ScriptedClient(error=RuntimeError("boom: /Users/someone/private/path"))
    )

    result = executor.execute(_request())

    assert result.error is not None
    assert result.error.code is ModelExecutionErrorCode.PROVIDER_FAILURE
    serialized = repr(result.to_dict())
    assert "boom" not in serialized
    assert "/Users/someone" not in serialized


def test_no_secret_value_can_surface_through_a_normalized_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(BEARER_ENV, "secret-bearer-value")
    executor, _, _, _, _, _ = _seam(
        client=_ScriptedClient(
            error=ProviderError("401 Unauthorized: bearer secret-bearer-value rejected")
        )
    )

    result = executor.execute(_request())

    serialized = repr(result.to_dict())
    assert result.error is not None
    assert "secret-bearer-value" not in serialized
    assert "bearer" not in serialized.lower()
