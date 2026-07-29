"""Phase 9.18 – Memory Update Policy Adapter.

Evaluates memory write candidates against privacy, permissions, sensitivity, and confirmation policies.
Produces MemoryWriteDecision instances without directly accessing or mutating underlying memory tables.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from cmm.agent_runtime.enums import MemoryWriteDecisionKind
from cmm.agent_runtime.knowledge_update_contracts import (
    KnowledgeConfirmationRequirement,
    MemoryUpdateCandidate,
    MemoryWriteDecision,
)


class MemoryUpdatePolicyAdapter:
    """Evaluates memory write policy decisions for memory update candidates."""

    def evaluate_candidate(
        self,
        candidate: MemoryUpdateCandidate,
        granted_permissions: Sequence[str] = (),
    ) -> MemoryWriteDecision:
        """Analyze memory update candidate against policy rules."""
        reasons: list[str] = []

        # 1. Check inferred preference rule
        if (
            candidate.memory_type == "preference"
            and not candidate.is_explicit_preference
        ):
            reasons.append("INFERRED_PREFERENCE_REJECTED")
            return MemoryWriteDecision(
                decision_id=f"mem-dec-{uuid.uuid4().hex[:8]}",
                candidate_id=candidate.candidate_id,
                decision=MemoryWriteDecisionKind.REJECT,
                reason_codes=tuple(reasons),
            )

        # 2. Check unconfirmed personal decision rule
        if (
            candidate.memory_type == "personal_decision"
            and not candidate.user_confirmed
        ):
            reasons.append("UNCONFIRMED_PERSONAL_DECISION_REJECTED")
            return MemoryWriteDecision(
                decision_id=f"mem-dec-{uuid.uuid4().hex[:8]}",
                candidate_id=candidate.candidate_id,
                decision=MemoryWriteDecisionKind.REJECT,
                reason_codes=tuple(reasons),
            )

        # 3. Check secrets in sensitivity
        if candidate.sensitivity and candidate.sensitivity.contains_secrets:
            reasons.append("SECRET_DATA_MEMORY_REJECTED")
            return MemoryWriteDecision(
                decision_id=f"mem-dec-{uuid.uuid4().hex[:8]}",
                candidate_id=candidate.candidate_id,
                decision=MemoryWriteDecisionKind.REJECT,
                reason_codes=tuple(reasons),
            )

        # 4. Check sensitivity requiring confirmation / redaction
        if (
            candidate.sensitivity
            and (
                candidate.sensitivity.contains_personal_data
                or candidate.sensitivity.level.value in ("restricted", "confidential")
            )
            and not candidate.user_confirmed
        ):
            reasons.append("SENSITIVE_DATA_REQUIRES_CONFIRMATION")
            req = KnowledgeConfirmationRequirement(
                requirement_id=f"req-{uuid.uuid4().hex[:8]}",
                required=True,
                reason="Sensitive memory item requires explicit user confirmation",
                scope=candidate.key,
            )
            return MemoryWriteDecision(
                decision_id=f"mem-dec-{uuid.uuid4().hex[:8]}",
                candidate_id=candidate.candidate_id,
                decision=MemoryWriteDecisionKind.ALLOW_WITH_CONFIRMATION,
                reason_codes=tuple(reasons),
                confirmation_req=req,
            )

        # 5. Permission check
        required_perm = f"memory:write:{candidate.memory_type}"
        if (
            granted_permissions
            and required_perm not in granted_permissions
            and "memory:write:*" not in granted_permissions
        ):
            reasons.append("PERMISSION_MISMATCH")
            return MemoryWriteDecision(
                decision_id=f"mem-dec-{uuid.uuid4().hex[:8]}",
                candidate_id=candidate.candidate_id,
                decision=MemoryWriteDecisionKind.REJECT,
                reason_codes=tuple(reasons),
            )

        reasons.append("MEMORY_WRITE_ALLOWED")
        return MemoryWriteDecision(
            decision_id=f"mem-dec-{uuid.uuid4().hex[:8]}",
            candidate_id=candidate.candidate_id,
            decision=MemoryWriteDecisionKind.ALLOW,
            reason_codes=tuple(reasons),
        )
