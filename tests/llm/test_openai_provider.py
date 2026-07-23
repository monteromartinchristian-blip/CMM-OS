from __future__ import annotations

from typing import Any

import pytest

from kernel.llm.exceptions import ProviderError
from kernel.llm.models import LLMRequest, LLMResponse
from kernel.llm.openai_provider import OpenAIProvider


class DummyClient:
    def __init__(self) -> None:
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
        return "generated", 12, 7, "completed"


def test_generate_returns_llm_response() -> None:
    client = DummyClient()
    provider = OpenAIProvider(client=client, model="gpt-test")

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
    assert response.model == "gpt-test"
    assert response.usage_prompt_tokens == 12
    assert response.usage_completion_tokens == 7
    assert response.metadata["source"] == "openai"
    assert client.calls[0]["max_output_tokens"] == 64


def test_generate_rejects_empty_prompt() -> None:
    provider = OpenAIProvider(client=DummyClient())

    with pytest.raises(ProviderError, match="Prompt cannot be empty"):
        provider.generate(LLMRequest(prompt="   "))


def test_generate_rejects_invalid_max_tokens() -> None:
    provider = OpenAIProvider(client=DummyClient())

    with pytest.raises(ProviderError, match="max_tokens must be an integer"):
        provider.generate(
            LLMRequest(prompt="hello", metadata={"max_tokens": "invalid"})
        )
