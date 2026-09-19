"""Wave E canonical reconciliation — the chat surface of the execution seam.

The obsolete Phase-10 clone exposed CMMChat's intelligence boundary through a
parallel ``ModelGateway``.  Canonically, the same surface is a *method set on
the existing seam* (:class:`CanonicalModelExecutor`): a normalized catalog
projection, AUTO/explicit resolution through the canonical router and catalog,
and token streaming through the canonical provider abstraction.  These tests
pin that ported semantics and the guarantee that no provider detail escapes.
"""

from __future__ import annotations

import threading
from typing import Any

import pytest

from cmm.model_execution.contracts import NormalizedModel, ResolvedChatModel
from cmm.model_execution.errors import ModelExecutionError
from cmm.model_execution.executor import CanonicalModelExecutor
from kernel.llm.capabilities import ModelCapabilities
from kernel.llm.exceptions import ProviderError
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_router import ModelRouter
from kernel.llm.provider_factory import ProviderFactory
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

ROUTER = "cmmchat-router"


class _StreamClient:
    """Scripted transport client for both the generate and stream contracts."""

    def __init__(
        self,
        *,
        deltas: tuple[str, ...] = ("Ho", "la"),
        error: BaseException | None = None,
    ) -> None:
        self.deltas = deltas
        self.error = error
        self.stream_calls: list[dict[str, Any]] = []

    def generate(self, **_: Any) -> Any:  # pragma: no cover - unused here
        raise AssertionError("generate must not be used by stream")

    def stream_chat(self, **parameters: Any) -> Any:
        self.stream_calls.append(parameters)
        if self.error is not None:
            raise self.error
        yield from self.deltas


def _compose(
    *,
    models: tuple[tuple[str, dict[str, Any]], ...] = (
        ("model-one", {"availability": "available"}),
    ),
    provider: ProviderSpec | None = None,
    client: Any | None = None,
) -> CanonicalModelExecutor:
    """Build the executor over fresh canonical authorities."""

    spec = provider or ProviderSpec(
        id=ROUTER,
        provider_type="local",
        api_style="chat_completions",
        base_url="http://127.0.0.1:8790/v1",
        availability="available",
    )
    registry = ProviderRegistry()
    registry.register(spec)
    catalog = ModelCatalog(registry)
    for model_id, kwargs in models:
        catalog.register(
            ModelSpec(
                id=model_id,
                provider_id=spec.id,
                context_window=kwargs.get("context_window", 32_000),
                availability=kwargs.get("availability", "available"),
                capabilities=kwargs.get("capabilities", ModelCapabilities()),
                aliases=tuple(kwargs.get("aliases", ())),
            )
        )
    return CanonicalModelExecutor(
        model_router=ModelRouter(provider_registry=registry, model_catalog=catalog),
        provider_factory=ProviderFactory(),
        provider_registry=registry,
        model_catalog=catalog,
        client=client,
    )


# ── catalog projection ───────────────────────────────────────────────────────


def test_catalog_projects_normalized_models_from_the_canonical_catalog() -> None:
    executor = _compose(
        models=(
            (
                "provider/chatgpt-web/medium",
                {"capabilities": ModelCapabilities(reasoning=True, vision=True)},
            ),
        )
    )

    models = executor.catalog()

    assert [model.model_id for model in models] == ["provider/chatgpt-web/medium"]
    model = models[0]
    assert isinstance(model, NormalizedModel)
    assert model.display_name == "medium"
    assert model.availability == "available"
    assert model.locality == "local"
    assert model.provider_id == ROUTER
    assert model.capabilities == {
        "reasoning": True,
        "vision": True,
        "tool_calling": False,
        "structured_output": False,
    }


def test_catalog_skips_disabled_providers_and_marks_unavailable_models() -> None:
    executor = _compose(
        models=(
            ("good", {}),
            ("bad", {"availability": "unavailable"}),
        )
    )
    assert {model.model_id: model.availability for model in executor.catalog()} == {
        "good": "available",
        "bad": "unavailable",
    }

    disabled = _compose(
        provider=ProviderSpec(
            id=ROUTER,
            provider_type="remote",
            api_style="chat_completions",
            base_url="https://example.invalid/v1",
            enabled=False,
        )
    )
    assert disabled.catalog() == ()


# ── resolution ──────────────────────────────────────────────────────────────


def test_auto_selection_uses_the_canonical_router_and_reports_the_policy() -> None:
    executor = _compose()
    resolved = executor.resolve_chat(None)
    assert isinstance(resolved, ResolvedChatModel)
    assert resolved.policy == "cmm-auto"
    assert resolved.model.model_id == "model-one"

    assert executor.resolve_chat("cmm-auto").policy == "cmm-auto"
    assert executor.resolve_chat("  ").policy == "cmm-auto"


def test_auto_without_any_available_model_fails_closed() -> None:
    executor = _compose(models=(("bad", {"availability": "unavailable"}),))
    with pytest.raises(ModelExecutionError) as raised:
        executor.resolve_chat(None)
    assert raised.value.code == "NO_MODELS_AVAILABLE"
    assert "provider" not in raised.value.message.lower()


def test_explicit_selection_resolves_by_id_qualified_id_alias_and_case() -> None:
    executor = _compose(
        models=(("DeepSeek/Chat", {"aliases": ("ds",)}),),
    )
    for selection in ("deepseek/chat", f"{ROUTER}:deepseek/chat", "DS", "ds"):
        resolved = executor.resolve_chat(selection)
        assert resolved.policy == "explicit"
        assert resolved.model.model_id == "deepseek/chat"


def test_explicit_selection_of_unknown_or_unavailable_model_fails() -> None:
    executor = _compose(
        models=(("present", {}), ("gone", {"availability": "unavailable"}))
    )
    for selection in ("absent", "gone"):
        with pytest.raises(ModelExecutionError) as raised:
            executor.resolve_chat(selection)
        assert raised.value.code == "MODEL_UNAVAILABLE"
        assert selection not in raised.value.message


# ── streaming ───────────────────────────────────────────────────────────────


def test_stream_yields_normalized_deltas_and_carries_the_transcript() -> None:
    client = _StreamClient(deltas=("Ho", "la CMM"))
    executor = _compose(client=client)
    resolved = executor.resolve_chat("model-one")

    deltas = list(
        executor.stream(
            resolved,
            prompt="mundo",
            system="sys",
            history=(("user", "hola"), ("assistant", "hey")),
        )
    )

    assert "".join(deltas) == "Hola CMM"
    call = client.stream_calls[0]
    assert call["model"] == "model-one"
    assert call["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hola"},
        {"role": "assistant", "content": "hey"},
        {"role": "user", "content": "mundo"},
    ]


def test_stream_propagates_cancellation_to_the_provider() -> None:
    cancel = threading.Event()
    client = _StreamClient()
    executor = _compose(client=client)
    resolved = executor.resolve_chat(None)

    list(executor.stream(resolved, prompt="x", cancel_event=cancel))
    assert client.stream_calls[0]["cancel_event"] is cancel


def test_stream_provider_failure_is_normalized_without_provider_detail() -> None:
    client = _StreamClient(error=ProviderError("upstream sk-secret exploded"))
    executor = _compose(client=client)
    resolved = executor.resolve_chat(None)

    with pytest.raises(ModelExecutionError) as raised:
        list(executor.stream(resolved, prompt="x"))
    assert raised.value.code == "PROVIDER_FAILURE"
    assert "sk-secret" not in raised.value.message
    assert "sk-secret" not in str(raised.value)


def test_stream_refuses_a_disabled_provider_at_the_stream_boundary() -> None:
    """Streaming re-checks the provider gate; a disabled provider never streams."""

    executor = _compose(client=_StreamClient())
    disabled = ResolvedChatModel(
        model=NormalizedModel(
            model_id="model-one",
            display_name="model-one",
            provider_id=ROUTER,
            locality="local",
            availability="available",
            capabilities={},
        ),
        policy="explicit",
        spec=ModelSpec(id="model-one", provider_id=ROUTER),
        provider=ProviderSpec(
            id=ROUTER,
            provider_type="local",
            api_style="chat_completions",
            base_url="http://127.0.0.1:8790/v1",
            enabled=False,
        ),
    )
    with pytest.raises(ModelExecutionError) as raised:
        list(executor.stream(disabled, prompt="x"))
    assert raised.value.code == "PROVIDER_UNAVAILABLE"
