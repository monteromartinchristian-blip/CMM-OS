"""Phase 9.18 – Knowledge Contradiction Resolver.

Detects contradictions between candidate knowledge and existing knowledge entries,
evaluating confidence, temporal validity, and evidence to propose invalidation,
coexistence, or human approval escalation while preserving historical provenance.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from cmm.agent_runtime.knowledge_update_contracts import KnowledgeUpdateCandidate


@dataclass(frozen=True)
class ContradictionResolutionProposal:
    """Structured resolution proposal when a contradiction is detected."""

    conflict_detected: bool
    target_item_id: str | None
    resolution_strategy: (
        str  # "invalidation", "temporal_coexistence", "require_approval", "none"
    )
    invalidation_reason: str | None
    reasons: tuple[str, ...]
    requires_human_review: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)


class KnowledgeContradictionResolver:
    """Detects and resolves contradictions adhering to safety and provenance preservation rules."""

    def resolve_contradiction(
        self,
        candidate: KnowledgeUpdateCandidate,
        existing_items: Sequence[Any] | None = None,
    ) -> ContradictionResolutionProposal:
        """Evaluate candidate for contradictions against existing knowledge entries."""
        if not existing_items:
            return ContradictionResolutionProposal(
                conflict_detected=False,
                target_item_id=None,
                resolution_strategy="none",
                invalidation_reason=None,
                reasons=(),
                requires_human_review=False,
            )

        cand_title = candidate.title.strip().lower()
        cand_scope = candidate.scope

        for item in existing_items:
            item_id = getattr(
                item,
                "addition_id",
                getattr(item, "item_id", getattr(item, "candidate_id", "item-1")),
            )
            item_title = (
                str(getattr(item, "title", getattr(item, "topic", ""))).strip().lower()
            )
            item_scope = getattr(item, "scope", {})
            item_confidence = getattr(item, "confidence", 0.5)
            item_content = getattr(item, "content", None)

            # Check if topics conflict
            if cand_title == item_title:
                # Disjoint, non-empty dict fields carry no conflicting claim: this
                # is complementary information to be merged, not a contradiction.
                if (
                    isinstance(candidate.content, dict)
                    and isinstance(item_content, dict)
                    and candidate.content
                    and item_content
                    and not (set(candidate.content) & set(item_content))
                ):
                    return ContradictionResolutionProposal(
                        conflict_detected=False,
                        target_item_id=None,
                        resolution_strategy="none",
                        invalidation_reason=None,
                        reasons=("COMPLEMENTARY_NON_CONFLICTING_FIELDS",),
                        requires_human_review=False,
                    )

                # Check scope differentiation
                if cand_scope and item_scope and cand_scope != item_scope:
                    return ContradictionResolutionProposal(
                        conflict_detected=True,
                        target_item_id=item_id,
                        resolution_strategy="temporal_coexistence",
                        invalidation_reason=None,
                        reasons=("DIFFERENT_SCOPES_COEXISTENCE",),
                        requires_human_review=False,
                    )

                # Check confidence differential
                diff = abs(candidate.confidence - item_confidence)

                # Similar confidence -> Escalate to human review
                if diff < 0.15:
                    return ContradictionResolutionProposal(
                        conflict_detected=True,
                        target_item_id=item_id,
                        resolution_strategy="require_approval",
                        invalidation_reason="Contradiction between entries with similar confidence scores",
                        reasons=("SIMILAR_CONFIDENCE_ESCALATE_TO_HUMAN",),
                        requires_human_review=True,
                    )

                # Candidate has significantly higher confidence -> Invalidate prior entry
                if candidate.confidence > item_confidence:
                    return ContradictionResolutionProposal(
                        conflict_detected=True,
                        target_item_id=item_id,
                        resolution_strategy="invalidation",
                        invalidation_reason=f"Superseded by higher confidence entry ({candidate.confidence:.2f} > {item_confidence:.2f})",
                        reasons=("HIGHER_CONFIDENCE_SUPERSEDES_PRIOR",),
                        requires_human_review=False,
                    )
                else:
                    # Existing entry has higher confidence -> Preserve existing, require review or skip
                    return ContradictionResolutionProposal(
                        conflict_detected=True,
                        target_item_id=item_id,
                        resolution_strategy="require_approval",
                        invalidation_reason=None,
                        reasons=("LOWER_CONFIDENCE_CONTRADICTION_BLOCKED",),
                        requires_human_review=True,
                    )

        return ContradictionResolutionProposal(
            conflict_detected=False,
            target_item_id=None,
            resolution_strategy="none",
            invalidation_reason=None,
            reasons=(),
            requires_human_review=False,
        )
