"""Provider implementation for OpenAI-compatible Chat Completions APIs."""

from __future__ import annotations

import base64

from collections.abc import Iterator, Mapping
from threading import Event
from typing import Any, Protocol

from kernel.llm.capabilities import ReasoningEffort
from kernel.llm.clients.openai_compatible_client import configured_reasoning_effort_map
from kernel.llm.exceptions import ProviderError
from kernel.llm.models import LLMRequest, LLMResponse
from kernel.llm.provider import LLMProvider


class OpenAICompatibleClientProtocol(Protocol):
    """Minimum client contract required by the provider."""

    def generate(
        self,
        *,
        model: str,
        system: str | None,
        prompt: str,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> tuple[str, int, int, str]:
        """Generate text through an OpenAI-compatible endpoint."""

    def stream_chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.0,
        max_tokens: int | None = None,
        cancel_event: Event | None = None,
        request_extras: Mapping[str, Any] | None = None,
    ) -> Iterator[str]:
        """Stream content deltas through an OpenAI-compatible endpoint."""


class OpenAICompatibleProvider(LLMProvider):
    """Generate responses through a provider-specific compatible client."""

    def __init__(
        self,
        *,
        provider_id: str,
        client: OpenAICompatibleClientProtocol,
        model: str,
        reasoning_effort_map: Mapping[ReasoningEffort, Mapping[str, Any]] | None = None,
    ) -> None:
        normalized_provider_id = provider_id.strip().lower()
        if not normalized_provider_id:
            raise ProviderError("provider_id cannot be empty")
        if not model.strip():
            raise ProviderError("model cannot be empty")

        self.provider_id = normalized_provider_id
        self.client = client
        self.model = model.strip()
        #: Per-model map of canonical effort level -> the wire fragment this
        #: endpoint understands.  A level absent from the map is one this
        #: provider cannot transmit, so it is refused instead of being silently
        #: dropped.  An injected map wins; otherwise the launcher's configured
        #: map for this provider answers, so capability declaration and wire
        #: transmission can never diverge.
        injected = (
            {self.model.strip().lower(): dict(reasoning_effort_map)}
            if reasoning_effort_map is not None
            else None
        )
        self.reasoning_effort_map: Mapping[
            str, Mapping[ReasoningEffort, Mapping[str, Any]]
        ] = injected or configured_reasoning_effort_map(normalized_provider_id)

    def _efforts_for_model(self) -> Mapping[ReasoningEffort, Mapping[str, Any]]:
        return self.reasoning_effort_map.get(self.model.lower(), {})

    def supports_reasoning_effort(self, effort: ReasoningEffort | str) -> bool:
        """Whether this provider can put ``effort`` on the wire for this model."""

        normalized = ReasoningEffort(effort)
        if normalized is ReasoningEffort.DEFAULT:
            return True
        return normalized in self._efforts_for_model()

    def reasoning_effort_extras(
        self, effort: ReasoningEffort | str
    ) -> Mapping[str, Any]:
        """Return the wire fragment for ``effort``; empty for ``DEFAULT``."""

        normalized = ReasoningEffort(effort)
        if normalized is ReasoningEffort.DEFAULT:
            return {}
        fragment = self._efforts_for_model().get(normalized)
        if fragment is None:
            raise ProviderError(
                f"this provider cannot transmit reasoning effort {normalized.value}"
            )
        return dict(fragment)

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response for the supplied request."""

        if not isinstance(request, LLMRequest):
            raise ProviderError("Request must be an LLMRequest")

        if not request.prompt.strip():
            raise ProviderError("Prompt cannot be empty")

        max_tokens = self._max_tokens(request)

        (
            content,
            prompt_tokens,
            completion_tokens,
            finish_reason,
        ) = self.client.generate(
            model=self.model,
            system=request.system_prompt,
            prompt=request.prompt,
            temperature=request.temperature,
            max_tokens=max_tokens,
        )

        return LLMResponse(
            content=content,
            model=self.model,
            usage_prompt_tokens=prompt_tokens,
            usage_completion_tokens=completion_tokens,
            finish_reason=finish_reason,
            metadata={
                "source": self.provider_id,
                "provider_id": self.provider_id,
                "api_style": "chat_completions",
            },
        )

    def stream(
        self, request: LLMRequest, *, cancel_event: Event | None = None
    ) -> Iterator[str]:
        """Stream provider-independent content deltas for the supplied request."""

        if not isinstance(request, LLMRequest):
            raise ProviderError("Request must be an LLMRequest")
        if not request.prompt.strip():
            raise ProviderError("Prompt cannot be empty")

        yield from self.client.stream_chat(
            model=self.model,
            messages=self._stream_messages(request),
            temperature=request.temperature,
            max_tokens=self._max_tokens(request),
            cancel_event=cancel_event,
            request_extras=self.reasoning_effort_extras(request.reasoning_effort),
        )

    @staticmethod
    def _stream_messages(
        request: LLMRequest,
    ) -> list[dict[str, Any]]:
        """Serialize canonical image inputs as multimodal content parts."""

        messages: list[dict[str, Any]] = [
            {
                "role": item["role"],
                "content": item["content"],
            }
            for item in request.transcript()
        ]

        if not request.images:
            return messages

        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": request.prompt,
            }
        ]

        for image in request.images:
            encoded = base64.b64encode(
                image.data
            ).decode("ascii")

            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": (
                            f"data:{image.media_type};"
                            f"base64,{encoded}"
                        )
                    },
                }
            )

        messages[-1] = {
            "role": "user",
            "content": content,
        }

        return messages

    @staticmethod
    def _max_tokens(request: LLMRequest) -> int | None:
        """Resolve an optional integer max_tokens from request metadata."""

        max_tokens = request.metadata.get("max_tokens")
        if max_tokens is None:
            return None
        try:
            return int(max_tokens)
        except (TypeError, ValueError) as error:
            raise ProviderError("max_tokens must be an integer") from error
