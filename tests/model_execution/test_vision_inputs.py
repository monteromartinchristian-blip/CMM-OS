"""Wave E canonical reconciliation — visual inputs on the execution seam.

Vision is a *declared capability*, not a product assumption: the seam accepts
canonical :class:`~kernel.llm.models.ImageInput` values only when the resolved
model's catalog entry declares ``vision``, serializes them as provider-neutral
multimodal content parts, and fails closed — before any provider call — when
the model cannot see.  These tests pin that contract with a scripted transport
client, exactly like the rest of the seam's suite: no live inference, no
network, no credential.
"""

from __future__ import annotations

import base64
from typing import Any

import pytest

from cmm.model_execution.composition import (
    LOCAL_RUNTIME_VISION_MODEL_IDS_ENV,
    register_local_runtime,
)
from cmm.model_execution.errors import ModelExecutionError
from cmm.model_execution.executor import CanonicalModelExecutor
from kernel.llm.capabilities import ModelCapabilities
from kernel.llm.model_catalog import ModelCatalog, ModelSpec
from kernel.llm.model_router import ModelRouter
from kernel.llm.models import ImageInput
from kernel.llm.provider_factory import ProviderFactory
from kernel.llm.provider_registry import ProviderRegistry, ProviderSpec

ROUTER = "cmmchat-router"
PNG = b"\x89PNG\r\n\x1a\n" + b"vision-fixture-bytes"


class _StreamClient:
    """Scripted transport client recording the exact provider messages."""

    def __init__(self, *, deltas: tuple[str, ...] = ("seen",)) -> None:
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
) -> CanonicalModelExecutor:
    """Build the executor over fresh canonical authorities, one vision model."""

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
            id="vision-model",
            provider_id=spec.id,
            context_window=32_000,
            capabilities=capabilities or ModelCapabilities(),
        )
    )
    return CanonicalModelExecutor(
        model_router=ModelRouter(provider_registry=registry, model_catalog=catalog),
        provider_factory=ProviderFactory(),
        provider_registry=registry,
        model_catalog=catalog,
        client=client,
    )


# ── the canonical image value ────────────────────────────────────────────────


def test_image_input_normalizes_the_media_type_and_keeps_the_bytes() -> None:
    image = ImageInput(media_type="image/png; charset=binary", data=PNG)

    assert image.media_type == "image/png"
    assert image.data == PNG


@pytest.mark.parametrize("media_type", ["application/pdf", "text/plain", "image"])
def test_image_input_refuses_a_non_image_media_type(media_type: str) -> None:
    with pytest.raises(ValueError):
        ImageInput(media_type=media_type, data=PNG)


@pytest.mark.parametrize("data", [b"", "not-bytes", None])
def test_image_input_refuses_empty_or_non_byte_payloads(data: Any) -> None:
    with pytest.raises(ValueError):
        ImageInput(media_type="image/png", data=data)


# ── the seam's vision gate ───────────────────────────────────────────────────


def test_images_against_a_non_vision_model_fail_closed_before_any_call() -> None:
    client = _StreamClient()
    executor = _compose(client=client)
    resolved = executor.resolve_chat("vision-model")

    with pytest.raises(ModelExecutionError) as raised:
        list(executor.stream(resolved, prompt="what is in the image?",
                             images=(ImageInput(media_type="image/png", data=PNG),)))

    assert raised.value.code == "CHAT_PROMPT_INVALID"
    assert client.stream_calls == []


def test_images_reach_a_vision_model_as_multimodal_content_parts() -> None:
    client = _StreamClient()
    executor = _compose(
        capabilities=ModelCapabilities(vision=True), client=client
    )
    resolved = executor.resolve_chat("vision-model")

    deltas = list(
        executor.stream(
            resolved,
            prompt="what is in the image?",
            history=(("user", "earlier"), ("assistant", "reply")),
            images=(ImageInput(media_type="image/png", data=PNG),),
        )
    )

    assert "".join(deltas) == "seen"
    messages = client.stream_calls[0]["messages"]
    # The transcript is preserved verbatim; only the current user turn becomes
    # a multimodal part list.
    assert messages[:-1] == [
        {"role": "user", "content": "earlier"},
        {"role": "assistant", "content": "reply"},
    ]
    content = messages[-1]["content"]
    assert content[0] == {
        "type": "text",
        "text": "what is in the image?",
    }
    assert content[1] == {
        "type": "image_url",
        "image_url": {
            "url": f"data:image/png;base64,{base64.b64encode(PNG).decode('ascii')}"
        },
    }


def test_a_vision_model_without_images_keeps_the_plain_string_transcript() -> None:
    client = _StreamClient()
    executor = _compose(capabilities=ModelCapabilities(vision=True), client=client)
    resolved = executor.resolve_chat("vision-model")

    list(executor.stream(resolved, prompt="plain"))

    assert client.stream_calls[0]["messages"] == [
        {"role": "user", "content": "plain"}
    ]


# ── declaring vision on the local runtime lane ───────────────────────────────


def test_local_runtime_vision_ids_grant_vision_only_to_listed_models(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LOCAL_RUNTIME_VISION_MODEL_IDS_ENV, "Qwen2-VL-2B")
    registry = ProviderRegistry()
    catalog = ModelCatalog(registry)

    _, models = register_local_runtime(
        provider_registry=registry,
        model_catalog=catalog,
        model_ids=("Qwen2-VL-2B", "MiniCPM5-2B"),
    )

    # Canonical model identities are case-normalized by the catalog.
    declared = {model.id: model.capabilities.vision for model in models}
    assert declared == {"qwen2-vl-2b": True, "minicpm5-2b": False}


def test_local_runtime_models_are_text_only_without_vision_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(LOCAL_RUNTIME_VISION_MODEL_IDS_ENV, raising=False)
    registry = ProviderRegistry()
    catalog = ModelCatalog(registry)

    _, models = register_local_runtime(
        provider_registry=registry,
        model_catalog=catalog,
        model_ids=("Qwen2-VL-2B",),
    )

    assert models[0].capabilities.vision is False
