from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from kernel.llm.clients.openai_client import OpenAIClient
from kernel.llm.exceptions import ProviderError


class DummyResponses:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.response


class DummySDKClient:
    def __init__(self, response: Any) -> None:
        self.responses = DummyResponses(response)


def test_generate_returns_content_and_usage() -> None:
    response = SimpleNamespace(
        output_text="hello",
        usage=SimpleNamespace(input_tokens=4, output_tokens=3),
        status="completed",
    )
    sdk = DummySDKClient(response)
    client = OpenAIClient(client=sdk)

    result = client.generate(
        model="gpt-test",
        system="system",
        prompt="prompt",
        temperature=0.0,
        max_output_tokens=32,
    )

    assert result == ("hello", 4, 3, "completed")
    assert sdk.responses.calls[0]["model"] == "gpt-test"
    assert sdk.responses.calls[0]["max_output_tokens"] == 32


def test_generate_rejects_empty_response() -> None:
    response = SimpleNamespace(
        output_text=" ",
        usage=None,
        status="completed",
    )
    client = OpenAIClient(client=DummySDKClient(response))

    with pytest.raises(ProviderError, match="response was empty"):
        client.generate(
            model="gpt-test",
            system=None,
            prompt="prompt",
        )


def test_generate_maps_quota_errors() -> None:
    class FailingResponses:
        def create(self, **kwargs: Any) -> Any:
            raise RuntimeError("insufficient_quota")

    sdk = SimpleNamespace(responses=FailingResponses())
    client = OpenAIClient(client=sdk)

    with pytest.raises(ProviderError, match="quota is exhausted"):
        client.generate(
            model="gpt-test",
            system=None,
            prompt="prompt",
        )
