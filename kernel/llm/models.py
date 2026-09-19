"""Data models for LLM requests and responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ChatRole = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class ChatTurn:
    """One conversational turn inside an LLM request transcript."""

    role: ChatRole
    content: str

    def __post_init__(self) -> None:
        if self.role not in ("system", "user", "assistant"):
            raise ValueError(f"Unsupported chat role: {self.role!r}")
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("ChatTurn content must be non-empty")


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """Represents a request to be sent to an LLM provider."""

    prompt: str
    system_prompt: str | None = None
    temperature: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    history: tuple[ChatTurn, ...] = ()

    def transcript(self) -> list[dict[str, str]]:
        """Return the provider-independent chat transcript for this request.

        The order is canonical: an optional system turn, the prior conversation
        turns, then the current user prompt.
        """

        messages: list[dict[str, str]] = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.extend(
            {"role": turn.role, "content": turn.content} for turn in self.history
        )
        messages.append({"role": "user", "content": self.prompt})
        return messages


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
