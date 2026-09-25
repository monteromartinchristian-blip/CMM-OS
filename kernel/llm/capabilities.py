"""Provider and model capability descriptors."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReasoningEffort(str, Enum):
    """Closed, provider-independent reasoning-effort level (Phase 11.21).

    ``DEFAULT`` means "impose no explicit effort override". The remaining
    members are canonical levels. Provider-native names (for example a
    ``minimal`` or ``thinking`` setting) are translated inside a provider
    adapter and never appear in this contract.
    """

    DEFAULT = "default"
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTRA_HIGH = "extra_high"


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
