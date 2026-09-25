"""Canonical provider-independent Model Gateway contracts (Phase 11.21).

This module owns the *shape* of a model call: inputs, tools, structured-output
requirements, the request/response pair, normalized usage and latency facts, and
the normalized provider-token stream events.

Two safety rules are enforced here rather than left to callers:

1. **Content never leaks through ordinary serialization.** Image and document
   bytes are carried for the provider adapter but ``to_dict()`` exposes only
   safe facts (kind, media type, byte length, content digest, display name).
2. **Metadata is a closed safe boundary.** Public metadata must be JSON-safe and
   secret-free; a secret-shaped key or binary payload fails closed at
   construction time.

Reasoning effort is the closed :class:`~kernel.llm.capabilities.ReasoningEffort`
enum.  Provider-native effort names are translated inside provider adapters and
never appear in these contracts.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any, Protocol, runtime_checkable

from kernel.llm.capabilities import ReasoningEffort

__all__ = [
    "CANONICAL_DOCUMENT_MEDIA_TYPES",
    "CANONICAL_MODEL_CAPABILITIES",
    "TERMINAL_STREAM_EVENT_TYPES",
    "InMemoryModelExecutionEvidenceSink",
    "InputModality",
    "InputPartKind",
    "ModelExecutionEvidenceSink",
    "ModelExecutionFacts",
    "ModelGatewayRequest",
    "ModelGatewayResponse",
    "ModelInputPart",
    "ModelSelectionMode",
    "ModelStreamEvent",
    "ModelStreamEventType",
    "ModelToolCall",
    "ModelToolDefinition",
    "ModelUsage",
    "PrivacyEgressDecision",
    "PrivacyEgressGate",
    "ReasoningEffort",
    "StructuredOutputRequirement",
    "ensure_json_safe_mapping",
    "ensure_safe_metadata",
    "screen_provider_request_metadata",
    "to_plain_json",
]


#: Document media types Phase 11.21 must transport as real content.  A model
#: declares which of these (or which additional media types) it truly accepts;
#: nothing is inferred from a model name.
CANONICAL_DOCUMENT_MEDIA_TYPES: tuple[str, ...] = (
    "application/pdf",
    "text/plain",
    "text/markdown",
)

#: Closed canonical capability names a caller may require.  ``document`` maps to
#: declared document media types; every other name maps to the matching
#: canonical model-capability field.
CANONICAL_MODEL_CAPABILITIES: tuple[str, ...] = (
    "reasoning",
    "tool_calling",
    "structured_output",
    "json_mode",
    "json_schema",
    "vision",
    "document",
    "streaming",
    "audio_input",
    "audio_output",
    "embeddings",
)

_SENSITIVE_METADATA_KEYS = frozenset(
    {
        "apikey",
        "api_key",
        "access_key",
        "auth",
        "authorization",
        "cookie",
        "credential",
        "credentials",
        "password",
        "passwd",
        "private_key",
        "secret",
        "secrets",
        "session_key",
        "token",
    }
)

_SENSITIVE_METADATA_KEY_TOKENS = frozenset(
    {
        "apikey",
        "authorization",
        "cookie",
        "credential",
        "credentials",
        "password",
        "passwd",
        "secret",
        "secrets",
        "token",
    }
)


def _is_sensitive_key(key: str) -> bool:
    lowered = key.strip().lower()
    if lowered in _SENSITIVE_METADATA_KEYS:
        return True
    segments = {segment for segment in _split_key(lowered) if segment}
    return bool(segments & _SENSITIVE_METADATA_KEY_TOKENS)


def _split_key(key: str) -> tuple[str, ...]:
    normalized = key
    for separator in ("-", ".", " ", "/", ":"):
        normalized = normalized.replace(separator, "_")
    return tuple(normalized.split("_"))


def ensure_json_safe_mapping(
    value: Mapping[str, Any],
    *,
    label: str,
) -> Mapping[str, Any]:
    """Return an immutable, JSON-safe copy of ``value`` or fail closed.

    Rejects non-string keys, non-finite numbers, binary values and arbitrary
    objects.  Nested mappings and sequences are normalized so a caller cannot
    smuggle a mutable or unserializable value into a public contract.
    """

    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")

    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError(f"{label} keys must be strings")
        normalized[key] = _ensure_json_safe_value(item, label=f"{label}.{key}")
    return MappingProxyType(normalized)


def _ensure_json_safe_value(value: Any, *, label: str) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError(f"{label} must be a finite number")
        return value
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError(f"{label} must not carry binary data")
    if isinstance(value, Mapping):
        return ensure_json_safe_mapping(value, label=label)
    if isinstance(value, (list, tuple)):
        return tuple(
            _ensure_json_safe_value(item, label=f"{label}[{index}]")
            for index, item in enumerate(value)
        )
    raise TypeError(f"{label} must be a JSON-safe value, not {type(value).__name__}")


def _ensure_safe_metadata_value(value: Any, *, label: str) -> Any:
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"{label} keys must be strings")
            if _is_sensitive_key(key):
                raise ValueError(f"{label} key '{key}' is not permitted")
            normalized[key] = _ensure_safe_metadata_value(item, label=f"{label}.{key}")
        return MappingProxyType(normalized)
    if isinstance(value, (list, tuple)):
        return tuple(
            _ensure_safe_metadata_value(item, label=f"{label}[{index}]")
            for index, item in enumerate(value)
        )
    if isinstance(value, (bytes, bytearray, memoryview)):
        raise TypeError(f"{label} must not carry binary data")
    if value is None or isinstance(value, (bool, int, str, Decimal)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError(f"{label} must be a finite number")
        return value
    raise TypeError(f"{label} must be a JSON-safe value, not {type(value).__name__}")


def ensure_safe_metadata(
    value: Mapping[str, Any],
    *,
    label: str = "metadata",
) -> Mapping[str, Any]:
    """Return screened, JSON-safe metadata, rejecting secret-shaped keys.

    Screening is recursive: a secret-shaped key nested inside a metadata
    mapping fails closed exactly like a top-level one.
    """

    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping")
    return _ensure_safe_metadata_value(value, label=label)


def screen_provider_request_metadata(
    value: Mapping[str, Any],
    *,
    label: str = "provider request metadata",
) -> Mapping[str, Any]:
    """Screen adapter-facing metadata with the same boundary as public metadata."""

    return ensure_safe_metadata(value, label=label)


def to_plain_json(value: Any) -> Any:
    """Convert a frozen contract value into plain JSON-compatible structures."""

    if isinstance(value, Mapping):
        return {str(key): to_plain_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_plain_json(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def _require_identifier(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _require_optional_identifier(value: Any, *, label: str) -> str | None:
    if value is None:
        return None
    return _require_identifier(value, label=label)


class ModelSelectionMode(str, Enum):
    """How the model for a call was chosen."""

    EXPLICIT = "explicit"
    AUTO = "auto"


class InputPartKind(str, Enum):
    """Canonical provider-independent input part kinds."""

    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"


#: Canonical alias: a "modality" is the kind of an input part.
InputModality = InputPartKind


class ModelStreamEventType(str, Enum):
    """Normalized provider-token stream event types."""

    STARTED = "started"
    CONTENT_DELTA = "content_delta"
    TOOL_CALL_DELTA = "tool_call_delta"
    USAGE = "usage"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


#: Exactly one of these terminates any normalized stream.
TERMINAL_STREAM_EVENT_TYPES = frozenset(
    {
        ModelStreamEventType.COMPLETED,
        ModelStreamEventType.CANCELLED,
        ModelStreamEventType.ERROR,
    }
)


# ── Input parts ──────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ModelInputPart:
    """One authorized input part carrying real content.

    ``content`` is the actual authorized payload.  It is deliberately excluded
    from :meth:`to_dict`: public serialization exposes only safe facts.  The
    content digest is always derived from the content, so a caller cannot forge
    a digest that disagrees with the payload.
    """

    kind: InputPartKind
    content: bytes = b""
    media_type: str | None = None
    display_name: str | None = None
    content_digest: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        kind = InputPartKind(self.kind)
        object.__setattr__(self, "kind", kind)

        if not isinstance(self.content, (bytes, bytearray, memoryview)):
            raise TypeError("content must be bytes")
        content = bytes(self.content)
        if not content:
            raise ValueError(f"{kind.value} input content must not be empty")
        object.__setattr__(self, "content", content)

        media_type = self.media_type
        if media_type is not None:
            media_type = _require_identifier(media_type, label="media_type")
        if kind is InputPartKind.TEXT:
            if media_type is None:
                media_type = "text/plain"
            if not media_type.startswith("text/"):
                raise ValueError("text input media_type must be a text media type")
            try:
                content.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ValueError("text input content must be valid UTF-8") from error
        elif kind is InputPartKind.IMAGE:
            if media_type is None or not media_type.startswith("image/"):
                raise ValueError("image input requires an image media type")
        else:
            if media_type is None or "/" not in media_type:
                raise ValueError("document input requires a media type")
            if media_type.startswith("image/"):
                raise ValueError(
                    "document input media type must not be an image media type"
                )
        object.__setattr__(self, "media_type", media_type)

        display_name = self.display_name
        if display_name is not None:
            display_name = _require_identifier(display_name, label="display_name")
            if _looks_like_path_or_url(display_name):
                raise ValueError(
                    "display_name must be a safe display name, not a path or URL"
                )
        object.__setattr__(self, "display_name", display_name)

        digest = hashlib.sha256(content).hexdigest()
        if self.content_digest is not None and self.content_digest != digest:
            raise ValueError(
                "content_digest must be the digest of the supplied content"
            )
        object.__setattr__(self, "content_digest", digest)

        object.__setattr__(
            self,
            "metadata",
            ensure_safe_metadata(self.metadata, label=f"{kind.value} metadata"),
        )

    @property
    def byte_length(self) -> int:
        """Return the exact number of authorized content bytes carried."""

        return len(self.content)

    @property
    def text(self) -> str | None:
        """Return the decoded text for a TEXT part, else ``None``."""

        if self.kind is not InputPartKind.TEXT:
            return None
        return self.content.decode("utf-8")

    @classmethod
    def text_part(
        cls,
        text: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> ModelInputPart:
        """Build a TEXT part from a string."""

        if not isinstance(text, str):
            raise TypeError("text must be a string")
        return cls(
            kind=InputPartKind.TEXT,
            content=text.encode("utf-8"),
            media_type="text/plain",
            metadata=metadata or {},
        )

    @classmethod
    def image_part(
        cls,
        content: bytes,
        media_type: str,
        *,
        display_name: str | None = None,
        content_digest: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ModelInputPart:
        """Build an IMAGE part carrying real authorized image bytes."""

        return cls(
            kind=InputPartKind.IMAGE,
            content=content,
            media_type=media_type,
            display_name=display_name,
            content_digest=content_digest,
            metadata=metadata or {},
        )

    @classmethod
    def document_part(
        cls,
        content: bytes,
        media_type: str,
        *,
        display_name: str | None = None,
        content_digest: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ModelInputPart:
        """Build a DOCUMENT part carrying real authorized document bytes."""

        return cls(
            kind=InputPartKind.DOCUMENT,
            content=content,
            media_type=media_type,
            display_name=display_name,
            content_digest=content_digest,
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        """Return safe public facts; raw content is never included."""

        return {
            "kind": self.kind.value,
            "media_type": self.media_type,
            "byte_length": self.byte_length,
            "content_digest": self.content_digest,
            "display_name": self.display_name,
            "metadata": to_plain_json(self.metadata),
        }


def _looks_like_path_or_url(value: str) -> bool:
    if "://" in value:
        return True
    if value.startswith(("/", "\\", "~")):
        return True
    if ".." in value.split("/") or ".." in value.split("\\"):
        return True
    return bool(len(value) > 1 and value[1] == ":")


# ── Tool contracts ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ModelToolDefinition:
    """A canonical tool declaration.

    It declares *only* identity, description and input schema.  There is no
    callback, handler or executor field: a tool definition can never carry
    execution authority.
    """

    tool_id: str
    description: str = ""
    input_schema: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "tool_id", _require_identifier(self.tool_id, label="tool_id")
        )
        if not isinstance(self.description, str):
            raise TypeError("description must be a string")
        object.__setattr__(
            self,
            "input_schema",
            ensure_json_safe_mapping(self.input_schema, label="input_schema"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the safe public representation of this declaration."""

        return {
            "tool_id": self.tool_id,
            "description": self.description,
            "input_schema": to_plain_json(self.input_schema),
        }


@dataclass(frozen=True, slots=True)
class ModelToolCall:
    """One provider-generated tool call.

    A tool call is a *request for authority*, never authority itself: this
    contract carries no permission, approval or execution state.
    """

    call_id: str
    tool_id: str
    arguments: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "call_id", _require_identifier(self.call_id, label="call_id")
        )
        object.__setattr__(
            self, "tool_id", _require_identifier(self.tool_id, label="tool_id")
        )
        object.__setattr__(
            self,
            "arguments",
            ensure_json_safe_mapping(self.arguments, label="tool call arguments"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the safe public representation of this call."""

        return {
            "call_id": self.call_id,
            "tool_id": self.tool_id,
            "arguments": to_plain_json(self.arguments),
        }


# ── Structured output ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class StructuredOutputRequirement:
    """A provider-independent structured-output requirement.

    The gateway translates the schema to a provider-native form and normalizes
    the returned value.  Semantic and domain validity remain owned by the
    canonical Phase 7 validation system.
    """

    required: bool = True
    schema: Mapping[str, Any] | None = None
    schema_id: str | None = None
    schema_version: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.required, bool):
            raise TypeError("required must be a bool")
        if self.schema is not None:
            object.__setattr__(
                self,
                "schema",
                ensure_json_safe_mapping(self.schema, label="structured schema"),
            )
        object.__setattr__(
            self,
            "schema_id",
            _require_optional_identifier(self.schema_id, label="schema_id"),
        )
        object.__setattr__(
            self,
            "schema_version",
            _require_optional_identifier(self.schema_version, label="schema_version"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the safe public representation of this requirement."""

        return {
            "required": self.required,
            "schema": to_plain_json(self.schema) if self.schema is not None else None,
            "schema_id": self.schema_id,
            "schema_version": self.schema_version,
        }


# ── Usage and execution facts ────────────────────────────────────────────────


def _optional_count(value: Any, *, label: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{label} must be an integer or None")
    if value < 0:
        raise ValueError(f"{label} cannot be negative")
    return value


@dataclass(frozen=True, slots=True)
class ModelUsage:
    """Factual per-call usage accounting.

    Unknown provider metrics stay ``None``.  Phase 11.21 never fabricates a
    zero for a metric the provider did not report.
    """

    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_tokens: int | None = None
    cost: Decimal | None = None
    cost_source: str | None = None
    currency: str = "USD"

    def __post_init__(self) -> None:
        for name in ("input_tokens", "output_tokens", "cached_tokens"):
            object.__setattr__(
                self,
                name,
                _optional_count(getattr(self, name), label=name),
            )

        if self.cost is None:
            if self.cost_source is not None:
                raise ValueError("cost_source requires a cost value")
        else:
            if not isinstance(self.cost, Decimal):
                raise TypeError("cost must be a Decimal or None")
            if self.cost < 0:
                raise ValueError("cost cannot be negative")
            if self.cost_source not in {"provider_reported", "catalog_derived"}:
                raise ValueError(
                    "cost requires cost_source 'provider_reported' or 'catalog_derived'"
                )
        if self.cost_source is not None and self.cost_source not in {
            "provider_reported",
            "catalog_derived",
        }:
            raise ValueError(
                "cost_source must be 'provider_reported' or 'catalog_derived'"
            )

        object.__setattr__(
            self, "currency", _require_identifier(self.currency, label="currency")
        )

    @property
    def total_tokens(self) -> int | None:
        """Return the total token count, or ``None`` when either side is unknown."""

        if self.input_tokens is None or self.output_tokens is None:
            return None
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict[str, Any]:
        """Return the safe public representation of these facts."""

        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_tokens": self.cached_tokens,
            "cost": None if self.cost is None else str(self.cost),
            "cost_source": self.cost_source,
            "currency": self.currency,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True, slots=True)
class ModelExecutionFacts:
    """Safe, structured evidence for one model call.

    This is the canonical evidence object.  It deliberately carries no prompt,
    no attachment content, no credential and no hidden reasoning.
    """

    request_id: str
    provider_id: str
    model_id: str
    selection_mode: ModelSelectionMode
    success: bool
    privacy_decision: str
    capability_decision: str = "verified"
    requested_reasoning_effort: ReasoningEffort = ReasoningEffort.DEFAULT
    effective_reasoning_effort: ReasoningEffort = ReasoningEffort.DEFAULT
    reasoning_used: bool = False
    input_modalities: tuple[str, ...] = ()
    tool_use: bool = False
    structured_output_use: bool = False
    streamed: bool = False
    cancelled: bool = False
    timed_out: bool = False
    retry_count: int = 0
    fallback_index: int = 0
    fallback_used: bool = False
    fallback_skipped: tuple[str, ...] = ()
    usage: ModelUsage = field(default_factory=ModelUsage)
    latency_ms: int | None = None
    finish_reason: str | None = None
    error_code: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _require_identifier(self.request_id, label="request_id")
        )
        object.__setattr__(
            self,
            "provider_id",
            _require_identifier(self.provider_id, label="provider_id"),
        )
        object.__setattr__(
            self, "model_id", _require_identifier(self.model_id, label="model_id")
        )
        object.__setattr__(
            self,
            "selection_mode",
            ModelSelectionMode(self.selection_mode),
        )
        object.__setattr__(
            self,
            "capability_decision",
            _require_identifier(self.capability_decision, label="capability_decision"),
        )
        object.__setattr__(
            self,
            "privacy_decision",
            _require_identifier(self.privacy_decision, label="privacy_decision"),
        )
        object.__setattr__(
            self,
            "requested_reasoning_effort",
            ReasoningEffort(self.requested_reasoning_effort),
        )
        object.__setattr__(
            self,
            "effective_reasoning_effort",
            ReasoningEffort(self.effective_reasoning_effort),
        )

        if not isinstance(self.usage, ModelUsage):
            raise TypeError("usage must be a ModelUsage")

        modalities = tuple(self.input_modalities)
        for modality in modalities:
            InputPartKind(modality)
        object.__setattr__(self, "input_modalities", tuple(dict.fromkeys(modalities)))

        if self.retry_count < 0:
            raise ValueError("retry_count cannot be negative")
        if self.fallback_index < 0:
            raise ValueError("fallback_index cannot be negative")
        if self.fallback_used and self.fallback_index < 1:
            raise ValueError("fallback_used requires a fallback_index >= 1")
        if self.latency_ms is not None and self.latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")
        if self.success and self.error_code is not None:
            raise ValueError("a successful call cannot carry an error_code")
        object.__setattr__(
            self,
            "fallback_skipped",
            tuple(str(entry) for entry in self.fallback_skipped),
        )
        if self.finish_reason is not None:
            object.__setattr__(
                self,
                "finish_reason",
                _require_identifier(self.finish_reason, label="finish_reason"),
            )
        if self.error_code is not None:
            object.__setattr__(
                self,
                "error_code",
                _require_identifier(self.error_code, label="error_code"),
            )
        object.__setattr__(
            self,
            "metadata",
            ensure_safe_metadata(self.metadata, label="execution facts metadata"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the safe public evidence record."""

        return {
            "request_id": self.request_id,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "selection_mode": self.selection_mode.value,
            "success": self.success,
            "capability_decision": self.capability_decision,
            "privacy_decision": self.privacy_decision,
            "requested_reasoning_effort": self.requested_reasoning_effort.value,
            "effective_reasoning_effort": self.effective_reasoning_effort.value,
            "reasoning_used": self.reasoning_used,
            "input_modalities": list(self.input_modalities),
            "tool_use": self.tool_use,
            "structured_output_use": self.structured_output_use,
            "streamed": self.streamed,
            "cancelled": self.cancelled,
            "timed_out": self.timed_out,
            "retry_count": self.retry_count,
            "fallback_index": self.fallback_index,
            "fallback_used": self.fallback_used,
            "fallback_skipped": list(self.fallback_skipped),
            "usage": self.usage.to_dict(),
            "latency_ms": self.latency_ms,
            "finish_reason": self.finish_reason,
            "error_code": self.error_code,
            "metadata": to_plain_json(self.metadata),
        }


@runtime_checkable
class ModelExecutionEvidenceSink(Protocol):
    """Injected seam that receives safe model-call evidence."""

    def record(self, facts: ModelExecutionFacts) -> None:
        """Record one safe evidence record."""


class InMemoryModelExecutionEvidenceSink:
    """Official in-memory evidence sink used by tests and local runtimes.

    It intentionally persists nothing beyond the process: Phase 11.21 must not
    create the future Phase 11.44 model usage audit store.
    """

    def __init__(self) -> None:
        self._records: list[ModelExecutionFacts] = []

    def record(self, facts: ModelExecutionFacts) -> None:
        """Append one safe evidence record."""

        if not isinstance(facts, ModelExecutionFacts):
            raise TypeError("facts must be a ModelExecutionFacts instance")
        self._records.append(facts)

    @property
    def records(self) -> tuple[ModelExecutionFacts, ...]:
        """Return every recorded fact in call order."""

        return tuple(self._records)

    def clear(self) -> None:
        """Drop every recorded fact."""

        self._records.clear()


# ── Privacy egress boundary ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PrivacyEgressDecision:
    """One safe, canonical privacy decision about model egress.

    It is produced by an injected :class:`PrivacyEgressGate` implemented over
    the canonical cognitive privacy evaluator; the gateway only reads it.
    """

    allowed: bool
    reason_code: str
    requires_approval: bool = False
    requires_redaction: bool = False
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.allowed, bool):
            raise TypeError("allowed must be a bool")
        object.__setattr__(
            self,
            "reason_code",
            _require_identifier(self.reason_code, label="reason_code"),
        )
        object.__setattr__(
            self,
            "details",
            ensure_safe_metadata(self.details, label="privacy decision details"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the safe public representation of this decision."""

        return {
            "allowed": self.allowed,
            "reason_code": self.reason_code,
            "requires_approval": self.requires_approval,
            "requires_redaction": self.requires_redaction,
            "details": to_plain_json(self.details),
        }


@runtime_checkable
class PrivacyEgressGate(Protocol):
    """Injected canonical privacy authority consulted before provider egress.

    Implementations delegate to the canonical cognitive privacy evaluator.  The
    gateway treats ``privacy`` as opaque: it never inspects or rewrites it.
    """

    def evaluate_egress(
        self,
        *,
        privacy: object | None,
        provider_id: str,
        is_remote: bool,
        is_premium: bool = False,
    ) -> PrivacyEgressDecision:
        """Return the canonical decision for transmitting content to a provider."""


# ── Request / response ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ModelGatewayRequest:
    """One immutable, provider-independent model-call request."""

    request_id: str
    model_id: str | None = None
    provider_id: str | None = None
    selection_mode: ModelSelectionMode = ModelSelectionMode.EXPLICIT
    input_parts: tuple[ModelInputPart, ...] = ()
    reasoning_effort: ReasoningEffort = ReasoningEffort.DEFAULT
    required_capabilities: tuple[str, ...] = ()
    tools: tuple[ModelToolDefinition, ...] = ()
    structured_output: StructuredOutputRequirement | None = None
    stream: bool = False
    timeout_seconds: float = 60.0
    privacy: object | None = None
    fallback_model_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _require_identifier(self.request_id, label="request_id")
        )
        object.__setattr__(
            self,
            "model_id",
            _require_optional_identifier(self.model_id, label="model_id"),
        )
        object.__setattr__(
            self,
            "provider_id",
            _require_optional_identifier(self.provider_id, label="provider_id"),
        )

        selection_mode = ModelSelectionMode(self.selection_mode)
        object.__setattr__(self, "selection_mode", selection_mode)
        if selection_mode is ModelSelectionMode.EXPLICIT and self.model_id is None:
            raise ValueError("explicit model selection requires a model_id")

        input_parts = tuple(self.input_parts)
        if not input_parts:
            raise ValueError("a model request requires at least one input part")
        for part in input_parts:
            if not isinstance(part, ModelInputPart):
                raise TypeError("input_parts must contain ModelInputPart values")
        object.__setattr__(self, "input_parts", input_parts)

        object.__setattr__(
            self, "reasoning_effort", ReasoningEffort(self.reasoning_effort)
        )

        required = tuple(self.required_capabilities)
        for capability in required:
            if capability not in CANONICAL_MODEL_CAPABILITIES:
                raise ValueError(f"unknown required capability: {capability!r}")
        object.__setattr__(
            self, "required_capabilities", tuple(dict.fromkeys(required))
        )

        tools = tuple(self.tools)
        for tool in tools:
            if not isinstance(tool, ModelToolDefinition):
                raise TypeError("tools must contain ModelToolDefinition values")
        tool_ids = [tool.tool_id for tool in tools]
        if len(tool_ids) != len(set(tool_ids)):
            raise ValueError("tool definitions must have unique tool_id values")
        object.__setattr__(self, "tools", tools)

        if self.structured_output is not None and not isinstance(
            self.structured_output, StructuredOutputRequirement
        ):
            raise TypeError(
                "structured_output must be a StructuredOutputRequirement or None"
            )

        if not isinstance(self.stream, bool):
            raise TypeError("stream must be a bool")

        timeout = self.timeout_seconds
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
            raise TypeError("timeout_seconds must be a number")
        timeout = float(timeout)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout_seconds must be a finite positive number")
        object.__setattr__(self, "timeout_seconds", timeout)

        fallbacks = tuple(self.fallback_model_ids)
        for candidate in fallbacks:
            _require_identifier(candidate, label="fallback_model_id")
        if len(fallbacks) != len(set(fallbacks)):
            raise ValueError("fallback_model_ids must be unique")
        object.__setattr__(self, "fallback_model_ids", fallbacks)

        object.__setattr__(
            self,
            "metadata",
            ensure_safe_metadata(self.metadata, label="request metadata"),
        )

    @property
    def input_modalities(self) -> tuple[str, ...]:
        """Return the distinct input modalities in stable first-seen order."""

        return tuple(dict.fromkeys(part.kind.value for part in self.input_parts))

    @property
    def has_image_input(self) -> bool:
        """Return whether any input part carries image content."""

        return any(part.kind is InputPartKind.IMAGE for part in self.input_parts)

    @property
    def has_document_input(self) -> bool:
        """Return whether any input part carries document content."""

        return any(part.kind is InputPartKind.DOCUMENT for part in self.input_parts)

    def to_dict(self) -> dict[str, Any]:
        """Return the safe public request description (never the raw content)."""

        return {
            "request_id": self.request_id,
            "model_id": self.model_id,
            "provider_id": self.provider_id,
            "selection_mode": self.selection_mode.value,
            "input_parts": [part.to_dict() for part in self.input_parts],
            "input_modalities": list(self.input_modalities),
            "reasoning_effort": self.reasoning_effort.value,
            "required_capabilities": list(self.required_capabilities),
            "tools": [tool.to_dict() for tool in self.tools],
            "structured_output": (
                self.structured_output.to_dict()
                if self.structured_output is not None
                else None
            ),
            "stream": self.stream,
            "timeout_seconds": self.timeout_seconds,
            "privacy_provided": self.privacy is not None,
            "fallback_model_ids": list(self.fallback_model_ids),
            "metadata": to_plain_json(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ModelGatewayResponse:
    """One normalized, provider-independent model-call response."""

    request_id: str
    provider_id: str
    model_id: str
    selection_mode: ModelSelectionMode
    content: str = ""
    structured_output: Mapping[str, Any] | None = None
    tool_calls: tuple[ModelToolCall, ...] = ()
    usage: ModelUsage = field(default_factory=ModelUsage)
    facts: ModelExecutionFacts | None = None
    finish_reason: str | None = None
    cancelled: bool = False
    error_code: str | None = None
    reasoning_used: bool = False
    effective_reasoning_effort: ReasoningEffort = ReasoningEffort.DEFAULT

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id", _require_identifier(self.request_id, label="request_id")
        )
        object.__setattr__(
            self,
            "provider_id",
            _require_identifier(self.provider_id, label="provider_id"),
        )
        object.__setattr__(
            self, "model_id", _require_identifier(self.model_id, label="model_id")
        )
        object.__setattr__(
            self, "selection_mode", ModelSelectionMode(self.selection_mode)
        )

        if not isinstance(self.content, str):
            raise TypeError("content must be a string")
        if self.structured_output is not None:
            object.__setattr__(
                self,
                "structured_output",
                ensure_json_safe_mapping(
                    self.structured_output, label="structured output"
                ),
            )

        tool_calls = tuple(self.tool_calls)
        for call in tool_calls:
            if not isinstance(call, ModelToolCall):
                raise TypeError("tool_calls must contain ModelToolCall values")
        object.__setattr__(self, "tool_calls", tool_calls)

        if not isinstance(self.usage, ModelUsage):
            raise TypeError("usage must be a ModelUsage")

        if self.facts is not None:
            if not isinstance(self.facts, ModelExecutionFacts):
                raise TypeError("facts must be a ModelExecutionFacts or None")
            if self.facts.request_id != self.request_id:
                raise ValueError("facts request_id must match the response")

        if self.cancelled and self.error_code is not None:
            raise ValueError("a cancelled response cannot also carry an error_code")
        if self.finish_reason is not None:
            object.__setattr__(
                self,
                "finish_reason",
                _require_identifier(self.finish_reason, label="finish_reason"),
            )
        if self.error_code is not None:
            object.__setattr__(
                self,
                "error_code",
                _require_identifier(self.error_code, label="error_code"),
            )
        object.__setattr__(
            self,
            "effective_reasoning_effort",
            ReasoningEffort(self.effective_reasoning_effort),
        )
        if not isinstance(self.reasoning_used, bool):
            raise TypeError("reasoning_used must be a bool")

    def to_dict(self) -> dict[str, Any]:
        """Return the safe public response representation."""

        return {
            "request_id": self.request_id,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "selection_mode": self.selection_mode.value,
            "content": self.content,
            "structured_output": (
                to_plain_json(self.structured_output)
                if self.structured_output is not None
                else None
            ),
            "tool_calls": [call.to_dict() for call in self.tool_calls],
            "usage": self.usage.to_dict(),
            "facts": self.facts.to_dict() if self.facts is not None else None,
            "finish_reason": self.finish_reason,
            "cancelled": self.cancelled,
            "error_code": self.error_code,
            "reasoning_used": self.reasoning_used,
            "effective_reasoning_effort": self.effective_reasoning_effort.value,
        }


# ── Normalized stream events ─────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ModelStreamEvent:
    """One normalized provider-token stream event.

    The contract has no field capable of carrying hidden chain-of-thought or a
    raw provider object; reasoning may only be described by the safe metadata
    fields below.
    """

    event_type: ModelStreamEventType
    request_id: str
    sequence: int
    content_delta: str | None = None
    tool_call: ModelToolCall | None = None
    usage: ModelUsage | None = None
    response: ModelGatewayResponse | None = None
    error_code: str | None = None
    provider_id: str | None = None
    model_id: str | None = None
    effective_reasoning_effort: ReasoningEffort = ReasoningEffort.DEFAULT
    reasoning_used: bool = False

    def __post_init__(self) -> None:
        event_type = ModelStreamEventType(self.event_type)
        object.__setattr__(self, "event_type", event_type)
        object.__setattr__(
            self, "request_id", _require_identifier(self.request_id, label="request_id")
        )
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool):
            raise TypeError("sequence must be an integer")
        if self.sequence < 0:
            raise ValueError("sequence cannot be negative")

        if self.content_delta is not None and (
            not isinstance(self.content_delta, str) or not self.content_delta
        ):
            raise ValueError("content_delta must be a non-empty string")
        if event_type is ModelStreamEventType.CONTENT_DELTA and (
            self.content_delta is None
        ):
            raise ValueError("a CONTENT_DELTA event requires content_delta")
        if event_type is ModelStreamEventType.TOOL_CALL_DELTA and (
            self.tool_call is None
        ):
            raise ValueError("a TOOL_CALL_DELTA event requires a normalized tool call")
        if self.tool_call is not None and not isinstance(self.tool_call, ModelToolCall):
            raise TypeError("tool_call must be a ModelToolCall or None")
        if self.usage is not None and not isinstance(self.usage, ModelUsage):
            raise TypeError("usage must be a ModelUsage or None")
        if self.response is not None and not isinstance(
            self.response, ModelGatewayResponse
        ):
            raise TypeError("response must be a ModelGatewayResponse or None")
        if event_type is ModelStreamEventType.COMPLETED and self.response is None:
            raise ValueError("a COMPLETED event requires the normalized response")
        if event_type is ModelStreamEventType.ERROR and self.error_code is None:
            raise ValueError("an ERROR event requires an error_code")
        if self.error_code is not None:
            object.__setattr__(
                self,
                "error_code",
                _require_identifier(self.error_code, label="error_code"),
            )
        object.__setattr__(
            self,
            "provider_id",
            _require_optional_identifier(self.provider_id, label="provider_id"),
        )
        object.__setattr__(
            self,
            "model_id",
            _require_optional_identifier(self.model_id, label="model_id"),
        )
        object.__setattr__(
            self,
            "effective_reasoning_effort",
            ReasoningEffort(self.effective_reasoning_effort),
        )
        if not isinstance(self.reasoning_used, bool):
            raise TypeError("reasoning_used must be a bool")

    @property
    def is_terminal(self) -> bool:
        """Return whether this event terminates the stream."""

        return self.event_type in TERMINAL_STREAM_EVENT_TYPES

    def to_dict(self) -> dict[str, Any]:
        """Return the safe public representation of this event."""

        return {
            "event_type": self.event_type.value,
            "request_id": self.request_id,
            "sequence": self.sequence,
            "content_delta": self.content_delta,
            "tool_call": self.tool_call.to_dict() if self.tool_call else None,
            "usage": self.usage.to_dict() if self.usage else None,
            "response": self.response.to_dict() if self.response else None,
            "error_code": self.error_code,
            "provider_id": self.provider_id,
            "model_id": self.model_id,
            "effective_reasoning_effort": self.effective_reasoning_effort.value,
            "reasoning_used": self.reasoning_used,
            "is_terminal": self.is_terminal,
        }
