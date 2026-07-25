"""Phase 8.9 – Contradiction Resolution Contracts & Enums.

Defines immutable, typed contracts for contradiction resolution proposals and results.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.cognitive.contracts import utc_now
from cmm.cognitive.errors import InvalidResolutionProposalError


def _require_aware(value: datetime | None, field_name: str) -> None:
    if value is not None and value.tzinfo is None:
        raise InvalidResolutionProposalError(
            f"{field_name} must be timezone-aware when provided"
        )


class ResolutionDecision(str, Enum):
    """Enumeration of possible contradiction resolution decisions."""

    KEEP_BOTH = "keep_both"
    PREFER_ITEM_A = "prefer_item_a"
    PREFER_ITEM_B = "prefer_item_b"
    MERGE_INFORMATION = "merge_information"
    MARK_ONE_INVALID = "mark_one_invalid"
    REQUEST_HUMAN_REVIEW = "request_human_review"
    DEFER = "defer"


class ResolutionStatus(str, Enum):
    """Enumeration of contradiction resolution statuses."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class ContradictionResolutionProposal:
    """Complete proposal for resolving a contradiction between knowledge items."""

    id: str
    contradiction_id: str
    item_a_id: str
    item_b_id: str
    decision: ResolutionDecision
    status: ResolutionStatus
    confidence: float
    rationale: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    actor_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise InvalidResolutionProposalError("id must be a non-empty string")
        object.__setattr__(self, "id", self.id.strip())

        if (
            not isinstance(self.contradiction_id, str)
            or not self.contradiction_id.strip()
        ):
            raise InvalidResolutionProposalError(
                "contradiction_id must be a non-empty string"
            )
        object.__setattr__(self, "contradiction_id", self.contradiction_id.strip())

        if not isinstance(self.item_a_id, str) or not self.item_a_id.strip():
            raise InvalidResolutionProposalError("item_a_id must be a non-empty string")
        object.__setattr__(self, "item_a_id", self.item_a_id.strip())

        if not isinstance(self.item_b_id, str) or not self.item_b_id.strip():
            raise InvalidResolutionProposalError("item_b_id must be a non-empty string")
        object.__setattr__(self, "item_b_id", self.item_b_id.strip())

        if self.item_a_id == self.item_b_id:
            raise InvalidResolutionProposalError(
                "item_a_id and item_b_id must be distinct"
            )

        dec_val = self.decision
        if isinstance(dec_val, str):
            try:
                dec_val = ResolutionDecision(dec_val)
            except ValueError as exc:
                raise InvalidResolutionProposalError(
                    f"Unknown ResolutionDecision: {dec_val}"
                ) from exc
        elif not isinstance(dec_val, ResolutionDecision):
            raise InvalidResolutionProposalError(f"Invalid decision: {dec_val}")
        object.__setattr__(self, "decision", dec_val)

        stat_val = self.status
        if isinstance(stat_val, str):
            try:
                stat_val = ResolutionStatus(stat_val)
            except ValueError as exc:
                raise InvalidResolutionProposalError(
                    f"Unknown ResolutionStatus: {stat_val}"
                ) from exc
        elif not isinstance(stat_val, ResolutionStatus):
            raise InvalidResolutionProposalError(f"Invalid status: {stat_val}")
        object.__setattr__(self, "status", stat_val)

        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not (0.0 <= float(self.confidence) <= 1.0)
        ):
            raise InvalidResolutionProposalError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
        object.__setattr__(self, "confidence", float(self.confidence))

        object.__setattr__(self, "rationale", tuple(self.rationale or ()))
        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids or ()))

        if self.actor_id is not None:
            if not isinstance(self.actor_id, str):
                raise InvalidResolutionProposalError(
                    "actor_id must be a string or None"
                )
            actor_str = self.actor_id.strip()
            object.__setattr__(self, "actor_id", actor_str if actor_str else None)

        if not isinstance(self.created_at, datetime):
            raise InvalidResolutionProposalError("created_at must be a datetime")
        _require_aware(self.created_at, "created_at")

        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization."""
        return {
            "id": self.id,
            "contradiction_id": self.contradiction_id,
            "item_a_id": self.item_a_id,
            "item_b_id": self.item_b_id,
            "decision": self.decision.value,
            "status": self.status.value,
            "confidence": self.confidence,
            "rationale": list(self.rationale),
            "evidence_ids": list(self.evidence_ids),
            "actor_id": self.actor_id,
            "created_at": self.created_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(
        cls, payload: Mapping[str, Any]
    ) -> ContradictionResolutionProposal:
        """Canonical deserialization from mapping."""
        created_at_raw = payload.get("created_at")
        if isinstance(created_at_raw, datetime):
            created_at = created_at_raw
        elif isinstance(created_at_raw, str):
            try:
                created_at = datetime.fromisoformat(created_at_raw)
            except ValueError as exc:
                raise InvalidResolutionProposalError(
                    f"Invalid ISO format for created_at: {created_at_raw}"
                ) from exc
        else:
            created_at = utc_now()

        dec_raw = payload.get("decision")
        if isinstance(dec_raw, ResolutionDecision):
            decision = dec_raw
        elif isinstance(dec_raw, str):
            try:
                decision = ResolutionDecision(dec_raw)
            except ValueError as exc:
                raise InvalidResolutionProposalError(
                    f"Unknown ResolutionDecision: {dec_raw}"
                ) from exc
        else:
            raise InvalidResolutionProposalError(f"Invalid decision: {dec_raw}")

        stat_raw = payload.get("status", ResolutionStatus.PROPOSED)
        if isinstance(stat_raw, ResolutionStatus):
            status = stat_raw
        elif isinstance(stat_raw, str):
            try:
                status = ResolutionStatus(stat_raw)
            except ValueError as exc:
                raise InvalidResolutionProposalError(
                    f"Unknown ResolutionStatus: {stat_raw}"
                ) from exc
        else:
            raise InvalidResolutionProposalError(f"Invalid status: {stat_raw}")

        prop_id = payload.get("id")
        if not isinstance(prop_id, str):
            raise InvalidResolutionProposalError("id must be a string")

        contradiction_id = payload.get("contradiction_id")
        if not isinstance(contradiction_id, str):
            raise InvalidResolutionProposalError("contradiction_id must be a string")

        item_a_id = payload.get("item_a_id")
        if not isinstance(item_a_id, str):
            raise InvalidResolutionProposalError("item_a_id must be a string")

        item_b_id = payload.get("item_b_id")
        if not isinstance(item_b_id, str):
            raise InvalidResolutionProposalError("item_b_id must be a string")

        conf_raw = payload.get("confidence")
        if conf_raw is None:
            raise InvalidResolutionProposalError("confidence is required")

        return cls(
            id=prop_id,
            contradiction_id=contradiction_id,
            item_a_id=item_a_id,
            item_b_id=item_b_id,
            decision=decision,
            status=status,
            confidence=float(conf_raw),
            rationale=tuple(payload.get("rationale") or ()),
            evidence_ids=tuple(payload.get("evidence_ids") or ()),
            actor_id=payload.get("actor_id"),
            created_at=created_at,
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContradictionResolutionProposal:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(data)


@dataclass(frozen=True, slots=True)
class ContradictionResolutionResult:
    """Future result of applying a contradiction resolution proposal."""

    proposal_id: str
    applied: bool
    status: ResolutionStatus
    affected_item_ids: tuple[str, ...] = ()
    created_records: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    started_at: datetime = field(default_factory=utc_now)
    finished_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_id, str) or not self.proposal_id.strip():
            raise InvalidResolutionProposalError(
                "proposal_id must be a non-empty string"
            )
        object.__setattr__(self, "proposal_id", self.proposal_id.strip())

        stat_val = self.status
        if isinstance(stat_val, str):
            try:
                stat_val = ResolutionStatus(stat_val)
            except ValueError as exc:
                raise InvalidResolutionProposalError(
                    f"Unknown ResolutionStatus: {stat_val}"
                ) from exc
        elif not isinstance(stat_val, ResolutionStatus):
            raise InvalidResolutionProposalError(f"Invalid status: {stat_val}")
        object.__setattr__(self, "status", stat_val)

        object.__setattr__(self, "applied", bool(self.applied))
        object.__setattr__(
            self, "affected_item_ids", tuple(self.affected_item_ids or ())
        )
        object.__setattr__(self, "created_records", tuple(self.created_records or ()))
        object.__setattr__(self, "warnings", tuple(self.warnings or ()))

        if not isinstance(self.started_at, datetime):
            raise InvalidResolutionProposalError("started_at must be a datetime")
        _require_aware(self.started_at, "started_at")

        if not isinstance(self.finished_at, datetime):
            raise InvalidResolutionProposalError("finished_at must be a datetime")
        _require_aware(self.finished_at, "finished_at")

        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization."""
        return {
            "proposal_id": self.proposal_id,
            "applied": self.applied,
            "status": self.status.value,
            "affected_item_ids": list(self.affected_item_ids),
            "created_records": list(self.created_records),
            "warnings": list(self.warnings),
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ContradictionResolutionResult:
        """Canonical deserialization from mapping."""
        prop_id = payload.get("proposal_id")
        if not isinstance(prop_id, str):
            raise InvalidResolutionProposalError("proposal_id must be a string")

        stat_raw = payload.get("status", ResolutionStatus.APPLIED)
        if isinstance(stat_raw, ResolutionStatus):
            status = stat_raw
        elif isinstance(stat_raw, str):
            try:
                status = ResolutionStatus(stat_raw)
            except ValueError as exc:
                raise InvalidResolutionProposalError(
                    f"Unknown ResolutionStatus: {stat_raw}"
                ) from exc
        else:
            raise InvalidResolutionProposalError(f"Invalid status: {stat_raw}")

        started_at_raw = payload.get("started_at")
        if isinstance(started_at_raw, datetime):
            started_at = started_at_raw
        elif isinstance(started_at_raw, str):
            try:
                started_at = datetime.fromisoformat(started_at_raw)
            except ValueError as exc:
                raise InvalidResolutionProposalError(
                    f"Invalid ISO format for started_at: {started_at_raw}"
                ) from exc
        else:
            started_at = utc_now()

        finished_at_raw = payload.get("finished_at")
        if isinstance(finished_at_raw, datetime):
            finished_at = finished_at_raw
        elif isinstance(finished_at_raw, str):
            try:
                finished_at = datetime.fromisoformat(finished_at_raw)
            except ValueError as exc:
                raise InvalidResolutionProposalError(
                    f"Invalid ISO format for finished_at: {finished_at_raw}"
                ) from exc
        else:
            finished_at = utc_now()

        return cls(
            proposal_id=prop_id,
            applied=bool(payload.get("applied", False)),
            status=status,
            affected_item_ids=tuple(payload.get("affected_item_ids") or ()),
            created_records=tuple(payload.get("created_records") or ()),
            warnings=tuple(payload.get("warnings") or ()),
            started_at=started_at,
            finished_at=finished_at,
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContradictionResolutionResult:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(data)
