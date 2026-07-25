"""Phase 8.3 – Extraction layer.

Consumes normalised :class:`Resource` objects and produces structured
candidate objects that the future Phase 8.4 Knowledge Model can promote
into persistent epistemic facts.

Public surface
--------------
ExtractionContext
ExtractionEvidence
ExtractionCandidate
KnowledgeExtractionResult
KnowledgeExtractor            (Protocol)
PlainTextKnowledgeExtractor
MappingKnowledgeExtractor
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from cmm.cognitive.contracts import Confidence
from cmm.cognitive.enums import (
    CandidateKind,
    ExtractionStatus,
    ResourceKind,
    ResourcePermissionOperation,
)
from cmm.cognitive.errors import (
    InvalidExtractionError,
    InvalidExtractionEvidenceError,
)
from cmm.cognitive.identifiers import generate_cognitive_id
from cmm.cognitive.resources import Resource


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ── ExtractionContext ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ExtractionContext:
    """Transports contextual information for an extraction operation."""

    actor_id: str | None = None
    domain: str | None = None
    trace_id: str | None = None
    session_id: str | None = None
    timestamp: datetime = field(default_factory=_utc_now)
    max_candidates: int | None = None
    max_content_length: int | None = None
    allowed_candidate_kinds: tuple[CandidateKind, ...] | None = None
    options: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None:
            raise InvalidExtractionError(
                "ExtractionContext timestamp must be timezone-aware"
            )
        if self.max_candidates is not None and self.max_candidates <= 0:
            raise InvalidExtractionError(
                "ExtractionContext max_candidates must be a positive integer"
            )
        if self.max_content_length is not None and self.max_content_length <= 0:
            raise InvalidExtractionError(
                "ExtractionContext max_content_length must be a positive integer"
            )
        if self.allowed_candidate_kinds is not None:
            object.__setattr__(
                self,
                "allowed_candidate_kinds",
                tuple(self.allowed_candidate_kinds),
            )
        object.__setattr__(self, "options", dict(self.options))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "domain": self.domain,
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "max_candidates": self.max_candidates,
            "max_content_length": self.max_content_length,
            "allowed_candidate_kinds": (
                [k.value for k in self.allowed_candidate_kinds]
                if self.allowed_candidate_kinds is not None
                else None
            ),
            "options": dict(self.options),
            "metadata": dict(self.metadata),
        }


# ── ExtractionEvidence ────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ExtractionEvidence:
    """Pinpoints the exact location in the source resource."""

    resource_id: str
    fragment: str
    start: int | None = None
    end: int | None = None
    selector: str | None = None
    page: int | None = None
    section: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.resource_id.strip():
            raise InvalidExtractionEvidenceError(
                "ExtractionEvidence resource_id must not be empty"
            )
        if self.start is not None and self.start < 0:
            raise InvalidExtractionEvidenceError(
                "ExtractionEvidence start must not be negative"
            )
        if self.end is not None and self.end < 0:
            raise InvalidExtractionEvidenceError(
                "ExtractionEvidence end must not be negative"
            )
        if self.start is not None and self.end is not None and self.end < self.start:
            raise InvalidExtractionEvidenceError(
                "ExtractionEvidence end must not be less than start"
            )
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "fragment": self.fragment,
            "start": self.start,
            "end": self.end,
            "selector": self.selector,
            "page": self.page,
            "section": self.section,
            "metadata": dict(self.metadata),
        }


# ── ExtractionCandidate ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ExtractionCandidate:
    """A neutral extraction candidate, not yet committed to the Knowledge Model."""

    kind: CandidateKind
    value: Any
    confidence: Confidence
    resource_id: str
    extractor_name: str
    evidence: ExtractionEvidence
    id: str = field(
        default_factory=lambda: generate_cognitive_id("extraction-candidate", "general")
    )
    source_fragment: str | None = None
    labels: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.resource_id.strip():
            raise InvalidExtractionError(
                "ExtractionCandidate resource_id must not be empty"
            )
        if not self.extractor_name.strip():
            raise InvalidExtractionError(
                "ExtractionCandidate extractor_name must not be empty"
            )
        object.__setattr__(self, "labels", tuple(self.labels))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "value": self.value,
            "confidence": self.confidence.to_dict(),
            "resource_id": self.resource_id,
            "extractor_name": self.extractor_name,
            "evidence": self.evidence.to_dict(),
            "source_fragment": self.source_fragment,
            "labels": list(self.labels),
            "metadata": dict(self.metadata),
        }


# ── KnowledgeExtractionResult ─────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class KnowledgeExtractionResult:
    """The full outcome of a knowledge extraction run."""

    resource_id: str
    extractor_name: str
    extractor_version: str
    status: ExtractionStatus
    id: str = field(
        default_factory=lambda: generate_cognitive_id("extraction-result", "general")
    )
    candidates: tuple[ExtractionCandidate, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=_utc_now)
    duration_ms: float | None = None
    processed_length: int | None = None
    truncated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.resource_id.strip():
            raise InvalidExtractionError(
                "KnowledgeExtractionResult resource_id must not be empty"
            )
        if not self.extractor_name.strip():
            raise InvalidExtractionError(
                "KnowledgeExtractionResult extractor_name must not be empty"
            )
        if not self.extractor_version.strip():
            raise InvalidExtractionError(
                "KnowledgeExtractionResult extractor_version must not be empty"
            )
        if self.created_at.tzinfo is None:
            raise InvalidExtractionError(
                "KnowledgeExtractionResult created_at must be timezone-aware"
            )
        if self.duration_ms is not None and self.duration_ms < 0:
            raise InvalidExtractionError(
                "KnowledgeExtractionResult duration_ms must not be negative"
            )
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "errors", tuple(self.errors))
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def successful(self) -> bool:
        return self.status in (ExtractionStatus.COMPLETED, ExtractionStatus.PARTIAL)

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "extractor_name": self.extractor_name,
            "extractor_version": self.extractor_version,
            "status": self.status.value,
            "candidates": [c.to_dict() for c in self.candidates],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "created_at": self.created_at.isoformat(),
            "duration_ms": self.duration_ms,
            "processed_length": self.processed_length,
            "truncated": self.truncated,
            "successful": self.successful,
            "candidate_count": self.candidate_count,
            "has_warnings": self.has_warnings,
            "has_errors": self.has_errors,
            "metadata": dict(self.metadata),
        }


# ── KnowledgeExtractor Protocol ───────────────────────────────────────────────


@runtime_checkable
class KnowledgeExtractor(Protocol):
    """Protocol that all knowledge extractors must satisfy."""

    name: str
    version: str

    def supports(self, resource: Resource) -> bool: ...

    def extract(
        self,
        resource: Resource,
        *,
        context: ExtractionContext | None = None,
    ) -> KnowledgeExtractionResult: ...


# ── Internal extraction utilities ─────────────────────────────────────────────

_EXTRACTOR_SYSTEM_ACTOR = "system:extractor"

# A simple pattern for dates / year references
_YEAR_RE = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")
_DATE_RE = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2})\b")
_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?(?:\s*%|\s*(?:mg|kg|km|ml|L|m|s))?\b")


def _split_sentences(text: str) -> list[tuple[str, int, int]]:
    """Split text into (sentence, start_offset, end_offset) triples."""
    # Split on sentence-ending punctuation while preserving positions
    results: list[tuple[str, int, int]] = []
    pattern = re.compile(r"(?<=[.!?])\s+")
    prev = 0
    for m in pattern.finditer(text):
        chunk = text[prev : m.start() + 1].strip()
        if chunk:
            results.append((chunk, prev, m.start() + 1))
        prev = m.end()
    remainder = text[prev:].strip()
    if remainder:
        results.append((remainder, prev, len(text)))
    return results


def _split_lines(text: str) -> list[tuple[str, int, int]]:
    """Yield non-empty lines with their character positions."""
    results: list[tuple[str, int, int]] = []
    offset = 0
    for line in text.splitlines():
        start = offset
        end = offset + len(line)
        stripped = line.strip()
        if stripped:
            results.append((stripped, start, end))
        offset = end + 1  # +1 for the newline
    return results


def _is_question(text: str) -> bool:
    return text.rstrip().endswith("?")


def _extract_keywords_from_text(text: str) -> list[str]:
    """Extract candidate keywords: capitalised multi-char tokens that aren't
    common stopwords and appear in an initial-capitals context."""
    stop = {
        "the",
        "a",
        "an",
        "in",
        "on",
        "at",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "to",
        "of",
        "and",
        "or",
        "but",
        "this",
        "that",
        "with",
        "for",
        "from",
        "by",
        "it",
        "its",
        "not",
        "do",
        "did",
        "does",
        "has",
        "have",
        "had",
        "will",
        "would",
        "can",
        "could",
        "may",
        "might",
        "shall",
        "should",
        "must",
    }
    seen: set[str] = set()
    words = re.findall(r"[A-Za-z]{3,}", text)
    keywords = []
    for w in words:
        lower = w.lower()
        if lower not in stop and lower not in seen:
            seen.add(lower)
            keywords.append(w)
    return keywords


def _check_infer_permission(resource: Resource) -> bool:
    """Return True when the resource allows INFER, False otherwise."""
    return resource.permits(ResourcePermissionOperation.INFER)


def _make_extraction_failed(
    *,
    resource_id: str,
    extractor_name: str,
    extractor_version: str,
    error: str,
    duration_ms: float,
) -> KnowledgeExtractionResult:
    return KnowledgeExtractionResult(
        resource_id=resource_id,
        extractor_name=extractor_name,
        extractor_version=extractor_version,
        status=ExtractionStatus.FAILED,
        errors=(error,),
        duration_ms=duration_ms,
    )


def _make_extraction_unsupported(
    *,
    resource_id: str,
    extractor_name: str,
    extractor_version: str,
    duration_ms: float,
) -> KnowledgeExtractionResult:
    return KnowledgeExtractionResult(
        resource_id=resource_id,
        extractor_name=extractor_name,
        extractor_version=extractor_version,
        status=ExtractionStatus.UNSUPPORTED,
        errors=("resource type is not supported by this extractor",),
        duration_ms=duration_ms,
    )


def _candidate(
    *,
    kind: CandidateKind,
    value: Any,
    confidence: float,
    resource_id: str,
    extractor_name: str,
    fragment: str,
    start: int | None = None,
    end: int | None = None,
    selector: str | None = None,
    source_fragment: str | None = None,
    labels: tuple[str, ...] = (),
) -> ExtractionCandidate:
    evidence = ExtractionEvidence(
        resource_id=resource_id,
        fragment=fragment,
        start=start,
        end=end,
        selector=selector,
    )
    return ExtractionCandidate(
        kind=kind,
        value=value,
        confidence=Confidence(confidence),
        resource_id=resource_id,
        extractor_name=extractor_name,
        evidence=evidence,
        source_fragment=source_fragment,
        labels=labels,
    )


# ── PlainTextKnowledgeExtractor ───────────────────────────────────────────────

_TEXT_RESOURCE_KINDS = {
    ResourceKind.DOCUMENT,
    ResourceKind.USER_MESSAGE,
    ResourceKind.NOTE,
    ResourceKind.EMAIL,
    ResourceKind.EXTERNAL_WEB_SOURCE,
    ResourceKind.SOURCE_CODE,
    ResourceKind.OPPOSITION_PLAN,
}


class PlainTextKnowledgeExtractor:
    """Deterministic, dependency-free extractor for textual resources."""

    name: str = "plain_text"
    version: str = "1.0.0"

    def supports(self, resource: Resource) -> bool:
        return resource.kind in _TEXT_RESOURCE_KINDS and isinstance(
            resource.content, str
        )

    def extract(
        self,
        resource: Resource,
        *,
        context: ExtractionContext | None = None,
    ) -> KnowledgeExtractionResult:
        t0 = time.monotonic()
        rid = resource.id

        if not _check_infer_permission(resource):
            ms = (time.monotonic() - t0) * 1000
            return _make_extraction_failed(
                resource_id=rid,
                extractor_name=self.name,
                extractor_version=self.version,
                error="resource does not permit INFER operation",
                duration_ms=ms,
            )

        if not self.supports(resource):
            ms = (time.monotonic() - t0) * 1000
            return _make_extraction_unsupported(
                resource_id=rid,
                extractor_name=self.name,
                extractor_version=self.version,
                duration_ms=ms,
            )

        text: str = resource.content  # type: ignore[assignment]
        truncated = False
        max_len = context.max_content_length if context else None
        if max_len is not None and len(text) > max_len:
            text = text[:max_len]
            truncated = True

        if not text.strip():
            ms = (time.monotonic() - t0) * 1000
            return KnowledgeExtractionResult(
                resource_id=rid,
                extractor_name=self.name,
                extractor_version=self.version,
                status=ExtractionStatus.EMPTY,
                processed_length=len(text),
                truncated=truncated,
                duration_ms=ms,
            )

        max_cands = context.max_candidates if context else None
        allowed_kinds = context.allowed_candidate_kinds if context else None

        def _kind_allowed(k: CandidateKind) -> bool:
            return allowed_kinds is None or k in allowed_kinds

        candidates: list[ExtractionCandidate] = []

        # ── Statements and questions ──────────────────────────────────────────
        segments = _split_sentences(text)
        if not segments:
            segments = _split_lines(text)

        for seg_text, seg_start, seg_end in segments:
            if max_cands is not None and len(candidates) >= max_cands:
                break
            if _is_question(seg_text) and _kind_allowed(CandidateKind.QUESTION):
                candidates.append(
                    _candidate(
                        kind=CandidateKind.QUESTION,
                        value=seg_text,
                        confidence=0.85,
                        resource_id=rid,
                        extractor_name=self.name,
                        fragment=seg_text,
                        start=seg_start,
                        end=seg_end,
                        source_fragment=seg_text,
                    )
                )
            elif _kind_allowed(CandidateKind.STATEMENT):
                candidates.append(
                    _candidate(
                        kind=CandidateKind.STATEMENT,
                        value=seg_text,
                        confidence=0.75,
                        resource_id=rid,
                        extractor_name=self.name,
                        fragment=seg_text,
                        start=seg_start,
                        end=seg_end,
                        source_fragment=seg_text,
                    )
                )

        # ── Temporal references ───────────────────────────────────────────────
        if _kind_allowed(CandidateKind.TEMPORAL_REFERENCE):
            for pattern in (_DATE_RE, _YEAR_RE):
                for m in pattern.finditer(text):
                    if max_cands is not None and len(candidates) >= max_cands:
                        break
                    matched = m.group(0)
                    candidates.append(
                        _candidate(
                            kind=CandidateKind.TEMPORAL_REFERENCE,
                            value=matched,
                            confidence=0.70,
                            resource_id=rid,
                            extractor_name=self.name,
                            fragment=matched,
                            start=m.start(),
                            end=m.end(),
                            source_fragment=matched,
                        )
                    )

        # ── Keywords ──────────────────────────────────────────────────────────
        if _kind_allowed(CandidateKind.KEYWORD):
            for kw in _extract_keywords_from_text(text):
                if max_cands is not None and len(candidates) >= max_cands:
                    break
                kw_start = text.find(kw)
                candidates.append(
                    _candidate(
                        kind=CandidateKind.KEYWORD,
                        value=kw,
                        confidence=0.55,
                        resource_id=rid,
                        extractor_name=self.name,
                        fragment=kw,
                        start=kw_start if kw_start >= 0 else None,
                        end=kw_start + len(kw) if kw_start >= 0 else None,
                        source_fragment=kw,
                    )
                )

        ms = (time.monotonic() - t0) * 1000
        status = ExtractionStatus.COMPLETED if candidates else ExtractionStatus.EMPTY
        return KnowledgeExtractionResult(
            resource_id=rid,
            extractor_name=self.name,
            extractor_version=self.version,
            status=status,
            candidates=tuple(candidates),
            processed_length=len(text),
            truncated=truncated,
            duration_ms=ms,
        )


# ── MappingKnowledgeExtractor ─────────────────────────────────────────────────

_MAPPING_RESOURCE_KINDS = {
    ResourceKind.STRUCTURED_DATASET,
    ResourceKind.CALENDAR_EVENT,
    ResourceKind.NOTE,
    ResourceKind.VALIDATION_RESULT,
    ResourceKind.TEST_RESULT,
    ResourceKind.PERSONAL_PREFERENCE,
    ResourceKind.MEMORY_ENTRY,
}


def _flatten_mapping(
    obj: Any,
    *,
    prefix: str = "$",
    depth: int = 0,
    max_depth: int = 10,
) -> list[tuple[str, Any]]:
    """Walk a nested mapping/list and yield (selector, scalar_value) pairs."""
    if depth > max_depth:
        return []
    result: list[tuple[str, Any]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            child_sel = f"{prefix}.{k}"
            if isinstance(v, (dict, list)):
                result.extend(_flatten_mapping(v, prefix=child_sel, depth=depth + 1))
            else:
                result.append((child_sel, v))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            child_sel = f"{prefix}[{i}]"
            if isinstance(item, (dict, list)):
                result.extend(_flatten_mapping(item, prefix=child_sel, depth=depth + 1))
            elif item is not None:
                result.append((child_sel, item))
    return result


class MappingKnowledgeExtractor:
    """Deterministic extractor for structured-mapping resources."""

    name: str = "mapping"
    version: str = "1.0.0"

    def supports(self, resource: Resource) -> bool:
        return resource.kind in _MAPPING_RESOURCE_KINDS and isinstance(
            resource.content, (dict, list)
        )

    def extract(
        self,
        resource: Resource,
        *,
        context: ExtractionContext | None = None,
    ) -> KnowledgeExtractionResult:
        t0 = time.monotonic()
        rid = resource.id

        if not _check_infer_permission(resource):
            ms = (time.monotonic() - t0) * 1000
            return _make_extraction_failed(
                resource_id=rid,
                extractor_name=self.name,
                extractor_version=self.version,
                error="resource does not permit INFER operation",
                duration_ms=ms,
            )

        if not self.supports(resource):
            ms = (time.monotonic() - t0) * 1000
            return _make_extraction_unsupported(
                resource_id=rid,
                extractor_name=self.name,
                extractor_version=self.version,
                duration_ms=ms,
            )

        max_cands = context.max_candidates if context else None
        allowed_kinds = context.allowed_candidate_kinds if context else None

        def _kind_allowed(k: CandidateKind) -> bool:
            return allowed_kinds is None or k in allowed_kinds

        content = resource.content
        pairs = _flatten_mapping(content)

        candidates: list[ExtractionCandidate] = []

        for selector, value in pairs:
            if max_cands is not None and len(candidates) >= max_cands:
                break
            if value is None:
                continue
            if not isinstance(value, (str, int, float, bool)):
                continue

            fragment = str(value)
            kind = _infer_candidate_kind_from_value(selector, value)
            if not _kind_allowed(kind):
                continue

            candidates.append(
                _candidate(
                    kind=kind,
                    value=value,
                    confidence=0.80,
                    resource_id=rid,
                    extractor_name=self.name,
                    fragment=fragment,
                    selector=selector,
                    source_fragment=fragment,
                )
            )

        ms = (time.monotonic() - t0) * 1000
        status = ExtractionStatus.COMPLETED if candidates else ExtractionStatus.EMPTY
        return KnowledgeExtractionResult(
            resource_id=rid,
            extractor_name=self.name,
            extractor_version=self.version,
            status=status,
            candidates=tuple(candidates),
            duration_ms=ms,
        )


_TEMPORAL_KEY_PATTERNS = re.compile(
    r"\b(date|time|at|on|when|year|month|day|timestamp|created|updated|start|end)\b",
    re.IGNORECASE,
)
_QUANTITY_KEY_PATTERNS = re.compile(
    r"\b(count|amount|total|value|score|age|size|weight|height|length|price|"
    r"quantity|number|rate|ratio|percent|percentage)\b",
    re.IGNORECASE,
)


def _infer_candidate_kind_from_value(selector: str, value: Any) -> CandidateKind:
    key = selector.rsplit(".", 1)[-1].rsplit("[", 1)[0]
    # Split on underscores / hyphens so compound keys like 'created_at' or
    # 'event-date' are checked part-by-part against our keyword patterns.
    key_parts = " ".join(re.split(r"[_\-]", key))
    if _TEMPORAL_KEY_PATTERNS.search(key_parts):
        return CandidateKind.TEMPORAL_REFERENCE
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return CandidateKind.QUANTITY
    if _QUANTITY_KEY_PATTERNS.search(key_parts):
        return CandidateKind.QUANTITY
    return CandidateKind.STATEMENT
