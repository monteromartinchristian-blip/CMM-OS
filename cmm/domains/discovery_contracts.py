"""Phase 10.4 – Domain Discovery Contracts.

Immutable, JSON-serializable, type-safe contracts representing discovery
sources, discovered candidates, discovery issues, and discovery results.

Discovery never executes code: these contracts only describe what was
found on authorized locations, never runtime state.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from functools import cmp_to_key
from types import MappingProxyType
from typing import Any

from cmm.domains.contracts import (
    _ensure_tz_aware,
    _reject_unknown_fields,
    _validate_non_empty_str,
    _validate_strict_bool,
)
from cmm.domains.enums import DomainSourceKind
from cmm.domains.errors import (
    DomainContractValidationError,
    DomainSerializationError,
)
from cmm.domains.identifiers import DomainId
from cmm.domains.registry_contracts import (
    _reject_sensitive_keys,
    _validate_json_safe_metadata,
    parse_semver,
)

_CHECKSUM_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _validate_strict_int(value: Any, field_name: str) -> int:
    """Validate that value is exactly an int (not bool)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise DomainContractValidationError(
            f"{field_name} must be an int (not bool), got {type(value).__name__}: {value!r}",
            field=field_name,
        )
    return value


def _validate_checksum(value: Any, field_name: str) -> str:
    """Validate checksum format: sha256:<64 lowercase hex chars>."""
    if not isinstance(value, str) or not _CHECKSUM_RE.match(value):
        raise DomainContractValidationError(
            f"{field_name} must match 'sha256:<64 hex chars>', got {value!r}",
            field=field_name,
        )
    return value


def _validate_semver_str(value: Any, field_name: str) -> str:
    """Validate that value is a strict SemVer string."""
    if not isinstance(value, str):
        raise DomainContractValidationError(
            f"{field_name} must be a string, got {type(value).__name__}",
            field=field_name,
        )
    try:
        parse_semver(value)
    except DomainContractValidationError as exc:
        raise DomainContractValidationError(
            f"{field_name} must be a valid SemVer string, got {value!r}",
            field=field_name,
        ) from exc
    return value


def _coerce_domain_id_str(value: Any, field_name: str) -> str:
    """Validate and canonicalize a domain identity to ``domain:<slug>``."""
    if not isinstance(value, str) or not value.strip():
        raise DomainContractValidationError(
            f"{field_name} must be a non-empty string, got {type(value).__name__}",
            field=field_name,
        )
    stripped = value.strip()
    slug = stripped.removeprefix("domain:")
    # DomainId.__post_init__ enforces canonical slug rules.
    domain_id = DomainId(slug=slug)
    return str(domain_id)


def _coerce_source_kind(value: Any, field_name: str) -> DomainSourceKind:
    if isinstance(value, DomainSourceKind):
        return value
    if isinstance(value, str):
        try:
            return DomainSourceKind(value)
        except ValueError as exc:
            raise DomainContractValidationError(
                f"Invalid DomainSourceKind for {field_name}: {value!r}",
                field=field_name,
            ) from exc
    raise DomainContractValidationError(
        f"{field_name} must be a DomainSourceKind or string, got {type(value).__name__}",
        field=field_name,
    )


# ── DomainSource ────────────────────────────────────────────────────────────

_SOURCE_KNOWN = frozenset(
    {
        "source_id",
        "kind",
        "location",
        "trusted",
        "recursive",
        "enabled",
        "priority",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainSource:
    """Immutable declaration of a domain discovery source."""

    source_id: str
    kind: DomainSourceKind
    location: str
    trusted: bool = False
    recursive: bool = False
    enabled: bool = True
    priority: int = 0
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_id", _validate_non_empty_str(self.source_id, "source_id")
        )
        object.__setattr__(self, "kind", _coerce_source_kind(self.kind, "kind"))
        object.__setattr__(
            self, "location", _validate_non_empty_str(self.location, "location")
        )
        object.__setattr__(
            self, "trusted", _validate_strict_bool(self.trusted, "trusted")
        )
        object.__setattr__(
            self, "recursive", _validate_strict_bool(self.recursive, "recursive")
        )
        object.__setattr__(
            self, "enabled", _validate_strict_bool(self.enabled, "enabled")
        )
        object.__setattr__(
            self, "priority", _validate_strict_int(self.priority, "priority")
        )
        meta = _validate_json_safe_metadata(self.metadata, "metadata")
        _reject_sensitive_keys(meta, "metadata")
        object.__setattr__(self, "metadata", meta)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "kind": self.kind.value,
            "location": self.location,
            "trusted": self.trusted,
            "recursive": self.recursive,
            "enabled": self.enabled,
            "priority": self.priority,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainSource:
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainSource.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _SOURCE_KNOWN, "DomainSource")
        required = {"source_id", "kind", "location"}
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainSource.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                source_id=data["source_id"],
                kind=data["kind"],
                location=data["location"],
                trusted=data.get("trusted", False),
                recursive=data.get("recursive", False),
                enabled=data.get("enabled", True),
                priority=data.get("priority", 0),
                metadata=data.get("metadata", {}),
            )
        except DomainContractValidationError as exc:
            raise DomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


def _compare_sources(left: DomainSource, right: DomainSource) -> int:
    """Deterministic comparator: priority desc, then source_id, then location."""
    if left.priority != right.priority:
        return -1 if left.priority > right.priority else 1
    if left.source_id != right.source_id:
        return -1 if left.source_id < right.source_id else 1
    if left.location != right.location:
        return -1 if left.location < right.location else 1
    return 0


# ── DomainCandidate ─────────────────────────────────────────────────────────

_CANDIDATE_KNOWN = frozenset(
    {
        "candidate_id",
        "source_id",
        "source_kind",
        "location",
        "manifest_path",
        "domain_id",
        "detected_version",
        "checksum",
        "trusted",
        "discovered_at",
        "metadata",
    }
)


@dataclass(frozen=True, slots=True)
class DomainCandidate:
    """Immutable description of a discovered domain pack candidate.

    ``domain_id`` is the authoritative domain identity for this candidate
    (as extracted from the manifest during discovery). ``candidate_id`` is
    merely a discovery-local identifier and must never be parsed to derive
    identity.
    """

    candidate_id: str
    source_id: str
    source_kind: DomainSourceKind
    location: str
    manifest_path: str
    domain_id: str
    detected_version: str
    checksum: str
    trusted: bool
    discovered_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "candidate_id",
            _validate_non_empty_str(self.candidate_id, "candidate_id"),
        )
        object.__setattr__(
            self, "source_id", _validate_non_empty_str(self.source_id, "source_id")
        )
        object.__setattr__(
            self, "source_kind", _coerce_source_kind(self.source_kind, "source_kind")
        )
        object.__setattr__(
            self, "location", _validate_non_empty_str(self.location, "location")
        )
        object.__setattr__(
            self, "domain_id", _coerce_domain_id_str(self.domain_id, "domain_id")
        )
        object.__setattr__(
            self,
            "manifest_path",
            _validate_non_empty_str(self.manifest_path, "manifest_path"),
        )
        object.__setattr__(
            self,
            "detected_version",
            _validate_semver_str(self.detected_version, "detected_version"),
        )
        object.__setattr__(
            self, "checksum", _validate_checksum(self.checksum, "checksum")
        )
        object.__setattr__(
            self, "trusted", _validate_strict_bool(self.trusted, "trusted")
        )
        object.__setattr__(
            self, "discovered_at", _ensure_tz_aware(self.discovered_at, "discovered_at")
        )
        meta = _validate_json_safe_metadata(self.metadata, "metadata")
        _reject_sensitive_keys(meta, "metadata")
        object.__setattr__(self, "metadata", meta)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "source_id": self.source_id,
            "source_kind": self.source_kind.value,
            "location": self.location,
            "manifest_path": self.manifest_path,
            "domain_id": self.domain_id,
            "detected_version": self.detected_version,
            "checksum": self.checksum,
            "trusted": self.trusted,
            "discovered_at": self.discovered_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainCandidate:
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainCandidate.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _CANDIDATE_KNOWN, "DomainCandidate")
        required = {
            "candidate_id",
            "source_id",
            "source_kind",
            "location",
            "manifest_path",
            "domain_id",
            "detected_version",
            "checksum",
            "trusted",
            "discovered_at",
        }
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainCandidate.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        discovered_raw = data["discovered_at"]
        if isinstance(discovered_raw, datetime):
            discovered_at = discovered_raw
        elif isinstance(discovered_raw, str):
            try:
                discovered_at = datetime.fromisoformat(discovered_raw)
            except ValueError as exc:
                raise DomainSerializationError(
                    f"Invalid isoformat datetime for discovered_at: {discovered_raw!r}",
                    field="discovered_at",
                ) from exc
        else:
            raise DomainSerializationError(
                "discovered_at must be a datetime or ISO string",
                field="discovered_at",
            )
        if discovered_at.tzinfo is None:
            raise DomainSerializationError(
                "discovered_at must be timezone-aware", field="discovered_at"
            )
        try:
            return cls(
                candidate_id=data["candidate_id"],
                source_id=data["source_id"],
                source_kind=data["source_kind"],
                location=data["location"],
                manifest_path=data["manifest_path"],
                domain_id=data["domain_id"],
                detected_version=data["detected_version"],
                checksum=data["checksum"],
                trusted=data["trusted"],
                discovered_at=discovered_at,
                metadata=data.get("metadata", {}),
            )
        except DomainContractValidationError as exc:
            raise DomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


# ── DomainDiscoveryIssue ────────────────────────────────────────────────────

_ISSUE_KNOWN = frozenset(
    {"source_id", "location", "code", "message", "blocking", "metadata"}
)

_MAX_ISSUE_MESSAGE_LEN = 2000


@dataclass(frozen=True, slots=True)
class DomainDiscoveryIssue:
    """Immutable, structured issue encountered during discovery."""

    source_id: str
    location: str
    code: str
    message: str
    blocking: bool
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_id", _validate_non_empty_str(self.source_id, "source_id")
        )
        if not isinstance(self.location, str):
            raise DomainContractValidationError(
                f"location must be a string, got {type(self.location).__name__}",
                field="location",
            )
        object.__setattr__(self, "location", self.location.strip())
        object.__setattr__(self, "code", _validate_non_empty_str(self.code, "code"))
        object.__setattr__(
            self, "message", _validate_non_empty_str(self.message, "message")
        )
        if len(self.message) > _MAX_ISSUE_MESSAGE_LEN:
            raise DomainContractValidationError(
                f"message exceeds maximum length of {_MAX_ISSUE_MESSAGE_LEN}",
                field="message",
            )
        object.__setattr__(
            self, "blocking", _validate_strict_bool(self.blocking, "blocking")
        )
        meta = _validate_json_safe_metadata(self.metadata, "metadata")
        _reject_sensitive_keys(meta, "metadata")
        object.__setattr__(self, "metadata", meta)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "location": self.location,
            "code": self.code,
            "message": self.message,
            "blocking": self.blocking,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainDiscoveryIssue:
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainDiscoveryIssue.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _ISSUE_KNOWN, "DomainDiscoveryIssue")
        required = {"source_id", "location", "code", "message", "blocking"}
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainDiscoveryIssue.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        try:
            return cls(
                source_id=data["source_id"],
                location=data["location"],
                code=data["code"],
                message=data["message"],
                blocking=data["blocking"],
                metadata=data.get("metadata", {}),
            )
        except DomainContractValidationError as exc:
            raise DomainSerializationError(
                exc.message, field=exc.field, details=dict(exc.details)
            ) from exc


def _compare_issues(left: DomainDiscoveryIssue, right: DomainDiscoveryIssue) -> int:
    left_key = (left.source_id, left.location, left.code)
    right_key = (right.source_id, right.location, right.code)
    if left_key != right_key:
        return -1 if left_key < right_key else 1
    return 0


# ── DomainDiscoveryResult ───────────────────────────────────────────────────

_RESULT_KNOWN = frozenset({"candidates", "issues", "scanned_sources", "discovered_at"})


def _compare_candidates(left: DomainCandidate, right: DomainCandidate) -> int:
    left_key = (left.source_id, left.location, left.manifest_path, left.candidate_id)
    right_key = (
        right.source_id,
        right.location,
        right.manifest_path,
        right.candidate_id,
    )
    if left_key != right_key:
        return -1 if left_key < right_key else 1
    return 0


@dataclass(frozen=True, slots=True)
class DomainDiscoveryResult:
    """Immutable, deterministic snapshot of a discovery run."""

    candidates: tuple[DomainCandidate, ...]
    issues: tuple[DomainDiscoveryIssue, ...]
    scanned_sources: tuple[str, ...]
    discovered_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.candidates, (list, tuple)):
            raise DomainContractValidationError(
                "candidates must be a list or tuple", field="candidates"
            )
        for c in self.candidates:
            if not isinstance(c, DomainCandidate):
                raise DomainContractValidationError(
                    f"candidates items must be DomainCandidate, got {type(c).__name__}",
                    field="candidates",
                )
        object.__setattr__(
            self,
            "candidates",
            tuple(sorted(self.candidates, key=cmp_to_key(_compare_candidates))),
        )

        if not isinstance(self.issues, (list, tuple)):
            raise DomainContractValidationError(
                "issues must be a list or tuple", field="issues"
            )
        for i in self.issues:
            if not isinstance(i, DomainDiscoveryIssue):
                raise DomainContractValidationError(
                    f"issues items must be DomainDiscoveryIssue, got {type(i).__name__}",
                    field="issues",
                )
        object.__setattr__(
            self, "issues", tuple(sorted(self.issues, key=cmp_to_key(_compare_issues)))
        )

        if not isinstance(self.scanned_sources, (list, tuple, set)):
            raise DomainContractValidationError(
                "scanned_sources must be a list, tuple, or set",
                field="scanned_sources",
            )
        for s in self.scanned_sources:
            if not isinstance(s, str) or not s.strip():
                raise DomainContractValidationError(
                    "scanned_sources items must be non-empty strings",
                    field="scanned_sources",
                )
        object.__setattr__(
            self, "scanned_sources", tuple(sorted(set(self.scanned_sources)))
        )

        object.__setattr__(
            self, "discovered_at", _ensure_tz_aware(self.discovered_at, "discovered_at")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": [c.to_dict() for c in self.candidates],
            "issues": [i.to_dict() for i in self.issues],
            "scanned_sources": list(self.scanned_sources),
            "discovered_at": self.discovered_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainDiscoveryResult:
        if not isinstance(data, Mapping):
            raise DomainSerializationError(
                "DomainDiscoveryResult.from_dict requires a mapping", field="data"
            )
        _reject_unknown_fields(data, _RESULT_KNOWN, "DomainDiscoveryResult")
        required = {"candidates", "issues", "scanned_sources", "discovered_at"}
        missing = required - set(data.keys())
        if missing:
            raise DomainSerializationError(
                f"DomainDiscoveryResult.from_dict missing required fields: {sorted(missing)}",
                field="data",
            )
        discovered_raw = data["discovered_at"]
        if isinstance(discovered_raw, datetime):
            discovered_at = discovered_raw
        elif isinstance(discovered_raw, str):
            try:
                discovered_at = datetime.fromisoformat(discovered_raw)
            except ValueError as exc:
                raise DomainSerializationError(
                    f"Invalid isoformat datetime for discovered_at: {discovered_raw!r}",
                    field="discovered_at",
                ) from exc
        else:
            raise DomainSerializationError(
                "discovered_at must be a datetime or ISO string",
                field="discovered_at",
            )
        candidates = tuple(
            DomainCandidate.from_dict(dict(c)) for c in data["candidates"]
        )
        issues = tuple(DomainDiscoveryIssue.from_dict(dict(i)) for i in data["issues"])
        return cls(
            candidates=candidates,
            issues=issues,
            scanned_sources=tuple(data["scanned_sources"]),
            discovered_at=discovered_at,
        )


__all__ = [
    "DomainCandidate",
    "DomainDiscoveryIssue",
    "DomainDiscoveryResult",
    "DomainSource",
]
