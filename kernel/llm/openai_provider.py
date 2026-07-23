"""OpenAI-backed LLM provider implementation."""

from __future__ import annotations

from kernel.llm.clients.openai_client import OpenAIClient
from kernel.llm.exceptions import ProviderError
from kernel.llm.models import LLMRequest, LLMResponse
from kernel.llm.provider import LLMProvider


class OpenAIProvider(LLMProvider):
    """Generate responses through the OpenAI Responses API."""

    def __init__(
        self,
        client: OpenAIClient | None = None,
        model: str = "gpt-5-mini",
    ) -> None:
        self.client = client or OpenAIClient()
        self.model = model

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response for the supplied request."""

        return self.complete(request)

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Delegate generation to the OpenAI client."""

        if not isinstance(request, LLMRequest):
            raise ProviderError("Request must be an LLMRequest")

        if not request.prompt.strip():
            raise ProviderError("Prompt cannot be empty")

        max_tokens = request.metadata.get("max_tokens")
        max_output_tokens = None
        if max_tokens is not None:
            try:
                max_output_tokens = int(max_tokens)
            except (TypeError, ValueError) as error:
                raise ProviderError("max_tokens must be an integer") from error

        content, prompt_tokens, completion_tokens, status = self.client.generate(
            model=self.model,
            system=request.system_prompt,
            prompt=request.prompt,
            temperature=request.temperature,
            max_output_tokens=max_output_tokens,
        )

        return LLMResponse(
            content=content,
            model=self.model,
            usage_prompt_tokens=prompt_tokens,
            usage_completion_tokens=completion_tokens,
            finish_reason=status,
            metadata={"source": "openai"},
        )
