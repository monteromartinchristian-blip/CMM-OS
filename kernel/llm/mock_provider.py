"""Simple mock provider for testing the LLM abstraction layer."""

from __future__ import annotations

from kernel.llm.models import LLMRequest, LLMResponse
from kernel.llm.provider import LLMProvider


class MockProvider(LLMProvider):
    """Return a deterministic mock response without any external dependency."""

    def __init__(self, response: str) -> None:
        self.response = response

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Return a mock LLM response for the supplied request."""

        return LLMResponse(
            content=self.response,
            model="mock",
            usage_prompt_tokens=0,
            usage_completion_tokens=0,
        )
