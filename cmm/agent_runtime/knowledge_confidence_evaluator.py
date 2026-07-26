"""Phase 9.18 – Knowledge Confidence Evaluator.

Evaluates confidence score and level for candidate knowledge based on evidence count,
validation status, reproducibility, contradictions, and user confirmations.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from cmm.agent_runtime.enums import KnowledgeCandidateKind, KnowledgeConfidenceLevel
from cmm.agent_runtime.knowledge_update_contracts import KnowledgeUpdateCandidate


@dataclass(frozen=True)
class KnowledgeConfidenceAssessment:
    """Structured evaluation of candidate confidence level and supporting evidence."""

    confidence_score: float
    level: KnowledgeConfidenceLevel
    reason_codes: tuple[str, ...]
    evidence_count: int
    verified: bool
    metadata: Mapping[str, Any] = field(default_factory=dict)


class KnowledgeConfidenceEvaluator:
    """Evaluates candidate confidence level adhering to strict verification rules."""

    def evaluate_confidence(
        self,
        candidate: KnowledgeUpdateCandidate,
        has_failed_validation: bool = False,
        has_unresolved_contradiction: bool = False,
    ) -> KnowledgeConfidenceAssessment:
        """Calculate confidence score and classification level."""
        reasons: list[str] = []
        score = candidate.confidence
        evidence_count = len(candidate.evidence_ids)

        # 1. Failed validation penalty
        if has_failed_validation:
            score *= 0.5
            reasons.append("VALIDATION_FAILED_PENALTY")

        # 2. Evidence count adjustments
        if evidence_count == 0:
            score *= 0.7
            reasons.append("NO_EXPLICIT_EVIDENCE")
        elif evidence_count > 1:
            score = min(1.0, score * 1.15)
            reasons.append("MULTIPLE_EVIDENCE_BOOST")

        # 3. Reproducible error rule
        if candidate.kind == KnowledgeCandidateKind.REPRODUCIBLE_ERROR:
            attempts = (
                candidate.content.get("attempt_count", 1)
                if isinstance(candidate.content, dict)
                else 1
            )
            if evidence_count < 2 and attempts < 2:
                score *= 0.6
                reasons.append("UNREPRODUCED_ERROR_SINGLE_EVIDENCE_PENALTY")

        # 4. User preference user statement rule
        is_user_confirmed = False
        if candidate.kind == KnowledgeCandidateKind.EXPLICIT_PREFERENCE:
            is_user_confirmed = (
                bool(candidate.content.get("user_confirmed", False))
                if isinstance(candidate.content, dict)
                else False
            )
            if is_user_confirmed:
                score = 1.0
                reasons.append("USER_EXPLICIT_CONFIRMATION")

        # 5. Classify level & handle unresolved contradictions
        verified = False
        if has_unresolved_contradiction:
            reasons.append("UNRESOLVED_CONTRADICTION_PRESENT")
            # Block VERIFIED level
            score = min(score, 0.84)

        if (
            score >= 0.95
            and not has_unresolved_contradiction
            and (evidence_count >= 1 or is_user_confirmed)
        ):
            level = KnowledgeConfidenceLevel.VERIFIED
            verified = True
        elif score >= 0.8:
            level = KnowledgeConfidenceLevel.HIGH
        elif score >= 0.6:
            level = KnowledgeConfidenceLevel.MEDIUM
        else:
            level = KnowledgeConfidenceLevel.LOW

        return KnowledgeConfidenceAssessment(
            confidence_score=round(score, 4),
            level=level,
            reason_codes=tuple(reasons),
            evidence_count=evidence_count,
            verified=verified,
        )
