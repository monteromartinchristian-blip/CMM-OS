"""Generic LLM provider abstraction for planner integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract interface for text completion providers."""

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """Return a completion for the supplied prompt."""

