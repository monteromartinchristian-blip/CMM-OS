from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from kernel.llm.clients.openai_compatible_client import (
    OpenAICompatibleClient,
)
from kernel.llm.exceptions import ProviderError
from kernel.llm.models import LLMRequest, LLMResponse
from kernel.llm.openai_compatible_provider import (
    OpenAICompatibleProvider,
)


class DummyCompatibleClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        *,
        model: str,
        system: str | None,
        prompt: str,
        temperature: float,
        max_tokens: int | None,
    ) -> tuple[str, int, int, str]:
        self.calls.append(
            {
                "model": model,
                "system": system,
                "prompt": prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return "generated", 11, 5, "stop"


def test_provider_generates_normalized_response() -> None:
    client = DummyCompatibleClient()
    provider = OpenAICompatibleProvider(
        provider_id=" Example ",
        client=client,
        model="model-a",
    )

    response = provider.generate(
        LLMRequest(
            prompt="hello",
            system_prompt="system",
            temperature=0.2,
            metadata={"max_tokens": 64},
        )
    )

    assert isinstance(response, LLMResponse)
    assert response.content == "generated"
    assert response.model == "model-a"
    assert response.total_tokens == 16
    assert response.metadata["provider_id"] == "example"
    assert response.metadata["api_style"] == "chat_completions"
    assert client.calls[0]["max_tokens"] == 64


def test_provider_rejects_empty_prompt() -> None:
    provider = OpenAICompatibleProvider(
        provider_id="example",
        client=DummyCompatibleClient(),
        model="model-a",
    )

    with pytest.raises(ProviderError, match="Prompt cannot be empty"):
        provider.generate(LLMRequest(prompt="   "))


def test_provider_rejects_invalid_max_tokens() -> None:
    provider = OpenAICompatibleProvider(
        provider_id="example",
        client=DummyCompatibleClient(),
        model="model-a",
    )

    with pytest.raises(ProviderError, match="max_tokens must be an integer"):
        provider.generate(
            LLMRequest(
                prompt="hello",
                metadata={"max_tokens": "invalid"},
            )
        )


def test_client_normalizes_chat_completions_response() -> None:
    calls: list[dict[str, Any]] = []

    class DummyCompletions:
        def create(self, **kwargs: Any) -> Any:
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="answer"),
                        finish_reason="stop",
                    )
                ],
                usage=SimpleNamespace(
                    prompt_tokens=7,
                    completion_tokens=3,
                ),
            )

    sdk_client = SimpleNamespace(
        chat=SimpleNamespace(completions=DummyCompletions())
    )
    client = OpenAICompatibleClient(client=sdk_client)

    result = client.generate(
        model="model-a",
        system="system",
        prompt="question",
        temperature=0.1,
        max_tokens=32,
    )

    assert result == ("answer", 7, 3, "stop")
    assert calls[0]["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "question"},
    ]
    assert calls[0]["max_tokens"] == 32


def test_client_rejects_response_without_choices() -> None:
    class DummyCompletions:
        def create(self, **kwargs: Any) -> Any:
            return SimpleNamespace(choices=[])

    sdk_client = SimpleNamespace(
        chat=SimpleNamespace(completions=DummyCompletions())
    )

    with pytest.raises(ProviderError, match="had no choices"):
        OpenAICompatibleClient(client=sdk_client).generate(
            model="model-a",
            system=None,
            prompt="question",
        )
