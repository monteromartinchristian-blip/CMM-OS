"""Phase 8.14 – Cognitive Reflection & Resolution Feedback Contracts.

Defines immutable, typed contracts for cognitive reflection reports, findings, reflection queries, and deterministic ID generation.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from cmm.cognitive.errors import InvalidReflectionReportError
from cmm.cognitive.resolution_contracts import ResolutionDecision
from cmm.cognitive.resolution_executor_contracts import ExecutionStatus
from cmm.cognitive.resolution_memory_contracts import ResolutionMemoryEntry


def _require_aware(value: datetime | None, field_name: str) -> None:
    if value is not None:
        if not isinstance(value, datetime):
            raise InvalidReflectionReportError(
                f"{field_name} must be a datetime instance"
            )
        if value.tzinfo is None:
            raise InvalidReflectionReportError(
                f"{field_name} must be timezone-aware when provided"
            )


def generate_reflection_report_id(
    analysed_entries: int,
    query: ReflectionQuery | Mapping[str, Any] | None = None,
    created_at: datetime | str | None = None,
    decision_distribution: Mapping[str, int] | None = None,
    contradiction_distribution: Mapping[str, int] | None = None,
    policy_distribution: Mapping[str, int] | None = None,
) -> str:
    """Generate a deterministic cognitive identifier for a reflection report."""
    if (
        isinstance(analysed_entries, bool)
        or not isinstance(analysed_entries, int)
        or analysed_entries < 0
    ):
        raise InvalidReflectionReportError(
            "analysed_entries must be a non-negative integer"
        )

    ts_val = ""
    if created_at is not None:
        if isinstance(created_at, datetime):
            ts_val = created_at.isoformat()
        else:
            ts_val = str(created_at).strip()

    q_val = ""
    if query is not None:
        if isinstance(query, ReflectionQuery):
            q_val = str(query.serialize())
        elif isinstance(query, Mapping):
            q_val = str(dict(query))
        else:
            q_val = str(query).strip()

    def _format_dist(dist: Mapping[str, int] | None) -> str:
        if not dist:
            return ""
        sorted_pairs = sorted((str(k).strip().lower(), int(v)) for k, v in dist.items())
        return ";".join(f"{k}:{v}" for k, v in sorted_pairs)

    dec_str = _format_dist(decision_distribution)
    con_str = _format_dist(contradiction_distribution)
    pol_str = _format_dist(policy_distribution)

    seed = f"{analysed_entries}:{ts_val}:{q_val}:{dec_str}:{con_str}:{pol_str}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"reflection-report:{digest}"


@dataclass(frozen=True, slots=True)
class ReflectionFinding:
    """Represents a structured conclusion or insight discovered during reflection analysis."""

    category: str
    severity: str
    description: str
    related_entry_ids: tuple[str, ...] = ()
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not isinstance(self.category, str) or not self.category.strip():
            raise InvalidReflectionReportError("category must be a non-empty string")
        object.__setattr__(self, "category", self.category.strip().lower())

        if not isinstance(self.severity, str) or not self.severity.strip():
            raise InvalidReflectionReportError("severity must be a non-empty string")
        object.__setattr__(self, "severity", self.severity.strip().lower())

        if not isinstance(self.description, str) or not self.description.strip():
            raise InvalidReflectionReportError("description must be a non-empty string")
        object.__setattr__(self, "description", self.description.strip())

        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not (0.0 <= float(self.confidence) <= 1.0)
        ):
            raise InvalidReflectionReportError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
        object.__setattr__(self, "confidence", float(self.confidence))

        ids: list[str] = []
        raw_ids = self.related_entry_ids or ()
        if isinstance(raw_ids, (str, bytes)):
            raw_ids = (raw_ids,)
        for entry_id in raw_ids:
            if not isinstance(entry_id, str) or not entry_id.strip():
                raise InvalidReflectionReportError(
                    "related_entry_ids must contain non-empty strings"
                )
            ids.append(entry_id.strip())
        object.__setattr__(self, "related_entry_ids", tuple(ids))

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization."""
        return {
            "category": self.category,
            "severity": self.severity,
            "description": self.description,
            "related_entry_ids": list(self.related_entry_ids),
            "confidence": self.confidence,
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ReflectionFinding:
        """Canonical deserialization from mapping."""
        if not isinstance(payload, Mapping):
            raise InvalidReflectionReportError("payload must be a mapping")

        category = payload.get("category")
        severity = payload.get("severity")
        description = payload.get("description")
        related = payload.get("related_entry_ids", ())
        confidence = payload.get("confidence", 1.0)

        if not isinstance(category, str):
            raise InvalidReflectionReportError("category field must be a string")
        if not isinstance(severity, str):
            raise InvalidReflectionReportError("severity field must be a string")
        if not isinstance(description, str):
            raise InvalidReflectionReportError("description field must be a string")

        return cls(
            category=category,
            severity=severity,
            description=description,
            related_entry_ids=tuple(related) if isinstance(related, Sequence) else (),
            confidence=confidence,
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ReflectionFinding:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(payload)


@dataclass(frozen=True, slots=True)
class ReflectionQuery:
    """Specification of query criteria for selecting resolution memory entries for analysis."""

    decision: ResolutionDecision | str | None = None
    execution_status: ExecutionStatus | str | None = None
    minimum_confidence: float | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None

    def __post_init__(self) -> None:
        dec_val = self.decision
        if dec_val is not None:
            if isinstance(dec_val, str):
                try:
                    dec_val = ResolutionDecision(dec_val.strip().lower())
                except ValueError as exc:
                    raise InvalidReflectionReportError(
                        f"Unknown ResolutionDecision: {dec_val}"
                    ) from exc
            elif not isinstance(dec_val, ResolutionDecision):
                raise InvalidReflectionReportError(
                    f"Invalid decision filter: {dec_val}"
                )
            object.__setattr__(self, "decision", dec_val)

        exec_val = self.execution_status
        if exec_val is not None:
            if isinstance(exec_val, str):
                try:
                    exec_val = ExecutionStatus(exec_val.strip().lower())
                except ValueError:
                    try:
                        exec_val = ExecutionStatus[exec_val.strip().upper()]
                    except KeyError as exc:
                        raise InvalidReflectionReportError(
                            f"Unknown ExecutionStatus: {exec_val}"
                        ) from exc
            elif not isinstance(exec_val, ExecutionStatus):
                raise InvalidReflectionReportError(
                    f"Invalid execution_status filter: {exec_val}"
                )
            object.__setattr__(self, "execution_status", exec_val)

        if self.minimum_confidence is not None:
            if (
                isinstance(self.minimum_confidence, bool)
                or not isinstance(self.minimum_confidence, (int, float))
                or not (0.0 <= float(self.minimum_confidence) <= 1.0)
            ):
                raise InvalidReflectionReportError(
                    f"minimum_confidence must be between 0.0 and 1.0, got {self.minimum_confidence}"
                )
            object.__setattr__(
                self, "minimum_confidence", float(self.minimum_confidence)
            )

        _require_aware(self.created_after, "created_after")
        _require_aware(self.created_before, "created_before")

        if (
            self.created_after is not None
            and self.created_before is not None
            and self.created_before < self.created_after
        ):
            raise InvalidReflectionReportError(
                "created_before cannot be earlier than created_after"
            )

    def matches(self, entry: ResolutionMemoryEntry) -> bool:
        """Check whether a resolution memory entry matches this query."""
        if not isinstance(entry, ResolutionMemoryEntry):
            return False

        if self.decision is not None and entry.decision != self.decision:
            return False

        if (
            self.execution_status is not None
            and entry.execution_status != self.execution_status
        ):
            return False

        if (
            self.minimum_confidence is not None
            and entry.confidence < self.minimum_confidence
        ):
            return False

        if self.created_after is not None and entry.created_at < self.created_after:
            return False

        return not (
            self.created_before is not None and entry.created_at > self.created_before
        )

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization."""
        return {
            "decision": self.decision.value if self.decision else None,
            "execution_status": (
                self.execution_status.value if self.execution_status else None
            ),
            "minimum_confidence": self.minimum_confidence,
            "created_after": (
                self.created_after.isoformat() if self.created_after else None
            ),
            "created_before": (
                self.created_before.isoformat() if self.created_before else None
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ReflectionQuery:
        """Canonical deserialization from mapping."""
        if not isinstance(payload, Mapping):
            raise InvalidReflectionReportError("payload must be a mapping")

        after_val = payload.get("created_after")
        before_val = payload.get("created_before")

        created_after = (
            datetime.fromisoformat(after_val) if isinstance(after_val, str) else None
        )
        created_before = (
            datetime.fromisoformat(before_val) if isinstance(before_val, str) else None
        )

        return cls(
            decision=payload.get("decision"),
            execution_status=payload.get("execution_status"),
            minimum_confidence=payload.get("minimum_confidence"),
            created_after=created_after,
            created_before=created_before,
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ReflectionQuery:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(payload)


@dataclass(frozen=True, slots=True)
class CognitiveReflectionReport:
    """Immutable report representing an analytical reflection over cognitive history."""

    id: str
    created_at: datetime
    analysed_entries: int
    contradiction_count: int
    resolution_count: int
    human_review_count: int
    auto_resolution_count: int
    average_confidence: float
    decision_distribution: Mapping[str, int]
    contradiction_distribution: Mapping[str, int]
    policy_distribution: Mapping[str, int]
    findings: tuple[ReflectionFinding, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise InvalidReflectionReportError("id must be a non-empty string")
        object.__setattr__(self, "id", self.id.strip())

        if not isinstance(self.created_at, datetime):
            raise InvalidReflectionReportError("created_at must be a datetime")
        _require_aware(self.created_at, "created_at")

        for field_name, val in (
            ("analysed_entries", self.analysed_entries),
            ("contradiction_count", self.contradiction_count),
            ("resolution_count", self.resolution_count),
            ("human_review_count", self.human_review_count),
            ("auto_resolution_count", self.auto_resolution_count),
        ):
            if isinstance(val, bool) or not isinstance(val, int) or val < 0:
                raise InvalidReflectionReportError(
                    f"{field_name} must be a non-negative integer, got {val}"
                )

        if (
            isinstance(self.average_confidence, bool)
            or not isinstance(self.average_confidence, (int, float))
            or not (0.0 <= float(self.average_confidence) <= 1.0)
        ):
            raise InvalidReflectionReportError(
                f"average_confidence must be between 0.0 and 1.0, got {self.average_confidence}"
            )
        object.__setattr__(self, "average_confidence", float(self.average_confidence))

        def _clean_dist(
            dist: Mapping[str, int] | None, dist_name: str
        ) -> MappingProxyType[str, int]:
            res: dict[str, int] = {}
            if dist is not None:
                if not isinstance(dist, Mapping):
                    raise InvalidReflectionReportError(f"{dist_name} must be a mapping")
                for k, v in dist.items():
                    if not isinstance(k, str) or not k.strip():
                        raise InvalidReflectionReportError(
                            f"{dist_name} keys must be non-empty strings"
                        )
                    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                        raise InvalidReflectionReportError(
                            f"{dist_name} values must be non-negative integers"
                        )
                    res[k.strip().lower()] = v
            return MappingProxyType(res)

        object.__setattr__(
            self,
            "decision_distribution",
            _clean_dist(self.decision_distribution, "decision_distribution"),
        )
        object.__setattr__(
            self,
            "contradiction_distribution",
            _clean_dist(self.contradiction_distribution, "contradiction_distribution"),
        )
        object.__setattr__(
            self,
            "policy_distribution",
            _clean_dist(self.policy_distribution, "policy_distribution"),
        )

        cleaned_findings: list[ReflectionFinding] = []
        raw_findings = self.findings or ()
        if isinstance(raw_findings, (str, bytes, ReflectionFinding)):
            raw_findings = (raw_findings,)
        for f in raw_findings:
            if isinstance(f, ReflectionFinding):
                cleaned_findings.append(f)
            elif isinstance(f, str):
                if not f.strip():
                    raise InvalidReflectionReportError(
                        "finding description string cannot be empty"
                    )
                cleaned_findings.append(
                    ReflectionFinding(
                        category="general",
                        severity="info",
                        description=f.strip(),
                        related_entry_ids=(),
                        confidence=1.0,
                    )
                )
            elif isinstance(f, Mapping):
                cleaned_findings.append(ReflectionFinding.from_mapping(f))
            else:
                raise InvalidReflectionReportError(
                    f"Invalid finding item type: {type(f).__name__}"
                )
        object.__setattr__(self, "findings", tuple(cleaned_findings))

        cleaned_warnings: list[str] = []
        raw_warnings = self.warnings or ()
        if isinstance(raw_warnings, (str, bytes)):
            raw_warnings = (raw_warnings,)
        for w in raw_warnings:
            if not isinstance(w, str) or not w.strip():
                raise InvalidReflectionReportError(
                    "warnings must contain non-empty strings"
                )
            cleaned_warnings.append(w.strip())
        object.__setattr__(self, "warnings", tuple(cleaned_warnings))

        meta = self.metadata or {}
        if not isinstance(meta, Mapping):
            raise InvalidReflectionReportError("metadata must be a mapping")
        object.__setattr__(self, "metadata", MappingProxyType(dict(meta)))

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization."""
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "analysed_entries": self.analysed_entries,
            "contradiction_count": self.contradiction_count,
            "resolution_count": self.resolution_count,
            "human_review_count": self.human_review_count,
            "auto_resolution_count": self.auto_resolution_count,
            "average_confidence": self.average_confidence,
            "decision_distribution": dict(self.decision_distribution),
            "contradiction_distribution": dict(self.contradiction_distribution),
            "policy_distribution": dict(self.policy_distribution),
            "findings": [f.serialize() for f in self.findings],
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> CognitiveReflectionReport:
        """Canonical deserialization from mapping."""
        if not isinstance(payload, Mapping):
            raise InvalidReflectionReportError("payload must be a mapping")

        report_id = payload.get("id")
        created_val = payload.get("created_at")

        if not isinstance(report_id, str):
            raise InvalidReflectionReportError("id field must be a string")
        if not isinstance(created_val, str):
            raise InvalidReflectionReportError("created_at field must be a string")

        try:
            created_at = datetime.fromisoformat(created_val)
        except (ValueError, TypeError) as exc:
            raise InvalidReflectionReportError(
                f"Invalid ISO datetime string for created_at: '{created_val}'"
            ) from exc

        findings_raw = payload.get("findings", ())
        parsed_findings: list[ReflectionFinding] = []
        if isinstance(findings_raw, Sequence):
            for item in findings_raw:
                if isinstance(item, ReflectionFinding):
                    parsed_findings.append(item)
                elif isinstance(item, Mapping):
                    parsed_findings.append(ReflectionFinding.from_mapping(item))
                elif isinstance(item, str):
                    parsed_findings.append(
                        ReflectionFinding(
                            category="general",
                            severity="info",
                            description=item,
                            related_entry_ids=(),
                            confidence=1.0,
                        )
                    )

        return cls(
            id=report_id,
            created_at=created_at,
            analysed_entries=payload.get("analysed_entries", 0),
            contradiction_count=payload.get("contradiction_count", 0),
            resolution_count=payload.get("resolution_count", 0),
            human_review_count=payload.get("human_review_count", 0),
            auto_resolution_count=payload.get("auto_resolution_count", 0),
            average_confidence=payload.get("average_confidence", 0.0),
            decision_distribution=payload.get("decision_distribution", {}),
            contradiction_distribution=payload.get("contradiction_distribution", {}),
            policy_distribution=payload.get("policy_distribution", {}),
            findings=tuple(parsed_findings),
            warnings=tuple(payload.get("warnings", ())),
            metadata=payload.get("metadata", {}),
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CognitiveReflectionReport:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(payload)
