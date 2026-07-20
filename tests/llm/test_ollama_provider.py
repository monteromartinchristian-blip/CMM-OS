from __future__ import annotations

from typing import Any

import pytest

from kernel.llm.clients.ollama_client import OllamaClient
from kernel.llm.exceptions import ProviderError
from kernel.llm.models import LLMRequest, LLMResponse
from kernel.llm.ollama_provider import OllamaProvider


class DummyClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate(self, *, model: str, system: str | None, prompt: str, temperature: float, num_predict: int | None) -> str:
        self.calls.append(
            {
                "model": model,
                "system": system,
                "prompt": prompt,
                "temperature": temperature,
                "num_predict": num_predict,
            }
        )
        return "hello from ollama"


class TimeoutClient(DummyClient):
    def generate(self, *, model: str, system: str | None, prompt: str, temperature: float, num_predict: int | None) -> str:
        raise ProviderError("Ollama request timed out")


class UnreachableClient(DummyClient):
    def generate(self, *, model: str, system: str | None, prompt: str, temperature: float, num_predict: int | None) -> str:
        raise ProviderError("Ollama host is unreachable")


class MissingModelClient(DummyClient):
    def generate(self, *, model: str, system: str | None, prompt: str, temperature: float, num_predict: int | None) -> str:
        raise ProviderError("Ollama model not found")


class EmptyResponseClient(DummyClient):
    def generate(self, *, model: str, system: str | None, prompt: str, temperature: float, num_predict: int | None) -> str:
        return "   "


def test_provider_creation_uses_default_model() -> None:
    provider = OllamaProvider(client=DummyClient(), model="qwen3:30b-a3b")

    assert provider.model == "qwen3:30b-a3b"


def test_complete_returns_llm_response() -> None:
    client = DummyClient()
    provider = OllamaProvider(client=client)
    request = LLMRequest(prompt="hello", system_prompt="system", temperature=0.2, metadata={"max_tokens": 64})

    response = provider.complete(request)

    assert isinstance(response, LLMResponse)
    assert response.content == "hello from ollama"
    assert response.model == provider.model
    assert response.metadata["source"] == "ollama"
    assert client.calls[0]["num_predict"] == 64


def test_complete_raises_timeout_error() -> None:
    provider = OllamaProvider(client=TimeoutClient())
    request = LLMRequest(prompt="hello")

    with pytest.raises(ProviderError, match="timed out"):
        provider.complete(request)


def test_complete_raises_on_unreachable_host() -> None:
    provider = OllamaProvider(client=UnreachableClient())
    request = LLMRequest(prompt="hello")

    with pytest.raises(ProviderError, match="unreachable"):
        provider.complete(request)


def test_complete_raises_on_missing_model() -> None:
    provider = OllamaProvider(client=MissingModelClient())
    request = LLMRequest(prompt="hello")

    with pytest.raises(ProviderError, match="not found"):
        provider.complete(request)


def test_complete_raises_on_empty_response() -> None:
    provider = OllamaProvider(client=EmptyResponseClient())
    request = LLMRequest(prompt="hello")

    with pytest.raises(ProviderError, match="empty"):
        provider.complete(request)


def test_provider_uses_the_requested_model() -> None:
    client = DummyClient()
    provider = OllamaProvider(client=client, model="glm4.5")
    request = LLMRequest(prompt="hello")

    provider.complete(request)

    assert client.calls[0]["model"] == "glm4.5"


def test_provider_delegates_all_communication_to_client() -> None:
    client = DummyClient()
    provider = OllamaProvider(client=client, model="deepseek-r1")
    request = LLMRequest(prompt="hello", system_prompt="sys", temperature=0.5, metadata={"max_tokens": 32})

    provider.complete(request)

    assert client.calls[0]["system"] == "sys"
    assert client.calls[0]["prompt"] == "hello"
    assert client.calls[0]["temperature"] == 0.5
    assert client.calls[0]["num_predict"] == 32
    assert client.calls[0]["model"] == "deepseek-r1"
