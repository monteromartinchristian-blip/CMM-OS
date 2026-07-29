"""Provider and model capability descriptors."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Transport-level capabilities exposed by a provider API."""

    chat_completions: bool = False
    responses_api: bool = False
    streaming: bool = False
    embeddings: bool = False


@dataclass(frozen=True, slots=True)
class ModelCapabilities:
    """Capabilities declared for a concrete model."""

    reasoning: bool = False
    tool_calling: bool = False
    structured_output: bool = False
    json_mode: bool = False
    json_schema: bool = False
    vision: bool = False
    audio_input: bool = False
    audio_output: bool = False
    embeddings: bool = False
