"""The stable client boundary: one import path, closed vocabulary, no internals.

These tests pin the contract a first-party client relies on: the descriptor
carries the full capability truth, resolution exposes what the descriptor
declares, a visual turn on the capability plane declares its downgrade instead
of hiding it, and every failure leaves as a closed code.  The architecture test
pins the layering itself: only the facade may reach below the boundary.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

import cmm.model_client as boundary
from cmm.model_client import (
    MODEL_CLIENT_INTERFACE_VERSION,
    ClientModelDescriptor,
    ClientStreamFacts,
    ModelClient,
    ModelClientError,
    normalize,
)
from cmm.model_execution.contracts import NormalizedModel, ResolvedChatModel
from cmm.model_execution.errors import ModelExecutionError
from kernel.llm.capabilities import ModelCapabilities, ReasoningEffort
from kernel.llm.model_catalog import ModelSpec
from kernel.llm.provider_registry import ProviderSpec

PACKAGE = Path(boundary.__file__).parent
ROUTER = "cmmchat-router"


class _FakeExecutor:
    """A scripted executor standing in for the composed canonical seam."""

    def __init__(
        self,
        *,
        models: tuple[NormalizedModel, ...],
        resolved: ResolvedChatModel,
        deltas: tuple[str, ...] = ("Ho", "la"),
    ) -> None:
        self._models = models
        self._resolved = resolved
        self._deltas = deltas
        self.stream_calls: list[dict[str, Any]] = []

    def catalog(self) -> tuple[NormalizedModel, ...]:
        return self._models

    def resolve_chat(self, selection: str | None) -> ResolvedChatModel:
        return self._resolved

    def stream(self, handle: Any, **parameters: Any) -> Any:
        self.stream_calls.append({"handle": handle, **parameters})
        if parameters.get("facts_sink") is not None:
            from cmm.model_execution.contracts import ChatStreamFacts

            parameters["facts_sink"](
                ChatStreamFacts(
                    requested_reasoning_effort=str(
                        parameters.get("reasoning_effort", "default")
                    ),
                    effective_reasoning_effort=None,
                )
            )
        yield from self._deltas


def _normalized(**capabilities: Any) -> NormalizedModel:
    return NormalizedModel(
        model_id="thinker",
        display_name="Thinker",
        provider_id=ROUTER,
        locality="local",
        availability="available",
        capabilities=capabilities,
    )


def _resolved(model: NormalizedModel) -> ResolvedChatModel:
    return ResolvedChatModel(
        model=model,
        policy="explicit",
        spec=ModelSpec(id=model.model_id, provider_id=ROUTER),
        provider=ProviderSpec(
            id=ROUTER,
            provider_type="local",
            api_style="chat_completions",
            base_url="http://127.0.0.1:8790/v1",
        ),
    )


def test_the_boundary_exports_one_versioned_surface() -> None:
    # v2 added `version` and `status` to ClientModelDescriptor. Both are
    # additive with honest defaults, so a v1 client still decodes a v2
    # payload; the pin moves only because the descriptor now carries facts it
    # previously had no field to show.
    assert MODEL_CLIENT_INTERFACE_VERSION == "2"
    assert set(boundary.__all__) >= {
        "ModelClient",
        "ModelClientError",
        "ClientModelDescriptor",
        "ClientResolvedModel",
        "ClientStreamEvent",
        "ClientStreamFacts",
        "normalize",
    }


def test_catalog_projects_the_full_capability_truth() -> None:
    model = NormalizedModel(
        model_id="thinker",
        display_name="Thinker",
        provider_id=ROUTER,
        locality="local",
        availability="available",
        capabilities={"vision": True, "reasoning": True},
        reasoning_efforts=("low", "medium"),
        document_media_types=("application/pdf",),
        context_window=8192,
        streaming=True,
    )
    client = ModelClient(executor=_FakeExecutor(models=(model,), resolved=_resolved(model)))

    (descriptor,) = client.catalog()

    assert descriptor == ClientModelDescriptor(
        id="thinker",
        display_name="Thinker",
        availability="available",
        locality="local",
        provider_id=ROUTER,
        capabilities={"vision": True, "reasoning": True},
        reasoning_efforts=("low", "medium"),
        document_media_types=("application/pdf",),
        context_window=8192,
        streaming=True,
    )


def test_resolution_exposes_what_the_descriptor_declares() -> None:
    model = _normalized(vision=True, tool_calling=False, structured_output=False)
    client = ModelClient(executor=_FakeExecutor(models=(model,), resolved=_resolved(model)))

    resolved = client.resolve("thinker")

    assert resolved.supports_vision is True
    assert resolved.supports_capability_plane is False
    assert resolved.policy == "explicit"


def test_stream_forwards_the_effort_and_reports_the_facts() -> None:
    model = _normalized(vision=False)
    executor = _FakeExecutor(models=(model,), resolved=_resolved(model))
    client = ModelClient(executor=executor)
    facts: list[ClientStreamFacts] = []

    deltas = list(
        client.stream(
            client.resolve("thinker"),
            prompt="hola",
            reasoning_effort="medium",
            facts_sink=facts.append,
        )
    )

    assert "".join(deltas) == "Hola"
    assert executor.stream_calls[0]["reasoning_effort"] == "medium"
    assert facts == [
        ClientStreamFacts(requested_reasoning_effort="medium", effective_reasoning_effort=None)
    ]


def test_a_visual_turn_declares_its_capability_downgrade() -> None:
    model = _normalized(vision=True)
    client = ModelClient(executor=_FakeExecutor(models=(model,), resolved=_resolved(model)))

    events = list(
        client.stream_with_capabilities(
            client.resolve("thinker"),
            prompt="look",
            images=({"media_type": "image/png", "data": b"x"},),
            capabilities={"web_search": "on"},
        )
    )

    kinds = [event.kind for event in events]
    assert kinds[0] == "capability.degraded"
    assert events[0].data == {"reason": "visual_input"}
    assert kinds[-2:] == ["message.delta", "run.summary"]


def test_failures_leave_as_closed_codes_only() -> None:
    assert normalize(
        ModelExecutionError("boom", code="MODEL_UNAVAILABLE")
    ).code == "MODEL_UNAVAILABLE"
    assert normalize(RuntimeError("sk-secret exploded")).code == "PROVIDER_FAILURE"
    assert normalize(TimeoutError()).code == "TIMEOUT"
    with pytest.raises(ValueError):
        ModelClientError("NOT_A_CODE", "x")


def test_only_the_facade_reaches_below_the_boundary() -> None:
    """No module of the boundary except the facade imports OS internals."""

    offenders: list[str] = []
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or node.module is None:
                continue
            root = node.module.split(".")[0]
            second = node.module.split(".")[:2]
            internal = root == "kernel" or second in (
                ["cmm", "model_execution"],
                ["cmm", "capabilities"],
            )
            if internal and path.name != "interface.py":
                offenders.append(f"{path.name}:{node.module}")

    assert offenders == []
