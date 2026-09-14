"""Phase 8.4 – Knowledge Model.

Immutable, validated, serialisable cognitive contracts.  No persistence,
no search, no agents.  Every contract validates its invariants in
``__post_init__`` and exposes a deterministic ``serialize()`` / ``from_mapping()``
pair (with ``to_dict()`` / ``from_dict()`` compatibility aliases).

Public surface
--------------
TemporalScope
Evidence
KnowledgeRelation
KnowledgeItem
Contradiction
KnowledgeBundle
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any

from cmm.cognitive.contracts import Confidence
from cmm.cognitive.enums import (
    ContradictionSeverity,
    ContradictionStatus,
    EvidenceKind,
    EvidencePolarityKind,
    KnowledgeKind,
    KnowledgeRelationKind,
    KnowledgeStatus,
    SensitivityLevel,
    TemporalScopeKind,
    TemporalValidityStatus,
)
from cmm.cognitive.errors import (
    InvalidContradictionError,
    InvalidEvidenceError,
    InvalidKnowledgeBundleError,
    InvalidKnowledgeItemError,
    InvalidKnowledgeRelationError,
    InvalidTemporalValidityError,
)
from cmm.cognitive.identifiers import generate_cognitive_id


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(value: datetime | None, field_name: str) -> None:
    if value is not None and value.tzinfo is None:
        raise InvalidTemporalValidityError(
            f"{field_name} must be timezone-aware when provided"
        )


# ── TemporalScope ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TemporalScope:
    """Represents when a piece of knowledge holds or held true."""

    kind: TemporalScopeKind = TemporalScopeKind.UNKNOWN
    observed_at: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    expires_at: datetime | None = None
    last_verified_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_aware(self.observed_at, "TemporalScope.observed_at")
        _require_aware(self.valid_from, "TemporalScope.valid_from")
        _require_aware(self.valid_until, "TemporalScope.valid_until")
        _require_aware(self.expires_at, "TemporalScope.expires_at")
        _require_aware(self.last_verified_at, "TemporalScope.last_verified_at")

        if (
            self.valid_from is not None
            and self.valid_until is not None
            and self.valid_until < self.valid_from
        ):
            raise InvalidTemporalValidityError(
                "TemporalScope.valid_until cannot be before valid_from"
            )

        if self.kind is TemporalScopeKind.INTERVAL and (
            self.valid_from is None or self.valid_until is None
        ):
            raise InvalidTemporalValidityError(
                "INTERVAL temporal scope requires valid_from and valid_until"
            )

        if self.kind is TemporalScopeKind.POINT_IN_TIME and self.observed_at is None:
            raise InvalidTemporalValidityError(
                "POINT_IN_TIME temporal scope requires observed_at"
            )

        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    def is_valid_at(self, moment: datetime) -> bool:
        """Return True if ``moment`` falls within this scope."""
        _require_aware(moment, "moment")

        if self.kind is TemporalScopeKind.TIMELESS:
            return True
        if self.kind is TemporalScopeKind.UNKNOWN:
            return False
        if self.kind is TemporalScopeKind.POINT_IN_TIME:
            return moment == self.observed_at

        if self.valid_from is not None and moment < self.valid_from:
            return False
        return self.valid_until is None or moment <= self.valid_until

    def contains(self, moment: datetime) -> bool:
        """Alias for :meth:`is_valid_at`."""
        return self.is_valid_at(moment)

    @property
    def validity_status(self) -> TemporalValidityStatus:
        """Broad status label: valid / expired / future / unknown / timeless."""
        now = _utc_now()
        if self.kind is TemporalScopeKind.TIMELESS:
            return TemporalValidityStatus.TIMELESS
        if self.kind is TemporalScopeKind.UNKNOWN:
            return TemporalValidityStatus.UNKNOWN
        if self.valid_until is not None and now > self.valid_until:
            return TemporalValidityStatus.EXPIRED
        if self.valid_from is not None and now < self.valid_from:
            return TemporalValidityStatus.FUTURE
        if self.expires_at is not None and now > self.expires_at:
            return TemporalValidityStatus.POTENTIALLY_OBSOLETE
        return TemporalValidityStatus.VALID

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization."""
        return {
            "kind": self.kind.value,
            "observed_at": (
                self.observed_at.isoformat() if self.observed_at is not None else None
            ),
            "valid_from": (
                self.valid_from.isoformat() if self.valid_from is not None else None
            ),
            "valid_until": (
                self.valid_until.isoformat() if self.valid_until is not None else None
            ),
            "expires_at": (
                self.expires_at.isoformat() if self.expires_at is not None else None
            ),
            "last_verified_at": (
                self.last_verified_at.isoformat()
                if self.last_verified_at is not None
                else None
            ),
            "validity_status": self.validity_status.value,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> TemporalScope:
        """Canonical deserialization from mapping."""

        def _parse(key: str) -> datetime | None:
            raw = payload.get(key)
            if raw is None:
                return None
            if isinstance(raw, datetime):
                return raw
            if isinstance(raw, str):
                try:
                    return datetime.fromisoformat(raw)
                except ValueError as exc:
                    raise InvalidTemporalValidityError(
                        f"Invalid ISO timestamp for {key}: {raw}"
                    ) from exc
            raise InvalidTemporalValidityError(
                f"Expected timestamp string for {key}: {raw}"
            )

        kind_raw = payload.get("kind", TemporalScopeKind.UNKNOWN.value)
        if isinstance(kind_raw, TemporalScopeKind):
            kind_val = kind_raw
        elif isinstance(kind_raw, str):
            try:
                kind_val = TemporalScopeKind(kind_raw)
            except ValueError as exc:
                raise InvalidTemporalValidityError(
                    f"Unknown TemporalScopeKind: {kind_raw}"
                ) from exc
        else:
            raise InvalidTemporalValidityError(f"Invalid kind: {kind_raw}")

        return cls(
            kind=kind_val,
            observed_at=_parse("observed_at"),
            valid_from=_parse("valid_from"),
            valid_until=_parse("valid_until"),
            expires_at=_parse("expires_at"),
            last_verified_at=_parse("last_verified_at"),
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemporalScope:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(data)


# ── Evidence ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Evidence:
    """Structured evidence that supports or contradicts a KnowledgeItem.

    Links back to a source Resource (via ``resource_id``) and an optional
    ``extraction_candidate_id`` from Phase 8.3 for full traceability.
    """

    resource_id: str
    fragment: str
    confidence: Confidence
    id: str = field(
        default_factory=lambda: generate_cognitive_id("evidence", "knowledge")
    )
    kind: EvidenceKind = EvidenceKind.UNKNOWN
    polarity: EvidencePolarityKind = EvidencePolarityKind.NEUTRAL
    locator: str | None = None
    section: str | None = None
    page: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    actor_id: str | None = None
    extraction_candidate_id: str | None = None
    resource_provenance_id: str | None = None
    observed_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidEvidenceError("Evidence.id must not be empty")
        if not self.resource_id.strip():
            raise InvalidEvidenceError("Evidence.resource_id must not be empty")
        if not self.fragment.strip():
            raise InvalidEvidenceError("Evidence.fragment must not be empty")
        if self.locator is not None and not self.locator.strip():
            raise InvalidEvidenceError("Evidence.locator must not be blank when set")
        if self.char_start is not None and self.char_start < 0:
            raise InvalidEvidenceError("Evidence.char_start must not be negative")
        if self.char_end is not None and self.char_end < 0:
            raise InvalidEvidenceError("Evidence.char_end must not be negative")
        if (
            self.char_start is not None
            and self.char_end is not None
            and self.char_end < self.char_start
        ):
            raise InvalidEvidenceError(
                "Evidence.char_end must not be less than char_start"
            )
        _require_aware(self.observed_at, "Evidence.observed_at")
        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization."""
        return {
            "id": self.id,
            "resource_id": self.resource_id,
            "fragment": self.fragment,
            "confidence": self.confidence.to_dict(),
            "kind": self.kind.value,
            "polarity": self.polarity.value,
            "locator": self.locator,
            "section": self.section,
            "page": self.page,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "actor_id": self.actor_id,
            "extraction_candidate_id": self.extraction_candidate_id,
            "resource_provenance_id": self.resource_provenance_id,
            "observed_at": self.observed_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> Evidence:
        """Canonical deserialization from mapping."""
        conf_data = payload.get("confidence")
        if isinstance(conf_data, Confidence):
            conf = conf_data
        elif isinstance(conf_data, Mapping):
            conf = Confidence(
                **{
                    k: v
                    for k, v in conf_data.items()
                    if k in ("value", "source", "reasons", "metadata")
                }
            )
        else:
            raise InvalidEvidenceError(
                f"Invalid confidence payload in Evidence: {conf_data}"
            )

        kind_raw = payload.get("kind", EvidenceKind.UNKNOWN.value)
        if isinstance(kind_raw, EvidenceKind):
            kind_val = kind_raw
        elif isinstance(kind_raw, str):
            try:
                kind_val = EvidenceKind(kind_raw)
            except ValueError as exc:
                raise InvalidEvidenceError(f"Unknown EvidenceKind: {kind_raw}") from exc
        else:
            raise InvalidEvidenceError(f"Invalid kind: {kind_raw}")

        polarity_raw = payload.get("polarity", EvidencePolarityKind.NEUTRAL.value)
        if isinstance(polarity_raw, EvidencePolarityKind):
            polarity_val = polarity_raw
        elif isinstance(polarity_raw, str):
            try:
                polarity_val = EvidencePolarityKind(polarity_raw)
            except ValueError as exc:
                raise InvalidEvidenceError(
                    f"Unknown EvidencePolarityKind: {polarity_raw}"
                ) from exc
        else:
            raise InvalidEvidenceError(f"Invalid polarity: {polarity_raw}")

        obs_at_raw = payload.get("observed_at")
        if isinstance(obs_at_raw, datetime):
            obs_at = obs_at_raw
        elif isinstance(obs_at_raw, str):
            try:
                obs_at = datetime.fromisoformat(obs_at_raw)
            except ValueError as exc:
                raise InvalidEvidenceError(
                    f"Invalid ISO timestamp for observed_at: {obs_at_raw}"
                ) from exc
        else:
            raise InvalidEvidenceError(f"Expected timestamp string: {obs_at_raw}")

        return cls(
            id=payload["id"],
            resource_id=payload["resource_id"],
            fragment=payload["fragment"],
            confidence=conf,
            kind=kind_val,
            polarity=polarity_val,
            locator=payload.get("locator"),
            section=payload.get("section"),
            page=payload.get("page"),
            char_start=payload.get("char_start"),
            char_end=payload.get("char_end"),
            actor_id=payload.get("actor_id"),
            extraction_candidate_id=payload.get("extraction_candidate_id"),
            resource_provenance_id=payload.get("resource_provenance_id"),
            observed_at=obs_at,
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Evidence:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(data)


# ── KnowledgeRelation ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class KnowledgeRelation:
    """A typed, traceable relationship between two KnowledgeItems."""

    source_id: str
    target_id: str
    kind: KnowledgeRelationKind
    confidence: Confidence
    id: str = field(
        default_factory=lambda: generate_cognitive_id("knowledge-relation", "knowledge")
    )
    actor_id: str | None = None
    provenance: str | None = None
    created_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidKnowledgeRelationError(
                "KnowledgeRelation.id must not be empty"
            )
        if not self.source_id.strip():
            raise InvalidKnowledgeRelationError(
                "KnowledgeRelation.source_id must not be empty"
            )
        if not self.target_id.strip():
            raise InvalidKnowledgeRelationError(
                "KnowledgeRelation.target_id must not be empty"
            )
        if self.source_id == self.target_id:
            raise InvalidKnowledgeRelationError(
                "KnowledgeRelation cannot reference its own source as target"
            )
        _require_aware(self.created_at, "KnowledgeRelation.created_at")
        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization."""
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "kind": self.kind.value,
            "confidence": self.confidence.to_dict(),
            "actor_id": self.actor_id,
            "provenance": self.provenance,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> KnowledgeRelation:
        """Canonical deserialization from mapping."""
        conf_data = payload.get("confidence")
        if isinstance(conf_data, Confidence):
            conf = conf_data
        elif isinstance(conf_data, Mapping):
            conf = Confidence(
                **{
                    k: v
                    for k, v in conf_data.items()
                    if k in ("value", "source", "reasons", "metadata")
                }
            )
        else:
            raise InvalidKnowledgeRelationError(
                f"Invalid confidence payload in KnowledgeRelation: {conf_data}"
            )

        kind_raw = payload["kind"]
        if isinstance(kind_raw, KnowledgeRelationKind):
            kind_val = kind_raw
        elif isinstance(kind_raw, str):
            try:
                kind_val = KnowledgeRelationKind(kind_raw)
            except ValueError as exc:
                raise InvalidKnowledgeRelationError(
                    f"Unknown KnowledgeRelationKind: {kind_raw}"
                ) from exc
        else:
            raise InvalidKnowledgeRelationError(f"Invalid kind: {kind_raw}")

        created_at_raw = payload.get("created_at")
        if isinstance(created_at_raw, datetime):
            created_at = created_at_raw
        elif isinstance(created_at_raw, str):
            try:
                created_at = datetime.fromisoformat(created_at_raw)
            except ValueError as exc:
                raise InvalidKnowledgeRelationError(
                    f"Invalid ISO timestamp for created_at: {created_at_raw}"
                ) from exc
        else:
            created_at = _utc_now()

        return cls(
            id=payload["id"],
            source_id=payload["source_id"],
            target_id=payload["target_id"],
            kind=kind_val,
            confidence=conf,
            actor_id=payload.get("actor_id"),
            provenance=payload.get("provenance"),
            created_at=created_at,
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeRelation:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(data)


# ── KnowledgeItem ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class KnowledgeItem:
    """Canonical unit of structured knowledge in CMM OS.

    Represents a proposition together with its epistemic type, confidence,
    temporal validity, traceability chain, and optional relations.
    Immutable after construction.
    """

    statement: str
    kind: KnowledgeKind
    confidence: Confidence
    id: str = field(
        default_factory=lambda: generate_cognitive_id("knowledge-item", "knowledge")
    )
    status: KnowledgeStatus = KnowledgeStatus.ACTIVE
    evidence: tuple[Evidence, ...] = ()
    relations: tuple[KnowledgeRelation, ...] = ()
    temporal_scope: TemporalScope = field(default_factory=TemporalScope)
    sensitivity: SensitivityLevel | None = None
    actor_id: str | None = None
    resource_id: str | None = None
    version: int = 1
    supersedes_id: str | None = None
    superseded_by_id: str | None = None
    invalidated_at: datetime | None = None
    invalidation_reason: str | None = None
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidKnowledgeItemError("KnowledgeItem.id must not be empty")
        if not self.statement.strip():
            raise InvalidKnowledgeItemError("KnowledgeItem.statement must not be empty")
        if self.version < 1:
            raise InvalidKnowledgeItemError("KnowledgeItem.version must be at least 1")
        if self.supersedes_id is not None and not self.supersedes_id.strip():
            raise InvalidKnowledgeItemError(
                "KnowledgeItem.supersedes_id must not be blank when set"
            )
        if self.superseded_by_id is not None and not self.superseded_by_id.strip():
            raise InvalidKnowledgeItemError(
                "KnowledgeItem.superseded_by_id must not be blank when set"
            )

        _require_aware(self.created_at, "KnowledgeItem.created_at")
        _require_aware(self.updated_at, "KnowledgeItem.updated_at")
        _require_aware(self.invalidated_at, "KnowledgeItem.invalidated_at")

        if self.updated_at < self.created_at:
            raise InvalidKnowledgeItemError(
                "KnowledgeItem.updated_at cannot be before created_at"
            )

        if self.status is KnowledgeStatus.INVALIDATED:
            if self.invalidated_at is None:
                raise InvalidKnowledgeItemError(
                    "INVALIDATED KnowledgeItem requires invalidated_at"
                )
            if not self.invalidation_reason or not self.invalidation_reason.strip():
                raise InvalidKnowledgeItemError(
                    "INVALIDATED KnowledgeItem requires invalidation_reason"
                )
        elif self.invalidated_at is not None or self.invalidation_reason is not None:
            raise InvalidKnowledgeItemError(
                "invalidated_at / invalidation_reason require INVALIDATED status"
            )

        if self.status is KnowledgeStatus.SUPERSEDED and self.superseded_by_id is None:
            raise InvalidKnowledgeItemError(
                "SUPERSEDED KnowledgeItem requires superseded_by_id"
            )

        evidence_ids = [e.id for e in self.evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise InvalidKnowledgeItemError(
                "KnowledgeItem.evidence must not contain duplicate ids"
            )

        relation_ids = [r.id for r in self.relations]
        if len(relation_ids) != len(set(relation_ids)):
            raise InvalidKnowledgeItemError(
                "KnowledgeItem.relations must not contain duplicate ids"
            )

        object.__setattr__(self, "evidence", tuple(self.evidence or ()))
        object.__setattr__(self, "relations", tuple(self.relations or ()))
        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    @property
    def is_active(self) -> bool:
        return self.status in {
            KnowledgeStatus.ACTIVE,
            KnowledgeStatus.UNVERIFIED,
            KnowledgeStatus.DISPUTED,
        }

    def invalidate(
        self,
        reason: str,
        *,
        invalidated_at: datetime | None = None,
    ) -> KnowledgeItem:
        """Return a new INVALIDATED copy; original is unchanged."""
        if not reason.strip():
            raise InvalidKnowledgeItemError("invalidation reason must not be empty")
        ts = invalidated_at or _utc_now()
        _require_aware(ts, "invalidated_at")
        return replace(
            self,
            status=KnowledgeStatus.INVALIDATED,
            invalidated_at=ts,
            invalidation_reason=reason,
            updated_at=ts,
        )

    def create_revision(
        self,
        *,
        statement: str | None = None,
        kind: KnowledgeKind | None = None,
        confidence: Confidence | None = None,
        evidence: tuple[Evidence, ...] | None = None,
        relations: tuple[KnowledgeRelation, ...] | None = None,
        temporal_scope: TemporalScope | None = None,
        actor_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> KnowledgeItem:
        """Return a new KnowledgeItem with incremented version linked to self."""
        ts = created_at or _utc_now()
        _require_aware(ts, "revision created_at")
        return KnowledgeItem(
            statement=statement if statement is not None else self.statement,
            kind=kind if kind is not None else self.kind,
            confidence=confidence if confidence is not None else self.confidence,
            status=KnowledgeStatus.ACTIVE,
            evidence=evidence if evidence is not None else self.evidence,
            relations=relations if relations is not None else self.relations,
            temporal_scope=(
                temporal_scope if temporal_scope is not None else self.temporal_scope
            ),
            actor_id=actor_id if actor_id is not None else self.actor_id,
            resource_id=self.resource_id,
            version=self.version + 1,
            supersedes_id=self.id,
            created_at=ts,
            updated_at=ts,
            metadata=metadata if metadata is not None else dict(self.metadata),
        )

    def mark_superseded(
        self,
        superseded_by_id: str,
        *,
        superseded_at: datetime | None = None,
    ) -> KnowledgeItem:
        """Return a SUPERSEDED copy; original is unchanged."""
        if not superseded_by_id.strip():
            raise InvalidKnowledgeItemError("superseded_by_id must not be empty")
        ts = superseded_at or _utc_now()
        _require_aware(ts, "superseded_at")
        return replace(
            self,
            status=KnowledgeStatus.SUPERSEDED,
            superseded_by_id=superseded_by_id,
            updated_at=ts,
        )

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization."""
        return {
            "id": self.id,
            "statement": self.statement,
            "kind": self.kind.value,
            "status": self.status.value,
            "confidence": self.confidence.to_dict(),
            "evidence": [e.serialize() for e in self.evidence],
            "relations": [r.serialize() for r in self.relations],
            "temporal_scope": self.temporal_scope.serialize(),
            "sensitivity": (
                self.sensitivity.value if self.sensitivity is not None else None
            ),
            "actor_id": self.actor_id,
            "resource_id": self.resource_id,
            "version": self.version,
            "supersedes_id": self.supersedes_id,
            "superseded_by_id": self.superseded_by_id,
            "invalidated_at": (
                self.invalidated_at.isoformat()
                if self.invalidated_at is not None
                else None
            ),
            "invalidation_reason": self.invalidation_reason,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_active": self.is_active,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> KnowledgeItem:
        """Canonical deserialization from mapping."""

        def _parse_dt(raw: Any, field_name: str) -> datetime | None:
            if raw is None:
                return None
            if isinstance(raw, datetime):
                return raw
            if isinstance(raw, str):
                try:
                    return datetime.fromisoformat(raw)
                except ValueError as exc:
                    raise InvalidKnowledgeItemError(
                        f"Invalid ISO timestamp for {field_name}: {raw}"
                    ) from exc
            raise InvalidKnowledgeItemError(
                f"Expected timestamp string for {field_name}: {raw}"
            )

        kind_raw = payload["kind"]
        if isinstance(kind_raw, KnowledgeKind):
            kind_val = kind_raw
        elif isinstance(kind_raw, str):
            try:
                kind_val = KnowledgeKind(kind_raw)
            except ValueError as exc:
                raise InvalidKnowledgeItemError(
                    f"Unknown KnowledgeKind: {kind_raw}"
                ) from exc
        else:
            raise InvalidKnowledgeItemError(f"Invalid kind: {kind_raw}")

        status_raw = payload.get("status", KnowledgeStatus.ACTIVE.value)
        if isinstance(status_raw, KnowledgeStatus):
            status_val = status_raw
        elif isinstance(status_raw, str):
            try:
                status_val = KnowledgeStatus(status_raw)
            except ValueError as exc:
                raise InvalidKnowledgeItemError(
                    f"Unknown KnowledgeStatus: {status_raw}"
                ) from exc
        else:
            raise InvalidKnowledgeItemError(f"Invalid status: {status_raw}")

        conf_data = payload.get("confidence")
        if isinstance(conf_data, Confidence):
            conf = conf_data
        elif isinstance(conf_data, Mapping):
            conf = Confidence(
                **{
                    k: v
                    for k, v in conf_data.items()
                    if k in ("value", "source", "reasons", "metadata")
                }
            )
        else:
            raise InvalidKnowledgeItemError(
                f"Invalid confidence payload in KnowledgeItem: {conf_data}"
            )

        ev_raw = payload.get("evidence", ())
        ev_list = []
        for item in ev_raw:
            if isinstance(item, Evidence):
                ev_list.append(item)
            elif isinstance(item, Mapping):
                ev_list.append(Evidence.from_mapping(item))

        rel_raw = payload.get("relations", ())
        rel_list = []
        for item in rel_raw:
            if isinstance(item, KnowledgeRelation):
                rel_list.append(item)
            elif isinstance(item, Mapping):
                rel_list.append(KnowledgeRelation.from_mapping(item))

        ts_raw = payload.get("temporal_scope")
        if isinstance(ts_raw, TemporalScope):
            ts_val = ts_raw
        elif isinstance(ts_raw, Mapping):
            ts_val = TemporalScope.from_mapping(ts_raw)
        else:
            ts_val = TemporalScope()

        sens_raw = payload.get("sensitivity")
        sens_val: SensitivityLevel | None = None
        if sens_raw is not None:
            if isinstance(sens_raw, SensitivityLevel):
                sens_val = sens_raw
            elif isinstance(sens_raw, str):
                try:
                    sens_val = SensitivityLevel(sens_raw)
                except ValueError as exc:
                    raise InvalidKnowledgeItemError(
                        f"Unknown SensitivityLevel: {sens_raw}"
                    ) from exc
            else:
                raise InvalidKnowledgeItemError(f"Invalid sensitivity: {sens_raw}")

        created_at = _parse_dt(payload.get("created_at"), "created_at") or _utc_now()
        updated_at = _parse_dt(payload.get("updated_at"), "updated_at") or created_at

        return cls(
            id=payload["id"],
            statement=payload["statement"],
            kind=kind_val,
            confidence=conf,
            status=status_val,
            evidence=tuple(ev_list),
            relations=tuple(rel_list),
            temporal_scope=ts_val,
            sensitivity=sens_val,
            actor_id=payload.get("actor_id"),
            resource_id=payload.get("resource_id"),
            version=payload.get("version", 1),
            supersedes_id=payload.get("supersedes_id"),
            superseded_by_id=payload.get("superseded_by_id"),
            invalidated_at=_parse_dt(payload.get("invalidated_at"), "invalidated_at"),
            invalidation_reason=payload.get("invalidation_reason"),
            created_at=created_at,
            updated_at=updated_at,
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeItem:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(data)


# ── Contradiction ─────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Contradiction:
    """Explicit representation of a conflict between two KnowledgeItems.

    Never resolves automatically: a preferred item may be nominated, but
    the losing item is kept for auditability.
    """

    item_a_id: str
    item_b_id: str
    id: str = field(
        default_factory=lambda: generate_cognitive_id("contradiction", "knowledge")
    )
    severity: ContradictionSeverity = ContradictionSeverity.MEDIUM
    status: ContradictionStatus = ContradictionStatus.UNRESOLVED
    supporting_evidence: tuple[Evidence, ...] = ()
    explanation: str | None = None
    preferred_id: str | None = None
    preference_reason: str | None = None
    remaining_uncertainty: str | None = None
    actor_id: str | None = None
    created_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidContradictionError("Contradiction.id must not be empty")
        if not self.item_a_id.strip():
            raise InvalidContradictionError("Contradiction.item_a_id must not be empty")
        if not self.item_b_id.strip():
            raise InvalidContradictionError("Contradiction.item_b_id must not be empty")
        if self.item_a_id == self.item_b_id:
            raise InvalidContradictionError(
                "Contradiction must reference two distinct items"
            )

        if self.preferred_id is not None:
            if self.preferred_id not in (self.item_a_id, self.item_b_id):
                raise InvalidContradictionError(
                    "Contradiction.preferred_id must be one of item_a_id or item_b_id"
                )
            if not self.preference_reason or not self.preference_reason.strip():
                raise InvalidContradictionError(
                    "Contradiction.preference_reason required when preferred_id is set"
                )

        _require_aware(self.created_at, "Contradiction.created_at")
        object.__setattr__(
            self, "supporting_evidence", tuple(self.supporting_evidence or ())
        )
        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization."""
        return {
            "id": self.id,
            "item_a_id": self.item_a_id,
            "item_b_id": self.item_b_id,
            "severity": self.severity.value,
            "status": self.status.value,
            "supporting_evidence": [e.serialize() for e in self.supporting_evidence],
            "explanation": self.explanation,
            "preferred_id": self.preferred_id,
            "preference_reason": self.preference_reason,
            "remaining_uncertainty": self.remaining_uncertainty,
            "actor_id": self.actor_id,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> Contradiction:
        """Canonical deserialization from mapping."""

        def _parse_dt(raw: Any, field_name: str) -> datetime | None:
            if raw is None:
                return None
            if isinstance(raw, datetime):
                return raw
            if isinstance(raw, str):
                try:
                    return datetime.fromisoformat(raw)
                except ValueError as exc:
                    raise InvalidContradictionError(
                        f"Invalid ISO timestamp for {field_name}: {raw}"
                    ) from exc
            raise InvalidContradictionError(
                f"Expected timestamp string for {field_name}: {raw}"
            )

        sev_raw = payload.get("severity", ContradictionSeverity.MEDIUM.value)
        if isinstance(sev_raw, ContradictionSeverity):
            sev_val = sev_raw
        elif isinstance(sev_raw, str):
            try:
                sev_val = ContradictionSeverity(sev_raw)
            except ValueError as exc:
                raise InvalidContradictionError(
                    f"Unknown ContradictionSeverity: {sev_raw}"
                ) from exc
        else:
            raise InvalidContradictionError(f"Invalid severity: {sev_raw}")

        stat_raw = payload.get("status", ContradictionStatus.UNRESOLVED.value)
        if isinstance(stat_raw, ContradictionStatus):
            stat_val = stat_raw
        elif isinstance(stat_raw, str):
            try:
                stat_val = ContradictionStatus(stat_raw)
            except ValueError as exc:
                raise InvalidContradictionError(
                    f"Unknown ContradictionStatus: {stat_raw}"
                ) from exc
        else:
            raise InvalidContradictionError(f"Invalid status: {stat_raw}")

        ev_raw = payload.get("supporting_evidence", ())
        ev_list = []
        for item in ev_raw:
            if isinstance(item, Evidence):
                ev_list.append(item)
            elif isinstance(item, Mapping):
                ev_list.append(Evidence.from_mapping(item))

        created_at = _parse_dt(payload.get("created_at"), "created_at") or _utc_now()

        return cls(
            id=payload["id"],
            item_a_id=payload["item_a_id"],
            item_b_id=payload["item_b_id"],
            severity=sev_val,
            status=stat_val,
            supporting_evidence=tuple(ev_list),
            explanation=payload.get("explanation"),
            preferred_id=payload.get("preferred_id"),
            preference_reason=payload.get("preference_reason"),
            remaining_uncertainty=payload.get("remaining_uncertainty"),
            actor_id=payload.get("actor_id"),
            created_at=created_at,
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Contradiction:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(data)


# ── KnowledgeBundle ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class KnowledgeBundle:
    """Immutable container grouping the output of a cognitive process.

    Not a store: no search, no persistence, no indexing.
    """

    id: str = field(
        default_factory=lambda: generate_cognitive_id("knowledge-bundle", "knowledge")
    )
    items: tuple[KnowledgeItem, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    relations: tuple[KnowledgeRelation, ...] = ()
    contradictions: tuple[Contradiction, ...] = ()
    open_questions: tuple[str, ...] = ()
    findings: tuple[str, ...] = ()
    actor_id: str | None = None
    status: str = "complete"
    created_at: datetime = field(default_factory=_utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidKnowledgeBundleError("KnowledgeBundle.id must not be empty")
        if not self.status.strip():
            raise InvalidKnowledgeBundleError(
                "KnowledgeBundle.status must not be empty"
            )
        _require_aware(self.created_at, "KnowledgeBundle.created_at")

        item_ids = [i.id for i in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise InvalidKnowledgeBundleError(
                "KnowledgeBundle.items must not contain duplicate ids"
            )

        object.__setattr__(self, "items", tuple(self.items or ()))
        object.__setattr__(self, "evidence", tuple(self.evidence or ()))
        object.__setattr__(self, "relations", tuple(self.relations or ()))
        object.__setattr__(self, "contradictions", tuple(self.contradictions or ()))
        object.__setattr__(self, "open_questions", tuple(self.open_questions or ()))
        object.__setattr__(self, "findings", tuple(self.findings or ()))
        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def has_contradictions(self) -> bool:
        return bool(self.contradictions)

    @property
    def has_open_questions(self) -> bool:
        return bool(self.open_questions)

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization."""
        return {
            "id": self.id,
            "items": [i.serialize() for i in self.items],
            "evidence": [e.serialize() for e in self.evidence],
            "relations": [r.serialize() for r in self.relations],
            "contradictions": [c.serialize() for c in self.contradictions],
            "open_questions": list(self.open_questions),
            "findings": list(self.findings),
            "actor_id": self.actor_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "item_count": self.item_count,
            "has_contradictions": self.has_contradictions,
            "has_open_questions": self.has_open_questions,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> KnowledgeBundle:
        """Canonical deserialization from mapping."""

        def _parse_dt(raw: Any, field_name: str) -> datetime | None:
            if raw is None:
                return None
            if isinstance(raw, datetime):
                return raw
            if isinstance(raw, str):
                try:
                    return datetime.fromisoformat(raw)
                except ValueError as exc:
                    raise InvalidKnowledgeBundleError(
                        f"Invalid ISO timestamp for {field_name}: {raw}"
                    ) from exc
            raise InvalidKnowledgeBundleError(
                f"Expected timestamp string for {field_name}: {raw}"
            )

        items_raw = payload.get("items", ())
        items_list = []
        for item in items_raw:
            if isinstance(item, KnowledgeItem):
                items_list.append(item)
            elif isinstance(item, Mapping):
                items_list.append(KnowledgeItem.from_mapping(item))

        ev_raw = payload.get("evidence", ())
        ev_list = []
        for item in ev_raw:
            if isinstance(item, Evidence):
                ev_list.append(item)
            elif isinstance(item, Mapping):
                ev_list.append(Evidence.from_mapping(item))

        rel_raw = payload.get("relations", ())
        rel_list = []
        for item in rel_raw:
            if isinstance(item, KnowledgeRelation):
                rel_list.append(item)
            elif isinstance(item, Mapping):
                rel_list.append(KnowledgeRelation.from_mapping(item))

        contra_raw = payload.get("contradictions", ())
        contra_list = []
        for item in contra_raw:
            if isinstance(item, Contradiction):
                contra_list.append(item)
            elif isinstance(item, Mapping):
                contra_list.append(Contradiction.from_mapping(item))

        created_at = _parse_dt(payload.get("created_at"), "created_at") or _utc_now()

        return cls(
            id=payload["id"],
            items=tuple(items_list),
            evidence=tuple(ev_list),
            relations=tuple(rel_list),
            contradictions=tuple(contra_list),
            open_questions=tuple(payload.get("open_questions") or ()),
            findings=tuple(payload.get("findings") or ()),
            actor_id=payload.get("actor_id"),
            status=payload.get("status", "complete"),
            created_at=created_at,
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeBundle:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(data)
