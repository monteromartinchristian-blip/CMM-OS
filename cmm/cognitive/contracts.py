from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from cmm.cognitive.enums import (
    CognitiveActorKind,
    CognitiveSeverity,
    CognitiveStatus,
)
from cmm.cognitive.errors import (
    InvalidCognitiveContractError,
    InvalidConfidenceError,
)
from cmm.cognitive.identifiers import generate_cognitive_id


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class Confidence:
    value: float
    source: str | None = None
    reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise InvalidConfidenceError(
                "confidence value must be a number between 0.0 and 1.0"
            )

        normalized = float(self.value)
        if not 0.0 <= normalized <= 1.0:
            raise InvalidConfidenceError("confidence value must be between 0.0 and 1.0")

        object.__setattr__(self, "value", normalized)
        object.__setattr__(self, "reasons", tuple(self.reasons))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "source": self.source,
            "reasons": list(self.reasons),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class CognitiveActor:
    id: str
    kind: CognitiveActorKind
    name: str | None = None
    permissions: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidCognitiveContractError("cognitive actor id must not be empty")

        if self.name is not None and not self.name.strip():
            raise InvalidCognitiveContractError(
                "cognitive actor name must not be blank"
            )

        object.__setattr__(self, "permissions", tuple(self.permissions))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "name": self.name,
            "permissions": list(self.permissions),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class CognitiveFinding:
    code: str
    message: str
    severity: CognitiveSeverity = CognitiveSeverity.INFO
    blocking: bool = False
    source: str = "cognitive"
    related_ids: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise InvalidCognitiveContractError(
                "cognitive finding code must not be empty"
            )

        if not self.message.strip():
            raise InvalidCognitiveContractError(
                "cognitive finding message must not be empty"
            )

        if not self.source.strip():
            raise InvalidCognitiveContractError(
                "cognitive finding source must not be empty"
            )

        object.__setattr__(self, "related_ids", tuple(self.related_ids))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "blocking": self.blocking,
            "source": self.source,
            "related_ids": list(self.related_ids),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class CognitiveResult:
    objective: str
    status: CognitiveStatus
    confidence: Confidence
    id: str = field(
        default_factory=lambda: generate_cognitive_id(
            "cognitive-result",
            "general",
        )
    )
    findings: tuple[CognitiveFinding, ...] = ()
    trace_id: str | None = None
    session_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise InvalidCognitiveContractError("cognitive result id must not be empty")

        if not self.objective.strip():
            raise InvalidCognitiveContractError(
                "cognitive result objective must not be empty"
            )

        if self.created_at.tzinfo is None:
            raise InvalidCognitiveContractError(
                "cognitive result created_at must be timezone-aware"
            )

        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def blocking_findings(self) -> tuple[CognitiveFinding, ...]:
        return tuple(finding for finding in self.findings if finding.blocking)

    @property
    def successful(self) -> bool:
        return self.status is CognitiveStatus.COMPLETED and not self.blocking_findings

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "objective": self.objective,
            "status": self.status.value,
            "confidence": self.confidence.to_dict(),
            "findings": [finding.to_dict() for finding in self.findings],
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "successful": self.successful,
            "metadata": dict(self.metadata),
        }
