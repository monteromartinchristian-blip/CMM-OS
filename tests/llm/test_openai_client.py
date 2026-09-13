from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from kernel.llm.clients.openai_client import OpenAIClient
from kernel.llm.clients.openai_compatible_client import (
    OpenAICompatibleClient,
)
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


# OpenAICompatibleClient.list_models: administrative /models discovery.


class DummyModelsNamespace:
    def __init__(self, sdk: DummyModelListSDK, response: Any) -> None:
        self._sdk = sdk
        self._response = response

    def list(self) -> Any:
        self._sdk.calls.append("models.list")
        return self._response


class DummyCompletionsSentinel:
    def __init__(self, sdk: DummyModelListSDK) -> None:
        self._sdk = sdk

    def create(self, **kwargs: Any) -> Any:
        self._sdk.calls.append("chat.completions.create")
        raise AssertionError(
            "model discovery must never perform an inference request"
        )


class DummyModelListSDK:
    def __init__(self, response: Any) -> None:
        self.calls: list[str] = []
        self.models = DummyModelsNamespace(self, response)
        self.chat = SimpleNamespace(
            completions=DummyCompletionsSentinel(self),
        )


def test_compatible_list_models_returns_ids_in_provider_order() -> None:
    response = SimpleNamespace(
        data=[
            SimpleNamespace(id="model-a", object="model"),
            SimpleNamespace(id="model-b", object="model"),
        ],
    )
    sdk = DummyModelListSDK(response)
    client = OpenAICompatibleClient(client=sdk)

    assert client.list_models() == ("model-a", "model-b")
    assert sdk.calls == ["models.list"]


def test_compatible_list_models_never_calls_inference() -> None:
    response = SimpleNamespace(
        data=[SimpleNamespace(id="model-a", object="model")],
    )
    sdk = DummyModelListSDK(response)

    OpenAICompatibleClient(client=sdk).list_models()

    assert "chat.completions.create" not in sdk.calls


def test_compatible_list_models_rejects_non_list_data() -> None:
    response = SimpleNamespace(data="not-a-list")
    sdk = DummyModelListSDK(response)

    with pytest.raises(ProviderError, match="data"):
        OpenAICompatibleClient(client=sdk).list_models()


def test_compatible_list_models_rejects_item_without_string_id() -> None:
    response = SimpleNamespace(
        data=[
            SimpleNamespace(id="model-a", object="model"),
            SimpleNamespace(id=None, object="model"),
        ],
    )
    sdk = DummyModelListSDK(response)

    with pytest.raises(ProviderError, match="string id"):
        OpenAICompatibleClient(client=sdk).list_models()


def test_compatible_list_models_rejects_duplicate_ids() -> None:
    response = SimpleNamespace(
        data=[
            SimpleNamespace(id="model-a", object="model"),
            SimpleNamespace(id="model-a", object="model"),
        ],
    )
    sdk = DummyModelListSDK(response)

    with pytest.raises(ProviderError, match="duplicate"):
        OpenAICompatibleClient(client=sdk).list_models()
