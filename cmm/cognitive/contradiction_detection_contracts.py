"""Phase 8.8 – Contradiction Detection Contracts & Enums.

Defines immutable, typed contracts for signals, detections, and detection results.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.cognitive.contracts import utc_now
from cmm.cognitive.enums import ContradictionSeverity
from cmm.cognitive.errors import (
    InvalidContradictionDetectionError,
    InvalidContradictionSignalError,
)
from cmm.cognitive.knowledge import _require_aware
from cmm.cognitive.query import KnowledgeQuery


class ContradictionKind(str, Enum):
    """Classification of contradiction types."""

    DIRECT = "direct"
    NEGATION = "negation"
    QUANTITATIVE = "quantitative"
    TEMPORAL = "temporal"
    STATUS = "status"
    LINEAGE = "lineage"
    RELATIONAL = "relational"
    PROVENANCE = "provenance"
    POSSIBLE = "possible"


@dataclass(frozen=True, slots=True)
class ContradictionSignal:
    """An atomic signal indicating a specific conflict between two items."""

    kind: ContradictionKind
    field: str
    value_a: Any
    value_b: Any
    strength: float
    reason: str
    evidence_ids: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        kind_val = self.kind
        if isinstance(kind_val, str):
            try:
                kind_val = ContradictionKind(kind_val)
            except ValueError as exc:
                raise InvalidContradictionSignalError(
                    f"Unknown ContradictionKind: {kind_val}"
                ) from exc
        elif not isinstance(kind_val, ContradictionKind):
            raise InvalidContradictionSignalError(f"Invalid kind: {kind_val}")
        object.__setattr__(self, "kind", kind_val)

        if not isinstance(self.field, str) or not self.field.strip():
            raise InvalidContradictionSignalError(
                "ContradictionSignal.field must be a non-empty string"
            )

        if not isinstance(self.reason, str) or not self.reason.strip():
            raise InvalidContradictionSignalError(
                "ContradictionSignal.reason must be a non-empty string"
            )

        if not isinstance(self.strength, (int, float)) or not (
            0.0 <= float(self.strength) <= 1.0
        ):
            raise InvalidContradictionSignalError(
                f"ContradictionSignal.strength must be between 0.0 and 1.0, got {self.strength}"
            )
        object.__setattr__(self, "strength", float(self.strength))

        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids or ()))
        object.__setattr__(self, "warnings", tuple(self.warnings or ()))
        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization."""
        return {
            "kind": self.kind.value,
            "field": self.field,
            "value_a": self.value_a,
            "value_b": self.value_b,
            "strength": self.strength,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ContradictionSignal:
        """Canonical deserialization from mapping."""
        kind_raw = payload.get("kind")
        if isinstance(kind_raw, ContradictionKind):
            kind_val = kind_raw
        elif isinstance(kind_raw, str):
            try:
                kind_val = ContradictionKind(kind_raw)
            except ValueError as exc:
                raise InvalidContradictionSignalError(
                    f"Unknown ContradictionKind: {kind_raw}"
                ) from exc
        else:
            raise InvalidContradictionSignalError(f"Invalid kind: {kind_raw}")

        field_val = payload.get("field")
        if not isinstance(field_val, str) or not field_val.strip():
            raise InvalidContradictionSignalError(
                "ContradictionSignal.field must be non-empty string"
            )

        reason_val = payload.get("reason")
        if not isinstance(reason_val, str) or not reason_val.strip():
            raise InvalidContradictionSignalError(
                "ContradictionSignal.reason must be non-empty string"
            )

        strength_raw = payload.get("strength")
        if not isinstance(strength_raw, (int, float)) or not (
            0.0 <= float(strength_raw) <= 1.0
        ):
            raise InvalidContradictionSignalError(
                f"ContradictionSignal.strength must be between 0.0 and 1.0, got {strength_raw}"
            )

        return cls(
            kind=kind_val,
            field=field_val,
            value_a=payload.get("value_a"),
            value_b=payload.get("value_b"),
            strength=float(strength_raw),
            reason=reason_val,
            evidence_ids=tuple(payload.get("evidence_ids") or ()),
            warnings=tuple(payload.get("warnings") or ()),
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContradictionSignal:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(data)


@dataclass(frozen=True, slots=True)
class ContradictionDetection:
    """Evaluation result comparing two KnowledgeItems."""

    item_a_id: str
    item_b_id: str
    is_contradiction: bool
    kind: ContradictionKind | None = None
    severity: ContradictionSeverity = ContradictionSeverity.LOW
    confidence: float = 0.0
    signals: tuple[ContradictionSignal, ...] = ()
    contradicting_fields: tuple[str, ...] = ()
    shared_evidence_ids: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    existing_contradiction_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.item_a_id, str) or not self.item_a_id.strip():
            raise InvalidContradictionDetectionError(
                "item_a_id must be a non-empty string"
            )
        if not isinstance(self.item_b_id, str) or not self.item_b_id.strip():
            raise InvalidContradictionDetectionError(
                "item_b_id must be a non-empty string"
            )
        if self.item_a_id == self.item_b_id:
            raise InvalidContradictionDetectionError(
                "ContradictionDetection must reference two distinct item IDs"
            )

        # Canonicalize pair order
        if self.item_a_id > self.item_b_id:
            min_id, max_id = self.item_b_id, self.item_a_id
            object.__setattr__(self, "item_a_id", min_id)
            object.__setattr__(self, "item_b_id", max_id)

        if not isinstance(self.confidence, (int, float)) or not (
            0.0 <= float(self.confidence) <= 1.0
        ):
            raise InvalidContradictionDetectionError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
        object.__setattr__(self, "confidence", float(self.confidence))

        kind_val = self.kind
        if kind_val is not None:
            if isinstance(kind_val, str):
                try:
                    kind_val = ContradictionKind(kind_val)
                except ValueError as exc:
                    raise InvalidContradictionDetectionError(
                        f"Unknown ContradictionKind: {kind_val}"
                    ) from exc
            elif not isinstance(kind_val, ContradictionKind):
                raise InvalidContradictionDetectionError(f"Invalid kind: {kind_val}")
        object.__setattr__(self, "kind", kind_val)

        sev_val = self.severity
        if isinstance(sev_val, str):
            try:
                sev_val = ContradictionSeverity(sev_val)
            except ValueError as exc:
                raise InvalidContradictionDetectionError(
                    f"Unknown ContradictionSeverity: {sev_val}"
                ) from exc
        elif not isinstance(sev_val, ContradictionSeverity):
            raise InvalidContradictionDetectionError(f"Invalid severity: {sev_val}")
        object.__setattr__(self, "severity", sev_val)

        sig_tuple = tuple(self.signals or ())
        object.__setattr__(self, "signals", sig_tuple)

        if self.is_contradiction:
            if self.kind is None:
                raise InvalidContradictionDetectionError(
                    "ContradictionDetection requires kind when is_contradiction is True"
                )
            if not sig_tuple:
                raise InvalidContradictionDetectionError(
                    "ContradictionDetection requires at least one signal when is_contradiction is True"
                )

        object.__setattr__(
            self, "contradicting_fields", tuple(self.contradicting_fields or ())
        )
        object.__setattr__(
            self, "shared_evidence_ids", tuple(self.shared_evidence_ids or ())
        )
        object.__setattr__(self, "reasons", tuple(self.reasons or ()))
        object.__setattr__(self, "warnings", tuple(self.warnings or ()))
        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization."""
        return {
            "item_a_id": self.item_a_id,
            "item_b_id": self.item_b_id,
            "is_contradiction": self.is_contradiction,
            "kind": self.kind.value if self.kind is not None else None,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "signals": [s.serialize() for s in self.signals],
            "contradicting_fields": list(self.contradicting_fields),
            "shared_evidence_ids": list(self.shared_evidence_ids),
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "existing_contradiction_id": self.existing_contradiction_id,
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ContradictionDetection:
        """Canonical deserialization from mapping."""
        item_a_id = payload.get("item_a_id")
        item_b_id = payload.get("item_b_id")
        if not isinstance(item_a_id, str) or not item_a_id.strip():
            raise InvalidContradictionDetectionError(
                "item_a_id must be a non-empty string"
            )
        if not isinstance(item_b_id, str) or not item_b_id.strip():
            raise InvalidContradictionDetectionError(
                "item_b_id must be a non-empty string"
            )

        is_contradiction = bool(payload.get("is_contradiction", False))

        kind_raw = payload.get("kind")
        kind_val: ContradictionKind | None = None
        if kind_raw is not None:
            if isinstance(kind_raw, ContradictionKind):
                kind_val = kind_raw
            elif isinstance(kind_raw, str):
                try:
                    kind_val = ContradictionKind(kind_raw)
                except ValueError as exc:
                    raise InvalidContradictionDetectionError(
                        f"Unknown ContradictionKind: {kind_raw}"
                    ) from exc
            else:
                raise InvalidContradictionDetectionError(f"Invalid kind: {kind_raw}")

        sev_raw = payload.get("severity", ContradictionSeverity.LOW.value)
        if isinstance(sev_raw, ContradictionSeverity):
            sev_val = sev_raw
        elif isinstance(sev_raw, str):
            try:
                sev_val = ContradictionSeverity(sev_raw)
            except ValueError as exc:
                raise InvalidContradictionDetectionError(
                    f"Unknown ContradictionSeverity: {sev_raw}"
                ) from exc
        else:
            raise InvalidContradictionDetectionError(f"Invalid severity: {sev_raw}")

        conf_raw = payload.get("confidence", 0.0)

        signals_raw = payload.get("signals", ())
        sig_list = []
        for s in signals_raw:
            if isinstance(s, ContradictionSignal):
                sig_list.append(s)
            elif isinstance(s, Mapping):
                sig_list.append(ContradictionSignal.from_mapping(s))

        return cls(
            item_a_id=item_a_id,
            item_b_id=item_b_id,
            is_contradiction=is_contradiction,
            kind=kind_val,
            severity=sev_val,
            confidence=float(conf_raw),
            signals=tuple(sig_list),
            contradicting_fields=tuple(payload.get("contradicting_fields") or ()),
            shared_evidence_ids=tuple(payload.get("shared_evidence_ids") or ()),
            reasons=tuple(payload.get("reasons") or ()),
            warnings=tuple(payload.get("warnings") or ()),
            existing_contradiction_id=payload.get("existing_contradiction_id"),
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContradictionDetection:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(data)


@dataclass(frozen=True, slots=True)
class ContradictionDetectionResult:
    """Batch contradiction detection result."""

    detections: tuple[ContradictionDetection, ...]
    contradiction_count: int
    possible_count: int
    non_contradiction_count: int
    existing_count: int
    created_at: datetime = field(default_factory=utc_now)
    query: KnowledgeQuery | None = None
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_aware(self.created_at, "ContradictionDetectionResult.created_at")
        object.__setattr__(self, "detections", tuple(self.detections or ()))
        object.__setattr__(self, "warnings", tuple(self.warnings or ()))
        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization."""
        return {
            "detections": [d.serialize() for d in self.detections],
            "contradiction_count": self.contradiction_count,
            "possible_count": self.possible_count,
            "non_contradiction_count": self.non_contradiction_count,
            "existing_count": self.existing_count,
            "created_at": self.created_at.isoformat(),
            "query": self.query.serialize() if self.query is not None else None,
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ContradictionDetectionResult:
        """Canonical deserialization from mapping."""
        det_raw = payload.get("detections", ())
        det_list = []
        for d in det_raw:
            if isinstance(d, ContradictionDetection):
                det_list.append(d)
            elif isinstance(d, Mapping):
                det_list.append(ContradictionDetection.from_mapping(d))

        created_at_raw = payload.get("created_at")
        if isinstance(created_at_raw, datetime):
            created_at = created_at_raw
        elif isinstance(created_at_raw, str):
            created_at = datetime.fromisoformat(created_at_raw)
        else:
            created_at = utc_now()

        query_raw = payload.get("query")
        query_val: KnowledgeQuery | None = None
        if isinstance(query_raw, KnowledgeQuery):
            query_val = query_raw
        elif isinstance(query_raw, Mapping):
            query_val = KnowledgeQuery.from_mapping(query_raw)

        return cls(
            detections=tuple(det_list),
            contradiction_count=payload.get("contradiction_count", 0),
            possible_count=payload.get("possible_count", 0),
            non_contradiction_count=payload.get("non_contradiction_count", 0),
            existing_count=payload.get("existing_count", 0),
            created_at=created_at,
            query=query_val,
            warnings=tuple(payload.get("warnings") or ()),
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContradictionDetectionResult:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(data)
