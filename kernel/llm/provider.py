"""Abstract base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from kernel.llm.models import LLMRequest, LLMResponse


class LLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response for the given request."""

        raise NotImplementedError
