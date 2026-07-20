"""Ollama-backed LLM provider implementation."""

from __future__ import annotations

from kernel.llm.clients.ollama_client import OllamaClient
from kernel.llm.exceptions import ProviderError
from kernel.llm.models import LLMRequest, LLMResponse
from kernel.llm.provider import LLMProvider


class OllamaProvider(LLMProvider):
    """Generate responses by delegating to an Ollama client."""

    def __init__(self, client: OllamaClient | None = None, model: str = "qwen3:30b-a3b") -> None:
        self.client = client or OllamaClient()
        self.model = model

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response for the supplied request."""

        return self.complete(request)

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Delegate the request to Ollama and convert it to an LLMResponse."""

        if not isinstance(request, LLMRequest):
            raise ProviderError("Request must be an LLMRequest")

        if not request.prompt.strip():
            raise ProviderError("Prompt cannot be empty")

        max_tokens = request.metadata.get("max_tokens")
        num_predict = None
        if max_tokens is not None:
            try:
                num_predict = int(max_tokens)
            except (TypeError, ValueError) as exc:
                raise ProviderError("max_tokens must be an integer") from exc

        try:
            content = self.client.generate(
                model=self.model,
                system=request.system_prompt,
                prompt=request.prompt,
                temperature=request.temperature,
                num_predict=num_predict,
            )
        except ProviderError:
            raise

        if not isinstance(content, str) or not content.strip():
            raise ProviderError("Ollama response was empty")

        return LLMResponse(
            content=content,
            model=self.model,
            usage_prompt_tokens=0,
            usage_completion_tokens=0,
            finish_reason="stop",
            metadata={"source": "ollama"},
        )
