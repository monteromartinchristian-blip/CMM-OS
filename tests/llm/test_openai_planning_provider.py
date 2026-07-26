from __future__ import annotations

import json
from typing import Any

import pytest

from cmm.development.providers import (
    OpenAIPlanningProvider,
    PlanningProviderError,
    create_planning_provider,
)


class DummyContext:
    def serialize(self) -> dict[str, Any]:
        return {"root": ".", "files": []}


class DummyResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.output_text = json.dumps(payload)


class DummyResponses:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> DummyResponse:
        self.calls.append(kwargs)
        return DummyResponse(self.payload)


class DummyKernelProvider:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.calls: list[Any] = []

    def generate(self, request: Any) -> Any:
        from kernel.llm.models import LLMResponse

        self.calls.append(request)
        return LLMResponse(
            content=json.dumps(self.payload),
            model="test-model",
        )


def valid_plan(path: str = "requested.py") -> dict[str, Any]:
    return {
        "goal": f"create class Example in {path}",
        "affected_files": [path],
        "operations": [
            {
                "domain": "python",
                "type": "create_class",
                "parameters": {
                    "path": path,
                    "class_name": "Example",
                },
                "reason": "Create the requested class.",
            }
        ],
        "rationale": "Implement the explicit goal.",
        "validations": ["python_ast", "python_compile"],
        "risks": [],
    }


def test_factory_creates_openai_provider_with_requested_model() -> None:
    provider = create_planning_provider("openai:gpt-5-mini")

    assert isinstance(provider, OpenAIPlanningProvider)
    assert provider.model == "gpt-5-mini"


def test_generate_plan_uses_injected_client() -> None:
    provider = DummyKernelProvider(valid_plan())
    adapter = OpenAIPlanningProvider(model="test-model", provider=provider)

    result = adapter.generate_plan(
        "create class Example in requested.py",
        DummyContext(),
    )

    assert result["affected_files"] == ["requested.py"]
    assert provider.calls[0].prompt


def test_prompt_requires_exact_explicit_paths() -> None:
    provider = OpenAIPlanningProvider(provider=DummyKernelProvider(valid_plan()))

    prompt = provider._prompt(
        "create class Example in requested.py",
        DummyContext(),
    )

    assert "Preserve all file paths explicitly written in the goal exactly" in prompt
    assert "Development goal: create class Example in requested.py" in prompt


def test_generate_plan_rejects_relocated_explicit_path() -> None:
    kernel_provider = DummyKernelProvider(valid_plan("tests/requested.py"))
    provider = OpenAIPlanningProvider(provider=kernel_provider)

    with pytest.raises(
        PlanningProviderError,
        match="changed an explicitly requested path",
    ):
        provider.generate_plan(
            "create class Example in requested.py",
            DummyContext(),
        )


def test_generate_plan_accepts_exact_explicit_path() -> None:
    provider = OpenAIPlanningProvider(
        provider=DummyKernelProvider(valid_plan("requested.py"))
    )

    result = provider.generate_plan(
        "create class Example in requested.py",
        DummyContext(),
    )

    assert result["operations"][0]["parameters"]["path"] == "requested.py"


def test_factory_creates_registered_nvidia_provider() -> None:
    from cmm.development.providers import (
        OpenAICompatiblePlanningProvider,
    )

    provider = create_planning_provider("nvidia")

    assert isinstance(
        provider,
        OpenAICompatiblePlanningProvider,
    )
    assert provider.model == "z-ai/glm-5.2"
    assert provider.provider.source == "nvidia"


def test_factory_uses_requested_registered_provider_model() -> None:
    provider = create_planning_provider("nvidia:custom/model")

    assert provider.model == "custom/model"
    assert provider.provider.source == "nvidia"
