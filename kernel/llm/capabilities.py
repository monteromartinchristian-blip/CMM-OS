"""Provider and model capability descriptors."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ReasoningEffort(str, Enum):
    """Closed, provider-independent reasoning-effort level.

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
    MAX = "max"


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Transport-level capabilities exposed by a provider API."""

    chat_completions: bool = False
    responses_api: bool = False
    streaming: bool = False
    embeddings: bool = False


@dataclass(frozen=True, slots=True)
class ModelCapabilities:
    """Capabilities declared for a concrete model.

    The final three fields are a strictly additive seam: they default to
    "unknown/unsupported" so every pre-existing construction and every existing
    test keeps its exact previous meaning.  Capability truth is always explicit
    here — never inferred from a model name.
    """

    reasoning: bool = False
    tool_calling: bool = False
    structured_output: bool = False
    json_mode: bool = False
    json_schema: bool = False
    vision: bool = False
    audio_input: bool = False
    audio_output: bool = False
    embeddings: bool = False

    reasoning_efforts: tuple[ReasoningEffort, ...] = ()
    document_media_types: tuple[str, ...] = ()
    streaming: bool = False

    def __post_init__(self) -> None:
        efforts: list[ReasoningEffort] = []
        for effort in self.reasoning_efforts:
            normalized = ReasoningEffort(effort)
            if normalized in efforts:
                raise ValueError("reasoning_efforts must be unique")
            efforts.append(normalized)
        object.__setattr__(self, "reasoning_efforts", tuple(efforts))

        media_types: list[str] = []
        for media_type in self.document_media_types:
            if not isinstance(media_type, str):
                raise TypeError("document_media_types must contain strings")
            normalized_type = media_type.strip().lower()
            if not normalized_type or "/" not in normalized_type:
                raise ValueError(
                    "document media types must be non-empty type/subtype values"
                )
            if normalized_type in media_types:
                continue
            media_types.append(normalized_type)
        object.__setattr__(self, "document_media_types", tuple(media_types))

    def supports_reasoning_effort(self, effort: ReasoningEffort | str) -> bool:
        """Return whether the model explicitly supports ``effort``.

        ``DEFAULT`` means "no explicit override" and is always acceptable; it is
        never stored in the declared effort set.  Every other level must be
        declared, so an unknown effort fails closed.
        """

        normalized = ReasoningEffort(effort)
        if normalized is ReasoningEffort.DEFAULT:
            return True
        return normalized in self.reasoning_efforts

    def supports_document_media_type(self, media_type: str) -> bool:
        """Return whether the model explicitly accepts ``media_type`` documents."""

        if not isinstance(media_type, str):
            raise TypeError("media_type must be a string")
        return media_type.strip().lower() in self.document_media_types
