"""Capability descriptors for LLM providers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Features supported by an LLM provider."""

    chat_completions: bool = True
    responses_api: bool = False

    streaming: bool = True
    tool_calling: bool = True
    vision: bool = False
    reasoning: bool = False

    json_mode: bool = True
    json_schema: bool = True

    embeddings: bool = False

    audio_input: bool = False
    audio_output: bool = False

    max_context_tokens: int | None = None

    local: bool = False
