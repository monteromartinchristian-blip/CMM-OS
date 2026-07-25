"""Phase 8.7 – Knowledge Consolidation Contracts & Normalization.

Defines deterministic normalization, stable fingerprints, and frozen contracts for
candidates, actions, plans, and results.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.cognitive.contracts import Confidence, utc_now
from cmm.cognitive.enums import KnowledgeRelationKind, KnowledgeStatus
from cmm.cognitive.errors import (
    InvalidConsolidationCandidateError,
    InvalidConsolidationPlanError,
)
from cmm.cognitive.identifiers import generate_cognitive_id
from cmm.cognitive.knowledge import KnowledgeItem
from cmm.cognitive.store_contracts import validate_store_id


def normalize_statement(statement: str) -> str:
    """Normalize a knowledge statement deterministically.

    Semantics:
    1. strip leading/trailing whitespace
    2. collapse consecutive whitespace to a single space
    3. Unicode NFKC normalization
    4. casefold for case-insensitivity
    """
    if not isinstance(statement, str):
        raise TypeError(f"statement must be str, got {type(statement).__name__}")
    text = statement.strip()
    text = re.sub(r"\s+", " ", text)
    text = unicodedata.normalize("NFKC", text)
    return text.casefold()


def knowledge_fingerprint(item: KnowledgeItem) -> str:
    """Generate a stable, process-independent SHA-256 fingerprint for a KnowledgeItem."""
    if not isinstance(item, KnowledgeItem):
        raise TypeError(f"item must be KnowledgeItem, got {type(item).__name__}")

    payload = {
        "kind": item.kind.value,
        "resource_id": item.resource_id,
        "statement_normalized": normalize_statement(item.statement),
        "temporal_scope": item.temporal_scope.serialize(),
    }
    canonical_json = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class ConsolidationMatchKind(str, Enum):
    EXACT_DUPLICATE = "exact_duplicate"
    NORMALIZED_DUPLICATE = "normalized_duplicate"
    VERSION_SUCCESSOR = "version_successor"
    VERSION_PREDECESSOR = "version_predecessor"
    STRUCTURAL_OVERLAP = "structural_overlap"
    RELATED = "related"
    DISTINCT = "distinct"


class ConsolidationDecision(str, Enum):
    MERGE = "merge"
    SUPERSEDE = "supersede"
    LINK = "link"
    KEEP_SEPARATE = "keep_separate"
    MANUAL_REVIEW = "manual_review"
    SKIP = "skip"


@dataclass(frozen=True, slots=True)
class ConsolidationCandidate:
    """Immutable representation of a comparison candidate between two KnowledgeItems."""

    item_a_id: str
    item_b_id: str
    match_kind: ConsolidationMatchKind
    recommended_decision: ConsolidationDecision
    confidence: Confidence
    matching_fields: tuple[str, ...] = ()
    differing_fields: tuple[str, ...] = ()
    shared_evidence_ids: tuple[str, ...] = ()
    shared_relation_ids: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_store_id(self.item_a_id, "item_a_id")
        validate_store_id(self.item_b_id, "item_b_id")

        if self.item_a_id == self.item_b_id:
            raise InvalidConsolidationCandidateError(
                "item_a_id and item_b_id must be distinct"
            )

        match_kind_norm = (
            self.match_kind
            if isinstance(self.match_kind, ConsolidationMatchKind)
            else ConsolidationMatchKind(self.match_kind)
        )
        object.__setattr__(self, "match_kind", match_kind_norm)

        rec_dec_norm = (
            self.recommended_decision
            if isinstance(self.recommended_decision, ConsolidationDecision)
            else ConsolidationDecision(self.recommended_decision)
        )
        object.__setattr__(self, "recommended_decision", rec_dec_norm)

        if isinstance(self.confidence, (int, float)):
            conf_norm = Confidence(value=float(self.confidence))
        elif isinstance(self.confidence, Confidence):
            conf_norm = self.confidence
        elif isinstance(self.confidence, dict):
            conf_norm = Confidence(
                value=float(self.confidence.get("value", 1.0)),
                source=self.confidence.get("source"),
                reasons=tuple(self.confidence.get("reasons", ())),
                metadata=dict(self.confidence.get("metadata", {})),
            )
        else:
            raise InvalidConsolidationCandidateError(
                f"Invalid confidence type: {type(self.confidence).__name__}"
            )
        object.__setattr__(self, "confidence", conf_norm)

        object.__setattr__(self, "matching_fields", tuple(self.matching_fields or ()))
        object.__setattr__(self, "differing_fields", tuple(self.differing_fields or ()))
        object.__setattr__(
            self, "shared_evidence_ids", tuple(self.shared_evidence_ids or ())
        )
        object.__setattr__(
            self, "shared_relation_ids", tuple(self.shared_relation_ids or ())
        )
        object.__setattr__(self, "reasons", tuple(self.reasons or ()))
        object.__setattr__(self, "warnings", tuple(self.warnings or ()))
        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe dictionary representation."""
        return {
            "item_a_id": self.item_a_id,
            "item_b_id": self.item_b_id,
            "match_kind": self.match_kind.value,
            "recommended_decision": self.recommended_decision.value,
            "confidence": self.confidence.to_dict(),
            "matching_fields": list(self.matching_fields),
            "differing_fields": list(self.differing_fields),
            "shared_evidence_ids": list(self.shared_evidence_ids),
            "shared_relation_ids": list(self.shared_relation_ids),
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ConsolidationCandidate:
        conf_raw = payload.get("confidence")
        if isinstance(conf_raw, dict):
            conf = Confidence(
                value=float(conf_raw["value"]),
                source=conf_raw.get("source"),
                reasons=tuple(conf_raw.get("reasons", ())),
                metadata=dict(conf_raw.get("metadata", {})),
            )
        elif isinstance(conf_raw, (int, float)):
            conf = Confidence(value=float(conf_raw))
        else:
            conf = Confidence(value=1.0)

        return cls(
            item_a_id=payload["item_a_id"],
            item_b_id=payload["item_b_id"],
            match_kind=ConsolidationMatchKind(payload["match_kind"]),
            recommended_decision=ConsolidationDecision(payload["recommended_decision"]),
            confidence=conf,
            matching_fields=tuple(payload.get("matching_fields", ())),
            differing_fields=tuple(payload.get("differing_fields", ())),
            shared_evidence_ids=tuple(payload.get("shared_evidence_ids", ())),
            shared_relation_ids=tuple(payload.get("shared_relation_ids", ())),
            reasons=tuple(payload.get("reasons", ())),
            warnings=tuple(payload.get("warnings", ())),
            metadata=payload.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ConsolidationCandidate:
        return cls.from_mapping(payload)


@dataclass(frozen=True, slots=True)
class ConsolidationAction:
    """Immutable representation of a single action within a ConsolidationPlan."""

    decision: ConsolidationDecision
    source_item_ids: tuple[str, ...]
    target_item_id: str | None = None
    create_target: bool = False
    preserve_sources: bool = True
    result_status: KnowledgeStatus | None = None
    relation_kind: KnowledgeRelationKind | None = None
    reason: str = ""
    actor_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        dec_norm = (
            self.decision
            if isinstance(self.decision, ConsolidationDecision)
            else ConsolidationDecision(self.decision)
        )
        object.__setattr__(self, "decision", dec_norm)

        sources = tuple(self.source_item_ids or ())
        for sid in sources:
            validate_store_id(sid, "source_item_id")
        object.__setattr__(self, "source_item_ids", sources)

        if self.target_item_id is not None:
            validate_store_id(self.target_item_id, "target_item_id")

        if self.result_status is not None and not isinstance(
            self.result_status, KnowledgeStatus
        ):
            object.__setattr__(
                self, "result_status", KnowledgeStatus(self.result_status)
            )

        if self.relation_kind is not None and not isinstance(
            self.relation_kind, KnowledgeRelationKind
        ):
            object.__setattr__(
                self, "relation_kind", KnowledgeRelationKind(self.relation_kind)
            )

        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    def serialize(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "source_item_ids": list(self.source_item_ids),
            "target_item_id": self.target_item_id,
            "create_target": self.create_target,
            "preserve_sources": self.preserve_sources,
            "result_status": (
                self.result_status.value if self.result_status is not None else None
            ),
            "relation_kind": (
                self.relation_kind.value if self.relation_kind is not None else None
            ),
            "reason": self.reason,
            "actor_id": self.actor_id,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ConsolidationAction:
        res_status = (
            KnowledgeStatus(payload["result_status"])
            if payload.get("result_status") is not None
            else None
        )
        rel_kind = (
            KnowledgeRelationKind(payload["relation_kind"])
            if payload.get("relation_kind") is not None
            else None
        )
        return cls(
            decision=ConsolidationDecision(payload["decision"]),
            source_item_ids=tuple(payload.get("source_item_ids", ())),
            target_item_id=payload.get("target_item_id"),
            create_target=payload.get("create_target", False),
            preserve_sources=payload.get("preserve_sources", True),
            result_status=res_status,
            relation_kind=rel_kind,
            reason=payload.get("reason", ""),
            actor_id=payload.get("actor_id", ""),
            metadata=payload.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ConsolidationAction:
        return cls.from_mapping(payload)


@dataclass(frozen=True, slots=True)
class ConsolidationPlan:
    """Immutable technical proposal for a set of consolidation actions."""

    actions: tuple[ConsolidationAction, ...]
    actor_id: str
    id: str = field(
        default_factory=lambda: generate_cognitive_id("plan", "consolidation")
    )
    candidate_ids: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=utc_now)
    dry_run: bool = True
    warnings: tuple[str, ...] = ()
    expected_fingerprints: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_store_id(self.id, "plan_id")
        validate_store_id(self.actor_id, "actor_id")

        actions_tuple = tuple(self.actions or ())
        if not actions_tuple:
            raise InvalidConsolidationPlanError(
                "ConsolidationPlan must contain at least one action"
            )
        object.__setattr__(self, "actions", actions_tuple)

        if self.created_at.tzinfo is None:
            raise InvalidConsolidationPlanError(
                "ConsolidationPlan.created_at must be timezone-aware"
            )

        # Check action consistency (no duplicate conflicting target/source actions)
        seen_superseded_sources: set[str] = set()
        for act in actions_tuple:
            if act.decision in (
                ConsolidationDecision.MERGE,
                ConsolidationDecision.SUPERSEDE,
            ):
                for sid in act.source_item_ids:
                    if (
                        sid == act.target_item_id
                        and act.decision == ConsolidationDecision.SUPERSEDE
                    ):
                        raise InvalidConsolidationPlanError(
                            f"Action cannot supersede item '{sid}' by itself"
                        )
                    if sid in seen_superseded_sources:
                        raise InvalidConsolidationPlanError(
                            f"Item '{sid}' is subject to multiple conflicting actions in plan"
                        )
                    seen_superseded_sources.add(sid)

        object.__setattr__(self, "candidate_ids", tuple(self.candidate_ids or ()))
        object.__setattr__(self, "warnings", tuple(self.warnings or ()))
        object.__setattr__(
            self,
            "expected_fingerprints",
            MappingProxyType(dict(self.expected_fingerprints or {})),
        )
        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "actions": [a.serialize() for a in self.actions],
            "candidate_ids": list(self.candidate_ids),
            "actor_id": self.actor_id,
            "created_at": self.created_at.isoformat(),
            "dry_run": self.dry_run,
            "warnings": list(self.warnings),
            "expected_fingerprints": dict(self.expected_fingerprints),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ConsolidationPlan:
        created_at_dt = datetime.fromisoformat(payload["created_at"])
        actions_list = [
            ConsolidationAction.from_mapping(a) for a in payload.get("actions", [])
        ]
        return cls(
            id=payload["id"],
            actions=tuple(actions_list),
            candidate_ids=tuple(payload.get("candidate_ids", ())),
            actor_id=payload["actor_id"],
            created_at=created_at_dt,
            dry_run=payload.get("dry_run", True),
            warnings=tuple(payload.get("warnings", ())),
            expected_fingerprints=payload.get("expected_fingerprints", {}),
            metadata=payload.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ConsolidationPlan:
        return cls.from_mapping(payload)


@dataclass(frozen=True, slots=True)
class ConsolidationResult:
    """Immutable audit record resulting from execution or preview of a ConsolidationPlan."""

    plan_id: str
    applied: bool
    created_item_ids: tuple[str, ...] = ()
    updated_item_ids: tuple[str, ...] = ()
    superseded_item_ids: tuple[str, ...] = ()
    linked_relation_ids: tuple[str, ...] = ()
    unchanged_item_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    started_at: datetime = field(default_factory=utc_now)
    finished_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_store_id(self.plan_id, "plan_id")

        if self.started_at.tzinfo is None or self.finished_at.tzinfo is None:
            raise ValueError("ConsolidationResult timestamps must be timezone-aware")
        if self.started_at > self.finished_at:
            raise ValueError("started_at cannot be after finished_at")

        object.__setattr__(self, "created_item_ids", tuple(self.created_item_ids or ()))
        object.__setattr__(self, "updated_item_ids", tuple(self.updated_item_ids or ()))
        object.__setattr__(
            self, "superseded_item_ids", tuple(self.superseded_item_ids or ())
        )
        object.__setattr__(
            self, "linked_relation_ids", tuple(self.linked_relation_ids or ())
        )
        object.__setattr__(
            self, "unchanged_item_ids", tuple(self.unchanged_item_ids or ())
        )
        object.__setattr__(self, "warnings", tuple(self.warnings or ()))
        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    def serialize(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "applied": self.applied,
            "created_item_ids": list(self.created_item_ids),
            "updated_item_ids": list(self.updated_item_ids),
            "superseded_item_ids": list(self.superseded_item_ids),
            "linked_relation_ids": list(self.linked_relation_ids),
            "unchanged_item_ids": list(self.unchanged_item_ids),
            "warnings": list(self.warnings),
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ConsolidationResult:
        return cls(
            plan_id=payload["plan_id"],
            applied=payload["applied"],
            created_item_ids=tuple(payload.get("created_item_ids", ())),
            updated_item_ids=tuple(payload.get("updated_item_ids", ())),
            superseded_item_ids=tuple(payload.get("superseded_item_ids", ())),
            linked_relation_ids=tuple(payload.get("linked_relation_ids", ())),
            unchanged_item_ids=tuple(payload.get("unchanged_item_ids", ())),
            warnings=tuple(payload.get("warnings", ())),
            started_at=datetime.fromisoformat(payload["started_at"]),
            finished_at=datetime.fromisoformat(payload["finished_at"]),
            metadata=payload.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ConsolidationResult:
        return cls.from_mapping(payload)
