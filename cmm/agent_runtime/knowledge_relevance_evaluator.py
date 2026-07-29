"""Phase 9.18 – Knowledge Relevance and Utility Evaluator.

Evaluates candidates for future utility, reusability, temporal stability, storage cost vs. value,
and operational relevance to determine if candidate knowledge should be persisted.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from cmm.agent_runtime.enums import KnowledgeCandidateKind
from cmm.agent_runtime.knowledge_update_contracts import KnowledgeUpdateCandidate


@dataclass(frozen=True)
class KnowledgeRelevanceAssessment:
    """Structured result of relevance and utility evaluation for a candidate item."""

    relevant: bool
    utility_score: float
    reuse_score: float
    temporal_stability: str
    recommended_retention: str
    reason_codes: tuple[str, ...]
    confidence: float
    metadata: Mapping[str, Any] = field(default_factory=dict)


class KnowledgeRelevanceEvaluator:
    """Evaluates candidate relevance, operational utility, and retention value."""

    def evaluate_relevance(
        self, candidate: KnowledgeUpdateCandidate
    ) -> KnowledgeRelevanceAssessment:
        """Evaluate candidate relevance against utility and retention rules."""
        reasons: list[str] = []
        utility = candidate.relevance_score
        reuse = 1.0 if candidate.reusable else 0.3
        stability = candidate.temporal_stability

        # 1. Reject trivial / zero content candidates
        if not candidate.content or (
            isinstance(candidate.content, dict) and len(candidate.content) == 0
        ):
            reasons.append("TRIVIAL_EMPTY_CONTENT")
            return KnowledgeRelevanceAssessment(
                relevant=False,
                utility_score=0.0,
                reuse_score=0.0,
                temporal_stability="volatile",
                recommended_retention="none",
                reason_codes=tuple(reasons),
                confidence=1.0,
            )

        # 2. Reject temporary / single-run non-reusable items with low score
        if not candidate.reusable and candidate.relevance_score < 0.5:
            reasons.append("TEMPORARY_LOW_UTILITY")
            return KnowledgeRelevanceAssessment(
                relevant=False,
                utility_score=utility,
                reuse_score=reuse,
                temporal_stability="ephemeral",
                recommended_retention="none",
                reason_codes=tuple(reasons),
                confidence=0.9,
            )

        # 3. High storage cost / low value check
        content_repr = str(candidate.content)
        if len(content_repr) > 100_000 and candidate.relevance_score < 0.7:
            reasons.append("HIGH_STORAGE_COST_LOW_UTILITY")
            return KnowledgeRelevanceAssessment(
                relevant=False,
                utility_score=utility,
                reuse_score=reuse,
                temporal_stability=stability,
                recommended_retention="none",
                reason_codes=tuple(reasons),
                confidence=0.95,
            )

        # 4. Special evaluation by Kind
        if candidate.kind == KnowledgeCandidateKind.EXPLICIT_PREFERENCE:
            reasons.append("EXPLICIT_USER_PREFERENCE")
            utility = max(utility, 0.9)
            retention = "permanent"
        elif candidate.kind in (
            KnowledgeCandidateKind.SUCCESSFUL_STRATEGY,
            KnowledgeCandidateKind.REPRODUCIBLE_ERROR,
            KnowledgeCandidateKind.TECHNICAL_DEBT,
            KnowledgeCandidateKind.NEW_CAPABILITY,
        ):
            reasons.append("HIGH_VALUE_OPERATIONAL_PATTERN")
            utility = max(utility, 0.85)
            retention = "long_term"
        elif candidate.kind == KnowledgeCandidateKind.CONSTRAINT:
            reasons.append("EXPLICIT_KNOWLEDGE_GAP_OR_CONSTRAINT")
            retention = "medium_term"
        else:
            reasons.append("STANDARD_CANDIDATE_EVALUATION")
            retention = "medium_term" if candidate.reusable else "short_term"

        is_relevant = utility >= 0.5

        return KnowledgeRelevanceAssessment(
            relevant=is_relevant,
            utility_score=utility,
            reuse_score=reuse,
            temporal_stability=stability,
            recommended_retention=retention,
            reason_codes=tuple(reasons),
            confidence=min(1.0, (candidate.confidence + utility) / 2.0),
        )
