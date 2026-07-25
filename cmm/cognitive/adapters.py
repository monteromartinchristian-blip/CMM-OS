"""Phase 8.3 – Adaptation layer.

Converts heterogeneous inputs into normalised :class:`Resource` objects
without performing any knowledge extraction.

Public surface
--------------
ResourceInput
AdaptationContext
ResourceAdaptationResult
ResourceAdapter              (Protocol)
PlainTextResourceAdapter
MappingResourceAdapter
ExistingResourceAdapter
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from cmm.cognitive.enums import (
    AdaptationStatus,
    ResourceIntegrityStatus,
    ResourceKind,
    ResourcePermissionOperation,
    ResourceSourceKind,
    SensitivityLevel,
)
from cmm.cognitive.errors import (
    InvalidAdaptationError,
    InvalidResourceInputError,
)
from cmm.cognitive.identifiers import generate_cognitive_id
from cmm.cognitive.resources import (
    Resource,
    ResourcePermission,
    ResourceProvenance,
    ResourceTemporalScope,
    ResourceTransformation,
)
from cmm.cognitive.contracts import Confidence


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ── ResourceInput ─────────────────────────────────────────────────────────────

_VALID_PAYLOAD_TYPES = (str, bytes, dict, list)


@dataclass(frozen=True, slots=True)
class ResourceInput:
    """Represents a raw, not-yet-normalised input to the cognitive layer."""

    id: str
    source_kind: ResourceSourceKind
    payload: Any  # str | bytes | dict | list | object
    format_hint: str | None = None
    name: str | None = None
    mime_type: str | None = None
    location: str | None = None
    author: str | None = None
    language: str | None = None
    content_created_at: datetime | None = None
    observed_at: datetime | None = None
    checksum: str | None = None
    sensitivity: SensitivityLevel = SensitivityLevel.INTERNAL
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise InvalidResourceInputError("ResourceInput id must not be empty")
        if self.mime_type is not None and not self.mime_type.strip():
            raise InvalidResourceInputError("ResourceInput mime_type must not be blank")
        if self.checksum is not None and not self.checksum.strip():
            raise InvalidResourceInputError("ResourceInput checksum must not be blank")
        if self.author is not None and not self.author.strip():
            raise InvalidResourceInputError("ResourceInput author must not be blank")
        if self.language is not None and not self.language.strip():
            raise InvalidResourceInputError("ResourceInput language must not be blank")
        if self.name is not None and not self.name.strip():
            raise InvalidResourceInputError("ResourceInput name must not be blank")

        for dt_field in ("content_created_at", "observed_at"):
            value: datetime | None = getattr(self, dt_field)
            if value is not None and value.tzinfo is None:
                raise InvalidResourceInputError(
                    f"ResourceInput {dt_field} must be timezone-aware"
                )

        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_kind": self.source_kind.value,
            "format_hint": self.format_hint,
            "name": self.name,
            "mime_type": self.mime_type,
            "location": self.location,
            "author": self.author,
            "language": self.language,
            "content_created_at": (
                self.content_created_at.isoformat()
                if self.content_created_at is not None
                else None
            ),
            "observed_at": (
                self.observed_at.isoformat() if self.observed_at is not None else None
            ),
            "checksum": self.checksum,
            "sensitivity": self.sensitivity.value,
            "metadata": dict(self.metadata),
        }


# ── AdaptationContext ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AdaptationContext:
    """Transports contextual information for an adaptation operation."""

    actor_id: str | None = None
    target_domain: str | None = None
    permissions: tuple[str, ...] = ()
    trace_id: str | None = None
    session_id: str | None = None
    timestamp: datetime = field(default_factory=_utc_now)
    options: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise InvalidAdaptationError(
                "AdaptationContext timestamp must be timezone-aware"
            )
        object.__setattr__(self, "permissions", tuple(self.permissions))
        object.__setattr__(self, "options", dict(self.options))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "target_domain": self.target_domain,
            "permissions": list(self.permissions),
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "options": dict(self.options),
            "metadata": dict(self.metadata),
        }


# ── ResourceAdaptationResult ──────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ResourceAdaptationResult:
    """The outcome of an adaptation operation."""

    adapter_name: str
    adapter_version: str
    input_id: str
    status: AdaptationStatus
    id: str = field(
        default_factory=lambda: generate_cognitive_id("adaptation-result", "general")
    )
    resource: Resource | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_utc_now)
    duration_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.adapter_name.strip():
            raise InvalidAdaptationError(
                "ResourceAdaptationResult adapter_name must not be empty"
            )
        if not self.adapter_version.strip():
            raise InvalidAdaptationError(
                "ResourceAdaptationResult adapter_version must not be empty"
            )
        if not self.input_id.strip():
            raise InvalidAdaptationError(
                "ResourceAdaptationResult input_id must not be empty"
            )
        if self.created_at.tzinfo is None:
            raise InvalidAdaptationError(
                "ResourceAdaptationResult created_at must be timezone-aware"
            )
        if self.duration_ms is not None and self.duration_ms < 0:
            raise InvalidAdaptationError(
                "ResourceAdaptationResult duration_ms must not be negative"
            )
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "errors", tuple(self.errors))
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def successful(self) -> bool:
        return self.status in (AdaptationStatus.COMPLETED, AdaptationStatus.PARTIAL)

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "adapter_name": self.adapter_name,
            "adapter_version": self.adapter_version,
            "input_id": self.input_id,
            "status": self.status.value,
            "resource": self.resource.to_dict() if self.resource is not None else None,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "created_at": self.created_at.isoformat(),
            "duration_ms": self.duration_ms,
            "successful": self.successful,
            "has_warnings": self.has_warnings,
            "has_errors": self.has_errors,
            "metadata": dict(self.metadata),
        }


# ── ResourceAdapter Protocol ──────────────────────────────────────────────────


@runtime_checkable
class ResourceAdapter(Protocol):
    """Protocol that all resource adapters must satisfy."""

    name: str
    version: str

    def supports(self, source: ResourceInput) -> bool: ...

    def adapt(
        self,
        source: ResourceInput,
        *,
        context: AdaptationContext | None = None,
    ) -> ResourceAdaptationResult: ...


# ── Shared helpers ────────────────────────────────────────────────────────────

_TEXT_MIME_PREFIXES = (
    "text/",
    "application/json",
    "application/xml",
    "application/yaml",
    "application/toml",
    "application/csv",
)

_TEXT_FORMAT_HINTS = {
    "text",
    "plain",
    "txt",
    "markdown",
    "md",
    "rst",
    "json",
    "yaml",
    "toml",
    "csv",
    "html",
    "xml",
}


def _is_text_mime(mime: str | None) -> bool:
    if mime is None:
        return False
    m = mime.lower().split(";")[0].strip()
    return any(m.startswith(p) for p in _TEXT_MIME_PREFIXES)


def _is_text_format_hint(hint: str | None) -> bool:
    if hint is None:
        return False
    return hint.lower() in _TEXT_FORMAT_HINTS


def _compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_provenance(
    source: ResourceInput,
    *,
    adapter_name: str,
    adapter_version: str,
    operation: str,
    actor_id: str,
    checksum: str | None,
) -> ResourceProvenance:
    transformation = ResourceTransformation(
        operation=operation,
        actor_id=actor_id,
        metadata={
            "adapter": adapter_name,
            "adapter_version": adapter_version,
        },
    )
    return ResourceProvenance(
        source_type=source.source_kind,
        source_id=source.id,
        author=source.author,
        original_location=source.location,
        checksum=checksum or source.checksum,
        transformation_history=(transformation,),
        metadata=dict(source.metadata),
    )


def _make_temporal_scope(source: ResourceInput) -> ResourceTemporalScope:
    return ResourceTemporalScope(
        content_created_at=source.content_created_at,
        observed_at=source.observed_at,
    )


def _result_failed(
    *,
    adapter_name: str,
    adapter_version: str,
    input_id: str,
    error: str,
    duration_ms: float,
) -> ResourceAdaptationResult:
    return ResourceAdaptationResult(
        adapter_name=adapter_name,
        adapter_version=adapter_version,
        input_id=input_id,
        status=AdaptationStatus.FAILED,
        errors=(error,),
        duration_ms=duration_ms,
    )


def _result_unsupported(
    *,
    adapter_name: str,
    adapter_version: str,
    input_id: str,
    duration_ms: float,
) -> ResourceAdaptationResult:
    return ResourceAdaptationResult(
        adapter_name=adapter_name,
        adapter_version=adapter_version,
        input_id=input_id,
        status=AdaptationStatus.UNSUPPORTED,
        errors=("input type is not supported by this adapter",),
        duration_ms=duration_ms,
    )


# ── PlainTextResourceAdapter ──────────────────────────────────────────────────

_ADAPTER_SYSTEM_ACTOR = "system:adapter"


class PlainTextResourceAdapter:
    """Adapts str or utf-8 bytes payloads into textual Resources."""

    name: str = "plain_text"
    version: str = "1.0.0"

    def supports(self, source: ResourceInput) -> bool:
        payload = source.payload
        if isinstance(payload, (str, bytes)):
            return True
        if _is_text_mime(source.mime_type):
            return isinstance(payload, (str, bytes))
        if _is_text_format_hint(source.format_hint):
            return isinstance(payload, (str, bytes))
        return False

    def adapt(
        self,
        source: ResourceInput,
        *,
        context: AdaptationContext | None = None,
    ) -> ResourceAdaptationResult:
        t0 = time.monotonic()
        actor_id = (
            context.actor_id if context and context.actor_id else _ADAPTER_SYSTEM_ACTOR
        )
        domain = context.target_domain if context else "general"
        if domain is None:
            domain = "general"

        payload = source.payload

        # Resolve to str
        if isinstance(payload, bytes):
            try:
                text = payload.decode("utf-8")
            except (UnicodeDecodeError, AttributeError) as exc:
                ms = (time.monotonic() - t0) * 1000
                return _result_failed(
                    adapter_name=self.name,
                    adapter_version=self.version,
                    input_id=source.id,
                    error=f"bytes payload could not be decoded as utf-8: {exc}",
                    duration_ms=ms,
                )
        elif isinstance(payload, str):
            text = payload
        else:
            ms = (time.monotonic() - t0) * 1000
            return _result_unsupported(
                adapter_name=self.name,
                adapter_version=self.version,
                input_id=source.id,
                duration_ms=ms,
            )

        if not text.strip():
            ms = (time.monotonic() - t0) * 1000
            return _result_failed(
                adapter_name=self.name,
                adapter_version=self.version,
                input_id=source.id,
                error="text payload is empty or contains only whitespace",
                duration_ms=ms,
            )

        checksum = _compute_sha256(text.encode("utf-8"))
        provenance = _make_provenance(
            source,
            adapter_name=self.name,
            adapter_version=self.version,
            operation="plain_text_adaptation",
            actor_id=actor_id,
            checksum=checksum,
        )
        temporal_scope = _make_temporal_scope(source)
        resource = Resource(
            domain=domain,
            kind=ResourceKind.DOCUMENT,
            source=source.source_kind,
            content=text,
            provenance=provenance,
            reliability=Confidence(1.0),
            temporal_scope=temporal_scope,
            language=source.language,
            sensitivity=source.sensitivity,
            integrity=ResourceIntegrityStatus.VERIFIED,
            metadata={
                "adapter": self.name,
                "adapter_version": self.version,
                "input_id": source.id,
            },
        )
        ms = (time.monotonic() - t0) * 1000
        return ResourceAdaptationResult(
            adapter_name=self.name,
            adapter_version=self.version,
            input_id=source.id,
            status=AdaptationStatus.COMPLETED,
            resource=resource,
            duration_ms=ms,
        )


# ── MappingResourceAdapter ────────────────────────────────────────────────────

_MAPPING_FORMAT_HINTS = {
    "json",
    "yaml",
    "toml",
    "mapping",
    "dict",
    "structured",
    "dataset",
    "event",
    "note",
}

_MAPPING_MIME_TYPES = {
    "application/json",
    "application/yaml",
    "application/toml",
    "application/x-yaml",
}


def _infer_resource_kind_from_mapping(source: ResourceInput) -> ResourceKind:
    hint = (source.format_hint or "").lower()
    if hint in ("note",):
        return ResourceKind.NOTE
    if hint in ("event",):
        return ResourceKind.CALENDAR_EVENT
    if hint in ("dataset",):
        return ResourceKind.STRUCTURED_DATASET
    return ResourceKind.STRUCTURED_DATASET


class MappingResourceAdapter:
    """Adapts dict/mapping payloads into structured Resources."""

    name: str = "mapping"
    version: str = "1.0.0"

    def supports(self, source: ResourceInput) -> bool:
        payload = source.payload
        if isinstance(payload, dict):
            return True
        mime = (source.mime_type or "").lower().split(";")[0].strip()
        if mime in _MAPPING_MIME_TYPES and isinstance(payload, dict):
            return True
        hint = (source.format_hint or "").lower()
        if hint in _MAPPING_FORMAT_HINTS and isinstance(payload, (dict, list)):
            return True
        return False

    def adapt(
        self,
        source: ResourceInput,
        *,
        context: AdaptationContext | None = None,
    ) -> ResourceAdaptationResult:
        t0 = time.monotonic()
        actor_id = (
            context.actor_id if context and context.actor_id else _ADAPTER_SYSTEM_ACTOR
        )
        domain = context.target_domain if context else "general"
        if domain is None:
            domain = "general"

        payload = source.payload
        if not isinstance(payload, (dict, list)):
            ms = (time.monotonic() - t0) * 1000
            return _result_unsupported(
                adapter_name=self.name,
                adapter_version=self.version,
                input_id=source.id,
                duration_ms=ms,
            )

        kind = _infer_resource_kind_from_mapping(source)
        provenance = _make_provenance(
            source,
            adapter_name=self.name,
            adapter_version=self.version,
            operation="mapping_adaptation",
            actor_id=actor_id,
            checksum=source.checksum,
        )
        temporal_scope = _make_temporal_scope(source)
        # Preserve the original mapping (copy defensively)
        content = dict(payload) if isinstance(payload, dict) else list(payload)
        resource = Resource(
            domain=domain,
            kind=kind,
            source=source.source_kind,
            content=content,
            provenance=provenance,
            reliability=Confidence(1.0),
            temporal_scope=temporal_scope,
            language=source.language,
            sensitivity=source.sensitivity,
            integrity=ResourceIntegrityStatus.UNKNOWN,
            metadata={
                "adapter": self.name,
                "adapter_version": self.version,
                "input_id": source.id,
            },
        )
        ms = (time.monotonic() - t0) * 1000
        return ResourceAdaptationResult(
            adapter_name=self.name,
            adapter_version=self.version,
            input_id=source.id,
            status=AdaptationStatus.COMPLETED,
            resource=resource,
            duration_ms=ms,
        )


# ── ExistingResourceAdapter ───────────────────────────────────────────────────


class ExistingResourceAdapter:
    """Pass-through adapter for payloads that are already a Resource.

    The original Resource is returned without modification.  A provenance
    note is recorded in the result metadata rather than in the Resource
    itself, so the original object is never mutated.
    """

    name: str = "existing_resource"
    version: str = "1.0.0"

    def supports(self, source: ResourceInput) -> bool:
        return isinstance(source.payload, Resource)

    def adapt(
        self,
        source: ResourceInput,
        *,
        context: AdaptationContext | None = None,
    ) -> ResourceAdaptationResult:
        t0 = time.monotonic()

        payload = source.payload
        if not isinstance(payload, Resource):
            ms = (time.monotonic() - t0) * 1000
            return _result_unsupported(
                adapter_name=self.name,
                adapter_version=self.version,
                input_id=source.id,
                duration_ms=ms,
            )

        # Check READ permission when an explicit permission set exists
        if not payload.permits(ResourcePermissionOperation.READ):
            ms = (time.monotonic() - t0) * 1000
            return _result_failed(
                adapter_name=self.name,
                adapter_version=self.version,
                input_id=source.id,
                error="existing resource does not permit READ operation",
                duration_ms=ms,
            )

        ms = (time.monotonic() - t0) * 1000
        return ResourceAdaptationResult(
            adapter_name=self.name,
            adapter_version=self.version,
            input_id=source.id,
            status=AdaptationStatus.COMPLETED,
            resource=payload,  # unchanged original
            duration_ms=ms,
            metadata={"already_normalised": True},
        )
