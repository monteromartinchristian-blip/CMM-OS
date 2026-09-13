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


class InferenceForbidden(BaseException):
    """Raised if model discovery ever performs an inference request.

    This derives from ``BaseException`` so that ``list_models``' broad
    ``except Exception`` handler cannot convert it into a ``ProviderError``
    and thereby hide the mutation.
    """


class DummyCompletionsSentinel:
    def __init__(self, sdk: DummyModelListSDK) -> None:
        self._sdk = sdk

    def create(self, **kwargs: Any) -> Any:
        self._sdk.calls.append("chat.completions.create")
        raise InferenceForbidden(
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
    assert not any("completions" in call for call in sdk.calls)


def test_compatible_list_models_never_calls_inference() -> None:
    response = SimpleNamespace(
        data=[SimpleNamespace(id="model-a", object="model")],
    )
    sdk = DummyModelListSDK(response)

    assert OpenAICompatibleClient(client=sdk).list_models() == ("model-a",)
    assert sdk.calls == ["models.list"]
    assert not any("completions" in call for call in sdk.calls)


class DelegatingClient(OpenAICompatibleClient):
    """Mutation guard: a client whose discovery delegates to ``generate()``."""

    def list_models(self) -> tuple[str, ...]:
        self.generate(model="model-a", system=None, prompt="prompt")
        return ()


def test_compatible_list_models_inference_trap_is_not_vacuous() -> None:
    # Mutation guard: if list_models delegated to generate(), the
    # BaseException sentinel must propagate instead of being swallowed by
    # list_models' broad ``except Exception`` handler. This test is what
    # makes test_compatible_list_models_never_calls_inference meaningful.
    response = SimpleNamespace(
        data=[SimpleNamespace(id="model-a", object="model")],
    )
    sdk = DummyModelListSDK(response)

    with pytest.raises(InferenceForbidden):
        DelegatingClient(client=sdk).list_models()


def test_compatible_list_models_returns_empty_tuple_for_no_models() -> None:
    # Documented decision: an empty ``data`` list is a valid discovery
    # result and is returned as an empty tuple, never an error.
    response = SimpleNamespace(data=[])
    sdk = DummyModelListSDK(response)
    client = OpenAICompatibleClient(client=sdk)

    assert client.list_models() == ()
    assert sdk.calls == ["models.list"]


def test_compatible_list_models_rejects_non_list_data() -> None:
    response = SimpleNamespace(data="not-a-list")
    sdk = DummyModelListSDK(response)

    with pytest.raises(ProviderError, match=r"had no data list"):
        OpenAICompatibleClient(client=sdk).list_models()


def test_compatible_list_models_rejects_missing_data_attribute() -> None:
    response = SimpleNamespace()
    sdk = DummyModelListSDK(response)

    with pytest.raises(ProviderError, match=r"had no data list"):
        OpenAICompatibleClient(client=sdk).list_models()


def test_compatible_list_models_rejects_item_without_string_id() -> None:
    response = SimpleNamespace(
        data=[
            SimpleNamespace(id="model-a", object="model"),
            SimpleNamespace(id=None, object="model"),
        ],
    )
    sdk = DummyModelListSDK(response)

    with pytest.raises(ProviderError, match=r"lacks a string id"):
        OpenAICompatibleClient(client=sdk).list_models()


def test_compatible_list_models_rejects_non_string_id() -> None:
    response = SimpleNamespace(data=[SimpleNamespace(id=123, object="model")])
    sdk = DummyModelListSDK(response)

    with pytest.raises(ProviderError, match=r"lacks a string id"):
        OpenAICompatibleClient(client=sdk).list_models()


def test_compatible_list_models_rejects_duplicate_ids() -> None:
    response = SimpleNamespace(
        data=[
            SimpleNamespace(id="model-a", object="model"),
            SimpleNamespace(id="model-a", object="model"),
        ],
    )
    sdk = DummyModelListSDK(response)

    with pytest.raises(ProviderError, match=r"duplicate id: model-a"):
        OpenAICompatibleClient(client=sdk).list_models()
