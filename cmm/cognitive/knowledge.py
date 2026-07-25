"""Phase 8.4 – Knowledge Model.

Immutable, validated, serialisable cognitive contracts.  No persistence,
no search, no agents.  Every contract validates its invariants in
``__post_init__`` and exposes a deterministic ``to_dict()`` / ``from_dict()``
pair.

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

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
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
    TemporalScopeKind,
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
    metadata: dict[str, Any] = field(default_factory=dict)

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

        object.__setattr__(self, "metadata", dict(self.metadata))

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
        if self.valid_until is not None and moment > self.valid_until:
            return False
        return True

    def contains(self, moment: datetime) -> bool:
        """Alias for :meth:`is_valid_at`."""
        return self.is_valid_at(moment)

    @property
    def validity_status(self) -> str:
        """Broad status label: valid / expired / future / unknown / timeless."""
        now = _utc_now()
        if self.kind is TemporalScopeKind.TIMELESS:
            return "timeless"
        if self.kind is TemporalScopeKind.UNKNOWN:
            return "unknown"
        if self.valid_until is not None and now > self.valid_until:
            return "expired"
        if self.valid_from is not None and now < self.valid_from:
            return "future"
        if self.expires_at is not None and now > self.expires_at:
            return "potentially_obsolete"
        return "valid"

    def to_dict(self) -> dict[str, Any]:
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
            "validity_status": self.validity_status,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemporalScope:
        def _parse(key: str) -> datetime | None:
            raw = data.get(key)
            return datetime.fromisoformat(raw) if raw is not None else None

        return cls(
            kind=TemporalScopeKind(data["kind"]),
            observed_at=_parse("observed_at"),
            valid_from=_parse("valid_from"),
            valid_until=_parse("valid_until"),
            expires_at=_parse("expires_at"),
            last_verified_at=_parse("last_verified_at"),
            metadata=dict(data.get("metadata") or {}),
        )


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
    metadata: dict[str, Any] = field(default_factory=dict)

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
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Evidence:
        return cls(
            id=data["id"],
            resource_id=data["resource_id"],
            fragment=data["fragment"],
            confidence=Confidence(
                **{
                    k: v
                    for k, v in data["confidence"].items()
                    if k in ("value", "source", "reasons", "metadata")
                }
            ),
            kind=EvidenceKind(data.get("kind", EvidenceKind.UNKNOWN.value)),
            polarity=EvidencePolarityKind(
                data.get("polarity", EvidencePolarityKind.NEUTRAL.value)
            ),
            locator=data.get("locator"),
            section=data.get("section"),
            page=data.get("page"),
            char_start=data.get("char_start"),
            char_end=data.get("char_end"),
            actor_id=data.get("actor_id"),
            extraction_candidate_id=data.get("extraction_candidate_id"),
            resource_provenance_id=data.get("resource_provenance_id"),
            observed_at=datetime.fromisoformat(data["observed_at"]),
            metadata=dict(data.get("metadata") or {}),
        )


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
    metadata: dict[str, Any] = field(default_factory=dict)

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
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeRelation:
        return cls(
            id=data["id"],
            source_id=data["source_id"],
            target_id=data["target_id"],
            kind=KnowledgeRelationKind(data["kind"]),
            confidence=Confidence(
                **{
                    k: v
                    for k, v in data["confidence"].items()
                    if k in ("value", "source", "reasons", "metadata")
                }
            ),
            actor_id=data.get("actor_id"),
            provenance=data.get("provenance"),
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=dict(data.get("metadata") or {}),
        )


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
    sensitivity: str | None = None
    actor_id: str | None = None
    resource_id: str | None = None
    version: int = 1
    supersedes_id: str | None = None
    superseded_by_id: str | None = None
    invalidated_at: datetime | None = None
    invalidation_reason: str | None = None
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

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

        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "relations", tuple(self.relations))
        object.__setattr__(self, "metadata", dict(self.metadata))

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
        metadata: dict[str, Any] | None = None,
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "statement": self.statement,
            "kind": self.kind.value,
            "status": self.status.value,
            "confidence": self.confidence.to_dict(),
            "evidence": [e.to_dict() for e in self.evidence],
            "relations": [r.to_dict() for r in self.relations],
            "temporal_scope": self.temporal_scope.to_dict(),
            "sensitivity": self.sensitivity,
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
    metadata: dict[str, Any] = field(default_factory=dict)

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
        object.__setattr__(self, "supporting_evidence", tuple(self.supporting_evidence))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "item_a_id": self.item_a_id,
            "item_b_id": self.item_b_id,
            "severity": self.severity.value,
            "status": self.status.value,
            "supporting_evidence": [e.to_dict() for e in self.supporting_evidence],
            "explanation": self.explanation,
            "preferred_id": self.preferred_id,
            "preference_reason": self.preference_reason,
            "remaining_uncertainty": self.remaining_uncertainty,
            "actor_id": self.actor_id,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }


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
    metadata: dict[str, Any] = field(default_factory=dict)

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

        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "relations", tuple(self.relations))
        object.__setattr__(self, "contradictions", tuple(self.contradictions))
        object.__setattr__(self, "open_questions", tuple(self.open_questions))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def item_count(self) -> int:
        return len(self.items)

    @property
    def has_contradictions(self) -> bool:
        return bool(self.contradictions)

    @property
    def has_open_questions(self) -> bool:
        return bool(self.open_questions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "items": [i.to_dict() for i in self.items],
            "evidence": [e.to_dict() for e in self.evidence],
            "relations": [r.to_dict() for r in self.relations],
            "contradictions": [c.to_dict() for c in self.contradictions],
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
