"""Helpers for building prompt payloads for future LLM integrations."""

from __future__ import annotations

from kernel.llm.models import LLMRequest
from kernel.planner.context import PlanningContext


class PromptBuilder:
    """Build simple prompt payloads or LLM requests from a planning context."""

    def __init__(self, system_prompt: str | None = None, user_prompt: str | None = None) -> None:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt

    def build_system_prompt(self) -> str:
        """Return the configured system prompt."""

        return self.system_prompt or ""

    def build_user_prompt(self) -> str:
        """Return the configured user prompt."""

        return self.user_prompt or ""

    def build(self, context: PlanningContext | None = None) -> LLMRequest | str:
        """Build an LLM request from a planning context or a simple text prompt."""

        if context is None:
            parts = [part for part in (self.build_system_prompt(), self.build_user_prompt()) if part]
            return "\n\n".join(parts)

        return LLMRequest(
            prompt=context.intent,
            system_prompt=self.build_system_prompt(),
        )
