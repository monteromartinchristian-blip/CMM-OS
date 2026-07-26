from __future__ import annotations

from typing import Any

import pytest

from kernel.llm.exceptions import ProviderError
from kernel.llm.models import LLMRequest
from kernel.llm.openai_compatible_provider import (
    OpenAICompatibleProvider,
)


class DummyClient:
    def __init__(self, content: str = "generated") -> None:
        self.content = content
        self.calls: list[dict[str, Any]] = []

    def generate(
        self,
        *,
        model: str,
        system: str | None,
        prompt: str,
        temperature: float,
        max_output_tokens: int | None,
    ) -> tuple[str, int, int, str]:
        self.calls.append(
            {
                "model": model,
                "system": system,
                "prompt": prompt,
                "temperature": temperature,
                "max_output_tokens": max_output_tokens,
            }
        )
        return self.content, 10, 5, "stop"


def test_generate_returns_compatible_response() -> None:
    client = DummyClient()
    provider = OpenAICompatibleProvider(
        client=client,
        model="z-ai/glm-5.2",
        source="nvidia",
    )

    response = provider.generate(
        LLMRequest(
            prompt="hello",
            system_prompt="system",
            temperature=0.1,
            metadata={"max_tokens": 128},
        )
    )

    assert response.content == "generated"
    assert response.model == "z-ai/glm-5.2"
    assert response.usage_prompt_tokens == 10
    assert response.usage_completion_tokens == 5
    assert response.metadata["source"] == "nvidia"
    assert client.calls[0]["max_output_tokens"] == 128


def test_generate_rejects_empty_prompt() -> None:
    provider = OpenAICompatibleProvider(client=DummyClient())

    with pytest.raises(ProviderError, match="Prompt cannot be empty"):
        provider.generate(LLMRequest(prompt="   "))


class FailingCompletions:
    def create(self, **kwargs: Any) -> None:
        raise RuntimeError("Error code: 429 - Too Many Requests")


class FailingChat:
    def __init__(self) -> None:
        self.completions = FailingCompletions()


class FailingSDKClient:
    def __init__(self) -> None:
        self.chat = FailingChat()


def test_client_translates_rate_limit_error() -> None:
    from kernel.llm.clients.openai_compatible_client import (
        OpenAICompatibleClient,
    )

    client = OpenAICompatibleClient(client=FailingSDKClient())

    with pytest.raises(
        ProviderError,
        match="OpenAI-compatible rate limit exceeded",
    ):
        client.generate(
            model="z-ai/glm-5.2",
            system=None,
            prompt="hello",
        )
