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

import hashlib
import time
from collections import deque
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from kernel.llm.capabilities import ReasoningEffort
from kernel.llm.model_gateway_contracts import (
    InputPartKind,
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
from kernel.llm.model_gateway_errors import ModelGatewayError, ModelGatewayErrorCode
from kernel.llm.models import LLMRequest, LLMResponse
from kernel.llm.provider import LLMProvider

__all__ = [
    "InMemoryModelProviderAdapter",
    "LLMProviderModelAdapter",
    "ModelProviderAdapter",
    "ModelProviderAdapterRegistry",
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


def _is_cancelled(cancellation: object | None) -> bool:
    """Return whether a cooperative cancellation token was cancelled."""

    return bool(getattr(cancellation, "is_cancelled", False))


def _raise_if_cancelled(cancellation: object | None) -> None:
    if _is_cancelled(cancellation):
        raise ModelGatewayError(
            ModelGatewayErrorCode.MODEL_CALL_CANCELLED,
            "model call was cancelled before provider execution",
            retryable=False,
        )


def _shared_failure(code: ModelGatewayErrorCode, message: str) -> ModelGatewayError:
    return ModelGatewayError(code, message, retryable=False)


class ModelProviderAdapterRegistry:
    """Resolve exactly one executor per canonical provider identity.

    This is an execution registry, not a provider registry: entries carry no
    provider metadata, no credentials, no capability truth and no policy, and
    nothing here may become an alternative authority for provider identity.
    """

    def __init__(self, adapters: Iterable[ModelProviderAdapter] = ()) -> None:
        self._adapters: dict[str, ModelProviderAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: ModelProviderAdapter) -> None:
        """Register one adapter, rejecting a duplicate provider identity."""

        provider_id = getattr(adapter, "provider_id", None)
        execute = getattr(adapter, "execute", None)
        stream = getattr(adapter, "stream", None)
        if (
            not isinstance(provider_id, str)
            or not provider_id.strip()
            or not callable(execute)
            or not callable(stream)
        ):
            raise TypeError(
                "adapter must implement provider_id, execute() and stream()"
            )
        normalized = provider_id.strip().lower()
        if normalized in self._adapters:
            raise ValueError(f"adapter is already registered: {normalized}")
        self._adapters[normalized] = adapter

    def get(self, provider_id: str) -> ModelProviderAdapter:
        """Return the adapter for ``provider_id`` or fail closed."""

        normalized = str(provider_id).strip().lower()
        adapter = self._adapters.get(normalized)
        if adapter is None:
            raise ModelGatewayError(
                ModelGatewayErrorCode.PROVIDER_NOT_AVAILABLE,
                "no provider adapter is registered for this provider",
                details={"provider_id": normalized},
                retryable=False,
            )
        return adapter

    def has(self, provider_id: str) -> bool:
        """Return whether an adapter is registered for ``provider_id``."""

        return str(provider_id).strip().lower() in self._adapters

    def provider_ids(self) -> tuple[str, ...]:
        """Return every registered provider identity, sorted."""

        return tuple(sorted(self._adapters))

    def __len__(self) -> int:
        return len(self._adapters)


@dataclass(frozen=True, slots=True)
class _Scenario:
    """One scripted in-memory provider outcome."""

    kind: str
    content: str = ""
    structured_output: Mapping[str, Any] | None = None
    tool_calls: tuple[ModelToolCall, ...] = ()
    usage: ModelUsage | None = None
    finish_reason: str = "stop"
    chunks: tuple[str, ...] = ()
    error_code: ModelGatewayErrorCode = ModelGatewayErrorCode.PROVIDER_FAILURE
    error_message: str = "in-memory provider failure"
    retryable: bool | None = None
    delay_seconds: float = 0.0
    fail_with: ModelGatewayErrorCode | None = None


class InMemoryModelProviderAdapter:
    """Official in-memory provider adapter used by connected acceptance.

    It is a real implementation of the canonical adapter protocol: it validates
    its own translation duties, translates canonical reasoning effort through a
    provider-local mapping, produces canonical provider responses, observes
    cooperative cancellation, and records the *actual* content fingerprints it
    received so acceptance can prove that real bytes reached the adapter.

    Scripted outcomes are consumed in order, so a scenario sequence is fully
    deterministic and never depends on wall-clock timing.
    """

    def __init__(
        self,
        provider_id: str,
        *,
        supports_streaming: bool = True,
        reasoning_effort_map: Mapping[ReasoningEffort | str, str] | None = None,
        derive_content_from_input: bool = False,
    ) -> None:
        self.provider_id = require_identifier(provider_id, label="provider_id")
        self._supports_streaming = bool(supports_streaming)
        self._derive_content_from_input = bool(derive_content_from_input)
        self._effort_map = {
            ReasoningEffort(effort): str(native)
            for effort, native in (reasoning_effort_map or {}).items()
        }
        self._scenarios: deque[_Scenario] = deque()
        self._requests: list[ProviderModelRequest] = []
        self._fingerprints: list[tuple[tuple[str, int, str], ...]] = []
        self._native_efforts: list[str | None] = []

    # ── Scripting ────────────────────────────────────────────────────────────

    def add_response(
        self,
        content: str = "",
        *,
        structured_output: Mapping[str, Any] | None = None,
        tool_calls: tuple[ModelToolCall, ...] = (),
        usage: ModelUsage | None = None,
        finish_reason: str = "stop",
    ) -> None:
        """Script one successful provider response."""

        if not isinstance(content, str):
            raise TypeError("content must be a string")
        self._scenarios.append(
            _Scenario(
                kind="response",
                content=content,
                structured_output=structured_output,
                tool_calls=tuple(tool_calls),
                usage=usage,
                finish_reason=finish_reason,
            )
        )

    def add_failure(
        self,
        code: ModelGatewayErrorCode,
        message: str = "in-memory provider failure",
        *,
        retryable: bool | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        """Script one normalized provider failure."""

        self._scenarios.append(
            _Scenario(
                kind="failure",
                error_code=ModelGatewayErrorCode(code),
                error_message=message,
                retryable=retryable,
                delay_seconds=float(delay_seconds),
            )
        )

    def add_timeout(
        self,
        *,
        delay_seconds: float = 0.0,
        message: str = "in-memory provider timeout",
    ) -> None:
        """Script one provider timeout."""

        self.add_failure(
            ModelGatewayErrorCode.PROVIDER_TIMEOUT,
            message,
            retryable=True,
            delay_seconds=delay_seconds,
        )

    def add_stream(
        self,
        chunks: Iterable[str] = (),
        *,
        usage: ModelUsage | None = None,
        tool_calls: tuple[ModelToolCall, ...] = (),
        finish_reason: str = "stop",
        fail_with: ModelGatewayErrorCode | None = None,
    ) -> None:
        """Script one provider token stream."""

        normalized_chunks = tuple(str(chunk) for chunk in chunks)
        if any(not chunk for chunk in normalized_chunks):
            raise ValueError("streamed chunks must be non-empty")
        self._scenarios.append(
            _Scenario(
                kind="stream",
                chunks=normalized_chunks,
                usage=usage,
                tool_calls=tuple(tool_calls),
                finish_reason=finish_reason,
                fail_with=(
                    None if fail_with is None else ModelGatewayErrorCode(fail_with)
                ),
            )
        )

    # ── Observation ──────────────────────────────────────────────────────────

    @property
    def requests(self) -> tuple[ProviderModelRequest, ...]:
        """Return every request this adapter received, in call order."""

        return tuple(self._requests)

    @property
    def received_input_fingerprints(
        self,
    ) -> tuple[tuple[tuple[str, int, str], ...], ...]:
        """Return (kind, byte_length, content_digest) facts per received call."""

        return tuple(self._fingerprints)

    @property
    def native_efforts(self) -> tuple[str | None, ...]:
        """Return the provider-native effort value translated per call."""

        return tuple(self._native_efforts)

    @property
    def call_count(self) -> int:
        """Return how many provider calls this adapter recorded."""

        return len(self._requests)

    @property
    def supports_streaming(self) -> bool:
        """Return whether this adapter can stream provider tokens."""

        return self._supports_streaming

    # ── Canonical adapter protocol ───────────────────────────────────────────

    def execute(
        self,
        request: ProviderModelRequest,
        *,
        cancellation: object | None = None,
    ) -> ProviderModelResponse:
        """Execute one scripted scenario and return the normalized result."""

        _raise_if_cancelled(cancellation)
        self._record(request)
        scenario = self._next_scenario()
        return self._materialize(request, scenario)

    def stream(
        self,
        request: ProviderModelRequest,
        *,
        cancellation: object | None = None,
    ) -> Iterator[ProviderStreamEvent]:
        """Stream one scripted scenario as ordered provider events."""

        if not self._supports_streaming:
            raise _shared_failure(
                ModelGatewayErrorCode.STREAM_FAILURE,
                "provider adapter does not support token streaming",
            )
        _raise_if_cancelled(cancellation)
        self._record(request)
        scenario = self._next_scenario()

        yield ProviderStreamEvent(
            event_type=ModelStreamEventType.STARTED,
            effective_reasoning_effort=request.reasoning_effort,
            reasoning_used=self._reasoning_used(request),
        )

        if scenario.kind == "failure":
            if scenario.delay_seconds:
                time.sleep(scenario.delay_seconds)
            yield ProviderStreamEvent(
                event_type=ModelStreamEventType.ERROR,
                error_code=scenario.error_code.value,
                failure=scenario.error_message,
            )
            return

        chunks = (
            scenario.chunks
            if scenario.kind == "stream"
            else ((scenario.content,) if scenario.content else ())
        )
        for chunk in chunks:
            if _is_cancelled(cancellation):
                yield ProviderStreamEvent(event_type=ModelStreamEventType.CANCELLED)
                return
            yield ProviderStreamEvent(
                event_type=ModelStreamEventType.CONTENT_DELTA,
                content_delta=chunk,
            )

        for call in scenario.tool_calls:
            if _is_cancelled(cancellation):
                yield ProviderStreamEvent(event_type=ModelStreamEventType.CANCELLED)
                return
            yield ProviderStreamEvent(
                event_type=ModelStreamEventType.TOOL_CALL_DELTA,
                tool_call=call,
            )

        if scenario.fail_with is not None:
            yield ProviderStreamEvent(
                event_type=ModelStreamEventType.ERROR,
                error_code=scenario.fail_with.value,
                failure="provider stream failed",
            )
            return

        if _is_cancelled(cancellation):
            yield ProviderStreamEvent(event_type=ModelStreamEventType.CANCELLED)
            return

        if scenario.usage is not None:
            yield ProviderStreamEvent(
                event_type=ModelStreamEventType.USAGE,
                usage=scenario.usage,
            )

        yield ProviderStreamEvent(
            event_type=ModelStreamEventType.COMPLETED,
            response=self._materialize(request, scenario),
        )

    # ── Internals ────────────────────────────────────────────────────────────

    def _record(self, request: ProviderModelRequest) -> None:
        self._requests.append(request)
        self._fingerprints.append(
            tuple(
                (part.kind.value, part.byte_length, part.content_digest or "")
                for part in request.input_parts
            )
        )
        native: str | None = None
        if request.reasoning_effort is not ReasoningEffort.DEFAULT:
            if request.reasoning_effort not in self._effort_map:
                raise ModelGatewayError(
                    ModelGatewayErrorCode.UNSUPPORTED_REASONING_EFFORT,
                    "provider adapter cannot translate the requested reasoning effort",
                    details={
                        "provider_id": self.provider_id,
                        "effort": request.reasoning_effort.value,
                    },
                    retryable=False,
                )
            native = self._effort_map[request.reasoning_effort]
        self._native_efforts.append(native)

    def _next_scenario(self) -> _Scenario:
        if not self._scenarios:
            raise _shared_failure(
                ModelGatewayErrorCode.PROVIDER_FAILURE,
                "in-memory adapter has no scripted outcome left",
            )
        return self._scenarios.popleft()

    def _reasoning_used(self, request: ProviderModelRequest) -> bool:
        return request.reasoning_effort not in (
            ReasoningEffort.DEFAULT,
            ReasoningEffort.NONE,
        )

    def _materialize(
        self,
        request: ProviderModelRequest,
        scenario: _Scenario,
    ) -> ProviderModelResponse:
        if scenario.kind == "failure":
            if scenario.delay_seconds:
                time.sleep(scenario.delay_seconds)
            raise ModelGatewayError(
                scenario.error_code,
                scenario.error_message,
                details={"provider_id": self.provider_id},
                retryable=scenario.retryable,
            )

        input_digest = _input_content_digest(request)
        content = (
            scenario.content
            if scenario.kind == "response"
            else "".join(scenario.chunks)
        )
        if self._derive_content_from_input:
            content = f"echo:{input_digest}"

        return ProviderModelResponse(
            content=content,
            tool_calls=scenario.tool_calls,
            structured_output=scenario.structured_output,
            usage=scenario.usage or ModelUsage(),
            finish_reason=scenario.finish_reason,
            effective_reasoning_effort=request.reasoning_effort,
            reasoning_used=self._reasoning_used(request),
            metadata={
                "provider_id": self.provider_id,
                "input_parts": [part.to_dict() for part in request.input_parts],
                "input_content_digest": input_digest,
            },
        )


def _input_content_digest(request: ProviderModelRequest) -> str:
    """Return a digest over the exact content digests the adapter received."""

    joined = "|".join(part.content_digest or "" for part in request.input_parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


class LLMProviderModelAdapter:
    """Adapt a pre-existing canonical ``LLMProvider`` to the adapter protocol.

    The closed providers (OpenAI-compatible, Ollama, mock) speak a text-only
    ``LLMRequest``/``LLMResponse`` contract.  This wrapper reuses them exactly
    as they are instead of forking them, and honestly refuses what they cannot
    do: multimodal content, explicit reasoning effort and token streaming all
    fail closed before any provider call.

    The legacy response contract cannot distinguish "reported zero tokens" from
    "reported nothing", so an all-zero usage pair is reported as unknown rather
    than as a fabricated zero.
    """

    def __init__(
        self,
        provider: LLMProvider,
        *,
        provider_id: str,
        model_id: str,
    ) -> None:
        if not isinstance(provider, LLMProvider):
            raise TypeError("provider must be an LLMProvider")
        self._provider = provider
        self.provider_id = require_identifier(provider_id, label="provider_id")
        self._model_id = require_identifier(model_id, label="model_id")

    @property
    def supports_streaming(self) -> bool:
        """The wrapped text-only providers cannot stream tokens."""

        return False

    def execute(
        self,
        request: ProviderModelRequest,
        *,
        cancellation: object | None = None,
    ) -> ProviderModelResponse:
        """Execute a text-only request through the wrapped provider."""

        _raise_if_cancelled(cancellation)
        if request.model_id != self._model_id:
            raise _shared_failure(
                ModelGatewayErrorCode.MODEL_NOT_FOUND,
                "wrapped provider is bound to a different model",
            )
        for part in request.input_parts:
            if part.kind is not InputPartKind.TEXT:
                raise ModelGatewayError(
                    ModelGatewayErrorCode.CAPABILITY_UNSUPPORTED,
                    "the wrapped provider transports text input only",
                    details={"kind": part.kind.value, "provider_id": self.provider_id},
                    retryable=False,
                )
        if request.reasoning_effort is not ReasoningEffort.DEFAULT:
            raise ModelGatewayError(
                ModelGatewayErrorCode.UNSUPPORTED_REASONING_EFFORT,
                "the wrapped provider cannot apply an explicit reasoning effort",
                details={"provider_id": self.provider_id},
                retryable=False,
            )

        prompt = "\n".join(part.text or "" for part in request.input_parts)
        response: LLMResponse = self._provider.generate(
            LLMRequest(prompt=prompt, system_prompt=None, temperature=0.0, metadata={})
        )
        input_tokens, output_tokens = _legacy_token_counts(response)
        return ProviderModelResponse(
            content=response.content,
            usage=ModelUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ),
            finish_reason=response.finish_reason,
            effective_reasoning_effort=ReasoningEffort.DEFAULT,
            reasoning_used=False,
            metadata={
                "provider_id": self.provider_id,
                "adapted_provider": type(self._provider).__name__,
            },
        )

    def stream(
        self,
        request: ProviderModelRequest,
        *,
        cancellation: object | None = None,
    ) -> Iterator[ProviderStreamEvent]:
        """Fail closed: the wrapped providers have no streaming transport."""

        raise _shared_failure(
            ModelGatewayErrorCode.STREAM_FAILURE,
            "the wrapped provider does not support token streaming",
        )


def _legacy_token_counts(response: LLMResponse) -> tuple[int | None, int | None]:
    """Map legacy usage counters, reporting all-zero counters as unknown."""

    prompt_tokens = response.usage_prompt_tokens
    completion_tokens = response.usage_completion_tokens
    if prompt_tokens == 0 and completion_tokens == 0:
        return None, None
    return prompt_tokens, completion_tokens
