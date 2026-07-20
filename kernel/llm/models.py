"""Data models for LLM requests and responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """Represents a request to be sent to an LLM provider."""

    prompt: str
    system_prompt: str | None = None
    temperature: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Represents the response returned by an LLM provider."""

    content: str
    model: str
    usage_prompt_tokens: int = 0
    usage_completion_tokens: int = 0
    finish_reason: str = "stop"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        """Return the total number of tokens consumed by the request."""

        return self.usage_prompt_tokens + self.usage_completion_tokens
