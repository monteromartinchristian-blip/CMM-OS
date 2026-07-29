"""Provider implementation for OpenAI-compatible Chat Completions APIs."""

from __future__ import annotations

from typing import Protocol

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


class OpenAICompatibleProvider(LLMProvider):
    """Generate responses through a provider-specific compatible client."""

    def __init__(
        self,
        *,
        provider_id: str,
        client: OpenAICompatibleClientProtocol,
        model: str,
    ) -> None:
        normalized_provider_id = provider_id.strip().lower()
        if not normalized_provider_id:
            raise ProviderError("provider_id cannot be empty")
        if not model.strip():
            raise ProviderError("model cannot be empty")

        self.provider_id = normalized_provider_id
        self.client = client
        self.model = model.strip()

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response for the supplied request."""

        if not isinstance(request, LLMRequest):
            raise ProviderError("Request must be an LLMRequest")

        if not request.prompt.strip():
            raise ProviderError("Prompt cannot be empty")

        max_tokens = request.metadata.get("max_tokens")
        resolved_max_tokens = None
        if max_tokens is not None:
            try:
                resolved_max_tokens = int(max_tokens)
            except (TypeError, ValueError) as error:
                raise ProviderError(
                    "max_tokens must be an integer"
                ) from error

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
            max_tokens=resolved_max_tokens,
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
