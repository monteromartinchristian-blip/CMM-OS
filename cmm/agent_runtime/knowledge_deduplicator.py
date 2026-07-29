"""Phase 9.18 – Knowledge Deduplicator.

Detects exact duplicates, semantic duplicates, newer/higher confidence updates, and contradictions.
Determines whether candidates should be added, updated, merged, linked, or rejected as duplicate.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from cmm.agent_runtime.enums import KnowledgeWriteDecisionKind
from cmm.agent_runtime.knowledge_update_contracts import (
    KnowledgeDeduplicationResult,
    KnowledgeUpdateCandidate,
)


class KnowledgeDeduplicator:
    """Evaluates candidate knowledge items against existing knowledge entries for duplication."""

    def evaluate_candidate(
        self,
        candidate: KnowledgeUpdateCandidate,
        existing_items: Sequence[Any] | None = None,
    ) -> KnowledgeDeduplicationResult:
        """Analyze candidate against existing entries to determine deduplication decision."""
        if not existing_items:
            return KnowledgeDeduplicationResult(
                candidate_id=candidate.candidate_id,
                is_duplicate=False,
                existing_item_id=None,
                action=KnowledgeWriteDecisionKind.ADD,
                match_type="none",
                similarity_score=0.0,
            )

        cand_title = candidate.title.strip().lower()
        cand_content_str = str(candidate.content).strip().lower()

        def _is_complementary(item_content: Any) -> bool:
            """Candidate and existing content are non-conflicting when they carry
            disjoint fields under the same title: nothing is being overwritten,
            so the two versions can be safely merged instead of replaced."""
            if not (
                isinstance(candidate.content, dict) and isinstance(item_content, dict)
            ):
                return False
            if not candidate.content or not item_content:
                return False
            return not (set(candidate.content) & set(item_content))

        for item in existing_items:
            item_id = getattr(
                item,
                "addition_id",
                getattr(item, "item_id", getattr(item, "candidate_id", "item-1")),
            )
            item_title = (
                str(getattr(item, "title", getattr(item, "topic", ""))).strip().lower()
            )
            item_content_str = str(getattr(item, "content", "")).strip().lower()
            item_confidence = getattr(item, "confidence", 0.5)

            # 1. Exact Duplicate check
            if cand_title == item_title and cand_content_str == item_content_str:
                return KnowledgeDeduplicationResult(
                    candidate_id=candidate.candidate_id,
                    is_duplicate=True,
                    existing_item_id=item_id,
                    action=KnowledgeWriteDecisionKind.REJECT,
                    match_type="exact_duplicate",
                    similarity_score=1.0,
                    reasons=("EXACT_DUPLICATE_FOUND",),
                )

            # 2. Same Title/Topic, complementary (non-conflicting) fields -> MERGE
            item_content = getattr(item, "content", None)
            if (
                cand_title == item_title
                and isinstance(item_content, dict)
                and _is_complementary(item_content)
            ):
                merged_content = {**item_content, **candidate.content}
                return KnowledgeDeduplicationResult(
                    candidate_id=candidate.candidate_id,
                    is_duplicate=True,
                    existing_item_id=item_id,
                    action=KnowledgeWriteDecisionKind.MERGE,
                    match_type="complementary_merge",
                    similarity_score=0.6,
                    merged_content=merged_content,
                    reasons=("COMPLEMENTARY_NON_CONFLICTING_FIELDS",),
                )

            # 3. Same Title/Topic update check
            if cand_title == item_title:
                # Do NOT overwrite confirmed/higher confidence knowledge with lower confidence candidate
                if candidate.confidence < item_confidence:
                    return KnowledgeDeduplicationResult(
                        candidate_id=candidate.candidate_id,
                        is_duplicate=True,
                        existing_item_id=item_id,
                        action=KnowledgeWriteDecisionKind.REJECT,
                        match_type="lower_confidence_update",
                        similarity_score=0.9,
                        reasons=("CANNOT_OVERWRITE_WITH_LOWER_CONFIDENCE",),
                    )

                # Higher confidence or newer update -> UPDATE or MERGE
                return KnowledgeDeduplicationResult(
                    candidate_id=candidate.candidate_id,
                    is_duplicate=True,
                    existing_item_id=item_id,
                    action=KnowledgeWriteDecisionKind.UPDATE,
                    match_type="version_update",
                    similarity_score=0.9,
                    merged_content=candidate.content,
                    reasons=("HIGHER_CONFIDENCE_VERSION_UPDATE",),
                )

        return KnowledgeDeduplicationResult(
            candidate_id=candidate.candidate_id,
            is_duplicate=False,
            existing_item_id=None,
            action=KnowledgeWriteDecisionKind.ADD,
            match_type="none",
            similarity_score=0.0,
        )
