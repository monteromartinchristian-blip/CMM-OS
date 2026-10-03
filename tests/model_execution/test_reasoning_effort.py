"""Wave E canonical reconciliation — reasoning effort on the execution seam.

An effort level is a *declared capability with a wire path*, never a product
assumption: the model must declare the level, the provider must be able to put
it on the wire, and a level that fails either gate is refused before any
provider call.  A level that passes both is transmitted verbatim, and the seam
reports what it requested plus what the runtime says it applied — which, for
runtimes that stay silent, is honestly "unknown".
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from cmm.model_execution.composition import (
    LOCAL_RUNTIME_PROVIDER_ID,
    register_local_runtime,
)
from cmm.model_execution.contracts import ChatStreamFacts
from cmm.model_execution.errors import ModelExecutionError
from cmm.model_execution.executor import CanonicalModelExecutor
from kernel.llm.capabilities import ModelCapabilities, ReasoningEffort
from kernel.llm.clients.openai_compatible_client import REASONING_EFFORT_MAP_ENV
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_router import ModelRouter
from kernel.llm.provider_factory import ProviderFactory
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

ROUTER = "cmmchat-router"
THINKING_FRAGMENT = {"chat_template_kwargs": {"enable_thinking": True}}


class _StreamClient:
    """Scripted transport client recording the exact wire parameters."""

    def __init__(self, *, deltas: tuple[str, ...] = ("thought",)) -> None:
        self.deltas = deltas
        self.stream_calls: list[dict[str, Any]] = []

    def generate(self, **_: Any) -> Any:  # pragma: no cover - unused here
        raise AssertionError("generate must not be used by stream")

    def stream_chat(self, **parameters: Any) -> Any:
        self.stream_calls.append(parameters)
        yield from self.deltas


def _compose(
    *,
    capabilities: ModelCapabilities | None = None,
    client: Any | None = None,
    effort_map: dict[ReasoningEffort, dict[str, Any]] | None = None,
) -> CanonicalModelExecutor:
    """Build the executor over fresh canonical authorities, one model."""

    spec = ProviderSpec(
        id=ROUTER,
        provider_type="local",
        api_style="chat_completions",
        base_url="http://127.0.0.1:8790/v1",
        availability="available",
    )
    registry = ProviderRegistry()
    registry.register(spec)
    catalog = ModelCatalog(registry)
    catalog.register(
        ModelSpec(
            id="thinker",
            provider_id=spec.id,
            context_window=32_000,
            capabilities=capabilities or ModelCapabilities(),
        )
    )
    provider_factory = ProviderFactory()
    if effort_map is not None:
        original = provider_factory.create

        def _with_map(**parameters: Any) -> Any:
            provider = original(**parameters)
            provider.reasoning_effort_map = {"thinker": dict(effort_map)}
            return provider

        provider_factory.create = _with_map  # type: ignore[method-assign]
    return CanonicalModelExecutor(
        model_router=ModelRouter(provider_registry=registry, model_catalog=catalog),
        provider_factory=provider_factory,
        provider_registry=registry,
        model_catalog=catalog,
        client=client,
    )


def test_an_undeclared_effort_is_refused_before_any_provider_call() -> None:
    client = _StreamClient()
    executor = _compose(client=client)
    resolved = executor.resolve_chat("thinker")

    with pytest.raises(ModelExecutionError) as raised:
        list(executor.stream(resolved, prompt="x", reasoning_effort="high"))

    assert raised.value.code == "UNSUPPORTED_REASONING_EFFORT"
    assert client.stream_calls == []


def test_an_invented_effort_level_is_refused() -> None:
    executor = _compose()
    resolved = executor.resolve_chat("thinker")

    with pytest.raises(ModelExecutionError) as raised:
        list(executor.stream(resolved, prompt="x", reasoning_effort="ludicrous"))

    assert raised.value.code == "UNSUPPORTED_REASONING_EFFORT"


def test_a_declared_effort_without_a_wire_path_is_refused() -> None:
    client = _StreamClient()
    executor = _compose(
        capabilities=ModelCapabilities(
            reasoning=True, reasoning_efforts=(ReasoningEffort.HIGH,)
        ),
        client=client,
        effort_map={},
    )
    resolved = executor.resolve_chat("thinker")

    with pytest.raises(ModelExecutionError) as raised:
        list(executor.stream(resolved, prompt="x", reasoning_effort="high"))

    assert raised.value.code == "UNSUPPORTED_REASONING_EFFORT"
    assert client.stream_calls == []


def test_a_declared_effort_with_a_wire_path_is_transmitted_verbatim() -> None:
    client = _StreamClient()
    executor = _compose(
        capabilities=ModelCapabilities(
            reasoning=True, reasoning_efforts=(ReasoningEffort.MEDIUM,)
        ),
        client=client,
        effort_map={ReasoningEffort.MEDIUM: THINKING_FRAGMENT},
    )
    resolved = executor.resolve_chat("thinker")

    deltas = list(
        executor.stream(resolved, prompt="think hard", reasoning_effort="medium")
    )

    assert "".join(deltas) == "thought"
    assert client.stream_calls[0]["request_extras"] == THINKING_FRAGMENT


def test_the_default_effort_sends_no_wire_override() -> None:
    client = _StreamClient()
    executor = _compose(
        capabilities=ModelCapabilities(
            reasoning=True, reasoning_efforts=(ReasoningEffort.MEDIUM,)
        ),
        client=client,
        effort_map={ReasoningEffort.MEDIUM: THINKING_FRAGMENT},
    )
    resolved = executor.resolve_chat("thinker")

    list(executor.stream(resolved, prompt="plain"))

    assert client.stream_calls[0]["request_extras"] == {}


def test_the_facts_sink_reports_requested_and_an_honest_unknown_effective() -> None:
    facts: list[ChatStreamFacts] = []
    executor = _compose(
        capabilities=ModelCapabilities(
            reasoning=True, reasoning_efforts=(ReasoningEffort.MEDIUM,)
        ),
        client=_StreamClient(),
        effort_map={ReasoningEffort.MEDIUM: THINKING_FRAGMENT},
    )
    resolved = executor.resolve_chat("thinker")

    list(
        executor.stream(
            resolved,
            prompt="think hard",
            reasoning_effort="medium",
            facts_sink=facts.append,
        )
    )

    assert facts == [
        ChatStreamFacts(requested_reasoning_effort="medium", effective_reasoning_effort=None)
    ]


def test_the_local_lane_declares_exactly_the_levels_it_can_transmit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        REASONING_EFFORT_MAP_ENV,
        json.dumps(
            {
                LOCAL_RUNTIME_PROVIDER_ID: {
                    "qwen3-1.7b": {"medium": THINKING_FRAGMENT}
                }
            }
        ),
    )
    registry = ProviderRegistry()
    catalog = ModelCatalog(registry)

    _, models = register_local_runtime(
        provider_registry=registry,
        model_catalog=catalog,
        model_ids=("qwen3-1.7b", "minicpm5-2b"),
    )

    declared = {model.id: model.capabilities for model in models}
    assert declared["qwen3-1.7b"].reasoning is True
    assert declared["qwen3-1.7b"].reasoning_efforts == (ReasoningEffort.MEDIUM,)
    assert declared["qwen3-1.7b"].supports_reasoning_effort(ReasoningEffort.MEDIUM)
    assert not declared["qwen3-1.7b"].supports_reasoning_effort(ReasoningEffort.HIGH)
    assert declared["minicpm5-2b"].reasoning is False
    assert declared["minicpm5-2b"].reasoning_efforts == ()


def test_max_is_a_canonical_level_and_not_a_spelling_of_extra_high() -> None:
    """``max`` is representable, and it is a different level from ``extra_high``.

    Before this, ``max`` existed nowhere in the canonical contract, so a model
    declaring it was projected onto a shorter ladder and a client could never
    select or forward it. Now both rungs exist and remain distinct.
    """

    assert ReasoningEffort("max") is ReasoningEffort.MAX
    assert ReasoningEffort.MAX != ReasoningEffort.EXTRA_HIGH
    # Declaration order is ladder order: max is the strongest rung.
    assert list(ReasoningEffort)[-1] is ReasoningEffort.MAX


def test_a_declared_max_is_transmitted_verbatim() -> None:
    """A model that declares ``max`` forwards it unchanged to the lane."""

    client = _StreamClient()
    executor = _compose(
        capabilities=ModelCapabilities(
            reasoning=True, reasoning_efforts=(ReasoningEffort.MAX,)
        ),
        client=client,
        effort_map={ReasoningEffort.MAX: THINKING_FRAGMENT},
    )
    resolved = executor.resolve_chat("thinker")

    deltas = list(executor.stream(resolved, prompt="x", reasoning_effort="max"))

    assert "".join(deltas) == "thought"
    assert client.stream_calls[0]["request_extras"] == THINKING_FRAGMENT


def test_max_is_refused_for_a_model_that_does_not_declare_it() -> None:
    """The new rung widens what can be sent, never what any one model accepts."""

    client = _StreamClient()
    executor = _compose(
        capabilities=ModelCapabilities(
            reasoning=True, reasoning_efforts=(ReasoningEffort.HIGH,)
        ),
        client=client,
        effort_map={ReasoningEffort.MAX: THINKING_FRAGMENT},
    )
    resolved = executor.resolve_chat("thinker")

    with pytest.raises(ModelExecutionError) as raised:
        list(executor.stream(resolved, prompt="x", reasoning_effort="max"))

    assert raised.value.code == "UNSUPPORTED_REASONING_EFFORT"
    assert client.stream_calls == []
