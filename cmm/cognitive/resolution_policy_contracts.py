"""Phase 8.11 – Contradiction Resolution Policy Contracts & Enums.

Defines immutable, typed contracts for evaluating resolution proposals against cognitive policies.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any

from cmm.cognitive.errors import InvalidResolutionPolicyEvaluationError


class PolicyDecision(str, Enum):
    """Enumeration of possible resolution policy evaluation decisions."""

    AUTO_APPROVED = "auto_approved"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class PolicySeverity(str, Enum):
    """Enumeration of policy risk/impact severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class ResolutionPolicyEvaluation:
    """Immutable evaluation result of a contradiction resolution proposal by policy rules."""

    proposal_id: str
    decision: PolicyDecision
    severity: PolicySeverity
    confidence: float
    allowed: bool
    reasons: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_id, str) or not self.proposal_id.strip():
            raise InvalidResolutionPolicyEvaluationError(
                "proposal_id must be a non-empty string"
            )
        object.__setattr__(self, "proposal_id", self.proposal_id.strip())

        dec_val = self.decision
        if isinstance(dec_val, str):
            try:
                dec_val = PolicyDecision(dec_val.lower())
            except ValueError:
                try:
                    dec_val = PolicyDecision[dec_val.upper()]
                except KeyError as exc:
                    raise InvalidResolutionPolicyEvaluationError(
                        f"Unknown PolicyDecision: {dec_val}"
                    ) from exc
        elif not isinstance(dec_val, PolicyDecision):
            raise InvalidResolutionPolicyEvaluationError(f"Invalid decision: {dec_val}")
        object.__setattr__(self, "decision", dec_val)

        sev_val = self.severity
        if isinstance(sev_val, str):
            try:
                sev_val = PolicySeverity(sev_val.lower())
            except ValueError:
                try:
                    sev_val = PolicySeverity[sev_val.upper()]
                except KeyError as exc:
                    raise InvalidResolutionPolicyEvaluationError(
                        f"Unknown PolicySeverity: {sev_val}"
                    ) from exc
        elif not isinstance(sev_val, PolicySeverity):
            raise InvalidResolutionPolicyEvaluationError(f"Invalid severity: {sev_val}")
        object.__setattr__(self, "severity", sev_val)

        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not (0.0 <= float(self.confidence) <= 1.0)
        ):
            raise InvalidResolutionPolicyEvaluationError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
        object.__setattr__(self, "confidence", float(self.confidence))

        if not isinstance(self.allowed, bool):
            raise InvalidResolutionPolicyEvaluationError("allowed must be a boolean")

        if not isinstance(self.reasons, (tuple, list)):
            raise InvalidResolutionPolicyEvaluationError(
                "reasons must be a tuple or list of strings"
            )
        object.__setattr__(self, "reasons", tuple(str(r) for r in self.reasons))

        if not isinstance(self.warnings, (tuple, list)):
            raise InvalidResolutionPolicyEvaluationError(
                "warnings must be a tuple or list of strings"
            )
        object.__setattr__(self, "warnings", tuple(str(w) for w in self.warnings))

        object.__setattr__(
            self, "metadata", MappingProxyType(dict(self.metadata or {}))
        )

    def serialize(self) -> dict[str, Any]:
        """Canonical JSON-safe serialization."""
        return {
            "proposal_id": self.proposal_id,
            "decision": self.decision.value,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "allowed": self.allowed,
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }

    def to_dict(self) -> dict[str, Any]:
        """Compatibility alias for :meth:`serialize`."""
        return self.serialize()

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> ResolutionPolicyEvaluation:
        """Canonical deserialization from mapping."""
        if not isinstance(payload, Mapping):
            raise InvalidResolutionPolicyEvaluationError("payload must be a mapping")

        prop_id = payload.get("proposal_id")
        if not isinstance(prop_id, str):
            raise InvalidResolutionPolicyEvaluationError("proposal_id must be a string")

        dec_raw = payload.get("decision")
        if dec_raw is None:
            raise InvalidResolutionPolicyEvaluationError("decision is required")

        sev_raw = payload.get("severity")
        if sev_raw is None:
            raise InvalidResolutionPolicyEvaluationError("severity is required")

        conf_raw = payload.get("confidence")
        if conf_raw is None:
            raise InvalidResolutionPolicyEvaluationError("confidence is required")

        allowed_raw = payload.get("allowed")
        if allowed_raw is None:
            raise InvalidResolutionPolicyEvaluationError("allowed is required")

        return cls(
            proposal_id=prop_id,
            decision=dec_raw,
            severity=sev_raw,
            confidence=conf_raw,
            allowed=allowed_raw,
            reasons=tuple(payload.get("reasons") or ()),
            warnings=tuple(payload.get("warnings") or ()),
            metadata=dict(payload.get("metadata") or {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResolutionPolicyEvaluation:
        """Compatibility alias for :meth:`from_mapping`."""
        return cls.from_mapping(data)
