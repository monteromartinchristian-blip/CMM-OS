"""Phase 9.18 – Knowledge Update Policy Adapter.

Evaluates candidates against relevance, confidence, sensitivity, deduplication, and permissions
to select the precise KnowledgeWriteDecisionKind action for each item.
Does not write directly to Knowledge Store tables.
"""

from __future__ import annotations

from collections.abc import Sequence

from cmm.agent_runtime.enums import KnowledgeWriteDecisionKind
from cmm.agent_runtime.knowledge_update_contracts import KnowledgeUpdateCandidate


class KnowledgeUpdatePolicyAdapter:
    """Evaluates candidate knowledge items to produce structured write decisions."""

    def evaluate_candidate(
        self,
        candidate: KnowledgeUpdateCandidate,
        relevance_relevant: bool = True,
        confidence_level: str = "high",
        sensitivity_level: str = "public",
        dedup_action: KnowledgeWriteDecisionKind = KnowledgeWriteDecisionKind.ADD,
        contradiction_strategy: str = "none",
        granted_permissions: Sequence[str] = (),
    ) -> KnowledgeWriteDecisionKind:
        """Determine policy decision kind for candidate item."""
        # 1. Irrelevant or low utility candidates -> REJECT
        if not relevance_relevant:
            return KnowledgeWriteDecisionKind.REJECT

        # 2. Secret level -> REJECT
        if sensitivity_level == "secret":
            return KnowledgeWriteDecisionKind.REJECT

        # 3. Restricted sensitivity or Contradiction human review -> REQUIRE_APPROVAL
        if (
            sensitivity_level == "restricted"
            or contradiction_strategy == "require_approval"
        ):
            return KnowledgeWriteDecisionKind.REQUIRE_APPROVAL

        # 4. Invalidation strategy -> INVALIDATE
        if contradiction_strategy == "invalidation":
            return KnowledgeWriteDecisionKind.INVALIDATE

        # 5. Permission check
        required_perm = f"knowledge:write:{candidate.kind.value}"
        if (
            granted_permissions
            and required_perm not in granted_permissions
            and "knowledge:write:*" not in granted_permissions
        ):
            return KnowledgeWriteDecisionKind.REJECT

        # 6. Dependency mappings are stored as relations
        if candidate.kind.value == "dependency":
            return KnowledgeWriteDecisionKind.LINK

        # 6. Default to deduplication decision (ADD, UPDATE, MERGE, LINK, REJECT)
        return dedup_action
