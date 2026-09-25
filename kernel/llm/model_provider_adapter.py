"""Provider adapter boundary for the canonical Model Gateway (Phase 11.21).

The gateway core is provider-name agnostic.  It never branches on a provider
name: it resolves one adapter by canonical provider identity and hands that
adapter an already-validated, provider-independent request.  All
provider-native translation lives inside the adapter.

This module defines the adapter-facing canonical contracts, the adapter
protocol and the adapter registry.  The registry resolves *execution* only — it
stores no provider metadata, no credentials and no policy, so it is not and can
never become a second provider registry.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from kernel.llm.capabilities import ReasoningEffort
from kernel.llm.model_gateway_contracts import (
    ModelInputPart,
    ModelStreamEventType,
    ModelToolCall,
    ModelToolDefinition,
    ModelUsage,
    StructuredOutputRequirement,
    ensure_safe_metadata,
    require_identifier,
    to_plain_json,
)

__all__ = [
    "ModelProviderAdapter",
    "ProviderModelRequest",
    "ProviderModelResponse",
    "ProviderStreamEvent",
]


@dataclass(frozen=True, slots=True)
class ProviderModelRequest:
    """One validated, provider-independent request handed to an adapter.

    The gateway only builds this after canonical model lookup, capability
    validation and privacy enforcement succeeded.  ``input_parts`` carry the
    real authorized content the adapter must transport.
    """

    request_id: str
    provider_id: str
    model_id: str
    input_parts: tuple[ModelInputPart, ...]
    reasoning_effort: ReasoningEffort = ReasoningEffort.DEFAULT
    tools: tuple[ModelToolDefinition, ...] = ()
    structured_output: StructuredOutputRequirement | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", require_identifier(self.request_id, label="request_id")
        )
        object.__setattr__(
            self,
            "provider_id",
            require_identifier(self.provider_id, label="provider_id"),
        )
        object.__setattr__(
            self, "model_id", require_identifier(self.model_id, label="model_id")
        )
        parts = tuple(self.input_parts)
        for part in parts:
            if not isinstance(part, ModelInputPart):
                raise TypeError("input_parts must contain ModelInputPart values")
        object.__setattr__(self, "input_parts", parts)
        object.__setattr__(
            self, "reasoning_effort", ReasoningEffort(self.reasoning_effort)
        )
        tools = tuple(self.tools)
        for tool in tools:
            if not isinstance(tool, ModelToolDefinition):
                raise TypeError("tools must contain ModelToolDefinition values")
        object.__setattr__(self, "tools", tools)
        if self.structured_output is not None and not isinstance(
            self.structured_output, StructuredOutputRequirement
        ):
            raise TypeError(
                "structured_output must be a StructuredOutputRequirement or None"
            )
        object.__setattr__(
            self,
            "metadata",
            ensure_safe_metadata(self.metadata, label="provider request metadata"),
        )
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive when provided")

    @property
    def input_modalities(self) -> tuple[str, ...]:
        """Return the distinct input modalities in stable first-seen order."""

        return tuple(dict.fromkeys(part.kind.value for part in self.input_parts))

    def to_dict(self) -> dict[str, Any]:
        """Return the safe public view; raw content is never included."""

        return {
            "request_id": self.request_id,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "input_parts": [part.to_dict() for part in self.input_parts],
            "input_modalities": list(self.input_modalities),
            "reasoning_effort": self.reasoning_effort.value,
            "tools": [tool.to_dict() for tool in self.tools],
            "structured_output": (
                self.structured_output.to_dict()
                if self.structured_output is not None
                else None
            ),
            "timeout_seconds": self.timeout_seconds,
            "metadata": to_plain_json(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ProviderModelResponse:
    """One provider-native result normalized by an adapter.

    Adapters report only facts: content, normalized tool calls, optional
    structured output, truthful usage counters (``None`` when the provider
    reported nothing) and the effective reasoning effort actually applied.
    """

    content: str = ""
    tool_calls: tuple[ModelToolCall, ...] = ()
    structured_output: Mapping[str, Any] | None = None
    usage: ModelUsage = field(default_factory=ModelUsage)
    finish_reason: str | None = None
    effective_reasoning_effort: ReasoningEffort = ReasoningEffort.DEFAULT
    reasoning_used: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.content, str):
            raise TypeError("content must be a string")
        calls = tuple(self.tool_calls)
        for call in calls:
            if not isinstance(call, ModelToolCall):
                raise TypeError("tool_calls must contain ModelToolCall values")
        object.__setattr__(self, "tool_calls", calls)
        if not isinstance(self.usage, ModelUsage):
            raise TypeError("usage must be a ModelUsage")
        object.__setattr__(
            self,
            "effective_reasoning_effort",
            ReasoningEffort(self.effective_reasoning_effort),
        )
        if not isinstance(self.reasoning_used, bool):
            raise TypeError("reasoning_used must be a bool")
        object.__setattr__(
            self,
            "metadata",
            ensure_safe_metadata(self.metadata, label="provider response metadata"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the safe public view of this result."""

        return {
            "content": self.content,
            "tool_calls": [call.to_dict() for call in self.tool_calls],
            "structured_output": (
                to_plain_json(self.structured_output)
                if self.structured_output is not None
                else None
            ),
            "usage": self.usage.to_dict(),
            "finish_reason": self.finish_reason,
            "effective_reasoning_effort": self.effective_reasoning_effort.value,
            "reasoning_used": self.reasoning_used,
            "metadata": to_plain_json(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ProviderStreamEvent:
    """One adapter-emitted, already provider-normalized stream event.

    The gateway's stream normalizer turns these into canonical
    :class:`~kernel.llm.model_gateway_contracts.ModelStreamEvent` values and
    enforces the ordering and single-terminal invariants.
    """

    event_type: ModelStreamEventType
    content_delta: str | None = None
    tool_call: ModelToolCall | None = None
    usage: ModelUsage | None = None
    response: ProviderModelResponse | None = None
    error_code: str | None = None
    failure: str | None = None
    effective_reasoning_effort: ReasoningEffort = ReasoningEffort.DEFAULT
    reasoning_used: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_type", ModelStreamEventType(self.event_type))
        if self.content_delta is not None and not self.content_delta:
            raise ValueError("content_delta must be non-empty when provided")
        if self.tool_call is not None and not isinstance(self.tool_call, ModelToolCall):
            raise TypeError("tool_call must be a ModelToolCall or None")
        if self.usage is not None and not isinstance(self.usage, ModelUsage):
            raise TypeError("usage must be a ModelUsage or None")
        if self.response is not None and not isinstance(
            self.response, ProviderModelResponse
        ):
            raise TypeError("response must be a ProviderModelResponse or None")
        object.__setattr__(
            self,
            "effective_reasoning_effort",
            ReasoningEffort(self.effective_reasoning_effort),
        )


@runtime_checkable
class ModelProviderAdapter(Protocol):
    """Narrow execute/stream boundary implemented once per provider.

    Implementations translate between the canonical provider-independent
    contracts and one provider's native protocol.  They receive no policy
    authority: validation, privacy and fallback already happened in the gateway
    core.
    """

    @property
    def provider_id(self) -> str:
        """Return the canonical provider id this adapter executes."""

    def execute(
        self,
        request: ProviderModelRequest,
        *,
        cancellation: object | None = None,
    ) -> ProviderModelResponse:
        """Execute one request and return the normalized provider result."""

    def stream(
        self,
        request: ProviderModelRequest,
        *,
        cancellation: object | None = None,
    ) -> Iterator[ProviderStreamEvent]:
        """Stream one request as ordered provider-normalized events."""
